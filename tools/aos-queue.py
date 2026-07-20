#!/usr/bin/env python3
"""Local Agentic OS work queue and explicit workbench launch boundary.

Queue mutations stay local. The ``codex-run`` command is the one bounded
exception: it launches the installed Codex CLI for an explicit work-item ID,
waits for exit, then reconciles the CLI's final token summary into the existing
receipt/sidecar/token-ledger path.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

TOOLS_DIR = Path(__file__).resolve().parent
REPO_DIR = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from aos_paths import AuthorityError, aos_root, assert_authoritative_root
from aos_codex_policy import (
    CODEX_TARGET,
    CONTEXT_HANDOFF_THRESHOLD_TOKENS,
    MAX_CONTEXT_HANDOFFS,
    CodexPolicyError,
    build_environment as build_codex_environment,
    build_exec_command as build_codex_exec_command,
    cumulative_usage_snapshot,
    prepare_fresh_prompt as prepare_codex_fresh_prompt,
    require_clean_session_id,
    validate_runtime as validate_codex_runtime,
)
from aos_queue_storage import QueueStorageError, durable_replace_text, queue_write_lock
from business_brain_context import BrainContextError, validate_completion_context

DEFAULT_ROOT = aos_root()
QUEUE_DIR = Path("queue")
WORK_ITEMS_PATH = QUEUE_DIR / "work_items.jsonl"
REGISTRY_PATH = QUEUE_DIR / "agent_registry.json"
RECEIPTS_DIR = QUEUE_DIR / "receipts"
LOCKS_DIR = QUEUE_DIR / "locks"
SCHEMAS_DIR = QUEUE_DIR / "schemas"
ROLLUPS_DIR = QUEUE_DIR / "rollups"
LANE_PROFILES_PATH = QUEUE_DIR / "lane_profiles.json"
MODEL_ROUTES_PATH = QUEUE_DIR / "model_routes.json"
RUN_LEDGER_PATH = QUEUE_DIR / "run_ledger.jsonl"
TOKEN_LEDGER_PATH = QUEUE_DIR / "token_ledger.jsonl"
RUN_LEDGER_SCHEMA_PATH = QUEUE_DIR / "run_ledger_schema.json"
TOKEN_LEDGER_SCHEMA_PATH = QUEUE_DIR / "token_ledger_schema.json"
# Pricing and schemas are repo assets, resolved from the tool location (not --root),
# so a temporary --root (tests/sandboxes) still finds the canonical files.
MODEL_PRICES_PATH = REPO_DIR / "scripts" / "model_prices.json"
HERMES_PROBE_TIMEOUT_S = 20
# Mirrors the orchestration runner's DEFAULT_EXECUTION_TIMEOUT_SECONDS contract
# (tools/aos-orchestration-runner.py) so a hung Codex process is bounded here too.
CODEX_EXECUTION_TIMEOUT_SECONDS = 7800
DONE_STATUS = "done"
CODEX_TOKEN_SUMMARY_RE = re.compile(
    r"^Token usage:\s*total=(?P<total>[\d,]+)\s+"
    r"input=(?P<input>[\d,]+)"
    r"(?:\s+\(\+\s*(?P<cached>[\d,]+)\s+cached\))?\s+"
    r"output=(?P<output>[\d,]+)"
    r"(?:\s+\(reasoning\s+(?P<reasoning>[\d,]+)\))?\s*$",
    re.MULTILINE,
)
UNAVAILABLE_CLI_VALUE = "unavailable from current CLI output"
CODEX_COUNTER_FIELDS = (
    "initial_prompt_bytes",
    "model_turns",
    "retained_context_bytes",
    "compaction_count",
    "total_input",
    "cached_input",
    "non_cached_input",
    "output",
    "reasoning",
    "input_plus_output",
    "fresh_input",
    "largest_tool_result_bytes",
    "context_pct_at_close",
)

APPROVED_STATUSES = {
    "inbox",
    "agent_todo",
    "agent_working",
    "needs_input",
    "human_review",
    "done",
    "blocked",
    "cancelled",
}
AVAILABLE_STATUSES = {"inbox", "agent_todo"}
APPROVED_OWNER_TYPES = {"agent", "workflow"}
STARTER_AGENTS = ["hermes", "codex", "claude", "revenue", "marketing", "delivery", "operations"]


class QueueError(Exception):
    """Raised when a local queue operation cannot continue."""


class ClaimConflictError(QueueError):
    """Raised when a claim is refused because the item is already claimed or
    already agent_working. The `code` attribute survives dynamic module loads
    (importlib gives each load distinct class objects), so callers such as the
    dashboard run endpoint match on it rather than on class identity."""

    code = "claim_conflict"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_queue(root: Path) -> None:
    root = assert_authoritative_root(root)
    queue = root / QUEUE_DIR
    queue.mkdir(parents=True, exist_ok=True)
    (root / RECEIPTS_DIR).mkdir(parents=True, exist_ok=True)
    (root / LOCKS_DIR).mkdir(parents=True, exist_ok=True)
    (root / SCHEMAS_DIR).mkdir(parents=True, exist_ok=True)
    work_items = root / WORK_ITEMS_PATH
    if not work_items.exists():
        with queue_write_lock(root):
            if not work_items.exists():
                durable_replace_text(work_items, "")
    registry = root / REGISTRY_PATH
    if not registry.exists():
        durable_replace_text(
            registry,
            json.dumps(
                {
                    "version": 1,
                    "agents": [{"id": agent, "name": agent.title()} for agent in STARTER_AGENTS],
                },
                indent=2,
            )
            + "\n",
        )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry(root: Path) -> dict:
    path = root / REGISTRY_PATH
    if not path.exists():
        # Read-only commands must not initialize state. Mutating create calls
        # ensure_queue first; isolated fixtures may use the built-in registry.
        return {"version": 1, "agents": [{"id": agent, "name": agent.title()} for agent in STARTER_AGENTS]}
    registry = read_json(path)
    if not isinstance(registry.get("agents"), list):
        raise QueueError("Agent registry must contain an agents list")
    return registry


def agent_ids(root: Path) -> set[str]:
    return {agent["id"] for agent in load_registry(root)["agents"]}


def validate_agent(root: Path, agent_id: str) -> None:
    if agent_id not in agent_ids(root):
        raise QueueError(f"Unknown agent: {agent_id}")


def validate_status(status: str) -> None:
    if status not in APPROVED_STATUSES:
        raise QueueError(f"Invalid status: {status}")


def load_items(root: Path) -> list[dict]:
    path = root / WORK_ITEMS_PATH
    if not path.exists():
        raise QueueError(f"Work queue not found: {path}")
    items = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise QueueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
        items.append(item)
    return items


def save_items(root: Path, items: list[dict]) -> None:
    with queue_write_lock(root):
        ensure_queue(root)
        text = "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in items)
        durable_replace_text(root / WORK_ITEMS_PATH, text)


def locked_queue_mutation(function):
    """Hold the shared ledger lock across the complete read/modify/write."""
    @functools.wraps(function)
    def wrapped(root: Path, *args, **kwargs):
        with queue_write_lock(root):
            return function(root, *args, **kwargs)
    return wrapped


def find_item(items: list[dict], item_id: str) -> dict:
    for item in items:
        if item.get("id") == item_id:
            return item
    raise QueueError(f"Work item not found: {item_id}")


def next_id(items: list[dict], created_at: str) -> str:
    year = created_at[:4]
    prefix = f"AOS-{year}-"
    max_number = 0
    for item in items:
        item_id = str(item.get("id", ""))
        if item_id.startswith(prefix):
            try:
                max_number = max(max_number, int(item_id.rsplit("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}{max_number + 1:04d}"


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


# ---------------------------------------------------------------------------
# Coordinator done-transition: lane->profile resolution, dual ledger write,
# and token metering. Everything here is best-effort with respect to queue
# liveness: a metering problem is surfaced (NEEDS ATTENTION on stderr) but the
# token_usage block is always assemblable ("unavailable" where a component did
# not report), so the transition is never blocked for missing tokens. Numbers
# come from harness/API usage fields only — never estimated (never.md #7).
# ---------------------------------------------------------------------------

DEFAULT_PROFILE = "default"
DEFAULT_BUDGET_CLASS = "standard"
BUDGET_CLASSES = {"light", "standard", "heavy"}


def _read_json_or(default: Any, path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_lane_profiles(root: Path) -> dict:
    return _read_json_or({}, root / LANE_PROFILES_PATH)


def load_model_routes(root: Path) -> dict:
    return _read_json_or({}, root / MODEL_ROUTES_PATH)


def load_prices() -> dict:
    prices = _read_json_or({}, MODEL_PRICES_PATH)
    return prices.get("models", {}) if isinstance(prices, dict) else {}


def resolve_route(root: Path, owner: str | None) -> dict:
    """Map a queue owner to its lane, requested profile, and fallback profile.

    Owners are looked up as lane keys in lane_profiles.json. Owners with no lane
    entry (workbenches like codex/claude, or unassigned) resolve to the default
    Hermes route, matching model_routes.json.
    """
    owner = owner or "unassigned"
    lanes = load_lane_profiles(root).get("lanes", {})
    entry = lanes.get(owner)
    if isinstance(entry, dict):
        return {
            "owner": owner,
            "lane": entry.get("lane", owner),
            "profile_requested": entry.get("profile_requested", DEFAULT_PROFILE),
            "fallback_profile": entry.get("fallback_profile", DEFAULT_PROFILE),
        }
    return {
        "owner": owner,
        "lane": owner,
        "profile_requested": DEFAULT_PROFILE,
        "fallback_profile": DEFAULT_PROFILE,
    }


def probe_profile_invocation(profile_requested: str, fallback_profile: str) -> dict:
    """Attempt a REAL, read-only resolution of the requested Hermes profile and
    record honestly whether native profile switching can be performed.

    This never runs `hermes profile use` (prohibited for queue routing by
    queue/profiles/README.md) and never runs a model. It queries
    `hermes profile show`, which HERMES_CAPABILITIES.md sanctions as the
    inspection surface, and reports the evidence. No invocation is simulated:
    when native switching cannot occur, the reason is recorded, not faked.
    """
    result: dict[str, Any] = {
        "requested_profile": profile_requested,
        "fallback_profile": fallback_profile,
        "invoked": False,
        "native_invocation": "unavailable",
        "resolved_profile": fallback_profile,
        "evidence": None,
        "reason": None,
    }

    hermes = shutil.which("hermes")
    if profile_requested in (DEFAULT_PROFILE, "", None):
        result["resolved_profile"] = DEFAULT_PROFILE
        result["reason"] = "Owner routes to the default Hermes runtime; no aos-* profile switch requested."
        result["native_invocation"] = "not_applicable"

    if not hermes:
        result["evidence"] = "hermes CLI not found on PATH"
        result["reason"] = "Cannot resolve Hermes profile: `hermes` not on PATH."
        return result

    try:
        proc = subprocess.run(
            [hermes, "profile", "show", profile_requested],
            capture_output=True,
            text=True,
            timeout=HERMES_PROBE_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["evidence"] = f"`hermes profile show {profile_requested}` failed: {exc}"
        result["reason"] = "Cannot resolve Hermes profile: probe command failed."
        return result

    out = (proc.stdout or "") + (proc.stderr or "")
    result["evidence"] = f"`hermes profile show {profile_requested}` rc={proc.returncode}"
    if proc.returncode != 0:
        result["reason"] = (
            f"Profile '{profile_requested}' not resolvable via `hermes profile show`; "
            f"fell back to '{fallback_profile}' route."
        )
        return result

    has_model = any(line.strip().lower().startswith("model:") for line in out.splitlines())
    if profile_requested == DEFAULT_PROFILE:
        # Default route confirmed present; still no switch performed here.
        result["resolved_profile"] = DEFAULT_PROFILE
        result["evidence"] += "; profile present"
        result["reason"] = "Default Hermes route confirmed present; no profile switch needed."
        return result

    if has_model:
        result["resolved_profile"] = profile_requested
        result["evidence"] += "; profile present WITH configured model"
        result["reason"] = (
            f"Profile '{profile_requested}' has a configured model, but `hermes profile use` is "
            "prohibited for queue routing (queue/profiles/README.md); the queue does not switch "
            "the sticky default. Native switching intentionally not performed."
        )
    else:
        result["resolved_profile"] = fallback_profile
        result["evidence"] += "; profile present WITHOUT configured model (no Model: line)"
        result["reason"] = (
            f"Profile '{profile_requested}' exists but has no configured model "
            "(HERMES_CAPABILITIES.md; enabled_only_when_model_configured=true), and "
            "`hermes profile use` is prohibited for queue routing; fell back to "
            f"'{fallback_profile}' route."
        )
    return result


def _coerce_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def cost_for(
    model: str | None,
    inp: int,
    outp: int,
    prices: dict,
    *,
    fresh_input: int | None = None,
    cached_input: int | None = None,
) -> float | None:
    """Price provider-total input once, using cache-read pricing when split."""
    rate = prices.get(model) if model else None
    if not isinstance(rate, dict):
        return None
    if fresh_input is not None and cached_input is not None:
        if fresh_input + cached_input != inp or "cache_read_per_mtok" not in rate:
            return None
        input_cost = (
            fresh_input / 1_000_000 * rate.get("input_per_mtok", 0.0)
            + cached_input / 1_000_000 * rate["cache_read_per_mtok"]
        )
    else:
        # Legacy ``input`` is provider-total input. With no reported cache
        # split it is charged once at the normal input rate.
        input_cost = inp / 1_000_000 * rate.get("input_per_mtok", 0.0)
    return round(input_cost + outp / 1_000_000 * rate.get("output_per_mtok", 0.0), 6)


def token_usage_warnings(block: dict) -> list[str]:
    """Return deterministic soft warnings for reported workbench drift."""
    warnings: list[str] = []
    for work in block.get("workbenches") or []:
        if not isinstance(work, dict) or work.get("source") != "reported":
            continue
        tool = str(work.get("tool") or "workbench")
        session = str(work.get("session_id") or "unavailable")
        fresh = _coerce_int(work.get("fresh_input"))
        cached = _coerce_int(work.get("cached_input"))
        if fresh is not None and cached is not None:
            ratio = round(cached / max(fresh, 1), 6)
            work["cache_ratio"] = ratio
            if ratio > 20:
                warnings.append(f"cache_ratio > 20: {tool} session {session} ratio={ratio}")
        context_pct = work.get("context_pct_at_close")
        if isinstance(context_pct, (int, float)) and not isinstance(context_pct, bool) and context_pct > 50:
            warnings.append(
                f"context_pct_at_close > 50: {tool} session {session} context_pct_at_close={context_pct}"
            )
    return warnings


def _empty_token_usage(unavailable: list[str]) -> dict:
    return {
        "orchestrator": {"input": 0, "output": 0},
        "subagents": [],
        "workbenches": [],
        "totals": {"input": 0, "output": 0},
        "est_cost_usd": 0.0,
        "unavailable": list(unavailable),
    }


def _recompute_totals_and_cost(block: dict, prices: dict, model_confirmed: str) -> dict:
    """Recompute totals and est_cost_usd deterministically from model_prices.json.

    Never accepts a caller-supplied cost (TOKEN_POLICY.md:47) — every component
    is priced from its own model rate. The orchestrator block carries no
    per-component model (receipt schema), so it is priced at model_confirmed,
    the same attribution scripts/token_rollup.py uses for its by_model
    breakdown; this keeps the ledger's stored est_cost_usd and the rollup's
    recomputed total in agreement.
    """
    orch = block.get("orchestrator", {"input": 0, "output": 0})
    subs = block.get("subagents", [])
    works = block.get("workbenches", [])
    total_in = int(orch.get("input", 0)) + sum(int(s.get("input", 0)) for s in subs) + sum(int(w.get("input", 0)) for w in works)
    total_out = int(orch.get("output", 0)) + sum(int(s.get("output", 0)) for s in subs) + sum(int(w.get("output", 0)) for w in works)
    block["totals"] = {"input": total_in, "output": total_out}

    cost = 0.0
    orch_cost = cost_for(model_confirmed, int(orch.get("input", 0)), int(orch.get("output", 0)), prices)
    if orch_cost is not None:
        cost += orch_cost
    for s in subs:
        c = cost_for(s.get("model"), int(s.get("input", 0)), int(s.get("output", 0)), prices)
        if c is not None:
            cost += c
    for w in works:
        if w.get("source") == "reported":
            fresh = _coerce_int(w.get("fresh_input"))
            cached = _coerce_int(w.get("cached_input"))
            c = cost_for(
                w.get("model"), int(w.get("input", 0)), int(w.get("output", 0)), prices,
                fresh_input=fresh, cached_input=cached,
            )
            if c is not None:
                cost += c
            elif fresh is not None and cached is not None:
                message = f"cost/cache-read rate for workbench model {w.get('model') or 'unavailable'}"
                if message not in block.setdefault("unavailable", []):
                    block["unavailable"].append(message)
    block["est_cost_usd"] = round(cost, 6)
    return block


def build_token_usage(route: dict, *, usage_file: str | None, token_usage_json: dict | None) -> tuple[dict, str]:
    """Assemble the token_usage block and the confirmed model.

    Priority of sources (all harness/API-derived — never estimated):
      1. token_usage_json: a pre-assembled block (e.g. from the orchestrator).
      2. usage_file: a Hermes one-shot `--usage-file` JSON (HERMES_CAPABILITIES.md).
      3. neither: a fully-"unavailable" block.
    """
    prices = load_prices()

    if token_usage_json is not None:
        block = _empty_token_usage([])
        for key in ("orchestrator", "subagents", "workbenches", "unavailable"):
            if key in token_usage_json:
                block[key] = token_usage_json[key]
        # est_cost_usd, if the caller supplied one, is ignored: cost is always
        # computed deterministically below, never taken from the caller.
        model_confirmed = "unavailable"
        subs = block.get("subagents", [])
        if subs and subs[0].get("model"):
            model_confirmed = subs[0]["model"]
        block = _recompute_totals_and_cost(block, prices, model_confirmed)
        return block, model_confirmed

    if usage_file:
        usage = _read_json_or(None, Path(usage_file))
        if not isinstance(usage, dict):
            return _empty_token_usage([f"usage file unreadable: {usage_file}"]), "unavailable"
        inp = _coerce_int(usage.get("input_tokens"))
        outp = _coerce_int(usage.get("output_tokens"))
        model = usage.get("model") or "unavailable"
        unavailable: list[str] = []
        role = f"{route['profile_requested']}/oneshot"
        if inp is None:
            unavailable.append(f"{role} input tokens")
        if outp is None:
            unavailable.append(f"{role} output tokens")
        block = _empty_token_usage(unavailable)
        block["subagents"] = [{"role": role, "model": model, "input": inp or 0, "output": outp or 0}]
        # orchestrator and workbench are not carried by a one-shot usage file.
        block["unavailable"].extend(["orchestrator tokens", "workbench session totals"])
        model_confirmed = model if model != "unavailable" else "unavailable"
        # est_cost_usd is always computed deterministically below; a caller-supplied
        # estimated_cost_usd in the usage file is never used (TOKEN_POLICY.md:47).
        block = _recompute_totals_and_cost(block, prices, model_confirmed)
        if cost_for(model, inp or 0, outp or 0, prices) is None:
            block["unavailable"].append(f"cost for model {model}")
        return block, model_confirmed

    return _empty_token_usage(["orchestrator tokens", "subagent tokens", "workbench session totals"]), "unavailable"


def _derive_budget_class(item: dict, override: str | None) -> str:
    if override in BUDGET_CLASSES:
        return override
    for tag in item.get("tags", []):
        if tag.startswith("budget:"):
            candidate = tag.split(":", 1)[1]
            if candidate in BUDGET_CLASSES:
                return candidate
    return DEFAULT_BUDGET_CLASS


def _derive_skill(item: dict, override: str | None) -> str:
    if override:
        return override
    for tag in item.get("tags", []):
        if tag.startswith(("budget:", "hermes")) or tag in {"queue", "synthetic", "test"}:
            continue
        return tag
    return "unspecified"


def _latest_receipt_path(item: dict, override: str | None) -> str | None:
    if override:
        return override
    receipts = item.get("receipts", [])
    if receipts:
        return receipts[-1].get("path")
    return None


def _validate_against_schema(line: dict, schema_path: Path) -> str | None:
    """Validate against JSON Schema. Returns an error string, or None if valid."""
    schema = _read_json_or(None, schema_path)
    if not isinstance(schema, dict):
        return None
    try:
        jsonschema.validate(line, schema)
    except jsonschema.ValidationError as exc:
        return exc.message
    return None


def _append_jsonl(root: Path, path: Path, line: dict, *, effect_id: str | None = None) -> bool:
    """Durably append one logical row unless its deterministic key exists."""
    with queue_write_lock(root):
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if effect_id:
            for number, raw in enumerate(existing.splitlines(), start=1):
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise QueueError(f"malformed JSONL effect store {path} line {number}") from exc
                if row.get("effect_id") == effect_id:
                    return False
            line = {**line, "effect_id": effect_id}
        durable_replace_text(path, existing + json.dumps(line, separators=(",", ":")) + "\n")
        return True


def _write_receipt_token_usage(
    root: Path,
    item_id: str,
    receipt_path: str | None,
    block: dict,
    invocation: dict,
    counters: dict | None = None,
) -> str:
    """Attach the token_usage block to the item's receipt.

    If a markdown receipt exists, append a fenced block (idempotent per id).
    Always also write a machine-readable sidecar so the receipt-completeness
    hook and the dashboard have a deterministic source.
    """
    payload = {
        "token_usage": block,
        "profile_invocation": invocation,
        "warnings": token_usage_warnings(block),
        **(counters or _unavailable_codex_counters()),
    }
    sidecar = root / RECEIPTS_DIR / f"{item_id}.token_usage.json"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    existing_payload = _read_json_or(None, sidecar) if sidecar.exists() else None
    if not (_token_payload_is_exact(existing_payload) and not _token_payload_is_exact(payload)):
        durable_replace_text(sidecar, json.dumps(payload, indent=2) + "\n")

    if receipt_path:
        md = root / receipt_path
        marker = f"<!-- token_usage:{item_id} -->"
        if md.exists() and md.suffix.lower() == ".md":
            existing = md.read_text(encoding="utf-8")
            if marker not in existing:
                block_md = (
                    f"\n\n{marker}\n## token_usage\n```json\n"
                    + json.dumps(payload, indent=2)
                    + "\n```\n"
                )
                durable_replace_text(md, existing + block_md)
    return str(sidecar.relative_to(root)) if sidecar.is_relative_to(root) else str(sidecar)


def _token_payload_is_exact(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    evidence = payload.get("capture_evidence") if isinstance(payload.get("capture_evidence"), dict) else {}
    if all(_coerce_int(evidence.get(key)) is not None for key in ("input_tokens", "output_tokens", "total_tokens")):
        return evidence["total_tokens"] == evidence["input_tokens"] + evidence["output_tokens"]
    usage = payload.get("token_usage") if isinstance(payload.get("token_usage"), dict) else {}
    for workbench in usage.get("workbenches") or []:
        if isinstance(workbench, dict) and workbench.get("source") == "reported" and all(_coerce_int(workbench.get(key)) is not None for key in ("input", "output")):
            return True
    unavailable = usage.get("unavailable") if isinstance(usage.get("unavailable"), list) else ["unknown"]
    totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else {}
    return not unavailable and all(_coerce_int(totals.get(key)) is not None for key in ("input", "output"))


def _unavailable_codex_counters() -> dict:
    return {key: UNAVAILABLE_CLI_VALUE for key in CODEX_COUNTER_FIELDS}


def normalize_codex_usage(
    provider_total_input: int,
    cached_input: int | None,
    output: int,
    reasoning: int | None,
) -> dict:
    """Normalize Codex JSONL without double-counting provider-total input."""
    values = (provider_total_input, output)
    if any(_coerce_int(value) is None or value < 0 for value in values):
        raise QueueError("Codex provider input/output must be non-negative integers")
    if cached_input is not None:
        if _coerce_int(cached_input) is None or cached_input < 0:
            raise QueueError("Codex cached input must be a non-negative integer")
        if cached_input > provider_total_input:
            raise QueueError("Codex cached input cannot exceed provider-total input")
        fresh_input: int | str = provider_total_input - cached_input
        cache_ratio: float | str = round(cached_input / max(fresh_input, 1), 6)
    else:
        fresh_input = UNAVAILABLE_CLI_VALUE
        cache_ratio = UNAVAILABLE_CLI_VALUE
    if reasoning is not None and (_coerce_int(reasoning) is None or reasoning < 0 or reasoning > output):
        raise QueueError("Codex reasoning output must be a non-negative subset of output")
    return {
        "input": provider_total_input,
        "fresh_input": fresh_input,
        "cached_input": cached_input if cached_input is not None else UNAVAILABLE_CLI_VALUE,
        "output": output,
        "reasoning": reasoning if reasoning is not None else UNAVAILABLE_CLI_VALUE,
        "cache_ratio": cache_ratio,
    }


def parse_codex_usage_counters(output: str) -> dict:
    """Parse only counters explicitly emitted by Codex; never derive missing values."""
    counters = _unavailable_codex_counters()
    aliases = {
        "input_tokens": "total_input",
        "cached_input_tokens": "cached_input",
        "output_tokens": "output",
        "reasoning_output_tokens": "reasoning",
    }
    for raw in (output or "").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        containers = [event]
        for key in ("usage", "usage_counters", "metrics"):
            if isinstance(event.get(key), dict):
                containers.append(event[key])
        for container in containers:
            for source, target in (*((key, key) for key in CODEX_COUNTER_FIELDS), *aliases.items()):
                value = _coerce_int(container.get(source))
                if value is not None:
                    if value < 0:
                        raise QueueError(f"Codex usage counter {source} must be a non-negative integer")
                    counters[target] = value

    terminal_matches = list(CODEX_TOKEN_SUMMARY_RE.finditer(output or ""))
    if terminal_matches:
        terminal = terminal_matches[-1].groupdict()
        for source, target in (("input", "total_input"), ("cached", "cached_input"), ("output", "output"), ("reasoning", "reasoning")):
            value = terminal.get(source)
            if value is not None:
                counters[target] = int(value.replace(",", ""))
    snapshot = cumulative_usage_snapshot(output)
    if snapshot.get("event_count"):
        for key in ("total_input", "cached_input", "non_cached_input", "fresh_input", "output", "reasoning", "input_plus_output"):
            counters[key] = UNAVAILABLE_CLI_VALUE
        if snapshot.get("available"):
            counters["total_input"] = snapshot["input_tokens"]
            counters["output"] = snapshot["output_tokens"]
            if snapshot.get("cached_input_tokens") is not None:
                counters["cached_input"] = snapshot["cached_input_tokens"]
            if snapshot.get("reasoning_output_tokens") is not None:
                counters["reasoning"] = snapshot["reasoning_output_tokens"]
    total_input = counters.get("total_input")
    cached_input = counters.get("cached_input")
    output = counters.get("output")
    if isinstance(total_input, int) and isinstance(cached_input, int) and cached_input <= total_input:
        counters["non_cached_input"] = total_input - cached_input
        counters["fresh_input"] = total_input - cached_input
    if isinstance(total_input, int) and isinstance(output, int):
        counters["input_plus_output"] = total_input + output
    return counters


def parse_codex_token_summary(output: str) -> dict:
    """Return the final exact Codex token summary from combined process output."""
    terminal_matches = list(CODEX_TOKEN_SUMMARY_RE.finditer(output or ""))
    # ``codex exec --json`` is the supported machine-readable exiting mode in
    # codex-cli 0.144.1. Its terminal turn.completed event carries the exact
    # breakdown. Structured evidence has precedence over a terminal cross-check.
    turn_events: list[dict] = []
    for raw in (output or "").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "turn.completed":
            turn_events.append(event)
    if turn_events:
        usage = turn_events[-1].get("usage")
        if not isinstance(usage, dict):
            raise QueueError("Codex terminal turn.completed usage is malformed")
        values = {
            "input": _coerce_int(usage.get("input_tokens")),
            "output": _coerce_int(usage.get("output_tokens")),
            "cached": _coerce_int(usage.get("cached_input_tokens")),
            "reasoning": _coerce_int(usage.get("reasoning_output_tokens")),
        }
        if values["input"] is None or values["output"] is None:
            raise QueueError("Codex terminal turn.completed usage lacks input/output")
        if any(value is not None and value < 0 for value in values.values()):
            raise QueueError("Codex JSON token summary contains a negative value")
        parsed = {
            **values,
            "total": values["input"] + values["output"],
            "raw_summary": raw.strip(),
            "summary_format": "turn.completed JSONL",
            "usage_counters": parse_codex_usage_counters(output),
        }
        parsed["normalized_usage"] = normalize_codex_usage(
            values["input"], values["cached"], values["output"], values["reasoning"]
        )
        _validate_codex_summary(parsed)
        if terminal_matches:
            terminal = {
                key: int(value.replace(",", "")) if value is not None else None
                for key, value in terminal_matches[-1].groupdict().items()
            }
            _validate_codex_summary(terminal)
            structured_values = tuple(parsed.get(key) for key in ("input", "output", "total", "cached", "reasoning"))
            terminal_values = tuple(terminal.get(key) for key in ("input", "output", "total", "cached", "reasoning"))
            if structured_values != terminal_values:
                raise QueueError("Codex structured usage conflicts with terminal summary cross-check")
            parsed["terminal_summary_cross_check"] = terminal_matches[-1].group(0).strip()
        return parsed

    if terminal_matches:
        match = terminal_matches[-1]
        parsed = {
            key: int(value.replace(",", "")) if value is not None else None
            for key, value in match.groupdict().items()
        }
        parsed["raw_summary"] = match.group(0).strip()
        parsed["summary_format"] = "text"
        parsed["usage_counters"] = parse_codex_usage_counters(output)
        parsed["normalized_usage"] = normalize_codex_usage(
            parsed["input"], parsed.get("cached"), parsed["output"], parsed.get("reasoning")
        )
        _validate_codex_summary(parsed)
        return parsed
    raise QueueError("Codex exited without a parseable final token summary")


def _validate_codex_summary(summary: dict) -> None:
    for key in ("input", "output", "total"):
        if _coerce_int(summary.get(key)) is None or summary[key] < 0:
            raise QueueError(f"Codex token summary {key} must be a non-negative integer")
    if summary["total"] != summary["input"] + summary["output"]:
        raise QueueError("Codex token summary total does not equal input + output")
    for key in ("cached", "reasoning"):
        value = summary.get(key)
        if value is not None and (_coerce_int(value) is None or value < 0):
            raise QueueError(f"Codex token summary {key} must be a non-negative integer")
    if summary.get("cached") is not None and summary["cached"] > summary["input"]:
        raise QueueError("Codex cached input cannot exceed provider-total input")
    if summary.get("reasoning") is not None and summary["reasoning"] > summary["output"]:
        raise QueueError("Codex reasoning output must be a subset of output")


def parse_codex_session_id(output: str) -> str | None:
    """Extract the supervised Codex thread/session identity from JSONL output."""
    for raw in (output or "").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "thread.started":
            continue
        for key in ("thread_id", "session_id", "id"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _write_codex_stream_artifacts(root: Path, identity: str, stdout: str, stderr: str) -> list[str]:
    directory = root / "logs" / "codex_sessions"
    directory.mkdir(parents=True, exist_ok=True)
    safe_identity = re.sub(r"[^A-Za-z0-9_.-]+", "_", identity)[:120] or "clean-session-failed"
    paths: list[str] = []
    for suffix, content in (("stdout.jsonl", stdout), ("stderr.txt", stderr)):
        if not content:
            continue
        target = directory / f"{safe_identity}.{suffix}"
        durable_replace_text(target, content if content.endswith("\n") else content + "\n")
        paths.append(target.relative_to(root).as_posix())
    return paths


def _write_codex_context_handoff(
    root: Path,
    session_id: str,
    item_id: str,
    prompt: str,
    usage: dict,
    stream_artifacts: list[str],
) -> str:
    directory = root / "logs" / "codex_handoffs"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', session_id)[:120]}.md"
    task_summary = re.sub(r"\s+", " ", str(prompt or "")).strip()[:2_000]
    lines = [
        "# Codex context handoff receipt",
        "> Revisit: when the linked task continuation is complete. · Last touched: 2026-07-19.",
        "",
        "- Session mode: fresh ephemeral; transcript resume forbidden",
        f"- Completed session ID: `{session_id}`",
        f"- Work item ID: `{item_id}`",
        f"- Configured handoff boundary: 50% / {CONTEXT_HANDOFF_THRESHOLD_TOKENS} cumulative tokens",
        f"- Observed cumulative usage: `{json.dumps(usage, sort_keys=True)}`",
        f"- Original task summary: {task_summary}",
        "- Raw evidence artifacts (inspect selectively; never paste wholesale):",
        *(f"  - `{path}`" for path in stream_artifacts),
        "",
        "Continue from repository state plus this receipt. Do not replay or recover the prior transcript.",
    ]
    durable_replace_text(target, "\n".join(lines).rstrip() + "\n")
    return target.relative_to(root).as_posix()


def _codex_usage_block(summary: dict | None, session_id: str) -> dict:
    if summary is None:
        return {
            "orchestrator": {"input": 0, "output": 0},
            "subagents": [],
            "workbenches": [{
                "tool": "codex", "session_id": session_id,
                "input": 0, "fresh_input": 0, "cached_input": 0,
                "output": 0, "reasoning": 0,
                "context_pct_at_close": UNAVAILABLE_CLI_VALUE,
                "source": "unavailable",
            }],
            "totals": {"input": 0, "output": 0},
            "est_cost_usd": 0.0,
            "unavailable": ["Codex token usage", "Codex model identity", "codex.context_pct_at_close"],
        }
    normalized = normalize_codex_usage(
        summary["input"], summary.get("cached"), summary["output"], summary.get("reasoning")
    )
    unavailable = ["Codex model identity", "cost for unavailable Codex model", "codex.context_pct_at_close"]
    if summary.get("cached") is None:
        unavailable.extend(["codex.cached_input", "codex.fresh_input", "codex.cache_ratio"])
    if summary.get("reasoning") is None:
        unavailable.append("codex.reasoning")
    return {
        "orchestrator": {"input": 0, "output": 0},
        "subagents": [],
        "workbenches": [{
            "tool": "codex",
            "session_id": session_id,
            **normalized,
            "context_pct_at_close": UNAVAILABLE_CLI_VALUE,
            "source": "reported",
        }],
        "totals": {"input": summary["input"], "output": summary["output"]},
        "est_cost_usd": 0.0,
        "unavailable": unavailable,
    }


def _codex_capture_evidence(
    summary: dict | None,
    cli_version: str,
    source: str,
    invocation: dict | None = None,
) -> dict:
    if summary is None:
        evidence = {
            "source": source,
            "captured_after_process_exit": True,
            "summary_format": "unavailable",
            "cli_version": cli_version or "unavailable",
            "model_identity": "unavailable",
        }
        if invocation:
            evidence["invocation"] = invocation
        return evidence
    evidence = {
        "source": source,
        "captured_after_process_exit": True,
        "raw_summary": summary["raw_summary"],
        "summary_format": summary.get("summary_format", "unavailable"),
        "input_tokens": summary["input"],
        "provider_total_input_tokens": summary["input"],
        "output_tokens": summary["output"],
        "total_tokens": summary["total"],
        "cli_version": cli_version or "unavailable",
        "model_identity": "unavailable",
        "component_scope": {
            "orchestrator": "not invoked by direct Codex launch",
            "subagents": "none invoked",
            "workbench": "Codex CLI reported exact usage",
        },
    }
    if summary.get("cached") is not None:
        evidence["cached_input_tokens"] = summary["cached"]
        evidence["fresh_input_tokens"] = summary["input"] - summary["cached"]
        evidence["cache_ratio"] = round(
            summary["cached"] / max(summary["input"] - summary["cached"], 1), 6
        )
    if summary.get("reasoning") is not None:
        evidence["reasoning_output_tokens"] = summary["reasoning"]
    if summary.get("terminal_summary_cross_check"):
        evidence["terminal_summary_cross_check"] = summary["terminal_summary_cross_check"]
    if invocation:
        evidence["invocation"] = invocation
    return evidence


def _codex_usage_counters(summary: dict | None) -> dict:
    if not isinstance(summary, dict):
        return _unavailable_codex_counters()
    counters = summary.get("usage_counters")
    if not isinstance(counters, dict):
        return _unavailable_codex_counters()
    return {
        key: counters.get(key)
        if _coerce_int(counters.get(key)) is not None
        else UNAVAILABLE_CLI_VALUE
        for key in CODEX_COUNTER_FIELDS
    }


def _replace_receipt_token_usage(
    root: Path,
    item_id: str,
    receipt_path: str,
    payload: dict,
) -> None:
    md = root / receipt_path
    if not md.is_file() or md.suffix.lower() != ".md":
        raise QueueError(f"Codex reconciliation receipt not found: {receipt_path}")
    marker = f"<!-- token_usage:{item_id} -->"
    replacement = f"{marker}\n## token_usage\n```json\n{json.dumps(payload, indent=2)}\n```"
    existing = md.read_text(encoding="utf-8")
    block_re = re.compile(
        rf"{re.escape(marker)}\s*\n## token_usage\s*\n```json\s*\n.*?\n```",
        re.DOTALL,
    )
    blocks = list(block_re.finditer(existing))
    if len(blocks) > 1:
        updated = block_re.sub("", existing).rstrip() + "\n\n" + replacement + "\n"
    elif blocks:
        updated = block_re.sub(replacement, existing, count=1)
    elif marker in existing:
        raise QueueError(f"Malformed existing token_usage block in {receipt_path}")
    else:
        placeholder_re = re.compile(
            r"(?im)^\s*(?:-\s*)?Token usage:\s*(?:unavailable(?: from current CLI output)?\.?|no agent invocation)\s*$"
        )
        placeholders = list(placeholder_re.finditer(existing))
        if len(placeholders) > 1:
            updated = placeholder_re.sub("", existing).rstrip() + "\n\n" + replacement + "\n"
        elif placeholders:
            updated = placeholder_re.sub(replacement, existing, count=1)
        else:
            updated = existing.rstrip() + "\n\n" + replacement + "\n"
    updated = updated if updated.endswith("\n") else updated + "\n"
    if updated != existing:
        durable_replace_text(md, updated)


@locked_queue_mutation
def reconcile_codex_usage(
    root: Path,
    item_id: str,
    summary: dict | None,
    cli_version: str,
    session_id: str,
    *,
    source: str = "Codex supervisor final structured usage event",
    invocation: dict | None = None,
) -> dict:
    """Reconcile one Codex invocation independently of the queue status lifecycle."""
    runtime_invocation = invocation
    item = find_item(load_items(root), item_id)
    if not session_id.strip():
        raise QueueError("Codex reconciliation requires an explicit session ID")
    session_id = session_id.strip()
    if summary is not None:
        _validate_codex_summary(summary)
    receipt_path = _latest_receipt_path(item, None)
    if not receipt_path:
        raise QueueError(f"{item_id} has no receipt for Codex token reconciliation")

    ledger_path = root / TOKEN_LEDGER_PATH
    rows: list[dict] = []
    matches: list[int] = []
    ledger_text = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
    for line_number, raw in enumerate(ledger_text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise QueueError(f"Invalid token ledger JSONL at line {line_number}") from exc
        if row.get("item_id") == item_id and row.get("session_id") == session_id:
            matches.append(len(rows))
        rows.append(row)
    if len(matches) > 1:
        raise QueueError(f"Duplicate token-ledger identity for {item_id} + {session_id}")

    block = _codex_usage_block(summary, session_id)
    evidence = _codex_capture_evidence(summary, cli_version, source, runtime_invocation)
    counters = _codex_usage_counters(summary)
    existing = rows[matches[0]] if matches else None
    if existing:
        existing_workbenches = (existing.get("token_usage") or {}).get("workbenches") or []
        existing_exact = any(work.get("tool") == "codex" and work.get("source") == "reported" for work in existing_workbenches)
        if existing_exact and summary is None:
            reconciled = existing
            block = existing["token_usage"]
            evidence = existing.get("capture_evidence") or evidence
            counters = {key: existing.get(key, UNAVAILABLE_CLI_VALUE) for key in CODEX_COUNTER_FIELDS}
        elif existing_exact:
            old = existing.get("capture_evidence") or {}
            old_values = (
                old.get("input_tokens"), old.get("output_tokens"), old.get("total_tokens"),
                old.get("cached_input_tokens"), old.get("reasoning_output_tokens"),
            )
            new_values = (
                summary["input"], summary["output"], summary["total"],
                summary.get("cached"), summary.get("reasoning"),
            )
            if old_values != new_values:
                raise QueueError(f"Conflicting exact Codex usage for {item_id} + {session_id}")
            reconciled = existing
            block = existing["token_usage"]
            evidence = existing.get("capture_evidence") or evidence
        else:
            reconciled = {**existing, "model_confirmed": "unavailable", "token_usage": block, "capture_evidence": evidence}
    else:
        reconciled = {
            "item_id": item_id,
            "session_id": session_id,
            "invocation_id": session_id,
            "event": "codex_process_exit",
            "lane": item.get("owner") or "codex",
            "profile": "default",
            "timestamp": now_iso(),
            "escalated": False,
            "model_requested": "Codex workbench session",
            "model_confirmed": "unavailable",
            "budget_class": _derive_budget_class(item, None),
            "token_usage": block,
            "capture_evidence": evidence,
            "effect_id": f"codex:{item_id}:{session_id}:tokens",
        }
        if runtime_invocation:
            reconciled["invocation"] = runtime_invocation
    reconciled.update(counters)
    reconciled["warnings"] = token_usage_warnings(block)
    token_err = _validate_against_schema(reconciled, root / TOKEN_LEDGER_SCHEMA_PATH)
    if token_err:
        raise QueueError(f"reconciled token_ledger line failed schema: {token_err}")

    profile_invocation = {
        "invoked": True,
        "tool": "codex",
        "session_id": session_id,
        "lifecycle": "process_exit",
        "queue_status_at_reconciliation": item.get("status"),
        **({"runtime_policy": runtime_invocation} if runtime_invocation else {}),
    }
    payload = {
        "token_usage": block,
        "profile_invocation": profile_invocation,
        "capture_evidence": evidence,
        "warnings": token_usage_warnings(block),
        **counters,
    }
    if matches:
        rows[matches[0]] = reconciled
    else:
        rows.append(reconciled)
    reconciled_ledger_text = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
    if reconciled_ledger_text != ledger_text:
        durable_replace_text(ledger_path, reconciled_ledger_text)
    sidecar = root / RECEIPTS_DIR / f"{item_id}.token_usage.json"
    sidecar_text = json.dumps(payload, indent=2) + "\n"
    existing_sidecar_text = sidecar.read_text(encoding="utf-8") if sidecar.exists() else ""
    if sidecar_text != existing_sidecar_text:
        durable_replace_text(sidecar, sidecar_text)
    _replace_receipt_token_usage(root, item_id, receipt_path, payload)
    return {
        "item_id": item_id,
        "session_id": session_id,
        "queue_status": item.get("status"),
        "receipt": receipt_path,
        "token_usage_sidecar": str(sidecar.relative_to(root)),
        "token_usage": block,
        "capture_evidence": evidence,
    }


def run_codex_work_item(
    root: Path,
    item_id: str,
    prompt: str,
    *,
    _handoff_depth: int = 0,
    execution_timeout_seconds: float = CODEX_EXECUTION_TIMEOUT_SECONDS,
) -> dict:
    """Run Codex noninteractively, capture both streams, wait, and reconcile."""
    find_item(load_items(root), item_id)  # explicit association must exist before launch
    try:
        invocation = validate_codex_runtime(root, CODEX_TARGET)
        command = build_codex_exec_command(CODEX_TARGET)
        env = build_codex_environment(CODEX_TARGET)
        prepared_prompt = prepare_codex_fresh_prompt(prompt)
    except CodexPolicyError as exc:
        raise QueueError(str(exc)) from exc
    version_proc = subprocess.run(
        [str(CODEX_TARGET.executable), "--version"],
        cwd=str(CODEX_TARGET.root), env=env,
        capture_output=True, text=True, timeout=20, check=False,
    )
    cli_version = ((version_proc.stdout or "") + (version_proc.stderr or "")).strip() or "unavailable"
    proc = subprocess.Popen(
        command,
        cwd=CODEX_TARGET.root,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
        close_fds=True,
    )
    try:
        stdout, stderr = proc.communicate(prepared_prompt, timeout=execution_timeout_seconds)
    except subprocess.TimeoutExpired:
        # Popen accumulates partial output across communicate() calls, so the
        # post-kill call below returns the complete captured stdout/stderr
        # (the documented pattern for handling TimeoutExpired) rather than
        # only what arrived after the timeout.
        proc.kill()
        stdout, stderr = proc.communicate()
    combined = "\n".join(part for part in (stdout, stderr) if part)
    try:
        session_id = require_clean_session_id(combined or "")
    except CodexPolicyError as exc:
        _write_codex_stream_artifacts(root, f"clean-session-failed-{proc.pid}", stdout or "", stderr or "")
        raise QueueError(str(exc)) from exc
    stream_artifacts = _write_codex_stream_artifacts(root, session_id, stdout or "", stderr or "")
    try:
        summary = parse_codex_token_summary(combined or "")
    except QueueError as exc:
        if "without a parseable final token summary" not in str(exc):
            raise
        result = reconcile_codex_usage(
            root, item_id, None, cli_version, session_id,
            source="Codex supervisor process exit; usage unavailable",
            invocation=invocation,
        )
    else:
        source = (
            "Codex supervisor final structured usage event"
            if summary.get("summary_format") == "turn.completed JSONL"
            else "Codex supervisor final terminal usage summary"
        )
        result = reconcile_codex_usage(
            root, item_id, summary, cli_version, session_id,
            source=source, invocation=invocation,
        )
    if proc.returncode != 0:
        raise QueueError(f"Codex exited with status {proc.returncode}; process-exit usage was reconciled")
    snapshot = cumulative_usage_snapshot(combined or "")
    if snapshot.get("available") and int(snapshot["cumulative_tokens"]) >= CONTEXT_HANDOFF_THRESHOLD_TOKENS:
        handoff_artifact = _write_codex_context_handoff(
            root, session_id, item_id, prompt, snapshot, stream_artifacts,
        )
        if _handoff_depth >= MAX_CONTEXT_HANDOFFS:
            raise QueueError(
                f"Codex reached the context handoff boundary after {MAX_CONTEXT_HANDOFFS} fresh continuations; "
                f"latest handoff: {handoff_artifact}"
            )
        continuation_prompt = "\n".join((
            "Continue the same bounded queue task in a new fresh ephemeral session.",
            f"Read the compact handoff receipt at `{handoff_artifact}` and inspect only its named repository/artifact paths as needed.",
            "Do not resume, recover, or replay the prior transcript. Do not paste raw logs, test output, diffs, screenshots, or browser evidence into this prompt or your closeout.",
            "Complete the remaining task, validate it, and return the required compact receipt.",
        ))
        continued = run_codex_work_item(
            root, item_id, continuation_prompt,
            _handoff_depth=_handoff_depth + 1,
            execution_timeout_seconds=execution_timeout_seconds,
        )
        return {
            **continued,
            "handoff_sessions": [{
                "session_id": session_id,
                "token_usage": result["token_usage"],
                "handoff_artifact": handoff_artifact,
                "stream_artifacts": stream_artifacts,
                "threshold_usage": snapshot,
            }, *list(continued.get("handoff_sessions") or [])],
            "handoff_artifacts": [handoff_artifact, *list(continued.get("handoff_artifacts") or [])],
            "stream_artifacts": [*stream_artifacts, handoff_artifact, *list(continued.get("stream_artifacts") or [])],
            "retained_output_truncated": bool(continued.get("retained_output_truncated")) or len(stdout or "") > 16_000 or len(stderr or "") > 16_000,
        }
    return {
        **result,
        "returncode": proc.returncode,
        "stdout": (stdout or "") if len(stdout or "") <= 16_000 else (stdout or "")[-4_000:],
        "stderr": (stderr or "") if len(stderr or "") <= 16_000 else (stderr or "")[-4_000:],
        "stream_artifacts": stream_artifacts,
        "retained_output_truncated": len(stdout or "") > 16_000 or len(stderr or "") > 16_000,
        "invocation": invocation,
    }


def finalize_done(
    root: Path,
    item: dict,
    *,
    receipt_path: str | None = None,
    usage_file: str | None = None,
    token_usage_json: dict | None = None,
    budget_class: str | None = None,
    escalated: bool = False,
    review: str | None = None,
    model_requested: str | None = None,
    model_confirmed: str | None = None,
    skill: str | None = None,
    effect_id: str | None = None,
    effect_timestamp: str | None = None,
) -> dict:
    """Run the coordinator side-effects for a real transition into `done`:
    profile resolution/invocation, dual ledger write, and token metering.

    Returns a close record (for stdout). Raises QueueError — refusing the
    done-transition outright, before any file is written — if the token_usage
    block cannot be built with the required keys, or if the assembled run/token
    ledger lines fail schema validation. Callers must call this before
    persisting status=done, so a refusal here leaves the item's prior status
    untouched (hooks/token_budget_check.md).
    """
    route = resolve_route(root, item.get("owner"))
    invocation = probe_profile_invocation(route["profile_requested"], route["fallback_profile"])

    block, confirmed = build_token_usage(route, usage_file=usage_file, token_usage_json=token_usage_json)
    required_keys = {"orchestrator", "subagents", "workbenches", "totals", "est_cost_usd", "unavailable"}
    if not required_keys.issubset(block):
        raise QueueError("token_usage block incomplete; refusing done-transition (hooks/token_budget_check.md)")

    resolved_budget = _derive_budget_class(item, budget_class)
    resolved_skill = _derive_skill(item, skill)
    resolved_receipt = _latest_receipt_path(item, receipt_path)
    routes_meta = load_model_routes(root).get("routes", {}).get(route["lane"], {})
    resolved_model_requested = model_requested or routes_meta.get("model") or "configured externally"
    resolved_model_confirmed = model_confirmed or confirmed or "unavailable"
    block = _recompute_totals_and_cost(block, load_prices(), resolved_model_confirmed)
    timestamp = effect_timestamp or now_iso()
    # The sidecar path is deterministic from item id alone, so it can be used
    # in run_line for schema validation before the file is actually written.
    sidecar_rel_path = str(RECEIPTS_DIR / f"{item['id']}.token_usage.json")

    run_line = {
        "item_id": item["id"],
        "lane": route["lane"],
        "profile": route["profile_requested"],
        "skill": resolved_skill,
        "created": item.get("created_at", timestamp),
        "done": timestamp,
        "status": DONE_STATUS,
        "escalated": bool(escalated),
        "review": review or "pending",
        "budget_class": resolved_budget,
        "receipt": resolved_receipt or sidecar_rel_path,
        "memory_promotion": [str(value) for value in item.get("memory_promotion") or []],
    }
    context_fields_present = any(
        key in item for key in ("client_scope", "context_classification", "brain_context_status", "brain_context_used", "degraded_context")
    )
    if context_fields_present:
        try:
            validated_context = validate_completion_context(
                item,
                brain_context_used=item.get("brain_context_used") or [],
                brain_context_status=item.get("brain_context_status"),
                degraded_context=item.get("degraded_context"),
            )
        except BrainContextError as exc:
            raise QueueError(f"context validation failed; status must be needs_input: {exc}") from exc
        if validated_context.get("brain_context_used"):
            run_line["brain_context_status"] = "used"
            run_line["brain_context_used"] = validated_context["brain_context_used"]
        elif item.get("brain_context_status"):
            run_line["brain_context_status"] = item["brain_context_status"]
        if validated_context.get("degraded_context"):
            run_line["degraded_context"] = validated_context["degraded_context"]
    token_line = {
        "item_id": item["id"],
        "lane": route["lane"],
        "profile": route["profile_requested"],
        "timestamp": timestamp,
        "escalated": bool(escalated),
        "model_requested": resolved_model_requested,
        "model_confirmed": resolved_model_confirmed,
        "budget_class": resolved_budget,
        "token_usage": block,
        **_unavailable_codex_counters(),
    }

    # Hard block: a line that fails schema validation must never be appended
    # (finding #2). Validated before any file is touched, so a failure here
    # leaves the ledgers, the sidecar, and the item's status all unchanged.
    run_err = _validate_against_schema(run_line, root / RUN_LEDGER_SCHEMA_PATH)
    if run_err:
        raise QueueError(f"run_ledger line failed schema; refusing done-transition: {run_err}")
    token_err = _validate_against_schema(token_line, root / TOKEN_LEDGER_SCHEMA_PATH)
    if token_err:
        raise QueueError(f"token_ledger line failed schema; refusing done-transition: {token_err}")

    sidecar_path = _write_receipt_token_usage(
        root, item["id"], resolved_receipt, block, invocation, _unavailable_codex_counters()
    )
    stable_effect = effect_id or f"done:{item['id']}:{timestamp}"
    _append_jsonl(root, root / RUN_LEDGER_PATH, run_line, effect_id=f"{stable_effect}:run")
    _append_jsonl(root, root / TOKEN_LEDGER_PATH, token_line, effect_id=f"{stable_effect}:tokens")

    return {
        "item_id": item["id"],
        "route": route,
        "profile_invocation": invocation,
        "run_ledger_line": run_line,
        "token_ledger_line": token_line,
        "token_usage_sidecar": sidecar_path,
        "effect_id": stable_effect,
    }


def _done_effect_id(item: dict, receipt_path: str | None, mode: str) -> str:
    material = "\0".join([str(item.get("id") or ""), mode, receipt_path or "", str(item.get("updated_at") or "")])
    return "done:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _prepare_done_intent(root: Path, items: list[dict], item: dict, effect_id: str, receipt_path: str | None) -> dict:
    effects = item.setdefault("transition_effects", {})
    intent = effects.get(effect_id)
    if intent is None:
        intent = {"kind": "done", "status": "pending", "created_at": now_iso(), "receipt_path": receipt_path}
        effects[effect_id] = intent
        # No auxiliary effect may run until the intent is durably visible in
        # the authoritative queue. A surfaced post-replace ambiguity is safe:
        # retry reloads this same deterministic intent.
        save_items(root, items)
    elif not isinstance(intent, dict) or intent.get("kind") != "done" or intent.get("receipt_path") != receipt_path:
        raise QueueError(f"contradictory done transition intent for {item.get('id')}")
    return intent


def _finish_done(root: Path, items: list[dict], item: dict, effect_id: str, intent: dict, receipt_path: str | None) -> None:
    timestamp = intent["created_at"]
    if receipt_path and not any(
        isinstance(row, dict) and row.get("path") == receipt_path and row.get("status") == DONE_STATUS
        for row in item.get("receipts", [])
    ):
        item.setdefault("receipts", []).append({"path": receipt_path, "created_at": timestamp, "status": DONE_STATUS})
    item["status"] = DONE_STATUS
    item["updated_at"] = timestamp
    intent["status"] = "applied"
    save_items(root, items)


def _load_json_arg(value: str | None) -> dict | None:
    """Parse a JSON argument that may be inline JSON or @path/to/file.json."""
    if not value:
        return None
    if value.startswith("@"):
        return _read_json_or(None, Path(value[1:]))
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise QueueError(f"Invalid JSON argument: {exc}") from exc


@locked_queue_mutation
def create_item(root: Path, args: argparse.Namespace) -> dict:
    ensure_queue(root)
    validate_status(args.status)
    if args.owner_type not in APPROVED_OWNER_TYPES:
        raise QueueError(f"Invalid owner_type: {args.owner_type}; use agent or workflow")
    if args.owner and args.owner_type == "agent" and args.owner != "unassigned":
        validate_agent(root, args.owner)
    items = load_items(root)
    idempotency_key = str(getattr(args, "idempotency_key", "") or "").strip()
    if idempotency_key:
        for existing in items:
            dispatch = existing.get("dispatch")
            if isinstance(dispatch, dict) and dispatch.get("idempotency_key") == idempotency_key:
                setattr(args, "idempotency_duplicate", True)
                return existing
    timestamp = now_iso()
    item = {
        "id": next_id(items, timestamp),
        "title": args.title,
        "status": args.status,
        "priority": args.priority,
        "requested_by": args.requested_by,
        "owner_type": args.owner_type,
        "owner": args.owner,
        "source": args.source,
        "tags": split_csv(args.tags),
        "context": args.context,
        "sources": split_csv(args.sources),
        "allowed_actions": split_csv(args.allowed_actions),
        "stop_conditions": split_csv(args.stop_conditions),
        "definition_of_done": args.definition_of_done,
        "parent_id": getattr(args, "parent_id", None) or None,
        "step_index": getattr(args, "step_index", None),
        "depends_on": split_csv(getattr(args, "depends_on", "")),
        "on_complete": getattr(args, "on_complete", None) or None,
        "workbench": getattr(args, "workbench", None) or None,
        "review": getattr(args, "review", None) or "none",
        "claim": {"claimed_by": None, "claimed_at": None},
        "receipts": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    if idempotency_key:
        item["dispatch"] = {
            "idempotency_key": idempotency_key,
            "inbound_route": str(getattr(args, "inbound_route", "") or ""),
            "delivery_id": str(getattr(args, "delivery_id", "") or ""),
            "reply_to": str(getattr(args, "reply_to", "") or ""),
            "accepted_at": timestamp,
        }
        setattr(args, "idempotency_duplicate", False)
    optional_values = {
        "client_scope": getattr(args, "client_scope", None),
        "context_classification": getattr(args, "context_classification", None),
        "brain_context_status": getattr(args, "brain_context_status", None),
        "brain_context_used": _load_json_arg(getattr(args, "brain_context_used", None)),
        "degraded_context": _load_json_arg(getattr(args, "degraded_context", None)),
        "promotion_proposal": _load_json_arg(getattr(args, "promotion_proposal", None)),
        "capture_proposal": _load_json_arg(getattr(args, "capture_proposal", None)),
        "run_prompt_path": getattr(args, "run_prompt_path", None),
        "needs_me": getattr(args, "needs_me", None),
    }
    for key, value in optional_values.items():
        if value is not None and value != "":
            item[key] = value
    items.append(item)
    save_items(root, items)
    return item


def list_items(root: Path, status: str | None = None, owner: str | None = None) -> list[dict]:
    if status:
        validate_status(status)
    items = load_items(root)
    if status:
        items = [item for item in items if item.get("status") == status]
    if owner:
        items = [item for item in items if item.get("owner") == owner]
    return sorted(items, key=lambda item: (-int(item.get("priority", 0)), item.get("created_at", ""), item.get("id", "")))


@locked_queue_mutation
def claim_item(root: Path, item_id: str, agent_id: str) -> dict:
    validate_agent(root, agent_id)
    items = load_items(root)
    item = find_item(items, item_id)
    if item.get("owner_type") == "workflow":
        raise QueueError(f"{item_id} is a workflow aggregate and cannot be claimed")
    claimed_by = (item.get("claim") or {}).get("claimed_by")
    if claimed_by:
        raise ClaimConflictError(
            f"Work item already claimed by {claimed_by}; claims are exclusive even for the same agent: {item_id}"
        )
    if item.get("status") == "agent_working":
        raise ClaimConflictError(f"Work item is already agent_working and cannot be claimed: {item_id}")
    timestamp = now_iso()
    item["claim"] = {"claimed_by": agent_id, "claimed_at": timestamp}
    item["worker_heartbeat_at"] = timestamp
    item["status"] = "agent_working"
    item["updated_at"] = timestamp
    save_items(root, items)
    return item


@locked_queue_mutation
def renew_claim(root: Path, item_id: str, agent_id: str) -> dict:
    """Renew the existing worker claim without changing queue ownership or status."""
    items = load_items(root)
    item = find_item(items, item_id)
    claimed_by = str((item.get("claim") or {}).get("claimed_by") or "")
    if item.get("status") != "agent_working" or claimed_by != agent_id:
        raise QueueError(f"Work item claim is not active for {agent_id}: {item_id}")
    timestamp = now_iso()
    item["worker_heartbeat_at"] = timestamp
    item["updated_at"] = timestamp
    save_items(root, items)
    return item


@locked_queue_mutation
def register_worker_runtime(
    root: Path,
    item_id: str,
    agent_id: str,
    pid: int,
    process_start_id: str,
    route: str,
) -> dict:
    """Bind an active claim to an exact Linux process identity.

    The PID alone is not sufficient because it can be reused after a worker
    exits.  Recovery readers compare both values before treating a stale
    heartbeat as abandoned.
    """
    items = load_items(root)
    item = find_item(items, item_id)
    claimed_by = str((item.get("claim") or {}).get("claimed_by") or "")
    if item.get("status") != "agent_working" or claimed_by != agent_id:
        raise QueueError(f"Work item claim is not active for {agent_id}: {item_id}")
    if int(pid) < 1 or not str(process_start_id or "").strip():
        raise QueueError("Worker runtime identity is incomplete")
    timestamp = now_iso()
    item["worker_runtime"] = {
        "pid": int(pid),
        "process_start_id": str(process_start_id),
        "route": str(route or agent_id),
        "registered_at": timestamp,
    }
    item["worker_heartbeat_at"] = timestamp
    item["updated_at"] = timestamp
    save_items(root, items)
    return item


@locked_queue_mutation
def release_item(root: Path, item_id: str, status: str) -> dict:
    """Release a claim, setting the requested status. A transition into `done`
    runs finalize_done first (see update_status): the claim is cleared only
    after finalize_done succeeds, so a refusal leaves the item — including its
    claim — unmodified. Releasing an already-done item just clears the claim."""
    validate_status(status)
    items = load_items(root)
    item = find_item(items, item_id)
    previous_status = item.get("status")
    if status == DONE_STATUS and previous_status != DONE_STATUS:
        effect_id = _done_effect_id(item, None, "release")
        intent = _prepare_done_intent(root, items, item, effect_id, None)
        finalize_done(root, item, effect_id=effect_id, effect_timestamp=intent["created_at"])
        item["claim"] = {"claimed_by": None, "claimed_at": None}
        item["worker_heartbeat_at"] = None
        item.pop("worker_runtime", None)
        _finish_done(root, items, item, effect_id, intent, None)
        return item
    timestamp = now_iso()
    item["claim"] = {"claimed_by": None, "claimed_at": None}
    item["worker_heartbeat_at"] = None
    item.pop("worker_runtime", None)
    item["status"] = status
    item["updated_at"] = timestamp
    save_items(root, items)
    return item


@locked_queue_mutation
def update_status(root: Path, item_id: str, status: str) -> dict:
    """Update an item's status. A transition into `done` runs finalize_done
    first: if the token_usage block can't be built or fails schema validation,
    finalize_done raises and this function propagates it without saving —
    the item's prior status stands (hooks/token_budget_check.md)."""
    validate_status(status)
    items = load_items(root)
    item = find_item(items, item_id)
    previous_status = item.get("status")
    if status == DONE_STATUS and previous_status != DONE_STATUS:
        effect_id = _done_effect_id(item, None, "status")
        intent = _prepare_done_intent(root, items, item, effect_id, None)
        finalize_done(root, item, effect_id=effect_id, effect_timestamp=intent["created_at"])
        _finish_done(root, items, item, effect_id, intent, None)
        return item
    item["status"] = status
    item["updated_at"] = now_iso()
    save_items(root, items)
    return item


@locked_queue_mutation
def attach_receipt(root: Path, item_id: str, receipt_path: str, status: str | None = None) -> dict:
    """Attach a receipt, optionally setting status. A transition into `done`
    runs finalize_done first (see update_status) so a refusal leaves the item
    unmodified — no receipt attached, no status change, nothing saved."""
    if status:
        validate_status(status)
    items = load_items(root)
    item = find_item(items, item_id)
    previous_status = item.get("status")
    timestamp = now_iso()
    if status == DONE_STATUS and previous_status != DONE_STATUS:
        effect_id = _done_effect_id(item, receipt_path, "receipt")
        intent = _prepare_done_intent(root, items, item, effect_id, receipt_path)
        finalize_done(
            root, item, receipt_path=receipt_path, effect_id=effect_id,
            effect_timestamp=intent["created_at"],
        )
        _finish_done(root, items, item, effect_id, intent, receipt_path)
        return item
    receipt = {"path": receipt_path, "created_at": timestamp}
    if status:
        receipt["status"] = status
        item["status"] = status
    item.setdefault("receipts", []).append(receipt)
    item["updated_at"] = timestamp
    save_items(root, items)
    return item


@locked_queue_mutation
def done_item(root: Path, args: argparse.Namespace) -> dict:
    """Explicit coordinator close: run the metering/ledger side-effects with
    full metadata first, then attach the optional receipt and set status done.
    A token_usage block that cannot be built or fails schema validation raises
    from finalize_done before anything is saved (hooks/token_budget_check.md)."""
    items = load_items(root)
    item = find_item(items, args.item_id)
    previous_status = item.get("status")

    if previous_status == DONE_STATUS and not args.reclose:
        print(
            f"NEEDS ATTENTION: {args.item_id} was already done; skipped ledger append "
            "(pass --reclose to force).",
            file=sys.stderr,
        )
        return item

    # finalize_done only reads item fields already present (owner, tags,
    # created_at, receipts) — the pending receipt path is passed explicitly,
    # so it need not be attached in memory first for route/budget resolution.
    effect_id = _done_effect_id(item, args.receipt, "reclose" if args.reclose else "done")
    intent = _prepare_done_intent(root, items, item, effect_id, args.receipt)
    record = finalize_done(
        root,
        item,
        receipt_path=args.receipt,
        usage_file=args.usage_file,
        token_usage_json=_load_json_arg(args.token_usage),
        budget_class=args.budget_class,
        escalated=args.escalated,
        review=args.review,
        model_requested=args.model_requested,
        model_confirmed=args.model_confirmed,
        skill=args.skill,
        effect_id=effect_id,
        effect_timestamp=intent["created_at"],
    )
    _finish_done(root, items, item, effect_id, intent, args.receipt)
    return record


def item_is_available_for(item: dict, agent_id: str) -> bool:
    if item.get("owner_type") == "workflow":
        return False
    if item.get("status") not in AVAILABLE_STATUSES:
        return False
    if item.get("claim", {}).get("claimed_by"):
        return False
    owner = item.get("owner")
    return owner in {"", "unassigned", agent_id}


def next_item(root: Path, agent_id: str) -> dict | None:
    validate_agent(root, agent_id)
    candidates = [item for item in load_items(root) if item_is_available_for(item, agent_id)]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (-int(item.get("priority", 0)), item.get("created_at", ""), item.get("id", "")))[0]


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def print_item_table(items: list[dict]) -> None:
    for item in items:
        claimed_by = item.get("claim", {}).get("claimed_by") or "-"
        print(f"{item['id']}\t{item['status']}\t{item['priority']}\t{item['owner']}\t{claimed_by}\t{item['title']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Agentic OS work queue")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a local work item")
    create.add_argument("--title", required=True)
    create.add_argument("--requested-by", default="local")
    create.add_argument("--owner-type", default="agent")
    create.add_argument("--owner", default="unassigned")
    create.add_argument("--status", default="inbox")
    create.add_argument("--priority", type=int, default=0)
    create.add_argument("--source", default="local")
    create.add_argument("--tags", default="")
    create.add_argument("--context", default="")
    create.add_argument("--sources", default="")
    create.add_argument("--allowed-actions", default="")
    create.add_argument("--stop-conditions", default="")
    create.add_argument("--definition-of-done", default="")
    create.add_argument("--parent-id", default="")
    create.add_argument("--step-index", type=int)
    create.add_argument("--depends-on", default="")
    create.add_argument("--on-complete", default="")
    create.add_argument("--workbench", default="")
    create.add_argument("--review", choices=["none", "model"], default="none")
    create.add_argument("--client-scope", default="")
    create.add_argument("--context-classification", choices=["knowledge_sensitive", "technical_only", "ambiguous"])
    create.add_argument("--brain-context-status", choices=["used", "not_applicable", "degraded", "missing"])
    create.add_argument("--brain-context-used", help="Structured JSON or @path for actual successful Brain reads")
    create.add_argument("--degraded-context", help="Structured JSON or @path for an explicit safe degradation contract")
    create.add_argument("--promotion-proposal", help="Structured review-tier proposal JSON or @path")
    create.add_argument("--capture-proposal", help="Structured metadata-only capture proposal JSON or @path")

    list_parser = subparsers.add_parser("list", help="List local work items")
    list_parser.add_argument("--status")
    list_parser.add_argument("--owner")
    list_parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")

    show = subparsers.add_parser("show", help="Show one work item")
    show.add_argument("item_id")

    claim = subparsers.add_parser("claim", help="Claim a work item for an agent")
    claim.add_argument("item_id")
    claim.add_argument("agent_id")

    release = subparsers.add_parser("release", help="Release a work item claim")
    release.add_argument("item_id")
    release.add_argument("--status", default="agent_todo")

    receipt = subparsers.add_parser("receipt", help="Attach a receipt path: receipt ITEM_ID RECEIPT_PATH [--status STATUS]")
    receipt.add_argument("item_id", metavar="ITEM_ID")
    receipt.add_argument("receipt_path", metavar="RECEIPT_PATH")
    receipt.add_argument("--status", metavar="STATUS", help="Optional approved status to set after attaching the receipt")

    status = subparsers.add_parser("status", help="Update item status: status ITEM_ID STATUS")
    status.add_argument("item_id", metavar="ITEM_ID")
    status.add_argument("status", metavar="STATUS", help="Approved status value such as human_review, done, or blocked")

    next_parser = subparsers.add_parser("next", help="Show the highest-priority available item for an agent")
    next_parser.add_argument("agent_id")

    done = subparsers.add_parser(
        "done",
        help="Close an item: resolve lane->profile, write run+token ledgers, meter tokens",
    )
    done.add_argument("item_id", metavar="ITEM_ID")
    done.add_argument("--receipt", metavar="RECEIPT_PATH", help="Receipt path to attach on close")
    done.add_argument("--usage-file", metavar="PATH", help="Hermes one-shot --usage-file JSON (harness usage source)")
    done.add_argument("--token-usage", metavar="JSON", help="Pre-assembled token_usage block: inline JSON or @path.json")
    done.add_argument("--budget-class", choices=sorted(BUDGET_CLASSES), help="Override budget class (else derived from tags)")
    done.add_argument("--skill", help="Skill name for the run ledger (else derived from tags)")
    done.add_argument("--review", choices=["ACCEPT", "REVISE", "pending"], help="Review outcome for the run ledger")
    done.add_argument("--model-requested", help="Model requested for the token ledger")
    done.add_argument("--model-confirmed", help="Model confirmed for the token ledger")
    done.add_argument("--escalated", action="store_true", help="Mark the run as escalated")
    done.add_argument("--reclose", action="store_true", help="Force ledger append even if already done")

    codex_run = subparsers.add_parser(
        "codex-run",
        help="Run Codex exec for an explicit item, wait for exit, and reconcile its final token summary",
    )
    codex_run.add_argument("item_id", metavar="ITEM_ID")
    codex_run.add_argument(
        "--prompt-file",
        default="-",
        metavar="PATH",
        help="Prompt file, or - to read the complete prompt from stdin (default)",
    )
    codex_reconcile = subparsers.add_parser(
        "codex-reconcile",
        help="Reconcile pasted final Codex CLI evidence for one explicit item/session",
    )
    codex_reconcile.add_argument("item_id", metavar="ITEM_ID")
    codex_reconcile.add_argument("--session-id", required=True, help="Exact Codex session ID")
    codex_reconcile.add_argument("--summary", required=True, help="Exact final Codex Token usage: summary")
    codex_reconcile.add_argument("--cli-version", default="unavailable", help="Exact codex --version output when known")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        if args.command == "create":
            print_json(create_item(root, args))
        elif args.command == "list":
            items = list_items(root, args.status, args.owner)
            print_json(items) if args.json else print_item_table(items)
        elif args.command == "show":
            print_json(find_item(load_items(root), args.item_id))
        elif args.command == "claim":
            print_json(claim_item(root, args.item_id, args.agent_id))
        elif args.command == "release":
            print_json(release_item(root, args.item_id, args.status))
        elif args.command == "receipt":
            print_json(attach_receipt(root, args.item_id, args.receipt_path, args.status))
        elif args.command == "status":
            print_json(update_status(root, args.item_id, args.status))
        elif args.command == "next":
            item = next_item(root, args.agent_id)
            print_json(item if item else {})
        elif args.command == "done":
            print_json(done_item(root, args))
        elif args.command == "codex-run":
            prompt = sys.stdin.read() if args.prompt_file == "-" else Path(args.prompt_file).read_text(encoding="utf-8")
            if not prompt.strip():
                raise QueueError("Codex prompt is empty")
            print_json(run_codex_work_item(root, args.item_id, prompt))
        elif args.command == "codex-reconcile":
            print_json(reconcile_codex_usage(
                root,
                args.item_id,
                parse_codex_token_summary(args.summary),
                args.cli_version,
                args.session_id,
                source="operator-supplied terminal evidence",
            ))
        else:
            parser.error(f"Unknown command: {args.command}")
    except (AuthorityError, QueueError, QueueStorageError, json.JSONDecodeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"NEEDS ATTENTION: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
