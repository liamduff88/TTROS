"""Fixture checks for the Operating Hermes Codex capacity gate.

Revisit: when Hermes changes its pool or usage window schema. · Last touched: 2026-09-23.
"""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from tools.codex_capacity_preflight import CapacityUnavailable, healthy_windows, preflight_agent


def snapshot(session, weekly):
    return SimpleNamespace(
        source="usage_api", unavailable_reason=None,
        windows=[SimpleNamespace(label="Session", used_percent=session),
                 SimpleNamespace(label="Weekly", used_percent=weekly)],
    )


class Pool:
    def __init__(self):
        self.benched = []
        self.rows = [
            SimpleNamespace(id="a", label="Account A", priority=0, runtime_api_key="a-key", runtime_base_url="https://example.test"),
            SimpleNamespace(id="b", label="Account B", priority=1, runtime_api_key="b-key", runtime_base_url="https://example.test"),
        ]

    def entries(self):
        return self.rows

    def reclaim(self, slot, *, model=None):
        return next((row for row in self.rows if row.id == slot and slot not in self.benched), None)

    def mark_exhausted_and_rotate(self, *, status_code, credential_id, error_context, failure_reason):
        self.benched.append(credential_id)
        return None


class CodexCapacityPreflightTests(unittest.TestCase):
    def setUp(self):
        self.home = mock.patch.dict(os.environ, {"HERMES_HOME": "/tmp/profiles/aos-orchestrator"})
        self.home.start()
        self.addCleanup(self.home.stop)
        self.pool = Pool()
        self.agent = SimpleNamespace(
            provider="openai-codex", model="gpt-5.5", api_key="a-key",
            _credential_pool_entry_id="a", _credential_pool=self.pool,
        )
        def swap(entry):
            self.agent.api_key = entry.runtime_api_key
            self.agent._credential_pool_entry_id = entry.id
            return True
        self.agent._swap_credential = mock.Mock(side_effect=swap)

    def check(self, a, b):
        fetched = []
        def fetch(*, base_url, api_key):
            fetched.append(api_key)
            return {"a-key": a, "b-key": b}[api_key]
        return preflight_agent(self.agent, fetch_usage=fetch, pool=self.pool), fetched

    def test_above_three_percent_keeps_selected_slot(self):
        slot, fetched = self.check(snapshot(96.9, 96.9), snapshot(0, 0))
        self.assertEqual((slot, fetched), ("a", ["a-key"]))
        self.agent._swap_credential.assert_not_called()

    def test_either_window_at_three_percent_selects_b(self):
        for a in (snapshot(97, 10), snapshot(10, 97)):
            with self.subTest(a=a.windows[0].used_percent):
                self.pool.benched.clear()
                self.agent._credential_pool_entry_id = "a"
                self.agent.api_key = "a-key"
                slot, fetched = self.check(a, snapshot(2, 4))
                self.assertEqual((slot, fetched), ("b", ["a-key", "b-key"]))
                self.assertEqual(self.pool.benched, ["a"])

    def test_recovered_a_reclaims_primary_priority(self):
        self.agent._credential_pool_entry_id = "b"
        self.agent.api_key = "b-key"
        slot, fetched = self.check(snapshot(2, 2), snapshot(40, 50))
        self.assertEqual((slot, fetched), ("a", ["a-key"]))
        self.agent._swap_credential.assert_called_once_with(self.pool.rows[0])

    def test_b_remains_selected_while_a_is_benched(self):
        self.pool.benched.append("a")
        self.agent._credential_pool_entry_id = "b"
        self.agent.api_key = "b-key"
        slot, fetched = self.check(snapshot(2, 2), snapshot(40, 50))
        self.assertEqual((slot, fetched), ("b", ["b-key"]))

    def test_both_low_or_unknown_stop_before_model(self):
        for b in (snapshot(97, 0), snapshot(0, 97), None):
            with self.subTest(b=b):
                self.pool.benched.clear()
                with self.assertRaises(CapacityUnavailable):
                    self.check(snapshot(97, 0), b)
        self.agent._swap_credential.assert_not_called()

    def test_missing_window_fails_closed(self):
        self.assertFalse(healthy_windows(SimpleNamespace(
            source="usage_api", unavailable_reason=None,
            windows=[SimpleNamespace(label="Session", used_percent=1)],
        )))


if __name__ == "__main__":
    unittest.main()
