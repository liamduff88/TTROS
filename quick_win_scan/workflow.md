---
workflow: quick_win_scan
skill: skills/quick_win_scan/SKILL.md
path: workflows/quick_win_scan/workflow.md
lane: delivery
profile: aos-delivery
trust: watch
---
# workflow: quick_win_scan — deliver one CA$350 Quick-Win Scan
> Revisit: when quick_win_scan SKILL.md or the offer changes. · Last touched: 2026-07-07.

## Trigger
Queue item with: client entity page, Liam's intake notes/transcript, completion contract. Refuse without all three.

## Completion contract (default)
- **Done** = short report artifact in `output/`: current state → one bottleneck (ROI-lever tagged) → why it matters → one fix (DIY / done-with-you / done-for-you labelled) → first step → soft upgrade path. Assumptions labelled. Receipt written. 48h delivery target where practical.
- **Allowed unprompted** = read client entity page + intake notes, draft the report.
- **Stop conditions** = notes span multiple workflows (ask Liam which one); missing entity page; anything that would blend another client's data (rules/client_data_boundaries.md).

## Run
1. Open queue item; confirm inputs + contract; confirm client-isolation folder.
2. Execute skill steps 1–5 (confirm scope → map → diagnose → prescribe → report).
3. Write report to `workflows/quick_win_scan/output/Q-YYYY-NNNN_quick_win_scan.md`.
4. Update client entity page; write receipt with token breakdown.
5. Coordinator appends run_ledger + token_ledger at done-transition.

## Never
- More than one workflow or more than one headline bottleneck (that's the CA$750 assessment).
- Unlabelled assumptions or ROI numbers without evidence.
- Start implementation inside the scan.
- Reuse another client's data or examples.

## Verifier check
Exactly one workflow, one tagged bottleneck, one next step; assumptions labelled; receipt complete.
