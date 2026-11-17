"""Localised delivery date parsing (stub; owned by the mail-core agent)."""

from __future__ import annotations

from datetime import datetime, time, tzinfo

from .base import Eta


def parse_eta(
    text: str, reference: datetime, tz: tzinfo, lang: str | None = None
) -> Eta | None:
    """Parse a snippet that describes a delivery date."""
    raise NotImplementedError


def find_eta(
    text: str, reference: datetime, tz: tzinfo, lang: str | None = None
) -> Eta | None:
    """Find a delivery date anchored on delivery keywords in a whole e-mail."""
    raise NotImplementedError


def parse_time_window(text: str) -> tuple[time | None, time | None] | None:
    """Find a delivery time window such as ``13:00-14:00``."""
    raise NotImplementedError
