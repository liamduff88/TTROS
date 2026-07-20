"""Canonical LinkedIn carousel render/package contracts.

Revisit: when carousel input, PDF, or package schemas change. · Last touched: 2026-07-20.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows" / "linkedin_carousel_from_md"
PDF_WORKFLOW = ROOT / "workflows" / "pdf_branding"
BUILDER = WORKFLOW / "scripts" / "build_package.py"
PDF_PYTHON = ROOT / ".venv-pdf" / "bin" / "python"
FIXTURE = WORKFLOW / "fixtures" / "agentic_os_not_bureaucracy"
SOURCE = FIXTURE / "source.md"
ARTIFACTS = {
    "source.md",
    "carousel_draft.md",
    "linkedin_caption.md",
    "carousel.pdf",
    "review_receipt.md",
    "post_package.json",
}


def load_builder_module():
    spec = importlib.util.spec_from_file_location("linkedin_carousel_builder", BUILDER)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER_MODULE = load_builder_module()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LinkedinCarouselWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PDF_PYTHON.is_file():
            raise AssertionError("missing declared .venv-pdf environment")
        cls.temp = tempfile.TemporaryDirectory(prefix=".unit-carousel-", dir=WORKFLOW / "output")
        cls.output = Path(cls.temp.name) / "package"
        cls.result = cls.run_builder()
        if cls.result.returncode != 0:
            raise AssertionError(cls.result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def run_builder(
        cls,
        *,
        draft: Path | None = None,
        caption: Path | None = None,
        resource_metadata: Path | None = None,
        output: Path | None = None,
        item_id: str = "UNIT-CAROUSEL",
    ):
        command = [
            str(PDF_PYTHON),
            str(BUILDER),
            "--source",
            str(SOURCE),
            "--carousel-draft",
            str(draft or FIXTURE / "carousel_draft.md"),
            "--caption",
            str(caption or FIXTURE / "linkedin_caption.md"),
            "--output-dir",
            str(output or cls.output),
            "--item-id",
            item_id,
        ]
        if resource_metadata:
            command.extend(("--resource-metadata", str(resource_metadata)))
        return subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def pdf_probe(self, pdf_path: Path) -> dict:
        script = """
import json, sys
from pypdf import PdfReader
reader = PdfReader(sys.argv[1], strict=True)
print(json.dumps({
    'pages': len(reader.pages),
    'width': float(reader.pages[0].mediabox.width),
    'height': float(reader.pages[0].mediabox.height),
    'texts': [' '.join((page.extract_text() or '').split()) for page in reader.pages],
    'links': sum(len(page.get('/Annots') or []) for page in reader.pages),
}))
"""
        result = subprocess.run(
            [str(PDF_PYTHON), "-c", script, str(pdf_path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_valid_slide_input_succeeds_with_complete_package(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertIn("PASS: ready_for_review", self.result.stdout)
        self.assertEqual({path.name for path in self.output.iterdir()}, ARTIFACTS)

    def test_malformed_or_incomplete_input_fails_clearly(self):
        with tempfile.TemporaryDirectory(prefix="carousel-invalid-") as temporary:
            invalid = Path(temporary) / "invalid.md"
            invalid.write_text("# One\n\nCopy\n\n<!-- slide -->\n\n# Two\n\nCopy\n", encoding="utf-8")
            result = self.run_builder(draft=invalid)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("carousel must contain 6-10 slides", result.stderr)

    def test_genuine_readable_pdf_matches_slide_count_and_dimensions(self):
        probe = self.pdf_probe(self.output / "carousel.pdf")
        draft = (FIXTURE / "carousel_draft.md").read_text(encoding="utf-8")
        slide_count = draft.count("<!-- slide -->") + 1
        self.assertEqual(probe["pages"], slide_count)
        self.assertEqual((probe["width"], probe["height"]), (576.0, 720.0))
        self.assertGreater((self.output / "carousel.pdf").stat().st_size, 10_000)
        self.assertTrue(all(text for text in probe["texts"]))
        self.assertEqual(len(set(probe["texts"])), slide_count)
        self.assertIn("We rebuilt our AI", probe["texts"][0])
        self.assertIn("actually mattered", probe["texts"][0].replace("whatactually", "what actually"))
        self.assertIn("Where does work", probe["texts"][-1])
        self.assertIn(
            "Take the full assessment using the link in the LinkedIn post below.",
            probe["texts"][-1],
        )
        self.assertNotIn("http", "\n".join(probe["texts"]).lower())
        self.assertNotIn("[ADD RESOURCE LINK BEFORE POSTING]", "\n".join(probe["texts"]))
        self.assertEqual(probe["links"], 0)

    def test_placeholder_pdf_cannot_pass_validation(self):
        with tempfile.TemporaryDirectory(prefix="carousel-placeholder-") as temporary:
            placeholder = Path(temporary) / "placeholder.pdf"
            placeholder.write_bytes(b"%PDF-1.4\nplaceholder\n" + (b"0" * 12_000) + b"\n%%EOF\n")
            script = f"""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('renderer', {str(PDF_WORKFLOW / 'scripts' / 'render_pdf.py')!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
slides = module.parse_carousel_slides(Path({str(FIXTURE / 'carousel_draft.md')!r}).read_text(encoding='utf-8'))
try:
    module.validate_carousel_pdf(Path({str(placeholder)!r}), slides)
except RuntimeError as exc:
    print(exc)
    raise SystemExit(0)
raise SystemExit(1)
"""
            result = subprocess.run(
                [str(PDF_PYTHON), "-c", script], cwd=ROOT, text=True, capture_output=True, check=False
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("structurally readable", result.stdout)

    def test_caption_and_source_association_is_hashed_and_checked(self):
        package = json.loads((self.output / "post_package.json").read_text(encoding="utf-8"))
        association = package["source_association"]
        self.assertEqual(association["source_sha256"], file_sha256(self.output / "source.md"))
        self.assertEqual(association["carousel_draft_sha256"], file_sha256(self.output / "carousel_draft.md"))
        self.assertEqual(association["linkedin_caption_sha256"], file_sha256(self.output / "linkedin_caption.md"))
        self.assertIn("rebuilt our internal AI system", package["caption"])
        self.assertIn("rebuilt our ai system", association["opening_hook"].lower())

        with tempfile.TemporaryDirectory(prefix="carousel-caption-") as temporary:
            unrelated = Path(temporary) / "caption.md"
            unrelated.write_text(
                "# Caption\n\nA completely unrelated note about quarterly accounting controls and tax records.\n\n"
                "{{RESOURCE_CAPTION_CTA}}\n\n{{RESOURCE_LINK}}\n",
                encoding="utf-8",
            )
            result = self.run_builder(caption=unrelated)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not clearly associated", result.stderr)

    def test_artifacts_receipt_and_registry_use_existing_machinery(self):
        package = json.loads((self.output / "post_package.json").read_text(encoding="utf-8"))
        registry = json.loads((ROOT / "workflows" / "workflow_registry.json").read_text(encoding="utf-8"))
        self.assertEqual(package["status"], "ready_for_review")
        self.assertEqual(package["render"]["page_count"], package["render"]["slide_count"])
        self.assertTrue(all(str(self.output.relative_to(ROOT)) in value for value in package["artifacts"].values()))
        self.assertIn("linkedin_carousel_from_md", {row["id"] for row in registry["workflows"]})
        receipt = (self.output / "review_receipt.md").read_text(encoding="utf-8")
        self.assertIn("## Token usage", receipt)
        self.assertIn("External action: none", receipt)

    def test_context_aware_resource_types_and_actions(self):
        cases = {
            "guide": ("A practical guide to fixing handoffs.", "guide", "access", "full guide"),
            "quiz": ("Take the quick operations quiz.", "quiz", "take", "Take the full quiz"),
            "questionnaire": (
                "Download the operations questionnaire.",
                "questionnaire",
                "download",
                "Download the full questionnaire",
            ),
            "template": (
                "Use this downloadable handoff template.",
                "template",
                "download",
                "Download the complete template",
            ),
            "downloadable document": (
                "A downloadable document for the operator.",
                "resource",
                "download",
                "Download the full resource",
            ),
        }
        for label, (source, expected_type, expected_action, wording) in cases.items():
            with self.subTest(label=label):
                resolved = BUILDER_MODULE.resolve_resource_cta(source, "Draft content", "Caption context")
                self.assertEqual(resolved["resource_type"], expected_type)
                self.assertEqual(resolved["action"], expected_action)
                self.assertIn(wording, resolved["final_slide_cta"])

    def test_unknown_content_uses_exact_neutral_fallback(self):
        resolved = BUILDER_MODULE.resolve_resource_cta(
            "Ideas for making operations clearer.", "Draft content", "Caption context"
        )
        self.assertEqual(resolved["resource_type"], "resource")
        self.assertTrue(resolved["fallback"])
        self.assertEqual(resolved["inference_source"], "neutral_fallback")
        self.assertEqual(
            resolved["final_slide_cta"],
            "Access the full resource using the link in the LinkedIn post below.",
        )

    def test_explicit_resource_metadata_precedes_content_inference(self):
        resolved = BUILDER_MODULE.resolve_resource_cta(
            "This source repeatedly describes a quiz and quiz results.",
            "Quiz draft",
            "Quiz caption",
            {"resource_type": "questionnaire", "action": "get"},
        )
        self.assertEqual(resolved["resource_type"], "questionnaire")
        self.assertEqual(resolved["action"], "get")
        self.assertEqual(resolved["inference_source"], "explicit_metadata.resource_type")
        self.assertIn("Get the full questionnaire", resolved["final_slide_cta"])

    def test_pdf_source_rejects_links_placeholders_and_images(self):
        renderer = BUILDER_MODULE.load_renderer()
        draft = (FIXTURE / "carousel_draft.md").read_text(encoding="utf-8")
        caption = (FIXTURE / "linkedin_caption.md").read_text(encoding="utf-8")
        cta = BUILDER_MODULE.resolve_resource_cta(
            SOURCE.read_text(encoding="utf-8"), draft, caption
        )
        cases = {
            "placeholder": "[ADD RESOURCE LINK BEFORE POSTING]",
            "url": "https://example.com/assessment",
            "embedded link": "[assessment](assessment.pdf)",
            "QR image": "![QR code](qr.png)",
        }
        for label, forbidden in cases.items():
            with self.subTest(label=label):
                invalid = draft.replace("{{RESOURCE_CTA}}", f"{{{{RESOURCE_CTA}}}}\n\n{forbidden}")
                with self.assertRaisesRegex(ValueError, "PDF source"):
                    BUILDER_MODULE.apply_resource_cta(invalid, caption, cta, renderer)

    def test_proof_metadata_matches_generated_assessment_cta(self):
        package = json.loads((self.output / "post_package.json").read_text(encoding="utf-8"))
        resource = package["resource_cta"]
        draft = (self.output / "carousel_draft.md").read_text(encoding="utf-8")
        caption = (self.output / "linkedin_caption.md").read_text(encoding="utf-8")
        self.assertEqual(resource["resource_type"], "assessment")
        self.assertEqual(resource["action"], "take")
        self.assertEqual(resource["inference_source"], "deterministic_content_inference")
        self.assertFalse(resource["fallback"])
        self.assertEqual(
            resource["final_slide_cta"],
            "Take the full assessment using the link in the LinkedIn post below.",
        )
        self.assertEqual(resource["caption_cta"], "Take the full assessment here:")
        self.assertEqual(resource["caption_link_status"], "review_placeholder")
        self.assertEqual(resource["caption_link"], "[ADD RESOURCE LINK BEFORE POSTING]")
        self.assertIn(resource["final_slide_cta"], draft)
        self.assertIn(
            "Take the full assessment here:\n[ADD RESOURCE LINK BEFORE POSTING]",
            caption,
        )
        self.assertNotIn("[ADD RESOURCE LINK BEFORE POSTING]", draft)

    def test_supplied_url_is_preserved_in_caption_but_not_pdf(self):
        metadata_path = Path(self.temp.name) / "resource.json"
        configured_url = "https://example.com/resources/ai-operations-assessment?campaign=linkedin-carousel"
        metadata_path.write_text(json.dumps({"url": configured_url}), encoding="utf-8")
        output = Path(self.temp.name) / "url-package"
        result = self.run_builder(
            resource_metadata=metadata_path,
            output=output,
            item_id="UNIT-CAROUSEL-URL",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        package = json.loads((output / "post_package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["resource_cta"]["caption_link"], configured_url)
        self.assertEqual(package["resource_cta"]["caption_link_status"], "configured")
        self.assertIn(configured_url, package["caption"])
        self.assertIn(configured_url, (output / "linkedin_caption.md").read_text(encoding="utf-8"))
        probe = self.pdf_probe(output / "carousel.pdf")
        self.assertNotIn(configured_url, "\n".join(probe["texts"]))
        self.assertEqual(probe["links"], 0)

    def test_default_path_contains_no_dm_or_checklist_cta(self):
        active_text = "\n".join(
            (self.output / name).read_text(encoding="utf-8")
            for name in ("carousel_draft.md", "linkedin_caption.md", "review_receipt.md", "post_package.json")
        ).lower()
        self.assertNotIn("dm me", active_text)
        self.assertNotIn("dm **", active_text)
        self.assertNotIn("checklist", active_text)
        with self.assertRaisesRegex(ValueError, "future explicit workflow contract"):
            BUILDER_MODULE.resolve_resource_cta(
                "A guide to operations.", "Draft", "Caption", {"cta_mode": "dm"}
            )

    def test_cta_resolution_is_deterministic(self):
        inputs = ("A scored assessment with five questions.", "Draft", "Caption")
        self.assertEqual(
            BUILDER_MODULE.resolve_resource_cta(*inputs),
            BUILDER_MODULE.resolve_resource_cta(*inputs),
        )

    def test_rerun_is_deterministic_and_idempotent(self):
        before = {name: file_sha256(self.output / name) for name in ARTIFACTS}
        result = self.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {name: file_sha256(self.output / name) for name in ARTIFACTS}
        self.assertEqual(before, after)
        self.assertEqual({path.name for path in self.output.iterdir()}, ARTIFACTS)

    def test_no_external_action_code_or_state_is_present(self):
        source = BUILDER.read_text(encoding="utf-8")
        for forbidden in ("urllib", "requests", "composio", "linkedin.com", "subprocess"):
            self.assertNotIn(forbidden, source.lower())
        package = json.loads((self.output / "post_package.json").read_text(encoding="utf-8"))
        self.assertTrue(package["manual_handoff_only"])
        self.assertFalse(package["external_transmission"])
        self.assertIn("No LinkedIn post", package["external_action_confirmation"])


if __name__ == "__main__":
    unittest.main()
