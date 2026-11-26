# .github/workflows

CI and service-specific GitHub Actions workflows; inspect individual triggers before relying on coverage.

Read [repository instructions](../../AGENTS.md) and [codebase navigation](../../CODEBASE.md). See the [implementation guide](../../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`ai-mesh.yml`](ai-mesh.yml) | Workflow/configuration: ai mesh; inspect triggers, jobs and gates. | Indexed |
| [`ci.yml`](ci.yml) | Workflow/configuration: ci; inspect triggers, jobs and gates. | Indexed |
| [`dragonzpyder-api.yml`](dragonzpyder-api.yml) | Workflow/configuration: dragonzpyder api; inspect triggers, jobs and gates. | Indexed |
| [`mcp-connections.yml`](mcp-connections.yml) | Workflow/configuration: mcp connections; inspect triggers, jobs and gates. | Indexed |
| [`web.yml`](web.yml) | Workflow/configuration: web; inspect triggers, jobs and gates. | Indexed |

## Integrated harness changes

- [dragonzpyder-api.yml](dragonzpyder-api.yml): Run combined graph, media, recovery, and PostgreSQL integration tests, with agent-stack dependencies for actual checkpoints.
- [scoped-sandbox-runner.yml](scoped-sandbox-runner.yml): Check Node runner syntax and scoped protocol tests without allocating live VMs.
