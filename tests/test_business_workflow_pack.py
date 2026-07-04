import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"

WORKFLOW_FILES = {
    "marketing_pdf_package": [
        "workflow.md",
        "input/.gitkeep",
        "output/.gitkeep",
        "receipts/.gitkeep",
        "templates/package_brief.md",
        "templates/lead_magnet_package_checklist.md",
    ],
    "revenue_linkedin_outreach": [
        "workflow.md",
        "input/.gitkeep",
        "output/.gitkeep",
        "receipts/.gitkeep",
        "templates/prospect_brief.md",
        "templates/outreach_pack.md",
    ],
    "delivery_ops_documents": [
        "workflow.md",
        "input/.gitkeep",
        "output/.gitkeep",
        "receipts/.gitkeep",
        "templates/sop_template.md",
        "templates/implementation_plan_template.md",
        "templates/founder_ops_summary_template.md",
    ],
}

SCOPED_PATHS = [
    ROOT / "workflows" / name for name in WORKFLOW_FILES
] + [
    ROOT / "tests" / "test_business_workflow_pack.py",
]


class BusinessWorkflowPackTest(unittest.TestCase):
    def test_required_workflow_files_exist(self):
        for workflow_name, relative_paths in WORKFLOW_FILES.items():
            base = WORKFLOWS / workflow_name
            for relative_path in relative_paths:
                self.assertTrue((base / relative_path).exists(), f"missing {workflow_name}/{relative_path}")

    def test_workflows_are_draft_first_and_human_reviewed(self):
        expectations = {
            "marketing_pdf_package": ["draft-first", "human review", "before publishing"],
            "revenue_linkedin_outreach": ["draft only", "human review", "do not send"],
            "delivery_ops_documents": ["draft-first", "human review", "Liam approval"],
        }
        for workflow_name, phrases in expectations.items():
            text = (WORKFLOWS / workflow_name / "workflow.md").read_text(encoding="utf-8")
            lowered = text.lower()
            for phrase in phrases:
                self.assertIn(phrase.lower(), lowered, f"{phrase} missing from {workflow_name}")

    def test_linkedin_workflow_has_no_automation_or_crm_mutation(self):
        text = (WORKFLOWS / "revenue_linkedin_outreach" / "workflow.md").read_text(encoding="utf-8").lower()
        self.assertIn("do not automate linkedin", text)
        self.assertIn("do not scrape private data", text)
        self.assertIn("do not mutate crm", text)

    def test_delivery_workflow_requires_liam_approval_for_client_actions(self):
        text = (WORKFLOWS / "delivery_ops_documents" / "workflow.md").read_text(encoding="utf-8").lower()
        self.assertIn("do not send client deliverables without liam approval", text)
        self.assertIn("do not change client systems without liam approval", text)

    def test_marketing_workflow_hands_off_to_pdf_branding(self):
        text = (WORKFLOWS / "marketing_pdf_package" / "workflow.md").read_text(encoding="utf-8").lower()
        self.assertIn("workflows/pdf_branding", text)
        self.assertIn("pdf source markdown", text)
        self.assertIn("receipt format", text)

    def test_no_forbidden_legacy_references_in_pack(self):
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

    def test_no_dashboard_telegram_hermes_wiring_files_in_pack(self):
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
