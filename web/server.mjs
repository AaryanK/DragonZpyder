import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
const port = Number(process.env.PORT || 3000);
const upstreamOrigin = String(process.env.OPERLY_ORIGIN || "https://operly.dragonzpyder.xyz").replace(/\/+$/, "");

const publicFiles = new Set([
  "/",
  "/index.html",
  "/app.html",
  "/app.css",
  "/app.js",
  "/home.js",
  "/chat.html",
  "/privacy.html",
  "/terms.html",
  "/robots.txt",
  "/sitemap.xml",
  "/script.js",
]);

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".xml": "application/xml; charset=utf-8",
};

function sendJson(res, status, body) {
  const payload = Buffer.from(JSON.stringify(body));
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": payload.length,
    "cache-control": "no-store",
  });
  res.end(payload);
}

function normalizedProxyHeaders(req) {
  const headers = new Headers();
  for (const [name, value] of Object.entries(req.headers)) {
    if (value == null) continue;
    if (Array.isArray(value)) {
      for (const item of value) headers.append(name, item);
    } else {
      headers.set(name, value);
    }
  }
  for (const name of ["host", "connection", "content-length", "transfer-encoding"]) headers.delete(name);
  headers.set("origin", upstreamOrigin);
  headers.set("referer", `${upstreamOrigin}/`);
  return headers;
}

function copyProxyResponseHeaders(upstream, res) {
  for (const [name, value] of upstream.headers.entries()) {
    const lower = name.toLowerCase();
    if (["set-cookie", "content-length", "content-encoding", "transfer-encoding", "connection"].includes(lower)) continue;
    res.setHeader(name, value);
  }
  if (typeof upstream.headers.getSetCookie === "function") {
    const cookies = upstream.headers.getSetCookie();
    if (cookies.length) res.setHeader("set-cookie", cookies);
  } else {
    const cookie = upstream.headers.get("set-cookie");
    if (cookie) res.setHeader("set-cookie", cookie);
  }
}

async function proxyApi(req, res, url) {
  let target;
  try {
    target = new URL(`${url.pathname}${url.search}`, upstreamOrigin);
  } catch {
    sendJson(res, 500, { detail: { code: "UPSTREAM_CONFIGURATION_INVALID", message: "DragonZpyder API bridge is not configured." } });
    return;
  }

  const method = String(req.method || "GET").toUpperCase();
  const init = {
    method,
    headers: normalizedProxyHeaders(req),
    redirect: "manual",
  };
  if (!['GET', 'HEAD'].includes(method)) {
    init.body = req;
    init.duplex = "half";
  }

  try {
    const upstream = await fetch(target, init);
    copyProxyResponseHeaders(upstream, res);
    res.statusCode = upstream.status;
    if (method === "HEAD" || !upstream.body) {
      res.end();
      return;
    }
    const bytes = Buffer.from(await upstream.arrayBuffer());
    res.setHeader("content-length", bytes.length);
    res.end(bytes);
  } catch (error) {
    console.error("DragonZpyder Operly bridge failed", error);
    sendJson(res, 502, {
      detail: {
        code: "OPERLY_UNREACHABLE",
        message: "DragonZpyder could not reach its Operly runtime.",
        retryable: true,
      },
    });
  }
}

async function serveStatic(req, res, url) {
  const pathname = url.pathname === "/" ? "/index.html" : url.pathname;
  if (!publicFiles.has(url.pathname) && !publicFiles.has(pathname)) {
    sendJson(res, 404, { detail: { code: "NOT_FOUND", message: "Page not found." } });
    return;
  }

  const filename = join(root, pathname.slice(1));
  try {
    const info = await stat(filename);
    if (!info.isFile()) throw new Error("not-file");
    res.writeHead(200, {
      "content-type": contentTypes[extname(filename)] || "application/octet-stream",
      "content-length": info.size,
      "cache-control": pathname.endsWith(".html") ? "no-cache" : "public, max-age=300",
      "x-content-type-options": "nosniff",
      "referrer-policy": "strict-origin-when-cross-origin",
    });
    createReadStream(filename).pipe(res);
  } catch {
    sendJson(res, 404, { detail: { code: "NOT_FOUND", message: "Page not found." } });
  }
}

createServer(async (req, res) => {
  const url = new URL(req.url || "/", "http://dragonzpyder.local");
  if (url.pathname === "/healthz") {
    sendJson(res, 200, { status: "ok", service: "dragonzpyder-web" });
    return;
  }
  if (url.pathname.startsWith("/api/")) {
    await proxyApi(req, res, url);
    return;
  }
  await serveStatic(req, res, url);
}).listen(port, "0.0.0.0", () => {
  console.log(`DragonZpyder web listening on ${port}`);
});
