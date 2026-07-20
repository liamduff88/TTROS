#!/usr/bin/env python3
"""Build one canonical, local-only LinkedIn carousel review package.

Revisit: when the carousel CTA, package schema, or PDF renderer contract changes. · Last touched: 2026-07-20.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WORKFLOW_ROOT.parents[1]
OUTPUT_ROOT = WORKFLOW_ROOT / "output"
RENDERER_PATH = REPO_ROOT / "workflows" / "pdf_branding" / "scripts" / "render_pdf.py"
EXPECTED_ARTIFACTS = (
    "source.md",
    "carousel_draft.md",
    "linkedin_caption.md",
    "carousel.pdf",
    "review_receipt.md",
    "post_package.json",
)
WORD_RE = re.compile(r"[A-Za-z0-9']+")
HOOK_STOP_WORDS = {"about", "actually", "after", "again", "carousel", "from", "here", "into", "that", "this", "what", "when", "with", "your"}
FINAL_CTA_MARKER = "{{RESOURCE_CTA}}"
CAPTION_CTA_MARKER = "{{RESOURCE_CAPTION_CTA}}"
RESOURCE_LINK_MARKER = "{{RESOURCE_LINK}}"
MISSING_RESOURCE_LINK = "[ADD RESOURCE LINK BEFORE POSTING]"
ALLOWED_RESOURCE_TYPES = {
    "guide",
    "checklist",
    "questionnaire",
    "quiz",
    "assessment",
    "worksheet",
    "template",
    "report",
    "scorecard",
    "framework",
    "resource",
}
RESOURCE_TYPE_ALIASES = {
    "check list": "checklist",
    "download": "resource",
    "downloadable document": "resource",
    "document": "resource",
    "playbook": "guide",
    "score card": "scorecard",
    "self assessment": "assessment",
    "survey": "questionnaire",
    "white paper": "report",
    "workbook": "worksheet",
}
RESOURCE_TERMS = {
    "guide": ("guide", "playbook", "handbook", "manual"),
    "checklist": ("checklist", "check list"),
    "questionnaire": ("questionnaire", "survey"),
    "quiz": ("quiz",),
    "assessment": ("assessment", "self-assessment", "self assessment", "audit"),
    "worksheet": ("worksheet", "workbook"),
    "template": ("template",),
    "report": ("report", "white paper", "research paper"),
    "scorecard": ("scorecard", "score card"),
    "framework": ("framework",),
}
DEFAULT_ACTIONS = {
    "guide": "access",
    "checklist": "download",
    "questionnaire": "download",
    "quiz": "take",
    "assessment": "take",
    "worksheet": "download",
    "template": "download",
    "report": "download",
    "scorecard": "access",
    "framework": "access",
    "resource": "access",
}
ALLOWED_ACTIONS = {"access", "download", "get", "take"}
RESOURCE_METADATA_FIELDS = {"resource_type", "action", "title", "url", "context", "cta_mode"}


def load_renderer():
    spec = importlib.util.spec_from_file_location("ttr_pdf_renderer", RENDERER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load canonical renderer: {RENDERER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_markdown(path: Path, label: str) -> str:
    if not path.is_file():
        raise ValueError(f"{label} file not found: {path}")
    if path.suffix.lower() != ".md":
        raise ValueError(f"{label} must be a Markdown (.md) file")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{label} is empty")
    return text + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def validate_output_dir(path: Path) -> Path:
    resolved = path.resolve()
    output_root = OUTPUT_ROOT.resolve()
    try:
        relative = resolved.relative_to(output_root)
    except ValueError as exc:
        raise ValueError(f"output directory must be inside {output_root}") from exc
    if not relative.parts:
        raise ValueError("output directory must be a named run folder below the workflow output directory")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("output directory contains an unsafe path segment")
    return resolved


def association_terms(text: str) -> set[str]:
    return {
        word.lower()
        for word in WORD_RE.findall(text)
        if len(word) >= 5 and word.lower() not in HOOK_STOP_WORDS
    }


def phrase_present(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])", text, re.IGNORECASE))


def normalize_resource_type(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().lower().replace("_", " ").replace("-", " "))
    normalized = RESOURCE_TYPE_ALIASES.get(normalized, normalized)
    if normalized not in ALLOWED_RESOURCE_TYPES:
        choices = ", ".join(sorted(ALLOWED_RESOURCE_TYPES))
        raise ValueError(f"unsupported resource_type {value!r}; expected one of: {choices}")
    return normalized


def normalize_resource_metadata(raw: dict[str, Any] | None) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("resource metadata must be a JSON object")
    unknown = sorted(set(raw) - RESOURCE_METADATA_FIELDS)
    if unknown:
        raise ValueError(f"unsupported resource metadata fields: {', '.join(unknown)}")
    metadata: dict[str, str] = {}
    for key, value in raw.items():
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"resource metadata field {key!r} must be a non-empty string")
        metadata[key] = value.strip()
    mode = metadata.get("cta_mode", "link").lower()
    if mode != "link":
        raise ValueError("only link CTA mode is active; a DM CTA requires a future explicit workflow contract")
    metadata["cta_mode"] = "link"
    if "resource_type" in metadata:
        original_type = metadata["resource_type"]
        metadata["resource_type"] = normalize_resource_type(original_type)
        if original_type.strip().lower().replace("_", " ").replace("-", " ") in {
            "download",
            "downloadable document",
            "document",
        }:
            metadata.setdefault("action", "download")
    if "action" in metadata:
        metadata["action"] = metadata["action"].lower()
        if metadata["action"] not in ALLOWED_ACTIONS:
            raise ValueError(f"unsupported CTA action {metadata['action']!r}")
    if "url" in metadata:
        if not re.fullmatch(r"https?://[^\s]+", metadata["url"]):
            raise ValueError("resource URL must be one visible http:// or https:// URL")
    return metadata


def inference_segments(
    source: str, draft: str, caption: str, metadata: dict[str, str]
) -> list[tuple[int, str, str]]:
    source_lines = source.splitlines()
    source_titles = "\n".join(
        line
        for line in source_lines
        if re.match(r"^#{1,6}\s+", line)
        or re.match(r"^(working\s+)?title\s*:", line, re.IGNORECASE)
    )
    segments: list[tuple[int, str, str]] = []
    if metadata.get("title"):
        segments.append((6, "structured_metadata.title", metadata["title"]))
    if metadata.get("context"):
        segments.append((5, "structured_metadata.context", metadata["context"]))
    if source_titles:
        segments.append((5, "source.title_or_heading", source_titles))
    segments.extend(
        ((3, "source.content", source), (2, "carousel.content", draft), (2, "caption.context", caption))
    )
    if metadata.get("url"):
        segments.append((2, "resource_link.context", metadata["url"]))
    return segments


def infer_resource_type(
    source: str, draft: str, caption: str, metadata: dict[str, str]
) -> tuple[str, str, bool, list[str]]:
    if metadata.get("resource_type"):
        return metadata["resource_type"], "explicit_metadata.resource_type", False, [
            f"resource_type={metadata['resource_type']}"
        ]

    scores = {resource_type: 0 for resource_type in RESOURCE_TERMS}
    evidence: dict[str, list[str]] = {resource_type: [] for resource_type in RESOURCE_TERMS}
    segments = inference_segments(source, draft, caption, metadata)
    for weight, source_name, text in segments:
        for resource_type, terms in RESOURCE_TERMS.items():
            matched = next((term for term in terms if phrase_present(text, term)), None)
            if matched:
                scores[resource_type] += weight * 3
                evidence[resource_type].append(f"{source_name}:{matched}")
        lowered = text.lower()
        assessment_signal = (
            bool(re.search(r"\bself[- ]?score\b|\bscore ranges?\b", lowered))
            or (phrase_present(lowered, "questions") and phrase_present(lowered, "score"))
        )
        if assessment_signal:
            scores["assessment"] += weight * 2
            evidence["assessment"].append(f"{source_name}:questions-and-scoring")

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_type, best_score = ranked[0]
    second_score = ranked[1][1]
    if best_score >= 4 and best_score >= second_score + 2:
        return best_type, "deterministic_content_inference", False, evidence[best_type]

    combined = "\n".join(text for _, _, text in segments)
    if re.search(r"\b(downloadable document|download|pdf|\.pdf)\b", combined, re.IGNORECASE):
        return "resource", "deterministic_download_context", False, ["content:downloadable-document"]
    return "resource", "neutral_fallback", True, []


def cta_copy(resource_type: str, action: str, fallback: bool) -> tuple[str, str]:
    qualifier = "complete" if resource_type in {"framework", "template"} else "full"
    description = f"{qualifier} {resource_type}"
    if action == "take":
        return (
            f"Take the {description} using the link in the LinkedIn post below.",
            f"Take the {description} here:",
        )
    if action == "download":
        return (
            f"Download the {description} from the link in the LinkedIn post below.",
            f"Download the {description} here:",
        )
    if action == "get":
        return (
            f"Get the {description} from the link in the LinkedIn post below.",
            f"Get the {description} here:",
        )
    return (
        f"Access the {description} using the link in the LinkedIn post below.",
        f"Access the {description} here:",
    )


def resolve_resource_cta(
    source: str, draft: str, caption: str, raw_metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    metadata = normalize_resource_metadata(raw_metadata)
    resource_type, inference_source, fallback, evidence = infer_resource_type(
        source, draft, caption, metadata
    )
    action = metadata.get("action") or DEFAULT_ACTIONS[resource_type]
    if inference_source == "deterministic_download_context" and "action" not in metadata:
        action = "download"
    final_cta, caption_cta = cta_copy(resource_type, action, fallback)
    link = metadata.get("url", MISSING_RESOURCE_LINK)
    return {
        "resource_type": resource_type,
        "action": action,
        "title": metadata.get("title"),
        "final_slide_cta": final_cta,
        "caption_cta": caption_cta,
        "caption_link": link,
        "caption_link_status": "configured" if "url" in metadata else "review_placeholder",
        "inference_source": inference_source,
        "fallback": fallback,
        "evidence": evidence,
    }


def apply_resource_cta(draft: str, caption: str, cta: dict[str, Any], renderer: Any) -> tuple[str, str]:
    raw_slides = renderer.parse_carousel_slides(draft)
    if draft.count(FINAL_CTA_MARKER) != 1 or FINAL_CTA_MARKER not in raw_slides[-1]:
        raise ValueError(f"carousel draft final slide must contain exactly one {FINAL_CTA_MARKER} marker")
    if any(FINAL_CTA_MARKER in slide for slide in raw_slides[:-1]):
        raise ValueError("resource CTA marker may appear only on the final slide")
    if caption.count(CAPTION_CTA_MARKER) != 1 or caption.count(RESOURCE_LINK_MARKER) != 1:
        raise ValueError(
            f"caption must contain exactly one {CAPTION_CTA_MARKER} and one {RESOURCE_LINK_MARKER} marker"
        )
    resolved_draft = draft.replace(FINAL_CTA_MARKER, cta["final_slide_cta"])
    resolved_caption = caption.replace(CAPTION_CTA_MARKER, cta["caption_cta"]).replace(
        RESOURCE_LINK_MARKER, cta["caption_link"]
    )
    if MISSING_RESOURCE_LINK in resolved_draft:
        raise ValueError("carousel PDF source must not contain the resource-link placeholder")
    if re.search(r"(?:https?://|www\.)\S+", resolved_draft, re.IGNORECASE):
        raise ValueError("carousel PDF source must not expose a raw URL")
    if re.search(r"!?\[[^\]]*\]\([^)]+\)", resolved_draft):
        raise ValueError("carousel PDF source must not contain an embedded resource hyperlink or image")
    return resolved_draft, resolved_caption


def validate_inputs(
    source: str, draft: str, caption: str, renderer: Any, resource_cta: dict[str, Any]
) -> tuple[list[str], str]:
    if len(WORD_RE.findall(source)) < 40:
        raise ValueError("source is incomplete; provide a substantive sourced Markdown document")
    if len(WORD_RE.findall(caption)) < 12:
        raise ValueError("LinkedIn caption is incomplete")
    slides = renderer.parse_carousel_slides(draft)
    hook = renderer.carousel_heading(slides[0])
    overlap = association_terms(hook) & association_terms(caption)
    if len(overlap) < 2:
        raise ValueError(
            "LinkedIn caption is not clearly associated with the opening hook; repeat at least two meaningful hook terms"
        )
    if resource_cta["final_slide_cta"] not in slides[-1]:
        raise ValueError("final slide does not match the resolved resource CTA")
    if resource_cta["caption_cta"] not in caption or resource_cta["caption_link"] not in caption:
        raise ValueError("caption does not contain the resolved CTA and resource link")
    if re.search(r"\bdm\s+(?:me\b|[\"'“‘*])", slides[-1], re.IGNORECASE) or re.search(
        r"\bdm\s+(?:me\b|[\"'“‘*])", caption, re.IGNORECASE
    ):
        raise ValueError("DM CTA is not allowed in the active link CTA contract")
    return slides, hook


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def build_package(
    source_path: Path,
    draft_path: Path,
    caption_path: Path,
    output_dir: Path,
    item_id: str,
    resource_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", item_id):
        raise ValueError("item id must be 1-120 safe filename characters")
    output_dir = validate_output_dir(output_dir)
    source = read_markdown(source_path, "source")
    draft_template = read_markdown(draft_path, "carousel draft")
    caption_template = read_markdown(caption_path, "LinkedIn caption")
    renderer = load_renderer()
    resource_cta = resolve_resource_cta(source, draft_template, caption_template, resource_metadata)
    draft, caption = apply_resource_cta(draft_template, caption_template, resource_cta, renderer)
    slides, hook = validate_inputs(source, draft, caption, renderer, resource_cta)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".carousel-build-", dir=output_dir) as temporary_dir:
        temporary_root = Path(temporary_dir)
        temporary_draft = temporary_root / "carousel_draft.md"
        temporary_pdf = temporary_root / "carousel.pdf"
        temporary_draft.write_text(draft, encoding="utf-8")
        render_result = renderer.render_carousel(temporary_draft, temporary_pdf)
        pdf_bytes = temporary_pdf.read_bytes()

    artifact_paths = {name: output_dir / name for name in EXPECTED_ARTIFACTS}
    source_hash = sha256_text(source)
    draft_hash = sha256_text(draft)
    caption_hash = sha256_text(caption)
    pdf_hash = sha256_bytes(pdf_bytes)
    receipt = "\n".join(
        [
            "# LinkedIn Carousel Review Receipt",
            "> Expires: when this package is regenerated or reviewed. · Last touched: 2026-07-20.",
            "",
            f"- Workflow: `linkedin_carousel_from_md`",
            f"- Item id: `{item_id}`",
            f"- Source: `{display_path(source_path)}`",
            f"- Source SHA-256: `{source_hash}`",
            f"- Opening hook: {hook}",
            f"- Resource type / action: `{resource_cta['resource_type']}` / `{resource_cta['action']}`",
            f"- Final CTA: {resource_cta['final_slide_cta']}",
            f"- CTA inference: `{resource_cta['inference_source']}`; fallback: `{str(resource_cta['fallback']).lower()}`",
            f"- Caption link: `{resource_cta['caption_link_status']}`",
            f"- Slide count / PDF page count: {len(slides)} / {render_result['page_count']}",
            f"- Page size: {int(render_result['width_points'])} x {int(render_result['height_points'])} points (8 x 10 inches)",
            "- Renderer: canonical `workflows/pdf_branding` Playwright/Chromium carousel profile",
            "- Structural validation: readable PDF, matching non-blank unique pages, matching headings, no HTML overflow",
            "- Review gate: `ready_for_review`; manual LinkedIn document upload only",
            "- External action: none; no post, upload, schedule, message, or connection occurred",
            "",
            "## Token usage",
            "",
            "- Model invocation: none (deterministic local packaging and rendering)",
            "- Provider-total input: unavailable",
            "- Fresh input: unavailable",
            "- Cached input: unavailable",
            "- Output: unavailable",
            "- Reasoning: unavailable",
            "",
        ]
    )
    package = {
        "status": "ready_for_review",
        "workflow": "linkedin_carousel_from_md",
        "item_id": item_id,
        "manual_handoff_only": True,
        "external_transmission": False,
        "source_association": {
            "original_source_path": display_path(source_path),
            "source_sha256": source_hash,
            "carousel_draft_sha256": draft_hash,
            "linkedin_caption_sha256": caption_hash,
            "opening_hook": hook,
        },
        "resource_cta": resource_cta,
        "render": {
            "renderer": "workflows/pdf_branding/scripts/render_pdf.py --layout carousel",
            "engine": "playwright-chromium",
            "page_count": render_result["page_count"],
            "slide_count": len(slides),
            "page_size_points": [int(render_result["width_points"]), int(render_result["height_points"])],
            "overflow_problems": render_result["overflow_problems"],
            "pdf_sha256": pdf_hash,
        },
        "artifacts": {name.rsplit(".", 1)[0]: display_path(path) for name, path in artifact_paths.items()},
        "caption": caption.rstrip(),
        "review_gate": "human_review before manual LinkedIn upload",
        "external_action_confirmation": "No LinkedIn post, upload, message, connection, schedule, or external action occurred.",
        "token_usage": {
            "model_invocation": "none",
            "provider_total_input": "unavailable",
            "fresh_input": "unavailable",
            "cached_input": "unavailable",
            "output": "unavailable",
            "reasoning": "unavailable",
        },
    }

    atomic_write(artifact_paths["source.md"], source.encode("utf-8"))
    atomic_write(artifact_paths["carousel_draft.md"], draft.encode("utf-8"))
    atomic_write(artifact_paths["linkedin_caption.md"], caption.encode("utf-8"))
    atomic_write(artifact_paths["carousel.pdf"], pdf_bytes)
    atomic_write(artifact_paths["review_receipt.md"], receipt.encode("utf-8"))
    atomic_write(
        artifact_paths["post_package.json"],
        (json.dumps(package, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return package


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a canonical local LinkedIn carousel review package.")
    parser.add_argument("--source", required=True, type=Path, help="Substantive sourced Markdown file.")
    parser.add_argument("--carousel-draft", required=True, type=Path, help="Validated slide Markdown file.")
    parser.add_argument("--caption", required=True, type=Path, help="Associated LinkedIn caption Markdown file.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Named canonical workflow output directory.")
    parser.add_argument("--item-id", required=True, help="Stable local workflow item/run identifier.")
    parser.add_argument(
        "--resource-metadata",
        type=Path,
        help="Optional JSON object with resource_type/action/title/url/context; structured values take precedence.",
    )
    return parser.parse_args(argv)


def read_resource_metadata(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        raise ValueError(f"resource metadata file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"resource metadata is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("resource metadata must be a JSON object")
    return raw


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        package = build_package(
            args.source,
            args.carousel_draft,
            args.caption,
            args.output_dir,
            args.item_id,
            read_resource_metadata(args.resource_metadata),
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        f"PASS: {package['status']} package created at {args.output_dir} "
        f"({package['render']['page_count']} pages; external actions: none)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
