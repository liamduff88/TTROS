#!/usr/bin/env python3
"""Compare a freshly assembled AOS-2026-0943-style Codex prompt with the original.

Baseline: queue/context_assemblies/ctx-10bcbed83efb48439f2e489146bacc00.json
(worker:codex, 2026-10-24, assembler total 6,235 estimated tokens; route log
initial_prompt_bytes 32,818). Zero model calls. Assembly artifacts and the
pack go to a temporary directory, never the live cache.

Revisit: one-off for the 2026-10-25 prompt-budget correction. · Last touched: 2026-10-25.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))

BASELINE = ROOT / "queue/context_assemblies/ctx-10bcbed83efb48439f2e489146bacc00.json"
BASELINE_TOKENS = 6_235
BASELINE_PROMPT_BYTES = 32_818
UNRELATED = ("client_memory/workflow.md", "lead_gen_agent/workflow.md", "voice_agent_setup/workflow.md", "aoa_working_session/SKILL.md")


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

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert baseline["total_tokens"] == BASELINE_TOKENS, baseline["total_tokens"]
    item = next(
        json.loads(line) for line in (ROOT / "queue/work_items.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("id") == "AOS-2026-0943"
    )
    lines: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(context_assembler, "ASSEMBLY_DIR", Path(tmp) / "assemblies"):
            instructions = backend._queue_actual_run_prompt(item, "codex", attempt=1, max_attempts=2)
            context, _pack = context_assembler.worker_context_pack(
                item, owner="codex", execution_instructions=instructions, pack_dir=Path(tmp) / "packs",
            )
            prepared = prepare_fresh_prompt(context.render())
    total = context.total_tokens
    assert isinstance(total, int) and total > 0
    prepared_bytes = len(prepared.encode("utf-8"))
    prepared_tokens = context_assembler.estimate_tokens(prepared)
    present = [name for name in UNRELATED if name in prepared]
    blocks = {block.name: block.token_count for block in context.blocks}
    lines += [
        "AOS-2026-0943-style technical Codex prompt — surface worker:codex (same estimator: context_assembler.estimate_tokens)",
        f"classification: {context.classification}",
        f"baseline assembler total: {BASELINE_TOKENS} est. tokens; new: {total} ({total / BASELINE_TOKENS:.1%} of baseline)",
        f"baseline prepared prompt: {BASELINE_PROMPT_BYTES} bytes; new: {prepared_bytes} bytes ({prepared_bytes / BASELINE_PROMPT_BYTES:.1%}); new prepared est. tokens {prepared_tokens}",
        f"baseline matching-workflow block: {next(b['token_count'] for b in baseline['blocks'] if b['name'] == 'matching skills/workflows')} tokens; new: {blocks['matching skills/workflows']}",
        f"unrelated workflows present in new prompt: {present or 'none'}",
        f"permission header occurrences: {prepared.count('PERMISSION MODE — SCOPED LOCAL TASK APPROVED')}",
        f"objective lines: {prepared.count('Objective (definition of done):')}; receipt-shape blocks: {prepared.count('Summary for operator:')}",
        "operator chat in prompt: " + ("yes" if "What the fuck" in prepared else "no"),
        "new blocks (tokens): " + json.dumps(blocks),
        "",
        "--- prepared prompt ---",
        prepared,
    ]
    text = "\n".join(lines)
    transcript.write_text(text, encoding="utf-8")
    print("\n".join(lines[:10]))
    return 0 if not present else 1


if __name__ == "__main__":
    raise SystemExit(main())
