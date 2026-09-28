// Unit tests for public/js/crypto-service.js (SD-04).
// Exports runAll(); run-node.mjs and browser-test.html both call it.
import {
  deriveConversationKey,
  seal,
  open,
  clearKeyCache,
  CryptoServiceError,
} from "../../public/js/crypto-service.js";

const enc = new TextEncoder();

async function newPair() {
  // Non-extractable private key, same as what SD-03 stores in IndexedDB.
  return crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, ["deriveBits"]);
}

async function deriveFor(me, them, myUserId, theirUserId) {
  return deriveConversationKey({
    myPrivateKey: me.privateKey,
    theirPublicKey: them.publicKey,
    myUserId,
    theirUserId,
  });
}

function makePayload(overrides = {}) {
  return { text: "hello", seq: 1, sentAt: 1700000000000, senderId: "alice", ...overrides };
}

function b64ToBytes(b64) {
  const bin = atob(b64);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}
function bytesToB64(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}
function flipBit(b64, byteIndex, bit = 0) {
  const bytes = b64ToBytes(b64);
  bytes[byteIndex] ^= 1 << bit;
  return bytesToB64(bytes);
}

function assert(cond, msg) {
  if (!cond) throw new Error("Assertion failed: " + msg);
}

async function assertRejects(fn, msg) {
  let threw = false;
  let err;
  try {
    await fn();
  } catch (e) {
    threw = true;
    err = e;
  }
  assert(threw, msg + " (expected an error, but nothing was thrown)");
  assert(err instanceof CryptoServiceError, msg + " (expected CryptoServiceError, got " + err?.name + ")");
  return err;
}

const tests = [];
const test = (name, fn) => tests.push({ name, fn });

test("A and B derive the same key: each opens what the other sealed", async () => {
  clearKeyCache();
  const A = await newPair();
  const B = await newPair();
  const keyA = await deriveFor(A, B, "alice", "bob");
  const keyB = await deriveFor(B, A, "bob", "alice");

  const fromA = await seal(keyA, "conv-1", makePayload({ text: "hi bob", senderId: "alice" }));
  const openedByB = await open(keyB, "conv-1", fromA);
  assert(openedByB.text === "hi bob", "B should read A's message");

  const fromB = await seal(keyB, "conv-1", makePayload({ text: "hi alice", senderId: "bob" }));
  const openedByA = await open(keyA, "conv-1", fromB);
  assert(openedByA.text === "hi alice", "A should read B's message");
});

test("Payload {text, seq, sentAt, senderId} survives the round trip", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const payload = makePayload({ text: "check fields", seq: 42, sentAt: 1712345678901, senderId: "alice" });
  const out = await open(key, "conv-1", await seal(key, "conv-1", payload));
  assert(out.text === payload.text, "text");
  assert(out.seq === 42, "seq");
  assert(out.sentAt === 1712345678901, "sentAt");
  assert(out.senderId === "alice", "senderId");
  assert(Object.keys(out).length === 4, "only the four payload fields come back");
});

test("Derived key is AES-GCM 256-bit and non-extractable", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  assert(key.algorithm.name === "AES-GCM", "algorithm is AES-GCM");
  assert(key.algorithm.length === 256, "key length is 256 bits");
  assert(key.extractable === false, "key is non-extractable");
  assert(
    key.usages.length === 2 && key.usages.includes("encrypt") && key.usages.includes("decrypt"),
    "usages are encrypt + decrypt only"
  );
  let exported = true;
  try {
    await crypto.subtle.exportKey("raw", key);
  } catch {
    exported = false;
  }
  assert(!exported, "exportKey must fail on the derived key");
});

test("Derived keys are cached in memory; clearKeyCache() empties the cache", async () => {
  clearKeyCache();
  const A = await newPair();
  const B = await newPair();
  const k1 = await deriveFor(A, B, "alice", "bob");
  const k2 = await deriveFor(A, B, "alice", "bob");
  assert(k1 === k2, "second derive should return the cached key object");
  clearKeyCache();
  const k3 = await deriveFor(A, B, "alice", "bob");
  assert(k3 !== k1, "after clearKeyCache a new key object is derived");
});

test("A changed peer public key never reuses the stale cached key", async () => {
  clearKeyCache();
  const A = await newPair();
  const bobOld = await newPair();
  const bobNew = await newPair(); // Bob "rotated" his key but keeps the same user id
  const keyOld = await deriveFor(A, bobOld, "alice", "bob");
  const keyNew = await deriveFor(A, bobNew, "alice", "bob");
  assert(keyOld !== keyNew, "different peer key must give a different derived key");
  const sealedWithOld = await seal(keyOld, "conv-1", makePayload());
  await assertRejects(() => open(keyNew, "conv-1", sealedWithOld), "new key must not open old ciphertext");
});

test("IV is 12 bytes and the same message sealed twice gives different output", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const s1 = await seal(key, "conv-1", makePayload());
  const s2 = await seal(key, "conv-1", makePayload());
  assert(b64ToBytes(s1.iv).length === 12, "IV must be 12 bytes");
  assert(s1.iv !== s2.iv, "IVs differ");
  assert(s1.ciphertext !== s2.ciphertext, "ciphertexts differ");
});

test("10,000 seals under one key produce 0 duplicate IVs", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const seen = new Set();
  let duplicates = 0;
  for (let i = 0; i < 10000; i++) {
    const { iv } = await seal(key, "conv-1", makePayload({ seq: i }));
    if (seen.has(iv)) duplicates++;
    seen.add(iv);
  }
  assert(duplicates === 0, "found " + duplicates + " duplicate IVs");
});

test("Output format: base64 ciphertext = plaintext bytes + 16-byte GCM tag", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const payload = makePayload({ text: "length check" });
  const sealed = await seal(key, "conv-1", payload);
  const plainLen = enc.encode(
    JSON.stringify({ text: payload.text, seq: payload.seq, sentAt: payload.sentAt, senderId: payload.senderId })
  ).length;
  assert(b64ToBytes(sealed.ciphertext).length === plainLen + 16, "ciphertext length should be plaintext + 16");
  assert(typeof sealed.ciphertext === "string" && typeof sealed.iv === "string", "both fields are strings");
});

test("Flipping 1 bit in the ciphertext makes open throw", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const sealed = await seal(key, "conv-1", makePayload({ text: "do not tamper" }));
  const len = b64ToBytes(sealed.ciphertext).length;
  for (const idx of [0, Math.floor((len - 16) / 2), len - 17]) {
    const bad = { ...sealed, ciphertext: flipBit(sealed.ciphertext, idx, 3) };
    await assertRejects(() => open(key, "conv-1", bad), "ciphertext byte " + idx);
  }
});

test("Flipping 1 bit in the tag (last 16 bytes) makes open throw", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const sealed = await seal(key, "conv-1", makePayload());
  const len = b64ToBytes(sealed.ciphertext).length;
  for (const idx of [len - 16, len - 8, len - 1]) {
    const bad = { ...sealed, ciphertext: flipBit(sealed.ciphertext, idx, 0) };
    await assertRejects(() => open(key, "conv-1", bad), "tag byte " + idx);
  }
});

test("Flipping 1 bit in the IV makes open throw", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const sealed = await seal(key, "conv-1", makePayload());
  for (const idx of [0, 5, 11]) {
    const bad = { ...sealed, iv: flipBit(sealed.iv, idx, 7) };
    await assertRejects(() => open(key, "conv-1", bad), "iv byte " + idx);
  }
});

test("A third user's key cannot open the message", async () => {
  const A = await newPair();
  const B = await newPair();
  const C = await newPair();
  const keyAB = await deriveFor(A, B, "alice", "bob");
  const keyCB = await deriveFor(C, B, "carol", "bob");
  const keyAC = await deriveFor(A, C, "alice", "carol");
  const sealed = await seal(keyAB, "conv-1", makePayload());
  await assertRejects(() => open(keyCB, "conv-1", sealed), "carol<->bob key");
  await assertRejects(() => open(keyAC, "conv-1", sealed), "alice<->carol key");
});

test("Ciphertext copied into another conversation fails to open (additionalData)", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const sealed = await seal(key, "conv-1", makePayload());
  await assertRejects(() => open(key, "conv-2", sealed), "wrong conversation id");
  const ok = await open(key, "conv-1", sealed);
  assert(ok.text === "hello", "still opens in the right conversation");
});

test("Malformed input to open throws the same generic error, with no plaintext in it", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const secret = "super secret text";
  const sealed = await seal(key, "conv-1", makePayload({ text: secret }));
  const cases = [
    ["null input", null],
    ["missing iv", { ciphertext: sealed.ciphertext }],
    ["bad base64", { ciphertext: "!!!not base64!!!", iv: sealed.iv }],
    ["short iv", { ciphertext: sealed.ciphertext, iv: bytesToB64(new Uint8Array(8)) }],
    ["truncated ciphertext", { ciphertext: bytesToB64(new Uint8Array(5)), iv: sealed.iv }],
  ];
  let firstMessage = null;
  for (const [label, input] of cases) {
    const err = await assertRejects(() => open(key, "conv-1", input), label);
    assert(!err.message.includes(secret), "error message must not contain plaintext");
    if (firstMessage === null) firstMessage = err.message;
    assert(err.message === firstMessage, "all failures use the same generic message");
  }
});

test("Round trips are byte-identical: emoji, Vietnamese, CJK, and a 4 KB message", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const samples = {
    emoji: "Hello 👋🏽 🔐 🕊️ 🇺🇸 👨‍👩‍👧‍👦",
    vietnamese: "Xin chào! Tiếng Việt có dấu: ắ ằ ẳ ẵ ặ ơ ư đ Đ",
    cjk: "你好，世界。こんにちは世界。안녕하세요 세계",
    fourKB: "abcdefghij".repeat(410).slice(0, 4096),
  };
  assert(samples.fourKB.length === 4096, "4 KB sample is 4096 chars");
  for (const [label, text] of Object.entries(samples)) {
    const out = await open(key, "conv-1", await seal(key, "conv-1", makePayload({ text })));
    assert(out.text === text, label + " must come back identical");
    assert(
      bytesToB64(enc.encode(out.text)) === bytesToB64(enc.encode(text)),
      label + " must be byte-identical (UTF-8)"
    );
  }
});

test("seal rejects invalid payloads", async () => {
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  const bad = [
    ["missing text", { seq: 1, sentAt: 1, senderId: "a" }],
    ["text not a string", makePayload({ text: 123 })],
    ["negative seq", makePayload({ seq: -1 })],
    ["fractional seq", makePayload({ seq: 1.5 })],
    ["sentAt NaN", makePayload({ sentAt: NaN })],
    ["empty senderId", makePayload({ senderId: "" })],
    ["null payload", null],
  ];
  for (const [label, payload] of bad) {
    await assertRejects(() => seal(key, "conv-1", payload), label);
  }
  await assertRejects(() => seal(key, "", makePayload()), "empty conversationId");
});

test("deriveConversationKey rejects wrong key types and bad ids", async () => {
  const A = await newPair();
  const B = await newPair();
  await assertRejects(
    () =>
      deriveConversationKey({
        myPrivateKey: A.publicKey, // wrong: a public key
        theirPublicKey: B.publicKey,
        myUserId: "alice",
        theirUserId: "bob",
      }),
    "public key passed as private key"
  );
  await assertRejects(
    () =>
      deriveConversationKey({
        myPrivateKey: A.privateKey,
        theirPublicKey: B.privateKey, // wrong: a private key
        myUserId: "alice",
        theirUserId: "bob",
      }),
    "private key passed as public key"
  );
  await assertRejects(
    () => deriveConversationKey({ myPrivateKey: A.privateKey, theirPublicKey: B.publicKey, myUserId: "", theirUserId: "bob" }),
    "empty user id"
  );
  const noUsage = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, ["deriveKey"]);
  await assertRejects(
    () =>
      deriveConversationKey({
        myPrivateKey: noUsage.privateKey, // has deriveKey but not deriveBits
        theirPublicKey: B.publicKey,
        myUserId: "alice",
        theirUserId: "bob",
      }),
    "private key without deriveBits usage"
  );
});

test("Browser only: crypto-service never writes to localStorage or sessionStorage", async () => {
  if (typeof localStorage === "undefined" || typeof sessionStorage === "undefined") return; // Node: skipped
  const before = [localStorage.length, sessionStorage.length];
  clearKeyCache();
  const A = await newPair();
  const B = await newPair();
  const key = await deriveFor(A, B, "alice", "bob");
  await open(key, "conv-1", await seal(key, "conv-1", makePayload()));
  assert(localStorage.length === before[0], "localStorage changed");
  assert(sessionStorage.length === before[1], "sessionStorage changed");
});

export async function runAll(onResult = () => {}) {
  const results = [];
  for (const t of tests) {
    const started = Date.now();
    let result;
    try {
      await t.fn();
      result = { name: t.name, ok: true, ms: Date.now() - started };
    } catch (e) {
      result = { name: t.name, ok: false, error: e.message, ms: Date.now() - started };
    }
    results.push(result);
    onResult(result);
  }
  return results;
}



// Notes:
// helpers: newPair makes a non-extractable ECDH keypair like SD-03 will.
//   deriveFor, makePayload, flipBit and the assert helpers keep the tests short.
// Key derivation: both users get the same key, it is AES-GCM 256 and
//   non-extractable, it is cached in memory, and a changed peer key is never
//   served a stale cached key.
// IVs: 12 bytes, and no repeats across 10,000 seals.
// Tampering: flipping 1 bit in the ciphertext, the tag, or the IV makes open throw.
//   A third user's key and a different conversation id also fail to open.
// Round trips: emoji, Vietnamese, CJK and a 4 KB message come back byte-identical.
// Input checks: seal and deriveConversationKey reject bad payloads, wrong key types
//   and empty ids. open always throws the same generic error, with no plaintext in it.
// Browser only: confirms nothing is written to localStorage or sessionStorage.
// runAll() runs every test and is shared by run-node.mjs and browser-test.html.