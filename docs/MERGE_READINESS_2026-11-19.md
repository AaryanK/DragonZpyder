# DragonZpyder / Operly merge readiness — 19 November 2026

**Scope:** GitHub source integration and review only. Does not authorize a production deploy, real business writes, fresh credential issuance, or merging unchecked branches.

## Updated development tree

- Starting point: DragonZpyder `test/real-scheduled-long-horizon-staging-20261119`, encompassing the tested stacked PRs #40–#45.
- Reconciled **all three `master`-only commits** with a two-parent merge commit. The only material file overlap was `README.md`; retained the staging README because it contains every line of the master README plus additional platform notes.
- Brought forward PR #47's stronger `local_monitor.py` integrity checks and `test_local_monitor_receipt_integrity.py` without merging #47 into an earlier shared branch.
- Enforced that regression in both `.github/workflows/ci.yml` and `.github/workflows/dragonzpyder-api.yml`.
- GitHub compare confirmed the integration history is **0 commits behind `master`** at the time of sync. No local workstation checkout was updated; direct GitHub cloning was unavailable in this execution environment.

## Recommended merge order

### DragonZpyder (staging first)

1. **PR #33**: staging FastAPI / Deep Agents / LangGraph / Hatchet / PostgreSQL gateway foundation; validate against the preceding web consolidation stack before any default-branch promotion.
2. **PR #40**: reviewed MCP capability hub, opt-in remote adapters and safety tests.
3. **PR #41 + PR #47 fix**: time/RAM/disk local tools, recurring monitor, durable observations and receipt-integrity verification. The integration branch already includes #47's complete fix, so avoid merging the same patch twice.
4. **PR #42**: 100 local scenario fixtures and 100 accelerated database wakeups. Treat these as bounded regression tests, NOT 100 live cross-provider workflows.
5. **PR #43 + #44**: allowlisted Operly read-only client contract and five-minute *synthetic broker* regression runner. Do not interpret the fake broker as authenticated access to real Operly.
6. **PR #45**: scheduled real-model local-tool choices and three-step persistent PostgreSQL goal. Three observed five-minute executions completed the bounded goal; many later cron cycles correctly used 0 model calls. Stop scheduling terminal goals to avoid pointless Railway container starts.
7. **PR #37**: richer generic goal ledger, web dashboard and event wakeups — integrate/reconcile **separately**. It is on a sibling branch and is not already incorporated into #40–#45. Test cancellation, durable authority renewal, approval handoffs, cost controls, owner isolation and resume semantics before using it for arbitrary tasks.

The integrated branch is a merge candidate and CI baseline, **not a replacement for feature-by-feature review**. Do not merge 400+ historical commits blindly into `master`.

### Operly

1. **PR #374**: fix potential stored HTML injection in the artifact library. Prioritize independent browser/security verification and merge after the security gate passes.
2. **PR #375 vs #376**: both are isolated real Kernel/business-provider read-test branches based on #373. Reconcile the overlapping `controls.py` and test approach; choose one reviewed series rather than merging both blindly.
3. **PR #373**: workspace-scoped delegation and DragonZpyder broker handoff. Hold until the read-only broker works against a dedicated staging Operly workspace with a **fresh** short-lived signed lease on every wake, current membership and consent checks, and revocation tests.
4. The Operly security gate on #376 has been failing Python dependency and frontend Vite audits despite its native-provider tests passing. Vulnerability findings require triage/remediation; do not waive the security gate simply because the provider tests are green.

## Go/no-go gate

- All required CI green on the **integrated commit**, not only older individual feature heads.
- Confirm `master` and feature head ancestry again immediately before merging.
- Verify budget ceilings, no plaintext secrets or user data in checkpoints/prompts, no unsanctioned shell/network access, and scoped read-only workspaces.
- Use isolated staging for one complete signed DragonZpyder -> Operly call with genuinely reissued consent-bound authority, including revoke-then-wake denial.
- Verify branch promotion doesn't auto-deploy to an unreviewed production environment. The main Hatchet worker still runs the older staging branch as of this audit.
- Prefer squash/merge only after resolving branch targets, running the full stack, and receiving deliberate production promotion approval.

## Evidence links

- DragonZpyder #33: https://github.com/AaryanK/DragonZpyder/pull/33
- DragonZpyder #37: https://github.com/AaryanK/DragonZpyder/pull/37
- DragonZpyder #40–#45: https://github.com/AaryanK/DragonZpyder/pulls
- DragonZpyder #47: https://github.com/AaryanK/DragonZpyder/pull/47
- Operly #373, #374, #375, #376: https://github.com/AaryanK/Operly/pulls
