"""One-off: move the 35 pre-v3 packages whose ledger rows the removal dropped out of
Drive 04_IMPORTED into 08_SUPERSEDED_PRE_V3 (2026-11-07). Moves, never deletes.

Population: ledger.package_ids in ~/ttros-memory-audit/apply_rest_2026-11-07.json, matched to
04_IMPORTED folders by INGEST_MANIFEST.json package_id (derived in this run). Each folder's
sibling <name>.IMPORT_RECEIPT.json moves with it. 03_READY_FOR_TTROS is only listed.

Usage: move_superseded.py --dry-run | --apply   [--overwrite]
Tees a transcript beside itself and refuses to overwrite it. No model calls.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ME = Path("/mnt/g/My Drive/TTROS Memory Exchange")
READY, IMPORTED, SUPERSEDED = ME / "03_READY_FOR_TTROS", ME / "04_IMPORTED", ME / "08_SUPERSEDED_PRE_V3"
RECEIPT = Path.home() / "ttros-memory-audit/apply_rest_2026-11-07.json"
LEDGER = Path("/home/liam/agentic-os-live/queue/receipts/memory_exchange_import.jsonl")
WATCH = re.compile(r"_(6e9806531b13|88e0ed70f72a)$")
V3_MARK = re.compile(r"20261107|491e70003998")


def listing(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def watched(folder: Path) -> list[str]:
    return [n for n in listing(folder) if WATCH.search(n)]


def main(argv: list[str]) -> int:
    mode = "apply" if "--apply" in argv else "dry-run"
    transcript = Path(__file__).with_suffix(f".{mode}.txt")
    if transcript.exists() and "--overwrite" not in argv:
        print(f"refusing to overwrite {transcript.name}; pass --overwrite")
        return 2
    out = [f"move superseded pre-v3 packages, {mode} (model calls: 0 of declared max 0)"]
    ids = set(json.loads(RECEIPT.read_text())["ledger"]["package_ids"])
    out.append(f"dropped package IDs: {len(ids)}")
    rows = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    live = sorted({r.get("package_id") for r in rows} & ids)
    out.append(f"ledger rows still naming one of them: {sum(r.get('package_id') in ids for r in rows)} {live}")
    ready_before, imported_before = listing(READY), listing(IMPORTED)
    out.append(f"READY before: {ready_before}")
    out.append(f"IMPORTED entries before: {len(imported_before)}; SUPERSEDED exists: {SUPERSEDED.exists()}")
    out.append(f"watched suffixes before: IMPORTED {watched(IMPORTED)} READY {watched(READY)}")

    moves, by_id = [], {}
    for folder in sorted(IMPORTED.iterdir()):
        manifest = folder / "INGEST_MANIFEST.json"
        if folder.is_symlink() or not folder.is_dir() or not manifest.is_file():
            continue
        pid = json.loads(manifest.read_text(encoding="utf-8")).get("package_id")
        if pid in ids:
            by_id.setdefault(pid, []).append(folder.name)
            moves.append(folder)
    missing = sorted(ids - set(by_id))
    multi = {k: v for k, v in by_id.items() if len(v) > 1}
    v3 = [f.name for f in moves if V3_MARK.search(f.name)]
    out.append(f"folders matched: {len(moves)}; IDs with no folder: {missing}; IDs with >1 folder: {multi}")
    out.append(f"v3 folders in the move set: {v3}")
    entries = []
    for folder in moves:
        entries.append(folder)
        receipt = IMPORTED / (folder.name + ".IMPORT_RECEIPT.json")
        if receipt.is_file():
            entries.append(receipt)
    out.append(f"entries to move: {len(entries)}")
    out += [f"  {e.name}" for e in entries]
    # Gates: abort on any surprise before touching anything.
    assert not live and not v3 and not multi, "gate: live ledger rows, v3 folder or duplicate folder"
    if mode == "apply":
        active = subprocess.run(["systemctl", "--user", "is-active", "aos-memory-exchange-import.service"],
                                capture_output=True, text=True).stdout.strip()
        out.append(f"importer service at move time: {active}")
        assert active != "activating" and active != "active", "gate: importer run in progress"
        SUPERSEDED.mkdir(exist_ok=False)
        for entry in entries:
            target = SUPERSEDED / entry.name
            assert not target.exists(), f"gate: {target} exists"
            shutil.move(str(entry), str(target))
        after_imported, after_sup = listing(IMPORTED), listing(SUPERSEDED)
        out.append(f"IMPORTED entries after: {len(after_imported)}; SUPERSEDED entries after: {len(after_sup)}")
        out.append(f"moved names all present in SUPERSEDED: {sorted(e.name for e in entries) == after_sup}")
        out.append(f"watched suffixes after: IMPORTED {watched(IMPORTED)} READY {watched(READY)}")
        out.append(f"READY unchanged: {listing(READY) == ready_before}")
        out.append(f"IMPORTED lost only the moved names: "
                   f"{sorted(set(imported_before) - set(after_imported)) == after_sup}")
    text = "\n".join(out) + "\n"
    transcript.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
