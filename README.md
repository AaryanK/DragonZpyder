# DragonZpyder

**One intelligence experience. Many models, tools, and environments. Verified work, not just answers.**

DragonZpyder is an evolving **agentic AI platform** intended to help people express a goal, coordinate the best permitted models and tools, execute work over time, and verify what actually happened. Its longer-term ambition is to make computing feel less like manually operating disconnected apps and more like directing an accountable, persistent assistant.

The design is deliberately **not** to build another monolithic agent framework or pretend that one model can do everything. DragonZpyder uses existing model providers, Deep Agents, LangGraph, MCP, schedulers, and governed tool runtimes, adding the integration, permissions, state, product experience, and outcome verification those components do not supply together.

**[Website](https://dragonzpyder.xyz/) · [Personal AI](https://dragonzpyder.xyz/app) · [Operly](https://operly.dragonzpyder.xyz/) · [Engineering notes](api/agent_platform/README.md) · [Platform ownership](docs/platform-ownership.md)**

> **Status — November 21, 2026:** An actively developed, partially deployed platform, **not** a generally available autonomous computer replacement. The repository contains real model APIs, a React/FastAPI web product, an internal agent harness, PostgreSQL persistence, Hatchet workers, and guarded Operly MCP adapters. Their presence in source does **not** imply that every feature is enabled for every signed-in user. The Personal MCP bridge and scheduled Personal tool execution are still gated and have not passed a live, user-scoped, multi-wake production acceptance test.

## The product we are building

A user should eventually be able to say *what they want done*, rather than specify every application, prompt, and sequence of clicks. The system should:

1. **Understand the objective.** Plan the work, clarify only consequential uncertainty, and define measurable completion criteria.
2. **Discover available capabilities.** Find permitted models, MCP tools, connected accounts, computer environments, and existing services without inventing access.
3. **Execute and delegate.** Select capable models and specialized workers; run independent tasks in parallel when useful, with bounded costs and isolated authority.
4. **Persist and resume.** Save goals, dependencies, checkpoints, approvals, results, and failures so a task survives requests and worker restarts.
5. **Verify outcomes.** Read back actual artifacts, tool receipts, external state, and costs; distinguish evidence from an agent's claim of success.
6. **Keep the user in control.** Enforce identity, per-tool permissions, revocation, approvals for consequential actions, spending limits, and privacy boundaries.

**Operly** provides the governed real-world action layer and currently the authentication and Personal runtime used by DragonZpyder's web product. DragonZpyder's intended long-term role is the **shared intelligence and execution platform**; Operly remains authoritative for its business tenants, memberships, connected accounts, policies, tools, and approvals. A personal login must never imply permission to act for a business workspace.

## Current implementation, without conflating code with rollout

| Capability | Implemented or verified | Important boundary |
| --- | --- | --- |
| **Web experience** | React 19 + Vite 7 frontend, Python FastAPI delivery, Personal chat, account pages, model/media UI, and server-side proxying | Some features require provider credentials or explicit flags; compatibility controllers are still being migrated to React |
| **Identity** | DragonZpyder browser login uses Operly's existing authenticated Personal session, via same-origin `/api/*` | Independent DragonZpyder identity/OIDC migration remains future work; no implicit Workspace permissions |
| **AI Mesh experience** | Model selection and chat/media endpoints exist, including guarded image, speech, transcription and video paths | This is not a universal, contractually available model/app marketplace or full autonomous model router |
| **Inference gateway** | Separate service-authenticated FastAPI API with model allowlists, server-side provider access, usage accounting and policy checks | Per-user/global cost enforcement and provider coverage need continued validation; the browser never receives provider keys |
| **Agent harness** | Deep Agents + LangGraph, bounded specialists, virtual filesystem, approved tool adapters, and PostgreSQL checkpoints | Internal/operator-gated. Virtual files are not arbitrary host files; model output alone is not verified completion |
| **Persistent jobs** | Dedicated Hatchet worker; real production ping execution; PostgreSQL checkpoint write and resume across fresh production deployments | Those production proofs used a zero-inference ping and **synthetic** tool messages, not real Personal account tools |
| **Long-horizon model/tool canary** | Isolated staging three-wake read-only local tool selection completed, persisted receipts, and stopped on terminal state | The selected local tools were not Operly Personal tools and do not prove general unattended work |
| **Operly MCP** | Native LangChain MCP adapter, server authorization, read-only tool tests, and first-party Personal delegation code merged across repositories | Personal MCP execution for logged-in end users remains disabled pending live end-to-end and revocation acceptance |
| **Personal multi-wake path** | Source includes a session-bound Personal run route, PostgreSQL goal/receipt ledger, replay protections, and an opt-in Hatchet wake | Two-wake and cross-user tests use real PostgreSQL but simulated remote calls. No public recurring Personal jobs are enabled |
| **Parallelism / verification** | Bounded LangGraph fan-out, specialist agents, verification-oriented tests and receipt checks | Not yet a globally budgeted, durable, externally verified parallel execution system |
| **Memory and computer tools** | Mem0/pgvector experiment and a scoped Operly computer adapter exist | Neither authorizes arbitrary end-user desktop control; complete memory retention/erasure is not production-certified |
| **Project IC / AIC** | Research and product concept | **No launched AIC wallet, transferable token, universal subscription, or issued currency** |

**Operational snapshot (November 21, 2026):** The existing Railway production API and Hatchet worker were deployed from `develop` at merge `55044a93`; the production web service remained on its earlier pinned build. Production tests verified an authenticated worker-to-gateway request, a real Hatchet ping, and synthetic LangGraph tool-message persistence across two separate deployments. All eight DragonZpyder production services were healthy after those tests. These are **infrastructure acceptance results**, not an end-to-end Personal MCP or live multi-wake agent success claim. Runtime status can change independently of this README.

## Architecture and ownership

```text
User / web client
    |
    v
DragonZpyder Web (React/Vite -> FastAPI)
    |                              |
    | same-origin /api/*           | /mesh/* and media/voice routes
    v                              v
Operly authentication        DragonZpyder model/provider boundary
+ existing Personal runtime  (authenticated gateway, metering, limits)
    |                              |
    | current Personal chat        v
    |                        Permitted AI providers
    |
    | gated first-party Personal delegation (NOT enabled by default)
    v
DragonZpyder Agent Harness (Deep Agents + LangGraph)
    |           |                |
    |           |                +--> specialist agents / bounded fan-out
    |           +--> PostgreSQL checkpoints and goal/receipt ledger
    +--> Hatchet worker and explicitly authorized wakes
    |
    +--> approved outbound MCP client
              |
              v
         Operly MCP server
              |
              v
       Operly Kernel + per-user capability registry
       (membership, connector availability, policy, approvals, audit)
```

The **model never becomes the source of authorization**. Operly validates the already signed-in Personal user and, when the bridge is explicitly enabled, issues a short-lived delegation for that user's currently allowed tools. DragonZpyder discovers only those tools and presents a separate first-party service proof. Operly revalidates the session and authorization at the MCP boundary. No browser cookies, OAuth provider secrets, or broad administrator tokens belong in model context or LangGraph checkpoints.

A scheduled Personal wake obtains **fresh** authority. The current session-bound mechanism must stop when the source Operly session expires or is revoked. Truly unattended work lasting beyond a browser session requires a separate consented **durable grant** with its own lifecycle, expiry, revocation, and policy checks—not an indefinitely reusable session token.

## Repository map

| Path | Responsibility |
| --- | --- |
| [`web/frontend/`](web/frontend/) | React/Vite source, landing, Personal, account and admin pages; compiled/prerendered assets |
| [`web/main.py`](web/main.py) | FastAPI web delivery, same-origin Operly proxy, AI Mesh and voice routes |
| [`web/`](web/) | Temporary browser compatibility controllers and legacy Node rollback code |
| [`api/main.py`](api/main.py) | Separate authenticated inference API and service endpoints |
| [`api/agent_platform/runtime.py`](api/agent_platform/runtime.py) | Model client, checkpointed agent execution and reporting |
| [`api/agent_platform/harness.py`](api/agent_platform/harness.py) | Deep Agents supervisor, specialists, bounded tools and virtual filesystem |
| [`api/agent_platform/operly_mcp_client.py`](api/agent_platform/operly_mcp_client.py) | Native, allowlisted outbound MCP tool loading |
| [`api/agent_platform/personal_bridge.py`](api/agent_platform/personal_bridge.py) | Private Operly Personal delegation receiver and isolated LangGraph thread |
| [`api/agent_platform/personal_wake.py`](api/agent_platform/personal_wake.py) | Opt-in session-renewed Hatchet wakes, durable progress and receipts |
| [`api/agent_platform/worker.py`](api/agent_platform/worker.py) | Dedicated Hatchet worker registration |
| [`api/agent_platform/memory.py`](api/agent_platform/memory.py) | Experimental Mem0 memory integration |
| [`identity/`](identity/) | Independent identity/OIDC migration contracts; not the live sign-in authority |
| [`docs/`](docs/) | Platform ownership and security guidance |
| [`tests/`](tests/) and [`api/tests/`](api/tests/) | Client, agent, provider, authorization, persistence and integration regressions |
| [`legacy/`](legacy/) | Historical implementation material; do not treat as the current deployed harness |

The related Operly repository owns the **inbound MCP server and governed Personal/Workspace tool registries**. Cross-repository integration landed in [Operly PR #383](https://github.com/AaryanK/Operly/pull/383) and [DragonZpyder PR #56](https://github.com/AaryanK/DragonZpyder/pull/56). Merged source is not equivalent to enabled customer access.

## Develop and test

The actively integrated branch is **`develop`**. GitHub's repository default is still **`master`**; do not assume that the default branch contains the latest application or deployed integration. Production services may also be **pinned to specific commits** even when their configured branch is `develop`.

### Frontend

Node.js 22 is the build toolchain. Production serves the compiled React/Vite output from FastAPI rather than running the Vite development server.

```bash
git clone https://github.com/AaryanK/DragonZpyder.git
cd DragonZpyder
git switch develop

npm --prefix web/frontend install
npm --prefix web/frontend run build
npm --prefix web/frontend test
# Optional local frontend preview (backend-dependent features need their services)
npm --prefix web/frontend run dev
```

See [frontend instructions](web/frontend/README.md). A compiled local frontend alone does not create an authenticated Operly session or supply live provider credentials.

### FastAPI services

Use Python 3.12 and isolated environments. These are **developer smoke tests**, not instructions to expose private endpoints publicly.

```bash
python -m pip install -r api/requirements.txt -r web/requirements.txt pytest

python -m pytest -q \
  api/tests/test_fastapi_gateway.py \
  web/tests/test_fastapi_web.py
```

The web server is launched from `web/` as `uvicorn main:app`, and the inference API from `api/` as `uvicorn main:app`, with separate environment configuration. The inference API's health check may correctly report `unconfigured` when no provider credentials are supplied.

### Agent harness and persistence tests

```bash
python -m pip install -r api/requirements-agent.txt pytest
cd api

pytest -q \
  tests/test_personal_mcp_bridge.py \
  tests/test_personal_mcp_wake.py \
  tests/test_operly_mcp_client.py \
  tests/test_harness_v2.py
```

The [API CI workflow](.github/workflows/dragonzpyder-api.yml) additionally launches **disposable PostgreSQL** to test checkpoint restart, concurrent goal fencing, two-wake Personal receipt persistence, replay rejection and cross-user isolation. Those PostgreSQL tests require their CI database and are not part of the no-database smoke command. Provider/model calls are not required by these tests.

**No setup step here authorizes writing to a real user's Operly account.** Do not put live tokens in source, browser bundles, test fixtures or agent prompts.

## Deployment and security model

Railway currently hosts **separate** DragonZpyder Web, inference API, agent worker, Hatchet and database services. Operly is a separate product with its own release lifecycle. The Web and API each use explicit root directories and startup commands. A merged commit should be checked against the **actual deployed commit SHA**, not inferred from the branch name.

The agent, MCP, personal delegated execution, schedule registration, model spending, computer execution and mutating tools have independent gates. Their default-off behavior is intentional:

- **Human authority:** authenticate an actual Personal user and separately verify Workspace membership where applicable; neither the LLM nor a caller-provided user ID grants access.
- **Tool authority:** derive a bounded allowlist from Operly, validate server-side on every call, and reject cross-user data and unauthorized writes.
- **Persistence:** checkpoint messages by a user-and-conversation-isolated key; record immutable goal identity, wake sequence, tool receipts and terminal state in PostgreSQL.
- **Execution:** use Hatchet for scheduled tasks; registration alone does **not** install a cron or authorize background access.
- **Costs:** run inference through an authenticated metered gateway, cap work and model calls, and add end-to-end atomic parent/child budgets before enabling general parallel paid work.
- **Approvals and evidence:** consequential actions require policy/approval paths; a model's completion statement is not independent verification.
- **Revocation and privacy:** expiration, sign-out or revoked capability must prevent later use; memory/history deletion and cloud/local disclosure need explicit lifecycle policies.
- **Computer access:** do not interpret an Operly Workspace sandbox adapter as permission to control the user's personal machine.

For current security and ownership details, see [security baseline](docs/security-baseline.md), [platform ownership](docs/platform-ownership.md), [agent harness notes](api/agent_platform/AGENT_HARNESS_V3.md), and [long-horizon canary specification](api/agent_platform/REAL_LONG_HORIZON_STAGING.md). Some older engineering notes describe earlier branches; use current source, CI, and deployment evidence to resolve their historical status.

## Roadmap: what needs to happen next

**P0 — make the actual user experience trustworthy**

1. **Complete Personal MCP acceptance.** Run a synthetic signed-in Operly user through the *live* first-party MCP bridge with a real model selecting read-only tools on at least two separate scheduled wakes. Verify the underlying Operly Kernel result, checkpoint readback, grant expiry, revocation, cross-user isolation, cost and replay handling.
2. **Introduce durable, consented goals.** Move beyond a session-bound canary to an owner-scoped Goal Manager with persisted objectives, dependencies, attempt history, deadlines, pause/resume, approvals, cancellation and explicitly authorized wake policies.
3. **Verify outcomes, not narratives.** Establish independent artifacts/external-state oracles, receipts, negative tests and transparent partial-completion reporting.
4. **Make production spend predictable.** Enforce per-user and per-goal limits, atomic budgets across delegated/parallel workers, provider pricing checks and accurate usage reconciliation.
5. **Ship a coherent agent UI.** Show goal state, why a tool is available, approval requests, step receipts, failures, resumptions, artifacts and actual incurred costs.

**P1 — expand useful, safely delegated execution**

- Bounded parallel specialist workers with real concurrency measurement, durable parent-child recovery, cancellation and shared-resource isolation.
- An outbound MCP broker with reviewed providers, user-scoped OAuth, safe discovery, policy enforcement, egress restrictions and genuine revocation.
- Secure computer/browser execution in disposable sandboxes; local-device operation only with explicit per-device grants and credential isolation.
- Multimodal and realtime experiences that use the same accountable execution and tool-authorization model across clients.
- Long-term Personal memory only after consent, retention, complete deletion/erasure and data-migration guarantees are proven.

**Research, not a shipping promise**

- **AI Mesh:** broad provider and participating-app discovery, robust model routing and interoperability subject to vendor APIs and agreements. The currently deployed model/media UI is only a subset.
- **Project IC / AIC:** a proposed, auditable prepaid usage balance shared across participating services. It is **not** a live wallet, a transferable token, or a way to obtain a vendor's paid subscription entitlements. Payments, compliance, pricing, refunds, fraud, and contractual rights must be solved first.
- **Privacy-preserving local intelligence:** device-side context minimization and selective cloud consultation with measurable privacy controls; do not claim perfect anonymization.

## Engineering rule

**A feature is not complete because the model said so, the code compiled, CI passed, a worker started, or a scheduler fired.** For any release claim, identify the execution boundary, the authenticated principal, permitted tools, actual input/output, durable receipt, verification oracle, cost, and behavior on retry, expiry, failure and revocation.

Historical branding still applies: the **dragon** evokes creative power and the **spider** a web of connections. The aim is not to own every model or app, but to connect authorized capabilities into work people can understand, govern and verify.

**Connect intelligence. Preserve agency. Verify results.**
