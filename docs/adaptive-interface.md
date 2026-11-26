# Adaptive Interface — frontend subsystem of Universal Harness V4

Status: first increment, proposed for review. Not a production release.

## Goal
Make the UI an addressable, declarative environment. Users and the shared
DragonZpyder harness should eventually inspect, compose and customize the
application across devices, without granting arbitrary access to production
source or security decisions. This subsystem is not another agent or runtime.

## First increment
The Personal web application includes a React customization control and a pure,
versioned semantic interface contract in web/frontend/src/adaptive-interface.js.
The closed-world contract validates atomic revision-checked changes, returns
a semantic snapshot and supports reset. The renderer maps enumerated values
to known styles for conversation font, accent (send action only), message size,
content width and conversation motion. Existing chat DOM IDs and controllers
remain intact. Preferences are held in React state for the mounted page only;
no cross-user browser storage, network endpoint, agent invocation or production
configuration is introduced. The registry is intentionally partial.

## Dependency-ordered expansion
1. Inventory every frontend component and action. Migrate hardcoded CSS to
   semantic tokens, aligned with DTCG design-token format; map existing DOM IDs
   to stable semantic IDs. Preserve a default theme and accessibility.
2. Expand the schema to layout regions, typography, spacing, responsive
   constraints, safe visibility/reordering, localization keys and direction,
   animation, and user-composed workspaces. Translate actual strings rather
   than just setting the HTML lang attribute. Include web and Compose capability
   declarations and unsupported-property errors.
3. Establish authenticated, owner-scoped persistent revisions through the
   existing API/PostgreSQL, with optimistic concurrency, device overrides,
   undo, reset, logout isolation and bounded audit records.
4. Connect to the existing harness with trusted UI inspect/preview/apply/readback
   operations. Evaluate AG-UI for event/state transport and A2UI for declarative
   dynamic surfaces against current upstream specs. Do not build a parallel
   agent, or assume these protocols provide arbitrary shell mutation. The
   authenticated client must explicitly acknowledge the actual applied revision;
   never report a proposed patch as successful execution.
5. Support MCP Apps in isolated, permissioned surfaces and custom sandbox
   applications. Bind actions through the existing capability policy.
6. Qualify real rendering with computed layout, accessibility snapshots and
   optional user-authorized screenshots (redact secrets/content by default).
   Verify keyboard, small screens, zoom, contrast, long strings, RTL, interrupted
   sessions, concurrent edits, denied changes and reset recovery.
7. Implement a native Android Compose renderer for the same portable contract.
   Preserve native controls, and do not replace Android with a WebView.

## Security boundaries
Identity, permissions, approvals, execution receipts and reset affordances
are not removable or agent-editable. No arbitrary HTML, CSS, JavaScript,
network URLs, DOM selectors or code execution may enter the trusted shell
through customization. Data bindings require normal authorization. Model text
and untrusted tool content must never be interpreted as privileged UI patches.
Cross-device persistence and transport are explicitly deferred; no claim of
agent-driven mutation, full customization, or production acceptance yet.

## Acceptance before merge
Run existing web CI and new contract regressions; inspect real browser layout
at desktop and mobile widths, verify existing login/chat/voice/approval behavior,
and verify reset preserves the original visual defaults. Review independent of
backend work. No rollout flag or deployment is authorized by this change.
