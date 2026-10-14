"""OpenTelemetry + Langfuse export and persistent inference accounting.

The ledger is deliberately independent of Langfuse: trace export can fail
without losing billing records. Input/output content is never stored or
exported by default. Content capture requires an explicit encrypted key.
"""
from __future__ import annotations

import base64
import hmac
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import asyncpg
from cryptography.fernet import Fernet
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.propagate import extract
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import SpanKind

_tracer = trace.get_tracer("dragonzpyder.inference")
_export_configured = False


def configure_otel() -> None:
    """Export every span when operator-provided Langfuse credentials exist."""
    global _tracer, _export_configured
    public = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    private = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not public or not private:
        _tracer = trace.get_tracer("dragonzpyder.inference")
        return
    host = os.getenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com").rstrip("/")
    # A fixed operator-controlled destination; credentials must never be sent
    # to a model-chosen URL or a browser-controlled endpoint.
    if not host.startswith("https://"):
        raise ValueError("LANGFUSE_BASE_URL must be HTTPS")
    auth = base64.b64encode((public + ":" + private).encode()).decode()
    provider = TracerProvider(resource=Resource.create({
        "service.name": "dragonzpyder-inference", "service.namespace": "dragonzpyder",
    }))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
        endpoint=host + "/api/public/otel/v1/traces",
        headers={"Authorization": "Basic " + auth, "x-langfuse-ingestion-version": "4"},
        timeout=10,
    )))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("dragonzpyder.inference")
    _export_configured = True


@contextmanager
def model_span(headers: dict[str, str], *, app_id: str, model: str):
    parent: Context = extract(headers)
    with _tracer.start_as_current_span(
        "dragonzpyder.chat.completion", context=parent, kind=SpanKind.SERVER,
        attributes={"gen_ai.operation.name": "chat", "gen_ai.system": "openrouter",
                    "gen_ai.request.model": model, "dragonzpyder.app.id": app_id},
    ) as span:
        ctx = span.get_span_context()
        trace_id = format(ctx.trace_id, "032x") if ctx.is_valid else uuid.uuid4().hex
        yield span, trace_id


def provider_observation(span, *, model: str, result: dict, duration_ms: int) -> None:
    span.set_attribute("gen_ai.response.model", str(result.get("model") or model))
    span.set_attribute("dragonzpyder.provider.latency_ms", duration_ms)
    if result.get("id"):
        span.set_attribute("gen_ai.response.id", str(result["id"]))
    usage = result.get("usage") or {}
    for key, attr in (("prompt_tokens", "gen_ai.usage.input_tokens"),
                      ("completion_tokens", "gen_ai.usage.output_tokens"),
                      ("total_tokens", "gen_ai.usage.total_tokens")):
        if type(usage.get(key)) is int and usage[key] >= 0:
            span.set_attribute(attr, usage[key])
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    for value, attr in ((prompt_details.get("cached_tokens"), "gen_ai.usage.cache_read.input_tokens"),
                        (completion_details.get("reasoning_tokens"), "gen_ai.usage.reasoning.output_tokens")):
        if type(value) is int and value >= 0:
            span.set_attribute(attr, value)
    if isinstance(usage.get("cost"), (int, float)) and usage["cost"] >= 0:
        span.set_attribute("gen_ai.usage.cost", float(usage["cost"]))


def client_identity(request) -> str:
    """Map an API credential to a stable trusted app ID; never trust app headers."""
    header = request.headers.get("authorization", "")
    bearer = header[7:] if header.startswith("Bearer ") else ""
    configured = os.getenv("DRAGONZPYDER_CLIENT_TOKENS", "{}")
    try:
        clients = json.loads(configured)
    except ValueError:
        clients = {}
    if isinstance(clients, dict):
        for app_id, token in clients.items():
            if (isinstance(app_id, str) and isinstance(token, str)
                    and len(token) >= 32 and hmac.compare_digest(bearer, token)):
                return app_id[:80]
    legacy = os.getenv("DRAGONZPYDER_RUNTIME_TOKEN", "")
    if len(legacy) >= 32 and hmac.compare_digest(bearer, legacy):
        return "legacy-internal"
    return ""


def content_cipher() -> Fernet | None:
    if os.getenv("DRAGONZPYDER_CAPTURE_MODEL_PAYLOADS") != "true":
        return None
    key = os.getenv("DRAGONZPYDER_AUDIT_ENCRYPTION_KEY", "")
    if not key:
        raise ValueError("Payload capture requires DRAGONZPYDER_AUDIT_ENCRYPTION_KEY")
    return Fernet(key.encode())


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def _stored(value: Any, cipher: Fernet | None) -> bytes | None:
    return cipher.encrypt(_json(value).encode()) if cipher else None


class UsageLedger:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None
        self.cipher: Fernet | None = None

    async def connect(self):
        self.cipher = content_cipher()
        url = os.getenv("DRAGONZPYDER_LEDGER_DATABASE_URL", "").strip()
        if not url:
            return
        self.pool = await asyncpg.create_pool(url, min_size=1, max_size=5, command_timeout=15)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS inference_usage (
                    request_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    requested_model TEXT NOT NULL,
                    actual_model TEXT,
                    provider TEXT NOT NULL DEFAULT 'openrouter',
                    generation_id TEXT,
                    status TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    completed_at TIMESTAMPTZ,
                    duration_ms INTEGER,
                    input_tokens BIGINT,
                    output_tokens BIGINT,
                    total_tokens BIGINT,
                    cost_usd NUMERIC(20, 12),
                    usage JSONB,
                    error_code TEXT,
                    request_encrypted BYTEA,
                    response_encrypted BYTEA
                )
            """)
            await conn.execute("""CREATE INDEX IF NOT EXISTS inference_usage_by_app
                ON inference_usage (app_id, started_at DESC)""")
            await conn.execute("""CREATE INDEX IF NOT EXISTS inference_usage_by_model
                ON inference_usage (requested_model, started_at DESC)""")
            await conn.execute("""CREATE INDEX IF NOT EXISTS inference_usage_by_trace
                ON inference_usage (trace_id)""")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS inference_content_access (
                    id BIGSERIAL PRIMARY KEY,
                    request_id TEXT NOT NULL REFERENCES inference_usage(request_id),
                    accessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    admin_actor TEXT NOT NULL
                )
            """)

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    @property
    def configured(self) -> bool:
        return self.pool is not None

    async def begin(self, request_id: str, trace_id: str, app_id: str,
                    body: dict) -> None:
        if not self.pool:
            if os.getenv("DRAGONZPYDER_REQUIRE_LEDGER") == "true":
                raise RuntimeError("Durable usage ledger is not configured")
            return
        await self.pool.execute("""
            INSERT INTO inference_usage
            (request_id,trace_id,app_id,requested_model,status,request_encrypted)
            VALUES ($1,$2,$3,$4,'pending',$5)
        """, request_id, trace_id, app_id, body["model"], _stored(body, self.cipher))

    async def complete(self, request_id: str, *, status: str,
                       duration_ms: int, result: dict | None = None,
                       error_code: str | None = None) -> None:
        if not self.pool:
            return
        result = result or {}
        usage = result.get("usage") or {}
        def count(name):
            value = usage.get(name)
            return value if type(value) is int and value >= 0 else None
        cost = usage.get("cost")
        try:
            cost_usd = Decimal(str(cost)) if cost is not None else None
            if cost_usd is not None and (not cost_usd.is_finite() or cost_usd < 0):
                cost_usd = None
        except (ValueError, ArithmeticError):
            cost_usd = None
        await self.pool.execute("""
            UPDATE inference_usage SET
            status=$2, completed_at=now(), duration_ms=$3, actual_model=$4,
            generation_id=$5, input_tokens=$6, output_tokens=$7, total_tokens=$8,
            cost_usd=$9, usage=$10::jsonb, error_code=$11, response_encrypted=$12
            WHERE request_id=$1
        """, request_id, status, duration_ms,
             str(result.get("model") or "")[:120] or None,
             str(result.get("id") or "")[:200] or None,
             count("prompt_tokens"), count("completion_tokens"), count("total_tokens"),
             cost_usd, _json(usage), error_code,
             _stored(result, self.cipher))

    async def summary(self, days: int = 7) -> dict:
        if not self.pool:
            return {"configured": False, "records": 0, "by_app": [], "by_model": [],
                    "message": "Configure a durable PostgreSQL ledger to collect usage."}
        days = max(1, min(90, days))
        async with self.pool.acquire() as conn:
            totals = await conn.fetchrow("""
                SELECT COUNT(*) AS calls, COALESCE(SUM(input_tokens),0) AS input_tokens,
                       COALESCE(SUM(output_tokens),0) AS output_tokens,
                       COALESCE(SUM(cost_usd),0) AS cost_usd,
                       COUNT(*) FILTER (WHERE status='pending') AS pending,
                       COUNT(*) FILTER (WHERE input_tokens IS NULL) AS unknown_usage
                  FROM inference_usage
                 WHERE started_at >= NOW() - ($1::int * INTERVAL '1 day')
            """, days)
            breakdowns = {}
            for field, name in (("app_id", "by_app"), ("requested_model", "by_model")):
                rows = await conn.fetch(f"""
                    SELECT {field} AS key, COUNT(*) AS calls,
                           COALESCE(SUM(input_tokens),0) AS input_tokens,
                           COALESCE(SUM(output_tokens),0) AS output_tokens,
                           COALESCE(SUM(cost_usd),0) AS cost_usd
                      FROM inference_usage
                     WHERE started_at >= NOW() - ($1::int * INTERVAL '1 day')
                     GROUP BY {field} ORDER BY calls DESC LIMIT 40
                """, days)
                breakdowns[name] = [dict(row) for row in rows]
        return {"configured": True, "days": days, "records": totals["calls"],
                "totals": dict(totals), **breakdowns}

    async def events(self, limit=50, *, app_id=None):
        if not self.pool:
            return []
        return [dict(row) for row in await self.pool.fetch("""
            SELECT request_id,trace_id,app_id,requested_model,actual_model,
                   generation_id,status,started_at,completed_at,duration_ms,
                   input_tokens,output_tokens,total_tokens,cost_usd,error_code
              FROM inference_usage
             WHERE ($1::text IS NULL OR app_id=$1)
             ORDER BY started_at DESC LIMIT $2
        """, app_id, max(1, min(200, limit)))]

    async def event(self, request_id: str, *, reveal: bool, actor: str) -> dict | None:
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("""
                    SELECT * FROM inference_usage WHERE request_id=$1
                """, request_id)
                if not row:
                    return None
                entry = dict(row)
                raw_req = entry.pop("request_encrypted", None)
                raw_res = entry.pop("response_encrypted", None)
                if reveal:
                    if not self.cipher:
                        raise PermissionError("Encrypted payload capture is not enabled")
                    await conn.execute("""
                        INSERT INTO inference_content_access(request_id,admin_actor)
                        VALUES($1,$2)
                    """, request_id, actor[:80])
                    entry["request"] = _json_or_none(self.cipher, raw_req)
                    entry["response"] = _json_or_none(self.cipher, raw_res)
                return entry


def _json_or_none(cipher: Fernet, data: bytes | None):
    return json.loads(cipher.decrypt(data).decode()) if data else None


ledger = UsageLedger()
