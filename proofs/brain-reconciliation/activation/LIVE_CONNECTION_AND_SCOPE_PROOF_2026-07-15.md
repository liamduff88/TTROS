# Live connection and mailbox scope proof
> Expires: when the Gmail connection or authorized capture scope changes. · Last touched: 2026-07-15.

Result: **PASS**.

- Gmail toolkit connected: **yes**.
- Required read-only actions available: **yes** — profile, history, metadata-only bootstrap, and one-message metadata.
- Safe profile probe returned a history checkpoint; checkpoint SHA-256 was `ae733ec7fddd841f19cf11a5d11efc6ea6242ec6458caff9082823a87aca2bf4` at verification.
- Mailbox identity value emitted: **no**. Account ID and connection ID emitted: **no**.
- Connection mutation performed: **no**.
- Credential material opened: **no**.
- OAuth/relink performed: **no**.
- Mailbox alias: `me`; label scope: `INBOX`; excluded labels: `SPAM`, `TRASH`, `SENT`; direction: inbound only.
- Primary delta: `GMAIL_LIST_HISTORY` with `history_types=[messageAdded]`, `label_id=INBOX`, bounded pagination.
- Bootstrap: `GMAIL_FETCH_EMAILS`, `include_payload=false`, `include_spam_trash=false`, `label_ids=[INBOX]`, exact 24-hour-or-less timestamp boundary, maximum 100 rows.
- Individual follow-up: `GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID`, `format=metadata` only.
- Production and receipt-covered diagnostic action counts through the automatic 23:15 cycle: profile 9, bootstrap 4, one-message metadata 6, history 3. Mutation action count: zero.

No `whoami`, account listing, credential inspection, connection mutation, Calendar, Drive, CRM, or attachment action was used.

Token usage: no agent invocation.
