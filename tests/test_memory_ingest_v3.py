"""Memory Ingest v3 importer (spec 0.2 §8 items 1-5), on the fictional fixture only. Temp-dir vaults.

The fixture (tests/fixtures/memory_ingest_v3/) is the real TOOL_package.py v3.0 output for a
fictional call. It is test data only and is never imported into the live Brain.

Revisit: when the Memory Ingest v3 manifest or note contract changes. · Last touched: 2026-11-07.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import brain_memory, memory_filing as F, source_intake
from tools.memory_exchange_import import (
    HISTORICAL_INDEX_SECTION, V3_INDEX_SECTION, historical_index_text, historical_index_v3_text, process,
)
from tools.validate_business_brain import analyze_vault
from tests.test_memory_filing import Registry, ok_refresh, ok_verify, vault

FIXTURE = Path(__file__).resolve().parent / "fixtures/memory_ingest_v3/INGEST_20261014_jordan-ellis-intro-call_4bbd735bd750"
SHA = "4bbd735bd750c2a6cee5b5669f8a0ceb8a5b2e2dd9eb077a71ba698b55911111"
FOLDER = "sources/historical_calls/2026-10-14-jordan-ellis-intro-call-4bbd735b/"
RECORD = f"sources/intake/records/{SHA}.md"
TOPICS = ("call-tracker-feedback", "free-trial-next-steps", "missed-calls-problem", "referral-brother-in-law")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def covered(paths):
    return {"status": "success"}, {"status": "success", "coverage": [{"pointer": p} for p in paths]}


class V3Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.pkg = self.root / "ready" / FIXTURE.name
        shutil.copytree(FIXTURE, self.pkg)
        self.brain = self.root / "TTROS Business Brain"

    def manifest(self):
        return json.loads((self.pkg / "INGEST_MANIFEST.json").read_text(encoding="utf-8"))

    def save(self, manifest, *, rehash=True):
        """Write the manifest; by default re-declare every file's real hash and size first."""
        if rehash:
            for row in manifest["package_files"] + manifest["outputs"] + [manifest["source"]]:
                path = self.pkg / (row.get("path") or row["package_path"])
                if path.is_file():
                    raw = path.read_bytes()
                    row["sha256"], row["size_bytes"] = sha(raw), len(raw)
        (self.pkg / "INGEST_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def edit_note(self, name, old, new):
        path = self.pkg / "notes" / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def git_brain(self, notes=None):
        vault(self.brain, notes={} if notes is None else notes)
        subprocess.run(["git", "init", "-q", str(self.brain)], check=True)
        subprocess.run(["git", "-C", str(self.brain), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.brain), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "fixture"], check=True)
        for patcher in (mock.patch.object(brain_memory, "VAULT_ROOT", self.brain),
                        mock.patch("tools.brain_git_closure.push_commit", return_value="local_only"),
                        mock.patch("tools.brain_git_closure.record"),
                        mock.patch("tools.aos_indexer.index_one", return_value={"status": "success"}),
                        mock.patch("tools.aos_entity_index.ensure_current"),
                        mock.patch.dict(os.environ, {F.FLAG: "0"})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def head(self):
        return subprocess.check_output(["git", "-C", str(self.brain), "rev-parse", "HEAD"], text=True).strip()

    def run_import(self, dry=False, **kwargs):
        kwargs.setdefault("refresh", covered)
        return process(self.pkg, brain=self.brain, root=self.root, dry_run=dry, **kwargs)


class V3ValidationTests(V3Base):
    def setUp(self):
        super().setUp()
        self.brain.mkdir()

    def test_fixture_is_accepted_on_dry_run_with_zero_writes(self):
        row = self.run_import(dry=True)
        self.assertEqual("validated", row["outcome"], row.get("reason"))
        self.assertEqual(sorted([FOLDER + "INDEX.md"] + [FOLDER + t + ".md" for t in TOPICS]),
                         sorted(o["pointer"].removeprefix("business_brain:") for o in row["outputs"]))
        self.assertEqual({"pointer": "business_brain:" + RECORD, "sha256": SHA, "action": "write",
                          "source_path": f"drive:04_IMPORTED/{FIXTURE.name}/source/original.txt"}, row["record"])
        self.assertEqual([], list(self.brain.rglob("*")))
        self.assertFalse((self.root / "queue/receipts/memory_exchange_import.jsonl").exists())

    def test_v2_checks_are_not_applied_to_v3(self):
        manifest = self.manifest()
        self.assertNotIn("batch_id", manifest)
        self.assertNotIn("has_conflicts", manifest)
        self.assertEqual("validated", self.run_import(dry=True)["outcome"])

    def test_junk_files_are_ignored_including_ds_store(self):
        for name in ("desktop.ini", "notes/Thumbs.db", ".DS_Store", "source/.DS_Store"):
            (self.pkg / name).write_text("junk")
        row = self.run_import(dry=True)
        self.assertEqual("validated", row["outcome"], row.get("reason"))
        self.assertEqual([".DS_Store", "desktop.ini", "notes/Thumbs.db", "source/.DS_Store"], row["ignored_package_files"])

    def rejected(self, needle):
        row = self.run_import(dry=True)
        self.assertEqual("rejected", row["outcome"], row)
        self.assertIn(needle, row["reason"])
        return row

    def test_hash_and_size_mismatches_are_rejected(self):
        cases = {
            "package file sha": lambda m: m["package_files"][1].update(sha256="0" * 64),
            "package file size": lambda m: m["package_files"][1].update(size_bytes=1),
            "output sha": lambda m: m["outputs"][1].update(sha256="0" * 64),
            "output size": lambda m: m["outputs"][1].update(size_bytes=1),
            "source sha": lambda m: m["source"].update(sha256="1" + SHA[1:]),
            "source size": lambda m: m["source"].update(size_bytes=1),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                self.setUp()
                manifest = self.manifest()
                mutate(manifest)
                self.save(manifest, rehash=False)
                row = self.run_import(dry=True)
                self.assertEqual("rejected", row["outcome"])
                self.assertRegex(row["reason"], "mismatch|do not match|source_folder")

    def test_undeclared_file_is_rejected(self):
        (self.pkg / "notes/extra.md").write_text("---\nid: x\n---\n")
        self.rejected("undeclared package file: notes/extra.md")

    def test_two_source_indexes_are_rejected(self):
        manifest = self.manifest()
        manifest["outputs"][1]["role"] = "source_index"
        self.save(manifest)
        self.rejected("source_index")
        self.setUp()
        manifest = self.manifest()
        manifest["outputs"] = [o for o in manifest["outputs"] if o["role"] != "source_index"]
        self.save(manifest)
        self.rejected("exactly one source_index output is required (found 0)")

    def test_bad_folder_and_slug_are_rejected(self):
        folders = {
            "no sha8": "sources/historical_calls/2026-10-14-jordan-ellis-intro-call/",
            "wrong sha8": "sources/historical_calls/2026-10-14-jordan-ellis-intro-call-deadbeef/",
            "bad date": "sources/historical_calls/14-10-2026-jordan-ellis-4bbd735b/",
            "uppercase": "sources/historical_calls/2026-10-14-Jordan-4bbd735b/",
            "outside": "memory/2026-10-14-jordan-ellis-4bbd735b/",
            "no slash": "sources/historical_calls/2026-10-14-jordan-ellis-4bbd735b",
        }
        for label, folder in folders.items():
            with self.subTest(label):
                self.setUp()
                manifest = self.manifest()
                manifest["source_folder"] = folder
                for output in manifest["outputs"]:
                    output["target_path"] = folder + output["target_path"].rsplit("/", 1)[1]
                self.save(manifest)
                self.assertEqual("rejected", self.run_import(dry=True)["outcome"])
        slugs = {"uppercase": "Call-Tracker", "underscore": "call_tracker", "too long": "a" * 61,
                 "index": "index", "nested": "x/y", "not md": None}
        for label, slug in slugs.items():
            with self.subTest(label):
                self.setUp()
                manifest = self.manifest()
                manifest["outputs"][1]["target_path"] = FOLDER + ("call-tracker-feedback.txt" if slug is None else slug + ".md")
                self.save(manifest)
                self.assertEqual("rejected", self.run_import(dry=True)["outcome"], label)
        with self.subTest("index target"):
            self.setUp()
            manifest = self.manifest()
            manifest["outputs"][0]["target_path"] = FOLDER + "index-page.md"
            self.save(manifest)
            self.rejected("source_index target must be <source_folder>INDEX.md")
        with self.subTest("outside folder"):
            self.setUp()
            manifest = self.manifest()
            manifest["outputs"][1]["target_path"] = "sources/historical_calls/call-tracker-feedback.md"
            self.save(manifest)
            self.rejected("target is not inside source_folder")
        with self.subTest("60 characters is allowed"):
            self.setUp()
            manifest = self.manifest()
            manifest["outputs"][1]["target_path"] = FOLDER + "a" * 60 + ".md"
            self.save(manifest)
            self.assertEqual("validated", self.run_import(dry=True)["outcome"])

    def test_excluded_word_in_any_segment_is_rejected(self):
        for word in ("token", "secret", "credential", "password", "legacy", "zpc"):
            with self.subTest(f"topic {word}"):
                self.setUp()
                manifest = self.manifest()
                manifest["outputs"][1]["target_path"] = FOLDER + f"api-{word}-notes.md"
                self.save(manifest)
                self.rejected("excludes")
        with self.subTest("folder slug"):
            self.setUp()
            manifest = self.manifest()
            folder = "sources/historical_calls/2026-10-14-legacy-call-4bbd735b/"
            manifest["source_folder"] = folder
            for output in manifest["outputs"]:
                output["target_path"] = folder + output["target_path"].rsplit("/", 1)[1]
            self.save(manifest)
            self.rejected("excludes")

    def test_missing_or_wrong_frontmatter_is_rejected(self):
        for field in ("id", "type", "status", "canonical_truth", "title", "knowledge_type", "participants_text",
                      "entities", "source_sha256", "source_record", "source_date_text"):
            with self.subTest(field):
                self.setUp()
                path = self.pkg / "notes/call-tracker-feedback.md"
                lines = path.read_text(encoding="utf-8").split("\n")
                path.write_text("\n".join(l for l in lines if not l.startswith(field + ":")), encoding="utf-8")
                self.save(self.manifest())
                self.rejected(f"missing frontmatter in notes/call-tracker-feedback.md: {field}")
        with self.subTest("entity_key is optional"):
            self.setUp()
            self.edit_note("call-tracker-feedback.md", "entity_key: [person:jordan-ellis]\n", "")
            self.save(self.manifest())
            self.assertEqual("validated", self.run_import(dry=True)["outcome"])
        with self.subTest("canonical_truth true"):
            self.setUp()
            self.edit_note("call-tracker-feedback.md", "canonical_truth: false", "canonical_truth: true")
            self.save(self.manifest())
            self.rejected("canonical_truth must be false")
        with self.subTest("topic typed as index"):
            self.setUp()
            self.edit_note("call-tracker-feedback.md", "type: historical_record", "type: source_index")
            self.save(self.manifest())
            self.rejected("type must be historical_record")
        with self.subTest("index typed as topic"):
            self.setUp()
            self.edit_note("INDEX.md", "type: source_index", "type: historical_record")
            self.save(self.manifest())
            self.rejected("type must be source_index")
        with self.subTest("source_record"):
            self.setUp()
            self.edit_note("INDEX.md", f"source_record: business_brain:{RECORD}", "source_record: business_brain:x.md")
            self.save(self.manifest())
            self.rejected("source_record must be")

    def test_source_sha_mismatch_is_rejected(self):
        self.edit_note("missed-calls-problem.md", f"source_sha256: {SHA}", "source_sha256: " + "a" * 64)
        self.save(self.manifest())
        self.rejected("source_sha256 does not match the original")
        self.setUp()
        (self.pkg / "source/original.txt").write_bytes(b"different original\n")
        self.save(self.manifest())  # re-declared honestly, so only the stated source sha disagrees
        self.assertEqual("rejected", self.run_import(dry=True)["outcome"])

    def test_malformed_shapes_reject_and_never_raise(self):
        mutations = [lambda m: m.update(outputs="x"), lambda m: m.pop("source"), lambda m: m.update(source=[1]),
                     lambda m: m["outputs"].append(7), lambda m: m.update(source_folder=None),
                     lambda m: m["outputs"][1].update(target_path=["x"]), lambda m: m["outputs"][1].update(target_path="../x.md"),
                     lambda m: m["package_files"].append({"path": "/etc/passwd", "sha256": "0" * 64, "size_bytes": 1})]
        for index, mutate in enumerate(mutations):
            with self.subTest(index):
                self.setUp()
                manifest = self.manifest()
                mutate(manifest)
                self.save(manifest, rehash=False)
                self.assertEqual("rejected", self.run_import(dry=True)["outcome"])
        self.setUp()
        (self.pkg / "INGEST_MANIFEST.json").write_text("{not json")
        self.assertEqual("rejected", self.run_import(dry=True)["outcome"])

    def test_v2_manifest_still_goes_down_the_v2_path(self):
        manifest = self.manifest()
        manifest["schema_version"] = "2.0"
        self.save(manifest)
        self.rejected("unsupported semantic_contract_version")


class V3IndexEntryTests(unittest.TestCase):
    INDEX = ("---\nid: hc-index\n---\n# Historical Calls\n\n## Memory Exchange imports\n\nHistorical evidence.\n\n"
             "- [[sources/historical_calls/old|Old]]\n\n[[index/MEMORY_INDEX|Memory Index]]\n")

    def entry(self, *topics):
        return [f"- [[{FOLDER}INDEX|Jordan]] · 2026-10-14 · [[sources/intake/records/{SHA}|Original record]]",
                *(f"  - [[{FOLDER}{t}|{t}]]" for t in topics)]

    def test_same_source_folder_replaces_its_own_entry_and_v2_is_untouched(self):
        once = historical_index_v3_text(self.INDEX, FOLDER, self.entry("a", "b"))
        self.assertEqual(once, historical_index_v3_text(once, FOLDER, self.entry("a", "b")))
        changed = historical_index_v3_text(once, FOLDER, self.entry("c"))
        self.assertEqual(1, changed.count(f"[[{FOLDER}INDEX|"))
        self.assertIn(f"[[{FOLDER}c|c]]", changed)
        self.assertNotIn(f"[[{FOLDER}a|a]]", changed)
        other = "sources/historical_calls/undated-other-call-12345678/"
        both = historical_index_v3_text(changed, other, [f"- [[{other}INDEX|Other]] · undated · x"])
        self.assertIn(f"[[{FOLDER}c|c]]", both)
        self.assertLess(both.index(FOLDER), both.index(other))
        self.assertEqual(1, both.count(V3_INDEX_SECTION))
        self.assertTrue(both.endswith("\n\n[[index/MEMORY_INDEX|Memory Index]]\n"))
        v2_section = lambda t: t[t.index(HISTORICAL_INDEX_SECTION):t.index(V3_INDEX_SECTION)]
        self.assertEqual(self.INDEX[self.INDEX.index(HISTORICAL_INDEX_SECTION):].removesuffix("[[index/MEMORY_INDEX|Memory Index]]\n"),
                         v2_section(both))
        # A later v2 import still appends in its own section, in its own format.
        v2 = historical_index_text(both, {"sources/historical_calls/new.md": "---\ntitle: New\n---\n"})
        self.assertLess(v2.index("- [[sources/historical_calls/new|New]]"), v2.index(V3_INDEX_SECTION))
        self.assertEqual(both, historical_index_v3_text(v2, FOLDER, self.entry("c")).replace(
            "- [[sources/historical_calls/new|New]]\n", ""))


class V3ImportTests(V3Base):
    def setUp(self):
        super().setUp()
        self.git_brain()

    def test_import_writes_notes_record_and_indexes_in_one_commit(self):
        before = self.head()
        row = self.run_import()
        self.assertEqual("imported", row["outcome"], row.get("reason"))
        self.assertEqual(before, subprocess.check_output(["git", "-C", str(self.brain), "rev-parse", "HEAD~1"], text=True).strip())
        changed = subprocess.check_output(["git", "-C", str(self.brain), "show", "--name-only", "--format=", "HEAD"], text=True).split()
        self.assertEqual(sorted([FOLDER + "INDEX.md", *(FOLDER + t + ".md" for t in TOPICS), RECORD,
                                 "sources/intake/INDEX.md", "sources/historical_calls/INDEX.md", "index/MEMORY_INDEX.md"]),
                         sorted(changed))
        self.assertEqual("PASS", analyze_vault(self.brain)["status"])
        # The grouped entry: source INDEX (title, date), each topic (frontmatter title), the original.
        index = (self.brain / "sources/historical_calls/INDEX.md").read_text(encoding="utf-8")
        self.assertIn(f"- [[{FOLDER}INDEX|Jordan Ellis / Liam: Ellis Plumbing intro call (14 Oct 2026)]] · 2026-10-14 · "
                      f"[[sources/intake/records/{SHA}|Original record]]", index)
        self.assertIn(f"  - [[{FOLDER}call-tracker-feedback|Jordan Ellis: reaction to the call tracker and text-back (14 Oct 2026)]]", index)
        self.assertEqual(len(TOPICS), index.count(f"  - [[{FOLDER}"))
        self.assertEqual({"status": "success"}, row["search_refresh"])
        self.assertIn("business_brain:" + RECORD, {c["pointer"] for c in row["graphify_refresh"]["coverage"]})

    def test_original_is_stored_exactly_under_a_logical_path(self):
        row = self.run_import()
        self.assertEqual("imported", row["outcome"], row.get("reason"))
        text = (self.brain / RECORD).read_text(encoding="utf-8")
        original = (FIXTURE / "source/original.txt").read_bytes()
        self.assertEqual(original, source_intake.extract_exact_bytes(text))
        fields = source_intake._frontmatter(self.brain / RECORD)
        self.assertEqual(f"drive:04_IMPORTED/{FIXTURE.name}/source/original.txt", fields["source_path"])
        self.assertEqual("2026-10-14 Jordan Ellis intro call.txt", fields["original_filename"])
        self.assertEqual(SHA, fields["source_sha256"])
        self.assertEqual("2026-10-14", fields["source_date"])
        for host in (str(self.root), str(self.pkg), "/home/", "/mnt/", "/tmp/"):
            self.assertNotIn(host, text)
        intake_index = (self.brain / "sources/intake/INDEX.md").read_text(encoding="utf-8")
        self.assertIn(f"[[sources/intake/records/{SHA}|", intake_index)

    def test_record_is_titled_after_its_source_index(self):
        row = self.run_import()
        self.assertEqual("imported", row["outcome"], row.get("reason"))
        expected = "Original: Jordan Ellis / Liam: Ellis Plumbing intro call (14 Oct 2026)"
        self.assertEqual(expected, source_intake._frontmatter(self.brain / RECORD)["title"])
        self.assertIn(f"\n# {expected}\n", (self.brain / RECORD).read_text(encoding="utf-8"))
        intake_index = (self.brain / "sources/intake/INDEX.md").read_text(encoding="utf-8")
        self.assertIn(f"[[sources/intake/records/{SHA}|{expected}]]", intake_index)

    def test_existing_record_is_reused_not_rewritten(self):
        item = source_intake.SourceItem(Path("earlier.txt"), (FIXTURE / "source/original.txt").read_bytes(), SHA,
                                        "text/plain", "Earlier capture", None)
        record_text = source_intake.render_record(item, "2026-10-15T00:00:00Z", source_path="drive:earlier")
        brain_memory.write_transaction({RECORD: record_text, "sources/intake/INDEX.md": source_intake.render_index(self.brain, [item]),
                                        "index/MEMORY_INDEX.md": (self.brain / "index/MEMORY_INDEX.md").read_text() +
                                        f"\n{source_intake.INTAKE_LINK}\n"},
                                       source="fixture", session_id="fixture")
        record_before = (self.brain / RECORD).read_bytes()
        intake_before = (self.brain / "sources/intake/INDEX.md").read_bytes()
        row = self.run_import()
        self.assertEqual("imported", row["outcome"], row.get("reason"))
        self.assertEqual("reused", row["record"]["action"])
        self.assertEqual(record_before, (self.brain / RECORD).read_bytes())
        self.assertEqual(intake_before, (self.brain / "sources/intake/INDEX.md").read_bytes())
        changed = subprocess.check_output(["git", "-C", str(self.brain), "show", "--name-only", "--format=", "HEAD"], text=True).split()
        self.assertNotIn(RECORD, changed)

    def test_record_with_other_bytes_is_rejected(self):
        item = source_intake.SourceItem(Path("x.txt"), b"other bytes\n", SHA, "text/plain", "X", None)
        (self.brain / RECORD).parent.mkdir(parents=True, exist_ok=True)
        (self.brain / RECORD).write_text(source_intake.render_record(item, "2026-10-15T00:00:00Z"), encoding="utf-8")
        row = self.run_import()
        self.assertEqual("rejected", row["outcome"])
        self.assertIn("exact-byte verification", row["reason"])

    def test_rerun_is_idempotent_and_another_package_on_the_same_targets_is_refused(self):
        first = self.run_import()
        self.assertEqual("imported", first["outcome"], first.get("reason"))
        head = self.head()
        again = self.run_import()
        self.assertEqual("already_imported", again["outcome"], again.get("reason"))
        self.assertEqual(head, self.head())
        index = (self.brain / "sources/historical_calls/INDEX.md").read_text(encoding="utf-8")
        self.assertEqual(1, index.count(f"[[{FOLDER}INDEX|"))
        manifest = self.manifest()
        manifest["package_id"] = "MI-jordan-ellis-intro-call-resend"
        self.save(manifest)
        refused = self.run_import()
        self.assertEqual("rejected", refused["outcome"])
        self.assertIn("target already exists in the Brain (previously imported)", refused["reason"])
        self.assertIn("not overwritten", refused["reason"])
        self.assertEqual(head, self.head())

    def test_a_refresh_pending_import_completes_on_the_next_poll(self):
        pending = self.run_import(refresh=lambda p: ({"status": "failed"}, {"status": "pending"}))
        self.assertEqual("refresh_pending", pending["outcome"])
        head = self.head()
        done = self.run_import()
        self.assertEqual("imported", done["outcome"], done.get("reason"))
        self.assertEqual(head, self.head(), "the retry writes nothing")
        self.assertTrue(all(o["action"] == "already_present" for o in done["outputs"]))

    def test_a_note_that_fails_the_brain_gate_rolls_back_everything(self):
        self.edit_note("missed-calls-problem.md", "## Summary\n", "## Summary\n[[memory/missing|gone]]\n")
        self.save(self.manifest())
        head = self.head()
        row = self.run_import()
        self.assertEqual("rejected", row["outcome"])
        self.assertIn("broken links", row["reason"])
        self.assertEqual(head, self.head())
        self.assertFalse((self.brain / RECORD).exists())
        self.assertEqual("", subprocess.check_output(["git", "-C", str(self.brain), "status", "--porcelain"], text=True))

    def test_live_writes_need_the_brain_transaction(self):
        with mock.patch.object(brain_memory, "VAULT_ROOT", self.root / "elsewhere"):
            row = self.run_import()
        self.assertEqual("rejected", row["outcome"])
        self.assertIn("only through the live Brain transaction", row["reason"])


class V3FilingTests(V3Base):
    def setUp(self):
        super().setUp()
        self.git_brain()
        self.db = self.root / "search/os_index.db"

    def test_filing_reads_the_subfolder_and_never_counts_the_index(self):
        row = self.run_import()
        self.assertEqual("imported", row["outcome"], row.get("reason"))
        plan = F.build_plan(self.brain, db_path=self.db)
        relatives = {n["relative"] for n in plan["notes"]}
        self.assertEqual({FOLDER + t + ".md" for t in TOPICS}, relatives)
        self.assertNotIn(FOLDER + "INDEX.md", relatives)
        hub = next(h for h in plan["hubs"] if h["entity_id"] == "person:jordan-ellis")
        self.assertEqual(len(TOPICS), hub["count"], "the source index is never an evidence note")
        text = plan["documents"]["people/jordan-ellis.md"]
        self.assertEqual(len(TOPICS), text.count(f"|source]]"))
        self.assertIn(f"[[{FOLDER}INDEX|source]]", text)
        needs = plan["documents"]["people/NEEDS_IDENTITY.md"]
        self.assertIn(f"- Priya (L9, L14, L25): first name only; checks voicemail and will get a reports login. · "
                      f"listed under Needs identity in [[{FOLDER}INDEX|", needs)
        self.assertIn("Jordan s brother-in-law (L32): not named.", needs.replace("Jordan's", "Jordan s"))
        self.assertFalse(any(h["entity_id"] == "person:liam-duff" for h in plan["hubs"]))

    def test_import_hook_files_only_topic_notes(self):
        with mock.patch.dict(os.environ, {F.FLAG: "1"}):
            row = self.run_import(refresh=ok_refresh, filing=lambda pointers, **kw: F.file_imported(
                pointers, **kw, db_path=self.db, registry=Registry(), refresh=ok_refresh, verifier=ok_verify))
        self.assertEqual("imported", row["outcome"], row.get("reason"))
        self.assertEqual("filed", row["filing"]["status"], row["filing"])
        hub = (self.brain / "people/jordan-ellis.md").read_text(encoding="utf-8")
        for topic in TOPICS:
            self.assertIn(f"[[{FOLDER}{topic}|", hub)
        self.assertNotIn(f"[[{FOLDER}INDEX|Jordan", hub)
        self.assertEqual("PASS", analyze_vault(self.brain)["status"])

    def test_v2_top_level_notes_are_still_filed_and_cards_are_not(self):
        self.assertEqual(sorted(["sources/historical_calls/a.md", FOLDER + "b.md"]),
                         F._filing_notes(["sources/historical_calls/a.md", FOLDER + "b.md", FOLDER + "INDEX.md",
                                          "sources/historical_calls/cards/x.card.md",
                                          "sources/historical_calls/INDEX.md", FOLDER + "deeper/c.md"]))


if __name__ == "__main__":
    unittest.main()
