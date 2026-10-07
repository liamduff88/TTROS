"""Stage 3 durable submit and Git closure checks on a local Brain clone.

Revisit: when the Stage 3 submit or recovery contract changes. Last touched: 2026-10-07.
"""
from __future__ import annotations

import json
import hashlib
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tools import aos_entity_index, aos_indexer, brain_git_closure, brain_memory, brain_memory_mcp, memory_exchange_import, shared_brain_confirm, shared_brain_http, shared_brain_read, shared_brain_submit


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture
def brain(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    root = tmp_path / "brain"
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    git(root, "remote", "add", "origin", str(remote))
    (root / "README.md").write_text("---\nid: test-root\ntype: index\n---\n# Brain\n")
    (root / "memory").mkdir()
    (root / "memory/company.md").write_text("---\nid: company\ntype: fact\n---\n# Company\n")
    git(root, "add", "README.md", "memory/company.md")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-m", "baseline")
    git(root, "push", "-u", "origin", "main")
    monkeypatch.setattr(brain_memory, "VAULT_ROOT", root)
    monkeypatch.setattr(shared_brain_read, "VAULT_ROOT", root)
    monkeypatch.setattr(shared_brain_read, "aos_indexer", aos_indexer)
    monkeypatch.setattr(aos_indexer, "BUSINESS_BRAIN_ROOT", root)
    monkeypatch.setattr(aos_indexer, "runtime_db_path", lambda path=None: tmp_path / "index.db")
    monkeypatch.setattr(aos_entity_index, "ensure_current", lambda: None)
    monkeypatch.setattr(brain_memory_mcp, "VAULT_ROOT", root)
    monkeypatch.setattr(brain_memory_mcp, "resolve_ordinary_knowledge_pointer", brain_memory.resolve_ordinary_knowledge_pointer)
    monkeypatch.setattr(brain_memory_mcp, "update_note_section", brain_memory.update_note_section)
    monkeypatch.setenv("TTROS_BRAIN_CLOSURE_STATE", str(tmp_path / "closure.json"))
    monkeypatch.setenv("TTROS_BRAIN_AUTOPUSH", "1")
    return root, remote


STAMP = {"authenticated_identity": "verified-test", "surface": "claude",
         "actor_class": "authorised_client", "surface_source": "address"}


def submit(key="test-key-123", **changes):
    fields = dict(type="milestone", title="Shared Brain milestone", body="A completed milestone about TTROS.",
                  source_refs=["https://example.org/evidence"], idempotency_key=key)
    fields.update(changes)
    return shared_brain_submit.submit(**fields, attribution=STAMP)


def test_submit_search_and_idempotency(brain):
    root, remote = brain
    first = submit()
    assert first["success"] and first["status"] == "unconfirmed"
    assert first["attribution"] == STAMP and first["commit"] == git(root, "rev-parse", "HEAD")
    assert first["sync_status"] == "synced" and first["index_status"] == "refreshed"
    response_text = json.dumps(first)
    assert str(root) not in response_text and "localhost" not in response_text and "127.0.0.1" not in response_text
    text = (root / first["reference"].removeprefix("business_brain:")).read_text()
    assert "status: unconfirmed" in text
    matches = shared_brain_read.search("completed milestone")["matches"]
    assert matches and matches[0]["reference"] == first["reference"], (
        aos_indexer.search("completed milestone", source="business_brain", client_scope="global"),
        shared_brain_read._indexed_target(first["reference"]))
    again = submit()
    assert again["duplicate"] and again["commit"] == first["commit"]
    assert git(root, "rev-list", "--count", "HEAD") == "2"
    assert not submit(body="Different claim")["success"]


def test_limits_refuse_without_commit(brain):
    root, _ = brain
    before = git(root, "rev-parse", "HEAD")
    bad = [dict(body="x" * 20001), dict(title="x" * 201),
           dict(source_refs=["https://example.org"] * 21),
           *[dict(source_refs=[ref]) for ref in ("/tmp/file.md", "x/../y", "C:\\tmp\\file", "file:///tmp/file")],
           dict(type="unsupported"), dict(idempotency_key="bad key")]
    for changes in bad:
        assert not submit(**changes)["success"]
        assert git(root, "rev-parse", "HEAD") == before
    assert not submit(title="http://localhost:8010")["success"]
    assert submit(key="limit-key-123", title="x" * 200, body="x" * 20000,
                  source_refs=["https://example.org/" + "x" * 280] * 20)["success"]


def test_concurrency_pending_recovery_and_divergence(brain, monkeypatch):
    root, remote = brain
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda key: submit(key=key), ("parallel-111", "parallel-222")))
    assert all(row["success"] for row in outcomes)
    assert git(root, "rev-list", "--count", "origin/main..HEAD") == "0"
    original_push = brain_git_closure.push_commit
    monkeypatch.setattr(brain_git_closure, "push_commit", lambda _root, _sha: "pending")
    pending = submit(key="pending-123")
    assert pending["success"] and pending["sync_status"] == "pending"
    assert brain_git_closure.pending_count(root) == 1
    continuity = root / "sessions/workstreams/pending-work.md"
    continuity.parent.mkdir(parents=True)
    continuity.write_text("continuity written while durable commit is pending")
    assert subprocess.run(["git", "-C", str(root), "cat-file", "-e",
                           "HEAD:sessions/workstreams/pending-work.md"], capture_output=True).returncode != 0
    monkeypatch.setattr(brain_git_closure, "push_commit", original_push)
    # The real push function is restored; the remote is still the local bare repo.
    assert brain_git_closure.sweep(root, alert=lambda _: None)["result"] == "synced"
    assert brain_git_closure.pending_count(root) == 0
    assert subprocess.run(["git", "-C", str(remote), "cat-file", "-e",
                           "main:sessions/workstreams/pending-work.md"], capture_output=True).returncode != 0
    other = root.parent / "other"
    subprocess.run(["git", "clone", "-b", "main", str(remote), str(other)], check=True, capture_output=True)
    (other / "remote.md").write_text("remote change")
    git(other, "add", "remote.md")
    git(other, "-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-m", "remote")
    git(other, "push", "origin", "main")
    alerts = []
    stopped = brain_git_closure.sweep(root, alert=alerts.append)
    assert stopped["result"] == "stopped_remote_diverged" and len(alerts) == 1
    # Still diverged on the next tick: stays stopped, does not alert again.
    assert brain_git_closure.sweep(root, alert=alerts.append)["result"] == "stopped_remote_diverged"
    assert len(alerts) == 1
    assert git(root, "rev-parse", "HEAD") != git(remote, "rev-parse", "main")


def test_sweep_ignores_continuity_only(brain):
    root, _ = brain
    before = git(root, "rev-parse", "HEAD")
    note = root / "sessions/workstreams/work-test.md"
    note.parent.mkdir(parents=True)
    note.write_text("working continuity")
    (root / "sessions/thread_david.md").write_text("thread")
    result = brain_git_closure.sweep(root, alert=lambda _: None)
    assert result == {"result": "synced", "pending_count": 0}
    assert git(root, "rev-parse", "HEAD") == before
    assert git(root, "status", "--short")


def test_push_timeout_keeps_valid_commit_and_releases_lock(brain, monkeypatch):
    root, _ = brain
    real_git = brain_git_closure.git
    def timeout_push(path, *args):
        if args and args[0] == "push":
            raise subprocess.TimeoutExpired("git push", 20)
        return real_git(path, *args)
    monkeypatch.setattr(brain_git_closure, "git", timeout_push)
    row = submit(key="timeout-key-123")
    assert row["success"] and row["sync_status"] == "pending"
    assert brain_git_closure.pending_count(root) == 1
    # A second durable transaction obtains the lock; the timed out push did not hold it.
    assert submit(key="timeout-key-456")["success"]


def test_david_write_uses_shared_closure(brain):
    root, _ = brain
    result = brain_memory_mcp.remember_brain_knowledge(
        "company", "stage3-milestone", "TTROS completed a verified milestone.",
        "verified_fact", "operator-confirmed", "stage3-test")
    assert result["success"] and result["sync_status"] == "synced"
    assert result["commit"] == git(root, "rev-parse", "origin/main")
    assert brain_git_closure.status(root)["last_write"]["attribution"]["surface"] == "david"


def test_submit_flag_and_drive_handoff(brain, monkeypatch, tmp_path):
    monkeypatch.setattr(shared_brain_http, "WRITE_ENABLED", True)
    monkeypatch.setattr(shared_brain_http, "SUBMIT_ENABLED", False)
    assert {tool.name for tool in shared_brain_http._server()._tool_manager.list_tools()} == {
        "search", "read", "entity", "checkpoint", "resume"}
    monkeypatch.setattr(shared_brain_http, "SUBMIT_ENABLED", True)
    assert "submit" in {tool.name for tool in shared_brain_http._server()._tool_manager.list_tools()}
    package = tmp_path / "handoff"
    package.mkdir()
    (package / "SUBMIT.json").write_text(json.dumps({
        "schema_version": "shared-brain-submit-v1", "operation": "submit",
        "type": "milestone", "title": "Drive handoff milestone", "body": "Finished result.",
        "source_refs": [], "idempotency_key": "drive-key-123",
    }))
    monkeypatch.setenv("TTROS_SHARED_BRAIN_SUBMIT", "1")
    result = memory_exchange_import.process_submit_package(package, brain=brain[0])
    assert result["outcome"] == "imported" and result["attribution"]["surface"] == "chatgpt"
    assert result["commit"] == git(brain[0], "rev-parse", "origin/main")


def test_legacy_importer_uses_transaction(brain, tmp_path):
    root, _ = brain
    package = tmp_path / "package"
    package.mkdir()
    filename = "historical/meeting.md"
    payload = b"---\nid: old-meeting\ntype: historical\n---\n# Meeting\nHistorical evidence.\n"
    target = package / filename
    target.parent.mkdir()
    target.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    manifest = {
        "schema_version": "2.0", "semantic_contract_version": "2.0.0",
        "reconciliation_contract_version": "2.0.0", "transport_mode": "directory-v1",
        "status": "ready_for_ttros", "package_id": "stage3-package", "batch_id": "stage3-batch",
        "batch_fingerprint_sha256": "a" * 64, "package_disposition": "evidence_only",
        "source_count": 1, "sources": [{"source_id": "SRC-001", "role": "batch_input", "title": "Meeting"}],
        "canonical_comparison": {"status": "partial"}, "has_conflicts": False,
        "requires_human_review": False, "output_count": 1,
        "package_files": [{"path": filename, "size_bytes": len(payload), "sha256": digest}],
        "outputs": [{"package_path": filename, "size_bytes": len(payload), "sha256": digest,
                     "source_ids": ["SRC-001"], "requires_human_review": False, "conflict_ids": [],
                     "operation": "historical_record", "temporal_posture": "historical",
                     "target": {"namespace": "historical", "suggested_relative_path": filename,
                                "canonical_ref": None, "expected_base_sha256": None}}],
    }
    (package / "INGEST_MANIFEST.json").write_text(json.dumps(manifest))
    refresh = lambda paths: ({"status": "success"}, {"status": "success", "coverage": [{"pointer": p} for p in paths]})
    first = memory_exchange_import.process(package, brain=root, root=tmp_path,
                                           dry_run=False, refresh=refresh)
    assert first["outcome"] == "imported" and first["sync_status"] == "synced"
    assert first["commit"] == git(root, "rev-parse", "origin/main")
    again = memory_exchange_import.process(package, brain=root, root=tmp_path,
                                           dry_run=False, refresh=refresh)
    assert again["outcome"] == "already_imported", again
    # The stamped Brain note differs from the package bytes; an edit after import is still caught.
    note = root / "sources/historical_calls/meeting.md"
    assert note.read_bytes() != payload
    note.write_text(note.read_text() + "edited\n")
    edited = memory_exchange_import.process(package, brain=root, root=tmp_path,
                                            dry_run=False, refresh=refresh)
    assert edited["outcome"] == "rejected" and "previously imported target changed" in edited["reason"]


def test_submit_write_error_does_not_leak_host_path(brain, monkeypatch):
    def fail(*_args, **_kwargs):
        raise brain_memory.BrainMemoryError(
            "fatal: Unable to create '/mnt/c/Brain/.git/index.lock': File exists.")
    monkeypatch.setattr(brain_memory, "write_transaction", fail)
    result = submit(key="leak-check-123")
    assert result == {"success": False, "error": "Brain write failed; nothing was stored"}


def test_submit_accepts_client_whitespace_the_commit_gate_refuses(brain):
    # S3-11: a real Claude body ending in a newline failed `git diff --check` and was masked.
    root, _remote = brain
    cases = {"eof-newline-1": "Finished result.\n", "hard-break-1": "Line one.  \nLine two.",
             "crlf-lines-1": "Line one.\r\nLine two.\r\n", "tab-indent-1": "List:\n \titem"}
    for key, body in cases.items():
        result = submit(key=key, body=body, title="Shared Brain milestone ")
        assert result["success"], (key, result)
        assert result["sync_status"] == "synced" and result["commit"] == git(root, "rev-parse", "origin/main")
    again = submit(key="eof-newline-1", body="Finished result.\n", title="Shared Brain milestone ")
    assert again["success"] and again["duplicate"]


def test_submit_commits_into_brain_ignored_intake_directory(brain):
    # S3-11 attempts 1-2: the live Brain ignores inbox/distilled_packets/*, so `git add`
    # refused the record ("The following paths are ignored by one of your .gitignore files").
    root, remote = brain
    (root / ".gitignore").write_text("inbox/distilled_packets/*\n!inbox/distilled_packets/.gitkeep\n")
    (root / "inbox/distilled_packets").mkdir(parents=True)
    (root / "inbox/distilled_packets/.gitkeep").write_text("\n")
    (root / "inbox/distilled_packets/raw-intake.md").write_text("---\nid: raw\ntype: note\n---\n# Raw\n")
    git(root, "add", ".gitignore", "inbox/distilled_packets/.gitkeep")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-m", "live ignore rule")
    git(root, "push", "origin", "main")
    result = submit(key="shared-brain-stage3-live-20261003", title="Shared Brain durable submit live",
                    body="Milestone reached.\n")
    assert result["success"], result
    assert result["sync_status"] == "synced" and result["commit"] == git(root, "rev-parse", "origin/main")
    relative = result["reference"].removeprefix("business_brain:")
    assert git(root, "show", "--name-only", "--format=", "HEAD").splitlines() == [relative]
    assert git(root, "ls-files", "inbox/distilled_packets/raw-intake.md") == ""
    assert submit(key="shared-brain-stage3-live-20261003", title="Shared Brain durable submit live",
                  body="Milestone reached.\n")["duplicate"]
    # Only submit force-adds: an ordinary Brain write to an ignored path is still refused.
    with pytest.raises(brain_memory.BrainMemoryError, match="ignored"):
        brain_memory.write_transaction({"inbox/distilled_packets/other.md": "---\nid: other\ntype: note\n---\n# Other\n"},
                                       source="test", session_id="ignored-path", require_absent=True)
    assert not (root / "inbox/distilled_packets/other.md").exists()


def test_submit_refuses_conflict_marker_body_without_commit(brain):
    root, _remote = brain
    head = git(root, "rev-parse", "HEAD")
    result = submit(key="conflict-mark-1", body="Heading\n=======\nText")
    assert result == {"success": False, "error": "body cannot contain Git conflict-marker lines"}
    assert git(root, "rev-parse", "HEAD") == head


def test_timer_typed_only_skips_full_ingest_packages(brain, monkeypatch, tmp_path, capsys):
    ready = tmp_path / "ready"
    (ready / "submit-package").mkdir(parents=True)
    (ready / "ingest-package").mkdir()
    (ready / "submit-package" / "SUBMIT.json").write_text(json.dumps({
        "schema_version": "shared-brain-submit-v1", "operation": "submit",
        "type": "milestone", "title": "Typed timer milestone", "body": "Finished result.",
        "source_refs": [], "idempotency_key": "timer-key-123",
    }))
    (ready / "ingest-package" / "INGEST_MANIFEST.json").write_text("{}")
    monkeypatch.setenv("TTROS_SHARED_BRAIN_SUBMIT", "1")
    monkeypatch.setattr("sys.argv", ["memory_exchange_import.py", "--ready", str(ready),
                                     "--brain", str(brain[0]), "--dry-run", "--typed-only"])
    assert memory_exchange_import.main() == 0
    output = json.loads(capsys.readouterr().out.split("\nToken usage")[0])
    assert output == [{"outcome": "validated", "operation": "submit"}]


def _live_shaped_submit(root):
    # The live Brain ignores the intake directory; continuity files are dirty, as on the host.
    (root / ".gitignore").write_text("inbox/distilled_packets/*\n!inbox/distilled_packets/.gitkeep\n")
    (root / "sessions").mkdir()
    (root / "sessions/thread_david.md").write_text("---\nid: thread-david\ntype: session\n---\n# Thread\n")
    git(root, "add", ".gitignore", "sessions/thread_david.md")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-m", "live shape")
    git(root, "push", "origin", "main")
    result = submit(key="shared-brain-stage3-live-20261003", title="Shared Brain durable submit live",
                    body="Milestone reached.")
    assert result["success"] and result["sync_status"] == "synced", result
    (root / "sessions/thread_david.md").write_text("---\nid: thread-david\ntype: session\n---\n# Thread\nDavid note.\n")
    (root / "sessions/workstreams").mkdir()
    (root / "sessions/workstreams/s311.md").write_text("continuity")
    return result


def test_confirm_flips_unconfirmed_submit_and_syncs_without_continuity(brain):
    root, remote = brain
    submitted = _live_shaped_submit(root)
    relative = submitted["reference"].removeprefix("business_brain:")
    before = (root / relative).read_text()
    continuity = {path: (root / path).read_bytes() for path in ("sessions/thread_david.md", "sessions/workstreams/s311.md")}
    result = shared_brain_confirm.confirm(submitted["record_id"])
    assert result["success"] and result["previous_status"] == "unconfirmed" and result["status"] == "confirmed", result
    assert not result["already_confirmed"] and result["sync_status"] == "synced"
    assert result["commit"] == git(root, "rev-parse", "HEAD") == git(remote, "rev-parse", "main")
    assert git(root, "show", "--name-only", "--format=", "HEAD").splitlines() == [relative]
    after = (root / relative).read_text()
    fields, _ = brain_memory.parse_frontmatter(after)
    assert fields["status"] == "confirmed" and fields["hermes_last_write"]["source"] == "shared-brain-confirm"
    # Only the status line and Hermes's provenance block change; the submitted payload is untouched.
    changed = {line for line in before.splitlines() if line not in after.splitlines()}
    assert {line for line in changed if not line.startswith("  ")} == {"status: unconfirmed"}
    assert after.split("\n---\n", 1)[1] == before.split("\n---\n", 1)[1]
    assert {path: (root / path).read_bytes() for path in continuity} == continuity
    assert git(root, "status", "--short", "sessions/thread_david.md") == "M sessions/thread_david.md"
    assert subprocess.run(["git", "-C", str(remote), "cat-file", "-e", "main:sessions/workstreams/s311.md"],
                          capture_output=True).returncode != 0
    assert str(root) not in json.dumps(result)


def test_confirm_repeat_is_idempotent(brain, capsys):
    root, _remote = brain
    submitted = _live_shaped_submit(root)
    first = shared_brain_confirm.confirm(submitted["record_id"])
    count = git(root, "rev-list", "--count", "HEAD")
    assert shared_brain_confirm.main([submitted["reference"]]) == 0
    again = json.loads(capsys.readouterr().out)
    assert again["success"] and again["already_confirmed"] and again["status"] == "confirmed"
    assert again["commit"] == first["commit"] and again["sync_status"] == "synced"
    assert git(root, "rev-list", "--count", "HEAD") == count


def test_confirm_refuses_unknown_and_unrelated_records(brain):
    root, _remote = brain
    submitted = _live_shaped_submit(root)
    relative = submitted["reference"].removeprefix("business_brain:")
    # A committed record in the intake directory that submit did not write.
    other_id = "shared-submit-" + "0" * 32
    (root / f"inbox/distilled_packets/{other_id}.md").write_text(
        f"---\nid: {other_id}\ntype: milestone\nstatus: unconfirmed\ntitle: \"Other\"\n---\n# Other\n\nBody\n")
    git(root, "add", "--force", f"inbox/distilled_packets/{other_id}.md")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-m", "unrelated")
    head = git(root, "rev-parse", "HEAD")
    for record in ("shared-submit-" + "f" * 32, "memory/company", "../memory/company", "company",
                   "shared-submit-" + "A" * 32, other_id, ""):
        result = shared_brain_confirm.confirm(record)
        assert not result["success"], (record, result)
        assert git(root, "rev-parse", "HEAD") == head
    assert shared_brain_confirm.main(["memory/company"]) == 1
    # David's direct hand edit: refused, and his bytes are left for the operator.
    hand_edited = (root / relative).read_text().replace("status: unconfirmed", "status: confirmed")
    (root / relative).write_text(hand_edited)
    assert shared_brain_confirm.confirm(submitted["record_id"])["error"].startswith("record has uncommitted changes")
    assert (root / relative).read_text() == hand_edited and git(root, "rev-parse", "HEAD") == head
    git(root, "checkout", "--", relative)
    # A committed body that no longer matches the submitted fingerprint is refused.
    tampered = (root / relative).read_text().replace("Milestone reached.", "Different claim.")
    (root / relative).write_text(tampered)
    git(root, "-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-m", "tamper", "--", relative)
    head = git(root, "rev-parse", "HEAD")
    assert "fingerprint" in shared_brain_confirm.confirm(submitted["record_id"])["error"]
    assert git(root, "rev-parse", "HEAD") == head


def test_confirm_skill_is_selected_for_the_aos_confirmation_request():
    from tools import context_assembler
    # AOS-2026-0524's worker request, as worker_context_pack builds it.
    request = "\n".join((
        "Work item AOS-2026-0524: Inspect Shared Brain record and run existing confirmation path only if unconfirmed",
        'Find the Shared Brain milestone titled "Shared Brain durable submit live" and inspect record '
        "shared-submit-4aa6ab0fb5595f52032e5d4a8dd9087b. Report current status, source references, and attribution. "
        "If and only if the record is currently unconfirmed, confirm that same record through the existing TTROS "
        "confirmation path. Do not create another durable submission, checkpoint, queue item, connector mutation, "
        "draft, send, post, publish, deployment, Git commit, or Git push.",
        "Source references: ",
    ))
    block = context_assembler._matching_workflows_block(request)
    selected = [line for line in block.content.splitlines() if line.startswith("### ")]
    assert selected[0].startswith("### 1. READ_SOURCE=submit-confirm/SKILL.md"), selected
    assert "python3 tools/shared_brain_confirm.py shared-submit-<32 hex>" in block.content
    assert "submit-confirm" not in context_assembler._matching_workflows_block("Prepare a fit call brief for Mike Knapp").content
