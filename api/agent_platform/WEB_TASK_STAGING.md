# DragonZpyder Web Harness — Staging deployment contract

This branch introduces a real, permissioned Personal Tasks view and protected
operator activity view. Neither page is a substitute for the user-identity
service, token budget gateway, PostgreSQL migrations, or a registered Hatchet
worker. The feature flags below default to OFF.

## User-visible routes

- `/app`: existing chat stays operational; the "Tasks & activity" sidebar
  entry opens the bounded task drawer (live 2-second *polling*, not SSE).
- `GET /api/harness/tasks`: lists only the signed-in Personal owner's tasks
  via verified Operly session and Personal scope.
- `POST /api/harness/tasks`: starts a task; requires anti-CSRF proof and a
  canonical idempotency UUID. `kind=probe` is zero-cost and tests the actual
  Hatchet worker. `kind=agent` can be submitted only if transactional gateway
  budget reservation is active; otherwise the UI disables "Run agent".
- `GET /api/harness/tasks/{id}`: owner-scoped status, sanitized activity
  events, and decrypted *owner-only* final answer.
- `POST /api/harness/tasks/{id}/cancel`: fences a stale worker's completion
  and marks a task cancelled; does not claim to interrupt an in-flight
  provider request before provider cancellation is implemented.
- `/admin`: existing allowlisted administrator page. "Harness activity"
  displays cross-account operational metadata and safe event messages.
  It never exposes stored prompts, answers, function arguments or secrets.

The Python Web backend, not the browser, authenticates the private
`/internal/web-tasks` API using a service token; no browser-provided owner,
workspace or URL is accepted.

## Staging topology

Existing `DragonZpyder Agent Test Lab` uses `api/staging_app.py`,
**NOT** `api/main.py`. The feature branch exposes the new private router
from both entrypoints. The Lab must use `Dockerfile.staging`, root
`/api`, `uvicorn staging_app:app`. The dedicated Hatchet worker must use
`Dockerfile.staging`, root `/api`,
`python -m agent_platform.worker`.

The React Web preview uses root `/web`, `web/Dockerfile`, and
`uvicorn main:app`. Keep the preview separate from production.

## Required staging variables

**API / Lab:**

```env
DRAGONZPYDER_WEB_TASKS_ENABLED=1
DRAGONZPYDER_GOAL_STORE_ENABLED=1
DRAGONZPYDER_WEB_TASKS_PAID_ENABLED=0
DRAGONZPYDER_GOALS_DATABASE_URL=<STAGING_POSTGRES_URL>
DRAGONZPYDER_GOALS_ENCRYPTION_KEY=<ONE_VALID_FERNET_KEY_SHARED_WITH_WORKER>
DRAGONZPYDER_WEB_TASK_SERVICE_TOKEN=<NEW_PRIVATE_RANDOM_TOKEN_40_PLUS>
HATCHET_CLIENT_TOKEN=<EXISTING_STAGING_HATCHET_TOKEN>
HATCHET_CLIENT_HOST_PORT=<EXISTING_STAGING_PRIVATE_HOST>
RAILWAY_ENVIRONMENT_NAME=staging
```

**Worker:** the same task/store flags, database URL, Fernet key and Hatchet
credentials, plus `DRAGONZPYDER_AGENTS_ENABLED=1` and
`DRAGONZPYDER_AGENT_WORKER_ALLOWED=1`. Paid agent execution stays disabled
until a matched per-job budget and model-provider test passes.

**Web preview:**

```env
DRAGONZPYDER_API_ORIGIN=https://<STAGING_LAB_PUBLIC_DOMAIN>
DRAGONZPYDER_WEB_TASK_SERVICE_TOKEN=<SAME_RANDOM_SERVICE_TOKEN_AS_LAB>
DRAGONZPYDER_ADMIN_EMAILS=<VERIFIED_ADMIN_EMAIL_ALLOWLIST>
```

Do not put Fernet, OpenRouter, Hatchet or private service credentials in
`VITE_` variables or React JS, and do not reuse a production application
token. The Administrator allowlist must use a verified identity; the default
empty allowlist denies all system-wide access.

**DB schema (operator-only, staging-only):** run
`python -m agent_platform.staging_task_migrate` once with
`DRAGONZPYDER_STAGE=staging` and
`DRAGONZPYDER_APPLY_STAGING_TASK_SCHEMA=1`. The SQL migration is explicit;
the API refuses to boot if the tables are absent. This applies the complete
`goal_store.SCHEMA`, including the new encrypted task ledger and events.

## Verify before any user's paid agent task

1. Verify `/healthz` from the staging Lab and Web preview; ensure the
   private service token does NOT appear in browser network requests.
2. Sign in on the Web preview and establish a Personal session.
3. Open Tasks and launch **Test worker**. Watch status transition from
   queued to running to completed and confirm five persisted events.
4. Refresh the page and verify all task events and the result are still there.
5. Log into a different Personal account and verify no task or answer is
   visible. An administrator sees status, timestamp and generic events only.
6. Cancel a task and verify a stale worker cannot mark it completed.
7. Leave **Run agent** disabled unless the gateway's atomic reservation
   system is in a known ready state and a per-task spending cap is enforced.
   Model output is not automatically considered independently verified.
8. Verify execution and cost records against actual Hatchet, PostgreSQL and
   Langfuse, then run the same task from the real web UI.
9. Do NOT merge the draft PR or deploy to the public production website
   until all above gates and the dependency/security audits pass.

## Evidence and known limitations

The real embedded Hatchet CI checks the async fire-and-forget dispatch path
for a browser-style `probe` task and checks the stored task events/results
in PostgreSQL. Web auth/CSRF/admin tests and React/Vite build run separately.
Cross-service staging deployment and real user-operated paid LangGraph runs
are NOT established by these isolated CI tests.

The frontend currently polls every two seconds; this is near-live status,
not server push. The activity feed deliberately contains sanitized execution
events rather than private chain of thought or tool input/output content.
