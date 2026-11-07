"""Password-gated staging smoke lab. Never grants workspace or computer tools."""
import asyncio
from datetime import datetime, timedelta, timezone
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
from agent_platform.web_research import search_sources, SearchUnavailable
from agent_platform.frontier_stress import run_live_case, live_eval_enabled
from agent_platform.staging_smokes import hatchet_readiness, vector_readiness, gateway_readiness, synthetic_memory_smoke

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
        "web_search": env.get("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED") == "1",
        "web_monitor": env.get("DRAGONZPYDER_WEB_MONITOR_ENABLED") == "1",
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


async def public_web_search_smoke() -> tuple[str, int]:
    """One bounded external GET with no LLM inference, only when opted in."""
    if os.getenv("DRAGONZPYDER_STAGING_WEB_SEARCH_LIVE_SMOKE") != "1":
        return "disabled", 0
    try:
        report = await asyncio.wait_for(
            search_sources("George Washington", provider="wikipedia", limit=1),
            timeout=14,
        )
    except Exception:
        # Never log provider payloads or exception messages.
        return "failed", 0
    count = len(report.get("results", []))
    return ("verified" if count else "empty"), count


async def run_staging_frontier_canary_once() -> None:
    """One bounded operator-approved model test, exactly once across redeploys."""
    if os.getenv("DRAGONZPYDER_STAGING_FRONTIER_CANARY_ONCE") != "1":
        return
    if not live_eval_enabled():
        logger.warning("Frontier stress canary skipped: missing metered evaluation opt-in")
        return
    from asyncpg import connect
    dsn = os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        logger.warning("Frontier stress canary skipped: no dedicated database")
        return
    # The versioned key is fixed in source. Never let user input select paid
    # prompts, number of cases or pricing limits through this boot hook.
    key = "stress-canary-v1-20261107-F08"
    try:
        conn = await connect(dsn, timeout=7, command_timeout=7)
    except Exception:
        logger.error("Frontier stress canary reservation database unavailable")
        return
    try:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS dz_staging_frontier_canary (
                run_key text PRIMARY KEY,
                case_id text NOT NULL,
                started_at timestamptz NOT NULL DEFAULT now(),
                finished_at timestamptz,
                status text NOT NULL DEFAULT 'reserved',
                metrics jsonb
            )"""
        )
        claimed = await conn.fetchval(
            """INSERT INTO dz_staging_frontier_canary(run_key, case_id)
               VALUES($1,'F08') ON CONFLICT DO NOTHING RETURNING run_key""",
            key,
        )
        if not claimed:
            existing = await conn.fetchrow(
                """SELECT status,metrics FROM dz_staging_frontier_canary
                   WHERE run_key=$1""", key,
            )
            raw_metrics = existing["metrics"] if existing else None
            if isinstance(raw_metrics, str):
                try:
                    import json as _json
                    raw_metrics = _json.loads(raw_metrics)
                except ValueError:
                    raw_metrics = None
            metrics = raw_metrics if isinstance(raw_metrics, dict) else {}
            logger.warning(
                "Frontier stress canary previously recorded status=%s "
                "failure_type=%s error_phase=%s http_status=%s "
                "elapsed_s=%s",
                existing["status"] if existing else "unknown",
                metrics.get("exception_type", "none"),
                metrics.get("error_phase", "none"),
                metrics.get("http_status", "unknown"),
                metrics.get("elapsed_s", "unknown"),
            )
            return
    except Exception:
        logger.error("Frontier stress canary reservation failed")
        return
    finally:
        await conn.close()
    result = {"id": "F08", "status": "aborted", "objective_verified": False}
    try:
        result = await run_live_case("F08")
    except Exception as exc:
        result["exception_type"] = type(exc).__name__
    # Persist only sanitized evaluator metrics, never raw prompts or model text.
    try:
        conn = await connect(dsn, timeout=7, command_timeout=7)
        try:
            import json as _json
            await conn.execute(
                """UPDATE dz_staging_frontier_canary SET
                   status=$2, metrics=$3::jsonb, finished_at=now()
                   WHERE run_key=$1""",
                key, result.get("status", "unknown"), _json.dumps(result),
            )
        finally:
            await conn.close()
    except Exception:
        logger.error("Frontier stress canary metrics persistence failed")
    logger.warning(
        "Staging frontier canary case=F08 status=%s verified=%s "
        "tools=%s elapsed_s=%s",
        result.get("status"), bool(result.get("objective_verified")),
        result.get("successful_tool_count", 0), result.get("elapsed_s", "unknown"),
    )


@asynccontextmanager
async def lifespan(app):
    app.state.runtime = None
    app.state.runtime_error = False
    app.state.provider_auth = await verify_provider_key()
    logger.warning("Staging OpenRouter key verification status=%s", app.state.provider_auth)
    hatchet_state, vector_state, gateway_state = await asyncio.gather(
        hatchet_readiness(), vector_readiness(), gateway_readiness()
    )
    logger.warning(
        "Staging infrastructure readiness hatchet=%s pgvector=%s agent_gateway=%s",
        hatchet_state, vector_state, gateway_state,
    )
    app.state.public_web_smoke, source_count = await public_web_search_smoke()
    if app.state.public_web_smoke != "disabled":
        logger.warning(
            "Staging no-model public-web search smoke result=%s source_count=%d",
            app.state.public_web_smoke, source_count,
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
    stress_task = None
    if os.getenv("DRAGONZPYDER_STAGING_FRONTIER_CANARY_ONCE") == "1":
        stress_task = asyncio.create_task(run_staging_frontier_canary_once())
    try:
        yield
    finally:
        if stress_task and not stress_task.done():
            stress_task.cancel()
            try:
                await stress_task
            except asyncio.CancelledError:
                pass
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
    hatchet_status, memory_status, gateway_status = await asyncio.gather(
        hatchet_readiness(), vector_readiness(), gateway_readiness()
    )
    components["agent_inference_route"] = gateway_status
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


class SearchPrompt(BaseModel):
    query: str = Field(min_length=3, max_length=240)


search_attempts = deque(maxlen=12)
search_running = asyncio.Lock()


@app.post("/test-web-search")
async def test_web_search(
    payload: SearchPrompt,
    x_staging_password: str = Header(default=""),
):
    """Authenticated, no-model search smoke; not a public web search API."""
    password = os.getenv("DRAGONZPYDER_STAGING_PASSWORD", "")
    if len(password) < 24 or not hmac.compare_digest(password, x_staging_password):
        raise HTTPException(401, "Incorrect staging password")
    if os.getenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED") != "1":
        raise HTTPException(503, "Staging web search is disabled")
    now = time.monotonic()
    while search_attempts and search_attempts[0] < now - 3600:
        search_attempts.popleft()
    if len(search_attempts) >= 12 or search_running.locked():
        raise HTTPException(429, "Web search staging smoke limit reached")
    search_attempts.append(now)
    provider = os.getenv("DRAGONZPYDER_AGENT_SEARCH_PROVIDER", "wikipedia")
    async with search_running:
        try:
            data = await asyncio.wait_for(
                search_sources(payload.query, provider=provider, limit=3),
                timeout=15,
            )
        except (SearchUnavailable, ValueError, TimeoutError):
            raise HTTPException(502, "Search backend unavailable") from None
    return {
        "provider": data["provider"],
        "source_scope": data["source_scope"],
        "results": data["results"],
        "fetched_at": data["fetched_at"],
        "inference_used": False,
    }


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
            result = await asyncio.wait_for(
                asyncio.to_thread(synthetic_memory_smoke), timeout=70,
            )
            required = ("memory_written", "memory_retrieved", "vector_records_deleted")
            if not all(result.get(field) is True for field in required):
                logger.warning(
                    "Synthetic memory verification incomplete: %s",
                    ",".join(field for field in required if result.get(field) is not True),
                )
                raise RuntimeError("Synthetic memory verification failed")
            return result
        except Exception as exc:
            reference = uuid.uuid4().hex[:12]
            log_safe_failure(exc, reference)
            raise HTTPException(
                502,
                "Synthetic memory smoke failed; check staging logs. Reference: " + reference
            ) from None


hatchet_attempts = deque(maxlen=10)
hatchet_running = asyncio.Lock()


@app.post("/test-hatchet")
async def test_hatchet(x_staging_password: str = Header(default="")):
    """Execute exactly one synthetic ping through Hatchet, never a model task."""
    password = os.getenv("DRAGONZPYDER_STAGING_PASSWORD", "")
    if len(password) < 24 or not hmac.compare_digest(password, x_staging_password):
        raise HTTPException(401, "Incorrect staging password")
    if os.getenv("DRAGONZPYDER_HATCHET_TEST_ENABLED") != "1":
        raise HTTPException(503, "Hatchet acceptance test is disabled")
    if not os.getenv("HATCHET_CLIENT_TOKEN"):
        raise HTTPException(503, "Hatchet worker credential unavailable")
    now = time.monotonic()
    while hatchet_attempts and hatchet_attempts[0] < now - 3600:
        hatchet_attempts.popleft()
    if len(hatchet_attempts) >= 3 or hatchet_running.locked():
        raise HTTPException(429, "Hatchet smoke test rate limit reached")
    hatchet_attempts.append(now)
    async with hatchet_running:
        try:
            from hatchet_sdk import Hatchet
            from agent_platform.jobs import PingInput, make_ping_task
            client = Hatchet()
            task = make_ping_task(client)
            result = await asyncio.wait_for(
                task.aio_run(PingInput(message="staging-healthcheck")),
                timeout=35,
            )
            if hasattr(result, "model_dump"):
                result = result.model_dump()
            if not isinstance(result, dict) or result.get("ok") is not True:
                # Synthetic output only; log type and key names, not arbitrary values.
                root_keys = [str(k)[:72] for k in result.keys()][:8] if isinstance(result, dict) else []
                child_types = [type(v).__name__ for v in result.values()][:8] if isinstance(result, dict) else []
                logger.warning("Hatchet ping result shape type=%s keys=%s child_types=%s",
                               type(result).__name__, root_keys, child_types)
                raise RuntimeError("Hatchet returned an unexpected ping result")
            return {"task": "dragonzpyder-staging-ping", "worker_executed": True,
                    "result": {"ok": True, "message": result.get("message")}}
        except Exception as exc:
            reference = uuid.uuid4().hex[:12]
            log_safe_failure(exc, reference)
            raise HTTPException(502, "Hatchet smoke test failed; inspect staging logs. Reference: " + reference) from None



scheduled_attempts = deque(maxlen=10)
scheduled_lock = asyncio.Lock()


@app.post("/test-hatchet-schedule")
async def test_hatchet_schedule(x_staging_password: str = Header(default="")):
    """Schedule ONE synthetic ping for 20 seconds later, without an LLM."""
    password = os.getenv("DRAGONZPYDER_STAGING_PASSWORD", "")
    if len(password) < 24 or not hmac.compare_digest(password, x_staging_password):
        raise HTTPException(401, "Incorrect staging password")
    if os.getenv("DRAGONZPYDER_HATCHET_TEST_ENABLED") != "1" or not os.getenv("HATCHET_CLIENT_TOKEN"):
        raise HTTPException(503, "Hatchet staging scheduling is disabled")
    now = time.monotonic()
    while scheduled_attempts and scheduled_attempts[0] < now - 3600:
        scheduled_attempts.popleft()
    if len(scheduled_attempts) >= 2 or scheduled_lock.locked():
        raise HTTPException(429, "Scheduling test rate limit reached")
    scheduled_attempts.append(now)
    async with scheduled_lock:
        from hatchet_sdk import Hatchet
        from agent_platform.jobs import PingInput, make_ping_task
        run_at = datetime.now(tz=timezone.utc) + timedelta(seconds=20)
        try:
            task = make_ping_task(Hatchet())
            await asyncio.wait_for(
                task.aio_schedule(
                    run_at=run_at,
                    input=PingInput(message="delayed-staging-ping"),
                ),
                timeout=12,
            )
        except Exception as exc:
            reference = uuid.uuid4().hex[:12]
            log_safe_failure(exc, reference)
            raise HTTPException(
                502, "Hatchet did not accept schedule. Reference: " + reference
            ) from None
        return {
            "task": "dragonzpyder-staging-ping",
            "accepted_by_scheduler": True,
            "scheduled_at_utc": run_at.isoformat(),
            "execution_verified": False,
            "next_step": "Check Hatchet dashboard under Runs for delayed-staging-ping",
        }
