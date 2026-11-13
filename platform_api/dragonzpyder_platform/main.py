"""Standalone FastAPI entry point for DragonZpyder's future shared platform.

Intentionally no legacy Operly router, data store, credentials, proxy or
capability execution is mounted. A successful liveness check is NOT evidence
that the agent runtime or account migration is complete.
"""
from fastapi import FastAPI

app = FastAPI(
    title="DragonZpyder Platform API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str | bool]:
    return {
        "service": "dragonzpyder-platform-api",
        "status": "bootstrap-only",
        "runtime_ready": False,
    }
