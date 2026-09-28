// SD-04 crypto core Task: ECDH P-256 -> HKDF-SHA256 -> AES-256-GCM.
// Load pages with <script type="module">.

const HKDF_INFO_PREFIX = "securedove-v1|";
const IV_BYTES = 12;
const TAG_BYTES = 16;
const encoder = new TextEncoder();
const keyCache = new Map();

export class CryptoServiceError extends Error {
  constructor(message) {
    super(message);
    this.name = "CryptoServiceError";
  }
}
const DECRYPT_FAILED = "Message could not be decrypted or verified.";

function subtle() {
  const c = globalThis.crypto;
  if (!c || !c.subtle) {
    throw new CryptoServiceError(
      "WebCrypto is unavailable. Use HTTPS or localhost (secure context)."
    );
  }
  return c.subtle;
}

function bytesToBase64(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64ToBytes(b64) {
  if (typeof b64 !== "string") throw new CryptoServiceError(DECRYPT_FAILED);
  let binary;
  try {
    binary = atob(b64);
  } catch {
    throw new CryptoServiceError(DECRYPT_FAILED);
  }
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function requireNonEmptyString(value, name) {
  if (typeof value !== "string" || value.length === 0) {
    throw new CryptoServiceError(`${name} must be a non-empty string.`);
  }
}

function validatePayload(p) {
  if (
    p === null ||
    typeof p !== "object" ||
    typeof p.text !== "string" ||
    !Number.isSafeInteger(p.seq) ||
    p.seq < 0 ||
    typeof p.sentAt !== "number" ||
    !Number.isFinite(p.sentAt) ||
    typeof p.senderId !== "string" ||
    p.senderId.length === 0
  ) {
    return false;
  }
  return true;
}

export async function deriveConversationKey({
  myPrivateKey,
  theirPublicKey,
  myUserId,
  theirUserId,
}) {
  requireNonEmptyString(myUserId, "myUserId");
  requireNonEmptyString(theirUserId, "theirUserId");

  if (
    !myPrivateKey ||
    myPrivateKey.type !== "private" ||
    myPrivateKey.algorithm?.name !== "ECDH" ||
    myPrivateKey.algorithm?.namedCurve !== "P-256" ||
    !myPrivateKey.usages.includes("deriveBits")
  ) {
    throw new CryptoServiceError(
      "myPrivateKey must be an ECDH P-256 private key with the deriveBits usage."
    );
  }
  if (
    !theirPublicKey ||
    theirPublicKey.type !== "public" ||
    theirPublicKey.algorithm?.name !== "ECDH" ||
    theirPublicKey.algorithm?.namedCurve !== "P-256"
  ) {
    throw new CryptoServiceError("theirPublicKey must be an ECDH P-256 public key.");
  }

  const s = subtle();
  const ids = [myUserId, theirUserId].sort(); 
  const peerRaw = new Uint8Array(await s.exportKey("raw", theirPublicKey));
  const cacheKey = ids.join("|") + "#" + bytesToBase64(peerRaw);

  const cached = keyCache.get(cacheKey);
  if (cached) return cached;

  const sharedBits = await s.deriveBits(
    { name: "ECDH", public: theirPublicKey },
    myPrivateKey,
    256
  );

  const hkdfKey = await s.importKey("raw", sharedBits, "HKDF", false, ["deriveKey"]);
  new Uint8Array(sharedBits).fill(0); 

  const aesKey = await s.deriveKey(
    {
      name: "HKDF",
      hash: "SHA-256",
      salt: new Uint8Array(0), 
      info: encoder.encode(HKDF_INFO_PREFIX + ids.join("|")),
    },
    hkdfKey,
    { name: "AES-GCM", length: 256 },
    false, 
    ["encrypt", "decrypt"]
  );

  keyCache.set(cacheKey, aesKey);
  return aesKey;
}

export async function seal(conversationKey, conversationId, payload) {
  requireNonEmptyString(conversationId, "conversationId");
  if (!validatePayload(payload)) {
    throw new CryptoServiceError(
      "payload must be { text: string, seq: integer >= 0, sentAt: number, senderId: string }."
    );
  }

  const plaintext = encoder.encode(
    JSON.stringify({
      text: payload.text,
      seq: payload.seq,
      sentAt: payload.sentAt,
      senderId: payload.senderId,
    })
  );

  const iv = globalThis.crypto.getRandomValues(new Uint8Array(IV_BYTES)); // fresh IV every message

  const sealed = await subtle().encrypt(
    {
      name: "AES-GCM",
      iv,
      additionalData: encoder.encode(conversationId), // ties the ciphertext to this conversation
      tagLength: TAG_BYTES * 8,
    },
    conversationKey,
    plaintext
  );

  return {
    ciphertext: bytesToBase64(new Uint8Array(sealed)),
    iv: bytesToBase64(iv),
  };
}

export async function open(conversationKey, conversationId, sealed) {
  requireNonEmptyString(conversationId, "conversationId");
  if (!sealed || typeof sealed !== "object") throw new CryptoServiceError(DECRYPT_FAILED);

  const iv = base64ToBytes(sealed.iv);
  const ciphertext = base64ToBytes(sealed.ciphertext);
  if (iv.length !== IV_BYTES || ciphertext.length < TAG_BYTES) {
    throw new CryptoServiceError(DECRYPT_FAILED);
  }

  let plaintext;
  try {
    plaintext = await subtle().decrypt(
      {
        name: "AES-GCM",
        iv,
        additionalData: encoder.encode(conversationId),
        tagLength: TAG_BYTES * 8,
      },
      conversationKey,
      ciphertext
    );
  } catch {

    throw new CryptoServiceError(DECRYPT_FAILED);
  }

  let payload;
  try {
    payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(plaintext));
  } catch {
    throw new CryptoServiceError(DECRYPT_FAILED);
  }
  if (!validatePayload(payload)) throw new CryptoServiceError(DECRYPT_FAILED);

  return {
    text: payload.text,
    seq: payload.seq,
    sentAt: payload.sentAt,
    senderId: payload.senderId,
  };
}

export function clearKeyCache() {
  keyCache.clear();
}


// ---- Notes ----
// deriveConversationKey: builds one AES-256-GCM key for a pair of users from
//   your private key and their public key (ECDH, then HKDF-SHA256).
//   The HKDF info string is "securedove-v1|" + both user ids sorted.
//   The key is non-extractable and cached in memory only.
// seal: encrypts { text, seq, sentAt, senderId } with a fresh random 12-byte IV.
//   The conversation id is bound in as additionalData, so a ciphertext copied
//   into another conversation fails to open. Returns { ciphertext, iv } in
//   base64, with the 16-byte GCM tag at the end of the ciphertext.
// open: decrypts and verifies. Any failure throws the same generic error and
//   returns nothing, so there is never partial plaintext.
// clearKeyCache: call on logout or when the device keypair changes.
// Not handled here: replay/reorder checks on seq. That belongs to the read path (SD-09).