import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from aos_paths import AuthorityError, AosPathError, aos_root, assert_authoritative_root, resolve_root_relative


class AosPathsTest(unittest.TestCase):
    def test_default_root_resolution(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(aos_root(), ROOT)

    def test_env_var_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp)
            with patch.dict(os.environ, {"AOS_ROOT": str(override)}, clear=True):
                self.assertEqual(aos_root(), override.resolve())

    def test_root_relative_path_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                resolve_root_relative("queue/work_items.jsonl", root=root),
                root.resolve() / "queue" / "work_items.jsonl",
            )

    def test_path_traversal_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(AosPathError):
                resolve_root_relative("../outside.txt", root=root)
            with self.assertRaises(AosPathError):
                resolve_root_relative("/tmp/outside.txt", root=root)
            with self.assertRaises(AosPathError):
                resolve_root_relative(r"C:\Users\Admin\outside.txt", root=root)

    def test_linux_native_authority_is_accepted(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            self.assertEqual(Path(tmp).resolve(), assert_authoritative_root(tmp))

    def test_native_windows_authority_is_rejected(self):
        with patch("aos_paths.os.name", "nt"), patch("aos_paths.sys.platform", "win32"):
            with self.assertRaisesRegex(AuthorityError, "requires Linux/POSIX"):
                assert_authoritative_root(r"C:\AgenticOS")

    def test_windows_mount_authority_is_rejected(self):
        with self.assertRaisesRegex(AuthorityError, "Windows-mounted roots"):
            assert_authoritative_root("/mnt/c/AgenticOS")


if __name__ == "__main__":
    unittest.main()
