# scripts

Repository maintenance and validation scripts.

Read [repository instructions](../AGENTS.md) and [codebase navigation](../CODEBASE.md). See the [implementation guide](../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`check_no_secrets.py`](check_no_secrets.py) | Navigation hint: check no secrets; source behavior not independently reviewed. | Indexed |
| [`production_acceptance_probe.ts`](production_acceptance_probe.ts) | Private one-shot Bun acceptance runner using ordinary test-identity password login, session/CSRF, explicit prompts and request-ledger readback; no provider or DB secrets. | Reviewed |

The probe expects `DZ_PROBE_EMAIL`, `DZ_PROBE_PASSWORD`, `DZ_PROBE_CASE` and optional `DZ_PROBE_RUN` on the existing private Railway Function. Supported cases: auth, chat, python, terminal, research, media. Credential material is never logged. Each deployment executes one case without automatic retry; it logs the full synthetic response and ledger readback, then logs out. Capability flags and HTTP success are not outcome verification. Real artifacts, sources, tool receipts and metering must be inspected separately. Auth setup uses the reviewed operator identity migration; it is not performed by the acceptance runner.
