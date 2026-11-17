"""Language helpers for pt, es, en, de, fr, it and nl (stub)."""

from __future__ import annotations

LANGUAGES: tuple[str, ...] = ("pt", "es", "en", "de", "fr", "it", "nl")


def fold(text: str) -> str:
    """Lowercase and strip accents."""
    raise NotImplementedError


def detect_language(text: str) -> str | None:
    """Guess the language of a text."""
    raise NotImplementedError
