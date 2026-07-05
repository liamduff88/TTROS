# Agentic OS Work Queue v0

Minimal local work movement layer for Agentic OS.

This queue is intentionally boring:

- JSONL/local files only
- no database
- no server
- no scheduler
- no dashboard changes
- no connector calls
- no external writes

Access behavior should reference `context/ACCESS_MODEL.md` instead of repeating long rules in queue items.

## Files

- `queue/work_items.jsonl` stores one JSON work item per line.
- `queue/agent_registry.json` stores local agent names.
- `queue/receipts/` stores optional receipt artifacts.
- `queue/locks/` is reserved for future local lock files.
- `queue/schemas/` documents the JSON shapes.

## Prompt Templates

- `queue/templates/` contains copy/paste Codex, Claude, and receipt templates for scoped queue work.
- `context/ACCESS_MODEL.md` defines the native access model those templates should reference.

## CLI

Run from the repository root:

```bash
python3 tools/aos-queue.py create --title "Review packet" --requested-by liam --owner codex
python3 tools/aos-queue.py list
python3 tools/aos-queue.py show AOS-2026-0001
python3 tools/aos-queue.py claim AOS-2026-0001 codex
python3 tools/aos-queue.py release AOS-2026-0001 --status agent_todo
python3 tools/aos-queue.py status AOS-2026-0001 human_review
python3 tools/aos-queue.py receipt AOS-2026-0001 queue/receipts/AOS-2026-0001.md --status done
python3 tools/aos-queue.py next codex
```

Approved statuses:

- `inbox`
- `agent_todo`
- `agent_working`
- `needs_input`
- `human_review`
- `done`
- `blocked`
- `cancelled`
