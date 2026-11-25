"""Tests for the Parcel app source.

Parcel's API is mocked with answers shaped like its documentation
(parcelapp.net/help/api-view-deliveries.html and api-add-delivery.html).
Every key, number, shop and postcode is made up.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable
import copy
from datetime import UTC, date, datetime, time, timedelta
from http import HTTPStatus
import json
import logging
from typing import Any
from unittest.mock import patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

from custom_components.parcels.const import (
    CONF_COLLAPSE_THRESHOLD,
    CONF_PARCEL_APP_ADD,
    CONF_PARCEL_APP_DAILY,
    CONF_PARCEL_APP_EVERYONE,
    CONF_PARCEL_APP_IMPORT,
    CONF_PARCEL_APP_KEY,
    CONF_PARCEL_APP_OWNER,
    CONF_PARCEL_APP_POSTCODE,
    DOMAIN,
    EVENT_DELIVERED,
    EVENT_PARCEL_ADDED,
    EVENT_STATUS_CHANGED,
    ISSUE_PARCEL_APP_KEY,
    LeftAt,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.dedup import (
    REPAIR_KEY,
    REPAIR_VERSION,
    Contribution,
    apply_contribution,
    merge_parcels,
    split_parcel,
)
from custom_components.parcels.engine import ParcelsEngine, get_engine
from custom_components.parcels.models import (
    PARCELAPP_PREFIX,
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    Source,
    day_known,
    dt_to_str,
)
from custom_components.parcels.parcelapp.api import ADD_URL, DELIVERIES_URL
from custom_components.parcels.parcelapp.sync import (
    BUSY_INTERVAL,
    ERROR_BACKOFF,
    FALLBACK_DESCRIPTION,
    INTERVAL,
    KEY_BACKOFF,
    LEARN_DAYS,
    LEARN_MAX,
    MAX_BACKOFF,
    MAX_DESCRIPTION,
    MAX_HISTORY,
    MIN_INTERVAL,
    ORIGIN_LABEL,
    RATE_BACKOFF,
    RECONFIGURE_DELAY,
    RECORD_DAYS,
    START_DELAY,
    SWITCH_WINDOW,
    TASK_NAME,
    ParcelAppSync,
    delivery_key,
    order_number,
    status_code,
)
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.seventeentrack import origin_id as tracked_origin
from custom_components.parcels.store import SAVE_DELAY, apply_retention

from .common import OTHER_OWNER, OWNER, add_hub, add_mailbox, async_setup_parcels
from .factories import contribution

NOW = "2026-11-17 10:00:00+00:00"
TODAY = date(2026, 11, 17)
LISBON = "Europe/Lisbon"
KEY = "synthetic-parcel-key-0001"
NEW_KEY = "synthetic-parcel-key-0002"
SECOND = timedelta(seconds=1)
MICROSECOND = timedelta(microseconds=1)
NUMBER = "1Z9W8R371125836041"
OTHER_UPS = "1Z9W8R371125870003"
THIRD_UPS = "1Z9W8R371125900006"
FOURTH_UPS = "1Z9W8R371125911110"
BAD_UPS = "1Z9W8R371125836042"
TBA = "TBA123456789012"
PAACK = "Qm7Rt2Kp9_2"
GLS = "61234567890"
DPD = "09445440512345"
CTT_EXPRESS = "1234567890123"
ORDER = "405-1234567-1234567"
ORDER_KEY = "40512345671234567"
SHOP = "Example Shop"
PLACE = "Example City"
OPTIONS = {CONF_PARCEL_APP_KEY: KEY, CONF_PARCEL_APP_OWNER: OWNER}


class FakeParcelApp:
    """Parcel's API, with the user's deliveries in memory.

    ``deliveries`` is what a read returns. Set ``read_status`` (and
    ``read_headers``) or ``read_error`` to make the reads fail, and
    ``add_status`` and ``add_answer``, or ``add_error``, to answer the adds.
    ``on_add`` runs first with each add's payload, and may change them. A
    delivery that is added joins ``deliveries`` without news, as on Parcel's
    server.
    """

    def __init__(self, aioclient_mock: AiohttpClientMocker) -> None:
        """Start with an empty list."""
        self.mock = aioclient_mock
        self.deliveries: list[dict[str, Any]] = []
        self.read_status = HTTPStatus.OK
        self.read_headers: dict[str, str] = {}
        self.read_error: Exception | None = None
        self.add_status = HTTPStatus.OK
        self.add_answer: dict[str, Any] = {"success": True}
        self.add_error: Exception | None = None
        self.on_add: Callable[[dict[str, Any]], Awaitable[None]] | None = None
        self.reads: list[dict[str, str]] = []
        self.adds: list[dict[str, Any]] = []
        aioclient_mock.get(DELIVERIES_URL, side_effect=self._read)
        aioclient_mock.post(ADD_URL, side_effect=self._add)

    def keys(self) -> list[str | None]:
        """Return the api-key header of every request, in order."""
        return [(headers or {}).get("api-key") for *_, headers in self.mock.mock_calls]

    async def _read(
        self, method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        self.reads.append(dict(url.query))
        if self.read_error is not None:
            return AiohttpClientMockResponse(method, url, exc=self.read_error)
        if self.read_status != HTTPStatus.OK:
            return AiohttpClientMockResponse(
                method,
                url,
                status=self.read_status,
                json={"success": False, "error_message": "Synthetic failure."},
                headers=self.read_headers,
            )
        return AiohttpClientMockResponse(
            method,
            url,
            json={"success": True, "deliveries": copy.deepcopy(self.deliveries)},
        )

    def numbers(self) -> list[str]:
        """Return the numbers sent to be added, in order."""
        return [add["tracking_number"] for add in self.adds]

    async def _add(self, method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        self.adds.append(dict(data))
        if self.on_add is not None:
            await self.on_add(dict(data))
        if self.add_error is not None:
            return AiohttpClientMockResponse(method, url, exc=self.add_error)
        if self.add_status == HTTPStatus.OK and self.add_answer.get("success"):
            self.deliveries.append(
                {
                    "carrier_code": data["carrier_code"],
                    "description": data["description"],
                    "status_code": 8,
                    "tracking_number": data["tracking_number"],
                    "events": [],
                }
            )
        return AiohttpClientMockResponse(
            method, url, status=self.add_status, json=self.add_answer
        )


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on 17 November 2026 at 10:00, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone(LISBON)


@pytest.fixture
def parcel_app(aioclient_mock: AiohttpClientMocker) -> FakeParcelApp:
    """Return Parcel's mocked API."""
    return FakeParcelApp(aioclient_mock)


@pytest.fixture
def options() -> dict[str, Any]:
    """Return the hub options of a test: the Parcel app on, for OWNER."""
    return dict(OPTIONS)


@pytest.fixture
async def engine(
    hass: HomeAssistant, parcel_app: FakeParcelApp, options: dict[str, Any]
) -> ParcelsEngine:
    """Load the hub with the test's options."""
    add_hub(hass, **options)
    return await async_setup_parcels(hass)


def capture(
    engine: ParcelsEngine, monkeypatch: pytest.MonkeyPatch
) -> list[asyncio.Task[Any]]:
    """Collect the Parcel app refreshes that the engine's timers start."""
    tasks: list[asyncio.Task[Any]] = []
    create = engine.async_create_task

    def keep(coro: Coroutine[Any, Any, Any], name: str) -> asyncio.Task[Any]:
        """Start the task as usual and keep it when it's a Parcel app read."""
        task = create(coro, name)
        if name == TASK_NAME:
            tasks.append(task)
        return task

    monkeypatch.setattr(engine, "async_create_task", keep)
    return tasks


@pytest.fixture
def refreshes(
    engine: ParcelsEngine, monkeypatch: pytest.MonkeyPatch
) -> list[asyncio.Task[Any]]:
    """Collect the refreshes that the timer starts."""
    return capture(engine, monkeypatch)


def sync_of(engine: ParcelsEngine) -> ParcelAppSync:
    """Return the engine's Parcel app sync."""
    assert engine.parcelapp is not None
    return engine.parcelapp


async def advance(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    refreshes: list[asyncio.Task[Any]],
    delay: timedelta,
) -> int:
    """Move the clock, run what became due and return how many refreshes ran."""
    freezer.tick(delay)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    count = len(refreshes)
    await asyncio.gather(*refreshes)
    refreshes.clear()
    return count


async def reads_after(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
    delay: timedelta,
) -> int:
    """Move the clock in two steps and return when the next read came.

    Returns 0 when the read came exactly at ``delay``, -1 when it came
    earlier and 1 when it hadn't come by then.
    """
    before = len(parcel_app.reads)
    await advance(hass, freezer, refreshes, delay - SECOND)
    if len(parcel_app.reads) > before:
        return -1
    await advance(hass, freezer, refreshes, SECOND)
    return 0 if len(parcel_app.reads) > before else 1


async def set_options(
    hass: HomeAssistant, engine: ParcelsEngine, **changes: Any
) -> None:
    """Change some hub options, as the options flow does."""
    entry = engine.entry
    hass.config_entries.async_update_entry(entry, options={**entry.options, **changes})
    await hass.async_block_till_done()


def key_issue(hass: HomeAssistant) -> ir.IssueEntry | None:
    """Return the repair about a refused key, if raised."""
    return ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PARCEL_APP_KEY)


def own_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the warnings Parcels logged."""
    return [
        record
        for record in caplog.records
        if record.levelno >= logging.WARNING
        and record.name.startswith("custom_components.parcels")
    ]


def delivery(
    number: str = NUMBER,
    *,
    code: str | None = "ups",
    status: Any = 2,
    events: Iterable[tuple[str, str]] = (("In transit", "2026-11-16 18:30:00"),),
    description: str | None = SHOP,
    **extra: Any,
) -> dict[str, Any]:
    """Return a delivery as Parcel lists it: events are (text, date)."""
    return {
        "carrier_code": code,
        "description": description,
        "status_code": status,
        "tracking_number": number,
        "events": [
            {"event": text, "date": when, "location": PLACE, "additional": ""}
            for text, when in events
        ],
        **extra,
    }


async def read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    parcel_app: FakeParcelApp,
    after: timedelta = MIN_INTERVAL,
) -> None:
    """Read the deliveries once, ``after`` the last read if there was one."""
    before = len(parcel_app.reads)
    if before:
        freezer.tick(after)
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    await hass.async_block_till_done()
    assert len(parcel_app.reads) == before + 1


def add_parcel(
    engine: ParcelsEngine,
    name: str,
    number: str | None = NUMBER,
    *,
    carrier: str | None = "ups",
    kind: MailKind = MailKind.SHIPPED,
    eta: Eta | None = None,
    merchant: str | None = None,
    orders: Iterable[str] = (),
    age: timedelta = timedelta(days=2),
    status: ParcelStatus | None = None,
    owner: str | None = OWNER,
    private: bool = False,
    items: Iterable[str] = (),
    shipment: str | None = None,
) -> Parcel:
    """Add a parcel from an e-mail of ``owner``, received ``age`` ago."""
    now = dt_util.utcnow()
    applied = apply_contribution(
        engine.data,
        contribution(
            f"msg:{name}#0",
            kind=kind,
            time=now - age,
            carrier=carrier,
            number=number,
            merchant=merchant,
            orders=orders,
            shipment_id=shipment,
            eta=eta,
            owner=owner,
            status=status,
            private=private,
            items=items,
        ),
        now,
    )
    engine.async_changed()
    assert applied.parcel_id is not None
    return engine.data.parcels[applied.parcel_id]


def holder(engine: ParcelsEngine, key: str = NUMBER) -> Parcel | None:
    """Return the parcel that holds a delivery."""
    oid = PARCELAPP_PREFIX + key
    return next(
        (parcel for parcel in engine.data.parcels.values() if oid in parcel.origins),
        None,
    )


def record(engine: ParcelsEngine, key: str = NUMBER) -> dict[str, Any]:
    """Return what Parcels keeps of a delivery."""
    return engine.data.parcelapp["records"][key]


def own_events(parcel: Parcel, key: str = NUMBER) -> list[ParcelEvent]:
    """Return the events a delivery gave its parcel, in time order."""
    oid = PARCELAPP_PREFIX + key
    return sorted(
        (event for event in parcel.events if event.origin == oid),
        key=lambda event: event.time,
    )


def counts(engine: ParcelsEngine) -> tuple[int, int, int, int]:
    """Return the last read's deliveries, matched, imported and unmatched."""
    found = engine.data.parcelapp["counts"]
    return (
        found["deliveries"],
        found["matched"],
        found["imported"],
        found["unmatched"],
    )


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """Return a time of November 2026, in UTC (Lisbon's time in November)."""
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def capture_news(hass: HomeAssistant) -> list[tuple[str, str | None]]:
    """Collect the news Parcels fires from now on: its type and status."""
    fired: list[tuple[str, str | None]] = []

    @callback
    def keep(event: Event) -> None:
        """Keep one piece of news."""
        fired.append((event.event_type, event.data.get("status")))

    for event_type in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED):
        hass.bus.async_listen(event_type, keep)
    return fired


# -- Scheduling ----------------------------------------------------------------


@pytest.mark.parametrize("options", [{}, {CONF_PARCEL_APP_KEY: ""}])
async def test_off_without_a_key(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
) -> None:
    """Without a key nothing is read."""
    assert not sync_of(engine).enabled

    assert await advance(hass, freezer, refreshes, timedelta(hours=2)) == 0
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)

    assert parcel_app.reads == []
    assert engine.data.parcelapp == {}


async def test_first_read_a_minute_after_start(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
) -> None:
    """The first read comes a minute after the start, with the key header."""
    assert sync_of(engine).enabled

    assert await reads_after(hass, freezer, refreshes, parcel_app, START_DELAY) == 0

    assert parcel_app.reads == [{"filter_mode": "recent"}]
    assert parcel_app.keys() == [KEY]
    assert engine.data.parcelapp["last_poll"] == dt_to_str(dt_util.utcnow())
    assert sync_of(engine).last_refresh == dt_util.utcnow()
    # Then every quarter of an hour.
    assert await reads_after(hass, freezer, refreshes, parcel_app, INTERVAL) == 0
    assert await reads_after(hass, freezer, refreshes, parcel_app, INTERVAL) == 0
    assert len(parcel_app.reads) == 3


async def test_restart_waits_ten_minutes_after_the_last_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reload doesn't read again before ten minutes have passed."""
    await advance(hass, freezer, refreshes, START_DELAY)
    assert len(parcel_app.reads) == 1
    freezer.tick(timedelta(minutes=3))

    assert await hass.config_entries.async_reload(engine.entry.entry_id)
    await hass.async_block_till_done()
    reloaded = get_engine(hass)
    assert reloaded is not None
    assert reloaded is not engine
    tasks = capture(reloaded, monkeypatch)

    assert (
        await reads_after(
            hass, freezer, tasks, parcel_app, MIN_INTERVAL - timedelta(minutes=3)
        )
        == 0
    )
    assert len(parcel_app.reads) == 2


async def test_refresh_service_respects_the_minimum(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
) -> None:
    """Refresh reads at once unless the last read was under ten minutes ago."""
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert len(parcel_app.reads) == 1

    freezer.tick(timedelta(minutes=2))
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert len(parcel_app.reads) == 1
    # The read it asked for comes as soon as it's allowed.
    assert (
        await reads_after(
            hass,
            freezer,
            refreshes,
            parcel_app,
            MIN_INTERVAL - timedelta(minutes=2),
        )
        == 0
    )
    freezer.tick(MIN_INTERVAL)
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert len(parcel_app.reads) == 3
    assert await reads_after(hass, freezer, refreshes, parcel_app, INTERVAL) == 0


async def test_nothing_after_unload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
) -> None:
    """Unloading the hub stops the reads."""
    await advance(hass, freezer, refreshes, START_DELAY)
    assert await hass.config_entries.async_unload(engine.entry.entry_id)

    await advance(hass, freezer, refreshes, timedelta(hours=1))

    assert len(parcel_app.reads) == 1


# -- Errors --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("headers", "wait"),
    [
        ({}, RATE_BACKOFF),
        ({"Retry-After": "1200"}, timedelta(minutes=20)),
        ({"Retry-After": "30"}, MIN_INTERVAL),
        ({"Retry-After": "172800"}, MAX_BACKOFF),
    ],
)
async def test_rate_limit_waits(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
    headers: dict[str, str],
    wait: timedelta,
) -> None:
    """Too many requests: wait as long as Parcel asks, within limits."""
    parcel_app.read_status = HTTPStatus.TOO_MANY_REQUESTS
    parcel_app.read_headers = headers
    await advance(hass, freezer, refreshes, START_DELAY)
    sync = sync_of(engine)
    assert sync.last_error == "rate_429"
    assert engine.data.parcelapp.get("errors", 0) == 0

    parcel_app.read_status = HTTPStatus.OK
    assert await reads_after(hass, freezer, refreshes, parcel_app, wait) == 0
    assert sync.last_error is None
    assert "backoff_until" not in engine.data.parcelapp


async def test_errors_back_off_until_a_good_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failures wait longer each time; one warning per kind of failure."""
    parcel_app.read_status = HTTPStatus.BAD_GATEWAY
    caplog.set_level(logging.DEBUG, "custom_components.parcels")
    await advance(hass, freezer, refreshes, START_DELAY)
    for wait in (*ERROR_BACKOFF, ERROR_BACKOFF[-1]):
        assert await reads_after(hass, freezer, refreshes, parcel_app, wait) == 0
    sync = sync_of(engine)
    assert engine.data.parcelapp["errors"] == len(ERROR_BACKOFF) + 2
    assert sync.last_error == "server_502"
    warnings = own_warnings(caplog)
    assert len(warnings) == 1
    assert "server_502" in warnings[0].getMessage()
    assert KEY not in caplog.text

    parcel_app.read_status = HTTPStatus.OK
    assert (
        await reads_after(hass, freezer, refreshes, parcel_app, ERROR_BACKOFF[-1]) == 0
    )
    assert engine.data.parcelapp.get("errors", 0) == 0
    assert sync.last_error is None
    # A new failure starts the series again, and is reported again.
    parcel_app.read_error = aiohttp.ClientError()
    assert await reads_after(hass, freezer, refreshes, parcel_app, INTERVAL) == 0
    assert sync.last_error == "network"
    assert (
        await reads_after(hass, freezer, refreshes, parcel_app, ERROR_BACKOFF[0]) == 0
    )
    assert engine.data.parcelapp["errors"] == 2
    warnings = own_warnings(caplog)
    assert len(warnings) == 2


@pytest.mark.parametrize("status", [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN])
async def test_refused_key_raises_a_repair(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
    status: HTTPStatus,
) -> None:
    """A refused key is tried again every six hours, with a repair meanwhile."""
    parcel_app.read_status = status
    await advance(hass, freezer, refreshes, START_DELAY)
    assert key_issue(hass) is not None
    assert sync_of(engine).last_error == f"key_{status.value}"

    assert await reads_after(hass, freezer, refreshes, parcel_app, KEY_BACKOFF) == 0
    assert key_issue(hass) is not None

    parcel_app.read_status = HTTPStatus.OK
    assert await reads_after(hass, freezer, refreshes, parcel_app, KEY_BACKOFF) == 0
    assert key_issue(hass) is None
    assert "key_refused" not in engine.data.parcelapp


async def test_refused_key_repair_comes_back_after_a_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repair is raised again at the start while the same key is set."""
    parcel_app.read_status = HTTPStatus.UNAUTHORIZED
    await advance(hass, freezer, refreshes, START_DELAY)
    ir.async_delete_issue(hass, DOMAIN, ISSUE_PARCEL_APP_KEY)

    assert await hass.config_entries.async_reload(engine.entry.entry_id)
    await hass.async_block_till_done()

    assert key_issue(hass) is not None
    reloaded = get_engine(hass)
    assert reloaded is not None
    tasks = capture(reloaded, monkeypatch)
    # Still six hours after the refusal.
    assert await reads_after(hass, freezer, tasks, parcel_app, KEY_BACKOFF) == 0
    assert len(parcel_app.reads) == 2


async def test_new_key_is_tried_at_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
) -> None:
    """Changing a refused key removes the repair and reads soon."""
    parcel_app.read_status = HTTPStatus.UNAUTHORIZED
    await advance(hass, freezer, refreshes, START_DELAY)
    freezer.tick(MIN_INTERVAL)

    parcel_app.read_status = HTTPStatus.OK
    await set_options(hass, engine, **{CONF_PARCEL_APP_KEY: NEW_KEY})
    assert key_issue(hass) is None

    assert (
        await reads_after(hass, freezer, refreshes, parcel_app, RECONFIGURE_DELAY) == 0
    )
    assert parcel_app.keys() == [KEY, NEW_KEY]


async def test_only_parcel_options_reschedule(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
) -> None:
    """Other options keep the timer; the Parcel app's read as soon as allowed."""
    await advance(hass, freezer, refreshes, START_DELAY)
    freezer.tick(timedelta(minutes=1))
    await set_options(hass, engine, **{CONF_COLLAPSE_THRESHOLD: 5})
    assert (
        await reads_after(
            hass, freezer, refreshes, parcel_app, INTERVAL - timedelta(minutes=1)
        )
        == 0
    )

    freezer.tick(timedelta(minutes=1))
    await set_options(hass, engine, **{CONF_PARCEL_APP_DAILY: 5})
    assert (
        await reads_after(
            hass, freezer, refreshes, parcel_app, MIN_INTERVAL - timedelta(minutes=1)
        )
        == 0
    )


async def test_cleared_key_stops_and_forgets(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
) -> None:
    """Clearing the key stops the reads and drops what the source kept."""
    await advance(hass, freezer, refreshes, START_DELAY)
    assert engine.data.parcelapp

    await set_options(hass, engine, **{CONF_PARCEL_APP_KEY: ""})
    assert engine.data.parcelapp == {}
    await advance(hass, freezer, refreshes, timedelta(hours=1))
    assert len(parcel_app.reads) == 1

    await set_options(hass, engine, **{CONF_PARCEL_APP_KEY: KEY})
    assert (
        await reads_after(hass, freezer, refreshes, parcel_app, RECONFIGURE_DELAY) == 0
    )


# -- Reading -------------------------------------------------------------------


async def test_delivery_joins_its_parcel(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery with a parcel's number adds its news and name to that parcel."""
    parcel = add_parcel(engine, "a")
    parcel_app.deliveries = [delivery()]

    await read(hass, freezer, parcel_app)

    joined = holder(engine)
    assert joined is not None
    assert joined.id == parcel.id
    assert len(engine.data.parcels) == 1
    origin = joined.origins[PARCELAPP_PREFIX + NUMBER]
    assert origin.source is Source.PARCELAPP
    assert origin.label == ORIGIN_LABEL
    assert origin.name == SHOP
    assert origin.merchant is None
    assert origin.owners == ()
    assert origin.tracking_number == NUMBER
    assert origin.carrier == "ups"
    assert origin.time == at(16, 18, 30)
    state = joined.state
    assert state.status is ParcelStatus.IN_TRANSIT
    assert state.name == SHOP
    assert [
        (entry.time, entry.status, entry.label, entry.source)
        for entry in state.timeline
        if entry.origin == origin.id
    ] == [
        (
            at(16, 18, 30),
            ParcelStatus.IN_TRANSIT,
            "In transit, Example City",
            Source.PARCELAPP,
        )
    ]
    assert counts(engine) == (1, 1, 0, 0)
    assert record(engine)["held"] is True


async def test_history_keeps_the_ten_newest_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Ten distinct events are kept, newest first; only the newest has a status."""
    hours = [7, 2, 11, 0, 5, 9, 3, 10, 1, 8, 4, 6]
    events = [(f"Scan {hour}", f"2026-11-16 {hour:02d}:00:00") for hour in hours]
    events.insert(3, ("Scan 5", "2026-11-16 05:00:00"))
    add_parcel(engine, "a")
    parcel_app.deliveries = [delivery(events=events)]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    kept = own_events(parcel)
    assert [(event.time, event.label) for event in kept] == [
        (at(16, hour), f"Scan {hour}, Example City") for hour in range(2, 12)
    ]
    assert [event.status for event in kept] == [None] * 9 + [ParcelStatus.IN_TRANSIT]
    history = record(engine)["history"]
    assert len(history) == MAX_HISTORY == 10
    assert history[0] == {
        "info": "Scan 11, Example City",
        "at": "2026-11-16T11:00:00+00:00",
        "status": "in_transit",
    }


async def test_history_keeps_the_order_without_every_date(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Unless every event is dated, the list's order stands.

    An undated event goes just after the newest of the older ones, and keeps
    when it was first seen. Events without text or date, and entries that
    aren't events, are skipped.
    """
    item = delivery(
        events=(
            ("Departed", "garbage"),
            ("Arrived", "2026-11-15 08:00:00"),
            ("Sorted", "2026-11-16 08:00:00"),
        )
    )
    item["events"] += [{"event": " ", "date": "garbage", "location": ""}, "junk"]
    add_parcel(engine, "a")
    parcel_app.deliveries = [item]

    await read(hass, freezer, parcel_app)

    assert [
        (entry["info"], entry["at"], entry.get("seen"), entry["status"])
        for entry in record(engine)["history"]
    ] == [
        ("Departed, Example City", None, dt_to_str(at(17, 10)), "in_transit"),
        ("Arrived, Example City", "2026-11-15T08:00:00+00:00", None, None),
        ("Sorted, Example City", "2026-11-16T08:00:00+00:00", None, None),
    ]
    parcel = holder(engine)
    assert parcel is not None
    assert [
        (event.time, event.label, event.undated, event.dayless)
        for event in own_events(parcel)
    ] == [
        (at(15, 8), "Arrived, Example City", False, False),
        (at(16, 8), "Sorted, Example City", False, False),
        (at(16, 8) + 10 * MICROSECOND, "Departed, Example City", True, False),
    ]


async def test_delivery_without_events_gives_its_status(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery without events still tells its status, without a date.

    It goes on the parcel's last known day, here its shipping e-mail's: the
    read may come days after the status changed. Without a date, out for
    delivery doesn't mean today.
    """
    add_parcel(engine, "a")
    parcel_app.deliveries = [delivery(status=4, events=())]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    anchored = at(15, 10) + 10 * MICROSECOND
    assert [
        (event.time, event.status, event.label, event.undated)
        for event in own_events(parcel)
    ] == [(anchored, ParcelStatus.OUT_FOR_DELIVERY, None, True)]
    state = parcel.state
    assert state.status is ParcelStatus.OUT_FOR_DELIVERY
    assert (state.status_time, state.status_undated) == (anchored, True)
    assert state.eta is None


async def test_reading_again_keeps_what_was_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """An unchanged delivery changes nothing; known events keep time and status."""
    add_parcel(engine, "a")
    parcel_app.deliveries = [delivery()]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    updated = parcel.updated

    await read(hass, freezer, parcel_app)

    assert holder(engine) is parcel
    assert parcel.updated == updated

    parcel_app.deliveries = [
        delivery(
            status=4,
            events=(
                ("Out for delivery", "2026-11-17 09:30:00"),
                ("In transit", "2026-11-16 18:30:00"),
            ),
        )
    ]
    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    assert parcel.updated > updated
    assert [(event.time, event.status) for event in own_events(parcel)] == [
        (at(16, 18, 30), ParcelStatus.IN_TRANSIT),
        (at(17, 9, 30), ParcelStatus.OUT_FOR_DELIVERY),
    ]
    assert parcel.state.status is ParcelStatus.OUT_FOR_DELIVERY


async def test_undated_event_never_takes_the_read_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """An undated event stays on the parcel's last known day.

    It keeps when it was first seen with its status; a new status is seen
    again.
    """
    add_parcel(engine, "a")
    parcel_app.deliveries = [delivery(events=(("Update", "garbage"),))]
    await read(hass, freezer, parcel_app)

    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    anchored = at(15, 10) + 10 * MICROSECOND
    assert [
        (event.time, event.status, event.undated) for event in own_events(parcel)
    ] == [(anchored, ParcelStatus.IN_TRANSIT, True)]
    assert record(engine)["history"][0]["seen"] == dt_to_str(at(17, 10))

    parcel_app.deliveries = [delivery(status=4, events=(("Update", "garbage"),))]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    assert [
        (event.time, event.status, event.undated) for event in own_events(parcel)
    ] == [(anchored, ParcelStatus.OUT_FOR_DELIVERY, True)]
    assert record(engine)["history"][0]["seen"] == dt_to_str(
        at(17, 10) + 2 * MIN_INTERVAL
    )


@pytest.mark.parametrize("parcel_date", [False, True])
async def test_undated_delivery_goes_on_the_expected_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    parcel_date: bool,
) -> None:
    """A delivery read days later without a date isn't put on the read's day.

    It goes on the parcel's last known day, here the expected day, Parcel's
    or the e-mails', and stays marked as undated.
    """
    add_parcel(
        engine,
        "a",
        age=timedelta(days=7),
        eta=None if parcel_date else Eta(day(12), day(12)),
    )
    expected = {"date_expected": "2026-11-12 00:00:00"} if parcel_date else {}
    parcel_app.deliveries = [
        delivery(status=0, events=(("Delivered", "garbage"),), **expected)
    ]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    anchored = at(12, 0) + 10 * MICROSECOND
    assert [
        (event.time, event.status, event.undated)
        for event in own_events(parcel)
        if event.status is not None
    ] == [(anchored, ParcelStatus.DELIVERED, True)]
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert (state.status_time, state.status_undated) == (anchored, True)
    assert (state.delivered_at, state.delivered_undated) == (anchored, True)


async def test_undated_delivery_after_a_dated_one(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Parcel's undated delivery doesn't add one at the read time.

    It goes just after the delivery an e-mail dated, which keeps its time.
    """
    add_parcel(
        engine, "a", kind=MailKind.DELIVERED, age=timedelta(hours=21, minutes=17)
    )
    parcel_app.deliveries = [delivery(status=0, events=(("Delivered", "garbage"),))]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    delivered = at(16, 12, 43)
    assert [
        (event.time, event.status, event.undated) for event in own_events(parcel)
    ] == [(delivered + 10 * MICROSECOND, ParcelStatus.DELIVERED, True)]
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert (state.status_time, state.status_undated) == (delivered, False)
    assert (state.delivered_at, state.delivered_undated) == (delivered, False)


async def test_imported_undated_delivery_has_no_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery only in Parcel, delivered on a day not known, has no day.

    Nothing tells when it happened: it isn't dated by the read, and no news
    is fired for it.
    """
    fired = capture_news(hass)
    parcel_app.deliveries = [delivery(status=0, events=(("Delivered", "garbage"),))]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    assert [
        (event.time, event.status, event.undated, event.dayless)
        for event in own_events(parcel)
    ] == [(at(17, 10), ParcelStatus.DELIVERED, True, True)]
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert (state.status_time, state.status_undated) == (None, True)
    assert (state.delivered_at, state.delivered_undated) == (None, True)
    assert fired == []


@pytest.mark.parametrize("same_day", [True, False])
async def test_undated_delivery_waits_for_a_dated_report(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    same_day: bool,
) -> None:
    """No news for a delivery of a day not known, until an e-mail dates it.

    An e-mail from the day Parcel's delivery was read gives its time, and
    the news then. One from a later day is about it too, but its date isn't
    the delivery's: nothing changes.
    """
    add_parcel(engine, "a")
    await hass.async_block_till_done()
    fired = capture_news(hass)
    parcel_app.deliveries = [delivery(status=0, events=(("Delivered", "garbage"),))]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    anchored = at(15, 10) + 10 * MICROSECOND
    assert [
        (event.time, event.status, event.undated, event.by)
        for event in own_events(parcel)
    ] == [(anchored, ParcelStatus.DELIVERED, True, at(17, 10))]
    assert (parcel.state.status_time, parcel.state.status_undated) == (
        anchored,
        True,
    )
    assert fired == []

    if not same_day:
        freezer.move_to(at(18, 10))
    add_parcel(engine, "b", kind=MailKind.DELIVERED, age=timedelta(hours=1))
    await hass.async_block_till_done()

    parcel = holder(engine)
    assert parcel is not None
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    if same_day:
        assert (state.status_time, state.status_undated) == (at(17, 9), False)
        assert (state.delivered_at, state.delivered_undated) == (at(17, 9), False)
        assert fired == [
            (EVENT_STATUS_CHANGED, ParcelStatus.DELIVERED.value),
            (EVENT_DELIVERED, ParcelStatus.DELIVERED.value),
        ]
    else:
        assert (state.status_time, state.status_undated) == (anchored, True)
        assert (state.delivered_at, state.delivered_undated) == (anchored, True)
        assert fired == []


async def test_day_only_delivery_stays_on_its_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A date whose time isn't understood still gives the event its day.

    The delivery goes on its own day, with its time not known: not on the
    day of an older event, nor on the expected day. It's news while it can
    have happened in the last day.
    """
    add_parcel(engine, "a", age=timedelta(days=7), eta=Eta(day(18), day(18)))
    await hass.async_block_till_done()
    fired = capture_news(hass)
    parcel_app.deliveries = [
        delivery(
            status=0,
            events=(
                ("Delivered", "Monday, 16 November 4:20 qwerty"),
                ("In transit", "2026-11-13 09:05:00"),
            ),
        )
    ]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    placed = at(16, 0) + MAX_HISTORY * MICROSECOND
    delivered = [event for event in own_events(parcel) if event.status is not None]
    assert [
        (event.time, event.status, event.undated, event.timeless) for event in delivered
    ] == [(placed, ParcelStatus.DELIVERED, True, True)]
    assert day_known(delivered[0])
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert (state.status_time, state.status_undated, state.status_timeless) == (
        placed,
        True,
        True,
    )
    assert (
        state.delivered_at,
        state.delivered_undated,
        state.delivered_timeless,
    ) == (placed, True, True)
    newest = record(engine)["history"][0]
    assert (newest["at"], newest["day"]) == (None, "2026-11-16")
    assert fired == [
        (EVENT_STATUS_CHANGED, ParcelStatus.DELIVERED.value),
        (EVENT_DELIVERED, ParcelStatus.DELIVERED.value),
    ]


@pytest.mark.parametrize(
    ("written", "when"),
    [
        ("sábado, 14 de novembro 3:15 da tarde", at(14, 15, 15)),
        ("sexta-feira, 13 de novembro 12:30 da madrugada", at(13, 0, 30)),
        ("Saturday, 14 November 3:15 pm WET", at(14, 15, 15)),
        ("Saturday, 14 November 4:15 pm GMT+1", at(14, 15, 15)),
    ],
)
async def test_dates_with_the_part_of_the_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    written: str,
    when: datetime,
) -> None:
    """A date with the part of the day or a time zone after its time is read."""
    add_parcel(engine, "a", age=timedelta(days=7))
    parcel_app.deliveries = [delivery(status=0, events=(("Delivered", written),))]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    assert [
        (event.time, event.status, event.undated, event.timeless)
        for event in own_events(parcel)
    ] == [(when, ParcelStatus.DELIVERED, False, False)]
    assert (parcel.state.delivered_at, parcel.state.delivered_undated) == (
        when,
        False,
    )
    newest = record(engine)["history"][0]
    assert newest["at"] == dt_to_str(when)
    assert "day" not in newest


@pytest.mark.parametrize(
    ("code", "text", "written", "details"),
    [
        (
            0,
            "Entregue - Caixa de correio",
            "2026-11-16 18:30:00",
            {"left_at": LeftAt.MAILBOX},
        ),
        (0, "Entregue - Caixa de correio", "garbage", {"left_at": LeftAt.MAILBOX}),
        (
            3,
            "Disponível para levantamento até 19/11",
            "2026-11-16 18:30:00",
            {"collect_by": date(2026, 11, 19)},
        ),
        (
            3,
            "Disponível para levantamento até 19/11",
            "Monday, 16 November 4:20 qwerty",
            {"collect_by": date(2026, 11, 19)},
        ),
        (3, "Disponível para levantamento até 19/11", "garbage", {}),
        (
            6,
            "Destinatário ausente. Nova entrega amanhã",
            "2026-11-16 18:30:00",
            {"next_attempt": TODAY},
        ),
        (6, "Destinatário ausente. Nova entrega amanhã", "garbage", {}),
    ],
    ids=[
        "left",
        "left-undated",
        "collect",
        "collect-day-only",
        "collect-undated",
        "attempt",
        "attempt-undated",
    ],
)
async def test_event_text_gives_details(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    code: int,
    text: str,
    written: str,
    details: dict[str, Any],
) -> None:
    """An event's text says until when to collect, the next attempt and where.

    Its days count from the event's own day, so an event whose day isn't
    known gives none; where a parcel was left needs no day.
    """
    add_parcel(engine, "a", age=timedelta(days=7))
    parcel_app.deliveries = [delivery(status=code, events=((text, written),))]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    fields = ("collect_by", "next_attempt", "left_at")
    assert [
        {name: getattr(event, name) for name in fields if getattr(event, name)}
        for event in own_events(parcel)
    ] == [details]
    state = parcel.state
    assert {name: getattr(state, name) for name in fields if getattr(state, name)} == (
        details
    )


async def test_dates_read_later_keep_what_was_seen(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Events stored before their dates could be read stay the same events.

    They keep the statuses they had and when they were first seen.
    """
    add_parcel(engine, "a", age=timedelta(days=7))
    parcel_app.deliveries = [
        delivery(
            status=0,
            events=(
                ("Delivered", "Monday, 16 November 4:20 qwerty"),
                ("Out for delivery", "segunda-feira, 16 de novembro 7:50 da manhã"),
            ),
        )
    ]
    await read(hass, freezer, parcel_app)
    # As an earlier version kept them, without their dates.
    seen = dt_to_str(at(16, 11))
    stored = record(engine)
    stored["history"] = [
        {"info": entry["info"], "at": None, "status": status, "seen": seen}
        for entry, status in zip(
            stored["history"], ("delivered", "out_for_delivery"), strict=True
        )
    ]
    stored.pop("fp")

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    out = at(16, 7, 50)
    assert [
        (event.time, event.status, event.timeless, event.by)
        for event in own_events(parcel)
        if event.status is not None
    ] == [
        (out, ParcelStatus.OUT_FOR_DELIVERY, False, None),
        (out + MAX_HISTORY * MICROSECOND, ParcelStatus.DELIVERED, True, at(16, 11)),
    ]
    history = record(engine)["history"]
    assert [entry["status"] for entry in history] == [
        "delivered",
        "out_for_delivery",
    ]
    assert history[0]["seen"] == seen


async def test_diagnostics_tell_the_dates_not_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Diagnostics count the event dates of the last read Parcels can't use.

    Dates to come are only counted. The ten commonest shapes are kept: digits
    become 9 and words x, but for the words of dates. Never the events.
    """
    dates = [
        "garbage",
        "garbage",
        "garbage",
        "Today, 2:05 PM",
        "Today, 2:05 PM",
        "2026-11-25 10:00:00",
        *("#" + "1" * size for size in range(1, 8)),
        "abc1",
        "2026-11-16 18:30:00",
    ]
    item = delivery(
        events=[(f"Secret note {index}", value) for index, value in enumerate(dates)]
    )
    item["events"].append({"event": "Secret note", "location": PLACE})
    parcel_app.deliveries = [item]

    await read(hass, freezer, parcel_app)

    diagnostics = sync_of(engine).diagnostics()
    found = diagnostics["event_dates"]
    assert (found["unparsed"], found["future"]) == (14, 1)
    assert list(found["shapes"].items()) == [
        ("x", 3),
        ("today, 9:99 pm", 2),
        ("#9", 1),
        ("#99", 1),
        ("#999", 1),
        ("#9999", 1),
        ("#99999", 1),
        ("#999999", 1),
        ("#9999999", 1),
        ("missing", 1),
    ]
    text = json.dumps(diagnostics)
    for secret in ("Secret", "garbage", "Today", "abc", NUMBER, SHOP, PLACE):
        assert secret not in text


async def test_diagnostics_tell_the_dates_read_in_part(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Diagnostics count the dates read without their time apart.

    Their shapes keep a short last word as it is. The shapes of the dates
    read with a part of the day or a time zone after the time are kept too.
    """
    dates = [
        "garbage",
        "Monday, 16 November 4:20 qwerty",
        "Monday, 16 November 4:20 qwerty",
        "Monday, 16 November 4:20 Hidden remarks",
        "sábado, 14 de novembro 3:15 da tarde",
        "sexta-feira, 13 de novembro 9:05 da manhã",
        "sexta-feira, 13 de novembro 9:05 da manhã",
        "Saturday, 14 November 3:15 pm WET",
        "2026-11-16 18:30:00",
    ]
    parcel_app.deliveries = [
        delivery(
            events=[
                (f"Secret note {index}", value) for index, value in enumerate(dates)
            ]
        )
    ]

    await read(hass, freezer, parcel_app)

    diagnostics = sync_of(engine).diagnostics()
    found = diagnostics["event_dates"]
    assert (found["unparsed"], found["day_only"], found["future"]) == (1, 3, 0)
    assert found["shapes"] == {"x": 1}
    assert list(found["day_only_shapes"].items()) == [
        ("monday, 99 november 9:99 qwerty", 2),
        ("monday, 99 november 9:99 x", 1),
    ]
    assert list(found["marked"].items()) == [
        ("sexta-feira, 99 de novembro 9:99 da manha", 2),
        ("sabado, 99 de novembro 9:99 da tarde", 1),
        ("saturday, 99 november 9:99 pm wet", 1),
    ]
    text = json.dumps(diagnostics)
    for secret in ("Secret", "garbage", "Hidden", "remarks", NUMBER, SHOP, PLACE):
        assert secret not in text


async def test_repair_places_undated_events_again(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    parcel_app: FakeParcelApp,
) -> None:
    """Once, the events 0.1.6 put at the time they were read are placed again.

    That time is kept as when they were first seen, and the deliveries are
    applied again at the next read, which keeps them there.
    """
    read_at = at(16, 17, 21)
    data = ParcelsData()
    shipped = contribution(
        "msg:a#0", time=at(14, 9), carrier="ups", number=NUMBER, owner=OWNER
    )
    apply_contribution(data, shipped, at(14, 9))
    delivered = contribution(
        "msg:b#0",
        kind=MailKind.DELIVERED,
        time=at(10, 12),
        carrier="ups",
        number=OTHER_UPS,
        owner=OWNER,
    )
    other = apply_contribution(data, delivered, at(10, 12)).parcel_id
    assert other is not None
    stored: dict[str, Any] = {}
    for key, time_read in ((NUMBER, read_at), (OTHER_UPS, at(11, 9))):
        info = "Delivered, " + PLACE
        apply_contribution(
            data,
            Contribution(
                origin=Origin(
                    id=PARCELAPP_PREFIX + key,
                    source=Source.PARCELAPP,
                    time=time_read,
                    label="Parcel app",
                    carrier="ups",
                    tracking_number=key,
                ),
                events=[
                    ParcelEvent(
                        time=time_read,
                        source=Source.PARCELAPP,
                        status=ParcelStatus.DELIVERED,
                        label=info,
                    )
                ],
            ),
            time_read,
        )
        stored[key] = {
            "history": [
                {
                    "info": info,
                    "at": None,
                    "time": dt_to_str(time_read),
                    "status": "delivered",
                }
            ],
            "fp": "0.1.6",
            "since": dt_to_str(time_read),
            "held": True,
            "code": "ups",
        }
    data.parcels[other].archived = at(11, 10)
    dated = {
        "info": "In transit, " + PLACE,
        "at": dt_to_str(at(16, 8)),
        "time": dt_to_str(at(16, 8)),
        "status": "in_transit",
    }
    stored[THIRD_UPS] = {
        "history": [dated],
        "fp": "0.1.6",
        "since": dt_to_str(at(16, 8)),
        "held": False,
        "code": "ups",
    }
    data.parcelapp["records"] = stored
    data.engine[REPAIR_KEY] = REPAIR_VERSION
    hass_storage[DOMAIN] = {
        "version": 1,
        "minor_version": 1,
        "key": DOMAIN,
        "data": data.as_dict(),
    }
    hub = add_hub(hass, **OPTIONS)

    engine = await async_setup_parcels(hass)

    assert engine.data.engine["parcel_app_dates"] == 2
    assert engine.diagnostics()["parcel_app_dates_repaired"] == 2
    parcel = holder(engine)
    assert parcel is not None
    expected = [(at(14, 9) + 10 * MICROSECOND, ParcelStatus.DELIVERED, True, read_at)]
    assert [
        (event.time, event.status, event.undated, event.by)
        for event in own_events(parcel)
    ] == expected
    assert parcel.state.status_time == at(14, 9) + 10 * MICROSECOND
    archived = holder(engine, OTHER_UPS)
    assert archived is not None
    assert archived.archived is not None
    assert [
        (event.time, event.undated) for event in own_events(archived, OTHER_UPS)
    ] == [(at(10, 12) + 10 * MICROSECOND, True)]
    assert record(engine)["history"] == [
        {
            "info": "Delivered, " + PLACE,
            "at": None,
            "status": "delivered",
            "seen": dt_to_str(read_at),
        }
    ]
    assert "fp" not in record(engine)
    assert "fp" not in record(engine, OTHER_UPS)
    third = record(engine, THIRD_UPS)
    assert third["fp"] == "0.1.6"
    assert third["history"] == [
        {name: value for name, value in dated.items() if name != "time"}
    ]

    with patch("custom_components.parcels.engine.repair_parcel_dates") as repair:
        assert await hass.config_entries.async_reload(hub.entry_id)
        await hass.async_block_till_done()
    repair.assert_not_called()
    engine = get_engine(hass)
    assert engine is not None

    parcel_app.deliveries = [delivery(status=0, events=(("Delivered", "garbage"),))]
    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    assert [
        (event.time, event.status, event.undated, event.by)
        for event in own_events(parcel)
    ] == expected
    assert record(engine)["fp"]


@pytest.mark.parametrize(
    ("code", "event_status", "status"),
    [
        (2, ParcelStatus.IN_TRANSIT, ParcelStatus.IN_TRANSIT),
        (1, None, ParcelStatus.SHIPPED),
        (5, None, ParcelStatus.SHIPPED),
        (None, None, ParcelStatus.SHIPPED),
        (True, None, ParcelStatus.SHIPPED),
        ("0", ParcelStatus.DELIVERED, ParcelStatus.DELIVERED),
        (" 4 ", ParcelStatus.OUT_FOR_DELIVERY, ParcelStatus.OUT_FOR_DELIVERY),
        (3, ParcelStatus.READY_FOR_PICKUP, ParcelStatus.READY_FOR_PICKUP),
        (6, ParcelStatus.ATTEMPTED, ParcelStatus.ATTEMPTED),
        (7, ParcelStatus.EXCEPTION, ParcelStatus.EXCEPTION),
        (8, ParcelStatus.SHIPPED, ParcelStatus.SHIPPED),
    ],
)
async def test_status_codes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    code: Any,
    event_status: ParcelStatus | None,
    status: ParcelStatus,
) -> None:
    """Parcel's status codes become statuses; frozen and not found say nothing."""
    add_parcel(engine, "a")
    parcel_app.deliveries = [
        delivery(status=code, events=(("Update", "2026-11-16 18:30:00"),))
    ]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    assert [event.status for event in own_events(parcel)] == [event_status]
    assert parcel.state.status is status


def day(number: int) -> date:
    """Return a day of November 2026."""
    return date(2026, 11, number)


def expected_eta(parcel: Parcel, key: str = NUMBER) -> list[tuple[datetime, Eta]]:
    """Return the dates a delivery gave its parcel, with when they were heard."""
    return [
        (event.time, event.eta)
        for event in own_events(parcel, key)
        if event.eta is not None
    ]


async def test_expected_date_fills_a_missing_one(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Parcel's expected days fill a missing date, as heard when first read.

    The date goes when Parcel no longer gives one.
    """
    add_parcel(engine, "a")
    parcel_app.deliveries = [
        delivery(
            date_expected="2026-11-19 00:00:00",
            date_expected_end="2026-11-20 00:00:00",
        )
    ]
    await read(hass, freezer, parcel_app)

    expected = Eta(day(19), day(20))
    parcel = holder(engine)
    assert parcel is not None
    assert parcel.state.eta == expected
    assert expected_eta(parcel) == [(at(17, 10), expected)]
    assert record(engine)["eta"] == {
        "value": {
            "start": "2026-11-19",
            "end": "2026-11-20",
            "window_start": None,
            "window_end": None,
        },
        "seen": "2026-11-17T10:00:00+00:00",
    }

    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    assert expected_eta(parcel) == [(at(17, 10), expected)]

    parcel_app.deliveries = [delivery()]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    assert parcel.state.eta is None
    assert expected_eta(parcel) == []
    assert "eta" not in record(engine)


async def test_email_window_stays_against_a_date(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """The same day without a window doesn't take an e-mail's window away."""
    window = Eta(day(19), day(19), time(14), time(16))
    add_parcel(engine, "a", eta=window)
    parcel_app.deliveries = [delivery(date_expected="2026-11-19 00:00:00")]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    assert parcel.state.eta == window
    assert expected_eta(parcel) == []
    assert record(engine)["eta"]["seen"] == dt_to_str(at(17, 10))


async def test_parcel_window_fills_an_email_date(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Parcel's window fills the day an e-mail gave, even after it's repeated."""
    add_parcel(engine, "a", eta=Eta(day(19), day(19)))
    parcel_app.deliveries = [
        delivery(
            date_expected="2026-11-19 14:00:00",
            date_expected_end="2026-11-19 16:00:00",
        )
    ]
    await read(hass, freezer, parcel_app)
    window = Eta(day(19), day(19), time(14), time(16))
    parcel = holder(engine)
    assert parcel is not None
    assert parcel.state.eta == window

    freezer.tick(timedelta(minutes=1))
    add_parcel(engine, "b", eta=Eta(day(19), day(19)), age=timedelta(0))
    parcel = holder(engine)
    assert parcel is not None
    assert parcel.state.eta == Eta(day(19), day(19))

    await read(hass, freezer, parcel_app, after=MIN_INTERVAL - timedelta(minutes=1))
    parcel = holder(engine)
    assert parcel is not None
    assert parcel.state.eta == window
    assert expected_eta(parcel) == [(at(17, 10, 10), window)]


async def test_newer_news_wins_the_date(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Of the e-mails' and Parcel's dates, the newer news wins, either way."""
    add_parcel(engine, "a", eta=Eta(day(19), day(19)))
    parcel_app.deliveries = [delivery(date_expected="2026-11-20 00:00:00")]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    assert parcel.state.eta == Eta(day(20), day(20))

    freezer.tick(timedelta(minutes=1))
    add_parcel(engine, "b", eta=Eta(day(21), day(21)), age=timedelta(0))
    await read(hass, freezer, parcel_app, after=MIN_INTERVAL - timedelta(minutes=1))
    parcel = holder(engine)
    assert parcel is not None
    assert parcel.state.eta == Eta(day(21), day(21))
    assert expected_eta(parcel) == [(at(17, 10), Eta(day(20), day(20)))]

    parcel_app.deliveries = [delivery(date_expected="2026-11-22 00:00:00")]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    assert parcel.state.eta == Eta(day(22), day(22))
    assert expected_eta(parcel) == [(at(17, 10, 20), Eta(day(22), day(22)))]


@pytest.mark.parametrize(
    ("deliveries", "email_kind", "interval"),
    [
        ([delivery(status=4)], None, BUSY_INTERVAL),
        ([delivery(date_expected="2026-11-17 00:00:00")], None, BUSY_INTERVAL),
        ([delivery(date_expected="2026-11-18 00:00:00")], None, INTERVAL),
        ([delivery(status=0, date_expected="2026-11-17 00:00:00")], None, INTERVAL),
        ([], MailKind.OUT_FOR_DELIVERY, INTERVAL),
        ([delivery(GLS, code="gls")], MailKind.OUT_FOR_DELIVERY, INTERVAL),
    ],
)
async def test_reads_more_often_on_delivery_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    refreshes: list[asyncio.Task[Any]],
    parcel_app: FakeParcelApp,
    deliveries: list[dict[str, Any]],
    email_kind: MailKind | None,
    interval: timedelta,
) -> None:
    """Every ten minutes while a parcel Parcel follows may arrive today."""
    add_parcel(
        engine,
        "a",
        OTHER_UPS if email_kind else NUMBER,
        kind=email_kind or MailKind.SHIPPED,
    )
    parcel_app.deliveries = copy.deepcopy(deliveries)
    await advance(hass, freezer, refreshes, START_DELAY)
    assert len(parcel_app.reads) == 1

    assert await reads_after(hass, freezer, refreshes, parcel_app, interval) == 0


@pytest.mark.parametrize(
    ("number", "code", "description", "merchant", "name", "carrier"),
    [
        (NUMBER, "ups", SHOP, None, SHOP, "ups"),
        (NUMBER, "ups", "Amazon.es order", "Amazon", "Amazon.es order", "ups"),
        (TBA, "amzles", "Headphones", "Amazon", "Headphones", "amazon"),
        # Amazon's stores follow orders; only Amazon Logistics' numbers say
        # who delivers.
        (GLS, "amzles", "Headphones", "Amazon", "Headphones", None),
        # Amazon Shipping and Amazon's sellers' site carry other shops' goods.
        (GLS, "amshipuk", "Headphones", None, "Headphones", None),
        (TBA, "swiship", "Headphones", None, "Headphones", "amazon"),
        (GLS, None, SHOP, None, SHOP, None),
        (NUMBER, "ups", None, None, None, "ups"),
        (NUMBER, "ups", "Parcels", None, None, "ups"),
        (NUMBER, "ups", "x" * 150, None, "x" * 100, "ups"),
        (NUMBER, "ups", "a" * 99 + " " + "b" * 50, None, "a" * 99, "ups"),
    ],
)
async def test_delivery_only_in_parcel_becomes_a_parcel(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    number: str,
    code: str | None,
    description: str | None,
    merchant: str | None,
    name: str | None,
    carrier: str | None,
) -> None:
    """A delivery no parcel has becomes one, named after its description.

    Its merchant is only one Parcels knows the description starts with.
    """
    parcel_app.deliveries = [delivery(number, code=code, description=description)]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine, number)
    assert parcel is not None
    assert list(parcel.origins) == [PARCELAPP_PREFIX + number]
    origin = parcel.origins[PARCELAPP_PREFIX + number]
    assert (origin.merchant, origin.name, origin.carrier) == (merchant, name, carrier)
    assert origin.tracking_number == number
    assert origin.owners == (OWNER,)
    assert parcel.state.name == name
    assert parcel.state.status is ParcelStatus.IN_TRANSIT
    assert counts(engine) == (1, 0, 1, 0)
    assert record(engine, number)["import"] is True


@pytest.mark.parametrize("options", [{CONF_PARCEL_APP_KEY: KEY}])
async def test_imported_parcel_without_an_owner(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Without the key's person, imported parcels belong to no one."""
    parcel_app.deliveries = [delivery()]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    assert parcel.origins[PARCELAPP_PREFIX + NUMBER].owners == ()


async def test_turning_imports_off_removes_them(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Without imports, deliveries only in Parcel go; the news on others stays."""
    parcel = add_parcel(engine, "a")
    parcel_app.deliveries = [delivery(), delivery(GLS, code="gls")]
    await read(hass, freezer, parcel_app)
    assert counts(engine) == (2, 1, 1, 0)
    assert len(engine.data.parcels) == 2

    await set_options(hass, engine, **{CONF_PARCEL_APP_IMPORT: False})
    await read(hass, freezer, parcel_app)

    assert holder(engine, GLS) is None
    assert list(engine.data.parcels) == [parcel.id]
    kept = holder(engine)
    assert kept is not None
    assert kept.id == parcel.id
    assert counts(engine) == (2, 1, 0, 1)
    assert record(engine, GLS)["held"] is False
    assert "fp" not in record(engine, GLS)

    await set_options(hass, engine, **{CONF_PARCEL_APP_IMPORT: True})
    await read(hass, freezer, parcel_app)
    assert holder(engine, GLS) is not None
    assert counts(engine) == (2, 1, 1, 0)


async def test_cleared_key_keeps_news_on_email_parcels(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Clearing the key removes imported parcels, not news on e-mail parcels."""
    parcel = add_parcel(engine, "a")
    parcel_app.deliveries = [delivery(), delivery(GLS, code="gls")]
    await read(hass, freezer, parcel_app)

    await set_options(hass, engine, **{CONF_PARCEL_APP_KEY: ""})

    assert holder(engine, GLS) is None
    assert list(engine.data.parcels) == [parcel.id]
    kept = holder(engine)
    assert kept is not None
    assert kept.state.name == SHOP
    assert engine.data.parcelapp == {}


# -- Deliveries that leave the list --------------------------------------------


async def test_import_goes_after_two_reads_without_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A parcel only Parcel knows goes once two reads miss its delivery."""
    parcel_app.deliveries = [delivery()]
    await read(hass, freezer, parcel_app)
    assert holder(engine) is not None

    parcel_app.deliveries = []
    await read(hass, freezer, parcel_app)
    assert holder(engine) is not None
    assert record(engine)["missing"] == 1

    await read(hass, freezer, parcel_app)
    assert engine.data.parcels == {}
    assert record(engine)["missing"] == 2
    assert record(engine)["held"] is False
    assert "fp" not in record(engine)
    assert counts(engine) == (0, 0, 0, 0)


async def test_delivery_back_in_the_list_counts_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery back before the second read starts the count again."""
    parcel_app.deliveries = [delivery()]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    parcel_app.deliveries = []
    await read(hass, freezer, parcel_app)
    parcel_app.deliveries = [delivery()]
    await read(hass, freezer, parcel_app)
    assert record(engine)["missing"] == 0

    parcel_app.deliveries = []
    await read(hass, freezer, parcel_app)

    kept = holder(engine)
    assert kept is not None
    assert kept.id == parcel.id
    assert record(engine)["missing"] == 1


@pytest.mark.parametrize("case", ["delivered", "archived", "email"])
async def test_parcel_stays_when_its_delivery_leaves(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    case: str,
) -> None:
    """Only open parcels made of deliveries go with them.

    A delivered or archived one stays, as does one from e-mails, with its news.
    """
    if case == "email":
        add_parcel(engine, "a")
    parcel_app.deliveries = [delivery(status=0 if case == "delivered" else 2)]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    if case == "archived":
        engine.archive(parcel.id)
    origins = set(parcel.origins)

    parcel_app.deliveries = []
    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    kept = holder(engine)
    assert kept is not None
    assert kept.id == parcel.id
    assert set(kept.origins) == origins
    assert record(engine)["missing"] == 2
    assert record(engine)["held"] is True


async def test_email_about_an_import_keeps_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """An e-mail with an imported parcel's number joins it, which then stays."""
    parcel_app.deliveries = [delivery()]
    await read(hass, freezer, parcel_app)
    imported = holder(engine)
    assert imported is not None

    parcel = add_parcel(engine, "a")
    assert parcel.id == imported.id
    await read(hass, freezer, parcel_app)
    assert counts(engine) == (1, 1, 0, 0)

    parcel_app.deliveries = []
    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    kept = holder(engine)
    assert kept is not None
    assert set(kept.origins) == {PARCELAPP_PREFIX + NUMBER, "msg:a#0"}


@pytest.mark.parametrize("case", ["missing", "import_off", "key_cleared"])
async def test_parcel_added_by_hand_stays(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    case: str,
) -> None:
    """A parcel the user added isn't only in Parcel: it stays, with its news.

    When its delivery leaves the list, imports are turned off or the key is
    cleared, it's kept as a parcel from e-mails is, with the user's edits.
    """
    parcel_id = engine.add_parcel(NUMBER, carrier="ups", owners=(OWNER,))
    engine.update(parcel_id, {"merchant": "Loja Exemplo", "eta_start": "2026-11-18"})
    parcel_app.deliveries = [delivery()]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    assert parcel.id == parcel_id
    assert counts(engine) == (1, 1, 0, 0)
    origins = set(parcel.origins)
    assert len(origins) == 3

    if case == "missing":
        parcel_app.deliveries = []
        await read(hass, freezer, parcel_app)
        await read(hass, freezer, parcel_app)
        assert record(engine)["missing"] == 2
        assert record(engine)["held"] is True
    elif case == "import_off":
        await set_options(hass, engine, **{CONF_PARCEL_APP_IMPORT: False})
        await read(hass, freezer, parcel_app)
        assert counts(engine) == (1, 1, 0, 0)
    else:
        await set_options(hass, engine, **{CONF_PARCEL_APP_KEY: ""})
        assert engine.data.parcelapp == {}

    kept = engine.data.parcels.get(parcel_id)
    assert kept is not None
    assert set(kept.origins) == origins
    assert kept.state.merchant == "Loja Exemplo"
    assert kept.state.eta == Eta(
        start=TODAY + timedelta(days=1), end=TODAY + timedelta(days=1)
    )
    assert own_events(kept)


@pytest.mark.parametrize("merged", [False, True])
async def test_edited_import_goes_with_the_edits(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    merged: bool,
) -> None:
    """The user's edits don't make an import his own: they go with it.

    Also when he merged two imports, each with its edits.
    """
    parcel_app.deliveries = [delivery()]
    if merged:
        parcel_app.deliveries.append(delivery(GLS, code="gls"))
    await read(hass, freezer, parcel_app)
    ids = sorted(engine.data.parcels)
    assert len(ids) == (2 if merged else 1)
    for parcel_id in ids:
        engine.update(
            parcel_id, {"merchant": "Loja Exemplo", "eta_start": "2026-11-18"}
        )
    if merged:
        engine.merge(ids)
        assert len(engine.data.parcels) == 1

    parcel_app.deliveries = []
    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    assert engine.data.parcels == {}


async def test_forgotten_delivery_takes_its_import(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery forgotten after a month out of the list takes its import."""
    parcel_app.deliveries = [delivery(date_expected="2026-12-31 00:00:00")]
    await read(hass, freezer, parcel_app)
    parcel_app.deliveries = []
    await read(hass, freezer, parcel_app, after=RECORD_DAYS - timedelta(hours=1))
    assert holder(engine) is not None
    assert record(engine)["missing"] == 1

    await read(hass, freezer, parcel_app, after=timedelta(hours=1, minutes=1))

    assert NUMBER not in engine.data.parcelapp["records"]
    assert engine.data.parcels == {}


def amazon(number: str = ORDER, **extra: Any) -> dict[str, Any]:
    """Return a delivery with Amazon Spain's code, by default an order's."""
    return delivery(number, code="amzles", description="Amazon.es order", **extra)


def amazon_order(
    engine: ParcelsEngine,
    name: str,
    number: str = ORDER,
    *,
    eta: Eta | None = None,
    age: timedelta = timedelta(days=2),
) -> Parcel:
    """Add the parcel of an Amazon order e-mail, without a tracking number."""
    return add_parcel(
        engine,
        name,
        None,
        carrier=None,
        kind=MailKind.ORDER,
        merchant="Amazon",
        orders=(number,),
        eta=eta,
        age=age,
    )


def amazon_shipment(
    engine: ParcelsEngine, name: str, shipment: str, number: str = ORDER
) -> Parcel:
    """Add the parcel of an Amazon shipping e-mail that names its shipment."""
    return add_parcel(
        engine,
        name,
        None,
        carrier=None,
        merchant="Amazon",
        orders=(number,),
        shipment=shipment,
    )


def shipment_holder(engine: ParcelsEngine, shipment: str) -> Parcel | None:
    """Return the parcel that holds the Parcel app's delivery of a shipment."""
    return next(
        (
            parcel
            for parcel in engine.data.parcels.values()
            for oid, origin in parcel.origins.items()
            if oid.startswith(PARCELAPP_PREFIX)
            and origin.amazon_shipment_id == shipment
        ),
        None,
    )


def parcel_app_origins(parcel: Parcel) -> list[str]:
    """Return the IDs of a parcel's deliveries."""
    return [oid for oid in parcel.origins if oid.startswith(PARCELAPP_PREFIX)]


async def test_delivery_leaving_keeps_the_other_delivery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """When one of two deliveries of a parcel leaves, the other keeps it."""
    order = amazon(date_expected="2026-11-19 00:00:00")
    parcel_app.deliveries = [order, amazon(TBA, date_expected="2026-11-19 00:00:00")]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine, ORDER_KEY)
    assert parcel is not None
    assert set(parcel.origins) == {
        PARCELAPP_PREFIX + ORDER_KEY,
        PARCELAPP_PREFIX + TBA,
    }
    assert counts(engine) == (2, 0, 2, 0)

    parcel_app.deliveries = [order]
    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    kept = holder(engine, ORDER_KEY)
    assert kept is not None
    assert kept.id == parcel.id
    assert list(kept.origins) == [PARCELAPP_PREFIX + ORDER_KEY]
    assert kept.auto_merged is None
    assert record(engine, TBA)["held"] is False
    assert record(engine, ORDER_KEY)["held"] is True

    await read(hass, freezer, parcel_app)
    assert holder(engine, ORDER_KEY) is not None
    assert counts(engine) == (1, 0, 1, 0)


# -- Amazon orders -------------------------------------------------------------


async def test_order_delivery_joins_its_order(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery Parcel follows by order number joins that order's parcel."""
    parcel = amazon_order(engine, "a")
    parcel_app.deliveries = [amazon()]

    await read(hass, freezer, parcel_app)

    joined = holder(engine, ORDER_KEY)
    assert joined is not None
    assert joined.id == parcel.id
    origin = joined.origins[PARCELAPP_PREFIX + ORDER_KEY]
    assert origin.tracking_number is None
    assert origin.order_numbers == (ORDER,)
    assert origin.merchant is None
    assert origin.owners == ()
    assert joined.state.status is ParcelStatus.IN_TRANSIT
    assert counts(engine) == (1, 1, 0, 0)


async def test_order_with_two_parcels_is_left(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """With two open parcels of the order, which one Parcel means is unclear."""
    add_parcel(engine, "a", merchant="Amazon", orders=(ORDER,))
    add_parcel(engine, "b", OTHER_UPS, merchant="Amazon", orders=(ORDER,))
    assert len(engine.data.parcels) == 2
    parcel_app.deliveries = [amazon()]

    await read(hass, freezer, parcel_app)

    assert holder(engine, ORDER_KEY) is None
    assert len(engine.data.parcels) == 2
    assert counts(engine) == (1, 0, 0, 1)


async def test_order_of_an_archived_parcel_is_left(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """An order whose parcel is archived counts as matched and changes nothing."""
    parcel = amazon_order(engine, "a")
    engine.archive(parcel.id)
    parcel_app.deliveries = [amazon()]

    await read(hass, freezer, parcel_app)

    assert holder(engine, ORDER_KEY) is None
    assert list(engine.data.parcels) == [parcel.id]
    assert counts(engine) == (1, 1, 0, 0)


async def test_order_without_a_parcel_becomes_one(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """An order no parcel has becomes an Amazon parcel; its e-mail joins it."""
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)

    parcel = holder(engine, ORDER_KEY)
    assert parcel is not None
    origin = parcel.origins[PARCELAPP_PREFIX + ORDER_KEY]
    assert (
        origin.merchant,
        origin.carrier,
        origin.tracking_number,
        origin.order_numbers,
        origin.owners,
    ) == ("Amazon", None, None, (ORDER,), (OWNER,))
    assert parcel.state.merchant == "Amazon"
    assert parcel.state.carrier is None
    assert counts(engine) == (1, 0, 1, 0)

    joined = amazon_order(engine, "a")
    assert joined.id == parcel.id
    await read(hass, freezer, parcel_app)
    assert counts(engine) == (1, 1, 0, 0)


async def test_amazon_delivery_joins_the_parcel_due_that_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery of Amazon's joins the only Amazon parcel due then; undo holds."""
    parcel = amazon_order(engine, "a", eta=Eta(day(19), day(19)))
    parcel_app.deliveries = [amazon(TBA, date_expected="2026-11-19 00:00:00")]
    await read(hass, freezer, parcel_app)

    joined = holder(engine, TBA)
    assert joined is not None
    assert joined.id == parcel.id
    assert joined.auto_merged is not None
    assert joined.auto_merged.reason == "same_merchant_eta"
    assert joined.auto_merged.origin == PARCELAPP_PREFIX + TBA
    assert counts(engine) == (1, 1, 0, 0)

    restored = engine.undo_merge(parcel.id)
    await read(hass, freezer, parcel_app)

    apart = holder(engine, TBA)
    assert apart is not None
    assert apart.id == restored
    assert list(apart.origins) == [PARCELAPP_PREFIX + TBA]
    assert list(engine.data.parcels[parcel.id].origins) == ["msg:a#0"]
    assert counts(engine) == (1, 0, 1, 0)


async def test_amazon_email_pairs_with_the_delivery_out_that_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """An Amazon parcel due the day a delivery goes out pairs with it.

    The delivery had no date when the e-mail came, so they stayed apart until
    it went out for delivery. Undo keeps them apart.
    """
    parcel_app.deliveries = [amazon(TBA)]
    await read(hass, freezer, parcel_app)
    imported = holder(engine, TBA)
    assert imported is not None
    parcel = amazon_order(engine, "a", eta=Eta(TODAY, TODAY))
    assert parcel.id != imported.id

    parcel_app.deliveries = [
        amazon(TBA, status=4, events=(("Out for delivery", "2026-11-17 09:30:00"),))
    ]
    await read(hass, freezer, parcel_app)

    merged = holder(engine, TBA)
    assert merged is not None
    assert merged.id == imported.id
    assert set(merged.origins) == {PARCELAPP_PREFIX + TBA, "msg:a#0"}
    assert merged.auto_merged is not None
    assert merged.auto_merged.reason == "same_merchant_day"
    assert merged.auto_merged.all_origins == {"msg:a#0"}
    assert counts(engine) == (1, 0, 1, 0)
    await read(hass, freezer, parcel_app)
    assert counts(engine) == (1, 1, 0, 0)

    restored = engine.undo_merge(merged.id)
    await read(hass, freezer, parcel_app)

    assert restored is not None
    assert list(engine.data.parcels[restored].origins) == ["msg:a#0"]
    apart = holder(engine, TBA)
    assert apart is not None
    assert list(apart.origins) == [PARCELAPP_PREFIX + TBA]
    assert len(engine.data.parcels) == 2
    assert engine.suggestions == []
    assert counts(engine) == (1, 0, 1, 0)


async def test_amazon_delivery_with_two_parcels_due_is_a_suggestion(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """With two Amazon parcels due the day a delivery is out, the user picks."""
    first = amazon_order(engine, "a", eta=Eta(TODAY, TODAY))
    second = amazon_order(
        engine, "b", "405-7654321-7654321", eta=Eta(TODAY, TODAY), age=timedelta(1)
    )
    assert first.id != second.id
    parcel_app.deliveries = [
        amazon(TBA, status=4, events=(("Out for delivery", "2026-11-17 09:30:00"),))
    ]

    await read(hass, freezer, parcel_app)

    imported = holder(engine, TBA)
    assert imported is not None
    assert list(imported.origins) == [PARCELAPP_PREFIX + TBA]
    assert counts(engine) == (1, 0, 1, 0)
    [suggestion] = engine.suggestions
    assert suggestion.parcel_id == imported.id
    assert suggestion.candidates == (first.id, second.id)
    assert suggestion.reason == "same_merchant_day"
    assert suggestion.day == TODAY


# -- Amazon shipments ----------------------------------------------------------
# Parcel follows each shipment of an order as a delivery of its own, numbered
# by the order, with the shipment ID as its extra information.

SHIPMENT = "Tq4Wz8Lm1"
OTHER_SHIPMENT = "Hb7Np2Xc5"
SECOND_ORDER = "405-7654321-7654321"
THIRD_ORDER = "403-1111111-2222222"
FOURTH_ORDER = "171-3333333-4444444"


async def test_shipments_of_an_order_join_their_parcels(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Each shipment of an order joins the parcel of its Amazon e-mail."""
    first = amazon_shipment(engine, "a", SHIPMENT)
    second = amazon_shipment(engine, "b", OTHER_SHIPMENT)
    assert first.id != second.id
    parcel_app.deliveries = [
        amazon(extra_information=SHIPMENT),
        amazon(
            extra_information=OTHER_SHIPMENT,
            status=4,
            events=(("Out for delivery", "2026-11-17 09:30:00"),),
        ),
    ]

    await read(hass, freezer, parcel_app)

    joined = shipment_holder(engine, SHIPMENT)
    other = shipment_holder(engine, OTHER_SHIPMENT)
    assert joined is not None
    assert other is not None
    assert (joined.id, other.id) == (first.id, second.id)
    assert joined.state.status is ParcelStatus.IN_TRANSIT
    assert other.state.status is ParcelStatus.OUT_FOR_DELIVERY
    assert len(engine.data.parcels) == 2
    assert counts(engine) == (2, 2, 0, 0)


async def test_shipment_joins_the_parcel_that_names_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Of an order's parcels, a delivery joins the one with its shipment."""
    amazon_shipment(engine, "a", SHIPMENT)
    second = amazon_shipment(engine, "b", OTHER_SHIPMENT)
    parcel_app.deliveries = [amazon(extra_information=OTHER_SHIPMENT)]

    await read(hass, freezer, parcel_app)

    joined = shipment_holder(engine, OTHER_SHIPMENT)
    assert joined is not None
    assert joined.id == second.id
    assert len(engine.data.parcels) == 2
    assert counts(engine) == (1, 1, 0, 0)


async def test_followed_order_learns_its_shipment(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery followed by its order stays put once its shipment is known.

    Its news isn't added twice.
    """
    parcel = amazon_order(engine, "a")
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)
    assert holder(engine, ORDER_KEY) is not None

    parcel_app.deliveries = [amazon(extra_information=SHIPMENT)]
    await read(hass, freezer, parcel_app)

    joined = shipment_holder(engine, SHIPMENT)
    assert joined is not None
    assert joined.id == parcel.id
    assert parcel_app_origins(joined) == [PARCELAPP_PREFIX + ORDER_KEY]
    assert len(own_events(joined, ORDER_KEY)) == 1
    assert joined.state.amazon_shipment_ids == (SHIPMENT,)
    assert counts(engine) == (1, 1, 0, 0)


async def test_delivery_of_another_shipment_leaves_the_parcel(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery followed by its order leaves a parcel of another shipment."""
    parcel = amazon_shipment(engine, "a", SHIPMENT)
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)
    joined = holder(engine, ORDER_KEY)
    assert joined is not None
    assert joined.id == parcel.id

    parcel_app.deliveries = [amazon(extra_information=OTHER_SHIPMENT)]
    await read(hass, freezer, parcel_app)

    moved = shipment_holder(engine, OTHER_SHIPMENT)
    assert moved is not None
    assert moved.id != parcel.id
    assert list(engine.data.parcels[parcel.id].origins) == ["msg:a#0"]
    assert counts(engine) == (1, 0, 1, 0)


async def test_two_shipments_and_one_parcel_of_the_order_are_left(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """With two shipments and one parcel of the order, which is which is unclear."""
    parcel = amazon_order(engine, "a")
    parcel_app.deliveries = [
        amazon(extra_information=SHIPMENT),
        amazon(extra_information=OTHER_SHIPMENT),
    ]

    await read(hass, freezer, parcel_app)

    assert list(engine.data.parcels) == [parcel.id]
    assert list(engine.data.parcels[parcel.id].origins) == ["msg:a#0"]
    assert counts(engine) == (2, 0, 0, 2)


async def test_two_shipments_without_parcels_become_two(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """An order's two shipments become two parcels; each e-mail joins its own.

    A shipment that leaves the list takes its parcel along; the other stays.
    """
    parcel_app.deliveries = [
        amazon(extra_information=SHIPMENT),
        amazon(extra_information=OTHER_SHIPMENT),
    ]
    await read(hass, freezer, parcel_app)

    first = shipment_holder(engine, SHIPMENT)
    second = shipment_holder(engine, OTHER_SHIPMENT)
    assert first is not None
    assert second is not None
    assert first.id != second.id
    assert counts(engine) == (2, 0, 2, 0)

    joined = amazon_shipment(engine, "b", OTHER_SHIPMENT)
    assert joined.id == second.id
    await read(hass, freezer, parcel_app)
    assert counts(engine) == (2, 1, 1, 0)

    parcel_app.deliveries = [amazon(extra_information=OTHER_SHIPMENT)]
    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    assert shipment_holder(engine, SHIPMENT) is None
    assert list(engine.data.parcels) == [second.id]
    kept = shipment_holder(engine, OTHER_SHIPMENT)
    assert kept is not None
    assert kept.id == second.id
    assert counts(engine) == (1, 1, 0, 0)


async def test_shipment_leaves_the_order_for_the_parcel_that_names_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Once its shipment is known, a delivery moves to the parcel naming it.

    Here the user had split the shipping e-mail from the order's parcel.
    """
    parcel = amazon_order(engine, "a")
    amazon_shipment(engine, "b", SHIPMENT)
    assert list(parcel.origins) == ["msg:a#0", "msg:b#0"]
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)
    named = split_parcel(engine.data, parcel.id, ["msg:b#0"], dt_util.utcnow())

    parcel_app.deliveries = [amazon(extra_information=SHIPMENT)]
    await read(hass, freezer, parcel_app)

    joined = shipment_holder(engine, SHIPMENT)
    assert joined is not None
    assert joined.id == named.id
    assert list(engine.data.parcels[parcel.id].origins) == ["msg:a#0"]
    assert counts(engine) == (1, 1, 0, 0)
    assert sync_of(engine).diagnostics()["deliveries"]["amazon"]["by_shipment_id"] == 1


async def test_order_delivery_becomes_the_shipment_its_parcel_names(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery followed by its order stays as the shipment its parcel names.

    The order's other shipment becomes a parcel of its own.
    """
    parcel = amazon_shipment(engine, "a", SHIPMENT)
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)

    parcel_app.deliveries = [
        amazon(extra_information=SHIPMENT),
        amazon(extra_information=OTHER_SHIPMENT),
    ]
    await read(hass, freezer, parcel_app)

    assert parcel_app_origins(engine.data.parcels[parcel.id]) == [
        PARCELAPP_PREFIX + ORDER_KEY
    ]
    other = shipment_holder(engine, OTHER_SHIPMENT)
    assert other is not None
    assert other.id != parcel.id
    assert counts(engine) == (2, 1, 1, 0)


async def test_order_delivery_that_cannot_be_told_leaves_its_parcel(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery followed by its order leaves when the order has two shipments.

    Its parcel names neither, so which one it followed is unclear.
    """
    parcel = amazon_order(engine, "a")
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)

    parcel_app.deliveries = [
        amazon(extra_information=SHIPMENT),
        amazon(extra_information=OTHER_SHIPMENT),
    ]
    await read(hass, freezer, parcel_app)

    assert list(engine.data.parcels) == [parcel.id]
    assert list(engine.data.parcels[parcel.id].origins) == ["msg:a#0"]
    assert counts(engine) == (2, 0, 0, 2)


async def test_shipment_beside_a_delivery_without_one_is_left(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A shipment doesn't join its order's parcel by the order number.

    Not while the order has another delivery whose shipment isn't known.
    """
    parcel = amazon_order(engine, "a")
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)

    parcel_app.deliveries = [amazon(), amazon(extra_information=SHIPMENT)]
    await read(hass, freezer, parcel_app)

    assert shipment_holder(engine, SHIPMENT) is None
    assert parcel_app_origins(engine.data.parcels[parcel.id]) == [
        PARCELAPP_PREFIX + ORDER_KEY
    ]
    assert counts(engine) == (2, 1, 0, 1)


async def test_delivery_without_a_shipment_leaves_the_known_one_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A new delivery of the order without a shipment isn't taken for it.

    The known shipment keeps its parcel and its news.
    """
    parcel = amazon_order(engine, "a")
    parcel_app.deliveries = [amazon(extra_information=SHIPMENT)]
    await read(hass, freezer, parcel_app)
    assert shipment_holder(engine, SHIPMENT) is parcel

    parcel_app.deliveries = [
        amazon(
            extra_information=SHIPMENT,
            status=4,
            events=(("Out for delivery", "2026-11-17 09:30:00"),),
        ),
        amazon(),
    ]
    await read(hass, freezer, parcel_app)

    assert parcel_app_origins(engine.data.parcels[parcel.id]) == [
        PARCELAPP_PREFIX + ORDER_KEY
    ]
    assert parcel.state.status is ParcelStatus.OUT_FOR_DELIVERY
    assert counts(engine) == (2, 1, 0, 1)


async def test_diagnostics_count_amazon_deliveries(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """The diagnostics count how Amazon's deliveries found their parcels."""
    amazon_shipment(engine, "a", SHIPMENT)
    amazon_order(engine, "b", SECOND_ORDER)
    amazon_order(engine, "c", THIRD_ORDER)
    parcel_app.deliveries = [
        amazon(extra_information=SHIPMENT),
        amazon(SECOND_ORDER, extra_information=OTHER_SHIPMENT),
        amazon(THIRD_ORDER, extra_information="Wd2Fh9Qa4"),
        amazon(THIRD_ORDER, extra_information="Zr5Kc8Pv3"),
        amazon(FOURTH_ORDER),
        delivery(),
    ]

    await read(hass, freezer, parcel_app)

    assert sync_of(engine).diagnostics()["deliveries"]["amazon"] == {
        "by_shipment_id": 1,
        "by_order": 1,
        "imported": 1,
        "other": 0,
        "unmatched": 2,
    }


# An Amazon shipment's boxes have their own numbers, and are parcels of their
# own: the first box's e-mails name the shipment, the others add their index.
# Parcel lists the shipment once.
BOX_ONE = "RR102030405PT"
BOX_TWO = "RR102030419PT"
BOX_THREE = "RR102030422PT"


def amazon_box(
    engine: ParcelsEngine, name: str, shipment: str, number: str | None
) -> Parcel:
    """Add the parcel of a box of an Amazon shipment, from its shipping e-mail."""
    return add_parcel(
        engine,
        name,
        number,
        carrier="ctt" if number else None,
        merchant="Amazon",
        orders=(ORDER,),
        shipment=shipment,
    )


async def test_shipment_joins_its_first_box(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A shipment's delivery joins its first box; the other box stays apart."""
    first = amazon_box(engine, "a", SHIPMENT, BOX_ONE)
    second = amazon_box(engine, "b", f"{SHIPMENT}#1", BOX_TWO)
    assert first.id != second.id
    parcel_app.deliveries = [amazon(extra_information=SHIPMENT)]

    await read(hass, freezer, parcel_app)

    joined = holder(engine, ORDER_KEY)
    assert joined is not None
    assert joined.id == first.id
    assert parcel_app_origins(engine.data.parcels[second.id]) == []
    assert len(engine.data.parcels) == 2
    assert counts(engine) == (1, 1, 0, 0)


async def test_shipment_joins_its_only_box(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A shipment's delivery joins the only box known, and stays with it.

    The first box's e-mail without a number, read later, is a parcel apart.
    """
    box = amazon_box(engine, "b", f"{SHIPMENT}#1", BOX_TWO)
    parcel_app.deliveries = [amazon(extra_information=SHIPMENT)]

    await read(hass, freezer, parcel_app)

    joined = holder(engine, ORDER_KEY)
    assert joined is not None
    assert joined.id == box.id
    origin = joined.origins[PARCELAPP_PREFIX + ORDER_KEY]
    assert origin.amazon_shipment_id == f"{SHIPMENT}#1"
    assert record(engine, ORDER_KEY)["shipment"] == SHIPMENT
    assert len(engine.data.parcels) == 1
    assert counts(engine) == (1, 1, 0, 0)
    amazon_counts = sync_of(engine).diagnostics()["deliveries"]["amazon"]
    assert amazon_counts["by_shipment_id"] == 1

    first = amazon_box(engine, "a", SHIPMENT, None)

    assert first.id != box.id
    assert parcel_app_origins(engine.data.parcels[box.id]) == [
        PARCELAPP_PREFIX + ORDER_KEY
    ]


async def test_shipment_with_two_later_boxes_is_left(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """With two boxes known but not the first, which one Parcel follows is unclear."""
    amazon_box(engine, "b", f"{SHIPMENT}#1", BOX_TWO)
    amazon_box(engine, "c", f"{SHIPMENT}#2", BOX_THREE)
    parcel_app.deliveries = [amazon(extra_information=SHIPMENT)]

    await read(hass, freezer, parcel_app)

    assert holder(engine, ORDER_KEY) is None
    assert len(engine.data.parcels) == 2
    assert counts(engine) == (1, 0, 0, 1)


async def test_followed_order_stays_with_its_box(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery followed by its order stays when its shipment is the box's.

    Its news isn't added twice.
    """
    box = amazon_box(engine, "b", f"{SHIPMENT}#1", BOX_TWO)
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)
    followed = holder(engine, ORDER_KEY)
    assert followed is not None
    assert followed.id == box.id

    parcel_app.deliveries = [amazon(extra_information=SHIPMENT)]
    await read(hass, freezer, parcel_app)

    joined = holder(engine, ORDER_KEY)
    assert joined is not None
    assert joined.id == box.id
    assert len(own_events(joined, ORDER_KEY)) == 1
    assert len(engine.data.parcels) == 1
    assert counts(engine) == (1, 1, 0, 0)


async def test_shipment_of_a_known_box_is_placed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A shipment whose box is known leaves the order's parcel to the other one.

    Here the user had split the box's e-mail from the order's parcel.
    """
    parcel = amazon_order(engine, "a")
    amazon_box(engine, "b", f"{SHIPMENT}#1", BOX_TWO)
    assert list(parcel.origins) == ["msg:a#0", "msg:b#0"]
    box = split_parcel(engine.data, parcel.id, ["msg:b#0"], dt_util.utcnow())
    parcel_app.deliveries = [
        amazon(extra_information=SHIPMENT),
        amazon(extra_information=OTHER_SHIPMENT),
    ]

    await read(hass, freezer, parcel_app)

    assert parcel_app_origins(engine.data.parcels[box.id]) == [
        f"{PARCELAPP_PREFIX}{ORDER_KEY}#{SHIPMENT}"
    ]
    assert parcel_app_origins(engine.data.parcels[parcel.id]) == [
        f"{PARCELAPP_PREFIX}{ORDER_KEY}#{OTHER_SHIPMENT}"
    ]
    assert counts(engine) == (2, 2, 0, 0)


async def test_followed_order_keeps_its_box_among_shipments(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery followed into a shipment's later box stays there when Parcel
    then lists the order's shipments: the box's e-mail names that shipment."""
    box = amazon_box(engine, "b", f"{SHIPMENT}#1", BOX_TWO)
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)
    followed = holder(engine, ORDER_KEY)
    assert followed is not None
    assert followed.id == box.id

    parcel_app.deliveries = [
        amazon(extra_information=SHIPMENT),
        amazon(extra_information=OTHER_SHIPMENT),
    ]
    await read(hass, freezer, parcel_app)

    joined = holder(engine, ORDER_KEY)
    assert joined is not None
    assert joined.id == box.id
    assert record(engine, ORDER_KEY)["shipment"] == SHIPMENT
    assert len(own_events(joined, ORDER_KEY)) == 1


async def test_followed_order_stays_with_its_box_beside_another(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery followed into a shipment's box stays with it when Parcel names
    the shipment, though another of the shipment's boxes is known by then."""
    box = amazon_box(engine, "b", f"{SHIPMENT}#1", BOX_TWO)
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)
    followed = holder(engine, ORDER_KEY)
    assert followed is not None
    assert followed.id == box.id
    other = amazon_box(engine, "c", f"{SHIPMENT}#2", BOX_THREE)
    assert other.id != box.id

    parcel_app.deliveries = [amazon(extra_information=SHIPMENT)]
    await read(hass, freezer, parcel_app)

    joined = holder(engine, ORDER_KEY)
    assert joined is not None
    assert joined.id == box.id
    assert parcel_app_origins(engine.data.parcels[other.id]) == []


async def test_order_delivery_moves_to_its_shipments_box(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery followed by its order moves to a box of its shipment once
    Parcel names the shipment: the order's parcel names none.

    Here the user had split the box's e-mail from the order's parcel.
    """
    parcel = amazon_order(engine, "a")
    parcel_app.deliveries = [amazon()]
    await read(hass, freezer, parcel_app)
    followed = holder(engine, ORDER_KEY)
    assert followed is not None
    assert followed.id == parcel.id
    amazon_box(engine, "b", f"{SHIPMENT}#1", BOX_TWO)
    assert "msg:b#0" in engine.data.parcels[parcel.id].origins
    box = split_parcel(engine.data, parcel.id, ["msg:b#0"], dt_util.utcnow())
    assert holder(engine, ORDER_KEY) is engine.data.parcels[parcel.id]

    parcel_app.deliveries = [amazon(extra_information=SHIPMENT)]
    await read(hass, freezer, parcel_app)

    joined = holder(engine, ORDER_KEY)
    assert joined is not None
    assert joined.id == box.id
    origin = joined.origins[PARCELAPP_PREFIX + ORDER_KEY]
    assert origin.amazon_shipment_id == f"{SHIPMENT}#1"
    assert parcel_app_origins(engine.data.parcels[parcel.id]) == []


async def test_shipment_joins_its_merged_boxes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A shipment's delivery joins a parcel the user merged two of its boxes
    into, as the shipment: which box Parcel follows is unknown."""
    first = amazon_box(engine, "b", f"{SHIPMENT}#1", BOX_TWO)
    second = amazon_box(engine, "c", f"{SHIPMENT}#2", BOX_THREE)
    merged = merge_parcels(engine.data, first.id, [second.id], dt_util.utcnow())
    parcel_app.deliveries = [amazon(extra_information=SHIPMENT)]

    await read(hass, freezer, parcel_app)

    joined = holder(engine, ORDER_KEY)
    assert joined is not None
    assert joined.id == merged.id
    origin = joined.origins[PARCELAPP_PREFIX + ORDER_KEY]
    assert origin.amazon_shipment_id == SHIPMENT
    amazon_counts = sync_of(engine).diagnostics()["deliveries"]["amazon"]
    assert amazon_counts["by_shipment_id"] == 1
    assert amazon_counts["by_order"] == 0


async def test_shipment_read_again_keeps_its_box(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A shipment's delivery that joined a later box keeps that box when its
    news is read again."""
    box = amazon_box(engine, "b", f"{SHIPMENT}#1", BOX_TWO)
    sent = ("In transit", "2026-11-15 18:30:00")
    parcel_app.deliveries = [amazon(extra_information=SHIPMENT, events=[sent])]
    await read(hass, freezer, parcel_app)
    oid = PARCELAPP_PREFIX + ORDER_KEY
    assert engine.data.parcels[box.id].origins[oid].amazon_shipment_id == (
        f"{SHIPMENT}#1"
    )

    parcel_app.deliveries = [
        amazon(
            extra_information=SHIPMENT,
            status=4,
            events=[sent, ("Out for delivery", "2026-11-17 08:15:00")],
        )
    ]
    await read(hass, freezer, parcel_app)

    joined = holder(engine, ORDER_KEY)
    assert joined is not None
    assert joined.id == box.id
    assert len(own_events(joined, ORDER_KEY)) == 2
    assert joined.origins[oid].amazon_shipment_id == f"{SHIPMENT}#1"


@pytest.mark.parametrize(
    ("email", "outcome"), [(True, (1, 1, 0, 0)), (False, (1, 0, 1, 0))]
)
async def test_archived_parcel_takes_no_news(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    email: bool,
    outcome: tuple[int, int, int, int],
) -> None:
    """An archived parcel keeps what it had; its delivery still counts."""
    if email:
        add_parcel(engine, "a")
    parcel_app.deliveries = [delivery()]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    engine.archive(parcel.id)
    updated = engine.data.parcels[parcel.id].updated

    parcel_app.deliveries = [
        delivery(status=4, events=(("Out for delivery", "2026-11-17 09:30:00"),))
    ]
    await read(hass, freezer, parcel_app)

    kept = holder(engine)
    assert kept is not None
    assert kept.updated == updated
    assert [event.status for event in own_events(kept)] == [ParcelStatus.IN_TRANSIT]
    assert counts(engine) == outcome


# -- Carrier switches ----------------------------------------------------------

# Parcel may switch an Amazon delivery to the carrier's number: the Amazon
# delivery leaves the list, and the carrier's appears with its description,
# the item's title.
TITLE = "Example desk lamp, warm white, 2 pack…"
CORREOS = "38123456789012345678901"
OTHER_CORREOS = "38123456789012345678902"
SECOND_ORDER_KEY = "40576543217654321"
NO_IMPORTS = {**OPTIONS, CONF_PARCEL_APP_IMPORT: False}


def switched_amazon(
    number: str = ORDER, shipment: str = SHIPMENT, *, description: str | None = TITLE
) -> dict[str, Any]:
    """Return an Amazon order's delivery, described with its item's title."""
    return delivery(
        number,
        code="amzles",
        description=description,
        extra_information=shipment,
        events=(("Arrived at the carrier's facility", "2026-11-15 15:12:00"),),
    )


def carrier_delivery(
    description: str | None = TITLE,
    number: str = CORREOS,
    *,
    status: int = 2,
    events: Iterable[tuple[str, str]] = (("Accepted", "2026-11-15 15:12:00"),),
) -> dict[str, Any]:
    """Return the carrier's delivery Parcel switched the Amazon order to."""
    return delivery(
        number,
        code="chrexp",
        status=status,
        description=description,
        events=events,
        date_expected="2026-11-18 00:00:00",
    )


async def switch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    parcel_app: FakeParcelApp,
    after: timedelta = MIN_INTERVAL,
) -> None:
    """Read the Amazon order's delivery, then only the carrier's, ``after``."""
    parcel_app.deliveries = [switched_amazon()]
    await read(hass, freezer, parcel_app)
    parcel_app.deliveries = [carrier_delivery()]
    await read(hass, freezer, parcel_app, after)


def switched(engine: ParcelsEngine) -> int:
    """Return how many deliveries the diagnostics count as switched."""
    return sync_of(engine).diagnostics()["deliveries"]["switched"]


@pytest.mark.parametrize("options", [OPTIONS, NO_IMPORTS], ids=["import", "no_import"])
async def test_switch_joins_the_orders_parcel(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A carrier's delivery that continues an Amazon order's joins its parcel.

    As if the number were the parcel's own: the parcel takes the number, the
    carrier and the newer date, and other news of the number finds it. The
    join is flagged, so the user can undo it.
    """
    order = amazon_order(engine, "a", eta=Eta(day(25), day(25)))
    parcel_app.deliveries = [switched_amazon()]
    await read(hass, freezer, parcel_app)
    first = holder(engine, ORDER_KEY)
    assert first is not None
    assert first.id == order.id

    parcel_app.deliveries = [carrier_delivery()]
    await read(hass, freezer, parcel_app)

    assert list(engine.data.parcels) == [order.id]
    joined = engine.data.parcels[order.id]
    carried = holder(engine, CORREOS)
    assert carried is not None
    assert carried.id == order.id
    assert joined.state.tracking_number == CORREOS
    assert joined.state.carrier == "correos_express"
    assert joined.state.eta == Eta(day(18), day(18))
    assert joined.auto_merged is not None
    assert joined.auto_merged.reason == "parcel_switch"
    assert joined.auto_merged.all_origins == {PARCELAPP_PREFIX + CORREOS}
    assert counts(engine) == (1, 1, 0, 0)
    assert switched(engine) == 1
    assert record(engine, CORREOS)["switch"] == ORDER_KEY
    assert parcel_app.adds == []

    await read(hass, freezer, parcel_app)

    assert list(engine.data.parcels) == [order.id]
    assert counts(engine) == (1, 1, 0, 0)
    assert switched(engine) == 1

    tracked_news(
        engine,
        ParcelStatus.OUT_FOR_DELIVERY,
        at(17, 9, 45),
        number=CORREOS,
        carrier="correos_express",
    )
    add_parcel(engine, "b", CORREOS, carrier="correos_express")

    assert list(engine.data.parcels) == [order.id]
    assert engine.data.parcels[order.id].state.status is (ParcelStatus.OUT_FOR_DELIVERY)


@pytest.mark.parametrize("case", ["imported", "email"])
async def test_switch_joins_a_held_delivery_on_the_next_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    case: str,
) -> None:
    """A carrier's delivery that already had a parcel joins on the next read.

    Imported before Parcels saw that it continues an Amazon order, or held by
    the carrier's own e-mail: the parcels merge, and the user can undo it.
    Then it doesn't join again.
    """
    order = amazon_order(engine, "a", eta=Eta(day(25), day(25)))
    parcel_app.deliveries = [switched_amazon()]
    await read(hass, freezer, parcel_app)
    parcel_app.deliveries = [carrier_delivery()]
    if case == "email":
        add_parcel(engine, "c", CORREOS, carrier="correos_express")
        await read(hass, freezer, parcel_app)
    else:
        # As before carrier switches were known.
        with patch.object(ParcelAppSync, "_switched_target", return_value=None):
            await read(hass, freezer, parcel_app)
    held = (1, 1, 0, 0) if case == "email" else (1, 0, 1, 0)
    own = holder(engine, CORREOS)
    assert own is not None
    assert own.id != order.id
    assert counts(engine) == held
    assert switched(engine) == 0

    await read(hass, freezer, parcel_app)

    assert list(engine.data.parcels) == [order.id]
    joined = engine.data.parcels[order.id]
    carried = holder(engine, CORREOS)
    assert carried is not None
    assert carried.id == order.id
    assert joined.state.tracking_number == CORREOS
    assert joined.state.eta == Eta(day(18), day(18))
    assert joined.auto_merged is not None
    assert joined.auto_merged.reason == "parcel_switch"
    assert counts(engine) == (1, 1, 0, 0)
    assert switched(engine) == 1

    restored = engine.undo_merge(order.id)
    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    back = holder(engine, CORREOS)
    assert back is not None
    assert back.id == restored
    assert engine.data.parcels[order.id].auto_merged is None
    assert engine.data.parcels[order.id].state.tracking_number is None
    assert record(engine, CORREOS)["switch"] == ""
    assert counts(engine) == held
    assert switched(engine) == 0


@pytest.mark.parametrize(
    "description",
    [
        None,
        "",
        FALLBACK_DESCRIPTION,
        "Amazon",
        "SHEIN",
        "Correos Express",
        "Amazon.es order",
    ],
)
async def test_switch_needs_an_items_title(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    description: str | None,
) -> None:
    """Not when the description isn't an item's title: many deliveries share it.

    None, Parcels' own, or a shop's or carrier's name.
    """
    order = amazon_order(engine, "a")
    parcel_app.deliveries = [switched_amazon(description=description)]
    await read(hass, freezer, parcel_app)
    parcel_app.deliveries = [carrier_delivery(description)]
    await read(hass, freezer, parcel_app)

    own = holder(engine, CORREOS)
    assert own is not None
    assert own.id != order.id
    assert engine.data.parcels[order.id].auto_merged is None
    assert "switch" not in record(engine, CORREOS)
    assert counts(engine) == (1, 0, 1, 0)


@pytest.mark.parametrize("options", [{**OPTIONS, CONF_PARCEL_APP_ADD: False}])
@pytest.mark.parametrize(
    ("case", "joins"),
    [
        ("none", True),
        ("shop", False),
        ("sent", False),
        ("delivered", False),
        ("archived", False),
        ("numbered", False),
        ("imported", False),
        ("overlap", False),
        ("tie", False),
        ("tie_listed", False),
    ],
)
async def test_switch_guards(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    case: str,
    joins: bool,
) -> None:
    """Only to one open order's parcel, whose Amazon delivery left before.

    Not when the title names a shop, or is what Parcels sent; the order's
    parcel is delivered, archived, has a number, or is only the Amazon
    delivery's import; the Amazon delivery is still listed; or two orders'
    deliveries had the title, even with one still listed: a tie, which is
    final.
    """
    title = "Northwind Home Goods order" if case == "shop" else TITLE
    if case == "shop":
        add_parcel(engine, "n", OTHER_UPS, merchant="Northwind Home Goods")
    if case == "numbered":
        add_parcel(
            engine, "a", TBA, carrier="amazon", merchant="Amazon", orders=(ORDER,)
        )
    elif case != "imported":
        amazon_order(engine, "a")
    listed = [switched_amazon(description=title)]
    if case.startswith("tie"):
        amazon_order(engine, "b", SECOND_ORDER)
        listed.append(switched_amazon(SECOND_ORDER, OTHER_SHIPMENT, description=title))
    parcel_app.deliveries = listed
    await read(hass, freezer, parcel_app)
    target = holder(engine, ORDER_KEY)
    assert target is not None
    if case == "sent":
        engine.data.parcelapp["records"][CORREOS] = {"sent": title}
    elif case == "delivered":
        engine.mark_delivered(target.id)
    elif case == "archived":
        engine.archive(target.id)

    still = {"overlap": listed[:1], "tie_listed": listed[1:]}.get(case, [])
    parcel_app.deliveries = [*still, carrier_delivery(title)]
    await read(hass, freezer, parcel_app)
    if case == "overlap":
        parcel_app.deliveries = [carrier_delivery(title)]
        await read(hass, freezer, parcel_app)

    own = holder(engine, CORREOS)
    assert own is not None
    assert (own.id == target.id) is joins
    tie = "" if case.startswith("tie") else None
    assert record(engine, CORREOS).get("switch") == (ORDER_KEY if joins else tie)
    if not joins:
        assert engine.data.parcels[target.id].auto_merged is None


@pytest.mark.parametrize(
    ("after", "joins"), [(SWITCH_WINDOW, True), (SWITCH_WINDOW + SECOND, False)]
)
async def test_switch_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    after: timedelta,
    joins: bool,
) -> None:
    """The Amazon delivery left at most ``SWITCH_WINDOW`` before."""
    order = amazon_order(engine, "a")

    await switch(hass, freezer, parcel_app, after)

    own = holder(engine, CORREOS)
    assert own is not None
    assert (own.id == order.id) is joins


@pytest.mark.parametrize(
    ("options", "outcome"),
    [(OPTIONS, (1, 0, 1, 0)), (NO_IMPORTS, (1, 0, 0, 1))],
    ids=["import", "no_import"],
)
async def test_switch_undo(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    outcome: tuple[int, int, int, int],
) -> None:
    """Undo takes the carrier's delivery back out, and it doesn't join again.

    The order's parcel is as before. The delivery is then like any other
    with no e-mail: imported, or not shown when not importing.
    """
    order = amazon_order(engine, "a", eta=Eta(day(25), day(25)))
    await switch(hass, freezer, parcel_app)

    restored = engine.undo_merge(order.id)
    assert restored is not None
    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    kept = engine.data.parcels[order.id]
    assert kept.auto_merged is None
    assert set(kept.origins) == {"msg:a#0", PARCELAPP_PREFIX + ORDER_KEY}
    assert kept.state.tracking_number is None
    assert kept.state.eta == Eta(day(25), day(25))
    assert counts(engine) == outcome
    assert switched(engine) == 0
    assert record(engine, CORREOS)["switch"] == ""
    back = holder(engine, CORREOS)
    if outcome[2]:
        assert back is not None
        assert back.id == restored
    else:
        assert back is None


@pytest.mark.parametrize(
    ("options", "owner", "joins"),
    [
        (OPTIONS, OWNER, True),
        (OPTIONS, OTHER_OWNER, False),
        (NO_IMPORTS, OTHER_OWNER, True),
    ],
    ids=["own", "someone_else", "no_import"],
)
async def test_switch_keeps_a_private_parcel_apart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    owner: str,
    joins: bool,
) -> None:
    """A private parcel takes nobody else's delivery: suggested instead.

    Imported deliveries are the Parcel app owner's; others are nobody's.
    """
    order = add_parcel(
        engine,
        "a",
        None,
        carrier=None,
        kind=MailKind.ORDER,
        merchant="Amazon",
        orders=(ORDER,),
        owner=owner,
        private=True,
    )

    await switch(hass, freezer, parcel_app)

    own = holder(engine, CORREOS)
    assert own is not None
    assert (own.id == order.id) is joins
    if joins:
        assert "held_guesses" not in engine.data.engine
        return
    assert engine.data.parcels[order.id].auto_merged is None
    assert record(engine, CORREOS).get("switch") is None
    [suggestion] = engine.suggestions
    assert (suggestion.parcel_id, suggestion.candidates) == (order.id, (own.id,))
    assert suggestion.reason == "parcel_switch"

    assert engine.accept_suggestion(suggestion.id, own.id) == order.id
    await read(hass, freezer, parcel_app)

    joined = holder(engine, CORREOS)
    assert joined is not None
    assert joined.id == order.id
    assert joined.private
    assert set(joined.state.owners) == {OWNER, OTHER_OWNER}
    assert engine.suggestions == []
    assert "held_guesses" not in engine.data.engine


@pytest.mark.parametrize("options", [OPTIONS, NO_IMPORTS], ids=["import", "no_import"])
@pytest.mark.parametrize("case", ["one", "two", "listed"])
async def test_switch_tie_is_final(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    case: str,
) -> None:
    """A tie stays one once a tied order is delivered.

    Two orders' Amazon deliveries had the title when a carrier's delivery
    appeared: it may be either's. The other order's parcel doesn't take it
    later, as it may be the delivered order's, nor its news.
    """
    order = amazon_order(engine, "a")
    other = amazon_order(engine, "b", SECOND_ORDER)
    second = switched_amazon(SECOND_ORDER, OTHER_SHIPMENT)
    parcel_app.deliveries = [switched_amazon(), second]
    await read(hass, freezer, parcel_app)
    carriers = {
        "one": [carrier_delivery(number=OTHER_CORREOS)],
        "two": [carrier_delivery(number=OTHER_CORREOS), carrier_delivery()],
        "listed": [second, carrier_delivery()],
    }[case]
    parcel_app.deliveries = carriers
    await read(hass, freezer, parcel_app)

    engine.mark_delivered(other.id)
    delivered = carrier_delivery(
        number=OTHER_CORREOS,
        status=0,
        events=(
            ("Accepted", "2026-11-15 15:12:00"),
            ("Delivered", "2026-11-18 11:15:00"),
        ),
    )
    parcel_app.deliveries = [
        delivered if item["tracking_number"] == OTHER_CORREOS else item
        for item in carriers
    ]
    await read(hass, freezer, parcel_app, timedelta(days=2))
    await read(hass, freezer, parcel_app)

    kept = engine.data.parcels[order.id]
    assert kept.auto_merged is None
    assert kept.state.tracking_number is None
    assert not kept.state.terminal
    numbers = [item["tracking_number"] for item in carriers if item is not second]
    for number in numbers:
        assert record(engine, number)["switch"] == ""
        own = holder(engine, number)
        assert own is None or own.id != order.id
    assert switched(engine) == 0


async def test_switch_tie_counts_orders_open_when_it_appeared(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A carrier's delivery is judged as it was when it appeared.

    Also when that's on a later read, as for one imported before carrier
    switches were known: an order delivered since it appeared still ties.
    """
    order = amazon_order(engine, "a")
    other = amazon_order(engine, "b", SECOND_ORDER)
    parcel_app.deliveries = [
        switched_amazon(),
        switched_amazon(SECOND_ORDER, OTHER_SHIPMENT),
    ]
    await read(hass, freezer, parcel_app)
    parcel_app.deliveries = [carrier_delivery()]
    # As before carrier switches were known.
    with patch.object(ParcelAppSync, "_switched_target", return_value=None):
        await read(hass, freezer, parcel_app)
    assert "switch" not in record(engine, CORREOS)
    engine.mark_delivered(other.id)

    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    own = holder(engine, CORREOS)
    assert own is not None
    assert own.id != order.id
    assert engine.data.parcels[order.id].auto_merged is None
    assert record(engine, CORREOS)["switch"] == ""
    assert counts(engine) == (1, 0, 1, 0)


async def test_switch_tie_outlasts_an_order_that_left(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A tie stays one when a tied order's parcel goes.

    That order had no e-mail: its parcel was only its Amazon delivery's
    import, and went once the delivery had left the list.
    """
    order = amazon_order(engine, "a")
    parcel_app.deliveries = [
        switched_amazon(),
        switched_amazon(SECOND_ORDER, OTHER_SHIPMENT),
    ]
    await read(hass, freezer, parcel_app)
    assert holder(engine, SECOND_ORDER_KEY) is not None
    parcel_app.deliveries = [carrier_delivery()]
    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)
    assert holder(engine, SECOND_ORDER_KEY) is None

    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    own = holder(engine, CORREOS)
    assert own is not None
    assert own.id != order.id
    assert engine.data.parcels[order.id].auto_merged is None
    assert record(engine, CORREOS)["switch"] == ""
    assert counts(engine) == (1, 0, 1, 0)


@pytest.mark.parametrize("finish", ["delivered", "archived"])
async def test_switch_leaves_out_orders_finished_before(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    finish: str,
) -> None:
    """An order finished before the carrier's delivery appeared doesn't tie."""
    order = amazon_order(engine, "a")
    other = amazon_order(engine, "b", SECOND_ORDER)
    parcel_app.deliveries = [
        switched_amazon(),
        switched_amazon(SECOND_ORDER, OTHER_SHIPMENT),
    ]
    await read(hass, freezer, parcel_app)
    if finish == "delivered":
        engine.mark_delivered(other.id)
    else:
        engine.archive(other.id)

    parcel_app.deliveries = [carrier_delivery()]
    await read(hass, freezer, parcel_app)

    own = holder(engine, CORREOS)
    assert own is not None
    assert own.id == order.id
    assert record(engine, CORREOS)["switch"] == ORDER_KEY
    assert switched(engine) == 1


# -- Corrections ---------------------------------------------------------------


@pytest.mark.parametrize("options", [{**OPTIONS, CONF_PARCEL_APP_ADD: False}])
@pytest.mark.parametrize("number", [OTHER_UPS, ""])
async def test_corrected_number_closes_the_delivery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    number: str,
) -> None:
    """When the user gives a parcel another number, or none, its delivery goes.

    It doesn't come back, nor become a parcel of its own.
    """
    parcel = add_parcel(engine, "a")
    parcel_app.deliveries = [delivery()]
    await read(hass, freezer, parcel_app)
    assert holder(engine) is not None

    engine.update(parcel.id, {"tracking_number": number})
    parcel_app.deliveries = [
        delivery(status=4, events=(("Out for delivery", "2026-11-17 09:30:00"),))
    ]
    await read(hass, freezer, parcel_app)

    edited = engine.data.parcels[parcel.id]
    assert PARCELAPP_PREFIX + NUMBER not in edited.origins
    assert own_events(edited) == []
    assert record(engine)["closed"] is True
    assert record(engine)["held"] is False
    assert counts(engine) == (1, 0, 0, 1)

    await read(hass, freezer, parcel_app)

    assert holder(engine) is None
    assert list(engine.data.parcels) == [parcel.id]
    assert counts(engine) == (1, 0, 0, 1)


async def test_corrected_number_is_added(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """The number the user corrects a parcel to is added, then joins it."""
    parcel = add_parcel(engine, "a")
    parcel_app.deliveries = [delivery()]
    await read(hass, freezer, parcel_app)
    assert parcel_app.adds == []

    engine.update(parcel.id, {"tracking_number": OTHER_UPS})
    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [OTHER_UPS]

    await read(hass, freezer, parcel_app)

    joined = holder(engine, OTHER_UPS)
    assert joined is not None
    assert joined.id == parcel.id
    assert holder(engine) is None
    assert counts(engine) == (2, 1, 0, 1)
    assert parcel_app.numbers() == [OTHER_UPS]


async def test_number_corrected_before_it_is_listed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery under a number the user replaced stays out."""
    parcel = add_parcel(engine, "a")
    engine.update(parcel.id, {"tracking_number": OTHER_UPS})
    parcel_app.deliveries = [delivery()]

    await read(hass, freezer, parcel_app)

    assert holder(engine) is None
    assert list(engine.data.parcels) == [parcel.id]
    assert record(engine)["closed"] is True
    assert counts(engine) == (1, 0, 0, 1)


async def test_purged_parcel_does_not_come_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery whose parcel was archived and purged stays out."""
    parcel_app.deliveries = [
        delivery(status=0, events=(("Delivered", "2026-11-17 09:00:00"),))
    ]
    await read(hass, freezer, parcel_app)
    parcel = holder(engine)
    assert parcel is not None
    engine.archive(parcel.id)
    apply_retention(
        engine.data, dt_util.utcnow() + timedelta(days=2), archive_days=0, purge_days=1
    )
    engine.async_changed()
    assert engine.data.parcels == {}

    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    assert engine.data.parcels == {}
    assert record(engine)["closed"] is True
    assert counts(engine) == (1, 0, 0, 1)


# -- Learning carrier codes ----------------------------------------------------


async def test_learns_the_code_parcel_gives_a_carrier(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A delivery the user added teaches the code of the carrier e-mails named."""
    add_parcel(engine, "a", GLS, carrier="gls")
    parcel_app.deliveries = [delivery(GLS, code="glsx")]
    await read(hass, freezer, parcel_app)
    first = dt_to_str(dt_util.utcnow())

    assert engine.data.parcelapp["learned"] == {
        GLS: {"carrier": "gls", "code": "glsx", "time": first}
    }
    assert sync_of(engine).learned_by_carrier() == {"gls": "glsx"}

    await read(hass, freezer, parcel_app)
    assert engine.data.parcelapp["learned"][GLS]["time"] == first

    parcel_app.deliveries = [delivery(GLS, code="glsy")]
    await read(hass, freezer, parcel_app)
    assert engine.data.parcelapp["learned"] == {
        GLS: {"carrier": "gls", "code": "glsy", "time": dt_to_str(dt_util.utcnow())}
    }


def tracked_news(
    engine: ParcelsEngine,
    status: ParcelStatus,
    time: datetime,
    *,
    number: str = NUMBER,
    carrier: str = "ups",
) -> None:
    """Add 17TRACK's news about a number, as the 17TRACK sync does."""
    origin = Origin(
        id=tracked_origin(number),
        source=Source.SEVENTEENTRACK,
        time=time,
        label="17TRACK",
        carrier=carrier,
        tracking_number=number,
    )
    event = ParcelEvent(time=time, source=Source.SEVENTEENTRACK, status=status)
    apply_contribution(
        engine.data,
        Contribution(origin=origin, events=[event]),
        dt_util.utcnow(),
    )
    engine.async_changed()


@pytest.mark.parametrize(
    "case",
    [
        "own",
        "not_found",
        "no_events",
        "no_code",
        "no_email",
        "no_carrier",
        "other",
        "unknown_carrier",
        "other_family",
        "order",
    ],
)
async def test_learns_only_what_is_sure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    case: str,
) -> None:
    """Only deliveries the user added, on parcels e-mails named the carrier of.

    Deliveries Parcels added, ones Parcel hasn't found, Amazon orders and
    codes of another carrier teach nothing.
    """
    carrier = {"no_carrier": None, "other": "other", "unknown_carrier": "acme"}
    extra: dict[str, Any] = {
        "not_found": {"status": 5},
        "no_events": {"events": ()},
        "no_code": {"code": None},
        "other_family": {"code": "ups"},
        # A code naming no carrier, so the carrier check alone decides.
        **{name: {"code": "qqx"} for name in carrier},
    }.get(case, {})
    key = GLS
    if case == "order":
        key = ORDER_KEY
        parcel = add_parcel(
            engine,
            "a",
            None,
            carrier="amazon",
            kind=MailKind.ORDER,
            merchant="Amazon",
            orders=(ORDER,),
        )
        assert parcel.state.carrier == "amazon"
        parcel_app.deliveries = [amazon()]
    else:
        if case == "no_email":
            tracked_news(
                engine, ParcelStatus.IN_TRANSIT, at(16, 9), number=GLS, carrier="gls"
            )
        else:
            parcel = add_parcel(engine, "a", GLS, carrier=carrier.get(case, "gls"))
            assert parcel.state.carrier == carrier.get(case, "gls")
        if case == "own":
            engine.data.parcelapp["records"] = {
                GLS: {"own": True, "added": dt_to_str(dt_util.utcnow())}
            }
        parcel_app.deliveries = [delivery(GLS, **{"code": "glsx", **extra})]

    await read(hass, freezer, parcel_app)

    joined = holder(engine, key)
    assert joined is not None
    assert len(joined.origins) == 2
    assert engine.data.parcelapp["learned"] == {}


async def test_learned_codes_are_kept_a_year(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Codes learned over a year ago go, as do broken entries."""
    now = dt_util.utcnow()
    learned: dict[str, Any] = {
        name: {"carrier": "gls", "code": "glsx", "time": dt_to_str(now - age)}
        for name, age in (
            ("NEW", timedelta(0)),
            ("EDGE", LEARN_DAYS),
            ("OLD", LEARN_DAYS + SECOND),
        )
    }
    learned["BROKEN"] = "glsx"
    learned["UNDATED"] = {"carrier": "gls", "code": "glsx"}
    engine.data.parcelapp["learned"] = learned
    parcel_app.deliveries = []

    await read(hass, freezer, parcel_app)

    assert set(engine.data.parcelapp["learned"]) == {"NEW", "EDGE"}


async def test_learned_codes_keep_the_newest(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Only the newest learned codes are kept."""
    now = dt_util.utcnow()
    engine.data.parcelapp["learned"] = {
        f"K{index:03}": {
            "carrier": "gls",
            "code": "glsx",
            "time": dt_to_str(now - timedelta(hours=index)),
        }
        for index in range(LEARN_MAX + 1)
    }
    parcel_app.deliveries = []

    await read(hass, freezer, parcel_app)

    kept = engine.data.parcelapp["learned"]
    assert len(kept) == LEARN_MAX
    assert f"K{LEARN_MAX:03}" not in kept


async def test_learned_code_by_carrier(engine: ParcelsEngine) -> None:
    """Each carrier's most common code is used, the latest when tied."""
    sync = sync_of(engine)
    assert sync.learned_by_carrier() == {}

    def entry(carrier: Any, code: Any, hour: int) -> dict[str, Any]:
        return {"carrier": carrier, "code": code, "time": dt_to_str(at(16, hour))}

    engine.data.parcelapp["learned"] = {
        "A": entry("gls", "glsx", 1),
        "B": entry("gls", "glsx", 2),
        "C": entry("gls", "glsy", 3),
        "D": entry("dpd", "dpda", 2),
        "E": entry("dpd", "dpdb", 3),
        "F": entry("dpd", "dpda", 1) | {"time": None},
        "G": "broken",
        "H": entry(1, "upsx", 1),
        "I": entry("ups", None, 1),
    }

    assert sync.learned_by_carrier() == {"gls": "glsx", "dpd": "dpda"}

    del engine.data.parcelapp["learned"]["F"]
    assert sync.learned_by_carrier() == {"gls": "glsx", "dpd": "dpdb"}

    engine.data.parcelapp["learned"] = ["broken"]
    assert sync.learned_by_carrier() == {}


# -- Other sources and numbers -------------------------------------------------


@pytest.mark.parametrize(
    ("tracked", "code", "text", "when", "status"),
    [
        (
            ParcelStatus.OUT_FOR_DELIVERY,
            6,
            "Delivery attempted",
            "2026-11-17 08:00:00",
            ParcelStatus.OUT_FOR_DELIVERY,
        ),
        (
            ParcelStatus.OUT_FOR_DELIVERY,
            6,
            "Delivery attempted",
            "2026-11-17 09:30:00",
            ParcelStatus.ATTEMPTED,
        ),
        (
            ParcelStatus.READY_FOR_PICKUP,
            6,
            "Delivery attempted",
            "2026-11-17 08:00:00",
            ParcelStatus.READY_FOR_PICKUP,
        ),
        (
            ParcelStatus.READY_FOR_PICKUP,
            6,
            "Delivery attempted",
            "2026-11-17 09:30:00",
            ParcelStatus.ATTEMPTED,
        ),
        (
            ParcelStatus.OUT_FOR_DELIVERY,
            2,
            "In transit",
            "2026-11-17 09:30:00",
            ParcelStatus.IN_TRANSIT,
        ),
        (
            ParcelStatus.READY_FOR_PICKUP,
            2,
            "In transit",
            "2026-11-17 09:30:00",
            ParcelStatus.IN_TRANSIT,
        ),
    ],
)
async def test_newest_news_wins_against_17track(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    tracked: ParcelStatus,
    code: int,
    text: str,
    when: str,
    status: ParcelStatus,
) -> None:
    """When Parcel and 17TRACK both have news, the newest decides.

    Out for delivery and waiting at a pickup point too: the carrier can take
    the parcel back, or try again.
    """
    add_parcel(engine, "a")
    tracked_news(engine, tracked, at(17, 9))
    parcel_app.deliveries = [delivery(status=code, events=((text, when),))]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    assert tracked_origin(NUMBER) in parcel.origins
    assert parcel.state.status is status


@pytest.mark.parametrize(
    ("number", "carrier", "listed", "key", "joined"),
    [
        (PAACK, "paack", PAACK, PAACK, True),
        (PAACK, "paack", PAACK.lower(), PAACK.lower(), False),
        (NUMBER, "ups", NUMBER.lower(), NUMBER, True),
    ],
)
async def test_numbers_match_as_parcels_keeps_them(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    number: str,
    carrier: str,
    listed: str,
    key: str,
    joined: bool,
) -> None:
    """Paack's IDs match only as written; other numbers in any case."""
    parcel = add_parcel(engine, "a", number, carrier=carrier)
    parcel_app.deliveries = [delivery(listed, code=carrier)]

    await read(hass, freezer, parcel_app)

    found = holder(engine, key)
    assert found is not None
    assert (found.id == parcel.id) is joined
    assert counts(engine) == ((1, 1, 0, 0) if joined else (1, 0, 1, 0))


@pytest.mark.parametrize("known", [True, False])
async def test_two_deliveries_with_one_number_are_left(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    known: bool,
) -> None:
    """Which of two deliveries with one number to believe is unclear.

    Neither changes the parcel, but the number is still listed.
    """
    if known:
        parcel_app.deliveries = [delivery()]
        await read(hass, freezer, parcel_app)
        parcel_app.deliveries = []
        await read(hass, freezer, parcel_app)
        assert record(engine)["missing"] == 1
    parcel = holder(engine)
    events = own_events(parcel) if parcel is not None else []

    parcel_app.deliveries = [
        delivery(),
        delivery(status=4, events=(("Out for delivery", "2026-11-17 09:30:00"),)),
    ]
    await read(hass, freezer, parcel_app)
    await read(hass, freezer, parcel_app)

    assert counts(engine) == (2, 0, 0, 1)
    if not known:
        assert engine.data.parcels == {}
        assert NUMBER not in engine.data.parcelapp["records"]
        return
    kept = holder(engine)
    assert kept is not None
    assert parcel is not None
    assert kept.id == parcel.id
    assert own_events(kept) == events
    assert record(engine)["missing"] == 0

    parcel_app.deliveries = []
    await read(hass, freezer, parcel_app)
    assert holder(engine) is not None


# -- Adding --------------------------------------------------------------------

REFUSAL = {"success": False, "error_message": "Unknown tracking number"}
OTHER_GLS = "60000000001"


def two_parcels(
    engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> tuple[Parcel, Parcel]:
    """Add two undated parcels of OWNER, NUMBER's first."""
    first = add_parcel(engine, "a")
    freezer.tick(SECOND)
    return first, add_parcel(engine, "b", OTHER_UPS)


async def test_adds_a_new_parcel(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A parcel goes to the user's list under its merchant's name, never items.

    Without a push to his devices. Its delivery then joins it, under no name
    of its own, and teaches nothing about how Parcel names the carrier.
    """
    hass.config.language = "en"
    parcel = add_parcel(engine, "a", merchant=SHOP, items=("Synthetic Widget",))

    await read(hass, freezer, parcel_app)

    assert parcel_app.adds == [
        {
            "tracking_number": NUMBER,
            "carrier_code": "ups",
            "description": SHOP,
            "language": "en",
            "send_push_confirmation": False,
        }
    ]
    assert parcel_app.keys() == [KEY, KEY]
    stamp = dt_to_str(at(17, 10))
    assert record(engine) == {
        "tried": stamp,
        "added": stamp,
        "own": True,
        "sent": SHOP,
    }
    assert engine.data.parcelapp["adds"] == {
        "day": "2026-11-17",
        "sent": 1,
        "added": 1,
    }

    await read(hass, freezer, parcel_app)

    assert len(parcel_app.adds) == 1
    joined = holder(engine)
    assert joined is not None
    assert joined.id == parcel.id
    assert joined.origins[PARCELAPP_PREFIX + NUMBER].name is None
    assert engine.data.parcelapp.get("learned", {}) == {}
    assert counts(engine) == (1, 1, 0, 0)


@pytest.mark.parametrize(
    ("options", "read_status"),
    [
        ({**OPTIONS, CONF_PARCEL_APP_ADD: False}, HTTPStatus.OK),
        ({**OPTIONS, CONF_PARCEL_APP_DAILY: 0}, HTTPStatus.OK),
        (OPTIONS, HTTPStatus.INTERNAL_SERVER_ERROR),
    ],
)
async def test_adds_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    read_status: HTTPStatus,
) -> None:
    """Nothing is added with adding off, a limit of 0, or after a failed read."""
    add_parcel(engine, "a")
    parcel_app.read_status = read_status

    await read(hass, freezer, parcel_app)

    assert parcel_app.adds == []
    assert NUMBER not in engine.data.parcelapp.get("records", {})
    assert "adds" not in engine.data.parcelapp


@pytest.mark.parametrize(
    "kwargs",
    [
        {"private": True},
        {"kind": MailKind.DELIVERED},
        {"owner": OTHER_OWNER},
        {"number": None},
        {"number": GLS, "carrier": None},
        {"number": GLS, "carrier": "gls"},
        {"number": BAD_UPS},
        {"number": PAACK, "carrier": "paack"},
        {"kind": MailKind.ORDER, "age": timedelta(days=22)},
    ],
)
async def test_parcels_not_added(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    kwargs: dict[str, Any],
) -> None:
    """Private, finished, someone else's and quiet parcels aren't added.

    Nor those without a number of a known format, nor those whose carrier
    Parcel has no sure code for, or only one that needs a postcode not given.
    """
    add_parcel(engine, "a", **kwargs)
    freezer.tick(SECOND)
    add_parcel(engine, "control", OTHER_UPS)

    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [OTHER_UPS]


@pytest.mark.parametrize(
    "case", ["archived", "origin", "unusable", "twice", "paack", "order"]
)
async def test_parcels_in_the_list_not_added(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    case: str,
) -> None:
    """Parcels in the user's list aren't added, by number or Amazon order.

    In any case, even listed twice. Nor are archived parcels, those with a
    delivery already, or those whose learned code needs more than a postcode.
    """
    now = dt_util.utcnow()
    if case == "archived":
        engine.archive(add_parcel(engine, "a").id)
    elif case == "origin":
        apply_contribution(
            engine.data,
            contribution(
                PARCELAPP_PREFIX + NUMBER,
                time=now - timedelta(days=2),
                source=Source.PARCELAPP,
                carrier="ups",
                number=NUMBER,
                owner=OWNER,
            ),
            now,
        )
        engine.async_changed()
    elif case == "unusable":
        engine.data.parcelapp["learned"] = {
            OTHER_GLS: {"carrier": "gls", "code": "eshopw", "time": dt_to_str(now)}
        }
        add_parcel(engine, "a", GLS, carrier="gls")
    elif case == "twice":
        add_parcel(engine, "a")
        parcel_app.deliveries = [delivery(), delivery()]
    elif case == "paack":
        hass.config.country = "PT"
        await set_options(hass, engine, **{CONF_PARCEL_APP_POSTCODE: "1000-001"})
        add_parcel(engine, "a", PAACK, carrier="paack")
        parcel_app.deliveries = [delivery(PAACK.lower(), code="paack")]
    else:
        for name, number in (("a", NUMBER), ("b", THIRD_UPS)):
            add_parcel(engine, name, number, merchant="Amazon", orders=(ORDER,))
        parcel_app.deliveries = [amazon()]
    freezer.tick(SECOND)
    add_parcel(engine, "control", OTHER_UPS)

    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [OTHER_UPS]


@pytest.mark.parametrize(
    "kept",
    [
        {"seen": dt_to_str(at(16, 10)), "missing": 1},
        {"tried": dt_to_str(at(16, 10)), "added": dt_to_str(at(16, 10)), "own": True},
        {"tried": dt_to_str(at(16, 10)), "refused": "ups"},
        {"tried": dt_to_str(at(17, 9))},
    ],
)
async def test_numbers_known_not_added(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    kept: dict[str, Any],
) -> None:
    """A number once in the user's list, or added, isn't sent again.

    Nor one Parcel refused under the same code, nor one tried today.
    """
    engine.data.parcelapp["records"] = {NUMBER: dict(kept)}
    two_parcels(engine, freezer)

    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [OTHER_UPS]


@pytest.mark.parametrize(
    ("zone", "added"),
    [(LISBON, True), ("Europe/Madrid", False), ("Pacific/Pago_Pago", False)],
)
async def test_tried_once_a_day_in_home_assistant_s_time_zone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    zone: str,
    added: bool,
) -> None:
    """A number is tried once a day, by Home Assistant's day."""
    await hass.config.async_set_time_zone(zone)
    engine.data.parcelapp["records"] = {NUMBER: {"tried": dt_to_str(at(16, 23, 30))}}
    add_parcel(engine, "a")

    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == ([NUMBER] if added else [])


@pytest.mark.parametrize("case", ["yesterday", "refused", "learned"])
async def test_numbers_tried_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    case: str,
) -> None:
    """A number tried on another day is sent again, even refused under another code.

    A code learned from the user's own deliveries names the carrier.
    """
    yesterday = dt_to_str(at(16, 10))
    number, carrier, code = NUMBER, "ups", "ups"
    if case == "yesterday":
        engine.data.parcelapp["records"] = {NUMBER: {"tried": yesterday}}
    elif case == "refused":
        engine.data.parcelapp["records"] = {
            NUMBER: {"tried": yesterday, "refused": "upsx"}
        }
    else:
        number, carrier, code = GLS, "gls", "glsx"
        engine.data.parcelapp["learned"] = {
            OTHER_GLS: {"carrier": "gls", "code": "glsx", "time": yesterday}
        }
    add_parcel(engine, "a", number, carrier=carrier)

    await read(hass, freezer, parcel_app)

    sent = [(add["tracking_number"], add["carrier_code"]) for add in parcel_app.adds]
    assert sent == [(number, code)]
    assert "refused" not in record(engine, number)
    assert record(engine, number)["added"] == dt_to_str(at(17, 10))


@pytest.mark.parametrize("options", [{**OPTIONS, CONF_PARCEL_APP_DAILY: 2}])
async def test_adds_the_soonest_due_first(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Late parcels go first, then by date, undated ones last.

    Up to the daily limit; the rest wait for the next day.
    """
    for name, number, due in (
        ("late", NUMBER, day(15)),
        ("undated", OTHER_UPS, None),
        ("later", THIRD_UPS, day(20)),
        ("tomorrow", FOURTH_UPS, day(18)),
    ):
        add_parcel(engine, name, number, eta=None if due is None else Eta(due, due))
        freezer.tick(SECOND)

    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [NUMBER, FOURTH_UPS]

    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [NUMBER, FOURTH_UPS]

    freezer.move_to(at(18, 10))
    await read(hass, freezer, parcel_app, after=timedelta(0))

    assert parcel_app.numbers() == [NUMBER, FOURTH_UPS, THIRD_UPS, OTHER_UPS]


@pytest.mark.parametrize("options", [{**OPTIONS, CONF_PARCEL_APP_DAILY: 2}])
async def test_refused_add_counts_toward_the_limit(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """Parcel counts every request, so a refused one counts too."""
    two_parcels(engine, freezer)
    freezer.tick(SECOND)
    add_parcel(engine, "c", THIRD_UPS)

    async def refuse_first(payload: dict[str, Any]) -> None:
        parcel_app.add_answer = (
            REFUSAL if len(parcel_app.adds) == 1 else {"success": True}
        )

    parcel_app.on_add = refuse_first
    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [NUMBER, OTHER_UPS]
    assert engine.data.parcelapp["adds"] == {
        "day": "2026-11-17",
        "sent": 2,
        "added": 1,
        "error": "refused",
    }


@pytest.mark.parametrize("options", [{**OPTIONS, CONF_PARCEL_APP_DAILY: 1}])
@pytest.mark.parametrize(("zone", "added"), [(LISBON, False), ("Europe/Madrid", True)])
async def test_daily_limit_starts_again_at_local_midnight(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    zone: str,
    added: bool,
) -> None:
    """The daily limit counts Home Assistant's day."""
    await hass.config.async_set_time_zone(zone)
    two_parcels(engine, freezer)
    await read(hass, freezer, parcel_app)
    assert parcel_app.numbers() == [NUMBER]

    freezer.move_to(at(17, 22, 50))
    await read(hass, freezer, parcel_app, after=timedelta(0))
    assert parcel_app.numbers() == [NUMBER]

    freezer.move_to(at(17, 23, 10))
    await read(hass, freezer, parcel_app, after=timedelta(0))
    assert parcel_app.numbers() == ([NUMBER, OTHER_UPS] if added else [NUMBER])


@pytest.mark.parametrize(
    ("status", "message", "code"),
    [
        (HTTPStatus.TOO_MANY_REQUESTS, "Too many requests", "rate_429"),
        (HTTPStatus.OK, "Daily limit reached", "rate"),
        (HTTPStatus.OK, "Invalid API key", "key"),
        (HTTPStatus.UNAUTHORIZED, "Unauthorized", "key_401"),
    ],
)
async def test_limit_or_refused_key_stops_adding_for_the_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    caplog: pytest.LogCaptureFixture,
    status: HTTPStatus,
    message: str,
    code: str,
) -> None:
    """Parcel's limit, or a refused key, stops adding until the next day.

    With one warning, which names no number, and no repair: reading tells
    whether the key works.
    """
    caplog.set_level(logging.DEBUG)
    two_parcels(engine, freezer)
    parcel_app.add_status = status
    parcel_app.add_answer = {"success": False, "error_message": message}

    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [NUMBER]
    adds = engine.data.parcelapp["adds"]
    assert adds["stopped"] is True
    assert adds["error"] == code
    assert key_issue(hass) is None

    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [NUMBER]

    parcel_app.add_status = HTTPStatus.OK
    parcel_app.add_answer = {"success": True}
    freezer.move_to(at(18, 10))
    await read(hass, freezer, parcel_app, after=timedelta(0))

    assert parcel_app.numbers() == [NUMBER, NUMBER, OTHER_UPS]
    assert [warning.getMessage() for warning in own_warnings(caplog)] == [
        f"Adding a delivery to the Parcel app failed ({code}); trying again tomorrow"
    ]
    assert not any(
        number in entry.getMessage()
        for entry in caplog.records
        for number in (NUMBER, OTHER_UPS)
    )


async def test_new_key_adds_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A new key adds again the same day; a number tried today waits."""
    two_parcels(engine, freezer)
    parcel_app.add_status = HTTPStatus.UNAUTHORIZED
    await read(hass, freezer, parcel_app)
    assert parcel_app.numbers() == [NUMBER]

    parcel_app.add_status = HTTPStatus.OK
    await set_options(hass, engine, **{CONF_PARCEL_APP_KEY: NEW_KEY})
    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [NUMBER, OTHER_UPS]
    assert parcel_app.keys()[-1] == NEW_KEY

    freezer.move_to(at(18, 10))
    await read(hass, freezer, parcel_app, after=timedelta(0))

    assert parcel_app.numbers() == [NUMBER, OTHER_UPS, NUMBER]


@pytest.mark.parametrize(
    ("status", "answer", "error", "code"),
    [
        (
            HTTPStatus.INTERNAL_SERVER_ERROR,
            {"success": False, "error_message": "Synthetic failure."},
            None,
            "server_500",
        ),
        (HTTPStatus.OK, {"success": True}, aiohttp.ClientError(), "network"),
        (HTTPStatus.NOT_FOUND, {"detail": "Not found."}, None, "http_404"),
        (HTTPStatus.OK, {"ok": 1}, None, "invalid"),
    ],
)
async def test_other_failures_wait_for_the_next_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    caplog: pytest.LogCaptureFixture,
    status: HTTPStatus,
    answer: dict[str, Any],
    error: Exception | None,
    code: str,
) -> None:
    """Another failure ends adding until the next read, with one warning.

    The number that failed waits for the next day. Once an add goes through,
    the next failure warns again.
    """
    two_parcels(engine, freezer)
    parcel_app.add_status = status
    parcel_app.add_answer = answer
    parcel_app.add_error = error

    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [NUMBER]
    adds = engine.data.parcelapp["adds"]
    assert adds["error"] == code
    assert "stopped" not in adds

    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [NUMBER, OTHER_UPS]
    assert [warning.getMessage() for warning in own_warnings(caplog)] == [
        f"Adding a delivery to the Parcel app failed ({code}); trying again later"
    ]

    parcel_app.add_status = HTTPStatus.OK
    parcel_app.add_answer = {"success": True}
    parcel_app.add_error = None
    freezer.move_to(at(18, 10))
    await read(hass, freezer, parcel_app, after=timedelta(0))

    assert parcel_app.numbers() == [NUMBER, OTHER_UPS, NUMBER, OTHER_UPS]
    assert engine.data.parcelapp["adds"] == {
        "day": "2026-11-18",
        "sent": 2,
        "added": 2,
    }

    add_parcel(engine, "c", THIRD_UPS)
    parcel_app.add_status = status
    parcel_app.add_answer = answer
    parcel_app.add_error = error
    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers()[-1] == THIRD_UPS
    assert [warning.getMessage() for warning in own_warnings(caplog)] == 2 * [
        f"Adding a delivery to the Parcel app failed ({code}); trying again later"
    ]


async def test_refused_number_is_left(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A number Parcel refuses is left, without a warning, and the next is sent.

    It isn't sent again under the same code.
    """
    two_parcels(engine, freezer)

    async def refuse(payload: dict[str, Any]) -> None:
        parcel_app.add_answer = (
            REFUSAL if payload["tracking_number"] == NUMBER else {"success": True}
        )

    parcel_app.on_add = refuse
    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [NUMBER, OTHER_UPS]
    assert record(engine)["refused"] == "ups"
    assert "added" not in record(engine)
    assert "added" in record(engine, OTHER_UPS)
    assert own_warnings(caplog) == []

    freezer.move_to(at(18, 10))
    await read(hass, freezer, parcel_app, after=timedelta(0))

    assert parcel_app.numbers() == [NUMBER, OTHER_UPS]


@pytest.mark.parametrize(
    ("merchant", "description"),
    [
        ("A" * (MAX_DESCRIPTION - 1) + " " + "B" * 20, "A" * (MAX_DESCRIPTION - 1)),
        ("Example\n  Shop ", SHOP),
        (None, FALLBACK_DESCRIPTION),
    ],
)
async def test_description_is_the_merchant(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    merchant: str | None,
    description: str,
) -> None:
    """The merchant's name goes on one line, cut to size; without one, "Parcels".

    The delivery doesn't name the parcel then.
    """
    add_parcel(engine, "a", merchant=merchant)

    await read(hass, freezer, parcel_app)

    assert [add["description"] for add in parcel_app.adds] == [description]

    await read(hass, freezer, parcel_app)

    parcel = holder(engine)
    assert parcel is not None
    assert parcel.origins[PARCELAPP_PREFIX + NUMBER].name is None


@pytest.mark.parametrize(
    ("language", "sent"),
    [("pt-BR", "pt"), ("zh-Hant", "zh"), ("EN", "en"), ("fil", None)],
)
async def test_language_is_home_assistant_s(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    language: str,
    sent: str | None,
) -> None:
    """Parcel gets Home Assistant's language as two letters, or none."""
    hass.config.language = language
    add_parcel(engine, "a")

    await read(hass, freezer, parcel_app)

    assert [add.get("language", None) for add in parcel_app.adds] == [sent]
    assert ("language" in parcel_app.adds[0]) is (sent is not None)


@pytest.mark.parametrize("options", [{**OPTIONS, CONF_PARCEL_APP_POSTCODE: "1000001"}])
async def test_postcode_goes_only_where_parcel_needs_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """The postcode goes with Paack's IDs, in its usual form, but not with UPS.

    A Paack ID in another case is in the list already.
    """
    hass.config.country = "PT"
    add_parcel(engine, "a", PAACK, carrier="paack")
    freezer.tick(SECOND)
    add_parcel(engine, "b")
    freezer.tick(SECOND)
    add_parcel(engine, "c", PAACK.lower(), carrier="paack")

    await read(hass, freezer, parcel_app)

    assert parcel_app.adds == [
        {
            "tracking_number": PAACK,
            "carrier_code": "paack",
            "description": FALLBACK_DESCRIPTION,
            "language": "en",
            "send_push_confirmation": False,
            "postcode": "1000-001",
        },
        {
            "tracking_number": NUMBER,
            "carrier_code": "ups",
            "description": FALLBACK_DESCRIPTION,
            "language": "en",
            "send_push_confirmation": False,
        },
    ]


@pytest.mark.parametrize(
    ("country", "code"), [("PT", "ctt"), ("ES", "tourline"), (None, "tourline")]
)
async def test_carrier_code_follows_home_assistant_s_country(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    country: str | None,
    code: str,
) -> None:
    """CTT Express goes as "ctt" in Portugal, where ctt.pt tracks it.

    Elsewhere it's Parcel's "tourline", CTT Express in Spain.
    """
    hass.config.country = country
    add_parcel(engine, "a", CTT_EXPRESS, carrier="ctt_expresso")

    await read(hass, freezer, parcel_app)

    sent = [(add["tracking_number"], add["carrier_code"]) for add in parcel_app.adds]
    assert sent == [(CTT_EXPRESS, code)]


@pytest.mark.parametrize(
    "change",
    [
        {CONF_PARCEL_APP_KEY: ""},
        {CONF_PARCEL_APP_KEY: NEW_KEY},
        {CONF_PARCEL_APP_ADD: False},
    ],
)
async def test_options_changed_while_adding(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    change: dict[str, Any],
) -> None:
    """Adding stops when the key changes, or adding is turned off, meanwhile."""
    two_parcels(engine, freezer)

    async def update(payload: dict[str, Any]) -> None:
        hass.config_entries.async_update_entry(
            engine.entry, options={**engine.entry.options, **change}
        )
        await asyncio.sleep(0)

    parcel_app.on_add = update
    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [NUMBER]


@pytest.mark.parametrize(
    ("options", "mailboxes", "added"),
    [
        (OPTIONS, (), [NUMBER]),
        ({CONF_PARCEL_APP_KEY: KEY}, (), [THIRD_UPS]),
        ({CONF_PARCEL_APP_KEY: KEY}, (None,), [THIRD_UPS]),
        ({CONF_PARCEL_APP_KEY: KEY}, (None, OTHER_OWNER), []),
        (
            {**OPTIONS, CONF_PARCEL_APP_EVERYONE: True},
            (),
            sorted([NUMBER, OTHER_UPS, THIRD_UPS]),
        ),
    ],
)
async def test_adds_the_parcels_of_the_key_s_owner(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    mailboxes: tuple[str | None, ...],
    added: list[str],
) -> None:
    """Only the parcels of the person whose key it is, unless he chose everyone's.

    Without a person chosen, only parcels of no one, while no mailbox has an
    owner. Never private parcels.
    """
    for index, owner in enumerate(mailboxes):
        add_mailbox(hass, address=f"box{index}@example.com", owner=owner)
    add_parcel(engine, "mine")
    add_parcel(engine, "theirs", OTHER_UPS, owner=OTHER_OWNER)
    add_parcel(engine, "nobody", THIRD_UPS, owner=None)
    add_parcel(engine, "private", FOURTH_UPS, private=True)

    await read(hass, freezer, parcel_app)

    assert sorted(parcel_app.numbers()) == added


async def test_what_adding_did_is_saved(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
    hass_storage: dict[str, Any],
) -> None:
    """An add is saved, even when the data was written while it was sent."""
    add_parcel(engine, "a")

    async def save(payload: dict[str, Any]) -> None:
        await engine.store.async_save()

    parcel_app.on_add = save
    await read(hass, freezer, parcel_app)
    freezer.tick(timedelta(seconds=SAVE_DELAY + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    saved = hass_storage["parcels"]["data"]["parcelapp"]
    assert saved["records"][NUMBER]["added"] == dt_to_str(at(17, 10))
    assert saved["adds"]["added"] == 1


async def test_number_tried_is_kept_a_month(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """A number tried but never listed is forgotten a month after."""
    tried = dt_to_str(dt_util.utcnow() - RECORD_DAYS + timedelta(hours=1))
    engine.data.parcelapp["records"] = {NUMBER: {"tried": tried}}

    await read(hass, freezer, parcel_app)

    assert record(engine) == {"tried": tried}

    await read(hass, freezer, parcel_app, after=timedelta(hours=2))

    assert NUMBER not in engine.data.parcelapp["records"]


# -- Diagnostics ---------------------------------------------------------------

POSTCODE = "1000-001"


@pytest.mark.parametrize("options", [{**OPTIONS, CONF_PARCEL_APP_POSTCODE: POSTCODE}])
async def test_diagnostics_count_without_numbers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    parcel_app: FakeParcelApp,
) -> None:
    """The diagnostics count the deliveries, today's adds and the codes in use.

    Without a number, the key or the postcode. Yesterday's adds don't count,
    by the day in Home Assistant's time zone.
    """
    await hass.config.async_set_time_zone("Europe/Madrid")
    hass.config.country = "PT"
    sync = sync_of(engine)
    no_adds = {"sent": 0, "added": 0, "stopped": False, "error": None}
    no_amazon = dict.fromkeys(
        ("by_shipment_id", "by_order", "imported", "other", "unmatched"), 0
    )
    before = sync.diagnostics()
    assert before["deliveries"] == {
        "listed": 0,
        "matched": 0,
        "imported": 0,
        "unmatched": 0,
        "amazon": no_amazon,
        "switched": 0,
    }
    assert before["added_today"] == no_adds
    assert before["carriers"]["learned"] == {}
    assert before["carriers"]["codes"]["ctt_expresso"] == "ctt"
    assert "gls" not in before["carriers"]["codes"]

    add_parcel(engine, "a")
    add_parcel(engine, "b", GLS, carrier="gls")
    add_parcel(engine, "e", OTHER_GLS, carrier="gls")
    freezer.tick(SECOND)
    add_parcel(engine, "c", OTHER_UPS)
    freezer.tick(SECOND)
    add_parcel(engine, "d", THIRD_UPS)
    parcel_app.deliveries = [
        delivery(),
        delivery(GLS, code="glsx"),
        delivery(OTHER_GLS, code=None),
        delivery(DPD, code="dpd"),
        delivery(PAACK, code="paack"),
        delivery(CTT_EXPRESS, code="ctt"),
        delivery(CTT_EXPRESS, code="ctt"),
    ]

    async def limit_the_second(payload: dict[str, Any]) -> None:
        if len(parcel_app.adds) > 1:
            parcel_app.add_status = HTTPStatus.TOO_MANY_REQUESTS

    parcel_app.on_add = limit_the_second
    await read(hass, freezer, parcel_app)

    assert parcel_app.numbers() == [OTHER_UPS, THIRD_UPS]
    diagnostics = sync.diagnostics()
    assert diagnostics["deliveries"] == {
        "listed": 7,
        "matched": 3,
        "imported": 2,
        "unmatched": 1,
        "amazon": no_amazon,
        "switched": 0,
    }
    assert diagnostics["added_today"] == {
        "sent": 2,
        "added": 1,
        "stopped": True,
        "error": "rate_429",
    }
    assert diagnostics["carriers"]["learned"] == {"gls": "glsx", "ups": "ups"}
    assert diagnostics["carriers"]["codes"]["gls"] == "glsx"
    text = json.dumps(diagnostics)
    numbers = (NUMBER, GLS, OTHER_GLS, OTHER_UPS, THIRD_UPS, DPD, PAACK, CTT_EXPRESS)
    for secret in (*numbers, KEY):
        assert secret not in text
    assert POSTCODE not in text
    assert SHOP not in text

    # 23:50 and 00:10 in Madrid.
    freezer.move_to(at(17, 22, 50))
    assert sync.diagnostics()["added_today"]["sent"] == 2
    freezer.move_to(at(17, 23, 10))
    assert sync.diagnostics()["added_today"] == no_adds
    assert engine.data.parcelapp["adds"]["day"] == "2026-11-17"


# -- Helpers -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (7, 7),
        ("4", 4),
        (" 4 ", 4),
        (True, None),
        (None, None),
        (2.0, None),
        ("", None),
        ("x", None),
        ("-1", None),
        ("²", None),
        ("٣", None),
    ],
)
def test_status_code(value: Any, expected: int | None) -> None:
    """Status codes are whole numbers, or digits; anything else is none."""
    assert status_code(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (f" {NUMBER.lower()} ", NUMBER),
        (12345678, "12345678"),
        (PAACK, PAACK),
        (PAACK.lower(), PAACK.lower()),
        (ORDER, ORDER_KEY),
        ("12345", "12345"),
        ("1234", None),
        ("X" * 40, "X" * 40),
        ("X" * 41, None),
        ("Ünïcode123", None),
        (True, None),
        (False, None),
        (None, None),
        (12.5, None),
    ],
)
def test_delivery_key(value: Any, expected: str | None) -> None:
    """Numbers are kept as Parcels keeps them; others are left out."""
    assert delivery_key(value) == expected


@pytest.mark.parametrize(
    ("raw", "key", "code", "expected"),
    [
        (ORDER, ORDER_KEY, None, ORDER),
        (f" {ORDER} ", ORDER_KEY, "ups", ORDER),
        (ORDER_KEY, ORDER_KEY, "amzles", ORDER),
        (ORDER_KEY, ORDER_KEY, "ups", None),
        (ORDER_KEY, ORDER_KEY, None, None),
        (TBA, TBA, "amzles", None),
        (ORDER_KEY, ORDER_KEY, "swiship", None),
        (ORDER_KEY, ORDER_KEY, "amshipuk", None),
        ("TBA12345678901234", "TBA12345678901234", "amzles", None),
        ("4051234567123456", "4051234567123456", "amzles", None),
    ],
)
def test_order_number(
    raw: Any, key: str, code: str | None, expected: str | None
) -> None:
    """Amazon orders are told by their 3-7-7 form, or Amazon's code."""
    assert order_number(raw, key, code) == expected
