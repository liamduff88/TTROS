#!/usr/bin/env python3
"""Remove a named set of old Brain notes so their sources can be re-ingested (Memory Ingest spec 0.2 §8 item 6).

Input is a file of Brain paths (one per line; blank lines and `#` comments ignored; an optional
`business_brain:` prefix is accepted) and/or paths on the command line. Only these are allowed:
  - notes directly under sources/historical_calls/ (never INDEX.md or MANIFEST.md);
  - cards under sources/historical_calls/cards/;
  - files inside a v3 source folder, only when that exact file is named (no folder expansion);
  - source-intake cards, sources/intake/cards/<sha256>.card.md;
  - source-intake records, sources/intake/records/<sha256>.md, only when named explicitly.
Anything else is refused, and one refused path refuses the whole --apply.

--dry-run is the default and writes nothing: it proves the result on a vault copy (deletions,
INDEX edits, then the filing plan for people hubs / NEEDS_IDENTITY / MEMORY_INDEX) and reports the
counts. --apply re-plans and re-proves inside the importer lock, then:
  1. ONE brain_memory.write_transaction deletes the files and removes their rows/links from
     sources/historical_calls/INDEX.md and sources/intake/INDEX.md (search rows go with it);
  2. removes the import-ledger rows of every package that wrote a removed note, so re-ingest is not
     refused (the rows are archived to queue/receipts/memory_exchange_import.removed.jsonl first);
  3. marks the removed notes in the filing ledger so a pending retry never asks for them again;
  4. reruns filing --all, so hubs and NEEDS_IDENTITY rebuild without them.
Session/workstream logs and inbox packets are left alone as history.

--orphan-records lists intake records that no note points to (frontmatter `source_record`, or a
card's `source_path`) and, with --apply, removes them the same way. Run it after re-ingest.
No model calls.

Revisit: when the import ledger, filing stage or intake INDEX format changes. · Last touched: 2026-11-07.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import brain_memory
from tools import memory_filing as filing
from tools.business_brain import BUSINESS_BRAIN_ROOT
from tools.memory_exchange_import import (
    HISTORICAL_INDEX, LEDGER, TOKEN_USAGE, V3_SOURCE_FOLDER, append, digest, ledger_rows, locked,
)
from tools.validate_business_brain import WIKI_LINK_RE, analyze_vault, canonical_wiki_target, parse_frontmatter

INTAKE_INDEX = "sources/intake/INDEX.md"
RECORDS = "sources/intake/records/"
INDEXES = (HISTORICAL_INDEX, INTAKE_INDEX)
IMPORT_LOCK = "queue/locks/memory_exchange_import.lock"
ARCHIVE = "queue/receipts/memory_exchange_import.removed.jsonl"
RECEIPTS = "queue/receipts/memory_remove_notes.jsonl"
SOURCE = "memory-remove-notes"
PREFIX = "business_brain:"
ATTRIBUTION = {"authenticated_identity": "ttros-memory-remove-notes", "surface": "ttros",
               "actor_class": "operator_cli", "surface_source": "address"}
# Pages the filing stage regenerates; their links to removed notes are fixed by the filing rerun.
FILING_MANAGED = re.compile(r"(?:people/[^/]+\.md|index/MEMORY_INDEX\.md)\Z")
HISTORY_PREFIXES = ("sessions/", "inbox/")
KINDS = (
    ("historical_note", re.compile(r"sources/historical_calls/(?!INDEX\.md\Z|MANIFEST\.md\Z)[^/]+\.md\Z")),
    ("historical_card", re.compile(r"sources/historical_calls/cards/[^/]+\.card\.md\Z")),
    ("v3_note", re.compile(V3_SOURCE_FOLDER + r"[^/]+\.md\Z")),
    ("intake_card", re.compile(r"sources/intake/cards/[0-9a-f]{64}\.card\.md\Z")),
    ("intake_record", re.compile(r"sources/intake/records/[0-9a-f]{64}\.md\Z")),
)


class RemovalError(RuntimeError):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


# ---------------------------------------------------------------- input


def read_list(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def classify(raw: str) -> tuple[str | None, str]:
    """(kind, relative) for an allowed path, or (None, reason)."""
    value = raw.strip().removeprefix(PREFIX)
    pure = PurePosixPath(value)
    if (not value or "\\" in value or "\x00" in value or ":" in value or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        return None, "unsafe path"
    for kind, pattern in KINDS:
        if pattern.fullmatch(value):
            return kind, value
    return None, "not an allowed removal path (historical note/card, named v3 file, intake card or named intake record)"


def gather(brain: Path, raws: list[str]) -> dict:
    allowed, refused, absent, seen, duplicates = {}, [], [], set(), 0
    for raw in raws:
        kind, value = classify(raw)
        if kind is None:
            refused.append({"path": raw, "reason": value})
            continue
        if value in seen:
            duplicates += 1
            continue
        seen.add(value)
        path = brain / value
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if brain in p.parents):
            refused.append({"path": raw, "reason": "symlink path"})
        elif not path.exists():
            absent.append(value)
        elif not path.is_file():
            refused.append({"path": raw, "reason": "not a regular file"})
        else:
            allowed[value] = kind
    return {"allowed": allowed, "refused": refused, "absent": absent, "duplicates": duplicates}


# ---------------------------------------------------------------- INDEX edits


def strip_index(text: str, removed: set[str]) -> tuple[str, list[str], int]:
    """Remove links to removed notes: the whole line when its first link is removed, else the link itself.

    Returns (text, dropped lines, links stripped from kept lines). A `##` section this emptied goes too.
    """
    lines = text.split("\n")
    body_start = 0
    if lines and lines[0] == "---":
        body_start = next((i + 1 for i in range(1, len(lines)) if lines[i] == "---"), 0)
    out, dropped, stripped, touched = lines[:body_start], [], 0, set()
    for line in lines[body_start:]:
        links = [(m, canonical_wiki_target(m.group(1))) for m in WIKI_LINK_RE.finditer(line)]
        hits = [(m, target) for m, target in links if target in removed]
        if not hits:
            out.append(line)
            continue
        if links[0][1] in removed:
            dropped.append(line)
            touched.add(len(out))
            continue
        for m, _target in hits:
            line, n = re.subn(r"(?:\s*·\s*|,\s*)?" + re.escape(m.group(0)), "", line, count=1)
            stripped += n
        out.append(line)
    # Drop `##` headings left with nothing under them, only where lines were dropped.
    result, i = [], 0
    while i < len(out):
        line = out[i]
        if line.startswith("## ") and i >= body_start:
            j = i + 1
            while j < len(out) and not out[j].strip():
                j += 1
            end_of_section = j >= len(out) or out[j].startswith(("#", "[[index/"))
            if end_of_section and any(i < t <= j for t in touched):
                i = j
                continue
        result.append(line)
        i += 1
    return "\n".join(result), dropped, stripped


def remaining_links(text: str, removed: set[str]) -> list[str]:
    return sorted({canonical_wiki_target(raw) for raw in WIKI_LINK_RE.findall(text)} & removed)


# ---------------------------------------------------------------- ledger


def _pointer(row_output: dict) -> str:
    return str(row_output.get("pointer") or "").removeprefix(PREFIX)


def ledger_plan(root: Path, brain: Path, removed: set[str]) -> dict:
    rows = ledger_rows(root / LEDGER)
    packages: dict[str, set[str]] = {}
    for row in rows:
        pid = row.get("package_id")
        for output in row.get("outputs") or []:
            if pid and _pointer(output) in removed:
                packages.setdefault(pid, set()).add(_pointer(output))
    partial = []
    for pid in sorted(packages):
        wrote = {_pointer(o) for row in rows if row.get("package_id") == pid for o in row.get("outputs") or []}
        kept = sorted(p for p in wrote - removed if p and (brain / p).exists())
        if kept:
            partial.append({"package_id": pid, "still_in_brain": kept})
    indexes = [i for i, row in enumerate(rows)
               if row.get("package_id") in packages or (not row.get("package_id") and row.get("package") in packages)]
    return {"packages": sorted(packages), "row_indexes": indexes, "rows_total": len(rows), "partial": partial}


def rewrite_ledger(root: Path, drop: list[int], removal_id: str) -> dict:
    """Archive then atomically drop these ledger rows. Caller holds the importer lock."""
    path = root / LEDGER
    raw_lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    rows = [json.loads(line) for line in raw_lines]
    drop_set = set(drop)
    for index in sorted(drop_set):
        append(root / ARCHIVE, {"removal_id": SOURCE + ":" + removal_id, "removed_at": now(), "row": rows[index]})
    kept = [line for i, line in enumerate(raw_lines) if i not in drop_set]
    fd, tmp = tempfile.mkstemp(prefix=".memory_exchange_import.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("".join(line + "\n" for line in kept))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)
    after = len([line for line in path.read_text(encoding="utf-8").splitlines() if line])
    if after != len(raw_lines) - len(drop_set):
        raise RemovalError(f"ledger row count after rewrite is {after}, expected {len(raw_lines) - len(drop_set)}")
    return {"rows_before": len(raw_lines), "rows_removed": len(drop_set), "rows_after": after}


# ---------------------------------------------------------------- plan and proof


def build_plan(brain: Path, root: Path, raws: list[str]) -> dict:
    gathered = gather(brain, raws)
    present = gathered["allowed"]
    removed = set(present) | set(gathered["absent"])
    documents, index_report = {}, {}
    for relative in INDEXES:
        path = brain / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        updated, dropped, stripped = strip_index(text, removed)
        left = remaining_links(updated, removed)
        if left:
            raise RemovalError(f"{relative} still links removed paths after editing: {left}")
        index_report[relative] = {"lines_removed": len(dropped), "links_stripped": stripped}
        if updated != text:
            documents[relative] = updated
    ledger = ledger_plan(root, brain, removed)
    pending = sorted(set(filing.pending_notes(root)) & {PREFIX + p for p in removed}) if (root / filing.LEDGER).exists() else []
    refused = list(gathered["refused"])
    refused += [{"path": PREFIX + p, "reason": f"package {row['package_id']} also wrote this, and it is not on the list"}
                for row in ledger["partial"] for p in row["still_in_brain"]]
    counts: dict[str, int] = {}
    for kind in present.values():
        counts[kind] = counts.get(kind, 0) + 1
    return {"present": present, "absent": gathered["absent"], "duplicates": gathered["duplicates"],
            "refused": refused, "documents": documents, "index_report": index_report, "ledger": ledger,
            "filing_pending_removed": pending, "counts": counts,
            "expected_hashes": {**{rel: digest((brain / rel).read_bytes()) for rel in documents},
                                **{rel: digest((brain / rel).read_bytes()) for rel in present}}}


def removal_gate(vault: Path, removed: set[str]) -> dict:
    """After deletions + INDEX edits: links to removed notes remain only on pages filing regenerates."""
    result = analyze_vault(vault)
    to_removed = [row for row in result["broken_links"] if row["target"] in removed]
    other = [row for row in result["broken_links"] if row["target"] not in removed]
    outside = sorted({row["source"] for row in to_removed if not FILING_MANAGED.fullmatch(row["source"])})
    return {"broken_links_to_removed_on_filing_pages": len(to_removed) - sum(1 for r in to_removed if r["source"] in outside),
            "pages_outside_filing_still_linking": outside, "other_broken_links": other,
            "unreachable": result["unreachable"],
            "passed": not outside and not other and not result["unreachable"]}


def _history_mentions(brain: Path, removed: set[str]) -> list[str]:
    stems = {PurePosixPath(p).name.removesuffix(".md") for p in removed}
    pages = []
    for prefix in HISTORY_PREFIXES:
        for path in sorted((brain / prefix).rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(stem in text for stem in stems):
                pages.append(path.relative_to(brain).as_posix())
    return sorted(pages)


def prove(brain: Path, plan: dict, *, db_path: Path | None, owners=None) -> dict:
    """Apply the plan, then the filing plan, to a vault copy and check the result. The live vault is untouched."""
    removed = set(plan["present"]) | set(plan["absent"])
    with tempfile.TemporaryDirectory(prefix="memory-remove-notes-") as temp:
        copy = Path(temp) / "vault"
        shutil.copytree(brain, copy, ignore=shutil.ignore_patterns(".git"))
        for relative in plan["present"]:
            (copy / relative).unlink()
        for relative, text in plan["documents"].items():
            stamped = brain_memory.apply_provenance(text, source=SOURCE, session_id="dry-run")
            brain_memory.validate_markdown(stamped, relative=relative)
            (copy / relative).write_text(stamped, encoding="utf-8")
        gate = removal_gate(copy, removed)
        before_index = (copy / filing.MEMORY_INDEX).read_text(encoding="utf-8")
        fplan = filing.build_plan(copy, db_path=db_path, owners=owners)
        for relative, text in fplan["changed"].items():
            stamped = brain_memory.apply_provenance(text, source=filing.SOURCE, session_id=filing.SESSION)
            (copy / relative).parent.mkdir(parents=True, exist_ok=True)
            (copy / relative).write_text(stamped, encoding="utf-8")
        notes = [n["relative"] for n in fplan["notes"]]
        checks = filing.vault_checks(copy, before_index=before_index, notes=notes, documents=fplan["documents"])
        survivors = sorted(rel for rel in removed if (copy / rel).exists())
    hubs = sorted(rel for rel in fplan["changed"] if filing.HUB_RE.fullmatch(rel))
    return {"removal_gate": gate, "filing_on_copy": checks, "hubs_affected": hubs,
            "other_navigation_changed": sorted(set(fplan["changed"]) - set(hubs)),
            "removed_still_present_on_copy": survivors,
            "passed": gate["passed"] and checks["passed"] and not survivors}


def summary(plan: dict, proof: dict | None) -> dict:
    report = {"files": {"to_delete": len(plan["present"]), "by_kind": plan["counts"],
                        "already_absent": plan["absent"], "duplicates_ignored": plan["duplicates"]},
              "index_edits": plan["index_report"],
              "ledger": {"packages": len(plan["ledger"]["packages"]), "rows": len(plan["ledger"]["row_indexes"]),
                         "rows_total": plan["ledger"]["rows_total"], "package_ids": plan["ledger"]["packages"]},
              "filing_pending_cleared": plan["filing_pending_removed"],
              "refused": plan["refused"]}
    if proof is not None:
        report["proof"] = proof
    return report


# ---------------------------------------------------------------- orphan records


def orphan_records(brain: Path) -> list[str]:
    """Intake records that no note's `source_record` (or card's `source_path`) points to."""
    records = sorted(p.relative_to(brain).as_posix() for p in (brain / RECORDS).glob("*.md")
                     if re.fullmatch(r"[0-9a-f]{64}\.md", p.name))
    referenced = set()
    for path in brain.rglob("*.md"):
        relative = path.relative_to(brain).as_posix()
        if relative.startswith((RECORDS, ".git/", "_backups/")):
            continue
        fields, _ = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        for key in ("source_record", "source_path"):
            value = str(fields.get(key) or "").removeprefix(PREFIX)
            if value.startswith(RECORDS):
                referenced.add(value)
    return [r for r in records if r not in referenced]


# ---------------------------------------------------------------- run


def run(raws: list[str], *, brain: Path = BUSINESS_BRAIN_ROOT, root: Path = ROOT, apply: bool = False,
        db_path: Path | None = None, owners=None, refresh=None, filing_kwargs=None, orphan_mode: bool = False) -> dict:
    brain, root = Path(brain), Path(root)
    receipt = {"operation": "orphan_records" if orphan_mode else "remove_notes", "apply": apply,
               "timestamp": now(), "token_usage": TOKEN_USAGE}
    if orphan_mode:
        raws = [PREFIX + r for r in orphan_records(brain)]
        receipt["orphan_records"] = [r.removeprefix(PREFIX) for r in raws]
    plan = build_plan(brain, root, raws)
    if not apply:
        proof = prove(brain, plan, db_path=db_path, owners=owners) if plan["present"] or plan["documents"] else None
        receipt.update(summary(plan, proof))
        receipt["history_pages_left_alone"] = _history_mentions(brain, set(plan["present"]))
        receipt["outcome"] = ("refused" if plan["refused"] else
                              "validated" if proof is None or proof["passed"] else "would_fail")
        return receipt
    if plan["refused"]:
        receipt.update(summary(plan, None), outcome="refused")
        return receipt
    removal_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with locked(root / IMPORT_LOCK):
        plan = build_plan(brain, root, raws)  # fresh hashes inside the lock
        if orphan_mode and sorted(plan["present"]) != sorted(r.removeprefix(PREFIX) for r in raws):
            raise RemovalError("orphan set changed while planning")
        proof = prove(brain, plan, db_path=db_path, owners=owners) if plan["present"] or plan["documents"] else None
        receipt.update(summary(plan, proof))
        if plan["refused"] or (proof is not None and not proof["passed"]):
            receipt["outcome"] = "refused" if plan["refused"] else "would_fail"
            _record(root, receipt)
            return receipt
        removed = set(plan["present"]) | set(plan["absent"])
        if plan["present"] or plan["documents"]:
            if brain.resolve() != brain_memory.VAULT_ROOT or not (brain / ".git").is_dir():
                raise RemovalError("removal writes only through the live Brain transaction")

            def gate(_changed):
                result = removal_gate(brain, removed)
                if not result["passed"]:
                    raise RemovalError(f"post-write removal gate failed: {json.dumps(result, sort_keys=True)}")

            write = brain_memory.write_transaction(
                plan["documents"], deletions=sorted(plan["present"]), source=SOURCE,
                session_id=f"{SOURCE}-{removal_id}", expected_hashes=plan["expected_hashes"],
                post_write_validator=gate, attribution=ATTRIBUTION)
            receipt["brain"] = {"commit": write.commit, "sync_status": write.sync_status,
                                "index_status": write.index_status, "changed_paths": list(write.changed_paths),
                                "deleted_paths": list(write.deleted_paths)}
        if plan["ledger"]["row_indexes"]:
            receipt["ledger_rewrite"] = rewrite_ledger(root, plan["ledger"]["row_indexes"], removal_id)
            left = ledger_plan(root, brain, removed)
            if left["row_indexes"]:
                raise RemovalError(f"ledger still holds {len(left['row_indexes'])} rows for removed notes")
        with locked(root / filing.LOCK):
            append(root / filing.LEDGER, {"trigger": f"{SOURCE}:{removal_id}", "dry_run": False, "outcome": "removed",
                                          "notes": sorted(PREFIX + p for p in removed), "token_usage": TOKEN_USAGE,
                                          "timestamp": now()})
        if plan["documents"]:
            from tools.memory_exchange_import import _refresh
            fn = refresh or (lambda pointers: _refresh(pointers, brain, root))
            try:
                search, graph = fn(sorted(PREFIX + rel for rel in plan["documents"]))
            except Exception as exc:
                search, graph = {"status": "pending", "reason": str(exc)}, {"status": "pending"}
            receipt["search_refresh"] = {k: search.get(k) for k in ("status", "reason", "indexed")}
            receipt["graphify_refresh"] = {k: graph.get(k) for k in ("status", "reason", "missing")}
        result = filing.file_notes(None, brain=brain, root=root, trigger=f"{SOURCE}:{removal_id}",
                                   db_path=db_path, owners=owners, **(filing_kwargs or {}))
        receipt["filing"] = {k: result.get(k) for k in ("outcome", "reason", "commit", "changed_paths")}
        ok = (result["outcome"] in {"filed", "unchanged"}
              and receipt.get("graphify_refresh", {"status": "success"}).get("status") == "success")
        receipt["outcome"] = "removed" if ok else "removed_navigation_pending"
        _record(root, receipt)
    return receipt


def _record(root: Path, receipt: dict) -> None:
    append(root / RECEIPTS, receipt)


def _brief(receipt: dict) -> dict:
    out = {k: receipt.get(k) for k in ("operation", "apply", "outcome", "files", "index_edits", "refused",
                                       "filing_pending_cleared", "brain", "ledger_rewrite", "filing",
                                       "search_refresh", "graphify_refresh") if k in receipt}
    if "ledger" in receipt:
        out["ledger"] = {k: v for k, v in receipt["ledger"].items() if k != "package_ids"}
    if "orphan_records" in receipt:
        out["orphan_records"] = receipt["orphan_records"]
    if receipt.get("proof"):
        proof = receipt["proof"]
        out["proof"] = {"passed": proof["passed"], "hubs_affected": proof["hubs_affected"],
                        "other_navigation_changed": proof["other_navigation_changed"],
                        "removal_gate": {k: proof["removal_gate"][k] for k in
                                         ("passed", "broken_links_to_removed_on_filing_pages",
                                          "pages_outside_filing_still_linking", "unreachable")},
                        "filing_on_copy_passed": proof["filing_on_copy"]["passed"],
                        "filing_failed_checks": proof["filing_on_copy"]["failed_checks"]}
    if "history_pages_left_alone" in receipt:
        out["history_pages_left_alone"] = len(receipt["history_pages_left_alone"])
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Remove named old Brain notes for re-ingest (dry run by default)")
    parser.add_argument("paths", nargs="*", help="Brain paths to remove")
    parser.add_argument("--list", type=Path, action="append", default=[], help="file of Brain paths, one per line")
    parser.add_argument("--orphan-records", action="store_true", help="intake records no note points to")
    parser.add_argument("--apply", action="store_true", help="really remove (default is a dry run)")
    parser.add_argument("--dry-run", action="store_true", help="the default; accepted for clarity")
    parser.add_argument("--brain", type=Path, default=BUSINESS_BRAIN_ROOT)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--db", type=Path, help="search database (default: the runtime index)")
    parser.add_argument("--out", type=Path, help="write the full JSON report here")
    parser.add_argument("--overwrite", action="store_true", help="allow --out to replace an existing file")
    parser.add_argument("--json", action="store_true", help="print the full report")
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run are exclusive")
    raws = list(args.paths)
    for path in args.list:
        raws += read_list(path)
    if args.orphan_records and raws:
        parser.error("--orphan-records takes no paths")
    if not raws and not args.orphan_records:
        parser.error("give paths, --list or --orphan-records")
    if args.out and args.out.exists() and not args.overwrite:
        parser.error(f"{args.out} exists; pass --overwrite to replace it")
    try:
        receipt = run(raws, brain=args.brain, root=args.root, apply=args.apply, db_path=args.db,
                      owners=filing.owner_names(), orphan_mode=args.orphan_records)
    except (RemovalError, brain_memory.BrainMemoryError) as exc:
        receipt = {"outcome": "failed", "reason": f"{type(exc).__name__}: {exc}"[-2000:], "apply": args.apply}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt if args.json else _brief(receipt), indent=2, sort_keys=True))
    print(TOKEN_USAGE)
    return 0 if receipt["outcome"] in {"validated", "removed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
