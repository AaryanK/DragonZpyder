# DragonZpyder UI 1.0 — release candidate

## Principle

A conversation is the product surface. Additional capability remains discoverable through the attachment menu, command palette, and workspace drawer. A visible control must be real, clearly disabled, or absent.

## Implemented in this branch

- Real React/Vite Personal chat, with the existing governed FastAPI/Operly adapters preserved.
- Final UI theme layer (`web/ui-v1.css`) split from legacy component rules; shared typography, contrast, focus, spacing and touch sizing tokens.
- Collapsible and keyboard-accessible desktop sidebar, persisted locally; mobile drawer remains independent.
- Command search with focus containment, clear labels, and keyboard shortcuts.
- Explicit, reversible user consent before a file switches from Agent to a separate AI Mesh conversation. Files remain local until submitted.
- Focus containment/restoration for camera, screen, workspace and Agent-to-Mesh confirmation dialogs.
- Desktop and phone layouts validated with Playwright Chromium smoke tests.
- API proxy corrected so `/mesh.css` is served as a stylesheet in development/preview. Build copies only allowlisted CSS into `web/dist`; production FastAPI serves `/ui-v1.css` via an explicit allowlist.
- Windows 10/11 web-app installation support retained with official DragonZpyder assets.

## Automated verification

`npm run build`, `npm test`, `npm run test:e2e`. GitHub Actions `DragonZpyder Web` includes React, FastAPI, Linux Chromium and Windows Chromium; CI and AI Mesh tests run separately.

The browser suite mocks authentication and service APIs to avoid acting on user accounts. It checks user-interface behavior, **not** real provider responses or permissioned agent execution.

## Required before release

- [ ] Verify signed-in live or isolated staging conversation creation, history, long messages and errors.
- [ ] Verify Agent/Mesh switching, accepted and cancelled attachments, model selection and spending caps.
- [ ] Verify action approvals remain explicit, and no unsolicited external action is executed.
- [ ] Test dictation, live voice, camera and screen-capture start/stop on real browsers with permissions.
- [ ] Check keyboard-only flow, zoom/reflow and a screen reader on Windows and mobile.
- [ ] Confirm desktop/mobile visual layouts against actual browser screenshots and both themes.
- [ ] Confirm readiness of Railway production service, previous successful deployment and rollback procedure.
- [ ] Merge only after release gates are met; then verify public route, /app route, login and static assets.

## Scope boundaries

No new backend agent orchestration, memory service, automatic model routing, offline AI, live vision streaming or background job dashboard has been claimed or added. UI controls for unreleased capabilities must remain labeled as planned.

**Do not deploy this branch merely because CI is green.** Authenticated and device-level regression checks are separate acceptance requirements.
