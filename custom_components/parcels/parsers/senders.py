"""Known sender domains (stub; owned by the mail-core agent)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SenderInfo:
    """A merchant, carrier or platform that sends shipping e-mails."""

    domain: str
    name: str
    kind: str
    carrier: str | None = None
    parser: str | None = None


KNOWN_SENDERS: dict[str, SenderInfo] = {}


def organizational_domain(domain: str) -> str:
    """Return the registrable domain, e.g. ``amazon.co.uk``."""
    raise NotImplementedError


def lookup(domain: str) -> SenderInfo | None:
    """Return the known sender for a domain or any of its subdomains."""
    raise NotImplementedError
