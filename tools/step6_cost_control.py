#!/usr/bin/env python3
"""Single TTROS cost dial and 500,000-token fuse.

The existing ``queue/token_ledger.jsonl`` is the only durable accounting and
control-evidence store.  Every model invocation is recorded separately.  A
provider's input total is authoritative; cached input is displayed and priced
separately when available, but is never added to input again.

Revisit: on provider usage-schema or model-pricing changes. · Last touched: 2026-08-06.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("AOS_ROOT", Path(__file__).resolve().parents[1])).resolve()
LEDGER_PATH = Path("queue/token_ledger.jsonl")
NOTIFICATIONS_PATH = Path("queue/notifications.json")
PRICES_PATH = Path("scripts/model_prices.json")
FUSE_LIMIT = 500_000
THRESHOLDS = (("advisory", 250_000, 50), ("warning", 400_000, 80), ("pause", 500_000, 100))
DIAL_VALUES = ("light", "standard", "heavy")
DEFAULT_DIAL = "standard"
UNAVAILABLE = "unavailable from current CLI output"
STICKY_RE = re.compile(r"(?m)^TTROS sticky session key:\s*([A-Za-z0-9_-]{8,128})\s*$")
ITEM_RE = re.compile(r"\bAOS-\d{4}-\d{4}\b", re.IGNORECASE)


class CostControlError(RuntimeError):
    """The canonical cost/fuse contract cannot safely proceed."""


class FusePausedError(CostControlError):
    """The named work item or session is paused before a model call."""


@dataclass(frozen=True)
class Scope:
    kind: str
    scope_id: str

    def __post_init__(self) -> None:
        if self.kind not in {"work_item", "session"}:
            raise CostControlError("scope kind must be work_item or session")
        if not str(self.scope_id).strip():
            raise CostControlError("scope id must not be empty")

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.scope_id}"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def derive_scope(*, work_item_id: str = "", session_id: str = "", prompt: str = "") -> Scope:
    item = str(work_item_id or "").strip().upper()
    if item:
        if not re.fullmatch(r"AOS-\d{4}-\d{4}", item):
            raise CostControlError(f"invalid work-item scope: {item}")
        return Scope("work_item", item)
    sticky = STICKY_RE.search(str(prompt or ""))
    value = sticky.group(1) if sticky else str(session_id or "").strip()
    if not value:
        raise CostControlError("a model invocation requires a named work-item or session scope")
    if len(value) > 160 or any(char in value for char in "\r\n\x00"):
        raise CostControlError("invalid session scope")
    return Scope("session", value)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CostControlError(f"invalid or unavailable JSON contract: {path}") from exc
    if not isinstance(value, dict):
        raise CostControlError(f"JSON contract must be an object: {path}")
    return value


def _contract_path(root: Path, relative: Path) -> Path:
    """Use fixture-local contracts when present, otherwise the live contract."""
    candidate = root / relative
    return candidate if candidate.exists() else ROOT / relative


def resolve_cost_dial(*, override: str | None = None, root: Path = ROOT) -> dict[str, str]:
    if override is not None:
        value = str(override).strip().lower()
        if value not in DIAL_VALUES:
            raise CostControlError(f"invalid cost dial {override!r}; expected light, standard, or heavy")
        return {"value": value, "source": "scope_override"}
    config = _read_json(_contract_path(root, NOTIFICATIONS_PATH))
    controls = config.get("operator_controls")
    if controls is not None and not isinstance(controls, dict):
        raise CostControlError("queue/notifications.json operator_controls must be an object")
    configured = (controls or {}).get("cost_dial")
    if configured is not None:
        value = str(configured).strip().lower()
        if value not in DIAL_VALUES:
            raise CostControlError(
                f"invalid global cost dial {configured!r} in queue/notifications.json"
            )
        return {"value": value, "source": "global_config"}
    return {"value": DEFAULT_DIAL, "source": "documented_default"}


def canonical_usage(usage: dict[str, Any]) -> dict[str, Any]:
    """Normalize exact provider counters without inventing missing values.

    Canonical fuse total = provider-reported input + provider-reported output.
    Cached input is a separately displayed counter and is never added again.
    Reasoning is a labelled subset of output when the provider exposes it.
    """
    aliases = {
        "input": ("input_tokens", "total_input", "input"),
        "cached_input": ("cached_input_tokens", "cache_read_tokens", "cached_input"),
        "output": ("output_tokens", "output"),
        "reasoning": ("reasoning_tokens", "reasoning_output_tokens", "reasoning"),
    }
    values: dict[str, int | None] = {}
    for target, names in aliases.items():
        found: object = None
        for name in names:
            if name in usage:
                found = usage.get(name)
                break
        if found is None:
            values[target] = None
        elif isinstance(found, int) and not isinstance(found, bool) and found >= 0:
            values[target] = found
        elif isinstance(found, str) and found.isdigit():
            values[target] = int(found)
        else:
            raise CostControlError(f"corrupt {target} token counter")
    if values["input"] is None or values["output"] is None:
        raise CostControlError("exact provider input and output token counters are required")
    if values["reasoning"] is not None and values["reasoning"] > values["output"]:
        raise CostControlError("reasoning tokens exceed provider output tokens")
    # Codex declares cached input as a subset of provider-total input. Hermes'
    # cache_read_tokens may be an independent cumulative cache counter. Either
    # way it is never added to the canonical fuse total.
    provider = str(usage.get("provider") or "unknown")
    explicit_cache_semantics = str(usage.get("cache_semantics") or "").strip()
    reported_total = usage.get("total_tokens")
    # Direct Codex summaries declare cached input as a subset and pass that
    # contract explicitly. Hermes' aggregate openai-codex usage report uses a
    # different shape: input_tokens is non-cached input, cache_read_tokens is
    # separate, and total_tokens equals input + cache read + output. Recognize
    # that exact self-describing report shape so the Hermes -> Step 6 handoff
    # does not reject a valid cache counter larger than fresh input.
    hermes_separate_cache_shape = (
        not explicit_cache_semantics
        and provider in {"openai", "openai-codex"}
        and isinstance(reported_total, int)
        and not isinstance(reported_total, bool)
        and isinstance(values["cached_input"], int)
        and reported_total == values["input"] + values["cached_input"] + values["output"]
    )
    cache_semantics = explicit_cache_semantics or (
        "provider_separate_counter"
        if hermes_separate_cache_shape or provider not in {"openai", "openai-codex"}
        else "included_in_provider_input"
    )
    if cache_semantics == "included_in_provider_input" and values["cached_input"] is not None:
        if values["cached_input"] > values["input"]:
            raise CostControlError("cached input exceeds provider-total input")
        fresh_input: int | None = values["input"] - values["cached_input"]
    else:
        fresh_input = values["input"]
    return {
        **values,
        "fresh_input": fresh_input,
        "canonical_total": values["input"] + values["output"],
        "formula": "provider_input + provider_output; cached_input never added again; reasoning is output subset",
        "cache_semantics": cache_semantics,
    }


def _price_contract(model: str, at: str, root: Path) -> tuple[dict[str, Any] | None, str | None]:
    payload = _read_json(_contract_path(root, PRICES_PATH))
    rate = (payload.get("models") or {}).get(model)
    if not isinstance(rate, dict) or rate.get("priced") is False:
        return None, f"missing pricing contract for model {model or 'unknown'}"
    effective = str(rate.get("effective_from") or "")
    if not effective:
        return None, f"pricing contract for {model} has no effective_from"
    try:
        instant = dt.date.fromisoformat(str(at)[:10])
        effective_date = dt.date.fromisoformat(effective)
        expires = dt.date.fromisoformat(str(rate["effective_through"])) if rate.get("effective_through") else None
    except ValueError:
        return None, f"pricing contract for {model} has invalid effective dates"
    if instant < effective_date or (expires and instant > expires):
        return None, f"no effective pricing contract for {model} at {instant.isoformat()}"
    required = ("input_per_mtok", "cache_read_per_mtok", "output_per_mtok")
    if any(not isinstance(rate.get(key), (int, float)) or isinstance(rate.get(key), bool) for key in required):
        return None, f"pricing contract for {model} lacks numeric token rates"
    return rate, None


def calculate_cost(
    model: str,
    normalized: dict[str, Any],
    *,
    at: str | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    timestamp = at or utc_now()
    rate, unavailable = _price_contract(model, timestamp, root)
    if rate is None:
        return {"status": "unpriced", "usd": None, "reason": unavailable}
    fresh = normalized.get("fresh_input")
    cached = normalized.get("cached_input")
    cache_semantics = normalized.get("cache_semantics")
    if not isinstance(fresh, int):
        return {"status": "unpriced", "usd": None, "reason": "fresh input unavailable"}
    if cache_semantics == "included_in_provider_input":
        cache_tokens = cached if isinstance(cached, int) else 0
    else:
        # Hermes cache reads are additional billed cache activity even though
        # they do not enter the canonical fuse total.
        cache_tokens = cached if isinstance(cached, int) else 0
    input_rate = float(rate["input_per_mtok"])
    cache_rate = float(rate["cache_read_per_mtok"])
    output_rate = float(rate["output_per_mtok"])
    long_rule = rate.get("long_context") if isinstance(rate.get("long_context"), dict) else None
    if long_rule and int(normalized["input"]) > int(long_rule.get("input_tokens_above", 10**18)):
        input_rate *= float(long_rule.get("input_multiplier", 1))
        cache_rate *= float(long_rule.get("cache_read_multiplier", long_rule.get("input_multiplier", 1)))
        output_rate *= float(long_rule.get("output_multiplier", 1))
    value = (
        fresh / 1_000_000 * input_rate
        + cache_tokens / 1_000_000 * cache_rate
        + int(normalized["output"]) / 1_000_000 * output_rate
    )
    return {
        "status": "priced",
        "usd": round(value, 6),
        "pricing_version": str(_read_json(_contract_path(root, PRICES_PATH)).get("version") or "unversioned"),
        "effective_from": rate["effective_from"],
        "effective_through": rate.get("effective_through"),
        "source": rate.get("source"),
    }


def _ledger_rows(root: Path, ledger_path: Path = LEDGER_PATH) -> list[dict[str, Any]]:
    path = root / ledger_path
    if not path.exists():
        return []
    rows = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CostControlError(f"corrupt token ledger line {number}") from exc
        if not isinstance(value, dict):
            raise CostControlError(f"corrupt token ledger line {number}")
        rows.append(value)
    return rows


def _scope_rows(scope: Scope, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("scope_key") == scope.key]


def fuse_status(scope: Scope, *, root: Path = ROOT, ledger_path: Path = LEDGER_PATH) -> dict[str, Any]:
    all_rows = _scope_rows(scope, _ledger_rows(root, ledger_path))
    reset_indexes = [index for index, row in enumerate(all_rows) if row.get("event") == "fuse_scope_reset"]
    rows = all_rows[reset_indexes[-1] + 1:] if reset_indexes else all_rows
    last_reset = all_rows[reset_indexes[-1]] if reset_indexes else None
    seen: set[str] = set()
    total = 0
    unknown: list[str] = []
    emitted: list[str] = []
    override = False
    override_reason = ""
    actual_model = "unavailable"
    dial = resolve_cost_dial(root=root)
    breakdown = {"input": 0, "cached_input": 0, "output": 0, "reasoning": 0}
    cached_known = output_known = reasoning_known = input_known = True
    cost_total = 0.0
    unpriced: list[str] = []
    for row in rows:
        event = row.get("event")
        if event == "fuse_override_set":
            override = True
            override_reason = str(row.get("override_reason") or "operator scoped override")
            continue
        if event == "fuse_override_reset":
            override = False
            override_reason = ""
            continue
        if event != "model_invocation":
            continue
        identity = str(row.get("invocation_id") or "")
        if not identity:
            unknown.append("model invocation lacks invocation_id")
            continue
        if identity in seen:
            continue
        seen.add(identity)
        fuse = row.get("fuse") if isinstance(row.get("fuse"), dict) else {}
        value = fuse.get("invocation_tokens")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            unknown.append(f"{identity}: canonical usage unavailable")
            continue
        total += value
        for name in fuse.get("thresholds_emitted") or []:
            if name in {item[0] for item in THRESHOLDS} and name not in emitted:
                emitted.append(name)
        usage = row.get("exact_usage") if isinstance(row.get("exact_usage"), dict) else {}
        for key in breakdown:
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                breakdown[key] += value
            elif key == "input": input_known = False
            elif key == "cached_input": cached_known = False
            elif key == "output": output_known = False
            elif key == "reasoning": reasoning_known = False
        actual_model = str(row.get("model_confirmed") or actual_model)
        if isinstance(row.get("cost"), dict) and row["cost"].get("status") == "priced":
            cost_total += float(row["cost"].get("usd") or 0)
        else:
            unpriced.append(str((row.get("cost") or {}).get("reason") or actual_model))
        if isinstance(row.get("cost_dial"), dict):
            dial = {"value": str(row["cost_dial"].get("value")), "source": str(row["cost_dial"].get("source"))}
    paused_by_total = total >= FUSE_LIMIT
    accounting_unknown = bool(unknown)
    # A scoped override bypasses only a known 500K fuse state. Corrupt or
    # unknown accounting still fails closed and is never treated as zero.
    paused = accounting_unknown or (paused_by_total and not override)
    return {
        "scope": {"type": scope.kind, "id": scope.scope_id, "key": scope.key},
        "effective_cost_dial": dial,
        "actual_model": actual_model,
        "canonical_tokens": None if accounting_unknown else total,
        "breakdown": {
            "input": breakdown["input"] if input_known else None,
            "cached_input": breakdown["cached_input"] if cached_known else None,
            "output": breakdown["output"] if output_known else None,
            "reasoning": breakdown["reasoning"] if reasoning_known else None,
        },
        "cost": {"status": "unpriced", "usd": None, "reasons": sorted(set(unpriced))}
        if unpriced else {"status": "priced", "usd": round(cost_total, 6)},
        "fuse_limit": FUSE_LIMIT,
        "fuse_percent": None if accounting_unknown else round(total / FUSE_LIMIT * 100, 3),
        "thresholds_emitted": emitted,
        "paused": paused,
        "pause_reason": (
            "; ".join(unknown) if accounting_unknown else
            f"canonical token fuse reached {total}/{FUSE_LIMIT}" if paused_by_total else ""
        ),
        "accounting_unknown": accounting_unknown,
        "override_active": override,
        "override_reason": override_reason,
        "invocation_count": len(seen),
        "reset_count": len(reset_indexes),
        "last_reset_at": str((last_reset or {}).get("timestamp") or ""),
    }


def preflight(scope: Scope, *, dial_override: str | None = None, root: Path = ROOT, ledger_path: Path = LEDGER_PATH) -> dict[str, Any]:
    dial = resolve_cost_dial(override=dial_override, root=root)
    status = fuse_status(scope, root=root, ledger_path=ledger_path)
    status["effective_cost_dial"] = dial
    if status["paused"]:
        raise FusePausedError(
            f"Step 6 fuse paused {scope.key}: {status['pause_reason']}; "
            "the next model invocation is blocked until a scoped override or accounting repair"
        )
    return status


def _thresholds_crossed(before: int, after: int, already: set[str]) -> list[str]:
    return [name for name, value, _pct in THRESHOLDS if before < value <= after and name not in already]


def _zero_usage() -> dict[str, Any]:
    return {
        "orchestrator": {"input": 0, "output": 0},
        "subagents": [],
        "workbenches": [],
        "totals": {"input": 0, "output": 0},
        "est_cost_usd": 0.0,
        "unavailable": ["no agent invocation"],
    }


def _append_row(root: Path, ledger_path: Path, row: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Append under one ledger lock and assign threshold evidence atomically."""
    path = root / ledger_path
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        rows = _ledger_rows(root, ledger_path)
        if row.get("event") == "model_invocation":
            identity = str(row.get("invocation_id") or "")
            duplicate = next((
                existing for existing in rows
                if existing.get("event") == "model_invocation"
                and existing.get("scope_key") == row.get("scope_key")
                and existing.get("invocation_id") == identity
            ), None)
            if duplicate is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
                return False, duplicate

            prior_total = 0
            emitted: set[str] = set()
            seen: set[str] = set()
            prior_unknown = False
            for existing in rows:
                if existing.get("scope_key") != row.get("scope_key"):
                    continue
                if existing.get("event") == "fuse_scope_reset":
                    prior_total = 0
                    emitted.clear()
                    seen.clear()
                    prior_unknown = False
                    continue
                if existing.get("event") != "model_invocation":
                    continue
                existing_id = str(existing.get("invocation_id") or "")
                if not existing_id or existing_id in seen:
                    continue
                seen.add(existing_id)
                fuse = existing.get("fuse") if isinstance(existing.get("fuse"), dict) else {}
                amount = fuse.get("invocation_tokens")
                if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
                    prior_unknown = True
                else:
                    prior_total += amount
                emitted.update(str(name) for name in (fuse.get("thresholds_emitted") or []))
            current_fuse = row.get("fuse") if isinstance(row.get("fuse"), dict) else {}
            invocation_tokens = current_fuse.get("invocation_tokens")
            if not prior_unknown and isinstance(invocation_tokens, int):
                after_total = prior_total + invocation_tokens
                crossed = _thresholds_crossed(prior_total, after_total, emitted)
                current_fuse.update({
                    "scope_total_before": prior_total,
                    "scope_total_after": after_total,
                    "percent_after": round(after_total / FUSE_LIMIT * 100, 3),
                    "thresholds_emitted": crossed,
                    "paused_after": after_total >= FUSE_LIMIT,
                    "blocks_next_invocation": after_total >= FUSE_LIMIT,
                })
                row["fuse"] = current_fuse
            elif prior_unknown:
                current_fuse.update({
                    "scope_total_before": None,
                    "scope_total_after": None,
                    "percent_after": None,
                    "thresholds_emitted": [],
                    "accounting_status": "unknown",
                })
                row["fuse"] = current_fuse
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return True, row


def record_invocation(
    scope: Scope,
    *,
    invocation_id: str,
    provider: str,
    model: str,
    usage: dict[str, Any],
    dial_override: str | None = None,
    timestamp: str | None = None,
    root: Path = ROOT,
    ledger_path: Path = LEDGER_PATH,
    surface: str = "unknown",
) -> dict[str, Any]:
    if not str(invocation_id).strip():
        raise CostControlError("invocation_id is required")
    before = fuse_status(scope, root=root, ledger_path=ledger_path)
    existing = [
        row for row in _scope_rows(scope, _ledger_rows(root, ledger_path))
        if row.get("event") == "model_invocation" and row.get("invocation_id") == invocation_id
    ]
    if existing:
        candidate = canonical_usage(usage)
        recorded = (existing[-1].get("fuse") or {}).get("invocation_tokens")
        if recorded != candidate["canonical_total"]:
            raise CostControlError(f"conflicting exact usage for invocation {invocation_id}")
        return {"recorded": False, "idempotent": True, "row": existing[-1], "status": before}
    if before["paused"]:
        raise FusePausedError(f"Step 6 fuse paused {scope.key}: {before['pause_reason']}")
    normalized = canonical_usage({**usage, "provider": provider})
    event_at = timestamp or utc_now()
    dial = resolve_cost_dial(override=dial_override, root=root)
    prior_total = int(before["canonical_tokens"] or 0)
    after_total = prior_total + normalized["canonical_total"]
    crossed = _thresholds_crossed(prior_total, after_total, set(before["thresholds_emitted"]))
    cost = calculate_cost(model, normalized, at=event_at, root=root)
    cached = normalized["cached_input"]
    reasoning = normalized["reasoning"]
    row = {
        "item_id": scope.scope_id if scope.kind == "work_item" else "AOS-2026-0000",
        "session_id": scope.scope_id if scope.kind == "session" else invocation_id,
        "invocation_id": invocation_id,
        "event": "model_invocation",
        "scope_type": scope.kind,
        "scope_id": scope.scope_id,
        "scope_key": scope.key,
        "surface": surface,
        "lane": "hermes" if "hermes" in surface else "codex" if "codex" in surface else "claude" if "claude" in surface else "unassigned",
        "profile": "default",
        "timestamp": event_at,
        "provider": provider or "unknown",
        "escalated": False,
        "model_requested": model or "unavailable",
        "model_confirmed": model or "unavailable",
        "actual_model": model or "unavailable",
        "budget_class": dial["value"],
        "cost_dial": dial,
        "exact_usage": {
            "input": normalized["input"],
            "cached_input": cached,
            "fresh_input": normalized["fresh_input"],
            "output": normalized["output"],
            "reasoning": reasoning,
            "canonical_total": normalized["canonical_total"],
            "cache_semantics": normalized["cache_semantics"],
        },
        "fuse": {
            "limit": FUSE_LIMIT,
            "formula": normalized["formula"],
            "invocation_tokens": normalized["canonical_total"],
            "scope_total_before": prior_total,
            "scope_total_after": after_total,
            "percent_after": round(after_total / FUSE_LIMIT * 100, 3),
            "thresholds_emitted": crossed,
            "paused_after": after_total >= FUSE_LIMIT,
            "blocks_next_invocation": after_total >= FUSE_LIMIT,
        },
        "cost": cost,
        "pricing_version": cost.get("pricing_version"),
        "pricing_effective_date": cost.get("effective_from"),
        "token_usage": {
            "orchestrator": {"input": normalized["input"], "output": normalized["output"]},
            "subagents": [],
            "workbenches": [],
            "totals": {"input": normalized["input"], "output": normalized["output"]},
            "est_cost_usd": cost.get("usd"),
            "unavailable": [] if cost["status"] == "priced" else [str(cost.get("reason"))],
        },
        "total_input": normalized["input"],
        "fresh_input": normalized["fresh_input"] if normalized["fresh_input"] is not None else UNAVAILABLE,
        "cached_input": cached if cached is not None else UNAVAILABLE,
        "output": normalized["output"],
        "reasoning": reasoning if reasoning is not None else UNAVAILABLE,
        "input_plus_output": normalized["canonical_total"],
    }
    recorded, durable_row = _append_row(root, ledger_path, row)
    if not recorded:
        recorded_total = (durable_row.get("fuse") or {}).get("invocation_tokens")
        if recorded_total != normalized["canonical_total"]:
            raise CostControlError(f"conflicting exact usage for invocation {invocation_id}")
    return {
        "recorded": recorded,
        "idempotent": not recorded,
        "row": durable_row,
        "status": fuse_status(scope, root=root, ledger_path=ledger_path),
    }


def record_unavailable_invocation(
    scope: Scope,
    *,
    invocation_id: str,
    provider: str = "unknown",
    model: str = "unavailable",
    reason: str,
    dial_override: str | None = None,
    root: Path = ROOT,
    ledger_path: Path = LEDGER_PATH,
    surface: str = "unknown",
) -> dict[str, Any]:
    """Persist an attempted provider call whose exact counters are unavailable.

    This is deliberately not a zero-token row.  Its missing canonical total
    makes the named scope fail closed on the next preflight.
    """
    existing = [
        row for row in _scope_rows(scope, _ledger_rows(root, ledger_path))
        if row.get("event") == "model_invocation" and row.get("invocation_id") == invocation_id
    ]
    if existing:
        return {"recorded": False, "idempotent": True, "row": existing[-1], "status": fuse_status(scope, root=root, ledger_path=ledger_path)}
    dial = resolve_cost_dial(override=dial_override, root=root)
    row = {
        "item_id": scope.scope_id if scope.kind == "work_item" else "AOS-2026-0000",
        "session_id": scope.scope_id if scope.kind == "session" else invocation_id,
        "invocation_id": invocation_id,
        "event": "model_invocation",
        "scope_type": scope.kind,
        "scope_id": scope.scope_id,
        "scope_key": scope.key,
        "surface": surface,
        "lane": "hermes" if "hermes" in surface else "codex" if "codex" in surface else "claude" if "claude" in surface else "unassigned",
        "profile": "default",
        "timestamp": utc_now(),
        "provider": provider,
        "escalated": False,
        "model_requested": model,
        "model_confirmed": model,
        "actual_model": model,
        "budget_class": dial["value"],
        "cost_dial": dial,
        "exact_usage": {"input": None, "cached_input": None, "output": None, "reasoning": None, "canonical_total": None},
        "fuse": {"limit": FUSE_LIMIT, "invocation_tokens": None, "accounting_status": "unknown", "reason": str(reason)},
        "cost": {"status": "unpriced", "usd": None, "reason": "exact token usage unavailable"},
        "token_usage": {
            "orchestrator": {"input": 0, "output": 0},
            "subagents": [],
            "workbenches": [],
            "totals": {"input": 0, "output": 0},
            "est_cost_usd": None,
            "unavailable": [str(reason)],
        },
        "total_input": UNAVAILABLE,
        "fresh_input": UNAVAILABLE,
        "cached_input": UNAVAILABLE,
        "output": UNAVAILABLE,
        "reasoning": UNAVAILABLE,
        "input_plus_output": UNAVAILABLE,
    }
    recorded, durable_row = _append_row(root, ledger_path, row)
    return {
        "recorded": recorded,
        "idempotent": not recorded,
        "row": durable_row,
        "status": fuse_status(scope, root=root, ledger_path=ledger_path),
    }


def set_override(
    scope: Scope,
    *,
    active: bool,
    reason: str,
    root: Path = ROOT,
    ledger_path: Path = LEDGER_PATH,
) -> dict[str, Any]:
    rows = _scope_rows(scope, _ledger_rows(root, ledger_path))
    current = fuse_status(scope, root=root, ledger_path=ledger_path)["override_active"]
    if current == active:
        return {"recorded": False, "idempotent": True, "status": fuse_status(scope, root=root, ledger_path=ledger_path)}
    if active and not str(reason).strip():
        raise CostControlError("a scoped fuse override requires a visible reason")
    event = "fuse_override_set" if active else "fuse_override_reset"
    ordinal = sum(1 for row in rows if row.get("event") == event) + 1
    timestamp = utc_now()
    row = {
        "item_id": scope.scope_id if scope.kind == "work_item" else "AOS-2026-0000",
        "session_id": scope.scope_id,
        "invocation_id": f"{event}:{scope.key}:{ordinal}",
        "event": event,
        "scope_type": scope.kind,
        "scope_id": scope.scope_id,
        "scope_key": scope.key,
        "lane": "operations",
        "profile": "default",
        "timestamp": timestamp,
        "provider": "none",
        "escalated": False,
        "model_requested": "none",
        "model_confirmed": "no agent invocation",
        "actual_model": "no agent invocation",
        "budget_class": resolve_cost_dial(root=root)["value"],
        "no_agent_invocation": True,
        "override_reason": str(reason).strip() if active else "override reset; canonical fuse restored",
        "token_usage": _zero_usage(),
        "total_input": 0,
        "fresh_input": 0,
        "cached_input": 0,
        "output": 0,
        "reasoning": 0,
        "input_plus_output": 0,
    }
    _append_row(root, ledger_path, row)
    return {"recorded": True, "idempotent": False, "row": row, "status": fuse_status(scope, root=root, ledger_path=ledger_path)}


def reset_scope(
    scope: Scope,
    *,
    reason: str,
    root: Path = ROOT,
    ledger_path: Path = LEDGER_PATH,
) -> dict[str, Any]:
    """Start one explicit named-scope fuse epoch without erasing its history."""
    visible_reason = str(reason or "").strip()
    if not visible_reason:
        raise CostControlError("a scoped fuse reset requires a visible reason")
    before = fuse_status(scope, root=root, ledger_path=ledger_path)
    if before["reset_count"] and before["invocation_count"] == 0 and not before["override_active"]:
        return {"recorded": False, "idempotent": True, "status": before}
    rows = _scope_rows(scope, _ledger_rows(root, ledger_path))
    ordinal = sum(1 for row in rows if row.get("event") == "fuse_scope_reset") + 1
    row = {
        "item_id": scope.scope_id if scope.kind == "work_item" else "AOS-2026-0000",
        "session_id": scope.scope_id,
        "invocation_id": f"fuse_scope_reset:{scope.key}:{ordinal}",
        "event": "fuse_scope_reset",
        "scope_type": scope.kind,
        "scope_id": scope.scope_id,
        "scope_key": scope.key,
        "lane": "operations",
        "profile": "default",
        "timestamp": utc_now(),
        "provider": "none",
        "escalated": False,
        "model_requested": "none",
        "model_confirmed": "no agent invocation",
        "actual_model": "no agent invocation",
        "budget_class": resolve_cost_dial(root=root)["value"],
        "no_agent_invocation": True,
        "reset_reason": visible_reason,
        "previous_canonical_tokens": before["canonical_tokens"],
        "previous_accounting_unknown": before["accounting_unknown"],
        "previous_paused": before["paused"],
        "token_usage": _zero_usage(),
        "total_input": 0,
        "fresh_input": 0,
        "cached_input": 0,
        "output": 0,
        "reasoning": 0,
        "input_plus_output": 0,
    }
    _append_row(root, ledger_path, row)
    return {"recorded": True, "idempotent": False, "row": row, "status": fuse_status(scope, root=root, ledger_path=ledger_path)}


def format_threshold_alert(scope: Scope, status: dict[str, Any], threshold: str) -> str:
    try:
        from aos_orchestration import format_operator_work_item_notification
    except ImportError:  # package import in tests/backend
        from tools.aos_orchestration import format_operator_work_item_notification

    labels = {name: (value, pct) for name, value, pct in THRESHOLDS}
    if threshold not in labels:
        raise CostControlError(f"unknown fuse threshold {threshold}")
    value, pct = labels[threshold]
    total = status.get("canonical_tokens")
    state = "paused; next model invocation blocked" if threshold == "pause" else "informational only; no model, context, compaction, or permission change"
    total_text = f"{total:,}" if isinstance(total, int) else "unavailable"
    summary = (
        f"Step 6 token fuse {threshold}: {pct}% / {value:,}; exact scope total "
        f"{total_text}. {state}. Cost dial {status['effective_cost_dial']['value']} "
        f"({status['effective_cost_dial']['source']}); actual model "
        f"{status.get('actual_model') or 'unavailable'}."
    )
    return format_operator_work_item_notification(
        {"id": scope.scope_id, "title": "Step 6 token fuse"},
        "blocked" if threshold == "pause" else "running",
        summary=summary,
        next_action="Set a scoped fuse override after review." if threshold == "pause" else "None",
        receipt_attached=False,
    )


def _scope_from_args(args: argparse.Namespace) -> Scope:
    return Scope(args.scope_type, args.scope_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TTROS Step 6 cost dial and token fuse")
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "preflight", "override", "reset", "reset-scope"):
        command = sub.add_parser(name)
        command.add_argument("--scope-type", choices=("work_item", "session"), required=True)
        command.add_argument("--scope-id", required=True)
        if name == "preflight":
            command.add_argument("--cost-dial", choices=DIAL_VALUES)
        if name in {"override", "reset-scope"}:
            command.add_argument("--reason", required=True)
    record = sub.add_parser("record-usage")
    record.add_argument("--scope-type", choices=("work_item", "session"), required=True)
    record.add_argument("--scope-id", required=True)
    record.add_argument("--invocation-id", required=True)
    record.add_argument("--provider")
    record.add_argument("--model")
    record.add_argument("--usage-file", type=Path, required=True)
    record.add_argument("--cost-dial", choices=DIAL_VALUES)
    record.add_argument("--surface", default="cli")
    unavailable = sub.add_parser("record-unavailable")
    unavailable.add_argument("--scope-type", choices=("work_item", "session"), required=True)
    unavailable.add_argument("--scope-id", required=True)
    unavailable.add_argument("--invocation-id", required=True)
    unavailable.add_argument("--provider", default="unknown")
    unavailable.add_argument("--model", default="unavailable")
    unavailable.add_argument("--reason", required=True)
    unavailable.add_argument("--cost-dial", choices=DIAL_VALUES)
    unavailable.add_argument("--surface", default="cli")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        scope = _scope_from_args(args)
        if args.command == "status":
            result = fuse_status(scope, root=root)
        elif args.command == "preflight":
            result = preflight(scope, dial_override=args.cost_dial, root=root)
        elif args.command == "override":
            result = set_override(scope, active=True, reason=args.reason, root=root)
        elif args.command == "reset":
            result = set_override(scope, active=False, reason="", root=root)
        elif args.command == "reset-scope":
            result = reset_scope(scope, reason=args.reason, root=root)
        elif args.command == "record-usage":
            usage = _read_json(args.usage_file)
            result = record_invocation(
                scope,
                invocation_id=args.invocation_id,
                provider=args.provider or str(usage.get("provider") or "unknown"),
                model=args.model or str(usage.get("model") or "unavailable"),
                usage=usage,
                dial_override=args.cost_dial,
                root=root,
                surface=args.surface,
            )
        else:
            result = record_unavailable_invocation(
                scope,
                invocation_id=args.invocation_id,
                provider=args.provider,
                model=args.model,
                reason=args.reason,
                dial_override=args.cost_dial,
                root=root,
                surface=args.surface,
            )
    except CostControlError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 78
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
