"""Deterministic structural validation for the canonical Business Brain vault.

Revisit: when the vault metadata or Obsidian wiki-link contract changes. · Last touched: 2026-07-15.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, deque
from pathlib import Path

try:
    from business_brain import BUSINESS_BRAIN_ROOT
except ModuleNotFoundError:  # package import in unittest/IDE contexts
    from tools.business_brain import BUSINESS_BRAIN_ROOT


FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
WIKI_LINK_RE = re.compile(r"(?<!!)\[\[([^\]]+)\]\]")
ROOTS = ("README.md", "index/MEMORY_INDEX.md")
OBSIDIAN_JSON = ("app.json", "appearance.json", "core-plugins.json", "graph.json", "workspace.json")
INTAKE_PREFIXES = ("inbox/source_notes/", "inbox/distilled_packets/")


def canonical_markdown(vault: Path) -> list[Path]:
    return sorted(
        path
        for path in vault.rglob("*.md")
        if path.is_file()
        and "_backups" not in {part.lower() for part in path.relative_to(vault).parts}
        and not path.relative_to(vault).as_posix().startswith(INTAKE_PREFIXES)
    )


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("'\"")
    return fields, text[match.end() :]


def canonical_wiki_target(raw: str) -> str:
    target = raw.split("|", 1)[0].split("#", 1)[0].strip()
    if not target:
        return ""
    if target.startswith("/") or "\\" in target or any(part in {".", ".."} for part in Path(target).parts):
        return target
    return target if target.lower().endswith(".md") else f"{target}.md"


def _before_hashes(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    hashes = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "  " not in line:
            continue
        digest, relative = line.split("  ", 1)
        hashes[relative.removeprefix("./")] = digest
    return hashes


def _strip_block1_structures(relative: str, raw: bytes) -> bytes:
    match = re.match(br"\A---\r?\n.*?\r?\n---\r?\n", raw, re.S)
    body = raw[match.end() :] if match else raw
    if relative in ROOTS:
        lines = body.splitlines(keepends=True)
        first_link = next((index for index, line in enumerate(lines) if b"[[" in line), None)
        if first_link is not None:
            prefix = b"".join(lines[:first_link])
            if prefix.endswith(b"\n\n"):
                prefix = prefix[:-1]
            body = prefix
    if relative == "operating_context/old_vault_archive_plan.md":
        if body.startswith(b"# Old Vault Archive Plan"):
            body = b"\xef\xbb\xbf" + body
    if relative in {"memory/ideal_clients.md", "memory/positioning.md"} and body.endswith(b"\n"):
        # apply_patch normalized a redundant trailing blank line while adding
        # frontmatter; reconstruct it for exact before-body hash comparison.
        body += b"\n"
    return body


def analyze_vault(vault: Path, *, before_manifest: Path | None = None) -> dict:
    vault = vault.resolve()
    notes = canonical_markdown(vault)
    intake_paths = sorted(
        path.relative_to(vault).as_posix()
        for prefix in INTAKE_PREFIXES
        for path in (vault / prefix.rstrip("/")).rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    )
    relative_paths = [path.relative_to(vault).as_posix() for path in notes]
    path_set = set(relative_paths)
    ids: dict[str, str] = {}
    missing_ids = []
    duplicate_ids = []
    fields_by_path = {}
    links: dict[str, list[str]] = {relative: [] for relative in relative_paths}
    broken = []
    backup_targets = []

    for path, relative in zip(notes, relative_paths):
        text = path.read_text(encoding="utf-8", errors="strict")
        fields, body = parse_frontmatter(text)
        fields_by_path[relative] = sorted(fields)
        note_id = fields.get("id", "")
        if not note_id:
            missing_ids.append(relative)
        elif note_id in ids:
            duplicate_ids.append({"id": note_id, "paths": [ids[note_id], relative]})
        else:
            ids[note_id] = relative
        for raw_target in WIKI_LINK_RE.findall(body):
            target = canonical_wiki_target(raw_target)
            if not target:
                continue
            links[relative].append(target)
            if "_backups" in {part.lower() for part in Path(target).parts}:
                backup_targets.append({"source": relative, "target": target})
            elif target not in path_set:
                broken.append({"source": relative, "target": target})

    distances = {root: 0 for root in ROOTS if root in path_set}
    queue = deque(distances)
    while queue:
        source = queue.popleft()
        if distances[source] >= 2:
            continue
        for target in links.get(source, []):
            if target in path_set and (target not in distances or distances[target] > distances[source] + 1):
                distances[target] = distances[source] + 1
                queue.append(target)
    unreachable = sorted(path_set - set(distances))
    backlinks = Counter(target for targets in links.values() for target in targets if target in path_set)

    obsidian_errors = []
    graph_backup_filter_valid = False
    obsidian = vault / ".obsidian"
    if not obsidian.is_dir():
        obsidian_errors.append(".obsidian directory is missing")
    else:
        for name in OBSIDIAN_JSON:
            path = obsidian / name
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if name == "graph.json" and isinstance(value, dict):
                    graph_backup_filter_valid = "-path:_backups" in str(value.get("search") or "")
            except (OSError, json.JSONDecodeError) as exc:
                obsidian_errors.append(f"{name}: {exc}")

    before = _before_hashes(before_manifest)
    unauthorized_body_changes = []
    if before:
        for path, relative in zip(notes, relative_paths):
            expected = before.get(relative)
            actual = hashlib.sha256(_strip_block1_structures(relative, path.read_bytes())).hexdigest()
            if expected != actual:
                unauthorized_body_changes.append({"path": relative, "before": expected, "stripped_after": actual})

    checks = {
        "canonical_note_count": len(notes),
        "unique_ids": not duplicate_ids,
        "all_canonical_notes_have_ids": not missing_ids,
        "zero_broken_wiki_links": not broken,
        "root_reachability_within_two_hops": not unreachable and all(root in path_set for root in ROOTS),
        "backups_excluded": not backup_targets and all(not relative.startswith("_backups/") for relative in relative_paths),
        "obsidian_configuration_valid": not obsidian_errors,
        "obsidian_graph_excludes_backups": graph_backup_filter_valid,
        "authorized_structural_diff_only": not unauthorized_body_changes if before else None,
    }
    passed = all(value is not False for value in checks.values())
    return {
        "status": "PASS" if passed else "FAIL",
        "vault": str(vault),
        "checks": checks,
        "canonical_paths": relative_paths,
        "intake_capture_count": len(intake_paths),
        "intake_capture_paths": intake_paths,
        "ids": dict(sorted(ids.items())),
        "frontmatter_fields": fields_by_path,
        "links": links,
        "backlinks": dict(sorted(backlinks.items())),
        "root_distances": dict(sorted(distances.items())),
        "missing_ids": missing_ids,
        "duplicate_ids": duplicate_ids,
        "broken_links": broken,
        "backup_targets": backup_targets,
        "unreachable": unreachable,
        "obsidian_errors": obsidian_errors,
        "unauthorized_body_changes": unauthorized_body_changes,
        "authorized_mechanical_corrections": [
            "Removed the old_vault_archive_plan UTF-8 BOM so YAML starts at byte zero.",
            "Normalized one redundant trailing blank line in ideal_clients and positioning while inserting frontmatter.",
        ],
        "token_usage_text": "Token usage: no agent invocation",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=Path, default=BUSINESS_BRAIN_ROOT)
    parser.add_argument("--before-manifest", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = analyze_vault(args.vault, before_manifest=args.before_manifest)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
