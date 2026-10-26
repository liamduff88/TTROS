# Prompt writing — worker work orders

> Revisit: when the queue prompt builder, Codex template, or decomposition contract changes. · Last touched: 2026-10-25

One writing standard for every prompt handed to a worker step. It is applied by Operating
Hermes when it writes a stage's `context` and `definition_of_done`, by David when it fills an
`execution_handoff` (`objective`, `source_refs`), and deterministically by the queue builder
(`_queue_actual_run_prompt`, `queue/templates/codex_task.prompt.md`, and the Context
Assembler's technical-worker mode, which also serves direct Dashboard Codex requests). No extra
model call writes or rewrites prompts.

## A work order is 5–10 lines, one part per line

1. **Task** — the item ID and title.
2. **Context** — what to inspect or change, and what not to touch. Name files, folders and item IDs.
3. **Pointers** — paths to the authoritative spec, code, receipts or artifacts. Point; do not
   paste. Workers can read the repository. Omit the line when there are none.
4. **Done when** — what must be true at the end, including the check that proves it.
5. **Allowed / stop** — the item's allowed actions and stop conditions, once.
6. **Closeout** — where the result goes and the reply labels, once.

The launcher adds the standard permission header once. More lines only when the step genuinely
needs them (a named playbook, a cited item's current status, a run-prompt file).

## Enforced by the runtime, not restated in prose

Fresh ephemeral session and no resume (`--ephemeral`, one real `thread.started` ID), the
per-session 500,000-token fuse, token accounting, model and effort, approval policy, and Codex's
no-push rule (`NO_PUSH_GIT_ENV` in `tools/aos_codex_policy.py`). The approved closeout outside
Codex commits and pushes.

## Leave out of technical steps

Business workflows and playbooks the step does not name, conversation history, prior-run
narration, relevance-matched receipts, the global boundary block, provenance and assembly
metadata (the assembly manifest keeps them), repeated boilerplate, and N/A sections. Put large
evidence in an artifact and pass its path.

## Always keep

Client scope and isolation, the item's stop conditions, evidence requirements the definition of
done asks for (exact command, exit status, captured output), and the token-usage reply label.

## Size and splitting

Keep a step's context to about 150 words. This is a target, not a byte ceiling. Split work into
separate stages when it needs unrelated expertise or many tool calls: each stage runs in a fresh
Codex session with its own 500,000-token fuse and its own model tier.

## Model and effort

Chosen per step from `queue/model_routes.json` (`codex_selection`) by complexity and the cost
dial. Do not ask for a model in prose. The operator override is the item tag
`budget:light|standard|heavy`.
