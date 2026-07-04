# Time to Revenue PDF Branding Workflow

Local Markdown-to-PDF workflow for polished Time to Revenue reports and lead magnets.

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
