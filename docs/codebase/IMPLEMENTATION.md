# Implementation and execution flows

Operator production acceptance uses `scripts/production_acceptance_probe.ts` on the existing private Railway Function. An operator-only expiring principal is provisioned by `api/identity/schema_operator_test_manual.sql`; normal password login, session cookies, CSRF and the canonical chat/request ledger execute each test. Identity RLS expiry and protected provisioning fields keep these principals bounded. This path adds no public auth endpoint, provider bypass, workspace grant or alternate agent runtime. Live evidence is reported separately from CI.

Source baseline: [d38aa819af86](https://github.com/AaryanK/DragonZpyder/tree/d38aa819af869c3b4f5d979939441b711324d3e5). This describes inspected entrypoints and links to adjacent files; it does not supersede [AGENTS](../../AGENTS.md), [V4](../universal-harness-v4.md), or [ownership](../platform-ownership.md).

## 1. Process and trust boundaries

- [web/Dockerfile](../../web/Dockerfile) builds and tests React/Vite with Node 22, then serves it through Python FastAPI. [web/main.py](../../web/main.py) owns dispatch, security headers, native API forwarding, compatibility Operly forwarding and admin access. [web/frontend/src/main.jsx](../../web/frontend/src/main.jsx) hydrates or mounts the React app; [pages.jsx](../../web/frontend/src/pages.jsx) selects page and compatibility controllers. [web/app.js](../../web/app.js) still owns important transitional chat state and request logic.
- [api/Dockerfile](../../api/Dockerfile) starts the non-root Uvicorn service. [api/main.py](../../api/main.py) registers identity, first-party chat/history/voice, MCP and Operly bridge routers. Its lifespan owns service state, including gated runtime and MCP manager initialization. [provider_gateway.py](../../api/provider_gateway.py) handles provider transport; the gateway is not a client-side agent.
- [worker.py](../../api/agent_platform/worker.py) is a separate Hatchet process. It checks enablement and worker approval, registers ping and bounded job tasks, plus conditional monitor, Personal wake, execution graph, native canary, goal controller and Operly dispatch tasks. Import/registration does not create a user schedule.
- [src/dragonzpyder](../../src/dragonzpyder/) is a thin packaged CLI/client, not the FastAPI harness. The root pyproject registers its CLI. No Android source tree appears in this baseline; do not assume its implementation is here.

## 2. Personal chat, from request to result

```text
React page / compatibility controller (web/app.js)
  -> web/main.py native API proxy
  -> api/main.py registered first-party router
  -> first_party_chat.py: chat / chat_stream
  -> _owner + conversation checks + _chat_owned request ledger path
  -> _execute_chat: model_client, personal_thread, managed_catalog_tools (if selected)
  -> harness.build_frontier_agent + LangGraph checkpointer
  -> _invoke_cancellable / _stream_agent -> result / receipts
```

Start at [first_party_chat.py](../../api/agent_platform/first_party_chat.py): `ChatInput`, `_owner`, `_require_conversation`, `_fingerprint`, `_chat_owned`, `_execute_chat`, `_invoke_cancellable`, `_stream_agent`. Exposed route decorators cover status/session, goals, conversation messages, request status/cancel, chat and chat/stream. Ledger enablement and checkpoint availability are distinct gates. [request ledger migration](../../api/agent_platform/migrations/20261125_first_party_request_ledger.sql) and [ledger tests](../../api/tests/test_first_party_request_ledger.py) are the next stops. [personal_history_http.py](../../api/agent_platform/personal_history_http.py) is the separate history surface; inspect it for archived history changes. Do not route new Personal work through legacy Operly authentication merely because compatibility paths remain.

## 3. Shared intelligence and tools

[harness.py](../../api/agent_platform/harness.py) defines `specialist_specs` and `build_frontier_agent`, Deep Agents virtual filesystem tools, supervisor/specialist instructions and limits. [runtime.py](../../api/agent_platform/runtime.py) defines `model_client`, `build_agent`, `thread_key`, `AgentRuntime`, and result/termination summaries. Check actual caller and tool bindings: there is also a service-only experimental [router.py](../../api/agent_platform/router.py), not a public user endpoint. The virtual filesystem is not an executable computer or durable artifact service. [computer.py](../../api/agent_platform/computer.py) contains the signed runner transport, not a general agent tool. [local_tools.py](../../api/agent_platform/local_tools.py) observes limited worker resources, not a user's laptop.

Relevant cross-cutting implementation candidates: [progress_guard.py](../../api/agent_platform/progress_guard.py), [artifact_evidence.py](../../api/agent_platform/artifact_evidence.py), [scientific_oracles.py](../../api/agent_platform/scientific_oracles.py), [delegation_trace.py](../../api/agent_platform/delegation_trace.py), [orchestration.py](../../api/agent_platform/orchestration.py), [evaluation.py](../../api/agent_platform/evaluation.py). These links are navigation, not proof each is bound to every product route. Inspect [harness tests](../../api/tests/test_harness_product_surface.py) and [tool acceptance](../../api/tests/test_harness_tool_acceptance.py) before changing the interface.

## 4. MCP lifecycle and execution

```text
Authenticated browser/native connection UI
  -> mcp_connection_http.py -> mcp_connections.OAuthConnectionManager
  -> operator-reviewed provider metadata + encrypted credentials
  -> selected user connection / managed_catalog_tools
  -> mcp_broker: McpGrant / CatalogGrant / McpRunCatalog
  -> discover_granted_mcp_tools -> validate_arguments -> invoke_granted_mcp_tool
  -> ToolReceipt / ToolOutcome
```

[mcp_connection_http.py](../../api/agent_platform/mcp_connection_http.py) exposes providers, connection start, native start/complete, callback, connected/list and disconnect. [mcp_connections.py](../../api/agent_platform/mcp_connections.py) handles reviewed providers, OAuth metadata, credential encryption and connection lifecycle. [mcp_broker.py](../../api/agent_platform/mcp_broker.py) owns grant-scoped tool schemas and invocation, including `catalog_tools`. [capability_hub.py](../../api/agent_platform/capability_hub.py) holds per-run bindings; do not cache expiring authority across users. See [mcp_managed_catalog.py](../../api/agent_platform/mcp_managed_catalog.py), [mcp_adapter.py](../../api/agent_platform/mcp_adapter.py), [connection migration](../../api/agent_platform/migrations/20261122_mcp_connections.sql), [native OAuth migration](../../api/agent_platform/migrations/20261125_native_mcp_oauth.sql), [broker tests](../../api/tests/test_mcp_broker.py), [Postgres connection tests](../../api/tests/test_mcp_connections_postgres.py). Do not let models choose credentials or arbitrary endpoint URLs. Native OAuth, provider grants, tool authorization and user approval are distinct concerns.

## 5. Persistent objectives

[worker.py](../../api/agent_platform/worker.py) registers Hatchet task factories in [jobs.py](../../api/agent_platform/jobs.py), [personal_wake.py](../../api/agent_platform/personal_wake.py) and [persistent_graph.py](../../api/agent_platform/persistent_graph.py), among others. [personal_goal_tools.py](../../api/agent_platform/personal_goal_tools.py) binds trusted owner/session/conversation to short read-only native goal tools. In personal_wake, start with `perform_personal_wake`, `execute_personal_goal_plan`, `make_personal_goal_controller_task`; wake authority is renewed for the original session and capability. In persistent_graph, start with `GraphStep`, `validate_plan`, `execute_graph_wake`, `_renew`, `_compose`, `_verify`. This is a typed resumable read-only path, not generalized arbitrary mutation or sandbox execution. Compare [goal receipts schema](../../api/agent_platform/migrations/20261121_personal_goal_receipts.sql), [graph tests](../../api/tests/test_persistent_graph.py), [Postgres graph tests](../../api/tests/test_persistent_graph_postgres.py), [wake tests](../../api/tests/test_personal_mcp_wake.py). For Operly dispatch inspect [operly_workflow_dispatch.py](../../api/agent_platform/operly_workflow_dispatch.py) separately; business authority remains Operly's.

## 6. Identity and Operly separation

[api/identity/](../../api/identity/README.md) is the implementation area; [identity/contracts](../../identity/contracts/) is the contract area. [router.py](../../api/identity/router.py) supplies discovery/JWKS; [browser_authorize.py](../../api/identity/browser_authorize.py) supplies browser UI; [http_bridge.py](../../api/identity/http_bridge.py) owns authorize/token endpoints and DB access helpers; [grants.py](../../api/identity/grants.py) handles registered clients and code/PKCE redemption. [login_http.py](../../api/identity/login_http.py) provides password/profile/logout routes; [sessions.py](../../api/identity/sessions.py) creates, resolves and revokes opaque sessions. [mobile_provider.py](../../api/identity/mobile_provider.py) exposes provider start/callback/redeem and capabilities; [native_signup.py](../../api/identity/native_signup.py) handles explicit verified Google signup. Inspect [provider_http.py](../../api/identity/provider_http.py), recovery and import modules for their separate proof boundaries. Historic module docstrings can lag subsequent route integrations; use current router registration and implementation, not old statements about rollout.

[personal_bridge.py](../../api/agent_platform/personal_bridge.py) and [workspace_bridge.py](../../api/agent_platform/workspace_bridge.py) are private signed Operly bridges, not the first-party Personal login API. Their thread keys and delegated capability scopes are distinct. Personal identity does not grant workspace membership. Tests: [OAuth grants](../../api/tests/test_identity_oauth_grants.py), [native mobile](../../api/tests/test_identity_mobile_provider.py), [session](../../api/tests/test_identity_browser_sessions.py), [workspace bridge](../../api/tests/test_workspace_bridge.py).

## 7. Provider accounting, voice and rollout

Start model request changes at [api/main.py](../../api/main.py) and [provider_gateway.py](../../api/provider_gateway.py). Related paths include [usage_ledger.py](../../api/usage_ledger.py), [budget_reservations.py](../../api/agent_platform/budget_reservations.py), [gateway_parent_budget.py](../../api/agent_platform/gateway_parent_budget.py), [provider_pacing.py](../../api/agent_platform/provider_pacing.py), [model_capabilities.py](../../api/agent_platform/model_capabilities.py), [observability.py](../../api/observability.py). Inspect the specific enforcement path, not just a similarly named helper. Never interpret unknown charges as free or expose provider secrets.

[first_party_voice.py](../../api/agent_platform/first_party_voice.py) starts/ends opt-in audio-only WebRTC sessions, reserves starts and cleans expired sessions. It does not grant agent tools. Inspect [web/backend/voice.py](../../web/backend/voice.py), [VoiceOrb.jsx](../../web/frontend/src/VoiceOrb.jsx), [voice-canvas-renderer.js](../../web/frontend/src/voice-canvas-renderer.js) and [voice tests](../../api/tests/test_first_party_voice.py) for interface-specific changes. The target of voice sharing the same agent harness is not evidence it is already connected.

Deployment truth is independent: inspect [workflows](../../.github/workflows/), service Dockerfiles, Railway deployed commit and feature gates, then relevant acceptance evidence. Keep earlier Node implementations and staged paths distinct from current FastAPI/React entrypoints. Do not remove compatibility code just because a newer path exists.


## Additional reviewed modules and generated index

The file inventory now records source-inspected cross-cutting modules for artifact readback, budget reservations, provider pacing, MCP trust and authorization, memory, persistent monitoring, archive migration, and delegation. Read the named module and tests for the exact boundary; historical rollout wording in source docstrings may be stale.

The checkout-specific generated directory contains an index, a page for every tracked file, folder indexes, and a flat symbol map. Static references and related tests are candidates, not exhaustive dynamic dependencies. Use human-maintained change records and curated summaries to explain actual behavior.

## Frontend V2 foundation

`web/frontend/src/dz-mark.svg` is the local brand master. `web/frontend/scripts/prepare-desktop.mjs` produces web/installation rasters; `android/prepare-brand.sh` produces the native vector. The Personal React shell uses `UiIcon.jsx` and V2 semantic shell tokens in `web/ui-v1.css`. The existing `web/app.js` adapter requests authenticated `/dz/identity/v1/me` for optional display name metadata and never uses it to grant authorization. Native chat capability remains backend-owned; unavailable chat retains drafts and disables send. No provider avatar claim, runtime flag changes or deployment implied.

## Integrated V4 candidate paths

Native chat uses the shared adaptive router and the canonical Deep Agents graph. Selected MCP reads may be bound directly or through bounded QuickJS. Selected artifacts pass through owner-bound encrypted storage and the signed scoped VM runner. Reviewed media operations pass through the capped provider gateway. Native voice transcripts enter the chat ledger; spoken playback remains separate. Native durable objectives are finite dependent phases dispatched by Hatchet with checkpoint/receipt fencing, original authority and shared model budget. All rollout gates remain off unless separately authorized. Tests use scripted providers; production validation remains outstanding.

### Browser sign-in correction

Once `/dz/status` establishes routing, signed-out `/app` goes directly to `/login` for native identity or `/account` for explicitly legacy access. Failed probes show a retry dialog, not a second credential form. `web/account.js` retains verified provider, password, migration and recovery flows; the legacy sign-in link requires explicit routing eligibility. Voice and server authorization remain unchanged.

## Modular streaming voice

The optional modular route uses LiveKit WebRTC, Deepgram Flux STT and Aura streaming TTS, with no separate reasoning model. The canonical chat ledger and owner-scoped harness execute completed transcripts; original session authority is checked repeatedly. The browser prefers modular when the operator flag is enabled. Existing realtime transport remains independently gated. The worker uses a dedicated internal service credential and room nonce, not user cookies. Configure LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET and DRAGONZPYDER_VOICE_WORKER_TOKEN; worker additionally needs DEEPGRAM_API_KEY and DRAGONZPYDER_VOICE_API_ORIGIN. Apply the modular voice session migration after the native voice migration before enabling DRAGONZPYDER_MODULAR_VOICE_ENABLED. The duration/session quotas are admission bounds, not a verified provider-dollar ceiling. No live call, production migration or deployment has been performed. Full confirmed answer playback is streamed by TTS, but agent generation is not yet streamed into TTS; interruption does not replay an accepted task. Android modular transport and latency benchmarks remain pending.

## OpenRouter-only voice (preferred gated transport)

The browser uses local AudioWorklet energy-based utterance detection, OpenRouter Whisper Large V3 Turbo STT, the canonical authenticated chat graph, and Kokoro 82M / af_alloy MP3 playback. No LiveKit service, Deepgram account, or extra paid subscription is required for this path. The same OpenRouter account can supply the existing DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY; the verified non-resetting cap (at most $0.50 for the initial rollout) and persistent usage ledger remain mandatory. Configure DRAGONZPYDER_OPENROUTER_VOICE_ENABLED only after applying the native voice, modular voice and OpenRouter voice SQL migrations, enabling the native chat request ledger, and verifying provider key and budget. Optional LiveKit and native realtime adapters remain separately gated. Speech is request-based per detected utterance and per committed answer segment, not continuous streaming STT or token-to-audio. Barge-in stops playback, but an accepted request is not automatically replayed or replaced. Voice sessions are limited to five minutes and twenty turns, four speech segments maximum per response. Long responses remain in chat. Native Android and measured live latency remain unqualified. No deployment, migration or paid calls performed.

## Transport-neutral voice session contract v1

All supported clients use the same backend: authenticated session creation at POST /v2/personal/voice/sessions; POST /v2/personal/voice/sessions/{session_id}/turn with event_id, base64 audio, format and explicit sample_rate/channels when using raw PCM; POST /v2/personal/voice/sessions/{session_id}/speech/{event_id}/{index} returns the committed answer segment as MP3; POST /v2/personal/voice/sessions/{session_id}/end revokes session authority. Existing provider-specific paths remain compatibility aliases. Browser and native Android/iOS clients use existing DragonZpyder session and CSRF authentication. An authenticated user may explicitly create a short-lived, session-only external bridge grant with source=discord, telephony or external and delegate=true. Return the grant once; pass it as Authorization: Bearer <grant> only to that session's endpoints. Store only a digest; validate original account/session authority on each call. No account mapping from untrusted channel IDs, no login cookie sharing, no arbitrary tool or model authority. The bridge integration must obtain user authorization and protect the token. The backend accepts canonical mono 16 kHz WAV, PCM signed little-endian 16-bit mono/stereo at 8/16/24/48 kHz, and mono G.711 mu-law/A-law at 8 kHz; converts to mono 16 kHz WAV before the same metered OpenRouter STT/harness/TTS path. Each utterance is 0.15–30 seconds. Opus/RTP/WebSocket packet framing, jitter buffering, per-speaker segmentation, consent and output re-encoding belong in transport adapters. These adapters are not implemented by this change. MP3 is the common egress; voice bridges decode/resample for their own transport. Session lifetime and quotas are unchanged. No deployment or paid testing performed.


### Production voice readiness (current policy)

Production reuses `OPENROUTER_API_KEY`; no new voice feature variable or dedicated credential is needed. The existing native chat, identity, agent and request-ledger prerequisites remain. The API lifespan probes the existing schema and DML permissions first; only missing voice/ledger schema triggers the four existing additive migrations in one bounded advisory-locked transaction using the configured agent database role. A complete schema is reused without DDL; failure leaves voice unavailable, not text chat. Voice is advertised only after schema readback and usage-ledger readiness. Each production STT/TTS request consumes an atomic shared hourly call allowance in PostgreSQL, in addition to existing duration/turn/session limits and accounting. This is a call-count budget, **not** a provider-enforced $0.50 dollar cap. The nonproduction opt-in path retains its capped test key and cap preflight. Existing explicit voice value `0` remains an emergency rollback, not a required activation setting. No role grants, identity changes, or paid test calls are included. CI and production verification pending.

### Voice failure handling

OpenRouter voice distinguishes unsubmitted transcription failure, unconfirmed canonical execution and committed answer with failed playback. The browser pauses utterance admission during agent execution/playback and after uncertain failure, preserves chat results and never automatically replays a paid turn. Speaker mute controls the Web Audio gain; original orb rendering remains unchanged. Automatic barge-in is temporarily disabled to avoid echo-triggered requests. Sanitized server phase/status logs support production diagnosis without logging audio, transcripts, credentials or provider response bodies.

## Native personal memory

The authenticated first-party memory API stores exact user-entered records in the existing agent PostgreSQL database. The web memory dialog separately asks whether a saved record may be recalled in future personal chats. Only consented records are searched by the supervisor's bounded, live-authorized read tool. No model tool can write or delete memory; no Mem0 extraction or additional inference provider is required. Removal affects the memory store, not historical chat content. Schema readiness fails closed independently of ordinary chat.

## Operator console

The existing web/main.py admin_route enforces identity allowlist before admin_operations; native session required for new panels. Fixed read-only provider adapters return bounded deployment, edge request aggregate, GitHub and Langfuse metadata. React admin.jsx loads a selected tab on demand. See OBSERVABILITY.md for credentials and limitations. No new user-data or mutation authority; live validation pending.

Admin product activity: Web native identity check → fixed /internal/admin/activity request using existing independent reporting bearer → bounded read-only native aggregate SELECTs plus configuration signals. No user payload, identity database access or mutation. Usage summary provides UTC daily latency and spend aggregates.

Resource metrics and historical HTTP traffic: admin Web adapters resolve project-scoped service names and request bounded Railway samples; React shows summary, time-series and status/latency tables. Provider retention/availability is explicit. No mutation or user payload.


### Admin account analytics

The native admin activity report reads aggregate account states, native signup counts and unexpired session counts using the existing restricted identity database role in a read-only transaction, excluding operator test identities. Distinct request owners are counted across the selected interval, not by summing daily counts. Sessions are not devices or online presence; device/country/referral data are not provided by these stores. No new grants or credentials. CI and live data verification pending.
