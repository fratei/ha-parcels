"""Tests for the Parcels lock-screen notifier."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from itertools import count
import json
import logging
import re
from typing import Any
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.persistent_notification.helpers import (
    _async_get_or_create_notifications,
)
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, MATCH_ALL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util, slugify
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.parcels.const import (
    CONF_COLLAPSE_THRESHOLD,
    CONF_DASHBOARD_PATH,
    CONF_EXCLUDED_DEVICES,
    CONF_ITEM_NAMES,
    CONF_NOTIFY_PERSONS,
    CONF_PIN_ON_LOCK_SCREEN,
    CONF_TEST_DEVICE,
    CONF_TEST_MODE,
    DOMAIN,
    PERSISTENT_NOTIFICATION_ID,
    LeftAt,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.customer_returns import mark_return_picked_up
from custom_components.parcels.dedup import (
    mark_delivered,
    repair_store,
    undo_delivery,
)
from custom_components.parcels.models import (
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    PickupRule,
    ReturnEntry,
    ReturnOrigin,
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

from .common import (
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    patch_mail_clients,
)

S = ParcelStatus
TZ = ZoneInfo("Europe/Lisbon")
# A Thursday in summer time (UTC+1), to catch UTC/local mix-ups.
DAY = date(2026, 6, 18)
NEXT_DAY = DAY + timedelta(days=1)
PATH = "/dashboard-parcels/week"
END = "clear_notification"
COMBINED = "parcels-today-20260618"
CART = "mdi:cart-outline"
TRUCK = "mdi:truck-fast"
OUT = "mdi:truck-delivery"
DONE = "mdi:package-check"
SHOP = "mdi:storefront"
ALERT = "mdi:alert-circle-outline"
BOX = "mdi:package-variant-closed"
RETURN = "mdi:package-up"
BLUE = "#039BE5"
ORANGE = "#FFA600"
GREEN = "#43A047"
PURPLE = "#926BC7"
RED = "#DB4437"
PINK = "#E91E63"
# The colour each icon goes with, so expected payloads needn't repeat it.
COLOURS = {
    CART: BLUE,
    TRUCK: BLUE,
    BOX: BLUE,
    OUT: ORANGE,
    DONE: GREEN,
    SHOP: PURPLE,
    ALERT: RED,
    RETURN: PINK,
}
DASH = "\u2013"
SEP = " \u00b7 "
CHECK = "\u2713"
ELLIPSIS = "\u2026"

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


def news_tag(parcel: Parcel) -> str:
    """Return the tag of an iPhone's notification of a parcel's news."""
    return f"{tag_of(parcel)}-news"


def link_of(parcel: Parcel) -> str:
    """Return the dashboard path that opens a parcel's details."""
    return f"{PATH}?parcel={parcel.id}"


def ret_tag(entry: ReturnEntry, gen: int = 1) -> str:
    """Return the tag of a return pickup's activity."""
    suffix = f"-{gen}" if gen > 1 else ""
    return f"return-{entry.id.removeprefix('ret_')}{suffix}"


def _link_of_tag(tag: str) -> str:
    """Return what tapping an activity with a tag opens."""
    if match := re.fullmatch(r"parcel-([0-9a-f]+)(?:-\d+)?", tag):
        return f"{PATH}?parcel=p_{match.group(1)}"
    if match := re.fullmatch(r"return-([0-9a-f]+)(?:-\d+)?", tag):
        return f"{PATH}?return=ret_{match.group(1)}"
    return PATH


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
        "notification_icon_color": COLOURS[icon],
        "progress_bar_color": COLOURS[icon],
        "url": _link_of_tag(tag),
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
    """A mobile_app device and the calls its notify service received.

    Pushes that bypass the service, as those with a PIN do, have a target.
    """

    device_id: str
    calls: list[ServiceCall]
    service: str = ""
    webhook_id: str = ""
    error: Exception | None = None

    def take(self) -> list[dict[str, Any]]:
        """Return the payloads received so far and forget them."""
        payloads = [dict(call.data) for call in self.calls]
        self.calls.clear()
        return payloads


class FakePush:
    """mobile_app's notify service, as Parcels calls it directly."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Start without devices."""
        self.hass = hass
        self.phones: dict[str, Phone] = {}

    @property
    def registered_targets(self) -> dict[str, str]:
        """Return the webhook ID behind each notify service, like mobile_app."""
        return {phone.service: webhook for webhook, phone in self.phones.items()}

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Record a push to one device, or fail as its service would."""
        target = kwargs["target"]
        assert isinstance(target, list)
        assert len(target) == 1
        phone = self.phones[target[0]]
        if phone.error is not None:
            raise phone.error
        data = {"message": message, **kwargs}
        phone.calls.append(ServiceCall(self.hass, "notify", phone.service, data))


def pinned(payload: dict[str, Any], phone: Phone) -> dict[str, Any]:
    """Return a payload as pushed to a phone without its notify service."""
    return payload | {"target": [phone.webhook_id]}


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
        self.entries: dict[str, MockConfigEntry] = {}
        self.tokens: dict[str, dict[str, dict[str, Any]]] = {}
        # Whether iPhones report the token of each activity they start at once.
        self.auto_token = True
        self.push = FakePush(hass)
        hass.data["mobile_app"] = {
            "config_entries": self.entries,
            "notify": self.push,
            "live_activity_tokens": self.tokens,
            "push_channel": {},
        }

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
        self.entries[f"webhook-{slug}"] = entry
        device = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("mobile_app", f"app-{slug}")},
            name=name,
        )
        calls: list[ServiceCall] = []
        phone = Phone(device.id, calls, f"mobile_app_{slug}", f"webhook-{slug}", error)
        if service:

            @callback
            def handle(call: ServiceCall) -> None:
                calls.append(call)
                if error is not None:
                    raise error
                if kind == "iphone":
                    self._activity_reported(phone, call)

            self.hass.services.async_register("notify", phone.service, handle)
            self.push.phones[phone.webhook_id] = phone
        return phone

    def _activity_reported(self, phone: Phone, call: ServiceCall) -> None:
        """Do what the iPhone app does: report a started activity's token.

        mobile_app starts an activity when it holds no valid token for the tag,
        and forgets the token when it ends one.
        """
        data = call.data.get("data") or {}
        tag = data.get("tag")
        if not isinstance(tag, str):
            return
        if call.data.get("message") == END:
            self.untoken(phone, tag)
            return
        if not data.get("live_update") or not self.auto_token:
            return
        stored = self.tokens.get(phone.webhook_id, {}).get(tag)
        if stored is None or stored["expires_at"] <= dt_util.utcnow().timestamp():
            self.token(phone, tag)

    def token(self, phone: Phone, tag: str, expires: datetime | None = None) -> None:
        """Store the push token an iPhone sent for one of its activities."""
        moment = expires or dt_util.utcnow() + timedelta(hours=12)
        self.tokens.setdefault(phone.webhook_id, {})[tag] = {
            "token": "made-up-token",
            "expires_at": moment.timestamp(),
        }

    def untoken(self, phone: Phone, tag: str) -> None:
        """Forget an activity's push token, as mobile_app does when it ends."""
        self.tokens.get(phone.webhook_id, {}).pop(tag, None)

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
        pickup_code: str | None = None,
        when: datetime | None = None,
        name: str | None = None,
        order_numbers: tuple[str, ...] = (),
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
            order_numbers=order_numbers,
            items=items,
            owners=owners,
            pickup_point=pickup_point,
            pickup_code=pickup_code,
            name=name,
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
        undated: bool = False,
        timeless: bool = False,
        sent: datetime | None = None,
        pickup_point: str | None = None,
        pickup_code: str | None = None,
        collect_by: date | None = None,
        next_attempt: date | None = None,
        left_at: LeftAt | None = None,
        label: str = "",
    ) -> None:
        """Add an event to a parcel and tell the notifier.

        With ``sent``, the event comes from an e-mail sent then, which may
        name a pickup point and a code; an event at the time its e-mail was
        sent has only that time. ``label`` is the e-mail's sender domain.
        ``timeless`` gives the day without the time. As news does, it
        replaces a delivery Parcels only inferred.
        """
        moment = when or dt_util.utcnow()
        parcel.events = [event for event in parcel.events if not event.inferred]
        origin: str | None = None
        if sent is not None:
            origin = f"origin-{next(self._numbers)}"
            parcel.origins[origin] = Origin(
                id=origin,
                source=Source.PARSER,
                time=sent,
                label=label,
                pickup_point=pickup_point,
                pickup_code=pickup_code,
            )
        assert pickup_point is None or origin is not None
        assert pickup_code is None or origin is not None
        parcel.events.append(
            ParcelEvent(
                time=moment,
                source=Source.PARSER,
                origin=origin,
                status=status,
                eta=eta,
                force=True,
                undated=undated or timeless,
                timeless=timeless,
                by=moment if undated or timeless else None,
                collect_by=collect_by,
                next_attempt=next_attempt,
                left_at=left_at,
            )
        )
        parcel.touch(moment)
        self.changed()

    def infer(self, parcel: Parcel) -> None:
        """Deliver a parcel as another package of its shipment was, and tell."""
        moment = dt_util.utcnow()
        parcel.events.append(
            ParcelEvent(
                time=moment,
                source=Source.PARSER,
                status=S.DELIVERED,
                kind=MailKind.DELIVERED,
                label="shipment",
                inferred=True,
            )
        )
        parcel.touch(moment)
        self.changed()

    def uninfer(self, parcel: Parcel) -> None:
        """Take back an inferred delivery, as the user can, and tell."""
        parcel.events = [event for event in parcel.events if not event.inferred]
        parcel.delivery_rejected = True
        parcel.touch(dt_util.utcnow())
        self.changed()

    def ret(
        self,
        merchant: str | None = "Zalando",
        carrier: str | None = "ctt",
        pickup: date | None = DAY,
        *,
        items: tuple[str, ...] = (),
        owners: tuple[str, ...] = (),
        private: bool = False,
        order_numbers: tuple[str, ...] = (),
        received: bool = False,
        rule: PickupRule = PickupRule.EMAIL,
        sent: datetime | None = None,
    ) -> ReturnEntry:
        """Add a return whose one e-mail gives its pickup day.

        With ``sent``, the e-mail is older than the return.
        """
        number = next(self._numbers)
        moment = dt_util.utcnow()
        origin = ReturnOrigin(
            message=f"m-{number}",
            time=sent or moment,
            merchant=merchant,
            order_numbers=order_numbers,
            items=items,
            carrier=carrier,
            pickup=pickup,
            pickup_rule=rule if pickup is not None else None,
            received=received,
            owners=owners,
        )
        entry = ReturnEntry(
            id=f"ret_{number:012x}",
            created=moment,
            updated=moment,
            origins={origin.message: origin},
            private=private,
        )
        self.host.data.returns[entry.id] = entry
        return entry

    def picked_up(self, entry: ReturnEntry, picked_up: bool = True) -> None:
        """Mark a return picked up, or take that back, and tell the notifier."""
        mark_return_picked_up(self.host.data, entry.id, picked_up, dt_util.utcnow())
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
            "data": {"tag": tag_of(parcel), "url": link_of(parcel)},
        }
    ]
    assert android.take() == [
        {
            "title": "Amazon",
            "message": message,
            "data": {
                "tag": tag_of(parcel),
                "clickAction": link_of(parcel),
                "notification_icon": OUT,
                "color": ORANGE,
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


async def test_phone_registered_again(env: Env, hass: HomeAssistant) -> None:
    """A phone registered again is notified, though its old device has the same ID."""
    old = env.phone("Alex iPhone", ALEX, service=False)
    dr.async_get(hass).async_update_device(
        old.device_id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    phone = env.phone("Alex iPhone", ALEX)
    assert phone.device_id != old.device_id
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert summary(phone.take()) == [(tag_of(parcel), f"Expected today{SEP}DPD")]


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
    """Today's parcels start at 08:00; one found later joins until the cut-off."""
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

    # Expected today but found late: it joins too.
    await env.goto(at(12))
    late = env.parcel(eta=on(), merchant="Late Shop", carrier="gls")
    env.changed()
    await env.settle()
    assert phone.take() == [
        activity(
            tag_of(late), "Late Shop", f"Expected today{SEP}GLS", "Today", 2, TRUCK, 0.5
        )
    ]
    assert f"- Late Shop{SEP}GLS{SEP}Expected today" in (persistent(hass) or "")


async def test_due_today_after_the_start_joins(env: Env) -> None:
    """A parcel whose date becomes today after the start time joins, once a day.

    Moved to tomorrow and back, it doesn't start a second activity.
    """
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on(NEXT_DAY), merchant="Zalando", carrier="ctt")
    tag = tag_of(parcel)
    notifier = await env.start()
    await env.goto(at(8))
    assert phone.take() == []
    assert notifier.diagnostics()["today"]["parcels"] == 0

    await env.goto(at(8, 24))
    env.change(parcel, eta=on())
    await env.settle()
    assert phone.take() == [
        activity(tag, "Zalando", f"Expected today{SEP}CTT", "Today", 2, TRUCK, 0.5)
    ]
    assert notifier.diagnostics()["today"]["parcels"] == 1

    await env.goto(at(9))
    env.change(parcel, eta=on(NEXT_DAY))
    await env.settle()
    assert phone.take() == [
        activity(
            tag,
            "Zalando",
            f"Expected tomorrow{SEP}CTT",
            "Tomorrow",
            2,
            TRUCK,
            0.1,
            silent=True,
        )
    ]
    await env.goto(at(9, 31))
    assert phone.take() == [end(tag)]

    await env.goto(at(10))
    env.change(parcel, eta=on())
    await env.settle()
    assert phone.take() == []
    today = notifier.diagnostics()["today"]
    assert (today["parcels"], today["activity_starts"]) == (1, 1)


async def test_late_joiners_follow_the_morning_rules(env: Env) -> None:
    """After the start time, finished parcels and old pickups don't join either."""
    phone = env.phone("Alex iPhone", ALEX)
    waiting = env.parcel(
        S.READY_FOR_PICKUP,
        eta=on(NEXT_DAY),
        merchant="Decathlon",
        carrier="ctt",
        when=at(9, day=DAY - timedelta(days=1)),
    )
    notifier = await env.start()
    await env.goto(at(8))
    assert phone.take() == []

    await env.goto(at(10))
    env.parcel(S.DELIVERED, on(), carrier="ctt")
    env.parcel(S.CANCELLED, on(), merchant="Zalando", carrier="gls")
    env.parcel(S.RETURNED, on(), merchant="IKEA", carrier="seur")
    # Ready since yesterday: news only once it's ready, as in the morning.
    env.change(waiting, eta=on())
    await env.settle()
    assert phone.take() == []
    assert notifier.diagnostics()["today"]["parcels"] == 0


async def test_late_joiner_updates_the_combined_activity(env: Env) -> None:
    """On a device showing one activity, a parcel due today later updates it."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    env.parcel(eta=on())
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    late = env.parcel(eta=on(NEXT_DAY), merchant="Decathlon", carrier="gls")
    notifier = await env.start()
    await env.goto(at(8))
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            "0 of 2 delivered",
            "0/2",
            0,
            BOX,
            0.5,
            progress_max=2,
        )
    ]

    await env.goto(at(8, 24))
    env.change(late, eta=on())
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            "0 of 3 delivered",
            "0/3",
            0,
            BOX,
            0.5,
            progress_max=3,
        )
    ]
    assert notifier.diagnostics()["today"]["activity_starts"] == 1


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
            f"0 of 4 delivered{SEP}next: IKEA via GLS 13{DASH}14h",
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
            f"1 of 4 delivered{SEP}next: Amazon via DPD 15{DASH}16h",
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
            f"1 of 3 delivered{SEP}next: Amazon via DPD 15{DASH}16h",
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
            f"0 of 2 delivered{SEP}next: Amazon via DPD 13{DASH}14h",
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


async def test_probably_delivered(env: Env, hass: HomeAssistant) -> None:
    """An inferred delivery alerts no one, and shows no time it isn't sure of."""
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    android = env.phone("Sam Pixel", SAM, "android")
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(iphone.take()) == 1

    await env.goto(at(10, 42))
    env.infer(parcel)
    await env.settle()
    assert iphone.take() == [
        activity(
            tag_of(parcel),
            "Amazon",
            f"Probably delivered{SEP}DPD",
            "Probably",
            4,
            DONE,
            0.2,
            silent=True,
        )
    ]
    assert ipad.take() == android.take() == []
    assert persistent(hass) == lines(
        "**1 parcel today**",
        "",
        f"- Amazon{SEP}DPD{SEP}Probably delivered",
        "",
        f"[Open Parcels]({PATH})",
    )

    await env.goto(at(11, 13))
    assert iphone.take() == [end(tag_of(parcel))]
    assert ipad.take() == android.take() == []


async def test_probably_delivered_confirmed(env: Env) -> None:
    """The carrier's news that it was delivered alerts, as any delivery does."""
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(iphone.take()) == 1

    await env.goto(at(10, 42))
    env.infer(parcel)
    await env.settle()
    assert len(iphone.take()) == 1
    assert ipad.take() == []

    await env.goto(at(10, 55))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    assert [
        (payload["message"], payload["data"].get("silent")) for payload in iphone.take()
    ] == [(f"Delivered {CHECK} 10:55{SEP}DPD", None)]
    assert [payload["message"] for payload in ipad.take()] == [
        f"Delivered {CHECK} 10:55{SEP}DPD"
    ]


async def test_probably_delivered_taken_back_once_ended(env: Env) -> None:
    """Taking back an inferred delivery once its activity ended starts it anew."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1

    await env.goto(at(10, 42))
    env.infer(parcel)
    await env.settle()
    assert len(phone.take()) == 1
    await env.goto(at(11, 13))
    assert phone.take() == [end(tag_of(parcel))]

    await env.goto(at(14))
    env.uninfer(parcel)
    await env.settle()
    assert phone.take() == [
        activity(
            tag_of(parcel, 2),
            "Amazon",
            f"Expected today{SEP}DPD",
            "Today",
            2,
            TRUCK,
            0.5,
        )
    ]


async def test_a_delivery_marked_by_hand_taken_back(env: Env) -> None:
    """Undoing a mark brings the activity back, with an alert, also once ended.

    Marking it delivered by mistake told everyone; so does taking it back, and
    marking it again, however soon: that's no flip to damp.
    """
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    await env.goto(at(9))
    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    assert len(phone.take()) == 1

    def hand(action: Any) -> None:
        action(env.host.data, parcel.id, dt_util.utcnow())
        env.changed()

    def shown() -> list[tuple[str, str, bool | None]]:
        return [
            (payload["data"]["tag"], payload["message"], payload["data"].get("silent"))
            for payload in phone.take()
        ]

    await env.goto(at(10, 42))
    hand(mark_delivered)
    await env.settle()
    assert shown() == [(tag_of(parcel), f"Delivered {CHECK} 10:42{SEP}DPD", None)]
    await env.goto(at(10, 50))
    hand(undo_delivery)
    await env.settle()
    assert shown() == [(tag_of(parcel), f"Out for delivery{SEP}DPD", None)]

    await env.goto(at(11))
    hand(mark_delivered)
    await env.settle()
    assert shown() == [(tag_of(parcel), f"Delivered {CHECK} 11:00{SEP}DPD", None)]
    await env.goto(at(11, 31))
    assert phone.take() == [end(tag_of(parcel))]
    await env.goto(at(14))
    hand(undo_delivery)
    await env.settle()
    assert shown() == [(tag_of(parcel, 2), f"Out for delivery{SEP}DPD", None)]


async def test_probably_delivered_in_the_combined_activity(env: Env) -> None:
    """An inferred delivery counts apart in the combined activity, quietly.

    Even when the parcel was out for delivery; taking it back is quiet too,
    and a real delivery alerts.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    parcel = env.parcel(eta=on())
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1

    await env.goto(at(9))
    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    assert [payload["data"].get("silent") for payload in phone.take()] == [None]

    await env.goto(at(10, 42))
    env.infer(parcel)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 2 delivered{SEP}1 probably",
            "0/2",
            0,
            BOX,
            0.5,
            progress_max=2,
            silent=True,
        )
    ]

    await env.goto(at(10, 50))
    env.uninfer(parcel)
    await env.settle()
    assert [
        (payload["message"], payload["data"].get("silent")) for payload in phone.take()
    ] == [(f"0 of 2 delivered{SEP}Amazon via DPD out for delivery", True)]

    await env.goto(at(11))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    assert [
        (payload["message"], payload["data"].get("silent")) for payload in phone.take()
    ] == [("1 of 2 delivered", None)]


async def test_probably_delivered_last_in_the_combined_activity(env: Env) -> None:
    """A day whose last package was only inferred delivered isn't done.

    The combined activity says the delivery is probable, without the check
    mark, and keeps showing; the carrier's confirmation alerts, and the
    activity ends 30 minutes after it.
    """
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    first = env.parcel(eta=on())
    last = env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert len(iphone.take()) == 1

    await env.goto(at(9))
    env.change(first, S.DELIVERED)
    await env.settle()
    assert [payload["message"] for payload in iphone.take()] == ["1 of 2 delivered"]
    assert len(ipad.take()) == 1

    await env.goto(at(10, 42))
    env.infer(last)
    await env.settle()
    assert iphone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"1 of 2 delivered{SEP}1 probably",
            "1/2",
            1,
            BOX,
            0.2,
            progress_max=2,
            silent=True,
        )
    ]
    assert ipad.take() == []
    await env.goto(at(14))
    assert iphone.take() == []

    env.change(last, S.DELIVERED)
    await env.settle()
    assert iphone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"2 of 2 delivered {CHECK}",
            "2/2",
            2,
            DONE,
            0.2,
            progress_max=2,
        )
    ]
    assert [payload["message"] for payload in ipad.take()] == [
        f"Delivered {CHECK} 14:00{SEP}CTT"
    ]
    await env.goto(at(14, 25))
    assert iphone.take() == []
    await env.goto(at(14, 31))
    assert iphone.take() == [end(COMBINED)]


async def test_probably_delivered_last_ends_instead_of_restarting(env: Env) -> None:
    """With only inferred deliveries left, the combined activity isn't restarted.

    A restart would alert with nothing new: after 7.5 hours it ends instead,
    and the carrier's later confirmation starts nothing.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    first = env.parcel(eta=on())
    last = env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    await env.goto(at(9))
    env.change(first, S.DELIVERED)
    env.infer(last)
    await env.settle()
    assert [payload["message"] for payload in phone.take()] == [
        f"1 of 2 delivered{SEP}1 probably"
    ]

    await env.goto(at(15, 31))
    assert phone.take() == [end(COMBINED)]
    await env.goto(at(16))
    env.change(last, S.DELIVERED)
    await env.settle()
    assert phone.take() == []


async def test_probably_delivered_taken_back(env: Env) -> None:
    """Taking back an inferred delivery is quiet; a real delivery alerts."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    [started] = phone.take()

    await env.goto(at(10, 42))
    env.infer(parcel)
    await env.settle()
    assert len(phone.take()) == 1

    await env.goto(at(10, 50))
    env.uninfer(parcel)
    await env.settle()
    assert phone.take() == [{**started, "data": {**started["data"], "silent": True}}]

    await env.goto(at(11))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    assert [
        (payload["message"], payload["data"].get("silent")) for payload in phone.take()
    ] == [(f"Delivered {CHECK} 11:00{SEP}DPD", None)]


@pytest.mark.parametrize("undated", [False, True])
async def test_delivered_at_a_time_not_known(
    env: Env, hass: HomeAssistant, undated: bool
) -> None:
    """A delivery whose time a source didn't give shows no time."""
    env.hub()
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on(), merchant="Shop store", carrier="gls")
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1

    await env.goto(at(10, 42))
    env.change(parcel, S.DELIVERED, undated=undated)
    await env.settle()
    at_time = "" if undated else " 10:42"
    assert phone.take() == [
        activity(
            tag_of(parcel),
            "Shop store",
            f"Delivered {CHECK}{at_time}{SEP}GLS",
            f"{CHECK}{at_time}",
            4,
            DONE,
            0.2,
        )
    ]
    delivered = f"Delivered {CHECK}" if undated else f"Delivered 10:42 {CHECK}"
    assert persistent(hass) == lines(
        "**1 parcel today**",
        "",
        f"- Shop store{SEP}GLS{SEP}{delivered}",
        "",
        f"[Open Parcels]({PATH})",
    )


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


async def test_a_new_time_zone_moves_the_start(env: Env, hass: HomeAssistant) -> None:
    """The day's start follows a change of Home Assistant's time zone.

    At 07:00 in Lisbon the notifier waits for 08:00. Home Assistant moves to
    Dubai, where it's 10:00 already: today's parcel starts now, not when
    08:00 in Lisbon comes.
    """
    listeners = hass.bus.async_listeners().get(EVENT_CORE_CONFIG_UPDATE, 0)
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    notifier = await env.start()
    assert phone.take() == []

    await hass.config.async_update(time_zone="Asia/Dubai")
    await env.settle()
    assert summary(phone.take()) == [(tag_of(parcel), f"Expected today{SEP}DPD")]

    await notifier.async_stop()
    assert hass.bus.async_listeners().get(EVENT_CORE_CONFIG_UPDATE, 0) == listeners


async def test_a_new_time_zone_moves_the_cutoff(env: Env, hass: HomeAssistant) -> None:
    """Moving east past the cut-off ends the day's activities at once."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    for hour, minute in ((8, 0), (15, 30), (21, 30)):
        await env.goto(at(hour, minute))
    assert [tag for tag, _ in summary(phone.take())] == [
        tag_of(parcel),
        tag_of(parcel),
        tag_of(parcel, 2),
    ]

    # 22:30 in Berlin.
    await hass.config.async_update(time_zone="Europe/Berlin")
    await env.settle()
    assert phone.take() == [end(tag_of(parcel, 2))]

    # A change that keeps the zone changes nothing.
    await hass.config.async_update(time_zone="Europe/Berlin", location_name="Home")
    await env.settle()
    assert phone.take() == []


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
    second = at(9) + timedelta(seconds=1)
    dpd = "dpd.pt"
    env.change(parcel, S.OUT_FOR_DELIVERY, eta=window(13, 14), sent=at(9), label=dpd)
    env.change(parcel, eta=window(14, 15), when=second, sent=second, label=dpd)
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


@pytest.mark.parametrize(
    ("item_names", "named", "plain"),
    [
        (
            True,
            f"Expected today{SEP}CTT{SEP}Winter coat",
            f"Expected today{SEP}DPD{SEP}Blue scarf",
        ),
        (False, f"Expected today{SEP}CTT", f"Expected today{SEP}DPD"),
    ],
)
async def test_parcel_app_names_go_with_item_names(
    env: Env, item_names: bool, named: str, plain: str
) -> None:
    """A parcel's Parcel app name shows when it has no items, like item names.

    It's left out when it repeats the title, and for private parcels.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_ITEM_NAMES: item_names, CONF_COLLAPSE_THRESHOLD: 9})
    coat = env.parcel(eta=on(), merchant="Zalando", carrier="ctt", name="Winter coat")
    scarf = env.parcel(eta=on(), items=("Blue scarf",), name="Scarf, gift wrap")
    same = env.parcel(eta=on(), merchant="Etsy", carrier="gls", name=" etsy ")
    gift = env.parcel(eta=on(), owners=(ALEX,), private=True, name="Board game")
    await env.start()
    await env.goto(at(8))
    assert summary(phone.take()) == [
        (tag_of(coat), named),
        (tag_of(scarf), plain),
        (tag_of(same), f"Expected today{SEP}GLS"),
        (tag_of(gift), f"Expected today{SEP}DPD"),
    ]


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
            "data": {"tag": tag_of(parcel), "url": link_of(parcel)},
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


async def test_persistent_notification_one_line_per_shipment(
    env: Env, hass: HomeAssistant
) -> None:
    """Packages of one shipment share a line per status; delivered ones don't."""
    env.hub()
    packages = [
        env.parcel(eta=on(), merchant="Loja Exemplo", carrier="gls") for _ in range(4)
    ]
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()

    await env.goto(at(8))
    assert persistent(hass) == lines(
        "**5 parcels today**",
        "",
        f"- Loja Exemplo{SEP}GLS{SEP}4 packages{SEP}Expected today",
        f"- Zalando{SEP}CTT{SEP}Expected today",
        "",
        f"[Open Parcels]({PATH})",
    )

    await env.goto(at(10, 42))
    env.change(packages[0], S.DELIVERED)
    await env.goto(at(11, 5))
    env.change(packages[2], S.DELIVERED)
    await env.settle()
    assert persistent(hass) == lines(
        "**5 parcels today**",
        "",
        f"- Loja Exemplo{SEP}GLS{SEP}2 packages{SEP}Expected today",
        f"- Zalando{SEP}CTT{SEP}Expected today",
        f"- Loja Exemplo{SEP}GLS{SEP}Delivered 10:42 {CHECK}",
        f"- Loja Exemplo{SEP}GLS{SEP}Delivered 11:05 {CHECK}",
        "",
        f"[Open Parcels]({PATH})",
    )


async def test_persistent_notification_packages_probably_delivered(
    env: Env, hass: HomeAssistant
) -> None:
    """Packages only inferred delivered share a line, after those delivered.

    Their time is another package's: they come after those with a time.
    """
    env.hub()
    packages = [
        env.parcel(eta=on(), merchant="Loja Exemplo", carrier="gls") for _ in range(4)
    ]
    other = env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))

    await env.goto(at(10, 42))
    env.infer(packages[1])
    env.infer(packages[2])
    env.change(packages[0], S.DELIVERED)
    await env.settle()
    assert persistent(hass) == lines(
        "**5 parcels today**",
        "",
        f"- Loja Exemplo{SEP}GLS{SEP}Expected today",
        f"- Zalando{SEP}CTT{SEP}Expected today",
        f"- Loja Exemplo{SEP}GLS{SEP}Delivered 10:42 {CHECK}",
        f"- Loja Exemplo{SEP}GLS{SEP}2 packages{SEP}Probably delivered",
        "",
        f"[Open Parcels]({PATH})",
    )

    await env.goto(at(11, 5))
    env.change(other, S.DELIVERED)
    await env.settle()
    assert persistent(hass) == lines(
        "**5 parcels today**",
        "",
        f"- Loja Exemplo{SEP}GLS{SEP}Expected today",
        f"- Loja Exemplo{SEP}GLS{SEP}Delivered 10:42 {CHECK}",
        f"- Zalando{SEP}CTT{SEP}Delivered 11:05 {CHECK}",
        f"- Loja Exemplo{SEP}GLS{SEP}2 packages{SEP}Probably delivered",
        "",
        f"[Open Parcels]({PATH})",
    )


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
            f"Ready at Locker 12{SEP}CTT",
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


async def test_pickup_says_where_and_until_when(env: Env, hass: HomeAssistant) -> None:
    """A pickup names its point without the address, and the last day to collect."""
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    android = env.phone("Sam Pixel", SAM, "android")
    parcel = env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert len(iphone.take()) == 1

    await env.goto(at(10, 15))
    env.change(
        parcel,
        S.READY_FOR_PICKUP,
        sent=at(10, 15),
        pickup_point="Papelaria Exemplo do Bairro Alto, Rua Inventada 7, Lisboa",
    )
    await env.settle()
    ready = f"Ready at Papelaria Exemplo do Bairro{ELLIPSIS}"
    assert iphone.take() == [
        activity(
            tag_of(parcel), "Decathlon", f"{ready}{SEP}CTT", "Pickup", 3, SHOP, 0.7
        )
    ]
    assert (
        summary(ipad.take())
        == summary(android.take())
        == [(tag_of(parcel), f"{ready}{SEP}CTT")]
    )

    # A later e-mail gives the last day: a quiet update and no new notification.
    await env.goto(at(10, 50))
    env.change(
        parcel, S.READY_FOR_PICKUP, sent=at(10, 50), collect_by=date(2026, 6, 24)
    )
    await env.settle()
    assert iphone.take() == [
        activity(
            tag_of(parcel),
            "Decathlon",
            f"{ready}{SEP}collect by Wed 24{SEP}CTT",
            "Pickup",
            3,
            SHOP,
            0.7,
            silent=True,
        )
    ]
    assert ipad.take() == android.take() == []
    assert (
        f"- Decathlon{SEP}CTT{SEP}Ready for pickup at Papelaria Exemplo do Bairro "
        f"Alto, Rua I{ELLIPSIS}, collect by Wed 24 Jun"
    ) in str(persistent(hass)).splitlines()


def pending_return(entry: ReturnEntry, gen: int = 1, **kwargs: Any) -> dict[str, Any]:
    """Return the payload of a return pickup still to come, by CTT for Zalando."""
    return activity(
        ret_tag(entry, gen),
        "Zalando",
        f"Return pickup today{SEP}CTT",
        "Return",
        3,
        RETURN,
        0.6,
        **kwargs,
    )


async def test_return_pickup(env: Env, hass: HomeAssistant) -> None:
    """A return pickup has its own pink activity until it's marked picked up.

    Marking it is a quiet update, and the activity ends half an hour later,
    like a delivered parcel's. A pickup on another day waits for that day.
    """
    phone = env.phone("Alex iPhone", ALEX)
    entry = env.ret(items=("Winter coat",))
    later = env.ret("Decathlon", "dpd", NEXT_DAY)
    notifier = await env.start()
    await env.goto(at(8))
    assert phone.take() == [pending_return(entry)]
    listed = lines(
        "**1 return pickup today**",
        "",
        f"- Zalando{SEP}CTT{SEP}Return pickup today",
        "",
        f"[Open Parcels]({PATH})",
    )
    assert persistent(hass) == listed
    assert notifier.diagnostics()["today"]["return_pickups"] == 1

    env.changed()
    await env.settle()
    assert phone.take() == []

    await env.goto(at(10, 42))
    env.picked_up(entry)
    await env.settle()
    assert phone.take() == [
        activity(
            ret_tag(entry),
            "Zalando",
            f"Return picked up {CHECK} 10:42{SEP}CTT",
            f"{CHECK} 10:42",
            4,
            RETURN,
            0.2,
            silent=True,
        )
    ]
    done = lines(
        "**1 return pickup today**",
        "",
        f"- Zalando{SEP}CTT{SEP}Return picked up 10:42 {CHECK}",
        "",
        f"[Open Parcels]({PATH})",
    )
    assert persistent(hass) == done

    await env.goto(at(11, 5))
    assert phone.take() == []
    await env.goto(at(11, 13))
    assert phone.take() == [end(ret_tag(entry))]

    await env.goto(at(0, 30, NEXT_DAY))
    assert persistent(hass) == done.replace("today", "yesterday")

    await env.goto(at(8, day=NEXT_DAY))
    assert phone.take() == [
        activity(
            ret_tag(later),
            "Decathlon",
            f"Return pickup today{SEP}DPD",
            "Return",
            3,
            RETURN,
            0.6,
        )
    ]
    # Not marked picked up: like a parcel's, it starts again before Apple's
    # limit, and the cut-off ends it.
    await env.goto(at(15, 30, NEXT_DAY))
    assert summary(phone.take()) == [
        (ret_tag(later), END),
        (ret_tag(later, 2), f"Return pickup today{SEP}DPD"),
    ]
    await env.goto(at(22, day=NEXT_DAY))
    assert phone.take() == [end(ret_tag(later, 2))]


async def test_return_pickup_undo(env: Env) -> None:
    """Undo shows the return pickup again: quietly, or anew once it ended."""
    phone = env.phone("Alex iPhone", ALEX)
    entry = env.ret()
    await env.start()
    await env.goto(at(8))
    assert phone.take() == [pending_return(entry)]

    await env.goto(at(10, 42))
    env.picked_up(entry)
    await env.settle()
    assert summary(phone.take()) == [
        (ret_tag(entry), f"Return picked up {CHECK} 10:42{SEP}CTT")
    ]

    await env.goto(at(11, 5))
    env.picked_up(entry, False)
    await env.settle()
    assert phone.take() == [pending_return(entry, silent=True)]
    await env.goto(at(11, 13))
    assert phone.take() == []

    await env.goto(at(13, 40))
    env.picked_up(entry)
    await env.settle()
    assert summary(phone.take()) == [
        (ret_tag(entry), f"Return picked up {CHECK} 13:40{SEP}CTT")
    ]
    await env.goto(at(14, 11))
    assert phone.take() == [end(ret_tag(entry))]

    await env.goto(at(15))
    env.picked_up(entry, False)
    await env.settle()
    assert phone.take() == [pending_return(entry, 2)]


async def test_one_activity_per_return_pickup(env: Env) -> None:
    """A return pickup starts one activity, whatever else happens that day."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    entry = env.ret()
    notifier = await env.start()
    await env.goto(at(8))
    assert summary(phone.take()) == [
        (tag_of(parcel), f"Expected today{SEP}DPD"),
        (ret_tag(entry), f"Return pickup today{SEP}CTT"),
    ]

    env.changed()
    await env.settle()
    await env.goto(at(9))
    notifier = await env.restart()
    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    await env.goto(at(10, 42))
    env.picked_up(entry)
    await env.settle()
    await env.goto(at(11, 5))
    env.picked_up(entry, False)
    await env.settle()
    await env.goto(at(13, 40))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    assert [
        payload["data"]["tag"]
        for payload in phone.take()
        if not payload["data"].get("silent")
    ] == [tag_of(parcel), tag_of(parcel)]
    assert notifier.diagnostics()["today"]["activity_starts"] == 2


async def test_return_pickup_joins_and_leaves(env: Env, hass: HomeAssistant) -> None:
    """A return whose pickup becomes today joins; one moved to another day leaves.

    One picked up before the start time starts nothing, until someone takes
    that back.
    """
    phone = env.phone("Alex iPhone", ALEX)
    early = env.ret()
    moved = env.ret("Decathlon", "dpd")
    await env.start()
    await env.goto(at(7, 30))
    env.picked_up(early)
    await env.settle()
    await env.goto(at(8))
    assert summary(phone.take()) == [(ret_tag(moved), f"Return pickup today{SEP}DPD")]
    assert (
        f"- Zalando{SEP}CTT{SEP}Return picked up 07:30 {CHECK}"
        in str(persistent(hass)).splitlines()
    )

    await env.goto(at(9))
    moved.origins["m-later"] = ReturnOrigin(
        message="m-later",
        time=dt_util.utcnow(),
        merchant="Decathlon",
        carrier="dpd",
        pickup=NEXT_DAY,
        pickup_rule=PickupRule.EMAIL,
    )
    env.changed()
    await env.settle()
    assert phone.take() == [end(ret_tag(moved))]

    await env.goto(at(11, 5))
    late = env.ret("IKEA", "gls")
    env.changed()
    await env.settle()
    assert phone.take() == [
        activity(
            ret_tag(late),
            "IKEA",
            f"Return pickup today{SEP}GLS",
            "Return",
            3,
            RETURN,
            0.6,
        )
    ]

    await env.goto(at(12))
    env.picked_up(early, False)
    await env.settle()
    assert phone.take() == [pending_return(early)]


async def test_return_pickups_in_the_combined_activity(env: Env) -> None:
    """Return pickups count toward the threshold but are listed apart."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 2})
    first = env.parcel(eta=window(13, 14))
    second = env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    entry = env.ret()
    notifier = await env.start()
    await env.goto(at(8))
    next_up = f"next: Amazon via DPD 13{DASH}14h"
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 2 delivered{SEP}1 return pickup{SEP}{next_up}",
            "0/3",
            0,
            RETURN,
            0.6,
            progress_max=3,
        )
    ]

    await env.goto(at(10, 42))
    env.picked_up(entry)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 2 delivered{SEP}1 return picked up {CHECK}{SEP}{next_up}",
            "1/3",
            1,
            BOX,
            0.5,
            progress_max=3,
            silent=True,
        )
    ]

    await env.goto(at(11, 5))
    env.change(first, S.DELIVERED)
    env.change(second, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"2 of 2 delivered {CHECK}{SEP}1 return picked up {CHECK}",
            "3/3",
            3,
            DONE,
            0.2,
            progress_max=3,
        )
    ]
    await env.goto(at(11, 36))
    assert phone.take() == [end(COMBINED)]
    assert notifier.diagnostics()["today"]["activity_starts"] == 1


async def test_return_pickups_alone_can_be_combined(env: Env) -> None:
    """A second return pickup over the threshold combines them."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    entry = env.ret()
    await env.start()
    await env.goto(at(8))
    assert phone.take() == [pending_return(entry)]

    await env.goto(at(11, 5))
    env.ret("IKEA", "gls")
    env.changed()
    await env.settle()
    assert phone.take() == [
        end(ret_tag(entry)),
        activity(
            COMBINED,
            "Parcels today",
            "2 return pickups",
            "0/2",
            0,
            RETURN,
            0.6,
            progress_max=2,
        ),
    ]

    await env.goto(at(13, 40))
    env.picked_up(entry)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"1 return pickup{SEP}1 return picked up {CHECK}",
            "1/2",
            1,
            RETURN,
            0.6,
            progress_max=2,
            silent=True,
        )
    ]


async def test_private_return_pickups(env: Env, hass: HomeAssistant) -> None:
    """A private return, or one of a private parcel's order, reaches its owners only.

    Item names show only for shared returns.
    """
    alex = env.phone("Alex iPhone", ALEX)
    sam = env.phone("Sam iPhone", SAM)
    env.hub(**{CONF_ITEM_NAMES: True, CONF_COLLAPSE_THRESHOLD: 9})
    shared = env.ret(items=("Winter coat", "Wool hat"))
    mine = env.ret("Etsy", "gls", items=("Board game",), owners=(SAM,), private=True)
    gift = env.ret(
        "IKEA", "dpd", items=("Blue scarf",), order_numbers=("ZX2026061077",)
    )
    env.parcel(
        S.DELIVERED,
        merchant="IKEA",
        owners=(ALEX,),
        private=True,
        order_numbers=("ZX2026061077",),
        when=at(10, day=DAY - timedelta(days=4)),
    )
    await env.start()
    await env.goto(at(8))
    named = (ret_tag(shared), f"Return pickup today{SEP}CTT{SEP}Winter coat +1 more")
    assert summary(alex.take()) == [
        named,
        (ret_tag(gift), f"Return pickup today{SEP}DPD"),
    ]
    assert summary(sam.take()) == [
        named,
        (ret_tag(mine), f"Return pickup today{SEP}GLS"),
    ]
    listed = str(persistent(hass)).splitlines()
    assert f"- Zalando{SEP}CTT{SEP}Return pickup today" in listed
    assert "- +2 private return pickups" in listed
    assert not any("IKEA" in row or "Etsy" in row for row in listed)


async def test_persistent_notification_lists_return_pickups(
    env: Env, hass: HomeAssistant
) -> None:
    """The day's list names the return pickups after the parcels."""
    env.hub()
    env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    done = env.ret("IKEA", "gls")
    env.ret()
    env.ret("Etsy", "dpd")
    env.ret("Late Shop", "dpd", private=True, owners=(SAM,))
    env.ret("Shop store", None, NEXT_DAY)
    env.parcel(eta=on(), merchant="Loja Exemplo", carrier="gls", private=True)
    await env.start()
    await env.goto(at(10, 42))
    env.picked_up(done)
    await env.settle()
    rows = [
        f"- Decathlon{SEP}CTT{SEP}Expected today",
        f"- Etsy{SEP}DPD{SEP}Return pickup today",
        f"- Zalando{SEP}CTT{SEP}Return pickup today",
        f"- IKEA{SEP}GLS{SEP}Return picked up 10:42 {CHECK}",
        "- +1 private parcel",
        "- +1 private return pickup",
        "",
        f"[Open Parcels]({PATH})",
    ]
    assert persistent(hass) == lines(
        "**2 parcels and 4 return pickups today**", "", *rows
    )

    await env.goto(at(0, 30, NEXT_DAY))
    rows[0] = f"- Decathlon{SEP}CTT{SEP}Expected yesterday"
    rows[1] = f"- Etsy{SEP}DPD{SEP}Return pickup yesterday"
    rows[2] = f"- Zalando{SEP}CTT{SEP}Return pickup yesterday"
    assert persistent(hass) == lines(
        "**2 parcels and 4 return pickups yesterday**", "", *rows
    )

    await env.goto(at(8, day=NEXT_DAY))
    assert persistent(hass) == lines(
        "**1 return pickup today**",
        "",
        f"- Shop store{SEP}Return pickup today",
        "",
        f"[Open Parcels]({PATH})",
    )


async def test_return_pickup_on_ipads_and_android(env: Env) -> None:
    """iPads and Android phones get one notification per return pickup."""
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    android = env.phone("Sam Pixel", SAM, "android")
    entry = env.ret()
    await env.start()
    await env.goto(at(8))
    message = f"Return pickup today{SEP}CTT"
    link = f"{PATH}?return={entry.id}"
    assert ipad.take() == [
        {
            "title": "Zalando",
            "message": message,
            "data": {"tag": ret_tag(entry), "url": link},
        }
    ]
    assert android.take() == [
        {
            "title": "Zalando",
            "message": message,
            "data": {
                "tag": ret_tag(entry),
                "clickAction": link,
                "notification_icon": RETURN,
                "color": PINK,
            },
        }
    ]

    await env.goto(at(10, 42))
    env.picked_up(entry)
    await env.settle()
    env.picked_up(entry, False)
    await env.settle()
    await env.restart()
    assert ipad.take() == android.take() == []


@pytest.mark.parametrize("updated", [True, False], ids=["updated", "started late"])
async def test_return_pickups_set_before_the_start_wait(
    env: Env, hass: HomeAssistant, updated: bool
) -> None:
    """Started after the start time, returns set before it start nothing that day.

    Their carrier may have come hours ago: after an update from a release
    without return pickups, whose day has none, or when Home Assistant was
    down at the start time. The persistent notification still lists them.
    A return an e-mail sets for today afterwards joins; one from an older
    e-mail, read only now, doesn't. Taking back a "picked up" makes a waiting
    return join.
    """
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    waiting = env.ret()
    env.ret("Decathlon", "dpd")
    if updated:
        env.host.data.engine[STATE_KEY] = {
            "version": 1,
            "days": {
                DAY.isoformat(): {
                    "morning": True,
                    "board": [],
                    "combined": [],
                    "activities": {},
                    "notified": {},
                }
            },
        }
    env.freezer.move_to(at(15))
    notifier = await env.start()
    await env.settle()
    assert iphone.take() == ipad.take() == []
    assert notifier.diagnostics()["today"]["return_pickups"] == 0
    listed = str(persistent(hass)).splitlines()
    assert f"- Zalando{SEP}CTT{SEP}Return pickup today" in listed
    assert f"- Decathlon{SEP}DPD{SEP}Return pickup today" in listed

    await env.goto(at(15, 10))
    late = env.ret("IKEA", "gls")
    env.ret("Etsy", "dpd", sent=at(18, day=DAY - timedelta(days=1)))
    env.changed()
    await env.settle()
    joined = [(ret_tag(late), f"Return pickup today{SEP}GLS")]
    assert summary(iphone.take()) == summary(ipad.take()) == joined
    assert notifier.diagnostics()["today"]["return_pickups"] == 1

    await env.goto(at(15, 20))
    env.picked_up(waiting)
    await env.settle()
    assert iphone.take() == ipad.take() == []
    env.picked_up(waiting, False)
    await env.settle()
    joined = [(ret_tag(waiting), f"Return pickup today{SEP}CTT")]
    assert summary(iphone.take()) == summary(ipad.take()) == joined
    assert notifier.diagnostics()["today"]["return_pickups"] == 2


@pytest.mark.parametrize(("minute", "joins"), [(14, True), (15, False)])
async def test_return_pickups_join_within_15_minutes_of_the_start(
    env: Env, minute: int, joins: bool
) -> None:
    """Started shortly after the start time, the day's return pickups join."""
    phone = env.phone("Alex iPhone", ALEX)
    entry = env.ret()
    env.freezer.move_to(at(8, minute))
    await env.start()
    await env.settle()
    assert phone.take() == ([pending_return(entry)] if joins else [])


async def test_return_pickup_moved_to_today_after_the_start(env: Env) -> None:
    """After the start time, an e-mail that moves a pickup to today makes it join.

    One that repeats a pickup already today before the start doesn't.
    """
    phone = env.phone("Alex iPhone", ALEX)
    moved = env.ret(pickup=NEXT_DAY)
    repeated = env.ret("Decathlon", "dpd")
    env.freezer.move_to(at(15))
    await env.start()
    await env.settle()
    assert phone.take() == []

    await env.goto(at(15, 10))
    for entry in (moved, repeated):
        origin = next(iter(entry.origins.values()))
        later = replace(
            origin, message=f"{origin.message}-later", time=dt_util.utcnow(), pickup=DAY
        )
        entry.origins[later.message] = later
    env.changed()
    await env.settle()
    assert phone.take() == [pending_return(moved)]


@pytest.mark.parametrize(
    ("details", "message", "listed"),
    [
        # The carrier said when it tried.
        (
            {"when": at(11, 20), "sent": at(11, 50), "next_attempt": date(2026, 6, 22)},
            f"Missed 11:20{SEP}next attempt Mon 22",
            "Delivery attempted 11:20, next attempt Mon 22 Jun",
        ),
        # Only the e-mail's time is known: it doesn't pass for the attempt's.
        (
            {"when": at(11, 50), "sent": at(11, 50), "next_attempt": NEXT_DAY},
            f"Missed{SEP}reported 11:50{SEP}next attempt tomorrow",
            "Delivery attempted, reported 11:50, next attempt tomorrow",
        ),
        # The carrier took it to a pickup point.
        (
            {
                "when": at(11, 20),
                "sent": at(11, 50),
                "pickup_point": "Loja Exemplo, Avenida Inventada 3",
                "collect_by": date(2026, 6, 25),
            },
            f"Missed 11:20{SEP}taken to Loja Exemplo{SEP}collect by Thu 25",
            "Delivery attempted 11:20, taken to Loja Exemplo, Avenida Inventada 3, "
            "collect by Thu 25 Jun",
        ),
        (
            {"when": at(11, 20), "sent": at(11, 50), "collect_by": date(2026, 6, 25)},
            f"Missed 11:20{SEP}collect by Thu 25",
            "Delivery attempted 11:20, collect by Thu 25 Jun",
        ),
        # Only its day is known, and that's today.
        ({"timeless": True}, "Missed", "Delivery attempted"),
        (
            {"when": at(11, 20), "eta": on(NEXT_DAY)},
            f"Missed 11:20{SEP}Expected tomorrow",
            "Delivery attempted 11:20, expected tomorrow",
        ),
    ],
)
async def test_missed_attempt(
    env: Env, hass: HomeAssistant, details: dict[str, Any], message: str, listed: str
) -> None:
    """A missed attempt says when it happened and what comes next."""
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(iphone.take()) == 1

    await env.goto(at(11, 50))
    env.change(parcel, S.ATTEMPTED, **details)
    await env.settle()
    shown = [(tag_of(parcel), f"{message}{SEP}DPD")]
    assert summary(iphone.take()) == summary(ipad.take()) == shown
    assert f"- Amazon{SEP}DPD{SEP}{listed}" in str(persistent(hass)).splitlines()


@pytest.mark.parametrize(
    ("details", "message", "listed"),
    [
        (
            {"left_at": LeftAt.NEIGHBOUR},
            f"Delivered {CHECK} 10:25{SEP}with a neighbour",
            f"Delivered 10:25 with a neighbour {CHECK}",
        ),
        # Only its day is known.
        (
            {"left_at": LeftAt.MAILBOX, "timeless": True},
            f"Delivered {CHECK}{SEP}in the mailbox",
            f"Delivered in the mailbox {CHECK}",
        ),
    ],
)
async def test_delivered_says_where_it_was_left(
    env: Env, hass: HomeAssistant, details: dict[str, Any], message: str, listed: str
) -> None:
    """The final state says where the parcel was left."""
    iphone = env.phone("Alex iPhone", ALEX)
    android = env.phone("Sam Pixel", SAM, "android")
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(iphone.take()) == 1

    await env.goto(at(10, 25))
    env.change(parcel, S.DELIVERED, **details)
    await env.settle()
    shown = [(tag_of(parcel), f"{message}{SEP}DPD")]
    assert summary(iphone.take()) == summary(android.take()) == shown
    assert f"- Amazon{SEP}DPD{SEP}{listed}" in str(persistent(hass)).splitlines()


def _amazon_said_it_delivers(order: Parcel, source: Source) -> None:
    """Add what 0.1.7 stored: Amazon as the carrier, without one of its numbers."""
    origin = Origin(
        id=f"said-{order.id}",
        source=source,
        time=at(7),
        carrier="amazon",
        merchant="Amazon",
    )
    order.origins[origin.id] = origin
    order.touch(at(7))


async def test_delivery_day_counts_packages(env: Env, hass: HomeAssistant) -> None:
    """Orders without a carrier number ride in the day's packages: 3 of 3."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 2})
    ctt = env.parcel(eta=on(), carrier="ctt_expresso")
    paack = [env.parcel(eta=on(), merchant=None, carrier="paack") for _ in range(2)]
    lamp = env.parcel(eta=on(), carrier=None, items=("Desk lamp",))
    gifts = env.parcel(
        eta=on(), carrier=None, items=("Blue scarf", "Wool hat", "Green gloves")
    )
    _amazon_said_it_delivers(lamp, Source.PARCELAPP)
    _amazon_said_it_delivers(gifts, Source.AI)
    assert lamp.state.carrier == gifts.state.carrier == "amazon"
    # The one-time repair forgets it.
    repair_store(env.host.data, at(7), since=3)
    assert len(env.host.data.parcels) == 5
    assert lamp.state.carrier is None
    assert gifts.state.carrier is None

    notifier = await env.start()
    await env.goto(at(8))
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 3 delivered{SEP}may hold 2 Amazon orders",
            "0/3",
            0,
            BOX,
            0.5,
            progress_max=3,
        )
    ]

    await env.goto(at(11, 10))
    env.change(ctt, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"1 of 3 delivered{SEP}may hold 2 Amazon orders",
            "1/3",
            1,
            BOX,
            0.5,
            progress_max=3,
        )
    ]

    await env.goto(at(14, 20))
    for box in paack:
        env.change(box, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"3 of 3 delivered {CHECK}{SEP}may hold 2 Amazon orders",
            "3/3",
            3,
            DONE,
            0.2,
            progress_max=3,
        )
    ]

    await env.goto(at(14, 51))
    assert phone.take() == [end(COMBINED)]

    # The Parcel app tells, without a date, that an order came: in a package.
    await env.goto(at(15, 2))
    env.change(lamp, S.DELIVERED, undated=True)
    await env.settle()
    assert phone.take() == []
    assert persistent(hass) == lines(
        "**3 parcels today**",
        "",
        f"- Amazon{SEP}CTT Expresso{SEP}Delivered 11:10 {CHECK}",
        f"- Paack{SEP}Delivered 14:20 {CHECK}",
        f"- Paack{SEP}Delivered 14:20 {CHECK}",
        f"- Amazon{SEP}2 orders{SEP}Possibly in a package from CTT Expresso",
        "",
        f"[Open Parcels]({PATH})",
    )
    assert notifier.diagnostics()["today"]["orders_in_a_box"] == 2


async def test_order_no_package_could_hold_counts_alone(env: Env) -> None:
    """An order that none of the day's packages could hold is its own entry."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    box = env.parcel(eta=on(), carrier="gls")
    alone = env.parcel(eta=on(), carrier=None)
    # The shop named CTT, which doesn't deliver the GLS package.
    alone.origins["named"] = Origin(
        id="named", source=Source.PARSER, time=at(7), carrier="ctt", merchant="Amazon"
    )
    alone.touch(at(7))
    env.parcel(eta=on(), carrier=None)
    await env.start()
    await env.goto(at(8))
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 2 delivered{SEP}may hold 1 Amazon order",
            "0/2",
            0,
            BOX,
            0.5,
            progress_max=2,
        )
    ]

    await env.goto(at(10))
    env.change(box, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"1 of 2 delivered{SEP}may hold 1 Amazon order",
            "1/2",
            1,
            BOX,
            0.5,
            progress_max=2,
        )
    ]
    await env.goto(at(10, 31))
    assert phone.take() == []


async def test_orders_wait_for_their_package(env: Env) -> None:
    """Until the package that may hold them comes, its orders are pending."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    amazon = env.parcel(eta=on(), carrier="ctt")
    zalando = env.parcel(eta=on(), merchant="Zalando", carrier="gls")
    env.parcel(eta=on(), carrier=None)
    await env.start()
    await env.goto(at(8))
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 2 delivered{SEP}may hold 1 Amazon order",
            "0/2",
            0,
            BOX,
            0.5,
            progress_max=2,
        )
    ]

    await env.goto(at(10))
    env.change(zalando, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"1 of 2 delivered{SEP}may hold 1 Amazon order",
            "1/2",
            1,
            BOX,
            0.5,
            progress_max=2,
        )
    ]
    await env.goto(at(10, 31))
    assert phone.take() == []

    await env.goto(at(12))
    env.change(amazon, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"2 of 2 delivered {CHECK}{SEP}may hold 1 Amazon order",
            "2/2",
            2,
            DONE,
            0.2,
            progress_max=2,
        )
    ]
    await env.goto(at(12, 31))
    assert phone.take() == [end(COMBINED)]


async def test_order_of_another_shop_counts_alone(env: Env) -> None:
    """A package from one shop never holds another shop's order."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    boxes = [
        env.parcel(eta=on(), carrier="ctt"),
        env.parcel(eta=on(), merchant="Zalando", carrier="gls"),
    ]
    env.parcel(eta=on(), carrier=None)
    env.parcel(eta=on(), merchant="Decathlon", carrier=None)
    await env.start()
    await env.goto(at(8))
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 3 delivered{SEP}may hold 1 Amazon order",
            "0/3",
            0,
            BOX,
            0.5,
            progress_max=3,
        )
    ]

    await env.goto(at(10))
    for box in boxes:
        env.change(box, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"2 of 3 delivered{SEP}may hold 1 Amazon order",
            "2/3",
            2,
            BOX,
            0.5,
            progress_max=3,
        )
    ]
    await env.goto(at(10, 31))
    assert phone.take() == []


async def test_package_shows_the_orders_it_may_hold(
    env: Env, hass: HomeAssistant
) -> None:
    """A package's activity names, as uncertain, the orders it may hold."""
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    env.hub(**{CONF_ITEM_NAMES: True, CONF_COLLAPSE_THRESHOLD: 9})
    box = env.parcel(eta=on(), carrier="ctt")
    lamp = env.parcel(eta=on(), carrier=None, items=("Desk lamp",))
    env.parcel(eta=on(), carrier=None, items=("Blue scarf", "Wool hat"))
    env.parcel(
        eta=on(), carrier=None, items=("Secret gift",), owners=(ALEX,), private=True
    )
    await env.start()
    await env.goto(at(8))
    # The private order is Alex's: his devices count it, without its items.
    possibly = f"CTT{SEP}Possibly: Desk lamp (+2){SEP}may hold 3 Amazon orders"
    assert iphone.take() == [
        activity(
            tag_of(box),
            "Amazon",
            f"Expected today{SEP}{possibly}",
            "Today",
            2,
            TRUCK,
            0.5,
        )
    ]
    assert ipad.take() == []

    await env.goto(at(10, 42))
    env.change(box, S.DELIVERED)
    await env.settle()
    delivered = f"Delivered {CHECK} 10:42{SEP}{possibly}"
    assert iphone.take() == [
        activity(tag_of(box), "Amazon", delivered, f"{CHECK} 10:42", 4, DONE, 0.2)
    ]
    assert ipad.take() == [
        {
            "title": "Amazon",
            "message": delivered,
            "data": {"tag": tag_of(box), "url": link_of(box)},
        }
    ]

    await env.goto(at(10, 50))
    env.change(lamp, S.DELIVERED, undated=True)
    await env.settle()
    assert iphone.take() == ipad.take() == []
    await env.goto(at(11, 13))
    assert iphone.take() == [end(tag_of(box))]
    assert ipad.take() == []
    assert persistent(hass) == lines(
        "**1 parcel today**",
        "",
        f"- Amazon{SEP}CTT{SEP}Delivered 10:42 {CHECK}",
        f"- Amazon{SEP}2 orders{SEP}Possibly in a package from CTT",
        "",
        f"[Open Parcels]({PATH})",
    )


async def test_one_package_may_hold_the_days_orders(env: Env) -> None:
    """The day's orders ride in the package that comes: 0 of 1, may hold 8.

    The package still counts once; its text says what it may hold.
    """
    phone = env.phone("Alex iPhone", ALEX)
    for _ in range(8):
        env.parcel(eta=on(), carrier=None)
    notifier = await env.start()
    await env.goto(at(8))
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            "0 of 8 delivered",
            "0/8",
            0,
            BOX,
            0.5,
            progress_max=8,
        )
    ]

    # A package of no known shop goes out for delivery: it may hold them all.
    await env.goto(at(11, 15))
    box = env.parcel(S.OUT_FOR_DELIVERY, on(), merchant=None, carrier="paack")
    env.changed()
    await env.settle()
    holds = "may hold 8 Amazon orders"
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 1 delivered{SEP}Paack out for delivery{SEP}{holds}",
            "0/1",
            0,
            OUT,
            0.9,
            progress_max=1,
        )
    ]
    today = notifier.diagnostics()["today"]
    assert (today["parcels"], today["orders_in_a_box"]) == (9, 8)

    await env.goto(at(14, 20))
    env.change(box, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"1 of 1 delivered {CHECK}{SEP}{holds}",
            "1/1",
            1,
            DONE,
            0.2,
            progress_max=1,
        )
    ]
    await env.goto(at(14, 55))
    assert phone.take() == [end(COMBINED)]


async def test_orders_several_packages_may_hold_count_once(env: Env) -> None:
    """Each package names the orders it may hold; the day counts each once."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 2})
    paack = env.parcel(eta=on(), merchant=None, carrier="paack")
    seur = env.parcel(eta=on(), merchant=None, carrier="seur")
    for _ in range(2):
        env.parcel(eta=on(), carrier=None)
    gls = env.parcel(eta=on(NEXT_DAY), merchant="Zalando", carrier="gls")
    await env.start()
    await env.goto(at(8))
    holds = "may hold 2 Amazon orders"
    assert phone.take() == [
        activity(
            tag_of(paack),
            "Paack",
            f"Expected today{SEP}{holds}",
            "Today",
            2,
            TRUCK,
            0.5,
        ),
        activity(
            tag_of(seur), "SEUR", f"Expected today{SEP}{holds}", "Today", 2, TRUCK, 0.5
        ),
    ]

    # The mention comes last, after what's next.
    await env.goto(at(9))
    env.change(gls, S.OUT_FOR_DELIVERY, eta=on())
    await env.settle()
    assert phone.take() == [
        end(tag_of(paack)),
        end(tag_of(seur)),
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 3 delivered{SEP}Zalando via GLS out for delivery{SEP}{holds}",
            "0/3",
            0,
            OUT,
            0.9,
            progress_max=3,
        ),
    ]


async def test_private_order_counts_only_for_its_owner(env: Env) -> None:
    """Another person's device neither counts a private order nor names its shop."""
    alex = env.phone("Alex iPhone", ALEX)
    sam = env.phone("Sam iPhone", SAM)
    box = env.parcel(eta=on(), merchant=None, carrier="paack")
    env.parcel(eta=on(), carrier=None)
    env.parcel(eta=on(), merchant="Zalando", carrier=None, owners=(ALEX,), private=True)
    await env.start()
    await env.goto(at(8))
    assert alex.take() == [
        activity(
            tag_of(box),
            "Paack",
            f"Expected today{SEP}may hold 2 orders",
            "Today",
            2,
            TRUCK,
            0.5,
        )
    ]
    assert sam.take() == [
        activity(
            tag_of(box),
            "Paack",
            f"Expected today{SEP}may hold 1 Amazon order",
            "Today",
            2,
            TRUCK,
            0.5,
        )
    ]


async def test_pin_leads_what_a_package_may_hold(env: Env) -> None:
    """With a PIN, what a package may hold still comes last, never critical.

    iPads and Android phones show it too, without the PIN.
    """
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    android = env.phone("Sam Pixel", SAM, "android")
    env.hub(**{CONF_PIN_ON_LOCK_SCREEN: True})
    box = env.parcel(S.OUT_FOR_DELIVERY, eta=window(13, 14), pickup_code="4826")
    for _ in range(2):
        env.parcel(eta=on(), carrier=None)
    tag = tag_of(box)
    await env.start()
    await env.goto(at(8))
    holds = "may hold 2 Amazon orders"
    plain = f"Out for delivery 13:00{DASH}14:00{SEP}DPD{SEP}{holds}"
    short = f"13{DASH}14h"
    assert iphone.take() == [activity(tag, "Amazon", plain, short, 3, OUT, 0.9)]
    env.token(iphone, tag)
    await env.goto(at(8) + timedelta(seconds=5))
    shown = f"Out for delivery\nPIN 4826{SEP}13:00{DASH}14:00{SEP}DPD{SEP}{holds}"
    assert iphone.take() == [
        pinned(activity(tag, "Amazon", shown, short, 3, OUT, 0.9, silent=True), iphone)
    ]
    assert ipad.take() == [
        {"title": "Amazon", "message": plain, "data": {"tag": tag, "url": link_of(box)}}
    ]
    assert android.take() == [
        {
            "title": "Amazon",
            "message": plain,
            "data": {
                "tag": tag,
                "clickAction": link_of(box),
                "notification_icon": OUT,
                "color": ORANGE,
            },
        }
    ]


async def test_combined_pin_leads_what_packages_may_hold(env: Env) -> None:
    """The combined activity puts what packages may hold last, also with a PIN."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1, CONF_PIN_ON_LOCK_SCREEN: True})
    env.parcel(
        S.OUT_FOR_DELIVERY,
        eta=window(13, 15),
        merchant="Zalando",
        carrier="ctt",
        pickup_code="4826",
    )
    pickup = env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    env.parcel(eta=on())
    for _ in range(2):
        env.parcel(eta=on(), carrier=None)
    await env.start()
    await env.goto(at(8))
    next_up = f"next: Zalando via CTT 13{DASH}15h"
    holds = "may hold 2 Amazon orders"
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 3 delivered{SEP}{next_up}{SEP}{holds}",
            "0/3",
            0,
            OUT,
            0.9,
            progress_max=3,
        )
    ]
    env.token(phone, COMBINED)
    await env.goto(at(8) + timedelta(seconds=5))
    assert phone.take() == [
        pinned(
            activity(
                COMBINED,
                "Parcels today",
                f"0 of 3 delivered\nPIN 4826{SEP}{next_up}{SEP}{holds}",
                "0/3",
                0,
                OUT,
                0.9,
                progress_max=3,
                silent=True,
            ),
            phone,
        )
    ]

    await env.goto(at(10))
    env.change(
        pickup,
        S.READY_FOR_PICKUP,
        sent=at(10),
        pickup_point="Locker 12",
        pickup_code="59031",
    )
    await env.settle()
    assert summary(phone.take()) == [
        (COMBINED, f"0 of 3 delivered{SEP}1 ready for pickup{SEP}{next_up}{SEP}{holds}")
    ]
    await env.goto(at(10, 1))
    assert phone.take() == [
        pinned(
            activity(
                COMBINED,
                "Parcels today",
                f"0 of 3 delivered\nPIN 4826{SEP}{next_up}{SEP}1 ready for pickup"
                f"{SEP}{holds}",
                "0/3",
                0,
                OUT,
                0.9,
                progress_max=3,
                silent=True,
            ),
            phone,
        )
    ]


async def test_what_a_package_may_hold_changes_quietly(env: Env) -> None:
    """A change in how many orders a package may hold alone is a quiet update.

    An order whose date becomes today rides along without an activity of its
    own, and the mention goes once no order rides along.
    """
    phone = env.phone("Alex iPhone", ALEX)
    box = env.parcel(eta=on(), carrier="ctt")
    first = env.parcel(eta=on(), carrier=None)
    second = env.parcel(eta=on(NEXT_DAY), carrier=None)
    tag = tag_of(box)
    notifier = await env.start()
    await env.goto(at(8))
    one = f"Expected today{SEP}CTT{SEP}may hold 1 Amazon order"
    assert phone.take() == [activity(tag, "Amazon", one, "Today", 2, TRUCK, 0.5)]

    await env.goto(at(9))
    env.change(second, eta=on())
    await env.settle()
    two = f"Expected today{SEP}CTT{SEP}may hold 2 Amazon orders"
    assert phone.take() == [
        activity(tag, "Amazon", two, "Today", 2, TRUCK, 0.5, silent=True)
    ]

    await env.goto(at(10))
    env.change(first, eta=on(NEXT_DAY))
    await env.settle()
    assert phone.take() == [
        activity(tag, "Amazon", one, "Today", 2, TRUCK, 0.5, silent=True)
    ]

    await env.goto(at(11))
    env.change(second, eta=on(NEXT_DAY))
    await env.settle()
    assert phone.take() == [
        activity(
            tag,
            "Amazon",
            f"Expected today{SEP}CTT",
            "Today",
            2,
            TRUCK,
            0.5,
            silent=True,
        )
    ]
    assert notifier.diagnostics()["today"]["activity_starts"] == 1


@pytest.mark.parametrize(
    ("status", "icon", "colour"),
    [
        (S.ORDERED, CART, BLUE),
        (S.SHIPPED, TRUCK, BLUE),
        (S.IN_TRANSIT, TRUCK, BLUE),
        (S.OUT_FOR_DELIVERY, OUT, ORANGE),
        (S.READY_FOR_PICKUP, SHOP, PURPLE),
        (S.ATTEMPTED, ALERT, RED),
        (S.EXCEPTION, ALERT, RED),
    ],
)
async def test_colour_follows_the_status(
    env: Env, status: ParcelStatus, icon: str, colour: str
) -> None:
    """The icon and the progress bar take the status colour; the card stays dark."""
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    android = env.phone("Sam Pixel", SAM, "android")
    parcel = env.parcel(status, eta=on())
    await env.start()
    await env.goto(at(8))
    looks = (
        "notification_icon",
        "notification_icon_color",
        "progress_bar_color",
        "background_color",
        "text_color",
    )
    [started] = iphone.take()
    assert [started["data"].get(key) for key in looks] == [
        icon,
        colour,
        colour,
        None,
        None,
    ]
    key = status in {S.OUT_FOR_DELIVERY, S.READY_FOR_PICKUP, S.ATTEMPTED, S.EXCEPTION}
    assert [payload["data"] for payload in android.take()] == (
        [
            {
                "tag": tag_of(parcel),
                "clickAction": link_of(parcel),
                "notification_icon": icon,
                "color": colour,
            }
        ]
        if key
        else []
    )
    # An iPad notification has no colour.
    assert [payload["data"] for payload in ipad.take()] == (
        [{"tag": tag_of(parcel), "url": link_of(parcel)}] if key else []
    )

    await env.goto(at(10))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    [delivered] = iphone.take()
    assert [delivered["data"].get(key) for key in looks] == [
        DONE,
        GREEN,
        GREEN,
        None,
        None,
    ]
    assert [payload["data"] for payload in android.take()] == [
        {
            "tag": tag_of(parcel),
            "clickAction": link_of(parcel),
            "notification_icon": DONE,
            "color": GREEN,
        }
    ]
    assert [payload["data"] for payload in ipad.take()] == [
        {"tag": tag_of(parcel), "url": link_of(parcel)}
    ]


async def test_combined_takes_the_most_urgent_colour(env: Env) -> None:
    """Out for delivery leads, then a problem, then a pickup; all done is green."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    moving = env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    ready = env.parcel(S.READY_FOR_PICKUP, merchant="Decathlon", carrier="gls")
    missed = env.parcel(S.ATTEMPTED, eta=on(), merchant="IKEA", carrier="correos")
    await env.start()
    await env.goto(at(8))
    counts = f"0 of 3 delivered{SEP}1 ready for pickup{SEP}1 problem"
    assert phone.take() == [
        activity(
            COMBINED, "Parcels today", counts, "0/3", 0, ALERT, 0.7, progress_max=3
        )
    ]

    await env.goto(at(9))
    env.change(moving, S.OUT_FOR_DELIVERY, eta=on())
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"{counts}{SEP}Zalando via CTT out for delivery",
            "0/3",
            0,
            OUT,
            0.9,
            progress_max=3,
        )
    ]

    await env.goto(at(10))
    for parcel in (moving, ready, missed):
        env.change(parcel, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"3 of 3 delivered {CHECK}",
            "3/3",
            3,
            DONE,
            0.2,
            progress_max=3,
        )
    ]


async def test_tapping_opens_the_parcel(env: Env, hass: HomeAssistant) -> None:
    """A tap opens the parcel's details; the combined activity opens the week."""
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    android = env.phone("Sam Pixel", SAM, "android")
    path = "/parcels-test/week?kiosk"
    env.hub(**{CONF_DASHBOARD_PATH: path, CONF_COLLAPSE_THRESHOLD: 1})
    first = env.parcel(S.OUT_FOR_DELIVERY, eta=on())
    second = env.parcel(eta=on(NEXT_DAY), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    link = f"{path}&parcel={first.id}"
    assert [payload["data"]["url"] for payload in iphone.take()] == [link]
    assert [payload["data"] for payload in ipad.take()] == [
        {"tag": tag_of(first), "url": link}
    ]
    assert [payload["data"] for payload in android.take()] == [
        {
            "tag": tag_of(first),
            "clickAction": link,
            "notification_icon": OUT,
            "color": ORANGE,
        }
    ]
    assert (persistent(hass) or "").endswith(f"[Open Parcels]({path})")

    await env.goto(at(9))
    env.change(second, S.OUT_FOR_DELIVERY, eta=on())
    await env.settle()
    assert [
        (payload["data"]["tag"], payload["data"].get("url"))
        for payload in iphone.take()
    ] == [(tag_of(first), None), (COMBINED, path)]
    assert [payload["data"]["clickAction"] for payload in android.take()] == [
        f"{path}&parcel={second.id}"
    ]
    assert (persistent(hass) or "").endswith(f"[Open Parcels]({path})")


@pytest.mark.parametrize(
    ("eta", "countdown", "ends", "shown", "short"),
    [
        (window(9, 12), at(11), at(12), f"09:00{DASH}12:00", f"9{DASH}12h"),
        (
            Eta(start=DAY, end=DAY, window_start=time(13), window_end=time(13, 45)),
            at(13),
            at(13, 45),
            f"13:00{DASH}13:45",
            f"13{DASH}13:45",
        ),
    ],
)
async def test_countdown_in_the_last_hour(
    env: Env, eta: Eta, countdown: datetime, ends: datetime, shown: str, short: str
) -> None:
    """The timer runs in the last hour of the window; until then the text shows."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(S.OUT_FOR_DELIVERY, eta=eta)
    notifier = await env.start()
    await env.goto(at(8))
    message = f"Out for delivery {shown}{SEP}DPD"
    assert phone.take() == [
        activity(tag_of(parcel), "Amazon", message, short, 3, OUT, 0.9)
    ]

    await env.goto(countdown - timedelta(minutes=1))
    assert phone.take() == []

    # One quiet update starts the timer.
    await env.goto(countdown)
    assert phone.take() == [
        activity(
            tag_of(parcel),
            "Amazon",
            message,
            short,
            3,
            OUT,
            1.0,
            when=ends,
            silent=True,
        )
    ]

    await env.goto(ends)
    assert phone.take() == [
        activity(tag_of(parcel), "Amazon", message, short, 3, OUT, 0.9, silent=True)
    ]
    assert notifier.diagnostics()["today"]["activity_starts"] == 1


@pytest.mark.parametrize("problem", [S.ATTEMPTED, S.EXCEPTION])
@pytest.mark.parametrize("combined", [True, False])
async def test_problem_stops_the_combined_countdown(
    env: Env, problem: ParcelStatus, combined: bool
) -> None:
    """While a parcel has a problem, the combined activity says so, not a timer.

    Its text keeps the window, and the timer runs again once no parcel has a
    problem. A parcel's own activity keeps its timer.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1 if combined else 9})
    moving = env.parcel(
        S.OUT_FOR_DELIVERY, eta=window(13, 15), merchant="Zalando", carrier="ctt"
    )
    other = env.parcel(eta=on(), merchant="IKEA", carrier="correos")
    await env.start()
    await env.goto(at(8))
    phone.take()
    await env.goto(at(14))
    timers = {
        payload["data"]["tag"]: payload["data"].get("when") for payload in phone.take()
    }
    assert timers == {COMBINED if combined else tag_of(moving): int(at(15).timestamp())}

    await env.goto(at(14, 10))
    env.change(other, problem)
    await env.settle()
    sent = phone.take()

    if not combined:
        assert [payload["data"]["tag"] for payload in sent] == [tag_of(other)]
        return
    next_up = f"next: Zalando via CTT 13{DASH}15h"
    assert sent == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 2 delivered{SEP}1 problem{SEP}{next_up}",
            "0/2",
            0,
            OUT,
            1.0,
            progress_max=2,
        )
    ]

    await env.goto(at(14, 20))
    env.change(other, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"1 of 2 delivered{SEP}{next_up}",
            "1/2",
            1,
            OUT,
            1.0,
            progress_max=2,
            when=at(15),
        )
    ]


@pytest.mark.parametrize(
    ("merchant", "carrier", "label"),
    [
        ("Amazon", "paack", "Amazon via Paack"),
        (None, "paack", "Paack"),
        ("Loja Exemplo", None, "Loja Exemplo"),
        ("DPD", "dpd", "DPD"),
        (
            "A very long shop name that goes on",
            "gls",
            f"A very long shop na{ELLIPSIS} via GLS",
        ),
    ],
)
async def test_combined_next_names_shop_and_carrier(
    env: Env, merchant: str | None, carrier: str | None, label: str
) -> None:
    """The next delivery of the combined activity names its shop and carrier."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    env.parcel(eta=window(13, 15), merchant=merchant, carrier=carrier)
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert [payload["message"] for payload in phone.take()] == [
        f"0 of 2 delivered{SEP}next: {label} 13{DASH}15h"
    ]


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
    assert diagnostics["pin_on_lock_screen"] is False
    assert diagnostics["today"] == {
        "parcels": 1,
        "morning_done": True,
        "combined_devices": 0,
        "activities": 1,
        "activity_starts": 1,
        "running": 1,
        "showing_pin": 0,
        "dismissed": 0,
        "waiting_for_token": 0,
        "notifications_sent": 0,
        "orders_in_a_box": 0,
        "return_pickups": 0,
    }
    dumped = json.dumps(diagnostics).casefold()
    for secret in (iphone.device_id, android.device_id, parcel.id, "Amazon", "Alex"):
        assert secret.casefold() not in dumped


@pytest.mark.parametrize("dismissed", [False, True])
async def test_pin_option_changes_running_activities_quietly(
    env: Env, hass: HomeAssistant, dismissed: bool
) -> None:
    """Turning the PIN option on or off updates running activities quietly.

    Hubs set up before the option show no PIN. Taking a PIN away doesn't
    start again an activity the user dismissed.
    """
    phone = env.phone("Alex iPhone", ALEX)
    entry = env.hub()
    parcel = env.parcel(S.OUT_FOR_DELIVERY, eta=window(13, 14), pickup_code="4826")
    tag = tag_of(parcel)
    notifier = await env.start()
    await env.goto(at(8))
    plain = f"Out for delivery 13:00{DASH}14:00{SEP}DPD"
    short = f"13{DASH}14h"
    assert phone.take() == [activity(tag, "Amazon", plain, short, 3, OUT, 0.9)]
    env.token(phone, tag)
    await env.goto(at(8, 10))
    assert phone.take() == []

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_PIN_ON_LOCK_SCREEN: True}
    )
    env.changed()
    await env.settle()
    shown = f"Out for delivery\nPIN 4826{SEP}13:00{DASH}14:00{SEP}DPD"
    assert phone.take() == [
        pinned(activity(tag, "Amazon", shown, short, 3, OUT, 0.9, silent=True), phone)
    ]

    if dismissed:
        env.untoken(phone, tag)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_PIN_ON_LOCK_SCREEN: False}
    )
    env.changed()
    await env.settle()
    assert phone.take() == (
        []
        if dismissed
        else [activity(tag, "Amazon", plain, short, 3, OUT, 0.9, silent=True)]
    )
    await env.goto(at(9))
    assert phone.take() == []
    assert notifier.diagnostics()["today"]["activity_starts"] == 1


async def test_pin_while_out_for_delivery(env: Env, hass: HomeAssistant) -> None:
    """With the option on, the iPhone's activity shows the delivery PIN.

    It comes quietly once the activity can be updated, never in an alert. No
    timer hides it, and it goes with the delivery. iPads, Android phones and
    the persistent notification never show it.
    """
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    android = env.phone("Sam Pixel", SAM, "android")
    env.hub(**{CONF_PIN_ON_LOCK_SCREEN: True})
    parcel = env.parcel(S.OUT_FOR_DELIVERY, eta=window(13, 14), pickup_code="4826")
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    plain = f"Out for delivery 13:00{DASH}14:00{SEP}DPD"
    short = f"13{DASH}14h"
    assert iphone.take() == [activity(tag, "Amazon", plain, short, 3, OUT, 0.9)]
    env.token(iphone, tag)
    await env.goto(at(8) + timedelta(seconds=5))
    shown = f"Out for delivery\nPIN 4826{SEP}13:00{DASH}14:00{SEP}DPD"
    assert iphone.take() == [
        pinned(activity(tag, "Amazon", shown, short, 3, OUT, 0.9, silent=True), iphone)
    ]

    # The last hour's timer would replace the text, PIN included.
    await env.goto(at(13))
    assert iphone.take() == [
        pinned(activity(tag, "Amazon", shown, short, 3, OUT, 1.0, silent=True), iphone)
    ]

    await env.goto(at(13, 40))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    delivered = f"Delivered {CHECK} 13:40{SEP}DPD"
    assert iphone.take() == [
        activity(tag, "Amazon", delivered, f"{CHECK} 13:40", 4, DONE, 0.2)
    ]
    await env.goto(at(14, 15))
    assert iphone.take() == [end(tag)]
    assert (
        summary(ipad.take())
        == summary(android.take())
        == [(tag, plain), (tag, delivered)]
    )
    assert "Amazon" in str(persistent(hass))
    assert "4826" not in str(persistent(hass))


async def test_pickup_code_follows_the_alert(env: Env) -> None:
    """A pickup code comes in a quiet update after the alert of the new status.

    A private parcel's code shows only on its owner's iPhone.
    """
    alex = env.phone("Alex iPhone", ALEX)
    sam = env.phone("Sam iPhone", SAM)
    env.hub(**{CONF_PIN_ON_LOCK_SCREEN: True})
    parcel = env.parcel(
        eta=on(), merchant="Decathlon", carrier="ctt", owners=(ALEX,), private=True
    )
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    assert alex.take() == [
        activity(tag, "Decathlon", f"Expected today{SEP}CTT", "Today", 2, TRUCK, 0.5)
    ]
    env.token(alex, tag)

    await env.goto(at(10, 15))
    env.change(
        parcel,
        S.READY_FOR_PICKUP,
        sent=at(10, 15),
        pickup_point="Locker 12, Rua Inventada 7",
        pickup_code="59031",
        collect_by=date(2026, 6, 24),
    )
    await env.settle()
    ready = f"Ready at Locker 12{SEP}collect by Wed 24{SEP}CTT"
    assert alex.take() == [activity(tag, "Decathlon", ready, "Pickup", 3, SHOP, 0.7)]

    await env.goto(at(10, 16))
    shown = f"Ready for pickup\nPIN 59031{SEP}Locker 12{SEP}collect by Wed 24{SEP}CTT"
    assert alex.take() == [
        pinned(
            activity(tag, "Decathlon", shown, "Pickup", 3, SHOP, 0.7, silent=True),
            alex,
        )
    ]
    assert sam.calls == []


async def test_pickup_code_stays_at_the_pickup_point(
    env: Env, hass: HomeAssistant
) -> None:
    """Taken from its locker back to delivery, a parcel shows no locker code.

    The locker's code would read as the PIN of the new delivery.
    """
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    env.hub(**{CONF_PIN_ON_LOCK_SCREEN: True})
    parcel = env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    assert len(iphone.take()) == 1
    assert ipad.take() == []
    env.token(iphone, tag)

    await env.goto(at(10, 15))
    env.change(
        parcel,
        S.READY_FOR_PICKUP,
        sent=at(10, 15),
        pickup_point="Locker 12, Rua Inventada 7",
        pickup_code="731905",
        collect_by=date(2026, 6, 24),
    )
    await env.settle()
    await env.goto(at(10, 16))
    assert [payload["message"] for payload in iphone.take()] == [
        f"Ready at Locker 12{SEP}collect by Wed 24{SEP}CTT",
        f"Ready for pickup\nPIN 731905{SEP}Locker 12{SEP}collect by Wed 24{SEP}CTT",
    ]
    assert len(ipad.take()) == 1

    await env.goto(at(11))
    env.change(
        parcel, S.OUT_FOR_DELIVERY, sent=at(11), eta=window(16, 19), label="ctt.pt"
    )
    await env.settle()
    out = f"Out for delivery 16:00{DASH}19:00{SEP}CTT"
    short = f"16{DASH}19h"
    assert iphone.take() == [activity(tag, "Decathlon", out, short, 3, OUT, 0.9)]
    assert summary(ipad.take()) == [(tag, out)]
    await env.goto(at(11, 5))
    assert iphone.take() == []
    shown = str(persistent(hass))
    assert f"- Decathlon{SEP}CTT{SEP}Out for delivery 16:00{DASH}19:00" in shown
    assert "Locker 12" not in shown
    assert "731905" not in shown


@pytest.mark.parametrize("status", [S.OUT_FOR_DELIVERY, S.READY_FOR_PICKUP])
async def test_a_parcel_taken_back_replaces_its_notification(
    env: Env, status: ParcelStatus
) -> None:
    """Taken back to transit, a parcel's notification says when it's expected.

    iPads and Android phones were told it was out for delivery, or ready for
    pickup; the carrier's newer news replaces that, with an alert as the
    iPhone's activity gives, and only once. Its next key news comes again.
    """
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    android = env.phone("Sam Pixel", SAM, "android")
    parcel = env.parcel(eta=window(14, 18), merchant="Decathlon", carrier="ctt")
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    assert len(iphone.take()) == 1
    env.token(iphone, tag)

    await env.goto(at(9))
    if status is S.OUT_FOR_DELIVERY:
        env.change(parcel, status, sent=at(9), eta=window(14, 18), label="ctt.pt")
        told = f"Out for delivery 14:00{DASH}18:00{SEP}CTT"
    else:
        env.change(
            parcel, status, sent=at(9), pickup_point="Locker 12, Rua Inventada 7"
        )
        told = f"Ready at Locker 12{SEP}CTT"
    await env.settle()
    assert summary(ipad.take()) == summary(android.take()) == [(tag, told)]
    assert len(iphone.take()) == 1

    await env.goto(at(11))
    tomorrow = on(DAY + timedelta(days=1))
    env.change(parcel, S.IN_TRANSIT, sent=at(11), eta=tomorrow, label="ctt.pt")
    await env.settle()
    back = f"Expected tomorrow{SEP}CTT"
    assert summary(iphone.take()) == [(tag, back)]
    assert ipad.take() == [
        {
            "title": "Decathlon",
            "message": back,
            "data": {"tag": tag, "url": link_of(parcel)},
        }
    ]
    assert android.take() == [
        {
            "title": "Decathlon",
            "message": back,
            "data": {
                "tag": tag,
                "clickAction": link_of(parcel),
                "notification_icon": TRUCK,
                "color": BLUE,
            },
        }
    ]
    env.changed()
    await env.goto(at(11, 10))
    assert ipad.take() == android.take() == []

    env.change(
        parcel, S.OUT_FOR_DELIVERY, sent=at(11, 10), eta=window(15, 19), label="ctt.pt"
    )
    await env.settle()
    again = [(tag, f"Out for delivery 15:00{DASH}19:00{SEP}CTT")]
    assert summary(ipad.take()) == summary(android.take()) == again


async def test_a_step_back_reversed_soon_after_is_quiet(env: Env) -> None:
    """A parcel flipping between two statuses alerts only for the first change.

    News that brings back, within 15 minutes, the status the parcel had just
    left updates the activity silently, and replaces the notifications of
    iPads and Android phones quietly. Later news alerts again.
    """
    iphone = env.phone("Alex iPhone", ALEX)
    ipad = env.phone("Alex iPad", ALEX, "ipad")
    android = env.phone("Sam Pixel", SAM, "android")
    parcel = env.parcel(eta=window(14, 18), merchant="Decathlon", carrier="ctt")
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    assert len(iphone.take()) == 1

    await env.goto(at(9))
    env.change(
        parcel, S.OUT_FOR_DELIVERY, sent=at(9), eta=window(14, 18), label="ctt.pt"
    )
    await env.settle()
    out = f"Out for delivery 14:00{DASH}18:00{SEP}CTT"
    assert summary(ipad.take()) == summary(android.take()) == [(tag, out)]
    (update,) = iphone.take()
    assert "silent" not in update["data"]

    await env.goto(at(11))
    tomorrow = on(DAY + timedelta(days=1))
    env.change(parcel, S.IN_TRANSIT, sent=at(11), eta=tomorrow, label="ctt.pt")
    await env.settle()
    back = f"Expected tomorrow{SEP}CTT"
    (update,) = iphone.take()
    assert summary([update]) == [(tag, back)]
    assert "silent" not in update["data"]
    assert ipad.take() == [
        {
            "title": "Decathlon",
            "message": back,
            "data": {"tag": tag, "url": link_of(parcel)},
        }
    ]
    assert android.take() == [
        {
            "title": "Decathlon",
            "message": back,
            "data": {
                "tag": tag,
                "clickAction": link_of(parcel),
                "notification_icon": TRUCK,
                "color": BLUE,
            },
        }
    ]

    await env.goto(at(11, 1))
    env.change(
        parcel, S.OUT_FOR_DELIVERY, sent=at(11, 1), eta=window(15, 19), label="ctt.pt"
    )
    await env.settle()
    out = f"Out for delivery 15:00{DASH}19:00{SEP}CTT"
    (update,) = iphone.take()
    assert summary([update]) == [(tag, out)]
    assert update["data"]["silent"] is True
    (notification,) = ipad.take()
    assert notification["message"] == out
    assert notification["data"]["push"] == {"interruption-level": "passive"}
    (notification,) = android.take()
    assert notification["message"] == out
    assert notification["data"]["alert_once"] is True

    await env.goto(at(11, 2))
    env.change(parcel, S.IN_TRANSIT, sent=at(11, 2), eta=tomorrow, label="ctt.pt")
    await env.settle()
    (update,) = iphone.take()
    assert summary([update]) == [(tag, back)]
    assert update["data"]["silent"] is True
    assert ipad.take() == [
        {
            "title": "Decathlon",
            "message": back,
            "data": {
                "tag": tag,
                "url": link_of(parcel),
                "push": {"interruption-level": "passive"},
            },
        }
    ]
    assert android.take() == [
        {
            "title": "Decathlon",
            "message": back,
            "data": {
                "tag": tag,
                "clickAction": link_of(parcel),
                "notification_icon": TRUCK,
                "color": BLUE,
                "alert_once": True,
            },
        }
    ]

    await env.goto(at(11, 20))
    env.change(
        parcel, S.OUT_FOR_DELIVERY, sent=at(11, 20), eta=window(16, 19), label="ctt.pt"
    )
    await env.settle()
    out = f"Out for delivery 16:00{DASH}19:00{SEP}CTT"
    (update,) = iphone.take()
    assert summary([update]) == [(tag, out)]
    assert "silent" not in update["data"]
    assert ipad.take() == [
        {
            "title": "Decathlon",
            "message": out,
            "data": {"tag": tag, "url": link_of(parcel)},
        }
    ]
    (notification,) = android.take()
    assert notification["message"] == out
    assert "alert_once" not in notification["data"]


async def test_a_step_back_reversed_soon_after_is_quiet_when_shared(
    env: Env,
) -> None:
    """A shared activity changes silently for a parcel flipping back.

    It alerts when another parcel has news at the same time.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    parcel = env.parcel(eta=window(14, 18), merchant="Decathlon", carrier="ctt")
    other = env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert [payload["data"]["tag"] for payload in phone.take()] == [COMBINED]

    await env.goto(at(9))
    env.change(
        parcel, S.OUT_FOR_DELIVERY, sent=at(9), eta=window(14, 18), label="ctt.pt"
    )
    await env.settle()
    (update,) = phone.take()
    assert "silent" not in update["data"]

    await env.goto(at(11))
    tomorrow = on(DAY + timedelta(days=1))
    env.change(parcel, S.IN_TRANSIT, sent=at(11), eta=tomorrow, label="ctt.pt")
    await env.settle()
    (update,) = phone.take()
    assert "silent" not in update["data"]
    assert update["message"].startswith("0 of 1 delivered")

    await env.goto(at(11, 1))
    env.change(
        parcel, S.OUT_FOR_DELIVERY, sent=at(11, 1), eta=window(15, 19), label="ctt.pt"
    )
    await env.settle()
    (update,) = phone.take()
    assert update["message"].startswith("0 of 2 delivered")
    assert update["data"]["silent"] is True

    await env.goto(at(11, 5))
    env.change(parcel, S.IN_TRANSIT, sent=at(11, 5), eta=tomorrow, label="ctt.pt")
    env.change(
        other, S.OUT_FOR_DELIVERY, sent=at(11, 5), eta=window(12, 14), label="ctt.pt"
    )
    await env.settle()
    (update,) = phone.take()
    assert update["message"].startswith("0 of 1 delivered")
    assert "silent" not in update["data"]


async def test_pin_waits_until_the_activity_can_be_updated(env: Env) -> None:
    """A PIN waits for the token of the running activity, and starts none.

    Without a token, or with one about to expire, the push would start an
    activity with an alert that shows the PIN. Restarts before Apple's 8
    hours run out are plain too.
    """
    env.auto_token = False
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_PIN_ON_LOCK_SCREEN: True})
    parcel = env.parcel(S.OUT_FOR_DELIVERY, eta=on(), pickup_code="4826")
    await env.start()
    await env.goto(at(8))
    plain = f"Out for delivery{SEP}DPD"
    assert phone.take() == [
        activity(tag_of(parcel), "Amazon", plain, "Today", 3, OUT, 0.9)
    ]

    # Asked again after 5 s, 20 s and 80 s.
    await env.goto(at(8) + timedelta(seconds=5))
    env.token(phone, tag_of(parcel), expires=at(8, 1) + timedelta(seconds=10))
    await env.goto(at(8) + timedelta(seconds=20))
    assert phone.take() == []
    env.token(phone, tag_of(parcel))
    await env.goto(at(8, 1) + timedelta(seconds=20))
    shown = f"Out for delivery\nPIN 4826{SEP}DPD"
    assert phone.take() == [
        pinned(
            activity(
                tag_of(parcel), "Amazon", shown, "Today", 3, OUT, 0.9, silent=True
            ),
            phone,
        )
    ]

    await env.goto(at(15, 30))
    assert phone.take() == [
        end(tag_of(parcel)),
        activity(tag_of(parcel, 2), "Amazon", plain, "Today", 3, OUT, 0.9),
    ]
    env.token(phone, tag_of(parcel, 2))
    await env.goto(at(15, 30) + timedelta(seconds=5))
    assert phone.take() == [
        pinned(
            activity(
                tag_of(parcel, 2), "Amazon", shown, "Today", 3, OUT, 0.9, silent=True
            ),
            phone,
        )
    ]


@pytest.mark.parametrize("started", [False, True])
async def test_a_new_pin_wait_starts_the_cadence_again(env: Env, started: bool) -> None:
    """Each PIN that starts waiting is asked again after 5 s.

    An iPhone that never sends its activity's token is asked only every 5
    minutes after a while. Another delivery's PIN doesn't wait as long,
    whether its activity starts now or turns out for delivery.
    """
    env.auto_token = False
    alex = env.phone("Alex iPhone", ALEX)
    sam = env.phone("Sam iPhone", SAM)
    env.hub(**{CONF_PIN_ON_LOCK_SCREEN: True})
    env.parcel(
        S.OUT_FOR_DELIVERY, eta=on(), pickup_code="4826", owners=(ALEX,), private=True
    )
    parcel = env.parcel(
        eta=on() if started else None,
        merchant="Zalando",
        owners=(SAM,),
        private=True,
    )
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    assert len(alex.take()) == 1
    assert len(sam.take()) == int(started)
    if started:
        env.token(sam, tag)
    for seconds in (5, 20, 80, 380, 680):
        await env.goto(at(8) + timedelta(seconds=seconds))
    assert alex.take() == []

    await env.goto(at(8, 15))
    env.change(parcel, S.OUT_FOR_DELIVERY, sent=at(8, 15), pickup_code="59031")
    await env.settle()
    assert summary(sam.take()) == [(tag, f"Out for delivery{SEP}DPD")]
    env.token(sam, tag)
    await env.goto(dt_util.utcnow() + timedelta(seconds=5))
    assert summary(sam.take()) == [(tag, f"Out for delivery\nPIN 59031{SEP}DPD")]
    assert alex.take() == []


async def test_a_failing_alert_is_tried_less_often(
    env: Env, hass: HomeAssistant
) -> None:
    """An alert that keeps failing isn't tried every few seconds.

    The PIN that waits for it follows soon after it goes through.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_PIN_ON_LOCK_SCREEN: True})
    parcel = env.parcel(eta=on())
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    env.token(phone, tag)

    phone.calls = async_mock_service(
        hass, "notify", phone.service, raise_exception=HomeAssistantError("down")
    )
    env.change(parcel, S.OUT_FOR_DELIVERY, sent=at(8), pickup_code="4826")
    await env.settle()
    first = dt_util.utcnow()
    for seconds in range(5, 125, 5):
        await env.goto(first + timedelta(seconds=seconds))
    # Tried at once, then after 5, 20 and 80 seconds.
    assert len(phone.take()) == 4

    phone.calls = async_mock_service(hass, "notify", phone.service)
    await env.goto(first + timedelta(minutes=7))
    assert summary(phone.take()) == [(tag, f"Out for delivery{SEP}DPD")]
    await env.goto(dt_util.utcnow() + timedelta(seconds=5))
    assert summary(phone.take()) == [(tag, f"Out for delivery\nPIN 4826{SEP}DPD")]


async def test_a_dismissed_activity_stays_ended(env: Env) -> None:
    """An activity the user dismissed isn't started again that day.

    Its token is gone, so the restart before Apple's 8 hours run out would
    start it again, with an alert.
    """
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    tag = tag_of(parcel)
    notifier = await env.start()
    await env.goto(at(8))
    assert summary(phone.take()) == [(tag, f"Expected today{SEP}DPD")]
    await env.goto(at(8, 10))
    env.untoken(phone, tag)

    await env.goto(at(15, 30))
    assert phone.take() == []
    await env.goto(at(22))
    assert phone.take() == []
    today = notifier.diagnostics()["today"]
    assert today["dismissed"] == 1
    assert today["activity_starts"] == 1


async def test_updates_wait_for_the_token_of_a_new_activity(env: Env) -> None:
    """Updates right after a start wait for the iPhone to send its token.

    Sent before it, each would start a second activity with the same tag.
    They go as one quiet update once the token is there.
    """
    env.auto_token = False
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    tag = tag_of(parcel)
    notifier = await env.start()
    await env.goto(at(8))
    assert summary(phone.take()) == [(tag, f"Expected today{SEP}DPD")]

    env.change(parcel, eta=window(13, 14))
    await env.settle()
    env.change(parcel, eta=window(14, 15))
    await env.settle()
    assert phone.take() == []
    assert notifier.diagnostics()["today"]["waiting_for_token"] == 1

    env.token(phone, tag)
    await env.goto(at(8, 10))
    assert phone.take() == [
        activity(
            tag,
            "Amazon",
            f"Expected today 14:00{DASH}15:00{SEP}DPD",
            f"14{DASH}15h",
            2,
            TRUCK,
            0.5,
            silent=True,
        )
    ]
    assert notifier.diagnostics()["today"]["waiting_for_token"] == 0


@pytest.mark.parametrize("threshold", [1, 9])
async def test_news_after_a_dismissal_comes_as_notifications(
    env: Env, threshold: int
) -> None:
    """After the user dismisses an activity, key news comes as notifications.

    As on an iPad, each key status comes once, and other changes, an
    inferred delivery included, send nothing. Combined activities too.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: threshold})
    parcel = env.parcel(eta=on())
    other = env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    notifier = await env.start()
    await env.goto(at(8))
    started = phone.take()
    assert len(started) == (1 if threshold == 1 else 2)
    await env.goto(at(8, 10))
    for payload in started:
        env.untoken(phone, payload["data"]["tag"])

    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    assert phone.take() == [
        {
            "title": "Amazon",
            "message": f"Out for delivery{SEP}DPD",
            "data": {"tag": news_tag(parcel), "url": link_of(parcel)},
        }
    ]

    env.change(other, eta=window(15, 16))
    env.infer(other)
    await env.settle()
    assert phone.take() == []

    await env.goto(at(13, 40))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        {
            "title": "Amazon",
            "message": f"Delivered {CHECK} 13:40{SEP}DPD",
            "data": {"tag": news_tag(parcel), "url": link_of(parcel)},
        }
    ]
    env.changed()
    await env.settle()
    assert phone.take() == []
    today = notifier.diagnostics()["today"]
    assert today["activity_starts"] == len(started)
    assert today["running"] == 0


@pytest.mark.parametrize("when", ["today", "tomorrow"])
@pytest.mark.parametrize("threshold", [1, 9])
async def test_news_notification_replaced_when_taken_back(
    env: Env, threshold: int, when: str
) -> None:
    """After a dismissal, a parcel taken back from out for delivery says so.

    The notification that said it was out for delivery is replaced once, also
    when the parcel moved to tomorrow, as on an iPad.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: threshold})
    parcel = env.parcel(eta=window(14, 18), merchant="Decathlon", carrier="ctt")
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    notifier = await env.start()
    await env.goto(at(8))
    started = phone.take()
    assert len(started) == (1 if threshold == 1 else 2)
    await env.goto(at(8, 10))
    for payload in started:
        env.untoken(phone, payload["data"]["tag"])

    env.change(
        parcel, S.OUT_FOR_DELIVERY, sent=at(8, 10), eta=window(14, 18), label="ctt.pt"
    )
    await env.settle()
    out = f"Out for delivery 14:00{DASH}18:00{SEP}CTT"
    assert summary(phone.take()) == [(news_tag(parcel), out)]

    await env.goto(at(11))
    if when == "today":
        eta, back = window(15, 17), f"Expected today 15:00{DASH}17:00{SEP}CTT"
    else:
        eta, back = on(DAY + timedelta(days=1)), f"Expected tomorrow{SEP}CTT"
    env.change(parcel, S.IN_TRANSIT, sent=at(11), eta=eta, label="ctt.pt")
    await env.settle()
    assert phone.take() == [
        {
            "title": "Decathlon",
            "message": back,
            "data": {"tag": news_tag(parcel), "url": link_of(parcel)},
        }
    ]
    env.changed()
    await env.goto(at(11, 10))
    assert phone.take() == []
    assert notifier.diagnostics()["today"]["activity_starts"] == len(started)


@pytest.mark.parametrize("threshold", [1, 9])
async def test_news_of_a_parcel_moved_after_a_dismissal(
    env: Env, threshold: int
) -> None:
    """A missed parcel moved to tomorrow still comes as a notification.

    After the user dismissed its activity, as on an iPad.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: threshold})
    parcel = env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    started = phone.take()
    await env.goto(at(8, 10))
    for payload in started:
        env.untoken(phone, payload["data"]["tag"])

    await env.goto(at(12, 30))
    env.change(parcel, S.ATTEMPTED, eta=on(DAY + timedelta(days=1)))
    await env.settle()
    assert summary(phone.take()) == [
        (news_tag(parcel), f"Missed 12:30{SEP}Expected tomorrow{SEP}CTT")
    ]
    env.changed()
    await env.settle()
    assert phone.take() == []


async def test_shown_news_of_a_moved_parcel_is_not_sent_after_a_dismissal(
    env: Env,
) -> None:
    """A dismissed shared activity's news isn't sent again for a moved parcel.

    The activity showed the missed delivery; moving the parcel to tomorrow
    took it off, and the move alone isn't news.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    parcel = env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert [payload["data"]["tag"] for payload in phone.take()] == [COMBINED]

    await env.goto(at(12, 30))
    env.change(parcel, S.ATTEMPTED, sent=at(12, 30), label="ctt.pt")
    await env.settle()
    shown = phone.take()
    assert len(shown) == 1
    assert "1 problem" in shown[0]["message"]

    await env.goto(at(12, 40))
    tomorrow = on(DAY + timedelta(days=1))
    env.change(parcel, eta=tomorrow, sent=at(12, 40), label="ctt.pt")
    await env.settle()
    assert "problem" not in phone.take()[-1]["message"]

    await env.goto(at(13))
    env.untoken(phone, COMBINED)
    env.changed()
    await env.settle()
    assert phone.take() == []

    await env.goto(at(15))
    env.change(parcel, S.OUT_FOR_DELIVERY, sent=at(15), label="ctt.pt")
    await env.settle()
    assert summary(phone.take()) == [(news_tag(parcel), f"Out for delivery{SEP}CTT")]


async def test_news_shown_before_a_collapse_is_not_sent_after_a_dismissal(
    env: Env,
) -> None:
    """News a parcel's own activity showed isn't sent once a later one is dismissed.

    The parcel's activity showed the missed delivery and ended when the
    parcel moved to tomorrow; then the iPhone's activities collapsed into
    the shared one, which the user dismissed.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 2})
    parcel = env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 2

    await env.goto(at(12, 30))
    env.change(parcel, S.ATTEMPTED, sent=at(12, 30), label="ctt.pt")
    await env.settle()
    assert summary(phone.take()) == [
        (tag_of(parcel), f"Missed{SEP}reported 12:30{SEP}CTT")
    ]

    await env.goto(at(12, 40))
    tomorrow = on(DAY + timedelta(days=1))
    env.change(parcel, eta=tomorrow, sent=at(12, 40), label="ctt.pt")
    await env.settle()
    await env.goto(at(13, 11))
    assert phone.take()[-1] == end(tag_of(parcel))

    await env.goto(at(13, 20))
    env.parcel(eta=on(), merchant="IKEA", carrier="ctt")
    env.parcel(eta=on(), merchant="Etsy", carrier="ctt")
    env.changed()
    await env.settle()
    assert [payload["data"]["tag"] for payload in phone.take()][-1] == COMBINED

    await env.goto(at(13, 30))
    env.untoken(phone, COMBINED)
    env.changed()
    await env.settle()
    assert phone.take() == []


@pytest.mark.parametrize("how", ["switch", "recipient"])
async def test_a_dismissed_activity_comes_back_when_turned_on_again(
    env: Env, hass: HomeAssistant, how: str
) -> None:
    """Turning Live Activities back on, or notifying the iPhone again, starts it.

    Until then, updates don't start the activity the user dismissed.
    """
    phone = env.phone("Alex iPhone", ALEX)
    entry = env.hub()
    parcel = env.parcel(eta=on())
    notifier = await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    await env.goto(at(8, 10))
    env.untoken(phone, tag_of(parcel))
    env.change(parcel, eta=window(13, 14))
    await env.settle()
    assert phone.take() == []

    if how == "switch":
        await notifier.async_set_live_activities(False)
        assert phone.take() == []
        await notifier.async_set_live_activities(True)
    else:
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_NOTIFY_PERSONS: [SAM]}
        )
        env.changed()
        await env.settle()
        assert phone.take() == []
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_NOTIFY_PERSONS: [ALEX, SAM]}
        )
        env.changed()
        await env.settle()
    assert phone.take() == [
        activity(
            tag_of(parcel, 2),
            "Amazon",
            f"Expected today 13:00{DASH}14:00{SEP}DPD",
            f"13{DASH}14h",
            2,
            TRUCK,
            0.5,
        )
    ]


async def test_updates_go_on_when_tokens_cant_be_read(
    env: Env, hass: HomeAssistant
) -> None:
    """When what mobile_app keeps can't be read, activities update as before."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    hass.data["mobile_app"]["live_activity_tokens"] = []

    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    out = f"Out for delivery{SEP}DPD"
    assert phone.take() == [
        activity(tag_of(parcel), "Amazon", out, "Today", 3, OUT, 0.9)
    ]
    await env.goto(at(15, 30))
    assert phone.take() == [
        end(tag_of(parcel)),
        activity(tag_of(parcel, 2), "Amazon", out, "Today", 3, OUT, 0.9),
    ]


async def test_news_reaches_an_iphone_that_sends_no_token(env: Env) -> None:
    """Without the activity's token, key news comes as a notification.

    Updates wait for the token; 5 minutes after the start, news an iPad
    would get comes as a notification. Once the token comes, the activity
    catches up quietly.
    """
    env.auto_token = False
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    assert summary(phone.take()) == [(tag, f"Expected today{SEP}DPD")]

    await env.goto(at(8, 2))
    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    assert phone.take() == []
    await env.goto(at(8, 4))
    assert phone.take() == []

    await env.goto(at(8, 6))
    out = f"Out for delivery{SEP}DPD"
    assert phone.take() == [
        {
            "title": "Amazon",
            "message": out,
            "data": {"tag": news_tag(parcel), "url": link_of(parcel)},
        }
    ]

    env.token(phone, tag)
    await env.goto(at(8, 15))
    assert phone.take() == [
        activity(tag, "Amazon", out, "Today", 3, OUT, 0.9, silent=True)
    ]


@pytest.mark.parametrize("threshold", [1, 9])
async def test_news_of_a_moved_parcel_reaches_an_iphone_that_sends_no_token(
    env: Env, threshold: int
) -> None:
    """Without the activity's token, a parcel missed and moved to tomorrow says so.

    As for a parcel still expected today, also with a combined activity.
    """
    env.auto_token = False
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: threshold})
    parcel = env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == (1 if threshold == 1 else 2)

    await env.goto(at(8, 2))
    env.change(parcel, S.ATTEMPTED, eta=on(DAY + timedelta(days=1)))
    await env.settle()
    assert phone.take() == []

    await env.goto(at(8, 6))
    assert summary(phone.take()) == [
        (news_tag(parcel), f"Missed 08:02{SEP}Expected tomorrow{SEP}CTT")
    ]
    await env.goto(at(8, 10))
    assert phone.take() == []


async def test_activity_dismissed_before_an_upgrade(env: Env) -> None:
    """An activity stored by an older version, since dismissed, stays ended.

    It had shown a PIN, so its token had come: now it is gone. What it
    showed isn't notified again; later news is.
    """
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(S.OUT_FOR_DELIVERY, eta=on())
    await env.goto(at(9))
    record = {
        "tag": tag_of(parcel),
        "gen": 1,
        "title": "Amazon",
        "started": dt_util.as_utc(at(8)).isoformat(),
        "running": True,
        "end_reason": None,
        "end_at": None,
        "linger": None,
        "fp": "made-up",
        "status": "out_for_delivery",
        "service": phone.service,
        "pin": True,
        "plain": "made-up-plain",
    }
    env.host.data.engine[STATE_KEY] = {
        "version": 1,
        "live_activities": True,
        "daily_notification": True,
        "days": {
            DAY.isoformat(): {
                "morning": True,
                "board": [parcel.id],
                "returns": [],
                "combined": [],
                "activities": {phone.device_id: {parcel.id: record}},
                "notified": {},
            }
        },
    }
    notifier = await env.start()
    assert phone.take() == []
    assert notifier.diagnostics()["today"]["dismissed"] == 1

    await env.goto(at(13, 40))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        {
            "title": "Amazon",
            "message": f"Delivered {CHECK} 13:40{SEP}DPD",
            "data": {"tag": news_tag(parcel), "url": link_of(parcel)},
        }
    ]


async def test_an_activity_dismissed_right_after_its_start_stays_ended(
    env: Env,
) -> None:
    """An activity the user dismissed before any update stays ended.

    Its token came with the start, so its going is the user's doing.
    """
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    tag = tag_of(parcel)
    notifier = await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    env.untoken(phone, tag)
    assert notifier.diagnostics()["today"]["waiting_for_token"] == 0

    await env.goto(at(15, 30))
    assert phone.take() == []
    assert notifier.diagnostics()["today"]["dismissed"] == 1


async def test_a_token_that_comes_after_the_start_then_goes_is_a_dismissal(
    env: Env,
) -> None:
    """A token the iPhone sends seconds after the start, then forgets, ends it.

    Parcels looks for the token soon after the start; from then on, its
    going means the user dismissed the activity.
    """
    env.auto_token = False
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    tag = tag_of(parcel)
    notifier = await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    env.token(phone, tag)
    await env.goto(at(8) + timedelta(seconds=5))
    assert phone.take() == []

    env.untoken(phone, tag)
    assert notifier.diagnostics()["today"]["waiting_for_token"] == 0
    await env.goto(at(15, 30))
    assert phone.take() == []
    today = notifier.diagnostics()["today"]
    assert today["dismissed"] == 1
    assert today["activity_starts"] == 1


async def test_news_an_update_showed_isnt_notified_after_a_dismissal(
    env: Env,
) -> None:
    """News the activity already showed isn't notified once it is dismissed."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    assert summary(phone.take()) == [(tag, f"Out for delivery{SEP}DPD")]

    env.untoken(phone, tag)
    env.changed()
    await env.settle()
    assert phone.take() == []


@pytest.mark.parametrize("threshold", [1, 9])
async def test_a_guessed_delivery_is_notified_once_confirmed(
    env: Env, threshold: int
) -> None:
    """A delivery the activity showed only as a guess is news after a dismissal.

    Inferred from another package of the shipment, it showed quietly; once
    the user has dismissed the activity, the carrier's word comes as a
    notification.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: threshold})
    parcel = env.parcel(S.OUT_FOR_DELIVERY, eta=on())
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    started = phone.take()
    assert len(started) == (1 if threshold == 1 else 2)

    await env.goto(at(13))
    env.infer(parcel)
    await env.settle()
    assert [payload["data"].get("silent") for payload in phone.take()] == [True]
    for payload in started:
        env.untoken(phone, payload["data"]["tag"])

    await env.goto(at(13, 10))
    env.change(parcel, S.DELIVERED)
    await env.settle()
    assert phone.take() == [
        {
            "title": "Amazon",
            "message": f"Delivered {CHECK} 13:10{SEP}DPD",
            "data": {"tag": news_tag(parcel), "url": link_of(parcel)},
        }
    ]


@pytest.mark.parametrize("restart", [False, True])
async def test_a_combined_activity_remembers_what_it_showed(
    env: Env, restart: bool
) -> None:
    """News the day's activity showed isn't notified once it is dismissed.

    What it showed is kept across a restart of Home Assistant.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1})
    env.parcel(S.OUT_FOR_DELIVERY, eta=on())
    env.parcel(eta=on(), merchant="Zalando", carrier="ctt")
    await env.start()
    await env.goto(at(8))
    assert [payload["data"]["tag"] for payload in phone.take()] == [COMBINED]
    if restart:
        await env.restart()
        assert phone.take() == []

    env.untoken(phone, COMBINED)
    env.changed()
    await env.settle()
    assert phone.take() == []


async def test_news_after_a_dismissal_names_what_a_package_may_hold(
    env: Env,
) -> None:
    """News of a package of the day's activity names the orders it may hold.

    Once the user has dismissed the day's activity, as the package's own
    activity would.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_ITEM_NAMES: True, CONF_COLLAPSE_THRESHOLD: 1})
    box = env.parcel(eta=on(), carrier="ctt")
    env.parcel(eta=on(), carrier=None, items=("Desk lamp",))
    env.parcel(eta=on(), carrier=None, items=("Blue scarf", "Wool hat"))
    env.parcel(eta=on(), merchant="Zalando", carrier="gls")
    await env.start()
    await env.goto(at(8))
    assert [payload["data"]["tag"] for payload in phone.take()] == [COMBINED]
    await env.goto(at(8, 10))
    env.untoken(phone, COMBINED)

    await env.goto(at(10, 42))
    env.change(box, S.DELIVERED)
    await env.settle()
    possibly = f"CTT{SEP}Possibly: Desk lamp (+2){SEP}may hold 2 Amazon orders"
    assert phone.take() == [
        {
            "title": "Amazon",
            "message": f"Delivered {CHECK} 10:42{SEP}{possibly}",
            "data": {"tag": news_tag(box), "url": link_of(box)},
        }
    ]


async def test_an_activity_whose_token_never_came_is_restarted(env: Env) -> None:
    """An activity the iPhone sent no token for is restarted before 8 hours.

    Nothing says the user dismissed it.
    """
    env.auto_token = False
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1

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


async def test_a_token_gone_after_apples_limit_isnt_a_dismissal(env: Env) -> None:
    """After Apple's 8 hours, a gone token doesn't mean the user dismissed it.

    Apple ended the activity. When Home Assistant was down at its restart
    time, it starts again once Home Assistant is back.
    """
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    tag = tag_of(parcel)
    notifier = await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    await notifier.async_stop()

    env.freezer.move_to(at(16, 10))
    env.untoken(phone, tag)
    env.host.data.engine = json.loads(json.dumps(env.host.data.engine))
    await env.start()
    assert phone.take() == [
        end(tag),
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


async def test_turning_live_activities_on_again_revives_only_dismissed_ones(
    env: Env,
) -> None:
    """Turning Live Activities off and on doesn't bring back other ended ones.

    An activity that ended as its parcel moved to another day stays ended
    when the parcel comes back to today, as it would without the switch.
    """
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    notifier = await env.start()
    await env.goto(at(8))
    env.change(parcel, eta=on(NEXT_DAY))
    await env.settle()
    await env.goto(at(9))
    assert phone.take()[-1] == end(tag_of(parcel))

    await notifier.async_set_live_activities(False)
    await notifier.async_set_live_activities(True)
    assert phone.take() == []
    env.change(parcel, eta=window(13, 14))
    await env.settle()
    assert phone.take() == []


async def test_news_as_an_activity_restarts_shows_on_the_new_one(env: Env) -> None:
    """News that comes as the activity restarts shows on the new activity.

    It isn't notified as well: only a dismissed activity's news is.
    """
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1

    env.freezer.move_to(at(15, 30))
    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    out = f"Out for delivery{SEP}DPD"
    assert phone.take() == [
        end(tag_of(parcel)),
        activity(tag_of(parcel, 2), "Amazon", out, "Today", 3, OUT, 0.9),
    ]


async def test_unreadable_tokens_bring_no_notifications(
    env: Env, hass: HomeAssistant
) -> None:
    """When tokens can't be read, news comes only on the activity.

    Not as a notification too, even when its update fails: it is tried again.
    """
    hass.data["mobile_app"]["live_activity_tokens"] = []
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    await env.goto(at(8, 10))
    assert phone.take() == []

    phone.calls = async_mock_service(
        hass, "notify", phone.service, raise_exception=HomeAssistantError("down")
    )
    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    out = f"Out for delivery{SEP}DPD"
    assert summary(phone.take()) == [(tag, out)]

    phone.calls = async_mock_service(hass, "notify", phone.service)
    await env.goto(dt_util.utcnow() + timedelta(minutes=5))
    assert summary(phone.take()) == [(tag, out)]


async def test_news_that_cant_be_notified_after_a_dismissal_is_retried(
    env: Env, hass: HomeAssistant
) -> None:
    """News that can't be notified is tried again 5 minutes later."""
    phone = env.phone("Alex iPhone", ALEX)
    parcel = env.parcel(eta=on())
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    await env.goto(at(8, 10))
    env.untoken(phone, tag_of(parcel))
    env.changed()
    await env.settle()
    assert phone.take() == []

    phone.calls = async_mock_service(
        hass, "notify", phone.service, raise_exception=HomeAssistantError("down")
    )
    env.change(parcel, S.OUT_FOR_DELIVERY)
    await env.settle()
    assert len(phone.take()) == 1

    phone.calls = async_mock_service(hass, "notify", phone.service)
    await env.goto(dt_util.utcnow() + timedelta(minutes=5))
    assert phone.take() == [
        {
            "title": "Amazon",
            "message": f"Out for delivery{SEP}DPD",
            "data": {"tag": news_tag(parcel), "url": link_of(parcel)},
        }
    ]


async def test_pin_leaves_no_trace(
    env: Env, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A PIN goes straight to the iPhone's push and is kept nowhere.

    A notify service call would put it in an event, which the recorder and
    the logbook keep. Logs, the stored state and the diagnostics don't have
    it either.
    """
    caplog.set_level(logging.DEBUG)
    events = async_capture_events(hass, MATCH_ALL)
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_PIN_ON_LOCK_SCREEN: True})
    parcel = env.parcel(S.OUT_FOR_DELIVERY, eta=on(), pickup_code="4826")
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    env.token(phone, tag_of(parcel))
    await env.goto(at(8, 1))
    assert summary(phone.take()) == [
        (tag_of(parcel), f"Out for delivery\nPIN 4826{SEP}DPD")
    ]
    notifier = await env.restart()
    await env.goto(at(8, 30))
    assert phone.take() == []

    assert events
    for event in events:
        assert "4826" not in json.dumps(event.as_dict(), default=str)
    assert "4826" not in caplog.text
    # Fingerprints are keyed hashes, which can't be checked against guesses.
    stored = json.dumps(env.host.data.engine)
    assert "4826" not in re.sub(r'"[0-9a-f]{16}"', '""', stored)
    diagnostics = notifier.diagnostics()
    assert diagnostics["pin_on_lock_screen"] is True
    assert diagnostics["today"]["showing_pin"] == 1
    assert "4826" not in json.dumps(diagnostics)


@pytest.mark.parametrize(
    "fault", ["no mobile_app", "no push target", "no app entry", "no expiry", "error"]
)
async def test_pin_fails_closed(
    env: Env, hass: HomeAssistant, caplog: pytest.LogCaptureFixture, fault: str
) -> None:
    """Without proof that the activity can be updated, no PIN is pushed.

    A failed push is retried later, and its error isn't logged.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_PIN_ON_LOCK_SCREEN: True})
    parcel = env.parcel(S.OUT_FOR_DELIVERY, eta=on(), pickup_code="4826")
    tag = tag_of(parcel)
    await env.start()
    await env.goto(at(8))
    assert len(phone.take()) == 1
    env.token(phone, tag)
    mobile_app = hass.data["mobile_app"]
    app_entry = env.entries[phone.webhook_id]
    if fault == "no mobile_app":
        del hass.data["mobile_app"]
    elif fault == "no push target":
        del env.push.phones[phone.webhook_id]
    elif fault == "no app entry":
        del env.entries[phone.webhook_id]
    elif fault == "no expiry":
        del env.tokens[phone.webhook_id][tag]["expires_at"]
    else:
        phone.error = HomeAssistantError("PIN 4826")
    await env.goto(at(8, 10))
    assert phone.take() == []
    assert "4826" not in caplog.text
    if fault == "error":
        assert "Notifying a device (iphone) failed: HomeAssistantError" in caplog.text

    hass.data["mobile_app"] = mobile_app
    env.push.phones[phone.webhook_id] = phone
    env.entries[phone.webhook_id] = app_entry
    env.token(phone, tag)
    phone.error = None
    await env.goto(at(8, 20))
    assert summary(phone.take()) == [(tag, f"Out for delivery\nPIN 4826{SEP}DPD")]


async def test_combined_activity_shows_the_next_pin(env: Env) -> None:
    """The combined activity shows the PIN of the delivery it names next.

    Without one, the code of its one parcel ready for pickup, with the place.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1, CONF_PIN_ON_LOCK_SCREEN: True})
    moving = env.parcel(
        S.OUT_FOR_DELIVERY,
        eta=window(13, 15),
        merchant="Zalando",
        carrier="ctt",
        pickup_code="4826",
    )
    pickup = env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    env.parcel(eta=window(16, 18), merchant="IKEA", carrier="dpd")
    await env.start()
    await env.goto(at(8))
    next_up = f"next: Zalando via CTT 13{DASH}15h"
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 3 delivered{SEP}{next_up}",
            "0/3",
            0,
            OUT,
            0.9,
            progress_max=3,
        )
    ]
    env.token(phone, COMBINED)
    await env.goto(at(8) + timedelta(seconds=5))
    assert phone.take() == [
        pinned(
            activity(
                COMBINED,
                "Parcels today",
                f"0 of 3 delivered\nPIN 4826{SEP}{next_up}",
                "0/3",
                0,
                OUT,
                0.9,
                progress_max=3,
                silent=True,
            ),
            phone,
        )
    ]

    await env.goto(at(10))
    env.change(
        pickup,
        S.READY_FOR_PICKUP,
        sent=at(10),
        pickup_point="Locker 12",
        pickup_code="59031",
    )
    await env.settle()
    assert summary(phone.take()) == [
        (COMBINED, f"0 of 3 delivered{SEP}1 ready for pickup{SEP}{next_up}")
    ]
    await env.goto(at(10, 1))
    assert phone.take() == [
        pinned(
            activity(
                COMBINED,
                "Parcels today",
                f"0 of 3 delivered\nPIN 4826{SEP}{next_up}{SEP}1 ready for pickup",
                "0/3",
                0,
                OUT,
                0.9,
                progress_max=3,
                silent=True,
            ),
            phone,
        )
    ]

    # The next delivery has no PIN, so the one pickup code shows.
    await env.goto(at(11))
    env.change(moving, S.DELIVERED)
    await env.settle()
    await env.goto(at(11, 10))
    after = f"next: IKEA via DPD 16{DASH}18h"
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"1 of 3 delivered{SEP}1 ready for pickup{SEP}{after}",
            "1/3",
            1,
            SHOP,
            0.7,
            progress_max=3,
        ),
        pinned(
            activity(
                COMBINED,
                "Parcels today",
                f"1 of 3 delivered\nPIN 59031{SEP}Locker 12{SEP}{after}"
                f"{SEP}1 ready for pickup",
                "1/3",
                1,
                SHOP,
                0.7,
                progress_max=3,
                silent=True,
            ),
            phone,
        ),
    ]


async def test_combined_activity_shows_one_pickup_code(env: Env) -> None:
    """A pickup code shows only while one parcel of the day waits for pickup.

    With two waiting, neither code shows, even when only one has a code.
    """
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_COLLAPSE_THRESHOLD: 1, CONF_PIN_ON_LOCK_SCREEN: True})
    env.parcel(
        S.OUT_FOR_DELIVERY, eta=window(13, 15), merchant="Zalando", carrier="ctt"
    )
    first = env.parcel(eta=on(), merchant="Decathlon", carrier="ctt")
    second = env.parcel(eta=on(), merchant="IKEA", carrier="dpd")
    await env.start()
    await env.goto(at(8))
    phone.take()
    env.token(phone, COMBINED)
    next_up = f"next: Zalando via CTT 13{DASH}15h"

    await env.goto(at(9))
    env.change(
        first,
        S.READY_FOR_PICKUP,
        sent=at(9),
        pickup_point="Locker 12, Rua Inventada 7",
        pickup_code="59031",
    )
    await env.settle()
    await env.goto(at(9, 1))
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 3 delivered{SEP}1 ready for pickup{SEP}{next_up}",
            "0/3",
            0,
            OUT,
            0.9,
            progress_max=3,
        ),
        pinned(
            activity(
                COMBINED,
                "Parcels today",
                f"0 of 3 delivered\nPIN 59031{SEP}Locker 12{SEP}{next_up}"
                f"{SEP}1 ready for pickup",
                "0/3",
                0,
                OUT,
                0.9,
                progress_max=3,
                silent=True,
            ),
            phone,
        ),
    ]

    await env.goto(at(10))
    env.change(second, S.READY_FOR_PICKUP, sent=at(10), pickup_point="Shop 7")
    await env.settle()
    await env.goto(at(10, 1))
    assert phone.take() == [
        activity(
            COMBINED,
            "Parcels today",
            f"0 of 3 delivered{SEP}2 ready for pickup{SEP}{next_up}",
            "0/3",
            0,
            OUT,
            0.9,
            progress_max=3,
        )
    ]


async def test_test_live_activity_shows_a_made_up_pin(env: Env) -> None:
    """With the option on, the demo shows a made-up PIN, for two minutes."""
    phone = env.phone("Alex iPhone", ALEX)
    env.hub(**{CONF_PIN_ON_LOCK_SCREEN: True})
    notifier = await env.start()
    await notifier.async_test_live_activity()
    assert phone.take() == [
        activity(
            "parcels-test",
            "Parcels",
            f"Test{SEP}Out for delivery 13:00{DASH}14:00",
            "Test",
            3,
            OUT,
            0.5,
            when=at(7, 2),
        )
    ]
    env.token(phone, "parcels-test")
    await env.goto(at(7) + timedelta(seconds=5))
    assert phone.take() == [
        pinned(
            activity(
                "parcels-test",
                "Parcels",
                f"Test{SEP}Out for delivery\nPIN 4826{SEP}13:00{DASH}14:00",
                "Test",
                3,
                OUT,
                0.5,
                silent=True,
            ),
            phone,
        )
    ]
    await env.goto(at(7, 2))
    assert phone.take() == [end("parcels-test")]


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
            DAY.isoformat(): {
                "board": "p_1",
                "activities": {"x": {"tag": 1}},
                "returns": 5,
            },
        },
        "test": {"device": 5},
    }
    notifier = await env.start()
    assert notifier.live_activities_enabled
    assert "test" not in env.host.data.engine[STATE_KEY]
    await env.goto(at(8))
    assert summary(phone.take()) == [(tag_of(parcel), f"Expected today{SEP}DPD")]


async def test_no_deprecated_api(
    env: Env, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Setting up the hub and notifying a delivery day use no deprecated API."""
    # The day of the e-mail: DPD delivers today from 13:00 to 14:00.
    await env.goto(datetime(2026, 11, 17, 8, 30, tzinfo=TZ))
    phone = env.phone("Alex iPhone", ALEX)
    add_hub(hass, **{CONF_NOTIFY_PERSONS: [ALEX]})
    add_mailbox(hass, owner=ALEX)
    client = FakeMailClient()
    client.add("carriers/dpd_predict_pt.eml")
    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        await env.settle()

    [parcel] = engine.data.parcels.values()
    assert phone.take() == [
        activity(
            tag_of(parcel),
            "Zalando",
            f"Out for delivery 13:00{DASH}14:00{SEP}DPD",
            f"13{DASH}14h",
            3,
            OUT,
            0.9,
        )
    ]
    assert "Zalando" in (persistent(hass) or "")
    # How Home Assistant reports deprecated usage: frame.report_usage, and the
    # deprecation helpers for constants, functions, classes and entity members.
    marks = (
        "Detected that custom integration",
        "Detected code that",
        "The deprecated ",
        " provides the deprecated ",
        " is deprecated. Please rename ",
    )
    messages = [record.getMessage() for record in caplog.records]
    assert [m for m in messages if any(mark in m for mark in marks)] == []
