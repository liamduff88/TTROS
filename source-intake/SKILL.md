---
name: source-intake
description: Deterministically capture .txt, .md, text/plain, and message/rfc822 files as historical TTROS Business Brain sources. Use when Liam says to import transcripts or conversations, add files to the Brain, keep files as historical context, or make notes available for later; distinguish cheap CAPTURE from requested INTERPRET or DISTILL work.
---

# Source Intake

> Revisit: when source formats, retrieval surfaces, or promotion rules change. · Last touched: 2026-08-17.

Choose exactly one mode from the user's intent.

## CAPTURE (default)

Preserve and index sources without interpreting them. Run:

```bash
python3 tools/source_intake.py "/path/to/file-or-folder"
```

Use CAPTURE for requests such as "import these transcripts," "add these conversations to the Brain," "keep these files as historical context," or "make these notes available for later." Do not send the corpus to a model, delegate an investigation, summarize it, extract durable knowledge, or rerun prior platform proofs. A successful result must report zero model calls and retrieval ready. Exact duplicates are no-ops.

## INTERPRET

First CAPTURE, then retrieve only the source or narrow source set relevant to the user's explicit question. Reason over those retrieved sources; never load the full corpus by default. Keep raw communications as evidence rather than canonical truth.

## DISTILL

Use only when Liam explicitly requests durable learnings or the existing promotion system identifies a justified candidate. Retrieve source-by-source or narrowly by query, preserve knowledge-state distinctions, and route pricing, commitments, strategy, legal/financial conclusions, authority changes, conflicts, and communications-derived durable facts through the existing review tier. Use `skills/memory_promotion/SKILL.md`; do not write canonical knowledge directly.

## Boundaries

- Accept only `.txt`, `.md`, `text/plain`, and `message/rfc822` (`.eml`).
- Keep client material in its existing isolated client workflow; routine intake is global historical TTROS context only.
- Do not add OCR, conversion, another database, index, queue, Graphify, memory system, approval layer, scheduler, or orchestrator.
- Treat unsupported or protected input as a clear failure with no mutation.

## Done when

The compact command result reports scanned/imported/duplicate counts, `0 model calls`, and `retrieval ready`; or the request fails before mutation with one actionable reason.
