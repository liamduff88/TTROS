import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows" / "pdf_branding"


class PdfBrandingWorkflowTest(unittest.TestCase):
    def test_sample_markdown_exists(self):
        sample = WORKFLOW / "input" / "sample_ttr_report.md"
        self.assertTrue(sample.exists())
        self.assertIn("Time to Revenue", sample.read_text(encoding="utf-8"))

    def test_agentic_os_lead_magnet_input_exists(self):
        lead_magnet = WORKFLOW / "input" / "agentic_os_not_bureaucracy_lead_magnet.md"
        self.assertTrue(lead_magnet.exists())
        text = lead_magnet.read_text(encoding="utf-8")
        self.assertIn("One Working AI System Beats More AI Architecture", text)
        self.assertIn('Comment or DM "SYSTEM"', text)

    def test_render_script_exists(self):
        self.assertTrue((WORKFLOW / "scripts" / "render_pdf.py").exists())
        self.assertTrue((WORKFLOW / "scripts" / "render_pdf.ps1").exists())

    def test_brand_tokens_json_loads(self):
        tokens = json.loads((WORKFLOW / "brand" / "time-to-revenue.tokens.json").read_text(encoding="utf-8"))
        self.assertEqual(tokens["colors"]["executiveGraphite"], "#111315")
        self.assertEqual(tokens["colors"]["deepInk"], "#0D1418")
        self.assertEqual(tokens["colors"]["champagne"], "#B89B63")
        self.assertEqual(tokens["colors"]["warmStone"], "#D8D0C2")
        self.assertEqual(tokens["colors"]["ivory"], "#F7F3EA")
        self.assertIn("Geist", tokens["fonts"]["heading"])
        self.assertIn("Inter", tokens["fonts"]["body"])
        self.assertEqual(tokens["page"]["size"], "A4")

    def test_css_exists_and_includes_print_page_rules(self):
        css = (WORKFLOW / "styles" / "ttr_print.css").read_text(encoding="utf-8")
        self.assertIn("@page", css)
        self.assertIn("@media print", css)
        self.assertIn("size: A4", css)
        self.assertIn("var(--ttr-champagne)", css)
        self.assertIn("var(--ttr-executive-graphite)", css)
        self.assertIn(".page-break", css)
        self.assertIn("page-break-before: always", css)
        self.assertIn("break-before: page", css)
        self.assertIn("widows: 3", css)
        self.assertIn("orphans: 3", css)

    def test_pagebreak_marker_renders_to_print_safe_element(self):
        sys.path.insert(0, str(WORKFLOW / "scripts"))
        try:
            import render_pdf

            html = render_pdf.markdown_to_html("# Title\n\nIntro\n\n<!-- pagebreak -->\n\n## Next\n\nBody")
        finally:
            sys.path.remove(str(WORKFLOW / "scripts"))

        self.assertIn('<div class="page-break" aria-hidden="true"></div>', html)
        self.assertIn('<section class="content-section">', html)

    def test_template_and_brand_styles_do_not_use_green_strip(self):
        paths = [
            WORKFLOW / "templates" / "ttr_report_template.html",
            WORKFLOW / "styles" / "ttr_print.css",
            WORKFLOW / "brand" / "time-to-revenue.tokens.json",
        ]
        forbidden_terms = ["signal" + "Green", "#" + "22C55E"]
        forbidden = [re.compile(re.escape(term), re.IGNORECASE) for term in forbidden_terms]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden:
                self.assertIsNone(pattern.search(text), f"{pattern.pattern} found in {path}")

    def test_render_command_creates_pdf_or_html_fallback(self):
        output = WORKFLOW / "output" / "unit_test_sample_ttr_report.pdf"
        fallback = output.with_suffix(".html")
        output.unlink(missing_ok=True)
        fallback.unlink(missing_ok=True)

        result = subprocess.run(
            [
                sys.executable,
                str(WORKFLOW / "scripts" / "render_pdf.py"),
                "--input",
                str(WORKFLOW / "input" / "sample_ttr_report.md"),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        if output.exists() and output.stat().st_size > 0:
            self.assertIn("PASS", result.stdout)
        else:
            self.assertTrue(fallback.exists())
            self.assertGreater(fallback.stat().st_size, 0)
            self.assertIn("NEEDS ATTENTION", result.stdout)
            self.assertIn("python3 -m pip install playwright", result.stdout)
        output.unlink(missing_ok=True)
        fallback.unlink(missing_ok=True)

    def test_no_forbidden_legacy_source_paths_in_workflow_files(self):
        forbidden = [re.compile(r"zpc", re.IGNORECASE), re.compile(r"super ai system", re.IGNORECASE)]
        for path in WORKFLOW.rglob("*"):
            if path.is_file() and path.suffix.lower() not in {".pdf", ".png"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for pattern in forbidden:
                    self.assertIsNone(pattern.search(text), f"{pattern.pattern} found in {path}")

    def test_no_secret_shaped_content_was_copied(self):
        secret_patterns = [
            re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
            re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
            re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE),
            re.compile(r"(api[_-]?key|password|secret|credential)\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
        ]
        for base in [WORKFLOW, ROOT / "tests" / "test_pdf_branding_workflow.py"]:
            paths = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()]
            for path in paths:
                if path.suffix.lower() in {".pdf", ".png"}:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                for pattern in secret_patterns:
                    self.assertIsNone(pattern.search(text), f"secret-shaped content found in {path}")


if __name__ == "__main__":
    unittest.main()
