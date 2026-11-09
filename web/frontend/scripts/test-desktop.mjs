import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../dist");

test("Windows browser-install assets are generated with valid PNG dimensions", () => {
  const manifest = JSON.parse(readFileSync(resolve(root, "app.webmanifest"), "utf8"));
  assert.equal(manifest.start_url, "/app");
  assert.equal(manifest.scope, "/app");
  assert.equal(manifest.id, "/app");
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.icons.length, 2);
  const expected = [192, 512];
  for (const size of expected) {
    const name = "app-icon-"+size+".png";
    const png = readFileSync(resolve(root, name));
    assert.deepEqual(Array.from(png.subarray(0,8)), [137,80,78,71,13,10,26,10], name+" signature");
    assert.equal(png.readUInt32BE(16), size, name+" width");
    assert.equal(png.readUInt32BE(20), size, name+" height");
    assert.ok(png.length > 1000, name+" appears empty");
    assert.ok(manifest.icons.some(icon => icon.src === "/"+name
      && icon.sizes === size+"x"+size && icon.type === "image/png"));
  }
});

test("Personal app advertises the manifest without caching privileged chat", () => {
  const app = readFileSync(resolve(root, "app.html"), "utf8");
  assert.match(app, /rel="manifest" href="\/app\.webmanifest"/);
  assert.match(app, /name="application-name" content="DragonZpyder"/);
  assert.doesNotMatch(app, /navigator\\.serviceWorker\\.register/);
});
