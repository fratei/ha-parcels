"""Mailbox API clients (stub; owned by the OAuth and mail agent)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from ..parsers.base import MailMessage


@dataclass(frozen=True, slots=True)
class MessageMeta:
    """Headers of one e-mail, read before deciding to download its body."""

    provider_id: str
    message_id: str | None
    sender: str
    sender_name: str
    subject: str
    received: datetime
    sent: datetime | None = None
    folder: str | None = None


@dataclass(slots=True)
class SyncResult:
    """New e-mails since the last sync and the cursor for the next one."""

    messages: list[MessageMeta] = field(default_factory=list)
    cursor: dict[str, Any] = field(default_factory=dict)
    complete: bool = True


class MailClient(Protocol):
    """What the polling coordinator needs from a mailbox API."""

    provider: str

    async def async_get_address(self) -> str:
        """Return the mailbox address."""

    async def async_sync(
        self,
        cursor: dict[str, Any] | None,
        *,
        lookback: timedelta,
        folders: Sequence[str] = (),
    ) -> SyncResult:
        """Return e-mails added since ``cursor``, or within ``lookback``."""

    async def async_fetch(self, provider_id: str) -> MailMessage:
        """Download one full e-mail and normalise it."""
