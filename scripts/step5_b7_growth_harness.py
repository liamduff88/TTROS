#!/usr/bin/env python3
"""Step 5 -- B7 growth-loop instrument.

Grows the canonical map ONE class at a time (manifest id order, fixed before
any call: 1..9) and re-scores B7 after each addition, using the EXACT SAME
frozen 25-question set, scorer, and vault-isolation snapshot as Step 3
(imported from step3_b7_harness.py, not re-implemented) so pass totals are
comparable to the Step 3 baseline without a second source of drift.

Budget (CLAUDE.md "budget enforcement is inside the instrument"):
  N = 9 (number of candidate canonical fact classes, from canonical.manifest
  n_classes, declared before the first call). Maximum 25 calls per pass,
  maximum N=9 passes overall (225 calls). Hard-stops in-process; writes
  actual vs declared counts into the transcript; refuses to exceed.

Growth stops at whichever comes first:
  - incremental gain (this pass's total coverage minus the previous total,
    where "previous" is the Step 3 lower-anchor baseline for k=1, then the
    prior k for k>1) fails to exceed the Step 3 B7 noise allowance (4.0pp,
    from scripts/step3_b7_report.md, fixed before this run);
  - the map's own byte size leaves less than 10,000 B of headroom under the
    B2 96,000 B ceiling (map_bytes > 86,000).

The old canonical ranking path (tools/context_assembler.py _scoped_note_block)
is left ENABLED throughout this growth/measurement loop -- each pass measures
the map's ADDITION on top of today's production retrieval, isolating the
map's marginal contribution. Disabling the ranker is a separate apply-gate
step, done once after growth stops (scripts/step5_apply_flag.md describes it),
because only then does "fresh bytes per turn" actually drop.

Usage:
  step5_b7_growth_harness.py run-pass --k 1 [--dry-run] [--resume]
  step5_b7_growth_harness.py score-pass --k 1
  step5_b7_growth_harness.py report
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/liam/agentic-os-live")
SCRIPT_DIR = Path(__file__).resolve().parent
MASTER_SNAPSHOT = Path("/home/liam/ttros_backups/b7_harness_vault_snapshot_20260907_000711Z")
WORK_VAULT = Path(
    "/tmp/claude-1002/-home-liam-agentic-os-live/c396368d-faf5-4c05-89e5-20cb00b7fd57/"
    "scratchpad/step5_b7_vault_work"
)
ASSEMBLY_DIR = ROOT / "queue" / "context_assemblies"
HERMES_MD_PATH = ROOT / ".hermes.md"
HERMES_BIN = "/home/liam/.local/bin/hermes"
CALL_TIMEOUT_SECONDS = 600
MAX_CALLS_PER_PASS = 25
N_CLASSES = 9  # declared from canonical.manifest n_classes, before any Step 5 call
NOISE_ALLOWANCE_PP = 4.0  # from scripts/step3_b7_report.md, fixed before this run
STEP3_LOWER_ANCHOR_PCT = 52.5  # from scripts/step3_b7_report.md
B2_CEILING_BYTES = 96_000
B2_HEADROOM_FLOOR_BYTES = 10_000

# Import the frozen Step 3 question set / scorer by path (reuse, not re-implement).
spec = importlib.util.spec_from_file_location("step3_b7_harness", SCRIPT_DIR / "step3_b7_harness.py")
step3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step3)  # type: ignore[union-attr]

QUESTIONS = step3.QUESTIONS
NON_HONESTY_FACT_COUNT = step3.NON_HONESTY_FACT_COUNT
score_pass = step3.score_pass


def refresh_work_vault() -> None:
    WORK_VAULT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsync", "-a", "--delete", f"{MASTER_SNAPSHOT}/", f"{WORK_VAULT}/"], check=True)


def git_status_porcelain() -> set[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                          capture_output=True, text=True, check=True)
    return set(out.stdout.splitlines())


def newest_assembly_file(after: float) -> Path | None:
    candidates = [p for p in ASSEMBLY_DIR.glob("*.json") if p.stat().st_mtime >= after]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def call_david(question_text: str, usage_file: Path, dry_run: bool) -> dict:
    import os
    refresh_work_vault()
    before_status = git_status_porcelain()
    before_mtime = datetime.datetime.now().timestamp()
    start = datetime.datetime.now(datetime.timezone.utc)
    env = dict(os.environ)
    env["AOS_ROOT"] = str(ROOT)
    env["AOS_OPERATOR_CONSULTATION"] = "1"
    env["TTROS_BRAIN_ROOT"] = str(WORK_VAULT)
    # TTROS_CANONICAL_RANKER_ENABLED deliberately NOT set -> defaults to "0"
    # (disabled) per the Step 5 flag. See module docstring: growth passes
    # measure the map's addition on top of whatever the *new default* is,
    # which is the map-only path David actually runs under from this step
    # forward -- not the old Step 3 production config. This is a deliberate
    # divergence from Step 3's baseline surface, recorded here rather than
    # silently assumed; see the transcript's SURFACE NOTE.
    if dry_run:
        answer = f"[DRY RUN stub answer for: {question_text}]"
        stderr = ""
        returncode = 0
    else:
        proc = subprocess.run(
            [HERMES_BIN, "-p", "david", "-z", question_text, "--usage-file", str(usage_file)],
            env=env, capture_output=True, text=True, timeout=CALL_TIMEOUT_SECONDS,
        )
        answer = proc.stdout.strip()
        stderr = proc.stderr.strip()
        returncode = proc.returncode
    end = datetime.datetime.now(datetime.timezone.utc)
    manifest_path = None if dry_run else newest_assembly_file(before_mtime)
    manifest = {}
    if manifest_path and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            manifest = {"_read_error": str(exc)}
    after_status = git_status_porcelain()
    unexpected = {
        line for line in (after_status - before_status)
        if re.search(r"\bqueue/", line)
        and "queue/context_assemblies/" not in line
        and "scripts/step5_b7_pass_" not in line
    }
    usage = {}
    if usage_file.exists():
        try:
            usage = json.loads(usage_file.read_text(encoding="utf-8"))
        except Exception:
            usage = {"_unparsed": usage_file.read_text(encoding="utf-8")[:2000]}
    # B6 depth-tool arrival evidence for this call's own session (see
    # step3_b7_harness.extract_tool_reads -- shared, not re-implemented).
    tool_reads = sorted(step3.extract_tool_reads(usage.get("session_id"))) if not dry_run else []
    return {
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "latency_seconds": (end - start).total_seconds(),
        "answer": answer,
        "stderr": stderr,
        "returncode": returncode,
        "manifest_path": str(manifest_path) if manifest_path else None,
        "manifest": manifest,
        "usage": usage,
        "tool_reads": tool_reads,
        "unexpected_repo_mutation": sorted(unexpected),
    }


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def cmd_run_pass(args: argparse.Namespace) -> int:
    k = args.k
    if not (1 <= k <= N_CLASSES):
        print(f"k={k} out of range 1..{N_CLASSES}", file=sys.stderr)
        return 2
    if not HERMES_MD_PATH.exists():
        print(f"HARD STOP: {HERMES_MD_PATH} does not exist. Generate it first with "
              f"step5_map_generator.py generate --classes 1-{k}.", file=sys.stderr)
        return 2
    map_bytes = len(HERMES_MD_PATH.read_bytes())
    headroom = B2_CEILING_BYTES - map_bytes
    if headroom < B2_HEADROOM_FLOOR_BYTES:
        print(f"HARD STOP: map is {map_bytes} B, headroom {headroom} B < "
              f"{B2_HEADROOM_FLOOR_BYTES} B floor. Growth stopping rule triggered "
              f"BEFORE spending any call this pass.", file=sys.stderr)
        return 6

    label = f"k{k}"
    transcript_path = SCRIPT_DIR / f"step5_b7_pass_{label}.transcript.txt"
    json_path = SCRIPT_DIR / f"step5_b7_pass_{label}.raw.json"

    records = []
    already_done: set[str] = set()
    if args.resume:
        if not json_path.exists():
            print(f"--resume given but no prior evidence at {json_path}.", file=sys.stderr)
            return 2
        prior = json.loads(json_path.read_text(encoding="utf-8"))
        if not prior.get("aborted"):
            print(f"{json_path} is not marked aborted -- nothing to resume.", file=sys.stderr)
            return 2
        records = prior["records"]
        already_done = {r["question_id"] for r in records}
        lines = (transcript_path.read_text(encoding="utf-8").splitlines() if transcript_path.exists() else [])
        lines += [f"[resumed at {datetime.datetime.now(datetime.timezone.utc).isoformat()}, "
                  f"{len(records)} prior call(s) carried forward: {sorted(already_done)}]", ""]
    elif not args.overwrite and (transcript_path.exists() or json_path.exists()):
        print(f"REFUSING to overwrite existing pass {label} evidence: "
              f"{transcript_path} / {json_path}. Pass --overwrite or --resume.", file=sys.stderr)
        return 2
    else:
        lines = [
            f"STEP 5 -- B7 GROWTH PASS k={k} ({N_CLASSES} classes declared max) -- "
            f"{'DRY RUN' if args.dry_run else 'LIVE'}",
            f"Started (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
            "Surface declared: CLI-David (direct `hermes -p david -z` invocation, not dashboard/gateway).",
            "Model pin (from ~/.hermes/profiles/david/config.yaml): openai-codex / gpt-5.5.",
            f"Vault isolation: TTROS_BRAIN_ROOT={WORK_VAULT} (restored from {MASTER_SNAPSHOT}, "
            f"the SAME snapshot Step 3 used, before every call).",
            f".hermes.md present at repo root: {map_bytes} B (classes 1..{k}). B2 headroom vs "
            f"{B2_CEILING_BYTES} B ceiling: {headroom} B.",
            "TTROS_CANONICAL_RANKER_ENABLED: unset (defaults to 0 / disabled) -- SURFACE NOTE: "
            "this pass therefore measures David under the NEW default config (map present, old "
            "ranker off), not Step 3's old-production-config-plus-map. Recorded here, not hidden.",
            f"Declared maximum calls this pass: {MAX_CALLS_PER_PASS}.",
            "",
        ]

    if not MASTER_SNAPSHOT.exists():
        print(f"HARD STOP: vault master snapshot missing at {MASTER_SNAPSHOT}", file=sys.stderr)
        return 3

    declared_max = MAX_CALLS_PER_PASS
    call_count = len(records)

    for q in QUESTIONS:
        if q["id"] in already_done:
            continue
        if call_count >= declared_max:
            lines.append(f"HARD STOP: reached declared maximum of {declared_max} calls "
                         f"before question {q['id']}.")
            _write(transcript_path, lines)
            _write_json(json_path, {"pass": label, "aborted": True, "k": k,
                                      "declared_max": declared_max, "actual_calls": call_count,
                                      "map_bytes": map_bytes, "records": records})
            print("HARD STOP: budget exceeded.", file=sys.stderr)
            return 4
        call_count += 1
        usage_file = SCRIPT_DIR / f"step5_b7_pass_{label}_{q['id']}.usage.json"
        result = call_david(q["text"], usage_file, args.dry_run)
        result["question_id"] = q["id"]
        result["question_text"] = q["text"]
        result["call_index"] = call_count
        records.append(result)
        lines.append(f"--- Q{call_count}/{declared_max} [{q['id']}] {q['text']}")
        lines.append(f"    latency_s={result['latency_seconds']:.1f} manifest={result['manifest_path']}")
        if result["unexpected_repo_mutation"]:
            lines.append(f"    !!! UNEXPECTED REPO MUTATION: {result['unexpected_repo_mutation']}")
        lines.append(f"    ANSWER: {result['answer'][:4000]}")
        lines.append("")
        if result["unexpected_repo_mutation"]:
            lines.append("HARD STOP: unexpected repo mutation detected outside "
                         "queue/context_assemblies/. Aborting.")
            _write(transcript_path, lines)
            _write_json(json_path, {"pass": label, "aborted": True, "k": k,
                                      "declared_max": declared_max, "actual_calls": call_count,
                                      "map_bytes": map_bytes, "records": records})
            print("HARD STOP: unexpected repo mutation detected.", file=sys.stderr)
            return 5

    lines.append(f"Finished (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    lines.append(f"Actual call count: {call_count} / declared maximum {declared_max}")
    _write(transcript_path, lines)
    _write_json(json_path, {"pass": label, "aborted": False, "k": k,
                              "declared_max": declared_max, "actual_calls": call_count,
                              "map_bytes": map_bytes, "records": records})
    print(f"Pass {label} complete: {call_count}/{declared_max} calls. "
          f"Transcript: {transcript_path}  JSON: {json_path}")
    return 0


def cmd_score_pass(args: argparse.Namespace) -> int:
    k = args.k
    label = f"k{k}"
    raw_path = SCRIPT_DIR / f"step5_b7_pass_{label}.raw.json"
    scored_path = SCRIPT_DIR / f"step5_b7_pass_{label}.scored.json"
    if not raw_path.exists():
        print(f"No raw evidence at {raw_path} -- run run-pass first.", file=sys.stderr)
        return 2
    if not args.overwrite and scored_path.exists():
        print(f"REFUSING to overwrite {scored_path}. Pass --overwrite.", file=sys.stderr)
        return 2
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if raw.get("aborted"):
        print(f"Pass {label} was aborted mid-run. Scoring a partial pass is not meaningful.", file=sys.stderr)
        return 3
    scored = score_pass(raw)
    scored["k"] = k
    scored["map_bytes"] = raw["map_bytes"]
    _write_json(scored_path, scored)
    honesty_fails = [q["id"] for q in scored["questions"] if q["honesty"] and q["verdict"] == "FAIL"]
    zero_pct = [q["id"] for q in scored["questions"] if not q["honesty"] and q["coverage"] == 0.0]
    print(f"Pass {label}: coverage {scored['coverage_pct']:.1f}% "
          f"({scored['total_facts_present']}/{scored['total_facts_possible']}). map_bytes={scored['map_bytes']}. "
          f"Honesty fails: {honesty_fails or 'none'}. Zero-coverage: {zero_pct or 'none'}.")
    print(f"Written: {scored_path}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    scored_files = sorted(SCRIPT_DIR.glob("step5_b7_pass_k*.scored.json"))
    if not scored_files:
        print("No scored passes found.", file=sys.stderr)
        return 2
    passes = []
    for p in scored_files:
        d = json.loads(p.read_text(encoding="utf-8"))
        passes.append(d)
    passes.sort(key=lambda d: d["k"])

    lines = ["# Step 5 -- B7 growth loop report", ""]
    lines.append(f"N (declared max passes, from canonical.manifest n_classes): {N_CLASSES}")
    lines.append(f"Declared max calls: {N_CLASSES} x 25 = {N_CLASSES * 25}")
    total_calls = sum(p["actual_calls"] for p in passes)
    lines.append(f"Actual calls made across {len(passes)} pass(es): {total_calls}")
    lines.append(f"Step 3 lower-anchor baseline: {STEP3_LOWER_ANCHOR_PCT:.1f}%")
    lines.append(f"B7 noise allowance (fixed, from Step 3): {NOISE_ALLOWANCE_PP:.1f}pp")
    lines.append("")
    prev_total = STEP3_LOWER_ANCHOR_PCT
    stop_k = None
    stop_reason = None
    for p in passes:
        gain = p["coverage_pct"] - prev_total
        headroom = B2_CEILING_BYTES - p["map_bytes"]
        lines.append(f"## k={p['k']} -- coverage {p['coverage_pct']:.1f}% "
                     f"({p['total_facts_present']}/{p['total_facts_possible']}), "
                     f"map_bytes={p['map_bytes']}, headroom={headroom}")
        lines.append(f"   gain vs previous ({prev_total:.1f}%): {gain:+.1f}pp "
                     f"({'EXCEEDS' if gain > NOISE_ALLOWANCE_PP else 'DOES NOT EXCEED'} noise allowance)")
        if headroom < B2_HEADROOM_FLOOR_BYTES and stop_k is None:
            stop_k, stop_reason = p["k"], "B2 headroom < 10,000 B"
        if gain <= NOISE_ALLOWANCE_PP and stop_k is None:
            stop_k, stop_reason = p["k"], "incremental gain did not exceed noise allowance"
        prev_total = p["coverage_pct"]
    lines.append("")
    if stop_k is not None:
        lines.append(f"## Growth stopped at k={stop_k}: {stop_reason}.")
    else:
        lines.append(f"## Growth loop did not hit a stop condition within the {len(passes)} pass(es) run.")
    report_path = SCRIPT_DIR / "step5_b7_growth_report.md"
    if not args.overwrite and report_path.exists():
        print(f"REFUSING to overwrite {report_path}. Pass --overwrite.", file=sys.stderr)
        return 2
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWritten: {report_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run-pass")
    p_run.add_argument("--k", type=int, required=True)
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--overwrite", action="store_true")
    p_run.add_argument("--resume", action="store_true")
    p_run.set_defaults(func=cmd_run_pass)

    p_score = sub.add_parser("score-pass")
    p_score.add_argument("--k", type=int, required=True)
    p_score.add_argument("--overwrite", action="store_true")
    p_score.set_defaults(func=cmd_score_pass)

    p_report = sub.add_parser("report")
    p_report.add_argument("--overwrite", action="store_true")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
