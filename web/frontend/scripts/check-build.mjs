import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

const dist = resolve(import.meta.dirname, "../../dist");
for (const page of ["index", "app", "account", "admin"]) {
  const html = readFileSync(resolve(dist, page + ".html"), "utf8");
  assert.match(html, /id="root"/, page + ": missing React root");
  assert.match(html, /assets\//, page + ": no compiled React entry");
  assert.doesNotMatch(html, /<script[^>]+src="\/(?:app|account|mesh|home|dictation|companion)\.js"/,
    page + ": legacy modules executed before React mount");
  assert.ok(html.match(/id="root"[\s\S]{500,}/), page + ": no React prerender");
}
const home = readFileSync(resolve(dist, "index.html"), "utf8");
const app = readFileSync(resolve(dist, "app.html"), "utf8");
const account = readFileSync(resolve(dist, "account.html"), "utf8");
const admin = readFileSync(resolve(dist, "admin.html"), "utf8");
assert.match(admin, /Model operations/);
assert.match(admin, /Inference Observatory/);
assert.match(home, /Make progress|best of AI|All that intelligence/i);
assert.match(home, /runtime-dot/);
assert.match(home, /href="\/app"/, "Marketing CTA must link to the canonical React page");
for (const [name, markup] of [["home", home], ["app", app], ["account", account]]) {
  assert.doesNotMatch(markup, /href="\/(?:app|account)\.html(?:[?"#])/,
    name + ": found old static-template navigation");
}
assert.match(app, /id="composer"/);
assert.equal((app.match(/id="companion-open"/g) || []).length, 1,
  "Live voice should have exactly one launch button");
const voice = app.indexOf('id="companion-open"');
const mic = app.indexOf('id="dictation-toggle"');
const send = app.indexOf('id="send-button"');
assert.ok(mic !== -1 && mic < voice && voice < send,
  "Composer action order must be microphone, Live voice, then conditional Send");
assert.match(app, /id="send-button"[^>]*hidden/,
  "Send starts hidden until the composer has something to send");

assert.match(account, /id="login-form"/);
assert.match(home, /runtime-text/);
for (const id of ["composer","auth-modal","mesh-switch","conversation-list",
                   "companion-open","dictation-toggle","message-input"]) {
  assert.ok(app.includes('id="' + id + '"'), "Lost Personal UI element: " + id);
}
for (const id of ["login-form","mode-tabs","signup-panel","reset-panel",
                   "linked-identities","profile-panel"]) {
  assert.ok(account.includes('id="' + id + '"'), "Lost account UI element: " + id);
}
assert.ok(readdirSync(resolve(dist, "assets")).some(name => name.endsWith(".js")));
console.log("React JSX pages, prerendered SEO, legacy controller IDs and styles verified");
