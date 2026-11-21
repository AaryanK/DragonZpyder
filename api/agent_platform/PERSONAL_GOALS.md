# Native Personal recurring goals — deployment/acceptance gate

This implementation belongs to DragonZpyder. Operly remains the signed
identity and MCP permission authority; users do not name Hatchet.

## What is implemented

- Chat-scoped `goal_schedule`, `goal_status`, `goal_cancel` tools; user,
  session and conversation IDs come exclusively from the authenticated
  Operly->DragonZpyder request, never from the model.
- Five or fewer pre-scheduled separate Hatchet wakes, 2-10 minutes apart.
  The first wake is scheduled one minute after creation.
- PostgreSQL sequence fence, durable receipts, and LangGraph
  conversation checkpoint reuse by the existing `personal_wake.py`.
- A deliberately narrow scheduled MCP capability allowlist:
  `workflow.list`, `system.runtime.status`, `tasks.list`.
- Child wake executions cannot call the native goal-creation tools.
- Cancellation marks a goal cancelled so later scheduled wakes become no-ops.
  Currently queued Hatchet events may remain in the scheduler until fired.
- No user-visible completion claim before durable receipts are observed.

## Critical limitations

This is not deployed or production-accepted merely by merging source.

1. Apply `migrations/20261121_personal_goal_receipts.sql` to the
   durable PostgreSQL database shared by API and worker.
2. Configure the production API with `HATCHET_CLIENT_TOKEN` and its private
   Hatchet client connection settings. Do not publish or return those secrets.
3. Set `DRAGONZPYDER_PERSONAL_GOAL_TOOLS_ENABLED=1` on API.
4. Set `DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED=1` on both
   API and worker, after verifying `require_wake_gate()` in the worker.
5. Keep `DRAGONZPYDER_PERSONAL_MCP_MUTATIONS_ENABLED=0` on worker.
   Confirm external MCP delegation includes an audited read-only tool.
6. Deploy a canary, then verify five separate Hatchet executions, distinct
   timestamps, five durable SQL receipts, no duplicate calls, and a
   terminal completed state. Repeat after a worker restart.
7. Verify cancellation, auth revocation, API outage and inference quota
   behavior; do not silently retry unknown in-flight tool outcomes.

The bounded five-wake implementation is intentionally NOT a general
unbounded recurring workflow service. Expand duration, per-user quotas,
task scheduling idempotency, and deadline reconciliation only after the
production canary succeeds.

## Acceptance prompt

"Over the next 10 minutes, check my Operly workflow list every two minutes.
Remember the outcome of each check and summarize the differences. Do not
change any workflows. Stop automatically when finished."

The user should receive an actual `goal_id` from `goal_schedule`, followed
by independently verifiable `goal_status` receipts. An LLM saying it
scheduled something without tool receipts is not a passing result.
