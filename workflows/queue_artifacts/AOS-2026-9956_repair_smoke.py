"""One real David -> Operating Hermes -> Codex smoke after the 9955/9956 repair.

Sends exactly one Ask David request (hard cap 1), waits a bounded time for the
resulting objective to reach a terminal state, then records the evidence:
route model invocations from logs/token_usage.jsonl since start (declared max
6: David, planner, Codex, reviewer, synthesis + 1 slack), the Codex stream, and
both receipts. Tees a .txt transcript beside itself; refuses to overwrite it
without --overwrite.
"""
import datetime
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path("/home/liam/agentic-os-live")
TRANSCRIPT = Path(__file__).with_suffix(".txt")
DECLARED_MAX_INVOCATIONS = 6
MAX_REQUESTS = 1
WAIT_SECONDS = 900
MESSAGE = (
    "Run one NEW, minimal, read-only task through Operating Hermes → Codex to verify the complete execution route.\n"
    "Codex should execute only git rev-parse --short HEAD in the TTROS repository and report the result.\n"
    "No other investigation, code edits, extensive file reading, or additional tasks.\n"
    "Confirm:\nReal Codex session ID\nExecution success and command output\nActual token usage\n"
    "Durable receipt and final queue status\n"
    "Report PASS only if the complete route works and the task finishes successfully. Otherwise, report the exact failure."
)

if TRANSCRIPT.exists() and "--overwrite" not in sys.argv:
    sys.exit(f"refusing to overwrite {TRANSCRIPT}; pass --overwrite")
lines: list[str] = []


def log(text=""):
    print(text)
    lines.append(str(text))


def items():
    return [json.loads(l) for l in (ROOT / "queue/work_items.jsonl").read_text().splitlines() if l.strip()]


started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
known = {row["id"] for row in items()}
requests_sent = 0
log(f"start {started}Z; declared max route invocations {DECLARED_MAX_INVOCATIONS}; max requests {MAX_REQUESTS}")
assert requests_sent < MAX_REQUESTS
request = urllib.request.Request(
    "http://127.0.0.1:8010/api/dashboard/ask-david",
    data=json.dumps({"text": MESSAGE}).encode(), headers={"Content-Type": "application/json"}, method="POST",
)
requests_sent += 1
with urllib.request.urlopen(request, timeout=900) as response:
    reply = json.loads(response.read())
log(f"ask-david http ok; keys={sorted(reply)[:12]}")

deadline = time.monotonic() + WAIT_SECONDS
parent = None
while time.monotonic() < deadline:
    new = [row for row in items() if row["id"] not in known]
    parents = [row for row in new if "executive_objective" in (row.get("tags") or [])]
    if parents and parents[0]["status"] in {"done", "blocked", "needs_input", "human_review"}:
        parent = parents[0]
        break
    time.sleep(5)
new = [row for row in items() if row["id"] not in known]
for row in new:
    log(f"item {row['id']} owner={row.get('owner')} status={row['status']} allowed={row.get('allowed_actions')}")
    for receipt in row.get("receipts") or []:
        log(f"  receipt {receipt.get('status')} {receipt.get('path')}")
if parent is None:
    log("NO TERMINAL PARENT within wait")

invocations = []
for raw in (ROOT / "logs/token_usage.jsonl").read_text().splitlines():
    row = json.loads(raw)
    if str(row.get("timestamp", "")) >= started:
        usage = row.get("token_usage") or {}
        invocations.append(row)
        log(f"invocation role={row.get('role')} route={row.get('route')} in={usage.get('input_tokens')} "
            f"cached={usage.get('cached_input_tokens', usage.get('cache_read_tokens'))} out={usage.get('output_tokens')} "
            f"total={usage.get('total_tokens')} api_calls={usage.get('api_calls')} session={usage.get('session_id')}")
log(f"route invocations {len(invocations)} / declared max {DECLARED_MAX_INVOCATIONS}")

for row in new:
    if row.get("owner") != "codex":
        continue
    for raw in (ROOT / "logs/local_agent_route.jsonl").read_text().splitlines()[::-1]:
        route = json.loads(raw)
        if route.get("item_id") == row["id"]:
            stream = ROOT / route["stream_artifacts"][0]
            events = [json.loads(l) for l in stream.read_text().splitlines() if l.strip()]
            thread = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
            kinds = [(e.get("item") or {}).get("type") for e in events if e.get("type") == "item.completed"]
            log(f"codex stream {stream.relative_to(ROOT)} thread.started={thread}")
            log(f"codex items {kinds}; file_change={kinds.count('file_change')}; "
                f"requests_estimated={(route.get('session_fuse') or {}).get('requests_estimated')}")
            break
log(f"requests sent {requests_sent} / max {MAX_REQUESTS}")
TRANSCRIPT.write_text("\n".join(lines) + "\n")
if len(invocations) > DECLARED_MAX_INVOCATIONS:
    sys.exit(f"route invocations {len(invocations)} exceeded declared max {DECLARED_MAX_INVOCATIONS}")
