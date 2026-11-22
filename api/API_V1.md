# DragonZpyder API v1 — operator preview

The existing FastAPI API service is the package boundary. There is no second
agent framework, scheduler, or inference gateway. The web app and Operly
retain their existing routes and authorization boundaries.

| Method | Path | Authority | Availability |
| --- | --- | --- | --- |
| GET | /healthz | none | Existing service health |
| GET | /v1/health | existing inference service token/app key | Existing |
| GET | /v1/models | existing inference service token/app key | Existing |
| POST | /v1/chat/completions | existing inference service token/app key | Existing bounded text inference |
| POST | /v1/agents/run | existing agent operator service token | Opt-in pilot only |

The inference and agent tokens are distinct; do not give either to browser
clients. The agent endpoint does not accept a caller-supplied principal, model
override, tool grant, checkpoint ID, callback URL, or workspace ID.

## Run an agent

Use the actual API service origin for the deployment; the intended public
hostname is api.dragonzpyder.xyz (not verified by this change).

```sh
curl --fail-with-body --max-time 180 \
  "$DRAGONZPYDER_API_URL/v1/agents/run" \
  -H "Authorization: Bearer $DRAGONZPYDER_AGENT_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Draft a small Python function and verify the example arithmetic."}'
```

Example response shape (illustrative, not a recorded execution):

```json
{
  "object": "agent.run",
  "id": "32-character-server-generated-hex-id",
  "status": "completed",
  "answer": "Agent result",
  "termination_reason": null,
  "successful_tools": ["read_file"],
  "failed_tool_count": 0,
  "virtual_artifact_paths": ["/workspace/example.py"],
  "artifact_readback_paths": ["/workspace/example.py"],
  "objective_verified": false
}
```

The status describes agent execution, not verified achievement of an objective.
Virtual paths are not downloadable files or external changes. A request starts
a fresh checkpoint thread. This is a synchronous operation; the ID is not yet
a polling handle. Do not automatically retry POST requests, including after
timeouts; retry may create another paid run. No user-scoped tool authority or
durable schedule is granted by this endpoint.

## Operator configuration

Keep the preview off unless deliberately validating it. In addition to the
existing runtime, database, model and service credential settings, it requires:

- DRAGONZPYDER_VERSIONED_AGENT_API_ENABLED=1
- DRAGONZPYDER_AGENTS_ENABLED=1
- DRAGONZPYDER_AGENT_USE_GATEWAY=1
- DRAGONZPYDER_AGENT_TOOL_CALLS_ENABLED=1
- DRAGONZPYDER_AGENT_PAID_TEST_MAX_KEY_LIMIT_USD=0.50

The last setting must also be configured on the actual inference gateway;
its existing provider-side cap check must pass and its persistent usage ledger
must be available. The cap is aggregate, not a per-run/customer allocation.
Do not enable on an unrestricted shared production provider account.
The API does not manage key provisioning. Do not put any credentials in source.

Contract tests:
```sh
pytest -q api/tests/test_agent_platform_contract.py
```

## Next contracts (not implemented by this PR)

- POST /v1/runs, GET /v1/runs/{id}, event streaming, cancellation and
  idempotency: extend the existing persistent graph and Hatchet worker.
- Goals and schedules: durable owner-scoped authority, fresh validation,
  recovery, and revocation.
- Tool discovery and execution: use the existing MCP broker, not a second
  registry; require signed scoped delegation for Operly and connected tools.
- Artifact retrieval and memory: authorize each access and deletion, enforce
  retention policy, never expose arbitrary checkpoint contents.
- Customer API keys/OIDC, per-principal quotas and atomic parent/child spend
  limits: prerequisites for public multi-tenant access.
- Multimodal and realtime APIs: migrate the existing web/provider paths with
  compatibility tests rather than duplicating provider logic.

No new deployment service is required. This PR does not enable the pilot,
publish credentials, move Operly's business authority or cut over clients.
