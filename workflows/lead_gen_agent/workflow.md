---
workflow: lead_gen_agent
skill: skills/build_lead_gen_agent/SKILL.md
path: workflows/lead_gen_agent/workflow.md
lane: delivery
profile: aos-delivery (pipeline logic with aos-revenue)
trust: v0 pre-seeded
---
# workflow: lead_gen_agent — deliver one signed Lead Generation Agent build (scoped after Fit Call)
> Revisit: after each of the first 3 client runs; when build_lead_gen_agent SKILL.md or the internal V4.1 pipeline changes. · Last touched: 2026-07-07.

Workflow drops the skill's `build_` prefix — named for the deliverable, per workflows/README.md.

## Trigger
Queue item with: signed post-Fit-Call scope, client entity page, isolation folder confirmed, completion contract, plus client ICP definition, CASL/consent posture + sender identity, and CRM system of record.

## Completion contract (default)
- **Done** = Stage 6 CLOSE per completion_contract.md: all stages evidenced; Stage 4 sample run passed acceptance (evidence-verified prospects, scoring matches calibration, drafts pass the binding QA checklist, CRM records land correctly, **zero sends occurred**); per-message client approval gate demonstrated; handoff doc delivered; access closeout passed; entity page updated; receipt with full token breakdown.
- **Allowed unprompted** = Stages 0–2 reads/drafts; Stage 3 pipeline implementation with connector actions read/draft-only.
- **Stop conditions** = missing scope, entity page, ICP, CASL posture, or CRM system; Stage 2 design not client-signed; any send/connect/message to anyone — no test exception — without per-message client approval and `approved_external_action` on the item; CRM mutation outside the designed handoff.

## Run
Execute Stages 0–6 exactly per `skills/build_lead_gen_agent/SKILL.md` (client mirror of V4.1: calibration → discovery → evidence verify → contact verify → scoring → outreach drafting → QA → report → memory write), with per-stage artifacts:
- Stage 1 lead-gen reality map + Stage 2 pipeline design (QA checklist, forced downgrades, CASL rules, hard approval gate) → `output/`, client-approved before Stage 3.
- Stage 4 sample-run evidence incl. zero-send confirmation → `output/evidence/`.
- Stage 5 handoff doc → `output/`; Stage 6 receipt → `receipts/`.
Coordinator appends run_ledger + token_ledger; skill_trust.jsonl updated toward v0-marker removal (3 real uses).

## Never
- Send, connect, or message any prospect — ever — without per-message client approval.
- Invent prospect facts, urgency, budget, or intent; weak evidence gets downgraded, not dressed up.
- Skip the QA checklist or CASL encoding.
- Mutate the client CRM outside the approved handoff.

## Verifier check
Stage 4 acceptance evidence includes an explicit zero-sends confirmation and a demonstrated approval gate — never inferred.
