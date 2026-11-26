# Universal harness V4 — architecture and engineering contract

Status: accepted product direction, 2026-11-25. This is a target architecture, not a release announcement. Read this before modifying the harness, runtime, model gateway, tools, session/identity, clients, workflows, or computer infrastructure. Supersedes conflicting architectural direction in historical notes; source, CI and deployment evidence govern actual availability.

## Mission and success

DragonZpyder is the intelligence layer through which humans operate computers and applications. A person expresses an objective in text, speech, images, video or files; the system discovers available intelligence and permitted capabilities, chooses efficient execution mechanisms, completes work, verifies results, and resumes authorized unfinished work across devices and time. The ambition is broad digital task coverage, not a claim of unrestricted or perfectly reliable computer control.

Success means independently verified outcomes, not fluent responses, tool count, model size, or a running worker. Measure task completion, cost per verified success, latency, human interventions, recovery, and security failures.

## Non-negotiable architecture

1. One core harness, many interfaces. Web, mobile, desktop, realtime voice, camera, API and Operly use the same core agent and authorization semantics. Voice may use a low-latency model, but delegates execution to the core; never create a competing agent runtime.
2. Reuse upstream capabilities. Deep Agents is the harness; LangChain supplies model/tool abstractions and middleware; LangGraph supplies agent state, checkpoints, interrupts and explicit orchestration. Hatchet dispatches durable jobs and events. OpenRouter and direct providers sit behind DragonZpyder's authenticated, metered inference gateway. PostgreSQL stores authoritative metadata, goals, receipts and checkpoints; S3-compatible object storage holds binary artifacts; Langfuse records redacted traces. Mem0 is optional and consent-gated. QuickJS is the bounded programmatic composition layer. Do not duplicate these systems.
3. Composition over hardcoding. An agent selects a combination of structured MCP/API calls, programmatic execution (shell/Python/JS), browser/GUI interaction, or specialist intelligence. Prefer reliable, economical deterministic operations over model calls or clicking when appropriate.
4. One capability policy, many providers. Native tools, MCP, model/media adapters, computer tools and external agents have stable IDs, schemas, risk/side-effect classifications, scoped authority, budgets, timeouts, cancellation, receipts and verification requirements. Frequently used native tools can be bound directly; discover rare tools lazily using search/describe/invoke. Keep provider authorization distinct from DragonZpyder policy and human approval.
5. Persistent objectives, not merely sessions. Save goals, dependencies, checkpoints, artifact versions, attempts, approvals, evidence and terminal state. Renew authority on every wake; stop on revocation/expiry/cancellation. Do not conflate retries with exactly-once effects.
6. Human control. Identity is derived by trusted services; never by the model. Consequential actions require explicit approvals according to policy, stable idempotency keys and readback. No broad admin tokens, provider secrets, or browser credentials in model context, traces, checkpoints, sandbox code or job payloads.
7. Preserve boundaries. DragonZpyder owns shared intelligence, Personal identity/state, native tools, computer environments and schedules. Operly owns business tenants, memberships, business data, workspace policy, connectors, approvals and application-specific workflow semantics. Use scoped delegates/MCP; personal identity does not confer workspace rights. Retire redundant intelligence services only after dependency audit, cutover proof and rollback.

## Execution environment

Use Deep Agents backend abstractions rather than replacing its filesystem middleware. A trusted per-run context binds owner, scope, conversation, goal, permissions, budget, deadline and cancellation. Use a composite backend or compatible routing adapter with these logical mounts:

| Mount | Role |
| --- | --- |
| /scratch | bounded agent state and temporary context |
| /workspace | real isolated executable working directory |
| /uploads | authorized immutable input files |
| /artifacts | output staging and durable publication by artifact ID |
| /skills | versioned reviewed instructions, scripts and acceptance criteria |
| /memory | explicitly consented, scoped persistent knowledge |

Keep virtual StateBackend where useful. Implement native filesystem and shell/Python/Git through a remote isolated sandbox; never execute arbitrary commands on the API/worker host. Evaluate the existing signed Operly runner before reusing it. Personal execution needs a genuine Personal authorization contract, not invented workspace IDs. Sandbox access is least privilege with filesystem confinement (including symlinks), no ambient secrets, default-deny network, bounded CPU/RAM/disk/time, output limits, cleanup, leases and audited egress. Prefer structured browser automation (e.g. Playwright) before visual GUI controls. Local devices require separate authenticated device grants and user consent.

## Universal artifacts and multimodal sessions

Store immutable originals and versioned outputs in object storage, with PostgreSQL records for opaque ID, owner/scope, filename, media type, byte size, digest, version, provenance, lifecycle and authorization. Validate file type/size, scan hostile inputs, prevent traversal and archive expansion, and authorize every download, range request, sandbox transfer and publication. Checkpoints hold references rather than raw binary or signed URLs. Expose attachment IDs in first-party chat, structured artifact and progress events, download/preview, cancellation, and cross-device recovery. Independently parse/read back generated artifacts.

Use deterministic document and media libraries (PyMuPDF, python-docx, openpyxl, python-pptx, pandas, Pillow, FFmpeg) in the sandbox. Route image understanding/generation/editing, transcription, speech, audio/video understanding and generation through suitable model adapters, with capability checks and gateway accounting. Text-only models may delegate to vision/audio specialists. Do not silently fall back to a model that lacks the required modality. Realtime voice uses the same authenticated conversation and controlled server-side execution bridge; do not assume direct provider WebRTC sessions already have tools.

## Skills, agent manufacturing and model routing

See [System One routing](system-one-routing.md) for the typed decision-model integration gates, shadow evaluation, and policy boundary.

Use upstream Deep Agents skill loading (reviewed SKILL.md packages with progressive disclosure). Begin with document/spreadsheet creation, software engineering, research, scientific computing, media and browser skills. Skills are procedural knowledge, not authority. Construct task-scoped specialist configurations from approved models, capabilities, skill versions, context and bounded budgets. Dynamic delegation never widens parent grants or budgets; avoid unrestricted recursive spawning. Route by measured suitability, modalities, tool-call correctness, context, cost and latency; support bounded retries and explicit failure rather than inventing tool outputs. Do not train new models when existing intelligence meets the requirement.

Use QuickJS for small programmatic tool compositions; expand existing restricted interpreter only when nested calls inherit authorization, cancellation, approval, audit and atomic parent budget. LangGraph owns durable reasoning; Hatchet owns dispatch and wake/recovery. No custom competing cron, planner or queue.

## Implementation sequence (reviewable increments)

| Package | Scope and acceptance gate |
| --- | --- |
| 1 P0 execution contract | Shared trusted run context, native capability policy, typed receipts, cancellation and atomic budget propagation; fail-closed tests. |
| 2 P0 sandbox backend | Real read/edit/search/shell/Python, scoped Personal and Workspace leases, no host access; run a script and independently verify output, adversarial isolation tests. |
| 3 P0 artifact service | Authenticated upload/download, metadata/object store, sandbox import/export; test cross-owner denial, hostile input, immutable versions, restart recovery. |
| 4 P0 chat integration | Attachment IDs, typed events, actual downloadable artifact, request idempotency, progress and cancellation across web/mobile. |
| 5 P0 multimodal tools | Image inspection/generation, audio transcription/speech, media transformation via gateway and sandbox; real artifact readback and spend evidence. |
| 6 P1 skills and discovery | Native skill loading, lazy capability discovery, task-scoped specialists and safe model routing; no second harness. |
| 7 P1 browser/voice/programmatic work | Structured browser then GUI, realtime tool delegation, QuickJS nested tool calls, durable workflows; security, revocation and cost gates. |
| 8 P0 measurement / P2 continuous improvement | Repeatable acceptance suite and matched-model harness comparisons; traces and failure taxonomy; proposals reviewed and tested before promotion. |

Land small PRs against current integrated branch; inspect concurrent migration PRs and active deployment SHA before changes. Docs-only approval is not permission to deploy, spend or enable feature flags. Implement and validate staging first. Never enable public arbitrary execution before isolation, resource quotas and permission controls pass.

## Definition of done and benchmarking

Run representative real objectives: upload PDF and produce report; analyze spreadsheet and create charts; execute Python and verify output; modify repository and run tests; understand image; generate image; transcribe recording; generate playable speech; research and create presentation with grounded sources; resume after worker restart with artifacts intact. Negative cases: cross-user/scope access, malformed arguments, prompt injection from files/web/tools, path traversal and symlinks, malicious archive, secret leakage, unauthorized shell/egress, revoked grants, duplicate side effects, exhausted budgets and cancellation. Record actual artifact digests, parser/test results, tool receipts, costs and trace IDs. A checked planning list, mock, build, or HTTP success alone is not acceptance.

Evaluate matched models/fixtures/budgets and report repetitions, failures and partial results. References include Terminal-Bench, SWE-bench Verified, OSWorld, WebArena, GAIA, AppWorld and custom multimodal/artifact/persistence tasks. Do not claim state-of-the-art without reproducible comparison.

## Current source baseline and gaps (2026-11-25)

- `harness.py`: Deep Agents StateBackend and virtual ls/read/write/edit/glob/grep; specialists; optional QuickJS with empty programmatic tool list. Not real OS execution.
- `runtime.py`: checkpointed agent execution and bounded parallel experiments; production availability and end-to-end budgets require evidence.
- `computer.py`: signed workspace-scoped transport, not registered as an agent tool; Personal contract and isolation unverified.
- `first_party_chat.py`: native text chat, authenticated owner and MCP account IDs; no attachment IDs in ChatInput.
- `first_party_voice.py`: audio-only WebRTC session with empty tools; not core tool execution.
- `provider_gateway.py`: media routes exist; core multimodal workflow and artifact publication not established.
- Managed MCP/OAuth, identity migration, Hatchet goals, streaming and receipt paths exist in source with gates. Do not infer rollout from code.

Update this baseline when source/CI/production acceptance changes. Preserve historical proofs as dated evidence; do not relabel them as current.

## Upstream references

- [Deep Agents documentation](https://docs.langchain.com/oss/python/deepagents/overview) and [source](https://github.com/langchain-ai/deepagents)
- [LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/overview)
- [OpenCode](https://github.com/anomalyco/opencode), [OpenHands](https://github.com/All-Hands-AI/OpenHands), [Hermes Agent](https://github.com/NousResearch/hermes-agent), [OpenClaw](https://github.com/openclaw/openclaw)
- [MCP specification](https://modelcontextprotocol.io/specification), [Hatchet](https://docs.hatchet.run/), [Playwright](https://playwright.dev/)
- [Anthropic: effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

These are reference patterns, not claims of feature parity or a mandate to import entire runtimes. Verify upstream APIs and licenses at the pinned dependency version.
