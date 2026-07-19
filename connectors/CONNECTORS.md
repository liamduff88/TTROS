# Agentic OS Connectors

> Revisit: when connector authority or the live Composio catalog changes. · Last touched: 2026-07-17.

Composio is the primary connector spine. All connector work goes through `connectors/composio_access_adapter.py` first; do not build separate app APIs where Composio supplies the toolkit.

Mode: operator-command enabled.

- Read/search/status/prepare may run when requested.
- Gmail draft creation may run only through `gmail_draft_adapter.py`, which
  allowlists exactly `GMAIL_CREATE_EMAIL_DRAFT` and enforces idempotency.
- Gmail send, reply, forward, schedule-send, draft deletion/update, and
  message/label mutation are forbidden to Agentic OS.
- Send/write/book/push/publish/delete/mutate may run only when Liam explicitly commands the specific action.
- Use `prepare <toolkit> <intent>` to discover exact Composio actions, `execute ACTION --get-schema` to inspect inputs, and guarded adapter `run` for preview or execution.
- `run` defaults to Composio dry-run. Actual execution requires `--execute --operator-command`.
- Shared callers can inspect any tool with `tool-info TOOL_SLUG` and execute it with `tool-run TOOL_SLUG '<json_args>'`.
- `tool-run` directly executes read/search/status/get/list/fetch/info tools.
  Gmail non-read actions are rejected before Composio is called; other toolkit
  mutation slugs retain the explicit `--confirmed` gate.

Live `connections list` JSON verifies active/current accounts for Google Sheets, Instagram, Google Maps, YouTube, Google Docs, Agent Mail, Reddit, LinkedIn, GitHub, Google Drive, Google Calendar, and Gmail. Facebook (2), WhatsApp, Apollo, and duplicate Google Maps, YouTube, and Google Drive connections remain recorded separately as expired.

The adapter can fall back to this verified current snapshot during an intermittent CLI transport failure. Action discovery is currently pending transport recovery. No dashboard backend route is wired in this pass. See `composio_access_spine.md` and `composio_tool_registry.json`.
