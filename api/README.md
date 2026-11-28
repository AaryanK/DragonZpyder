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

## OpenRouter-only voice (preferred gated transport)

The browser uses local AudioWorklet energy-based utterance detection, OpenRouter Whisper Large V3 Turbo STT, the canonical authenticated chat graph, and Kokoro 82M / af_alloy MP3 playback. No LiveKit service, Deepgram account, or extra paid subscription is required for this path. The same OpenRouter account can supply the existing DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY; the verified non-resetting cap (at most $0.50 for the initial rollout) and persistent usage ledger remain mandatory. Configure DRAGONZPYDER_OPENROUTER_VOICE_ENABLED only after applying the native voice, modular voice and OpenRouter voice SQL migrations, enabling the native chat request ledger, and verifying provider key and budget. Optional LiveKit and native realtime adapters remain separately gated. Speech is request-based per detected utterance and per committed answer segment, not continuous streaming STT or token-to-audio. Barge-in stops playback, but an accepted request is not automatically replayed or replaced. Voice sessions are limited to five minutes and twenty turns, four speech segments maximum per response. Long responses remain in chat. Native Android and measured live latency remain unqualified. No deployment, migration or paid calls performed.

## Transport-neutral voice session contract v1

All supported clients use the same backend: authenticated session creation at POST /v2/personal/voice/sessions; POST /v2/personal/voice/sessions/{session_id}/turn with event_id, base64 audio, format and explicit sample_rate/channels when using raw PCM; POST /v2/personal/voice/sessions/{session_id}/speech/{event_id}/{index} returns the committed answer segment as MP3; POST /v2/personal/voice/sessions/{session_id}/end revokes session authority. Existing provider-specific paths remain compatibility aliases. Browser and native Android/iOS clients use existing DragonZpyder session and CSRF authentication. An authenticated user may explicitly create a short-lived, session-only external bridge grant with source=discord, telephony or external and delegate=true. Return the grant once; pass it as Authorization: Bearer <grant> only to that session's endpoints. Store only a digest; validate original account/session authority on each call. No account mapping from untrusted channel IDs, no login cookie sharing, no arbitrary tool or model authority. The bridge integration must obtain user authorization and protect the token. The backend accepts canonical mono 16 kHz WAV, PCM signed little-endian 16-bit mono/stereo at 8/16/24/48 kHz, and mono G.711 mu-law/A-law at 8 kHz; converts to mono 16 kHz WAV before the same metered OpenRouter STT/harness/TTS path. Each utterance is 0.15–30 seconds. Opus/RTP/WebSocket packet framing, jitter buffering, per-speaker segmentation, consent and output re-encoding belong in transport adapters. These adapters are not implemented by this change. MP3 is the common egress; voice bridges decode/resample for their own transport. Session lifetime and quotas are unchanged. No deployment or paid testing performed.

### Admin operations

Existing independent admin bearer protects /internal/admin/activity and usage. Activity reads bounded aggregate native request, conversation, goal, workflow and memory counts plus runtime initialization; no customer payloads or identity DB grants. The ledger includes daily UTC usage. See OBSERVABILITY.md for limits.


### Admin account analytics

The native admin activity report reads aggregate account states, native signup counts and unexpired session counts using the existing restricted identity database role in a read-only transaction, excluding operator test identities. Distinct request owners are counted across the selected interval, not by summing daily counts. Sessions are not devices or online presence; device/country/referral data are not provided by these stores. No new grants or credentials. CI and live data verification pending.
