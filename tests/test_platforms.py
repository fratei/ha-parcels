"""Tests for the entities of Parcels: sensors, binary sensors, calendar, switches.

Alex's mailbox holds shipping e-mails of one week. The clock is frozen at
15:00 on Tuesday 17 November 2026 in Lisbon, which is on UTC in November.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
import json
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.recorder.db_schema import StateAttributes
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_get_persistent_notifications,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from custom_components.parcels.ai_worker import STAT_KEYS
from custom_components.parcels.const import (
    CONF_INTERVAL_MINUTES,
    DOMAIN,
    PERSISTENT_NOTIFICATION_ID,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.dedup import apply_contribution
from custom_components.parcels.engine import ParcelsEngine, get_engine
from custom_components.parcels.mail.errors import (
    MailAuthError,
    MailError,
    MailServerError,
)
from custom_components.parcels.models import Parcel, ParcelsData
from custom_components.parcels.notifier import DEBOUNCE_COOLDOWN
from custom_components.parcels.parsers.base import Eta

from .common import (
    ADDRESS,
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    patch_mail_clients,
)
from .factories import contribution

FIXTURES = (
    "carriers/dpd_predict_pt.eml",
    "carriers/ctt_in_transit_pt.eml",
    "carriers/ctt_delivered_pt.eml",
    "carriers/ctt_locker_ready_pt.eml",
    "carriers/gls_tomorrow_it.eml",
    "shopify/shipped_en.eml",
)
# The tracking numbers in the e-mails.
ZALANDO = "05346718290412"  # DPD, out for delivery today from 13:00 to 14:00
WORTEN = "RR482915732PT"  # CTT, in transit, expected on Thursday
DELIVERED = "RL273849102PT"  # CTT, delivered at 11:42
LOCKER = "RH358201962PT"  # CTT, in a locker since 14:02
YOOX = "620417393016"  # GLS, expected tomorrow from 09:00 to 12:00
OUTFITTERS = "1Z999AA10123456784"  # UPS, shipped yesterday, expected Thursday
PICKUP_POINT = "Cacifo CTT Saldanha, Avenida Exemplo 1, 1050-001 Lisboa"
ITEMS = ("Merino Wool Beanie", "Waxed Cotton Jacket")

COUNTS = ("arriving_today", "in_transit", "ready_for_pickup", "delivered_today")
SWITCHES = ("switch.parcels_live_activities", "switch.parcels_daily_notification")
# The tests check the mailbox on demand: no scheduled check while they move the
# clock.
DAILY_CHECKS = {CONF_INTERVAL_MINUTES: 24 * 60}
# Longer than the cooldown of the coordinator's refresh debouncer.
DEBOUNCER_COOLDOWN = timedelta(seconds=11)


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Freeze the clock at 15:00 on Tuesday 17 November 2026, in Lisbon."""
    freezer.move_to("2026-11-17 15:00:00+00:00")
    await hass.config.async_set_time_zone("Europe/Lisbon")


@pytest.fixture
def client() -> FakeMailClient:
    """Return Alex's mailbox with the shipping e-mails of the week."""
    client = FakeMailClient()
    for fixture in FIXTURES:
        client.add(fixture)
    return client


@pytest.fixture
def mailbox(hass: HomeAssistant) -> MockConfigEntry:
    """Add the hub and Alex's mailbox; return the mailbox entry."""
    add_hub(hass)
    return add_mailbox(hass, **DAILY_CHECKS)


@pytest.fixture
async def engine(
    hass: HomeAssistant, client: FakeMailClient, mailbox: MockConfigEntry
) -> AsyncGenerator[ParcelsEngine]:
    """Load the entries and read Alex's e-mails."""
    with patch_mail_clients(client):
        yield await async_setup_parcels(hass)


def get(hass: HomeAssistant, entity_id: str) -> State:
    """Return the state of an entity that must exist."""
    state = hass.states.get(entity_id)
    assert state is not None, entity_id
    return state


def parcel_with(engine: ParcelsEngine, number: str) -> Parcel:
    """Return the parcel with a tracking number."""
    return next(
        parcel
        for parcel in engine.data.parcels.values()
        if parcel.state.tracking_number == number
    )


def listed(hass: HomeAssistant) -> dict[str, list[str | None]]:
    """Return the tracking numbers each count sensor lists, in order."""
    result: dict[str, list[str | None]] = {}
    for key in COUNTS:
        state = get(hass, f"sensor.parcels_{key}")
        numbers = [p.get("tracking_number") for p in state.attributes["parcels"]]
        assert state.state == str(len(numbers))
        result[key] = numbers
    return result


def all_states(hass: HomeAssistant) -> str:
    """Return every state with its attributes, as JSON."""
    return json.dumps([s.as_dict() for s in hass.states.async_all()], default=str)


def persistent(hass: HomeAssistant) -> str | None:
    """Return the message of the persistent notification, if shown."""
    notification = async_get_persistent_notifications(hass).get(
        PERSISTENT_NOTIFICATION_ID
    )
    return notification["message"] if notification is not None else None


def mailbox_entities(hass: HomeAssistant, entry: MockConfigEntry) -> tuple[str, str]:
    """Return the last sync sensor and the problem sensor of a mailbox."""
    registry = er.async_get(hass)
    last_sync = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_last_sync"
    )
    problem = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_problem"
    )
    assert last_sync is not None
    assert problem is not None
    return last_sync, problem


async def async_get_events(
    hass: HomeAssistant, start: str, end: str
) -> list[dict[str, Any]]:
    """Return the events of the calendar, as the get_events action does."""
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"start_date_time": start, "end_date_time": end},
        target={ATTR_ENTITY_ID: "calendar.parcels"},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    return response["calendar.parcels"]["events"]


async def async_move_to(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, moment: str
) -> None:
    """Move the clock and run what is due."""
    freezer.move_to(moment)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def async_settle(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the notifier's debouncer run."""
    freezer.tick(timedelta(seconds=DEBOUNCE_COOLDOWN + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def async_check_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, entity_id: str
) -> None:
    """Check the mailbox of an entity now, with the update entity action."""
    freezer.tick(DEBOUNCER_COOLDOWN)
    async_fire_time_changed(hass)
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant", "update_entity", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def test_count_sensors(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """The sensors count the parcels of each kind and list them, newest first."""
    assert listed(hass) == {
        "arriving_today": [ZALANDO],
        "in_transit": [YOOX, WORTEN, ZALANDO, OUTFITTERS],
        "ready_for_pickup": [LOCKER],
        "delivered_today": [DELIVERED],
    }
    state = get(hass, "sensor.parcels_arriving_today")
    assert state.attributes["parcels"] == [
        {
            "id": parcel_with(engine, ZALANDO).id,
            "status": "out_for_delivery",
            "eta_start": "2026-11-17",
            "eta_end": "2026-11-17",
            "window_start": "13:00",
            "window_end": "14:00",
            "merchant": "Zalando",
            "carrier": "DPD",
            "tracking_number": ZALANDO,
        }
    ]
    assert state.attributes["unit_of_measurement"] == "parcels"
    assert state.attributes["state_class"] == "measurement"
    assert get(hass, "binary_sensor.parcels_delivery_today").state == STATE_ON
    # The order e-mail named the items; no state shows them.
    states = all_states(hass)
    assert OUTFITTERS in states
    assert not [item for item in ITEMS if item in states]


async def test_parcel_lists_not_recorded(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """The recorder keeps the counts but not the lists of parcels."""
    for key in COUNTS:
        state = get(hass, f"sensor.parcels_{key}")
        event = Event(
            EVENT_STATE_CHANGED,
            {"entity_id": state.entity_id, "old_state": None, "new_state": state},
        )
        recorded = json.loads(
            StateAttributes.shared_attrs_bytes_from_event(event, None)
        )
        assert "parcels" in state.attributes
        assert "parcels" not in recorded
        assert recorded["unit_of_measurement"] == "parcels"


async def test_ai_queue_sensor(
    hass: HomeAssistant, engine: ParcelsEngine, entity_registry: er.EntityRegistry
) -> None:
    """The AI queue is a diagnostic sensor with the mode, status and counters."""
    entity = entity_registry.async_get("sensor.parcels_ai_queue")
    assert entity is not None
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    state = get(hass, "sensor.parcels_ai_queue")
    assert state.state == "0"
    assert state.attributes["unit_of_measurement"] == "e-mails"
    assert {key: state.attributes[key] for key in ("mode", "status", *STAT_KEYS)} == {
        "mode": "suggest",
        "status": "off",
        **dict.fromkeys(STAT_KEYS, 0),
    }


async def test_sensors_follow_the_parcels(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """A parcel marked delivered moves from arriving to delivered today."""
    engine.mark_delivered(parcel_with(engine, ZALANDO).id)
    await hass.async_block_till_done()

    assert listed(hass) == {
        "arriving_today": [],
        "in_transit": [YOOX, WORTEN, OUTFITTERS],
        "ready_for_pickup": [LOCKER],
        "delivered_today": [ZALANDO, DELIVERED],
    }
    assert get(hass, "binary_sensor.parcels_delivery_today").state == STATE_OFF


async def test_midnight(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> None:
    """At midnight the sensors and the calendar move to the new day."""
    await async_move_to(hass, freezer, "2026-11-18 00:00:10+00:00")

    assert listed(hass) == {
        "arriving_today": [YOOX],
        "in_transit": [YOOX, WORTEN, ZALANDO, OUTFITTERS],
        "ready_for_pickup": [LOCKER],
        "delivered_today": [],
    }
    assert get(hass, "binary_sensor.parcels_delivery_today").state == STATE_ON
    # The parcel in the locker now waits for a second day.
    calendar = get(hass, "calendar.parcels")
    assert calendar.state == STATE_ON
    assert calendar.attributes["message"] == "CTT"
    assert calendar.attributes["start_time"] == "2026-11-17 00:00:00"
    assert calendar.attributes["end_time"] == "2026-11-19 00:00:00"


async def test_midnight_brings_the_shops_later_date(
    hass: HomeAssistant, hass_storage: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """At midnight a shop's later date takes over from the carrier's past one.

    CTT expects the parcel on Tuesday; the shop's newer e-mail says
    Wednesday. No e-mail comes at midnight: the expected date is worked out
    again for the new day.
    """
    freezer.move_to("2026-11-17 23:59:00+00:00")
    tuesday, wednesday = date(2026, 11, 17), date(2026, 11, 18)
    data = ParcelsData()
    for mail in (
        contribution(
            "msg:ctt#0",
            kind=MailKind.IN_TRANSIT,
            time=datetime(2026, 11, 15, 9, tzinfo=UTC),
            carrier="ctt",
            number=WORTEN,
            label="ctt.pt",
            eta=Eta(tuesday, tuesday),
        ),
        contribution(
            "msg:shop#0",
            kind=MailKind.IN_TRANSIT,
            time=datetime(2026, 11, 15, 18, tzinfo=UTC),
            carrier="ctt",
            number=WORTEN,
            merchant="Loja Exemplo",
            label="loja-exemplo.example",
            eta=Eta(wednesday, wednesday),
        ),
    ):
        apply_contribution(data, mail, mail.origin.time)
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)
    await async_setup_parcels(hass)

    def eta_start() -> str:
        [parcel] = get(hass, "sensor.parcels_in_transit").attributes["parcels"]
        return parcel["eta_start"]

    assert listed(hass)["arriving_today"] == [WORTEN]
    assert eta_start() == "2026-11-17"

    await async_move_to(hass, freezer, "2026-11-18 00:00:10+00:00")

    assert listed(hass)["arriving_today"] == [WORTEN]
    assert eta_start() == "2026-11-18"
    assert get(hass, "binary_sensor.parcels_delivery_today").state == STATE_ON


async def test_private_parcel(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """A private parcel shows no merchant, carrier, number or pickup point."""
    locker = parcel_with(engine, LOCKER)
    assert PICKUP_POINT in all_states(hass)

    engine.update(locker.id, {"private": True})
    await hass.async_block_till_done()

    assert get(hass, "sensor.parcels_ready_for_pickup").attributes["parcels"] == [
        {
            "id": locker.id,
            "status": "ready_for_pickup",
            "eta_start": "2026-11-17",
            "eta_end": "2026-11-24",
            "window_start": None,
            "window_end": None,
            "private": True,
        }
    ]
    events = await async_get_events(
        hass, "2026-11-17T00:00:00+00:00", "2026-11-17T12:00:00+00:00"
    )
    assert events == [
        {
            "start": "2026-11-17",
            "end": "2026-11-18",
            "summary": "CTT ✓",
            "description": f"Delivered\nCarrier: CTT\nTracking number: {DELIVERED}",
        },
        {
            "start": "2026-11-17",
            "end": "2026-11-18",
            "summary": "Private parcel",
            "description": "Ready for pickup",
        },
    ]
    states = all_states(hass)
    assert LOCKER not in states
    assert PICKUP_POINT not in states


async def test_calendar_week(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """The calendar shows the week's deliveries on the days the week card does."""
    outfitters = parcel_with(engine, OUTFITTERS)
    engine.update(outfitters.id, {"eta_start": "2026-11-18", "eta_end": "2026-11-20"})
    await hass.async_block_till_done()
    assert outfitters.state.status is ParcelStatus.SHIPPED

    events = await async_get_events(
        hass, "2026-11-16T00:00:00+00:00", "2026-11-23T00:00:00+00:00"
    )

    assert events == [
        # Waiting in the locker since today.
        {
            "start": "2026-11-17",
            "end": "2026-11-18",
            "summary": "CTT",
            "description": f"Ready for pickup\nCarrier: CTT\nTracking number: {LOCKER}",
            "location": PICKUP_POINT,
        },
        # Delivered this morning.
        {
            "start": "2026-11-17",
            "end": "2026-11-18",
            "summary": "CTT ✓",
            "description": f"Delivered\nCarrier: CTT\nTracking number: {DELIVERED}",
        },
        # A one-day estimate with a time window.
        {
            "start": "2026-11-17T13:00:00+00:00",
            "end": "2026-11-17T14:00:00+00:00",
            "summary": "Zalando",
            "description": (
                f"Out for delivery\nCarrier: DPD\nTracking number: {ZALANDO}"
            ),
        },
        # An estimate of three days.
        {
            "start": "2026-11-18",
            "end": "2026-11-21",
            "summary": "Example Outfitters",
            "description": f"Shipped\nCarrier: UPS\nTracking number: {OUTFITTERS}",
        },
        {
            "start": "2026-11-18T09:00:00+00:00",
            "end": "2026-11-18T12:00:00+00:00",
            "summary": "Yoox",
            "description": f"In transit\nCarrier: GLS\nTracking number: {YOOX}",
        },
        {
            "start": "2026-11-19",
            "end": "2026-11-20",
            "summary": "Worten",
            "description": f"In transit\nCarrier: CTT\nTracking number: {WORTEN}",
        },
    ]
    # Only events that overlap the range: today's all-day events end at midnight.
    tomorrow = await async_get_events(
        hass, "2026-11-18T00:00:00+00:00", "2026-11-19T00:00:00+00:00"
    )
    assert [event["summary"] for event in tomorrow] == ["Example Outfitters", "Yoox"]


async def test_calendar_api(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    hass_client: ClientSessionGenerator,
) -> None:
    """The calendar API returns the events of a range, with the parcel IDs."""
    client = await hass_client()
    response = await client.get(
        "/api/calendars/calendar.parcels",
        params={"start": "2026-11-17T12:00:00Z", "end": "2026-11-18T10:00:00Z"},
    )

    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert [
        (event["summary"], event["start"], event["end"], event["uid"])
        for event in events
    ] == [
        (
            "CTT",
            {"date": "2026-11-17"},
            {"date": "2026-11-18"},
            parcel_with(engine, LOCKER).id,
        ),
        (
            "CTT ✓",
            {"date": "2026-11-17"},
            {"date": "2026-11-18"},
            parcel_with(engine, DELIVERED).id,
        ),
        (
            "Zalando",
            {"dateTime": "2026-11-17T13:00:00+00:00"},
            {"dateTime": "2026-11-17T14:00:00+00:00"},
            parcel_with(engine, ZALANDO).id,
        ),
        (
            "Yoox",
            {"dateTime": "2026-11-18T09:00:00+00:00"},
            {"dateTime": "2026-11-18T12:00:00+00:00"},
            parcel_with(engine, YOOX).id,
        ),
    ]
    assert events[0]["location"] == PICKUP_POINT


async def test_current_event(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mailbox: MockConfigEntry
) -> None:
    """The calendar is on during a delivery window, then shows the next event."""
    freezer.move_to("2026-11-17 13:30:00+00:00")
    client = FakeMailClient()
    client.add("carriers/dpd_predict_pt.eml")
    client.add("carriers/ctt_in_transit_pt.eml")
    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)

        state = get(hass, "calendar.parcels")
        assert state.state == STATE_ON
        assert state.attributes == {
            "friendly_name": "Parcels",
            "message": "Zalando",
            "all_day": False,
            "start_time": "2026-11-17 13:00:00",
            "end_time": "2026-11-17 14:00:00",
            "location": "",
            "description": (
                f"Out for delivery\nCarrier: DPD\nTracking number: {ZALANDO}"
            ),
        }

        engine.update(parcel_with(engine, ZALANDO).id, {"private": True})
        await hass.async_block_till_done()
        state = get(hass, "calendar.parcels")
        assert state.state == STATE_ON
        assert state.attributes["message"] == "Private parcel"
        assert state.attributes["description"] == "Out for delivery"

        await async_move_to(hass, freezer, "2026-11-17 14:00:01+00:00")
        state = get(hass, "calendar.parcels")
        assert state.state == STATE_OFF
        assert state.attributes["message"] == "Worten"
        assert state.attributes["all_day"] is True
        assert state.attributes["start_time"] == "2026-11-19 00:00:00"


async def test_switches(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """The switches turn parts of the notifier off and on, also after a reload."""
    hub = add_hub(hass)
    engine = await async_setup_parcels(hass)
    parcel_id = engine.add_parcel("PX1234567890", merchant="Example Shop")
    engine.update(parcel_id, {"eta_start": "2026-11-17"})
    await async_settle(hass, freezer)
    assert "Example Shop" in (persistent(hass) or "")
    registry = er.async_get(hass)
    for entity_id in SWITCHES:
        entity = registry.async_get(entity_id)
        assert entity is not None
        assert entity.entity_category is EntityCategory.CONFIG
        assert get(hass, entity_id).state == STATE_ON

    await hass.services.async_call(
        "switch", "turn_off", target={ATTR_ENTITY_ID: list(SWITCHES)}, blocking=True
    )

    assert [get(hass, entity_id).state for entity_id in SWITCHES] == [STATE_OFF] * 2
    assert engine.notifier is not None
    assert not engine.notifier.live_activities_enabled
    assert not engine.notifier.daily_notification_enabled
    assert persistent(hass) is None

    assert await hass.config_entries.async_reload(hub.entry_id)
    await hass.async_block_till_done()
    engine = get_engine(hass)
    assert engine is not None
    assert engine.notifier is not None
    assert [get(hass, entity_id).state for entity_id in SWITCHES] == [STATE_OFF] * 2
    assert not engine.notifier.live_activities_enabled
    assert not engine.notifier.daily_notification_enabled
    await async_settle(hass, freezer)
    assert persistent(hass) is None

    await hass.services.async_call(
        "switch", "turn_on", target={ATTR_ENTITY_ID: list(SWITCHES)}, blocking=True
    )

    assert [get(hass, entity_id).state for entity_id in SWITCHES] == [STATE_ON] * 2
    assert engine.notifier.live_activities_enabled
    assert engine.notifier.daily_notification_enabled
    assert "Example Shop" in (persistent(hass) or "")


async def test_mailbox_last_sync(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    client: FakeMailClient,
    mailbox: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A mailbox shows when it was last checked; a check reads new e-mails."""
    last_sync, problem = mailbox_entities(hass, mailbox)
    assert get(hass, last_sync).state == "2026-11-17T15:00:00+00:00"
    assert get(hass, problem).state == STATE_OFF
    assert get(hass, problem).attributes["last_error"] is None
    for entity_id in (last_sync, problem):
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.entity_category is EntityCategory.DIAGNOSTIC
        device = device_registry.async_get(entity.device_id or "")
        assert device is not None
        assert (device.name, device.manufacturer, device.model) == (
            ADDRESS,
            "Google",
            "Gmail",
        )

    client.add("carriers/inpost_ready_pt.eml")
    await async_check_now(hass, freezer, last_sync)

    assert get(hass, last_sync).state == "2026-11-17T15:00:11+00:00"
    assert len(listed(hass)["ready_for_pickup"]) == 2
    assert len(client.syncs) == 2


@pytest.mark.parametrize(
    ("error", "last_error", "reauth"),
    [
        (MailServerError("HTTP 503"), "MailServerError", False),
        (MailAuthError("HTTP 401"), "auth", True),
    ],
    ids=["server", "auth"],
)
async def test_mailbox_problem(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: FakeMailClient,
    mailbox: MockConfigEntry,
    error: MailError,
    last_error: str,
    reauth: bool,
) -> None:
    """The problem sensor is on while checks fail and off after one succeeds."""
    client.sync_error = error
    with patch_mail_clients(client):
        await async_setup_parcels(hass)
        last_sync, problem = mailbox_entities(hass, mailbox)

        state = get(hass, problem)
        assert state.state == STATE_ON
        assert state.attributes["last_error"] == last_error
        assert get(hass, last_sync).state == STATE_UNAVAILABLE
        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert [
            (flow["context"]["source"], flow["context"]["entry_id"], flow["step_id"])
            for flow in flows
        ] == ([(SOURCE_REAUTH, mailbox.entry_id, "reauth_confirm")] if reauth else [])

        client.sync_error = None
        await async_check_now(hass, freezer, problem)

        state = get(hass, problem)
        assert state.state == STATE_OFF
        assert state.attributes["last_error"] is None
        assert get(hass, last_sync).state == "2026-11-17T15:00:11+00:00"
        assert listed(hass)["arriving_today"] == [ZALANDO]
