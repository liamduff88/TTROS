"""Match the re-ingest sources in REINGEST_INVENTORY.md to raw originals in Downloads (2026-11-07).
Read-only: writes match_sources.json/.txt beside itself; refuses to overwrite without --overwrite.
argv[1] = sha256sum listing of Downloads (relative paths). No model calls."""
import json, re, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
OUT = HERE / "match_sources.json"
if OUT.exists() and "--overwrite" not in sys.argv:
    sys.exit("refusing to overwrite match_sources.json")
BRAIN = Path("/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain")
DL = Path("/mnt/c/Users/Admin/Downloads")
listing = [l.split("  ", 1) for l in Path(sys.argv[1]).read_text().splitlines()]
by_sha = {}
for h, p in listing:
    by_sha.setdefault(h, []).append(p.removeprefix("./"))
inv = (Path.home() / "ttros-memory-audit/REINGEST_INVENTORY.md").read_text()
SKIP = {"V15", "V16", "I12", "I13", "I14"}

def git_sha(note):  # legacy notes were removed in Brain 0608f73; read the frontmatter from its parent
    text = subprocess.run(["git", "-C", str(BRAIN), "show", f"0608f73^:sources/historical_calls/{note}"],
                          capture_output=True, text=True, check=True).stdout
    return re.search(r"^source_sha256: ([0-9a-f]{64})$", text, re.M).group(1)

rows = []
for line in inv.splitlines():
    m = re.match(r"\| (V\d+|L\d+|I\d+) \|", line)
    if not m or m.group(1) in SKIP:
        continue
    sid = m.group(1); cells = [c.strip() for c in line.split(" | ")]
    src = cells[1]
    if sid.startswith("V"):
        filename = re.sub(r"\s*\(([0-9a-f]{8}),.*$", "", src)
        filename = re.sub(r", (Sep|Oct|Nov) \d+$", "", filename)
        sha = re.search(r"\(([0-9a-f]{8}),", src)
        sha = sha.group(1) if sha else None
        who = cells[3]
        if sid == "V14":
            sha = re.search(r"sha ([0-9a-f]{8})", line).group(1)
            filename = re.search(r"Downloads\\([^()]+?\.txt)", line).group(1)
    elif sid.startswith("L"):
        filename = src
        note = re.findall(r"`([^`]+\.md)`", cells[2])[0]
        sha = git_sha(note); who = cells[3]
    else:
        filename = re.sub(r"\s*\(.*$", "", src)
        sha = re.search(r"records/([0-9a-f]{64})\.md", line).group(1)
        who = cells[3] + (f" — {re.search(r'\((.*)\)', src).group(1)}" if "(" in src else "")
    hits = sorted({p for h, ps in by_sha.items() if sha and h.startswith(sha) for p in ps})
    how = "sha256"
    if not hits:
        how = "filename"
        hits = sorted(p for _, p0 in listing for p in [p0.removeprefix("./")] if Path(p).name.lower() == filename.lower())
    rows.append({"id": sid, "who": re.sub(r"<br>|\*", " ", who)[:80], "filename": filename, "sha": sha,
                 "match": how if hits else "none", "hits": hits})
assert len(rows) == 40, len(rows)
OUT.write_text(json.dumps(rows, indent=1) + "\n")
lines = [f"{i+1:02d} {r['id']:4} {r['match']:8} n={len(r['hits'])} {r['filename'][:60]} -> {r['hits'][:3]}" for i, r in enumerate(rows)]
text = "\n".join(lines) + "\n"
(HERE / "match_sources.txt").write_text(text); print(text)
