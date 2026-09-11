# Phase 2 — rehearsal plan (declared BEFORE any rehearsal call is spent)

Cap (SS6.4, operator ruling 2026-09-09): **20 calls total**, one persisted counter, covering
rehearsal + retries + the 12 real items combined.

## Deterministic (zero-cost) checks — already run

`scripts/validation_a_runs/blind_run/phase2_deterministic_selftest.txt` — 8/8 pass, 0 model
calls spent (counter file did not exist before or after). Proves: SOURCE_UNAVAILABLE suppresses a
detector call; invalid verdict rejected (including SOURCE_UNAVAILABLE-as-verdict); SOURCE_UNAVAILABLE-as-tag
rejected; unknown tag rejected; a valid output is accepted (both-answers rehearsal of the parser);
cap enforcement denies over-cap and allows under-cap (both directions of that detector too).

## Planned model-assisted fixture set (constructed, synthetic — never a real item)

Three fixtures, designed to jointly cover both binary verdict directions and all nine SS6.1
reason tags using multi-tag fixtures per the operator's ruling to conserve budget:

1. **Fixture 1 — SUPPORTED / normalization.** Claim and source differ only by apostrophe style
   and hyphen-vs-space (a "90-day pilot" vs "90 day pilot", "client's" vs "clients"). Expected:
   verdict SUPPORTED, tag `normalization`.
2. **Fixture 2 — NOT SUPPORTED / five tags.** Source: a contractor suggested a free tier; Liam
   explicitly rejected it; pricing stays paid-only; the decision was finalized and closed. Claim:
   "Liam is currently considering a free tier, as advised by the team." Expected tags:
   `attribution` (wrong actor — team vs. Liam-rejected-contractor-suggestion), `polarity_assertion`
   (asserts consideration where source asserts rejection), `prohibited_opposite` (free tier vs.
   confirmed paid-only), `temporal_status` (currently-considering vs. finalized/closed),
   `essential_qualifier` (drops "explicitly rejected" / "finalized" / "not up for
   reconsideration").
3. **Fixture 3 — NOT SUPPORTED / three tags.** Source: two disconnected paragraphs — current
   integrations (Slack, Gmail) in one, and a separately-excluded historical Salesforce evaluation
   (explicitly not among this source's own declared content) in an unrelated section. Claim:
   "Integrates with Slack, Gmail, and Salesforce, with full visibility into the Salesforce
   evaluation." Expected tags: `list_coverage` (false third list member), `locality` (connects two
   disconnected subjects from opposite parts of the source), `source_contract` (the Salesforce
   evaluation detail is explicitly excluded source material, not an ordinary retrieval miss).

Coverage check: normalization(f1) + attribution, polarity_assertion, prohibited_opposite,
temporal_status, essential_qualifier (f2) + list_coverage, locality, source_contract (f3) = all
nine tags, each at least once. Both verdict directions present (SUPPORTED in f1; NOT SUPPORTED in
f2, f3).

## Planned call count and budget preservation

* **Call #0 — wiring shakedown (added before spending, still inside the 6-call ceiling below):**
  one trivial call through the exact same `invoke_hermes()` plumbing (pinned provider/model/
  reasoning, `--query-file`, `--oneshot`, `-t ""`, `--max-turns 1`) with a throwaway prompt asking
  for the literal JSON `{"verdict": "SUPPORTED", "reason_tags": [], "evidence": "shakedown"}`, to
  catch a CLI-flag/plumbing defect before spending it against a real fixture. This is a detector
  self-check, not a rehearsal fixture, and proves nothing about the vocabulary.
* Primary plan: **3 calls** (one per fixture, no retries expected).
* Contingency reserve: up to **3 additional calls** for a redesigned fixture, only if the primary
  fixture set fails to exercise a required direction or tag (a redesign is a fresh call under this
  same declared rehearsal ceiling, not a "retry" of a fixture that already returned a valid but
  differently-tagged result — per the ruling, a valid detector result is final and is never
  retried because a tag was unexpected).
* **Declared rehearsal ceiling: 6 calls maximum, inclusive of call #0.**
* Budget check: cap 20 − rehearsal ceiling 6 = **14 remaining**, which is ≥ 12 required for the
  real population, with 2 calls of margin for real-item retries (transport/malformed-output only).

If the required rehearsal cannot be completed within this 6-call ceiling while preserving ≥12 for
the real population, the run stops before spending real-item budget (Phase 2.3 / SS0.7).
