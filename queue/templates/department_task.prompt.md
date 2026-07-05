# Operating Hermes Queue Task

PERMISSION MODE — SCOPED LOCAL TASK APPROVED

Do not ask for permission during this scoped local task. Assume approval for local reads, local edits, local file creation, dependency installation, validation commands, local dev-server startup, browser preview, and screenshot capture inside the stated scope.

Do not ask before editing files inside the stated folder. Make the changes, validate, and return the compact closeout.

Stop only for real external/destructive actions.

Use `context/ACCESS_MODEL.md` as the access model. Use targeted reads/searches. Broad read/search access is allowed when relevant under `context/ACCESS_MODEL.md`. Do not paste or expose secrets.

This is a manual Operating Hermes prompt copied from a queue item. Do not automatically launch Hermes, Codex, Claude, connectors, Telegram, schedulers, servers, databases, autonomous loops, or external actions.

## Work item

- ID: <AOS-ID>
- Title: <TITLE>
- Owner: <OWNER_OR_AGENT>
- Status: <STATUS>

## Context

<CONTEXT>

## Source references

<SOURCE_REFERENCES>

## Required local references

- `queue/agent_registry.json`
- `context/ACCESS_MODEL.md`
- `queue/templates/receipt.prompt.md`
<CARD_REFERENCE>

## Allowed actions

<ALLOWED_ACTIONS>

## Stop conditions

<STOP_CONDITIONS>

## Definition of done

<DEFINITION_OF_DONE>

## Operating Hermes routing

<ROUTING_INSTRUCTION>

Do not create bureaucracy. Read only the queue item, registry, access model, receipt template, relevant card/context, and source refs needed to complete or route this item well.

## Department card

<CARD_CONTENT>

## Manual launch

Paste this prompt into Operating Hermes manually. Do not automatically launch anything from dashboard prompt copy.

Suggested manual launch from PowerShell only when the operator chooses to run it:

cd "C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live"

wsl -d AgenticOSClean --user liam -- bash -lc 'export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$HOME/.composio:$PATH"; cd "/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live"; aos-hermes'

## Receipt

Return a compact receipt and create or reference a durable receipt after work is complete using `queue/templates/receipt.prompt.md`.

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

Token usage:
- available / unavailable from current CLI output
