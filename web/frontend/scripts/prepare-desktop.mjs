/**
 * Generate DragonZpyder icons from the local SVG master.
 * Operly retains its independently pinned image. No offline service worker.
 */
import { createHash } from "node:crypto";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync, writeFileSync, copyFileSync, readFileSync } from "node:fs";
import { PNG } from "pngjs";

const dist = resolve(dirname(fileURLToPath(import.meta.url)), "../../dist");
const commit = "76009b2b88c46ae2e9e1d0cb543345a19f2ef71c";
const base = "https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/"+commit+"/";
const assets = [
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
// Constrained vector master: straight polygon subpaths, even-odd holes, solid fill.
const master = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "../src/dz-mark.svg"), "utf8");
const fill = master.match(/fill="#([0-9a-fA-F]{6})"/)?.[1];
const paths = [...master.matchAll(/<path\s+[^>]*?\bd="([^"]+)"/g)].map(match => {
  if (!/^[MLZ0-9. -]+$/.test(match[1])) throw Error("Unsupported DZ vector command");
  return [...match[1].matchAll(/M\s+([^Z]+)Z/g)].map(part => {
    const n = part[1].match(/-?\d+(?:\.\d+)?/g)?.map(Number) || [];
    if(n.length < 6 || n.length % 2) throw Error("Invalid DZ polygon");
    return Array.from({length:n.length/2},(_,i)=>[n[i*2],n[i*2+1]]);
  });
});
if (!fill || paths.length !== 2 || paths[0].length !== 2 || paths[1].length !== 1) throw Error("Invalid DZ master");
const rgb = [0,2,4].map(i=>parseInt(fill.slice(i,i+2),16));
function contains(poly,x,y) {
  let inside=false;
  for(let i=0,j=poly.length-1;i<poly.length;j=i++){
    const [a,b]=poly[i], [c,d]=poly[j];
    if((b>y)!==(d>y) && x<(c-a)*(y-b)/(d-b)+a) inside=!inside;
  }
  return inside;
}
function monogramPng(size, opaque=false) {
  const out = new PNG({width:size,height:size,colorType:6});
  const samples=4;
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    let count=0;
    for(let dy=0;dy<samples;dy++)for(let dx=0;dx<samples;dx++){
      const px=(x+(dx+.5)/samples)*64/size, py=(y+(dy+.5)/samples)*64/size;
      if(paths.some(polys=>polys.reduce((inside,poly)=>inside!==contains(poly,px,py),false)))count++;
    }
    const alpha=count/(samples*samples), i=(y*size+x)*4;
    for(let c=0;c<3;c++)out.data[i+c]=opaque?Math.round(rgb[c]*alpha+[20,20,21][c]*(1-alpha)):rgb[c];
    out.data[i+3]=opaque?255:Math.round(255*alpha);
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
writeFileSync(resolve(dist,"dz-mark.svg"),master);
writeFileSync(resolve(dist,"brand-icon.png"),monogramPng(128));
writeFileSync(resolve(dist,"brand-logo.png"),monogramPng(512));
for(const size of [16,32])writeFileSync(resolve(dist,"favicon-"+size+".png"),monogramPng(size));
for(const size of [192,512])writeFileSync(resolve(dist,"app-icon-"+size+".png"),monogramPng(size,true));
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
console.log("Generated local DZ vector and raster sizes; verified pinned Operly asset.");
