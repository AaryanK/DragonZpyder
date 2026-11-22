# Shared workflow dispatch — consolidation

One canonical agent harness (Deep Agents + LangGraph) and one durable dispatch
infrastructure (Hatchet). Operly remains the authority for business records,
workflow definitions/versions, permission checks, approvals and audit.

The existing DragonZpyder worker registers a single operator-gated
`dragonzpyder-operly-workflow-dispatch` task. It invokes Operly's exact
authenticated dispatch endpoint; no model call, arbitrary capability ID, user
identity or business payload travels in the pulse. Operly uses its existing
reconciliation/lease engine, not a second agent implementation. This is an
incremental dispatch migration, not a new workflow engine. The first adapter
uses minute-resolution wakes, not per-workflow Hatchet timers or events yet.

## Cutover requirements

1. Deploy both repositories with the new modes disabled. Keep all existing
   workflow definitions, runs, approvals, schedules, logs, databases and leases.
2. Provision an independent matching secret to the DragonZpyder worker
   (`DRAGONZPYDER_OPERLY_WORKFLOW_DISPATCH_SECRET`) and Operly API
   (`OPERLY_HATCHET_WORKFLOW_DISPATCH_SECRET`). Never store secrets in a
   workflow, model context, repository or log.
3. Configure `DRAGONZPYDER_OPERLY_WORKFLOW_DISPATCH_ENABLED=1` only after
   the exact internal endpoint is available. Check authenticated GET readiness;
   verify the worker and its task registration. A POST while Operly's local
   driver is active must refuse with HTTP 409.
4. In a disposable isolated environment, explicitly provision the unique
   Hatchet cron once with
   `DRAGONZPYDER_OPERLY_WORKFLOW_CRON_INSTALL_ALLOWED=1 python -m agent_platform.operly_workflow_dispatch install-cron`.
   Check it in Hatchet; remove the install flag after registration. Do not create
   multiple cron identities or a separate cron service.
5. Drain local workers on all replicas before switching
   `OPERLY_WORKFLOW_DRIVER=hatchet`. Verify readiness reports both local
   loops stopped; confirm the existing Hatchet worker starts the pulse.
6. Exercise manual runs, recurring and event triggers, waiting, approval and
   cancellation, duplicate delivery, revoked owner permissions, worker restart,
   long-running actions and a readback of actual business state. Measure trigger
   lag and resource consumption. No production cutover without passing the
   agreed latency and recovery acceptance tests. A dispatched count is not
   completion evidence. Minute polling is transitional and may regress
   sub-minute wait/event latency.
7. If acceptance fails, stop the shared cron; drain in-flight dispatches,
   restore local mode and verify resumed processing. Never silently replay an
   action with uncertain side effects.
8. After demonstrated parity, delete the legacy local polling driver and
   installation compatibility paths. Convert periodic reconciliation to
   durable per-run Hatchet events/schedules with an outbox if latency requires it.

No additional infrastructure service is required by this adapter. Existing
specialized DragonZpyder canaries remain tests; that migration is separate.
