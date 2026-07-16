#!/usr/bin/env python3
"""Run the complete Block 3 fixture through durable local integrations.

This command uses only synthetic Gmail data, a local deterministic classifier,
an ignored fixture Brain, a disposable search/Graphify build, and the existing
live local queue/ledger paths. It never invokes a connector or external model.

Revisit: when the Block 3 fixture contract or live activation boundary changes. · Last touched: 2026-07-15.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import aos_indexer
from aos_capture import (
    CaptureEngine,
    CaptureEnvelope,
    CaptureLedgerWriter,
    CaptureProposer,
    CaptureQueueWriter,
    CaptureStorage,
    CaptureTriage,
    DeltaBatch,
    FixtureDeltaAdapter,
    LocalDeterministicClassifier,
)
from business_brain_context import ScopedBrainLoader
from business_brain_scope import ClientScopeRegistry
from dashboard.backend.business_brain_graph import BusinessBrainGraphService


BODY_SENTINEL = "BLOCK3_BODY_SENTINEL_7a9f"
THREAD_SENTINEL = "BLOCK3_THREAD_SENTINEL_83bd"
ATTACHMENT_SENTINEL = "BLOCK3_ATTACHMENT_SENTINEL_42ce"
SCOPE = "client:block-3-fixture-a"
POINTER = "business_brain:memory/block-3-fixture-a.md"


def fixture_registry(vault_note: Path) -> ClientScopeRegistry:
    data = copy.deepcopy(json.loads((ROOT / "context/client_scope_registry.json").read_text(encoding="utf-8")))
    record = data["scopes"][SCOPE]
    record["brain_pointers"] = [POINTER]
    record["search_source_identities"].append({"source": "business_brain", "paths": [POINTER]})
    record["graphify_targets"] = [{"namespace": "ttros-business-brain", "paths": [POINTER]}]
    return ClientScopeRegistry(data=data, schema_path=ROOT / "context/client_scope_registry.schema.json")


def ensure_fixture_brain(storage: CaptureStorage) -> Path:
    vault = storage.scope_dir(SCOPE) / "fixtures" / "business-brain"
    note = vault / "memory" / "block-3-fixture-a.md"
    note.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(note.parent, 0o700)
    if not note.exists():
        note.write_text(
            "---\nid: block-3-fixture-client-a\ntype: knowledge\n---\n"
            "# Block 3 fixture client A\n\nSynthetic scoped context for the dark capture proof.\n",
            encoding="utf-8",
        )
    os.chmod(note, 0o600)
    storage.enforce_permissions()
    return vault


def prepare_disposable_search(path: Path, registry: ClientScopeRegistry) -> None:
    conn = aos_indexer.connect(path)
    aos_indexer.reset_index(conn)
    aos_indexer.upsert_document(conn, {
        "path": POINTER,
        "title": "Block 3 fixture client A",
        "kind": "memory",
        "source": "business_brain",
        "source_root": "capture/runtime/scoped-fixture-brain",
        "client_scope": SCOPE,
        "mtime": 0.0,
        "tags": "block-3-fixture",
        "snippet": "Synthetic scoped context for dark capture proof.",
        "body": "Synthetic scoped context for dark capture proof.",
        "indexed_at": "2026-07-15T12:00:00Z",
        "size_bytes": 0,
    })
    conn.commit()
    conn.close()
    result = aos_indexer.search("Synthetic scoped context", source="business_brain", client_scope=SCOPE, db_path=path, registry=registry, path_only=True)
    if result["count"] != 1:
        raise RuntimeError("disposable scoped search fixture did not resolve exactly one row")


def main() -> int:
    storage = CaptureStorage()
    storage.set_control_for_fixture(kill_switch=False)
    vault = ensure_fixture_brain(storage)
    registry = fixture_registry(vault / "memory" / "block-3-fixture-a.md")
    known = CaptureEnvelope(
        provider="gmail_fixture",
        message_id="fixture-block3-known-a",
        thread_id="block3-thread-a",
        history_id="101",
        timestamp="2026-07-15T12:00:00Z",
        sender="block3-client-a@example.invalid",
        subject="Approved - go ahead with the fixture review",
        source_type="gmail_fixture",
        headers={},
    )
    unresolved = CaptureEnvelope(
        provider="gmail_fixture",
        message_id="fixture-block3-ambiguous",
        thread_id="block3-unknown-thread",
        history_id="102",
        timestamp="2026-07-15T12:01:00Z",
        sender="block3-unknown@example.invalid",
        subject="Could this require follow-up?",
        source_type="gmail_fixture",
        headers={"ambiguous_candidate": True},
    )
    adapter = FixtureDeltaAdapter(DeltaBatch(next_cursor="102", envelopes=(unresolved, known)))
    engine = CaptureEngine(storage, registry)
    first_capture = engine.run_once(adapter)
    replay_capture = engine.run_once(adapter)
    storage.append_fixture_evidence(
        client_scope=SCOPE,
        record_id=known.record_id,
        body=f"Approved is evidence only. {BODY_SENTINEL}",
        thread_text=THREAD_SENTINEL,
        attachments=[ATTACHMENT_SENTINEL],
    )
    triage = CaptureTriage(storage)
    known_decision = triage.triage(known.record_id)
    classifier = LocalDeterministicClassifier(True)
    unresolved_decision = triage.triage(unresolved.record_id, classifier=classifier)

    with tempfile.TemporaryDirectory(prefix="ttros-block3-fixture-") as temp_name:
        temp = Path(temp_name)
        search_db = temp / "os_index.db"
        prepare_disposable_search(search_db, registry)
        graph_service = BusinessBrainGraphService(graphify_root=temp / "graphify", vault_root=vault, registry=registry)
        graph_build = graph_service.build()
        brain_loader = ScopedBrainLoader(registry=registry, vault_root=vault, graph_service=graph_service, search_db_path=search_db)
        queue_writer = CaptureQueueWriter(ROOT, ledger=CaptureLedgerWriter(ROOT))
        opens = []
        proposer = CaptureProposer(
            storage=storage,
            registry=registry,
            brain_loader=brain_loader,
            queue_writer=queue_writer,
            evidence_loader=lambda **kwargs: storage.load_fixture_evidence(on_open=lambda kind, scope: opens.append(f"{kind}:{scope}"), **kwargs),
            search_selector=lambda **kwargs: aos_indexer.search(
                kwargs["query"], source="business_brain", client_scope=kwargs["client_scope"], db_path=search_db, registry=registry, path_only=True
            ),
            graph_selector=lambda **kwargs: graph_service.query_targets(kwargs["query"], client_scope=kwargs["client_scope"], registry=registry),
        )
        known_result = proposer.propose(known_decision, brain_pointers=[POINTER], query="Synthetic scoped context")
        known_replay = proposer.propose(known_decision, brain_pointers=[POINTER], query="Synthetic scoped context")
        unresolved_proposer = CaptureProposer(
            storage=storage,
            registry=registry,
            brain_loader=None,
            queue_writer=queue_writer,
            evidence_loader=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("unresolved scope opened evidence")),
            search_selector=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("unresolved scope opened search")),
            graph_selector=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("unresolved scope opened graph")),
        )
        unresolved_result = unresolved_proposer.propose(unresolved_decision)
        unresolved_replay = unresolved_proposer.propose(unresolved_decision)

    result = {
        "status": "PASS",
        "capture": {
            "cursor": first_capture["cursor"],
            "raw_count": len(storage.raw_records()),
            "replay_new_raw_count": sum(1 for row in replay_capture["records"] if row["raw_appended"]),
            "permissions": storage.permission_report(),
        },
        "triage": {
            "known_route": known_decision.route,
            "ambiguous_route": unresolved_decision.route,
            "classifier_invocations": len(classifier.invocations),
        },
        "stage3": {
            "known_item_id": known_result["item"]["id"],
            "known_status": known_result["item"]["status"],
            "known_replay_created": known_replay["created"],
            "unresolved_item_id": unresolved_result["item"]["id"],
            "unresolved_status": unresolved_result["item"]["status"],
            "unresolved_replay_created": unresolved_replay["created"],
            "known_content_open_events": opens,
            "unresolved_content_opened": unresolved_result["content_opened"],
            "brain_context_used": known_result["item"].get("brain_context_used") or [],
        },
        "graph_fixture": {"status": graph_build["status"], "published": graph_build.get("published")},
        "sentinel_hashes": {
            "body": hashlib.sha256(BODY_SENTINEL.encode()).hexdigest(),
            "thread": hashlib.sha256(THREAD_SENTINEL.encode()).hexdigest(),
            "attachment": hashlib.sha256(ATTACHMENT_SENTINEL.encode()).hexdigest(),
        },
        "external_actions": 0,
        "live_provider_calls": 0,
        "live_model_calls": 0,
        "token_usage_text": "Token usage: no agent invocation",
    }
    if result["capture"]["replay_new_raw_count"] != 0 or result["stage3"]["known_replay_created"] or result["stage3"]["unresolved_replay_created"]:
        raise RuntimeError("fixture replay was not idempotent")
    if result["stage3"]["known_status"] != "human_review" or result["stage3"]["unresolved_status"] != "needs_input":
        raise RuntimeError("fixture queue routing did not use existing Needs Me statuses")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
