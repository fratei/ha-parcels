"""Fixed instructions, input and output structure for the AI (stub)."""

from __future__ import annotations

from datetime import tzinfo

from ..parsers.base import MailMessage

INSTRUCTIONS = ""


def build_input(message: MailMessage, tz: tzinfo) -> str:
    """Build the text the model reads for one e-mail."""
    raise NotImplementedError
