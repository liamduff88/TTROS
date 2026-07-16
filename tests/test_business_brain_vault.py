import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_business_brain import analyze_vault


class BusinessBrainVaultValidationTest(unittest.TestCase):
    def test_ids_links_reachability_and_backup_exclusion(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            for name in ("app.json", "appearance.json", "core-plugins.json", "graph.json", "workspace.json"):
                path = vault / ".obsidian" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                value = {"search": "-path:_backups"} if name == "graph.json" else {}
                path.write_text(json.dumps(value), encoding="utf-8")
            originals = {
                "README.md": "# Root\n",
                "index/MEMORY_INDEX.md": "# Index\n",
                "memory/company.md": "# Company\nHuman wording.\n",
            }
            ids = {"README.md": "root", "index/MEMORY_INDEX.md": "index", "memory/company.md": "company"}
            for relative, body in originals.items():
                path = vault / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                links = ""
                if relative == "README.md":
                    links = "\n[[index/MEMORY_INDEX|Index]]\n"
                if relative == "index/MEMORY_INDEX.md":
                    links = "\n[[README|Root]] · [[memory/company|Company]]\n"
                path.write_text(f"---\nid: {ids[relative]}\ntype: knowledge\n---\n{body}{links}", encoding="utf-8")
            backup = vault / "_backups" / "memory" / "company.md"
            backup.parent.mkdir(parents=True)
            backup.write_text("# Backup\n", encoding="utf-8")
            before = vault / "before.sha256"
            before.write_text("".join(f"{hashlib.sha256(body.encode()).hexdigest()}  ./{relative}\n" for relative, body in originals.items()), encoding="utf-8")
            result = analyze_vault(vault, before_manifest=before)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["checks"]["canonical_note_count"], 3)
            self.assertEqual(result["root_distances"]["memory/company.md"], 1)
            self.assertNotIn("_backups/memory/company.md", result["canonical_paths"])


if __name__ == "__main__":
    unittest.main()
