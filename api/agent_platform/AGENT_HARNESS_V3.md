# DragonZpyder Agent Harness V3 — selective LangChain capabilities

**Staging only.** Do not merge this draft branch, remove production workloads,
grant external file/computer access, or turn on paid parallel evaluation without
separate account budget and authorization checks.

## Design decision: use the stack instead of copying every library

LangChain is a framework ecosystem, not a finite set of capabilities that can
safely be switched on together. DragonZpyder uses:

- **Deep Agents** as the agent harness and adaptive supervisor.
- **LangChain** for model abstraction, middleware, tools, bounded call budgets.
- **LangGraph** for checkpointed agents and explicit multi-track `Send` fan-out.
- **OpenRouter** only behind our private authenticated usage-ledger gateway.
- **Hatchet** for persistent scheduled work (not agent-owned arbitrary cron).

Official guidance: https://www.langchain.com/oss-overview and
https://github.com/langchain-ai/docs/blob/main/src/oss/deepagents/subagents.mdx

## Added in this iteration

| Capability | Implementation | Actual guarantee |
| --- | --- | --- |
| Supervisor and specialists | `harness.py` | Analyst, independent verifier and virtual artifact builder; optional web researcher when operator enables constrained search |
| Long-horizon budget mode | `harness.py` | 12 supervisor / 5 per-specialist model calls only with four explicit paid+gateway flags; baseline remains 8 / 3 and 3 parent task calls |
| Bounded parallel investigation | `orchestration.py` | LangGraph `Send` fan-out and reducer-based result aggregation of 2–3 isolated tracks; returns partial failure explicitly |
| Real-model parallel integration | `runtime.AgentRuntime.run_parallel_report` | Requires explicit sixth parallel-eval flag, dedicated authenticated gateway, and independent PostgreSQL saver per child; not enabled for personal accounts |
| Delegation telemetry | `delegation_trace.py` | LangChain callback records only tool-run hashes, timestamps and success; overlap cannot be inferred from claims |
| In-memory code interpreter | `harness.py`, optional `langchain-quickjs` | Optional 16 MiB / 2 s JavaScript compute-only `eval`, maximum four eval calls/run; no JS network, host shell, files, remote tools or subagent bridges; REPL state cleared after each call |
| Offline integration tests | `test_orchestration.py` / `test_harness_v2.py` | Concurrency, failure containment, opt-in tool visibility, no paid-mode access by default |

**Important:** The new orchestration graph is a bounded *one-shot investigation*
and does not yet have its **own** durable parent-level retry/recovery
checkpoint or exactly-once semantics. Child agent graphs use PostgreSQL
checkpoints. It is not yet safe to use the multi-track runner for external
writes, and there is no user-facing parallel-run endpoint. The raw duration
and file-path diagnostics do not prove task quality or objective success.

### Enabling operator-only canaries

```bash
# Never set these on public traffic without a hard global ledger cap.
DRAGONZPYDER_AGENT_HARNESS_V2=1
DRAGONZPYDER_AGENT_USE_GATEWAY=1
DRAGONZPYDER_AGENT_PRODUCTION_MODE=1
DRAGONZPYDER_AGENT_EVAL_ALLOW_PAID=1
DRAGONZPYDER_AGENT_STRESS_EVAL_ENABLED=1
DRAGONZPYDER_AGENT_PARALLEL_EVAL_ENABLED=1
# Optional bounded sandboxed JS calculations:
DRAGONZPYDER_AGENT_QUICKJS_ENABLED=1
```

`run_parallel_report` is an internal method only. Every child still uses
per-run call limits, isolated virtual files, and metered model gateway
requests, but the program **does not yet implement a total USD budget
reservation across all children**. Use an operator-established hard provider
limit and approve a one-case experimental budget before triggering it.

## Already present from Deep Agents — do not duplicate

- Checkpointed LangGraph state in PostgreSQL per trusted service/thread;
- todo planning via `TodoListMiddleware`;
- virtual read/write/edit/glob/grep tools via `FilesystemMiddleware`;
- Deep Agents context summarization / tool-result offloading;
- independent named specialists, callable in parallel if the model issues
  concurrent `task` calls; separate experimental graph for deterministic fan-out;
- model-call and task-call limits;
- Langfuse callback hook (requires staging credentials);
- dedicated web snippet provider (not general arbitrary-page fetch);
- independent verifier instructions, though not an outcome oracle.

## Deferred until explicitly secured and validated

1. **Actual sandbox computer and Python execution:** must be an isolated per-
   task host with no credentials, network policy, quotas, cleanup and audited
   permission lease. Never enable `ShellToolMiddleware` with host execution.
2. **Full-page web and MCP:** DNS rebinding/SSRF protection, origin allowlist,
   OAuth scopes, revocation, output trust boundaries, and side-effect approval.
3. **Human-in-the-loop actions:** only after app identity, scoped grants,
   approval UI, interrupt resume, and idempotency keys exist.
4. **Long-term memory:** Mem0 vector add/search/delete smoke passes, but
   auxiliary raw-history deletion is not certified. No personal memory rollout.
5. **Async/remote specialist jobs:** need hard global model budget, durable
   task identity, cancellation, compensation/recovery and true latency traces.
6. **Streaming UI:** typed event stream for plan, subagent runs, artifacts and
   errors with data redaction, not unsanitized LangGraph checkpoint dumps.
7. **Provider resilience:** gateway canaries previously failed because of
   malformed model tool-call responses and upstream 404/502. Classify model
   availability and tool support before spending on long benchmark runs;
   never execute malformed or creatively repaired function arguments.

## Required promotion tests

- Offline CI all green. No mock success claim.
- QuickJS `eval` actually executes deterministic arithmetic within budget.
- Repeat fan-out, forced one-child failure, cancellation and worker-restart.
- Separate provider/tool-binding canary returns valid tool-call JSON.
- Human-graded outputs and independently read-back artifacts.
- Observe real overlapped *successful* task spans and trace durations.
- Authenticate independent sandbox/environment oracles.
- Per-user and per-task ledger totals including all delegated children.
- Ten-case multi-run comparison with same fixtures and frontier baselines.

**Status:** Feature availability != production acceptance. Keep this branch
unmerged pending a staged integration review.


## November 7 reliability pass: before new real-model stress runs

**GitHub CI evidence:** After gateway history validation, catalog preflight,
parallel deadlines, and overlap-grading fixes, PR API run
`42394104067` completed all four jobs successfully: 35 gateway/API
contracts and 87 agent-stack contracts passed in their respective jobs.
These are offline integration tests, **not frontier-agent outcome scores**.

- Agent protocol rejects orphan, replayed, duplicated or unresolved tool-call
  IDs. It rejects unrequested provider tool names and truncated outputs.
- OpenRouter tool requests now carry `provider.require_parameters=true`.
  A temperature parameter is passed only when the caller explicitly provided
  it, so providers are not excluded by an invented default. Incompatibility
  fails closed rather than silently pretending a tool was called.
- `model_capabilities.py` performs an **operator-opt-in** catalog preflight
  from a fixed HTTPS OpenRouter model endpoint: exact slug, advertised
  `tools` support and minimum context. Enable it with
  `DRAGONZPYDER_AGENT_REQUIRE_MODEL_PREFLIGHT=1` after confirming the current
  catalog, gateway budget and test environment. It does not replace a real
  end-to-end model tool smoke or prove that provider routing will succeed.
- Parallel track calls now have an independent default 180-second deadline
  (hard maximum 240 seconds) and report failures without claiming completion.
- The grader excludes failed and cancelled task spans when scoring concurrency;
  merely overlapping failed calls cannot earn a parallelism pass.
- The child-thread hash separator was normalized for consistent isolation.

### Redundancy and deletion audit

**Safe simplification already made:** no duplicate provider-parameter
defaults for the agent gateway; each explicitly supplied setting has one
validation path. Reuse Deep Agents and LangGraph primitives instead of
adding a second queue, planner, or memory engine.

**Keep, not redundant:**

- `TodoListMiddleware` is **opt-in in Deep Agents v0.7+**; removing it
  would disable `write_todos`. Source:
  https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/CHANGELOG.md
- `FilesystemMiddleware` specifies our explicit limited virtual tools;
  the Deep Agents replacement inherits our /workspace permissions.
- Legacy read-only agent path remains an operational rollback switch.
- A separate LangGraph fan-out path allows explicit independently measured
  parallel track execution; it is not a substitute for inline Deep Agents
  subagent tasks.

**Do not delete automatically:** legacy Node backend while consumers
may still be using it; staging lab acceptance endpoints, older test reports,
or temporary fallback modes before dependency/traffic audit and rollback
verification. Database histories, Mem0 auxiliary retention, Hatchet state,
production secrets, production services, and user data are not cleanup targets.

### Next priority

1. Run an actual model-tool JSON smoke on an operator-approved
   tool-capable model and confirm catalog + gateway parameter compatibility.
2. Add a global, atomic multi-child cost reservation budget before enabling
   parallel paid evaluation; existing model-call ceilings alone are not enough.
3. Add durable parent retry/cancel recovery, isolated executable sandbox and
   separately authenticated outcome judges.
4. Verify real, three-run ten-case outcomes and matched frontier models.
5. Only then audit dead production dependencies and safely remove them,
   one reversible change per CI-backed migration.
