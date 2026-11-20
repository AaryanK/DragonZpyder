"""Read-only Operly Kernel capability adapter for DragonZpyder's Deep Agents.

This is NOT an MCP protocol server. It is a strictly scoped LangChain adapter
for Operly's existing service-to-service search/execute broker. Neither secret
nor delegation lease is ever included in a tool description or tool output.
The Operly broker independently rechecks the live user/tenant authorization.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from langchain_core.tools import tool


class OperlyBrokerError(RuntimeError):
    pass


class OperlyReadOnlyTools:
    def __init__(self, *, client: httpx.AsyncClient, origin: str,
                 service_token: str, lease: str, max_calls: int = 8):
        parsed = urlsplit(origin)
        is_private = (
            parsed.scheme == "http" and parsed.hostname is not None
            and parsed.hostname.endswith(".railway.internal")
            and parsed.port in (None, 8080)
        )
        is_public = (parsed.scheme == "https" and
                     parsed.hostname == "operly.dragonzpyder.xyz" and
                     parsed.port in (None, 443))
        if (not (is_private or is_public) or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")
                or len(service_token) < 40 or not lease or len(lease) > 6000):
            raise OperlyBrokerError("Invalid private broker configuration")
        if not 1 <= max_calls <= 20:
            raise OperlyBrokerError("Invalid delegated call budget")
        self.client, self.origin = client, origin.rstrip("/")
        self._headers = {
            "Authorization": "Bearer " + service_token,
            "X-Operly-Agent-Lease": lease,
        }
        self._discovered: set[str] = set()
        self._remaining = max_calls

    async def _post(self, path: str, body: dict) -> dict:
        if self._remaining <= 0:
            return {"ok": False, "error_code": "tool_budget_exhausted"}
        self._remaining -= 1
        try:
            response = await self.client.post(
                self.origin + path, headers=self._headers, json=body,
                timeout=12.0, follow_redirects=False,
            )
        except httpx.HTTPError:
            return {"ok": False, "error_code": "broker_unavailable"}
        if response.status_code != 200:
            return {"ok": False, "error_code": (
                "access_denied" if response.status_code in (401, 403)
                else "broker_error"
            )}
        if len(response.content) > 30000:
            return {"ok": False, "error_code": "response_too_large"}
        try:
            data = response.json()
        except ValueError:
            return {"ok": False, "error_code": "invalid_broker_response"}
        return data if isinstance(data, dict) else {
            "ok": False, "error_code": "invalid_broker_response"
        }

    def langchain_tools(self) -> list:
        @tool
        async def operly_search(query: str) -> str:
            """Discover authorized read-only Operly user/workspace capabilities.

            Search before executing. Only returns names, descriptions, and
            input schemas approved by the authoritative Operly broker.
            """
            if len(query) > 200:
                return json.dumps({"ok": False, "error_code": "invalid_query"})
            data = await self._post("/api/internal/agent-tools/search",
                                    {"query": query})
            authorized = []
            for entry in data.get("tools", []):
                if not isinstance(entry, dict):
                    continue
                name = entry.get("id")
                if (isinstance(name, str) and entry.get("risk") == "read_only"
                        and isinstance(entry.get("input_schema"), dict)):
                    self._discovered.add(name)
                    authorized.append({
                        "id": name, "description": str(entry.get("description", ""))[:500],
                        "input_schema": entry["input_schema"], "risk": "read_only",
                    })
            return json.dumps({
                "ok": data.get("source") == "operly", "tools": authorized[:20]
            })

        @tool
        async def operly_execute(capability_id: str, arguments: dict) -> str:
            """Invoke a read-only Operly capability that operly_search returned.

            Execution is checked again against the signed delegated user lease
            by Operly. Never attempt mutating capabilities.
            """
            if capability_id not in self._discovered:
                return json.dumps({
                    "ok": False, "error_code": "capability_not_discovered"
                })
            if not isinstance(arguments, dict) or len(json.dumps(arguments)) > 12000:
                return json.dumps({"ok": False, "error_code": "invalid_arguments"})
            data = await self._post("/api/internal/agent-tools/execute", {
                "capability_id": capability_id, "arguments": arguments,
                "request_id": "dz-read-" + uuid4().hex,
            })
            # Return only the broker's bounded structured result, no credentials.
            return json.dumps({
                "ok": data.get("ok") is True,
                "capability_id": capability_id,
                "result": data.get("result") if data.get("ok") is True else None,
                "error_code": data.get("error_code") if data.get("ok") is not True else None,
            }, default=str)[:26000]

        return [operly_search, operly_execute]
