# DragonZpyder agent platform (experimental)

DragonZpyder owns model access, reusable agent harnesses, scheduling,
personal memory, checkpoints, and sandbox adapters. Operly retains workspace
records, memberships, business authorization, and business capability tools.

## Starting point

Install \`api/requirements-agent.txt\` in a separate agent-capable image.
The existing production inference API remains on its minimal requirements.
Set \`DRAGONZPYDER_AGENTS_ENABLED=1\` ONLY in a private test deployment.

Required for the internal agent smoke route:

- \`OPENROUTER_API_KEY\` (server-side, with an upstream hard spend cap)
- \`DRAGONZPYDER_AGENT_MODEL_ID\` (a tool-capable model in the gateway allowlist)
- \`DRAGONZPYDER_RUNTIME_ALLOWED_MODELS\`
- \`DRAGONZPYDER_AGENT_DATABASE_URL\` (PostgreSQL, distinct checkpoint data)
- \`DRAGONZPYDER_AGENT_SERVICE_TOKEN\` (random secret, at least 40 characters)

Optional Langfuse agent callbacks: set \`LANGFUSE_PUBLIC_KEY\`,
\`LANGFUSE_SECRET_KEY\` and \`LANGFUSE_BASE_URL\`. Existing gateway OTLP
export stays separate and unchanged.

When enabled, \`POST /internal/agents/run\` accepts Bearer service token and
JSON \`{"thread_id":"smoke-1","prompt":"Explain rate limiting"}\`.
It provides no real-world execution tools, user identity, or business scopes.
It is NOT a public multi-tenant endpoint.

The Deep Agents harness runs with a read-only virtual filesystem. It uses
LangGraph checkpoints in PostgreSQL, isolates service/thread identities,
caps recursion, and sends traces to Langfuse when configured. This is an
integration slice, not a production-complete autonomous agent.

## Prerequisites before user launch

- Repair upstream OpenRouter HTTP 401 and verify cost/usage events.
- Apply provider-level spend ceilings and per-user atomic budget reservations.
- Create DragonZpyder identity; implement signed, short-lived delegated
  principal and workspace scopes before any external tool usage.
- Add load testing, cancellation, concurrency quotas, streaming, and retries.
- Never let model-generated content supply trusted user or workspace IDs.
- Enable direct sandbox commands ONLY after authorization and approval gates.
- Validate DB backups, privacy controls, data deletion, consent and retention.
