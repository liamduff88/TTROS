---
workflow: business_efficiency_assessment
skill: skills/business_efficiency_assessment/SKILL.md
path: workflows/business_efficiency_assessment/workflow.md
lane: delivery
profile: aos-delivery
trust: watch
---
# workflow: business_efficiency_assessment — deliver one CA$750 assessment
> Revisit: when the assessment SKILL.md, pricing, or report structure changes. · Last touched: 2026-07-07.

## Trigger
Queue item with: client entity page, discovery interview notes/transcript (Liam-run — intake is never automated), completion contract.

## Completion contract (default)
- **Done** = six-part report artifact in `output/`: executive summary · opportunity matrix · recommended tools/systems with cost ranges · quick-win plan · implementation/upsell opportunities · quantified value estimate with labelled assumptions. Every bottleneck (3–7) tagged: ROI lever + matrix position + target state (manual/hybrid/automated). Ends with the walkthrough routing question mapped to offers. Receipt written. Target: report in 48h + 30-min walkthrough scheduled by Liam.
- **Allowed unprompted** = read entity page + notes, draft report and matrix.
- **Stop conditions** = notes too thin to support ≥3 credible bottlenecks (return to Liam, don't pad); sensitive-data workflow needing impact-vs-risk framing Liam hasn't scoped; cross-client blend risk.

## Run
1. Confirm inputs + contract + isolation folder.
2. Execute skill steps 1–6 (inventory → select 3–7 → matrix → classify fixes → draft six-part report → route to offers).
3. Write to `workflows/business_efficiency_assessment/output/Q-YYYY-NNNN_assessment.md`.
4. Entity page update; receipt with token breakdown; coordinator writes ledgers at done-transition.

## Never
- <3 or >7 headline bottlenecks.
- Guaranteed savings/revenue claims; unlabelled assumptions.
- Full-autonomy recommendations where an approval gate belongs.
- Generic AI-agency tone — calm, premium, systems-led only.

## Verifier check
Six parts present, 3–7 bottlenecks fully tagged, assumptions labelled, routing question included, receipt complete.
