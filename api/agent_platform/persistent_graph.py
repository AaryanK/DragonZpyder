"""Bounded signed-user execution graphs on Hatchet + PostgreSQL.

This is the first *typed, resumable* multi-tool execution path. It is intentionally
unattended READ ONLY: authorized MCP reads -> deterministic report -> verification.
Neither an LLM nor a sandbox is trusted with credentials at wake time.
Production mutations, arbitrary code, and parallel DAG workers are NOT enabled.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
import re
from typing import Any, Literal
from uuid import UUID, uuid4

import asyncpg
import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field

from .personal_wake import require_wake_gate

log = logging.getLogger(__name__)
ALLOWED_READS = frozenset({"workflow.list", "tasks.list", "system.runtime.status"})
_STEP_ID = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_STEP_LIMIT = 6
_MAX_SNAPSHOT = 24000

SCHEMA = """
CREATE TABLE IF NOT EXISTS dz_execution_graphs (
  goal_id text PRIMARY KEY,
  user_id text NOT NULL,
  session_id text NOT NULL,
  conversation_id text NOT NULL,
  plan_sha256 text NOT NULL,
  plan jsonb NOT NULL,
  state text NOT NULL,
  next_sequence integer NOT NULL DEFAULT 0,
  blocked_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dz_execution_graphs_owner
  ON dz_execution_graphs(user_id,conversation_id,created_at DESC);
CREATE TABLE IF NOT EXISTS dz_execution_graph_steps (
  goal_id text NOT NULL REFERENCES dz_execution_graphs(goal_id),
  sequence integer NOT NULL,
  step_id text NOT NULL,
  kind text NOT NULL,
  tool_name text,
  output_data jsonb NOT NULL,
  output_sha256 char(64) NOT NULL,
  executed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(goal_id,sequence),
  UNIQUE(goal_id,step_id)
);
"""


class GraphStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=40)
    kind: Literal["mcp_read", "compose", "verify"]
    depends_on: list[str] = Field(default_factory=list, max_length=5)
    capability_id: str | None = Field(default=None, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)


class GraphWake(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal_id: str
    sequence: int = Field(ge=0, le=_STEP_LIMIT - 1)


def _uuid(value: str) -> str:
    try:
        canonical = str(UUID(value))
    except (TypeError, AttributeError, ValueError):
        raise ValueError("Canonical signed identity required") from None
    if canonical != value:
        raise ValueError("Canonical signed identity required")
    return canonical


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str,
                      separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def validate_plan(steps: list[GraphStep]) -> list[dict]:
    """Strict forward-only DAG. Every source must feed the final report.

    Explicit model-selected capability IDs are *requests*, not authorizations.
    Operly renews the actual Personal capability on EACH scheduled wake.
    """
    if not 4 <= len(steps) <= _STEP_LIMIT:
        raise ValueError("Plan requires 4-6 bounded steps")
    ids: set[str] = set()
    kinds: dict[str, str] = {}
    reads: list[str] = []
    for i, step in enumerate(steps):
        if not _STEP_ID.fullmatch(step.id) or step.id in ids:
            raise ValueError("Invalid or duplicate step identifier")
        if len(set(step.depends_on)) != len(step.depends_on):
            raise ValueError("Duplicate dependency")
        if any(dep not in ids for dep in step.depends_on):
            raise ValueError("All dependencies must be earlier steps")
        if step.kind == "mcp_read":
            if step.capability_id not in ALLOWED_READS:
                raise ValueError("Only audited, unattended MCP reads are allowed")
            if step.arguments:
                raise ValueError("The initial graph supports zero-argument reads only")
            if step.depends_on:
                raise ValueError("Read steps cannot depend on other steps in this slice")
            reads.append(step.id)
        else:
            if step.capability_id is not None or step.arguments:
                raise ValueError("Internal steps cannot request tools or arguments")
            if step.kind == "compose":
                if set(step.depends_on) != set(reads) or len(reads) < 2:
                    raise ValueError("Compose must depend on every read step (at least two)")
                if i != len(steps) - 2:
                    raise ValueError("Compose must be penultimate")
            elif step.kind == "verify":
                if i != len(steps) - 1 or step.depends_on != [steps[-2].id] or kinds.get(steps[-2].id) != "compose":
                    raise ValueError("Verify must be final and depend on compose")
        ids.add(step.id)
        kinds[step.id] = step.kind
    if steps[-2].kind != "compose" or steps[-1].kind != "verify":
        raise ValueError("Plan must finish with compose then verify")
    if len(reads) != len(steps) - 2:
        raise ValueError("All nonterminal steps must be MCP reads")
    if len({s.capability_id for s in steps if s.kind == "mcp_read"}) < 2:
        raise ValueError("Plan must exercise at least two distinct capabilities")
    plan = [step.model_dump(mode="json") for step in steps]
    if len(_json(plan)) > 12000:
        raise ValueError("Plan is too large")
    return plan


def require_graph_gate(*, worker: bool = False) -> str:
    if os.getenv("DRAGONZPYDER_EXECUTION_GRAPH_ENABLED") != "1":
        raise RuntimeError("Execution graph is disabled")
    if os.getenv("DRAGONZPYDER_EXECUTION_GRAPH_SCHEMA_INSTALL_ALLOWED") != "1":
        raise RuntimeError("Graph schema was not operator-approved")
    if worker:
        dsn, *_ = require_wake_gate()
    else:
        if (os.getenv("DRAGONZPYDER_PERSONAL_GOAL_TOOLS_ENABLED") != "1"
                or os.getenv("DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED") != "1"):
            raise RuntimeError("Signed Personal goal scheduling is unavailable")
        dsn = os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", "")
        if not dsn.startswith(("postgresql://", "postgres://")):
            raise RuntimeError("Personal graph database unavailable")
    return dsn


async def _pool(*, worker: bool = False):
    return await asyncpg.create_pool(
        dsn=require_graph_gate(worker=worker), min_size=1, max_size=2,
        timeout=10, command_timeout=40,
    )


async def _renew(row: dict, requested: str) -> tuple[str, list[str], str]:
    """Validate the ORIGINAL Operly Personal session; never cache bearer tokens."""
    _, service_secret, _, operly, _ = require_wake_gate()
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False,
                                 timeout=15) as client:
        response = await client.post(
            operly, headers={"X-Operly-Agent-Service": service_secret},
            json={"user_id": row["user_id"], "session_id": row["session_id"],
                  "conversation_id": row["conversation_id"], "query": requested},
        )
    if response.status_code in (401, 403):
        raise PermissionError("personal_authority_revoked")
    if response.status_code != 200:
        raise RuntimeError("personal_authority_unavailable")
    data = response.json()
    token = data.get("access_token")
    permitted = data.get("approved_tool_names")
    if not isinstance(token, str) or not isinstance(permitted, list):
        raise RuntimeError("invalid_personal_delegation")
    return token, [x for x in permitted if isinstance(x, str)], service_secret


def _snapshot(value: Any) -> Any:
    result = json.loads(_json(value))
    if len(_json(result).encode("utf-8")) > _MAX_SNAPSHOT:
        raise ValueError("tool_result_exceeds_snapshot_budget")
    return result


def _compose(goal_id: str, step: GraphStep, outputs: dict[str, dict]) -> dict:
    parts = ["# DragonZpyder evidence report", "", "Goal: " + goal_id, "",
             "This report contains tool observations, not inferred facts.", ""]
    references = {}
    for dep in step.depends_on:
        entry = outputs[dep]
        references[dep] = entry["hash"]
        parts.extend([
            "## " + dep, "",
            "Tool: " + str(entry["tool"]), "",
            "Result SHA-256: " + entry["hash"], "",
            "~~~json", json.dumps(entry["data"], ensure_ascii=False, sort_keys=True,
                                  indent=2), "~~~", "",
        ])
    markdown = "\n".join(parts)
    if len(markdown.encode("utf-8")) > 70000:
        raise ValueError("report_exceeds_budget")
    return {"format": "markdown", "markdown": markdown,
            "source_hashes": references, "source_count": len(references)}


def _verify(step: GraphStep, outputs: dict[str, dict]) -> dict:
    report = outputs[step.depends_on[0]]["data"]
    sources = report.get("source_hashes")
    if not isinstance(sources, dict) or len(sources) < 2:
        raise ValueError("Report lacks source references")
    for name, digest in sources.items():
        source = outputs.get(name)
        if not source or source["hash"] != digest:
            raise ValueError("Report source hash mismatch")
        if _sha(source["data"]) != source["hash"]:
            raise ValueError("Stored source data fails integrity")
        if source["tool"] not in ("operly_workflow_list", "operly_tasks_list",
                                   "operly_system_runtime_status"):
            raise ValueError("Source lacks approved tool receipt")
        if digest not in report.get("markdown", ""):
            raise ValueError("Report omits source digest")
    return {"verified": True, "source_count": len(sources),
            "report_sha256": outputs[step.depends_on[0]]["hash"],
            "verification_scope": "stored read receipts and report integrity only"}


async def execute_graph_wake(wake: GraphWake) -> dict:
    """Claim -> fresh authorization -> execute -> write receipt.

    An interrupted inflight step is deliberately NOT replayed automatically.
    Mutations are not available in this executor; recovery still requires a
    separately reviewed action instead of hiding transport uncertainty.
    """
    _uuid(wake.goal_id)
    pool = await _pool(worker=True)
    try:
        async with pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(
                    """SELECT * FROM dz_execution_graphs WHERE goal_id=$1
                       FOR UPDATE""", wake.goal_id,
                )
                if row is None:
                    return {"state": "not_found", "executed": False}
                plan = row["plan"]
                if isinstance(plan, str):
                    plan = json.loads(plan)
                if _sha(plan) != row["plan_sha256"]:
                    raise RuntimeError("Stored plan integrity mismatch")
                if row["state"] != "active":
                    return {"state": row["state"], "executed": False}
                if row["next_sequence"] > wake.sequence:
                    return {"state": "already_processed", "executed": False}
                if row["next_sequence"] < wake.sequence:
                    return {"state": "out_of_order", "executed": False}
                step = GraphStep.model_validate(plan[wake.sequence])
                await con.execute(
                    """UPDATE dz_execution_graphs SET state='inflight',
                       updated_at=now() WHERE goal_id=$1""", wake.goal_id,
                )

        # A single step may rely on earlier snapshots, but never user-controlled
        # session IDs, network targets, mutable tool names, or unscoped files.
        async with pool.acquire() as con:
            prior = await con.fetch(
                """SELECT step_id,tool_name,output_data,output_sha256
                   FROM dz_execution_graph_steps
                   WHERE goal_id=$1 ORDER BY sequence""", wake.goal_id,
            )
        outputs: dict[str, dict] = {}
        for item in prior:
            value = item["output_data"]
            if isinstance(value, str):
                value = json.loads(value)
            if _sha(value) != item["output_sha256"]:
                raise RuntimeError("Stored output integrity mismatch")
            outputs[item["step_id"]] = {
                "tool": item["tool_name"], "hash": item["output_sha256"],
                "data": value,
            }
        if any(dep not in outputs for dep in step.depends_on):
            raise RuntimeError("unsatisfied_dependency")
        try:
            # Even native compose/verify stages revalidate the original user's
            # active Personal session rather than continuing after revocation.
            read_query = step.capability_id or next(
                s["capability_id"] for s in plan if s["kind"] == "mcp_read"
            )
            token, approved, proof = await _renew(dict(row), read_query)
            if step.kind == "mcp_read":
                if step.capability_id not in approved:
                    raise PermissionError("requested_read_not_authorized")
                from .operly_mcp_client import load_authorized_operly_mcp_tools
                from .mcp_broker import invoke_granted_mcp_tool
                tools = await asyncio.wait_for(
                    load_authorized_operly_mcp_tools(
                        url=os.getenv("DRAGONZPYDER_OPERLY_MCP_URL",
                                      "https://operly.dragonzpyder.xyz/mcp"),
                        access_token=token, service_proof=proof,
                        approved_tool_names=frozenset({step.capability_id}),
                        max_tools=3,
                    ), timeout=20,
                )
                invoked = await invoke_granted_mcp_tool(
                    tools=tools, provider_id="operly",
                    capability_id=step.capability_id,
                    approved_ids=frozenset({step.capability_id}),
                    unattended_read_ids=ALLOWED_READS, arguments={}, timeout_seconds=20,
                )
                value = {"result": _snapshot(invoked.result),
                         "arguments_sha256": invoked.receipt.arguments_sha256,
                         "result_sha256": invoked.receipt.result_sha256}
                actual_tool = invoked.receipt.alias
            elif step.kind == "compose":
                value = _compose(wake.goal_id, step, outputs)
                actual_tool = "native_graph_compose"
            else:
                value = _verify(step, outputs)
                actual_tool = "native_graph_verify"
            value = _snapshot(value) if step.kind != "compose" else value
            digest = _sha(value)
        except Exception as error:
            # Errors are rendered only as safe categories; no user data or
            # credentials from provider exception text enters durable state.
            reason = ("authorization_revoked" if isinstance(error, PermissionError)
                      else "step_execution_failed")
            log.warning("Execution graph step blocked kind=%s seq=%s type=%s",
                        step.kind, wake.sequence, type(error).__name__)
            async with pool.acquire() as con:
                await con.execute(
                    """UPDATE dz_execution_graphs SET state='blocked',
                       blocked_reason=$2,updated_at=now()
                       WHERE goal_id=$1 AND state='inflight'""",
                    wake.goal_id, reason,
                )
            return {"state": "blocked", "reason": reason, "executed": False}
        async with pool.acquire() as con:
            async with con.transaction():
                current = await con.fetchrow(
                    """SELECT state,next_sequence FROM dz_execution_graphs
                       WHERE goal_id=$1 FOR UPDATE""", wake.goal_id,
                )
                if current is None or current["state"] != "inflight" or current["next_sequence"] != wake.sequence:
                    return {"state": "not_committed", "executed": True}
                await con.execute(
                    """INSERT INTO dz_execution_graph_steps
                       (goal_id,sequence,step_id,kind,tool_name,output_data,output_sha256)
                       VALUES($1,$2,$3,$4,$5,$6::jsonb,$7)""",
                    wake.goal_id, wake.sequence, step.id, step.kind,
                    actual_tool, _json(value), digest,
                )
                state = "completed" if wake.sequence + 1 == len(plan) else "active"
                await con.execute(
                    """UPDATE dz_execution_graphs
                       SET state=$2,next_sequence=$3,updated_at=now()
                       WHERE goal_id=$1""",
                    wake.goal_id,state,wake.sequence + 1,
                )
                return {"state":state,"executed":True,"sequence":wake.sequence,
                        "step":step.id,"tool":actual_tool,
                        "receipt_sha256":digest,"verification":"postgres_receipt"}
    finally:
        await pool.close()


def make_graph_hatchet_task(hatchet, *, validate_worker: bool = True):
    if validate_worker:
        require_graph_gate(worker=True)
    @hatchet.task(
        name="dragonzpyder-personal-execution-graph",
        input_validator=GraphWake, concurrency=1, retries=0,
        execution_timeout=timedelta(minutes=2),
    )
    async def run_graph(input: GraphWake, ctx) -> dict:
        return await execute_graph_wake(input)
    return run_graph


def graph_tools(*, user_id: str, session_id: str, conversation_id: str):
    """User/session ownership comes ONLY from the signed internal route."""
    user_id,session_id,conversation_id = [
        _uuid(x) for x in (user_id,session_id,conversation_id)
    ]

    @tool("graph_schedule")
    async def graph_schedule(objective: str, steps: list[GraphStep],
                             interval_minutes: int = 2) -> dict:
        """Schedule an evidence-grounded multi-step persistent execution graph.

        Provide 4-6 steps: at least TWO different authorized MCP read tools
        (workflow.list, tasks.list, system.runtime.status), then ONE compose
        step dependent on ALL reads, then ONE final verify step dependent on
        compose. Each step has id, kind, depends_on, and for mcp_read a
        capability_id. Other steps have no capability_id. This is read-only,
        unattended, checkpointed and finite. Never claim the final objective
        is completed before graph_status says verified=true.
        """
        require_graph_gate()
        if not isinstance(objective,str) or not 1 <= len(objective.strip()) <= 500:
            return {"status":"rejected","reason":"invalid_objective"}
        if type(interval_minutes) is not int or not 1 <= interval_minutes <= 5:
            return {"status":"rejected","reason":"invalid_interval"}
        try:
            plan=validate_plan(steps)
        except ValueError:
            return {"status":"rejected","reason":"invalid_plan"}
        if not os.getenv("HATCHET_CLIENT_TOKEN"):
            raise RuntimeError("Private Hatchet dispatch unavailable")
        goal_id=str(uuid4())
        pool=await _pool()
        try:
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
                async with con.transaction():
                    await con.execute("SELECT pg_advisory_xact_lock(hashtext($1))", user_id)
                    prior=await con.fetchrow(
                        """SELECT goal_id,state FROM dz_execution_graphs
                           WHERE user_id=$1 AND state IN ('preparing','active','inflight')
                           ORDER BY created_at DESC LIMIT 1""",user_id,
                    )
                    if prior is not None:
                        return {"status":"existing_graph","goal_id":prior["goal_id"],
                                "state":prior["state"]}
                    await con.execute(
                        """INSERT INTO dz_execution_graphs
                           (goal_id,user_id,session_id,conversation_id,
                            plan_sha256,plan,state)
                           VALUES($1,$2,$3,$4,$5,$6::jsonb,'preparing')""",
                        goal_id,user_id,session_id,conversation_id,_sha(plan),_json(plan),
                    )
            from hatchet_sdk import Hatchet
            hatchet=Hatchet()
            task=make_graph_hatchet_task(hatchet, validate_worker=False)
            base=datetime.now(timezone.utc)+timedelta(minutes=1)
            count=0
            try:
                for seq in range(len(plan)):
                    await task.aio_schedule(
                        run_at=base+timedelta(minutes=seq*interval_minutes),
                        input=GraphWake(goal_id=goal_id,sequence=seq),
                    )
                    count+=1
                async with pool.acquire() as con:
                    await con.execute(
                        """UPDATE dz_execution_graphs
                           SET state='active',updated_at=now()
                           WHERE goal_id=$1 AND state='preparing'""",goal_id,
                    )
            except Exception:
                async with pool.acquire() as con:
                    await con.execute(
                        """UPDATE dz_execution_graphs
                           SET state='blocked',blocked_reason='dispatch_failed',
                           updated_at=now() WHERE goal_id=$1""",goal_id,
                    )
                return {"status":"dispatch_failed","goal_id":goal_id,
                        "accepted_wakes":count,"verified":False}
            return {"status":"scheduled","goal_id":goal_id,
                    "scheduled_wakes":len(plan),"first_wake_utc":base.isoformat(),
                    "last_wake_utc":(base+timedelta(minutes=(len(plan)-1)*interval_minutes)).isoformat(),
                    "verified":False}
        finally:
            await pool.close()

    @tool("graph_status")
    async def graph_status(goal_id: str) -> dict:
        """Inspect YOUR graph, receipts, verification and final evidence report.

        A Hatchet success or created plan is not verified task completion.
        """
        try:
            _uuid(goal_id)
        except ValueError:
            return {"status":"invalid_goal_id"}
        pool=await _pool()
        try:
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
                graph=await con.fetchrow(
                    """SELECT state,next_sequence,blocked_reason,plan,plan_sha256
                       FROM dz_execution_graphs
                       WHERE goal_id=$1 AND user_id=$2 AND conversation_id=$3""",
                    goal_id,user_id,conversation_id,
                )
                if graph is None:
                    return {"status":"not_found"}
                plan=graph["plan"]
                if isinstance(plan,str):
                    plan=json.loads(plan)
                if _sha(plan)!=graph["plan_sha256"]:
                    return {"status":"corrupt_plan","verified":False}
                receipts=await con.fetch(
                    """SELECT sequence,step_id,kind,tool_name,output_data,
                              output_sha256,executed_at
                       FROM dz_execution_graph_steps WHERE goal_id=$1
                       ORDER BY sequence""",goal_id,
                )
                result=[]
                ok=True
                report=None
                verifier=False
                for r in receipts:
                    data=r["output_data"]
                    if isinstance(data,str):
                        data=json.loads(data)
                    integrity=_sha(data)==r["output_sha256"]
                    ok=ok and integrity and r["sequence"]==len(result)
                    if r["kind"]=="compose":
                        report=data.get("markdown")
                    if r["kind"]=="verify":
                        verifier=data.get("verified") is True
                    result.append({"sequence":r["sequence"],"step_id":r["step_id"],
                                   "kind":r["kind"],"tool":r["tool_name"],
                                   "output_sha256":r["output_sha256"],
                                   "integrity_valid":integrity,
                                   "executed_at_utc":r["executed_at"].isoformat()})
                verified=(graph["state"]=="completed"
                          and graph["next_sequence"]==len(plan)
                          and len(receipts)==len(plan) and ok and verifier)
                return {"goal_id":goal_id,"state":graph["state"],
                        "blocked_reason":graph["blocked_reason"],
                        "completed_steps":graph["next_sequence"],
                        "total_steps":len(plan),"verified":verified,
                        "receipts":result,
                        "report_markdown":report[:12000] if isinstance(report,str) else None}
        finally:
            await pool.close()

    @tool("graph_cancel")
    async def graph_cancel(goal_id: str) -> dict:
        """Cancel your own graph. Future queued Hatchet wake-ups become no-ops."""
        try:
            _uuid(goal_id)
        except ValueError:
            return {"status":"invalid_goal_id"}
        pool=await _pool()
        try:
            async with pool.acquire() as con:
                await con.execute(SCHEMA)
                outcome=await con.execute(
                    """UPDATE dz_execution_graphs
                       SET state='cancelled',updated_at=now()
                       WHERE goal_id=$1 AND user_id=$2 AND conversation_id=$3
                         AND state IN ('preparing','active')""",
                    goal_id,user_id,conversation_id,
                )
            return {"goal_id":goal_id,
                    "status":"cancelled" if outcome=="UPDATE 1" else "not_cancellable"}
        finally:
            await pool.close()

    return [graph_schedule,graph_status,graph_cancel]
