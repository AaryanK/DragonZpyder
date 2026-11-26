# api/agent_platform — navigation

Shared runtime, execution, capabilities and persistence modules.

Start at [CODEBASE.md](../../CODEBASE.md), [file inventory](../../docs/codebase/FILE_INDEX.md) and [execution flows](../../docs/codebase/IMPLEMENTATION.md). For current checkout-specific symbols, dependency candidates and tests, generate the source index. Keep this guide current with changes to this directory.

## Child directories

- [benchmarks](benchmarks/)
- [evals](evals/)
- [migrations](migrations/)
- [reports](reports/)

## Files

| Path | Responsibility / navigation | Evidence |
| --- | --- | --- |
| [`AGENT_HARNESS_V2.md`](AGENT_HARNESS_V2.md) | Documentation: AGENT HARNESS V2; check date and canonical status. | Indexed |
| [`AGENT_HARNESS_V3.md`](AGENT_HARNESS_V3.md) | Documentation: AGENT HARNESS V3; check date and canonical status. | Indexed |
| [`BENCHMARK_3_SCENARIOS.md`](BENCHMARK_3_SCENARIOS.md) | Documentation: BENCHMARK 3 SCENARIOS; check date and canonical status. | Indexed |
| [`BUSINESS_CANARY_FIVE_MINUTE_STAGING.md`](BUSINESS_CANARY_FIVE_MINUTE_STAGING.md) | Documentation: BUSINESS CANARY FIVE MINUTE STAGING; check date and canonical status. | Indexed |
| [`GOAL_CONTROLLER.md`](GOAL_CONTROLLER.md) | Documentation: GOAL CONTROLLER; check date and canonical status. | Indexed |
| [`LOCAL_COMPUTER_AUTONOMY.md`](LOCAL_COMPUTER_AUTONOMY.md) | Documentation: LOCAL COMPUTER AUTONOMY; check date and canonical status. | Indexed |
| [`MIGRATION_AUDIT_2026-11-19.md`](MIGRATION_AUDIT_2026-11-19.md) | Documentation: MIGRATION AUDIT 2026 11 19; check date and canonical status. | Indexed |
| [`OPERLY_BUSINESS_CANARY.md`](OPERLY_BUSINESS_CANARY.md) | Documentation: OPERLY BUSINESS CANARY; check date and canonical status. | Indexed |
| [`PERSONAL_GOALS.md`](PERSONAL_GOALS.md) | Documentation: PERSONAL GOALS; check date and canonical status. | Indexed |
| [`README.md`](README.md) | Documentation: README; check date and canonical status. | Indexed |
| [`REAL_LONG_HORIZON_STAGING.md`](REAL_LONG_HORIZON_STAGING.md) | Documentation: REAL LONG HORIZON STAGING; check date and canonical status. | Indexed |
| [`SHARED_WORKFLOW_DISPATCH.md`](SHARED_WORKFLOW_DISPATCH.md) | Documentation: SHARED WORKFLOW DISPATCH; check date and canonical status. | Indexed |
| [`TOOL_RUNTIME_ARCHITECTURE.md`](TOOL_RUNTIME_ARCHITECTURE.md) | Documentation: TOOL RUNTIME ARCHITECTURE; check date and canonical status. | Indexed |
| [`UNIVERSAL_MCP_CONNECTIONS.md`](UNIVERSAL_MCP_CONNECTIONS.md) | Documentation: UNIVERSAL MCP CONNECTIONS; check date and canonical status. | Indexed |
| [`UNIVERSAL_MCP_RUNTIME.md`](UNIVERSAL_MCP_RUNTIME.md) | Documentation: UNIVERSAL MCP RUNTIME; check date and canonical status. | Indexed |
| [`WEB_MONITORING.md`](WEB_MONITORING.md) | Documentation: WEB MONITORING; check date and canonical status. | Indexed |
| [`__init__.py`](__init__.py) | Navigation hint:   init  ; source behavior not independently reviewed. | Indexed |
| [`artifact_evidence.py`](artifact_evidence.py) | Matches successful writes to later reads of the latest exact virtual path; filenames alone are not evidence. | Reviewed |
| [`budget_reservations.py`](budget_reservations.py) | PostgreSQL AtomicBudgetStore and Decimal validation; transactional budget holds and unknown-cost reservations. | Reviewed |
| [`business_canary.py`](business_canary.py) | Navigation hint: business canary; source behavior not independently reviewed. | Indexed |
| [`business_canary_cli.py`](business_canary_cli.py) | Navigation hint: business canary cli; source behavior not independently reviewed. | Indexed |
| [`capability_hub.py`](capability_hub.py) | Per-run tool discovery and binding; capability authority must not be cached across runs. | Reviewed |
| [`computer.py`](computer.py) | Signed transport for existing Operly sandbox runner; not itself a bound agent tool. | Reviewed |
| [`delegation_trace.py`](delegation_trace.py) | Privacy-minimal LangChain callback measuring task invocation and overlap without prompts or outputs. | Reviewed |
| [`eval_runner.py`](eval_runner.py) | Navigation hint: eval runner; source behavior not independently reviewed. | Indexed |
| [`evaluation.py`](evaluation.py) | Navigation hint: evaluation; source behavior not independently reviewed. | Indexed |
| [`first_party_chat.py`](first_party_chat.py) | First-party Personal HTTP session, conversations, chat, streaming, request ledger, goal lookup and cancellation; resolves owner before execution and binds managed MCP tools. | Reviewed |
| [`first_party_voice.py`](first_party_voice.py) | Opt-in audio-only WebRTC start/end and expired-session cleanup; durable reservations, no embedded provider key or agent tools. | Reviewed |
| [`frontier_batch.py`](frontier_batch.py) | Navigation hint: frontier batch; source behavior not independently reviewed. | Indexed |
| [`frontier_stress.py`](frontier_stress.py) | Navigation hint: frontier stress; source behavior not independently reviewed. | Indexed |
| [`gateway_parent_budget.py`](gateway_parent_budget.py) | ParentBudgetGateway reserves a conservative ceiling before dispatch; ambiguous costs retain their hold. | Reviewed |
| [`gateway_protocol.py`](gateway_protocol.py) | Validates bounded internal OpenAI-compatible tool-call request and response schemas; never executes tools. | Reviewed |
| [`harness.py`](harness.py) | Deep Agents construction, specialist prompts/specifications, virtual StateBackend and call/progress limits; accepts explicitly delegated tools. | Reviewed |
| [`jobs.py`](jobs.py) | Hatchet task factories and API delegation for bounded internal agent jobs and ping. | Reviewed |
| [`key_budget.py`](key_budget.py) | Provider-enforced non-resetting OpenRouter per-key cap verification before paid staging tests. | Reviewed |
| [`live_operly_mcp_smoke.py`](live_operly_mcp_smoke.py) | Navigation hint: live operly mcp smoke; source behavior not independently reviewed. | Indexed |
| [`live_platform_tool_smoke.py`](live_platform_tool_smoke.py) | Navigation hint: live platform tool smoke; source behavior not independently reviewed. | Indexed |
| [`local_monitor.py`](local_monitor.py) | Worker-health monitor with local tools, policy decisions and PostgreSQL deduplication/history; no model or remote accounts. | Reviewed |
| [`local_monitor_cli.py`](local_monitor_cli.py) | Navigation hint: local monitor cli; source behavior not independently reviewed. | Indexed |
| [`local_tools.py`](local_tools.py) | Operator-defined read-only worker observations (memory/disk/time); not user's computer or arbitrary shell. | Reviewed |
| [`mcp_adapter.py`](mcp_adapter.py) | ApprovedMCPServer and reviewed remote bindings; allowlisted hosts/tools, no arbitrary stdio or user endpoints. | Reviewed |
| [`mcp_broker.py`](mcp_broker.py) | Provider-neutral grant-scoped discovery, tool schema validation, invocation receipts, lazy catalog tools. | Reviewed |
| [`mcp_connection_http.py`](mcp_connection_http.py) | Browser/native connection start, callback, completion, listing and disconnect routes; session/CSRF boundary. | Reviewed |
| [`mcp_connections.py`](mcp_connections.py) | Reviewed provider OAuth discovery and encrypted user-scoped connection lifecycle; not MCP protocol transport. | Reviewed |
| [`mcp_managed_catalog.py`](mcp_managed_catalog.py) | ManagedMcpRunCatalog rechecks account authorization and token freshness on describe/invoke without checkpoint credentials. | Reviewed |
| [`memory.py`](memory.py) | PersonalMemory and Mem0 configuration for separately provisioned or explicitly approved shared pgvector; caller owns consent. | Reviewed |
| [`model_capabilities.py`](model_capabilities.py) | Fixed OpenRouter catalog preflight for advertised tool support and context size; live smoke still required. | Reviewed |
| [`monitor.py`](monitor.py) | Deterministic staging web monitor: normalize snapshots, compare sources, fingerprint and persist state across wakes. | Reviewed |
| [`monitor_admin.py`](monitor_admin.py) | Navigation hint: monitor admin; source behavior not independently reviewed. | Indexed |
| [`native_canary.py`](native_canary.py) | Finite native-only scheduled LangChain tool canary with signed Personal scope and persisted receipts. | Reviewed |
| [`openrouter_spend_guard.py`](openrouter_spend_guard.py) | Strict provider cap preflight, rejecting missing, reset or excessive limits before model dispatch. | Reviewed |
| [`operly_broker.py`](operly_broker.py) | Verifies Operly wrapper context and uses short-lived opaque leases for remote read-only tools. | Reviewed |
| [`operly_mcp_client.py`](operly_mcp_client.py) | Upstream LangChain MCP adapter loads authorized Operly tools from validated URL, token and exact allowlist. | Reviewed |
| [`operly_readonly_tools.py`](operly_readonly_tools.py) | Scoped LangChain adapter for Operly Kernel search/execute broker; broker rechecks live authority. | Reviewed |
| [`operly_workflow_dispatch.py`](operly_workflow_dispatch.py) | Shared Hatchet pulse dispatch to governed Operly business executor; explicit cron provisioning and dispatch gate. | Reviewed |
| [`ops_benchmark.py`](ops_benchmark.py) | Navigation hint: ops benchmark; source behavior not independently reviewed. | Indexed |
| [`orchestration.py`](orchestration.py) | LangGraph StateGraph and Send fan-out for bounded independent investigation tracks and sanitized reports. | Reviewed |
| [`paid_tool_smoke.py`](paid_tool_smoke.py) | Navigation hint: paid tool smoke; source behavior not independently reviewed. | Indexed |
| [`persistent_graph.py`](persistent_graph.py) | Typed resumable read-only execution graph, wake authorization, deterministic composition and verification. | Reviewed |
| [`persistent_tool_canary.py`](persistent_tool_canary.py) | Bounded three-wake model-selected local-tool canary; validates actual tool calls and persisted result digest. | Reviewed |
| [`personal_bridge.py`](personal_bridge.py) | Private Operly signed-session Personal entry point, isolated thread key, scheduled reads and receipt reporting. | Reviewed |
| [`personal_goal_tools.py`](personal_goal_tools.py) | Signed-user native persistent-goal tools with trusted owner/session scope; short read-only jobs. | Reviewed |
| [`personal_history_http.py`](personal_history_http.py) | Gated read-only archive conversation/message endpoints; archived content never replayed into agents. | Reviewed |
| [`personal_history_import.py`](personal_history_import.py) | Operator-only transcript export/prepare/seal/open/import with expected counts and approved owners; archive not a checkpoint. | Reviewed |
| [`personal_wake.py`](personal_wake.py) | Durable sequential Personal MCP wakes and goal controller; renews exact-capability authority per wake. | Reviewed |
| [`progress_guard.py`](progress_guard.py) | Before-model middleware fingerprints current-turn tool actions and terminates repeated cycles as incomplete. | Reviewed |
| [`provider_pacing.py`](provider_pacing.py) | Gateway-local admission pacing and capped Retry-After parsing; not cross-replica accounting. | Reviewed |
| [`router.py`](router.py) | Internal service-authenticated experimental /internal/agents/run route. | Reviewed |
| [`runtime.py`](runtime.py) | Model selection, LangGraph checkpoint runtime, model client, telemetry and result/termination summaries. | Reviewed |
| [`scientific_oracles.py`](scientific_oracles.py) | Bounded deterministic Decimal numerical audits for quadratic gradient updates and trilinear interpolation; no dynamic code. | Reviewed |
| [`staging_smokes.py`](staging_smokes.py) | Navigation hint: staging smokes; source behavior not independently reviewed. | Indexed |
| [`subjective_monitoring.py`](subjective_monitoring.py) | Recommendation schema and provenance/approval validation; does not establish subjective correctness. | Reviewed |
| [`synthetic_business_cron.py`](synthetic_business_cron.py) | Navigation hint: synthetic business cron; source behavior not independently reviewed. | Indexed |
| [`synthetic_business_tools.py`](synthetic_business_tools.py) | Navigation hint: synthetic business tools; source behavior not independently reviewed. | Indexed |
| [`web_research.py`](web_research.py) | Bounded provider-specific search, query/excerpt normalization and source URL safety; external text untrusted. | Reviewed |
| [`worker.py`](worker.py) | Hatchet worker startup and conditional workflow registration; registration alone does not schedule work. | Reviewed |
| [`workspace_bridge.py`](workspace_bridge.py) | Signed Operly workspace delegation bridge; scoped MCP bearer excluded from model context. | Reviewed |

Reviewed entries are source-inspected summaries; indexed entries are navigation only. Neither proves deployment.
