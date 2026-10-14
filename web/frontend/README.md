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
