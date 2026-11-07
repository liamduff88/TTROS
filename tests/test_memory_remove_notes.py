"""Removal tool (Memory Ingest spec 0.2 §8 item 6) and the Brain transaction's deletions. Temp-dir vaults only.

Revisit: when the removal tool, import ledger or filing stage changes. · Last touched: 2026-11-07.
"""
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import aos_indexer, brain_memory, memory_filing as F, memory_remove_notes as R
from tools.memory_exchange_import import LEDGER
from tools.validate_business_brain import analyze_vault
from tests.test_memory_filing import NOTES, Registry, ok_refresh, ok_verify, vault, write

SHA_A = "a" * 64  # card + record; the card goes, the record stays
SHA_B = "b" * 64  # a test record, removed by name
SHA_C = "c" * 64  # record a v3 note points to
V3 = "sources/historical_calls/2026-11-04-ryan-spencer-first-call-cccccccc/"


def record(sha, title):
    return (f'---\nid: source-intake-{sha}\ntype: source\ntitle: "{title}"\nsource_sha256: {sha}\n---\n'
            f"# {title}\n\nExact bytes.\n")


def card(sha):
    return (f'---\nid: source-intake-card-{sha}\ntype: source_card\nsource_path: "sources/intake/records/{sha}.md"\n---\n'
            f"# Card\n\n- Original: [[sources/intake/records/{sha}|source]]\n")


def intake_index(entries):
    lines = ["---", "id: source-intake-index", "type: index", "---", "# Historical source intake", "", "## Sources", ""]
    for sha, title, has_card in entries:
        suffix = f" · [[sources/intake/cards/{sha}.card|card]]" if has_card else ""
        lines.append(f"- [[sources/intake/records/{sha}|{title}]] — `normalized.md` · `sha256:{sha}`{suffix}")
    return "\n".join(lines) + "\n"


class RemovalBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.brain = self.root / "TTROS Business Brain"
        self.db = self.root / "search/os_index.db"  # absent: no entity-index persons

    def build(self, *, extra=None, ledger=None, git=True):
        vault(self.brain, notes=NOTES)
        b = self.brain
        # MEMORY_INDEX also links the intake INDEX, as the live one does.
        text = (b / "index/MEMORY_INDEX.md").read_text()
        (b / "index/MEMORY_INDEX.md").write_text(text + "\n[[sources/intake/INDEX|Historical source intake]]\n")
        # A historical card plus a table row linking card and note, and a dated section with one note.
        write(b / "sources/historical_calls/cards/ryan-a.card.md", "---\nid: ryan-a-card\n---\n# Card\n\n[[sources/historical_calls/ryan-a|Original]]\n")
        hc = (b / "sources/historical_calls/INDEX.md").read_text()
        hc = hc.replace("[[index/MEMORY_INDEX|Memory Index]]",
                        "| Date | Card | Original |\n|---|---|---|\n"
                        "| Nov 4 | [[sources/historical_calls/cards/ryan-a.card|card]] | [[sources/historical_calls/ryan-a|original]] |\n\n"
                        "## September 18 Kenneth historical evidence\n\n- [[sources/historical_calls/kenneth|Kenneth]]\n\n"
                        f"## Source packages\n\n- [[{V3}INDEX|Ryan v3]] · 2026-11-04 · [[sources/intake/records/{SHA_C}|Original record]]\n"
                        f"  - [[{V3}beta|Ryan beta (v3)]]\n\n[[index/MEMORY_INDEX|Memory Index]]")
        (b / "sources/historical_calls/INDEX.md").write_text(hc)
        write(b / f"{V3}INDEX.md", f'---\nid: v3-index\ntype: source_index\ntitle: "Ryan v3"\n'
              f"source_record: business_brain:sources/intake/records/{SHA_C}.md\n---\n# Ryan v3\n\n[[{V3}beta|beta]]\n")
        write(b / f"{V3}beta.md", f'---\nid: v3-beta\ntype: historical_record\ntitle: "Ryan beta (v3)"\n'
              f"entity_key: person:ryan-spencer\nsource_record: business_brain:sources/intake/records/{SHA_C}.md\n---\n# Ryan beta\n")
        for sha, title in ((SHA_A, "Fred call"), (SHA_B, "Disposable sentinel"), (SHA_C, "Ryan original")):
            write(b / f"sources/intake/records/{sha}.md", record(sha, title))
        write(b / f"sources/intake/cards/{SHA_A}.card.md", card(SHA_A))
        write(b / "sources/intake/INDEX.md", intake_index([(SHA_A, "Fred call", True), (SHA_B, "Disposable sentinel", False),
                                                           (SHA_C, "Ryan original", False)]))
        write(b / "sessions/2026-08-17_log.md", "---\nid: session-log\n---\n# Log\n\nImported `ryan-a.md` today.\n")
        for relative, text in (extra or {}).items():
            write(b / relative, text)
        rows = ledger if ledger is not None else [
            {"package_id": "MI-ryan-a", "outcome": "in_progress", "outputs": [{"pointer": "business_brain:sources/historical_calls/ryan-a.md"}]},
            {"package_id": "MI-ryan-a", "outcome": "imported", "outputs": [{"pointer": "business_brain:sources/historical_calls/ryan-a.md"}]},
            {"package_id": "MI-ryan-b", "outcome": "imported", "outputs": [{"pointer": "business_brain:sources/historical_calls/ryan-b.md"}]},
            {"package": "MI-ryan-b", "outcome": "rejected", "reason": "earlier attempt"},
            {"package_id": "MI-kenneth", "outcome": "imported", "outputs": [{"pointer": "business_brain:sources/historical_calls/kenneth.md"}]},
            {"outcome": "imported", "operation": "checkpoint"},
        ]
        write(self.root / LEDGER, "".join(json.dumps(r) + "\n" for r in rows))
        if git:
            subprocess.run(["git", "init", "-q", str(b)], check=True)
            subprocess.run(["git", "-C", str(b), "add", "."], check=True)
            subprocess.run(["git", "-C", str(b), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                            "commit", "-qm", "fixture"], check=True)
            for patcher in (mock.patch.object(brain_memory, "VAULT_ROOT", self.brain),
                            mock.patch("tools.brain_git_closure.push_commit", return_value="local_only"),
                            mock.patch("tools.brain_git_closure.record"),
                            mock.patch("tools.aos_indexer.index_one", return_value={"status": "success"}),
                            mock.patch("tools.aos_indexer.remove_one", return_value={"status": "success"}),
                            mock.patch("tools.aos_entity_index.ensure_current"),
                            mock.patch.dict(os.environ, {F.FLAG: "1"})):
                patcher.start()
                self.addCleanup(patcher.stop)
        # The fixture starts filed, as the live Brain does after each import.
        if git:
            filed = F.file_notes(None, brain=b, root=self.root, db_path=self.db, registry=Registry(),
                                 refresh=ok_refresh, verifier=ok_verify)
            self.assertEqual("filed", filed["outcome"], filed.get("reason"))
        self.assertEqual("PASS", analyze_vault(b)["status"], analyze_vault(b)["broken_links"])

    def run_tool(self, paths, apply=False, **kwargs):
        options = dict(brain=self.brain, root=self.root, apply=apply, db_path=self.db, refresh=ok_refresh,
                       filing_kwargs={"registry": Registry(), "refresh": ok_refresh, "verifier": ok_verify})
        options.update(kwargs)
        return R.run(paths, **options)

    def snapshot(self):
        files = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*")
                 if p.is_file() and ".git" not in p.parts}
        return files, self.head()

    def head(self):
        return subprocess.check_output(["git", "-C", str(self.brain), "rev-parse", "HEAD"], text=True).strip()

    def ledger(self):
        return [json.loads(line) for line in (self.root / LEDGER).read_text().splitlines() if line]


LIST = ["sources/historical_calls/ryan-a.md", "business_brain:sources/historical_calls/ryan-b.md",
        "sources/historical_calls/cards/ryan-a.card.md", f"sources/intake/cards/{SHA_A}.card.md",
        f"sources/intake/records/{SHA_B}.md"]


class ClassifyTests(unittest.TestCase):
    def test_allowed_and_refused_paths(self):
        allowed = {
            "sources/historical_calls/ryan-a.md": "historical_note",
            "business_brain:sources/historical_calls/ryan-a.md": "historical_note",
            "sources/historical_calls/cards/ryan-a.card.md": "historical_card",
            f"{V3}beta.md": "v3_note",
            f"{V3}INDEX.md": "v3_note",
            f"sources/intake/cards/{SHA_A}.card.md": "intake_card",
            f"sources/intake/records/{SHA_A}.md": "intake_record",
        }
        for raw, kind in allowed.items():
            self.assertEqual(kind, R.classify(raw)[0], raw)
        for raw in ("sources/historical_calls/INDEX.md", "sources/historical_calls/MANIFEST.md", "sources/intake/INDEX.md",
                    "people/ryan-spencer.md", "index/MEMORY_INDEX.md", "sessions/2026-08-17_log.md",
                    "inbox/distilled_packets/shared-submit-abc.md", "memory/company.md",
                    "sources/historical_calls/../people/x.md", "/sources/historical_calls/x.md",
                    "sources\\historical_calls\\x.md", "sources/historical_calls/x.txt",
                    "sources/historical_calls/other-folder/x.md", f"{V3}deeper/x.md",
                    "sources/intake/records/not-a-sha.md", f"sources/intake/records/{SHA_A}.txt",
                    "sources/historical_calls/cards/ryan-a.md", "sources/historical_calls"):
            self.assertIsNone(R.classify(raw)[0], raw)

    def test_list_file_skips_blanks_and_comments(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "list.txt"
            path.write_text("# header\n\nsources/historical_calls/a.md\n  sources/historical_calls/b.md  \n")
            self.assertEqual(["sources/historical_calls/a.md", "sources/historical_calls/b.md"], R.read_list(path))


class StripIndexTests(unittest.TestCase):
    def test_lines_fragments_and_emptied_sections(self):
        text = ("---\nid: x\nlink: [[sources/historical_calls/a]]\n---\n# T\n\n## One\n\n- [[sources/historical_calls/a|A]]\n\n"
                "## Two\n\n- [[sources/intake/records/r|R]] · `sha` · [[sources/intake/cards/r.card|card]]\n"
                "- [[sources/historical_calls/b|B]]\n\n## Empty already\n\n## Three\n\n[[index/MEMORY_INDEX|Memory Index]]\n")
        out, dropped, stripped = R.strip_index(text, {"sources/historical_calls/a.md", "sources/intake/cards/r.card.md"})
        self.assertEqual(["- [[sources/historical_calls/a|A]]"], dropped)
        self.assertEqual(1, stripped)
        self.assertNotIn("## One", out, "a section this emptied is dropped")
        self.assertIn("## Empty already", out, "a section that was already empty is left alone")
        self.assertIn("link: [[sources/historical_calls/a]]", out, "frontmatter is never edited")
        self.assertIn("- [[sources/intake/records/r|R]] · `sha`\n", out)
        self.assertIn("- [[sources/historical_calls/b|B]]", out)
        self.assertEqual([], R.remaining_links(out.split("---\n", 2)[2], {"sources/historical_calls/a.md", "sources/intake/cards/r.card.md"}))


class DryRunTests(RemovalBase):
    def test_dry_run_is_the_default_and_writes_nothing(self):
        self.build()
        before = self.snapshot()
        receipt = self.run_tool(LIST)
        self.assertEqual("validated", receipt["outcome"], json.dumps(receipt.get("proof"), indent=1))
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / R.RECEIPTS).exists())
        self.assertEqual(5, receipt["files"]["to_delete"])
        self.assertEqual({"historical_note": 2, "historical_card": 1, "intake_card": 1, "intake_record": 1},
                         receipt["files"]["by_kind"])
        # ryan-a, ryan-b list lines + the table row; the intake record line; the card fragment.
        self.assertEqual({"lines_removed": 3, "links_stripped": 0}, receipt["index_edits"]["sources/historical_calls/INDEX.md"])
        self.assertEqual({"lines_removed": 1, "links_stripped": 1}, receipt["index_edits"]["sources/intake/INDEX.md"])
        self.assertEqual(["MI-ryan-a", "MI-ryan-b"], receipt["ledger"]["package_ids"])
        self.assertEqual(4, receipt["ledger"]["rows"], "both MI-ryan-a rows, MI-ryan-b and its unnamed rejected row")
        self.assertEqual(["people/ryan-spencer.md"], receipt["proof"]["hubs_affected"])
        self.assertTrue(receipt["proof"]["passed"])
        self.assertEqual(["inbox/distilled_packets/shared-submit-abc.md", "sessions/2026-08-17_log.md"],
                         receipt["history_pages_left_alone"])

    def test_cli_defaults_to_dry_run_and_refuses_to_overwrite_out(self):
        self.build()
        listing = self.root / "list.txt"
        listing.write_text("\n".join(LIST) + "\n")
        out = self.root / "report.json"
        before = self.snapshot()
        with mock.patch("builtins.print"):
            code = R.main(["--list", str(listing), "--brain", str(self.brain), "--root", str(self.root),
                           "--db", str(self.db), "--out", str(out)])
        self.assertEqual(0, code)
        self.assertEqual("validated", json.loads(out.read_text())["outcome"])
        out.unlink()
        self.assertEqual(before, self.snapshot())
        out.write_text("keep")
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            R.main(["--list", str(listing), "--brain", str(self.brain), "--root", str(self.root), "--out", str(out)])
        self.assertEqual("keep", out.read_text())

    def test_a_refused_path_refuses_the_whole_apply(self):
        self.build()
        before = self.snapshot()
        dry = self.run_tool(LIST + ["people/ryan-spencer.md", "sources/historical_calls/INDEX.md"])
        self.assertEqual("refused", dry["outcome"])
        self.assertEqual(["people/ryan-spencer.md", "sources/historical_calls/INDEX.md"], [r["path"] for r in dry["refused"]])
        applied = self.run_tool(LIST + ["people/ryan-spencer.md"], apply=True)
        self.assertEqual("refused", applied["outcome"])
        self.assertEqual(before, self.snapshot())

    def test_a_package_that_wrote_an_unlisted_note_is_refused(self):
        self.build(ledger=[{"package_id": "MI-both", "outcome": "imported", "outputs": [
            {"pointer": "business_brain:sources/historical_calls/ryan-a.md"},
            {"pointer": "business_brain:sources/historical_calls/ryan-b.md"}]}])
        receipt = self.run_tool(["sources/historical_calls/ryan-a.md"])
        self.assertEqual("refused", receipt["outcome"])
        self.assertIn("MI-both", receipt["refused"][0]["reason"])
        both = ["sources/historical_calls/ryan-a.md", "sources/historical_calls/ryan-b.md"]
        blocked = self.run_tool(both)
        self.assertEqual("would_fail", blocked["outcome"], "the card still links ryan-a")
        self.assertEqual(["sources/historical_calls/cards/ryan-a.card.md"],
                         blocked["proof"]["removal_gate"]["pages_outside_filing_still_linking"])
        self.assertEqual("validated", self.run_tool(both + ["sources/historical_calls/cards/ryan-a.card.md"])["outcome"])

    def test_a_canonical_page_still_linking_a_removed_note_would_fail(self):
        self.build(extra={"memory/company.md": "---\nid: company\n---\n# Company\n\n[[sources/historical_calls/ryan-a|Ryan]]\n"
                          "\n[[index/MEMORY_INDEX|Memory Index]]\n",
                          "README.md": "---\nid: readme\n---\n# Brain\n\n[[index/MEMORY_INDEX|Memory Index]]\n[[memory/company|Company]]\n"})
        before = self.snapshot()
        receipt = self.run_tool(LIST)
        self.assertEqual("would_fail", receipt["outcome"])
        self.assertEqual(["memory/company.md"], receipt["proof"]["removal_gate"]["pages_outside_filing_still_linking"])
        self.assertEqual("would_fail", self.run_tool(LIST, apply=True)["outcome"])
        kept = lambda files: {k: v for k, v in files.items() if not k.startswith(("queue/locks/", R.RECEIPTS))}
        self.assertEqual(kept(before[0]), kept(self.snapshot()[0]), "Brain and ledger untouched")
        self.assertEqual(before[1], self.head(), "no Brain commit")


class ApplyTests(RemovalBase):
    def test_apply_removes_in_one_brain_commit_then_cleans_ledger_and_refiles(self):
        self.build()
        start = self.head()
        receipt = self.run_tool(LIST, apply=True)
        self.assertEqual("removed", receipt["outcome"], json.dumps(receipt, indent=1, default=str))
        b = self.brain
        for relative in LIST:
            self.assertFalse((b / relative.removeprefix("business_brain:")).exists(), relative)
        self.assertTrue((b / f"sources/intake/records/{SHA_A}.md").exists(), "a record goes only when named")
        # One removal commit (deletions + both INDEX edits), then the filing commit.
        commits = subprocess.check_output(["git", "-C", str(b), "rev-list", f"{start}..HEAD"], text=True).split()
        self.assertEqual(2, len(commits))
        removal = receipt["brain"]["commit"]
        changes = subprocess.check_output(["git", "-C", str(b), "show", "--name-status", "--format=", removal], text=True).split("\n")
        status = {line.split("\t")[1]: line.split("\t")[0] for line in changes if line}
        self.assertEqual({**{p.removeprefix("business_brain:"): "D" for p in LIST},
                          "sources/historical_calls/INDEX.md": "M", "sources/intake/INDEX.md": "M"}, status)
        hc = (b / "sources/historical_calls/INDEX.md").read_text()
        self.assertNotIn("ryan-a", hc)
        self.assertNotIn("ryan-b", hc)
        self.assertIn("[[sources/historical_calls/kenneth|Kenneth]]", hc)
        intake = (b / "sources/intake/INDEX.md").read_text()
        self.assertNotIn(SHA_B, intake)
        self.assertIn(f"- [[sources/intake/records/{SHA_A}|Fred call]] — `normalized.md` · `sha256:{SHA_A}`\n", intake)
        # Ledger: removed rows archived, others kept.
        self.assertEqual([{"package_id": "MI-kenneth", "outcome": "imported", "outputs": [{"pointer": "business_brain:sources/historical_calls/kenneth.md"}]},
                          {"outcome": "imported", "operation": "checkpoint"}], self.ledger())
        archived = [json.loads(line) for line in (self.root / R.ARCHIVE).read_text().splitlines()]
        self.assertEqual(4, len(archived))
        self.assertEqual({"MI-ryan-a", "MI-ryan-b"}, {row["row"].get("package_id") or row["row"].get("package") for row in archived})
        # Filing rebuilt the hub without the removed notes; the v3 note is still filed.
        hub = (b / "people/ryan-spencer.md").read_text()
        self.assertNotIn("sources/historical_calls/ryan-a", hub)
        self.assertNotIn("sources/historical_calls/ryan-b", hub)
        self.assertIn(f"{V3}beta", hub)
        self.assertEqual("filed", receipt["filing"]["outcome"])
        self.assertEqual("PASS", analyze_vault(b)["status"])
        self.assertEqual("---\nid: session-log\n---\n# Log\n\nImported `ryan-a.md` today.\n",
                         (b / "sessions/2026-08-17_log.md").read_text(), "logs are left alone")
        self.assertEqual("removed", json.loads((self.root / R.RECEIPTS).read_text().splitlines()[-1])["outcome"])
        # A pending filing retry never asks for the removed notes again.
        self.assertFalse(set(F.pending_notes(self.root)) & {"business_brain:sources/historical_calls/ryan-a.md"})
        # Rerun: everything already absent, nothing left to do.
        again = self.run_tool(LIST, apply=True)
        self.assertEqual("removed", again["outcome"])
        self.assertNotIn("brain", again)
        self.assertEqual(5, len(again["files"]["already_absent"]))

    def test_removing_a_named_v3_folder_drops_its_grouped_entry(self):
        self.build(ledger=[])
        receipt = self.run_tool([f"{V3}INDEX.md", f"{V3}beta.md"], apply=True)
        self.assertEqual("removed", receipt["outcome"], json.dumps(receipt, indent=1, default=str))
        hc = (self.brain / "sources/historical_calls/INDEX.md").read_text()
        self.assertNotIn(V3, hc)
        self.assertNotIn("## Source packages", hc, "the emptied section goes too")
        self.assertEqual("PASS", analyze_vault(self.brain)["status"])

    def test_post_write_gate_failure_rolls_everything_back(self):
        self.build()
        before = self.snapshot()
        with mock.patch.object(R, "removal_gate", side_effect=[{"passed": True, "broken_links_to_removed_on_filing_pages": 0,
                                                                 "pages_outside_filing_still_linking": [], "other_broken_links": [],
                                                                 "unreachable": []},
                                                                {"passed": False}]):
            with self.assertRaises(R.RemovalError):
                self.run_tool(LIST, apply=True)
        after = self.snapshot()
        self.assertEqual(before[1], after[1], "no Brain commit")
        kept = lambda files: {k: v for k, v in files.items() if not k.startswith("queue/locks/")}
        self.assertEqual(kept(before[0]), kept(after[0]), "files and ledger restored/untouched")
        staged = subprocess.check_output(["git", "-C", str(self.brain), "status", "--porcelain"], text=True)
        self.assertEqual("", staged)


class OrphanTests(RemovalBase):
    def test_orphan_records_dry_run_lists_and_apply_removes(self):
        self.build(ledger=[])
        dry = self.run_tool([], orphan_mode=True)
        # A is referenced by its card's source_path, C by the v3 notes' source_record; B is the orphan.
        self.assertEqual([f"sources/intake/records/{SHA_B}.md"], dry["orphan_records"])
        self.assertEqual("validated", dry["outcome"])
        self.assertTrue((self.brain / f"sources/intake/records/{SHA_B}.md").exists())
        applied = self.run_tool([], orphan_mode=True, apply=True)
        self.assertEqual("removed", applied["outcome"], json.dumps(applied, indent=1, default=str))
        self.assertFalse((self.brain / f"sources/intake/records/{SHA_B}.md").exists())
        self.assertNotIn(SHA_B, (self.brain / "sources/intake/INDEX.md").read_text())
        # Once A's card is gone, A is an orphan too.
        self.assertEqual("removed", self.run_tool([f"sources/intake/cards/{SHA_A}.card.md"], apply=True)["outcome"])
        self.assertEqual([f"sources/intake/records/{SHA_A}.md"], self.run_tool([], orphan_mode=True)["orphan_records"])


class TransactionDeletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brain = Path(self.tmp.name).resolve() / "vault"
        write(self.brain / "a.md", "---\nid: a\n---\n# A\n")
        write(self.brain / "b.md", "---\nid: b\n---\n# B\n")
        write(self.brain / "ignored/c.md", "---\nid: c\n---\n# C\n")
        write(self.brain / ".gitignore", "ignored/\n")
        subprocess.run(["git", "init", "-q", str(self.brain)], check=True)
        subprocess.run(["git", "-C", str(self.brain), "add", "a.md", "b.md", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(self.brain), "-c", "user.name=F", "-c", "user.email=f@example.invalid",
                        "commit", "-qm", "fixture"], check=True)
        for patcher in (mock.patch.object(brain_memory, "VAULT_ROOT", self.brain),
                        mock.patch("tools.brain_git_closure.push_commit", return_value="local_only"),
                        mock.patch("tools.brain_git_closure.record"),
                        mock.patch("tools.aos_indexer.index_one", return_value={"status": "success"}),
                        mock.patch("tools.aos_indexer.remove_one", return_value={"status": "success"}),
                        mock.patch("tools.aos_entity_index.ensure_current")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_deletions_commit_with_writes_including_untracked(self):
        sha = brain_memory.file_sha256
        result = brain_memory.write_transaction({"b.md": "---\nid: b\n---\n# B2\n"}, deletions=["a.md", "ignored/c.md"],
                                                source="t", session_id="t",
                                                expected_hashes={"a.md": sha(self.brain / "a.md"), "ignored/c.md": sha(self.brain / "ignored/c.md")})
        self.assertEqual(("a.md", "ignored/c.md"), result.deleted_paths)
        self.assertFalse((self.brain / "a.md").exists())
        self.assertFalse((self.brain / "ignored/c.md").exists())
        names = subprocess.check_output(["git", "-C", str(self.brain), "show", "--name-status", "--format=", "HEAD"], text=True)
        self.assertEqual("D\ta.md\nM\tb.md\n", names)

    def test_stale_hash_or_failed_validator_restores_the_file(self):
        with self.assertRaises(brain_memory.ConcurrentEditError):
            brain_memory.write_transaction({}, deletions=["a.md"], source="t", session_id="t", expected_hashes={"a.md": "0" * 64})
        self.assertTrue((self.brain / "a.md").exists())

        def fail(_changed):
            raise RuntimeError("gate")
        with self.assertRaises(RuntimeError):
            brain_memory.write_transaction({"b.md": "---\nid: b\n---\n# B2\n"}, deletions=["a.md"], source="t",
                                           session_id="t", post_write_validator=fail)
        self.assertEqual("---\nid: a\n---\n# A\n", (self.brain / "a.md").read_text())
        self.assertEqual("---\nid: b\n---\n# B\n", (self.brain / "b.md").read_text())
        self.assertEqual("", subprocess.check_output(["git", "-C", str(self.brain), "status", "--porcelain"], text=True))

    def test_overlap_and_empty_are_refused(self):
        with self.assertRaises(brain_memory.BrainMemoryError):
            brain_memory.write_transaction({"a.md": "---\nid: a\n---\n# A\n"}, deletions=["a.md"], source="t", session_id="t")
        with self.assertRaises(brain_memory.BrainMemoryError):
            brain_memory.write_transaction({}, deletions=[], source="t", session_id="t")


class RemoveOneTests(unittest.TestCase):
    def test_remove_one_drops_the_search_row_only_for_a_missing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = Path(temp).resolve() / "brain"
            db = Path(temp).resolve() / "search/os_index.db"
            note = brain / "people/ryan-spencer.md"
            write(note, "---\nid: ryan\ntitle: Ryan Spencer\n---\n# Ryan Spencer\n\nUniqueword.\n")
            with mock.patch.object(aos_indexer, "BUSINESS_BRAIN_ROOT", brain):
                self.assertEqual("success", aos_indexer.index_one(str(note), db_path=db, registry=Registry())["status"])
                self.assertEqual("refused", aos_indexer.remove_one(str(note), db_path=db)["status"])
                note.unlink()
                result = aos_indexer.remove_one(str(note), db_path=db)
            self.assertEqual({"status": "success", "removed": 1}, {k: result[k] for k in ("status", "removed")})
            conn = sqlite3.connect(db)
            self.assertEqual(0, conn.execute("SELECT count(*) FROM documents").fetchone()[0])
            self.assertEqual([], conn.execute("SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'Uniqueword'").fetchall())
            conn.close()


if __name__ == "__main__":
    unittest.main()
