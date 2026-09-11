"""Executable proofs for the David-only B7 answer-key leak closure
(hooks/b7_test_material_guard.py).

Covers the exact leak mechanisms documented in
scripts/b7_contamination_map_and_clean_subset.md: direct reads of the
capability-harness question doc and frozen scorer source, prior pass output
records, the preimage backup, and the session_search cross-session leak --
while proving the four scoped Business Brain depth tools (search_calls,
open_call, open_note, search_history) and ordinary non-test-material file
access remain completely unaffected.

Zero model calls -- every case below is a synthetic pre_tool_call payload,
never a live Hermes invocation.

Run-scoping (2026-09-08, zero-model cleanup pass): the guard is now inactive
unless ``TTROS_BRAIN_ROOT`` is present in the process environment -- the same
signal the three B7 harness scripts already set before every David
subprocess call. Every "should block" case below therefore runs inside
``_b7_env()``, which sets that variable for the duration of the call; the new
``NormalDavidIsUnaffectedTests`` class proves the identical blocked-by-B7
inputs pass through untouched with no B7 env present.

Revisit: if a new leak-capable tool is confirmed, or a legitimate David use
for one of the blocked tools is identified. · Added 2026-09-07. Run-scoping
added 2026-09-08.
"""

from __future__ import annotations

import contextlib
import os
import unittest

from hooks.b7_test_material_guard import evaluate


@contextlib.contextmanager
def _b7_env():
    """Set the B7-run signal (TTROS_BRAIN_ROOT) for the duration of a call.

    Mirrors exactly what scripts/step3_b7_harness.py, step5_b7_growth_harness.py
    and step6_b7_tools_harness.py do to their own subprocess env before
    invoking David.
    """
    previous = os.environ.get("TTROS_BRAIN_ROOT")
    os.environ["TTROS_BRAIN_ROOT"] = "/tmp/b7-test-work-vault"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TTROS_BRAIN_ROOT", None)
        else:
            os.environ["TTROS_BRAIN_ROOT"] = previous


class B7LeakClosureTests(unittest.TestCase):
    """All cases here run with the B7 env signal present (guard active)."""

    def test_harness_question_doc_read_is_blocked(self):
        with _b7_env():
            result = evaluate({
                "tool_name": "open_file",
                "tool_input": {"path": "docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md"},
            })
        self.assertEqual("block", result["action"])

    def test_scorer_source_read_is_blocked(self):
        with _b7_env():
            result = evaluate({"tool_name": "open_file", "tool_input": {"path": "scripts/step3_b7_harness.py"}})
        self.assertEqual("block", result["action"])

    def test_prior_pass_output_and_reports_are_blocked(self):
        for path in (
            "scripts/step3_b7_pass_A.scored.json",
            "scripts/step6_b7_pass.raw.json",
            "scripts/step3_b7_report.md",
            "scripts/step6_prediction.md",  # no "b6"/"b7" in the filename, still instrument-only
            "scripts/step5_apply_gate.md",
        ):
            with self.subTest(path=path):
                with _b7_env():
                    result = evaluate({"tool_name": "open_file", "tool_input": {"path": path}})
                self.assertEqual("block", result["action"])

    def test_preimage_backup_read_is_blocked(self):
        with _b7_env():
            result = evaluate({
                "tool_name": "open_file",
                "tool_input": {"path": "/home/liam/ttros_backups/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_PREIMAGE_2026-09-05.md"},
            })
        self.assertEqual("block", result["action"])

    def test_other_canonical_docs_ttros_files_are_also_blocked(self):
        # docs/ttros/ is blocked in full (not just the harness-questions file):
        # David has no legitimate business reason to read TTROS's own internal
        # design/status docs either.
        with _b7_env():
            result = evaluate({
                "tool_name": "open_file",
                "tool_input": {"path": "docs/ttros/00_TTROS_CURRENT_STATE_v2026-09-04_rev6.md"},
            })
        self.assertEqual("block", result["action"])

    def test_search_files_read_file_execute_code_are_blocked_outright(self):
        # Blocked by tool name, not just by path: this is what closes the
        # confirmed content-search leak (a path-free query whose *result*
        # incidentally surfaces the harness doc's own prose), which a
        # path-pattern check alone cannot see at pre_tool_call time.
        for tool_name, tool_input in (
            ("search_files", {"pattern": "ICP-A|System Buyers|GTM Engineering", "target": "content"}),
            ("read_file", {"path": "memory/offers.md"}),
            ("execute_code", {"code": "print('hello')"}),
        ):
            with self.subTest(tool_name=tool_name):
                with _b7_env():
                    result = evaluate({"tool_name": tool_name, "tool_input": tool_input})
                self.assertEqual("block", result["action"])

    def test_tool_name_block_is_case_insensitive(self):
        with _b7_env():
            result = evaluate({"tool_name": "Search_Files", "tool_input": {"pattern": "anything"}})
        self.assertEqual("block", result["action"])

    def test_session_search_is_blocked(self):
        with _b7_env():
            result = evaluate({"tool_name": "session_search", "tool_input": {"query": "CCI OR TRACC"}})
        self.assertEqual("block", result["action"])

    def test_legitimate_business_brain_depth_tools_remain_available(self):
        # Preserved even DURING an active B7 run, not just when the guard is
        # inactive -- this is the "legitimate depth tools survive B7" proof.
        for tool_name, tool_input in (
            ("mcp__brain__open_note", {"pointer": "memory/offers.md"}),
            ("mcp__brain__open_call", {"call_id": "mike-knapp-july-21"}),
            ("mcp__brain__search_calls", {"query": "Mike Knapp"}),
            ("mcp__brain__search_history", {"query": "positioning"}),
            ("mcp__brain__remember_brain_knowledge", {"pointer": "memory/offers.md", "statement": "x"}),
            ("mcp__brain__brain_memory_status", {}),
        ):
            with self.subTest(tool_name=tool_name):
                with _b7_env():
                    result = evaluate({"tool_name": tool_name, "tool_input": tool_input})
                self.assertEqual({}, result)

    def test_legitimate_queue_tool_and_non_blocked_tool_names_remain_available(self):
        # read_file/search_files/execute_code are blocked by NAME, unconditionally
        # (see test_search_files_read_file_execute_code_are_blocked_outright) --
        # that is the point, not a gap. This proves the block is scoped to those
        # specific tool names and BLOCKED_TOOL_NAMES-listed tools, not a blanket
        # deny on every tool call or every ordinary path.
        with _b7_env():
            self.assertEqual({}, evaluate({"tool_name": "mcp__queue__list_items", "tool_input": {}}))
            self.assertEqual({}, evaluate({
                "tool_name": "some_other_tool",
                "tool_input": {"path": "operating_context/current_priorities.md"},
            }))

    def test_empty_or_malformed_payload_does_not_crash(self):
        with _b7_env():
            self.assertEqual({}, evaluate({}))
            self.assertEqual({}, evaluate({"tool_name": None, "tool_input": None}))


class NormalDavidIsUnaffectedTests(unittest.TestCase):
    """No TTROS_BRAIN_ROOT in the environment => guard is a pass-through.

    Every input here is one that B7LeakClosureTests proves gets blocked when
    the B7 env signal is present. Run without that signal, normal David must
    retain full native tool capability.
    """

    def setUp(self):
        self._previous = os.environ.pop("TTROS_BRAIN_ROOT", None)

    def tearDown(self):
        if self._previous is not None:
            os.environ["TTROS_BRAIN_ROOT"] = self._previous

    def test_guard_is_inactive_without_b7_env(self):
        self.assertNotIn("TTROS_BRAIN_ROOT", os.environ)
        result = evaluate({
            "tool_name": "open_file",
            "tool_input": {"path": "docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md"},
        })
        self.assertEqual({}, result)

    def test_normal_david_keeps_search_files_read_file_execute_code(self):
        for tool_name, tool_input in (
            ("search_files", {"pattern": "ICP-A|System Buyers|GTM Engineering", "target": "content"}),
            ("read_file", {"path": "memory/offers.md"}),
            ("execute_code", {"code": "print('hello')"}),
            ("session_search", {"query": "CCI OR TRACC"}),
        ):
            with self.subTest(tool_name=tool_name):
                self.assertEqual({}, evaluate({"tool_name": tool_name, "tool_input": tool_input}))

    def test_normal_david_keeps_docs_ttros_and_scripts_paths(self):
        for path in (
            "docs/ttros/00_TTROS_CURRENT_STATE_v2026-09-04_rev6.md",
            "scripts/step3_b7_harness.py",
            "scripts/step3_b7_pass_A.scored.json",
        ):
            with self.subTest(path=path):
                self.assertEqual({}, evaluate({"tool_name": "open_file", "tool_input": {"path": path}}))

    def test_empty_or_malformed_payload_still_does_not_crash(self):
        self.assertEqual({}, evaluate({}))
        self.assertEqual({}, evaluate({"tool_name": None, "tool_input": None}))


if __name__ == "__main__":
    unittest.main()
