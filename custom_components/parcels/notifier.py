"""Lock-screen notifications for Parcels.

The notifier turns the day's parcels into iOS Live Activities, plain
notifications on iPads and Android phones, and one persistent notification in
Home Assistant. The engine creates one :class:`Notifier` for the hub entry,
starts it once the store is loaded, calls :meth:`Notifier.async_parcels_changed`
after every data change and stops it on unload.

Routing
    Only ``notify.mobile_app_<device>`` services are called, never
    ``notify.notify`` or a group. A device is notified when one of its persons
    (a ``person`` whose ``user_id`` is the mobile_app entry's ``user_id``) is in
    the hub's notify persons and the device isn't excluded. In test mode only
    the test device gets anything. Private parcels go only to their owners'
    devices and never show item names; item names reach the lock screen only
    when the hub option allows it.

Device kinds
    iPhones get Live Activities. iPads and Android phones get one normal
    notification per parcel (same tag, each replacing the last) on key changes:
    out for delivery, ready for pickup, delivered, attempted and exception.
    Macs, watches and unknown systems get nothing; they mirror the iPhone.
    The Live Activities switch covers these notifications too.

The day
    Everything happens between the start time and the cut-off, in Home
    Assistant's time zone. At the start time the day's board is built from
    non-terminal parcels expected today (the last day of the ETA is today) and
    parcels that became ready for pickup since the previous cut-off. Later in
    the day a parcel joins when it goes out for delivery today or becomes ready
    for pickup. Nothing starts after the cut-off, and the cut-off ends every
    remaining activity. A pickup parcel is on the lock screen on the day it
    became ready (or the next day when that happened after the cut-off); on
    later days only the persistent notification lists it, for up to a week.

Live Activities
    One activity per parcel and iPhone (tag ``parcel-<id>``), or one combined
    activity (``parcels-today-YYYYMMDD``) once a device has more parcels than
    the collapse threshold; a device then stays combined for the rest of the
    day. Updates are sent only when the payload changes, and quietly when the
    status didn't change. A delivered parcel shows its delivery time at 4/4 and
    ends 30 minutes later; a parcel moved to a later day says so and ends 30
    minutes later. Apple ends activities after 8 hours, so an undelivered
    parcel's activity is ended and restarted with a ``-2`` (``-3`` ...) tag
    after 7.5 hours. To respect Apple's push-to-start budget a parcel starts at
    most once per device and day, except for that restart, the switch being
    turned back on, a device becoming a recipient again and a moved parcel that
    goes out for delivery after all. The state is persisted, so a restart of
    Home Assistant neither ends nor duplicates an activity.

    The icon and the progress bar take the colour of the status: blue on the
    way, orange out for delivery, green delivered, purple ready for pickup and
    red for a missed attempt or a problem. The card keeps the system's dark
    background, and the icon and the text still say the status. A combined
    activity takes the colour of its most urgent parcel: out for delivery,
    then a problem, then a pickup; green once all are delivered. The message
    always shows the delivery window; the countdown runs only in the last
    hour of the window (all of a shorter one) and starts with one quiet
    update. The combined activity shows no countdown while one of its
    parcels has a missed attempt or a problem, so its text can say so; a
    parcel's own activity keeps its countdown. Tapping an activity or a
    notification opens the parcel on the dashboard
    (``<path>?parcel=<id>``); the combined activity opens the week.

Packages
    The day counts packages, not records. An order without a carrier's
    number that one of the day's packages may hold rides along with it (see
    :func:`~.dedup.boxes_of_day`): it doesn't count, start an activity or
    notify on its own, and with item names on, the package says what it may
    hold ("Possibly: ..."). An order that no package may hold counts on its
    own. When an order stops riding along, its activity starts again.

Persistent notification
    ``parcels_today`` lists the day's parcels from the start time until the
    next morning's start time, without item names; private parcels are only
    counted.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Coroutine, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
import hashlib
import json
import logging
import re
import traceback
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit, urlunsplit

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, CoreState, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CONF_COLLAPSE_THRESHOLD,
    CONF_CUTOFF_TIME,
    CONF_DASHBOARD_PATH,
    CONF_EXCLUDED_DEVICES,
    CONF_ITEM_NAMES,
    CONF_NOTIFY_PERSONS,
    CONF_START_TIME,
    CONF_TEST_DEVICE,
    CONF_TEST_MODE,
    DEFAULT_COLLAPSE_THRESHOLD,
    DEFAULT_CUTOFF_TIME,
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_ITEM_NAMES,
    DEFAULT_START_TIME,
    DOMAIN,
    PERSISTENT_NOTIFICATION_ID,
    STATUS_RANK,
    ParcelStatus,
)
from .dedup import boxes_of_day
from .models import Parcel, ParcelsData, ParcelState, local_date
from .parsers.base import Eta
from .parsers.items import unique_items
from .views import shipment_groups

_LOGGER = logging.getLogger(__name__)

STATE_KEY = "notifier"
STATE_VERSION = 1

DEBOUNCE_COOLDOWN = 10.0
DELIVERED_LINGER = timedelta(minutes=30)
RESTART_AFTER = timedelta(hours=7, minutes=30)
APPLE_LIMIT = timedelta(hours=8)
RETRY_DELAY = timedelta(minutes=5)
TEST_ACTIVITY_DURATION = timedelta(minutes=1)
DUE_TOLERANCE = timedelta(seconds=1)
COUNTDOWN = timedelta(hours=1)
PICKUP_DAYS = 7

PROGRESS_MAX = 4
COMBINED = "combined"
COMBINED_TITLE = "Parcels today"
TEST_TAG = "parcels-test"
MAX_TAG = 64
MAX_TEXT = 40
MAX_NAME = 20
# The query parameters the dashboard opens details from.
LINK_KEYS = frozenset({"parcel", "return"})

NOTIFY_DOMAIN = "notify"
MOBILE_APP_DOMAIN = "mobile_app"
PERSON_DOMAIN = "person"
CLEAR_NOTIFICATION = "clear_notification"
PERSISTENT_TITLE = "Parcels"

DASH = "\u2013"
SEP = " \u00b7 "
CHECK = "\u2713"
ELLIPSIS = "\u2026"

REASON_CUTOFF = "cutoff"
REASON_DISABLED = "disabled"
REASON_REMOVED = "removed"
REASON_COLLAPSED = "collapsed"
REASON_DELIVERED = "delivered"
REASON_RESTART = "restart"
REASON_MOVED = "moved"
RESTARTABLE = frozenset({REASON_RESTART, REASON_DISABLED, REASON_REMOVED})

S = ParcelStatus
KEY_STATUSES = frozenset(
    {S.OUT_FOR_DELIVERY, S.READY_FOR_PICKUP, S.DELIVERED, S.ATTEMPTED, S.EXCEPTION}
)
EN_ROUTE = frozenset({S.ORDERED, S.SHIPPED, S.IN_TRANSIT, S.OUT_FOR_DELIVERY})
MOVABLE = frozenset({S.ORDERED, S.SHIPPED, S.IN_TRANSIT, S.ATTEMPTED, S.EXCEPTION})
PROBLEMS = frozenset({S.ATTEMPTED, S.EXCEPTION})
GONE = frozenset({S.RETURNED, S.CANCELLED})

ICONS: dict[ParcelStatus, str] = {
    S.ORDERED: "mdi:cart-outline",
    S.SHIPPED: "mdi:truck-fast",
    S.IN_TRANSIT: "mdi:truck-fast",
    S.OUT_FOR_DELIVERY: "mdi:truck-delivery",
    S.DELIVERED: "mdi:package-check",
    S.READY_FOR_PICKUP: "mdi:storefront",
    S.ATTEMPTED: "mdi:alert-circle-outline",
    S.EXCEPTION: "mdi:alert-circle-outline",
}
DEFAULT_ICON = "mdi:package-variant-closed"

# Legible on the Lock Screen's dark card; never the only sign of a status.
BLUE = "#039BE5"
ORANGE = "#FFA600"
GREEN = "#43A047"
PURPLE = "#926BC7"
RED = "#DB4437"
COLORS: dict[ParcelStatus, str] = {
    S.OUT_FOR_DELIVERY: ORANGE,
    S.DELIVERED: GREEN,
    S.READY_FOR_PICKUP: PURPLE,
    S.ATTEMPTED: RED,
    S.EXCEPTION: RED,
}
DEFAULT_COLOR = BLUE

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
_TAG_INVALID = re.compile(r"[^A-Za-z0-9_-]+")
_SPACES = re.compile(r"\s+")
_MARKDOWN = re.compile(r"([\\`*_\[\]<>|#~])")
_OTHER_APPLE_OS = frozenset(
    {"macos", "mac os x", "macosx", "watchos", "tvos", "visionos", "xros"}
)
# The persistent notification may still be shown after a reload.
_UNKNOWN = "\x00unknown"


class NotifierHost(Protocol):
    """What the notifier needs from the engine."""

    data: ParcelsData

    def visible_parcels(self) -> list[Parcel]:
        """Return the parcels that aren't archived."""

    def async_schedule_save(self) -> None:
        """Save the store after a short delay."""


class DeviceKind(StrEnum):
    """What a mobile_app device is sent."""

    IPHONE = "iphone"
    IPAD = "ipad"
    ANDROID = "android"
    OTHER = "other"


def classify_device(data: Mapping[str, Any]) -> DeviceKind:
    """Classify a mobile_app config entry from its data."""
    os_name = str(data.get("os_name") or "").strip().casefold()
    model = str(data.get("model") or "").strip().casefold()
    app_id = str(data.get("app_id") or "").strip().casefold()
    if os_name == "android" or app_id.startswith("io.homeassistant.companion.android"):
        return DeviceKind.ANDROID
    if os_name in _OTHER_APPLE_OS or model.startswith(("mac", "imac", "watch")):
        return DeviceKind.OTHER
    if os_name == "ipados" or model.startswith(("ipad", "ipod")):
        return DeviceKind.IPAD
    if os_name == "ios" or model.startswith("iphone"):
        return DeviceKind.IPHONE
    return DeviceKind.OTHER


@dataclass(frozen=True, slots=True)
class _Device:
    """A mobile_app device and the persons it belongs to."""

    device_id: str
    service: str
    kind: DeviceKind
    persons: frozenset[str]


@dataclass(frozen=True, slots=True)
class _Options:
    """The hub options the notifier uses."""

    persons: frozenset[str]
    excluded: frozenset[str]
    test_mode: bool
    test_device: str | None
    start: time
    cutoff: time
    threshold: int
    item_names: bool
    path: str

    @classmethod
    def from_entry(cls, entry: ConfigEntry) -> _Options:
        """Read the options of the hub entry, with defaults."""
        options = entry.options
        test_device = options.get(CONF_TEST_DEVICE)
        return cls(
            persons=frozenset(_str_list(options.get(CONF_NOTIFY_PERSONS))),
            excluded=frozenset(_str_list(options.get(CONF_EXCLUDED_DEVICES))),
            test_mode=options.get(CONF_TEST_MODE) is True,
            test_device=test_device
            if isinstance(test_device, str) and test_device
            else None,
            start=_parse_time(options.get(CONF_START_TIME), DEFAULT_START_TIME),
            cutoff=_parse_time(options.get(CONF_CUTOFF_TIME), DEFAULT_CUTOFF_TIME),
            threshold=_parse_int(
                options.get(CONF_COLLAPSE_THRESHOLD), DEFAULT_COLLAPSE_THRESHOLD
            ),
            item_names=bool(options.get(CONF_ITEM_NAMES, DEFAULT_ITEM_NAMES)),
            path=str(options.get(CONF_DASHBOARD_PATH) or DEFAULT_DASHBOARD_PATH),
        )


@dataclass(frozen=True, slots=True)
class _Context:
    """One evaluation: the time, today's window and the options."""

    now: datetime
    today: date
    start: datetime
    cutoff: datetime
    prev_cutoff: datetime
    options: _Options

    @property
    def key(self) -> str:
        """Return the state key of today."""
        return self.today.isoformat()

    @property
    def in_window(self) -> bool:
        """Return True between the start time and the cut-off."""
        return self.start <= self.now < self.cutoff


class _Result(StrEnum):
    """The outcome of a notify call."""

    SENT = "sent"
    MISSING = "missing"
    FAILED = "failed"


def _user_error(key: str) -> ServiceValidationError:
    return ServiceValidationError(translation_domain=DOMAIN, translation_key=key)


def _str_list(value: Any) -> list[str]:
    """Return the non-empty strings of a list (or a single string)."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list | tuple | set | frozenset):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _parse_time(value: Any, default: str) -> time:
    """Parse an ``HH:MM[:SS]`` option, falling back to the default."""
    parsed: time | None = None
    if isinstance(value, time):
        parsed = value
    elif isinstance(value, str):
        parsed = dt_util.parse_time(value.strip())
    return (parsed or time.fromisoformat(default)).replace(tzinfo=None)


def _parse_int(value: Any, default: int) -> int:
    """Parse a whole number option, falling back to the default."""
    try:
        return max(0, int(float(value)))
    except TypeError, ValueError, OverflowError:
        return default


def _parse_date(value: str) -> date | None:
    """Parse an ISO date, or return None."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _iso(value: datetime) -> str:
    """Serialise an aware datetime as UTC."""
    return dt_util.as_utc(value).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    """Parse a serialised datetime as UTC, or return None."""
    if not isinstance(value, str):
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return dt_util.as_utc(parsed)


def _local_at(day: date, value: time) -> datetime:
    """Return a wall-clock time in Home Assistant's time zone, as UTC."""
    local = datetime.combine(day, value, tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_utc(local)


def _window(day: date, options: _Options) -> tuple[datetime, datetime]:
    """Return the start and the cut-off of a day, as UTC."""
    start = _local_at(day, options.start)
    if options.cutoff == time(0, 0):
        cutoff = _local_at(day + timedelta(days=1), time(0, 0))
    else:
        cutoff = _local_at(day, options.cutoff)
    return start, max(start, cutoff)


def _clean(value: Any, limit: int = MAX_TEXT) -> str:
    """Collapse whitespace and shorten a text for the lock screen."""
    text = _SPACES.sub(" ", str(value or "")).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + ELLIPSIS
    return text


def _tag(base: str, gen: int = 1) -> str:
    """Return a valid tag: letters, digits, - and _, at most 64 characters."""
    suffix = f"-{gen}" if gen > 1 else ""
    return _TAG_INVALID.sub("-", base)[: MAX_TAG - len(suffix)] + suffix


def _parcel_tag(parcel_id: str, gen: int = 1) -> str:
    """Return the tag of a parcel's activity or notification."""
    return _tag(f"parcel-{parcel_id.removeprefix('p_')}", gen)


def _combined_tag(day: date, gen: int = 1) -> str:
    """Return the tag of a device's combined activity of a day."""
    return _tag(f"parcels-today-{day:%Y%m%d}", gen)


def _markdown(text: str) -> str:
    """Escape Markdown in a text."""
    return _MARKDOWN.sub(r"\\\1", text)


def _hm(value: time) -> str:
    """Return a time as HH:MM."""
    return f"{value.hour:02d}:{value.minute:02d}"


def _local_hm(value: datetime) -> str:
    """Return the local wall-clock time of an aware datetime as HH:MM."""
    return _hm(dt_util.as_local(value).time())


def _short_time(value: time) -> str:
    """Return a time as 14h or 14:30."""
    return f"{value.hour}h" if value.minute == 0 else f"{value.hour}:{value.minute:02d}"


def _day_text(day: date) -> str:
    """Return a date such as Thu 19 Nov."""
    return f"{_WEEKDAYS[day.weekday()]} {day.day} {_MONTHS[day.month - 1]}"


def _day_word(day: date, today: date) -> str:
    """Return a date relative to today: today, tomorrow, yesterday or Thu 19 Nov."""
    if day == today:
        return "today"
    if day == today + timedelta(days=1):
        return "tomorrow"
    if day == today - timedelta(days=1):
        return "yesterday"
    return _day_text(day)


def _window_text(eta: Eta | None) -> str | None:
    """Return a delivery window such as 13:00-14:00, by 14:00 or from 13:00."""
    if eta is None:
        return None
    start, end = eta.window_start, eta.window_end
    if start is not None and end is not None:
        return f"{_hm(start)}{DASH}{_hm(end)}"
    if end is not None:
        return f"by {_hm(end)}"
    if start is not None:
        return f"from {_hm(start)}"
    return None


def _window_short(eta: Eta | None) -> str | None:
    """Return a short delivery window such as 13-14h, by 14h or from 13h."""
    if eta is None:
        return None
    start, end = eta.window_start, eta.window_end
    if start is not None and end is not None:
        first = str(start.hour) if start.minute == 0 else _short_time(start)
        return f"{first}{DASH}{_short_time(end)}"
    if end is not None:
        return f"by {_short_time(end)}"
    if start is not None:
        return f"from {_short_time(start)}"
    return None


def _title(state: ParcelState) -> str:
    """Return the title of a parcel: its shop, else its carrier."""
    return _clean(state.merchant) or _clean(state.carrier_name) or "Parcel"


def _names(state: ParcelState) -> list[str]:
    """Return the shop and the carrier of a parcel, without duplicates."""
    names: list[str] = []
    for value in (state.merchant, state.carrier_name):
        name = _clean(value)
        if name and name.casefold() not in {n.casefold() for n in names}:
            names.append(name)
    return names


def _expected_today(state: ParcelState, today: date) -> bool:
    """Return True for an undelivered parcel whose ETA ends today."""
    return state.eta is not None and state.eta.end == today and not state.terminal


def _routed(parcel: Parcel, device: _Device) -> bool:
    """Return True when a device may show a parcel.

    Private parcels go only to their owners' devices (and to nobody when they
    have no owner).
    """
    return not parcel.private or bool(device.persons & set(parcel.state.owners))


def _countdown(eta: Eta, day: date) -> tuple[datetime, datetime] | None:
    """Return when the countdown to the end of a day's window starts and ends.

    It covers the last hour of the window, or all of a shorter one.
    """
    if eta.window_end is None:
        return None
    end = _local_at(day, eta.window_end)
    start = end - COUNTDOWN
    if eta.window_start is not None:
        start = max(start, _local_at(day, eta.window_start))
    return start, end


def _wake_moments(eta: Eta, day: date) -> list[datetime]:
    """Return when the time alone may change what a day's window shows."""
    moments = [
        _local_at(day, value)
        for value in (eta.window_start, eta.window_end)
        if value is not None
    ]
    if (countdown := _countdown(eta, day)) is not None:
        moments.append(countdown[0])
    return moments


def _chronometer_end(state: ParcelState, ctx: _Context) -> datetime | None:
    """Return the end of today's delivery window during its countdown.

    Without a window start ("by 14:00") it runs only while out for delivery.
    """
    eta = state.eta
    if (
        eta is None
        or eta.end != ctx.today
        or state.status not in EN_ROUTE
        or (eta.window_start is None and state.status is not S.OUT_FOR_DELIVERY)
        or (countdown := _countdown(eta, ctx.today)) is None
    ):
        return None
    start, end = countdown
    return end if start <= ctx.now < end else None


def _detail_url(path: str, key: str, value: str) -> str:
    """Return the dashboard path that opens the details of a parcel or a return.

    The dashboard path's own query is kept, except an earlier link.
    """
    parts = urlsplit(path)
    query = [
        pair
        for pair in parts.query.split("&")
        if pair and pair.split("=", 1)[0] not in LINK_KEYS
    ]
    query.append(urlencode({key: value}))
    return urlunsplit(parts._replace(query="&".join(query)))


def _relevance(state: ParcelState, ctx: _Context) -> float:
    """Return how prominent a parcel's activity is, from 0 to 1."""
    status = state.status
    if status is S.OUT_FOR_DELIVERY:
        return 1.0 if _chronometer_end(state, ctx) is not None else 0.9
    if status is S.READY_FOR_PICKUP:
        return 0.7
    if status in PROBLEMS:
        return 0.6
    if status is S.DELIVERED:
        return 0.2
    if _expected_today(state, ctx.today):
        return 0.5
    return 0.1


_STATUS_TEXT: dict[ParcelStatus, str] = {
    S.ORDERED: "Ordered",
    S.SHIPPED: "Shipped",
    S.IN_TRANSIT: "In transit",
    S.OUT_FOR_DELIVERY: "Out for delivery",
    S.DELIVERED: "Delivered",
    S.ATTEMPTED: "Delivery attempted",
    S.EXCEPTION: "Delivery problem",
    S.READY_FOR_PICKUP: "Ready for pickup",
    S.RETURNED: "Returned to sender",
    S.CANCELLED: "Cancelled",
}


@dataclass(frozen=True, slots=True)
class _Content:
    """What an activity or a notification shows."""

    title: str
    message: str
    critical: str
    progress: int
    progress_max: int
    icon: str
    color: str
    relevance: float
    when: int | None
    status: str
    url: str


def _status_texts(state: ParcelState, today: date) -> tuple[str, str]:
    """Return the status line and the short critical text of a parcel."""
    status = state.status
    eta = state.eta
    expected_today = eta is not None and eta.end == today and status in EN_ROUTE
    later = eta.end if eta is not None and eta.end > today else None
    window = _window_text(eta) if expected_today else None
    short = _window_short(eta) if expected_today else None
    if status is S.OUT_FOR_DELIVERY:
        text, critical = "Out for delivery", short or "Today"
    elif status is S.DELIVERED:
        delivered = _delivered_time(state)
        at = _local_hm(delivered) if delivered is not None else None
        text = f"Delivered {CHECK} {at}" if at else f"Delivered {CHECK}"
        critical = f"{CHECK} {at}" if at else CHECK
    elif status is S.READY_FOR_PICKUP:
        text, critical = "Ready for pickup", "Pickup"
    elif status in PROBLEMS:
        text = _STATUS_TEXT[status]
        critical = "Missed" if status is S.ATTEMPTED else "Problem"
        if later is not None:
            text += f"{SEP}Expected {_day_word(later, today)}"
    elif expected_today:
        text, critical = "Expected today", short or "Today"
    elif later is not None and status in EN_ROUTE:
        text = f"Expected {_day_word(later, today)}"
        critical = (
            "Tomorrow"
            if later == today + timedelta(days=1)
            else f"{_WEEKDAYS[later.weekday()]} {later.day}"
        )
    elif eta is not None and eta.end < today and status in EN_ROUTE:
        text, critical = "Delayed", "Delayed"
    else:
        text, critical = _STATUS_TEXT.get(status, "In transit"), "Soon"
    if window:
        text += f" {window}"
    return text, critical


def _parcel_content(
    parcel: Parcel, ctx: _Context, possibly: Sequence[str] = ()
) -> _Content:
    """Return what a parcel's activity or notification shows.

    ``possibly`` lists the items of the orders the package may hold.
    """
    state = parcel.state
    text, critical = _status_texts(state, ctx.today)
    title = _title(state)
    parts = [text]
    if state.status is S.READY_FOR_PICKUP and (point := _clean(state.pickup_point)):
        parts.append(point)
    carrier = _clean(state.carrier_name)
    if carrier and carrier.casefold() != title.casefold():
        parts.append(carrier)
    if ctx.options.item_names and not parcel.private:
        if state.items:
            item = _clean(state.items[0], 30)
            more = len(state.items) - 1
            parts.append(f"{item} +{more} more" if more else item)
        elif (name := _clean(state.name, 30)) and name.casefold() not in {
            shown.casefold() for shown in (title, *parts)
        }:
            # What the user calls it in the Parcel app, unless it's the shop.
            parts.append(name)
        elif possibly:
            more = len(possibly) - 1
            parts.append(
                f"Possibly: {_clean(possibly[0], 30)}" + (f" (+{more})" if more else "")
            )
    end = _chronometer_end(state, ctx)
    return _Content(
        title=title,
        message=SEP.join(parts),
        critical=critical,
        progress=max(1, min(PROGRESS_MAX, STATUS_RANK.get(state.status, 1))),
        progress_max=PROGRESS_MAX,
        icon=ICONS.get(state.status, DEFAULT_ICON),
        color=COLORS.get(state.status, DEFAULT_COLOR),
        relevance=_relevance(state, ctx),
        when=int(end.timestamp()) if end is not None else None,
        status=state.status.value,
        url=_detail_url(ctx.options.path, "parcel", parcel.id),
    )


def _packages(
    data: ParcelsData, parcels: list[Parcel], day: date
) -> tuple[list[Parcel], dict[str, list[str]]]:
    """Return the parcels that count on a day, and what each package may hold.

    An order that one of the day's packages may hold rides along with it and
    doesn't count. Each package gets the items of the public orders it may
    hold.
    """
    covered = boxes_of_day(data, parcels, day)
    items: dict[str, list[str]] = {}
    for parcel in parcels:
        if not parcel.private:
            for box in covered.get(parcel.id, ()):
                items.setdefault(box, []).extend(parcel.state.items)
    return (
        [parcel for parcel in parcels if parcel.id not in covered],
        {box: unique_items(names) for box, names in items.items()},
    )


def _next_state(states: list[ParcelState], today: date) -> ParcelState | None:
    """Return the parcel expected next: out for delivery first, then by window."""
    candidates = [
        state
        for state in states
        if state.status is S.OUT_FOR_DELIVERY
        or (
            state.status in EN_ROUTE
            and state.eta is not None
            and state.eta.end == today
        )
    ]

    def order(state: ParcelState) -> tuple[bool, bool, time]:
        eta = state.eta
        window = (eta.window_start or eta.window_end) if eta is not None else None
        return (
            state.status is not S.OUT_FOR_DELIVERY,
            window is None,
            window or time.max,
        )

    return min(candidates, key=order, default=None)


def _next_label(state: ParcelState) -> str:
    """Return who brings the next delivery: Amazon via Paack, else either name."""
    shop = _clean(state.merchant, MAX_NAME)
    carrier = _clean(state.carrier_name, MAX_NAME)
    if shop and carrier and shop.casefold() != carrier.casefold():
        return f"{shop} via {carrier}"
    return shop or carrier or "Parcel"


def _combined_content(parcels: list[Parcel], ctx: _Context) -> _Content:
    """Return what a device's combined activity shows."""
    states = [parcel.state for parcel in parcels]
    total = len(states)
    counts = Counter(state.status for state in states)
    delivered = counts[S.DELIVERED]
    pickup = counts[S.READY_FOR_PICKUP]
    problems = counts[S.ATTEMPTED] + counts[S.EXCEPTION]
    out = counts[S.OUT_FOR_DELIVERY]
    done = bool(total) and delivered == total
    parts = [f"{delivered} of {total} delivered" + (f" {CHECK}" if done else "")]
    if pickup:
        parts.append(f"{pickup} ready for pickup")
    if problems:
        parts.append(f"{problems} problem" + ("s" if problems > 1 else ""))
    when: int | None = None
    if (upcoming := _next_state(states, ctx.today)) is not None:
        label = _next_label(upcoming)
        if short := _window_short(upcoming.eta):
            parts.append(f"next: {label} {short}")
        elif upcoming.status is S.OUT_FOR_DELIVERY:
            parts.append(f"{label} out for delivery")
        # The timer would hide the text that names a problem.
        if not problems and (end := _chronometer_end(upcoming, ctx)) is not None:
            when = int(end.timestamp())
    # The most urgent parcel leads the icon and the colour.
    if out:
        lead: ParcelStatus | None = S.OUT_FOR_DELIVERY
    elif done:
        lead = S.DELIVERED
    elif problems:
        lead = S.EXCEPTION
    elif pickup:
        lead = S.READY_FOR_PICKUP
    else:
        lead = None
    relevance = max(
        (_relevance(state, ctx) for state in states if state.status is not S.DELIVERED),
        default=0.2,
    )
    return _Content(
        title=COMBINED_TITLE,
        message=SEP.join(parts),
        critical=f"{delivered}/{total}",
        progress=delivered,
        progress_max=max(total, 1),
        icon=ICONS[lead] if lead is not None else DEFAULT_ICON,
        color=COLORS[lead] if lead is not None else DEFAULT_COLOR,
        relevance=relevance,
        when=when,
        status=f"{delivered}/{total}/{out}/{pickup}/{problems}",
        url=ctx.options.path,
    )


def _activity_payload(
    content: _Content, tag: str, title: str, *, silent: bool
) -> dict[str, Any]:
    """Return the notify payload that starts or updates a Live Activity.

    Every update repeats the colours, the link and the relevance, which an
    update without them isn't guaranteed to keep.
    """
    data: dict[str, Any] = {
        "tag": tag,
        "live_update": True,
        "critical_text": content.critical,
        "progress": content.progress,
        "progress_max": content.progress_max,
        "notification_icon": content.icon,
        "notification_icon_color": content.color,
        "progress_bar_color": content.color,
        "url": content.url,
        "relevance_score": content.relevance,
    }
    if content.when is not None:
        data["chronometer"] = True
        data["when"] = content.when
    if silent:
        data["silent"] = True
    return {"title": title, "message": content.message, "data": data}


def _end_payload(tag: str) -> dict[str, Any]:
    """Return the notify payload that ends a Live Activity."""
    return {"message": CLEAR_NOTIFICATION, "data": {"tag": tag}}


def _key_payload(content: _Content, parcel_id: str, kind: DeviceKind) -> dict[str, Any]:
    """Return a normal notification for an iPad or an Android phone.

    Android tints the icon with the status colour; iPad notifications have no
    colour.
    """
    data: dict[str, Any] = {"tag": _parcel_tag(parcel_id)}
    if kind is DeviceKind.ANDROID:
        data["clickAction"] = content.url
        data["notification_icon"] = content.icon
        data["color"] = content.color
    else:
        data["url"] = content.url
    return {"title": content.title, "message": content.message, "data": data}


def _test_payload(now: datetime, path: str) -> dict[str, Any]:
    """Return the demo Live Activity."""
    return {
        "title": PERSISTENT_TITLE,
        "message": f"Test{SEP}Out for delivery 13:00{DASH}14:00",
        "data": {
            "tag": TEST_TAG,
            "live_update": True,
            "critical_text": "Test",
            "progress": 3,
            "progress_max": PROGRESS_MAX,
            "notification_icon": ICONS[S.OUT_FOR_DELIVERY],
            "notification_icon_color": COLORS[S.OUT_FOR_DELIVERY],
            "progress_bar_color": COLORS[S.OUT_FOR_DELIVERY],
            "url": path,
            "relevance_score": 0.5,
            "chronometer": True,
            "when": int((now + TEST_ACTIVITY_DURATION).timestamp()),
        },
    }


def _fingerprint(payload: Mapping[str, Any]) -> str:
    """Return a fingerprint of a payload, ignoring how quietly it is sent."""
    data = {key: value for key, value in payload["data"].items() if key != "silent"}
    raw = json.dumps(
        {
            "title": payload.get("title"),
            "message": payload.get("message"),
            "data": data,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


_GROUPS: dict[ParcelStatus, int] = {
    S.OUT_FOR_DELIVERY: 0,
    S.ATTEMPTED: 1,
    S.EXCEPTION: 1,
    S.READY_FOR_PICKUP: 2,
    S.DELIVERED: 4,
}


def _delivered_time(state: ParcelState) -> datetime | None:
    """Return when a parcel was delivered, or None when the time isn't known."""
    if state.delivered_undated:
        return None
    return state.delivered_at or state.status_time


def _shown_on(state: ParcelState, day: date) -> bool:
    """Return True when the persistent notification of a day lists a parcel."""
    status = state.status
    if status is S.DELIVERED:
        delivered = state.delivered_at or state.status_time
        return delivered is not None and local_date(delivered) == day
    if _expected_today(state, day):
        return True
    changed = local_date(state.status_time) if state.status_time is not None else None
    if changed is None:
        return False
    if status is S.READY_FOR_PICKUP:
        return day - timedelta(days=PICKUP_DAYS) < changed <= day
    return changed == day and (status is S.OUT_FOR_DELIVERY or status in PROBLEMS)


def _persistent_status(state: ParcelState, day: date, today: date) -> str:
    """Return the status of a parcel in the persistent notification."""
    status = state.status
    eta = state.eta
    expected = eta is not None and eta.end == day and status in EN_ROUTE
    if status is S.OUT_FOR_DELIVERY:
        text = "Out for delivery"
    elif status is S.DELIVERED:
        delivered = _delivered_time(state)
        text = (
            f"Delivered {_local_hm(delivered)} {CHECK}"
            if delivered is not None
            else f"Delivered {CHECK}"
        )
    elif status is S.READY_FOR_PICKUP:
        text = "Ready for pickup"
        if point := _clean(state.pickup_point):
            text += f" at {point}"
    elif status in PROBLEMS:
        text = _STATUS_TEXT[status]
        if eta is not None and eta.end > day:
            text += f", expected {_day_word(eta.end, today)}"
    elif expected:
        text = f"Expected {_day_word(day, today)}"
    elif eta is not None and eta.end > day:
        text = f"Moved to {_day_word(eta.end, today)}"
    else:
        text = _STATUS_TEXT.get(status, "In transit")
    if expected and (window := _window_text(eta)):
        text += f" {window}"
    return text


def _persistent_order(state: ParcelState) -> tuple[int, int, str]:
    """Sort out for delivery first, then problems, pickups, expected, delivered."""
    status = state.status
    moment: time | None = None
    if status in EN_ROUTE and state.eta is not None:
        moment = state.eta.window_start or state.eta.window_end
    elif status is S.DELIVERED:
        if (at := _delivered_time(state)) is not None:
            moment = dt_util.as_local(at).time()
    elif state.status_time is not None and not state.status_undated:
        moment = dt_util.as_local(state.status_time).time()
    minutes = moment.hour * 60 + moment.minute if moment is not None else 24 * 60
    return _GROUPS.get(status, 3), minutes, _title(state).casefold()


def _persistent_message(
    listed: list[tuple[str, ParcelState]],
    private: int,
    day: date,
    today: date,
    path: str,
    riders: Sequence[tuple[ParcelState, Sequence[ParcelState]]] = (),
) -> str:
    """Return the Markdown of the persistent notification.

    ``listed`` pairs each parcel with its shipment. Packages of one shipment
    with the same status share a line; a delivered one keeps its own, with
    its time. The count in the title stays in packages. ``riders`` pairs each
    public order that packages of the day may hold with those packages; the
    orders of a shop that the same packages may hold share a line.
    """
    total = len(listed) + private
    lines = [
        f"**{total} parcel{'' if total == 1 else 's'} {_day_word(day, today)}**",
        "",
    ]
    rows: dict[tuple[str, str, int], list[ParcelState]] = {}
    ordered = sorted(listed, key=lambda item: _persistent_order(item[1]))
    for index, (shipment, state) in enumerate(ordered):
        status = _persistent_status(state, day, today)
        alone = index if state.status is S.DELIVERED else -1
        rows.setdefault((shipment, status, alone), []).append(state)
    for (_, status, _), states in rows.items():
        parts = _names(states[0]) or ["Parcel"]
        if len(states) > 1:
            parts.append(f"{len(states)} packages")
        parts.append(status)
        lines.append("- " + SEP.join(_markdown(part) for part in parts))
    orders: Counter[tuple[str, tuple[str, ...]]] = Counter()
    for state, boxes in riders:
        labels: list[str] = []
        for box in boxes:
            label = _clean(box.carrier_name) or _title(box)
            if label.casefold() not in {known.casefold() for known in labels}:
                labels.append(label)
        orders[_title(state), tuple(labels)] += 1
    for (title, labels), count in sorted(
        orders.items(),
        key=lambda row: (row[0][0].casefold(), [x.casefold() for x in row[0][1]]),
    ):
        where = labels[-1]
        if len(labels) > 1:
            where = f"{', '.join(labels[:-1])} or {where}"
        parts = [
            title,
            f"{count} order{'' if count == 1 else 's'}",
            f"Possibly in a package from {where}",
        ]
        lines.append("- " + SEP.join(_markdown(part) for part in parts))
    if private:
        lines.append(f"- +{private} private parcel{'' if private == 1 else 's'}")
    lines += ["", f"[Open Parcels]({path})"]
    return "\n".join(lines)


def _new_day() -> dict[str, Any]:
    """Return the state of a new day."""
    return {
        "morning": False,
        "board": [],
        "combined": [],
        "activities": {},
        "notified": {},
    }


def _strings(value: Any) -> list[str]:
    """Return the unique strings of a stored list."""
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(item for item in value if isinstance(item, str) and item))


def _optional_str(value: Any) -> str | None:
    """Return a stored string, or None."""
    return value if isinstance(value, str) and value else None


def _sanitize_record(raw: Any) -> dict[str, Any] | None:
    """Return a stored activity, or None when it is unusable."""
    if not isinstance(raw, Mapping):
        return None
    tag = _optional_str(raw.get("tag"))
    started = _parse_dt(raw.get("started"))
    if tag is None or started is None:
        return None
    gen = raw.get("gen")
    if not isinstance(gen, int) or isinstance(gen, bool) or gen < 1:
        gen = 1
    end_at = _parse_dt(raw.get("end_at"))
    linger = raw.get("linger")
    return {
        "tag": tag[:MAX_TAG],
        "gen": gen,
        "title": _optional_str(raw.get("title")) or "Parcel",
        "started": _iso(started),
        "running": raw.get("running") is True,
        "end_reason": _optional_str(raw.get("end_reason")),
        "end_at": _iso(end_at) if end_at is not None else None,
        "linger": linger if linger in (REASON_DELIVERED, REASON_MOVED) else None,
        "fp": _optional_str(raw.get("fp")),
        "status": _optional_str(raw.get("status")),
        "service": _optional_str(raw.get("service")),
    }


def _sanitize_day(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return the stored state of a day, dropping anything unusable."""
    day = _new_day()
    day["morning"] = raw.get("morning") is True
    day["board"] = _strings(raw.get("board"))
    day["combined"] = _strings(raw.get("combined"))
    activities = raw.get("activities")
    if isinstance(activities, Mapping):
        for device_id, records in activities.items():
            if not isinstance(device_id, str) or not isinstance(records, Mapping):
                continue
            clean = {
                key: record
                for key, value in records.items()
                if isinstance(key, str) and (record := _sanitize_record(value))
            }
            if clean:
                day["activities"][device_id] = clean
    notified = raw.get("notified")
    if isinstance(notified, Mapping):
        for device_id, sent in notified.items():
            if not isinstance(device_id, str) or not isinstance(sent, Mapping):
                continue
            clean_sent = {
                parcel_id: status
                for parcel_id, status in sent.items()
                if isinstance(parcel_id, str) and isinstance(status, str)
            }
            if clean_sent:
                day["notified"][device_id] = clean_sent
    return day


def _sanitize_state(raw: Any) -> dict[str, Any]:
    """Return the stored notifier state, dropping anything unusable."""
    state: dict[str, Any] = {
        "version": STATE_VERSION,
        "live_activities": True,
        "daily_notification": True,
        "days": {},
    }
    if not isinstance(raw, Mapping):
        return state
    for key in ("live_activities", "daily_notification"):
        if isinstance(raw.get(key), bool):
            state[key] = raw[key]
    days = raw.get("days")
    if isinstance(days, Mapping):
        for key, day in sorted(days.items()):
            if isinstance(key, str) and _parse_date(key) and isinstance(day, Mapping):
                state["days"][key] = _sanitize_day(day)
    test = raw.get("test")
    if isinstance(test, Mapping):
        device = _optional_str(test.get("device"))
        end_at = _parse_dt(test.get("end_at"))
        if device is not None and end_at is not None:
            state["test"] = {
                "device": device,
                "service": _optional_str(test.get("service")),
                "end_at": _iso(end_at),
            }
    return state


def _describe_error(err: BaseException) -> str:
    """Describe an unexpected error without its message, which may hold content."""
    frames = traceback.extract_tb(err.__traceback__)
    where = f" in {frames[-1].name}:{frames[-1].lineno}" if frames else ""
    return f"{type(err).__name__}{where}"


class Notifier:
    """Send the day's parcels to phones and keep a persistent notification."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, host: NotifierHost
    ) -> None:
        """Initialise the notifier and restore its state from the engine data."""
        self.hass = hass
        self.entry = entry
        self._host = host
        self._state: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None
        self._unsub_started: CALLBACK_TYPE | None = None
        self._ready = False
        self._stopped = False
        self._retry_at: datetime | None = None
        self._wake_points: list[datetime] = []
        self._persistent_fp: str | None = _UNKNOWN
        self._devices: dict[str, _Device] = {}
        self._recipients: dict[str, _Device] = {}
        self._saved = json.dumps(self._data, sort_keys=True)

    @property
    def _data(self) -> dict[str, Any]:
        """Return the notifier state, kept JSON-safe in the engine data."""
        engine = self._host.data.engine
        if engine.get(STATE_KEY) is not self._state:
            self._state = _sanitize_state(engine.get(STATE_KEY))
            engine[STATE_KEY] = self._state
        return self._state

    @property
    def live_activities_enabled(self) -> bool:
        """Return True when Live Activities and phone notifications are on."""
        return bool(self._data["live_activities"])

    @property
    def daily_notification_enabled(self) -> bool:
        """Return True when the persistent notification is on."""
        return bool(self._data["daily_notification"])

    async def async_start(self) -> None:
        """Start: evaluate now, or as soon as Home Assistant has started."""
        if self._debouncer is not None:
            return
        self._stopped = False
        self._debouncer = Debouncer(
            self.hass,
            _LOGGER,
            cooldown=DEBOUNCE_COOLDOWN,
            immediate=False,
            function=self._async_evaluate,
        )
        if self.hass.state is CoreState.running:
            await self._async_evaluate()
        else:
            self._unsub_started = async_at_started(self.hass, self._async_hass_started)

    async def _async_hass_started(self, _hass: HomeAssistant) -> None:
        """Evaluate once Home Assistant and the mobile apps are ready."""
        self._unsub_started = None
        await self._async_evaluate()

    async def async_stop(self) -> None:
        """Stop listening, without ending activities or notifications."""
        self._stopped = True
        if self._unsub_started is not None:
            self._unsub_started()
            self._unsub_started = None
        self._cancel_timer()
        if self._debouncer is not None:
            self._debouncer.async_shutdown()
            self._debouncer = None
        async with self._lock:
            self._cancel_timer()
            self._save_if_changed()

    @callback
    def async_parcels_changed(self) -> None:
        """Re-evaluate shortly after the parcels changed; bursts are merged."""
        if self._stopped or not self._ready or self._debouncer is None:
            return
        self._debouncer.async_schedule_call()

    async def async_set_live_activities(self, enabled: bool) -> None:
        """Turn Live Activities and phone notifications on or off.

        Turning them off ends every running activity.
        """
        async with self._lock:
            self._data["live_activities"] = enabled
            self._save_if_changed()
        await self._async_refresh()

    async def async_set_daily_notification(self, enabled: bool) -> None:
        """Turn the persistent notification on or off."""
        async with self._lock:
            self._data["daily_notification"] = enabled
            if not enabled:
                self._dismiss_persistent()
            self._save_if_changed()
        await self._async_refresh()

    async def _async_refresh(self) -> None:
        """Evaluate now when the notifier is running."""
        if self._ready and not self._stopped:
            await self._async_evaluate()

    async def async_test_live_activity(self, device_id: str | None = None) -> None:
        """Send a demo Live Activity to one iPhone and end it a minute later.

        Without a device the test device is used, else the first iPhone that
        normally gets notifications. In test mode only the test device is used.
        """
        async with self._lock:
            if self._stopped:
                raise _user_error("test_not_running")
            now = dt_util.utcnow()
            options = _Options.from_entry(self.entry)
            self._devices = self._discover_devices()
            device = self._test_target(device_id, options)
            test = self._data.get("test")
            if test is not None and test["device"] != device.device_id:
                await self._async_end_test(now, force=True)
            result = await self._async_send(
                device.service, device.kind, _test_payload(now, options.path)
            )
            if result is _Result.MISSING:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="test_app_unregistered"
                )
            if result is _Result.FAILED:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="test_send_failed"
                )
            self._data["test"] = {
                "device": device.device_id,
                "service": device.service,
                "end_at": _iso(now + TEST_ACTIVITY_DURATION),
            }
            self._save_if_changed()
            if not self._stopped:
                self._schedule_timer(self._context(now, options))

    def _test_target(self, device_id: str | None, options: _Options) -> _Device:
        """Return the iPhone that gets the demo Live Activity."""
        if device_id is not None:
            device = self._devices.get(device_id)
            if device is None or device.kind is not DeviceKind.IPHONE:
                raise _user_error("test_not_iphone")
            return device
        if options.test_mode or options.test_device is not None:
            test_device = (
                self._devices.get(options.test_device) if options.test_device else None
            )
            if test_device is not None and test_device.kind is DeviceKind.IPHONE:
                return test_device
            if options.test_mode:
                raise _user_error("test_mode_not_iphone")
        for device in self._recipients_for(replace(options, test_mode=False)).values():
            if device.kind is DeviceKind.IPHONE:
                return device
        raise _user_error("test_no_iphone")

    def diagnostics(self) -> dict[str, Any]:
        """Return counts for the diagnostics, without names or IDs."""
        state = self._data
        options = _Options.from_entry(self.entry)
        today = dt_util.now().date()
        day = state["days"].get(today.isoformat()) or _new_day()
        parcels = {parcel.id: parcel for parcel in self._host.visible_parcels()}
        board = [
            parcel
            for parcel_id in day["board"]
            if (parcel := parcels.get(parcel_id)) is not None
            and parcel.state.status not in GONE
        ]
        records = [
            record
            for records in day["activities"].values()
            for record in records.values()
        ]
        return {
            "live_activities": state["live_activities"],
            "daily_notification": state["daily_notification"],
            "started": self._ready and not self._stopped,
            "test_mode": options.test_mode,
            "test_device_set": options.test_device is not None,
            "notify_persons": len(options.persons),
            "excluded_devices": len(options.excluded),
            "devices": dict(Counter(d.kind.value for d in self._devices.values())),
            "recipients": dict(
                Counter(d.kind.value for d in self._recipients.values())
            ),
            "today": {
                "parcels": len(day["board"]),
                "morning_done": day["morning"],
                "combined_devices": len(day["combined"]),
                "activities": len(records),
                "activity_starts": sum(record["gen"] for record in records),
                "running": sum(1 for record in records if record["running"]),
                "notifications_sent": sum(len(s) for s in day["notified"].values()),
                "orders_in_a_box": len(boxes_of_day(self._host.data, board, today)),
            },
            "persistent_notification_shown": self._persistent_fp
            not in (None, _UNKNOWN),
            "days_stored": len(state["days"]),
            "test_activity_running": "test" in state,
        }

    async def _async_evaluate(self) -> None:
        """Bring activities, notifications and the timer up to date."""
        async with self._lock:
            if self._stopped:
                return
            self._ready = True
            self._cancel_timer()
            self._retry_at = None
            ctx = self._context(dt_util.utcnow(), _Options.from_entry(self.entry))
            try:
                await self._async_evaluate_locked(ctx)
            except Exception as err:
                _LOGGER.error(
                    "Updating the parcel notifications failed: %s",
                    _describe_error(err),
                )
            finally:
                self._save_if_changed()
                self._schedule_timer(ctx)

    async def _async_evaluate_locked(self, ctx: _Context) -> None:
        """Evaluate everything; the caller holds the lock."""
        self._devices = self._discover_devices()
        self._recipients = self._recipients_for(ctx.options)
        await self._async_close_past_days(ctx)
        await self._async_end_test(ctx.now, force=not self.live_activities_enabled)
        parcels = {parcel.id: parcel for parcel in self._host.visible_parcels()}
        # Chronometers appear and disappear with today's delivery windows.
        self._wake_points = [
            moment
            for parcel in parcels.values()
            if (eta := parcel.state.eta) is not None and eta.end == ctx.today
            for moment in _wake_moments(eta, ctx.today)
        ]
        days: dict[str, Any] = self._data["days"]
        if ctx.in_window:
            day = days.setdefault(ctx.key, _new_day())
            self._update_board(ctx, day, parcels)
        else:
            day = days.get(ctx.key)
        if day is not None:
            for device_id in sorted(set(self._recipients) | set(day["activities"])):
                await self._async_device(ctx, day, device_id, parcels)
        self._update_persistent(ctx, parcels)

    @staticmethod
    def _context(now: datetime, options: _Options) -> _Context:
        """Return the context of an evaluation at a point in time."""
        today = dt_util.as_local(now).date()
        start, cutoff = _window(today, options)
        return _Context(
            now=now,
            today=today,
            start=start,
            cutoff=cutoff,
            prev_cutoff=_window(today - timedelta(days=1), options)[1],
            options=options,
        )

    def _discover_devices(self) -> dict[str, _Device]:
        """Return the enabled mobile_app devices, with their notify service name."""
        registry = dr.async_get(self.hass)
        persons: dict[str, set[str]] = {}
        for state in self.hass.states.async_all(PERSON_DOMAIN):
            user_id = state.attributes.get("user_id")
            if isinstance(user_id, str) and user_id:
                persons.setdefault(user_id, set()).add(state.entity_id)
        by_service: dict[str, _Device] = {}
        for entry in self.hass.config_entries.async_entries(
            MOBILE_APP_DOMAIN, include_ignore=False, include_disabled=False
        ):
            name = entry.data.get("device_name")
            if not isinstance(name, str) or not name:
                continue
            device = self._registry_device(registry, entry)
            if device is None or device.disabled:
                continue
            user_id = entry.data.get("user_id")
            # Like mobile_app: a later device with the same name takes the service.
            service = slugify(f"mobile_app_{name}")
            by_service[service] = _Device(
                device_id=device.id,
                service=service,
                kind=classify_device(entry.data),
                persons=frozenset(
                    persons.get(user_id, ()) if isinstance(user_id, str) else ()
                ),
            )
        return {device.device_id: device for device in by_service.values()}

    @staticmethod
    def _registry_device(
        registry: dr.DeviceRegistry, entry: ConfigEntry
    ) -> dr.DeviceEntry | None:
        """Return the registry device of a mobile_app config entry.

        Device identifiers are only unique within a config entry, so the device is
        looked up among the entry's own devices.
        """
        device_id = entry.data.get("device_id")
        if isinstance(device_id, str) and device_id:
            device = registry.async_get_device_by_identifier(
                (MOBILE_APP_DOMAIN, device_id), entry.entry_id
            )
            if device is not None:
                return device
        devices = dr.async_entries_for_config_entry(registry, entry.entry_id)
        return devices[0] if devices else None

    def _recipients_for(self, options: _Options) -> dict[str, _Device]:
        """Return the devices that get notifications."""
        if options.test_mode:
            device = (
                self._devices.get(options.test_device) if options.test_device else None
            )
            if device is None or device.kind is DeviceKind.OTHER:
                return {}
            return {device.device_id: device}
        return {
            device_id: device
            for device_id, device in self._devices.items()
            if device.kind is not DeviceKind.OTHER
            and device_id not in options.excluded
            and device.persons & options.persons
        }

    async def _async_close_past_days(self, ctx: _Context) -> None:
        """End what is left of earlier days and forget days before yesterday."""
        days: dict[str, Any] = self._data["days"]
        for key in sorted(days):
            day_date = _parse_date(key)
            if day_date is not None and day_date >= ctx.today:
                continue
            for device_id, records in days[key]["activities"].items():
                for record in records.values():
                    if record["running"]:
                        await self._async_end(device_id, record, REASON_CUTOFF, ctx.now)
            if day_date is None or day_date < ctx.today - timedelta(days=1):
                del days[key]

    @staticmethod
    def _joins(state: ParcelState, ctx: _Context) -> bool:
        """Return True when a parcel joins the day after the start time."""
        if state.status is S.OUT_FOR_DELIVERY and state.eta is not None:
            return state.eta.end == ctx.today
        if state.status in (S.OUT_FOR_DELIVERY, S.READY_FOR_PICKUP):
            return (
                state.status_time is not None and state.status_time >= ctx.prev_cutoff
            )
        return False

    def _update_board(
        self, ctx: _Context, day: dict[str, Any], parcels: dict[str, Parcel]
    ) -> None:
        """Add the parcels that are on the lock screen today; none leave."""
        board: list[str] = day["board"]
        added = set(board)
        candidates: list[Parcel] = []
        if not day["morning"]:
            day["morning"] = True
            candidates += [
                parcel
                for parcel in parcels.values()
                if _expected_today(parcel.state, ctx.today)
                and parcel.state.status is not S.READY_FOR_PICKUP
            ]
        candidates += [p for p in parcels.values() if self._joins(p.state, ctx)]
        for parcel in candidates:
            if parcel.id not in added:
                added.add(parcel.id)
                board.append(parcel.id)

    async def _async_device(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device_id: str,
        parcels: dict[str, Parcel],
    ) -> None:
        """Bring one device up to date."""
        device = self._recipients.get(device_id)
        if device is None:
            await self._async_end_all(ctx, day, device_id, REASON_REMOVED)
        elif device.kind is DeviceKind.IPHONE:
            await self._async_live_device(ctx, day, device, parcels)
        else:
            await self._async_end_all(ctx, day, device_id, REASON_REMOVED)
            await self._async_key_notifications(ctx, day, device, parcels)

    async def _async_end_all(
        self, ctx: _Context, day: dict[str, Any], device_id: str, reason: str
    ) -> None:
        """End every running activity of a device."""
        for record in day["activities"].get(device_id, {}).values():
            if record["running"]:
                await self._async_end(device_id, record, reason, ctx.now)

    async def _async_live_device(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        parcels: dict[str, Parcel],
    ) -> None:
        """Bring the Live Activities of one iPhone up to date."""
        device_id = device.device_id
        if not ctx.in_window:
            await self._async_end_all(ctx, day, device_id, REASON_CUTOFF)
            return
        if not self.live_activities_enabled:
            await self._async_end_all(ctx, day, device_id, REASON_DISABLED)
            return
        members: list[Parcel] = []
        moved: list[Parcel] = []
        for parcel_id in day["board"]:
            parcel = parcels.get(parcel_id)
            if parcel is None or not _routed(parcel, device):
                continue
            state = parcel.state
            if state.status in GONE:
                continue
            if (
                state.status in MOVABLE
                and state.eta is not None
                and state.eta.end > ctx.today
            ):
                moved.append(parcel)
            else:
                members.append(parcel)
        entries, possibly = _packages(self._host.data, members, ctx.today)
        records: dict[str, Any] = day["activities"].get(device_id, {})
        if device_id in day["combined"] or len(entries) > ctx.options.threshold:
            if device_id not in day["combined"]:
                day["combined"].append(device_id)
            for key, record in records.items():
                if key != COMBINED and record["running"]:
                    await self._async_end(device_id, record, REASON_COLLAPSED, ctx.now)
            await self._async_combined(ctx, day, device, entries)
            return
        keep = {parcel.id for parcel in (*entries, *moved)}
        for key, record in records.items():
            if record["running"] and key not in keep:
                await self._async_end(device_id, record, REASON_REMOVED, ctx.now)
        for parcel in entries:
            await self._async_individual(
                ctx, day, device, parcel, possibly.get(parcel.id, ())
            )
        for parcel in moved:
            record = day["activities"].get(device_id, {}).get(parcel.id)
            if record is not None and record["running"]:
                content = _parcel_content(parcel, ctx)
                await self._async_linger(ctx, device, record, content, REASON_MOVED)

    async def _async_individual(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        parcel: Parcel,
        possibly: Sequence[str] = (),
    ) -> None:
        """Start, update, restart or end the activity of one parcel."""
        record = day["activities"].get(device.device_id, {}).get(parcel.id)
        status = parcel.state.status
        content = _parcel_content(parcel, ctx, possibly)
        if record is None or not record["running"]:
            if status is S.DELIVERED:
                return
            if record is None:
                await self._async_start(ctx, day, device, parcel.id, 1, content)
            elif record["end_reason"] in RESTARTABLE or (
                record["end_reason"] == REASON_MOVED and status is S.OUT_FOR_DELIVERY
            ):
                gen = record["gen"] + 1
                await self._async_start(ctx, day, device, parcel.id, gen, content)
            return
        if status is S.DELIVERED:
            await self._async_linger(ctx, device, record, content, REASON_DELIVERED)
            return
        record["linger"] = record["end_at"] = None
        await self._async_keep_alive(ctx, day, device, parcel.id, record, content)

    async def _async_combined(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        members: list[Parcel],
    ) -> None:
        """Start, update, restart or end the combined activity of one iPhone."""
        record = day["activities"].get(device.device_id, {}).get(COMBINED)
        pending = any(parcel.state.status is not S.DELIVERED for parcel in members)
        content = _combined_content(members, ctx)
        if record is None or not record["running"]:
            if not pending:
                return
            if record is None:
                await self._async_start(ctx, day, device, COMBINED, 1, content)
            elif record["end_reason"] in (*RESTARTABLE, REASON_DELIVERED):
                gen = record["gen"] + 1
                await self._async_start(ctx, day, device, COMBINED, gen, content)
            return
        if not members:
            await self._async_end(device.device_id, record, REASON_REMOVED, ctx.now)
            return
        if not pending:
            await self._async_linger(ctx, device, record, content, REASON_DELIVERED)
            return
        record["linger"] = record["end_at"] = None
        await self._async_keep_alive(ctx, day, device, COMBINED, record, content)

    async def _async_keep_alive(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        key: str,
        record: dict[str, Any],
        content: _Content,
    ) -> None:
        """Update an activity, restarting it before Apple ends it after 8 hours."""
        started = _parse_dt(record["started"])
        if (
            started is not None
            and ctx.now >= started + RESTART_AFTER - DUE_TOLERANCE
            and started + APPLE_LIMIT < ctx.cutoff
        ):
            if await self._async_end(device.device_id, record, REASON_RESTART, ctx.now):
                gen = record["gen"] + 1
                await self._async_start(ctx, day, device, key, gen, content)
            return
        await self._async_update(ctx, device, record, content)

    async def _async_linger(
        self,
        ctx: _Context,
        device: _Device,
        record: dict[str, Any],
        content: _Content,
        reason: str,
    ) -> None:
        """Show a final state for 30 minutes, then end the activity."""
        end_at = _parse_dt(record["end_at"])
        if record["linger"] != reason or end_at is None:
            end_at = ctx.now + DELIVERED_LINGER
            record["linger"] = reason
            record["end_at"] = _iso(end_at)
        if ctx.now >= end_at - DUE_TOLERANCE:
            await self._async_end(device.device_id, record, reason, ctx.now)
        else:
            await self._async_update(ctx, device, record, content)

    async def _async_start(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        key: str,
        gen: int,
        content: _Content,
    ) -> bool:
        """Start an activity; return True when it was sent."""
        tag = (
            _combined_tag(ctx.today, gen) if key == COMBINED else _parcel_tag(key, gen)
        )
        payload = _activity_payload(content, tag, content.title, silent=False)
        result = await self._async_send(device.service, device.kind, payload)
        if result is not _Result.SENT:
            if result is _Result.FAILED:
                self._retry(ctx.now)
            return False
        day["activities"].setdefault(device.device_id, {})[key] = {
            "tag": tag,
            "gen": gen,
            "title": content.title,
            "started": _iso(ctx.now),
            "running": True,
            "end_reason": None,
            "end_at": None,
            "linger": None,
            "fp": _fingerprint(payload),
            "status": content.status,
            "service": device.service,
        }
        return True

    async def _async_update(
        self,
        ctx: _Context,
        device: _Device,
        record: dict[str, Any],
        content: _Content,
    ) -> None:
        """Update a running activity when what it shows changed.

        The title stays the one the activity started with; the update is quiet
        when the status didn't change.
        """
        payload = _activity_payload(
            content,
            record["tag"],
            record["title"],
            silent=record["status"] == content.status,
        )
        fingerprint = _fingerprint(payload)
        if fingerprint == record["fp"]:
            record["service"] = device.service
            return
        result = await self._async_send(device.service, device.kind, payload)
        if result is _Result.SENT:
            record["fp"] = fingerprint
            record["status"] = content.status
            record["service"] = device.service
        elif result is _Result.FAILED:
            self._retry(ctx.now)

    async def _async_end(
        self, device_id: str, record: dict[str, Any], reason: str, now: datetime
    ) -> bool:
        """End a running activity; return True when it is over.

        When the end can't be sent the activity is kept and retried, until
        Apple has ended it anyway.
        """
        device = self._devices.get(device_id)
        service = device.service if device is not None else record["service"]
        kind = device.kind if device is not None else DeviceKind.IPHONE
        result = _Result.MISSING
        if service:
            result = await self._async_send(service, kind, _end_payload(record["tag"]))
        started = _parse_dt(record["started"])
        if (
            result is not _Result.SENT
            and started is not None
            and now < started + APPLE_LIMIT
        ):
            self._retry(now)
            return False
        record["running"] = False
        record["end_reason"] = reason
        record["linger"] = record["end_at"] = None
        return True

    async def _async_end_test(self, now: datetime, *, force: bool = False) -> None:
        """End the demo Live Activity when it is due."""
        test = self._data.get("test")
        if test is None:
            return
        end_at = _parse_dt(test["end_at"])
        if not force and end_at is not None and now < end_at - DUE_TOLERANCE:
            return
        device = self._devices.get(test["device"])
        service = device.service if device is not None else test["service"]
        result = _Result.MISSING
        if service:
            result = await self._async_send(
                service, DeviceKind.IPHONE, _end_payload(TEST_TAG)
            )
        if (
            result is _Result.FAILED
            and end_at is not None
            and now < end_at + APPLE_LIMIT
        ):
            self._retry(now)
            return
        del self._data["test"]

    async def _async_send(
        self, service: str, kind: DeviceKind, payload: dict[str, Any]
    ) -> _Result:
        """Call a mobile_app notify service; nothing that is sent is logged."""
        if not self.hass.services.has_service(NOTIFY_DOMAIN, service):
            _LOGGER.debug("A device (%s) has no notify service", kind)
            return _Result.MISSING
        try:
            await self.hass.services.async_call(
                NOTIFY_DOMAIN, service, payload, blocking=True
            )
        except Exception as err:
            _LOGGER.warning(
                "Notifying a device (%s) failed: %s", kind, _describe_error(err)
            )
            return _Result.FAILED
        return _Result.SENT

    def _retry(self, now: datetime) -> None:
        """Evaluate again a little later."""
        at = now + RETRY_DELAY
        if self._retry_at is None or at < self._retry_at:
            self._retry_at = at

    async def _async_key_notifications(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        parcels: dict[str, Parcel],
    ) -> None:
        """Notify an iPad or an Android phone of key changes of today's parcels."""
        if not ctx.in_window or not self.live_activities_enabled:
            return
        board = [
            parcel
            for parcel_id in day["board"]
            if (parcel := parcels.get(parcel_id)) is not None
            and _routed(parcel, device)
            and parcel.state.status not in GONE
        ]
        entries, possibly = _packages(self._host.data, board, ctx.today)
        for parcel in entries:
            status = parcel.state.status
            sent = day["notified"].get(device.device_id, {})
            if status not in KEY_STATUSES or sent.get(parcel.id) == status.value:
                continue
            content = _parcel_content(parcel, ctx, possibly.get(parcel.id, ()))
            payload = _key_payload(content, parcel.id, device.kind)
            result = await self._async_send(device.service, device.kind, payload)
            if result is _Result.SENT:
                day["notified"].setdefault(device.device_id, {})[parcel.id] = (
                    status.value
                )
            elif result is _Result.FAILED:
                self._retry(ctx.now)

    def _update_persistent(self, ctx: _Context, parcels: dict[str, Parcel]) -> None:
        """Create, update or dismiss the persistent notification.

        From the start time it lists today's parcels; before it, yesterday's
        notification stays as it is (only updated) until it is replaced or
        removed at the start time.
        """
        if not self.daily_notification_enabled:
            self._dismiss_persistent()
            return
        shown = ctx.today
        if ctx.now < ctx.start:
            shown = ctx.today - timedelta(days=1)
            if self._persistent_fp in (None, _UNKNOWN):
                self._dismiss_persistent()
                return
        day = self._data["days"].get(shown.isoformat())
        board = set(day["board"]) if day is not None else set()
        # Grouped as the page shows them to someone who sees no private parcel.
        shipments = shipment_groups(
            parcel for parcel in parcels.values() if not parcel.private
        )
        pool = [
            parcel
            for parcel in parcels.values()
            if parcel.state.status not in GONE
            and (parcel.id in board or _shown_on(parcel.state, shown))
        ]
        covered = boxes_of_day(self._host.data, pool, shown)
        listed: list[tuple[str, ParcelState]] = []
        riders: list[tuple[ParcelState, list[ParcelState]]] = []
        private = 0
        for parcel in pool:
            if (boxes := covered.get(parcel.id)) is not None:
                # Counted with its package; a private one isn't named at all.
                if not parcel.private:
                    riders.append((parcel.state, [parcels[box].state for box in boxes]))
            elif parcel.private:
                private += 1
            else:
                listed.append((shipments.get(parcel.id, parcel.id), parcel.state))
        if not listed and not private:
            self._dismiss_persistent()
            return
        message = _persistent_message(
            listed, private, shown, ctx.today, ctx.options.path, riders
        )
        fingerprint = hashlib.sha256(message.encode()).hexdigest()[:16]
        if fingerprint != self._persistent_fp:
            persistent_notification.async_create(
                self.hass,
                message,
                title=PERSISTENT_TITLE,
                notification_id=PERSISTENT_NOTIFICATION_ID,
            )
            self._persistent_fp = fingerprint

    def _dismiss_persistent(self) -> None:
        """Dismiss the persistent notification unless it is known to be gone."""
        if self._persistent_fp is not None:
            persistent_notification.async_dismiss(self.hass, PERSISTENT_NOTIFICATION_ID)
            self._persistent_fp = None

    def _schedule_timer(self, ctx: _Context) -> None:
        """Wake up at the next moment something may change."""
        self._cancel_timer()
        if self._stopped:
            return
        tomorrow = ctx.today + timedelta(days=1)
        points = [
            ctx.start,
            ctx.cutoff,
            _local_at(tomorrow, time(0, 0)),
            _window(tomorrow, ctx.options)[0],
            *self._wake_points,
        ]
        if self._retry_at is not None:
            points.append(self._retry_at)
        test = self._data.get("test")
        if test is not None and (end_at := _parse_dt(test["end_at"])) is not None:
            points.append(end_at)
        day = self._data["days"].get(ctx.key)
        for records in day["activities"].values() if day is not None else ():
            for record in records.values():
                if not record["running"]:
                    continue
                if (end_at := _parse_dt(record["end_at"])) is not None:
                    points.append(end_at)
                started = _parse_dt(record["started"])
                if started is not None and started + APPLE_LIMIT < ctx.cutoff:
                    points.append(started + RESTART_AFTER)
        future = [point for point in points if point > ctx.now]
        if future:
            self._unsub_timer = async_track_point_in_utc_time(
                self.hass, self._async_timer_fired, min(future)
            )

    def _cancel_timer(self) -> None:
        """Cancel the timer."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def _async_timer_fired(self, _now: datetime) -> None:
        """Evaluate when the timer fires."""
        self._unsub_timer = None
        await self._async_evaluate()

    def _save_if_changed(self) -> None:
        """Ask the engine to save when the notifier state changed."""
        snapshot = json.dumps(self._data, sort_keys=True)
        if snapshot != self._saved:
            self._saved = snapshot
            self._host.async_schedule_save()
