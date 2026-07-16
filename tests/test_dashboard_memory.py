import importlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class DashboardMemoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = importlib.import_module("dashboard.backend.main")

    def test_reads_canonical_vault_and_never_infers_promotions(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            (vault / "index").mkdir()
            (vault / "memory").mkdir()
            (vault / "_backups").mkdir()
            (vault / "README.md").write_text("---\nid: brain-root\ntype: navigation\n---\n# Brain\n", encoding="utf-8")
            (vault / "index" / "MEMORY_INDEX.md").write_text("---\nid: brain-index\ntype: index\n---\n# Index\n", encoding="utf-8")
            (vault / "memory" / "company.md").write_text("---\nid: company\ntype: memory\n---\n# Company\n", encoding="utf-8")
            (vault / "_backups" / "old.md").write_text("# old\n", encoding="utf-8")
            fake_queue = [{"id": "AOS-1", "title": "Memory promotion", "tags": ["memory"], "status": "human_review"}]
            with mock.patch.object(self.backend.business_brain, "BUSINESS_BRAIN_ROOT", vault), mock.patch.object(self.backend, "_read_queue_items", return_value=fake_queue):
                result = self.backend.dashboard_memory()
            self.assertTrue(result["brain"]["available"])
            self.assertEqual(result["brain"]["root"], "business_brain:README.md")
            self.assertEqual(result["brain"]["file_count"], 3)
            self.assertEqual(result["brain"]["blocked_path_count"], 1)
            self.assertEqual(result["promotion_queue"], [])
            self.assertEqual(result["promotion_state"]["mode"], "operational")
            self.assertTrue(result["promotion_state"]["available"])
            self.assertEqual(result["promotion_state"]["automatic_classes"], ["generated_marker_section"])
            self.assertEqual(result["promotion_state"]["review_route"], "human_review")
            self.assertNotIn("_backups", str(result["files"]))
            self.assertIn("business_brain:memory/company.md", {row["path"] for row in result["files"]})
            titles = {row["path"]: row["title"] for row in result["files"]}
            self.assertEqual(titles["business_brain:memory/company.md"], "Company")
            self.assertEqual({row["retrieval_route"] for row in result["brain_context_used"]}, {"pointer"})


if __name__ == "__main__":
    unittest.main()
