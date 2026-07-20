# LinkedIn Carousel Rendering Recovery Proof
> Expires: when the canonical carousel renderer or package contract changes. · Last touched: 2026-07-20.

## Result

PASS. The canonical `linkedin_carousel_from_md` workflow produced a real,
branded, upload-ready seven-page PDF review package through the existing
`workflows/pdf_branding` subsystem. Its deterministic resource resolver
correctly classified the fixture's diagnostic questions, self-score grid, and
score ranges as an `assessment`, selected the grammatical `take` action,
directed the PDF reader to the link in the LinkedIn post, and used the visible
missing-URL review placeholder only in the caption. No LinkedIn or other
external action ran.

## Current-state trace before repair

- Canonical skill/workflow: `skills/linkedin_carousel_from_md/SKILL.md` and
  `workflows/linkedin_carousel_from_md/workflow.md` declared the six-file
  package and manual handoff gate, but named only an undefined dashboard
  "render tool."
- Existing output: `output/WP11_PHASE_D_PROOF/` was intentionally a blocked
  stub with no PDF and `blocked_render_stub` status.
- Renderer: `workflows/pdf_branding/scripts/render_pdf.py` was executable for
  A4 reports, with brand tokens, A4 CSS/template, Playwright and lower-fidelity
  report fallbacks. It had no slide parser, carousel geometry, overflow gate,
  or package entry point.
- Packaging caller: `workflows/marketing_pdf_package/workflow.md` correctly
  handed lead-magnet Markdown to `workflows/pdf_branding`; it did not execute
  carousel packages and was preserved.
- Shell/registry: `tools/aos-workflow.py` prepared empty run scaffolds from
  `workflows/workflow_registry.json`; it did not execute workflow logic.
  `linkedin_carousel_from_md` was in `workflows/runner_contracts.json` and the
  dashboard runner-contract surface, but absent from the library registry and
  catalog.
- Dashboard exposure: `dashboard/backend/main.py` discovers canonical
  `workflows/*/workflow.md`, exposes them at `/api/dashboard/workflows`, and
  derives runner contracts at `/api/dashboard/workflow-contracts`. No second
  dashboard or backend renderer existed or was added.
- Existing tests: `tests/test_pdf_branding_workflow.py` was byte-identical to
  the backup and allowed either a PDF or HTML/report fallback. It did not prove
  carousel input validation, page count, readable page text, source/caption
  association, idempotency, or no-external-action packaging.

## Backup comparison and dispositions

Current-style candidates were compared with SHA-256 and `diff -u`.

| Backup path | SHA-256 / comparison | Disposition |
| --- | --- | --- |
| `workflows/pdf_branding/scripts/render_pdf.py` | `3f76f019...b78fa0`; byte-identical to pre-repair live file | Accepted as the newest live baseline; extended in place, not copied as a second renderer. |
| `workflows/pdf_branding/scripts/render_pdf.ps1` | `1dbaf888...70a1b`; byte-identical | Preserved; thin wrapper only, no carousel behavior. |
| `workflows/pdf_branding/README.md` | `feb1b6ad...c8eb`; byte-identical | Accepted as A4 contract evidence; updated without changing A4 default. |
| `workflows/marketing_pdf_package/workflow.md` | `cad2aeb8...7ceb`; byte-identical | Accepted unchanged; its lead-magnet handoff remains valid. |
| `tests/test_pdf_branding_workflow.py` | `c96906a5...9020`; byte-identical | Accepted as A4 regression coverage, rejected as sufficient carousel proof. |
| `workflows/workflow_registry.json` | backup was older; diff showed current prospecting entries absent from backup | Rejected as a replacement; newer current entries preserved and carousel added additively. |
| `legacy_harvest/pdf_branding_workflow/PDF_BRANDING_WORKFLOW_MANIFEST.md` | `07865cd9...55a3` | Accepted as dependency, contract, candidate, and sample-output evidence only. |
| `legacy_harvest/pdf_branding_workflow/docs/` | four checkpoint/README/AGENTS docs | Accepted as design/behavior evidence only; no runtime copied. |
| `legacy_harvest/pdf_branding_workflow/scripts/ttr-guide-project/package.json` | `33f89ac6...489` | Accepted dependency evidence (`playwright`, `markdown-it`); no Node subsystem copied. |
| `legacy_harvest/pdf_branding_workflow/scripts/ttr-guide-project/src/render-pdf.js` | `48efa113...b48` | Accepted pattern: Chromium print plus in-page overflow/CTA containment checks. Adapted narrowly in Python. |
| `legacy_harvest/pdf_branding_workflow/scripts/ttr-publication-engine/package.json` | `1839443c...a50` | Accepted dependency/fallback evidence only. |
| `legacy_harvest/pdf_branding_workflow/scripts/ttr-publication-engine/src/build.js` | `d6f16d6f...692` | Rejected for direct reuse: general but A4-specific Node build, config/manuscript subsystem, website copy behavior, and lower-fidelity `pdfkit` fallback duplicated current responsibilities. |
| `legacy_harvest/pdf_branding_workflow/templates/` | 8.1 MB HTML, 108 KB HTML, 965 KB PDF specimens | Rejected for runtime copy: visual references, not executable templates. Current tokens/text wordmark were sufficient. |
| `legacy_harvest/linkedin_workflow/*.md` | status docs only | Rejected as implementation: explicitly says the LinkedIn workflow was a stub. Thumbnail assets were unrelated to document-page rendering. |
| `legacy_harvest/linkedin_migration_plan.md` | `1a72dc34...7f2c` | Accepted as architectural evidence: LinkedIn should call PDF branding rather than duplicate it. |

The backup proof outputs were real A4 PDFs (publication-engine sample 218,534
bytes; guide-project sample 221,632 bytes). They proved the Playwright method,
not a LinkedIn carousel page contract. No backup virtualenv, browser cache,
`node_modules`, output, credential, log, receipt, queue state, or unrelated
legacy file was copied.

## Root cause and behavior changed

The migration did not lose the current Python A4 renderer: it migrated intact.
The gap was created later when `linkedin_carousel_from_md` was registered as a
declarative workflow with a blocked proof stub but no executable package runner
or dashboard render implementation. Carousel-specific input parsing, 8×10 page
geometry, strict Chromium requirement, overflow checks, structural PDF checks,
and source/caption association were never connected.

The repair keeps one PDF subsystem. `render_pdf.py --layout report` preserves
the existing A4 behavior. `--layout carousel` now:

- accepts 6–10 Markdown slides separated by `<!-- slide -->`;
- requires one leading level-1/2 heading and bounded useful copy per slide;
- renders one branded 8×10-inch portrait page per slide through local
  Playwright/Chromium;
- fails on browser/layout errors instead of accepting report fallbacks;
- normalizes volatile PDF metadata for deterministic reruns;
- validates strict readability, file size/header, 576×720-point dimensions,
  page count, non-blank unique pages, and heading/page association with `pypdf`.

`scripts/build_package.py` is the canonical workflow entry point. It validates
the real source, draft, hook-associated caption and controlled CTA markers;
resolves structured resource metadata before deterministic content inference;
invokes the existing renderer; then atomically/idempotently writes the six
contracted artifacts. The manifest stores source/draft/caption/PDF hashes,
resource type/action/copy/caption-link/inference/fallback provenance, and an explicit
`external_transmission: false` review gate. Unsupported or ambiguous resource
types retain the neutral `resource` fallback and its `access` action. A
configured URL is preserved in the caption but never exposed in the PDF
carousel. The PDF also contains no URL placeholder, QR code, embedded resource
hyperlink, or default DM instruction.

## Files changed

- Behavior/contracts: `decisions/DECISIONS.md`,
  `skills/linkedin_carousel_from_md/SKILL.md`,
  `workflows/linkedin_carousel_from_md/workflow.md`,
  `workflows/pdf_branding/README.md`, `workflows/runner_contracts.json`,
  `workflows/workflow_registry.json`, `workflows/WORKFLOW_CATALOG.md`.
- Implementation: `workflows/pdf_branding/scripts/render_pdf.py`,
  `workflows/pdf_branding/styles/ttr_carousel.css`,
  `workflows/pdf_branding/templates/ttr_carousel_template.html`,
  `workflows/pdf_branding/requirements.txt`,
  `workflows/pdf_branding/requirements-visual.txt`, and
  `workflows/linkedin_carousel_from_md/scripts/build_package.py`.
- Fixture/tests: the three files under
  `workflows/linkedin_carousel_from_md/fixtures/agentic_os_not_bureaucracy/`,
  `tests/test_linkedin_carousel_workflow.py`, and the additive expected registry
  ID in `tests/test_aos_workflow_shell.py`.
- Real package/proof: `workflows/linkedin_carousel_from_md/output/LINKEDIN-CAROUSEL-RECOVERY-2026-07-20/`
  and this proof.

## Dependencies

Reused existing ignored `.venv-pdf` and its already-working Chromium install.
Installed from the new local declarations; no environment was copied:

- Playwright 1.61.0 (already present and reused)
- markdown-it-py 3.0.0
- pypdf 6.14.2
- PyMuPDF 1.28.0 (visual proof only)

Install command:

```bash
.venv-pdf/bin/python -m pip install -r workflows/pdf_branding/requirements.txt -r workflows/pdf_branding/requirements-visual.txt
```

## Real end-to-end proof

Canonical command:

```bash
.venv-pdf/bin/python workflows/linkedin_carousel_from_md/scripts/build_package.py \
  --source workflows/linkedin_carousel_from_md/fixtures/agentic_os_not_bureaucracy/source.md \
  --carousel-draft workflows/linkedin_carousel_from_md/fixtures/agentic_os_not_bureaucracy/carousel_draft.md \
  --caption workflows/linkedin_carousel_from_md/fixtures/agentic_os_not_bureaucracy/linkedin_caption.md \
  --output-dir workflows/linkedin_carousel_from_md/output/LINKEDIN-CAROUSEL-RECOVERY-2026-07-20 \
  --item-id LINKEDIN-CAROUSEL-RECOVERY-2026-07-20
```

Result: PASS, `ready_for_review`, six contracted artifacts, seven PDF pages,
42,378-byte PDF, seven unique readable page texts, 576×720 points on every
page, SHA-256 `f3db9055e03f39934d2ad9b48112912e31a93d777ddfe50b6a420326a583a020`.
The stored CTA contract is `assessment` / `take`, inferred from
`source.content:questions-and-scoring`, with fallback `false` and caption-link
status `review_placeholder`.

Final PDF:
`workflows/linkedin_carousel_from_md/output/LINKEDIN-CAROUSEL-RECOVERY-2026-07-20/carousel.pdf`

## Visual inspection

Every actual PDF page was rasterized at 2× with PyMuPDF to the package's
`visual-proof/page-01.png` through `page-07.png` and individually inspected.

- Typography: large, readable, consistent graphite/ivory/champagne system.
- Geometry/margins: consistent 4:5 portrait pages with safe interior margins.
- Wrapping: sensible on hook, body, numbered list, and CTA pages.
- Integrity: no clipping, overlap, blanks, duplication, or missing header/footer.
- Content: opening hook is usable; slide sequence is coherent; final CTA reads
  “Take the full assessment using the link in the LinkedIn post below.” and is
  contained and legible. No raw URL appears on the page.
- Upload suitability: one PDF document, seven portrait pages, no fallback or
  placeholder content, ready for manual LinkedIn document upload after review.

## Validation

```text
python3 -m py_compile workflows/pdf_branding/scripts/render_pdf.py workflows/linkedin_carousel_from_md/scripts/build_package.py tests/test_linkedin_carousel_workflow.py
PASS

.venv-pdf/bin/python -m unittest tests.test_pdf_branding_workflow tests.test_linkedin_carousel_workflow -v
PASS — 25 tests

python3 -m unittest tests.test_aos_workflow_shell tests.test_aos_paths tests.test_aos_queue dashboard.backend.test_composio_hermes -v
PASS — 278 tests

Package-integrity / deterministic rerun probe
PASS — all six artifact hashes reproduced exactly; JSON paths/hashes, CTA
metadata/surfaces, seven-page count, 576×720 geometry, caption placeholder,
no raw final-page URL, active stale-CTA scan, and neutral fallback validated

git diff --check
PASS
```

The protected dashboard route files were not directly opened or modified. The
existing queue/dashboard regression suites exercised their contracts without
emitting protected contents. No dashboard server was required.

## External and protected boundaries

- No LinkedIn post, upload, message, connection, schedule, browser login, API
  call, connector call, publish, deploy, Git stage/commit/push, or other
  external action occurred.
- No protected task IDs were mutated. No North Shore or Telegram bridge file,
  protected route file, environment/secret/credential/token/authentication
  file, or Hermes global/default profile was modified.
- The pre-existing recovery worktree and historical approved source stayed
  intact outside the scoped carousel recovery paths; no unrelated file was
  altered.

## Token usage

- Provider-total input: unavailable
- Fresh input: unavailable
- Cached input: unavailable
- Output: unavailable
- Reasoning: unavailable
- Closing context percentage: unavailable
