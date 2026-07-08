# Agentic OS Lead Magnet Brand Fix Receipt

Date: 2026-07-03

## Scope

Updated the clean PDF branding workflow for the Agentic OS lead magnet. This was a design
migration correction only: the existing Markdown input and renderer shape were preserved.

## Brand Source Used

- Legacy harvest source retired; no current equivalent brand asset path was found in the live Business Brain pointer
  (`C:\Users\Admin\Documents\A-Time to revenue\TTROS Business Brain`). Brand assets must be re-sourced from the live Business Brain before reuse.
- `C:\Users\Admin\Code\ttr-publication-engine\brand\time-to-revenue.tokens.json`
- `C:\Users\Admin\Code\ttr-publication-engine\styles\base.css`

## Changes

- Migrated the live template toward the TTR publication-engine cover/header/footer structure.
- Reworked print CSS around the TTR graphite, ivory, warm stone, and champagne system.
- Preserved Geist heading and Inter body font stacks from the TTR tokens.
- Removed green accent treatment from the editable template/CSS/token brand layer.
- Added tests that lock TTR color/font expectations and reject the green strip in brand files.

## Validation

- `python3 -m compileall -q workflows tests` passed.
- `python3 -m unittest tests.test_pdf_branding_workflow -v` passed.
- Expected HTML artifact exists and is non-empty.
- Expected PDF artifact exists, is non-empty, and has a valid `%PDF-` header.
- Expected PDF artifact could not be regenerated because the existing file is locked against
  overwrite/unlink from this WSL shell.
- Playwright Chromium launch is blocked in this shell by a local sandbox shutdown error.
