"""Deterministic natural-language intent routing for the direct sub-bot."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .command_router import CommandRouter, Route


@dataclass(frozen=True)
class NaturalLanguageRoute:
    intent: str
    handler: str
    token_free_route: bool
    llm_allowed_for_parse_only: bool
    source: str = "deterministic"


LlmIntentFallback = Callable[[str, str, str], str | None]


class NaturalLanguageRouter:
    """Classify only approved local intents; never execute tools or send messages."""

    _out_of_scope = re.compile(
        r"(?:"
        r"(?:^|\s)/work\b|"
        r"\b(?:hermes|agentic\s*os|codex|claude|composio)\b|"
        r"\b(?:web\s*search|search(?:ing)?\s+(?:the\s+)?(?:web|internet)|ask\s+the\s+internet|"
        r"browse\s+the\s+(?:web|internet)|internet\s+research)\b|"
        r"\b(?:run|launch|start|delegate\s+to)\s+(?:an?\s+)?agent\b|"
        r"\b(?:execute|invoke|run)\s+(?:an?\s+)?(?:tool|connector)\b|"
        r"\b(?:edit|write|delete|create|modify)\s+(?:a\s+|the\s+|my\s+)?files?\b|"
        r"\b(?:control|restart|shutdown|reboot|open)\s+(?:the\s+)?(?:os|system|dashboard)\b"
        r")",
        re.IGNORECASE,
    )

    _sales_activity = re.compile(
        r"\b(walk[ -]?in|test drove|test drive|worksheet|offer|spoke to|people|customer|"
        r"appointment|follow[ -]?up|cr-?v|civic|accord|pilot|odyssey|ridgeline|vehicle|numbers)\b",
        re.IGNORECASE,
    )
    _manager_patterns = (
        ("missing", "missing", re.compile(r"\b(who (hasn'?t|has not) updated|not updated|missing updates?)\b", re.I)),
        ("followups", "followups", re.compile(r"\bfollow[ -]?ups?\b.*\b(due|today|tomorrow|upcoming)?\b", re.I)),
        ("coaching", "coaching", re.compile(r"\bcoaching\s+(flags?|issues?|opportunities)\b", re.I)),
        ("team", "team", re.compile(r"\b(team\s+scorecard|scorecard)\b", re.I)),
        ("report", "report", re.compile(r"\b(generate|create|give me|show me)?\s*(a\s+)?report\b", re.I)),
        ("dashboard", "dashboard", re.compile(r"\b(?:north\s+shore\s+)?dashboard(?:\s+link)?\b", re.I)),
        (
            "today",
            "today",
            re.compile(r"\b(how did (the )?team do today|today'?s summary|summary (for|of) today)\b", re.I),
        ),
    )
    def __init__(
        self,
        *,
        llm_enabled: bool | None = None,
        llm_fallback: LlmIntentFallback | None = None,
    ) -> None:
        # Compatibility metadata for a future downstream parse step. Intent
        # classification itself never invokes an LLM.
        self.llm_enabled = llm_enabled is True
        self._llm_fallback = llm_fallback

    def route(self, text: str, role: str, context: str) -> NaturalLanguageRoute:
        value = text.strip()
        if value.startswith("/"):
            raise ValueError("Slash commands must route through CommandRouter")

        # Reject capability-escalation language before matching words such as
        # "report" or "dashboard". This route is always local and token-free.
        if self._out_of_scope.search(value):
            return NaturalLanguageRoute(
                intent="scope_rejected",
                handler="help",
                token_free_route=True,
                llm_allowed_for_parse_only=False,
                source="local_scope_boundary",
            )

        route = self._deterministic_route(value, role, context)
        if route is not None:
            return route

        return NaturalLanguageRoute(
            intent="unknown_help",
            handler="help",
            token_free_route=True,
            llm_allowed_for_parse_only=False,
        )

    def _deterministic_route(self, text: str, role: str, context: str) -> NaturalLanguageRoute | None:
        if role in {"salesperson", "admin"} and context == "dm" and self._sales_activity.search(text):
            return NaturalLanguageRoute(
                intent="log_sales_activity",
                handler="log",
                token_free_route=True,
                llm_allowed_for_parse_only=True,
            )
        if role in {"manager", "admin"} and context == "group":
            for intent, handler, pattern in self._manager_patterns:
                if pattern.search(text):
                    return NaturalLanguageRoute(
                        intent=intent,
                        handler=handler,
                        token_free_route=True,
                        llm_allowed_for_parse_only=False,
                    )
        return None

class MessageRouter:
    """Select slash-command or natural-language routing without other gateways."""

    def __init__(self, command_router: CommandRouter, natural_language_router: NaturalLanguageRouter):
        self.command_router = command_router
        self.natural_language_router = natural_language_router

    def route(self, text: str, role: str, context: str) -> Route | NaturalLanguageRoute:
        if text.strip().startswith("/"):
            return self.command_router.route(text, role, context)
        return self.natural_language_router.route(text, role, context)
