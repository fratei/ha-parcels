"""Tests for the Parcels data model and its status machine."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date, datetime, time, timedelta
import json
import logging

from freezegun.api import FrozenDateTimeFactory
from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import LeftAt, MailKind, ParcelStatus
from custom_components.parcels.models import (
    AutoMerge,
    FilteredItem,
    MessageRecord,
    MessageState,
    Order,
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    ParcelShell,
    ParcelState,
    ReviewItem,
    SenderPrefs,
    Source,
    Suggestion,
    dt_from_str,
    known_merchant_name,
    merchant_display,
    merchant_key,
    order_key,
)
from custom_components.parcels.parsers.base import Eta

from .factories import T0, at

S = ParcelStatus


@pytest.fixture
def lisbon() -> Generator[None]:
    """Use the Lisbon time zone for local dates."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Lisbon"))
    yield
    dt_util.set_default_time_zone(previous)


def _origin(origin_id: str = "o1", **kwargs) -> Origin:
    kwargs.setdefault("source", Source.PARSER)
    kwargs.setdefault("time", T0)
    return Origin(id=origin_id, **kwargs)


def _event(status: ParcelStatus | None, when, **kwargs) -> ParcelEvent:
    kwargs.setdefault("source", Source.PARSER)
    kwargs.setdefault("origin", "o1")
    return ParcelEvent(time=when, status=status, **kwargs)


def _carrier(origin_id: str = "o1", **kwargs) -> Origin:
    """Return an origin from an e-mail of the carrier's own domain."""
    return _origin(origin_id, label="ctt.pt", **kwargs)


def _parcel(*events: ParcelEvent, origins: tuple[Origin, ...] = ()) -> Parcel:
    parcel = Parcel(id="p_test", created=T0, updated=T0)
    for origin in origins or (_origin(),):
        parcel.origins[origin.id] = origin
    parcel.events = list(events)
    return parcel


def test_event_time_decides_not_arrival_order() -> None:
    """A late "shipped" e-mail doesn't move a delivered parcel back."""
    parcel = _parcel(
        _event(S.DELIVERED, at(days=2)),
        _event(S.SHIPPED, at()),
        _event(S.OUT_FOR_DELIVERY, at(days=2, hours=-4)),
    )
    state = parcel.state
    assert state.status is S.DELIVERED
    assert state.status_time == at(days=2)
    assert state.delivered_at == at(days=2)
    assert [entry.status for entry in state.timeline] == [
        S.SHIPPED,
        S.OUT_FOR_DELIVERY,
        S.DELIVERED,
    ]


def test_backward_status_is_ignored() -> None:
    """A reminder that the parcel shipped doesn't undo "in transit"."""
    parcel = _parcel(_event(S.IN_TRANSIT, at()), _event(S.SHIPPED, at(days=1)))
    state = parcel.state
    assert state.status is S.IN_TRANSIT
    assert [entry.accepted for entry in state.timeline] == [True, False]


def test_delay_takes_out_for_delivery_back_to_transit() -> None:
    """A delay notice with a new date can follow "out for delivery"."""
    new_eta = Eta(start=date(2026, 11, 4), end=date(2026, 11, 4))
    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at()),
        _event(S.IN_TRANSIT, at(hours=6), kind=MailKind.DELAYED, eta=new_eta),
    )
    assert parcel.state.status is S.IN_TRANSIT
    assert parcel.state.eta == new_eta

    # The carrier's newer news does, without the delay kind too.
    events = (_event(S.OUT_FOR_DELIVERY, at()), _event(S.IN_TRANSIT, at(hours=6)))
    plain = _parcel(*events, origins=(_carrier(),))
    assert plain.state.status is S.IN_TRANSIT
    # A shop's doesn't.
    assert _parcel(*events).state.status is S.OUT_FOR_DELIVERY

    # A delay notice doesn't take a parcel from its pickup point.
    ready = _parcel(
        _event(S.READY_FOR_PICKUP, at()),
        _event(S.IN_TRANSIT, at(hours=6), kind=MailKind.DELAYED, eta=new_eta),
    )
    assert ready.state.status is S.READY_FOR_PICKUP


# Out for delivery, or waiting at a pickup point, can end in more news: the
# carrier takes the parcel back, tries again, or delivers it after all.
NEWS_AFTER = [
    (S.OUT_FOR_DELIVERY, S.IN_TRANSIT),
    (S.READY_FOR_PICKUP, S.IN_TRANSIT),
    (S.READY_FOR_PICKUP, S.OUT_FOR_DELIVERY),
    (S.READY_FOR_PICKUP, S.ATTEMPTED),
]


@pytest.mark.parametrize(("current", "news"), NEWS_AFTER)
@pytest.mark.parametrize("source", [Source.SEVENTEENTRACK, Source.PARCELAPP])
def test_newer_news_wins(
    current: ParcelStatus, news: ParcelStatus, source: Source
) -> None:
    """The newest news decides the status, whichever source gave it."""
    parcel = _parcel(
        _event(S.SHIPPED, at(days=-1)),
        _event(current, at()),
        _event(news, at(hours=2), source=source, origin="o2"),
        origins=(_origin(), _origin("o2", source=source)),
    )
    state = parcel.state
    assert (state.status, state.status_time) == (news, at(hours=2))
    assert [entry.accepted for entry in state.timeline] == [True, True, True]


@pytest.mark.parametrize(("current", "news"), NEWS_AFTER)
@pytest.mark.parametrize("source", [Source.PARSER, Source.AI])
@pytest.mark.parametrize(
    "label",
    [
        "ctt.pt",
        "notifications.cttexpress.com",
        # A shop that sends its carriers' notices from its own domain.
        "leroymerlin.pt",
    ],
)
def test_the_carriers_newer_email_steps_back(
    current: ParcelStatus, news: ParcelStatus, source: Source, label: str
) -> None:
    """The carrier's own e-mail is its news, read by a parser or the AI."""
    parcel = _parcel(
        _event(S.SHIPPED, at(days=-1)),
        _event(current, at()),
        _event(news, at(hours=2), source=source, origin="o2"),
        origins=(_origin(), _origin("o2", source=source, label=label)),
    )
    state = parcel.state
    assert (state.status, state.status_time) == (news, at(hours=2))


# Senders whose e-mails pass on a carrier's news, timed when they were sent:
# a shop, the Shop app, Shopify, an unknown domain and a free mail one.
SHOP_LABELS = ["lumenhaus.example", "shop.app", "shopify.com", "", "gmail.com"]


@pytest.mark.parametrize(("current", "news"), NEWS_AFTER)
@pytest.mark.parametrize("source", [Source.PARSER, Source.AI])
@pytest.mark.parametrize("label", SHOP_LABELS)
def test_a_shops_newer_email_never_steps_back(
    current: ParcelStatus, news: ParcelStatus, source: Source, label: str
) -> None:
    """A shop passes on the carrier's news late: it never takes a step back.

    The parcel stays at its pickup point, with its last day to collect it.
    """
    collect_by = date(2026, 11, 9)
    parcel = _parcel(
        _event(S.SHIPPED, at(days=-1)),
        _event(current, at(), collect_by=collect_by),
        _event(news, at(hours=2), source=source, origin="o2"),
        origins=(_carrier(), _origin("o2", source=source, label=label)),
    )
    state = parcel.state
    assert (state.status, state.status_time) == (current, at())
    assert [entry.accepted for entry in state.timeline] == [True, True, False]
    if current is S.READY_FOR_PICKUP:
        assert state.collect_by == collect_by


@pytest.mark.parametrize(("current", "news"), NEWS_AFTER)
@pytest.mark.parametrize(
    ("label", "own", "number"),
    [
        ("amazon.es", "amazon", "TBA123456789012"),
        ("vinted.pt", "vinted_go", None),
    ],
)
def test_a_shop_whose_own_service_delivers_is_the_carrier(
    current: ParcelStatus,
    news: ParcelStatus,
    label: str,
    own: str,
    number: str | None,
) -> None:
    """A shop's e-mails are the carrier's news when its own service delivers.

    Not when it hands the parcel to a carrier, such as CTT, or when the user
    says another carrier delivers it.
    """

    def state(carrier: str, number: str | None, *edits: Origin) -> ParcelState:
        origins = tuple(
            _origin(oid, label=label, carrier=carrier, tracking_number=number)
            for oid in ("o1", "o2")
        )
        return _parcel(
            _event(current, at()),
            _event(news, at(hours=2), origin="o2"),
            origins=(*origins, *edits),
        ).state

    assert state(own, number).status is news
    assert state("ctt", "RR123456785PT").status is current
    edit = _origin("man:p_test", source=Source.MANUAL, carrier="ctt")
    assert state(own, number, edit).status is current


@pytest.mark.parametrize(("current", "news"), NEWS_AFTER)
def test_late_news_still_never_moves_a_parcel_back(
    current: ParcelStatus, news: ParcelStatus
) -> None:
    """News older than the status, read after it, changes nothing."""
    parcel = _parcel(
        _event(S.SHIPPED, at(days=-1)),
        _event(current, at()),
        _event(news, at(hours=-2), origin="o2"),
        origins=(_carrier(), _carrier("o2")),
    )
    state = parcel.state
    assert (state.status, state.status_time) == (current, at())
    assert [entry.status for entry in state.timeline] == [S.SHIPPED, news, current]


LOCKER = "Locker 12, Rua Inventada 7"


def _at_locker(*events: ParcelEvent, origins: tuple[Origin, ...] = ()) -> Parcel:
    """Return a parcel the carrier left at a locker, followed by more news."""
    ready = _carrier(pickup_point=LOCKER, pickup_code="731905")
    return _parcel(
        _event(S.READY_FOR_PICKUP, at(), collect_by=date(2026, 11, 9)),
        *events,
        origins=(ready, *origins),
    )


def _tracked(when: datetime) -> tuple[Origin, ParcelEvent]:
    """Return 17TRACK's origin and its news: out for delivery then."""
    return (
        _origin("o2", source=Source.SEVENTEENTRACK, time=when),
        _event(S.OUT_FOR_DELIVERY, when, source=Source.SEVENTEENTRACK, origin="o2"),
    )


@pytest.mark.parametrize("news", [S.IN_TRANSIT, S.OUT_FOR_DELIVERY])
@pytest.mark.parametrize(
    ("source", "label"),
    [
        (Source.PARSER, "ctt.pt"),
        (Source.SEVENTEENTRACK, ""),
        (Source.PARCELAPP, ""),
    ],
)
def test_leaving_the_pickup_point_takes_its_details(
    news: ParcelStatus, source: Source, label: str
) -> None:
    """News taking a parcel from its pickup point takes the point's details.

    Out for delivery, the locker's code would read as the delivery PIN.
    """
    parcel = _at_locker(
        _event(news, at(hours=2), source=source, origin="o2"),
        origins=(_origin("o2", source=source, label=label, time=at(hours=2)),),
    )
    state = parcel.state
    assert state.status is news
    assert (state.pickup_point, state.pickup_code, state.collect_by) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize("between", [S.ATTEMPTED, S.EXCEPTION])
def test_leaving_the_pickup_point_after_an_attempt_or_a_problem(
    between: ParcelStatus,
) -> None:
    """A failed attempt or a problem at the pickup point doesn't take it away.

    Leaving it after that does.
    """
    track, out = _tracked(at(days=1))
    attempt = _event(between, at(hours=1), source=Source.SEVENTEENTRACK, origin="o2")
    state = _at_locker(attempt, origins=(track,)).state
    assert (state.status, state.pickup_point, state.pickup_code) == (
        between,
        LOCKER,
        "731905",
    )
    state = _at_locker(attempt, out, origins=(track,)).state
    assert (state.status, state.pickup_point, state.pickup_code) == (
        S.OUT_FOR_DELIVERY,
        None,
        None,
    )


def test_news_after_leaving_the_pickup_point_gives_new_details() -> None:
    """Only news from after the parcel left its pickup point gives details.

    The e-mail that took it away may give a code for the new delivery, and so
    may one sent later. One sent later about its time at the locker doesn't.
    """
    out = _carrier("o2", time=at(hours=2), pickup_code="4826")
    parcel = _at_locker(
        _event(S.OUT_FOR_DELIVERY, at(hours=2), origin="o2"), origins=(out,)
    )
    assert (parcel.state.pickup_point, parcel.state.pickup_code) == (None, "4826")

    # An e-mail with a code and no news counts from when it was sent.
    track, back = _tracked(at(hours=2))
    later = _carrier("o3", time=at(hours=3), pickup_code="5512")
    earlier = _carrier("o3", time=at(hours=1), pickup_code="5512")
    assert _at_locker(back, origins=(track, later)).state.pickup_code == "5512"
    assert _at_locker(back, origins=(track, earlier)).state.pickup_code is None

    late = _carrier("o3", time=at(hours=3), pickup_point="Locker 15", pickup_code="1")
    parcel = _at_locker(
        _event(S.READY_FOR_PICKUP, at(hours=1), origin="o3"),
        back,
        origins=(track, late),
    )
    state = parcel.state
    assert (state.status, state.pickup_point, state.pickup_code) == (
        S.OUT_FOR_DELIVERY,
        None,
        None,
    )


def test_back_at_its_pickup_point_its_details_show_again() -> None:
    """Back at the pickup point it left without going out, its details show.

    Its collect-by date too, unless the news gives a new one. Out for delivery
    and back, it may be at another point, such as a shop after a failed
    attempt: only news from then on counts.
    """
    track = _origin("o2", source=Source.SEVENTEENTRACK, time=at(hours=2))
    away = _event(S.IN_TRANSIT, at(hours=2), source=Source.SEVENTEENTRACK, origin="o2")
    ready = _event(
        S.READY_FOR_PICKUP, at(days=1), source=Source.SEVENTEENTRACK, origin="o2"
    )
    state = _at_locker(away, ready, origins=(track,)).state
    assert (state.status, state.pickup_point, state.pickup_code, state.collect_by) == (
        S.READY_FOR_PICKUP,
        LOCKER,
        "731905",
        date(2026, 11, 9),
    )

    track, out = _tracked(at(hours=2))
    state = _at_locker(out, ready, origins=(track,)).state
    assert (state.status, state.pickup_point, state.pickup_code, state.collect_by) == (
        S.READY_FOR_PICKUP,
        None,
        None,
        None,
    )


def test_back_at_its_pickup_point_its_days_to_collect_come_back() -> None:
    """Back at the point it left without going out, it's expected there again.

    The days to collect it there are its expected date, as before it left,
    unless the news that it's back gives new ones.
    """
    days = _day(2, 9)
    locker = _event(S.READY_FOR_PICKUP, at(), eta=days, collect_by=date(2026, 11, 9))
    point = _carrier(pickup_point=LOCKER, pickup_code="731905")
    track = _origin("o2", source=Source.SEVENTEENTRACK, time=at(hours=2))
    away = _event(S.IN_TRANSIT, at(hours=2), source=Source.SEVENTEENTRACK, origin="o2")
    state = _parcel(locker, away, origins=(point, track)).state
    assert (state.status, state.eta) == (S.IN_TRANSIT, None)

    ready = _event(
        S.READY_FOR_PICKUP, at(days=1), source=Source.SEVENTEENTRACK, origin="o2"
    )
    state = _parcel(locker, away, ready, origins=(point, track)).state
    assert (state.status, state.eta, state.eta_source, state.collect_by) == (
        S.READY_FOR_PICKUP,
        days,
        Source.PARSER,
        date(2026, 11, 9),
    )

    again = _day(3, 10)
    ready = _event(
        S.READY_FOR_PICKUP,
        at(days=1),
        source=Source.SEVENTEENTRACK,
        origin="o2",
        eta=again,
    )
    state = _parcel(locker, away, ready, origins=(point, track)).state
    assert (state.eta, state.eta_source) == (again, Source.SEVENTEENTRACK)

    # Nor when news gave it a date since it left, or after you cleared it.
    ready = _event(
        S.READY_FOR_PICKUP, at(days=1), source=Source.SEVENTEENTRACK, origin="o2"
    )
    dated = _event(
        S.IN_TRANSIT,
        at(hours=2),
        source=Source.SEVENTEENTRACK,
        origin="o2",
        eta=_day(4),
    )
    assert _parcel(locker, dated, ready, origins=(point, track)).state.eta == _day(4)
    edit = _origin("man", source=Source.MANUAL, time=at(days=2))
    cleared = _event(
        None, at(days=2), source=Source.MANUAL, origin="man", clears_eta=True
    )
    state = _parcel(locker, away, ready, cleared, origins=(point, track, edit)).state
    assert (state.collect_by, state.eta) == (date(2026, 11, 9), None)

    # Moved to another point, it isn't expected at the one it left.
    moved = _carrier("o3", time=at(days=1), pickup_point="Locker 30")
    there = _event(S.READY_FOR_PICKUP, at(days=1), origin="o3")
    state = _parcel(locker, away, there, origins=(point, track, moved)).state
    assert (state.pickup_point, state.collect_by, state.eta) == (
        "Locker 30",
        None,
        None,
    )

    # Leaving and coming back again, it's expected there again.
    out_again = _event(
        S.IN_TRANSIT, at(days=2), source=Source.SEVENTEENTRACK, origin="o2"
    )
    back_again = _event(
        S.READY_FOR_PICKUP, at(days=3), source=Source.SEVENTEENTRACK, origin="o2"
    )
    events = (locker, away, ready, out_again, back_again)
    state = _parcel(*events, origins=(point, track)).state
    assert (state.status, state.eta, state.collect_by) == (
        S.READY_FOR_PICKUP,
        days,
        date(2026, 11, 9),
    )
    assert _parcel(*events[:4], origins=(point, track)).state.eta is None


def test_a_new_pickup_point_takes_only_its_own_details() -> None:
    """At a new pickup point, the code comes from the news that names it.

    Neither the last point's code nor a delivery code for the trip home
    reads as the new point's.
    """
    first = _carrier(pickup_point="Locker 21", pickup_code="610003")
    out = _carrier("o2", time=at(hours=2))
    second = _carrier("o3", time=at(days=1), pickup_point="Locker 30")
    parcel = _parcel(
        _event(S.READY_FOR_PICKUP, at(), collect_by=date(2026, 11, 9)),
        _event(S.OUT_FOR_DELIVERY, at(hours=2), origin="o2"),
        _event(
            S.READY_FOR_PICKUP, at(days=1), origin="o3", collect_by=date(2026, 11, 10)
        ),
        origins=(first, out, second),
    )
    state = parcel.state
    assert (state.status, state.pickup_point, state.pickup_code, state.collect_by) == (
        S.READY_FOR_PICKUP,
        "Locker 30",
        None,
        date(2026, 11, 10),
    )

    # A shop after a failed attempt: the attempt names it, and the news that
    # it's there has no code. Neither has the PIN for the trip home.
    shop = "Loja Exemplo, Rua Fictícia 2"
    parcel = _parcel(
        _event(S.READY_FOR_PICKUP, at(), collect_by=date(2026, 11, 9)),
        _event(S.OUT_FOR_DELIVERY, at(hours=2), origin="o2"),
        _event(S.ATTEMPTED, at(hours=4), origin="o3"),
        _event(S.READY_FOR_PICKUP, at(days=1), origin="o4"),
        origins=(
            _carrier(pickup_point="Locker 21", pickup_code="610004"),
            _carrier("o2", time=at(hours=2), pickup_code="4826"),
            _carrier("o3", time=at(hours=4), pickup_point=shop),
            _carrier("o4", time=at(days=1)),
        ),
    )
    state = parcel.state
    assert (state.status, state.pickup_point, state.pickup_code) == (
        S.READY_FOR_PICKUP,
        shop,
        None,
    )

    # The same at the first pickup point it goes to.
    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at()),
        _event(S.ATTEMPTED, at(hours=4), origin="o3"),
        _event(S.READY_FOR_PICKUP, at(days=1), origin="o4"),
        origins=(
            _carrier(pickup_code="4826"),
            _carrier("o3", time=at(hours=4), pickup_point=shop),
            _carrier("o4", time=at(days=1)),
        ),
    )
    state = parcel.state
    assert (state.status, state.pickup_point, state.pickup_code) == (
        S.READY_FOR_PICKUP,
        shop,
        None,
    )


def test_a_rerouted_parcel_takes_only_the_new_points_details() -> None:
    """Moved to another locker without going out, the old one's code stays."""
    track = _origin("o2", source=Source.SEVENTEENTRACK, time=at(hours=2))
    away = _event(S.IN_TRANSIT, at(hours=2), source=Source.SEVENTEENTRACK, origin="o2")
    moved = _carrier("o3", time=at(days=1), pickup_point="Locker 30")
    state = _at_locker(
        away,
        _event(S.READY_FOR_PICKUP, at(days=1), origin="o3"),
        origins=(track, moved),
    ).state
    assert (state.status, state.pickup_point, state.pickup_code, state.collect_by) == (
        S.READY_FOR_PICKUP,
        "Locker 30",
        None,
        None,
    )


def test_the_news_that_a_parcel_is_at_its_point_gives_the_code() -> None:
    """The code comes with the news that the parcel got to its pickup point.

    Also when a later e-mail names the point in other words, or is the first
    to name it, and at a point the parcel was moved to.
    """
    reminder = _carrier("o3", time=at(days=2), pickup_point="Locker 12")
    state = _at_locker(
        _event(S.READY_FOR_PICKUP, at(days=2), origin="o3"), origins=(reminder,)
    ).state
    assert (state.pickup_point, state.pickup_code) == ("Locker 12", "731905")

    parcel = _parcel(
        _event(S.READY_FOR_PICKUP, at()),
        _event(S.READY_FOR_PICKUP, at(days=2), origin="o3"),
        origins=(
            _carrier(pickup_code="731905"),
            _carrier("o3", time=at(days=2), pickup_point=LOCKER),
        ),
    )
    assert (parcel.state.pickup_point, parcel.state.pickup_code) == (
        LOCKER,
        "731905",
    )

    track = _origin("o2", source=Source.SEVENTEENTRACK, time=at(hours=2))
    away = _event(S.IN_TRANSIT, at(hours=2), source=Source.SEVENTEENTRACK, origin="o2")
    state = _at_locker(
        away,
        _event(S.READY_FOR_PICKUP, at(days=1), origin="o3"),
        _event(S.READY_FOR_PICKUP, at(days=2), origin="o4"),
        origins=(
            track,
            _carrier("o3", time=at(days=1), pickup_code="640217"),
            _carrier("o4", time=at(days=2), pickup_point="Locker 30"),
        ),
    ).state
    assert (state.pickup_point, state.pickup_code, state.collect_by) == (
        "Locker 30",
        "640217",
        None,
    )


def test_a_shops_news_it_cant_give_leaves_the_pickup_details() -> None:
    """A shop's late "out for delivery" doesn't give a locker parcel its code.

    The shop's e-mail can't take the parcel from the locker, so its code
    isn't the locker's.
    """
    number = "RR123456785PT"
    parcel = _parcel(
        _event(S.SHIPPED, at(hours=-2)),
        _event(
            S.READY_FOR_PICKUP,
            at(hours=-1),
            origin="o2",
            collect_by=date(2026, 11, 9),
        ),
        _event(S.OUT_FOR_DELIVERY, at(), origin="o3"),
        origins=(
            _origin(
                label="amazon.es",
                time=at(hours=-2),
                carrier="ctt",
                tracking_number=number,
            ),
            _carrier(
                "o2",
                time=at(hours=-1),
                carrier="ctt",
                tracking_number=number,
                pickup_point="Locker 21",
                pickup_code="482913",
            ),
            _origin("o3", label="amazon.es", pickup_code="4821"),
        ),
    )
    state = parcel.state
    assert (state.status, state.pickup_point, state.pickup_code, state.collect_by) == (
        S.READY_FOR_PICKUP,
        "Locker 21",
        "482913",
        date(2026, 11, 9),
    )
    assert state.eta is None


@pytest.mark.parametrize("code", [None, "4821"])
def test_a_shop_is_the_carrier_while_no_carrier_is_known(code: str | None) -> None:
    """With no carrier known, Amazon's own e-mails are its delivery's news.

    Its e-mails in Europe don't name Amazon Logistics. Its newer "out for
    delivery" takes the parcel from its locker, with the code it gives.
    """
    parcel = _parcel(
        _event(S.ORDERED, at(hours=-3)),
        _event(S.SHIPPED, at(hours=-2)),
        _event(
            S.READY_FOR_PICKUP,
            at(hours=-1),
            origin="o2",
            collect_by=date(2026, 11, 9),
        ),
        _event(S.OUT_FOR_DELIVERY, at(), origin="o3"),
        origins=(
            _origin(label="amazon.es", time=at(hours=-3)),
            _origin(
                "o2",
                label="amazon.es",
                time=at(hours=-1),
                pickup_point="Amazon Locker - Exemplo",
                pickup_code="551100",
            ),
            _origin("o3", label="amazon.es", pickup_code=code),
        ),
    )
    state = parcel.state
    assert (state.status, state.pickup_point, state.pickup_code, state.collect_by) == (
        S.OUT_FOR_DELIVERY,
        None,
        code,
        None,
    )


def test_a_shops_delay_notice_leaves_a_locker_parcel_as_it_is() -> None:
    """A shop's delay notice can't take a parcel from its locker, or date it."""
    late = Eta(start=date(2026, 11, 6), end=date(2026, 11, 6))
    parcel = _at_locker(
        _event(S.IN_TRANSIT, at(hours=2), origin="o2", kind=MailKind.DELAYED, eta=late),
        origins=(_origin("o2", label="amazon.es", time=at(hours=2)),),
    )
    state = parcel.state
    assert (state.status, state.eta, state.collect_by, state.pickup_code) == (
        S.READY_FOR_PICKUP,
        None,
        date(2026, 11, 9),
        "731905",
    )


def test_heading_for_a_pickup_point_keeps_its_details() -> None:
    """A parcel on its way to its pickup point hasn't left it."""
    track, out = _tracked(at(hours=2))
    parcel = _parcel(
        _event(S.SHIPPED, at(days=-1)),
        _event(S.IN_TRANSIT, at()),
        out,
        origins=(_carrier(pickup_point=LOCKER), track),
    )
    state = parcel.state
    assert (state.status, state.pickup_point) == (S.OUT_FOR_DELIVERY, LOCKER)


def test_typed_pickup_details_belong_to_their_pickup_point() -> None:
    """A code typed while the parcel is at its pickup point is the point's.

    Once the parcel leaves, it isn't a delivery PIN. One typed after that is
    for the delivery. Each value counts from when it was typed, whatever
    was edited later.
    """
    track, out = _tracked(at(hours=2))

    def code(typed) -> str | None:
        edit = _origin(
            "man:p_test",
            source=Source.MANUAL,
            time=at(hours=3),
            pickup_code="2468",
            typed_at={"pickup_code": typed},
        )
        state = _at_locker(out, origins=(track, edit)).state
        assert state.pickup_point is None
        return state.pickup_code

    assert code(at(hours=1)) is None
    assert code(at(hours=3)) == "2468"


def _typed(attr: str, value: str, when: datetime, shown: ParcelStatus) -> Origin:
    """Return his edit: the value typed then, while Parcels showed ``shown``."""
    return _origin(
        "man:p_test",
        source=Source.MANUAL,
        time=when,
        typed_at={attr: when},
        typed_status={attr: shown},
        **{attr: value},
    )


@pytest.mark.parametrize(
    ("attr", "value"), [("pickup_code", "2468"), ("pickup_point", "Loja Exemplo")]
)
def test_what_he_typed_at_the_point_stays_there(attr: str, value: str) -> None:
    """What he typed while Parcels showed the parcel at its point is the point's.

    Though the news that took it out was sent before he typed it, and read
    after. Typed while the parcel was out for delivery, it's the delivery's.
    """
    track, out = _tracked(at(hours=2))
    typed = _typed(attr, value, at(hours=3), S.READY_FOR_PICKUP)
    state = _at_locker(out, origins=(track, typed)).state
    assert (state.status, state.pickup_point, state.pickup_code) == (
        S.OUT_FOR_DELIVERY,
        None,
        None,
    )
    typed = _typed(attr, value, at(hours=3), S.OUT_FOR_DELIVERY)
    assert getattr(_at_locker(out, origins=(track, typed)).state, attr) == value


def test_his_code_from_the_point_is_back_when_the_parcel_is() -> None:
    """Back at the point it left without going out, his code holds again."""
    parcel = _at_locker(
        _event(S.IN_TRANSIT, at(hours=2), origin="o2"),
        _event(S.READY_FOR_PICKUP, at(hours=3), origin="o3"),
        origins=(
            _carrier("o2", time=at(hours=2)),
            _carrier("o3", time=at(hours=3), pickup_point=LOCKER),
            _typed("pickup_code", "2468", at(hours=1), S.READY_FOR_PICKUP),
        ),
    )
    state = parcel.state
    assert (state.status, state.pickup_point, state.pickup_code) == (
        S.READY_FOR_PICKUP,
        LOCKER,
        "2468",
    )


def test_a_delivery_pin_is_not_the_points_code() -> None:
    """The PIN he typed while the parcel was out isn't its pickup point's code.

    Though the news of the missed delivery was sent before he typed it.
    """
    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at()),
        _event(S.ATTEMPTED, at(hours=1), origin="o2"),
        _event(
            S.READY_FOR_PICKUP,
            at(hours=1.5),
            origin="o2",
            collect_by=date(2026, 11, 9),
        ),
        origins=(
            _carrier(),
            _carrier("o2", time=at(hours=1), pickup_point=LOCKER),
            _typed("pickup_code", "2468", at(hours=2), S.OUT_FOR_DELIVERY),
        ),
    )
    state = parcel.state
    assert (state.status, state.pickup_point, state.pickup_code) == (
        S.READY_FOR_PICKUP,
        LOCKER,
        None,
    )


@pytest.mark.parametrize("theirs", [None, "551100"])
def test_a_code_typed_ahead_waits_for_the_point(theirs: str | None) -> None:
    """A code he typed before the parcel got to its point shows there.

    Unless the point's own news gives one. Typed after that news was sent,
    though read later, his code is the point's.
    """

    def code(typed: datetime) -> str | None:
        parcel = _parcel(
            _event(S.IN_TRANSIT, at()),
            _event(
                S.READY_FOR_PICKUP,
                at(hours=2),
                origin="o2",
                collect_by=date(2026, 11, 9),
            ),
            origins=(
                _carrier(),
                _carrier(
                    "o2", time=at(hours=2), pickup_point=LOCKER, pickup_code=theirs
                ),
                _typed("pickup_code", "2468", typed, S.IN_TRANSIT),
            ),
        )
        assert parcel.state.status is S.READY_FOR_PICKUP
        return parcel.state.pickup_code

    assert code(at(hours=1)) == (theirs or "2468")
    assert code(at(hours=3)) == "2468"


def test_a_code_typed_after_a_missed_delivery_is_for_the_point() -> None:
    """Typed after the missed delivery, a code is for the point it goes to."""
    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at()),
        _event(S.ATTEMPTED, at(hours=1)),
        _event(
            S.READY_FOR_PICKUP,
            at(hours=3),
            origin="o2",
            collect_by=date(2026, 11, 9),
        ),
        origins=(
            _carrier(),
            _carrier("o2", time=at(hours=3), pickup_point=LOCKER),
            _typed("pickup_code", "2468", at(hours=2), S.ATTEMPTED),
        ),
    )
    assert parcel.state.pickup_code == "2468"


def test_a_code_typed_ahead_stays_when_the_shop_names_the_point() -> None:
    """The shop naming the point later, without a code, doesn't drop his."""
    parcel = _parcel(
        _event(S.IN_TRANSIT, at()),
        _event(S.IN_TRANSIT, at(hours=2), origin="o2"),
        origins=(
            _carrier(),
            _origin("o2", time=at(hours=2), pickup_point=LOCKER),
            _typed("pickup_code", "2468", at(hours=1), S.IN_TRANSIT),
        ),
    )
    state = parcel.state
    assert (state.status, state.pickup_point, state.pickup_code) == (
        S.IN_TRANSIT,
        LOCKER,
        "2468",
    )


@pytest.mark.parametrize(
    "current",
    [S.IN_TRANSIT, S.OUT_FOR_DELIVERY, S.ATTEMPTED, S.READY_FOR_PICKUP, S.EXCEPTION],
)
@pytest.mark.parametrize("news", [S.ORDERED, S.SHIPPED])
def test_order_and_shipping_news_never_moves_a_parcel_back(
    current: ParcelStatus, news: ParcelStatus
) -> None:
    """Order and shipping e-mails repeat themselves: they never step back."""
    parcel = _parcel(_event(current, at()), _event(news, at(hours=2)))
    assert parcel.state.status is current
    assert [entry.accepted for entry in parcel.state.timeline] == [True, False]
    shipped = _parcel(_event(S.SHIPPED, at()), _event(S.ORDERED, at(hours=2)))
    assert shipped.state.status is S.SHIPPED


@pytest.mark.parametrize(
    "news",
    [
        S.SHIPPED,
        S.IN_TRANSIT,
        S.OUT_FOR_DELIVERY,
        S.ATTEMPTED,
        S.READY_FOR_PICKUP,
        S.EXCEPTION,
        S.CANCELLED,
    ],
)
def test_only_a_return_follows_a_delivery(news: ParcelStatus) -> None:
    """Newer news about a delivered parcel doesn't undo the delivery."""
    parcel = _parcel(_event(S.DELIVERED, at()), _event(news, at(hours=2)))
    assert parcel.state.status is S.DELIVERED
    returned = _parcel(_event(S.DELIVERED, at()), _event(S.RETURNED, at(hours=2)))
    assert returned.state.status is S.RETURNED


@pytest.mark.parametrize(
    "current", [S.OUT_FOR_DELIVERY, S.ATTEMPTED, S.READY_FOR_PICKUP]
)
def test_cancelling_doesnt_stop_a_parcel_on_its_way(current: ParcelStatus) -> None:
    """An order cancelled after its parcel left can't cancel the parcel."""
    parcel = _parcel(_event(current, at()), _event(S.CANCELLED, at(hours=2)))
    assert parcel.state.status is current
    in_transit = _parcel(_event(S.IN_TRANSIT, at()), _event(S.CANCELLED, at(hours=2)))
    assert in_transit.state.status is S.CANCELLED


def _guessed(news: ParcelStatus, when, by, origin: str = "o2", **kwargs):
    """Return news that gave no time, placed by a guess."""
    return _event(
        news,
        when,
        undated=True,
        by=by,
        origin=origin,
        source=Source.PARCELAPP,
        **kwargs,
    )


@pytest.mark.usefixtures("lisbon")
@pytest.mark.parametrize(("current", "news"), NEWS_AFTER)
def test_a_guessed_time_takes_a_parcel_back_only_on_a_later_day(
    current: ParcelStatus, news: ParcelStatus
) -> None:
    """News without a time steps back only when it's surely newer.

    Its time is a guess: just after what's known to come before it. Another
    source's news of the status's day, or of no known day, may be older.
    """
    origins = (_origin(), _origin("o2", source=Source.PARCELAPP))
    for guessed in (
        # Only the day: the status's own.
        _guessed(news, at(hours=1), at(hours=14), timeless=True),
        # No date, placed between times of the status's day.
        _guessed(news, at(hours=1), at(hours=3)),
        # No date, placed after the status, but seen days later.
        _guessed(news, at(hours=1), at(days=2)),
        # No date, placed on a later day, but seen days after that.
        _guessed(news, at(days=1), at(days=3)),
        # No date, nothing to place it by.
        _guessed(news, at(hours=3), at(hours=3), dayless=True),
        _guessed(news, at(days=1), at(days=1), dayless=True),
    ):
        state = _parcel(_event(current, at()), guessed, origins=origins).state
        assert (state.status, state.status_time) == (current, at())
        assert [entry.accepted for entry in state.timeline] == [True, False]

    # Only the day, a later one.
    later = _guessed(news, at(days=1, hours=-9), at(days=1, hours=14), timeless=True)
    state = _parcel(_event(current, at()), later, origins=origins).state
    assert (state.status, state.status_time) == (news, at(days=1, hours=-9))
    # No date, between times of a later day.
    later = _guessed(news, at(days=1), at(days=1, hours=3))
    assert _parcel(_event(current, at()), later, origins=origins).state.status is news


@pytest.mark.usefixtures("lisbon")
@pytest.mark.parametrize(("current", "news"), NEWS_AFTER)
def test_a_status_of_no_known_time_ends_on_its_last_possible_day(
    current: ParcelStatus, news: ParcelStatus
) -> None:
    """A status that gave no time may have happened as late as it was seen by."""
    origins = (_origin(), _origin("o2", source=Source.PARCELAPP))
    for status in (
        _guessed(current, at(hours=-2), at(days=1, hours=-1), origin="o1"),
        _guessed(
            current, at(hours=-2), at(days=1, hours=-1), origin="o1", dayless=True
        ),
    ):
        same_day = _guessed(
            news, at(days=1, hours=-8), at(days=1, hours=14), timeless=True
        )
        assert _parcel(status, same_day, origins=origins).state.status is current
        next_day = _guessed(
            news, at(days=2, hours=-8), at(days=2, hours=14), timeless=True
        )
        assert _parcel(status, next_day, origins=origins).state.status is news

    # A status with no time, and no time it was seen by: nothing is later.
    unknown = _event(current, at(), undated=True, dayless=True)
    days_later = _guessed(news, at(days=5), at(days=5, hours=2), timeless=True)
    assert _parcel(unknown, days_later, origins=origins).state.status is current


@pytest.mark.usefixtures("lisbon")
@pytest.mark.parametrize(("current", "news"), NEWS_AFTER)
def test_a_sources_own_list_orders_its_news(
    current: ParcelStatus, news: ParcelStatus
) -> None:
    """A source's newer entry follows its older one, though neither has a time.

    Its entry after a dated status counts once it was seen after that time;
    one placed just after it, though seen by it, is the list's older entry.
    """
    origins = (_origin(), _origin("o2", source=Source.PARCELAPP))
    status = _guessed(current, at(hours=1), at(hours=14), timeless=True)
    newer = _guessed(news, at(hours=2), at(hours=14), timeless=True)
    assert _parcel(status, newer, origins=origins).state.status is news
    dated = _event(current, at(), origin="o2", source=Source.PARCELAPP)
    assert (
        _parcel(
            dated, _guessed(news, at(hours=1), at(hours=2)), origins=origins
        ).state.status
        is news
    )
    older = _guessed(news, at() + timedelta(microseconds=5), at())
    assert _parcel(dated, older, origins=origins).state.status is current

    # Another source's news is placed by the guess alone.
    other = _guessed(news, at(hours=2), at(hours=14), timeless=True, origin="o3")
    origins = (*origins, _origin("o3", source=Source.PARCELAPP))
    assert _parcel(status, other, origins=origins).state.status is current


def test_forced_manual_event_wins() -> None:
    """Marking a parcel delivered works from any status."""
    parcel = _parcel(_event(S.ORDERED, at()))
    parcel.events.append(
        _event(S.DELIVERED, at(hours=1), source=Source.MANUAL, origin=None, force=True)
    )
    assert parcel.state.status is S.DELIVERED

    # A returned parcel can't become delivered without force.
    returned = _parcel(_event(S.RETURNED, at()), _event(S.DELIVERED, at(hours=1)))
    assert returned.state.status is S.RETURNED


@pytest.mark.usefixtures("lisbon")
def test_out_for_delivery_without_date_means_today() -> None:
    """The local date of the event is the delivery date."""
    parcel = _parcel(_event(S.OUT_FOR_DELIVERY, at(hours=15)))  # 00:00 in Lisbon
    assert parcel.state.eta == Eta(start=date(2026, 11, 3), end=date(2026, 11, 3))


@pytest.mark.usefixtures("lisbon")
def test_out_for_delivery_of_a_day_not_known_isnt_today() -> None:
    """Undated, "out for delivery" sets the day only when that day is known."""
    seen_that_day = _event(S.OUT_FOR_DELIVERY, at(), undated=True, by=at(hours=5))
    assert _parcel(seen_that_day).state.eta == Eta(
        start=date(2026, 11, 2), end=date(2026, 11, 2)
    )
    for event in (
        _event(S.OUT_FOR_DELIVERY, at(days=-2), undated=True, by=at()),
        _event(S.OUT_FOR_DELIVERY, at(), undated=True, dayless=True, by=at()),
    ):
        assert _parcel(event).state.eta is None


@pytest.mark.usefixtures("lisbon")
def test_a_dated_report_dates_an_undated_status() -> None:
    """A delivery of a day not known takes the time of a report of its day.

    The report must be from no later than the day the delivery was seen by:
    a later one is about the same delivery, but isn't when it happened.
    """
    shipped = _event(S.SHIPPED, at(days=-3))
    undated = _event(S.DELIVERED, at(days=-2), undated=True, by=at(hours=8))
    state = _parcel(shipped, undated).state
    assert (state.status, state.status_time, state.status_undated) == (
        S.DELIVERED,
        at(days=-2),
        True,
    )
    assert (state.delivered_at, state.delivered_undated) == (at(days=-2), True)
    assert [entry.undated for entry in state.timeline] == [False, True]

    state = _parcel(shipped, undated, _event(S.DELIVERED, at(days=1))).state
    assert (state.status_time, state.status_undated) == (at(days=-2), True)
    assert (state.delivered_at, state.delivered_undated) == (at(days=-2), True)

    state = _parcel(shipped, undated, _event(S.DELIVERED, at(hours=-2))).state
    assert (state.status_time, state.status_undated) == (at(hours=-2), False)
    assert (state.delivered_at, state.delivered_undated) == (at(hours=-2), False)


def test_a_status_of_no_known_day_has_no_time() -> None:
    """A delivery that nothing dates is delivered, on no day."""
    state = _parcel(
        _event(S.SHIPPED, at()),
        _event(S.DELIVERED, at(days=1), undated=True, dayless=True, by=at(days=1)),
    ).state
    assert state.status is S.DELIVERED
    assert (state.status_time, state.status_undated) == (None, True)
    assert (state.delivered_at, state.delivered_undated) == (None, True)


def test_what_is_not_known_of_a_date_is_stored() -> None:
    """An event's missing date survives storage."""
    for event in (
        _event(S.IN_TRANSIT, at(), undated=True, by=at(hours=5)),
        _event(S.DELIVERED, at(days=1), undated=True, dayless=True, by=at(days=1)),
    ):
        assert ParcelEvent.from_dict(json.loads(json.dumps(event.as_dict()))) == event


def test_latest_estimate_wins_and_can_be_cleared() -> None:
    """A newer estimate replaces an older one, also when it arrives first."""
    early = Eta(start=date(2026, 11, 5), end=date(2026, 11, 6))
    late = Eta(start=date(2026, 11, 7), end=date(2026, 11, 7), window_start=time(9))
    parcel = _parcel(
        _event(S.IN_TRANSIT, at(days=1), eta=late), _event(None, at(), eta=early)
    )
    assert parcel.state.eta == late

    parcel.events.append(_event(None, at(days=2), clears_eta=True))
    parcel.touch(at(days=2))
    assert parcel.state.eta is None


def test_the_date_keeps_its_source() -> None:
    """The expected date says which source gave it: the newest that may.

    A shop's newer estimate doesn't replace the carrier's.
    """
    early = Eta(start=date(2026, 11, 5), end=date(2026, 11, 5))
    late = Eta(start=date(2026, 11, 6), end=date(2026, 11, 6))
    parcel = _parcel(
        _event(None, at(days=1), eta=late, source=Source.PARCELAPP),
        _event(S.IN_TRANSIT, at(), eta=early),
        origins=(_origin(), _carrier("o3")),
    )
    assert (parcel.state.eta, parcel.state.eta_source) == (late, Source.PARCELAPP)

    parcel.events.append(_event(None, at(days=2), eta=early))
    parcel.touch(at(days=2))
    assert (parcel.state.eta, parcel.state.eta_source) == (late, Source.PARCELAPP)

    parcel.events.append(_event(None, at(days=2, hours=1), eta=early, origin="o3"))
    parcel.touch(at(days=2, hours=1))
    assert (parcel.state.eta, parcel.state.eta_source) == (early, Source.PARSER)

    # News without a date keeps the date and its source.
    parcel.events.append(_event(S.IN_TRANSIT, at(days=3), source=Source.PARCELAPP))
    parcel.touch(at(days=3))
    assert (parcel.state.eta, parcel.state.eta_source) == (early, Source.PARSER)

    # Out for delivery without a date means today, as that source says.
    parcel.events.append(
        _event(S.OUT_FOR_DELIVERY, at(days=4), source=Source.PARCELAPP)
    )
    parcel.touch(at(days=4))
    today = Eta(start=date(2026, 11, 6), end=date(2026, 11, 6))
    assert (parcel.state.eta, parcel.state.eta_source) == (today, Source.PARCELAPP)

    parcel.events.append(_event(None, at(days=5), clears_eta=True))
    parcel.touch(at(days=5))
    assert (parcel.state.eta, parcel.state.eta_source) == (None, None)


def _day(start: int, end: int | None = None) -> Eta:
    """Return an estimate of days in November 2026."""
    return Eta(start=date(2026, 11, start), end=date(2026, 11, end or start))


def _window(day: int, start: int, end: int) -> Eta:
    """Return an estimate of a day in November 2026, between two hours."""
    return Eta(
        start=date(2026, 11, day),
        end=date(2026, 11, day),
        window_start=time(start),
        window_end=time(end),
    )


@pytest.mark.usefixtures("lisbon")
def test_a_shops_news_it_cant_give_doesnt_date_the_parcel() -> None:
    """A shop's late e-mail that can't take a step back doesn't date it either.

    Out for delivery, the carrier's day and window stay. At a locker, the
    parcel isn't expected anywhere.
    """
    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at()),
        _event(S.IN_TRANSIT, at(hours=1), origin="o2", eta=_day(5)),
        origins=(
            _origin(label="ups.com", carrier="ups"),
            _origin("o2", label="shopify.com", time=at(hours=1)),
        ),
    )
    assert (parcel.state.status, parcel.state.eta) == (S.OUT_FOR_DELIVERY, _day(2))

    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at(days=2, hours=-1.5), eta=_window(4, 13, 17)),
        _event(S.IN_TRANSIT, at(days=2, hours=1.5), origin="o2", eta=_day(7)),
        origins=(
            _carrier(time=at(days=2, hours=-1.5)),
            _origin("o2", label="shop.app", time=at(days=2, hours=1.5)),
        ),
    )
    state = parcel.state
    assert (state.status, state.eta, state.eta_source) == (
        S.OUT_FOR_DELIVERY,
        _window(4, 13, 17),
        Source.PARSER,
    )

    parcel = _at_locker(
        _event(S.OUT_FOR_DELIVERY, at(hours=2), origin="o2", eta=_day(4)),
        origins=(_origin("o2", label="shop.app", time=at(hours=2)),),
    )
    assert (parcel.state.status, parcel.state.eta) == (S.READY_FOR_PICKUP, None)


@pytest.mark.usefixtures("lisbon")
def test_a_shops_estimate_doesnt_replace_the_carriers() -> None:
    """Once the carrier has news, a shop's estimate doesn't replace its date.

    A shop's day-only estimate for the carrier's day keeps its window. Nor
    does the carrier's "out for delivery" without a window wipe the shop's
    window for that day. A shop's estimate that came while the parcel was out
    for delivery doesn't count once that day has passed either.
    """
    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at(), eta=_window(2, 10, 12)),
        _event(S.ORDERED, at(hours=1 / 60), origin="o2", eta=_day(2)),
        origins=(
            _origin(label="paack.co", carrier="paack"),
            _origin("o2", label="amazon.es", time=at(hours=1 / 60)),
        ),
    )
    assert parcel.state.eta == _window(2, 10, 12)

    parcel = _parcel(
        _event(S.SHIPPED, at(hours=-3), eta=_window(2, 14, 16)),
        _event(S.OUT_FOR_DELIVERY, at(), origin="o2"),
        _event(S.SHIPPED, at(hours=2), origin="o3", eta=_day(5)),
        origins=(
            _origin(label="lumenhaus.example", time=at(hours=-3)),
            _carrier("o2"),
            _origin("o3", label="lumenhaus.example", time=at(hours=2)),
        ),
    )
    assert parcel.state.eta == _window(2, 14, 16)


@pytest.mark.usefixtures("lisbon")
def test_a_shops_out_for_delivery_falls_within_the_carriers_estimate() -> None:
    """A shop's "out for delivery" picks its day from the carrier's days.

    It keeps the carrier's window for that day. Once the carrier's estimate
    has passed, a shop's newer one replaces it.
    """
    parcel = _parcel(
        _event(S.IN_TRANSIT, at(), eta=_day(4, 6)),
        _event(S.OUT_FOR_DELIVERY, at(days=3), origin="o2"),
        origins=(_carrier(), _origin("o2", label="shop.app", time=at(days=3))),
    )
    assert parcel.state.eta == _day(5)

    parcel = _parcel(
        _event(S.IN_TRANSIT, at(), eta=_window(5, 13, 17)),
        _event(S.OUT_FOR_DELIVERY, at(days=3, hours=-1), origin="o2"),
        origins=(
            _carrier(),
            _origin("o2", label="shop.app", time=at(days=3, hours=-1)),
        ),
    )
    assert parcel.state.eta == _window(5, 13, 17)

    parcel = _parcel(
        _event(S.IN_TRANSIT, at(), eta=_day(3)),
        _event(S.IN_TRANSIT, at(days=3), origin="o2", eta=_day(6)),
        origins=(
            _carrier(),
            _origin("o2", label="lumenhaus.example", time=at(days=3)),
        ),
    )
    assert parcel.state.eta == _day(6)


@pytest.mark.usefixtures("lisbon")
def test_a_shops_later_estimate_counts_once_the_carriers_date_passed(
    freezer: FrozenDateTimeFactory,
) -> None:
    """A shop's estimate the carrier's date held back counts once that passed.

    Judged on the day the parcel is looked at, not when the shop wrote, and
    only while the parcel is on its way. Not an earlier one, nor one the
    carrier's newer date replaced.
    """
    origins = (
        _carrier(),
        _origin("o2", label="lumenhaus.example", time=at(days=1)),
    )
    parcel = _parcel(
        _event(S.IN_TRANSIT, at(), eta=_day(4)),
        _event(S.IN_TRANSIT, at(days=1), origin="o2", eta=_day(7)),
        origins=origins,
    )
    freezer.move_to("2026-11-04 23:30:00+00:00")
    assert parcel.state.eta == _day(4)
    freezer.move_to("2026-11-05 00:30:00+00:00")
    assert parcel.state.eta == _day(7)

    earlier = _parcel(
        _event(S.IN_TRANSIT, at(), eta=_day(4)),
        _event(S.IN_TRANSIT, at(days=1), origin="o2", eta=_day(3)),
        origins=origins,
    )
    assert earlier.state.eta == _day(4)

    replaced = _parcel(
        _event(S.IN_TRANSIT, at(days=1), origin="o2", eta=_day(7)),
        _event(S.IN_TRANSIT, at(days=1, hours=2), eta=_day(4)),
        origins=origins,
    )
    assert replaced.state.eta == _day(4)

    delivered = _parcel(
        _event(S.IN_TRANSIT, at(), eta=_day(4)),
        _event(S.IN_TRANSIT, at(days=1), origin="o2", eta=_day(7)),
        _event(S.DELIVERED, at(days=2)),
        origins=origins,
    )
    assert delivered.state.eta == _day(4)

    # Out for delivery without a date, then a missed delivery and the shop's
    # new date.
    missed = _parcel(
        _event(S.OUT_FOR_DELIVERY, at(days=2)),
        _event(S.EXCEPTION, at(days=2, hours=6), origin="o2", eta=_day(7)),
        origins=origins,
    )
    assert missed.state.eta == _day(7)
    # Not one the shop sent while the parcel was out for delivery.
    stale = _parcel(
        _event(S.OUT_FOR_DELIVERY, at(days=2)),
        _event(S.SHIPPED, at(days=2, hours=2), origin="o2", eta=_day(7)),
        _event(S.EXCEPTION, at(days=2, hours=6)),
        origins=origins,
    )
    assert stale.state.status is S.EXCEPTION
    assert stale.state.eta == _day(4)
    freezer.move_to("2026-11-04 12:00:00+00:00")
    assert missed.state.eta == _day(4)


@pytest.mark.usefixtures("lisbon")
def test_a_shops_newer_out_for_delivery_replaces_its_own_window() -> None:
    """Without the carrier's news, a shop's newer window replaces its older one.

    The carrier's window for the day still stays.
    """
    shop = (
        _origin(label="lumenhaus.example"),
        _origin("o2", label="lumenhaus.example", time=at(hours=1)),
    )
    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at(), eta=_window(2, 13, 14)),
        _event(S.OUT_FOR_DELIVERY, at(hours=1), origin="o2", eta=_window(2, 14, 15)),
        origins=shop,
    )
    assert parcel.state.eta == _window(2, 14, 15)

    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at(), eta=_window(2, 13, 14)),
        _event(S.OUT_FOR_DELIVERY, at(hours=1), origin="o2", eta=_window(2, 14, 15)),
        origins=(_carrier(), shop[1]),
    )
    assert parcel.state.eta == _window(2, 13, 14)


def test_a_delay_notice_moves_the_carriers_date() -> None:
    """A shop's delay notice gives the parcel on its way its new date."""
    parcel = _parcel(
        _event(S.IN_TRANSIT, at(), eta=_day(4)),
        _event(
            S.IN_TRANSIT, at(hours=2), origin="o2", kind=MailKind.DELAYED, eta=_day(6)
        ),
        origins=(
            _carrier(),
            _origin("o2", label="lumenhaus.example", time=at(hours=2)),
        ),
    )
    assert parcel.state.eta == _day(6)


@pytest.mark.parametrize(
    ("source", "label"), [(Source.PARSER, "ctt.pt"), (Source.SEVENTEENTRACK, "")]
)
def test_leaving_the_pickup_point_takes_its_days(source: Source, label: str) -> None:
    """The days to collect a parcel aren't when it's expected once it leaves.

    Unless the news that takes it away gives a date.
    """
    origins = (_carrier(), _origin("o2", source=source, label=label, time=at(hours=2)))
    ready = _event(S.READY_FOR_PICKUP, at(), eta=_day(3, 9))
    away = _event(S.IN_TRANSIT, at(hours=2), source=source, origin="o2")
    assert _parcel(ready, away, origins=origins).state.eta is None

    dated = _event(S.IN_TRANSIT, at(hours=2), source=source, origin="o2", eta=_day(5))
    assert _parcel(ready, dated, origins=origins).state.eta == _day(5)


def test_manual_origin_overrides_and_clears() -> None:
    """The user's edits win; an empty string clears a field."""
    parcel = _parcel(
        _event(S.SHIPPED, at()),
        origins=(
            _origin(
                carrier="dpd",
                tracking_number="05212345678901",
                merchant="Example Shop",
                pickup_point="Locker 1",
            ),
            _origin(
                "man:p_test",
                source=Source.MANUAL,
                time=at(hours=1),
                carrier="gls",
                pickup_point="",
            ),
        ),
    )
    state = parcel.state
    assert state.carrier == "gls"
    assert state.carrier_name == "GLS"
    assert state.tracking_number == "05212345678901"
    assert state.merchant == "Example Shop"
    assert state.pickup_point is None
    assert state.source is Source.MANUAL
    assert state.tracking_url
    assert state.tracking_url.startswith("https://")


def test_best_source_supplies_the_number() -> None:
    """A parser number beats the AI's; the latest parser number wins."""
    parcel = _parcel(
        origins=(
            _origin("a", source=Source.AI, tracking_number="AI000000001"),
            _origin("b", tracking_number="OLD00000001", carrier="ctt"),
            _origin(
                "c", tracking_number="NEW00000001", carrier="ctt", time=at(hours=1)
            ),
        )
    )
    assert parcel.state.tracking_number == "NEW00000001"
    assert parcel.state.source is Source.PARSER


def test_ai_flag_until_confirmed() -> None:
    """Parcels found only by the AI are marked until the user confirms them."""
    origin = _origin(source=Source.AI, tracking_number="AI000000001")
    parcel = _parcel(_event(S.SHIPPED, at(), source=Source.AI), origins=(origin,))
    assert parcel.state.ai
    assert not parcel.state.ai_filled
    origin.confirmed = True
    parcel.touch(at())
    assert not parcel.state.ai


def test_ai_filled_until_confirmed() -> None:
    """What the AI filled in for a parser's parcel is marked until confirmed."""
    fill = _origin("msg:a#ai", source=Source.AI, items=("Lamp",))
    parcel = _parcel(
        _event(S.SHIPPED, at(), origin="msg:a#0"),
        origins=(_origin("msg:a#0", tracking_number="05212345678901"), fill),
    )
    assert not parcel.state.ai
    assert parcel.state.ai_filled
    assert parcel.state.items == ("Lamp",)
    # A parser's items replace the AI's.
    parcel.origins["b"] = _origin("b", time=at(hours=1), items=("Desk lamp",))
    parcel.touch(at())
    assert parcel.state.items == ("Desk lamp",)
    fill.confirmed = True
    parcel.touch(at())
    assert not parcel.state.ai_filled


def test_provisional_until_tracked() -> None:
    """An order without a tracking number is provisional."""
    parcel = _parcel(
        _event(S.ORDERED, at()), origins=(_origin(order_numbers=("#1001",)),)
    )
    assert parcel.state.provisional
    parcel.origins["o1"].tracking_number = "05212345678901"
    parcel.touch(at())
    assert not parcel.state.provisional


def _details(state: ParcelState) -> tuple[date | None, date | None, LeftAt | None]:
    return state.collect_by, state.next_attempt, state.left_at


def test_a_collect_by_date_holds_while_the_carrier_keeps_the_parcel() -> None:
    """A missed attempt's date carries to the pickup notice, a later one wins.

    It goes once the parcel is delivered, which has its own place.
    """
    first, later = date(2026, 11, 9), date(2026, 11, 10)
    transit = _event(S.IN_TRANSIT, at(days=-1))
    missed = _event(S.ATTEMPTED, at(hours=2), collect_by=first)
    notice = _event(S.READY_FOR_PICKUP, at(hours=5))
    reminder = _event(S.READY_FOR_PICKUP, at(days=1), collect_by=later)
    delivered = _event(S.DELIVERED, at(days=2), left_at=LeftAt.LOCKER)

    assert _details(_parcel(transit, missed).state) == (first, None, None)
    state = _parcel(transit, missed, notice).state
    assert (state.status, state.collect_by) == (S.READY_FOR_PICKUP, first)
    assert _parcel(transit, missed, notice, reminder).state.collect_by == later
    # Event times decide, not the order the e-mails came in.
    assert _parcel(reminder, notice, missed, transit).state.collect_by == later
    state = _parcel(transit, missed, notice, reminder, delivered).state
    assert _details(state) == (None, None, LeftAt.LOCKER)


def test_a_new_status_starts_afresh() -> None:
    """Details belong to their status: a new attempt has none of the last's."""
    missed = _event(
        S.ATTEMPTED,
        at(),
        collect_by=date(2026, 11, 9),
        next_attempt=date(2026, 11, 3),
    )
    again = _event(S.OUT_FOR_DELIVERY, at(days=1))
    missed_again = _event(S.ATTEMPTED, at(days=1, hours=3))
    assert _details(_parcel(missed, again).state) == (None, None, None)
    assert _details(_parcel(missed, again, missed_again).state) == (None, None, None)
    # Details sent with another status count for nothing.
    stray = _event(
        S.IN_TRANSIT,
        at(),
        collect_by=date(2026, 11, 9),
        next_attempt=date(2026, 11, 3),
        left_at=LeftAt.DOOR,
    )
    assert _details(_parcel(stray).state) == (None, None, None)


def test_a_next_attempt_lasts_until_news_from_its_day() -> None:
    """A report from the day of the next attempt or later ends it."""
    tuesday, thursday = date(2026, 11, 3), date(2026, 11, 5)
    missed = _event(S.ATTEMPTED, at(hours=2), next_attempt=tuesday)
    same_day = _event(S.ATTEMPTED, at(hours=6))
    next_day = _event(S.ATTEMPTED, at(days=1, hours=3))
    moved = _event(S.ATTEMPTED, at(days=1, hours=4), next_attempt=thursday)
    # Placed on Tuesday, but seen by Wednesday: its day isn't known.
    undated = _event(S.ATTEMPTED, at(days=1), undated=True, by=at(days=2))

    assert _parcel(missed).state.next_attempt == tuesday
    assert _parcel(missed, same_day).state.next_attempt == tuesday
    assert _parcel(missed, next_day).state.next_attempt is None
    assert _parcel(missed, next_day, moved).state.next_attempt == thursday
    assert _parcel(missed, undated).state.next_attempt == tuesday


def test_where_a_delivered_parcel_was_left() -> None:
    """A later report adds or corrects the place; one without keeps it."""
    delivered = _event(S.DELIVERED, at(), left_at=LeftAt.NEIGHBOUR)
    confirmed = _event(S.DELIVERED, at(hours=1))
    corrected = _event(S.DELIVERED, at(hours=2), left_at=LeftAt.MAILBOX)
    returned = _event(S.RETURNED, at(days=3))

    assert _parcel(delivered).state.left_at is LeftAt.NEIGHBOUR
    assert _parcel(delivered, confirmed).state.left_at is LeftAt.NEIGHBOUR
    assert _parcel(delivered, confirmed, corrected).state.left_at is LeftAt.MAILBOX
    assert _parcel(confirmed, corrected).state.left_at is LeftAt.MAILBOX
    assert _parcel(delivered, returned).state.left_at is None


def test_a_status_reported_without_its_time() -> None:
    """The status's time is only the e-mail's when the e-mail gave none."""
    # The e-mail's own time: it didn't say when it happened.
    assert _parcel(_event(S.ATTEMPTED, T0)).state.status_reported
    ai = _origin(source=Source.AI)
    assert _parcel(
        _event(S.ATTEMPTED, T0, source=Source.AI), origins=(ai,)
    ).state.status_reported
    # A time the e-mail gave.
    assert not _parcel(_event(S.ATTEMPTED, at(hours=-2))).state.status_reported
    # Trackers give the time it happened, and inferred deliveries aren't news.
    tracker = _origin("o2", source=Source.SEVENTEENTRACK)
    tracked = _event(S.ATTEMPTED, T0, source=Source.SEVENTEENTRACK, origin="o2")
    assert not _parcel(tracked, origins=(tracker,)).state.status_reported
    inferred = _event(S.DELIVERED, T0, origin=None, inferred=True)
    assert not _parcel(inferred).state.status_reported
    # The first report gives the status its time; a later one changes nothing.
    first = _event(S.ATTEMPTED, at(hours=-2))
    assert not _parcel(first, _event(S.ATTEMPTED, T0)).state.status_reported

    # A report that dates an undated status gives it its time, as reported.
    app = _origin("pa", source=Source.PARCELAPP, time=at(days=-1))
    undated = _event(
        S.DELIVERED,
        at(days=-1),
        source=Source.PARCELAPP,
        origin="pa",
        undated=True,
        by=at(hours=8),
    )
    state = _parcel(undated, _event(S.DELIVERED, T0), origins=(app, _origin())).state
    assert (state.status_time, state.status_reported) == (T0, True)
    state = _parcel(
        undated, _event(S.DELIVERED, at(hours=-1)), origins=(app, _origin())
    ).state
    assert (state.status_time, state.status_reported) == (at(hours=-1), False)


def test_details_are_stored() -> None:
    """Details survive the store; events without them add no keys."""
    missed = _event(
        S.ATTEMPTED,
        at(),
        collect_by=date(2026, 11, 9),
        next_attempt=date(2026, 11, 3),
    )
    delivered = _event(S.DELIVERED, at(days=1), left_at=LeftAt.GARAGE)
    for event in (missed, delivered):
        stored = json.loads(json.dumps(event.as_dict()))
        assert ParcelEvent.from_dict(stored) == event
    assert missed.as_dict()["collect_by"] == "2026-11-09"
    assert missed.as_dict()["next_attempt"] == "2026-11-03"
    assert delivered.as_dict()["left_at"] == "garage"
    assert not {"collect_by", "next_attempt", "left_at"} & set(
        _event(S.SHIPPED, at()).as_dict()
    )
    # A place this release doesn't know is dropped, not guessed.
    assert (
        ParcelEvent.from_dict({**delivered.as_dict(), "left_at": "roof"}).left_at
        is None
    )

    suggestion = Suggestion(
        kind=MailKind.ATTEMPTED,
        tracking_numbers=("RR123456785PT",),
        collect_by=date(2026, 11, 9),
        next_attempt=date(2026, 11, 3),
    )
    stored = json.loads(json.dumps(suggestion.as_dict()))
    assert Suggestion.from_dict(stored) == suggestion
    place = Suggestion(kind=MailKind.DELIVERED, left_at=LeftAt.RECEPTION)
    assert Suggestion.from_dict(place.as_dict()) == place
    assert (
        Suggestion.from_dict({"kind": "delivered", "left_at": "roof"}).left_at is None
    )


def test_items_are_unique_and_capped() -> None:
    """Items are merged from all origins without duplicates."""
    parcel = _parcel(
        origins=(
            _origin("a", items=("Lamp", "Cable")),
            _origin("b", items=("lamp", *(f"Item {n}" for n in range(30)))),
        )
    )
    assert parcel.state.items[:3] == ("Lamp", "Cable", "Item 0")
    assert len(parcel.state.items) == 20


def test_carrier_mail_names_the_carrier() -> None:
    """The carrier's own e-mail names the carrier; the shop's names the shop."""
    number = "61234567890123"
    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at()),
        origins=(
            _origin(
                "carrier",
                label="cttexpresso.pt",
                carrier="ctt_expresso",
                tracking_number=number,
                merchant="Example Seller SL",
            ),
            _origin(
                "shop",
                label="shop.example",
                time=at(hours=1),
                carrier="dhl",
                tracking_number=number,
                merchant="Example Shop",
            ),
        ),
    )
    assert parcel.state.carrier == "ctt_expresso"
    assert parcel.state.merchant == "Example Shop"


def test_seller_is_the_shop_not_a_domain_or_carrier() -> None:
    """The shop's own e-mails name the seller, even when they come later.

    A status service wrote first and only gave its domain; the carrier's
    e-mail named itself. Better evidence re-decides the seller.
    """
    number = "61234567890123"
    service = _origin(
        "service", label="statusmail.example", merchant="statusmail.example"
    )
    carrier = _origin(
        "carrier",
        label="cttexpresso.pt",
        time=at(hours=1),
        carrier="ctt_expresso",
        tracking_number=number,
        merchant="CTT Expresso",
    )
    parcel = _parcel(_event(S.SHIPPED, at()), origins=(service, carrier))
    assert parcel.state.merchant == "statusmail.example"

    parcel.origins["shop"] = _origin(
        "shop", label="lumenhaus.example", time=at(hours=2), merchant="Lumenhaus"
    )
    parcel.touch(at(hours=2))
    assert parcel.state.merchant == "Lumenhaus"

    # Another shop's name from a sender of its own beats a name from elsewhere.
    parcel.origins["relay"] = _origin(
        "relay", label="notify.example", time=at(hours=-1), merchant="Lumenhaus Store"
    )
    parcel.touch(at(hours=2))
    assert parcel.state.merchant == "Lumenhaus"

    # A carrier's name is never the seller.
    only_carrier = _parcel(_event(S.SHIPPED, at()), origins=(carrier,))
    assert only_carrier.state.merchant is None


def test_shop_mail_carrier_only_without_others() -> None:
    """Without a carrier's e-mail or a number, a shop's e-mail names it."""
    shop = _origin(
        "shop", label="shop.example", time=at(hours=1), carrier="gls", merchant="Shop"
    )
    parcel = _parcel(_event(S.SHIPPED, at()), origins=(shop,))
    assert parcel.state.carrier == "gls"

    # Even when the shop's e-mail is newer.
    parcel.origins["carrier"] = _origin(
        "carrier", label="cttexpresso.pt", carrier="ctt_expresso"
    )
    parcel.touch(at(hours=1))
    assert parcel.state.carrier == "ctt_expresso"


def test_shipment_items_win_over_the_order() -> None:
    """A package holds what its shipping e-mail lists, not the whole order."""
    order = _origin(
        "order",
        order_numbers=("1001",),
        items=("Lamp", "Cable", "Chávena de café EX200 para..."),
    )
    shipped = _origin(
        "shipped",
        time=at(hours=1),
        tracking_number="05212345678901",
        order_numbers=("1001",),
        items=("lamp",),
    )
    assert _parcel(origins=(order, shipped)).state.items == ("lamp",)

    # Without a shipment's list, the order's items show, each once.
    again = _origin(
        "again",
        time=at(hours=2),
        order_numbers=("1001",),
        items=("Chávena de café EX200 para expresso", "LAMP"),
    )
    assert _parcel(origins=(order, again)).state.items == (
        "Lamp",
        "Cable",
        "Chávena de café EX200 para expresso",
    )


def test_delivery_code_until_the_parcel_arrives() -> None:
    """A delivery code shows until the parcel is delivered, unless inferred."""
    coded = _origin(tracking_number="05212345678901", pickup_code="4821")
    parcel = _parcel(_event(S.OUT_FOR_DELIVERY, at()), origins=(coded,))
    assert parcel.state.pickup_code == "4821"

    parcel.events.append(_event(S.DELIVERED, at(hours=2), inferred=True))
    parcel.touch(at(hours=2))
    assert parcel.state.inferred
    assert parcel.state.pickup_code == "4821"

    parcel.events.append(_event(S.DELIVERED, at(hours=3)))
    parcel.touch(at(hours=3))
    assert parcel.state.pickup_code is None


def test_an_inferred_delivery_is_not_news() -> None:
    """The news gave the status before an inferred delivery.

    A delivery reported after it takes its own time: the inferred one was
    only a guess.
    """
    guessed = _event(S.DELIVERED, at(hours=2), origin=None, inferred=True)
    assert _parcel(guessed).state.inferred_over is S.ORDERED
    parcel = _parcel(_event(S.SHIPPED, at()), guessed)
    state = parcel.state
    assert (state.status, state.inferred_over, state.news_status) == (
        S.DELIVERED,
        S.SHIPPED,
        S.SHIPPED,
    )

    parcel.origins["man"] = _origin("man", source=Source.MANUAL, time=at(hours=3))
    parcel.events.append(
        _event(S.DELIVERED, at(hours=3), source=Source.MANUAL, origin="man", force=True)
    )
    parcel.touch(at(hours=3))
    state = parcel.state
    assert (state.status, state.inferred, state.inferred_over, state.news_status) == (
        S.DELIVERED,
        False,
        None,
        S.DELIVERED,
    )
    assert (state.status_time, state.delivered_at) == (at(hours=3), at(hours=3))


def test_keys() -> None:
    """Merchant and order keys ignore case, accents and marketplaces."""
    assert merchant_key("Amazon.es") == merchant_key("amazon.co.uk") == "amazon"
    assert merchant_key("AMAZON EU SARL SUCURSAL EN") == "amazon"
    assert merchant_key("Amazon EU S.à r.l.") == "amazon"
    assert merchant_key("Amazonia Store") == "amazoniastore"
    assert merchant_key("Loja Ação") == "lojaacao"
    assert merchant_key(None) == ""
    assert order_key("Amazon.es", "405-1234567-1234567") == "ord:40512345671234567"
    assert order_key(None, "405-1234567-1234567") == "ord:40512345671234567"
    assert order_key("Example Shop", "#1001") == "ord:exampleshop:1001"
    assert order_key(None, "#1001") is None
    assert order_key("Example Shop", "#") is None


def test_merchant_display() -> None:
    """Marketplaces and legal names of a known merchant show as its name."""
    for name in ("Amazon.es", "amazon.co.uk", "AMAZON EU SARL SUCURSAL EN"):
        assert merchant_display(name) == "Amazon"
    assert merchant_display("Loja Ação") == "Loja Ação"
    assert merchant_display(None) is None


def test_known_merchant_name() -> None:
    """Free text names a merchant only when it starts with a known one."""
    assert known_merchant_name("Amazon.es order") == "Amazon"
    assert known_merchant_name("AMAZON EU SARL") == "Amazon"
    assert known_merchant_name("Headphones from Amazon") is None
    assert known_merchant_name("Example Shop") is None
    assert known_merchant_name("") is None
    assert known_merchant_name(None) is None


def _full_data() -> ParcelsData:
    parcel = _parcel(
        _event(S.SHIPPED, at(), kind=MailKind.SHIPPED),
        _event(
            None,
            at(hours=1),
            eta=Eta(date(2026, 11, 4), date(2026, 11, 5), time(9), time(13)),
        ),
        origins=(
            _origin(
                tracking_number="05212345678901",
                carrier="dpd",
                order_numbers=("#1001",),
                items=("Lamp",),
                owners=("person.one",),
                message="abc",
            ),
            _origin(
                "man:p_test",
                source=Source.MANUAL,
                time=at(),
                merchant="",
                pickup_code="2468",
                typed_at={"pickup_code": at(hours=1)},
                typed_status={"pickup_code": S.READY_FOR_PICKUP},
            ),
        ),
    )
    parcel.private = True
    parcel.auto_merged = AutoMerge(origin="o1", at=at(), reason="same_merchant_eta")
    suggestion = Suggestion(
        kind=MailKind.SHIPPED,
        carrier="ctt",
        tracking_numbers=("RR123456785PT",),
        eta_start=date(2026, 11, 4),
        window_start=time(9),
        reference="Wx4Hn8Tz3",
    )
    return ParcelsData(
        parcels={parcel.id: parcel},
        orders={
            "ord:exampleshop:1001": Order(
                "ord:exampleshop:1001", "#1001", "Example Shop", at(), at()
            )
        },
        messages={
            "abc": MessageRecord(
                "abc", at(), MessageState.APPLIED, {"entry": "id1"}, at(), "example.com"
            )
        },
        review={
            "r1": ReviewItem(
                "r1",
                at(),
                "def",
                at(),
                "Shop <shop@example.com>",
                "example.com",
                "Your order",
                "entry",
                "person.one",
                "low_confidence",
                True,
                Source.AI,
                suggestion,
                fill=True,
                errors=("tracking_invalid", "eta_not_in_text"),
                notes=("carrier_unproven", "eta_from_text"),
            )
        },
        filtered={
            "f1": FilteredItem(
                "f1", at(), "ghi", at(), "news@example.com", "example.com", "Hi", None
            )
        },
        senders={"example.com": SenderPrefs("example.com", trusted=True)},
        engine={"notifier": {"x": 1}},
        parcelapp={"poll": {"last": "2026-11-02T09:00:00+00:00"}},
        cursors={"entry": {"delta": "token"}},
    )


def test_round_trip() -> None:
    """Everything survives serialisation, as JSON."""
    data = _full_data()
    stored = json.loads(json.dumps(data.as_dict()))
    loaded = ParcelsData.from_dict(stored)
    assert loaded.as_dict() == data.as_dict()
    parcel = loaded.parcels["p_test"]
    assert parcel.state == data.parcels["p_test"].state
    assert parcel.origins["man:p_test"].merchant == ""
    assert parcel.origins["man:p_test"].typed_at == {"pickup_code": at(hours=1)}
    assert parcel.origins["man:p_test"].typed_status == {
        "pickup_code": S.READY_FOR_PICKUP
    }
    assert loaded.review["r1"].suggestion == data.review["r1"].suggestion
    assert loaded.review["r1"].fill
    assert loaded.review["r1"].errors == ("tracking_invalid", "eta_not_in_text")
    assert loaded.review["r1"].notes == ("carrier_unproven", "eta_from_text")
    assert loaded.trusted_domains() == ("example.com",)


def test_typed_times_that_cant_be_read_are_left_out() -> None:
    """A stored time of an edit that can't be read is as if not known."""
    stored = _origin("man:p_test", source=Source.MANUAL, pickup_code="2468").as_dict()
    stored["typed_at"] = {
        "pickup_code": "2026-13-45T00:00:00",
        "pickup_point": None,
        "merchant": "2026-11-02T10:00:00+00:00",
    }
    assert Origin.from_dict(stored).typed_at == {"merchant": at(hours=1)}
    stored["typed_at"] = ["pickup_code"]
    assert Origin.from_dict(stored).typed_at == {}
    stored["typed_status"] = {
        "pickup_code": "teleported",
        "pickup_point": None,
        "merchant": "in_transit",
    }
    assert Origin.from_dict(stored).typed_status == {"merchant": S.IN_TRANSIT}
    stored["typed_status"] = ["pickup_code"]
    assert Origin.from_dict(stored).typed_status == {}


def test_failed_emails_keep_their_tries() -> None:
    """An e-mail that failed keeps its count of tries and its next try."""
    record = MessageRecord(
        "failing",
        at(),
        MessageState.FAILED,
        {"entry": "id2"},
        at(),
        "example.com",
        attempts=3,
        retry_at=at(hours=1),
    )

    loaded = MessageRecord.from_dict(json.loads(json.dumps(record.as_dict())))

    assert loaded == record
    assert "attempts" not in MessageRecord("abc", at(), MessageState.APPLIED).as_dict()


def test_failed_emails_of_an_earlier_release_are_tried_again() -> None:
    """An e-mail an earlier release gave up on is due for another try.

    One this release gave up on, after all its tries, stays given up.
    """
    stored = json.loads(json.dumps(_full_data().as_dict()))
    stored["messages"] += [
        {
            "hash": "earlier",
            "seen": "2026-11-02T10:00:00+00:00",
            "state": "failed",
            "refs": {"entry": "id3"},
        },
        {
            "hash": "given_up",
            "seen": "2026-11-02T10:00:00+00:00",
            "state": "failed",
            "refs": {"entry": "id4"},
            "attempts": 8,
        },
    ]

    loaded = ParcelsData.from_dict(stored)

    earlier = loaded.messages["earlier"]
    assert (earlier.attempts, earlier.retry_at) == (0, at(hours=1))
    given_up = loaded.messages["given_up"]
    assert (given_up.attempts, given_up.retry_at) == (8, None)
    assert loaded.messages["abc"].retry_at is None


def _shells() -> tuple[ParcelShell, ...]:
    """Return what an e-mail's two parcels were while it's read again."""
    lost = ParcelShell(
        id="p_lost",
        created=at(),
        origins=("msg:abc#0",),
        status=S.DELIVERED,
        private=True,
        archived=at(days=1),
        delivery_rejected=True,
        auto_merged=AutoMerge(origin="msg:abc#0", at=at(), reason="same_merchant_eta"),
        lost=True,
        kept_origins=(
            _origin(
                "man:p_lost", source=Source.MANUAL, time=at(), pickup_point="Locker 12"
            ),
        ),
        kept_events=(
            _event(S.DELIVERED, at(hours=2), origin=None, inferred=True, id="e_1"),
        ),
    )
    kept = ParcelShell(
        id="p_kept", created=at(), origins=("msg:abc#1",), status=S.SHIPPED
    )
    return lost, kept


def test_message_shells_round_trip() -> None:
    """What an e-mail's parcels were, while it's read again, survives a restart."""
    data = _full_data()
    data.messages["abc"].shells = _shells()

    loaded = ParcelsData.from_dict(json.loads(json.dumps(data.as_dict())))

    assert loaded.messages["abc"].shells == _shells()
    assert loaded.as_dict() == data.as_dict()
    assert loaded.damaged == {}
    assert "shells" not in _full_data().messages["abc"].as_dict()
    assert ParcelsData.from_dict(_full_data().as_dict()).messages["abc"].shells == ()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("id", None),
        ("id", ""),
        ("created", None),
        ("created", "2026-13-02T08:00:00+00:00"),
        ("status", "lost_in_space"),
        ("kept_origins", [{"source": "manual"}]),
        (None, "garbage"),
    ],
)
def test_a_damaged_shell_is_skipped(key: str | None, value: object) -> None:
    """A damaged shell is skipped alone: the e-mail and its other shells stay."""
    data = _full_data()
    data.messages["abc"].shells = _shells()
    stored = json.loads(json.dumps(data.as_dict()))
    shells = stored["messages"][0]["shells"]
    if key is None:
        shells[0] = value
    elif value is None:
        del shells[0][key]
    else:
        shells[0][key] = value

    loaded = ParcelsData.from_dict(stored)

    assert loaded.messages["abc"].shells == _shells()[1:]
    assert loaded.damaged == {}


def test_auto_merge_groups() -> None:
    """A merge of several shipments keeps each one's origins, to undo apart."""
    flag = AutoMerge(
        origin="o1",
        at=at(),
        reason="amazon_tracking",
        origins=("o2", "o3"),
        groups=(("o1", "o2"), ("o3",)),
    )
    stored = json.loads(json.dumps(flag.as_dict()))
    assert AutoMerge.from_dict(stored) == flag
    assert flag.all_origins == {"o1", "o2", "o3"}
    stored["groups"] = [["o1", "o2"], [], "o3", 7, ["o3"]]
    assert AutoMerge.from_dict(stored).groups == (("o1", "o2"), ("o3",))
    single = AutoMerge(origin="o1", at=at(), reason="amazon_tracking")
    assert "groups" not in single.as_dict()
    assert AutoMerge.from_dict(single.as_dict()).groups == ()


def test_references() -> None:
    """A parcel lists its shipment references, with the stem of Paack's ID."""
    parcel = _parcel(
        _event(S.SHIPPED, at()),
        origins=(
            _origin(carrier="paack", tracking_number="Wx4Hn8Tz3_1"),
            _origin("o2", carrier="paack", reference="Wx4Hn8Tz3"),
            _origin(
                "o3", time=at(hours=1), merchant="Casa Exemplo", reference="1234567890"
            ),
            _origin("o4", time=at(hours=2), carrier="gls", tracking_number="AB12_3"),
        ),
    )
    assert parcel.state.references == ("Wx4Hn8Tz3", "1234567890")
    for origin in parcel.origins.values():
        assert Origin.from_dict(json.loads(json.dumps(origin.as_dict()))) == origin


def test_seller() -> None:
    """A parcel shows the marketplace seller its newest e-mail names."""
    parcel = _parcel(
        _event(S.SHIPPED, at()),
        origins=(
            _origin(merchant="Leroy Merlin", order_numbers=("51800012",)),
            _origin("o2", time=at(hours=1), merchant="Leroy Merlin", seller="Loja A"),
            _origin("o3", time=at(hours=2), merchant="Leroy Merlin", seller="Loja B"),
            _origin("o4", time=at(hours=3), carrier="gls", tracking_number="AB12CD34"),
        ),
    )
    assert parcel.state.seller == "Loja B"
    assert parcel.state.merchant == "Leroy Merlin"
    for origin in parcel.origins.values():
        assert Origin.from_dict(json.loads(json.dumps(origin.as_dict()))) == origin
    assert _parcel(_event(S.SHIPPED, at())).state.seller is None


def test_review_item_keeps_only_check_codes() -> None:
    """A stored item's failed checks and notes are codes: anything else is dropped."""
    stored = _full_data().review["r1"].as_dict()
    stored["errors"] = ["order_is_part", "RR123456785PT", 7, "x" * 41, "order_is_part"]
    stored["notes"] = ["eta_from_text", "Amazon", None, "eta_from_text"]
    item = ReviewItem.from_dict(stored)
    assert (item.errors, item.notes) == (("order_is_part",), ("eta_from_text",))
    del stored["errors"], stored["notes"]
    item = ReviewItem.from_dict(stored)
    assert (item.errors, item.notes) == ((), ())
    assert "notes" not in item.as_dict()


def test_unreadable_entries_are_skipped(caplog: pytest.LogCaptureFixture) -> None:
    """One damaged record doesn't lose the others."""
    stored = _full_data().as_dict()
    stored["parcels"].append({"origins": []})
    stored["orders"] = "garbage"
    with caplog.at_level(logging.WARNING):
        loaded = ParcelsData.from_dict(stored)
    assert list(loaded.parcels) == ["p_test"]
    assert loaded.orders == {}
    assert "unreadable stored parcel" in caplog.text
    assert ParcelsData.from_dict(None) == ParcelsData()


@pytest.mark.parametrize("damaged", [None, "garbage", ["a", "list"], 42])
def test_an_entry_that_is_not_an_object_is_skipped(damaged: object) -> None:
    """Any damaged entry is skipped, and counted for diagnostics."""
    stored = _full_data().as_dict()
    stored["parcels"].append(damaged)
    stored["orders"] = "garbage"

    loaded = ParcelsData.from_dict(stored)

    assert list(loaded.parcels) == ["p_test"]
    assert loaded.damaged == {"orders": 1, "parcels": 1}
    assert ParcelsData.from_dict(_full_data().as_dict()).damaged == {}


def test_an_impossible_time_skips_only_its_entry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A well-formed but impossible stored time ("month 13") skips its entry.

    The log says what kind of entry, never the stored value.
    """
    stored = _full_data().as_dict()
    broken = json.loads(json.dumps(stored["parcels"][0]))
    broken["id"] = "p_broken"
    broken["created"] = "2026-13-02T08:00:00+00:00"
    stored["parcels"].append(broken)
    stored["messages"][0]["received"] = "2026-11-02T25:00:00+00:00"

    with caplog.at_level(logging.WARNING):
        loaded = ParcelsData.from_dict(stored)

    assert list(loaded.parcels) == ["p_test"]
    assert loaded.messages == {}
    assert loaded.damaged == {"messages": 1, "parcels": 1}
    assert "unreadable stored parcel" in caplog.text
    assert "2026-13-02" not in caplog.text
    assert "05212345678901" not in caplog.text


def test_impossible_times_in_free_form_sections_are_counted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Other modules' sections keep their data; their unreadable times count.

    Their readers take such a time as missing.
    """
    stored = _full_data().as_dict()
    stored["engine"] = {
        "notifier": {"days": {"2026-11-02": {"started": "2026-13-02T08:00:00"}}},
        "checks": [{"before": "2026-11-02T09:00:00+00:00"}, "2026-11-31 10:00"],
    }
    stored["seventeentrack"] = {"packages": {"RR123456785PT": {"added": "never"}}}

    with caplog.at_level(logging.WARNING):
        loaded = ParcelsData.from_dict(stored)

    assert loaded.engine == stored["engine"]
    assert loaded.damaged == {"engine": 2}
    assert dt_from_str("2026-13-02T08:00:00") is None
    assert dt_from_str("2026-11-02T09:00:00+00:00") == T0
    assert "2026-13-02" not in caplog.text
    assert "Ignoring 2 unreadable stored times in engine" in caplog.text
    assert loaded.as_dict() == ParcelsData.from_dict(loaded.as_dict()).as_dict()
    assert "damaged" not in loaded.as_dict()


# The sources 0.1.5 can read: it skips a whole parcel with any other.
SOURCES_0_1_5 = {"parser", "ai", "manual", "seventeentrack"}


def test_parcel_app_news_is_stored_so_older_releases_read_it() -> None:
    """The Parcel app's records are stored as 17TRACK's and read back as its own.

    A parcel with the Parcel app's news must survive going back to 0.1.5.
    """
    parcel = _parcel(
        _event(S.SHIPPED, at()),
        _event(S.IN_TRANSIT, at(hours=2), source=Source.PARCELAPP, origin="pa:1"),
        _event(S.IN_TRANSIT, at(hours=3), source=Source.SEVENTEENTRACK, origin="17t:2"),
        origins=(
            _origin(),
            _origin("pa:1", source=Source.PARCELAPP, time=at(hours=2), name="Lamp"),
            _origin("17t:2", source=Source.SEVENTEENTRACK, time=at(hours=3)),
        ),
    )
    stored = json.loads(json.dumps(parcel.as_dict()))
    assert {origin["source"] for origin in stored["origins"]} <= SOURCES_0_1_5
    assert {event["source"] for event in stored["events"]} <= SOURCES_0_1_5
    loaded = Parcel.from_dict(stored)
    assert loaded.origins["pa:1"].source is Source.PARCELAPP
    assert loaded.origins["17t:2"].source is Source.SEVENTEENTRACK
    assert [event.source for event in loaded.events] == [
        Source.PARSER,
        Source.PARCELAPP,
        Source.SEVENTEENTRACK,
    ]
    assert loaded.as_dict() == parcel.as_dict()
    assert loaded.state == parcel.state


def test_a_source_from_a_newer_release_reads_as_a_parser() -> None:
    """A record isn't lost because a newer release stored an unknown source."""
    stored = _full_data().as_dict()
    stored["parcels"][0]["origins"][0]["source"] = "newer"
    stored["parcels"][0]["events"][0]["source"] = "newer"
    stored["review"][0]["source"] = "newer"
    loaded = ParcelsData.from_dict(stored)
    parcel = loaded.parcels["p_test"]
    assert parcel.origins["o1"].source is Source.PARSER
    assert parcel.events[0].source is Source.PARSER
    assert loaded.review["r1"].source is Source.PARSER


def test_name_from_the_latest_origin_that_has_one() -> None:
    """A delivery only in the Parcel app is named after its description."""
    parcel = _parcel(
        origins=(
            _origin("pa:1", source=Source.PARCELAPP, name="Old name"),
            _origin("pa:2", source=Source.PARCELAPP, time=at(hours=1), name="Lamp"),
            _origin("o1", time=at(hours=2)),
        )
    )
    assert parcel.state.name == "Lamp"
    assert parcel.state.source is Source.PARSER
    assert _parcel().state.name is None
    only = _parcel(origins=(_origin("pa:1", source=Source.PARCELAPP, name="Lamp"),))
    assert only.state.source is Source.PARCELAPP


def test_sender_preferences() -> None:
    """Sender domains are case-insensitive."""
    data = ParcelsData()
    data.sender("Example.COM").ignored = True
    assert data.is_ignored("example.com")
    assert not data.is_ignored("other.example")
