"""Before/after snapshot for the v3 search-ranking change (2026-11-07).

Usage: measure_search_ranking.py <label> [--overwrite]
       measure_search_ranking.py --compare <a.json> <b.json>
Writes <label>.json and tees <label>.txt beside itself; refuses to overwrite.
No model calls.
"""
from __future__ import annotations
import hashlib, json, sqlite3, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
from tools import aos_indexer, aos_entity_index  # noqa: E402

QUERIES = ["how to get my first paying customers", "how often should I post on LinkedIn",
           "lead magnet ideas to collect emails", "who did I talk to about scheduler beta testing"]
CONTROLS = ["Ryan Spencer", "Chris Donnelly", "Kenneth CCI", "Andrea Roberts", "What did Fred say about MLS"]
PERSONS = ["person:ryan-spencer", "person:chris-donnelly"]
V3_RECORDS = ["491e7000399832dc31f7d3e507db9ab751e4155d997f51ca38af8c02ee121d29",
              "098e5a08d7aef17cdd9e87bb76fe5b6ead7c3719d4413bd5c48e37c67569335d",
              "7ded0d7cd9d8447def32df46dec9e1d6ae965917508a787904003a54f2b9c13f",
              "f44cccaace70a48ac05695d64f8889d5d438c84fd4ce97abf6f0f1b01a07808a"]


def top(query, n=3):
    # The exact call David's brain MCP (search_history/_vault_search) and shared_brain_read.search make.
    r = aos_indexer.search(query, source="business_brain", limit=10, client_scope="global")
    return [{"path": row["path"].removeprefix("business_brain:"), "title": row["title"]}
            for g in r["groups"].values() for row in g][:n]


def search_calls_top(query, n=3):
    # David's search_calls: _vault_search(limit=50) filtered to sources/historical_calls/.
    r = aos_indexer.search(query, source="business_brain", limit=50, client_scope="global")
    rows = [row for g in r["groups"].values() for row in g
            if row["path"].startswith("business_brain:sources/historical_calls/")]
    return [row["path"].removeprefix("business_brain:") for row in rows[:n]]


def snapshot() -> dict:
    from tools.business_brain import BUSINESS_BRAIN_ROOT
    from tools.business_brain_scope import load_registry
    from tools.validate_business_brain import analyze_vault
    from tools import context_assembler
    from dashboard.backend.business_brain_graph import BusinessBrainGraphService
    registry = load_registry(aos_indexer.CLIENT_SCOPE_REGISTRY_PATH)
    graph_path = BusinessBrainGraphService(vault_root=BUSINESS_BRAIN_ROOT, registry=registry).published / "graph.json"
    graph_bytes = graph_path.read_bytes()
    graph = json.loads(graph_bytes)
    entities = {}
    for pid in PERSONS:
        view = aos_entity_index.entity_view(pid) or {"knowledge": [], "sources": []}
        entities[pid] = {"knowledge": len(view["knowledge"]), "sources": len(view["sources"]),
                         "paths": sorted(i["path"] for i in view["knowledge"] + view["sources"])}
    conn = sqlite3.connect(f"file:{aos_indexer.DB_PATH}?mode=ro", uri=True)
    tables = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("documents", "entities", "entity_aliases", "entity_links")}
    conn.close()
    vault = analyze_vault(BUSINESS_BRAIN_ROOT)
    titles = {}
    for sha in V3_RECORDS:
        text = (BUSINESS_BRAIN_ROOT / f"sources/intake/records/{sha}.md").read_text(encoding="utf-8")
        titles[sha[:8]] = next(l for l in text.splitlines() if l.startswith("title:"))
    return {
        "queries": {q: top(q) for q in QUERIES},
        "david_search_calls": {QUERIES[3]: search_calls_top(QUERIES[3])},
        "controls": {q: top(q) for q in CONTROLS},
        "david_card_prefetch": {q: context_assembler._card_search_pointers(q, client_scope="global", registry=registry)
                                for q in CONTROLS + QUERIES},
        "graph": {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
                  "sha256": hashlib.sha256(graph_bytes).hexdigest()},
        "entities": entities, "entity_tables": tables,
        "vault": {"status": vault["status"], "canonical_note_count": vault["checks"]["canonical_note_count"],
                  "broken_links": len(vault["broken_links"]), "unreachable": len(vault["unreachable"]),
                  "failed_checks": sorted(k for k, v in vault["checks"].items() if v is False)},
        "v3_record_titles": titles,
    }


INVARIANTS = ("graph", "entities", "entity_tables", "vault")


def compare(a: dict, b: dict) -> list[str]:
    for key in INVARIANTS:
        assert key in a and key in b, f"snapshot missing {key}"
    assert isinstance(a["graph"]["nodes"], int) and isinstance(a["graph"]["edges"], int)
    return [f"{key} differs: {a[key]} != {b[key]}" for key in INVARIANTS if a[key] != b[key]]


def main(argv):
    if argv[:1] == ["--compare"]:
        a, b = (json.loads(Path(p).read_text()) for p in argv[1:3])
        diffs = compare(a, b)
        print("INVARIANTS UNCHANGED: PASS" if not diffs else "INVARIANTS CHANGED: FAIL\n" + "\n".join(diffs))
        return 0 if not diffs else 1
    label = argv[0]
    out_json, out_txt = HERE / f"{label}.json", HERE / f"{label}.txt"
    if (out_json.exists() or out_txt.exists()) and "--overwrite" not in argv:
        print(f"refusing to overwrite {label}.*; pass --overwrite"); return 2
    snap = snapshot()
    out_json.write_text(json.dumps(snap, indent=2) + "\n")
    lines = [f"snapshot {label} (model calls: 0 of declared max 0)"]
    for section in ("queries", "controls"):
        for q, rows in snap[section].items():
            lines.append(f"[{section}] {q}")
            lines += [f"   {i+1}. {r['path']}  |  {r['title'][:70]}" for i, r in enumerate(rows)]
    lines.append(f"[david search_calls] {json.dumps(snap['david_search_calls'], indent=1)}")
    lines.append(f"[david card prefetch] {json.dumps(snap['david_card_prefetch'], indent=1)}")
    for key in INVARIANTS + ("v3_record_titles",):
        value = snap[key]
        if key == "entities":
            value = {k: {kk: vv for kk, vv in v.items() if kk != "paths"} for k, v in value.items()}
        lines.append(f"[{key}] {json.dumps(value)}")
    text = "\n".join(lines) + "\n"
    out_txt.write_text(text); print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
