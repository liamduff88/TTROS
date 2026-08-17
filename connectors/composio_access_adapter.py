#!/usr/bin/env python3
"""Thin stdlib-only access spine for the local Composio CLI.

Revisit: when connector mutation approval or Composio CLI contracts change. · Last touched: 2026-07-31.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from gmail_draft_policy import GmailAuthorityError, authorize_generic_gmail_action
except ModuleNotFoundError:  # package import in tests/IDE contexts
    from connectors.gmail_draft_policy import GmailAuthorityError, authorize_generic_gmail_action


COMPOSIO = Path("/home/liam/.composio/composio")
ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path(__file__).with_name("composio_tool_registry.json")
TIMEOUT_SECONDS = 30
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ACTION_RE = re.compile(r"^[A-Z][A-Z0-9_]+$")
MUTATION_VERBS = {
    "SEND",
    "CREATE",
    "UPDATE",
    "DELETE",
    "MODIFY",
    "ADD",
    "FORWARD",
    "POST",
    "PUBLISH",
    "UPLOAD",
}
PUBLISH_VERBS = {"SEND", "POST", "PUBLISH", "UPLOAD"}
SECRET_VALUE_RES = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9._~+/-]{12,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _append_gate_receipt(
    *,
    work_item_id: str,
    action: str,
    target: str,
    decision: str,
    reason: str,
    root: Path | None = None,
) -> None:
    path = (root or ROOT) / "queue/receipts/external-action-gate.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": now_utc(),
        "work_item_id": work_item_id or "unavailable",
        "action": action,
        "target_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest() if target else None,
        "decision": decision,
        "reason": reason,
        "execution_occurred": decision == "allowed",
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _queue_item(work_item_id: str) -> dict[str, Any] | None:
    if not work_item_id:
        return None
    path = ROOT / "queue/work_items.jsonl"
    if not path.is_file():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("id") == work_item_id:
            return row
    return None


def _payload_contains_secret(value: Any) -> bool:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return any(pattern.search(rendered) for pattern in SECRET_VALUE_RES)


def authorize_external_mutation(*, action: str, target: str, work_item_id: str, payload: dict[str, Any]) -> tuple[bool, str]:
    verbs = set(action.split("_")).intersection(MUTATION_VERBS)
    if not verbs:
        return True, "read-only action"
    if _payload_contains_secret(payload):
        return False, "secret-exposure check failed"
    item = _queue_item(work_item_id)
    if item is None:
        return False, "exact queue item approval is required"
    approved_actions = item.get("approved_external_action")
    if isinstance(approved_actions, str):
        approved_actions = [approved_actions]
    approved_actions = {str(value).strip().upper() for value in (approved_actions or [])}
    if action not in approved_actions:
        return False, "queue item does not approve this exact action"
    if not target or str(item.get("approved_external_target") or "").strip() != target:
        return False, "queue item does not approve this exact target"
    if not str(item.get("approved_external_command") or "").strip():
        return False, "typed per-action operator command is missing"
    if verbs.intersection(PUBLISH_VERBS) and item.get("publish_review_passed") is not True:
        return False, "pre-publish review has not passed"
    if "SEND" in verbs and (item.get("email_safe") is not True or not str(item.get("outreach_basis") or "").strip()):
        return False, "email-safe/CASL basis is missing"
    return True, "exact action, target, operator command, and publication gates matched"


def _authorize_or_emit(*, action: str, payload: dict[str, Any], args: argparse.Namespace) -> bool:
    work_item_id = str(getattr(args, "work_item_id", "") or "").strip()
    target = str(getattr(args, "target", "") or "").strip()
    allowed, reason = authorize_external_mutation(
        action=action,
        target=target,
        work_item_id=work_item_id,
        payload=payload,
    )
    _append_gate_receipt(
        work_item_id=work_item_id,
        action=action,
        target=target,
        decision="allowed" if allowed else "blocked",
        reason=reason,
    )
    if not allowed:
        emit({"ok": False, "tool_slug": action, "args": None, "error": reason, "transmitted": False})
    return allowed


def clean_error(text: str) -> str:
    lines = [line.strip() for line in ANSI_RE.sub("", text).splitlines() if line.strip()]
    useful = [line for line in lines if "Error" in line or "error" in line or "Unable" in line]
    return (useful[0] if useful else (lines[0] if lines else "Composio CLI returned no detail"))[:500]


def parse_cli_stdout(stdout: str) -> tuple[Any | None, bool]:
    """Parse plain or decorated CLI JSON; report whether raw output must be retained."""
    plain = ANSI_RE.sub("", stdout).strip()
    if not plain:
        return None, False
    try:
        return json.loads(plain), False
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    candidates: list[tuple[int, Any]] = []
    for index, char in enumerate(plain):
        if char not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(plain, index)
        except json.JSONDecodeError:
            continue
        candidates.append((end - index, value))
    if candidates:
        return max(candidates, key=lambda candidate: candidate[0])[1], True
    return None, True


def cli(*args: str, timeout: int = TIMEOUT_SECONDS) -> dict[str, Any]:
    if not COMPOSIO.is_file():
        return {"ok": False, "exit_code": None, "error": f"Composio CLI not found: {COMPOSIO}"}
    try:
        result = subprocess.run(
            [str(COMPOSIO), *args],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": None, "error": f"Composio CLI timed out after {timeout}s"}
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    parsed, mixed_output = parse_cli_stdout(stdout)
    response: dict[str, Any] = {"ok": result.returncode == 0, "exit_code": result.returncode}
    if parsed is not None:
        response["data"] = parsed
    if stdout and mixed_output:
        response["raw_stdout"] = stdout
    if stderr:
        response["stderr"] = clean_error(stderr)
    if result.returncode != 0:
        response["error"] = clean_error(stderr or stdout)
    return response


def send_authorized_morning_brief_agentmail(
    *,
    root: Path,
    inbox_id: str,
    recipient: str,
    subject: str,
    text: str,
) -> dict[str, Any]:
    """Execute only Liam's standing internal morning-brief AgentMail send."""
    from tools.aos_orchestration import load_notifications

    action = "AGENT_MAIL_SEND_EMAIL"
    target = str(recipient).strip()
    allowed_recipients = set(load_notifications(root).get("agentmail_internal") or [])
    checks = (
        (target == "liam@timetorevenue.com", "recipient is not the authorized morning-brief target"),
        (target in allowed_recipients, "recipient is not on the internal AgentMail allowlist"),
        (str(inbox_id).strip().endswith("@agentmail.to"), "AgentMail inbox id is invalid"),
        (subject.startswith("David Morning Brief — "), "subject is outside the morning-brief contract"),
        (text.startswith("# David Morning Brief\n"), "body is not a David morning-brief artifact"),
    )
    failure = next((reason for passed, reason in checks if not passed), None)
    payload = {
        "inbox_id": str(inbox_id).strip(),
        "to": [target],
        "subject": subject,
        "text": text,
    }
    if failure or _payload_contains_secret(payload):
        reason = failure or "secret-exposure check failed"
        _append_gate_receipt(
            work_item_id="DAVID-MORNING-BRIEF",
            action=action,
            target=target,
            decision="blocked",
            reason=reason,
            root=root,
        )
        return {"ok": False, "error": reason, "transmitted": False}
    _append_gate_receipt(
        work_item_id="DAVID-MORNING-BRIEF",
        action=action,
        target=target,
        decision="allowed",
        reason="standing internal morning-brief authorization and recipient allowlist matched",
        root=root,
    )
    return cli("execute", action, "-d", json.dumps(payload, separators=(",", ":")), timeout=120)


def load_registry() -> dict[str, Any]:
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot load registry {REGISTRY}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("toolkits"), list):
        raise SystemExit(f"Invalid registry structure: {REGISTRY}")
    return data


def sanitize_whoami(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data")
    if result["ok"] and isinstance(data, str):
        # CLI releases may render a human-readable table instead of JSON.
        plain = ANSI_RE.sub("", data)
        email_match = re.search(r"(?im)^\s*(?:[│|]\s*)?Email\s*(?:[│|:]|\s{2,})\s*([^│|\r\n]+)", plain)
        org_match = re.search(
            r"(?im)^\s*(?:[│|]\s*)?(?:Current\s+Org|Organization|Workspace)\s*(?:[│|:]|\s{2,})\s*([^│|\r\n]+)",
            plain,
        )
        data = {
            "email": email_match.group(1).strip() if email_match else None,
            "current_org_name": org_match.group(1).strip() if org_match else None,
        }
    if result["ok"] and isinstance(data, dict) and data.get("email") and data.get("current_org_name"):
        return {
            "ok": True,
            "account_type": data.get("account_type", "human"),
            "identity_present": True,
            "organization_present": True,
            "source": "live_cli",
        }
    registry = load_registry()
    verified = registry.get("current_verification", {}).get("identity", {})
    if verified.get("email") and verified.get("organization"):
        return {
            "ok": True,
            "account_type": verified.get("account_type", "human"),
            "identity_present": True,
            "organization_present": True,
            "source": "last_verified_live_cli",
            "live_probe_error": result.get("error") or "Live CLI returned incomplete identity fields",
        }
    return {
        "ok": False,
        "error": result.get("error", "Identity unavailable or incomplete"),
    }


def normalize_connections(result: dict[str, Any]) -> dict[str, Any]:
    if not result["ok"] or not isinstance(result.get("data"), dict):
        registry = load_registry()
        verified = registry.get("current_verification", {})
        if verified.get("state") == "verified" and isinstance(verified.get("accounts"), list):
            return {
                "ok": True,
                "current": True,
                "source": "last_verified_live_cli",
                "accounts": verified["accounts"],
                "live_probe_error": result.get("error", "Connected accounts live probe unavailable"),
            }
        return {
            "ok": False,
            "current": False,
            "accounts": [],
            "error": result.get("error", "Connected accounts unavailable"),
            "stale_snapshot": registry.get("stale_snapshot"),
        }
    accounts: list[dict[str, Any]] = []
    for toolkit, rows in sorted(result["data"].items()):
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                continue
            accounts.append(
                {
                    "toolkit": toolkit,
                    "account": row.get("alias") or row.get("word_id") or f"account-{index}",
                    "status": row.get("status", "UNKNOWN"),
                }
            )
    return {"ok": True, "current": True, "source": "live_cli", "accounts": accounts}


def command_status(_: argparse.Namespace) -> int:
    version = cli("--version")
    identity = sanitize_whoami(cli("whoami"))
    connections = normalize_connections(cli("connections", "list"))
    state = "pass" if version["ok"] and identity["ok"] and connections["ok"] else "needs_attention"
    emit(
        {
            "adapter": "composio_access_spine_v0",
            "checked_at": now_utc(),
            "state": state,
            "cli": {"path": str(COMPOSIO), "available": COMPOSIO.is_file(), "version": version.get("data")},
            "identity": identity,
            "connections": connections,
            "policy_mode": "operator-command enabled; Gmail draft-only outbound preparation",
        }
    )
    return 0


def command_whoami(_: argparse.Namespace) -> int:
    emit(sanitize_whoami(cli("whoami")))
    return 0


def command_connected_accounts(_: argparse.Namespace) -> int:
    emit(normalize_connections(cli("connections", "list")))
    return 0


def command_registry(_: argparse.Namespace) -> int:
    emit(load_registry())
    return 0


def valid_tool_slug(tool_slug: str) -> str | None:
    normalized = tool_slug.upper()
    return normalized if ACTION_RE.fullmatch(normalized) else None


def tool_response(
    *,
    tool_slug: str,
    mode: str,
    command: list[str],
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "ok": bool(result and result.get("ok")) and error is None,
        "tool_slug": tool_slug,
        "mode": mode,
        "command": command,
        "timestamp": now_utc(),
    }
    if result is not None and "data" in result:
        response["stdout"] = result["data"]
    if result is not None and "raw_stdout" in result:
        response["raw_stdout"] = result["raw_stdout"]
    if result is not None and "stderr" in result:
        response["stderr"] = result["stderr"]
    failure = error or (result or {}).get("error")
    if failure:
        response["error"] = failure
    return response


def command_tool_info(args: argparse.Namespace) -> int:
    tool_slug = valid_tool_slug(args.tool_slug)
    if tool_slug is None:
        emit(
            tool_response(
                tool_slug=args.tool_slug,
                mode="tool_info",
                command=[],
                error="Tool slug must contain only A-Z, 0-9, and underscore.",
            )
        )
        return 2
    command = [str(COMPOSIO), "tools", "info", tool_slug]
    result = cli("tools", "info", tool_slug)
    emit(tool_response(tool_slug=tool_slug, mode="tool_info", command=command, result=result))
    return 0 if result["ok"] else 2


def command_tool_run(args: argparse.Namespace) -> int:
    tool_slug = valid_tool_slug(args.tool_slug)
    if tool_slug is None:
        emit({
            "ok": False,
            "tool_slug": args.tool_slug,
            "args": None,
            "error": "Tool slug must contain only A-Z, 0-9, and underscore.",
        })
        return 2
    try:
        authorize_generic_gmail_action(tool_slug)
    except GmailAuthorityError as exc:
        emit({"ok": False, "tool_slug": tool_slug, "args": None, "error": str(exc)})
        return 2
    try:
        payload = json.loads(args.json_args)
    except json.JSONDecodeError as exc:
        emit({
            "ok": False,
            "tool_slug": tool_slug,
            "args": None,
            "error": f"json_args must be valid JSON: {exc.msg}",
        })
        return 2
    if not isinstance(payload, dict):
        emit({
            "ok": False,
            "tool_slug": tool_slug,
            "args": payload,
            "error": "json_args must decode to a JSON object.",
        })
        return 2

    data = json.dumps(payload, separators=(",", ":"))
    command = [str(COMPOSIO), "execute", tool_slug, "-d", data]
    mutation_verbs = sorted(MUTATION_VERBS.intersection(tool_slug.split("_")))
    if mutation_verbs and not args.confirmed:
        emit({
            "ok": False,
            "tool_slug": tool_slug,
            "args": payload,
            "error": f"External mutation tool requires --confirmed ({', '.join(mutation_verbs)}).",
        })
        return 2
    if mutation_verbs and not _authorize_or_emit(action=tool_slug, payload=payload, args=args):
        return 2

    result = cli("execute", tool_slug, "-d", data)
    response = {"ok": result["ok"], "tool_slug": tool_slug, "args": payload}
    if result["ok"]:
        response["result"] = result.get("data", result.get("raw_stdout"))
    else:
        response["error"] = result.get("error", "Composio tool execution failed")
    emit(response)
    return 0 if result["ok"] else 2


def toolkit_record(toolkit: str) -> dict[str, Any] | None:
    key = toolkit.lower().replace("-", "_")
    for record in load_registry()["toolkits"]:
        names = [record.get("slug", ""), *record.get("aliases", [])]
        if key in {str(name).lower().replace("-", "_") for name in names}:
            return record
    return None


def command_prepare(args: argparse.Namespace) -> int:
    record = toolkit_record(args.toolkit)
    if record is None:
        emit({"ok": False, "error": f"Toolkit is not in the local registry: {args.toolkit}"})
        return 2
    intent = " ".join(args.intent).strip()
    discovery = cli("search", intent, "--toolkits", record["slug"], "--limit", str(args.limit))
    mutation_policy = (
        "Gmail generic routing is read-only. Only GMAIL_CREATE_EMAIL_DRAFT may run through "
        "gmail_draft_adapter; send/reply/forward/schedule and other mutations are forbidden."
        if record["slug"] == "gmail"
        else "Actual send/write/book/push/publish/delete/mutate requires the specific adapter run command with --execute --operator-command."
    )
    emit(
        {
            "ok": discovery["ok"],
            "mode": "prepare_only",
            "toolkit": record["slug"],
            "intent": intent,
            "connection_evidence": record["connection_evidence"],
            "action_families": record["action_families"],
            "candidates": discovery.get("data", []),
            "discovery_error": discovery.get("error"),
            "next": "Choose a specific action slug, inspect it with `composio execute ACTION --get-schema`, then use adapter run.",
            "mutation_policy": mutation_policy,
        }
    )
    return 0 if discovery["ok"] else 2


def command_run(args: argparse.Namespace) -> int:
    record = toolkit_record(args.toolkit)
    if record is None:
        emit({"ok": False, "error": f"Toolkit is not in the local registry: {args.toolkit}"})
        return 2
    action = args.action.upper()
    if not ACTION_RE.fullmatch(action):
        emit({"ok": False, "error": "Action must be a Composio slug containing only A-Z, 0-9, and underscore."})
        return 2
    try:
        authorize_generic_gmail_action(action)
    except GmailAuthorityError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    prefixes = tuple(prefix.upper() + "_" for prefix in record.get("action_prefixes", []))
    if prefixes and not action.startswith(prefixes):
        emit({"ok": False, "error": f"Action {action} does not match toolkit {record['slug']} prefixes."})
        return 2
    try:
        payload = json.loads(args.data)
    except json.JSONDecodeError as exc:
        emit({"ok": False, "error": f"--data must be valid JSON: {exc.msg}"})
        return 2
    if not isinstance(payload, dict):
        emit({"ok": False, "error": "--data must decode to a JSON object."})
        return 2
    execute_requested = args.execute or args.operator_command
    if execute_requested and not (args.execute and args.operator_command):
        emit({"ok": False, "error": "Actual execution requires both --execute and --operator-command."})
        return 2
    if execute_requested and not _authorize_or_emit(action=action, payload=payload, args=args):
        return 2
    cli_args = ["execute", action, "-d", json.dumps(payload, separators=(",", ":"))]
    if not execute_requested:
        cli_args.append("--dry-run")
    result = cli(*cli_args)
    emit(
        {
            "ok": result["ok"],
            "mode": "execute" if execute_requested else "dry_run",
            "toolkit": record["slug"],
            "action": action,
            "result": result.get("data"),
            "error": result.get("error"),
        }
    )
    return 0 if result["ok"] else 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Hermes / Agentic OS generic Composio adapter")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("status").set_defaults(handler=command_status)
    commands.add_parser("whoami").set_defaults(handler=command_whoami)
    commands.add_parser("connected_accounts").set_defaults(handler=command_connected_accounts)
    commands.add_parser("registry").set_defaults(handler=command_registry)

    tool_info = commands.add_parser("tool-info", help="Inspect a Composio tool")
    tool_info.add_argument("tool_slug")
    tool_info.set_defaults(handler=command_tool_info)

    tool_run = commands.add_parser("tool-run", help="Execute a Composio tool through the shared spine")
    tool_run.add_argument("tool_slug")
    tool_run.add_argument("json_args", help="JSON object containing tool arguments")
    tool_run.add_argument(
        "--confirmed",
        action="store_true",
        help="Explicitly confirm execution of an external mutation tool",
    )
    tool_run.add_argument("--work-item-id", help="Queue item carrying exact action approval")
    tool_run.add_argument("--target", help="Exact externally affected target named by Liam")
    tool_run.set_defaults(handler=command_tool_run)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("toolkit")
    prepare.add_argument("intent", nargs="+")
    prepare.add_argument("--limit", type=int, default=10, choices=range(1, 101), metavar="1..100")
    prepare.set_defaults(handler=command_prepare)

    run = commands.add_parser("run")
    run.add_argument("toolkit")
    run.add_argument("action")
    run.add_argument("--data", default="{}", help="JSON object for the action")
    run.add_argument("--execute", action="store_true", help="Execute instead of previewing with --dry-run")
    run.add_argument("--operator-command", action="store_true", help="Confirm Liam explicitly commanded this specific action")
    run.add_argument("--work-item-id", help="Queue item carrying exact action approval")
    run.add_argument("--target", help="Exact externally affected target named by Liam")
    run.set_defaults(handler=command_run)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
