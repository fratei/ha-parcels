"""Tests for the rules the sensors and the calendar share."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Any

from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import ParcelStatus
from custom_components.parcels.models import Origin, Parcel, ParcelEvent, Source
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.summary import (
    KIND_DELIVERED,
    KIND_ETA,
    KIND_PICKUP,
    KIND_RETURNED,
    KIND_STATUS,
    Placement,
    arriving_today,
    count,
    delivered_today,
    in_transit,
    parcel_attributes,
    parcel_title,
    placement,
    window_bounds,
)

S = ParcelStatus
# Tuesday 17 November 2026: Lisbon is on UTC+0 in November and UTC+1 in July.
TODAY = date(2026, 11, 17)
CREATED = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def lisbon() -> Generator[None]:
    """Use the Lisbon time zone for local dates."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Lisbon"))
    yield
    dt_util.set_default_time_zone(previous)


def day(number: int) -> date:
    """Return a day of November 2026."""
    return date(2026, 11, number)


def nov(number: int, hour: int = 9, minute: int = 0) -> datetime:
    """Return a time in November 2026, when Lisbon time is UTC."""
    return datetime(2026, 11, number, hour, minute, tzinfo=UTC)


def step(status: ParcelStatus, when: datetime, eta: Eta | None = None) -> ParcelEvent:
    """Return a status change read from an e-mail."""
    return ParcelEvent(
        time=when, source=Source.PARSER, origin="o1", status=status, eta=eta
    )


def build(
    *events: ParcelEvent,
    parcel_id: str = "p1",
    private: bool = False,
    **origin: Any,
) -> Parcel:
    """Return a parcel made of one e-mail and its status changes."""
    return Parcel(
        id=parcel_id,
        created=CREATED,
        updated=CREATED,
        origins={"o1": Origin(id="o1", source=Source.PARSER, time=CREATED, **origin)},
        events=list(events),
        private=private,
    )


@pytest.mark.parametrize(
    ("today", "expected"), [(day(16), False), (day(17), False), (day(18), True)]
)
def test_arriving_on_the_last_day_of_the_estimate(today: date, expected: bool) -> None:
    """A parcel expected from the 16th to the 18th arrives on the 18th."""
    parcel = build(step(S.IN_TRANSIT, nov(15), Eta(day(16), day(18))))

    assert arriving_today(parcel.state, today) is expected


@pytest.mark.parametrize(
    "status", [S.DELIVERED, S.RETURNED, S.CANCELLED, S.READY_FOR_PICKUP]
)
def test_finished_or_waiting_parcels_are_not_arriving(status: ParcelStatus) -> None:
    """Delivered, returned, cancelled and pickup parcels never arrive."""
    parcel = build(step(S.SHIPPED, nov(16), Eta(TODAY, TODAY)), step(status, nov(17)))

    assert parcel.state.eta == Eta(TODAY, TODAY)
    assert not arriving_today(parcel.state, TODAY)


def test_out_for_delivery_since_today_is_arriving() -> None:
    """A parcel out for delivery since today arrives today despite a longer ETA."""
    parcel = build(step(S.OUT_FOR_DELIVERY, nov(17, 7), Eta(TODAY, day(19))))

    assert arriving_today(parcel.state, TODAY)
    assert not arriving_today(parcel.state, day(18))
    assert arriving_today(parcel.state, day(19))


def test_out_for_delivery_since_yesterday_is_not_arriving() -> None:
    """A parcel still out for delivery from yesterday isn't expected today."""
    parcel = build(step(S.OUT_FOR_DELIVERY, nov(16, 7)))

    assert parcel.state.eta == Eta(day(16), day(16))
    assert arriving_today(parcel.state, day(16))
    assert not arriving_today(parcel.state, TODAY)


def test_out_for_delivery_counts_on_the_local_day() -> None:
    """Out for delivery at 00:30 in Lisbon summer time counts for that day."""
    when = datetime(2026, 7, 14, 23, 30, tzinfo=UTC)
    parcel = build(
        step(S.OUT_FOR_DELIVERY, when, Eta(date(2026, 7, 15), date(2026, 7, 17)))
    )

    assert arriving_today(parcel.state, date(2026, 7, 15))
    assert not arriving_today(parcel.state, date(2026, 7, 14))


def test_parcel_without_estimate_is_not_arriving() -> None:
    """A shipped parcel without an estimate isn't expected on any day."""
    parcel = build(step(S.SHIPPED, nov(17)))

    assert not arriving_today(parcel.state, TODAY)


PARIS_HALF_PAST_MIDNIGHT = datetime(
    2026, 11, 17, 0, 30, tzinfo=timezone(timedelta(hours=1))
)
JULY_HALF_PAST_ELEVEN_UTC = datetime(2026, 7, 14, 23, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("delivered", "today", "expected"),
    [
        # 00:30 in Paris is still 23:30 on the 16th in Lisbon.
        (PARIS_HALF_PAST_MIDNIGHT, day(16), True),
        (PARIS_HALF_PAST_MIDNIGHT, day(17), False),
        # 23:30 UTC in July is already 00:30 on the 15th in Lisbon.
        (JULY_HALF_PAST_ELEVEN_UTC, date(2026, 7, 15), True),
        (JULY_HALF_PAST_ELEVEN_UTC, date(2026, 7, 14), False),
    ],
)
def test_delivered_today_uses_the_local_day(
    delivered: datetime, today: date, expected: bool
) -> None:
    """The delivery day is the day in Home Assistant's time zone."""
    parcel = build(
        step(S.SHIPPED, delivered - timedelta(days=2)), step(S.DELIVERED, delivered)
    )

    assert delivered_today(parcel.state, today) is expected


def test_delivered_today_keeps_the_first_delivery() -> None:
    """A second delivery e-mail the next morning doesn't move the delivery day."""
    parcel = build(
        step(S.SHIPPED, nov(15)),
        step(S.DELIVERED, nov(16, 18)),
        step(S.DELIVERED, nov(17, 8)),
    )

    assert delivered_today(parcel.state, day(16))
    assert not delivered_today(parcel.state, TODAY)


def test_undelivered_parcel_is_not_delivered_today() -> None:
    """Only delivered parcels count as delivered today."""
    parcel = build(step(S.OUT_FOR_DELIVERY, nov(17)))

    assert not delivered_today(parcel.state, TODAY)


@pytest.mark.parametrize(
    ("origin", "title"),
    [
        pytest.param(
            {"merchant": " Fnac \n Portugal ", "carrier": "ctt"},
            "Fnac Portugal",
            id="merchant",
        ),
        pytest.param(
            {"merchant": "   ", "carrier": "ctt", "tracking_number": "ZX1234567"},
            "CTT",
            id="carrier",
        ),
        pytest.param(
            {"carrier": "other", "tracking_number": "ZX1234567"},
            "ZX1234567",
            id="other-carrier",
        ),
        pytest.param({"tracking_number": "ZX1234567"}, "ZX1234567", id="number"),
        pytest.param({"items": ("Merino Wool Beanie",)}, "Parcel", id="unnamed"),
    ],
)
def test_parcel_title(origin: dict[str, Any], title: str) -> None:
    """The title is the shop, the carrier or the number, never an item."""
    parcel = build(step(S.SHIPPED, nov(16)), **origin)

    assert parcel_title(parcel) == title


def test_parcel_attributes() -> None:
    """Attributes show the estimate, shop, carrier and number, never items."""
    parcel = build(
        step(S.IN_TRANSIT, nov(16), Eta(day(18), day(20))),
        merchant="Zalando",
        carrier="dpd",
        tracking_number="ZX1234567",
        items=("Merino Wool Beanie",),
    )

    assert parcel_attributes(parcel) == {
        "id": "p1",
        "status": "in_transit",
        "eta_start": "2026-11-18",
        "eta_end": "2026-11-20",
        "window_start": None,
        "window_end": None,
        "merchant": "Zalando",
        "carrier": "DPD",
        "tracking_number": "ZX1234567",
    }


def test_private_parcel_shows_no_details() -> None:
    """A private parcel is titled "Private parcel" and hides shop and number."""
    parcel = build(
        step(S.OUT_FOR_DELIVERY, nov(17, 8), Eta(TODAY, TODAY, time(13), time(14))),
        private=True,
        merchant="Zalando",
        carrier="dpd",
        tracking_number="ZX1234567",
        items=("Merino Wool Beanie",),
    )

    assert parcel_title(parcel) == "Private parcel"
    assert parcel_attributes(parcel) == {
        "id": "p1",
        "status": "out_for_delivery",
        "eta_start": "2026-11-17",
        "eta_end": "2026-11-17",
        "window_start": "13:00",
        "window_end": "14:00",
        "private": True,
    }


@pytest.mark.parametrize(
    ("events", "expected"),
    [
        pytest.param(
            [step(S.SHIPPED, nov(15)), step(S.CANCELLED, nov(16))], None, id="cancelled"
        ),
        pytest.param(
            [
                step(S.SHIPPED, nov(15), Eta(day(19), day(19))),
                step(S.DELIVERED, nov(17, 10)),
            ],
            Placement(KIND_DELIVERED, day(17), day(17)),
            id="delivered-before-estimate",
        ),
        pytest.param(
            [
                step(S.SHIPPED, nov(10)),
                step(S.DELIVERED, nov(12)),
                step(S.RETURNED, nov(15)),
            ],
            Placement(KIND_RETURNED, day(15), day(15)),
            id="returned",
        ),
        pytest.param(
            [step(S.READY_FOR_PICKUP, nov(15), Eta(day(15), day(22)))],
            Placement(KIND_PICKUP, day(15), TODAY),
            id="waiting-since-the-15th",
        ),
        pytest.param(
            [step(S.IN_TRANSIT, nov(15), Eta(day(18), day(20)))],
            Placement(KIND_ETA, day(18), day(20)),
            id="estimate",
        ),
        pytest.param(
            [step(S.ATTEMPTED, nov(16), Eta(day(18), day(18)))],
            Placement(KIND_ETA, day(18), day(18)),
            id="attempted-with-estimate",
        ),
        pytest.param(
            [step(S.ATTEMPTED, nov(16))],
            Placement(KIND_STATUS, day(16), day(16)),
            id="attempted",
        ),
        pytest.param(
            [step(S.EXCEPTION, nov(16))],
            Placement(KIND_STATUS, day(16), day(16)),
            id="exception",
        ),
        pytest.param([step(S.SHIPPED, nov(16))], None, id="no-estimate"),
    ],
)
def test_placement(events: list[ParcelEvent], expected: Placement | None) -> None:
    """Each status covers its own days in the calendar."""
    assert placement(build(*events), TODAY) == expected


@pytest.mark.parametrize(
    ("when", "offset"),
    [
        (datetime(2026, 7, 15, 7, 0, tzinfo=UTC), "+01:00"),
        (datetime(2026, 11, 17, 7, 0, tzinfo=UTC), "+00:00"),
    ],
)
def test_window_bounds_are_local_times(when: datetime, offset: str) -> None:
    """A one-day window becomes times in Home Assistant's time zone."""
    on = when.date()
    parcel = build(step(S.OUT_FOR_DELIVERY, when, Eta(on, on, time(13), time(14, 30))))

    bounds = window_bounds(parcel, placement(parcel, on))

    assert bounds is not None
    assert [bound.isoformat() for bound in bounds] == [
        f"{on}T13:00:00{offset}",
        f"{on}T14:30:00{offset}",
    ]


@pytest.mark.parametrize(
    "events",
    [
        pytest.param(
            [step(S.IN_TRANSIT, nov(16), Eta(day(18), day(19), time(9), time(12)))],
            id="several-days",
        ),
        pytest.param(
            [step(S.IN_TRANSIT, nov(16), Eta(day(18), day(18), time(14), time(13)))],
            id="inverted",
        ),
        pytest.param(
            [step(S.IN_TRANSIT, nov(16), Eta(day(18), day(18), time(9)))],
            id="open-ended",
        ),
        pytest.param(
            [step(S.IN_TRANSIT, nov(16), Eta(day(18), day(18)))], id="no-window"
        ),
        pytest.param(
            [
                step(
                    S.OUT_FOR_DELIVERY,
                    nov(17, 8),
                    Eta(TODAY, TODAY, time(13), time(14)),
                ),
                step(S.DELIVERED, nov(17, 13, 20)),
            ],
            id="delivered",
        ),
    ],
)
def test_window_bounds_need_a_one_day_window(events: list[ParcelEvent]) -> None:
    """Only an undelivered one-day estimate with a proper window gets times."""
    parcel = build(*events)
    place = placement(parcel, TODAY)

    assert place is not None
    assert window_bounds(parcel, place) is None


def test_count_lists_matches_newest_first() -> None:
    """count keeps the parcels matching a rule, latest status change first."""
    older = build(step(S.IN_TRANSIT, nov(15)), parcel_id="older")
    newer = build(step(S.OUT_FOR_DELIVERY, nov(17, 8)), parcel_id="newer")
    delivered = build(step(S.DELIVERED, nov(17, 9)), parcel_id="delivered")
    parcels = [older, delivered, newer]

    assert [p.id for p in count(parcels, in_transit)] == ["newer", "older"]
    assert [p.id for p in count(parcels, arriving_today, TODAY)] == ["newer"]
