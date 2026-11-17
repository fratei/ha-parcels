"""Fallback parser for senders without a dedicated parser (stub)."""

from __future__ import annotations

from datetime import tzinfo

from .base import MailMessage, ParseResult, SenderVerdict


def parse_generic(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult | None:
    """Read tracking numbers, status and dates from any e-mail."""
    raise NotImplementedError
