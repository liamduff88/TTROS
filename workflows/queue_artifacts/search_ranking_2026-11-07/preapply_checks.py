"""Pre-apply checks (a) and (b) for the remove_list.txt removal, 2026-11-07. Read-only; no model calls.
Tees preapply_checks.txt beside itself; refuses to overwrite without --overwrite."""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from tools import memory_remove_notes as R, source_intake
from tools.business_brain import BUSINESS_BRAIN_ROOT as BRAIN
out_path = HERE / "preapply_checks.txt"
if out_path.exists() and "--overwrite" not in sys.argv:
    sys.exit("refusing to overwrite preapply_checks.txt")
AUDIT = Path.home() / "ttros-memory-audit"
removed = {l.strip() for l in (AUDIT / "remove_list.txt").read_text().splitlines() if l.strip()}
rows = R.ledger_rows(ROOT / R.LEDGER)
plan = R.ledger_plan(ROOT, BRAIN, removed)
drop = set(plan["row_indexes"]); kept = [r for i, r in enumerate(rows) if i not in drop]
lines = [f"ledger rows {len(rows)}; dropped {len(drop)} in {len(plan['packages'])} packages; left {len(kept)}"]
assert isinstance(len(drop), int) and len(plan["packages"]) == 35, plan["packages"]

# The 40 re-ingest sources from REINGEST_INVENTORY.md (V1-V14, L1-L15, I1-I11).
inv = (AUDIT / "REINGEST_INVENTORY.md").read_text()
sources = []
for line in inv.splitlines():
    m = re.match(r"\| (V\d+|L\d+|I\d+) \|", line)
    if not m or m.group(1) in {"V15", "V16", "I12", "I13", "I14"}:
        continue
    sid = m.group(1); cells = line.split(" | ")
    files = re.findall(r"`([^`]+\.md)`", cells[2])
    if sid.startswith("I"):
        full = re.search(r"records/([0-9a-f]{64})\.md", line).group(1)
        pointers = {f"sources/intake/cards/{full}.card.md"}; shas = [full]
    else:
        pointers = {f"sources/historical_calls/{f}" for f in files}
        shas = re.findall(r"\(([0-9a-f]{8}),", cells[1])
        if sid.startswith("L"):
            note = next(p for p in pointers if "/cards/" not in p)
            shas = [source_intake._frontmatter(BRAIN / note)["source_sha256"]] if (BRAIN / note).exists() else shas
    sources.append((sid, cells[1].strip()[:60], pointers, shas))
assert len(sources) == 40, len(sources)

def touches(row, pointers, shas):
    hit_ptr = {R._pointer(o) for o in row.get("outputs") or []} & pointers
    blob = json.dumps({k: row.get(k) for k in ("package_id", "package", "source", "source_folder", "record", "fingerprint")})
    hit_sha = [s for s in shas if s[:8] in blob]
    return hit_ptr, hit_sha

no_rows, blocking = [], []
for sid, name, pointers, shas in sources:
    in_drop = [r for i, r in enumerate(rows) if i in drop and any(touches(r, pointers, shas))]
    left = [(r.get("package_id") or r.get("package"), *touches(r, pointers, shas)) for r in kept if any(touches(r, pointers, shas))]
    not_listed = sorted(pointers - removed)
    lines.append(f"{sid:4} rows_in_35={len(in_drop):3} rows_left={len(left)} not_in_remove_list={not_listed} | {name}")
    if not in_drop: no_rows.append(sid)
    if left: blocking.append((sid, left))
lines.append(f"(a) sources with no ledger rows in the 35 packages: {len(no_rows)}: {' '.join(no_rows)}")
lines.append(f"(a) sources with a ledger row left after removal: {len(blocking)} {blocking}")

# (b) nothing under a v3 folder, and no record a v3 note's source_record points to.
v3_folders, v3_records = set(), set()
for index in (BRAIN / "sources/historical_calls").glob("*/INDEX.md"):
    if source_intake._frontmatter(index).get("type") == "source_index":
        v3_folders.add(index.parent.relative_to(BRAIN).as_posix() + "/")
        for note in index.parent.glob("*.md"):
            ref = source_intake._frontmatter(note).get("source_record", "")
            if ref: v3_records.add(ref.removeprefix("business_brain:"))
under_v3 = sorted(p for p in removed if any(p.startswith(f) for f in v3_folders))
v3_rec = sorted(removed & v3_records)
lines.append(f"(b) v3 folders {len(v3_folders)}, v3 records {len(v3_records)}: {sorted(v3_records)}")
lines.append(f"(b) remove_list paths {len(removed)}; under a v3 folder: {len(under_v3)} {under_v3}; v3 source_record: {len(v3_rec)} {v3_rec}")
lines.append(f"(b) remove_list records: {sorted(p for p in removed if p.startswith('sources/intake/records/'))}")
text = "\n".join(lines) + "\n"; out_path.write_text(text); print(text)
