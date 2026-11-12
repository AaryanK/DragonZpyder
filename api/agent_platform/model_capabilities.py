"""Operator-only OpenRouter model preflight before paid agent tool use.

A model slug in an allowlist does not establish that it has a tool-capable
provider endpoint. Query a fixed HTTPS catalog URL and check the current
model's advertised tool parameter and context size. An actual live tool smoke
is still necessary; catalogs can be stale. Never fallback to another model
without a separately approved routing and spend policy.
"""
from __future__ import annotations

import httpx

CATALOG_URL = "https://openrouter.ai/api/v1/models"
MAX_CATALOG_BYTES = 5_000_000


class ModelCapabilityUnavailable(RuntimeError):
    pass


def parse_tool_capability(payload: object, model_id: str, *,
                          min_context: int = 8192) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ModelCapabilityUnavailable("Model catalog had an invalid shape")
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("Model ID required")
    matches = [
        model for model in payload["data"]
        if isinstance(model, dict) and model.get("id") == model_id
    ]
    if len(matches) != 1:
        raise ModelCapabilityUnavailable("Requested model missing from trusted catalog")
    model = matches[0]
    params = model.get("supported_parameters")
    if not isinstance(params, list) or "tools" not in params:
        raise ModelCapabilityUnavailable("Requested model has no advertised tool support")
    context = model.get("context_length")
    if type(context) is not int or context < min_context:
        raise ModelCapabilityUnavailable("Requested model context is insufficient or unknown")
    return {"model": model_id, "tools": True, "context_length": context}


async def preflight_tool_model(
    model_id: str, *, client: httpx.AsyncClient | None = None,
    min_context: int = 8192,
) -> dict:
    owned = client is None
    if owned:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(7.0), trust_env=False,
            follow_redirects=False,
        )
    try:
        response = await client.get(
            CATALOG_URL,
            params={"q": model_id, "supported_parameters": "tools"},
            headers={"accept": "application/json"},
        )
        if response.is_redirect or response.status_code != 200:
            raise ModelCapabilityUnavailable("Trusted model catalog unavailable")
        if len(response.content) > MAX_CATALOG_BYTES:
            raise ModelCapabilityUnavailable("Model catalog exceeded response limit")
        try:
            data = response.json()
        except ValueError as exc:
            raise ModelCapabilityUnavailable("Model catalog returned invalid JSON") from exc
        return parse_tool_capability(data, model_id, min_context=min_context)
    except httpx.HTTPError as exc:
        raise ModelCapabilityUnavailable("Model catalog request failed") from exc
    finally:
        if owned:
            await client.aclose()
