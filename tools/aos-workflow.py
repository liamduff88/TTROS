#!/usr/bin/env python3
"""Local workflow library shell.

This tool catalogs workflow packs and prepares empty local run folders only.
It does not execute workflow logic or call external systems.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from aos_paths import aos_root, assert_authoritative_root
except ModuleNotFoundError:  # package import in unittest/IDE contexts
    from tools.aos_paths import aos_root, assert_authoritative_root


DEFAULT_ROOT = aos_root()
REGISTRY_PATH = Path("workflows/workflow_registry.json")
RUNS_PATH = Path("results/workflow_runs")


class WorkflowError(Exception):
    """Raised when a workflow shell operation cannot continue."""


def load_registry(root: Path) -> list[dict]:
    registry_file = root / REGISTRY_PATH
    if not registry_file.exists():
        raise WorkflowError(f"Registry not found: {registry_file}")

    data = json.loads(registry_file.read_text(encoding="utf-8"))
    workflows = data.get("workflows")
    if not isinstance(workflows, list):
        raise WorkflowError("Registry must contain a workflows list")

    present = []
    for workflow in workflows:
        source = root / workflow["source_path"]
        if source.exists():
            present.append(workflow)
    return present


def find_workflow(root: Path, workflow_id: str) -> dict:
    for workflow in load_registry(root):
        if workflow["id"] == workflow_id:
            return workflow
    raise WorkflowError(f"Workflow not found or source path missing: {workflow_id}")


def print_workflow_list(root: Path) -> None:
    for workflow in load_registry(root):
        print(f"{workflow['id']}\t{workflow['owner_agent']}\t{workflow['name']}")


def print_workflow_summary(root: Path, workflow_id: str) -> None:
    workflow = find_workflow(root, workflow_id)
    print(f"Workflow ID: {workflow['id']}")
    print(f"Name: {workflow['name']}")
    print(f"Owner agent: {workflow['owner_agent']}")
    print(f"Source: {workflow['source_path']}")
    print(f"Intake template: {workflow.get('intake_template_path') or 'None'}")
    print(f"Intake reference: {workflow.get('intake_reference_path') or 'None'}")
    print(f"Summary: {workflow['summary']}")


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_intake_file(root: Path, run_dir: Path, workflow: dict) -> Path:
    template_path = workflow.get("intake_template_path")
    if template_path:
        source = root / template_path
        if source.exists():
            destination = run_dir / source.name
            shutil.copyfile(source, destination)
            return destination

    destination = run_dir / "intake.md"
    reference = workflow.get("intake_reference_path") or workflow["source_path"]
    destination.write_text(
        "\n".join(
            [
                f"# Intake Packet: {workflow['name']}",
                "",
                "Status: empty local intake scaffold.",
                f"Workflow source: {workflow['source_path']}",
                f"Intake reference: {reference}",
                "",
                "Add source notes here before any later workflow run.",
                "No workflow logic has been executed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return destination


def packet_text(workflow: dict, run_dir: Path, intake_path: Path) -> str:
    output_placeholder = run_dir / "output_placeholder.md"
    receipt_placeholder = run_dir / "receipt_placeholder.md"
    lines = [
        f"# Workflow Run Packet: {workflow['name']}",
        "",
        f"- Workflow id: {workflow['id']}",
        f"- Workflow name: {workflow['name']}",
        f"- Owner agent: {workflow['owner_agent']}",
        f"- Source workflow path: {workflow['source_path']}",
        f"- Intake file path: {intake_path.as_posix()}",
        f"- Output placeholder: {output_placeholder.as_posix()}",
        f"- Receipt placeholder: {receipt_placeholder.as_posix()}",
        "- Human review reminder: review all future workflow outputs before any external use.",
        "- No external action reminder: this scaffold does not send, publish, upload, write records, call models, or contact external systems.",
        "",
        "## Status",
        "",
        "Prepared as an empty local run scaffold only.",
        "",
    ]
    return "\n".join(lines)


def prepare_workflow(root: Path, workflow_id: str, run_id: str | None, dry_run: bool) -> Path:
    workflow = find_workflow(root, workflow_id)
    run_name = run_id or utc_run_id()
    run_dir = root / RUNS_PATH / workflow["id"] / run_name

    planned = [
        run_dir,
        run_dir / "run_packet.md",
        run_dir / "output_placeholder.md",
        run_dir / "receipt_placeholder.md",
    ]
    template_path = workflow.get("intake_template_path")
    if template_path and (root / template_path).exists():
        planned.append(run_dir / Path(template_path).name)
    else:
        planned.append(run_dir / "intake.md")

    if dry_run:
        print("Dry run: no files written.")
        for path in planned:
            print(path.relative_to(root).as_posix())
        return run_dir

    root = assert_authoritative_root(root)
    run_dir.mkdir(parents=True, exist_ok=False)
    intake_path = write_intake_file(root, run_dir, workflow)
    (run_dir / "output_placeholder.md").write_text("Output placeholder. No workflow output has been created.\n", encoding="utf-8")
    (run_dir / "receipt_placeholder.md").write_text("Receipt placeholder. No receipt has been created.\n", encoding="utf-8")
    (run_dir / "run_packet.md").write_text(packet_text(workflow, run_dir, intake_path), encoding="utf-8")
    print(f"Prepared {run_dir.relative_to(root).as_posix()}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local workflow library shell")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available workflows")

    show_parser = subparsers.add_parser("show", help="Show one workflow summary")
    show_parser.add_argument("workflow_id")

    prepare_parser = subparsers.add_parser("prepare", help="Prepare an empty local run scaffold")
    prepare_parser.add_argument("workflow_id")
    prepare_parser.add_argument("--run-id", help="Stable run folder name")
    prepare_parser.add_argument("--dry-run", action="store_true", help="Print planned files without writing")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        if args.command == "list":
            print_workflow_list(root)
        elif args.command == "show":
            print_workflow_summary(root, args.workflow_id)
        elif args.command == "prepare":
            prepare_workflow(root, args.workflow_id, args.run_id, args.dry_run)
        else:
            parser.error(f"Unknown command: {args.command}")
    except (WorkflowError, FileExistsError, json.JSONDecodeError) as exc:
        print(f"NEEDS ATTENTION: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
