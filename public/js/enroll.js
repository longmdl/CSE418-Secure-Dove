// SD-03 enrolment: make sure the signed-in account has a device key on this
// browser and that the server has its public half. Safe to call on every load.

import { getOrCreateDeviceKey, KeyStoreError } from "./keystore.js";
import { publishMyKey, KeyApiError } from "./key-api.js";

export class NotSignedInError extends Error {
  constructor() {
    super("You are not signed in, so there is no account to enrol a key for.");
    this.name = "NotSignedInError";
  }
}

// Keys are filed per account, so enrolment starts by finding out who is signed in.
export async function currentUserId() {
  const response = await fetch("/api/users/@me");
  if (!response.ok) throw new NotSignedInError();
  const me = await response.json();
  if (!me || typeof me.id !== "string" || me.id.length === 0) throw new NotSignedInError();
  return me.id;
}

export async function ensureEnrolled(userId) {
  const id = userId || (await currentUserId());
  await getOrCreateDeviceKey(id);
  return publishMyKey(id);
}

// Same thing, but reports failure to the user instead of throwing. Encryption is
// not optional, so a failure here has to be visible rather than let the page
// quietly carry on without a key.
export async function ensureEnrolledOrExplain(onFailure) {
  try {
    return await ensureEnrolled();
  } catch (error) {
    const known =
      error instanceof KeyStoreError ||
      error instanceof KeyApiError ||
      error instanceof NotSignedInError;
    const message = known ? error.message : "Could not set up encryption on this device.";
    if (typeof onFailure === "function") onFailure(message);
    else if (globalThis.alertManager) {
      globalThis.alertManager.newAlert(message, "error", 0, "Encryption unavailable");
    }
    return null;
  }
}
