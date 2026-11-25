"""Tests for shipments of several packages: one delivered, the others probably."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import UTC, date, datetime, timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant.common import async_capture_events

from custom_components.parcels.const import (
    DOMAIN,
    EVENT_DELIVERED,
    EVENT_PARCEL_ADDED,
    EVENT_STATUS_CHANGED,
    KIND_TO_STATUS,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.dedup import (
    apply_contribution,
    mark_delivered,
    reconcile,
    reported_delivery_event,
    update_parcel,
)
from custom_components.parcels.engine import ParcelsEngine, get_engine
from custom_components.parcels.models import (
    ParcelEvent,
    ParcelsData,
    Source,
    local_date,
)
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.siblings import infer_shipment_deliveries
from custom_components.parcels.views import SYSTEM_VIEWER, details

from .common import add_hub, async_setup_parcels
from .factories import at, contribution

SHOP = "bricolage-exemplo.example"
SHOP_NAME = "Bricolage Exemplo"
# Packages of one shipment: numbers in a short run. The first is delivered.
FIRST = "61000012310052"
OTHERS = ("61000012310061", "61000012310071", "61000012310089")
# 40 after the first, and 40 after that one: linked only through it.
LINK = "61000012310453"
FAR = "61000012310859"
# A package of another shipment.
STRANGER = "61000012399995"
# Due on Tuesday 3 and Wednesday 4 November 2026.
DUE = Eta(start=date(2026, 11, 3), end=date(2026, 11, 4))
# Monday 2 November, 07:00: the shop's e-mails.
SENT = at(hours=-2)
# Wednesday 4 November, 11:30.
DELIVERED_AT = at(days=2, hours=2.5)
NOW = at(days=2, hours=9)


@pytest.fixture(autouse=True)
def lisbon() -> Generator[None]:
    """Use the Lisbon time zone (UTC in November) for local dates."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Lisbon"))
    yield
    dt_util.set_default_time_zone(previous)


def _box(
    data: ParcelsData, number: str, eta: Eta | None = DUE, *, owner: str = "person.one"
) -> str:
    """Add the shop's e-mail about one package; return its parcel's ID."""
    return apply_contribution(
        data,
        contribution(
            f"msg:{number}#0",
            time=SENT,
            carrier="gls",
            number=number,
            merchant=SHOP_NAME,
            eta=eta,
            label=SHOP,
            owner=owner,
        ),
        SENT,
    ).parcel_id


def _news(
    data: ParcelsData,
    number: str,
    kind: MailKind,
    when: datetime = DELIVERED_AT,
    *,
    owner: str = "person.one",
) -> str:
    """Add the carrier's e-mail about one package; return its parcel's ID."""
    return apply_contribution(
        data,
        contribution(
            f"msg:{kind}-{number}-{when:%d%H%M}#0",
            kind=kind,
            time=when,
            carrier="gls",
            number=number,
            owner=owner,
        ),
        when,
    ).parcel_id


def _infer(data: ParcelsData, parcel_id: str) -> None:
    """Give a parcel a delivery Parcels inferred from another package."""
    parcel = data.parcels[parcel_id]
    parcel.events.append(
        ParcelEvent(
            time=DELIVERED_AT,
            source=Source.PARSER,
            status=ParcelStatus.DELIVERED,
            kind=MailKind.DELIVERED,
            label="shipment",
            inferred=True,
        )
    )
    parcel.touch(DELIVERED_AT)


def test_packages_due_by_then_are_probably_delivered() -> None:
    """Once one package is delivered, the others due by that day probably are."""
    data = ParcelsData()
    first = _box(data, FIRST)
    others = {_box(data, number) for number in OTHERS}
    _news(data, FIRST, MailKind.DELIVERED)

    assert infer_shipment_deliveries(data, NOW) == others
    for parcel_id in others:
        state = data.parcels[parcel_id].state
        assert state.status is ParcelStatus.DELIVERED
        assert state.inferred
        assert state.inferred_reason == "shipment"
        assert state.delivered_at == DELIVERED_AT
        assert not state.delivered_undated
    assert not data.parcels[first].state.inferred
    # Once is enough.
    assert infer_shipment_deliveries(data, NOW) == set()


def _due_later(data: ParcelsData) -> str:
    return _box(data, OTHERS[0], Eta(start=date(2026, 11, 5), end=date(2026, 11, 6)))


def _not_due(data: ParcelsData) -> str:
    return _box(data, OTHERS[0], None)


def _later_news(data: ParcelsData) -> str:
    parcel_id = _box(data, OTHERS[0])
    _news(data, OTHERS[0], MailKind.IN_TRANSIT, at(days=2, hours=3))
    return parcel_id


def _other_shipment(data: ParcelsData) -> str:
    return _box(data, STRANGER)


def _archived(data: ParcelsData) -> str:
    parcel_id = _box(data, OTHERS[0])
    data.parcels[parcel_id].archived = NOW
    return parcel_id


@pytest.mark.parametrize(
    "package",
    [_due_later, _not_due, _later_news, _other_shipment, _archived],
    ids=["due-later", "no-date", "later-news", "other-shipment", "archived"],
)
def test_packages_that_stay_on_their_way(
    package: Callable[[ParcelsData], str],
) -> None:
    """Not when due later, without a date, with later news, of another shipment.

    Nor when the user archived it.
    """
    data = ParcelsData()
    _box(data, FIRST)
    parcel_id = package(data)
    status = data.parcels[parcel_id].state.status
    _news(data, FIRST, MailKind.DELIVERED)

    assert infer_shipment_deliveries(data, NOW) == set()
    assert data.parcels[parcel_id].state.status is status


@pytest.mark.parametrize(
    "kind", [MailKind.ATTEMPTED, MailKind.CUSTOMS, MailKind.READY_FOR_PICKUP]
)
def test_packages_with_news_of_their_own_stay(kind: MailKind) -> None:
    """A missed delivery, a problem or a pickup isn't overruled by another package."""
    data = ParcelsData()
    _box(data, FIRST)
    parcel_id = _box(data, OTHERS[0])
    _news(data, OTHERS[0], kind, at(days=2))
    _news(data, FIRST, MailKind.DELIVERED)

    assert infer_shipment_deliveries(data, NOW) == set()
    assert data.parcels[parcel_id].state.status is KIND_TO_STATUS[kind]


def test_news_from_the_minute_of_the_delivery() -> None:
    """News from the very time another package was delivered isn't later."""
    data = ParcelsData()
    _box(data, FIRST)
    other = _box(data, OTHERS[0])
    _news(data, OTHERS[0], MailKind.OUT_FOR_DELIVERY, DELIVERED_AT)
    _news(data, FIRST, MailKind.DELIVERED)

    assert infer_shipment_deliveries(data, NOW) == {other}


def test_the_first_delivery_closes_the_others() -> None:
    """With two packages delivered, the others came with the first."""
    data = ParcelsData()
    _box(data, FIRST)
    _box(data, OTHERS[0])
    other = _box(data, OTHERS[1])
    _news(data, OTHERS[0], MailKind.DELIVERED, at(days=2, hours=6))
    _news(data, FIRST, MailKind.DELIVERED)

    assert infer_shipment_deliveries(data, NOW) == {other}
    assert data.parcels[other].state.delivered_at == DELIVERED_AT


def _marked(data: ParcelsData, parcel_id: str) -> None:
    mark_delivered(data, parcel_id, DELIVERED_AT)


def _kept(data: ParcelsData, parcel_id: str) -> None:
    _infer(data, parcel_id)
    update_parcel(data, parcel_id, {"confirm_delivery": True}, NOW)


@pytest.mark.parametrize(
    "deliver", [_marked, _kept, _infer], ids=["marked", "kept", "inferred"]
)
def test_only_reported_deliveries_count(
    deliver: Callable[[ParcelsData, str], None],
) -> None:
    """A delivery the user marked, kept or Parcels inferred names no package."""
    data = ParcelsData()
    first = _box(data, FIRST)
    others = [_box(data, number) for number in OTHERS]
    deliver(data, first)
    assert data.parcels[first].state.status is ParcelStatus.DELIVERED

    assert infer_shipment_deliveries(data, NOW) == set()
    for parcel_id in others:
        assert data.parcels[parcel_id].state.status is ParcelStatus.SHIPPED


def test_an_archived_package_still_counts() -> None:
    """The delivered package may have left the lists already."""
    data = ParcelsData()
    first = _box(data, FIRST)
    other = _box(data, OTHERS[0])
    _news(data, FIRST, MailKind.DELIVERED)
    data.parcels[first].archived = NOW

    assert infer_shipment_deliveries(data, NOW) == {other}


def test_a_delivery_known_only_by_its_day() -> None:
    """A delivery on a known day, at a time not known, gives the others that day."""
    data = ParcelsData()
    first = _box(data, FIRST)
    other = _box(data, OTHERS[0])
    held = _box(data, OTHERS[1])
    # Parcel told only the day: the event sits at its start.
    day = datetime(2026, 11, 4, tzinfo=UTC)
    parcel = data.parcels[first]
    parcel.events.append(
        ParcelEvent(
            time=day + timedelta(microseconds=1),
            source=Source.PARCELAPP,
            status=ParcelStatus.DELIVERED,
            undated=True,
            timeless=True,
            by=day + timedelta(days=1, microseconds=-1),
        )
    )
    parcel.touch(NOW)
    # News of the same day may be from after the delivery.
    _news(data, OTHERS[1], MailKind.IN_TRANSIT, at(days=2, hours=-1))

    assert infer_shipment_deliveries(data, NOW) == {other}
    state = data.parcels[other].state
    assert state.inferred_reason == "shipment"
    assert state.delivered_undated
    assert state.delivered_timeless
    assert state.delivered_at is not None
    assert local_date(state.delivered_at) == date(2026, 11, 4)
    assert data.parcels[held].state.status is ParcelStatus.IN_TRANSIT


# Thursday 5 November, 12:00.
LATER = at(days=3, hours=3)


def _report(data: ParcelsData, sent: datetime) -> None:
    """Add an e-mail, read later, saying the first package came but not when."""
    apply_contribution(
        data,
        contribution(
            f"msg:report-{sent:%d%H%M}#0",
            kind=MailKind.DELIVERED,
            time=sent,
            carrier="gls",
            number=FIRST,
            undated=True,
        ),
        LATER,
    )


@pytest.mark.parametrize(
    "reports",
    [(at(days=2, hours=8),), (at(days=3), at(days=2, hours=8))],
    ids=["that-day", "next-day-first"],
)
def test_a_kept_package_keeps_the_day(reports: tuple[datetime, ...]) -> None:
    """Kept, a package came the day its shipment's delivery was reported.

    An e-mail that doesn't say when tells the day only when it was sent on a
    day the packages were expected; of two, the one that tells it counts. A
    shop's order due that day may then be in either package: the user picks.
    """
    data = ParcelsData()
    first = _box(data, FIRST)
    other = _box(data, OTHERS[0])
    for sent in reports:
        _report(data, sent)
    assert infer_shipment_deliveries(data, LATER) == {other}
    update_parcel(data, other, {"confirm_delivery": True}, LATER)
    order = apply_contribution(
        data,
        contribution(
            "msg:order#0",
            kind=MailKind.ORDER,
            time=SENT,
            merchant=SHOP_NAME,
            eta=Eta(start=date(2026, 11, 4), end=date(2026, 11, 4)),
            label=SHOP,
        ),
        LATER,
    ).parcel_id

    result = reconcile(data, LATER)

    assert order in data.parcels
    assert {
        suggestion.parcel_id
        for suggestion in result.suggestions
        if suggestion.candidates == (order,)
    } == {first, other}


def test_a_confirmed_package_reports_its_own_delivery() -> None:
    """Once its own e-mail says so, that e-mail is the package's delivery news.

    An e-mail read again, say after an update, keeps what Parcels inferred.
    """
    data = ParcelsData()
    _box(data, FIRST)
    other = _box(data, OTHERS[0])
    _news(data, FIRST, MailKind.DELIVERED)
    assert infer_shipment_deliveries(data, NOW) == {other}
    # Both came at once.
    apply_contribution(
        data,
        contribution(
            "msg:delivered-again#0",
            kind=MailKind.DELIVERED,
            time=DELIVERED_AT,
            carrier="gls",
            number=OTHERS[0],
        ),
        NOW,
        keep_closed=True,
    )
    assert any(event.inferred for event in data.parcels[other].events)

    event = reported_delivery_event(data.parcels[other])
    assert event is not None
    assert not event.inferred


def test_private_packages_only_for_the_same_people() -> None:
    """A private package counts for the packages of people who all may see it."""
    data = ParcelsData()
    first = _box(data, FIRST)
    _news(data, FIRST, MailKind.DELIVERED, owner="person.two")
    mine = _box(data, OTHERS[0])
    public = _box(data, OTHERS[1])
    theirs = _box(data, OTHERS[2], owner="person.three")
    for parcel_id in (first, mine, theirs):
        data.parcels[parcel_id].private = True

    assert infer_shipment_deliveries(data, NOW) == {mine}
    assert data.parcels[public].state.status is ParcelStatus.SHIPPED
    assert data.parcels[theirs].state.status is ParcelStatus.SHIPPED


@pytest.mark.parametrize("owner", ["", "person.one"], ids=["nobody", "owned"])
def test_private_packages_nobody_owns(owner: str) -> None:
    """Admins see private packages nobody owns, but not always someone's."""
    data = ParcelsData()
    first = _box(data, FIRST, owner=owner)
    _news(data, FIRST, MailKind.DELIVERED, owner=owner)
    nobody = _box(data, OTHERS[0], owner="")
    owned = _box(data, OTHERS[1])
    for parcel_id in (first, nobody, owned):
        data.parcels[parcel_id].private = True

    assert infer_shipment_deliveries(data, NOW) == ({owned} if owner else {nobody})


def test_a_public_delivery_counts_for_private_packages() -> None:
    """Everyone may see a public package."""
    data = ParcelsData()
    _box(data, FIRST)
    _news(data, FIRST, MailKind.DELIVERED)
    mine = _box(data, OTHERS[0])
    data.parcels[mine].private = True

    assert infer_shipment_deliveries(data, NOW) == {mine}


@pytest.mark.parametrize("private", [False, True])
def test_packages_linked_through_a_private_one(private: bool) -> None:
    """Packages linked only through a private package are linked for its owners."""
    data = ParcelsData()
    _box(data, FIRST)
    _news(data, FIRST, MailKind.DELIVERED)
    link = _box(data, LINK)
    far = _box(data, FAR)
    if private:
        data.parcels[link].private = True

    assert infer_shipment_deliveries(data, NOW) == ({link} if private else {link, far})


@pytest.fixture
async def engine(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> ParcelsEngine:
    """Load the hub on Wednesday 4 November 2026, in Lisbon."""
    freezer.move_to("2026-11-04 18:00:00+00:00")
    await hass.config.async_set_time_zone("Europe/Lisbon")
    add_hub(hass)
    return await async_setup_parcels(hass)


async def test_parcels_close_the_other_packages(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """Reconciling infers the deliveries; the details say why; Undo takes one back."""
    data = engine.data
    _box(data, FIRST)
    other = _box(data, OTHERS[0])
    _news(data, FIRST, MailKind.DELIVERED)

    engine.async_changed()

    parcel = data.parcels[other]
    assert parcel.state.status is ParcelStatus.DELIVERED
    shown = details(engine, parcel, SYSTEM_VIEWER)
    assert shown["parcel"]["inferred_reason"] == "shipment"
    assert [(entry["status"], entry["source"]) for entry in shown["timeline"]] == [
        ("shipped", "parser"),
        ("delivered", "inferred_shipment"),
    ]

    await hass.services.async_call(
        DOMAIN, "undo_delivery", {"parcel_id": other}, blocking=True
    )

    assert parcel.state.status is ParcelStatus.SHIPPED
    assert parcel.delivery_rejected
    engine.async_changed()
    assert parcel.state.status is ParcelStatus.SHIPPED


async def test_automations_hear_only_of_reported_deliveries(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """Neither inferring a delivery nor undoing it fires events.

    A delivery the carrier reports later does, after a restart too, as it
    would have without the inference.
    """
    data = engine.data
    first = _box(data, FIRST)
    undone, confirmed = (_box(data, number) for number in OTHERS[:2])
    _news(data, OTHERS[0], MailKind.IN_TRANSIT, at(days=2, hours=1))
    engine.async_changed()
    fired = [
        async_capture_events(hass, event)
        for event in (EVENT_STATUS_CHANGED, EVENT_DELIVERED)
    ]

    _news(data, FIRST, MailKind.DELIVERED)
    engine.async_changed()
    assert data.parcels[undone].state.inferred
    await hass.services.async_call(
        DOMAIN, "undo_delivery", {"parcel_id": undone}, blocking=True
    )
    assert await hass.config_entries.async_reload(engine.entry.entry_id)
    engine = get_engine(hass)
    assert engine is not None
    assert engine.data.parcels[confirmed].state.inferred
    _news(engine.data, OTHERS[1], MailKind.DELIVERED, at(days=2, hours=4))
    engine.async_changed()

    assert [
        [(event.data["parcel_id"], event.data.get("previous_status")) for event in kind]
        for kind in fired
    ] == [
        [(first, "shipped"), (confirmed, "shipped")],
        [(first, None), (confirmed, None)],
    ]


async def test_a_new_package_inferred_at_once(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """A package first read with its shipment's delivery comes with its news."""
    data = engine.data
    first = _box(data, FIRST)
    other = _box(data, OTHERS[0])
    _news(data, FIRST, MailKind.DELIVERED)
    fired = [
        async_capture_events(hass, event)
        for event in (EVENT_PARCEL_ADDED, EVENT_DELIVERED)
    ]

    engine.async_changed()
    assert data.parcels[other].state.inferred
    _news(data, OTHERS[0], MailKind.DELIVERED, at(days=2, hours=4))
    engine.async_changed()

    assert [
        [(event.data["parcel_id"], event.data["status"]) for event in kind]
        for kind in fired
    ] == [[(first, "delivered"), (other, "delivered")]] * 2


async def test_news_an_inference_hid_comes_with_its_undo(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """News read with the shipment's delivery fires if that's taken back."""
    data = engine.data
    first = _box(data, FIRST)
    other = _box(data, OTHERS[0])
    engine.async_changed()
    fired = async_capture_events(hass, EVENT_STATUS_CHANGED)

    _news(data, OTHERS[0], MailKind.OUT_FOR_DELIVERY, at(days=2, hours=2))
    _news(data, FIRST, MailKind.DELIVERED)
    engine.async_changed()
    assert data.parcels[other].state.inferred
    await hass.services.async_call(
        DOMAIN, "undo_delivery", {"parcel_id": other}, blocking=True
    )

    assert [
        (event.data["parcel_id"], event.data["status"], event.data["previous_status"])
        for event in fired
    ] == [(first, "delivered", "shipped"), (other, "out_for_delivery", "shipped")]


@pytest.mark.parametrize(
    ("service", "extra"),
    [("update", {"confirm_delivery": True}), ("mark_delivered", {})],
    ids=["kept", "marked"],
)
async def test_a_delivery_the_user_confirms_is_news(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    service: str,
    extra: dict[str, Any],
) -> None:
    """Keeping an inferred delivery, or marking it, tells automations."""
    data = engine.data
    _box(data, FIRST)
    other = _box(data, OTHERS[0])
    engine.async_changed()
    _news(data, FIRST, MailKind.DELIVERED)
    engine.async_changed()
    fired = [
        async_capture_events(hass, event)
        for event in (EVENT_STATUS_CHANGED, EVENT_DELIVERED)
    ]

    await hass.services.async_call(
        DOMAIN, service, {"parcel_id": other, **extra}, blocking=True
    )

    assert [
        [(event.data["parcel_id"], event.data.get("previous_status")) for event in kind]
        for kind in fired
    ] == [[(other, "shipped")], [(other, None)]]


async def test_a_kept_delivery_reads_as_the_users(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """Keeping it makes it the user's delivery, without the reason's word."""
    data = engine.data
    _box(data, FIRST)
    other = _box(data, OTHERS[0])
    _news(data, FIRST, MailKind.DELIVERED)
    engine.async_changed()

    await hass.services.async_call(
        DOMAIN, "update", {"parcel_id": other, "confirm_delivery": True}, blocking=True
    )

    shown = details(engine, data.parcels[other], SYSTEM_VIEWER)
    assert shown["parcel"]["inferred"] is False
    last = shown["timeline"][-1]
    assert (last["status"], last["source"], last["label"]) == (
        "delivered",
        "manual",
        "",
    )
