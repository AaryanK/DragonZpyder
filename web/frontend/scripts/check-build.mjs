import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

const dist = resolve(import.meta.dirname, "../../dist");
for (const page of ["index", "app", "account"]) {
  const html = readFileSync(resolve(dist, page + ".html"), "utf8");
  assert.match(html, /id="root"/, page + ": missing React root");
  assert.match(html, /assets\//, page + ": no compiled React entry");
  assert.doesNotMatch(html, /<script[^>]+src="\/(?:app|account|mesh|home|dictation|companion)\.js"/,
    page + ": legacy modules executed before React hydration");
}
const app = readFileSync(resolve(dist, "app.html"), "utf8");
const account = readFileSync(resolve(dist, "account.html"), "utf8");
assert.match(app, /id="composer"/);
assert.match(app, /id="auth-modal"/);
assert.match(app, /id="mesh-switch"/);
assert.match(account, /id="login-form"/);
assert.match(account, /id="mode-tabs"/);
assert.ok(readdirSync(resolve(dist, "assets")).some(name => name.endsWith(".js")));
console.log("React/Vite output and preserved template contracts verified");
