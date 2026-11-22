// SD-17: the 2FA QR code must be drawn in the browser, never by a third party.
// run this from the repo root: node tests/qr/run-node.mjs
// needs node 18 or newer, no npm packages
import { readFileSync, readdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "../..");
const require = createRequire(import.meta.url);

let failCount = 0;
let total = 0;
function check(name, fn) {
  total++;
  try {
    const ok = fn();
    console.log((ok ? "PASS  " : "FAIL  ") + name);
    if (!ok) failCount++;
  } catch (e) {
    console.log("FAIL  " + name + "\n      -> " + e.message);
    failCount++;
  }
}

function walk(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = path.join(dir, f);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

const settingsJs = readFileSync(path.join(root, "public/js/settings.js"), "utf8");
const settingsHtml = readFileSync(path.join(root, "public/settings.html"), "utf8");

check("no file in public/ references a third-party QR service", () => {
  const bad = /qrserver\.com|chart\.googleapis\.com|quickchart\.io|goqr\.me/i;
  const hits = walk(path.join(root, "public")).filter(
    (f) => /\.(js|html)$/.test(f) && bad.test(readFileSync(f, "utf8"))
  );
  if (hits.length) throw new Error("found in: " + hits.join(", "));
  return true;
});

check("settings.js never puts an http(s) URL into the QR <img> src", () =>
  !/qrCodeImg\.src\s*=\s*[`'"]https?:/.test(settingsJs)
);

check("settings.html loads the vendored QR library before settings.js", () => {
  const vendor = settingsHtml.indexOf('src="/public/js/vendor/qrcode.js"');
  const settings = settingsHtml.indexOf('src="/public/js/settings.js"');
  return vendor !== -1 && settings !== -1 && vendor < settings;
});

const qrcode = require(path.join(root, "public/js/vendor/qrcode.js"));
const otpauth =
  "otpauth://totp/418site:alice%40418site.com?secret=JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP&issuer=YourApp";

check("vendored library builds a valid QR matrix for an otpauth URL", () => {
  const qr = qrcode(0, "M");
  qr.addData(otpauth);
  qr.make();
  const n = qr.getModuleCount();
  // QR versions are 21 + 4*(v-1) modules wide
  if ((n - 21) % 4 !== 0 || n < 21) throw new Error("bad module count " + n);
  // three finder patterns: top-left, top-right, bottom-left corners are dark
  return qr.isDark(0, 0) && qr.isDark(0, n - 1) && qr.isDark(n - 1, 0);
});

check("vendored library outputs an inline data: URL (no network)", () => {
  const qr = qrcode(0, "M");
  qr.addData(otpauth);
  qr.make();
  return qr.createDataURL(6, 4).startsWith("data:image/gif;base64,");
});

console.log(`\n${total - failCount}/${total} passed`);
process.exit(failCount ? 1 : 0);
