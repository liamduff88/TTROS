#!/usr/bin/env python3
"""Hermes lifecycle hook for mandatory One Brain context and session journals.

`pre_llm_call` returns the assembled context. `post_llm_call` records completed
executive turns in the vault with an atomic audited transaction.

Revisit: when Hermes native plugin payloads or sticky-session identity changes. · Last touched: 2026-08-05.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


ROOT = Path("/home/liam/agentic-os-live")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# F-BRAINSCOPEIDENTITY-1 (STEP X3, 2026-09-11 -> STEP X4, 2026-09-11): dashboard/backend/
# business_brain_graph.py used to bare-import ClientScopeError, creating a second, distinct
# `business_brain_scope` module object in this process and causing its own
# `except ClientScopeError: return` to silently fail to catch an out-of-scope graph
# candidate. STEP X3 shimmed around it here by pre-aliasing the qualified module under the
# bare name. STEP X4 fixed the import at its source instead (business_brain_graph.py now
# tries the qualified module first) and proved the shim is no longer needed: both of X3's
# own offline controls (real-prompt positive, no-AOS_STEP6_WRAPPED negative) still hold with
# the shim removed. Shim deleted; see scripts/stepX4_harden_x3.md for the proof.

from tools.brain_memory import append_session_turn, write_thread
from tools.context_assembler import MARKER, assemble, assemble_source_intake_semantic_extraction
from tools.step6_cost_control import Scope, preflight


STICKY_RE = re.compile(r"(?m)^TTROS sticky session key:\s*([a-f0-9]{12,64})\s*$")
AOS_PROFILES = {"operator-lean", "aos-orchestrator", "aos-revenue", "aos-marketing", "aos-delivery", "aos-ops"}
# STEP I1 (2026-09-09), Liam-authorized narrow exception: a dedicated profile used only by
# tools/source_intake.py semantic extraction. Deliberately NOT in AOS_PROFILES (no Step 6
# accounting/fuse wrapper), NOT in THREAD_PROFILES/JOURNAL_PROFILES (no David-style thread or
# journal writes), NOT "david". See scripts/i1_source_intake_semantic_extraction_transcript.md.
SOURCE_INTAKE_SEMANTIC_PROFILE = "source-intake-semantic"
SOURCE_INTAKE_SEMANTIC_ENV_SENTINEL = "TTROS_SOURCE_INTAKE_SEMANTIC_EXTRACTION"
BRAIN_CONTEXT_PROFILES = {*AOS_PROFILES, "david", SOURCE_INTAKE_SEMANTIC_PROFILE}

# STEP T7 (2026-09-10), F-TESTCONTAMINATION-1: a David turn run with this sentinel set is a
# test/harness turn (T5/T6/T7/B7-style manual live-proof invocations), not real conversational
# continuity. Same pattern as SOURCE_INTAKE_SEMANTIC_ENV_SENTINEL. Suppressing the write is
# sufficient and closes both downstream leaks at their one shared source: a turn never written
# to sessions/*.md or thread_david.md cannot later be selected by _session_recency_block (which
# only scans existing vault session files) or surfaced by search_history (an FTS index over
# files actually on disk) -- no separate assembler-side exclusion list is needed for turns
# marked this way. Scoped to profile "david" only (this step's authorized surface); does not
# change operator-lean's or any AOS profile's journalling.
# Revisit: if a non-CLI surface needs to mark a David test turn without an env var, or if
# native `memory` tool writes during a marked turn are found to need the same gate.
DAVID_TEST_TURN_ENV_SENTINEL = "TTROS_DAVID_TEST_TURN"


# Profiles that own a rolling continuity thread. An allowlist, so a profile that merely
# echoes the delimiters can never silently acquire a thread record and displace its journal.
THREAD_PROFILES = ("david",)
# Profiles whose turns are journalled verbatim regardless of the sticky-key marker.
JOURNAL_PROFILES = ("operator-lean", "david")


THREAD_OPEN = "<<<TTROS_THREAD"
THREAD_CLOSE = "TTROS_THREAD>>>"


def _thread_marks(lines: list[str]) -> tuple[list[int], list[int]]:
    """Indices of lines that are a delimiter and nothing else.

    A delimiter mentioned inside a sentence does not count, so David can discuss
    this contract with Liam without breaking his own continuity.
    """
    opens, closes = [], []
    for index, line in enumerate(lines):
        bare = line.strip()
        if bare == THREAD_OPEN:
            opens.append(index)
        elif bare == THREAD_CLOSE:
            closes.append(index)
    return opens, closes


JOURNAL_PROMPT_MARKER = "\nOperator request:\n"


def _journal_message(profile: str, message: str) -> str:
    """What to write in the journal's Operator section.

    The model still receives the whole prompt. The journal keeps the operator's real
    request plus a note naming what was left out, instead of storing the execution
    handoff contract and the thread contract verbatim on every single turn.

    Fail safe by direction: partition takes the FIRST marker, so if a contract ever
    contains the marker itself the result is less stripping, never a truncated
    operator request. If the marker is missing entirely the full message is journalled
    exactly as before. The hook cannot report a problem — Hermes swallows hook errors
    and post_llm_call is fire-and-forget (F1) — so the only honest failure mode is one
    that loses nothing and shows up in the journal size measurement.
    """
    if profile not in THREAD_PROFILES:
        return message
    _head, separator, tail = message.partition(JOURNAL_PROMPT_MARKER)
    request = tail.strip()
    if not separator or not request:
        return message
    # UTF-8 bytes, not len(): the contracts are full of em-dashes and curly quotes, so
    # character count and byte count differ and a note labelled "B" must mean bytes.
    omitted = len(message.encode("utf-8")) - len(request.encode("utf-8"))
    return (f"[consultation scaffolding omitted from this journal, {omitted} UTF-8 bytes: "
            "dashboard instructions, rules/david_execution_handoff.md, "
            "rules/david_thread_contract.md. The model received the full prompt.]\n\n"
            + request)


def _split_thread_block(answer: str) -> tuple[str, str, int]:
    """Return (answer shown to the operator, thread body to save, valid block count).

    Fail closed: anything but exactly one well-formed block saves nothing, leaves the
    previous thread standing, and is reported to the operator by main.py.
    """
    lines = answer.splitlines()
    opens, closes = _thread_marks(lines)
    if len(opens) == 1 and len(closes) == 1 and opens[0] < closes[0]:
        body = "\n".join(lines[opens[0] + 1:closes[0]]).strip()
        cleaned = "\n".join(lines[:opens[0]] + lines[closes[0] + 1:]).strip()
        return cleaned, body, 1
    if len(opens) == 1 and not closes:
        # Unambiguous. The contract puts the block at the very end, so everything after
        # an unclosed opener is thread content: drop it rather than show it to Liam.
        return "\n".join(lines[:opens[0]]).strip(), "", 0
    # Ambiguous shape — two blocks, a stray closer, a close before an open. We cannot
    # tell which side is answer and which is thread, so keep the prose (losing a real
    # answer is worse than showing stray notes) and remove only the delimiter lines.
    drop = set(opens + closes)
    kept = [line for index, line in enumerate(lines) if index not in drop]
    return "\n".join(kept).strip(), "", len(opens)


def _profile() -> str:
    home = Path(os.environ.get("HERMES_HOME", ""))
    return home.name if home.parent.name == "profiles" else ""


def _sticky_key(message: str, session_id: str) -> str:
    match = STICKY_RE.search(str(message or ""))
    return match.group(1) if match else session_id


def evaluate(payload: dict) -> dict:
    if (
        os.environ.get("TTROS_NATIVE_CONTEXT_PLUGIN_REGISTERED") == "1"
        and not payload.get("native_plugin")
    ):
        return {}
    event = str(payload.get("hook_event_name") or "")
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    session_id = str(payload.get("session_id") or "")
    platform = str(extra.get("platform") or "hermes")
    surface = f"hermes:{platform}"
    message = str(extra.get("user_message") or "")
    profile = _profile()
    if profile not in BRAIN_CONTEXT_PROFILES:
        return {}
    sticky = _sticky_key(message, session_id)

    if event == "pre_llm_call":
        if profile == SOURCE_INTAKE_SEMANTIC_PROFILE:
            # Fail closed: the profile alone is not activation. Only
            # tools/source_intake.py's own subprocess call sets this env
            # sentinel; ordinary chat text (even text naming this profile or
            # the sentinel string) cannot set an environment variable, so it
            # cannot activate the narrow blind-extraction path.
            if os.environ.get(SOURCE_INTAKE_SEMANTIC_ENV_SENTINEL) != "1":
                raise RuntimeError(
                    f"{SOURCE_INTAKE_SEMANTIC_PROFILE} profile requires explicit "
                    f"{SOURCE_INTAKE_SEMANTIC_ENV_SENTINEL}=1 activation"
                )
            context = assemble_source_intake_semantic_extraction(
                message,
                session_id=session_id,
                invocation_id=f"hermes-{session_id or 'session'}-{str(extra.get('turn_id') or 'turn')}",
            )
            return {"context": context.render(include_request=False)}
        if profile in AOS_PROFILES and os.environ.get("AOS_STEP6_WRAPPED") != "1":
            raise RuntimeError("Step 6 protected model runner requires the canonical accounting/fuse wrapper")
        if profile in AOS_PROFILES:
            scope_type = os.environ.get("AOS_STEP6_SCOPE_TYPE", "")
            scope_id = os.environ.get("AOS_STEP6_SCOPE_ID", "")
            preflight(Scope(scope_type, scope_id), root=ROOT)
        context = assemble(
            message,
            surface=surface,
            session_id=session_id,
            session_key=sticky,
            profile=profile,
            invocation_id=f"hermes-{session_id or 'session'}-{str(extra.get('turn_id') or 'turn')}",
        )
        return {"context": context.render(include_request=False)}

    if event == "post_llm_call":
        response = str(extra.get("assistant_response") or "")
        read_only_consultation = os.environ.get("AOS_OPERATOR_CONSULTATION") == "1"
        is_test_turn = profile == "david" and os.environ.get(DAVID_TEST_TURN_ENV_SENTINEL) == "1"
        if profile in THREAD_PROFILES:
            cleaned, thread_body, _thread_blocks = _split_thread_block(response)
        else:
            # Profiles without a thread never enter the parser at all. splitlines() +
            # "\n".join() + strip() would normalise line endings and trim whitespace even
            # when no block is present, and proof 7 requires operator-lean's journalled
            # bytes to stay identical to pre-patch. Untouched means untouched.
            cleaned, thread_body = response, ""
        if thread_body and profile in THREAD_PROFILES and not is_test_turn:
            try:
                write_thread(
                    identity=profile,
                    body=thread_body,
                    session_id=session_id or "hermes-turn",
                    source=f"session {session_id or 'unknown'}",
                )
            except Exception:
                # Hermes catches and logs hook errors and post_llm_call is a fire-and-forget
                # observer, so raising here would lose the journal silently and tell nobody.
                # main.py verifies persistence synchronously and warns the operator instead.
                pass
        # Thread-owning profiles have no stable sticky key (a consultation is a fresh CLI
        # session every turn), so journal them under the profile name. Without this the
        # journal would be one new file per turn instead of one per UTC day.
        journal_key = profile if profile in THREAD_PROFILES else sticky
        if cleaned and not read_only_consultation and not is_test_turn and (profile in JOURNAL_PROFILES or STICKY_RE.search(message)):
            append_session_turn(
                surface=surface,
                session_key=journal_key,
                session_id=session_id or "hermes-turn",
                user_message=_journal_message(profile, message),
                assistant_response=cleaned,
                token_usage="unavailable from current Hermes post_llm_call payload",
                source=f"session {session_id or 'unknown'}",
            )
        return {}
    return {}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be an object")
        result = evaluate(payload)
    except Exception as exc:
        # The scoped Hermes runtime has a matching fail-closed marker check;
        # returning no marker prevents a model call instead of degrading.
        print(json.dumps({"error": f"context assembly failed: {type(exc).__name__}"}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
