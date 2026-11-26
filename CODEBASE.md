# DragonZpyder — codebase navigation

**Read this alongside, not instead of, [README.md](README.md) and [AGENTS.md](AGENTS.md).** The product goal and [canonical V4 architecture](docs/universal-harness-v4.md) remain authoritative and unchanged. This is an implementation/navigation companion, not a new specification or deployment claim.

Baseline: [develop at d38aa819af86](https://github.com/AaryanK/DragonZpyder/tree/d38aa819af869c3b4f5d979939441b711324d3e5).

## Start with the smallest relevant context

1. Read the goal and mandatory guardrails in [AGENTS.md](AGENTS.md).
2. Find the relevant system and request path in [Implementation and execution flows](docs/codebase/IMPLEMENTATION.md).
3. Locate individual paths in [the tracked file inventory](docs/codebase/FILE_INDEX.md). It indexes every baseline tracked file and identifies reviewed vs path-only entries.
4. For source-derived folder and individual file pages, symbols, imports, routes and candidate references, run `python scripts/build_codebase_index.py --directory /tmp/dragonzpyder-codebase`. Start at `INDEX.md`. Use `--output /tmp/dragonzpyder-symbols.md` for one searchable file. This is static navigation, not behavioral verification. CI publishes the generated index.
5. Read the specific function and its tests before editing. Check current PRs, source SHA and actual deployment evidence when relevant. Do not rely on historical reports for current rollout.

## Where to start

| Task | Entry point | Tests |
| --- | --- | --- |
| Personal chat, streaming, cancellation | [first_party_chat.py](api/agent_platform/first_party_chat.py) | [chat](api/tests/test_first_party_chat.py), [stream](api/tests/test_first_party_agent_stream.py), [request ledger](api/tests/test_first_party_request_ledger.py) |
| Core agent and specialists | [harness.py](api/agent_platform/harness.py), [runtime.py](api/agent_platform/runtime.py) | [harness](api/tests/test_harness_v2.py), [tool acceptance](api/tests/test_harness_tool_acceptance.py) |
| MCP and authorization | [mcp_broker.py](api/agent_platform/mcp_broker.py), [mcp_connections.py](api/agent_platform/mcp_connections.py) | [broker](api/tests/test_mcp_broker.py), [connections](api/tests/test_mcp_connections.py) |
| Jobs and scheduled objectives | [worker.py](api/agent_platform/worker.py), [personal_wake.py](api/agent_platform/personal_wake.py), [persistent_graph.py](api/agent_platform/persistent_graph.py) | [wake](api/tests/test_personal_mcp_wake.py), [graph](api/tests/test_persistent_graph.py) |
| Identity and login | [api/identity/](api/identity/README.md) | [password](api/tests/test_identity_password_login.py), [mobile](api/tests/test_identity_mobile_provider.py), [sessions](api/tests/test_identity_browser_sessions.py) |
| Frontend and browser routing | [web/main.py](web/main.py), [React source](web/frontend/src/README.md), [app.js](web/app.js) | [native routing](web/frontend/tests/native-routing.spec.js), [native proxy](web/tests/test_native_first_party_proxy.py) |
| Model gateway and budgets | [api/main.py](api/main.py), [provider_gateway.py](api/provider_gateway.py) | [gateway](api/tests/test_fastapi_gateway.py), [budget](api/tests/test_budget_reservations.py) |
| Voice | [first_party_voice.py](api/agent_platform/first_party_voice.py), [VoiceOrb.jsx](web/frontend/src/VoiceOrb.jsx) | [API voice](api/tests/test_first_party_voice.py), [browser voice](web/frontend/tests/voice-orb.spec.js) |
| Operly delegation | [workspace_bridge.py](api/agent_platform/workspace_bridge.py), [personal_bridge.py](api/agent_platform/personal_bridge.py) | [workspace](api/tests/test_workspace_bridge.py), [Personal MCP](api/tests/test_personal_mcp_bridge.py) |

## Keeping this useful

Every implementation change must update [path-specific change records](docs/codebase/CHANGES.md), file descriptions, and applicable directory/flow documentation in the same PR (see AGENTS.md). Regenerate the local symbol inventory after a checkout change. Prefer meaningful module docstrings and public interface documentation in future implementation PRs over comments that repeat obvious code. Record what is gated, what was tested and what is deployed separately. Never put credentials, personal data or live token values in docs.
