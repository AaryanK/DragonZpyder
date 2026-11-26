# DragonZpyder isolated computer execution plane

Source migration from Operly's apps/sandbox_runner, adapted to DragonZpyder's scope model. This is source and offline test coverage, not a deployed VM capability. No legacy v1 endpoint is exposed by this service.

## Contract

- The trusted API constructs a scope: Personal principal + task session, or Workspace principal + workspace + task session. The runner checks the exact scope on every status, execute and destroy request. Personal must not carry a workspace identity.
- POST /v2/computer/sessions creates an isolated Railway Sandbox VM; POST /v2/computer/sessions/{id}/status, /destroy, and /tools/{tool_id} require that scope in the signed payload. Tools require a nested arguments object.
- Separate bearer and HMAC secrets; timestamp/nonce replay protection; response signature binds nonce, HTTP status and bytes. Run exactly one replica; the process-local replay cache is not a cluster-wide or restart-durable replay ledger.
- Root-owned scope metadata, public network-policy metadata, helper and request directory; untrusted Python/shell run under uid 10001, not on the API or runner host. The VM has network off, explicit firewall verification, limited TTL and bounded command deadlines. Browser/network/background execution are not exposed by scoped v2.
- ComputerRun lazily allocates once, serializes calls, enforces a finite run call/deadline grant and explicitly destroys known sessions. Ambiguous operations block further execution; a lost allocation can remain until provider TTL. A signed destroy response is required for a cleanup claim.
- Native tools expose shell/Python/file list/read/write/search and preserve bounded outputs. Files are task-VM data, not user-downloadable artifacts or durable storage.

## Configuration (not applied by this PR)

Runner: DRAGONZPYDER_RUNNER_TOKEN, DRAGONZPYDER_RUNNER_SIGNING_KEY (different), RAILWAY_ENVIRONMENT_ID, Railway SDK authentication. Control plane: DRAGONZPYDER_COMPUTER_RUNNER_URL, DRAGONZPYDER_COMPUTER_RUNNER_TOKEN, DRAGONZPYDER_COMPUTER_RUNNER_SIGNING_KEY. Use private networking and new service secrets. Do not share Operly's credentials. Configure one replica and monitor actual template/VM readiness.

## Gates before any live use

1. Verify exact source/deployment and runner service configuration; do not retire Operly's still-used runner on the basis of this code.
2. Prove real VM allocation, tool result, firewall isolation, root-file protection, cross-scope denial, deadline/cleanup and TTL behavior on a separately approved spend-limited staging run. Offline tests do not establish these properties.
3. Wire trusted per-principal sandbox spend reservations, capability policy, cancellation and user grant into the shared harness call sites; never expose model-supplied runtime IDs or principal IDs. Integrate approved artifact import/export and durable receipts. No public chat activation in this PR.
4. Review restart-durable nonce/idempotency and orphan cleanup before multi-replica or sustained autonomous use.

Implementation uses the existing Railway Sandbox SDK, migrated Python helpers and the same Deep Agents graph. No competing host shell or sandbox orchestrator.

## Production rollout evidence — 2026-11-26

Railway runner deployment `6e4bbb6c-3cdc-4ee3-8d01-a84d91590af2` from `develop` SHA `1dbe06518850256fa8ebd054e137cc267e401d48` passed HTTP health. One private replica, separate runner credentials, port 3000. Template warm failed with `Missing Railway credential`; a DragonZpyder production-scoped Railway project token remains required. Do not reuse Operly's token. API deployment `6d6ce1f4-172e-404f-a569-bff6a8d78d17` passed healthz after runner and S3 bucket/encryption references were configured. Computer and artifact flags remain gated pending migration, budget, VM/isolation and encrypted-object readback tests. HTTP health is not VM readiness.
