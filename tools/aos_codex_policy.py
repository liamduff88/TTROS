"""Mandatory Agentic OS policy for every Codex process launch.

Revisit: when the canonical Agentic OS root, Linux user, Codex installation,
fresh-session/compaction CLI contract, model catalog, or ``codex exec --json``
usage-event contract changes. · Last touched: 2026-10-25.
"""

from __future__ import annotations

import codecs
import os
import pwd
import json
import re
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CodexPolicyError(RuntimeError):
    """The mandatory Agentic OS Codex runtime contract is not effective."""


SANDBOX_MODE = "danger-full-access"
APPROVAL_POLICY = "never"
AUTO_COMPACT_TOKEN_LIMIT = 75_000
REASONING_EFFORT_BY_DIAL = {"light": "low", "standard": "medium", "heavy": "high"}
CODEX_MODEL = "gpt-6-sol"
SESSION_FUSE_LIMIT = 500_000
SUPPORTED_EFFORTS = ("low", "medium", "high")
COMPLEXITY_TIERS = ("simple", "medium", "complex")
TIER_BY_DIAL = {"light": "simple", "standard": "medium", "heavy": "complex"}
MODEL_ROUTES_PATH = Path("queue/model_routes.json")


def _positive_environment_integer(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise CodexPolicyError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise CodexPolicyError(f"{name} must be a positive integer")
    return value


PERMISSION_HEADER = """PERMISSION MODE — SCOPED LOCAL TASK APPROVED

Do not ask for permission during this scoped local task. Assume approval for local reads, local edits, local file creation, dependency installation, validation commands, local dev-server startup, browser preview, and screenshot capture inside the stated scope.

Do not ask before editing files inside the stated folder. Make the changes, validate, and return the compact closeout.

Stop only for real external/destructive actions."""
FRESH_SESSION_POLICY = """## Fresh-session and retained-context contract

- This invocation is a new, independently scoped ephemeral Codex session. Do not resume, inherit, or search for any previous Codex transcript or session.
- Work only from this prompt and the repository/artifact paths it names. Do not replay orchestration history.
- Keep logs, screenshots, browser evidence, and verbose test output in local artifacts; retain only compact summaries and paths in prompts and closeouts.
- Native automatic compaction may summarise retained conversation for session hygiene; it must preserve the assembled context needed to complete the task.
- The only token breaker is this session's own 500,000-token fuse (input + output). Many tool calls each re-send the whole context, so prefer few, targeted reads.
- If a clean session cannot be created, fail explicitly without doing task work."""

@dataclass(frozen=True)
class CodexRuntimeTarget:
    """Filesystem/process identity only; permission policy cannot be overridden."""

    root: Path
    executable: Path
    linux_user: str
    codex_home: Path


CODEX_TARGET = CodexRuntimeTarget(
    root=Path("/home/liam/agentic-os-live"),
    executable=Path("/home/liam/.local/npm/bin/codex"),
    linux_user="liam",
    codex_home=Path("/home/liam/.codex"),
)


def effective_linux_user() -> str:
    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except KeyError as exc:  # pragma: no cover - a broken host account database
        raise CodexPolicyError(f"effective uid {os.geteuid()} has no Linux user") from exc


def invocation_metadata(target: CodexRuntimeTarget = CODEX_TARGET) -> dict:
    return {
        "executable": str(target.executable),
        "cwd": str(target.root),
        "linux_user": effective_linux_user(),
        "effective_uid": os.geteuid(),
        "sandbox": SANDBOX_MODE,
        "sandbox_mode": SANDBOX_MODE,
        "approval_policy": APPROVAL_POLICY,
        "ask_for_approval": APPROVAL_POLICY,
        "session_mode": "fresh_ephemeral",
        "resume_allowed": False,
        "model_auto_compact_token_limit": AUTO_COMPACT_TOKEN_LIMIT,
        "token_fuse_limit": 500_000,
        "model_requested": CODEX_MODEL,
        "actual_model": CODEX_MODEL,
    }


def validate_runtime(
    requested_root: Path | str,
    target: CodexRuntimeTarget = CODEX_TARGET,
) -> dict:
    requested = Path(requested_root).resolve()
    expected = target.root.resolve()
    user = effective_linux_user()
    defects = []
    if requested != expected:
        defects.append(f"cwd must be {expected}, got {requested}")
    if user != target.linux_user:
        defects.append(f"Linux user must be {target.linux_user}, got {user}")
    if not target.executable.is_absolute() or not target.executable.is_file() or not os.access(target.executable, os.X_OK):
        defects.append(f"Codex executable is missing or not executable: {target.executable}")
    if str(expected).startswith("/mnt/"):
        defects.append(f"Windows-mounted Agentic OS roots are forbidden: {expected}")
    if defects:
        raise CodexPolicyError("Agentic OS Codex policy defect: " + "; ".join(defects))
    return invocation_metadata(target)


def build_exec_command(
    target: CodexRuntimeTarget = CODEX_TARGET,
    *,
    cost_dial: str = "standard",
    selection: dict | None = None,
) -> list[str]:
    """Return the immutable headless CLI contract.

    ``selection`` (from :func:`select_model_and_effort`) sets model and effort;
    without it the canonical dial effort and pinned model apply unchanged.
    """
    if cost_dial not in REASONING_EFFORT_BY_DIAL:
        raise CodexPolicyError(
            f"invalid cost dial {cost_dial!r}; expected light, standard, or heavy"
        )
    model, effort = CODEX_MODEL, REASONING_EFFORT_BY_DIAL[cost_dial]
    if selection is not None:
        model, effort = str(selection.get("model") or ""), str(selection.get("reasoning_effort") or "")
        if effort not in SUPPORTED_EFFORTS or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,63}", model):
            raise CodexPolicyError(f"invalid Codex model selection {model!r}/{effort!r}")
    return [
        str(target.executable),
        "--sandbox", SANDBOX_MODE,
        "--ask-for-approval", APPROVAL_POLICY,
        "-C", str(target.root),
        "--config", f"model_auto_compact_token_limit={AUTO_COMPACT_TOKEN_LIMIT}",
        "--config", f"model_reasoning_effort={effort}",
        "exec", "--model", model,
        "--ephemeral", "--skip-git-repo-check", "--json", "--color", "never", "-",
    ]


# --- Automatic model and effort selection --------------------------------
# One deterministic, zero-token classifier feeds the existing cost dial. The
# configured tier table lives in queue/model_routes.json (codex route); only
# models listed there may be launched, and that list is checked against the
# Codex CLI catalog (``codex debug models``) when it is edited, not per call.

_RISK_TERMS = re.compile(
    r"\b(?:security|credential|auth(?:entication|orization)?|secret|migrat\w*|concurren\w*|race|"
    r"deadlock|data loss|architecture|schema|ledger|fuse|refactor|multi-file|cross-cutting|"
    r"protected|rollback|lock(?:ing)?|encryption|permission)\b",
    re.IGNORECASE,
)
_SIMPLE_TERMS = re.compile(
    r"\b(?:typo|rename|one-line|single-line|read-only|status check|list|count|inspect|"
    r"report only|docs? only|comment|wording|smoke)\b",
    re.IGNORECASE,
)
_LOCAL_ACTIONS = {"local_read", "local_edit", "local_test"}


def classify_step_complexity(item: dict | None, *, attempt: int = 1) -> dict:
    """Score one bounded step as simple / medium / complex with visible reasons."""
    item = item or {}
    text = " ".join(str(item.get(key) or "") for key in ("title", "context", "definition_of_done"))
    actions = {str(value) for value in (item.get("allowed_actions") or [])}
    score = 0
    reasons: list[str] = []
    size = str(item.get("size") or "").strip().casefold()
    if size == "small":
        score -= 2
        reasons.append("size=small (-2)")
    elif size == "large":
        score += 2
        reasons.append("size=large (+2)")
    if actions and actions <= {"local_read"}:
        score -= 1
        reasons.append("read-only actions (-1)")
    elif actions - _LOCAL_ACTIONS:
        score += 2
        reasons.append(f"non-local actions {sorted(actions - _LOCAL_ACTIONS)} (+2)")
    if len(text) < 500:
        score -= 1
        reasons.append(f"short brief {len(text)} chars (-1)")
    elif len(text) > 2500:
        score += 1
        reasons.append(f"long brief {len(text)} chars (+1)")
    risk = sorted({match.lower() for match in _RISK_TERMS.findall(text)})
    if risk:
        score += 2
        reasons.append(f"risk terms {risk[:4]} (+2)")
        if len(risk) >= 3:
            score += 1
            reasons.append("several distinct risk signals (+1)")
    simple = sorted({match.lower() for match in _SIMPLE_TERMS.findall(text)})
    if simple and not risk:
        score -= 1
        reasons.append(f"simple terms {simple[:4]} (-1)")
    if attempt > 1:
        score += 1
        reasons.append(f"retry attempt {attempt} (+1)")
    if str(item.get("client_scope") or "global") != "global" and score < 0:
        score = 0
        reasons.append("client-scoped work floors at medium")
    tier = "simple" if score <= -2 else "complex" if score >= 2 else "medium"
    return {"tier": tier, "score": score, "reasons": reasons}


def load_codex_tiers(root: Path | None = None) -> dict:
    """Return the configured tier table from the existing queue route config.

    Fixture roots without their own route file use the repository's contract.
    """
    path = (root or CODEX_TARGET.root) / MODEL_ROUTES_PATH
    if not path.exists():
        path = Path(__file__).resolve().parents[1] / MODEL_ROUTES_PATH
    try:
        route = json.loads(path.read_text(encoding="utf-8"))["routes"]["codex"]
        table = route["codex_selection"]
        supported = set(table["supported_models"])
        tiers = {name: dict(table["tiers"][name]) for name in COMPLEXITY_TIERS}
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise CodexPolicyError(f"Codex model tiers unavailable in {MODEL_ROUTES_PATH}: {exc}") from exc
    for name, tier in tiers.items():
        if tier.get("model") not in supported or tier.get("reasoning_effort") not in SUPPORTED_EFFORTS:
            raise CodexPolicyError(f"Codex tier {name} names an unconfigured model or effort: {tier}")
    return {"tiers": tiers, "supported_models": sorted(supported), "catalog_check": table.get("catalog_check", "")}


def select_model_and_effort(
    item: dict | None,
    *,
    cost_dial: dict,
    attempt: int = 1,
    root: Path | None = None,
) -> dict:
    """Pick model + effort for one step from complexity and the cost dial.

    An explicit scoped ``budget:<dial>`` override pins the tier outright. The
    global dial shifts the classified tier: light one step down, heavy one up.
    """
    table = load_codex_tiers(root)
    value, source = str(cost_dial.get("value") or "standard"), str(cost_dial.get("source") or "")
    if value not in TIER_BY_DIAL:
        raise CodexPolicyError(f"invalid cost dial {value!r}")
    classified = classify_step_complexity(item, attempt=attempt)
    if source == "scope_override":
        tier = TIER_BY_DIAL[value]
        reason = f"operator override budget:{value} pins tier {tier}"
    else:
        index = COMPLEXITY_TIERS.index(classified["tier"]) + {"light": -1, "standard": 0, "heavy": 1}[value]
        tier = COMPLEXITY_TIERS[max(0, min(2, index))]
        shift = "" if tier == classified["tier"] else f"; {value} dial shifted {classified['tier']}->{tier}"
        reason = f"classified {classified['tier']} (score {classified['score']}: {', '.join(classified['reasons']) or 'no signals'}){shift}"
    chosen = table["tiers"][tier]
    return {
        "tier": tier,
        "model": chosen["model"],
        "reasoning_effort": chosen["reasoning_effort"],
        "reason": reason,
        "classification": classified,
        "cost_dial": {"value": value, "source": source},
        "catalog_check": table["catalog_check"],
    }


# --- Streaming per-session fuse --------------------------------------------
# codex-cli 0.164.0 ``exec --json`` emits exact usage only in turn.completed,
# once per turn, and an exec run is normally one turn. A single long turn can
# therefore exceed 500K before any exact counter exists. The monitor enforces
# the exact counter whenever one streams, and between turns stops on an
# UNVERIFIED in-flight estimate: inferred model requests x (prompt + fixed
# overhead floor). It is neither usage nor a proven lower bound -- the stream
# shows tool events, not model requests, and a stopped session records usage
# as unavailable. Cumulative tool output is deliberately not re-counted per
# request: against the 25 recorded streams with exact usage that term
# overshot the provider total up to 4.67x and stopped AOS-2026-0947 after 35s
# (scripts/codex_fuse_calibration.txt); without it the estimate ranged 0.24x
# to 1.27x of exact, so a stop can land before or after the true 500K point.
REQUEST_OVERHEAD_FLOOR_TOKENS = 12_000  # measured ~20K via `codex debug prompt-input` 2026-10-25
CHARS_PER_TOKEN_ESTIMATE = 4
ESTIMATE_BASIS = "in_flight_estimate_unverified"
TOOL_ITEM_TYPES = frozenset({"command_execution", "file_change"})


class StreamingSessionFuse:
    """Watch one Codex JSONL stream and say when its own 500K fuse is reached."""

    def __init__(self, prompt: str, *, limit: int = SESSION_FUSE_LIMIT) -> None:
        self.limit = limit
        self._prompt_tokens = len(prompt) // CHARS_PER_TOKEN_ESTIMATE
        self._buffer = ""
        self._in_response = False
        self.requests_estimated = 0
        self.in_flight_estimate = 0
        self.exact_cumulative: int | None = None
        self.turn_usage_events = 0
        self.breach: dict | None = None

    def _event(self, event: dict) -> None:
        kind = event.get("type")
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        if kind == "turn.started":
            self._in_response = False
        elif kind == "item.started" or (kind == "item.completed" and item.get("type") == "agent_message"):
            # One model response may carry a message and several tool calls;
            # only a tool result in between proves a further request.
            if not self._in_response:
                self.requests_estimated += 1
                self.in_flight_estimate += self._prompt_tokens + REQUEST_OVERHEAD_FLOOR_TOKENS
                self._in_response = True
        if kind == "item.completed" and item.get("type") in TOOL_ITEM_TYPES:
            self._in_response = False
        elif kind == "turn.completed":
            usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
            value_in, value_out = usage.get("input_tokens"), usage.get("output_tokens")
            if all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in (value_in, value_out)):
                self.exact_cumulative = value_in + value_out
                self.turn_usage_events += 1
        if self.breach is None:
            if self.exact_cumulative is not None and self.exact_cumulative >= self.limit:
                self.breach = {"basis": "exact_turn_usage", "tokens": self.exact_cumulative, "limit": self.limit}
            elif self.in_flight_estimate >= self.limit:
                self.breach = {
                    "basis": ESTIMATE_BASIS,
                    "tokens": self.in_flight_estimate,
                    "limit": self.limit,
                    "verified": False,
                }

    def feed(self, text: str) -> dict | None:
        """Consume streamed stdout text; return the breach once the fuse is reached."""
        self._buffer += text
        *lines, self._buffer = self._buffer.split("\n")
        for raw in lines:
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                self._event(event)
        return self.breach

    def summary(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "scope": "this Codex session only",
            "exact_cumulative_streamed": self.exact_cumulative,
            "turn_usage_events": self.turn_usage_events,
            "in_flight_estimate": self.in_flight_estimate,
            "in_flight_estimate_status": "unverified heuristic; not usage and not a lower bound",
            "requests_estimated": self.requests_estimated,
            "stopped": self.breach,
            "latency_note": (
                "codex exec --json reports exact usage only at turn.completed; between turns the "
                "fuse stops on an unverified estimate, so a stop can land before or after the true 500K point"
            ),
        }


def describe_fuse_stop(breach: dict) -> str:
    """Operator wording for a fuse stop that never passes an estimate off as usage."""
    if breach.get("basis") == "exact_turn_usage":
        return f"exact provider usage {breach['tokens']:,} of {breach['limit']:,}"
    return (
        f"unverified in-flight estimate ~{breach['tokens']:,} of {breach['limit']:,}; "
        "not provider usage and not a lower bound"
    )


def prepare_fresh_prompt(prompt: str) -> str:
    """Apply the mandatory permission/session header without a hidden byte cap."""
    task = str(prompt or "").strip()
    if not task:
        raise CodexPolicyError("Codex clean-session prompt is empty")
    # The canonical header goes first exactly once; copies embedded by a
    # template (e.g. the manual codex-run prompt) are dropped, not repeated.
    task = re.sub(r"\n{3,}", "\n\n", task.replace(PERMISSION_HEADER, "")).strip()
    sections = [PERMISSION_HEADER, FRESH_SESSION_POLICY, task]
    prepared = "\n\n".join(sections).rstrip() + "\n"
    return prepared


def require_clean_session_id(output: str) -> str:
    """Require one real ``thread.started`` identity; never invent a fallback ID."""
    identities: list[str] = []
    started_events = 0
    for raw in str(output or "").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "thread.started":
            continue
        started_events += 1
        value = event.get("thread_id") or event.get("session_id") or event.get("id")
        if isinstance(value, str) and value.strip():
            identities.append(value.strip())
    if started_events != 1 or len(identities) != 1:
        if started_events == 0:
            detail = "missing"
        elif not identities:
            detail = "invalid (thread.started has no real identity)"
        else:
            detail = f"ambiguous ({started_events} thread.started events)"
        raise CodexPolicyError(
            f"Codex clean-session creation failed: thread.started identity is {detail}; "
            "refusing previous-session inheritance or synthetic fallback"
        )
    return identities[0]


def cumulative_usage_snapshot(output: str) -> dict:
    """Return the last cumulative JSONL usage snapshot without summing events.

    Codex ``turn.completed`` usage is cumulative. Repeated snapshots replace the
    preceding snapshot; an incomplete final event never falls back to an older
    complete event because that would silently under-report the closing usage.
    """
    event_count = 0
    last_usage: object = None
    for raw in str(output or "").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.completed":
            continue
        event_count += 1
        last_usage = event.get("usage")
    if event_count == 0:
        return {"available": False, "event_count": 0, "reason": "missing terminal turn.completed usage"}
    if not isinstance(last_usage, dict):
        return {"available": False, "event_count": event_count, "reason": "terminal turn.completed usage is malformed"}

    values = {
        "input_tokens": last_usage.get("input_tokens"),
        "cached_input_tokens": last_usage.get("cached_input_tokens"),
        "output_tokens": last_usage.get("output_tokens"),
        "reasoning_output_tokens": last_usage.get("reasoning_output_tokens"),
    }
    required = ("input_tokens", "output_tokens")
    if any(not isinstance(values[key], int) or isinstance(values[key], bool) or values[key] < 0 for key in required):
        return {"available": False, "event_count": event_count, "reason": "terminal turn.completed usage lacks non-negative input/output"}
    for key in ("cached_input_tokens", "reasoning_output_tokens"):
        value = values[key]
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            return {"available": False, "event_count": event_count, "reason": f"terminal {key} is malformed"}
    cached = values["cached_input_tokens"]
    reasoning = values["reasoning_output_tokens"]
    if cached is not None and cached > values["input_tokens"]:
        return {"available": False, "event_count": event_count, "reason": "cached input exceeds provider-total input"}
    if reasoning is not None and reasoning > values["output_tokens"]:
        return {"available": False, "event_count": event_count, "reason": "reasoning output exceeds provider output"}
    return {
        "available": True,
        "event_count": event_count,
        **values,
        "cumulative_tokens": values["input_tokens"] + values["output_tokens"],
    }


def build_environment(target: CodexRuntimeTarget = CODEX_TARGET) -> dict[str, str]:
    """Retain the authenticated process environment while pinning Liam's Codex home."""
    try:
        account = pwd.getpwnam(target.linux_user)
    except KeyError as exc:
        raise CodexPolicyError(f"Linux user does not exist: {target.linux_user}") from exc
    env = os.environ.copy()
    env["HOME"] = account.pw_dir
    env["USER"] = target.linux_user
    env["LOGNAME"] = target.linux_user
    env["CODEX_HOME"] = str(target.codex_home)
    env["PATH"] = os.pathsep.join((
        str(target.executable.parent),
        str(Path(account.pw_dir) / ".local" / "bin"),
        env.get("PATH", ""),
    ))
    return env


def readiness(target: CodexRuntimeTarget = CODEX_TARGET, *, timeout: float = 5) -> dict:
    """Inspect the actual production command, identity, executable, and authentication."""
    metadata = invocation_metadata(target)
    command = build_exec_command(target)
    try:
        validate_runtime(target.root, target)
    except CodexPolicyError as exc:
        return {"available": False, "state": "policy_defect", "policy_error": str(exc), **metadata, "command": command}
    env = build_environment(target)
    try:
        version = subprocess.run(
            [str(target.executable), "--version"],
            cwd=str(target.root), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "state": type(exc).__name__, **metadata, "command": command}
    result = {
        "available": version.returncode == 0,
        "state": "ready" if version.returncode == 0 else "version_probe_failed",
        "version": ((version.stdout or "") + (version.stderr or "")).strip().splitlines()[-1]
        if (version.stdout or version.stderr) else "unavailable",
        **metadata,
        "command": command,
    }
    if not result["available"]:
        return result
    try:
        auth = subprocess.run(
            [str(target.executable), "login", "status"],
            cwd=str(target.root), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result.update(available=False, authenticated=False, state="authentication_probe_failed")
        return result
    result["authenticated"] = auth.returncode == 0 and "logged in" in ((auth.stdout or "") + (auth.stderr or "")).lower()
    if not result["authenticated"]:
        result.update(available=False, state="authentication_unavailable")
    return result


def run_streaming(
    command: list[str],
    *,
    cwd: Path | str,
    env: dict[str, str],
    prompt: str,
    timeout_seconds: float,
    fuse: StreamingSessionFuse,
    terminate_grace_seconds: float = 1.0,
    kill_grace_seconds: float = 1.0,
) -> dict[str, Any]:
    """Run one Codex process, feeding stdout to the session fuse as it streams.

    On timeout or a fuse breach the whole process group gets SIGTERM, then
    SIGKILL after the grace period; output that arrives meanwhile is kept.
    """
    process = subprocess.Popen(
        command, cwd=str(cwd), env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True, close_fds=True,
    )
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    try:
        process.stdin.write(prompt.encode("utf-8"))
        process.stdin.close()
    except BrokenPipeError:
        pass
    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    stop_stage = ""  # "", "terminated", "killed"
    stop_at = 0.0

    def signal_group(sig: int) -> None:
        try:
            os.killpg(process.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass

    try:
        while selector.get_map():
            now = time.monotonic()
            if not stop_stage and now >= deadline:
                timed_out = True
            if not stop_stage and (timed_out or fuse.breach is not None):
                signal_group(signal.SIGTERM)
                stop_stage, stop_at = "terminated", now
            elif stop_stage == "terminated" and now - stop_at >= terminate_grace_seconds:
                signal_group(signal.SIGKILL)
                stop_stage, stop_at = "killed", now
            elif stop_stage == "killed" and now - stop_at >= kill_grace_seconds:
                break
            for key, _ in selector.select(timeout=0.1):
                try:
                    chunk = os.read(key.fileobj.fileno(), 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                chunks[key.data].append(chunk)
                if key.data == "stdout" and fuse.breach is None:
                    fuse.feed(decoder.decode(chunk))
        if stop_stage:
            signal_group(signal.SIGKILL)
        try:
            process.wait(timeout=kill_grace_seconds + 1)
        except subprocess.TimeoutExpired:
            pass
    finally:
        selector.close()
        for stream in (process.stdout, process.stderr):
            try:
                stream.close()
            except OSError:
                pass
    return {
        "stdout": b"".join(chunks["stdout"]).decode("utf-8", errors="replace"),
        "stderr": b"".join(chunks["stderr"]).decode("utf-8", errors="replace"),
        "returncode": process.returncode,
        "timed_out": timed_out,
        "fuse_breach": fuse.breach,
        "pid": process.pid,
    }
