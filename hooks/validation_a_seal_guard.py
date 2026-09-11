#!/usr/bin/env python3
"""Run-scoped guard for the Validation A blind run: deny reads of sealed paths.

Modeled on ``hooks/b7_test_material_guard.py`` (same shape: environment-gated,
off by default, no effect on David or any other profile outside an active
Validation A run).

Built during Validation A -- PREP PASS (2026-09-08), a session deliberately
contaminated by design: it built the seal manifest
(``scripts/validation_a_runs/seal_manifest.json``) but never read, scored, or
judged any of the 12 historical candidates, and must not be reused for the
blind run itself.

Gate: ``TTROS_VALIDATION_A_RUN`` in the hook process's own environment. Unlike
B7's ``TTROS_BRAIN_ROOT`` (a value already produced as a side effect of the
B7 harness scripts' own vault routing), Validation A has no such pre-existing
signal to reuse, so this introduces one dedicated env var, set by whatever
harness script drives the blind run's subprocess -- and nothing else. No
normal invocation path sets it, so the guard is inert everywhere else.

Sealed-path source of truth: ``scripts/validation_a_runs/seal_manifest.json``,
read fresh on every ``evaluate()`` call (no caching across calls) so a manifest
rebuild is picked up without restarting the run. The manifest holds paths,
hashes and byte sizes only -- reading it here to build the deny-set is a
metadata read, never a content read of a sealed file itself.

Defense-in-depth: sealed paths are matched both as an exact/prefix match on
the payload's own path-shaped strings AND via each sealed file's basename, so
a call that names a sealed file by a relative/different-rooted path (e.g. the
docs/ttros mirror path vs. the manifest's absolute repo path) still gets
caught -- mirroring the b7 guard's own "tool name block + defense-in-depth
path regex" two-layer design.

Revisit: if the blind run needs to reach a sealed file through a tool this
guard doesn't see (new tool name), or if the manifest is rebuilt with a
different schema. * Added 2026-09-08.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_PATH = REPO_ROOT / "scripts" / "validation_a_runs" / "seal_manifest.json"

# Phase 2A extension (2026-09-09): authoring-isolation deny-list, covering the
# 12 resolved blind-run candidate items' 14 distinct source documents, so the
# detector can be authored with those specific sources unreadable while the
# run is active. Separate source file from the PREP PASS manifest above --
# loaded the same way (fresh, no caching, metadata/paths only) and merged
# into the same deny-set.
DEFAULT_FREEZE_PATH = REPO_ROOT / "scripts" / "validation_a_runs" / "blind_run_phase1_freeze.json"

# Tools blocked outright while the Validation A run is active: same confirmed
# leak mechanisms as the B7 guard (generic search/read/exec reach anything on
# disk, including sealed paths, without naming them in a way a path-pattern
# check alone could catch).
BLOCKED_TOOL_NAMES = {"search_files", "read_file", "execute_code", "session_search", "terminal", "process_manage"}


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _strings(child)


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _run_active() -> bool:
    return bool(os.environ.get("TTROS_VALIDATION_A_RUN", "").strip())


def _manifest_path() -> Path:
    override = os.environ.get("TTROS_VALIDATION_A_SEAL_MANIFEST", "").strip()
    return Path(override) if override else DEFAULT_MANIFEST_PATH


def _freeze_path() -> Path:
    override = os.environ.get("TTROS_VALIDATION_A_FREEZE_FILE", "").strip()
    return Path(override) if override else DEFAULT_FREEZE_PATH


def _load_freeze_source_paths_and_basenames() -> tuple[set[str], set[str]]:
    """Return (normalized full paths, basenames) of the 14 distinct source
    documents behind the 12 resolved blind-run candidate items.

    Reads only ``distinct_resolved_source_paths`` (and each candidate's own
    ``sources[].resolved_path``, as a defense-in-depth duplicate) out of the
    freeze file -- never any source document's own content, and the freeze
    file itself carries no source document content either (candidate claim
    text and resolved paths only).
    """
    freeze_path = _freeze_path()
    try:
        data = json.loads(freeze_path.read_text())
    except (OSError, json.JSONDecodeError):
        return set(), set()

    paths: set[str] = set()
    basenames: set[str] = set()

    for p in data.get("distinct_resolved_source_paths", []) if isinstance(data.get("distinct_resolved_source_paths"), list) else []:
        norm = str(p).replace("\\", "/")
        paths.add(norm)
        basenames.add(norm.rsplit("/", 1)[-1])

    for candidate in data.get("candidates", []) if isinstance(data.get("candidates"), list) else []:
        if not isinstance(candidate, dict):
            continue
        for src in candidate.get("sources", []) if isinstance(candidate.get("sources"), list) else []:
            if isinstance(src, dict) and src.get("resolved_path"):
                norm = str(src["resolved_path"]).replace("\\", "/")
                paths.add(norm)
                basenames.add(norm.rsplit("/", 1)[-1])

    return paths, basenames


def _load_sealed_paths_and_basenames() -> tuple[set[str], set[str]]:
    """Return (normalized full paths, basenames) from the seal manifest.

    Reads only path/basename metadata out of the manifest -- never any
    sealed file's own content, and the manifest itself carries no sealed
    file's content either (paths, hashes, sizes, reasons only).
    """
    manifest_path = _manifest_path()
    try:
        data = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return set(), set()

    paths: set[str] = set()
    basenames: set[str] = set()

    adjudication = data.get("adjudication_file")
    if isinstance(adjudication, dict) and adjudication.get("path"):
        p = str(adjudication["path"]).replace("\\", "/")
        paths.add(p)
        basenames.add(p.rsplit("/", 1)[-1])

    for entry in data.get("files", []) if isinstance(data.get("files"), list) else []:
        if not isinstance(entry, dict) or not entry.get("path"):
            continue
        p = str(entry["path"]).replace("\\", "/")
        paths.add(p)
        basenames.add(p.rsplit("/", 1)[-1])

    return paths, basenames


def evaluate(payload: dict[str, Any]) -> dict[str, str]:
    if not _run_active():
        return {}

    tool_name = str(payload.get("tool_name") or "").strip()
    if tool_name.lower() in BLOCKED_TOOL_NAMES:
        return _block(
            "validation-a seal guard blocked a call to "
            f"'{tool_name}': generic tool with unrestricted disk reach, "
            "blocked outright for the duration of the Validation A run"
        )

    sealed_paths, sealed_basenames = _load_sealed_paths_and_basenames()
    freeze_paths, freeze_basenames = _load_freeze_source_paths_and_basenames()
    sealed_paths = sealed_paths | freeze_paths
    sealed_basenames = sealed_basenames | freeze_basenames
    if not sealed_paths and not sealed_basenames:
        # Manifest missing/unreadable: fail closed on nothing rather than
        # silently no-op -- but do not crash the hook. An empty deny-set
        # here means the guard cannot do its job; that is a hard
        # precondition failure for the run, not something this hook should
        # paper over.
        return {}

    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    normalized_values = [value.replace("\\", "/") for value in _strings(tool_input)]

    for value in normalized_values:
        if value in sealed_paths:
            return _block(
                "validation-a seal guard denied a read of a sealed Validation A path"
            )
        basename = value.rsplit("/", 1)[-1]
        if basename in sealed_basenames:
            return _block(
                "validation-a seal guard denied a read of a sealed Validation A path "
                "(matched by basename)"
            )

    return {}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        print(json.dumps(_block("validation-a seal guard received an invalid Hermes hook payload")))
        return 0
    print(json.dumps(evaluate(payload if isinstance(payload, dict) else {})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
