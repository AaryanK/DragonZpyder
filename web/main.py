"""Python FastAPI gateway serving compiled, React-owned pages and API routes."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from backend.voice import realtime
from backend.mesh import mesh
from backend.security import OPERLY

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"  # Vite-built React pages and fingerprinted assets
API = os.getenv("DRAGONZPYDER_API_ORIGIN", "https://api.dragonzpyder.xyz").rstrip("/")
STATIC = {
    "/", "/index.html", "/app.html", "/account.html", "/account.css",
    "/account.js", "/app.css", "/app.js", "/companion.js", "/dictation.js",
    "/mesh.js", "/mesh.css", "/chat.html", "/privacy.html",
    "/terms.html", "/robots.txt", "/sitemap.xml", "/script.js",
}
HOP_HEADERS = {"connection", "transfer-encoding", "content-length", "host",
               "content-encoding", "keep-alive", "upgrade", "proxy-connection"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(follow_redirects=False, timeout=120.0) as http:
        app.state.http = http
        yield


app = FastAPI(title="DragonZpyder Web", docs_url=None, redoc_url=None,
              openapi_url=None, lifespan=lifespan)


@app.middleware("http")
async def secure_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    return response


async def proxy(request: Request, destination: str, rewrite_origin=False):
    # Fixed trusted service origins; never proxy to a host provided by the browser.
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}
    if rewrite_origin:
        headers["origin"] = destination
        headers["referer"] = destination + "/"
    body = await request.body()
    try:
        upstream = await request.app.state.http.request(
            request.method, destination + request.url.path +
            ("?" + request.url.query if request.url.query else ""),
            headers=headers, content=body)
    except httpx.HTTPError:
        return JSONResponse({"detail": {"code": "UPSTREAM_UNREACHABLE",
                                        "message": "DragonZpyder could not reach the upstream service.",
                                        "retryable": True}}, status_code=502)
    response_headers = [(k.encode(), v.encode()) for k, v in upstream.headers.multi_items()
                        if k.lower() not in HOP_HEADERS and k.lower() != "set-cookie"]
    response = Response(content=upstream.content, status_code=upstream.status_code,
                        headers=dict((k.decode(), v.decode()) for k, v in response_headers))
    # Headers must retain repeated Set-Cookie values for secure sessions.
    for cookie in upstream.headers.get_list("set-cookie"):
        response.raw_headers.append((b"set-cookie", cookie.encode()))
    return response


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "dragonzpyder-web"}


@app.api_route("/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def dispatch(path: str, request: Request):
    route = "/" + path
    if route.startswith("/api/"):
        return await proxy(request, OPERLY, rewrite_origin=True)
    if route.startswith("/internal/v1/"):
        return await proxy(request, API)
    if route == "/companion/realtime":
        return await realtime(request)
    if route.startswith("/mesh/"):
        return await mesh(request)
    file_route = "/index.html" if route == "/" else route
    if request.method in ("GET", "HEAD") and route.startswith("/assets/"):
        # Only serve hashed assets emitted by Vite, never arbitrary files.
        assets = (DIST / "assets").resolve()
        target = (DIST / route.lstrip("/")).resolve()
        if target.is_relative_to(assets) and target.is_file():
            return FileResponse(target, headers={"cache-control": "public, max-age=31536000, immutable"})
    if request.method in ("GET", "HEAD") and file_route in STATIC:
        if file_route in ("/index.html", "/app.html", "/account.html"):
            target = DIST / file_route.lstrip("/")
            if not target.is_file():
                return JSONResponse({"detail": {"code": "FRONTEND_UNAVAILABLE",
                                               "message": "React build is unavailable."}},
                                    status_code=503, headers={"cache-control": "no-store"})
        else:
            target = ROOT / file_route.lstrip("/")
        if target.is_file():
            media_types = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
                           ".xml": "application/xml", ".txt": "text/plain"}
            return FileResponse(target, media_type=media_types.get(target.suffix),
                                headers={"cache-control": "no-store" if target.suffix in
                                         (".html", ".js", ".css") else "public, max-age=300"})
    return JSONResponse({"detail": {"code": "NOT_FOUND", "message": "Page not found."}}, status_code=404)
