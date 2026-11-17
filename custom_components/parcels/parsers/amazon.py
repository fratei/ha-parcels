"""Parser for Amazon e-mails (stub; owned by the merchants agent)."""

from __future__ import annotations

from datetime import tzinfo

from .base import MailMessage, ParseResult, SenderVerdict


def parse_amazon(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult | None:
    """Parse an Amazon order or shipping e-mail."""
    return None
