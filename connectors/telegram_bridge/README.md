# Telegram Bridge
> Revisit: when Olmec commands or operator routing changes. · Last touched: 2026-07-28.

Minimal secondary dashboard bridge.

Commands:
- /status
- /inbox <text> (alias: /capture; forwarded content is captured directly)
- /connectors
- /work hermes <task>
- /work codex <task>
- /work claude <task>

Token stays local in `.env`. Do not paste it into ChatGPT.

Inbox behavior: `INBOX_CAPTURE.md`. This is the existing Olmec bridge; no
second Telegram bot or listener is used.

Agent work is submitted off the polling thread through the existing backend,
queue, and runner. Telegram update IDs become durable delivery IDs, so a
replayed update reuses its original queue item and cannot start another run.
The intake message is the only acknowledgement; the existing completion path
sends one final closeout with its receipt attachment. `/status`, `/whoami`,
capture, and help handling never invoke an agent.

After slash-command handling, the backend checks one frozen
case-insensitive literal table. `What tasks are open?` is the zero-token open
task reader. The table is deliberately not expanded with semantic patterns:
wording variants fall through to one bounded Hermes `operator-lean` turn.
Conversation and reads do not queue; clear execution may create one item.
