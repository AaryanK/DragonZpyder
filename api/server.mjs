// Standalone DragonZpyder API runtime. The personal website is not imported here.
import { createServer } from "node:http";
import { handleInternalInference } from "./inference.mjs";

const port = Number(process.env.PORT || 3000);
const maxConcurrent = Math.max(1, Math.min(128, Number(process.env.DRAGONZPYDER_API_CONCURRENCY) || 12));
let pending = 0;

export function serve(req, res) {
  const url = new URL(req.url || "/", "http://localhost");
  res.setHeader("x-content-type-options", "nosniff");
  res.setHeader("referrer-policy", "no-referrer");
  res.setHeader("access-control-allow-origin", "null"); // Never allow credentialed browser CORS.
  if (req.method === "GET" && url.pathname === "/healthz") {
    const configured = Boolean(process.env.DRAGONZPYDER_RUNTIME_TOKEN && process.env.OPENROUTER_API_KEY);
    res.writeHead(configured ? 200 : 503, {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    });
    res.end(JSON.stringify({ service: "dragonzpyder-api", status: configured ? "ready" : "unconfigured" }));
    return;
  }
  if (!url.pathname.startsWith("/internal/v1/") && !url.pathname.startsWith("/v1/")) {
    res.writeHead(404, {"content-type":"application/json; charset=utf-8"});
    res.end(JSON.stringify({error:{message:"Unknown DragonZpyder API route"}}));
    return;
  }
  if (pending >= maxConcurrent) {
    res.writeHead(503, {"content-type":"application/json; charset=utf-8","retry-after":"2"});
    res.end(JSON.stringify({error:{message:"API is busy; retry shortly"}}));
    return;
  }
  pending += 1;
  Promise.resolve(handleInternalInference(req,res,url)).catch(e=>{
    console.error("API request handler failed",e?.name||"error");
    if (!res.headersSent) res.writeHead(502, {"content-type":"application/json; charset=utf-8"});
    if(!res.writableEnded)res.end(JSON.stringify({error:{message:"Gateway unavailable"}}));
  }).finally(()=>{pending -= 1;});
}

if (process.env.NODE_ENV !== "test") {
  createServer(serve).listen(port, "0.0.0.0", () => console.log("DragonZpyder API service listening on port " + port));
}
