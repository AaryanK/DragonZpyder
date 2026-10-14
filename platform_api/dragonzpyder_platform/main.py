"""Standalone FastAPI entry point for DragonZpyder's future shared platform.

Intentionally no legacy Operly router, data store, credentials, proxy or
capability execution is mounted. A successful liveness check is NOT evidence
that the agent runtime or account migration is complete.
"""
from fastapi import FastAPI, Request
from .demo import router as demo_router

app = FastAPI(
    title="DragonZpyder Platform API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    )
    return response


app.include_router(demo_router)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str | bool]:
    return {
        "service": "dragonzpyder-platform-api",
        "status": "bootstrap-only",
        "runtime_ready": False,
    }
