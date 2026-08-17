# CODEX.md — Codex workbench, TTROS Agentic OS
> Revisit: quarterly, or on major repo refactor, Codex CLI change, or model-generation jump. · Last touched: 2026-08-17.

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
- Routine completed and proven TTROS source work is logically committed and
  normally pushed to the authoritative existing Git remote at completion;
  separate Liam approval is not required.
- Stage only proven task source changes; preserve unrelated or unfinished work
  and exclude credentials, secrets, generated/runtime data, and protected
  material. Never force-push or rewrite shared history, and do not clean,
  reset, or stash unrelated work. Explicit `do not commit` or `do not push`
  instructions override this default; unresolved remote divergence is a blocker.
- Keep existing tests green: tests.test_aos_queue, tests.test_aos_paths,
  dashboard.backend.test_composio_hermes.
- Do NOT assume sandbox network checks represent live connector status —
  live checks go through PowerShell → WSL CLI.

## Conventions
- Report findings as PASS / NEEDS ATTENTION with exact file references.
- Small diffs when editing. Behavior-affecting changes get a decisions-log line.
- Apply `rules/always.md`'s efficient-operation doctrine: focused proof for a
  first build or repair; narrow result verification for routine use. Do not
  rediscover established platform invariants or load unrelated context.

## Token reporting
Every unrelated task starts a separate fresh ephemeral session. Resume is never
implicit. Large logs, screenshots, browser evidence, and test output stay in
artifacts, not prompts. Automatic compaction may preserve a long task in the
same session; it must not remove assembled context required to finish it.

At session end, report provider-total input, fresh input, cached input, output,
reasoning, and closing context percentage when the harness exposes them; the
launching agent appends them to queue/token_ledger.jsonl. The shared 500,000-
token work-item/session fuse is the only token breaker; 50% and 80% are visible
informational events.
If unavailable, state "unavailable" — never estimate.
