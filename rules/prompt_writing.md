# Prompt writing — worker work orders

> Revisit: when the queue prompt builder, Codex template, or decomposition contract changes. · Last touched: 2026-10-25

One writing standard for every prompt handed to a worker step. It is applied by Operating
Hermes when it writes a stage's `context` and `definition_of_done`, by David when it fills an
`execution_handoff` (`objective`, `source_refs`), and deterministically by the queue builder
(`_queue_actual_run_prompt`, `queue/templates/codex_task.prompt.md`, and the Context
Assembler's technical-worker mode). No extra model call writes or rewrites prompts.

## A work order has six parts, once each

1. **Objective** — one sentence: what must be true when the step is finished.
2. **Scope** — what to inspect or change, and what not to touch. Name files, folders and item IDs.
3. **Pointers** — paths to the authoritative spec, code, receipts or artifacts. Point; do not
   paste. Workers can read the repository.
4. **Permissions** — the item's allowed actions and stop conditions. The launcher adds the
   standard permission header once; do not restate it.
5. **Validation** — the specific check that proves done: a test path, command or artifact.
6. **Closeout** — the receipt shape, once.

## Leave out of technical steps

Business workflows and playbooks the step does not name, conversation history, prior-run
narration, provenance hashes (the assembly artifact keeps them), repeated boilerplate, and
empty N/A sections. Put large evidence in an artifact and pass its path.

## Always keep

Client scope and isolation, safety stop conditions, evidence requirements the definition of
done asks for (exact command, exit status, captured output), and the token-usage line.

## Size and splitting

Keep a step's context to about 150 words. This is a target, not a byte ceiling. Split work into
separate stages when it needs unrelated expertise or many tool calls: each stage runs in a fresh
Codex session with its own 500,000-token fuse and its own model tier.

## Model and effort

Chosen per step from `queue/model_routes.json` (`codex_selection`) by complexity and the cost
dial. Do not ask for a model in prose. The operator override is the item tag
`budget:light|standard|heavy`.
