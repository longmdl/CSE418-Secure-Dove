// run this from the repo root: node tests/verify/run-node.mjs
// needs node 18 or newer
import { readFileSync } from "node:fs";
import { webcrypto } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

if (!globalThis.crypto) globalThis.crypto = webcrypto;

const here = path.dirname(fileURLToPath(import.meta.url));
const { runAll } = await import("./contact-verifier.test.js");
let failCount = 0;
function printResult(ok, name, extra = "") {
  console.log((ok ? "PASS  " : "FAIL  ") + name + extra);
}

// before running the real tests, just scan the file as text and make sure
// it's not doing anything sketchy (no extra hash function, no logging keys)
function removeComments(code) {
  return code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|\s)\/\/.*$/gm, "$1");
}
const filePath = path.join(here, "../../public/js/contact-verifier.js");
const fileText = removeComments(readFileSync(filePath, "utf8"));
const simpleChecks = [
  ["uses fingerprintOf/formatFingerprint from key-api.js (not its own copy)", fileText.includes('from "./key-api.js"') && fileText.includes("fingerprintOf") && fileText.includes("formatFingerprint")],
  ["does not call crypto.subtle.digest directly", !fileText.includes("crypto.subtle.digest")],
  ["no console.log anywhere in the file", !fileText.includes("console.")],
  ["does not touch localStorage or sessionStorage", !fileText.includes("localStorage") && !fileText.includes("sessionStorage")],
];
for (const [name, ok] of simpleChecks) {
  printResult(ok, name);
  if (!ok) failCount++;
}

// now run the real tests from contact-verifier.test.js
const testResults = await runAll((r) => {
  printResult(r.ok, r.name, r.ok ? "  (" + r.ms + " ms)" : "\n      -> " + r.error);
});
failCount += testResults.filter((r) => !r.ok).length;
const total = simpleChecks.length + testResults.length;
console.log("\n" + (total - failCount) + " passed, " + failCount + " failed");
process.exit(failCount ? 1 : 0);