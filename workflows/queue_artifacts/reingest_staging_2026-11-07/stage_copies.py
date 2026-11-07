"""Copy (never move) the 40 re-ingest originals from Downloads into TTROS Reingest and write CHECKLIST.md.
Refuses to run if the destination folder already exists. Tees stage_copies.txt. No model calls."""
import hashlib, json, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
DL = Path("/mnt/c/Users/Admin/Downloads")
DEST = Path("/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Reingest")
if DEST.exists():
    sys.exit(f"refusing: {DEST} already exists")
rows = json.loads((HERE / "match_sources.json").read_text())
# Chosen copy where Downloads holds byte-identical duplicates (name that matches the inventory),
# and the content matches for I4-I8 (same text after whitespace/line-ending normalisation).
CHOICE = {"V2": "Meeting wit Arpi.txt", "L7": "hermes_water_treatment_system_summary_for_trent.md",
          "I1": "Fred Haiderzada meeting sept 9th.txt", "I10": "personal-brand-strategy (1).md"}
CONTENT = {"I4": "2nd meeting with Fred.txt", "I5": "meeting with Santosh from Deliger digital.txt",
           "I6": "meeting_saved_new_chat WRN 2.txt", "I7": "AI franchise model.txt",
           "I8": "Dan Koe, Eden and content strategy set up.txt"}
WHO = {"V1": "Dr Kenneth Moodley, Nikshen, CCI (Sep 18)", "V2": "Arpi (SEO specialist)", "V3": "Grand Connection group",
       "V4": "Fred Haiderzada, dashboard walkthrough (Sep 30)", "V5": "Fred Haiderzada, dashboard (Oct 1)",
       "V6": "Video: 8 GitHub repos", "V7": "Video: selling talking websites", "V8": "Jenny Holly Hansen (BUN)",
       "V9": "Jake Van Clief: do you need AI agents", "V10": "Greg Isenberg: 1-person AI business",
       "V11": "Video: one client pays $15K/month", "V12": "Amber Noakes (barter network)",
       "V13": "Video: GTM expert (Alex, Frontal)", "V14": "John / Jean Bach (identity unconfirmed)",
       "L1": "Andrea Roberts", "L2": "Andrea (second call)", "L3": "Dr Kenneth Moodley after 2nd CCI call",
       "L4": "Kenneth Moodley after 1st CCI call", "L5": "CCI second call (Ollie, Kenneth)", "L6": "CCI first call",
       "L7": "Trent / Lance: water treatment summary (document)", "L8": "Kenneth Moodley (Jun 30)",
       "L9": "Kenneth Moodley (May 27)", "L10": "Kenneth Moodley: SME (Jun 18)", "L11": "Ken Stanick (Quinn)",
       "L12": "Mike Knapp: MSP GTM context (summary)", "L13": "Mike Knapp (Jul 21)", "L14": "Trent MacGregor (1st call)",
       "L15": "Trent MacGregor (Jul 9)", "I1": "Fred Haiderzada (Sep 9)", "I2": "Keith Daser (Deliver Digital)",
       "I3": "Fred Haiderzada: system walkthrough (Sep 22)", "I4": "Fred Haiderzada: AI agent / CMA (Sep 15)",
       "I5": "Santosh (Deliver Digital, Sep 15)", "I6": "Zoom chat log (Kendol Mason, Sep 19)",
       "I7": "Video: AI business, 7.5 years", "I8": "Video: Eden / Dan Koe content strategy",
       "I9": "Fred: Hermes real-estate assistant brief (document)", "I10": "Liam: personal brand strategy (document)",
       "I11": "Liam: weekly ideas (Sep 13)"}
assert len(rows) == 40 and set(WHO) == {r["id"] for r in rows}
DEST.mkdir(parents=True)
out, check = [], ["# TTROS re-ingest checklist", "",
                  "Copies of the raw originals from Downloads (originals untouched). One ChatGPT chat per source.", "",
                  "| # | ID | Person or topic | File | Status |", "|---|---|---|---|---|"]
for n, r in enumerate(rows, 1):
    sid = r["id"]
    if sid in CONTENT:
        src, how = CONTENT[sid], "content (same text, whitespace differs)"
    else:
        src = CHOICE.get(sid) or (r["hits"][0] if len(r["hits"]) == 1 else None)
        how = "sha256"
        assert src in r["hits"], (sid, r["hits"])
    source = DL / src
    target = DEST / f"{n:02d}_{sid}_{Path(src).name}"
    shutil.copy2(source, target)
    a, b = (hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, target))
    assert a == b and source.exists(), sid
    if how == "sha256":
        assert a.startswith(r["sha"]), (sid, a, r["sha"])
    out.append(f"{n:02d} {sid:4} {how:9} {a[:12]} {target.name}")
    check.append(f"| {n:02d} | {sid} | {WHO[sid]} | {target.name} | not done |")
(DEST / "CHECKLIST.md").write_text("\n".join(check) + "\n", encoding="utf-8")
text = "\n".join(out) + f"\ncopied {len(out)}; checklist lines {len(check) - 6}\n"
(HERE / "stage_copies.txt").write_text(text); print(text)
