"""AOS-2026-9955/9956: David -> Operating Hermes -> Codex completion defects.

Fixtures only. No Hermes or Codex process is launched: the synthesis call is
a fake and the worker results are the dicts the real route returns.
"""
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

THREAD_ID = "01a176e2-5e3f-77e0-a283-1bf5b52d5e76"
INVOCATION_ID = "codex-b4313080bf1745318f25154746eba91d"


def write_items(root, items):
    path = root / "queue" / "work_items.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in items), encoding="utf-8")


def read_item(root, item_id):
    for line in (root / "queue" / "work_items.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["id"] == item_id:
            return row
    raise KeyError(item_id)


def item(item_id, status, **extra):
    base = {
        "id": item_id, "title": f"Fixture {item_id}", "status": status, "priority": 5,
        "requested_by": "Hermes", "owner_type": "agent", "owner": "codex",
        "source": "dashboard/hermes_message", "tags": [], "context": "", "sources": [],
        "source_refs": [], "allowed_actions": ["local_read", "local_test"],
        "stop_conditions": ["external_send"], "definition_of_done": "done",
        "claim": {"claimed_by": None, "claimed_at": None}, "receipts": [],
        "created_at": "2026-10-26T06:25:05Z", "updated_at": "2026-10-26T06:25:05Z",
    }
    base.update(extra)
    return base


def stream(*items):
    events = [{"type": "thread.started", "thread_id": THREAD_ID}, {"type": "turn.started"}]
    events += [{"type": "item.completed", "item": row} for row in items]
    events.append({"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 10}})
    return "\n".join(json.dumps(event) for event in events) + "\n"


class CodexCompletionDefectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = importlib.import_module("dashboard.backend.main")

    def _codex_result(self, reply, **extra):
        return {
            "success": True, "output": reply, "returncode": 0, "session_id": THREAD_ID,
            "token_usage": {"available": True, "session_id": THREAD_ID, "invocation_id": INVOCATION_ID},
            "token_usage_text": "Token usage: input 100, output 10", "token_usage_logged": True, **extra,
        }

    # Defect 2: a markdown NEEDS ATTENTION verdict was read as PASS.
    def test_markdown_needs_attention_verdict_fails_and_plain_pass_passes(self):
        failed = self.backend._compact_agent_closeout(
            self._codex_result("**NEEDS ATTENTION**\n\n- **Blockers:** the requirement was not met."),
            "codex", "codex", "t",
        )
        self.assertFalse(failed["success"])
        self.assertEqual("agent_reported_task_failure", failed["failure_class"])
        self.assertTrue(failed["output"].startswith("NEEDS ATTENTION"))
        self.assertIn("the requirement was not met", failed["output"])
        passed = self.backend._compact_agent_closeout(
            self._codex_result("**PASS**\n\n- **Summary for operator:** ran it."), "codex", "codex", "t",
        )
        self.assertTrue(passed["success"])
        self.assertEqual(THREAD_ID, passed["session_id"])

    def test_closeout_verdict_reads_only_the_first_line(self):
        verdict = self.backend._closeout_verdict
        self.assertEqual("NEEDS ATTENTION", verdict("NEEDS ATTENTION — the command succeeded, but ..."))
        self.assertEqual("PASS", verdict("\n## PASS\nbody mentions NEEDS ATTENTION"))
        self.assertIsNone(verdict("The command ran. PASS"))
        self.assertIsNone(verdict("PASSING grade"))

    # Defect 1: the receipt must carry the thread.started ID, never an invocation ID.
    def test_receipt_records_thread_id_and_never_substitutes_the_invocation_id(self):
        review = {"token_usage": {}, "token_usage_text": "Token usage: no agent invocation"}
        with_session = self._codex_result("PASS")
        without_session = {**self._codex_result("PASS"), "session_id": None,
                           "token_usage": {"available": False, "invocation_id": INVOCATION_ID}}
        texts = {}
        for name, worker in (("with", with_session), ("without", without_session)):
            attempts = [{"attempt": 1, "worker": "codex", "worker_result": worker,
                         "review_result": review, "review": {"decision": "PASS"}}]
            texts[name] = self.backend._queue_run_receipt_text(
                "PASS", item("AOS-2026-0001", "agent_working"), "codex", attempts,
                {"decision": "PASS"}, "done", "None",
            )
        self.assertIn(f"Codex session ID (thread.started): attempt 1 {THREAD_ID}", texts["with"])
        self.assertIn(f"session={THREAD_ID}; invocation={INVOCATION_ID}", texts["with"])
        self.assertIn("Codex session ID (thread.started): attempt 1 unavailable", texts["without"])
        self.assertNotIn(f"session={INVOCATION_ID}", texts["without"])
        self.assertIn(f"session=unavailable; invocation={INVOCATION_ID}", texts["without"])

    def test_file_change_paths_come_from_the_codex_stream(self):
        out = stream(
            {"id": "i0", "type": "command_execution", "command": "git rev-parse --short HEAD"},
            {"id": "i1", "type": "file_change", "changes": [{"path": "/r/a.md", "kind": "add"}, {"path": "/r/b.py", "kind": "update"}]},
            {"id": "i2", "type": "file_change", "changes": [{"path": "/r/a.md", "kind": "update"}]},
        )
        self.assertEqual(["/r/a.md", "/r/b.py"], self.backend._codex_file_change_paths(out))
        self.assertEqual([], self.backend._codex_file_change_paths(stream()))


class WorkerDispositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = importlib.import_module("dashboard.backend.main")

    def _worker(self, **extra):
        return {"success": True, "output": "PASS\n\nSummary for operator: ok", "session_id": THREAD_ID,
                "review_output": "PASS\n\n- Summary for operator: `def7c4d`", "file_changes": [], **extra}

    def _apply(self, root, row, worker, current=None):
        write_items(root, [current or row])
        with patch.object(self.backend, "BASE_DIR", root):
            return self.backend._queue_apply_worker_disposition(row, "codex", worker)

    # Defect 3: read-only steps get their bookkeeping from the runner, never a source edit.
    def test_read_only_step_gets_a_runner_written_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = item("AOS-2026-0002", "agent_working")
            result = self._apply(root, row, self._worker())
            self.assertTrue(result["success"])
            artifact = root / "workflows" / "queue_artifacts" / "AOS-2026-0002_Fixture_AOS-2026-0002.md"
            text = artifact.read_text(encoding="utf-8")
            self.assertIn(f"Codex session ID (thread.started): {THREAD_ID}", text)
            self.assertIn("`def7c4d`", text)

    def test_read_only_step_that_changes_a_source_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = item("AOS-2026-0003", "agent_working")
            result = self._apply(root, row, self._worker(file_changes=[str(root / "tools" / "x.py")]))
            self.assertFalse(result["success"])
            self.assertEqual("read_only_violation", result["failure_class"])
            self.assertTrue(result["output"].startswith("NEEDS ATTENTION"))

    def test_read_only_step_may_still_write_its_own_closeout_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = item("AOS-2026-0004", "agent_working")
            own = root / "workflows" / "queue_artifacts" / "AOS-2026-0004_Fixture_AOS-2026-0004.md"
            result = self._apply(root, row, self._worker(file_changes=[str(own)]))
            self.assertTrue(result["success"])

    def test_editing_step_is_not_held_to_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = item("AOS-2026-0005", "agent_working", allowed_actions=["local_read", "local_edit", "local_test"])
            result = self._apply(root, row, self._worker(file_changes=[str(root / "tools" / "x.py")]))
            self.assertTrue(result["success"])
            self.assertFalse((root / "workflows" / "queue_artifacts").exists())

    def test_worker_attached_needs_input_receipt_is_not_overridden_to_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = item("AOS-2026-0006", "agent_working", allowed_actions=["local_read", "local_edit"])
            current = {**row, "status": "needs_input", "receipts": [
                {"path": "workflows/queue_artifacts/x.md", "status": "needs_input", "created_at": "2026-10-26T06:25:36Z"},
            ]}
            result = self._apply(root, row, self._worker(), current=current)
            self.assertFalse(result["success"])
            self.assertEqual("agent_reported_status", result["failure_class"])
            self.assertIn("needs_input", result["failure_detail"])


class ExecutiveParentVerdictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = importlib.import_module("dashboard.backend.main")

    def _finalize(self, root, answer):
        child_receipt = "queue/receipts/AOS-2026-0011.md"
        (root / child_receipt).parent.mkdir(parents=True, exist_ok=True)
        (root / child_receipt).write_text(
            f"PASS\n\nWork item ID: AOS-2026-0011\nCodex session ID (thread.started): attempt 1 {THREAD_ID}\n",
            encoding="utf-8",
        )
        parent = item("AOS-2026-0010", "agent_working", owner="hermes", owner_type="workflow",
                      tags=["executive_objective", "parent"],
                      objective={"original_command": "Run the command and report the session.", "version": 1})
        child = item("AOS-2026-0011", "done", parent_id="AOS-2026-0010", step_index=1,
                     tags=["executive_objective_child"], review="model",
                     receipts=[{"path": child_receipt, "status": "done", "created_at": "2026-10-26T06:26:05Z"}])
        write_items(root, [parent, child])
        prompts = []

        def fake_hermes(context, **_kwargs):
            prompts.append(context.request)
            return {"success": True, "reply": answer, "token_usage_text": "Token usage: input 1, output 1"}

        with patch.object(self.backend, "BASE_DIR", root), \
             patch.object(self.backend, "_run_hermes_message", fake_hermes), \
             patch.object(self.backend, "assemble_model_context", lambda prompt, **_k: type("C", (), {"request": prompt})()):
            self.backend._finalize_executive_objective_parent("AOS-2026-0010")
        return read_item(root, "AOS-2026-0010"), prompts[0]

    def test_needs_attention_synthesis_never_closes_the_parent_as_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent, prompt = self._finalize(root, "NEEDS ATTENTION — a requirement was not met.\n\nDetail.")
            self.assertEqual("blocked", parent["status"])
            receipt = (root / "queue/receipts/AOS-2026-0010-executive-objective.md").read_text(encoding="utf-8")
            self.assertTrue(receipt.startswith("NEEDS ATTENTION\n"))
            self.assertNotIn("the objective is complete", receipt)
            self.assertIn(f"Codex session ID (thread.started): attempt 1 {THREAD_ID}", prompt)

    def test_synthesis_without_a_verdict_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent, _ = self._finalize(Path(tmp), "The command ran and everything looks fine.")
            self.assertEqual("blocked", parent["status"])

    def test_pass_synthesis_closes_done_and_carries_the_codex_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent, _ = self._finalize(root, "PASS\n\nThe command ran; exit 0.")
            self.assertEqual("done", parent["status"])
            receipt = (root / "queue/receipts/AOS-2026-0010-executive-objective.md").read_text(encoding="utf-8")
            self.assertTrue(receipt.startswith("PASS\n"))
            self.assertIn(f"- AOS-2026-0011: attempt 1 {THREAD_ID}", receipt)
            outcome = (root / "workflows/queue_artifacts/AOS-2026-0010_executive_outcome.md").read_text(encoding="utf-8")
            self.assertIn(f"- AOS-2026-0011: attempt 1 {THREAD_ID}", outcome)
            self.assertIn("Verdict: PASS", outcome)


class PlannerStepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = importlib.import_module("dashboard.backend.main")

    def test_planner_is_told_not_to_use_tools_and_how_to_mark_read_only(self):
        with patch.object(self.backend, "_latest_executive_outcome", lambda _c: None), \
             patch.object(self.backend, "_workflow_capability_catalog", lambda: []):
            prompt = self.backend._hermes_decomposition_prompt("Run git rev-parse --short HEAD")
        self.assertIn("do not call tools, read files or search", prompt)
        self.assertIn('"allowed_actions":["local_read","local_edit","local_test"]', prompt)
        self.assertNotIn("per rules/prompt_writing.md", prompt)

    def test_planner_may_narrow_a_step_to_read_only_but_never_widen_it(self):
        def steps(*actions):
            reply = "```json\n" + json.dumps({"title": "t", "steps": [
                {"title": f"s{i}", "owner": "codex", "context": "c", "definition_of_done": "d", "allowed_actions": a}
                for i, a in enumerate(actions)
            ]}) + "\n```"
            return [s["allowed_actions"] for s in self.backend._normalize_chain_proposal(reply, "x")["steps"]]
        default = ["local_read", "local_edit", "local_test"]
        self.assertEqual(
            [["local_read", "local_test"], ["local_read", "local_edit"], default, default],
            steps(["local_read", "local_test"], ["local_read", "local_edit", "external_send"], ["external_send"], "x"),
        )


if __name__ == "__main__":
    unittest.main()
