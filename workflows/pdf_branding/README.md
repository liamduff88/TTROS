# Time to Revenue PDF Branding Workflow

> Revisit: when the renderer, supported layouts, or local dependency contract changes. · Last touched: 2026-07-20.

Local Markdown-to-PDF workflow for polished Time to Revenue reports, lead magnets, and LinkedIn carousel pages.

## Render the sample

```bash
.venv-pdf/bin/python workflows/pdf_branding/scripts/render_pdf.py \
  --input workflows/pdf_branding/input/sample_ttr_report.md \
  --output workflows/pdf_branding/output/sample_ttr_report.pdf
```

Render the Agentic OS lead magnet:

```bash
.venv-pdf/bin/python workflows/pdf_branding/scripts/render_pdf.py \
  --input workflows/pdf_branding/input/agentic_os_not_bureaucracy_lead_magnet.md \
  --output workflows/pdf_branding/output/agentic_os_not_bureaucracy_lead_magnet.pdf
```

Manual page breaks can be added to a Markdown source with this line on its own:

```markdown
<!-- pagebreak -->
```

The renderer converts that marker to a print-safe `.page-break` element with
`page-break-before` and `break-before` rules. Use it sparingly for short lead
magnet and report layouts where a major section needs to start cleanly.

PowerShell:

```powershell
.\workflows\pdf_branding\scripts\render_pdf.ps1 `
  -InputPath ".\workflows\pdf_branding\input\sample_ttr_report.md" `
  -OutputPath ".\workflows\pdf_branding\output\sample_ttr_report.pdf"
```

## Behavior

The renderer converts Markdown to branded HTML, applies the Time to Revenue print stylesheet
and brand tokens, then attempts local PDF rendering. The visual system is sourced from the
harvested `ttr-publication-engine`: graphite/ivory/champagne color, Geist heading stack,
Inter body stack, restrained rules, and print-first A4 page geometry.

Preferred PDF renderers:

1. Python Playwright with Chromium
2. WeasyPrint

If neither renderer is available, the command writes a branded HTML fallback next to the
requested PDF path and prints `NEEDS ATTENTION` with exact local install steps. No external
API, dashboard, connector, or server is used.

## Install an optional PDF renderer

Playwright:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
```

WeasyPrint:

```bash
python3 -m pip install weasyprint
```

The HTML fallback is still useful for review and browser-based printing while the local PDF
dependency is being installed.

## Render a LinkedIn carousel

Carousel rendering is a strict profile of this same PDF subsystem. It preserves the A4 report
default while adding an 8×10-inch portrait page per slide. Separate 6–10 slides with a
`<!-- slide -->` line and start every slide with exactly one `#` or `##` heading.

```bash
.venv-pdf/bin/python workflows/pdf_branding/scripts/render_pdf.py \
  --layout carousel \
  --input workflows/linkedin_carousel_from_md/fixtures/agentic_os_not_bureaucracy/carousel_draft.md \
  --output workflows/linkedin_carousel_from_md/output/example/carousel.pdf
```

The carousel profile requires Playwright/Chromium and `pypdf`, performs in-browser overflow
checks, normalizes volatile PDF metadata, and then validates structure, dimensions, page count,
readable slide text, and page uniqueness. It fails instead of accepting the lower-fidelity
built-in report fallback. The canonical end-to-end entry point is the carousel workflow's
`scripts/build_package.py`, which also associates the source, caption, receipt, and manifest.

Install the declared local dependencies into the ignored renderer environment:

```bash
python3 -m venv .venv-pdf
.venv-pdf/bin/python -m pip install -r workflows/pdf_branding/requirements.txt
.venv-pdf/bin/python -m playwright install chromium
```
