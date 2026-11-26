# api

FastAPI inference/API composition, provider transport, ledgers, service images, staging and implementation packages.

Read [repository instructions](../AGENTS.md) and [codebase navigation](../CODEBASE.md). See the [implementation guide](../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`Dockerfile`](Dockerfile) | Non-root Python 3.12 FastAPI service image and Uvicorn entrypoint. | Reviewed |
| [`Dockerfile.business-canary`](Dockerfile.business-canary) | Navigation hint: Dockerfile; source behavior not independently reviewed. | Indexed |
| [`Dockerfile.personal`](Dockerfile.personal) | Navigation hint: Dockerfile; source behavior not independently reviewed. | Indexed |
| [`Dockerfile.staging`](Dockerfile.staging) | Navigation hint: Dockerfile; source behavior not independently reviewed. | Indexed |
| [`inference.mjs`](inference.mjs) | Legacy Node private inference handler with backend bearer, model allowlist, bounded parsing and per-hour admission. | Reviewed |
| [`main.py`](main.py) | FastAPI gateway composition root, lifespan, router registration, caller auth and catch-all inference dispatch. | Reviewed |
| [`observability.py`](observability.py) | Configures OpenTelemetry/Langfuse OTLP export and redacted inference spans; full encrypted payload storage is separate. | Reviewed |
| [`package.json`](package.json) | Data/configuration fixture: package; inspect schema and consumers. | Indexed |
| [`provider_gateway.py`](provider_gateway.py) | Scoped OpenRouter transport, operation classification, provider-key selection, metering and tracing. | Reviewed |
| [`requirements-agent.txt`](requirements-agent.txt) | Navigation hint: requirements agent; source behavior not independently reviewed. | Indexed |
| [`requirements-personal.txt`](requirements-personal.txt) | Navigation hint: requirements personal; source behavior not independently reviewed. | Indexed |
| [`requirements.txt`](requirements.txt) | Navigation hint: requirements; source behavior not independently reviewed. | Indexed |
| [`server.mjs`](server.mjs) | Legacy standalone Node HTTP API server; wraps internal inference with concurrency limits and headers. | Reviewed |
| [`staging.css`](staging.css) | Stylesheet: staging; inspect selectors and importing page. | Indexed |
| [`staging.js`](staging.js) | Navigation hint: staging; source behavior not independently reviewed. | Indexed |
| [`staging_app.py`](staging_app.py) | Password-gated staging smoke lab for agent, search, memory and Hatchet diagnostics; no workspace/computer grants. | Reviewed |
| [`staging_ui.html`](staging_ui.html) | Navigation hint: staging ui; source behavior not independently reviewed. | Indexed |
| [`usage_ledger.py`](usage_ledger.py) | Append-only PostgreSQL metering, normalized token/cost usage and optional AES-GCM payload escrow; unknown cost is not zero. | Reviewed |

## Modular streaming voice

The optional modular route uses LiveKit WebRTC, Deepgram Flux STT and Aura streaming TTS, with no separate reasoning model. The canonical chat ledger and owner-scoped harness execute completed transcripts; original session authority is checked repeatedly. The browser prefers modular when the operator flag is enabled. Existing realtime transport remains independently gated. The worker uses a dedicated internal service credential and room nonce, not user cookies. Configure LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET and DRAGONZPYDER_VOICE_WORKER_TOKEN; worker additionally needs DEEPGRAM_API_KEY and DRAGONZPYDER_VOICE_API_ORIGIN. Apply the modular voice session migration after the native voice migration before enabling DRAGONZPYDER_MODULAR_VOICE_ENABLED. The duration/session quotas are admission bounds, not a verified provider-dollar ceiling. No live call, production migration or deployment has been performed. Full confirmed answer playback is streamed by TTS, but agent generation is not yet streamed into TTS; interruption does not replay an accepted task. Android modular transport and latency benchmarks remain pending.
