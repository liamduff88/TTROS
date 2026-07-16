"""Prospecting engine integration contracts.

Revisit: when prospecting workflow registration or ledger semantics change. · Last touched: 2026-07-16.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
VAULT = Path("/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain")
WORKFLOWS = {"prospecting_daily_run", "prospecting_week_review"}


def load_validator():
    path = ROOT / "tools" / "validate-prospect-ledger.py"
    spec = importlib.util.spec_from_file_location("validate_prospect_ledger", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProspectingContractsTest(unittest.TestCase):
    def test_workflows_are_registered_routed_and_mapped_to_skills(self):
        registry = json.loads((ROOT / "workflows" / "workflow_registry.json").read_text(encoding="utf-8"))
        routes = json.loads((ROOT / "queue" / "command_routes.json").read_text(encoding="utf-8"))
        registered = {row["id"] for row in registry["workflows"]}
        routed = {row["workflow"] for row in routes["routes"]}
        static = json.loads((ROOT / "workflows" / "runner_contracts.json").read_text(encoding="utf-8"))
        runner_registered = {row["workflow_id"] for row in static["contracts"]}
        self.assertTrue(WORKFLOWS <= registered)
        self.assertTrue(WORKFLOWS <= routed)
        self.assertTrue(WORKFLOWS <= runner_registered)
        for workflow in WORKFLOWS:
            text = (ROOT / "workflows" / workflow / "workflow.md").read_text(encoding="utf-8")
            self.assertIn(f"skill: skills/{workflow}/SKILL.md", text)
            self.assertTrue((ROOT / "skills" / workflow / "SKILL.md").is_file())

    def test_canonical_brain_inputs_exist_and_are_scope_registered(self):
        pointers = {
            "business_brain:memory/ideal_clients.md",
            "business_brain:memory/ideal_clients_A.md",
            "business_brain:memory/ideal_clients_B.md",
            "business_brain:memory/prospecting_query_bank.md",
            "business_brain:memory/prospecting_rotation_plan.md",
            "business_brain:memory/prospecting_scoring_contract.md",
        }
        scope = json.loads((ROOT / "context" / "client_scope_registry.json").read_text(encoding="utf-8"))["scopes"]["global"]
        self.assertTrue(pointers <= set(scope["brain_pointers"]))
        for pointer in pointers:
            self.assertTrue((VAULT / pointer.removeprefix("business_brain:")).is_file())
        for path in (ROOT / "skills" / "prospecting_daily_run", ROOT / "skills" / "prospecting_week_review"):
            for source in path.glob("*.md"):
                self.assertNotIn("`memory/", source.read_text(encoding="utf-8"))

    def test_skill_registrations_validate(self):
        schema = json.loads((ROOT / "queue" / "skill_trust_schema.json").read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in (ROOT / "queue" / "skill_trust.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            jsonschema.validate(row, schema, format_checker=jsonschema.FormatChecker())
        registered = {row["skill"] for row in rows}
        self.assertTrue(WORKFLOWS <= registered)

    def test_prospect_ledger_contract(self):
        result = load_validator().validate_ledger()
        self.assertEqual(result["status"], "PASS", result["errors"])


if __name__ == "__main__":
    unittest.main()
