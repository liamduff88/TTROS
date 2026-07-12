#!/usr/bin/env python3
"""End-to-end acceptance proof for the supported Linux authority architecture.

Revisit: when queue, package recovery, launcher, or authority contracts change. · Last touched: 2026-07-11.
"""
from __future__ import annotations

import contextlib
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(os.environ.get("AOS_ROOT") or Path(__file__).resolve().parents[1]).resolve()
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from aos_paths import AuthorityError, assert_authoritative_root
import aos_queue_storage
from aos_queue_storage import QueueStorageError, durable_replace_text
import aos_orchestration

SOURCE = Path("/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live")
EXPECTED = {
    "queue/work_items.jsonl": "cd79bcfdc9ce21611fbcb85b25a667bf0c9e24b84b2933f01f7b2a8047cdcadd",
    "run_ledger.jsonl": "7c30992dc7f22aef3990551801789a8809a1fc4a5d93e4435c55172ceb55c8a6",
    "token_ledger.jsonl": "fb1ab5c459cd02f4bed255dbe01338c7931621b5ceb415fb32a1c3dba5da5a6a",
    "dashboard/frontend/src/views/Overview.jsx": "0499ab163c28f3facba1d5a14d4467f6aba698e760374799584599f47340b8df",
    "workflows/queue_artifacts/AOS-2026-0075_pass_0_dispatch_proof.md": "38934cd06f9f657c6d2d2bbbd8aac56cd095b57f740c0d77d29aa31166250c14",
}
PRESERVED_COUNTS = {"queue/receipts": 97, "results": 153, "workflows/queue_artifacts": 1, "_buildout_package": 28}
HISTORICAL = {
    "AOS-2026-0071": "0d80507557701fa8af8a9910a03105b87c2a24f13cf29622be0320e08bd81767",
    "AOS-2026-0073": "6af21e26e37fff31ee9d2416580e302c36392532be98a37bb9dd5e73810eb622",
    "AOS-2026-0074": "e03e633c2e8b7d4e0cdfbe739088ce5461f02db88f5747f47a88bea2c256968d",
    "AOS-2026-0075": "40670b793e9c184daf1d4cb720affbdf9d64936d452274e9d643ce7e0767c191",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_fingerprint() -> dict[str, str]:
    require(SOURCE.is_dir(), "frozen Windows-backed rollback source is present")
    return {name: sha(SOURCE / name) for name in EXPECTED}


def file_manifest(root: Path, relative: str) -> list[tuple[str, str]]:
    base = root / relative
    rows = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rows.append((path.relative_to(root).as_posix(), sha(path)))
    return rows


def preserved_state_fingerprint(root: Path) -> dict[str, object]:
    return {
        relative: file_manifest(root, relative)
        for relative in ("queue/receipts", "results", "workflows/queue_artifacts")
    } | {
        relative: sha(root / relative)
        for relative in ("queue/work_items.jsonl", "run_ledger.jsonl", "token_ledger.jsonl", "queue/run_ledger.jsonl", "queue/token_ledger.jsonl")
    }


def process_from_root(name: str) -> int:
    pid_file = ROOT / "logs" / "runtime" / f"{name}.pid"
    pid = int(pid_file.read_text(encoding="utf-8").strip())
    os.kill(pid, 0)
    cwd = Path(f"/proc/{pid}/cwd").resolve()
    require(cwd == ROOT or ROOT in cwd.parents, f"{name} process runs from canonical Linux root")
    return pid


def cloud_and_queue_proof(cloud: Path) -> None:
    env = {**os.environ, "AOS_ROOT": str(cloud), "PYTHONDONTWRITEBYTECODE": "1", "AOS_DISABLE_TELEMETRY": "1"}
    create = [sys.executable, str(ROOT / "tools" / "aos-queue.py"), "--root", str(cloud), "create", "--title", "cloud proof", "--owner", "codex", "--status", "inbox"]
    processes = [subprocess.Popen(create, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(32)]
    outputs = [proc.communicate(timeout=30) + (proc.returncode,) for proc in processes]
    require(all(code == 0 for _, _, code in outputs), "concurrent Linux queue writers all completed")
    lines = (cloud / "queue" / "work_items.jsonl").read_text(encoding="utf-8").splitlines()
    items = [json.loads(line) for line in lines if line.strip()]
    require(len(items) == 32 and len({item["id"] for item in items}) == 32, "32 concurrent queue writers were serialized without loss")

    parent = "AOS-2099-1000"
    (cloud / "queue" / "receipts").mkdir(parents=True, exist_ok=True)
    (cloud / "results").mkdir(parents=True, exist_ok=True)
    (cloud / "results" / "cloud-step-one.md").write_text("reviewed artifact\n", encoding="utf-8")
    (cloud / "queue" / "receipts" / "cloud-step-one.md").write_text(
        "PASS\nArtifact: results/cloud-step-one.md\nToken usage: no agent invocation\n", encoding="utf-8"
    )
    step1 = {
        "id": "AOS-2099-1001", "title": "reviewed step", "status": "done", "owner": "codex",
        "parent_id": parent, "step_index": 1, "depends_on": [],
        "receipts": [{"path": "queue/receipts/cloud-step-one.md", "created_at": "2099-01-01T00:00:00Z", "status": "done"}], "source_refs": [],
    }
    step2 = {
        "id": "AOS-2099-1002", "title": "resume step", "status": "inbox", "owner": "codex",
        "parent_id": parent, "step_index": 2, "depends_on": [step1["id"]], "receipts": [], "source_refs": [],
    }
    items.extend([step1, step2])
    durable_replace_text(cloud / "queue" / "work_items.jsonl", "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in items))
    tick = aos_orchestration.tick(cloud, allow_telegram_escalation=False)
    refreshed = aos_orchestration.load_items(cloud)
    resumed = next(row for row in refreshed if row.get("id") == step2["id"])
    require(tick["success"] and resumed["status"] == "agent_todo", "review completion resumed a disposable dependency chain")

    backend_python = ROOT / "dashboard" / "backend" / ".venv" / "bin" / "python"
    import_result = subprocess.run(
        [str(backend_python), "-c", "import main; assert main.BASE_DIR == __import__('pathlib').Path(__import__('os').environ['AOS_ROOT']).resolve(); assert main.health()['workspace'] == __import__('os').environ['AOS_ROOT']"],
        cwd=ROOT / "dashboard" / "backend", env=env, capture_output=True, text=True, timeout=30,
    )
    require(import_result.returncode == 0, "backend imports against a cloud-style configurable Linux root")
    listed = subprocess.run([sys.executable, str(ROOT / "tools" / "aos-queue.py"), "--root", str(cloud), "list", "--json"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    require(listed.returncode == 0 and "cloud proof" in listed.stdout, "queue/storage operate from cloud-style root")


def in_process_backend_proof(cloud: Path) -> None:
    env = {**os.environ, "AOS_ROOT": str(cloud), "PYTHONDONTWRITEBYTECODE": "1", "AOS_DISABLE_TELEMETRY": "1"}
    backend_python = ROOT / "dashboard" / "backend" / ".venv" / "bin" / "python"
    code = """
import asyncio, json, main
from starlette.requests import Request
async def proof():
    scope = {'type':'http','http_version':'1.1','method':'GET','scheme':'http','path':'/api/health','raw_path':b'/api/health','query_string':b'','root_path':'','headers':[], 'client':('in-process',1),'server':('in-process',80)}
    request = Request(scope)
    async def endpoint(_request):
        return main.JSONResponse(main.health())
    response = await main.linux_authority_boundary(request, endpoint)
    assert response.status_code == 200
    assert json.loads(response.body)['workspace'] == __import__('os').environ['AOS_ROOT']
asyncio.run(proof())
"""
    result = subprocess.run([str(backend_python), "-c", code], cwd=ROOT / "dashboard" / "backend", env=env, capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, "FastAPI health endpoint and authority middleware pass in-process ASGI proof on a cloud-style root" + (f" ({result.stderr.strip()[-500:]})" if result.returncode else ""))


def package_recovery_proof() -> None:
    result = subprocess.run(
        [
            sys.executable, "-m", "unittest", "-v",
            "_buildout_package.loader.test_aos_buildout.BuildoutLoaderTests.test_state_failure_leaves_journal_and_state_then_cleanup_recovery",
            "_buildout_package.loader.test_aos_buildout.BuildoutLoaderTests.test_package_release_requires_exact_complete_acquired_owner",
            "_buildout_package.loader.test_aos_buildout.BuildoutLoaderTests.test_package_publication_sync_failure_never_yields_canonical_lock",
        ],
        cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True, timeout=60,
    )
    require(
        result.returncode == 0 and "OK" in result.stderr + result.stdout,
        "package recovery, exact-owner release, and namespace-publication failure proofs pass",
    )


def queue_lock_integrity_proof() -> None:
    with tempfile.TemporaryDirectory(prefix="ttros-lock-owner-proof-", dir="/tmp") as tmp:
        root = Path(tmp)
        lock = root / aos_queue_storage.LOCK_RELATIVE
        try:
            with aos_queue_storage.queue_write_lock(root):
                owner = aos_queue_storage.read_lock_owner(lock)
                owner["pid"] = owner["pid"] + 1000000
                durable_replace_text(
                    lock / aos_queue_storage.OWNER_FILE,
                    json.dumps(owner, sort_keys=True) + "\n",
                )
        except QueueStorageError:
            pass
        else:
            raise AssertionError("altered complete queue owner unexpectedly released lock")
        require(lock.exists(), "matching token with altered queue owner identity cannot release the lock")

    result = subprocess.run(
        [
            sys.executable, "-m", "unittest", "-v",
            "tests.test_aos_queue.AosQueueTest.test_queue_publication_sync_failure_quarantines_canonical_and_retains_evidence",
            "tests.test_aos_queue.AosQueueTest.test_stale_quarantine_never_deletes_replacement_owner",
            "tests.test_aos_queue.AosQueueTest.test_eacces_retry_paths_are_bounded_and_honest",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    require(
        result.returncode == 0 and "OK" in result.stderr + result.stdout,
        "queue namespace failure, replacement-owner, and bounded-timeout proofs pass",
    )


def assert_no_pass_one() -> None:
    definitions = json.loads((ROOT / "_buildout_package" / "pass_definitions.json").read_text(encoding="utf-8"))
    pass_one = next(row for row in definitions["passes"] if row["number"] == 1)
    items = [json.loads(line) for line in (ROOT / "queue" / "work_items.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    require(not any(row.get("source") == pass_one["marker"] or row.get("title") == pass_one["queue"]["title"] for row in items), "no Pass 1 queue item exists by marker or package title")
    state_dir = ROOT / "_buildout_package" / "state"
    for name in ("package_state.json", "operation_journal.json", "operation_journal.closeout.json"):
        path = state_dir / name
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            require("1" not in (data.get("allocations") or {}) and data.get("pass") != 1, f"{name} contains no Pass 1 state")
    require(not (state_dir / ".operation.lock").exists(), "no active package mutation lock exists")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "in-process", "cloud"), default="live")
    args = parser.parse_args()
    require(sys.platform.startswith("linux") and os.name == "posix", "canonical runtime is Linux/POSIX")
    require(assert_authoritative_root(ROOT) == ROOT, "canonical root is on an accepted Linux-native filesystem")
    before = source_fingerprint()
    require(before == EXPECTED, "frozen source critical hashes match the migration baseline")
    source_state_before = preserved_state_fingerprint(SOURCE)
    target_state_before = preserved_state_fingerprint(ROOT)
    require(source_state_before == target_state_before, "queue history, receipts, artifacts, and run/token ledgers match the frozen source")
    for relative, count in PRESERVED_COUNTS.items():
        require(len(file_manifest(SOURCE, relative)) == count, f"preserved {relative} inventory count is {count}")
    if args.mode == "live":
        require(urllib.request.urlopen("http://127.0.0.1:8010/api/health", timeout=3).status == 200, "Linux backend listener is ready")
        process_from_root("backend")
        process_from_root("frontend")
        process_from_root("runner")

    with tempfile.TemporaryDirectory(prefix="ttros-posix-proof-", dir="/tmp") as tmp:
        target = Path(tmp) / "state" / "proof.txt"
        durable_replace_text(target, "durable\n")
        require(target.read_text(encoding="utf-8") == "durable\n", "POSIX durable replacement succeeds")

    with patch("aos_paths.os.name", "nt"), patch("aos_paths.sys.platform", "win32"):
        with contextlib.suppress(AuthorityError):
            assert_authoritative_root("C:\\AgenticOS")
            raise AssertionError("native Windows authority unexpectedly accepted")
    print("PASS: native Windows mutation fails closed")
    try:
        assert_authoritative_root("/mnt/c/AgenticOS")
    except AuthorityError:
        print("PASS: Windows-mounted mutation fails closed")
    else:
        raise AssertionError("Windows-mounted authority unexpectedly accepted")

    storage_source = (ROOT / "tools" / "aos_queue_storage.py").read_text(encoding="utf-8")
    core_source = storage_source + (ROOT / "dashboard" / "backend" / "main.py").read_text(encoding="utf-8")
    require("MoveFileExW" not in core_source and "ctypes.WinDLL" not in core_source, "retired Windows mutation API is unreachable")
    require("wsl.exe" not in (ROOT / "dashboard" / "backend" / "main.py").read_text(encoding="utf-8"), "Linux backend has no WSL executable dependency")

    with tempfile.TemporaryDirectory(prefix="ttros-cloud-proof-", dir="/tmp") as tmp:
        cloud = Path(tmp)
        cloud_and_queue_proof(cloud)
        in_process_backend_proof(cloud)
    queue_lock_integrity_proof()
    package_recovery_proof()

    queue_lines = (ROOT / "queue" / "work_items.jsonl").read_bytes().splitlines(keepends=True)
    effective = {json.loads(line)["id"]: line for line in queue_lines if line.strip()}
    require(all(hashlib.sha256(effective[item]).hexdigest() == digest for item, digest in HISTORICAL.items()), "historical queue fixture hashes remain unchanged")
    assert_no_pass_one()
    after = source_fingerprint()
    require(after == before, "old Windows-backed source remained unchanged during Linux operation")
    require(preserved_state_fingerprint(SOURCE) == source_state_before, "old source historical/runtime manifests remained unchanged")
    if args.mode == "live":
        print("FINAL OVERALL PASS: Linux-native TTROS Agentic OS authority and live cutover completed successfully")
    elif args.mode == "cloud":
        print("FINAL CLOUD PORTABILITY PASS: configurable Linux root, storage, orchestration, package recovery, and backend ASGI succeeded")
    else:
        print("FINAL LOCAL PROOF PASS: Linux authority and in-process architecture succeeded; listener/process cutover is intentionally unclaimed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
