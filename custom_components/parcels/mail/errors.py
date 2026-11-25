"""Errors raised by the mailbox API clients."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import math


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


class MailNoMailbox(MailError):
    """The account has no mailbox the API can read."""


class MailApiDisabled(MailError):
    """The mail API is not enabled for the app registration (Gmail API off)."""


class MailCursorExpired(MailError):
    """The sync cursor expired; the clients restart with a lookback sync."""


# Errors about the whole mailbox; any other error is about one e-mail.
MAILBOX_ERRORS: tuple[type[MailError], ...] = (
    MailAuthError,
    MailRateLimited,
    MailCursorExpired,
    MailNoMailbox,
    MailApiDisabled,
)


def parse_retry_after(
    value: str | None, *, now: datetime | None = None
) -> float | None:
    """Return the delay of a ``Retry-After`` header in seconds.

    The header holds either a number of seconds or an HTTP date.
    """
    if not value or not (value := value.strip()):
        return None
    try:
        seconds = float(value)
    except ValueError:
        pass
    else:
        return max(seconds, 0.0) if math.isfinite(seconds) else None
    try:
        when = parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max((when - (now or datetime.now(UTC))).total_seconds(), 0.0)
