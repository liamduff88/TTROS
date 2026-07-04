import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "workflows" / "prompt_templates"

REQUIRED_TEMPLATE_FILES = [
    "README.md",
    "hermes_workflow_router.md",
    "codex_workflow_runner.md",
    "claude_workflow_refiner.md",
    "human_review_checklist.md",
    "receipt_closeout_template.md",
]

MANDATORY_PERMISSION_HEADER = "PERMISSION MODE — SCOPED LOCAL TASK APPROVED"
CANONICAL_CODEX_LAUNCH_COMMAND = 'cd "/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live" && codex'


class WorkflowPromptTemplatesTest(unittest.TestCase):
    def read_template(self, name):
        return (TEMPLATES / name).read_text(encoding="utf-8")

    def test_all_prompt_template_files_exist(self):
        for filename in REQUIRED_TEMPLATE_FILES:
            self.assertTrue((TEMPLATES / filename).exists(), f"missing {filename}")

    def test_readme_references_workflow_shell(self):
        text = self.read_template("README.md")
        self.assertIn("python3 tools/aos-workflow.py prepare <workflow_id>", text)
        self.assertIn("workflows/workflow_registry.json", text)
        self.assertIn("templates do not execute anything by themselves", text.lower())

    def test_codex_template_contains_required_header_and_launch_command(self):
        text = self.read_template("codex_workflow_runner.md")
        self.assertIn(MANDATORY_PERMISSION_HEADER, text)
        self.assertIn(CANONICAL_CODEX_LAUNCH_COMMAND, text)

    def test_claude_template_contains_required_header(self):
        text = self.read_template("claude_workflow_refiner.md")
        self.assertIn(MANDATORY_PERMISSION_HEADER, text)

    def test_templates_include_run_folder_contract(self):
        required = [
            "run_packet.md",
            "intake_template.md",
            "output_placeholder.md",
            "receipt_placeholder.md",
            "source workflow folder",
        ]
        for filename in REQUIRED_TEMPLATE_FILES:
            text = self.read_template(filename)
            for phrase in required:
                self.assertIn(phrase, text, f"{phrase} missing from {filename}")

    def test_templates_include_human_review_and_no_external_action_language(self):
        expected_phrases = [
            "human review",
            "no external",
            "explicit human approval",
        ]
        for filename in REQUIRED_TEMPLATE_FILES:
            text = self.read_template(filename).lower()
            for phrase in expected_phrases:
                self.assertIn(phrase, text, f"{phrase} missing from {filename}")

    def test_receipt_template_contains_required_closeout_sections(self):
        text = self.read_template("receipt_closeout_template.md")
        sections = [
            "PASS/NEEDS ATTENTION",
            "Workflow:",
            "Run folder:",
            "Files touched:",
            "Validation:",
            "External actions:",
            "Blockers:",
            "Human review needed:",
            "Next action:",
        ]
        for section in sections:
            self.assertIn(section, text)

    def test_prompt_template_tests_are_local_content_checks_only(self):
        this_file = Path(__file__).read_text(encoding="utf-8").lower()
        forbidden_runtime_calls = [
            "requests" + ".",
            "urllib" + ".",
            "socket" + ".",
            "subprocess" + ".",
            "selen" + "ium",
            "play" + "wright",
        ]
        for phrase in forbidden_runtime_calls:
            self.assertNotIn(phrase, this_file)


if __name__ == "__main__":
    unittest.main()
