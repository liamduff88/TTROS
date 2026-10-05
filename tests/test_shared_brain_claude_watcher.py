"""Claude handoff watcher: selection, at-most-once runs per note version, and the run shape.

Runs against a temporary Brain root and a stub `claude` binary; no model call, live Brain untouched.
Revisit: when tools/shared_brain_claude_watcher.py changes. Last touched: 2026-10-04.
"""
import datetime as dt
import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from tools import shared_brain_checkpoint as store
from tools import shared_brain_claude_watcher as watcher

REPO = Path(__file__).resolve().parents[1]
STAMP = {"chatgpt": {"authenticated_identity": "liam-drive-channel", "surface": "chatgpt",
                     "actor_class": "authorised_client", "surface_source": "address"},
         "claude": {"authenticated_identity": "liam", "surface": "claude",
                    "actor_class": "authorised_client", "surface_source": "address"}}
STUB = textwrap.dedent("""\
    #!{python}
    import json, os, sys
    sys.path.insert(0, {repo!r})
    from tools import shared_brain_checkpoint as store
    prompt = sys.stdin.read()
    with open(os.environ["STUB_CALLS"], "a") as handle:
        handle.write(json.dumps({{"argv": sys.argv[1:], "prompt": prompt}}) + "\\n")
    if os.environ.get("STUB_MODE") == "checkpoint":
        ws, version = os.environ["STUB_WS"], int(os.environ["STUB_VERSION"])
        fields = dict(goal="g", done="reviewed", decisions="PASS", work_product_reference="",
                      next_action="ChatGPT should construct the offer.", open_questions="")
        stamp = {{"authenticated_identity": "liam", "surface": "claude",
                  "actor_class": "authorised_client", "surface_source": "address"}}
        store.checkpoint(ws, fields, version, attribution=stamp, root=__import__("pathlib").Path(os.environ["STUB_ROOT"]))
    print(json.dumps({{"is_error": False, "num_turns": 3, "total_cost_usd": 0.0, "permission_denials": [],
                      "result": "v2, next owner ChatGPT"}}))
""")


def note(root, ws, next_action, surface="chatgpt", versions=1):
    for version in range(versions):
        fields = dict(goal="g", done="d", decisions="x", work_product_reference="", next_action=next_action,
                      open_questions="")
        result = store.checkpoint(ws, fields, version, attribution=STAMP[surface], root=root)
        assert result["success"], result


class WatcherTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / "brain"
        (self.root / ".git").mkdir(parents=True)
        self.log = base / "watcher.log"
        self.calls = base / "calls.jsonl"
        self.stub = base / "claude"
        self.stub.write_text(STUB.format(python=sys.executable, repo=str(REPO)), encoding="utf-8")
        self.stub.chmod(0o755)
        os.environ.update(STUB_CALLS=str(self.calls), STUB_ROOT=str(self.root), STUB_MODE="checkpoint")
        patches = [mock.patch.object(watcher, "RUN_DIR", base / "run"),
                   mock.patch.object(watcher, "_preflight", return_value=None)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        for key in ("STUB_CALLS", "STUB_ROOT", "STUB_MODE", "STUB_WS", "STUB_VERSION"):
            os.environ.pop(key, None)
        self.temp.cleanup()

    def tick(self, *extra):
        return watcher.main(["--log", str(self.log), "--claude", str(self.stub), *extra], root=self.root)

    def runs(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def events(self):
        return [entry["event"] for entry in watcher._read_log(self.log)]

    def test_assignment_wording(self):
        yes = ["Claude should resume x", "Claude: review", "claude resumes x", "Claude Code reviews", "**Claude** should"]
        no = ["Liam confirms", "ChatGPT should then Claude", "Claude or ChatGPT should", "Claude/ChatGPT",
              "Claudette", "Review the report", ""]
        self.assertEqual([watcher.assigned_to_claude({"next_action": s}) for s in yes], [True] * len(yes))
        self.assertEqual([watcher.assigned_to_claude({"next_action": s}) for s in no], [False] * len(no))

    def test_nothing_assigned_to_claude_does_nothing(self):
        note(self.root, "liam-stream", "Liam confirms the defaults.")
        note(self.root, "own-stream", "Claude should continue.", surface="claude")
        self.assertEqual(self.tick(), 0)
        self.assertEqual((self.runs(), self.events()), ([], []))

    def test_stale_note_is_not_current(self):
        note(self.root, "old-stream", "Claude should review it.")
        later = watcher._now() + dt.timedelta(hours=watcher.FRESH_HOURS + 1)
        with mock.patch.object(watcher, "_now", return_value=later):
            self.assertEqual(self.tick(), 0)
        self.assertEqual(self.runs(), [])

    def test_one_handoff_runs_once_and_never_again_for_that_version(self):
        note(self.root, "dp-stage4", "Claude should resume dp-stage4 and review the package.", versions=3)
        os.environ.update(STUB_WS="dp-stage4", STUB_VERSION="3")
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.tick(), 0)
        runs = self.runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(self.events(), ["claimed", "finished"])
        finished = watcher._read_log(self.log)[-1]
        self.assertEqual((finished["note_id"], finished["new_version"], finished["checkpointed"], finished["new_surface"]),
                         ("workstream:dp-stage4:v3", 4, True, "claude"))
        self.assertEqual((finished["model_calls"], finished["max_model_calls"]), (1, 1))
        argv, prompt = runs[0]["argv"], runs[0]["prompt"]
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(argv[argv.index("--allowedTools") + 1:], watcher.ALLOWED_TOOLS)
        self.assertTrue(all(tool.startswith(watcher.TOOL_PREFIX) for tool in watcher.ALLOWED_TOOLS))
        self.assertIn("workstream_id `dp-stage4`", prompt)
        self.assertIn("expected_version 3", prompt)
        self.assertEqual(store.resume("dp-stage4", root=self.root)["note"]["version"], 4)

    def test_failed_run_is_not_retried(self):
        note(self.root, "dp-stage4", "Claude should review it.")
        os.environ["STUB_MODE"] = "no-checkpoint"
        self.assertEqual(self.tick(), 1)
        self.assertEqual(self.tick(), 0)
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual(watcher._read_log(self.log)[-1]["checkpointed"], False)

    def test_new_version_handed_back_to_claude_runs_again(self):
        note(self.root, "dp-stage4", "Claude should review it.")
        os.environ.update(STUB_WS="dp-stage4", STUB_VERSION="1")
        self.tick()
        note_v3 = dict(goal="g", done="d", decisions="x", work_product_reference="",
                       next_action="Claude should review the revision.", open_questions="")
        store.checkpoint("dp-stage4", note_v3, 2, attribution=STAMP["chatgpt"], root=self.root)
        os.environ["STUB_VERSION"] = "3"
        self.tick()
        self.assertEqual([entry.get("note_id") for entry in watcher._read_log(self.log) if entry["event"] == "claimed"],
                         ["workstream:dp-stage4:v1", "workstream:dp-stage4:v3"])

    def test_two_handoffs_are_ambiguous_and_logged_once(self):
        note(self.root, "stream-a", "Claude should do a.")
        note(self.root, "stream-b", "Claude should do b.")
        self.tick()
        self.tick()
        self.assertEqual(self.runs(), [])
        self.assertEqual(self.events(), ["ambiguous"])

    def test_version_moved_before_run_is_not_executed(self):
        note(self.root, "dp-stage4", "Claude should review it.")
        real = store.resume

        def racing(workstream_id=None, version=None, *, root=None):
            if workstream_id and racing.calls == 1:
                fields = dict(goal="g", done="d", decisions="x", work_product_reference="",
                              next_action="Claude should review the newer version.", open_questions="")
                store.checkpoint(workstream_id, fields, 1, attribution=STAMP["chatgpt"], root=root)
            racing.calls += bool(workstream_id)
            return real(workstream_id, version, root=root)
        racing.calls = 0
        with mock.patch.object(watcher.checkpoint_store, "resume", side_effect=racing):
            self.tick()
        self.assertEqual((self.runs(), self.events()), ([], ["changed_before_run"]))
        os.environ.update(STUB_WS="dp-stage4", STUB_VERSION="2")
        self.tick()
        self.assertEqual([entry.get("note_id") for entry in watcher._read_log(self.log) if entry["event"] == "claimed"],
                         ["workstream:dp-stage4:v2"])

    def test_blocked_preflight_waits_without_claiming(self):
        note(self.root, "dp-stage4", "Claude should review it.")
        os.environ.update(STUB_WS="dp-stage4", STUB_VERSION="1")
        with mock.patch.object(watcher, "_preflight", return_value="claude_connector_not_connected"):
            self.tick()
            self.tick()
        self.assertEqual((self.runs(), self.events()), ([], ["waiting"]))
        self.tick()
        self.assertEqual(len(self.runs()), 1)

    def test_dry_run_neither_claims_nor_calls(self):
        note(self.root, "dp-stage4", "Claude should review it.")
        self.tick("--dry-run")
        self.assertEqual((self.runs(), self.events()), ([], []))


class PreflightTest(unittest.TestCase):
    def check(self, mcp_output, health_status=200):
        response = mock.MagicMock(status=health_status)
        response.__enter__.return_value = response
        with mock.patch.object(watcher.urllib.request, "urlopen", return_value=response), \
             mock.patch.object(watcher.subprocess, "run",
                               return_value=mock.Mock(stdout=mcp_output, returncode=0)):
            return watcher._preflight("claude")

    def test_connector_state_gates_the_run(self):
        self.assertIsNone(self.check("claude.ai TTROS Shared Brain:\n  Status: ✔ Connected\n"))
        self.assertEqual(self.check("claude.ai TTROS Shared Brain:\n  Status: ! Needs authentication\n"),
                         "claude_connector_not_connected")
        self.assertEqual(self.check("Status: ✔ Connected", health_status=503), "brain_backend_unhealthy")


if __name__ == "__main__":
    unittest.main()
