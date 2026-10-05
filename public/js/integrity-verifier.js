import { open } from "./crypto-service.js";

// SD-09 depends on the crypto/read foundations from SD-06 and SD-08.
// This verifier assumes open() performs authenticated AES-GCM decryption and
// that message.sender_id is the authenticated server routing identity.
// If either dependency is not merged, add that dependency before relying on
// the tamper/spoof checks below.

const TIMESTAMP_MISMATCH_MS = 5 * 60 * 1000;

const stats = {
  tamper: 0,
  spoof: 0,
  replay: 0
};

//Highest accepted sequence number for each sender, scoped per conversation.
//The client rebuilds this state from verified history whenever a conversation opens.
const highestSeenByConversation = new Map();

function getHighestSeenMap(conversationId) {
  if (!highestSeenByConversation.has(conversationId)) {
    highestSeenByConversation.set(conversationId, new Map());
  }

  return highestSeenByConversation.get(conversationId);
}

//Clears replay state for one conversation before rebuilding it from history.
export function resetHighestSeen(conversationId) {
  highestSeenByConversation.set(conversationId, new Map());
}

//Returns a copy so callers cannot modify the counters directly.
export function getStats() {
  return {
    tamper: stats.tamper,
    spoof: stats.spoof,
    replay: stats.replay
  };
}

//Useful for automated/demo tests without exposing the counter object itself.
export function resetStats() {
  stats.tamper = 0;
  stats.spoof = 0;
  stats.replay = 0;
}

// had to add this or else i was getting 
// test: test (timestamp mismatch)
function parseServerTimestamp(timestamp) {
  if (typeof timestamp !== "string") {
    return NaN;
  }

  // MongoDB/PyMongo may return a UTC datetime without an explicit timezone.
  // Server message timestamps are UTC, so add Z when no timezone is present.
  const hasTimezone =
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(timestamp);

  const normalizedTimestamp =
    hasTimezone
      ? timestamp
      : timestamp + "Z";

  return Date.parse(normalizedTimestamp);
}


//Authenticates, decrypts, validates routing metadata, and enforces replay order.
//History and live WebSocket messages both call this exact function.
//Parameters:
    //conversationKey: AES-GCM key derived for the conversation.
    //conversationId: ID bound into AES-GCM additional authenticated data.
    //message: Server envelope containing sender_id, seq, ciphertext, iv, and timestamp.
export async function verify({ conversationKey, conversationId, message }) {
  let payload;

  try {
    payload = await open(
      conversationKey,
      conversationId,
      {
        ciphertext: message.ciphertext,
        iv: message.iv
      }
    );
  } catch (error) {
    stats.tamper += 1;

    return {
      accepted: false,
      reason: "tamper",
      displayError: "Integrity check failed"
    };
  }

  //The authenticated sender inside the ciphertext must match the sender identity
  //the server attached from its authenticated routing path.
  if (payload.senderId !== message.sender_id) {
    stats.spoof += 1;

    return {
      accepted: false,
      reason: "spoof",
      displayError: "Integrity check failed"
    };
  }

  //seq is authenticated inside the ciphertext too. A mismatch means the outer
  //server envelope was changed or does not belong to this ciphertext.
  if (payload.seq !== message.seq) {
    stats.tamper += 1;

    return {
      accepted: false,
      reason: "tamper",
      displayError: "Integrity check failed"
    };
  }

  const highestSeen = getHighestSeenMap(conversationId);
  const previousHighest = highestSeen.get(payload.senderId);

  if (
    previousHighest !== undefined &&
    payload.seq <= previousHighest
  ) {
    stats.replay += 1;

    return {
      accepted: false,
      reason: "replay",
      displayError: "Integrity check failed"
    };
  }

  //Only accepted messages advance replay state.
  highestSeen.set(payload.senderId, payload.seq);

  const serverTimestamp = parseServerTimestamp(message.timestamp);
  const timestampMismatch =
    Number.isFinite(serverTimestamp) &&
    Math.abs(payload.sentAt - serverTimestamp) > TIMESTAMP_MISMATCH_MS;

  return {
    accepted: true,
    payload: payload,
    timestampMismatch: timestampMismatch
  };
}
