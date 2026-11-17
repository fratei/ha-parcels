"""Call the AI task (stub; owned by the AI agent)."""

from __future__ import annotations

from datetime import tzinfo

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from ..parsers.base import MailMessage
from .validate import Validation


class AIError(HomeAssistantError):
    """The AI couldn't read an e-mail."""


class AIUnavailable(AIError):
    """The AI task or the Ollama app isn't available."""


class AITimeout(AIError):
    """The AI took too long."""


async def async_extract(
    hass: HomeAssistant, entity_id: str, message: MailMessage, tz: tzinfo
) -> Validation:
    """Ask the AI task to read one e-mail and check its answer."""
    raise AIUnavailable("not implemented")
