"""Deliveries from the Parcel app (parcelapp.net), for Premium accounts.

Off until the user enters the API key he generated at web.parcelapp.net. The
key goes in the ``api-key`` header of requests to api.parcel.app, and only
there. Each read, at most every ten minutes because Parcel allows 20 an hour,
which other tools using the key may share:

- matches the deliveries in his list to parcels by tracking number and turns
  their status and events into events of the parcel; their expected date fills
  a missing date or window, and the newer news wins;
- follows each shipment of an Amazon order, which Parcel lists by the order
  number with the shipment ID as extra information: it joins the parcel with
  that shipment, else its order's parcel when which one is clear;
- follows Parcel when it switches an Amazon delivery to the carrier's number:
  the order's delivery leaves the list and the carrier's arrives with the
  same description. The carrier's delivery joins the order's parcel, flagged
  so the user can undo it (see ``_switched_target``);
- shows the deliveries that are only in Parcel as parcels, named after their
  description, unless the user turned that off;
- learns the carrier code Parcel gave each carrier in the deliveries he added;
- adds the numbers of new parcels to his list, soonest due first and at most
  ``parcel_app_daily`` a day (Parcel accepts 20, failures included), with the
  merchant's name as description: never items, and never private parcels.

Parcel answers reads from its cache, so reading doesn't make it ask the
carrier; it updates the deliveries on its own.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Iterator, Mapping
from datetime import date, datetime, timedelta, tzinfo
import hashlib
import json
import logging
import re
from typing import TYPE_CHECKING, Any, Final, NamedTuple

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from ..const import (
    CARRIER_NAMES,
    CONF_ENTRY_TYPE,
    CONF_OWNER,
    CONF_PARCEL_APP_ADD,
    CONF_PARCEL_APP_DAILY,
    CONF_PARCEL_APP_EVERYONE,
    CONF_PARCEL_APP_IMPORT,
    CONF_PARCEL_APP_KEY,
    CONF_PARCEL_APP_OWNER,
    CONF_PARCEL_APP_POSTCODE,
    DEFAULT_PARCEL_APP_ADD,
    DEFAULT_PARCEL_APP_DAILY,
    DEFAULT_PARCEL_APP_EVERYONE,
    DEFAULT_PARCEL_APP_IMPORT,
    DOMAIN,
    ENTRY_TYPE_MAILBOX,
    ISSUE_PARCEL_APP_KEY,
    MAX_PARCEL_APP_DAILY,
    ParcelStatus,
)
from ..dedup import (
    REASON_PARCEL_SWITCH,
    Contribution,
    apply_contribution,
    carrier_family,
    find_parcels_by_number,
    flag_switch,
    hold_guess,
    join_switched,
    kept_apart_from,
    may_guess_into,
    number_key_text,
    order_parcels,
    origin_order_keys,
    remove_origins,
    shipment_parcels,
    switch_target_open,
)
from ..models import (
    PARCELAPP_PREFIX,
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    ParcelState,
    Source,
    dt_from_str,
    dt_to_str,
    eta_from_dict,
    eta_to_dict,
    is_generic_title,
    known_merchant_name,
    order_key,
)
from ..parsers.base import Eta
from ..parsers.details import tracker_details
from ..parsers.tracking import normalize_tracking_number, validate_tracking_number
from ..quiet import is_quiet
from ..seventeentrack import add_order, clip_text, refine_status
from .api import (
    ErrorKind,
    ParcelAppError,
    async_add_delivery,
    async_get_deliveries,
    normalize_postcode,
    valid_key,
)
from .carriers import (
    NEEDS_POSTCODE,
    UNUSABLE,
    amazon_code,
    amazon_store,
    normalize_code,
    parcel_code,
    parcel_codes,
    parcels_carrier,
)
from .dates import date_shape, is_future_date, parse_expected, read_event_date

if TYPE_CHECKING:
    from ..engine import ParcelsEngine

_LOGGER = logging.getLogger(__name__)

ORIGIN_LABEL: Final = "Parcel app"
FALLBACK_DESCRIPTION: Final = "Parcels"
INTERVAL: Final = timedelta(minutes=15)
# On delivery day Parcel's server updates more often.
BUSY_INTERVAL: Final = timedelta(minutes=10)
# The least time between two reads, restarts and the refresh action included.
MIN_INTERVAL: Final = timedelta(minutes=10)
START_DELAY: Final = timedelta(seconds=60)
RECONFIGURE_DELAY: Final = timedelta(seconds=5)
RATE_BACKOFF: Final = timedelta(hours=1)
MAX_BACKOFF: Final = timedelta(hours=24)
ERROR_BACKOFF: Final = (
    timedelta(minutes=15),
    timedelta(minutes=30),
    timedelta(hours=1),
    timedelta(hours=2),
)
KEY_BACKOFF: Final = timedelta(hours=6)
TASK_NAME: Final = "parcels parcel app refresh"
# Events of a delivery kept, newest first.
MAX_HISTORY: Final = 10
# The diagnostics show this many shapes of event dates Parcels couldn't read.
MAX_DATE_SHAPES: Final = 10
# Set once, as the store loads, when the stored history was checked: 0.1.6
# gave an event without a date the time of the read that found it. Then it
# holds how many deliveries and parcels the check changed.
DATES_REPAIR_KEY: Final = "parcel_app_dates"
# Good reads without a delivery before the parcel made of it goes.
MISSING_READS: Final = 2
# A delivery not seen for this long is forgotten.
RECORD_DAYS: Final = timedelta(days=30)
# When Parcel switches an Amazon delivery to the carrier's number, the most
# time between the last read listing the order's delivery and the first
# listing the carrier's.
SWITCH_WINDOW: Final = timedelta(days=3)
LEARN_MAX: Final = 200
LEARN_DAYS: Final = timedelta(days=365)
MAX_DESCRIPTION: Final = 100
MIN_NUMBER: Final = 5
MAX_NUMBER: Final = 40
NOT_FOUND: Final = 5
# Parcel's status codes. 1 (frozen: no news for a long time) and 5 (not found)
# don't say where the parcel is.
STATUSES: Final[dict[int, ParcelStatus]] = {
    0: ParcelStatus.DELIVERED,
    2: ParcelStatus.IN_TRANSIT,
    3: ParcelStatus.READY_FOR_PICKUP,
    4: ParcelStatus.OUT_FOR_DELIVERY,
    6: ParcelStatus.ATTEMPTED,
    7: ParcelStatus.EXCEPTION,
    8: ParcelStatus.SHIPPED,
}
_KEY_RE: Final = re.compile(r"[!-~]+")
_AMAZON_ORDER_RE: Final = re.compile(r"\d{3}-\d{7}-\d{7}")
# Origins whose carrier says how Parcel names it.
_LEARN_SOURCES: Final = frozenset({Source.PARSER, Source.AI})
_MATCHED: Final = "matched"
_IMPORTED: Final = "imported"
_UNMATCHED: Final = "unmatched"
# How each Amazon delivery found its parcel, for the diagnostics.
_AMAZON_COUNTS: Final = ("by_shipment_id", "by_order", "imported", "other", "unmatched")
# Between an order number and a shipment ID in the key of a delivery.
SHIPMENT_SEPARATOR: Final = "#"


class _Entry(NamedTuple):
    """A delivery of the user's list Parcels can follow."""

    delivery: dict[str, Any]
    number: str
    code: str | None
    # Amazon's order number, and its shipment when Parcel gives it.
    order: str | None
    shipment: str | None


def _fingerprint(key: str) -> str:
    """Return a short hash that tells keys apart without keeping them."""
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def _compared(key: str) -> str:
    """Return a number as compared with the user's list, where case doesn't count."""
    return number_key_text(key).upper()


def _count(value: Any) -> int:
    """Return a stored count, or 0 when it isn't one."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def status_code(value: Any) -> int | None:
    """Return a delivery's status code, or None when it isn't one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        # isdigit() alone also accepts "²" and other scripts' digits.
        text = value.strip()
        return int(text) if text.isascii() and text.isdigit() else None
    return None


def delivery_key(value: Any) -> str | None:
    """Return a delivery's tracking number as Parcels keeps it, or None."""
    if not isinstance(value, str | int) or isinstance(value, bool):
        return None
    key = normalize_tracking_number(str(value).strip())
    if not MIN_NUMBER <= len(key) <= MAX_NUMBER or not _KEY_RE.fullmatch(key):
        return None
    return key


def order_number(raw: Any, key: str, code: str | None) -> str | None:
    """Return the Amazon order number a delivery stands for, as 3-7-7.

    Parcel follows Amazon orders by their order number.
    """
    if len(key) != 17 or not key.isdigit():
        return None
    if not _AMAZON_ORDER_RE.fullmatch(str(raw).strip()) and not amazon_store(code):
        return None
    return f"{key[:3]}-{key[3:10]}-{key[10:]}"


def shipment_id(value: Any) -> str | None:
    """Return the Amazon shipment ID an order's delivery gives, or None.

    Parcel gives it as the delivery's extra information, as Amazon writes it.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not MIN_NUMBER <= len(text) <= MAX_NUMBER or not _KEY_RE.fullmatch(text):
        return None
    return text


def _entries(deliveries: list[Any]) -> list[_Entry]:
    """Return the deliveries with a number Parcels can follow."""
    entries: list[_Entry] = []
    for delivery in deliveries:
        if not isinstance(delivery, dict):
            continue
        raw = delivery.get("tracking_number")
        if (number := delivery_key(raw)) is None:
            continue
        code = normalize_code(delivery.get("carrier_code"))
        order = order_number(raw, number, code)
        shipment = (
            shipment_id(delivery.get("extra_information"))
            if order is not None
            else None
        )
        entries.append(_Entry(delivery, number, code, order, shipment))
    return entries


def _description(delivery: Mapping[str, Any]) -> str | None:
    """Return a delivery's description as Parcels keeps it, or None."""
    description = clip_text(delivery.get("description"))
    if description is None:
        return None
    return description[:MAX_DESCRIPTION].rstrip() or None


def _record_shipment(record: Mapping[str, Any]) -> str | None:
    """Return the shipment a delivery Parcels keeps is, if known."""
    shipment = record.get("shipment")
    return shipment if isinstance(shipment, str) and shipment else None


def _own_shipments(parcel: Parcel) -> set[str]:
    """Return the Amazon shipments a parcel's own news names.

    Its e-mails, mostly: Parcel's deliveries don't count.
    """
    return {
        origin.amazon_shipment_id
        for oid, origin in parcel.origins.items()
        if not oid.startswith(PARCELAPP_PREFIX) and origin.amazon_shipment_id
    }


def removable(parcel: Parcel) -> bool:
    """Return True for a parcel made only of Parcel app deliveries.

    The user's own edits of it don't count: they go with it.
    """
    return any(oid.startswith(PARCELAPP_PREFIX) for oid in parcel.origins) and all(
        oid.startswith(PARCELAPP_PREFIX) or origin.source is Source.MANUAL
        for oid, origin in parcel.origins.items()
    )


def _open_at(parcel: Parcel, time: datetime) -> bool:
    """Return True when a parcel was still open at ``time``.

    Not archived nor finished before it. A parcel finished with no time for
    its status counts as open: it may have finished since.
    """
    if parcel.archived is not None and parcel.archived < time:
        return False
    state = parcel.state
    return not (
        state.terminal and state.status_time is not None and state.status_time < time
    )


def _manual_number(parcel: Parcel) -> str | None:
    """Return the number the user typed for a parcel, "" when he cleared it."""
    typed = [
        origin
        for origin in parcel.origins.values()
        if origin.source is Source.MANUAL and origin.tracking_number is not None
    ]
    if not typed:
        return None
    return max(typed, key=lambda origin: origin.time).tracking_number


def _corrected(parcel: Parcel, key: str) -> bool:
    """Return True when the user gave a parcel another number than this one."""
    number = _manual_number(parcel)
    return number is not None and (
        not number or number_key_text(number) != number_key_text(key)
    )


def _without(parcel: Parcel | None, oid: str) -> Parcel | None:
    """Return a copy of a parcel without an origin, or None when none's left."""
    if parcel is None:
        return None
    origins = {key: value for key, value in parcel.origins.items() if key != oid}
    if not origins:
        return None
    return Parcel(
        id=parcel.id,
        created=parcel.created,
        updated=parcel.updated,
        origins=origins,
        events=[event for event in parcel.events if event.origin != oid],
        private=parcel.private,
        archived=parcel.archived,
        delivery_rejected=parcel.delivery_rejected,
    )


def _latest_eta_time(parcel: Parcel) -> datetime | None:
    """Return when a parcel last heard about its delivery date."""
    return max(
        (
            event.time
            for event in parcel.events
            if event.eta is not None
            or event.clears_eta
            or event.status is ParcelStatus.OUT_FOR_DELIVERY
        ),
        default=None,
    )


def _has_window(eta: Any) -> bool:
    return eta.window_start is not None or eta.window_end is not None


def _event_text(item: Mapping[str, Any]) -> str | None:
    """Return an event's text and place on one line; never its details."""
    parts = [
        text
        for name in ("event", "location")
        if isinstance(value := item.get(name), str) and (text := value.strip())
    ]
    return clip_text(", ".join(parts))


def _stored_status(value: Any) -> ParcelStatus | None:
    try:
        return ParcelStatus(value) if value else None
    except ValueError:
        return None


def _digest(origin: Origin, events: list[ParcelEvent]) -> str:
    """Return a hash of what a delivery says, to apply it only when it changed."""
    payload = {
        "origin": origin.as_dict(),
        "events": [
            {name: value for name, value in event.as_dict().items() if name != "id"}
            for event in events
        ],
    }
    text = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def _known_times(
    base: Parcel | None,
    base_state: ParcelState | None,
    expected: Eta | None,
    tz: tzinfo,
) -> list[datetime]:
    """Return the times a parcel's other news dates, to place undated events.

    The dated statuses of its other sources, and the start of its expected
    days in Home Assistant's time zone: Parcel's, else the parcel's.
    """
    times = [
        event.time
        for event in (base.events if base is not None else ())
        if event.status is not None and not event.inferred and not event.undated
    ]
    eta = expected or (base_state.eta if base_state is not None else None)
    if eta is not None:
        times.extend(_day_start(day, tz) for day in (eta.start, eta.end))
    return times


def _day_start(day: date, tz: tzinfo) -> datetime:
    """Return when a day starts in Home Assistant's time zone, in UTC."""
    return dt_util.as_utc(datetime(day.year, day.month, day.day, tzinfo=tz))


def _stored_day(entry: Mapping[str, Any]) -> date | None:
    """Return the day of a stored event that gave no time, if it gave one."""
    value = entry.get("day")
    if entry.get("at") is not None or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _history_events(
    history: list[dict[str, Any]],
    known: list[datetime],
    now: datetime,
    tz: tzinfo,
) -> list[ParcelEvent]:
    """Return a delivery's stored events, newest first, as its parcel's events.

    An event without a date never takes the time it was read at, which can
    be days after it happened. It goes just after the latest time known to
    come before it: an older event, or a time of ``known``, no later than
    when it was first seen with its status, nor than a newer event. With
    none, its day isn't known either. An event that gave only its day stays
    on that day: just after the latest such time on it, else at its start.
    """
    times = [dt_from_str(entry.get("at")) for entry in history]
    days = [_stored_day(entry) for entry in history]
    # The earliest each event can have happened.
    floors = [
        time if time is not None else _day_start(day, tz) if day is not None else None
        for time, day in zip(times, days, strict=True)
    ]
    events: list[ParcelEvent] = []
    bound: datetime | None = None
    for index, entry in enumerate(history):
        when = times[index]
        day = days[index]
        undated = dayless = timeless = False
        limit: datetime | None = None
        offset = timedelta(microseconds=MAX_HISTORY - index)
        if when is not None:
            bound = when if bound is None else min(bound, when)
        elif day is not None:
            start = floors[index] or _day_start(day, tz)
            end = _day_start(day + timedelta(days=1), tz) - timedelta(microseconds=1)
            seen = dt_from_str(entry.get("seen")) or now
            limit = min(end, seen) if bound is None else min(end, seen, bound)
            limit = max(start, limit)
            bound = limit if bound is None else min(bound, limit)
            before = [
                value
                for value in (*known, *floors[index + 1 :])
                if value is not None and start <= value <= limit
            ]
            undated = timeless = True
            when = min(max(before) + offset, end) if before else start + offset
        else:
            seen = dt_from_str(entry.get("seen")) or now
            limit = seen if bound is None else min(bound, seen)
            bound = limit
            before = [
                value
                for value in (*known, *floors[index + 1 :])
                if value is not None and value <= limit
            ]
            undated = True
            if before:
                # Newer events go after older ones, on the same day.
                when = max(before) + offset
            else:
                when = limit - timedelta(microseconds=index)
                dayless = True
        status = _stored_status(entry.get("status"))
        info = entry.get("info")
        label = info if isinstance(info, str) and info else None
        # Days in its text are read only when the event's own day is known.
        reference = when if times[index] is not None or day is not None else None
        if status is not None or label is not None:
            events.append(
                ParcelEvent(
                    time=when,
                    source=Source.PARCELAPP,
                    status=status,
                    label=label,
                    undated=undated,
                    dayless=dayless,
                    by=limit,
                    timeless=timeless,
                    **tracker_details(label, status, reference, tz),
                )
            )
    return events


def _common(shapes: Counter[str]) -> dict[str, int]:
    """Return the most common shapes, most common first."""
    ranked = sorted(shapes.items(), key=lambda pair: (-pair[1], pair[0]))
    return dict(ranked[:MAX_DATE_SHAPES])


def _date_stats(
    deliveries: list[dict[str, Any]], now: datetime, tz: tzinfo
) -> dict[str, Any]:
    """Count the event dates of a read Parcels couldn't use, and their shapes.

    Apart from those, the dates read without their time, and the shapes of
    those read with a part of the day or a time zone after the time. A shape
    keeps only the date words and the layout, see ``date_shape``.
    """
    unparsed = future = day_only = 0
    shapes: Counter[str] = Counter()
    day_shapes: Counter[str] = Counter()
    marked: Counter[str] = Counter()
    for delivery in deliveries:
        if not isinstance(delivery, dict) or not isinstance(
            events := delivery.get("events"), list
        ):
            continue
        for item in events:
            if not isinstance(item, Mapping):
                continue
            value = item.get("date")
            if (found := read_event_date(value, now, tz)) is not None:
                if found.at is None:
                    day_only += 1
                    day_shapes[date_shape(value)] += 1
                elif found.marks:
                    marked[date_shape(value)] += 1
                continue
            if is_future_date(value, now, tz):
                future += 1
                continue
            unparsed += 1
            shapes[date_shape(value) if "date" in item else "missing"] += 1
    return {
        "unparsed": unparsed,
        "future": future,
        "shapes": _common(shapes),
        "day_only": day_only,
        "day_only_shapes": _common(day_shapes),
        "marked": _common(marked),
    }


def repair_parcel_dates(data: ParcelsData, now: datetime, tz: tzinfo) -> int:
    """Take away the read times 0.1.6 gave Parcel's events without a date.

    Such an event keeps that time only as when it was first seen, and the
    events of its delivery are placed again, as ``_history_events`` does.
    Returns how many parcels changed.
    """
    records = data.parcelapp.get("records")
    if not isinstance(records, dict):
        return 0
    changed = 0
    for key, record in records.items():
        if not isinstance(record, dict) or not isinstance(
            stored := record.get("history"), list
        ):
            continue
        history: list[dict[str, Any]] = []
        undated = False
        for item in stored:
            if not isinstance(item, dict):
                continue
            entry = {name: value for name, value in item.items() if name != "time"}
            if item.get("at") is None and "time" in item:
                undated = True
                entry.setdefault("seen", item["time"])
            history.append(entry)
        record["history"] = history
        if not undated:
            continue
        record.pop("fp", None)
        oid = PARCELAPP_PREFIX + str(key)
        holder = next(
            (parcel for parcel in data.parcels.values() if oid in parcel.origins),
            None,
        )
        if holder is None:
            continue
        base = _without(holder, oid)
        eta = record.get("eta")
        expected = eta_from_dict(eta.get("value")) if isinstance(eta, dict) else None
        events = _history_events(
            history,
            _known_times(base, base.state if base is not None else None, expected, tz),
            now,
            tz,
        )
        for event in events:
            event.origin = oid
        # Its expected date is dated when Parcel first gave it: it stays.
        kept = [
            event
            for event in holder.events
            if event.origin == oid and (event.eta is not None or event.clears_eta)
        ]
        holder.events = [
            *(event for event in holder.events if event.origin != oid),
            *events,
            *kept,
        ]
        origin = holder.origins[oid]
        since = dt_from_str(record.get("since")) or origin.time
        origin.time = min([event.time for event in (*events, *kept)] + [since])
        holder.touch(now)
        changed += 1
    return changed


class ParcelAppSync:
    """Keeps the parcels in step with the user's list in the Parcel app."""

    def __init__(self, engine: ParcelsEngine) -> None:
        """Initialise the sync of the hub's engine."""
        self.engine = engine
        self.hass = engine.hass
        self._lock = asyncio.Lock()
        self._unsub: CALLBACK_TYPE | None = None
        self._running = False
        self._key_id: str | None = None
        self._snapshot: tuple[Any, ...] | None = None
        self._logged: str | None = None
        self._add_logged: str | None = None
        # The keys of the deliveries in the list, during a read.
        self._present: set[str] = set()
        self.last_refresh: datetime | None = None
        self.last_error: str | None = None

    # -- Options ------------------------------------------------------------

    @property
    def key(self) -> str:
        """Return the API key, or "" when there's none."""
        return str(self.engine.options.get(CONF_PARCEL_APP_KEY) or "")

    @property
    def enabled(self) -> bool:
        """Return True when an API key is set."""
        return valid_key(self.key)

    @property
    def owner(self) -> str | None:
        """Return the person whose key it is, if chosen."""
        return self.engine.options.get(CONF_PARCEL_APP_OWNER) or None

    @property
    def importing(self) -> bool:
        """Return True when deliveries only in Parcel show as parcels."""
        return bool(
            self.engine.options.get(CONF_PARCEL_APP_IMPORT, DEFAULT_PARCEL_APP_IMPORT)
        )

    @property
    def adding(self) -> bool:
        """Return True when new parcels are added to the user's list."""
        return bool(
            self.engine.options.get(CONF_PARCEL_APP_ADD, DEFAULT_PARCEL_APP_ADD)
        )

    @property
    def everyone(self) -> bool:
        """Return True when everyone's parcels are added, not only the owner's."""
        return bool(
            self.engine.options.get(
                CONF_PARCEL_APP_EVERYONE, DEFAULT_PARCEL_APP_EVERYONE
            )
        )

    @property
    def daily(self) -> int:
        """Return how many deliveries may be added a day."""
        try:
            value = int(
                self.engine.options.get(CONF_PARCEL_APP_DAILY, DEFAULT_PARCEL_APP_DAILY)
            )
        except TypeError, ValueError:
            value = DEFAULT_PARCEL_APP_DAILY
        return min(max(value, 0), MAX_PARCEL_APP_DAILY)

    @property
    def postcode(self) -> str | None:
        """Return the delivery postcode, or None when unset or invalid."""
        value = self.engine.options.get(CONF_PARCEL_APP_POSTCODE)
        if not value:
            return None
        return normalize_postcode(str(value), self.hass.config.country)

    def _options_snapshot(self) -> tuple[Any, ...]:
        return (
            self._key_id,
            self.owner,
            self.importing,
            self.adding,
            self.everyone,
            self.daily,
            self.postcode,
        )

    @property
    def _state(self) -> dict[str, Any]:
        return self.engine.data.parcelapp

    # -- Scheduling ---------------------------------------------------------

    @callback
    def async_start(self) -> None:
        """Start the periodic reads."""
        self._running = True
        self._key_id = _fingerprint(self.key) if self.enabled else None
        self._snapshot = self._options_snapshot()
        if self._key_id is None:
            if self._state:
                self._forget()
            return
        refused = self._state.get("key_refused")
        if refused == self._key_id:
            self._raise_key_issue()
        elif refused is not None:
            # The key changed while Parcels wasn't running.
            self._clear_failures()
        delay = self._due_delay(dt_util.utcnow())
        self._schedule(max(START_DELAY.total_seconds(), delay))

    async def async_stop(self) -> None:
        """Stop the periodic reads."""
        self._running = False
        self._cancel()

    @callback
    def reconfigure(self) -> None:
        """Apply changed options: read soon when the Parcel app's changed."""
        if not self._running:
            return
        key_id = _fingerprint(self.key) if self.enabled else None
        if key_id != self._key_id:
            self._key_id = key_id
            if key_id is None:
                self._cancel()
                self._forget()
                self._snapshot = self._options_snapshot()
                return
            self._clear_failures()
        snapshot = self._options_snapshot()
        moved = snapshot != self._snapshot
        self._snapshot = snapshot
        if (moved or self._unsub is None) and not self._lock.locked():
            delay = self._due_delay(dt_util.utcnow())
            self._schedule(max(RECONFIGURE_DELAY.total_seconds(), delay))

    @callback
    def _cancel(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _schedule(self, delay: float) -> None:
        self._cancel()
        if self._running and self.enabled:
            self._unsub = async_call_later(self.hass, delay, self._async_timer)

    @callback
    def _async_timer(self, _now: datetime) -> None:
        self._unsub = None
        self.engine.async_create_task(self.async_refresh(), TASK_NAME)

    def _due_delay(self, now: datetime) -> float:
        """Return the seconds until the next read is allowed."""
        state = self._state
        due = now
        if (last := dt_from_str(state.get("last_poll"))) is not None:
            due = max(due, min(last, now) + MIN_INTERVAL)
        if (backoff := dt_from_str(state.get("backoff_until"))) is not None:
            due = max(due, min(backoff, now + MAX_BACKOFF))
        return (due - now).total_seconds()

    def _busy(self) -> bool:
        """Return True when a parcel Parcel follows may arrive today."""
        today = dt_util.now().date()
        for parcel in self.engine.data.parcels.values():
            if parcel.archived is not None or not any(
                oid.startswith(PARCELAPP_PREFIX) for oid in parcel.origins
            ):
                continue
            state = parcel.state
            if state.status is ParcelStatus.OUT_FOR_DELIVERY or (
                state.eta is not None
                and not state.terminal
                and state.eta.start <= today <= state.eta.end
            ):
                return True
        return False

    # -- Refresh ------------------------------------------------------------

    async def async_refresh(self) -> None:
        """Read the deliveries, unless the last read was under ten minutes ago."""
        read_ok: bool | None = None
        try:
            async with self._lock:
                now = dt_util.utcnow()
                if self.enabled and self._due_delay(now) <= 0:
                    read_ok = await self._async_sync(now)
        finally:
            delay = self._due_delay(dt_util.utcnow())
            if read_ok:
                interval = BUSY_INTERVAL if self._busy() else INTERVAL
                delay = max(delay, interval.total_seconds())
            self._schedule(delay)

    async def _async_sync(self, now: datetime) -> bool:
        """Read the deliveries, apply them and add the new parcels.

        Returns False when reading failed; nothing is added then.
        """
        state = self._state
        state["last_poll"] = dt_to_str(now)
        self.engine.async_schedule_save()
        try:
            deliveries = await async_get_deliveries(self.hass, self.key)
        except ParcelAppError as err:
            self._read_failed(err, now)
            self.engine.async_schedule_save()
            return False
        self._read_ok()
        changed, listed = self._read(deliveries, now)
        self.last_refresh = now
        if changed:
            self.engine.async_changed()
        else:
            self.engine.async_schedule_save()
        await self._async_add(listed, now)
        return True

    def _read_failed(self, err: ParcelAppError, now: datetime) -> None:
        state = self._state
        if err.kind is ErrorKind.KEY:
            state["key_refused"] = self._key_id
            wait = KEY_BACKOFF
            self._raise_key_issue()
        elif err.kind is ErrorKind.RATE:
            wait = (
                RATE_BACKOFF
                if err.retry_after is None
                else max(timedelta(seconds=err.retry_after), MIN_INTERVAL)
            )
        else:
            errors = _count(state.get("errors")) + 1
            state["errors"] = errors
            wait = ERROR_BACKOFF[min(errors, len(ERROR_BACKOFF)) - 1]
        state["backoff_until"] = dt_to_str(now + min(wait, MAX_BACKOFF))
        self.last_error = err.code
        if err.code != self._logged:
            self._logged = err.code
            _LOGGER.warning(
                "Reading the Parcel app deliveries failed (%s); trying again later",
                err.code,
            )
        else:
            _LOGGER.debug("Reading the Parcel app deliveries failed (%s)", err.code)

    def _read_ok(self) -> None:
        state = self._state
        state.pop("backoff_until", None)
        state.pop("errors", None)
        if state.pop("key_refused", None) is not None:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_PARCEL_APP_KEY)
        self._logged = None
        self.last_error = None

    @callback
    def _clear_failures(self) -> None:
        """Forget the failures of an earlier key."""
        state = self._state
        for name in ("key_refused", "backoff_until", "errors"):
            state.pop(name, None)
        if isinstance(adds := state.get("adds"), dict):
            adds.pop("stopped", None)
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_PARCEL_APP_KEY)
        self._logged = None
        self._add_logged = None
        self.last_error = None

    @callback
    def _raise_key_issue(self) -> None:
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_PARCEL_APP_KEY,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_PARCEL_APP_KEY,
        )

    @callback
    def _forget(self) -> None:
        """Drop what the source kept once its key is cleared.

        The parcels made only of its deliveries go too; what it added to
        parcels from e-mails stays.
        """
        self._clear_failures()
        removed = self._remove_imports(dt_util.utcnow())
        self.engine.data.parcelapp.clear()
        self.last_refresh = None
        if removed:
            self.engine.async_changed()
        else:
            self.engine.async_schedule_save()

    # -- Reading ------------------------------------------------------------

    @property
    def _records(self) -> dict[str, dict[str, Any]]:
        """Return what Parcels knows of each delivery, by its key.

        The key is the delivery's number, but an Amazon order's later
        shipments each have their own: see ``_record_key``.
        """
        records = self._state.get("records")
        if not isinstance(records, dict):
            records = self._state["records"] = {}
        return records

    def _holder(self, oid: str) -> Parcel | None:
        """Return the parcel holding an origin."""
        for parcel in self.engine.data.parcels.values():
            if oid in parcel.origins:
                return parcel
        return None

    def _remove_imports(self, now: datetime) -> bool:
        """Remove the parcels made only of deliveries; return True if any."""
        data = self.engine.data
        gone = [parcel for parcel in data.parcels.values() if removable(parcel)]
        records = self._records
        for parcel in gone:
            for oid in parcel.origins:
                if oid.startswith(PARCELAPP_PREFIX) and (
                    record := records.get(oid.removeprefix(PARCELAPP_PREFIX))
                ):
                    record["held"] = False
                    record.pop("fp", None)
            remove_origins(data, parcel, set(parcel.origins), now)
        return bool(gone)

    def _read(
        self, deliveries: list[dict[str, Any]], now: datetime
    ) -> tuple[bool, set[str]]:
        """Apply the deliveries to the parcels.

        Returns whether a parcel changed, and the numbers in the user's list.
        """
        tz = dt_util.get_default_time_zone()
        records = self._records
        stamp = dt_to_str(now)
        entries = _entries(deliveries)
        changed = self._bind_shipments(entries, now)
        several = Counter(entry.number for entry in entries)
        found: dict[str, _Entry] = {}
        twice: set[str] = set()
        for entry in entries:
            key = self._record_key(entry, several=several[entry.number] > 1)
            if key in found:
                twice.add(key)
            found[key] = entry
        counts: dict[str, Any] = {
            "deliveries": len(deliveries),
            _MATCHED: 0,
            _IMPORTED: 0,
            _UNMATCHED: 0,
        }
        amazon = dict.fromkeys(_AMAZON_COUNTS, 0)
        # Two deliveries with one number: which one to believe is unclear.
        for key in twice:
            if found.pop(key).order is not None:
                amazon["unmatched"] += 1
            if isinstance(record := records.get(key), dict):
                record["seen"] = stamp
                record["missing"] = 0
            counts[_UNMATCHED] += 1
        self._present = set(found) | twice
        changed |= not self.importing and self._remove_imports(now)
        unplaced = self._unplaced(found)
        orders: set[str] = set()
        switched = 0
        for key, entry in found.items():
            record = records.get(key)
            if not isinstance(record, dict):
                record = records[key] = {}
            record.setdefault("since", stamp)
            record["seen"] = stamp
            record["missing"] = 0
            record["code"] = entry.code
            record["status"] = status_code(entry.delivery.get("status_code"))
            if entry.shipment is not None:
                record["shipment"] = entry.shipment
            if entry.order is not None:
                orders.add(key)
            # A delivery without its shipment goes by the order when it's the
            # order's only one, as before Parcel gave shipments.
            alone = entry.order is None or (
                unplaced[entry.order] <= 1
                if entry.shipment is not None
                else several[entry.number] == 1
            )
            moved, outcome = self._read_delivery(key, record, entry, alone, now, tz)
            changed |= moved
            counts[outcome] += 1
            if outcome == _MATCHED and record.get("switch"):
                switched += 1
        changed |= self._missing(set(found) | twice, now)
        self._learn({key: entry.delivery for key, entry in found.items()}, orders, now)
        self._amazon_counts(found, orders, amazon)
        counts["amazon"] = amazon
        counts["switched"] = switched
        self._state["counts"] = counts
        self._state["dates"] = _date_stats(deliveries, now, tz)
        return changed, {entry.number for entry in entries}

    def _record_key(self, entry: _Entry, *, several: bool) -> str:
        """Return the key Parcels keeps a delivery under.

        Its number; but Parcel lists each shipment of an Amazon order under
        the order number. The first shipment Parcels saw keeps the number,
        the others take it with their shipment ID after ``#``.
        """
        number, shipment = entry.number, entry.shipment
        records = self._records
        if shipment is None:
            plain = records.get(number)
            if several and isinstance(plain, dict) and _record_shipment(plain):
                # The number is a shipment's: this one has none yet.
                return f"{number}{SHIPMENT_SEPARATOR}"
            return number
        split = f"{number}{SHIPMENT_SEPARATOR}{shipment}"
        if split in records:
            return split
        plain = records.get(number)
        if isinstance(plain, dict):
            return number if _record_shipment(plain) == shipment else split
        if several:
            return split
        records[number] = {"shipment": shipment}
        return number

    def _bind_shipments(self, entries: list[_Entry], now: datetime) -> bool:
        """Tell the deliveries kept by an order number which shipment they are.

        Before 0.1.13 Parcels kept an order's delivery by the order number
        alone. It becomes the shipment of the order's only delivery in the
        list, or of the parcel holding it. It leaves a parcel that holds
        another shipment, to be placed again, and so does one that can't be
        told. Returns True when a parcel changed.
        """
        records = self._records
        data = self.engine.data
        groups: dict[str, list[str | None]] = {}
        for entry in entries:
            if entry.order is not None:
                groups.setdefault(entry.number, []).append(entry.shipment)
        changed = False
        for number, shipments in groups.items():
            record = records.get(number)
            if (
                not isinstance(record, dict)
                or "shipment" in record
                # It may still be the delivery without one.
                or None in shipments
            ):
                continue
            given = set(shipments)
            oid = PARCELAPP_PREFIX + number
            holder = self._holder(oid)
            if len(shipments) == 1:
                [shipment] = given
                if (
                    _count(record.get("missing")) >= MISSING_READS
                    or f"{number}{SHIPMENT_SEPARATOR}{shipment}" in records
                ):
                    # It left the list: that was another delivery.
                    continue
                record["shipment"] = shipment
                if (
                    holder is not None
                    and holder.archived is None
                    and self._elsewhere(holder, shipment)
                ):
                    remove_origins(data, holder, {oid}, now)
                    record["held"] = False
                    record.pop("fp", None)
                    changed = True
                continue
            if holder is None or holder.archived is not None:
                continue
            named = _own_shipments(holder) & given
            if len(named) == 1:
                record["shipment"] = next(iter(named))
                continue
            remove_origins(data, holder, {oid}, now)
            del records[number]
            changed = True
        return changed

    def _elsewhere(self, holder: Parcel, shipment: str) -> bool:
        """Return True when a shipment's delivery doesn't belong in a parcel.

        The parcel's e-mails name other shipments; or they name none, and
        another parcel has it.
        """
        if own := _own_shipments(holder):
            return shipment not in own
        return any(
            parcel is not holder and parcel.archived is None
            for parcel in shipment_parcels(self.engine.data, shipment)
        )

    def _unplaced(self, found: dict[str, _Entry]) -> Counter[str]:
        """Count the deliveries of each Amazon order no parcel holds yet.

        A delivery without its shipment counts even when held: which of the
        order's shipments it is stays unclear.
        """
        data = self.engine.data
        held = {oid for parcel in data.parcels.values() for oid in parcel.origins}
        shipments = {
            shipment
            for parcel in data.parcels.values()
            for shipment in parcel.state.amazon_shipment_ids
        }
        records = self._records
        tally: Counter[str] = Counter()
        for key, entry in found.items():
            if entry.order is None:
                continue
            record = records.get(key)
            if isinstance(record, dict) and record.get("closed"):
                continue
            if entry.shipment is not None and (
                PARCELAPP_PREFIX + key in held
                or entry.shipment in shipments
                or (isinstance(record, dict) and record.get("held"))
            ):
                continue
            tally[entry.order] += 1
        return tally

    def _amazon_counts(
        self, found: dict[str, _Entry], orders: set[str], amazon: dict[str, int]
    ) -> None:
        """Count how Amazon's deliveries found their parcels.

        By the shipment an e-mail names, by the order, or as a parcel of
        their own.
        """
        for key in orders:
            entry = found[key]
            oid = PARCELAPP_PREFIX + key
            if (parcel := self._holder(oid)) is None:
                amazon["unmatched"] += 1
                continue
            shipment = parcel.origins[oid].amazon_shipment_id
            wanted = order_key("Amazon", entry.order or "")
            others = [
                origin
                for other, origin in parcel.origins.items()
                if not other.startswith(PARCELAPP_PREFIX)
            ]
            if shipment and any(
                origin.amazon_shipment_id == shipment for origin in others
            ):
                amazon["by_shipment_id"] += 1
            elif any(
                wanted in origin_order_keys(origin, parcel.state.merchant)
                for origin in others
            ):
                amazon["by_order"] += 1
            elif removable(parcel):
                amazon["imported"] += 1
            else:
                amazon["other"] += 1

    def _read_delivery(
        self,
        key: str,
        record: dict[str, Any],
        entry: _Entry,
        alone: bool,
        now: datetime,
        tz: tzinfo,
    ) -> tuple[bool, str]:
        """Apply one delivery; return whether a parcel changed, and how it's held.

        ``alone`` is False for a shipment of an order with other deliveries
        no parcel holds: which of them an order's parcel is, is unclear.
        """
        data = self.engine.data
        number, order, shipment = entry.number, entry.order, entry.shipment
        oid = PARCELAPP_PREFIX + key
        if (holder := self._holder(oid)) is not None:
            outcome = _IMPORTED if removable(holder) else _MATCHED
            if holder.archived is not None:
                return False, outcome
            if order is None and _corrected(holder, number):
                # The user said the parcel has another number.
                remove_origins(data, holder, {oid}, now)
                self._close(record)
                return True, _UNMATCHED
            if order is None and self._join_held(key, record, entry, holder, now):
                return self._apply(key, record, entry, now, tz) or True, _MATCHED
            return self._apply(key, record, entry, now, tz), outcome
        if record.get("held"):
            # Its parcel was purged after archiving: don't bring it back.
            self._close(record)
        if record.get("switch"):
            # It left the order's parcel: the user undid the join.
            record["switch"] = ""
        if record.get("closed"):
            return False, _UNMATCHED
        if order is not None:
            if shipment is not None:
                parcels = shipment_parcels(data, shipment)
                active = [parcel for parcel in parcels if parcel.archived is None]
                if len(active) > 1:
                    return False, _UNMATCHED
                if active:
                    applied = self._apply(key, record, entry, now, tz, anchor=active[0])
                    return applied, _MATCHED
                if parcels:
                    return False, _MATCHED
            parcels = order_parcels(data, order_key("Amazon", order))
            if shipment is not None:
                # A parcel of another of the order's shipments isn't this one.
                parcels = [
                    parcel for parcel in parcels if not parcel.state.amazon_shipment_ids
                ]
            active = [parcel for parcel in parcels if parcel.archived is None]
            if len(active) > 1 or (active and not alone):
                # Parcel follows the order as one delivery: which is unclear.
                return False, _UNMATCHED
            if active:
                applied = self._apply(key, record, entry, now, tz, anchor=active[0])
                return applied, _MATCHED
            if parcels:
                return False, _MATCHED if alone else _UNMATCHED
        else:
            matches = find_parcels_by_number(data, number)
            active = [parcel for parcel in matches if parcel.archived is None]
            if usable := [
                parcel for parcel in active if not _corrected(parcel, number)
            ]:
                wanted = number_key_text(number)
                chosen = max(
                    usable,
                    key=lambda parcel: (
                        number_key_text(parcel.state.tracking_number or "") == wanted,
                        parcel.updated,
                    ),
                )
                applied = self._apply(key, record, entry, now, tz, anchor=chosen)
                return applied, _MATCHED
            if active:
                self._close(record)
                return False, _UNMATCHED
            if matches:
                return False, _MATCHED
            if "switch" not in record and (
                found := self._switched_target(key, record, entry)
            ):
                return self._join_switched(key, record, entry, *found, now, tz)
        if not self.importing:
            return False, _UNMATCHED
        record["import"] = True
        moved = self._apply(key, record, entry, now, tz)
        # The dedup may have joined it to a parcel from e-mails.
        if (holder := self._holder(oid)) is None:
            return moved, _UNMATCHED
        return moved, _IMPORTED if removable(holder) else _MATCHED

    def _switched_target(
        self, key: str, record: dict[str, Any], entry: _Entry
    ) -> tuple[Parcel, str] | None:
        """Return the Amazon order's parcel a carrier's delivery continues.

        The Parcel app may switch an Amazon delivery to the carrier's number:
        the Amazon delivery leaves the list and the carrier's appears, with
        its description, the item's title. Returns the order's parcel and
        the key of the Amazon delivery that left, or None. Only when:

        - the description is an item's title: not one word, a shop's or a
          carrier's name, also with words like "order", or what Parcels
          itself sent;
        - one parcel open when this delivery appeared had an Amazon delivery
          with it: two orders of the same item are a tie, even while one is
          still listed or once one has finished. A tie is final: the record
          is marked, so it isn't judged again when the facts change;
        - that parcel may take the number (:func:`switch_target_open`) and
          has more than the Parcel app's deliveries;
        - its Amazon delivery left the list before this one appeared, at
          most ``SWITCH_WINDOW`` before;
        - the user doesn't keep them apart;
        - a private parcel is the delivery's owner's: else it's suggested.
        """
        if entry.order is not None:
            return None
        title = _description(entry.delivery)
        since = dt_from_str(record.get("since"))
        if (
            title is None
            or since is None
            or title.casefold()
            in (
                FALLBACK_DESCRIPTION.casefold(),
                str(record.get("sent") or "").casefold(),
            )
            or is_generic_title(title)
        ):
            return None
        data = self.engine.data
        wanted = title.casefold()
        sources: list[tuple[Parcel, list[str]]] = []
        for parcel in data.parcels.values():
            if not _open_at(parcel, since):
                continue
            if keys := [
                oid.removeprefix(PARCELAPP_PREFIX)
                for oid, origin in parcel.origins.items()
                if oid.startswith(PARCELAPP_PREFIX)
                and origin.order_numbers
                and not origin.tracking_number
                and (origin.name or "").casefold() == wanted
            ]:
                sources.append((parcel, keys))
        if len(sources) > 1:
            # Later, an order finished or gone would seem to settle it.
            record["switch"] = ""
            return None
        if not sources:
            return None
        target, keys = sources[0]
        if not switch_target_open(target) or removable(target):
            return None
        records = self._records
        left: list[str] = []
        for source in keys:
            source_record = records.get(source)
            if source in self._present or not isinstance(source_record, dict):
                continue
            seen = dt_from_str(source_record.get("seen"))
            if seen is not None and seen < since <= seen + SWITCH_WINDOW:
                left.append(source)
        if not left:
            return None
        names = {
            name
            for parcel in data.parcels.values()
            for origin in parcel.origins.values()
            for name in (origin.merchant, origin.seller)
            if name
        }
        if is_generic_title(title, names) or kept_apart_from(
            data, {PARCELAPP_PREFIX + key}, target
        ):
            return None
        if not may_guess_into(
            target, (self.owner,) if self.importing and self.owner else ()
        ):
            # A private parcel takes nobody else's delivery: suggested instead.
            hold_guess(
                data, target.origins, {PARCELAPP_PREFIX + key}, REASON_PARCEL_SWITCH
            )
            return None
        return target, min(left)

    def _join_switched(
        self,
        key: str,
        record: dict[str, Any],
        entry: _Entry,
        target: Parcel,
        source: str,
        now: datetime,
        tz: tzinfo,
    ) -> tuple[bool, str]:
        """Join a carrier's delivery to the Amazon order's parcel it continues.

        As if the number were the parcel's own; flagged, so the user can
        undo it. ``source`` is the key of the Amazon delivery that left.
        """
        record["switch"] = source
        record.pop("import", None)
        moved = self._apply(key, record, entry, now, tz, anchor=target)
        oid = PARCELAPP_PREFIX + key
        if (holder := self._holder(oid)) is None:
            record.pop("switch", None)
            return moved, _UNMATCHED
        flag_switch(self.engine.data, holder.id, {oid}, now)
        return True, _MATCHED

    def _join_held(
        self,
        key: str,
        record: dict[str, Any],
        entry: _Entry,
        holder: Parcel,
        now: datetime,
    ) -> bool:
        """Join a held carrier's delivery's parcel to the order's it continues.

        For one imported, or matched by number, before the Amazon delivery
        left: see ``_switched_target``. The merge is flagged, so the user
        can undo it. Returns True when they merged. A join the user undid
        is marked, and a parcel made only of deliveries is an import again
        when importing.
        """
        if "switch" in record:
            source = record["switch"]
            if (
                isinstance(source, str)
                and source
                and (keeper := self._holder(PARCELAPP_PREFIX + source)) is not None
                and keeper is not holder
            ):
                # The user took it back out of the order's parcel.
                record["switch"] = ""
                if self.importing and removable(holder):
                    record["import"] = True
                    record.pop("fp", None)
            return False
        found = self._switched_target(key, record, entry)
        if (
            found is None
            or found[0] is holder
            or not join_switched(self.engine.data, found[0].id, holder.id, now)
        ):
            return False
        record["switch"] = found[1]
        record.pop("import", None)
        record.pop("fp", None)
        return True

    @staticmethod
    def _close(record: dict[str, Any]) -> None:
        """Stop following a delivery until it's forgotten."""
        record["held"] = False
        record["closed"] = True
        record.pop("fp", None)

    def _apply(
        self,
        key: str,
        record: dict[str, Any],
        entry: _Entry,
        now: datetime,
        tz: tzinfo,
        *,
        anchor: Parcel | None = None,
    ) -> bool:
        """Apply a delivery to its parcel; return True when the parcel changed."""
        delivery, number, order = entry.delivery, entry.number, entry.order
        oid = PARCELAPP_PREFIX + key
        holder = self._holder(oid)
        base = _without(holder or anchor, oid)
        base_state = base.state if base is not None else None
        expected = parse_expected(delivery, tz)
        history = self._history(record, delivery, now, tz)
        events = _history_events(
            history, _known_times(base, base_state, expected, tz), now, tz
        )
        if (eta := self._eta(record, expected, base, base_state, now)) is not None:
            events.append(eta)
        code = record.get("code")
        imported = bool(record.get("import"))
        description = _description(delivery)
        merchant: str | None = None
        if imported:
            merchant = (
                "Amazon"
                if order is not None or amazon_store(code)
                else known_merchant_name(description)
            )
        since = dt_from_str(record.get("since")) or now
        carrier = parcels_carrier(code, number)
        base_carrier = base_state.carrier if base_state else None
        origin = Origin(
            id=oid,
            source=Source.PARCELAPP,
            time=min([event.time for event in events] + [since]),
            label=ORIGIN_LABEL,
            # Parcel's carrier fills one the parcel doesn't know; but the
            # number Parcel switched an Amazon order to is the carrier's.
            carrier=(carrier or base_carrier)
            if record.get("switch")
            else (base_carrier or carrier),
            tracking_number=None if order is not None else number,
            merchant=merchant,
            order_numbers=(order,) if order is not None else (),
            amazon_shipment_id=(
                _record_shipment(record) if order is not None else None
            ),
            owners=(self.owner,) if imported and self.owner else (),
            name=(
                None
                if description in (None, record.get("sent"), FALLBACK_DESCRIPTION)
                else description
            ),
        )
        digest = _digest(origin, events)
        if holder is not None and record.get("fp") == digest:
            return False
        contribution = Contribution(
            origin=origin,
            events=events,
            anchor=min(anchor.origins)
            if anchor is not None and holder is None
            else None,
        )
        applied = apply_contribution(self.engine.data, contribution, now)
        if applied.parcel_id is None:
            record["held"] = False
            record.pop("fp", None)
            return False
        record["held"] = True
        record["fp"] = digest
        return True

    def _history(
        self,
        record: dict[str, Any],
        delivery: dict[str, Any],
        now: datetime,
        tz: tzinfo,
    ) -> list[dict[str, Any]]:
        """Store a delivery's events, newest first, and return them.

        An event keeps the status it had when first read. The newest takes
        the delivery's status: Parcel gives one for the whole delivery. An
        event without a date keeps when it was first seen with its status:
        it happened by then. An event whose date gave only its day keeps it.
        """
        # An event's text, its time, and its day when only that was read.
        read: list[tuple[str | None, datetime | None, date | None]] = []
        for item in delivery.get("events") or ():
            if not isinstance(item, Mapping):
                continue
            info = _event_text(item)
            found = read_event_date(item.get("date"), now, tz)
            at = found.at if found is not None else None
            day = found.day if found is not None and at is None else None
            if info is not None or found is not None:
                read.append((info, at, day))
        if read and all(at is not None for _, at, _ in read):
            read.sort(key=lambda entry: entry[1] or now, reverse=True)
        elif read and all(at is not None or day is not None for _, at, day in read):
            # Newest day first; on one day, as Parcel lists them.
            read.sort(
                key=lambda entry: (
                    entry[1].astimezone(tz).date()
                    if entry[1] is not None
                    else entry[2] or date.min
                ),
                reverse=True,
            )
        entries: list[tuple[str | None, datetime | None, date | None]] = []
        for entry in read:
            if entry not in entries:
                entries.append(entry)
            if len(entries) == MAX_HISTORY:
                break
        if not entries:
            entries.append((None, None, None))
        kept = {
            (item.get("info"), item.get("at"), item.get("day")): item
            for item in record.get("history") or ()
            if isinstance(item, dict)
        }
        code = status_code(delivery.get("status_code"))
        mapped = STATUSES.get(code) if code is not None else None
        history: list[dict[str, Any]] = []
        for index, (info, at, day) in enumerate(entries):
            iso = day.isoformat() if day is not None else None
            # Before 0.1.10, a date read now may not have been read at all.
            old = (
                kept.get((info, dt_to_str(at), iso))
                or kept.get((info, None, None))
                or {}
            )
            stored = _stored_status(old.get("status"))
            status = stored
            if index == 0 and mapped is not None:
                status = refine_status(mapped, info)
            item: dict[str, Any] = {
                "info": info,
                "at": dt_to_str(at),
                "status": status.value if status else None,
            }
            if iso is not None:
                item["day"] = iso
            if at is None:
                # 0.1.6 kept when it was first read as "time".
                seen = dt_from_str(old.get("seen") or old.get("time"))
                item["seen"] = dt_to_str(
                    now if seen is None or status is not stored else seen
                )
            history.append(item)
        record["history"] = history
        return history

    @staticmethod
    def _eta(
        record: dict[str, Any],
        value: Eta | None,
        base: Parcel | None,
        base_state: ParcelState | None,
        now: datetime,
    ) -> ParcelEvent | None:
        """Return the delivery's expected date as an event, if it tells one.

        It's dated when Parcel first gave it, so that newer news wins. It
        doesn't take away the time window an e-mail gave for the same days,
        and its own window fills one the e-mails didn't give.
        """
        if value is None:
            record.pop("eta", None)
            return None
        stored = record.get("eta") if isinstance(record.get("eta"), dict) else {}
        serialised = eta_to_dict(value)
        seen = (
            dt_from_str(stored.get("seen"))
            if stored.get("value") == serialised
            else None
        ) or now
        current = base_state.eta if base_state is not None else None
        emit = True
        if current is not None and (current.start, current.end) == (
            value.start,
            value.end,
        ):
            if _has_window(current) and not _has_window(value):
                emit = False
            elif (
                _has_window(value)
                and not _has_window(current)
                and base is not None
                and (latest := _latest_eta_time(base)) is not None
                and seen <= latest
            ):
                seen = now
        record["eta"] = {"value": serialised, "seen": dt_to_str(seen)}
        if not emit:
            return None
        return ParcelEvent(time=seen, source=Source.PARCELAPP, eta=value)

    def _missing(self, read: set[str], now: datetime) -> bool:
        """Count the reads a delivery was missing from; forget old ones.

        A delivery that left the user's list, or was forgotten, leaves its
        parcel when it's made only of deliveries (see ``_drop_delivery``).
        """
        records = self._records
        changed = False
        for key, record in list(records.items()):
            if key in read:
                continue
            if not isinstance(record, dict):
                del records[key]
                continue
            last = max(
                (
                    value
                    for name in ("seen", "added", "since", "tried")
                    if (value := dt_from_str(record.get(name))) is not None
                ),
                default=None,
            )
            if last is None or now - last > RECORD_DAYS:
                del records[key]
                changed |= self._drop_delivery(key, now)
                continue
            if "seen" not in record:
                continue
            record["missing"] = missing = _count(record.get("missing")) + 1
            if missing >= MISSING_READS and self._drop_delivery(key, now):
                record["held"] = False
                record.pop("fp", None)
                changed = True
        return changed

    def _drop_delivery(self, key: str, now: datetime) -> bool:
        """Take a delivery out of its parcel; return True when it was.

        Only an open parcel made of deliveries loses it: a delivered or
        archived one keeps its news, as does one with e-mails. The parcel
        goes with its last delivery, and the user's edits go with it.
        """
        oid = PARCELAPP_PREFIX + key
        holder = self._holder(oid)
        if (
            holder is None
            or holder.archived is not None
            or holder.state.terminal
            or not removable(holder)
        ):
            return False
        others = any(
            other != oid and other.startswith(PARCELAPP_PREFIX)
            for other in holder.origins
        )
        removed = {oid} if others else set(holder.origins)
        remove_origins(self.engine.data, holder, removed, now)
        return True

    def _learn(
        self, found: dict[str, dict[str, Any]], orders: set[str], now: datetime
    ) -> None:
        """Learn the code Parcel gave each carrier from the user's deliveries.

        Only deliveries he added himself that Parcel found, on parcels whose
        carrier e-mails named.
        """
        learned = self._state.get("learned")
        if not isinstance(learned, dict):
            learned = self._state["learned"] = {}
        records = self._records
        for key, delivery in found.items():
            record = records[key]
            code = record.get("code")
            if (
                key in orders
                or code is None
                or record.get("own")
                or record.get("status") == NOT_FOUND
                or not delivery.get("events")
            ):
                continue
            oid = PARCELAPP_PREFIX + key
            holder = self._holder(oid)
            if holder is None or not any(
                origin.source in _LEARN_SOURCES for origin in holder.origins.values()
            ):
                continue
            base = _without(holder, oid)
            carrier = base.state.carrier if base is not None else None
            if carrier is None or carrier == "other" or carrier not in CARRIER_NAMES:
                continue
            named = "amazon" if amazon_code(code) else parcels_carrier(code)
            if named is not None and carrier_family(named) != carrier_family(carrier):
                continue
            entry = learned.get(key)
            if (
                not isinstance(entry, dict)
                or entry.get("carrier") != carrier
                or entry.get("code") != code
            ):
                learned[key] = {
                    "carrier": carrier,
                    "code": code,
                    "time": dt_to_str(now),
                }
        oldest = now - LEARN_DAYS
        kept = sorted(
            (
                (time, key)
                for key, entry in learned.items()
                if isinstance(entry, dict)
                and (time := dt_from_str(entry.get("time"))) is not None
                and time >= oldest
            ),
            reverse=True,
        )[:LEARN_MAX]
        self._state["learned"] = {key: learned[key] for _, key in kept}

    def learned_by_carrier(self) -> dict[str, str]:
        """Return the code Parcel gives each carrier: the most common, then latest."""
        tally: dict[str, dict[str, tuple[int, str]]] = {}
        learned = self._state.get("learned")
        for entry in learned.values() if isinstance(learned, dict) else ():
            if not isinstance(entry, dict):
                continue
            carrier, code = entry.get("carrier"), entry.get("code")
            if not isinstance(carrier, str) or not isinstance(code, str):
                continue
            codes = tally.setdefault(carrier, {})
            count, latest = codes.get(code, (0, ""))
            codes[code] = (count + 1, max(latest, str(entry.get("time") or "")))
        return {
            carrier: max(codes.items(), key=lambda item: item[1])[0]
            for carrier, codes in tally.items()
        }

    # -- Adding -------------------------------------------------------------

    def _adds_today(self, now: datetime) -> dict[str, Any]:
        """Return today's adds; they start afresh each day, in HA's time zone."""
        day = dt_util.as_local(now).date().isoformat()
        adds = self._state.get("adds")
        if not isinstance(adds, dict) or adds.get("day") != day:
            adds = self._state["adds"] = {"day": day, "sent": 0, "added": 0}
        return adds

    def _mailboxes_have_owners(self) -> bool:
        """Return whether any mailbox entry has an owner."""
        return any(
            entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_MAILBOX
            and entry.options.get(CONF_OWNER)
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        )

    def _in_scope(self, state: ParcelState, mailbox_owners: bool) -> bool:
        """Return whether a parcel is one the user wants in his list.

        His own parcels, or everyone's when he chose so. Without an owner
        chosen, only parcels of no one, while no mailbox has an owner.
        """
        if self.everyone:
            return True
        if (owner := self.owner) is not None:
            return owner in state.owners
        return not state.owners and not mailbox_owners

    def _language(self) -> str | None:
        """Return Home Assistant's language as an ISO 639-1 code, or None."""
        first = re.split(r"[-_]", str(self.hass.config.language or ""))[0].lower()
        if len(first) == 2 and first.isascii() and first.isalpha():
            return first
        return None

    @staticmethod
    def _description(state: ParcelState) -> str:
        """Return what a parcel is added as: its merchant's name, never items."""
        merchant = (clip_text(state.merchant) or "")[:MAX_DESCRIPTION].rstrip()
        return merchant or FALLBACK_DESCRIPTION

    def _candidates(
        self, listed: set[str], now: datetime
    ) -> Iterator[tuple[ParcelState, str, str]]:
        """Yield the parcels to add, soonest due first, with number and code.

        Open parcels in scope, with a number of a known format and a carrier
        Parcel names, that aren't in the user's list, by their number or
        their Amazon order. A number is sent once a day at most, never again
        once in his list or added, nor again under a code Parcel refused.
        ``listed`` holds the numbers as compared, and may grow meanwhile.
        """
        records = self._records
        today = dt_util.as_local(now).date()
        learned = self.learned_by_carrier()
        country = self.hass.config.country
        mailbox_owners = self._mailboxes_have_owners()
        ids = [p.id for p in sorted(self.engine.data.parcels.values(), key=add_order)]
        for parcel_id in ids:
            # Parcels may change while a delivery is being added.
            if (parcel := self.engine.data.parcels.get(parcel_id)) is None:
                continue
            state = parcel.state
            if (
                parcel.archived is not None
                or parcel.private
                or state.terminal
                or any(oid.startswith(PARCELAPP_PREFIX) for oid in parcel.origins)
                or not self._in_scope(state, mailbox_owners)
                or (key := delivery_key(state.tracking_number)) is None
                or (code := parcel_code(state.carrier, country, learned)) is None
                or code in UNUSABLE
                or (code in NEEDS_POSTCODE and self.postcode is None)
                or not validate_tracking_number(key, state.carrier)
                or _compared(key) in listed
                or any(
                    _compared(order) in listed
                    for order in map(delivery_key, state.order_numbers)
                    if order is not None
                )
                or is_quiet(parcel, now)
            ):
                continue
            record = records.get(key)
            if isinstance(record, dict) and (
                "seen" in record
                or "added" in record
                or record.get("refused") == code
                or (
                    (tried := dt_from_str(record.get("tried"))) is not None
                    and dt_util.as_local(tried).date() == today
                )
            ):
                continue
            yield state, key, code

    async def _async_add(self, listed: set[str], now: datetime) -> None:
        """Add the numbers of new parcels to the user's list.

        At most ``daily`` requests a day, failures included, since Parcel
        counts them. A refused number is skipped; any other failure ends
        adding until the next read, and Parcel's limit or a refused key until
        tomorrow. Logs carry error codes, never numbers.
        """
        if not self.adding or self.daily <= 0:
            return
        adds = self._adds_today(now)
        if adds.get("stopped"):
            return
        api_key = self.key
        compared = {_compared(key) for key in listed}
        language = self._language()
        stamp = dt_to_str(now)
        records = self._records
        for state, key, code in self._candidates(compared, now):
            # The options may change while a delivery is being added.
            if (
                _count(adds.get("sent")) >= self.daily
                or self.key != api_key
                or not self.adding
            ):
                break
            description = self._description(state)
            record = records.get(key)
            if not isinstance(record, dict):
                record = records[key] = {}
            record["tried"] = stamp
            adds["sent"] = _count(adds.get("sent")) + 1
            compared.add(_compared(key))
            try:
                await async_add_delivery(
                    self.hass,
                    api_key,
                    number=key,
                    carrier=code,
                    description=description,
                    language=language,
                    postcode=self.postcode if code in NEEDS_POSTCODE else None,
                )
            except ParcelAppError as err:
                adds["error"] = err.code
                if err.kind is ErrorKind.REFUSED:
                    record["refused"] = code
                    _LOGGER.debug("The Parcel app refused a delivery (%s)", err.code)
                    continue
                if err.kind in (ErrorKind.RATE, ErrorKind.KEY):
                    adds["stopped"] = True
                self._add_failed(err)
                break
            record["added"] = stamp
            record["own"] = True
            record["sent"] = description
            record.pop("refused", None)
            adds["added"] = _count(adds.get("added")) + 1
            self._add_logged = None
        self.engine.async_schedule_save()

    def _add_failed(self, err: ParcelAppError) -> None:
        if err.code != self._add_logged:
            self._add_logged = err.code
            _LOGGER.warning(
                "Adding a delivery to the Parcel app failed (%s); trying again %s",
                err.code,
                "tomorrow" if err.kind in (ErrorKind.RATE, ErrorKind.KEY) else "later",
            )
        else:
            _LOGGER.debug("Adding a delivery to the Parcel app failed (%s)", err.code)

    # -- Diagnostics --------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        """Return the state of the source, without numbers or the key."""
        state = self._state
        counts = state.get("counts")
        counts = counts if isinstance(counts, dict) else {}
        adds = state.get("adds")
        today = dt_util.as_local(dt_util.utcnow()).date().isoformat()
        if not isinstance(adds, dict) or adds.get("day") != today:
            adds = {}
        learned = self.learned_by_carrier()
        dates = state.get("dates")
        dates = dates if isinstance(dates, dict) else {}
        shapes = dates.get("shapes")
        day_shapes = dates.get("day_only_shapes")
        marked = dates.get("marked")
        amazon = counts.get("amazon")
        amazon = amazon if isinstance(amazon, dict) else {}
        return {
            "enabled": self.enabled,
            "last_refresh": dt_to_str(self.last_refresh),
            "last_error": self.last_error,
            "key_refused": state.get("key_refused") is not None,
            "backoff_until": state.get("backoff_until"),
            "errors": _count(state.get("errors")),
            "deliveries": {
                "listed": _count(counts.get("deliveries")),
                "matched": _count(counts.get(_MATCHED)),
                "imported": _count(counts.get(_IMPORTED)),
                "unmatched": _count(counts.get(_UNMATCHED)),
                # Of those, Amazon's, by how each found its parcel.
                "amazon": {name: _count(amazon.get(name)) for name in _AMAZON_COUNTS},
                # Carriers' deliveries held in the Amazon order's parcel they
                # continue: see ``_switched_target``.
                "switched": _count(counts.get("switched")),
            },
            "added_today": {
                "sent": _count(adds.get("sent")),
                "added": _count(adds.get("added")),
                "stopped": bool(adds.get("stopped")),
                "error": adds.get("error"),
            },
            "carriers": {
                "learned": learned,
                "codes": parcel_codes(self.hass.config.country, learned),
            },
            # Of the last read, without the dates: see ``_date_stats``.
            "event_dates": {
                "unparsed": _count(dates.get("unparsed")),
                "future": _count(dates.get("future")),
                "shapes": shapes if isinstance(shapes, dict) else {},
                "day_only": _count(dates.get("day_only")),
                "day_only_shapes": day_shapes if isinstance(day_shapes, dict) else {},
                "marked": marked if isinstance(marked, dict) else {},
            },
        }
