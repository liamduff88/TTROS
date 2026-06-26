"""Token-free command whitelist and role authorization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


class CommandRoutingError(ValueError):
    """Raised when a command cannot be safely routed."""


@dataclass(frozen=True)
class Route:
    command: str
    handler: str
    arguments: str


class CommandRouter:
    def __init__(self, config: Mapping[str, Any]):
        self._commands = dict(config.get("commands", {}))

    @classmethod
    def from_file(cls, path: str | Path) -> "CommandRouter":
        with Path(path).open(encoding="utf-8") as handle:
            return cls(json.load(handle))

    def is_whitelisted(self, command: str) -> bool:
        return command.lower().lstrip("/") in self._commands

    def route(self, text: str, role: str, context: str = "dm") -> Route:
        value = text.strip()
        if not value.startswith("/"):
            raise CommandRoutingError("Only whitelisted slash commands are accepted")
        head, _, arguments = value.partition(" ")
        command = head[1:].split("@", 1)[0].lower()
        spec = self._commands.get(command)
        if not spec:
            raise CommandRoutingError("Command is not whitelisted")
        if spec.get("enabled") is False:
            raise CommandRoutingError("Command is disabled")
        if spec.get("token_free") is not True:
            raise CommandRoutingError("Basic commands must be token-free")
        if role not in spec.get("roles", []):
            raise CommandRoutingError("Role is not authorized for this command")
        allowed_contexts = spec.get("context")
        if isinstance(allowed_contexts, str):
            allowed_contexts = [allowed_contexts]
        if context not in (allowed_contexts or []):
            raise CommandRoutingError("Command is not authorized in this chat context")
        return Route(command=command, handler=str(spec["handler"]), arguments=arguments.strip())

    def dispatch(
        self,
        text: str,
        role: str,
        handlers: Mapping[str, Callable[[str], Any]],
        context: str = "dm",
    ) -> Any:
        route = self.route(text, role, context)
        handler = handlers.get(route.handler)
        if handler is None:
            raise CommandRoutingError("Whitelisted handler is unavailable")
        return handler(route.arguments)
