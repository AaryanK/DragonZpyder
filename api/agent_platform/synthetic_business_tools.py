"""Isolated, deterministic simulated business tools for harness acceptance.

No HTTP, OS, credentials, customer records, or provider side effects. Use the
standard LangChain @tool adapter so the real graph exercises ordinary tool calls.
Never register these in a production user/tenant context.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from langchain_core.tools import tool


@dataclass
class SyntheticBusiness:
    inventory: dict[str, int] = field(default_factory=lambda: {"coffee": 7})
    approvals: set[str] = field(default_factory=set)
    receipts: dict[str, dict] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    fail_next_commit: bool = False

    def tools(self) -> list:
        @tool
        def lookup_inventory(sku: str) -> str:
            """Get quantity for a simulated inventory SKU; read-only."""
            self.calls.append("lookup_inventory")
            if sku not in self.inventory:
                return json.dumps({"ok": False, "code": "not_found"})
            return json.dumps({"ok": True, "sku": sku, "quantity": self.inventory[sku]})

        @tool
        def simulate_order(sku: str, quantity: int) -> str:
            """Preview a simulated inventory order; never changes inventory."""
            self.calls.append("simulate_order")
            if quantity <= 0 or quantity > 100 or sku not in self.inventory:
                return json.dumps({"ok": False, "code": "invalid_order"})
            return json.dumps({
                "ok": self.inventory[sku] >= quantity,
                "sku": sku,
                "quantity": quantity,
                "available": self.inventory[sku],
                "requires_approval": True,
            })

        @tool
        def commit_order(sku: str, quantity: int, request_id: str, approval_id: str) -> str:
            """Commit a SIMULATED order only if approved; request_id is idempotent."""
            self.calls.append("commit_order")
            # Idempotency is checked first: retrying a successful request
            # returns its receipt without repeating the mutation.
            if request_id in self.receipts:
                prior = self.receipts[request_id]
                if prior["sku"] != sku or prior["quantity"] != quantity:
                    return json.dumps({"ok": False, "code": "idempotency_conflict"})
                return json.dumps({"ok": True, "replayed": True, "receipt": prior})
            if not request_id or len(request_id) > 80:
                return json.dumps({"ok": False, "code": "invalid_request_id"})
            if approval_id not in self.approvals:
                return json.dumps({"ok": False, "code": "approval_required"})
            if sku not in self.inventory or quantity <= 0 or quantity > self.inventory[sku]:
                return json.dumps({"ok": False, "code": "insufficient_inventory"})
            if self.fail_next_commit:
                self.fail_next_commit = False
                return json.dumps({"ok": False, "code": "transient_failure", "retryable": True})
            self.inventory[sku] -= quantity
            receipt = {"request_id": request_id, "sku": sku, "quantity": quantity}
            self.receipts[request_id] = receipt
            return json.dumps({"ok": True, "replayed": False, "receipt": receipt})

        @tool
        def lookup_order(request_id: str) -> str:
            """Read a simulated order receipt, if one was committed."""
            self.calls.append("lookup_order")
            receipt = self.receipts.get(request_id)
            return json.dumps({"ok": bool(receipt), "receipt": receipt})

        return [lookup_inventory, simulate_order, commit_order, lookup_order]
