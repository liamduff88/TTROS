---
name: prospecting_week_review
description: Friday rollup of the prospect ledger — funnel counts and reply/call rates by lane, signal class, ICP variant, and angle type; flags stale states; at cycle end, proposes evidence-backed ICP edits. Proposes only — never edits memory files.
when-to-use: Every Friday after the follow-up sweep; week 4 run doubles as the cycle review. Owner: aos-revenue. Trust: v0 (pre-seeded — hardened by first 3 runs; approval to be logged in decisions/DECISIONS.md).
---
# /prospecting-week-review
> Revisit: after the first cycle review — the metrics set itself is v1. · Last touched: 2026-07-16

## Purpose
The engine's brain: turn ledger rows into decisions. Weekly it reports;
at week 4 it proposes ICP changes with evidence. Data changes the ICP
files; vibes don't.

## Inputs
- `queue/prospects.jsonl` (full history) + status vocabulary.
- `business_brain:memory/ideal_clients_A.md`,
  `business_brain:memory/ideal_clients_B.md`,
  `business_brain:memory/prospecting_query_bank.md`, and
  `business_brain:memory/prospecting_rotation_plan.md` — hypotheses under test.
- `business_brain:memory/prospecting_scoring_contract.md` — score/tier audit contract.
- Prior week-review artifacts (trend continuity).

## Steps
1. **Integrity pass** — flag unlogged gaps (drafted >3 days with no
   sent/rejected), overdue touches, pendings ≥7 days not withdrawn,
   schema-invalid rows. List for Liam; don't repair silently.
2. **Funnel rollup** — counts per status, week and cumulative, vs
   cycle-1 targets (25 sends/wk; reply ≥10%; 2–4 Fit Calls/cycle).
3. **Segment cuts** — acceptance rate, reply rate, positive-reply rate,
   call-booked rate by: lane · signal_class · icp_variant · angle_type ·
   first_touch_style. Mark every segment under ~20 sends
   **INSUFFICIENT SAMPLE — no conclusion** (hard rule).
4. **Tier accuracy** — do A-tier prospects outperform B-tier? If not,
   the scoring weights are the suspect, not the prospects.
5. **Query performance** — evidenced candidates per query; recommend
   retiring 2-week zero-yield queries, promoting producers.
6. **Weekly artifact** — one report: integrity flags, funnel, segment
   table (sample sizes always shown), top/bottom performers, next-week
   focus suggestion. Benchmarks for context: 30–45% connection
   acceptance is par; 10–25% reply rate is a good outreach range.
7. **Cycle review (week 4 only)** — proposed edits to ideal_clients_A/B
   (weights, disqualifiers, 60/40 split), rotation plan, and query bank
   — each proposal citing the ledger rows behind it, formatted for the
   memory_promotion flow. Include the LinkedIn Premium renew/upgrade/
   lapse recommendation from acceptance-rate and search-friction
   evidence. Liam approves; `memory_promotion` applies.

## Never
- Edit any Business Brain memory file, the rotation plan, or the query bank directly.
- Draw conclusions from segments under minimum sample.
- Invent, backfill, or smooth ledger data; report gaps as gaps.
- Propose >2 variable changes per cycle (attribution collapses).

## Done when
Weekly report artifact exists with integrity flags, funnel vs targets,
segment cuts with sample sizes, and query performance; week-4 runs also
contain evidence-cited change proposals awaiting Liam's approval.
Receipt written.
