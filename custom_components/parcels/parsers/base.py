"""Shared data types for e-mail parsing.

These types are the contract between mail fetchers, parsers, the local AI
and the parcel engine. E-mail bodies only ever live in memory, inside
``MailMessage``; nothing in this module is persisted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
import hashlib
from typing import Any

from ..const import LeftAt, MailKind


@dataclass(frozen=True, slots=True)
class Link:
    """A link found in an e-mail. Links are never fetched."""

    url: str
    text: str = ""


@dataclass(frozen=True, slots=True)
class AuthResult:
    """One Authentication-Results header, parsed."""

    authserv_id: str | None = None
    dkim_pass_domains: tuple[str, ...] = ()
    dmarc_pass: bool = False
    dmarc_domain: str | None = None
    spf_pass: bool = False
    spf_domain: str | None = None
    # Result words ("pass", "fail", ...); "" when the method isn't there.
    dkim: str = ""
    dmarc: str = ""
    spf: str = ""


@dataclass(frozen=True, slots=True)
class AuthCheck:
    """What the sender checks saw, without addresses: safe to show and log."""

    headers: int = 0
    servers: tuple[str, ...] = ()
    used: int | None = None
    dkim: str = ""
    dmarc: str = ""
    spf: str = ""
    originals: int = 0

    def as_dict(self) -> dict[str, Any]:
        """Serialise the details."""
        return {
            "headers": self.headers,
            "servers": list(self.servers),
            "used": self.used,
            "dkim": self.dkim,
            "dmarc": self.dmarc,
            "spf": self.spf,
            "originals": self.originals,
        }


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
    # Every Authentication-Results value, top-down, and how many headers
    # were renamed Authentication-Results-Original by the provider.
    auth_headers: tuple[str, ...] = ()
    auth_originals: int = 0

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
    check: AuthCheck | None = None

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
    # Amazon's shipment ID, with the package's index when not the first:
    # see shipment_key.
    amazon_shipment_id: str | None = None
    # A shipment number other than the tracking number, see Origin.reference.
    reference: str | None = None
    order_numbers: tuple[str, ...] = ()
    items: tuple[str, ...] = ()
    tracking_url: str | None = None
    # The marketplace seller, see Origin.seller.
    seller: str | None = None
    # The e-mail can only add to a parcel already known, never make one.
    attach_only: bool = False
    # The e-mail says what happened but not when: by the time it was sent.
    undated: bool = False
    # Read by parsers.details: the last day to collect the parcel at its
    # pickup point, the day of the next delivery attempt, where it was left.
    collect_by: date | None = None
    next_attempt: date | None = None
    left_at: LeftAt | None = None


def shipment_key(shipment_id: str, package_index: int | None = None) -> str:
    """Return the key of one package of an Amazon shipment, e.g. "Ab12Cd34E#1".

    A shipment sent in several boxes gives each its index, from 0. The
    first package keeps the shipment ID alone, so the keys read before
    packages were told apart stay the same.
    """
    return f"{shipment_id}#{package_index}" if package_index else shipment_id


def shipment_base(key: str) -> str:
    """Return the Amazon shipment ID of a package's key (see shipment_key)."""
    return key.partition("#")[0]


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
