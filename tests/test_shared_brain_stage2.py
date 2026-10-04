"""Stage 2 checkpoint and Drive handoff proofs against a temporary Brain."""

from __future__ import annotations

import contextlib
import fcntl
import io
import json
import multiprocessing as mp
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import shared_brain_checkpoint as shared
from tools.memory_exchange_import import main as exchange_main, process as exchange_process


STAMP = {"authenticated_identity": "server-verified", "surface": "claude",
         "actor_class": "authorised_client", "surface_source": "address"}


def fields(goal: str = "Goal") -> dict[str, str]:
    return {"goal": goal, "done": "First task", "decisions": "Use one note",
            "work_product_reference": "https://example.com/result", "next_action": "Continue",
            "open_questions": "None"}


def race_writer(brain: str, workstream_id: str, goal: str, start, output) -> None:
    start.wait()
    with mock.patch("subprocess.run", side_effect=AssertionError("checkpoint ran Git")):
        result = shared.checkpoint(workstream_id, fields(goal), 1, attribution=STAMP, root=Path(brain))
    output.put((result["success"], result.get("error")))


def hold_durable_lock(brain: str, ready, release) -> None:
    with (Path(brain) / ".git" / "hermes-memory.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        ready.set()
        release.wait(timeout=10)
        fcntl.flock(handle, fcntl.LOCK_UN)


class Stage2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.brain = Path(self.temp.name) / "brain"
        self.brain.mkdir()
        subprocess.run(["git", "init", "-q", str(self.brain)], check=True)

    def save(self, workstream_id="sample-workstream", goal="Goal", version=0, stamp=STAMP):
        return shared.checkpoint(workstream_id, fields(goal), version,
                                 attribution=stamp, root=self.brain)

    def test_checkpoint_resume_previous_stale_and_server_attribution(self):
        supplied = fields()
        supplied.update(actor="fake", identity="fake", surface="chatgpt",
                        authenticated_identity="fake", actor_class="fake", surface_source="fake")
        first = shared.checkpoint("sample-workstream", supplied, 0, attribution=STAMP, root=self.brain)
        self.assertTrue(first["success"], first)
        self.assertEqual(shared.resume("sample-workstream", root=self.brain)["note"]["goal"], "Goal")
        self.assertEqual({key: first["note"][key] for key in STAMP}, STAMP)
        second = self.save(goal="Next goal", version=1)
        self.assertTrue(second["success"], second)
        self.assertEqual(shared.resume("sample-workstream", version=1, root=self.brain)["note"]["goal"], "Goal")
        stale = self.save(goal="Lost goal", version=1)
        self.assertFalse(stale["success"])
        self.assertIn("stale", stale["error"])
        self.assertEqual(stale["current"]["goal"], "Next goal")
        self.assertEqual(shared.resume("sample-workstream", root=self.brain)["note"]["goal"], "Next goal")

    def test_bounds_ids_references_and_listing(self):
        for bad in ("../x", "/tmp/x", "Aaa", "a", "a_b", "c:/x"):
            with self.subTest(bad=bad):
                self.assertFalse(self.save(workstream_id=bad)["success"])
        for reference in ("/tmp/result", "C:\\result", "file:///tmp/result", "../result",
                          "business_brain:../../result.md"):
            item = fields()
            item["work_product_reference"] = reference
            self.assertFalse(shared.checkpoint("sample-workstream", item, 0, attribution=STAMP,
                                               root=self.brain)["success"])
        item = fields()
        item["done"] = "x" * 1201
        self.assertIn("1200", shared.checkpoint("sample-workstream", item, 0,
                                                attribution=STAMP, root=self.brain)["error"])
        item = fields()
        item["done"] = "x" * 1100
        item["decisions"] = "y" * 1100
        self.assertIn("2500", shared.checkpoint("sample-workstream", item, 0,
                                                attribution=STAMP, root=self.brain)["error"])
        item = fields()
        item["done"] = "See C:\\Users\\Admin\\secret"
        self.assertFalse(shared.checkpoint("sample-workstream", item, 0,
                                           attribution=STAMP, root=self.brain)["success"])
        for n in range(25):
            self.assertTrue(self.save(workstream_id=f"stream-{n:02d}")["success"])
        listing = shared.resume(root=self.brain)
        self.assertEqual(len(listing["workstreams"]), 20)
        self.assertEqual(set(listing["workstreams"][0]), {"workstream_id", "goal", "last_surface", "updated"})

    def test_no_git_commit_and_no_durable_lock_dependency(self):
        before = subprocess.run(["git", "-C", str(self.brain), "rev-parse", "HEAD"],
                                capture_output=True, text=True).stdout
        ctx = mp.get_context("fork")
        ready, release = ctx.Event(), ctx.Event()
        locker = ctx.Process(target=hold_durable_lock, args=(str(self.brain), ready, release))
        locker.start()
        self.assertTrue(ready.wait(timeout=10))
        try:
            with mock.patch("subprocess.run", side_effect=AssertionError("checkpoint ran Git")):
                self.assertTrue(self.save()["success"])
        finally:
            release.set()
            locker.join(timeout=10)
        self.assertEqual(locker.exitcode, 0)
        after = subprocess.run(["git", "-C", str(self.brain), "rev-parse", "HEAD"],
                               capture_output=True, text=True).stdout
        self.assertEqual(before, after)

    def test_twenty_cross_process_version_races(self):
        ctx = mp.get_context("fork")
        for n in range(20):
            workstream_id = f"race-{n:02d}"
            self.assertTrue(self.save(workstream_id=workstream_id)["success"])
            start, output = ctx.Event(), ctx.Queue()
            writers = [ctx.Process(target=race_writer,
                                   args=(str(self.brain), workstream_id, f"winner-{i}", start, output))
                       for i in range(2)]
            for writer in writers:
                writer.start()
            start.set()
            results = [output.get(timeout=10) for _ in writers]
            for writer in writers:
                writer.join(timeout=10)
                self.assertEqual(writer.exitcode, 0)
            self.assertEqual(sorted(success for success, _ in results), [False, True], results)
            self.assertIn("stale", next(error for success, error in results if not success))
            self.assertIn(shared.resume(workstream_id, root=self.brain)["note"]["goal"],
                          {"winner-0", "winner-1"})
            self.assertEqual(shared.resume(workstream_id, version=1, root=self.brain)["note"]["goal"], "Goal")

    def test_drive_package_uses_same_checkpoint_function(self):
        package = Path(self.temp.name) / "ready" / "package-01"
        package.mkdir(parents=True)
        payload = {"schema_version": "shared-brain-checkpoint-v1", "operation": "checkpoint",
                   "workstream_id": "drive-workstream", "fields": fields(), "expected_version": 0,
                   "actor": "fake", "surface": "claude", "authenticated_identity": "fake"}
        (package / "CHECKPOINT.json").write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(exchange_process(package, brain=self.brain, root=Path(self.temp.name),
                                          dry_run=True)["outcome"], "validated")
        self.assertFalse((self.brain / "sessions/workstreams/drive-workstream.md").exists())
        self.assertEqual(exchange_process(package, brain=self.brain, root=Path(self.temp.name))["outcome"], "disabled")
        with mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_WRITE": "1"}):
            result = exchange_process(package, brain=self.brain, root=Path(self.temp.name))
        self.assertEqual(result["outcome"], "imported", result)
        note = shared.resume("drive-workstream", root=self.brain)["note"]
        self.assertEqual(note["surface"], "chatgpt")
        self.assertEqual(note["surface_source"], "address")
        self.assertEqual(note["authenticated_identity"], "liam-drive-channel")
        with mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_WRITE": "1"}):
            self.assertEqual(exchange_process(package, brain=self.brain, root=Path(self.temp.name))["outcome"], "rejected")

    def test_timer_mode_selects_only_checkpoint_packages(self):
        ready = Path(self.temp.name) / "ready"
        checkpoint_package = ready / "checkpoint-package"
        ingest_package = ready / "ingest-package"
        checkpoint_package.mkdir(parents=True)
        ingest_package.mkdir()
        (checkpoint_package / "CHECKPOINT.json").write_text(json.dumps({
            "schema_version": "shared-brain-checkpoint-v1", "operation": "checkpoint",
            "workstream_id": "timer-workstream", "fields": fields(), "expected_version": 0,
        }), encoding="utf-8")
        (ingest_package / "INGEST_MANIFEST.json").write_text("{}", encoding="utf-8")
        output = io.StringIO()
        with mock.patch("sys.argv", ["memory_exchange_import.py", "--ready", str(ready),
                                     "--brain", str(self.brain), "--dry-run", "--checkpoint-only"]), \
             contextlib.redirect_stdout(output):
            self.assertEqual(exchange_main(), 0)
        self.assertIn('"workstream_id": "timer-workstream"', output.getvalue())
        self.assertNotIn("ingest-package", output.getvalue())
        self.assertTrue((ingest_package / "INGEST_MANIFEST.json").is_file())

    def test_missing_projection_mount_does_not_fail_checkpoint(self):
        absent = Path(self.temp.name) / "missing-mount" / "06_WORKSTREAMS_READ"
        with mock.patch.object(shared, "VAULT_ROOT", self.brain), \
             mock.patch.dict("os.environ", {"TTROS_SHARED_BRAIN_DRIVE_PROJECTION": str(absent)}):
            result = self.save()
        self.assertTrue(result["success"], result)
        self.assertEqual(result["drive_projection"], "unavailable")
        self.assertEqual(shared.resume("sample-workstream", root=self.brain)["note"]["version"], 1)

    def test_read_projection_is_a_copy_of_current_note(self):
        projection = Path(self.temp.name) / "drive" / "06_WORKSTREAMS_READ"
        projection.parent.mkdir()
        with mock.patch.object(shared, "VAULT_ROOT", self.brain), \
             mock.patch.dict("os.environ", {"TTROS_SHARED_BRAIN_DRIVE_PROJECTION": str(projection)}):
            first = self.save()
            self.assertEqual(first["drive_projection"], "synced")
            second = self.save(goal="Latest", version=1)
            self.assertEqual(second["drive_projection"], "synced")
        self.assertEqual((projection / "sample-workstream.md").read_text(),
                         (self.brain / "sessions/workstreams/sample-workstream.md").read_text())

    def test_stdio_write_flag_reaches_david_without_inherited_env(self):
        from tools import brain_memory_mcp as bmm
        flag = Path(self.temp.name) / "ttros-shared-brain.env"
        with mock.patch.object(bmm, "SHARED_BRAIN_WRITE_FLAG_FILE", flag):
            with mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_WRITE": ""}):
                self.assertFalse(bmm._shared_brain_write_enabled())
                flag.write_text("TTROS_SHARED_BRAIN_WRITE=1\n", encoding="utf-8")
                self.assertTrue(bmm._shared_brain_write_enabled())
                flag.write_text("TTROS_SHARED_BRAIN_WRITE=0\n", encoding="utf-8")
                self.assertFalse(bmm._shared_brain_write_enabled())
                flag.write_text("TTROS_SHARED_BRAIN_WRITE=1\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_WRITE": "0"}):
                self.assertFalse(bmm._shared_brain_write_enabled())


class LargeWorkProductTests(unittest.TestCase):
    """Stage 4 repair: large unfinished work lives as a Drive working artifact, not in the note."""

    WS = "digital-product-validation-stage4"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.brain = Path(self.temp.name) / "brain"
        self.brain.mkdir()
        subprocess.run(["git", "init", "-q", str(self.brain)], check=True)
        self.exchange = Path(self.temp.name) / "TTROS Memory Exchange"
        self.exchange.mkdir()
        self.artifacts = self.exchange / "07_WORKSTREAM_ARTIFACTS"
        env = mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_ARTIFACTS": str(self.artifacts)})
        env.start()
        self.addCleanup(env.stop)
        # A ~5,800-character stand-in for the real Prompt 1, with a non-ASCII character.
        self.prompt = ("# Prompt 1 — market research\n" + "Rank evidence-backed opportunities. " * 170)[:5800]

    def note_fields(self, reference: str = "") -> dict[str, str]:
        item = fields()
        item["work_product_reference"] = reference
        return item

    def store(self, version: int = 0, name: str = "prompt-1.md", content: str | None = None,
              reference: str = ""):
        return shared.checkpoint(self.WS, self.note_fields(reference), version, attribution=STAMP,
                                 root=self.brain,
                                 work_product={"name": name, "content": self.prompt if content is None else content})

    def test_large_artifact_is_stored_and_referenced_without_enlarging_the_note(self):
        before = subprocess.run(["git", "-C", str(self.brain), "status", "--porcelain", "--ignored"],
                                capture_output=True, text=True).stdout
        with mock.patch("subprocess.run", side_effect=AssertionError("checkpoint ran Git")):
            result = self.store()
        self.assertTrue(result["success"], result)
        reference = f"artifact:{self.WS}/prompt-1.md"
        self.assertEqual(result["note"]["work_product_reference"], reference)
        self.assertEqual(result["work_product"]["characters"], 5800)
        note_text = (self.brain / f"sessions/workstreams/{self.WS}.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(note_text), shared.MAX_NOTE_CHARS)
        self.assertNotIn("Rank evidence-backed opportunities", note_text)
        stored = self.artifacts / self.WS / "prompt-1.md"
        self.assertEqual(stored.read_text(encoding="utf-8"), self.prompt)
        self.assertFalse(stored.resolve().is_relative_to(self.brain.resolve()))
        # Nothing was committed, and nothing outside the workstream note entered the Brain.
        self.assertNotEqual(subprocess.run(["git", "-C", str(self.brain), "rev-parse", "HEAD"],
                                           capture_output=True, text=True).returncode, 0)
        after = subprocess.run(["git", "-C", str(self.brain), "status", "--porcelain", "--ignored"],
                               capture_output=True, text=True).stdout
        self.assertEqual(sorted(set(after.splitlines()) - set(before.splitlines())), ["?? sessions/"])
        # The receiving client gets the exact artifact back with the compact note.
        resumed = shared.resume(self.WS, root=self.brain)
        self.assertEqual(resumed["note"]["work_product_reference"], reference)
        self.assertTrue(resumed["work_product"]["available"])
        self.assertEqual(resumed["work_product"]["content"], self.prompt)
        self.assertFalse(resumed["work_product"]["truncated"])
        self.assertIn("not Brain knowledge", resumed["work_product"]["authority"])
        # A later compact checkpoint keeps pointing at the same artifact without resending it.
        later = shared.checkpoint(self.WS, self.note_fields(reference), 1, attribution=STAMP, root=self.brain)
        self.assertTrue(later["success"], later)
        self.assertNotIn("work_product", later)
        self.assertEqual(shared.resume(self.WS, version=1, root=self.brain)["work_product"]["content"], self.prompt)

    def test_artifact_inputs_and_references_are_bounded_and_refused(self):
        for name in ("../prompt.md", "Prompt-1.md", "prompt-1.exe", "a/b.md", "", ".md", "x" * 70 + ".md"):
            with self.subTest(name=name):
                self.assertFalse(self.store(name=name)["success"])
        self.assertIn("20000", self.store(content="x" * 20_001)["error"])
        self.assertFalse(self.store(content="   ")["success"])
        self.assertTrue(self.store(name="at-limit.txt", content="x" * 20_000)["success"])
        self.assertFalse(self.store(version=1, reference="https://example.com/other")["success"])
        bad = shared.checkpoint(self.WS, self.note_fields(), 1, attribution=STAMP, root=self.brain,
                                work_product={"name": "p.md", "content": "x", "path": "/tmp/x"})
        self.assertFalse(bad["success"])
        for reference in (f"artifact:{self.WS}/missing.md", "artifact:other-workstream/at-limit.txt",
                          f"artifact:{self.WS}/../at-limit.txt", f"artifact:{self.WS}/at-limit.exe"):
            with self.subTest(reference=reference):
                result = shared.checkpoint(self.WS, self.note_fields(reference), 1,
                                           attribution=STAMP, root=self.brain)
                self.assertFalse(result["success"])
                self.assertNotIn(self.temp.name, result["error"])
        # A stale version writes neither the artifact nor the note.
        stale = self.store(version=0, name="stale.md")
        self.assertIn("stale", stale["error"])
        self.assertFalse((self.artifacts / self.WS / "stale.md").exists())
        # Over-size notes are still refused when an artifact is attached.
        item = self.note_fields()
        item["done"], item["decisions"] = "x" * 1100, "y" * 1100
        over = shared.checkpoint(self.WS, item, 1, attribution=STAMP, root=self.brain,
                                 work_product={"name": "big.md", "content": self.prompt})
        self.assertIn("2500", over["error"])
        self.assertFalse((self.artifacts / self.WS / "big.md").exists())

    def test_unavailable_storage_refuses_and_test_brains_never_reach_live_drive(self):
        with mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_ARTIFACTS": ""}):
            result = self.store()
        self.assertEqual(result["error"], "working-artifact storage is unavailable")
        self.assertFalse((self.brain / f"sessions/workstreams/{self.WS}.md").exists())
        with mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_ARTIFACTS":
                                          str(Path(self.temp.name) / "no-mount" / "07_WORKSTREAM_ARTIFACTS")}):
            self.assertFalse(self.store()["success"])
        self.assertTrue(self.store()["success"])
        with mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_ARTIFACTS": ""}):
            resumed = shared.resume(self.WS, root=self.brain)
        self.assertTrue(resumed["success"])
        self.assertFalse(resumed["work_product"]["available"])

    def test_drive_handoff_references_a_client_written_artifact(self):
        (self.artifacts / self.WS).mkdir(parents=True)
        (self.artifacts / self.WS / "research-package-1.md").write_text(self.prompt, encoding="utf-8")
        package = Path(self.temp.name) / "ready" / "package-01"
        package.mkdir(parents=True)
        payload = {"schema_version": "shared-brain-checkpoint-v1", "operation": "checkpoint",
                   "workstream_id": self.WS, "expected_version": 0,
                   "fields": self.note_fields(f"artifact:{self.WS}/research-package-1.md")}
        (package / "CHECKPOINT.json").write_text(json.dumps(payload), encoding="utf-8")
        with mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_WRITE": "1"}):
            result = exchange_process(package, brain=self.brain, root=Path(self.temp.name))
        self.assertEqual(result["outcome"], "imported", result)
        resumed = shared.resume(self.WS, root=self.brain)
        self.assertEqual(resumed["note"]["surface"], "chatgpt")
        self.assertEqual(resumed["work_product"]["content"], self.prompt)
        # The package contract itself is unchanged: an inline work_product field is refused.
        inline = Path(self.temp.name) / "ready" / "package-02"
        inline.mkdir()
        payload.update(expected_version=1, work_product={"name": "x.md", "content": "x"})
        (inline / "CHECKPOINT.json").write_text(json.dumps(payload), encoding="utf-8")
        with mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_WRITE": "1"}):
            refused = exchange_process(inline, brain=self.brain, root=Path(self.temp.name))
        self.assertEqual(refused["outcome"], "rejected")
        self.assertEqual(refused["reason"], "unknown checkpoint package field")

    def test_working_artifacts_are_not_durable_submit_sources(self):
        from tools import aos_entity_index, shared_brain_submit  # noqa: F401 (puts tools/ on sys.path, as Stage 3 tests do)
        error = shared_brain_submit._validate(
            type="deliverable", title="Prompt 1", body="Finished", idempotency_key="artifact-check-01",
            source_refs=[f"artifact:{self.WS}/prompt-1.md"], workstream_id=self.WS)
        self.assertIsNotNone(error)

    def test_guidance_reaches_every_client_from_one_constant(self):
        from tools import aos_entity_index, shared_brain_read  # noqa: F401 (puts tools/ on sys.path, as Stage 3 tests do)
        guidance = shared_brain_read.LARGE_WORK_PRODUCT_GUIDANCE
        self.assertIn(guidance, shared_brain_read.CLIENT_INSTRUCTIONS)
        self.assertIn("07_WORKSTREAM_ARTIFACTS", guidance)
        self.assertIn("work_product_reference", guidance)
        self.assertIn("Do not durable-submit unfinished work", guidance)
        from tools import brain_memory_mcp as bmm
        self.assertIn("LARGE WORK PRODUCT", bmm.checkpoint.__doc__)


if __name__ == "__main__":
    unittest.main()
