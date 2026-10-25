#!/usr/bin/env python3
"""One small fresh Codex session through the production launcher.

Calls ``dashboard/backend/main.py::_run_codex_local`` exactly as
``/api/wsl/codex`` does (direct route, no work item): per-session fuse scope,
automatic model/effort selection, streaming fuse, canonical ledger row.
Declared model-call budget: 1. The script hard-stops before a second call and
records the actual count in its transcript.

Revisit: one-off for the 2026-10-25 token-budget correction. · Last touched: 2026-10-25.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))

MAX_MODEL_CALLS = 1
TASK = (
    "Read-only status check: report the count of files directly inside queue/templates. "
    "Run one listing command, do not edit anything, and reply with one line: TEMPLATE_COUNT=<n>."
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    transcript = Path(__file__).with_suffix(".txt")
    if transcript.exists() and not args.overwrite:
        print(f"refusing to overwrite {transcript}; pass --overwrite", file=sys.stderr)
        return 2

    import main as backend

    calls = 0
    if calls >= MAX_MODEL_CALLS:
        raise SystemExit("model-call budget exhausted before launch")
    context = backend.assemble_model_context(
        TASK, surface="dashboard:codex", session_id=f"codex-{uuid.uuid4().hex}",
    )
    started = time.monotonic()
    calls += 1
    result = backend._run_codex_local(context)
    elapsed = round(time.monotonic() - started, 3)
    if calls > MAX_MODEL_CALLS:  # pragma: no cover - structural guard
        raise SystemExit("model-call budget exceeded")

    invocation = result.get("invocation") or {}
    rows = [
        json.loads(line) for line in (ROOT / "queue" / "token_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("invocation_id") == invocation.get("invocation_id")
    ]
    record = {
        "model_calls": {"actual": calls, "declared_max": MAX_MODEL_CALLS},
        "surface": "dashboard:codex via _run_codex_local (direct route, no work item)",
        "success": result.get("success"),
        "failure_class": result.get("failure_class"),
        "returncode": result.get("returncode"),
        "elapsed_seconds": elapsed,
        "command_stage": result.get("command_stage"),
        "session_id": result.get("session_id"),
        "fuse_scope": invocation.get("fuse_scope"),
        "model_selection": invocation.get("model_selection"),
        "initial_prompt_bytes": invocation.get("initial_prompt_bytes"),
        "session_fuse": invocation.get("session_fuse"),
        "token_usage_text": result.get("token_usage_text"),
        "output": str(result.get("output") or "")[-1_500:],
        "stream_artifacts": result.get("stream_artifacts"),
        "ledger_rows": [
            {key: row.get(key) for key in ("event", "scope_key", "invocation_id", "model_requested", "model_selection", "exact_usage", "fuse")}
            for row in rows
        ],
    }
    text = json.dumps(record, indent=2, ensure_ascii=False)
    transcript.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
