# api/tests

Backend contracts, regressions, PostgreSQL integration, and explicitly gated live tests.

Read [repository instructions](../../AGENTS.md) and [codebase navigation](../../CODEBASE.md). See the [implementation guide](../../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`gateway.test.mjs`](gateway.test.mjs) | Test target: gateway.test; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_agent_evaluation.py`](test_agent_evaluation.py) | Test target: agent evaluation; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_agent_gateway_protocol.py`](test_agent_gateway_protocol.py) | Test target: agent gateway protocol; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_agent_platform_contract.py`](test_agent_platform_contract.py) | Test target: agent platform contract; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_agent_stack_integration.py`](test_agent_stack_integration.py) | Test target: agent stack integration; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_agent_web_monitor.py`](test_agent_web_monitor.py) | Test target: agent web monitor; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_artifact_evidence.py`](test_artifact_evidence.py) | Test target: artifact evidence; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_budget_postgres_integration.py`](test_budget_postgres_integration.py) | Test target: budget postgres integration; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_budget_reservations.py`](test_budget_reservations.py) | Test target: budget reservations; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_capability_hub.py`](test_capability_hub.py) | Test target: capability hub; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_fastapi_gateway.py`](test_fastapi_gateway.py) | Test target: fastapi gateway; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_agent_stream.py`](test_first_party_agent_stream.py) | Test target: first party agent stream; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_chat.py`](test_first_party_chat.py) | Test target: first party chat; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_goal_management.py`](test_first_party_goal_management.py) | Test target: first party goal management; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_request_ledger.py`](test_first_party_request_ledger.py) | Test target: first party request ledger; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_request_ledger_postgres.py`](test_first_party_request_ledger_postgres.py) | Test target: first party request ledger postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_first_party_voice.py`](test_first_party_voice.py) | Test target: first party voice; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_frontier_batch.py`](test_frontier_batch.py) | Test target: frontier batch; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_frontier_live_trust_boundary.py`](test_frontier_live_trust_boundary.py) | Test target: frontier live trust boundary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_frontier_stress.py`](test_frontier_stress.py) | Test target: frontier stress; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_gateway_parent_budget.py`](test_gateway_parent_budget.py) | Test target: gateway parent budget; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_harness_product_surface.py`](test_harness_product_surface.py) | Test target: harness product surface; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_harness_tool_acceptance.py`](test_harness_tool_acceptance.py) | Test target: harness tool acceptance; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_harness_v2.py`](test_harness_v2.py) | Test target: harness v2; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_activation_postgres.py`](test_identity_activation_postgres.py) | Test target: identity activation postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_bootstrap_postgres.py`](test_identity_bootstrap_postgres.py) | Test target: identity bootstrap postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_browser_authorize.py`](test_identity_browser_authorize.py) | Test target: identity browser authorize; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_browser_sessions.py`](test_identity_browser_sessions.py) | Test target: identity browser sessions; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_consent.py`](test_identity_consent.py) | Test target: identity consent; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_first_party_registry.py`](test_identity_first_party_registry.py) | Test target: identity first party registry; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_http_bridge.py`](test_identity_http_bridge.py) | Test target: identity http bridge; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_importer.py`](test_identity_importer.py) | Test target: identity importer; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_jwks.py`](test_identity_jwks.py) | Test target: identity jwks; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_mobile_provider.py`](test_identity_mobile_provider.py) | Test target: identity mobile provider; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_native_recovery_http.py`](test_identity_native_recovery_http.py) | Test target: identity native recovery http; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_native_recovery_postgres.py`](test_identity_native_recovery_postgres.py) | Test target: identity native recovery postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_native_signup.py`](test_identity_native_signup.py) | Test target: identity native signup; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_oauth_grants.py`](test_identity_oauth_grants.py) | Test target: identity oauth grants; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_offline_transfer.py`](test_identity_offline_transfer.py) | Test target: identity offline transfer; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_oidc_exchange.py`](test_identity_oidc_exchange.py) | Test target: identity oidc exchange; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_password_compat.py`](test_identity_password_compat.py) | Test target: identity password compat; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_password_login.py`](test_identity_password_login.py) | Test target: identity password login; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_pending_proof_http.py`](test_identity_pending_proof_http.py) | Test target: identity pending proof http; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_pending_reconciliation.py`](test_identity_pending_reconciliation.py) | Test target: identity pending reconciliation; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_personal_history_http.py`](test_identity_personal_history_http.py) | Test target: identity personal history http; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_personal_history_import.py`](test_identity_personal_history_import.py) | Test target: identity personal history import; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_postgres_integration.py`](test_identity_postgres_integration.py) | Test target: identity postgres integration; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_production_import.py`](test_identity_production_import.py) | Test target: identity production import; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_provider_challenges.py`](test_identity_provider_challenges.py) | Test target: identity provider challenges; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_provider_http.py`](test_identity_provider_http.py) | Test target: identity provider http; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_providers.py`](test_identity_providers.py) | Test target: identity providers; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_reconciliation.py`](test_identity_reconciliation.py) | Test target: identity reconciliation; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_recovery_delta.py`](test_identity_recovery_delta.py) | Test target: identity recovery delta; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_refresh.py`](test_identity_refresh.py) | Test target: identity refresh; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_relying_party_status.py`](test_identity_relying_party_status.py) | Test target: identity relying party status; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_role_postgres.py`](test_identity_role_postgres.py) | Test target: identity role postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_identity_token_boundary.py`](test_identity_token_boundary.py) | Test target: identity token boundary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_key_budget.py`](test_key_budget.py) | Test target: key budget; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_live_operly_mcp_smoke.py`](test_live_operly_mcp_smoke.py) | Test target: live operly mcp smoke; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_live_platform_tool_smoke.py`](test_live_platform_tool_smoke.py) | Test target: live platform tool smoke; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_local_autonomy_100.py`](test_local_autonomy_100.py) | Test target: local autonomy 100; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_local_autonomy_100_postgres.py`](test_local_autonomy_100_postgres.py) | Test target: local autonomy 100 postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_local_monitor.py`](test_local_monitor.py) | Test target: local monitor; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_local_monitor_postgres.py`](test_local_monitor_postgres.py) | Test target: local monitor postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_local_monitor_receipt_integrity.py`](test_local_monitor_receipt_integrity.py) | Test target: local monitor receipt integrity; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_long_horizon_monitoring_acceptance.py`](test_long_horizon_monitoring_acceptance.py) | Test target: long horizon monitoring acceptance; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mcp_adapter.py`](test_mcp_adapter.py) | Test target: mcp adapter; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mcp_broker.py`](test_mcp_broker.py) | Test target: mcp broker; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mcp_connections.py`](test_mcp_connections.py) | Test target: mcp connections; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mcp_connections_postgres.py`](test_mcp_connections_postgres.py) | Test target: mcp connections postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_mcp_schedule_selection.py`](test_mcp_schedule_selection.py) | Test target: mcp schedule selection; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_memory_database_reuse.py`](test_memory_database_reuse.py) | Test target: memory database reuse; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_model_capabilities.py`](test_model_capabilities.py) | Test target: model capabilities; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_native_canary.py`](test_native_canary.py) | Test target: native canary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_native_canary_postgres.py`](test_native_canary_postgres.py) | Test target: native canary postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_openrouter_spend_guard.py`](test_openrouter_spend_guard.py) | Test target: openrouter spend guard; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_operly_business_canary.py`](test_operly_business_canary.py) | Test target: operly business canary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_operly_mcp_client.py`](test_operly_mcp_client.py) | Test target: operly mcp client; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_operly_workflow_dispatch.py`](test_operly_workflow_dispatch.py) | Test target: operly workflow dispatch; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_ops_benchmark.py`](test_ops_benchmark.py) | Test target: ops benchmark; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_orchestration.py`](test_orchestration.py) | Test target: orchestration; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_persistent_graph.py`](test_persistent_graph.py) | Test target: persistent graph; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_persistent_graph_postgres.py`](test_persistent_graph_postgres.py) | Test target: persistent graph postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_persistent_tool_canary.py`](test_persistent_tool_canary.py) | Test target: persistent tool canary; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_persistent_tool_canary_postgres.py`](test_persistent_tool_canary_postgres.py) | Test target: persistent tool canary postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_core.py`](test_personal_core.py) | Test target: personal core; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_goal_tools.py`](test_personal_goal_tools.py) | Test target: personal goal tools; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_mcp_bridge.py`](test_personal_mcp_bridge.py) | Test target: personal mcp bridge; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_mcp_checkpoint_postgres.py`](test_personal_mcp_checkpoint_postgres.py) | Test target: personal mcp checkpoint postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_mcp_wake.py`](test_personal_mcp_wake.py) | Test target: personal mcp wake; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_mcp_wake_postgres.py`](test_personal_mcp_wake_postgres.py) | Test target: personal mcp wake postgres; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_personal_quota_checkpoint.py`](test_personal_quota_checkpoint.py) | Test target: personal quota checkpoint; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_progress_guard.py`](test_progress_guard.py) | Test target: progress guard; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_provider_gateway.py`](test_provider_gateway.py) | Test target: provider gateway; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_provider_pacing.py`](test_provider_pacing.py) | Test target: provider pacing; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_sandbox_math.py`](test_sandbox_math.py) | Test target: sandbox math; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_scientific_oracles.py`](test_scientific_oracles.py) | Test target: scientific oracles; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_shared_hourly_quota.py`](test_shared_hourly_quota.py) | Test target: shared hourly quota; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_staging_lab.py`](test_staging_lab.py) | Test target: staging lab; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_subjective_monitoring.py`](test_subjective_monitoring.py) | Test target: subjective monitoring; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_synthetic_business_cron.py`](test_synthetic_business_cron.py) | Test target: synthetic business cron; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_universal_mcp_catalog.py`](test_universal_mcp_catalog.py) | Test target: universal mcp catalog; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_usage_audit.py`](test_usage_audit.py) | Test target: usage audit; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_workflow_catalog_100.py`](test_workflow_catalog_100.py) | Test target: workflow catalog 100; inspect assertions and fixtures for the exact contract. | Indexed |
| [`test_workspace_bridge.py`](test_workspace_bridge.py) | Test target: workspace bridge; inspect assertions and fixtures for the exact contract. | Indexed |

`test_identity_profile_avatar.py`: offline verified-profile URL, bounded fetch and owner-linked persistence tests. No real Google requests.
