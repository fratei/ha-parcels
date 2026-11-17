"""The Parcels calendar: one event per parcel, on the days the week card shows it."""

from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import summary
from .const import ParcelStatus
from .engine import ParcelsEngine
from .entity import ParcelsEntity
from .models import Parcel

PARALLEL_UPDATES = 0

DELIVERED_MARK = "✓"


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


class ParcelsCalendar(ParcelsEntity, CalendarEntity):
    """Deliveries by day: expected, waiting for pickup, delivered and returned.

    Archived parcels stay, so past weeks keep their deliveries.
    """

    _attr_name = None

    def __init__(self, engine: ParcelsEngine) -> None:
        """Initialise the calendar."""
        super().__init__(engine, "parcels")
        self._events: list[CalendarEvent] = []

    @callback
    def _async_compute(self) -> None:
        today = summary.today()
        events = [
            event
            for parcel in self.engine.data.parcels.values()
            if (event := parcel_event(parcel, today)) is not None
        ]
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
