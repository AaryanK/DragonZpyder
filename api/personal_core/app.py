"""Feature-flagged, low-cost personal AI API. Not an Operly workspace API."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from personal_core.identity import verify, IdentityUnavailable
from personal_core.models import Catalog, choose, approved_models, ModelUnavailable
from personal_core.budget import Budget, BudgetExceeded, hash_principal
from usage_ledger import token_usage

SYSTEM = (
    "You are DragonZpyder, a concise personal assistant. "
    "Never claim to have performed an external action unless a tool result confirms it. "
    "Do not ask for passwords or private access tokens."
)


class HistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=1500)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=3000)
    history: list[HistoryItem] = Field(default_factory=list, max_length=8)
    max_output_tokens: int = Field(default=384, ge=32, le=768)


def gateway_url():
    url = os.getenv("DRAGONZPYDER_PERSONAL_GATEWAY_URL", "")
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or not parsed.hostname or
            not parsed.hostname.endswith(".railway.internal") or
            parsed.path != "/internal/personal/v1/chat/completions" or
            parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise RuntimeError("Trusted private personal gateway URL not configured")
    return url


def gateway_token():
    value = os.getenv("DRAGONZPYDER_PERSONAL_GATEWAY_TOKEN", "")
    if len(value) < 40:
        raise RuntimeError("Personal gateway credential missing")
    return value


catalog = Catalog()
budget = Budget()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("DRAGONZPYDER_PERSONAL_ENABLED") == "1":
        gateway_url()
        gateway_token()
        await budget.start(os.getenv("DRAGONZPYDER_PERSONAL_DATABASE_URL", ""))
    try:
        async with httpx.AsyncClient(timeout=70, follow_redirects=False) as client:
            app.state.http = client
            yield
    finally:
        await budget.stop()


app = FastAPI(title="DragonZpyder Personal Core", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security(request, call_next):
    response = await call_next(request)
    response.headers["cache-control"] = "no-store"
    response.headers["access-control-allow-origin"] = "null"
    response.headers["x-frame-options"] = "DENY"
    response.headers["x-content-type-options"] = "nosniff"
    return response


@app.get("/healthz")
async def health():
    return {"service": "dragonzpyder-personal-core",
            "status": "online", "personal_enabled":
            os.getenv("DRAGONZPYDER_PERSONAL_ENABLED") == "1",
            "public_registration_enabled": False}


def authenticated(authorization: str) -> str:
    if os.getenv("DRAGONZPYDER_PERSONAL_ENABLED") != "1":
        raise HTTPException(503, "Personal API not yet enabled")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "OIDC access token required")
    try:
        identity = verify(authorization[7:])
        return hash_principal(identity.issuer, identity.subject)
    except IdentityUnavailable:
        raise HTTPException(503, "Identity service not ready") from None
    except ValueError:
        raise HTTPException(401, "Access token rejected") from None
    except RuntimeError:
        raise HTTPException(503, "Identity not configured") from None


@app.get("/v1/me/budget")
async def budget_info(authorization: str = Header(default="")):
    user = authenticated(authorization)
    try:
        return await budget.summary(user)
    except Exception:
        raise HTTPException(503, "Budget store unavailable") from None


@app.post("/v1/chat")
async def chat(payload: ChatRequest, authorization: str = Header(default="")):
    principal = authenticated(authorization)
    if budget.pool is None:
        raise HTTPException(503, "Budget store unavailable")
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs.extend(item.model_dump() for item in payload.history)
    msgs.append({"role": "user", "content": payload.message})
    input_bytes = sum(len(m["content"].encode("utf-8")) for m in msgs)
    try:
        models = await catalog.get(app.state.http)
        chosen = choose(models, approved_models(), input_bytes=input_bytes,
                        output_tokens=payload.max_output_tokens)
    except ModelUnavailable:
        raise HTTPException(503, "Affordable approved model unavailable") from None
    try:
        hold = await budget.reserve(principal, chosen.reserve_micro_usd)
    except BudgetExceeded:
        raise HTTPException(429, "Personal daily budget reached") from None
    except Exception:
        raise HTTPException(503, "Unable to reserve user budget") from None
    body = {"model": chosen.model, "messages": msgs, "max_tokens":
            payload.max_output_tokens, "temperature": 0.3}
    try:
        response = await app.state.http.post(
            gateway_url(), json=body,
            headers={"Authorization": "Bearer " + gateway_token()},
        )
    except httpx.HTTPError:
        # Reservation intentionally held if provider may have charged.
        raise HTTPException(502, "Model gateway unavailable") from None
    if response.status_code != 200:
        raise HTTPException(429 if response.status_code == 429 else 502,
                            "Personal inference failed") from None
    try:
        result = response.json()
        text = result["choices"][0]["message"]["content"]
        if not isinstance(text, str) or len(text) > 90000:
            raise ValueError("Invalid model content")
        usage = token_usage(result)
        await budget.settle(hold, usage["provider_cost_usd"])
    except Exception:
        raise HTTPException(502, "Inference result could not be verified") from None
    try:
        remaining = await budget.summary(principal)
    except Exception:
        remaining = None
    return {"answer": text, "model": chosen.model,
            "reported_provider_cost_usd": (
                str(usage["provider_cost_usd"])
                if usage["provider_cost_usd"] is not None else None
            ),
            "cost_confirmed": usage["provider_cost_usd"] is not None,
            "remaining_budget": remaining}
