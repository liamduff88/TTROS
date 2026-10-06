"""ChatGPT wake signal: one AgentMail email per workstream version newly handed to ChatGPT.

Runs against a temporary Brain root and log; no model call, no email: the send is an injected
recorder, and the real adapter command is only ever invoked with `subprocess.run` mocked.
Revisit: when tools/shared_brain_chatgpt_wake.py changes. Last touched: 2026-10-05.
"""
import datetime as dt
import json
import os
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import shared_brain_checkpoint as store
from tools import shared_brain_claude_watcher as watcher
from tools import shared_brain_chatgpt_wake as wake

CLAUDE = {"authenticated_identity": "liam", "surface": "claude",
          "actor_class": "authorised_client", "surface_source": "address"}
CHATGPT = {"authenticated_identity": "liam-drive-channel", "surface": "chatgpt",
           "actor_class": "authorised_client", "surface_source": "drive"}
DAVID = {"authenticated_identity": "david", "surface": "david",
         "actor_class": "authorised_client", "surface_source": "local-stdio"}


class ChatGPTWakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "brain"
        (self.root / ".git").mkdir(parents=True)
        env = mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_ARTIFACTS": str(base / "artifacts")})
        env.start()
        self.addCleanup(env.stop)
        (base / "artifacts").mkdir()
        self.log = base / "wake.log"
        self.sent = []

    def write(self, ws, next_action, version, attribution=CLAUDE):
        fields = dict(goal="g", done="d", decisions="", work_product_reference="",
                      next_action=next_action, open_questions="")
        out = store.checkpoint(ws, fields, version, attribution=attribution, root=self.root)
        self.assertTrue(out["success"], out)
        return out["note"]

    def send(self, recipient, subject, body):
        self.sent.append((recipient, subject, body))
        return {"ok": True, "data": {"successful": True, "data": {"message_id": f"m{len(self.sent)}"}}}

    def run_tick(self, send=None, **extra):
        return wake.run(root=self.root, log=self.log, recipient="liam@timetorevenue.com",
                        send=send or self.send, is_authorized=lambda r: True, **extra)

    def events(self, name):
        return [e for e in watcher._read_log(self.log) if e.get("event") == name]

    def test_new_chatgpt_version_wakes_once_with_routing_fields_only(self):
        self.write("alpha-stream", "ChatGPT should draft the launch email from result.md.", 0)
        actions = self.run_tick()
        self.assertEqual([a["event"] for a in actions], ["wake_sent"])
        self.assertEqual(len(self.sent), 1)
        recipient, subject, body = self.sent[0]
        self.assertEqual(recipient, "liam@timetorevenue.com")
        self.assertEqual(subject, "TTROS ChatGPT handoff: alpha-stream v1")
        self.assertTrue(body.startswith("TTROS-SHARED-BRAIN-WAKE v1\nworkstream_id: alpha-stream\nversion: 1\naction: resume\n"))
        self.assertIn("projection: TTROS Memory Exchange/06_WORKSTREAMS_READ/alpha-stream.md", body)
        self.assertNotIn("launch email", body)  # wake signal only: no note content
        self.assertFalse(store._host_path(body))
        self.assertEqual(self.events("wake_sent")[0]["provider_message_id"], "m1")

    def test_duplicate_observation_of_the_same_version_does_not_resend(self):
        self.write("alpha-stream", "ChatGPT: review the draft.", 0)
        self.run_tick()
        self.assertEqual(self.run_tick(), [])
        self.assertEqual(self.run_tick(), [])
        self.assertEqual(len(self.sent), 1)

    def test_next_version_assigned_to_chatgpt_wakes_again(self):
        self.write("alpha-stream", "ChatGPT should review the draft.", 0)
        self.run_tick()
        self.write("alpha-stream", "Claude should tighten the draft.", 1, CHATGPT)
        self.assertEqual(self.run_tick(), [])  # Claude's turn: no ChatGPT wake
        self.write("alpha-stream", "ChatGPT should approve the tightened draft.", 2)
        self.run_tick()
        self.assertEqual([s[1] for s in self.sent], ["TTROS ChatGPT handoff: alpha-stream v1",
                                                     "TTROS ChatGPT handoff: alpha-stream v3"])

    def test_independent_workstreams_each_get_their_own_wake(self):
        self.write("alpha-stream", "ChatGPT should draft A.", 0)
        self.write("beta-stream", "ChatGPT should draft B.", 0, DAVID)
        self.write("beta-stream", "ChatGPT should draft B again.", 1)
        self.run_tick()
        subjects = sorted(s[1] for s in self.sent)
        self.assertEqual(subjects, ["TTROS ChatGPT handoff: alpha-stream v1", "TTROS ChatGPT handoff: beta-stream v2"])
        bodies = {s[1]: s[2] for s in self.sent}
        self.assertIn("workstream_id: beta-stream\nversion: 2", bodies["TTROS ChatGPT handoff: beta-stream v2"])
        self.assertNotIn("alpha", bodies["TTROS ChatGPT handoff: beta-stream v2"])

    def test_superseded_version_is_never_sent(self):
        old = self.write("alpha-stream", "ChatGPT should review v1.", 0)
        self.write("alpha-stream", "Liam: decide between A and B.", 1, CHATGPT)
        with mock.patch.object(wake, "candidates", return_value=[old]):
            actions = self.run_tick()
        self.assertEqual([a["event"] for a in actions], ["changed_before_wake"])
        self.assertEqual(self.sent, [])
        self.assertEqual(self.events("wake_claimed"), [])

    def test_superseded_by_a_newer_chatgpt_version_wakes_only_the_newer_one(self):
        old = self.write("alpha-stream", "ChatGPT should review v1.", 0)
        self.write("alpha-stream", "ChatGPT should review v2 instead.", 1, CLAUDE)
        with mock.patch.object(wake, "candidates", return_value=[old]):
            self.run_tick()
        self.run_tick()
        self.assertEqual([s[1] for s in self.sent], ["TTROS ChatGPT handoff: alpha-stream v2"])

    def test_non_chatgpt_or_ambiguous_assignment_sends_nothing(self):
        for index, action in enumerate(["Claude should finish the draft.", "Liam: answer the open questions.",
                                        "David or ChatGPT should do the follow-up Liam names.",
                                        "ChatGPT or Claude should review.", "ChatGPT/Claude review",
                                        "Review the Stage 2 build report", "chatgptish tool review"]):
            self.write(f"stream-{index:02d}", action, 0)
        self.assertEqual(self.run_tick(), [])
        self.assertEqual(self.sent, [])

    def test_a_note_chatgpt_wrote_or_an_old_note_never_wakes(self):
        self.write("self-stream", "ChatGPT should continue.", 0, CHATGPT)
        self.assertEqual(self.run_tick(), [])
        old = self.write("old-stream", "ChatGPT should continue.", 0)
        later = dt.datetime.fromisoformat(old["updated"].replace("Z", "+00:00")) + dt.timedelta(hours=13)
        with mock.patch.object(wake, "_now", return_value=later):
            self.assertEqual(self.run_tick(), [])
        self.assertEqual(self.sent, [])

    def test_failed_send_is_logged_and_not_retried(self):
        self.write("alpha-stream", "ChatGPT should review.", 0)
        actions = self.run_tick(send=lambda *a: {"ok": False, "error": "provider down"})
        self.assertEqual(actions[0]["event"], "wake_failed")
        self.assertEqual(self.run_tick(), [])
        self.assertEqual(self.sent, [])

        self.write("beta-stream", "ChatGPT should review.", 0)
        def boom(*args):
            raise TimeoutError
        self.assertEqual(self.run_tick(send=boom)[0]["reason"], "TimeoutError")
        self.assertEqual(self.run_tick(), [])

    def test_unacknowledged_provider_response_is_a_failure(self):
        self.write("alpha-stream", "ChatGPT should review.", 0)
        actions = self.run_tick(send=lambda *a: {"ok": True, "data": {"successful": False}})
        self.assertEqual(actions[0]["event"], "wake_failed")

    def test_recipient_outside_the_allowlist_blocks_every_send(self):
        self.write("alpha-stream", "ChatGPT should review.", 0)
        for _ in range(2):
            actions = wake.run(root=self.root, log=self.log, recipient="someone@example.org", send=self.send)
            self.assertEqual(actions, [])
        self.assertEqual(self.sent, [])
        self.assertEqual(len(self.events("wake_blocked")), 1)
        self.assertEqual(self.events("wake_claimed"), [])

    def test_real_allowlist_accepts_only_the_internal_recipient(self):
        self.assertTrue(wake.authorized("liam@timetorevenue.com"))
        self.assertFalse(wake.authorized("someone@example.org"))
        self.assertFalse(wake.authorized(""))

    def test_dry_run_sends_and_logs_nothing(self):
        self.write("alpha-stream", "ChatGPT should review.", 0)
        actions = self.run_tick(dry_run=True)
        self.assertEqual(actions, [{"note_id": "workstream:alpha-stream:v1", "dry_run": True, "would_wake": True}])
        self.assertEqual(self.sent, [])
        self.assertFalse(self.log.exists())

    def test_per_tick_bound_leaves_the_rest_for_the_next_tick(self):
        for index in range(wake.MAX_WAKES_PER_TICK + 2):
            self.write(f"stream-{index:02d}", "ChatGPT should review.", 0)
        self.run_tick()
        self.assertEqual(len(self.sent), wake.MAX_WAKES_PER_TICK)
        self.run_tick()
        self.assertEqual(len(self.sent), wake.MAX_WAKES_PER_TICK + 2)
        self.assertEqual(len({s[1] for s in self.sent}), wake.MAX_WAKES_PER_TICK + 2)

    def test_send_uses_the_backends_governed_agentmail_command(self):
        completed = mock.Mock(stdout=json.dumps({"ok": True, "data": {"successful": True}}), stderr="")
        with mock.patch.object(wake.subprocess, "run", return_value=completed) as run:
            out = wake.agentmail_send("liam@timetorevenue.com", "TTROS ChatGPT handoff: a v1", "body")
        self.assertTrue(wake._acknowledged(out))
        argv = run.call_args.args[0]
        self.assertEqual(argv[:2], ["bash", "-lc"])
        command = argv[2]
        self.assertIn("python3 connectors/composio_access_adapter.py run agent_mail AGENT_MAIL_SEND_EMAIL --data ", command)
        self.assertTrue(command.endswith("--execute --operator-command"))
        argv = shlex.split(command)
        self.assertEqual(argv[argv.index("--target") + 1], "liam@timetorevenue.com")
        payload = json.loads(argv[argv.index("--data") + 1])
        self.assertEqual(payload["to"], ["liam@timetorevenue.com"])
        self.assertEqual(payload["inbox_id"], "olmec1@agentmail.to")
        self.assertEqual(payload["subject"], "TTROS ChatGPT handoff: a v1")
        with mock.patch.object(wake.subprocess, "run", return_value=mock.Mock(stdout="not json", stderr="")):
            self.assertFalse(wake._acknowledged(wake.agentmail_send("liam@timetorevenue.com", "s", "b")))

    def test_adapter_target_is_the_exact_normalized_recipient_as_one_quoted_argument(self):
        completed = mock.Mock(stdout=json.dumps({"ok": True}), stderr="")
        for given, expected in (("  Liam@TimeToRevenue.com ", "liam@timetorevenue.com"),
                                ("x@y.z; touch /tmp/pwn $(id) 'q'", "x@y.z; touch /tmp/pwn $(id) 'q'")):
            with mock.patch.object(wake.subprocess, "run", return_value=completed) as run:
                wake.agentmail_send(given, "s", "b")
            argv = shlex.split(run.call_args.args[0][2])
            self.assertEqual(argv.count("--target"), 1)
            self.assertEqual(argv[argv.index("--target") + 1], expected)
            self.assertEqual(json.loads(argv[argv.index("--data") + 1])["to"], [expected])
            self.assertEqual(argv[-2:], ["--execute", "--operator-command"])

    def test_real_adapter_command_reaches_authorization_and_answers_json(self):
        # The unmocked adapter, through the wake's own command. Only the recipient being outside the
        # allowlist keeps this from transmitting: hiding HOME/PATH does NOT stop a send (2026-10-06,
        # an allowlisted probe under this env delivered). Never point this at an allowlisted address.
        # Before the PYTHONPATH fix this returned adapter_returned_no_json (ModuleNotFoundError).
        env = {"HOME": self.temp.name, "PATH": "/usr/bin:/bin"}
        with mock.patch.dict(os.environ, env, clear=True):
            out = wake.agentmail_send("nobody@example.invalid", "s", "probe only")
        self.assertNotIn("adapter_returned_no_json", str(out.get("error")))
        self.assertIs(out.get("ok"), False)
        self.assertFalse(wake._acknowledged(out))
        self.assertIn("transmitted", out)
        self.assertIs(out["transmitted"], False)

    def test_claude_watcher_selection_is_unchanged_by_chatgpt_notes(self):
        self.write("alpha-stream", "ChatGPT should review.", 0)
        self.write("beta-stream", "Claude should draft.", 0, DAVID)
        self.run_tick()
        picked = [n["id"] for n in watcher.candidates(watcher._now(), watcher.FRESH_HOURS, self.root)]
        self.assertEqual(picked, ["workstream:beta-stream:v1"])
        self.assertEqual([s[1] for s in self.sent], ["TTROS ChatGPT handoff: alpha-stream v1"])


if __name__ == "__main__":
    unittest.main()
