"""Executable proofs for the Validation A run-scoped seal guard
(hooks/validation_a_seal_guard.py).

Validation A -- PREP PASS (2026-09-08). Proves the guard can return both
answers on a consequential check (deny AND allow), not just PASS: a read of a
path listed in scripts/validation_a_runs/seal_manifest.json is DENIED while
the run is active, a read of an unsealed control path is ALLOWED while the
run is active, and the guard is a complete pass-through (inert) when
TTROS_VALIDATION_A_RUN is not set -- mirroring the run-scoping proof pattern
already used for tests/test_b7_test_material_guard.py.

Zero model calls -- every case below is a synthetic pre_tool_call payload,
never a live Hermes invocation.
"""

from __future__ import annotations

import contextlib
import os
import unittest

from hooks.validation_a_seal_guard import evaluate

SEALED_PATH = (
    "/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Reviews/"
    "00_TTROS_CURRENT_STATE_v2026-09-01.md"
)
SEALED_BASENAME = "00_TTROS_CURRENT_STATE_v2026-09-01.md"
UNSEALED_CONTROL_PATH = "operating_context/current_priorities.md"

# Phase 2A extension target: one of the 12 resolved blind-run candidates' 14
# distinct source documents, from blind_run_phase1_freeze.json ->
# distinct_resolved_source_paths. Authoring-isolation deny target, not a
# PREP PASS seal-manifest entry.
FREEZE_SOURCE_PATH = (
    "/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain/"
    "sources/historical_calls/mike-knapp-july-21.md"
)
FREEZE_SOURCE_BASENAME = "mike-knapp-july-21.md"


@contextlib.contextmanager
def _validation_a_env():
    """Set the Validation A run-active signal for the duration of a call."""
    previous = os.environ.get("TTROS_VALIDATION_A_RUN")
    os.environ["TTROS_VALIDATION_A_RUN"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TTROS_VALIDATION_A_RUN", None)
        else:
            os.environ["TTROS_VALIDATION_A_RUN"] = previous


class SealGuardActiveTests(unittest.TestCase):
    """All cases here run with TTROS_VALIDATION_A_RUN set (guard active)."""

    def test_sealed_adjudication_path_is_denied(self):
        with _validation_a_env():
            result = evaluate({"tool_name": "open_file", "tool_input": {"path": SEALED_PATH}})
        self.assertEqual("block", result["action"])

    def test_sealed_path_denied_by_basename_even_if_differently_rooted(self):
        # A relative or differently-rooted reference to the same sealed file
        # (e.g. the docs/ttros mirror rather than the manifest's own absolute
        # path) must still be caught -- this is the defense-in-depth
        # basename match, not just an exact-string compare.
        with _validation_a_env():
            result = evaluate({
                "tool_name": "open_file",
                "tool_input": {"path": f"some/other/root/{SEALED_BASENAME}"},
            })
        self.assertEqual("block", result["action"])

    def test_sealed_scorer_report_is_denied(self):
        with _validation_a_env():
            result = evaluate({
                "tool_name": "open_file",
                "tool_input": {"path": "scripts/validation_a_fidelity_detector_report.md"},
            })
        self.assertEqual("block", result["action"])

    def test_generic_tools_are_blocked_outright(self):
        for tool_name, tool_input in (
            ("search_files", {"pattern": "candidate", "target": "content"}),
            ("read_file", {"path": UNSEALED_CONTROL_PATH}),
            ("execute_code", {"code": "print('hello')"}),
            ("session_search", {"query": "validation a"}),
        ):
            with self.subTest(tool_name=tool_name):
                with _validation_a_env():
                    result = evaluate({"tool_name": tool_name, "tool_input": tool_input})
                self.assertEqual("block", result["action"])

    def test_unsealed_control_path_is_allowed(self):
        # Negative case: a detector that can only print DENY proves nothing
        # either. This is the required "can return both answers" rehearsal.
        with _validation_a_env():
            result = evaluate({"tool_name": "open_file", "tool_input": {"path": UNSEALED_CONTROL_PATH}})
        self.assertEqual({}, result)

    def test_phase2a_freeze_source_path_is_denied(self):
        # Authoring-isolation extension: one of the 12 resolved candidates'
        # 14 source documents must DENY while the run is active.
        with _validation_a_env():
            result = evaluate({"tool_name": "open_file", "tool_input": {"path": FREEZE_SOURCE_PATH}})
        self.assertEqual("block", result["action"])

    def test_phase2a_freeze_source_denied_by_basename_even_if_differently_rooted(self):
        with _validation_a_env():
            result = evaluate({
                "tool_name": "open_file",
                "tool_input": {"path": f"some/other/root/{FREEZE_SOURCE_BASENAME}"},
            })
        self.assertEqual("block", result["action"])

    def test_phase2a_unsealed_control_still_allowed_alongside_freeze_extension(self):
        # Both-answers rehearsal for the extension specifically, not just the
        # original manifest: adding the 14-path deny-set must not turn the
        # guard into a deny-everything.
        with _validation_a_env():
            result = evaluate({"tool_name": "open_file", "tool_input": {"path": UNSEALED_CONTROL_PATH}})
        self.assertEqual({}, result)

    def test_legitimate_non_generic_tool_names_remain_available(self):
        with _validation_a_env():
            self.assertEqual({}, evaluate({
                "tool_name": "mcp__brain__open_note",
                "tool_input": {"pointer": "memory/offers.md"},
            }))

    def test_empty_or_malformed_payload_does_not_crash(self):
        with _validation_a_env():
            self.assertEqual({}, evaluate({}))
            self.assertEqual({}, evaluate({"tool_name": None, "tool_input": None}))


class SealGuardInertWhenInactiveTests(unittest.TestCase):
    """No TTROS_VALIDATION_A_RUN in the environment => guard is a pass-through."""

    def setUp(self):
        self._previous = os.environ.pop("TTROS_VALIDATION_A_RUN", None)

    def tearDown(self):
        if self._previous is not None:
            os.environ["TTROS_VALIDATION_A_RUN"] = self._previous

    def test_guard_is_inactive_without_env_signal(self):
        self.assertNotIn("TTROS_VALIDATION_A_RUN", os.environ)
        result = evaluate({"tool_name": "open_file", "tool_input": {"path": SEALED_PATH}})
        self.assertEqual({}, result)

    def test_phase2a_freeze_extension_inactive_without_env_signal(self):
        self.assertNotIn("TTROS_VALIDATION_A_RUN", os.environ)
        result = evaluate({"tool_name": "open_file", "tool_input": {"path": FREEZE_SOURCE_PATH}})
        self.assertEqual({}, result)

    def test_generic_tools_unaffected_when_inactive(self):
        for tool_name, tool_input in (
            ("search_files", {"pattern": "candidate"}),
            ("read_file", {"path": SEALED_PATH}),
            ("execute_code", {"code": "print('hello')"}),
        ):
            with self.subTest(tool_name=tool_name):
                self.assertEqual({}, evaluate({"tool_name": tool_name, "tool_input": tool_input}))


if __name__ == "__main__":
    unittest.main()
