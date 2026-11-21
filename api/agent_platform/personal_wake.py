"""Opt-in durable, sequential Personal MCP wake executor.

Hatchet handles scheduling, PostgreSQL fences one authorized wake at a time,
Operly reissues an exact-capability token after checking the original Personal
session on *every* wake, and LangGraph resumes the user-scoped checkpoint.

No recurring task is created by importing/registering this module. Read-only
MCP tools only until explicit audit of write/approval resumptions.
"""
from __future__ import annotations

import os
import json
import hashlib
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field


class PersonalWakeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal_id: str
    user_id: str
    session_id: str
    conversation_id: str
    sequence: int = Field(ge=0, le=20)
    total_wakes: int = Field(ge=2, le=20)
    prompt: str = Field(min_length=1, max_length=12000)


SCHEMA = """
CREATE TABLE IF NOT EXISTS dz_personal_mcp_goals (
    goal_id text PRIMARY KEY,
    user_id text NOT NULL,
    session_id text NOT NULL,
    conversation_id text NOT NULL,
    total_wakes integer NOT NULL,
    objective_hash char(64) NOT NULL,
    next_sequence integer NOT NULL DEFAULT 0,
    state text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS dz_personal_mcp_receipts (
    goal_id text NOT NULL REFERENCES dz_personal_mcp_goals(goal_id),
    sequence integer NOT NULL,
    status text NOT NULL,
    tool_names jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (goal_id, sequence)
);
"""


def _approved_url(name: str, *, path: str, public_host: str) -> str:
    url = os.getenv(name, "").strip()
    p = urlsplit(url)
    public = p.scheme == "https" and p.hostname == public_host and p.port in (None, 443)
    private = (os.getenv("DRAGONZPYDER_STAGE") == "staging"
               and p.scheme == "http" and p.hostname is not None
               and p.hostname.endswith(".railway.internal")
               and p.port in (None, 8080))
    if not (public or private) or p.path != path or p.query or p.fragment or p.username or p.password:
        raise RuntimeError("Unapproved Personal wake service endpoint")
    return url


def require_wake_gate() -> tuple[str, str, str, str, str]:
    required = (
        "DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED",
        "DRAGONZPYDER_AGENT_USE_GATEWAY",
        "DRAGONZPYDER_AGENT_PRODUCTION_MODE",
        "DRAGONZPYDER_OPERLY_MCP_ENABLED",
        "DRAGONZPYDER_OPERLY_TOOLS_ENABLED",
    )
    if any(os.getenv(flag) != "1" for flag in required):
        raise RuntimeError("Personal MCP scheduling is disabled")
    if os.getenv("DRAGONZPYDER_PERSONAL_MCP_MUTATIONS_ENABLED") == "1":
        raise RuntimeError("Personal writes cannot run on the read-only wake executor")
    dsn = os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", "")
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("Durable Personal wake PostgreSQL is required")
    service_secret = os.getenv("DRAGONZPYDER_OPERLY_MCP_SERVICE_SECRET", "")
    agent_secret = os.getenv("DRAGONZPYDER_OPERLY_PERSONAL_AGENT_TOKEN", "")
    if min(len(service_secret), len(agent_secret)) < 40:
        raise RuntimeError("Personal wake requires distinct backend authority")
    operly = _approved_url(
        "DRAGONZPYDER_OPERLY_PERSONAL_RENEW_URL",
        path="/api/internal/dragonzpyder/personal-mcp-delegation",
        public_host="operly.dragonzpyder.xyz",
    )
    dragon = _approved_url(
        "DRAGONZPYDER_OPERLY_PERSONAL_RUN_URL",
        path="/internal/agents/operly/personal/run",
        public_host="api.dragonzpyder.xyz",
    )
    return dsn, service_secret, agent_secret, operly, dragon


async def perform_personal_wake(wake: PersonalWakeInput, *, http=None) -> dict:
    import asyncpg
    # Stable caller-assigned IDs prevent a scheduled run from shifting scopes.
    try:
        UUID(wake.goal_id)
        UUID(wake.user_id)
        UUID(wake.session_id)
        UUID(wake.conversation_id)
    except ValueError:
        raise RuntimeError("Canonical user, session, conversation and goal IDs are required") from None
    dsn, service_secret, agent_secret, operly, dragon = require_wake_gate()
    objective_hash = hashlib.sha256(wake.prompt.encode("utf-8")).hexdigest()
    pool = await asyncpg.create_pool(
        dsn=dsn, min_size=1, max_size=2, timeout=10, command_timeout=150,
    )
    try:
        if (os.getenv("DRAGONZPYDER_STAGE") == "staging"
                and os.getenv("DRAGONZPYDER_PERSONAL_MCP_SCHEMA_INSTALL_ALLOWED") == "1"):
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
        # Commit the in-flight fence BEFORE requesting fresh authority or
        # invoking remote inference. If the worker dies mid-request, a later
        # Hatchet dispatch must not replay an action with unknown effects.
        async with pool.acquire() as claim_con:
            async with claim_con.transaction():
                await claim_con.execute(
                    """INSERT INTO dz_personal_mcp_goals
                       (goal_id, user_id, session_id, conversation_id, total_wakes, objective_hash)
                       VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING""",
                    wake.goal_id, wake.user_id, wake.session_id, wake.conversation_id,
                    wake.total_wakes, objective_hash,
                )
                claimed = await claim_con.fetchrow(
                    """SELECT user_id, session_id, conversation_id, total_wakes,
                              objective_hash, state, next_sequence
                       FROM dz_personal_mcp_goals WHERE goal_id=$1 FOR UPDATE""",
                    wake.goal_id,
                )
                if (claimed["user_id"], claimed["session_id"],
                    claimed["conversation_id"], claimed["total_wakes"],
                    claimed["objective_hash"]) != (
                    wake.user_id, wake.session_id, wake.conversation_id,
                    wake.total_wakes, objective_hash,
                ):
                    raise RuntimeError("Persistent goal authority changed")
                if claimed["state"] != "active" or claimed["next_sequence"] > wake.sequence:
                    return {
                        "state": claimed["state"], "next_sequence": claimed["next_sequence"],
                        "model_calls": 0,
                        "reason": ("inflight_outcome_uncertain"
                                   if claimed["state"] == "inflight" else "already_processed"),
                    }
                if claimed["next_sequence"] != wake.sequence:
                    raise RuntimeError("Out-of-order durable Personal wake")
                await claim_con.execute(
                    """UPDATE dz_personal_mcp_goals SET state='inflight',
                       updated_at=now() WHERE goal_id=$1""", wake.goal_id,
                )
        async with pool.acquire() as con:
            async with con.transaction():
                await con.execute(
                    """INSERT INTO dz_personal_mcp_goals
                       (goal_id, user_id, session_id, conversation_id, total_wakes, objective_hash)
                       VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING""",
                    wake.goal_id, wake.user_id, wake.session_id, wake.conversation_id,
                    wake.total_wakes, objective_hash,
                )
                row = await con.fetchrow(
                    """SELECT user_id, session_id, conversation_id, total_wakes, objective_hash, state, next_sequence
                       FROM dz_personal_mcp_goals WHERE goal_id=$1 FOR UPDATE""",
                    wake.goal_id,
                )
                if (row["user_id"], row["session_id"], row["conversation_id"],
                    row["total_wakes"], row["objective_hash"]) != (
                    wake.user_id, wake.session_id, wake.conversation_id,
                    wake.total_wakes, objective_hash,
                ):
                    raise RuntimeError("Persistent goal authority changed")
                if row["state"] != "inflight" or row["next_sequence"] != wake.sequence:
                    return {
                        "state": row["state"], "next_sequence": row["next_sequence"],
                        "model_calls": 0, "reason": "already_processed",
                    }
                if row["next_sequence"] != wake.sequence:
                    raise RuntimeError("Out-of-order durable Personal wake")
                own_http = http is None
                if own_http:
                    http = httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=105)
                try:
                    renewed = await http.post(
                        operly,
                        headers={"X-Operly-Agent-Service": service_secret},
                        json={
                            "user_id": wake.user_id,
                            "session_id": wake.session_id,
                            "conversation_id": wake.conversation_id,
                            "query": wake.prompt[:200],
                        },
                        timeout=12,
                    )
                    if renewed.status_code in (401, 403):
                        await con.execute(
                            """UPDATE dz_personal_mcp_goals SET state='blocked',
                               updated_at=now() WHERE goal_id=$1""",
                            wake.goal_id,
                        )
                        return {"state": "blocked", "next_sequence": wake.sequence,
                                "model_calls": 0, "reason": "personal_authority_revoked"}
                    if renewed.status_code != 200:
                        raise RuntimeError("Personal authorization service unavailable")
                    data = renewed.json()
                    if (not isinstance(data.get("access_token"), str)
                            or not isinstance(data.get("approved_tool_names"), list)):
                        raise RuntimeError("Invalid fresh Personal MCP delegation")
                    # A service flag alone cannot enforce read-only authority.
                    # Never pass a renewed mutation capability to the agent.
                    read_only_names = {
                        "workflow.list", "system.runtime.status", "tasks.list",
                    }
                    approved = sorted(
                        set(data["approved_tool_names"]) & read_only_names
                    )
                    if not approved:
                        await con.execute(
                            """UPDATE dz_personal_mcp_goals SET state='blocked',
                               updated_at=now() WHERE goal_id=$1""",
                            wake.goal_id,
                        )
                        return {"state":"blocked","next_sequence":wake.sequence,
                                "model_calls":0,"reason":"read_only_tools_unavailable"}
                    reply = await http.post(
                        dragon,
                        headers={
                            "Authorization": "Bearer " + agent_secret,
                            "X-Operly-Agent-Service": service_secret,
                        },
                        json={
                            "scope_kind": "personal",
                            "user_id": wake.user_id,
                            "session_id": wake.session_id,
                            "conversation_id": wake.conversation_id,
                            "prompt": wake.prompt,
                            "mcp_access_token": data["access_token"],
                            "approved_tool_names": approved,
                            "scheduled_wake": True,
                        },
                        timeout=100,
                    )
                    pause_reason = pause_reason_from_reply(reply)
                    if pause_reason is not None:
                        # The current wake can have unknown partial tool effects.
                        # Freeze at the SAME sequence without replaying it, and
                        # require a separate authorized recovery decision.
                        await con.execute(
                            """UPDATE dz_personal_mcp_goals SET state='paused_budget',
                               updated_at=now() WHERE goal_id=$1""", wake.goal_id,
                        )
                        return {
                            "state": "paused_budget",
                            "next_sequence": wake.sequence,
                            "model_calls": None,
                            "reason": pause_reason,
                            "requires_authorized_resume": True,
                        }
                    if reply.status_code != 200:
                        raise RuntimeError("Personal MCP agent execution rejected")
                    result = reply.json()
                    if result.get("status") not in ("completed", "incomplete"):
                        raise RuntimeError("Personal agent response is not a valid state")
                    names = result.get("successful_tools", [])
                    if not isinstance(names, list):
                        names = []
                    if not any(isinstance(item, str) and item.startswith("operly_")
                               for item in names):
                        raise RuntimeError("No verified Operly tool receipt in scheduled wake")
                    state = ("completed" if wake.sequence + 1 == wake.total_wakes
                             else "active")
                    if result["status"] != "completed":
                        raise RuntimeError("Personal agent did not complete wake")
                    await con.execute(
                        """INSERT INTO dz_personal_mcp_receipts
                           (goal_id, sequence, status, tool_names)
                           VALUES($1,$2,$3,$4::jsonb)""",
                        wake.goal_id, wake.sequence, result["status"],
                        json.dumps(names[:20]),
                    )
                    await con.execute(
                        """UPDATE dz_personal_mcp_goals SET next_sequence=$2,
                           state=$3, updated_at=now() WHERE goal_id=$1""",
                        wake.goal_id, wake.sequence + 1, state,
                    )
                    return {
                        "state": state, "next_sequence": wake.sequence + 1,
                        "tools": names[:20], "verification": "postgres_receipt",
                    }
                finally:
                    if own_http:
                        await http.aclose()
    finally:
        await pool.close()


def pause_reason_from_reply(reply) -> str | None:
    """Only signed, internal run responses can cause a budget pause.

    Never interpret arbitrary provider prose or an ambiguous 503 as a quota.
    The run route validates its own inference errors before returning this code.
    """
    if reply.status_code == 503:
        try:
            detail = reply.json().get("detail", {})
        except (ValueError, AttributeError, TypeError):
            return None
        if isinstance(detail, dict) and detail.get("code") == "INFERENCE_LIMIT_REACHED":
            return "inference_limit_reached"
    if reply.status_code == 200:
        try:
            result = reply.json()
        except (ValueError, AttributeError, TypeError):
            return None
        if (isinstance(result, dict) and result.get("status") == "incomplete"
                and result.get("termination_reason") == "inference_limit_reached"):
            return "inference_limit_reached"
    return None


async def operator_resume_paused_personal_goal(wake: PersonalWakeInput, *, http=None) -> dict:
    """Internal-only, operator-authorized resume of a read-only paused goal.

    Does NOT dispatch a Hatchet task. A trusted caller must separately enqueue
    the exact same sequence. Never expose this helper to model/MCP/user input:
    the operator flag is NOT itself proof of end-user consent.
    """
    if os.getenv("DRAGONZPYDER_PERSONAL_MCP_RESUME_OPERATOR_ALLOWED") != "1":
        raise RuntimeError("Operator-authorized Personal goal resumption is disabled")
    dsn, service_secret, _agent_secret, operly, _dragon = require_wake_gate()
    try:
        canonical = [str(UUID(item)) for item in (
            wake.goal_id, wake.user_id, wake.session_id, wake.conversation_id,
        )]
        if canonical != [wake.goal_id, wake.user_id, wake.session_id, wake.conversation_id]:
            raise ValueError("noncanonical")
    except ValueError:
        raise RuntimeError("Canonical goal and Personal authority IDs required") from None
    import asyncpg
    own_http = http is None
    if own_http:
        http = httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=12)
    try:
        # Revalidate live Personal authority *before* permitting another wake.
        try:
            renewed = await http.post(
                operly, headers={"X-Operly-Agent-Service": service_secret},
                json={
                    "user_id": wake.user_id,
                    "session_id": wake.session_id,
                    "conversation_id": wake.conversation_id,
                    "query": wake.prompt[:200],
                }, timeout=12,
            )
        except httpx.HTTPError:
            raise RuntimeError("Personal session renewal unavailable") from None
        if renewed.status_code != 200:
            raise RuntimeError("Personal session cannot authorize resume")
        try:
            renewed_body = renewed.json()
        except ValueError:
            raise RuntimeError("Personal session renewal invalid") from None
        if (not isinstance(renewed_body, dict)
                or not isinstance(renewed_body.get("approved_tool_names"), list)
                or not renewed_body["approved_tool_names"]):
            raise RuntimeError("No current Personal read-only capabilities")
        pool = await asyncpg.create_pool(
            dsn=dsn, min_size=1, max_size=2, timeout=10, command_timeout=15,
        )
        try:
            async with pool.acquire() as con:
                async with con.transaction():
                    row = await con.fetchrow(
                        """SELECT user_id,session_id,conversation_id,total_wakes,
                                  objective_hash,next_sequence,state
                           FROM dz_personal_mcp_goals WHERE goal_id=$1 FOR UPDATE""",
                        wake.goal_id,
                    )
                    if row is None or (
                        row["user_id"], row["session_id"], row["conversation_id"],
                        row["total_wakes"], row["objective_hash"], row["next_sequence"],
                    ) != (
                        wake.user_id, wake.session_id, wake.conversation_id,
                        wake.total_wakes, hashlib.sha256(wake.prompt.encode("utf-8")).hexdigest(),
                        wake.sequence,
                    ):
                        raise RuntimeError("Personal resume authority or sequence mismatch")
                    if row["state"] != "paused_budget":
                        raise RuntimeError("Personal goal is not paused for budget")
                    await con.execute(
                        """UPDATE dz_personal_mcp_goals SET state='active',updated_at=now()
                           WHERE goal_id=$1""", wake.goal_id,
                    )
                    return {"state": "active", "next_sequence": wake.sequence,
                            "scheduled": False, "requires_hatchet_dispatch": True}
        finally:
            await pool.close()
    finally:
        if own_http:
            await http.aclose()


class PersonalGoalPlanInput(BaseModel):
    """Tiny bounded Hatchet plan, not a free-form model-defined workflow."""
    model_config = ConfigDict(extra="forbid")
    goal_id: str
    user_id: str
    session_id: str
    conversation_id: str
    total_wakes: int = Field(ge=2, le=3)
    prompt: str = Field(min_length=1, max_length=12000)


async def execute_personal_goal_plan(plan: PersonalGoalPlanInput) -> dict:
    """Run sequential durable wake steps and stop at the first unsafe boundary.

    The same plan can be explicitly re-dispatched after a worker restart.
    Persisted goal sequence fencing skips already committed steps, while an
    uncertain in-flight wake is never automatically replayed by Hatchet.
    """
    require_wake_gate()
    for seq in range(plan.total_wakes):
        wake = PersonalWakeInput(**plan.model_dump(), sequence=seq)
        outcome = await perform_personal_wake(wake)
        state = outcome.get("state")
        next_seq = outcome.get("next_sequence")
        if state in ("paused_budget", "blocked"):
            return {"state": state, "next_sequence": next_seq,
                    "requires_authorized_resume": state == "paused_budget"}
        if state == "completed":
            return {"state": "completed", "next_sequence": next_seq,
                    "verification": "postgres_receipts_only"}
        if state != "active" or type(next_seq) is not int or next_seq <= seq:
            raise RuntimeError("Personal goal did not advance; refusing replay")
    raise RuntimeError("Personal goal sequence exhausted without durable completion")


def make_personal_goal_controller_task(hatchet):
    """Opt-in bounded Hatchet controller registration; never schedules a cron."""
    if os.getenv("DRAGONZPYDER_PERSONAL_GOAL_CONTROLLER_ENABLED") != "1":
        raise RuntimeError("Personal goal controller is not enabled")
    require_wake_gate()
    from datetime import timedelta

    @hatchet.task(
        name="dragonzpyder-personal-goal-controller",
        input_validator=PersonalGoalPlanInput,
        concurrency=1,
        retries=0,
        execution_timeout=timedelta(minutes=8),
    )
    async def run_plan(input: PersonalGoalPlanInput, ctx) -> dict:
        return await execute_personal_goal_plan(input)
    return run_plan


def make_personal_mcp_wake_task(hatchet):
    """Register a gated Hatchet task; never create a cron automatically."""
    from datetime import timedelta

    @hatchet.task(
        name="dragonzpyder-personal-mcp-wake",
        input_validator=PersonalWakeInput,
        concurrency=1, retries=0,
        execution_timeout=timedelta(minutes=3),
    )
    async def wake(input: PersonalWakeInput, ctx) -> dict:
        return await perform_personal_wake(input)

    return wake
