#!/usr/bin/env python3
"""Two steps of one work item through the production Codex worker path.

Each step runs ``_queue_actual_run_prompt`` -> ``worker_context_pack`` ->
``_run_codex_local`` exactly as the queue does, capturing the exact prompt
written to Codex stdin and the exact argv. Step 1 is given a random nonce;
step 2 is asked for it. A fresh session cannot know it, so a leaked nonce, a
missing or repeated ``thread.started`` ID, or a ``resume`` argv fails the run.

Declared model-call budget: 2. The script hard-stops before a third call and
records the actual count in its transcript.

Revisit: one-off for the 2026-10-25 work-order prompt repair. · Last touched: 2026-10-25.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))

MAX_MODEL_CALLS = 2
PARENT = "AOS-2026-9950"


def _step(item_id: str, title: str, context: str) -> dict:
    return {
        "id": item_id, "parent_id": PARENT, "title": title, "owner": "codex", "context": context,
        "definition_of_done": "The reply is the single requested line; nothing is edited or written.",
        "allowed_actions": ["local_read"],
        "stop_conditions": ["local_edit", "external_send", "git_commit", "git_push"],
        "sources": ["queue/templates/"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--transcript", type=Path, default=Path(__file__).with_suffix(".txt"))
    args = parser.parse_args()
    if args.transcript.exists() and not args.overwrite:
        print(f"refusing to overwrite {args.transcript}; pass --overwrite", file=sys.stderr)
        return 2

    import context_assembler
    import main as backend

    nonce = f"NONCE-{secrets.token_hex(6)}"
    probe = "Probe step: skip the artifact and receipt; reply with exactly one line and nothing else."
    steps = [
        _step("AOS-2026-9951", "Isolation probe step 1: template count", (
            f"{probe} Remember the value {nonce}. Count the files directly inside queue/templates with one "
            "listing command, run `git remote get-url --push origin`, and reply: COUNT=<n> PUSH_URL=<url>."
        )),
        _step("AOS-2026-9952", "Isolation probe step 2: prior-session recall", (
            f"{probe} Without running any command, if this session already holds a value that starts with "
            "NONCE- from any earlier message, reply PRIOR=<that value>; otherwise reply PRIOR=none."
        )),
    ]
    calls = 0
    records = []
    for item in steps:
        if calls >= MAX_MODEL_CALLS:
            raise SystemExit("model-call budget exhausted before launch")
        sent: dict = {}
        real_prepare, real_command = backend.prepare_codex_fresh_prompt, backend.build_codex_exec_command

        def capture_prompt(text: str) -> str:
            sent["prompt"] = real_prepare(text)
            return sent["prompt"]

        def capture_command(*a, **kw) -> list[str]:
            sent["argv"] = real_command(*a, **kw)
            return sent["argv"]

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(backend, "prepare_codex_fresh_prompt", side_effect=capture_prompt), \
             patch.object(backend, "build_codex_exec_command", side_effect=capture_command):
            instructions = backend._queue_actual_run_prompt(item, "codex")
            context, _pack = context_assembler.worker_context_pack(
                item, owner="codex", execution_instructions=instructions, pack_dir=Path(tmp),
            )
            calls += 1
            result = backend._run_codex_local(context, item)
        if calls > MAX_MODEL_CALLS:  # pragma: no cover - structural guard
            raise SystemExit("model-call budget exceeded")
        invocation = result.get("invocation") or {}
        prompt = sent.get("prompt", "")
        records.append({
            "item_id": item["id"],
            "success": result.get("success"),
            "failure_class": result.get("failure_class"),
            "session_id": result.get("session_id"),
            "invocation_id": invocation.get("invocation_id"),
            "fuse_scope": invocation.get("fuse_scope"),
            "model": invocation.get("actual_model"),
            "reasoning_effort": invocation.get("reasoning_effort"),
            "argv": sent.get("argv"),
            "prompt_sent": prompt,
            "prompt_bytes": len(prompt.encode("utf-8")),
            "prompt_non_blank_lines": sum(1 for line in prompt.splitlines() if line.strip()),
            "context_manifest": f"queue/context_assemblies/{context.invocation_id}.json",
            "output": str(result.get("output") or "")[-600:],
            "token_usage_text": result.get("token_usage_text"),
            "stream_artifacts": result.get("stream_artifacts"),
        })

    ids = [row["session_id"] for row in records]
    checks = {
        "every_step_succeeded": all(row["success"] for row in records),
        "every_step_has_real_thread_id": all(isinstance(value, str) and value for value in ids),
        "thread_ids_distinct": len(set(ids)) == len(ids),
        "fuse_scopes_distinct": len({row["fuse_scope"] for row in records}) == len(records),
        "argv_ephemeral_no_resume": all(
            "--ephemeral" in (row["argv"] or []) and not {"resume", "--last"} & set(row["argv"] or [])
            for row in records
        ),
        "step2_did_not_see_step1_nonce": nonce not in records[1]["output"],
        "step2_prompt_lacks_nonce": nonce not in records[1]["prompt_sent"],
        "push_url_blocked_inside_codex": "codex-push-forbidden://" in records[0]["output"],
        "prompts_within_10_non_blank_lines": all(row["prompt_non_blank_lines"] <= 10 for row in records),
    }
    record = {
        "model_calls": {"actual": calls, "declared_max": MAX_MODEL_CALLS},
        "surface": "queue worker path (_queue_actual_run_prompt -> worker_context_pack -> _run_codex_local), no queue mutation",
        "parent_item": PARENT,
        "nonce": nonce,
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "steps": records,
    }
    text = json.dumps(record, indent=2, ensure_ascii=False)
    args.transcript.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
