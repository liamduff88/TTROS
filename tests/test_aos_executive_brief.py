"""Executive brief generator and runtime wiring proofs.

Revisit: when executive evidence or profile assembly contracts change. · Last touched: 2026-08-01.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

from tools import aos_executive_brief as brief


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


class ExecutiveBriefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.brain = Path(self.temp.name) / "brain"
        for path in (
            self.root / "context",
            self.root / "queue" / "receipts",
            self.brain / "index",
            self.brain / "operating_context",
            self.brain / "memory",
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.write_jsonl("queue/work_items.jsonl", [])
        self.write_jsonl("queue/run_ledger.jsonl", [])
        self.write_jsonl("queue/prospects.jsonl", [])
        indexed = "\n".join(f"- `{pointer.removeprefix('business_brain:')}`" for pointer in brief.CANONICAL_POINTERS)
        (self.brain / "index/MEMORY_INDEX.md").write_text(f"# Index\n{indexed}\n", encoding="utf-8")
        for pointer in brief.CANONICAL_POINTERS:
            path = self.brain / pointer.removeprefix("business_brain:")
            path.write_text(
                "---\nid: fixture-note\ntype: knowledge\n---\n"
                f"# {path.stem.replace('_', ' ').title()}\n"
                "> Revisit: on material change. · Last touched: 2026-07-31\n",
                encoding="utf-8",
            )

    def tearDown(self):
        self.temp.cleanup()

    def write_jsonl(self, relative: str, rows: list[dict]) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

    @staticmethod
    def item(item_id: str, status: str, created: str, title: str, **extra) -> dict:
        return {
            "id": item_id,
            "status": status,
            "created_at": created,
            "updated_at": created,
            "title": title,
            "source": "manual",
            "receipts": [],
            **extra,
        }

    def refresh(self, when: datetime = NOW):
        return brief.refresh(root=self.root, brain_root=self.brain, now=when)

    def test_caps_required_order_and_empty_sections(self):
        outcome = self.refresh()
        self.assertEqual(0, outcome.exit_code, outcome.reason)
        self.assertLess(brief.token_count(outcome.header), brief.HEADER_TOKEN_LIMIT)
        self.assertLess(brief.token_count(outcome.brief), brief.BRIEF_TOKEN_LIMIT)
        self.assertEqual(1, len((self.root / brief.HEADER_REL).read_text(encoding="utf-8").splitlines()))
        positions = [outcome.brief.index(f"## {name}") for name in brief.SECTION_NAMES]
        self.assertEqual(positions, sorted(positions))
        for name in ("Open", "Changed", "Decisions"):
            section = outcome.brief.partition(f"## {name}\n")[2].partition("\n\n## ")[0]
            self.assertEqual("none", section.strip())
        conflicts = outcome.brief.partition("## Conflicts\n")[2].partition("\n\n## Decisions")[0]
        self.assertEqual("### Conflicts\nnone\n\n### Unknown\nnone", conflicts)
        self.assertRegex(
            outcome.header,
            r"^0 awaiting you · 0 conflicts · 0 unknown · oldest open commitment 0d · brief 0h old$",
        )

    def test_exact_runtime_tokenizer_caps_when_available(self):
        try:
            import tiktoken
        except ImportError:
            self.skipTest("runtime tokenizer is not installed in this interpreter")
        rows = [
            self.item(
                f"AOS-2026-{1000 + index:04d}",
                "needs_input",
                "2026-07-31T10:00:00Z",
                "decision",
            )
            for index in range(260)
        ]
        self.write_jsonl("queue/work_items.jsonl", rows)
        outcome = self.refresh()
        encoding = tiktoken.get_encoding("o200k_base")
        self.assertLess(len(encoding.encode(outcome.header)), brief.HEADER_TOKEN_LIMIT)
        self.assertLess(len(encoding.encode(outcome.brief)), brief.BRIEF_TOKEN_LIMIT)

    def test_contradiction_detection_cites_recent_and_canonical_sources(self):
        canonical = self.brain / "operating_context/active_projects.md"
        canonical.write_text(
            "---\nid: active\ntype: operating_state\n---\n# Active Projects\n"
            "> Revisit: on material change. · Last touched: 2026-07-30\n\n"
            "## Project Atlas — benched\n",
            encoding="utf-8",
        )
        self.write_jsonl("queue/work_items.jsonl", [
            self.item("AOS-2026-1001", "agent_todo", "2026-07-31T10:00:00Z", "Project Atlas is active")
        ])
        outcome = self.refresh()
        self.assertIn("Project Atlas: recent evidence says active; canonical note says inactive", outcome.brief)
        self.assertIn("queue/work_items.jsonl#AOS-2026-1001", outcome.brief)
        self.assertIn("business_brain:operating_context/active_projects.md", outcome.brief)
        self.assertIn("3 conflicts", outcome.header)
        self.assertIn("0 unknown", outcome.header)
        self.assertIn("STALE — `business_brain:operating_context/active_projects.md`", outcome.brief)
        self.assertIn("REVISIT MET — `business_brain:operating_context/active_projects.md`", outcome.brief)

    def test_open_shows_recent_items_stale_material_and_excludes_dead_fixtures(self):
        rows = [
            self.item("AOS-2026-1002", "agent_todo", "2026-07-30T10:00:00Z", "newer"),
            self.item("AOS-2026-1001", "blocked", "2026-07-01T10:00:00Z", "dead fixture"),
            self.item(
                "AOS-2026-1004",
                "human_review",
                "2026-07-02T10:00:00Z",
                "stale with receipt",
                receipts=[{"path": "queue/receipts/AOS-2026-1004.json"}],
            ),
            self.item("AOS-2026-1003", "done", "2026-06-01T10:00:00Z", "closed"),
        ]
        self.write_jsonl("queue/work_items.jsonl", rows)
        outcome = self.refresh()
        open_text = outcome.brief.partition("## Open\n")[2].partition("\n\n## Changed")[0]
        self.assertIn("AOS-2026-1002", open_text)
        self.assertIn("AOS-2026-1004", open_text)
        self.assertNotIn("AOS-2026-1001", open_text)
        self.assertNotIn("AOS-2026-1003", open_text)
        self.assertIn("1 stale item(s) without artifact or receipt excluded", open_text)
        self.assertIn("oldest open commitment 30d", outcome.header)

    def test_changed_uses_only_previous_single_brief(self):
        self.write_jsonl("queue/work_items.jsonl", [
            self.item("AOS-2026-1001", "human_review", "2026-07-30T10:00:00Z", "review me")
        ])
        first = self.refresh()
        self.assertIn("## Changed\nnone", first.brief)
        self.write_jsonl("queue/work_items.jsonl", [
            self.item("AOS-2026-1001", "done", "2026-07-30T10:00:00Z", "review me")
        ])
        second = self.refresh(NOW + timedelta(hours=1))
        self.assertIn("AOS-2026-1001: human_review → done", second.brief)
        third = self.refresh(NOW + timedelta(hours=2))
        self.assertNotIn("human_review → done", third.brief)

    def test_decisions_show_ten_informative_rows_material_first_and_summary(self):
        rows = [
            self.item(
                f"AOS-2026-{1000 + index:04d}",
                "needs_input" if index % 2 else "human_review",
                f"2026-07-{(index % 28) + 1:02d}T10:00:00Z",
                "long decision title " + ("x" * 180),
            )
            for index in range(260)
        ]
        rows[-1]["receipts"] = [{"path": "queue/receipts/material.json"}]
        self.write_jsonl("queue/work_items.jsonl", rows)
        outcome = self.refresh()
        decisions = outcome.brief.partition("## Decisions\n")[2]
        decision_rows = [line for line in decisions.splitlines() if line.startswith("- AOS-")]
        self.assertEqual(10, len(decision_rows))
        self.assertIn(rows[-1]["id"], decision_rows[0])
        self.assertIn("long decision title", decision_rows[0])
        self.assertIn("status:", decision_rows[0])
        self.assertIn("age:", decision_rows[0])
        self.assertIn("250 further items awaiting review — see dashboard", decisions)
        self.assertNotRegex(decisions, r"human_review — AOS-")
        self.assertLess(brief.token_count(outcome.brief), brief.BRIEF_TOKEN_LIMIT)

    def test_full_canonical_roots_are_read_and_skips_are_reported(self):
        extra = self.brain / "memory/unindexed_note.md"
        extra.write_text(
            "---\nid: extra\ntype: knowledge\n---\n# Extra\n"
            "> Revisit: on material change. · Last touched: 2026-07-31\n",
            encoding="utf-8",
        )
        backup = self.brain / "operating_context/registry-copy.bak"
        backup.write_text("not a note", encoding="utf-8")
        outcome = self.refresh()
        self.assertIn("`memory/unindexed_note.md`", outcome.brief)
        self.assertIn("Canonical notes SKIPPED under `business_brain:` (1)", outcome.brief)
        self.assertIn("`operating_context/registry-copy.bak`", outcome.brief)
        self.assertIn("not a Markdown note", outcome.brief)

    def test_unparseable_note_is_unknown_and_revisit_condition_is_flagged(self):
        unknown = self.brain / "memory/unknown.md"
        unknown.write_text(
            "---\nid: unknown\ntype: knowledge\n---\n# Missing freshness metadata\n",
            encoding="utf-8",
        )
        due = self.brain / "memory/due.md"
        due.write_text(
            "---\nid: due\ntype: knowledge\n---\n# Due\n"
            "> Revisit: at each 1-week review. · Last touched: 2026-07-01\n",
            encoding="utf-8",
        )
        outcome = self.refresh()
        section = outcome.brief.partition("## Conflicts\n")[2].partition("\n\n## Decisions")[0]
        conflicts = section.partition("### Conflicts\n")[2].partition("\n\n### Unknown")[0]
        unknowns = section.partition("### Unknown\n")[2]
        self.assertNotIn("business_brain:memory/unknown.md", conflicts)
        self.assertIn("REVISIT MET — `business_brain:memory/due.md`", conflicts)
        self.assertIn("`business_brain:memory/unknown.md`", unknowns)
        self.assertIn("missing parseable Revisit and Last touched metadata", unknowns)
        self.assertIn("1 conflicts · 1 unknown", outcome.header)

    def test_formatting_equivalence_is_not_a_conflict(self):
        canonical = self.brain / "operating_context/active_projects.md"
        canonical.write_text(
            "---\nid: active\ntype: operating_state\n---\n# Active Projects\n"
            "> Revisit: on material change. · Last touched: 2026-07-31\n\n"
            "## Project Atlas — active\n",
            encoding="utf-8",
        )
        self.write_jsonl("queue/work_items.jsonl", [
            self.item("AOS-2026-1001", "agent_todo", "2026-07-31T10:00:00Z", "Project Atlas is Active")
        ])
        outcome = self.refresh()
        self.assertNotIn("Project Atlas: recent evidence", outcome.brief)

    def test_atomic_replaces_target_artifacts(self):
        real_replace = os.replace
        replaced: list[tuple[Path, Path]] = []

        def recording_replace(source, target):
            replaced.append((Path(source), Path(target)))
            return real_replace(source, target)

        with mock.patch.object(brief.os, "replace", side_effect=recording_replace):
            outcome = self.refresh()
        self.assertEqual(0, outcome.exit_code, outcome.reason)
        targets = [target for _source, target in replaced]
        self.assertEqual([self.root / brief.BRIEF_REL, self.root / brief.HEADER_REL], targets)
        self.assertTrue(all(source.parent == target.parent for source, target in replaced))
        self.assertFalse(list((self.root / "context").glob("*.tmp")))

    def test_failed_refresh_retains_last_good_brief_and_marks_header_stale(self):
        first = self.refresh()
        expected_brief = first.brief
        for relative in ("queue/work_items.jsonl", "queue/run_ledger.jsonl", "queue/prospects.jsonl"):
            (self.root / relative).unlink()
        for path in sorted(self.brain.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        outcome = self.refresh(NOW + timedelta(hours=5))
        self.assertNotEqual(0, outcome.exit_code)
        self.assertEqual(expected_brief, (self.root / brief.BRIEF_REL).read_text(encoding="utf-8"))
        header = (self.root / brief.HEADER_REL).read_text(encoding="utf-8").strip()
        self.assertTrue(header.endswith("· STALE"))
        self.assertIn("brief 5h old", header)
        self.assertIn("0 conflicts · 0 unknown", header)

    def test_no_previous_complete_failure_emits_unavailable_artifacts(self):
        empty_root = Path(self.temp.name) / "empty"
        (empty_root / "context").mkdir(parents=True)
        outcome = brief.refresh(root=empty_root, brain_root=Path(self.temp.name) / "missing", now=NOW)
        self.assertNotEqual(0, outcome.exit_code)
        self.assertEqual("brief unavailable\n", (empty_root / brief.HEADER_REL).read_text(encoding="utf-8"))
        generated = (empty_root / brief.BRIEF_REL).read_text(encoding="utf-8")
        for name in brief.SECTION_NAMES:
            self.assertIn(f"## {name}\nnone", generated)

    def test_bad_source_degrades_without_blocking_good_sources(self):
        (self.root / "queue/prospects.jsonl").write_text("{not-json}\n", encoding="utf-8")
        outcome = self.refresh()
        self.assertEqual(0, outcome.exit_code, outcome.reason)
        self.assertIn("ignored 1 malformed JSONL line", outcome.brief)
        self.assertIn("source: `queue/prospects.jsonl`", outcome.brief)

    def test_generation_writes_nothing_outside_two_artifacts(self):
        before = {
            path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file()
        }
        outcome = self.refresh()
        self.assertEqual(0, outcome.exit_code, outcome.reason)
        after = {
            path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob("*") if path.is_file()
        }
        changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
        self.assertEqual({brief.BRIEF_REL, brief.HEADER_REL}, changed)

    def test_pending_gmail_proposals_are_counted_without_body_or_attachment_reads(self):
        item = self.item(
            "AOS-2026-1001",
            "needs_input",
            "2026-07-31T10:00:00Z",
            "Live Gmail capture requires review",
            source="capture/gmail-live-read-only",
            context="metadata-only",
            capture_proposal={"record_id": "cap-123", "permitted_metadata": {"triage_state": "needs_input"}},
        )
        self.write_jsonl("queue/work_items.jsonl", [item])
        outcome = self.refresh()
        self.assertIn("Gmail capture: 1 pending metadata-only proposal", outcome.brief)
        self.assertIn("AOS-2026-1001", outcome.brief.partition("## Decisions\n")[2])


class ExecutiveBriefWiringTests(unittest.TestCase):
    def test_operator_lean_refreshes_once_and_loads_header_only(self):
        launcher = (ROOT / "tools/aos-hermes-operator-lean.sh").read_text(encoding="utf-8")
        self.assertEqual(1, launcher.count('python3 "$brief_generator"'))
        self.assertIn("EXECUTIVE_HEADER.txt", launcher)
        self.assertNotIn("EXECUTIVE_BRIEF.md", launcher)
        self.assertNotIn("aos-orchestrator", launcher)
        self.assertNotIn("create_task", launcher)

    def test_orchestrator_refreshes_once_and_loads_full_brief_conditionally(self):
        launcher = (ROOT / "tools/aos-hermes-coordinator.sh").read_text(encoding="utf-8")
        self.assertEqual(1, launcher.count('python3 "$brief_generator"'))
        self.assertIn('if [[ "$profile" == "aos-orchestrator" ]]', launcher)
        self.assertIn("EXECUTIVE_BRIEF.md", launcher)
        self.assertNotIn("EXECUTIVE_HEADER.txt", launcher)
        self.assertIn("do not auto-escalate", launcher)
        self.assertNotIn("create_task", launcher)

    def test_real_cli_writes_only_bounded_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            brain_root = Path(tmp) / "brain"
            (root / "context").mkdir(parents=True)
            (root / "queue").mkdir()
            for name in ("work_items.jsonl", "run_ledger.jsonl", "prospects.jsonl"):
                (root / "queue" / name).write_text("", encoding="utf-8")
            (brain_root / "index").mkdir(parents=True)
            (brain_root / "index/MEMORY_INDEX.md").write_text("# Index\n", encoding="utf-8")
            result = subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools/aos_executive_brief.py"),
                    "--root",
                    str(root),
                    "--brain-root",
                    str(brain_root),
                    "--now",
                    "2026-07-31T12:00:00Z",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / brief.BRIEF_REL).is_file())
            self.assertTrue((root / brief.HEADER_REL).is_file())


if __name__ == "__main__":
    unittest.main()
