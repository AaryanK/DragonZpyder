"use strict";
const el = (id) => document.getElementById(id);
const articlePath = window.location.pathname.startsWith("/wiki/")
  ? window.location.pathname.slice(6) : null;
let currentArticle = null;

function showToast(message) {
  const node = el("toast");
  node.textContent = message;
  node.classList.remove("hidden");
  window.setTimeout(() => node.classList.add("hidden"), 4500);
}
async function readResponse(response) {
  let data;
  try { data = await response.json(); } catch (_) { data = {}; }
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Sorry, something went wrong.");
  return data;
}
function addText(parent, tag, value, cls) {
  const node = document.createElement(tag);
  node.textContent = value;
  if (cls) node.className = cls;
  parent.appendChild(node);
  return node;
}
async function searchWikipedia(query) {
  const results = el("search-results"), list = el("result-list");
  results.classList.remove("hidden");
  list.replaceChildren();
  addText(list, "p", "Searching Wikipedia…");
  try {
    const pages = (await readResponse(await fetch("/api/search?q=" + encodeURIComponent(query)))).pages;
    list.replaceChildren();
    if (!pages.length) return addText(list, "p", "No results found. Try another term.");
    for (const page of pages) {
      const link = document.createElement("a");
      link.href = "/wiki/" + page.key.split("/").map(encodeURIComponent).join("/");
      link.className = "search-result";
      addText(link, "b", page.title || page.key);
      addText(link, "span", page.description || "Wikipedia article");
      list.appendChild(link);
    }
  } catch (error) {
    list.replaceChildren();
    addText(list, "p", error.message);
  }
}
function makeContents(body) {
  const toc = el("toc");
  toc.replaceChildren();
  let index = 0;
  for (const h of body.querySelectorAll("h2, h3")) {
    const title = h.textContent.trim();
    if (!title || title.toLowerCase() === "contents") continue;
    if (!h.id) h.id = "querypedia-section-" + (++index);
    const a = document.createElement("a");
    a.href = "#" + encodeURIComponent(h.id);
    a.textContent = title.length > 72 ? title.slice(0, 69) + "…" : title;
    if (h.tagName === "H3") a.style.paddingLeft = "21px";
    toc.appendChild(a);
    if (toc.children.length >= 60) break;
  }
  if (!toc.children.length) addText(toc, "div", "No sections available", "muted");
}
function fillAttribution(article) {
  for (const id of ["source-top", "source-bottom", "source-panel"]) el(id).href = article.source;
  el("history-link").href = "https://en.wikipedia.org/w/index.php?title=" +
    encodeURIComponent(article.key) + "&action=history";
  const license = article.license || {};
  if (license.url) {
    el("license-link").href = license.url.startsWith("//") ? "https:" + license.url : license.url;
    el("license-link").textContent = license.title || "Content licence";
  }
}
async function loadArticle() {
  el("home-view").classList.add("hidden");
  el("article-view").classList.remove("hidden");
  const requested = decodeURIComponent(articlePath);
  el("breadcrumb-title").textContent = requested.replaceAll("_", " ");
  el("article-title").textContent = requested.replaceAll("_", " ");
  try {
    const article = await readResponse(await fetch("/api/page/" + articlePath));
    currentArticle = article;
    document.title = article.title + " — Querypedia";
    el("article-title").textContent = article.title;
    el("breadcrumb-title").textContent = article.title;
    el("last-updated").textContent = article.last_updated
      ? "Wikipedia revision · " + new Date(article.last_updated).toLocaleDateString(undefined, {year:"numeric",month:"long",day:"numeric"})
      : "From Wikipedia";
    el("article-body").innerHTML = article.html;
    makeContents(el("article-body"));
    fillAttribution(article);
    el("loading").classList.add("hidden");
    el("article-ready").classList.remove("hidden");
  } catch (error) {
    el("loading").textContent = error.message + " Open the original Wikipedia article or try another search.";
  }
}
function bubble(message, kind, source) {
  const conversation = el("conversation");
  const node = addText(conversation, "div", message, "bubble " + kind);
  if (source) {
    const foot = document.createElement("div");
    foot.className = "answer-source";
    const link = addText(foot, "a", "Verify on Wikipedia ↗");
    link.href = source;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    conversation.appendChild(foot);
  }
  conversation.scrollTop = conversation.scrollHeight;
  return node;
}
async function askQuestion(question) {
  if (!currentArticle) return showToast("Open an article before asking a question.");
  bubble(question, "user");
  const input = el("question-input");
  input.value = "";
  el("ask-button").disabled = true;
  const pending = bubble("Reading article and composing an answer…", "assistant");
  try {
    const result = await readResponse(await fetch("/api/ask", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({title:currentArticle.key,question})
    }));
    pending.remove();
    bubble(result.answer, "assistant", result.source);
  } catch (error) {
    pending.remove();
    bubble(error.message, "assistant error");
  } finally {
    el("ask-button").disabled = false;
    input.focus();
  }
}
for (const id of ["search-form", "hero-form"]) {
  el(id).addEventListener("submit", (event) => {
    event.preventDefault();
    const value = (id === "search-form" ? el("search-input") : el("hero-input")).value.trim();
    if (value) searchWikipedia(value);
  });
}
el("close-search").addEventListener("click", () => el("search-results").classList.add("hidden"));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") el("search-results").classList.add("hidden");
});
el("ask-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const question = el("question-input").value.trim();
  if (question.length >= 3) askQuestion(question);
});
el("question-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    el("ask-form").requestSubmit();
  }
});
for (const btn of document.querySelectorAll(".suggestion")) {
  btn.addEventListener("click", () => askQuestion(btn.dataset.question));
}
if (articlePath) loadArticle();
