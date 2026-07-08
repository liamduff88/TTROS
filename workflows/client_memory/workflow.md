---
workflow: client_memory
skill: skills/build_client_memory/SKILL.md
path: workflows/client_memory/workflow.md
lane: delivery
profile: aos-delivery
trust: v0 pre-seeded
---
# workflow: client_memory — deliver one signed Client Memory & Data Consolidation build (from CA$2,000)
> Revisit: after each of the first 3 client runs; when build_client_memory SKILL.md changes. · Last touched: 2026-07-07.

Workflow drops the skill's `build_` prefix — named for the deliverable, per workflows/README.md.

## Trigger
Queue item with: signed scope, client entity page, client-isolation folder confirmed, completion contract, data-sensitivity classification started or scheduled at Stage 0.

## Completion contract (default)
- **Done** = Stage 6 CLOSE per completion_contract.md: knowledge base delivered matching the client-approved Stage 2 plan; citation rule ("no claim without a source link") verified by recorded spot-check; the defined real-business-question set answered correctly from the base alone; TTR access to client sources revoked; entity page updated; receipt with full token breakdown.
- **Allowed unprompted** = Stages 0–2 reads/drafts; Stage 3 consolidation in read/draft-only posture against client systems.
- **Stop conditions** = missing signed scope, entity page, or sensitivity classification; Stage 2 plan not client-signed; any source outside the classified inventory; anything requiring write access to client systems without `approved_external_action` (EXTERNAL_ACTIONS.md).

## Run
Execute Stages 0–6 exactly per `skills/build_client_memory/SKILL.md`, with per-stage artifacts:
- Stage 1 source inventory + Stage 2 consolidation plan → `output/`, client-approved before Stage 3.
- Stage 4 acceptance evidence (spot-check trace log + question-set results) → `output/evidence/`.
- Stage 5 handoff doc (structure, update model, citation rule, AI consumption, pause/rollback) → `output/`; Stage 6 receipt → `receipts/`.
Coordinator appends run_ledger + token_ledger; skill_trust.jsonl updated toward v0-marker removal (3 real uses).

## Never
- Ingest a source outside the scoped, sensitivity-classified inventory.
- Write any page claim without a source link.
- Copy client knowledge into TTROS's substrate or any other client's space (client_data_boundaries.md).
- Retain access to client data stores after Stage 6.

## Verifier check
Contract's Stage 6 definition met with spot-check and question-set evidence on file — never a general impression of quality.
