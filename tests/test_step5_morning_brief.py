"""Step 5 deterministic morning-brief acceptance and self-clearing proofs.

Revisit: when Step 5 predicates or authority contracts change. · Last touched: 2026-08-16.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

from tests.business_brain_test_support import make_registry, registry_data
from tools import aos_executive_brief as generator
from tools import context_assembler
from tools import morning_brief_detector as detector
from hooks import context_assembler_hook


NOW = dt.datetime(2026, 8, 4, 12, 30, tzinfo=dt.timezone.utc)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def jsonl(path: Path, rows: list[dict]) -> None:
    write(path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


class Step5Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / "repo"
        self.brain = base / "brain"
        for path in (
            self.root / "queue/receipts",
            self.root / "context",
            self.brain / "prospects",
            self.brain / "inbox",
            self.brain / "operating_context",
            self.brain / "projects",
        ):
            path.mkdir(parents=True, exist_ok=True)
        jsonl(self.root / "queue/work_items.jsonl", [])
        jsonl(self.root / "queue/prospects.jsonl", [])
        jsonl(self.root / "queue/run_ledger.jsonl", [])
        write(self.brain / "inbox/contradictions.md", self.note("contradictions", "inbox", "active", "Contradictions", "## Open\n\n- None.\n\n## Resolved\n\n- None."))
        write(self.brain / "operating_context/open_loops.md", self.note("loops", "operating_context", "active", "Open Loops", "## Open\n\n- None."))
        data = registry_data()
        paths = [
            "business_brain:prospects/fixture-alex.md",
            "business_brain:prospects/fixture-blair.md",
            "business_brain:inbox/contradictions.md",
            "business_brain:operating_context/open_loops.md",
            "business_brain:projects/stalled.md",
        ]
        scope = data["scopes"]["global"]
        scope["brain_pointers"].extend(paths)
        scope["search_source_identities"][-1]["paths"].extend(paths)
        scope["graphify_targets"][0]["paths"].extend(paths)
        self.registry = make_registry(data)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def note(note_id: str, kind: str, status: str, title: str, body: str, *, extra: str = "") -> str:
        return (
            f"---\nid: {note_id}\ntype: {kind}\nstatus: {status}\n{extra}"
            "hermes_last_write:\n  at: 2026-07-23T09:33:56Z\n---\n"
            f"# {title}\n\n> Revisit: on authoritative transition. · Last touched: 2026-07-23\n\n{body}\n"
        )

    @staticmethod
    def item(item_id: str, status: str, title: str, **extra) -> dict:
        return {
            "id": item_id,
            "title": title,
            "status": status,
            "owner": "revenue",
            "source": "fixture-authoritative",
            "created_at": "2026-07-22T23:59:55Z",
            "updated_at": "2026-07-22T23:59:55Z",
            "receipts": [],
            "allowed_actions": [],
            "needs_me": [],
            "review": "none",
            **extra,
        }

    @staticmethod
    def prospect(prospect_id: str, name: str, pointer: str, **extra) -> dict:
        return {
            "prospect_id": prospect_id,
            "name": name,
            "person_name": name,
            "status": "drafted",
            "status_date": "2026-07-22",
            "entity_page_path": pointer,
            "last_contact_date": None,
            "next_touch_due": None,
            "outcome": None,
            "reply_status": "none",
            "latest_event": {"type": "handoff_imported", "recorded_at": "2026-07-23T00:00:00Z"},
            "outreach_history": [{"type": "handoff_imported"}],
            "future_activity_cancelled": False,
            **extra,
        }

    def add_review_fixture(self, *, item_id: str = "AOS-2026-9001", name: str = "Alex Morgan", pointer: str = "business_brain:prospects/fixture-alex.md") -> tuple[dict, dict]:
        receipt = f"queue/receipts/{item_id}.md"
        write(self.root / receipt, "# Prepared review\n\nPASS\n")
        note_name = Path(pointer.removeprefix("business_brain:"))
        write(
            self.brain / note_name,
            self.note(
                "prospect-fixture-alex" if "alex" in pointer else "prospect-fixture-blair",
                "prospect",
                "human_review",
                name,
                "Verified fixture facts only.",
                extra=f"date: 2026-07-22\nqueue_ids:\n  - {item_id}\n",
            ),
        )
        item = self.item(
            item_id,
            "human_review",
            f"{name} — invitation ready",
            receipts=[{"path": receipt, "created_at": "2026-07-23T09:33:56Z", "status": "human_review"}],
            allowed_actions=["record_actual_outreach_event", "review_prepared_copy"],
            needs_me=["manual outreach action or outcome required"],
            outreach_review={
                "channel": "linkedin",
                "last_event": None,
                "prospect": {"person_name": name},
            },
        )
        row = self.prospect(
            f"prospect-{name.casefold().replace(' ', '-')}",
            name,
            pointer,
            review_item_id=item_id,
            outreach_channel="linkedin",
        )
        return item, row

    def graph(self, mapping: dict[str, str], *, state: str = "fresh"):
        def query(item_id: str, scope: str) -> dict:
            if state != "fresh":
                return {"graph_state": state, "targets": [], "fallback": {"route": "pointers_search", "reason": "injected stale projection"}}
            pointer = mapping.get(item_id)
            return {
                "graph_state": "fresh",
                "targets": [] if pointer is None else [{"path": pointer, "relationship_reasons": [f"one-hop fixture touched: {item_id}"]}],
                "fallback": None,
            }
        return query

    def detect(self, **kwargs):
        return detector.detect(
            root=self.root,
            brain_root=self.brain,
            now=NOW,
            client_scope="global",
            registry=self.registry,
            graph_query=kwargs.pop("graph_query", self.graph({})),
            **kwargs,
        )


class Step5DetectionTests(Step5Fixture):
    def test_review_finding_has_exact_evidence_age_owner_and_zero_tokens(self):
        item, row = self.add_review_fixture()
        jsonl(self.root / "queue/work_items.jsonl", [item])
        jsonl(self.root / "queue/prospects.jsonl", [row])
        result = self.detect(graph_query=self.graph({item["id"]: row["entity_page_path"]}))
        self.assertEqual(1, len(result.findings))
        finding = result.findings[0]
        self.assertEqual("prospect_review_without_outcome", finding.rule)
        self.assertEqual("liam_judgment", finding.owner_class)
        self.assertEqual(12, finding.calculated_age["days"])
        self.assertEqual("queue/receipts/AOS-2026-9001.md", finding.last_relevant_activity["reference"])
        self.assertIn("Liam's internal review", finding.waits_on)
        self.assertIn("explicit per-action confirmation", finding.external_action_boundary)
        self.assertEqual({"model_invocations": 0, "input_tokens": 0, "output_tokens": 0}, result.token_usage)
        self.assertNotIn("Verified fixture facts", json.dumps(result.to_dict()))

    def test_self_clears_via_supported_queue_transition_and_retains_history(self):
        item, row = self.add_review_fixture()
        other, other_row = self.add_review_fixture(
            item_id="AOS-2026-9002",
            name="Blair Singh",
            pointer="business_brain:prospects/fixture-blair.md",
        )
        jsonl(self.root / "queue/work_items.jsonl", [item, other])
        jsonl(self.root / "queue/prospects.jsonl", [row, other_row])
        graph = self.graph({item["id"]: row["entity_page_path"], other["id"]: other_row["entity_page_path"]})
        before = self.detect(graph_query=graph)
        self.assertEqual(1, sum(f.entity_id == "prospect-fixture-alex" for f in before.findings))
        canonical_before = (self.brain / "prospects/fixture-alex.md").read_bytes()
        ledger_before = (self.root / "queue/prospects.jsonl").read_bytes()

        spec = importlib.util.spec_from_file_location("step5_aos_queue", Path(__file__).parents[1] / "tools/aos-queue.py")
        queue_module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(queue_module)
        queue_module.update_status(self.root, item["id"], "cancelled")

        after = self.detect(graph_query=self.graph({other["id"]: other_row["entity_page_path"]}))
        self.assertFalse(any(f.entity_id == "prospect-fixture-alex" for f in after.findings))
        self.assertTrue(any(f.entity_id == "prospect-fixture-blair" for f in after.findings))
        self.assertEqual(canonical_before, (self.brain / "prospects/fixture-alex.md").read_bytes())
        self.assertEqual(ledger_before, (self.root / "queue/prospects.jsonl").read_bytes())
        closed = next(json.loads(line) for line in (self.root / "queue/work_items.jsonl").read_text().splitlines() if item["id"] in line)
        self.assertEqual("cancelled", closed["status"])
        self.assertEqual(item["receipts"], closed["receipts"])
        self.assertEqual([{"type": "handoff_imported"}], row["outreach_history"])
        from workflows.prospecting_daily_run.outreach_handoff import reconcile_prospect
        reconciliation = reconcile_prospect(row, [row, other_row], [closed, other])
        self.assertEqual(1, reconciliation["matched_ledger_snapshots"])
        self.assertEqual(1, reconciliation["matched_review_items"])
        self.assertFalse(reconciliation["missing_record_is_not_clearance"])

    def test_graph_fallback_is_scoped_body_free_and_reasoned(self):
        item, row = self.add_review_fixture()
        jsonl(self.root / "queue/work_items.jsonl", [item])
        jsonl(self.root / "queue/prospects.jsonl", [row])
        result = self.detect(graph_query=self.graph({}, state="stale"))
        self.assertEqual("canonical_frontmatter_fallback", result.discovery["route"])
        self.assertEqual("degraded", result.discovery["graph_state"])
        finding = result.findings[0]
        self.assertIn("canonical queue_ids", finding.discovery["relationship_reasons"][0])
        self.assertNotIn("Verified fixture facts", json.dumps(result.to_dict()))

    def test_unresolved_and_cross_client_scope_fail_closed_before_target_return(self):
        item, row = self.add_review_fixture()
        jsonl(self.root / "queue/work_items.jsonl", [item])
        jsonl(self.root / "queue/prospects.jsonl", [row])
        with self.assertRaisesRegex(detector.MorningBriefError, "unresolved scope"):
            detector.detect(root=self.root, brain_root=self.brain, now=NOW, client_scope=None, registry=self.registry, graph_query=self.graph({item["id"]: row["entity_page_path"]}))
        with self.assertRaises(PermissionError):
            detector.detect(root=self.root, brain_root=self.brain, now=NOW, client_scope="client-a", registry=self.registry, graph_query=self.graph({item["id"]: row["entity_page_path"]}))

    def test_authority_precedence_queue_terminal_beats_retained_note_and_ledger(self):
        item, row = self.add_review_fixture()
        item["status"] = "cancelled"
        jsonl(self.root / "queue/work_items.jsonl", [item])
        jsonl(self.root / "queue/prospects.jsonl", [row])
        result = self.detect()
        self.assertEqual([], [f.entity_id for f in result.findings if "fixture-alex" in f.entity_id])
        self.assertEqual("human_review", detector._canonical_prospect_notes(self.brain)[row["entity_page_path"]]["fields"]["status"])

    def test_predicates_deduplicate_and_stable_sort(self):
        due = self.prospect(
            "due-prospect", "Due Prospect", "business_brain:prospects/fixture-alex.md",
            status="sent", status_date="2026-07-20", next_touch_due="2026-07-24",
            outreach_channel="linkedin", last_contact_date="2026-07-20",
            latest_event={"type": "invitation_sent", "recorded_at": "2026-07-20T09:00:00Z"},
        )
        write(self.brain / "prospects/fixture-alex.md", self.note("due-prospect-note", "prospect", "sent", "Due Prospect", "No body is projected."))
        jsonl(self.root / "queue/prospects.jsonl", [due])
        first = self.detect()
        second = self.detect()
        self.assertEqual([f.to_dict() for f in first.findings], [f.to_dict() for f in second.findings])
        matches = [f for f in first.findings if f.entity_path == due["entity_page_path"]]
        self.assertEqual(1, len(matches))
        self.assertEqual("prospect_pending_connection", matches[0].rule)
        self.assertIn("prospect_overdue_follow_up", matches[0].supporting_rules)
        self.assertEqual(sorted(f.entity_path for f in first.findings), [f.entity_path for f in first.findings])

    def test_draft_and_due_date_boundaries_are_calculated_from_live_dates(self):
        write(self.brain / "prospects/fixture-alex.md", self.note("alex-note", "prospect", "drafted", "Alex", "No projected body."))
        write(self.brain / "prospects/fixture-blair.md", self.note("blair-note", "prospect", "sent", "Blair", "No projected body."))
        exactly_three = self.prospect(
            "alex", "Alex", "business_brain:prospects/fixture-alex.md",
            status_date="2026-08-01", latest_event=None,
        )
        due_today = self.prospect(
            "blair", "Blair", "business_brain:prospects/fixture-blair.md",
            status="sent", status_date="2026-07-31", next_touch_due="2026-08-04",
            latest_event={"type": "email_1_sent", "recorded_at": "2026-07-31T12:30:00Z"},
        )
        jsonl(self.root / "queue/prospects.jsonl", [exactly_three, due_today])
        first = self.detect()
        self.assertFalse(any(f.entity_id == "alex" for f in first.findings))
        due = next(f for f in first.findings if f.entity_id == "blair")
        self.assertEqual("prospect_overdue_follow_up", due.rule)
        self.assertEqual(4, due.calculated_age["days"])

        exactly_three["status_date"] = "2026-07-31"
        jsonl(self.root / "queue/prospects.jsonl", [exactly_three, due_today])
        second = self.detect()
        stale = next(f for f in second.findings if f.entity_id == "alex")
        self.assertEqual("prospect_no_recent_activity", stale.rule)
        self.assertEqual(4, stale.calculated_age["days"])

    def test_standalone_open_loop_is_query_derived_and_self_clearing(self):
        write(
            self.brain / "operating_context/open_loops.md",
            self.note("loops", "operating_context", "active", "Open Loops", "## Open\n\n- Reconcile the fixture operating question."),
        )
        before = self.detect()
        loop = next(f for f in before.findings if f.rule == "unresolved_follow_up")
        self.assertEqual("business_brain:operating_context/open_loops.md", loop.supporting_references[0])
        write(
            self.brain / "operating_context/open_loops.md",
            self.note("loops", "operating_context", "active", "Open Loops", "## Open\n\n- None.\n\n## Resolved\n\n- Reconcile the fixture operating question."),
        )
        after = self.detect()
        self.assertNotIn("unresolved_follow_up", {f.rule for f in after.findings})

    def test_queue_categories_contradiction_and_blocked_project_self_clear(self):
        rows = [
            self.item("AOS-2026-9101", "agent_todo", "System work"),
            self.item("AOS-2026-9102", "human_review", "Decision", receipts=[]),
            self.item("AOS-2026-9103", "blocked", "Blocked system", needs_me=[]),
            self.item("AOS-2026-9104", "blocked", "Needs judgment", needs_me=["choose path"]),
        ]
        jsonl(self.root / "queue/work_items.jsonl", rows)
        write(
            self.brain / "inbox/contradictions.md",
            self.note("contradictions", "inbox", "active", "Contradictions", "## Open\n\n- Fixture classification: records disagree.\n\n## Resolved\n\n- None."),
        )
        write(self.brain / "projects/stalled.md", self.note("stalled-project", "project", "blocked", "Stalled Project", "Blocked by recorded dependency."))
        result = self.detect()
        rules = {finding.rule for finding in result.findings}
        self.assertTrue({"open_commitment", "decision_awaiting_confirmation", "open_commitment_blocked", "item_waiting_on_liam_judgment", "recorded_contradiction", "project_blocked"}.issubset(rules))
        write(
            self.brain / "inbox/contradictions.md",
            self.note("contradictions", "inbox", "active", "Contradictions", "## Open\n\n- None.\n\n## Resolved\n\n- Fixture classification: resolved."),
        )
        write(self.brain / "projects/stalled.md", self.note("stalled-project", "project", "done", "Stalled Project", "Outcome retained."))
        cleared = self.detect()
        self.assertNotIn("recorded_contradiction", {f.rule for f in cleared.findings})
        self.assertNotIn("project_blocked", {f.rule for f in cleared.findings})


class Step5PublicationTests(Step5Fixture):
    def refresh(self, **kwargs):
        return generator.refresh(
            root=self.root,
            brain_root=self.brain,
            now=NOW,
            client_scope="global",
            registry=self.registry,
            graph_query=kwargs.pop("graph_query", self.graph({})),
            **kwargs,
        )

    def test_atomic_publication_and_failed_generation_preserve_complete_prior_set(self):
        first = self.refresh()
        self.assertEqual(0, first.exit_code, first.reason)
        paths = [self.root / generator.BRIEF_REL, self.root / generator.HEADER_REL, self.root / generator.FINDINGS_REL]
        before = {path: path.read_bytes() for path in paths}
        (self.root / "queue/prospects.jsonl").write_text("{malformed}\n", encoding="utf-8")
        failed = self.refresh()
        self.assertNotEqual(0, failed.exit_code)
        self.assertEqual(before, {path: path.read_bytes() for path in paths})

    def test_injected_replace_failure_rolls_back_every_artifact(self):
        self.assertEqual(0, self.refresh().exit_code)
        paths = [self.root / generator.BRIEF_REL, self.root / generator.HEADER_REL, self.root / generator.FINDINGS_REL]
        before = {path: path.read_bytes() for path in paths}
        real_replace = generator.os.replace
        counter = 0

        def fail_second(source, target):
            nonlocal counter
            counter += 1
            if counter == 2:
                raise OSError("injected publication failure")
            return real_replace(source, target)

        with mock.patch.object(generator.os, "replace", side_effect=fail_second):
            outcome = self.refresh()
        self.assertNotEqual(0, outcome.exit_code)
        self.assertEqual(before, {path: path.read_bytes() for path in paths})

    def test_generation_changes_only_three_artifacts_and_never_queue_or_brain(self):
        queue_before = (self.root / "queue/work_items.jsonl").read_bytes()
        brain_before = {path: path.read_bytes() for path in self.brain.rglob("*.md")}
        outcome = self.refresh()
        self.assertEqual(0, outcome.exit_code, outcome.reason)
        self.assertEqual(queue_before, (self.root / "queue/work_items.jsonl").read_bytes())
        self.assertEqual(brain_before, {path: path.read_bytes() for path in self.brain.rglob("*.md")})
        value = json.loads((self.root / generator.FINDINGS_REL).read_text(encoding="utf-8"))
        self.assertEqual(0, value["token_usage"]["model_invocations"])
        self.assertFalse(value["generated_artifact_used_as_input"])

    def test_assembled_context_projects_same_fresh_findings_and_decision_facts(self):
        jsonl(self.root / "queue/work_items.jsonl", [
            self.item("AOS-2026-9001", "agent_todo", "First outstanding fixture"),
            self.item("AOS-2026-9002", "blocked", "Second blocked fixture"),
        ])
        self.assertEqual(0, self.refresh().exit_code)
        expected = (self.root / generator.FINDINGS_REL).read_text(encoding="utf-8")
        success = generator.RefreshOutcome(0, "header", "brief")
        with (
            mock.patch.object(context_assembler, "ROOT", self.root),
            mock.patch("aos_executive_brief.refresh", return_value=success),
        ):
            block = context_assembler._deterministic_morning_brief(
                "knowledge_sensitive", query="What needs my attention this morning?"
            )
        self.assertEqual("deterministic morning findings", block.name)
        expected_value = json.loads(expected)
        expected_by_id = {row["finding_id"]: row for row in expected_value["findings"]}
        selected_ids = [line.split(" |", 1)[0][2:] for line in block.content.splitlines() if line.startswith("- morning-")]
        self.assertEqual(2, len(selected_ids))
        self.assertEqual(len(selected_ids), len(set(selected_ids)))
        self.assertTrue(set(selected_ids).issubset(expected_by_id))
        self.assertIn(f"{len(selected_ids)} of {expected_value['finding_count']} findings", block.content)
        for finding_id in selected_ids:
            finding = expected_by_id[finding_id]
            projected = context_assembler._project_morning_finding(finding)
            self.assertIn(projected["finding_id"], block.content)
            self.assertIn(projected["category"], block.content)
            self.assertIn(projected["rule"], block.content)
            self.assertIn(projected["entity_id"], block.content)
            self.assertIn(projected["title"], block.content)
            self.assertIn(projected["entity_path"], block.content)
            self.assertIn(projected["age"], block.content)
            self.assertIn(projected["reason"], block.content)
            self.assertIn(projected["owner_class"], block.content)
            self.assertIn(projected["waits_on"], block.content)
            self.assertIn(projected["next_permitted_action"], block.content)
            self.assertIn(projected["last_activity_source"], block.content)
            self.assertIn(projected["retrieval_route"], block.content)
            for predicate in projected["supporting_rules"]:
                self.assertIn(predicate, block.content)
            state = json.dumps(projected["current_state"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            self.assertIn(state, block.content)
            for reference in projected["supporting_references"]:
                self.assertIn(reference, block.content)
        self.assertNotIn("source_state_sha256", block.content)
        self.assertNotIn("observation_timestamp", block.content)
        self.assertNotIn('"seconds"', block.content)
        self.assertIn(hashlib.sha256(expected.encode("utf-8")).hexdigest(), "\n".join(block.sources))
        self.assertIn("zero-model-token detector", block.selection)
        self.assertIn("queue/work_items.jsonl", block.sources)

    def test_read_only_hermes_consultation_skips_session_vault_write_only(self):
        payload = {
            "hook_event_name": "post_llm_call",
            "session_id": "step5-read-only",
            "extra": {
                "platform": "cli",
                "user_message": "What needs my attention this morning?",
                "assistant_response": "Interpretation only.",
            },
        }
        with (
            mock.patch.object(context_assembler_hook, "_profile", return_value="operator-lean"),
            mock.patch.object(context_assembler_hook, "append_session_turn") as append,
            mock.patch.dict("os.environ", {"AOS_OPERATOR_CONSULTATION": "1"}),
        ):
            self.assertEqual({}, context_assembler_hook.evaluate(payload))
            append.assert_not_called()
        with (
            mock.patch.object(context_assembler_hook, "_profile", return_value="operator-lean"),
            mock.patch.object(context_assembler_hook, "append_session_turn") as append,
            mock.patch.dict("os.environ", {}, clear=True),
        ):
            self.assertEqual({}, context_assembler_hook.evaluate(payload))
            append.assert_called_once()


if __name__ == "__main__":
    unittest.main()
