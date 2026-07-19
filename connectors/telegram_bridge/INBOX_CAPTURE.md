# Olmec Telegram inbox capture — implemented contract
> Revisit: when Telegram inbound types, the canonical inbox, or local voice transcription changes. · Last touched: 2026-07-19

## Routing

The existing Olmec bridge owns capture; no second bot, token, listener, or
launcher exists. Operator messages use `/inbox <text>` or `/capture <text>`.
Forwarded operator content is also an unambiguous capture signal. Existing
`/status`, `/work`, approvals, natural-language Hermes routing, receipts, pilot
reporting, and completion notifications retain their established routes.

Captured text, forwarded text, supported documents (`txt`, `md`, `pdf`,
`docx`, `rtf`, `csv`, `json`, and YAML), and voice audio use
`tools/business_brain_inbox.py` and terminate under
`business_brain:inbox/source_notes/`. Attachments are retained in its
`attachments/` child with a companion intake note. Telegram chat IDs and
forwarded-party identity are not written to the note; a one-way replay identity
prevents duplicates. Capture never calls the queue backend.

## Voice behavior

Audio is always retained when capture succeeds. No proven local speech-to-text
engine is installed on the current host. The bridge therefore records
`transcription_status: unavailable` and says so in the companion note. A local,
no-shell adapter is available only when the operator configures
`AOS_VOICE_TRANSCRIBE_COMMAND` as an argv string containing `{audio}`; stdout is
the transcript. The remaining external dependency is a locally installed and
configured Whisper-compatible transcriber. Cloud STT is never used.

## Safety and acknowledgement

Only operator-authorized chats can enter this route. Filenames are sanitized,
downloads are size/type bounded, paths are containment checked, and files are
published append-only. The ordinary handler sends only `Captured ✓`,
`Already captured ✓`, or a bounded failure reason. Test proof stubs every send
and download; it never contacts Telegram.
