# DragonZpyder

**An intelligence that stays with you.**

DragonZpyder is the personal interface to useful AI: a place to reason, work with connected information, and take carefully authorised actions. Models and interfaces will change. Your context, preferences, permissions, and relationship with the system should not have to start over each time.

**[Website](https://dragonzpyder.xyz/) · [Personal AI](https://dragonzpyder.xyz/app.html) · [Operly](https://operly.dragonzpyder.xyz/)**

## What we're building

We start with a practical personal assistant, not a catalogue of model names. DragonZpyder provides the experience; **Operly provides the governed execution infrastructure**—authentication, capability discovery, approval checks, durable tasks, integrations, and execution. Sensitive credentials and business/workspace authority stay on the server.

The broader direction is an interoperable **AI Mesh**: compatible models and specialist creative or software tools, brought together under explicit user permission and visible cost controls. **Project IC** is separate, early-stage research into metered access and accounting among consenting AI-service partners. A universal wallet, transferable credits, cross-provider subscription sharing, and compute-backed currency are **not launched features**.

| Area | Status | Purpose |
| --- | --- | --- |
| DragonZpyder Personal | Early access / active development | Personal conversations, connected capabilities, and reviewed actions |
| Operly | Separate product and runtime | Workspaces, permissions, approvals, integrations, and execution |
| AI Mesh | Planned | Model-agnostic access, bounded delegation, and usage controls |
| Project IC | Research | Auditable consumption and partner settlement, subject to commercial and regulatory work |

## Design principles

1. **Useful before impressive.** Build functioning workflows; show what the product does rather than promising general intelligence.
2. **Continuity over lock-in.** Separate the person's context and permissions from a particular model.
3. **Permission before action.** Show consequential actions for review. Do not blur a personal account into business/workspace authority.
4. **Clarity over spectacle.** Plain language, legible interfaces, real status information, and transparent limitations.
5. **Broad access.** Design for different languages, devices, budgets, and technical experience.

The name combines the creative force of fire with the image of a spider weaving a web without becoming trapped by it: connections should expand human capability, not constrain it.

## Repositories and architecture

**This is the authoritative DragonZpyder repository.** The former `DragonZpyder-Landing` repository is legacy website history and temporary asset storage, not the long-term product source.

The web consolidation is being integrated in [PR #9](https://github.com/AaryanK/DragonZpyder/pull/9). Until that work merges, some paths below exist on its development branch rather than on `master`.

```text
DragonZpyder/
├── web/                 # Public site + Personal AI frontend (web consolidation branch)
│   ├── index.html       # Public website
│   ├── app.html         # Personal interface
│   ├── app.js / app.css
│   └── server.mjs       # Same-origin gateway for /api/*
├── src/                 # Python Personal client (development branch)
├── tests/               # Client validation
└── docs/                # Design and implementation notes
```

```text
Browser / Personal CLI
       │
       ▼
DragonZpyder (Personal-only interface)
       │ HTTPS, authenticated & retry-safe
       ▼
Operly Personal Runtime + Execution Kernel
       │ permissions · approvals · durable tasks · auditing
       ▼
Approved connected tools and model providers
```

The web service is designed to run from `web/` on Railway, with `npm start`, `/healthz`, and a server-side `OPERLY_ORIGIN` override when required. The default upstream is `https://operly.dragonzpyder.xyz`. Do not put model keys, third-party access tokens, or administrative credentials in browser code.

## Personal client (development branch)

```bash
git checkout codex/consolidate-dragonzpyder-web
python -m pip install --no-deps .
export DRAGONZPYDER_OPERLY_BASE_URL=https://your-operly.example

dragonzpyder login --email you@example.com
dragonzpyder submit "Help me plan my week."
dragonzpyder approvals
dragonzpyder status
```

For durable actions and approval recovery, see [the client implementation](src/) and [web deployment guide](web/README.md) **on the consolidation branch**. Keep request identities stable when retrying and never blindly repeat an externally uncertain action.

## Validate

On the consolidation branch:

```bash
python -m compileall -q src tests scripts
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/check_no_secrets.py
node --check web/server.mjs
node --check web/app.js
node --check web/home.js
```

## An open-ended vision, a grounded starting point

DragonZpyder should make intelligence useful to individuals and, through Operly, to the people running real organisations. Future systems may connect creative work, software, education, science, and industry. That ambition does not change what must be demonstrated today: software that works, honest descriptions of what is available, and user control over actions and spending.

See [the consolidation PR](https://github.com/AaryanK/DragonZpyder/pull/9) for current web work and deployment/cutover notes.
