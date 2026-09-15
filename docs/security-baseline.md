# Legacy security and execution baseline — 2026-09-15

Inspected revision: `86a12ef56bf46d214dd02ee4be7549d7056dd4c7` on master. Static inspection only; no credentials were used and no legacy actions were executed.

The sole program contains 1,042 lines. Python 3.12 `ast.parse` fails at line 346: unterminated string literal. There is no dependency manifest, package layout, test suite or CI. The `testcode` import has no matching tracked module. These facts block a reproducible launch independently of provider access.

Non-placeholder credential-like Twilio assignments occur at lines 320–321 and 359–360. Treat them as exposed pending owner/provider revocation checks; their validity was not tested. Some top-level credential assignments are obvious placeholders. Do not copy any values into reports, prompts or tickets. This was not a complete history or secret scan.

Next containment PR: replace all credential literals with validated environment/broker lookups, add ignored local secret/token paths and a placeholder-only example configuration, scan current tree and full history with redacted output, and add a secrets gate. Revoke/rotate affected provider credentials and check usage through an authorized account. Removing source values does not revoke credentials or remove historical copies. Do not rewrite shared history without coordinating downstream clones and branches.

Keep the old program as clearly labelled legacy reference, excluded from the new package and default startup. Do not repair just the syntax and expose its ungoverned SMTP/Twilio/desktop actions. Avoid loading its pickle credential files in a new runtime; migrate through fresh trusted OAuth authorization and encrypted credential storage. Scope shell/files/browser access, make consequential mutations policy-controlled, and verify effects.

The current work adds acceptance specifications only and has not performed revocation, source containment, provider configuration or production deployment. The architectural plan is maintained in Operly at `docs/architecture/dragonzpyder-operly-2026-09-15.md`.
