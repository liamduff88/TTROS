#!/usr/bin/env python3
"""David-only Hermes ``pre_tool_call`` hook: close the B7 answer-key leak.

Confirmed leak (2026-09-07, ``scripts/b7_contamination_map_and_clean_subset.md``):
David's generic, unrestricted native tools (``search_files``, ``read_file``,
``execute_code``) and the generic ``session_search`` tool reached the B7
capability-harness question/fact-list document, the frozen scorer source, its
generated pass outputs, and prior pass records -- 16 of 125 traced Step 3/5
question-records were contaminated this way. The four scoped
``mcp__brain__{search_calls,open_call,open_note,search_history}`` Business
Brain depth tools are architecturally vault-scoped
(``tools/brain_memory.py::_target`` resolves and bounds every read to
``VAULT_ROOT``) and were confirmed, across all 125 traced sessions, never to
return a ``docs/ttros`` or ``scripts`` path -- they are not touched by
anything in this file.

Deliberately a SEPARATE script from ``hooks/runtime_guard.py``, not an
addition to it: ``runtime_guard.py`` is the shared ``pre_tool_call`` hook for
the orchestrator and four department profiles (aos-delivery/aos-marketing/
aos-ops/aos-revenue) today. Adding a David-only, B7-specific rule to that
shared file would silently change behavior for those five unrelated profiles
too -- the wrong blast radius for a narrowly-scoped fix, and outside this
task's authorized surface. This file is wired only into
``~/.hermes/profiles/david/config.yaml``'s own ``hooks.pre_tool_call``, so it
can never fire for any other profile.

Known, documented limit (see the mechanical-repair report): this hook sees
only a tool call's own input, before the call runs, so it can block a call
that *names* a forbidden path but cannot block a path-free content search
(e.g. ``search_files(pattern="ICP-A|System Buyers")``) whose *result* happens
to include the harness doc's own prose. Closing that residual class would
need inspecting tool *output*, a materially larger mechanism this narrow step
does not build. ``search_files``/``read_file``/``execute_code`` are therefore
blocked outright below (they have no confirmed legitimate use in any of the
125 traced sessions and are not on the task's preserved-access list), which
closes both the path-read vector and the content-search vector completely
for those three tools specifically -- narrower in blast radius than removing
a whole tool class from every profile, because it only ever runs for David.

Revisit: if a legitimate David use for search_files/read_file/execute_code/
session_search is ever identified, or if the four brain depth tools' path
scoping changes. · Added 2026-09-07.

Run-scoping (2026-09-08, zero-model cleanup pass, scripts/b7_cleanup_pass_report.md):
this hook now activates ONLY for an actual B7 harness/test run, not for normal
David use. Gate: ``TTROS_BRAIN_ROOT`` in the hook process's own environment.
That variable is set in exactly three places in this repo -- the ``env = dict
(os.environ); env["TTROS_BRAIN_ROOT"] = str(WORK_VAULT)`` block in
``scripts/step3_b7_harness.py``, ``scripts/step5_b7_growth_harness.py``, and
``scripts/step6_b7_tools_harness.py`` -- immediately before each one's
``subprocess.run([HERMES_BIN, "-p", "david", ...], env=env, ...)`` call. No
normal David invocation path (dashboard backend, gateway, direct CLI) sets it;
it is read nowhere except ``tools/brain_memory.py`` (to point at the B7 work
vault instead of the real vault). A child process (Hermes, and the hooks it
spawns for a pre_tool_call check) inherits its parent's environment, so this
hook sees the same variable David's own vault-resolution code sees -- the
existing signal already used to distinguish a B7 pass from ordinary use,
reused here rather than inventing a new permission framework. This is the
same read-os-environ-in-a-hook pattern already used by
``hooks/context_assembler_hook.py`` (``AOS_OPERATOR_CONSULTATION``,
``TTROS_NATIVE_CONTEXT_PLUGIN_REGISTERED``).

Revisit: if a B7 harness script ever invokes David without setting
TTROS_BRAIN_ROOT, or if TTROS_BRAIN_ROOT is ever set for a non-B7 purpose. ·
Added 2026-09-08.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

# Tools blocked outright for David: no confirmed legitimate use in any of the
# 125 traced B7 sessions, not on the task's preserved-access list (Business
# Brain, transcript corpus, INDEX/MANIFEST, search_calls, open_call,
# open_note, legitimate search_history), and each is a confirmed leak
# mechanism (search_files/read_file/execute_code: direct/incidental
# answer-key exposure; session_search: cross-session answer leakage, distinct
# from its vault-scoped Step 6 replacement mcp__brain__search_history).
#
# Re-derived 2026-09-08 (STEP U, post-Hermes-upgrade tool-registry review):
# David's "terminal" toolset (tools "terminal" and, as of the v0.21.1
# registry, "process_manage" -- renamed from "process") can run an arbitrary
# shell command (e.g. `cat scripts/step3_b7_harness.py`) and was NOT in this
# set. Confirmed live: with TTROS_BRAIN_ROOT set (an active B7 run), a
# terminal call naming a blocked path passed through unblocked before this
# fix -- the same path/content leak this hook exists to close, just reached
# through an un-named tool instead of read_file/search_files. The
# defense-in-depth regex below does not catch this case either: it anchors
# on "scripts" appearing at the start of a value or right after "/", which a
# shell command string breaks (the path is preceded by a command name and a
# space, e.g. "cat scripts/...", not by "/" or start-of-string).
BLOCKED_TOOL_NAMES = {"search_files", "read_file", "execute_code", "session_search", "terminal", "process_manage"}

# Defense-in-depth path/name block, kept even though the tool-name block above
# already covers every confirmed reachability route: if a future tool (or a
# native alias of one of the names above) is ever added without updating this
# file, a call that literally names one of these paths is still caught.
TEST_MATERIAL_PATH_PATTERNS = (
    r"(?:^|/)docs/ttros(?:/|$)",
    r"(?:^|/)scripts(?:/|$)",
    r"(?:^|/)ttros_backups/[^/]*(?:harness|capability_harness|b7)[^/]*",
)


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


def _b7_run_active() -> bool:
    return bool(os.environ.get("TTROS_BRAIN_ROOT", "").strip())


def evaluate(payload: dict[str, Any]) -> dict[str, str]:
    if not _b7_run_active():
        return {}
    tool_name = str(payload.get("tool_name") or "").strip()
    if tool_name.lower() in BLOCKED_TOOL_NAMES:
        return _block(
            "b7-leak hook (David-only) blocked a call to "
            f"'{tool_name}': no confirmed legitimate use and a confirmed "
            "answer-key/cross-session leak history"
        )
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    normalized_values = [value.replace("\\", "/") for value in _strings(tool_input)]
    if any(
        re.search(pattern, value, re.IGNORECASE)
        for pattern in TEST_MATERIAL_PATH_PATTERNS
        for value in normalized_values
    ):
        return _block(
            "b7-leak hook (David-only) blocked access to B7 harness/scorer/"
            "answer-key test material"
        )
    return {}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        print(json.dumps(_block("b7-leak hook received an invalid Hermes hook payload")))
        return 0
    print(json.dumps(evaluate(payload if isinstance(payload, dict) else {})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
