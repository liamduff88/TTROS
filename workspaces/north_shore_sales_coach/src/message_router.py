"""Package-local Telegram update handling and safe response selection."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

from .command_router import CommandRouter, CommandRoutingError
from .local_store import LocalJsonlStore, LocalStateStore, ROLE_RANK
from .natural_language_router import NaturalLanguageRouter
from .report_generator import (
    archive_record,
    format_coaching,
    format_daily,
    format_followups,
    format_missing,
    format_team,
    generate_daily_report,
)
from .role_store import RoleStore
from .sales_log_parser import apply_missing_field_answer, parse_sales_log
from .sheets_manual_sync import SheetsManualSyncError, SheetsManualSyncResult, run_manual_sheets_sync

UNREGISTERED_START = "North Shore Sales Coach connected. You are not registered yet."
SALESPERSON_START = "North Shore Sales Coach connected. Send a sales update in plain English, or use /log."
LOG_SAVED = "Sales update saved locally."
LOG_COMPLETED = "Sales update completed locally."
MEDIA_PLACEHOLDER = "Text messages only for now. Please send your update in plain English."
SAFE_HELP = "I can help with North Shore sales updates and approved team summaries. Use /help for available shortcuts."
SAFE_SCOPE_REJECTION = "That request is outside the North Shore Sales Coach scope. Use /help for approved actions."
DASHBOARD_UNAVAILABLE = "The North Shore dashboard link is not configured."
ROSTER_HELP = (
    "Roster shortcuts:\n"
    "/list_salespeople\n"
    "/register_salesperson <display name>\n"
    "/deactivate_salesperson <display name or salesperson_id>\n"
    "/invite salesperson <display name>\n"
    "/invites"
)
EMPTY_ROSTER = "No salesperson roster is configured yet, so missing-person checks are not active."


class MessageRouter:
    """Combine roles, command intents, natural language, and local registration state."""

    def __init__(
        self,
        role_store: RoleStore,
        command_router: CommandRouter,
        natural_language_router: NaturalLanguageRouter,
        state_store: LocalStateStore,
        events_store: LocalJsonlStore,
        sales_store: LocalJsonlStore,
        report_archive_store: LocalJsonlStore | None = None,
        dashboard_url: str | None = None,
        sheets_sync_runner: Callable[[], SheetsManualSyncResult] | None = None,
    ) -> None:
        self.role_store = role_store
        self.command_router = command_router
        self.natural_language_router = natural_language_router
        self.state_store = state_store
        self.events_store = events_store
        self.sales_store = sales_store
        self.report_archive_store = report_archive_store or LocalJsonlStore(
            sales_store.path.parent / "report_archive.jsonl"
        )
        self.dashboard_url = dashboard_url.strip() if isinstance(dashboard_url, str) else ""
        self.sheets_sync_runner = sheets_sync_runner

    def handle_update(self, update: dict[str, Any]) -> str | None:
        message = update.get("message")
        if not isinstance(message, dict):
            return None
        chat = message.get("chat", {})
        sender = message.get("from", {})
        chat_id = chat.get("id")
        user_id = sender.get("id")
        context = "dm" if chat.get("type") == "private" else "group"
        if context == "dm" and user_id is not None:
            self.state_store.update_user_profile(user_id, sender)
        text = message.get("text")
        if not isinstance(text, str):
            return MEDIA_PLACEHOLDER
        role = self._role_for(user_id)

        if text.strip().startswith("/"):
            return self._handle_command(text, role, context, chat_id, user_id)
        if context == "dm" and role in {"salesperson", "admin"} and user_id is not None:
            pending = self.state_store.pending_sales_log(user_id)
            if pending is not None:
                return self._complete_pending_sales_log(text, user_id, pending)
        invite_request = self._parse_natural_invite(text)
        if invite_request is not None:
            target_role, display_name = invite_request
            return self._create_invite_response(role, user_id, target_role, display_name)
        route = self.natural_language_router.route(text, role or "inactive", context)
        if route.intent == "scope_rejected":
            return SAFE_SCOPE_REJECTION
        if route.intent == "log_sales_activity":
            return self._save_sales_log(text, user_id)
        if route.intent == "dashboard":
            return self._dashboard_response()
        if route.intent in {"today", "team", "followups", "missing", "coaching", "report"}:
            return self._report_response(route.intent)
        return SAFE_HELP

    def _handle_command(
        self,
        text: str,
        role: str | None,
        context: str,
        chat_id: Any,
        user_id: Any,
    ) -> str:
        command = text.strip().partition(" ")[0][1:].split("@", 1)[0].lower()
        if command == "start":
            argument = text.strip().partition(" ")[2].strip()
            if argument:
                return self._redeem_invite_response(argument, context, user_id)
        if command == "start" and context == "dm" and role is None:
            # The public bootstrap reply is still bounded by the configured command whitelist.
            if self.command_router.is_whitelisted("start"):
                return UNREGISTERED_START
            return SAFE_HELP
        try:
            route = self.command_router.route(text, role or "inactive", context)
        except CommandRoutingError:
            return SAFE_HELP

        if route.handler == "start":
            return SALESPERSON_START if role == "salesperson" else UNREGISTERED_START
        if route.handler == "help":
            return ROSTER_HELP if role in {"manager", "admin"} else SAFE_HELP
        if route.handler == "create_invite":
            target_role, display_name = self._parse_invite_arguments(route.arguments)
            return self._create_invite_response(role, user_id, target_role, display_name)
        if route.handler == "list_invites":
            return self._list_invites_response(role)
        if route.handler == "revoke_invite":
            return self._revoke_invite_response(role, route.arguments)
        if route.handler == "my_status":
            return self._my_status_response(user_id)
        if route.handler == "log":
            if not route.arguments:
                return "Please include the sales update after /log."
            return self._save_sales_log(route.arguments, user_id)
        if route.handler == "register_salesperson":
            if not route.arguments:
                return "Please include a display name after /register_salesperson."
            try:
                record = self.state_store.register_salesperson(route.arguments)
            except ValueError as exc:
                return str(exc)
            return f"Salesperson registered locally: {record['display_name']} ({record['salesperson_id']})."
        if route.handler == "list_salespeople":
            salespeople = self.state_store.salespeople(active_only=True)
            if not salespeople:
                return EMPTY_ROSTER
            return "Active salespeople:\n" + "\n".join(
                f"- {record['display_name']} ({record['salesperson_id']})" for record in salespeople
            )
        if route.handler == "deactivate_salesperson":
            if not route.arguments:
                return "Please include a display name or salesperson ID after /deactivate_salesperson."
            record = self.state_store.deactivate_salesperson(route.arguments)
            if record is None:
                return "Salesperson not found in the local roster."
            return f"Salesperson deactivated locally: {record['display_name']}."
        if route.handler in {"today", "team", "followups", "missing", "coaching", "report"}:
            return self._report_response(route.handler)
        if route.handler == "dashboard":
            return self._dashboard_response()
        if route.handler == "sync_sheets":
            return self._sync_sheets_response()
        if route.handler == "register_admin_group":
            self._register_group("admin_group", chat_id, user_id)
            return "Admin group registered in local North Shore state."
        if route.handler == "register_broadcast_group":
            self._register_group("broadcast_group", chat_id, user_id)
            return "Broadcast group registered in local North Shore state."
        return "This approved shortcut is not implemented in the Phase 2 demo."

    def _role_for(self, user_id: Any) -> str | None:
        if user_id is None:
            return None
        roles = [
            role
            for role in (self.state_store.role_for(user_id), self.role_store.role_for(user_id))
            if role in ROLE_RANK
        ]
        return max(roles, key=lambda value: ROLE_RANK[value]) if roles else None

    def _display_name_for(self, user_id: Any) -> str | None:
        status = self.state_store.user_status(user_id)
        if status is not None:
            return str(status["display_name"])
        profile_names = self.state_store.user_display_names()
        if str(user_id) in profile_names:
            return profile_names[str(user_id)]
        for identity in self.role_store.salesperson_identities().values():
            if str(identity.get("telegram_user_id")) == str(user_id):
                name = identity.get("display_name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        return None

    def _parse_invite_arguments(self, arguments: str) -> tuple[str | None, str]:
        value = " ".join(arguments.split())
        if not value:
            return None, ""
        parts = value.split(" ", 1)
        first = parts[0].casefold()
        if first in {"manager", "salesperson", "admin"}:
            return first, parts[1].strip() if len(parts) > 1 else ""
        return "salesperson", value

    def _parse_natural_invite(self, text: str) -> tuple[str, str] | None:
        value = " ".join(text.split())
        lower = value.casefold()
        for prefix in ("create invite for ", "create an invite for ", "invite "):
            if lower.startswith(prefix):
                remainder = value[len(prefix) :].strip()
                break
        else:
            return None
        target_role = "salesperson"
        words = remainder.split()
        if words and words[0].casefold() in {"manager", "salesperson", "admin"}:
            target_role = words[0].casefold()
            remainder = " ".join(words[1:]).strip()
        if " as manager" in remainder.casefold():
            index = remainder.casefold().rfind(" as manager")
            target_role, remainder = "manager", remainder[:index].strip()
        elif " as admin" in remainder.casefold():
            index = remainder.casefold().rfind(" as admin")
            target_role, remainder = "admin", remainder[:index].strip()
        elif " as salesperson" in remainder.casefold():
            index = remainder.casefold().rfind(" as salesperson")
            target_role, remainder = "salesperson", remainder[:index].strip()
        return target_role, remainder

    def _create_invite_response(
        self,
        actor_role: str | None,
        actor_user_id: Any,
        target_role: str | None,
        display_name: str,
    ) -> str:
        if actor_role is None:
            return "Only registered admins and managers can create invites."
        if actor_role == "salesperson":
            return "Salespeople cannot create invites."
        if target_role not in {"manager", "salesperson"}:
            return "Managers can invite salespeople. Admin invites are not available here."
        if actor_role == "manager" and target_role != "salesperson":
            return "Managers can invite salespeople only. Ask an admin to create manager invites."
        if not display_name.strip():
            return "Please include the person's name."
        try:
            invite = self.state_store.create_invite(
                role=target_role,
                display_name=display_name,
                created_by=actor_user_id,
            )
        except ValueError as exc:
            return str(exc)
        instruction = f"/start {invite['code']}"
        return (
            f"Invite ready for {invite['display_name']} ({invite['role']}).\n"
            "Send them this in a DM with the bot:\n"
            f"{instruction}\n"
            "This code expires in 14 days and works once."
        )

    def _redeem_invite_response(self, code: str, context: str, user_id: Any) -> str:
        if context != "dm":
            return "For privacy, redeem invite codes in a DM with the bot: /start CODE"
        if user_id is None:
            return "I could not read your Telegram account. Please try again in a DM."
        existing_role = self._role_for(user_id)
        status, record = self.state_store.redeem_invite(code, user_id, existing_role=existing_role)
        if status == "redeemed" and record is not None:
            role = record.get("role")
            name = record.get("display_name")
            if role == "admin":
                return f"Welcome, {name}. You are set up as an admin."
            if role == "manager":
                return f"Welcome, {name}. You are set up as a manager."
            return f"Welcome, {name}. You are set up as a salesperson."
        if status == "expired":
            return "That invite code has expired. Ask your manager for a new one."
        if status == "already_redeemed":
            return "That invite code has already been used."
        if status == "revoked":
            return "That invite code is no longer active."
        return "Invite code not found. Please check the code and try again."

    def _list_invites_response(self, actor_role: str | None) -> str:
        if actor_role not in {"manager", "admin"}:
            return SAFE_HELP
        invites = self.state_store.pending_invites()
        if not invites:
            return "No pending invites."
        lines = ["Pending invites:"]
        for invite in invites:
            expires = str(invite.get("expires_at", ""))[:10] or "soon"
            lines.append(f"- {invite['display_name']} ({invite['role']}): {invite['code']} expires {expires}")
        return "\n".join(lines)

    def _revoke_invite_response(self, actor_role: str | None, arguments: str) -> str:
        if actor_role not in {"manager", "admin"}:
            return SAFE_HELP
        code = arguments.strip()
        if not code:
            return "Please include the invite code to revoke."
        record = self.state_store.revoke_invite(code)
        if record is None:
            return "No pending invite found for that code."
        return f"Invite revoked for {record['display_name']}."

    def _my_status_response(self, user_id: Any) -> str:
        if user_id is None:
            return "You are not registered yet."
        role = self._role_for(user_id)
        if role is None:
            return "You are not registered yet."
        name = self._display_name_for(user_id) or "Registered user"
        return f"You are registered as {name} ({role})."

    def _dashboard_response(self) -> str:
        """Return only a deployment-configured North Shore link; never fetch it."""
        if self.dashboard_url.startswith(("https://", "http://")):
            return f"North Shore dashboard: {self.dashboard_url}"
        return DASHBOARD_UNAVAILABLE

    def _sync_sheets_response(self) -> str:
        """Run only the explicit admin/manager Sheets sync command."""
        runner = self.sheets_sync_runner
        if runner is None:
            root = self.sales_store.path.parent.parent
            runner = lambda: run_manual_sheets_sync(root=root)
        try:
            result = runner()
        except SheetsManualSyncError as exc:
            return f"Sheets sync not completed: {exc}"
        tab_list = ", ".join(result.tabs) if result.tabs else "no tabs"
        return (
            f"Sheets sync completed: {result.row_count} row(s) across {len(result.tabs)} tab(s): {tab_list}.\n"
            "Note: this sync is append-only, so running it again may duplicate rows."
        )

    def _report_response(self, intent: str) -> str:
        profile_names = self.state_store.user_display_names()
        identities = self.role_store.salesperson_identities()
        roster: dict[str, str] = self.state_store.salesperson_roster()
        names = dict(profile_names)
        names.update(roster)
        for record in self.state_store.salespeople(active_only=True):
            telegram_user_id = record.get("telegram_user_id")
            if telegram_user_id is not None:
                names[str(telegram_user_id)] = str(record["display_name"])
        for salesperson_id, identity in identities.items():
            telegram_user_id = str(identity["telegram_user_id"])
            explicit = identity.get("display_name")
            name = (
                explicit.strip()
                if isinstance(explicit, str) and explicit.strip()
                else profile_names.get(telegram_user_id, "Unregistered salesperson")
            )
            roster[salesperson_id] = name
            names[salesperson_id] = name
            if isinstance(explicit, str) and explicit.strip():
                names[telegram_user_id] = explicit.strip()
        report = generate_daily_report(
            self.sales_store.records(),
            date.today(),
            roster,
            names=names,
        )
        if intent == "report":
            self.report_archive_store.append(archive_record(report))
            return format_daily(report) + "\nArchived locally."
        formatters = {
            "today": format_daily,
            "team": format_team,
            "followups": format_followups,
            "missing": format_missing,
            "coaching": format_coaching,
        }
        return formatters[intent](report)

    def _save_sales_log(self, raw_text: str, user_id: Any) -> str:
        salesperson_id = str(user_id)
        for configured_id, identity in self.role_store.salesperson_identities().items():
            if str(identity.get("telegram_user_id")) == str(user_id):
                salesperson_id = configured_id
                break
        for record in self.state_store.salespeople(active_only=True):
            if str(record.get("telegram_user_id")) == str(user_id):
                salesperson_id = str(record["salesperson_id"])
                break
        record = parse_sales_log(
            raw_text,
            str(user_id),
            salesperson_id=salesperson_id,
            source="telegram_dm",
        )
        self.sales_store.append(record)
        if not record["missing_fields"]:
            return LOG_SAVED
        questions = {
            "interaction_type": "Was this a walk-in, call, appointment, or another interaction?",
            "vehicle_interest": "Which vehicle were they interested in?",
            "outcome": "What was the outcome?",
            "next_step": "What is the next step?",
        }
        field = record["missing_fields"][0]
        self.state_store.set_pending_sales_log(user_id, record["log_id"], field)
        return f"{LOG_SAVED}\nOne thing missing: {questions[field]}"

    def _complete_pending_sales_log(self, answer: str, user_id: Any, pending: dict[str, str]) -> str:
        matching = next(
            (
                record
                for record in self.sales_store.records()
                if str(record.get("log_id")) == pending["log_id"]
                and str(record.get("telegram_user_id")) == str(user_id)
            ),
            None,
        )
        if matching is None:
            self.state_store.clear_pending_sales_log(user_id)
            return SAFE_HELP
        updated = apply_missing_field_answer(matching, pending["field"], answer)
        saved = self.sales_store.update_first(
            lambda record: str(record.get("log_id")) == pending["log_id"]
            and str(record.get("telegram_user_id")) == str(user_id),
            updated,
        )
        if not saved:
            self.state_store.clear_pending_sales_log(user_id)
            return SAFE_HELP
        self.state_store.clear_pending_sales_log(user_id)
        if not updated["missing_fields"]:
            return LOG_COMPLETED
        questions = {
            "interaction_type": "Was this a walk-in, call, appointment, or another interaction?",
            "vehicle_interest": "Which vehicle were they interested in?",
            "outcome": "What was the outcome?",
            "next_step": "What is the next step?",
        }
        field = updated["missing_fields"][0]
        self.state_store.set_pending_sales_log(user_id, updated["log_id"], field)
        return f"Answer saved locally.\nOne thing missing: {questions[field]}"

    def _register_group(self, group_type: str, chat_id: Any, user_id: Any) -> None:
        if chat_id is None:
            raise ValueError("Telegram update is missing a chat ID")
        self.state_store.set_group(group_type, chat_id)
        self.events_store.append(
            {
                "event": "group_registered",
                "group_type": group_type,
                "chat_id": str(chat_id),
                "registered_by": str(user_id),
                "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
