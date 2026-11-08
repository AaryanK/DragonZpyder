"""Exactly-once, low-risk virtual file round-trip using a real model in staging.

The metered private gateway MUST prove an enforced <=$0.50 upstream key cap
before each model request. Nothing here grants shell, browser or external writes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

import httpx

from .frontier_stress import live_eval_enabled
from .runtime import AgentRuntime
from .staging_smokes import gateway_readiness

logger = logging.getLogger("dragonzpyder.paid_tool_smoke")
RUN_KEY = "paid-tool-smoke-20261108-v1"
ARTIFACT = "/workspace/tool_smoke_20261108.txt"


async def _gateway_guard_ready() -> bool:
    base = os.getenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "")
    token = os.getenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "")
    if (not base.startswith("http://dragonzpyder-gateway.railway.internal:8080/")
            or not base.endswith("/internal/agent/v1") or len(token) < 32):
        return False
    url = base.removesuffix("/internal/agent/v1") + "/internal/v1/health"
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            res = await client.get(url, headers={"Authorization": "Bearer " + token})
        return res.status_code == 200 and res.json().get("paid_test_cap_guard") is True
    except (httpx.HTTPError, ValueError):
        return False


async def run_paid_tool_smoke_once() -> None:
    if os.getenv("DRAGONZPYDER_STAGING_PAID_TOOL_SMOKE_ONCE") != "1":
        return
    if not live_eval_enabled():
        logger.warning("Paid tool smoke skipped: explicit metered agent evaluation flags absent")
        return
    if await gateway_readiness() != "metered_gateway_ready" or not await _gateway_guard_ready():
        logger.warning("Paid tool smoke skipped: private gateway $0.50 cap guard not ready")
        return
    from asyncpg import connect
    dsn = os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        logger.warning("Paid tool smoke skipped: persistent reservation database missing")
        return
    try:
        conn = await connect(dsn, timeout=7, command_timeout=7)
        try:
            await conn.execute(
                """CREATE TABLE IF NOT EXISTS dz_staging_paid_tool_smoke (
                    run_key text PRIMARY KEY,
                    started_at timestamptz NOT NULL DEFAULT now(),
                    finished_at timestamptz,
                    status text NOT NULL DEFAULT 'reserved',
                    metrics jsonb
                )"""
            )
            inserted = await conn.fetchval(
                """INSERT INTO dz_staging_paid_tool_smoke(run_key)
                   VALUES($1) ON CONFLICT DO NOTHING RETURNING run_key""", RUN_KEY
            )
            if not inserted:
                old = await conn.fetchval(
                    "SELECT status FROM dz_staging_paid_tool_smoke WHERE run_key=$1",
                    RUN_KEY,
                )
                logger.warning("Paid tool smoke already claimed, status=%s", old or "unknown")
                return
        finally:
            await conn.close()
    except Exception:
        logger.error("Paid tool smoke declined: unable to durably reserve single attempt")
        return
    started = time.monotonic()
    result = {"status": "aborted", "write_verified": False,
              "readback_verified": False, "objective_verified": False}
    runtime = AgentRuntime()
    try:
        await runtime.start()
        prompt = (
            "This is a small authorized test of virtual tools only. Do not "
            "delegate, research, or use external actions. Use write_file to "
            "write the exact text DRAGONZPYDER-STAGING-TEST-20261108 to "
            "/workspace/tool_smoke_20261108.txt. Then call read_file on "
            "that same path. Reply in one sentence after receiving both tool "
            "results. If tools are unavailable, stop and say so."
        )
        report = await asyncio.wait_for(
            runtime.run_report(
                service_id="paid-tool-smoke",
                thread_id="one-shot-20261108-v1",
                prompt=prompt,
            ),
            timeout=85,
        )
        tools = set(report.get("successful_tools", []))
        written = ("write_file" in tools or "edit_file" in tools) and (
            ARTIFACT in report.get("virtual_artifact_paths", [])
        )
        readback = "read_file" in tools and ARTIFACT in report.get(
            "artifact_readback_paths", []
        )
        result.update({
            "status": "virtual_roundtrip_observed" if written and readback else "insufficient_tool_evidence",
            "write_verified": written,
            "readback_verified": readback,
            "successful_tool_count": len(report.get("successful_tools", [])),
            "failed_tool_count": report.get("failed_tool_count", 0),
        })
    except Exception as exc:
        root = exc.__cause__ or exc
        result.update({"status": "execution_failed",
                       "exception_type": type(root).__name__,
                       "error_phase": getattr(exc, "phase", "unknown")})
    finally:
        await runtime.close()
    result["elapsed_s"] = round(time.monotonic() - started, 2)
    # No model text, user content, credentials, or tool arguments are logged.
    try:
        conn = await connect(dsn, timeout=7, command_timeout=7)
        try:
            await conn.execute(
                """UPDATE dz_staging_paid_tool_smoke
                   SET status=$2, metrics=$3::jsonb, finished_at=now()
                   WHERE run_key=$1""",
                RUN_KEY, result["status"], json.dumps(result)
            )
        finally:
            await conn.close()
    except Exception:
        logger.error("Paid tool smoke metrics persistence failed")
    logger.warning(
        "Paid tool smoke result=%s write=%s readback=%s calls=%s elapsed_s=%s",
        result["status"], result["write_verified"],
        result["readback_verified"], result.get("successful_tool_count", 0),
        result["elapsed_s"],
    )
