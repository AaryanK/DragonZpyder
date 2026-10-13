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

## AI Mesh and Project IC direction (October 2026)

The public landing page also documents a broader **planned** vision alongside the already implemented Personal AI frontend:

- **AI Mesh:** a model-agnostic consumer interface, selectable primary models, bounded delegation to specialist models, creative services, explicit approvals, usage metering and task spending limits. A model gateway such as OpenRouter is an implementation candidate, not a completed integration.
- **Project IC:** an exploratory shared wallet and usage-ledger concept for participating AI applications, allowing small metered experiences alongside subscriptions. External credits are not automatically portable; partner contracts and payment compliance are prerequisites.
- **Compute economy:** longer-term research into verifiable GPU-hours, operations, useful AI work and contractual redemption for computing services. FLOPs do not directly measure intelligence and do not by themselves back a stable currency.
- **Motivation:** accessible AI across backgrounds and languages, with imagery of fire as creative energy and the spider that weaves a web without becoming confined by it. These philosophical inspirations are inclusive, not product access requirements.

**Implementation status:** these are roadmap/research initiatives, not claims that the wallet, partner marketplace, multi-model consumer hub or currency is live. The production runtime and approved-action boundary described above remain unchanged.

**Proposed order:** prototype a provider-connected model selector and usage controls; validate unit economics; pilot an auditable ledger; then explore consenting partner integrations and regulated settlement, before any transferable-credit or compute-backed instrument.
