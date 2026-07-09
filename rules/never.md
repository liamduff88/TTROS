# NEVER
> Revisit: monthly review pass. · Last touched: 2026-07-08.

Operator-approved hard prohibitions (pruned 2026-07-08). "Never send Telegram"
and "no model calls on parse" style LLM-invented absolutes are removed —
internal sends are governed by rules/always.md #11–12; model spend by #5.

1. Never take a THIRD-PARTY external side effect (clients, prospects, LinkedIn,
   anyone outside the system) without typed per-action confirmation naming
   that action. Internal sends per allowlist are exempt (always.md #11).
2. Never touch North Shore files from this system.
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
11. Never mutate CRM/Gmail/Calendar/Drive/LinkedIn/GitHub remote without
    explicit per-action approval. Codex never pushes to git.
12. Never delete during maintenance — report and recommend only.
13. Never edit Telegram bridge FILES (read-only process/log status is fine;
    Phase B notifications use the existing send path only).
14. Never mutate the Hermes global/default profile.
15. Never make queue schema changes that are not additive.

## Pointers
- Enforcement: hooks/pre_external_action.md · hooks/protected_path_check.md ·
  hooks/secret_exposure_check.md · hooks/client_isolation_check.md
- Companion: rules/always.md
