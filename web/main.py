"""Python FastAPI gateway serving compiled, React-owned pages and API routes."""
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse

from backend.voice import realtime
from backend.mesh import mesh
from backend.security import OPERLY
from backend.chat_demo import router as chat_router

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"  # Vite-built React pages and fingerprinted assets
API = os.getenv("DRAGONZPYDER_API_ORIGIN", "https://api.dragonzpyder.xyz").rstrip("/")
CHAT_HOST = "chat.dragonspire.xyz"
CHAT_PATHS = {"/chat", "/chat/app.js", "/chat/app.css", "/demo/session",
              "/demo/login", "/demo/logout", "/demo/chat", "/healthz"}
# Clean public URLs; Vite uses HTML entry filenames only as internal build artifacts.
PUBLIC_PAGES = {"/": "/index.html", "/app": "/app.html", "/account": "/account.html"}
LEGACY_PAGE_ROUTES = {"/app.html": "/app", "/account.html": "/account"}
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
    # A single Web deployment answers both the public site and the private
    # chat hostname. The latter exposes only its dedicated routes.
    host = (request.url.hostname or "").lower().rstrip(".")
    route = request.url.path
    is_chat = host == CHAT_HOST
    if is_chat and route in ("/", "/index.html"):
        return RedirectResponse("/chat", status_code=307)
    if is_chat and route not in CHAT_PATHS:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    # The chat demo is not a public API on the main marketing website.
    if (route == "/chat" or route.startswith("/chat/") or route.startswith("/demo/")) and (
        not is_chat and not host.endswith(".up.railway.app")
    ):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    response = await call_next(request)
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    if is_chat or route == "/chat" or route.startswith(("/chat/", "/demo/")):
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; form-action 'self'; "
            "base-uri 'none'; frame-ancestors 'none'"
        )
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



async def is_admin(request: Request) -> bool:
    """Check a signed-in Operly identity against the operator's explicit allowlist."""
    allowed = {entry.strip().casefold() for entry in
               os.getenv("DRAGONZPYDER_ADMIN_EMAILS", "").split(",") if entry.strip()}
    if not allowed:
        return False
    cookie = request.headers.get("cookie", "")
    if not cookie:
        return False
    try:
        response = await request.app.state.http.get(
            OPERLY + "/api/auth/me",
            headers={"cookie": cookie, "origin": OPERLY, "referer": OPERLY + "/"},
            timeout=10)
        if response.status_code != 200:
            return False
        account = response.json()
        email = account.get("email", "") if isinstance(account, dict) else ""
        return isinstance(email, str) and email.casefold() in allowed
    except (httpx.HTTPError, ValueError, TypeError):
        return False


async def admin_route(request: Request):
    if request.method != "GET":
        return JSONResponse({"detail": "Not found"}, status_code=404)
    if not await is_admin(request):
        return JSONResponse({"detail": "Administrator sign-in required"}, status_code=403,
                            headers={"cache-control": "no-store"})
    if request.url.path == "/admin":
        target = DIST / "admin.html"
        if not target.is_file():
            return JSONResponse({"detail": "Admin frontend not built"}, status_code=503)
        return FileResponse(target, media_type="text/html",
                            headers={"cache-control": "no-store", "x-frame-options": "DENY"})
    secret = os.getenv("DRAGONZPYDER_ADMIN_TOKEN", "")
    if len(secret) < 40:
        return JSONResponse({"detail": "Admin usage gateway is not configured"},
                            status_code=503)
    params = request.query_params
    # Narrowly copy validated filters; never construct target URLs from user input.
    days = params.get("days", "30")
    app = params.get("app", "")
    if not days.isdigit() or not 1 <= int(days) <= 90:
        return JSONResponse({"detail": "Invalid date range"}, status_code=400)
    if app and not re.fullmatch(r"[a-z0-9_-]{2,60}", app):
        return JSONResponse({"detail": "Invalid app filter"}, status_code=400)
    try:
        upstream = await request.app.state.http.get(
            API + "/internal/admin/usage",
            params={"days": days, **({"app": app} if app else {})},
            headers={"authorization": "Bearer " + secret}, timeout=20)
    except httpx.HTTPError:
        return JSONResponse({"detail": "Usage data service unavailable"}, status_code=502)
    return Response(content=upstream.content, status_code=upstream.status_code,
                    media_type="application/json", headers={"cache-control": "no-store"})

app.include_router(chat_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "dragonzpyder-web"}


@app.api_route("/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def dispatch(path: str, request: Request):
    route = "/" + path
    if route == "/admin" or route == "/admin/api/usage":
        return await admin_route(request)
    if route.startswith("/api/"):
        return await proxy(request, OPERLY, rewrite_origin=True)
    if route.startswith("/internal/v1/"):
        return await proxy(request, API)
    if route == "/companion/realtime":
        return await realtime(request)
    if route.startswith("/mesh/"):
        return await mesh(request)
    if request.method in ("GET", "HEAD") and route in LEGACY_PAGE_ROUTES:
        query = ("?" + request.url.query) if request.url.query else ""
        return RedirectResponse(LEGACY_PAGE_ROUTES[route] + query,
                                status_code=308, headers={"cache-control": "no-store"})
    file_route = PUBLIC_PAGES.get(route, route)
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
