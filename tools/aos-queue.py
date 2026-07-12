#!/usr/bin/env python3
"""Local Agentic OS work queue.

This tool only moves work items through local JSONL files. It does not call
external services, run agents, start schedulers, or update dashboards.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
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
from aos_queue_storage import QueueStorageError, durable_replace_text, queue_write_lock

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
DONE_STATUS = "done"

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
STARTER_AGENTS = ["hermes", "codex", "claude", "revenue", "marketing", "delivery", "operations"]


class QueueError(Exception):
    """Raised when a local queue operation cannot continue."""


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


def cost_for(model: str | None, inp: int, outp: int, prices: dict) -> float | None:
    """Deterministic USD cost for a component, or None when the model has no rate."""
    rate = prices.get(model) if model else None
    if not isinstance(rate, dict):
        return None
    return round(inp / 1_000_000 * rate.get("input_per_mtok", 0.0)
                 + outp / 1_000_000 * rate.get("output_per_mtok", 0.0), 6)


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
            c = cost_for(w.get("model"), int(w.get("input", 0)), int(w.get("output", 0)), prices)
            if c is not None:
                cost += c
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


def _write_receipt_token_usage(root: Path, item_id: str, receipt_path: str | None, block: dict, invocation: dict) -> str:
    """Attach the token_usage block to the item's receipt.

    If a markdown receipt exists, append a fenced block (idempotent per id).
    Always also write a machine-readable sidecar so the receipt-completeness
    hook and the dashboard have a deterministic source.
    """
    payload = {"token_usage": block, "profile_invocation": invocation}
    sidecar = root / RECEIPTS_DIR / f"{item_id}.token_usage.json"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
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
        "memory_promotion": [],
    }
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

    sidecar_path = _write_receipt_token_usage(root, item["id"], resolved_receipt, block, invocation)
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
    if args.owner and args.owner_type == "agent" and args.owner != "unassigned":
        validate_agent(root, args.owner)
    items = load_items(root)
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
        "claim": {"claimed_by": None, "claimed_at": None},
        "receipts": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
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
    claimed_by = item.get("claim", {}).get("claimed_by")
    if claimed_by and claimed_by != agent_id:
        raise QueueError(f"Work item already claimed by {claimed_by}")
    timestamp = now_iso()
    item["claim"] = {"claimed_by": agent_id, "claimed_at": timestamp}
    item["status"] = "agent_working"
    item["updated_at"] = timestamp
    save_items(root, items)
    return item


@locked_queue_mutation
def release_item(root: Path, item_id: str, status: str) -> dict:
    validate_status(status)
    items = load_items(root)
    item = find_item(items, item_id)
    timestamp = now_iso()
    item["claim"] = {"claimed_by": None, "claimed_at": None}
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
        else:
            parser.error(f"Unknown command: {args.command}")
    except (AuthorityError, QueueError, QueueStorageError, json.JSONDecodeError, OSError) as exc:
        print(f"NEEDS ATTENTION: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
