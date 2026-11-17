"""Shared data types for e-mail parsing.

These types are the contract between mail fetchers, parsers, the local AI
and the parcel engine. E-mail bodies only ever live in memory, inside
``MailMessage``; nothing in this module is persisted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
import hashlib

from ..const import MailKind


@dataclass(frozen=True, slots=True)
class Link:
    """A link found in an e-mail. Links are never fetched."""

    url: str
    text: str = ""


@dataclass(frozen=True, slots=True)
class AuthResult:
    """The topmost Authentication-Results header added by the mail provider."""

    authserv_id: str | None = None
    dkim_pass_domains: tuple[str, ...] = ()
    dmarc_pass: bool = False
    dmarc_domain: str | None = None
    spf_pass: bool = False
    spf_domain: str | None = None


@dataclass(slots=True)
class MailMessage:
    """A normalised e-mail, held in memory only."""

    message_id: str
    provider_id: str
    provider: str
    mailbox: str
    sender: str
    sender_name: str
    subject: str
    date: datetime
    text: str
    links: tuple[Link, ...] = ()
    reply_to: str | None = None
    auth: AuthResult | None = None
    received: datetime | None = None
    headers: dict[str, str] = field(default_factory=dict)
    language: str | None = None

    @property
    def sender_domain(self) -> str:
        """Return the lowercased domain of the From address."""
        return self.sender.rpartition("@")[2].lower()

    @property
    def hash(self) -> str:
        """Return a stable hash that identifies this e-mail in every mailbox."""
        return message_hash(self.message_id, self.sender, self.subject, self.date)


def message_hash(
    message_id: str | None, sender: str, subject: str, sent: datetime | None
) -> str:
    """Hash a Message-ID, or the sender, subject and date when it's missing."""
    if message_id and (normalised := message_id.strip().strip("<>").lower()):
        source = f"mid:{normalised}"
    else:
        stamp = sent.isoformat() if sent else ""
        source = f"hdr:{sender.lower()}|{subject.strip()}|{stamp}"
    return hashlib.sha256(source.encode()).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class SenderVerdict:
    """Whether the sender of an e-mail is authenticated and known."""

    domain: str
    authenticated: bool
    known: bool
    shopify: bool = False
    method: str = "none"
    reason: str = ""

    @property
    def verified(self) -> bool:
        """Return True when the sender is authenticated and on the allow list."""
        return self.authenticated and self.known


@dataclass(slots=True)
class Eta:
    """An expected delivery date, range or time window, in local time."""

    start: date
    end: date
    window_start: time | None = None
    window_end: time | None = None


@dataclass(slots=True)
class ParsedShipment:
    """One parcel found in an e-mail."""

    carrier: str | None = None
    tracking_number: str | None = None
    kind: MailKind | None = None
    eta: Eta | None = None
    event_time: datetime | None = None
    pickup_point: str | None = None
    pickup_code: str | None = None
    amazon_shipment_id: str | None = None
    order_numbers: tuple[str, ...] = ()
    items: tuple[str, ...] = ()
    tracking_url: str | None = None


@dataclass(slots=True)
class ParseResult:
    """What a parser or the local AI read from one e-mail."""

    parser: str
    kind: MailKind
    merchant: str | None = None
    order_numbers: tuple[str, ...] = ()
    shipments: list[ParsedShipment] = field(default_factory=list)
    items: tuple[str, ...] = ()
    confidence: float = 0.0
    language: str | None = None
    source: str = "parser"
    notes: tuple[str, ...] = ()

    @property
    def is_parcel(self) -> bool:
        """Return True when the e-mail is about a parcel."""
        return self.kind not in (MailKind.NOT_PARCEL, MailKind.UNKNOWN)
