#!/usr/bin/env python3
"""Run the complete local David morning-brief path.

Revisit: when the detector, Ask David API, or morning delivery boundary changes. · Last touched: 2026-08-17.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

try:
    from aos_executive_brief import FINDINGS_REL, refresh
except ModuleNotFoundError:
    from tools.aos_executive_brief import FINDINGS_REL, refresh


ROOT = Path(os.environ.get("AOS_ROOT", Path(__file__).resolve().parents[1])).resolve()
OUTPUT_REL = Path("context/DAVID_MORNING_BRIEF.md")
DELIVERY_LOG_REL = Path("logs/david_morning_brief_delivery.jsonl")
RECEIPT_DIR_REL = Path("queue/receipts")
LOCAL_TIMEZONE = ZoneInfo("America/Vancouver")
EMAIL_RECIPIENT = "liam@timetorevenue.com"
AGENTMAIL_INBOX_ID = "olmec1@agentmail.to"
DEFAULT_ENDPOINT = os.environ.get(
    "AOS_MORNING_BRIEF_API_URL",
    "http://127.0.0.1:8010/api/dashboard/ask-david",
)
DETECTOR_USAGE = {"model_invocations": 0, "input_tokens": 0, "output_tokens": 0}
PROMPT = """This is a scheduled read-only morning interpretation, not a request to execute work.
Use the fresh deterministic morning findings supplied by mandatory Context Assembler context.
Write a concise executive brief of at most 400 words with exactly these headings:
## What matters today
## Why it matters and current evidence
## Liam decisions / next focus
Select at most three priorities. Interpret current status and evidence; do not dump all findings.
Distinguish work already done from unresolved work and name any decision actually waiting on Liam.
Do not create queue work, emit an execution handoff, send anything, mutate connectors, or take any external action."""


class MorningBriefRunError(RuntimeError):
    """The complete morning path did not reach its local delivery boundary."""


def _post_json(endpoint: str, payload: dict[str, Any], timeout: int = 660) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise MorningBriefRunError(f"Ask David request failed: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise MorningBriefRunError("Ask David returned a non-object response")
    return value


def _validate_david_response(response: dict[str, Any]) -> None:
    if response.get("success") is not True or response.get("kind") != "david_reply":
        raise MorningBriefRunError(
            f"Ask David did not return a read-only David reply: {response.get('kind') or 'unknown'}"
        )
    queue_effect = response.get("queue_effect") if isinstance(response.get("queue_effect"), dict) else {}
    if queue_effect.get("unchanged") is not True or queue_effect.get("items_created") != 0:
        raise MorningBriefRunError("Ask David did not prove a zero-queue consultation")
    usage = response.get("token_usage") if isinstance(response.get("token_usage"), dict) else {}
    if usage.get("available") is not True or usage.get("completed") is not True or usage.get("failed") is not False:
        raise MorningBriefRunError("Ask David did not expose completed authoritative token usage")
    answer = str(response.get("response") or "").strip()
    for heading in (
        "## What matters today",
        "## Why it matters and current evidence",
        "## Liam decisions / next focus",
    ):
        if heading not in answer:
            raise MorningBriefRunError(f"David brief is missing required heading: {heading}")
    if len(answer.split()) > 400:
        raise MorningBriefRunError("David brief exceeded the 400-word concise-delivery contract")


def _render_artifact(response: dict[str, Any], detector: dict[str, Any], generated: dt.datetime) -> str:
    usage = response["token_usage"]
    context = response.get("context") if isinstance(response.get("context"), dict) else {}
    return "\n".join((
        "# David Morning Brief",
        f"> Revisit: when the scheduled morning path or delivery boundary changes. · Last touched: {generated.date().isoformat()}.",
        f"> Generated: {generated.replace(microsecond=0).isoformat().replace('+00:00', 'Z')} · non-authoritative local delivery artifact",
        "",
        "## Path evidence",
        f"- Detector observed: `{detector.get('observed_at') or 'unknown'}`; findings: {detector.get('finding_count', len(detector.get('findings') or []))}",
        "- Detector token usage: 0 model invocations, 0 input, 0 output",
        f"- Context Assembler: {context.get('total_bytes', 'unavailable')} bytes / {context.get('total_tokens', 'unavailable')} estimated tokens",
        f"- David provider/model: `{usage.get('provider') or 'unavailable'}` / `{usage.get('model') or 'unavailable'}`",
        f"- Actual usage: input {usage.get('input_tokens')}, cached input {usage.get('cache_read_tokens')}, output {usage.get('output_tokens')}, reasoning {usage.get('reasoning_tokens')}, total {usage.get('total_tokens')}",
        f"- Invocation: `{response.get('invocation_id') or usage.get('invocation_id') or 'unavailable'}`; queue unchanged: yes",
        "",
        str(response["response"]).strip(),
        "",
    ))


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _delivery_records(path: Path, run_id: str, channel: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("run_id") == run_id and record.get("channel") == channel:
            records.append(record)
    return records


def _message_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("message_id", "messageId", "id"):
        candidate = value.get(key)
        if isinstance(candidate, (str, int)) and str(candidate).strip():
            return str(candidate)
    for key in ("data", "response", "result", "message"):
        candidate = _message_id(value.get(key))
        if candidate:
            return candidate
    return None


def _agentmail_send(root: Path, recipient: str, subject: str, body: str) -> dict[str, Any]:
    from connectors.composio_access_adapter import send_authorized_morning_brief_agentmail

    response = send_authorized_morning_brief_agentmail(
        root=root,
        inbox_id=AGENTMAIL_INBOX_ID,
        recipient=recipient,
        subject=subject,
        text=body,
    )
    provider = response.get("data") if isinstance(response.get("data"), dict) else {}
    if response.get("ok") is not True or provider.get("successful") is not True:
        raise MorningBriefRunError("AgentMail send was not acknowledged by the governed Composio adapter")
    return {
        "provider": "agentmail_via_composio_governed_adapter",
        "provider_message_id": _message_id(provider) or "unavailable",
        "acknowledged": True,
    }


def _telegram_send(root: Path, body: str) -> dict[str, Any]:
    from tools.aos_orchestration import default_bridge_send, load_notifications

    recipients = load_notifications(root).get("telegram") or []
    if not recipients:
        raise MorningBriefRunError("Telegram operator allowlist has no exposed recipient")
    response = default_bridge_send(str(recipients[0]), body)
    return {
        "provider": "telegram_via_existing_aos_bridge",
        "provider_message_id": _message_id(response) or "unavailable",
        "acknowledged": True,
    }


def _send_once(
    *,
    log_path: Path,
    run_id: str,
    channel: str,
    artifact_sha256: str,
    send: Callable[[], dict[str, Any]],
    now: dt.datetime,
) -> dict[str, Any]:
    prior = _delivery_records(log_path, run_id, channel)
    sent = next((record for record in reversed(prior) if record.get("status") == "sent"), None)
    if sent:
        return {
            "channel": channel,
            "status": "already_sent",
            "artifact_sha256": artifact_sha256,
            "provider": sent.get("provider", "unavailable"),
            "provider_message_id": sent.get("provider_message_id", "unavailable"),
            "acknowledged": True,
        }
    if prior and prior[-1].get("status") == "intent":
        return {
            "channel": channel,
            "status": "ambiguous_not_retried",
            "artifact_sha256": artifact_sha256,
            "acknowledged": False,
            "error": "durable intent exists without a terminal provider result",
        }

    created_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _append_jsonl(log_path, {
        "run_id": run_id,
        "channel": channel,
        "status": "intent",
        "artifact_sha256": artifact_sha256,
        "created_at": created_at,
    })
    try:
        evidence = send()
    except Exception as exc:
        _append_jsonl(log_path, {
            "run_id": run_id,
            "channel": channel,
            "status": "failed",
            "artifact_sha256": artifact_sha256,
            "error": type(exc).__name__,
            "created_at": created_at,
        })
        return {
            "channel": channel,
            "status": "failed",
            "artifact_sha256": artifact_sha256,
            "acknowledged": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    record = {
        "run_id": run_id,
        "channel": channel,
        "status": "sent",
        "artifact_sha256": artifact_sha256,
        "provider": evidence.get("provider", "unavailable"),
        "provider_message_id": evidence.get("provider_message_id", "unavailable"),
        "acknowledged": evidence.get("acknowledged") is True,
        "created_at": created_at,
    }
    _append_jsonl(log_path, record)
    return {"channel": channel, **{key: value for key, value in record.items() if key != "run_id"}}


def _actual_cost(usage: dict[str, Any]) -> Any:
    for key in ("cost_usd", "actual_cost_usd", "cost"):
        if usage.get(key) is not None:
            return usage[key]
    return "unavailable from provider response"


def _write_delivery_receipt(
    *,
    root: Path,
    run_id: str,
    artifact_sha256: str,
    response: dict[str, Any],
    deliveries: list[dict[str, Any]],
    generated: dt.datetime,
) -> Path:
    usage = response.get("token_usage") if isinstance(response.get("token_usage"), dict) else {}
    passed = all(row.get("status") in {"sent", "already_sent"} and row.get("acknowledged") for row in deliveries)
    path = root / RECEIPT_DIR_REL / f"david-morning-brief-{run_id}.md"
    content = "\n".join((
        "# David morning brief delivery receipt",
        f"> Expires: never; point-in-time delivery evidence. · Created: {generated.replace(microsecond=0).isoformat().replace('+00:00', 'Z')}.",
        "",
        "PASS" if passed else "NEEDS ATTENTION",
        "",
        f"- Run ID: `{run_id}` (America/Vancouver service date)",
        f"- Local artifact: `{OUTPUT_REL.as_posix()}`",
        f"- Artifact SHA-256: `{artifact_sha256}`",
        f"- Email target: `{EMAIL_RECIPIENT}`",
        f"- Email result: `{next((row.get('status') for row in deliveries if row.get('channel') == 'email'), 'not_attempted')}`",
        f"- Email provider message ID: `{next((row.get('provider_message_id') for row in deliveries if row.get('channel') == 'email'), 'unavailable')}`",
        "- Telegram target: existing primary operator allowlist entry (identifier not exposed)",
        f"- Telegram result: `{next((row.get('status') for row in deliveries if row.get('channel') == 'telegram'), 'not_attempted')}`",
        f"- Telegram provider message ID: `{next((row.get('provider_message_id') for row in deliveries if row.get('channel') == 'telegram'), 'unavailable')}`",
        "- External-action audit: exactly the authorized AgentMail recipient and existing Telegram operator path were attempted; no other sender is present in this service path.",
        f"- David provider/model: `{usage.get('provider', 'unavailable')}` / `{usage.get('model', 'unavailable')}`",
        f"- Actual cost: `{_actual_cost(usage)}`",
        "",
        "## token_usage",
        "```json",
        json.dumps(usage, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## delivery_evidence",
        "```json",
        json.dumps(deliveries, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
    ))
    _atomic_write(path, content)
    return path


def _completed_delivery_for_day(root: Path, run_id: str) -> dict[str, Any] | None:
    target = root / OUTPUT_REL
    if not target.is_file():
        return None
    artifact = target.read_text(encoding="utf-8")
    artifact_sha256 = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
    deliveries = []
    for channel in ("email", "telegram"):
        sent = next((
            row for row in reversed(_delivery_records(root / DELIVERY_LOG_REL, run_id, channel))
            if row.get("status") == "sent"
        ), None)
        if sent is None:
            return None
        if sent.get("artifact_sha256") != artifact_sha256:
            raise MorningBriefRunError(f"{channel} delivery hash does not match the retained local artifact")
        deliveries.append({
            "channel": channel,
            "status": "already_sent",
            "artifact_sha256": artifact_sha256,
            "provider": sent.get("provider", "unavailable"),
            "provider_message_id": sent.get("provider_message_id", "unavailable"),
            "acknowledged": True,
        })
    receipt = root / RECEIPT_DIR_REL / f"david-morning-brief-{run_id}.md"
    return {
        "success": True,
        "idempotent_skip": True,
        "detector_token_usage": dict(DETECTOR_USAGE),
        "context": None,
        "token_usage": None,
        "invocation_id": None,
        "queue_effect": {"unchanged": True, "items_created": 0},
        "delivery": {
            "type": "local_generated_artifact",
            "path": OUTPUT_REL.as_posix(),
            "written": False,
            "external": True,
            "artifact_sha256": artifact_sha256,
            "authorized_external_deliveries": deliveries,
            "receipt_path": receipt.relative_to(root).as_posix() if receipt.is_file() else None,
        },
        "brief": None,
    }


def run(
    *,
    root: Path = ROOT,
    endpoint: str = DEFAULT_ENDPOINT,
    dry_run: bool = False,
    deliver: bool = False,
    refresh_fn: Callable[..., Any] = refresh,
    post_json: Callable[[str, dict[str, Any]], dict[str, Any]] = _post_json,
    email_sender: Callable[[Path, str, str, str], dict[str, Any]] = _agentmail_send,
    telegram_sender: Callable[[Path, str], dict[str, Any]] = _telegram_send,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    run_clock = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    local_day = run_clock.astimezone(LOCAL_TIMEZONE).date().isoformat()
    if deliver:
        if dry_run:
            raise MorningBriefRunError("external delivery cannot be combined with dry-run")
        completed = _completed_delivery_for_day(root, local_day)
        if completed is not None:
            return completed
    outcome = refresh_fn(root=root, client_scope="global")
    if outcome.exit_code:
        raise MorningBriefRunError(f"fresh deterministic detector failed: {outcome.reason}")
    try:
        detector = json.loads((root / FINDINGS_REL).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MorningBriefRunError(f"fresh detector artifact unavailable: {type(exc).__name__}") from exc
    if detector.get("token_usage") != DETECTOR_USAGE:
        raise MorningBriefRunError("detector did not prove exact zero-model-token usage")

    response = post_json(endpoint, {"text": PROMPT})
    _validate_david_response(response)
    generated = run_clock
    artifact = _render_artifact(response, detector, generated)
    target = root / OUTPUT_REL
    if not dry_run:
        _atomic_write(target, artifact)
    artifact_sha256 = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
    external_deliveries: list[dict[str, Any]] = []
    receipt_path: Path | None = None
    if deliver:
        subject = f"David Morning Brief — {local_day}"
        log_path = root / DELIVERY_LOG_REL
        external_deliveries = [
            _send_once(
                log_path=log_path,
                run_id=local_day,
                channel="email",
                artifact_sha256=artifact_sha256,
                send=lambda: email_sender(root, EMAIL_RECIPIENT, subject, artifact),
                now=generated,
            ),
            _send_once(
                log_path=log_path,
                run_id=local_day,
                channel="telegram",
                artifact_sha256=artifact_sha256,
                send=lambda: telegram_sender(root, artifact),
                now=generated,
            ),
        ]
        receipt_path = _write_delivery_receipt(
            root=root,
            run_id=local_day,
            artifact_sha256=artifact_sha256,
            response=response,
            deliveries=external_deliveries,
            generated=generated,
        )
        failures = [row for row in external_deliveries if row.get("status") not in {"sent", "already_sent"}]
        if failures:
            channels = ", ".join(str(row.get("channel")) for row in failures)
            raise MorningBriefRunError(f"authorized delivery failed or is ambiguous: {channels}")
    return {
        "success": True,
        "dry_run": dry_run,
        "detector_token_usage": dict(DETECTOR_USAGE),
        "context": response.get("context"),
        "token_usage": response.get("token_usage"),
        "invocation_id": response.get("invocation_id"),
        "queue_effect": response.get("queue_effect"),
        "delivery": {
            "type": "local_generated_artifact",
            "path": OUTPUT_REL.as_posix(),
            "written": not dry_run,
            "external": bool(external_deliveries),
            "artifact_sha256": artifact_sha256,
            "authorized_external_deliveries": external_deliveries,
            "receipt_path": receipt_path.relative_to(root).as_posix() if receipt_path else None,
        },
        "brief": response.get("response"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--deliver", action="store_true", help="send the exact artifact by authorized AgentMail and operator Telegram paths")
    parser.add_argument("--format", choices=("json", "markdown", "quiet"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(root=args.root, endpoint=args.endpoint, dry_run=args.dry_run, deliver=args.deliver)
    except MorningBriefRunError as exc:
        print(f"morning brief failed: {exc}", file=os.sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.format == "markdown":
        print(result["brief"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
