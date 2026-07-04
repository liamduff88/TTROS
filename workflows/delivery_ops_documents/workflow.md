# Delivery / Operations Document Workflow

Purpose: turn notes, transcripts, or build outputs into useful internal and client-ready documents while keeping final delivery under Liam approval.

## Inputs

Place source material in `input/`:

- Meeting notes.
- Transcript excerpts.
- Build outputs.
- Client context approved for use.
- Existing decisions, blockers, and acceptance criteria.

## Draft-First Steps

1. Identify the source notes, transcript, or build output.
2. Decide which document type is needed: SOP, implementation plan, client-ready summary, founder ops summary, or a combination.
3. Extract facts, decisions, blockers, dependencies, and open questions.
4. Draft the requested document in `output/`.
5. Add acceptance criteria where the work requires completion checks.
6. Add blockers and decisions needed.
7. Write a receipt in `receipts/`.
8. Route the draft for human review before sending or using it to change client systems.

## Document Types

- SOP creation: convert repeatable operational steps into a clear procedure with owner, trigger, steps, quality checks, and exception handling.
- Implementation plan creation: convert a goal or build output into phases, tasks, owners, dependencies, risks, and acceptance criteria.
- Client-ready summary creation: convert internal notes into a concise client-facing update that avoids private internal reasoning.
- Founder ops summary creation: convert messy operating context into priorities, decisions, blockers, and next actions.

## Acceptance Criteria

Each output should include:

- Source material used.
- Intended audience.
- Scope.
- Clear next action.
- Blockers or decisions needed.
- Human review status.

## Rules

- Draft-first: create documents and review notes only.
- Do not send client deliverables without Liam approval.
- Do not change client systems without Liam approval.
- Do not invent commitments, timelines, owners, or client facts.
- Do not modify dashboard, Telegram, Hermes, queue, connectors, backend routes, or pilot-specific files.

## Receipt Format

Create a receipt in `receipts/YYYY-MM-DD_document_name_receipt.md`:

```markdown
# Delivery / Operations Document Receipt

- Source material:
- Document type:
- Output path:
- Intended audience:
- Acceptance criteria:
- Blockers:
- Decisions needed:
- Human review status:
- Delivery status: not sent by workflow
- Client system status: not changed by workflow
```
