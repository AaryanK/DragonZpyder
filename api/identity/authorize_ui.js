"use strict";
// No third-party scripts, storage, local account IDs or unsafe DOM HTML.
const statusEl = document.getElementById("status");
const loginForm = document.getElementById("login-form");
const query = new URLSearchParams(location.search);
const fields = [
  "response_type", "client_id", "redirect_uri", "scope", "state",
  "code_challenge_method", "code_challenge", "nonce"
];
const payload = Object.fromEntries(
  fields.filter(k => query.has(k)).map(k => [k, query.get(k)])
);
function csrfCookie() {
  const found = document.cookie.split("; ").find(c => c.startsWith("__Host-dz_csrf="));
  return found ? decodeURIComponent(found.slice("__Host-dz_csrf=".length)) : "";
}
loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusEl.textContent = "Signing in…";
  const form = new FormData(event.target);
  try {
    const response = await fetch("/identity/v1/password/login", {
      method: "POST", credentials: "same-origin",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({email:form.get("email"), password:form.get("password")}),
      redirect: "error", cache: "no-store"
    });
    if (!response.ok) throw new Error("Sign-in could not be verified");
    location.reload();
  } catch {
    statusEl.textContent = "Sign-in failed. Check your credentials.";
  }
});
// Never enable password fields until the submit handler is installed.
document.getElementById("login-fields").disabled = false;
document.getElementById("approve").addEventListener("click", async () => {
  statusEl.textContent = "Confirming authorization…";
  try {
    const response = await fetch("/identity/v1/authorize", {
      method: "POST", credentials: "same-origin", cache: "no-store",
      headers: {"Content-Type":"application/json", "Accept":"application/json",
                "x-dz-csrf":csrfCookie()},
      body: JSON.stringify(payload), redirect: "error"
    });
    if (!response.ok) throw new Error("Authorization denied");
    const result = await response.json();
    if (!result || typeof result.redirect_url !== "string") throw new Error("Invalid response");
    location.assign(result.redirect_url);
  } catch {
    statusEl.textContent = "Authorization could not be completed.";
  }
});
document.getElementById("deny").addEventListener("click", () => {
  statusEl.textContent = "Cancelled. You may close this page.";
  document.getElementById("approve").disabled = true;
});
