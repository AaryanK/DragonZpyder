# DragonZpyder — 100 practical agent workflows

**This is a capability roadmap, NOT evidence that 100 autonomous workflows have run.** `implemented` = source/contract exists, not necessarily deployed; `operator_staging` = requires operator-authorized staging activation; `integration` = existing components are not yet wired and authorized in this persistent harness; `new_tool` = no approved execution adapter yet.

## Worker observability

| ID | Workflow | Required capability | Readiness |
|---|---|---|---|
| WF-001 | Capture a timestamped RAM baseline | `time.now, system.memory` | implemented |
| WF-002 | Warn when RAM crosses a threshold | `system.memory, local_monitor` | implemented |
| WF-003 | Detect memory growth between scheduled samples | `system.memory, PostgreSQL` | implemented |
| WF-004 | Warn when root disk fills | `system.disk, local_monitor` | implemented |
| WF-005 | Flag simultaneous RAM and disk saturation | `system.memory, system.disk` | implemented |
| WF-006 | Produce worker-health receipt history | `PostgreSQL observations` | implemented |
| WF-007 | Report CPU load spikes | `system.cpu` | new_tool |
| WF-008 | Detect process-level memory leaks | `process.inspect` | new_tool |
| WF-009 | Detect inode exhaustion | `system.inodes` | new_tool |
| WF-010 | Compare container and host capacity | `system.memory, host.capacity` | new_tool |

## Schedules and follow-up

| ID | Workflow | Required capability | Readiness |
|---|---|---|---|
| WF-011 | Wake a health monitor every five minutes | `Hatchet cron, local_monitor` | operator_staging |
| WF-012 | Run a one-off timestamped monitor snapshot | `local_monitor_cli` | implemented |
| WF-013 | Avoid duplicate logging on retry | `PostgreSQL unique occurrence` | implemented |
| WF-014 | Recover monitor history after worker restart | `PostgreSQL observations` | implemented |
| WF-015 | Check resource pressure before nightly backup | `Hatchet, filesystem.backup` | new_tool |
| WF-016 | Delay a task until an external signal | `Hatchet events` | integration |
| WF-017 | Pause recurring work for maintenance | `Hatchet management` | integration |
| WF-018 | Escalate on missed scheduling windows | `Hatchet, alert transport` | integration |
| WF-019 | Send an end-of-day health digest | `PostgreSQL, notifier` | new_tool |
| WF-020 | Change cadence without duplicate crons | `Hatchet cron management` | integration |

## Local files and desktop

| ID | Workflow | Required capability | Readiness |
|---|---|---|---|
| WF-021 | Organize downloads into folders | `desktop.files.move` | new_tool |
| WF-022 | Deduplicate identical local files | `desktop.files.hash/delete` | new_tool |
| WF-023 | Find large temporary files | `desktop.files.scan` | new_tool |
| WF-024 | Create a daily work journal | `desktop.files.append` | new_tool |
| WF-025 | Watch a folder for new PDFs | `desktop.files.watch` | new_tool |
| WF-026 | Merge PDFs without cloud upload | `pdf.merge` | new_tool |
| WF-027 | Extract text from selected documents | `pdf.extract` | new_tool |
| WF-028 | Generate a backup manifest | `desktop.files.inventory` | new_tool |
| WF-029 | Rename screenshots by metadata | `desktop.files.rename` | new_tool |
| WF-030 | Recover interrupted local file writes | `desktop.files.journal` | new_tool |

## Developer and CI

| ID | Workflow | Required capability | Readiness |
|---|---|---|---|
| WF-031 | Summarize newly opened GitHub issues | `github.issues.list` | integration |
| WF-032 | Triage reproducible bug reports | `github.issues.read, sandbox.test` | integration |
| WF-033 | Report failing CI jobs | `github.actions.list` | integration |
| WF-034 | Prepare a feature-branch patch | `github.files, sandbox.git` | integration |
| WF-035 | Run unit tests after an authorized change | `sandbox.python` | new_tool |
| WF-036 | Generate release notes from PRs | `github.pulls.list` | integration |
| WF-037 | Check dependency updates weekly | `github.files, package audit` | integration |
| WF-038 | Create a draft PR with evidence | `github.pr.create` | integration |
| WF-039 | Watch review requests | `github.review.list` | integration |
| WF-040 | Retry a failed disposable CI job | `github.actions.rerun` | integration |

## Web and information

| ID | Workflow | Required capability | Readiness |
|---|---|---|---|
| WF-041 | Search technical documentation | `web_search` | integration |
| WF-042 | Track published documentation changes | `web_search, Hatchet` | integration |
| WF-043 | Compare scientific sources | `web_search, document.read` | integration |
| WF-044 | Prepare a weekly research digest | `web_search, Hatchet` | integration |
| WF-045 | Detect a public API schema change | `http.get, schema.diff` | new_tool |
| WF-046 | Summarize an authorized webpage | `web.fetch, LLM` | new_tool |
| WF-047 | Monitor library release feeds | `release.rss` | new_tool |
| WF-048 | Check public status pages | `http.get, Hatchet` | new_tool |
| WF-049 | Find MCP servers in a registry | `mcp.registry` | integration |
| WF-050 | Verify a cited URL | `web_search, http.get` | integration |

## Personal communications

| ID | Workflow | Required capability | Readiness |
|---|---|---|---|
| WF-051 | Draft an email reply | `gmail.read/draft` | integration |
| WF-052 | Find messages needing follow-up | `gmail.search` | integration |
| WF-053 | Schedule a meeting after checking availability | `calendar.freebusy/create` | integration |
| WF-054 | Send a due-date reminder | `calendar.read, notify` | integration |
| WF-055 | Summarize authorized unread email | `gmail.search/read` | integration |
| WF-056 | Prepare a daily agenda | `calendar.list` | integration |
| WF-057 | Save a note from a conversation | `notes.create` | new_tool |
| WF-058 | Track a sent request's reply | `gmail.search, Hatchet` | integration |
| WF-059 | Sort authorized Drive documents | `drive.search/move` | integration |
| WF-060 | Draft an email with an attachment | `gmail.draft, drive.read` | integration |

## Business and operations

| ID | Workflow | Required capability | Readiness |
|---|---|---|---|
| WF-061 | Summarize workspace activity | `operly.kernel.read` | integration |
| WF-062 | Review pending approvals | `operly.approvals.list` | integration |
| WF-063 | Prepare customer follow-up drafts | `crm.read, draft` | new_tool |
| WF-064 | Draft an invoice from approved records | `accounting.read, invoice.draft` | new_tool |
| WF-065 | Find overdue business tasks | `operly.tasks.list` | integration |
| WF-066 | Gather weekly performance reports | `operly.records.read` | integration |
| WF-067 | Identify stalled workflow executions | `operly.workflow.status` | integration |
| WF-068 | Request approval before changing records | `operly.approvals.request` | integration |
| WF-069 | Watch inventory thresholds | `inventory.read, Hatchet` | new_tool |
| WF-070 | Audit an automated business write | `operly.kernel.audit` | integration |

## Data and artifacts

| ID | Workflow | Required capability | Readiness |
|---|---|---|---|
| WF-071 | Check CSV files for missing fields | `filesystem.read, csv.validate` | new_tool |
| WF-072 | Chart a local dataset | `data.plot` | new_tool |
| WF-073 | Transform a spreadsheet to schema | `sheets.read/write` | integration |
| WF-074 | Aggregate health readings | `PostgreSQL, data.aggregate` | integration |
| WF-075 | Generate monthly PDF reports | `pdf.write` | new_tool |
| WF-076 | Cluster log errors | `logs.read, data.group` | new_tool |
| WF-077 | Compare document versions | `files.diff` | new_tool |
| WF-078 | Create an HTML health dashboard | `html.render` | new_tool |
| WF-079 | Find anomalies in time-series data | `PostgreSQL, analysis` | integration |
| WF-080 | Verify exported artifact hashes | `files.hash, receipt.verify` | new_tool |

## MCP capability ecosystem

| ID | Workflow | Required capability | Readiness |
|---|---|---|---|
| WF-081 | Discover approved MCP read tools | `mcp_adapter, capability_hub` | integration |
| WF-082 | Reject an unexpected MCP tool name | `capability_hub` | implemented |
| WF-083 | Block unapproved MCP hosts | `mcp_adapter` | implemented |
| WF-084 | Refresh provider OAuth authorization | `OAuth broker` | new_tool |
| WF-085 | Bind tools to an authorized run | `signed lease, capability_hub` | integration |
| WF-086 | Stop revoked MCP access | `revocation check` | new_tool |
| WF-087 | Quarantine prompt-injected tool output | `tool output policy` | new_tool |
| WF-088 | Verify provider-signed receipts | `MCP tool receipt` | new_tool |
| WF-089 | Compare paid tool alternatives | `capability pricing` | new_tool |
| WF-090 | Discover public MCP automatically | `MCP registry discovery` | new_tool |

## Reliability and privacy

| ID | Workflow | Required capability | Readiness |
|---|---|---|---|
| WF-091 | Continue monitoring after process restart | `PostgreSQL ledger` | implemented |
| WF-092 | Reject unsafe local commands | `local_tool_registry` | implemented |
| WF-093 | Keep credentials out of prompts | `local vault, policy gate` | new_tool |
| WF-094 | Log failed tools without claiming success | `execution journal` | integration |
| WF-095 | Cancel an authorized scheduled goal | `goal registry, Hatchet` | integration |
| WF-096 | Verify external side effects independently | `external receipt oracle` | new_tool |
| WF-097 | Enforce per-goal inference spend | `gateway budget ledger` | integration |
| WF-098 | Renew expiring delegation on wake | `signed delegation, OAuth` | new_tool |
| WF-099 | Resume work after human approval | `approval resume` | integration |
| WF-100 | Reconcile uncertain remote tool outcomes | `idempotency ledger` | new_tool |

## What counts as a passing real-world workflow?

Require signed/authorized tool access, durable task identity, actual invocation, observed side-effect receipts, independent outcome verification, retry/cancellation/restart behavior, cost controls, and no unapproved effects. The separate 100-case test suite measures only what local tools currently support; its synthetic data and accelerated time must not be presented as 100 live jobs.
