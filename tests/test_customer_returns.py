"""Tests for customer returns: pickup days, joining e-mails and deliveries.

Made-up orders and items only.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.calendar import (
    PRIVATE_RETURN_TITLE,
    RETURN_PICKUP_LINES,
    return_event,
)
from custom_components.parcels.const import CARRIER_NAMES, MailKind, ParcelStatus
from custom_components.parcels.customer_returns import (
    INFERRED_RETURN,
    apply_return,
    infer_return_deliveries,
    linked_parcels,
    order_index,
    pickup_suggestion,
    remove_return,
    return_origin,
)
from custom_components.parcels.dedup import (
    add_owner,
    apply_contribution,
    remove_message,
)
from custom_components.parcels.models import (
    Parcel,
    ParcelEvent,
    ParcelsData,
    PickupRule,
    ReturnEntry,
    ReturnOrigin,
    Source,
    Suggestion,
)
from custom_components.parcels.parsers.base import Eta, ParsedShipment, ParseResult
from custom_components.parcels.parsers.returns import (
    NOTE_PICKUP_NEXT_WORKING_DAY,
    NOTE_RETURN_RECEIVED,
)
from custom_components.parcels.parsers.tracking import tracking_url
from custom_components.parcels.store import apply_retention
from custom_components.parcels.views import Viewer, return_json

from .factories import contribution

ORDER_1 = "171-0000001-0000001"
ORDER_2 = "171-0000002-0000002"
LAMP = "Candeeiro Exemplo de secretária, LED, 5 W"
MUG = "Caneca Exemplo de cerâmica, 350 ml"
CTT_1 = "EX123456789012"
CTT_2 = "EX123456789013"
ALEX = "person.alex"
SAM = "person.sam"
SHOP = {"merchant": "Loja Exemplo", "label": "loja-exemplo.example"}


@pytest.fixture(autouse=True)
def lisbon() -> Generator[None]:
    """Use the Lisbon time zone for local dates."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Lisbon"))
    yield
    dt_util.set_default_time_zone(previous)


def _nov(day: int, hour: int = 12, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def _weekday_after(day: date) -> date:
    """Return the next working day, Monday to Friday."""
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _result(
    *,
    merchant: str | None = "Amazon",
    orders: tuple[str, ...] = (ORDER_1,),
    items: tuple[str, ...] = (LAMP,),
    notes: tuple[str, ...] = (),
    pickup: date | None = None,
    pickup_end: date | None = None,
    carrier: str | None = None,
    number: str | None = None,
) -> ParseResult:
    """Return what a parser read from a shop's return e-mail."""
    shipments = []
    if pickup or carrier or number:
        eta = Eta(start=pickup, end=pickup_end or pickup) if pickup else None
        shipments.append(
            ParsedShipment(carrier=carrier, tracking_number=number, eta=eta)
        )
    return ParseResult(
        parser="amazon",
        kind=MailKind.CUSTOMER_RETURN,
        merchant=merchant,
        order_numbers=orders,
        items=items,
        shipments=shipments,
        confidence=0.9,
        notes=notes,
    )


def _origin(
    message: str,
    time: datetime,
    *,
    label: str = "amazon.es",
    owners: tuple[str, ...] = (ALEX,),
    **kwargs: Any,
) -> ReturnOrigin:
    return return_origin(
        _result(**kwargs),
        message_hash=message,
        time=time,
        source=Source.PARSER,
        label=label,
        owners=owners,
        next_working_day=_weekday_after,
    )


def _apply(
    data: ParcelsData, message: str, time: datetime, **kwargs: Any
) -> ReturnEntry:
    return apply_return(data, _origin(message, time, **kwargs), time)


def _bare(
    message: str,
    time: datetime,
    pickup: date | None = None,
    rule: PickupRule | None = None,
    **kwargs: Any,
) -> ReturnOrigin:
    return ReturnOrigin(
        message=message,
        time=time,
        label="amazon.es",
        pickup=pickup,
        pickup_rule=rule,
        **kwargs,
    )


def _entry(*origins: ReturnOrigin) -> ReturnEntry:
    entry = ReturnEntry(id="ret_1", created=_nov(1), updated=_nov(1))
    for origin in origins:
        entry.origins[origin.message] = origin
    return entry


def _shipped(
    data: ParcelsData,
    origin_id: str,
    *,
    items: tuple[str, ...] = (LAMP,),
    eta: tuple[int, int] | None = None,
    time: datetime | None = None,
    **kwargs: Any,
) -> str:
    """Add Amazon's "shipped" e-mail for ORDER_1; return the parcel's ID."""
    when = time or _nov(3)
    contrib = contribution(
        origin_id,
        time=when,
        merchant="Amazon.es",
        orders=[ORDER_1],
        items=items,
        eta=(
            Eta(start=date(2026, 11, eta[0]), end=date(2026, 11, eta[1]))
            if eta
            else None
        ),
        label="amazon.es",
        **kwargs,
    )
    applied = apply_contribution(data, contrib, when)
    assert applied.parcel_id
    return applied.parcel_id


def _set_events(parcel: Parcel, *events: ParcelEvent) -> None:
    parcel.events.extend(events)
    parcel.touch(_nov(9))


# --- Pickup days -----------------------------------------------------------------


def test_pickup_day_from_the_email() -> None:
    origin = _origin("m1", _nov(12, 9), pickup=date(2026, 11, 13))
    assert (origin.pickup, origin.pickup_rule) == (date(2026, 11, 13), PickupRule.EMAIL)
    # Between two days: the first.
    window = _origin(
        "m2", _nov(12, 9), pickup=date(2026, 11, 13), pickup_end=date(2026, 11, 14)
    )
    assert window.pickup == date(2026, 11, 13)


def test_next_working_day_skips_the_weekend() -> None:
    # Friday afternoon: picked up on Monday.
    origin = _origin("m1", _nov(13, 15), notes=(NOTE_PICKUP_NEXT_WORKING_DAY,))
    assert (origin.pickup, origin.pickup_rule) == (
        date(2026, 11, 16),
        PickupRule.NEXT_WORKING_DAY,
    )


def test_next_working_day_counts_from_the_local_day() -> None:
    # 23:30 UTC on Tuesday 30 June is Wednesday 1 July in Lisbon.
    time = datetime(2026, 6, 30, 23, 30, tzinfo=UTC)
    origin = _origin("m1", time, notes=(NOTE_PICKUP_NEXT_WORKING_DAY,))
    assert origin.pickup == date(2026, 7, 2)


def test_pickup_day_assumed_for_amazon_only() -> None:
    amazon = _origin("m1", _nov(10, 15))
    assert (amazon.pickup, amazon.pickup_rule) == (
        date(2026, 11, 11),
        PickupRule.ASSUMED,
    )
    # The sender's domain names the shop when the e-mail doesn't.
    unnamed = _origin("m2", _nov(10, 15), merchant=None, label="amazon.de")
    assert unnamed.pickup_rule is PickupRule.ASSUMED
    other = _origin("m3", _nov(10, 15), **SHOP)
    assert (other.pickup, other.pickup_rule) == (None, None)
    # The shop has it back: nothing left to pick up.
    received = _origin("m4", _nov(10, 15), notes=(NOTE_RETURN_RECEIVED,))
    assert received.received
    assert (received.pickup, received.pickup_rule) == (None, None)


def test_origin_keeps_orders_items_carrier_and_owners() -> None:
    result = _result(items=(LAMP, LAMP.upper()), carrier="ctt_expresso", number=CTT_1)
    result.shipments[0] = replace(
        result.shipments[0], order_numbers=(ORDER_1, ORDER_2), items=(MUG,)
    )
    origin = return_origin(
        result,
        message_hash="m1",
        time=_nov(10),
        source=Source.PARSER,
        label="amazon.es",
        owners=(SAM, "", ALEX, SAM),
        next_working_day=_weekday_after,
    )
    assert origin.order_numbers == (ORDER_1, ORDER_2)
    assert origin.items == (LAMP, MUG)
    assert (origin.carrier, origin.tracking_number) == ("ctt_expresso", CTT_1)
    assert origin.owners == (ALEX, SAM)


def test_pickup_from_an_email_beats_next_working_day_beats_assumed() -> None:
    entry = _entry(
        _bare("m1", _nov(10), date(2026, 11, 12), PickupRule.EMAIL),
        _bare("m2", _nov(11), date(2026, 11, 13), PickupRule.NEXT_WORKING_DAY),
        _bare("m3", _nov(12), date(2026, 11, 16), PickupRule.ASSUMED),
    )
    assert entry.pickup == (date(2026, 11, 12), PickupRule.EMAIL)
    del entry.origins["m1"]
    assert entry.pickup == (date(2026, 11, 13), PickupRule.NEXT_WORKING_DAY)
    # Among e-mails of the same rank, the newest wins.
    entry.origins["m4"] = _bare(
        "m4", _nov(13), date(2026, 11, 17), PickupRule.NEXT_WORKING_DAY
    )
    assert entry.pickup == (date(2026, 11, 17), PickupRule.NEXT_WORKING_DAY)


def test_day_and_done() -> None:
    entry = _entry(_bare("m1", _nov(10, 15), date(2026, 11, 11), PickupRule.ASSUMED))
    assert entry.day == date(2026, 11, 11)
    assert not entry.done(date(2026, 11, 11))
    assert entry.done(date(2026, 11, 12))
    # The shop has it back: done before its day.
    entry.origins["m2"] = _bare("m2", _nov(10, 18), received=True)
    assert entry.done(date(2026, 11, 10))
    # Without a pickup day: the day of the first e-mail, in Lisbon.
    summer = _entry(_bare("m3", datetime(2026, 6, 30, 23, 30, tzinfo=UTC)))
    assert summer.day == date(2026, 7, 1)


def test_the_sender_names_the_shop() -> None:
    assert _entry(_bare("m1", _nov(10))).merchant == "Amazon"


# --- Joining e-mails -------------------------------------------------------------


def test_the_same_email_in_another_mailbox_adds_its_owner() -> None:
    data = ParcelsData()
    first = _apply(data, "m1", _nov(10), owners=(ALEX,))
    assert _apply(data, "m1", _nov(10), owners=(SAM,)) is first
    assert list(data.returns) == [first.id]
    assert list(first.origins) == ["m1"]
    assert first.owners == (ALEX, SAM)


def test_emails_about_one_return_join() -> None:
    data = ParcelsData()
    first = _apply(data, "m1", _nov(10))
    assert _apply(data, "m2", _nov(12)) is first
    # Without items, the order is enough.
    assert _apply(data, "m3", _nov(13), items=()) is first
    assert len(data.returns) == 1


def test_parts_of_an_order_sent_back_apart_stay_apart() -> None:
    data = ParcelsData()
    lamp = _apply(data, "m1", _nov(10))
    mug = _apply(data, "m2", _nov(11), items=(MUG,))
    other_order = _apply(data, "m3", _nov(11), orders=(ORDER_2,))
    assert len({lamp.id, mug.id, other_order.id}) == 3


def test_emails_without_orders_join_on_the_shop_and_an_item() -> None:
    data = ParcelsData()
    first = _apply(data, "m1", _nov(10), orders=())
    assert _apply(data, "m2", _nov(11), orders=()) is first
    # An e-mail with the order joins on the same terms.
    assert _apply(data, "m3", _nov(11)) is first
    other_shop = _apply(data, "m4", _nov(11), orders=(), **SHOP)
    other_item = _apply(data, "m5", _nov(11), orders=(), items=(MUG,))
    no_items = _apply(data, "m6", _nov(11), orders=(), items=())
    assert len({first.id, other_shop.id, other_item.id, no_items.id}) == 4


def test_emails_join_within_a_week() -> None:
    week = timedelta(days=7)
    data = ParcelsData()
    first = _apply(data, "m1", _nov(10))
    assert _apply(data, "m2", _nov(10) + week) is first
    assert _apply(data, "m3", _nov(10) - week) is first
    # A week from the first e-mail, now on 3 November.
    later = _apply(data, "m4", _nov(3) + week + timedelta(minutes=1))
    assert later is not first


def test_the_shops_received_email_joins_within_45_days() -> None:
    days = timedelta(days=45)
    data = ParcelsData()
    first = _apply(data, "m1", _nov(2))
    received = (NOTE_RETURN_RECEIVED,)
    # Not before the return started.
    early = _apply(data, "m2", _nov(2) - timedelta(minutes=1), notes=received)
    assert early is not first
    late = _apply(data, "m3", _nov(2) + days + timedelta(minutes=1), notes=received)
    assert late is not first
    assert not first.received
    assert _apply(data, "m4", _nov(2) + days, notes=received) is first
    assert first.received


def test_after_the_shop_has_it_a_new_email_is_a_new_return() -> None:
    data = ParcelsData()
    first = _apply(data, "m1", _nov(10))
    _apply(data, "m2", _nov(12), notes=(NOTE_RETURN_RECEIVED,))
    assert _apply(data, "m3", _nov(13)) is not first


def test_an_email_that_fits_two_returns_joins_the_closest_open_one() -> None:
    data = ParcelsData()
    lamp = _apply(data, "m1", _nov(2))
    mug = _apply(data, "m2", _nov(5), items=(MUG,))
    # The IDs only break ties: make them prefer the other one.
    lamp.id, mug.id = "ret_a", "ret_b"
    data.returns = {lamp.id: lamp, mug.id: mug}
    # It names both items: the return that started closest.
    assert _apply(data, "m3", _nov(6), items=(LAMP, MUG)) is mug
    # The shop has the mug back; its next "received" e-mail is the lamp's.
    _apply(data, "m4", _nov(7), items=(MUG,), notes=(NOTE_RETURN_RECEIVED,))
    assert mug.received
    received = _apply(
        data, "m5", _nov(8), items=(LAMP, MUG), notes=(NOTE_RETURN_RECEIVED,)
    )
    assert received is lamp


def test_a_new_email_brings_an_archived_return_back() -> None:
    data = ParcelsData()
    entry = _apply(data, "m1", _nov(10))
    entry.archived = _nov(11)
    # The pickup moved to Monday: on the page again.
    _apply(data, "m2", _nov(12), pickup=date(2026, 11, 16))
    assert entry.archived is None
    # Not after its day.
    entry.archived = _nov(17)
    apply_return(data, _origin("m3", _nov(13)), _nov(17))
    assert entry.archived == _nov(17)


# --- Deliveries ------------------------------------------------------------------


def test_a_returned_parcel_on_its_way_gets_an_inferred_delivery() -> None:
    data = ParcelsData()
    parcel_id = _shipped(data, "msg:s1#0", eta=(5, 6))
    _apply(data, "m1", _nov(10))
    assert infer_return_deliveries(data, _nov(10, 13)) == {parcel_id}
    parcel = data.parcels[parcel_id]
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert parcel.state.inferred
    event = parcel.events[-1]
    assert (event.label, event.inferred, event.source) == (
        INFERRED_RETURN,
        True,
        Source.PARSER,
    )
    assert parcel.updated == _nov(10, 13)
    # Once is enough.
    assert infer_return_deliveries(data, _nov(10, 14)) == set()
    assert sum(event.inferred for event in parcel.events) == 1


@pytest.mark.parametrize(
    ("eta", "shipped", "delivered"),
    [
        # Noon of its last expected day.
        ((5, 6), _nov(3), _nov(6, 12)),
        # News after that day: delivered after the news.
        ((5, 6), _nov(7, 8), _nov(7, 8)),
        # No expected day: when the return started.
        (None, _nov(3), _nov(10)),
        # Never after the return started.
        ((5, 6), _nov(11), _nov(10)),
    ],
)
def test_when_a_returned_parcel_arrived(
    eta: tuple[int, int] | None, shipped: datetime, delivered: datetime
) -> None:
    data = ParcelsData()
    parcel_id = _shipped(data, "msg:s1#0", eta=eta, time=shipped)
    _apply(data, "m1", _nov(10))
    infer_return_deliveries(data, _nov(11, 13))
    assert data.parcels[parcel_id].events[-1].time == delivered


def test_of_an_orders_parcels_the_one_with_the_item() -> None:
    data = ParcelsData()
    _shipped(data, "msg:s1#0", carrier="ctt_expresso", number=CTT_1)
    mug = _shipped(data, "msg:s2#0", items=(MUG,), carrier="ctt_expresso", number=CTT_2)
    _apply(data, "m1", _nov(10), items=(MUG,))
    assert infer_return_deliveries(data, _nov(10)) == {mug}


def test_the_orders_only_parcel_whatever_the_items() -> None:
    data = ParcelsData()
    parcel_id = _shipped(data, "msg:s1#0")
    _apply(data, "m1", _nov(10), items=())
    assert infer_return_deliveries(data, _nov(10)) == {parcel_id}


@pytest.mark.parametrize(
    ("second", "returned"),
    [
        # Both parcels hold the item.
        (LAMP, (LAMP,)),
        # The return names no item.
        (MUG, ()),
    ],
)
def test_no_inferred_delivery_when_the_parcel_is_unclear(
    second: str, returned: tuple[str, ...]
) -> None:
    data = ParcelsData()
    _shipped(data, "msg:s1#0", carrier="ctt_expresso", number=CTT_1)
    _shipped(data, "msg:s2#0", items=(second,), carrier="ctt_expresso", number=CTT_2)
    _apply(data, "m1", _nov(10), items=returned)
    assert infer_return_deliveries(data, _nov(10)) == set()


@pytest.mark.parametrize("case", ["delivered", "rejected", "undone_by_hand"])
def test_no_inferred_delivery_for(case: str) -> None:
    data = ParcelsData()
    parcel = data.parcels[_shipped(data, "msg:s1#0")]
    delivered = ParcelEvent(
        time=_nov(5),
        source=Source.PARSER,
        status=ParcelStatus.DELIVERED,
        kind=MailKind.DELIVERED,
        inferred=case == "undone_by_hand",
    )
    if case == "rejected":
        parcel.delivery_rejected = True
    elif case == "delivered":
        _set_events(parcel, delivered)
    else:
        # The user set an inferred delivery back to "in transit".
        moved = ParcelEvent(
            time=_nov(6),
            source=Source.MANUAL,
            status=ParcelStatus.IN_TRANSIT,
            force=True,
        )
        _set_events(parcel, delivered, moved)
        assert parcel.state.status is ParcelStatus.IN_TRANSIT
    events = list(parcel.events)
    _apply(data, "m1", _nov(10))
    assert infer_return_deliveries(data, _nov(10)) == set()
    assert parcel.events == events


def test_removing_a_return_takes_back_its_inferred_delivery() -> None:
    data = ParcelsData()
    parcel_id = _shipped(data, "msg:s1#0")
    entry = _apply(data, "m1", _nov(10))
    infer_return_deliveries(data, _nov(10))
    parcel = data.parcels[parcel_id]
    parcel.archived = _nov(12)
    assert remove_return(data, entry.id, _nov(13)) is entry
    assert entry.id not in data.returns
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert not any(event.inferred for event in parcel.events)
    assert parcel.updated == _nov(13)
    # Not finished any more: back on the page.
    assert parcel.archived is None
    with pytest.raises(KeyError):
        remove_return(data, entry.id, _nov(13))


def test_a_delivery_another_return_inferred_stays() -> None:
    data = ParcelsData()
    parcel_id = _shipped(data, "msg:s1#0", items=(LAMP, MUG))
    lamp = _apply(data, "m1", _nov(10))
    mug = _apply(data, "m2", _nov(11), items=(MUG,))
    infer_return_deliveries(data, _nov(11))
    remove_return(data, lamp.id, _nov(12))
    assert data.parcels[parcel_id].state.status is ParcelStatus.DELIVERED
    remove_return(data, mug.id, _nov(12))
    assert data.parcels[parcel_id].state.status is ParcelStatus.SHIPPED


def test_removing_a_return_keeps_other_inferred_deliveries() -> None:
    data = ParcelsData()
    parcel = data.parcels[_shipped(data, "msg:s1#0")]
    # Inferred from another parcel of the shop, before the return.
    _set_events(
        parcel,
        ParcelEvent(
            time=_nov(6),
            source=Source.PARSER,
            status=ParcelStatus.DELIVERED,
            kind=MailKind.DELIVERED,
            inferred=True,
        ),
    )
    entry = _apply(data, "m1", _nov(10))
    updated = parcel.updated
    remove_return(data, entry.id, _nov(12))
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert parcel.state.inferred
    assert parcel.updated == updated


# --- Storage, retention and the mailboxes ----------------------------------------


def test_returns_are_archived_after_their_day_and_purged_later() -> None:
    data = ParcelsData()
    entry = _apply(data, "m1", _nov(2))
    _apply(data, "m2", _nov(4), notes=(NOTE_RETURN_RECEIVED,))
    assert entry.day == date(2026, 11, 3)
    apply_retention(data, _nov(16, 23), archive_days=14, purge_days=90)
    assert entry.archived is None
    result = apply_retention(data, _nov(17), archive_days=14, purge_days=90)
    assert result.returns_archived == [entry.id]
    assert entry.archived == _nov(17)
    # 90 days after its last e-mail.
    purge = _nov(4) + timedelta(days=90)
    apply_retention(data, purge - timedelta(minutes=1), archive_days=14, purge_days=90)
    assert entry.id in data.returns
    result = apply_retention(data, purge, archive_days=14, purge_days=90)
    assert result.returns_purged == [entry.id]
    assert not data.returns


def test_a_return_waiting_for_its_pickup_stays() -> None:
    data = ParcelsData()
    entry = _apply(data, "m1", _nov(2), pickup=date(2026, 11, 30))
    apply_retention(data, _nov(29), archive_days=14, purge_days=90)
    assert entry.archived is None


def test_removing_an_email_removes_what_it_said_about_returns() -> None:
    data = ParcelsData()
    entry = _apply(data, "m1", _nov(10))
    _apply(data, "m2", _nov(11), pickup=date(2026, 11, 13))
    assert remove_message(data, "m2", _nov(12)) == set()
    assert list(entry.origins) == ["m1"]
    assert entry.updated == _nov(12)
    assert entry.pickup == (date(2026, 11, 11), PickupRule.ASSUMED)
    remove_message(data, "m1", _nov(12))
    assert not data.returns


def test_an_email_in_another_mailbox_adds_its_owner_to_the_return() -> None:
    data = ParcelsData()
    entry = _apply(data, "m1", _nov(10))
    assert add_owner(data, "m1", SAM, _nov(11)) == set()
    assert entry.owners == (ALEX, SAM)
    assert entry.updated == _nov(11)


def test_a_return_survives_a_restart() -> None:
    data = ParcelsData()
    entry = _apply(data, "m1", _nov(10), carrier="ctt_expresso", number=CTT_1)
    _apply(data, "m2", _nov(20), notes=(NOTE_RETURN_RECEIVED,))
    entry.archived = _nov(21)
    restored = ParcelsData.from_dict(data.as_dict()).returns[entry.id]
    assert restored == entry
    assert restored.received


def test_a_pickup_rule_from_a_newer_release_is_dropped() -> None:
    stored = _bare("m1", _nov(10), date(2026, 11, 11), PickupRule.EMAIL).as_dict()
    origin = ReturnOrigin.from_dict({**stored, "pickup_rule": "carrier_scan"})
    assert (origin.pickup, origin.pickup_rule) == (None, None)
    origin = ReturnOrigin.from_dict({**stored, "pickup": None})
    assert (origin.pickup, origin.pickup_rule) == (None, None)


def test_a_review_suggestion_gets_the_next_working_day() -> None:
    suggestion = Suggestion(kind=MailKind.CUSTOMER_RETURN, merchant="Loja Exemplo")
    result = _result(notes=(NOTE_PICKUP_NEXT_WORKING_DAY,))
    kwargs: dict[str, Any] = {"time": _nov(13, 15), "next_working_day": _weekday_after}
    filled = pickup_suggestion(suggestion, result, **kwargs)
    assert filled is not None
    assert (filled.eta_start, filled.eta_end) == (date(2026, 11, 16),) * 2
    # A date it already has stays; without the wording nothing changes.
    dated = replace(suggestion, eta_start=date(2026, 11, 20))
    assert pickup_suggestion(dated, result, **kwargs) is dated
    assert pickup_suggestion(suggestion, _result(), **kwargs) is suggestion
    assert pickup_suggestion(None, result, **kwargs) is None


# --- What the page and the calendar show -----------------------------------------


def test_return_json() -> None:
    data = ParcelsData()
    parcel_id = _shipped(data, "msg:s1#0")
    entry = _apply(data, "m1", _nov(10), carrier="ctt_expresso", number=CTT_1)
    linked = linked_parcels(entry, order_index(data))
    assert [parcel.id for parcel in linked] == [parcel_id]
    shown = return_json(entry, Viewer(is_admin=False), linked)
    assert shown == {
        "id": entry.id,
        "merchant": "Amazon",
        "carrier": "ctt_expresso",
        "carrier_name": CARRIER_NAMES["ctt_expresso"],
        "tracking_number": CTT_1,
        "tracking_url": tracking_url("ctt_expresso", CTT_1),
        "day": "2026-11-11",
        "pickup": "2026-11-11",
        "pickup_rule": "assumed",
        "started": _nov(10).isoformat(),
        "received": False,
        "order_numbers": [ORDER_1],
        "items": [LAMP],
        "parcel_ids": [parcel_id],
        "emails": [
            {"time": _nov(10).isoformat(), "label": "amazon.es", "source": "parser"}
        ],
        "private": False,
        "owners": [ALEX],
        "archived": False,
        "restricted": False,
    }


def test_a_private_parcel_makes_its_return_private() -> None:
    data = ParcelsData()
    parcel_id = _shipped(data, "msg:s1#0", owner=SAM)
    data.parcels[parcel_id].private = True
    entry = _apply(data, "m1", _nov(10), owners=(ALEX,))
    linked = linked_parcels(entry, order_index(data))
    sam = return_json(entry, Viewer(is_admin=False, persons=frozenset({SAM})), linked)
    assert not sam["restricted"]
    assert sam["private"]
    assert sam["parcel_ids"] == [parcel_id]
    # The return's own owner sees it, but not the private parcel.
    alex = return_json(entry, Viewer(is_admin=False, persons=frozenset({ALEX})), linked)
    assert not alex["restricted"]
    assert alex["parcel_ids"] == []
    # Anyone else only sees its day, even an administrator.
    other = return_json(entry, Viewer(is_admin=True), linked)
    assert other["restricted"]
    assert other["day"] == "2026-11-11"
    assert [
        other[key]
        for key in ("merchant", "tracking_number", "items", "order_numbers", "emails")
    ] == [None, None, [], [], []]


def test_a_private_return_without_owners_is_for_administrators() -> None:
    entry = _entry(_bare("m1", _nov(10)))
    entry.private = True
    assert not return_json(entry, Viewer(is_admin=True), [])["restricted"]
    assert return_json(entry, Viewer(is_admin=False), [])["restricted"]


def test_calendar_event_of_a_return() -> None:
    data = ParcelsData()
    entry = _apply(data, "m1", _nov(10), carrier="ctt_expresso", number=CTT_1)
    event = return_event(entry, [], date(2026, 11, 11))
    assert event.summary == "Return pickup: Amazon"
    assert (event.start, event.end) == (date(2026, 11, 11), date(2026, 11, 12))
    assert event.uid == entry.id
    assert event.description == "\n".join(
        [
            "Return to the shop",
            RETURN_PICKUP_LINES[PickupRule.ASSUMED],
            f"Carrier: {CARRIER_NAMES['ctt_expresso']}",
            f"Tracking number: {CTT_1}",
        ]
    )
    # Once its day is over.
    assert return_event(entry, [], date(2026, 11, 12)).summary == (
        "Return pickup: Amazon ✓"
    )
    # A private parcel of the order makes it private.
    parcel = data.parcels[_shipped(data, "msg:s1#0")]
    parcel.private = True
    private = return_event(entry, [parcel], date(2026, 11, 11))
    assert private.summary == PRIVATE_RETURN_TITLE
    assert private.description == "\n".join(
        ["Return to the shop", RETURN_PICKUP_LINES[PickupRule.ASSUMED]]
    )


def test_calendar_event_of_a_return_without_a_pickup_day() -> None:
    data = ParcelsData()
    entry = _apply(data, "m1", _nov(10), **SHOP)
    event = return_event(entry, [], date(2026, 11, 10))
    assert event.summary == "Return: Loja Exemplo"
    assert event.start == date(2026, 11, 10)
    assert event.description == "Return to the shop"
    _apply(data, "m2", _nov(12), notes=(NOTE_RETURN_RECEIVED,), **SHOP)
    received = return_event(entry, [], date(2026, 11, 10))
    assert received.summary == "Return: Loja Exemplo ✓"
    assert received.description == "Received by the shop"
