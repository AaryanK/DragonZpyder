# DragonZpyder Python FastAPI runtime

## Web templates

The existing public index, account and Personal AI HTML, CSS and vanilla JS remain unchanged.
Python `web/main.py` serves only explicitly allowlisted files and retains existing routes:
`/api/*` to Operly, `/mesh/*` for AI Mesh, `/companion/realtime` for voice, and
`/internal/v1/*` to the DragonZpyder API service.

## Services

- `api/main.py`: private server-to-server inference API; no browser cookie authentication.
- `web/main.py`: frontend static gateway and session-bound model and voice endpoints.
- Both services run `uvicorn main:app --host 0.0.0.0 --port $PORT`, in their own
  Docker build root.
- Railway should use the existing source branch and root directories `api` and `web`.
  Update the existing explicit `npm start` start commands to use uvicorn after checks pass.
- OpenRouter and realtime provider keys remain server-side.
- Image/video are disabled unless `MESH_ENABLE_IMAGE` or `MESH_ENABLE_VIDEO`
  is explicitly enabled, with enforceable upstream spending controls.
- Existing in-process quotas are not durable cost metering; use a provider-level budget.

## Local tests

```bash
python -m pip install -r api/requirements.txt pytest
python -m pytest -q api/tests/test_fastapi_gateway.py
python -m pip install -r web/requirements.txt
python -m pytest -q web/tests/test_fastapi_web.py
```

## Rollback

Until production smoke tests and parity checks are complete, the existing Node server
modules are retained in Git. Revert each Railway start command to `npm start` and its
prior deployment if necessary. Node modules can be removed in a later cleanup once
Python handles production traffic reliably.
