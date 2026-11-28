# DragonZpyder React frontend

React 19 + Vite 7 with Node.js 22 as the build-time toolchain. FastAPI
continues to serve the compiled frontend and private APIs in production.

## Source of truth

- `src/HomeTemplate.jsx` — existing landing design, sections, typography, and navigation.
- `src/PersonalTemplate.jsx` — existing chat, AI Mesh, and voice interface.
- `src/AccountTemplate.jsx` — existing account, sign-in and signup forms.
- `src/pages.jsx` — page orchestration and transitional controllers.
- `src/runtime.jsx` — React runtime status components.
- `index.html`, `app.html`, `account.html` — **minimal Vite entry shells** with metadata
  and styles; page layout is NOT duplicated here.
- `scripts/prerender.mjs` — renders all JSX pages into HTML after Vite compiles them,
  maintaining meaningful content for first paint, crawlers, and no-JavaScript access.
- `web/dist` — build output; FastAPI serves only compiled pages/assets.

## Build and test

```sh
cd web/frontend
npm install
npm run build
npm test
```

The former `web/index.html`, `web/app.html` and `web/account.html`
files have been removed. Visual styles remain in `web/*.css`, and
historical authentication/chat/voice logic in `web/{account,app,mesh,companion,dictation}.js`
is loaded as a compatibility adapter after React hydration. Migrate
these controllers incrementally to React-owned hooks/components without
weakening the server-side auth, CSRF or permission controls.

Do not expose provider credentials via `VITE_` variables or browser bundles.

## Usage admin

`/admin` is a React page but the FastAPI server refuses to serve it without a
verified Operly account whose email is included in `DRAGONZPYDER_ADMIN_EMAILS`.
It does **not** expose the gateway's private admin token to the browser.

## Frontend V2 (first increment)

The local `src/dz-mark.svg` defines the shared DZ mark. The desktop preparation script generates favicon, logo and PWA icon sizes; Android derives its vector from the same master. The compact shell uses semantic light/dark tokens and outline icons. Keep compatibility IDs until controllers are migrated. Future increments: authenticated provider avatars (requires identity contract and safe image serving), React-owned state, remaining secondary surfaces, accessible responsive and visual regression qualification. Do not enable production capability flags in a presentation PR.


## Operations control center (source candidate, November 27, 2026)

The existing /admin page retains inference usage and adds lazy, read-only panels
for Railway deployment inventory (DragonZpyder and Operly), recent Web edge-log
samples, GitHub develop commits/PRs/CI, and Langfuse v2 observation metadata.
New endpoints require an allowlisted native DragonZpyder session; legacy-only
Operly login cannot read these panels. Each response is bounded, no-store,
uses fixed provider endpoints, and sends neither browser cookies nor provider
credentials to the frontend. No mutations or arbitrary provider queries.

Configure **Web service** secrets separately:
- DRAGONZPYDER_ADMIN_RAILWAY_DRAGONZPYDER_TOKEN and DRAGONZPYDER_ADMIN_RAILWAY_OPERLY_TOKEN:
  dedicated environment-scoped Railway project tokens, not a workspace token.
  The implementation performs only fixed GraphQL reads; provider tokens may
  carry broader authority and must remain server-side. Inventory IDs are fixed
  to the current production environments.
- DRAGONZPYDER_ADMIN_GITHUB_TOKEN: optional fine-grained repository read token
  for Contents, Pull requests and Actions; otherwise public API limits apply.
- DRAGONZPYDER_ADMIN_LANGFUSE_HOST, DRAGONZPYDER_ADMIN_LANGFUSE_PUBLIC_KEY,
  DRAGONZPYDER_ADMIN_LANGFUSE_SECRET_KEY: dedicated project credentials for a
  supported HTTPS Langfuse cloud origin; do not paste tokens into code.

Traffic is limited to 200 recent edge requests from the latest Web deployment.
Edge regions are not visitor countries; no raw paths, source IPs, unique users,
referrers or historical totals are inferred. Langfuse reads up to 50 recent
observations, excludes payloads and identifiers of users, and does not claim
complete coverage. No personal conversations, memory contents, secrets, or
workspace records are exposed. Support access to individual customer content
requires a separate durable audit, purpose/permission/retention controls and
authorization review. Future phases: durable aggregated traffic and geolocation,
resource time series, workflow health, trace pagination, identity aggregates,
correlation, and audited support access. CI and live credential-backed
validation are pending; do not claim production deployment or complete analytics.
