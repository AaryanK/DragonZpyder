"use strict";
const byId = id => document.getElementById(id);
const login = byId("login");
const chat = byId("chat");
const loginError = byId("loginerror");
const chatError = byId("chaterror");
const send = byId("send");
const promptInput = byId("prompt");
const fileInput = byId("file");
const pillBox = byId("attachments");
const messages = byId("messages");
const modelSelect = byId("model");
let history = [];
let selected = [];

function showError(element, message) {
  element.textContent = message;
  element.hidden = !message;
}
function toggleSession(isAuthed, models = []) {
  login.hidden = isAuthed;
  chat.hidden = !isAuthed;
  byId("logout").hidden = !isAuthed;
  if (isAuthed) {
    modelSelect.replaceChildren();
    for (const item of models) {
      const option = document.createElement("option");
      option.value = item;
      option.textContent = item;
      modelSelect.append(option);
    }
  }
}
async function call(path, data) {
  const result = await fetch(path, {
    method: "POST",
    headers: {"content-type": "application/json", "x-dragonzpyder-chat": "1"},
    body: JSON.stringify(data),
    credentials: "same-origin",
    cache: "no-store"
  });
  let json = {};
  try { json = await result.json(); } catch {}
  if (!result.ok) {
    const message = typeof json.detail === "string" ? json.detail : "Request failed (" + result.status + ")";
    throw new Error(message);
  }
  return json;
}
async function refreshSession() {
  try {
    const response = await fetch("/demo/session", {credentials: "same-origin", cache: "no-store"});
    const data = await response.json();
    toggleSession(Boolean(data.authenticated), data.models || []);
    if (!data.configured) showError(loginError, "Demo setup pending: add OPENROUTER_API_KEY and DRAGONZPYDER_CHAT_PASSWORD to this Railway service.");
  } catch { showError(loginError, "Unable to reach the demo backend."); }
}
byId("loginform").addEventListener("submit", async event => {
  event.preventDefault();
  showError(loginError, "");
  const password = byId("password").value;
  const button = event.currentTarget.querySelector("button");
  button.disabled = true;
  try {
    const data = await call("/demo/login", {password});
    byId("password").value = "";
    toggleSession(true, data.models);
    promptInput.focus();
  } catch (e) {
    showError(loginError, e.message);
  } finally { button.disabled = false; }
});
byId("logout").addEventListener("click", async () => {
  try { await call("/demo/logout", {}); }
  finally { history = []; selected = []; toggleSession(false); }
});
byId("clear").addEventListener("click", () => {
  history = [];
  selected = [];
  fileInput.value = "";
  renderFiles();
  messages.replaceChildren();
  const note = document.createElement("div");
  note.className = "intro";
  note.textContent = "New conversation started. Attach a file to analyse it, or ask a question.";
  messages.append(note);
});
function renderFiles() {
  pillBox.replaceChildren();
  pillBox.hidden = selected.length === 0;
  selected.forEach((f, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "filepill";
    btn.textContent = f.name + " ×";
    btn.title = "Remove attachment";
    btn.addEventListener("click", () => { selected.splice(i, 1); renderFiles(); });
    pillBox.append(btn);
  });
}
fileInput.addEventListener("change", () => {
  showError(chatError, "");
  for (const f of fileInput.files) {
    if (selected.length >= 3) { showError(chatError, "Maximum three attachments."); break; }
    if (f.size > 3 * 1024 * 1024) { showError(chatError, f.name + " is larger than 3 MB."); continue; }
    if (!/\.(png|jpe?g|webp|pdf|docx|txt|md|csv|json|py|log)$/i.test(f.name)) {
      showError(chatError, "Unsupported file type: " + f.name); continue;
    }
    selected.push(f);
  }
  fileInput.value = "";
  renderFiles();
});
function addBubble(role, content) {
  const intro = messages.querySelector(".intro");
  if (intro) intro.remove();
  const box = document.createElement("div");
  box.className = "bubble " + role;
  const title = document.createElement("div");
  title.className = "speaker";
  title.textContent = role === "user" ? "YOU" : "DRAGONZPYDER";
  const body = document.createElement("div");
  body.textContent = content;
  box.append(title, body);
  messages.append(box);
  messages.scrollTop = messages.scrollHeight;
  return body;
}
async function toBase64(file) {
  const dataURL = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Could not read " + file.name));
    reader.readAsDataURL(file);
  });
  return {name: file.name, data: dataURL.substring(dataURL.indexOf(",") + 1)};
}
byId("composer").addEventListener("submit", async event => {
  event.preventDefault();
  if (send.disabled) return;
  showError(chatError, "");
  const text = promptInput.value.trim();
  if (!text) return;
  send.disabled = true;
  send.textContent = "Thinking…";
  const files = [...selected];
  try {
    const attachments = await Promise.all(files.map(toBase64));
    const turns = [...history, {role:"user", content:text}].slice(-12);
    const result = await call("/demo/chat", {model:modelSelect.value, messages:turns, attachments});
    const names = files.length ? "\nAttached: " + files.map(f => f.name).join(", ") : "";
    addBubble("user", text + names);
    addBubble("assistant", result.reply || "(empty response)");
    history = [...turns, {role:"assistant", content:result.reply || "(empty)"}].slice(-10);
    promptInput.value = "";
    selected = [];
    renderFiles();
  } catch (e) {
    showError(chatError, e.message);
    if (/sign in/i.test(e.message)) toggleSession(false);
  } finally {
    send.disabled = false;
    send.textContent = "Send ↗";
  }
});
promptInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    byId("composer").requestSubmit();
  }
});
refreshSession();