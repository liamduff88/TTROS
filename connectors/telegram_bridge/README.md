# Telegram Bridge

Minimal secondary dashboard bridge.

Commands:
- /status
- /inbox <text> (alias: /capture; forwarded content is captured directly)
- /connectors
- /hermes <task>
- /codex <task>
- /claude <task>

Token stays local in `.env`. Do not paste it into ChatGPT.

Inbox behavior: `INBOX_CAPTURE.md`. This is the existing Olmec bridge; no
second Telegram bot or listener is used.
