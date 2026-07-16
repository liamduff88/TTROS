---
workflow: fit_call_prep
skill: skills/fit_call_prep/SKILL.md
path: workflows/fit_call_prep/workflow.md
lane: revenue
profile: aos-revenue
trust: watch
---
# workflow: fit_call_prep — run a Fit Call prep for one named prospect
> Revisit: when fit_call_prep SKILL.md changes. · Last touched: 2026-07-15.

## Trigger
Queue item exists (Q-YYYY-NNNN) with: prospect name + company + at least one public URL, and a completion contract. Refuse to start without the contract (always.md #8).

## Completion contract (default for this workflow)
- **Done** = one-page brief artifact in `output/` with sourced research summary, 2–3 leak hypotheses tagged to ROI levers, question script, next-step options (Quick-Win Scan CA$350 / Assessment CA$750 / scoped build); receipt in `receipts/`.
- **Allowed unprompted** = read an exact prospect `business_brain:<relative-path>` supplied by the item, read public web signals, draft. No basename lookup or inferred client path.
- **Stop conditions** = prospect can't be verified from public signals; ambiguity about which prospect/company; anything requiring contact with the prospect (never happens here — no `approved_external_action` variant of this workflow exists).

## Run
1. Open queue item; confirm contract present; log start.
2. Execute skill steps 1–4 (research → leak hypotheses → question script → next-step options) exactly per `skills/fit_call_prep/SKILL.md`.
3. Write brief to `workflows/fit_call_prep/output/Q-YYYY-NNNN_fit_call_brief.md`.
4. Record a sourced prospect entity-page update proposal in the receipt when an exact pointer was supplied; do not write to the Brain in Block 1.
5. Write receipt to `receipts/` with token breakdown; coordinator appends run_ledger + token_ledger lines at done-transition.

## Never
- Contact the prospect or touch their systems.
- Invent facts, budget, urgency, or tech stack.
- Widen to a full diagnosis — the call finds one bottleneck.

## Verifier check
Brief exists, every research claim sourced, hypotheses ≤3 and lever-tagged, receipt complete. Checked against this contract, not vibes.
