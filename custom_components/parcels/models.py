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
from typing import Any
import unicodedata

from homeassistant.util import dt as dt_util

from .const import (
    ALLOWED_TRANSITIONS,
    CARRIER_NAMES,
    STATUS_RANK,
    TERMINAL_STATUSES,
    MailKind,
    ParcelStatus,
)
from .parsers.base import Eta
from .parsers.items import unique_items
from .parsers.senders import KNOWN_SENDERS, lookup
from .parsers.tracking import detect_carrier, normalize_tracking_number, tracking_url

_LOGGER = logging.getLogger(__name__)

MAX_ITEMS = 20


class Source(StrEnum):
    """Where a piece of information came from."""

    PARSER = "parser"
    AI = "ai"
    MANUAL = "manual"
    SEVENTEENTRACK = "seventeentrack"


# Lower wins when origins disagree.
SOURCE_PRIORITY: dict[Source, int] = {
    Source.MANUAL: 0,
    Source.PARSER: 1,
    Source.SEVENTEENTRACK: 2,
    Source.AI: 3,
}


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
    """Parse a serialised datetime; naive values are taken as UTC."""
    if not value:
        return None
    if isinstance(value, datetime):
        parsed: datetime | None = value
    else:
        parsed = dt_util.parse_datetime(str(value))
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


def merchant_key(name: str | None) -> str:
    """Normalise a merchant name for comparisons: ``Amazon.es`` -> ``amazon``.

    Legal suffixes don't count: ``AMAZON EU SARL SUCURSAL EN`` -> ``amazon``.
    """
    if not name:
        return ""
    tokens = _name_tokens(name)
    for index, token in enumerate(tokens):
        if index and token in _LEGAL_WORDS:
            tokens = tokens[:index]
            while len(tokens) > 1 and tokens[-1] in _REGION_WORDS:
                tokens.pop()
            break
    for words in _KNOWN_MERCHANTS:
        if tuple(tokens[: len(words)]) == words:
            return "".join(words)
    return "".join(tokens)


_KNOWN_MERCHANT_NAMES: dict[str, str] = {
    "".join(words): name for words, name in _KNOWN_MERCHANTS.items()
}


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
    merchant: str | None = None
    order_numbers: tuple[str, ...] = ()
    items: tuple[str, ...] = ()
    pickup_point: str | None = None
    pickup_code: str | None = None
    tracking_url: str | None = None
    message: str | None = None
    owners: tuple[str, ...] = ()
    confirmed: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialise the origin."""
        return _compact(
            {
                "id": self.id,
                "source": self.source.value,
                "time": dt_to_str(self.time),
                "label": self.label,
                "carrier": self.carrier,
                "tracking_number": self.tracking_number,
                "amazon_shipment_id": self.amazon_shipment_id,
                "merchant": self.merchant,
                "order_numbers": list(self.order_numbers),
                "items": list(self.items),
                "pickup_point": self.pickup_point,
                "pickup_code": self.pickup_code,
                "tracking_url": self.tracking_url,
                "message": self.message,
                "owners": list(self.owners),
                "confirmed": self.confirmed,
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
            source=Source(data.get("source", Source.PARSER)),
            time=dt_from_str(data.get("time")) or dt_util.utcnow(),
            label=str(data.get("label", "")),
            carrier=data.get("carrier"),
            tracking_number=data.get("tracking_number"),
            amazon_shipment_id=data.get("amazon_shipment_id"),
            merchant=data.get("merchant"),
            order_numbers=_tuple(data.get("order_numbers")),
            items=_tuple(data.get("items")),
            pickup_point=data.get("pickup_point"),
            pickup_code=data.get("pickup_code"),
            tracking_url=data.get("tracking_url"),
            message=data.get("message"),
            owners=_tuple(data.get("owners")),
            confirmed=bool(data.get("confirmed", False)),
        )


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
    # A delivery concluded from another parcel of the same merchant.
    inferred: bool = False
    id: str = field(default_factory=lambda: secrets.token_hex(6))

    def as_dict(self) -> dict[str, Any]:
        """Serialise the event."""
        return _compact(
            {
                "id": self.id,
                "time": dt_to_str(self.time),
                "source": self.source.value,
                "origin": self.origin,
                "status": self.status.value if self.status else None,
                "kind": self.kind.value if self.kind else None,
                "eta": eta_to_dict(self.eta),
                "clears_eta": self.clears_eta,
                "label": self.label,
                "force": self.force,
                "inferred": self.inferred,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ParcelEvent:
        """Parse a serialised event."""
        return cls(
            id=str(data.get("id") or secrets.token_hex(6)),
            time=dt_from_str(data.get("time")) or dt_util.utcnow(),
            source=Source(data.get("source", Source.PARSER)),
            origin=data.get("origin"),
            status=ParcelStatus(data["status"]) if data.get("status") else None,
            kind=MailKind(data["kind"]) if data.get("kind") else None,
            eta=eta_from_dict(data.get("eta")),
            clears_eta=bool(data.get("clears_eta", False)),
            label=data.get("label"),
            force=bool(data.get("force", False)),
            inferred=bool(data.get("inferred", False)),
        )


@dataclass(slots=True)
class AutoMerge:
    """A heuristic merge that the user should check, with the origins to undo.

    ``origin`` is the origin the heuristic linked; ``origins`` lists more
    origins that leave with it, when a whole parcel was merged.
    """

    origin: str
    at: datetime
    reason: str
    origins: tuple[str, ...] = ()

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
        return data

    @classmethod
    def from_dict(cls, data: Any) -> AutoMerge | None:
        """Parse a serialised flag."""
        if not isinstance(data, Mapping) or not data.get("origin"):
            return None
        return cls(
            origin=str(data["origin"]),
            at=dt_from_str(data.get("at")) or dt_util.utcnow(),
            reason=str(data.get("reason", "")),
            origins=_tuple(data.get("origins")),
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
    # Delivered according to another parcel of the same merchant only.
    inferred: bool = False

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
        created = dt_from_str(data.get("created")) or dt_util.utcnow()
        origins = [Origin.from_dict(item) for item in data.get("origins", ())]
        return cls(
            id=str(data["id"]),
            created=created,
            updated=dt_from_str(data.get("updated")) or created,
            origins={origin.id: origin for origin in origins},
            events=[ParcelEvent.from_dict(item) for item in data.get("events", ())],
            private=bool(data.get("private", False)),
            archived=dt_from_str(data.get("archived")),
            auto_merged=AutoMerge.from_dict(data.get("auto_merged")),
            delivery_rejected=bool(data.get("delivery_rejected", False)),
        )


def is_carrier_mail(origin: Origin) -> bool:
    """Return True for an origin from an e-mail of a carrier's own domain."""
    return (info := lookup(origin.label)) is not None and info.kind == "carrier"


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

    # The merchant's own e-mails name it better than a carrier's.
    merchant_set, merchant = manual_value("merchant")
    if not merchant_set:
        merchant = merchant_display(
            next(
                (
                    o.merchant
                    for o in sorted(
                        origins,
                        key=lambda o: (
                            SOURCE_PRIORITY[o.source],
                            is_carrier_mail(o),
                            o.time,
                            o.id,
                        ),
                    )
                    if o.merchant
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
    # list the whole order, which may come in several packages.
    shipped = [
        o for o in origins if o.items and (o.tracking_number or o.amazon_shipment_id)
    ]
    items = unique_items(item for o in shipped or origins for item in o.items)
    order_numbers: list[str] = []
    shipment_ids: set[str] = set()
    owners: set[str] = set()
    for origin in origins:
        for order in origin.order_numbers:
            if order not in order_numbers:
                order_numbers.append(order)
        if origin.amazon_shipment_id:
            shipment_ids.add(origin.amazon_shipment_id)
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
    status_inferred = False
    delivered_at: datetime | None = None
    eta: Eta | None = None
    eta_time: datetime | None = None
    timeline: list[TimelineEntry] = []
    for event in sorted(parcel.events, key=_event_sort_key):
        accepted, new_status = _accepts(status, event)
        if accepted and new_status is not status:
            status, status_time = new_status, event.time
            status_inferred = event.inferred
            if new_status is ParcelStatus.DELIVERED and delivered_at is None:
                delivered_at = event.time
        elif accepted and not event.inferred:
            # A real e-mail confirming an inferred status makes it a fact.
            status_inferred = False
        event_eta = event.eta
        if (
            event_eta is None
            and accepted
            and event.status is ParcelStatus.OUT_FOR_DELIVERY
            and not event.clears_eta
        ):
            # Out for delivery means today, even when the e-mail gives no date.
            today = local_date(event.time)
            event_eta = Eta(start=today, end=today)
        if (event_eta is not None or event.clears_eta) and (
            eta_time is None or event.time >= eta_time
        ):
            eta, eta_time = (None if event.clears_eta else event_eta), event.time
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
    provisional = not number and not shipment_ids and status is ParcelStatus.ORDERED
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
        inferred=status_inferred and status is ParcelStatus.DELIVERED,
    )


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
            placed_at=dt_from_str(data.get("placed_at")),
            created=dt_from_str(data.get("created")) or dt_util.utcnow(),
        )


@dataclass(slots=True)
class MessageRecord:
    """A processed e-mail, identified by a hash of its Message-ID.

    ``refs`` maps a mailbox config entry to the provider's message ID, so the
    e-mail can be fetched again (for the AI queue or reprocessing). No content
    is kept.
    """

    hash: str
    seen: datetime
    state: MessageState
    refs: dict[str, str] = field(default_factory=dict)
    received: datetime | None = None
    sender_domain: str = ""
    owners: tuple[str, ...] = ()

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
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MessageRecord:
        """Parse a serialised record."""
        return cls(
            hash=str(data["hash"]),
            seen=dt_from_str(data.get("seen")) or dt_util.utcnow(),
            state=MessageState(data.get("state", MessageState.APPLIED)),
            refs={str(k): str(v) for k, v in dict(data.get("refs", {})).items()},
            received=dt_from_str(data.get("received")),
            sender_domain=str(data.get("sender_domain", "")),
            owners=_tuple(data.get("owners")),
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
            "owner": self.owner,
            "reason": self.reason,
            "authenticated": self.authenticated,
            "source": self.source.value,
            "suggestion": self.suggestion.as_dict() if self.suggestion else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReviewItem:
        """Parse a serialised item."""
        suggestion = data.get("suggestion")
        return cls(
            id=str(data["id"]),
            created=dt_from_str(data.get("created")) or dt_util.utcnow(),
            message=str(data.get("message", "")),
            received=dt_from_str(data.get("received")),
            sender=str(data.get("sender", "")),
            sender_domain=str(data.get("sender_domain", "")),
            subject=str(data.get("subject", "")),
            mailbox=data.get("mailbox"),
            owner=data.get("owner"),
            reason=str(data.get("reason", "")),
            authenticated=bool(data.get("authenticated", False)),
            source=Source(data.get("source", Source.PARSER)),
            suggestion=Suggestion.from_dict(suggestion)
            if isinstance(suggestion, Mapping)
            else None,
        )


@dataclass(slots=True)
class FilteredItem:
    """An e-mail the AI classed as not about a parcel, kept so it can be undone."""

    id: str
    created: datetime
    message: str
    received: datetime | None
    sender: str
    sender_domain: str
    subject: str
    mailbox: str | None

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
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FilteredItem:
        """Parse a serialised item."""
        return cls(
            id=str(data["id"]),
            created=dt_from_str(data.get("created")) or dt_util.utcnow(),
            message=str(data.get("message", "")),
            received=dt_from_str(data.get("received")),
            sender=str(data.get("sender", "")),
            sender_domain=str(data.get("sender_domain", "")),
            subject=str(data.get("subject", "")),
            mailbox=data.get("mailbox"),
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
            updated=dt_from_str(data.get("updated")),
        )


# --- The whole store -----------------------------------------------------------

SECTIONS: tuple[str, ...] = (
    "parcels",
    "orders",
    "messages",
    "review",
    "filtered",
    "senders",
    "engine",
    "ai",
    "seventeentrack",
    "cursors",
)


def _load_list[T](
    raw: Any, parse: Callable[[Mapping[str, Any]], T], what: str
) -> list[T]:
    items: list[T] = []
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        return items
    for entry in raw:
        try:
            items.append(parse(entry))
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.warning("Skipping an unreadable stored %s: %s", what, err)
    return items


@dataclass(slots=True)
class ParcelsData:
    """Everything Parcels stores in ``.storage/parcels``."""

    parcels: dict[str, Parcel] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    messages: dict[str, MessageRecord] = field(default_factory=dict)
    review: dict[str, ReviewItem] = field(default_factory=dict)
    filtered: dict[str, FilteredItem] = field(default_factory=dict)
    senders: dict[str, SenderPrefs] = field(default_factory=dict)
    # Free-form sections owned by other modules.
    engine: dict[str, Any] = field(default_factory=dict)
    ai: dict[str, Any] = field(default_factory=dict)
    seventeentrack: dict[str, Any] = field(default_factory=dict)
    cursors: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Serialise everything."""
        return {
            "parcels": [parcel.as_dict() for parcel in self.parcels.values()],
            "orders": [order.as_dict() for order in self.orders.values()],
            "messages": [record.as_dict() for record in self.messages.values()],
            "review": [item.as_dict() for item in self.review.values()],
            "filtered": [item.as_dict() for item in self.filtered.values()],
            "senders": [prefs.as_dict() for prefs in self.senders.values()],
            "engine": self.engine,
            "ai": self.ai,
            "seventeentrack": self.seventeentrack,
            "cursors": self.cursors,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> ParcelsData:
        """Parse stored data, skipping unreadable entries."""
        data = data or {}

        def section(name: str) -> dict[str, Any]:
            value = data.get(name)
            return dict(value) if isinstance(value, Mapping) else {}

        parcels = _load_list(data.get("parcels"), Parcel.from_dict, "parcel")
        orders = _load_list(data.get("orders"), Order.from_dict, "order")
        messages = _load_list(data.get("messages"), MessageRecord.from_dict, "e-mail")
        review = _load_list(data.get("review"), ReviewItem.from_dict, "review item")
        filtered = _load_list(
            data.get("filtered"), FilteredItem.from_dict, "filtered item"
        )
        senders = _load_list(data.get("senders"), SenderPrefs.from_dict, "sender")
        return cls(
            parcels={parcel.id: parcel for parcel in parcels},
            orders={order.key: order for order in orders},
            messages={record.hash: record for record in messages},
            review={item.id: item for item in review},
            filtered={item.id: item for item in filtered},
            senders={prefs.domain: prefs for prefs in senders},
            engine=section("engine"),
            ai=section("ai"),
            seventeentrack=section("seventeentrack"),
            cursors=section("cursors"),
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
