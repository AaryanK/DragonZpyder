# DragonZpyder Web

This directory is the source for `dragonzpyder.xyz`.

## Deployment

The existing Vercel project should be connected to the `AaryanK/DragonZpyder` repository with **Root Directory** set to `web`.

The server-side `/api/*` bridge defaults to `https://operly.dragonzpyder.xyz` and may be overridden only by the Vercel server environment variable `OPERLY_ORIGIN`.

Browser → `dragonzpyder.xyz/api/*` → Vercel bridge → Operly Personal Runtime / Kernel.

The browser contains no provider/model/admin credential and exposes no Workspace selector.

## Migrated assets

The first consolidation commit intentionally pins the existing favicon/social preview image to immutable blobs in the former `DragonZpyder-Landing` repository. This keeps the live visual identity stable without copying large binary blobs through the GitHub API migration. Those two assets can be copied into `web/` later without changing the application architecture.

## Legacy boundary

`chat.html` redirects to the governed `/app.html` product. Direct RunPod/OpenAI-compatible browser inference is prohibited and checked in CI.
