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
- `queue/model_routes.json` stores lane/profile/provider/model route metadata for queue runs, receipts, and token ledgers. Hermes receives explicit `--provider` and `--model` flags only when both values are real configured values; placeholders such as `configured externally`, `inherit_default`, `default`, `unavailable`, `TBD`, `—`, empty string, or `null` keep the default Hermes route.
- `queue/lane_profiles.json` documents prior lane profile requests only. Queue execution does not call `hermes profile use` and does not use native Hermes profile switching.
- `queue/profiles/` documents the manual `aos-*` Hermes profile status without storing secrets or mutating Hermes config.
- `queue/receipts/` stores optional receipt artifacts.
- `queue/locks/` is reserved for future local lock files.
- `queue/schemas/` documents the JSON shapes.

## Prompt Templates

- `queue/templates/` contains copy/paste Codex, Claude, and receipt templates for scoped queue work.
- `context/ACCESS_MODEL.md` defines the native access model those templates should reference.

## Receipt artifact policy

- `queue/receipts/*.md` files are local runtime proof trail by default.
- Smoke-test receipts should not be committed.
- Real receipts may be committed only when intentionally promoted as durable project proof or handoff.
- `queue/receipts/.gitkeep` remains tracked so the folder exists.
- Do not include secrets, tokens, customer private data, raw OAuth values, Telegram IDs, or connector credentials in receipts.

## CLI

Run from the repository root:

```bash
python3 tools/aos-queue.py create --title "Review packet" --requested-by liam --owner codex
python3 tools/aos-queue.py list
python3 tools/aos-queue.py show AOS-2026-0001
python3 tools/aos-queue.py claim AOS-2026-0001 codex
python3 tools/aos-queue.py release AOS-2026-0001 --status agent_todo
# Status update syntax: positional status, no --status flag.
python3 tools/aos-queue.py status AOS-2026-0001 human_review
# Receipt attach syntax: positional receipt path; optional --status updates the item at the same time.
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
