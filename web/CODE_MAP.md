# web — navigation

Web frontend, FastAPI gateway and compatibility adapters.

Start at [CODEBASE.md](../CODEBASE.md), [file inventory](../docs/codebase/FILE_INDEX.md) and [execution flows](../docs/codebase/IMPLEMENTATION.md). For current checkout-specific symbols, dependency candidates and tests, generate the source index. Keep this guide current with changes to this directory.

## Child directories

- [backend](backend/)
- [frontend](frontend/)
- [tests](tests/)

## Files

| Path | Responsibility / navigation | Evidence |
| --- | --- | --- |
| [`Dockerfile`](Dockerfile) | Node 22 Vite build/test stage followed by non-root Python 3.12 FastAPI runtime. | Reviewed |
| [`Procfile`](Procfile) | Navigation hint: Procfile; source behavior not independently reviewed. | Indexed |
| [`README.md`](README.md) | Documentation: README; check date and canonical status. | Indexed |
| [`account.css`](account.css) | Stylesheet: account; inspect selectors and importing page. | Indexed |
| [`account.js`](account.js) | Navigation hint: account; source behavior not independently reviewed. | Indexed |
| [`app.css`](app.css) | Stylesheet: app; inspect selectors and importing page. | Indexed |
| [`app.js`](app.js) | Transitional Personal chat controller: sessions, conversations, request sending, approval UI and runtime status. | Reviewed |
| [`chat.html`](chat.html) | Navigation hint: chat; source behavior not independently reviewed. | Indexed |
| [`companion.js`](companion.js) | Navigation hint: companion; source behavior not independently reviewed. | Indexed |
| [`dictation.js`](dictation.js) | Navigation hint: dictation; source behavior not independently reviewed. | Indexed |
| [`image-progress.mjs`](image-progress.mjs) | Navigation hint: image progress; source behavior not independently reviewed. | Indexed |
| [`internal-inference.mjs`](internal-inference.mjs) | Navigation hint: internal inference; source behavior not independently reviewed. | Indexed |
| [`main.py`](main.py) | FastAPI compiled-page server, native API and compatibility proxy dispatch, admin protection and security headers. | Reviewed |
| [`mesh-picker.js`](mesh-picker.js) | Navigation hint: mesh picker; source behavior not independently reviewed. | Indexed |
| [`mesh-server.mjs`](mesh-server.mjs) | Navigation hint: mesh server; source behavior not independently reviewed. | Indexed |
| [`mesh.css`](mesh.css) | Stylesheet: mesh; inspect selectors and importing page. | Indexed |
| [`mesh.js`](mesh.js) | Navigation hint: mesh; source behavior not independently reviewed. | Indexed |
| [`package.json`](package.json) | Data/configuration fixture: package; inspect schema and consumers. | Indexed |
| [`privacy.html`](privacy.html) | Navigation hint: privacy; source behavior not independently reviewed. | Indexed |
| [`realtime-server.mjs`](realtime-server.mjs) | Navigation hint: realtime server; source behavior not independently reviewed. | Indexed |
| [`requirements.txt`](requirements.txt) | Navigation hint: requirements; source behavior not independently reviewed. | Indexed |
| [`robots.txt`](robots.txt) | Navigation hint: robots; source behavior not independently reviewed. | Indexed |
| [`script.js`](script.js) | Navigation hint: script; source behavior not independently reviewed. | Indexed |
| [`server.mjs`](server.mjs) | Navigation hint: server; source behavior not independently reviewed. | Indexed |
| [`sitemap.xml`](sitemap.xml) | Navigation hint: sitemap; source behavior not independently reviewed. | Indexed |
| [`terms.html`](terms.html) | Navigation hint: terms; source behavior not independently reviewed. | Indexed |
| [`ui-v1.css`](ui-v1.css) | Stylesheet: ui v1; inspect selectors and importing page. | Indexed |
| [`workspace.css`](workspace.css) | Stylesheet: workspace; inspect selectors and importing page. | Indexed |

Reviewed entries are source-inspected summaries; indexed entries are navigation only. Neither proves deployment.
