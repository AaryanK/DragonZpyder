# DragonZpyder FastAPI platform — migration scaffold

This isolated Python service is the **first extracted slice** of the shared
backend currently implemented inside Operly. It is NOT a complete backend
migration or a production replacement for the existing Node.js inference API.

## Migrated, without business access

The original Operly source on `main` is the provenance of these pure modules:

| Source in Operly | New DragonZpyder location |
| --- | --- |
| `packages/agent_runtime/context.py` | `dragonzpyder_platform/runtime/context.py` |
| `packages/agent_runtime/contracts.py` | `dragonzpyder_platform/runtime/agent_contracts.py` |
| `packages/kernel/contracts.py` | `dragonzpyder_platform/runtime/capability_contracts.py` |
| `packages/kernel/schema_validation.py` | `dragonzpyder_platform/runtime/schema_validation.py` |

These are stateless primitives, not a second authorised capability runtime.
They don't open databases or connect to external providers. The old Operly
implementations must remain until callers are migrated and tested.

## Local smoke test

```bash
cd platform_api
python -m pip install -r requirements.txt httpx
python -m unittest discover -s tests -v
uvicorn dragonzpyder_platform.main:app --host 0.0.0.0 --port 8000
```

`GET /healthz` returns HTTP 200 for process liveness while deliberately
reporting `runtime_ready: false`. Do NOT route user traffic to this service
until delegated capabilities, identity, persistence and API contracts exist.

## Next migration steps

1. Extract remaining general-purpose agent runtime, Kernel, registry and policy
   behind DragonZpyder-owned modules, preserving explicit authorisation checks.
2. Define signed, short-lived service-to-service delegations. Operly should
   issue business-scope delegates with business, workspace, principal, allowed
   capability IDs, expiration and approval requirements. The DragonZpyder
   runtime must fail closed on missing or expired scope and must not infer
   permission from credentials or user-supplied identifiers.
3. Migrate personal identity/conversations/jobs/credits to DragonZpyder-owned
   storage using tested, reversible backfills. Never silently reuse Operly
   business sessions or grants.
4. Move general MCP, plugin, connectors, workflows, tools and sandbox execution
   into DragonZpyder in dependency order with tests and rollback paths.
5. Keep Operly's business data, tenancy, memberships, workspace permission
   enforcement, operational APIs and audit trail owned by Operly. Replace its
   direct runtime calls with scoped calls into DragonZpyder and remove duplicate
   runtime modules only after end-to-end compatibility verification.
6. Deploy this FastAPI entry point as a **new** Railway service for testing;
   don't change the existing live DragonZpyder API or custom domains during
   extraction. Once inference parity and auth are tested, switch one route at
   a time and confirm production health and usage metering.

The existing `docs/platform-ownership.md` is the authoritative migration
plan; this directory supplies the first dependency-free code extraction.
