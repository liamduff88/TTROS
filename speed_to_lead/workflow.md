---
workflow: speed_to_lead
skill: skills/build_speed_to_lead/SKILL.md
path: workflows/speed_to_lead/workflow.md
lane: delivery
profile: aos-delivery
trust: v0 pre-seeded
---
# workflow: speed_to_lead — deliver one signed Speed-to-Lead build (from CA$1,000)
> Revisit: after each of the first 3 client runs; when build_speed_to_lead SKILL.md changes. · Last touched: 2026-07-07.

Workflow name drops the skill's `build_` prefix — named for the deliverable, per workflows/README.md.

## Trigger
Queue item with: signed scope, client entity page, client-isolation folder confirmed, completion contract.

## Completion contract (default)
- **Done** = Stage 6 CLOSE per completion_contract.md: all 7 stages evidenced, test lead met response-time targets on every scoped inbound path, handoff doc delivered, access closeout checklist passed (aos-ops review), entity page updated, receipt with full token breakdown.
- **Allowed unprompted** = Stages 0–2 reads/drafts; Stage 3–4 config work in read/draft-only connector posture; launching Claude Code/Codex for config/scripts.
- **Stop conditions** = missing signed scope or entity page; Stage 2 design not client-signed; any action that would send to a real lead without `approved_external_action` named on the item (EXTERNAL_ACTIONS.md); scope creep beyond mapped inbound paths.

## Run
Execute Stages 0–6 exactly per `skills/build_speed_to_lead/SKILL.md`, with per-stage artifacts:
- Stage 1 map + Stage 2 design → `output/` and client-approved before Stage 3.
- Stage 4 acceptance evidence (screenshots/logs, per inbound path) → `output/evidence/`.
- Stage 5 handoff doc → `output/`; Stage 6 receipt → `receipts/`.
Coordinator appends run_ledger + token_ledger; skill_trust.jsonl updated toward v0-marker removal (3 real uses).

## Never
- Skip Stage 0 inputs or Stage 2 sign-off.
- Auto-send to real leads during build/test without the flag.
- Declare done without recorded per-path evidence.
- Leave client credentials/access open after Stage 6.

## Verifier check
Contract's Stage 6 definition met with evidence on file — never a general impression of quality.
