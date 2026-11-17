"""Cheap check on headers before an e-mail body is downloaded (stub)."""

from __future__ import annotations


def is_candidate(sender: str, subject: str, preview: str = "") -> bool:
    """Return True when an e-mail is likely about a parcel."""
    raise NotImplementedError
