import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"

WORKFLOW_FILES = {
    "revenue_sales_prep": [
        "workflow.md",
        "templates/intake_template.md",
        "templates/output_template.md",
        "templates/receipt_template.md",
        "examples/README.md",
        "receipts/batch2_added.md",
    ],
    "marketing_content_repurposing": [
        "workflow.md",
        "templates/intake_template.md",
        "templates/output_template.md",
        "templates/receipt_template.md",
        "examples/README.md",
        "receipts/batch2_added.md",
    ],
    "delivery_client_kickoff": [
        "workflow.md",
        "templates/intake_template.md",
        "templates/output_template.md",
        "templates/receipt_template.md",
        "examples/README.md",
        "receipts/batch2_added.md",
    ],
    "operations_founder_review": [
        "workflow.md",
        "templates/intake_template.md",
        "templates/output_template.md",
        "templates/receipt_template.md",
        "examples/README.md",
        "receipts/batch2_added.md",
    ],
}

REQUIRED_SECTIONS = [
    "purpose:",
    "owner agent:",
    "## when to use",
    "## inputs",
    "## local-only steps",
    "## output contract",
    "## stop conditions",
    "## definition of done",
    "## receipt format",
    "## validation notes",
]

SCOPED_PATHS = [
    ROOT / "workflows" / name for name in WORKFLOW_FILES
] + [
    ROOT / "tests" / "test_business_workflow_pack_batch2.py",
]


class BusinessWorkflowPackBatch2Test(unittest.TestCase):
    def test_required_workflow_files_exist(self):
        for workflow_name, relative_paths in WORKFLOW_FILES.items():
            base = WORKFLOWS / workflow_name
            self.assertTrue(base.exists(), f"missing workflow folder {workflow_name}")
            for relative_path in relative_paths:
                self.assertTrue((base / relative_path).exists(), f"missing {workflow_name}/{relative_path}")

    def test_workflows_have_required_sections(self):
        for workflow_name in WORKFLOW_FILES:
            text = (WORKFLOWS / workflow_name / "workflow.md").read_text(encoding="utf-8").lower()
            for section in REQUIRED_SECTIONS:
                self.assertIn(section, text, f"{section} missing from {workflow_name}")

    def test_workflows_include_stop_conditions_and_review_gates(self):
        expectations = {
            "revenue_sales_prep": [
                "stop conditions",
                "human review",
                "do not send outreach",
                "do not mutate crm",
                "before external use",
            ],
            "marketing_content_repurposing": [
                "stop conditions",
                "human review",
                "do not publish",
                "not published by workflow",
                "before external use",
            ],
            "delivery_client_kickoff": [
                "stop conditions",
                "human review",
                "do not send client deliverables",
                "do not request credentials in plain text",
                "before client-facing use",
            ],
            "operations_founder_review": [
                "stop conditions",
                "human review",
                "do not book meetings",
                "do not send emails",
                "before external use",
            ],
        }
        for workflow_name, phrases in expectations.items():
            text = (WORKFLOWS / workflow_name / "workflow.md").read_text(encoding="utf-8").lower()
            for phrase in phrases:
                self.assertIn(phrase, text, f"{phrase} missing from {workflow_name}")

    def test_each_workflow_has_receipt_template_or_receipt_note(self):
        for workflow_name in WORKFLOW_FILES:
            workflow_text = (WORKFLOWS / workflow_name / "workflow.md").read_text(encoding="utf-8").lower()
            receipt_template = WORKFLOWS / workflow_name / "templates" / "receipt_template.md"
            self.assertTrue(receipt_template.exists(), f"missing receipt template for {workflow_name}")
            self.assertIn("receipt", workflow_text, f"receipt note missing from {workflow_name}")
            receipt_text = receipt_template.read_text(encoding="utf-8").lower()
            self.assertIn("human review status", receipt_text)

    def test_tests_and_workflows_are_local_only(self):
        required_local_language = [
            "local-only",
            "no network",
            "no network, connectors, dashboard, telegram, hermes",
            "external service is required",
        ]
        for workflow_name in WORKFLOW_FILES:
            text = (WORKFLOWS / workflow_name / "workflow.md").read_text(encoding="utf-8").lower()
            for phrase in required_local_language:
                self.assertIn(phrase, text, f"{phrase} missing from {workflow_name}")

    def test_no_forbidden_legacy_or_external_runtime_references_in_pack(self):
        forbidden = [
            re.compile(r"\b" + "z" + "pc" + r"\b", re.IGNORECASE),
            re.compile("legacy" + "_" + "harvest", re.IGNORECASE),
            re.compile("super" + "_" + "ai" + "_" + "system" + "_" + "review", re.IGNORECASE),
            re.compile("super" + " " + "ai" + " " + "system" + " " + "review", re.IGNORECASE),
            re.compile(r"north\s*shore", re.IGNORECASE),
        ]
        for base in SCOPED_PATHS:
            paths = [base] if base.is_file() else [path for path in base.rglob("*") if path.is_file()]
            for path in paths:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for pattern in forbidden:
                    self.assertIsNone(pattern.search(text), f"{pattern.pattern} found in {path}")

    def test_no_forbidden_wiring_paths_in_pack(self):
        forbidden_path_parts = {
            "dashboard",
            "connectors",
            "telegram_bridge",
            "hermes",
            "queue",
            "backend",
            "routes",
        }
        for path in SCOPED_PATHS:
            relative_parts = {part.lower() for part in path.relative_to(ROOT).parts}
            self.assertTrue(
                relative_parts.isdisjoint(forbidden_path_parts),
                f"scoped pack path touches forbidden wiring area: {path}",
            )


if __name__ == "__main__":
    unittest.main()
