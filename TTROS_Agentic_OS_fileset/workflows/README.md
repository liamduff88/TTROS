# workflows/ — run instances of earned skills
> Revisit: when a workflow is added, retired, or a skill it mirrors changes. · Last touched: 2026-07-07.

A workflow is the executable shape of a skill: `workflows/<name>/workflow.md`
plus, once run, that instance's `output/` and `receipts/`. A skill defines
*how* to do the work; a workflow is *doing it* for a specific queue item.
No workflow exists without a matching skill in `skills/` — this folder
never invents scope the skill layer hasn't earned.

## Planned inventory (built in Batches 10–11, not yet present)
**Delivery workflows** (Batch 10 — 5 files, mirroring Batch 8 skills):
`fit_call_prep`, `quick_win_scan`, `business_efficiency_assessment`,
`speed_to_lead`, `voice_agent_setup`.

**Remaining workflows** (Batch 11 — 5 files, mirroring Batch 8–9 skills):
`client_memory`, `lead_gen_agent`, `ai_operations_support`,
`marketing_content`, `weekly_review`.

## Naming note
Workflow folder names occasionally drop the `build_` / `_prep` prefix used
on the matching skill (e.g. skill `build_speed_to_lead` → workflow
`speed_to_lead`) — the workflow is named for the deliverable, the skill
for the playbook. Keep this mapping explicit in each `workflow.md`'s
frontmatter so the link isn't left to inference.

## Status
Every workflow this OS runs stays queue-tracked and receipted per
`rules/completion_contract.md` — no workflow ships an external action
without the same per-action approval `no_external_action_without_approval.goal.md`
checks for.

## Pointers
- Matching skills: `skills/README.md`
- Queue tracking: `queue/run_ledger.jsonl` · schema: `run_ledger_schema.json`
- Completion rule: `rules/completion_contract.md`
