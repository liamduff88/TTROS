# Prospect Status Vocabulary
> Revisit: if the touch cadence or funnel stages change. · Last touched: 2026-07-16
> Governs the `status` field in `queue/prospects.jsonl` (schema: `queue/prospects_schema.json`).

## Lifecycle
```text
identified → drafted → sent → touch_2 → touch_3 →
replied_positive | replied_negative | no_response →
call_booked → fit_call_done → offer_sent → won | lost | nurture
```
Side states (enter from anywhere): `rejected` (failed gates pre-send),
`do_not_contact` (requested or CASL-required — permanent unless Liam
overrides with a new lawful basis), `withdrawn` (connection request
pulled after 7 days pending).

## Definitions and transition rules
| Status | Means | Set by | Rule |
|---|---|---|---|
| identified | Evidenced, scored, ledger row exists | daily run | Duplicate + do-not-contact check passed first |
| drafted | Outreach drafts exist, awaiting Liam | daily run | Normal initial state for a completed daily-run candidate; never auto-advances |
| sent | Liam sent touch 1 | Liam log | `next_touch_due = +4 days` |
| touch_2 | Follow-up 1 sent | Liam log | `next_touch_due = +5 days` (day 9) |
| touch_3 | Final touch sent (InMail variant allowed for A-tier) | Liam log | `next_touch_due = null`; no touch 4, ever |
| replied_positive | Any reply worth a conversation | Liam log | Route to `/fit-call-prep` |
| replied_negative | Decline / not now | Liam log | If "stop contacting" → `do_not_contact` |
| no_response | 7+ days after touch_3 | weekly review | Terminal for cycle; eligible for future re-signal only |
| call_booked / fit_call_done / offer_sent | Self-evident | Liam log | Existing fit_call_prep / proposal_prep skills take over |
| won / lost / nurture | Outcome | Liam log | `nurture` = real future potential with a stated reason |
| withdrawn | Pending request pulled at 7 days | daily run flags, Liam acts | Protects account health |

## Cadence constants (cycle 1)
Touch days: 0 / +4 / +9. Pending-request withdrawal: 7 days. Hard cap:
3 touches (V4.1). First-touch default: `noted_request` (Premium active);
flip config to `blank_request` + post-acceptance DM if Premium lapses.

## Logging discipline
Every line is a full snapshot. The normal daily workflow atomically accepts
and drafts a candidate, so its initial line is `drafted`; `identified` is
reserved for discovery-only imports. Append one new snapshot per later state
change on the same day as the event. Never rewrite history. The weekly review
flags stale statuses; analytics are only as honest as the log.
