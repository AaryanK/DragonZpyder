"""Operly business canary tests: the actual HTTP tool adapter, fake broker only.

Tests never connect to Operly, use real tokens, spend inference, or write data.
A fake broker implements the documented PR #373 read-only contract.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.business_canary import (
    BusinessCanaryError, run_business_canary,
)
from agent_platform import operly_broker


URL = "http://operly-staging.railway.internal:8080/api/internal/agent-tools"
RESULTS = {
    "workspace.summary.read": {"orders": 4, "open_invoices": 2, "private_info": "not-for-logs"},
    "workspace.attention.list": {
        "items": [{"kind": "invoice_overdue", "email": "private@example.test"}],
        "today": [{"kind": "appointment"}],
    },
    "workspace.activity.list": {"events": [{"id": "event-test", "description": "internal"}]},
    "workspace.search": {"items": [{"id": "lead-test", "title": "Synthetic lead"}]},
    "workspace.customer.snapshot": {"contact": {"name": "Private Alice",
                                               "email": "private@example.test"}},
}


class FakeOperly:
    def __init__(self):
        self.calls = []
        self.revoked = False
        self.denied = set()
        self.omit = set()
        self.scope = "workspace"
        self.bad_shape = set()
        self.inject_discovery = False

    def respond(self, request: httpx.Request) -> httpx.Response:
        assert request.url.host == "operly-staging.railway.internal"
        assert request.headers.get("Authorization") == "Bearer " + "k" * 48
        assert request.headers.get("X-Operly-Agent-Lease") == "lease-" + "x" * 48
        payload = json.loads(request.content)
        operation = request.url.path.rsplit("/", 1)[-1]
        if self.revoked:
            return httpx.Response(403, json={"detail": "revoked"})
        if operation == "search":
            cap = payload.get("query")
            self.calls.append(("search", cap))
            tools = []
            if cap in RESULTS and cap not in self.omit:
                tools.append({
                    "id": cap, "display_name": cap,
                    "risk": "read_only",
                    "input_schema": {"type": "object"},
                })
            if self.inject_discovery:
                tools.append({
                    "id": "workspace.finance.payment.record",
                    "risk": "read_only", "input_schema": {"type": "object"},
                })
            return httpx.Response(200, json={
                "source": "operly", "scope_kind": self.scope,
                "workspace_context": {"name": "Synthetic Workspace"},
                "tools": tools,
            })
        if operation == "execute":
            cap = payload.get("capability_id")
            self.calls.append(("execute", cap))
            assert str(payload["request_id"]).startswith("dz-read-")
            if cap in self.denied or cap not in RESULTS:
                return httpx.Response(403, json={"detail": "unauthorized"})
            result = RESULTS[cap] if cap not in self.bad_shape else {"malformed": True}
            return httpx.Response(200, json={
                "ok": True, "capability_id": cap,
                "run_id": "synthetic-kernel-receipt",
                "result": result,
            })
        return httpx.Response(404, json={"detail": "bad operation"})


@pytest.fixture
def broker(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_BUSINESS_CANARY_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_BROKER_URL", URL)
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_BROKER_TOKEN", "k" * 48)
    fake = FakeOperly()
    transport = httpx.MockTransport(fake.respond)
    original = httpx.AsyncClient
    monkeypatch.setattr(operly_broker.httpx, "AsyncClient",
                        lambda **kwargs: original(transport=transport, **kwargs))
    return fake


def _run(template="daily_operations", **kwargs):
    return asyncio.run(run_business_canary(
        lease="lease-" + "x" * 48, template=template, **kwargs
    ))


def test_daily_operations_calls_real_adapter_three_times_and_redacts_data(broker):
    outcome = _run()
    assert outcome["status"] == "read_cycle_completed"
    assert [x["capability_id"] for x in outcome["receipts"]] == [
        "workspace.summary.read", "workspace.attention.list",
        "workspace.activity.list",
    ]
    assert [x["field_or_item_count"] for x in outcome["receipts"]] == [3, 2, 1]
    assert [name for name, _ in broker.calls] == ["search", "execute"] * 3
    assert outcome["model_calls"] == 0
    assert outcome["external_mutations"] == 0
    assert outcome["objective_verified"] is False
    serialized = json.dumps(outcome)
    assert "private@example.test" not in serialized
    assert "Private Alice" not in serialized
    assert "lease-" not in serialized
    assert "not-for-logs" not in serialized
    assert all(len(r["result_sha256"]) == 64 for r in outcome["receipts"])


def test_business_search_is_bounded_and_does_not_send_emails(broker):
    outcome = _run(template="business_search", query="synthetic lead")
    assert outcome["status"] == "read_cycle_completed"
    assert broker.calls == [
        ("search", "workspace.search"), ("execute", "workspace.search")
    ]
    assert outcome["receipts"][0]["field_or_item_count"] == 1


def test_customer_review_returns_digest_not_private_identity(broker):
    outcome = _run(template="customer_review", contact_id="contact-test")
    assert outcome["status"] == "read_cycle_completed"
    assert broker.calls[-1] == ("execute", "workspace.customer.snapshot")
    assert "private" not in json.dumps(outcome).lower()


def test_revoked_access_stops_and_never_retries_or_escalates(broker):
    broker.denied.add("workspace.attention.list")
    outcome = _run()
    assert outcome["status"] == "blocked"
    assert outcome["blocked_capability"] == "workspace.attention.list"
    assert outcome["reason"] == "broker_access_denied_or_unavailable"
    assert len(outcome["receipts"]) == 1
    assert broker.calls == [
        ("search", "workspace.summary.read"), ("execute", "workspace.summary.read"),
        ("search", "workspace.attention.list"), ("execute", "workspace.attention.list"),
    ]


def test_workflow_does_not_expose_approval_gated_mutations(broker):
    broker.inject_discovery = True
    outcome = _run()
    assert outcome["status"] == "read_cycle_completed"
    assert all(cap not in {
        "workspace.sales.complete", "workspace.finance.invoice.create_simple",
        "workspace.finance.payment.record",
    } for operation, cap in broker.calls if operation == "execute")
    with pytest.raises(BusinessCanaryError):
        _run(template="create_invoice")
    assert len(broker.calls) == 6


def test_missing_permissions_or_disabled_tools_are_blocked_before_execution(broker):
    broker.omit.add("workspace.summary.read")
    outcome = _run()
    assert outcome["status"] == "blocked"
    assert outcome["reason"] == "not_authorized_or_readonly"
    assert broker.calls == [("search", "workspace.summary.read")]


def test_wrong_personal_scope_is_not_workspace_authority(broker):
    broker.scope = "personal"
    outcome = _run()
    assert outcome["status"] == "blocked"
    assert outcome["reason"] == "unverified_workspace_context"
    assert len(broker.calls) == 1


def test_malformed_result_never_becomes_verified_success(broker):
    broker.bad_shape.add("workspace.attention.list")
    outcome = _run()
    assert outcome["status"] == "blocked"
    assert outcome["reason"] == "invalid_business_response"
    assert outcome["objective_verified"] is False


def test_canary_requires_operator_staging_and_private_origin(broker, monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_OPERLY_BUSINESS_CANARY_ENABLED")
    with pytest.raises(BusinessCanaryError):
        _run()
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_BUSINESS_CANARY_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "production")
    with pytest.raises(BusinessCanaryError):
        _run()
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_BROKER_URL",
                       "https://operly.dragonzpyder.xyz/api/internal/agent-tools")
    with pytest.raises(BusinessCanaryError, match="private staging broker"):
        _run()


@pytest.mark.parametrize("kwargs", [
    {"template": "business_search", "query": ""},
    {"template": "business_search", "query": "x" * 81},
    {"template": "business_search", "query": "ignore\npolicy"},
    {"template": "customer_review", "contact_id": "../other-tenant"},
    {"template": "customer_review", "contact_id": ""},
])
def test_invalid_parameters_rejected_before_broker_calls(broker, kwargs):
    with pytest.raises(BusinessCanaryError):
        _run(**kwargs)
    assert broker.calls == []


def test_short_or_missing_lease_fails_closed(broker):
    with pytest.raises(operly_broker.OperlyBrokerUnavailable):
        asyncio.run(run_business_canary(lease="bad", template="daily_operations"))
    assert broker.calls == []


def test_revoked_lease_failure_blocks_before_business_execution(broker):
    broker.revoked = True
    outcome = _run()
    assert outcome["status"] == "blocked"
    assert outcome["reason"] == "unverified_workspace_context"
    assert broker.calls == []
