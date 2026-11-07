"""Signed transport adapter for the existing Operly Railway Sandbox Runner.

Not exposed as an agent tool. Tool invocation needs a trusted capability
delegate, current principal authorization, budget and approval enforcement.
"""
from __future__ import annotations

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

    async def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
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
            timeout=30, follow_redirects=False, trust_env=False
        ) as http:
            response = await http.request(
                method, self.origin + path, headers=headers, content=raw
            )
        expected = self._signature(response.content)
        actual = response.headers.get("X-Operly-Signature", "")
        if not hmac.compare_digest(expected, actual):
            raise RuntimeError("Runner response failed signature verification")
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise RuntimeError("Invalid runner response")
        return result

    async def create(self, *, network_policy: str = "off") -> dict:
        if network_policy not in {"off", "web"}:
            raise ValueError("Invalid sandbox network policy")
        return await self._call(
            "POST", "/v1/computer/sessions",
            {"networkPolicy": network_policy},
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
            "POST", f"/v1/computer/sessions/{sandbox_id}/tools/{tool_id}", args
        )

    async def destroy_authorized(self, sandbox_id: str) -> dict:
        if not _SAFE_ID.fullmatch(sandbox_id):
            raise ValueError("Invalid sandbox ID")
        return await self._call("DELETE", f"/v1/computer/sessions/{sandbox_id}")
