# web/frontend/src

React source, UI components, runtime context, markdown and voice renderer.

Read [repository instructions](../../../AGENTS.md) and [codebase navigation](../../../CODEBASE.md). See the [implementation guide](../../../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../../../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`AccountTemplate.jsx`](AccountTemplate.jsx) | Navigation hint: AccountTemplate; source behavior not independently reviewed. | Indexed |
| [`HomeTemplate.jsx`](HomeTemplate.jsx) | Navigation hint: HomeTemplate; source behavior not independently reviewed. | Indexed |
| [`NativeMcpCenter.jsx`](NativeMcpCenter.jsx) | React first-party OAuth MCP connection UI; CSRF-protected requests and opaque selected aliases, never bearer credentials. | Reviewed |
| [`PersonalTemplate.jsx`](PersonalTemplate.jsx) | Navigation hint: PersonalTemplate; source behavior not independently reviewed. | Indexed |
| [`VoiceOrb.jsx`](VoiceOrb.jsx) | React-owned voice interface/lifecycle and artwork renderer integration; visual canvas does not request microphone itself. | Reviewed |
| [`WorkspaceCenter.jsx`](WorkspaceCenter.jsx) | React account-scoped workspace center and same-origin API requests; includes native MCP UI. | Reviewed |
| [`WorkspaceControls.jsx`](WorkspaceControls.jsx) | Accessible modal focus and progressive-disclosure chat controls, command palette, capture/add menus and desktop install; delegates to existing adapters. | Reviewed |
| [`admin.css`](admin.css) | Responsive operations navigation, tables, metrics and distribution bars. | Indexed |
| [`admin.jsx`](admin.jsx) | Read-only operations console: usage, Railway deployments, bounded traffic sample, GitHub and redacted Langfuse observations. | Indexed |
| [`main.jsx`](main.jsx) | React mount/hydrate entrypoint selecting page by route. | Reviewed |
| [`markdown.js`](markdown.js) | Navigation hint: markdown; source behavior not independently reviewed. | Indexed |
| [`pages.jsx`](pages.jsx) | React page selection and compatibility-adapter orchestration. | Reviewed |
| [`runtime.jsx`](runtime.jsx) | Navigation hint: runtime; source behavior not independently reviewed. | Indexed |
| [`voice-canvas-renderer.js`](voice-canvas-renderer.js) | Navigation hint: voice canvas renderer; source behavior not independently reviewed. | Indexed |
| [`voice-orb.css`](voice-orb.css) | Stylesheet: voice orb; inspect selectors and importing page. | Indexed |
| [`workspace-center.css`](workspace-center.css) | Stylesheet: workspace center; inspect selectors and importing page. | Indexed |

## V2 foundation

- `dz-mark.svg`: canonical monogram consumed by the desktop asset build and Android resource generation.
- `UiIcon.jsx`: outline icon geometry, used by the Personal shell and workspace controls.
- `PersonalTemplate.jsx`: compact shell; preserves controller IDs. `web/app.js` still owns identity and chat capability presentation.

`NativeGoals.jsx` renders first-party goal list, wake counts, receipts and explicit cancellation through the existing owner-scoped API. `NativeMcpCenter.jsx` provides the native connections/goals navigation; no legacy execution fallback.

V2 shared tokens live in `design-tokens.css`; `ui-preferences.js` defines a versioned allowlisted browser-local presentation contract and `AppearanceSettings.jsx` is its user-facing editor. Account synchronization and agent-mediated updates require a separate authenticated API, preview/approval and rollback contract.

The chat no longer owns a duplicate credential form. `web/app.js` redirects known signed-out sessions to the canonical account entrypoint and shows a retry state for connection failures. `AccountTemplate.jsx` uses compact utility layouts; the sidebar prioritizes chat and capability navigation.

## Modular streaming voice

The optional modular route uses LiveKit WebRTC, Deepgram Flux STT and Aura streaming TTS, with no separate reasoning model. The canonical chat ledger and owner-scoped harness execute completed transcripts; original session authority is checked repeatedly. The browser prefers modular when the operator flag is enabled. Existing realtime transport remains independently gated. The worker uses a dedicated internal service credential and room nonce, not user cookies. Configure LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET and DRAGONZPYDER_VOICE_WORKER_TOKEN; worker additionally needs DEEPGRAM_API_KEY and DRAGONZPYDER_VOICE_API_ORIGIN. Apply the modular voice session migration after the native voice migration before enabling DRAGONZPYDER_MODULAR_VOICE_ENABLED. The duration/session quotas are admission bounds, not a verified provider-dollar ceiling. No live call, production migration or deployment has been performed. Full confirmed answer playback is streamed by TTS, but agent generation is not yet streamed into TTS; interruption does not replay an accepted task. Android modular transport and latency benchmarks remain pending.

## OpenRouter-only voice (preferred gated transport)

The browser uses local AudioWorklet energy-based utterance detection, OpenRouter Whisper Large V3 Turbo STT, the canonical authenticated chat graph, and Kokoro 82M / af_alloy MP3 playback. No LiveKit service, Deepgram account, or extra paid subscription is required for this path. The same OpenRouter account can supply the existing DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY; the verified non-resetting cap (at most $0.50 for the initial rollout) and persistent usage ledger remain mandatory. Configure DRAGONZPYDER_OPENROUTER_VOICE_ENABLED only after applying the native voice, modular voice and OpenRouter voice SQL migrations, enabling the native chat request ledger, and verifying provider key and budget. Optional LiveKit and native realtime adapters remain separately gated. Speech is request-based per detected utterance and per committed answer segment, not continuous streaming STT or token-to-audio. Barge-in stops playback, but an accepted request is not automatically replayed or replaced. Voice sessions are limited to five minutes and twenty turns, four speech segments maximum per response. Long responses remain in chat. Native Android and measured live latency remain unqualified. No deployment, migration or paid calls performed.

## Transport-neutral voice session contract v1

All supported clients use the same backend: authenticated session creation at POST /v2/personal/voice/sessions; POST /v2/personal/voice/sessions/{session_id}/turn with event_id, base64 audio, format and explicit sample_rate/channels when using raw PCM; POST /v2/personal/voice/sessions/{session_id}/speech/{event_id}/{index} returns the committed answer segment as MP3; POST /v2/personal/voice/sessions/{session_id}/end revokes session authority. Existing provider-specific paths remain compatibility aliases. Browser and native Android/iOS clients use existing DragonZpyder session and CSRF authentication. An authenticated user may explicitly create a short-lived, session-only external bridge grant with source=discord, telephony or external and delegate=true. Return the grant once; pass it as Authorization: Bearer <grant> only to that session's endpoints. Store only a digest; validate original account/session authority on each call. No account mapping from untrusted channel IDs, no login cookie sharing, no arbitrary tool or model authority. The bridge integration must obtain user authorization and protect the token. The backend accepts canonical mono 16 kHz WAV, PCM signed little-endian 16-bit mono/stereo at 8/16/24/48 kHz, and mono G.711 mu-law/A-law at 8 kHz; converts to mono 16 kHz WAV before the same metered OpenRouter STT/harness/TTS path. Each utterance is 0.15–30 seconds. Opus/RTP/WebSocket packet framing, jitter buffering, per-speaker segmentation, consent and output re-encoding belong in transport adapters. These adapters are not implemented by this change. MP3 is the common egress; voice bridges decode/resample for their own transport. Session lifetime and quotas are unchanged. No deployment or paid testing performed.

Admin console also renders internal native product/harness aggregates, daily inference usage and trace filtering/pagination; production verification pending.

Resources and Traffic history sections use bounded fixed provider queries, time-series SVG charts and table readbacks; external schema/credentials and live production verification pending.
