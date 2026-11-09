# DragonZpyder Personal — Progressive UI Prototype (review only)

This branch preserves the existing React 19 + Vite 7 frontend (Node.js 22 build) and Python FastAPI backend. The landing page is separate from the real Personal AI chat at `/app`.

## Intent

Keep chat clean by default. Make working tools accessible from a single **+ menu**, **Ctrl/⌘ K** searchable command palette, or the **Explore workspace** drawer. Unreleased agents/jobs/projects/memory-management views appear as explicitly unavailable, not as working controls.

### Features to review

| Surface | Working behavior in source | Notes |
| --- | --- | --- |
| Composer | Existing message input, Agent/AI Mesh toggle, dictation, live voice and conditional Send | Existing controller IDs retained |
| + menu | File attachment, user-approved camera photo, screen screenshot, workspace navigation | Uploading an image uses the existing AI Mesh attachment flow and changes execution context |
| Command palette | Ctrl/⌘ K, searchable actions, navigation and input controls | The previous Ctrl/⌘ K = new chat binding is removed; New Chat remains its own sidebar action |
| Workspace drawer | Conversations, approvals, connections, model switch discoverable | Agent teams, jobs, projects and memory tools are *marked planned* |
| Camera | Local preview/capture with explicit permission, input attachment, no auto-send | Existing camera prototype; React portal keeps it usable when + menu is hidden |
| Screen capture | getDisplayMedia invoked from a user gesture, local preview, optional screenshot attachment | Browser/device support varies; **no live screen stream is sent to the model** |
| Theme | Graphite and ember dark default, light option remains | User's saved appearance choice persists |
| Mobile | Sidebar drawer, bottom composer, scrollable welcome prompts and compact + menu | Test Android/iOS browser permissions before release |

## Review locally (do not deploy)

From the repository root with Node 22:

```sh
npm install --prefix web/frontend --no-audit --no-fund
npm run dev --prefix web/frontend
```

Open `http://localhost:5173/app`. The frontend uses the existing local API proxy at `http://127.0.0.1:8080`; authenticated chat and approvals require the backend and valid sessions, so a frontend-only run can show an authentication/runtime notice.

To verify the build without a live backend:

```sh
npm run build --prefix web/frontend
npm run test --prefix web/frontend
```

## Acceptance criteria before deployment

- Default desktop/mobile views contain no persistent camera, screen, agents or jobs toolbars.
- Command palette works with keyboard and touch; pressing Ctrl/⌘ K does **not** clear the conversation.
- + menu does not duplicate the existing `mesh-upload`, camera, or model controls.
- Camera and screen preview require browser permission; stream tracks stop on close; no data leaves the browser on preview alone.
- Switching to AI Mesh on upload is clearly disclosed; changing modes does not silently authorize tools.
- Existing auth, CSRF, approvals, voice, Mesh inference, and conversations remain functional after React hydration.
- Real mobile QA confirms the composer does not cover prompt cards, and tests pass in CI.

**Do not merge or deploy** this branch until reviewed and explicitly approved.
