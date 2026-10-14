"""Server-only administrator access to DragonZpyder inference telemetry.

The browser authenticates to the Web service with HTTP Basic over HTTPS;
the dedicated service admin bearer token is never sent to client code.
"""
from __future__ import annotations

import base64
import hmac
import os
from pathlib import Path

import httpx
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response

_ROOT = Path(__file__).resolve().parents[1]
_DIST = _ROOT / "dist"
_BASIC = {"www-authenticate": 'Basic realm="DragonZpyder Admin", charset="UTF-8"',
          "cache-control": "no-store"}
_HEADERS = {"cache-control": "no-store", "x-frame-options": "DENY",
            "referrer-policy": "no-referrer",
            "content-security-policy": "default-src 'none'; script-src 'self'; "
                                       "style-src 'self'; connect-src 'self'; "
                                       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"}


def _credentials_ok(request: Request) -> bool:
    password = os.getenv("DRAGONZPYDER_ADMIN_PASSWORD", "")
    user = os.getenv("DRAGONZPYDER_ADMIN_USERNAME", "admin")
    if len(password) < 24:
        return False
    value = request.headers.get("authorization", "")
    if not value.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(value[6:], validate=True).decode("utf-8")
        supplied_user, supplied_password = raw.split(":", 1)
    except (ValueError, UnicodeDecodeError):
        return False
    return hmac.compare_digest(supplied_user, user) and hmac.compare_digest(supplied_password, password)


async def admin_dispatch(request: Request, api_origin: str):
    path = request.url.path
    if request.method not in ("GET", "HEAD"):
        return JSONResponse({"error": "Method not allowed"}, status_code=405, headers=_HEADERS)
    if len(os.getenv("DRAGONZPYDER_ADMIN_PASSWORD", "")) < 24 or len(
        os.getenv("DRAGONZPYDER_ADMIN_TOKEN", "")) < 32:
        return JSONResponse({"error": "Administrator access has not been configured."},
                            status_code=503, headers=_HEADERS)
    if not _credentials_ok(request):
        return Response(status_code=401, headers={**_HEADERS, **_BASIC})
    if path in ("/admin", "/admin/"):
        entry = _DIST / "admin.html"
        if not entry.is_file():
            return JSONResponse({"error": "Admin frontend build unavailable"},
                                status_code=503, headers=_HEADERS)
        return FileResponse(entry, headers=_HEADERS)
    if not path.startswith("/admin/api/"):
        return JSONResponse({"error": "Not found"}, status_code=404, headers=_HEADERS)
    rel = path[len("/admin/api/"):]
    if rel not in ("summary", "events") and not (
        rel.startswith("events/") and len(rel.split("/")) == 2 and
        1 <= len(rel.rsplit("/", 1)[-1]) <= 80 and
        all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for c in rel.rsplit("/", 1)[-1])
    ):
        return JSONResponse({"error": "Unsupported admin route"}, status_code=404, headers=_HEADERS)
    query = ("?" + request.url.query) if request.url.query else ""
    url = api_origin + "/internal/admin/v1/" + rel + query
    try:
        upstream = await request.app.state.http.get(
            url, headers={"authorization": "Bearer " + os.environ["DRAGONZPYDER_ADMIN_TOKEN"]},
            timeout=20)
    except httpx.HTTPError:
        return JSONResponse({"error": "Inference admin API unavailable"},
                            status_code=502, headers=_HEADERS)
    return Response(content=upstream.content, media_type="application/json",
                    status_code=upstream.status_code, headers=_HEADERS)
