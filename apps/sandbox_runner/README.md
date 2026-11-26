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
