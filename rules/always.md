# ALWAYS
> Revisit: monthly review pass. · Last touched: 2026-08-17.

Operator-approved rule set (pruned 2026-07-08). Absolutes an LLM invented and
the operator never approved were removed; see rules/never.md for the hard
prohibitions.

1. Every meaningful queue item leaves a receipt: lane, profile, model requested,
   model confirmed, tokens (exact / ~estimate / "unavailable" — never invented),
   artifact paths.
2. Every external-facing draft states its outreach basis (CASL block for leads).
3. Every approved Business Brain ingest uses canonical
   `business_brain:<relative-path>` references and keeps
   `business_brain:index/MEMORY_INDEX.md` navigable.
4. Every new file in the substrate carries a Revisit: or Expires: line.
5. Deterministic script first where it can complete the work. Model calls use
   the one visible `light|standard|heavy` cost dial and record the actual model;
   no hidden rule may silently downgrade it. Model spend happens on explicit
   operator action or an explicit Hermes address — never silently from typing,
   viewing, or searching.
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

## Efficient-operation doctrine

The unit of work is the requested practical outcome, not maximum inspection or proof. For routine operations:

1. Use deterministic/local mechanisms whenever they can correctly produce the answer or perform the operation.
2. Call a model only for genuine interpretation, judgment, synthesis, or language reasoning.
3. Do not repeatedly prove established platform invariants during normal use.
4. Distinguish FIRST BUILD / REPAIR (focused tests plus representative end-to-end proof) from ROUTINE USE (narrow integrity/result verification only).
5. Reuse existing evidence and live contracts instead of rediscovering repository history.
6. Avoid broad repository reads, full suites, multi-agent investigation, and extensive proof artifacts unless failure evidence or change scope requires them.
7. Optimize for useful outcome per token, not maximum context.
8. Routine source/data operations use existing deterministic capabilities instead of invoking Codex to rediscover the system.
9. Load only the smallest relevant knowledge into model context.
10. Complete and proven source changes are logically committed and normally pushed automatically under the current Git rule.

Protected boundaries and review-tier promotion rules remain unchanged.

## Pointers
- Enforcement: hooks/receipt_completeness_check.md · hooks/token_budget_check.md
- Companion: rules/never.md
