/**
 * Build authentic brand assets directly from the published DragonZpyder-Landing
 * repository, pinned to a reviewed commit and checked against Git blob hashes.
 *
 * No generated replacement spider/logo, and no offline service worker.
 * The exact same brand assets are served by FastAPI after the Vite build.
 */
import { createHash } from "node:crypto";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync, writeFileSync, copyFileSync } from "node:fs";
import { PNG } from "pngjs";

const dist = resolve(dirname(fileURLToPath(import.meta.url)), "../../dist");
const commit = "76009b2b88c46ae2e9e1d0cb543345a19f2ef71c";
const base = "https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/"+commit+"/";
const assets = [
  { name: "favicon.png", dest: "brand-icon.png", sha: "0c0c18b561ea8ed2dcfc57328d62e6bba69d247d", maxBytes: 700_000 },
  { name: "logo.png", dest: "brand-logo.png", sha: "507747470707d1d2b821ea91538c14125f3ea257", maxBytes: 3_000_000 },
  { name: "operly_logo.png", dest: "brand-operly.png", sha: "46d62298df18aecc16aac9caf4e17475d080db5d", maxBytes: 2_000_000 },
];
const PNG_SIGNATURE = Buffer.from([137,80,78,71,13,10,26,10]);
async function download(asset) {
  const url = base + asset.name;
  let lastError;
  for (let attempt=0;attempt<3;attempt++) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(20_000) });
      if (!response.ok) throw new Error("HTTP "+response.status+" for "+asset.name);
      const bytes = Buffer.from(await response.arrayBuffer());
      if (bytes.length < 100 || bytes.length > asset.maxBytes) throw new Error("Unexpected image size for "+asset.name);
      if (!bytes.subarray(0,8).equals(PNG_SIGNATURE)) throw new Error("Not a PNG: "+asset.name);
      const gitBlobHash = createHash("sha1").update(Buffer.from("blob "+bytes.length+"\0")).update(bytes).digest("hex");
      if (gitBlobHash !== asset.sha) throw new Error("Official "+asset.name+" hash differs from pinned brand source");
      return bytes;
    } catch (err) {
      lastError = err;
      if (attempt < 2) await new Promise(done => setTimeout(done,(attempt+1)*500));
    }
  }
  throw lastError;
}
function resizedPng(bytes, size) {
  const source = PNG.sync.read(bytes);
  if (!(source.width>0 && source.height>0) || source.width>4096 || source.height>4096) {
    throw new Error("Unsupported official favicon dimensions");
  }
  // Preserve aspect ratio on a transparent square background; do not crop the logo.
  const out = new PNG({ width:size, height:size, colorType:6 });
  out.data.fill(0);
  const factor = Math.min(size/source.width,size/source.height);
  const width = Math.round(source.width*factor), height=Math.round(source.height*factor);
  const xoff=Math.floor((size-width)/2),yoff=Math.floor((size-height)/2);
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const srcX=Math.min(source.width-1,Math.floor((x+0.5)*source.width/width));
    const srcY=Math.min(source.height-1,Math.floor((y+0.5)*source.height/height));
    const src=(srcY*source.width+srcX)*4;
    const dst=((y+yoff)*size+x+xoff)*4;
    for(let c=0;c<4;c++)out.data[dst+c]=source.data[src+c];
  }
  return PNG.sync.write(out);
}
mkdirSync(dist,{recursive:true});
/* Vite's publicDir is disabled for safety. Copy only allowlisted presentation
 * files into the preview build for automated browser tests and local review.
 * Never expose arbitrary Python backend files or .env secrets. */
const appRoot=resolve(dist,"..");
for (const name of ["app.css","mesh.css","workspace.css","ui-v1.css","account.css"]) {
  copyFileSync(resolve(appRoot,name),resolve(dist,name));
}
const data = await Promise.all(assets.map(download));
for(let i=0;i<assets.length;i++) writeFileSync(resolve(dist,assets[i].dest),data[i]);
const favicon=data[0];
for(const size of [192,512])writeFileSync(resolve(dist,"app-icon-"+size+".png"),resizedPng(favicon,size));
const manifest = {
  id:"/app",name:"DragonZpyder Personal AI",short_name:"DragonZpyder",
  description:"Your DragonZpyder workspace for conversations, tools and voice.",
  start_url:"/app",scope:"/app",display:"standalone",
  background_color:"#faf9f7",theme_color:"#faf9f7",
  categories:["productivity","utilities"],
  icons:[
    {src:"/app-icon-192.png",sizes:"192x192",type:"image/png",purpose:"any"},
    {src:"/app-icon-512.png",sizes:"512x512",type:"image/png",purpose:"any"},
  ]
};
writeFileSync(resolve(dist,"app.webmanifest"),JSON.stringify(manifest,null,2)+"\n");
console.log("Verified official DragonZpyder and Operly logos and Windows install icons.");
