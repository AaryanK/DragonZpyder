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

## 2026-11-26 — Android harness and appearance parity

- `android/app/src/main/java/xyz/dragonzpyder/android/DragonApi.java`: Reads computer/media/durable/voice-agent capability flags without legacy fallback; ledger and streaming prerequisites. CI/device qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/NativeChatView.kt`: Native one-message execution options and compact neutral drawer/welcome. CI/device qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/MainActivity.java`: Submits selected allow_* fields through existing ledger, clears on send/chat change, simplifies auth/settings and binds dictation result to session. CI/device qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/DragonDesignTokens.kt`: Matches web semantic palette, keeping accessible outlines and native targets. CI/device qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/ChatPresentationState.kt`: Immutable optional capability state, default-off. CI/device qualification pending.
- `android/prepare-brand.sh`: Validates web/Android palette parity during preparation. CI/device qualification pending.
- `android/app/src/test/java/xyz/dragonzpyder/android/DesignContractTest.kt`: Tests default-off consent state. CI/device qualification pending.

## 2026-11-26 — existing voice and capability integration

- `android/app/src/main/java/xyz/dragonzpyder/android/NativeVoiceSession.java`: Adds existing native WebRTC agent-mode transcript submission, dedupe, authenticated request binding and readback of committed response; no automatic replay. Native voice art unchanged. CI/device/live qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/NativeVoiceView.kt`: Shows current provider transcript/committed agent answer and actual voice mode in existing native orb; status-driven animation retained. CI/device/live qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/MainActivity.java`: Requests explicit voice consent, binds selected connections and conversation to the voice session, inserts confirmed agent results and file receipts. CI/device/live qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/DragonApi.java`: Voice call bound to authenticated session under identity lock. CI/device/live qualification pending.
- `android/app/src/main/java/xyz/dragonzpyder/android/ApiRoutePolicy.java`: Exact UUID turn/end allowlist, no broad proxy. CI/device/live qualification pending.
- `android/tests/ApiRoutePolicyTest.java`: Tests voice turn route and rejection paths. CI/device/live qualification pending.
- `web/frontend/src/PersonalTemplate.jsx`: Compact web execution capability menu preserving existing consent IDs. CI/device/live qualification pending.
- `web/app.js`: Syncs menu with available first-party capabilities and clears selections. CI/device/live qualification pending.
- `web/ui-v1.css`: Compact responsive menu style. CI/device/live qualification pending.
- `web/frontend/tests/native-routing.spec.js`: Mock test for gated capability options and chat reset. CI/device/live qualification pending.

## 2026-11-26 — voice lifecycle and appearance review

- `android/app/src/main/java/xyz/dragonzpyder/android/NativeVoiceSession.java`: Separates in-flight execution from playback; stale provider audio buffer events cannot reopen the microphone before a committed agent answer is available.
- `android/app/src/main/java/xyz/dragonzpyder/android/MainActivity.java`: Clears the pending dictation binding when account state resets.
- `android/app/src/androidTest/java/xyz/dragonzpyder/android/AccountIsolationTest.java`: Updates account isolation regression for the current neutral initials fallback and verifies reset of the dictation binding.
- `web/frontend/src/design-tokens.css`: Uses system sans-serif for the shared web token, matching Android platform typography on Android devices; not a bundled identical font file.
- `android/app/src/main/java/xyz/dragonzpyder/android/NativeChatView.kt`: Centralizes capability selection so unavailable controls cannot set consent. Full qualification pending.
