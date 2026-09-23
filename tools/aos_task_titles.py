#!/usr/bin/env python3
"""Deterministic human-readable titles for Agentic OS work items.

Revisit: when work-item creation metadata or operator title conventions change. · Last touched: 2026-09-22.
"""

from __future__ import annotations

import re
from pathlib import PurePath
from typing import Iterable


TECHNICAL_ID_RE = re.compile(r"^AOS-\d{4}-\d{4}$", re.IGNORECASE)
_COMMAND_PREFIX_RE = re.compile(r"^/work\s+(?:(?:claude|codex|hermes)\s+)?", re.IGNORECASE)
_FILE_COPY_SUFFIX_RE = re.compile(r"\s*\(\d+\)(?=\.[A-Za-z0-9]{1,8}$|$)")
_SKIP_LINE_PREFIXES = (
    "permission mode", "do not ask", "assume approval", "do not ", "stop only",
    "work only in", "for codex", "claude is for", "codex is for", "hermes is for",
)
_GENERIC_TITLES = {"task", "work item", "queue item", "new task", "untitled", "untitled task"}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n-:|")


def _is_usable(value: object) -> bool:
    text = _clean(value)
    if not text or TECHNICAL_ID_RE.fullmatch(text) or text.casefold() in _GENERIC_TITLES:
        return False
    return not (text.casefold().startswith("permission mode") or text.casefold().startswith("/work "))


def humanize_identifier(value: object) -> str:
    """Turn a workflow/action/file identifier into a readable title."""
    text = _clean(value)
    if not text:
        return ""
    name = PurePath(text).name
    name = _FILE_COPY_SUFFIX_RE.sub("", name)
    name = re.sub(r"\.(?:md|txt|json|jsonl|yaml|yml|pdf|docx?)$", "", name, flags=re.IGNORECASE)
    words = [part for part in re.split(r"[_\-\s]+", name) if part]
    return " ".join(word if word.isupper() else word.capitalize() for word in words)


def _workflow_from_tags(tags: object) -> str:
    values: Iterable[object]
    if isinstance(tags, str):
        values = re.split(r"[,\n]", tags)
    elif isinstance(tags, (list, tuple, set)):
        values = tags
    else:
        values = ()
    for raw in values:
        value = _clean(raw)
        if value.casefold().startswith("workflow:"):
            return value.split(":", 1)[1].strip()
    return ""


def _request_title(context: object) -> str:
    raw = str(context or "").strip()
    if not raw:
        return ""
    lines = [re.sub(r"^[#*>\-\s]+", "", line).strip() for line in raw.splitlines()]
    for index, line in enumerate(lines):
        if line.casefold() in {"task", "task:", "request", "request:"}:
            lines = lines[index + 1:] + lines[:index]
            break
    for line in lines:
        candidate = _COMMAND_PREFIX_RE.sub("", line).strip()
        lowered = candidate.casefold()
        if not candidate or lowered.startswith(_SKIP_LINE_PREFIXES):
            continue
        if TECHNICAL_ID_RE.fullmatch(candidate):
            continue
        intake = re.match(r"^(?:memory|source|document|file)\s+intake\s*:\s*(.+)$", candidate, re.IGNORECASE)
        if intake:
            subject = humanize_identifier(intake.group(1))
            return f"Ingest {subject}" if subject else "Ingest task"
        candidate = re.split(r"(?<=[.!?])\s+", candidate, maxsplit=1)[0]
        candidate = _clean(candidate)
        if not candidate:
            continue
        sentence_case = candidate[:1].isupper() and candidate[1:] == candidate[1:].lower()
        if (re.fullmatch(r"[a-z0-9_\- ]+", candidate) or sentence_case) and len(candidate.split()) <= 18:
            candidate = humanize_identifier(candidate)
        return candidate
    return ""


def derive_task_title(
    *,
    title: object = "",
    workflow_id: object = "",
    action_name: object = "",
    context: object = "",
    tags: object = (),
) -> str:
    """Resolve the operator title without a model call or record mutation."""
    explicit = _clean(title)
    if _is_usable(explicit):
        if re.fullmatch(r"[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)+", explicit):
            return humanize_identifier(explicit)
        return explicit

    workflow = _clean(workflow_id) or _workflow_from_tags(tags)
    if workflow:
        readable = humanize_identifier(workflow)
        if readable:
            return readable

    action = _clean(action_name)
    if action:
        readable = humanize_identifier(action)
        if readable:
            return readable

    request = _request_title(context)
    return request or "Untitled task"


def title_for_item(item: dict) -> str:
    return derive_task_title(
        title=item.get("title"),
        workflow_id=item.get("workflow_id") or item.get("workflow"),
        action_name=item.get("action_name") or item.get("action"),
        context=item.get("context") or item.get("request"),
        tags=item.get("tags") or (),
    )
