# Staging agent traces and loop debugging

## What is actually connected

- **Railway traces:** enabled for the staging Lab and Gateway with auto-instrumentation. The Railway traces viewer can show gateway health/inference traffic, latency, failures and service spans. It does not automatically reveal LangGraph's internal todo list or tool content.
- **Langfuse:** the LangChain CallbackHandler is installed but **not active** until the Test Lab service has valid credentials AND the explicit staging toggle below. No Langfuse trace was established by the 2026-11-08 original trials.
- **Privacy:** only the synthetic service IDs `frontier-stress` and `paid-tool-smoke` can export prompts/responses with the Langfuse handler. Password-gated freeform `/test` user prompts and personal chat do not connect.

## Enabling Langfuse in the Railway staging Test Lab

In Railway > DRAGONZPYDER AGENT STAGING > **DragonZpyder Agent Test Lab** > Variables, set:

- `LANGFUSE_PUBLIC_KEY` to the public key of the intended Langfuse project.
- `LANGFUSE_SECRET_KEY` to its secret key (do not commit or paste into chat).
- `LANGFUSE_BASE_URL` to the correct host for your region, for example `https://us.cloud.langfuse.com`.
- `DRAGONZPYDER_STAGING_LANGFUSE_ENABLED=1`.
- Optional `LANGFUSE_TRACING_ENVIRONMENT=staging`.

The runtime supports the older prefixed aliases `DRAGONZPYDER_LANGFUSE_PUBLIC_KEY`, `DRAGONZPYDER_LANGFUSE_SECRET_KEY`, and `DRAGONZPYDER_LANGFUSE_HOST` as alternatives. Redeploy the Test Lab; `/status` reports `configured_unverified` when values are present. **That status is not proof of ingestion**. To prove actual ingestion, trigger a consented synthetic test, obtain the trace ID from its persisted sanitized metrics, and check the Langfuse Trace Table for that ID. Langfuse ingestion can be delayed.

## Loop-failure evidence

- `progress_guard.py` detects four identical single-tool calls, three repeated 2-/3-tool-call cycles, or 18 supervisor AI turns in paid stress mode (10 in normal mode). These yield a terminal `DRAGONZPYDER_INCOMPLETE` message instead of infinite requests.
- `run_report(..., recover_partial_on_failure=True)` fetches checkpoint state on recognized model-call, tool-call and recursion-limit exceptions. It returns safe tool names, virtual artifact paths and correlated readback receipts; the result is `incomplete` and `objective_verified=false`.
- The benchmark runner reports a score of `execution_incomplete` for bounded partial outcomes and never grants task success from tool counts, unfinished files or model self-reports.
- The separate durable parent parallel fan-out remains blocked until **gateway-enforced atomic budget reservations** are integrated.
- OpenRouter key's non-resetting hard cap of **$0.50** must remain enforced. The post-debug test is a single F08 only, under the remaining key allowance.
