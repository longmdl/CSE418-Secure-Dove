// SD-03 keystore: one ECDH P-256 device keypair per account, private half
// non-extractable and kept in IndexedDB. Load pages with <script type="module">.

const DB_NAME = "securedove";
const DB_VERSION = 1;
const STORE = "device";
const RECORD_PREFIX = "device:";

export class KeyStoreError extends Error {
  constructor(message) {
    super(message);
    this.name = "KeyStoreError";
  }
}

// Records are keyed by user id, so two accounts on one browser never share a
// keypair. Without this, the second account to enrol would publish the first
// account's public key as its own.
function recordKey(userId) {
  if (typeof userId !== "string" || userId.length === 0) {
    throw new KeyStoreError("A user id is required to reach this device's key.");
  }
  return RECORD_PREFIX + userId;
}

function subtle() {
  const c = globalThis.crypto;
  if (!c || !c.subtle) {
    throw new KeyStoreError(
      "WebCrypto is unavailable, so this device cannot hold an encryption key. " +
        "Use HTTPS or localhost in a current browser."
    );
  }
  return c.subtle;
}

function db() {
  if (!globalThis.indexedDB) {
    throw new KeyStoreError(
      "IndexedDB is unavailable, so this device cannot store an encryption key."
    );
  }
  return new Promise((resolve, reject) => {
    const request = globalThis.indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) {
        request.result.createObjectStore(STORE);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new KeyStoreError("Could not open the key database."));
  });
}

function transact(handle, mode, run) {
  return new Promise((resolve, reject) => {
    const tx = handle.transaction(STORE, mode);
    const request = run(tx.objectStore(STORE));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new KeyStoreError("Key database request failed."));
  });
}

async function readRecord(userId) {
  const key = recordKey(userId);
  const handle = await db();
  try {
    return await transact(handle, "readonly", (s) => s.get(key));
  } finally {
    handle.close();
  }
}

async function writeRecord(userId, record) {
  const key = recordKey(userId);
  const handle = await db();
  try {
    await transact(handle, "readwrite", (s) => s.put(record, key));
  } finally {
    handle.close();
  }
  return record;
}

function isUsableRecord(record, userId) {
  return (
    record &&
    record.userId === userId && // a record filed under someone else is never used
    record.keyPair &&
    record.keyPair.privateKey &&
    record.keyPair.publicKey &&
    record.keyPair.privateKey.type === "private" &&
    record.keyPair.privateKey.algorithm?.name === "ECDH" &&
    record.keyPair.privateKey.algorithm?.namedCurve === "P-256" &&
    record.keyPair.privateKey.usages.includes("deriveBits") &&
    typeof record.deviceId === "string" &&
    record.deviceId.length > 0
  );
}

// Returns { userId, keyPair, deviceId }. Generates once per account, then
// returns the same record. Never silently replaces an existing key.
export async function getOrCreateDeviceKey(userId) {
  const existing = await readRecord(userId);
  if (isUsableRecord(existing, userId)) return existing;
  if (existing) {
    throw new KeyStoreError(
      "The stored device key for this account is unusable. Clear this site's data " +
        "to enrol again; past messages sealed to the old key will not be readable."
    );
  }

  // extractable:false applies to the private key. The public half stays
  // exportable, which is what lets us publish it.
  const keyPair = await subtle().generateKey(
    { name: "ECDH", namedCurve: "P-256" },
    false,
    ["deriveBits"]
  );

  const deviceId = globalThis.crypto.randomUUID();
  // CryptoKey is structured-cloneable, so the private key persists without its
  // bytes ever existing in JS.
  return writeRecord(userId, { userId, keyPair, deviceId, createdAt: Date.now() });
}

export async function getDeviceId(userId) {
  const { deviceId } = await getOrCreateDeviceKey(userId);
  return deviceId;
}

export async function getPrivateKey(userId) {
  const { keyPair } = await getOrCreateDeviceKey(userId);
  return keyPair.privateKey;
}

// The public half only. Throws if a private component ever appears.
export async function exportPublicJwk(userId) {
  const { keyPair } = await getOrCreateDeviceKey(userId);
  const jwk = await subtle().exportKey("jwk", keyPair.publicKey);
  if ("d" in jwk) throw new KeyStoreError("Refusing to export a private key.");
  return { kty: jwk.kty, crv: jwk.crv, x: jwk.x, y: jwk.y };
}

export async function hasDeviceKey(userId) {
  return isUsableRecord(await readRecord(userId), userId);
}

// Forgets one account's key on this device. Not wired to logout on purpose:
// dropping the private key drops the ability to read that account's history.
export async function clearDeviceKey(userId) {
  const key = recordKey(userId);
  const handle = await db();
  try {
    await transact(handle, "readwrite", (s) => s.delete(key));
  } finally {
    handle.close();
  }
  const cryptoService = await import("./crypto-service.js");
  cryptoService.clearKeyCache();
}


// ---- Notes ----
// Every entry point takes a user id and reads or writes only that account's
//   record, so switching accounts in one browser cannot cross keys over.
// getOrCreateDeviceKey: generates an ECDH P-256 pair with extractable:false and
//   usages ["deriveBits"], the exact shape crypto-service.js validates, and
//   stores the CryptoKeyPair itself in IndexedDB. On every later call it returns
//   the stored pair, so a reload never rotates a key behind the user's back.
// exportPublicJwk: the only thing that ever leaves this module, and it strips
//   the record down to kty/crv/x/y so nothing else can ride along.
// clearDeviceKey: explicit "forget this device" only. It also clears
//   crypto-service's derived-key cache.
