#!/usr/bin/env python3
"""Replay the Codex session fuse over every recorded stream that has exact usage.

Population: logs/codex_sessions/*.stdout.jsonl, derived in this run. Each
stream is fed to the production ``StreamingSessionFuse`` with its
``turn.completed`` events removed (what the fuse sees mid-turn); the final
in-flight estimate is compared with the provider's exact input+output.
Prompt sizes come from ``initial_prompt_bytes`` in logs/local_agent_route.jsonl.
The pre-fix estimator (cumulative tool output re-counted per inferred
request) is replayed alongside for reference. Then every FULL stream is fed
to the production fuse to record its stop decision, next to the stop the
pre-correction rule (stop when the estimate reaches the limit) would have
made, plus two synthetic streams that rehearse the exact-usage stop. Zero
model calls. Prediction: codex_fuse_calibration.prediction.txt.

Revisit: when the fuse estimator or codex exec --json events change. · Last touched: 2026-10-25.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import aos_codex_policy as policy  # noqa: E402

AOS_0947 = "codex-454889f5823f454ebc8400e17219c2de"
AOS_9954 = "codex-787ca932c741441e88c8a95d8214adec"


def prompt_text(size_bytes: int) -> str:
    """Production prompts open with the permission header, whose em dash is 3 bytes / 1 char."""
    return "\u2014" + "x" * (size_bytes - 3) if size_bytes >= 3 else "x" * size_bytes


def stop_decisions(stream: str, prompt: str) -> dict:
    """Feed one full stream line by line: the production stop and the pre-correction estimate stop."""
    fuse = policy.StreamingSessionFuse(prompt)
    old_stop = None
    for index, line in enumerate(stream.splitlines(keepends=True)):
        fuse.feed(line)
        if old_stop is None and fuse.exact_cumulative is None and fuse.in_flight_estimate >= fuse.limit:
            old_stop = {"line": index, "requests": fuse.requests_estimated, "estimate": fuse.in_flight_estimate}
    return {"stopped": fuse.breach, "limit_reached_at_turn_end": fuse.limit_reached_at_turn_end,
            "exact": fuse.exact_cumulative, "old_estimate_stop": old_stop}


def legacy_estimate(events: list[dict], prompt_tokens: int) -> int:
    """The estimator shipped in e2e12d3 (40K-char cap per tool output)."""
    last, requests, context_chars, total = "completed", 0, 0, 0
    for event in events:
        kind, item = event.get("type"), event.get("item") or {}
        if kind == "turn.started":
            last = "completed"
        elif kind == "item.started":
            if last == "completed":
                requests += 1
                total += prompt_tokens + policy.REQUEST_OVERHEAD_FLOOR_TOKENS + context_chars // 4
            last = "started"
        elif kind == "item.completed":
            if last == "completed" and not requests:
                requests += 1
                total += prompt_tokens + policy.REQUEST_OVERHEAD_FLOOR_TOKENS + context_chars // 4
            last = "completed"
            text = str(item.get("aggregated_output") or item.get("text") or "")
            if item.get("type") == "command_execution":
                text = str(item.get("command") or "") + text
            elif item.get("type") == "file_change":
                text = json.dumps(item.get("changes"))
            context_chars += min(len(text), 40_000)
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    transcript = Path(__file__).with_suffix(".txt")
    if transcript.exists() and not args.overwrite:
        print(f"refusing to overwrite {transcript}; pass --overwrite", file=sys.stderr)
        return 2

    prompt_bytes: dict[str, int] = {}
    for raw in (ROOT / "logs" / "local_agent_route.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for artifact in row.get("stream_artifacts") or []:
            if isinstance(row.get("initial_prompt_bytes"), int):
                prompt_bytes[Path(artifact).name.split(".")[0]] = row["initial_prompt_bytes"]

    limit = policy.SESSION_FUSE_LIMIT
    lines = [f"limit {limit}; floor {policy.REQUEST_OVERHEAD_FLOOR_TOKENS}; chars/token {policy.CHARS_PER_TOKEN_ESTIMATE}", ""]
    lines.append("invocation      prompt_B req  estimate   legacy     exact      est/exact legacy/exact")
    ratios, legacy_ratios, false_stops, misses, legacy_false = [], [], [], [], []
    focus: dict | None = None
    decisions: dict[str, dict] = {}
    for path in sorted((ROOT / "logs" / "codex_sessions").glob("*.stdout.jsonl")):
        invocation = path.name.split(".")[0]
        events, exact = [], None
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "turn.completed":
                usage = event.get("usage") or {}
                exact = int(usage["input_tokens"]) + int(usage["output_tokens"])
            else:
                events.append(event)
        prompt = prompt_text(prompt_bytes.get(invocation, 0))
        decision = stop_decisions(path.read_text(encoding="utf-8"), prompt)
        decisions[invocation] = decision
        fuse = policy.StreamingSessionFuse(prompt, limit=10**12)
        fuse.feed("".join(json.dumps(event) + "\n" for event in events))
        estimate = fuse.in_flight_estimate
        legacy = legacy_estimate(events, len(prompt) // policy.CHARS_PER_TOKEN_ESTIMATE)
        if invocation == AOS_0947:
            stopping = policy.StreamingSessionFuse(prompt)
            stopping.feed("".join(json.dumps(event) + "\n" for event in events))
            focus = {"estimate": estimate, "requests": fuse.requests_estimated, "legacy": legacy, "stopped": stopping.breach}
        if exact is None:
            lines.append(f"{invocation[:15]} {len(prompt):8} {fuse.requests_estimated:3} {estimate:9} {legacy:9}  (no exact usage)")
            continue
        assert isinstance(exact, int) and exact > 0
        ratios.append(estimate / exact)
        legacy_ratios.append(legacy / exact)
        if exact < limit <= estimate:
            false_stops.append(f"{invocation[:15]} exact {exact:,}")
        if estimate < limit <= exact:
            misses.append(f"{invocation[:15]} exact {exact:,}")
        if exact < limit <= legacy:
            legacy_false.append(f"{invocation[:15]} exact {exact:,}")
        lines.append(
            f"{invocation[:15]} {len(prompt):8} {fuse.requests_estimated:3} {estimate:9} {legacy:9} {exact:9}"
            f"  {estimate / exact:9.2f} {legacy / exact:9.2f}"
        )
    lines += [
        "",
        f"streams with exact usage: {len(ratios)}",
        f"estimate/exact: min {min(ratios):.2f} max {max(ratios):.2f}; over 1.0: {sum(r > 1 for r in ratios)}",
        f"legacy/exact:   min {min(legacy_ratios):.2f} max {max(legacy_ratios):.2f}; over 1.0: {sum(r > 1 for r in legacy_ratios)}",
        f"estimate would stop below the limit (exact < {limit:,}): {len(false_stops)} {false_stops}",
        f"legacy would stop below the limit: {len(legacy_false)} {legacy_false}",
        f"estimate would not stop although exact >= {limit:,}: {len(misses)} {misses}",
        "",
        f"AOS-2026-0947 ({AOS_0947}): {json.dumps(focus)}",
    ]
    exact_streams = [d for d in decisions.values() if d["exact"] is not None]
    over = [name[:15] for name, d in decisions.items() if d["exact"] is not None and d["exact"] >= limit]
    stopped = [name[:15] for name, d in decisions.items() if d["stopped"]]
    old_stops = [name[:15] for name, d in decisions.items() if d["old_estimate_stop"]]
    synthetic = {
        "two_turns_first_ends_at_600k": "".join(json.dumps(e) + "\n" for e in (
            {"type": "turn.started"},
            {"type": "turn.completed", "usage": {"input_tokens": 599_000, "output_tokens": 1_000}},
            {"type": "turn.started"},
            {"type": "item.started", "item": {"type": "command_execution"}},
        )),
        "one_turn_ends_at_600k": "".join(json.dumps(e) + "\n" for e in (
            {"type": "turn.started"},
            {"type": "turn.completed", "usage": {"input_tokens": 599_000, "output_tokens": 1_000}},
        )),
    }
    rehearsal = {name: stop_decisions(stream, "prompt")["stopped"] for name, stream in synthetic.items()}
    assert rehearsal["two_turns_first_ends_at_600k"] == {"basis": policy.EXACT_BASIS, "tokens": 600_000, "limit": limit}
    assert rehearsal["one_turn_ends_at_600k"] is None
    lines += [
        "",
        "STOP DECISIONS (full streams, production fuse)",
        f"streams: {len(decisions)}; with exact usage: {len(exact_streams)}; without: {len(decisions) - len(exact_streams)}",
        f"exact provider total >= {limit:,}: {len(over)} {over}",
        f"corrected fuse stopped: {len(stopped)} {stopped}",
        f"pre-correction estimate rule would stop: {len(old_stops)} {old_stops}",
        f"AOS-2026-0947: {json.dumps(decisions.get(AOS_0947))}",
        f"AOS-2026-9954: {json.dumps(decisions.get(AOS_9954))}",
        f"negative rehearsal: {json.dumps(rehearsal)}",
    ]
    text = "\n".join(lines) + "\n"
    transcript.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
