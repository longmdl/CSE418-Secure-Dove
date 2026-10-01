

import { fingerprintOf, formatFingerprint } from "../../public/js/key-api.js";

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}
function assert(cond, message) {
  if (!cond) throw new Error(message|| "assertion failed");
}
// just a madeup key to test with, not a real one
const ALICE_JWK = {
  kty: "EC",
  crv: "P-256",
  x: "qTE964_zdo-F7OoedXAM2nTFt0J9EqiN7l4lQ0fgJkk",
  y: "Ab1PAl1IjZj-p0RpKjjptUhCSKUYcGpJJbeyFJtvlfI",
};
test("fingerprint matches the SD-03 / Python vector", async () => {
  const hex = await fingerprintOf(ALICE_JWK);
  assert(
    hex === "8534ca7bfc0ae12e58785ea620e594570b42b495b8cbbaad0415539e252646ee",
    "this should match the same value key_service.py computes for the same key"
  );
});

test("identical on both sides: same JWK computed independently gives the same fingerprint", async () => {
  //
  // we fake that here by making two separate copies of the same key.
  const asSeenByContact = { kty: "EC", crv: "P-256", x: ALICE_JWK.x, y: ALICE_JWK.y };
  const asSeenByOwner = JSON.parse(JSON.stringify(ALICE_JWK));
  const a =await fingerprintOf(asSeenByContact);
  const b= await fingerprintOf(asSeenByOwner);
  assert(a === b, "the same key should always give the same fingerprint");
  assert(formatFingerprint(a) === formatFingerprint(b), "and the formatted version should match too");
});
test("field order in the input object does not change the fingerprint", async () => {
  const reordered = { y: ALICE_JWK.y, kty: ALICE_JWK.kty, x: ALICE_JWK.x, crv: ALICE_JWK.crv };
  const a = await fingerprintOf(ALICE_JWK);
  const b = await fingerprintOf(reordered);
  assert(a === b, "fingerprint should not depend on what order the fields are in");
});

test("a substituted key changes the fingerprint", async () => {
  const attacker = { kty: "EC", crv: "P-256", x: "AAAA", y: "BBBB" };
  const a = await fingerprintOf(ALICE_JWK);
  const b = await fingerprintOf(attacker);
  assert(a !== b, "a different key should never give the same fingerprint as another key");
});

test("formatFingerprint renders 16 groups of 4 uppercase hex characters", async () =>{
  const hex =await fingerprintOf(ALICE_JWK);
  const formatted= formatFingerprint(hex);
  const groups =formatted.split(" ");
  assert(groups.length=== 16, "expected 16 groups, got " + groups.length);
  for (const g of groups) {
    assert(/^[0-9A-F]{4}$/.test(g), "this group looks wrong: " + JSON.stringify(g));
  }
  assert(formatted === formatted.toUpperCase(), "everything should be uppercase");
});

// runs every test wwe did
export async function runAll(report) {
  const results = [];
  for (const t of tests) {
    const started = Date.now();
    let result;
    try {
      await t.fn();
      result = { name: t.name,ok: true, ms: Date.now() - started };
    } catch (e) {
      result = { name: t.name, ok: false, error: e.message, ms: Date.now()- started };
    }
    results.push(result);
    if (report) report(result);
  }
  return results;
}
// waht we d id here
// tests for the fingerprint logic itself. these dont need a browser or a
// real serverso they just check the math part works right.
// (testing the actual IndexedDB key storage and the live server lookup
// happens in browser-test.html instead, since node cant do those parts)