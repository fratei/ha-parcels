"""Tests for the mail error helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.parcels.mail.errors import parse_retry_after

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("120", 120.0),
        (" 1.5 ", 1.5),
        ("-5", 0.0),
        ("Tue, 17 Nov 2026 12:00:30 GMT", 30.0),
        ("Tue, 17 Nov 2026 11:59:00 GMT", 0.0),
        ("nan", None),
        ("inf", None),
        ("soon", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_retry_after(value: str | None, expected: float | None) -> None:
    """Retry-After holds seconds or an HTTP date; anything else is ignored."""
    assert parse_retry_after(value, now=NOW) == expected
