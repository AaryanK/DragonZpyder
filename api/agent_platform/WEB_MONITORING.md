# Web Research and Change Monitoring — Staging

## Web research in the agent

- The existing V2 Deep Agents supervisor and `researcher` subagent receive an optional `web_search` tool. It is not a separate agent framework.
- Feature flags: `DRAGONZPYDER_AGENT_HARNESS_V2=1`, `DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED=1`.
- Default `DRAGONZPYDER_AGENT_SEARCH_PROVIDER=wikipedia` uses the English Wikipedia REST search API: **encyclopedia-only**, useful for background or historical questions, not general breaking news.
- Optional `DRAGONZPYDER_AGENT_SEARCH_PROVIDER=brave` uses the fixed Brave Web Search HTTPS API and requires `DRAGONZPYDER_BRAVE_SEARCH_API_KEY` added securely to the invoking service; Brave may charge for requests.
- Results are bounded source-attributed excerpts with URLs and retrieval timestamp. The tool cannot fetch arbitrary pages, make write requests, execute JS, or access private networks.
- The existing password-protected staging lab has `POST /test-web-search` with `X-Staging-Password` and JSON `{"query":"George Washington"}` to check real retrieval with no model cost; it is rate-limited and not a public search API.
- Models are instructed to cite the exact provided links, explain limited coverage, and treat all retrieved snippets as untrusted evidence rather than instructions.
- Each agent run permits at most three `web_search` tool calls. The researcher subagent is restricted to two web searches and three model calls.

## Cron-based change detection

- Enable `DRAGONZPYDER_WEB_MONITOR_ENABLED=1` on the staging Hatchet worker. The worker registers the `dragonzpyder-staging-web-monitor` workflow; **this flag creates no cron automatically**.
- A check searches sources, normalizes the results, and stores an initial fingerprint and minimal source metadata in the agent PostgreSQL database.
- Subsequent checks detect new, removed and updated source URLs. Empty results do not generate false deletion alerts. No language model is called to check unchanged sources.
- Cron scheduling uses Hatchet's built-in recurring jobs; no homegrown looping scheduler. A monitor is bound to one immutable query and provider.
- A cron can be explicitly registered only by a trusted operator using `python -m agent_platform.monitor_admin create` with a monitor ID, query, provider and an hourly-or-slower expression.
- Operator registration requires `DRAGONZPYDER_MONITOR_ADMIN_ENABLED=1` as well as the worker/research flags. That admin flag is **not enabled by default**.
- Example operator command: `python -m agent_platform.monitor_admin create --monitor-id history-watch --query 'history of computing' --provider wikipedia --cron '0 9 * * *'`.
- This is a command example only; no recurring monitor was created for any user by this code deployment.

## Proof versus remaining work

- CI tests: both search backends with mocked HTTP, control-character validation, malformed and internal URL rejection, optional-key failure handling, agent graph composition, monitor baseline/change detection with a fake DB, and schedule safeguards. CI spends zero tokens.
- Staging flags let the existing password-protected Agent Test Lab ask live research questions using Wikipedia. End-to-end model answers and cron execution should be verified before declaring the capability production-ready.
- Before users can create monitors: implement real per-user identity, permissions, cost controls, per-tenant monitor ownership, authenticated schedule APIs, cancellation, notification delivery and history deletion.
- After this agent/search foundation is validated, integrate the requested MCP tools and wider app actions.

## Useful files

- `agent_platform/web_research.py`: bounded citation-safe search provider adapter and LangChain tool.
- `agent_platform/harness.py`: V2 supervisor and researcher specialist.
- `agent_platform/monitor.py`: SQL-backed comparison and Hatchet task.
- `agent_platform/monitor_admin.py`: guarded explicit cron registration.
- `tests/test_agent_web_monitor.py`: zero-cost offline safety and functional contracts.
