"""Password-gated staging smoke lab. Never grants workspace or computer tools."""
import asyncio
import hmac
import httpx
import logging
import os
import time
import traceback
import uuid
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from agent_platform.runtime import AgentRuntime, AgentPipelineError
from agent_platform.staging_smokes import hatchet_readiness, vector_readiness, synthetic_memory_smoke

logger = logging.getLogger("dragonzpyder.staging")


def safe_failure(error: Exception) -> tuple[str, int]:
    """Classify without exposing provider messages, prompts or secret values."""
    root = error.__cause__ if isinstance(error, AgentPipelineError) and error.__cause__ else error
    code = getattr(root, "status_code", None)
    response = getattr(root, "response", None)
    if not isinstance(code, int):
        code = getattr(response, "status_code", None)
    phase = error.phase if isinstance(error, AgentPipelineError) else "unknown"
    if code == 401 or code == 403:
        return "Model provider rejected authentication or access.", 502
    if code == 402:
        return "Model provider reported insufficient credits.", 502
    if code == 429:
        return "Model provider rate limit reached.", 502
    if code in (400, 404, 422):
        return "Selected model or request format was rejected by provider.", 502
    if phase == "construction":
        return "Agent graph construction failed. See staging diagnostics.", 502
    if phase == "execution":
        return "Agent execution failed. See staging diagnostics.", 502
    return "Staging agent failed. See staging diagnostics.", 502


def log_safe_failure(error: Exception, reference: str) -> None:
    root = error.__cause__ if isinstance(error, AgentPipelineError) and error.__cause__ else error
    code = getattr(root, "status_code", None)
    if not isinstance(code, int):
        code = getattr(getattr(root, "response", None), "status_code", None)
    # Do not print exception messages: some SDK errors contain request text.
    frames = traceback.extract_tb(root.__traceback__)
    summary = [f"{frame.name}:{frame.lineno}" for frame in frames[-6:]]
    logger.error(
        "Agent smoke failure ref=%s phase=%s type=%s http_code=%s frames=%s",
        reference,
        getattr(error, "phase", "unknown"),
        type(root).__name__,
        code if isinstance(code, int) else "unknown",
        ",".join(summary),
    )


UI = Path(__file__).with_name("staging_ui.html")
attempts = deque(maxlen=40)
running = asyncio.Lock()

class Prompt(BaseModel):
    thread_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    prompt: str = Field(min_length=1, max_length=1600)

def configured():
    env = os.environ
    return {
        "deep_agents_langgraph": bool(env.get("DRAGONZPYDER_AGENTS_ENABLED") == "1" and env.get("DRAGONZPYDER_AGENT_DATABASE_URL") and env.get("DRAGONZPYDER_AGENT_MODEL_ID")),
        "openrouter": bool(env.get("OPENROUTER_API_KEY")),
        "langfuse": bool(env.get("DRAGONZPYDER_LANGFUSE_PUBLIC_KEY") or env.get("LANGFUSE_PUBLIC_KEY")),
        "hatchet": bool(env.get("HATCHET_CLIENT_TOKEN")),
        "mem0_postgres": bool(env.get("DRAGONZPYDER_MEMORY_DATABASE_URL") and (
            env.get("DRAGONZPYDER_EMBEDDING_API_KEY") or env.get("DRAGONZPYDER_USE_OPENROUTER_EMBEDDINGS") == "1"
        )),
        "operly_computer": bool(env.get("DRAGONZPYDER_COMPUTER_RUNNER_URL") and env.get("DRAGONZPYDER_COMPUTER_RUNNER_TOKEN")),
    }

async def verify_provider_key() -> str:
    """Verify key validity without an inference call or exposing account data."""
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        return "missing"
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/key",
                headers={"Authorization": "Bearer " + key},
            )
    except httpx.HTTPError:
        return "unreachable"
    if response.status_code == 200:
        return "verified"
    if response.status_code in (401, 403):
        return "rejected"
    if response.status_code == 429:
        return "rate_limited"
    return "unverified"


@asynccontextmanager
async def lifespan(app):
    app.state.runtime = None
    app.state.runtime_error = False
    app.state.provider_auth = await verify_provider_key()
    logger.warning("Staging OpenRouter key verification status=%s", app.state.provider_auth)
    hatchet_state, vector_state = await asyncio.gather(
        hatchet_readiness(), vector_readiness()
    )
    logger.warning(
        "Staging infrastructure readiness hatchet=%s pgvector=%s",
        hatchet_state, vector_state,
    )
    flags = configured()
    if flags["deep_agents_langgraph"] and flags["openrouter"]:
        runtime = AgentRuntime()
        try:
            await runtime.start()
            app.state.runtime = runtime
        except Exception:
            app.state.runtime_error = True
            await runtime.close()
    try:
        yield
    finally:
        if app.state.runtime:
            await app.state.runtime.close()

app = FastAPI(title="DragonZpyder Staging", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

@app.middleware("http")
async def headers(req, call_next):
    resp = await call_next(req)
    resp.headers["cache-control"] = "no-store"
    resp.headers["x-frame-options"] = "DENY"
    resp.headers["x-content-type-options"] = "nosniff"
    resp.headers["referrer-policy"] = "no-referrer"
    resp.headers["content-security-policy"] = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
    return resp

@app.get("/")
async def index():
    return FileResponse(UI, media_type="text/html")

@app.get("/staging.css")
async def stylesheet():
    return FileResponse(UI.with_name("staging.css"), media_type="text/css")

@app.get("/staging.js")
async def javascript():
    return FileResponse(UI.with_name("staging.js"), media_type="text/javascript")

@app.get("/healthz")
async def health():
    return {"status": "ok", "service": "dragonzpyder-staging"}

@app.get("/status")
async def status(req: Request):
    components = {
        name: ("configured_unverified" if present else "not_configured")
        for name, present in configured().items()
    }
    provider_state = req.app.state.provider_auth
    components["openrouter"] = {
        "verified": "key_verified",
        "rejected": "key_rejected",
        "missing": "missing_key",
        "rate_limited": "provider_rate_limited",
        "unreachable": "provider_unreachable",
    }.get(provider_state, "unverified")
    hatchet_status, memory_status = await asyncio.gather(
        hatchet_readiness(), vector_readiness()
    )
    components["hatchet"] = (
        "worker_connected" if hatchet_status == "server_online" and os.getenv("HATCHET_CLIENT_TOKEN")
        else hatchet_status
    )
    components["mem0_postgres"] = memory_status
    return {
        "components": components,
        "harness_ready": req.app.state.runtime is not None and provider_state == "verified",
        "openrouter_key_validation": provider_state,
        "runtime_start_error": req.app.state.runtime_error,
        "prod_connected": False,
    }

@app.post("/test")
async def test(payload: Prompt, req: Request, x_staging_password: str = Header(default="")):
    password = os.getenv("DRAGONZPYDER_STAGING_PASSWORD", "")
    if len(password)<24 or not hmac.compare_digest(password,x_staging_password):
        raise HTTPException(401,"Incorrect staging password")
    now=time.monotonic()
    while attempts and attempts[0]<now-3600:
        attempts.popleft()
    if len(attempts)>=6: raise HTTPException(429,"Smoke test limit: six runs per hour")
    if req.app.state.provider_auth == "rejected":
        raise HTTPException(503, "OpenRouter rejected the staging key. Replace OPENROUTER_API_KEY in Railway and redeploy.")
    if req.app.state.provider_auth == "rate_limited":
        raise HTTPException(503, "OpenRouter key validation was rate limited. Try again later.")
    if req.app.state.runtime is None: raise HTTPException(503,"Model or checkpoint database is not configured")
    if running.locked(): raise HTTPException(429,"A staging test is already running")
    attempts.append(now)
    async with running:
        try:
            answer = await asyncio.wait_for(req.app.state.runtime.run(
                service_id="agent-smoke", thread_id=payload.thread_id, prompt=payload.prompt), timeout=90)
            return {"answer": answer[:20000], "thread_id": payload.thread_id}
        except TimeoutError:
            raise HTTPException(504, "Test exceeded 90 seconds") from None
        except Exception as exc:
            reference = uuid.uuid4().hex[:12]
            log_safe_failure(exc, reference)
            description, status_code = safe_failure(exc)
            raise HTTPException(
                status_code,
                description + " Reference: " + reference,
            ) from None


memory_attempts = deque(maxlen=10)
memory_running = asyncio.Lock()


@app.post("/test-memory")
async def test_memory(x_staging_password: str = Header(default="")):
    password = os.getenv("DRAGONZPYDER_STAGING_PASSWORD", "")
    if len(password) < 24 or not hmac.compare_digest(password, x_staging_password):
        raise HTTPException(401, "Incorrect staging password")
    if os.getenv("DRAGONZPYDER_MEMORY_TEST_ENABLED") != "1":
        raise HTTPException(503, "Synthetic memory test is disabled")
    now = time.monotonic()
    while memory_attempts and memory_attempts[0] < now - 3600:
        memory_attempts.popleft()
    if len(memory_attempts) >= 2 or memory_running.locked():
        raise HTTPException(429, "Synthetic memory smoke limit reached")
    memory_attempts.append(now)
    async with memory_running:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(synthetic_memory_smoke), timeout=70,
            )
        except Exception as exc:
            reference = uuid.uuid4().hex[:12]
            log_safe_failure(exc, reference)
            raise HTTPException(
                502,
                "Synthetic memory smoke failed; check staging logs. Reference: " + reference
            ) from None
