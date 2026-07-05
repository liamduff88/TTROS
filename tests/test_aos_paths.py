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

from aos_paths import AosPathError, aos_root, resolve_root_relative


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


if __name__ == "__main__":
    unittest.main()
