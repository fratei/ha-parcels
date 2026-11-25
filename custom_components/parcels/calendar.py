"""The Parcels calendar: one event per parcel, on the days the week card shows it.

Late parcels are the exception: the week card carries them into today, while
the calendar keeps them on the days they were expected.

A customer return is an all-day event on its pickup day.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import summary
from .const import CARRIER_NAMES, ParcelStatus
from .customer_returns import linked_parcels, order_index
from .engine import ParcelsEngine
from .entity import ParcelsEntity
from .models import Parcel, PickupRule, ReturnEntry

PARALLEL_UPDATES = 0

DELIVERED_MARK = "✓"
PRIVATE_RETURN_TITLE = "Private return"
RETURN_PICKUP_LINES: dict[PickupRule, str] = {
    PickupRule.EMAIL: "Pickup day from the shop's e-mail",
    PickupRule.NEXT_WORKING_DAY: "Picked up the working day after the shop's e-mail",
    PickupRule.ASSUMED: (
        "Pickup day assumed: the shop's carrier usually comes"
        " the working day after its e-mail"
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the calendar of the hub."""
    engine: ParcelsEngine = entry.runtime_data
    async_add_entities([ParcelsCalendar(engine)])


def parcel_event(parcel: Parcel, today: date) -> CalendarEvent | None:
    """Return the calendar event of a parcel, or None when it has no days."""
    place = summary.placement(parcel, today)
    if place is None:
        return None
    state = parcel.state
    title = summary.parcel_title(parcel)
    if state.status is ParcelStatus.DELIVERED:
        title = f"{title} {DELIVERED_MARK}"
    lines = [summary.STATUS_LABELS[state.status]]
    location = None
    if not parcel.private:
        if carrier := summary.carrier_label(state):
            lines.append(f"Carrier: {carrier}")
        if state.tracking_number:
            lines.append(f"Tracking number: {state.tracking_number}")
        location = state.pickup_point or None
    if bounds := summary.window_bounds(parcel, place):
        start, end = bounds
        return CalendarEvent(
            start=start,
            end=end,
            summary=title,
            description="\n".join(lines),
            location=location,
            uid=parcel.id,
        )
    return CalendarEvent(
        start=place.first,
        end=summary.day_after(place.last),
        summary=title,
        description="\n".join(lines),
        location=location,
        uid=parcel.id,
    )


def _return_carrier(entry: ReturnEntry) -> str | None:
    carrier = entry.carrier
    if not carrier or carrier == "other":
        return None
    return CARRIER_NAMES.get(carrier, carrier)


def return_event(
    entry: ReturnEntry, linked: Iterable[Parcel], today: date
) -> CalendarEvent:
    """Return the all-day event of a customer return, on its pickup day.

    ``linked`` are the parcels of its orders: a private one makes the return
    private too. It's marked done once its day is over, someone marked it
    picked up or the shop has it.
    """
    private = entry.private or any(parcel.private for parcel in linked)
    pickup = entry.pickup
    carrier = _return_carrier(entry)
    if private:
        title = PRIVATE_RETURN_TITLE
    else:
        name = entry.merchant or carrier or summary.UNNAMED_TITLE
        title = f"Return pickup: {name}" if pickup else f"Return: {name}"
    if entry.done(today):
        title = f"{title} {DELIVERED_MARK}"
    lines = ["Received by the shop" if entry.received else "Return to the shop"]
    if pickup is not None:
        lines.append(RETURN_PICKUP_LINES[pickup[1]])
    if not private:
        if carrier:
            lines.append(f"Carrier: {carrier}")
        if entry.tracking_number:
            lines.append(f"Tracking number: {entry.tracking_number}")
    return CalendarEvent(
        start=entry.day,
        end=summary.day_after(entry.day),
        summary=title,
        description="\n".join(lines),
        uid=entry.id,
    )


class ParcelsCalendar(ParcelsEntity, CalendarEntity):
    """Deliveries by day: expected, waiting for pickup, delivered and returned,
    and the pickups of customer returns.

    Archived parcels and returns stay, so past weeks keep their deliveries.
    """

    _attr_name = None

    def __init__(self, engine: ParcelsEngine) -> None:
        """Initialise the calendar."""
        super().__init__(engine, "parcels")
        self._events: list[CalendarEvent] = []

    @callback
    def _async_compute(self) -> None:
        today = summary.today()
        data = self.engine.data
        events = [
            event
            for parcel in data.parcels.values()
            if (event := parcel_event(parcel, today)) is not None
        ]
        if data.returns:
            index = order_index(data)
            events.extend(
                return_event(entry, linked_parcels(entry, index), today)
                for entry in data.returns.values()
            )
        events.sort(key=lambda e: (e.start_datetime_local, e.summary, e.uid or ""))
        self._events = events

    async def async_added_to_hass(self) -> None:
        """Place the parcels before the first state is written."""
        self._async_compute()
        await super().async_added_to_hass()

    @callback
    def _async_data_updated(self) -> None:
        self._async_compute()
        super()._async_data_updated()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next event."""
        now = dt_util.now()
        return next((e for e in self._events if e.end_datetime_local > now), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events that overlap a range."""
        return [
            event
            for event in self._events
            if event.start_datetime_local < end_date
            and event.end_datetime_local > start_date
        ]
