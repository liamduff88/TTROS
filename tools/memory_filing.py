#!/usr/bin/env python3
"""Deterministic memory filing: F1 identities, F2 generated navigation, F4 refresh, F5 verify.

D1 generated navigation only (Liam, 2026-11-06, business_brain:inbox/distilled_packets/
shared-submit-9ee2033508c914546d5426dcff7e857c.md): links and lists, never content. No model calls.

F1 reads identities from frontmatter only. A `person:<slug>` entity_key is taken exactly. Each
`participants`/`participants_text` segment is matched by its exact normalised full name to a hub's
title/aliases or an entity-index person. A new person is created only for a full name of two or
more words that matches nobody. First-name-only names, names matching more than one person, and
slugs the search indexer would exclude go to people/NEEDS_IDENTITY.md. Filing never fuzzy-matches,
so Ryan Spencer and Ryan McVeigh stay separate. The owner (Liam Duff by default) gets no hub.
F2 renders the `generated-navigation` managed section of people/<slug>.md hubs, people/INDEX.md,
people/NEEDS_IDENTITY.md and index/MEMORY_INDEX.md. It writes them in ONE
brain_memory.write_transaction with expected hashes and an analyze_vault post-write check. The
render is global and deterministic, so every run converges on the same files, and an unchanged
render writes nothing. F4 refreshes search and Graphify exactly as the importer's _refresh does.
F5 verifies the vault, two-hop reachability, search, entity resolution and hub→note graph edges.

The importer calls file_imported() only after its own transaction has returned and its refresh
is done. Filing is never nested in a Brain transaction and never blocks or undoes an import.
TTROS_MEMORY_FILING=0 turns it off.

Memory Ingest v3: notes one level deep in a v3 source folder (sources/historical_calls/<date>-<slug>-<sha8>/)
are read too. A source INDEX (type: source_index) is navigation: never an evidence note, linked from a
hub only as a topic note's "source", and its `## Needs identity` items are listed on NEEDS_IDENTITY
with a link back to it.

A hub with zero notes (its person's only evidence was removed for re-ingest) is kept and marked
"No notes yet (awaiting re-ingest)." F5 reports it as a warning, not a failure: such a person has left
the entity index, so the resolution check cannot apply until the notes return.

Revisit: when person/topic hub rules or the D1 navigation policy change. · Last touched: 2026-11-07.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import os
import re
import shutil
import sys
import tempfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import aos_entity_index as entity_index
from tools import aos_indexer, brain_memory
from tools.business_brain import BUSINESS_BRAIN_ROOT
from tools.memory_exchange_import import (
    HISTORICAL_INDEX, HISTORICAL_INDEX_EXEMPT, TOKEN_USAGE, V3_SOURCE_FOLDER, _historical_notes, append, digest,
    ledger_rows, locked,
)
from tools.validate_business_brain import WIKI_LINK_RE, analyze_vault, resolve_wiki_target

LEDGER = "queue/receipts/memory_filing.jsonl"
LOCK = "queue/locks/memory_filing.lock"
FLAG = "TTROS_MEMORY_FILING"
OWNERS_ENV = "TTROS_MEMORY_FILING_OWNERS"
DEFAULT_OWNERS = ("Liam Duff",)
SECTION = "generated-navigation"
SOURCE = "memory-filing"
# Constant on purpose: managed_section prints it inside the section, which must not drift.
SESSION = "memory-filing-generated-navigation"
PREFIX = "business_brain:"
MEMORY_INDEX = "index/MEMORY_INDEX.md"
PEOPLE_DIR = "people"
PEOPLE_INDEX = "people/INDEX.md"
NEEDS_IDENTITY = "people/NEEDS_IDENTITY.md"
SUBMIT_GLOB = "inbox/distilled_packets/shared-submit-*.md"
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
HUB_RE = re.compile(r"people/[a-z0-9]+(?:-[a-z0-9]+)*\.md\Z")
SAFE_KT = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
MACHINE_BLOCK_RE = re.compile(r"<!-- TTROS:MACHINE:([^:>]+):BEGIN -->[\s\S]*?<!-- TTROS:MACHINE:\1:END -->")
# Memory Ingest v3: one folder per source, one level beneath sources/historical_calls/.
V3_NOTE_RE = re.compile(V3_SOURCE_FOLDER + r"[^/]+\.md\Z")
SOURCE_INDEX_TYPE = "source_index"
NEEDS_HEADING = "## Needs identity"
AWAITING = "No notes yet (awaiting re-ingest)."
OUTCOMES = ("filed", "unchanged", "filing_pending", "filing_failed")
RETRY_OUTCOMES = {"filing_pending", "filing_failed"}
ATTRIBUTION = {"authenticated_identity": "ttros-memory-filing", "surface": "ttros",
               "actor_class": "deterministic_runtime", "surface_source": "address"}


class FilingError(RuntimeError):
    """Filing cannot proceed; the reason goes in a filing_failed receipt."""


def enabled() -> bool:
    return os.environ.get(FLAG, "").strip() != "0"


def owner_names(extra=()) -> tuple[str, ...]:
    configured = os.environ.get(OWNERS_ENV)
    base = [part.strip() for part in configured.split(";")] if configured is not None else list(DEFAULT_OWNERS)
    return tuple(name for name in (*base, *extra) if name)


def norm(value: str) -> str:
    return entity_index.norm(value)


def _clean(text: str) -> str:
    """Text safe inside a wiki-link alias, a YAML double-quoted scalar and one Markdown line."""
    return " ".join(re.sub(r'[\[\]|"\\`]', " ", str(text or "")).split())


def _excluded_slug(slug: str) -> bool:
    """The search indexer's own exclusion rule, applied to the hub path it would index."""
    return aos_indexer.is_excluded(f"{PEOPLE_DIR}/{slug}.md")


def _strip_stamp(text: str) -> str:
    """The note without its hermes_last_write block: what a render is compared on."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return text
    out, skipping, closed = [lines[0]], False, False
    for line in lines[1:]:
        if closed:
            out.append(line)
            continue
        if line.rstrip("\r\n") == "---":
            closed, skipping = True, False
            out.append(line)
            continue
        if line.rstrip("\r\n") == f"{brain_memory.PROVENANCE_KEY}:":
            skipping = True
            continue
        if skipping and (line.startswith("  ") or not line.strip()):
            continue
        skipping = False
        out.append(line)
    return "".join(out)


def _section_markers() -> tuple[str, str]:
    return (brain_memory.MANAGED_BEGIN.format(section=SECTION), brain_memory.MANAGED_END.format(section=SECTION))


def _without_section(text: str) -> str:
    begin, end = _section_markers()
    return re.sub(r"\n*" + re.escape(begin) + r"[\s\S]*?" + re.escape(end) + r"\n?", "", text)


# ---------------------------------------------------------------- F1: identities


def _filing_notes(relatives) -> list[str]:
    """Historical notes filing reads: the top-level ones, plus v3 source folders one level deep.

    A source folder's INDEX.md is navigation and is never one of them (nor is any note whose
    type is source_index; build_plan drops those after reading the frontmatter).
    """
    relatives = list(relatives)
    nested = {r for r in relatives if V3_NOTE_RE.fullmatch(r) and r.rsplit("/", 1)[1] not in HISTORICAL_INDEX_EXEMPT}
    return sorted(set(_historical_notes(relatives)) | nested)


def _source_index(relative: str) -> str | None:
    """The v3 source INDEX of a note in a v3 source folder, else None."""
    return relative.rsplit("/", 1)[0] + "/INDEX.md" if V3_NOTE_RE.fullmatch(relative) else None


def _source_index_needs(brain: Path) -> list[dict]:
    """Names each v3 source INDEX lists under `## Needs identity`, each with a link back to its INDEX."""
    rows = []
    for path in sorted((brain / "sources/historical_calls").glob("*/INDEX.md")):
        relative = path.relative_to(brain).as_posix()
        if not V3_NOTE_RE.fullmatch(relative):
            continue
        try:
            fm, body = aos_indexer.parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if str(fm.get("type") or "") != SOURCE_INDEX_TYPE:
            continue
        lines = body.splitlines()
        if NEEDS_HEADING not in (line.strip() for line in lines):
            continue
        start = next(i for i, line in enumerate(lines) if line.strip() == NEEDS_HEADING) + 1
        title = _clean(fm.get("title") or relative)
        for line in lines[start:]:
            if line.startswith("#"):
                break
            if line.lstrip().startswith(("- ", "* ")) and _clean(line.lstrip()[2:]):
                rows.append({"name": _clean(line.lstrip()[2:])[:200], "index": relative, "title": title})
    return rows


def _read_note(brain: Path, relative: str) -> dict:
    raw = (brain / relative).read_text(encoding="utf-8")
    fm, body = aos_indexer.parse_frontmatter(raw)
    title = _clean(entity_index._title(body, fm, Path(relative).stem.replace("-", " ").replace("_", " ")))
    # The entity index's date rules. An import date is not an event date, so it is labelled as one
    # and never sorts or counts as "latest"; observed_at is the fallback for ingest notes.
    date, _text, basis = entity_index._resolve_date(relative, title, fm)
    observed = re.match(r"(20\d\d-\d\d-\d\d)", str(fm.get("observed_at") or ""))
    if date and basis != "imported_at":
        label = date
    elif observed:
        date, label = observed.group(1), f"observed {observed.group(1)}"
    elif date:
        date, label = "", f"imported {date}"
    else:
        label = "undated"
    declared = str(fm.get("knowledge_type") or "").strip()
    ktype = declared if SAFE_KT.fullmatch(declared) else entity_index.classify(relative, fm, body)[1]
    keys = [key.strip() for key in entity_index._frontmatter_list(raw, "entity_key")
            + entity_index._frontmatter_list(raw, "entity_keys") if key.strip()]
    participants = str(fm.get("participants") or fm.get("participants_text") or "")
    return {"relative": relative, "pointer": PREFIX + relative, "title": title, "date": date, "date_label": label,
            "knowledge_type": ktype, "keys": keys, "participants": participants,
            "type": str(fm.get("type") or ""), "source_index": _source_index(relative)}


def _hub_files(brain: Path) -> dict[str, dict]:
    """Existing hubs by entity id: their title and aliases are identity sources (created once)."""
    hubs = {}
    folder = brain / PEOPLE_DIR
    if not folder.is_dir():
        return hubs
    for path in sorted(folder.glob("*.md")):
        relative = path.relative_to(brain).as_posix()
        if not HUB_RE.fullmatch(relative):
            continue
        try:
            fields, _body = brain_memory.parse_frontmatter(path.read_text(encoding="utf-8"))
        except (brain_memory.BrainMemoryError, UnicodeDecodeError):
            continue
        key = str(fields.get("entity_key") or "")
        if str(fields.get("type") or "") != "person" or key != f"person:{path.stem}":
            continue
        aliases = fields.get("aliases") if isinstance(fields.get("aliases"), list) else []
        hubs[key] = {"relative": relative, "title": _clean(fields.get("title") or path.stem),
                     "aliases": sorted({_clean(a) for a in aliases if _clean(a)})}
    return hubs


def _entity_people(db_path: Path | None) -> dict[str, dict]:
    """Entity-index persons (read-only). A missing or unbuilt index simply contributes nothing."""
    path = aos_indexer.runtime_db_path(db_path)
    if not path.is_file():
        return {}
    try:
        conn = aos_indexer.connect(path, readonly=True)
    except Exception:
        return {}
    try:
        rows = conn.execute(
            "SELECT e.entity_id, e.display_name, a.alias FROM entities e JOIN entity_aliases a "
            "ON a.entity_id = e.entity_id WHERE e.entity_type = 'person'").fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    people: dict[str, dict] = {}
    for entity_id, name, alias in rows:
        record = people.setdefault(entity_id, {"title": _clean(name), "aliases": set()})
        record["aliases"].add(_clean(alias))
    return people


def resolve_identities(notes: list[dict], *, hubs: dict, people: dict, owners=DEFAULT_OWNERS) -> dict:
    """F1. Map each note to person ids by exact declared metadata; everything else is reported."""
    owner_norms = {norm(name) for name in owners}
    owner_ids = {f"person:{entity_index.slug(name)}" for name in owners}
    known: dict[str, set[str]] = {}
    for entity_id, record in [*hubs.items(), *people.items()]:
        for name in (record["title"], *record["aliases"]):
            if norm(name):
                known.setdefault(norm(name), set()).add(entity_id)
    by_note: dict[str, set[str]] = {}
    aliases: dict[str, set[str]] = {}
    needs: dict[tuple[str, str], set[str]] = {}
    unparsed, covered, owner_skips = [], [], []

    def need(name: str, reason: str, note: dict) -> None:
        needs.setdefault((_clean(name), reason), set()).add(note["pointer"])

    def accept(entity_id: str, note: dict, names=()) -> None:
        by_note.setdefault(note["relative"], set()).add(entity_id)
        aliases.setdefault(entity_id, set()).update(_clean(n) for n in names if _clean(n))

    for note in notes:
        declared_given = set()
        for key in note["keys"]:
            if not key.startswith("person:"):
                continue
            slug = key.split(":", 1)[1]
            if key in owner_ids:
                owner_skips.append({"note": note["pointer"], "entity_key": key})
            elif not SLUG_RE.fullmatch(slug):
                need(key, "entity_key is not a safe person slug", note)
            elif "-" not in slug:
                need(key, "entity_key names a first name only", note)
            elif _excluded_slug(slug):
                need(key, "hub path would be skipped by the search indexer", note)
            else:
                accept(key, note)
                declared_given.add(slug.split("-")[0])
        for segment in (s.strip() for s in note["participants"].split(";")):
            if not segment:
                continue
            person = entity_index.parse_person(segment)
            if person is None:
                unparsed.append({"note": note["pointer"], "segment": _clean(segment)})
                continue
            name = person["name"]
            if norm(name) in owner_norms:
                owner_skips.append({"note": note["pointer"], "participant": _clean(name)})
                continue
            if len(name.split()) == 1:
                if person["qualifier"] and entity_index.slug(name) in declared_given:
                    # The entity index's own rule: this record's declared person key names them.
                    covered.append({"note": note["pointer"], "participant": _clean(segment)})
                else:
                    need(segment, "first name only", note)
                continue
            matches = set()
            for alias in person["aliases"]:
                matches |= known.get(norm(alias), set())
            if len(matches) > 1:
                need(name, "matches more than one person: " + ", ".join(sorted(matches)), note)
                continue
            entity_id = next(iter(matches)) if matches else person["id"]
            slug = entity_id.split(":", 1)[1]
            if entity_id in owner_ids:
                owner_skips.append({"note": note["pointer"], "participant": _clean(name)})
            elif not SLUG_RE.fullmatch(slug):
                need(name, "name does not give a safe person slug", note)
            elif _excluded_slug(slug):
                need(name, "hub path would be skipped by the search indexer", note)
            else:
                accept(entity_id, note, person["aliases"])
    return {"by_note": by_note, "aliases": aliases, "unparsed": unparsed, "covered": covered,
            "owner_skips": owner_skips,
            "needs": [{"name": name, "reason": reason, "pointers": sorted(pointers)}
                      for (name, reason), pointers in sorted(needs.items())]}


# ---------------------------------------------------------------- F2: render


def _submit_records(brain: Path) -> list[dict]:
    records = []
    for path in sorted(brain.glob(SUBMIT_GLOB)):
        try:
            fields, _body = brain_memory.parse_frontmatter(path.read_text(encoding="utf-8"))
        except (brain_memory.BrainMemoryError, UnicodeDecodeError):
            continue
        refs = fields.get("source_refs") if isinstance(fields.get("source_refs"), list) else []
        records.append({"pointer": PREFIX + path.relative_to(brain).as_posix(),
                        "title": _clean(fields.get("title") or path.stem), "refs": {str(r) for r in refs}})
    return records


def _hub_title(entity_id: str, hubs: dict, people: dict, aliases: set[str]) -> str:
    if entity_id in hubs:
        return hubs[entity_id]["title"]
    full = sorted(a for a in aliases if len(a.split()) > 1 and a.split()[0].lower() not in entity_index.HONORIFICS)
    if full:
        return full[0]
    if entity_id in people:
        return people[entity_id]["title"]
    return entity_id.split(":", 1)[1].replace("-", " ").title()


def _new_hub(entity_id: str, title: str, aliases: list[str]) -> str:
    slug = entity_id.split(":", 1)[1]
    alias_lines = "".join(f"  - {json.dumps(alias, ensure_ascii=False)}\n" for alias in aliases)
    return (
        "---\n"
        f"id: person-{slug}\n"
        "type: person\n"
        f"entity_key: {entity_id}\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        + (f"aliases:\n{alias_lines}" if alias_lines else "")
        + "---\n"
        f"# {title}\n\n"
        "> Person hub: generated navigation only. The list below links the historical evidence that names "
        "this person; it is not canonical truth, so read each record for what was said. "
        "· Revisit: when this person's identity or the filing rules change.\n\n"
        "[[people/INDEX|People]] · [[index/MEMORY_INDEX|Memory Index]]\n"
    )


def _new_index(note_id: str, title: str, intro: str, back: str) -> str:
    return (f"---\nid: {note_id}\ntype: index\ntitle: {json.dumps(title)}\n---\n# {title}\n\n"
            f"> {intro} · Revisit: when the filing rules change.\n\n{back}\n")


def _section(existing: str, title: str, content: str) -> str:
    return brain_memory.managed_section(existing, section_id=SECTION, title=title, content=content,
                                        source=SOURCE, session_id=SESSION)


def _folder_indexes(brain: Path) -> list[str]:
    return sorted(p.relative_to(brain).as_posix() for p in brain.glob("sources/*/INDEX.md") if p.is_file())


def _linked_count(brain: Path, relative: str, paths: set[str]) -> int:
    folder = relative.rsplit("/", 1)[0] + "/"
    _fm, body = aos_indexer.parse_frontmatter((brain / relative).read_text(encoding="utf-8"))
    targets = {resolve_wiki_target(raw, source=relative, paths=paths) for raw in WIKI_LINK_RE.findall(body)}
    return len({t for t in targets if t.startswith(folder) and t != relative and t in paths})


def _index_title(brain: Path, relative: str) -> str:
    fm, body = aos_indexer.parse_frontmatter((brain / relative).read_text(encoding="utf-8"))
    heading = next((line.lstrip("#").strip() for line in body.splitlines() if line.startswith("# ")), "")
    return _clean(fm.get("title") or heading or relative.rsplit("/", 2)[-2].replace("_", " ").title())


def build_plan(brain: Path, *, db_path: Path | None = None, owners=None) -> dict:
    """Everything F2 would write, rendered deterministically from the vault as it is now."""
    brain = Path(brain)
    folder = brain / "sources/historical_calls"
    relatives = [p.relative_to(brain).as_posix() for pattern in ("*.md", "*/*.md") for p in folder.glob(pattern)]
    # A source index is navigation, never a person's evidence note.
    notes = [note for note in (_read_note(brain, relative) for relative in _filing_notes(relatives))
             if note["type"] != SOURCE_INDEX_TYPE]
    hubs = _hub_files(brain)
    people = _entity_people(db_path)
    identity = resolve_identities(notes, hubs=hubs, people=people, owners=owners or owner_names())
    note_by_rel = {note["relative"]: note for note in notes}
    members: dict[str, list[dict]] = {}
    for relative, ids in identity["by_note"].items():
        for entity_id in ids:
            members.setdefault(entity_id, []).append(note_by_rel[relative])
    all_ids = sorted(set(members) | set(hubs))
    submits = _submit_records(brain)
    documents: dict[str, str] = {}
    hub_rows = []
    for entity_id in all_ids:
        slug = entity_id.split(":", 1)[1]
        relative = f"{PEOPLE_DIR}/{slug}.md"
        title = _hub_title(entity_id, hubs, people, identity["aliases"].get(entity_id, set()))
        rows = sorted(members.get(entity_id, []), key=lambda n: (-int(n["date"].replace("-", "") or 0), n["relative"]))
        lines = [f"- [[{n['relative'].removesuffix('.md')}|{n['title']}]] · {n['date_label']} · {n['knowledge_type']}"
                 + (f" · [[{n['source_index'].removesuffix('.md')}|source]]" if n["source_index"] else "")
                 for n in rows]
        pointers = {n["pointer"] for n in rows}
        cited = sorted((s for s in submits if s["refs"] & (pointers | {entity_id})), key=lambda s: s["pointer"])
        if not rows:
            lines = [AWAITING]
        if cited:
            lines += ["", "Submit records that cite these notes (plain pointers; not canonical until confirmed):", ""]
            lines += [f"- `{s['pointer']}` · {s['title']}" for s in cited]
        existing_path = brain / relative
        if existing_path.is_file():
            existing = existing_path.read_text(encoding="utf-8")
        else:
            names = sorted(identity["aliases"].get(entity_id, set()) | {title})
            existing = _new_hub(entity_id, title, names)
        documents[relative] = _section(existing, "Linked records", "\n".join(lines))
        latest = max((n["date"] for n in rows if n["date"]), default="")
        hub_rows.append({"entity_id": entity_id, "relative": relative, "title": title,
                         "notes": [n["pointer"] for n in rows], "count": len(rows), "latest": latest,
                         "submits": [s["pointer"] for s in cited], "awaiting_reingest": not rows})
    needs = identity["needs"]
    index_needs = _source_index_needs(brain)
    unresolved = len(needs) + len(index_needs)
    people_lines = [f"- [[{h['relative'].removesuffix('.md')}|{h['title']}]] · "
                    + ("no notes yet (awaiting re-ingest)" if h["awaiting_reingest"] else
                       f"{h['count']} record{'s' if h['count'] != 1 else ''} · latest {h['latest'] or 'undated'}")
                    for h in sorted(hub_rows, key=lambda h: (h["title"].lower(), h["entity_id"]))]
    people_lines += ["", f"[[people/NEEDS_IDENTITY|Needs identity]] · {unresolved} name"
                     f"{'s' if unresolved != 1 else ''} filing could not tie to one person"]
    existing = (brain / PEOPLE_INDEX).read_text(encoding="utf-8") if (brain / PEOPLE_INDEX).is_file() else _new_index(
        "people-index", "People",
        "Person hubs: generated navigation only. Each hub lists the historical evidence that names one "
        "person; no statement here is canonical truth.", "[[index/MEMORY_INDEX|Memory Index]]")
    documents[PEOPLE_INDEX] = _section(existing, "Person hubs", "\n".join(people_lines))
    need_lines = [f"- {n['name']} · {n['reason']} · " + ", ".join(f"`{p}`" for p in n["pointers"]) for n in needs]
    need_lines += [f"- {n['name']} · listed under Needs identity in [[{n['index'].removesuffix('.md')}|{n['title']}]]"
                   for n in index_needs]
    existing = (brain / NEEDS_IDENTITY).read_text(encoding="utf-8") if (brain / NEEDS_IDENTITY).is_file() else _new_index(
        "people-needs-identity", "Needs identity",
        "Names filing could not tie to exactly one person. Filing never guesses: each name stays here until "
        "Liam records who it is (an entity_key on the note, or the full name).", "[[people/INDEX|People]]")
    documents[NEEDS_IDENTITY] = _section(existing, "Unresolved names", "\n".join(need_lines) or "None.")
    # MEMORY_INDEX: links to the people index and every folder INDEX, with counts.
    paths = {p.relative_to(brain).as_posix() for p in brain.rglob("*.md")} | set(documents)
    nav = [f"- [[people/INDEX|People]] · {len(hub_rows)} person hub{'s' if len(hub_rows) != 1 else ''} · "
           f"{unresolved} name{'s' if unresolved != 1 else ''} needing identity"]
    for relative in _folder_indexes(brain):
        count = _linked_count(brain, relative, paths)
        nav.append(f"- [[{relative.removesuffix('.md')}|{_index_title(brain, relative)}]] · {count} linked note"
                   f"{'s' if count != 1 else ''}")
    index_text = (brain / MEMORY_INDEX).read_text(encoding="utf-8")
    documents[MEMORY_INDEX] = _section(index_text, "Generated navigation", "\n".join(nav))
    changed = {rel: text for rel, text in documents.items()
               if not (brain / rel).is_file() or _strip_stamp((brain / rel).read_text(encoding="utf-8")) != _strip_stamp(text)}
    return {"notes": notes, "identity": identity, "hubs": hub_rows, "needs": needs, "source_index_needs": index_needs,
            "documents": documents, "changed": changed}


# ---------------------------------------------------------------- checks


def _two_hop(result: dict, start: str = MEMORY_INDEX) -> set[str]:
    """Notes within two links of one root, by the vault validator's own link resolution."""
    distances = {start: 0}
    queue = deque([start])
    paths = set(result["canonical_paths"])
    while queue:
        source = queue.popleft()
        if distances[source] >= 2:
            continue
        for target in result["links"].get(source, []):
            if target in paths and target not in distances:
                distances[target] = distances[source] + 1
                queue.append(target)
    return set(distances)


def check_scope(relatives, registry) -> None:
    """Only D1 targets, each covered by search_source_identities. brain_pointer_prefixes is never consulted."""
    for relative in relatives:
        if relative not in {MEMORY_INDEX, PEOPLE_INDEX, NEEDS_IDENTITY} and not HUB_RE.fullmatch(relative):
            raise FilingError(f"not a D1 navigation target: {relative}")
        if registry.scope_for_search_identity("business_brain", PREFIX + relative) != "global":
            raise FilingError(f"not covered by search_source_identities: {relative}")


def vault_checks(vault: Path, *, before_index: str, notes: list[str], documents) -> dict:
    """The post-write gate: run inside the transaction (rollback on failure) and on dry-run copies."""
    result = analyze_vault(vault)
    reach = _two_hop(result)
    after_index = (vault / MEMORY_INDEX).read_text(encoding="utf-8")
    hubs = sorted(rel for rel in documents if HUB_RE.fullmatch(rel))
    checks = {
        "analyze_vault": result["status"],
        "failed_checks": sorted(k for k, v in result["checks"].items() if v is False),
        "notes_beyond_two_hops_of_memory_index": sorted(n for n in notes if n not in reach),
        "navigation_beyond_two_hops_of_memory_index": sorted(
            rel for rel in (PEOPLE_INDEX, NEEDS_IDENTITY, *hubs) if rel not in reach),
        "machine_blocks_byte_identical":
            [m.group(0) for m in MACHINE_BLOCK_RE.finditer(before_index)] == [m.group(0) for m in MACHINE_BLOCK_RE.finditer(after_index)],
        "memory_index_outside_section_unchanged":
            _strip_stamp(_without_section(after_index)).rstrip() == _strip_stamp(_without_section(before_index)).rstrip(),
    }
    checks["passed"] = (checks["analyze_vault"] == "PASS" and not checks["notes_beyond_two_hops_of_memory_index"]
                        and not checks["navigation_beyond_two_hops_of_memory_index"]
                        and checks["machine_blocks_byte_identical"] and checks["memory_index_outside_section_unchanged"])
    return checks


def _published_graph(brain: Path, registry) -> dict:
    from dashboard.backend.business_brain_graph import BusinessBrainGraphService
    graph = BusinessBrainGraphService(vault_root=brain, registry=registry)
    return json.loads((graph.published / "graph.json").read_text(encoding="utf-8"))


def verify_live(plan: dict, *, brain: Path, registry, db_path: Path | None, hubs: list[dict], graph_loader=None) -> dict:
    """F5 beyond the vault gate: hubs searchable, entity resolves to one person, graph hub→note edges."""
    entity_index.ensure_current(db_path)
    graph = (graph_loader or (lambda: _published_graph(brain, registry)))()
    note_ids = {n["source_path"]: n["id"] for n in graph["nodes"] if n.get("kind") == "note"}
    edges = {(e["source"], e["target"]) for e in graph["edges"] if e.get("relation") == "wiki_link"}
    problems, warnings, rows = [], [], []
    for hub in hubs:
        pointer = PREFIX + hub["relative"]
        found = aos_indexer.search(hub["title"], source="business_brain", client_scope="global", registry=registry,
                                   db_path=db_path, exact=True, limit=100, path_only=True)
        searchable = pointer in {row["path"] for group in found["groups"].values() for row in group}
        resolved = entity_index.search_entities(hub["title"], db_path=db_path, limit=50)
        exact = sorted(e["entity_id"] for e in resolved["entities"] if e["entity_type"] == "person" and e["match"] == "exact")
        view = entity_index.entity_view(hub["entity_id"], db_path=db_path) or {"knowledge": [], "sources": []}
        linked = {item["path"] for item in view["knowledge"] + view["sources"]}
        hub_id = note_ids.get(pointer)
        missing_edges = [n for n in hub["notes"] if (hub_id, note_ids.get(n)) not in edges]
        row = {"hub": pointer, "searchable": searchable, "entity_exact_person_matches": exact,
               "entity_resolution": resolved["resolution"], "notes_missing_from_entity": sorted(set(hub["notes"]) - linked),
               "wiki_link_edges": len(hub["notes"]) - len(missing_edges), "notes_missing_edges": missing_edges}
        rows.append(row)
        if not searchable:
            problems.append(f"{pointer} is not searchable")
        if exact != [hub["entity_id"]]:
            message = f"{hub['title']} resolves to {exact or 'no person'}, not {hub['entity_id']}"
            if not hub["notes"] and not exact:
                # A zero-note hub's person has left the entity index; it returns with the re-ingest.
                warnings.append(f"{pointer} has no notes yet (awaiting re-ingest); {message}")
            else:
                problems.append(message)
        if row["notes_missing_from_entity"]:
            problems.append(f"{hub['entity_id']} lacks {row['notes_missing_from_entity']}")
        if hub_id is None or missing_edges:
            problems.append(f"{pointer} graph lacks wiki_link edges to {missing_edges or 'its node'}")
    return {"passed": not problems, "problems": problems, "warnings": warnings, "hubs": rows}


# ---------------------------------------------------------------- run


def _registry(root: Path):
    from tools.business_brain_scope import load_registry
    return load_registry(root / "context/client_scope_registry.json")


def _record(root: Path, row: dict) -> None:
    """Append a receipt. A retry that fails the same way again is not re-recorded."""
    ledger = root / LEDGER
    rows = ledger_rows(ledger) if ledger.exists() else []
    last = rows[-1] if rows else None
    if (row["outcome"] in RETRY_OUTCOMES and last and last.get("trigger") == row["trigger"] == "retry"
            and last.get("outcome") == row["outcome"] and last.get("reason") == row.get("reason")
            and last.get("notes") == row["notes"]):
        return
    append(ledger, row)


def _hubs_for(plan: dict, notes: list[str]) -> list[dict]:
    wanted = {PREFIX + n for n in notes}
    return [h for h in plan["hubs"] if wanted & set(h["notes"])]


def file_notes(notes: list[str] | None, *, brain: Path = BUSINESS_BRAIN_ROOT, root: Path = ROOT,
               trigger: str = "cli", dry_run: bool = False, db_path: Path | None = None, owners=None,
               registry=None, refresh=None, verifier=None, force_verify: bool = False, record: bool = True) -> dict:
    """File the given historical notes (None = all). Returns the receipt; never raises for a filing failure.

    Holds the filing lock (never the Brain lock) for the whole attempt; write_transaction takes the
    Brain lock itself. Dry-run takes no lock and records nothing.
    """
    receipt = {"trigger": trigger, "dry_run": dry_run, "token_usage": TOKEN_USAGE,
               "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
               "notes": None if notes is None else sorted({PREFIX + n.removeprefix(PREFIX) for n in notes})}
    kwargs = dict(db_path=db_path, owners=owners, registry=registry, refresh=refresh, verifier=verifier,
                  force_verify=force_verify)
    if dry_run:
        _attempt(receipt, notes, Path(brain), root, dry_run=True, **kwargs)
        return receipt
    with locked(root / LOCK):
        _attempt(receipt, notes, Path(brain), root, dry_run=False, **kwargs)
        if record:
            _record(root, receipt)
    return receipt


def _attempt(receipt: dict, notes, brain: Path, root: Path, *, dry_run, db_path, owners, registry, refresh,
             verifier, force_verify) -> None:
    try:
        plan = build_plan(brain, db_path=db_path, owners=owners)
        all_notes = [n["relative"] for n in plan["notes"]]
        if notes is None:
            selected = all_notes
        else:
            selected = sorted({n.removeprefix(PREFIX) for n in notes})
            unknown = [n for n in selected if n not in all_notes]
            if unknown:
                raise FilingError(f"not a historical note: {', '.join(unknown)}")
        receipt["notes"] = [PREFIX + n for n in selected]
        hubs = plan["hubs"] if notes is None else _hubs_for(plan, selected)
        receipt.update({"hubs": {h["entity_id"]: h["count"] for h in plan["hubs"]},
                        "needs_identity": plan["needs"], "documents": sorted(plan["changed"])})
        registry = registry or _registry(root)
        check_scope(plan["documents"], registry)
        before_index = (brain / MEMORY_INDEX).read_text(encoding="utf-8")
        if dry_run:
            receipt.update(_dry_run(brain, plan, before_index, selected))
            receipt["outcome"] = "validated" if receipt["on_copy"]["passed"] else "would_fail"
            return
        if not plan["changed"] and not force_verify:
            receipt["outcome"] = "unchanged"
            return
        if plan["changed"]:
            if brain.resolve() != brain_memory.VAULT_ROOT or not (brain / ".git").is_dir():
                raise FilingError("filing writes only through the live Brain transaction")

            def gate(_changed):
                checks = vault_checks(brain, before_index=before_index, notes=selected, documents=plan["documents"])
                if not checks["passed"]:
                    raise FilingError(f"post-write vault gate failed: {json.dumps(checks, sort_keys=True)}")

            write = brain_memory.write_transaction(
                plan["changed"], source=SOURCE, session_id=SESSION,
                expected_hashes={rel: digest((brain / rel).read_bytes()) if (brain / rel).is_file() else None
                                 for rel in plan["changed"]},
                post_write_validator=gate, attribution=ATTRIBUTION)
            receipt.update({"commit": write.commit, "sync_status": write.sync_status,
                            "index_status": write.index_status, "changed_paths": list(write.changed_paths)})
        # F4: refresh changed people/ pages (and, on a retry, the hubs being verified) exactly as the
        # importer's _refresh does: search index, Graphify build, source/node coverage.
        pointers = {PREFIX + rel for rel in plan["changed"] if rel.startswith(f"{PEOPLE_DIR}/")}
        if force_verify:
            pointers |= {PREFIX + h["relative"] for h in hubs}
        if pointers:
            search, graph = (refresh or (lambda p: _importer_refresh(p, brain, root)))(sorted(pointers))
            receipt["search_refresh"], receipt["graphify_refresh"] = _brief(search), _brief(graph)
            if search.get("status") != "success" or graph.get("status") != "success":
                receipt["outcome"] = "filing_pending"
                receipt["reason"] = "search or Graphify refresh pending: " + str(graph.get("reason") or search.get("status"))
                return
        else:
            receipt["search_refresh"] = receipt["graphify_refresh"] = {"status": "not_needed"}
        # F5
        checks = vault_checks(brain, before_index=before_index, notes=selected, documents=plan["documents"])
        live = (verifier or (lambda p, h: verify_live(p, brain=brain, registry=registry, db_path=db_path, hubs=h)))(plan, hubs)
        receipt["verify"] = {"vault": checks, "live": live}
        if live.get("warnings"):
            receipt["warnings"] = live["warnings"]
        if checks["passed"] and live["passed"]:
            receipt["outcome"] = "filed"
        else:
            receipt["outcome"] = "filing_failed"
            receipt["reason"] = "F5 verification failed: " + "; ".join(
                live.get("problems", []) + ([] if checks["passed"] else ["vault checks failed"]))
    except brain_memory.ConcurrentEditError as exc:
        receipt.update({"outcome": "filing_pending", "reason": f"concurrent Brain edit; retried next poll: {exc}"})
    except Exception as exc:  # every failure is a receipt, never an exception for the importer
        receipt.update({"outcome": "filing_failed", "reason": f"{type(exc).__name__}: {exc}"[-2000:]})


def _importer_refresh(pointers, brain, root):
    from tools.memory_exchange_import import _refresh
    return _refresh(pointers, brain, root)


def _brief(result: dict) -> dict:
    return {key: value for key, value in result.items() if key in {"status", "reason", "indexed", "missing", "receipt_path"}}


def _dry_run(brain: Path, plan: dict, before_index: str, selected: list[str]) -> dict:
    """Prove the plan on a vault copy; the live vault is never touched."""
    with tempfile.TemporaryDirectory(prefix="memory-filing-") as temp:
        copy = Path(temp) / "vault"
        shutil.copytree(brain, copy, ignore=shutil.ignore_patterns(".git"))
        for relative, text in plan["changed"].items():
            stamped = brain_memory.apply_provenance(text, source=SOURCE, session_id=SESSION)
            brain_memory.validate_markdown(stamped, relative=relative)
            (copy / relative).parent.mkdir(parents=True, exist_ok=True)
            (copy / relative).write_text(stamped, encoding="utf-8")
        checks = vault_checks(copy, before_index=before_index, notes=selected, documents=plan["documents"])
    after = _strip_stamp(plan["documents"][MEMORY_INDEX]).splitlines()
    diff = list(difflib.unified_diff(_strip_stamp(before_index).splitlines(), after, MEMORY_INDEX, MEMORY_INDEX + " (planned)", lineterm=""))
    return {"on_copy": checks, "memory_index_diff": diff,
            "plan": {"hubs": plan["hubs"], "needs_identity": plan["needs"],
                     "unparsed_participant_segments": plan["identity"]["unparsed"],
                     "covered_by_declared_entity_key": plan["identity"]["covered"],
                     "owner_skips": len(plan["identity"]["owner_skips"]),
                     "changed": sorted(plan["changed"])}}


def file_imported(pointers: list[str], *, brain: Path, root: Path, package_id: str, **kwargs) -> dict:
    """Importer hook: file the historical notes one import wrote. Returns the import receipt's `filing`."""
    relatives = [p.removeprefix(PREFIX) for p in pointers]
    notes = [PREFIX + rel for rel in _filing_notes(relatives)]
    if not notes:
        return {"status": "not_applicable", "reason": "no historical notes"}
    if not enabled():
        return {"status": "disabled", "reason": f"{FLAG}=0"}
    result = file_notes(notes, brain=brain, root=root, trigger=f"import:{package_id}", **kwargs)
    status = result["outcome"] if result["outcome"] in {"filed", "unchanged"} else "pending"
    return {"status": status, "outcome": result["outcome"], "reason": result.get("reason"), "commit": result.get("commit")}


def record_pending(root: Path, pointers: list[str], *, reason: str, trigger: str) -> None:
    """A filing_pending receipt for notes whose filing never got to write its own."""
    with locked(root / LOCK):
        _record(root, {"trigger": trigger, "dry_run": False, "outcome": "filing_pending", "reason": reason,
                       "notes": sorted(pointers), "token_usage": TOKEN_USAGE,
                       "timestamp": dt.datetime.now(dt.timezone.utc).isoformat()})


def pending_notes(root: Path) -> list[str]:
    latest: dict[str, str] = {}
    for row in ledger_rows(root / LEDGER) if (root / LEDGER).exists() else []:
        if row.get("dry_run"):
            continue
        for pointer in row.get("notes") or []:
            latest[pointer] = row.get("outcome", "")
    return sorted(p for p, outcome in latest.items() if outcome in RETRY_OUTCOMES)


def retry_pending(*, brain: Path = BUSINESS_BRAIN_ROOT, root: Path = ROOT, **kwargs) -> dict:
    """Called by every importer poll: re-file notes whose last filing did not finish."""
    if not enabled():
        return {"outcome": "disabled"}
    pending = pending_notes(root)
    if not pending:
        return {"outcome": "nothing_pending"}
    return file_notes(pending, brain=brain, root=root, trigger="retry", force_verify=True, **kwargs)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TTROS deterministic memory filing (generated navigation only)")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true", help="file every historical note")
    target.add_argument("--note", help="file one historical note (business_brain:sources/historical_calls/<name>.md)")
    parser.add_argument("--dry-run", action="store_true", help="prove the plan on a vault copy; write nothing")
    parser.add_argument("--json", action="store_true", help="print the full receipt as JSON")
    parser.add_argument("--brain", type=Path, default=BUSINESS_BRAIN_ROOT)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--db", type=Path, help="search database (default: the runtime index)")
    parser.add_argument("--owner", action="append", default=[], help="extra owner name to exclude from hubs")
    args = parser.parse_args(argv)
    if not enabled() and not args.dry_run:
        print(json.dumps({"outcome": "disabled", "reason": f"{FLAG}=0"}))
        return 0
    result = file_notes(None if args.all else [args.note], brain=args.brain, root=args.root,
                        trigger="cli:--all" if args.all else "cli:--note", dry_run=args.dry_run,
                        db_path=args.db, owners=owner_names(args.owner))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps({k: result.get(k) for k in ("outcome", "reason", "warnings", "commit", "documents", "hubs")}, indent=2))
        print(TOKEN_USAGE)
    return 0 if result["outcome"] in {"filed", "unchanged", "validated"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
