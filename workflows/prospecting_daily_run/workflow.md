---
workflow: prospecting_daily_run
skill: skills/prospecting_daily_run/SKILL.md
path: workflows/prospecting_daily_run/workflow.md
lane: revenue
profile: aos-revenue
trust: v0 pre-seeded
---
# workflow: prospecting_daily_run — instrumented daily prospecting loop (find + draft + ledger, never sends)
> Revisit: after first 3 real runs; when the rotation plan, ICP files, or first-touch config changes. · Last touched: 2026-07-16

Supersedes ad-hoc use of `internal_outreach_daily` for Liam's own
prospecting: same discovery/drafting chain, now with rotation scoping,
ledger writes, and a follow-up sweep. `internal_outreach_daily` remains
callable directly for one-off asks outside the daily ritual.

## Trigger
Queue item each prospecting weekday (morning), workflow match
`prospecting_daily_run`; or command-bar "run today's prospecting".
Default N=5 per `business_brain:memory/prospecting_rotation_plan.md`.

## Completion contract (default)
- **Done** = review-package artifact containing (a) due follow-up drafts
  + ≥7-day pending withdrawals flagged, and (b) N (or fewer, reasoned)
  new evidenced prospects with wedge, score/tier, angle-typed drafts;
  one schema-valid `queue/prospects.jsonl` full-snapshot row per new prospect;
  canonical prospect entity pages updated; receipt with token block.
- **Allowed unprompted** = reading rotation plan, ICP files, query bank,
  ledger; public-signal search; chaining `internal_outreach_daily` and
  `linkedin_outreach_prep`; appending schema-valid ledger rows; merging
  a Liam-pasted ChatGPT candidate table through the same gates; writing
  sourced prospect entity pages under `business_brain:prospects/`.
- **Stop conditions** = zero evidenced candidates (report zero, never
  fabricate); any send/connect/message/withdraw attempt (never allowed —
  Liam performs all platform actions and logs them); ledger file missing
  or schema-invalid (stop and flag, do not free-write); request is
  client-scoped (route to `lead_gen_agent`).

## Run
Sweep ledger for due touches and stale pendings → execute
`prospecting_daily_run` skill Steps 1–7 (sweep → discover via
`internal_outreach_daily` 1–4 → gate → draft via `linkedin_outreach_prep`
2–5 → ledger write → package → receipt). Single combined artifact.
run_ledger + token_ledger appended for the queue run; skill_trust.jsonl gets
one explicit invocation row for each chained skill, with only the daily skill
counting toward its own three-run v0 hardening threshold.
Liam's same-day duty: send/reject each draft and log `sent`/`rejected`
(one ledger line per action) — unlogged sends corrupt the weekly
analytics.

## Never
- Send, connect, message, or withdraw on any platform — ever.
- Pad the list past what evidence supports.
- Touch a do_not_contact record or exceed the 3-touch cap.
- Rebalance the ICP split or rotation mid-cycle — that's the cycle
  review's job.

## Verifier check
Every new prospect row in today's ledger append has a distinct real
public signal URL, a verbatim wedge sentence, and drafts referencing
that specific signal; every due follow-up in the ledger appears in the
package (or the sweep is explicitly empty).
