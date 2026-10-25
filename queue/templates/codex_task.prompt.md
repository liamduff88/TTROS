# Codex task

PERMISSION MODE — SCOPED LOCAL TASK APPROVED

Do not ask for permission during this scoped local task. Assume approval for local reads, local edits, local file creation, dependency installation, validation commands, local dev-server startup, browser preview, and screenshot capture inside the stated scope.

Do not ask before editing files inside the stated folder. Make the changes, validate, and return the compact closeout.

Stop only for real external/destructive actions.

Work order shape: `rules/prompt_writing.md`. Access model: `context/ACCESS_MODEL.md`. This runs in one fresh ephemeral Codex session with its own 500,000-token fuse; never resume a prior session.

## Work item

- ID: <AOS-ID>
- Title: <TITLE>

## Objective

<DEFINITION_OF_DONE>

## Scope

<CONTEXT>

## Pointers

<SOURCE_REFERENCES>

## Permissions

Allowed actions:
<ALLOWED_ACTIONS>

Stop and report instead of:
<STOP_CONDITIONS>

## Validation

<VALIDATION_COMMANDS_OR_CHECKS>

## Closeout

Store large logs and test output as artifacts; return summaries and paths. Attach a durable receipt and leave <AOS-ID> in its honest status (`human_review`, `done`, `needs_input`, or `blocked`); the `codex-run` supervisor reconciles this session's usage against this item.

PASS/NEEDS ATTENTION

Files touched:
- ...

Validation:
- ...

Blockers:
- ...

Next action:
- ...

Token usage:
- available / unavailable from current CLI output
