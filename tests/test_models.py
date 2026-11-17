"""Tests for the Parcels data model and its status machine."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date, time
import json
import logging

from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import MailKind, ParcelStatus
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
    ReviewItem,
    SenderPrefs,
    Source,
    Suggestion,
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

    # Without the delay kind, the same status is a step back.
    plain = _parcel(_event(S.OUT_FOR_DELIVERY, at()), _event(S.IN_TRANSIT, at(hours=6)))
    assert plain.state.status is S.OUT_FOR_DELIVERY


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
    origin.confirmed = True
    parcel.touch(at())
    assert not parcel.state.ai


def test_provisional_until_tracked() -> None:
    """An order without a tracking number is provisional."""
    parcel = _parcel(
        _event(S.ORDERED, at()), origins=(_origin(order_numbers=("#1001",)),)
    )
    assert parcel.state.provisional
    parcel.origins["o1"].tracking_number = "05212345678901"
    parcel.touch(at())
    assert not parcel.state.provisional


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


def test_keys() -> None:
    """Merchant and order keys ignore case, accents and marketplaces."""
    assert merchant_key("Amazon.es") == merchant_key("amazon.co.uk") == "amazon"
    assert merchant_key("Loja Ação") == "lojaacao"
    assert merchant_key(None) == ""
    assert order_key("Amazon.es", "405-1234567-1234567") == "ord:40512345671234567"
    assert order_key(None, "405-1234567-1234567") == "ord:40512345671234567"
    assert order_key("Example Shop", "#1001") == "ord:exampleshop:1001"
    assert order_key(None, "#1001") is None
    assert order_key("Example Shop", "#") is None


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
            _origin("man:p_test", source=Source.MANUAL, time=at(), merchant=""),
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
            )
        },
        filtered={
            "f1": FilteredItem(
                "f1", at(), "ghi", at(), "news@example.com", "example.com", "Hi", None
            )
        },
        senders={"example.com": SenderPrefs("example.com", trusted=True)},
        engine={"notifier": {"x": 1}},
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
    assert loaded.review["r1"].suggestion == data.review["r1"].suggestion
    assert loaded.trusted_domains() == ("example.com",)


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


def test_sender_preferences() -> None:
    """Sender domains are case-insensitive."""
    data = ParcelsData()
    data.sender("Example.COM").ignored = True
    assert data.is_ignored("example.com")
    assert not data.is_ignored("other.example")
