# queue/templates/skill_creation.prompt.md
> Template only — does not create a skill file or change queue state.
> Claude Code and Codex do not invent skills outside the blueprint; they
> propose, Liam decides (SKILL_GRADUATION_POLICY.md).

## Purpose
Turn a repeated manual workflow into a proposal for a named skill file in
`skills/`.

---

**Skill creation proposal — proposed name: {skill_name}**

Lane: {lane} · Owning profile: {profile}

### Evidence of repetition
Reference the specific `skill_trust.jsonl` / `run_ledger.jsonl` entries (or
manual run dates) showing the workflow has recurred:
- {repeat_1}
- {repeat_2}
- {repeat_3}

Default rule: **roughly three manual repeats** before a file exists. The
only exception is the pre-seeded v0 delivery playbooks (already filed) —
this template is for anything else.

### Proposed skill shape
- Stages: {stage_list}
- Owner profile: {profile}
- Inputs it reads (pointers only): {memory_pointers}
- Outputs it produces: {expected_artifacts}
- Stop conditions: {stop_conditions}

### Why this isn't already covered
{gap_explanation} — confirm this doesn't duplicate an existing skill in
`skills/` or a pre-seeded playbook.

### Never
- File the skill before Liam approves this proposal.
- Invent an agent or profile to own it — it must map to one of the five
  existing `aos-*` profiles.

### On approval
File `skills/{skill_name}/SKILL.md` per the blueprint's skill template,
marked `earned` (not v0) with today's date as its origin, and log the
approval in `decisions/DECISIONS.md`.
