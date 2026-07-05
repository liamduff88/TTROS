import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from src.admin_recovery import main, promote_by_name
import _force_liam_admin


class AdminRecoveryTests(unittest.TestCase):
    def test_promote_by_name_updates_matching_user_without_revealing_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local_state.json"
            path.write_text(
                json.dumps(
                    {
                        "users": {
                            "123456": {
                                "telegram_user_id": "123456",
                                "display_name": "Liam Duff",
                                "role": "manager",
                                "active": True,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(promote_by_name(path, "Liam Duff", "admin"), 1)
            state = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(state["users"]["123456"]["role"], "admin")
            self.assertNotIn("salesperson_id", state["users"]["123456"])

    def test_cli_output_does_not_print_raw_telegram_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local_state.json"
            path.write_text(
                json.dumps(
                    {
                        "users": {
                            "123456": {
                                "telegram_user_id": "123456",
                                "display_name": "Liam Duff",
                                "role": "manager",
                                "active": True,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            with unittest.mock.patch(
                "sys.argv",
                [
                    "admin_recovery",
                    "--promote-name",
                    "Liam Duff",
                    "--role",
                    "admin",
                    "--state-path",
                    str(path),
                ],
            ), redirect_stdout(stdout):
                self.assertEqual(main(), 0)
            output = stdout.getvalue()
            self.assertIn("Liam Duff", output)
            self.assertIn("admin", output)
            self.assertNotIn("123456", output)

    def test_force_liam_admin_uses_package_local_state_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local_state.json"
            path.write_text(
                json.dumps(
                    {
                        "users": {
                            "123456": {
                                "telegram_user_id": "123456",
                                "display_name": "Liam Duff",
                                "role": "manager",
                                "active": True,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            with patch.object(_force_liam_admin, "STATE_PATH", path), redirect_stdout(stdout):
                self.assertEqual(_force_liam_admin.main(), 0)
            state = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(state["users"]["123456"]["role"], "admin")
            output = stdout.getvalue()
            self.assertIn("Liam Duff", output)
            self.assertNotIn("123456", output)


if __name__ == "__main__":
    unittest.main()
