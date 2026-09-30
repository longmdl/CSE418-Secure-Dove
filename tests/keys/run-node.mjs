import { readFileSync } from "node:fs";
import { webcrypto } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

if (!globalThis.crypto) globalThis.crypto = webcrypto;
const here = path.dirname(fileURLToPath(import.meta.url));
const { runAll } = await import("./keystore.test.js");

let failed = 0;
const line = (ok, name, extra = "") => console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra}`);
const strip = (f) =>
  readFileSync(path.join(here, "../../public/js/", f), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|\s)\/\/.*$/gm, "$1");

const keystore = strip("keystore.js");
const keyApi = strip("key-api.js");

const staticChecks = [
  ["keystore generates with extractable:false", /generateKey\([\s\S]*?\},\s*false,/.test(keystore)],
  ["keystore asks for deriveBits", /\["deriveBits"\]/.test(keystore)],
  ["keystore never exports the private key", !/exportKey\([^)]*privateKey/.test(keystore)],
  ["keystore never writes keys to localStorage or sessionStorage", !/\b(localStorage|sessionStorage)\b/.test(keystore)],
  ["keystore clears the derived-key cache when a key is forgotten", /clearKeyCache\(\)/.test(keystore)],
  ["keystore files records under the user id, not a constant", /RECORD_PREFIX \+ userId/.test(keystore)],
  ["keystore refuses a record belonging to another account", /record\.userId === userId/.test(keystore)],
  ["key-api publishes for one named account", /publishMyKey\(userId\)/.test(keyApi)],
  ["key-api imports peer keys extractable with no usages", /importKey\([\s\S]*?true,\s*\[\]\s*\)/.test(keyApi)],
  ["key-api recomputes the fingerprint instead of trusting the server", /fingerprintOf\(body\.public_jwk\)/.test(keyApi)],
  ["key-api refuses a response containing a private component", /"d" in jwk/.test(keyApi)],
];
for (const [name, ok] of staticChecks) {
  line(ok, name);
  if (!ok) failed++;
}

const results = await runAll((r) => line(r.ok, r.name, r.ok ? `  (${r.ms} ms)` : `\n      -> ${r.error}`));
failed += results.filter((r) => !r.ok).length;
console.log(`\n${results.length + staticChecks.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
