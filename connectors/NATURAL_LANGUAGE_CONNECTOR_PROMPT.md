# Natural-language connector routing

For any connector request, route through the local Composio access spine first.

1. Extract the requested toolkit, intent, target, and scope from normal language.
2. Call `python3 connectors/composio_access_adapter.py prepare <toolkit> <intent>` to discover candidate actions.
3. For read/search/status/draft/prepare requests, select the exact action and proceed when requested.
4. For send/write/book/push/publish/delete/mutate requests, proceed only when Liam explicitly commands the specific external action. There is no blanket no-write rule.
5. Preview uncertain calls with adapter `run` (dry-run is the default). Actual execution requires `--execute --operator-command`.
6. If live Composio discovery is unavailable, report the blocker. Never treat stale registry evidence as a current connection and never reconnect automatically.

Use one generic Composio adapter for LinkedIn, YouTube, Gmail, Calendar, Drive, Docs, Sheets, GitHub, Reddit, Instagram, Google Maps, Agent Mail, and every other registry toolkit. Do not route to separate direct APIs.
