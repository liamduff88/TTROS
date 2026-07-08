# skills/ — earned playbooks
> Revisit: when a skill is added, retired, or a v0 marker is removed. · Last touched: 2026-07-07.

A skill is a named, repeatable playbook — not invented ahead of need.
Claude Code and Codex propose skills; they don't create them. The default
rule and the one doctrine exception (pre-seeded v0 delivery builds) are
in `SKILL_GRADUATION_POLICY.md` — read that before adding anything here.

## What goes in each skill folder
`skills/<name>/SKILL.md` — frontmatter (name, description, when-to-use),
steps, a "never" list, a verifiable done-when. Every non-v0 skill starts
at `watch` in `queue/skill_trust.jsonl` and graduates on real repeated use.

## Planned inventory (built in Batches 8–9, not yet present)
**Delivery & sales** (Batch 8 — 10 files): `fit_call_prep`,
`quick_win_scan`, `business_efficiency_assessment`,
`ai_operations_support`, `client_hub`, `aoa_working_session`,
`build_speed_to_lead` (v0), `build_voice_agent` (v0),
`build_client_memory` (v0), `build_lead_gen_agent` (v0).

**Ops & content** (Batch 9 — list carries an open count question: the
batch prompt names 9 files against a planned count of 8, and flags that
`custom_project` may duplicate into Batch 8's v0 set — resolve at Batch 9
time, not here): `custom_project` (v0), `content_draft`,
`linkedin_outreach_prep`, `proposal_prep`, `case_note`, `weekly_review`,
`morning_brief`, `maintain_os`, `memory_promotion`.

## v0 pre-seeded skills
`build_speed_to_lead`, `build_voice_agent`, `build_client_memory`,
`build_lead_gen_agent`, `custom_project` are seeded immediately (they map
directly to the offer ladder) and carry a `v0 (pre-seeded — hardened by
first 3 client uses)` marker until three real uses clear it.

## Pointers
- Graduation rule: `SKILL_GRADUATION_POLICY.md`
- Trust ledger: `queue/skill_trust.jsonl` · schema: `skill_trust_schema.json`
- Matching workflows: `workflows/README.md`
