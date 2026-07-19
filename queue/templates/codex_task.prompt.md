# Codex Work Queue Task

PERMISSION MODE — SCOPED LOCAL TASK APPROVED

Do not ask for permission during this scoped local task. Assume approval for local reads, local edits, local file creation, dependency installation, validation commands, local dev-server startup, browser preview, and screenshot capture inside the stated scope.

Do not ask before editing files inside the stated folder. Make the changes, validate, and return the compact closeout.

Stop only for real external/destructive actions.

This task starts in a fresh ephemeral Codex session. Never use `resume`,
`--last`, or a prior transcript. Before 50% context, write a compact
artifact-backed receipt/handoff and end; any continuation starts fresh from
that artifact. Store large logs, screenshots, browser evidence, and verbose
test output as artifacts and retain only summaries plus paths.

Use `context/ACCESS_MODEL.md` as the access model. Use targeted reads/searches. Broad read/search access is allowed when relevant under `context/ACCESS_MODEL.md`. Do not paste or expose secrets.

Codex is for code edits, file-heavy implementation, repo inspection, tests, backend/dashboard patches, connector adapters, and local validation.

## Work Scope

<WORK_SCOPE>

## Work item

- ID: <AOS-ID>
- Owner/agent: <OWNER_OR_AGENT>
- Title: <TITLE>

## Context

<CONTEXT>

## Source references

<SOURCE_REFERENCES>

## Allowed actions

<ALLOWED_ACTIONS>

## Stop conditions

<STOP_CONDITIONS>

## Definition of done

<DEFINITION_OF_DONE>

## Validation

<VALIDATION_COMMANDS_OR_CHECKS>

## Closeout

Return a compact receipt and create or reference a durable receipt after work is complete.
Before exiting successfully, attach the durable receipt and leave the item in
its honest requested terminal status (`human_review`, `done`, `needs_input`, or
`blocked`). The enclosing `codex-run` supervisor will wait for process exit and
reconcile the final structured usage against this exact item/session without
requiring a `done` transition; do not select or infer a different queue item.

Required closeout format:

PASS/NEEDS ATTENTION

Files touched:
- ...

Validation:
- ...

Blockers:
- ...

Next action:
- ...
