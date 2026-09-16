# DragonZpyder Web

This directory is the source for `dragonzpyder.xyz`.

## Deployment

DragonZpyder Web is designed to run as a small Railway Node service from the `AaryanK/DragonZpyder` repository with **Root Directory** set to `web`.

Railway runs `npm start`, which starts `server.mjs`. The server:

- serves the public landing page and Personal AI frontend;
- exposes `/healthz` for Railway health checks;
- proxies same-origin `/api/*` requests to `https://operly.dragonzpyder.xyz`;
- preserves the browser session/CSRF boundary while normalizing upstream Origin/Referer headers for Operly;
- never ships provider/model/admin credentials or a Workspace selector to the browser.

`OPERLY_ORIGIN` is an optional server-side override. The default is the existing Railway-hosted Operly service at `https://operly.dragonzpyder.xyz`.

Browser → `dragonzpyder.xyz/api/*` → DragonZpyder Web on Railway → Operly Personal Runtime / Kernel on Railway.

## Migrated assets

The first consolidation commit intentionally pins the existing favicon/social preview image to immutable blobs in the former `DragonZpyder-Landing` repository. This keeps the visual identity stable without copying large binary blobs through the GitHub API migration. Those assets can be copied into `web/` later without changing the application architecture.

## Legacy boundary

`chat.html` redirects to the governed `/app.html` product. Direct RunPod/OpenAI-compatible browser inference is prohibited and checked in CI.
