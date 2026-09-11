"""STEP X4 Part B/D(b) regression coverage.

STEP X3 added ``_queue_artifact_at_workspace_divergence`` in dashboard/backend/main.py as a
narrowly-scoped fallback for Hermes's own documented worker-cwd divergence: when a worker's
claimed artifact is genuinely absent at the canonical ``BASE_DIR``-relative path, the queue
review also checks ``BASE_DIR.parent / path`` before concluding the claim is false. As shipped
in X3, that fallback accepted any file with the right name and extension at that one extra
location, with no check on *when* the file was written -- a stale leftover with the right name
(from an earlier attempt, or planted by a lying worker some other way) would be accepted just
like a genuine one. These four controls (declared in scripts/stepX4_harden_x3.transcript.txt
before this file was run) bound that hole: a fallback hit only counts if its mtime is at or
after the attempt's own recorded start time (the queue item's ``claim.claimed_at``).
"""

import datetime
import importlib
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class QueueArtifactWorkspaceDivergenceFallbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = importlib.import_module("dashboard.backend.main")

    def _run(self, *, seed_primary: bool, seed_fallback: bool, fallback_mtime_offset_seconds: float | None):
        """Build an isolated BASE_DIR / BASE_DIR.parent pair, seed the requested file(s),
        and return the verified-artifact ref dict for the one claimed path."""
        with tempfile.TemporaryDirectory() as temp:
            workspace_root = Path(temp)
            base_dir = workspace_root / "repo"
            (base_dir / "workflows" / "queue_artifacts").mkdir(parents=True)
            relative = "workflows/queue_artifacts/AOS-TEST-0001_stepx4_control.md"

            attempt_start = datetime.datetime.now(datetime.timezone.utc)
            item = {
                "id": "AOS-TEST-0001",
                "claim": {"claimed_by": "hermes", "claimed_at": attempt_start.isoformat().replace("+00:00", "Z")},
            }
            worker_result = {"output": f"Files touched: {relative}"}

            if seed_primary:
                target = base_dir / relative
                target.write_text("primary copy\n", encoding="utf-8")

            if seed_fallback:
                target = workspace_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("fallback copy\n", encoding="utf-8")
                if fallback_mtime_offset_seconds is not None:
                    stamp = (attempt_start + datetime.timedelta(seconds=fallback_mtime_offset_seconds)).timestamp()
                    import os
                    os.utime(target, (stamp, stamp))

            with mock.patch.object(self.main, "BASE_DIR", base_dir):
                verified = self.main._queue_verified_artifacts_from_worker_result(item, worker_result)
            matches = [ref for ref in verified if ref.get("path") == relative]
            self.assertEqual(len(matches), 1, f"expected exactly one ref for {relative}, got {verified}")
            return matches[0]

    def test_control_1_stale_seed_must_block(self):
        ref = self._run(seed_primary=False, seed_fallback=True, fallback_mtime_offset_seconds=-300.0)
        self.assertFalse(
            ref.get("available"),
            "control 1 (stale seed, mtime before attempt start, primary absent) must BLOCK, "
            f"got: {ref}",
        )

    def test_control_2_fresh_file_must_pass(self):
        ref = self._run(seed_primary=False, seed_fallback=True, fallback_mtime_offset_seconds=5.0)
        self.assertTrue(
            ref.get("available"),
            f"control 2 (fresh file, mtime at/after attempt start, primary absent) must PASS, got: {ref}",
        )

    def test_control_3_nowhere_path_must_block(self):
        ref = self._run(seed_primary=False, seed_fallback=False, fallback_mtime_offset_seconds=None)
        self.assertFalse(
            ref.get("available"),
            f"control 3 (absent at both locations) must BLOCK, got: {ref}",
        )

    def test_control_4_primary_hit_must_pass_unchanged(self):
        ref = self._run(seed_primary=True, seed_fallback=False, fallback_mtime_offset_seconds=None)
        self.assertTrue(
            ref.get("available"),
            f"control 4 (present at primary path) must PASS, unchanged behaviour, got: {ref}",
        )
        self.assertNotIn(
            "workspace_divergence", ref,
            "a primary-path hit must not be reported as a workspace-divergence fallback hit",
        )


class QueueArtifactCanonicalCopyOnDivergenceTest(unittest.TestCase):
    """STEP X5, 2026-09-11: live post-repair use (AOS-2026-0913) showed X4's fallback correctly
    accepted a fresh divergent artifact but left it outside the canonical workspace, so normal
    dashboard/artifact discovery (which only looks under BASE_DIR) never surfaced it. These cases
    prove the accepted fallback is additively copied into the canonical BASE_DIR-relative path
    with exact contents, the fallback source is left untouched, and every existing X4 block case
    still blocks with no canonical copy created.
    """

    @classmethod
    def setUpClass(cls):
        cls.main = importlib.import_module("dashboard.backend.main")

    def _run(self, *, seed_primary: bool, seed_fallback: bool, fallback_mtime_offset_seconds: float | None,
              fallback_content: str = "fallback copy\n"):
        temp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp, ignore_errors=True)
        workspace_root = Path(temp)
        base_dir = workspace_root / "repo"
        (base_dir / "workflows" / "queue_artifacts").mkdir(parents=True)
        relative = "workflows/queue_artifacts/AOS-TEST-0002_stepx5_canonical_copy.md"

        attempt_start = datetime.datetime.now(datetime.timezone.utc)
        item = {
            "id": "AOS-TEST-0002",
            "claim": {"claimed_by": "hermes", "claimed_at": attempt_start.isoformat().replace("+00:00", "Z")},
        }
        worker_result = {"output": f"Files touched: {relative}"}

        primary_target = base_dir / relative
        fallback_target = workspace_root / relative

        if seed_primary:
            primary_target.write_text("primary copy\n", encoding="utf-8")

        if seed_fallback:
            fallback_target.parent.mkdir(parents=True, exist_ok=True)
            fallback_target.write_text(fallback_content, encoding="utf-8")
            if fallback_mtime_offset_seconds is not None:
                stamp = (attempt_start + datetime.timedelta(seconds=fallback_mtime_offset_seconds)).timestamp()
                os.utime(fallback_target, (stamp, stamp))

        with mock.patch.object(self.main, "BASE_DIR", base_dir):
            verified = self.main._queue_verified_artifacts_from_worker_result(item, worker_result)
        matches = [ref for ref in verified if ref.get("path") == relative]
        self.assertEqual(len(matches), 1, f"expected exactly one ref for {relative}, got {verified}")
        return matches[0], primary_target, fallback_target, fallback_content

    def test_fresh_fallback_accepted_and_canonically_copied(self):
        ref, primary_target, fallback_target, content = self._run(
            seed_primary=False, seed_fallback=True, fallback_mtime_offset_seconds=5.0,
        )
        self.assertTrue(ref.get("available"), f"fresh fallback must be accepted, got: {ref}")
        self.assertTrue(
            primary_target.is_file(),
            "accepted fallback must be copied into the canonical BASE_DIR-relative workspace path",
        )
        self.assertEqual(
            primary_target.read_text(encoding="utf-8"), content,
            "canonical copy must have exact contents of the accepted fallback",
        )
        self.assertTrue(
            fallback_target.is_file(),
            "the original fallback source must not be deleted or moved",
        )
        self.assertEqual(fallback_target.read_text(encoding="utf-8"), content)

    def test_stale_fallback_still_blocked_no_canonical_copy(self):
        ref, primary_target, fallback_target, _content = self._run(
            seed_primary=False, seed_fallback=True, fallback_mtime_offset_seconds=-300.0,
        )
        self.assertFalse(ref.get("available"), f"stale fallback must still be blocked, got: {ref}")
        self.assertFalse(
            primary_target.exists(),
            "a blocked stale fallback must not produce a canonical copy",
        )

    def test_nowhere_path_still_blocked(self):
        ref, primary_target, _fallback_target, _content = self._run(
            seed_primary=False, seed_fallback=False, fallback_mtime_offset_seconds=None,
        )
        self.assertFalse(ref.get("available"), f"absent at both locations must block, got: {ref}")
        self.assertFalse(primary_target.exists())

    def test_primary_hit_unchanged_no_fallback_copy_logic_triggered(self):
        ref, primary_target, fallback_target, _content = self._run(
            seed_primary=True, seed_fallback=False, fallback_mtime_offset_seconds=None,
        )
        self.assertTrue(ref.get("available"), f"primary hit must still pass, got: {ref}")
        self.assertEqual(primary_target.read_text(encoding="utf-8"), "primary copy\n")
        self.assertFalse(fallback_target.exists())

    def test_fabricated_artifact_cannot_become_available(self):
        """A worker claiming a path that was never written anywhere (not primary, not fallback)
        must never become available -- and must never gain a canonical copy -- no matter what
        text it puts in its own output."""
        ref, primary_target, fallback_target, _content = self._run(
            seed_primary=False, seed_fallback=False, fallback_mtime_offset_seconds=None,
        )
        self.assertFalse(
            ref.get("available"),
            f"a fabricated claim with no artifact at either location must never be available, got: {ref}",
        )
        self.assertNotIn("workspace_divergence", ref)
        self.assertFalse(primary_target.exists())
        self.assertFalse(fallback_target.exists())


if __name__ == "__main__":
    unittest.main()
