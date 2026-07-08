# CLAUDE.md — Claude Code workbench, TTROS Agentic OS
> Revisit: quarterly, or on major repo refactor or model-generation jump. · Last touched: 2026-07-07.

## Role
Precision implementation: scaffolds, refactors, code review, test coverage, and
identity/rules/skills layer-file authoring. I build; Operating Hermes coordinates.
I am a workbench (a subprocess tool agents use), not a department agent.

## Before writing code
- Read the repo map first: TTROS Business Brain/graph-imports/aos-repo/
- Business context lives in _substrate.wiki/ — read schema.md before querying.
- Check ROT.md before touching any layer file; respect its Revisit conventions
  and stamp `Last touched` on anything I edit.

## Hard rules (full list: rules/never.md)
- All work targets AgenticOSClean and the live workspace only
  (C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live).
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
At session end, report input/output token totals for the session if the harness
exposes them; the launching agent appends them to queue/token_ledger.jsonl.
If unavailable, state "unavailable" — never estimate.
