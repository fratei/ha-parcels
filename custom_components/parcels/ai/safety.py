"""Local-only checks for the AI task (stub; owned by the AI agent)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.core import HomeAssistant


@dataclass(frozen=True, slots=True)
class AICheck:
    """Whether an AI task entity may be used for e-mail text."""

    ok: bool
    reason: str
    model: str | None = None
    host: str | None = None


async def async_check_ai_task(hass: HomeAssistant, entity_id: str) -> AICheck:
    """Check that an AI task runs on a local Ollama model on the HA host."""
    return AICheck(ok=False, reason="not_implemented")
