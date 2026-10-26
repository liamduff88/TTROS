#!/usr/bin/env python3
"""Compare the original AOS-2026-0947 Codex prompt with the current pipeline's.

Original: the worker:codex manifest the 2026-10-26T01:16Z launch actually used
(queue/context_assemblies/ctx-7506462770e1464fab549760cea9ddc9.json), rendered
and prepared by the code at commit 1c70d68. New: the live item through
``_queue_actual_run_prompt`` -> ``worker_context_pack`` -> ``render`` ->
``prepare_fresh_prompt``, the exact text ``_run_codex_local`` writes to stdin.
Zero model calls; assembly artifacts go to a temporary directory.

Revisit: one-off for the 2026-10-25 work-order prompt repair. · Last touched: 2026-10-25.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))

BASELINE = ROOT / "queue/context_assemblies/ctx-7506462770e1464fab549760cea9ddc9.json"
BASELINE_COMMIT = "1c70d68"
ITEM_ID = "AOS-2026-0947"


def _module_at(commit: str, relative: str, name: str, tmp: Path):
    source = subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{relative}"], check=True, capture_output=True, text=True).stdout
    path = tmp / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _original_prompt(tmp: Path) -> str:
    old_ca = _module_at(BASELINE_COMMIT, "tools/context_assembler.py", "context_assembler_1c70d68", tmp)
    old_policy = _module_at(BASELINE_COMMIT, "tools/aos_codex_policy.py", "aos_codex_policy_1c70d68", tmp)
    manifest = json.loads(BASELINE.read_text(encoding="utf-8"))
    blocks = tuple(
        old_ca.ContextBlock(
            b["name"], b["content"], tuple(b["sources"]), b.get("stable_prefix", False), b.get("selection", "required"),
            tuple(old_ca.ActualRead(**read) for read in b.get("actual_reads", [])),
        )
        for b in manifest["blocks"]
    )
    context = old_ca.AssembledContext(
        manifest["invocation_id"], manifest["surface"], manifest["session_id"], manifest["classification"],
        manifest["client_scope"], manifest["request"], blocks, manifest["created_at"], tuple(manifest.get("warnings", [])),
    )
    assert context.total_bytes == manifest["total_bytes"], (context.total_bytes, manifest["total_bytes"])
    return old_policy.prepare_fresh_prompt(context.render())


def _shape(prompt: str) -> dict:
    return {
        "bytes": len(prompt.encode("utf-8")),
        "lines": len(prompt.splitlines()),
        "non_blank_lines": sum(1 for line in prompt.splitlines() if line.strip()),
        "permission_headers": prompt.count("PERMISSION MODE — SCOPED LOCAL TASK APPROVED"),
        "session_essay": "Fresh-session and retained-context contract" in prompt,
        "receipt_template": "Required artifact/receipt shape" in prompt,
        "assembly_metadata": "[TTROS_ASSEMBLED_CONTEXT_V1]" in prompt,
        "global_boundary_block": "## action boundaries" in prompt,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    transcript = Path(__file__).with_suffix(".txt")
    if transcript.exists() and not args.overwrite:
        print(f"refusing to overwrite {transcript}; pass --overwrite", file=sys.stderr)
        return 2

    import context_assembler
    import main as backend
    from aos_codex_policy import prepare_fresh_prompt

    item = next(
        json.loads(line) for line in (ROOT / "queue/work_items.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("id") == ITEM_ID
    )
    with tempfile.TemporaryDirectory() as tmp:
        original = _original_prompt(Path(tmp))
        with mock.patch.object(context_assembler, "ASSEMBLY_DIR", Path(tmp) / "assemblies"):
            instructions = backend._queue_actual_run_prompt(item, "codex", attempt=1, max_attempts=2)
            context, _pack = context_assembler.worker_context_pack(
                item, owner="codex", execution_instructions=instructions, pack_dir=Path(tmp) / "packs",
            )
            new = prepare_fresh_prompt(context.render())
    before, after = _shape(original), _shape(new)
    assert isinstance(before["bytes"], int) and before["bytes"] > 0 and after["bytes"] > 0
    kept = all(fragment in new for fragment in (item["context"][:60], item["definition_of_done"][:60], "git_push", "Token usage"))
    lines = [
        f"{ITEM_ID} final Codex prompt (text written to codex exec stdin), worker:codex surface",
        f"original ({BASELINE_COMMIT}, manifest {BASELINE.name}): " + json.dumps(before),
        "new (working tree): " + json.dumps(after),
        f"bytes: {before['bytes']} -> {after['bytes']} ({after['bytes'] / before['bytes']:.1%}); "
        f"non-blank lines: {before['non_blank_lines']} -> {after['non_blank_lines']}",
        f"item context, done-when, git_push stop and token-usage label kept: {kept}",
        "",
        "--- original prompt ---",
        original,
        "--- new prompt ---",
        new,
    ]
    text = "\n".join(lines)
    transcript.write_text(text, encoding="utf-8")
    print("\n".join(lines[:5]))
    return 0 if kept and after["non_blank_lines"] <= 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
