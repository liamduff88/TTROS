# NEVER
> Revisit: monthly review pass. · Last touched: 2026-07-07.

1. Never send, push, mutate, delete, archive, or trigger any external side
   effect without an explicit command naming that action.
2. Never touch North Shore files from this system.
3. Never route through old Ubuntu, old Hermes, old vaults, ZPC, legacy_harvest.
4. Never import old runtime state.
5. Never create a second dashboard or new dashboard pages this phase.
6. Never inspect, print, or commit secrets, .env, tokens, or credentials.
7. Never invent token numbers, sources, or completion claims.
8. Never modify protected paths (operating_context/protected_paths.md,
   mirrored in PROTECTED_PATHS.md).
9. Never blend two clients' data in one output.
10. Never contact a lead that failed the email-safe / CASL check.
11. Never mutate CRM/Gmail/Calendar/Drive/LinkedIn/GitHub remote without
    explicit per-action approval.
12. Never delete during maintenance — report and recommend only.

## Pointers
- Enforcement: hooks/pre_external_action.md · hooks/protected_path_check.md ·
  hooks/secret_exposure_check.md · hooks/client_isolation_check.md
- Companion: rules/always.md
