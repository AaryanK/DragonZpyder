# DragonZpyder Agent Harness V2 — staging integration

Built on Deep Agents + LangGraph, **not a competing framework**.
Source: `api/agent_platform/harness.py`, called through
`api/agent_platform/runtime.py`.

## Enabled by `DRAGONZPYDER_AGENT_HARNESS_V2=1` (staging worker only)

- Deep Agents supervisor with explicit success criteria and no fabricated actions.
- Opt-in `TodoListMiddleware` for planning complex objectives.
- `StateBackend` virtual filesystem: `ls`, `read_file`, `write_file`,
  `edit_file`, `glob`, `grep`. Files live in LangGraph checkpoint
  state per service/thread; **they are not host files or user computer files**.
- Two isolated specialist subagents: `analyst` and `verifier`, with
  tightly scoped roles and no external app/computer tools.
- Delegation is optional (simple tasks should not spawn agents).
- Per-run model-call limits: supervisor 8; each specialist 3.
  Parent `task` delegation calls limited to 3. These are **not** a total
  financial budget: the metered gateway and provider spend caps remain essential.
- A default specialist inherits the main model, but a trusted operator can set:
  - `DRAGONZPYDER_AGENT_ANALYST_MODEL_ID`
  - `DRAGONZPYDER_AGENT_VERIFIER_MODEL_ID`
  Every override is checked against
  `DRAGONZPYDER_RUNTIME_ALLOWED_MODELS` and routed through the same private,
  authenticated DragonZpyder gateway—never direct provider keys in worker mode.
- OpenTelemetry/Langfuse callback wiring remains available when staging
  credentials are configured.
- Hatchet manages worker jobs and scheduled tasks, not LangGraph itself.
- `DRAGONZPYDER_AGENT_HARNESS_V2=0` immediately switches back to the
  old read-only proof-of-concept agent.

## What is and is not proven

- CI compiles both real LangChain agent graphs without paid inference.
- CI runs a deterministic fake-model tool loop through LangGraph
  `write_file` and verifies the virtual artifact operation.
- CI checks specialist tool/model boundaries and a 12-case synthetic
  rubric spanning communication, schedules, arithmetic, documents,
  spreadsheets, software review, research honesty, virtual artifacts,
  quality, authority, orchestration and cost awareness.
- These prove SDK composition and basic tool wiring, **not** that a frontier
  model can execute every task. Before declaring agent quality, run held-out
  human-graded multi-step benchmarks with real sandbox outcome checking,
  time/cost accounting and verified external results.

## Next agent-only release gates

1. Real staged model eval (initially small and bounded; explicit operator action).
2. Full multi-step tool-result verification and recovery benchmarks.
3. Streaming event contract for supervisor, plan, delegated agents and artifacts,
   without requiring UI work to wait.
4. Secure sandbox-backed `execute` via a dedicated personal capability.
   The production Operly computer remains workspace-scoped and **must not**
   be handed to an unauthenticated personal agent.
5. Measure specialist strategy and multi-model value against a single-model
   no-delegation baseline (quality, total cost and elapsed time).
6. Connect image/video/audio/MCP integrations **after** the agent engine
   earns passing scores and permission boundaries exist.

Production unchanged; no public user sessions or external side effects.
