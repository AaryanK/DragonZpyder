"""Append-only PostgreSQL usage ledger and encrypted payload escrow.

Never treat missing provider usage as zero. Prompts and model outputs are *not*
stored unless an operator configures a separate AES-256-GCM encryption key.
The ledger is independent of OpenTelemetry sampling/export availability.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

import asyncpg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS model_usage_events (
  request_id uuid PRIMARY KEY,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  app_id text NOT NULL,
  trace_id text NOT NULL,
  requested_model text NOT NULL,
  served_model text,
  provider text NOT NULL DEFAULT 'openrouter',
  provider_generation_id text,
  status text NOT NULL,
  duration_ms integer NOT NULL,
  input_tokens bigint,
  output_tokens bigint,
  total_tokens bigint,
  cache_read_tokens bigint,
  reasoning_tokens bigint,
  provider_cost_usd numeric(20,10),
  failure_code text,
  request_sha256 text,
  response_sha256 text,
  encrypted_payload bytea
);
CREATE INDEX IF NOT EXISTS model_usage_events_time_idx ON model_usage_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS model_usage_events_app_time_idx ON model_usage_events(app_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS model_usage_events_model_time_idx ON model_usage_events(requested_model, occurred_at DESC);
"""


def safe_int(value):
    if type(value) is int and value >= 0:
        return value
    return None


def safe_cost(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            return None
        return number.quantize(Decimal("0.0000000001"))
    except (ValueError, InvalidOperation, TypeError):
        return None


def digest(value) -> str | None:
    if value is None:
        return None
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def token_usage(response) -> dict:
    usage = response.get("usage", {}) if isinstance(response, dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    details = usage.get("completion_tokens_details") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    if not isinstance(details, dict):
        details = {}
    if not isinstance(prompt_details, dict):
        prompt_details = {}
    return {
        "input_tokens": safe_int(usage.get("prompt_tokens")),
        "output_tokens": safe_int(usage.get("completion_tokens")),
        "total_tokens": safe_int(usage.get("total_tokens")),
        "cache_read_tokens": safe_int(prompt_details.get("cached_tokens")),
        "reasoning_tokens": safe_int(details.get("reasoning_tokens")),
        # Usage may omit cost entirely; never substitute zero or price estimates.
        "provider_cost_usd": safe_cost(usage.get("cost")),
    }


class UsageLedger:
    def __init__(self):
        self.pool = None
        self.encryption_key = None
        self.required = False

    async def open(self):
        self.required = os.getenv("DRAGONZPYDER_USAGE_REQUIRED", "0") == "1"
        key = os.getenv("DRAGONZPYDER_AUDIT_ENCRYPTION_KEY", "")
        if key:
            try:
                raw = base64.urlsafe_b64decode(key + "=" * (-len(key) % 4))
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid audit encryption key") from exc
            if len(raw) != 32:
                raise ValueError("Audit encryption key must contain exactly 32 bytes")
            self.encryption_key = raw
        dsn = os.getenv("DRAGONZPYDER_USAGE_DATABASE_URL", "")
        if not dsn:
            if self.required:
                raise RuntimeError("Usage database required but not configured")
            return
        try:
            self.pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4, command_timeout=7)
            async with self.pool.acquire() as con:
                await con.execute(SCHEMA)
        except Exception:
            log.exception("Usage ledger database setup failed")
            if self.pool is not None:
                await self.pool.close()
                self.pool = None
            if self.required:
                raise

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    @property
    def available(self) -> bool:
        return self.pool is not None

    def encrypt(self, request_payload, response_payload, request_id: str):
        if self.encryption_key is None:
            return None
        import secrets
        nonce = secrets.token_bytes(12)
        data = json.dumps({"request": request_payload, "response": response_payload},
                          ensure_ascii=False, separators=(",", ":")).encode()
        return nonce + AESGCM(self.encryption_key).encrypt(nonce, data, request_id.encode())

    async def record(self, *, request_id: str, app_id: str, trace_id: str,
                     requested_model: str, served_model: str | None,
                     generation_id: str | None, status: str, duration_ms: int,
                     response: dict | None, request_payload: dict | None,
                     failure_code: str | None = None):
        if self.pool is None:
            return False
        usage = token_usage(response)
        sealed = self.encrypt(request_payload, response, request_id)
        try:
            async with self.pool.acquire() as con:
                await con.execute(
                    """INSERT INTO model_usage_events
                    (request_id,app_id,trace_id,requested_model,served_model,
                     provider_generation_id,status,duration_ms,input_tokens,
                     output_tokens,total_tokens,cache_read_tokens,reasoning_tokens,
                     provider_cost_usd,failure_code,request_sha256,response_sha256,
                     encrypted_payload)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
                    ON CONFLICT(request_id) DO NOTHING""",
                    UUID(request_id), app_id, trace_id, requested_model, served_model,
                    generation_id, status, duration_ms,
                    usage["input_tokens"], usage["output_tokens"], usage["total_tokens"],
                    usage["cache_read_tokens"], usage["reasoning_tokens"],
                    usage["provider_cost_usd"], failure_code, digest(request_payload),
                    digest(response), sealed,
                )
            return True
        except Exception:
            log.exception("Failed to persist model usage event %s", request_id)
            if self.required:
                raise
            return False

    async def summary(self, *, days: int = 30, app_id: str | None = None):
        if not self.pool:
            return None
        days = max(1, min(days, 90))
        async with self.pool.acquire() as con:
            totals = await con.fetchrow(
                """SELECT COUNT(*) AS calls, COUNT(*) FILTER (WHERE status <> 'ok') AS failures,
                   COALESCE(SUM(input_tokens),0) AS input_tokens,
                   COALESCE(SUM(output_tokens),0) AS output_tokens,
                   COALESCE(SUM(total_tokens),0) AS total_tokens,
                   SUM(provider_cost_usd) AS provider_cost_usd,
                   COUNT(*) FILTER (WHERE total_tokens IS NULL) AS missing_token_usage,
                   COUNT(*) FILTER (WHERE provider_cost_usd IS NULL) AS missing_cost
                   FROM model_usage_events
                   WHERE occurred_at >= now() - ($1::int * interval '1 day')
                   AND ($2::text IS NULL OR app_id = $2)""", days, app_id)
            group = await con.fetch(
                """SELECT app_id, requested_model, COUNT(*) AS calls,
                   SUM(input_tokens) AS input_tokens,
                   SUM(output_tokens) AS output_tokens,
                   SUM(total_tokens) AS total_tokens,
                   SUM(provider_cost_usd) AS provider_cost_usd
                   FROM model_usage_events
                   WHERE occurred_at >= now() - ($1::int * interval '1 day')
                   AND ($2::text IS NULL OR app_id = $2)
                   GROUP BY app_id, requested_model ORDER BY calls DESC LIMIT 200""", days, app_id)
        def json_safe(row):
            return {k: str(v) if isinstance(v, Decimal) else v for k, v in dict(row).items()}
        return {"days": days, "app_id": app_id, "totals": json_safe(totals),
                "groups": [json_safe(row) for row in group]}


ledger = UsageLedger()
