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
