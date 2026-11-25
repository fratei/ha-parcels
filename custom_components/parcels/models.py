"""Persisted data model of the Parcels integration.

Parcels are event-sourced. Every e-mail, 17TRACK update or manual edit adds an
*origin*, which holds the facts it carried (carrier, tracking number, merchant,
order numbers...), and *events*, which hold status changes with their time and
an optional delivery estimate. The current state of a parcel is derived from
both. That way records can be merged and split again without losing anything,
and an e-mail that arrives late can't move a parcel backwards: event times
decide, not arrival order.

Nothing here holds e-mail bodies. Sender addresses and subjects are kept only
for items in the "Needs review" and "Filtered" lists, which expire.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum
import logging
import re
import secrets
from typing import Any, Literal
import unicodedata

from homeassistant.util import dt as dt_util

from .const import (
    ALLOWED_TRANSITIONS,
    CARRIER_NAMES,
    STATUS_RANK,
    TERMINAL_STATUSES,
    LeftAt,
    MailKind,
    ParcelStatus,
)
from .parsers.base import Eta
from .parsers.carriers import brand_carriers
from .parsers.items import unique_items
from .parsers.senders import KNOWN_SENDERS, lookup, organizational_domain
from .parsers.tracking import (
    detect_carrier,
    normalize_tracking_number,
    paack_stem,
    tracking_url,
)

_LOGGER = logging.getLogger(__name__)

MAX_ITEMS = 20
# Ends the ID of the origin that holds what the local AI filled in for an
# e-mail a parser read: the parser's origins end in "#0", "#1"…
FILL_ORIGIN_SUFFIX = "#ai"


class Source(StrEnum):
    """Where a piece of information came from."""

    PARSER = "parser"
    AI = "ai"
    MANUAL = "manual"
    SEVENTEENTRACK = "seventeentrack"
    PARCELAPP = "parcelapp"


# Lower wins when origins disagree.
SOURCE_PRIORITY: dict[Source, int] = {
    Source.MANUAL: 0,
    Source.PARSER: 1,
    Source.SEVENTEENTRACK: 2,
    Source.PARCELAPP: 2,
    Source.AI: 3,
}

# Starts the ID of the origin that holds the Parcel app's news about a number.
# Releases before 0.1.6 skip a whole parcel with a source they don't know, so
# the Parcel app's origins and events are stored as 17TRACK's and told apart
# by this prefix when read back.
PARCELAPP_PREFIX = "pa:"


def _stored_source(source: Source) -> str:
    return Source.SEVENTEENTRACK.value if source is Source.PARCELAPP else source.value


def _loaded_source(value: Any, origin_id: Any) -> Source:
    source = _source(value)
    if (
        source is Source.SEVENTEENTRACK
        and isinstance(origin_id, str)
        and origin_id.startswith(PARCELAPP_PREFIX)
    ):
        return Source.PARCELAPP
    return source


def _source(value: Any) -> Source:
    """Read a stored source; one from a newer release reads as a parser's."""
    try:
        return Source(value or Source.PARSER)
    except ValueError:
        return Source.PARSER


class MessageState(StrEnum):
    """What happened to a processed e-mail."""

    APPLIED = "applied"
    REVIEW = "review"
    FILTERED = "filtered"
    QUEUED = "queued"
    IGNORED = "ignored"
    NOT_PARCEL = "not_parcel"
    DISMISSED = "dismissed"
    FAILED = "failed"


def new_id(prefix: str) -> str:
    """Return a short random identifier such as ``p_1a2b3c4d5e6f``."""
    return f"{prefix}_{secrets.token_hex(6)}"


# --- Serialisation helpers ---------------------------------------------------


def dt_to_str(value: datetime | None) -> str | None:
    """Serialise an aware datetime."""
    return value.isoformat() if value else None


def dt_from_str(value: Any) -> datetime | None:
    """Parse a serialised datetime; naive values are taken as UTC.

    A damaged value (see ``stored_dt``) gives None, as a missing one does.
    """
    try:
        return stored_dt(value)
    except ValueError:
        return None


def stored_dt(value: Any) -> datetime | None:
    """Parse a stored datetime as ``dt_from_str`` does, refusing a damaged one.

    Raises ValueError for a well-formed but impossible time ("month 13"). The
    stored entries' ``from_dict`` use this, so that an entry holding such a
    time is skipped rather than read with the time missing.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        parsed: datetime | None = value
    else:
        try:
            parsed = dt_util.parse_datetime(str(value))
        except OverflowError as err:
            raise ValueError("impossible time") from err
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return parsed


def date_from_str(value: Any) -> date | None:
    """Parse a ``YYYY-MM-DD`` date."""
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def time_to_str(value: time | None) -> str | None:
    """Serialise a wall-clock time as ``HH:MM``."""
    return value.strftime("%H:%M") if value else None


def time_from_str(value: Any) -> time | None:
    """Parse ``HH:MM`` or ``HH:MM:SS``."""
    if not value:
        return None
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0, tzinfo=None)
    try:
        parsed = time.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed.replace(second=0, microsecond=0, tzinfo=None)


def date_to_str(value: date | None) -> str | None:
    """Serialise a date as ``YYYY-MM-DD``."""
    return value.isoformat() if value else None


def left_at_from_str(value: Any) -> LeftAt | None:
    """Parse where a parcel was left; None for anything else."""
    try:
        return LeftAt(value) if value else None
    except ValueError:
        return None


def eta_to_dict(eta: Eta | None) -> dict[str, str | None] | None:
    """Serialise a delivery estimate."""
    if eta is None:
        return None
    return {
        "start": eta.start.isoformat(),
        "end": eta.end.isoformat(),
        "window_start": time_to_str(eta.window_start),
        "window_end": time_to_str(eta.window_end),
    }


def eta_from_dict(data: Any) -> Eta | None:
    """Parse a serialised delivery estimate."""
    if not isinstance(data, Mapping):
        return None
    start = date_from_str(data.get("start"))
    if start is None:
        return None
    end = date_from_str(data.get("end")) or start
    return Eta(
        start=start,
        end=max(start, end),
        window_start=time_from_str(data.get("window_start")),
        window_end=time_from_str(data.get("window_end")),
    )


def local_date(value: datetime) -> date:
    """Return the date of an aware datetime in HA's time zone."""
    return dt_util.as_local(value).date()


def _tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(str(item) for item in value)


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    """Drop keys whose value is None, empty or False, to keep the file small."""
    return {k: v for k, v in data.items() if v not in (None, (), [], {}, False)}


# Words that start the legal part of a company name, e.g. "Amazon EU S.à r.l."
_LEGAL_WORDS = frozenset(
    {
        "ag",
        "branch",
        "bv",
        "gmbh",
        "inc",
        "kg",
        "lda",
        "limited",
        "llc",
        "ltd",
        "niederlassung",
        "nv",
        "plc",
        "sa",
        "sarl",
        "sas",
        "sl",
        "slu",
        "spa",
        "srl",
        "succursale",
        "sucursal",
        "unipessoal",
    }
)
_REGION_WORDS = frozenset({"eu", "europe"})
# Words a shop's or carrier's name may end with: "DHL Express", "Amazon Spain".
_NAME_TAIL_WORDS = frozenset(
    {
        "be",
        "belgium",
        "de",
        "delivery",
        "deutschland",
        "es",
        "espana",
        "eu",
        "europe",
        "express",
        "fr",
        "france",
        "international",
        "it",
        "italia",
        "logistics",
        "marketplace",
        "nederland",
        "nl",
        "online",
        "parcel",
        "portugal",
        "pt",
        "shipping",
        "shop",
        "spain",
        "store",
    }
)


def _name_tokens(name: str) -> list[str]:
    """Split a merchant name into folded words; ``S.à r.l.`` becomes ``sarl``."""
    folded = unicodedata.normalize("NFKD", name.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c)).strip()
    folded = re.sub(r"\.(com|net|org|shop|store|co)?(\.?[a-z]{2})?$", "", folded)
    tokens: list[str] = []
    letters = ""
    for token in re.findall(r"[0-9a-z]+", folded):
        if len(token) == 1 and token.isalpha():
            letters += token
            continue
        if letters:
            tokens.append(letters)
            letters = ""
        tokens.append(token)
    if letters:
        tokens.append(letters)
    return tokens


# Merchants with a sender entry, by their words: their legal entities and
# marketplaces ("Amazon.es", "AMAZON EU SARL") show under one name.
_KNOWN_MERCHANTS: dict[tuple[str, ...], str] = {
    tuple(_name_tokens(info.name)): info.name
    for info in KNOWN_SENDERS.values()
    if info.kind == "merchant"
}


def _merchant_tokens(name: str) -> list[str]:
    """Return a merchant name's words without its legal suffix."""
    tokens = _name_tokens(name)
    for index, token in enumerate(tokens):
        if index and token in _LEGAL_WORDS:
            tokens = tokens[:index]
            while len(tokens) > 1 and tokens[-1] in _REGION_WORDS:
                tokens.pop()
            break
    return tokens


def merchant_key(name: str | None) -> str:
    """Normalise a merchant name for comparisons: ``Amazon.es`` -> ``amazon``.

    Legal suffixes don't count: ``AMAZON EU SARL SUCURSAL EN`` -> ``amazon``.
    """
    if not name:
        return ""
    tokens = _merchant_tokens(name)
    for words in _KNOWN_MERCHANTS:
        if tuple(tokens[: len(words)]) == words:
            return "".join(words)
    return "".join(tokens)


def _named(tokens: list[str], keys: Iterable[str]) -> bool:
    """Return True when words are one of keys, then only a name's tail words."""
    keys = set(keys) - {""}
    return any(
        "".join(tokens[:end]) in keys
        and all(token in _NAME_TAIL_WORDS for token in tokens[end:])
        for end in range(1, len(tokens) + 1)
    )


def is_merchant_name(text: str | None, names: Iterable[str | None] = ()) -> bool:
    """Return True when a text is only a shop's name: a known one, or one of names.

    Unlike :func:`known_merchant_name`, an item named after its shop isn't:
    ``Amazon.es`` and ``Amazon Spain`` are, ``Amazon Basics cable`` isn't.
    """
    if not text or not (tokens := _merchant_tokens(text)):
        return False
    return _named(
        tokens,
        (
            *("".join(words) for words in _KNOWN_MERCHANTS),
            *(merchant_key(name) for name in names if name),
        ),
    )


def is_one_word(text: str | None) -> bool:
    """Return True when a text is at most one word, besides a name's tail words.

    Like a shop's name Parcels may not know: ``SHEIN``, ``Temu Store``.
    An item's title rarely is.
    """
    tokens = _merchant_tokens(text) if text else []
    while len(tokens) > 1 and tokens[-1] in _NAME_TAIL_WORDS:
        tokens.pop()
    return len(tokens) <= 1


# Words a description may add to a shop's name without naming an item:
# "Amazon.es order", "Encomenda da Amazon", "Commande Amazon".
_GENERIC_TITLE_WORDS = frozenset(
    {
        # en
        "a",
        "an",
        "delivery",
        "from",
        "my",
        "of",
        "order",
        "package",
        "parcel",
        "shipment",
        "the",
        # pt
        "da",
        "de",
        "do",
        "encomenda",
        "entrega",
        "envio",
        "meu",
        "minha",
        "pacote",
        "pedido",
        # es
        "del",
        "mi",
        "paquete",
        # fr
        "colis",
        "commande",
        "du",
        "la",
        "le",
        "livraison",
        "ma",
        "mon",
        # de
        "bestellung",
        "lieferung",
        "mein",
        "meine",
        "paket",
        "sendung",
        "von",
        # it
        "consegna",
        "di",
        "il",
        "mio",
        "ordine",
        "pacco",
        "spedizione",
        # nl
        "bestelling",
        "levering",
        "mijn",
        "pakket",
        "van",
        "zending",
    }
)


def is_generic_title(text: str | None, names: Iterable[str | None] = ()) -> bool:
    """Return True when a description names no item, only who sends it.

    One word, or a shop's or carrier's name, also with words like ``order``:
    ``SHEIN``, ``Correos Express``, ``Amazon.es order``, ``Encomenda da
    Amazon``; names adds shops Parcels doesn't know.
    """
    core = " ".join(
        token
        for token in (_name_tokens(text) if text else [])
        if token not in _GENERIC_TITLE_WORDS
    )
    return is_one_word(core) or is_carrier_name(core) or is_merchant_name(core, names)


_KNOWN_MERCHANT_NAMES: dict[str, str] = {
    "".join(words): name for words, name in _KNOWN_MERCHANTS.items()
}


def known_merchant_name(text: str | None) -> str | None:
    """Return the known merchant free text starts with: ``Amazon.es order``."""
    return _KNOWN_MERCHANT_NAMES.get(merchant_key(text)) if text else None


def merchant_display(name: str | None) -> str | None:
    """Return the name to show for a merchant: ``Amazon.es`` -> ``Amazon``."""
    if not name:
        return name
    return _KNOWN_MERCHANT_NAMES.get(merchant_key(name), name)


def order_key(merchant: str | None, number: str) -> str | None:
    """Return the key of an order number.

    Long order numbers (Amazon's ``405-1234567-1234567``) are unique on their
    own. Short ones (a shop's ``#1001``) only together with the merchant.
    """
    normalised = re.sub(r"[^0-9A-Z]", "", number.upper())
    if not normalised:
        return None
    if len(normalised) >= 8:
        return f"ord:{normalised}"
    if not (merchant_part := merchant_key(merchant)):
        return None
    return f"ord:{merchant_part}:{normalised}"


# --- Parcels -----------------------------------------------------------------

_CLEARABLE = ("carrier", "tracking_number", "merchant", "pickup_point", "pickup_code")


@dataclass(slots=True)
class Origin:
    """One source record of a parcel: an e-mail shipment, a 17TRACK package or
    a manual edit.

    In a manual origin, ``None`` means "not set" and an empty string means
    "cleared by the user".
    """

    id: str
    source: Source
    time: datetime
    label: str = ""
    carrier: str | None = None
    tracking_number: str | None = None
    amazon_shipment_id: str | None = None
    # A shipment number other than the tracking number: the part of Paack's
    # order ID before "_", or a shop's own shipment number, which may be the
    # carrier's tracking number too.
    reference: str | None = None
    merchant: str | None = None
    order_numbers: tuple[str, ...] = ()
    items: tuple[str, ...] = ()
    pickup_point: str | None = None
    pickup_code: str | None = None
    tracking_url: str | None = None
    message: str | None = None
    owners: tuple[str, ...] = ()
    confirmed: bool = False
    # What the user calls the parcel in the Parcel app.
    name: str | None = None
    # The marketplace seller that a shop's e-mail names, besides the shop.
    seller: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialise the origin."""
        return _compact(
            {
                "id": self.id,
                "source": _stored_source(self.source),
                "time": dt_to_str(self.time),
                "label": self.label,
                "carrier": self.carrier,
                "tracking_number": self.tracking_number,
                "amazon_shipment_id": self.amazon_shipment_id,
                "reference": self.reference,
                "merchant": self.merchant,
                "order_numbers": list(self.order_numbers),
                "items": list(self.items),
                "pickup_point": self.pickup_point,
                "pickup_code": self.pickup_code,
                "tracking_url": self.tracking_url,
                "message": self.message,
                "owners": list(self.owners),
                "confirmed": self.confirmed,
                "name": self.name,
                "seller": self.seller,
            }
        ) | {
            # Keep explicit clears of manual origins.
            key: ""
            for key in _CLEARABLE
            if getattr(self, key) == ""
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Origin:
        """Parse a serialised origin."""
        return cls(
            id=str(data["id"]),
            source=_loaded_source(data.get("source"), data["id"]),
            time=stored_dt(data.get("time")) or dt_util.utcnow(),
            label=str(data.get("label", "")),
            carrier=data.get("carrier"),
            tracking_number=data.get("tracking_number"),
            amazon_shipment_id=data.get("amazon_shipment_id"),
            reference=data.get("reference") or None,
            merchant=data.get("merchant"),
            order_numbers=_tuple(data.get("order_numbers")),
            items=_tuple(data.get("items")),
            pickup_point=data.get("pickup_point"),
            pickup_code=data.get("pickup_code"),
            tracking_url=data.get("tracking_url"),
            message=data.get("message"),
            owners=_tuple(data.get("owners")),
            confirmed=bool(data.get("confirmed", False)),
            name=data.get("name") or None,
            seller=data.get("seller") or None,
        )


# Why a delivery was only inferred: another parcel of the shop was delivered
# around its dates, a return of its order was started, or it had no news for
# three weeks.
type InferredReason = Literal["shop", "return", "quiet"]
# The label of a delivery inferred from a return of the parcel's order.
INFERRED_RETURN = "return"


def inference_reason(kind: MailKind | None, label: str | None) -> InferredReason:
    """Return why an inferred event concluded a delivery."""
    if label == INFERRED_RETURN:
        return "return"
    return "quiet" if kind is None else "shop"


@dataclass(slots=True)
class ParcelEvent:
    """A status change or a new delivery estimate."""

    time: datetime
    source: Source
    origin: str | None = None
    status: ParcelStatus | None = None
    kind: MailKind | None = None
    eta: Eta | None = None
    clears_eta: bool = False
    label: str | None = None
    force: bool = False
    # A delivery concluded from another parcel of the same merchant (kind
    # "delivered"), from a return of the parcel's order (``label`` is then
    # "return"), or from three weeks without news (no kind).
    inferred: bool = False
    # The source gave no date it could read: ``time`` only places the event
    # after the last thing known to have come before it, on that day. With
    # ``dayless``, nothing did: the day isn't known either. With
    # ``timeless``, the source gave the day but not the time: ``time`` is on
    # that day. It had happened ``by`` then, when it was first seen.
    undated: bool = False
    dayless: bool = False
    by: datetime | None = None
    timeless: bool = False
    # What the source said besides the status: the last day to collect the
    # parcel at its pickup point, the day of the next attempt after a missed
    # one, and where a delivered parcel was left.
    collect_by: date | None = None
    next_attempt: date | None = None
    left_at: LeftAt | None = None
    id: str = field(default_factory=lambda: secrets.token_hex(6))

    def as_dict(self) -> dict[str, Any]:
        """Serialise the event."""
        return _compact(
            {
                "id": self.id,
                "time": dt_to_str(self.time),
                "source": _stored_source(self.source),
                "origin": self.origin,
                "status": self.status.value if self.status else None,
                "kind": self.kind.value if self.kind else None,
                "eta": eta_to_dict(self.eta),
                "clears_eta": self.clears_eta,
                "label": self.label,
                "force": self.force,
                "inferred": self.inferred,
                "undated": self.undated,
                "dayless": self.dayless,
                "by": dt_to_str(self.by),
                "timeless": self.timeless,
                "collect_by": date_to_str(self.collect_by),
                "next_attempt": date_to_str(self.next_attempt),
                "left_at": self.left_at.value if self.left_at else None,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ParcelEvent:
        """Parse a serialised event."""
        return cls(
            id=str(data.get("id") or secrets.token_hex(6)),
            time=stored_dt(data.get("time")) or dt_util.utcnow(),
            source=_loaded_source(data.get("source"), data.get("origin")),
            origin=data.get("origin"),
            status=ParcelStatus(data["status"]) if data.get("status") else None,
            kind=MailKind(data["kind"]) if data.get("kind") else None,
            eta=eta_from_dict(data.get("eta")),
            clears_eta=bool(data.get("clears_eta", False)),
            label=data.get("label"),
            force=bool(data.get("force", False)),
            inferred=bool(data.get("inferred", False)),
            undated=bool(data.get("undated", False)),
            dayless=bool(data.get("dayless", False)),
            by=stored_dt(data.get("by")),
            timeless=bool(data.get("timeless", False)),
            collect_by=date_from_str(data.get("collect_by")),
            next_attempt=date_from_str(data.get("next_attempt")),
            left_at=left_at_from_str(data.get("left_at")),
        )


@dataclass(slots=True)
class AutoMerge:
    """A heuristic merge that the user should check, with the origins to undo.

    ``origin`` is the origin the heuristic linked; ``origins`` lists more
    origins that leave with it, when a whole parcel was merged. ``groups``
    is set when several merges share the flag, such as Amazon shipments
    linked one by one to the package that carried them: on undo, each group
    leaves as its own parcel.
    """

    origin: str
    at: datetime
    reason: str
    origins: tuple[str, ...] = ()
    groups: tuple[tuple[str, ...], ...] = ()

    @property
    def all_origins(self) -> set[str]:
        """Return every origin that leaves on undo."""
        return {self.origin, *self.origins}

    def as_dict(self) -> dict[str, Any]:
        """Serialise the flag."""
        data: dict[str, Any] = {
            "origin": self.origin,
            "at": dt_to_str(self.at),
            "reason": self.reason,
        }
        if self.origins:
            data["origins"] = list(self.origins)
        if self.groups:
            data["groups"] = [list(group) for group in self.groups]
        return data

    @classmethod
    def from_dict(cls, data: Any) -> AutoMerge | None:
        """Parse a serialised flag."""
        if not isinstance(data, Mapping) or not data.get("origin"):
            return None
        groups = data.get("groups")
        return cls(
            origin=str(data["origin"]),
            at=stored_dt(data.get("at")) or dt_util.utcnow(),
            reason=str(data.get("reason", "")),
            origins=_tuple(data.get("origins")),
            groups=tuple(
                group
                for value in (groups if isinstance(groups, list) else ())
                if isinstance(value, list) and (group := _tuple(value))
            ),
        )


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """One event as shown in the parcel details."""

    time: datetime
    status: ParcelStatus | None
    kind: MailKind | None
    source: Source
    origin: str | None
    label: str | None
    accepted: bool
    eta: Eta | None
    inferred: bool = False
    # When it happened isn't known, see ParcelEvent.undated, or only its day
    # is, see ParcelEvent.timeless.
    undated: bool = False
    timeless: bool = False


@dataclass(frozen=True, slots=True)
class ParcelState:
    """The current state of a parcel, derived from its origins and events."""

    status: ParcelStatus
    status_time: datetime | None
    delivered_at: datetime | None
    eta: Eta | None
    carrier: str | None
    tracking_number: str | None
    tracking_url: str | None
    amazon_shipment_ids: tuple[str, ...]
    merchant: str | None
    order_numbers: tuple[str, ...]
    items: tuple[str, ...]
    pickup_point: str | None
    pickup_code: str | None
    owners: tuple[str, ...]
    source: Source
    ai: bool
    provisional: bool
    last_event: datetime | None
    timeline: tuple[TimelineEntry, ...]
    # Delivered by inference only: from another parcel of the same merchant,
    # from a return of the parcel's order, or after three weeks without news.
    inferred: bool = False
    # Why the delivery was inferred, see :func:`inference_reason`.
    inferred_reason: InferredReason | None = None
    # Some details were filled in by the local AI and aren't confirmed yet.
    ai_filled: bool = False
    # What the user calls the parcel in the Parcel app.
    name: str | None = None
    # Which source gave the expected date: the newest event that did.
    eta_source: Source | None = None
    # Shipment numbers, see Origin.reference, other than the tracking numbers.
    references: tuple[str, ...] = ()
    # The status, or the delivery, came without a date: its time is only the
    # last known day (see ParcelEvent.undated), or None when no day is known.
    status_undated: bool = False
    delivered_undated: bool = False
    # It came with its day but not its time: the time is only on that day.
    status_timeless: bool = False
    delivered_timeless: bool = False
    # The marketplace seller, see Origin.seller.
    seller: str | None = None
    # The last day to collect the parcel at its pickup point: while it's
    # ready for pickup, or after a missed attempt.
    collect_by: date | None = None
    # The day of the next attempt, after a missed one.
    next_attempt: date | None = None
    # Where the parcel was left, once delivered.
    left_at: LeftAt | None = None
    # The status's time is when an e-mail reported it, not when it happened:
    # the e-mail didn't say.
    status_reported: bool = False

    @property
    def carrier_name(self) -> str | None:
        """Return the carrier's display name."""
        if not self.carrier:
            return None
        return CARRIER_NAMES.get(self.carrier, self.carrier)

    @property
    def terminal(self) -> bool:
        """Return True for delivered, returned and cancelled parcels."""
        return self.status in TERMINAL_STATUSES


@dataclass(slots=True)
class Parcel:
    """A parcel, possibly assembled from several e-mails and sources."""

    id: str
    created: datetime
    updated: datetime
    origins: dict[str, Origin] = field(default_factory=dict)
    events: list[ParcelEvent] = field(default_factory=list)
    private: bool = False
    archived: datetime | None = None
    auto_merged: AutoMerge | None = None
    # The user undid an inferred delivery: don't infer one again.
    delivery_rejected: bool = False
    _state: ParcelState | None = field(default=None, repr=False, compare=False)

    @property
    def state(self) -> ParcelState:
        """Return the derived state, computed on first use after a change."""
        if self._state is None:
            self._state = derive_state(self)
        return self._state

    def touch(self, now: datetime) -> None:
        """Record a change: forget the derived state and set ``updated``."""
        self._state = None
        self.updated = now

    def drop_codes(self) -> int:
        """Forget the delivery codes; return how many there were."""
        codes = [origin for origin in self.origins.values() if origin.pickup_code]
        for origin in codes:
            origin.pickup_code = None
        if codes:
            self._state = None
        return len(codes)

    def as_dict(self) -> dict[str, Any]:
        """Serialise the parcel."""
        return _compact(
            {
                "id": self.id,
                "created": dt_to_str(self.created),
                "updated": dt_to_str(self.updated),
                "origins": [origin.as_dict() for origin in self.origins.values()],
                "events": [event.as_dict() for event in self.events],
                "private": self.private,
                "archived": dt_to_str(self.archived),
                "auto_merged": self.auto_merged.as_dict() if self.auto_merged else None,
                "delivery_rejected": self.delivery_rejected,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Parcel:
        """Parse a serialised parcel."""
        created = stored_dt(data.get("created")) or dt_util.utcnow()
        origins = [Origin.from_dict(item) for item in data.get("origins", ())]
        return cls(
            id=str(data["id"]),
            created=created,
            updated=stored_dt(data.get("updated")) or created,
            origins={origin.id: origin for origin in origins},
            events=[ParcelEvent.from_dict(item) for item in data.get("events", ())],
            private=bool(data.get("private", False)),
            archived=stored_dt(data.get("archived")),
            auto_merged=AutoMerge.from_dict(data.get("auto_merged")),
            delivery_rejected=bool(data.get("delivery_rejected", False)),
        )


def is_carrier_mail(origin: Origin) -> bool:
    """Return True for an origin from an e-mail of a carrier's own domain."""
    return (info := lookup(origin.label)) is not None and info.kind == "carrier"


_BARE_DOMAIN = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", re.IGNORECASE)

# Carriers by their names' keys; a known merchant (Amazon) is never a carrier.
_CARRIER_KEYS: frozenset[str] = frozenset(
    key
    for key in (
        *(
            merchant_key(name)
            for code, name in CARRIER_NAMES.items()
            if code != "other"
        ),
        *(
            merchant_key(info.name)
            for info in KNOWN_SENDERS.values()
            if info.kind == "carrier"
        ),
    )
    if key and key not in _KNOWN_MERCHANT_NAMES
)


def _bare_domain(name: str) -> bool:
    """Return True for a merchant that is only a domain: ``shop.example``."""
    return merchant_display(name) == name and bool(_BARE_DOMAIN.fullmatch(name.strip()))


def carrier_like(name: str | None) -> bool:
    """Return True when a merchant name is a carrier's: "CTT Expresso"."""
    key = merchant_key(name)
    if not key or key in _KNOWN_MERCHANT_NAMES:
        return False
    return key in _CARRIER_KEYS or bool(brand_carriers(name))


def is_carrier_name(text: str | None) -> bool:
    """Return True when a text is only a carrier's name: "Correos Express".

    Unlike :func:`carrier_like`, an item named after a carrier isn't:
    ``UPS battery backup`` names a UPS but isn't the carrier.
    """
    if not text:
        return False
    return merchant_key(text) in _CARRIER_KEYS or _named(
        _merchant_tokens(text), _CARRIER_KEYS
    )


def _own_mail(origin: Origin) -> bool:
    """Return True when an e-mail's merchant is its sender's own name.

    ``Lumenhaus`` from ``lumenhaus.example`` is; a name from a relay or a
    status service's domain isn't.
    """
    key = merchant_key(origin.merchant)
    first = re.sub(
        r"[^0-9a-z]", "", organizational_domain(origin.label).partition(".")[0]
    )
    if not key or not first:
        return False
    short, long = sorted((key, first), key=len)
    return short == long or (len(short) >= 4 and short in long)


def _best_carrier(ranked: list[Origin], number: str | None) -> str | None:
    """Return a parcel's carrier from its origins, best first.

    The carrier's own e-mails name it best, then the other e-mails about the
    tracking number, then the number's format. A merchant's e-mail without
    the number only counts when nothing else names a carrier.
    """
    if number:
        about = [o for o in ranked if o.tracking_number == number and o.carrier]
        if found := (
            next((o.carrier for o in about if is_carrier_mail(o)), None)
            or next((o.carrier for o in about), None)
            or detect_carrier(number)
        ):
            return found
    named = [o for o in ranked if o.carrier]
    return next((o.carrier for o in named if is_carrier_mail(o)), None) or next(
        (o.carrier for o in named), None
    )


def _event_sort_key(event: ParcelEvent) -> tuple[datetime, int, str]:
    rank = STATUS_RANK.get(event.status, -1) if event.status else -1
    return (event.time, rank, event.id)


def day_known(event: ParcelEvent) -> bool:
    """Return whether an event's day is known.

    An undated event's is when its source gave the day, or when the times
    it's placed between share a day.
    """
    if not event.undated or event.timeless:
        return True
    return (
        not event.dayless
        and event.by is not None
        and local_date(event.by) == local_date(event.time)
    )


def _accepts(
    current: ParcelStatus | None, event: ParcelEvent
) -> tuple[bool, ParcelStatus | None]:
    """Return whether an event's status applies, and the resulting status."""
    new = event.status
    if new is None:
        return False, current
    if current is None or event.force or new in ALLOWED_TRANSITIONS[current]:
        return True, new
    if new is current:
        return True, current
    # A delay notice can take a parcel that was out for delivery back to
    # transit, with a new date.
    if (
        event.kind is MailKind.DELAYED
        and current is ParcelStatus.OUT_FOR_DELIVERY
        and new is ParcelStatus.IN_TRANSIT
    ):
        return True, new
    return False, current


def derive_state(parcel: Parcel) -> ParcelState:
    """Compute the current state of a parcel from its origins and events."""
    origins = sorted(parcel.origins.values(), key=lambda o: (o.time, o.id))
    manual = [o for o in reversed(origins) if o.source is Source.MANUAL]
    ranked = sorted(
        (o for o in origins if o.source is not Source.MANUAL),
        key=lambda o: (SOURCE_PRIORITY[o.source], -o.time.timestamp(), o.id),
    )

    def manual_value(attr: str) -> tuple[bool, str | None]:
        for origin in manual:
            value = getattr(origin, attr)
            if value is not None:
                return True, value or None
        return False, None

    # Tracking number and carrier: a manual edit wins, then the best source,
    # latest first (an international number changes carrier at the border).
    number_set, number = manual_value("tracking_number")
    if not number_set:
        number = next((o.tracking_number for o in ranked if o.tracking_number), None)
    carrier_set, carrier = manual_value("carrier")
    if not carrier_set:
        carrier = _best_carrier(ranked, number)

    # The shop's own e-mails name it best; a bare domain only counts when no
    # e-mail gives a name, and a carrier is never the seller.
    merchant_set, merchant = manual_value("merchant")
    if not merchant_set:
        merchant = merchant_display(
            next(
                (
                    o.merchant
                    for o in sorted(
                        (o for o in origins if o.merchant),
                        key=lambda o: (
                            _bare_domain(o.merchant or ""),
                            not _own_mail(o),
                            is_carrier_mail(o),
                            SOURCE_PRIORITY[o.source],
                            o.time,
                            o.id,
                        ),
                    )
                    if not carrier_like(o.merchant)
                ),
                None,
            )
        )

    def latest(attr: str) -> str | None:
        found, value = manual_value(attr)
        if found:
            return value
        return next((getattr(o, attr) for o in ranked if getattr(o, attr)), None)

    pickup_point = latest("pickup_point")
    pickup_code = latest("pickup_code")

    # A shipment's e-mails list what the package holds; an order's e-mails
    # list the whole order, which may come in several packages. What a parser
    # or the user found replaces what the AI read.
    listed = [o for o in origins if o.items and o.source is not Source.AI] or [
        o for o in origins if o.items
    ]
    shipped = [o for o in listed if o.tracking_number or o.amazon_shipment_id]
    items = unique_items(item for o in shipped or listed for item in o.items)
    order_numbers: list[str] = []
    shipment_ids: set[str] = set()
    references: list[str] = []
    # A shop's shipment number that's the tracking number too shows once.
    numbers = {n.upper() for n in (number, *(o.tracking_number for o in origins)) if n}
    owners: set[str] = set()
    for origin in origins:
        for order in origin.order_numbers:
            if order not in order_numbers:
                order_numbers.append(order)
        if origin.amazon_shipment_id:
            shipment_ids.add(origin.amazon_shipment_id)
        for reference in (origin_paack_stem(origin), origin.reference):
            if (
                reference
                and reference not in references
                and reference.upper() not in numbers
            ):
                references.append(reference)
        owners.update(origin.owners)

    url: str | None = None
    if number:
        url = next(
            (
                o.tracking_url
                for o in ranked
                if o.tracking_number == number and _is_https(o.tracking_url)
            ),
            None,
        ) or tracking_url(carrier, number)
    else:
        url = next((o.tracking_url for o in ranked if _is_https(o.tracking_url)), None)

    # Status: fold the events in time order through the allowed transitions.
    status: ParcelStatus | None = None
    status_time: datetime | None = None
    # When an undated status had happened by.
    status_by: datetime | None = None
    status_undated = False
    status_timeless = False
    status_inferred = False
    inferred_by: InferredReason | None = None
    delivered_at: datetime | None = None
    delivered_found = False
    delivered_undated = False
    delivered_timeless = False
    eta: Eta | None = None
    eta_time: datetime | None = None
    eta_source: Source | None = None
    status_reported = False
    collect_by: date | None = None
    next_attempt: date | None = None
    left_at: LeftAt | None = None
    timeline: list[TimelineEntry] = []
    for event in sorted(parcel.events, key=_event_sort_key):
        accepted, new_status = _accepts(status, event)
        if accepted and new_status is not status:
            status = new_status
            status_time = None if event.dayless else event.time
            status_undated = event.undated
            status_timeless = event.undated and event.timeless
            status_by = event.by if event.undated else None
            status_reported = _reported(parcel, event)
            # Each status has its own details: a new attempt, pickup or
            # delivery starts afresh.
            if new_status not in _COLLECT_STATUSES:
                collect_by = None
            next_attempt = (
                event.next_attempt if new_status is ParcelStatus.ATTEMPTED else None
            )
            left_at = None
            status_inferred = event.inferred
            inferred_by = (
                inference_reason(event.kind, event.label) if event.inferred else None
            )
            if new_status is ParcelStatus.DELIVERED and not delivered_found:
                delivered_found = True
                delivered_at = status_time
                delivered_undated = event.undated
                delivered_timeless = status_timeless
        elif accepted and not event.inferred:
            # A real e-mail confirming an inferred status makes it a fact.
            status_inferred = False
            if (
                status_undated
                and not event.undated
                and status_by is not None
                and local_date(event.time) <= local_date(status_by)
            ):
                # A dated report of an undated status, from no later than the
                # day it had happened by: the best time known.
                replaced = status_time
                status_time, status_undated = event.time, False
                status_timeless = False
                status_reported = _reported(parcel, event)
                if (
                    status is ParcelStatus.DELIVERED
                    and delivered_undated
                    and delivered_at == replaced
                ):
                    delivered_at, delivered_undated = event.time, False
                    delivered_timeless = False
        if accepted:
            collect_by, next_attempt, left_at = _details(
                status, event, collect_by, next_attempt, left_at
            )
        event_eta = event.eta
        if (
            event_eta is None
            and accepted
            and event.status is ParcelStatus.OUT_FOR_DELIVERY
            and not event.clears_eta
            and day_known(event)
        ):
            # Out for delivery means today, even when the e-mail gives no date.
            today = local_date(event.time)
            event_eta = Eta(start=today, end=today)
        if (event_eta is not None or event.clears_eta) and (
            eta_time is None or event.time >= eta_time
        ):
            eta, eta_time = (None if event.clears_eta else event_eta), event.time
            eta_source = None if event.clears_eta else event.source
        timeline.append(
            TimelineEntry(
                time=event.time,
                status=event.status,
                kind=event.kind,
                source=event.source,
                origin=event.origin,
                label=event.label,
                accepted=accepted,
                eta=event.eta,
                inferred=event.inferred,
                undated=event.undated,
                timeless=event.undated and event.timeless,
            )
        )
    if status is None:
        status = ParcelStatus.ORDERED
    if status in TERMINAL_STATUSES and not status_inferred:
        # A delivery code is no use once the parcel arrived or went back.
        pickup_code = None

    if origins:
        source = min((o.source for o in origins), key=lambda s: SOURCE_PRIORITY[s])
    else:
        source = Source.MANUAL
    # Edits don't count as a review: only confirming removes the AI mark.
    found_by = min(
        (o.source for o in origins if o.source is not Source.MANUAL),
        key=lambda s: SOURCE_PRIORITY[s],
        default=None,
    )
    ai = found_by is Source.AI and not any(o.confirmed for o in origins)
    # The AI filled in details of a parcel a parser found.
    ai_filled = not ai and any(
        o.source is Source.AI and o.id.endswith(FILL_ORIGIN_SUFFIX) and not o.confirmed
        for o in origins
    )
    provisional = not number and not shipment_ids and status is ParcelStatus.ORDERED
    inferred = status_inferred and status is ParcelStatus.DELIVERED
    return ParcelState(
        status=status,
        status_time=status_time,
        delivered_at=delivered_at,
        eta=eta,
        carrier=carrier,
        tracking_number=number,
        tracking_url=url,
        amazon_shipment_ids=tuple(sorted(shipment_ids)),
        merchant=merchant,
        order_numbers=tuple(order_numbers),
        items=tuple(items[:MAX_ITEMS]),
        pickup_point=pickup_point,
        pickup_code=pickup_code,
        owners=tuple(sorted(owners)),
        source=source,
        ai=ai,
        provisional=provisional,
        last_event=max((e.time for e in parcel.events), default=None),
        timeline=tuple(timeline),
        inferred=inferred,
        inferred_reason=inferred_by if inferred else None,
        ai_filled=ai_filled,
        name=next((o.name for o in reversed(origins) if o.name), None),
        eta_source=eta_source,
        references=tuple(references),
        status_undated=status_undated,
        delivered_undated=delivered_undated,
        status_timeless=status_timeless,
        delivered_timeless=delivered_timeless,
        seller=next((o.seller for o in reversed(origins) if o.seller), None),
        collect_by=collect_by if status in _COLLECT_STATUSES else None,
        next_attempt=next_attempt if status is ParcelStatus.ATTEMPTED else None,
        left_at=left_at if status is ParcelStatus.DELIVERED else None,
        status_reported=status_reported and status_time is not None,
    )


# The statuses a collect-by date belongs to: a parcel the carrier holds.
_COLLECT_STATUSES = frozenset({ParcelStatus.READY_FOR_PICKUP, ParcelStatus.ATTEMPTED})
# Sources whose event times are an e-mail's when it didn't say when.
_MAIL_SOURCES = frozenset({Source.PARSER, Source.AI})


def _reported(parcel: Parcel, event: ParcelEvent) -> bool:
    """Return True when an event's time is only when its e-mail was sent."""
    if event.source not in _MAIL_SOURCES or event.undated or event.origin is None:
        return False
    origin = parcel.origins.get(event.origin)
    return origin is not None and origin.time == event.time


def _details(
    status: ParcelStatus | None,
    event: ParcelEvent,
    collect_by: date | None,
    next_attempt: date | None,
    left_at: LeftAt | None,
) -> tuple[date | None, date | None, LeftAt | None]:
    """Fold an accepted event's details into the parcel's.

    A later report of the same status adds what it says; one that says
    nothing keeps what an earlier one did. A next attempt is over once
    news comes from its day or later.
    """
    if status in _COLLECT_STATUSES and event.collect_by is not None:
        collect_by = event.collect_by
    if status is ParcelStatus.ATTEMPTED:
        if event.next_attempt is not None:
            next_attempt = event.next_attempt
        elif (
            next_attempt is not None
            and day_known(event)
            and local_date(event.time) >= next_attempt
        ):
            next_attempt = None
    if status is ParcelStatus.DELIVERED and event.left_at is not None:
        left_at = event.left_at
    return collect_by, next_attempt, left_at


def origin_paack_stem(origin: Origin) -> str | None:
    """Return the shipment that Paack's order ID of an origin names, as written."""
    if origin.carrier != "paack":
        return None
    return paack_stem(origin.tracking_number)


def _is_https(url: str | None) -> bool:
    return bool(url) and str(url).lower().startswith("https://")


# --- Orders, e-mails, review --------------------------------------------------


@dataclass(slots=True)
class Order:
    """An order; one order can have several parcels and the reverse."""

    key: str
    number: str
    merchant: str | None
    placed_at: datetime | None
    created: datetime

    def as_dict(self) -> dict[str, Any]:
        """Serialise the order."""
        return _compact(
            {
                "key": self.key,
                "number": self.number,
                "merchant": self.merchant,
                "placed_at": dt_to_str(self.placed_at),
                "created": dt_to_str(self.created),
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Order:
        """Parse a serialised order."""
        return cls(
            key=str(data["key"]),
            number=str(data.get("number", "")),
            merchant=data.get("merchant"),
            placed_at=stored_dt(data.get("placed_at")),
            created=stored_dt(data.get("created")) or dt_util.utcnow(),
        )


@dataclass(frozen=True, slots=True)
class ParcelShell:
    """What a parcel was while one of its e-mails is read again.

    Reading an e-mail again takes its origins out of their parcels, then adds
    the new reading. The shell takes the new reading back to the same parcel,
    with its ID, privacy and flags, instead of a new one. ``origins`` are the
    e-mail's origins that the parcel held.

    ``lost`` is set when nothing else, or only the user's edits, held the
    parcel: it went with the e-mail's origins, and comes back with the edits
    (``kept_origins``) and its inferred events (``kept_events``).
    """

    id: str
    created: datetime
    origins: tuple[str, ...]
    status: ParcelStatus | None = None
    private: bool = False
    archived: datetime | None = None
    delivery_rejected: bool = False
    auto_merged: AutoMerge | None = None
    lost: bool = False
    kept_origins: tuple[Origin, ...] = ()
    kept_events: tuple[ParcelEvent, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Serialise the shell."""
        return _compact(
            {
                "id": self.id,
                "created": dt_to_str(self.created),
                "origins": list(self.origins),
                "status": self.status.value if self.status else None,
                "private": self.private,
                "archived": dt_to_str(self.archived),
                "delivery_rejected": self.delivery_rejected,
                "auto_merged": self.auto_merged.as_dict() if self.auto_merged else None,
                "lost": self.lost,
                "kept_origins": [origin.as_dict() for origin in self.kept_origins],
                "kept_events": [event.as_dict() for event in self.kept_events],
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ParcelShell:
        """Parse a serialised shell; raises ValueError for a damaged one."""
        created = stored_dt(data.get("created"))
        if not data.get("id") or created is None:
            raise ValueError("incomplete shell")
        return cls(
            id=str(data["id"]),
            created=created,
            origins=_tuple(data.get("origins")),
            status=ParcelStatus(data["status"]) if data.get("status") else None,
            private=bool(data.get("private", False)),
            archived=stored_dt(data.get("archived")),
            delivery_rejected=bool(data.get("delivery_rejected", False)),
            auto_merged=AutoMerge.from_dict(data.get("auto_merged")),
            lost=bool(data.get("lost", False)),
            kept_origins=tuple(
                Origin.from_dict(item) for item in data.get("kept_origins", ())
            ),
            kept_events=tuple(
                ParcelEvent.from_dict(item) for item in data.get("kept_events", ())
            ),
        )


def _shells(value: Any) -> tuple[ParcelShell, ...]:
    """Read a record's shells, skipping damaged ones: they only help."""
    shells: list[ParcelShell] = []
    for item in value if isinstance(value, list) else ():
        if not isinstance(item, Mapping):
            continue
        try:
            shells.append(ParcelShell.from_dict(item))
        except AttributeError, KeyError, TypeError, ValueError:
            continue
    return tuple(shells)


@dataclass(slots=True)
class MessageRecord:
    """A processed e-mail, identified by a hash of its Message-ID.

    ``refs`` maps a mailbox config entry to the provider's message ID, so the
    e-mail can be fetched again (for the AI queue or reprocessing). No content
    is kept. ``shells`` hold what the e-mail's parcels were while it is read
    again.
    """

    hash: str
    seen: datetime
    state: MessageState
    refs: dict[str, str] = field(default_factory=dict)
    received: datetime | None = None
    sender_domain: str = ""
    owners: tuple[str, ...] = ()
    shells: tuple[ParcelShell, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Serialise the record."""
        return _compact(
            {
                "hash": self.hash,
                "seen": dt_to_str(self.seen),
                "state": self.state.value,
                "refs": dict(self.refs),
                "received": dt_to_str(self.received),
                "sender_domain": self.sender_domain,
                "owners": list(self.owners),
                "shells": [shell.as_dict() for shell in self.shells],
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MessageRecord:
        """Parse a serialised record."""
        return cls(
            hash=str(data["hash"]),
            seen=stored_dt(data.get("seen")) or dt_util.utcnow(),
            state=MessageState(data.get("state", MessageState.APPLIED)),
            refs={str(k): str(v) for k, v in dict(data.get("refs", {})).items()},
            received=stored_dt(data.get("received")),
            sender_domain=str(data.get("sender_domain", "")),
            owners=_tuple(data.get("owners")),
            shells=_shells(data.get("shells")),
        )


@dataclass(slots=True)
class Suggestion:
    """What a parser or the AI read from an e-mail, as shown for review."""

    kind: MailKind
    merchant: str | None = None
    carrier: str | None = None
    tracking_numbers: tuple[str, ...] = ()
    order_numbers: tuple[str, ...] = ()
    eta_start: date | None = None
    eta_end: date | None = None
    window_start: time | None = None
    window_end: time | None = None
    pickup_point: str | None = None
    pickup_code: str | None = None
    items: tuple[str, ...] = ()
    amazon_shipment_id: str | None = None
    reference: str | None = None
    # The details the e-mail gave besides the status, see ParcelEvent. Not
    # edited in review: kept for the kind they belong to.
    collect_by: date | None = None
    next_attempt: date | None = None
    left_at: LeftAt | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialise the suggestion in the WebSocket format."""
        return {
            "kind": self.kind.value,
            "merchant": self.merchant,
            "carrier": self.carrier,
            "tracking_numbers": list(self.tracking_numbers),
            "order_numbers": list(self.order_numbers),
            "eta_start": self.eta_start.isoformat() if self.eta_start else None,
            "eta_end": self.eta_end.isoformat() if self.eta_end else None,
            "window_start": time_to_str(self.window_start),
            "window_end": time_to_str(self.window_end),
            "pickup_point": self.pickup_point,
            "pickup_code": self.pickup_code,
            "items": list(self.items),
            "amazon_shipment_id": self.amazon_shipment_id,
            "reference": self.reference,
            "collect_by": date_to_str(self.collect_by),
            "next_attempt": date_to_str(self.next_attempt),
            "left_at": self.left_at.value if self.left_at else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Suggestion:
        """Parse a serialised suggestion."""
        try:
            kind = MailKind(data.get("kind", MailKind.UNKNOWN))
        except ValueError:
            kind = MailKind.UNKNOWN
        numbers = tuple(
            normalize_tracking_number(n)
            for n in data.get("tracking_numbers") or ()
            if n and normalize_tracking_number(str(n))
        )
        return cls(
            kind=kind,
            merchant=data.get("merchant") or None,
            carrier=data.get("carrier") or None,
            tracking_numbers=numbers,
            order_numbers=_tuple(data.get("order_numbers")),
            eta_start=date_from_str(data.get("eta_start")),
            eta_end=date_from_str(data.get("eta_end")),
            window_start=time_from_str(data.get("window_start")),
            window_end=time_from_str(data.get("window_end")),
            pickup_point=data.get("pickup_point") or None,
            pickup_code=data.get("pickup_code") or None,
            items=_tuple(data.get("items")),
            amazon_shipment_id=data.get("amazon_shipment_id") or None,
            reference=data.get("reference") or None,
            collect_by=date_from_str(data.get("collect_by")),
            next_attempt=date_from_str(data.get("next_attempt")),
            left_at=left_at_from_str(data.get("left_at")),
        )


@dataclass(slots=True)
class ReviewItem:
    """An e-mail waiting for the user's decision under "Needs review"."""

    id: str
    created: datetime
    message: str
    received: datetime | None
    sender: str
    sender_domain: str
    subject: str
    mailbox: str | None
    owner: str | None
    reason: str
    authenticated: bool
    source: Source
    suggestion: Suggestion | None = None
    # The sender checks, without addresses: see parsers.base.AuthCheck.
    checks: dict[str, Any] | None = None
    # Details the local AI found that a parser missed in an e-mail it read;
    # accepting adds them to the parcel of that e-mail.
    fill: bool = False
    # The checks a rejected AI answer failed, as codes without values.
    errors: tuple[str, ...] = ()
    # What the checks changed in an AI answer, as codes: not failures.
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Serialise the item."""
        data = {
            "id": self.id,
            "created": dt_to_str(self.created),
            "message": self.message,
            "received": dt_to_str(self.received),
            "sender": self.sender,
            "sender_domain": self.sender_domain,
            "subject": self.subject,
            "mailbox": self.mailbox,
            "owner": self.owner,
            "reason": self.reason,
            "authenticated": self.authenticated,
            "source": self.source.value,
            "suggestion": self.suggestion.as_dict() if self.suggestion else None,
            "checks": self.checks,
            "fill": self.fill,
        }
        if self.errors:
            data["errors"] = list(self.errors)
        if self.notes:
            data["notes"] = list(self.notes)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReviewItem:
        """Parse a serialised item."""
        suggestion = data.get("suggestion")
        checks = data.get("checks")
        return cls(
            id=str(data["id"]),
            created=stored_dt(data.get("created")) or dt_util.utcnow(),
            message=str(data.get("message", "")),
            received=stored_dt(data.get("received")),
            sender=str(data.get("sender", "")),
            sender_domain=str(data.get("sender_domain", "")),
            subject=str(data.get("subject", "")),
            mailbox=data.get("mailbox"),
            owner=data.get("owner"),
            reason=str(data.get("reason", "")),
            authenticated=bool(data.get("authenticated", False)),
            source=_source(data.get("source")),
            suggestion=Suggestion.from_dict(suggestion)
            if isinstance(suggestion, Mapping)
            else None,
            checks=dict(checks) if isinstance(checks, Mapping) else None,
            fill=bool(data.get("fill", False)),
            errors=check_codes(data.get("errors")),
            notes=check_codes(data.get("notes")),
        )


_CHECK_CODE = re.compile(r"[a-z0-9_]{1,40}")


def check_codes(value: Any) -> tuple[str, ...]:
    """Return the check codes or notes in a value; anything else is dropped."""
    if not isinstance(value, list | tuple):
        return ()
    return tuple(
        dict.fromkeys(
            code
            for code in value
            if isinstance(code, str) and _CHECK_CODE.fullmatch(code)
        )
    )


@dataclass(slots=True)
class FilteredItem:
    """An e-mail the AI classed as not about a parcel, kept so it can be undone.

    ``removed`` marks an e-mail an administrator removed from Parcels after
    it was read into a parcel. Its subject is empty: Parcels doesn't keep
    the subjects of e-mails it reads into parcels.
    """

    id: str
    created: datetime
    message: str
    received: datetime | None
    sender: str
    sender_domain: str
    subject: str
    mailbox: str | None
    removed: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialise the item."""
        return {
            "id": self.id,
            "created": dt_to_str(self.created),
            "message": self.message,
            "received": dt_to_str(self.received),
            "sender": self.sender,
            "sender_domain": self.sender_domain,
            "subject": self.subject,
            "mailbox": self.mailbox,
            "removed": self.removed,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FilteredItem:
        """Parse a serialised item."""
        return cls(
            id=str(data["id"]),
            created=stored_dt(data.get("created")) or dt_util.utcnow(),
            message=str(data.get("message", "")),
            received=stored_dt(data.get("received")),
            sender=str(data.get("sender", "")),
            sender_domain=str(data.get("sender_domain", "")),
            subject=str(data.get("subject", "")),
            mailbox=data.get("mailbox"),
            removed=bool(data.get("removed", False)),
        )


@dataclass(slots=True)
class SenderPrefs:
    """What the user decided about a sender domain, and what was learned."""

    domain: str
    trusted: bool = False
    ignored: bool = False
    carrier: str | None = None
    accepted: int = 0
    corrections: int = 0
    updated: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialise the preferences."""
        return _compact(
            {
                "domain": self.domain,
                "trusted": self.trusted,
                "ignored": self.ignored,
                "carrier": self.carrier,
                "accepted": self.accepted,
                "corrections": self.corrections,
                "updated": dt_to_str(self.updated),
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SenderPrefs:
        """Parse serialised preferences."""
        return cls(
            domain=str(data["domain"]),
            trusted=bool(data.get("trusted", False)),
            ignored=bool(data.get("ignored", False)),
            carrier=data.get("carrier"),
            accepted=int(data.get("accepted", 0)),
            corrections=int(data.get("corrections", 0)),
            updated=stored_dt(data.get("updated")),
        )


# --- Customer returns ----------------------------------------------------------


class PickupRule(StrEnum):
    """Where a return's pickup day comes from."""

    # The e-mail gives the date.
    EMAIL = "email"
    # The e-mail says "next working day".
    NEXT_WORKING_DAY = "next_working_day"
    # Not in the e-mail: the shop's carrier usually comes the next working day.
    ASSUMED = "assumed"


# Higher wins when e-mails disagree about the pickup day.
PICKUP_RANK: dict[PickupRule, int] = {
    PickupRule.ASSUMED: 0,
    PickupRule.NEXT_WORKING_DAY: 1,
    PickupRule.EMAIL: 2,
}


def _pickup_key(origin: ReturnOrigin) -> tuple[int, datetime]:
    """Return how strongly an e-mail's pickup day counts: by rule, then newest."""
    return PICKUP_RANK[origin.pickup_rule or PickupRule.ASSUMED], origin.time


@dataclass(slots=True)
class ReturnOrigin:
    """What one e-mail said about a customer return.

    ``message`` is the e-mail's hash; ``label`` its sender's organisation.
    ``received`` is set when the shop said the return arrived.
    """

    message: str
    time: datetime
    source: Source = Source.PARSER
    label: str = ""
    merchant: str | None = None
    order_numbers: tuple[str, ...] = ()
    items: tuple[str, ...] = ()
    carrier: str | None = None
    tracking_number: str | None = None
    pickup: date | None = None
    pickup_rule: PickupRule | None = None
    received: bool = False
    owners: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Serialise the origin."""
        return _compact(
            {
                "message": self.message,
                "time": dt_to_str(self.time),
                "source": self.source.value,
                "label": self.label,
                "merchant": self.merchant,
                "order_numbers": list(self.order_numbers),
                "items": list(self.items),
                "carrier": self.carrier,
                "tracking_number": self.tracking_number,
                "pickup": self.pickup.isoformat() if self.pickup else None,
                "pickup_rule": self.pickup_rule.value if self.pickup_rule else None,
                "received": self.received,
                "owners": list(self.owners),
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReturnOrigin:
        """Parse a serialised origin; a rule from a newer release is dropped."""
        pickup = date_from_str(data.get("pickup"))
        try:
            rule = PickupRule(data["pickup_rule"]) if data.get("pickup_rule") else None
        except ValueError:
            rule = None
        return cls(
            message=str(data["message"]),
            time=stored_dt(data.get("time")) or dt_util.utcnow(),
            source=_source(data.get("source")),
            label=str(data.get("label", "")),
            merchant=data.get("merchant") or None,
            order_numbers=_tuple(data.get("order_numbers")),
            items=_tuple(data.get("items")),
            carrier=data.get("carrier") or None,
            tracking_number=data.get("tracking_number") or None,
            pickup=pickup if rule else None,
            pickup_rule=rule if pickup else None,
            received=bool(data.get("received", False)),
            owners=_tuple(data.get("owners")),
        )


@dataclass(slots=True)
class ReturnEntry:
    """A parcel the user sends back to a shop, from the shop's e-mails.

    Kept apart from parcels: it never changes the state of the order's own
    parcels, and it isn't tracked or sent to 17TRACK. On its pickup day the
    notifier shows it until someone marks it picked up (``picked_up``);
    ``reopened`` is when someone last took that back. ``origins`` are keyed
    by the e-mail's hash.
    """

    id: str
    created: datetime
    updated: datetime
    origins: dict[str, ReturnOrigin] = field(default_factory=dict)
    private: bool = False
    archived: datetime | None = None
    picked_up: datetime | None = None
    reopened: datetime | None = None

    def _oldest_first(self) -> list[ReturnOrigin]:
        return sorted(self.origins.values(), key=lambda o: (o.time, o.message))

    def _newest(self, attr: str) -> Any:
        return next(
            (
                value
                for origin in reversed(self._oldest_first())
                if (value := getattr(origin, attr))
            ),
            None,
        )

    @property
    def merchant(self) -> str | None:
        """Return the shop's name, from the newest e-mail that gives it.

        Without one, the sender's domain names it: ``amazon.es`` -> ``Amazon``.
        """
        return merchant_display(self._newest("merchant") or self._newest("label"))

    @property
    def carrier(self) -> str | None:
        """Return the carrier that picks the parcel up, when an e-mail says."""
        return self._newest("carrier")

    @property
    def tracking_number(self) -> str | None:
        """Return the return's tracking number, when an e-mail gives one."""
        return self._newest("tracking_number")

    @property
    def order_numbers(self) -> tuple[str, ...]:
        """Return the order numbers, oldest e-mail first."""
        numbers: list[str] = []
        for origin in self._oldest_first():
            numbers.extend(n for n in origin.order_numbers if n not in numbers)
        return tuple(numbers)

    @property
    def items(self) -> tuple[str, ...]:
        """Return the items sent back."""
        found = unique_items(i for o in self._oldest_first() for i in o.items)
        return tuple(found[:MAX_ITEMS])

    @property
    def owners(self) -> tuple[str, ...]:
        """Return the people whose mailboxes the e-mails came from."""
        return tuple(sorted({p for o in self.origins.values() for p in o.owners}))

    @property
    def started(self) -> datetime:
        """Return the time of the first e-mail."""
        return min((o.time for o in self.origins.values()), default=self.created)

    @property
    def last_news(self) -> datetime:
        """Return the time of the newest e-mail."""
        return max((o.time for o in self.origins.values()), default=self.created)

    def _pickup_origin(self) -> tuple[ReturnOrigin | None, datetime | None]:
        """Return the e-mail whose pickup day counts, and when the day was set.

        The e-mails are replayed oldest first. The day was set by the last
        one that changed it; one giving the same day, like a reminder,
        doesn't change it.
        """
        best: ReturnOrigin | None = None
        since: datetime | None = None
        for origin in self._oldest_first():
            if origin.pickup is None or origin.pickup_rule is None:
                continue
            if best is not None and _pickup_key(origin) <= _pickup_key(best):
                continue
            if best is None or origin.pickup != best.pickup:
                since = origin.time
            best = origin
        return best, since

    @property
    def pickup(self) -> tuple[date, PickupRule] | None:
        """Return the pickup day and where it comes from.

        A date in an e-mail beats "next working day", which beats the day
        assumed for the shop; among equals the newest e-mail wins.
        """
        best, _ = self._pickup_origin()
        if best is None or best.pickup is None or best.pickup_rule is None:
            return None
        return best.pickup, best.pickup_rule

    @property
    def pickup_set(self) -> datetime | None:
        """Return the time of the e-mail that set the pickup day, if there is one."""
        return self._pickup_origin()[1]

    @property
    def received(self) -> bool:
        """Return True when the shop said the return arrived."""
        return any(origin.received for origin in self.origins.values())

    @property
    def day(self) -> date:
        """Return the day shown in the calendar: the pickup, or the first e-mail."""
        pickup = self.pickup
        return pickup[0] if pickup else local_date(self.started)

    def done(self, today: date) -> bool:
        """Return True once the parcel was picked up, or the shop has it.

        Picked up means marked so, or its day is over.
        """
        return self.received or self.picked_up is not None or self.day < today

    def as_dict(self) -> dict[str, Any]:
        """Serialise the return."""
        return _compact(
            {
                "id": self.id,
                "created": dt_to_str(self.created),
                "updated": dt_to_str(self.updated),
                "origins": [origin.as_dict() for origin in self._oldest_first()],
                "private": self.private,
                "archived": dt_to_str(self.archived),
                "picked_up": dt_to_str(self.picked_up),
                "reopened": dt_to_str(self.reopened),
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReturnEntry:
        """Parse a serialised return."""
        created = stored_dt(data.get("created")) or dt_util.utcnow()
        origins = [ReturnOrigin.from_dict(item) for item in data.get("origins", ())]
        return cls(
            id=str(data["id"]),
            created=created,
            updated=stored_dt(data.get("updated")) or created,
            origins={origin.message: origin for origin in origins},
            private=bool(data.get("private", False)),
            archived=stored_dt(data.get("archived")),
            picked_up=stored_dt(data.get("picked_up")),
            reopened=stored_dt(data.get("reopened")),
        )


# --- The whole store -----------------------------------------------------------

SECTIONS: tuple[str, ...] = (
    "parcels",
    "returns",
    "orders",
    "messages",
    "review",
    "filtered",
    "senders",
    "engine",
    "ai",
    "seventeentrack",
    "parcelapp",
    "cursors",
)


def _load_list[T](
    data: Mapping[str, Any],
    key: str,
    parse: Callable[[Mapping[str, Any]], T],
    what: str,
    damaged: dict[str, int],
) -> list[T]:
    """Read a stored list, skipping and counting the entries that can't be read.

    The log names the kind of error only: its text could quote stored data.
    """
    raw = data.get(key)
    items: list[T] = []
    if raw is None:
        return items
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        _LOGGER.warning("Skipping the unreadable stored %s list", what)
        damaged[key] = damaged.get(key, 0) + 1
        return items
    for entry in raw:
        try:
            if not isinstance(entry, Mapping):
                raise TypeError("not an object")
            items.append(parse(entry))
        except Exception as err:
            # One damaged entry never stops the load.
            _LOGGER.warning(
                "Skipping an unreadable stored %s (%s)", what, type(err).__name__
            )
            damaged[key] = damaged.get(key, 0) + 1
    return items


# A time in the ISO form Parcels stores: such a string that can't be read is
# damaged ("month 13"). Free-form sections keep it; their readers ignore it.
_STORED_TIME = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_FREE_FORM_SECTIONS = ("engine", "ai", "seventeentrack", "parcelapp", "cursors")


def _unreadable_times(value: Any, depth: int = 0) -> int:
    """Count the stored times in a free-form section that can't be read."""
    if isinstance(value, str):
        return int(
            _STORED_TIME.fullmatch(value) is not None and dt_from_str(value) is None
        )
    if depth >= 32:
        return 0
    if isinstance(value, Mapping):
        return sum(_unreadable_times(item, depth + 1) for item in value.values())
    if isinstance(value, list):
        return sum(_unreadable_times(item, depth + 1) for item in value)
    return 0


@dataclass(slots=True)
class ParcelsData:
    """Everything Parcels stores in ``.storage/parcels``."""

    parcels: dict[str, Parcel] = field(default_factory=dict)
    returns: dict[str, ReturnEntry] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    messages: dict[str, MessageRecord] = field(default_factory=dict)
    review: dict[str, ReviewItem] = field(default_factory=dict)
    filtered: dict[str, FilteredItem] = field(default_factory=dict)
    senders: dict[str, SenderPrefs] = field(default_factory=dict)
    # Free-form sections owned by other modules.
    engine: dict[str, Any] = field(default_factory=dict)
    ai: dict[str, Any] = field(default_factory=dict)
    seventeentrack: dict[str, Any] = field(default_factory=dict)
    parcelapp: dict[str, Any] = field(default_factory=dict)
    cursors: dict[str, Any] = field(default_factory=dict)
    # What the last load found damaged, by section: the entries it skipped, or
    # in a free-form section the times no reader can use. Not stored.
    damaged: dict[str, int] = field(default_factory=dict, compare=False, repr=False)

    def as_dict(self) -> dict[str, Any]:
        """Serialise everything."""
        return {
            "parcels": [parcel.as_dict() for parcel in self.parcels.values()],
            "returns": [entry.as_dict() for entry in self.returns.values()],
            "orders": [order.as_dict() for order in self.orders.values()],
            "messages": [record.as_dict() for record in self.messages.values()],
            "review": [item.as_dict() for item in self.review.values()],
            "filtered": [item.as_dict() for item in self.filtered.values()],
            "senders": [prefs.as_dict() for prefs in self.senders.values()],
            "engine": self.engine,
            "ai": self.ai,
            "seventeentrack": self.seventeentrack,
            "parcelapp": self.parcelapp,
            "cursors": self.cursors,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> ParcelsData:
        """Parse stored data, skipping and counting unreadable entries."""
        if not isinstance(data, Mapping):
            data = {}
        damaged: dict[str, int] = {}

        def section(name: str) -> dict[str, Any]:
            value = data.get(name)
            if not isinstance(value, Mapping):
                return {}
            value = dict(value)
            if count := _unreadable_times(value):
                _LOGGER.warning(
                    "Ignoring %d unreadable stored times in %s", count, name
                )
                damaged[name] = count
            return value

        parcels = _load_list(data, "parcels", Parcel.from_dict, "parcel", damaged)
        returns = _load_list(data, "returns", ReturnEntry.from_dict, "return", damaged)
        orders = _load_list(data, "orders", Order.from_dict, "order", damaged)
        messages = _load_list(
            data, "messages", MessageRecord.from_dict, "e-mail", damaged
        )
        review = _load_list(
            data, "review", ReviewItem.from_dict, "review item", damaged
        )
        filtered = _load_list(
            data, "filtered", FilteredItem.from_dict, "filtered item", damaged
        )
        senders = _load_list(data, "senders", SenderPrefs.from_dict, "sender", damaged)
        free_form = {name: section(name) for name in _FREE_FORM_SECTIONS}
        return cls(
            parcels={parcel.id: parcel for parcel in parcels},
            returns={entry.id: entry for entry in returns},
            orders={order.key: order for order in orders},
            messages={record.hash: record for record in messages},
            review={item.id: item for item in review},
            filtered={item.id: item for item in filtered},
            senders={prefs.domain: prefs for prefs in senders},
            **free_form,
            damaged=damaged,
        )

    def sender(self, domain: str) -> SenderPrefs:
        """Return the preferences of a sender domain, creating them if needed."""
        domain = domain.lower()
        if (prefs := self.senders.get(domain)) is None:
            prefs = self.senders[domain] = SenderPrefs(domain=domain)
        return prefs

    def trusted_domains(self) -> tuple[str, ...]:
        """Return the domains the user chose to trust."""
        return tuple(sorted(d for d, p in self.senders.items() if p.trusted))

    def is_ignored(self, domain: str) -> bool:
        """Return True when the user chose to ignore a sender domain."""
        prefs = self.senders.get(domain.lower())
        return bool(prefs and prefs.ignored)
