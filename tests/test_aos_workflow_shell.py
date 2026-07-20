import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "aos-workflow.py"
WORKFLOWS = ROOT / "workflows"

EXPECTED_WORKFLOWS = {
    "linkedin_content",
    "pdf_branding",
    "marketing_pdf_package",
    "linkedin_carousel_from_md",
    "revenue_linkedin_outreach",
    "delivery_ops_documents",
    "revenue_sales_prep",
    "marketing_content_repurposing",
    "delivery_client_kickoff",
    "operations_founder_review",
    "prospecting_daily_run",
    "prospecting_week_review",
}


def load_tool_module():
    spec = importlib.util.spec_from_file_location("aos_workflow", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AosWorkflowShellTest(unittest.TestCase):
    def test_registry_includes_existing_expected_workflows_only(self):
        registry = json.loads((WORKFLOWS / "workflow_registry.json").read_text(encoding="utf-8"))
        workflow_ids = {workflow["id"] for workflow in registry["workflows"]}
        existing_expected = {workflow_id for workflow_id in EXPECTED_WORKFLOWS if (WORKFLOWS / workflow_id).exists()}

        self.assertEqual(workflow_ids, existing_expected)
        for workflow in registry["workflows"]:
            self.assertTrue((ROOT / workflow["source_path"]).exists(), workflow["source_path"])
            template_path = workflow.get("intake_template_path")
            if template_path:
                self.assertTrue((ROOT / template_path).exists(), template_path)

    def test_list_command_reads_registry(self):
        result = subprocess.run(
            [sys.executable, str(TOOL), "list"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("revenue_sales_prep", result.stdout)
        self.assertIn("Marketing PDF Package Workflow", result.stdout)

    def test_show_command_prints_summary_without_running_workflow(self):
        result = subprocess.run(
            [sys.executable, str(TOOL), "show", "revenue_sales_prep"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Workflow ID: revenue_sales_prep", result.stdout)
        self.assertIn("Owner agent: Revenue", result.stdout)
        self.assertIn("templates/intake_template.md", result.stdout)

    def test_prepare_dry_run_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            make_fixture_registry(fixture)

            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--root",
                    str(fixture),
                    "prepare",
                    "sample_workflow",
                    "--run-id",
                    "unit_run",
                    "--dry-run",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Dry run: no files written.", result.stdout)
            self.assertIn("results/workflow_runs/sample_workflow/unit_run/run_packet.md", result.stdout)
            self.assertFalse((fixture / "results").exists())

    def test_prepare_creates_empty_run_scaffold_from_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            make_fixture_registry(fixture)

            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--root",
                    str(fixture),
                    "prepare",
                    "sample_workflow",
                    "--run-id",
                    "unit_run",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = fixture / "results" / "workflow_runs" / "sample_workflow" / "unit_run"
            self.assertTrue((run_dir / "run_packet.md").exists())
            self.assertTrue((run_dir / "intake_template.md").exists())
            self.assertEqual((run_dir / "intake_template.md").read_text(encoding="utf-8"), "# Intake\n\n")
            packet = (run_dir / "run_packet.md").read_text(encoding="utf-8")
            self.assertIn("Workflow id: sample_workflow", packet)
            self.assertIn("Owner agent: Revenue", packet)
            self.assertIn("Output placeholder:", packet)
            self.assertIn("Receipt placeholder:", packet)
            self.assertIn("Human review reminder:", packet)
            self.assertIn("No external action reminder:", packet)
            self.assertTrue((run_dir / "output_placeholder.md").exists())
            self.assertTrue((run_dir / "receipt_placeholder.md").exists())

    def test_prepare_creates_intake_packet_when_template_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            make_fixture_registry(fixture, template=False)
            module = load_tool_module()

            run_dir = module.prepare_workflow(fixture, "sample_workflow", "unit_run", dry_run=False)

            intake = run_dir / "intake.md"
            self.assertTrue(intake.exists())
            self.assertIn("empty local intake scaffold", intake.read_text(encoding="utf-8"))


def make_fixture_registry(root, template=True):
    workflow_dir = root / "workflows" / "sample_workflow"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "workflow.md").write_text("# Sample Workflow\n", encoding="utf-8")
    if template:
        (workflow_dir / "templates").mkdir()
        (workflow_dir / "templates" / "intake_template.md").write_text("# Intake\n\n", encoding="utf-8")

    registry = {
        "version": 1,
        "workflows": [
            {
                "id": "sample_workflow",
                "name": "Sample Workflow",
                "owner_agent": "Revenue",
                "summary": "Fixture workflow.",
                "source_path": "workflows/sample_workflow/workflow.md",
                "intake_template_path": "workflows/sample_workflow/templates/intake_template.md" if template else None,
                "intake_reference_path": "workflows/sample_workflow/input",
            }
        ],
    }
    (root / "workflows" / "workflow_registry.json").write_text(json.dumps(registry), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
