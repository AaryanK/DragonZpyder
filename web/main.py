"""Python FastAPI gateway serving compiled, React-owned pages and API routes."""
import os
import re
from contextlib import asynccontextmanager
from http.cookiejar import CookieJar, DefaultCookiePolicy
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse, HTMLResponse, StreamingResponse

from backend.voice import realtime
from backend.mesh import mesh
from backend.security import OPERLY
from backend.chat_demo import router as chat_router

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"  # Vite-built React pages and fingerprinted assets
API = os.getenv("DRAGONZPYDER_API_ORIGIN", "https://api.dragonzpyder.xyz").rstrip("/")
IDENTITY_PUBLIC_ORIGIN = "https://api.dragonzpyder.xyz"
CHAT_HOST = "chat.dragonspire.xyz"
CHAT_PATHS = {"/chat", "/chat/app.js", "/chat/app.css", "/demo/session",
              "/demo/login", "/demo/logout", "/demo/chat", "/healthz"}
# Clean public URLs; Vite uses HTML entry filenames only as internal build artifacts.
PUBLIC_PAGES = {"/": "/index.html", "/app": "/app.html", "/account": "/account.html", "/login": "/account.html"}
LEGACY_PAGE_ROUTES = {"/app.html": "/app", "/account.html": "/account"}
STATIC = {
    "/", "/index.html", "/app.html", "/account.html", "/account.css",
    "/account.js", "/app.css", "/app.js", "/companion.js", "/dictation.js",
    "/mesh.js", "/mesh.css", "/workspace.css", "/ui-v1.css", "/chat.html", "/privacy.html",
    "/terms.html", "/robots.txt", "/sitemap.xml", "/script.js",
    "/app.webmanifest", "/app-icon-192.png", "/app-icon-512.png",
    "/brand-icon.png", "/brand-logo.png", "/brand-operly.png", "/dz-mark.svg", "/favicon-16.png", "/favicon-32.png",
}
HOP_HEADERS = {"connection", "transfer-encoding", "content-length", "host",
               "content-encoding", "keep-alive", "upgrade", "proxy-connection"}


class _RejectUpstreamCookies(DefaultCookiePolicy):
    """A multi-user proxy must not keep any upstream user's cookies."""
    def set_ok(self, cookie, request):
        return False
    def return_ok(self, cookie, request):
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    jar = CookieJar(policy=_RejectUpstreamCookies())
    async with httpx.AsyncClient(follow_redirects=False, timeout=120.0, cookies=jar) as http:
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


async def proxy(request: Request, destination: str, rewrite_origin=False, upstream_path=None, *, proof_only=False):
    # Fixed trusted service origins; never proxy to a host provided by the browser.
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}
    if proof_only:
        # The migration verifier receives only its own challenge. Never relay
        # Operly credentials, active identity sessions, or bearer headers.
        headers = {k:v for k,v in headers.items() if k in ("accept","content-type","user-agent")}
        challenge = (request.cookies.get("__Host-dz_import_proof", "")
                     if upstream_path.startswith("/identity/v1/import-proof/") else "")
        headers["cookie"] = ("__Host-dz_import_proof=" + challenge
                             if re.fullmatch(r"[A-Za-z0-9_-]{32,128}", challenge) else "")
    else:
        # An explicit empty cookie header also prevents a client's cookie jar
        # from attaching a previous caller's cookies when no cookie was sent.
        # Never forward a native session to Operly or legacy cookies to the issuer.
        cookie_names = ({"__Host-dz_identity", "__Host-dz_csrf", "__Host-dz_provider"}
                        if destination == API and upstream_path else None)
        if cookie_names is not None:
            headers["cookie"] = "; ".join(part.strip() for part in headers.get("cookie", "").split(";")
                                          if part.strip().partition("=")[0] in cookie_names)
        elif destination == OPERLY:
            headers["cookie"] = "; ".join(part.strip() for part in headers.get("cookie", "").split(";")
                                          if not part.strip().partition("=")[0].startswith("__Host-dz_"))
        else:
            headers.setdefault("cookie", "")
    if rewrite_origin:
        # Transport may use Railway private DNS; identity expects its public issuer.
        # Native mutation routes validate browser Origin before reaching this proxy.
        origin = IDENTITY_PUBLIC_ORIGIN if upstream_path and destination == API else destination
        headers["origin"] = origin
        headers["referer"] = origin + "/"
    if upstream_path and re.fullmatch(r"/v2/personal/voice/(?:sessions|openrouter)/[0-9a-f-]{36}/turn",upstream_path) and request.method=="POST":
        data=bytearray()
        async for chunk in request.stream():
            if len(data)+len(chunk)>7_700_000:
                return JSONResponse({"detail":"Voice utterance exceeds bound"},status_code=413,headers={"Cache-Control":"no-store"})
            data.extend(chunk)
        body=bytes(data)
    elif upstream_path == "/v2/personal/files" and request.method == "POST":
        data=bytearray()
        async for chunk in request.stream():
            if len(data)+len(chunk)>10*1024*1024:
                return JSONResponse({"detail":"Attachment exceeds 10 MiB"},status_code=413)
            data.extend(chunk)
        body=bytes(data)
    elif proof_only:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 12288:
                return JSONResponse({"detail":"Request too large"},status_code=413,
                                    headers={"Cache-Control":"no-store"})
        body = bytes(data)
    else:
        body = await request.body()
    if upstream_path == "/v2/personal/chat/stream":
        client = request.app.state.http
        try:
            outgoing = client.build_request(request.method, destination + upstream_path,
                                            headers=headers, content=body)
            streamed = await client.send(outgoing, stream=True)
        except httpx.HTTPError:
            return JSONResponse({"detail":{"message":"Agent stream unavailable"}}, status_code=502)
        if streamed.status_code != 200 or "text/event-stream" not in streamed.headers.get("content-type",""):
            try:
                return Response(content=await streamed.aread(), status_code=streamed.status_code,
                                media_type=streamed.headers.get("content-type","application/json"))
            finally:
                await streamed.aclose()
        async def body_stream():
            try:
                async for chunk in streamed.aiter_bytes():
                    yield chunk
            finally:
                await streamed.aclose()
        return StreamingResponse(body_stream(), media_type="text/event-stream",
                                 headers={"Cache-Control":"no-store","X-Accel-Buffering":"no"})
    try:
        upstream = await request.app.state.http.request(
            request.method, destination + (upstream_path or request.url.path) +
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
        if proof_only and not cookie.startswith("__Host-dz_import_proof="):
            if not (upstream_path == "/identity/v1/recovery/complete"
                    and cookie.startswith(("__Host-dz_identity=", "__Host-dz_csrf="))
                    and "max-age=0" in cookie.lower()):
                continue
        response.raw_headers.append((b"set-cookie", cookie.encode()))
    return response




async def admin_auth_status(request: Request) -> str:
    """Resolve rights from an authenticated DragonZpyder browser session.

    Distinguish an expired/missing session from an authenticated non-admin.
    Neither a browser header nor a query string can elevate privileges.
    """
    allowed = {entry.strip().casefold() for entry in
               os.getenv("DRAGONZPYDER_ADMIN_EMAILS", "").split(",") if entry.strip()}
    if not allowed:
        return "forbidden"
    native = bool(request.cookies.get("__Host-dz_identity"))
    if not native and not (request.cookies.get("__Host-operly_session") or
            request.cookies.get("operly_session")):
        return "signin"
    target = API + "/identity/v1/me" if native else OPERLY + "/api/auth/me"
    origin = IDENTITY_PUBLIC_ORIGIN if native else OPERLY
    cookies = "; ".join(part.strip() for part in request.headers.get("cookie", "").split(";")
                        if (part.strip().startswith("__Host-dz_identity=") if native
                            else not part.strip().startswith("__Host-dz_")))
    try:
        response = await request.app.state.http.get(
            target,
            headers={"cookie": cookies,
                     "origin": origin, "referer": origin + "/",
                     "accept": "application/json"},
            timeout=10)
    except httpx.HTTPError:
        return "unavailable"
    if response.status_code in (401, 403):
        return "signin"
    if response.status_code != 200:
        return "unavailable"
    try:
        account = response.json()
        email = account.get("email", "") if isinstance(account, dict) else ""
    except (ValueError, TypeError):
        return "unavailable"
    return "allowed" if isinstance(email, str) and email.casefold() in allowed else "forbidden"


def admin_notice(message: str, *, status_code: int) -> HTMLResponse:
    # Messages are server-authored constants; never interpolate user strings.
    page = ("""<!doctype html><html lang="en"><head><meta charset="utf-8">"""
            """<meta name="viewport" content="width=device-width,initial-scale=1">"""
            """<meta name="robots" content="noindex,nofollow">"""
            """<title>DragonZpyder Admin</title><style>"""
            """:root{color-scheme:dark}body{margin:0;background:#0c0e0d;color:#f1f2e9;"""
            """font:16px system-ui,sans-serif;display:grid;min-height:100vh;place-items:center}"""
            """main{max-width:520px;padding:32px}h1{font-size:32px;letter-spacing:-.04em}"""
            """p{color:#b5b9b1;line-height:1.7}a{color:#edb36a}"""
            """</style></head><body><main><p>DRAGONZPYDER / ADMIN</p>"""
            """<h1>Access not available</h1><p>""" + message +
            """</p><a href="/account">Open account settings and sign-in →</a>"""
            """</main></body></html>""")
    return HTMLResponse(page, status_code=status_code, headers={
        "cache-control": "no-store", "x-frame-options": "DENY",
        "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; "
                                   "base-uri 'none'; frame-ancestors 'none'",
    })

async def admin_route(request: Request):
    if request.method != "GET":
        return JSONResponse({"detail": "Not found"}, status_code=404)
    status = await admin_auth_status(request)
    if status != "allowed":
        if request.url.path == "/admin":
            if status == "signin":
                # Fixed same-origin target; no user-controlled return URL.
                return RedirectResponse("/account?next=%2Fadmin", status_code=303,
                                        headers={"cache-control": "no-store"})
            if status == "forbidden":
                return admin_notice(
                    "The signed-in DragonZpyder account is not on the administrator allowlist. "
                    "Switch to an authorised account and try again.", status_code=403)
            return admin_notice(
                "The identity service is temporarily unavailable. Please try again.",
                status_code=503)
        return JSONResponse({"detail": "Administrator sign-in required" if status == "signin"
                             else "Administrator access denied" if status == "forbidden"
                             else "Account verification unavailable"},
                            status_code=401 if status == "signin" else
                                        403 if status == "forbidden" else 503,
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


def native_web_session(request: Request) -> bool:
    # A cookie is a routing hint, never authentication. The API verifies it.
    return bool(request.cookies.get("__Host-dz_identity"))


@app.api_route("/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def dispatch(path: str, request: Request):
    route = "/" + path
    if route == "/admin" or route == "/admin/api/usage":
        return await admin_route(request)
    # First-party identity, native chat and browser-only MCP routes terminate
    # at DragonZpyder API. No wildcard /internal proxy: browsers must never
    # reach the model gateway's service-token-bearing private routes.
    if route == "/dz/status" and request.method == "GET":
        return JSONResponse({"web_cutover_enabled":
            os.getenv("DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED") == "1",
            **({"native_session_present": True} if native_web_session(request) else {})},
            headers={"Cache-Control": "no-store"})
    if route == "/dz/recovery/status" and request.method == "GET":
        return JSONResponse({"enabled": os.getenv("DRAGONZPYDER_ACTIVE_RECOVERY_WEB_ENABLED") == "1"},
                            headers={"Cache-Control":"no-store"})
    if route == "/dz/import-proof/status" and request.method == "GET":
        return JSONResponse({"enabled": os.getenv("DRAGONZPYDER_IMPORT_PROOF_WEB_ENABLED") == "1"},
                            headers={"Cache-Control": "no-store"})
    if route == "/dz/import-proof/recovery/status" and request.method == "GET":
        return JSONResponse({"enabled": os.getenv("DRAGONZPYDER_IMPORT_PROOF_WEB_ENABLED") == "1"
            and os.getenv("DRAGONZPYDER_NATIVE_PENDING_RECOVERY_WEB_ENABLED") == "1"},
            headers={"Cache-Control":"no-store"})
    if route.startswith("/dz/"):
        native = route[3:]
        proof_routes = {
            "/identity/v1/import-proof/password",
            "/identity/v1/import-proof/google/start",
            "/identity/v1/import-proof/google/complete",
        }
        if os.getenv("DRAGONZPYDER_NATIVE_PENDING_RECOVERY_WEB_ENABLED") == "1":
            proof_routes.update({"/identity/v1/import-proof/recovery/start",
                                 "/identity/v1/import-proof/recovery/complete"})
        if native.startswith("/identity/v1/recovery/"):
            if (native not in {"/identity/v1/recovery/start","/identity/v1/recovery/complete"}
                    or request.method != "POST" or os.getenv("DRAGONZPYDER_ACTIVE_RECOVERY_WEB_ENABLED") != "1"):
                return JSONResponse({"detail":"Not found"},status_code=404,headers={"Cache-Control":"no-store"})
            if request.headers.get("origin") != "https://" + (request.url.hostname or "").lower():
                return JSONResponse({"detail":"Origin rejected"},status_code=403,headers={"Cache-Control":"no-store"})
            if request.url.query:
                return JSONResponse({"detail":"Unexpected query"},status_code=400,headers={"Cache-Control":"no-store"})
            return await proxy(request, API, rewrite_origin=True, upstream_path=native, proof_only=True)
        if native.startswith("/identity/v1/import-proof/"):
            if (native not in proof_routes or request.method != "POST"
                    or os.getenv("DRAGONZPYDER_IMPORT_PROOF_WEB_ENABLED") != "1"):
                return JSONResponse({"detail": "Not found"}, status_code=404,
                                    headers={"Cache-Control": "no-store"})
            if request.headers.get("origin") != "https://" + (request.url.hostname or "").lower():
                return JSONResponse({"detail": "Origin rejected"}, status_code=403,
                                    headers={"Cache-Control": "no-store"})
            if request.url.query:
                return JSONResponse({"detail":"Unexpected query"},status_code=400,headers={"Cache-Control":"no-store"})
            return await proxy(request, API, rewrite_origin=True, upstream_path=native, proof_only=True)
        permitted = (
            native.startswith("/v2/personal/")
            or native in (
                "/identity/v1/password/login",
                "/identity/v1/logout",
                "/identity/v1/me",
                "/identity/v1/avatar",
                "/identity/v1/provider/google/start",
                "/identity/v1/provider/google/complete",
                "/identity/v1/provider/google/signup",
                "/identity/v1/mobile/capabilities",
                "/identity/v1/mobile/google/start",
                "/identity/v1/mobile/google/callback",
                "/identity/v1/mobile/google/redeem",
                "/identity/v1/mobile/discord/start",
                "/identity/v1/mobile/discord/callback",
                "/identity/v1/mobile/discord/redeem",
            )
            or native.startswith("/internal/mcp/")
        )
        if not permitted:
            return JSONResponse({"detail": "Not found"}, status_code=404)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            # Reject cross-site browser mutation *before* re-authoring the
            # Origin header for the private first-party API.
            expected = "https://" + (request.url.hostname or "").lower()
            if request.headers.get("origin") != expected:
                return JSONResponse({"detail": "Origin rejected"}, status_code=403)
        return await proxy(request, API, rewrite_origin=True, upstream_path=native)
    if route.startswith("/api/"):
        # Native cutover must never silently re-enter the old Operly runtime.
        if os.getenv("DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED") == "1" or native_web_session(request):
            return JSONResponse({"detail": {"code": "LEGACY_OPERLY_ROUTE_RETIRED",
                "message": "Use DragonZpyder's first-party API and optional MCP connections."}},
                status_code=410)
        # Compatibility only until explicitly approved native cutover.
        return await proxy(request, OPERLY, rewrite_origin=True)
    if route.startswith("/internal/v1/"):
        return await proxy(request, API)
    if route == "/companion/realtime":
        if os.getenv("DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED") == "1" or native_web_session(request):
            return JSONResponse({"detail": "First-party voice authorization not ready"}, status_code=503)
        return await realtime(request)
    if route.startswith("/mesh/"):
        if os.getenv("DRAGONZPYDER_FIRST_PARTY_WEB_CUTOVER_ENABLED") == "1" or native_web_session(request):
            return JSONResponse({"detail": "First-party Mesh authorization not ready"}, status_code=503)
        return await mesh(request)
    if request.method in ("GET", "HEAD") and route in LEGACY_PAGE_ROUTES:
        query = ("?" + request.url.query) if request.url.query else ""
        return RedirectResponse(LEGACY_PAGE_ROUTES[route] + query,
                                status_code=308, headers={"cache-control": "no-store"})

    # Public event page; exact routes, no authentication or user data.
    if request.method in ("GET", "HEAD") and route in ("/thanksgiving", "/thanksgiving/start", "/thanksgiving/android"):
        if route == "/thanksgiving":
            return HTMLResponse("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>DragonZpyder</title><style>*{box-sizing:border-box}body{margin:0;background:#131313;color:#f8f4ed;font-family:system-ui,sans-serif;min-height:100vh;display:grid;place-items:center}main{width:100%;max-width:1800px;padding:6vw;text-align:center}h1{font-weight:500;letter-spacing:-.04em;font-size:clamp(42px,6vw,128px);line-height:1.08;margin:0 0 1rem}strong{color:#ffc78f;font-weight:650}p{font-size:clamp(19px,2.3vw,42px);margin:0 0 1rem;color:#d8d2c9}.display{display:grid;grid-template-columns:1.5fr 1fr;align-items:center;gap:5vw;text-align:left}.qr{text-align:center}.qr svg{width:min(34vw,62vh);max-width:100%;border-radius:12px;display:block;margin:0 auto 1rem}.qr p{font-size:clamp(18px,2vw,42px);margin:0}.choices{max-width:470px}.choices h1{font-size:44px;margin-bottom:2rem}.choice{display:flex;align-items:center;gap:18px;text-align:left;text-decoration:none;color:#f8f4ed;padding:22px;border:1px solid #49433e;border-radius:12px;margin:12px 0;font-size:23px;font-weight:600}.choice:hover,.choice:focus-visible{border-color:#ffc78f}.choice svg{width:38px;height:38px;flex:none}.small{font-size:16px;color:#aaa}.small a{color:#ffc78f}@media(max-width:700px){.display{grid-template-columns:1fr;text-align:center;gap:36px}.qr svg{width:min(70vw,360px)}main{padding:8vw}}</style><body><main class=\"display\"><div><h1>Enjoy the turkey.</h1><p>Sponsored by <strong>DragonZpyder</strong></p></div><div class=\"qr\"><a href=\"/thanksgiving/start\" aria-label=\"Choose your platform\"><svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 41 41\" role=\"img\" aria-label=\"Scan to choose Web or Android\" shape-rendering=\"crispEdges\"><rect width=\"41\" height=\"41\" fill=\"white\"/><path d=\"M4 4h1v1h-1zM5 4h1v1h-1zM6 4h1v1h-1zM7 4h1v1h-1zM8 4h1v1h-1zM9 4h1v1h-1zM10 4h1v1h-1zM12 4h1v1h-1zM16 4h1v1h-1zM17 4h1v1h-1zM18 4h1v1h-1zM21 4h1v1h-1zM25 4h1v1h-1zM26 4h1v1h-1zM30 4h1v1h-1zM31 4h1v1h-1zM32 4h1v1h-1zM33 4h1v1h-1zM34 4h1v1h-1zM35 4h1v1h-1zM36 4h1v1h-1zM4 5h1v1h-1zM10 5h1v1h-1zM12 5h1v1h-1zM14 5h1v1h-1zM17 5h1v1h-1zM18 5h1v1h-1zM22 5h1v1h-1zM23 5h1v1h-1zM24 5h1v1h-1zM30 5h1v1h-1zM36 5h1v1h-1zM4 6h1v1h-1zM6 6h1v1h-1zM7 6h1v1h-1zM8 6h1v1h-1zM10 6h1v1h-1zM12 6h1v1h-1zM13 6h1v1h-1zM14 6h1v1h-1zM16 6h1v1h-1zM17 6h1v1h-1zM18 6h1v1h-1zM24 6h1v1h-1zM25 6h1v1h-1zM27 6h1v1h-1zM30 6h1v1h-1zM32 6h1v1h-1zM33 6h1v1h-1zM34 6h1v1h-1zM36 6h1v1h-1zM4 7h1v1h-1zM6 7h1v1h-1zM7 7h1v1h-1zM8 7h1v1h-1zM10 7h1v1h-1zM18 7h1v1h-1zM19 7h1v1h-1zM20 7h1v1h-1zM22 7h1v1h-1zM23 7h1v1h-1zM24 7h1v1h-1zM26 7h1v1h-1zM27 7h1v1h-1zM28 7h1v1h-1zM30 7h1v1h-1zM32 7h1v1h-1zM33 7h1v1h-1zM34 7h1v1h-1zM36 7h1v1h-1zM4 8h1v1h-1zM6 8h1v1h-1zM7 8h1v1h-1zM8 8h1v1h-1zM10 8h1v1h-1zM12 8h1v1h-1zM13 8h1v1h-1zM14 8h1v1h-1zM15 8h1v1h-1zM16 8h1v1h-1zM17 8h1v1h-1zM19 8h1v1h-1zM20 8h1v1h-1zM26 8h1v1h-1zM27 8h1v1h-1zM30 8h1v1h-1zM32 8h1v1h-1zM33 8h1v1h-1zM34 8h1v1h-1zM36 8h1v1h-1zM4 9h1v1h-1zM10 9h1v1h-1zM15 9h1v1h-1zM17 9h1v1h-1zM19 9h1v1h-1zM20 9h1v1h-1zM21 9h1v1h-1zM22 9h1v1h-1zM23 9h1v1h-1zM25 9h1v1h-1zM28 9h1v1h-1zM30 9h1v1h-1zM36 9h1v1h-1zM4 10h1v1h-1zM5 10h1v1h-1zM6 10h1v1h-1zM7 10h1v1h-1zM8 10h1v1h-1zM9 10h1v1h-1zM10 10h1v1h-1zM12 10h1v1h-1zM14 10h1v1h-1zM16 10h1v1h-1zM18 10h1v1h-1zM20 10h1v1h-1zM22 10h1v1h-1zM24 10h1v1h-1zM26 10h1v1h-1zM28 10h1v1h-1zM30 10h1v1h-1zM31 10h1v1h-1zM32 10h1v1h-1zM33 10h1v1h-1zM34 10h1v1h-1zM35 10h1v1h-1zM36 10h1v1h-1zM15 11h1v1h-1zM17 11h1v1h-1zM19 11h1v1h-1zM20 11h1v1h-1zM22 11h1v1h-1zM27 11h1v1h-1zM4 12h1v1h-1zM7 12h1v1h-1zM8 12h1v1h-1zM9 12h1v1h-1zM10 12h1v1h-1zM11 12h1v1h-1zM12 12h1v1h-1zM13 12h1v1h-1zM14 12h1v1h-1zM15 12h1v1h-1zM18 12h1v1h-1zM20 12h1v1h-1zM21 12h1v1h-1zM27 12h1v1h-1zM28 12h1v1h-1zM29 12h1v1h-1zM32 12h1v1h-1zM34 12h1v1h-1zM35 12h1v1h-1zM36 12h1v1h-1zM5 13h1v1h-1zM8 13h1v1h-1zM9 13h1v1h-1zM16 13h1v1h-1zM17 13h1v1h-1zM19 13h1v1h-1zM21 13h1v1h-1zM23 13h1v1h-1zM24 13h1v1h-1zM25 13h1v1h-1zM27 13h1v1h-1zM32 13h1v1h-1zM33 13h1v1h-1zM34 13h1v1h-1zM35 13h1v1h-1zM4 14h1v1h-1zM5 14h1v1h-1zM6 14h1v1h-1zM10 14h1v1h-1zM13 14h1v1h-1zM16 14h1v1h-1zM17 14h1v1h-1zM19 14h1v1h-1zM20 14h1v1h-1zM24 14h1v1h-1zM26 14h1v1h-1zM27 14h1v1h-1zM30 14h1v1h-1zM32 14h1v1h-1zM33 14h1v1h-1zM34 14h1v1h-1zM35 14h1v1h-1zM36 14h1v1h-1zM4 15h1v1h-1zM5 15h1v1h-1zM7 15h1v1h-1zM8 15h1v1h-1zM9 15h1v1h-1zM11 15h1v1h-1zM12 15h1v1h-1zM13 15h1v1h-1zM16 15h1v1h-1zM17 15h1v1h-1zM20 15h1v1h-1zM22 15h1v1h-1zM23 15h1v1h-1zM25 15h1v1h-1zM26 15h1v1h-1zM29 15h1v1h-1zM30 15h1v1h-1zM31 15h1v1h-1zM34 15h1v1h-1zM35 15h1v1h-1zM4 16h1v1h-1zM5 16h1v1h-1zM7 16h1v1h-1zM8 16h1v1h-1zM9 16h1v1h-1zM10 16h1v1h-1zM11 16h1v1h-1zM13 16h1v1h-1zM15 16h1v1h-1zM17 16h1v1h-1zM19 16h1v1h-1zM21 16h1v1h-1zM23 16h1v1h-1zM25 16h1v1h-1zM27 16h1v1h-1zM28 16h1v1h-1zM30 16h1v1h-1zM35 16h1v1h-1zM4 17h1v1h-1zM7 17h1v1h-1zM9 17h1v1h-1zM13 17h1v1h-1zM16 17h1v1h-1zM17 17h1v1h-1zM18 17h1v1h-1zM21 17h1v1h-1zM22 17h1v1h-1zM23 17h1v1h-1zM24 17h1v1h-1zM25 17h1v1h-1zM28 17h1v1h-1zM31 17h1v1h-1zM33 17h1v1h-1zM34 17h1v1h-1zM5 18h1v1h-1zM7 18h1v1h-1zM10 18h1v1h-1zM12 18h1v1h-1zM14 18h1v1h-1zM18 18h1v1h-1zM19 18h1v1h-1zM22 18h1v1h-1zM23 18h1v1h-1zM24 18h1v1h-1zM26 18h1v1h-1zM28 18h1v1h-1zM30 18h1v1h-1zM6 19h1v1h-1zM7 19h1v1h-1zM9 19h1v1h-1zM12 19h1v1h-1zM13 19h1v1h-1zM14 19h1v1h-1zM15 19h1v1h-1zM16 19h1v1h-1zM18 19h1v1h-1zM20 19h1v1h-1zM24 19h1v1h-1zM26 19h1v1h-1zM29 19h1v1h-1zM31 19h1v1h-1zM33 19h1v1h-1zM34 19h1v1h-1zM36 19h1v1h-1zM6 20h1v1h-1zM7 20h1v1h-1zM9 20h1v1h-1zM10 20h1v1h-1zM14 20h1v1h-1zM15 20h1v1h-1zM16 20h1v1h-1zM19 20h1v1h-1zM26 20h1v1h-1zM27 20h1v1h-1zM28 20h1v1h-1zM29 20h1v1h-1zM30 20h1v1h-1zM31 20h1v1h-1zM32 20h1v1h-1zM33 20h1v1h-1zM4 21h1v1h-1zM6 21h1v1h-1zM8 21h1v1h-1zM9 21h1v1h-1zM14 21h1v1h-1zM17 21h1v1h-1zM19 21h1v1h-1zM21 21h1v1h-1zM23 21h1v1h-1zM24 21h1v1h-1zM30 21h1v1h-1zM32 21h1v1h-1zM34 21h1v1h-1zM36 21h1v1h-1zM6 22h1v1h-1zM10 22h1v1h-1zM11 22h1v1h-1zM12 22h1v1h-1zM13 22h1v1h-1zM14 22h1v1h-1zM18 22h1v1h-1zM19 22h1v1h-1zM20 22h1v1h-1zM21 22h1v1h-1zM22 22h1v1h-1zM23 22h1v1h-1zM25 22h1v1h-1zM26 22h1v1h-1zM27 22h1v1h-1zM30 22h1v1h-1zM31 22h1v1h-1zM33 22h1v1h-1zM34 22h1v1h-1zM36 22h1v1h-1zM5 23h1v1h-1zM6 23h1v1h-1zM7 23h1v1h-1zM8 23h1v1h-1zM11 23h1v1h-1zM12 23h1v1h-1zM13 23h1v1h-1zM16 23h1v1h-1zM23 23h1v1h-1zM26 23h1v1h-1zM28 23h1v1h-1zM29 23h1v1h-1zM30 23h1v1h-1zM32 23h1v1h-1zM33 23h1v1h-1zM34 23h1v1h-1zM4 24h1v1h-1zM6 24h1v1h-1zM7 24h1v1h-1zM9 24h1v1h-1zM10 24h1v1h-1zM11 24h1v1h-1zM15 24h1v1h-1zM17 24h1v1h-1zM18 24h1v1h-1zM20 24h1v1h-1zM22 24h1v1h-1zM23 24h1v1h-1zM25 24h1v1h-1zM26 24h1v1h-1zM31 24h1v1h-1zM33 24h1v1h-1zM4 25h1v1h-1zM5 25h1v1h-1zM8 25h1v1h-1zM12 25h1v1h-1zM13 25h1v1h-1zM16 25h1v1h-1zM17 25h1v1h-1zM21 25h1v1h-1zM27 25h1v1h-1zM32 25h1v1h-1zM4 26h1v1h-1zM6 26h1v1h-1zM7 26h1v1h-1zM10 26h1v1h-1zM12 26h1v1h-1zM15 26h1v1h-1zM16 26h1v1h-1zM22 26h1v1h-1zM23 26h1v1h-1zM24 26h1v1h-1zM25 26h1v1h-1zM27 26h1v1h-1zM28 26h1v1h-1zM29 26h1v1h-1zM30 26h1v1h-1zM32 26h1v1h-1zM34 26h1v1h-1zM35 26h1v1h-1zM36 26h1v1h-1zM4 27h1v1h-1zM6 27h1v1h-1zM8 27h1v1h-1zM11 27h1v1h-1zM15 27h1v1h-1zM16 27h1v1h-1zM17 27h1v1h-1zM18 27h1v1h-1zM19 27h1v1h-1zM21 27h1v1h-1zM22 27h1v1h-1zM23 27h1v1h-1zM24 27h1v1h-1zM26 27h1v1h-1zM28 27h1v1h-1zM31 27h1v1h-1zM32 27h1v1h-1zM34 27h1v1h-1zM35 27h1v1h-1zM36 27h1v1h-1zM4 28h1v1h-1zM5 28h1v1h-1zM6 28h1v1h-1zM8 28h1v1h-1zM9 28h1v1h-1zM10 28h1v1h-1zM11 28h1v1h-1zM13 28h1v1h-1zM14 28h1v1h-1zM15 28h1v1h-1zM20 28h1v1h-1zM22 28h1v1h-1zM24 28h1v1h-1zM27 28h1v1h-1zM28 28h1v1h-1zM29 28h1v1h-1zM30 28h1v1h-1zM31 28h1v1h-1zM32 28h1v1h-1zM33 28h1v1h-1zM35 28h1v1h-1zM12 29h1v1h-1zM14 29h1v1h-1zM16 29h1v1h-1zM17 29h1v1h-1zM18 29h1v1h-1zM19 29h1v1h-1zM20 29h1v1h-1zM21 29h1v1h-1zM22 29h1v1h-1zM25 29h1v1h-1zM26 29h1v1h-1zM28 29h1v1h-1zM32 29h1v1h-1zM34 29h1v1h-1zM35 29h1v1h-1zM4 30h1v1h-1zM5 30h1v1h-1zM6 30h1v1h-1zM7 30h1v1h-1zM8 30h1v1h-1zM9 30h1v1h-1zM10 30h1v1h-1zM12 30h1v1h-1zM16 30h1v1h-1zM18 30h1v1h-1zM19 30h1v1h-1zM20 30h1v1h-1zM21 30h1v1h-1zM23 30h1v1h-1zM27 30h1v1h-1zM28 30h1v1h-1zM30 30h1v1h-1zM32 30h1v1h-1zM34 30h1v1h-1zM4 31h1v1h-1zM10 31h1v1h-1zM12 31h1v1h-1zM14 31h1v1h-1zM18 31h1v1h-1zM21 31h1v1h-1zM22 31h1v1h-1zM25 31h1v1h-1zM26 31h1v1h-1zM27 31h1v1h-1zM28 31h1v1h-1zM32 31h1v1h-1zM33 31h1v1h-1zM34 31h1v1h-1zM35 31h1v1h-1zM4 32h1v1h-1zM6 32h1v1h-1zM7 32h1v1h-1zM8 32h1v1h-1zM10 32h1v1h-1zM12 32h1v1h-1zM13 32h1v1h-1zM15 32h1v1h-1zM16 32h1v1h-1zM17 32h1v1h-1zM18 32h1v1h-1zM19 32h1v1h-1zM20 32h1v1h-1zM21 32h1v1h-1zM25 32h1v1h-1zM26 32h1v1h-1zM27 32h1v1h-1zM28 32h1v1h-1zM29 32h1v1h-1zM30 32h1v1h-1zM31 32h1v1h-1zM32 32h1v1h-1zM36 32h1v1h-1zM4 33h1v1h-1zM6 33h1v1h-1zM7 33h1v1h-1zM8 33h1v1h-1zM10 33h1v1h-1zM12 33h1v1h-1zM13 33h1v1h-1zM15 33h1v1h-1zM18 33h1v1h-1zM20 33h1v1h-1zM22 33h1v1h-1zM25 33h1v1h-1zM26 33h1v1h-1zM27 33h1v1h-1zM29 33h1v1h-1zM31 33h1v1h-1zM36 33h1v1h-1zM4 34h1v1h-1zM6 34h1v1h-1zM7 34h1v1h-1zM8 34h1v1h-1zM10 34h1v1h-1zM15 34h1v1h-1zM17 34h1v1h-1zM18 34h1v1h-1zM19 34h1v1h-1zM23 34h1v1h-1zM25 34h1v1h-1zM26 34h1v1h-1zM27 34h1v1h-1zM28 34h1v1h-1zM31 34h1v1h-1zM32 34h1v1h-1zM33 34h1v1h-1zM35 34h1v1h-1zM36 34h1v1h-1zM4 35h1v1h-1zM10 35h1v1h-1zM14 35h1v1h-1zM15 35h1v1h-1zM16 35h1v1h-1zM17 35h1v1h-1zM23 35h1v1h-1zM24 35h1v1h-1zM26 35h1v1h-1zM27 35h1v1h-1zM29 35h1v1h-1zM30 35h1v1h-1zM31 35h1v1h-1zM32 35h1v1h-1zM33 35h1v1h-1zM34 35h1v1h-1zM35 35h1v1h-1zM36 35h1v1h-1zM4 36h1v1h-1zM5 36h1v1h-1zM6 36h1v1h-1zM7 36h1v1h-1zM8 36h1v1h-1zM9 36h1v1h-1zM10 36h1v1h-1zM12 36h1v1h-1zM13 36h1v1h-1zM14 36h1v1h-1zM18 36h1v1h-1zM19 36h1v1h-1zM21 36h1v1h-1zM23 36h1v1h-1zM27 36h1v1h-1zM28 36h1v1h-1zM31 36h1v1h-1zM32 36h1v1h-1z\" fill=\"black\"/></svg></a><p>Scan to learn more</p></div></main></body></html>", headers={"Cache-Control": "no-store"})
        if route == "/thanksgiving/start":
            return HTMLResponse("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>DragonZpyder</title><style>*{box-sizing:border-box}body{margin:0;background:#131313;color:#f8f4ed;font-family:system-ui,sans-serif;min-height:100vh;display:grid;place-items:center}main{width:100%;max-width:1800px;padding:6vw;text-align:center}h1{font-weight:500;letter-spacing:-.04em;font-size:clamp(42px,6vw,128px);line-height:1.08;margin:0 0 1rem}strong{color:#ffc78f;font-weight:650}p{font-size:clamp(19px,2.3vw,42px);margin:0 0 1rem;color:#d8d2c9}.display{display:grid;grid-template-columns:1.5fr 1fr;align-items:center;gap:5vw;text-align:left}.qr{text-align:center}.qr svg{width:min(34vw,62vh);max-width:100%;border-radius:12px;display:block;margin:0 auto 1rem}.qr p{font-size:clamp(18px,2vw,42px);margin:0}.choices{max-width:470px}.choices h1{font-size:44px;margin-bottom:2rem}.choice{display:flex;align-items:center;gap:18px;text-align:left;text-decoration:none;color:#f8f4ed;padding:22px;border:1px solid #49433e;border-radius:12px;margin:12px 0;font-size:23px;font-weight:600}.choice:hover,.choice:focus-visible{border-color:#ffc78f}.choice svg{width:38px;height:38px;flex:none}.small{font-size:16px;color:#aaa}.small a{color:#ffc78f}@media(max-width:700px){.display{grid-template-columns:1fr;text-align:center;gap:36px}.qr svg{width:min(70vw,360px)}main{padding:8vw}}</style><body><main class=\"choices\"><h1>Select your platform</h1><a class=\"choice\" href=\"/\"><svg viewBox=\"0 0 48 48\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.5\" aria-hidden=\"true\"><circle cx=\"24\" cy=\"24\" r=\"19\"/><ellipse cx=\"24\" cy=\"24\" rx=\"9\" ry=\"19\"/><path d=\"M5 24h38M8 14h32M8 34h32\"/></svg>Website</a><a class=\"choice\" href=\"https://github.com/AaryanK/DragonZpyder/releases/download/thanksgiving-2026-android-beta/DragonZpyder-beta.apk\"><svg viewBox=\"0 0 48 48\" aria-hidden=\"true\"><g fill=\"#a4c639\" stroke=\"#a4c639\" stroke-width=\"2\" stroke-linecap=\"round\"><path d=\"M5 30a19 19 0 0 1 38 0Z\"/><path d=\"m12 15-4-7m28 7 4-7\"/></g><circle cx=\"16\" cy=\"24\" r=\"2\" fill=\"#131313\"/><circle cx=\"32\" cy=\"24\" r=\"2\" fill=\"#131313\"/></svg>Android application</a></main></body></html>", headers={"Cache-Control": "no-store"})
        try:
            async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                response = await client.get("https://api.github.com/repos/AaryanK/DragonZpyder/releases?per_page=10", headers={"Accept": "application/vnd.github+json"})
                response.raise_for_status()
                for release in response.json():
                    if release.get("draft"):
                        continue
                    for asset in release.get("assets", []):
                        url = asset.get("browser_download_url", "")
                        if asset.get("name", "").lower().endswith(".apk") and url.startswith("https://github.com/AaryanK/DragonZpyder/releases/download/"):
                            return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            pass
        return HTMLResponse("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>DragonZpyder</title><style>*{box-sizing:border-box}body{margin:0;background:#131313;color:#f8f4ed;font-family:system-ui,sans-serif;min-height:100vh;display:grid;place-items:center}main{width:100%;max-width:1800px;padding:6vw;text-align:center}h1{font-weight:500;letter-spacing:-.04em;font-size:clamp(42px,6vw,128px);line-height:1.08;margin:0 0 1rem}strong{color:#ffc78f;font-weight:650}p{font-size:clamp(19px,2.3vw,42px);margin:0 0 1rem;color:#d8d2c9}.display{display:grid;grid-template-columns:1.5fr 1fr;align-items:center;gap:5vw;text-align:left}.qr{text-align:center}.qr svg{width:min(34vw,62vh);max-width:100%;border-radius:12px;display:block;margin:0 auto 1rem}.qr p{font-size:clamp(18px,2vw,42px);margin:0}.choices{max-width:470px}.choices h1{font-size:44px;margin-bottom:2rem}.choice{display:flex;align-items:center;gap:18px;text-align:left;text-decoration:none;color:#f8f4ed;padding:22px;border:1px solid #49433e;border-radius:12px;margin:12px 0;font-size:23px;font-weight:600}.choice:hover,.choice:focus-visible{border-color:#ffc78f}.choice svg{width:38px;height:38px;flex:none}.small{font-size:16px;color:#aaa}.small a{color:#ffc78f}@media(max-width:700px){.display{grid-template-columns:1fr;text-align:center;gap:36px}.qr svg{width:min(70vw,360px)}main{padding:8vw}}</style><body><main class=\"choices\"><h1>Android download</h1><p class=\"small\">No public APK is available from the official release feed right now.</p><a class=\"choice\" href=\"https://github.com/AaryanK/DragonZpyder/releases\">Check official releases</a><a class=\"choice\" href=\"/\">Open website</a></main></body></html>", status_code=503, headers={"Cache-Control": "no-store"})

    file_route = PUBLIC_PAGES.get(route, route)
    if request.method in ("GET", "HEAD") and route.startswith("/assets/"):
        # Only serve hashed assets emitted by Vite, never arbitrary files.
        assets = (DIST / "assets").resolve()
        target = (DIST / route.lstrip("/")).resolve()
        if target.is_relative_to(assets) and target.is_file():
            return FileResponse(target, headers={"cache-control": "public, max-age=31536000, immutable"})
    if request.method in ("GET", "HEAD") and file_route in STATIC:
        if file_route in ("/index.html", "/app.html", "/account.html",
                          "/app.webmanifest", "/app-icon-192.png", "/app-icon-512.png",
                          "/brand-icon.png", "/brand-logo.png", "/brand-operly.png", "/dz-mark.svg", "/favicon-16.png", "/favicon-32.png"):
            target = DIST / file_route.lstrip("/")
            if not target.is_file():
                return JSONResponse({"detail": {"code": "FRONTEND_UNAVAILABLE",
                                               "message": "React build is unavailable."}},
                                    status_code=503, headers={"cache-control": "no-store"})
        else:
            target = ROOT / file_route.lstrip("/")
        if target.is_file():
            media_types = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
                           ".xml": "application/xml", ".txt": "text/plain",
                           ".webmanifest": "application/manifest+json", ".png": "image/png", ".svg": "image/svg+xml"}
            return FileResponse(target, media_type=media_types.get(target.suffix),
                                headers={"cache-control": "no-store" if target.suffix in
                                         (".html", ".js", ".css") else "public, max-age=300"})
    return JSONResponse({"detail": {"code": "NOT_FOUND", "message": "Page not found."}}, status_code=404)
