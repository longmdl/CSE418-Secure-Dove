let storedUserSettings;

async function fetchUserSettings() {
  try {
    const response = await fetch("/api/users/@me");

    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }

    if (!response.ok) {
      const errorText = await response.text();
      alertManager.newAlert(errorText, "error", 5000, "Settings Error");
      return;
    }

    const body = await response.json();
    storedUserSettings = body;
    if (body && body.username) {
      document.getElementById('username').value = body.username;
    }
  } catch (error) {
    alertManager.newAlert(
      "Failed to fetch user settings. Please try again.",
      "error",
      5000,
      "Settings Error"
    );
  }
}

// ---- Current 2FA code prompt ----
// Changing the password or regenerating 2FA needs a code from the current
// authenticator when 2FA is on. The server enforces it; this just collects it.

const totpPromptDialog = document.getElementById("totpPromptDialog");
const totpPromptForm = document.getElementById("totpPromptForm");
const totpPromptReason = document.getElementById("totpPromptReason");
const totpPromptInput = document.getElementById("totpPromptInput");
const totpPromptError = document.getElementById("totpPromptError");
const totpPromptCancel = document.getElementById("totpPromptCancel");

// Resolves with the 6-digit code, or null if the user cancels.
function askForCurrentTotp(reason) {
  return new Promise((resolve) => {
    totpPromptReason.textContent = reason;
    totpPromptInput.value = "";
    totpPromptError.classList.add("hidden");
    totpPromptDialog.classList.remove("hidden");
    totpPromptInput.focus();

    function finish(code) {
      totpPromptDialog.classList.add("hidden");
      totpPromptInput.value = "";
      totpPromptForm.removeEventListener("submit", onSubmit);
      totpPromptCancel.removeEventListener("click", onCancel);
      resolve(code);
    }

    function onSubmit(event) {
      event.preventDefault();
      const code = totpPromptInput.value.replace(/\s/g, "");
      if (!/^\d{6}$/.test(code)) {
        totpPromptError.classList.remove("hidden");
        return;
      }
      finish(code);
    }

    function onCancel() {
      finish(null);
    }

    totpPromptForm.addEventListener("submit", onSubmit);
    totpPromptCancel.addEventListener("click", onCancel);
  });
}

// Returns "" when 2FA is off (nothing to check), the code when it's on,
// or null if the user cancelled.
async function getStepUpCode(reason) {
  if (!storedUserSettings || !storedUserSettings.totp_enabled) {
    return "";
  }
  return askForCurrentTotp(reason);
}

async function handleSubmit(event) {
  event.preventDefault();

  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;

  // Only a password change needs the code; a username-only change doesn't.
  let totpCode = "";
  if (password !== "") {
    totpCode = await getStepUpCode(
      "Enter the code from your authenticator app to change your password."
    );
    if (totpCode === null) {
      return;
    }
  }

  const formData = new URLSearchParams();
  formData.append("username", username);
  formData.append("password", password);
  if (totpCode) {
    formData.append("totp", totpCode); // must stay last, the server reads it after the password
  }

  try {
    const response = await fetch("/api/users/settings", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      alertManager.newAlert(errorText, "error", 5000, "Settings Update Error");
      return;
    }

    // Show success message and reload page
    window.location.reload();
  } catch (error) {
    alertManager.newAlert(
      "Failed to update settings. Please try again.",
      "error",
      5000,
      "Settings Error"
    );
  }
}

// Build a QR code image as a data: URL using the vendored library in
// /public/js/vendor/qrcode.js. Type 0 = auto-size, "M" = medium error correction.
function buildQrDataUrl(text) {
  const qr = qrcode(0, "M");
  qr.addData(text);
  qr.make();
  return qr.createDataURL(6, 4);
}

const dialog = document.getElementById("twoFactorDialog");
const enable2faBtn = document.getElementById("enable2fa");
const closeDialogBtn = document.getElementById("closeDialog");
const confirmForm = document.getElementById("twoFactorConfirmForm");
const confirmButton = document.getElementById("confirmNewTotp");
const newTotpInput = document.getElementById("newTotpInput");
const newTotpError = document.getElementById("newTotpError");
const qrCodeImg = document.getElementById("qrCode");
const secretCodeElement = document.getElementById("secretCode");
const form = document.querySelector("form");

// Show dialog
enable2faBtn.addEventListener("click", async () => {
  if (!storedUserSettings || !storedUserSettings.username) {
    alertManager.newAlert(
      "Could not find username in user settings. Is your /api/users/@me endpoint working?",
      "error",
      10000,
      "2FA Enable Failed"
    );
    return;
  }

  const totpCode = await getStepUpCode(
    "Enter the code from your current authenticator app to regenerate 2FA."
  );
  if (totpCode === null) {
    return;
  }

  const body = new URLSearchParams();
  if (totpCode) {
    body.append("totp", totpCode);
  }

  let response;
  try {
    response = await fetch("/api/totp/enable", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
  } catch (error) {
    alertManager.newAlert("Failed to enable 2FA. Please try again.", "error", 10000, "2FA Enable Failed");
    return;
  }

  if (!response.ok) {
    const errorText = await response.text();
    alertManager.newAlert(
      errorText || "Failed to enable 2FA.",
      "error",
      10000,
      "2FA Enable Failed"
    );
    return;
  }

  const totpBody = await response.json();
  if (!totpBody.secret) {
    alertManager.newAlert("No 2FA secret was returned.", "error", 10000, "2FA Enable Failed");
    return;
  }
  const secret = totpBody.secret;
  // Not live yet: the server keeps the old 2FA (or none) until the new code is confirmed below.

  // Generate otpauth URL for QR code
  const otpauthUrl = `otpauth://totp/418site:${encodeURIComponent(`${storedUserSettings.username}@418site.com`)}?secret=${secret}&issuer=YourApp`;

  // Render the QR code locally so the TOTP secret never leaves the browser
  // (SD-17: it used to be sent to a third-party QR image service).
  qrCodeImg.src = buildQrDataUrl(otpauthUrl);

  // Display secret code
  secretCodeElement.textContent = secret;

  // Show dialog
  newTotpInput.value = "";
  newTotpError.classList.add("hidden");
  dialog.classList.remove("hidden");
  newTotpInput.focus();
});

function showNewTotpError(message) {
  newTotpError.textContent = message;
  newTotpError.classList.remove("hidden");
}

// Confirm: the user proves they saved the new secret by entering a code from it.
// Only then does the server switch 2FA over, so an unsaved QR code can't lock them out.
let confirmingNewTotp = false;
confirmForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (confirmingNewTotp) {
    return;
  }

  const code = newTotpInput.value.replace(/\s/g, "");
  if (!/^\d{6}$/.test(code)) {
    showNewTotpError("Enter the 6-digit code from your authenticator app.");
    return;
  }

  confirmingNewTotp = true;
  confirmButton.disabled = true;
  try {
    const response = await fetch("/api/totp/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ totp: code }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      showNewTotpError(
        response.status === 403
          ? "That code doesn't match the new QR code. Make sure you saved the new entry and are reading its code."
          : errorText || "Could not confirm the new 2FA code."
      );
      newTotpInput.value = "";
      newTotpInput.focus();
      return;
    }

    storedUserSettings.totp_enabled = true; // the new secret is live, later sensitive actions on this page need it
    dialog.classList.add("hidden");
    alertManager.newAlert(
      "Your new 2FA is active. Use codes from the new entry from now on.",
      "success",
      5000,
      "2FA Updated"
    );
  } catch (error) {
    showNewTotpError("Failed to confirm 2FA. Please try again.");
  } finally {
    confirmingNewTotp = false;
    confirmButton.disabled = false;
  }
});

// Cancel: nothing was switched on, so the old 2FA (or none) stays in place.
closeDialogBtn.addEventListener("click", () => {
  dialog.classList.add("hidden");
  alertManager.newAlert(
    "2FA was not changed. Your previous setup is still active.",
    "info",
    5000,
    "2FA Unchanged"
  );
});


fetchUserSettings();

// document.getElementById("avatar").addEventListener("change", function (event) {
//   const file = event.target.files[0];
//   if (file) {
//     const reader = new FileReader();
//     reader.onload = function (e) {
//       document.getElementById("avatar-preview").src = e.target.result;
//     };
//     reader.readAsDataURL(file);
//   }
// });
