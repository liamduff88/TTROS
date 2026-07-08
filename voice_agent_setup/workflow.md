---
workflow: voice_agent_setup
skill: skills/build_voice_agent/SKILL.md
path: workflows/voice_agent_setup/workflow.md
lane: delivery
profile: aos-delivery
trust: v0 pre-seeded
---
# workflow: voice_agent_setup — deliver one signed Voice Agent Setup (from CA$1,000 + platform/usage)
> Revisit: after each of the first 3 client runs; when build_voice_agent SKILL.md changes. · Last touched: 2026-07-07.

Workflow name drops the skill's `build_` prefix — named for the deliverable, per workflows/README.md.

## Trigger
Queue item with: signed scope, client entity page, isolation folder, completion contract, plus Stage 0 capture fields — phone platform, call volume, hours, booking system, platform/usage cost expectations (priced separately).

## Completion contract (default)
- **Done** = Stage 6 CLOSE: all stages evidenced; scripted test calls passed (missed call, voicemail, after-hours, booking request, and the forbidden-promise probe) with per-call evidence; handoff doc including the client-approved never-say/never-promise list, pause procedure, and usage costs; access closeout passed; entity page + receipt written.
- **Allowed unprompted** = Stages 0–2 reads/drafts; Stage 3 platform config and scripts in read/draft-only posture.
- **Stop conditions** = never-say list not client-approved before deploy; any live outbound call or real-caller exposure without `approved_external_action`; regulated-claim ambiguity for the client's industry (escalate to Liam); scope creep past the mapped call flow.

## Run
Execute Stages 0–6 per `skills/build_voice_agent/SKILL.md`:
- Stage 1 call-flow map + Stage 2 design (incl. never-say list) → `output/`, client-approved before Stage 3.
- Stage 4 scripted-call evidence → `output/evidence/`, one record per test call.
- Stage 5 handoff doc → `output/`; Stage 6 receipt → `receipts/`.
Coordinator appends run_ledger + token_ledger; skill_trust.jsonl tracks v0 hardening.

## Never
- Deploy without the approved never-say/never-promise list.
- Let the agent quote prices, guarantees, or regulated claims outside the approved script.
- Skip scripted test calls or their evidence.
- Hide platform/usage costs from the handoff doc.

## Verifier check
Forbidden-promise probe evidence on file; never-say list in the handoff doc; Stage 6 contract met.
