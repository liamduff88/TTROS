# ALWAYS
> Revisit: monthly review pass. · Last touched: 2026-07-08.

Operator-approved rule set (pruned 2026-07-08). Absolutes an LLM invented and
the operator never approved were removed; see rules/never.md for the hard
prohibitions.

1. Every meaningful queue item leaves a receipt: lane, profile, model requested,
   model confirmed, tokens (exact / ~estimate / "unavailable" — never invented),
   artifact paths.
2. Every external-facing draft states its outreach basis (CASL block for leads).
3. Every wiki ingest appends one line to _substrate.wiki/log.md.
4. Every new file in the substrate carries a Revisit: or Expires: line.
5. Deterministic script first; cheap model second; strong model only on the
   two escalation triggers (rules/escalation.md). Model spend happens on
   explicit operator action or an explicit Hermes address — never silently
   from typing, viewing, or searching.
6. State sources for every factual claim in client-facing output.
7. Keep each client in its own context. One client, one thread, one folder
   (rules/client_data_boundaries.md).
8. Verify work against its completion contract before reporting done
   (rules/completion_contract.md).
9. Live connector checks go through PowerShell → WSL CLI, never assumed.
10. When in doubt about scope: stop, write the question into the receipt, ask.
11. Internal sends are unrestricted: Telegram to the operator, and AgentMail
    to the operator's Time to Revenue address or any internal agent inbox —
    enforced by the recipient allowlist in queue/notifications.json.
12. Review/blocked/needs_input items surface in the originating channel and
    the Needs Me rail immediately; unanswered after the configured window
    (default 10 min) escalates to Telegram via the existing bridge send path.

## Pointers
- Enforcement: hooks/receipt_completeness_check.md · hooks/token_budget_check.md
- Companion: rules/never.md
