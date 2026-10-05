import { getPrivateKey } from "./keystore.js";
import { fetchPeerKey } from "./key-api.js";
import { deriveConversationKey, seal } from "./crypto-service.js";
import { verify, resetHighestSeen, getStats } from "./integrity-verifier.js";

//Expose SD-09 integrity counters for SD-13.
export { getStats };

//Cache the recipient's public key per conversation.
//this prevents fetching the same public key before every message.
const peerKeyCache = new Map();

//Gets and caches the other user's public encryption key for a conversation.
//Parameters:
    //conversationId: ID of the conversation the public key will be used for.
    //otherUserId: ID of the other user whose public key is needed.
async function getPeerKeyForConversation(conversationId, otherUserId) {
  if (peerKeyCache.has(conversationId)) {
    return peerKeyCache.get(conversationId);
  }

  const peerKey = await fetchPeerKey(otherUserId);

  peerKeyCache.set(conversationId, peerKey);

  return peerKey;
}

//IndexedDB storage for each sender's message sequence number.
//The value survives page reloads so a sender never intentionally starts over at sequence 1 after refreshing.
const SEQ_DB_NAME = "securedove-sequences";
const SEQ_DB_VERSION = 1;
const SEQ_STORE = "sequences";

//Opens the IndexedDB database used to store message sequence numbers.
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

//Gets and saves the next message sequence number for a user.
//Parameters:
    //userId: ID of the user whose next sequence number is needed.
async function nextSequence(userId) {
  const db = await openSequenceDb();

  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(SEQ_STORE, "readwrite");
      const store = transaction.objectStore(SEQ_STORE);

      //Key used to store this user's sequence number in IndexedDB.
      const key = "seq:" + userId;
      const getRequest = store.get(key);

      getRequest.onerror = () => {
        reject(new Error("Could not read message sequence."));
      };

      getRequest.onsuccess = () => {
        //Start at 0 if no sequence exists yet, then increment before using it.
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

//Encrypts a private message in the user's browser before it is sent to the server.
//Parameters:
    //conversationId: ID of the conversation receiving the message.
    //myUserId: ID of the user sending the message.
    //otherUserId: ID of the other user in the conversation.
    //text: Readable message text that will be encrypted.
export async function sendEncryptedMessage({
  conversationId,
  myUserId,
  otherUserId,
  text
}) {
  //Do not encrypt or send empty/whitespace-only messages.
  if (typeof text !== "string" || text.trim().length === 0) {
    throw new Error("Message cannot be empty.");
  }

  //Block oversized messages before encryption.
  const textBytes = new TextEncoder().encode(text);

  if (textBytes.length > 10 * 1024) {
    throw new Error("Message is too large.");
  }

  //Get this device's private key.
  const myPrivateKey = await getPrivateKey(myUserId);

  //Fetch the recipient's public key once per conversation.
  //If this fails, sending stops here. Plaintext is never sent.
  const peer = await getPeerKeyForConversation(
    conversationId,
    otherUserId
  );

  //Finds the shared AES encryption key.
  const conversationKey = await deriveConversationKey({
    myPrivateKey,
    theirPublicKey: peer.publicKey,
    myUserId,
    theirUserId: otherUserId
  });

  //Allocate the next persistent sequence number.
  const seq = await nextSequence(myUserId);

  //Encrypt the plaintext locally in the browser.
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

//Sends an encrypted message envelope to the server and checks whether it was stored.
//Parameters:
    //conversationId: ID of the conversation receiving the message.
    //envelope: Encrypted message containing ciphertext, IV, and sequence number.
export async function postEncryptedMessage(conversationId, envelope) {
  const response = await fetch(
    "/api/conversations/" + encodeURIComponent(conversationId) + "/messages",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },

      //Only encrypted data is sent to the server.
      body: JSON.stringify({
        ciphertext: envelope.ciphertext,
        iv: envelope.iv,
        seq: envelope.seq
      })
    }
  );

  //A duplicate means this exact sequence number was already stored.
  //This can happen when retrying after the original response was lost.
  if (response.status === 409) {
    return {
      sent: true,
      duplicate: true
    };
  }

  //Any other failed request remains unsent.
  if (!response.ok) {
    return {
      sent: false,
      status: response.status
    };
  }

  const storedMessage = await response.json();

  //Do not mark the message sent unless the server returned
  //the stored message ID and server-generated timestamp.
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

//Displays a failed message as unsent and gives the user a button to retry it.
//Parameters:
    //text: Readable message text displayed to the user.
    //conversationId: ID of the conversation the message belongs to.
    //envelope: Original encrypted message that will be reused if Retry is clicked.
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
      //Reuse the exact same ciphertext, IV, and sequence number.
      const result = await postEncryptedMessage(
        conversationId,
        envelope
      );

      if (result.sent) {
        await handleStoredOutgoingMessage(
          conversationId,
          envelope,
          result
        );
        messageElement.remove();
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

//Information about the private conversation currently open in the user's browser.
let activeConversationId = null;
let activeOtherUserId = null;
let activeOtherUsername = null;
let activeMyUser = null;
let activeConversationKey = null;

//Messages in the currently open conversation that passed verify().
//The key is authenticated server sender_id + seq, which is unique in this repo.
const verifiedMessages = new Map();
let integrityFailureNotices = [];

let conversationLoadPromise = null;
let reconnectCatchUpPromise = null;
let privateSocket = null;
let socketHasDisconnected = false;
let reconnectTimer = null;

const privateUserInput = document.getElementById("private-user-id");
const openPrivateChatButton = document.getElementById("open-private-chat");
const privateChatStatus = document.getElementById("private-chat-status");
const privateMessageForm = document.getElementById("private-message-form");
const privateMessageInput = document.getElementById("private-message");
const privateMessages = document.getElementById("private-messages");

//Gets the currently authenticated user's ID and username from the server.
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

//Gets the other participant's username for a conversation.
//Parameters:
    //conversationId: ID of the conversation whose other participant is needed.
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

//Derives the one conversation key used by both history and live verification.
async function getConversationKey(conversationId, myUserId, otherUserId) {
  const myPrivateKey = await getPrivateKey(myUserId);
  const peer = await getPeerKeyForConversation(
    conversationId,
    otherUserId
  );

  return deriveConversationKey({
    myPrivateKey,
    theirPublicKey: peer.publicKey,
    myUserId,
    theirUserId: otherUserId
  });
}

function getMessageKey(message) {
  return String(message.sender_id) + ":" + String(message.seq);
}

function compareServerTimestamp(first, second) {
  const firstTimestamp = Date.parse(first.timestamp);
  const secondTimestamp = Date.parse(second.timestamp);

  if (firstTimestamp !== secondTimestamp) {
    return firstTimestamp - secondTimestamp;
  }

  if (first.sender_id === second.sender_id) {
    return first.seq - second.seq;
  }

  return String(first.sender_id).localeCompare(String(second.sender_id));
}

//Fetches one server history page. History fetch is the offline-delivery mechanism;
//there is intentionally no separate client or server queue for SD-09.
async function fetchHistoryPage(conversationId, before = null) {
  let url =
    "/api/conversations/" +
    encodeURIComponent(conversationId) +
    "/messages?limit=50";

  if (before !== null) {
    url += "&before=" + encodeURIComponent(before);
  }

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error("Could not load message history.");
  }

  const data = await response.json();

  if (!data || !Array.isArray(data.messages)) {
    throw new Error("Could not load message history.");
  }

  return data.messages;
}

//Fetches every page when a conversation is opened so messages sent while the
//recipient was offline are recovered from stored history in server order.
async function fetchAllHistory(conversationId) {
  let before = null;
  let history = [];

  while (true) {
    const page = await fetchHistoryPage(conversationId, before);

    if (page.length === 0) {
      break;
    }

    history = page.concat(history);

    if (page.length < 50) {
      break;
    }

    const oldestTimestamp = page[0].timestamp;

    if (
      typeof oldestTimestamp !== "string" ||
      oldestTimestamp === before
    ) {
      break;
    }

    before = oldestTimestamp;
  }

  return history;
}

//The existing history API only has a "before" cursor, not an "after/since"
//cursor. After reconnect, walk newest pages backward until an already-rendered
//message is reached. This obtains everything since the last message seen without
//adding a second offline queue or a weaker read path.
async function fetchHistorySinceLastSeen(conversationId) {
  let before = null;
  let unseenMessages = [];

  while (true) {
    const page = await fetchHistoryPage(conversationId, before);

    if (page.length === 0) {
      break;
    }

    let reachedKnownMessage = false;

    for (const message of page) {
      if (verifiedMessages.has(getMessageKey(message))) {
        reachedKnownMessage = true;
      } else {
        unseenMessages.push(message);
      }
    }

    if (reachedKnownMessage || page.length < 50) {
      break;
    }

    const oldestTimestamp = page[0].timestamp;

    if (
      typeof oldestTimestamp !== "string" ||
      oldestTimestamp === before
    ) {
      break;
    }

    before = oldestTimestamp;
  }

  unseenMessages.sort(compareServerTimestamp);
  return unseenMessages;
}

//Renders only plaintext that has already passed verify(). textContent is used
//for every decrypted body so message text is never interpreted as HTML.
function renderConversationMessages() {
  privateMessages
    .querySelectorAll('[data-sd09-rendered="true"]')
    .forEach((element) => element.remove());

  const sortedMessages = Array.from(verifiedMessages.values()).sort(
    (first, second) => {
      if (first.payload.sentAt !== second.payload.sentAt) {
        return first.payload.sentAt - second.payload.sentAt;
      }

      if (first.payload.seq !== second.payload.seq) {
        return first.payload.seq - second.payload.seq;
      }

      return first.message.sender_id.localeCompare(second.message.sender_id);
    }
  );

  const firstUnsentMessage = privateMessages.firstChild;

  for (const verified of sortedMessages) {
    const messageElement = document.createElement("div");
    messageElement.dataset.sd09Rendered = "true";

    const senderElement = document.createElement("strong");
    senderElement.textContent = verified.senderName + ": ";

    const textElement = document.createElement("span");
    textElement.textContent = verified.payload.text;

    messageElement.appendChild(senderElement);
    messageElement.appendChild(textElement);

    if (verified.timestampMismatch) {
      const warningElement = document.createElement("span");
      warningElement.textContent = " (timestamp mismatch)";
      messageElement.appendChild(warningElement);
    }

    privateMessages.insertBefore(messageElement, firstUnsentMessage);
  }

  for (const notice of integrityFailureNotices) {
    const noticeElement = document.createElement("div");
    noticeElement.dataset.sd09Rendered = "true";
    noticeElement.textContent = notice;
    privateMessages.insertBefore(noticeElement, firstUnsentMessage);
  }
}

//All history, reconnect, outgoing-confirmation, and live messages use this one
//verification/storage helper, which itself calls SD-09 verify().
async function verifyAndStoreMessage({
  conversationId,
  conversationKey,
  message,
  myUser,
  otherUsername,
  render = true
}) {
  const result = await verify({
    conversationKey,
    conversationId,
    message
  });

  if (!result.accepted) {
    //A replay is dropped and counted but does not create a fake chat row.
    //Tamper/tag/spoof failures are flagged without ever exposing a body.
    if (result.reason !== "replay") {
      integrityFailureNotices.push(result.displayError);
    }

    if (render) {
      renderConversationMessages();
    }

    return result;
  }

  const senderName =
    message.sender_id === myUser.id
      ? myUser.username
      : otherUsername;

  verifiedMessages.set(
    getMessageKey(message),
    {
      message: message,
      payload: result.payload,
      timestampMismatch: result.timestampMismatch,
      senderName: senderName
    }
  );

  if (render) {
    renderConversationMessages();
  }

  return result;
}

//Loads and verifies full paged history every time a conversation opens.
//Replay state is never copied from a server field; it is rebuilt by accepting
//history through verify() in server-receipt order.
async function loadMessageHistory(
  conversationId,
  myUser,
  otherUserId,
  otherUsername
) {
  const conversationKey = await getConversationKey(
    conversationId,
    myUser.id,
    otherUserId
  );

  const history = await fetchAllHistory(conversationId);
  history.sort(compareServerTimestamp);

  if (conversationId !== activeConversationId) {
    return;
  }

  activeConversationKey = conversationKey;
  verifiedMessages.clear();
  integrityFailureNotices = [];
  privateMessages.replaceChildren();
  resetHighestSeen(conversationId);

  for (const message of history) {
    await verifyAndStoreMessage({
      conversationId,
      conversationKey,
      message,
      myUser,
      otherUsername,
      render: false
    });
  }

  renderConversationMessages();
}

//After a WebSocket drop, recover messages from normal server history. Known
//history rows are skipped before verify() so transport catch-up does not inflate
//the replay counter; an actual repeated live seq still reaches verify() and counts.
async function catchUpActiveConversation() {
  if (
    !activeConversationId ||
    !activeConversationKey ||
    !activeMyUser ||
    !activeOtherUsername
  ) {
    return;
  }

  const conversationId = activeConversationId;
  const conversationKey = activeConversationKey;
  const myUser = activeMyUser;
  const otherUsername = activeOtherUsername;
  const unseenMessages = await fetchHistorySinceLastSeen(conversationId);

  if (conversationId !== activeConversationId) {
    return;
  }

  for (const message of unseenMessages) {
    await verifyAndStoreMessage({
      conversationId,
      conversationKey,
      message,
      myUser,
      otherUsername,
      render: false
    });
  }

  renderConversationMessages();
}

//A successfully stored outgoing message is not trusted just because this client
//created it. It is passed back through the same verify() path before rendering.
async function handleStoredOutgoingMessage(
  conversationId,
  envelope,
  result
) {
  if (conversationId !== activeConversationId) {
    return;
  }

  //A 409 retry means the server already has the message but this response does
  //not contain its timestamp. Recover the authoritative envelope from history.
  if (result.duplicate) {
    await catchUpActiveConversation();
    return;
  }

  if (!activeConversationKey || !activeMyUser) {
    return;
  }

  await verifyAndStoreMessage({
    conversationId,
    conversationKey: activeConversationKey,
    message: {
      sender_id: activeMyUser.id,
      seq: envelope.seq,
      ciphertext: envelope.ciphertext,
      iv: envelope.iv,
      timestamp: result.timestamp
    },
    myUser: activeMyUser,
    otherUsername: activeOtherUsername
  });
}

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
    activeMyUser = await getMyUser();
    activeConversationKey = null;

    privateChatStatus.textContent = "Loading encrypted messages...";

    conversationLoadPromise = loadMessageHistory(
      activeConversationId,
      activeMyUser,
      activeOtherUserId,
      activeOtherUsername
    );

    try {
      await conversationLoadPromise;
    } finally {
      conversationLoadPromise = null;
    }

    privateChatStatus.textContent = "Encrypted conversation ready.";
  } catch (error) {
    privateChatStatus.textContent = "Could not connect to the server.";
  }
});

privateMessageForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!activeConversationId || !activeOtherUserId) {
    privateChatStatus.textContent = "Open a private conversation first.";
    return;
  }

  const text = privateMessageInput.value;

  //Keep the encrypted envelope available in case sending fails.
  let envelope = null;

  try {
    privateChatStatus.textContent = "Encrypting message...";

    const myUser = activeMyUser || await getMyUser();
    const myUserId = myUser.id;

    //Encrypt the message locally.
    envelope = await sendEncryptedMessage({
      conversationId: activeConversationId,
      myUserId: myUserId,
      otherUserId: activeOtherUserId,
      text: text
    });

    privateChatStatus.textContent = "Sending encrypted message...";

    //Only the encrypted envelope is sent to the server.
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

    await handleStoredOutgoingMessage(
      activeConversationId,
      envelope,
      result
    );

    privateMessageInput.value = "";
    privateChatStatus.textContent = "Message sent.";

  } catch (error) {
    //If encryption succeeded but sending failed, preserve the exact
    //ciphertext, IV, and sequence number so Retry can resend them.
    if (envelope !== null) {
      showUnsentMessage(text, activeConversationId, envelope);
      privateMessageInput.value = "";
      privateChatStatus.textContent = "Message unsent.";
      return;
    }

    //Encryption/key setup failed, so there is no encrypted message to retry.
    privateChatStatus.textContent =
      error.message || "Could not encrypt message.";
  }
});

//Connects to the private-message WebSocket and handles incoming encrypted messages.
function connectPrivateWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";

  const socket = new WebSocket(
    protocol + "//" + window.location.host + "/websocket"
  );

  privateSocket = socket;

  socket.addEventListener("open", async () => {
    if (!socketHasDisconnected) {
      return;
    }

    socketHasDisconnected = false;

    if (!activeConversationId) {
      return;
    }

    try {
      //Finish an in-progress initial history load before reconnect catch-up.
      if (conversationLoadPromise) {
        await conversationLoadPromise;
      }

      reconnectCatchUpPromise = catchUpActiveConversation();
      await reconnectCatchUpPromise;
      privateChatStatus.textContent = "Encrypted conversation reconnected.";
    } catch (error) {
      privateChatStatus.textContent = "Could not recover missed messages.";
    } finally {
      reconnectCatchUpPromise = null;
    }
  });

  socket.addEventListener("message", async (event) => {
    let data;

    try {
      data = JSON.parse(event.data);
    } catch (error) {
      return;
    }

    //Ignore messages that are not private encrypted messages.
    if (data.messageType !== "encrypted_message") {
      return;
    }

    try {
      const myUser = activeMyUser || await getMyUser();

      //Ignore messages that are not addressed to this authenticated user.
      if (data.recipient_id !== myUser.id) {
        return;
      }

      //Messages for unopened conversations are not rendered. Opening that
      //conversation later fetches and verifies the stored history instead.
      if (data.conversation_id !== activeConversationId) {
        privateChatStatus.textContent =
          "New encrypted message received in another conversation.";
        return;
      }

      //Do not let a live message jump ahead of the history rebuild/catch-up and
      //incorrectly advance highest-seen before older stored messages are checked.
      if (conversationLoadPromise) {
        await conversationLoadPromise;
      }

      if (reconnectCatchUpPromise) {
        await reconnectCatchUpPromise;
      }

      if (!activeConversationKey) {
        return;
      }

      const result = await verifyAndStoreMessage({
        conversationId: activeConversationId,
        conversationKey: activeConversationKey,
        message: data,
        myUser: myUser,
        otherUsername: activeOtherUsername
      });

      if (result.accepted) {
        privateChatStatus.textContent = "Encrypted message received.";
      } else if (result.reason === "replay") {
        privateChatStatus.textContent = "Replay message dropped.";
      } else {
        privateChatStatus.textContent = "Integrity check failed";
      }
    } catch (error) {
      console.error("Could not verify private message:", error);
      privateChatStatus.textContent = "Integrity check failed";
    }
  });

  socket.addEventListener("close", () => {
    if (privateSocket !== socket) {
      return;
    }

    socketHasDisconnected = true;

    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
    }

    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectPrivateWebSocket();
    }, 1000);
  });

  return socket;
}

connectPrivateWebSocket();
