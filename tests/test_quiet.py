"""Tests for tracked parcels without news for three weeks: probably delivered."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import DOMAIN, MailKind, ParcelStatus
from custom_components.parcels.dedup import (
    apply_contribution,
    infer_deliveries,
    undo_inferred_delivery,
    update_parcel,
)
from custom_components.parcels.engine import ParcelsEngine
from custom_components.parcels.models import ParcelsData, dt_to_str
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.quiet import infer_quiet_deliveries
from custom_components.parcels.store import apply_retention
from custom_components.parcels.views import SYSTEM_VIEWER, Viewer, details, parcel_json

from .common import add_hub, async_setup_parcels
from .factories import T0, at, contribution

NUMBER = "RR482915732PT"
ON_THE_WAY = {
    ParcelStatus.SHIPPED,
    ParcelStatus.IN_TRANSIT,
    ParcelStatus.OUT_FOR_DELIVERY,
}
# Due on Tuesday 3 and Wednesday 4 November 2026.
DUE = Eta(start=date(2026, 11, 3), end=date(2026, 11, 4))


@pytest.fixture(autouse=True)
def lisbon() -> Generator[None]:
    """Use the Lisbon time zone (UTC in November) for local dates."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Lisbon"))
    yield
    dt_util.set_default_time_zone(previous)


def track(
    data: ParcelsData,
    *,
    kind: MailKind = MailKind.IN_TRANSIT,
    status: ParcelStatus | None = None,
    time: datetime = T0,
    eta: Eta | None = None,
) -> str:
    """Add what a carrier's e-mail said about a tracked parcel; return its ID."""
    return apply_contribution(
        data,
        contribution(
            "msg:carrier#0",
            kind=kind,
            status=status,
            time=time,
            carrier="ctt",
            number=NUMBER,
            eta=eta,
        ),
        time,
    ).parcel_id


def test_parcel_quiet_for_three_weeks_was_probably_delivered() -> None:
    """Three weeks after its last expected day, once, at midday that day."""
    data = ParcelsData()
    parcel_id = track(data, eta=DUE)
    parcel = data.parcels[parcel_id]

    assert (
        infer_quiet_deliveries(data, datetime(2026, 11, 24, 23, 59, tzinfo=UTC))
        == set()
    )
    assert parcel.state.status is ParcelStatus.IN_TRANSIT

    now = datetime(2026, 11, 25, 0, 1, tzinfo=UTC)
    assert infer_quiet_deliveries(data, now) == {parcel_id}

    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert state.inferred
    assert state.delivered_at == datetime(2026, 11, 4, 12, tzinfo=UTC)
    assert parcel.state.inferred_reason == "quiet"
    assert parcel.updated == now
    assert infer_quiet_deliveries(data, now + timedelta(days=1)) == set()
    assert sum(event.inferred for event in parcel.events) == 1


@pytest.mark.parametrize("status", list(ParcelStatus))
def test_only_parcels_on_their_way(status: ParcelStatus) -> None:
    """Not orders, problems, attempts, pickups or finished parcels."""
    data = ParcelsData()
    parcel_id = track(data, status=status)
    assert data.parcels[parcel_id].state.status is status

    changed = infer_quiet_deliveries(data, at(days=30))

    assert (parcel_id in changed) is (status in ON_THE_WAY)


def test_only_tracked_parcels() -> None:
    """Parcels without a carrier number are the shop rule's (dedup)."""
    data = ParcelsData()
    parcel_id = apply_contribution(
        data,
        contribution("msg:shop#0", merchant="Loja Exemplo", orders=["ENC-1001"]),
        T0,
    ).parcel_id
    assert data.parcels[parcel_id].state.status is ParcelStatus.SHIPPED

    assert infer_quiet_deliveries(data, at(days=60)) == set()


def test_archived_parcels_are_left_alone() -> None:
    data = ParcelsData()
    parcel_id = track(data)
    data.parcels[parcel_id].archived = at(days=10)

    assert infer_quiet_deliveries(data, at(days=30)) == set()
    assert data.parcels[parcel_id].state.status is ParcelStatus.IN_TRANSIT


@pytest.mark.parametrize(
    ("kind", "time", "eta", "delivered"),
    [
        # Due after its last news: midday on its last expected day.
        (MailKind.IN_TRANSIT, T0, DUE, datetime(2026, 11, 4, 12, tzinfo=UTC)),
        # Out for delivery in the morning: midday that day.
        (MailKind.OUT_FOR_DELIVERY, T0, None, datetime(2026, 11, 2, 12, tzinfo=UTC)),
        # Out for delivery in the afternoon: then.
        (MailKind.OUT_FOR_DELIVERY, at(hours=6), None, at(hours=6)),
        # News after its last expected day: then.
        (MailKind.IN_TRANSIT, at(days=3, hours=6.5), DUE, at(days=3, hours=6.5)),
        # No expected dates: its last news.
        (MailKind.SHIPPED, T0, None, T0),
    ],
)
def test_probable_delivery_time(
    kind: MailKind, time: datetime, eta: Eta | None, delivered: datetime
) -> None:
    """The calendar shows it on its expected day, after its last news."""
    data = ParcelsData()
    parcel_id = track(data, kind=kind, time=time, eta=eta)

    assert infer_quiet_deliveries(data, at(days=40)) == {parcel_id}
    assert data.parcels[parcel_id].state.delivered_at == delivered


def test_midday_is_local() -> None:
    """Midday in Home Assistant's time zone, stored in UTC."""
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Madrid"))
    data = ParcelsData()
    parcel_id = track(data, eta=DUE)

    infer_quiet_deliveries(data, at(days=40))

    delivered = data.parcels[parcel_id].state.delivered_at
    assert dt_to_str(delivered) == "2026-11-04T11:00:00+00:00"


def test_archived_at_once_and_undone_for_good() -> None:
    """It finished weeks ago, so retention archives it; Undo brings it back."""
    data = ParcelsData()
    parcel_id = track(data)
    now = at(days=21)
    infer_quiet_deliveries(data, now)

    assert apply_retention(data, now).archived == [parcel_id]

    undo_inferred_delivery(data, parcel_id, now)
    parcel = data.parcels[parcel_id]
    assert parcel.state.status is ParcelStatus.IN_TRANSIT
    assert parcel.archived is None
    assert parcel.delivery_rejected
    assert infer_quiet_deliveries(data, now + timedelta(days=1)) == set()
    assert parcel.state.status is ParcelStatus.IN_TRANSIT


def test_kept_delivery_is_no_longer_inferred() -> None:
    data = ParcelsData()
    parcel_id = track(data)
    now = at(days=21)
    infer_quiet_deliveries(data, now)

    update_parcel(data, parcel_id, {"confirm_delivery": True}, now)

    parcel = data.parcels[parcel_id]
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert not parcel.state.inferred
    assert parcel.state.inferred_reason is None


def test_news_takes_the_delivery_back() -> None:
    """A late e-mail about the parcel replaces the guess, even once archived."""
    data = ParcelsData()
    parcel_id = track(data)
    now = at(days=22)
    infer_quiet_deliveries(data, now)
    data.parcels[parcel_id].archived = now

    apply_contribution(
        data,
        contribution(
            "msg:carrier2#0",
            kind=MailKind.OUT_FOR_DELIVERY,
            time=now,
            carrier="ctt",
            number=NUMBER,
        ),
        now,
    )

    parcel = data.parcels[parcel_id]
    assert parcel.state.status is ParcelStatus.OUT_FOR_DELIVERY
    assert not parcel.state.inferred
    assert parcel.state.inferred_reason is None
    assert parcel.archived is None
    assert infer_quiet_deliveries(data, now) == set()


def test_page_says_why_a_delivery_was_inferred() -> None:
    """A shop's other delivery, or three weeks without news; never to strangers."""
    data = ParcelsData()
    delivered = at(days=11, hours=1.5)
    carrier_id = apply_contribution(
        data,
        contribution(
            "msg:carrier#0",
            kind=MailKind.DELIVERED,
            time=delivered,
            carrier="ctt_expresso",
            number="EX123456789012",
            merchant="Loja Exemplo",
        ),
        delivered,
    ).parcel_id
    shop_id = apply_contribution(
        data,
        contribution(
            "msg:order#0",
            time=at(days=9),
            merchant="Loja Exemplo",
            orders=["ENC-1001"],
            eta=Eta(start=date(2026, 11, 12), end=date(2026, 11, 12)),
        ),
        at(days=9),
    ).parcel_id
    quiet_id = apply_contribution(
        data,
        contribution(
            "msg:quiet#0", kind=MailKind.IN_TRANSIT, carrier="ctt", number=NUMBER
        ),
        T0,
    ).parcel_id
    now = at(days=30)

    assert infer_deliveries(data, now) == {shop_id}
    assert infer_quiet_deliveries(data, now) == {quiet_id}

    parcels = data.parcels
    reasons = {
        parcel_id: parcel_json(parcels[parcel_id], SYSTEM_VIEWER)["inferred_reason"]
        for parcel_id in (carrier_id, shop_id, quiet_id)
    }
    assert reasons == {carrier_id: None, shop_id: "shop", quiet_id: "quiet"}

    parcels[quiet_id].private = True
    stranger = Viewer(is_admin=False, persons=frozenset({"person.two"}))
    shown = parcel_json(parcels[quiet_id], stranger)
    assert shown["restricted"]
    assert shown["inferred"] is False
    assert shown["inferred_reason"] is None


@pytest.fixture
async def engine(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> ParcelsEngine:
    """Load the hub on Monday 30 November 2026, in Lisbon."""
    freezer.move_to("2026-11-30 10:00:00+00:00")
    await hass.config.async_set_time_zone("Europe/Lisbon")
    add_hub(hass)
    return await async_setup_parcels(hass)


async def test_parcels_close_quiet_parcels(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """Reconciling infers the delivery; the details show it; Undo takes it back."""
    data = engine.data
    parcel_id = apply_contribution(
        data,
        contribution(
            "msg:carrier#0",
            kind=MailKind.IN_TRANSIT,
            carrier="ctt",
            number=NUMBER,
            eta=DUE,
        ),
        T0,
    ).parcel_id

    engine.async_changed()

    parcel = data.parcels[parcel_id]
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert parcel.state.inferred
    shown = details(engine, parcel, SYSTEM_VIEWER)
    assert shown["parcel"]["inferred_reason"] == "quiet"
    assert [(entry["status"], entry["source"]) for entry in shown["timeline"]] == [
        ("in_transit", "parser"),
        ("delivered", "quiet"),
    ]

    await hass.services.async_call(
        DOMAIN, "undo_delivery", {"parcel_id": parcel_id}, blocking=True
    )

    assert parcel.state.status is ParcelStatus.IN_TRANSIT
    assert parcel.delivery_rejected
    engine.async_changed()
    assert parcel.state.status is ParcelStatus.IN_TRANSIT
