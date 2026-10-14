# Querypedia — DragonZpyder's queryable Wikipedia reader

An independent Wikipedia-based reader intended for https://querypedia.dragonzpyder.xyz/wiki/{existing_wikipedia_page}. Uses Wikipedia's official MediaWiki REST API and DragonZpyder's private model gateway. This does not host a full copy of Wikipedia; articles are fetched on demand and temporarily cached.

## Routes
- GET / — encyclopedia search/home page
- GET /wiki/Alan_Turing — reader for an existing Wikipedia page
- GET /api/search?q=alan+turing — search Wikipedia
- GET /api/page/Alan_Turing — sanitised article markup, source, revision, licence
- POST /api/ask with JSON {"title":"Alan_Turing","question":"What was his contribution?"} — grounded answer
- GET /healthz — service health

## Deploy
- Use repository AaryanK/DragonZpyder, branch codex/querypedia-wikipedia-agent and root directory /querypedia for a separate Railway service.
- Dockerfile uses Python 3.12 and uvicorn on the Railway PORT.
- Attach querypedia.dragonzpyder.xyz as a custom domain; set the Railway-provided DNS records.
- Configure DRAGONZPYDER_RUNTIME_TOKEN to the same private secret used by the DragonZpyder API. Do not expose it in browser code or git.
- Set DRAGONZPYDER_API_URL=http://dragonzpyder-api.railway.internal:8080 (or public HTTPS API if private DNS cannot resolve).
- Set QUERYPEDIA_MODEL=openai/gpt-oss-120b (must be allowed by the DragonZpyder gateway).
- Set WIKIMEDIA_USER_AGENT to an identifiable client string with a contact address, following the Wikimedia policy.

## Protections and limitations
- HTML is sanitised server-side before being inserted into the reader.
- Original article link, revision, licence, and contributor history remain available.
- Article questions retrieve selected excerpts of the currently open page; this is not cross-Wikipedia semantic retrieval.
- Inference requests use the server-side DragonZpyder gateway; no browser receives the provider token.
- Per-instance ask rate limits are a protective baseline, not a commercial production quota mechanism. Add shared rate limits plus identity/credits before scaling.
- The bounded cache holds up to 30 articles per process for 10 minutes; there is no bulk scraping.
- Images have their own licences, separate from article text.
