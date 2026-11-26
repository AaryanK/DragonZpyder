"""Signed transport adapter for the existing Operly Railway Sandbox Runner.

Not exposed as an agent tool. Tool invocation needs a trusted capability
delegate, current principal authorization, budget and approval enforcement.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from urllib.parse import urlsplit

import httpx

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{3,160}$")
_SAFE_TOOL = re.compile(r"^[A-Za-z0-9_.-]{2,100}$")


def canonical(method: str, path: str, timestamp: str, nonce: str, body: bytes) -> bytes:
    return (f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n").encode() + body


class ComputerTransport:
    def __init__(self, *, base_url: str, token: str, signing_key: str):
        url = urlsplit(base_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username:
            raise ValueError("Invalid runner origin")
        if url.scheme == "http" and not url.hostname.endswith(".railway.internal"):
            raise ValueError("Unencrypted public runner connections are forbidden")
        if url.path not in {"", "/"} or url.query or url.fragment:
            raise ValueError("Runner origin must not contain a path or query")
        if min(len(token), len(signing_key)) < 32 or token == signing_key:
            raise ValueError("Two separate strong runner credentials are required")
        self.origin = base_url.rstrip("/")
        self.token = token
        self.signing_key = signing_key.encode()

    @classmethod
    def from_environment(cls):
        return cls(
            base_url=os.environ["DRAGONZPYDER_COMPUTER_RUNNER_URL"],
            token=os.environ["DRAGONZPYDER_COMPUTER_RUNNER_TOKEN"],
            signing_key=os.environ["DRAGONZPYDER_COMPUTER_RUNNER_SIGNING_KEY"],
        )

    def _signature(self, value: bytes) -> str:
        return hmac.new(self.signing_key, value, hashlib.sha256).hexdigest()

    async def _call(self, method: str, path: str, payload: dict | None = None,
                    *, timeout: int = 30) -> dict:
        raw = (json.dumps(payload, separators=(",", ":")).encode()
               if payload is not None else b"")
        timestamp = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)
        headers = {
            "Authorization": "Bearer " + self.token,
            "X-Operly-Timestamp": timestamp,
            "X-Operly-Nonce": nonce,
            "X-Operly-Signature": self._signature(
                canonical(method, path, timestamp, nonce, raw)
            ),
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=False, trust_env=False
        ) as http:
            response = await http.request(
                method, self.origin + path, headers=headers, content=raw
            )
        signed_body = (f"{nonce}\n{response.status_code}\n".encode() + response.content
                       if path.startswith("/v2/computer/") else response.content)
        expected = self._signature(signed_body)
        actual = response.headers.get("X-Operly-Signature", "")
        if not hmac.compare_digest(expected, actual):
            raise RuntimeError("Runner response failed signature verification")
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise RuntimeError("Invalid runner response")
        return result

    async def create(
        self, *, client_session_id: str, workspace_id: str,
        principal_id: str, profile: str = "general", network_policy: str = "off",
    ) -> dict:
        # The existing runner is WORKSPACE-scoped. Personal sandboxes need a
        # separate signed authority contract rather than fake workspace IDs.
        if not all(_SAFE_ID.fullmatch(v) for v in (
            client_session_id, workspace_id, principal_id,
        )):
            raise ValueError("Signed workspace session identity is required")
        if profile not in {"general", "coding", "data", "browser"}:
            raise ValueError("Invalid sandbox profile")
        if network_policy not in {"off", "web"}:
            raise ValueError("Invalid sandbox network policy")
        return await self._call(
            "POST", "/v1/computer/sessions",
            {"clientSessionId": client_session_id, "workspaceId": workspace_id,
             "principalId": principal_id, "profile": profile,
             "networkPolicy": network_policy},
        )

    async def status(self, sandbox_id: str) -> dict:
        if not _SAFE_ID.fullmatch(sandbox_id):
            raise ValueError("Invalid sandbox ID")
        return await self._call("GET", f"/v1/computer/sessions/{sandbox_id}")

    async def execute_authorized(
        self, *, sandbox_id: str, tool_id: str, args: dict,
    ) -> dict:
        # This transport method must be called only by the trusted capability
        # gateway after a current permission and approval check.
        if not _SAFE_ID.fullmatch(sandbox_id) or not _SAFE_TOOL.fullmatch(tool_id):
            raise ValueError("Invalid computer operation")
        if not isinstance(args, dict):
            raise ValueError("Tool args must be an object")
        return await self._call(
            "POST", f"/v1/computer/sessions/{sandbox_id}/tools/{tool_id}", {"arguments": args}
        )

    async def destroy_authorized(self, sandbox_id: str) -> dict:
        if not _SAFE_ID.fullmatch(sandbox_id):
            raise ValueError("Invalid sandbox ID")
        return await self._call("DELETE", f"/v1/computer/sessions/{sandbox_id}")


SCOPED_TOOLS = frozenset({
    "terminal.exec", "python.exec", "files.list", "files.read", "files.write",
    "files.mkdir", "files.search", "git.status", "git.diff", "artifact.import",
    "artifact.export", "environment.info",
})


@dataclass(frozen=True)
class ComputerScope:
    """Construct only from trusted authenticated request/run state."""
    kind: str
    principal_id: str
    client_session_id: str
    workspace_id: str | None = None

    def __post_init__(self):
        def valid(value):
            return isinstance(value, str) and len(value) >= 4 and _SAFE_ID.fullmatch(value)
        if (self.kind not in {"personal", "workspace"}
                or not valid(self.principal_id) or not valid(self.client_session_id)
                or (self.kind == "personal" and self.workspace_id is not None)
                or (self.kind == "workspace" and not valid(self.workspace_id))):
            raise ValueError("Invalid scoped computer identity")

    def wire(self):
        return {"scopeKind": self.kind, "principalId": self.principal_id,
                "clientSessionId": self.client_session_id, "workspaceId": self.workspace_id}


class ScopedComputerTransport(ComputerTransport):
    """DragonZpyder v2 runner protocol, with nonce-bound signed responses.

    This is a control-plane transport, NOT a model tool or authorization
    service. Every operation requires the same trusted scope, including cleanup.
    """

    async def create(self, *, scope: ComputerScope, profile: str = "general",
                     ttl_seconds: int = 900) -> dict:
        if (not isinstance(scope, ComputerScope)
                or profile not in {"general", "coding", "data"}
                or type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 1800):
            raise ValueError("Invalid scoped computer allocation")
        result = await self._call("POST", "/v2/computer/sessions",
            {"scope": scope.wire(), "profile": profile, "networkPolicy": "off",
             "ttlSeconds": ttl_seconds}, timeout=120)
        if (not isinstance(result.get("id"), str) or not _SAFE_ID.fullmatch(result["id"])
                or result.get("state") != "active" or result.get("private_network") is not False
                or result.get("network_policy") != "off"):
            raise RuntimeError("Scoped computer allocation not confirmed")
        return result

    @staticmethod
    def _session(sandbox_id, scope):
        if (not isinstance(sandbox_id, str) or not _SAFE_ID.fullmatch(sandbox_id)
                or not isinstance(scope, ComputerScope)):
            raise ValueError("Invalid scoped computer session")

    async def status(self, sandbox_id: str, *, scope: ComputerScope) -> dict:
        self._session(sandbox_id, scope)
        return await self._call("POST", f"/v2/computer/sessions/{sandbox_id}/status",
                                {"scope": scope.wire()})

    async def execute_authorized(self, *, sandbox_id: str, scope: ComputerScope,
                                 tool_id: str, args: dict) -> dict:
        self._session(sandbox_id, scope)
        if (tool_id not in SCOPED_TOOLS or type(args) is not dict
                or "background" in args or "env" in args):
            raise ValueError("Invalid scoped computer operation")
        deadline = args.get("timeout_seconds", 30)
        if type(deadline) is not int or not 1 <= deadline <= 60:
            raise ValueError("Invalid computer tool deadline")
        return await self._call("POST", f"/v2/computer/sessions/{sandbox_id}/tools/{tool_id}",
                                {"scope": scope.wire(), "arguments": args}, timeout=90)

    async def destroy_authorized(self, sandbox_id: str, *, scope: ComputerScope) -> dict:
        self._session(sandbox_id, scope)
        return await self._call("POST", f"/v2/computer/sessions/{sandbox_id}/destroy",
                                {"scope": scope.wire()}, timeout=30)
