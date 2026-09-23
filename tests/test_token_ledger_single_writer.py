"""One invocation, one authoritative row, one ledger, one lock.

These regressions pin the property the token accounting depends on: every
production execution route records exactly one row for one model invocation, in
``queue/token_ledger.jsonl``, behind ``queue/token_ledger.jsonl.lock``, and the
500,000-token fuse sees every invocation attributable to a named work item.

Revisit: on a new execution route or a change to the canonical ledger contract.
· Last touched: 2026-09-22.
"""

from __future__ import annotations

import importlib.util
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import step6_cost_control as step6  # noqa: E402
import aos_orchestration  # noqa: E402
from tools import source_intake_semantic  # noqa: E402

LEDGER = Path("queue/token_ledger.jsonl")


def _make_root(tmp: str) -> Path:
    root = Path(tmp) / "agentic-os-live"
    (root / "queue").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "queue" / "notifications.json", root / "queue" / "notifications.json")
    shutil.copy(ROOT / "scripts" / "model_prices.json", root / "scripts" / "model_prices.json")
    (root / LEDGER).write_text("", encoding="utf-8")
    return root


def _rows(root: Path) -> list[dict]:
    text = (root / LEDGER).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class _StubContext:
    """Stand in for the frozen AssembledContext the launcher boundary requires."""

    request = "do the work"
    session_id = "dashboard-session"
    surface = "queue:claude"


def _usage(model: str = "gpt-5-codex") -> dict:
    return {"input_tokens": 1000, "cached_input_tokens": 0, "output_tokens": 200, "provider": "openai-codex"}


class CanonicalLedgerLockTests(unittest.TestCase):
    """The canonical ledger has exactly one write boundary and loses no writer."""

    def test_a_concurrent_bookkeeping_append_inside_step6_write_window_is_not_lost(self):
        # The failure mode is a lost writer, not a corrupt file: a
        # read-modify-replace writer holding a *different* lock rewrites the
        # whole ledger from a snapshot taken before Step 6's append landed.
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            for index in range(3):
                step6.record_invocation(
                    step6.Scope("work_item", "AOS-2026-0900"),
                    invocation_id=f"seed-{index}",
                    provider="openai-codex",
                    model="gpt-5-codex",
                    usage=_usage(),
                    root=root,
                )
            seeded = len(_rows(root))
            self.assertEqual(seeded, 3)

            competitor = Path(tmp) / "competitor.py"
            read_signal = Path(tmp) / "competitor_read.flag"
            # The competitor is the shipped orchestration bookkeeping writer.
            # Whichever mechanism it uses is the mechanism under test: a
            # read-modify-replace commit signals once it has read and is holding
            # a pre-append snapshot, which is precisely the window in which
            # Step 6's append is discarded.
            competitor.write_text(textwrap.dedent(f"""
                import sys, time
                sys.path.insert(0, {str(TOOLS)!r})
                from pathlib import Path
                import aos_orchestration, aos_queue_storage
                root = Path({str(root)!r})
                replace_text = aos_queue_storage.durable_replace_text

                def signal_then_replace(path, text):
                    if Path(path).name != "token_ledger.jsonl":
                        return replace_text(path, text)
                    Path({str(read_signal)!r}).write_text("snapshot taken", encoding="utf-8")
                    time.sleep(1.5)
                    return replace_text(path, text)

                aos_orchestration.durable_replace_text = signal_then_replace
                aos_queue_storage.durable_replace_text = signal_then_replace
                aos_orchestration.assert_authoritative_root = lambda value: Path(value)
                aos_queue_storage.assert_authoritative_root = lambda value: Path(value)
                aos_orchestration.append_no_agent_token_line(
                    root,
                    {{"id": "AOS-2026-0900", "owner": "operations"}},
                    "queue_transition",
                    effect_id="concurrent-bookkeeping",
                )
            """).strip() + "\n", encoding="utf-8")

            launched: list[subprocess.Popen] = []
            original_rows = step6._ledger_rows

            def read_then_race(*args, **kwargs):
                rows = original_rows(*args, **kwargs)
                if not launched:
                    # Step 6 has read and is about to recompute and append.
                    launched.append(subprocess.Popen([sys.executable, str(competitor)]))
                    deadline = time.monotonic() + 4.0
                    # Under one shared lock the competitor cannot reach its
                    # snapshot at all, so this simply times out and Step 6
                    # finishes first; under two locks it signals immediately.
                    while time.monotonic() < deadline and not read_signal.exists():
                        time.sleep(0.02)
                return rows

            with patch.object(step6, "_ledger_rows", read_then_race):
                step6.record_invocation(
                    step6.Scope("work_item", "AOS-2026-0900"),
                    invocation_id="raced-invocation",
                    provider="openai-codex",
                    model="gpt-5-codex",
                    usage=_usage(),
                    root=root,
                )
            self.assertTrue(launched, "the competing writer never started")
            self.assertEqual(launched[0].wait(timeout=60), 0)

            rows = _rows(root)
            # No writer is lost: three seeds, the raced invocation, and the
            # concurrent bookkeeping row are all durable.
            self.assertIn(
                "raced-invocation",
                [row.get("invocation_id") for row in rows],
                "Step 6's append was discarded by the concurrent bookkeeping writer",
            )
            self.assertIn(
                "concurrent-bookkeeping:tokens",
                [row.get("effect_id") for row in rows],
            )
            self.assertEqual(len(rows), seeded + 2)
            self.assertFalse(
                read_signal.exists(),
                "the bookkeeping writer reached a pre-append snapshot while Step 6 held the "
                "ledger lock; it is not on the canonical write boundary",
            )

            # The resulting rows are complete, so the fuse recomputed from the
            # ledger equals the correct canonical aggregate.
            status = step6.fuse_status(step6.Scope("work_item", "AOS-2026-0900"), root=root)
            self.assertFalse(status["accounting_unknown"])
            self.assertEqual(status["invocation_count"], 4)
            self.assertEqual(status["canonical_tokens"], 4 * 1200)

    def test_bookkeeping_writer_takes_the_canonical_ledger_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            with patch.object(aos_orchestration, "assert_authoritative_root", lambda value: Path(value)), \
                 patch.object(aos_orchestration, "append_canonical_row") as append:
                aos_orchestration.append_no_agent_token_line(
                    root, {"id": "AOS-2026-0901", "owner": "operations"}, "queue_transition", effect_id="e1",
                )
            append.assert_called_once()
            self.assertEqual(append.call_args.kwargs["effect_id"], "e1:tokens")

    def test_queue_storage_docstring_no_longer_claims_a_package_operation_lock(self):
        text = (ROOT / "tools" / "aos_queue_storage.py").read_text(encoding="utf-8")
        header = text.split('"""')[1]
        self.assertNotIn("Lock order is package-operation lock first", header)
        self.assertIn("token_ledger.jsonl.lock", header)


class OneRowPerInvocationTests(unittest.TestCase):
    """Step 6 is authoritative; a second parse of the same call defers to it."""

    def test_second_parse_of_a_step6_recorded_invocation_is_deferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            step6.record_invocation(
                step6.Scope("work_item", "AOS-2026-0902"),
                invocation_id="codex-abc",
                provider="openai-codex",
                model="gpt-5-codex",
                usage=_usage(),
                root=root,
            )
            recorded, authoritative = step6.append_canonical_row(
                root,
                {"item_id": "AOS-2026-0902", "task_id": "second parse", "tokens": 1200},
                effect_id="backend_token_usage:codex-abc",
                defer_to_invocation_id="codex-abc",
            )
            self.assertFalse(recorded)
            self.assertEqual(authoritative["event"], "model_invocation")
            rows = _rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                step6.fuse_status(step6.Scope("work_item", "AOS-2026-0902"), root=root)["canonical_tokens"],
                1200,
            )

    def test_an_invocation_step6_never_saw_is_still_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            recorded, row = step6.append_canonical_row(
                root,
                {"item_id": "AOS-2026-0903", "task_id": "uncovered route", "tokens": 42},
                effect_id="backend_token_usage:orphan-1",
                defer_to_invocation_id="orphan-1",
            )
            self.assertTrue(recorded)
            self.assertEqual(row["effect_id"], "backend_token_usage:orphan-1")
            self.assertEqual(len(_rows(root)), 1)

    def test_the_same_effect_is_never_recorded_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            first, _ = step6.append_canonical_row(root, {"item_id": "AOS-2026-0904"}, effect_id="once")
            second, _ = step6.append_canonical_row(root, {"item_id": "AOS-2026-0904"}, effect_id="once")
            self.assertTrue(first)
            self.assertFalse(second)
            self.assertEqual(len(_rows(root)), 1)

    def test_memory_intake_sidecar_records_once_and_replay_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            usage_file = root / "queue" / "context_assemblies" / "semantic.usage.json"
            usage_file.parent.mkdir(parents=True)
            usage_file.write_text(json.dumps({
                "provider": "openai-codex",
                "model": "gpt-5.5",
                "input_tokens": 15_868,
                "output_tokens": 2_098,
                "cache_read_tokens": 0,
                "reasoning_tokens": 187,
                "total_tokens": 17_966,
                "session_id": "20260922_173614_02857d",
            }), encoding="utf-8")

            first = source_intake_semantic._record_semantic_usage(
                usage_file,
                source_id="fixture-source",
                fallback_invocation_id="fallback-unused",
                model="gpt-5.5",
                root=root,
            )
            replay = source_intake_semantic._record_semantic_usage(
                usage_file,
                source_id="fixture-source",
                fallback_invocation_id="fallback-unused",
                model="gpt-5.5",
                root=root,
            )

            self.assertTrue(first["recorded"])
            self.assertTrue(replay["idempotent"])
            rows = _rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["invocation_id"], "20260922_173614_02857d")
            self.assertEqual(rows[0]["input_plus_output"], 17_966)
            self.assertEqual(rows[0]["surface"], "memory-intake:semantic")


class BackendLedgerRoutingTests(unittest.TestCase):
    """The backend writes and reads exactly one ledger."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "agentic_os_backend_ledger", ROOT / "dashboard" / "backend" / "test_composio_hermes.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.backend = module.backend

    def test_backend_token_rows_land_on_the_canonical_ledger_not_the_repo_root_one(self):
        backend = self.backend
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            legacy = root / "token_ledger.jsonl"
            legacy.write_text("", encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "TOKEN_LEDGER_FILE", root / LEDGER), \
                 patch.object(backend, "ROOT_TOKEN_LEDGER_FILE", legacy):
                backend._append_simple_token_ledger(
                    "AOS-2026-0905", "codex", {"available": True, "input_tokens": "7", "output_tokens": "5"},
                )
            self.assertEqual(legacy.read_text(encoding="utf-8"), "")
            rows = _rows(root)
            self.assertEqual([row["task_id"] for row in rows], ["AOS-2026-0905"])
            self.assertEqual(rows[0]["tokens"], 12)

    def test_backend_defers_to_the_step6_row_for_the_same_invocation(self):
        backend = self.backend
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            legacy = root / "token_ledger.jsonl"
            legacy.write_text("", encoding="utf-8")
            step6.record_invocation(
                step6.Scope("work_item", "AOS-2026-0906"),
                invocation_id="codex-xyz",
                provider="openai-codex",
                model="gpt-5-codex",
                usage=_usage(),
                root=root,
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "TOKEN_LEDGER_FILE", root / LEDGER), \
                 patch.object(backend, "ROOT_TOKEN_LEDGER_FILE", legacy):
                backend._append_simple_token_ledger(
                    "AOS-2026-0906",
                    "codex",
                    {"available": True, "input_tokens": 1000, "output_tokens": 200, "invocation_id": "codex-xyz"},
                    {"item_id": "AOS-2026-0906"},
                )
            rows = _rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["event"], "model_invocation")
            # The second parse is dropped, not relocated to the legacy ledger.
            self.assertEqual(legacy.read_text(encoding="utf-8"), "")
            self.assertEqual(
                step6.fuse_status(step6.Scope("work_item", "AOS-2026-0906"), root=root)["invocation_count"], 1,
            )

    def test_operational_totals_no_longer_merge_the_legacy_root_ledger(self):
        backend = self.backend
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            legacy = root / "token_ledger.jsonl"
            legacy.write_text(
                json.dumps({"ts": "2026-08-08T00:00:00Z", "task_id": "legacy-only", "tokens": 999, "basis": "exact"})
                + "\n",
                encoding="utf-8",
            )
            (root / LEDGER).write_text(
                json.dumps({"ts": "2026-08-08T00:00:00Z", "task_id": "canonical-only", "tokens": 5, "basis": "exact"})
                + "\n",
                encoding="utf-8",
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "TOKEN_LEDGER_FILE", root / LEDGER), \
                 patch.object(backend, "ROOT_TOKEN_LEDGER_FILE", legacy):
                records = backend._read_token_ledger_records()
            self.assertEqual([row["task_id"] for row in records], ["canonical-only"])
            # The legacy file is preserved, not migrated or truncated.
            self.assertIn("legacy-only", legacy.read_text(encoding="utf-8"))

    def test_canonical_memory_intake_row_reaches_both_dashboard_apis(self):
        backend = self.backend
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            step6.record_invocation(
                step6.Scope("session", "source-intake-semantic-fixture"),
                invocation_id="semantic-fixture-session",
                provider="openai-codex",
                model="gpt-5.5",
                usage={"input_tokens": 20, "output_tokens": 5, "cache_read_tokens": 0},
                root=root,
                surface="memory-intake:semantic",
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "TOKEN_LEDGER_FILE", root / LEDGER), \
                 patch.object(backend, "_read_claude_local_usage", return_value={"available": False}):
                token_api = backend.dashboard_tokens()
                overview_api = backend.get_overview()

            self.assertEqual(token_api["periods"]["today"]["tokens"], 25)
            self.assertEqual(overview_api["tokenUsage"]["known_tokens_today"], 25)
            self.assertEqual(token_api["strip"]["today"]["label"], "Token usage: 25 exact today")

    def test_dashboard_suppresses_completion_summary_behind_exact_invocation(self):
        backend = self.backend
        invocation = {
            "event": "model_invocation",
            "item_id": "AOS-2026-0909",
            "session_id": "provider-session",
            "invocation_id": "provider-session",
            "timestamp": "2026-09-22T12:00:00Z",
            "exact_usage": {"canonical_total": 25},
            "token_usage": {"totals": {"input": 20, "output": 5}, "unavailable": []},
        }
        completion_summary = {
            "item_id": "AOS-2026-0909",
            "timestamp": "2026-09-22T12:00:01Z",
            "effect_id": "done:fixture:tokens",
            "token_usage": {"totals": {"input": 20, "output": 5}, "unavailable": []},
        }
        effective = backend._effective_token_ledger_records([invocation, completion_summary])
        self.assertEqual(effective, [invocation])


class WorkerFuseScopeTests(unittest.TestCase):
    """Every worker invocation is attributable to its named work item."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "agentic_os_backend_scope", ROOT / "dashboard" / "backend" / "test_composio_hermes.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.backend = module.backend

    def test_claude_worker_invocation_counts_against_its_work_item(self):
        backend = self.backend
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_root(tmp)
            context = _StubContext()
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "require_assembled_context", lambda value: value), \
                 patch.object(backend, "_write_agent_prompt_file", return_value=(Path(tmp) / "p.txt", "/tmp/p.txt")), \
                 patch.object(backend, "_run_wsl_supervised", return_value={
                     "success": True, "output": "PASS", "stdout": "PASS", "stderr": "", "returncode": 0,
                 }), \
                 patch.object(backend, "_extract_token_usage", return_value=(
                     {"available": True, "input_tokens": 1000, "output_tokens": 200, "provider": "anthropic",
                      "model": "claude-opus-5"},
                     "Token usage: input 1000, output 200",
                 )):
                (Path(tmp) / "p.txt").write_text("prompt", encoding="utf-8")
                backend._run_wsl_prompt_command(
                    "true {prompt_file}", context, 30, item_id="AOS-2026-0907",
                )
            rows = [row for row in _rows(root) if row.get("event") == "model_invocation"]
            self.assertEqual([row["scope_key"] for row in rows], ["work_item:AOS-2026-0907"])
            status = step6.fuse_status(step6.Scope("work_item", "AOS-2026-0907"), root=root)
            self.assertEqual(status["canonical_tokens"], 1200)

    def test_claude_worker_call_site_passes_the_item_id(self):
        backend = self.backend
        item = {"id": "AOS-2026-0908", "title": "Claude fuse scope", "owner": "claude"}
        completed = {"success": True, "output": "PASS", "stdout": "PASS", "stderr": "", "returncode": 0}
        with patch.object(backend, "_queue_resolve_route_metadata",
                          return_value=backend._queue_resolve_route_metadata("claude")), \
             patch.object(backend, "_run_wsl_prompt_command", return_value=completed) as run, \
             patch.object(backend, "_local_agent_route_log", return_value="logs/local_agent_route.jsonl"), \
             patch.object(backend, "_log_token_usage"):
            backend._queue_run_worker("claude", "fixture prompt", item)
        self.assertEqual(run.call_args.kwargs["item_id"], "AOS-2026-0908")


if __name__ == "__main__":
    unittest.main()
