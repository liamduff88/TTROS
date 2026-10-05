"""Shared Brain workflow start/finish: David opens a bounded workstream for Claude; Liam gets the result back.

Runs against a temporary Brain root, artifact area and logs; no model call, no Telegram send,
live Brain untouched: durable submit is an injected idempotent fake, and the real Brain write
path is patched to fail the test if anything reaches it.
Revisit: when tools/shared_brain_workflow.py changes. Last touched: 2026-10-05.
"""
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import shared_brain_chatgpt_wake as wake
from tools import shared_brain_checkpoint as store
from tools import shared_brain_claude_watcher as watcher
from tools import shared_brain_workflow as workflow

DAVID = {"authenticated_identity": "david", "surface": "david",
         "actor_class": "authorised_client", "surface_source": "local-stdio"}
CLAUDE = {"authenticated_identity": "liam", "surface": "claude",
          "actor_class": "authorised_client", "surface_source": "address"}
class FakeSubmit:
    """The existing submit's contract, in memory: one record per idempotency key."""

    def __init__(self):
        self.calls, self.records = [], {}

    def __call__(self, type, title, body, source_refs, idempotency_key, workstream_id=None, *, attribution):
        self.calls.append(dict(type=type, title=title, body=body, source_refs=source_refs,
                               key=idempotency_key, workstream_id=workstream_id, attribution=attribution))
        record_id = "shared-submit-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]
        duplicate = record_id in self.records
        self.records.setdefault(record_id, body)
        return {"success": True, "record_id": record_id, "status": "unconfirmed", "duplicate": duplicate,
                "reference": f"business_brain:inbox/distilled_packets/{record_id}.md", "commit": "c0ffee",
                "sync_status": "synced"}


REQUEST = ("Start a Shared Brain workflow to validate this digital-product idea: a Notion client "
           "tracker for freelancers. Bring me back the finished result.")
REQUEST_B = "Start a Shared Brain workflow to draft the Etsy listing copy for the Notion client tracker."


class WorkflowFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "brain"
        (self.root / ".git").mkdir(parents=True)
        (base / "exchange").mkdir()
        env = mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_ARTIFACTS": str(base / "exchange" / "artifacts"),
                                           "TTROS_DRIVEFS_INDEX": "", "TTROS_SHARED_BRAIN_SUBMIT": "1"})
        env.start()
        self.addCleanup(env.stop)
        from tools import brain_memory
        for module in {brain_memory, sys.modules.get("brain_memory")} - {None}:
            guard = mock.patch.object(module, "write_transaction", side_effect=AssertionError("live Brain write"))
            self.addCleanup(lambda written=guard.start(): self.assertFalse(written.called, "live Brain write attempted"))
            self.addCleanup(guard.stop)
        self.log = base / "workflow.log"
        self.watcher_log = base / "watcher.log"
        self.sent = []
        self.submit = FakeSubmit()

    def start(self, request=REQUEST, workflow_id=""):
        return workflow.start(request, workflow_id, attribution=DAVID, root=self.root,
                              log=self.log, watcher_log=self.watcher_log)

    def report(self, send=None):
        return workflow.report(root=self.root, log=self.log, watcher_log=self.watcher_log,
                               send=send or (lambda chat, text: self.sent.append(text)), recipient="operator",
                               submit=self.submit)

    def claim(self, ws, version):
        with self.watcher_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": "claimed", "note_id": f"workstream:{ws}:v{version}"}) + "\n")

    def ask_liam(self, ws, version, surface="claude", next_action="Liam: answer the open questions.",
                 questions="Which launch price: US$29 or US$34?"):
        fields = dict(goal="g", done="Drafted the offer.", decisions="Etsy-first.", work_product_reference="",
                      next_action=next_action, open_questions=questions)
        out = store.checkpoint(ws, fields, version, attribution=dict(CLAUDE, surface=surface), root=self.root,
                               work_product={"name": "result.md", "content": "# Draft offer\nUS$29 or US$34"})
        self.assertTrue(out["success"], out)
        return out["note"]

    def waiting_for_liam(self, request=REQUEST, **kwargs):
        """A started workflow whose unattended pass handed a question back to Liam (v2)."""
        ws = self.start(request)["workstream_id"]
        self.claim(ws, 1)
        self.ask_liam(ws, 1, **kwargs)
        return ws

    def questions_sent(self):
        """Each Telegram question by the workstream named on its first line."""
        return {text.splitlines()[0].split()[2]: text for text in self.sent if text.startswith("TTROS WORKSTREAM ")}

    def claude_returns(self, ws, version, next_action="Liam: review the finished result.", result="# Verdict\nGO"):
        fields = dict(goal="g", done="Validated the idea.", decisions="GO at US$29.", work_product_reference="",
                      next_action=next_action, open_questions="")
        out = store.checkpoint(ws, fields, version, attribution=CLAUDE, root=self.root,
                               work_product={"name": "result.md", "content": result})
        self.assertTrue(out["success"], out)


class WorkflowTests(WorkflowFixture):
    def test_adhoc_start_opens_a_note_the_claude_watcher_runs(self):
        out = self.start()
        self.assertTrue(out["success"], out)
        ws = out["workstream_id"]
        self.assertTrue(ws.startswith("validate-digital-product-notion-client"), ws)
        resumed = store.resume(ws, root=self.root)
        note = resumed["note"]
        self.assertEqual((note["version"], note["surface"]), (1, "david"))
        self.assertTrue(watcher.assigned_to_claude(note))
        self.assertIn("ad-hoc bounded workstream", note["goal"])
        self.assertEqual(note["work_product_reference"], f"artifact:{ws}/workflow-brief.md")
        brief = resumed["work_product"]["content"]
        self.assertIn(REQUEST, brief)
        self.assertIn("Ad-hoc bounded Shared Brain workstream", brief)
        self.assertIn("Do not submit", brief)
        self.assertEqual([n["id"] for n in watcher.candidates(workflow._now(), 12, self.root)], [note["id"]])

    def test_named_start_carries_the_registry_workflow_method(self):
        out = self.start("Run the revenue sales prep workflow for Acme and bring me the result.", "revenue_sales_prep")
        self.assertTrue(out["success"], out)
        brief = store.resume(out["workstream_id"], root=self.root)["work_product"]["content"]
        self.assertIn("Named TTROS workflow `revenue_sales_prep`", brief)
        method = (workflow.REPO / "workflows/revenue_sales_prep/workflow.md").read_text(encoding="utf-8")
        self.assertIn(method.splitlines()[0], brief)
        self.assertNotIn("/home/", brief)

    def test_unknown_workflow_is_refused_and_writes_nothing(self):
        out = self.start(workflow_id="not-a-workflow")
        self.assertFalse(out["success"])
        self.assertIn("revenue_sales_prep", out["named_workflows"])
        self.assertEqual(store.resume(root=self.root)["workstreams"], [])
        self.assertFalse(self.log.exists())

    def test_unrelated_start_is_not_blocked_by_a_pending_claude_handoff(self):
        first = self.start()
        second = self.start(REQUEST_B)
        self.assertTrue(second["success"], second)
        self.assertEqual(sorted(note["workstream_id"] for note in watcher.candidates(workflow._now(), 12, self.root)),
                         sorted([first["workstream_id"], second["workstream_id"]]))

    def test_duplicate_start_of_the_same_waiting_workflow_is_refused(self):
        first = self.start()
        refused = self.start()
        self.assertFalse(refused["success"])
        self.assertEqual(refused["pending_workstreams"], [first["workstream_id"]])
        same_id = workflow.start(REQUEST_B, "", first["workstream_id"], attribution=DAVID, root=self.root,
                                 log=self.log, watcher_log=self.watcher_log)
        self.assertIn("already exists", same_id["error"])
        self.assertEqual(store.resume(first["workstream_id"], root=self.root)["note"]["version"], 1)
        self.claim(first["workstream_id"], 1)
        second = self.start()
        self.assertTrue(second["success"], second)
        self.assertEqual(second["workstream_id"], first["workstream_id"] + "-2")

    def test_start_prints_nothing_because_david_stdio_is_the_protocol(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertTrue(self.start()["success"])
        self.assertEqual(buffer.getvalue(), "")

    def test_report_sends_the_result_once_when_back_with_liam(self):
        ws = self.start()["workstream_id"]
        self.assertEqual(self.report(), [])  # still Claude's turn
        self.claude_returns(ws, 1, result="# Verdict\nGO: launch at US$29 on Etsy.")
        actions = self.report()
        self.assertEqual([a["event"] for a in actions], ["submitted", "reported"])
        self.assertEqual(len(self.sent), 1)
        self.assertIn(f"Shared Brain workflow COMPLETE: {ws}", self.sent[0])
        # No Drive index here, so no link can be produced: the result is inlined as the fallback.
        self.assertIn("No Drive link was available", self.sent[0])
        self.assertIn("GO: launch at US$29 on Etsy.", self.sent[0])
        self.assertEqual(self.report(), [])
        self.assertEqual(len(self.sent), 1)

    def test_report_stays_silent_while_another_surface_has_the_work(self):
        ws = self.start()["workstream_id"]
        self.claude_returns(ws, 1, next_action="ChatGPT should construct the offer.")
        self.assertEqual(self.report(), [])
        self.assertEqual(self.sent, [])

    def test_report_tells_liam_when_claudes_pass_ended_without_a_checkpoint(self):
        ws = self.start()["workstream_id"]
        self.watcher_log.write_text(json.dumps({"event": "finished", "note_id": f"workstream:{ws}:v1",
                                                "checkpointed": False, "aborted": "timeout"}) + "\n")
        self.report()
        self.report()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("did not finish (timeout)", self.sent[0])

    def test_failed_send_is_retried_a_bounded_number_of_times(self):
        ws = self.start()["workstream_id"]
        self.claude_returns(ws, 1)

        def broken(chat, text):
            raise OSError("bridge down")

        for _ in range(workflow.MAX_REPORT_ATTEMPTS + 2):
            self.report(send=broken)
        failures = [e for e in watcher._read_log(self.log) if e["event"] == "report_failed"]
        self.assertEqual(len(failures), workflow.MAX_REPORT_ATTEMPTS)

    def test_long_result_is_truncated_for_telegram(self):
        ws = self.start()["workstream_id"]
        self.claude_returns(ws, 1, result="x" * 15_000)
        self.report()
        self.assertLessEqual(len(self.sent[0]), workflow.MAX_MESSAGE_CHARS)
        self.assertIn(f"ask David to resume {ws}", self.sent[0])

    def drive_fixture(self, *, result_id="1ResultFileId_abcdefghij", indexed=True):
        """A Drive for Desktop mount and its index, with the newest rows left in the WAL as live."""
        base = Path(self.temp.name)
        artifacts = base / "G" / "My Drive" / "TTROS Memory Exchange" / "07_WORKSTREAM_ARTIFACTS"
        artifacts.mkdir(parents=True)
        index = base / "DriveFS" / "1234" / "metadata_sqlite_db"
        index.parent.mkdir(parents=True)
        os.environ["TTROS_SHARED_BRAIN_ARTIFACTS"] = str(artifacts)
        os.environ["TTROS_DRIVEFS_INDEX"] = str(base / "DriveFS" / "[0-9]*" / "metadata_sqlite_db")
        db = sqlite3.connect(index)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA wal_autocheckpoint=0")
        db.execute("CREATE TABLE items (stable_id INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, local_title TEXT, "
                   "is_folder BOOLEAN NOT NULL, trashed BOOLEAN NOT NULL, is_tombstone BOOLEAN NOT NULL)")
        db.execute("CREATE TABLE stable_parents (item_stable_id INTEGER NOT NULL, parent_stable_id INTEGER NOT NULL, "
                   "PRIMARY KEY (item_stable_id, parent_stable_id))")
        self.addCleanup(db.close)
        self.drive_db = db
        return artifacts, result_id, indexed

    def index_workstream(self, ws, result_id, with_result=True):
        rows = [(1, "0RootMyDriveId", "My Drive", 1, None), (2, "1ExchangeFolderIdxx", "TTROS Memory Exchange", 1, 1),
                (3, "1ArtifactsFolderIdx", "07_WORKSTREAM_ARTIFACTS", 1, 2), (4, "1WorkstreamFolderId-abc", ws, 1, 3),
                (5, "1BriefFileIdxxxxxx", "workflow-brief.md", 0, 4)]
        if with_result:
            rows.append((6, result_id, "result.md", 0, 4))
        for stable_id, cloud_id, title, folder, parent in rows:
            self.drive_db.execute("INSERT OR IGNORE INTO items VALUES (?, ?, ?, ?, 0, 0)", (stable_id, cloud_id, title, folder))
            if parent:
                self.drive_db.execute("INSERT OR IGNORE INTO stable_parents VALUES (?, ?)", (stable_id, parent))
        self.drive_db.commit()

    def test_finish_message_links_the_drive_result_and_does_not_inline_it(self):
        _, result_id, _ = self.drive_fixture()
        ws = self.start()["workstream_id"]
        self.index_workstream(ws, result_id)
        body = "Full analysis paragraph that must stay in Drive. " * 200
        self.claude_returns(ws, 1, result=f"# Verdict: GO at US$29\n\n{body}")
        self.assertTrue(Path(self.drive_db.execute("PRAGMA database_list").fetchone()[2] + "-wal").stat().st_size > 0)
        actions = self.report()
        self.assertEqual([a["event"] for a in actions], ["submitted", "reported"])
        text = self.sent[0]
        self.assertIn(f"Shared Brain workflow COMPLETE: {ws}", text)
        self.assertIn("Saved to the Brain as a durable record shared-submit-", text)
        self.assertIn("Verdict: GO at US$29", text)
        self.assertIn("Done: Validated the idea.", text)
        self.assertIn(f"https://drive.google.com/file/d/{result_id}/view", text)
        self.assertIn("https://drive.google.com/drive/folders/1WorkstreamFolderId-abc", text)
        self.assertNotIn("Full analysis paragraph", text)
        self.assertNotIn("artifact:", text)
        self.assertLess(len(text), 600)
        self.assertEqual(actions[1]["reference"], f"artifact:{ws}/result.md")
        self.assertEqual(actions[1]["drive_link"], f"https://drive.google.com/file/d/{result_id}/view")

    def test_report_waits_for_drive_upload_then_falls_back_to_inline(self):
        _, result_id, _ = self.drive_fixture(result_id="local-12345678901")
        ws = self.start()["workstream_id"]
        self.index_workstream(ws, result_id)  # still Drive for Desktop's local id: not uploaded
        self.claude_returns(ws, 1, result="# Verdict\nGO: launch at US$29 on Etsy.")
        self.assertEqual([a["event"] for a in self.report()], ["submitted"])
        self.assertEqual(self.report(), [])
        self.assertEqual(self.sent, [])
        later = workflow._now() + workflow.DRIVE_LINK_GRACE + dt.timedelta(minutes=1)
        with mock.patch.object(workflow, "_now", return_value=later):
            self.assertEqual([a["event"] for a in self.report()], ["reported"])
        self.assertIn("No Drive link was available", self.sent[0])
        self.assertIn("GO: launch at US$29 on Etsy.", self.sent[0])

    def test_report_sends_links_once_the_upload_is_indexed(self):
        _, result_id, _ = self.drive_fixture()
        ws = self.start()["workstream_id"]
        self.index_workstream(ws, result_id, with_result=False)
        self.claude_returns(ws, 1)
        self.assertEqual([a["event"] for a in self.report()], ["submitted"])
        self.index_workstream(ws, result_id)
        self.report()
        self.assertEqual(len(self.sent), 1)
        self.assertIn(f"https://drive.google.com/file/d/{result_id}/view", self.sent[0])

    def test_finished_result_is_submitted_once_and_the_workstream_marked_complete(self):
        ws = self.start()["workstream_id"]
        self.claude_returns(ws, 1, result="# Verdict: GO\nLaunch at US$29 on Etsy.")
        actions = self.report()
        self.assertEqual([a["event"] for a in actions], ["submitted", "reported"])
        self.assertEqual(len(self.submit.calls), 1)
        call = self.submit.calls[0]
        self.assertEqual((call["type"], call["title"], call["source_refs"], call["workstream_id"]),
                         ("deliverable", "Verdict: GO", [ws], ws))
        self.assertEqual(call["body"], "# Verdict: GO\nLaunch at US$29 on Etsy.")
        self.assertEqual(call["key"], f"workflow-{ws}-v2")
        self.assertEqual(call["attribution"], workflow.FINISH_STAMP)
        record_id = next(iter(self.submit.records))
        note = store.resume(ws, root=self.root)["note"]
        self.assertEqual(note["version"], 3)
        self.assertTrue(note["done"].startswith("COMPLETE. Validated the idea."), note["done"])
        self.assertIn(f"business_brain:inbox/distilled_packets/{record_id}.md", note["decisions"])
        self.assertIn("GO at US$29.", note["decisions"])
        self.assertTrue(note["next_action"].startswith("Liam: COMPLETE"), note["next_action"])
        self.assertEqual(note["work_product_reference"], f"artifact:{ws}/result.md")
        self.assertEqual((note["surface"], note["surface_source"]), ("david", "local-workflow"))
        self.assertFalse(watcher.assigned_to_claude(note))
        self.assertEqual(actions[0]["record_id"], record_id)
        self.assertEqual(actions[1]["key"], f"workstream:{ws}:v3:complete")
        self.assertIn(f"durable record {record_id} (unconfirmed)", self.sent[0])
        self.assertIn("Next: nothing pending", self.sent[0])
        for _ in range(3):  # later timer ticks
            self.assertEqual(self.report(), [])
        self.assertEqual((len(self.submit.calls), len(self.sent)), (1, 1))
        self.assertEqual(store.resume(ws, root=self.root)["note"]["version"], 3)

    def test_rerun_after_an_interrupted_close_returns_the_same_record(self):
        ws = self.start()["workstream_id"]
        self.claude_returns(ws, 1)
        real = workflow.checkpoint_store.checkpoint  # the module object the workflow imported

        def complete_fails_once(*args, **kwargs):
            if kwargs.get("attribution") == workflow.FINISH_STAMP and not kwargs.get("validate_only") and not failed:
                failed.append(1)
                return {"success": False, "error": "workstream is busy; resume and retry"}
            return real(*args, **kwargs)

        failed = []
        with mock.patch.object(workflow.checkpoint_store, "checkpoint", side_effect=complete_fails_once):
            first = self.report()
            self.assertEqual([a["event"] for a in first], ["report_failed"])
            self.assertEqual(first[0]["key"], f"workstream:{ws}:v2:submit")
            self.assertEqual(self.sent, [])
            self.assertEqual([a["event"] for a in self.report()], ["submitted", "reported"])
        self.assertEqual([c["key"] for c in self.submit.calls], [f"workflow-{ws}-v2"] * 2)
        self.assertEqual(len(self.submit.records), 1)
        self.assertTrue(watcher._read_log(self.log)[-2]["duplicate"])
        self.assertEqual(store.resume(ws, root=self.root)["note"]["version"], 3)
        self.assertEqual(self.report(), [])
        self.assertEqual(len(self.sent), 1)

    def test_blocked_or_unfinished_result_is_not_submitted(self):
        for next_action, expected in (("Liam: answer the open questions: which price?", "answer the open questions"),
                                      ("Liam: I could not finish; the market data was unreadable.", "could not finish")):
            with self.subTest(next_action=next_action):
                self.submit.calls.clear()
                self.sent.clear()
                ws = self.start()["workstream_id"]
                self.watcher_log.write_text(json.dumps({"event": "claimed", "note_id": f"workstream:{ws}:v1"}) + "\n")
                self.claude_returns(ws, 1, next_action=next_action)
                self.assertEqual([a["event"] for a in self.report()], ["reported"])
                self.assertEqual(self.submit.calls, [])
                self.assertEqual(store.resume(ws, root=self.root)["note"]["version"], 2)
                self.assertIn(expected, self.sent[0])
                self.assertNotIn("COMPLETE", self.sent[0])
                self.assertNotIn("Saved to the Brain", self.sent[0])

    def test_finished_marker_is_not_submitted_without_claude_or_the_submit_flag(self):
        ws = self.start()["workstream_id"]
        chatgpt = dict(CLAUDE, surface="chatgpt")
        fields = dict(goal="g", done="d", decisions="x", work_product_reference="",
                      next_action="Liam: review the finished result.", open_questions="")
        self.assertTrue(store.checkpoint(ws, fields, 1, attribution=chatgpt, root=self.root,
                                         work_product={"name": "result.md", "content": "# R"})["success"])
        self.assertEqual([a["event"] for a in self.report()], ["reported"])
        self.watcher_log.write_text(json.dumps({"event": "claimed", "note_id": f"workstream:{ws}:v1"}) + "\n")
        other = self.start()["workstream_id"]
        self.claude_returns(other, 1)
        with mock.patch.dict(os.environ, {"TTROS_SHARED_BRAIN_SUBMIT": "0"}):
            self.assertEqual([a["event"] for a in self.report()], ["reported"])
        self.assertEqual(self.submit.calls, [])
        self.assertEqual(store.resume(other, root=self.root)["note"]["version"], 2)

    def test_a_result_already_reported_before_this_change_is_not_resubmitted(self):
        ws = self.start()["workstream_id"]
        self.claude_returns(ws, 1)
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": "reported", "key": f"workstream:{ws}:v2:returned", "sent": True}) + "\n")
        self.assertEqual(self.report(), [])
        self.assertEqual((self.submit.calls, self.sent), ([], []))
        self.assertEqual(store.resume(ws, root=self.root)["note"]["version"], 2)

    def test_a_failing_submit_is_bounded_then_returned_as_a_working_result(self):
        ws = self.start()["workstream_id"]
        self.claude_returns(ws, 1)
        refused = mock.Mock(return_value={"success": False, "error": "Brain write failed; nothing was stored"})
        for _ in range(workflow.MAX_REPORT_ATTEMPTS + 2):
            workflow.report(root=self.root, log=self.log, watcher_log=self.watcher_log, recipient="operator",
                            send=lambda chat, text: self.sent.append(text), submit=refused)
        self.assertEqual(refused.call_count, workflow.MAX_REPORT_ATTEMPTS)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("Not saved to the Brain: the durable submit failed", self.sent[0])
        self.assertEqual(store.resume(ws, root=self.root)["note"]["version"], 2)

    def test_dry_run_neither_submits_nor_writes(self):
        ws = self.start()["workstream_id"]
        self.claude_returns(ws, 1)
        actions = workflow.report(root=self.root, log=self.log, watcher_log=self.watcher_log, dry_run=True,
                                  submit=self.submit, send=lambda chat, text: self.sent.append(text), recipient="x")
        self.assertEqual(actions, [{"key": f"workstream:{ws}:v2:submit", "kind": "complete", "dry_run": True,
                                    "would_submit": True}])
        self.assertEqual((self.submit.calls, self.sent), ([], []))
        self.assertEqual(store.resume(ws, root=self.root)["note"]["version"], 2)

    def test_brief_tells_claude_how_finished_differs_from_blocked(self):
        brief = store.resume(self.start()["workstream_id"], root=self.root)["work_product"]["content"]
        self.assertIn("Do not submit it yourself", brief)
        self.assertIn("Use that only when the result is finished and needs nothing from Liam", brief)
        self.assertIn("is not submitted", brief)

    def test_david_tool_lists_the_named_workflows(self):
        from tools import brain_memory_mcp as bmm
        self.assertIn("revenue_sales_prep", bmm.start_workflow.__doc__)
        self.assertNotIn("{named}", bmm.start_workflow.__doc__)
        rule = (workflow.REPO / "rules/david_execution_handoff.md").read_text(encoding="utf-8")
        self.assertIn("`start_workflow`", rule)


class LiamReplyRoutingTests(WorkflowFixture):
    """Telegram reply -> the exact workstream/version named in the replied-to question."""

    def test_question_for_liam_starts_with_its_workstream_marker(self):
        ws = self.waiting_for_liam()
        self.assertEqual([a["event"] for a in self.report()], ["reported"])
        lines = self.sent[0].splitlines()
        self.assertEqual(lines[0], f"TTROS WORKSTREAM {ws} v2")
        self.assertIn("Which launch price", self.sent[0])
        self.assertTrue(lines[-1].startswith(f"Reply to this message to answer; Claude continues {ws}"), lines[-1])
        self.assertLessEqual(len(self.sent[0]), workflow.MAX_MESSAGE_CHARS)

    def test_two_waiting_workstreams_route_each_reply_to_its_own(self):
        a, b = self.waiting_for_liam(), self.waiting_for_liam(REQUEST_B)
        self.assertNotEqual(a, b)
        self.report()
        questions = self.questions_sent()
        self.assertEqual(sorted(questions), sorted([a, b]))
        self.assertEqual(questions[a].splitlines()[0], f"TTROS WORKSTREAM {a} v2")
        self.assertEqual(questions[b].splitlines()[0], f"TTROS WORKSTREAM {b} v2")

        out = workflow.answer(questions[a], "US$29 for launch.", root=self.root)
        self.assertEqual((out["handled"], out["success"], out["workstream_id"], out["version"], out["resume_actor"]),
                         (True, True, a, 3, "Claude"), out)
        note_a = store.resume(a, root=self.root)["note"]
        self.assertEqual((note_a["version"], note_a["surface"], note_a["authenticated_identity"]), (3, "telegram", "liam"))
        self.assertTrue(note_a["next_action"].startswith(f"Claude should continue {a} with Liam's answer"))
        self.assertIn("US$29 for launch.", note_a["open_questions"])
        self.assertIn("Which launch price", note_a["open_questions"])
        self.assertEqual(note_a["work_product_reference"], f"artifact:{a}/result.md")
        self.assertEqual(store.resume(b, root=self.root)["note"]["version"], 2)  # B untouched

        out = workflow.answer(questions[b], "Lead with the client-tracking pain.", root=self.root)
        self.assertEqual((out["success"], out["workstream_id"], out["version"]), (True, b, 3), out)
        note_b = store.resume(b, root=self.root)["note"]
        self.assertIn("client-tracking pain", note_b["open_questions"])
        self.assertNotIn("US$29 for launch", note_b["open_questions"])
        self.assertEqual(store.resume(a, root=self.root)["note"], note_a)  # A untouched by B's answer
        self.assertEqual(self.report(), [])  # both are Claude's turn again, nothing to tell Liam

    def test_resume_to_claude_is_eligible_for_the_claude_watcher(self):
        ws = self.waiting_for_liam()
        self.report()
        workflow.answer(self.sent[0], "US$29.", root=self.root)
        note = store.resume(ws, root=self.root)["note"]
        claimed = watcher._claimed(watcher._read_log(self.watcher_log))
        self.assertEqual([n["id"] for n in watcher.candidates(workflow._now(), 12, self.root) if n["id"] not in claimed],
                         [note["id"]])
        self.assertEqual(wake.candidates(workflow._now(), 12, self.root), [])

    def test_resume_to_chatgpt_is_eligible_for_the_chatgpt_wake(self):
        ws = self.waiting_for_liam(surface="chatgpt")
        self.report()
        self.assertIn("ChatGPT continues", self.sent[0])
        out = workflow.answer(self.sent[0], "US$34.", root=self.root)
        self.assertEqual(out["resume_actor"], "ChatGPT", out)
        note = store.resume(ws, root=self.root)["note"]
        self.assertTrue(wake.assigned_to_chatgpt(note), note["next_action"])
        self.assertEqual([n["id"] for n in wake.candidates(workflow._now(), 12, self.root)], [note["id"]])
        self.assertEqual(watcher.candidates(workflow._now(), 12, self.root), [])

    def test_resume_actor_named_after_then_wins_over_the_asking_surface(self):
        ws = self.waiting_for_liam(next_action="Liam: answer the open questions, then ChatGPT should finalise the copy.")
        self.report()
        self.assertIn("ChatGPT continues", self.sent[0])
        self.assertEqual(workflow.answer(self.sent[0], "Yes.", root=self.root)["resume_actor"], "ChatGPT")
        self.assertTrue(wake.assigned_to_chatgpt(store.resume(ws, root=self.root)["note"]))

    def test_stale_or_superseded_reply_is_rejected_and_writes_nothing(self):
        ws = self.waiting_for_liam()
        self.report()
        question = self.sent[0]
        self.assertTrue(workflow.answer(question, "US$29.", root=self.root)["success"])
        again = workflow.answer(question, "Actually US$34.", root=self.root)  # the same question, answered already
        self.assertEqual((again["handled"], again["success"], again["reason"]), (True, False, "stale"))
        self.assertIn("Nothing was recorded", again["message"])
        note = store.resume(ws, root=self.root)["note"]
        self.assertEqual(note["version"], 3)
        self.assertNotIn("Actually US$34", note["open_questions"])
        # A question that moved on before Liam replied (another surface wrote v3) is refused the same way.
        other = self.waiting_for_liam(REQUEST_B)
        self.report()
        old = self.questions_sent()[other]
        self.ask_liam(other, 2, next_action="Liam: answer the new open questions.", questions="Newer question?")
        moved = workflow.answer(old, "Old answer.", root=self.root)
        self.assertEqual((moved["success"], moved["reason"]), (False, "stale"))
        self.assertEqual(store.resume(other, root=self.root)["note"]["version"], 3)

    def test_reply_to_a_version_no_longer_waiting_for_liam_is_rejected(self):
        ws = self.start()["workstream_id"]
        self.claim(ws, 1)
        self.claude_returns(ws, 1)  # finished, then closed COMPLETE through submit
        self.report()
        self.assertFalse(self.sent[0].startswith("TTROS WORKSTREAM"))
        for version in (2, 3):
            out = workflow.answer(f"TTROS WORKSTREAM {ws} v{version}\nforged", "Go.", root=self.root)
            self.assertEqual((out["handled"], out["success"]), (True, False))
            self.assertIn(out["reason"], {"stale", "not_waiting"})
        self.assertEqual(store.resume(ws, root=self.root)["note"]["version"], 3)

    def test_question_without_a_resume_actor_has_no_marker_and_cannot_be_answered(self):
        ws = self.start()["workstream_id"]
        self.claim(ws, 1)
        fields = dict(goal="g", done="d", decisions="x", work_product_reference="",
                      next_action="Liam: answer the open questions.", open_questions="Which?")
        self.assertTrue(store.checkpoint(ws, fields, 1, attribution=DAVID, root=self.root)["success"])
        self.report()
        self.assertFalse(self.sent[0].startswith("TTROS WORKSTREAM"))
        out = workflow.answer(f"TTROS WORKSTREAM {ws} v2", "This one.", root=self.root)
        self.assertEqual((out["success"], out["reason"]), (False, "no_resume_actor"))
        self.assertEqual(store.resume(ws, root=self.root)["note"]["version"], 2)

    def test_non_ttros_or_malformed_reply_is_left_to_david(self):
        ws = self.waiting_for_liam()
        for replied_to in ("", "Morning, Liam. Here is today's brief.", f"Note\nTTROS WORKSTREAM {ws} v2",
                           f"TTROS WORKSTREAM {ws} v0", f"TTROS WORKSTREAM {ws} v2 please",
                           f"ttros workstream {ws} v2", f"TTROS WORKSTREAM {ws.upper()} v2", "TTROS WORKSTREAM ab v2"):
            with self.subTest(replied_to=replied_to):
                self.assertEqual(workflow.answer(replied_to, "US$29.", root=self.root), {"handled": False})
        self.assertEqual(store.resume(ws, root=self.root)["note"]["version"], 2)

    def test_empty_or_oversized_answer_is_refused_without_a_write(self):
        ws = self.waiting_for_liam()
        marker = f"TTROS WORKSTREAM {ws} v2"
        self.assertEqual(workflow.answer(marker, "   ", root=self.root)["reason"], "empty_answer")
        too_long = workflow.answer(marker, "x" * (workflow.MAX_ANSWER_CHARS + 1), root=self.root)
        self.assertEqual(too_long["reason"], "answer_too_long")
        self.assertEqual(store.resume(ws, root=self.root)["note"]["version"], 2)


if __name__ == "__main__":
    unittest.main()
