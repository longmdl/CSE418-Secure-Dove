// SD-03 key directory client: publishes this device's public key and fetches a
// peer's, handing back a CryptoKey that crypto-service.js will accept.

import { exportPublicJwk, getDeviceId } from "./keystore.js";

export class KeyApiError extends Error {
  constructor(message) {
    super(message);
    this.name = "KeyApiError";
  }
}

// Same four fields, same order, same separators as key_service.canonical_jwk in
// Python. If one side changes, fingerprints stop matching and SD-11 reports a
// key change that never happened.
function canonicalJwk(jwk) {
  return JSON.stringify({ crv: jwk.crv, kty: jwk.kty, x: jwk.x, y: jwk.y });
}

export async function fingerprintOf(jwk) {
  const bytes = new TextEncoder().encode(canonicalJwk(jwk));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// "4b2e9c71..." -> "4B2E 9C71 ..." for out-of-band comparison (SD-11 renders it).
export function formatFingerprint(hex) {
  return (hex.match(/.{1,4}/g) || []).join(" ").toUpperCase();
}

function assertPublicJwk(jwk) {
  if (!jwk || typeof jwk !== "object") throw new KeyApiError("Malformed key from the server.");
  if ("d" in jwk) throw new KeyApiError("Server returned a private key. Refusing it.");
  if (jwk.kty !== "EC" || jwk.crv !== "P-256") {
    throw new KeyApiError("Peer key is not an ECDH P-256 key.");
  }
  if (typeof jwk.x !== "string" || typeof jwk.y !== "string") {
    throw new KeyApiError("Malformed key from the server.");
  }
}

// Publishes this device's public half for one account. Idempotent:
// republishing the same key is a no-op on the server.
export async function publishMyKey(userId) {
  const [publicJwk, deviceId] = await Promise.all([
    exportPublicJwk(userId),
    getDeviceId(userId),
  ]);

  const response = await fetch("/api/keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId, public_jwk: publicJwk }),
  });

  if (!response.ok) {
    throw new KeyApiError("Could not publish this device's key (" + response.status + ").");
  }
  return response.json(); // { fingerprint, outcome }
}

// Returns { userId, deviceId, publicKey: CryptoKey, fingerprint }.
// publicKey is imported extractable with no usages, which is the only shape
// deriveConversationKey accepts for a peer.
export async function fetchPeerKey(userId) {
  if (typeof userId !== "string" || userId.length === 0) {
    throw new KeyApiError("fetchPeerKey needs a user id.");
  }

  const response = await fetch("/api/users/" + encodeURIComponent(userId) + "/key");
  if (response.status === 404) throw new KeyApiError("That user has not enrolled a device yet.");
  if (!response.ok) throw new KeyApiError("Could not fetch that user's key (" + response.status + ").");

  const body = await response.json();
  assertPublicJwk(body.public_jwk);

  const publicKey = await globalThis.crypto.subtle.importKey(
    "jwk",
    body.public_jwk,
    { name: "ECDH", namedCurve: "P-256" },
    true, // must stay extractable: deriveConversationKey exports it to build its cache key
    []    // ECDH public keys take no usages; anything else throws SyntaxError
  );

  // Recompute rather than trust the server's copy.
  const fingerprint = await fingerprintOf(body.public_jwk);

  return { userId: body.user_id, deviceId: body.device_id, publicKey, fingerprint };
}


// ---- Notes ----
// fingerprintOf: SHA-256 over {crv,kty,x,y} serialised with sorted keys and no
//   spaces. Computed from the key we were handed, never read from the response,
//   so a lying server cannot make a substituted key look familiar.
// fetchPeerKey: imports with extractable:true and usages []. Both are forced by
//   crypto-service.js, which exports the peer key to build its cache key and
//   would throw on any usages at all.
// publishMyKey: sends device_id and public_jwk for one account's key. The
//   server files it under the session's user, so the body cannot claim someone
//   else's identity.
