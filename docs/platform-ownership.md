# DragonZpyder-first infrastructure migration

**Target:** DragonZpyder is the intelligence platform and service provider.
Operly is an authorised business client, not the owner of AI infrastructure.

## Ownership contract

| Capability | Owner | Operly relationship |
| --- | --- | --- |
| Model catalog, routing, provider adapters, prices, multimodal APIs | DragonZpyder | Calls authenticated DragonZpyder inference APIs |
| Personal conversations, files, personal memory, AIC and personal agents | DragonZpyder (migration target) | No implicit access without consent |
| AI runtime lifecycle, tools, scheduling, sandbox execution | DragonZpyder platform (migration target) | Executes with permission-scoped business tool delegates |
| Business accounts, workspaces, orders, inventory, customers, policies | Operly | Operly is authority for its own tenancy and tools |
| Per-business memberships, approvals and access audits | Operly | Never inherited from personal identity |
| Provider credentials (OpenRouter, direct models) | DragonZpyder (target) | Never sent or copied into Operly's user-facing apps |

## Implemented and deployed: Inference migration (Phase A)

1. DragonZpyder Web hosts authenticated `/internal/v1/chat/completions`,
   `/internal/v1/models`, and `/internal/v1/health`. These service-only
   endpoints are separate from personal-user `/mesh/*` APIs.
2. Requests require a dedicated bearer token with a fixed model allowlist,
   bounded request sizes and capped output. They never run tools.
3. Operly's Runtime 1.0 inference adapter can select
   `OPERLY_AGENT_MODEL_PROVIDER=dragonzpyder`, with explicit URL allowlist
   and the same backend-only service token.
4. Railway uses a cross-service secret reference. Operly starts with
   DragonZpyder as its selected agent inference provider.
5. CI uses mocked provider responses and verifies auth, reject paths and
   the OpenAI-compatible request/response transport; it spends no credits.

This proves the new direction architecturally but **does not yet prove every
live model request**. Watch provider errors, quota usage and client latency.

## Next migration stages, in dependency order

### B. Provider ownership and cost controls

- Create a new provider credential owned by the DragonZpyder service.
  The current DragonZpyder OpenRouter key temporarily references an Operly
  Railway variable. Rotate after the new owned key is provisioned.
- Add durable per-principal request/usage records, provider token usage,
  real USD accounting, budgets and hard provider-enforced limits.
- Make model pricing and capability declarations versioned, evaluable and
  owned by DragonZpyder. Keep selected provider APIs replaceable.

**Acceptance:** revoke the old Operly provider credential without disrupting
DragonZpyder inference, and demonstrate a per-user spend stop before charges.

### C. Migrate remaining direct inference calls

- Enumerate all Operly model consumers (agent runtime, Studio coding,
  research/analysis, workflow helpers and plugin orchestration).
- Replace direct model provider dependencies with narrow DragonZpyder client
  adapters and model-capability contracts. Run existing evaluation suites.
- Keep a staged rollback for each moved route; remove direct Operly provider
  keys only after all consumers have migrated.

**Acceptance:** end-to-end traces for each harness show Operly -> DragonZpyder
-> provider, and none of the moved routes reads external model API keys.

### D. Move personal state and agent infrastructure

- Introduce stable DragonZpyder users, session issuance and migration mapping;
  do not break existing Operly accounts or blindly reuse business sessions.
- Move personal chat history, attachments, persistent spaces, memory and agent
  schedules to DragonZpyder-owned stores using idempotent backfills.
- Create a shared DragonZpyder agent runtime that accepts only signed,
  scoped capability delegates. Operly keeps business records, access control,
  human approvals, idempotency and audit events on its side.
- Never grant personal agents access to unrelated business data by default.

**Acceptance:** a Personal conversation works without calling Operly's
personal-chat endpoint, while business actions are still blocked by Operly
unless membership, scope and approval are valid.

### E. Multimodal, realtime and workflows

- Consolidate text, image, speech, video, tool routing and live companion
  sessions behind DragonZpyder's client-agnostic APIs.
- Add durable media jobs, storage, webhook signature verification, receipts,
  retries and usage quotas.
- Make n8n an optional workflow execution adapter, not the source of truth
  for user permissions, money, or task completion.
- Require explicit approval for consequential external actions.

**Acceptance:** phone/web/desktop clients receive the same status, outputs and
cost receipts, and can resume work safely across devices.

## Safe deployment order

1. Land compatibility code without switching model routes.
2. Verify authentication and contract tests using mock models.
3. Configure same-token backend authentication and deploy.
4. Switch one low-volume route and monitor health, errors and cost.
5. Transfer the authoritative model credential to DragonZpyder.
6. Expand to other inference consumers with per-route rollback.
7. Move data and runtime ownership after migration/backfill testing.

**Non-goal:** moving Operly business databases, business memberships or
policy enforcement into a universal personal AI service.


## Independent API service (October 2026)

The production API code now has its own process in the `api/` directory.
It implements `GET /healthz`, service-authenticated `GET /v1/models`,
`POST /v1/chat/completions`, and compatible `/internal/v1/*` routes.
It has no personal website, login proxy, or business/tenant database.
Only the restricted inference contract is migrated in this cut.

The intended external hostname is `api.dragonzpyder.xyz`; the Operly
backend should prefer the private Railway endpoint
`http://dragonzpyder-api.railway.internal/internal/v1` while both services
run in the same Railway project. The API bearer token must be stored only
in service secrets and Operly's backend reference. API callers cannot use
browser cookies or business-session credentials.

The old DragonZpyder Web `/internal/v1/*` endpoint is kept temporarily for
rollback; do not remove until Operly's new internal target is verified.
