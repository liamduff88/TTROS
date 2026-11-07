"""Memory filing (F1, F2, F4, F5) and its importer integration. Temp-dir vaults only.

Revisit: when person hub rules or the D1 navigation policy change. · Last touched: 2026-11-06.
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import brain_memory, memory_filing as F
from tools.memory_exchange_import import process
from tools.validate_business_brain import analyze_vault

MACHINE = ("<!-- TTROS:MACHINE:block-2-outcome-index:BEGIN -->\n## Machine-maintained verified outcomes\n\n"
           "- Outcome one.\n<!-- TTROS:MACHINE:block-2-outcome-index:END -->\n")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def note(id_, title, extra=""):
    return f'---\nid: {id_}\ntype: knowledge\ntitle: "{title}"\nobserved_at: 2026-11-04T18:03:00Z\n{extra}---\n# {title}\n\nEvidence.\n'


NOTES = {
    "ryan-a.md": note("ryan-a", "Ryan Spencer / Liam — beta", 'participants_text: "Liam Duff; Ryan Spencer"\nentity_key: person:ryan-spencer\nknowledge_type: historical_evidence\n'),
    "ryan-b.md": note("ryan-b", "Ryan Spencer / Liam — scheduler", "entity_key: person:ryan-spencer\n"),
    "mcveigh.md": note("mcveigh", "Ryan McVeigh pilot", 'participants_text: "Liam Duff; Ryan McVeigh"\n'),
    "kenneth.md": note("kenneth", "Call with Kenneth", 'participants_text: "Liam Duff; Kenneth (surname absent from metadata)"\nentity_key: person:kenneth-moodley\n'),
    "andrea.md": note("andrea", "Andrea second call", 'participants_text: "Liam Duff; Andrea (surname inferred)"\n'),
    "prose.md": note("prose", "First CCI call", 'participants_text: "Liam Duff; CCI participants not individually attributable"\n'),
    "tokeni.md": note("tokeni", "Tokeni call", 'participants_text: "Liam Duff; Tokeni Smith"\n'),
    "career.md": note("career", "Liam career", "entity_key: person:liam-duff\n"),
}


def vault(brain, notes=NOTES, *, link_notes=True):
    write(brain / "README.md", "---\nid: readme\n---\n# Brain\n\n[[index/MEMORY_INDEX|Memory Index]]\n")
    write(brain / "index/MEMORY_INDEX.md", "---\nid: memory-index\ntype: index\n---\n# Memory Index\n\n[[README]]\n"
          + MACHINE + "\n## Historical source intake\n\n[[sources/historical_calls/INDEX|Historical calls]]\n")
    links = "".join(f"- [[sources/historical_calls/{name[:-3]}|{name}]]\n" for name in sorted(notes)) if link_notes else ""
    write(brain / "sources/historical_calls/INDEX.md",
          "---\nid: hc-index\ntype: index\n---\n# Historical Calls — Records Index\n\n" + links + "\n[[index/MEMORY_INDEX|Memory Index]]\n")
    for name, text in notes.items():
        write(brain / "sources/historical_calls" / name, text)
    write(brain / "inbox/distilled_packets/shared-submit-abc.md",
          '---\nid: shared-submit-abc\ntype: decision\nstatus: unconfirmed\ntitle: "Ryan beta decision"\n'
          'source_refs: ["business_brain:sources/historical_calls/ryan-a.md"]\n---\n# Ryan beta decision\n')
    for name in ("app.json", "appearance.json", "core-plugins.json", "workspace.json"):
        write(brain / ".obsidian" / name, "{}\n")
    write(brain / ".obsidian/graph.json", json.dumps({"search": "-path:_backups"}) + "\n")


class Registry:
    """search_source_identities for the D1 targets: MEMORY_INDEX by path, people/ by prefix."""

    def __init__(self, people=True):
        self.people = people

    def scope_for_search_identity(self, source, path):
        if source != "business_brain":
            return None
        if path == "business_brain:index/MEMORY_INDEX.md" or (self.people and path.startswith("business_brain:people/")):
            return "global"
        return None


def ok_refresh(pointers):
    return {"status": "success"}, {"status": "success", "coverage": [{"pointer": p} for p in pointers]}


def ok_verify(plan, hubs):
    return {"passed": True, "problems": [], "hubs": [h["entity_id"] for h in hubs]}


def bad_verify(plan, hubs):
    return {"passed": False, "problems": ["person:ryan-spencer resolves to no person"], "hubs": []}


def head(brain):
    return subprocess.check_output(["git", "-C", str(brain), "rev-parse", "HEAD"], text=True).strip()


class IdentityRuleTests(unittest.TestCase):
    def notes(self, rows):
        return [{"relative": f"sources/historical_calls/{k}.md", "pointer": f"business_brain:sources/historical_calls/{k}.md",
                 "keys": keys, "participants": parts} for k, keys, parts in rows]

    def test_exact_keys_owner_first_names_prose_and_indexer_exclusions(self):
        result = F.resolve_identities(self.notes([
            ("a", ["person:ryan-spencer"], "Liam Duff; Ryan Spencer"),
            ("b", [], "Liam Duff; Ryan McVeigh"),
            ("c", ["person:kenneth-moodley"], "Liam Duff; Kenneth (surname absent from metadata)"),
            ("d", [], "Liam Duff; Andrea (surname inferred)"),
            ("e", [], "Liam Duff; CCI participants not individually attributable"),
            ("f", [], "Liam Duff; Tokeni Smith"),
            ("g", ["person:liam-duff"], ""),
            ("h", [], "Liam Duff; Ryan"),
        ]), hubs={}, people={})
        by = result["by_note"]
        self.assertEqual({"person:ryan-spencer"}, by["sources/historical_calls/a.md"])
        self.assertEqual({"person:ryan-mcveigh"}, by["sources/historical_calls/b.md"], "never merged with Ryan Spencer")
        self.assertEqual({"person:kenneth-moodley"}, by["sources/historical_calls/c.md"])
        self.assertNotIn("sources/historical_calls/g.md", by, "the owner gets no hub")
        self.assertFalse(any("person:liam-duff" in ids for ids in by.values()))
        needs = {(n["name"], n["reason"]) for n in result["needs"]}
        self.assertIn(("Andrea (surname inferred)", "first name only"), needs)
        self.assertIn(("Ryan", "first name only"), needs, "a bare Ryan is never guessed")
        self.assertIn(("Tokeni Smith", "hub path would be skipped by the search indexer"), needs)
        self.assertEqual([{"note": "business_brain:sources/historical_calls/c.md",
                           "participant": "Kenneth (surname absent from metadata)"}], result["covered"])
        self.assertEqual(["CCI participants not individually attributable"], [u["segment"] for u in result["unparsed"]])
        for row in result["needs"]:
            self.assertNotRegex(row["reason"], r"(?i)token|secret|credential|password", "reasons must stay searchable")

    def test_multi_match_goes_to_needs_identity(self):
        hubs = {"person:ryan-x": {"title": "Ryan X", "aliases": ["Ryan Spencer"]}}
        people = {"person:ryan-spencer": {"title": "Ryan Spencer", "aliases": {"Ryan Spencer"}}}
        result = F.resolve_identities(self.notes([("a", [], "Ryan Spencer")]), hubs=hubs, people=people)
        self.assertEqual({}, result["by_note"])
        self.assertEqual("matches more than one person: person:ryan-spencer, person:ryan-x", result["needs"][0]["reason"])
        single = F.resolve_identities(self.notes([("a", [], "Ryan Spencer")]), hubs={}, people=people)
        self.assertEqual({"person:ryan-spencer"}, single["by_note"]["sources/historical_calls/a.md"])

    def test_owner_is_configurable(self):
        rows = self.notes([("a", [], "Liam Duff; Ryan Spencer")])
        self.assertEqual({"person:liam-duff"}, F.resolve_identities(rows, hubs={}, people={}, owners=("Ryan Spencer",))["by_note"]["sources/historical_calls/a.md"])
        with mock.patch.dict(os.environ, {F.OWNERS_ENV: "Liam Duff; Ryan Spencer"}):
            self.assertEqual(("Liam Duff", "Ryan Spencer"), F.owner_names())
            self.assertEqual({}, F.resolve_identities(rows, hubs={}, people={}, owners=F.owner_names())["by_note"])


class FilingTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.brain = (self.root / "TTROS Business Brain").resolve()
        self.db = self.root / "search/os_index.db"  # absent: no entity-index persons

    def git_brain(self, **kwargs):
        vault(self.brain, **kwargs)
        subprocess.run(["git", "init", "-q", str(self.brain)], check=True)
        subprocess.run(["git", "-C", str(self.brain), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.brain), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "fixture"], check=True)
        for patcher in (mock.patch.object(brain_memory, "VAULT_ROOT", self.brain),
                        mock.patch("tools.brain_git_closure.push_commit", return_value="local_only"),
                        mock.patch("tools.brain_git_closure.record"),
                        mock.patch("tools.aos_indexer.index_one", return_value={"status": "success"}),
                        mock.patch("tools.aos_entity_index.ensure_current"),
                        mock.patch.dict(os.environ, {F.FLAG: "1"})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def file(self, notes=None, **kwargs):
        options = dict(brain=self.brain, root=self.root, db_path=self.db, registry=Registry(),
                       refresh=ok_refresh, verifier=ok_verify)
        options.update(kwargs)
        return F.file_notes(notes, **options)

    def ledger(self):
        path = self.root / F.LEDGER
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_dry_run_proves_the_plan_on_a_copy_and_writes_nothing(self):
        self.git_brain()
        before = {p: p.read_bytes() for p in self.brain.rglob("*") if p.is_file() and ".git" not in p.parts}
        receipt = self.file(dry_run=True)
        self.assertEqual("validated", receipt["outcome"], receipt.get("reason"))
        self.assertEqual(before, {p: p.read_bytes() for p in self.brain.rglob("*") if p.is_file() and ".git" not in p.parts})
        self.assertFalse((self.root / F.LEDGER).exists(), "dry-run records nothing")
        self.assertTrue(receipt["on_copy"]["passed"])
        hubs = {h["entity_id"]: h["count"] for h in receipt["plan"]["hubs"]}
        self.assertEqual({"person:kenneth-moodley": 1, "person:ryan-mcveigh": 1, "person:ryan-spencer": 2}, hubs)
        self.assertTrue(any(line.startswith("+- [[people/INDEX|People]]") for line in receipt["memory_index_diff"]))

    def test_all_writes_hubs_indexes_and_memory_index_in_one_commit(self):
        self.git_brain()
        before_head = head(self.brain)
        receipt = self.file()
        self.assertEqual("filed", receipt["outcome"], receipt.get("reason"))
        changed = subprocess.check_output(["git", "-C", str(self.brain), "show", "--name-only", "--format=", "HEAD"], text=True).split()
        self.assertEqual(sorted(["index/MEMORY_INDEX.md", "people/INDEX.md", "people/NEEDS_IDENTITY.md", "people/kenneth-moodley.md",
                                 "people/ryan-mcveigh.md", "people/ryan-spencer.md"]), sorted(changed))
        self.assertEqual(before_head, subprocess.check_output(["git", "-C", str(self.brain), "rev-parse", "HEAD~1"], text=True).strip(),
                         "one transaction, one commit")
        hub = (self.brain / "people/ryan-spencer.md").read_text(encoding="utf-8")
        fields, _ = brain_memory.parse_frontmatter(hub)
        self.assertEqual(("person-ryan-spencer", "person", "person:ryan-spencer", "Ryan Spencer", ["Ryan Spencer"]),
                         (fields["id"], fields["type"], fields["entity_key"], fields["title"], fields["aliases"]))
        self.assertIn("- [[sources/historical_calls/ryan-a|Ryan Spencer / Liam — beta]] · observed 2026-11-04 · historical_evidence\n", hub)
        self.assertIn("- [[sources/historical_calls/ryan-b|Ryan Spencer / Liam — scheduler]] · observed 2026-11-04 · historical_evidence\n", hub)
        # D3: a submit record is a plain pointer, never a wiki-link
        self.assertIn("- `business_brain:inbox/distilled_packets/shared-submit-abc.md` · Ryan beta decision", hub)
        self.assertNotIn("[[inbox/", hub)
        section = re.search(r"<!-- TTROS:HERMES:generated-navigation:BEGIN -->[\s\S]*?:END -->", hub).group(0)
        self.assertNotRegex(section, r"\d{4}-\d\d-\d\dT\d\d:", "no timestamps inside sections")
        self.assertNotIn("liam-duff", " ".join(changed))
        mcveigh = (self.brain / "people/ryan-mcveigh.md").read_text(encoding="utf-8")
        self.assertIn("mcveigh|Ryan McVeigh pilot", mcveigh)
        self.assertNotIn("ryan-a", mcveigh)
        index = (self.brain / "people/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("- [[people/ryan-spencer|Ryan Spencer]] · 2 records · latest 2026-11-04", index)
        self.assertIn("[[people/NEEDS_IDENTITY|Needs identity]] · 2 names filing could not tie to one person", index)
        needs = (self.brain / "people/NEEDS_IDENTITY.md").read_text(encoding="utf-8")
        self.assertIn("- Andrea (surname inferred) · first name only · `business_brain:sources/historical_calls/andrea.md`", needs)
        self.assertIn("- Tokeni Smith · hub path would be skipped by the search indexer", needs)
        memory_index = (self.brain / "index/MEMORY_INDEX.md").read_text(encoding="utf-8")
        self.assertIn(MACHINE, memory_index, "machine block byte-identical")
        self.assertIn("- [[people/INDEX|People]] · 3 person hubs · 2 names needing identity", memory_index)
        self.assertIn("- [[sources/historical_calls/INDEX|Historical Calls — Records Index]] · 8 linked notes", memory_index)
        result = analyze_vault(self.brain)
        self.assertEqual("PASS", result["status"])
        self.assertTrue(receipt["verify"]["vault"]["passed"])
        self.assertEqual([], receipt["verify"]["vault"]["notes_beyond_two_hops_of_memory_index"])
        self.assertEqual(2, result["root_distances"]["people/ryan-spencer.md"])
        self.assertEqual(["filed"], [row["outcome"] for row in self.ledger()])

    def test_second_run_is_unchanged_and_writes_nothing(self):
        self.git_brain()
        self.assertEqual("filed", self.file()["outcome"])
        after = head(self.brain)
        bytes_after = {p: p.read_bytes() for p in (self.brain / "people").glob("*.md")}
        second = self.file()
        self.assertEqual("unchanged", second["outcome"])
        self.assertEqual([], second["documents"])
        self.assertEqual(after, head(self.brain))
        self.assertEqual(bytes_after, {p: p.read_bytes() for p in (self.brain / "people").glob("*.md")})
        self.assertEqual({"outcome": "nothing_pending"}, F.retry_pending(brain=self.brain, root=self.root))

    def test_dates_say_what_they_are_and_import_dates_never_count_as_latest(self):
        write(self.root / "v/x.md", '---\nid: x\nsource_date_text: "Jun 30"\nimported_at: "2026-08-17"\n---\n# X\n')
        write(self.root / "v/y.md", '---\nid: y\nimported_at: "2026-08-17"\n---\n# Y\n')
        write(self.root / "v/z.md", '---\nid: z\n---\n# Z\n')
        rows = {name: F._read_note(self.root / "v", f"{name}.md") for name in "xyz"}
        self.assertEqual(("2026-06-30", "2026-06-30"), (rows["x"]["date"], rows["x"]["date_label"]))
        self.assertEqual(("", "imported 2026-08-17"), (rows["y"]["date"], rows["y"]["date_label"]))
        self.assertEqual(("", "undated"), (rows["z"]["date"], rows["z"]["date_label"]))

    def test_render_is_deterministic(self):
        self.git_brain()
        first, second = F.build_plan(self.brain, db_path=self.db), F.build_plan(self.brain, db_path=self.db)
        self.assertEqual({k: F._strip_stamp(v) for k, v in first["documents"].items()},
                         {k: F._strip_stamp(v) for k, v in second["documents"].items()})

    def test_scope_check_refuses_targets_outside_search_identities(self):
        self.git_brain()
        before = head(self.brain)
        receipt = self.file(registry=Registry(people=False))
        self.assertEqual("filing_failed", receipt["outcome"])
        self.assertIn("not covered by search_source_identities: people/", receipt["reason"])
        self.assertEqual(before, head(self.brain))
        self.assertFalse((self.brain / "people").exists())
        with self.assertRaisesRegex(F.FilingError, "not a D1 navigation target"):
            F.check_scope(["memory/clients.md"], Registry())

    def test_post_write_gate_failure_rolls_back(self):
        self.git_brain(link_notes=False)  # the historical INDEX links no note, so none is within two hops
        before = head(self.brain)
        receipt = self.file()
        self.assertEqual("filing_failed", receipt["outcome"])
        self.assertIn("post-write vault gate failed", receipt["reason"])
        self.assertEqual(before, head(self.brain))
        self.assertFalse((self.brain / "people/ryan-spencer.md").exists())
        self.assertEqual("", subprocess.check_output(["git", "-C", str(self.brain), "status", "--porcelain"], text=True))

    def test_failed_verification_is_recorded_and_retried(self):
        self.git_brain()
        first = self.file(verifier=bad_verify)
        self.assertEqual("filing_failed", first["outcome"])
        self.assertIn("resolves to no person", first["reason"])
        self.assertIn("business_brain:sources/historical_calls/ryan-a.md", F.pending_notes(self.root))
        # an identical failing retry is not re-recorded
        F.retry_pending(brain=self.brain, root=self.root, db_path=self.db, registry=Registry(), refresh=ok_refresh, verifier=bad_verify)
        F.retry_pending(brain=self.brain, root=self.root, db_path=self.db, registry=Registry(), refresh=ok_refresh, verifier=bad_verify)
        self.assertEqual(["filing_failed", "filing_failed"], [r["outcome"] for r in self.ledger()])
        retried = F.retry_pending(brain=self.brain, root=self.root, db_path=self.db, registry=Registry(), refresh=ok_refresh, verifier=ok_verify)
        self.assertEqual("filed", retried["outcome"], retried.get("reason"))
        self.assertEqual([], F.pending_notes(self.root))

    def test_refresh_pending_is_filing_pending_and_retried(self):
        self.git_brain()
        pending = self.file(refresh=lambda p: ({"status": "success"}, {"status": "pending", "reason": "Graphify build did not succeed"}))
        self.assertEqual("filing_pending", pending["outcome"])
        self.assertTrue(pending["commit"], "the navigation commit stands; only the refresh is retried")
        seen = []
        retried = F.retry_pending(brain=self.brain, root=self.root, db_path=self.db, registry=Registry(),
                                  refresh=lambda p: (seen.append(p), ok_refresh(p))[1], verifier=ok_verify)
        self.assertEqual("filed", retried["outcome"])
        self.assertIn("business_brain:people/ryan-spencer.md", seen[0], "the retry refreshes the hubs again")


class ImporterIntegrationTests(unittest.TestCase):
    """Filing runs after the import transaction and refresh; it never blocks or undoes the import."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.brain = (self.root / "TTROS Business Brain").resolve()
        vault(self.brain, notes={})
        subprocess.run(["git", "init", "-q", str(self.brain)], check=True)
        subprocess.run(["git", "-C", str(self.brain), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.brain), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "fixture"], check=True)
        for patcher in (mock.patch.object(brain_memory, "VAULT_ROOT", self.brain),
                        mock.patch("tools.brain_git_closure.push_commit", return_value="local_only"),
                        mock.patch("tools.brain_git_closure.record"),
                        mock.patch("tools.aos_indexer.index_one", return_value={"status": "success"}),
                        mock.patch("tools.aos_entity_index.ensure_current"),
                        mock.patch.dict(os.environ, {F.FLAG: "1"})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.db = self.root / "search/os_index.db"

    def package(self, participants, name="ryan-new"):
        pkg = self.root / "ready" / f"MI-{name}"
        rel = f"historical/{name}.md"
        payload = note(f"icm-{name}", f"Ryan Spencer / Liam — {name}", f'participants_text: "{participants}"\n').encode()
        write(pkg / rel, payload.decode())
        manifest = {
            "schema_version": "2.0", "semantic_contract_version": "2.0.0", "reconciliation_contract_version": "2.0.0",
            "transport_mode": "directory-v1", "status": "ready_for_ttros", "package_id": pkg.name, "batch_id": name,
            "batch_fingerprint_sha256": sha(name.encode()), "package_disposition": "evidence_only", "source_count": 1,
            "sources": [{"source_id": "SRC-001", "role": "batch_input", "title": "call"}],
            "canonical_comparison": {"status": "partial"}, "has_conflicts": False, "requires_human_review": False,
            "output_count": 1, "knowledge_types_present": ["historical_evidence"],
            "package_files": [{"path": rel, "size_bytes": len(payload), "sha256": sha(payload)}],
            "outputs": [{"package_path": rel, "size_bytes": len(payload), "sha256": sha(payload), "source_ids": ["SRC-001"],
                         "requires_human_review": False, "conflict_ids": [], "operation": "historical_record",
                         "temporal_posture": "historical",
                         "target": {"namespace": "historical", "suggested_relative_path": rel,
                                    "canonical_ref": None, "expected_base_sha256": None}}],
        }
        (pkg / "INGEST_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        return pkg

    def filing(self, verifier=ok_verify):
        return lambda pointers, **kw: F.file_imported(pointers, **kw, db_path=self.db, registry=Registry(),
                                                      refresh=ok_refresh, verifier=verifier)

    def run_import(self, pkg, filing):
        return process(pkg, brain=self.brain, root=self.root, refresh=ok_refresh, filing=filing)

    def import_ledger(self):
        return [json.loads(l) for l in (self.root / "queue/receipts/memory_exchange_import.jsonl").read_text().splitlines()]

    def test_success_files_after_the_import_commit(self):
        row = self.run_import(self.package("Liam Duff; Ryan Spencer"), self.filing())
        self.assertEqual("imported", row["outcome"], row.get("reason"))
        self.assertEqual("filed", row["filing"]["status"], row["filing"])
        self.assertNotEqual(row["commit"], row["filing"]["commit"], "filing is its own transaction, after the import's")
        parent = subprocess.check_output(["git", "-C", str(self.brain), "rev-parse", "HEAD~1"], text=True).strip()
        self.assertEqual(row["commit"], parent)
        hub = (self.brain / "people/ryan-spencer.md").read_text(encoding="utf-8")
        self.assertIn("[[sources/historical_calls/ryan-new|", hub)
        self.assertEqual("filed", self.import_ledger()[-1]["filing"]["status"])
        self.assertEqual("PASS", analyze_vault(self.brain)["status"])

    def test_failure_leaves_the_import_imported_and_the_next_poll_retries(self):
        row = self.run_import(self.package("Liam Duff; Ryan Spencer"), self.filing(verifier=bad_verify))
        self.assertEqual("imported", row["outcome"])
        self.assertEqual("pending", row["filing"]["status"])
        self.assertTrue((self.brain / "sources/historical_calls/ryan-new.md").is_file(), "the import is never undone")
        self.assertEqual(["business_brain:sources/historical_calls/ryan-new.md"], F.pending_notes(self.root))
        retried = F.retry_pending(brain=self.brain, root=self.root, db_path=self.db, registry=Registry(), refresh=ok_refresh, verifier=ok_verify)
        self.assertEqual("filed", retried["outcome"])
        self.assertEqual([], F.pending_notes(self.root))

    def test_a_filing_crash_is_recorded_pending_and_retried(self):
        def crash(pointers, **kw):
            raise RuntimeError("filing exploded")
        row = self.run_import(self.package("Liam Duff; Ryan Spencer"), crash)
        self.assertEqual(("imported", "pending"), (row["outcome"], row["filing"]["status"]))
        self.assertIn("filing exploded", row["filing"]["reason"])
        self.assertEqual(["business_brain:sources/historical_calls/ryan-new.md"], F.pending_notes(self.root))
        retried = F.retry_pending(brain=self.brain, root=self.root, db_path=self.db, registry=Registry(), refresh=ok_refresh, verifier=ok_verify)
        self.assertEqual("filed", retried["outcome"], retried.get("reason"))

    def test_kill_switch_skips_filing(self):
        with mock.patch.dict(os.environ, {F.FLAG: "0"}):
            row = self.run_import(self.package("Liam Duff; Ryan Spencer"), self.filing())
            self.assertEqual({"status": "disabled", "reason": "TTROS_MEMORY_FILING=0"}, row["filing"])
            self.assertEqual({"outcome": "disabled"}, F.retry_pending(brain=self.brain, root=self.root))
        self.assertEqual(row["commit"], head(self.brain), "no filing commit")
        self.assertFalse((self.brain / "people").exists())
        self.assertFalse((self.root / F.LEDGER).exists())

    def test_unchanged_filing_is_a_no_op(self):
        row = self.run_import(self.package("Liam Duff; Ryan Spencer"), self.filing())
        self.assertEqual("filed", row["filing"]["status"])
        filed_head = head(self.brain)
        again = F.file_notes(["business_brain:sources/historical_calls/ryan-new.md"], brain=self.brain, root=self.root,
                             db_path=self.db, registry=Registry(), refresh=ok_refresh, verifier=ok_verify)
        self.assertEqual("unchanged", again["outcome"])
        self.assertEqual(filed_head, head(self.brain))

    def test_owner_only_participants_get_no_hub(self):
        row = self.run_import(self.package("Liam Duff"), self.filing())
        self.assertEqual("filed", row["filing"]["status"])
        self.assertEqual([], sorted(p.name for p in (self.brain / "people").glob("*.md") if p.name not in {"INDEX.md", "NEEDS_IDENTITY.md"}))
        self.assertIn("· 0 person hubs ·", (self.brain / "index/MEMORY_INDEX.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
