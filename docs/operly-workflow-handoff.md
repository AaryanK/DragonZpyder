# Operly workflow retirement: first-party wake handoff

The existing Hatchet deployment becomes the single wake clock, without new
Railway services. This opt-in compatibility slice does NOT replace Operly
definitions, leases, external effects or execution state with native
DragonZpyder graphs yet. It replaces the local scheduler's polling loop only
after the paired Operly deployment has switched to external-driver mode.

The worker registers `dragonzpyder-operly-workflow-compat-dispatch` only
with `DRAGONZPYDER_OPERLY_WORKFLOW_HANDOFF_ENABLED=1` and a dedicated
`DRAGONZPYDER_OPERLY_WORKFLOW_HANDOFF_SECRET` matching the Operly server.
The task calls one fixed HTTPS endpoint with no user/model-supplied args.
It never stores or returns the proof. HTTP 200 must carry a dispatch receipt
explicitly indicating completion is NOT verified.

No cron is installed at startup. After inventory, backup, synthetic
cross-repository acceptance and operator approval, reconcile the named cron
before installing it once using:

```sh
cd api
python -m agent_platform.workflow_compat_dispatch --install-cron
```

This requires the temporary explicit cron-install gate
`DRAGONZPYDER_WORKFLOW_HANDOFF_CRON_INSTALL_ALLOWED=1`.
Remove the install permission after use. Never auto-create cron on redeploy.
A one-minute cadence is slower than the existing two-second poll; measure
schedule, event and approval continuation latency and do not cut over if
unacceptable. For rollback disable/delete this cron, drain current dispatches,
and restore Operly's local driver while preserving all existing DB leases.

## Next: native ownership
Reuse the existing agent harness, MCP broker, LangGraph and Hatchet for one
provider-neutral durable workflow contract. Preserve legacy definition/version
IDs, timezones and trigger cursors; never copy provider credentials or accept
email-based identity matching. Implement approval/resume, exact-capability
authority, mutation evidence and recovery before migrating production runs.
Do not pretend this compatibility clock is the final universal executor.
