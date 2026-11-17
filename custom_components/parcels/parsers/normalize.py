"""Turn raw e-mails into ``MailMessage`` objects (stub; owned by the mail-core agent)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import Link, MailMessage


def html_to_text(html: str) -> tuple[str, tuple[Link, ...]]:
    """Convert HTML to plain text and the links it contains. Never fetches."""
    raise NotImplementedError


def message_from_bytes(
    raw: bytes, *, mailbox: str, provider_id: str, provider: str
) -> MailMessage:
    """Parse an RFC 5322 message (Gmail ``format=raw``)."""
    raise NotImplementedError


def message_from_graph(item: Mapping[str, Any], *, mailbox: str) -> MailMessage:
    """Build a message from a Microsoft Graph message resource."""
    raise NotImplementedError
