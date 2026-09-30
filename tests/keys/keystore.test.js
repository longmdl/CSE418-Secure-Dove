// SD-03 tests that do not need a browser: key shape, compatibility with the
// SD-04 crypto core, peer-import rules, and the fingerprint vector.
// IndexedDB behaviour is covered by browser-test.html instead.

import { deriveConversationKey, seal, open } from "../../public/js/crypto-service.js";

const tests = [];
const test = (name, fn) => tests.push({ name, fn });
function assert(cond, message) {
  if (!cond) throw new Error(message || "assertion failed");
}
async function throws(fn, message) {
  let threw = false;
  try { await fn(); } catch { threw = true; }
  assert(threw, message);
}

// exactly what keystore.getOrCreateDeviceKey() calls
const newDeviceKey = () =>
  crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, ["deriveBits"]);

const publicJwkOf = async (pair) => {
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  return { kty: jwk.kty, crv: jwk.crv, x: jwk.x, y: jwk.y };
};

// exactly what key-api.fetchPeerKey() calls
const importPeer = (jwk) =>
  crypto.subtle.importKey("jwk", jwk, { name: "ECDH", namedCurve: "P-256" }, true, []);

const canonicalJwk = (jwk) => JSON.stringify({ crv: jwk.crv, kty: jwk.kty, x: jwk.x, y: jwk.y });
async function fingerprintOf(jwk) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalJwk(jwk)));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

test("device private key is non-extractable and cannot be exported", async () => {
  const pair = await newDeviceKey();
  assert(pair.privateKey.extractable === false, "private key must be non-extractable");
  await throws(() => crypto.subtle.exportKey("jwk", pair.privateKey), "exportKey(jwk) must throw");
  await throws(() => crypto.subtle.exportKey("pkcs8", pair.privateKey), "exportKey(pkcs8) must throw");
});

test("device private key has the usages crypto-service requires", async () => {
  const pair = await newDeviceKey();
  assert(pair.privateKey.usages.includes("deriveBits"), "needs deriveBits");
  assert(pair.privateKey.algorithm.name === "ECDH", "needs ECDH");
  assert(pair.privateKey.algorithm.namedCurve === "P-256", "needs P-256");
});

test("public half is exportable and carries no private component", async () => {
  const pair = await newDeviceKey();
  assert(pair.publicKey.extractable === true, "public key must stay exportable");
  const jwk = await publicJwkOf(pair);
  assert(!("d" in jwk), "exported public JWK must not contain d");
  assert(jwk.kty === "EC" && jwk.crv === "P-256", "must be an EC P-256 key");
});

test("two devices derive the same conversation key through the directory", async () => {
  const alice = await newDeviceKey();
  const bob = await newDeviceKey();

  // each side fetches the other's key the way key-api does
  const aliceSeesBob = await importPeer(await publicJwkOf(bob));
  const bobSeesAlice = await importPeer(await publicJwkOf(alice));

  const kA = await deriveConversationKey({
    myPrivateKey: alice.privateKey, theirPublicKey: aliceSeesBob,
    myUserId: "alice", theirUserId: "bob",
  });
  const kB = await deriveConversationKey({
    myPrivateKey: bob.privateKey, theirPublicKey: bobSeesAlice,
    myUserId: "bob", theirUserId: "alice",
  });

  const sealed = await seal(kA, "conv-1", { text: "hi", seq: 0, sentAt: 1, senderId: "alice" });
  const opened = await open(kB, "conv-1", sealed);
  assert(opened.text === "hi", "round trip must return the same text");
});

test("a peer key imported non-extractable breaks derivation", async () => {
  const alice = await newDeviceKey();
  const bob = await newDeviceKey();
  const jwk = await publicJwkOf(bob);
  const nonExtractable = await crypto.subtle.importKey(
    "jwk", jwk, { name: "ECDH", namedCurve: "P-256" }, false, []);
  await throws(
    () => deriveConversationKey({
      myPrivateKey: alice.privateKey, theirPublicKey: nonExtractable,
      myUserId: "alice", theirUserId: "bob",
    }),
    "crypto-service exports the peer key, so a non-extractable import must fail");
});

test("importing a peer key with any usages is rejected by WebCrypto", async () => {
  const jwk = await publicJwkOf(await newDeviceKey());
  for (const usages of [["deriveBits"], ["deriveKey"]]) {
    await throws(
      () => crypto.subtle.importKey("jwk", jwk, { name: "ECDH", namedCurve: "P-256" }, true, usages),
      "ECDH public keys take no usages; " + JSON.stringify(usages) + " must throw");
  }
});

test("a substituted peer key changes the fingerprint", async () => {
  const real = await publicJwkOf(await newDeviceKey());
  const attacker = await publicJwkOf(await newDeviceKey());
  assert((await fingerprintOf(real)) !== (await fingerprintOf(attacker)), "fingerprints must differ");
});

test("fingerprint matches the Python key_service vector", async () => {
  const aliceJwk = {
    kty: "EC", crv: "P-256",
    x: "qTE964_zdo-F7OoedXAM2nTFt0J9EqiN7l4lQ0fgJkk",
    y: "Ab1PAl1IjZj-p0RpKjjptUhCSKUYcGpJJbeyFJtvlfI",
  };
  assert(
    (await fingerprintOf(aliceJwk)) ===
      "8534ca7bfc0ae12e58785ea620e594570b42b495b8cbbaad0415539e252646ee",
    "JS and Python fingerprints must agree byte for byte");
});

export async function runAll(report) {
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
    if (report) report(result);
  }
  return results;
}
