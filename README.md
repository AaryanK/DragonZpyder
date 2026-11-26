# DragonZpyder

**Express intent. Harness available intelligence. Complete and verify work.**

DragonZpyder is building the general-purpose intelligence layer through which people operate computers and applications. Instead of manually coordinating software, a person describes an objective through text, speech, vision or files. DragonZpyder discovers authorized capabilities, selects suitable models and execution mechanisms, performs the work, verifies the result, and can resume unfinished objectives over time.

The goal is not another chatbot or coding agent, and not to own every model or application. It is to compose existing intelligence and computing resources into reliable, accountable digital work.

**[Website](https://dragonzpyder.xyz/) · [Personal AI](https://dragonzpyder.xyz/app) · [Universal Harness V4 — canonical architecture](docs/universal-harness-v4.md) · [Contributor/agent instructions](AGENTS.md) · [Platform ownership](docs/platform-ownership.md) · [Operly](https://github.com/AaryanK/Operly)**

> **Status — November 25, 2026:** actively developed, partially deployed platform. The architecture below is the accepted direction, not a claim that universal autonomous computer use has shipped. Check actual source, feature gates, deployed SHA, and end-to-end evidence before asserting availability.

## Start here — contributors and coding agents

Before proposing or implementing any change, establish the project goal, follow the repository instructions, and inspect the actual implementation. This README is the product overview, not the complete engineering specification.

| Read in this order | What you will learn |
| --- | --- |
| 1. [AGENTS.md](AGENTS.md) | Mandatory repository-level development instructions and guardrails. |
| 2. [Universal Harness V4](docs/universal-harness-v4.md) | Canonical product mission, architecture, capability design, implementation sequence and acceptance criteria. |
| 3. [Platform ownership](docs/platform-ownership.md) | DragonZpyder/Operly boundaries and migration constraints. |
| 4. [Agent platform engineering notes](api/agent_platform/README.md) | Implementation entry points, historical test evidence and setup. |
| 5. [Harness source](api/agent_platform/harness.py), [runtime](api/agent_platform/runtime.py), [tests](api/tests/) | What actually exists, what is enforced and what remains to implement. |

Read the relevant source and current pull requests before editing. For major architecture changes, consult current upstream Deep Agents, LangChain and LangGraph documentation and relevant leading open-source harnesses before adding infrastructure; prefer reuse and explain deviations from the canonical design. Distinguish planned, implemented, tested and deployed features. Update the relevant documentation when decisions or verified capabilities change.

## What the platform is designed to do

A user can eventually request an outcome rather than specify individual tools: analyze a PDF and produce a report, write and run software, use a browser or application, create images/audio/video, or monitor a goal over time. The harness should choose among structured APIs/MCP, deterministic code execution, graphical computer use and specialized models. It should prefer the most reliable and economical suitable mechanism, enforce user authority, and return real artifacts or verified effects.

## Target architecture

```text
Text / speech / vision / files / web / mobile / desktop / Operly
                             |
                  Unified identity and sessions
                             |
               DragonZpyder shared intelligence
                  Deep Agents + LangGraph
         planning / context / skills / delegation / verification
                             |
                Governed capability discovery and execution
                /            |                |            \
          MCP / APIs     Files / shell     Browser / GUI   Models / media
                \            |                |            /
                 scoped execution, artifacts and receipts
                             |
            Hatchet + PostgreSQL + object storage + Langfuse
```

Deep Agents, LangGraph, OpenRouter/direct providers, Hatchet, existing MCP infrastructure and sandbox abstractions are foundations to extend, not duplicate. Realtime voice is an interface to the shared harness, not a second execution engine. Personal identity, native intelligence, artifacts and computer environments belong to DragonZpyder; Operly remains authoritative for its own business data, workspaces, memberships, application workflows, policies and approvals. Never infer business access from Personal login.

## Current source and rollout boundaries

| Capability | Source baseline | Remaining boundary |
| --- | --- | --- |
| Core harness | Deep Agents, LangGraph, virtual filesystem, bounded specialists | Real executable sandbox, skills and generalized capability policy |
| Native chat | First-party text API, identity and conversation paths, streaming and MCP account IDs | Attachment IDs, artifact stream, verified deployment/cutover |
| Computer | Signed scoped runner transport | Not bound as general agent tool; genuine Personal authorization and isolation proof |
| Models and media | Metered gateway; image, transcription, speech and video routes | Integrated multimodal agent workflows; provider availability and cost gates |
| Voice | Audio-only first-party WebRTC code | No execution tools in inspected session; shared conversation and execution bridge needed |
| External tools | MCP broker, managed OAuth connections and lazy discovery | End-to-end permission, revocation and rollout evidence |
| Durable tasks | Hatchet, PostgreSQL checkpoints, goal/receipt paths | General multi-wake task execution, recovery and budget proof |
| Memory | Experimental Mem0 integration | Consent, retention and complete erasure before rollout |
| Artifacts | Virtual file readbacks | Real binary upload/download, durable metadata and object storage |
| Project IC / AIC | Research concept | No launched wallet, transferable token or universal subscription |

Historical operational results from November 21 and earlier remain available in the previous README revisions and engineering notes. A source-level implementation or successful mock is not proof of a production feature. The [V4 contract](docs/universal-harness-v4.md#current-source-baseline-and-gaps-2026-11-25) records current gaps and how to update them.

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
| [`identity/`](identity/) | Independent identity/OIDC migration contracts and first-party identity implementation; verify rollout |
| [`docs/`](docs/) | Platform ownership and security guidance |
| [`tests/`](tests/) and [`api/tests/`](api/tests/) | Client, agent, provider, authorization, persistence and integration regressions |
| [`legacy/`](legacy/) | Historical implementation material; do not treat as the current deployed harness |

The related Operly repository owns its **inbound MCP server and governed business capability registries**, with transitional Personal integrations subject to migration. Cross-repository integration landed in [Operly PR #383](https://github.com/AaryanK/Operly/pull/383) and [DragonZpyder PR #56](https://github.com/AaryanK/DragonZpyder/pull/56). Merged source is not equivalent to enabled customer access.

## Develop and test

The actively integrated branch is **`develop`**. GitHub's default branch is **`develop`** as of November 25, 2026; do not infer the deployed revision from the branch name. Production services may also be **pinned to specific commits** even when their configured branch is `develop`.

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

## Roadmap: implementation in dependency order

The [Universal Harness V4 contract](docs/universal-harness-v4.md) is the source of truth for the architecture, milestones, acceptance criteria and research references.

1. Shared execution context, capability authorization, budgets, cancellation and receipts.
2. Isolated real filesystem, shell and Python sandbox using Deep Agents backends.
3. Durable artifact manager, authenticated uploads/downloads and sandbox transfers.
4. Native multimodal chat, typed progress and artifact events across clients.
5. Image, audio, speech and other media capabilities behind the same metered harness.
6. Reviewed skills, lazy discovery, capability-aware model selection and scoped specialist construction.
7. Browser/GUI, realtime voice execution bridge, bounded programmatic tool composition and durable recovery.
8. Repeatable objective-level evaluation and continuous improvement.

Work in small staging-first PRs. Public execution requires adversarial isolation, scope, revocation, replay, approval, cancellation and budget tests. Compare harnesses using matched models and fixtures; measure verified success, latency, cost and intervention. No performance parity is claimed.

AI Mesh, Project IC/AIC and privacy-preserving local intelligence remain research directions, subject to provider agreements, security and legal/product validation.

## Engineering rule

**A feature is not complete because the model said so, the code compiled, CI passed, a worker started, or a scheduler fired.** For any release claim, identify the execution boundary, the authenticated principal, permitted tools, actual input/output, durable receipt, verification oracle, cost, and behavior on retry, expiry, failure and revocation.

Historical branding still applies: the **dragon** evokes creative power and the **spider** a web of connections. The aim is not to own every model or app, but to connect authorized capabilities into work people can understand, govern and verify.

**Connect intelligence. Preserve agency. Verify results.**
