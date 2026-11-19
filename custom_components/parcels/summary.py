"""Shared rules for the sensors and the calendar.

The calendar places parcels exactly like the week card
(``frontend/src/placement.ts``), so both show the same days.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import TERMINAL_STATUSES, ParcelStatus
from .models import Parcel, ParcelState, local_date, time_to_str

S = ParcelStatus

IN_TRANSIT_STATUSES = frozenset(
    {S.SHIPPED, S.IN_TRANSIT, S.OUT_FOR_DELIVERY, S.ATTEMPTED, S.EXCEPTION}
)

PRIVATE_TITLE = "Private parcel"
UNNAMED_TITLE = "Parcel"
STATUS_LABELS: dict[ParcelStatus, str] = {
    S.ORDERED: "Ordered",
    S.SHIPPED: "Shipped",
    S.IN_TRANSIT: "In transit",
    S.OUT_FOR_DELIVERY: "Out for delivery",
    S.DELIVERED: "Delivered",
    S.ATTEMPTED: "Delivery attempted",
    S.EXCEPTION: "Problem",
    S.READY_FOR_PICKUP: "Ready for pickup",
    S.RETURNED: "Returned to sender",
    S.CANCELLED: "Cancelled",
}

KIND_DELIVERED = "delivered"
KIND_RETURNED = "returned"
KIND_PICKUP = "pickup"
KIND_STATUS = "status"
KIND_ETA = "eta"


def _status_day(state: ParcelState) -> date | None:
    return local_date(state.status_time) if state.status_time is not None else None


def arriving_today(state: ParcelState, today: date) -> bool:
    """Return True for an undelivered parcel expected today.

    Like the notifier, a parcel is expected on the last day of its estimate;
    parcels out for delivery since today count too. Parcels waiting at a
    pickup point don't arrive anywhere.
    """
    if state.status in TERMINAL_STATUSES or state.status is S.READY_FOR_PICKUP:
        return False
    if state.eta is not None and state.eta.end == today:
        return True
    return state.status is S.OUT_FOR_DELIVERY and _status_day(state) == today


def in_transit(state: ParcelState) -> bool:
    """Return True for a parcel on its way."""
    return state.status in IN_TRANSIT_STATUSES


def ready_for_pickup(state: ParcelState) -> bool:
    """Return True for a parcel waiting at a pickup point."""
    return state.status is S.READY_FOR_PICKUP


def delivered_today(state: ParcelState, today: date) -> bool:
    """Return True for a parcel delivered today, in Home Assistant's time zone."""
    if state.status is not S.DELIVERED:
        return False
    delivered = state.delivered_at or state.status_time
    return delivered is not None and local_date(delivered) == today


def today() -> date:
    """Return today in Home Assistant's time zone."""
    return dt_util.now().date()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


def carrier_label(state: ParcelState) -> str | None:
    """Return the carrier's name, or None when it's unknown."""
    if not state.carrier or state.carrier == "other":
        return None
    return _clean(state.carrier_name)


def parcel_title(parcel: Parcel) -> str:
    """Return the name of a parcel: never item names, nothing for private ones."""
    if parcel.private:
        return PRIVATE_TITLE
    state = parcel.state
    return (
        _clean(state.merchant)
        or carrier_label(state)
        or _clean(state.tracking_number)
        or UNNAMED_TITLE
    )


def parcel_attributes(parcel: Parcel) -> dict[str, Any]:
    """Return what a sensor attribute shows of a parcel: no item names."""
    state = parcel.state
    eta = state.eta
    data: dict[str, Any] = {
        "id": parcel.id,
        "status": state.status.value,
        "eta_start": eta.start.isoformat() if eta else None,
        "eta_end": eta.end.isoformat() if eta else None,
        "window_start": time_to_str(eta.window_start) if eta else None,
        "window_end": time_to_str(eta.window_end) if eta else None,
    }
    if parcel.private:
        data["private"] = True
    else:
        data["merchant"] = state.merchant
        data["carrier"] = carrier_label(state)
        data["tracking_number"] = state.tracking_number
    return data


@dataclass(frozen=True, slots=True)
class Placement:
    """The inclusive range of local days on which a parcel shows."""

    kind: str
    first: date
    last: date


def placement(parcel: Parcel, today: date) -> Placement | None:
    """Return the days a parcel covers in the calendar, or None.

    - delivered: the local day of the delivery;
    - returned: its status day;
    - cancelled: hidden;
    - ready for pickup: from its status day to today;
    - anything else with an estimate: the estimate;
    - attempted or exception without an estimate: its status day;
    - no estimate: not in the calendar.
    """
    state = parcel.state
    status_day = _status_day(state)
    status = state.status
    if status is S.CANCELLED:
        return None
    if status is S.DELIVERED:
        delivered = state.delivered_at or state.status_time
        day = local_date(delivered) if delivered is not None else None
        return Placement(KIND_DELIVERED, day, day) if day else None
    if status is S.RETURNED:
        return Placement(KIND_RETURNED, status_day, status_day) if status_day else None
    if status is S.READY_FOR_PICKUP:
        first = status_day or today
        return Placement(KIND_PICKUP, first, max(first, today))
    if state.eta is not None:
        return Placement(KIND_ETA, state.eta.start, max(state.eta.start, state.eta.end))
    if status in (S.ATTEMPTED, S.EXCEPTION) and status_day:
        return Placement(KIND_STATUS, status_day, status_day)
    return None


def count(parcels: Iterable[Parcel], rule: Any, *args: Any) -> list[Parcel]:
    """Return the parcels whose state matches a rule, newest change first."""
    matched = [parcel for parcel in parcels if rule(parcel.state, *args)]
    matched.sort(
        key=lambda p: p.state.status_time or datetime.min.replace(tzinfo=dt_util.UTC),
        reverse=True,
    )
    return matched


def window_bounds(parcel: Parcel, place: Placement) -> tuple[datetime, datetime] | None:
    """Return the local delivery window of a one-day estimate, or None."""
    eta = parcel.state.eta
    if (
        place.kind != KIND_ETA
        or eta is None
        or place.first != place.last
        or eta.window_start is None
        or eta.window_end is None
        or eta.window_end <= eta.window_start
    ):
        return None
    tz = dt_util.get_default_time_zone()
    return (
        datetime.combine(place.first, eta.window_start, tzinfo=tz),
        datetime.combine(place.first, eta.window_end, tzinfo=tz),
    )


def day_after(day: date) -> date:
    """Return the next day (all-day calendar events end exclusively)."""
    return day + timedelta(days=1)
