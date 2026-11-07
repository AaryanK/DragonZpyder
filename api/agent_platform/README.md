# DragonZpyder agent platform — staged integration

DragonZpyder owns the shared inference, agent harness, durable jobs, personal
memory, and tool adapters. **Operly retains workspaces, business data, business
authorization, approvals and workspace-specific capabilities.**

This is a reviewable integration slice, **not a production migration**. The
existing production API, Web, Operly worker and sandbox have not been changed.

## Six components

1. **Deep Agents + LangGraph:** `runtime.py` creates a bounded, read-only
   deep agent with virtual files and PostgreSQL checkpoints. It does not
   provide direct host shell, network, writes or real-world tools.
2. **OpenRouter:** the existing API provider gateway remains the public model
   gateway; the agent runtime uses the first-party `ChatOpenRouter` client
   inside the same protected DragonZpyder service. It requires a valid key.
3. **Langfuse:** the existing inference gateway retains OpenTelemetry export.
   Deep Agents can additionally use Langfuse's LangChain callback handler.
4. **Hatchet:** `jobs.py` defines a named bounded internal task;
   `worker.py` boots a dedicated worker. Hatchet provides scheduling,
   cron and task recovery; no custom timer/queue code is added.
5. **Mem0 + PostgreSQL:** `memory.py` provides explicit-consent personal
   memory via Mem0 and pgvector. This is NOT yet wired to the chat route;
   the DragonZpyder identity provider and deletion/retention policies
   must be finished before it is exposed to users.
6. **Existing Operly sandbox:** `computer.py` implements the existing
   Bearer + HMAC request/response protocol. The current sandbox runner
   REQUIRES an Operly workspace ID; it cannot be used as a personal computer
   by inventing a fake workspace. It is not registered as an agent tool.

## Install in a separate agent-enabled image

```sh
python -m pip install -r api/requirements-agent.txt
```

A service may enable the internal smoke endpoint with the following secrets:

- `DRAGONZPYDER_AGENTS_ENABLED=1` — default is off
- `OPENROUTER_API_KEY` — a rotated working key with a HARD upstream spend cap
- `DRAGONZPYDER_RUNTIME_ALLOWED_MODELS` — comma-separated model allowlist
- `DRAGONZPYDER_AGENT_MODEL_ID` — a tool-capable allowlisted model
- `DRAGONZPYDER_AGENT_DATABASE_URL` — a backed-up PostgreSQL checkpoint DSN
- `DRAGONZPYDER_AGENT_SERVICE_TOKEN` — separate, random 40+ character token
- Optional `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
  `LANGFUSE_BASE_URL` for agent traces

The guarded `POST /internal/agents/run` accepts only the internal Bearer token
and `{"thread_id":"smoke-1","prompt":"Explain rate limiting"}`.
It runs in a service-scoped thread, not a user/workspace scope. Do not publish
this route as a paid or multi-tenant service.

To test Hatchet separately, configure `HATCHET_CLIENT_TOKEN`,
`DRAGONZPYDER_AGENTS_ENABLED=1`, and
`DRAGONZPYDER_AGENT_WORKER_ALLOWED=1`; then launch
`python -m agent_platform.worker` from `api/`. The returned task object in
`make_agent_task(Hatchet())` supports `schedule()` and `create_cron()`,
but schedule-creation endpoints are intentionally not public yet.

For Mem0 set `DRAGONZPYDER_MEMORY_DATABASE_URL` to a pgvector-enabled
Postgres database, `DRAGONZPYDER_EMBEDDING_API_KEY`,
`DRAGONZPYDER_MEM0_LLM_MODEL`, `DRAGONZPYDER_MEM0_EMBED_MODEL`, and
`DRAGONZPYDER_EMBEDDING_DIMENSIONS` matching the model output. Optional:
`DRAGONZPYDER_EMBEDDING_BASE_URL`. Enable `CREATE EXTENSION vector` in a
properly authorized migration. Standard PostgreSQL images may not contain
pgvector. Do not store user memories until identity, consent and erasure work.

## Isolated Railway staging provisioned on November 7, 2026

- **Agent Test Lab**: password-protected browser harness, backed by the
  existing staging PostgreSQL checkpoint service.
- **Hatchet Lite**: independent Hatchet control plane, an independent Postgres,
  and a generated-secret dashboard at
  `https://hatchet-staging.up.railway.app/`. Sign-up is disabled. An administrator
  still needs to create an unrestricted worker token under **Settings → API Tokens**.
  Store it in the dedicated worker service as `HATCHET_CLIENT_TOKEN`.
  Do not paste it into an issue, chat, or browser test page.
- **Memory Postgres**: separate PostgreSQL 18 instance with pgvector installed;
  the staging lab uses a Railway variable reference, not copied credentials.
  The memory smoke endpoint writes only synthetic data, searches it and deletes it.
- **OpenRouter embeddings**: explicitly enabled in staging, reuses the
  already rate/spend-limited staging OpenRouter key for
  `openai/text-embedding-3-small` at dimension 1536.
- **Langfuse**: agent callback integration is ready, but requires Langfuse
  project public/secret keys and base URL in staging before traces can be verified.
- **Operly computer**: retained as an adapter only; do not cross the production
  workspace trust boundary from this staging project.

### Staging acceptance

Open the lab and inspect the Hatchet and pgvector readiness indicators.
Use **Run synthetic memory test** only with fictional/test data; it verifies
add/search/delete and may make a small charged inference and embedding request.

A dedicated worker should use:
- `HATCHET_CLIENT_TOKEN` (created inside Hatchet Dashboard)
- `HATCHET_CLIENT_HOST_PORT=${{hatchet.HATCHET_CLIENT_HOST_PORT}}`
- `HATCHET_CLIENT_TLS_STRATEGY=none` (Railway-private network only)
- `DRAGONZPYDER_AGENT_WORKER_ALLOWED=1`
- `DRAGONZPYDER_AGENTS_ENABLED=1`
- staging PostgreSQL checkpoint DSN and OpenRouter test key as Railway references.

Only then test the zero-model-cost `dragonzpyder-staging-ping` task, followed
by one bounded agent job. Neither personal cron creation nor workspace
execution is exposed to untrusted users.

Mem0 OSS uses SQLite for some history by default. Staging can test pgvector
storage, but production requires a durable history/retention and erasure
design. Agent outputs must be billed through the shared DragonZpyder
accounting boundary before multi-tenant release.

## Release gates

- Repair and verify the November 7 OpenRouter 401 → gateway 502 incident.
- Run a real model/tool-calling smoke in an isolated test environment.
- Validate provider spend caps, atomic user budgets and usage reconciliation.
- Reconcile canonical source branches and existing Railway duplicates.
- Implement verified DragonZpyder identity and signed, short-lived Operly
  capability delegation before any workspace tools reach the harness.
- Test Hatchet worker/schedules, failure recovery, quotas and cancellation.
- Test Mem0 embeddings, pgvector migrations and user deletion.
- Test Operly runner with correct workspace permissions and signed responses.
- Add personal-computer authority separately; do NOT bypass workspace scope.
- Keep old Node servers until the combined-project Railway services no
  longer depend on `npm start`; only then delete the obsolete runtime code.
