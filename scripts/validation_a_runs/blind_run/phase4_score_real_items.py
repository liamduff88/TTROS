#!/usr/bin/env python3
"""Phase 4 -- blind, mechanical scoring of the 12 frozen items at their fixed
positions 1-12. Reads each item's source document(s) itself (this script,
not manual inspection) and calls the FROZEN detector.detect(). No rule code
is touched here. No human-in-the-loop adjustment per item."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detector  # frozen, hash recorded in phase3_freeze.json

REPO_ROOT = Path(__file__).resolve().parents[3]
FREEZE_PATH = REPO_ROOT / "scripts" / "validation_a_runs" / "blind_run_phase1_freeze.json"
OUT_PATH = Path(__file__).resolve().parent / "phase4_real_item_scores.json"

# Integrity check: the frozen detector file's hash must still match what was
# recorded at freeze time before it is used to score anything.
FREEZE_RECORD = json.loads((Path(__file__).resolve().parent / "phase3_freeze.json").read_text())
DETECTOR_PATH = Path(__file__).resolve().parent / "detector.py"
actual_hash = hashlib.sha256(DETECTOR_PATH.read_bytes()).hexdigest()
expected_hash = FREEZE_RECORD["frozen_files"][0]["sha256"]
if actual_hash != expected_hash:
    raise SystemExit(f"FROZEN DETECTOR HASH MISMATCH: expected {expected_hash}, got {actual_hash}")


def main() -> None:
    data = json.loads(FREEZE_PATH.read_text())
    results = []
    for candidate in data["candidates"]:
        position = candidate["position"]
        claim = candidate["bullet_text"]
        source_paths = [s["resolved_path"] for s in candidate["sources"]]
        texts = []
        for p in source_paths:
            path = Path(p)
            if path.is_file():
                texts.append(path.read_text(encoding="utf-8", errors="replace"))
        source_text = "\n\n".join(texts) if texts else None
        outcome = detector.score_real_item(f"item-{position}", claim, source_paths, source_text)
        results.append({
            "position": position,
            "item_id": f"item-{position}",
            "status": outcome["status"],
            "result": outcome["result"],
        })

    output = {
        "schema": "validation_a_phase4_real_item_scores_v1",
        "detector_sha256_verified": actual_hash,
        "item_count": len(results),
        "results": results,
    }
    if OUT_PATH.exists():
        raise SystemExit(f"REFUSING to overwrite existing {OUT_PATH} without --overwrite")
    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))
    print(f"\nwritten to {OUT_PATH}")
    print(f"sha256: {hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
