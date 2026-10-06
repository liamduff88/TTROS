"""Runs tools/aos-linux-backup.sh against throwaway roots: local snapshot, external copy, retention."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "aos-linux-backup.sh"
OLD_STAMPS = [f"agentic-os-202609{day:02d}T010001Z" for day in range(1, 10)]


class LinuxBackupScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-backup-test-"))
        self.repo = self.tmp / "repo"
        (self.repo / "tools").mkdir(parents=True)
        shutil.copy2(SCRIPT, self.repo / "tools" / SCRIPT.name)
        shutil.copy2(ROOT / "tools" / "aos_paths.py", self.repo / "tools" / "aos_paths.py")
        for name in ("AGENTS.md", "CODEX.md"):
            (self.repo / name).write_text(name, encoding="utf-8")
        (self.repo / ".env").write_text("not copied", encoding="utf-8")
        self.brain = self.tmp / "brain"
        (self.brain / "memory").mkdir(parents=True)
        (self.brain / "README.md").write_text("brain", encoding="utf-8")
        (self.brain / "memory" / "fact.md").write_text("fact", encoding="utf-8")
        self.local = self.tmp / "local"
        for stamp in OLD_STAMPS:
            (self.local / stamp).mkdir(parents=True)
            (self.local / stamp / "AGENTS.md").write_text("old", encoding="utf-8")
        (self.local / "unrelated").mkdir()
        self.external = self.tmp / "external"
        self.external.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_backup(self, external=None, path_prefix=None):
        env = dict(os.environ)
        env.update(
            AOS_ROOT=str(self.repo),
            AOS_BACKUP_ROOT=str(self.local),
            AOS_EXTERNAL_BACKUP_ROOT=str(external or self.external),
            AOS_BRAIN_ROOT=str(self.brain),
        )
        if path_prefix:
            env["PATH"] = f"{path_prefix}:{env['PATH']}"
        return subprocess.run(
            ["bash", str(self.repo / "tools" / SCRIPT.name)], env=env, capture_output=True, text=True, timeout=120
        )

    def snapshots(self):
        return sorted(p.name for p in self.local.iterdir() if p.name.startswith("agentic-os-"))

    def last_receipt(self):
        lines = (self.repo / "queue" / "receipts" / "linux-backups.jsonl").read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1])

    def test_success_copies_off_machine_and_keeps_newest_seven(self):
        result = self.run_backup()
        self.assertEqual(0, result.returncode, result.stderr)
        snaps = self.snapshots()
        self.assertEqual(7, len(snaps))
        self.assertEqual(OLD_STAMPS[3:], snaps[:6])
        self.assertTrue((self.local / "unrelated").is_dir())
        self.assertEqual("*\n", (self.local / ".ignore").read_text(encoding="utf-8"))
        [ext] = list(self.external.iterdir())
        self.assertFalse(ext.name.endswith(".partial"))
        self.assertEqual("AGENTS.md", (ext / "AgenticOSLive" / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual("fact", (ext / "BusinessBrain" / "memory" / "fact.md").read_text(encoding="utf-8"))
        self.assertFalse((ext / "AgenticOSLive" / ".env").exists())
        self.assertTrue((ext / "MANIFEST.txt").is_file())
        receipt = self.last_receipt()
        self.assertEqual("success", receipt["status"])
        self.assertEqual(str(ext), receipt["external_snapshot_path"])
        self.assertEqual({"keep": 7, "pruned": 3}, receipt["local_retention"])

    def test_unplugged_drive_fails_and_prunes_nothing(self):
        result = self.run_backup(external=self.tmp / "missing-drive" / "TTROS_Backups")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(10, len(self.snapshots()))
        self.assertFalse((self.tmp / "missing-drive").exists())
        receipt = self.last_receipt()
        self.assertEqual("fail", receipt["status"])
        self.assertIn("drive disconnected", receipt["errors"][0])

    def test_corrupted_external_copy_fails_verification(self):
        shim = self.tmp / "shim"
        shim.mkdir()
        real_rsync = shutil.which("rsync")
        (shim / "rsync").write_text(
            "#!/usr/bin/env bash\n"
            f'"{real_rsync}" "$@"; rc=$?\n'
            'last="${!#}"\n'
            'if [[ "$*" != *--dry-run* && "$last" == */BusinessBrain/ ]]; then printf x >> "$last/memory/fact.md"; fi\n'
            "exit $rc\n",
            encoding="utf-8",
        )
        (shim / "rsync").chmod(0o755)
        result = self.run_backup(path_prefix=shim)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(10, len(self.snapshots()))
        self.assertEqual("fail", self.last_receipt()["status"])
        self.assertTrue(all(p.name.endswith(".partial") for p in self.external.iterdir()))


if __name__ == "__main__":
    unittest.main()
