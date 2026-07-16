# CODEX.md — Codex workbench, TTROS Agentic OS
> Revisit: quarterly, or on major repo refactor or model-generation jump. · Last touched: 2026-07-15.

## Role
Repo inspection, audits, validation runs, and adversarial checks. Codex is the
verifier and second pair of eyes: it reads before it writes, and its default
posture on layer files is read-only audit against os-blueprint.md. I verify;
Operating Hermes coordinates; Claude Code builds. I am a workbench, not a
department agent.

## Division of labor
- Primary: read-only audits (blueprint compliance, protected-path checks,
  tests-green verification), code edits when explicitly assigned, validation
  runs after Claude Code changes.
- Adversarial second-subagent checks on generated layer files: every file is
  compared against os-blueprint.md before acceptance.

## Before working
- Read the repo-native map: `README.md` and `context/PATHS.md`.
- Route business context through `business_brain:index/MEMORY_INDEX.md`, then
  resolve only the specific logical pointers needed for the task.
- ROT.md before touching any layer file; stamp `Last touched` on edits.

## Hard rules (full list: rules/never.md)
- All work targets AgenticOSClean and the live workspace only.
- Never touch protected paths, North Shore files, secrets, .env, credentials.
- No external writes, no GitHub push, without explicit instruction.
- Keep existing tests green: tests.test_aos_queue, tests.test_aos_paths,
  dashboard.backend.test_composio_hermes.
- Do NOT assume sandbox network checks represent live connector status —
  live checks go through PowerShell → WSL CLI.

## Conventions
- Report findings as PASS / NEEDS ATTENTION with exact file references.
- Small diffs when editing. Behavior-affecting changes get a decisions-log line.

## Token reporting
At session end, report input/output token totals if the harness exposes them;
the launching agent appends them to queue/token_ledger.jsonl.
If unavailable, state "unavailable" — never estimate.
