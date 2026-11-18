"""Tests for reconciling whole parcels, inferred deliveries and the repair."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime
from typing import Any

from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import MailKind, ParcelStatus
from custom_components.parcels.dedup import (
    REASON_SAME_MERCHANT_DAY,
    REASON_SAME_MERCHANT_DOMAIN,
    Contribution,
    DedupError,
    accept_suggestion,
    apply_contribution,
    dismiss_suggestion,
    infer_deliveries,
    order_parcels,
    reconcile,
    repair_store,
    undo_auto_merge,
    undo_inferred_delivery,
    update_parcel,
)
from custom_components.parcels.models import ParcelsData, Source, order_key
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.parsers.tracking import tracking_url

from .factories import contribution

ORDER_1 = "171-0000001-0000001"
ORDER_2 = "171-0000002-0000002"
ORDER_3 = "171-0000003-0000003"
CTT_1 = "EX123456789012"
CTT_2 = "EX123456789013"
SHOP = "bricolage-exemplo.example"
SHOP_NAME = "Bricolage Exemplo"
SHOP_ORDER = "2630001234"
GLS = ("61234567890123", "61234567890124", "61234567890125")


@pytest.fixture(autouse=True)
def lisbon() -> Generator[None]:
    """Use the Lisbon time zone for local dates."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Lisbon"))
    yield
    dt_util.set_default_time_zone(previous)


def _nov(day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


# The first sync of a mailbox reads every e-mail at once.
SYNC = _nov(4, 13)


def _eta(start: int, end: int | None = None) -> Eta:
    return Eta(start=date(2026, 11, start), end=date(2026, 11, end or start))


def _apply(
    data: ParcelsData, contrib: Contribution, now: datetime | None = None
) -> str:
    applied = apply_contribution(data, contrib, now or contrib.origin.time)
    assert applied.parcel_id
    return applied.parcel_id


def _ctt(origin_id: str, number: str, kind: MailKind, when: datetime) -> Contribution:
    """A carrier's e-mail about a parcel from Amazon: no order number."""
    return contribution(
        origin_id,
        kind=kind,
        time=when,
        carrier="ctt_expresso",
        number=number,
        merchant="Amazon",
        label="cttexpresso.pt",
    )


def _amazon(
    origin_id: str, order: str, when: datetime, eta: Eta | None, **kwargs: Any
) -> Contribution:
    """Amazon's "shipped" e-mail: an order number and no carrier number."""
    return contribution(
        origin_id,
        time=when,
        merchant="Amazon.es",
        orders=[order],
        eta=eta,
        label="amazon.es",
        **kwargs,
    )


def _shop_order(
    origin_id: str, when: datetime, order: str = SHOP_ORDER
) -> Contribution:
    """A shop's "shipped" e-mail without a tracking number."""
    return contribution(
        origin_id,
        time=when,
        merchant=SHOP_NAME,
        orders=[order],
        eta=_eta(20),
        label=SHOP,
    )


def _shop_gls(origin_id: str, number: str, when: datetime) -> Contribution:
    """A carrier notice the shop sends from its domain under the carrier's name."""
    return contribution(
        origin_id,
        kind=MailKind.IN_TRANSIT,
        time=when,
        merchant="GLS PT Informa",
        number=number,
        eta=_eta(18),
        label=SHOP,
    )


def _error(func: Any, *args: Any) -> str:
    with pytest.raises(DedupError) as err:
        func(*args)
    return err.value.reason


def test_order_joins_carrier_delivery_of_its_day() -> None:
    """The shop's e-mail and the carrier's delivery that day are one parcel.

    Graph doesn't list e-mails in time order, so the carrier's parcel may
    already be delivered when the older shop e-mail is read.
    """
    data = ParcelsData()
    ctt = _apply(
        data, _ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _nov(4, 9, 54)), SYNC
    )
    assert (
        _apply(data, _ctt("msg:c2#0", CTT_1, MailKind.DELIVERED, _nov(4, 11, 28)), SYNC)
        == ctt
    )
    amazon = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(4, 1, 31), _eta(4)), SYNC)
    assert amazon != ctt

    result = reconcile(data, SYNC)

    assert result.removed == {amazon}
    assert result.changed == {ctt}
    assert result.suggestions == []
    parcel = data.parcels[ctt]
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert state.merchant == "Amazon"
    assert state.carrier == "ctt_expresso"
    assert state.order_numbers == (ORDER_1,)
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_DAY
    assert parcel.auto_merged.origin == "msg:a1#0"
    assert order_parcels(data, order_key("Amazon", ORDER_1)) == [parcel]

    split = undo_auto_merge(data, ctt, SYNC)
    assert split is not None
    assert set(split.origins) == {"msg:a1#0"}
    again = reconcile(data, SYNC)
    assert not again.removed
    assert again.suggestions == []
    assert len(data.parcels) == 2


def test_order_mail_after_the_delivery_stays_apart() -> None:
    """An order e-mail sent after the carrier delivered is another parcel."""
    data = ParcelsData()
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(4, 11, 28)), SYNC)
    _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(4, 12), _eta(4)), SYNC)

    result = reconcile(data, SYNC)

    assert not result.removed
    assert result.suggestions == []
    assert infer_deliveries(data, _nov(5, 8)) == set()


def test_same_day_groups_are_suggested() -> None:
    """Two orders and two deliveries on one day: the user picks the pairs."""
    data = ParcelsData()
    first = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(4, 11)), SYNC)
    second = _apply(
        data, _ctt("msg:c2#0", CTT_2, MailKind.DELIVERED, _nov(4, 12)), SYNC
    )
    one = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(3, 1), _eta(4)), SYNC)
    two = _apply(data, _amazon("msg:a2#0", ORDER_2, _nov(3, 2), _eta(4)), SYNC)
    assert len(data.parcels) == 4

    result = reconcile(data, SYNC)

    assert not result.removed
    targets = sorted((first, second))
    assert [suggestion.parcel_id for suggestion in result.suggestions] == targets
    for suggestion in result.suggestions:
        assert suggestion.candidates == (one, two)
        assert suggestion.day == date(2026, 11, 4)
        assert suggestion.merchant == "Amazon"
        assert suggestion.reason == REASON_SAME_MERCHANT_DAY
    assert result.suggestions[0].id != result.suggestions[1].id

    dismiss_suggestion(data, targets[0], [one, two])
    result = reconcile(data, SYNC)
    assert [(s.parcel_id, s.candidates) for s in result.suggestions] == [
        (targets[1], (one, two))
    ]
    assert _error(dismiss_suggestion, data, "p_gone", []) == "unknown_parcel"


def test_accepting_a_suggestion_merges() -> None:
    """An accepted suggestion merges; two tracking numbers never do."""
    data = ParcelsData()
    first = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(4, 11)), SYNC)
    second = _apply(
        data, _ctt("msg:c2#0", CTT_2, MailKind.DELIVERED, _nov(4, 12)), SYNC
    )
    order = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(3, 1), _eta(4)), SYNC)

    result = reconcile(data, SYNC)

    assert not result.removed
    assert sorted(s.parcel_id for s in result.suggestions) == sorted((first, second))
    assert all(s.candidates == (order,) for s in result.suggestions)

    assert _error(accept_suggestion, data, first, first, SYNC) == "merge_needs_two"
    assert _error(accept_suggestion, data, first, "p_gone", SYNC) == "unknown_parcel"
    assert _error(accept_suggestion, data, first, second, SYNC) == "cannot_merge"

    merged = accept_suggestion(data, first, order, SYNC)
    assert merged.id == first
    assert merged.auto_merged is None
    assert order not in data.parcels
    assert merged.state.order_numbers == (ORDER_1,)
    assert reconcile(data, SYNC).suggestions == []


def test_shop_shipments_absorb_the_order() -> None:
    """A shop's carrier notices name the carrier and absorb the order's parcel."""
    data = ParcelsData()
    order = _apply(data, _shop_order("msg:o1#0", _nov(15, 21, 45)))
    shipments = [
        _apply(data, _shop_gls(f"msg:g{index}#0", number, _nov(16, 18, 50 + index)))
        for index, number in enumerate(GLS)
    ]
    assert len({order, *shipments}) == 4
    for parcel_id, number in zip(shipments, GLS, strict=True):
        state = data.parcels[parcel_id].state
        assert state.carrier == "gls"
        assert state.tracking_url == tracking_url("gls", number)
        assert state.merchant == SHOP_NAME

    result = reconcile(data, _nov(16, 19))

    assert result.removed == {order}
    assert result.suggestions == []
    parcel = data.parcels[shipments[0]]
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_DOMAIN
    assert parcel.auto_merged.origin == "msg:o1#0"
    assert parcel.state.order_numbers == (SHOP_ORDER,)
    assert parcel.state.carrier == "gls"
    assert parcel.state.merchant == SHOP_NAME
    assert parcel.state.eta == _eta(18)
    assert len(data.parcels) == 3


def test_shop_named_once_its_name_is_known() -> None:
    """A carrier brand never names the shop; its domain does until the name."""
    data = ParcelsData()
    shipment = _apply(data, _shop_gls("msg:g1#0", GLS[0], _nov(16, 18, 50)), SYNC)
    state = data.parcels[shipment].state
    assert state.carrier == "gls"
    assert state.merchant == SHOP
    order = _apply(data, _shop_order("msg:o1#0", _nov(15, 21, 45)), SYNC)
    assert order != shipment

    result = reconcile(data, _nov(16, 19))

    assert result.removed == {order}
    assert result.changed == {shipment}
    assert data.parcels[shipment].state.merchant == SHOP_NAME
    assert data.parcels[shipment].state.order_numbers == (SHOP_ORDER,)


def test_shop_with_two_open_orders_gets_a_suggestion() -> None:
    """With two orders that could be the shipment, the user decides."""
    data = ParcelsData()
    first = _apply(data, _shop_order("msg:o1#0", _nov(15, 21, 45)))
    second = _apply(data, _shop_order("msg:o2#0", _nov(15, 22), order="2630005678"))
    shipment = _apply(data, _shop_gls("msg:g1#0", GLS[0], _nov(16, 18, 50)))

    result = reconcile(data, _nov(16, 19))

    assert not result.removed
    assert [
        (s.parcel_id, s.candidates, s.day, s.reason) for s in result.suggestions
    ] == [(shipment, (first, second), None, REASON_SAME_MERCHANT_DOMAIN)]


def test_inferred_delivery() -> None:
    """Orders packed into one carrier parcel close with its delivery."""
    data = ParcelsData()
    orders = [
        _apply(data, _amazon(f"msg:a{day}#0", order, _nov(day, 8), _eta(4)))
        for day, order in enumerate((ORDER_1, ORDER_2, ORDER_3), start=1)
    ]
    ctt = _apply(
        data, _ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _nov(4, 9, 54))
    )
    _apply(data, _ctt("msg:c2#0", CTT_1, MailKind.DELIVERED, _nov(4, 11, 28)))
    assert len(data.parcels) == 4

    # Not before the day after the expected day.
    assert infer_deliveries(data, _nov(4, 23)) == set()
    assert infer_deliveries(data, _nov(5, 8)) == set(orders)
    for parcel_id in orders:
        parcel = data.parcels[parcel_id]
        assert parcel.state.status is ParcelStatus.DELIVERED
        assert parcel.state.inferred
        assert parcel.state.delivered_at == _nov(4, 11, 28)
        assert [entry.inferred for entry in parcel.state.timeline] == [False, True]
    assert not data.parcels[ctt].state.inferred
    assert len(data.parcels) == 4
    assert infer_deliveries(data, _nov(5, 9)) == set()

    # News about the order replaces the guess.
    _apply(
        data,
        _amazon("msg:a9#0", ORDER_1, _nov(5, 10), None, kind=MailKind.IN_TRANSIT),
    )
    state = data.parcels[orders[0]].state
    assert state.status is ParcelStatus.IN_TRANSIT
    assert not state.inferred
    assert infer_deliveries(data, _nov(6, 8)) == set()


@pytest.mark.parametrize(
    ("eta_day", "inferred"), [(2, False), (3, True), (5, True), (6, False)]
)
def test_inferred_delivery_margin(eta_day: int, inferred: bool) -> None:
    """A delivery within a day of the expected days counts."""
    data = ParcelsData()
    order = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(1, 8), _eta(eta_day)))
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(4, 11, 28)))
    assert infer_deliveries(data, _nov(10, 8)) == ({order} if inferred else set())


def test_tracked_parcels_arent_inferred() -> None:
    """A parcel with a carrier number waits for its carrier."""
    data = ParcelsData()
    _apply(
        data,
        _amazon(
            "msg:a1#0",
            ORDER_1,
            _nov(1, 8),
            _eta(4),
            carrier="amazon",
            number="TBA123456789012",
        ),
    )
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(4, 11, 28)))
    assert len(data.parcels) == 2
    assert infer_deliveries(data, _nov(10, 8)) == set()


def test_undo_and_confirm_inferred_delivery() -> None:
    """The user can take an inferred delivery back, or keep it."""
    data = ParcelsData()
    undone = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(1, 8), _eta(3)))
    kept = _apply(data, _amazon("msg:a2#0", ORDER_2, _nov(1, 9), _eta(3)))
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(4, 11, 28)))
    assert infer_deliveries(data, _nov(5, 8)) == {undone, kept}

    parcel = undo_inferred_delivery(data, undone, _nov(5, 9))
    assert parcel.delivery_rejected
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert not parcel.state.inferred
    assert infer_deliveries(data, _nov(6, 8)) == set()
    assert (
        _error(undo_inferred_delivery, data, undone, _nov(6, 9))
        == "no_inferred_delivery"
    )

    parcel = update_parcel(data, kept, {"confirm_delivery": True}, _nov(5, 9))
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert not state.inferred
    assert state.delivered_at == _nov(4, 11, 28)
    assert [event.source for event in parcel.events if event.kind] == [
        Source.PARSER,
        Source.MANUAL,
    ]
    assert _error(undo_inferred_delivery, data, kept, _nov(5, 9)) == (
        "no_inferred_delivery"
    )


def test_repair_store() -> None:
    """The one-time repair fixes what 0.1.0 stored."""
    data = ParcelsData()
    untracked = _apply(
        data, _amazon("msg:a1#0", ORDER_1, _nov(1, 8), _eta(4), carrier="amazon")
    )
    by_ai = _apply(
        data,
        _amazon(
            "msg:a2#0",
            ORDER_2,
            _nov(1, 9),
            _eta(5),
            carrier="amazon",
            source=Source.AI,
        ),
    )
    logistics = _apply(
        data,
        _amazon(
            "msg:a3#0",
            ORDER_3,
            _nov(1, 10),
            _eta(6),
            carrier="amazon",
            number="TBA123456789012",
        ),
    )
    edited = _apply(
        data,
        _amazon(
            "msg:a4#0", "171-0000004-0000004", _nov(1, 11), _eta(7), carrier="amazon"
        ),
    )
    update_parcel(data, edited, {"carrier": "amazon"}, _nov(1, 12))
    order = _apply(data, _shop_order("msg:o1#0", _nov(15, 21, 45)))
    shipment = _apply(data, _shop_gls("msg:g1#0", GLS[0], _nov(16, 18, 50)))
    # What 0.1.0 stored for the shop's carrier notice.
    parcel = data.parcels[shipment]
    stored = parcel.origins["msg:g1#0"]
    stored.carrier = None
    stored.merchant = "GLS PT Informa"
    stored.tracking_url = tracking_url(None, GLS[0])
    parcel.touch(_nov(16, 18, 50))
    assert parcel.state.carrier is None
    data.orders.clear()

    changed = repair_store(data, _nov(17, 8))

    assert changed == {untracked, by_ai, edited, shipment}
    assert data.parcels[untracked].state.carrier is None
    assert data.parcels[by_ai].state.carrier is None
    assert data.parcels[logistics].state.carrier == "amazon"
    assert data.parcels[edited].state.carrier == "amazon"
    state = data.parcels[shipment].state
    assert state.carrier == "gls"
    assert state.tracking_url == tracking_url("gls", GLS[0])
    assert state.merchant == SHOP_NAME
    assert data.parcels[order].state.merchant == SHOP_NAME
    assert {order_key("Amazon", ORDER_1), order_key(SHOP_NAME, SHOP_ORDER)} <= set(
        data.orders
    )
    assert repair_store(data, _nov(17, 9)) == set()
