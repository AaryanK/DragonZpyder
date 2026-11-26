# web/frontend/scripts

Frontend build validation, prerender and desktop/markdown checks.

Read [repository instructions](../../../AGENTS.md) and [codebase navigation](../../../CODEBASE.md). See the [implementation guide](../../../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../../../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`check-build.mjs`](check-build.mjs) | Navigation hint: check build; source behavior not independently reviewed. | Indexed |
| [`prepare-desktop.mjs`](prepare-desktop.mjs) | Navigation hint: prepare desktop; source behavior not independently reviewed. | Indexed |
| [`prerender.mjs`](prerender.mjs) | Navigation hint: prerender; source behavior not independently reviewed. | Indexed |
| [`test-desktop.mjs`](test-desktop.mjs) | Navigation hint: test desktop; source behavior not independently reviewed. | Indexed |
| [`test-markdown.mjs`](test-markdown.mjs) | Navigation hint: test markdown; source behavior not independently reviewed. | Indexed |

`prepare-desktop.mjs` generates DragonZpyder brand sizes from `../src/dz-mark.svg`; only the unrelated Operly brand remains a pinned network fetch. `test-desktop.mjs` verifies asset structure and manifest compatibility.

## OpenRouter-only voice (preferred gated transport)

The browser uses local AudioWorklet energy-based utterance detection, OpenRouter Whisper Large V3 Turbo STT, the canonical authenticated chat graph, and Kokoro 82M / af_alloy MP3 playback. No LiveKit service, Deepgram account, or extra paid subscription is required for this path. The same OpenRouter account can supply the existing DRAGONZPYDER_AGENT_MEDIA_OPENROUTER_API_KEY; the verified non-resetting cap (at most $0.50 for the initial rollout) and persistent usage ledger remain mandatory. Configure DRAGONZPYDER_OPENROUTER_VOICE_ENABLED only after applying the native voice, modular voice and OpenRouter voice SQL migrations, enabling the native chat request ledger, and verifying provider key and budget. Optional LiveKit and native realtime adapters remain separately gated. Speech is request-based per detected utterance and per committed answer segment, not continuous streaming STT or token-to-audio. Barge-in stops playback, but an accepted request is not automatically replayed or replaced. Voice sessions are limited to five minutes and twenty turns, four speech segments maximum per response. Long responses remain in chat. Native Android and measured live latency remain unqualified. No deployment, migration or paid calls performed.
