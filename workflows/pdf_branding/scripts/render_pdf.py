#!/usr/bin/env python3
"""Render a Time to Revenue branded report from Markdown."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any


WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = WORKFLOW_ROOT / "templates" / "ttr_report_template.html"
DEFAULT_CSS = WORKFLOW_ROOT / "styles" / "ttr_print.css"
DEFAULT_TOKENS = WORKFLOW_ROOT / "brand" / "time-to-revenue.tokens.json"
PAGE_BREAK_RE = re.compile(r"^\s*<!--\s*pagebreak\s*-->\s*$", re.IGNORECASE | re.MULTILINE)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_tokens(path: Path = DEFAULT_TOKENS) -> dict[str, Any]:
    return json.loads(read_text(path))


def slug_css_name(name: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"-\1", name).lower()


def token_css(tokens: dict[str, Any]) -> str:
    lines = [":root {"]
    for name, value in tokens.get("colors", {}).items():
        lines.append(f"  --ttr-{slug_css_name(name)}: {value};")
    fonts = tokens.get("fonts", {})
    if fonts.get("heading"):
        lines.append(f"  --ttr-font-heading: {fonts['heading']};")
    if fonts.get("body"):
        lines.append(f"  --ttr-font-body: {fonts['body']};")
    lines.append("}")
    return "\n".join(lines)


def extract_title(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1)
    return fallback


def wrap_content_sections(rendered_html: str) -> str:
    """Group h2-led blocks so print CSS can keep short sections together."""
    parts = re.split(r"(?=<h2>)", rendered_html)
    wrapped: list[str] = []
    for part in parts:
        if part.startswith("<h2>"):
            wrapped.append(f'<section class="content-section">\n{part.rstrip()}\n</section>')
        else:
            wrapped.append(part.rstrip())
    return "\n".join(part for part in wrapped if part)


def markdown_to_html(markdown_text: str) -> str:
    chunks = PAGE_BREAK_RE.split(markdown_text)

    def render_chunk(chunk: str) -> str:
        if not chunk.strip():
            return ""
        try:
            from markdown_it import MarkdownIt

            parser = MarkdownIt("commonmark", {"html": False})
            try:
                parser.enable("table")
            except ValueError:
                pass
            return parser.render(chunk)
        except Exception:
            return simple_markdown_to_html(chunk)

    rendered_chunks = [wrap_content_sections(render_chunk(chunk)) for chunk in chunks]
    return '\n<div class="page-break" aria-hidden="true"></div>\n'.join(
        chunk for chunk in rendered_chunks if chunk.strip()
    )


def _legacy_markdown_to_html(markdown_text: str) -> str:
    try:
        from markdown_it import MarkdownIt

        parser = MarkdownIt("commonmark", {"html": False})
        try:
            parser.enable("table")
        except ValueError:
            pass
        return parser.render(markdown_text)
    except Exception:
        return simple_markdown_to_html(markdown_text)


def simple_markdown_to_html(markdown_text: str) -> str:
    """Small fallback for the sample report if markdown-it is unavailable."""
    blocks: list[str] = []
    paragraph: list[str] = []
    bullets: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f"<p>{html.escape(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            items = "".join(f"<li>{html.escape(item)}</li>" for item in bullets)
            blocks.append(f"<ul>{items}</ul>")
            bullets.clear()

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if PAGE_BREAK_RE.match(raw_line):
            flush_paragraph()
            flush_bullets()
            blocks.append('<div class="page-break" aria-hidden="true"></div>')
            continue
        if not line:
            flush_paragraph()
            flush_bullets()
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_bullets()
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{html.escape(heading.group(2))}</h{level}>")
        elif bullet:
            flush_paragraph()
            bullets.append(bullet.group(1))
        else:
            flush_bullets()
            paragraph.append(line)

    flush_paragraph()
    flush_bullets()
    return "\n".join(blocks)


def build_html(input_path: Path, template_path: Path, css_path: Path, tokens_path: Path) -> str:
    markdown_text = read_text(input_path)
    title = extract_title(markdown_text, input_path.stem.replace("_", " ").title())
    template = read_text(template_path)
    return (
        template.replace("{{ title }}", html.escape(title))
        .replace("{{ token_css }}", token_css(load_tokens(tokens_path)))
        .replace("{{ print_css }}", read_text(css_path))
        .replace("{{ content }}", markdown_to_html(markdown_text))
    )


def write_pdf_with_playwright(html_path: Path, output_path: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                args=["--disable-setuid-sandbox", "--no-zygote", "--single-process"]
            )
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            page.emulate_media(media="print")
            page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            browser.close()
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as exc:
        print(f"INFO: Playwright PDF render unavailable: {exc}", file=sys.stderr)
        return False


def write_pdf_with_weasyprint(html_path: Path, output_path: Path) -> bool:
    try:
        from weasyprint import HTML
    except Exception:
        return False

    try:
        HTML(filename=str(html_path)).write_pdf(str(output_path))
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as exc:
        print(f"INFO: WeasyPrint PDF render unavailable: {exc}", file=sys.stderr)
        return False


def pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_color(hex_color: str) -> str:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        return "0 0 0"
    channels = [int(value[index : index + 2], 16) / 255 for index in range(0, 6, 2)]
    return " ".join(f"{channel:.3f}" for channel in channels)


def markdown_blocks(markdown_text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(("p", " ".join(paragraph)))
            paragraph.clear()

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if PAGE_BREAK_RE.match(raw_line):
            flush_paragraph()
            blocks.append(("pagebreak", ""))
            continue
        if not line:
            flush_paragraph()
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        if heading:
            flush_paragraph()
            blocks.append((f"h{len(heading.group(1))}", heading.group(2)))
        elif bullet:
            flush_paragraph()
            blocks.append(("li", bullet.group(1)))
        else:
            paragraph.append(line)

    flush_paragraph()
    return blocks


def wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def write_pdf_objects(objects: list[bytes], output_path: Path) -> None:
    offsets: list[int] = []
    content = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")

    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_offset}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    output_path.write_bytes(bytes(content))


def write_pdf_with_builtin(markdown_text: str, output_path: Path) -> bool:
    tokens = load_tokens(DEFAULT_TOKENS)
    colors = tokens.get("colors", {})
    deep_ink = pdf_color(colors.get("deepInk", "#0D1418"))
    champagne = pdf_color(colors.get("champagne", "#B89B63"))
    paper = pdf_color(colors.get("ivory", "#F7F3EA"))
    muted = pdf_color(colors.get("softGraphite", "#4E5659"))
    cover_text = pdf_color("#F4EFE3")
    title = extract_title(markdown_text, output_path.stem.replace("_", " ").title())
    subtitle = ""
    for kind, text in markdown_blocks(markdown_text):
        if kind == "h2":
            subtitle = text
            break

    width = 595
    height = 842
    left = 58
    right = 537
    y = 760
    page_commands: list[list[str]] = []

    def text_command(text: str, x: int, y_pos: int, size: int, font: str, color: str) -> str:
        return f"BT /{font} {size} Tf {color} rg {x} {y_pos} Td ({pdf_escape(text)}) Tj ET"

    cover_commands: list[str] = [
        f"{deep_ink} rg 0 0 {width} {height} re f",
        text_command("Time to Revenue", left, 760, 10, "F1", cover_text),
        text_command("Revenue Operations Guide", left, 540, 11, "F1", champagne),
    ]
    cover_y = 500
    for line in wrap_text(title, 25):
        cover_commands.append(text_command(line, left, cover_y, 32, "F1", cover_text))
        cover_y -= 38
    cover_y -= 14
    for line in wrap_text(subtitle, 58):
        cover_commands.append(text_command(line, left, cover_y, 12, "F2", cover_text))
        cover_y -= 18
    cover_commands.append(text_command("Client-ready publication", left, 58, 8, "F2", muted))
    page_commands.append(cover_commands)
    page_commands.append([])

    def current_page() -> list[str]:
        return page_commands[-1]

    def new_page() -> None:
        page_commands.append([])

    def add_text(text: str, x: int, y_pos: int, size: int, font: str, color: str) -> None:
        current_page().append(text_command(text, x, y_pos, size, font, color))

    def page_background(commands: list[str], page_index: int) -> list[str]:
        if page_index == 0:
            return commands
        return [
            f"{paper} rg 0 0 {width} {height} re f",
            f"{champagne} rg {left} {height - 48} {right - left} 1 re f",
            *commands,
            f"BT /F2 8 Tf {muted} rg {left} 32 Td (Time to Revenue) Tj ET",
        ]

    for kind, text in markdown_blocks(markdown_text):
        if kind == "pagebreak":
            if current_page():
                new_page()
            y = 760
            continue
        if kind == "h1":
            max_chars = 36
            size = 24
            line_height = 30
            gap = 18
            font = "F1"
            color = deep_ink
        elif kind == "h2":
            max_chars = 58
            size = 15
            line_height = 20
            gap = 12
            font = "F1"
            color = deep_ink
        elif kind == "h3":
            max_chars = 62
            size = 13
            line_height = 18
            gap = 8
            font = "F1"
            color = deep_ink
        else:
            max_chars = 82 if kind != "li" else 76
            size = 10
            line_height = 15
            gap = 8
            font = "F2"
            color = deep_ink

        lines = wrap_text(text, max_chars)
        needed = len(lines) * line_height + gap
        if y - needed < 42:
            new_page()
            y = 760
        for index, line in enumerate(lines):
            prefix = "- " if kind == "li" and index == 0 else "  " if kind == "li" else ""
            add_text(f"{prefix}{line}", left, y, size, font, color)
            y -= line_height
        y -= gap

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_refs: list[int] = []
    for page_index, commands in enumerate(page_commands):
        if page_index > 0 and not commands:
            continue
        stream = "\n".join(page_background(commands, page_index)).encode("latin-1", errors="replace")
        content_obj = len(objects) + 1
        page_obj = len(objects) + 2
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream")
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_obj} 0 R >>"
            ).encode("ascii")
        )
        page_refs.append(page_obj)

    kids = " ".join(f"{ref} 0 R" for ref in page_refs)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_refs)} >>".encode("ascii")
    write_pdf_objects(objects, output_path)
    return output_path.exists() and output_path.stat().st_size > 0


def render(input_path: Path, output_path: Path) -> int:
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_html = output_path.with_suffix(".html")
    fallback_html.write_text(
        build_html(input_path, DEFAULT_TEMPLATE, DEFAULT_CSS, DEFAULT_TOKENS),
        encoding="utf-8",
    )

    if write_pdf_with_playwright(fallback_html, output_path):
        print(f"PASS: PDF created at {output_path}")
        return 0

    if write_pdf_with_weasyprint(fallback_html, output_path):
        print(f"PASS: PDF created at {output_path}")
        return 0

    if write_pdf_with_builtin(read_text(input_path), output_path):
        print(f"PASS: PDF created at {output_path}")
        return 0

    print(f"NEEDS ATTENTION: PDF renderer unavailable; branded HTML fallback created at {fallback_html}")
    print("Install one local renderer:")
    print("  python3 -m pip install playwright && python3 -m playwright install chromium")
    print("  or")
    print("  python3 -m pip install weasyprint")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a branded Time to Revenue PDF from Markdown.")
    parser.add_argument("--input", required=True, type=Path, help="Markdown input path.")
    parser.add_argument("--output", required=True, type=Path, help="PDF output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    return render(args.input, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
