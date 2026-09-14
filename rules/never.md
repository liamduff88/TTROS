# NEVER
> Revisit: monthly review pass. · Last touched: 2026-09-13.

Operator-approved hard prohibitions (pruned 2026-07-08). "Never send Telegram"
and "no model calls on parse" style LLM-invented absolutes are removed —
internal sends are governed by rules/always.md #11–12; model spend by #5.

1. Never take an AGENT-INITIATED THIRD-PARTY external side effect (clients,
   prospects, LinkedIn, anyone outside the system) without typed per-action
   confirmation naming that action and target. Liam's exact command is that
   confirmation; internal delivery per allowlist is exempt (always.md #11, #13).
2. Never inspect or modify North Shore application code, client data, or
   workspace internals unless Liam explicitly scopes North Shore work.
   Scoped runtime/supervision maintenance may touch only the minimum
   infrastructure required to operate the existing service. Credential
   and protected-config contents remain protected unless Liam explicitly
   scopes them (#6).
3. Never route through old Ubuntu, old Hermes, old vaults, ZPC, legacy_harvest,
   or any legacy runtime path.
4. Never import old runtime state.
5. Never create a second dashboard — reshape the existing app only.
6. Never inspect, print, or commit secrets, .env, tokens, or credentials.
7. Never invent token numbers, progress percentages, sources, or completion
   claims.
8. Never modify protected paths (operating_context/protected_paths.md,
   mirrored in PROTECTED_PATHS.md).
9. Never blend two clients' data in one output.
10. Never contact a lead that failed the email-safe / CASL check.
11. Never mutate CRM/Gmail/Calendar/Drive/LinkedIn without explicit per-action
    approval. An exact Liam command supplies that approval; an unambiguous
    booking agreed in supplied meeting/transcript context does too. Ambiguous
    Calendar date/time/participants/timezone requires one clarification.
    Routine Git commits and normal pushes of completed, proven TTROS source
    work follow CODEX.md's completion-boundary rule.
12. Never delete during maintenance — report and recommend only.
13. Never edit Telegram bridge FILES (read-only process/log status is fine;
    Phase B notifications use the existing send path only).
14. Never mutate the Hermes global/default profile.
15. Never make queue schema changes that are not additive.

## Pointers
- Enforcement: hooks/pre_external_action.md · hooks/protected_path_check.md ·
  hooks/secret_exposure_check.md · hooks/client_isolation_check.md
- #2 invariant: North Shore is a separate business; its code, client data
  and workspace must never be reached incidentally, and operating the
  service is not permission to read what it holds. Revisit #2 if North
  Shore moves to its own repo or gains its own operator.
- Companion: rules/always.md
