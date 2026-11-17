"""Grounding checks for AI output (stub; owned by the AI agent)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import tzinfo
from typing import Any

from ..parsers.base import MailMessage, ParseResult


@dataclass(frozen=True, slots=True)
class Validation:
    """A checked AI answer: a result, or the reasons it was rejected."""

    result: ParseResult | None
    errors: tuple[str, ...] = ()


def validate_output(
    data: Mapping[str, Any], message: MailMessage, tz: tzinfo
) -> Validation:
    """Check an AI answer against the e-mail it came from."""
    raise NotImplementedError
