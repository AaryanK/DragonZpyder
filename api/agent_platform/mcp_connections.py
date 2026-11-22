"""Operator-reviewed, user-scoped OAuth connection lifecycle for MCP.

This module is NOT an MCP protocol client. MCP requests still pass through
mcp_broker and the upstream LangChain MCP adapter. Authentication uses Authlib;
the backend owns all credentials and never serializes them to agent state.
"""
from __future__ import annotations

import base64
from contextlib import asynccontextmanager
import hashlib
import ipaddress
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet, MultiFernet, InvalidToken

_ID = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")
_TOOL = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_MAX_METADATA = 32768
_NOW = lambda: datetime.now(timezone.utc)


class ConnectionDenied(PermissionError):
    pass


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_https(url: str, *, allow_path: bool = True) -> str:
    """Validate scheme and authority; network egress must ALSO be enforced."""
    if not isinstance(url, str) or not 8 < len(url) <= 2048:
        raise ConnectionDenied("Invalid reviewed HTTPS endpoint")
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ConnectionDenied("Literal IP endpoints are forbidden")
    if (p.scheme != "https" or p.port not in (None, 443) or not host
            or "." not in host or host == "localhost"
            or host.endswith((".localhost", ".internal", ".local", ".test"))
            or p.username or p.password or p.query or p.fragment
            or (not allow_path and p.path not in ("", "/"))):
        raise ConnectionDenied("Unapproved remote origin")
    return url


def _same_origin(url: str, issuer: str) -> str:
    _safe_https(url)
    a, b = urlsplit(url), urlsplit(issuer)
    if (a.scheme, a.hostname, a.port) != (b.scheme, b.hostname, b.port):
        raise ConnectionDenied("Authorization endpoint escapes pinned issuer")
    return url


def _scopes(value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    tokens = value.split() if isinstance(value, str) else value
    if (not isinstance(tokens, (tuple, list)) or len(tokens) > 32
            or any(not isinstance(s, str) or not re.fullmatch(r"[A-Za-z0-9:._/-]{1,100}", s)
                   for s in tokens)):
        raise ConnectionDenied("Invalid OAuth scopes")
    return tuple(dict.fromkeys(tokens))


@dataclass(frozen=True)
class ReviewedProvider:
    provider_id: str
    mcp_url: str
    issuer: str
    readonly_tools: frozenset[str]
    scheduled_tools: frozenset[str]
    requested_scopes: tuple[str, ...]
    registration: str
    client_id: str = ""
    client_secret_env: str = ""
    token_endpoint_auth_method: str = "none"
    client_id_metadata_url: str = ""
    description: str = ""

    @classmethod
    def parse(cls, row: dict) -> "ReviewedProvider":
        if not isinstance(row, dict) or set(row) - {
            "provider_id", "mcp_url", "issuer", "readonly_tools", "scheduled_tools", "requested_scopes",
            "registration", "client_id", "client_secret_env", "token_endpoint_auth_method", "client_id_metadata_url",
            "description",
        }:
            raise ConnectionDenied("Invalid reviewed provider manifest")
        provider_id = row["provider_id"]
        if not isinstance(provider_id, str) or not _ID.fullmatch(provider_id) or provider_id == "operly":
            raise ConnectionDenied("Invalid or reserved MCP provider ID")
        url = _safe_https(row["mcp_url"])
        issuer = _safe_https(row["issuer"])
        tools = row["readonly_tools"]
        if (not isinstance(tools, list) or not 1 <= len(tools) <= 40
                or any(not isinstance(t, str) or not _TOOL.fullmatch(t) for t in tools)
                or len(tools) != len(set(tools))):
            raise ConnectionDenied("Provider tools require independent read-only review")
        scheduled = row.get("scheduled_tools", [])
        if (not isinstance(scheduled, list) or len(set(scheduled)) != len(scheduled)
                or not set(scheduled) <= set(tools)):
            raise ConnectionDenied("Scheduled tool policy must be independently reviewed")
        mode = row.get("registration", "pre_registered")
        if mode not in ("pre_registered", "client_id_metadata", "dynamic"):
            raise ConnectionDenied("Unsupported client registration mechanism")
        client_id = row.get("client_id", "")
        metadata_url = row.get("client_id_metadata_url", "")
        secret_env = row.get("client_secret_env", "")
        if mode == "pre_registered" and (not isinstance(client_id, str) or not 1 <= len(client_id) <= 512):
            raise ConnectionDenied("Pre-registered OAuth client ID required")
        if mode == "client_id_metadata":
            _safe_https(metadata_url)
            if client_id or secret_env:
                raise ConnectionDenied("Metadata URL must be the client ID")
        if secret_env and (not isinstance(secret_env, str) or
                           not re.fullmatch(r"[A-Z][A-Z0-9_]{4,100}", secret_env)):
            raise ConnectionDenied("Invalid secret environment reference")
        auth_method = row.get("token_endpoint_auth_method",
                              "client_secret_basic" if secret_env else "none")
        if auth_method not in ("none", "client_secret_post", "client_secret_basic"):
            raise ConnectionDenied("Unsupported client authentication method")
        if mode == "client_id_metadata" and auth_method != "none":
            raise ConnectionDenied("Client metadata method cannot use a shared secret")
        description = row.get("description", "")
        if not isinstance(description, str) or len(description) > 500:
            raise ConnectionDenied("Invalid provider description")
        return cls(provider_id, url, issuer, frozenset(tools), frozenset(scheduled),
                   _scopes(row.get("requested_scopes", [])), mode,
                   client_id, secret_env, auth_method, metadata_url, description)


def reviewed_providers() -> dict[str, ReviewedProvider]:
    """Admin-controlled only. User/model input cannot register server URLs."""
    raw = os.getenv("DRAGONZPYDER_MCP_OAUTH_PROVIDERS_JSON", "[]")
    if len(raw.encode()) > 300000:
        raise ConnectionDenied("Provider registry exceeds limit")
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) > 100:
        raise ConnectionDenied("Invalid operator registry")
    providers = [ReviewedProvider.parse(row) for row in rows]
    if len({p.provider_id for p in providers}) != len(providers):
        raise ConnectionDenied("Duplicate reviewed provider")
    return {p.provider_id: p for p in providers}


def require_gate() -> None:
    if (os.getenv("DRAGONZPYDER_MCP_USER_CONNECTIONS_ENABLED") != "1"
            or os.getenv("DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED") != "1"):
        raise ConnectionDenied("Third-party MCP connections are disabled")
    if (os.getenv("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production"
            and os.getenv("DRAGONZPYDER_MCP_USER_CONNECTIONS_PRODUCTION_APPROVED") != "1"):
        raise ConnectionDenied("Third-party MCP production rollout is forbidden")



@asynccontextmanager
async def _reuse_db(pool, current):
    """Use the caller's locked transaction to avoid exhausting the pool."""
    if current is not None:
        yield current
    else:
        async with pool.acquire() as conn:
            yield conn


class CredentialCipher:
    def __init__(self, keyring: str | None = None):
        raw = keyring if keyring is not None else os.getenv("DRAGONZPYDER_MCP_FERNET_KEYS", "")
        keys = [k.strip().encode("ascii") for k in raw.split(",") if k.strip()]
        if not keys:
            raise ConnectionDenied("MCP encryption keys are not configured")
        try:
            self._fernet = MultiFernet([Fernet(k) for k in keys])
        except (ValueError, base64.binascii.Error) as error:
            raise ConnectionDenied("Invalid MCP encryption keyring") from error

    def seal(self, owner: str, identity: str, data: dict) -> bytes:
        plaintext = json.dumps({"owner": owner, "identity": identity, "payload": data},
                               separators=(",", ":"), sort_keys=True).encode()
        return self._fernet.encrypt(plaintext)

    def open(self, owner: str, identity: str, ciphertext: bytes) -> dict:
        try:
            data = json.loads(self._fernet.decrypt(bytes(ciphertext)))
            if (data["owner"], data["identity"]) != (owner, identity) or not isinstance(data["payload"], dict):
                raise ValueError("Encrypted principal mismatch")
            return data["payload"]
        except (InvalidToken, ValueError, KeyError, TypeError, UnicodeError) as error:
            raise ConnectionDenied("Stored MCP credentials rejected") from error


async def _json_get(client: httpx.AsyncClient, url: str) -> dict:
    _safe_https(url)
    async with client.stream("GET", url, headers={"Accept": "application/json"}) as response:
        if response.status_code != 200:
            raise ConnectionDenied("OAuth metadata is unavailable")
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > _MAX_METADATA:
                raise ConnectionDenied("OAuth metadata exceeds bound")
    try:
        result = json.loads(body)
    except (ValueError, UnicodeError) as error:
        raise ConnectionDenied("Invalid OAuth metadata") from error
    if not isinstance(result, dict):
        raise ConnectionDenied("Invalid OAuth metadata")
    return result


def _resource_metadata_urls(resource: str) -> tuple[str, str]:
    p = urlsplit(resource)
    path = p.path.rstrip("/")
    return (
        urlunsplit((p.scheme, p.netloc, "/.well-known/oauth-protected-resource" + path, "", "")),
        urlunsplit((p.scheme, p.netloc, "/.well-known/oauth-protected-resource", "", "")),
    )


def _issuer_metadata_urls(issuer: str) -> tuple[str, str, str]:
    p = urlsplit(issuer)
    path = p.path.rstrip("/")
    return (
        urlunsplit((p.scheme, p.netloc, "/.well-known/oauth-authorization-server" + path, "", "")),
        urlunsplit((p.scheme, p.netloc, "/.well-known/openid-configuration" + path, "", "")),
        issuer.rstrip("/") + "/.well-known/openid-configuration",
    )


async def discover_oauth(provider: ReviewedProvider, client: httpx.AsyncClient) -> dict:
    """RFC 9728 + RFC 8414/OIDC discovery; exact issuer pinned by operator."""
    resource = None
    for url in _resource_metadata_urls(provider.mcp_url):
        try:
            candidate = await _json_get(client, url)
        except ConnectionDenied:
            continue
        if candidate.get("resource") == provider.mcp_url:
            resource = candidate
            break
    if (not resource or not isinstance(resource.get("authorization_servers"), list)
            or provider.issuer not in resource["authorization_servers"]):
        raise ConnectionDenied("MCP protected resource does not advertise pinned issuer")
    metadata = None
    for url in dict.fromkeys(_issuer_metadata_urls(provider.issuer)):
        try:
            candidate = await _json_get(client, url)
        except ConnectionDenied:
            continue
        if candidate.get("issuer") == provider.issuer:
            metadata = candidate
            break
    if not metadata or "S256" not in metadata.get("code_challenge_methods_supported", []):
        raise ConnectionDenied("Authorization server did not confirm PKCE S256")
    for key in ("authorization_endpoint", "token_endpoint"):
        if not isinstance(metadata.get(key), str):
            raise ConnectionDenied("Incomplete OAuth discovery")
        _same_origin(metadata[key], provider.issuer)
    for key in ("registration_endpoint", "revocation_endpoint"):
        if key in metadata:
            _same_origin(metadata[key], provider.issuer)
    if "code" not in metadata.get("response_types_supported", ["code"]):
        raise ConnectionDenied("OAuth code flow unsupported")
    if "authorization_code" not in metadata.get("grant_types_supported", ["authorization_code"]):
        raise ConnectionDenied("OAuth code grant unsupported")
    return metadata


class OAuthConnectionManager:
    """Server-only authority. Uses a dedicated PostgreSQL pool supplied by the app."""

    def __init__(self, pool, cipher: CredentialCipher, *, http=None):
        self.pool = pool
        self.cipher = cipher
        self.http = http  # injectable for offline tests

    def _http(self):
        return self.http or httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False)

    async def _client_credentials(self, provider: ReviewedProvider, meta: dict, http, *, db=None) -> dict:
        if provider.registration == "pre_registered":
            secret = os.getenv(provider.client_secret_env, "") if provider.client_secret_env else ""
            if provider.client_secret_env and not secret:
                raise ConnectionDenied("Registered client secret is missing")
            return {"client_id": provider.client_id, "client_secret": secret,
                    "token_endpoint_auth_method": provider.token_endpoint_auth_method}
        if provider.registration == "client_id_metadata":
            return {"client_id": provider.client_id_metadata_url, "client_secret": "",
                    "token_endpoint_auth_method": "none"}
        endpoint = meta.get("registration_endpoint")
        if not endpoint:
            raise ConnectionDenied("Authorization server does not support dynamic registration")
        _same_origin(endpoint, provider.issuer)
        async with _reuse_db(self.pool, db) as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", provider.provider_id)
                row = await conn.fetchrow(
                    "SELECT issuer, encrypted_client FROM dz_mcp_oauth_clients WHERE provider_id=$1",
                    provider.provider_id,
                )
                if row:
                    if row["issuer"] != provider.issuer:
                        raise ConnectionDenied("OAuth client issuer changed")
                    return self.cipher.open("client", provider.provider_id, row["encrypted_client"])
                response = await http.post(endpoint, json={
                    "client_name": "DragonZpyder",
                    "redirect_uris": [callback_url()],
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                    "scope": " ".join(provider.requested_scopes),
                }, headers={"Accept": "application/json"}, timeout=10)
                if response.status_code not in (200, 201) or len(response.content) > _MAX_METADATA:
                    raise ConnectionDenied("OAuth client registration rejected")
                result = response.json()
                if (not isinstance(result, dict) or not isinstance(result.get("client_id"), str)
                        or len(result["client_id"]) > 512
                        or result.get("token_endpoint_auth_method", "none") not in ("none", "client_secret_post", "client_secret_basic")):
                    raise ConnectionDenied("Invalid registered OAuth client")
                info = {"client_id": result["client_id"],
                        "client_secret": result.get("client_secret", ""),
                        "token_endpoint_auth_method": result.get("token_endpoint_auth_method", "none")}
                await conn.execute(
                    "INSERT INTO dz_mcp_oauth_clients(provider_id, issuer, encrypted_client) VALUES($1,$2,$3)",
                    provider.provider_id, provider.issuer,
                    self.cipher.seal("client", provider.provider_id, info),
                )
                return info

    async def begin(self, *, owner: str, session_secret: str, provider_id: str,
                    label: str = "") -> str:
        require_gate()
        provider = reviewed_providers().get(provider_id)
        if not provider or not owner or len(session_secret) < 20 or len(label) > 80:
            raise ConnectionDenied("Invalid connection request")
        own = self.http is None
        http = self._http()
        try:
            meta = await discover_oauth(provider, http)
            info = await self._client_credentials(provider, meta, http)
            state = secrets.token_urlsafe(40)
            verifier = secrets.token_urlsafe(64)
            from authlib.integrations.httpx_client import AsyncOAuth2Client
            async with AsyncOAuth2Client(
                client_id=info["client_id"], client_secret=info["client_secret"] or None,
                token_endpoint_auth_method=info.get("token_endpoint_auth_method", "none"),
                redirect_uri=callback_url(), scope=" ".join(provider.requested_scopes),
                code_challenge_method="S256", follow_redirects=False, trust_env=False,
                timeout=10,
            ) as oauth:
                url, _ = oauth.create_authorization_url(
                    meta["authorization_endpoint"], state=state, code_verifier=verifier,
                    resource=provider.mcp_url,
                )
            details = {"verifier": verifier, "issuer": provider.issuer,
                       "token_url": meta["token_endpoint"], "client": info,
                       "label": label or provider.provider_id}
            async with self.pool.acquire() as db:
                await db.execute(
                    """INSERT INTO dz_mcp_oauth_attempts
                       (state_hash, owner_id, session_hash, provider_id, encrypted_flow, expires_at)
                       VALUES($1,$2,$3,$4,$5,$6)""",
                    _digest(state), owner, _digest(session_secret), provider_id,
                    self.cipher.seal(owner, _digest(state), details),
                    _NOW() + timedelta(minutes=10),
                )
            return url
        finally:
            if own:
                await http.aclose()

    async def finish(self, *, owner: str, session_secret: str, state: str,
                     code: str, issuer_response: str | None = None) -> dict:
        require_gate()
        if not owner or not 20 <= len(session_secret) <= 128 or not 30 <= len(state) <= 256:
            raise ConnectionDenied("Invalid OAuth callback binding")
        if not isinstance(code, str) or not 1 <= len(code) <= 4096:
            raise ConnectionDenied("Invalid OAuth authorization code")
        state_hash = _digest(state)
        async with self.pool.acquire() as db:
            # Atomic consume. Replays cannot exchange another authorization code.
            row = await db.fetchrow(
                """DELETE FROM dz_mcp_oauth_attempts WHERE state_hash=$1
                   RETURNING owner_id, session_hash, provider_id, encrypted_flow, expires_at""",
                state_hash,
            )
        if (not row or row["owner_id"] != owner or
                not secrets.compare_digest(row["session_hash"], _digest(session_secret)) or
                row["expires_at"] <= _NOW()):
            raise ConnectionDenied("OAuth callback expired or session mismatched")
        provider = reviewed_providers().get(row["provider_id"])
        if not provider:
            raise ConnectionDenied("Provider no longer reviewed")
        details = self.cipher.open(owner, state_hash, row["encrypted_flow"])
        if details["issuer"] != provider.issuer or (issuer_response and issuer_response != provider.issuer):
            raise ConnectionDenied("OAuth issuer mix-up rejected")
        _same_origin(details["token_url"], provider.issuer)
        from authlib.integrations.httpx_client import AsyncOAuth2Client
        info = details["client"]
        async with AsyncOAuth2Client(
            client_id=info["client_id"], client_secret=info["client_secret"] or None,
            token_endpoint_auth_method=("client_secret_basic" if info["client_secret"] else "none"),
            redirect_uri=callback_url(), follow_redirects=False, trust_env=False,
            timeout=10,
        ) as oauth:
            result = await oauth.fetch_token(
                details["token_url"], code=code, code_verifier=details["verifier"],
                resource=provider.mcp_url,
            )
        return await self._persist_token(owner, provider, details["label"], result)

    async def _persist_token(self, owner: str, provider: ReviewedProvider,
                             label: str, result: dict) -> dict:
        if not isinstance(result, dict) or result.get("token_type", "Bearer").lower() != "bearer":
            raise ConnectionDenied("OAuth did not issue a bearer token")
        access = result.get("access_token")
        if not isinstance(access, str) or not 8 <= len(access) <= 8192:
            raise ConnectionDenied("OAuth bearer credential is invalid")
        granted = _scopes(result.get("scope", list(provider.requested_scopes)))
        if not set(granted) <= set(provider.requested_scopes):
            raise ConnectionDenied("Provider expanded requested scopes")
        expiry = _token_expiry(result)
        identifier = uuid4()
        alias = "c" + identifier.hex[:30]
        payload = {"access_token": access, "refresh_token": result.get("refresh_token") or "",
                   "scope": list(granted)}
        async with self.pool.acquire() as db:
            await db.execute(
                """INSERT INTO dz_mcp_connections
                   (id, public_alias, owner_id, provider_id, display_label, issuer,
                    resource, granted_scopes, encrypted_tokens, access_expires_at)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
                identifier, alias, owner, provider.provider_id, label[:80],
                provider.issuer, provider.mcp_url, list(granted),
                self.cipher.seal(owner, alias, payload), expiry,
            )
        return {"connection_id": alias, "provider_id": provider.provider_id,
                "label": label[:80], "scopes": list(granted), "status": "active"}

    async def list_connections(self, owner: str) -> list[dict]:
        require_gate()
        async with self.pool.acquire() as db:
            rows = await db.fetch(
                """SELECT public_alias, provider_id, display_label, granted_scopes,
                          status, access_expires_at
                   FROM dz_mcp_connections WHERE owner_id=$1 ORDER BY created_at DESC LIMIT 100""",
                owner,
            )
        return [{"connection_id": r["public_alias"], "provider_id": r["provider_id"],
                 "label": r["display_label"], "scopes": list(r["granted_scopes"]),
                 "status": r["status"],
                 "expires_at": r["access_expires_at"].isoformat() if r["access_expires_at"] else None}
                for r in rows]

    async def disconnect(self, owner: str, alias: str) -> bool:
        """Immediately revoke local authority; attempt RFC 7009 revocation."""
        require_gate()
        if not isinstance(alias, str) or not re.fullmatch(r"c[a-f0-9]{30}", alias):
            raise ConnectionDenied("Invalid account ID")
        async with self.pool.acquire() as db:
            async with db.transaction():
                row = await db.fetchrow(
                    """SELECT provider_id, encrypted_tokens
                       FROM dz_mcp_connections
                       WHERE owner_id=$1 AND public_alias=$2 AND status='active'
                       FOR UPDATE""", owner, alias,
                )
                if not row:
                    return False
                tokens = self.cipher.open(owner, alias, row["encrypted_tokens"])
                await db.execute(
                    """UPDATE dz_mcp_connections SET status='revoked',
                       encrypted_tokens=NULL, revision=revision+1, revoked_at=now(),
                       updated_at=now() WHERE owner_id=$1 AND public_alias=$2""",
                    owner, alias,
                )
        # External revocation is best effort AFTER local transaction commits.
        # No future agent grant can use this connection even if AS is offline.
        provider = reviewed_providers().get(row["provider_id"])
        if provider:
            http = self._http()
            own = self.http is None
            try:
                meta = await discover_oauth(provider, http)
                revocation = meta.get("revocation_endpoint")
                if revocation:
                    info = await self._client_credentials(provider, meta, http)
                    from authlib.integrations.httpx_client import AsyncOAuth2Client
                    async with AsyncOAuth2Client(
                        client_id=info["client_id"],
                        client_secret=info["client_secret"] or None,
                        token_endpoint_auth_method=("client_secret_basic" if info["client_secret"] else "none"),
                        follow_redirects=False, trust_env=False, timeout=10,
                    ) as oauth:
                        await oauth.revoke_token(
                            revocation, token=tokens.get("refresh_token") or tokens["access_token"],
                            token_type_hint=("refresh_token" if tokens.get("refresh_token") else "access_token"),
                        )
            except Exception:
                # An opaque audit event may be emitted by the caller; never log
                # revoked credentials or silently claim upstream revocation.
                pass
            finally:
                if own:
                    await http.aclose()
        return True

    async def _refresh_locked(self, db, row, owner: str, alias: str,
                              tokens: dict, provider: ReviewedProvider) -> dict:
        refresh = tokens.get("refresh_token")
        if not refresh:
            await db.execute(
                """UPDATE dz_mcp_connections SET status='expired', encrypted_tokens=NULL,
                   revision=revision+1 WHERE owner_id=$1 AND public_alias=$2""", owner, alias)
            return None
        http = self._http()
        own = self.http is None
        try:
            meta = await discover_oauth(provider, http)
            info = await self._client_credentials(provider, meta, http, db=db)
            from authlib.integrations.httpx_client import AsyncOAuth2Client
            async with AsyncOAuth2Client(
                client_id=info["client_id"], client_secret=info["client_secret"] or None,
                token_endpoint_auth_method=("client_secret_basic" if info["client_secret"] else "none"),
                follow_redirects=False, trust_env=False, timeout=10,
            ) as oauth:
                updated = await oauth.refresh_token(
                    meta["token_endpoint"], refresh_token=refresh,
                    resource=provider.mcp_url,
                )
        except Exception as error:
            # Fail closed, leave encrypted old credentials for a later transient
            # retry. Never retry an MCP tool invocation after uncertain effects.
            raise ConnectionDenied("OAuth token refresh unavailable") from error
        finally:
            if own:
                await http.aclose()
        granted = _scopes(updated.get("scope", tokens["scope"]))
        if not set(granted) <= set(row["granted_scopes"]):
            raise ConnectionDenied("OAuth refresh expanded scopes")
        tokens = {"access_token": updated["access_token"],
                  "refresh_token": updated.get("refresh_token") or refresh,
                  "scope": list(granted)}
        expiry = _token_expiry(updated)
        await db.execute(
            """UPDATE dz_mcp_connections SET encrypted_tokens=$3, access_expires_at=$4,
               granted_scopes=$5, revision=revision+1, updated_at=now()
               WHERE owner_id=$1 AND public_alias=$2 AND status='active'""",
            owner, alias, self.cipher.seal(owner, alias, tokens), expiry, list(granted),
        )
        return tokens

    async def grant(self, *, owner: str, alias: str, capability: str,
                    authorized: bool) -> "McpGrant":
        """Resolve live DB + OAuth authority for ONE separately approved read."""
        require_gate()
        if not authorized:
            raise ConnectionDenied("DragonZpyder capability policy denied")
        if not isinstance(alias, str) or not re.fullmatch(r"c[a-f0-9]{30}", alias):
            raise ConnectionDenied("Invalid explicit account selection")
        async with self.pool.acquire() as db:
            async with db.transaction():
                row = await db.fetchrow(
                    """SELECT provider_id, issuer, resource, granted_scopes, status,
                              encrypted_tokens, access_expires_at
                       FROM dz_mcp_connections
                       WHERE owner_id=$1 AND public_alias=$2 FOR UPDATE""",
                    owner, alias,
                )
                if not row or row["status"] != "active" or row["encrypted_tokens"] is None:
                    raise ConnectionDenied("MCP account unavailable or revoked")
                provider = reviewed_providers().get(row["provider_id"])
                if (not provider or provider.mcp_url != row["resource"]
                        or provider.issuer != row["issuer"]
                        or capability not in provider.readonly_tools):
                    raise ConnectionDenied("MCP connection or tool no longer approved")
                tokens = self.cipher.open(owner, alias, row["encrypted_tokens"])
                expires = row["access_expires_at"]
                if not expires or expires <= _NOW() + timedelta(seconds=60):
                    tokens = await self._refresh_locked(db, row, owner, alias, tokens, provider)
        if tokens is None:
            raise ConnectionDenied("OAuth access expired; reconnect required")
        # Import only here: no OAuth secret is serialized to a LangGraph state.
        from .mcp_broker import McpGrant
        return McpGrant(
            provider_id=alias, url=provider.mcp_url,
            allowed_hosts=frozenset({urlsplit(provider.mcp_url).hostname}),
            headers={"Authorization": "Bearer " + tokens["access_token"]},
            capability_ids=frozenset({capability}),
        )


def _token_expiry(token: dict) -> datetime:
    now = _NOW()
    try:
        if token.get("expires_in") is not None:
            seconds = int(token["expires_in"])
            if 0 < seconds <= 86400 * 365:
                return now + timedelta(seconds=seconds)
        if token.get("expires_at") is not None:
            epoch = float(token["expires_at"])
            expiry = datetime.fromtimestamp(epoch, timezone.utc)
            if now < expiry <= now + timedelta(days=365):
                return expiry
    except (ValueError, TypeError, OverflowError):
        pass
    return now + timedelta(minutes=5)


def callback_url() -> str:
    url = os.getenv("DRAGONZPYDER_MCP_OAUTH_CALLBACK_URL", "")
    _safe_https(url)
    if urlsplit(url).path != "/internal/mcp/oauth/callback":
        raise ConnectionDenied("OAuth redirect URI must match reviewed server callback")
    return url
