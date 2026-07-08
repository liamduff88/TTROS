---
name: morning_brief
description: Daily 8am scheduled brief — calendar (read), open queue, overnight receipts, top 3 priorities. Read-only by construction; the safe first automation.
when-to-use: Scheduled daily 8am, or on Liam's command any morning. Owner: orchestrator. Trust: earned.
---
# /morning-brief
> Revisit: if calendar access or queue schema changes. · Last touched: 2026-07-07

## Purpose
Start the day oriented in under a minute of reading. This skill is deliberately incapable of side effects — it is the proof-case that scheduled automation is safe here.

## Inputs
- Calendar (read-only via connector).
- Open queue items; receipts landed since the last brief.
- current_priorities.md.

## Steps
1. **Today** — calendar items with times; flag anything needing prep (a Fit Call today → suggest /fit-call-prep if no brief exists yet).
2. **Overnight** — receipts since last brief, one line each; failures or REVISE verdicts first.
3. **Queue** — open items by lane, oldest-first; anything blocked on Liam highlighted.
4. **Top 3** — proposed from current_priorities.md + queue state. Proposals, not commitments.
5. **Output** — short brief delivered to the usual channel; receipt with token block.

## Never
- Write to calendar, queue, or any external system.
- Launch other skills (suggest them by name instead).
- Pad — if it's a quiet day, the brief is short.

## Done when
Brief delivered with today's calendar, overnight receipts, open queue, top 3. Receipt written.
