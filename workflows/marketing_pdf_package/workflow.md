# Marketing PDF Package Workflow

Purpose: turn an approved Marketing draft into a polished lead magnet package without changing runtime systems or publishing anything automatically.

## Inputs

Place source material in `input/`:

- Approved Marketing draft with approval note or review receipt.
- Intended audience and offer context.
- Desired lead magnet title and subtitle, if already chosen.
- CTA destination or CTA copy approved by Liam.
- Any notes for formatting, proof points, disclaimers, or examples.

If the draft is not clearly approved, stop and request human review before packaging.

## Draft-First Package Steps

1. Confirm the approved draft is the source of truth.
2. Create or refine the lead magnet title and subtitle.
3. Define one clear CTA, keeping it soft and useful.
4. Convert the approved draft into PDF source markdown.
5. Save the markdown source in `output/`.
6. Hand the markdown source to `workflows/pdf_branding` for PDF rendering.
7. Review the returned PDF or HTML fallback for title, CTA, formatting, page breaks, and obvious errors.
8. Complete the final asset checklist before publishing.

## PDF Branding Handoff

Use `workflows/pdf_branding` only as the renderer. Do not change its scripts, brand tokens, templates, or runtime behavior from this workflow.

Handoff package:

- Source markdown path.
- Desired output filename.
- Title and subtitle.
- CTA copy.
- Any page break notes.
- Receipt path for the render result.

## Final Asset Checklist

- The source draft was approved before packaging.
- Title and subtitle match the package brief.
- CTA is present, clear, and not overpromised.
- PDF source markdown is stored in `output/`.
- PDF branding render result is reviewed.
- Final PDF or fallback HTML is present.
- Receipt is written in `receipts/`.
- Liam completes human review before publishing or distributing.

## Receipt Format

Create a receipt in `receipts/YYYY-MM-DD_package_name_receipt.md`:

```markdown
# Marketing PDF Package Receipt

- Source draft:
- Approval evidence:
- Package title:
- Package subtitle:
- CTA:
- PDF source markdown:
- PDF branding handoff:
- Final asset path:
- Human review status:
- Publishing status: not published by workflow
- Blockers:
- Decisions needed:
```

## Rules

- Draft-first: produce package files and review notes only.
- Human review is required before publishing.
- Do not publish, schedule, email, upload, or distribute the asset.
- Do not modify dashboard, Telegram, Hermes, queue, connectors, backend routes, or pilot-specific files.
