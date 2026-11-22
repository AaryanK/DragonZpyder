"""Offline security acceptance tests: no real providers or bearer secrets."""
import asyncio
import base64
import hashlib
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform import mcp_connections as m
from agent_platform.mcp_managed_catalog import (
    ManagedMcpRunCatalog, managed_catalog_tools, _redact,
)
from agent_platform.mcp_broker import input_schema


def env(monkeypatch, *, names=("archive", "library")):
    monkeypatch.setenv("DRAGONZPYDER_MCP_USER_CONNECTIONS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_MCP_EGRESS_FIREWALL_ENFORCED", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    monkeypatch.setenv("DRAGONZPYDER_MCP_OAUTH_CALLBACK_URL",
                       "https://identity.example.com/internal/mcp/oauth/callback")
    monkeypatch.setenv("DRAGONZPYDER_MCP_FERNET_KEYS", Fernet.generate_key().decode())
    import json
    monkeypatch.setenv("DRAGONZPYDER_MCP_OAUTH_PROVIDERS_JSON", json.dumps([
        {"provider_id": p, "mcp_url": f"https://{p}.example.com/mcp",
         "issuer": "https://login.example.com",
         "readonly_tools": ["lookup"], "scheduled_tools": ["lookup"],
         "requested_scopes": ["documents.read"], "client_id": "dz-" + p,
         "registration": "pre_registered", "description": "Search documents"}
        for p in names
    ]))


class FakePool:
    def __init__(self):
        self.attempts = {}
        self.connections = {}
        self.clients = {}
        self.lock = asyncio.Lock()
        self.execs = []

    @asynccontextmanager
    async def acquire(self):
        yield FakeConn(self)


class FakeConn:
    def __init__(self, pool):
        self.pool = pool

    @asynccontextmanager
    async def transaction(self):
        async with self.pool.lock:
            yield

    async def execute(self, query, *args):
        self.pool.execs.append((query, args))
        if "INSERT INTO dz_mcp_oauth_attempts" in query:
            self.pool.attempts[args[0]] = {
                "owner_id": args[1], "session_hash": args[2],
                "provider_id": args[3], "encrypted_flow": args[4],
                "expires_at": args[5],
            }
        if "INSERT INTO dz_mcp_connections" in query:
            self.pool.connections[args[1]] = {
                "id": args[0], "public_alias": args[1], "owner_id": args[2],
                "provider_id": args[3], "display_label": args[4],
                "issuer": args[5], "resource": args[6],
                "granted_scopes": args[7], "encrypted_tokens": args[8],
                "access_expires_at": args[9], "status": "active",
            }
        if "UPDATE dz_mcp_connections" in query:
            record = self.pool.connections[args[1]]
            if "status='expired'" in query:
                record.update(status="expired", encrypted_tokens=None)
            elif "status='revoked'" in query:
                record.update(status="revoked", encrypted_tokens=None)
            else:
                record.update(encrypted_tokens=args[2], access_expires_at=args[3],
                              granted_scopes=args[4])

    async def fetchrow(self, query, *args):
        if "DELETE FROM dz_mcp_oauth_attempts" in query:
            return self.pool.attempts.pop(args[0], None)
        if "SELECT provider_id, encrypted_tokens" in query:
            r = self.pool.connections.get(args[1])
            return r if r and r["owner_id"] == args[0] and r["status"] == "active" else None
        if "FROM dz_mcp_connections" in query:
            r = self.pool.connections.get(args[1])
            return r if r and r["owner_id"] == args[0] else None
        return None

    async def fetch(self, query, *args):
        return [r for r in self.pool.connections.values() if r["owner_id"] == args[0]]


META = {"issuer": "https://login.example.com",
        "authorization_endpoint": "https://login.example.com/authorize",
        "token_endpoint": "https://login.example.com/token",
        "revocation_endpoint": "https://login.example.com/revoke",
        "code_challenge_methods_supported": ["S256"],
        "response_types_supported": ["code"], "grant_types_supported": ["authorization_code", "refresh_token"]}


class FakeOAuth:
    exchanges = []
    refreshes = 0
    revocations = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    def create_authorization_url(self, url, **kwargs):
        from urllib.parse import urlencode
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(kwargs["code_verifier"].encode()).digest()
        ).decode().rstrip("=")
        params = {"state": kwargs["state"], "code_challenge": challenge,
                  "code_challenge_method": "S256", "resource": kwargs["resource"],
                  "client_id": self.kwargs["client_id"]}
        return url + "?" + urlencode(params), kwargs["state"]

    async def fetch_token(self, url, **kwargs):
        FakeOAuth.exchanges.append(kwargs)
        return {"access_token": "secret-long-access-token-000",
                "refresh_token": "secret-refresh-token-000",
                "token_type": "Bearer", "scope": "documents.read",
                "expires_in": 3600}

    async def refresh_token(self, url, **kwargs):
        FakeOAuth.refreshes += 1
        assert kwargs["resource"].endswith("/mcp")
        return {"access_token": "secret-long-new-token-111",
                "refresh_token": "secret-new-refresh-111",
                "scope": "documents.read", "expires_in": 3600}

    async def revoke_token(self, url, **kwargs):
        FakeOAuth.revocations.append(kwargs)


@pytest.fixture
def manager(monkeypatch):
    env(monkeypatch)
    monkeypatch.setattr(m, "discover_oauth", lambda *args: asyncio.sleep(0, result=META))
    monkeypatch.setattr("authlib.integrations.httpx_client.AsyncOAuth2Client", FakeOAuth)
    FakeOAuth.exchanges.clear()
    FakeOAuth.revocations.clear()
    FakeOAuth.refreshes = 0
    db = FakePool()
    obj = m.OAuthConnectionManager(db, m.CredentialCipher(), http=object())
    return obj, db


async def connect(manager, owner="owner-one", provider="archive", session="s" * 40):
    url = await manager.begin(owner=owner, session_secret=session, provider_id=provider)
    state = parse_qs(urlsplit(url).query)["state"][0]
    account = await manager.finish(owner=owner, session_secret=session,
                                   state=state, code="auth-code")
    return url, account["connection_id"]


def test_crypto_separation_ciphertext_and_rotation(monkeypatch):
    env(monkeypatch)
    cipher = m.CredentialCipher()
    ciphertext = cipher.seal("user1", "alias1", {"access_token": "private-value"})
    assert b"private-value" not in ciphertext
    assert cipher.open("user1", "alias1", ciphertext)["access_token"] == "private-value"
    with pytest.raises(m.ConnectionDenied):
        cipher.open("user2", "alias1", ciphertext)
    key2 = Fernet.generate_key().decode()
    old = os.environ["DRAGONZPYDER_MCP_FERNET_KEYS"]
    assert m.CredentialCipher(key2 + "," + old).open("user1", "alias1", ciphertext)


def test_reviewed_registry_rejects_malicious_endpoints_and_expanding_policy(monkeypatch):
    env(monkeypatch)
    for host in ("127.0.0.1", "localhost", "metadata.google.internal", "169.254.169.254"):
        with pytest.raises(m.ConnectionDenied):
            m.ReviewedProvider.parse({
                "provider_id": "evil", "mcp_url": f"https://{host}/mcp",
                "issuer": "https://login.example.com",
                "readonly_tools": ["lookup"], "client_id": "x",
            })
    with pytest.raises(m.ConnectionDenied, match="Scheduled tool"):
        m.ReviewedProvider.parse({
            "provider_id": "evil", "mcp_url": "https://evil.example.com/mcp",
            "issuer": "https://login.example.com", "readonly_tools": ["lookup"],
            "scheduled_tools": ["delete"], "client_id": "x",
        })
    with pytest.raises(m.ConnectionDenied):
        m._same_origin("https://attacker.example.com/token", "https://login.example.com")


def test_disabled_by_default_and_production_gate(monkeypatch):
    env(monkeypatch)
    monkeypatch.delenv("DRAGONZPYDER_MCP_USER_CONNECTIONS_ENABLED")
    with pytest.raises(m.ConnectionDenied):
        m.require_gate()
    monkeypatch.setenv("DRAGONZPYDER_MCP_USER_CONNECTIONS_ENABLED", "1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    with pytest.raises(m.ConnectionDenied):
        m.require_gate()


def test_pkce_csrf_single_use_issuer_and_no_browser_token(manager):
    service, db = manager
    async def run():
        url = await service.begin(owner="alice", session_secret="a" * 40,
                                  provider_id="archive")
        query = parse_qs(urlsplit(url).query)
        assert query["code_challenge_method"] == ["S256"]
        assert query["resource"] == ["https://archive.example.com/mcp"]
        assert "secret" not in url.lower()
        state = query["state"][0]
        assert len(db.attempts) == 1
        blob = next(iter(db.attempts.values()))["encrypted_flow"]
        assert b"verifier" not in blob
        with pytest.raises(m.ConnectionDenied, match="mismatched"):
            await service.finish(owner="mallory", session_secret="a" * 40,
                                 state=state, code="code")
        with pytest.raises(m.ConnectionDenied):
            await service.finish(owner="alice", session_secret="a" * 40,
                                 state=state, code="code")
        url = await service.begin(owner="alice", session_secret="a" * 40,
                                  provider_id="archive")
        state = parse_qs(urlsplit(url).query)["state"][0]
        with pytest.raises(m.ConnectionDenied, match="issuer"):
            await service.finish(owner="alice", session_secret="a" * 40,
                                 state=state, code="code", issuer_response="https://evil.example.com")
        url = await service.begin(owner="alice", session_secret="a" * 40,
                                  provider_id="archive")
        state = parse_qs(urlsplit(url).query)["state"][0]
        account = await service.finish(owner="alice", session_secret="a" * 40,
                                       state=state, code="code",
                                       issuer_response="https://login.example.com")
        assert account["scopes"] == ["documents.read"]
        assert account["connection_id"].startswith("c")
        assert "access_token" not in str(account)
    asyncio.run(run())


def test_multiple_accounts_wrong_user_and_wrong_explicit_alias(manager):
    service, _ = manager
    async def run():
        _, alice_a = await connect(service, owner="alice", provider="archive")
        _, alice_b = await connect(service, owner="alice", provider="archive")
        _, bob = await connect(service, owner="bob", provider="library")
        assert len({alice_a, alice_b, bob}) == 3
        assert len(await service.list_connections("alice")) == 2
        for alias in (bob, "c" + "0" * 30):
            with pytest.raises(m.ConnectionDenied):
                await service.grant(owner="alice", alias=alias,
                                    capability="lookup", authorized=True)
        with pytest.raises(m.ConnectionDenied):
            await service.grant(owner="alice", alias=alice_a,
                                capability="lookup", authorized=False)
        assert (await service.grant(owner="alice", alias=alice_b,
                                    capability="lookup", authorized=True)).provider_id == alice_b
    asyncio.run(run())


def test_refresh_is_single_flight_across_parallel_requests(manager):
    service, db = manager
    async def run():
        _, alias = await connect(service)
        db.connections[alias]["access_expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        grants = await asyncio.gather(*[
            service.grant(owner="owner-one", alias=alias,
                          capability="lookup", authorized=True) for _ in range(8)
        ])
        assert all("secret-long-new-token-111" in x.headers["Authorization"] for x in grants)
        assert FakeOAuth.refreshes == 1
        assert db.connections[alias]["access_expires_at"] > datetime.now(timezone.utc)
    asyncio.run(run())


def test_disconnection_revocation_and_nonreplay(manager):
    service, db = manager
    async def run():
        _, alias = await connect(service)
        assert await service.disconnect("owner-one", alias)
        assert db.connections[alias]["encrypted_tokens"] is None
        assert FakeOAuth.revocations
        assert not await service.disconnect("owner-one", alias)
        with pytest.raises(m.ConnectionDenied):
            await service.grant(owner="owner-one", alias=alias,
                                capability="lookup", authorized=True)
    asyncio.run(run())


class FakeTool:
    def __init__(self, alias, token):
        self.name = alias
        self.description = "Provider description " + token
        self.args_schema = {"type": "object", "properties": {"q": {"type": "string"}},
                            "required": ["q"]}
        self.token = token

    async def ainvoke(self, args):
        return {"records": [args["q"]], "leak": self.token}


def test_multi_provider_catalog_reauth_redacts_and_scheduled_policy(manager, monkeypatch):
    service, _ = manager
    async def sdk(grants, max_tools=1):
        g = grants[0]
        return [FakeTool(g.provider_id + "_lookup", g.headers["Authorization"][7:])]
    monkeypatch.setattr("agent_platform.mcp_managed_catalog.discover_granted_mcp_tools", sdk)
    async def run():
        _, one = await connect(service, provider="archive")
        _, two = await connect(service, provider="library")
        tools = await managed_catalog_tools(manager=service, owner="owner-one",
                                            selected_account_ids=[one, two], scheduled=True)
        assert [t.name for t in tools] == ["search_tools", "describe_tool", "invoke_tool"]
        # The in-memory catalog is not itself a checkpoint or a tool result.
        catalog = tools[0].func.__closure__[0].cell_contents if False else None
        from agent_platform.mcp_managed_catalog import ManagedMcpRunCatalog
        from agent_platform.mcp_broker import CatalogGrant, McpGrant
        entries = [
            CatalogGrant(McpGrant(alias, f"https://{provider}.example.com/mcp",
                                  frozenset({provider + ".example.com"}), {},
                                  frozenset({"lookup"})),
                         frozenset({"lookup"}), "Search documents")
            for alias, provider in ((one, "archive"), (two, "library"))
        ]
        obj = ManagedMcpRunCatalog(entries, owner="owner-one", manager=service, scheduled=True)
        assert len(obj.search("lookup")) == 2
        for alias in (one, two):
            d = await obj.describe(alias, "lookup")
            assert "secret-long-access-token" not in str(d)
            out = await obj.invoke(alias, "lookup", {"q": "physics"}, d["schema_sha256"])
            assert out["result"]["records"] == ["physics"]
            assert out["result"]["leak"] == "[redacted credential]"
        with pytest.raises(PermissionError):
            await obj.describe(one, "delete")
        with pytest.raises(m.ConnectionDenied):
            await managed_catalog_tools(manager=service, owner="other",
                                        selected_account_ids=[one], scheduled=True)
    asyncio.run(run())



def test_real_authlib_client_constructs_pkce_s256_and_resource():
    """This uses actual Authlib request construction, not FakeOAuth."""
    from authlib.integrations.httpx_client import AsyncOAuth2Client

    async def build():
        async with AsyncOAuth2Client(
            client_id="client-123", redirect_uri="https://identity.example.com/internal/mcp/oauth/callback",
            code_challenge_method="S256", follow_redirects=False, trust_env=False,
        ) as oauth:
            return oauth.create_authorization_url(
                "https://login.example.com/authorize", state="test-csrf-state",
                code_verifier="this-is-a-valid-pkce-code-verifier-with-entropy-123456789",
                resource="https://archive.example.com/mcp",
            )[0]

    url = asyncio.run(build())
    params = parse_qs(urlsplit(url).query)
    assert params["state"] == ["test-csrf-state"]
    assert params["code_challenge_method"] == ["S256"]
    assert len(params["code_challenge"][0]) == 43
    assert params["resource"] == ["https://archive.example.com/mcp"]
    assert "code_verifier" not in params



def test_real_http_browser_csrf_origin_and_token_non_disclosure(manager, monkeypatch):
    """Actual FastAPI dispatch around existing identity-bound session verifier."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from contextlib import asynccontextmanager
    from identity.sessions import SessionDenied
    from agent_platform import mcp_connection_http as routes

    service, _ = manager
    monkeypatch.setenv("DRAGONZPYDER_IDENTITY_ISSUER", "https://identity.example.com")

    @asynccontextmanager
    async def fake_identity_db():
        yield object()

    async def session(db, *, secret, csrf=None, require_csrf=False):
        if secret != "s" * 40 or (require_csrf and csrf != "real-csrf-value"):
            raise SessionDenied("Bad session or csrf")
        return "owner-one"

    monkeypatch.setattr(routes, "_identity_db", fake_identity_db)
    monkeypatch.setattr(routes, "resolve_browser_session", session)
    app = FastAPI()
    app.state.mcp_connections = service
    app.include_router(routes.router)
    client = TestClient(app, base_url="https://identity.example.com")
    client.cookies.set("__Host-dz_identity", "s" * 40)
    path = "/internal/mcp/connections/archive/start"
    body = {"label": "Work"}
    assert client.post(path, json=body).status_code == 403
    assert client.post(path, json=body, headers={
        "origin": "https://identity.example.com",
        "x-dz-csrf": "wrong-value",
    }).status_code == 401
    response = client.post(path, json=body, headers={
        "origin": "https://identity.example.com",
        "x-dz-csrf": "real-csrf-value",
    })
    assert response.status_code == 200
    url = response.json()["authorization_url"]
    assert "secret-" not in url
    state = parse_qs(urlsplit(url).query)["state"][0]
    reply = client.get("/internal/mcp/oauth/callback", params={
        "state": state, "code": "real-looking-authorization-code",
        "iss": "https://login.example.com",
    })
    assert reply.status_code == 200
    assert "secret-" not in reply.text
    assert "real-looking-authorization-code" not in reply.text
    assert client.get("/internal/mcp/connections").status_code == 200
    saved = client.get("/internal/mcp/connections").json()["connections"]
    assert len(saved) == 1 and saved[0]["label"] == "Work"
    account = saved[0]["connection_id"]
    assert client.delete("/internal/mcp/connections/" + account).status_code == 403
    revoked = client.delete("/internal/mcp/connections/" + account, headers={
        "origin": "https://identity.example.com",
        "x-dz-csrf": "real-csrf-value",
    })
    assert revoked.status_code == 200
    assert client.get("/internal/mcp/connections").json()["connections"][0]["status"] == "revoked"


def test_secret_post_is_preserved_through_all_oauth_phases(manager, monkeypatch):
    """The registered AS method must survive begin, code exchange, refresh and revoke."""
    import json

    service, db = manager
    manifest = json.loads(os.environ["DRAGONZPYDER_MCP_OAUTH_PROVIDERS_JSON"])
    manifest[0].update({
        "client_secret_env": "TEST_MCP_OAUTH_CLIENT_SECRET",
        "token_endpoint_auth_method": "client_secret_post",
    })
    monkeypatch.setenv("TEST_MCP_OAUTH_CLIENT_SECRET", "registered-client-secret")
    monkeypatch.setenv("DRAGONZPYDER_MCP_OAUTH_PROVIDERS_JSON", json.dumps(manifest))

    class MethodSpy(FakeOAuth):
        modes = []

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.modes.append(kwargs["token_endpoint_auth_method"])

    monkeypatch.setattr("authlib.integrations.httpx_client.AsyncOAuth2Client", MethodSpy)

    async def run():
        _, alias = await connect(service, provider="archive")
        db.connections[alias]["access_expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        await service.grant(owner="owner-one", alias=alias,
                            capability="lookup", authorized=True)
        assert await service.disconnect("owner-one", alias)

    asyncio.run(run())
    assert MethodSpy.modes == ["client_secret_post"] * 4


@pytest.mark.parametrize("method", ["client_secret_post", "client_secret_basic"])
def test_actual_authlib_secret_authentication_conformance(method):
    """Use real Authlib and a local HTTPX transport, without third-party calls."""
    import importlib
    import json
    from authlib.integrations.httpx_client import AsyncOAuth2Client

    # Authlib may use httpx2, a separate compatibility transport package.
    # Construct mocks from the SAME HTTPX implementation as the OAuth client.
    module_name = next(
        cls.__module__.split(".")[0] for cls in AsyncOAuth2Client.__mro__
        if cls.__module__.startswith(("httpx.", "httpx2."))
    )
    oauth_httpx = importlib.import_module(module_name)
    seen = []

    class MockAsyncBody(oauth_httpx.AsyncByteStream):
        async def __aiter__(self):
            yield json.dumps({
                "access_token": "test-token-access-123456789",
                "token_type": "Bearer", "expires_in": 3600,
            }).encode()

    def responder(request):
        seen.append((request.headers.get("authorization", ""), request.content.decode()))
        return oauth_httpx.Response(200, headers={"content-type": "application/json"},
                              stream=MockAsyncBody())

    async def run():
        credential = "registered-secret"  # synthetic test value, not production authority
        async with AsyncOAuth2Client(
            client_id="registered-client", client_secret=credential,
            token_endpoint_auth_method=method,
            transport=oauth_httpx.MockTransport(responder),
            follow_redirects=False, trust_env=False,
        ) as oauth:
            return await oauth.fetch_token(
                "https://login.example.com/token",
                code="one-time-code", code_verifier="abcdefghijklmnopqrstuvwxyz1234567890abcde",
            )

    token = asyncio.run(run())
    assert token["access_token"] == "test-token-access-123456789"
    assert len(seen) == 1
    authorization, body = seen[0]
    if method == "client_secret_post":
        assert "client_secret=registered-secret" in body
        assert not authorization.startswith("Basic ")
    else:
        assert authorization.startswith("Basic ")
        assert "client_secret=registered-secret" not in body


def test_redaction_covers_untrusted_nested_object_keys():
    token = "secrettokenabcdefghijklmnopqrstuvwxyz"
    payload = {token: {"nested": [{"Bearer " + token: token}]}}
    assert token not in str(_redact(payload, token))


def test_operly_is_optional_oauth_provider_and_never_global_authority(monkeypatch):
    import json
    reviewed = {
        "provider_id": "operly",
        "mcp_url": "https://operly.dragonzpyder.xyz/mcp",
        "issuer": "https://operly.dragonzpyder.xyz",
        "readonly_tools": ["tasks.list"],
        "scheduled_tools": [],
        "requested_scopes": ["tasks.list", "offline_access"],
        "registration": "pre_registered",
        "client_id": "dragonzpyder",
        "description": "Operly Workspace MCP, optional and user-authorized",
    }
    monkeypatch.delenv("DRAGONZPYDER_OPERLY_USER_OAUTH_ENABLED", raising=False)
    with pytest.raises(m.ConnectionDenied, match="not approved"):
        m.ReviewedProvider.parse(reviewed)
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_USER_OAUTH_ENABLED", "1")
    record = m.ReviewedProvider.parse(reviewed)
    assert record.provider_id == "operly"
    assert record.readonly_tools == frozenset({"tasks.list"})
    for malicious in [
        {**reviewed, "mcp_url": "https://attacker.example/mcp"},
        {**reviewed, "issuer": "https://attacker.example"},
        {**reviewed, "client_id": "chatgpt"},
        {**reviewed, "registration": "dynamic"},
    ]:
        with pytest.raises(m.ConnectionDenied, match="pinned"):
            m.ReviewedProvider.parse(malicious)
    monkeypatch.setenv("DRAGONZPYDER_MCP_OAUTH_CALLBACK_URL",
                       "https://www.dragonzpyder.xyz/dz/internal/mcp/oauth/callback")
    assert m.callback_url().endswith("/dz/internal/mcp/oauth/callback")
    monkeypatch.setenv("DRAGONZPYDER_MCP_OAUTH_CALLBACK_URL",
                       "https://attacker.example/steal")
    with pytest.raises(m.ConnectionDenied, match="redirect URI"):
        m.callback_url()
