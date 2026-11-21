/* AI-generated text renderer — GFM markdown with strict HTML sanitisation.
   The same renderer is used by the permissioned Agent and direct AI Mesh.
   Nothing in a model response may execute code or mount browser controls. */
import { marked } from "marked";
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/core";
import javascript from "highlight.js/lib/languages/javascript";
import typescript from "highlight.js/lib/languages/typescript";
import python from "highlight.js/lib/languages/python";
import bash from "highlight.js/lib/languages/bash";
import json from "highlight.js/lib/languages/json";
import css from "highlight.js/lib/languages/css";
import xml from "highlight.js/lib/languages/xml";
import sql from "highlight.js/lib/languages/sql";
import java from "highlight.js/lib/languages/java";
import cpp from "highlight.js/lib/languages/cpp";
import c from "highlight.js/lib/languages/c";
import rust from "highlight.js/lib/languages/rust";
import go from "highlight.js/lib/languages/go";
import yaml from "highlight.js/lib/languages/yaml";
import markdown from "highlight.js/lib/languages/markdown";
import diff from "highlight.js/lib/languages/diff";

for (const [name, language] of Object.entries({
  javascript, js: javascript, typescript, ts: typescript, python, py: python,
  bash, sh: bash, shell: bash, json, css, html: xml, xml, sql, java,
  cpp, c, rust, go, yaml, yml: yaml, markdown, md: markdown, diff,
})) {
  if (!hljs.getLanguage(name)) hljs.registerLanguage(name, language);
}

const renderer = new marked.Renderer();
const escapeHTML = input => String(input).replace(/[&<>"']/g, chr => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[chr]);
// Render literal HTML as text, never as model-supplied DOM.
renderer.html = token => escapeHTML(typeof token === "string" ? token : token.text);
marked.setOptions({ gfm: true, breaks: true, renderer });

const sanitise = markup => {
  const purifier = DOMPurify.sanitize ? DOMPurify : DOMPurify(window);
  return purifier.sanitize(markup, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ["style", "script", "iframe", "svg", "math", "object", "embed",
      "form", "input", "select", "button", "textarea", "video", "audio", "picture"],
    FORBID_ATTR: ["style", "srcset", "onload", "onerror"],
    ALLOW_DATA_ATTR: false,
  });
};
function enhance(root) {
  for (const a of root.querySelectorAll("a[href]")) {
    try {
      const url = new URL(a.getAttribute("href"), "https://dragonzpyder.xyz");
      if (!["http:", "https:", "mailto:"].includes(url.protocol)) {
        a.removeAttribute("href");
        continue;
      }
      a.target = "_blank";
      a.rel = "noopener noreferrer nofollow";
    } catch {
      a.removeAttribute("href");
    }
  }
  // Images returned as external links would leak visitor network details.
  for (const img of root.querySelectorAll("img")) {
    const label = document.createElement("span");
    label.className = "md-image-placeholder";
    label.textContent = img.alt || "Image reference";
    img.replaceWith(label);
  }
  for (const table of root.querySelectorAll("table")) {
    const wrapper = document.createElement("div");
    wrapper.className = "md-table-scroll";
    wrapper.tabIndex = 0;
    wrapper.setAttribute("role", "region");
    wrapper.setAttribute("aria-label", "Scrollable table");
    table.replaceWith(wrapper);
    wrapper.append(table);
  }
  for (const pre of root.querySelectorAll("pre")) {
    const code = pre.querySelector("code");
    if (!code) continue;
    const original = code.textContent || "";
    const language = (code.className.match(/(?:^|\s)language-([\w+-]+)/) || [])[1] || "";
    if (language && hljs.getLanguage(language)) {
      try {
        const output = hljs.highlight(original, { language, ignoreIllegals: true }).value;
        code.innerHTML = sanitise(output);
        code.classList.add("hljs");
      } catch {
        code.textContent = original;
      }
    }
    const block = document.createElement("div");
    block.className = "md-code-block";
    const toolbar = document.createElement("div");
    toolbar.className = "md-code-toolbar";
    const title = document.createElement("span");
    title.textContent = language || "Code";
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "md-copy-code";
    copy.textContent = "Copy";
    copy.setAttribute("aria-label", "Copy code block");
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(original);
        copy.textContent = "Copied";
      } catch {
        copy.textContent = "Copy unavailable";
      }
    });
    toolbar.append(title, copy);
    pre.replaceWith(block);
    block.append(toolbar, pre);
  }
}
export function renderMarkdown(element, content, { streaming = false } = {}) {
  if (!element) return;
  const source = String(content || "").replace(/\r\n?/g, "\n").slice(0, 90_000);
  if (element.__mdFrame) {
    cancelAnimationFrame(element.__mdFrame);
    element.__mdFrame = null;
  }
  const commit = () => {
    element.__mdFrame = null;
    if (!element.isConnected) return;
    if (!source.trim()) { element.textContent = ""; return; }
    try {
      element.innerHTML = sanitise(marked.parse(source));
      element.classList.add("markdown-body");
      enhance(element);
    } catch (error) {
      element.textContent = source;
      console.warn("Could not format model text", error);
    }
  };
  if (streaming) element.__mdFrame = requestAnimationFrame(commit);
  else commit();
}
