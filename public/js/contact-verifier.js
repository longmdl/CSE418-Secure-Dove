

import { exportPublicJwk } from "./keystore.js";
import { fetchPeerKey, fingerprintOf, formatFingerprint, KeyApiError } from "./key-api.js";

export class FingerprintError extends Error {
  constructor(message) {
    super(message);
    this.name = "FingerprintError";
  }
}
// would compute it
export async function myFingerprint(userId) {
  const jwk = await exportPublicJwk(userId);
  return formatFingerprint(await fingerprintOf(jwk));
}

// gets a contact's fingerprint. fetchPeerKey already recomputes the hash
// itself instead of trusting whatever the server says, so this part is
// already safe 
export async function contactFingerprint(userId) {
  try {
    const peer = await fetchPeerKey(userId);
    return {
      userId: peer.userId,
      deviceId: peer.deviceId,
      fingerprint: formatFingerprint(peer.fingerprint),
    };
  } catch (error) {
    if (error instanceof KeyApiError) throw new FingerprintError(error.message);
    throw error;
  }
}

// this  just builds the html to show the fingerprint bleow
// kept separate from the functions above so we can test it with a made-up
// fingerprint string,

function row(labelText, valueText, selectable = true) {
  const wrap = document.createElement("div");
  wrap.className = "fingerprint-row";
  const label = document.createElement("div");
  label.className = "fingerprint-label";
  label.textContent = labelText;
  const value = document.createElement("div");
  value.className = "fingerprint-value";
  value.textContent = valueText;
  value.style.fontFamily = "ui-monospace, Consolas, monospace";
  value.style.userSelect = selectable ? "text" : "none";
  if (selectable) value.tabIndex = 0;
  wrap.appendChild(label);
  wrap.appendChild(value);
  return wrap;
}
function note(text) {
  const p = document.createElement("div");
  p.className = "fingerprint-note";
  p.textContent = text;
  return p;
}

// shows your own fingerprint in the given container
export async function renderMyFingerprint(container, userId) {
  container.textContent= ""; //changed for security 
  try {
    const formatted = await myFingerprint(userId);
    container.appendChild(row("Your fingerprint", formatted));
  } catch (error) {
    container.appendChild(note("Could not compute your fingerprint: " + error.message));
  }
}

// shows a contact's fingerprint,plus a short instruction telling the user
// to double check it with that person
export async function renderContactFingerprint(container, contactUserId) {
  container.textContent = ""; //changed for security 
  try {
    const result = await contactFingerprint(contactUserId);
    container.appendChild(row("Contact's fingerprint", result.fingerprint));
    container.appendChild(
      note("Compare this with your contact, over a call or in person. It should match exactly.")
    );
  } catch (error) {
    container.appendChild(note("Could not verify this contact: " + error.message));
  }
}

// helper for doing both at once, used in chat.html
export async function renderFingerprintPanels({ myContainer, contactContainer, myUserId, contactUserId }) {
  const tasks = [];
  if (myContainer) tasks.push(renderMyFingerprint(myContainer, myUserId));
  if (contactContainer && contactUserId) tasks.push(renderContactFingerprint(contactContainer, contactUserId));
  await Promise.all(tasks);
}

// SD-11 - this file shows a key fingerprint on screen so two people can
// check they both have the same key. it does NOT compute the hash itself -
// key-api.js already has fingerprintOf() and formatFingerprint(), from
// SD-03, so we just use those instead of writing our own version.
// one thing worth knowing: the original SD-11 card said the fingerprint
// should be a hash of the raw exported key bytes. but key-api.js actually
// hashes the key's JWK fields {crv, kty, x, y} as a JSON string instead.
// that's a different method than the card describes, but it's what SD-03
// already built and tested against the python side, so we're going with
// what's already there instead of making a second, different fingerprint.
