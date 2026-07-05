# Agentic OS Path Convention

- `AOS_ROOT` is the runtime root convention for Agentic OS.
- Code should resolve runtime files from `AOS_ROOT` or root-relative paths.
- New code should not add hardcoded Windows or WSL absolute workspace paths.
- User-facing launch command text may still show Windows or WSL paths when the operator needs to copy or inspect those commands.
- Secrets stay outside git and are re-provisioned during migration.
