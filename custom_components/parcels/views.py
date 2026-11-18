"""The JSON that the Parcels page reads, and who may see what.

A private parcel is shown in full to its owners (the people whose mailboxes
it came from), or to administrators when it has no owner. Everyone else sees
when it arrives, but not what it is or where it comes from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import CONF_DASHBOARD_PATH, CONF_SEVENTEENTRACK
from .dedup import (
    MergeSuggestion,
    manual_origin_id,
    order_parcels,
    parcel_order_keys,
)
from .models import (
    FilteredItem,
    Parcel,
    ReviewItem,
    dt_to_str,
    time_to_str,
)

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


def parcel_json(parcel: Parcel, viewer: Viewer) -> dict[str, Any]:
    """Return a parcel as the page shows it."""
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
        "pickup_point": state.pickup_point,
        "pickup_code": state.pickup_code,
        "order_numbers": list(state.order_numbers),
        "items": list(state.items),
        "private": parcel.private,
        "owners": list(state.owners),
        "source": state.source.value,
        "ai": state.ai,
        "auto_merged": parcel.auto_merged.as_dict() if parcel.auto_merged else None,
        "provisional": state.provisional,
        "archived": parcel.archived is not None,
        "origins": splittable_origins(parcel),
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
            order_numbers=[],
            items=[],
            source="parser",
            ai=False,
            auto_merged=None,
            inferred=False,
            origins=[],
        )
    return result


def mailbox_owner(hass: HomeAssistant, item: ReviewItem) -> str | None:
    """Return whose mailbox an e-mail came from."""
    if item.owner and (state := hass.states.get(item.owner)) is not None:
        return state.name
    if item.mailbox and (entry := hass.config_entries.async_get_entry(item.mailbox)):
        return entry.title
    return None


def review_json(hass: HomeAssistant, item: ReviewItem) -> dict[str, Any]:
    """Return an e-mail under "Needs review"."""
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
    """Return the settings the page needs."""
    options = engine.options
    return {
        "user_is_admin": viewer.is_admin,
        "ai_enabled": engine.ai_active,
        "ai_mode": engine.ai_mode.value,
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
        review = [
            review_json(hass, item)
            for item in _newest_first(list(data.review.values()))
        ]
        filtered = [
            filtered_json(item) for item in _newest_first(list(data.filtered.values()))
        ]
    return {
        "parcels": [parcel_json(parcel, viewer) for parcel in data.parcels.values()],
        "review": review,
        "merge_suggestions": suggestions,
        "filtered": filtered,
        "settings": settings_json(engine, viewer),
    }


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
            "source": "inferred" if entry.inferred else entry.source.value,
            "label": entry.label or "",
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
    return {
        "parcel": parcel_json(parcel, viewer),
        "timeline": timeline,
        "orders": orders,
        "origins": origins,
    }
