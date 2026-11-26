# api/agent_platform/migrations

SQL migrations for Personal goals/chat, request ledger, MCP and native voice/history. Manual scripts need separate authorization.

Read [repository instructions](../../../AGENTS.md) and [codebase navigation](../../../CODEBASE.md). See the [implementation guide](../../../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../../../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`20261121_personal_goal_receipts.sql`](20261121_personal_goal_receipts.sql) | SQL named for 20261121 personal goal receipts; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261122_first_party_chat.sql`](20261122_first_party_chat.sql) | SQL named for 20261122 first party chat; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261122_mcp_connections.sql`](20261122_mcp_connections.sql) | SQL named for 20261122 mcp connections; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261122_personal_mcp_goal_selections.sql`](20261122_personal_mcp_goal_selections.sql) | SQL named for 20261122 personal mcp goal selections; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_first_party_request_ledger.sql`](20261125_first_party_request_ledger.sql) | SQL named for 20261125 first party request ledger; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_native_mcp_oauth.sql`](20261125_native_mcp_oauth.sql) | SQL named for 20261125 native mcp oauth; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_native_voice.sql`](20261125_native_voice.sql) | SQL named for 20261125 native voice; inspect statements, transaction requirements and target database before use. | Indexed |
| [`20261125_personal_history_archive_manual.sql`](20261125_personal_history_archive_manual.sql) | SQL named for 20261125 personal history archive manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`operly_legacy_history_inventory_manual.sql`](operly_legacy_history_inventory_manual.sql) | SQL named for operly legacy history inventory manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`operly_personal_history_export_role_manual.sql`](operly_personal_history_export_role_manual.sql) | SQL named for operly personal history export role manual; inspect statements, transaction requirements and target database before use. | Indexed |
| [`operly_personal_history_inventory_manual.sql`](operly_personal_history_inventory_manual.sql) | SQL named for operly personal history inventory manual; inspect statements, transaction requirements and target database before use. | Indexed |
