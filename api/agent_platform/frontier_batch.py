"""Paid, live, outcome-first DragonZpyder 10-case staging stress trial.

One durable batch claim: only one staging instance may launch the trial, and a
redeploy never retries paid calls or ambiguous provider outcomes. Each task is
the *original* 450+ word fixture, not a mocked or simplified replacement.
No external file, browser, computer, credential, or publication tools.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from decimal import Decimal, InvalidOperation
from time import monotonic

import httpx

from .frontier_stress import load_suite, live_eval_enabled, run_live_case

log = logging.getLogger("dragonzpyder.frontier_batch")
RUN_KEY = "frontier-progress-guard-f08-20261108-v4"
ORDER = ("F08",)
MIN_REMAINING_USD = Decimal("0.12")
MAX_CASE_SECONDS = 115
MAX_BATCH_SECONDS = 150
GATEWAY = "http://dragonzpyder-gateway.railway.internal:8080/internal/agent/v1"


def safe_metrics(case_id: str, report: dict) -> dict:
    """Allow only evaluator-generated metadata, never model replies or arguments."""
    keep = (
        "status", "objective_verified", "missing_capabilities",
        "artifact_files_created", "artifact_files_read_back",
        "artifact_files_required", "parallelism_observed",
        "runtime_parallelism_observed", "independent_outcome_oracle_passed",
        "delegated_calls_observed", "successful_tool_count", "failed_tool_count",
        "elapsed_s", "exception_type", "error_phase", "http_status",
        "comparison_with_frontier_labs", "termination_reason",
        "checkpoint_recovered", "langfuse_trace_id",
    )
    return {"id": case_id, **{
        field: report[field] for field in keep if field in report
    }}


def validated_budget(data: object) -> Decimal | None:
    if (not isinstance(data, dict) or data.get("approved") is not True
            or data.get("reason") != "hard_nonresetting_key_cap_verified"):
        return None
    try:
        limit = Decimal(str(data["limit_usd"]))
        balance = Decimal(str(data["remaining_usd"]))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return None
    if (not limit.is_finite() or not balance.is_finite()
            or limit <= 0 or limit > Decimal("0.50")
            or balance < 0 or balance > limit):
        return None
    return balance


async def gateway_balance(client: httpx.AsyncClient, token: str) -> Decimal | None:
    try:
        res = await client.get(
            GATEWAY + "/key-budget",
            headers={"Authorization": "Bearer " + token},
            timeout=11,
        )
        return validated_budget(res.json()) if res.status_code == 200 else None
    except (httpx.HTTPError, ValueError, TypeError):
        return None


async def run_frontier_batch_once() -> None:
    if os.getenv("DRAGONZPYDER_STAGING_FRONTIER_BATCH_ONCE") != "1":
        return
    if not live_eval_enabled() or os.getenv("DRAGONZPYDER_STAGING_FRONTIER_CANARY_ONCE") == "1":
        log.warning("Frontier batch blocked: required paid-gateway flags or competing canary")
        return
    if os.getenv("DRAGONZPYDER_AGENT_GATEWAY_BASE_URL", "").rstrip("/") != GATEWAY:
        log.warning("Frontier batch blocked: authenticated private staging gateway required")
        return
    token = os.getenv("DRAGONZPYDER_AGENT_GATEWAY_TOKEN", "")
    dsn = os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", "")
    if len(token) < 32 or not dsn.startswith(("postgres://", "postgresql://")):
        log.warning("Frontier batch blocked: credential or durable database unavailable")
        return
    suite = {c["id"]: c for c in load_suite()}
    if set(suite) != {"F01", "F02", "F03", "F04", "F05", "F06", "F07", "F08", "F09", "F10"} or ORDER != ("F08",):
        log.error("Frontier batch blocked: fixture identity mismatch")
        return

    # Fail closed BEFORE a durable claim if the actual gateway key has
    # no non-resetting <= $0.50 provider cap. Not the lab's separate key.
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        if await gateway_balance(client, token) is None:
            log.warning("Frontier batch blocked: real gateway key budget unverified")
            return

    from asyncpg import connect
    try:
        con = await connect(dsn, timeout=8, command_timeout=10)
        try:
            await con.execute(
                """CREATE TABLE IF NOT EXISTS dz_frontier_batch_run (
                     run_key text PRIMARY KEY,
                     started_at timestamptz NOT NULL DEFAULT now(),
                     finished_at timestamptz,
                     status text NOT NULL DEFAULT 'started'
                   )"""
            )
            await con.execute(
                """CREATE TABLE IF NOT EXISTS dz_frontier_batch_case (
                     run_key text NOT NULL REFERENCES dz_frontier_batch_run(run_key),
                     case_id text NOT NULL,
                     started_at timestamptz NOT NULL DEFAULT now(),
                     finished_at timestamptz,
                     status text NOT NULL DEFAULT 'reserved',
                     metrics jsonb,
                     PRIMARY KEY (run_key, case_id)
                   )"""
            )
            claimed = await con.fetchval(
                """INSERT INTO dz_frontier_batch_run(run_key)
                   VALUES($1) ON CONFLICT DO NOTHING RETURNING run_key""",
                RUN_KEY,
            )
        finally:
            await con.close()
        if not claimed:
            log.warning("Frontier batch already claimed; refusing duplicate paid work")
            return
        # The earlier F07 attempt is already part of this ten-case study.
        # Inspect its sanitized diagnostic, never prompt or provider output.
        try:
            con = await connect(dsn, timeout=8, command_timeout=10)
            try:
                old = await con.fetchval(
                    """SELECT metrics FROM dz_frontier_batch_case
                       WHERE run_key=$1 AND case_id='F07'""",
                    "frontier-ten-20261108-real-v1",
                )
            finally:
                await con.close()
            if isinstance(old, str):
                old = json.loads(old)
            if isinstance(old, dict):
                log.warning(
                    "Frontier earlier F07 diagnostic status=%s exception_type=%s "
                    "error_phase=%s http_status=%s",
                    old.get("status"), old.get("exception_type"),
                    old.get("error_phase"), old.get("http_status"),
                )
        except Exception:
            log.warning("Frontier earlier F07 diagnostic unavailable")
    except Exception:
        log.error("Frontier batch refused: durable exactly-once claim unavailable")
        return

    started = monotonic()
    complete = 0
    verified = 0
    attempted = 0
    overall_status = "completed"
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        for case_id in ORDER:
            # Avoid firing consecutive provider bursts after the baseline 429s.
            # No inference occurs during this cooldown.
            if attempted:
                await asyncio.sleep(45)
            if monotonic() - started > MAX_BATCH_SECONDS:
                overall_status = "time_budget_exhausted"
                break
            before = await gateway_balance(client, token)
            if before is None:
                overall_status = "provider_key_cap_unverified"
                break
            if before < MIN_REMAINING_USD:
                overall_status = "provider_key_budget_low"
                break
            # Durable per-case claim is written before any model inference.
            try:
                con = await connect(dsn, timeout=8, command_timeout=10)
                try:
                    row = await con.fetchval(
                        """INSERT INTO dz_frontier_batch_case(run_key,case_id)
                           VALUES($1,$2) ON CONFLICT DO NOTHING RETURNING case_id""",
                        RUN_KEY, case_id,
                    )
                finally:
                    await con.close()
                if not row:
                    overall_status = "duplicate_case_claim"
                    break
            except Exception:
                overall_status = "case_claim_database_unavailable"
                break
            attempted += 1
            log.warning("Frontier live case starting id=%s remaining_before_usd=%s",
                        case_id, before)
            try:
                raw = await asyncio.wait_for(
                    run_live_case(case_id),
                    timeout=MAX_CASE_SECONDS,
                )
                report = safe_metrics(case_id, raw)
            except asyncio.TimeoutError:
                report = {
                    "id": case_id, "status": "deadline_exceeded",
                    "objective_verified": False,
                }
            except Exception as exc:
                # No provider text, arguments, secrets, exception messages.
                report = {
                    "id": case_id, "status": "execution_failed",
                    "objective_verified": False,
                    "exception_type": type(exc).__name__,
                }
            from .frontier_stress import CAPABILITIES
            report.setdefault(
                "missing_capabilities",
                sorted(set(suite[case_id]["required_capabilities"]) - CAPABILITIES),
            )
            after = await gateway_balance(client, token)
            report["provider_remaining_before_usd"] = str(before)
            if after is not None:
                report["provider_remaining_after_usd"] = str(after)
                if after <= before:
                    report["observed_key_delta_usd"] = str(before - after)
            report["objective_verified"] = False if report.get("objective_verified") is not True else True
            try:
                con = await connect(dsn, timeout=8, command_timeout=10)
                try:
                    await con.execute(
                        """UPDATE dz_frontier_batch_case
                           SET status=$3, metrics=$4::jsonb, finished_at=now()
                           WHERE run_key=$1 AND case_id=$2""",
                        RUN_KEY, case_id, report["status"], json.dumps(report),
                    )
                finally:
                    await con.close()
            except Exception:
                overall_status = "metrics_database_unavailable"
                log.error("Frontier case persistence unavailable id=%s", case_id)
                break
            complete += 1
            if report["objective_verified"] is True:
                verified += 1
            log.warning(
                "Frontier live case result id=%s status=%s verified=%s "
                "tools=%s delegated=%s parallel=%s created=%s read_back=%s "
                "seconds=%s observed_key_delta_usd=%s exception_type=%s "
                "error_phase=%s http_status=%s missing_capabilities=%s "
                "termination_reason=%s checkpoint_recovered=%s",
                case_id, report["status"], report["objective_verified"],
                report.get("successful_tool_count", 0),
                report.get("delegated_calls_observed", 0),
                report.get("parallelism_observed", False),
                len(report.get("artifact_files_created", [])),
                len(report.get("artifact_files_read_back", [])),
                report.get("elapsed_s", "unknown"),
                report.get("observed_key_delta_usd", "unknown"),
                report.get("exception_type", "none"),
                report.get("error_phase", "none"),
                report.get("http_status", "none"),
                ",".join(report.get("missing_capabilities", [])) or "none",
                report.get("termination_reason") or "none",
                report.get("checkpoint_recovered", False),
            )
            if after is None:
                overall_status = "provider_balance_unavailable_after_case"
                break
            # Timeouts, upstream provider failures and unknown-cost outcomes
            # stop this batch; never continue from an ambiguous paid outcome.
            if report["status"] == "deadline_exceeded":
                overall_status = "stopped_after_unresolved_timeout"
                break
            if report.get("http_status") == 429:
                overall_status = "stopped_after_provider_rate_limit"
                break
            # An observed graph/model error is a benchmark result. Resume
            # unrelated cases only after checking the immutable upstream cap.
    if complete != len(ORDER) and overall_status == "completed":
        overall_status = "partial"
    try:
        con = await connect(dsn, timeout=8, command_timeout=10)
        try:
            await con.execute(
                """UPDATE dz_frontier_batch_run
                   SET status=$2, finished_at=now() WHERE run_key=$1""",
                RUN_KEY, overall_status,
            )
        finally:
            await con.close()
    except Exception:
        log.error("Frontier batch completion status persistence unavailable")
    log.warning(
        "Frontier batch done status=%s completed=%d attempted=%d total=%d elapsed_s=%.2f verified=%d suite_total=%d",
        overall_status, complete, attempted, len(ORDER), monotonic()-started,
        verified, len(suite),
    )
