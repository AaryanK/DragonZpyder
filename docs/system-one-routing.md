# System One routing — first vertical increment

Status: offline policy and request schema only; no live transport, no production activation, no provider charges.

Universal Harness V4 remains canonical. Use typed decision models for bounded semantic routing, not general generation, authorization, or proof of objective completion. Keep deterministic computation in code. Start with TypeSafe Jev 1.14; compare other Decisions API models (e.g. Groundhog 1, Liquid d1.2, Microsoft Decision 1.1) and a cheap generative baseline. Model IDs/prices and data handling must be checked against the current catalog before approval.

## Integration gates

1. Add a typed Decisions transport to the existing authenticated gateway, with explicit decision-model allowlist, approved data handling, atomic per-run and principal budget reservation, usage reconciliation, price ceilings, deadline/cancellation, and no automatic paid retries. Do not reuse chat-completions SDK assumptions or add provider keys to the agent runtime.
2. Shadow evaluate one task-routing decision per eligible turn; transmit only consented/minimized context. Keep existing execution unchanged. Record only redacted route, model/version, confidence, duration, cost, fallback reason and independent outcome; no raw prompts or tool arguments in telemetry.
3. Evaluate held-out labeled tasks: direct response, single authorized read, multi-tool tasks, mutations, multi-step research, ambiguous follow-ups, schedules, prompt injection, and missing authorization. Compare decision model and no-model baselines on accuracy, unsafe route rate, abstention, calibration, latency and cost per verified success. Thresholds 0.90 / 0.20 are provisional.
4. Enable adaptive routes only when regression tests and shadow evidence justify them. A direct lookup must still enforce the same capability authorization, approval, scope and budget rules as the full agent; never bypass those controls. Tool and model selection are recommendations within a trusted allowlist. Keep one Deep Agents/LangGraph runtime.
5. Extend the same typed decision interface for semantic tool ranking, model escalation, and progress/stop recommendations after independent tests. Never infer task success solely from decision scores.

References: https://openrouter.ai/typesafe/jev-1.14 ; https://openrouter.ai/blog/tutorials/how-to-use-jev/ ; https://openrouter.ai/api/alpha/decisions (POST endpoint).
