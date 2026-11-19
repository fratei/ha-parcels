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
from .customer_returns import INFERRED_RETURN, linked_parcels, order_index
from .dedup import (
    MergeSuggestion,
    first_news,
    is_shop,
    manual_origin_id,
    order_parcels,
    parcel_order_keys,
)
from .models import (
    FilteredItem,
    Parcel,
    ReturnEntry,
    ReviewItem,
    TimelineEntry,
    dt_to_str,
    merchant_key,
    time_to_str,
)
from .parsers.senders import organizational_domain
from .parsers.tracking import tracking_url

if TYPE_CHECKING:
    from .engine import ParcelsEngine

PERSON_DOMAIN = "person"


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
            if origin.message is not None and is_shop(origin.label)
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
    may not see the parcel.
    """
    state = parcel.state
    eta = state.eta
    restricted = not viewer.can_see(parcel)
    result: dict[str, Any] = {
        "id": parcel.id,
        "merchant": state.merchant,
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
        "inferred": state.inferred,
        "inferred_reason": state.inferred_reason,
        "pickup_point": state.pickup_point,
        "pickup_code": state.pickup_code if code else None,
        "has_code": bool(state.pickup_code),
        "order_numbers": list(state.order_numbers),
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
        "restricted": restricted,
    }
    if restricted:
        result.update(
            merchant=None,
            carrier=None,
            carrier_name=None,
            tracking_number=None,
            tracking_url=None,
            pickup_point=None,
            pickup_code=None,
            has_code=False,
            order_numbers=[],
            items=[],
            source="parser",
            ai=False,
            ai_filled=False,
            auto_merged=None,
            inferred=False,
            inferred_reason=None,
            origins=[],
            shipment_group=None,
        )
    return result


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

    An inferred delivery comes from another delivery, or from a return of
    the parcel's order ("inferred_return").
    """
    if not entry.inferred:
        return entry.source.value
    return "inferred_return" if entry.label == INFERRED_RETURN else "inferred"


def details(engine: ParcelsEngine, parcel: Parcel, viewer: Viewer) -> dict[str, Any]:
    """Return a parcel with its timeline, orders and origins.

    Callers check ``viewer.can_see`` first.
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
    origins = [
        {
            "id": origin_id,
            "label": (origin := parcel.origins[origin_id]).label,
            "source": origin.source.value,
            "time": dt_to_str(origin.time),
        }
        for origin_id in splittable_origins(parcel)
    ]
    groups = shipment_groups(
        other for other in data.parcels.values() if viewer.can_see(other)
    )
    return {
        "parcel": parcel_json(
            parcel, viewer, shipment=groups.get(parcel.id), code=True
        ),
        "timeline": timeline,
        "orders": orders,
        "origins": origins,
    }
