"""Lock-screen notifications for Parcels.

The notifier turns the day's parcels into iOS Live Activities, plain
notifications on iPads and Android phones, and one persistent notification in
Home Assistant. The engine creates one :class:`Notifier` for the hub entry,
starts it once the store is loaded, calls :meth:`Notifier.async_parcels_changed`
after every data change and stops it on unload.

Routing
    Only ``notify.mobile_app_<device>`` services are called, never
    ``notify.notify`` or a group; an update with a delivery PIN goes straight
    to that device's mobile_app notify service instead (see Delivery PINs).
    A device is notified when one of its persons
    (a ``person`` whose ``user_id`` is the mobile_app entry's ``user_id``) is in
    the hub's notify persons and the device isn't excluded. In test mode only
    the test device gets anything. Private parcels go only to their owners'
    devices and never show item names; item names reach the lock screen only
    when the hub option allows it.

Device kinds
    iPhones get Live Activities. iPads and Android phones get one normal
    notification per parcel (same tag, each replacing the last) on key changes:
    out for delivery, ready for pickup, delivered, attempted and exception,
    and one per return pickup while it waits. An iPhone gets those
    notifications too for the parcels of an activity the user dismissed (tag
    ``parcel-<id>-news``; see Live Activities), also once they moved to a
    later day, except news that iPhone's activities already showed that day.
    When newer news takes a parcel from out for delivery or ready for pickup
    back to transit, its notification is replaced with what holds now, since
    the old one would no longer be true. News that brings back what a parcel
    held less than ``FLIP_QUIET`` ago comes quietly (passive on iOS,
    ``alert_once`` on Android), except a delivery and its undo, and a
    device's first news of the parcel that day.
    Macs, watches and unknown systems get nothing; they mirror the iPhone.
    The Live Activities switch covers these notifications too.

The day
    Everything happens between the start time and the cut-off, in Home
    Assistant's time zone. At the start time the day's board is built from
    non-terminal parcels expected today (the last day of the ETA is today) and
    parcels that became ready for pickup since the previous cut-off. Until the
    cut-off, a parcel joins on the same terms as soon as it's expected today,
    also when its date became today after the start time, or when it goes out
    for delivery today or becomes ready for pickup. Nothing starts after the
    cut-off, and the cut-off ends every remaining activity. A pickup parcel is
    on the lock screen on the day it became ready (or the next day when that
    happened after the cut-off); on later days only the persistent
    notification lists it, for up to a week.

Live Activities
    One activity per parcel and iPhone (tag ``parcel-<id>``), or one combined
    activity (``parcels-today-YYYYMMDD``) once a device has more parcels than
    the collapse threshold; a device then stays combined for the rest of the
    day. Updates are sent only when the payload changes, and quietly when the
    status didn't change or the news brings back what the parcel held less than
    ``FLIP_QUIET`` ago; a shared activity's, when every package that changed
    did that and the iPhone was told of each before. A start, a delivery and
    its undo always alert. A delivered parcel shows its delivery time at 4/4
    and ends 30 minutes later; a parcel moved to a later day says so and ends
    30 minutes later. Apple ends activities after 8 hours, so an undelivered
    parcel's activity is ended and restarted with a ``-2`` (``-3`` ...) tag
    after 7.5 hours. To respect Apple's push-to-start budget a parcel starts at
    most once per device and day, except for that restart, the switch being
    turned back on, a device becoming a recipient again, a delivery taken back
    and a moved parcel that goes out for delivery after all. The state is
    persisted, so a restart of Home Assistant neither ends nor duplicates an
    activity.

    mobile_app starts an activity whenever it holds no update token for the
    tag, so nothing but a start goes to an activity without one. A new
    activity's updates wait for its token, looked for as for a PIN (see
    Delivery PINs), and the latest goes once it comes; if none came within 5
    minutes, the activity's key news comes as notifications meanwhile. Once
    the token was there and is gone, the user dismissed the activity (or iOS
    ended it): it is over for the day, isn't restarted after 7.5 hours, and
    its key news comes as notifications, like an iPad's, except news that
    the iPhone's activities already showed that day, until the parcel's
    status changes. Only the switch being turned back on or the device
    becoming a recipient again starts it again.

    The icon and the progress bar take the colour of the status: blue on the
    way, orange out for delivery, green delivered, purple ready for pickup,
    red for a missed attempt or a problem and pink for a return pickup. The
    card keeps the system's dark background, and the icon and the text still
    say the status. A combined activity takes the colour of its most urgent
    parcel: out for delivery, then a problem, then a return pickup that
    waits, then a pickup; green once all are delivered. The message
    always shows the delivery window; the countdown runs only in the last
    hour of the window (all of a shorter one) and starts with one quiet
    update. The combined activity shows no countdown while one of its
    parcels has a missed attempt or a problem, so its text can say so; a
    parcel's own activity keeps its countdown. Tapping an activity or a
    notification opens the parcel on the dashboard
    (``<path>?parcel=<id>``), or the return (``<path>?return=<id>``); the
    combined activity opens the week.

    The text says what comes next: where and until when a parcel can be
    collected, when a missed attempt happened ("reported" when that's only
    its e-mail's time) and the next attempt or where the carrier took the
    parcel, and where a delivered parcel was left. iPads and Android phones
    get the same text.

Delivery PINs
    With the hub option on, an iPhone's activity shows a parcel's delivery
    PIN or pickup code while the parcel is out for delivery or ready for
    pickup, on the iPhones that may show the parcel. The status takes the
    message's first line and the PIN leads the second, which the Lock Screen
    shows and the one-line views (Smart Stack, CarPlay, the expanded Dynamic
    Island) leave out; ``critical_text`` never has it, and no countdown
    replaces the message while it shows. A combined activity shows the PIN
    of the parcel out for delivery that it names next; without one, the
    pickup code of its only parcel ready for pickup, with the pickup point,
    and no code while two or more wait for pickup. iPads, Android phones and
    the persistent notification never get it.

    Every start is plain: the PIN follows with a quiet update, sent through
    mobile_app's notify service object rather than a service call, whose
    ``call_service`` event the recorder would keep, and only while the
    activity's update token stays valid for another minute, so a dismissed
    or expiring activity isn't started again with it. Until then the
    notifier tries again (5 s, 15 s, 1 min, then every 5 min). The status
    change that ends the PIN, and turning the option off or on, send quiet
    updates. Records keep only whether a PIN shows and a fingerprint keyed
    with a random in-memory key, never the PIN, so after a restart the PIN
    is sent once more, quietly.

Packages
    The day counts packages, not records. An order without a carrier's
    number that one of the day's packages may hold rides along with it (see
    :func:`~.dedup.boxes_of_day`): it doesn't count, start an activity or
    notify on its own, and with item names on, the package says what it may
    hold ("Possibly: ..."). The package's text ends with how many orders it
    may hold, by shop when they're one shop's ("may hold 8 Amazon orders"):
    each once, and only those the device may show (see :func:`_holds`). A
    change in that alone is a quiet update. An order that no package may hold
    counts on its own. When an order stops riding along, its activity starts
    again.

Return pickups
    A return whose carrier collects it today (see
    :func:`~.customer_returns.pickup_today`) has its own activity
    (``return-<id>``) on the iPhones that may show the return: a shared
    return on every notified iPhone, a private one only on its owners'. It
    starts at the start time, or as soon as an e-mail sent since then sets
    its pickup for today, and names the shop, the carrier and, with item
    names on, a shared return's first item. A return set before the start
    time that the notifier first sees more than 15 minutes after it, as when
    Home Assistant was down or Parcels was updated, starts nothing that day:
    the carrier may have come hours ago. The page and the persistent
    notification still list it. The time of the e-mail counts, not when it
    was read. iPads and Android phones get their notification on the same
    terms.
    Marking it picked up updates it quietly to "Return picked up ✓" with the
    time at 4/4, and it ends 30 minutes later; undo brings it back, and
    starts it again once it has ended. A return picked up before the start
    time starts nothing until someone takes that back, and one moved to
    another day ends at once. Return pickups count towards the collapse
    threshold, and the combined activity counts them in its text and its
    progress.

Persistent notification
    ``parcels_today`` lists the day's parcels and return pickups from the
    start time until the next morning's start time, without item names, with
    the same details as the activities; private parcels and private returns
    are only counted.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable, Coroutine, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from enum import StrEnum
import hashlib
import hmac
import json
import logging
import re
import secrets
import traceback
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit, urlunsplit

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CARRIER_NAMES,
    CONF_COLLAPSE_THRESHOLD,
    CONF_CUTOFF_TIME,
    CONF_DASHBOARD_PATH,
    CONF_EXCLUDED_DEVICES,
    CONF_ITEM_NAMES,
    CONF_NOTIFY_PERSONS,
    CONF_PIN_ON_LOCK_SCREEN,
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
    LeftAt,
    ParcelStatus,
)
from .customer_returns import linked_parcels, order_index, pickup_today
from .dedup import boxes_of_day
from .models import (
    Parcel,
    ParcelsData,
    ParcelState,
    ReturnEntry,
    dt_from_str,
    local_date,
    merchant_key,
)
from .parsers.base import Eta
from .parsers.items import unique_items
from .views import shipment_groups

_LOGGER = logging.getLogger(__name__)

STATE_KEY = "notifier"
STATE_VERSION = 1

DEBOUNCE_COOLDOWN = 10.0
# News read while an evaluation sends starts it over, up to this many rounds;
# the last round sends everything, and news read during it is evaluated soon
# after.
EVALUATION_ROUNDS = 3
DELIVERED_LINGER = timedelta(minutes=30)
RESTART_AFTER = timedelta(hours=7, minutes=30)
APPLE_LIMIT = timedelta(hours=8)
RETRY_DELAY = timedelta(minutes=5)
TEST_ACTIVITY_DURATION = timedelta(minutes=1)
TEST_PIN_DURATION = timedelta(minutes=2)
TEST_PIN = "4826"
# A PIN is asked again after 5 s, 20 s and 80 s, then every 5 minutes; each
# activity that starts, or turns to a status with a PIN, starts over.
PIN_RETRY = (
    timedelta(seconds=5),
    timedelta(seconds=15),
    timedelta(minutes=1),
    timedelta(minutes=5),
)
# A push token this close to expiring may be gone when the push arrives.
TOKEN_MARGIN = timedelta(minutes=1)
# How long an iPhone may take to send a new activity's token before its key
# news comes as notifications instead.
TOKEN_WAIT = timedelta(minutes=5)
MAX_PIN = 20
DUE_TOLERANCE = timedelta(seconds=1)
COUNTDOWN = timedelta(hours=1)
PICKUP_DAYS = 7
# Return pickups set before the start time join only this soon after it.
RETURN_GRACE = timedelta(minutes=15)
# News that brings back what a parcel held this recently is quiet; a delivery
# and its undo always alert.
FLIP_QUIET = timedelta(minutes=15)
LATER = ":later"

PROGRESS_MAX = 4
COMBINED = "combined"
COMBINED_TITLE = "Parcels today"
TEST_TAG = "parcels-test"
MAX_TAG = 64
MAX_TEXT = 40
MAX_NAME = 20
MAX_PLACE = 28
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
REASON_PICKED_UP = "picked_up"
# Ended on the iPhone: dismissed by the user, or ended by iOS.
REASON_DISMISSED = "dismissed"
RESTARTABLE = frozenset({REASON_RESTART, REASON_DISABLED, REASON_REMOVED})
LINGERING = frozenset({REASON_DELIVERED, REASON_MOVED, REASON_PICKED_UP})
RETURN_STATUS = "return_pickup"

S = ParcelStatus
KEY_STATUSES = frozenset(
    {S.OUT_FOR_DELIVERY, S.READY_FOR_PICKUP, S.DELIVERED, S.ATTEMPTED, S.EXCEPTION}
)
EN_ROUTE = frozenset({S.ORDERED, S.SHIPPED, S.IN_TRANSIT, S.OUT_FOR_DELIVERY})
MOVABLE = frozenset({S.ORDERED, S.SHIPPED, S.IN_TRANSIT, S.ATTEMPTED, S.EXCEPTION})
PROBLEMS = frozenset({S.ATTEMPTED, S.EXCEPTION})
GONE = frozenset({S.RETURNED, S.CANCELLED})
PIN_STATUSES = frozenset({S.OUT_FOR_DELIVERY, S.READY_FOR_PICKUP})
# What a notification said that newer news can take back (see _taken_back).
TAKEN_BACK_FROM = frozenset({S.OUT_FOR_DELIVERY.value, S.READY_FOR_PICKUP.value})

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
RETURN_ICON = "mdi:package-up"

# Legible on the Lock Screen's dark card; never the only sign of a status.
BLUE = "#039BE5"
ORANGE = "#FFA600"
GREEN = "#43A047"
PURPLE = "#926BC7"
RED = "#DB4437"
PINK = "#E91E63"
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
# Keys the hashes of PINs in stored fingerprints; it never leaves memory.
_PIN_KEY = secrets.token_bytes(32)


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
    pin: bool
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
            pin=options.get(CONF_PIN_ON_LOCK_SCREEN) is True,
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
    # Not sent: the parcels changed while a round that starts over was sending.
    STALE = "stale"


class _Route(StrEnum):
    """What a push to a Live Activity's tag does on an iPhone."""

    UPDATE = "update"
    OTHER = "other"
    UNKNOWN = "unknown"


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
    """Parse a serialised datetime as UTC, or return None, also when damaged."""
    if not isinstance(value, str):
        return None
    parsed = dt_from_str(value)
    return dt_util.as_utc(parsed) if parsed is not None else None


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


def _news_tag(parcel_id: str) -> str:
    """Return the tag of an iPhone's notification of a parcel's news.

    It differs from the activity's tag: ending the activity once its token
    is gone clears what carries that tag.
    """
    return _parcel_tag(parcel_id)[: MAX_TAG - 5] + "-news"


def _return_tag(entry_id: str, gen: int = 1) -> str:
    """Return the tag of a return pickup's activity or notification."""
    return _tag(f"return-{entry_id.removeprefix('ret_')}", gen)


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


def _short_day(day: date, today: date) -> str:
    """Return a date for the lock screen: today, tomorrow, yesterday or Thu 19."""
    if abs((day - today).days) <= 1:
        return _day_word(day, today)
    return f"{_WEEKDAYS[day.weekday()]} {day.day}"


def _place(value: str | None) -> str:
    """Return the name of a pickup point for the lock screen, without its address."""
    text = _SPACES.sub(" ", str(value or "")).strip()
    return _clean(text.split(",", 1)[0].strip() or text, MAX_PLACE)


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


def _moved(state: ParcelState, today: date) -> bool:
    """Return True for a parcel on its way that is now expected on a later day."""
    return state.status in MOVABLE and state.eta is not None and state.eta.end > today


def _routed(parcel: Parcel, device: _Device) -> bool:
    """Return True when a device may show a parcel.

    Private parcels go only to their owners' devices (and to nobody when they
    have no owner).
    """
    return not parcel.private or bool(device.persons & set(parcel.state.owners))


@dataclass(frozen=True, slots=True)
class _DayReturn:
    """A return the carrier picks up on a day, and who may see it.

    One of a private parcel's order is private too, for the owners of both,
    as on the dashboard.
    """

    entry: ReturnEntry
    private: bool
    owners: frozenset[str]

    def routed(self, device: _Device) -> bool:
        """Return True when a device may show the return pickup."""
        return not self.private or bool(device.persons & self.owners)


def _day_returns(data: ParcelsData, day: date) -> dict[str, _DayReturn]:
    """Return the return pickups of a day by ID, in the store's order."""
    entries = [entry for entry in data.returns.values() if pickup_today(entry, day)]
    if not entries:
        return {}
    index = order_index(data)
    found: dict[str, _DayReturn] = {}
    for entry in entries:
        private = [parcel for parcel in linked_parcels(entry, index) if parcel.private]
        found[entry.id] = _DayReturn(
            entry=entry,
            private=entry.private or bool(private),
            owners=frozenset(
                {*entry.owners, *(o for parcel in private for o in parcel.state.owners)}
            ),
        )
    return found


def _return_carrier(entry: ReturnEntry) -> str | None:
    """Return the name of the carrier that picks a return up, when known."""
    carrier = entry.carrier
    if not carrier or carrier == "other":
        return None
    return _clean(CARRIER_NAMES.get(carrier, carrier)) or None


def _return_names(entry: ReturnEntry) -> list[str]:
    """Return the shop and the carrier of a return pickup, without duplicates.

    Without a shop the carrier names it, else just "Return".
    """
    carrier = _return_carrier(entry)
    title = _clean(entry.merchant) or carrier or "Return"
    if carrier and carrier.casefold() != title.casefold():
        return [title, carrier]
    return [title]


def _pin(parcel: Parcel, device: _Device, options: _Options) -> str | None:
    """Return the delivery PIN or pickup code an iPhone's activity may show.

    Only with the option on, on iPhones that may show the parcel, while it is
    out for delivery or ready for pickup. A code too long for the lock screen
    isn't shown at all, never cut.
    """
    state = parcel.state
    if (
        not options.pin
        or device.kind is not DeviceKind.IPHONE
        or state.status not in PIN_STATUSES
        or not _routed(parcel, device)
    ):
        return None
    code = _SPACES.sub(" ", state.pickup_code or "").strip()
    return code if 0 < len(code) <= MAX_PIN else None


def _pin_lines(state: ParcelState, today: date) -> tuple[str, list[str]]:
    """Return the status line above a PIN, and what follows the PIN.

    The Lock Screen shows two lines of the message, and the compact views
    one: the status, then the PIN with the window or the pickup point.
    """
    if state.status is S.READY_FOR_PICKUP:
        rest = [place] if (place := _place(state.pickup_point)) else []
        if state.collect_by is not None:
            rest.append(f"collect by {_short_day(state.collect_by, today)}")
        return _STATUS_TEXT[S.READY_FOR_PICKUP], rest
    eta = state.eta
    window = _window_text(eta) if eta is not None and eta.end == today else None
    return _STATUS_TEXT[S.OUT_FOR_DELIVERY], [window] if window else []


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

# Where a delivered parcel was left, after its delivery time.
LEFT_AT_TEXT: dict[LeftAt, str] = {
    LeftAt.NEIGHBOUR: "with a neighbour",
    LeftAt.MAILBOX: "in the mailbox",
    LeftAt.DOOR: "at the door",
    LeftAt.RECEPTION: "at reception",
    LeftAt.GARAGE: "in the garage",
    LeftAt.LOCKER: "in a locker",
}


def _attempt_time(
    state: ParcelState, day: date, today: date, day_text: Callable[[date, date], str]
) -> tuple[str | None, bool]:
    """Return when a missed attempt happened, and whether that's only its e-mail's time.

    The time when it was on ``day``, else its day; nothing when only its day
    is known and that is ``day``, or when not even its day is.
    """
    moment = state.status_time
    if moment is None or (state.status_undated and not state.status_timeless):
        return None, False
    happened = local_date(moment)
    if state.status_timeless:
        return (None if happened == day else day_text(happened, today)), False
    if happened != day:
        return day_text(happened, today), state.status_reported
    return _local_hm(moment), state.status_reported


def _attempt_tail(
    state: ParcelState,
    today: date,
    day_text: Callable[[date, date], str],
    place_text: Callable[[str | None], str],
) -> list[str]:
    """Return what follows a missed attempt.

    The next attempt; else where the carrier took the parcel and until when
    it can be collected.
    """
    if state.next_attempt is not None and state.next_attempt >= today:
        return [f"next attempt {day_text(state.next_attempt, today)}"]
    tail: list[str] = []
    if place := place_text(state.pickup_point):
        tail.append(f"taken to {place}")
    if state.collect_by is not None:
        tail.append(f"collect by {day_text(state.collect_by, today)}")
    return tail


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
    # An update alerts only when this changes: the real news, see
    # ParcelState.news_status.
    status: str
    url: str
    # The news status of each parcel it shows: once the user dismisses the
    # activity, only news it didn't show comes as a notification.
    shows: tuple[tuple[str, str], ...] = ()


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
    elif status is S.DELIVERED and state.inferred:
        # No check mark and no time: it may not have come.
        text, critical = "Probably delivered", "Probably"
    elif status is S.DELIVERED:
        delivered = _delivered_time(state)
        at = _local_hm(delivered) if delivered is not None else None
        text = f"Delivered {CHECK} {at}" if at else f"Delivered {CHECK}"
        critical = f"{CHECK} {at}" if at else CHECK
        if state.left_at is not None:
            text += f"{SEP}{LEFT_AT_TEXT[state.left_at]}"
    elif status is S.READY_FOR_PICKUP:
        place = _place(state.pickup_point)
        text = f"Ready at {place}" if place else "Ready for pickup"
        critical = "Pickup"
        if state.collect_by is not None:
            text += f"{SEP}collect by {_short_day(state.collect_by, today)}"
    elif status is S.ATTEMPTED:
        # The time stays apart from "Missed" when it's only the e-mail's.
        when, reported = _attempt_time(state, today, today, _short_day)
        text, critical = "Missed", "Missed"
        if when is not None:
            text += f"{SEP}reported {when}" if reported else f" {when}"
        if tail := _attempt_tail(state, today, _short_day, _place):
            text += SEP + SEP.join(tail)
        elif later is not None:
            text += f"{SEP}Expected {_day_word(later, today)}"
    elif status is S.EXCEPTION:
        text, critical = _STATUS_TEXT[status], "Problem"
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
    parcel: Parcel,
    ctx: _Context,
    possibly: Sequence[str] = (),
    pin: str | None = None,
    *,
    holds: str | None = None,
) -> _Content:
    """Return what a parcel's activity or notification shows.

    ``possibly`` lists the items of the orders the package may hold, and
    ``holds`` says how many they are (see :func:`_holds`): last, so the
    Lock Screen cuts it first. With a ``pin``, the status takes the first
    line and the PIN leads the second; no timer replaces them.
    """
    state = parcel.state
    text, critical = _status_texts(state, ctx.today)
    title = _title(state)
    first: str | None = None
    if pin is not None:
        first, rest = _pin_lines(state, ctx.today)
        parts = [f"PIN {pin}", *rest]
    else:
        parts = [text]
    carrier = _clean(state.carrier_name)
    if carrier and carrier.casefold() != title.casefold():
        parts.append(carrier)
    if ctx.options.item_names and not parcel.private:
        if state.items:
            item = _clean(state.items[0], 30)
            more = len(state.items) - 1
            parts.append(f"{item} +{more} more" if more else item)
        elif (name := _clean(state.name, 30)) and name.casefold() not in {
            shown.casefold() for shown in (title, *([first] if first else []), *parts)
        }:
            # What the user calls it in the Parcel app, unless it's the shop.
            parts.append(name)
        elif possibly:
            more = len(possibly) - 1
            parts.append(
                f"Possibly: {_clean(possibly[0], 30)}" + (f" (+{more})" if more else "")
            )
    if holds:
        parts.append(holds)
    end = _chronometer_end(state, ctx) if pin is None else None
    message = SEP.join(parts)
    return _Content(
        title=title,
        message=f"{first}\n{message}" if first is not None else message,
        critical=critical,
        progress=max(1, min(PROGRESS_MAX, STATUS_RANK.get(state.status, 1))),
        progress_max=PROGRESS_MAX,
        icon=ICONS.get(state.status, DEFAULT_ICON),
        color=COLORS.get(state.status, DEFAULT_COLOR),
        relevance=_relevance(state, ctx),
        when=int(end.timestamp()) if end is not None else None,
        status=state.news_status.value,
        url=_detail_url(ctx.options.path, "parcel", parcel.id),
        shows=((parcel.id, state.news_status.value),),
    )


def _return_content(item: _DayReturn, ctx: _Context) -> _Content:
    """Return what a return pickup's activity or notification shows.

    In pink until someone marks it picked up, then the time it was marked.
    Both share one status, so marking it, and taking that back, update the
    activity quietly.
    """
    entry = item.entry
    title, *names = _return_names(entry)
    done = entry.done(ctx.today)
    if done:
        at = _local_hm(entry.picked_up) if entry.picked_up is not None else None
        parts = [f"Return picked up {CHECK}" + (f" {at}" if at else "")]
        critical = f"{CHECK} {at}" if at else CHECK
    else:
        parts = ["Return pickup today"]
        critical = "Return"
    parts += names
    if ctx.options.item_names and not item.private and (items := entry.items):
        more = len(items) - 1
        name = _clean(items[0], 30)
        parts.append(f"{name} +{more} more" if more else name)
    return _Content(
        title=title,
        message=SEP.join(parts),
        critical=critical,
        progress=PROGRESS_MAX if done else PROGRESS_MAX - 1,
        progress_max=PROGRESS_MAX,
        icon=RETURN_ICON,
        color=PINK,
        relevance=0.2 if done else 0.6,
        when=None,
        status=RETURN_STATUS,
        url=_detail_url(ctx.options.path, "return", entry.id),
    )


def _packages(
    data: ParcelsData, parcels: list[Parcel], day: date
) -> tuple[list[Parcel], dict[str, list[str]], dict[str, list[Parcel]]]:
    """Return the parcels that count on a day, and what each package may hold.

    An order that one of the day's packages may hold rides along with it and
    doesn't count. Each package gets the items of the public orders it may
    hold, and every order it may hold: one that several packages may hold
    rides with each of them.
    """
    covered = boxes_of_day(data, parcels, day)
    items: dict[str, list[str]] = {}
    riding: dict[str, list[Parcel]] = {}
    for parcel in parcels:
        for box in covered.get(parcel.id, ()):
            riding.setdefault(box, []).append(parcel)
            if not parcel.private:
                items.setdefault(box, []).extend(parcel.state.items)
    return (
        [parcel for parcel in parcels if parcel.id not in covered],
        {box: unique_items(names) for box, names in items.items()},
        riding,
    )


def _holds(orders: Iterable[Parcel]) -> str | None:
    """Return how many orders a package, or the day's packages, may hold.

    Each order counts once, even when several packages may hold it, and
    the shop is named when they're all from one shop: "may hold 8 Amazon
    orders", "may hold 3 orders". None when no order rides along.
    """
    unique = list({order.id: order for order in orders}.values())
    if not unique:
        return None
    one_shop = len({merchant_key(order.state.merchant) for order in unique}) == 1
    shop = _clean(unique[0].state.merchant, MAX_NAME) if one_shop else ""
    words = [f"may hold {len(unique)}", *([shop] if shop else [])]
    return " ".join([*words, "order" if len(unique) == 1 else "orders"])


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


def _next_parcel(parcels: list[Parcel], today: date) -> Parcel | None:
    """Return the parcel that a combined activity names next."""
    states = [parcel.state for parcel in parcels]
    upcoming = _next_state(states, today)
    return next(
        (
            parcel
            for parcel, state in zip(parcels, states, strict=True)
            if state is upcoming
        ),
        None,
    )


def _next_label(state: ParcelState) -> str:
    """Return who brings the next delivery: Amazon via Paack, else either name."""
    shop = _clean(state.merchant, MAX_NAME)
    carrier = _clean(state.carrier_name, MAX_NAME)
    if shop and carrier and shop.casefold() != carrier.casefold():
        return f"{shop} via {carrier}"
    return shop or carrier or "Parcel"


def _combined_content(
    parcels: list[Parcel],
    ctx: _Context,
    pin: str | None = None,
    *,
    returns: Sequence[ReturnEntry] = (),
    place: str | None = None,
    holds: str | None = None,
) -> _Content:
    """Return what a device's combined activity shows.

    ``pin`` is the code of the parcel out for delivery that it names next, or
    of the one parcel ready for pickup at ``place``: the count keeps the
    first line, and the PIN leads the second. ``returns`` are the device's
    return pickups of the day; they count after the parcels. ``holds`` says
    how many orders its packages may hold, last (see :func:`_holds`).

    A delivery that Parcels only inferred is a guess, not news: it counts
    apart, as probable ("1 of 2 delivered · 1 probably"), and doesn't make the
    day done.
    """
    states = [parcel.state for parcel in parcels]
    total = len(states)
    counts = Counter(state.status for state in states)
    probably = sum(state.inferred for state in states)
    delivered = counts[S.DELIVERED] - probably
    pickup = counts[S.READY_FOR_PICKUP]
    problems = counts[S.ATTEMPTED] + counts[S.EXCEPTION]
    out = counts[S.OUT_FOR_DELIVERY]
    picked = sum(entry.done(ctx.today) for entry in returns)
    waiting = len(returns) - picked
    done = bool(total or returns) and delivered == total and not waiting
    head = (
        f"{delivered} of {total} delivered"
        + (f" {CHECK}" if total and delivered == total else "")
        + (f"{SEP}{probably} probably" if probably else "")
    )
    parts: list[str] = []
    if pickup:
        parts.append(f"{pickup} ready for pickup")
    if problems:
        parts.append(f"{problems} problem" + ("s" if problems > 1 else ""))
    if waiting:
        parts.append(f"{waiting} return pickup" + ("s" if waiting > 1 else ""))
    if picked:
        noun = "returns" if picked > 1 else "return"
        parts.append(f"{picked} {noun} picked up {CHECK}")
    upcoming_parts: list[str] = []
    when: int | None = None
    if (upcoming := _next_state(states, ctx.today)) is not None:
        label = _next_label(upcoming)
        if short := _window_short(upcoming.eta):
            upcoming_parts.append(f"next: {label} {short}")
        elif upcoming.status is S.OUT_FOR_DELIVERY:
            upcoming_parts.append(f"{label} out for delivery")
        # The timer would hide the text that names a problem, or the PIN.
        if (
            pin is None
            and not problems
            and (end := _chronometer_end(upcoming, ctx)) is not None
        ):
            when = int(end.timestamp())
    # The most urgent parcel leads the icon and the colour; a return pickup
    # waiting today comes before a parcel that can wait at its pickup point.
    icon, color = DEFAULT_ICON, DEFAULT_COLOR
    if out:
        icon, color = ICONS[S.OUT_FOR_DELIVERY], COLORS[S.OUT_FOR_DELIVERY]
    elif done:
        icon, color = ICONS[S.DELIVERED], COLORS[S.DELIVERED]
    elif problems:
        icon, color = ICONS[S.EXCEPTION], COLORS[S.EXCEPTION]
    elif waiting:
        icon, color = RETURN_ICON, PINK
    elif pickup:
        icon, color = ICONS[S.READY_FOR_PICKUP], COLORS[S.READY_FOR_PICKUP]
    relevance = max(
        [
            *(
                _relevance(state, ctx)
                for state in states
                if state.status is not S.DELIVERED
            ),
            *([0.6] if waiting else []),
        ],
        default=0.2,
    )
    tail = [holds] if holds and total else []
    if pin is not None and total:
        message = f"{head}\n" + SEP.join(
            [f"PIN {pin}", *([place] if place else []), *upcoming_parts, *parts, *tail]
        )
    else:
        message = SEP.join([*([head] if total else []), *parts, *upcoming_parts, *tail])
    news = Counter(state.news_status for state in states)
    status = "/".join(
        str(count)
        for count in (
            news[S.DELIVERED],
            total,
            news[S.OUT_FOR_DELIVERY],
            news[S.READY_FOR_PICKUP],
            news[S.ATTEMPTED] + news[S.EXCEPTION],
        )
    )
    return _Content(
        title=COMBINED_TITLE,
        message=message,
        critical=f"{delivered + picked}/{total + len(returns)}",
        progress=delivered + picked,
        progress_max=max(total + len(returns), 1),
        icon=icon,
        color=color,
        relevance=relevance,
        when=when,
        # Marking a return picked up, or taking that back, stays quiet.
        status=f"{status}/{len(returns)}" if returns else status,
        url=ctx.options.path,
        shows=tuple(
            (parcel.id, state.news_status.value)
            for parcel, state in zip(parcels, states, strict=True)
        ),
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


def _key_payload(
    content: _Content, tag: str, kind: DeviceKind, *, quiet: bool = False
) -> dict[str, Any]:
    """Return a normal notification for an iPad, an Android phone, or an iPhone.

    An iPhone gets one for an activity the user dismissed, or whose token
    didn't come. Android tints the icon with the status colour; iOS
    notifications have no colour. A ``quiet`` one replaces the last without
    an alert: passive on iOS, and on Android while the last still shows.
    """
    data: dict[str, Any] = {"tag": tag}
    if kind is DeviceKind.ANDROID:
        data["clickAction"] = content.url
        data["notification_icon"] = content.icon
        data["color"] = content.color
        if quiet:
            data["alert_once"] = True
    else:
        data["url"] = content.url
        if quiet:
            data["push"] = {"interruption-level": "passive"}
    return {"title": content.title, "message": content.message, "data": data}


def _test_payload(
    now: datetime,
    path: str,
    duration: timedelta = TEST_ACTIVITY_DURATION,
    pin: str | None = None,
) -> dict[str, Any]:
    """Return the demo Live Activity, or its quiet update with a made-up PIN."""
    data: dict[str, Any] = {
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
    }
    window = f"13:00{DASH}14:00"
    if pin is None:
        message = f"Test{SEP}Out for delivery {window}"
        data["chronometer"] = True
        data["when"] = int((now + duration).timestamp())
    else:
        message = f"Test{SEP}Out for delivery\nPIN {pin}{SEP}{window}"
        data["silent"] = True
    return {"title": PERSISTENT_TITLE, "message": message, "data": data}


def _fingerprint(payload: Mapping[str, Any], pin: str | None = None) -> str:
    """Return a fingerprint of a payload, ignoring how quietly it is sent.

    A PIN counts only through a key that lives in memory, so a stored
    fingerprint can't be matched against every possible PIN.
    """
    data = {key: value for key, value in payload["data"].items() if key != "silent"}
    message = payload.get("message")
    if pin is not None and isinstance(message, str):
        keyed = hmac.new(_PIN_KEY, pin.encode(), "sha256").hexdigest()
        message = message.replace(f"PIN {pin}", f"PIN {keyed}")
    raw = json.dumps(
        {
            "title": payload.get("title"),
            "message": message,
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
    """Return when a parcel was delivered, or None when the time isn't known.

    An inferred delivery's time is another parcel's, so it isn't known.
    """
    if state.delivered_undated or state.inferred:
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
    elif status is S.DELIVERED and state.inferred:
        text = "Probably delivered"
    elif status is S.DELIVERED:
        delivered = _delivered_time(state)
        text = "Delivered"
        if delivered is not None:
            text += f" {_local_hm(delivered)}"
        if state.left_at is not None:
            text += f" {LEFT_AT_TEXT[state.left_at]}"
        text += f" {CHECK}"
    elif status is S.READY_FOR_PICKUP:
        text = "Ready for pickup"
        if point := _clean(state.pickup_point):
            text += f" at {point}"
        if state.collect_by is not None:
            text += f", collect by {_day_word(state.collect_by, today)}"
    elif status is S.ATTEMPTED:
        text = _STATUS_TEXT[status]
        when, reported = _attempt_time(state, day, today, _day_word)
        if when is not None:
            text += f", reported {when}" if reported else f" {when}"
        if tail := _attempt_tail(state, today, _day_word, _clean):
            text += ", " + ", ".join(tail)
        elif eta is not None and eta.end > day:
            text += f", expected {_day_word(eta.end, today)}"
    elif status is S.EXCEPTION:
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
    returns: Sequence[_DayReturn] = (),
) -> str:
    """Return the Markdown of the persistent notification.

    ``listed`` pairs each parcel with its shipment. Packages of one shipment
    with the same status share a line; a delivered one keeps its own, with
    its time, unless the delivery is only inferred. The count in the title
    stays in packages. ``riders`` pairs each
    public order that packages of the day may hold with those packages; the
    orders of a shop that the same packages may hold share a line.
    ``returns`` are the day's return pickups, after the parcels; private ones
    are only counted.
    """
    total = len(listed) + private
    counts: list[str] = []
    if total or not returns:
        counts.append(f"{total} parcel{'' if total == 1 else 's'}")
    if returns:
        counts.append(f"{len(returns)} return pickup{'' if len(returns) == 1 else 's'}")
    lines = [f"**{' and '.join(counts)} {_day_word(day, today)}**", ""]
    rows: dict[tuple[str, str, int], list[ParcelState]] = {}
    ordered = sorted(listed, key=lambda item: _persistent_order(item[1]))
    for index, (shipment, state) in enumerate(ordered):
        status = _persistent_status(state, day, today)
        alone = index if state.status is S.DELIVERED and not state.inferred else -1
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
    shown = [item.entry for item in returns if not item.private]
    for entry in sorted(shown, key=lambda entry: _return_order(entry, day)):
        parts = _return_names(entry)
        if entry.done(day):
            text = "Return picked up"
            if entry.picked_up is not None and local_date(entry.picked_up) == day:
                text += f" {_local_hm(entry.picked_up)}"
            parts.append(f"{text} {CHECK}")
        else:
            parts.append(f"Return pickup {_day_word(day, today)}")
        lines.append("- " + SEP.join(_markdown(part) for part in parts))
    if private:
        lines.append(f"- +{private} private parcel{'' if private == 1 else 's'}")
    if hidden := len(returns) - len(shown):
        lines.append(f"- +{hidden} private return pickup{'' if hidden == 1 else 's'}")
    lines += ["", f"[Open Parcels]({path})"]
    return "\n".join(lines)


def _return_order(entry: ReturnEntry, day: date) -> tuple[bool, float, str]:
    """Sort return pickups still waiting by name, then those done by time."""
    done = entry.done(day)
    at = entry.picked_up.timestamp() if done and entry.picked_up else float("inf")
    return done, at, _return_names(entry)[0].casefold()


def _new_day() -> dict[str, Any]:
    """Return the state of a new day."""
    return {
        "morning": False,
        "board": [],
        "returns": [],
        "combined": [],
        "activities": {},
        "notified": {},
        # The news status of each parcel an activity of a device has shown
        # today, so a dismissal doesn't repeat it as a notification.
        "shown": {},
        # Each parcel an activity of a device has shown today, kept when its
        # status changes: with "notified", what the device was told of, so
        # its first news of a parcel alerts.
        "told": {},
        # Each parcel's news status (":later" once it moved to a later day),
        # when it left the statuses it held, and whether news is now quiet.
        "held": {},
    }


def _strings(value: Any) -> list[str]:
    """Return the unique strings of a stored list."""
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(item for item in value if isinstance(item, str) and item))


def _optional_str(value: Any) -> str | None:
    """Return a stored string, or None."""
    return value if isinstance(value, str) and value else None


def _sanitize_record(raw: Any, key: str) -> dict[str, Any] | None:
    """Return a stored activity, or None when it is unusable.

    ``key`` is what the activity shows: a parcel, a return pickup or the
    day's combined activity.
    """
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
    status = _optional_str(raw.get("status"))
    stored = raw.get("shown")
    shown: dict[str, str] = {}
    if isinstance(stored, Mapping):
        shown = {
            parcel_id: news
            for parcel_id, news in stored.items()
            if isinstance(parcel_id, str) and isinstance(news, str)
        }
    elif status is not None and key != COMBINED and not key.startswith("ret_"):
        # Stored by an older version: a parcel's activity showed its status.
        shown = {key: status}
    return {
        "tag": tag[:MAX_TAG],
        "gen": gen,
        "title": _optional_str(raw.get("title")) or "Parcel",
        "started": _iso(started),
        "running": raw.get("running") is True,
        "end_reason": _optional_str(raw.get("end_reason")),
        "end_at": _iso(end_at) if end_at is not None else None,
        "linger": linger if linger in LINGERING else None,
        "fp": _optional_str(raw.get("fp")),
        "status": status,
        "service": _optional_str(raw.get("service")),
        # Whether the last update showed a PIN, and the fingerprint of the
        # same update without it.
        "pin": raw.get("pin") is True,
        "plain": _optional_str(raw.get("plain")),
        # Whether the iPhone has sent the activity's token: updates wait for
        # it, and once it is gone the user has dismissed the activity. A PIN
        # shown by an older version means it had come.
        "seen": raw.get("seen") is True or raw.get("pin") is True,
        "shown": shown,
    }


def _statuses_by_device(raw: Any) -> dict[str, dict[str, str]]:
    """Return a stored map of device to parcel to status."""
    clean: dict[str, dict[str, str]] = {}
    if not isinstance(raw, Mapping):
        return clean
    for device_id, statuses in raw.items():
        if not isinstance(device_id, str) or not isinstance(statuses, Mapping):
            continue
        clean_statuses = {
            parcel_id: status
            for parcel_id, status in statuses.items()
            if isinstance(parcel_id, str) and isinstance(status, str)
        }
        if clean_statuses:
            clean[device_id] = clean_statuses
    return clean


def _sanitize_held(raw: Any) -> dict[str, dict[str, Any]]:
    """Return the stored statuses parcels held today."""
    clean: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, Mapping):
        return clean
    for parcel_id, value in raw.items():
        if not isinstance(parcel_id, str) or not isinstance(value, Mapping):
            continue
        key = _optional_str(value.get("key"))
        if key is None:
            continue
        left = value.get("left")
        clean[parcel_id] = {
            "key": key,
            "quiet": value.get("quiet") is True,
            "left": {
                held: _iso(at)
                for held, when in left.items()
                if isinstance(held, str) and (at := _parse_dt(when)) is not None
            }
            if isinstance(left, Mapping)
            else {},
        }
    return clean


def _sanitize_day(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return the stored state of a day, dropping anything unusable."""
    day = _new_day()
    day["morning"] = raw.get("morning") is True
    day["board"] = _strings(raw.get("board"))
    day["returns"] = _strings(raw.get("returns"))
    day["combined"] = _strings(raw.get("combined"))
    activities = raw.get("activities")
    if isinstance(activities, Mapping):
        for device_id, records in activities.items():
            if not isinstance(device_id, str) or not isinstance(records, Mapping):
                continue
            clean = {
                key: record
                for key, value in records.items()
                if isinstance(key, str) and (record := _sanitize_record(value, key))
            }
            if clean:
                day["activities"][device_id] = clean
    day["notified"] = _statuses_by_device(raw.get("notified"))
    if "shown" in raw:
        day["shown"] = _statuses_by_device(raw.get("shown"))
    else:
        # Stored by an older version: what the day's activities still show.
        for device_id, records in day["activities"].items():
            for record in records.values():
                if record["shown"]:
                    day["shown"].setdefault(device_id, {}).update(record["shown"])
    if "told" in raw:
        day["told"] = _statuses_by_device(raw.get("told"))
    else:
        # Stored by an older version: what the day's activities showed.
        for device_id, shown in day["shown"].items():
            day["told"].setdefault(device_id, {}).update(shown)
        for device_id, records in day["activities"].items():
            for record in records.values():
                if record["shown"]:
                    day["told"].setdefault(device_id, {}).update(record["shown"])
    day["held"] = _sanitize_held(raw.get("held"))
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
                "pin": test.get("pin") is True,
            }
    return state


def _describe_error(err: BaseException) -> str:
    """Describe an unexpected error without its message, which may hold content."""
    frames = traceback.extract_tb(err.__traceback__)
    where = f" in {frames[-1].name}:{frames[-1].lineno}" if frames else ""
    return f"{type(err).__name__}{where}"


def _mark_ended(record: dict[str, Any], reason: str) -> None:
    """Record that an activity is over."""
    record["running"] = False
    record["end_reason"] = reason
    record["linger"] = record["end_at"] = None
    record["pin"] = False
    record["plain"] = None


def _key_news(
    day: dict[str, Any],
    device_id: str,
    parcel: Parcel,
    shown: Mapping[str, str] | None = None,
) -> bool:
    """Return whether a parcel has key news a device wasn't told of yet.

    ``shown`` is what an activity the user dismissed had shown. An inferred
    delivery isn't news.
    """
    state = parcel.state
    status = state.status.value
    return (
        state.status in KEY_STATUSES
        and not state.inferred
        and day["notified"].get(device_id, {}).get(parcel.id) != status
        and (shown or {}).get(parcel.id) != status
    )


def _taken_back(day: dict[str, Any], device_id: str, parcel: Parcel) -> bool:
    """Return whether a device's notification of a parcel no longer holds.

    That is a notification that it was out for delivery or ready for pickup,
    once newer news took it back to transit.
    """
    told = day["notified"].get(device_id, {}).get(parcel.id)
    return told in TAKEN_BACK_FROM and parcel.state.status not in KEY_STATUSES


def _told(day: dict[str, Any], device_id: str, parcel_id: str) -> bool:
    """Return whether an activity or a notification told a device of a parcel.

    That is today: news flipping a parcel back is quiet only for a device
    that heard of the parcel before.
    """
    return parcel_id in day["told"].get(device_id, {}) or parcel_id in day[
        "notified"
    ].get(device_id, {})


def _note_shown(
    day: dict[str, Any], device: _Device, record: dict[str, Any], content: _Content
) -> None:
    """Record what an activity shows now, and that its iPhone has shown it today.

    So once the user dismisses any of that iPhone's activities, news one of
    them showed isn't sent again, also for a parcel since moved to another
    day; news changing the parcel's status makes it new again (see
    :meth:`Notifier._update_held`). The iPhone stays told of those parcels
    for the day.
    """
    shows = dict(content.shows)
    record["shown"] = shows
    if shows:
        day["shown"].setdefault(device.device_id, {}).update(shows)
        day["told"].setdefault(device.device_id, {}).update(shows)


def _flips_only(
    record: Mapping[str, Any], content: _Content, flipping: set[str]
) -> bool:
    """Return whether a shared activity changed only for parcels flipping back.

    That is, every parcel that changed, joined or left since its last update
    brings back what it held a moment ago, and no return pickup joined or
    left. ``flipping`` holds only parcels the iPhone was told of before.
    """
    before: Mapping[str, str] = record["shown"]
    after = dict(content.shows)
    changed = {
        parcel_id
        for parcel_id in before.keys() | after.keys()
        if before.get(parcel_id) != after.get(parcel_id)
    }
    status = record["status"]
    return (
        bool(changed)
        and changed <= flipping
        and status is not None
        and status.split("/")[5:] == content.status.split("/")[5:]
    )


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
        self._unsub_config: CALLBACK_TYPE | None = None
        # The time zone of the last evaluation, which the timer was set in.
        self._zone: str | None = None
        self._ready = False
        self._stopped = False
        # The parcels changed since the running round began.
        self._changed = False
        # Whether the running round starts over once the parcels change.
        self._restartable = False
        self._retry_at: datetime | None = None
        # When to look again for a token that lets a PIN go in a quiet update.
        self._pin_at: datetime | None = None
        self._pin_tries = 0
        self._wake_points: list[datetime] = []
        self._persistent_fp: str | None = _UNKNOWN
        self._devices: dict[str, _Device] = {}
        self._recipients: dict[str, _Device] = {}
        # The parcels whose news brings back what they held within
        # FLIP_QUIET, which updates and notifications give without an alert.
        self._flipping: set[str] = set()
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
        self._unsub_config = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, self._async_core_config_updated
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
        if self._unsub_config is not None:
            self._unsub_config()
            self._unsub_config = None
        self._cancel_timer()
        if self._debouncer is not None:
            self._debouncer.async_shutdown()
            self._debouncer = None
        async with self._lock:
            self._cancel_timer()
            self._save_if_changed()

    @callback
    def async_parcels_changed(self) -> None:
        """Re-evaluate shortly after the parcels changed; bursts are merged.

        An evaluation that is sending starts over, from the new data.
        """
        if self._stopped or not self._ready or self._debouncer is None:
            return
        self._changed = True
        self._debouncer.async_schedule_call()

    @callback
    def _async_core_config_updated(self, _event: Event) -> None:
        """Re-evaluate shortly after Home Assistant's time zone changed.

        The timer waits for a moment in UTC, worked out in the old zone.
        """
        if self._zone not in (None, str(dt_util.get_default_time_zone())):
            self.async_parcels_changed()

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

        With the PIN option on it lasts two minutes and shows a made-up PIN
        after its start. Without a device the test device is used, else the
        first iPhone that normally gets notifications. In test mode only the
        test device is used.
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
            # With the PIN option on, the demo lasts long enough to show one.
            duration = TEST_PIN_DURATION if options.pin else TEST_ACTIVITY_DURATION
            result = await self._async_send(
                device.service,
                device.kind,
                _test_payload(now, options.path, duration),
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
                "end_at": _iso(now + duration),
                "pin": False,
            }
            if options.pin:
                self._pin_later(now, first=True)
                # No evaluation follows to count this look.
                self._pin_tries = 1
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
        now = dt_util.utcnow()
        waiting = 0
        for device_id, device_records in day["activities"].items():
            if (device := self._devices.get(device_id)) is None:
                continue
            waiting += sum(
                1
                for record in device_records.values()
                if record["running"]
                and not record["seen"]
                and self._live_route(device, record["tag"], now)[0] is _Route.OTHER
            )
        return {
            "live_activities": state["live_activities"],
            "daily_notification": state["daily_notification"],
            "started": self._ready and not self._stopped,
            "test_mode": options.test_mode,
            "test_device_set": options.test_device is not None,
            "pin_on_lock_screen": options.pin,
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
                "showing_pin": sum(
                    1 for record in records if record["running"] and record["pin"]
                ),
                "dismissed": sum(
                    1 for record in records if record["end_reason"] == REASON_DISMISSED
                ),
                "waiting_for_token": waiting,
                "notifications_sent": sum(len(s) for s in day["notified"].values()),
                "orders_in_a_box": len(boxes_of_day(self._host.data, board, today)),
                "return_pickups": len(day["returns"]),
            },
            "persistent_notification_shown": self._persistent_fp
            not in (None, _UNKNOWN),
            "days_stored": len(state["days"]),
            "test_activity_running": "test" in state,
        }

    async def _async_evaluate(self) -> None:
        """Bring activities, notifications and the timer up to date.

        Sending can take longer than the debouncer waits. News read while a
        round sends starts the round over from the new data, so that no device
        gets a mix of old and new, and a flip back is quiet on every device.
        The last of EVALUATION_ROUNDS finishes, and news read during it gets
        an evaluation of its own soon after.
        """
        async with self._lock:
            if self._stopped:
                return
            self._ready = True
            self._cancel_timer()
            ctx = self._next_round()
            rounds = EVALUATION_ROUNDS
            try:
                while True:
                    rounds -= 1
                    await self._async_evaluate_locked(ctx, final=rounds == 0)
                    if self._stopped or not self._changed or rounds == 0:
                        break
                    ctx = self._next_round()
            except Exception as err:
                _LOGGER.error(
                    "Updating the parcel notifications failed: %s",
                    _describe_error(err),
                )
            finally:
                # Each look for a token that finds none waits longer.
                self._pin_tries = 0 if self._pin_at is None else self._pin_tries + 1
                if self._changed:
                    follow_up = dt_util.utcnow() + timedelta(seconds=DEBOUNCE_COOLDOWN)
                    if self._retry_at is None or follow_up < self._retry_at:
                        self._retry_at = follow_up
                self._save_if_changed()
                self._schedule_timer(ctx)

    def _next_round(self) -> _Context:
        """Start a round of an evaluation; return its context."""
        self._changed = False
        self._retry_at = None
        self._pin_at = None
        self._zone = str(dt_util.get_default_time_zone())
        return self._context(dt_util.utcnow(), _Options.from_entry(self.entry))

    async def _async_evaluate_locked(self, ctx: _Context, *, final: bool) -> None:
        """Evaluate everything; the caller holds the lock.

        Unless the round is ``final``, it stops before its next device once
        the parcels changed, and the next round does the rest.
        """
        self._devices = self._discover_devices()
        self._recipients = self._recipients_for(ctx.options)
        await self._async_close_past_days(ctx)
        await self._async_end_test(ctx.now, force=not self.live_activities_enabled)
        await self._async_test_pin(ctx)
        parcels = {parcel.id: parcel for parcel in self._host.visible_parcels()}
        # Chronometers appear and disappear with today's delivery windows.
        self._wake_points = [
            moment
            for parcel in parcels.values()
            if (eta := parcel.state.eta) is not None and eta.end == ctx.today
            for moment in _wake_moments(eta, ctx.today)
        ]
        days: dict[str, Any] = self._data["days"]
        returns = _day_returns(self._host.data, ctx.today)
        if ctx.in_window:
            day = days.setdefault(ctx.key, _new_day())
            self._update_board(ctx, day, parcels, returns)
            self._update_held(ctx, day, parcels)
        else:
            day = days.get(ctx.key)
            self._flipping = set()
        if day is not None:
            devices = sorted(set(self._recipients) | set(day["activities"]))
            self._restartable = not final
            try:
                for device_id in devices:
                    if self._restartable and self._changed:
                        return
                    await self._async_device(ctx, day, device_id, parcels, returns)
            finally:
                self._restartable = False
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

    @staticmethod
    def _return_joins(entry: ReturnEntry, ctx: _Context) -> bool:
        """Return True when a return pickup of today may join now.

        Within 15 minutes of the start time, every one may. After that, the
        carrier may have come hours ago, as when Parcels was updated or Home
        Assistant was down at the start time: only a return whose pickup was
        set for today by an e-mail sent since the start joins, or one someone
        took back from picked up since. Reading an older e-mail later counts
        as before the start.
        """
        if ctx.now < ctx.start + RETURN_GRACE:
            return True
        return any(
            moment is not None and moment >= ctx.start
            for moment in (entry.pickup_set, entry.reopened)
        )

    def _update_board(
        self,
        ctx: _Context,
        day: dict[str, Any],
        parcels: dict[str, Parcel],
        returns: Mapping[str, _DayReturn],
    ) -> None:
        """Add the parcels and return pickups on the lock screen today; none leave.

        Until the cut-off, a parcel joins once it's expected today, also when
        its date became today after the start time; one ready for pickup only
        when that's news (see :meth:`_joins`). A return pickup marked done
        before it joined stays off, and one set before the start time joins
        only soon after it (see :meth:`_return_joins`).
        """
        board: list[str] = day["board"]
        added = set(board)
        day["morning"] = True
        candidates = [
            parcel
            for parcel in parcels.values()
            if (
                _expected_today(parcel.state, ctx.today)
                and parcel.state.status is not S.READY_FOR_PICKUP
            )
            or self._joins(parcel.state, ctx)
        ]
        for parcel in candidates:
            if parcel.id not in added:
                added.add(parcel.id)
                board.append(parcel.id)
        pickups: list[str] = day["returns"]
        pickups += [
            return_id
            for return_id, item in returns.items()
            if return_id not in pickups
            and not item.entry.done(ctx.today)
            and self._return_joins(item.entry, ctx)
        ]

    def _update_held(
        self, ctx: _Context, day: dict[str, Any], parcels: Mapping[str, Parcel]
    ) -> None:
        """Note what each parcel of the day holds, and which ones flip back.

        News that brings back a status, with its day, that a parcel left
        within FLIP_QUIET is quiet until the parcel changes again, on devices
        told of the parcel before: carriers and 17TRACK that disagree then
        don't alert every device at each flip. A delivery and its undo still
        alert, as they always did. A new status also clears what the device's
        activities showed of the parcel, so a dismissal doesn't take it for
        news already shown.
        """
        held: dict[str, dict[str, Any]] = day["held"]
        since = ctx.now - FLIP_QUIET
        self._flipping = set()
        for parcel_id in day["board"]:
            parcel = parcels.get(parcel_id)
            if parcel is None:
                continue
            state = parcel.state
            news = state.news_status.value
            key = news + LATER if _moved(state, ctx.today) else news
            entry = held.get(parcel_id)
            if entry is None:
                held[parcel_id] = {"key": key, "quiet": False, "left": {}}
                continue
            if entry["key"] != key:
                left: dict[str, str] = entry["left"]
                left[entry["key"]] = _iso(ctx.now)
                for old, when in list(left.items()):
                    if (moment := _parse_dt(when)) is None or moment < since:
                        del left[old]
                before = entry["key"].removesuffix(LATER)
                if before != news:
                    for shown in day["shown"].values():
                        shown.pop(parcel_id, None)
                entry["key"] = key
                entry["quiet"] = key in left and S.DELIVERED.value not in (
                    before,
                    news,
                )
            if entry["quiet"]:
                self._flipping.add(parcel_id)

    @staticmethod
    def _device_returns(
        day: dict[str, Any], returns: Mapping[str, _DayReturn], device: _Device
    ) -> list[_DayReturn]:
        """Return the day's return pickups a device shows, in the order they joined.

        One moved to another day, or archived, leaves.
        """
        return [
            item
            for return_id in day["returns"]
            if (item := returns.get(return_id)) is not None and item.routed(device)
        ]

    async def _async_device(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device_id: str,
        parcels: dict[str, Parcel],
        returns: Mapping[str, _DayReturn],
    ) -> None:
        """Bring one device up to date."""
        device = self._recipients.get(device_id)
        if device is None:
            await self._async_end_all(ctx, day, device_id, REASON_REMOVED)
            return
        pickups = self._device_returns(day, returns, device)
        if device.kind is DeviceKind.IPHONE:
            await self._async_live_device(ctx, day, device, parcels, pickups)
        else:
            await self._async_end_all(ctx, day, device_id, REASON_REMOVED)
            await self._async_key_notifications(ctx, day, device, parcels, pickups)

    async def _async_end_all(
        self, ctx: _Context, day: dict[str, Any], device_id: str, reason: str
    ) -> None:
        """End every running activity of a device.

        Turning Live Activities off, or the device's not being notified,
        also lets the activities the user dismissed start again later.
        """
        for record in day["activities"].get(device_id, {}).values():
            if record["running"]:
                await self._async_end(device_id, record, reason, ctx.now)
            elif record["end_reason"] == REASON_DISMISSED and reason in (
                REASON_DISABLED,
                REASON_REMOVED,
            ):
                record["end_reason"] = reason

    async def _async_live_device(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        parcels: dict[str, Parcel],
        pickups: Sequence[_DayReturn] = (),
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
            if _moved(state, ctx.today):
                moved.append(parcel)
            else:
                members.append(parcel)
        entries, possibly, riding = _packages(self._host.data, members, ctx.today)
        records: dict[str, Any] = day["activities"].get(device_id, {})
        if (
            device_id in day["combined"]
            or len(entries) + len(pickups) > ctx.options.threshold
        ):
            if device_id not in day["combined"]:
                day["combined"].append(device_id)
            for key, record in records.items():
                if key != COMBINED and record["running"]:
                    await self._async_end(device_id, record, REASON_COLLAPSED, ctx.now)
            await self._async_combined(
                ctx,
                day,
                device,
                entries,
                [item.entry for item in pickups],
                holds=_holds(
                    order for box in entries for order in riding.get(box.id, ())
                ),
                possibly=possibly,
                riding=riding,
                moved=moved,
            )
            return
        keep = {
            *(parcel.id for parcel in (*entries, *moved)),
            *(item.entry.id for item in pickups),
        }
        for key, record in records.items():
            if record["running"] and key not in keep:
                await self._async_end(device_id, record, REASON_REMOVED, ctx.now)
        for parcel in entries:
            await self._async_individual(
                ctx,
                day,
                device,
                parcel,
                possibly.get(parcel.id, ()),
                _holds(riding.get(parcel.id, ())),
            )
        for parcel in moved:
            record = day["activities"].get(device_id, {}).get(parcel.id)
            if record is None:
                continue
            content = _parcel_content(parcel, ctx)
            if record["running"]:
                await self._async_linger(
                    ctx,
                    day,
                    device,
                    record,
                    content,
                    REASON_MOVED,
                    quiet=parcel.id in self._flipping,
                )
            await self._async_notify_instead(
                ctx,
                day,
                device,
                record,
                [parcel],
                lambda member: _parcel_content(member, ctx),
                content.status,
            )
        for item in pickups:
            await self._async_return(ctx, day, device, item)

    async def _async_individual(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        parcel: Parcel,
        possibly: Sequence[str] = (),
        holds: str | None = None,
    ) -> None:
        """Start, update, restart or end the activity of one parcel.

        Delivered, it shows that for 30 minutes and ends; taking back the
        delivery brings it back. Once the user has dismissed it, its key news
        comes as notifications.
        """
        record = day["activities"].get(device.device_id, {}).get(parcel.id)
        status = parcel.state.status
        content = _parcel_content(parcel, ctx, possibly, holds=holds)
        pin = _pin(parcel, device, ctx.options)
        pinned = (
            None
            if pin is None
            else (_parcel_content(parcel, ctx, possibly, pin, holds=holds), pin)
        )
        if record is None or not record["running"]:
            if record is not None and record["end_reason"] == REASON_DISMISSED:
                await self._async_notify_instead(
                    ctx,
                    day,
                    device,
                    record,
                    [parcel],
                    lambda _: content,
                    content.status,
                )
                return
            if status is S.DELIVERED:
                return
            pin_later = pinned is not None
            if record is None:
                await self._async_start(
                    ctx, day, device, parcel.id, 1, content, pin_later=pin_later
                )
            elif record["end_reason"] in (*RESTARTABLE, REASON_DELIVERED) or (
                record["end_reason"] == REASON_MOVED and status is S.OUT_FOR_DELIVERY
            ):
                gen = record["gen"] + 1
                await self._async_start(
                    ctx, day, device, parcel.id, gen, content, pin_later=pin_later
                )
            return
        quiet = parcel.id in self._flipping
        if status is S.DELIVERED:
            await self._async_linger(
                ctx, day, device, record, content, REASON_DELIVERED, quiet=quiet
            )
        else:
            record["linger"] = record["end_at"] = None
            await self._async_keep_alive(
                ctx, day, device, parcel.id, record, content, pinned, quiet=quiet
            )
        await self._async_notify_instead(
            ctx, day, device, record, [parcel], lambda _: content, content.status
        )

    async def _async_return(
        self, ctx: _Context, day: dict[str, Any], device: _Device, item: _DayReturn
    ) -> None:
        """Start, update, restart or end the activity of one return pickup.

        Marked picked up, it shows the time for 30 minutes and ends; taking
        that back brings it back.
        """
        entry = item.entry
        record = day["activities"].get(device.device_id, {}).get(entry.id)
        content = _return_content(item, ctx)
        done = entry.done(ctx.today)
        if record is None or not record["running"]:
            if done:
                return
            if record is None:
                await self._async_start(ctx, day, device, entry.id, 1, content)
            elif record["end_reason"] in (*RESTARTABLE, REASON_PICKED_UP):
                gen = record["gen"] + 1
                await self._async_start(ctx, day, device, entry.id, gen, content)
            return
        if done:
            await self._async_linger(
                ctx, day, device, record, content, REASON_PICKED_UP
            )
            return
        record["linger"] = record["end_at"] = None
        await self._async_keep_alive(ctx, day, device, entry.id, record, content)

    async def _async_combined(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        members: list[Parcel],
        returns: Sequence[ReturnEntry] = (),
        *,
        holds: str | None = None,
        possibly: Mapping[str, Sequence[str]] | None = None,
        riding: Mapping[str, Sequence[Parcel]] | None = None,
        moved: Sequence[Parcel] = (),
    ) -> None:
        """Start, update, restart or end the combined activity of one iPhone.

        ``possibly`` and ``riding`` are what each package may hold, for the
        notifications that replace the activity once the user dismissed it;
        those cover the ``moved`` parcels, now expected on a later day, too.
        """

        def member_content(member: Parcel) -> _Content:
            return _parcel_content(
                member,
                ctx,
                (possibly or {}).get(member.id, ()),
                holds=_holds((riding or {}).get(member.id, ())),
            )

        record = day["activities"].get(device.device_id, {}).get(COMBINED)
        pending = any(
            parcel.state.status is not S.DELIVERED for parcel in members
        ) or any(not entry.done(ctx.today) for entry in returns)
        # A delivery that was only inferred keeps a running activity until
        # the carrier confirms it, but doesn't start or restart one.
        probable = any(parcel.state.inferred for parcel in members)
        content = _combined_content(members, ctx, returns=returns, holds=holds)
        # The PIN of the delivery it names; else the code of its one parcel
        # ready for pickup, with the place.
        upcoming = _next_parcel(members, ctx.today)
        pin = (
            _pin(upcoming, device, ctx.options)
            if upcoming is not None and upcoming.state.status is S.OUT_FOR_DELIVERY
            else None
        )
        place: str | None = None
        ready = [p for p in members if p.state.status is S.READY_FOR_PICKUP]
        if pin is None and len(ready) == 1:
            pin = _pin(ready[0], device, ctx.options)
            place = _place(ready[0].state.pickup_point) or None
        pinned = (
            None
            if pin is None
            else (
                _combined_content(
                    members, ctx, pin, returns=returns, place=place, holds=holds
                ),
                pin,
            )
        )
        if record is None or not record["running"]:
            if record is not None and record["end_reason"] == REASON_DISMISSED:
                await self._async_notify_instead(
                    ctx,
                    day,
                    device,
                    record,
                    [*members, *moved],
                    member_content,
                    content.status,
                )
                return
            if not pending:
                return
            pin_later = pinned is not None
            if record is None:
                await self._async_start(
                    ctx, day, device, COMBINED, 1, content, pin_later=pin_later
                )
            elif record["end_reason"] in (*RESTARTABLE, REASON_DELIVERED):
                gen = record["gen"] + 1
                await self._async_start(
                    ctx, day, device, COMBINED, gen, content, pin_later=pin_later
                )
            return
        if not members and not returns:
            await self._async_end(device.device_id, record, REASON_REMOVED, ctx.now)
            return
        flipping = {
            parcel_id
            for parcel_id in self._flipping
            if _told(day, device.device_id, parcel_id)
        }
        quiet = _flips_only(record, content, flipping)
        if not pending and not probable:
            await self._async_linger(
                ctx, day, device, record, content, REASON_DELIVERED, quiet=quiet
            )
        else:
            record["linger"] = record["end_at"] = None
            await self._async_keep_alive(
                ctx,
                day,
                device,
                COMBINED,
                record,
                content,
                pinned,
                restart=pending,
                quiet=quiet,
            )
        await self._async_notify_instead(
            ctx,
            day,
            device,
            record,
            [*members, *moved],
            member_content,
            content.status,
        )

    async def _async_keep_alive(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        key: str,
        record: dict[str, Any],
        content: _Content,
        pinned: tuple[_Content, str] | None = None,
        *,
        restart: bool = True,
        quiet: bool = False,
    ) -> None:
        """Update an activity, restarting it before Apple ends it after 8 hours.

        A restart is plain, like every start: the PIN follows it quietly. An
        activity the user dismissed isn't restarted. Without ``restart``, when
        nothing is left to wait for but inferred deliveries, it ends instead:
        a restart would alert with nothing new. ``quiet`` updates it without
        an alert (see :meth:`_async_update`).
        """
        started = _parse_dt(record["started"])
        if (
            started is not None
            and ctx.now >= started + RESTART_AFTER - DUE_TOLERANCE
            and started + APPLE_LIMIT < ctx.cutoff
        ):
            if (
                record["seen"]
                and ctx.now < started + APPLE_LIMIT
                and self._live_route(device, record["tag"], ctx.now)[0] is _Route.OTHER
            ):
                _mark_ended(record, REASON_DISMISSED)
                return
            if not restart:
                await self._async_end(
                    device.device_id, record, REASON_DELIVERED, ctx.now
                )
                return
            if await self._async_end(device.device_id, record, REASON_RESTART, ctx.now):
                gen = record["gen"] + 1
                await self._async_start(
                    ctx, day, device, key, gen, content, pin_later=pinned is not None
                )
            return
        await self._async_update(ctx, day, device, record, content, pinned, quiet=quiet)

    async def _async_linger(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        record: dict[str, Any],
        content: _Content,
        reason: str,
        *,
        quiet: bool = False,
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
            await self._async_update(ctx, day, device, record, content, quiet=quiet)

    async def _async_start(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        key: str,
        gen: int,
        content: _Content,
        *,
        pin_later: bool = False,
    ) -> bool:
        """Start an activity; return True when it was sent.

        A start never carries a PIN: with ``pin_later`` the PIN follows in a
        quiet update, once the iPhone has registered the activity. Until the
        iPhone sends the activity's token, it is looked for as for a PIN.
        """
        if key == COMBINED:
            tag = _combined_tag(ctx.today, gen)
        elif key.startswith("ret_"):
            tag = _return_tag(key, gen)
        else:
            tag = _parcel_tag(key, gen)
        payload = _activity_payload(content, tag, content.title, silent=False)
        result = await self._async_send(device.service, device.kind, payload)
        if result is not _Result.SENT:
            if result is _Result.FAILED:
                self._retry(ctx.now)
            return False
        route, _webhook = self._live_route(device, tag, ctx.now)
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
            "pin": False,
            "plain": None,
            "seen": route is _Route.UPDATE,
            "shown": {},
        }
        _note_shown(day, device, day["activities"][device.device_id][key], content)
        if pin_later or route is _Route.OTHER:
            self._pin_later(ctx.now, first=True)
        return True

    async def _async_update(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        record: dict[str, Any],
        content: _Content,
        pinned: tuple[_Content, str] | None = None,
        *,
        quiet: bool = False,
    ) -> None:
        """Update a running activity when what it shows changed.

        The title stays the one the activity started with; the update is quiet
        when the status didn't change, or with ``quiet``, for news that brings
        back what parcels held a moment ago. ``pinned`` is what it shows with a
        PIN: that goes only in a quiet update, pushed straight to an iPhone
        known to hold the activity, so no alert and no new start ever carries
        a PIN.

        mobile_app starts an activity when it holds no token for it, so an
        update waits until the iPhone has sent the token of a new activity;
        once that token is gone, the user has dismissed the activity, and it
        is over.
        """
        silent = quiet or record["status"] == content.status
        payload = _activity_payload(
            content, record["tag"], record["title"], silent=silent
        )
        plain = _fingerprint(payload)
        route, webhook = self._live_route(device, record["tag"], ctx.now)
        if route is _Route.UPDATE:
            record["seen"] = True
        elif route is _Route.OTHER:
            if record["seen"]:
                _mark_ended(record, REASON_DISMISSED)
                return
            record["service"] = device.service
            self._pin_later(ctx.now)
            return
        if pinned is not None and silent:
            pin_content, pin = pinned
            pin_payload = _activity_payload(
                pin_content, record["tag"], record["title"], silent=True
            )
            keyed = _fingerprint(pin_payload, pin)
            if keyed == record["fp"]:
                record["service"] = device.service
                return
            if route is _Route.UPDATE and webhook is not None:
                if await self._async_push(device, webhook, pin_payload):
                    record["fp"] = keyed
                    record["pin"] = True
                    record["plain"] = plain
                    record["status"] = content.status
                    record["service"] = device.service
                    _note_shown(day, device, record, content)
                else:
                    self._retry(ctx.now)
                return
            self._pin_later(ctx.now)
            if record["pin"] and plain == record["plain"]:
                # Keep the PIN shown until its change can be pushed.
                record["service"] = device.service
                return
        elif pinned is not None:
            # A new status alerts without the PIN, which follows quietly.
            self._pin_later(ctx.now)
        if plain == record["fp"]:
            record["service"] = device.service
            return
        result = await self._async_send(device.service, device.kind, payload)
        if result is _Result.SENT:
            record["fp"] = plain
            record["status"] = content.status
            record["service"] = device.service
            record["pin"] = False
            record["plain"] = None
            _note_shown(day, device, record, content)
            if pinned is not None and not silent:
                self._pin_later(ctx.now, first=True)
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
        if result is _Result.STALE:
            return False
        started = _parse_dt(record["started"])
        if (
            result is not _Result.SENT
            and started is not None
            and now < started + APPLE_LIMIT
        ):
            self._retry(now)
            return False
        _mark_ended(record, reason)
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
        """Call a mobile_app notify service; nothing that is sent is logged.

        In a round that starts over, nothing is sent once the parcels changed.
        """
        if self._restartable and self._changed:
            return _Result.STALE
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

    def _pin_later(self, now: datetime, *, first: bool = False) -> None:
        """Look again soon for an activity a PIN can go to, then less often.

        A ``first`` look, for an activity just started or just turned to a
        status with a PIN, comes soon even while another PIN waits longer.
        """
        if first:
            self._pin_tries = 0
        at = now + PIN_RETRY[min(self._pin_tries, len(PIN_RETRY) - 1)]
        if self._pin_at is None or at < self._pin_at:
            self._pin_at = at

    def _live_route(
        self, device: _Device, tag: str, now: datetime
    ) -> tuple[_Route, str | None]:
        """Return what a push to an activity's tag does now, and its webhook.

        mobile_app updates an activity whose push token it holds and starts
        one otherwise. A token about to expire counts as gone, and anything
        unexpected in what mobile_app keeps reads as unknown.
        """
        try:
            mobile = self.hass.data.get(MOBILE_APP_DOMAIN)
            if not isinstance(mobile, Mapping):
                return _Route.UNKNOWN, None
            targets = getattr(mobile.get("notify"), "registered_targets", None)
            entries = mobile.get("config_entries")
            tokens = mobile.get("live_activity_tokens")
            if not (
                isinstance(targets, Mapping)
                and isinstance(entries, Mapping)
                and isinstance(tokens, Mapping)
            ):
                return _Route.UNKNOWN, None
            webhook = targets.get(device.service)
            if not isinstance(webhook, str) or webhook not in entries:
                return _Route.UNKNOWN, None
            stored = (tokens.get(webhook) or {}).get(tag)
            if stored is None:
                return _Route.OTHER, webhook
            if not isinstance(stored, Mapping):
                return _Route.UNKNOWN, None
            if float(stored["expires_at"]) > (now + TOKEN_MARGIN).timestamp():
                return _Route.UPDATE, webhook
        except Exception:
            return _Route.UNKNOWN, None
        return _Route.OTHER, webhook

    async def _async_push(
        self, device: _Device, webhook: str, payload: dict[str, Any]
    ) -> bool:
        """Push a quiet update straight to an iPhone; return True when sent.

        Unlike a notify service call it fires no event, so what it carries
        stays off the event bus, the recorder and the logbook.
        """
        title = payload.get("title")
        try:
            await self.hass.data[MOBILE_APP_DOMAIN]["notify"].async_send_message(
                payload["message"],
                target=[webhook],
                data=dict(payload["data"]),
                **({"title": title} if title else {}),
            )
        except Exception as err:
            _LOGGER.warning(
                "Notifying a device (%s) failed: %s",
                device.kind,
                _describe_error(err),
            )
            return False
        return True

    async def _async_test_pin(self, ctx: _Context) -> None:
        """Show the made-up PIN on the demo activity once the iPhone holds it."""
        test = self._data.get("test")
        if (
            test is None
            or test["pin"]
            or not ctx.options.pin
            or not self.live_activities_enabled
        ):
            return
        end_at = _parse_dt(test["end_at"])
        device = self._devices.get(test["device"])
        if (
            end_at is None
            or ctx.now >= end_at - DUE_TOLERANCE
            or device is None
            or device.kind is not DeviceKind.IPHONE
        ):
            return
        route, webhook = self._live_route(device, TEST_TAG, ctx.now)
        if route is not _Route.UPDATE or webhook is None:
            self._pin_later(ctx.now)
            return
        payload = _test_payload(ctx.now, ctx.options.path, pin=TEST_PIN)
        if await self._async_push(device, webhook, payload):
            test["pin"] = True
        else:
            self._retry(ctx.now)

    async def _async_notify_key(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        parcel: Parcel,
        content: _Content,
        tag: str,
    ) -> bool:
        """Notify a device of a parcel's key news; return True when it was sent.

        News that brings back what the parcel held a moment ago comes quietly,
        unless it's the first the device hears of the parcel today.
        """
        quiet = parcel.id in self._flipping and _told(day, device.device_id, parcel.id)
        payload = _key_payload(content, tag, device.kind, quiet=quiet)
        result = await self._async_send(device.service, device.kind, payload)
        if result is _Result.SENT:
            day["notified"].setdefault(device.device_id, {})[parcel.id] = (
                parcel.state.status.value
            )
            return True
        if result is _Result.FAILED:
            self._retry(ctx.now)
        return False

    async def _async_notify_instead(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        record: dict[str, Any],
        parcels: Sequence[Parcel],
        content_of: Callable[[Parcel], _Content],
        status: str,
    ) -> None:
        """Send as notifications the key news an iPhone's activity can't show.

        That is once the user has dismissed the activity, or while the iPhone
        hasn't sent a new activity's token 5 minutes after its start; news
        that one of the iPhone's activities already showed that day isn't sent
        again, until the parcel's status changes. Once that news is sent, the
        activity shows it quietly when its token comes.
        """
        if record["running"]:
            started = _parse_dt(record["started"])
            if (
                record["seen"]
                or started is None
                or ctx.now < started + TOKEN_WAIT - DUE_TOLERANCE
                or self._live_route(device, record["tag"], ctx.now)[0]
                is not _Route.OTHER
            ):
                return
        elif record["end_reason"] != REASON_DISMISSED:
            return
        sent = failed = False
        shown = day["shown"].get(device.device_id, {})
        for parcel in parcels:
            if not (
                _key_news(day, device.device_id, parcel, shown)
                or _taken_back(day, device.device_id, parcel)
            ):
                continue
            if await self._async_notify_key(
                ctx, day, device, parcel, content_of(parcel), _news_tag(parcel.id)
            ):
                sent = True
            else:
                failed = True
        if sent and not failed and record["running"]:
            record["status"] = status

    async def _async_key_notifications(
        self,
        ctx: _Context,
        day: dict[str, Any],
        device: _Device,
        parcels: dict[str, Parcel],
        pickups: Sequence[_DayReturn] = (),
    ) -> None:
        """Notify an iPad or an Android phone of key changes of today's parcels.

        Each return pickup gets one notification while it waits. An inferred
        delivery isn't news, so it notifies no one.
        """
        if not ctx.in_window or not self.live_activities_enabled:
            return
        board = [
            parcel
            for parcel_id in day["board"]
            if (parcel := parcels.get(parcel_id)) is not None
            and _routed(parcel, device)
            and parcel.state.status not in GONE
        ]
        entries, possibly, riding = _packages(self._host.data, board, ctx.today)
        for parcel in entries:
            if not (
                _key_news(day, device.device_id, parcel)
                or _taken_back(day, device.device_id, parcel)
            ):
                continue
            content = _parcel_content(
                parcel,
                ctx,
                possibly.get(parcel.id, ()),
                holds=_holds(riding.get(parcel.id, ())),
            )
            await self._async_notify_key(
                ctx, day, device, parcel, content, _parcel_tag(parcel.id)
            )
        for item in pickups:
            entry = item.entry
            sent = day["notified"].get(device.device_id, {})
            if entry.done(ctx.today) or sent.get(entry.id) == RETURN_STATUS:
                continue
            content = _return_content(item, ctx)
            payload = _key_payload(content, _return_tag(entry.id), device.kind)
            result = await self._async_send(device.service, device.kind, payload)
            if result is _Result.SENT:
                day["notified"].setdefault(device.device_id, {})[entry.id] = (
                    RETURN_STATUS
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
        returns = list(_day_returns(self._host.data, shown).values())
        if not listed and not private and not returns:
            self._dismiss_persistent()
            return
        message = _persistent_message(
            listed, private, shown, ctx.today, ctx.options.path, riders, returns
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
        if self._pin_at is not None:
            points.append(self._pin_at)
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
                if started is not None and not record["seen"]:
                    points.append(started + TOKEN_WAIT)
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
