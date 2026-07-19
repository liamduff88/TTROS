# Natural-language connector routing
> Revisit: when connector authority changes. · Last touched: 2026-07-17.

For any connector request, route through the local Composio access spine first.

1. Extract the requested toolkit, intent, target, and scope from normal language.
2. Call `python3 connectors/composio_access_adapter.py prepare <toolkit> <intent>` to discover candidate actions.
3. For read/search/status/prepare requests, select the exact action and proceed when requested. For Gmail draft creation, route only to `connectors/gmail_draft_adapter.py` and exact `GMAIL_CREATE_EMAIL_DRAFT`.
4. Never substitute a Gmail send/reply/forward/schedule, update/delete, or label action. Other toolkit writes retain their explicit-action gate.
5. Preview uncertain calls with adapter `run` (dry-run is the default). Actual execution requires `--execute --operator-command`.
6. If live Composio discovery is unavailable, report the blocker. Never treat stale registry evidence as a current connection and never reconnect automatically.

Use the existing Composio spine for every toolkit. The dedicated Gmail draft
adapter is a narrow policy/idempotency layer over that spine, not another API
or OAuth connector.
