# web/frontend/tests

Browser-level frontend regression specs.

Read [repository instructions](../../../AGENTS.md) and [codebase navigation](../../../CODEBASE.md). See the [implementation guide](../../../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../../../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`chat-editorial.spec.js`](chat-editorial.spec.js) | Test target: chat editorial.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`native-routing.spec.js`](native-routing.spec.js) | Test target: native routing.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`sso-login-entry.spec.js`](sso-login-entry.spec.js) | Test target: sso login entry.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`ui.spec.js`](ui.spec.js) | Test target: ui.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`voice-browser-fallback.spec.js`](voice-browser-fallback.spec.js) | Test target: voice browser fallback.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`voice-orb.spec.js`](voice-orb.spec.js) | Test target: voice orb.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`workspace-center.spec.js`](workspace-center.spec.js) | Test target: workspace center.spec; inspect assertions and fixtures for the exact contract. | Indexed |

V2 regressions in `ui.spec.js` cover compact phone layouts and account menu access; `native-routing.spec.js` covers identity-derived initials and the unavailable-chat submission guard. These are mocked browser tests, not production qualification.
