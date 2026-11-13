"""Safety and compatibility smoke tests for extracted pure runtime modules."""
import unittest
from fastapi.testclient import TestClient
from dragonzpyder_platform.main import app
from dragonzpyder_platform.runtime.agent_contracts import AgentBudget, stable_step_request_id
from dragonzpyder_platform.runtime.context import ContextAssembler, ContextBudget, ContextItem, ContextKind
from dragonzpyder_platform.runtime.schema_validation import SchemaValidationError, validate_schema


class PlatformBootstrapTests(unittest.TestCase):
    def test_liveness_does_not_claim_runtime_ready(self):
        result = TestClient(app).get("/healthz")
        self.assertEqual(result.status_code, 200)
        self.assertIs(result.json()["runtime_ready"], False)
        self.assertEqual(result.json()["status"], "bootstrap-only")

    def test_no_unsafe_business_routes_mounted(self):
        response = TestClient(app).get("/api/workspaces")
        self.assertEqual(response.status_code, 404)

    def test_agent_budget_limits_survive_extraction(self):
        with self.assertRaises(ValueError):
            AgentBudget(max_steps=1000)
        self.assertEqual(AgentBudget().max_mutations, 8)

    def test_step_ids_are_stable_and_distinct(self):
        self.assertEqual(stable_step_request_id("run", "step"), stable_step_request_id("run", "step"))
        self.assertNotEqual(stable_step_request_id("run", "step"), stable_step_request_id("run", "other"))

    def test_context_selection_remains_bounded(self):
        items = [ContextItem(key="a", kind=ContextKind.CONVERSATION, text="Check my calendar", relevance=1.0),
                 ContextItem(key="b", kind=ContextKind.ARTIFACT, text="Unrelated source")]
        selected = ContextAssembler().select("calendar", items, budget=ContextBudget(max_items=1))
        self.assertEqual(len(selected.items), 1)
        self.assertEqual(selected.items[0].key, "a")

    def test_schema_validation_rejects_unsafe_types_and_unknown_keys(self):
        schema = {"type":"object","properties":{"n":{"type":"integer"}},"required":["n"],"additionalProperties":False}
        validate_schema({"n":2}, schema)
        with self.assertRaises(SchemaValidationError):
            validate_schema({"n":True}, schema)
        with self.assertRaises(SchemaValidationError):
            validate_schema({"n":2,"secret":"extra"}, schema)


if __name__ == "__main__":
    unittest.main()
