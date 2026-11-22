"""The JSON that the Parcels page reads, and who may see what.

A private parcel is shown in full to its owners (the people whose mailboxes
it came from), or to administrators when it has no owner. Everyone else sees
when it arrives, but not what it is or where it comes from. A return is
private when it's marked so or its order's parcel is.

A delivery PIN or pickup code is sent with a parcel's details, and in the
list only to those who may see the parcel, while it's on its way. Entities,
events, logs, diagnostics and notifications never have it.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import TYPE_CHECKING, Any

from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import CARRIER_NAMES, CONF_DASHBOARD_PATH, CONF_SEVENTEENTRACK
from .customer_returns import linked_parcels, order_index
from .dedup import (
    MergeSuggestion,
    amazon_disagree,
    amazon_elsewhere,
    amazon_evidence,
    first_news,
    is_shop_sender,
    manual_origin_id,
    order_parcels,
    ordered_at,
    parcel_order_keys,
    shipped_at,
    split_problem,
)
from .models import (
    FILL_ORIGIN_SUFFIX,
    FilteredItem,
    InferredReason,
    Origin,
    Parcel,
    ParcelEvent,
    ReturnEntry,
    ReviewItem,
    Source,
    TimelineEntry,
    dt_to_str,
    inference_reason,
    merchant_key,
    time_to_str,
)
from .parsers.senders import lookup, organizational_domain
from .parsers.tracking import tracking_url

if TYPE_CHECKING:
    from .engine import ParcelsEngine

PERSON_DOMAIN = "person"
# How the parcel details name the source of an inferred delivery.
_INFERRED_SOURCES: dict[InferredReason, str] = {
    "shop": "inferred",
    "return": "inferred_return",
    "quiet": "quiet",
}


@dataclass(frozen=True, slots=True)
class Viewer:
    """The user a view is built for."""

    is_admin: bool
    persons: frozenset[str] = frozenset()

    def can_see(self, parcel: Parcel) -> bool:
        """Return True when the user may see a parcel's details."""
        if not parcel.private:
            return True
        owners = parcel.state.owners
        if owners:
            return not self.persons.isdisjoint(owners)
        return self.is_admin

    def can_see_return(self, entry: ReturnEntry, linked: Iterable[Parcel]) -> bool:
        """Return True when the user may see a return's details.

        ``linked`` are the parcels of its orders. A private one makes the
        return private too, shown to the owners of both.
        """
        private = [parcel for parcel in linked if parcel.private]
        if not entry.private and not private:
            return True
        owners = {
            *entry.owners,
            *(o for parcel in private for o in parcel.state.owners),
        }
        if owners:
            return not self.persons.isdisjoint(owners)
        return self.is_admin


# Automations, scripts and other calls without a user.
SYSTEM_VIEWER = Viewer(is_admin=True)


def viewer_for(hass: HomeAssistant, user: User | None) -> Viewer:
    """Return the viewer of a Home Assistant user; None means the system."""
    if user is None:
        return SYSTEM_VIEWER
    persons = frozenset(
        state.entity_id
        for state in hass.states.async_all(PERSON_DOMAIN)
        if state.attributes.get("user_id") == user.id
    )
    return Viewer(is_admin=user.is_admin, persons=persons)


async def async_viewer(hass: HomeAssistant, user_id: str | None) -> Viewer:
    """Return the viewer of a service call's user."""
    if user_id is None:
        return SYSTEM_VIEWER
    user = await hass.auth.async_get_user(user_id)
    if user is None:
        return Viewer(is_admin=False)
    return viewer_for(hass, user)


def splittable_origins(parcel: Parcel) -> list[str]:
    """Return the origins that can be split off, oldest first.

    The parcel's own edits always stay with it.
    """
    edits = manual_origin_id(parcel.id)
    return [
        origin.id
        for origin in sorted(parcel.origins.values(), key=lambda o: (o.time, o.id))
        if origin.id != edits
    ]


# --- Packages of one shipment ----------------------------------------------------

# The serial at the end of a tracking number; its last digit may be a check digit.
_SERIAL = re.compile(r"\d{6,}$")
SHIPMENT_MIN_LENGTH = 10
# How far apart the serials of one shipment's packages may be.
SHIPMENT_SPREAD = 50
# How far apart the first e-mails about them may be.
SHIPMENT_GAP = timedelta(hours=48)


@dataclass(frozen=True, slots=True)
class _Package:
    """What tells a package of a multi-package shipment apart."""

    parcel_id: str
    bucket: tuple[str, int, str]
    serial: int
    first: datetime
    orders: frozenset[str]
    shops: frozenset[str]
    merchant: str


def _package(parcel: Parcel) -> _Package | None:
    state = parcel.state
    number = state.tracking_number
    if not state.carrier or not number or len(number) < SHIPMENT_MIN_LENGTH:
        return None
    if (serial := _SERIAL.search(number)) is None:
        return None
    if (first := first_news(parcel)) is None:
        return None
    return _Package(
        parcel_id=parcel.id,
        bucket=(state.carrier, len(number), number[: serial.start()]),
        serial=int(serial.group()[:-1]),
        first=first,
        orders=frozenset(parcel_order_keys(parcel)),
        shops=frozenset(
            origin.label
            for origin in parcel.origins.values()
            if origin.message is not None and is_shop_sender(origin.label)
        ),
        merchant=merchant_key(state.merchant),
    )


def _one_shipment(first: _Package, second: _Package) -> bool:
    if abs(first.serial - second.serial) > SHIPMENT_SPREAD:
        return False
    if abs(first.first - second.first) > SHIPMENT_GAP:
        return False
    return bool(
        first.orders & second.orders
        or first.shops & second.shops
        or (first.merchant and first.merchant == second.merchant)
    )


def shipment_groups(parcels: Iterable[Parcel]) -> dict[str, str]:
    """Return the shipment of each parcel that is one package of several.

    A shop may send several packages at once, each with its own number. They
    have one carrier, numbers in a short run, and first e-mails within two
    days of each other from the same order, shop or merchant. The page shows
    them as one box per day; each stays a parcel of its own. A shipment is
    named after its smallest parcel ID.
    """
    buckets: dict[tuple[str, int, str], list[_Package]] = defaultdict(list)
    for parcel in parcels:
        if (package := _package(parcel)) is not None:
            buckets[package.bucket].append(package)
    parent: dict[str, str] = {}

    def root(parcel_id: str) -> str:
        while (up := parent.get(parcel_id, parcel_id)) != parcel_id:
            parcel_id = up
        return parcel_id

    for packages in buckets.values():
        for index, first in enumerate(packages):
            for second in packages[index + 1 :]:
                if _one_shipment(first, second):
                    one, other = root(first.parcel_id), root(second.parcel_id)
                    # The smallest ID stays the root, so it names the shipment.
                    parent[max(one, other)] = min(one, other)
                    parent.setdefault(min(one, other), min(one, other))
    return {parcel_id: root(parcel_id) for parcel_id in parent}


def _amazon_tracking(parcel: Parcel) -> dict[str, Any] | None:
    """Return when and where Amazon's tracking says a shipment was delivered.

    With "timeless", Amazon gave the day but not the time.
    """
    evidence = amazon_evidence(parcel)
    if evidence is None:
        return None
    return {
        "delivered": dt_to_str(evidence.delivered),
        "timeless": evidence.timeless,
        "place": evidence.place,
    }


def parcel_json(
    parcel: Parcel,
    viewer: Viewer,
    *,
    shipment: str | None = None,
    code: bool = False,
) -> dict[str, Any]:
    """Return a parcel as the page shows it.

    ``shipment`` is the parcel's group from :func:`shipment_groups`. The PIN
    or pickup code is only included with ``code``, and never for a viewer who
    may not see the parcel. Such a viewer sees when it comes, including the
    next attempt, but not where it waits or was left, nor until when.
    """
    state = parcel.state
    eta = state.eta
    restricted = not viewer.can_see(parcel)
    result: dict[str, Any] = {
        "id": parcel.id,
        "merchant": state.merchant,
        # The marketplace seller, when the shop sells for others.
        "seller": state.seller,
        "carrier": state.carrier,
        "carrier_name": state.carrier_name,
        "tracking_number": state.tracking_number,
        "tracking_url": state.tracking_url,
        "status": state.status.value,
        "status_time": dt_to_str(state.status_time),
        "eta_start": eta.start.isoformat() if eta else None,
        "eta_end": eta.end.isoformat() if eta else None,
        "window_start": time_to_str(eta.window_start) if eta else None,
        "window_end": time_to_str(eta.window_end) if eta else None,
        "delivered_at": dt_to_str(state.delivered_at),
        # Without a date from its source: the time is the last known day's,
        # or None when no day is known. Timeless: the day is known, the time
        # isn't.
        "status_undated": state.status_undated,
        "status_timeless": state.status_timeless,
        "delivered_undated": state.delivered_undated,
        "delivered_timeless": state.delivered_timeless,
        # The status time is when an e-mail reported it, not when it happened.
        "status_reported": state.status_reported,
        "next_attempt": (
            state.next_attempt.isoformat() if state.next_attempt else None
        ),
        "collect_by": state.collect_by.isoformat() if state.collect_by else None,
        "left_at": state.left_at.value if state.left_at else None,
        "inferred": state.inferred,
        "inferred_reason": state.inferred_reason,
        "pickup_point": state.pickup_point,
        "pickup_code": state.pickup_code if code else None,
        "has_code": bool(state.pickup_code),
        "order_numbers": list(state.order_numbers),
        "references": list(state.references),
        "items": list(state.items),
        "private": parcel.private,
        "owners": list(state.owners),
        "source": state.source.value,
        "ai": state.ai,
        "ai_filled": state.ai_filled,
        "auto_merged": parcel.auto_merged.as_dict() if parcel.auto_merged else None,
        "provisional": state.provisional,
        "archived": parcel.archived is not None,
        "origins": splittable_origins(parcel),
        "shipment_group": shipment,
        "name": state.name,
        "eta_source": state.eta_source.value if state.eta_source else None,
        "senders": parcel_senders(parcel),
        "ordered_at": dt_to_str(ordered_at(parcel)),
        "shipped_at": dt_to_str(shipped_at(parcel)),
        "amazon_tracking": _amazon_tracking(parcel),
        "restricted": restricted,
    }
    if restricted:
        result.update(
            merchant=None,
            seller=None,
            carrier=None,
            carrier_name=None,
            tracking_number=None,
            tracking_url=None,
            pickup_point=None,
            pickup_code=None,
            has_code=False,
            collect_by=None,
            left_at=None,
            order_numbers=[],
            references=[],
            items=[],
            source="parser",
            ai=False,
            ai_filled=False,
            auto_merged=None,
            inferred=False,
            inferred_reason=None,
            origins=[],
            shipment_group=None,
            name=None,
            eta_source=None,
            senders=[],
            ordered_at=None,
            shipped_at=None,
            amazon_tracking=None,
        )
    return result


# How a parcel's list of senders names where its news came from.
_SENDER_SOURCES: dict[Source, str] = {
    Source.PARSER: "email",
    Source.AI: "email",
    Source.SEVENTEENTRACK: "seventeentrack",
    Source.PARCELAPP: "parcelapp",
}


def parcel_senders(parcel: Parcel) -> list[dict[str, Any]]:
    """Return who told about a parcel, in the order they first did.

    Each e-mail counts once, with or without the local AI's reading of it;
    the user's edits don't count. ``carrier`` is True for a carrier's own
    e-mails.
    """
    senders: dict[tuple[str, str], dict[str, Any]] = {}
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for origin in sorted(parcel.origins.values(), key=lambda o: (o.time, o.id)):
        source = _SENDER_SOURCES.get(origin.source)
        if source is None:
            continue
        known = lookup(origin.label) if source == "email" and origin.label else None
        name = known.name if known else origin.label
        group = (source, name)
        seen[group].add(origin.message or origin.id)
        senders.setdefault(
            group,
            {
                "name": name,
                "source": source,
                "carrier": known is not None and known.kind == "carrier",
            },
        )["count"] = len(seen[group])
    return list(senders.values())


def return_json(
    entry: ReturnEntry, viewer: Viewer, linked: Iterable[Parcel]
) -> dict[str, Any]:
    """Return a customer return as the page shows it.

    ``linked`` are the parcels of its orders. Someone who may not see the
    return only gets its day. Whether it's done depends on the day, so the
    page works it out: picked up once its day is over, or received.
    """
    parcels = list(linked)
    pickup = entry.pickup
    carrier, number = entry.carrier, entry.tracking_number
    restricted = not viewer.can_see_return(entry, parcels)
    origins = sorted(entry.origins.values(), key=lambda o: (o.time, o.message))
    result: dict[str, Any] = {
        "id": entry.id,
        "merchant": entry.merchant,
        "carrier": carrier,
        "carrier_name": CARRIER_NAMES.get(carrier, carrier) if carrier else None,
        "tracking_number": number,
        "tracking_url": tracking_url(carrier, number) if number else None,
        "day": entry.day.isoformat(),
        "pickup": pickup[0].isoformat() if pickup else None,
        "pickup_rule": pickup[1].value if pickup else None,
        "started": dt_to_str(entry.started),
        "received": entry.received,
        "order_numbers": list(entry.order_numbers),
        "items": list(entry.items),
        "parcel_ids": [parcel.id for parcel in parcels if viewer.can_see(parcel)],
        "emails": [
            {
                "time": dt_to_str(origin.time),
                "label": origin.label,
                "source": origin.source.value,
            }
            for origin in origins
        ],
        "private": entry.private or any(parcel.private for parcel in parcels),
        "owners": list(entry.owners),
        "archived": entry.archived is not None,
        "restricted": restricted,
    }
    if restricted:
        result.update(
            merchant=None,
            carrier=None,
            carrier_name=None,
            tracking_number=None,
            tracking_url=None,
            order_numbers=[],
            items=[],
            parcel_ids=[],
            emails=[],
        )
    return result


def mailbox_owner(hass: HomeAssistant, item: ReviewItem) -> str | None:
    """Return whose mailbox an e-mail came from."""
    if item.owner and (state := hass.states.get(item.owner)) is not None:
        return state.name
    if item.mailbox and (entry := hass.config_entries.async_get_entry(item.mailbox)):
        return entry.title
    return None


def review_json(
    hass: HomeAssistant, item: ReviewItem, trusted: Collection[str] = ()
) -> dict[str, Any]:
    """Return an e-mail under "Needs review".

    ``trusted`` holds the trusted sender domains: an e-mail from one of them
    that failed the sender checks is marked, since trusting can't help it.
    """
    return {
        "id": item.id,
        "created": dt_to_str(item.created),
        "received": dt_to_str(item.received),
        "sender": item.sender,
        "sender_domain": item.sender_domain,
        "subject": item.subject,
        "mailbox_owner": mailbox_owner(hass, item),
        "reason": item.reason,
        "authenticated": item.authenticated,
        "trusted_sender": not item.authenticated
        and organizational_domain(item.sender_domain) in trusted,
        "checks": item.checks,
        "fill": item.fill,
        "errors": list(item.errors),
        "notes": list(item.notes),
        "source": "ai" if item.source.value == "ai" else "parser",
        "suggestion": item.suggestion.as_dict() if item.suggestion else None,
    }


def filtered_json(item: FilteredItem) -> dict[str, Any]:
    """Return an e-mail that was filtered as not about a parcel."""
    return {
        "id": item.id,
        "created": dt_to_str(item.created),
        "received": dt_to_str(item.received),
        "sender": item.sender,
        "sender_domain": item.sender_domain,
        "subject": item.subject,
        # Removed from Parcels by an administrator, rather than filtered.
        "removed": item.removed,
    }


def suggestion_json(
    engine: ParcelsEngine, item: MergeSuggestion, viewer: Viewer
) -> dict[str, Any] | None:
    """Return a merge suggestion with its parcels, or None to leave it out.

    The parcels are included because they may be archived, and only the
    parcels the user may see are.
    """
    parcels = engine.data.parcels
    target = parcels.get(item.parcel_id)
    if target is None or not viewer.can_see(target):
        return None
    candidates = [
        parcels[parcel_id]
        for parcel_id in item.candidates
        if parcel_id in parcels and viewer.can_see(parcels[parcel_id])
    ]
    if not candidates:
        return None
    return {
        "id": item.id,
        "reason": item.reason,
        "merchant": item.merchant,
        "day": item.day.isoformat() if item.day else None,
        "parcel": parcel_json(target, viewer),
        "candidates": [parcel_json(parcel, viewer) for parcel in candidates],
    }


def settings_json(engine: ParcelsEngine, viewer: Viewer) -> dict[str, Any]:
    """Return the settings the page needs.

    Only administrators see the review lists, so only they get the AI queue.
    """
    options = engine.options
    ai_queue = engine.ai.queue_size if viewer.is_admin and engine.ai_active else 0
    return {
        "user_is_admin": viewer.is_admin,
        "ai_enabled": engine.ai_active,
        "ai_mode": engine.ai_mode.value,
        "ai_queue": ai_queue,
        "ai_queue_seconds": engine.ai.wait_seconds() if ai_queue else None,
        "dashboard_url": str(options.get(CONF_DASHBOARD_PATH) or ""),
        "seventeentrack": bool(
            options.get(CONF_SEVENTEENTRACK)
            and engine.tracker is not None
            and engine.tracker.available
        ),
        "time_zone": engine.hass.config.time_zone,
        "today": dt_util.now().date().isoformat(),
    }


def _newest_first[T: (ReviewItem, FilteredItem)](items: list[T]) -> list[T]:
    return sorted(
        items, key=lambda item: (item.received or item.created, item.id), reverse=True
    )


def snapshot(engine: ParcelsEngine, viewer: Viewer) -> dict[str, Any]:
    """Return everything the page shows."""
    data = engine.data
    hass = engine.hass
    review: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    if viewer.is_admin:
        suggestions = [
            found
            for item in engine.suggestions
            if (found := suggestion_json(engine, item, viewer)) is not None
        ]
        trusted = frozenset(data.trusted_domains())
        review = [
            review_json(hass, item, trusted)
            for item in _newest_first(list(data.review.values()))
        ]
        filtered = [
            filtered_json(item) for item in _newest_first(list(data.filtered.values()))
        ]
    groups = shipment_groups(
        parcel for parcel in data.parcels.values() if viewer.can_see(parcel)
    )
    index = order_index(data)
    return {
        "parcels": [
            parcel_json(
                parcel,
                viewer,
                shipment=groups.get(parcel.id),
                code=not parcel.state.terminal,
            )
            for parcel in data.parcels.values()
        ],
        "returns": [
            return_json(entry, viewer, linked_parcels(entry, index))
            for entry in data.returns.values()
        ],
        "review": review,
        "merge_suggestions": suggestions,
        "filtered": filtered,
        "settings": settings_json(engine, viewer),
    }


def _timeline_source(entry: TimelineEntry) -> str:
    """Return where a timeline entry comes from, as the page names it.

    An inferred delivery comes from another delivery ("inferred"), from a
    return of the parcel's order ("inferred_return"), or from three weeks
    without news ("quiet").
    """
    if not entry.inferred:
        return entry.source.value
    return _INFERRED_SOURCES[inference_reason(entry.kind, entry.label)]


def details(engine: ParcelsEngine, parcel: Parcel, viewer: Viewer) -> dict[str, Any]:
    """Return a parcel with its timeline, orders and origins.

    "contradicted" lists the parcels the viewer may see that Amazon's
    tracking rules out as the same package: one is an Amazon shipment and
    the other a carrier's package delivered at another time. "elsewhere"
    lists the others its tracking points away from: the packages that don't
    repeat a shipment's times when some do, or the shipments whose times
    some other package repeats. Callers check ``viewer.can_see`` first.
    """
    data = engine.data
    state = parcel.state
    timeline = [
        {
            "time": dt_to_str(entry.time),
            "status": (
                entry.status.value
                if entry.status is not None
                else entry.kind.value
                if entry.kind is not None
                else "updated"
            ),
            "source": _timeline_source(entry),
            "label": "" if entry.inferred else entry.label or "",
            "undated": entry.undated,
            "timeless": entry.timeless,
        }
        for entry in state.timeline
        if entry.accepted
    ]
    orders = []
    for key in sorted(parcel_order_keys(parcel)):
        if (order := data.orders.get(key)) is None:
            continue
        orders.append(
            {
                "id": key,
                "merchant": order.merchant,
                "number": order.number,
                "placed_at": dt_to_str(order.placed_at),
                "parcel_ids": [
                    other.id
                    for other in order_parcels(data, key)
                    if viewer.can_see(other)
                ],
            }
        )
    groups = shipment_groups(
        other for other in data.parcels.values() if viewer.can_see(other)
    )
    contradicted = sorted(
        other.id
        for other in data.parcels.values()
        if other.id != parcel.id
        and viewer.can_see(other)
        and amazon_disagree(parcel, other)
    )
    return {
        "parcel": parcel_json(
            parcel, viewer, shipment=groups.get(parcel.id), code=True
        ),
        "timeline": timeline,
        "orders": orders,
        "origins": origin_rows(engine, parcel, viewer),
        "contradicted": contradicted,
        "elsewhere": sorted(
            amazon_elsewhere(data, parcel, viewer.can_see).difference(
                contradicted, (parcel.id,)
            )
        ),
    }


def _origin_news(
    parcel: Parcel, origin_id: str
) -> tuple[ParcelEvent | None, ParcelEvent | None]:
    """Return an origin's latest news and its latest delivery estimate.

    Inferred events aren't the origin's news. Of events at the same time,
    the later one in the list counts.
    """
    said = estimate = None
    events = (e for e in parcel.events if e.origin == origin_id and not e.inferred)
    for event in sorted(events, key=lambda e: e.time):
        if event.status is not None or event.kind is not None:
            said = event
        if event.eta is not None or event.clears_eta:
            estimate = event
    return said, estimate


def _shipment_numbers(
    engine: ParcelsEngine, parcel: Parcel, viewer: Viewer
) -> dict[str, list[int]]:
    """Number the Amazon shipments of a parcel's orders: [1, 2], [2, 2]…

    Shipments are numbered by when they were first seen, across the parcel
    and the other parcels of its orders the viewer may see. Orders of one
    shipment aren't numbered.
    """
    parcels = {parcel.id: parcel}
    for key in parcel_order_keys(parcel):
        parcels |= {
            other.id: other
            for other in order_parcels(engine.data, key)
            if viewer.can_see(other)
        }
    first: dict[str, datetime] = {}
    for each in parcels.values():
        for origin in each.origins.values():
            shipment = origin.amazon_shipment_id
            if shipment and (shipment not in first or origin.time < first[shipment]):
                first[shipment] = origin.time
    if len(first) < 2:
        return {}
    ordered = sorted(first, key=lambda shipment: (first[shipment], shipment))
    return {
        shipment: [number, len(ordered)]
        for number, shipment in enumerate(ordered, start=1)
    }


def _sender_name(origin: Origin) -> str | None:
    """Return the name of an e-mail's sender, when Parcels knows it."""
    if origin.message is None or not origin.label:
        return None
    sender = lookup(origin.label)
    return sender.name if sender else None


def _email_parts(parcel: Parcel) -> dict[str, str]:
    """Map each AI fill of a parcel to its e-mail's parser origin, if here.

    Both come from one e-mail, so they're shown and moved together.
    """
    parsed: dict[str, str] = {}
    for origin_id in sorted(parcel.origins):
        origin = parcel.origins[origin_id]
        if origin.message is not None and not origin_id.endswith(FILL_ORIGIN_SUFFIX):
            parsed.setdefault(origin.message, origin_id)
    return {
        origin_id: parsed[origin.message]
        for origin_id, origin in parcel.origins.items()
        if origin_id.endswith(FILL_ORIGIN_SUFFIX)
        and origin.message is not None
        and origin.message in parsed
    }


def origin_rows(
    engine: ParcelsEngine, parcel: Parcel, viewer: Viewer
) -> list[dict[str, Any]]:
    """Return what each e-mail and source of a parcel said and added.

    Oldest first, the user's edits included. Only what's stored is shown:
    never a subject, a body, a pickup code or an Amazon shipment ID. A row
    tells whether it can be moved to a new parcel ("split_blocked" says why
    not) and whether it's an e-mail, which can be removed from Parcels.
    What the local AI filled in for an e-mail is "part_of" that e-mail's
    row: the two move together.
    """
    edits = manual_origin_id(parcel.id)
    shipments = _shipment_numbers(engine, parcel, viewer)
    parts = _email_parts(parcel)
    groups: dict[str, set[str]] = defaultdict(set)
    for origin_id in parcel.origins:
        lead = parts.get(origin_id, origin_id)
        groups[lead].add(origin_id)
    rows = []
    for origin in sorted(parcel.origins.values(), key=lambda o: (o.time, o.id)):
        lead = parts.get(origin.id, origin.id)
        said, estimate = _origin_news(parcel, origin.id)
        eta = estimate.eta if estimate else None
        carrier = origin.carrier or None
        shipment = origin.amazon_shipment_id
        rows.append(
            {
                "id": origin.id,
                "source": origin.source.value,
                "label": origin.label,
                "sender_name": _sender_name(origin),
                "name": origin.name or None,
                "time": dt_to_str(origin.time),
                "status": said.status.value if said and said.status else None,
                "kind": said.kind.value if said and said.kind else None,
                "event_time": dt_to_str(said.time) if said else None,
                "undated": said.undated if said else False,
                "timeless": said.timeless if said else False,
                "dayless": said.dayless if said else False,
                "eta_start": eta.start.isoformat() if eta else None,
                "eta_end": eta.end.isoformat() if eta else None,
                "window_start": time_to_str(eta.window_start) if eta else None,
                "window_end": time_to_str(eta.window_end) if eta else None,
                "carrier": carrier,
                "carrier_name": CARRIER_NAMES.get(carrier, carrier)
                if carrier
                else None,
                "tracking_number": origin.tracking_number or None,
                "reference": origin.reference or None,
                "merchant": origin.merchant or None,
                "seller": origin.seller or None,
                "order_numbers": list(origin.order_numbers),
                "items": list(origin.items),
                "pickup_point": origin.pickup_point or None,
                "shipment": shipments.get(shipment) if shipment else None,
                "email": origin.message is not None,
                "edits": origin.id == edits,
                "part_of": parts.get(origin.id),
                "split_blocked": (
                    None if origin.id == edits else split_problem(parcel, groups[lead])
                ),
            }
        )
    return rows
