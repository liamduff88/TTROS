---
name: case_note
description: Capture a client engagement outcome as a reusable, anonymized case note — evidence for authority content and future proposals.
when-to-use: A build stage completes, a client result lands, or /weekly-review flags an outcome worth keeping. Owner: aos-delivery. Trust: watch.
---
# /case-note
> Revisit: if a note's claims are contradicted by later results. · Last touched: 2026-07-07

## Purpose
Turn real delivery outcomes into durable, sourced evidence — the raw material for content, proposals, and the ICP picture — without leaking client data.

## Inputs
- The engagement's receipts, acceptance-test evidence, and client entity page.
- client_data_boundaries.md rules (binding).

## Steps
1. **Facts only** — before/after state, what was built, measured result if one exists. Every claim needs a source (receipt, test log, client statement with date). No source → not in the note.
2. **Anonymize** — strip client name and identifying details unless the client is already named in context files with permission. Industry + size class is enough.
3. **Structure** — problem → build → result → what made it work → reusable lesson (one line, candidate for skill/memory promotion).
4. **File** — save alongside the client's records in their isolation folder, plus the anonymized version where marketing/revenue lanes can read it.
5. **Flag** — if the lesson recurs (3rd time), flag to /maintain-os as a /learn candidate per SKILL_GRADUATION_POLICY.md.

## Never
- Include unverified numbers or projected results as achieved results.
- Blend details from multiple clients into one "composite" note.
- Expose client-identifying data in the shared/anonymized copy.

## Done when
Two versions exist (full in isolation folder, anonymized shared), every claim sourced, one reusable lesson stated. Receipt written.
