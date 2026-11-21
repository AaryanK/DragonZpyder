# DragonZpyder

**One intelligence experience. Many models, tools, and environments. Verified work, not just answers.**

DragonZpyder is building a goal-driven AI execution platform: a single experience where people can direct compatible models, authorized tools, and long-running agents, with durable state, explicit permissions, transparent costs, and verifiable results.

> **The active codebase and up-to-date technical README live on [the `develop` branch](https://github.com/AaryanK/DragonZpyder/blob/develop/README.md).**
>
> GitHub still displays this older `master` branch by default. **Do not use `master` as evidence of the current architecture, production deployment, or feature availability.** Feature flags, production commits, and real execution tests determine what is live.

## Start here

- **[Current README — architecture, status, setup, roadmap](https://github.com/AaryanK/DragonZpyder/blob/develop/README.md)**
- **[Current source — `develop`](https://github.com/AaryanK/DragonZpyder/tree/develop)**
- [DragonZpyder website](https://dragonzpyder.xyz/)
- [Agent harness engineering notes](https://github.com/AaryanK/DragonZpyder/blob/develop/api/agent_platform/README.md)
- [Platform ownership and Operly boundary](https://github.com/AaryanK/DragonZpyder/blob/develop/docs/platform-ownership.md)

## What we're building

An assistant should understand a person's objective, use whichever **permitted** models and tools fit the task, coordinate and resume work over time, and verify the real outcome rather than merely reporting success. DragonZpyder is the intended intelligence and execution layer; Operly supplies governed account, workspace and business actions. A signed-in user's identity is not a blanket grant of access to every tool or business.

As of **November 21, 2026**, the active `develop` branch includes a React/FastAPI web app, authenticated inference gateway, Deep Agents/LangGraph harness, Hatchet workers, PostgreSQL checkpoints, and guarded Operly MCP integration. Production persistence infrastructure has passed bounded tests, but **live, user-scoped Personal MCP execution across multiple scheduled wakes has not been accepted for production**. Features that are merged but disabled are not advertised as launched.

**Research directions** include broader model/app interoperability (AI Mesh), secure computer control, durable goal management, independent completion verification, and a proposed shared usage-credit concept (Project IC / AIC). None should be mistaken for unrestricted access to other providers or a launched currency or wallet.

**[Read the maintained engineering and product overview →](https://github.com/AaryanK/DragonZpyder/blob/develop/README.md)**
