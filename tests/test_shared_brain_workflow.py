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


class WorkflowTests(unittest.TestCase):
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

    def claude_returns(self, ws, version, next_action="Liam: review the finished result.", result="# Verdict\nGO"):
        fields = dict(goal="g", done="Validated the idea.", decisions="GO at US$29.", work_product_reference="",
                      next_action=next_action, open_questions="")
        out = store.checkpoint(ws, fields, version, attribution=CLAUDE, root=self.root,
                               work_product={"name": "result.md", "content": result})
        self.assertTrue(out["success"], out)

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

    def test_second_start_waits_for_a_pending_claude_handoff(self):
        first = self.start()
        refused = self.start()
        self.assertFalse(refused["success"])
        self.assertEqual(refused["pending_workstreams"], [first["workstream_id"]])
        self.watcher_log.write_text(json.dumps({"event": "claimed", "note_id": f"workstream:{first['workstream_id']}:v1"}) + "\n")
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


if __name__ == "__main__":
    unittest.main()
