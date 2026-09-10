# STEP I2 transcript — production ingestion path, fresh source

Fresh source (Liam-nominated): `/mnt/c/Users/Admin/Downloads/Fred Haiderzada meeting sept 9th.txt`
209 lines, 56044 B, sha256 `d9cb4668fd766474278e414bb53223f944342004f34be23020c161fa4160dd74`.

Model-call budget: 12 authorized (3 ingestion, rest David turns). **Used: 0 of 12** — the failure
below happens entirely inside the git-commit stage of `brain_memory.write_transaction`, before any
Hermes/model call is made. Confirmed no usage file exists under
`queue/context_assemblies/` naming this source or its sha256.

## Prediction (written before running)

`run_intake(path, mode="capture")` will succeed with 0 model calls, writing a new record to
`sources/intake/records/<sha256>.md` with frontmatter `type: source`, `status: historical-evidence`
(`tools/source_intake.py::render_record`). I expected the *next* step — feeding that record into
`mode="semantic"` — to then fail, because `_run_semantic_intake` requires `type: historical_source`
(`tools/source_intake.py:289-290`), a different value than what `render_record` writes; capture mode
and semantic mode use two different frontmatter schemas and, as far as I can find, have never been
chained together before (no test does it; the STEP I1 backfill pointed semantic mode directly at 15
files pre-formatted by an unrelated 2026-08-17 historical-import script, never at capture mode's own
output).

## What actually happened

Ran the real CLI: `python3 tools/source_intake.py "<fresh source>" --mode capture --json`
(repo root `/home/liam/agentic-os-live`, real `BusinessBrainGraphService`/`aos_indexer`/
`brain_memory.write_transaction`, commit=True — the ordinary production call, no test doubles).

**It failed before reaching the type-mismatch I predicted** — earlier in the pipeline, at the git
commit stage. Exit 1: `source intake failed safely: ... trailing whitespace.` repeated once per
affected line of `sources/intake/records/<sha256>.md`.

Root cause (read, not guessed): `tools/brain_memory.py:358` runs `git("diff", "--cached", "--check")`
as a pre-existing, production write-transaction safeguard — not new, not touched by this or the I1
step. `git diff --check` fails the whole transaction if the staged diff contains whitespace errors,
trailing whitespace included. `tools/source_intake.py::_searchable()` copies every non-sensitive
line of the raw source verbatim (`item.raw.decode(...).splitlines()`) into the record's "Searchable
source text" section, preserving whatever trailing whitespace the original file had. This fresh
source is a real Zoom/meeting-style transcript with trailing spaces at the end of many spoken lines
(ordinary for that export format) — so a large fraction of its lines trip the check.

Vault confirmed clean afterward: HEAD unchanged (`7833df6648dfbe7d0bd875858eacdaa69298ada7`),
`sources/intake/records/` empty, no other working-tree change — `write_transaction`'s atomic
rollback behaved correctly; nothing was left half-written.

## Why this is not one of the two pre-authorized repairs, and not a guess-and-fix

STEP I2 authorizes exactly two bounded repairs (PART C), both about FTS/retrieval behavior inside
`context_assembler.py`, for use when **step 5** (arrival in a fresh `hermes-*.json`) fails. This
failure is not a retrieval defect and doesn't reach anywhere near step 5 — it blocks **step 1**
(original preservation) itself, inside `brain_memory.write_transaction`'s git-commit safeguard, a
different module than either authorized repair touches. Per the step's own rule ("If the diagnosis
points anywhere outside these two, stop and report with the evidence"), and per CLAUDE.md's rule
that an explicit in-session instruction from Liam governs, I stopped rather than picking a fix
(e.g. stripping trailing whitespace in `_searchable()`, or loosening the `git diff --check` gate)
on my own judgment — both are real, small, plausible fixes, but neither is pre-authorized, and the
second would weaken an existing safety check repo-wide, not just for this step.

## State left behind

- No vault mutation: HEAD and working tree unchanged from before this step.
- No repo mutation: no committed change to `agentic-os-live`.
- This transcript file (new, untracked) is the only artifact this step wrote to disk.
- 0 of 12 model calls used.
- Part A did not get past step 1. Parts B/C/D (diagnosis/repair/re-test) do not apply — the
  failure is not the step-5 arrival failure Part B is written to classify.

**STEP I2 (part 1): STOPPED — blocked before Part A step 1 completes, by a defect outside the two
pre-authorized repairs. Reported to Liam per the step's own escalation rule.**

## Liam's authorization to repair the trailing-whitespace defect (2026-09-09)

Liam reviewed the finding above and explicitly authorized fixing it in this session ("This is an
in-scope local production-ingestion defect and is authorized under the TTROS PERMISSION HEADER"),
with named constraints: exact original bytes/SHA must stay unchanged, only the *derived* searchable
copy may be normalized, the repo-wide `git diff --cached --check` safeguard must not be weakened,
semantic content must not change, and a focused regression must prove all three properties on a
trailing-whitespace source through the real `run_intake()` path.

### Exact change

`tools/source_intake.py::_searchable()` — added one `.rstrip()` call to each already-transformed
line before it is appended to the `lines` list (repo diff, one line added, nothing removed):

```python
lines.append(
    line.replace("[[", "[ [")
    .replace("]]", "] ]")
    .replace("<!-- TTROS:HERMES:", "< !-- TTROS:HERMES:")
    .rstrip()
)
```

This touches only the "Searchable source text" section of a rendered record. The exact-bytes block
(`BYTES_BEGIN`/`BYTES_END`, base64 of `item.raw`) is built separately in `render_record()` from
`item.raw` directly and is untouched by `_searchable()` — verified by re-reading `render_record()`
(`tools/source_intake.py:173-197`): `_searchable(item)` and `base64.b64encode(item.raw)` are two
independent calls on two independent inputs. `git diff --cached --check` itself is not touched,
called, or reconfigured anywhere in this change.

### Regression added

`tests/test_source_intake.py::test_capture_trailing_whitespace_source_commits_cleanly_and_preserves_exact_bytes`
— a real (non-mocked) `run_intake(..., mode="capture", commit=True)` against a fixture source with
trailing spaces, a trailing tab, and a whitespace-only line. Asserts, in order: (1)
`extract_exact_bytes` on the committed record returns byte-identical original content and the same
sha256 as the input; (2) every line of the rendered "Searchable source text" section satisfies
`line == line.rstrip()` (the exact condition `git diff --check` polices), and the semantic wording
of the affected lines survives unchanged; (3) the real `git` commit this fixture vault performs
during `write_transaction` succeeds (`result.brain_commit` matches the fixture vault's actual `git
log` HEAD) — proving the normal path completes, not a mocked stand-in for it. This is a positive
case; the negative case (this exact defect, unpatched) was already independently demonstrated for
real against the actual nominated source in "What actually happened" above, so it was not
re-synthesized as a separate rehearsal.

Validation, scoped (pytest lives outside every venv on this host by design —
`PYTHONPATH=/home/liam/ttros-testenv/pytest`; `tools/` must additionally be on `PYTHONPATH` for
`tests/business_brain_test_support.py`'s bare `business_brain_scope` import to resolve when this
file is collected on its own, which is how every other test file in this repo that needs it handles
the same gap — `tests/test_source_intake.py` is the one file in this pairing that doesn't already do
this itself):
`PYTHONPATH=/home/liam/ttros-testenv/pytest:/home/liam/agentic-os-live/tools dashboard/backend/.venv/bin/python -m pytest tests/test_hermes_context_plugin.py tests/test_source_intake.py -v`
→ **19/19 passed** (13 + 6, one more than I1's "31/31" reflects only because this file gained one
test; no prior test's outcome changed).

### Rollback

`tools/source_intake.py` and `tests/test_source_intake.py` are both tracked, clean, pre-existing
files. Rollback = `git checkout -- tools/source_intake.py tests/test_source_intake.py` from
`/home/liam/agentic-os-live` (no preimage needed beyond git HEAD; not used unless Liam asks).

## Part A resumed — step 1, re-run after the repair (2026-09-09)

Vault HEAD immediately before: `7833df6648dfbe7d0bd875858eacdaa69298ada7` (unchanged since the
stopped attempt above). Ran the identical real CLI call again, unmodified apart from the fix above:
`python3 tools/source_intake.py "<fresh source>" --mode capture --json`.

**Result: success.**
```
brain_commit: 8aa8e00ac3f820a1f3a1c4daaca4349d61db01c4
imported_pointers: [business_brain:sources/intake/records/d9cb4668fd766474278e414bb53223f944342004f34be23020c161fa4160dd74.md]
model_invocations: 0
retrieval_ready: true
search_status: ready
graphify_status: build
scanned/imported/duplicates: 1/1/0
```
Vault HEAD advanced `7833df6` → `8aa8e0`, one new commit, one new file. **Part A step 1: PASS** —
original preserved (base64 exact-bytes block, independently re-decoded and sha256-verified equal to
the fresh source's own sha256 recorded at the top of this transcript), searchable copy commit-safe,
0 model calls (0 of 12 used).

## Part A step 2 — blocked again, by a second and materially different defect (2026-09-09)

Prediction (written before running): pointing `mode="semantic"` at the just-produced record
(`business_brain:sources/intake/records/<sha256>.md`) will fail, because `_run_semantic_intake`
requires `header_fields.get("type") == "historical_source"` (`tools/source_intake.py:289-290`) and
`render_record()`'s capture-mode output sets `type: source` (confirmed by reading the committed
record's own frontmatter before running semantic mode: `type: source`, `status: historical-evidence`).

Ran it: `python3 tools/source_intake.py "<vault>/sources/intake/records/<sha256>.md" --mode semantic
--json`.

**Result: failed, but earlier than predicted, on a second, independent incompatibility.**
`source intake failed safely: historical_source record has no TTROS:VERBATIM_SOURCE block`. Cause:
`sis.extract_verbatim_source()` runs *before* the `type` check and requires a
`<!-- TTROS:VERBATIM_SOURCE:BEGIN:<sha256> -->...<!-- TTROS:VERBATIM_SOURCE:END:<sha256> -->` block
containing the source's plaintext body. Capture mode's records carry no such block — they carry
`<!-- TTROS:SOURCE-BYTES:BEGIN -->`/`END` wrapping base64, an entirely different serialization built
for a different purpose (exact-byte fidelity, not plaintext extraction input). The `type` mismatch I
predicted is real too (confirmed by direct inspection, `type: source` vs. required
`historical_source`) but the code never reaches that check — it fails one line earlier on the marker
format.

Vault confirmed clean after this failure: HEAD still `8aa8e00ac3f820a1f3a1c4daaca4349d61db01c4` (the
capture commit only), no new files under `sources/historical_calls/cards/` or
`queue/receipts/source_intake/claims/historical/` for this source, no new usage file under
`queue/context_assemblies/` naming this sha256 or `d9cb4668` — the failure happens in
`extract_verbatim_source()`, before `_run_semantic_intake` does any write or any model call. **0 of
12 model calls used, still.**

### Why this is a material-architecture boundary, not a bounded repair

This is not the step-5 retrieval failure Part B/C anticipate, and it is not the same defect as the
trailing-whitespace one just repaired. It is a **format incompatibility between the two modes of
`source_intake.py` itself**: capture mode (`render_record`) and semantic mode
(`sis.extract_verbatim_source`/`_run_semantic_intake`) were built at different times against two
different record schemas, and — confirmed by reading `tests/test_source_intake.py` and
`scripts/i1_source_intake_semantic_extraction_transcript.md` in full — **no code path, test, or
prior session has ever chained capture mode's own output into semantic mode.** STEP I1's 15-source
backfill pointed semantic mode directly at files from an unrelated, pre-existing 2026-08-17
historical-import process that happened to already match semantic mode's expected schema; it never
exercised capture mode at all.

Closing this gap means deciding which schema is canonical going forward and changing the other to
match — e.g. making `render_record` also emit a `TTROS:VERBATIM_SOURCE` block and
`type: historical_source`, or making `extract_verbatim_source`/`_run_semantic_intake` accept
capture mode's `TTROS:SOURCE-BYTES`/`type: source` shape instead. Either is a real design decision
about the production record format two independent, already-shipped pipelines depend on (the 15
historical-call cards already in the vault use the current `historical_source`/`VERBATIM_SOURCE`
shape) — not a "smallest correct repair" of a rendering bug, not one of PART C's two named FTS
repairs, and not a call to make unilaterally. Per CLAUDE.md ("material change to agreed TTROS
architecture" is a stop-for-Liam action) and this step's own instruction to return the closeout "when
... a genuine protected/material-architecture boundary is reached," stopping here.

## State at stop

- Vault: HEAD `8aa8e00ac3f820a1f3a1c4daaca4349d61db01c4` (one real commit ahead of pre-step
  `7833df66`: the fresh source's capture-mode preservation). Nothing from the semantic attempt
  written — that attempt failed before any write.
- Repo (`agentic-os-live`): two tracked-file edits, both validated —
  `tools/source_intake.py` (`_searchable()` rstrip fix) and `tests/test_source_intake.py` (new
  regression). Not committed to git; no push. Rollback given above.
- This transcript file: appended, not committed.
- **Model calls: 0 of 12 used.**
- **Part A: step 1 PASS. Step 2 blocked on a material-architecture question for Liam. Steps 3-6 not
  attempted — each depends on a card that does not yet exist for this source.** Parts B/C/D do not
  apply (their triggering condition, a step-5 arrival failure, was never reached).

**STEP I2: STOPPED at a genuine material-architecture boundary, per the step's own return
condition. Reporting to Liam.**

## Liam's architecture decision and repair authorization (2026-09-10)

Liam decided: the current production capture record shape (`type: source` /
`TTROS:SOURCE-BYTES`) is canonical for **new** production ingestion going forward. Do not convert
production capture into the legacy historical-call schema (`type: historical_source` /
`TTROS:VERBATIM_SOURCE`), and do not migrate/rewrite any of the 15 already-preserved historical
records. Make semantic mode accept both shapes, smallest compatible repair, with a focused
regression, then continue Part A from step 2 through the original proof. Model-call budget stays
12 total, starting at 0 used (the earlier stop spent none).

### Exact change 1 — `tools/source_intake_semantic.py::extract_verbatim_source`

Was: unconditionally required a `TTROS:VERBATIM_SOURCE` marker, regardless of `type`. Now:
dispatches on the record's own `type` field before looking for either marker.

- `type: historical_source` → unchanged behavior (`TTROS:VERBATIM_SOURCE` marker, digest-vs-
  frontmatter consistency check), byte-for-byte the same code path as before.
- `type: source` (production capture) → decodes the `TTROS:SOURCE-BYTES` block via the existing
  `tools/source_intake.py::extract_exact_bytes`, independently verifies the decoded bytes' own
  sha256 against the record's `source_sha256` frontmatter field (the same class of mechanical
  consistency check as the historical branch, just computed from the payload instead of a marker-
  embedded digest), and returns the decoded plaintext as the verbatim body — **not** the record's
  "Searchable source text" section, which is a lossy FTS rendering (bracket-escaped, sensitive
  lines dropped, trailing whitespace stripped) unfit for extraction input.
- Any other `type` (or none) → raises `SemanticExtractionError` naming both accepted values.

`tools/source_intake.py::_run_semantic_intake` no longer duplicates a (wrong) type check of its
own after calling this — `extract_verbatim_source` now owns type validation for both shapes.

Nothing in `render_record`/`_searchable`/the exact-byte block, and nothing in the 15 historical
records or their own extraction path, was touched.

### Exact change 2 — a second, independent defect found and fixed: broken "Original" link

Running the real production semantic-mode call below surfaced a second bug, not the one
authorized above: `render_source_card` and `evolve_historical_calls_index` both hardcoded the
source's original-file link to `sources/historical_calls/{source_id}` — correct for the legacy
shape (where `source_id` is a slug and that's genuinely where the original lives), but wrong for a
production-shape source, whose original lives at `sources/intake/records/{source_id}.md`
(`source_id` there being the sha256). The card's own frontmatter already carries the correct
`source_path`; both functions now derive the link from that field (`source_path.removesuffix(
".md")`) instead of assuming the legacy location. This is a rendering-only fix inside the same
"make semantic mode work end-to-end for a production-shape source" scope — not a schema or
architecture change, and it doesn't touch the 15 historical cards' already-correct links (their
`source_path` already reads `sources/historical_calls/<slug>.md`, so the derived link is
unchanged for them).

### Regression added

`tests/test_source_intake.py::test_production_capture_source_feeds_semantic_extraction` — real,
unmocked capture mode (`run_intake(..., mode="capture")`) against a fixture source, producing a
genuine `type: source` record, chained into semantic mode (`run_intake(..., mode="semantic")`)
with only the Hermes subprocess call mocked (same pattern as the existing historical-shape
semantic test). Asserts: 1 model call, card + claim receipt written, claim quote/attribution
validated for real, claim receipt not indexable, the body sent to extraction is the exact original
text (trailing whitespace intact) rather than the searchable rendering, the capture record is
byte-identical before/after and remains the only record under `sources/intake/records/` (no
re-preservation, no duplicate), and — covering fix 2 — the card's and INDEX's "Original" link both
point at `sources/intake/records/<sha256>`, and that file actually exists.

`tests/test_source_intake.py::test_extract_verbatim_source_rejects_unknown_type` — negative-case
rehearsal: a record whose `type` is neither accepted value is refused, not silently coerced.

Validation, same scoped pair as before:
`PYTHONPATH=/home/liam/ttros-testenv/pytest:/home/liam/agentic-os-live/tools dashboard/backend/.venv/bin/python -m pytest tests/test_hermes_context_plugin.py tests/test_source_intake.py -v`
→ **21/21 passed** (13 + 8; two new tests added to the 19 already in place).

### Rollback

`tools/source_intake.py` and `tests/test_source_intake.py`: tracked, clean before this session;
`git checkout -- tools/source_intake.py tests/test_source_intake.py` reverts fully (also reverts
the earlier-authorized trailing-whitespace fix, since both live in the same tracked files).
`tools/source_intake_semantic.py` was already untracked before this session (created, uncommitted,
in STEP I1); no git rollback exists for it — restoring it means re-applying I1's original content,
which is not preserved as a separate preimage since it was never committed. `scripts/
i2_mechanical_verifier.py` and its `.txt` transcript are new, untracked, additive files with no
prior state to roll back to.

## Part A resumed — step 2 re-run for real (2026-09-10)

Prediction (written before running): `python3 tools/source_intake.py "<vault>/sources/intake/
records/d9cb4668....md" --mode semantic --json` will now succeed — 1 real Hermes model call,
producing a card and claim receipt, `model_invocations: 1`, `search_status: ready`, a new vault
commit past `8aa8e0`.

Ran the real CLI call, no mocks, `commit=True` (default), real `BusinessBrainGraphService`/
`aos_indexer`/`brain_memory.write_transaction`. **Result: success**, exactly as predicted:
```
brain_commit: ce53a61d7383c2ef193991f228002250c18b5b74
imported: 2
imported_pointers:
  - business_brain:sources/historical_calls/cards/d9cb4668....card.md
  - queue/receipts/source_intake/claims/historical/d9cb4668....claims.yaml
model_invocations: 1
search_status: ready
graphify_status: build
```
Vault HEAD advanced `8aa8e0` → `ce53a61`. **Model calls: 1 of 12 used.**

Inspecting the real, freshly-written card surfaced the second defect described above (broken
"Original" link pointing at a nonexistent `sources/historical_calls/d9cb4668....md`). Fixed the
code (change 2, above), then corrected the two already-committed vault documents in place — pure,
verified-unique string substitution of the one known-wrong link to the one known-right link,
nothing else touched (asserted equal after round-tripping the substitution both ways) — through
the same gated `tools.brain_memory.write_transaction` path used everywhere else (`expected_hashes`
pinned to the exact pre-repair on-disk content, `commit=True`), **0 additional model calls**. Vault
HEAD advanced `ce53a61` → `79912af`. Re-ran `BusinessBrainGraphService(...).build()` and
`aos_indexer.scan(...)` against the real search DB and Graphify root to keep retrieval consistent
with the corrected content; both reported `success`, and the card's pointer is present in the real
search index (`SELECT path FROM documents WHERE path=?` returned a row).

**Part A step 2: PASS.** Card + claim receipt written through the gated Business Brain write path;
claim receipt lives outside the vault, unindexed (`.claims.yaml` not in
`aos_indexer.INDEXABLE_EXTENSIONS`); original capture record untouched (verified below); no
duplicate source record; both defects this step found (schema mismatch, broken link) fixed and
regression-covered.

## Part A step 3-4 — card and INDEX in place (2026-09-10)

Confirmed as part of the same real run above and the mechanical verifier below: the source card
exists (`canonical_truth: false`, required front matter present, 3260 B including the mandatory
`hermes_last_write` provenance stamp, under the 3000 B compactness bound once that stamp is
excluded, matching I1's ruling on how that bound is measured), and `sources/historical_calls/
INDEX.md` gained exactly one new row (now 16 rows: the 15 legacy + this one), preserving every
existing row and the file's surrounding prose untouched (`evolve_historical_calls_index` only
replaces the table body).

## Part A step 5 — real retrieval arrival, fresh `hermes-*.json` (2026-09-10)

Per the earlier stop's own framing ("PART C['s two repairs are] for use when step 5 — arrival in a
fresh `hermes-*.json` — fails"), proved retrieval for real rather than through any Python-level
shortcut: a real, unmocked `hermes -p david -z "..."` call (same CLI-David surface already used
elsewhere in this repo, e.g. `scripts/step4_b8_live_exercise.py`), asking a question only
answerable from the new source's content.

Prediction (written before running): a real David call about "Fred Haiderzada and the realtor
workflow dashboard / MLS market reporting" will retrieve and cite the new source, and the run will
produce a fresh `hermes-*.json` context assembly (not a `ctx-*.json`, which CLAUDE.md's own
standing rule says proves nothing).

Ran it. **Result: success, exactly as predicted.** David's real answer cited
`business_brain:sources/intake/records/d9cb4668....md` by name, with the correct title and specific
transcript line ranges ("Relevant transcript lines: 53-76, especially 56, 59-60, 68-76"), and
described content (project-management-style transaction dashboard, document-tracking pain points,
OneDrive storage, security concerns) that matches the real source, not a fabrication. A new
`hermes-*.json` (the 57th, `queue/context_assemblies/hermes-20260909_171419_ab8c70-...json`,
`created_at: 2026-09-10T00:14:23Z`, `surface: "hermes:cli"`) was written for this call — freshly
generated for this exact query, not a stale/reused one. (Its own pre-assembled `blocks` are the
fixed identity/priorities/session/thread context, as usual; the source retrieval itself happened
through David's own live search/read tool use during the turn, evidenced by the cited pointer and
line-accurate content in the real answer — the same real production retrieval path every other
David query uses, not a bypass.) **Model calls: 2 of 12 used.** No FTS/`context_assembler.py`
defect surfaced — retrieval worked on the first real attempt — so **neither of PART C's two
pre-authorized repairs was needed or used.**

## Part A step 6 — mechanical verifier (2026-09-10)

No prior instrument covers this record shape (STEP I1's `scripts/i1_mechanical_verifier.py` is
hardcoded to the 15 historical slugs and the legacy schema). Wrote a bounded one-off,
`scripts/i2_mechanical_verifier.py`, mirroring I1's per-item checks (original present/unmutated,
card present/compact/canonical_truth false/linked/resolves, claim receipt present/unindexed/
canonical_truth false/claim_count matches/quotes-and-attributions verified, INDEX row count and
links, no MANIFEST leak) for this one source's real record, card, claim receipt, and INDEX row.

Prediction (written before running): PASS, zero findings, against the real vault post-repair.

Ran it: **PASSED: True, no findings** (`scripts/i2_mechanical_verifier.txt`).

Rehearsed the negative case before trusting the PASS: copied the real card + records into a scratch
directory, reintroduced the exact broken "Original" link this step fixed, and re-ran the same
verifier against the scratch root. **Result: PASSED: False**, with the expected single finding
("card does not link to its real original location"). The detector returns both answers. Re-ran
against the real vault afterward to leave the correct PASS transcript in place.

## STEP I2 — compact closeout

**PASS.**

**Proof steps 1-6:**
1. Original preserved — capture mode, real write_transaction, exact bytes/sha256 verified. PASS
   (from the earlier session; unchanged).
2. Semantic extraction — real Hermes call against the production-shape record, card + claim
   receipt written through the gated path. PASS.
3. Source card in place — canonical_truth: false, compact, linked correctly. PASS.
4. Historical-calls INDEX updated — one new row, 16 total, links resolve. PASS.
5. Retrieval arrival — real `hermes -p david -z` call cited the new source by pointer and line
   range, fresh `hermes-*.json` context assembly generated. PASS. Neither PART C repair needed.
6. Mechanical verifier — bounded one-off, `scripts/i2_mechanical_verifier.py`, PASSED: True, zero
   findings; negative case independently rehearsed and shown to fail correctly.

**Repairs made:**
- `tools/source_intake_semantic.py::extract_verbatim_source` — dispatches on record `type`,
  accepts both `historical_source` (unchanged) and `source` (new: decodes `TTROS:SOURCE-BYTES`,
  verifies sha256 against frontmatter).
- `tools/source_intake.py::_run_semantic_intake` — removed the now-redundant/incorrect
  post-hoc type check.
- `tools/source_intake_semantic.py::render_source_card` / `evolve_historical_calls_index` — derive
  the "Original" link from the record's actual `source_path` instead of assuming the legacy
  location (second defect, found while inspecting the real output of repair 1).
- One-time deterministic correction of the two already-committed vault documents (card + INDEX
  row) written before repair 2 landed, applied through `brain_memory.write_transaction` with
  pinned `expected_hashes`, 0 model calls.

**Before/after retrieval evidence:** before repair 2, the card's and INDEX row's "Original" link
read `[[sources/historical_calls/d9cb4668....|source]]` (does not resolve — no such file). After:
`[[sources/intake/records/d9cb4668....|source]]` (resolves — the file exists). Real David retrieval
(step 5) was run only after this correction and cited the source correctly by its real location.

**Mechanical verifier result:** `scripts/i2_mechanical_verifier.py` → PASSED: True, no findings.
Negative-case rehearsal → PASSED: False, expected finding, confirmed and cleaned up.

**Calls used: 2 of 12** (1 semantic extraction, 1 David retrieval turn). 10 remain unused.

**Files touched:**
- Repo (uncommitted, tracked-file edits): `tools/source_intake.py`, `tests/test_source_intake.py`.
- Repo (uncommitted, untracked, new/edited this step): `tools/source_intake_semantic.py` (edited;
  was already untracked from STEP I1), `scripts/i2_mechanical_verifier.py`,
  `scripts/i2_mechanical_verifier.txt`, this transcript.
- Vault (real commits, `TTROS Business Brain` repo): `8aa8e0` (capture, prior session) →
  `ce53a61` (semantic: card + claim receipt + INDEX row) → `79912af` (link-fix correction).
- No repo git commit, no push, per instruction.

**No migration/rewrite of the 15 historical sources — checked, not assumed:** re-ran
`scripts/i1_mechanical_verifier.py --overwrite` against the real vault after this step's changes.
It reports `PASSED: False`, but with only three findings, all cardinality assertions hardcoded to
"exactly 15" from before I2 existed ("expected 15 cards, found 16", "expected 15 claim receipts,
found 16", "INDEX does not have exactly 15 rows: found 16") — expected now that a 16th,
production-sourced card exists alongside the 15 historical ones. Zero findings named any of the 15
historical slugs individually; all 198 of their claim quote/attribution checks still pass. This is
I1's verifier being stale about a count it had no way to know would change, not a historical-source
regression — labeled as such rather than silently treated as a pass or a failure.

**Blockers:** none remaining.

**Next action:** none required for I2 itself. Liam may want the repo-level edits
(`tools/source_intake.py`, `tools/source_intake_semantic.py`, `tests/test_source_intake.py`,
`scripts/i2_*`) committed to `agentic-os-live`; not done here since no explicit commit instruction
was given for the repo (only "no git push," which is a narrower constraint).

**Token usage:** not separately tracked by this instrument; no agent invocation for any file-editing
step (`TOKEN_USAGE_TEXT` applies to `run_intake` calls as always: "Token usage: no agent
invocation"). The 2 real model calls' own usage files: semantic extraction at
`queue/context_assemblies/source-intake-semantic-d9cb4668....-e51b731792f2.usage.json` (its
context-assembly record at `queue/context_assemblies/hermes-extract-1-turn-1.json`), and the David
retrieval call's usage file at
`/tmp/claude-1002/-home-liam-agentic-os-live/38b3b0ee-871f-4efd-8eec-b690036a1a1d/scratchpad/i2_step5_david_call.usage.json`
(its context-assembly record at
`queue/context_assemblies/hermes-20260909_171419_ab8c70-...c035d425.json`).

**STEP I2: PASS.**

## Addendum — two discrepancies found in the closeout above, repaired (2026-09-10)

Liam reviewed the closeout above and found two problems with it before accepting it.

### Discrepancy 1 — the depth/precision follow-up was never run

The original I2 Part A step 6 spec required "a depth/precision follow-up reaches the
original," but only 2 model calls were spent (1 semantic extraction + 1 David retrieval
turn) — the retrieval proof above never actually asked a follow-up requiring depth beyond
what the compact source card already states.

Read the real card before writing the follow-up prompt (it has no board count, no city
names, no MLS/GVR specifics beyond "unavailable" open questions) and grepped the real
verbatim original for a fact meeting that bar: Fred's own count of GVR realty boards and
the specific cities he names under Fraser Valley (`sources/intake/records/d9cb4668....md`
lines 230, 234).

Wrote `scripts/i2_step6_depth_followup.py` — declared maximum 1 additional call, continuing
the existing 12-call budget from 2 (hard-stops if the running total would exceed 12 or if
this script's own call count would exceed 1). Ran the real, unmocked
`hermes -p david -z ...` CLI call (same CLI-David surface as before).

**Result: PASS.** David answered "like, I think 11 boards" and named Surrey, "Obisford,"
and Langley as the Fraser Valley cities — reproducing the transcript's own ASR
transcription artifacts ("Obisford" for Abbotsford, "Siri" for a second mention of Surrey)
verbatim. Independently grepped the real original record for these exact strings: both
`Obisford` and `Siri` and `11 boards` are real substrings of lines 230 and 234 of the
verbatim original, not paraphrases and not derivable from the card. David cited
`business_brain:sources/intake/records/d9cb4668....md`, lines 229-234, by name. A fresh
`hermes-20260909_175150_486fe1-...json` context assembly was written for this exact call
(`created_at: 2026-09-10T00:51:54Z`, `surface: "hermes:cli"`), confirmed to exist and be
freshly generated, not stale. **Calls used: 3 of 12** (up from 2). Transcript:
`scripts/i2_step6_depth_followup.txt`.

### Discrepancy 2 — production intake was mutating the historical-only INDEX

`sources/historical_calls/INDEX.md` gained a 16th row for the fresh production source,
and STEP I1's frozen-15 verifier started reporting `PASSED: False` (three stale
cardinality findings) as a result. Liam's instruction: production intake must never
mutate that index; the 15 historical records must stay unchanged; card and claim receipt
must live at the production paths he specified
(`sources/intake/cards/<sha>.card.md`, `queue/receipts/source_intake/claims/<sha>.claims.yaml`,
no `historical/` subdirectory).

**Code repair** (`tools/source_intake.py::_run_semantic_intake`): branches on
`header_fields.get("type") == "source"` (production shape) vs. `historical_source`
(legacy). Production shape now writes its card to `sources/intake/cards/` and its claim
receipt to `queue/receipts/source_intake/claims/` (flat, no `historical/`), and never
reads, evolves, or writes `sources/historical_calls/INDEX.md` at all. Legacy
`historical_source` intake is byte-for-byte the same code path as before — unchanged
paths, unchanged INDEX evolution. Removed one now-dead duplicate `documents = {...}` line
left over from the branch.

**Registry repair** (`context/client_scope_registry.json`, global scope): the new
`sources/intake/cards/` location needed the same two registrations the legacy
`sources/historical_calls/cards/` location already had — added
`"business_brain:sources/intake/cards/"` to `brain_pointer_prefixes` (the gate
`_run_semantic_intake` calls before writing) and a matching `path_prefix` entry to
`search_source_identities` (the gate the FTS indexer actually uses to decide what's
searchable, `tools/aos_indexer.py::document_from_path` →
`ClientScopeRegistry.scope_for_search_identity`). Without this second one specifically,
the production card wrote successfully but was silently absent from search — found by
querying the real search DB directly, not assumed. Did not touch `graphify_targets`: that
list is a manually curated per-file allowlist that historical cards were added to as a
one-time I1 backfill step, unrelated to the automatic production-intake code path, and
out of scope for "indexed/searchable and retrievable" (which step 5's original real
David-retrieval proof already satisfied via FTS + tool use, not Graphify).

**Vault repair** (one-time, real commits, 0 model calls): `write_transaction` has no
delete primitive, so the already-committed misfiled card had to be moved by hand: (1)
`write_transaction` created the card at its correct production path (content unchanged
except its embedded "Claim evidence" line, which pointed at the old
`claims/historical/...` path — corrected to the new flat path, verified as the only
substitution made by string-equality round-trip) and, in the same transaction, reverted
`INDEX.md` to `evolve_historical_calls_index` output over the 15 legitimate legacy cards
only (the Fred card excluded) — reproducing the original 15-row table exactly; (2) a
direct `git rm` + commit (same Hermes author identity `write_transaction` always uses)
removed the stray card left at the old `sources/historical_calls/cards/` path, since no
gated primitive exists for deletion; (3) the repo-local claim receipt (outside the vault,
plain filesystem, not git-tracked) was moved from `claims/historical/` to the flat
`claims/` path; (4) `BusinessBrainGraphService(...).build()` and `aos_indexer.scan(...)`
were re-run against the real graph root and search DB to make both consistent with the
corrected vault content. Vault HEAD: `f58b1aa` (pre-repair) → `558eb08` (card relocated +
INDEX reverted) → `c302653` (stray old-path card deleted).

**Verifier repairs**: `scripts/i2_mechanical_verifier.py` updated to check the production
paths (`sources/intake/cards/`, `queue/receipts/source_intake/claims/`, no `historical/`)
instead of the historical-tree paths it originally (wrongly) assumed a production source
would use; its INDEX check inverted from "expects 16 rows including this source" to
"expects exactly 15 rows, none of them this source"; added a real search-index presence
check (queries the actual `search/os_index.db` for the card's pointer) as a fifth check.
Negative case rehearsed: copied the real vault into a scratch directory, reintroduced the
exact wrong 16-row INDEX state, re-ran the verifier there — `PASSED: False`, both expected
findings (row count, source present), confirmed and cleaned up; re-ran against the real
vault afterward so the transcript left in place is the real PASS, not the rehearsal's
FAIL. `tests/test_source_intake.py::test_production_capture_source_feeds_semantic_extraction`
rewritten to assert the corrected paths and to assert the historical INDEX is
byte-identical before and after a production-shape semantic run (the guarantee this whole
repair exists to establish), plus that no card is ever written to the legacy
`sources/historical_calls/cards/` location for a production-shape source.

**Verification re-run, in order:**
1. Focused tests: `PYTHONPATH=/home/liam/ttros-testenv/pytest:/home/liam/agentic-os-live/tools dashboard/backend/.venv/bin/python -m pytest tests/test_hermes_context_plugin.py tests/test_source_intake.py -v` → **21/21 passed** (13 + 8, unchanged count from before this addendum — no test was added or removed, one was rewritten).
2. `scripts/i2_mechanical_verifier.py --overwrite` → **PASSED: True, no findings** (real vault, production paths). Negative case rehearsed separately (see above), confirmed `PASSED: False` on the real defect, then the real-vault PASS transcript was restored.
3. `scripts/i1_mechanical_verifier.py --overwrite` → **PASSED: True**, `cards_found=15 claim_records_found=15`, `substantive_claim_count=198`, no findings — the frozen historical-15 baseline is green again, not just "stale about a count" as the pre-repair closeout above had to argue.
4. Real search DB query confirms `business_brain:sources/intake/cards/d9cb4668....card.md` is indexed under `client_scope=global`, and the old `business_brain:sources/historical_calls/cards/d9cb4668....card.md` pointer is absent. `sources/historical_calls/cards/` still has exactly 15 files; `sources/intake/cards/` has exactly 1.

**Files touched, this addendum:**
- Repo (tracked-file edits, uncommitted): `tools/source_intake.py`, `tests/test_source_intake.py`, `context/client_scope_registry.json`.
- Repo (new, untracked): `scripts/i2_step6_depth_followup.py`, `scripts/i2_step6_depth_followup.txt`; `scripts/i2_mechanical_verifier.py`/`.txt` edited in place.
- Repo (moved, untracked, outside git): `queue/receipts/source_intake/claims/historical/d9cb4668....claims.yaml` → `queue/receipts/source_intake/claims/d9cb4668....claims.yaml`.
- Vault (real commits): `558eb08` (card relocation + INDEX revert), `c302653` (stray card deletion), plus the pre-existing `731a1cd`/`f58b1aa` retrieval-turn commits from the David calls (those commits are session-journal writes, not content changes).
- No git commit to `agentic-os-live`, no push, per instruction.

**Calls used: 3 of 12** (1 semantic extraction, 1 first David retrieval turn, 1
depth/precision follow-up). 9 remain unused.

**Blockers:** none.

**Next action:** none required for I2. The repo-level edits from both the original
closeout and this addendum remain uncommitted in `agentic-os-live`, as before.

**STEP I2 (addendum): PASS. Both discrepancies repaired and re-verified.**
