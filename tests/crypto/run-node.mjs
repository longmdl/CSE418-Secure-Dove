import { readFileSync } from "node:fs";
import { webcrypto } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

if (!globalThis.crypto) globalThis.crypto = webcrypto;
const here = path.dirname(fileURLToPath(import.meta.url));
const { runAll } = await import("./crypto-service.test.js");

let failed = 0;
const line = (ok, name, extra = "") => console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra}`);

const source = readFileSync(path.join(here, "../../public/js/crypto-service.js"), "utf8");
const code = source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|\s)\/\/.*$/gm, "$1");
const staticChecks = [
  ["no console.* calls in crypto-service.js", !/\bconsole\s*\./.test(code)],
  ["no localStorage / sessionStorage / indexedDB use", !/\b(localStorage|sessionStorage|indexedDB)\b/.test(code)],
  ["no exportKey on the derived AES key path (only the peer PUBLIC key is exported)", (code.match(/exportKey/g) || []).length === 1],
];
for (const [name, ok] of staticChecks) {
  line(ok, name);
  if (!ok) failed++;
}

const results = await runAll((r) => line(r.ok, r.name, r.ok ? `  (${r.ms} ms)` : `\n      -> ${r.error}`));
failed += results.filter((r) => !r.ok).length;
console.log(`\n${results.length + staticChecks.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);



// notes:
// Node runner for the crypto tests. Loads crypto-service.test.js and calls runAll().
// Static checks read crypto-service.js with comments removed and confirm it has no
//   console calls, no localStorage/sessionStorage/indexedDB use, and only one
//   exportKey call (the peer's public key, never the derived AES key).
// Prints PASS or FAIL per check, a summary line, and exits with code 1 on any failure.
// Needs Node 18+. The WebCrypto polyfill line covers older versions.