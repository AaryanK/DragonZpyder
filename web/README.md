# DragonZpyder Web

This directory is the source for `dragonzpyder.xyz`.

## Core positioning (October 2026)

**DragonZpyder is building the connective layer for independent AI**, not chiefly marketing another Personal assistant. Lead with the fragmented model and app ecosystem, then the solution: a compatible AI Mesh, one coherent experience, and Project IC / AIC as a proposed unified usage-credit balance. Operly is the governed execution backbone; existing DragonZpyder Personal is an early-access starting point.

The purpose is to connect independent providers (reasoning, coding, image, video, audio, agents) and participating third-party AI applications into compound workflows, with visible model choice, permissions, cost and spending limits.

**Economic promise:** a user should be able to fund a DragonZpyder balance once and spend small amounts across services participating through permitted interfaces, rather than needing a premium subscription everywhere. The illustrative $20 allocation on the public site is hypothetical and must not be treated as live pricing, an announced offer, or existing partnerships.

**Non-negotiable honesty:** do not promise universal access, bypass subscriptions, claim external credits transfer, imply vendor partnerships, or present AIC as an issued crypto/transferable currency. Integration availability follows each vendor's technical access and commercial terms. Provider policies, payments compliance and cost recovery matter.

The homepage should introduce these concepts before describing the narrower currently available Personal AI interface. Use the existing grounded editorial palette and avoid decorative AI marketing cliches.

## Interface direction

The web surface and the Personal interface must look and feel like one product, not two unrelated AI demos.

- **Visual language:** graphite/ink surfaces, warm ember/copper emphasis, neutral type, restrained serif editorial moments, thin lines, and deliberate spacing. Avoid neon purple, abstract gradient glows, floating dashboard tiles, and decorative effects that carry no information.
- **Show the actual product:** Personal conversation, scoped capabilities, approvals, and clear execution status. Do not fabricate customer logos, testimonials, completion rates, live model availability, or connected services.
- **Keep examples honest:** example interactions on the landing page are labelled illustrative and never expose inert controls that look actionable.
- **Separate status from aspiration:** Personal AI and Operly have concrete experiences; AI Mesh and Project IC remain labelled planned/research until implemented.
- **Keep the boundaries:** frontend changes must preserve the existing element IDs consumed by `home.js` and `app.js`, same-origin API routing, and Personal-only permissions. Visual redesign is not a reason to widen authority.
- **Ship accessibly:** responsive mobile and desktop layouts, visible keyboard focus, semantic navigation and readable contrast, support for reduced motion.

Public page: `index.html` (self-contained styles). Authenticated experience: `app.html`, `app.css`, `app.js`. The common palette should evolve together; treat `app.js` selectors and backend endpoints as functional contracts.

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


## Live realtime companion

Talk starts a genuine two-way WebRTC audio session on the Personal page (not a voice note). Configure OPENAI_API_KEY on the DragonZpyder Web Railway server. Optional settings: OPENAI_REALTIME_MODEL (defaults to gpt-realtime-2.1), REALTIME_SESSIONS_PER_HOUR (defaults to six starts). Browser Ctrl+Space works only while this tab is focused. The /companion/realtime route verifies the current Personal session and CSRF through Operly. Voice task tool calls use the existing /api/personal-agent/chat and approval boundary. Session starts are rate-limited in memory; that is not durable metering or a spending cap. Implement hard per-user usage budgets before public rollout. Live audio requires HTTPS, a microphone, and provider API access. Transcripts are currently ephemeral, not stored as chat history.
