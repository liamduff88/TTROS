# Work Queue Prompt Templates

These are copy/paste workbench templates for turning an Agentic OS Work Queue item into a scoped Codex or Claude prompt.

They do not launch agents, do not replace Hermes, and do not change queue state automatically. The operator or future tooling can use them to prepare a workbench prompt from a queue item, then attach the result back to the queue.

Use:

- `codex_task.prompt.md` for Codex-scoped implementation, inspection, edits, and validation.
- `claude_task.prompt.md` for Claude-scoped polish, refactors, precision implementation, and complex assigned work.
- `hermes_dispatcher.prompt.md` for a lightweight Operating Hermes queue inspection and dispatcher recommendation.
- `revenue_linkedin_outreach.prompt.md` for Revenue-owned LinkedIn relationship outreach prep without external action.
- `receipt.prompt.md` for the durable work receipt shape.

Receipts should be attached back to the queue with:

```bash
python3 tools/aos-queue.py receipt <AOS-ID> <receipt-path> --status <status>
```

The access model is `context/ACCESS_MODEL.md`. Templates should reference that file instead of repeating long permission rules.
