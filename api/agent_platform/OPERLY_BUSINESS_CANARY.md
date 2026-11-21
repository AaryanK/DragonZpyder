# Operly business capability autonomy — staging canary

**Not a production deployment.** This feature is off by default. It uses the existing signed, short-lived, read-only Operly capability broker from the unmerged Operly PR #373 and the DragonZpyder client previously proposed in draft PR #37. It does not create new credentials, authorize workspaces, or store delegation tokens.

## What the code can do

- `daily_operations`: discover and invoke `workspace.summary.read`, `workspace.attention.list`, and `workspace.activity.list` in sequence.
- `business_search`: discover and invoke `workspace.search` with an approved bounded query.
- `customer_review`: discover and invoke `workspace.customer.snapshot` for an already authorized contact ID.

These are **read-only operations**. The canary verifies an exact approved capability ID and read-only classification before each execution. Operly independently validates the signed lease, current workspace membership, permissions, module state and capability risk at every invocation. On denial, the canary stops rather than retrying with broader privileges.

The result contains only a status, tool IDs, minimal counts, hashes of returned data and coarse error codes. The raw customer/business payload, service credentials and signed lease are never stored in the result. A result hash is **not** independent verification of the underlying business facts.

## No-network test

From DragonZpyder `api/` with opt-in agent requirements:

    pytest -q tests/test_operly_business_canary.py

The test monkeypatches HTTP with a synthetic broker implementing the documented Operly read-only protocol. It exercises success, revocation, wrong scope, hidden capability, malformed responses, sensitive-data redaction, denial of mutations and restricted endpoint/credential handling. It does **not** connect to a deployed Operly service.

## Optional real staging read test

Only after Operly PR #373 and the matching read-only broker are deployed in an isolated staging environment:

    DRAGONZPYDER_STAGE=staging
    DRAGONZPYDER_OPERLY_BUSINESS_CANARY_ENABLED=1
    DRAGONZPYDER_OPERLY_BROKER_URL=http://<TRUSTED-STAGING-SERVICE>.railway.internal:8080/api/internal/agent-tools
    DRAGONZPYDER_OPERLY_BROKER_TOKEN=<SERVER-ONLY-SERVICE-CREDENTIAL>
    DRAGONZPYDER_OPERLY_CANARY_LEASE=<FRESH-OPERLY-SIGNED-READONLY-LEASE>

Then, from a private operator-controlled staging shell:

    python -m agent_platform.business_canary_cli daily_operations
    python -m agent_platform.business_canary_cli business_search --query "synthetic"
    python -m agent_platform.business_canary_cli customer_review --contact-id "synthetic-contact"

Never paste tokens or real customer data into chat, PRs, CLI args, or model prompts. These commands are examples, not records of live execution.

## Why recurring business autonomy is still blocked

Operly-issued delegated leases expire after about 240 seconds. A scheduled agent waking tomorrow **cannot** securely reuse that lease. The next work is an authorization-renewal handoff in which Operly (not DragonZpyder or the model) mints a new scope-limited lease only after checking the user's current authorization and policy. Hatchet should schedule the goal ID, never a stored lease or customer data. The system must honor revocation, pause for approvals, and verify outcome receipts.

No invoice, payment, sale, membership change, message send, or production mutation may be performed by this canary. A green test suite does not prove successful model-selected tools, durable real business execution, or live MCP server availability.

## Acceptance gates before merging with the general autonomous harness

1. Operly Kernel and broker contract tests green, including permission revocation and tenant isolation.
2. DragonZpyder simulated broker tests green, and three real **staging** read cycles with a real short-lived lease and disposable business records succeed.
3. Demonstrate an authorized new lease for every scheduled wake, rather than caching tokens inside Hatchet, LangGraph checkpoints or memory.
4. Demonstrate independent side-effect verification for any later write workflow; human approval and budget controls remain enforced upstream.
5. Observe cancellation and worker restart without cross-workspace leakage or duplicate writes.

References:
- DragonZpyder harness foundation: https://github.com/AaryanK/DragonZpyder/pull/37
- Operly signed-delegation wrapper: https://github.com/AaryanK/Operly/pull/373
- Current local tool/schedule test work: https://github.com/AaryanK/DragonZpyder/pull/42
