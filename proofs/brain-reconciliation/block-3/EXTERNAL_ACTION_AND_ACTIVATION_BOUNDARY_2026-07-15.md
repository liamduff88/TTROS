# Block 3 external-action and activation boundary
> Expires: only at Liam's explicit live-capture activation decision. · Last touched: 2026-07-15.

Result: **PASS — dark and disabled**.

- Runtime control: `live_capture_enabled=false`, `kill_switch=false`.
- Separate activation records present: 0.
- Live adapter default: `no_live=true`.
- Live executor calls: 0.
- Live Gmail/Calendar metadata, body, thread, attachment, or event reads: 0.
- Connector links/relinks, credentials, OAuth, and connector mutations: 0.
- Live classifier/model calls: 0.
- Sends, replies, forwards, bookings, posts, messages, CRM/Drive mutations: 0.
- Recurring polling or scheduled capture jobs created/activated: 0.
- Auto-continue whitelist runtime entries/configuration: 0.
- Deployment, commit, and push: 0.

The adapter exposes only `GMAIL_GET_PROFILE`, `GMAIL_LIST_HISTORY`, and the
guarded metadata-only timestamp fallback contract. Tests prove the kill switch
prevents provider activity and that all three independent live guards are
required. Stage 3 exposes no external-action method and every proposal records
`external_actions_allowed=false`.

Whitelist governance is recorded in `context/MEMORY_PROMOTION_POLICY.md` with
the adopted observation, false-positive, binding, idempotency, kill-switch,
receipt, per-rule decision, and forbidden-category requirements. Nothing is
activated.

Token usage: no agent invocation.
