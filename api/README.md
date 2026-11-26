# api

FastAPI inference/API composition, provider transport, ledgers, service images, staging and implementation packages.

Read [repository instructions](../AGENTS.md) and [codebase navigation](../CODEBASE.md). See the [implementation guide](../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`Dockerfile`](Dockerfile) | Non-root Python 3.12 FastAPI service image and Uvicorn entrypoint. | Reviewed |
| [`Dockerfile.business-canary`](Dockerfile.business-canary) | Navigation hint: Dockerfile; source behavior not independently reviewed. | Indexed |
| [`Dockerfile.personal`](Dockerfile.personal) | Navigation hint: Dockerfile; source behavior not independently reviewed. | Indexed |
| [`Dockerfile.staging`](Dockerfile.staging) | Navigation hint: Dockerfile; source behavior not independently reviewed. | Indexed |
| [`inference.mjs`](inference.mjs) | Navigation hint: inference; source behavior not independently reviewed. | Indexed |
| [`main.py`](main.py) | FastAPI gateway composition root, lifespan, router registration, caller auth and catch-all inference dispatch. | Reviewed |
| [`observability.py`](observability.py) | Navigation hint: observability; source behavior not independently reviewed. | Indexed |
| [`package.json`](package.json) | Data/configuration fixture: package; inspect schema and consumers. | Indexed |
| [`provider_gateway.py`](provider_gateway.py) | Scoped OpenRouter transport, operation classification, provider-key selection, metering and tracing. | Reviewed |
| [`requirements-agent.txt`](requirements-agent.txt) | Navigation hint: requirements agent; source behavior not independently reviewed. | Indexed |
| [`requirements-personal.txt`](requirements-personal.txt) | Navigation hint: requirements personal; source behavior not independently reviewed. | Indexed |
| [`requirements.txt`](requirements.txt) | Navigation hint: requirements; source behavior not independently reviewed. | Indexed |
| [`server.mjs`](server.mjs) | Navigation hint: server; source behavior not independently reviewed. | Indexed |
| [`staging.css`](staging.css) | Stylesheet: staging; inspect selectors and importing page. | Indexed |
| [`staging.js`](staging.js) | Navigation hint: staging; source behavior not independently reviewed. | Indexed |
| [`staging_app.py`](staging_app.py) | Navigation hint: staging app; source behavior not independently reviewed. | Indexed |
| [`staging_ui.html`](staging_ui.html) | Navigation hint: staging ui; source behavior not independently reviewed. | Indexed |
| [`usage_ledger.py`](usage_ledger.py) | Navigation hint: usage ledger; source behavior not independently reviewed. | Indexed |
