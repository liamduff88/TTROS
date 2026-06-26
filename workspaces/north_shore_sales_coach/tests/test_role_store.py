import json
import tempfile
import unittest
from pathlib import Path

from src.role_store import RoleStore


class RoleStoreTests(unittest.TestCase):
    def test_active_known_user_has_role(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roles.json"
            path.write_text(json.dumps({"users": {"42": {"role": "manager", "active": True}}}), encoding="utf-8")
            store = RoleStore(path)
            self.assertEqual(store.role_for(42), "manager")
            self.assertIsNone(store.role_for(99))

    def test_inactive_user_is_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roles.json"
            path.write_text(json.dumps({"users": {"42": {"role": "admin", "active": False}}}), encoding="utf-8")
            self.assertFalse(RoleStore(path).is_authorized("42"))

    def test_inactive_role_is_denied_even_if_marked_active(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roles.json"
            path.write_text(json.dumps({"users": {"42": {"role": "inactive", "active": True}}}), encoding="utf-8")
            self.assertFalse(RoleStore(path).is_authorized("42"))


if __name__ == "__main__":
    unittest.main()
