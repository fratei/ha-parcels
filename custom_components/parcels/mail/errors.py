"""Errors raised by the mailbox API clients."""

from __future__ import annotations


class MailError(Exception):
    """A mailbox API request failed."""


class MailAuthError(MailError):
    """The token was rejected; the user must sign in again."""


class MailRateLimited(MailError):
    """The API asked to slow down (HTTP 429)."""

    def __init__(self, retry_after: float | None = None) -> None:
        """Store the delay the server asked for, in seconds."""
        super().__init__(f"rate limited, retry after {retry_after}")
        self.retry_after = retry_after


class MailServerError(MailError):
    """The API had a temporary problem (HTTP 5xx or a network error)."""


class MailNotFound(MailError):
    """The e-mail no longer exists."""
