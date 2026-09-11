#!/usr/bin/env python3
"""STEP T8-BCD Part C offline proof. Zero model calls.

Tees its own transcript beside itself; refuses to overwrite without --overwrite.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path("/home/liam/agentic-os-live")
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT))

TRANSCRIPT = Path(__file__).with_suffix(".txt")

POINTER_BARE = "sources/intake/records/d9cb4668fd766474278e414bb53223f944342004f34be23020c161fa4160dd74"
SPILL_THRESHOLD_CHARS = 50_000  # tools/budget_config.py::DEFAULT_MCP_RESULT_SIZE_CHARS
NEGATIVE_TERM = "unicorn"  # verified absent from the record via grep -c -i (exit 1, count 0)

SIX_CASES = [
    ("Fred/MLS", "What happened in my meeting with Fred, and what did he say about MLS?"),
    ("CCI", "What happened with CCI?"),
    ("Andrea", "Did Andrea Roberts introduce us to anyone?"),
    ("Negative control 1", "How many client work items are currently in human review?"),
    ("Negative control 2", "Thanks, that is helpful."),
    ("Fallback control", "What should I focus on this week given everything going on?"),
]
# T7's last-reported baseline (post-T8A cleanup has not touched these queries' selection).
T7_BASELINE_BYTES = {
    "Fred/MLS": 5148,
    "CCI": 7444,
    "Andrea": 4833,
    "Negative control 1": 192,
    "Negative control 2": 192,
    "Fallback control": 192,
}

lines: list[str] = []


def log(msg: str) -> None:
    print(msg)
    lines.append(msg)


def run_before(pointer: str) -> dict:
    """Exec the PREIMAGE module in a clean subinterpreter-like subprocess so
    'before' truly reflects the pre-change code, not an in-process monkeypatch."""
    script = f"""
import sys
sys.path.insert(0, {str(REPO_ROOT / "tools")!r})
sys.path.insert(0, {str(REPO_ROOT)!r})
import importlib.util, importlib.machinery
loader = importlib.machinery.SourceFileLoader("brain_memory_mcp_preimage", "/home/liam/ttros_backups/stepT8BCD_2026-09-10/brain_memory_mcp.py.PREIMAGE")
spec = importlib.util.spec_from_loader(loader.name, loader)
mod = importlib.util.module_from_spec(spec)
sys.modules["brain_memory_mcp_preimage"] = mod
loader.exec_module(mod)
result = mod.open_note({pointer!r})
import json
print(json.dumps(result))
"""
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        raise RuntimeError(f"before-subprocess failed: {proc.stderr}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main() -> int:
    if TRANSCRIPT.exists() and "--overwrite" not in sys.argv:
        print(f"refusing to overwrite existing transcript: {TRANSCRIPT}", file=sys.stderr)
        return 2

    log("=" * 78)
    log("STEP T8-BCD Part C offline proof -- zero model calls")
    log("=" * 78)

    # ---- PREDICTIONS (written before running each check) ----
    log("\n--- PREDICTIONS (written before running) ---")
    log("1. Card pointer, verbatim, BEFORE (preimage code): FAILS with "
        "'Hermes durable knowledge writes must target Markdown'.")
    log("2. Card pointer, verbatim, AFTER (this change): SUCCEEDS (success=true).")
    log("3. GVR-boards call via card pointer + query 'GVR boards how many': "
        "result content contains 'I think 11 boards'; JSON-serialized result size "
        f"strictly below {SPILL_THRESHOLD_CHARS:,} chars (the Hermes MCP spill threshold).")
    log(f"4. Negative control (term {NEGATIVE_TERM!r}, verified absent from the record by "
        "grep -c -i, count=0): matched=false, no passage returned.")
    log("5. search_calls/open_call on one historical call: output byte-identical before vs after.")
    log("6. T1's six assemble() cases: zero byte delta from T7's last-reported baseline.")
    log("7. hooks/context_assembler_hook.py mode: still 755 (untouched by this step).")

    os.environ.pop("TTROS_BRAIN_ROOT", None)  # use the real default vault, as David would

    import brain_memory_mcp as bmm  # noqa: E402  (AFTER code, imported fresh)
    importlib.reload(bmm)

    # ---- 1 & 2: pointer resolution before/after ----
    log("\n--- CHECK 1/2: card pointer resolution, before vs after ---")
    before = run_before(POINTER_BARE)
    log(f"BEFORE: success={before.get('success')} error={before.get('error')!r}")
    after = bmm.open_note(POINTER_BARE)
    log(f"AFTER:  success={after.get('success')} pointer={after.get('pointer')!r} "
        f"content_len={len(after.get('content',''))}")
    assert before.get("success") is False, "expected BEFORE to fail"
    assert "Markdown" in str(before.get("error", "")), "expected the misleading Markdown error BEFORE"
    assert after.get("success") is True, "expected AFTER to succeed"
    log("RESULT: PASS -- before fails, after resolves the exact card-rendered pointer.")

    # ---- 3: bounded passage for the GVR-boards question ----
    log("\n--- CHECK 3: bounded passage, GVR boards ---")
    query = "meeting Fred exact words how many GVR boards there"
    log(f"query (derived from Part D's verbatim question): {query!r}")
    passage_result = bmm.open_note(POINTER_BARE, query=query)
    content = passage_result.get("content", "")
    serialized_len = len(json.dumps(passage_result))
    log(f"matched={passage_result.get('matched')} content_len={len(content)} "
        f"serialized_len={serialized_len}")
    log(f"content:\n{content}\n")
    assert "I think 11 boards" in content, "expected the exact quote in the bounded passage"
    assert serialized_len < SPILL_THRESHOLD_CHARS, (
        f"serialized result {serialized_len} chars must be strictly under the "
        f"{SPILL_THRESHOLD_CHARS} char spill threshold"
    )
    log(f"RESULT: PASS -- quote present; serialized size {serialized_len:,} chars "
        f"< {SPILL_THRESHOLD_CHARS:,} char spill threshold.")

    # ---- 4: negative control ----
    log("\n--- CHECK 4: negative control ---")
    neg_result = bmm.open_note(POINTER_BARE, query=NEGATIVE_TERM)
    log(f"query={NEGATIVE_TERM!r} matched={neg_result.get('matched')} "
        f"content={neg_result.get('content')!r}")
    assert neg_result.get("matched") is False, "expected no match for a verified-absent term"
    assert neg_result.get("content", "") == "", "expected empty content, not an arbitrary chunk"
    log("RESULT: PASS -- verified-absent term returns no passage, not an arbitrary chunk.")

    # ---- 5: search_calls/open_call byte-identity on a historical call ----
    log("\n--- CHECK 5: search_calls/open_call byte-identity (historical call, untouched code path) ---")
    before_call = run_before_open_call("andrea-roberts-june-26")
    after_call = bmm.open_call("andrea-roberts-june-26")
    log(f"BEFORE open_call success={before_call.get('success')} content_len={len(before_call.get('content',''))}")
    log(f"AFTER  open_call success={after_call.get('success')} content_len={len(after_call.get('content',''))}")
    assert before_call == after_call, "expected byte-identical open_call result before vs after"
    log("RESULT: PASS -- open_call output byte-identical before vs after (function untouched).")

    # ---- 6: T1's six assemble() cases ----
    log("\n--- CHECK 6: T1's six assemble() cases (scoped canonical Brain notes block bytes) ---")
    from tools import context_assembler as ca
    all_zero_delta = True
    for name, question in SIX_CASES:
        assembled = ca.assemble(
            question,
            surface="cli",
            session_id="stept8bcd-offline-proof",
            session_key="",
            client_scope="global",
            profile="david",
            write_artifact=False,
        )
        block = next(b for b in assembled.blocks if b.name == "scoped canonical Brain notes")
        baseline = T7_BASELINE_BYTES[name]
        delta = block.byte_count - baseline
        status = "OK" if delta == 0 else "DRIFT"
        if delta != 0:
            all_zero_delta = False
        log(f"{name:22s} bytes={block.byte_count:6d} baseline={baseline:6d} delta={delta:+d} [{status}]")
    log(f"RESULT: {'PASS' if all_zero_delta else 'FAIL'} -- "
        f"{'zero byte drift on all six cases' if all_zero_delta else 'drift detected, see above'}.")

    # ---- 7: hooks/context_assembler_hook.py mode ----
    log("\n--- CHECK 7: hooks/context_assembler_hook.py mode ---")
    hook_path = REPO_ROOT / "hooks" / "context_assembler_hook.py"
    mode = oct(hook_path.stat().st_mode)[-3:]
    log(f"mode={mode}")
    assert mode == "755", f"expected mode 755, got {mode}"
    log("RESULT: PASS -- mode unchanged at 755.")

    log("\n" + "=" * 78)
    log("ALL CHECKS PASSED" if all_zero_delta else "SOME CHECKS FAILED -- see CHECK 6")
    log("=" * 78)

    TRANSCRIPT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\ntranscript written: {TRANSCRIPT}")
    return 0 if all_zero_delta else 1


def run_before_open_call(call_id: str) -> dict:
    script = f"""
import sys, importlib.util, importlib.machinery, json
sys.path.insert(0, {str(REPO_ROOT / "tools")!r})
sys.path.insert(0, {str(REPO_ROOT)!r})
loader = importlib.machinery.SourceFileLoader("brain_memory_mcp_preimage2", "/home/liam/ttros_backups/stepT8BCD_2026-09-10/brain_memory_mcp.py.PREIMAGE")
spec = importlib.util.spec_from_loader(loader.name, loader)
mod = importlib.util.module_from_spec(spec)
sys.modules["brain_memory_mcp_preimage2"] = mod
loader.exec_module(mod)
result = mod.open_call({call_id!r})
print(json.dumps(result))
"""
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        raise RuntimeError(f"before-open_call subprocess failed: {proc.stderr}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


if __name__ == "__main__":
    raise SystemExit(main())
