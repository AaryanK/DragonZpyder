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
