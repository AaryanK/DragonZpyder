import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><div id='answer'></div>", { url: "https://dragonzpyder.xyz/app" });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { configurable: true, value: dom.window.navigator });
globalThis.requestAnimationFrame = fn => { fn(); return 1; };
globalThis.cancelAnimationFrame = () => {};
const { renderMarkdown } = await import("../src/markdown.js");
const root = document.querySelector("#answer");
function render(markdown) { renderMarkdown(root, markdown); return root; }

test("renders GFM headings, lists, emphasis, strike and tables", () => {
  render("# Plan\n\n- **Prepare** the draft\n- ~~Old~~ New\n\n| Item | Cost |\n| --- | ---: |\n| Model | $2 |");
  assert.equal(root.querySelector("h1")?.textContent, "Plan");
  assert.equal(root.querySelector("strong")?.textContent, "Prepare");
  assert.equal(root.querySelector("del")?.textContent, "Old");
  assert.equal(root.querySelectorAll("li").length, 2);
  assert.equal(root.querySelectorAll(".md-table-scroll table tr").length, 2);
  assert.equal(root.querySelector("td")?.textContent, "Model");
});

test("highlights fenced code and creates a copy action", async () => {
  render("```python\nprint('hello')\n```");
  assert.ok(root.querySelector(".md-code-block code.hljs"));
  assert.equal(root.querySelector(".md-code-toolbar span")?.textContent, "python");
  assert.equal(root.querySelector(".md-copy-code")?.textContent, "Copy");
  const copied = [];
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: {
    writeText: async txt => copied.push(txt)
  }});
  root.querySelector(".md-copy-code").click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(copied[0], "print('hello')\n");
});

test("removes unsafe HTML and click/URL injection", () => {
  render('<img src=x onerror="alert(1)"> <script>alert(1)</script> <svg onload="alert(1)"></svg>\n\n[unsafe](javascript:alert(1)) [safe](https://example.org/path)');
  assert.equal(root.querySelector("script,iframe,svg,img"), null);
  assert.equal(root.querySelector("[onerror],[onload]"), null);
  assert.equal(root.querySelector('a[href^="javascript:"]'), null);
  const good = [...root.querySelectorAll("a")].find(a => a.textContent === "safe");
  assert.ok(good);
  assert.equal(good.target, "_blank");
  assert.ok(good.rel.includes("noopener"));
});

test("does not trust model embedded HTML or external inline images", () => {
  render("**Hello** <button type='button' onclick='bad()'>Run</button>\n\n![remote](https://example.com/x.png)");
  assert.equal(root.querySelector("button"), null);
  assert.equal(root.querySelector("img"), null);
  assert.ok(root.querySelector(".md-image-placeholder"));
  assert.match(root.textContent, /Hello/);
});

test("renders blockquotes, links and nested lists", () => {
  render("> Quoted advice\n\n1. Alpha\n   - Child\n2. Beta\n\n[Documentation](https://docs.python.org)");
  assert.ok(root.querySelector("blockquote"));
  assert.ok(root.querySelector("ol ul"));
  assert.equal(root.querySelector("a")?.getAttribute("href"), "https://docs.python.org");
});

test("handles partial streaming code without breaking sanitization", () => {
  renderMarkdown(root, "```js\nconsole.log('streaming')", { streaming: true });
  renderMarkdown(root, "```js\nconsole.log('streaming')\n```");
  assert.equal(root.querySelectorAll(".md-code-block").length, 1);
  assert.equal(root.querySelector("code")?.textContent, "console.log('streaming')\n");
});
