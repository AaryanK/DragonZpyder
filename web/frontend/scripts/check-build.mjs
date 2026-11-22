import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

const dist = resolve(import.meta.dirname, "../../dist");
for (const page of ["index", "app", "account", "admin"]) {
  const html = readFileSync(resolve(dist, page + ".html"), "utf8");
  assert.match(html, /id="(?:root|admin-root)"/, page + ": missing React root");
  assert.match(html, /assets\//, page + ": no compiled React entry");
  assert.doesNotMatch(html, /<script[^>]+src="\/(?:app|account|mesh|home|dictation|companion)\.js"/,
    page + ": legacy modules executed before React mount");
  if (page !== "admin") assert.ok(html.match(/id="root"[\s\S]{500,}/), page + ": no React prerender");
}
const home = readFileSync(resolve(dist, "index.html"), "utf8");
const app = readFileSync(resolve(dist, "app.html"), "utf8");
const account = readFileSync(resolve(dist, "account.html"), "utf8");
const manifest = JSON.parse(readFileSync(resolve(dist, "app.webmanifest"), "utf8"));
assert.equal(manifest.start_url, "/app");
assert.equal(manifest.scope, "/", "Standalone account navigation must remain inside app scope");
assert.equal(manifest.display, "standalone");
assert.equal(manifest.id, "/app");
assert.ok(manifest.icons.some(icon => icon.src === "/app-icon-192.png"));
assert.ok(manifest.icons.some(icon => icon.src === "/app-icon-512.png"));
for (const file of ["app-icon-180.png", "app-icon-192.png", "app-icon-512.png"]) {
  assert.ok(readFileSync(resolve(dist, file)).length > 100, file + ": generated icon unavailable");
}
for (const [page, html] of [["home", home], ["app", app], ["account", account]]) {
  assert.match(html, /apple-mobile-web-app-capable/, page + ": missing Safari standalone metadata");
  assert.match(html, /apple-touch-icon[^>]+app-icon-180\.png/, page + ": missing Apple touch icon");
  assert.match(html, /rel="manifest" href="\/app\.webmanifest"/, page + ": missing PWA manifest");
}
assert.match(home, /Make progress|best of AI|All that intelligence/i);
assert.match(home, /runtime-dot/);
assert.match(home, /href="\/app"/, "Marketing CTA must link to the canonical React page");
for (const [name, markup] of [["home", home], ["app", app], ["account", account]]) {
  assert.doesNotMatch(markup, /href="\/(?:app|account)\.html(?:[?"#])/,
    name + ": found old static-template navigation");
}
assert.match(app, /id="composer"/);
for (const section of ["workspace-switcher", "conversation-search", "workspace-breadcrumb", "welcome-section-title"]) {
  assert.ok(app.includes('class="' + section + '"') || app.includes('id="' + section + '"'),
    "Redesigned Personal workspace missing: " + section);
}
assert.match(app, /workspace\.css/, "Personal workspace stylesheet missing");
assert.match(app, /ui-v1\.css/, "UI 1.0 design-system stylesheet missing");
const ui=readFileSync(resolve(dist,"ui-v1.css"),"utf8");
assert.match(ui,/dz-sidebar-collapsed/, "Desktop sidebar styling missing");
assert.match(ui,/dz-confirm-panel/, "Attachment confirmation styling missing");
assert.match(app, /data-workspace-theme="light"/, "Quiet workspace appearance should be the default");
assert.match(app, /id="workspace-theme-toggle"/, "Dark/light theme control missing");
assert.match(app, /id="camera-capture-toggle"/, "Camera capture control must be present");
for (const [id, description] of [
  ["dz-add-toggle", "progressive attachment menu"],
  ["dz-add-menu", "hidden attachment options"],
  ["dz-workspace-trigger", "workspace drawer"],
  ["dz-command-trigger", "command shortcut trigger"],
  ["screen-capture-toggle", "local screen capture"],
]) {
  assert.ok(app.includes('id="' + id + '"'), "Missing " + description);
}
assert.equal((app.match(/id="mesh-upload"/g) || []).length, 1,
  "The existing Mesh uploader must be reused rather than duplicated");
assert.equal((app.match(/id="mesh-file-label"/g) || []).length, 1,
  "Attachment input label must remain unique");
assert.equal((app.match(/id="camera-capture-toggle"/g) || []).length, 1,
  "Camera button must remain available only through the input menu");

assert.match(app, /id="mesh-model"/, "Model selection must remain connected");

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
const admin = readFileSync(resolve(dist, "admin.html"), "utf8");
assert.match(admin, /noindex,nofollow/);
assert.match(admin, /admin-root/);
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
console.log("React pages, Apple home-screen assets, PWA scope, and controller IDs verified");
