import { PNG } from "pngjs";
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
  for(const brand of ["brand-icon.png","brand-logo.png","brand-operly.png"]) {
    const png=readFileSync(resolve(root,brand));
    assert.deepEqual(Array.from(png.subarray(0,8)),[137,80,78,71,13,10,26,10], brand+" is not PNG");
    assert.ok(png.length>100, brand+" missing image bytes");
    if (brand === "brand-operly.png") assert.ok(png.length>50000, "missing pinned Operly asset");
  }
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

test("local DZ vector produces transparent small rasters and opaque install icons", () => {
  assert.match(readFileSync(resolve(root,"dz-mark.svg"),"utf8"), /viewBox="0 0 64 64"/);
  for(const size of [16,32]){
    const {width,height,data}=PNG.sync.read(readFileSync(resolve(root,"favicon-"+size+".png")));
    assert.equal(width,size);assert.equal(height,size);assert.equal(data[3],0);
    assert.ok(data.some((v,i)=>i%4===3&&v>200));
  }
  for(const size of [192,512]){
    const {data}=PNG.sync.read(readFileSync(resolve(root,"app-icon-"+size+".png")));
    assert.equal(data[3],255);assert.ok(data.some((v,i)=>i%4===0&&v>180));
  }
});
