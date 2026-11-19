# Five-minute synthetic Operly business canary on Railway staging

This isolated test service runs the **checked-in synthetic broker contract suite** on a five-minute Railway cron. It does not authenticate to Operly, access user workspaces, call a model, or write any business records.

## Execution contract

Repository: AaryanK/DragonZpyder
Branch: test/operly-business-five-minute-staging-20261119
Dockerfile: /api/Dockerfile.business-canary
Root directory: /api
Start command: python -m agent_platform.synthetic_business_cron
Cron expression: */5 * * * *
Required, server-only environment variables:

    DRAGONZPYDER_STAGE=staging
    DRAGONZPYDER_SYNTHETIC_BUSINESS_CANARY_ENABLED=1

**Do not provide** OPENROUTER_API_KEY, HATCHET_CLIENT_TOKEN, DRAGONZPYDER_OPERLY_BROKER_TOKEN, or DRAGONZPYDER_OPERLY_CANARY_LEASE. The runner fails closed if any is set.

The process uses the real DragonZpyder Operly broker client but mocks its HTTP transport using deterministic fake responses, exercising the discovery-execute sequence, rejected permissions, revocation, workspace separation, and prohibition of sales/finance writes. The process records one sanitized JSON result in the Railway deployment logs and exits 0 only if tests pass.

## Verify it

1. Confirm GitHub CI passes the new runner unit tests and the synthetic business broker tests.
2. Deploy this Dockerfile to a separate *staging-only* Railway service, never to the production Operly worker, and check the schedule is exactly five minutes.
3. Inspect several separate Railway cron invocations; look for `event=dz_business_synthetic_canary` and `status=passed` JSON records and Railway's succeeded execution state.
4. Deliberately introduce a failure on a feature branch and verify the canary exits nonzero and Railway reports a failed cron. Restore only after the test.
5. Track and cap Railway compute costs; no LLM/provider credits are spent.

## What remains unproven

This does not validate a real signed Operly lease, actual Operly business provider state, a live MCP connection, persistence of a goal across five-minute Hatchet wakes, or user authorization renewal. The current Operly service is production-only in the accessible project, and its read-only broker remains unmerged in Operly PR #373.

To test actual autonomous business reads: deploy an isolated Operly broker to staging with disposable workspace data, obtain a newly authorized short-lived read-only lease on each Hatchet wake, and independently inspect the read receipts. Never reuse an expired lease or execute against production customer data.

**Merge policy:** synthetic cron success alone is insufficient for merging the full agent/business integration stack to production.
