# DragonZpyder — repository instructions

Before changing agent/runtime, tools, providers, media, filesystem, workflows, identity, or clients, read [the canonical Universal Harness V4 contract](docs/universal-harness-v4.md) and [platform ownership](docs/platform-ownership.md). Apply these instructions across the repository. For implementation, inspect current source, pending PRs, dependencies and tests; historical docs are evidence, not authority on present runtime.

- Mission: humans express objectives; DragonZpyder orchestrates available intelligence and authorized computing resources to deliver verified work. It is not merely chat or coding.
- Retain Deep Agents + LangGraph as the one core harness; use LangChain middleware, backend and skill primitives. Hatchet handles durable dispatch; PostgreSQL stores state and metadata; gateway routes/meters models; object storage stores binary artifacts. Do not introduce competing frameworks, planners, queues or voice agents.
- Generalize capability discovery and execution across MCP/API, native files/sandbox, programmatic tools, browser/GUI, media and specialist models. Reuse existing components before adding dependencies.
- Keep Personal identity and intelligence owned by DragonZpyder; Operly owns business tenancy, authorization, data, policies and application-specific workflow execution. Never infer workspace authority from a Personal login.
- Enforce trusted identity, scope, live authorization, consent, approval, idempotency, atomic budgets, bounded execution, cancellation and verifiable receipts. Never expose secrets in model context, checkpoints or sandbox; never execute untrusted commands on the API host.
- Apply [minimum harness release acceptance](docs/harness-release-acceptance.md) to every harness change: 100 held-out workflows, >=80 verified outcomes, >=95% interruption recovery, zero observed safety/replay/false-completion/spend/crash incidents, mandatory real-system probes. Do not substitute CI for qualification.
- Use real sandbox/artifact readback and objective-specific oracles. Test unauthorized access, revocation, replay, restart, cancellation and budget exhaustion. Do not claim deployed or verified features from source, mocks, green CI, or assistant prose.
- Implement V4 in small dependency-ordered PRs. Keep the architecture document and status current as changes land. Confirm actual deployed SHA and acceptance evidence before claiming production readiness. Preserve rollback and do not remove live dependencies prematurely.

Do not treat a design decision as authorization to enable production flags, incur unapproved paid tests, deploy services or widen permissions.
