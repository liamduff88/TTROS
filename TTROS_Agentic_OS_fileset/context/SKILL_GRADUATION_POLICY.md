# SKILL_GRADUATION_POLICY.md — how a workflow earns a file
> Revisit: when a v0 playbook hardens, or a lane trips a promotion trigger. · Last touched: 2026-07-07.

## The default rule
A skill gets a named file only after real repeated use — roughly three
manual repeats. Before that it's a note, not a file. Claude Code and Codex do
not invent skills or agents outside the blueprint; they propose, Liam decides.

## The one doctrine exception: pre-seeded (v0) playbooks
The four standard delivery builds (`/build-speed-to-lead`, `/build-voice-agent`,
`/build-client-memory`, `/build-lead-gen-agent`) plus `/custom-project` are
seeded as skill files immediately, marked `v0 (pre-seeded — hardened by first
3 client uses)`, because they map directly to the offer ladder and don't need
speculative invention. This is the only case where the 3-repeats rule runs
*after* the file exists instead of before it.

Every v0 skill records, in its own file, the date of each real use
(rules/always.md #11). Three real uses removes the v0 marker — the skill is
now "earned" like any other, and its next changes go through normal
maintenance, not hardening.

## What counts as a real use
A completed queue item, full receipt, real client or real internal task —
not a dry run, not a test call. `/maintain-os` audits v0-skill usage weekly
and flags any v0 skill sitting unused past a normal sales-cycle window.

## Trust tracking
`queue/skill_trust.jsonl` logs each skill invocation: skill, date, item id,
outcome (ACCEPT/REVISE), lane. This is the evidence base `/maintain-os` reads
— graduation and demotion are both mechanical checks against this ledger,
not vibes.

## Agent / profile promotion (departmental sub-orchestrators)
Same earned-not-invented logic, one layer up. A department gets its own
sub-orchestrator profile (e.g. `aos-delivery-lead`) when, for 3 consecutive
weeks, ANY of:
- ≥5 concurrent open queue items in that lane, or
- ≥2 multi-stage client projects running in parallel in that lane, or
- the orchestrator's token spend on intra-department coordination for that
  lane exceeds the cost of a dedicated mid-model sub-orchestrator (visible
  from `token_ledger.jsonl`).

Demotion: a sub-orchestrator whose lane drops below all three thresholds for
6 weeks is retired back to flat orchestration for that department.
Promotion/demotion are both a single-profile change plus a `lane_profiles.json`
edit — cheap, reversible, logged in the decisions log. Client Success and
Productization remain notes in the blueprint, not files, until they clear
this same bar.

## Demotion for skills
A skill with a REVISE rate trending up, or repeatedly bypassed in favor of a
manual approach, is a maintenance flag — `/maintain-os` reports it, Liam
decides whether to retire, merge, or rewrite it. Never silently dropped.

## Enforcement
Checked by `/maintain-os` (weekly scan + monthly interview). Mirrored in
rules/always.md #11, ROT.md's pre-seeded-playbook row.
