---
workflow: prospecting_daily_run
skill: skills/prospecting_daily_run/SKILL.md
path: workflows/prospecting_daily_run/workflow.md
lane: revenue
profile: aos-revenue
trust: v0 pre-seeded
---
# workflow: prospecting_daily_run — instrumented daily prospecting loop (find + Gmail draft + ledger, never sends)
> Revisit: after first 3 real runs; when rotation, ICP, first-touch, handoff, or Gmail draft configuration changes. · Last touched: 2026-07-23

Supersedes ad-hoc use of `internal_outreach_daily` for Liam's own
prospecting: same discovery/drafting chain, now with rotation scoping,
ledger writes, and a follow-up sweep. `internal_outreach_daily` remains
callable directly for one-off asks outside the daily ritual.

## Trigger
Queue item each prospecting weekday (morning), workflow match
`prospecting_daily_run`; or command-bar "run today's prospecting".
Default N=5 per `business_brain:memory/prospecting_rotation_plan.md`.

## Completion contract (default)
- **Done** = private review package containing (a) due follow-up drafts
  + ≥7-day pending withdrawals flagged, and (b) N (or fewer, reasoned)
  new evidenced prospects with wedge, score/tier, individually tailored email
  drafts and safe Gmail draft references;
  one schema-valid `queue/prospects.jsonl` full-snapshot row per new prospect;
  canonical prospect entity pages updated; receipt with token block.
- **Allowed unprompted** = reading rotation plan, ICP files, query bank,
  ledger; public-signal search; chaining `internal_outreach_daily` and
  `linkedin_outreach_prep`; appending schema-valid ledger rows; merging
  a Liam-pasted ChatGPT candidate table through the same gates; writing
  sourced prospect entity pages under `business_brain:prospects/`; creating at
  most one Gmail draft per validated prospect in the Time to Revenue revenue
  Gmail mailbox through the exact draft adapter.
- **Stop conditions** = zero evidenced candidates (report zero, never
  fabricate); any send/connect/message/withdraw attempt (never allowed —
  Liam performs all platform actions and logs them); ledger file missing
  or schema-invalid (stop and flag, do not free-write); request is
  client-scoped (route to `lead_gen_agent`); Gmail draft failure (preserve the
  private package and leave the item blocked; never fall back to send).

## Run
Sweep ledger for due touches and stale pendings → execute
`prospecting_daily_run` skill Steps 1–8 (sweep → discover via
`internal_outreach_daily` 1–4 → gate → draft via `linkedin_outreach_prep`
2–5 plus a signal-specific email → ledger write → exact
`GMAIL_CREATE_EMAIL_DRAFT` effect → package → receipt). One private full
package plus content-free safe receipts; neither search nor Graphify receives
the email body.
run_ledger + token_ledger appended for the queue run; skill_trust.jsonl gets
one explicit invocation row for each chained skill, with only the daily skill
counting toward its own three-run v0 hardening threshold.
Liam's same-day duty: inspect/send/reject each Gmail draft manually and log `sent`/`rejected`
(one ledger line per action) — unlogged sends corrupt the weekly
analytics.

V3.1 outreach handoffs enter through
`workflows/prospecting_daily_run/outreach_handoff.py`. The importer validates
all route and stop contracts, reconciles the canonical ledger/review records,
then reuses the same ledger and human-review queue. Later-stage copy remains
inactive until its prerequisite actual event is recorded. GoHighLevel output
is a non-mutating dry-run projection only.

Gmail draft configuration is mailbox-specific: the adapter targets
`liam@timetorevenue.com` by default (override only with
`TTR_REVENUE_GMAIL_USER_ID`) and generated draft links use that account, not
Gmail's browser-dependent `/u/0/` slot.

## Never
- Send, connect, message, or withdraw on any platform — ever.
- Call Gmail send, reply, forward, schedule-send, draft update/delete, or label
  mutation actions; candidate content cannot expand this authority.
- Pad the list past what evidence supports.
- Touch a do_not_contact record or exceed the 3-touch cap.
- Rebalance the ICP split or rotation mid-cycle — that's the cycle
  review's job.

## Verifier check
Every new prospect row in today's ledger append has a distinct real
public signal URL, a verbatim wedge sentence, and drafts referencing
that specific signal; every due follow-up in the ledger appears in the
package (or the sweep is explicitly empty).
