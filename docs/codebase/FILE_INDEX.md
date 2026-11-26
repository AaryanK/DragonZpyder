# Tracked file inventory

Baseline: [`d38aa819af869c3b4f5d979939441b711324d3e5`](https://github.com/AaryanK/DragonZpyder/tree/d38aa819af869c3b4f5d979939441b711324d3e5) (develop, 2026-11-26). 427 pre-existing tracked files across 29 file-containing directories. All paths were enumerated from the complete Git tree. **Reviewed** means source or entrypoint inspected for the summary; **Indexed** means path-based navigation only, not a verified behavior claim. This is not a live deployment inventory. New documentation files in this PR are intentionally outside this baseline. Use [the implementation guide](IMPLEMENTATION.md) first.

## .

Root product contracts, environment example, packaging and operational documentation.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`.env.example`](../../.env.example) | Navigation hint: .env; source behavior not independently reviewed. | Indexed |
| [`.gitignore`](../../.gitignore) | Navigation hint: ; source behavior not independently reviewed. | Indexed |
| [`AGENTS.md`](../../AGENTS.md) | Documentation: AGENTS; check date and canonical status. | Indexed |
| [`OBSERVABILITY.md`](../../OBSERVABILITY.md) | Documentation: OBSERVABILITY; check date and canonical status. | Indexed |
| [`PYTHON_MIGRATION.md`](../../PYTHON_MIGRATION.md) | Documentation: PYTHON MIGRATION; check date and canonical status. | Indexed |
| [`README.md`](../../README.md) | Documentation: README; check date and canonical status. | Indexed |
| [`pyproject.toml`](../../pyproject.toml) | Thin Python client package metadata, setuptools source layout and dragonzpyder CLI entrypoint. | Reviewed |

## .github/workflows

CI and service-specific GitHub Actions workflows; inspect individual triggers before relying on coverage.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`ai-mesh.yml`](../../.github/workflows/ai-mesh.yml) | Workflow/configuration: ai mesh; inspect triggers, jobs and gates. | Indexed |
| [`ci.yml`](../../.github/workflows/ci.yml) | Workflow/configuration: ci; inspect triggers, jobs and gates. | Indexed |
| [`dragonzpyder-api.yml`](../../.github/workflows/dragonzpyder-api.yml) | Workflow/configuration: dragonzpyder api; inspect triggers, jobs and gates. | Indexed |
| [`mcp-connections.yml`](../../.github/workflows/mcp-connections.yml) | Workflow/configuration: mcp connections; inspect triggers, jobs and gates. | Indexed |
| [`web.yml`](../../.github/workflows/web.yml) | Workflow/configuration: web; inspect triggers, jobs and gates. | Indexed |

## api

FastAPI inference/API composition, provider transport, ledgers, service images, staging and implementation packages.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`Dockerfile`](../../api/Dockerfile) | Non-root Python 3.12 FastAPI service image and Uvicorn entrypoint. | Reviewed |
| [`Dockerfile.business-canary`](../../api/Dockerfile.business-canary) | Navigation hint: Dockerfile; source behavior not independently reviewed. | Indexed |
| [`Dockerfile.personal`](../../api/Dockerfile.personal) | Navigation hint: Dockerfile; source behavior not independently reviewed. | Indexed |
| [`Dockerfile.staging`](../../api/Dockerfile.staging) | Navigation hint: Dockerfile; source behavior not independently reviewed. | Indexed |
| [`inference.mjs`](../../api/inference.mjs) | Legacy Node private inference handler with backend bearer, model allowlist, bounded parsing and per-hour admission. | Reviewed |
| [`main.py`](../../api/main.py) | FastAPI gateway composition root, lifespan, router registration, caller auth and catch-all inference dispatch. | Reviewed |
| [`observability.py`](../../api/observability.py) | Configures OpenTelemetry/Langfuse OTLP export and redacted inference spans; full encrypted payload storage is separate. | Reviewed |
| [`package.json`](../../api/package.json) | Data/configuration fixture: package; inspect schema and consumers. | Indexed |
| [`provider_gateway.py`](../../api/provider_gateway.py) | Scoped OpenRouter transport, operation classification, provider-key selection, metering and tracing. | Reviewed |
| [`requirements-agent.txt`](../../api/requirements-agent.txt) | Navigation hint: requirements agent; source behavior not independently reviewed. | Indexed |
| [`requirements-personal.txt`](../../api/requirements-personal.txt) | Navigation hint: requirements personal; source behavior not independently reviewed. | Indexed |
| [`requirements.txt`](../../api/requirements.txt) | Navigation hint: requirements; source behavior not independently reviewed. | Indexed |
| [`server.mjs`](../../api/server.mjs) | Legacy standalone Node HTTP API server; wraps internal inference with concurrency limits and headers. | Reviewed |
| [`staging.css`](../../api/staging.css) | Stylesheet: staging; inspect selectors and importing page. | Indexed |
| [`staging.js`](../../api/staging.js) | Navigation hint: staging; source behavior not independently reviewed. | Indexed |
| [`staging_app.py`](../../api/staging_app.py) | Password-gated staging smoke lab for agent, search, memory and Hatchet diagnostics; no workspace/computer grants. | Reviewed |
| [`staging_ui.html`](../../api/staging_ui.html) | Navigation hint: staging ui; source behavior not independently reviewed. | Indexed |
| [`usage_ledger.py`](../../api/usage_ledger.py) | Append-only PostgreSQL metering, normalized token/cost usage and optional AES-GCM payload escrow; unknown cost is not zero. | Reviewed |

## api/agent_platform

Shared harness, runtime, capabilities, MCP, bridges, scheduling, budgets, memory, verification and evaluation.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`AGENT_HARNESS_V2.md`](../../api/agent_platform/AGENT_HARNESS_V2.md) | Documentation: AGENT HARNESS V2; check date and canonical status. | Indexed |
| [`AGENT_HARNESS_V3.md`](../../api/agent_platform/AGENT_HARNESS_V3.md) | Documentation: AGENT HARNESS V3; check date and canonical status. | Indexed |
| [`BENCHMARK_3_SCENARIOS.md`](../../api/agent_platform/BENCHMARK_3_SCENARIOS.md) | Documentation: BENCHMARK 3 SCENARIOS; check date and canonical status. | Indexed |
| [`BUSINESS_CANARY_FIVE_MINUTE_STAGING.md`](../../api/agent_platform/BUSINESS_CANARY_FIVE_MINUTE_STAGING.md) | Documentation: BUSINESS CANARY FIVE MINUTE STAGING; check date and canonical status. | Indexed |
| [`GOAL_CONTROLLER.md`](../../api/agent_platform/GOAL_CONTROLLER.md) | Documentation: GOAL CONTROLLER; check date and canonical status. | Indexed |
| [`LOCAL_COMPUTER_AUTONOMY.md`](../../api/agent_platform/LOCAL_COMPUTER_AUTONOMY.md) | Documentation: LOCAL COMPUTER AUTONOMY; check date and canonical status. | Indexed |
| [`MIGRATION_AUDIT_2026-11-19.md`](../../api/agent_platform/MIGRATION_AUDIT_2026-11-19.md) | Documentation: MIGRATION AUDIT 2026 11 19; check date and canonical status. | Indexed |
| [`OPERLY_BUSINESS_CANARY.md`](../../api/agent_platform/OPERLY_BUSINESS_CANARY.md) | Documentation: OPERLY BUSINESS CANARY; check date and canonical status. | Indexed |
| [`PERSONAL_GOALS.md`](../../api/agent_platform/PERSONAL_GOALS.md) | Documentation: PERSONAL GOALS; check date and canonical status. | Indexed |
| [`README.md`](../../api/agent_platform/README.md) | Documentation: README; check date and canonical status. | Indexed |
| [`REAL_LONG_HORIZON_STAGING.md`](../../api/agent_platform/REAL_LONG_HORIZON_STAGING.md) | Documentation: REAL LONG HORIZON STAGING; check date and canonical status. | Indexed |
| [`SHARED_WORKFLOW_DISPATCH.md`](../../api/agent_platform/SHARED_WORKFLOW_DISPATCH.md) | Documentation: SHARED WORKFLOW DISPATCH; check date and canonical status. | Indexed |
| [`TOOL_RUNTIME_ARCHITECTURE.md`](../../api/agent_platform/TOOL_RUNTIME_ARCHITECTURE.md) | Documentation: TOOL RUNTIME ARCHITECTURE; check date and canonical status. | Indexed |
| [`UNIVERSAL_MCP_CONNECTIONS.md`](../../api/agent_platform/UNIVERSAL_MCP_CONNECTIONS.md) | Documentation: UNIVERSAL MCP CONNECTIONS; check date and canonical status. | Indexed |
| [`UNIVERSAL_MCP_RUNTIME.md`](../../api/agent_platform/UNIVERSAL_MCP_RUNTIME.md) | Documentation: UNIVERSAL MCP RUNTIME; check date and canonical status. | Indexed |
| [`WEB_MONITORING.md`](../../api/agent_platform/WEB_MONITORING.md) | Documentation: WEB MONITORING; check date and canonical status. | Indexed |
| [`__init__.py`](../../api/agent_platform/__init__.py) | Navigation hint:   init  ; source behavior not independently reviewed. | Indexed |
| [`artifact_evidence.py`](../../api/agent_platform/artifact_evidence.py) | Matches successful writes to later reads of the latest exact virtual path; filenames alone are not evidence. | Reviewed |
| [`budget_reservations.py`](../../api/agent_platform/budget_reservations.py) | PostgreSQL AtomicBudgetStore and Decimal validation; transactional budget holds and unknown-cost reservations. | Reviewed |
| [`business_canary.py`](../../api/agent_platform/business_canary.py) | Navigation hint: business canary; source behavior not independently reviewed. | Indexed |
| [`business_canary_cli.py`](../../api/agent_platform/business_canary_cli.py) | Navigation hint: business canary cli; source behavior not independently reviewed. | Indexed |
| [`capability_hub.py`](../../api/agent_platform/capability_hub.py) | Per-run tool discovery and binding; capability authority must not be cached across runs. | Reviewed |
| [`computer.py`](../../api/agent_platform/computer.py) | Signed transport for existing Operly sandbox runner; not itself a bound agent tool. | Reviewed |
| [`delegation_trace.py`](../../api/agent_platform/delegation_trace.py) | Privacy-minimal LangChain callback measuring task invocation and overlap without prompts or outputs. | Reviewed |
| [`eval_runner.py`](../../api/agent_platform/eval_runner.py) | Navigation hint: eval runner; source behavior not independently reviewed. | Indexed |
| [`evaluation.py`](../../api/agent_platform/evaluation.py) | Navigation hint: evaluation; source behavior not independently reviewed. | Indexed |
| [`first_party_chat.py`](../../api/agent_platform/first_party_chat.py) | First-party Personal HTTP session, conversations, chat, streaming, request ledger, goal lookup and cancellation; resolves owner before execution and binds managed MCP tools. | Reviewed |
| [`first_party_voice.py`](../../api/agent_platform/first_party_voice.py) | Opt-in audio-only WebRTC start/end and expired-session cleanup; durable reservations, no embedded provider key or agent tools. | Reviewed |
| [`frontier_batch.py`](../../api/agent_platform/frontier_batch.py) | Navigation hint: frontier batch; source behavior not independently reviewed. | Indexed |
| [`frontier_stress.py`](../../api/agent_platform/frontier_stress.py) | Navigation hint: frontier stress; source behavior not independently reviewed. | Indexed |
| [`gateway_parent_budget.py`](../../api/agent_platform/gateway_parent_budget.py) | ParentBudgetGateway reserves a conservative ceiling before dispatch; ambiguous costs retain their hold. | Reviewed |
| [`gateway_protocol.py`](../../api/agent_platform/gateway_protocol.py) | Validates bounded internal OpenAI-compatible tool-call request and response schemas; never executes tools. | Reviewed |
| [`harness.py`](../../api/agent_platform/harness.py) | Deep Agents construction, specialist prompts/specifications, virtual StateBackend and call/progress limits; accepts explicitly delegated tools. | Reviewed |
| [`jobs.py`](../../api/agent_platform/jobs.py) | Hatchet task factories and API delegation for bounded internal agent jobs and ping. | Reviewed |
| [`key_budget.py`](../../api/agent_platform/key_budget.py) | Provider-enforced non-resetting OpenRouter per-key cap verification before paid staging tests. | Reviewed |
| [`live_operly_mcp_smoke.py`](../../api/agent_platform/live_operly_mcp_smoke.py) | Navigation hint: live operly mcp smoke; source behavior not independently reviewed. | Indexed |
| [`live_platform_tool_smoke.py`](../../api/agent_platform/live_platform_tool_smoke.py) | Navigation hint: live platform tool smoke; source behavior not independently reviewed. | Indexed |
| [`local_monitor.py`](../../api/agent_platform/local_monitor.py) | Worker-health monitor with local tools, policy decisions and PostgreSQL deduplication/history; no model or remote accounts. | Reviewed |
| [`local_monitor_cli.py`](../../api/agent_platform/local_monitor_cli.py) | Navigation hint: local monitor cli; source behavior not independently reviewed. | Indexed |
| [`local_tools.py`](../../api/agent_platform/local_tools.py) | Operator-defined read-only worker observations (memory/disk/time); not user's computer or arbitrary shell. | Reviewed |
| [`mcp_adapter.py`](../../api/agent_platform/mcp_adapter.py) | ApprovedMCPServer and reviewed remote bindings; allowlisted hosts/tools, no arbitrary stdio or user endpoints. | Reviewed |
| [`mcp_broker.py`](../../api/agent_platform/mcp_broker.py) | Provider-neutral grant-scoped discovery, tool schema validation, invocation receipts, lazy catalog tools. | Reviewed |
| [`mcp_connection_http.py`](../../api/agent_platform/mcp_connection_http.py) | Browser/native connection start, callback, completion, listing and disconnect routes; session/CSRF boundary. | Reviewed |
| [`mcp_connections.py`](../../api/agent_platform/mcp_connections.py) | Reviewed provider OAuth discovery and encrypted user-scoped connection lifecycle; not MCP protocol transport. | Reviewed |
| [`mcp_managed_catalog.py`](../../api/agent_platform/mcp_managed_catalog.py) | ManagedMcpRunCatalog rechecks account authorization and token freshness on describe/invoke without checkpoint credentials. | Reviewed |
| [`memory.py`](../../api/agent_platform/memory.py) | PersonalMemory and Mem0 configuration for separately provisioned or explicitly approved shared pgvector; caller owns consent. | Reviewed |
| [`model_capabilities.py`](../../api/agent_platform/model_capabilities.py) | Fixed OpenRouter catalog preflight for advertised tool support and context size; live smoke still required. | Reviewed |
| [`monitor.py`](../../api/agent_platform/monitor.py) | Deterministic staging web monitor: normalize snapshots, compare sources, fingerprint and persist state across wakes. | Reviewed |
| [`monitor_admin.py`](../../api/agent_platform/monitor_admin.py) | Navigation hint: monitor admin; source behavior not independently reviewed. | Indexed |
| [`native_canary.py`](../../api/agent_platform/native_canary.py) | Finite native-only scheduled LangChain tool canary with signed Personal scope and persisted receipts. | Reviewed |
| [`openrouter_spend_guard.py`](../../api/agent_platform/openrouter_spend_guard.py) | Strict provider cap preflight, rejecting missing, reset or excessive limits before model dispatch. | Reviewed |
| [`operly_broker.py`](../../api/agent_platform/operly_broker.py) | Verifies Operly wrapper context and uses short-lived opaque leases for remote read-only tools. | Reviewed |
| [`operly_mcp_client.py`](../../api/agent_platform/operly_mcp_client.py) | Upstream LangChain MCP adapter loads authorized Operly tools from validated URL, token and exact allowlist. | Reviewed |
| [`operly_readonly_tools.py`](../../api/agent_platform/operly_readonly_tools.py) | Scoped LangChain adapter for Operly Kernel search/execute broker; broker rechecks live authority. | Reviewed |
| [`operly_workflow_dispatch.py`](../../api/agent_platform/operly_workflow_dispatch.py) | Shared Hatchet pulse dispatch to governed Operly business executor; explicit cron provisioning and dispatch gate. | Reviewed |
| [`ops_benchmark.py`](../../api/agent_platform/ops_benchmark.py) | Navigation hint: ops benchmark; source behavior not independently reviewed. | Indexed |
| [`orchestration.py`](../../api/agent_platform/orchestration.py) | LangGraph StateGraph and Send fan-out for bounded independent investigation tracks and sanitized reports. | Reviewed |
| [`paid_tool_smoke.py`](../../api/agent_platform/paid_tool_smoke.py) | Navigation hint: paid tool smoke; source behavior not independently reviewed. | Indexed |
| [`persistent_graph.py`](../../api/agent_platform/persistent_graph.py) | Typed resumable read-only execution graph, wake authorization, deterministic composition and verification. | Reviewed |
| [`persistent_tool_canary.py`](../../api/agent_platform/persistent_tool_canary.py) | Bounded three-wake model-selected local-tool canary; validates actual tool calls and persisted result digest. | Reviewed |
| [`personal_bridge.py`](../../api/agent_platform/personal_bridge.py) | Private Operly signed-session Personal entry point, isolated thread key, scheduled reads and receipt reporting. | Reviewed |
| [`personal_goal_tools.py`](../../api/agent_platform/personal_goal_tools.py) | Signed-user native persistent-goal tools with trusted owner/session scope; short read-only jobs. | Reviewed |
| [`personal_history_http.py`](../../api/agent_platform/personal_history_http.py) | Gated read-only archive conversation/message endpoints; archived content never replayed into agents. | Reviewed |
| [`personal_history_import.py`](../../api/agent_platform/personal_history_import.py) | Operator-only transcript export/prepare/seal/open/import with expected counts and approved owners; archive not a checkpoint. | Reviewed |
| [`personal_wake.py`](../../api/agent_platform/personal_wake.py) | Durable sequential Personal MCP wakes and goal controller; renews exact-capability authority per wake. | Reviewed |
| [`progress_guard.py`](../../api/agent_platform/progress_guard.py) | Before-model middleware fingerprints current-turn tool actions and terminates repeated cycles as incomplete. | Reviewed |
| [`provider_pacing.py`](../../api/agent_platform/provider_pacing.py) | Gateway-local admission pacing and capped Retry-After parsing; not cross-replica accounting. | Reviewed |
| [`router.py`](../../api/agent_platform/router.py) | Internal service-authenticated experimental /internal/agents/run route. | Reviewed |
| [`runtime.py`](../../api/agent_platform/runtime.py) | Model selection, LangGraph checkpoint runtime, model client, telemetry and result/termination summaries. | Reviewed |
| [`scientific_oracles.py`](../../api/agent_platform/scientific_oracles.py) | Bounded deterministic Decimal numerical audits for quadratic gradient updates and trilinear interpolation; no dynamic code. | Reviewed |
| [`staging_smokes.py`](../../api/agent_platform/staging_smokes.py) | Navigation hint: staging smokes; source behavior not independently reviewed. | Indexed |
| [`subjective_monitoring.py`](../../api/agent_platform/subjective_monitoring.py) | Recommendation schema and provenance/approval validation; does not establish subjective correctness. | Reviewed |
| [`synthetic_business_cron.py`](../../api/agent_platform/synthetic_business_cron.py) | Navigation hint: synthetic business cron; source behavior not independently reviewed. | Indexed |
| [`synthetic_business_tools.py`](../../api/agent_platform/synthetic_business_tools.py) | Navigation hint: synthetic business tools; source behavior not independently reviewed. | Indexed |
| [`web_research.py`](../../api/agent_platform/web_research.py) | Bounded provider-specific search, query/excerpt normalization and source URL safety; external text untrusted. | Reviewed |
| [`worker.py`](../../api/agent_platform/worker.py) | Hatchet worker startup and conditional workflow registration; registration alone does not schedule work. | Reviewed |
| [`workspace_bridge.py`](../../api/agent_platform/workspace_bridge.py) | Signed Operly workspace delegation bridge; scoped MCP bearer excluded from model context. | Reviewed |

## api/agent_platform/benchmarks

Benchmark specifications and workload fixtures.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`LONG_HORIZON_MONITORING_ACCEPTANCE.md`](../../api/agent_platform/benchmarks/LONG_HORIZON_MONITORING_ACCEPTANCE.md) | Documentation: LONG HORIZON MONITORING ACCEPTANCE; check date and canonical status. | Indexed |
| [`WORKFLOW_CATALOG_100.md`](../../api/agent_platform/benchmarks/WORKFLOW_CATALOG_100.md) | Documentation: WORKFLOW CATALOG 100; check date and canonical status. | Indexed |
| [`local_autonomy_100.json`](../../api/agent_platform/benchmarks/local_autonomy_100.json) | Data/configuration fixture: local autonomy 100; inspect schema and consumers. | Indexed |

## api/agent_platform/evals

Evaluation fixtures and dated historical findings.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`FRONTIER_STRESS_REPORT.md`](../../api/agent_platform/evals/FRONTIER_STRESS_REPORT.md) | Documentation: FRONTIER STRESS REPORT; check date and canonical status. | Indexed |
| [`HOURLY_20261107_ATOMIC_BUDGET_PRIMITIVE.md`](../../api/agent_platform/evals/HOURLY_20261107_ATOMIC_BUDGET_PRIMITIVE.md) | Documentation: HOURLY 20261107 ATOMIC BUDGET PRIMITIVE; check date and canonical status. | Indexed |
| [`HOURLY_20261107_BUILDER_ROUTING.md`](../../api/agent_platform/evals/HOURLY_20261107_BUILDER_ROUTING.md) | Documentation: HOURLY 20261107 BUILDER ROUTING; check date and canonical status. | Indexed |
| [`HOURLY_20261107_FIRST_RUN.md`](../../api/agent_platform/evals/HOURLY_20261107_FIRST_RUN.md) | Documentation: HOURLY 20261107 FIRST RUN; check date and canonical status. | Indexed |
| [`HOURLY_20261107_PARALLEL_BUDGET_GATE.md`](../../api/agent_platform/evals/HOURLY_20261107_PARALLEL_BUDGET_GATE.md) | Documentation: HOURLY 20261107 PARALLEL BUDGET GATE; check date and canonical status. | Indexed |
| [`ORACLE_TRUST_BOUNDARY_FINDING_20261108.md`](../../api/agent_platform/evals/ORACLE_TRUST_BOUNDARY_FINDING_20261108.md) | Documentation: ORACLE TRUST BOUNDARY FINDING 20261108; check date and canonical status. | Indexed |
| [`ROUND1_20261107.md`](../../api/agent_platform/evals/ROUND1_20261107.md) | Documentation: ROUND1 20261107; check date and canonical status. | Indexed |
| [`baseline.json`](../../api/agent_platform/evals/baseline.json) | Data/configuration fixture: baseline; inspect schema and consumers. | Indexed |
| [`frontier_stress_v1.json`](../../api/agent_platform/evals/frontier_stress_v1.json) | Data/configuration fixture: frontier stress v1; inspect schema and consumers. | Indexed |

## api/agent_platform/migrations

SQL migrations for Personal goals/chat, request ledger, MCP and native voice/history. Manual scripts need separate authorization.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`20261121_personal_goal_receipts.sql`](../../api/agent_platform/migrations/20261121_personal_goal_receipts.sql) | SQL named for 20261121 personal goal receipts; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261122_first_party_chat.sql`](../../api/agent_platform/migrations/20261122_first_party_chat.sql) | SQL named for 20261122 first party chat; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261122_mcp_connections.sql`](../../api/agent_platform/migrations/20261122_mcp_connections.sql) | SQL named for 20261122 mcp connections; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261122_personal_mcp_goal_selections.sql`](../../api/agent_platform/migrations/20261122_personal_mcp_goal_selections.sql) | SQL named for 20261122 personal mcp goal selections; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_first_party_request_ledger.sql`](../../api/agent_platform/migrations/20261125_first_party_request_ledger.sql) | SQL named for 20261125 first party request ledger; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_native_mcp_oauth.sql`](../../api/agent_platform/migrations/20261125_native_mcp_oauth.sql) | SQL named for 20261125 native mcp oauth; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_native_voice.sql`](../../api/agent_platform/migrations/20261125_native_voice.sql) | SQL named for 20261125 native voice; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_personal_history_archive_manual.sql`](../../api/agent_platform/migrations/20261125_personal_history_archive_manual.sql) | SQL named for 20261125 personal history archive manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`operly_legacy_history_inventory_manual.sql`](../../api/agent_platform/migrations/operly_legacy_history_inventory_manual.sql) | SQL named for operly legacy history inventory manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`operly_personal_history_export_role_manual.sql`](../../api/agent_platform/migrations/operly_personal_history_export_role_manual.sql) | SQL named for operly personal history export role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`operly_personal_history_inventory_manual.sql`](../../api/agent_platform/migrations/operly_personal_history_inventory_manual.sql) | SQL named for operly personal history inventory manual; inspect statements, transaction requirements and target database before use. | Indexed |

## api/agent_platform/reports

Historical execution evidence and investigations, not a deployment manifest.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`FIVE_FIXES_AND_F08_LIVE_REGRESSION_20261108.md`](../../api/agent_platform/reports/FIVE_FIXES_AND_F08_LIVE_REGRESSION_20261108.md) | Documentation: FIVE FIXES AND F08 LIVE REGRESSION 20261108; check date and canonical status. | Indexed |
| [`LIVE_LONGHORIZON_RESULTS_20261108.md`](../../api/agent_platform/reports/LIVE_LONGHORIZON_RESULTS_20261108.md) | Documentation: LIVE LONGHORIZON RESULTS 20261108; check date and canonical status. | Indexed |
| [`STAGING_TRACING_AND_LOOP_DEBUG_20261108.md`](../../api/agent_platform/reports/STAGING_TRACING_AND_LOOP_DEBUG_20261108.md) | Documentation: STAGING TRACING AND LOOP DEBUG 20261108; check date and canonical status. | Indexed |

## api/identity

First-party identity HTTP handlers, auth/session/token primitives, account migration and SQL schemas.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`MOBILE_OAUTH_RELEASE.md`](../../api/identity/MOBILE_OAUTH_RELEASE.md) | Documentation: MOBILE OAUTH RELEASE; check date and canonical status. | Indexed |
| [`__init__.py`](../../api/identity/__init__.py) | Navigation hint:   init  ; source behavior not independently reviewed. | Indexed |
| [`active_recovery_http.py`](../../api/identity/active_recovery_http.py) | Navigation hint: active recovery http; source behavior not independently reviewed. | Indexed |
| [`authorize_ui.css`](../../api/identity/authorize_ui.css) | Stylesheet: authorize ui; inspect selectors and importing page. | Indexed |
| [`authorize_ui.js`](../../api/identity/authorize_ui.js) | Navigation hint: authorize ui; source behavior not independently reviewed. | Indexed |
| [`browser_authorize.py`](../../api/identity/browser_authorize.py) | Browser authorization and consent UI, same-origin assets and Google sign-in page. | Reviewed |
| [`common_passwords.txt`](../../api/identity/common_passwords.txt) | Navigation hint: common passwords; source behavior not independently reviewed. | Indexed |
| [`consent.py`](../../api/identity/consent.py) | Session-bound single-use consent interaction for the exact registered OAuth request fields. | Reviewed |
| [`exchange.py`](../../api/identity/exchange.py) | Atomic authorization-code and refresh exchange with OIDC nonce; consumes code and creates refresh in one transaction. | Reviewed |
| [`grants.py`](../../api/identity/grants.py) | Server-side authorization-code and S256 PKCE grant validation and redemption. | Reviewed |
| [`http_bridge.py`](../../api/identity/http_bridge.py) | Identity database/gate helpers, POST authorization and token HTTP bridge. | Reviewed |
| [`importer.py`](../../api/identity/importer.py) | Strict authorized staging account/provider snapshot preparation and all-or-nothing import; no API or agent entrypoint. | Reviewed |
| [`issuer_google_ui.js`](../../api/identity/issuer_google_ui.js) | Navigation hint: issuer google ui; source behavior not independently reviewed. | Indexed |
| [`login_http.py`](../../api/identity/login_http.py) | Password login, logout, native profile lookup/update HTTP adapters. | Reviewed |
| [`mobile_provider.py`](../../api/identity/mobile_provider.py) | Native browser-provider start/callback/redeem with PKCE and ticket binding; provider capabilities. | Reviewed |
| [`native_recovery_http.py`](../../api/identity/native_recovery_http.py) | Navigation hint: native recovery http; source behavior not independently reviewed. | Indexed |
| [`native_signup.py`](../../api/identity/native_signup.py) | Explicit verified Google signup, without email-based linking of Operly identities. | Reviewed |
| [`offline_transfer.py`](../../api/identity/offline_transfer.py) | Operator-only sealed encrypted packages across isolated production DB networks; private file handling and migration-role checks. | Reviewed |
| [`password_login.py`](../../api/identity/password_login.py) | Database-backed password login, indistinguishable failures, shared PostgreSQL rate limiting and PBKDF2-to-Argon2 upgrade. | Reviewed |
| [`passwords.py`](../../api/identity/passwords.py) | Pure email normalization, password policy, legacy PBKDF2 compatibility and Argon2id hash/verification. | Reviewed |
| [`pending_proof_http.py`](../../api/identity/pending_proof_http.py) | Navigation hint: pending proof http; source behavior not independently reviewed. | Indexed |
| [`pending_proofs.py`](../../api/identity/pending_proofs.py) | Checks migrated pending identity password or Google proof without granting session or activation. | Reviewed |
| [`pending_reconciliation.py`](../../api/identity/pending_reconciliation.py) | Operator-only read-only source/target reconciliation with keyed full-field snapshot receipts, not just counts. | Reviewed |
| [`production_import.py`](../../api/identity/production_import.py) | Operator-only scoped pending production identity import with independently approved inventory and count validation. | Reviewed |
| [`provider_challenges.py`](../../api/identity/provider_challenges.py) | Creates and consumes one-time browser-bound provider challenge state, binding and nonce. | Reviewed |
| [`provider_http.py`](../../api/identity/provider_http.py) | Browser Google/Discord challenge initiation and completion; explicit Google signup path; verifies state/nonce/binding before session. | Reviewed |
| [`providers.py`](../../api/identity/providers.py) | Validates Google ID tokens and Discord OAuth code exchange, looks up verified provider subject, never merges accounts by email. | Reviewed |
| [`reconciliation.py`](../../api/identity/reconciliation.py) | Fail-closed validation and reconciliation of authorized Operly identity exports; no database mutation or authentication. | Reviewed |
| [`recovery_delta.py`](../../api/identity/recovery_delta.py) | Plans and applies reviewed pending recovery additions; requires source-authority handoff/freeze before writes. | Reviewed |
| [`refresh.py`](../../api/identity/refresh.py) | Opaque hashed single-use refresh tokens, atomic rotation and family replay revocation. | Reviewed |
| [`relying_party_status.py`](../../api/identity/relying_party_status.py) | Navigation hint: relying party status; source behavior not independently reviewed. | Indexed |
| [`router.py`](../../api/identity/router.py) | JWKS and OIDC discovery routes. | Reviewed |
| [`schema_active_recovery_review.sql`](../../api/identity/schema_active_recovery_review.sql) | SQL named for schema active recovery review; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_bootstrap_manual.sql`](../../api/identity/schema_bootstrap_manual.sql) | SQL named for schema bootstrap manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_consent_staging.sql`](../../api/identity/schema_consent_staging.sql) | SQL named for schema consent staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_export_role_manual.sql`](../../api/identity/schema_export_role_manual.sql) | SQL named for schema export role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_first_party_clients_staging.sql`](../../api/identity/schema_first_party_clients_staging.sql) | SQL named for schema first party clients staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_import_activation_review.sql`](../../api/identity/schema_import_activation_review.sql) | SQL named for schema import activation review; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_login_staging.sql`](../../api/identity/schema_login_staging.sql) | SQL named for schema login staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_migration_role_manual.sql`](../../api/identity/schema_migration_role_manual.sql) | SQL named for schema migration role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_mobile_provider_manual.sql`](../../api/identity/schema_mobile_provider_manual.sql) | SQL named for schema mobile provider manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_native_google_signup.sql`](../../api/identity/schema_native_google_signup.sql) | SQL named for schema native google signup; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_native_pending_recovery_review.sql`](../../api/identity/schema_native_pending_recovery_review.sql) | SQL named for schema native pending recovery review; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_oauth_staging.sql`](../../api/identity/schema_oauth_staging.sql) | SQL named for schema oauth staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_provider_challenge_staging.sql`](../../api/identity/schema_provider_challenge_staging.sql) | SQL named for schema provider challenge staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_recovery_sync_role_manual.sql`](../../api/identity/schema_recovery_sync_role_manual.sql) | SQL named for schema recovery sync role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_role_manual.sql`](../../api/identity/schema_role_manual.sql) | SQL named for schema role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_sessions_staging.sql`](../../api/identity/schema_sessions_staging.sql) | SQL named for schema sessions staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`schema_staging.sql`](../../api/identity/schema_staging.sql) | SQL named for schema staging; inspect statements, transaction requirements and target database before use. | Indexed |
| [`sessions.py`](../../api/identity/sessions.py) | Opaque host-only browser sessions, active-account checks, CSRF validation and revocation. | Reviewed |
| [`source_inventory_manual.sql`](../../api/identity/source_inventory_manual.sql) | SQL named for source inventory manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`source_recovery_inventory_manual.sql`](../../api/identity/source_recovery_inventory_manual.sql) | SQL named for source recovery inventory manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`tokens.py`](../../api/identity/tokens.py) | RS256 SigningIdentity, PKCE helpers and issuer/token signing primitives; private signing keys never reach agent context. | Reviewed |

## api/personal_core

Earlier feature-gated Personal API foundation; separate from first-party agent chat.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`CAPABILITIES.md`](../../api/personal_core/CAPABILITIES.md) | Documentation: CAPABILITIES; check date and canonical status. | Indexed |
| [`README.md`](../../api/personal_core/README.md) | Documentation: README; check date and canonical status. | Indexed |
| [`__init__.py`](../../api/personal_core/__init__.py) | Navigation hint:   init  ; source behavior not independently reviewed. | Indexed |
| [`app.py`](../../api/personal_core/app.py) | Navigation hint: app; source behavior not independently reviewed. | Indexed |
| [`budget.py`](../../api/personal_core/budget.py) | Navigation hint: budget; source behavior not independently reviewed. | Indexed |
| [`identity.py`](../../api/personal_core/identity.py) | Navigation hint: identity; source behavior not independently reviewed. | Indexed |
| [`models.py`](../../api/personal_core/models.py) | Navigation hint: models; source behavior not independently reviewed. | Indexed |

## api/tests

Backend contracts, regressions, PostgreSQL integration, and explicitly gated live tests.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`gateway.test.mjs`](../../api/tests/gateway.test.mjs) | Test target: gateway.test; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_agent_evaluation.py`](../../api/tests/test_agent_evaluation.py) | Test target: agent evaluation; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_agent_gateway_protocol.py`](../../api/tests/test_agent_gateway_protocol.py) | Test target: agent gateway protocol; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_agent_platform_contract.py`](../../api/tests/test_agent_platform_contract.py) | Test target: agent platform contract; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_agent_stack_integration.py`](../../api/tests/test_agent_stack_integration.py) | Test target: agent stack integration; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_agent_web_monitor.py`](../../api/tests/test_agent_web_monitor.py) | Test target: agent web monitor; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_artifact_evidence.py`](../../api/tests/test_artifact_evidence.py) | Test target: artifact evidence; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_budget_postgres_integration.py`](../../api/tests/test_budget_postgres_integration.py) | Test target: budget postgres integration; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_budget_reservations.py`](../../api/tests/test_budget_reservations.py) | Test target: budget reservations; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_capability_hub.py`](../../api/tests/test_capability_hub.py) | Test target: capability hub; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_fastapi_gateway.py`](../../api/tests/test_fastapi_gateway.py) | Test target: fastapi gateway; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_agent_stream.py`](../../api/tests/test_first_party_agent_stream.py) | Test target: first party agent stream; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_chat.py`](../../api/tests/test_first_party_chat.py) | Test target: first party chat; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_goal_management.py`](../../api/tests/test_first_party_goal_management.py) | Test target: first party goal management; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_request_ledger.py`](../../api/tests/test_first_party_request_ledger.py) | Test target: first party request ledger; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_request_ledger_postgres.py`](../../api/tests/test_first_party_request_ledger_postgres.py) | Test target: first party request ledger postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_voice.py`](../../api/tests/test_first_party_voice.py) | Test target: first party voice; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_frontier_batch.py`](../../api/tests/test_frontier_batch.py) | Test target: frontier batch; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_frontier_live_trust_boundary.py`](../../api/tests/test_frontier_live_trust_boundary.py) | Test target: frontier live trust boundary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_frontier_stress.py`](../../api/tests/test_frontier_stress.py) | Test target: frontier stress; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_gateway_parent_budget.py`](../../api/tests/test_gateway_parent_budget.py) | Test target: gateway parent budget; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_harness_product_surface.py`](../../api/tests/test_harness_product_surface.py) | Test target: harness product surface; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_harness_tool_acceptance.py`](../../api/tests/test_harness_tool_acceptance.py) | Test target: harness tool acceptance; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_harness_v2.py`](../../api/tests/test_harness_v2.py) | Test target: harness v2; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_activation_postgres.py`](../../api/tests/test_identity_activation_postgres.py) | Test target: identity activation postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_bootstrap_postgres.py`](../../api/tests/test_identity_bootstrap_postgres.py) | Test target: identity bootstrap postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_browser_authorize.py`](../../api/tests/test_identity_browser_authorize.py) | Test target: identity browser authorize; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_browser_sessions.py`](../../api/tests/test_identity_browser_sessions.py) | Test target: identity browser sessions; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_consent.py`](../../api/tests/test_identity_consent.py) | Test target: identity consent; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_first_party_registry.py`](../../api/tests/test_identity_first_party_registry.py) | Test target: identity first party registry; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_http_bridge.py`](../../api/tests/test_identity_http_bridge.py) | Test target: identity http bridge; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_importer.py`](../../api/tests/test_identity_importer.py) | Test target: identity importer; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_jwks.py`](../../api/tests/test_identity_jwks.py) | Test target: identity jwks; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_mobile_provider.py`](../../api/tests/test_identity_mobile_provider.py) | Test target: identity mobile provider; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_native_recovery_http.py`](../../api/tests/test_identity_native_recovery_http.py) | Test target: identity native recovery http; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_native_recovery_postgres.py`](../../api/tests/test_identity_native_recovery_postgres.py) | Test target: identity native recovery postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_native_signup.py`](../../api/tests/test_identity_native_signup.py) | Test target: identity native signup; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_oauth_grants.py`](../../api/tests/test_identity_oauth_grants.py) | Test target: identity oauth grants; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_offline_transfer.py`](../../api/tests/test_identity_offline_transfer.py) | Test target: identity offline transfer; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_oidc_exchange.py`](../../api/tests/test_identity_oidc_exchange.py) | Test target: identity oidc exchange; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_password_compat.py`](../../api/tests/test_identity_password_compat.py) | Test target: identity password compat; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_password_login.py`](../../api/tests/test_identity_password_login.py) | Test target: identity password login; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_pending_proof_http.py`](../../api/tests/test_identity_pending_proof_http.py) | Test target: identity pending proof http; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_pending_reconciliation.py`](../../api/tests/test_identity_pending_reconciliation.py) | Test target: identity pending reconciliation; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_personal_history_http.py`](../../api/tests/test_identity_personal_history_http.py) | Test target: identity personal history http; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_personal_history_import.py`](../../api/tests/test_identity_personal_history_import.py) | Test target: identity personal history import; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_postgres_integration.py`](../../api/tests/test_identity_postgres_integration.py) | Test target: identity postgres integration; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_production_import.py`](../../api/tests/test_identity_production_import.py) | Test target: identity production import; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_provider_challenges.py`](../../api/tests/test_identity_provider_challenges.py) | Test target: identity provider challenges; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_provider_http.py`](../../api/tests/test_identity_provider_http.py) | Test target: identity provider http; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_providers.py`](../../api/tests/test_identity_providers.py) | Test target: identity providers; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_reconciliation.py`](../../api/tests/test_identity_reconciliation.py) | Test target: identity reconciliation; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_recovery_delta.py`](../../api/tests/test_identity_recovery_delta.py) | Test target: identity recovery delta; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_refresh.py`](../../api/tests/test_identity_refresh.py) | Test target: identity refresh; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_relying_party_status.py`](../../api/tests/test_identity_relying_party_status.py) | Test target: identity relying party status; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_role_postgres.py`](../../api/tests/test_identity_role_postgres.py) | Test target: identity role postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_token_boundary.py`](../../api/tests/test_identity_token_boundary.py) | Test target: identity token boundary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_key_budget.py`](../../api/tests/test_key_budget.py) | Test target: key budget; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_live_operly_mcp_smoke.py`](../../api/tests/test_live_operly_mcp_smoke.py) | Test target: live operly mcp smoke; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_live_platform_tool_smoke.py`](../../api/tests/test_live_platform_tool_smoke.py) | Test target: live platform tool smoke; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_local_autonomy_100.py`](../../api/tests/test_local_autonomy_100.py) | Test target: local autonomy 100; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_local_autonomy_100_postgres.py`](../../api/tests/test_local_autonomy_100_postgres.py) | Test target: local autonomy 100 postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_local_monitor.py`](../../api/tests/test_local_monitor.py) | Test target: local monitor; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_local_monitor_postgres.py`](../../api/tests/test_local_monitor_postgres.py) | Test target: local monitor postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_local_monitor_receipt_integrity.py`](../../api/tests/test_local_monitor_receipt_integrity.py) | Test target: local monitor receipt integrity; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_long_horizon_monitoring_acceptance.py`](../../api/tests/test_long_horizon_monitoring_acceptance.py) | Test target: long horizon monitoring acceptance; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mcp_adapter.py`](../../api/tests/test_mcp_adapter.py) | Test target: mcp adapter; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mcp_broker.py`](../../api/tests/test_mcp_broker.py) | Test target: mcp broker; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mcp_connections.py`](../../api/tests/test_mcp_connections.py) | Test target: mcp connections; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mcp_connections_postgres.py`](../../api/tests/test_mcp_connections_postgres.py) | Test target: mcp connections postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mcp_schedule_selection.py`](../../api/tests/test_mcp_schedule_selection.py) | Test target: mcp schedule selection; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_memory_database_reuse.py`](../../api/tests/test_memory_database_reuse.py) | Test target: memory database reuse; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_model_capabilities.py`](../../api/tests/test_model_capabilities.py) | Test target: model capabilities; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_native_canary.py`](../../api/tests/test_native_canary.py) | Test target: native canary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_native_canary_postgres.py`](../../api/tests/test_native_canary_postgres.py) | Test target: native canary postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_openrouter_spend_guard.py`](../../api/tests/test_openrouter_spend_guard.py) | Test target: openrouter spend guard; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_operly_business_canary.py`](../../api/tests/test_operly_business_canary.py) | Test target: operly business canary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_operly_mcp_client.py`](../../api/tests/test_operly_mcp_client.py) | Test target: operly mcp client; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_operly_workflow_dispatch.py`](../../api/tests/test_operly_workflow_dispatch.py) | Test target: operly workflow dispatch; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_ops_benchmark.py`](../../api/tests/test_ops_benchmark.py) | Test target: ops benchmark; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_orchestration.py`](../../api/tests/test_orchestration.py) | Test target: orchestration; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_persistent_graph.py`](../../api/tests/test_persistent_graph.py) | Test target: persistent graph; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_persistent_graph_postgres.py`](../../api/tests/test_persistent_graph_postgres.py) | Test target: persistent graph postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_persistent_tool_canary.py`](../../api/tests/test_persistent_tool_canary.py) | Test target: persistent tool canary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_persistent_tool_canary_postgres.py`](../../api/tests/test_persistent_tool_canary_postgres.py) | Test target: persistent tool canary postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_core.py`](../../api/tests/test_personal_core.py) | Test target: personal core; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_goal_tools.py`](../../api/tests/test_personal_goal_tools.py) | Test target: personal goal tools; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_mcp_bridge.py`](../../api/tests/test_personal_mcp_bridge.py) | Test target: personal mcp bridge; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_mcp_checkpoint_postgres.py`](../../api/tests/test_personal_mcp_checkpoint_postgres.py) | Test target: personal mcp checkpoint postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_mcp_wake.py`](../../api/tests/test_personal_mcp_wake.py) | Test target: personal mcp wake; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_mcp_wake_postgres.py`](../../api/tests/test_personal_mcp_wake_postgres.py) | Test target: personal mcp wake postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_quota_checkpoint.py`](../../api/tests/test_personal_quota_checkpoint.py) | Test target: personal quota checkpoint; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_progress_guard.py`](../../api/tests/test_progress_guard.py) | Test target: progress guard; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_provider_gateway.py`](../../api/tests/test_provider_gateway.py) | Test target: provider gateway; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_provider_pacing.py`](../../api/tests/test_provider_pacing.py) | Test target: provider pacing; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_sandbox_math.py`](../../api/tests/test_sandbox_math.py) | Test target: sandbox math; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_scientific_oracles.py`](../../api/tests/test_scientific_oracles.py) | Test target: scientific oracles; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_shared_hourly_quota.py`](../../api/tests/test_shared_hourly_quota.py) | Test target: shared hourly quota; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_staging_lab.py`](../../api/tests/test_staging_lab.py) | Test target: staging lab; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_subjective_monitoring.py`](../../api/tests/test_subjective_monitoring.py) | Test target: subjective monitoring; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_synthetic_business_cron.py`](../../api/tests/test_synthetic_business_cron.py) | Test target: synthetic business cron; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_universal_mcp_catalog.py`](../../api/tests/test_universal_mcp_catalog.py) | Test target: universal mcp catalog; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_usage_audit.py`](../../api/tests/test_usage_audit.py) | Test target: usage audit; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_workflow_catalog_100.py`](../../api/tests/test_workflow_catalog_100.py) | Test target: workflow catalog 100; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_workspace_bridge.py`](../../api/tests/test_workspace_bridge.py) | Test target: workspace bridge; inspect assertions and fixtures for the exact contract. | Indexed |

## docs

Canonical architecture, ownership, identity phases, migration and security documentation.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`MERGE_READINESS_2026-11-19.md`](../../docs/MERGE_READINESS_2026-11-19.md) | Documentation: MERGE READINESS 2026 11 19; check date and canonical status. | Indexed |
| [`identity-import-checkpoint-2026-11-25.md`](../../docs/identity-import-checkpoint-2026-11-25.md) | Documentation: identity import checkpoint 2026 11 25; check date and canonical status. | Indexed |
| [`identity-migration-plan.md`](../../docs/identity-migration-plan.md) | Documentation: identity migration plan; check date and canonical status. | Indexed |
| [`identity-offline-transfer.md`](../../docs/identity-offline-transfer.md) | Documentation: identity offline transfer; check date and canonical status. | Indexed |
| [`identity-phase-b.md`](../../docs/identity-phase-b.md) | Documentation: identity phase b; check date and canonical status. | Indexed |
| [`identity-phase-d.md`](../../docs/identity-phase-d.md) | Documentation: identity phase d; check date and canonical status. | Indexed |
| [`identity-phase-e.md`](../../docs/identity-phase-e.md) | Documentation: identity phase e; check date and canonical status. | Indexed |
| [`identity-phase-f.md`](../../docs/identity-phase-f.md) | Documentation: identity phase f; check date and canonical status. | Indexed |
| [`identity-phase-g.md`](../../docs/identity-phase-g.md) | Documentation: identity phase g; check date and canonical status. | Indexed |
| [`identity-phase-h.md`](../../docs/identity-phase-h.md) | Documentation: identity phase h; check date and canonical status. | Indexed |
| [`identity-phase-i.md`](../../docs/identity-phase-i.md) | Documentation: identity phase i; check date and canonical status. | Indexed |
| [`identity-phase-j.md`](../../docs/identity-phase-j.md) | Documentation: identity phase j; check date and canonical status. | Indexed |
| [`identity-phase-k.md`](../../docs/identity-phase-k.md) | Documentation: identity phase k; check date and canonical status. | Indexed |
| [`identity-production-pending-import.md`](../../docs/identity-production-pending-import.md) | Documentation: identity production pending import; check date and canonical status. | Indexed |
| [`one-login-operational-gates.md`](../../docs/one-login-operational-gates.md) | Documentation: one login operational gates; check date and canonical status. | Indexed |
| [`one-login-web.md`](../../docs/one-login-web.md) | Documentation: one login web; check date and canonical status. | Indexed |
| [`operly-optional-oauth-mcp.md`](../../docs/operly-optional-oauth-mcp.md) | Documentation: operly optional oauth mcp; check date and canonical status. | Indexed |
| [`personal-memory-consolidation.md`](../../docs/personal-memory-consolidation.md) | Documentation: personal memory consolidation; check date and canonical status. | Indexed |
| [`platform-ownership.md`](../../docs/platform-ownership.md) | Documentation: platform ownership; check date and canonical status. | Indexed |
| [`railway-secret-ownership-cutover.md`](../../docs/railway-secret-ownership-cutover.md) | Documentation: railway secret ownership cutover; check date and canonical status. | Indexed |
| [`security-baseline.md`](../../docs/security-baseline.md) | Documentation: security baseline; check date and canonical status. | Indexed |
| [`universal-harness-v4.md`](../../docs/universal-harness-v4.md) | Documentation: universal harness v4; check date and canonical status. | Indexed |

## engineering-reports

Dated engineering evidence, not an authoritative current state.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`2026-11-07-durable-unknown-cost-holds.md`](../../engineering-reports/2026-11-07-durable-unknown-cost-holds.md) | Documentation: 2026 11 07 durable unknown cost holds; check date and canonical status. | Indexed |
| [`2026-11-07-postgres-budget-concurrency.md`](../../engineering-reports/2026-11-07-postgres-budget-concurrency.md) | Documentation: 2026 11 07 postgres budget concurrency; check date and canonical status. | Indexed |
| [`2026-11-07-tool-call-replay-gateway.md`](../../engineering-reports/2026-11-07-tool-call-replay-gateway.md) | Documentation: 2026 11 07 tool call replay gateway; check date and canonical status. | Indexed |

## evals/real_world_intents

Real-world objective cases and acceptance definitions.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`CASES.md`](../../evals/real_world_intents/CASES.md) | Documentation: CASES; check date and canonical status. | Indexed |
| [`README.md`](../../evals/real_world_intents/README.md) | Documentation: README; check date and canonical status. | Indexed |
| [`cases.json`](../../evals/real_world_intents/cases.json) | Data/configuration fixture: cases; inspect schema and consumers. | Indexed |

## identity

Identity contract and schema foundation; implementation is under api/identity.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`README.md`](../../identity/README.md) | Documentation: README; check date and canonical status. | Indexed |

## identity/contracts

Machine-readable identity contract.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`oidc-v1.json`](../../identity/contracts/oidc-v1.json) | Data/configuration fixture: oidc v1; inspect schema and consumers. | Indexed |

## identity/migrations

Initial identity schema; compare with API identity schema variants.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`0001_identity_schema.sql`](../../identity/migrations/0001_identity_schema.sql) | SQL named for 0001 identity schema; inspect statements, transaction requirements and target database before use. | Indexed |

## legacy

Retirement boundary; no active legacy assistant should be restored.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`README.md`](../../legacy/README.md) | Documentation: README; check date and canonical status. | Indexed |

## scripts

Repository maintenance and validation scripts.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`check_no_secrets.py`](../../scripts/check_no_secrets.py) | Navigation hint: check no secrets; source behavior not independently reviewed. | Indexed |

## src/dragonzpyder

Thin Python client package, not the production agent runtime.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`__init__.py`](../../src/dragonzpyder/__init__.py) | Navigation hint:   init  ; source behavior not independently reviewed. | Indexed |
| [`cli.py`](../../src/dragonzpyder/cli.py) | Navigation hint: cli; source behavior not independently reviewed. | Indexed |
| [`client.py`](../../src/dragonzpyder/client.py) | Navigation hint: client; source behavior not independently reviewed. | Indexed |
| [`config.py`](../../src/dragonzpyder/config.py) | Navigation hint: config; source behavior not independently reviewed. | Indexed |
| [`tasks.py`](../../src/dragonzpyder/tasks.py) | Navigation hint: tasks; source behavior not independently reviewed. | Indexed |

## tests

Thin client and package/UX contract tests.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`test_client.py`](../../tests/test_client.py) | Test target: client; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_config.py`](../../tests/test_config.py) | Test target: config; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_p6_approval_ux.py`](../../tests/test_p6_approval_ux.py) | Test target: p6 approval ux; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_p6_send_flow.py`](../../tests/test_p6_send_flow.py) | Test target: p6 send flow; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_p8_waiting_reply_ux.py`](../../tests/test_p8_waiting_reply_ux.py) | Test target: p8 waiting reply ux; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_package_boundary.py`](../../tests/test_package_boundary.py) | Test target: package boundary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_tasks.py`](../../tests/test_tasks.py) | Test target: tasks; inspect assertions and fixtures for the exact contract. | Indexed |

## web

FastAPI web gateway, styles and compatibility JavaScript; React source in frontend.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`Dockerfile`](../../web/Dockerfile) | Node 22 Vite build/test stage followed by non-root Python 3.12 FastAPI runtime. | Reviewed |
| [`Procfile`](../../web/Procfile) | Navigation hint: Procfile; source behavior not independently reviewed. | Indexed |
| [`README.md`](../../web/README.md) | Documentation: README; check date and canonical status. | Indexed |
| [`account.css`](../../web/account.css) | Stylesheet: account; inspect selectors and importing page. | Indexed |
| [`account.js`](../../web/account.js) | Navigation hint: account; source behavior not independently reviewed. | Indexed |
| [`app.css`](../../web/app.css) | Stylesheet: app; inspect selectors and importing page. | Indexed |
| [`app.js`](../../web/app.js) | Transitional Personal chat controller: sessions, conversations, request sending, approval UI and runtime status. | Reviewed |
| [`chat.html`](../../web/chat.html) | Navigation hint: chat; source behavior not independently reviewed. | Indexed |
| [`companion.js`](../../web/companion.js) | Navigation hint: companion; source behavior not independently reviewed. | Indexed |
| [`dictation.js`](../../web/dictation.js) | Navigation hint: dictation; source behavior not independently reviewed. | Indexed |
| [`image-progress.mjs`](../../web/image-progress.mjs) | Navigation hint: image progress; source behavior not independently reviewed. | Indexed |
| [`internal-inference.mjs`](../../web/internal-inference.mjs) | Navigation hint: internal inference; source behavior not independently reviewed. | Indexed |
| [`main.py`](../../web/main.py) | FastAPI compiled-page server, native API and compatibility proxy dispatch, admin protection and security headers. | Reviewed |
| [`mesh-picker.js`](../../web/mesh-picker.js) | Navigation hint: mesh picker; source behavior not independently reviewed. | Indexed |
| [`mesh-server.mjs`](../../web/mesh-server.mjs) | Navigation hint: mesh server; source behavior not independently reviewed. | Indexed |
| [`mesh.css`](../../web/mesh.css) | Stylesheet: mesh; inspect selectors and importing page. | Indexed |
| [`mesh.js`](../../web/mesh.js) | Navigation hint: mesh; source behavior not independently reviewed. | Indexed |
| [`package.json`](../../web/package.json) | Data/configuration fixture: package; inspect schema and consumers. | Indexed |
| [`privacy.html`](../../web/privacy.html) | Navigation hint: privacy; source behavior not independently reviewed. | Indexed |
| [`realtime-server.mjs`](../../web/realtime-server.mjs) | Navigation hint: realtime server; source behavior not independently reviewed. | Indexed |
| [`requirements.txt`](../../web/requirements.txt) | Navigation hint: requirements; source behavior not independently reviewed. | Indexed |
| [`robots.txt`](../../web/robots.txt) | Navigation hint: robots; source behavior not independently reviewed. | Indexed |
| [`script.js`](../../web/script.js) | Navigation hint: script; source behavior not independently reviewed. | Indexed |
| [`server.mjs`](../../web/server.mjs) | Navigation hint: server; source behavior not independently reviewed. | Indexed |
| [`sitemap.xml`](../../web/sitemap.xml) | Navigation hint: sitemap; source behavior not independently reviewed. | Indexed |
| [`terms.html`](../../web/terms.html) | Navigation hint: terms; source behavior not independently reviewed. | Indexed |
| [`ui-v1.css`](../../web/ui-v1.css) | Stylesheet: ui v1; inspect selectors and importing page. | Indexed |
| [`workspace.css`](../../web/workspace.css) | Stylesheet: workspace; inspect selectors and importing page. | Indexed |

## web/backend

Web backend handlers for mesh, voice, chat demo and security.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`__init__.py`](../../web/backend/__init__.py) | Navigation hint:   init  ; source behavior not independently reviewed. | Indexed |
| [`chat_demo.py`](../../web/backend/chat_demo.py) | Password-gated multimodal Chat Lab: session, request limits, attachment processing and central inference calls. | Reviewed |
| [`mesh.py`](../../web/backend/mesh.py) | Personal-only model catalog/chat, attachment parsing and gated image/audio/video operations; per-process quotas are not financial controls. | Reviewed |
| [`security.py`](../../web/backend/security.py) | Shared same-origin, CSRF and Personal session checks for compatibility Mesh and realtime voice. | Reviewed |
| [`voice.py`](../../web/backend/voice.py) | Compatibility WebRTC SDP exchange using server-side Personal authorization and CSRF checks. | Reviewed |

## web/backend/static

Chat demo static assets; not canonical React templates.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`app.css`](../../web/backend/static/app.css) | Stylesheet: app; inspect selectors and importing page. | Indexed |
| [`app.js`](../../web/backend/static/app.js) | Navigation hint: app; source behavior not independently reviewed. | Indexed |
| [`index.html`](../../web/backend/static/index.html) | Navigation hint: index; source behavior not independently reviewed. | Indexed |

## web/frontend

React/Vite application, build/prerender and Playwright tests.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`PROTOTYPE-REVIEW.md`](../../web/frontend/PROTOTYPE-REVIEW.md) | Documentation: PROTOTYPE REVIEW; check date and canonical status. | Indexed |
| [`README.md`](../../web/frontend/README.md) | Documentation: README; check date and canonical status. | Indexed |
| [`UI-1-RELEASE.md`](../../web/frontend/UI-1-RELEASE.md) | Documentation: UI 1 RELEASE; check date and canonical status. | Indexed |
| [`account.html`](../../web/frontend/account.html) | Navigation hint: account; source behavior not independently reviewed. | Indexed |
| [`admin.html`](../../web/frontend/admin.html) | Navigation hint: admin; source behavior not independently reviewed. | Indexed |
| [`app.html`](../../web/frontend/app.html) | Navigation hint: app; source behavior not independently reviewed. | Indexed |
| [`index.html`](../../web/frontend/index.html) | Navigation hint: index; source behavior not independently reviewed. | Indexed |
| [`package.json`](../../web/frontend/package.json) | Data/configuration fixture: package; inspect schema and consumers. | Indexed |
| [`playwright.config.mjs`](../../web/frontend/playwright.config.mjs) | Navigation hint: playwright.config; source behavior not independently reviewed. | Indexed |
| [`vite.config.js`](../../web/frontend/vite.config.js) | Navigation hint: vite.config; source behavior not independently reviewed. | Indexed |

## web/frontend/scripts

Frontend build validation, prerender and desktop/markdown checks.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`check-build.mjs`](../../web/frontend/scripts/check-build.mjs) | Navigation hint: check build; source behavior not independently reviewed. | Indexed |
| [`prepare-desktop.mjs`](../../web/frontend/scripts/prepare-desktop.mjs) | Navigation hint: prepare desktop; source behavior not independently reviewed. | Indexed |
| [`prerender.mjs`](../../web/frontend/scripts/prerender.mjs) | Navigation hint: prerender; source behavior not independently reviewed. | Indexed |
| [`test-desktop.mjs`](../../web/frontend/scripts/test-desktop.mjs) | Navigation hint: test desktop; source behavior not independently reviewed. | Indexed |
| [`test-markdown.mjs`](../../web/frontend/scripts/test-markdown.mjs) | Navigation hint: test markdown; source behavior not independently reviewed. | Indexed |

## web/frontend/src

React source, UI components, runtime context, markdown and voice renderer.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`AccountTemplate.jsx`](../../web/frontend/src/AccountTemplate.jsx) | Navigation hint: AccountTemplate; source behavior not independently reviewed. | Indexed |
| [`HomeTemplate.jsx`](../../web/frontend/src/HomeTemplate.jsx) | Navigation hint: HomeTemplate; source behavior not independently reviewed. | Indexed |
| [`NativeMcpCenter.jsx`](../../web/frontend/src/NativeMcpCenter.jsx) | React first-party OAuth MCP connection UI; CSRF-protected requests and opaque selected aliases, never bearer credentials. | Reviewed |
| [`PersonalTemplate.jsx`](../../web/frontend/src/PersonalTemplate.jsx) | Navigation hint: PersonalTemplate; source behavior not independently reviewed. | Indexed |
| [`VoiceOrb.jsx`](../../web/frontend/src/VoiceOrb.jsx) | React-owned voice interface/lifecycle and artwork renderer integration; visual canvas does not request microphone itself. | Reviewed |
| [`WorkspaceCenter.jsx`](../../web/frontend/src/WorkspaceCenter.jsx) | React account-scoped workspace center and same-origin API requests; includes native MCP UI. | Reviewed |
| [`WorkspaceControls.jsx`](../../web/frontend/src/WorkspaceControls.jsx) | Accessible modal focus and progressive-disclosure chat controls, command palette, capture/add menus and desktop install; delegates to existing adapters. | Reviewed |
| [`admin.css`](../../web/frontend/src/admin.css) | Stylesheet: admin; inspect selectors and importing page. | Indexed |
| [`admin.jsx`](../../web/frontend/src/admin.jsx) | Navigation hint: admin; source behavior not independently reviewed. | Indexed |
| [`main.jsx`](../../web/frontend/src/main.jsx) | React mount/hydrate entrypoint selecting page by route. | Reviewed |
| [`markdown.js`](../../web/frontend/src/markdown.js) | Navigation hint: markdown; source behavior not independently reviewed. | Indexed |
| [`pages.jsx`](../../web/frontend/src/pages.jsx) | React page selection and compatibility-adapter orchestration. | Reviewed |
| [`runtime.jsx`](../../web/frontend/src/runtime.jsx) | Navigation hint: runtime; source behavior not independently reviewed. | Indexed |
| [`voice-canvas-renderer.js`](../../web/frontend/src/voice-canvas-renderer.js) | Navigation hint: voice canvas renderer; source behavior not independently reviewed. | Indexed |
| [`voice-orb.css`](../../web/frontend/src/voice-orb.css) | Stylesheet: voice orb; inspect selectors and importing page. | Indexed |
| [`workspace-center.css`](../../web/frontend/src/workspace-center.css) | Stylesheet: workspace center; inspect selectors and importing page. | Indexed |

## web/frontend/tests

Browser-level frontend regression specs.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`chat-editorial.spec.js`](../../web/frontend/tests/chat-editorial.spec.js) | Test target: chat editorial.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`native-routing.spec.js`](../../web/frontend/tests/native-routing.spec.js) | Test target: native routing.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`sso-login-entry.spec.js`](../../web/frontend/tests/sso-login-entry.spec.js) | Test target: sso login entry.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`ui.spec.js`](../../web/frontend/tests/ui.spec.js) | Test target: ui.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`voice-browser-fallback.spec.js`](../../web/frontend/tests/voice-browser-fallback.spec.js) | Test target: voice browser fallback.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`voice-orb.spec.js`](../../web/frontend/tests/voice-orb.spec.js) | Test target: voice orb.spec; inspect assertions and fixtures for the exact contract. | Indexed |
| [`workspace-center.spec.js`](../../web/frontend/tests/workspace-center.spec.js) | Test target: workspace center.spec; inspect assertions and fixtures for the exact contract. | Indexed |

## web/tests

Web proxy, security, mesh and compatibility backend tests.

| File | Purpose / navigation | Evidence |
| --- | --- | --- |
| [`image-progress.test.mjs`](../../web/tests/image-progress.test.mjs) | Test target: image progress.test; inspect assertions and fixtures for the exact contract. | Indexed |
| [`internal-inference.test.mjs`](../../web/tests/internal-inference.test.mjs) | Test target: internal inference.test; inspect assertions and fixtures for the exact contract. | Indexed |
| [`mesh.test.mjs`](../../web/tests/mesh.test.mjs) | Test target: mesh.test; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_admin_protection.py`](../../web/tests/test_admin_protection.py) | Test target: admin protection; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_chat_demo.py`](../../web/tests/test_chat_demo.py) | Test target: chat demo; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_fastapi_web.py`](../../web/tests/test_fastapi_web.py) | Test target: fastapi web; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mesh_attachments.py`](../../web/tests/test_mesh_attachments.py) | Test target: mesh attachments; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mesh_image_generation.py`](../../web/tests/test_mesh_image_generation.py) | Test target: mesh image generation; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mesh_model_catalogue.py`](../../web/tests/test_mesh_model_catalogue.py) | Test target: mesh model catalogue; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_native_first_party_proxy.py`](../../web/tests/test_native_first_party_proxy.py) | Test target: native first party proxy; inspect assertions and fixtures for the exact contract. | Indexed |

## Documentation infrastructure introduced after the baseline

These paths are additional to the original 427 tracked files; the generated index enumerates the exact checkout rather than relying on this baseline.

- [`.github/README.md`](../../.github/README.md) — Local directory guide.
- [`.github/workflows/README.md`](../../.github/workflows/README.md) — Local directory guide.
- [`.github/workflows/codebase-docs.yml`](../../.github/workflows/codebase-docs.yml) — Documentation CI workflow.
- [`CODEBASE.md`](../../CODEBASE.md) — Codebase navigation documentation.
- [`api/README.md`](../../api/README.md) — Local directory guide.
- [`api/agent_platform/CODE_MAP.md`](../../api/agent_platform/CODE_MAP.md) — Local directory guide.
- [`api/agent_platform/benchmarks/README.md`](../../api/agent_platform/benchmarks/README.md) — Local directory guide.
- [`api/agent_platform/evals/README.md`](../../api/agent_platform/evals/README.md) — Local directory guide.
- [`api/agent_platform/migrations/README.md`](../../api/agent_platform/migrations/README.md) — Local directory guide.
- [`api/agent_platform/reports/README.md`](../../api/agent_platform/reports/README.md) — Local directory guide.
- [`api/identity/README.md`](../../api/identity/README.md) — Local directory guide.
- [`api/personal_core/CODE_MAP.md`](../../api/personal_core/CODE_MAP.md) — Local directory guide.
- [`api/tests/README.md`](../../api/tests/README.md) — Local directory guide.
- [`docs/README.md`](../../docs/README.md) — Local directory guide.
- [`docs/codebase/CHANGES.md`](../../docs/codebase/CHANGES.md) — Codebase navigation documentation.
- [`docs/codebase/FILE_INDEX.md`](../../docs/codebase/FILE_INDEX.md) — Codebase navigation documentation.
- [`docs/codebase/IMPLEMENTATION.md`](../../docs/codebase/IMPLEMENTATION.md) — Codebase navigation documentation.
- [`docs/codebase/README.md`](../../docs/codebase/README.md) — Local directory guide.
- [`engineering-reports/README.md`](../../engineering-reports/README.md) — Local directory guide.
- [`evals/README.md`](../../evals/README.md) — Local directory guide.
- [`evals/real_world_intents/CODE_MAP.md`](../../evals/real_world_intents/CODE_MAP.md) — Local directory guide.
- [`identity/CODE_MAP.md`](../../identity/CODE_MAP.md) — Local directory guide.
- [`identity/contracts/README.md`](../../identity/contracts/README.md) — Local directory guide.
- [`identity/migrations/README.md`](../../identity/migrations/README.md) — Local directory guide.
- [`legacy/CODE_MAP.md`](../../legacy/CODE_MAP.md) — Local directory guide.
- [`scripts/README.md`](../../scripts/README.md) — Local directory guide.
- [`scripts/build_codebase_index.py`](../../scripts/build_codebase_index.py) — Documentation generation, enforcement or offline fixtures.
- [`scripts/check_codebase_docs.py`](../../scripts/check_codebase_docs.py) — Documentation generation, enforcement or offline fixtures.
- [`src/README.md`](../../src/README.md) — Local directory guide.
- [`src/dragonzpyder/README.md`](../../src/dragonzpyder/README.md) — Local directory guide.
- [`tests/README.md`](../../tests/README.md) — Local directory guide.
- [`tests/test_codebase_documentation.py`](../../tests/test_codebase_documentation.py) — Documentation generation, enforcement or offline fixtures.
- [`web/CODE_MAP.md`](../../web/CODE_MAP.md) — Local directory guide.
- [`web/backend/README.md`](../../web/backend/README.md) — Local directory guide.
- [`web/backend/static/README.md`](../../web/backend/static/README.md) — Local directory guide.
- [`web/frontend/CODE_MAP.md`](../../web/frontend/CODE_MAP.md) — Local directory guide.
- [`web/frontend/scripts/README.md`](../../web/frontend/scripts/README.md) — Local directory guide.
- [`web/frontend/src/README.md`](../../web/frontend/src/README.md) — Local directory guide.
- [`web/frontend/tests/README.md`](../../web/frontend/tests/README.md) — Local directory guide.
- [`web/tests/README.md`](../../web/tests/README.md) — Local directory guide.

## Inventory synchronization — V2 and Android additions

These entries reconcile paths added after the documented baseline; Indexed descriptions are navigation hints, not behavior certification.

- [`.github/workflows/android-apk.yml`](../../.github/workflows/android-apk.yml) — Indexed; inspect source or directory guide.
- [`.github/workflows/android-benchmark.yml`](../../.github/workflows/android-benchmark.yml) — Indexed; inspect source or directory guide.
- [`.github/workflows/android-release.yml`](../../.github/workflows/android-release.yml) — Indexed; inspect source or directory guide.
- [`android/.gitignore`](../../android/.gitignore) — Excludes generated Android vector asset, keeping SVG as versioned source.
- [`android/AGENTS.md`](../../android/AGENTS.md) — Indexed; inspect source or directory guide.
- [`android/QUALIFICATION.md`](../../android/QUALIFICATION.md) — Indexed; inspect source or directory guide.
- [`android/README.md`](../../android/README.md) — Indexed; inspect source or directory guide.
- [`android/RELEASE_GATES.md`](../../android/RELEASE_GATES.md) — Indexed; inspect source or directory guide.
- [`android/app/CODE_MAP.md`](../../android/app/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/build.gradle`](../../android/app/build.gradle) — Indexed; inspect source or directory guide.
- [`android/app/src/CODE_MAP.md`](../../android/app/src/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/CODE_MAP.md`](../../android/app/src/androidTest/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/CODE_MAP.md`](../../android/app/src/androidTest/java/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/CODE_MAP.md`](../../android/app/src/androidTest/java/xyz/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/CODE_MAP.md`](../../android/app/src/androidTest/java/xyz/dragonzpyder/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/AccountIsolationTest.java`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/AccountIsolationTest.java) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/AgentRequestLifecycleTest.java`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/AgentRequestLifecycleTest.java) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/CODE_MAP.md`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/MarkdownRendererTest.kt`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/MarkdownRendererTest.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/MediaPayloadTest.java`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/MediaPayloadTest.java) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/MobileOAuthStoreTest.java`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/MobileOAuthStoreTest.java) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/NativeChatStateTest.java`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/NativeChatStateTest.java) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/NativeNavigationDrawerTest.kt`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/NativeNavigationDrawerTest.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/NavigationAccessibilityTest.kt`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/NavigationAccessibilityTest.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/PendingAgentRequestStoreTest.java`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/PendingAgentRequestStoreTest.java) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/ProviderSignInUiTest.java`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/ProviderSignInUiTest.java) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/SecurePasswordFieldTest.java`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/SecurePasswordFieldTest.java) — Indexed; inspect source or directory guide.
- [`android/app/src/androidTest/java/xyz/dragonzpyder/android/SecureSessionStoreTest.java`](../../android/app/src/androidTest/java/xyz/dragonzpyder/android/SecureSessionStoreTest.java) — Indexed; inspect source or directory guide.
- [`android/app/src/benchmark/AndroidManifest.xml`](../../android/app/src/benchmark/AndroidManifest.xml) — Indexed; inspect source or directory guide.
- [`android/app/src/benchmark/CODE_MAP.md`](../../android/app/src/benchmark/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/benchmark/java/CODE_MAP.md`](../../android/app/src/benchmark/java/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/benchmark/java/xyz/CODE_MAP.md`](../../android/app/src/benchmark/java/xyz/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/benchmark/java/xyz/dragonzpyder/CODE_MAP.md`](../../android/app/src/benchmark/java/xyz/dragonzpyder/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/benchmark/java/xyz/dragonzpyder/android/BenchmarkChatActivity.kt`](../../android/app/src/benchmark/java/xyz/dragonzpyder/android/BenchmarkChatActivity.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/benchmark/java/xyz/dragonzpyder/android/CODE_MAP.md`](../../android/app/src/benchmark/java/xyz/dragonzpyder/android/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/main/AndroidManifest.xml`](../../android/app/src/main/AndroidManifest.xml) — Indexed; inspect source or directory guide.
- [`android/app/src/main/CODE_MAP.md`](../../android/app/src/main/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/CODE_MAP.md`](../../android/app/src/main/java/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/CODE_MAP.md`](../../android/app/src/main/java/xyz/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/CODE_MAP.md`](../../android/app/src/main/java/xyz/dragonzpyder/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/AgentFileRepository.kt`](../../android/app/src/main/java/xyz/dragonzpyder/android/AgentFileRepository.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/AgentRequestViewModel.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/AgentRequestViewModel.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/ApiRoutePolicy.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/ApiRoutePolicy.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/CODE_MAP.md`](../../android/app/src/main/java/xyz/dragonzpyder/android/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/ChatPresentationState.kt`](../../android/app/src/main/java/xyz/dragonzpyder/android/ChatPresentationState.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/DragonApi.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/DragonApi.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/DragonDesignTokens.kt`](../../android/app/src/main/java/xyz/dragonzpyder/android/DragonDesignTokens.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/DragonNavigationRow.kt`](../../android/app/src/main/java/xyz/dragonzpyder/android/DragonNavigationRow.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/GoogleCredentialLogin.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/GoogleCredentialLogin.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/MainActivity.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/MainActivity.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/MarkdownDocument.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/MarkdownDocument.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/MarkdownRenderer.kt`](../../android/app/src/main/java/xyz/dragonzpyder/android/MarkdownRenderer.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/MathMarkup.kt`](../../android/app/src/main/java/xyz/dragonzpyder/android/MathMarkup.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/MediaPayload.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/MediaPayload.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/MobileOAuthStore.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/MobileOAuthStore.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/NativeChatView.kt`](../../android/app/src/main/java/xyz/dragonzpyder/android/NativeChatView.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/NativeCommandPalette.kt`](../../android/app/src/main/java/xyz/dragonzpyder/android/NativeCommandPalette.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/NativeVoiceSession.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/NativeVoiceSession.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/NativeVoiceView.kt`](../../android/app/src/main/java/xyz/dragonzpyder/android/NativeVoiceView.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/NavigationGlyph.kt`](../../android/app/src/main/java/xyz/dragonzpyder/android/NavigationGlyph.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/PendingAgentRequestStore.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/PendingAgentRequestStore.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/SecurePasswordField.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/SecurePasswordField.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/SecureSessionStore.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/SecureSessionStore.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/java/xyz/dragonzpyder/android/SessionCookies.java`](../../android/app/src/main/java/xyz/dragonzpyder/android/SessionCookies.java) — Indexed; inspect source or directory guide.
- [`android/app/src/main/res/CODE_MAP.md`](../../android/app/src/main/res/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/main/res/drawable/CODE_MAP.md`](../../android/app/src/main/res/drawable/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/main/res/drawable/ic_logo.xml`](../../android/app/src/main/res/drawable/ic_logo.xml) — Indexed; inspect source or directory guide.
- [`android/app/src/main/res/values/CODE_MAP.md`](../../android/app/src/main/res/values/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/main/res/values/dialog_themes.xml`](../../android/app/src/main/res/values/dialog_themes.xml) — Indexed; inspect source or directory guide.
- [`android/app/src/main/res/xml/CODE_MAP.md`](../../android/app/src/main/res/xml/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/main/res/xml/camera_paths.xml`](../../android/app/src/main/res/xml/camera_paths.xml) — Indexed; inspect source or directory guide.
- [`android/app/src/test/CODE_MAP.md`](../../android/app/src/test/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/test/java/CODE_MAP.md`](../../android/app/src/test/java/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/test/java/xyz/CODE_MAP.md`](../../android/app/src/test/java/xyz/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/test/java/xyz/dragonzpyder/CODE_MAP.md`](../../android/app/src/test/java/xyz/dragonzpyder/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/test/java/xyz/dragonzpyder/android/CODE_MAP.md`](../../android/app/src/test/java/xyz/dragonzpyder/android/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/app/src/test/java/xyz/dragonzpyder/android/DesignContractTest.kt`](../../android/app/src/test/java/xyz/dragonzpyder/android/DesignContractTest.kt) — Indexed; inspect source or directory guide.
- [`android/app/src/test/java/xyz/dragonzpyder/android/MarkdownDocumentTest.java`](../../android/app/src/test/java/xyz/dragonzpyder/android/MarkdownDocumentTest.java) — Indexed; inspect source or directory guide.
- [`android/app/src/test/java/xyz/dragonzpyder/android/MathMarkupTest.kt`](../../android/app/src/test/java/xyz/dragonzpyder/android/MathMarkupTest.kt) — Indexed; inspect source or directory guide.
- [`android/benchmark/CODE_MAP.md`](../../android/benchmark/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/benchmark/build.gradle`](../../android/benchmark/build.gradle) — Indexed; inspect source or directory guide.
- [`android/benchmark/src/CODE_MAP.md`](../../android/benchmark/src/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/benchmark/src/main/AndroidManifest.xml`](../../android/benchmark/src/main/AndroidManifest.xml) — Indexed; inspect source or directory guide.
- [`android/benchmark/src/main/CODE_MAP.md`](../../android/benchmark/src/main/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/benchmark/src/main/java/CODE_MAP.md`](../../android/benchmark/src/main/java/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/benchmark/src/main/java/xyz/CODE_MAP.md`](../../android/benchmark/src/main/java/xyz/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/benchmark/src/main/java/xyz/dragonzpyder/CODE_MAP.md`](../../android/benchmark/src/main/java/xyz/dragonzpyder/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/benchmark/src/main/java/xyz/dragonzpyder/benchmark/CODE_MAP.md`](../../android/benchmark/src/main/java/xyz/dragonzpyder/benchmark/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/benchmark/src/main/java/xyz/dragonzpyder/benchmark/ReleaseBenchmarks.kt`](../../android/benchmark/src/main/java/xyz/dragonzpyder/benchmark/ReleaseBenchmarks.kt) — Indexed; inspect source or directory guide.
- [`android/build.gradle`](../../android/build.gradle) — Indexed; inspect source or directory guide.
- [`android/gradle.properties`](../../android/gradle.properties) — Indexed; inspect source or directory guide.
- [`android/prepare-brand.sh`](../../android/prepare-brand.sh) — Generates native Android VectorDrawable from canonical web SVG using Python stdlib; removes stale generated PNG, retains resource identifier.
- [`android/qualify-device.sh`](../../android/qualify-device.sh) — Indexed; inspect source or directory guide.
- [`android/run-benchmarks.sh`](../../android/run-benchmarks.sh) — Indexed; inspect source or directory guide.
- [`android/settings.gradle`](../../android/settings.gradle) — Indexed; inspect source or directory guide.
- [`android/tests/ApiRoutePolicyTest.java`](../../android/tests/ApiRoutePolicyTest.java) — Indexed; inspect source or directory guide.
- [`android/tests/CODE_MAP.md`](../../android/tests/CODE_MAP.md) — Indexed; inspect source or directory guide.
- [`android/tests/SessionCookiesTest.java`](../../android/tests/SessionCookiesTest.java) — Indexed; inspect source or directory guide.
- [`android/tests/check_native_alignment.py`](../../android/tests/check_native_alignment.py) — Indexed; inspect source or directory guide.
- [`android/tests/test_native_alignment.py`](../../android/tests/test_native_alignment.py) — Indexed; inspect source or directory guide.
- [`web/frontend/src/UiIcon.jsx`](../../web/frontend/src/UiIcon.jsx) — Presentation-only 24-unit vector icon component; accessible names belong to controls; used by PersonalTemplate and WorkspaceControls.
- [`web/frontend/src/dz-mark.svg`](../../web/frontend/src/dz-mark.svg) — Canonical flat DZ geometric monogram; two closed paths, even-odd D counter, transparent background, 64-unit viewBox; read by web and Android build scripts.
