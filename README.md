# DragonZpyder

**Exceptional AI. One connected experience.**

AI is not held in a single laboratory or product. Exceptional models, creative engines, assistants and applications are developed independently, with different capabilities, rules, interfaces and pricing. No single company needs to recreate all of them. **DragonZpyder's mission is to connect the ones that can interoperate, so their combined utility is greater than a collection of disconnected tabs and subscriptions.**

The dots are already there. We want to build the connections.

**[Website](https://www.dragonzpyder.xyz/) · [Personal AI — early access](https://www.dragonzpyder.xyz/app.html) · [Operly](https://operly.dragonzpyder.xyz/) · [Web integration PR](https://github.com/AaryanK/DragonZpyder/pull/9)**

## The thesis

A person should not have to choose a single company's stack for every kind of intelligence. Reasoning, code, research, images, video, speech, scientific tools and specialised applications have different strengths. The useful product is the **interface, orchestration and economic layer** that makes compatible services work together, under the user's direction.

DragonZpyder is being designed around three layers:

1. **AI Mesh — connection and orchestration (planned).** Discover permitted providers, choose a model for a task or delegate bounded work to specialist models and applications; connect outputs into a coherent workflow; preserve user context and control. Integrations depend on published APIs, licensed access, partner agreements and provider terms.
2. **Project IC / AIC — a unified way to spend (research).** A proposed AI Credits balance for metered use of participating models and third-party experiences, with clear per-action prices, usage records and spending ceilings. The idea is *one DragonZpyder budget across participating services*, not automatic access to every product's paid plan.
3. **Operly — governed actions (existing separate product and runtime).** Authenticated tools, permissions, approvals, persistent tasks and execution for real workflows. Operly also serves the existing DragonZpyder Personal client.

The **current Personal AI** is an early interface built on Operly. It is **not** the completed multi-provider AI Mesh or an active AIC wallet.

## The unified spending idea

**Illustration, not available pricing or a launched payment product:** imagine adding **$20** to a DragonZpyder balance, then allocating it among supported tasks: $3 of reasoning, $4 of coding, $8 of video generation and $5 of storytelling-app activity. The person sees costs and approves the spending rather than purchasing four separate subscriptions merely to try each activity.

AIC (AI Credits) would initially be a platform-defined unit of **prepaid usage**, with denomination, conversion, expiry, refunds and redemption disclosed clearly. It is not currently issued as a transferable currency, investment, token or reserve-backed asset. Actual pricing and access require licensed API supply, partner contracts, viable unit economics, fraud controls, tax/payment review and appropriate compliance. A prepaid credit cannot turn a consumer subscription into an API entitlement or make existing unrelated platform credits portable.

## Product map

| Surface | Reality today | Direction |
| --- | --- | --- |
| DragonZpyder Personal | Early access client with conversations and governed Personal actions | Persistent interface for a wider AI ecosystem |
| AI Mesh | Planned; not a general catalogue of active integrations | Compatible model choice, task routing, creative toolchains and third-party applications |
| Project IC / AIC | Research concept; no launched wallet or currency | One clearly metered spending balance for participating services |
| Operly | Separate runtime and product with permissioned workflow capabilities | Backbone for approved tool use, organisation workflows and agent execution |

## What makes the experience worth building

- **Connection over imitation.** Work with the distinctive capabilities of independent AI builders instead of pretending to replace them all.
- **Agency over a model picker.** The user chooses an objective. Compatible tools can handle different stages, exchange authorised outputs and yield a useful outcome.
- **One coherent interface.** Keep work, files, context, hand-offs and reviews together as capabilities change.
- **Transparent economics.** Show usage costs, caps, balances, receipts and provider limitations. A shared budget is only useful if it is predictable.
- **Open participation, not false universality.** Third-party model and app access must be permitted and contractually supported. The ecosystem grows through integration and partnership, not paywall circumvention.
- **People remain in control.** Meaningful external actions require the permissions and approvals of the existing governed runtime.

## System boundaries

```text
                           DragonZpyder interface
                      (intent, context, choice, review)
                                      |
                  +-------------------+-------------------+
                  |                                       |
          AI Mesh — planned                       Project IC — research
       model/app discovery and                 prepaid credits, metering,
       bounded task coordination               spending limits, receipts
                  |                                       |
                  +--------------+------------------------+
                                 |
                  permitted provider APIs and
                   consenting third-party apps
                                 |
                  Operly permissioned execution
                    (where applicable, existing)
```

No UI design can waive a provider's terms. A provider may have no public API, restrictive resale conditions, separate quotas or unavailable capabilities. Integrations and billing must be explicit about those constraints.

## Implementation and repository

**This is the authoritative DragonZpyder repository.** The old `DragonZpyder-Landing` repository remains legacy site history and temporary asset storage. [Web consolidation PR #9](https://github.com/AaryanK/DragonZpyder/pull/9) is stacked on earlier client PRs and is not yet merged into `master`. The website is deployed from its development branch, not from `master`.

On the consolidation branch:

```text
web/                 # Public website + existing Personal AI UI
  index.html         # Ecosystem vision, AI Mesh, Project IC
  app.html           # Early Personal interface
  app.js / app.css   # Existing governed client behavior
  server.mjs         # Railway static server + same-origin /api/* proxy
src/                 # Python Personal client
tests/               # Client tests
docs/                # Engineering documents
```

The currently implemented web path is browser → DragonZpyder Web → Operly Personal Runtime / Kernel. The browser does not contain provider keys or select business/workspace authority.

### Existing Personal client (development branch)

```bash
git checkout codex/consolidate-dragonzpyder-web
python -m pip install --no-deps .
export DRAGONZPYDER_OPERLY_BASE_URL=https://your-operly.example

dragonzpyder login --email you@example.com
dragonzpyder submit "Help me plan my week."
dragonzpyder approvals
dragonzpyder status
```

For durable task handling and the live deployment contract, see the [client source](https://github.com/AaryanK/DragonZpyder/tree/codex/consolidate-dragonzpyder-web/src) and [web README](https://github.com/AaryanK/DragonZpyder/blob/codex/consolidate-dragonzpyder-web/web/README.md). Retry requests with stable identities and reconcile uncertain external effects before attempting them again.

```bash
# Local checks on the consolidation branch
python -m compileall -q src tests scripts
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/check_no_secrets.py
node --check web/app.js
node --check web/home.js
node --check web/server.mjs
```

## Roadmap, without pretending it's shipped

1. Test permitted multi-model integrations and a clear task/model selection experience.
2. Add transparent cost estimates, hard spending limits, usage metering and a conventional auditable ledger.
3. Build a bounded orchestration workflow that crosses reasoning, code and creative providers where permitted.
4. Pilot the AIC balance with compliant payment handling and a small number of participating services.
5. Provide partner integrations for creative apps, educational software and specialised services.
6. Explore compute-market accounting and transferable instruments only if justified and legally appropriate.

## Name and purpose

DragonZpyder takes the **dragon's fire** as creative power and the **spider's web** as connection without captivity—an inspiration from the image of a spider projecting its web while remaining distinct from it. The point is not to own every source of intelligence. It is to weave independent capabilities into something useful, accessible and under human direction.

**Not every dot belongs to one company. The connections can still belong to the people using them.**


## Platform ownership update (October 2026)

DragonZpyder is being established as the **upstream AI inference provider** for
Operly, not merely a frontend for it. The first authenticated internal model
API has been deployed and Operly's Runtime 1.0 adapter is configured to use it.
This does not mean that the personal agent kernel, business data or all Studio
model calls have migrated yet. The phased ownership and security plan is in
[DragonZpyder-first infrastructure migration](docs/platform-ownership.md).
