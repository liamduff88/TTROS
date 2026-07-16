"""Block 3 dark-capture durability, isolation, projection, and queue tests.

Revisit: at live-capture activation or when capture metadata changes. · Last touched: 2026-07-15.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import jsonschema

from dashboard.backend.business_brain_graph import BusinessBrainGraphService
from tests.business_brain_test_support import make_registry, registry_data, write_note
from tools import aos_indexer
from tools.aos_capture import (
    CaptureEngine,
    CaptureEnvelope,
    CaptureError,
    CaptureLedgerWriter,
    CaptureMetadataProjection,
    CaptureProposer,
    CaptureQueueWriter,
    CaptureStorage,
    CaptureStorageError,
    CaptureTriage,
    ComposioGmailLiveAdapter,
    DeltaBatch,
    FixtureDeltaAdapter,
    LiveCaptureDisabled,
    LocalDeterministicClassifier,
    STAGE2_EVENT,
    STAGE3_EVENT,
    capture_document,
)
from tools.business_brain_context import ScopedBrainLoader
from tools.business_brain_scope import ClientScopeError, ClientScopeRegistry


ROOT = Path(__file__).resolve().parents[1]
BODY_SENTINEL = "BLOCK3_BODY_SENTINEL_7a9f"
THREAD_SENTINEL = "BLOCK3_THREAD_SENTINEL_83bd"
ATTACHMENT_SENTINEL = "BLOCK3_ATTACHMENT_SENTINEL_42ce"


def capture_registry_data() -> dict:
    data = copy.deepcopy(registry_data())
    identities = {
        "client-a": ("block3-client-a@example.invalid", "block3-thread-a"),
        "client-b": ("block3-client-b@example.invalid", "block3-thread-b"),
        "global": ("block3-internal@example.invalid", "block3-thread-global"),
    }
    for scope, (sender, thread) in identities.items():
        record = data["scopes"][scope]
        record["capture_identities"] = [
            {"match_type": "sender", "value_sha256": ClientScopeRegistry.capture_identity_hash(sender)},
            {"match_type": "thread", "value_sha256": ClientScopeRegistry.capture_identity_hash(thread)},
        ]
        record["capture_evidence_prefixes"] = [f"capture:{scope}:"]
        record["search_source_identities"].append({"source": "capture_metadata", "path_prefix": f"capture:{scope}:"})
    data["scopes"]["client-disabled"]["capture_identities"] = []
    data["scopes"]["client-disabled"]["capture_evidence_prefixes"] = []
    return data


def envelope(
    message: str,
    *,
    sender: str = "block3-client-a@example.invalid",
    thread: str = "block3-thread-a",
    history: str = "10",
    subject: str = "Please review this update",
    headers: dict | None = None,
) -> CaptureEnvelope:
    return CaptureEnvelope(
        provider="gmail_fixture",
        message_id=f"fixture-{message}",
        thread_id=thread,
        history_id=history,
        timestamp="2026-07-15T12:00:00Z",
        sender=sender,
        subject=subject,
        source_type="gmail_fixture",
        headers=headers or {},
    )


class CaptureTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.storage = CaptureStorage(self.repo / "capture" / "runtime", repo_root=self.repo)
        self.registry = make_registry(capture_registry_data())

    def tearDown(self):
        self.temp.cleanup()

    def engine(self, *records: CaptureEnvelope, cursor: str = "20") -> tuple[CaptureEngine, FixtureDeltaAdapter]:
        adapter = FixtureDeltaAdapter(DeltaBatch(next_cursor=cursor, envelopes=tuple(records)))
        return CaptureEngine(self.storage, self.registry), adapter

    def prepare_queue(self) -> CaptureQueueWriter:
        for relative in (
            "queue/run_ledger_schema.json",
            "queue/token_ledger_schema.json",
            "queue/schemas/work_item.schema.json",
            "queue/schemas/receipt.schema.json",
        ):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        return CaptureQueueWriter(self.repo, ledger=CaptureLedgerWriter(self.repo))


class StorageAndStage1Tests(CaptureTestCase):
    def test_storage_contract_is_git_ignored_preview_blocked_and_backup_included(self):
        self.assertIn("capture/runtime/", (ROOT / ".gitignore").read_text(encoding="utf-8"))
        dashboard_source = (ROOT / "dashboard/backend/main.py").read_text(encoding="utf-8")
        allowed_block = dashboard_source.split("_QUEUE_ARTIFACT_ALLOWED_PREFIXES = (", 1)[1].split(")", 1)[0]
        self.assertNotIn("capture/", allowed_block)
        backup = (ROOT / "tools/aos-linux-backup.sh").read_text(encoding="utf-8")
        self.assertIn('"$ROOT/" "$destination/"', backup)
        self.assertNotRegex(backup, r"exclude=.*capture")

    def test_runtime_permissions_and_append_only_raw(self):
        engine, adapter = self.engine(envelope("one"))
        result = engine.run_once(adapter)
        self.assertEqual("20", result["cursor"])
        self.assertTrue(self.storage.permission_report()["ok"])
        raw_path = next(self.storage.root.glob("scopes/*/raw/records.jsonl"))
        before = raw_path.read_bytes()
        engine.run_once(adapter)
        self.assertEqual(before, raw_path.read_bytes())
        self.assertEqual(1, len(self.storage.raw_records()))
        self.assertEqual(0o700, os.stat(self.storage.root).st_mode & 0o777)
        self.assertEqual(0o600, os.stat(raw_path).st_mode & 0o777)

    def test_failure_before_raw_append_does_not_advance(self):
        engine, adapter = self.engine(envelope("one"))
        with self.assertRaises(CaptureStorageError):
            engine.run_once(adapter, failure_injection="before_raw_append")
        self.assertEqual([], self.storage.raw_records())
        self.assertIsNone(self.storage.cursor(adapter.provider_key))

    def test_failure_after_raw_append_replays_without_duplicate(self):
        engine, adapter = self.engine(envelope("one"))
        with self.assertRaises(CaptureStorageError):
            engine.run_once(adapter, failure_injection="after_raw_append")
        self.assertEqual(1, len(self.storage.raw_records()))
        self.assertEqual([], self.storage.processing_rows(adapter.provider_key))
        self.assertIsNone(self.storage.cursor(adapter.provider_key))
        engine.run_once(adapter)
        self.assertEqual(1, len(self.storage.raw_records()))
        self.assertEqual(1, len(self.storage.processing_rows(adapter.provider_key)))
        self.assertEqual("20", self.storage.cursor(adapter.provider_key))

    def test_failure_after_processing_replays_idempotently(self):
        engine, adapter = self.engine(envelope("one"))
        with self.assertRaises(CaptureStorageError):
            engine.run_once(adapter, failure_injection="after_processing_state")
        self.assertEqual(1, len(self.storage.raw_records()))
        self.assertEqual(1, len(self.storage.processing_rows(adapter.provider_key)))
        self.assertIsNone(self.storage.cursor(adapter.provider_key))
        engine.run_once(adapter)
        self.assertEqual(1, len(self.storage.raw_records()))
        self.assertEqual(1, len(self.storage.processing_rows(adapter.provider_key)))

    def test_cursor_publication_failure_preserves_prior_cursor(self):
        engine, adapter = self.engine(envelope("one"), cursor="20")
        engine.run_once(adapter)
        adapter.batch = DeltaBatch(next_cursor="30", envelopes=(envelope("two", history="30"),))
        with self.assertRaises(CaptureStorageError):
            engine.run_once(adapter, failure_injection="during_cursor_publication")
        self.assertEqual("20", self.storage.cursor(adapter.provider_key))
        engine.run_once(adapter)
        self.assertEqual("30", self.storage.cursor(adapter.provider_key))
        self.assertEqual(2, len(self.storage.raw_records()))

    def test_repeated_and_out_of_order_history_is_deterministic(self):
        first = envelope("same", history="11")
        duplicate = envelope("same", history="11")
        earlier = envelope("earlier", history="9")
        engine, adapter = self.engine(first, duplicate, earlier, cursor="12")
        engine.run_once(adapter)
        ids = [row["record_id"] for row in self.storage.processing_rows(adapter.provider_key)]
        self.assertEqual([earlier.record_id, first.record_id], ids)
        engine.run_once(adapter)
        self.assertEqual(2, len(self.storage.raw_records()))

    def test_kill_switch_prevents_provider_and_state_activity(self):
        self.storage.set_control_for_fixture(kill_switch=True)
        engine, adapter = self.engine(envelope("one"))
        with self.assertRaises(LiveCaptureDisabled):
            engine.run_once(adapter)
        self.assertEqual(0, adapter.activity_count)
        self.assertEqual([], self.storage.raw_records())
        self.assertIsNone(self.storage.cursor(adapter.provider_key))

    def test_live_adapter_requires_all_separate_activation_guards(self):
        activity = []
        activation = self.repo / "separate-activation.json"
        adapter = ComposioGmailLiveAdapter(
            storage=self.storage,
            executor=lambda action, payload: activity.append((action, payload)) or {"historyId": "10"},
            activation_path=activation,
            no_live=True,
        )
        with self.assertRaises(LiveCaptureDisabled):
            adapter.read_delta(None)
        self.assertEqual([], activity)
        self.storage._replace_json(self.storage.control_path, {"live_capture_enabled": True, "kill_switch": False})
        adapter.no_live = False
        with self.assertRaises(LiveCaptureDisabled):
            adapter.read_delta(None)
        self.assertEqual([], activity)
        activation.write_text(json.dumps({"approved": True, "contract": "wrong"}), encoding="utf-8")
        with self.assertRaises(LiveCaptureDisabled):
            adapter.read_delta(None)
        self.assertEqual([], activity)

    def test_capture_runtime_exposes_no_external_action_method(self):
        prohibited = {"send", "reply", "forward", "book", "schedule", "mutate_connector", "activate_polling"}
        for runtime_type in (CaptureEngine, CaptureTriage, CaptureProposer, CaptureQueueWriter):
            self.assertTrue(prohibited.isdisjoint(set(dir(runtime_type))))

    def test_cursor_rejects_backward_checkpoint(self):
        engine, adapter = self.engine(envelope("one"), cursor="20")
        engine.run_once(adapter)
        adapter.batch = DeltaBatch(next_cursor="19", envelopes=())
        with self.assertRaises(CaptureError):
            engine.run_once(adapter)
        self.assertEqual("20", self.storage.cursor(adapter.provider_key))


class MappingAndTriageTests(CaptureTestCase):
    def test_exact_global_client_unknown_ambiguous_and_conflicting_mapping(self):
        self.assertEqual("client-a", self.registry.resolve_capture_identity(sender="block3-client-a@example.invalid").client_scope)
        self.assertEqual("global", self.registry.resolve_capture_identity(sender="block3-internal@example.invalid").client_scope)
        self.assertEqual("unresolved", self.registry.resolve_capture_identity(sender="unknown@example.invalid").state)
        data = capture_registry_data()
        shared = data["scopes"]["client-a"]["capture_identities"][0]
        data["scopes"]["client-b"]["capture_identities"].append(shared)
        ambiguous = make_registry(data)
        self.assertEqual("ambiguous", ambiguous.resolve_capture_identity(sender="block3-client-a@example.invalid").state)
        conflict = self.registry.resolve_capture_identity(sender="block3-client-a@example.invalid", thread_id="block3-thread-b")
        self.assertEqual("conflicting", conflict.state)

    def test_rules_handle_noise_client_internal_and_unknown(self):
        records = (
            envelope("noise", subject="Weekly newsletter unsubscribe"),
            envelope("client"),
            envelope("internal", sender="block3-internal@example.invalid", thread="block3-thread-global"),
            envelope("unknown", sender="unknown@example.invalid", thread="block3-unknown"),
        )
        engine, adapter = self.engine(*records)
        engine.run_once(adapter)
        triage = CaptureTriage(self.storage)
        self.assertEqual("discard", triage.triage(records[0].record_id).route)
        self.assertEqual("client", triage.triage(records[1].record_id).route)
        self.assertEqual("internal_global", triage.triage(records[2].record_id).route)
        self.assertEqual("unresolved_identity", triage.triage(records[3].record_id).route)

    def test_only_ambiguous_survivor_reaches_metadata_only_stub(self):
        record = envelope(
            "ambiguous",
            sender="unknown@example.invalid",
            thread="block3-unknown",
            headers={"ambiguous_candidate": True},
        )
        engine, adapter = self.engine(record)
        engine.run_once(adapter)
        classifier = LocalDeterministicClassifier(True)
        decision = CaptureTriage(self.storage).triage(record.record_id, classifier=classifier)
        self.assertEqual("survivor_unresolved", decision.route)
        self.assertEqual(1, len(classifier.invocations))
        payload = classifier.invocations[0]
        self.assertEqual({"record_id", "timestamp", "source_type", "subject_classification", "header_flags"}, set(payload))
        serialized = json.dumps(payload)
        for forbidden in ("body", "attachment", "brain", "thread_text", "sender"):
            self.assertNotIn(forbidden, serialized.lower())


class ProjectionTests(CaptureTestCase):
    def projected(self) -> CaptureMetadataProjection:
        return CaptureMetadataProjection(
            record_id="cap-" + "a" * 24,
            reference_path="capture:client-a:cap-" + "a" * 24,
            client_scope="client-a",
            linked_item_id="AOS-2026-9999",
            subject_classification="business_message",
            timestamp="2026-07-15T12:00:00Z",
            source_type="gmail_fixture",
            triage_state="triaged",
            proposal_state="human_review",
        )

    def test_typed_projection_rejects_every_unapproved_field(self):
        value = self.projected().to_dict()
        for field in ("body", "body_preview", "thread_text", "attachments", "sender", "raw_headers", "account_id"):
            with self.assertRaises(CaptureError):
                CaptureMetadataProjection.from_mapping({**value, field: BODY_SENTINEL})

    def test_search_projection_uses_existing_db_with_empty_body(self):
        row = self.projected()
        self.storage.append_derived("client-a", "metadata", row.to_dict())
        raw = self.storage.scope_dir("client-a") / "raw" / "evidence.jsonl"
        self.storage._append_json(raw, {"record_id": row.record_id, "body": BODY_SENTINEL, "thread_text": THREAD_SENTINEL, "attachments": [ATTACHMENT_SENTINEL]})
        db = self.repo / "search" / "os_index.db"
        result = aos_indexer.scan(
            db,
            roots=[self.repo / "empty"],
            registry=self.registry,
            capture_runtime_root=self.storage.root,
        )
        self.assertEqual("success", result["status"])
        connection = sqlite3.connect(db)
        values = connection.execute("SELECT path, title, snippet, body, source, client_scope FROM documents WHERE source='capture_metadata'").fetchall()
        dump = json.dumps(values)
        connection.close()
        self.assertEqual(1, len(values))
        self.assertEqual("", values[0][3])
        for sentinel in (BODY_SENTINEL, THREAD_SENTINEL, ATTACHMENT_SENTINEL):
            self.assertNotIn(sentinel, dump)
        result_a = aos_indexer.search("business_message", source="capture_metadata", client_scope="client-a", db_path=db, registry=self.registry)
        result_b = aos_indexer.search("business_message", source="capture_metadata", client_scope="client-b", db_path=db, registry=self.registry)
        self.assertEqual(1, result_a["count"])
        self.assertEqual(0, result_b["count"])
        self.assertNotIn("body", json.dumps(result_a).lower())

    def test_graph_projection_is_metadata_only_and_scope_filtered(self):
        row = self.projected()
        graph_root = self.repo / "graphify"
        service = BusinessBrainGraphService(graphify_root=graph_root, vault_root=self.repo / "vault", registry=self.registry)
        result = service.publish_capture_metadata([row])
        self.assertTrue(result["metadata_only"])
        graph_path = graph_root / "document_graphs" / "ttros-business-brain" / "published" / "capture_evidence.graph.json"
        text = graph_path.read_text(encoding="utf-8")
        for forbidden in ("body", "body_preview", "thread_text", "attachments", "sender", BODY_SENTINEL, THREAD_SENTINEL, ATTACHMENT_SENTINEL):
            self.assertNotIn(forbidden, text)
        self.assertEqual(1, len(service.query_capture_targets("business", client_scope="client-a")["targets"]))
        self.assertEqual(0, len(service.query_capture_targets("business", client_scope="client-b")["targets"]))

    def test_capture_runtime_is_excluded_from_ordinary_file_indexing(self):
        raw = self.storage.scope_dir("client-a") / "raw" / "records.jsonl"
        self.storage._append_json(raw, {"body": BODY_SENTINEL})
        self.assertTrue(aos_indexer.is_excluded(raw, root=self.repo))
        self.assertIsNone(aos_indexer.document_from_path(raw, registry=self.registry))


class Stage3AndQueueTests(CaptureTestCase):
    def setUp(self):
        super().setUp()
        self.queue_writer = self.prepare_queue()
        self.vault = self.repo / "vault"
        write_note(self.vault / "memory" / "client-a.md", "client-a-note", "Client A", "Permitted fixture context")
        write_note(self.vault / "memory" / "client-b.md", "client-b-note", "Client B", "Other client context")
        self.brain_opens = []
        self.brain_loader = ScopedBrainLoader(
            registry=self.registry,
            vault_root=self.vault,
            opener=lambda path: self.brain_opens.append(path.name) or path.read_text(encoding="utf-8"),
        )

    def known_record(self) -> tuple[CaptureEnvelope, object]:
        record = envelope("proposal", subject="Approved - go ahead")
        engine, adapter = self.engine(record)
        engine.run_once(adapter)
        self.storage.append_fixture_evidence(
            client_scope="client-a",
            record_id=record.record_id,
            body=f"Approved as evidence only {BODY_SENTINEL}",
            thread_text=THREAD_SENTINEL,
            attachments=[ATTACHMENT_SENTINEL],
        )
        return record, CaptureTriage(self.storage).triage(record.record_id)

    def proposer(self, opens: list[str]) -> CaptureProposer:
        return CaptureProposer(
            storage=self.storage,
            registry=self.registry,
            brain_loader=self.brain_loader,
            queue_writer=self.queue_writer,
            evidence_loader=lambda **kwargs: self.storage.load_fixture_evidence(on_open=lambda kind, scope: opens.append(f"{kind}:{scope}"), **kwargs),
            search_selector=lambda **kwargs: opens.append(f"search:{kwargs['client_scope']}") or {"groups": {"memory": [{"path": "business_brain:memory/client-a.md"}]}},
            graph_selector=lambda **kwargs: opens.append(f"graph:{kwargs['client_scope']}") or {"targets": [{"path": "business_brain:memory/client-a.md"}]},
        )

    def test_scope_before_evidence_brain_search_graph_and_safe_human_review(self):
        record, decision = self.known_record()
        opens = []
        result = self.proposer(opens).propose(decision, brain_pointers=["business_brain:memory/client-a.md"], query="fixture")
        self.assertEqual("human_review", result["status"])
        self.assertEqual(["evidence:client-a", "search:client-a", "graph:client-a"], opens)
        self.assertEqual(["client-a.md"], self.brain_opens)
        item = result["item"]
        self.assertFalse(item["capture_proposal"]["external_actions_allowed"])
        self.assertEqual("liam_review_required", item["capture_proposal"]["communications_fact_promotion"])
        serialized = json.dumps(item)
        for sentinel in (BODY_SENTINEL, THREAD_SENTINEL, ATTACHMENT_SENTINEL):
            self.assertNotIn(sentinel, serialized)
        self.assertEqual("used", item["brain_context_status"])
        token_rows = [json.loads(line) for line in (self.repo / "queue/token_ledger.jsonl").read_text().splitlines()]
        self.assertEqual([row["invocation_id"] for row in token_rows], item["capture_proposal"]["token_references"])
        schema = json.loads((ROOT / "queue/schemas/work_item.schema.json").read_text(encoding="utf-8"))
        receipt_schema = json.loads((ROOT / "queue/schemas/receipt.schema.json").read_text(encoding="utf-8"))
        resolver = jsonschema.RefResolver.from_schema(schema, store={receipt_schema["$id"]: receipt_schema})
        jsonschema.Draft202012Validator(schema, resolver=resolver).validate(item)

    def test_unknown_scope_reaches_needs_input_with_no_content_open(self):
        record = envelope("unknown", sender="unknown@example.invalid", thread="block3-unknown", headers={"ambiguous_candidate": True})
        engine, adapter = self.engine(record)
        engine.run_once(adapter)
        classifier = LocalDeterministicClassifier(True)
        decision = CaptureTriage(self.storage).triage(record.record_id, classifier=classifier)
        opens = []
        proposer = CaptureProposer(
            storage=self.storage,
            registry=self.registry,
            brain_loader=None,
            queue_writer=self.queue_writer,
            evidence_loader=lambda **kwargs: opens.append("evidence") or {},
            search_selector=lambda **kwargs: opens.append("search") or {},
            graph_selector=lambda **kwargs: opens.append("graph") or {},
        )
        result = proposer.propose(decision)
        self.assertEqual("needs_input", result["status"])
        self.assertFalse(result["content_opened"])
        self.assertEqual([], opens)
        self.assertEqual([], self.brain_opens)
        token_rows = [json.loads(line) for line in (self.repo / "queue/token_ledger.jsonl").read_text().splitlines()]
        self.assertEqual({STAGE2_EVENT, STAGE3_EVENT}, {row["event"] for row in token_rows})
        stage2 = next(row for row in token_rows if row["event"] == STAGE2_EVENT)
        self.assertEqual("no-agent-invocation", stage2["model_confirmed"])
        self.assertEqual({"input": 0, "output": 0}, stage2["token_usage"]["totals"])
        self.assertEqual([], stage2["token_usage"]["unavailable"])
        self.assertEqual([row["invocation_id"] for row in token_rows], result["item"]["capture_proposal"]["token_references"])

    def test_live_needs_input_proposal_is_metadata_only_and_not_marked_fixture(self):
        record = envelope("live-unknown", sender="unknown@example.invalid", thread="live-thread")
        engine, adapter = self.engine(record)
        engine.run_once(adapter)
        decision = CaptureTriage(self.storage).triage(record.record_id)
        writer = CaptureQueueWriter(self.repo, capture_mode="live")
        result = CaptureProposer(
            storage=self.storage,
            registry=self.registry,
            brain_loader=None,
            queue_writer=writer,
            evidence_loader=lambda **_kwargs: self.fail("live needs_input opened content"),
        ).propose_needs_input(decision, intent="scope_resolution_required")
        proposal = result["item"]["capture_proposal"]
        self.assertEqual("phase-6b-live", proposal["fixture_marker"])
        self.assertNotIn("source_fixture_ids", proposal)
        self.assertFalse(result["content_opened"])
        serialized = json.dumps(result["item"])
        self.assertNotIn(record.message_id, serialized)
        self.assertNotIn(record.thread_id, serialized)
        schema = json.loads((ROOT / "queue/schemas/work_item.schema.json").read_text(encoding="utf-8"))
        receipt_schema = json.loads((ROOT / "queue/schemas/receipt.schema.json").read_text(encoding="utf-8"))
        resolver = jsonschema.RefResolver.from_schema(schema, store={receipt_schema["$id"]: receipt_schema})
        jsonschema.Draft202012Validator(schema, resolver=resolver).validate(result["item"])

    def test_conflicting_identity_reaches_needs_input_before_any_open(self):
        record = envelope("conflict", sender="block3-client-a@example.invalid", thread="block3-thread-b")
        engine, adapter = self.engine(record)
        engine.run_once(adapter)
        decision = CaptureTriage(self.storage).triage(record.record_id)
        self.assertEqual("conflicting", decision.route)
        opens = []
        proposer = CaptureProposer(
            storage=self.storage,
            registry=self.registry,
            brain_loader=None,
            queue_writer=self.queue_writer,
            evidence_loader=lambda **kwargs: opens.append("evidence") or {},
            search_selector=lambda **kwargs: opens.append("search") or {},
            graph_selector=lambda **kwargs: opens.append("graph") or {},
        )
        result = proposer.propose(decision)
        self.assertEqual("needs_input", result["status"])
        self.assertEqual([], opens)

    def test_cross_client_evidence_is_refused_before_open(self):
        record, decision = self.known_record()
        wrong = copy.copy(decision)
        object.__setattr__(wrong, "client_scope", "client-b")
        opens = []
        with self.assertRaises(PermissionError):
            self.proposer(opens).propose(wrong, brain_pointers=["business_brain:memory/client-b.md"])
        self.assertEqual([], opens)
        self.assertEqual([], self.brain_opens)

    def test_repeated_proposer_execution_is_queue_and_ledger_idempotent(self):
        _record, decision = self.known_record()
        proposer = self.proposer([])
        first = proposer.propose(decision, brain_pointers=["business_brain:memory/client-a.md"])
        second = proposer.propose(decision, brain_pointers=["business_brain:memory/client-a.md"])
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        items = [json.loads(line) for line in (self.repo / "queue/work_items.jsonl").read_text().splitlines()]
        self.assertEqual(1, len(items))
        self.assertEqual(1, len((self.repo / "queue/run_ledger.jsonl").read_text().splitlines()))
        self.assertEqual(1, len((self.repo / "queue/token_ledger.jsonl").read_text().splitlines()))

    def test_two_client_thread_brain_search_graph_no_open_boundaries(self):
        record, decision = self.known_record()
        opens = []
        result = self.proposer(opens).propose(decision, brain_pointers=["business_brain:memory/client-a.md"])
        self.assertEqual("human_review", result["status"])
        with self.assertRaises(PermissionError):
            self.storage.load_fixture_evidence(
                client_scope="client-b",
                reference=f"capture:client-b:{record.record_id}",
                record_id=record.record_id,
                on_open=lambda kind, scope: opens.append("cross-open"),
            )
        with self.assertRaises(PermissionError):
            self.registry.validate_brain_pointer("client-a", "business_brain:memory/client-b.md")
        self.assertNotIn("cross-open", opens)


if __name__ == "__main__":
    unittest.main()
