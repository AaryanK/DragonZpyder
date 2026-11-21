# Legacy security and execution baseline — 2026-09-15

Baseline revision: `86a12ef56bf46d214dd02ee4be7549d7056dd4c7` on `master`. The original repository was a single 1,042-line desktop-assistant program that did not parse under Python 3.12, had no reproducible package/test setup, and contained non-placeholder credential-like provider assignments.

## P1 source-containment status

The containment branch removes the historical program from the current runnable tree instead of repairing and re-exposing its ungoverned desktop, mail, telephony and local-credential actions. The new `src/dragonzpyder` package has no import path to the legacy program. The repository now has a pinned build backend, placeholder-only environment example, ignored credential/token/key/pickle paths, fail-clear configuration validation, a current-tree secret-pattern gate and minimal CI.

The legacy source remains reachable in Git history for audit/reference. No credential value is copied into the modern package, documentation, fixtures or CI.

## Outstanding operational security work

Provider revocation/rotation is **not** completed by deleting literals from source. The credential-like values observed in the historical program must be treated as exposed until an authorized provider account confirms replacement/revocation and downstream deployment health. This status must be tracked separately from source containment.

A complete independent full-history secret scan has not been executed in this slice. The known historical exposure is already sufficient to require provider-side action; history rewriting, if ever chosen, must be coordinated separately and must not be represented as credential revocation.

Fresh OAuth authorization must be used for the modern product. Historical pickle/token files must never be loaded into the new runtime. Consequential actions belong behind Operly's scoped authority, approval, idempotency and effect-verification boundaries.

## Acceptance evidence

Local pre-commit validation for this slice: package installation succeeds without runtime dependencies; the CLI reports its version; Python compile succeeds; five package/config boundary tests pass; and the current-tree secret-pattern scan passes. Live provider revocation and deployment changes are intentionally not claimed.
