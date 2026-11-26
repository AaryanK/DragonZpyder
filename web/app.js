import { renderMarkdown } from "./frontend/src/markdown.js";
const state = {
  session: null,
  firstParty: false,
  selectedMcpConnections: [],
  conversationId: null,
  archiveSelected: false,
  selectionVersion: 0,
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
const composerWrap = document.querySelector(".composer-wrap");
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

const workspaceThemeToggle = $("workspace-theme-toggle");
function applyWorkspaceTheme(theme, { persist = true } = {}) {
  const mode = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.workspaceTheme = mode;
  workspaceThemeToggle.setAttribute("aria-label", mode === "light" ? "Switch to dark appearance" : "Switch to light appearance");
  workspaceThemeToggle.setAttribute("aria-pressed", String(mode === "dark"));
  workspaceThemeToggle.title = mode === "light" ? "Dark mode" : "Light mode";
  // Vector glyphs follow the root theme attribute.
  if (persist) {
    try { localStorage.setItem("dragonzpyder:workspace-theme", mode); } catch {}
  }
}
try {
  applyWorkspaceTheme(localStorage.getItem("dragonzpyder:workspace-theme") || "light", { persist: false });
} catch { applyWorkspaceTheme("light", { persist: false }); }
workspaceThemeToggle.addEventListener("click", () => {
  applyWorkspaceTheme(document.documentElement.dataset.workspaceTheme === "light" ? "dark" : "light");
});


function getCookie(name) {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const value = part.trim();
    if (value.startsWith(prefix)) return decodeURIComponent(value.slice(prefix.length));
  }
  return null;
}

function sessionCsrf() {
  return state.firstParty
    ? getCookie("__Host-dz_csrf")
    : (getCookie("__Host-operly_csrf") || getCookie("operly_csrf") || null);
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
    // The native identity issuer uses its own anti-CSRF header. Never mix
    // the legacy Operly CSRF header with first-party DragonZpyder sessions.
    headers[state.firstParty && path.startsWith("/dz/")
      ? "X-DZ-CSRF" : "X-CSRF-Token"] = token;
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
  const parts = String(value || "").trim().split(/\s+/).filter(Boolean);
  return parts.length ? parts.slice(0, 2).map(part => Array.from(part)[0]).join("").toUpperCase() : "?";
}

function setSession(session) {
  state.session = session;
  if (!session) {
    sessionLabel.textContent = "Personal session";
    profileInitial.textContent = "?";
    $("dz-runtime-notice").hidden = true;
    setArchiveMode(state.archiveSelected);
    return;
  }
  sessionLabel.textContent = session.displayName || "Personal account";
  profileInitial.textContent = initials(session.displayName);
  $("dz-runtime-notice").hidden = session.nativeChatEnabled !== false;
  setArchiveMode(state.archiveSelected);
}

async function ensurePersonalSession() {
  if (state.firstParty) {
    const result = await api("/dz/v2/personal/session", { csrf: false });
    const session = { device: "DragonZpyder", scope: "personal", nativeChatEnabled: result.native_chat_enabled !== false };
    setSession(session);
    // Optional identity presentation data; never use it to grant authority.
    void api("/dz/identity/v1/me", { csrf: false }).then(profile => {
      if (state.session !== session) return;
      session.displayName = typeof profile.display_name === "string" ? profile.display_name : "";
      setSession(session);
    }).catch(() => {});
    return session;
  }
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

async function discoverCentralIdentity() {
  const link = $("dragonzpyder-central-signin-modal");
  if (!link) return;
  try {
    const config = await api("/api/auth/bootstrap", { csrf: false });
    link.hidden = false;
  } catch {
    link.hidden = false;
  }
}

async function bootstrapAuth() {
  setRuntimeStatus(null, "Checking personal runtime…");
  try {
    // This flag comes from our own Web service. If native cutover is on,
    // never fall back to Operly when the DragonZpyder API is unavailable.
    const routing = await api("/dz/status", { csrf: false });
    state.firstParty = routing.web_cutover_enabled === true || routing.native_session_present === true;
    window.dragonzpyderNativeMode = state.firstParty;
    window.dispatchEvent(new CustomEvent("dragonzpyder:runtime-mode", { detail: { firstParty: state.firstParty } }));
    if (!state.firstParty) {
      await discoverCentralIdentity();
    }
    if (state.firstParty) {
      const obsolete = $("dragonzpyder-central-signin-modal");
      if (obsolete) obsolete.hidden = false;
      // Voice/Mesh still use the legacy Operly session verifier. Until those
      // routes receive first-party identity, never expose that old path.
      const mesh = $("mesh-switch");
      if (mesh) mesh.hidden = true;
      const voice = $("companion-open");
      if (voice) voice.hidden = true;
    }
    await ensurePersonalSession();
    hideAuth();
    if (state.firstParty && state.session.nativeChatEnabled === false) {
      setRuntimeStatus("error", "Signed in · Agent runtime not enabled");
      renderConversations();
      return;
    }
    setRuntimeStatus("online", "Personal runtime connected");
    await Promise.all([loadConversations({ restoreLatest: true }), refreshApprovals()]);
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
  if (state.firstParty) {
    await api("/dz/identity/v1/password/login", {
      method: "POST", body: { email, password }, csrf: false,
    });
    await ensurePersonalSession();
    hideAuth();
    if (state.session.nativeChatEnabled === false) {
      setRuntimeStatus("error", "Signed in · Agent runtime not enabled");
      return;
    }
    setRuntimeStatus("online", "DragonZpyder agent connected");
    await loadConversations({ restoreLatest: true });
    return;
  }
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
  emptyState.style.setProperty("display", "none", "important");
  messages.classList.add("active");
}

function showEmptyState() {
  followingLatest = true;
  if (jumpLatest) jumpLatest.hidden = true;
  emptyState.hidden = false;
  emptyState.style.removeProperty("display");
  messages.classList.remove("active");
  messages.replaceChildren();
}

function renderMessageContent(element, content, role = "assistant") {
  const source = String(content || "").replace(/\r\n?/g, "\n")
    .replace(/^\s*(?:\*\*Operly:\*\*|\*\*Operly\*\*:|Operly:)\s*/i, "");
  if (role === "user") {
    element.textContent = source;
    return;
  }
  renderMarkdown(element, source);
}

function messageNode(role, content, { pending = false, error = false, meta = "", approvalId = null } = {}) {
  const wrap = document.createElement("article");
  wrap.className = `message ${role === "user" ? "user" : "assistant"}`;
  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "You" : "✳";
  const body = document.createElement("div");
  body.className = "message-body";
  const label = document.createElement("div");
  label.className = "message-role";
  label.textContent = role === "user" ? "You" : "DragonZpyder";
  const value = document.createElement("div");
  value.className = `message-content${error ? " error" : ""}`;
  if (pending) {
    value.innerHTML = '<span class="thinking"><i></i><i></i><i></i></span>';
  }
  // Markdown rendering requires an element attached to the live document.
  // The caller renders saved messages after appending their DOM nodes.
  body.append(label, value);
  if (role !== "user" && !pending) {
    // The message content, not an assistant's claims, is what gets copied.
    // Keep this action independent of any agent execution or retry semantics.
    const actions = document.createElement("div");
    actions.className = "dz-message-actions";
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "dz-message-copy";
    copy.setAttribute("aria-label", "Copy assistant response");
    copy.title = "Copy response";
    copy.textContent = "Copy";
    copy.addEventListener("click", async () => {
      const content = value.innerText || value.textContent || "";
      try {
        await navigator.clipboard.writeText(content);
        copy.textContent = "Copied";
        setTimeout(() => { if (copy.isConnected) copy.textContent = "Copy"; }, 1800);
      } catch {
        copy.textContent = "Copy unavailable";
        setTimeout(() => { if (copy.isConnected) copy.textContent = "Copy"; }, 1800);
      }
    });
    actions.appendChild(copy);
    body.appendChild(actions);
  }
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
  if (!options.pending) renderMessageContent(node.value, content, role);
  if (role !== "user" && options.pending) node.wrap.classList.add("dz-running");
  scrollToBottom(role === "user" && !options.restoring);
  return node;
}

// Stay attached to the latest turn only while the reader is near the bottom.
// Reading earlier responses must not be interrupted by asynchronous updates.
let followingLatest = true;
let lastProgrammaticScroll = false;
const jumpLatest = $("dz-jump-latest");
const atLatest = () => chatMain.scrollHeight - chatMain.scrollTop - chatMain.clientHeight < 120;
const updateLatestControl = () => {
  if (!jumpLatest) return;
  jumpLatest.hidden = followingLatest || !messages.classList.contains("active");
};
chatMain.addEventListener("scroll", () => {
  if (lastProgrammaticScroll) return;
  followingLatest = atLatest();
  updateLatestControl();
}, { passive: true });
jumpLatest?.addEventListener("click", () => scrollToBottom(true));
function scrollToBottom(force = false) {
  if (!force && !followingLatest) { updateLatestControl(); return; }
  requestAnimationFrame(() => {
    lastProgrammaticScroll = true;
    chatMain.scrollTop = chatMain.scrollHeight;
    followingLatest = true;
    updateLatestControl();
    requestAnimationFrame(() => { lastProgrammaticScroll = false; });
  });
}

// Keep the final message above the floating composer, even when a long draft,
// attachments, or mobile viewport changes alter its height.
function syncComposerClearance() {
  if (!composerWrap) return;
  const height = Math.ceil(composerWrap.getBoundingClientRect().height);
  if (!height) return;
  document.documentElement.style.setProperty("--dz-composer-height", `${height}px`);
  if (followingLatest) scrollToBottom();
}
if (composerWrap && typeof ResizeObserver !== "undefined") {
  new ResizeObserver(syncComposerClearance).observe(composerWrap);
}
window.addEventListener("resize", syncComposerClearance);
requestAnimationFrame(syncComposerClearance);

function clearConversationSelection() {
  state.selectionVersion++;
  state.conversationId = null;
  setArchiveMode(false);
  for (const button of conversationList.querySelectorAll(".conversation-button")) button.classList.remove("active");
  showEmptyState();
  if(window.dragonzpyderMesh?.isActive())window.dragonzpyderMesh.clear();
  messageInput.focus();
  sidebar.classList.remove("open");
}

function setArchiveMode(active) {
  state.archiveSelected = active;
  messageInput.disabled = active || state.sending;
  const unavailable = state.firstParty && state.session?.nativeChatEnabled === false;
  sendButton.disabled = active || state.sending || unavailable;
  for (const chip of document.querySelectorAll(".prompt-chip")) chip.disabled = unavailable;
  messageInput.placeholder = active ? "Archived history · start a new chat to continue" : (messageInput.dataset.originalPlaceholder || "Message DragonZpyder");
  syncComposerAction();
}
messageInput.dataset.originalPlaceholder = messageInput.placeholder;

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
  const search = ($("conversation-search")?.value || "").trim().toLocaleLowerCase();
  const filtered = state.conversations.filter(item =>
    (item.title || "Conversation").toLocaleLowerCase().includes(search));
  if (!filtered.length) {
    const empty = document.createElement("p");
    empty.className = "conversation-empty";
    empty.textContent = "No matching conversations";
    conversationList.append(empty);
    return;
  }
  const now = new Date();
  const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  let previousGroup = "";
  for (const item of filtered) {
    // Date grouping uses server timestamps when present. No inferred activity.
    const stamp = item.updated_at || item.created_at || null;
    const epoch = typeof stamp === "string" || typeof stamp === "number" ? new Date(stamp).getTime() : NaN;
    const daysAgo = Number.isFinite(epoch) ? Math.floor((dayStart - epoch) / 86400000) : null;
    const group = daysAgo === null ? "Conversations"
      : daysAgo <= 0 ? "Today"
      : daysAgo === 1 ? "Yesterday"
      : daysAgo < 7 ? "Previous 7 days" : "Earlier";
    if (group !== previousGroup) {
      const heading = document.createElement("div");
      heading.className = "dz-conversation-group";
      heading.textContent = group;
      conversationList.appendChild(heading);
      previousGroup = group;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = `conversation-button${item.id === state.conversationId && Boolean(item.archived) === state.archiveSelected ? " active" : ""}`;
    button.textContent = (item.archived ? "Archive · " : "") + (item.title || "Conversation");
    button.title = button.textContent;
    button.addEventListener("click", () => openConversation(item.id, { archived: Boolean(item.archived) }));
    conversationList.appendChild(button);
  }
}

async function loadConversations({ restoreLatest = false } = {}) {
  try {
    const rows = await api(state.firstParty
      ? "/dz/v2/personal/conversations" : "/api/personal-agent/conversations", { csrf: false });
    state.conversations = state.firstParty
      ? (Array.isArray(rows.conversations) ? rows.conversations : [])
      : (Array.isArray(rows) ? rows : []);
    if (state.firstParty) {
      const live = state.conversations;
      try {
        const archived = [];
        let offset = 0;
        // Bound the work and reject non-advancing pagination.
        for (let page = 0; page < 101; page++) {
          const result = await api("/dz/v2/personal/archive/conversations?offset=" + offset, { csrf: false });
          if (!Array.isArray(result.conversations)) throw Error("Invalid archive response");
          archived.push(...result.conversations.map(item => ({ ...item, archived: true })));
          if (result.next_offset == null) break;
          if (result.next_offset !== offset + 100 || page === 100) throw Error("Archive page limit reached");
          offset = result.next_offset;
        }
        if (!state.session) return;
        state.conversations = [...live, ...archived];
      } catch (error) {
        if (!state.session) return;
        if (error.status === 401) return showAuth();
        if (error.status !== 404) showToast("Archived history unavailable. Live chats are unaffected.", 5000);
      }
    }
    renderConversations();
    // Initial authentication populates the sidebar but otherwise leaves a
    // blank message pane. Restore the newest authorized Personal conversation.
    // Ordinary post-send refreshes must not change the current selection.
    if (restoreLatest && !state.conversationId && state.conversations.length) {
      await openConversation(state.conversations[0].id, { archived: Boolean(state.conversations[0].archived) });
    }
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return showAuth();
    console.warn("Could not load conversations", error);
  }
}

async function openConversation(id, { archived = false } = {}) {
  if (!id || state.sending || (archived && !state.firstParty)) return;
  const version = ++state.selectionVersion;
  setArchiveMode(archived);
  if(window.dragonzpyderMesh?.isActive())window.dragonzpyderMesh.disable();
  state.conversationId = id;
  renderConversations();
  sidebar.classList.remove("open");
  showMessages();
  messages.replaceChildren();
  const pending = appendMessage("assistant", "", { pending: true });
  try {
    if (archived) {
      const notice = document.createElement("p");
      notice.className = "message-meta";
      notice.textContent = "Read-only Operly archive. Start a new chat to use DragonZpyder.";
      messages.replaceChildren(notice);
      let offset = 0;
      for (let page = 0; page < 1000; page++) {
        const rows = await api(`/dz/v2/personal/archive/conversations/${encodeURIComponent(id)}/messages?offset=${offset}`, { csrf: false });
        if (version !== state.selectionVersion || !state.session) return;
        if (!Array.isArray(rows.messages) || rows.archived !== true) throw Error("Invalid archive response");
        for (const row of rows.messages) {
          if (!["user", "assistant"].includes(row.role)) continue;
          // Archived content is text only, not executable or interpreted markup.
          const node = messageNode(row.role, "", { restoring: true });
          node.value.textContent = row.content || "";
          node.value.style.whiteSpace = "pre-wrap";
          messages.appendChild(node.wrap);
        }
        if (rows.next_offset == null) { scrollToBottom(true); return; }
        if (rows.next_offset !== offset + 10) throw Error("Invalid archive pagination");
        offset = rows.next_offset;
      }
      throw Error("Archive display limit reached");
    }
    const rows = await api(state.firstParty
      ? `/dz/v2/personal/conversations/${encodeURIComponent(id)}/messages`
      : `/api/personal-agent/conversations/${encodeURIComponent(id)}/messages`, { csrf: false });
    if (version !== state.selectionVersion || !state.session) return;
    messages.replaceChildren();
    const history = state.firstParty ? rows.messages : rows;
    for (const row of Array.isArray(history) ? history : []) {
      if (row.role !== "user" && row.role !== "assistant") continue;
      appendMessage(row.role === "user" ? "user" : "assistant", row.content || "", { restoring: true });
    }
    renderConversations();
    scrollToBottom(true);
  } catch (error) {
    if (version !== state.selectionVersion || !state.session) return;
    if (archived) {
      const warning = document.createElement("p");
      warning.textContent = "Archive could not be fully loaded.";
      messages.appendChild(warning);
    } else {
      pending.value.textContent = error.message;
      pending.value.classList.add("error");
    }
  }
}

function runtimeMessage(result) {
  if (!result || typeof result !== "object") return "DragonZpyder completed the request.";
  return String(result.message || result.result?.message || result.output || "DragonZpyder completed the request.");
}

async function submitViaClientAdapter(message, requestId) {
  // The personal-tools client submission endpoint is not registered in Operly.
  // Use the supported personal-agent chat API directly.
  const body = { message };
  if (state.conversationId) body.conversation_id = state.conversationId;
  if (state.firstParty && state.selectedMcpConnections.length) {
    body.mcp_connection_ids = [...state.selectedMcpConnections];
  }
  const result = await api(state.firstParty
    ? "/dz/v2/personal/chat" : "/api/personal-agent/chat",
    { method: "POST", body });
  result.client_request_id = requestId;
  return result;
}

async function sendMessage(message, { companion = false, fromComposer = false } = {}) {
  if (state.archiveSelected) { showToast("Start a new chat to continue.", 4000); return; }
  const clean = String(message || "").trim();
  if (!clean || state.sending) { if (companion) throw Error("Personal agent is busy"); return; }
  if (!state.session) { showAuth(); if (companion) throw Error("Sign in first"); return; }

  if (state.firstParty && state.session.nativeChatEnabled === false) {
    showToast("Signed in, but native chat is not enabled yet.", 5000);
    return;
  }
  state.sending = true;
  sendButton.disabled = true;
  // The accepted prompt now lives in the conversation, not in the editor.
  // Clear synchronously before awaiting the agent, and preserve unrelated drafts
  // when the request came from a suggestion or voice rather than the composer.
  if (fromComposer) {
    messageInput.value = "";
    autoSizeInput();
    if (window.matchMedia("(max-width: 820px)").matches) messageInput.blur();
  }
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
    renderMessageContent(pending.value, text);
    pending.wrap.classList.remove("dz-running");
    // Add message actions only after the backend has actually returned.
    if (!pending.body.querySelector(".dz-message-actions")) {
      const actions = document.createElement("div");
      actions.className = "dz-message-actions";
      const copy = document.createElement("button");
      copy.className = "dz-message-copy";
      copy.type = "button";
      copy.setAttribute("aria-label", "Copy assistant response");
      copy.textContent = "Copy";
      copy.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(pending.value.innerText || pending.value.textContent || "");
          copy.textContent = "Copied";
          setTimeout(() => { if(copy.isConnected) copy.textContent = "Copy"; }, 1800);
        } catch { copy.textContent = "Copy unavailable"; }
      });
      actions.append(copy);
      pending.body.append(actions);
    }
    // The server chooses the trusted execution engine; the model cannot
    // declare itself a DragonZpyder harness run in the answer text.
    if (result.dispatch === "dragonzpyder_personal_mcp"
        || result.dispatch === "dragonzpyder_first_party") {
      const rawTools = result.dispatch === "dragonzpyder_first_party"
        ? result.execution_receipts?.tool_names : result.capability_calls;
      const tools = Array.isArray(rawTools)
        ? rawTools.filter(name => typeof name === "string"
            && /^[A-Za-z_][A-Za-z0-9_-]{0,79}$/.test(name)).slice(0, 20)
        : [];
      const meta = document.createElement("div");
      meta.className = "message-meta";
      meta.textContent = "DragonZpyder harness · " +
        (tools.length ? "MCP tools: " + tools.join(", ") : "No verified MCP tool calls") +
        (result.run_id ? " · Run: " + String(result.run_id).slice(0, 90) : "");
      pending.body.appendChild(meta);
      // Only show backend-issued tool receipts; assistant prose is not proof
      // of an executed tool. Tools may complete without proving the goal.
      const evidence = result.execution_receipts;
      if (evidence && typeof evidence === "object") {
        const names = Array.isArray(evidence.tool_names)
          ? evidence.tool_names.filter(x => typeof x === "string" && /^[A-Za-z_][A-Za-z0-9_-]{0,79}$/.test(x)).slice(0, 40)
          : [];
        const failures = Number.isInteger(evidence.failed_tool_count)
          && evidence.failed_tool_count >= 0 && evidence.failed_tool_count <= 100
          ? evidence.failed_tool_count : 0;
        // Do not label a backend tool receipt as independently verified objective completion.
        const trace = document.createElement("details");
        trace.className = "dz-execution-evidence";
        const summary = document.createElement("summary");
        summary.textContent = failures ? "Tool execution · " + failures + " failed" : "Tool execution · View receipts";
        trace.appendChild(summary);
        const list = document.createElement("ul");
        for (const name of names) {
          const li = document.createElement("li");
          li.textContent = name;
          list.appendChild(li);
        }
        if (names.length) trace.appendChild(list);
        const note = document.createElement("p");
        note.textContent = "Backend-reported tool activity only. The overall objective has not been independently verified.";
        trace.appendChild(note);
        pending.body.appendChild(trace);
      }
    }
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
    await Promise.all([loadConversations({ restoreLatest: true }), refreshApprovals()]);
    // MCP tools may request Kernel approval inside the model run. The agent's
    // visible prose is not a trustworthy approval ID; use only backend rows.
    if (state.approvals.some(row => row.approval_source === "kernel"
        && row.conversation_id === state.conversationId)) {
      const inline = document.createElement("div");
      inline.className = "approval-inline";
      inline.textContent = "An Operly action needs your exact approval. ";
      const review = document.createElement("button");
      review.type = "button"; review.className = "approve-btn";
      review.textContent = "Review";
      review.addEventListener("click", openApprovals);
      inline.appendChild(review);
      pending.body.appendChild(inline);
    }
    return { message: text, approval_required: Boolean(result.approval_id), blocked: Boolean(blocker) };
  } catch (error) {
    pending.wrap.classList.remove("dz-running");
    pending.value.classList.add("error");
    // The draft is recoverable on an ordinary failure, but never restore an
    // uncertain-delivery request where pressing Send could duplicate an action.
    if (fromComposer && !(error instanceof ApiError && error.code === "execution_outcome_uncertain")) {
      messageInput.value = clean;
      autoSizeInput();
    }
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
    if (companion) throw error;
  } finally {
    state.sending = false;
    sendButton.disabled = false;
    messageInput.disabled = false;
    autoSizeInput();
    // Focusing the textarea reopens the mobile keyboard over the response.
    if (!companion && !window.matchMedia("(max-width: 820px)").matches) messageInput.focus();
    scrollToBottom();
  }
}
window.dragonzpyderDelegatePersonalTask = (request) => sendMessage(request, { companion: true });

async function refreshApprovals() {
  if (state.firstParty) {
    // Never query Operly approval APIs with a first-party identity session.
    state.approvals = [];
    approvalCount.textContent = "0";
    return;
  }
  // Workspace provisioning uses Operly Kernel approvals, not the legacy
  // Personal-tools approvals table. Both are authenticated same-origin APIs.
  // No approval can be created or executed merely by rendering a card.
  const sources = [
    ["/api/personal-tools/approvals?status=pending", "legacy"],
    ["/api/kernel/personal/approvals?status=pending", "kernel"],
  ];
  const results = await Promise.allSettled(sources.map(async ([path, source]) => {
    const payload = await api(path, { csrf: false });
    return (Array.isArray(payload?.approvals) ? payload.approvals : []).map(row => ({
      ...row, approval_source: source,
    }));
  }));
  // Both legacy and Kernel endpoints may project the SAME KernelApproval.
  // Deduplicate by immutable approval ID, preferring the Kernel source so
  // the correct decision/continuation handlers are used for MCP actions.
  const unique = new Map();
  const rows = results.flatMap(result => result.status === "fulfilled" ? result.value : []);
  for (const approval of rows) {
    const id = typeof approval.id === "string" ? approval.id.trim() : "";
    if (!id) continue;
    if (!unique.has(id) || approval.approval_source === "kernel") unique.set(id, approval);
  }
  state.approvals = Array.from(unique.values());
  for (const result of results) {
    if (result.status === "rejected" && !(result.reason instanceof ApiError && result.reason.status === 401)) {
      console.warn("Could not load one approval source", result.reason);
    }
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
    const decisionPath = approval.approval_source === "kernel"
      ? `/api/kernel/personal/approvals/${encodeURIComponent(approval.id)}/decision`
      : `/api/personal-tools/approvals/${encodeURIComponent(approval.id)}/decision`;
    await api(decisionPath, { method: "POST", body: { approved: false } });
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
    if (approval.approval_source === "kernel") {
      // The backend re-opens the frozen, exact approved MCP request from the
      // Kernel approval row. Neither the model nor the UI may alter arguments.
      await api(`/api/kernel/personal/approvals/${encodeURIComponent(approval.id)}/decision`, {
        method: "POST", body: { approved: true },
      });
      const executed = await api(`/api/kernel/personal/approvals/${encodeURIComponent(approval.id)}/execute`, {
        method: "POST", body: {},
      });
      if (executed?.status !== "completed" || executed?.workspace_ownership_verified !== true) {
        throw new ApiError("Workspace creation could not be independently verified; do not repeat it.", {
          code: "WORKSPACE_VERIFICATION_FAILED",
        });
      }
      const created = executed.result || {};
      closeApprovals();
      appendMessage("assistant", `Operly confirmed workspace “${created.name}” was created under your account. Workspace ID: ${created.id}. Ownership verified. Adding workspace records requires separate workspace authorization.`, {
        meta: "Operly Kernel approval · database readback verified",
      });
      await refreshApprovals();
      return;
    }
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
    await api(state.firstParty ? "/dz/identity/v1/logout" : "/api/auth/logout",
      { method: "POST", body: {} });
  } catch (error) {
    if (state.firstParty) {
      // Do not present a successful native sign-out if server revocation failed.
      showToast("Sign-out could not be confirmed. Try again.", 7000);
      return;
    }
    if (!(error instanceof ApiError && [401, 409].includes(error.status))) console.warn("Logout failed", error);
  }
  window.dispatchEvent(new Event("dragonzpyder:logout"));
  setSession(null);
  state.selectionVersion++;
  state.conversationId = null;
  setArchiveMode(false);
  state.conversations = [];
  state.approvals = [];
  renderConversations();
  showEmptyState();
  refreshApprovals();
  profileMenu.hidden = true;
  setRuntimeStatus(null, "Sign in required");
  if (state.firstParty) { window.location.replace("/login"); return; }
  showAuth();
}

function syncComposerAction() {
  // The single trailing action is Live voice while the composer is empty,
  // and Send when text or attachments are ready.
  const pending = Boolean(messageInput.value.trim()) ||
    Boolean(window.dragonzpyderMesh?.hasAttachments?.());
  const voice = $("companion-open");
  voice.hidden = state.firstParty || pending;
  voice.disabled = state.sending || Boolean(window.dragonzpyderMesh?.isBusy?.());
  sendButton.hidden = state.archiveSelected || !pending;
  sendButton.disabled = state.archiveSelected || state.sending || (state.firstParty && state.session?.nativeChatEnabled === false);
}
window.dragonzpyderComposerSync = syncComposerAction;
window.addEventListener("dragonzpyder:mcp-selection", (event) => {
  const ids = event.detail?.ids;
  state.selectedMcpConnections = Array.isArray(ids)
    ? [...new Set(ids.filter(id => typeof id === "string" && /^c[a-f0-9]{30}$/.test(id)))].slice(0, 10)
    : [];
});

function autoSizeInput() {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 170)}px`;
  syncComposerAction();
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
  if(window.dragonzpyderMesh?.isActive())window.dragonzpyderMesh.submit(messageInput.value);
  else sendMessage(messageInput.value, { fromComposer: true });
});
messageInput.addEventListener("input", autoSizeInput);
messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

for (const chip of document.querySelectorAll(".prompt-chip")) {
  chip.addEventListener("click", () => {
    const prompt = chip.dataset.prompt || chip.textContent.trim();
    if (window.dragonzpyderMesh?.isActive()) {
      messageInput.value = prompt; autoSizeInput(); messageInput.focus();
    } else sendMessage(prompt);
  });
}
$("conversation-search")?.addEventListener("input", renderConversations);
// Ctrl/⌘ K is reserved for the React command palette; New Chat remains a separate action.

$("new-chat").addEventListener("click", clearConversationSelection);
$("approvals-button").addEventListener("click", openApprovals);
$("approvals-top").addEventListener("click", openApprovals);
$("close-approvals").addEventListener("click", closeApprovals);
approvalsDrawer.addEventListener("click", (event) => { if (event.target === approvalsDrawer) closeApprovals(); });
function setProfileMenu(open) {
  profileMenu.hidden = !open;
  $("profile-button").setAttribute("aria-expanded", String(open));
}
$("profile-button").addEventListener("click", () => setProfileMenu(profileMenu.hidden));
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !profileMenu.hidden) { setProfileMenu(false); $("profile-button").focus(); }
});
$("logout-button").addEventListener("click", logout);
$("open-sidebar").addEventListener("click", () => sidebar.classList.add("open"));
$("close-sidebar").addEventListener("click", () => sidebar.classList.remove("open"));

document.addEventListener("click", (event) => {
  if (!profileMenu.hidden && !profileMenu.contains(event.target) && !$("profile-button").contains(event.target)) setProfileMenu(false);
});

window.addEventListener("online", () => {
  const unavailable=state.session?.nativeChatEnabled === false;
  setRuntimeStatus(unavailable ? "error" : state.session ? "online" : null, unavailable ? "Signed in · Agent runtime not enabled" : state.session ? "Personal runtime connected" : "Sign in required");
});
window.addEventListener("offline", () => setRuntimeStatus("error", "Offline"));

autoSizeInput();
bootstrapAuth();

window.addEventListener("dragonzpyder:mesh-disabled",()=>{ if(state.conversationId)openConversation(state.conversationId, { archived: state.archiveSelected });else showEmptyState(); });
