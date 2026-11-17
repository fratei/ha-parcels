"""Tests for the Parcels lock-screen notifier."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import count
import json
from typing import Any
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.persistent_notification.helpers import (
    _async_get_or_create_notifications,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util, slugify
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.parcels.const import (
    CONF_COLLAPSE_THRESHOLD,
    CONF_EXCLUDED_DEVICES,
    CONF_ITEM_NAMES,
    CONF_NOTIFY_PERSONS,
    CONF_TEST_DEVICE,
    CONF_TEST_MODE,
    DOMAIN,
    PERSISTENT_NOTIFICATION_ID,
    ParcelStatus,
)
from custom_components.parcels.models import (
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    Source,
)
from custom_components.parcels.notifier import (
    DEBOUNCE_COOLDOWN,
    STATE_KEY,
    DeviceKind,
    Notifier,
    classify_device,
)
from custom_components.parcels.parsers.base import Eta

S = ParcelStatus
TZ = ZoneInfo("Europe/Lisbon")
# A Thursday in summer time (UTC+1), to catch UTC/local mix-ups.
DAY = date(2026, 6, 18)
NEXT_DAY = DAY + timedelta(days=1)
PATH = "/dashboard-parcels/week"
END = "clear_notification"
COMBINED = "parcels-today-20260618"
TRUCK = "mdi:truck-fast"
OUT = "mdi:truck-delivery"
DONE = "mdi:package-check"
SHOP = "mdi:storefront"
BOX = "mdi:package-variant-closed"
DASH = "\u2013"
SEP = " \u00b7 "
CHECK = "\u2713"

ALEX = "person.alex_doe"
SAM = "person.sam_example"
JO = "person.jo_tester"
PERSONS = {ALEX: "user-alex", SAM: "user-sam", JO: "user-jo"}

APPLE = "io.robbie.HomeAssistant"
DEVICES: dict[str, dict[str, str]] = {
    "iphone": {"os_name": "iOS", "model": "iPhone17,1", "manufacturer": "Apple"},
    "ipad": {"os_name": "iPadOS", "model": "iPad16,3", "manufacturer": "Apple"},
    "android": {"os_name": "Android", "model": "Pixel 9", "manufacturer": "Google"},
    "mac": {"os_name": "macOS", "model": "MacBookPro18,3", "manufacturer": "Apple"},
}


def at(hour: int, minute: int = 0, day: date = DAY) -> datetime:
    """Return a wall-clock time in Lisbon."""
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


def on(day: date = DAY) -> Eta:
    """Return an ETA of one day, without a time window."""
    return Eta(start=day, end=day)


def window(start: int, end: int, day: date = DAY) -> Eta:
    """Return an ETA with a time window, in whole hours."""
    return Eta(start=day, end=day, window_start=time(start), window_end=time(end))


def tag_of(parcel: Parcel, gen: int = 1) -> str:
    """Return the tag of a parcel's activity."""
    suffix = f"-{gen}" if gen > 1 else ""
    return f"parcel-{parcel.id.removeprefix('p_')}{suffix}"


def activity(
    tag: str,
    title: str,
    message: str,
    critical: str,
    progress: int,
    icon: str,
    relevance: float,
    *,
    progress_max: int = 4,
    when: datetime | None = None,
    silent: bool = False,
) -> dict[str, Any]:
    """Return the payload that starts or updates a Live Activity."""
    data: dict[str, Any] = {
        "tag": tag,
        "live_update": True,
        "critical_text": critical,
        "progress": progress,
        "progress_max": progress_max,
        "notification_icon": icon,
        "url": PATH,
        "relevance_score": relevance,
    }
    if when is not None:
        data |= {"chronometer": True, "when": int(when.timestamp())}
    if silent:
        data["silent"] = True
    return {"title": title, "message": message, "data": data}


def end(tag: str) -> dict[str, Any]:
    """Return the payload that ends a Live Activity."""
    return {"message": END, "data": {"tag": tag}}


def summary(payloads: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Return the tag and the message of every payload."""
    return [(payload["data"]["tag"], payload["message"]) for payload in payloads]


def lines(*rows: str) -> str:
    """Join the lines of a Markdown message."""
    return "\n".join(rows)


def persistent(hass: HomeAssistant) -> str | None:
    """Return the message of the persistent notification, if shown."""
    notification = _async_get_or_create_notifications(hass).get(
        PERSISTENT_NOTIFICATION_ID
    )
    return notification["message"] if notification is not None else None


@dataclass
class Phone:
    """A mobile_app device and the calls its notify service received."""

    device_id: str
    calls: list[ServiceCall]

    def take(self) -> list[dict[str, Any]]:
        """Return the payloads received so far and forget them."""
        payloads = [dict(call.data) for call in self.calls]
        self.calls.clear()
        return payloads


class FakeHost:
    """The part of the engine the notifier uses."""

    def __init__(self) -> None:
        """Start with an empty store."""
        self.data = ParcelsData()
        self.saves = 0

    def visible_parcels(self) -> list[Parcel]:
        """Return the parcels that aren't archived."""
        return [p for p in self.data.parcels.values() if p.archived is None]

    def async_schedule_save(self) -> None:
        """Count the saves."""
        self.saves += 1


class Env:
    """The world around one notifier: persons, phones, parcels and time."""

    def __init__(self, hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
        """Add the persons."""
        self.hass = hass
        self.freezer = freezer
        self.host = FakeHost()
        self.entry: MockConfigEntry | None = None
        self.notifier: Notifier | None = None
        self._numbers = count(1)
        for entity_id, user_id in PERSONS.items():
            hass.states.async_set(entity_id, "home", {"user_id": user_id})

    def phone(
        self,
        name: str,
        person: str,
        kind: str = "iphone",
        *,
        service: bool = True,
        error: Exception | None = None,
    ) -> Phone:
        """Add a mobile_app device of a person, with its notify service."""
        slug = slugify(name)
        entry = MockConfigEntry(
            domain="mobile_app",
            title=name,
            data={
                "app_data": {},
                "app_id": APPLE
                if kind != "android"
                else "io.homeassistant.companion.android",
                "app_name": "Home Assistant",
                "app_version": "2026.11",
                "device_id": f"app-{slug}",
                "device_name": name,
                "os_version": "26.1",
                "supports_encryption": False,
                "user_id": PERSONS[person],
                "webhook_id": f"webhook-{slug}",
                **DEVICES[kind],
            },
        )
        entry.add_to_hass(self.hass)
        device = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("mobile_app", f"app-{slug}")},
            name=name,
        )
        calls = (
            async_mock_service(
                self.hass, "notify", f"mobile_app_{slug}", raise_exception=error
            )
            if service
            else []
        )
        return Phone(device.id, calls)

    def hub(self, **options: Any) -> MockConfigEntry:
        """Add the hub entry; Alex and Sam are notified unless told otherwise."""
        self.entry = MockConfigEntry(
            domain=DOMAIN,
            title="Parcels",
            options={CONF_NOTIFY_PERSONS: [ALEX, SAM]} | options,
        )
        self.entry.add_to_hass(self.hass)
        return self.entry

    def parcel(
        self,
        status: ParcelStatus = S.IN_TRANSIT,
        eta: Eta | None = None,
        *,
        merchant: str | None = "Amazon",
        carrier: str | None = "dpd",
        items: tuple[str, ...] = (),
        owners: tuple[str, ...] = (),
        private: bool = False,
        pickup_point: str | None = None,
        when: datetime | None = None,
    ) -> Parcel:
        """Add a parcel whose only event is its current status."""
        number = next(self._numbers)
        moment = when or dt_util.utcnow()
        origin = Origin(
            id=f"origin-{number}",
            source=Source.PARSER,
            time=moment,
            carrier=carrier,
            tracking_number=f"TEST{number:08d}" if carrier else None,
            merchant=merchant,
            items=items,
            owners=owners,
            pickup_point=pickup_point,
        )
        parcel = Parcel(
            id=f"p_{number:012x}",
            created=moment,
            updated=moment,
            origins={origin.id: origin},
            events=[
                ParcelEvent(
                    time=moment,
                    source=Source.PARSER,
                    origin=origin.id,
                    status=status,
                    eta=eta,
                    force=True,
                )
            ],
            private=private,
        )
        self.host.data.parcels[parcel.id] = parcel
        return parcel

    def change(
        self,
        parcel: Parcel,
        status: ParcelStatus | None = None,
        *,
        eta: Eta | None = None,
        when: datetime | None = None,
    ) -> None:
        """Add an event to a parcel and tell the notifier."""
        moment = when or dt_util.utcnow()
        parcel.events.append(
            ParcelEvent(
                time=moment, source=Source.PARSER, status=status, eta=eta, force=True
            )
        )
        parcel.touch(moment)
        self.changed()

    def changed(self) -> None:
        """Tell the notifier the data changed."""
        assert self.notifier is not None
        self.notifier.async_parcels_changed()

    async def start(self) -> Notifier:
        """Create and start the notifier."""
        entry = self.entry or self.hub()
        self.notifier = Notifier(self.hass, entry, self.host)
        await self.notifier.async_start()
        await self.hass.async_block_till_done()
        return self.notifier

    async def restart(self) -> Notifier:
        """Stop the notifier and start a new one from the stored state."""
        assert self.notifier is not None
        await self.notifier.async_stop()
        self.host.data.engine = json.loads(json.dumps(self.host.data.engine))
        return await self.start()

    async def goto(self, moment: datetime) -> None:
        """Move the clock and run what is due."""
        self.freezer.move_to(moment)
        async_fire_time_changed(self.hass)
        await self.hass.async_block_till_done()

    async def settle(self) -> None:
        """Let the debouncer run."""
        self.freezer.tick(timedelta(seconds=DEBOUNCE_COOLDOWN + 1))
        async_fire_time_changed(self.hass)
        await self.hass.async_block_till_done()


@pytest.fixture
async def env(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> AsyncGenerator[Env]:
    """Return a world at 07:00 on a Thursday in Lisbon."""
    await hass.config.async_set_time_zone("Europe/Lisbon")
    freezer.move_to(at(7))
    world = Env(hass, freezer)
    yield world
    if world.notifier is not None:
        await world.notifier.async_stop()


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        ({"os_name": "iOS", "model": "iPhone17,1"}, DeviceKind.IPHONE),
        ({"os_name": "iPadOS", "model": "iPad16,3"}, DeviceKind.IPAD),
        ({"os_name": "iOS", "model": "iPad13,4"}, DeviceKind.IPAD),
        ({"os_name": "Android", "model": "Pixel 9"}, DeviceKind.ANDROID),
        ({"app_id": "io.homeassistant.companion.android.minimal"}, DeviceKind.ANDROID),
        ({"os_name": "macOS", "model": "MacBookPro18,3"}, DeviceKind.OTHER),
        ({"os_name": "watchOS", "model": "Watch7,1"}, DeviceKind.OTHER),
        ({"os_name": "Linux"}, DeviceKind.OTHER),
        ({}, DeviceKind.OTHER),
    ],
)
def test_classify_device(data: dict[str, str], kind: DeviceKind) -> None:
    """Devices are told apart from their mobile_app registration."""
    assert classify_device(data) is kind


async def test_routing(env: Env, hass: HomeAssistant) -> None:
    """Only the chosen persons' devices are notified, each in its own way."""
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    mac = env.phone("Alex MacBook", ALEX, "mac")
    android = env.phone("Sam Pixel", SAM, "android")
    excluded = env.phone("Sam iPhone", SAM)
    stranger = env.phone("Jo iPhone", JO)
    everyone = async_mock_service(hass, "notify", "notify")
    env.hub(**{CONF_EXCLUDED_DEVICES: [excluded.device_id]})
    parcel = env.parcel(eta=window(13, 14))
    await env.start()
    await env.goto(at(8))
    assert iphone.take() == [
        activity(
            tag_of(parcel),
            "Amazon",
            f"Expected today 13:00{DASH}14:00{SEP}DPD",
            f"13{DASH}14h",
            2,
            TRUCK,
            0.5,
        )
    ]
    assert ipad.take() == android.take() == []

    await env.goto(at(9))
    env.change(parcel, S.OUT_FOR_DELIVERY, eta=window(13, 14))
    await env.settle()
    message = f"Out for delivery 13:00{DASH}14:00{SEP}DPD"
    assert iphone.take() == [
        activity(tag_of(parcel), "Amazon", message, f"13{DASH}14h", 3, OUT, 0.9)
    ]
    assert ipad.take() == [
        {
            "title": "Amazon",
            "message": message,
            "data": {"tag": tag_of(parcel), "url": PATH},
        }
    ]
    assert android.take() == [
        {
            "title": "Amazon",
            "message": message,
            "data": {
                "tag": tag_of(parcel),
                "clickAction": PATH,
                "notification_icon": OUT,
            },
        }
    ]

    await env.goto(at(10, 42))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    delivered = [(tag_of(parcel), f"Delivered {CHECK} 10:42{SEP}DPD")]
    assert summary(iphone.take()) == delivered
    assert summary(ipad.take()) == delivered
    assert summary(android.take()) == delivered

    env.changed()
    await env.settle()
    assert iphone.take() == ipad.take() == android.take() == []
    assert mac.calls == excluded.calls == stranger.calls == everyone == []


async def test_test_mode(env: Env, hass: HomeAssistant) -> None:
    """In test mode only the test device gets anything, whoever owns it."""
    alex = env.phone("Alex iPhone", ALEX)
    jo = env.phone("Jo iPhone", JO)
    mac = env.phone("Jo MacBook", JO, "mac")
    entry = env.hub(**{CONF_TEST_MODE: True, CONF_TEST_DEVICE: jo.device_id})
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert summary(jo.take()) == [(tag_of(parcel), f"Expected today{SEP}DPD")]

    # A Mac mirrors its iPhone, so as the test device nothing gets anything.
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_TEST_DEVICE: mac.device_id}
    )
    env.changed()
    await env.settle()
    assert jo.take() == [end(tag_of(parcel))]
    assert alex.calls == mac.calls == []


async def test_start_time_and_joiners(env: Env, hass: HomeAssistant) -> None:
    """Today's parcels start at 08:00; later only deliveries and pickups join."""
    phone = env.phone("Alex iPhone", ALEX)
    today = env.parcel(eta=on(), items=("Blue scarf",))
    tomorrow = env.parcel(eta=on(NEXT_DAY), merchant="Zalando", carrier="ctt")
    await env.start()
    assert phone.take() == []
    assert persistent(hass) is None

    await env.goto(at(8))
    assert phone.take() == [
        activity(
            tag_of(today), "Amazon", f"Expected today{SEP}DPD", "Today", 2, TRUCK, 0.5
        )
    ]

    await env.goto(at(11))
    env.change(tomorrow, S.OUT_FOR_DELIVERY)
    await env.settle()
    assert phone.take() == [
        activity(
            tag_of(tomorrow),
            "Zalando",
            f"Out for delivery{SEP}CTT",
            "Today",
            3,
            OUT,
            0.9,
        )
    ]

    # Expected today but found late: listed, but it doesn't start an activity.
    await env.goto(at(12))
    env.parcel(eta=on(), merchant="Late Shop", carrier="gls")
    env.changed()
    await env.settle()
    assert phone.take() == []
    assert f"- Late Shop{SEP}GLS{SEP}Expected today" in (persistent(hass) or "")


async def test_cutoff(env: Env) -> None:
    """The cut-off ends every activity, and nothing starts after it."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    late = env.parcel(eta=on(NEXT_DAY), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert summary(phone.take()) == [(tag_of(parcel), f"Expected today{SEP}DPD")]

    await env.goto(at(22))
    assert phone.take() == [end(tag_of(parcel))]

    await env.goto(at(22, 30))
    env.change(late, S.OUT_FOR_DELIVERY)
    await env.settle()
    assert phone.take() == []

    # Nor after a restart of Home Assistant.
    await env.restart()
    assert phone.take() == []


async def test_collapse_is_sticky(env: Env) -> None:
    """More than three parcels become one activity for the rest of the day."""
    phone = env.phone("Alex iPhone", ALEX)
    first = env.parcel(eta=window(15, 16))
    second = env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    third = env.parcel(eta=on(), merchant="Decathlon", carrier="correos")
    fourth = env.parcel(eta=on(NEXT_DAY), merchant="IKEA", carrier="gls")
    await env.start()
    await env.goto(at(8))
    assert [payload["data"]["tag"] for payload in phone.take()] == [
        tag_of(first),
        tag_of(second),
        tag_of(third),
    ]

    await env.goto(at(9))
    env.change(fourth, S.OUT_FOR_DELIVERY, eta=window(13, 14))
    await env.settle()
    assert phone.take() == [
        end(tag_of(first)),
        end(tag_of(second)),
        end(tag_of(third)),
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 4 delivered{SEP}next: GLS 13{DASH}14h",
            "0/4",
            0,
            OUT,
            0.9,
        ),
    ]

    await env.goto(at(10))
    env.change(fourth, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"1 of 4 delivered{SEP}next: DPD 15{DASH}16h",
            "1/4",
            1,
            BOX,
            0.5,
        )
    ]

    # Back to three parcels, but it stays combined.
    await env.goto(at(10, 30))
    env.change(second, S.CANCELLED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"1 of 3 delivered{SEP}next: DPD 15{DASH}16h",
            "1/3",
            1,
            BOX,
            0.5,
            progress_max=3,
        )
    ]


async def test_collapsed_from_the_start(env: Env) -> None:
    """Over the threshold at the start time, only the combined activity starts."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    env.parcel(eta=window(13, 14))
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 2 delivered{SEP}next: DPD 13{DASH}14h",
            "0/2",
            0,
            BOX,
            0.5,
            progress_max=2,
        )
    ]


async def test_delivered(env: Env) -> None:
    """A window shows a timer; a delivered parcel ends 30 minutes later."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=window(10, 11))
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1

    await env.goto(at(9, 30))
    env.change(parcel, S.OUT_FOR_DELIVERY, eta=window(10, 11))
    await env.settle()
    out = f"Out for delivery 10:00{DASH}11:00{SEP}DPD"
    assert phone.take() == [
        activity(tag_of(parcel), "Amazon", out, f"10{DASH}11h", 3, OUT, 0.9)
    ]

    # The window starts: a quiet update adds the timer.
    await env.goto(at(10))
    assert phone.take() == [
        activity(
            tag_of(parcel),
            "Amazon",
            out,
            f"10{DASH}11h",
            3,
            OUT,
            1.0,
            when=at(11),
            silent=True,
        )
    ]

    await env.goto(at(10, 42))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            tag_of(parcel),
            "Amazon",
            f"Delivered {CHECK} 10:42{SEP}DPD",
            f"{CHECK} 10:42",
            4,
            DONE,
            0.2,
        )
    ]

    # The end of the window changes nothing any more.
    await env.goto(at(11, 5))
    assert phone.take() == []

    await env.goto(at(11, 13))
    assert phone.take() == [end(tag_of(parcel))]

    env.changed()
    await env.settle()
    assert phone.take() == []


async def test_restart_before_apple_ends_it(env: Env) -> None:
    """After 7.5 hours an undelivered parcel's activity restarts as -2."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert summary(phone.take()) == [(tag_of(parcel), f"Expected today{SEP}DPD")]

    await env.goto(at(15, 30))
    assert phone.take() == [
        end(tag_of(parcel)),
        activity(
            tag_of(parcel, 2),
            "Amazon",
            f"Expected today{SEP}DPD",
            "Today",
            2,
            TRUCK,
            0.5,
        ),
    ]

    # It wouldn't reach eight hours before the cut-off, which ends it.
    await env.goto(at(22))
    assert phone.take() == [end(tag_of(parcel, 2))]


async def test_home_assistant_restart(env: Env) -> None:
    """Stopping ends nothing, and starting again duplicates nothing."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    assert env.host.saves

    await env.goto(at(9))
    await env.restart()
    assert phone.take() == []

    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    assert summary(phone.take()) == [(tag_of(parcel), f"Out for delivery{SEP}DPD")]

    # The 7.5-hour restart still counts from the first start.
    await env.goto(at(15, 30))
    assert summary(phone.take()) == [
        (tag_of(parcel), END),
        (tag_of(parcel, 2), f"Out for delivery{SEP}DPD"),
    ]


async def test_updates_are_debounced(env: Env) -> None:
    """A burst of changes is one update, and no change sends nothing."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1

    await env.goto(at(9))
    env.change(parcel, S.OUT_FOR_DELIVERY, eta=window(13, 14))
    env.change(parcel, eta=window(14, 15), when=at(9) + timedelta(seconds=1))
    await env.hass.async_block_till_done()
    assert phone.calls == []
    await env.settle()
    assert summary(phone.take()) == [
        (tag_of(parcel), f"Out for delivery 14:00{DASH}15:00{SEP}DPD")
    ]

    env.change(parcel, S.OUT_FOR_DELIVERY, eta=window(14, 15))
    await env.settle()
    env.changed()
    await env.settle()
    assert phone.take() == []


async def test_moved_to_a_later_day(env: Env) -> None:
    """A parcel moved to tomorrow says so quietly, then ends 30 minutes later."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1

    await env.goto(at(9))
    env.change(parcel, eta=on(NEXT_DAY))
    await env.settle()
    assert phone.take() == [
        activity(
            tag_of(parcel),
            "Amazon",
            f"Expected tomorrow{SEP}DPD",
            "Tomorrow",
            2,
            TRUCK,
            0.1,
            silent=True,
        )
    ]

    await env.goto(at(9, 31))
    assert phone.take() == [end(tag_of(parcel))]


async def test_private_parcels_and_item_names(env: Env, hass: HomeAssistant) -> None:
    """Private parcels reach only their owners' devices, never with item names."""
    alex = env.phone("Alex iPhone", ALEX)
    sam = env.phone("Sam iPhone", SAM)
    env.hub(**{CONF_ITEM_NAMES: True})
    shared = env.parcel(
        eta=on(),
        merchant="Zalando",
        carrier="ctt",
        items=("Blue scarf", "Wool hat", "Red socks"),
    )
    gift = env.parcel(eta=on(), items=("Board game",), owners=(ALEX,), private=True)
    env.parcel(eta=on(), merchant="Etsy", carrier="gls", private=True)
    await env.start()
    await env.goto(at(8))
    shown = (tag_of(shared), f"Expected today{SEP}CTT{SEP}Blue scarf +2 more")
    assert summary(alex.take()) == [shown, (tag_of(gift), f"Expected today{SEP}DPD")]
    assert summary(sam.take()) == [shown]
    assert persistent(hass) == lines(
        "**3 parcels today**",
        "",
        f"- Zalando{SEP}CTT{SEP}Expected today",
        "- +2 private parcels",
        "",
        f"[Open Parcels]({PATH})",
    )


async def test_switches(env: Env, hass: HomeAssistant) -> None:
    """The switches stop and resume the phones and the persistent notification."""
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    parcel = env.parcel(eta=on())
    notifier = await env.start()
    assert notifier.live_activities_enabled
    assert notifier.daily_notification_enabled
    await env.goto(at(8))
    assert len(iphone.take()) == 1

    await notifier.async_set_live_activities(False)
    assert iphone.take() == [end(tag_of(parcel))]
    assert env.host.data.engine[STATE_KEY]["live_activities"] is False

    await env.goto(at(9))
    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    notifier = await env.restart()
    assert not notifier.live_activities_enabled
    assert iphone.take() == ipad.take() == []

    await notifier.async_set_live_activities(True)
    message = f"Out for delivery{SEP}DPD"
    assert iphone.take() == [
        activity(tag_of(parcel, 2), "Amazon", message, "Today", 3, OUT, 0.9)
    ]
    assert ipad.take() == [
        {
            "title": "Amazon",
            "message": message,
            "data": {"tag": tag_of(parcel), "url": PATH},
        }
    ]

    await notifier.async_set_daily_notification(False)
    assert persistent(hass) is None
    assert env.host.data.engine[STATE_KEY]["daily_notification"] is False
    env.changed()
    await env.settle()
    assert persistent(hass) is None

    await notifier.async_set_daily_notification(True)
    assert f"- Amazon{SEP}DPD{SEP}Out for delivery" in (persistent(hass) or "")


async def test_persistent_notification(env: Env, hass: HomeAssistant) -> None:
    """The day's list appears at the start time and is replaced the next morning."""
    env.hub()
    out = env.parcel(eta=window(13, 14))
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt", items=("Blue scarf",))
    shop = env.parcel(eta=on(), merchant="Shop store", carrier="gls")
    env.parcel(eta=on(NEXT_DAY), merchant="IKEA", carrier="correos")
    env.parcel(eta=on(), merchant="Etsy", carrier="ctt", private=True)
    await env.start()
    assert persistent(hass) is None

    await env.goto(at(8))
    assert persistent(hass) == lines(
        "**4 parcels today**",
        "",
        f"- Amazon{SEP}DPD{SEP}Expected today 13:00{DASH}14:00",
        f"- Shop store{SEP}GLS{SEP}Expected today",
        f"- Zalando{SEP}CTT{SEP}Expected today",
        "- +1 private parcel",
        "",
        f"[Open Parcels]({PATH})",
    )

    await env.goto(at(9))
    env.change(out, S.OUT_FOR_DELIVERY, eta=window(13, 14))
    await env.goto(at(10, 42))
    env.change(shop, S.DELIVERED)
    await env.settle()
    today = [
        f"- Amazon{SEP}DPD{SEP}Out for delivery 13:00{DASH}14:00",
        f"- Zalando{SEP}CTT{SEP}Expected today",
        f"- Shop store{SEP}GLS{SEP}Delivered 10:42 {CHECK}",
        "- +1 private parcel",
        "",
        f"[Open Parcels]({PATH})",
    ]
    assert persistent(hass) == lines("**4 parcels today**", "", *today)

    # Overnight it is still the list of the day before.
    await env.goto(at(0, 30, NEXT_DAY))
    today[1] = f"- Zalando{SEP}CTT{SEP}Expected yesterday"
    assert persistent(hass) == lines("**4 parcels yesterday**", "", *today)

    await env.goto(at(8, day=NEXT_DAY))
    assert persistent(hass) == lines(
        "**1 parcel today**",
        "",
        f"- IKEA{SEP}Correos{SEP}Expected today",
        "",
        f"[Open Parcels]({PATH})",
    )

    # Nothing is expected on the third day, and old days are forgotten.
    third_day = DAY + timedelta(days=2)
    await env.goto(at(8, day=third_day))
    assert persistent(hass) is None
    assert sorted(env.host.data.engine[STATE_KEY]["days"]) == [
        NEXT_DAY.isoformat(),
        third_day.isoformat(),
    ]


async def test_pickup(env: Env, hass: HomeAssistant) -> None:
    """Ready after the cut-off: on the lock screen the next day, then only listed."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(
        eta=on(), merchant="Decathlon", carrier="ctt", pickup_point="Locker 12"
    )
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1

    await env.goto(at(22, 30))
    assert phone.take() == [end(tag_of(parcel))]
    env.change(parcel, S.READY_FOR_PICKUP)
    await env.settle()
    assert phone.take() == []

    await env.goto(at(8, day=NEXT_DAY))
    assert phone.take() == [
        activity(
            tag_of(parcel),
            "Decathlon",
            f"Ready for pickup{SEP}Locker 12{SEP}CTT",
            "Pickup",
            3,
            SHOP,
            0.7,
        )
    ]

    await env.goto(at(22, day=NEXT_DAY))
    assert phone.take() == [end(tag_of(parcel))]

    await env.goto(at(8, day=DAY + timedelta(days=2)))
    assert phone.take() == []
    assert persistent(hass) == lines(
        "**1 parcel today**",
        "",
        f"- Decathlon{SEP}CTT{SEP}Ready for pickup at Locker 12",
        "",
        f"[Open Parcels]({PATH})",
    )


async def test_test_live_activity(env: Env, hass: HomeAssistant) -> None:
    """The demo activity goes to one iPhone and ends a minute later."""
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    offline = env.phone("Sam iPhone", SAM, service=False)
    entry = env.hub()
    notifier = await env.start()
    await notifier.async_test_live_activity()
    assert iphone.take() == [
        activity(
            "parcels-test",
            "Parcels",
            f"Test{SEP}Out for delivery 13:00{DASH}14:00",
            "Test",
            3,
            OUT,
            0.5,
            when=at(7, 1),
        )
    ]
    await env.goto(at(7, 1))
    assert iphone.take() == [end("parcels-test")]

    with pytest.raises(ServiceValidationError) as err:
        await notifier.async_test_live_activity(ipad.device_id)
    assert err.value.translation_key == "test_not_iphone"
    with pytest.raises(HomeAssistantError) as err:
        await notifier.async_test_live_activity(offline.device_id)
    assert not isinstance(err.value, ServiceValidationError)
    assert err.value.translation_key == "test_app_unregistered"
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_NOTIFY_PERSONS: [JO]}
    )
    with pytest.raises(ServiceValidationError) as err:
        await notifier.async_test_live_activity()
    assert err.value.translation_key == "test_no_iphone"
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            CONF_TEST_MODE: True,
            CONF_TEST_DEVICE: ipad.device_id,
        },
    )
    with pytest.raises(ServiceValidationError) as err:
        await notifier.async_test_live_activity()
    assert err.value.translation_key == "test_mode_not_iphone"
    assert iphone.calls == ipad.calls == []


async def test_diagnostics(env: Env) -> None:
    """Diagnostics hold counts only: no names and no IDs."""
    iphone = env.phone("Alex iPhone", ALEX)
    android = env.phone("Sam Pixel", SAM, "android")
    parcel = env.parcel(eta=on())
    notifier = await env.start()
    await env.goto(at(8))
    diagnostics = notifier.diagnostics()
    assert diagnostics["recipients"] == {"iphone": 1, "android": 1}
    assert diagnostics["today"] == {
        "parcels": 1,
        "morning_done": True,
        "combined_devices": 0,
        "activities": 1,
        "activity_starts": 1,
        "running": 1,
        "notifications_sent": 0,
    }
    dumped = json.dumps(diagnostics).casefold()
    for secret in (iphone.device_id, android.device_id, parcel.id, "Amazon", "Alex"):
        assert secret.casefold() not in dumped


async def test_failures_are_retried_without_content_in_the_log(
    env: Env, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed call logs no content and is retried five minutes later."""
    phone = env.phone("Alex iPhone", ALEX, error=HomeAssistantError("Amazon parcel"))
    env.hub(**{CONF_ITEM_NAMES: True})
    parcel = env.parcel(eta=on(), items=("Blue scarf",))
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    logged = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("custom_components.parcels")
    )
    assert "Notifying a device (iphone) failed: HomeAssistantError" in logged
    assert "Amazon" not in logged
    assert "Blue scarf" not in logged

    calls = async_mock_service(hass, "notify", "mobile_app_alex_iphone")
    await env.goto(at(8, 5))
    assert summary([dict(call.data) for call in calls]) == [
        (tag_of(parcel), f"Expected today{SEP}DPD{SEP}Blue scarf")
    ]


async def test_damaged_state_is_dropped(env: Env) -> None:
    """A damaged stored state is dropped instead of breaking the notifier."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    env.host.data.engine[STATE_KEY] = {
        "live_activities": "yes",
        "days": {
            "someday": {},
            DAY.isoformat(): {"board": "p_1", "activities": {"x": {"tag": 1}}},
        },
        "test": {"device": 5},
    }
    notifier = await env.start()
    assert notifier.live_activities_enabled
    assert "test" not in env.host.data.engine[STATE_KEY]
    await env.goto(at(8))
    assert summary(phone.take()) == [(tag_of(parcel), f"Expected today{SEP}DPD")]
