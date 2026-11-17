"""E-mail parsers (stub dispatcher; owned by the merchants agent)."""

from __future__ import annotations

from datetime import tzinfo

from ..const import MailKind
from .base import MailMessage, ParseResult, SenderVerdict


def parse_message(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult:
    """Parse an e-mail with the best matching parser. Never raises."""
    return ParseResult(parser="none", kind=MailKind.UNKNOWN, confidence=0.0)
