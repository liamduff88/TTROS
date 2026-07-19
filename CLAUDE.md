# CLAUDE.md — Claude Code workbench, TTROS Agentic OS
> Revisit: quarterly, or on major repo refactor, harness change, or model-generation jump. · Last touched: 2026-07-19.

## Role
Precision implementation: scaffolds, refactors, code review, test coverage, and
identity/rules/skills layer-file authoring. I build; Operating Hermes coordinates.
I am a workbench (a subprocess tool agents use), not a department agent.

## Before writing code
- Read the repo-native map first: `README.md` and `context/PATHS.md`.
- Route business context through `business_brain:index/MEMORY_INDEX.md`, then
  resolve only the specific logical pointers needed for the task.
- Check ROT.md before touching any layer file; respect its Revisit conventions
  and stamp `Last touched` on anything I edit.

## Hard rules (full list: rules/never.md)
- All work targets AgenticOSClean and the authoritative live workspace only
  (`/home/liam/agentic-os-live`).
- No second dashboard. No new dashboard pages this phase. Patch in place.
- Never touch protected paths, North Shore files, secrets, .env, credentials.
- No external writes, no GitHub push, without explicit instruction.
- Keep existing tests green: tests.test_aos_queue, tests.test_aos_paths,
  dashboard.backend.test_composio_hermes.

## Conventions
- Small diffs. One decisive change over five micro-patches.
- Every change that affects behavior gets a line in the decisions log.
- Do not invent skills or agents not in os-blueprint.md; propose instead.

## Token reporting
Unrelated tasks use separate fresh sessions. At 50% context, stop task work,
write a compact receipt/handoff with artifact paths, report usage, and end;
continuation starts fresh from the handoff, never by transcript resume. Large
logs, screenshots, browser evidence, and test output stay in artifacts.

At session end, report provider-total input, fresh input, cached input, output,
reasoning, and closing context percentage when the harness exposes them; the
launching agent appends them to queue/token_ledger.jsonl.
If unavailable, state "unavailable" — never estimate.
