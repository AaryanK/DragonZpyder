# Codebase change records

For each implementation change, add a new bullet beginning with the exact repository-relative path in backticks, followed by a colon and a substantive explanation. Include changed behavior or why behavior is unchanged, affected callers/dependencies, constraints, tests/evidence and unresolved limitations. Record both paths for a rename; describe removals. Do not edit old entries to make a new change appear covered. Update file inventory, local guides and execution flows alongside this record. Documentation-only edits need no records.

## 2026-11-26 — documentation infrastructure

- `scripts/build_codebase_index.py`: Generates source-derived file and directory pages and flat navigation, extracts symbols, docstrings, parameters, call candidates, imports, routes and candidate references; includes curated purpose rows; no application execution. Initial generator and gate passed the codebase documentation CI; expanded coverage checks require their own run.
- `scripts/check_codebase_docs.py`: Compares base and head; requires a new record naming every changed non-documentation path, including both old/new paths on rename; checks exact tracked inventory and folder guides. Structural check, not semantic certification.
- `tests/test_codebase_documentation.py`: Offline temporary-repository fixtures for extraction, reference hints, generated pages and change-record validation.
- `.github/workflows/codebase-docs.yml`: Read-only CI builds/uploads the index and checks path-specific records on PRs; no deployment or automatic branch writes.

## 2026-11-26 — Frontend V2 foundation

- `web/frontend/src/dz-mark.svg`: Canonical flat DZ geometric monogram; two closed paths, even-odd D counter, transparent background, 64-unit viewBox; read by web and Android build scripts. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/frontend/src/UiIcon.jsx`: Presentation-only 24-unit vector icon component; accessible names belong to controls; used by PersonalTemplate and WorkspaceControls. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/frontend/src/PersonalTemplate.jsx`: React Personal shell: vector controls, one connections entry, mobile new chat, account appearance and unavailable-runtime notice; preserves existing adapter IDs and authorization. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/frontend/src/WorkspaceControls.jsx`: Uses outline vector sidebar and add-menu controls; existing modal focus and permissions remain. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/app.js`: Loads authenticated first-party display name via /me with stale-response guard, derives initials, exposes disabled-chat state while preserving drafts and existing native guard; no provider-image support yet. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/ui-v1.css`: V2 semantic shell color tokens, compact responsive layout, theme-specific icons and composer clearance; legacy secondary surfaces not yet migrated. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/frontend/scripts/prepare-desktop.mjs`: Reads local SVG master and generates transparent favicon/logo rasters plus opaque PWA icons; Operly asset remains pinned and hash-verified. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/frontend/scripts/test-desktop.mjs`: Checks generated monogram vector, transparent favicon sizes and opaque installation icons; maintains manifest and pinned Operly checks. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/main.py`: Adds exact SVG and favicon allowlist routes and SVG media type; no arbitrary static directory exposure. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/frontend/tests/ui.spec.js`: Adds compact mobile dark/light layout, deduplicated navigation, composer clearance and profile menu checks. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/frontend/tests/native-routing.spec.js`: Adds native identity initials and unavailable-chat submission regression with mock routes. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `android/prepare-brand.sh`: Generates native Android VectorDrawable from canonical web SVG using Python stdlib; removes stale generated PNG, retains resource identifier. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `android/.gitignore`: Excludes generated Android vector asset, keeping SVG as versioned source. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/frontend/index.html`: Advertises canonical SVG and explicit 16/32 px favicon fallbacks; existing route and metadata retained. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/frontend/app.html`: Advertises canonical SVG and explicit 16/32 px favicon fallbacks; existing route and metadata retained. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.
- `web/frontend/account.html`: Advertises canonical SVG and explicit 16/32 px favicon fallbacks; existing route and metadata retained. Source inspection and regression coverage added where applicable; full CI, device and production checks pending.

## 2026-11-26 — V2 regression and history-state corrections

- `web/ui-v1.css`: Restores the connections/navigation rows hidden by UI1 light-theme CSS; compact sidebar controls in both themes. Previous Chromium native-routing test failed on the hidden button; rerun pending.
- `scripts/check_codebase_docs.py`: Android AAPT resource directories use their parent res guide; every file still requires exact inventory coverage. Narrow exception avoids invalid Markdown resource files.
- `tests/test_codebase_documentation.py`: Fixture verifies resource parent guide requirement and normal directory coverage.
- `web/app.js`: Distinguishes unavailable/loading/failed history from genuinely empty history, rejects stale session list responses; does not bypass backend feature gates or use Operly fallback.
- `web/frontend/tests/native-routing.spec.js`: Asserts unavailable history is not mislabeled as empty when chat capability is gated. Existing native authorization fixture retained.

Removed the three Markdown guides from Android drawable, values and xml resource folders because AAPT rejects them; their parent guide now documents the resource paths.

## 2026-11-26 — V2 native tasks and capability center

- `web/frontend/src/NativeGoals.jsx`: First-party goal list/detail/receipts and explicitly confirmed cancellation using owner-scoped native routes and CSRF; progress counts are service-reported, no guessed titles or scheduler creation. CI and live qualification pending.
- `web/frontend/src/NativeMcpCenter.jsx`: Native capability center switches between connections and first-party goals, focus containment and honest loading/empty states; retains authorized MCP aliases. CI and live qualification pending.
- `web/frontend/src/WorkspaceCenter.jsx`: Uses shared outline icons and delegates focus ownership to native center in first-party mode. CI and live qualification pending.
- `web/frontend/src/WorkspaceControls.jsx`: Adds Tasks and goals command and accurate workflow navigation copy. CI and live qualification pending.
- `web/frontend/src/UiIcon.jsx`: Adds tasks and tool vector geometry. CI and live qualification pending.
- `web/frontend/src/PersonalTemplate.jsx`: Direct Personal tasks navigation opens capability center. CI and live qualification pending.
- `web/frontend/src/workspace-center.css`: Semantic V2 surface/text/accent palette and responsive controls across native/legacy capability centers. CI and live qualification pending.
- `web/account.js`: Broadcasts resolved native routing mode to React capability center before profile use, avoiding obsolete Operly connector routes for native accounts. CI and live qualification pending.
- `web/frontend/tests/native-routing.spec.js`: Mock goal readback checks real wake counts, receipts, cancellation confirmation and absence of legacy requests. CI and live qualification pending.

## 2026-11-26 — V2 shared design and appearance configuration

- `web/frontend/src/ui-preferences.js`: Versioned, allowlisted browser-local theme, density, text size and reduced motion configuration; rejects arbitrary CSS and authority fields, preserves existing theme key. CI and production qualification pending.
- `web/frontend/src/AppearanceSettings.jsx`: Account appearance controls apply validated local preferences immediately and expose storage failures; no account or agent permission mutation. CI and production qualification pending.
- `web/frontend/src/design-tokens.css`: Shared neutral/accent semantic tokens and bounded motion override, imported by Personal, account and admin entrypoints. CI and production qualification pending.
- `web/frontend/src/pages.jsx`: Applies validated browser preferences before compatibility controllers; imports shared design tokens. CI and production qualification pending.
- `web/frontend/src/AccountTemplate.jsx`: Adds Appearance section and shared outline account icons; retains login/profile controller IDs and clarifies ownership. CI and production qualification pending.
- `web/frontend/src/admin.jsx`: Uses shared logo and design tokens while retaining protected admin API. CI and production qualification pending.
- `web/frontend/src/admin.css`: Applies shared semantic palette and accessible mobile controls. CI and production qualification pending.
- `web/account.css`: Responsive V2 identity/account UI and appearance settings using the shared palette; preserves auth forms. CI and production qualification pending.
- `web/ui-v1.css`: Moves palette definitions to shared design-token module and applies bounded chat density/text-size settings. CI and production qualification pending.
- `web/frontend/tests/ui.spec.js`: Regression verifies validated presentation settings after reload without arbitrary styling injection. CI and production qualification pending.
- `web/frontend/account.html`: Declares consistent default light appearance for server prerender before browser preferences load. CI and production qualification pending.

## 2026-11-26 — optional native profile avatar contract

- `api/identity/profile_avatar.py`: Optional Google picture URL validation, verified-provider/owner-scoped storage and bounded same-origin image readback; no arbitrary URLs, redirects or user credentials sent upstream. Offline regression coverage added; production migration and qualification pending.
- `api/identity/schema_google_avatar_manual.sql`: Operator-only nullable profile picture column and column-level update grant; no account activation or provider authority changes. Offline regression coverage added; production migration and qualification pending.
- `api/identity/providers.py`: Captures only allowlisted Google picture claim after signed ID token validation. Offline regression coverage added; production migration and qualification pending.
- `api/identity/provider_http.py`: Refreshes optional avatar only after verified provider resolves an active account; gate off by default. Offline regression coverage added; production migration and qualification pending.
- `api/identity/mobile_provider.py`: Refreshes optional avatar after verified provider account resolution; does not change ticket or session authority. Offline regression coverage added; production migration and qualification pending.
- `api/identity/login_http.py`: Advertises avatar availability and authenticated owner-only image endpoint with private no-store policy. Offline regression coverage added; production migration and qualification pending.
- `web/main.py`: Exact allowlist entry for native avatar endpoint; no new general proxy. Offline regression coverage added; production migration and qualification pending.
- `api/tests/test_identity_providers.py`: Verifies trusted picture claim is retained and untrusted claims rejected. Offline regression coverage added; production migration and qualification pending.
- `api/tests/test_identity_profile_avatar.py`: Offline tests for exact URL allowlist, no redirects, MIME/signature/byte bounds, flag and owner-link predicate. Offline regression coverage added; production migration and qualification pending.

## 2026-11-26 — V2 web and Android avatar presentation

- `web/app.js`: Loads the same-origin owner-scoped avatar only when authenticated profile metadata says available, resets image on account replacement and retains initials on error. Runtime migration remains gated; browser and Android qualification pending.
- `web/account.js`: Renders owner profile avatar and identity initials, avoids inferring no memberships from native endpoint absence. Runtime migration remains gated; browser and Android qualification pending.
- `web/frontend/src/PersonalTemplate.jsx`: Adds accessible profile image element with initial fallback. Runtime migration remains gated; browser and Android qualification pending.
- `web/frontend/src/AccountTemplate.jsx`: Adds profile photo and initials element in account settings. Runtime migration remains gated; browser and Android qualification pending.
- `web/ui-v1.css`: Sizes circular header profile photo and hides fallback correctly. Runtime migration remains gated; browser and Android qualification pending.
- `web/account.css`: Styles circular account profile avatar and fallback. Runtime migration remains gated; browser and Android qualification pending.
- `web/frontend/tests/native-routing.spec.js`: Mock image route success and failure verify owner-scoped photo and initials fallback. Runtime migration remains gated; browser and Android qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/DragonApi.java`: Bounded native photo fetch from fixed first-party route, authenticated cookies only and no redirects or cache. Runtime migration remains gated; browser and Android qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/MainActivity.java`: Loads optional profile name/photo on worker; checks session binding before UI publication, limits image dimensions, clears on account reset, keeps no persistent photo cache. Runtime migration remains gated; browser and Android qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/NativeChatView.kt`: Displays current profile name and photo or initials in native drawer; keeps account action and theme controls. Runtime migration remains gated; browser and Android qualification pending.

## 2026-11-26 — preserve live voice in V2

- `web/companion.js`: Preserves existing canvas event lifecycle and browser fallback for legacy sessions; native authenticated WebRTC uses first-party JSON start/end, native CSRF, session-bound cleanup, expiry and no legacy tool delegation or automatic paid retries. CI and real audio qualification pending.
- `web/app.js`: Enables native Live voice only for authenticated capability-bearing sessions, guards composer and keyboard launch, retains Mesh isolation. CI and real audio qualification pending.
- `api/agent_platform/first_party_chat.py`: Adds existing voice capability signal to authenticated session response without expanding its authority. CI and real audio qualification pending.
- `api/tests/test_first_party_chat.py`: Verifies disabled chat session also reports voice unavailable. CI and real audio qualification pending.
- `web/frontend/src/VoiceOrb.jsx`: Retains artwork and controls unchanged; clarifies first-party audio-only conversation limitations. CI and real audio qualification pending.
- `web/frontend/playwright.config.mjs`: Runs original orb and browser-transcription regression suites on Linux and Windows. CI and real audio qualification pending.
- `web/frontend/tests/voice-orb.spec.js`: Explicit legacy route fixture and readiness assertion for original renderer tests. CI and real audio qualification pending.
- `web/frontend/tests/voice-browser-fallback.spec.js`: Explicit legacy route fixture and readiness assertion for fallback regression tests. CI and real audio qualification pending.
- `web/frontend/tests/native-routing.spec.js`: Tests native start/owner CSRF/SDP/voice orb/mute/end and absence of legacy calls using mocked transport. CI and real audio qualification pending.
- `.github/workflows/web.yml`: Checks companion transport JavaScript syntax as part of web validation. CI and real audio qualification pending.

## 2026-11-26 — short portrait voice correction

- `web/frontend/src/voice-canvas-renderer.js`: Windows restored voice suite reported 33/34 passes; 360×600 captions overlapped the globe by 61px versus 36px allowed. Raise only the short portrait orb center, retaining radius, waveform energy, original art, and normal viewport geometry. The existing failure assertion is unchanged; rerun pending.
- `web/companion.js`: Prevent a second native start while a previously submitted WebRTC reservation is settling after the UI was closed; retain server-side expiry and explicit hangup handling.

## 2026-11-26 — integrated harness reconciliation

- `.github/workflows/dragonzpyder-api.yml`: Run combined graph, media, recovery, and PostgreSQL integration tests, with agent-stack dependencies for actual checkpoints. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `.github/workflows/scoped-sandbox-runner.yml`: Check Node runner syntax and scoped protocol tests without allocating live VMs. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/adaptive_routing.py`: Conservative fast/default/reasoning selection and sticky escalation after observed failures, through the approved model gateway. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/artifact_formats.py`: Render bounded PDF, DOCX, XLSX and PPTX outputs from validated structured data. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/artifact_http.py`: Authenticated owner-scoped upload, list, download and deletion; only committed artifacts visible. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/artifact_object_store.py`: Private encrypted S3-compatible bytes, conditional immutable writes and bounded reads. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/artifacts.py`: Owner-bound encrypted metadata/bytes, quotas, pending reconciliation, independent readback and idempotent publication. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/computer.py`: Signed scoped v2 runner transport with nonce-bound response verification and legacy compatibility. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/computer_acceptance.py`: Verify isolated computation via exact file bytes, storage readback and cleanup; scripted transport tests are not live VM proof. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/computer_admission.py`: Transactional per-owner/global VM exposure holds and unresolved cleanup fences. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/computer_artifacts.py`: Import selected authorized files and publish verified VM exports to immutable storage. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/computer_run.py`: Lazy scoped VM allocation, per-call authority, deadlines, serialization and cleanup receipts. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/decision_routing.py`: Offline calibrated decision-provider request and validation foundation; live integration absent. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/execution_contract.py`: Shared bounded execution and exact current-turn checkpoint identification. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/first_party_chat.py`: Bind native chat request ledger to selected MCP, artifact, computer, media and workflow capabilities, adaptive routing and exact recovery while preserving login independence. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/first_party_voice.py`: Opt-in realtime WebRTC voice transport and authenticated transcript handoff into canonical chat with exact event identity. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/harness.py`: Bind reviewed native, delegated and programmatic tools and adaptive middleware in one Deep Agents graph. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/mcp_broker.py`: Normalize relevance of authorized capability metadata while retaining schema and invocation grants. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/mcp_managed_catalog.py`: Bound direct reviewed reads and QuickJS bridge, recheck account authority, enforce shared quotas and scheduled policy. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/media_policy.py`: Validate selected inline image/audio bytes and approved model/modality payloads without arbitrary remote URLs. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/media_tools.py`: Bind scoped media tools to capped metered provider gateway, durable attempts and verified artifact publication. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/migrations/20261125_native_voice.sql`: Persist voice mode, selected accounts and conversation reference alongside session expiry. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/migrations/20261125_shared_artifacts.sql`: Create encrypted artifact metadata with pending, ready and deletion lifecycle. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/migrations/20261126_agent_media_attempts.sql`: Persist exact media invocation IDs and metered gateway receipts. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/migrations/20261126_computer_admission.sql`: Persist durable VM exposure and cleanup states. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/migrations/20261126_native_workflows.sql`: Store immutable finite workflow plan, authority reference, phase cursor and receipts. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/native_workflows.py`: Hatchet finite phase dispatch through the common checkpointed harness with owner authority, shared model budget and no blind replay. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/personal_bridge.py`: Apply common adaptive model policy to signed Operly Personal bridge. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/progress_guard.py`: Detect stagnant observed action loops and stop after unresolved external outcomes. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/run_telemetry.py`: Privacy-minimal bounded callback for observed model/tool counts, latency and token usage; cost remains gateway-owned. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/runtime.py`: Use bounded exact-turn recovery, shared routing and execution telemetry for internal harness runs. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/tool_outcomes.py`: Classify observed native and external tool messages, distinguish unknown effects from successful results. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/tool_relevance.py`: Rank authorized metadata conservatively and abstain on ambiguous matching. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/worker.py`: Register gated native durable workflow Hatchet controller alongside existing jobs. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/agent_platform/workspace_bridge.py`: Recover exact Workspace turn evidence on bounded failures and share adaptive routing without changing tenant scope. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/main.py`: Register authenticated artifact and durable-workflow routes and scoped metered media dispatch; web proxy preserves native login and limits upload bodies. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/provider_gateway.py`: Apply reviewed media schema, isolated capped provider key, persistent accounting and media-byte redaction. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/requirements-agent.txt`: Include deterministic document artifact dependencies for the agent runtime. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/requirements.txt`: Add document and private object storage SDK dependencies. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_agent_platform_contract.py`: Check agent contract and scoped runner/gateway compatibility. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_decision_routing.py`: Test offline decision route validation and conservative fallback. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_first_party_agent_stream.py`: Test exact request recovery and stream evidence after bounded termination. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_first_party_request_ledger.py`: Check immutable request fingerprints including explicit compute consent. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_harness_product_surface.py`: Preserve product-specific prompts and authorized capability separation. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_harness_tool_acceptance.py`: Exercise actual Deep Agents graph with scripted model, computer and reviewed MCP/QuickJS tools. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_mcp_connections.py`: Test direct capability selection, revocation and bounded connection behavior. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_native_harness_extensions.py`: Exercise voice event idempotency, model escalation, media schema and generic workflow plan checks. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_native_workflows_postgres.py`: Test workflow phase recovery and media artifact readback using real PostgreSQL and scripted providers. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_progress_guard.py`: Exercise stale-turn rejection, unknown effects, progress and telemetry regression fixtures. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_shared_artifacts.py`: Test deterministic document rendering, encrypted storage policy and object transport. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_shared_artifacts_postgres.py`: Test real PostgreSQL isolation, immutable publication, object reconciliation and VM admission using simulated external services. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_universal_mcp_catalog.py`: Retain grant-scoped catalog behavior under relevance ranking and direct reads. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `api/tests/test_workspace_bridge.py`: Check bounded Workspace execution and exact current-turn partial receipt recovery. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `apps/sandbox_runner/computer_tool.py`: Bound VM shell/Python output, file reads and exports; reject symlink traversal and clean process groups. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `apps/sandbox_runner/package-lock.json`: Pin sandbox runner SDK and transitive Node dependencies. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `apps/sandbox_runner/package.json`: Configure scoped runner Node package and tests. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `apps/sandbox_runner/scope.mjs`: Validate immutable personal/workspace scope, lifetime, operation allowlist and argument bounds. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `apps/sandbox_runner/scope.test.mjs`: Offline scope and protocol rejection fixtures. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `apps/sandbox_runner/server.mjs`: Authenticate signed scoped VM requests, isolate networking, transfer bounded result files and serialize operations. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `apps/sandbox_runner/server_ready.mjs`: Start and warm runner with readiness checks. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `web/app.js`: Native chat streaming, explicit per-turn consent, file upload/download and voice handoff; preserve native login routing. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `web/companion.js`: Bridge realtime voice transcript and spoken canonical response without provider tool authority. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `web/frontend/src/PersonalTemplate.jsx`: Expose gated compute/media/workflow consent controls without replacing existing login shell. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `web/frontend/src/WorkspaceControls.jsx`: Accept selected file types for native attachment ingestion. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `web/frontend/tests/native-routing.spec.js`: Scope checkbox assertions to the connection dialog and preserve dedicated login regression. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `web/main.py`: Register authenticated artifact and durable-workflow routes and scoped metered media dispatch; web proxy preserves native login and limits upload bodies. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `web/mesh.css`: Honor hidden capability controls despite switch styling. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.
- `web/mesh.js`: Route native attachment drafts to the canonical chat adapter instead of legacy Mesh. Integrated revision requires fresh CI; no live provider, storage or sandbox qualification asserted.


## 2026-11-26 — screenshot-driven UI correction

- `web/app.js`: Canonical account entrypoint redirects for signed-out sessions, retry state for outages, removes duplicate chat credential submission. CI and device verification pending.
- `web/frontend/src/PersonalTemplate.jsx`: Simplifies sidebar and removes duplicate login markup; voice retained. CI and device verification pending.
- `web/frontend/src/AccountTemplate.jsx`: Removes marketing hero and numbered settings headings; compact account navigation; preserves credential and recovery form IDs. CI and device verification pending.
- `web/account.js`: Official Google outline widget and explicit legacy eligibility; failed routing does not silently downgrade to legacy. CI and device verification pending.
- `web/ui-v1.css`: Explicit sidebar button reset and compact navigation/error UI; voice untouched. CI and device verification pending.
- `web/account.css`: Compact sign-in and flat settings sections; preserves accessible controls and hidden states. CI and device verification pending.
- `web/frontend/src/AppearanceSettings.jsx`: Concise appearance copy. CI and device verification pending.
- `web/frontend/tests/ui.spec.js`: Checks transparent button styling, border reset and mobile targets in both themes. CI and device verification pending.
- `web/frontend/tests/native-routing.spec.js`: Tests direct native redirect and failed-session retry without credential form. CI and device verification pending.

- `web/frontend/scripts/check-build.mjs`: Replaces obsolete workspace-switcher presence assertion with new-chat navigation and explicit checks that the duplicate credential form and marketing intro are absent; preserves all voice, composer, and account controller assertions. Rerun pending.

## Modular voice transport

- `api/agent_platform/modular_voice.py`: Room-scoped voice admission, expiry, participant token and authenticated worker turn dispatch. No live rollout or paid audio qualification performed.
- `api/agent_platform/migrations/20261126_modular_voice.sql`: Extend native voice session ledger for modular transport, hashed room nonce and original session authority. No live rollout or paid audio qualification performed.
- `api/agent_platform/first_party_chat.py`: Recheck scoped voice authority during canonical turns; advertise modular transport without granting extra computer, media or durable privileges. No live rollout or paid audio qualification performed.
- `api/main.py`: Register modular voice endpoints and bounded room expiry cleanup. No live rollout or paid audio qualification performed.
- `api/requirements.txt`: Add LiveKit server API dependency for room and token operations. No live rollout or paid audio qualification performed.
- `api/requirements-voice.txt`: Separate streaming speech worker dependencies, no reasoning provider. No live rollout or paid audio qualification performed.
- `api/voice_worker.py`: LiveKit worker with Deepgram Flux STT, Aura TTS and local VAD; confirmed turns delegated to canonical harness; no local LLM. No live rollout or paid audio qualification performed.
- `api/Dockerfile.voice`: Separate streaming audio worker image with predownloaded VAD model. No live rollout or paid audio qualification performed.
- `web/frontend/package.json`: Add LiveKit client dependency. No live rollout or paid audio qualification performed.
- `web/frontend/src/modular-voice.js`: Connect and publish microphone, attach remote audio, receive room-scoped result events. No live rollout or paid audio qualification performed.
- `web/companion.js`: Choose modular voice when gated; preserve existing realtime lifecycle as optional path. No live rollout or paid audio qualification performed.
- `web/app.js`: Expose modular capability and refresh canonical chat history on returned voice results without resubmission. No live rollout or paid audio qualification performed.
- `api/tests/test_modular_voice.py`: Offline config, token restriction and authorization regression tests. No live rollout or paid audio qualification performed.
- `.github/workflows/dragonzpyder-api.yml`: Run modular voice contracts and separate SDK import smoke checks without paid requests. No live rollout or paid audio qualification performed.
- `api/agent_platform/first_party_voice.py`: Require an actual realtime provider call ID before admitting browser-submitted realtime transcripts; modular voice rooms exclusively use their dedicated worker authorization. Existing schema compatible; regression CI pending.

## OpenRouter-only voice default candidate

- `api/agent_platform/openrouter_voice.py`: Browser-owned session admission, bounded mono PCM utterances, canonical chat ledger handoff, exact committed answer segments and replay fences. OpenRouter Whisper Turbo and Kokoro are reviewed fixed defaults. Live provider and device qualification pending.
- `api/agent_platform/migrations/20261126_openrouter_voice.sql`: Durable turn and per-segment attempt fences; no recordings or duplicated transcript storage. Live provider and device qualification pending.
- `api/provider_gateway.py`: Trusted internal speech payloads use the existing separately capped OpenRouter media key, existing admission and redacted accounting, including generation IDs. Live provider and device qualification pending.
- `api/main.py`: Register OpenRouter voice router and share existing provider runtime. Live provider and device qualification pending.
- `api/agent_platform/first_party_chat.py`: Expose independent OpenRouter-only voice capability and session availability. Live provider and device qualification pending.
- `web/main.py`: Limit utterance JSON body to 1.3 MB before native proxy buffers it. Live provider and device qualification pending.
- `web/companion.js`: Prefer OpenRouter-only voice when enabled; preserve optional LiveKit/realtime transport and lifecycle. Live provider and device qualification pending.
- `web/app.js`: Expose OpenRouter voice capability to existing voice UI. Live provider and device qualification pending.
- `web/frontend/src/openrouter-voice.js`: Local AudioWorklet microphone capture, energy VAD with pre-roll, 16 kHz WAV resampling, bounded one-at-a-time turns, prefetch one committed speech segment and stop audio on interruption. Live provider and device qualification pending.
- `api/tests/test_openrouter_voice.py`: Offline WAV, modality, session authority, capped key and redacted metering contracts. Live provider and device qualification pending.
- `web/frontend/scripts/test-openrouter-voice.mjs`: Offline WAV encoding, silence/pause and short-noise detector checks. Live provider and device qualification pending.
- `web/frontend/package.json`: Run local speech detector and WAV tests with frontend test suite. Live provider and device qualification pending.
- `.github/workflows/dragonzpyder-api.yml`: Run OpenRouter-only voice tests with offline API contracts. Live provider and device qualification pending.
- `api/tests/test_openrouter_voice.py`: Exercise actual PostgreSQL migration, duplicate utterance identity, no paid replay, segment claim, cross-owner denial and session closure with scripted gateway/harness.
- `.github/workflows/dragonzpyder-api.yml`: Include OpenRouter voice PostgreSQL fixture in disposable database integration job.

## Transport-independent voice session contract

- `api/agent_platform/openrouter_voice.py`: Introduce provider-neutral session endpoints, explicit bridge delegation and PCM/G.711 normalization; reuse existing speech providers and canonical request ledger. Offline CI pending; no live transport proof.
- `api/agent_platform/migrations/20261126_openrouter_voice.sql`: Persist source metadata and unique hashed session-bound bridge grants; revoke on closure. Offline CI pending; no live transport proof.
- `api/main.py`: Require bounded length-framed direct voice input before JSON parsing. Offline CI pending; no live transport proof.
- `web/main.py`: Bound provider-neutral and legacy utterance proxy bodies to accommodate 48 kHz stereo PCM. Offline CI pending; no live transport proof.
- `web/companion.js`: Use neutral session admission and closure endpoints. Offline CI pending; no live transport proof.
- `web/frontend/src/openrouter-voice.js`: Use shared neutral turn and speech endpoint. Offline CI pending; no live transport proof.
- `api/tests/test_openrouter_voice.py`: Add native PCM/telephone codec fixtures and bridge grant ownership and authority tests. Offline CI pending; no live transport proof.

## 2026-11-26 — Thanksgiving event

- `web/main.py`: Adds three exact public GET/HEAD routes for the minimal TV display, QR platform selector and official APK release redirect. Inline static QR targets the canonical main-domain selector; no new dependency, identity access, or external image service. Android checks public GitHub release assets only, returns explicit 503 fallback when unavailable. Source inspection only; production smoke check and APK availability pending.

## Thanksgiving public beta APK

- `.github/workflows/thanksgiving-apk.yml`: One-off develop push trigger or manual dispatch downloads the most recent successful develop Android APK workflow artifact, verifies archive and manifest, records SHA256 and publishes a debug-signed prerelease asset; limited job token, no secrets or production signing. Public release and live download verification pending.

- `web/main.py`: Android choice links directly to the named official Thanksgiving beta raw APK release asset, bypassing release page and release-feed lookup; old Android route remains compatible. Public asset must exist before distribution; live verification pending.

## 2026-11-26 — P0 gateway output recovery

- `api/agent_platform/gateway_protocol.py`: Preserve rejection of truncated completions with a fixed internal error code; never release partial tool calls. Offline protocol regression added; CI/live pending.
- `api/main.py`: Propagate fixed truncation code through authenticated internal agent gateway, retain generic error handling and conservative cost settlement. Route-level qualification pending.
- `api/agent_platform/runtime.py`: Opt-in 768–4096 token ceiling for metered gateway only, default unchanged; exact-turn incomplete recovery, no automatic paid retry. SDK regression added; CI/live pending.
- `api/agent_platform/personal_bridge.py`: Classify typed internal gateway error in OpenAI SDK 502 envelope; untrusted error text remains generic. Offline classification regression added; CI/live pending.
- `api/agent_platform/first_party_chat.py`: Recover typed truncation using existing exact-turn no-replay checkpoint mechanism; incomplete status remains nonverified. Offline regression added; CI/live pending.
- `api/tests/test_agent_gateway_protocol.py`: Assert typed rejection of truncated output without accepting it. Offline test, CI pending.
- `api/tests/test_agent_stack_integration.py`: Assert bounded opt-in output configuration, default ceiling and no automatic retry using SDK model construction. Offline test, CI pending.
- `api/tests/test_personal_mcp_bridge.py`: Verify flattened and nested gateway error envelope and unrelated error type handling. Offline test, CI pending.
- `api/tests/test_first_party_agent_stream.py`: Add output limit to exact-turn checkpoint recovery, verify no repeated invocation or historical receipt. Offline test, CI pending.

## 2026-11-26 — P0 runner bootstrap diagnostics

- `apps/sandbox_runner/server.mjs`: Record safe fixed stage and bounded exit status for bootstrap failure, log cleanup outcome on known VM failure. No auth, firewall or execution policy relaxation; real allocation failed before patch.
- `apps/sandbox_runner/server_ready.mjs`: Distinguish SDK allocation failure from readiness failure; known VM cleanup result logged, ambiguous allocation remains unknown.
- `apps/sandbox_runner/scope.mjs`: Add pure allowlisted diagnostic formatter with bounded numeric status and cleanup label; no private messages or identifiers.
- `apps/sandbox_runner/scope.test.mjs`: Verify diagnostic sanitization and fallback; offline CI pending.

## 2026-11-26 — P0 production streaming transport regression

- `api/agent_platform/runtime.py`: Disable SDK auto-streaming specifically for the signed non-streaming inference gateway. Graph-level SSE remains independent; no replay or security/budget bypass. Production 23:47 UTC requests rejected stream=true before inference; streaming flag temporarily rolled back.
- `api/tests/test_agent_stack_integration.py`: Exercise actual ChatOpenAI and LangGraph message-mode streaming against mock HTTP gateway validating complete-response request contract, one inference request and final result. Offline CI pending.

## 2026-11-26 — P0 research quota recovery

- `api/agent_platform/harness.py`: Supervisor gets five bounded web searches instead of three; search-only quota denial continues to synthesis rather than aborting the graph. Specialist search cap remains two. Explicitly disclose irrelevant or insufficient sources; model/tool mutation safeguards unchanged.
- `api/tests/test_harness_tool_acceptance.py`: Script real graph through six attempted searches, assert only five execute and a final grounded/limited answer survives. Offline CI pending. Live Langfuse evidence showed encyclopedia-only results and fourth search rejected; general web provider still must be qualified.

## 2026-11-27 — P0 unify production model routing

- `api/agent_platform/runtime.py`: Shared builder forwards scoped capabilities, specialist clients, routing middleware; startup preflight includes fast/reasoning roles. Offline regression added; CI/live pending.
- `api/agent_platform/first_party_chat.py`: Use shared builder for chat and checkpoint reads; include initial model route metadata. Existing authority preserved. Offline regression coverage via shared builder; CI/live pending.
- `api/agent_platform/workspace_bridge.py`: Use shared builder with authorized Operly workspace tools and existing product surface. Offline regression coverage via shared builder; CI/live pending.
- `api/agent_platform/personal_bridge.py`: Use shared builder with scoped Operly personal tools; no permission expansion. Offline regression coverage via shared builder; CI/live pending.
- `api/agent_platform/native_workflows.py`: Use shared builder in execution and recovery, propagate parent-budget job identity to specialist clients; no new execution or replay authority. Offline regression coverage via shared builder; CI/live pending.
- `api/tests/test_agent_stack_integration.py`: Test role-specific model construction, capability forwarding and parent-budget propagation without paid requests. CI/live pending.

## 2026-11-27 — P0 finalization and rejected tool recovery

- `api/agent_platform/harness.py`: 16/7 bounded call limits, synthesis reservation and explicit no-shell builder instructions. Offline CI and live acceptance pending.
- `api/agent_platform/progress_guard.py`: Final call text-only; one metered inference repair for typed rejected tool selection, never uncertain external effects. Offline CI and live acceptance pending.
- `api/agent_platform/gateway_protocol.py`: Typed rejection without allowing undeclared tools. Offline CI and live acceptance pending.
- `api/main.py`: Preserve only fixed gateway rejection code. Offline CI and live acceptance pending.
- `api/agent_platform/personal_bridge.py`: Classify authenticated gateway rejection envelope. Offline CI and live acceptance pending.
- `api/agent_platform/first_party_chat.py`: Recover checkpoint as incomplete if repair cannot finish. Offline CI and live acceptance pending.
- `api/tests/test_progress_guard.py`: Test bounded synthesis and typed-only repair. Offline CI and live acceptance pending.
- `api/tests/test_agent_gateway_protocol.py`: Test typed unapproved tool rejection. Offline CI and live acceptance pending.

- `api/tests/test_harness_v2.py`: Update the specialist middleware contract for the added finalization guard; retain all external-tool isolation assertions. CI pending.

## 2026-11-27 — Offline VM network enforcement repair

- `apps/sandbox_runner/server.mjs`: Replace failing guest iptables hardening with mandatory offline kernel probe using the same root-owned isolated helper as tool execution. Keep Railway ISOLATED network mode, clean environment and scope checks. No network-enabled mode or fallback.
- `apps/sandbox_runner/computer_tool.py`: Install inherited no_new_privs/libseccomp policy before dispatch; close inherited descriptors; deny network, io_uring and cross-process bypass syscall classes. Verify sockets and exec'ed child; fail closed. Real VM qualification pending.
- `.github/workflows/scoped-sandbox-runner.yml`: Execute actual Linux kernel isolation probe in CI without any network requests or hosted model calls. CI pending.
- `apps/sandbox_runner/README.md`: Record live network-hardening exit 4 and confirmed cleanup, replacement boundary and acceptance requirements.

## 2026-11-27 — production voice readiness instead of a new flag

- `api/agent_platform/openrouter_voice.py`: selects the existing production inference credential, prepares the reviewed additive voice/ledger schema under a bounded transaction and advisory lock, derives availability from existing authority prerequisites and accounting/schema readiness; staging still uses its capped key. Production speech calls consume the existing atomic hourly quota, not a hard dollar cap.
- `api/provider_gateway.py`: routes only approved voice STT/TTS through the shared production key and atomically admits each validated call; ordinary image/agent-media capped-key policy is unchanged.
- `api/main.py`: runs the voice preparation step in API lifespan; optional migration failure leaves text runtime intact.
- `api/tests/test_openrouter_voice.py`: verifies default production activation, key reuse, ledger/schema failure, explicit rollback and quota denial without paid calls. Existing staging tests retained.
- `api/agent_platform/README.md`, `api/agent_platform/migrations/README.md`, `docs/codebase/IMPLEMENTATION.md`: describe prerequisites, new default, bounded migration and budget tradeoff. CI, real role privileges and deployed voice acceptance remain unverified.

- `api/agent_platform/openrouter_voice.py`: checks existing conversation/quota schema, voice column/index and required DML permissions before attempting any DDL. A complete schema is reused without DDL; missing voice components are installed transactionally under the existing role. `api/tests/test_openrouter_voice.py` exercises bootstrap and repeated startup with disposable PostgreSQL. CI pending.
