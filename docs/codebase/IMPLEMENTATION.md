# Implementation and execution flows

Source baseline: [d38aa819af86](https://github.com/AaryanK/DragonZpyder/tree/d38aa819af869c3b4f5d979939441b711324d3e5). This describes inspected entrypoints and links to adjacent files; it does not supersede [AGENTS](../../AGENTS.md), [V4](../universal-harness-v4.md), or [ownership](../platform-ownership.md).

## 1. Process and trust boundaries

- [web/Dockerfile](../../web/Dockerfile) builds and tests React/Vite with Node 22, then serves it through Python FastAPI. [web/main.py](../../web/main.py) owns dispatch, security headers, native API forwarding, compatibility Operly forwarding and admin access. [web/frontend/src/main.jsx](../../web/frontend/src/main.jsx) hydrates or mounts the React app; [pages.jsx](../../web/frontend/src/pages.jsx) selects page and compatibility controllers. [web/app.js](../../web/app.js) still owns important transitional chat state and request logic.
- [api/Dockerfile](../../api/Dockerfile) starts the non-root Uvicorn service. [api/main.py](../../api/main.py) registers identity, first-party chat/history/voice, MCP and Operly bridge routers. Its lifespan owns service state, including gated runtime and MCP manager initialization. [provider_gateway.py](../../api/provider_gateway.py) handles provider transport; the gateway is not a client-side agent.
- [worker.py](../../api/agent_platform/worker.py) is a separate Hatchet process. It checks enablement and worker approval, registers ping and bounded job tasks, plus conditional monitor, Personal wake, execution graph, native canary, goal controller and Operly dispatch tasks. Import/registration does not create a user schedule.
- [src/dragonzpyder](../../src/dragonzpyder/) is a thin packaged CLI/client, not the FastAPI harness. The root pyproject registers its CLI. No Android source tree appears in this baseline; do not assume its implementation is here.

## 2. Personal chat, from request to result

```text
React page / compatibility controller (web/app.js)
  -> web/main.py native API proxy
  -> api/main.py registered first-party router
  -> first_party_chat.py: chat / chat_stream
  -> _owner + conversation checks + _chat_owned request ledger path
  -> _execute_chat: model_client, personal_thread, managed_catalog_tools (if selected)
  -> harness.build_frontier_agent + LangGraph checkpointer
  -> _invoke_cancellable / _stream_agent -> result / receipts
```

Start at [first_party_chat.py](../../api/agent_platform/first_party_chat.py): `ChatInput`, `_owner`, `_require_conversation`, `_fingerprint`, `_chat_owned`, `_execute_chat`, `_invoke_cancellable`, `_stream_agent`. Exposed route decorators cover status/session, goals, conversation messages, request status/cancel, chat and chat/stream. Ledger enablement and checkpoint availability are distinct gates. [request ledger migration](../../api/agent_platform/migrations/20261125_first_party_request_ledger.sql) and [ledger tests](../../api/tests/test_first_party_request_ledger.py) are the next stops. [personal_history_http.py](../../api/agent_platform/personal_history_http.py) is the separate history surface; inspect it for archived history changes. Do not route new Personal work through legacy Operly authentication merely because compatibility paths remain.

## 3. Shared intelligence and tools

[harness.py](../../api/agent_platform/harness.py) defines `specialist_specs` and `build_frontier_agent`, Deep Agents virtual filesystem tools, supervisor/specialist instructions and limits. [runtime.py](../../api/agent_platform/runtime.py) defines `model_client`, `build_agent`, `thread_key`, `AgentRuntime`, and result/termination summaries. Check actual caller and tool bindings: there is also a service-only experimental [router.py](../../api/agent_platform/router.py), not a public user endpoint. The virtual filesystem is not an executable computer or durable artifact service. [computer.py](../../api/agent_platform/computer.py) contains the signed runner transport, not a general agent tool. [local_tools.py](../../api/agent_platform/local_tools.py) observes limited worker resources, not a user's laptop.

Relevant cross-cutting implementation candidates: [progress_guard.py](../../api/agent_platform/progress_guard.py), [artifact_evidence.py](../../api/agent_platform/artifact_evidence.py), [scientific_oracles.py](../../api/agent_platform/scientific_oracles.py), [delegation_trace.py](../../api/agent_platform/delegation_trace.py), [orchestration.py](../../api/agent_platform/orchestration.py), [evaluation.py](../../api/agent_platform/evaluation.py). These links are navigation, not proof each is bound to every product route. Inspect [harness tests](../../api/tests/test_harness_product_surface.py) and [tool acceptance](../../api/tests/test_harness_tool_acceptance.py) before changing the interface.

## 4. MCP lifecycle and execution

```text
Authenticated browser/native connection UI
  -> mcp_connection_http.py -> mcp_connections.OAuthConnectionManager
  -> operator-reviewed provider metadata + encrypted credentials
  -> selected user connection / managed_catalog_tools
  -> mcp_broker: McpGrant / CatalogGrant / McpRunCatalog
  -> discover_granted_mcp_tools -> validate_arguments -> invoke_granted_mcp_tool
  -> ToolReceipt / ToolOutcome
```

[mcp_connection_http.py](../../api/agent_platform/mcp_connection_http.py) exposes providers, connection start, native start/complete, callback, connected/list and disconnect. [mcp_connections.py](../../api/agent_platform/mcp_connections.py) handles reviewed providers, OAuth metadata, credential encryption and connection lifecycle. [mcp_broker.py](../../api/agent_platform/mcp_broker.py) owns grant-scoped tool schemas and invocation, including `catalog_tools`. [capability_hub.py](../../api/agent_platform/capability_hub.py) holds per-run bindings; do not cache expiring authority across users. See [mcp_managed_catalog.py](../../api/agent_platform/mcp_managed_catalog.py), [mcp_adapter.py](../../api/agent_platform/mcp_adapter.py), [connection migration](../../api/agent_platform/migrations/20261122_mcp_connections.sql), [native OAuth migration](../../api/agent_platform/migrations/20261125_native_mcp_oauth.sql), [broker tests](../../api/tests/test_mcp_broker.py), [Postgres connection tests](../../api/tests/test_mcp_connections_postgres.py). Do not let models choose credentials or arbitrary endpoint URLs. Native OAuth, provider grants, tool authorization and user approval are distinct concerns.

## 5. Persistent objectives

[worker.py](../../api/agent_platform/worker.py) registers Hatchet task factories in [jobs.py](../../api/agent_platform/jobs.py), [personal_wake.py](../../api/agent_platform/personal_wake.py) and [persistent_graph.py](../../api/agent_platform/persistent_graph.py), among others. [personal_goal_tools.py](../../api/agent_platform/personal_goal_tools.py) binds trusted owner/session/conversation to short read-only native goal tools. In personal_wake, start with `perform_personal_wake`, `execute_personal_goal_plan`, `make_personal_goal_controller_task`; wake authority is renewed for the original session and capability. In persistent_graph, start with `GraphStep`, `validate_plan`, `execute_graph_wake`, `_renew`, `_compose`, `_verify`. This is a typed resumable read-only path, not generalized arbitrary mutation or sandbox execution. Compare [goal receipts schema](../../api/agent_platform/migrations/20261121_personal_goal_receipts.sql), [graph tests](../../api/tests/test_persistent_graph.py), [Postgres graph tests](../../api/tests/test_persistent_graph_postgres.py), [wake tests](../../api/tests/test_personal_mcp_wake.py). For Operly dispatch inspect [operly_workflow_dispatch.py](../../api/agent_platform/operly_workflow_dispatch.py) separately; business authority remains Operly's.

## 6. Identity and Operly separation

[api/identity/](../../api/identity/README.md) is the implementation area; [identity/contracts](../../identity/contracts/) is the contract area. [router.py](../../api/identity/router.py) supplies discovery/JWKS; [browser_authorize.py](../../api/identity/browser_authorize.py) supplies browser UI; [http_bridge.py](../../api/identity/http_bridge.py) owns authorize/token endpoints and DB access helpers; [grants.py](../../api/identity/grants.py) handles registered clients and code/PKCE redemption. [login_http.py](../../api/identity/login_http.py) provides password/profile/logout routes; [sessions.py](../../api/identity/sessions.py) creates, resolves and revokes opaque sessions. [mobile_provider.py](../../api/identity/mobile_provider.py) exposes provider start/callback/redeem and capabilities; [native_signup.py](../../api/identity/native_signup.py) handles explicit verified Google signup. Inspect [provider_http.py](../../api/identity/provider_http.py), recovery and import modules for their separate proof boundaries. Historic module docstrings can lag subsequent route integrations; use current router registration and implementation, not old statements about rollout.

[personal_bridge.py](../../api/agent_platform/personal_bridge.py) and [workspace_bridge.py](../../api/agent_platform/workspace_bridge.py) are private signed Operly bridges, not the first-party Personal login API. Their thread keys and delegated capability scopes are distinct. Personal identity does not grant workspace membership. Tests: [OAuth grants](../../api/tests/test_identity_oauth_grants.py), [native mobile](../../api/tests/test_identity_mobile_provider.py), [session](../../api/tests/test_identity_browser_sessions.py), [workspace bridge](../../api/tests/test_workspace_bridge.py).

## 7. Provider accounting, voice and rollout

Start model request changes at [api/main.py](../../api/main.py) and [provider_gateway.py](../../api/provider_gateway.py). Related paths include [usage_ledger.py](../../api/usage_ledger.py), [budget_reservations.py](../../api/agent_platform/budget_reservations.py), [gateway_parent_budget.py](../../api/agent_platform/gateway_parent_budget.py), [provider_pacing.py](../../api/agent_platform/provider_pacing.py), [model_capabilities.py](../../api/agent_platform/model_capabilities.py), [observability.py](../../api/observability.py). Inspect the specific enforcement path, not just a similarly named helper. Never interpret unknown charges as free or expose provider secrets.

[first_party_voice.py](../../api/agent_platform/first_party_voice.py) starts/ends opt-in audio-only WebRTC sessions, reserves starts and cleans expired sessions. It does not grant agent tools. Inspect [web/backend/voice.py](../../web/backend/voice.py), [VoiceOrb.jsx](../../web/frontend/src/VoiceOrb.jsx), [voice-canvas-renderer.js](../../web/frontend/src/voice-canvas-renderer.js) and [voice tests](../../api/tests/test_first_party_voice.py) for interface-specific changes. The target of voice sharing the same agent harness is not evidence it is already connected.

Deployment truth is independent: inspect [workflows](../../.github/workflows/), service Dockerfiles, Railway deployed commit and feature gates, then relevant acceptance evidence. Keep earlier Node implementations and staged paths distinct from current FastAPI/React entrypoints. Do not remove compatibility code just because a newer path exists.


## Additional reviewed modules and generated index

The file inventory now records source-inspected cross-cutting modules for artifact readback, budget reservations, provider pacing, MCP trust and authorization, memory, persistent monitoring, archive migration, and delegation. Read the named module and tests for the exact boundary; historical rollout wording in source docstrings may be stale.

The checkout-specific generated directory contains an index, a page for every tracked file, folder indexes, and a flat symbol map. Static references and related tests are candidates, not exhaustive dynamic dependencies. Use human-maintained change records and curated summaries to explain actual behavior.

## Frontend V2 foundation

`web/frontend/src/dz-mark.svg` is the local brand master. `web/frontend/scripts/prepare-desktop.mjs` produces web/installation rasters; `android/prepare-brand.sh` produces the native vector. The Personal React shell uses `UiIcon.jsx` and V2 semantic shell tokens in `web/ui-v1.css`. The existing `web/app.js` adapter requests authenticated `/dz/identity/v1/me` for optional display name metadata and never uses it to grant authorization. Native chat capability remains backend-owned; unavailable chat retains drafts and disables send. No provider avatar claim, runtime flag changes or deployment implied.

## Integrated V4 candidate paths

Native chat uses the shared adaptive router and the canonical Deep Agents graph. Selected MCP reads may be bound directly or through bounded QuickJS. Selected artifacts pass through owner-bound encrypted storage and the signed scoped VM runner. Reviewed media operations pass through the capped provider gateway. Native voice transcripts enter the chat ledger; spoken playback remains separate. Native durable objectives are finite dependent phases dispatched by Hatchet with checkpoint/receipt fencing, original authority and shared model budget. All rollout gates remain off unless separately authorized. Tests use scripted providers; production validation remains outstanding.

### Browser sign-in correction

Once `/dz/status` establishes routing, signed-out `/app` goes directly to `/login` for native identity or `/account` for explicitly legacy access. Failed probes show a retry dialog, not a second credential form. `web/account.js` retains verified provider, password, migration and recovery flows; the legacy sign-in link requires explicit routing eligibility. Voice and server authorization remain unchanged.

### Native capability parity

Android consumes `/dz/v2/personal/status` and passes explicit `allow_computer`, `allow_media` and `allow_durable` on the existing ledger-backed chat request, like web. Server authorization and budget gates remain authoritative. Modular OpenRouter voice is a separate pending dependency.
