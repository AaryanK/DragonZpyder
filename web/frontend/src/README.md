# web/frontend/src

React source, UI components, runtime context, markdown and voice renderer.

Read [repository instructions](../../../AGENTS.md) and [codebase navigation](../../../CODEBASE.md). See the [implementation guide](../../../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../../../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`AccountTemplate.jsx`](AccountTemplate.jsx) | Navigation hint: AccountTemplate; source behavior not independently reviewed. | Indexed |
| [`HomeTemplate.jsx`](HomeTemplate.jsx) | Navigation hint: HomeTemplate; source behavior not independently reviewed. | Indexed |
| [`NativeMcpCenter.jsx`](NativeMcpCenter.jsx) | React first-party OAuth MCP connection UI; CSRF-protected requests and opaque selected aliases, never bearer credentials. | Reviewed |
| [`PersonalTemplate.jsx`](PersonalTemplate.jsx) | Navigation hint: PersonalTemplate; source behavior not independently reviewed. | Indexed |
| [`VoiceOrb.jsx`](VoiceOrb.jsx) | React-owned voice interface/lifecycle and artwork renderer integration; visual canvas does not request microphone itself. | Reviewed |
| [`WorkspaceCenter.jsx`](WorkspaceCenter.jsx) | React account-scoped workspace center and same-origin API requests; includes native MCP UI. | Reviewed |
| [`WorkspaceControls.jsx`](WorkspaceControls.jsx) | Accessible modal focus and progressive-disclosure chat controls, command palette, capture/add menus and desktop install; delegates to existing adapters. | Reviewed |
| [`admin.css`](admin.css) | Stylesheet: admin; inspect selectors and importing page. | Indexed |
| [`admin.jsx`](admin.jsx) | Navigation hint: admin; source behavior not independently reviewed. | Indexed |
| [`main.jsx`](main.jsx) | React mount/hydrate entrypoint selecting page by route. | Reviewed |
| [`markdown.js`](markdown.js) | Navigation hint: markdown; source behavior not independently reviewed. | Indexed |
| [`pages.jsx`](pages.jsx) | React page selection and compatibility-adapter orchestration. | Reviewed |
| [`runtime.jsx`](runtime.jsx) | Navigation hint: runtime; source behavior not independently reviewed. | Indexed |
| [`voice-canvas-renderer.js`](voice-canvas-renderer.js) | Navigation hint: voice canvas renderer; source behavior not independently reviewed. | Indexed |
| [`voice-orb.css`](voice-orb.css) | Stylesheet: voice orb; inspect selectors and importing page. | Indexed |
| [`workspace-center.css`](workspace-center.css) | Stylesheet: workspace center; inspect selectors and importing page. | Indexed |

## V2 foundation

- `dz-mark.svg`: canonical monogram consumed by the desktop asset build and Android resource generation.
- `UiIcon.jsx`: outline icon geometry, used by the Personal shell and workspace controls.
- `PersonalTemplate.jsx`: compact shell; preserves controller IDs. `web/app.js` still owns identity and chat capability presentation.

`NativeGoals.jsx` renders first-party goal list, wake counts, receipts and explicit cancellation through the existing owner-scoped API. `NativeMcpCenter.jsx` provides the native connections/goals navigation; no legacy execution fallback.

V2 shared tokens live in `design-tokens.css`; `ui-preferences.js` defines a versioned allowlisted browser-local presentation contract and `AppearanceSettings.jsx` is its user-facing editor. Account synchronization and agent-mediated updates require a separate authenticated API, preview/approval and rollback contract.
