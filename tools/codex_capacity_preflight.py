"""Read-only Codex capacity gate for substantive aos-orchestrator requests.

Revisit: when Hermes changes its pool or account-usage API. · Last touched: 2026-09-23.
"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path


USED_LIMIT = 97.0
REQUIRED_WINDOWS = frozenset({"Session", "Weekly"})


class CapacityUnavailable(RuntimeError):
    """Neither Hermes OAuth slot can begin another substantive request."""


def healthy_windows(snapshot) -> bool:
    """Require a live, complete Codex usage snapshot; missing data fails closed."""
    if snapshot is None or snapshot.source != "usage_api" or snapshot.unavailable_reason:
        return False
    windows = {window.label: window.used_percent for window in snapshot.windows}
    if not REQUIRED_WINDOWS.issubset(windows):
        return False
    for label in REQUIRED_WINDOWS:
        value = windows[label]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if not math.isfinite(value) or value < 0 or value >= USED_LIMIT:
            return False
    return True


def _retry_at(snapshot) -> float:
    """Bench until every low window resets, or recheck an unknown window soon."""
    reset_times = []
    if snapshot is not None:
        for window in snapshot.windows:
            if window.label not in REQUIRED_WINDOWS:
                continue
            value = window.used_percent
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= USED_LIMIT:
                reset_at = getattr(window, "reset_at", None)
                if reset_at is not None:
                    reset_times.append(reset_at.timestamp())
    return max([time.time() + 300, *reset_times])


def preflight_agent(agent, *, fetch_usage=None, pool=None) -> str | None:
    """Use the first healthy Hermes slot in configured priority order.

    The usage endpoint is a read-only HTTP request. Native Hermes pool selection
    and hard-failure rotation remain responsible for quota/auth error handling.
    """
    if Path(os.environ.get("HERMES_HOME", "")).name != "aos-orchestrator":
        return None
    if getattr(agent, "provider", None) != "openai-codex":
        return None
    if fetch_usage is None:
        from agent.account_usage import _fetch_codex_account_usage
        fetch_usage = _fetch_codex_account_usage
    if pool is None:
        pool = getattr(agent, "_credential_pool", None)
        if pool is None:
            from agent.credential_pool import load_pool
            pool = load_pool("openai-codex")
            agent._credential_pool = pool
    entries = sorted(pool.entries(), key=lambda entry: entry.priority)
    current_id = getattr(agent, "_credential_pool_entry_id", None)
    if not current_id:
        current_id = next(
            (entry.id for entry in entries if entry.runtime_api_key == getattr(agent, "api_key", None)),
            None,
        )
    # Respect Hermes' fill_first order even when a cached agent is still on B
    # after A's cooldown has lifted.
    for candidate in entries:
        try:
            entry = pool.reclaim(candidate.id, model=getattr(agent, "model", None))
        except Exception:
            continue
        if entry is None:
            continue
        try:
            snapshot = fetch_usage(base_url=entry.runtime_base_url, api_key=entry.runtime_api_key)
        except Exception:
            snapshot = None
        if not healthy_windows(snapshot):
            # Put the soft threshold into Hermes' own pool cooldown. Native
            # 401/402/429 rotation must not retry a low slot later this turn.
            pool.mark_exhausted_and_rotate(
                status_code=None, credential_id=entry.id,
                error_context={"reset_at": _retry_at(snapshot)},
                failure_reason="ttros_capacity_preflight",
            )
            continue
        if entry.id != current_id or entry.runtime_api_key != getattr(agent, "api_key", None):
            if not agent._swap_credential(entry):
                continue
        agent._ttros_serving_slot = entry.id
        agent._ttros_serving_account_label = entry.label
        return entry.id
    raise CapacityUnavailable(
        "Both OpenAI-Codex accounts are at or below 3% remaining, or unavailable; "
        "Operating Hermes stopped before a model request."
    )
