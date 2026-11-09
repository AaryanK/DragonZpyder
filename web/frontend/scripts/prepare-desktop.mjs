/**
 * Produce Windows/desktop-friendly install assets without platform-specific
 * binaries or image toolchains. Called after Vite and React prerender.
 * We intentionally do NOT install a service worker: authenticated chat, voice
 * and tool traffic must never be silently cached.
 */
import { deflateSync } from "node:zlib";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync, writeFileSync } from "node:fs";

const dist = resolve(dirname(fileURLToPath(import.meta.url)), "../../dist");

function chunk(name, content) {
  const kind = Buffer.from(name, "ascii");
  const raw = Buffer.concat([kind, content]);
  let crc = 0xffffffff;
  for (const byte of raw) {
    crc ^= byte;
    for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  const size = Buffer.alloc(4); size.writeUInt32BE(content.length);
  const checksum = Buffer.alloc(4); checksum.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
  return Buffer.concat([size, raw, checksum]);
}
function iconPng(n) {
  const rgba = Buffer.alloc(n * n * 4);
  function pixel(x, y, r, g, b, a = 255) {
    x = Math.round(x); y = Math.round(y);
    if (x < 0 || x >= n || y < 0 || y >= n) return;
    const p = (y * n + x) * 4;
    rgba[p] = r; rgba[p + 1] = g; rgba[p + 2] = b; rgba[p + 3] = a;
  }
  // Dark, rounded-square plate.
  const rad = 0.195 * n;
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    const margin = 0.04 * n, right = n - margin;
    const cx = Math.max(margin + rad, Math.min(x, right - rad));
    const cy = Math.max(margin + rad, Math.min(y, right - rad));
    if ((x - cx) ** 2 + (y - cy) ** 2 <= rad ** 2) pixel(x, y, 29, 27, 29);
  }
  const drawLine = (ax, ay, bx, by, width, color) => {
    [ax, ay, bx, by, width] = [ax, ay, bx, by, width].map(v => v * n);
    const l2 = (bx-ax)**2 + (by-ay)**2 || 1;
    const xmin = Math.max(0, Math.floor(Math.min(ax,bx)-width));
    const xmax = Math.min(n-1, Math.ceil(Math.max(ax,bx)+width));
    const ymin = Math.max(0, Math.floor(Math.min(ay,by)-width));
    const ymax = Math.min(n-1, Math.ceil(Math.max(ay,by)+width));
    for(let y=ymin;y<=ymax;y++)for(let x=xmin;x<=xmax;x++){
      const t=Math.max(0,Math.min(1,((x-ax)*(bx-ax)+(y-ay)*(by-ay))/l2));
      if((x-ax-t*(bx-ax))**2+(y-ay-t*(by-ay))**2 <= (width/2)**2)
        pixel(x,y,...color);
    }
  };
  const ellipse = (cx, cy, rx, ry, color) => {
    const [x0,x1,y0,y1] = [Math.floor((cx-rx)*n),Math.ceil((cx+rx)*n),
      Math.floor((cy-ry)*n),Math.ceil((cy+ry)*n)];
    for(let y=Math.max(0,y0);y<Math.min(n,y1);y++)for(let x=Math.max(0,x0);x<Math.min(n,x1);x++){
      if(((x/n-cx)/rx)**2+((y/n-cy)/ry)**2<=1)pixel(x,y,...color);
    }
  };
  const ember=[255,100,33], highlight=[255,151,65];
  // Four articulated legs on each side, deliberately within safe icon bounds.
  const legs=[
    [[.45,.38],[.32,.28],[.23,.23]],
    [[.43,.46],[.29,.39],[.19,.39]],
    [[.43,.54],[.29,.61],[.19,.62]],
    [[.46,.62],[.33,.73],[.24,.79]],
  ];
  for (const mirror of [false,true]) for (const chain of legs) {
    const pt = p => [mirror ? 1-p[0]:p[0], p[1]];
    const a=pt(chain[0]),b=pt(chain[1]),c=pt(chain[2]);
    drawLine(...a,...b,.025,ember);
    drawLine(...b,...c,.023,ember);
  }
  ellipse(.5,.53,.093,.155,ember);
  ellipse(.5,.35,.063,.071,highlight);
  ellipse(.5,.55,.04,.096,[31,27,29]);
  drawLine(.5,.4,.5,.48,.023,highlight);
  const ihdr=Buffer.alloc(13);ihdr.writeUInt32BE(n,0);ihdr.writeUInt32BE(n,4);ihdr[8]=8;ihdr[9]=6;
  const scanlines=Buffer.alloc(n*(1+4*n));
  for(let y=0;y<n;y++)rgba.copy(scanlines,y*(1+4*n)+1,y*4*n,(y+1)*4*n);
  return Buffer.concat([
    Buffer.from([137,80,78,71,13,10,26,10]),
    chunk("IHDR",ihdr),chunk("IDAT",deflateSync(scanlines,{level:9})),chunk("IEND",Buffer.alloc(0))
  ]);
}
mkdirSync(dist, {recursive:true});
for (const size of [192,512]) writeFileSync(resolve(dist, "app-icon-"+size+".png"),iconPng(size));
const manifest={
  id:"/app",name:"DragonZpyder Personal AI",short_name:"DragonZpyder",
  description:"A focused, permissioned AI workspace for conversations, tools and voice.",
  start_url:"/app",scope:"/app",display:"standalone",
  background_color:"#faf9f7",theme_color:"#faf9f7",
  categories:["productivity","utilities"],
  icons:[
    {src:"/app-icon-192.png",sizes:"192x192",type:"image/png",purpose:"any maskable"},
    {src:"/app-icon-512.png",sizes:"512x512",type:"image/png",purpose:"any maskable"}
  ]
};
writeFileSync(resolve(dist,"app.webmanifest"),JSON.stringify(manifest,null,2)+"\n");
console.log("DragonZpyder Windows-compatible desktop install assets generated.");
