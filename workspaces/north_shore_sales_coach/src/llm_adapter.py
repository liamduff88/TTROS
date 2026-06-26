"""Explicit, disabled-by-default boundary for a future LLM integration."""

from __future__ import annotations

from typing import Any, Mapping


class LlmAdapter:
    def __init__(self, config: Mapping[str, Any]):
        self.config = dict(config)

    @property
    def enabled(self) -> bool:
        return self.config.get("enabled") is True

    def complete(self, prompt: str, *, purpose: str = "default") -> str:
        if not self.enabled:
            raise RuntimeError("LLM adapter is disabled")
        raise NotImplementedError("Phase 1 makes no LLM calls")

