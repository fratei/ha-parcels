"""Tests for the 17TRACK sync.

The core ``seventeentrack`` integration isn't installed in the tests, so a
mock integration registers its three services and keeps its packages in
memory. All tracking numbers are synthetic.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import UTC, date, datetime, timedelta
import logging
import re
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    async_fire_time_changed,
    mock_integration,
    mock_platform,
)

from custom_components.parcels.const import (
    CONF_SEVENTEENTRACK,
    DOMAIN,
    LeftAt,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.dedup import (
    REPAIR_KEY,
    REPAIR_VERSION,
    Contribution,
    apply_contribution,
    archive_parcel,
    mark_delivered,
    merge_parcels,
    update_parcel,
)
from custom_components.parcels.engine import ParcelsEngine
from custom_components.parcels.models import (
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    Source,
    dt_to_str,
)
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.parsers.tracking import s10_check_digit
from custom_components.parcels.seventeentrack import (
    ADD_RETRIES,
    ADD_RETRY_DELAY,
    ADD_RETRY_LATER,
    MAX_ADDS,
    MAX_HISTORY,
    NOT_FOUND_ARCHIVE,
    SEVENTEENTRACK_DOMAIN,
    SeventeenTrackSync,
    friendly_name,
    map_status,
    origin_id,
)

from .common import add_hub, async_setup_parcels
from .factories import contribution

NOW = "2026-11-17 10:00:00+00:00"
NOW_DT = datetime(2026, 11, 17, 10, 0, tzinfo=UTC)
NOW_ISO = dt_to_str(NOW_DT)
TODAY = date(2026, 11, 17)
LISBON = "Europe/Lisbon"


def s10(serial: int) -> str:
    """Return a valid CTT number for an 8-digit serial."""
    digits = f"{serial:08d}"
    return f"RR{digits}{s10_check_digit(digits)}PT"


CTT = s10(10000001)
OTHER = s10(10000002)
LEGACY = "RR123456785PT"
UPS = "1Z9W8R371125836041"
AMAZON = "TBA123456789012"
PAACK_ID = "Qm7Rt2Kp9_2"
PAACK_BARCODE = "534000077712340056"
GLS = "61234567890"
SEUR = "04512345678912"


class FakeSeventeenTrack:
    """The services of the core 17TRACK integration, with packages in memory.

    Set ``errors`` to make a service fail, ``response`` to replace what
    get_packages returns, and ``show_archived`` to list archived packages too,
    like 17TRACK's "Show archived packages" option.
    """

    def __init__(self) -> None:
        """Start without packages."""
        self.entry_id = ""
        self.packages: dict[str, dict[str, Any]] = {}
        self.archived: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.errors: dict[str, Exception] = {}
        self.response: dict[str, Any] | None = None
        self.show_archived = False

    def put(
        self,
        number: str,
        status: str = "In Transit",
        *,
        info: str = "",
        location: str = "",
        timestamp: str | None = None,
        name: str | None = None,
    ) -> None:
        """Add or update a package; ``name=None`` keeps its friendly name."""
        old = self.packages.get(number, {})
        package: dict[str, Any] = {
            "destination_country": "Portugal",
            "origin_country": "Portugal",
            "package_type": "Registered Parcel",
            "tracking_info_language": "Unknown",
            "tracking_number": number,
            "location": location,
            "status": status,
            "info_text": info,
            "friendly_name": old.get("friendly_name") if name is None else name,
        }
        if timestamp is not None:
            package["timestamp"] = timestamp
        self.packages[number] = package

    def numbers(self, service: str) -> list[str]:
        """Return the tracking numbers sent to a service, in order."""
        return [
            data["package_tracking_number"]
            for name, data in self.calls
            if name == service
        ]

    def count(self, service: str) -> int:
        """Return how often a service was called."""
        return sum(1 for name, _ in self.calls if name == service)

    async def _async_handle(self, call: ServiceCall) -> ServiceResponse:
        """Record a service call and answer it like 17TRACK."""
        data = dict(call.data)
        self.calls.append((call.service, data))
        if (error := self.errors.get(call.service)) is not None:
            raise error
        if call.service == "get_packages":
            if self.response is not None:
                return self.response
            listed = [*self.packages.values()]
            if self.show_archived:
                listed += self.archived.values()
            return {"packages": [dict(package) for package in listed]}
        number = data["package_tracking_number"]
        if call.service == "add_package":
            self.put(number, "Not Found", name=data["package_friendly_name"])
        else:
            self.archived[number] = self.packages.pop(number)
        return None

    async def async_setup_entry(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Register the services of the entry."""
        self.entry_id = entry.entry_id
        for service in ("add_package", "archive_package"):
            hass.services.async_register(
                SEVENTEENTRACK_DOMAIN, service, self._async_handle
            )
        hass.services.async_register(
            SEVENTEENTRACK_DOMAIN,
            "get_packages",
            self._async_handle,
            supports_response=SupportsResponse.ONLY,
        )

    async def async_unload_entry(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Unload the entry."""


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on 17 November 2026 at 10:00, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone(LISBON)


class FakeFlow(ConfigFlow):
    """The config flow of the mocked 17TRACK integration."""

    VERSION = 1


@pytest.fixture
async def track(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> FakeSeventeenTrack:
    """Load a 17TRACK entry backed by the fake services."""
    fake = FakeSeventeenTrack()
    monkeypatch.setitem(config_entries.HANDLERS, SEVENTEENTRACK_DOMAIN, FakeFlow)
    mock_integration(
        hass,
        MockModule(
            SEVENTEENTRACK_DOMAIN,
            async_setup_entry=fake.async_setup_entry,
            async_unload_entry=fake.async_unload_entry,
        ),
    )
    mock_platform(hass, f"{SEVENTEENTRACK_DOMAIN}.config_flow", None)
    entry = MockConfigEntry(domain=SEVENTEENTRACK_DOMAIN, title="17TRACK")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return fake


@pytest.fixture
async def engine(hass: HomeAssistant, track: FakeSeventeenTrack) -> ParcelsEngine:
    """Load the hub, with 17TRACK on."""
    add_hub(hass)
    return await async_setup_parcels(hass)


@pytest.fixture
async def tracker(engine: ParcelsEngine) -> SeventeenTrackSync:
    """Return the hub's 17TRACK sync without its timer: the test refreshes it."""
    tracker = engine.tracker
    assert tracker is not None
    await tracker.async_stop()
    return tracker


@pytest.fixture
def refreshes(
    engine: ParcelsEngine, monkeypatch: pytest.MonkeyPatch
) -> list[asyncio.Task[Any]]:
    """Collect the refreshes that the 17TRACK timer starts."""
    tasks: list[asyncio.Task[Any]] = []
    create = engine.async_create_task

    def capture(coro: Coroutine[Any, Any, Any], name: str) -> asyncio.Task[Any]:
        """Start the task as usual and keep it."""
        task = create(coro, name)
        tasks.append(task)
        return task

    monkeypatch.setattr(engine, "async_create_task", capture)
    return tasks


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


def add_parcel(
    engine: ParcelsEngine,
    name: str,
    number: str | None,
    *,
    carrier: str | None = None,
    kind: MailKind = MailKind.SHIPPED,
    private: bool = False,
    eta: Eta | None = None,
    age: timedelta = timedelta(hours=1),
) -> Parcel:
    """Record a shipping e-mail about one parcel, received ``age`` ago."""
    now = dt_util.utcnow()
    applied = apply_contribution(
        engine.data,
        contribution(
            f"msg:{name}#0",
            kind=kind,
            time=now - age,
            carrier=carrier,
            number=number,
            eta=eta,
            private=private,
        ),
        now,
    )
    engine.async_changed()
    assert applied.parcel_id is not None
    return engine.data.parcels[applied.parcel_id]


def tracked_before(
    engine: ParcelsEngine,
    track: FakeSeventeenTrack,
    number: str,
    parcel: Parcel,
    *,
    own: bool = True,
    added: str | None = None,
) -> None:
    """Record a number that an earlier release, or the user, put in 17TRACK."""
    track.put(
        number, "Not Found", name=friendly_name(parcel.id) if own else "Sapatilhas"
    )
    record: dict[str, Any] = {"parcel": parcel.id, "own": own}
    if added is not None:
        record["added"] = added
    engine.data.seventeentrack.setdefault("packages", {})[number] = record


def records(engine: ParcelsEngine) -> dict[str, dict[str, Any]]:
    """Return the stored 17TRACK records by tracking number."""
    return engine.data.seventeentrack.get("packages", {})


def failures(engine: ParcelsEngine) -> dict[str, dict[str, Any]]:
    """Return the stored failed adds by tracking number."""
    return engine.data.seventeentrack.get("failed", {})


def news(engine: ParcelsEngine, parcel_id: str, number: str) -> list[ParcelEvent]:
    """Return the events that 17TRACK gave a parcel about a number."""
    return [
        event
        for event in engine.data.parcels[parcel_id].events
        if event.origin == origin_id(number)
    ]


def status(engine: ParcelsEngine, parcel_id: str) -> ParcelStatus:
    """Return the current status of a parcel."""
    return engine.data.parcels[parcel_id].state.status


def get_call(track: FakeSeventeenTrack) -> tuple[str, dict[str, Any]]:
    """Return the expected get_packages call."""
    return ("get_packages", {"config_entry_id": track.entry_id})


def add_call(
    track: FakeSeventeenTrack, number: str, parcel: Parcel
) -> tuple[str, dict[str, Any]]:
    """Return the expected add_package call for a parcel's number."""
    return (
        "add_package",
        {
            "config_entry_id": track.entry_id,
            "package_tracking_number": number,
            "package_friendly_name": friendly_name(parcel.id),
        },
    )


def archive_call(track: FakeSeventeenTrack, number: str) -> tuple[str, dict[str, Any]]:
    """Return the expected archive_package call for a number."""
    return (
        "archive_package",
        {"config_entry_id": track.entry_id, "package_tracking_number": number},
    )


def logged_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the warnings that the 17TRACK sync logged."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "custom_components.parcels.seventeentrack"
        and record.levelno >= logging.WARNING
    ]


@pytest.mark.parametrize(
    ("package_status", "info", "expected"),
    [
        ("In Transit", None, ParcelStatus.IN_TRANSIT),
        ("In Transit", "Centro operacional 3", ParcelStatus.IN_TRANSIT),
        ("In Transit", "Em distribuição", ParcelStatus.OUT_FOR_DELIVERY),
        ("In Transit", "En reparto", ParcelStatus.OUT_FOR_DELIVERY),
        ("In Transit", "Aguarda levantamento na loja", ParcelStatus.READY_FOR_PICKUP),
        ("Alert", "Devolvido ao remetente", ParcelStatus.RETURNED),
        ("Alert", "Out for delivery", ParcelStatus.OUT_FOR_DELIVERY),
        ("Alert", "Morada incompleta", ParcelStatus.EXCEPTION),
        ("Undelivered", "Tentativa de entrega sem sucesso", ParcelStatus.ATTEMPTED),
        ("Undelivered", "Destinatário ausente", ParcelStatus.ATTEMPTED),
        ("Ready to be picked up", None, ParcelStatus.IN_TRANSIT),
        ("ready_to_be_picked_up", "", ParcelStatus.IN_TRANSIT),
        (
            "Ready to be picked up",
            "Em entrega - O objeto saiu para entrega ao destinatário.",
            ParcelStatus.OUT_FOR_DELIVERY,
        ),
        (
            "ready_to_be_picked_up",
            "Out for delivery - on the vehicle for delivery today",
            ParcelStatus.OUT_FOR_DELIVERY,
        ),
        (
            "Ready to be picked up",
            "En reparto. Tu paquete llegará hoy.",
            ParcelStatus.OUT_FOR_DELIVERY,
        ),
        (
            "Ready to be picked up",
            "Arrived at the local depot",
            ParcelStatus.IN_TRANSIT,
        ),
        (
            "Ready to be picked up",
            "Disponível para levantamento no Ponto Exemplo",
            ParcelStatus.READY_FOR_PICKUP,
        ),
        (
            "Ready to be picked up",
            "Ready for collection at the access point",
            ParcelStatus.READY_FOR_PICKUP,
        ),
        (
            "Ready to be picked up",
            "Destinatário ausente, aviso deixado",
            ParcelStatus.ATTEMPTED,
        ),
        ("Delivered", "Em distribuição", ParcelStatus.DELIVERED),
        ("Returned", None, ParcelStatus.RETURNED),
        ("Not Found", "Em distribuição", None),
        ("Expired", None, None),
        ("Unknown", None, None),
        (None, None, None),
    ],
)
async def test_map_status(
    package_status: str | None, info: str | None, expected: ParcelStatus | None
) -> None:
    """The carrier's text refines vague statuses, never a final one.

    17TRACK's "ready to be picked up" also means out for delivery: it's a
    pickup only when the carrier's text says so.
    """
    assert map_status(package_status, info) is expected


async def test_pickup_status_needs_the_carriers_word(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """17TRACK's pickup status alone makes no pickup; the carrier's e-mails count.

    Out for delivery in the carrier's text is out for delivery, and the
    carrier's own e-mail about it still moves the parcel on.
    """
    parcel = add_parcel(engine, "ctt", CTT, carrier="ctt")
    await tracker.async_refresh()
    track.put(
        CTT,
        "Ready to be picked up",
        info="Chegou à plataforma de distribuição",
        timestamp="2026-11-17T07:10:00+00:00",
    )

    await tracker.async_refresh()

    assert status(engine, parcel.id) is ParcelStatus.IN_TRANSIT
    assert engine.data.parcels[parcel.id].state.collect_by is None
    apply_contribution(
        engine.data,
        contribution(
            "msg:ctt-out#0",
            kind=MailKind.OUT_FOR_DELIVERY,
            time=datetime(2026, 11, 17, 8, 5, tzinfo=UTC),
            carrier="ctt",
            number=CTT,
        ),
        dt_util.utcnow(),
    )
    engine.async_changed()
    assert status(engine, parcel.id) is ParcelStatus.OUT_FOR_DELIVERY

    track.put(
        CTT,
        "Ready to be picked up",
        info="Em entrega - O objeto saiu para entrega ao destinatário.",
        timestamp="2026-11-17T08:20:00+00:00",
    )
    await tracker.async_refresh()

    assert status(engine, parcel.id) is ParcelStatus.OUT_FOR_DELIVERY
    assert [entry["status"] for entry in records(engine)[CTT]["history"]] == [
        "in_transit",
        "out_for_delivery",
    ]

    track.put(
        CTT,
        "Ready to be picked up",
        info="Disponível para levantamento até 19/11",
        timestamp="2026-11-17T09:30:00+00:00",
    )
    await tracker.async_refresh()

    state = engine.data.parcels[parcel.id].state
    assert (state.status, state.collect_by) == (
        ParcelStatus.READY_FOR_PICKUP,
        date(2026, 11, 19),
    )


async def test_update_takes_back_pickups_17track_alone_gave(
    hass: HomeAssistant, hass_storage: dict[str, Any], track: FakeSeventeenTrack
) -> None:
    """Once, the pickups that 17TRACK's status alone gave before 0.1.13 go.

    They take the status the carrier's text tells, or in transit, in the
    stored packages and on the parcels; a pickup the text tells stays, and
    the next refresh adds nothing new.
    """
    data = ParcelsData()
    shipped = NOW_DT - timedelta(hours=6)
    packages: dict[str, dict[str, Any]] = {}
    ids: dict[str, str] = {}
    texts = (
        (
            CTT,
            "ctt",
            "Em entrega - O objeto saiu para entrega ao destinatário.",
            datetime(2026, 11, 17, 8, 20, tzinfo=UTC),
        ),
        (
            OTHER,
            "ctt",
            "Disponível para levantamento até 19/11",
            datetime(2026, 11, 17, 9, 10, tzinfo=UTC),
        ),
        (UPS, "ups", None, None),
    )
    for number, carrier, info, at in texts:
        applied = apply_contribution(
            data,
            contribution(
                f"msg:{number}#0", time=shipped, carrier=carrier, number=number
            ),
            shipped,
        )
        assert applied.parcel_id is not None
        ids[number] = applied.parcel_id
        time = at or NOW_DT - timedelta(minutes=30)
        apply_contribution(
            data,
            Contribution(
                origin=Origin(
                    id=origin_id(number),
                    source=Source.SEVENTEENTRACK,
                    time=time,
                    label="17TRACK",
                    carrier=carrier,
                    tracking_number=number,
                ),
                events=[
                    ParcelEvent(
                        time=time,
                        source=Source.SEVENTEENTRACK,
                        status=ParcelStatus.READY_FOR_PICKUP,
                        label=info,
                        collect_by=date(2026, 11, 19),
                    )
                ],
            ),
            time,
        )
        packages[number] = {
            "parcel": applied.parcel_id,
            "own": True,
            "status": "ready_to_be_picked_up",
            "history": [
                {
                    "status": "ready_for_pickup",
                    "info": info,
                    "at": dt_to_str(at),
                    "time": dt_to_str(time),
                }
            ],
        }
    data.seventeentrack["packages"] = packages
    data.engine[REPAIR_KEY] = REPAIR_VERSION
    hass_storage[DOMAIN] = {
        "version": 1,
        "minor_version": 1,
        "key": DOMAIN,
        "data": data.as_dict(),
    }
    add_hub(hass)

    engine = await async_setup_parcels(hass)
    tracker = engine.tracker
    assert tracker is not None
    await tracker.async_stop()

    states = {
        number: engine.data.parcels[ids[number]].state for number in (CTT, OTHER, UPS)
    }
    assert {
        number: (state.status, state.collect_by) for number, state in states.items()
    } == {
        CTT: (ParcelStatus.OUT_FOR_DELIVERY, None),
        OTHER: (ParcelStatus.READY_FOR_PICKUP, date(2026, 11, 19)),
        UPS: (ParcelStatus.IN_TRANSIT, None),
    }
    assert {
        number: [entry["status"] for entry in record["history"]]
        for number, record in records(engine).items()
    } == {
        CTT: ["out_for_delivery"],
        OTHER: ["ready_for_pickup"],
        UPS: ["in_transit"],
    }
    assert engine.diagnostics()["seventeentrack_pickups_repaired"] == 2

    track.put(
        CTT,
        "Ready to be picked up",
        info="Em entrega - O objeto saiu para entrega ao destinatário.",
        timestamp="2026-11-17T08:20:00+00:00",
    )
    await tracker.async_refresh()

    assert len(records(engine)[CTT]["history"]) == 1
    assert status(engine, ids[CTT]) is ParcelStatus.OUT_FOR_DELIVERY


async def test_adds_the_numbers_of_active_parcels(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """Only active, public parcels with a full non-Amazon number are added."""
    ctt = add_parcel(engine, "ctt", CTT, carrier="ctt")
    ups = add_parcel(engine, "ups", UPS, carrier="ups")
    add_parcel(engine, "amazon", AMAZON)
    add_parcel(engine, "amazon-carrier", "AZ2611170001PT", carrier="amazon")
    add_parcel(engine, "private", s10(10000003), carrier="ctt", private=True)
    add_parcel(engine, "delivered", s10(10000004), kind=MailKind.DELIVERED)
    add_parcel(engine, "short", "AB12345")
    add_parcel(engine, "none", None)
    archived = add_parcel(engine, "archived", s10(10000005), carrier="ctt")
    archive_parcel(engine.data, archived.id, dt_util.utcnow())

    await tracker.async_refresh()

    assert track.calls == [
        get_call(track),
        add_call(track, CTT, ctt),
        add_call(track, UPS, ups),
    ]
    for _, data in track.calls[1:]:
        assert re.fullmatch(r"parcels-[0-9a-f]{6}", data["package_friendly_name"])
    assert records(engine) == {
        CTT: {"parcel": ctt.id, "own": True, "added": NOW_ISO},
        UPS: {"parcel": ups.id, "own": True, "added": NOW_ISO},
    }
    diagnostics = tracker.diagnostics()
    assert diagnostics == {
        "enabled": True,
        "available": True,
        "tracked": 2,
        "archived": 0,
        "failed": 0,
        "last_refresh": NOW_ISO,
        "last_error": None,
        "not_found_by_carrier": {},
    }
    assert CTT not in str(diagnostics)
    assert UPS not in str(diagnostics)

    track.calls.clear()
    await tracker.async_refresh()

    assert track.calls == [get_call(track)]


async def test_adopts_packages_already_in_17track(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """Existing packages are followed, but only the ones Parcels named are archived."""
    ours = add_parcel(engine, "ours", CTT, carrier="ctt")
    theirs = add_parcel(engine, "theirs", OTHER, carrier="ctt")
    track.put(CTT, name="parcels-abcdef")
    track.put(OTHER, name="Sapatilhas")

    await tracker.async_refresh()

    assert track.calls == [get_call(track)]
    assert records(engine)[CTT]["own"] is True
    assert records(engine)[OTHER]["own"] is False
    assert "added" not in records(engine)[CTT]
    assert status(engine, ours.id) is ParcelStatus.IN_TRANSIT
    assert status(engine, theirs.id) is ParcelStatus.IN_TRANSIT

    for number in (CTT, OTHER):
        track.put(number, "Delivered", timestamp="2026-11-17T09:50:00+00:00")
    track.calls.clear()
    await tracker.async_refresh()

    assert track.calls == [get_call(track), archive_call(track, CTT)]
    assert status(engine, ours.id) is ParcelStatus.DELIVERED
    assert status(engine, theirs.id) is ParcelStatus.DELIVERED
    assert records(engine)[CTT]["archived"] == NOW_ISO
    assert "archived" not in records(engine)[OTHER]
    assert tracker.diagnostics()["tracked"] == 1
    assert tracker.diagnostics()["archived"] == 1

    track.calls.clear()
    await tracker.async_refresh()

    assert track.calls == [get_call(track)]

    del engine.data.parcels[theirs.id]
    engine.async_changed()
    await tracker.async_refresh()

    assert track.calls == [get_call(track)] * 2
    assert set(records(engine)) == {CTT}


async def test_statuses_become_events(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """New statuses become events of a 17TRACK origin; repeats add nothing."""
    parcel = add_parcel(engine, "ctt", CTT, carrier="ctt")
    await tracker.async_refresh()
    track.put(CTT, info="Em distribuição", timestamp="2026-11-17T09:45:00+00:00")

    await tracker.async_refresh()

    out = datetime(2026, 11, 17, 9, 45, tzinfo=UTC)
    assert status(engine, parcel.id) is ParcelStatus.OUT_FOR_DELIVERY
    origin = engine.data.parcels[parcel.id].origins[origin_id(CTT)]
    assert origin.source is Source.SEVENTEENTRACK
    assert origin.label == "17TRACK"
    assert origin.carrier == "ctt"
    assert origin.tracking_number == CTT
    assert origin.time == out
    events = news(engine, parcel.id, CTT)
    assert [(e.status, e.label, e.time, e.source) for e in events] == [
        (ParcelStatus.OUT_FOR_DELIVERY, "Em distribuição", out, Source.SEVENTEENTRACK)
    ]
    assert records(engine)[CTT]["status"] == "in_transit"
    assert records(engine)[CTT]["history"] == [
        {
            "status": "out_for_delivery",
            "info": "Em distribuição",
            "at": dt_to_str(out),
            "time": dt_to_str(out),
        }
    ]

    await tracker.async_refresh()

    assert len(records(engine)[CTT]["history"]) == 1
    assert news(engine, parcel.id, CTT) == events

    track.put(CTT, "Delivered", timestamp="2026-11-17T09:58:00+00:00")
    await tracker.async_refresh()

    assert status(engine, parcel.id) is ParcelStatus.DELIVERED
    assert [e.status for e in news(engine, parcel.id, CTT)] == [
        ParcelStatus.OUT_FOR_DELIVERY,
        ParcelStatus.DELIVERED,
    ]
    assert track.numbers("archive_package") == [CTT]
    assert records(engine)[CTT]["archived"] == NOW_ISO
    assert tracker.diagnostics()["archived"] == 1

    track.show_archived = True
    track.archived[CTT].update(
        info_text="Entregue", timestamp="2026-11-17T09:59:00+00:00"
    )
    await tracker.async_refresh()

    assert len(news(engine, parcel.id, CTT)) == 2
    assert track.numbers("archive_package") == [CTT]


async def test_archived_parcels_get_no_news(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """News doesn't bring back a parcel the user archived; it leaves 17TRACK."""
    parcel = add_parcel(engine, "ctt", CTT, carrier="ctt")
    await tracker.async_refresh()
    archive_parcel(engine.data, parcel.id, dt_util.utcnow())
    engine.async_changed()
    track.put(CTT, info="Em distribuição")

    await tracker.async_refresh()

    assert engine.data.parcels[parcel.id].archived is not None
    assert news(engine, parcel.id, CTT) == []
    assert track.numbers("archive_package") == [CTT]
    assert records(engine)[CTT]["archived"] == NOW_ISO


@pytest.mark.parametrize(
    ("package", "zone", "info", "at"),
    [
        ({"location": "Centro de Lisboa"}, LISBON, "Centro de Lisboa", None),
        (
            {"info": " Centro\n operacional   3 ", "location": "Lisboa"},
            LISBON,
            "Centro operacional 3",
            None,
        ),
        ({"info": "x" * 200}, LISBON, "x" * 159 + "…", None),
        (
            {"timestamp": "2026-11-17T09:30:00+00:00"},
            LISBON,
            None,
            "2026-11-17T09:30:00+00:00",
        ),
        (
            {"timestamp": "2026-11-17T08:00:00"},
            "Atlantic/Azores",
            None,
            "2026-11-17T09:00:00+00:00",
        ),
        ({"timestamp": "2026-11-18T09:00:00+00:00"}, LISBON, None, NOW_ISO),
        ({"timestamp": "soon"}, LISBON, None, None),
    ],
    ids=["location", "whitespace", "long", "timestamp", "naive", "future", "invalid"],
)
async def test_package_text_and_time(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
    package: dict[str, str],
    zone: str,
    info: str | None,
    at: str | None,
) -> None:
    """The carrier's text is tidied; times are local and never in the future."""
    await hass.config.async_set_time_zone(zone)
    add_parcel(engine, "ctt", CTT, carrier="ctt")
    await tracker.async_refresh()
    track.put(CTT, **package)

    await tracker.async_refresh()
    await tracker.async_refresh()

    assert records(engine)[CTT]["history"] == [
        {"status": "in_transit", "info": info, "at": at, "time": at or NOW_ISO}
    ]


async def test_package_text_gives_details(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """The carrier's text says until when to collect, the next attempt and where.

    Its days count from the package's own time.
    """
    pickup = add_parcel(engine, "ctt", CTT, carrier="ctt")
    missed = add_parcel(engine, "other", OTHER, carrier="ctt")
    delivered = add_parcel(engine, "ups", UPS, carrier="ups")
    await tracker.async_refresh()
    track.put(
        CTT,
        "Ready to be picked up",
        info="Disponível para levantamento até 19/11",
        timestamp="2026-11-17T09:45:00+00:00",
    )
    track.put(
        OTHER,
        "Undelivered",
        info="Destinatário ausente. Nova entrega amanhã",
        timestamp="2026-11-16T18:10:00+00:00",
    )
    track.put(
        UPS,
        "Delivered",
        info="Delivered - Front door",
        timestamp="2026-11-17T09:40:00+00:00",
    )

    await tracker.async_refresh()

    state = engine.data.parcels[pickup.id].state
    assert (state.status, state.collect_by) == (
        ParcelStatus.READY_FOR_PICKUP,
        date(2026, 11, 19),
    )
    state = engine.data.parcels[missed.id].state
    assert (state.status, state.next_attempt) == (ParcelStatus.ATTEMPTED, TODAY)
    state = engine.data.parcels[delivered.id].state
    assert (state.status, state.left_at) == (ParcelStatus.DELIVERED, LeftAt.DOOR)
    assert [event.left_at for event in news(engine, delivered.id, UPS)] == [LeftAt.DOOR]


async def test_package_without_a_time_gives_no_days(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """Without the package's time, its text's days aren't read."""
    pickup = add_parcel(engine, "ctt", CTT, carrier="ctt")
    missed = add_parcel(engine, "other", OTHER, carrier="ctt")
    await tracker.async_refresh()
    track.put(
        CTT, "Ready to be picked up", info="Disponível para levantamento até 19/11"
    )
    track.put(OTHER, "Undelivered", info="Destinatário ausente. Nova entrega amanhã")

    await tracker.async_refresh()

    state = engine.data.parcels[pickup.id].state
    assert (state.status, state.collect_by) == (ParcelStatus.READY_FOR_PICKUP, None)
    state = engine.data.parcels[missed.id].state
    assert (state.status, state.next_attempt) == (ParcelStatus.ATTEMPTED, None)


async def test_history_keeps_the_last_statuses(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """Only the last ten statuses are kept, and they are the parcel's events."""
    parcel = add_parcel(engine, "ctt", CTT, carrier="ctt")
    await tracker.async_refresh()

    for index in range(MAX_HISTORY + 2):
        track.put(CTT, info=f"Centro {index}")
        await tracker.async_refresh()

    expected = [f"Centro {index}" for index in range(2, MAX_HISTORY + 2)]
    assert [entry["info"] for entry in records(engine)[CTT]["history"]] == expected
    assert [event.label for event in news(engine, parcel.id, CTT)] == expected


async def test_unknown_stored_status_is_skipped(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """A stored status that Parcels doesn't know adds no event."""
    parcel = add_parcel(engine, "ctt", CTT, carrier="ctt")
    await tracker.async_refresh()
    records(engine)[CTT]["history"] = [
        {"status": "teleported", "info": None, "at": None, "time": NOW_ISO}
    ]
    track.put(CTT)

    await tracker.async_refresh()

    assert len(records(engine)[CTT]["history"]) == 2
    assert [event.status for event in news(engine, parcel.id, CTT)] == [
        ParcelStatus.IN_TRANSIT
    ]


async def test_failed_add_is_retried_later(
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed add stays visible, without the error text, and is retried later."""
    add_parcel(engine, "ctt", CTT, carrier="ctt")
    track.errors["add_package"] = HomeAssistantError(f"{CTT} refused")

    await tracker.async_refresh()

    assert tracker.last_error == "add_package: HomeAssistantError"
    assert tracker.last_refresh == NOW_DT
    assert logged_warnings(caplog) == [
        "17TRACK add_package failed (HomeAssistantError)"
    ]
    assert "refused" not in caplog.text
    assert CTT not in caplog.text
    assert records(engine) == {}
    assert failures(engine) == {
        CTT: {"count": 1, "retry": dt_to_str(NOW_DT + ADD_RETRY_DELAY)}
    }
    assert tracker.diagnostics()["failed"] == 1

    del track.errors["add_package"]
    freezer.tick(ADD_RETRY_DELAY - timedelta(minutes=1))
    await tracker.async_refresh()

    assert track.numbers("add_package") == [CTT]
    assert tracker.last_error is None

    freezer.tick(timedelta(minutes=1))
    await tracker.async_refresh()

    assert track.numbers("add_package") == [CTT, CTT]
    assert failures(engine) == {}
    assert records(engine)[CTT]["added"] == dt_to_str(NOW_DT + ADD_RETRY_DELAY)


async def test_refused_add_is_tried_daily_after_three_failures(
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After three refusals a number is tried once a day until its parcel ends.

    17TRACK refuses new numbers while the account is full, so a refused number
    must get in once a place frees up.
    """
    parcel = add_parcel(engine, "ctt", CTT, carrier="ctt")
    track.errors["add_package"] = HomeAssistantError("refused")

    await tracker.async_refresh()
    for count in range(1, ADD_RETRIES):
        freezer.tick(ADD_RETRY_DELAY * count)
        await tracker.async_refresh()

    assert failures(engine)[CTT] == {
        "count": ADD_RETRIES,
        "retry": dt_to_str(dt_util.utcnow() + ADD_RETRY_LATER),
    }

    freezer.tick(ADD_RETRY_LATER - timedelta(minutes=1))
    await tracker.async_refresh()

    assert track.numbers("add_package") == [CTT] * ADD_RETRIES

    freezer.tick(timedelta(minutes=1))
    await tracker.async_refresh()

    assert track.numbers("add_package") == [CTT] * (ADD_RETRIES + 1)
    assert failures(engine)[CTT]["count"] == ADD_RETRIES + 1

    del track.errors["add_package"]
    freezer.tick(ADD_RETRY_LATER)
    await tracker.async_refresh()

    assert track.numbers("add_package") == [CTT] * (ADD_RETRIES + 2)
    assert failures(engine) == {}
    assert CTT in records(engine)

    mark_delivered(engine.data, parcel.id, dt_util.utcnow())
    engine.async_changed()
    await tracker.async_refresh()

    assert track.numbers("add_package") == [CTT] * (ADD_RETRIES + 2)


async def test_refused_numbers_are_forgotten_when_the_parcel_ends(
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A delivered parcel's refused number is never tried again."""
    parcel = add_parcel(engine, "ctt", CTT, carrier="ctt")
    track.errors["add_package"] = HomeAssistantError("refused")
    await tracker.async_refresh()

    mark_delivered(engine.data, parcel.id, dt_util.utcnow())
    engine.async_changed()
    freezer.tick(ADD_RETRY_LATER)
    await tracker.async_refresh()

    assert failures(engine) == {}
    assert track.numbers("add_package") == [CTT]


async def test_refusal_code_is_kept_without_the_message(
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """17TRACK's status code shows in diagnostics; other messages never do."""

    class RequestError(Exception):
        """Stands in for pyseventeentrack's RequestError."""

    class InvalidTrackingNumberError(Exception):
        """Stands in for pyseventeentrack's InvalidTrackingNumberError."""

    add_parcel(engine, "ctt", CTT, carrier="ctt")
    track.errors["add_package"] = RequestError("Non-zero status code in response: -7")

    await tracker.async_refresh()

    assert tracker.last_error == "add_package: RequestError (code -7)"
    assert tracker.diagnostics()["last_error"] == "add_package: RequestError (code -7)"
    assert logged_warnings(caplog) == [
        "17TRACK add_package failed (RequestError (code -7))"
    ]

    track.errors["add_package"] = InvalidTrackingNumberError(
        f"Recently added package not found by tracking number: {CTT}"
    )
    freezer.tick(ADD_RETRY_DELAY)
    await tracker.async_refresh()

    assert tracker.last_error == "add_package: InvalidTrackingNumberError"
    assert CTT not in caplog.text

    track.errors["add_package"] = RequestError(
        f"Non-zero status code in response: 5 {CTT}"
    )
    freezer.tick(ADD_RETRY_DELAY * 2)
    await tracker.async_refresh()

    assert tracker.last_error == "add_package: RequestError"
    assert CTT not in caplog.text


async def test_adds_at_most_ten_numbers_per_refresh(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """A long backlog is added over several refreshes."""
    numbers = [s10(10000001 + index) for index in range(MAX_ADDS + 2)]
    for index, number in enumerate(numbers):
        add_parcel(engine, f"parcel{index}", number, carrier="ctt")

    await tracker.async_refresh()

    assert track.numbers("add_package") == numbers[:MAX_ADDS]

    await tracker.async_refresh()

    assert track.numbers("add_package") == numbers


async def test_adds_the_parcels_due_soonest_first(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """Late parcels come first, then today's, later dates, and no date last."""
    numbers = [s10(20000001 + index) for index in range(6)]
    add_parcel(engine, "undated", numbers[0], carrier="ctt")
    add_parcel(
        engine,
        "next week",
        numbers[1],
        carrier="ctt",
        eta=Eta(start=TODAY + timedelta(days=5), end=TODAY + timedelta(days=6)),
    )
    add_parcel(
        engine,
        "late",
        numbers[2],
        carrier="ctt",
        eta=Eta(start=TODAY - timedelta(days=2), end=TODAY - timedelta(days=1)),
    )
    add_parcel(engine, "out", numbers[3], carrier="ctt", kind=MailKind.OUT_FOR_DELIVERY)
    add_parcel(
        engine,
        "tomorrow",
        numbers[4],
        carrier="ctt",
        eta=Eta(start=TODAY + timedelta(days=1), end=TODAY + timedelta(days=1)),
    )
    add_parcel(engine, "undated later", numbers[5], carrier="ctt")

    await tracker.async_refresh()

    assert track.numbers("add_package") == [
        numbers[2],
        numbers[3],
        numbers[4],
        numbers[1],
        numbers[0],
        numbers[5],
    ]


async def test_unreadable_packages_skip_the_refresh(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """When get_packages fails nothing else is tried until the next refresh."""
    add_parcel(engine, "ctt", CTT, carrier="ctt")
    track.errors["get_packages"] = HomeAssistantError("unavailable")

    await tracker.async_refresh()

    assert track.calls == [get_call(track)]
    assert tracker.last_error == "get_packages: HomeAssistantError"
    assert tracker.last_refresh is None
    assert records(engine) == {}

    del track.errors["get_packages"]
    await tracker.async_refresh()

    assert track.numbers("add_package") == [CTT]
    assert tracker.last_error is None
    assert tracker.last_refresh == NOW_DT


async def test_odd_package_lists(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """Entries without a number are skipped; numbers are normalised."""
    parcel = add_parcel(engine, "ctt", CTT, carrier="ctt")
    track.response = {
        "packages": [
            None,
            "x",
            {"tracking_number": ""},
            {"tracking_number": None},
            {
                "tracking_number": " rr 100 000 017 pt ",
                "status": "In Transit",
                "friendly_name": "Sapatilhas",
            },
        ]
    }

    await tracker.async_refresh()

    assert track.calls == [get_call(track)]
    assert records(engine)[CTT]["own"] is False
    assert status(engine, parcel.id) is ParcelStatus.IN_TRANSIT

    for response in ({"packages": None}, {}):
        track.response = response
        await tracker.async_refresh()

        assert CTT in records(engine)
        assert tracker.last_error is None
    assert track.calls == [get_call(track)] * 3


async def test_failed_archive_is_retried(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """A failed archive stays visible and is tried again on the next refresh."""
    parcel = add_parcel(engine, "ctt", CTT, carrier="ctt")
    await tracker.async_refresh()
    track.put(CTT, "Delivered", timestamp="2026-11-17T09:50:00+00:00")
    track.errors["archive_package"] = HomeAssistantError("refused")

    await tracker.async_refresh()

    assert status(engine, parcel.id) is ParcelStatus.DELIVERED
    assert tracker.last_error == "archive_package: HomeAssistantError"
    assert "archived" not in records(engine)[CTT]

    del track.errors["archive_package"]
    await tracker.async_refresh()

    assert track.numbers("archive_package") == [CTT, CTT]
    assert records(engine)[CTT]["archived"] == NOW_ISO
    assert tracker.last_error is None


async def test_numbers_17track_cannot_find_are_archived(
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A number still not found after two weeks is archived and not added again."""
    add_parcel(engine, "ctt", CTT, carrier="ctt")
    await tracker.async_refresh()
    await tracker.async_refresh()

    assert records(engine)[CTT]["status"] == "not_found"

    freezer.tick(NOT_FOUND_ARCHIVE - timedelta(days=1))
    await tracker.async_refresh()

    assert track.numbers("archive_package") == []

    freezer.tick(timedelta(days=1))
    await tracker.async_refresh()

    assert track.numbers("archive_package") == [CTT]
    assert records(engine)[CTT]["archived"] == dt_to_str(NOW_DT + NOT_FOUND_ARCHIVE)

    await tracker.async_refresh()

    assert track.numbers("add_package") == [CTT]


async def test_numbers_17track_cannot_follow_are_not_added(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
) -> None:
    """Paack's and SEUR's numbers, and GLS's in Portugal, need the recipient's
    postcode in 17TRACK, and SEUR's also the last digits of their phone.

    Its services take only a number and a name, so these numbers would stay
    "Not Found" and use up places in the account.
    """
    hass.config.country = "PT"
    add_parcel(engine, "paack", PAACK_ID, carrier="paack")
    add_parcel(engine, "paack id", "Wx4Hn8Tz3_1")
    add_parcel(engine, "barcode", PAACK_BARCODE, carrier="other")
    add_parcel(engine, "gls", GLS, carrier="gls")
    add_parcel(engine, "seur", SEUR, carrier="seur")
    ctt = add_parcel(engine, "ctt", CTT, carrier="ctt")

    await tracker.async_refresh()

    assert track.calls == [get_call(track), add_call(track, CTT, ctt)]
    assert set(records(engine)) == {CTT}
    assert failures(engine) == {}


@pytest.mark.parametrize("country", [None, "DE", "IT"])
async def test_gls_is_added_where_it_needs_no_postcode(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
    country: str | None,
) -> None:
    """17TRACK needs GLS's postcode only in some countries."""
    hass.config.country = country
    gls = add_parcel(engine, "gls", GLS, carrier="gls")

    await tracker.async_refresh()

    assert track.calls == [get_call(track), add_call(track, GLS, gls)]


@pytest.mark.parametrize("country", ["ES", "NL", "PT"])
async def test_gls_is_left_out_where_it_needs_a_postcode(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
    country: str,
) -> None:
    """GLS in Spain, the Netherlands and Portugal needs the postcode."""
    hass.config.country = country
    add_parcel(engine, "gls", GLS, carrier="gls")

    await tracker.async_refresh()

    assert track.calls == [get_call(track)]


async def test_numbers_17track_cannot_follow_leave_it(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
) -> None:
    """Such numbers that an earlier release added are archived; the user's stay."""
    hass.config.country = "PT"
    barcode = add_parcel(engine, "barcode", PAACK_BARCODE, carrier="paack")
    gls = add_parcel(engine, "gls", GLS, carrier="gls")
    paack = add_parcel(engine, "paack", PAACK_ID, carrier="paack")
    tracked_before(engine, track, PAACK_BARCODE, barcode, added=NOW_ISO)
    tracked_before(engine, track, GLS, gls)
    # The user added the order ID in the 17TRACK app, with the postcode.
    track.put(PAACK_ID, info="Em distribuição", name="Sapatilhas")

    await tracker.async_refresh()

    assert track.calls == [
        get_call(track),
        archive_call(track, PAACK_BARCODE),
        archive_call(track, GLS),
    ]
    assert records(engine)[PAACK_BARCODE]["archived"] == NOW_ISO
    assert records(engine)[GLS]["archived"] == NOW_ISO
    assert records(engine)[PAACK_ID]["own"] is False
    assert "archived" not in records(engine)[PAACK_ID]
    assert status(engine, paack.id) is ParcelStatus.OUT_FOR_DELIVERY

    track.calls.clear()
    await tracker.async_refresh()

    assert track.calls == [get_call(track)]


async def test_numbers_without_news_for_three_weeks_are_not_added(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """17TRACK stops following a number after 30 days without news.

    So a parcel without news for three weeks, and no date still to come, isn't
    added: not even one first read today from an old e-mail. Hand-added
    parcels count from when they were added.
    """
    three_weeks = timedelta(days=21)
    attempted = MailKind.ATTEMPTED
    add_parcel(engine, "quiet", CTT, carrier="ctt", kind=attempted, age=three_weeks)
    add_parcel(
        engine,
        "recent",
        OTHER,
        carrier="ctt",
        kind=attempted,
        age=three_weeks - timedelta(days=1),
    )
    add_parcel(
        engine,
        "expected",
        s10(10000003),
        carrier="ctt",
        kind=attempted,
        age=timedelta(days=30),
        eta=Eta(start=TODAY - timedelta(days=22), end=TODAY - timedelta(days=20)),
    )
    engine.add_parcel(s10(10000004), carrier="ctt")
    old = engine.add_parcel(s10(10000005), carrier="ctt")
    engine.data.parcels[old].created -= three_weeks

    await tracker.async_refresh()

    assert sorted(track.numbers("add_package")) == [
        s10(10000002),
        s10(10000003),
        s10(10000004),
    ]


async def test_numbers_without_news_for_three_weeks_leave_17track(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """Parcels' own numbers without news for three weeks are archived."""
    age = timedelta(days=21)
    ours = add_parcel(
        engine, "ours", CTT, carrier="ctt", kind=MailKind.ATTEMPTED, age=age
    )
    theirs = add_parcel(
        engine, "theirs", OTHER, carrier="ctt", kind=MailKind.ATTEMPTED, age=age
    )
    tracked_before(
        engine, track, CTT, ours, added=dt_to_str(NOW_DT - timedelta(days=3))
    )
    tracked_before(engine, track, OTHER, theirs, own=False)

    await tracker.async_refresh()

    assert track.calls == [get_call(track), archive_call(track, CTT)]
    assert records(engine)[CTT]["archived"] == NOW_ISO
    assert "archived" not in records(engine)[OTHER]


async def test_refused_number_that_went_quiet_is_forgotten(
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A refused number isn't tried again once its parcel had no news for long."""
    add_parcel(
        engine,
        "ctt",
        CTT,
        carrier="ctt",
        kind=MailKind.ATTEMPTED,
        age=timedelta(days=20),
    )
    track.errors["add_package"] = HomeAssistantError("refused")

    await tracker.async_refresh()

    assert set(failures(engine)) == {CTT}

    freezer.tick(timedelta(days=1))
    await tracker.async_refresh()

    assert track.numbers("add_package") == [CTT]
    assert failures(engine) == {}
    assert tracker.diagnostics()["failed"] == 0


async def test_skipped_numbers_leave_room_for_others(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    tracker: SeventeenTrackSync,
    track: FakeSeventeenTrack,
) -> None:
    """Numbers that aren't added don't count toward the ten per refresh."""
    hass.config.country = "PT"
    today = Eta(start=TODAY, end=TODAY)
    add_parcel(engine, "paack", PAACK_ID, carrier="paack", eta=today)
    add_parcel(engine, "gls", GLS, carrier="gls", eta=today)
    add_parcel(
        engine,
        "quiet",
        s10(30000000),
        carrier="ctt",
        kind=MailKind.ATTEMPTED,
        age=timedelta(days=30),
        eta=Eta(start=TODAY - timedelta(days=25), end=TODAY - timedelta(days=23)),
    )
    numbers = [s10(30000001 + index) for index in range(MAX_ADDS)]
    for index, number in enumerate(numbers):
        add_parcel(engine, f"parcel{index}", number, carrier="ctt")

    await tracker.async_refresh()

    assert track.numbers("add_package") == numbers


async def test_diagnostics_count_numbers_not_found_by_carrier(
    engine: ParcelsEngine, tracker: SeventeenTrackSync
) -> None:
    """Tracked numbers 17TRACK can't find, counted by carrier, without numbers."""
    numbers = {
        "gls": GLS,
        "gls user": "61234567891",
        "dpd": "09981234567890",
        "no carrier": "ZX81234567",
        "odd carrier": "EX123456789",
        "gone": OTHER,
        "in transit": CTT,
        "archived": s10(10000003),
        "unread": s10(10000004),
        "expired": s10(10000005),
    }
    carriers = {
        "gls": "gls",
        "gls user": "gls",
        "dpd": "dpd",
        "odd carrier": "Transportes Exemplo",
        "archived": "dpd",
        "unread": "dpd",
        "expired": "dpd",
    }
    parcels = {
        name: add_parcel(engine, name, number, carrier=carriers.get(name, "ctt"))
        for name, number in numbers.items()
        if name != "no carrier"
    }
    parcels["no carrier"] = add_parcel(engine, "no carrier", numbers["no carrier"])
    del engine.data.parcels[parcels["gone"].id]
    statuses = {"in transit": "in_transit", "unread": None, "expired": "expired"}
    packages = engine.data.seventeentrack.setdefault("packages", {})
    for name, number in numbers.items():
        record: dict[str, Any] = {
            "parcel": parcels[name].id,
            "own": name != "gls user",
        }
        if (stored := statuses.get(name, "not_found")) is not None:
            record["status"] = stored
        if name == "archived":
            record["archived"] = NOW_ISO
        packages[number] = record

    diagnostics = tracker.diagnostics()

    assert diagnostics["not_found_by_carrier"] == {
        "dpd": 1,
        "gls": 2,
        "other": 1,
        "unknown": 2,
    }
    assert list(diagnostics["not_found_by_carrier"]) == [
        "dpd",
        "gls",
        "other",
        "unknown",
    ]
    text = str(diagnostics)
    for name, number in numbers.items():
        assert number not in text
        assert parcels[name].id not in text
    assert "Transportes" not in text


async def test_corrected_number_replaces_the_old_one(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """When the user corrects the number, the old package and its news go."""
    parcel = add_parcel(engine, "ctt", CTT, carrier="ctt")
    await tracker.async_refresh()
    track.put(CTT)
    await tracker.async_refresh()

    assert status(engine, parcel.id) is ParcelStatus.IN_TRANSIT

    update_parcel(engine.data, parcel.id, {"tracking_number": OTHER}, dt_util.utcnow())
    engine.async_changed()
    track.calls.clear()
    await tracker.async_refresh()

    assert track.calls == [
        get_call(track),
        add_call(track, OTHER, parcel),
        archive_call(track, CTT),
    ]
    assert set(records(engine)) == {OTHER}
    assert origin_id(CTT) not in engine.data.parcels[parcel.id].origins
    assert news(engine, parcel.id, CTT) == []
    assert status(engine, parcel.id) is ParcelStatus.SHIPPED


async def test_merged_parcels_keep_their_current_number(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """After a merge the record follows the parcel and the other number goes."""
    first = add_parcel(engine, "first", LEGACY, carrier="ctt", age=timedelta(hours=2))
    second = add_parcel(engine, "second", CTT, carrier="ctt")
    await tracker.async_refresh()
    track.put(LEGACY)
    track.put(CTT)
    await tracker.async_refresh()

    merge_parcels(engine.data, first.id, [second.id], dt_util.utcnow())
    engine.async_changed()
    track.calls.clear()
    await tracker.async_refresh()

    assert track.calls == [get_call(track), archive_call(track, LEGACY)]
    assert set(records(engine)) == {CTT}
    assert records(engine)[CTT]["parcel"] == first.id
    merged = engine.data.parcels[first.id]
    assert merged.state.tracking_number == CTT
    assert [oid for oid in merged.origins if oid.startswith("17t:")] == [origin_id(CTT)]
    assert news(engine, first.id, LEGACY) == []
    assert len(news(engine, first.id, CTT)) == 1


async def test_private_and_deleted_parcels_are_archived(
    engine: ParcelsEngine, tracker: SeventeenTrackSync, track: FakeSeventeenTrack
) -> None:
    """Numbers of private or deleted parcels leave 17TRACK."""
    hidden = add_parcel(engine, "hidden", CTT, carrier="ctt")
    gone = add_parcel(engine, "gone", OTHER, carrier="ctt")
    await tracker.async_refresh()

    update_parcel(engine.data, hidden.id, {"private": True}, dt_util.utcnow())
    del engine.data.parcels[gone.id]
    engine.async_changed()
    track.calls.clear()
    await tracker.async_refresh()

    assert track.calls == [
        get_call(track),
        archive_call(track, CTT),
        archive_call(track, OTHER),
    ]
    assert records(engine) == {
        CTT: {
            "parcel": hidden.id,
            "own": True,
            "added": NOW_ISO,
            "status": "not_found",
            "archived": NOW_ISO,
        }
    }
    assert tracker.diagnostics()["tracked"] == 0
    assert tracker.diagnostics()["archived"] == 1

    del engine.data.parcels[hidden.id]
    engine.async_changed()
    track.calls.clear()
    await tracker.async_refresh()

    assert track.calls == [get_call(track)]
    assert records(engine) == {}


async def test_refresh_schedule(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    track: FakeSeventeenTrack,
    refreshes: list[asyncio.Task[Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A minute after the start, then every 30 minutes, or 10 on delivery day."""
    assert await advance(hass, freezer, refreshes, timedelta(seconds=50)) == 0
    assert await advance(hass, freezer, refreshes, timedelta(seconds=11)) == 1
    assert track.calls == [get_call(track)]

    assert await advance(hass, freezer, refreshes, timedelta(minutes=29)) == 0
    add_parcel(engine, "today", CTT, carrier="ctt", eta=Eta(start=TODAY, end=TODAY))
    assert await advance(hass, freezer, refreshes, timedelta(minutes=2)) == 1
    assert track.numbers("add_package") == [CTT]

    assert await advance(hass, freezer, refreshes, timedelta(minutes=9)) == 0
    assert await advance(hass, freezer, refreshes, timedelta(minutes=2)) == 1
    assert track.count("get_packages") == 3


async def test_options_turn_the_sync_off_and_on(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    track: FakeSeventeenTrack,
    refreshes: list[asyncio.Task[Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Turning 17TRACK off stops the refreshes; turning it on refreshes soon."""
    tracker = engine.tracker
    assert tracker is not None
    hub = engine.entry

    hass.config_entries.async_update_entry(
        hub, options={**hub.options, CONF_SEVENTEENTRACK: False}
    )
    await hass.async_block_till_done()

    assert await advance(hass, freezer, refreshes, timedelta(minutes=31)) == 0
    await tracker.async_refresh()
    assert await advance(hass, freezer, refreshes, timedelta(minutes=31)) == 0
    assert track.calls == []

    hass.config_entries.async_update_entry(
        hub, options={**hub.options, CONF_SEVENTEENTRACK: True}
    )
    await hass.async_block_till_done()

    assert await advance(hass, freezer, refreshes, timedelta(seconds=3)) == 0
    assert await advance(hass, freezer, refreshes, timedelta(seconds=3)) == 1
    assert track.calls == [get_call(track)]

    # A refresh is already planned: options changes don't bring it forward.
    tracker.reconfigure()
    assert await advance(hass, freezer, refreshes, timedelta(seconds=10)) == 0

    await tracker.async_stop()
    tracker.reconfigure()
    assert await advance(hass, freezer, refreshes, timedelta(minutes=31)) == 0
    assert track.calls == [get_call(track)]


async def test_nothing_without_the_integration(hass: HomeAssistant) -> None:
    """Without a loaded 17TRACK entry the sync does nothing."""
    add_hub(hass)
    engine = await async_setup_parcels(hass)
    tracker = engine.tracker
    assert tracker is not None
    await tracker.async_stop()
    add_parcel(engine, "ctt", CTT, carrier="ctt")

    await tracker.async_refresh()

    assert tracker.diagnostics() == {
        "enabled": True,
        "available": False,
        "tracked": 0,
        "archived": 0,
        "failed": 0,
        "last_refresh": None,
        "last_error": None,
        "not_found_by_carrier": {},
    }


async def test_nothing_when_turned_off(
    hass: HomeAssistant, track: FakeSeventeenTrack
) -> None:
    """With 17TRACK off in the options no number is sent."""
    add_hub(hass, **{CONF_SEVENTEENTRACK: False})
    engine = await async_setup_parcels(hass)
    tracker = engine.tracker
    assert tracker is not None
    add_parcel(engine, "ctt", CTT, carrier="ctt")

    await tracker.async_refresh()

    assert track.calls == []
    assert tracker.diagnostics()["enabled"] is False
    assert tracker.diagnostics()["available"] is False
    assert records(engine) == {}
