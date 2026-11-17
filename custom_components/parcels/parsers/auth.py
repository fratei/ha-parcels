"""Sender authentication (stub; owned by the mail-core agent)."""

from __future__ import annotations

from collections.abc import Iterable

from .base import AuthResult, MailMessage, SenderVerdict


def parse_authentication_results(value: str) -> AuthResult:
    """Parse one Authentication-Results header value."""
    raise NotImplementedError


def verify_sender(message: MailMessage, trusted: Iterable[str] = ()) -> SenderVerdict:
    """Decide whether the sender is authenticated and known."""
    raise NotImplementedError
