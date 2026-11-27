# api/agent_platform/migrations

SQL migrations for Personal goals/chat, request ledger, MCP and native voice/history. Manual scripts need separate authorization.

Read [repository instructions](../../../AGENTS.md) and [codebase navigation](../../../CODEBASE.md). See the [implementation guide](../../../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../../../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`20261121_personal_goal_receipts.sql`](20261121_personal_goal_receipts.sql) | SQL named for 20261121 personal goal receipts; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261122_first_party_chat.sql`](20261122_first_party_chat.sql) | SQL named for 20261122 first party chat; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261122_mcp_connections.sql`](20261122_mcp_connections.sql) | SQL named for 20261122 mcp connections; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261122_personal_mcp_goal_selections.sql`](20261122_personal_mcp_goal_selections.sql) | SQL named for 20261122 personal mcp goal selections; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_first_party_request_ledger.sql`](20261125_first_party_request_ledger.sql) | SQL named for 20261125 first party request ledger; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_native_mcp_oauth.sql`](20261125_native_mcp_oauth.sql) | SQL named for 20261125 native mcp oauth; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_native_voice.sql`](20261125_native_voice.sql) | SQL named for 20261125 native voice; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_personal_history_archive_manual.sql`](20261125_personal_history_archive_manual.sql) | SQL named for 20261125 personal history archive manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`operly_legacy_history_inventory_manual.sql`](operly_legacy_history_inventory_manual.sql) | SQL named for operly legacy history inventory manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`operly_personal_history_export_role_manual.sql`](operly_personal_history_export_role_manual.sql) | SQL named for operly personal history export role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`operly_personal_history_inventory_manual.sql`](operly_personal_history_inventory_manual.sql) | SQL named for operly personal history inventory manual; inspect statements, transaction requirements and target database before use. | Indexed |

## Integrated harness changes

- [20261125_native_voice.sql](20261125_native_voice.sql): Persist voice mode, selected accounts and conversation reference alongside session expiry.
- [20261125_shared_artifacts.sql](20261125_shared_artifacts.sql): Create encrypted artifact metadata with pending, ready and deletion lifecycle.
- [20261126_agent_media_attempts.sql](20261126_agent_media_attempts.sql): Persist exact media invocation IDs and metered gateway receipts.
- [20261126_computer_admission.sql](20261126_computer_admission.sql): Persist durable VM exposure and cleanup states.
- [20261126_native_workflows.sql](20261126_native_workflows.sql): Store immutable finite workflow plan, authority reference, phase cursor and receipts.

## OpenRouter-only voice (preferred gated transport)

The browser uses local AudioWorklet energy-based utterance detection, OpenRouter Whisper Large V3 Turbo STT, the canonical authenticated chat graph, and Kokoro 82M / af_alloy MP3 playback. No LiveKit service, Deepgram account, or extra paid subscription is required for this path. The same OpenRouter account can supply the existing DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY; the verified non-resetting cap (at most $0.50 for the initial rollout) and persistent usage ledger remain mandatory. Configure DRAGONZPYDER_OPENROUTER_VOICE_ENABLED only after applying the native voice, modular voice and OpenRouter voice SQL migrations, enabling the native chat request ledger, and verifying provider key and budget. Optional LiveKit and native realtime adapters remain separately gated. Speech is request-based per detected utterance and per committed answer segment, not continuous streaming STT or token-to-audio. Barge-in stops playback, but an accepted request is not automatically replayed or replaced. Voice sessions are limited to five minutes and twenty turns, four speech segments maximum per response. Long responses remain in chat. Native Android and measured live latency remain unqualified. No deployment, migration or paid calls performed.

## Transport-neutral voice session contract v1

All supported clients use the same backend: authenticated session creation at POST /v2/personal/voice/sessions; POST /v2/personal/voice/sessions/{session_id}/turn with event_id, base64 audio, format and explicit sample_rate/channels when using raw PCM; POST /v2/personal/voice/sessions/{session_id}/speech/{event_id}/{index} returns the committed answer segment as MP3; POST /v2/personal/voice/sessions/{session_id}/end revokes session authority. Existing provider-specific paths remain compatibility aliases. Browser and native Android/iOS clients use existing DragonZpyder session and CSRF authentication. An authenticated user may explicitly create a short-lived, session-only external bridge grant with source=discord, telephony or external and delegate=true. Return the grant once; pass it as Authorization: Bearer <grant> only to that session's endpoints. Store only a digest; validate original account/session authority on each call. No account mapping from untrusted channel IDs, no login cookie sharing, no arbitrary tool or model authority. The bridge integration must obtain user authorization and protect the token. The backend accepts canonical mono 16 kHz WAV, PCM signed little-endian 16-bit mono/stereo at 8/16/24/48 kHz, and mono G.711 mu-law/A-law at 8 kHz; converts to mono 16 kHz WAV before the same metered OpenRouter STT/harness/TTS path. Each utterance is 0.15–30 seconds. Opus/RTP/WebSocket packet framing, jitter buffering, per-speaker segmentation, consent and output re-encoding belong in transport adapters. These adapters are not implemented by this change. MP3 is the common egress; voice bridges decode/resample for their own transport. Session lifetime and quotas are unchanged. No deployment or paid testing performed.


### Production voice readiness (current policy)

Production reuses `OPENROUTER_API_KEY`; no new voice feature variable or dedicated credential is needed. The existing native chat, identity, agent and request-ledger prerequisites remain. The API lifespan attempts the four existing additive voice/ledger SQL migrations in one bounded advisory-locked transaction using the configured agent database role; failure leaves voice unavailable, not text chat. Voice is advertised only after schema readback and usage-ledger readiness. Each production STT/TTS request consumes an atomic shared hourly call allowance in PostgreSQL, in addition to existing duration/turn/session limits and accounting. This is a call-count budget, **not** a provider-enforced $0.50 dollar cap. The nonproduction opt-in path retains its capped test key and cap preflight. Existing explicit voice value `0` remains an emergency rollback, not a required activation setting. No role grants, identity changes, or paid test calls are included. CI and production verification pending.
