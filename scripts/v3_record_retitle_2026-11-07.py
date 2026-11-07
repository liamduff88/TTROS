"""One-off: re-title the existing Memory Ingest v3 original records (2026-11-07).

Each v3 source INDEX (sources/historical_calls/<folder>/INDEX.md, type source_index) names its
original record. That record was titled with the transcript's first line ("Date: Nov 4"); it
becomes "Original: <source INDEX title>", exactly what the importer now writes for new sources
(memory_exchange_import.v3_record_title). Changes: the record's frontmatter title and H1, and
its label in sources/intake/INDEX.md. Nothing else. One Brain write_transaction.

Usage: v3_record_retitle_2026-11-07.py --dry-run | --apply   [--overwrite]
Tees a transcript beside itself and refuses to overwrite it. No model calls.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import brain_memory, source_intake  # noqa: E402
from tools.memory_exchange_import import v3_record_title  # noqa: E402
from tools.validate_business_brain import analyze_vault  # noqa: E402

EXPECTED = {  # declared population: Ryan, Chris, Lara, Nick
    "491e7000399832dc31f7d3e507db9ab751e4155d997f51ca38af8c02ee121d29",
    "098e5a08d7aef17cdd9e87bb76fe5b6ead7c3719d4413bd5c48e37c67569335d",
    "7ded0d7cd9d8447def32df46dec9e1d6ae965917508a787904003a54f2b9c13f",
    "f44cccaace70a48ac05695d64f8889d5d438c84fd4ce97abf6f0f1b01a07808a",
}
ATTRIBUTION = {"authenticated_identity": "ttros-v3-record-retitle", "surface": "ttros",
               "actor_class": "authorised_client", "surface_source": "local-cli"}
SOURCE = "v3-record-retitle"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def plan(brain: Path) -> dict:
    items, documents, rows = [], {}, []
    for index in sorted((brain / "sources/historical_calls").glob("*/INDEX.md")):
        fields = source_intake._frontmatter(index)
        if fields.get("type") != "source_index":
            continue
        relative = fields["source_record"].removeprefix("business_brain:")
        record = brain / relative
        text = record.read_text(encoding="utf-8")
        rec = source_intake._frontmatter(record)
        old, new = rec["title"], v3_record_title(fields["title"])
        head, sep, body = text.partition("\n---\n")
        assert head.startswith("---\n") and sep, f"{relative}: frontmatter not found"
        title_lines = [line for line in head.split("\n") if line.startswith("title: ")]
        h1 = [line for line in body.split("\n") if line.startswith("# ")][:1]
        assert len(title_lines) == 1 and h1 == [f"# {old}"], f"{relative}: unexpected title layout"
        new_head = head.replace(title_lines[0], f"title: {json.dumps(new, ensure_ascii=False)}", 1)
        new_text = new_head + sep + body.replace(h1[0], f"# {new}", 1)
        assert source_intake.extract_exact_bytes(new_text) == source_intake.extract_exact_bytes(text)
        if new_text != text:
            documents[relative] = new_text
        rows.append({"record": relative, "old": old, "new": new})
        items.append(source_intake.SourceItem(PurePosixPath(rec["original_filename"]), b"", rec["source_sha256"],
                                              rec["content_type"], new, rec.get("source_date") or None))
    found = {PurePosixPath(r["record"]).stem for r in rows}
    assert found == EXPECTED, f"population differs from the declared 4: {sorted(found ^ EXPECTED)}"
    intake_rel = source_intake.INDEX_RELATIVE
    current = (brain / intake_rel).read_text(encoding="utf-8")
    rendered = source_intake.render_index(brain, items)
    # write_transaction re-stamps hermes_last_write; compare without it.
    strip = lambda t: re.sub(r"\nhermes_last_write:\n(?:  .*\n)+", "\n", t)
    changed = [l for l in difflib.unified_diff(strip(current).splitlines(), rendered.splitlines(), lineterm="", n=0)
               if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    assert len(changed) == 2 * len(documents), f"intake INDEX diff is not only the record labels: {changed}"
    if documents:
        documents[intake_rel] = rendered
    return {"rows": rows, "documents": documents, "index_diff": changed}


def main(argv: list[str]) -> int:
    mode = "apply" if "--apply" in argv else "dry-run"
    transcript = Path(__file__).with_suffix(f".{mode}.txt")
    if transcript.exists() and "--overwrite" not in argv:
        print(f"refusing to overwrite {transcript.name}; pass --overwrite")
        return 2
    brain = brain_memory.VAULT_ROOT
    result = plan(brain)
    out = [f"v3 record retitle, {mode} (model calls: 0 of declared max 0)"]
    out += [f"  {r['record']}\n     old: {r['old'][:90]}\n     new: {r['new']}" for r in result["rows"]]
    out.append(f"  documents to write: {sorted(result['documents'])}")
    out += [f"  index {line[:150]}" for line in result["index_diff"]]
    if mode == "apply" and result["documents"]:
        raw = {r["record"]: source_intake.extract_exact_bytes((brain / r["record"]).read_text(encoding="utf-8"))
               for r in result["rows"]}

        def gate(changed) -> None:
            for relative, original in raw.items():
                if source_intake.extract_exact_bytes((brain / relative).read_text(encoding="utf-8")) != original:
                    raise RuntimeError(f"exact bytes changed: {relative}")
            vault = analyze_vault(brain)
            if vault["status"] != "PASS":
                raise RuntimeError(f"vault gate failed: {[k for k, v in vault['checks'].items() if v is False]}")

        write = brain_memory.write_transaction(
            result["documents"], source=SOURCE, session_id=f"{SOURCE}-2026-11-07",
            expected_hashes={rel: sha((brain / rel).read_bytes()) for rel in result["documents"]},
            post_write_validator=gate, attribution=ATTRIBUTION)
        out.append(f"  commit {write.commit} sync {write.sync_status} index {write.index_status} "
                   f"changed {sorted(write.changed_paths)}")
    text = "\n".join(out) + "\n"
    transcript.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
