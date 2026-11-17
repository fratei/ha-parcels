"""Parsers for carrier e-mails (stub; owned by the carriers agent)."""

from __future__ import annotations

from datetime import tzinfo

from ..base import MailMessage, ParseResult, SenderVerdict

CARRIER_PARSERS: frozenset[str] = frozenset()


def parse_carrier(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo, carrier: str
) -> ParseResult | None:
    """Parse an e-mail from a carrier, or return None when it isn't readable."""
    return None
