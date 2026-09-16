const DEFAULT_OPERLY_ORIGIN = "https://operly.dragonzpyder.xyz";

function upstreamOrigin() {
  return String(process.env.OPERLY_ORIGIN || DEFAULT_OPERLY_ORIGIN).replace(/\/+$/, "");
}

function copyRequestHeaders(req, upstream) {
  const headers = new Headers();
  for (const [name, value] of Object.entries(req.headers || {})) {
    if (value == null) continue;
    if (Array.isArray(value)) {
      for (const item of value) headers.append(name, String(item));
    } else {
      headers.set(name, String(value));
    }
  }

  headers.delete("host");
  headers.delete("content-length");
  headers.delete("connection");
  headers.set("origin", upstream);
  headers.set("referer", `${upstream}/`);
  return headers;
}

function copyResponseHeaders(upstreamResponse, res) {
  for (const [name, value] of upstreamResponse.headers.entries()) {
    const lower = name.toLowerCase();
    if (lower === "set-cookie" || lower === "content-length" || lower === "content-encoding") continue;
    res.setHeader(name, value);
  }

  const getSetCookie = upstreamResponse.headers.getSetCookie;
  if (typeof getSetCookie === "function") {
    const cookies = getSetCookie.call(upstreamResponse.headers);
    if (cookies.length) res.setHeader("set-cookie", cookies);
  } else {
    const cookie = upstreamResponse.headers.get("set-cookie");
    if (cookie) res.setHeader("set-cookie", cookie);
  }
}

export const config = { api: { bodyParser: false } };

export default async function handler(req, res) {
  const upstream = upstreamOrigin();
  const path = String(req.url || "/api/");
  if (!path.startsWith("/api/")) {
    res.status(404).json({ detail: { code: "NOT_FOUND", message: "API route not found." } });
    return;
  }

  let target;
  try {
    target = new URL(path, upstream);
  } catch {
    res.status(500).json({ detail: { code: "UPSTREAM_CONFIGURATION_INVALID", message: "DragonZpyder API bridge is not configured." } });
    return;
  }

  const method = String(req.method || "GET").toUpperCase();
  const init = { method, headers: copyRequestHeaders(req, upstream), redirect: "manual" };
  if (method !== "GET" && method !== "HEAD") {
    init.body = req;
    init.duplex = "half";
  }

  try {
    const upstreamResponse = await fetch(target, init);
    copyResponseHeaders(upstreamResponse, res);
    res.status(upstreamResponse.status);
    const payload = Buffer.from(await upstreamResponse.arrayBuffer());
    res.send(payload);
  } catch (error) {
    console.error("DragonZpyder Operly bridge failed", error);
    res.status(502).json({
      detail: {
        code: "OPERLY_UNREACHABLE",
        message: "DragonZpyder could not reach its Operly runtime.",
        retryable: true,
      },
    });
  }
}
