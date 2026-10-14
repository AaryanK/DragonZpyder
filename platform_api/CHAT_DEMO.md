# DragonZpyder Chat Lab — private OpenRouter multimodal demo

This is a **standalone FastAPI prototype** under `platform_api/`. It does not
replace the existing Node API or expose Operly's personal/business data.

## What works

- Simple stateless chat sessions with history stored in the browser tab.
- Text prompts and image understanding (PNG/JPEG/WebP) via OpenRouter multimodal chat.
- PDF uploads (OpenRouter `file` content, `cloudflare-ai` parser).
- DOCX and UTF-8 TXT/MD/CSV/JSON/PY/LOG files, extracted by the server and
  attached as bounded text content.
- Operator allowlisted models, size validation, restricted input lengths,
  single-process 12 calls/hour demo throttling and a password-gated browser UI.
- Backend-only OpenRouter key; the browser never receives provider keys.
- No stored chats, uploaded files, business permissions or database dependency.

**Not yet supported:** image generation, audio/video, OCR guarantees, tools,
streaming, account login, durable spend accounting, file search/indexing or
persistent conversations. Attachments are per-request. Models must support image
input for image analysis; DOCX text extraction does not preserve all styling.

## Development

```bash
cd platform_api
python -m pip install -r requirements.txt
export OPENROUTER_API_KEY=your-provider-key
export DRAGONZPYDER_CHAT_PASSWORD='choose-a-unique-secret-at-least-16-characters'
export DRAGONZPYDER_CHAT_MODELS='google/gemini-2.5-flash,openai/gpt-4o-mini'
uvicorn dragonzpyder_platform.main:app --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000/chat` for the demo UI. Demo cookie is marked Secure
and therefore requires HTTPS for login; in local testing, place the service
behind an HTTPS reverse proxy (or use the hosted Railway test domain).

## Railway deployment (new service only)

- Project: `DRAGONZPYDER` (separate from Operly)
- GitHub repository: `AaryanK/DragonZpyder`
- Branch: `codex/openrouter-multimodal-chat-demo`
- Root directory: `platform_api`
- Start: `uvicorn dragonzpyder_platform.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Health check: `/healthz` (process liveness). `/readyz` is not yet provided.
- Mandatory variables: `OPENROUTER_API_KEY` and `DRAGONZPYDER_CHAT_PASSWORD`.
  Use a unique, random 16+-character password. Limit spend on the OpenRouter
  key itself before sharing a public test URL.
- Optional: `DRAGONZPYDER_CHAT_MODELS` (comma-separated allowlist).
- Never grant the demo credentials access to business data or privileged tools.

Demo rate limits use an in-memory bucket and are not billing guarantees.
Use provider-side key spending caps; rate and usage governance must be moved
into durable DragonZpyder stores before broad availability.

`GET /healthz` reports `bootstrap-only` and `runtime_ready: false`,
because the full agent platform migration remains incomplete even when
this standalone model chat works.

## Endpoint summary

`GET /chat` — browser app.
`GET /demo/session` — authenticated session + configured models.
`POST /demo/login`, `POST /demo/logout` — password-backed secure cookie.
`POST /demo/chat` — authenticated chat with optional base64 attachments.
Mutations require a same-origin request and `X-DragonZpyder-Chat: 1`.
All external LLM traffic goes only to OpenRouter's HTTPS chat endpoint.

## Tests

```bash
cd platform_api
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Tests mock provider calls and **do not spend OpenRouter credits**.
