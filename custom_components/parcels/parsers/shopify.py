"""Parsers for Shopify stores and the Shop app (stub; owned by the merchants agent)."""

from __future__ import annotations

from datetime import tzinfo

from .base import MailMessage, ParseResult, SenderVerdict


def parse_shopify(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult | None:
    """Parse a notification sent by a Shopify store."""
    return None


def parse_shop(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult | None:
    """Parse a delivery update sent by the Shop app."""
    return None
