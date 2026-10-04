import { getPrivateKey } from "./keystore.js";
import { fetchPeerKey } from "./key-api.js";
import { deriveConversationKey, seal, open } from "./crypto-service.js";

// Cache the recipient's public key per conversation.
// This prevents fetching the same public key before every message.
const peerKeyCache = new Map();

async function getPeerKeyForConversation(conversationId, otherUserId) {
  if (peerKeyCache.has(conversationId)) {
    return peerKeyCache.get(conversationId);
  }

  const peerKey = await fetchPeerKey(otherUserId);

  peerKeyCache.set(conversationId, peerKey);

  return peerKey;
}

// IndexedDB storage for each sender's message sequence number.
// The value survives page reloads so a sender never intentionally
// starts over at sequence 1 after refreshing.
const SEQ_DB_NAME = "securedove-sequences";
const SEQ_DB_VERSION = 1;
const SEQ_STORE = "sequences";

function openSequenceDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(SEQ_DB_NAME, SEQ_DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;

      if (!db.objectStoreNames.contains(SEQ_STORE)) {
        db.createObjectStore(SEQ_STORE);
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(
      new Error("Could not open the sequence database.")
    );
  });
}

async function nextSequence(userId) {
  const db = await openSequenceDb();

  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(SEQ_STORE, "readwrite");
      const store = transaction.objectStore(SEQ_STORE);

      const key = "seq:" + userId;
      const getRequest = store.get(key);

      getRequest.onerror = () => {
        reject(new Error("Could not read message sequence."));
      };

      getRequest.onsuccess = () => {
        const current = getRequest.result || 0;
        const next = current + 1;

        const putRequest = store.put(next, key);

        putRequest.onerror = () => {
          reject(new Error("Could not save message sequence."));
        };

        putRequest.onsuccess = () => {
          resolve(next);
        };
      };
    });
  } finally {
    db.close();
  }
}

export async function sendEncryptedMessage({
  conversationId,
  myUserId,
  otherUserId,
  text
}) {
  // Do not encrypt or send empty/whitespace-only messages.
  if (typeof text !== "string" || text.trim().length === 0) {
    throw new Error("Message cannot be empty.");
  }

  // Block oversized messages before encryption.
  const textBytes = new TextEncoder().encode(text);

  if (textBytes.length > 10 * 1024) {
    throw new Error("Message is too large.");
  }

  // Get this device's private key.
  const myPrivateKey = await getPrivateKey(myUserId);

  // Fetch the recipient's public key once per conversation.
  // If this fails, sending stops here. Plaintext is never sent.
  const peer = await getPeerKeyForConversation(
    conversationId,
    otherUserId
  );

  // Derive the shared AES encryption key.
  const conversationKey = await deriveConversationKey({
    myPrivateKey,
    theirPublicKey: peer.publicKey,
    myUserId,
    theirUserId: otherUserId
  });

  // Allocate the next persistent sequence number.
  const seq = await nextSequence(myUserId);

  // Encrypt the plaintext locally in the browser.
  const encrypted = await seal(
    conversationKey,
    conversationId,
    {
      text: text,
      seq: seq,
      sentAt: Date.now(),
      senderId: myUserId
    }
  );

  const envelope = {
    ciphertext: encrypted.ciphertext,
    iv: encrypted.iv,
    seq: seq
  };

  return envelope;
}

export async function postEncryptedMessage(conversationId, envelope) {
  const response = await fetch(
    "/api/conversations/" + encodeURIComponent(conversationId) + "/messages",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },

      // Only encrypted data is sent to the server.
      body: JSON.stringify({
        ciphertext: envelope.ciphertext,
        iv: envelope.iv,
        seq: envelope.seq
      })
    }
  );

  // A duplicate means this exact sequence number was already stored.
  // This can happen when retrying after the original response was lost.
  if (response.status === 409) {
    return {
      sent: true,
      duplicate: true
    };
  }

  // Any other failed request remains unsent.
  if (!response.ok) {
    return {
      sent: false,
      status: response.status
    };
  }

  const storedMessage = await response.json();

  // Do not mark the message sent unless the server returned
  // the stored message ID and server-generated timestamp.
  if (!storedMessage.id || !storedMessage.timestamp) {
    return {
      sent: false,
      status: response.status
    };
  }

  return {
    sent: true,
    duplicate: false,
    id: storedMessage.id,
    timestamp: storedMessage.timestamp
  };
}

function showUnsentMessage(text, conversationId, envelope) {
  const messageElement = document.createElement("div");

  const textElement = document.createElement("span");
  textElement.textContent = text + " (unsent)";

  const retryButton = document.createElement("button");
  retryButton.type = "button";
  retryButton.textContent = "Retry";

  retryButton.addEventListener("click", async () => {
    retryButton.disabled = true;
    retryButton.textContent = "Retrying...";

    try {
      // Reuse the exact same ciphertext, IV, and sequence number.
      const result = await postEncryptedMessage(
        conversationId,
        envelope
      );

      if (result.sent) {
        textElement.textContent = text;
        retryButton.remove();
        privateChatStatus.textContent = "Message sent.";
      } else {
        retryButton.disabled = false;
        retryButton.textContent = "Retry";
        privateChatStatus.textContent = "Message still unsent.";
      }
    } catch (error) {
      retryButton.disabled = false;
      retryButton.textContent = "Retry";
      privateChatStatus.textContent = "Message still unsent.";
    }
  });

  messageElement.appendChild(textElement);
  messageElement.appendChild(retryButton);

  privateMessages.appendChild(messageElement);
}

let activeConversationId = null;
let activeOtherUserId = null;
let activeOtherUsername = null;

const privateUserInput = document.getElementById("private-user-id");
const openPrivateChatButton = document.getElementById("open-private-chat");
const privateChatStatus = document.getElementById("private-chat-status");

openPrivateChatButton.addEventListener("click", async () => {
  const otherUserId = privateUserInput.value.trim();

  if (!otherUserId) {
    privateChatStatus.textContent = "Enter a user ID.";
    return;
  }

  privateChatStatus.textContent = "Opening conversation...";

  try {
    const response = await fetch("/api/conversations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        user_id: otherUserId
      })
    });

    if (!response.ok) {
      privateChatStatus.textContent = "Could not open conversation.";
      return;
    }

    const conversation = await response.json();

    activeConversationId = conversation.id;
    activeOtherUserId = otherUserId;
    activeOtherUsername = await getOtherUsername(conversation.id);

    const myUser = await getMyUser();
    privateChatStatus.textContent = "Loading encrypted messages...";
    await loadMessageHistory(activeConversationId, myUser, activeOtherUserId, activeOtherUsername);
    privateChatStatus.textContent = "Encrypted conversation ready.";

  } catch (error) {
    privateChatStatus.textContent = "Could not connect to the server.";
  }
});

const privateMessageForm = document.getElementById("private-message-form");
const privateMessageInput = document.getElementById("private-message");
const privateMessages = document.getElementById("private-messages");

async function getMyUser() {
  const response = await fetch("/api/users/@me");

  if (!response.ok) {
    throw new Error("Could not determine the current user.");
  }

  const user = await response.json();

  if (
    !user ||
    typeof user.id !== "string" ||
    typeof user.username !== "string"
  ) {
    throw new Error("Could not determine the current user.");
  }

  return user;
}

async function getOtherUsername(conversationId) {
  const response = await fetch("/api/conversations");

  if (!response.ok) {
    throw new Error("Could not load conversations.");
  }

  const data = await response.json();

  const conversation = data.conversations.find(
    (item) => item.id === conversationId
  );

  if (
    !conversation ||
    !conversation.other_participant ||
    typeof conversation.other_participant.username !== "string"
  ) {
    throw new Error("Could not determine the other user's username.");
  }

  return conversation.other_participant.username;
}

async function loadMessageHistory(conversationId, myUser, otherUserId, otherUsername) {
  const response = await fetch(
    "/api/conversations/" +
      encodeURIComponent(conversationId) +
      "/messages?limit=50"
  );

  if (!response.ok) {
    throw new Error("Could not load message history.");
  }

  const data = await response.json();

  // Get the keys needed to decrypt this conversation.
  const myPrivateKey = await getPrivateKey(myUser.id);

  const peer = await getPeerKeyForConversation(
    conversationId,
    otherUserId
  );

  const conversationKey = await deriveConversationKey({myPrivateKey, theirPublicKey: peer.publicKey, myUserId: myUser.id, theirUserId: otherUserId});

  // Clear messages from the previously opened conversation.
  privateMessages.replaceChildren();

  for (const message of data.messages) {
    try {
      const payload = await open(
        conversationKey,
        conversationId,
        {
          ciphertext: message.ciphertext,
          iv: message.iv
        }
      );

      // Make sure encrypted metadata agrees with the server envelope.
      if (
        payload.senderId !== message.sender_id ||
        payload.seq !== message.seq
      ) {
        continue;
      }

      const messageElement = document.createElement("div");

      const senderElement = document.createElement("strong");

      if (message.sender_id === myUser.id) {
        senderElement.textContent = myUser.username + ": ";
      } else {
        senderElement.textContent = otherUsername + ": ";
      }

      const textElement = document.createElement("span");
      textElement.textContent = payload.text;

      messageElement.appendChild(senderElement);
      messageElement.appendChild(textElement);

      privateMessages.appendChild(messageElement);
    } catch (error) {
      console.error(
        "Could not decrypt historical message:",
        error
      );
    }
  }
}

privateMessageForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!activeConversationId || !activeOtherUserId) {
    privateChatStatus.textContent = "Open a private conversation first.";
    return;
  }

  const text = privateMessageInput.value;

  // Keep the encrypted envelope available in case sending fails.
  let envelope = null;

  try {
    privateChatStatus.textContent = "Encrypting message...";

    const myUser = await getMyUser();
    const myUserId = myUser.id;

    // Encrypt the message locally.
    envelope = await sendEncryptedMessage({
      conversationId: activeConversationId,
      myUserId: myUserId,
      otherUserId: activeOtherUserId,
      text: text
    });

    privateChatStatus.textContent = "Sending encrypted message...";

    // Only the encrypted envelope is sent to the server.
    const result = await postEncryptedMessage(
      activeConversationId,
      envelope
    );

    if (!result.sent) {
      showUnsentMessage(text, activeConversationId, envelope);
      privateMessageInput.value = "";
      privateChatStatus.textContent = "Message unsent.";
      return;
    }

    // Only display the message as sent after server confirmation.
    const messageElement = document.createElement("div");
    const senderElement = document.createElement("strong");

    senderElement.textContent = myUser.username + ": ";

    const textElement = document.createElement("span");
    textElement.textContent = text;

    messageElement.appendChild(senderElement);
    messageElement.appendChild(textElement);
    privateMessages.appendChild(messageElement);

    privateMessageInput.value = "";
    privateChatStatus.textContent = "Message sent.";

  } catch (error) {
    // If encryption succeeded but sending failed, preserve the exact
    // ciphertext, IV, and sequence number so Retry can resend them.
    if (envelope !== null) {
      showUnsentMessage(text, activeConversationId, envelope);
      privateMessageInput.value = "";
      privateChatStatus.textContent = "Message unsent.";
      return;
    }

    // Encryption/key setup failed, so there is no encrypted message to retry.
    privateChatStatus.textContent =
      error.message || "Could not encrypt message.";
  }
});

function connectPrivateWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";

  const socket = new WebSocket(
    protocol + "//" + window.location.host + "/websocket"
  );

  socket.addEventListener("open", () => {
    console.log("Private message WebSocket connected.");
  });

  socket.addEventListener("message", async (event) => {
    let data;

    try {
      data = JSON.parse(event.data);
    } catch (error) {
      return;
    }

    // Ignore messages that are not private encrypted messages.
    if (data.messageType !== "encrypted_message") {
      return;
    }

    try {
      const myUser = await getMyUser();
      const myUserId = myUser.id;

      // Ignore messages that are not addressed to this user.
      if (data.recipient_id !== myUserId) {
        return;
      }

      const myPrivateKey = await getPrivateKey(myUserId);
      const peer = await getPeerKeyForConversation(data.conversation_id, data.sender_id);
      const conversationKey = await deriveConversationKey({myPrivateKey, theirPublicKey: peer.publicKey, myUserId: myUserId, theirUserId: data.sender_id});

      // Decrypt and authenticate the message locally.
      const payload = await open(conversationKey, data.conversation_id,
        {
          ciphertext: data.ciphertext, 
          iv: data.iv
        });

      // The encrypted metadata must match the server envelope.
      if (payload.senderId !== data.sender_id || payload.seq !== data.seq) 
        {
          throw new Error("Encrypted message metadata does not match.");
        }

      // Only display it if this conversation is currently open.
      if (data.conversation_id !== activeConversationId) {
        privateChatStatus.textContent = "New encrypted message received in another conversation.";
        return;
      }

      const messageElement = document.createElement("div");
      const senderElement = document.createElement("strong");

      senderElement.textContent = activeOtherUsername + ": ";
      const textElement = document.createElement("span");
      textElement.textContent = payload.text;

      messageElement.appendChild(senderElement);
      messageElement.appendChild(textElement);
      privateMessages.appendChild(messageElement);

      privateChatStatus.textContent = "Encrypted message received.";
    } catch (error) {
      console.error("Could not decrypt private message:", error);

      privateChatStatus.textContent = "Received a message that could not be decrypted.";
    }
  });

  socket.addEventListener("close", () => {
    console.log("Private message WebSocket disconnected.");
  });

  socket.addEventListener("error", () => {
    console.log("Private message WebSocket error.");
  });

  return socket;
}

const privateSocket = connectPrivateWebSocket();