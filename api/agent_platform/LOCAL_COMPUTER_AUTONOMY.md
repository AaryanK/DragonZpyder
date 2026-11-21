# DragonZpyder — persistent local computer agent (first slice)

Status: staging-only source implementation. No deployed recurring cron, no end-user computer access, no model inference, and no unrestricted shell/MCP access.

## What is actually implemented

- Stable local tool calls: time.now, system.memory, system.disk. These accept no arbitrary arguments, paths or shell commands, and return structured JSON-friendly results.
- LocalMonitorAgent.tick uses those tools, compares RAM/disk usage to configurable limits and previous persisted samples, and emits health/attention decisions.
- PostgreSQL stores a timestamped observation, decision and SHA-256 digest per time bucket. Duplicate Hatchet deliveries read the existing result. Transaction-scoped locks and a unique primary key protect concurrent commits.
- Hatchet task dragonzpyder-local-health-v1 is registered on the dedicated worker when explicitly enabled. A named cron can be installed separately by an operator.
- A CLI supports snapshot, migrate, once, history, and install-cron. Reading a local snapshot incurs zero model cost.

## Immediate local demo (no DB, no credentials)

From the DragonZpyder repository's api directory:

    python -m agent_platform.local_monitor_cli snapshot
    pytest -q tests/test_local_monitor.py

The RAM and disk readings refer to the EXECUTION WORKER / CONTAINER, not the user's personal laptop. Where available, a finite cgroup limit determines the RAM scope; otherwise the host RAM is reported.

## Persistent scheduling: explicit staging operation

On an isolated worker with an existing Hatchet connection and a dedicated durable PostgreSQL database, set the server-only environment variables:

    DRAGONZPYDER_AGENTS_ENABLED=1
    DRAGONZPYDER_AGENT_WORKER_ALLOWED=1
    DRAGONZPYDER_STAGE=staging
    DRAGONZPYDER_LOCAL_MONITOR_ENABLED=1
    DRAGONZPYDER_LOCAL_MONITOR_DATABASE_URL=<STAGING_POSTGRES_DSN>
    DRAGONZPYDER_LOCAL_MONITOR_INTERVAL_MINUTES=5
    DRAGONZPYDER_LOCAL_MONITOR_MEMORY_WARN_PERCENT=85
    DRAGONZPYDER_LOCAL_MONITOR_DISK_WARN_PERCENT=90

1. For a one-time schema operation, set DRAGONZPYDER_LOCAL_MONITOR_SCHEMA_INSTALL_ALLOWED=1 and execute: python -m agent_platform.local_monitor_cli migrate
2. Capture a real persisted cycle: python -m agent_platform.local_monitor_cli once
3. Read the last 20 persisted observations: python -m agent_platform.local_monitor_cli history
4. Configure trusted HATCHET_CLIENT_TOKEN. Set DRAGONZPYDER_LOCAL_MONITOR_CRON_INSTALL_ALLOWED=1 and execute ONCE: python -m agent_platform.local_monitor_cli install-cron
5. Verify recurring records in Hatchet and PostgreSQL. Restart the worker and verify recovery. This last end-to-end deployed acceptance is still pending.

Intervals supported: 1, 5, 10, 15, 30, 60 minutes. Do not repeatedly install cron or assume that disabling the worker removes a previously registered cron. Feature flags default to OFF.

## Testable claims and limitations

- Real local tool snapshot and offline unit tests: executed successfully.
- Disposable PostgreSQL restart/concurrency validation: CI test supplied; must pass on GitHub before merge.
- Production deployment, live recurring Hatchet execution, and actual notifications: NOT done.
- LLM-driven tool selection, open-ended objectives, browser/computer actions, external MCP side effects: NOT enabled in this first iteration.
- Receipts prove DB consistency, not externally attested physical hardware state.

## Next integration

Adapt this exact read-only tool registry to the existing Deep Agents / LangGraph capability hub and, later, an MCP adapter. Allow frontier reasoning only for bounded approved tasks and only through the metered gateway. Maintain durable job IDs, timeouts, retries, cancellation, human approvals, scoped permissions and verification. A separately consented local device node will be needed to inspect the user's actual computer.
