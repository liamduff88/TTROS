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
- `queue/lane_profiles.json` maps a lane to its requested/fallback Hermes profile. On the done-transition the coordinator resolves lane→profile from this file and performs a read-only `hermes profile show` probe to record whether native switching is possible. It never calls `hermes profile use` (that is prohibited for queue routing) — when a profile has no configured model, the coordinator records the reason and falls back to the default route.
- `queue/profiles/` documents the manual `aos-*` Hermes profile status without storing secrets or mutating Hermes config.
- `queue/run_ledger.jsonl` is the master per-run record (`run_ledger_schema.json`); one line appended per item at done-transition.
- `queue/token_ledger.jsonl` is the append-only token-usage ledger (`token_ledger_schema.json`); one line per completed receipt's `token_usage` block. Numbers come from harness/API usage only — unreportable components are listed under `unavailable`, never estimated.
- `queue/rollups/` holds weekly rollups produced by `scripts/token_rollup.py` (dashboard-ready JSON, no front end).
- `queue/receipts/` stores optional receipt artifacts; the coordinator writes a `<id>.token_usage.json` sidecar and, when a markdown receipt exists, a fenced `token_usage` block.
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
# Coordinator close: resolve lane->profile, write run+token ledgers, meter tokens.
# Token numbers come from a harness usage source (never estimated); omit them to record "unavailable".
python3 tools/aos-queue.py done AOS-2026-0001 --receipt queue/receipts/AOS-2026-0001.md --usage-file /tmp/hermes_usage.json
python3 scripts/token_rollup.py            # weekly rollups -> queue/rollups/
```

Any transition into `done` (via `status`, `receipt --status done`, or `done`)
triggers the coordinator: it appends one line to both `queue/run_ledger.jsonl`
and `queue/token_ledger.jsonl` and writes the `token_usage` block into the
receipt. The `status`/`receipt` paths keep queue liveness on a metering hiccup
(surfaced as `NEEDS ATTENTION (metering)` on stderr); the explicit `done`
command is the strict path.

Approved statuses:

- `inbox`
- `agent_todo`
- `agent_working`
- `needs_input`
- `human_review`
- `done`
- `blocked`
- `cancelled`
