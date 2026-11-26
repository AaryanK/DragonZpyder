"use strict";
// This page has no relying-party request parameters, consent ticket, or redirect.
const statusEl = document.getElementById("status");
const host = document.getElementById("google-signin");
let busy = false;
async function post(path, body) {
  const response = await fetch(path, {
    method: "POST", credentials: "same-origin", redirect: "error", cache: "no-store",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {})
  });
  if (!response.ok) throw Error("Google sign-in unavailable");
  return response.json();
}
(async () => {
  if (!window.google?.accounts?.id) throw Error("Google sign-in unavailable");
  const challenge = await post("/identity/v1/provider/google/start");
  if (!challenge.client_id || !challenge.nonce || !challenge.state) throw Error("Invalid challenge");
  window.google.accounts.id.initialize({
    client_id: challenge.client_id, nonce: challenge.nonce, auto_select: false,
    callback: async (result) => {
      if (busy || !result?.credential) return;
      busy = true;
      try {
        const login = await post("/identity/v1/provider/google/complete", {
          state: challenge.state, credential: result.credential
        });
        if (login.authenticated !== true) throw Error("Sign-in not confirmed");
        host.replaceChildren();
        statusEl.textContent = "Signed in. Return to your authorization tab and refresh it to continue.";
      } catch {
        host.replaceChildren();
        statusEl.textContent = "Sign-in could not be verified. Reload this page to retry.";
      }
    }
  });
  window.google.accounts.id.renderButton(host, {theme:"outline",size:"large",text:"signin_with"});
})().catch(() => {
  statusEl.textContent = "Google sign-in is unavailable. Reload or use your existing password.";
});
