import tempfile
import unittest
from pathlib import Path

from tools.business_brain import (
    BusinessBrainPointerError,
    business_brain_pointer_for_path,
    resolve_business_brain_pointer,
    resolve_optional_business_brain_pointer,
)


class BusinessBrainPointerTest(unittest.TestCase):
    def test_resolves_canonical_pointer_to_stable_forms(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "memory" / "company.md"
            target.parent.mkdir()
            target.write_text("# Company\n", encoding="utf-8")
            resolved = resolve_business_brain_pointer("business_brain:memory/company.md", root=root)
            self.assertEqual(resolved.pointer, "business_brain:memory/company.md")
            self.assertEqual(resolved.relative_path, "memory/company.md")
            self.assertEqual(resolved.resolved_path, target.resolve())
            self.assertEqual(business_brain_pointer_for_path(target, root=root), resolved.pointer)

    def test_rejects_absolute_traversal_backup_and_noncanonical_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            invalid = (
                "business_brain:/etc/passwd",
                "business_brain:C:/vault/note.md",
                "business_brain:../note.md",
                "business_brain:memory/../note.md",
                "business_brain:_backups/note.md",
                "business_brain:memory\\note.md",
                "business_brain:memory//note.md",
                "business_brain:~/note.md",
            )
            for pointer in invalid:
                with self.subTest(pointer=pointer), self.assertRaises(BusinessBrainPointerError):
                    resolve_business_brain_pointer(pointer, root=root, require_exists=False)

    def test_never_performs_filename_only_lookup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "memory" / "company.md"
            target.parent.mkdir()
            target.write_text("# Company\n", encoding="utf-8")
            with self.assertRaises(BusinessBrainPointerError):
                resolve_business_brain_pointer("business_brain:company.md", root=root)

    def test_rejects_symlink_escape_and_missing_target(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(temp)
            outside = Path(outside_temp) / "outside.md"
            outside.write_text("outside", encoding="utf-8")
            (root / "memory").mkdir()
            (root / "memory" / "escape.md").symlink_to(outside)
            with self.assertRaises(BusinessBrainPointerError):
                resolve_business_brain_pointer("business_brain:memory/escape.md", root=root)
            with self.assertRaises(BusinessBrainPointerError):
                resolve_business_brain_pointer("business_brain:memory/missing.md", root=root)

    def test_optional_resolver_is_graceful_for_unrelated_sources(self):
        self.assertIsNone(resolve_optional_business_brain_pointer(None))
        self.assertIsNone(resolve_optional_business_brain_pointer(""))
        self.assertIsNone(resolve_optional_business_brain_pointer("agentic_os_live:README.md"))


if __name__ == "__main__":
    unittest.main()
