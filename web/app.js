const state = {
  session: null,
  conversationId: null,
  conversations: [],
  approvals: [],
  sending: false,
  preauthCsrf: null,
  lastRequestId: null,
};

class ApiError extends Error {
  constructor(message, { status = 0, code = "REQUEST_FAILED", retryable = false, details = {} } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryable = retryable;
    this.details = details || {};
  }
}

const $ = (id) => document.getElementById(id);
const authModal = $("auth-modal");
const loginForm = $("login-form");
const loginEmail = $("login-email");
const loginPassword = $("login-password");
const loginButton = $("login-button");
const loginError = $("login-error");
const conversationList = $("conversation-list");
const emptyState = $("empty-state");
const messages = $("messages");
const chatMain = $("chat-main");
const composer = $("composer");
const messageInput = $("message-input");
const sendButton = $("send-button");
const statusDot = $("status-dot");
const statusText = $("status-text");
const approvalCount = $("approval-count");
const approvalsDrawer = $("approvals-drawer");
const approvalList = $("approval-list");
const profileMenu = $("profile-menu");
const sessionLabel = $("session-label");
const profileInitial = $("profile-initial");
const sidebar = $("sidebar");
const toast = $("toast");

function getCookie(name) {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const value = part.trim();
    if (value.startsWith(prefix)) return decodeURIComponent(value.slice(prefix.length));
  }
  return null;
}

function sessionCsrf() {
  return getCookie("__Host-operly_csrf") || getCookie("operly_csrf") || null;
}

function errorDetail(payload, status) {
  const detail = payload && typeof payload === "object" ? payload.detail : null;
  if (detail && typeof detail === "object") {
    return new ApiError(String(detail.message || detail.code || `Request failed (${status})`), {
      status,
      code: String(detail.code || `HTTP_${status}`),
      retryable: Boolean(detail.retryable),
      details: detail.details && typeof detail.details === "object" ? detail.details : {},
    });
  }
  return new ApiError(
    typeof detail === "string" ? detail : `Request failed (${status})`,
    { status, code: `HTTP_${status}`, retryable: status >= 500 },
  );
}

async function api(path, { method = "GET", body = undefined, csrf = true, csrfToken = null } = {}) {
  const upper = method.toUpperCase();
  const headers = { Accept: "application/json" };
  let requestBody;
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(upper) && csrf) {
    const token = csrfToken || sessionCsrf() || state.preauthCsrf;
    if (!token) throw new ApiError("Secure session token is missing. Sign in again.", { code: "CSRF_TOKEN_MISSING", status: 401 });
    headers["X-CSRF-Token"] = token;
  }

  let response;
  try {
    response = await fetch(path, {
      method: upper,
      headers,
      body: requestBody,
      credentials: "same-origin",
      redirect: "error",
    });
  } catch (error) {
    throw new ApiError(`Could not reach DragonZpyder: ${error.message}`, { code: "NETWORK_ERROR", retryable: true });
  }

  const text = await response.text();
  let payload = {};
  if (text) {
    try { payload = JSON.parse(text); }
    catch { payload = { detail: text }; }
  }
  if (!response.ok) throw errorDetail(payload, response.status);
  return payload;
}

function setRuntimeStatus(mode, text) {
  statusDot.classList.remove("online", "error");
  if (mode) statusDot.classList.add(mode);
  statusText.textContent = text;
}

function showToast(message, timeout = 4200) {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toast.hidden = true; }, timeout);
}

function showAuth(error = "") {
  authModal.hidden = false;
  profileMenu.hidden = true;
  if (error) {
    loginError.textContent = error;
    loginError.hidden = false;
  } else {
    loginError.hidden = true;
  }
  setTimeout(() => loginEmail.focus(), 30);
}

function hideAuth() {
  authModal.hidden = true;
  loginError.hidden = true;
  loginPassword.value = "";
}

function initials(value) {
  const clean = String(value || "D").trim();
  return (clean[0] || "D").toUpperCase();
}

function setSession(session) {
  state.session = session;
  if (!session) {
    sessionLabel.textContent = "Personal session";
    profileInitial.textContent = "D";
    return;
  }
  sessionLabel.textContent = session.device || "Personal session";
  profileInitial.textContent = initials(session.device || "D");
}

async function ensurePersonalSession() {
  const rows = await api("/api/auth/sessions", { csrf: false });
  if (!Array.isArray(rows)) throw new ApiError("Operly returned an invalid session response.", { code: "INVALID_SESSION_RESPONSE" });
  let current = rows.find((row) => row && row.current);
  if (!current) throw new ApiError("No active session.", { code: "SESSION_INVALID", status: 401 });

  if (current.scope !== "personal") {
    await api("/api/auth/personal-scope", { method: "POST", body: {} });
    const refreshed = await api("/api/auth/sessions", { csrf: false });
    current = Array.isArray(refreshed) ? refreshed.find((row) => row && row.current) : null;
  }
  if (!current || current.scope !== "personal") {
    throw new ApiError("DragonZpyder could not establish Personal-only authority.", { code: "PERSONAL_SCOPE_REQUIRED" });
  }
  setSession(current);
  return current;
}

async function bootstrapAuth() {
  setRuntimeStatus(null, "Checking personal runtime…");
  try {
    await ensurePersonalSession();
    hideAuth();
    setRuntimeStatus("online", "Personal runtime connected");
    await Promise.all([loadConversations(), refreshApprovals()]);
  } catch (error) {
    setSession(null);
    if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
      setRuntimeStatus(null, "Sign in required");
      showAuth();
      return;
    }
    setRuntimeStatus("error", "Runtime unavailable");
    showAuth(error.message || "DragonZpyder runtime is unavailable.");
  }
}

async function login(email, password) {
  const bootstrap = await api("/api/auth/bootstrap", { csrf: false });
  state.preauthCsrf = bootstrap && bootstrap.csrf_token ? String(bootstrap.csrf_token) : null;
  if (!state.preauthCsrf) throw new ApiError("Operly did not provide a login security token.", { code: "CSRF_BOOTSTRAP_FAILED" });

  const result = await api("/api/auth/login", {
    method: "POST",
    body: { email, password },
    csrfToken: state.preauthCsrf,
  });
  state.preauthCsrf = null;

  if (!result || result.scope !== "personal") {
    await api("/api/auth/personal-scope", { method: "POST", body: {} });
  }
  await ensurePersonalSession();
  hideAuth();
  setRuntimeStatus("online", "Personal runtime connected");
  await Promise.all([loadConversations(), refreshApprovals()]);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showMessages() {
  emptyState.hidden = true;
  messages.classList.add("active");
}

function showEmptyState() {
  emptyState.hidden = false;
  messages.classList.remove("active");
  messages.replaceChildren();
}

function messageNode(role, content, { pending = false, error = false, meta = "", approvalId = null } = {}) {
  const wrap = document.createElement("article");
  wrap.className = `message ${role === "user" ? "user" : "assistant"}`;
  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "You" : "DZ";
  const body = document.createElement("div");
  body.className = "message-body";
  const label = document.createElement("div");
  label.className = "message-role";
  label.textContent = role === "user" ? "You" : "DragonZpyder";
  const value = document.createElement("div");
  value.className = `message-content${error ? " error" : ""}`;
  if (pending) {
    value.innerHTML = '<span class="thinking"><i></i><i></i><i></i></span>';
  } else {
    value.textContent = content || "";
  }
  body.append(label, value);
  if (meta) {
    const m = document.createElement("div");
    m.className = "message-meta";
    m.textContent = meta;
    body.appendChild(m);
  }
  if (approvalId) {
    const box = document.createElement("div");
    box.className = "approval-inline";
    box.innerHTML = `<b>Approval required</b><p>Review the exact action before DragonZpyder executes it.</p>`;
    const button = document.createElement("button");
    button.className = "approve-btn";
    button.type = "button";
    button.textContent = "Review approval";
    button.addEventListener("click", openApprovals);
    box.appendChild(button);
    body.appendChild(box);
  }
  wrap.append(avatar, body);
  return { wrap, value, body };
}

function appendMessage(role, content, options = {}) {
  showMessages();
  const node = messageNode(role, content, options);
  messages.appendChild(node.wrap);
  scrollToBottom();
  return node;
}

function scrollToBottom() {
  requestAnimationFrame(() => { chatMain.scrollTop = chatMain.scrollHeight; });
}

function clearConversationSelection() {
  state.conversationId = null;
  for (const button of conversationList.querySelectorAll(".conversation-button")) button.classList.remove("active");
  showEmptyState();
  messageInput.focus();
  sidebar.classList.remove("open");
}

function renderConversations() {
  conversationList.replaceChildren();
  if (!state.conversations.length) {
    const empty = document.createElement("div");
    empty.className = "conversation-button";
    empty.textContent = "No conversations yet";
    empty.style.cursor = "default";
    conversationList.appendChild(empty);
    return;
  }
  for (const item of state.conversations) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `conversation-button${item.id === state.conversationId ? " active" : ""}`;
    button.textContent = item.title || "Conversation";
    button.title = item.title || "Conversation";
    button.addEventListener("click", () => openConversation(item.id));
    conversationList.appendChild(button);
  }
}

async function loadConversations() {
  try {
    const rows = await api("/api/personal-agent/conversations", { csrf: false });
    state.conversations = Array.isArray(rows) ? rows : [];
    renderConversations();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return showAuth();
    console.warn("Could not load conversations", error);
  }
}

async function openConversation(id) {
  if (!id || state.sending) return;
  state.conversationId = id;
  renderConversations();
  sidebar.classList.remove("open");
  showMessages();
  messages.replaceChildren();
  const pending = appendMessage("assistant", "", { pending: true });
  try {
    const rows = await api(`/api/personal-agent/conversations/${encodeURIComponent(id)}/messages`, { csrf: false });
    messages.replaceChildren();
    for (const row of Array.isArray(rows) ? rows : []) {
      if (row.role !== "user" && row.role !== "assistant") continue;
      appendMessage(row.role === "user" ? "user" : "assistant", row.content || "");
    }
    renderConversations();
  } catch (error) {
    pending.value.textContent = error.message;
    pending.value.classList.add("error");
  }
}

function runtimeMessage(result) {
  if (!result || typeof result !== "object") return "DragonZpyder completed the request.";
  return String(result.message || result.result?.message || result.output || "DragonZpyder completed the request.");
}

async function submitViaClientAdapter(message, requestId) {
  const body = { message, request_id: requestId };
  if (state.conversationId) body.conversation_id = state.conversationId;
  try {
    return await api("/api/personal-tools/client/submit", { method: "POST", body });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      const fallback = { message };
      if (state.conversationId) fallback.conversation_id = state.conversationId;
      const result = await api("/api/personal-agent/chat", { method: "POST", body: fallback });
      result.client_request_id = requestId;
      result.web_fallback = true;
      return result;
    }
    throw error;
  }
}

async function sendMessage(message) {
  const clean = String(message || "").trim();
  if (!clean || state.sending) return;
  if (!state.session) return showAuth();

  state.sending = true;
  sendButton.disabled = true;
  messageInput.disabled = true;
  appendMessage("user", clean);
  const pending = appendMessage("assistant", "", { pending: true });
  const requestId = crypto.randomUUID();
  state.lastRequestId = requestId;

  try {
    const result = await submitViaClientAdapter(clean, requestId);
    if (result.conversation_id) state.conversationId = String(result.conversation_id);
    const blocker = result.error_code ? String(result.error_code) : "";
    const text = runtimeMessage(result);
    pending.value.textContent = text;
    if (blocker) {
      pending.value.classList.add("error");
      const meta = document.createElement("div");
      meta.className = "message-meta";
      meta.textContent = `Blocked: ${blocker}`;
      pending.body.appendChild(meta);
    }
    if (result.approval_id) {
      const inline = document.createElement("div");
      inline.className = "approval-inline";
      inline.innerHTML = "<b>Approval required</b><p>Review the exact action before allowing execution.</p>";
      const button = document.createElement("button");
      button.className = "approve-btn";
      button.type = "button";
      button.textContent = "Review approval";
      button.addEventListener("click", openApprovals);
      inline.appendChild(button);
      pending.body.appendChild(inline);
    }
    await Promise.all([loadConversations(), refreshApprovals()]);
  } catch (error) {
    pending.value.classList.add("error");
    if (error instanceof ApiError && error.code === "execution_outcome_uncertain") {
      const stable = error.details?.rfc822_message_id ? ` Stable message identity: ${error.details.rfc822_message_id}.` : "";
      pending.value.textContent = `Delivery may already have happened. Do not send again until it is reconciled.${stable}`;
    } else if (error instanceof ApiError && error.status === 401) {
      pending.value.textContent = "Your session expired. Sign in again to continue.";
      setSession(null);
      showAuth();
    } else {
      pending.value.textContent = error.message || "DragonZpyder could not complete the request.";
      const meta = document.createElement("div");
      meta.className = "message-meta";
      meta.textContent = error.retryable ? `Safe retry identity: ${requestId}` : `Request ID: ${requestId}`;
      pending.body.appendChild(meta);
    }
  } finally {
    state.sending = false;
    sendButton.disabled = false;
    messageInput.disabled = false;
    messageInput.value = "";
    autoSizeInput();
    messageInput.focus();
    scrollToBottom();
  }
}

async function refreshApprovals() {
  try {
    const payload = await api("/api/personal-tools/approvals?status=pending", { csrf: false });
    state.approvals = payload && Array.isArray(payload.approvals) ? payload.approvals : [];
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) state.approvals = [];
    else console.warn("Could not load approvals", error);
  }
  approvalCount.textContent = String(state.approvals.length);
  approvalCount.hidden = state.approvals.length === 0;
  renderApprovals();
}

function stringifyArgument(value) {
  if (typeof value === "string") return value;
  try { return JSON.stringify(value, null, 2); }
  catch { return String(value); }
}

function renderApprovals() {
  approvalList.replaceChildren();
  if (!state.approvals.length) {
    const empty = document.createElement("div");
    empty.className = "empty-approvals";
    empty.textContent = "No Personal actions are waiting for approval.";
    approvalList.appendChild(empty);
    return;
  }

  for (const approval of state.approvals) {
    const card = document.createElement("article");
    card.className = "approval-card";
    const top = document.createElement("div");
    top.className = "approval-top";
    top.innerHTML = `<div class="approval-capability">${escapeHtml(approval.capability_id || "Personal action")}</div><div class="approval-state">${escapeHtml(approval.status || "pending")}</div>`;
    card.appendChild(top);

    const args = approval.arguments && typeof approval.arguments === "object" ? approval.arguments : {};
    const argsList = document.createElement("div");
    argsList.className = "argument-list";
    for (const [key, value] of Object.entries(args)) {
      const row = document.createElement("div");
      row.className = "argument-row";
      const name = document.createElement("span");
      name.textContent = key;
      const code = document.createElement("code");
      code.textContent = stringifyArgument(value);
      row.append(name, code);
      argsList.appendChild(row);
    }
    if (!argsList.children.length) {
      const none = document.createElement("div");
      none.className = "message-meta";
      none.textContent = "No arguments were supplied.";
      argsList.appendChild(none);
    }
    card.appendChild(argsList);

    const meta = document.createElement("div");
    meta.className = "approval-meta";
    if (approval.arguments_hash) {
      const hash = document.createElement("span");
      hash.textContent = `Review hash: ${approval.arguments_hash}`;
      meta.appendChild(hash);
    }
    if (approval.expires_at) {
      const expiry = document.createElement("span");
      expiry.textContent = `Expires: ${new Date(approval.expires_at).toLocaleString()}`;
      meta.appendChild(expiry);
    }
    const id = document.createElement("span");
    id.textContent = `Approval: ${approval.id}`;
    meta.appendChild(id);
    card.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "approval-actions";
    const approve = document.createElement("button");
    approve.type = "button";
    approve.className = "approve-btn";
    approve.textContent = "Approve exact action";
    approve.addEventListener("click", () => approveAction(approval, approve));
    const reject = document.createElement("button");
    reject.type = "button";
    reject.className = "reject-btn";
    reject.textContent = "Reject";
    reject.addEventListener("click", () => rejectAction(approval, reject));
    actions.append(approve, reject);
    card.appendChild(actions);
    approvalList.appendChild(card);
  }
}

async function openApprovals() {
  await refreshApprovals();
  approvalsDrawer.hidden = false;
}

function closeApprovals() {
  approvalsDrawer.hidden = true;
}

async function rejectAction(approval, button) {
  button.disabled = true;
  try {
    await api(`/api/personal-tools/approvals/${encodeURIComponent(approval.id)}/decision`, {
      method: "POST",
      body: { approved: false },
    });
    showToast("Action rejected. Nothing was executed.");
    await refreshApprovals();
  } catch (error) {
    showToast(error.message || "Could not reject the action.");
  } finally {
    button.disabled = false;
  }
}

async function approveAction(approval, button) {
  button.disabled = true;
  try {
    const decided = await api(`/api/personal-tools/approvals/${encodeURIComponent(approval.id)}/decision`, {
      method: "POST",
      body: { approved: true },
    });
    const contract = decided && typeof decided === "object" ? decided : approval;
    const capabilityId = String(contract.capability_id || approval.capability_id || "");
    const args = contract.arguments && typeof contract.arguments === "object" ? contract.arguments : approval.arguments || {};
    if (!capabilityId) throw new ApiError("Approved action is missing its capability contract.", { code: "APPROVAL_CONTRACT_INVALID" });

    const execution = await api(`/api/personal-tools/${encodeURIComponent(capabilityId)}/execute`, {
      method: "POST",
      body: {
        goal: "",
        arguments: args,
        request_id: contract.request_id || approval.request_id || crypto.randomUUID(),
        approval_id: contract.id || approval.id,
        ...(contract.conversation_id || approval.conversation_id ? { conversation_id: contract.conversation_id || approval.conversation_id } : {}),
      },
    });
    closeApprovals();
    appendMessage("assistant", "Approved action completed.", {
      meta: execution?.result?.verification_status ? `Verification: ${execution.result.verification_status}` : "Executed through Operly",
    });
    showToast("Approved action executed through Operly.");
    await refreshApprovals();
  } catch (error) {
    if (error instanceof ApiError && error.code === "execution_outcome_uncertain") {
      const stable = error.details?.rfc822_message_id ? ` Message identity: ${error.details.rfc822_message_id}.` : "";
      closeApprovals();
      appendMessage("assistant", `The provider outcome is uncertain.${stable} Do not repeat this action until it is reconciled.`, { error: true });
      showToast("Provider outcome uncertain — do not resend.", 7000);
    } else {
      showToast(error.message || "Could not execute the approved action.", 6000);
    }
    await refreshApprovals();
  } finally {
    button.disabled = false;
  }
}

async function logout() {
  try {
    await api("/api/auth/logout", { method: "POST", body: {} });
  } catch (error) {
    if (!(error instanceof ApiError && [401, 409].includes(error.status))) console.warn("Logout failed", error);
  }
  setSession(null);
  state.conversationId = null;
  state.conversations = [];
  state.approvals = [];
  renderConversations();
  showEmptyState();
  refreshApprovals();
  profileMenu.hidden = true;
  setRuntimeStatus(null, "Sign in required");
  showAuth();
}

function autoSizeInput() {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 170)}px`;
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = loginEmail.value.trim();
  const password = loginPassword.value;
  if (!email || !password) return;
  loginButton.disabled = true;
  loginButton.textContent = "Signing in…";
  loginError.hidden = true;
  try {
    await login(email, password);
  } catch (error) {
    loginError.textContent = error.message || "Sign-in failed.";
    loginError.hidden = false;
    setRuntimeStatus("error", "Sign-in failed");
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = "Sign in";
  }
});

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(messageInput.value);
});
messageInput.addEventListener("input", autoSizeInput);
messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

for (const chip of document.querySelectorAll(".prompt-chip")) {
  chip.addEventListener("click", () => sendMessage(chip.textContent));
}

$("new-chat").addEventListener("click", clearConversationSelection);
$("approvals-button").addEventListener("click", openApprovals);
$("approvals-top").addEventListener("click", openApprovals);
$("close-approvals").addEventListener("click", closeApprovals);
approvalsDrawer.addEventListener("click", (event) => { if (event.target === approvalsDrawer) closeApprovals(); });
$("profile-button").addEventListener("click", () => { profileMenu.hidden = !profileMenu.hidden; });
$("logout-button").addEventListener("click", logout);
$("open-sidebar").addEventListener("click", () => sidebar.classList.add("open"));
$("close-sidebar").addEventListener("click", () => sidebar.classList.remove("open"));

document.addEventListener("click", (event) => {
  if (!profileMenu.hidden && !profileMenu.contains(event.target) && !$("profile-button").contains(event.target)) profileMenu.hidden = true;
});

window.addEventListener("online", () => setRuntimeStatus(state.session ? "online" : null, state.session ? "Personal runtime connected" : "Sign in required"));
window.addEventListener("offline", () => setRuntimeStatus("error", "Offline"));

autoSizeInput();
bootstrapAuth();
