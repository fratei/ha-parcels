"""Tests for reconciling whole parcels, inferred deliveries and the repair.

Also how e-mails about one of an order's packages find that package.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import (
    REASON_AI_FILL,
    REASON_AI_SUGGESTION,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.dedup import (
    AMAZON_REPAIR_KEY,
    REASON_SAME_MERCHANT_DAY,
    REASON_SAME_MERCHANT_DOMAIN,
    REASON_SAME_MERCHANT_ETA,
    REASON_SAME_ORDER,
    REASON_SAME_REFERENCE,
    REPAIR_VERSION,
    Applied,
    Contribution,
    DedupError,
    accept_suggestion,
    apply_contribution,
    boxes_of_day,
    dismiss_suggestion,
    infer_deliveries,
    keep_apart,
    merge_parcels,
    order_parcels,
    reconcile,
    remove_message,
    repair_store,
    undo_auto_merge,
    undo_inferred_delivery,
    update_parcel,
)
from custom_components.parcels.models import (
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    ReviewItem,
    Source,
    Suggestion,
    order_key,
)
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.parsers.tracking import tracking_url
from custom_components.parcels.views import shipment_groups

from .factories import contribution

ORDER_1 = "171-0000001-0000001"
ORDER_2 = "171-0000002-0000002"
ORDER_3 = "171-0000003-0000003"
CTT_1 = "EX123456789012"
CTT_2 = "EX123456789013"
SHOP = "bricolage-exemplo.example"
SHOP_NAME = "Bricolage Exemplo"
SHOP_ORDER = "5180001234"
SELLER_SHOP = "loja-exemplo.example"
AMAZON_LOGISTICS = "TBA123456789012"
GLS = ("61234567890123", "61234567890124", "61234567890125")
LM = "leroymerlin.pt"
LM_NAME = "Leroy Merlin"
LM_ORDER = "51800012"
ENVIO = "1234567890"
LM_SELLER = "Loja Exemplo (Exemplo Lda)"
CEX = "3230000000000001"
MUG = "Caneca Exemplo de cerâmica, 350 ml, pack de 2"
LAMP = "Candeeiro Exemplo de secretária, LED, 5 W"
POT = "Vaso Exemplo para plantas, 20 cm"
SHARED = "Pilhas Exemplo AA, pack de 8"
RECOMMENDED = (
    "Chávenas Exemplo para expresso...",
    "Toalhas de mesa Exemplo, 2 un...",
    "Sacos do lixo Exemplo, 30 l...",
)


@pytest.fixture(autouse=True)
def lisbon() -> Generator[None]:
    """Use the Lisbon time zone for local dates."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Lisbon"))
    yield
    dt_util.set_default_time_zone(previous)


def _nov(day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


_DAYS_40 = timedelta(days=40)

# The first sync of a mailbox reads every e-mail at once.
SYNC = _nov(9, 13)


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
        eta=_eta(25),
        label=SHOP,
    )


def _shop_gls(
    origin_id: str, number: str, when: datetime, eta: Eta | None = None
) -> Contribution:
    """A carrier notice the shop sends from its domain under the carrier's name."""
    return contribution(
        origin_id,
        kind=MailKind.IN_TRANSIT,
        time=when,
        merchant="GLS PT Informa",
        number=number,
        eta=eta or _eta(23),
        label=SHOP,
    )


def _gls(origin_id: str, number: str, when: datetime, **kwargs: Any) -> Contribution:
    """GLS's own e-mail about a parcel."""
    return contribution(
        origin_id,
        kind=MailKind.IN_TRANSIT,
        time=when,
        carrier="gls",
        number=number,
        eta=_eta(23),
        label="gls-group.eu",
        **kwargs,
    )


def _lm(
    origin_id: str, when: datetime, kind: MailKind = MailKind.SHIPPED, **kwargs: Any
) -> Contribution:
    """Leroy Merlin's own e-mail about an order: no tracking number."""
    return contribution(
        origin_id,
        kind=kind,
        time=when,
        merchant=LM_NAME,
        orders=[LM_ORDER],
        label=LM,
        **kwargs,
    )


def _lm_gls(
    origin_id: str, number: str, when: datetime, eta: Eta | None = None
) -> Contribution:
    """A GLS notice Leroy Merlin sends from its own domain, which it names."""
    return contribution(
        origin_id,
        time=when,
        carrier="gls",
        number=number,
        merchant=LM_NAME,
        eta=eta or _eta(23),
        label=LM,
    )


def _lm_survey(
    origin_id: str, envio: str, when: datetime, *, confirmed: bool = False
) -> Contribution:
    """Leroy Merlin's survey about a delivered shipment: no day, no order."""
    return contribution(
        origin_id,
        kind=MailKind.DELIVERED,
        time=when,
        merchant=LM_NAME,
        reference=envio,
        seller=LM_SELLER,
        label=LM,
        attach_only=not confirmed,
        undated=True,
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
        data, _ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _nov(9, 9, 15)), SYNC
    )
    assert (
        _apply(data, _ctt("msg:c2#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)), SYNC)
        == ctt
    )
    amazon = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(9, 2, 5), _eta(9)), SYNC)
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
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)), SYNC)
    _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(9, 12), _eta(9)), SYNC)

    result = reconcile(data, SYNC)

    assert not result.removed
    assert result.suggestions == []
    assert infer_deliveries(data, _nov(10, 8)) == set()


@pytest.mark.parametrize(
    "status", [ParcelStatus.DELIVERED, ParcelStatus.OUT_FOR_DELIVERY]
)
@pytest.mark.parametrize(
    ("seen", "paired"), [(_nov(9, 20), True), (_nov(12, 9), False)]
)
def test_news_of_an_unknown_day_pairs_nothing(
    status: ParcelStatus, seen: datetime, paired: bool
) -> None:
    """News without a date pairs by day, or infers a delivery, only on its day.

    It's placed on the day the parcel was expected. Seen that day, that's
    its day; seen days later, it may have happened on any day in between.
    """
    data = ParcelsData()
    ctt = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.IN_TRANSIT, _nov(8, 15)), SYNC)
    parcel = data.parcels[ctt]
    parcel.events.append(
        ParcelEvent(
            time=_nov(9) + timedelta(microseconds=10),
            source=Source.PARCELAPP,
            origin="pa:" + CTT_1,
            status=status,
            undated=True,
            by=seen,
        )
    )
    parcel.touch(seen)
    amazon = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(7, 2, 5), _eta(9)), seen)

    result = reconcile(data, seen)

    assert result.suggestions == []
    assert infer_deliveries(data, seen) == set()
    holder = next(p for p in data.parcels.values() if "msg:a1#0" in p.origins)
    assert ("msg:c1#0" in holder.origins) is paired
    if not paired:
        assert holder.id == amazon
        assert holder.state.status is ParcelStatus.SHIPPED


def test_same_day_groups_are_suggested() -> None:
    """Two orders and two deliveries on one day: the user picks the pairs."""
    data = ParcelsData()
    first = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 11)), SYNC)
    second = _apply(
        data, _ctt("msg:c2#0", CTT_2, MailKind.DELIVERED, _nov(9, 12)), SYNC
    )
    one = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(8, 1), _eta(9)), SYNC)
    two = _apply(data, _amazon("msg:a2#0", ORDER_2, _nov(8, 2), _eta(9)), SYNC)
    assert len(data.parcels) == 4

    result = reconcile(data, SYNC)

    assert not result.removed
    targets = sorted((first, second))
    assert [suggestion.parcel_id for suggestion in result.suggestions] == targets
    for suggestion in result.suggestions:
        assert suggestion.candidates == (one, two)
        assert suggestion.day == date(2026, 11, 9)
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
    first = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 11)), SYNC)
    second = _apply(
        data, _ctt("msg:c2#0", CTT_2, MailKind.DELIVERED, _nov(9, 12)), SYNC
    )
    order = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(8, 1), _eta(9)), SYNC)

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
    order = _apply(data, _shop_order("msg:o1#0", _nov(20, 20, 30)))
    shipments = [
        _apply(data, _shop_gls(f"msg:g{index}#0", number, _nov(21, 17, 40 + index)))
        for index, number in enumerate(GLS)
    ]
    assert len({order, *shipments}) == 4
    for parcel_id, number in zip(shipments, GLS, strict=True):
        state = data.parcels[parcel_id].state
        assert state.carrier == "gls"
        assert state.tracking_url == tracking_url("gls", number)
        assert state.merchant == SHOP_NAME

    result = reconcile(data, _nov(21, 19))

    assert result.removed == {order}
    assert result.suggestions == []
    parcel = data.parcels[shipments[0]]
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_DOMAIN
    assert parcel.auto_merged.origin == "msg:o1#0"
    assert parcel.state.order_numbers == (SHOP_ORDER,)
    assert parcel.state.carrier == "gls"
    assert parcel.state.merchant == SHOP_NAME
    assert parcel.state.eta == _eta(23)
    assert len(data.parcels) == 3


def test_shop_named_once_its_name_is_known() -> None:
    """A carrier brand never names the shop; its domain does until the name."""
    data = ParcelsData()
    shipment = _apply(data, _shop_gls("msg:g1#0", GLS[0], _nov(21, 17, 40)), SYNC)
    state = data.parcels[shipment].state
    assert state.carrier == "gls"
    assert state.merchant == SHOP
    order = _apply(data, _shop_order("msg:o1#0", _nov(20, 20, 30)), SYNC)
    assert order != shipment

    result = reconcile(data, _nov(21, 19))

    assert result.removed == {order}
    assert result.changed == {shipment}
    assert data.parcels[shipment].state.merchant == SHOP_NAME
    assert data.parcels[shipment].state.order_numbers == (SHOP_ORDER,)


def test_shop_with_two_open_orders_gets_a_suggestion() -> None:
    """With two orders that could be the shipment, the user decides."""
    data = ParcelsData()
    first = _apply(data, _shop_order("msg:o1#0", _nov(20, 20, 30)))
    second = _apply(data, _shop_order("msg:o2#0", _nov(20, 22), order="5180005678"))
    shipment = _apply(data, _shop_gls("msg:g1#0", GLS[0], _nov(21, 17, 40)))

    result = reconcile(data, _nov(21, 19))

    assert not result.removed
    assert [
        (s.parcel_id, s.candidates, s.day, s.reason) for s in result.suggestions
    ] == [(shipment, (first, second), None, REASON_SAME_MERCHANT_DOMAIN)]


def test_shop_packages_are_one_shipment() -> None:
    """A shop's packages sent together are one shipment; each stays a parcel.

    Eight GLS packages of one order, in e-mails the shop sends under GLS's
    name, one of them about two packages. Half come a day later.
    """
    data = ParcelsData()
    order = _apply(data, _shop_order("msg:o1#0", _nov(20, 20, 30)))
    packages = {
        _apply(data, _shop_gls(origin_id, number, when, _eta(day))): day
        for origin_id, number, when, day in (
            ("msg:g1#0", "61000012310052", _nov(21, 17, 40), 23),
            ("msg:g1#1", "61000012310056", _nov(21, 17, 40), 23),
            ("msg:g2#0", "61000012310071", _nov(21, 17, 41), 23),
            ("msg:g3#0", "61000012310089", _nov(21, 17, 42), 23),
            ("msg:g4#0", "61000012310093", _nov(22, 2, 35), 22),
            ("msg:g5#0", "61000012310108", _nov(22, 2, 43), 22),
            ("msg:g6#0", "61000012310117", _nov(22, 2, 52), 22),
            ("msg:g7#0", "61000012310125", _nov(22, 3, 5), 22),
        )
    }
    assert len(packages) == 8

    result = reconcile(data, _nov(22, 5))

    assert result.removed == {order}
    assert set(data.parcels) == set(packages)
    for parcel_id, day in packages.items():
        state = data.parcels[parcel_id].state
        assert (state.carrier, state.merchant, state.eta) == (
            "gls",
            SHOP_NAME,
            _eta(day),
        )
    (absorbed,) = (
        parcel for parcel in data.parcels.values() if parcel.state.order_numbers
    )
    assert absorbed.state.order_numbers == (SHOP_ORDER,)
    assert absorbed.auto_merged is not None
    assert absorbed.auto_merged.reason == REASON_SAME_MERCHANT_DOMAIN
    assert shipment_groups(data.parcels.values()) == dict.fromkeys(
        packages, min(packages)
    )


@pytest.mark.parametrize(
    ("first", "second", "together"),
    [
        pytest.param(
            _shop_gls("msg:g1#0", "61000012310052", _nov(21, 17, 40)),
            _shop_gls("msg:g2#0", "61000012310552", _nov(23, 17, 40)),
            True,
            id="same-shop",
        ),
        pytest.param(
            _shop_gls("msg:g1#0", "61000012310052", _nov(21, 17, 40)),
            _shop_gls("msg:g2#0", "61000012310562", _nov(21, 17, 40)),
            False,
            id="numbers-far-apart",
        ),
        pytest.param(
            _shop_gls("msg:g1#0", "61000012310052", _nov(21, 17, 40)),
            _shop_gls("msg:g2#0", "61000012310061", _nov(23, 17, 41)),
            False,
            id="days-apart",
        ),
        pytest.param(
            _shop_gls("msg:g1#0", "61000012310052", _nov(21, 17, 40)),
            contribution(
                "msg:d1#0",
                kind=MailKind.IN_TRANSIT,
                time=_nov(21, 17, 40),
                carrier="dpd",
                number="61000012310061",
                label=SHOP,
            ),
            False,
            id="another-carrier",
        ),
        pytest.param(
            _shop_gls("msg:g1#0", "61000012310052", _nov(21, 17, 40)),
            contribution(
                "msg:x1#0",
                kind=MailKind.IN_TRANSIT,
                time=_nov(21, 17, 40),
                merchant="GLS PT Informa",
                number="61000012310061",
                label="outra-loja.example",
            ),
            False,
            id="another-shop",
        ),
        pytest.param(
            _gls("msg:g1#0", "61000012310052", _nov(21, 17, 40), orders=[SHOP_ORDER]),
            _gls("msg:g2#0", "61000012310061", _nov(21, 17, 40), orders=[SHOP_ORDER]),
            True,
            id="same-order",
        ),
        pytest.param(
            _gls("msg:g1#0", "61000012310052", _nov(21, 17, 40), merchant="Amazon"),
            _gls("msg:g2#0", "61000012310061", _nov(21, 17, 40), merchant="Amazon.es"),
            True,
            id="same-merchant",
        ),
        pytest.param(
            _gls("msg:g1#0", "61000012310052", _nov(21, 17, 40)),
            _gls("msg:g2#0", "61000012310061", _nov(21, 17, 40)),
            False,
            id="nothing-shared",
        ),
    ],
)
def test_one_shipment(
    first: Contribution, second: Contribution, together: bool
) -> None:
    """One carrier, close numbers and e-mails, and a shared order, shop or name."""
    data = ParcelsData()
    parcels = {_apply(data, first), _apply(data, second)}
    assert len(parcels) == 2

    groups = shipment_groups(data.parcels.values())

    assert groups == (dict.fromkeys(parcels, min(parcels)) if together else {})


@pytest.mark.parametrize("notice", [_shop_gls, _lm_gls], ids=["shop", "leroy-merlin"])
def test_renamed_package_stays_in_its_shipment(
    notice: Callable[[str, str, datetime], Contribution],
) -> None:
    """The shop that sent the packages decides, whatever the user names them."""
    data = ParcelsData()
    parcels = {
        _apply(data, notice("msg:g1#0", "61000012310052", _nov(21, 17, 40))),
        _apply(data, notice("msg:g2#0", "61000012310061", _nov(21, 17, 41))),
    }
    update_parcel(data, max(parcels), {"merchant": "Presente de anos"}, _nov(21, 19))

    groups = shipment_groups(data.parcels.values())

    assert groups == dict.fromkeys(parcels, min(parcels))


def test_leroy_merlin_notices_absorb_the_order() -> None:
    """Leroy Merlin forwards GLS's notices; they absorb its order's parcel."""
    data = ParcelsData()
    order = _apply(data, _lm("msg:o1#0", _nov(20, 20, 30)))
    shipments = [
        _apply(data, _lm_gls(f"msg:g{index}#0", number, _nov(21, 17, 40 + index)))
        for index, number in enumerate(GLS)
    ]
    assert len({order, *shipments}) == 4

    result = reconcile(data, _nov(21, 19))

    assert result.removed == {order}
    assert result.suggestions == []
    parcel = data.parcels[shipments[0]]
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_DOMAIN
    assert parcel.state.order_numbers == (LM_ORDER,)
    assert (parcel.state.carrier, parcel.state.merchant) == ("gls", LM_NAME)
    assert shipment_groups(data.parcels.values()) == dict.fromkeys(
        shipments, min(shipments)
    )


def test_survey_confirms_the_delivery_of_its_shipment() -> None:
    """A survey days later closes its shipment, on the day it was out.

    The e-mail doesn't say when the delivery was. The order's other
    shipment stays apart, and the "delivered" e-mail, read later, dates it.
    """
    data = ParcelsData()
    first = _apply(
        data,
        _lm(
            "msg:l1#0",
            _nov(17, 8, 30),
            MailKind.OUT_FOR_DELIVERY,
            carrier="gls",
            eta=_eta(17),
            reference=ENVIO,
            seller=LM_SELLER,
        ),
    )
    second = _apply(
        data,
        _lm(
            "msg:l2#0",
            _nov(17, 8, 40),
            MailKind.OUT_FOR_DELIVERY,
            carrier="gls",
            eta=_eta(17),
            reference="1234567891",
        ),
    )
    assert first != second

    assert _apply(data, _lm_survey("msg:s1#0", ENVIO, _nov(19, 10))) == first

    state = data.parcels[first].state
    assert state.status is ParcelStatus.DELIVERED
    assert state.delivered_undated
    assert state.delivered_at is not None
    assert _nov(17, 8, 30) < state.delivered_at < _nov(18)
    assert state.seller == LM_SELLER
    assert data.parcels[second].state.status is ParcelStatus.OUT_FOR_DELIVERY
    assert not reconcile(data, _nov(19, 11)).removed

    delivered = _lm("msg:l3#0", _nov(17, 15), MailKind.DELIVERED, reference=ENVIO)
    assert _apply(data, delivered, _nov(19, 12)) == first
    state = data.parcels[first].state
    assert (state.delivered_at, state.delivered_undated) == (_nov(17, 15), False)


def test_survey_without_its_shipment() -> None:
    """A survey alone makes no parcel; confirmed, it makes one of no known day."""
    data = ParcelsData()
    survey = _lm_survey("msg:s1#0", ENVIO, _nov(19, 10))

    assert apply_contribution(data, survey, _nov(19, 10)).parcel_id is None
    assert not data.parcels

    parcel_id = _apply(
        data, _lm_survey("msg:s1#0", ENVIO, _nov(19, 10), confirmed=True)
    )
    state = data.parcels[parcel_id].state
    assert state.status is ParcelStatus.DELIVERED
    assert (state.delivered_at, state.delivered_undated) == (None, True)


def test_marketplace_seller_pairs_with_its_carrier() -> None:
    """The carrier names Leroy Merlin's marketplace seller, not Leroy Merlin."""
    data = ParcelsData()
    shop = _apply(
        data,
        _lm(
            "msg:l1#0",
            _nov(21, 9),
            eta=_eta(23),
            reference=ENVIO,
            seller=LM_SELLER,
        ),
    )
    carrier = _apply(
        data,
        contribution(
            "msg:g1#0",
            kind=MailKind.DELIVERED,
            time=_nov(23, 15),
            carrier="gls",
            number=GLS[0],
            merchant="Loja Exemplo",
            label="gls-group.eu",
        ),
    )

    result = reconcile(data, _nov(23, 16))

    assert result.removed == {shop}
    parcel = data.parcels[carrier]
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_DAY
    state = parcel.state
    assert (state.merchant, state.seller) == (LM_NAME, LM_SELLER)
    assert state.order_numbers == (LM_ORDER,)


def test_inferred_delivery() -> None:
    """Orders packed into one carrier parcel close with its delivery."""
    data = ParcelsData()
    orders = [
        _apply(data, _amazon(f"msg:a{day}#0", order, _nov(day, 8), _eta(9)))
        for day, order in enumerate((ORDER_1, ORDER_2, ORDER_3), start=6)
    ]
    ctt = _apply(
        data, _ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _nov(9, 9, 15))
    )
    _apply(data, _ctt("msg:c2#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)))
    assert len(data.parcels) == 4

    # Not before the day after the expected day.
    assert infer_deliveries(data, _nov(9, 23)) == set()
    assert infer_deliveries(data, _nov(10, 8)) == set(orders)
    for parcel_id in orders:
        parcel = data.parcels[parcel_id]
        assert parcel.state.status is ParcelStatus.DELIVERED
        assert parcel.state.inferred
        assert parcel.state.delivered_at == _nov(9, 10, 40)
        assert [entry.inferred for entry in parcel.state.timeline] == [False, True]
    assert not data.parcels[ctt].state.inferred
    assert len(data.parcels) == 4
    assert infer_deliveries(data, _nov(10, 9)) == set()

    # News about the order replaces the guess.
    _apply(
        data,
        _amazon("msg:a9#0", ORDER_1, _nov(10, 10), None, kind=MailKind.IN_TRANSIT),
    )
    state = data.parcels[orders[0]].state
    assert state.status is ParcelStatus.IN_TRANSIT
    assert not state.inferred
    assert infer_deliveries(data, _nov(11, 8)) == set()


@pytest.mark.parametrize(
    ("eta_day", "inferred"), [(7, False), (8, True), (10, True), (11, False)]
)
def test_inferred_delivery_margin(eta_day: int, inferred: bool) -> None:
    """A delivery within a day of the expected days counts."""
    data = ParcelsData()
    order = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(6, 8), _eta(eta_day)))
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)))
    assert infer_deliveries(data, _nov(15, 8)) == ({order} if inferred else set())


def test_tracked_parcels_arent_inferred() -> None:
    """A parcel with a carrier number waits for its carrier."""
    data = ParcelsData()
    _apply(
        data,
        _amazon(
            "msg:a1#0",
            ORDER_1,
            _nov(6, 8),
            _eta(9),
            carrier="amazon",
            number="TBA123456789012",
        ),
    )
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)))
    assert len(data.parcels) == 2
    assert infer_deliveries(data, _nov(15, 8)) == set()


def test_undo_and_confirm_inferred_delivery() -> None:
    """The user can take an inferred delivery back, or keep it."""
    data = ParcelsData()
    undone = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(6, 8), _eta(8)))
    kept = _apply(data, _amazon("msg:a2#0", ORDER_2, _nov(6, 9), _eta(8)))
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)))
    assert infer_deliveries(data, _nov(10, 8)) == {undone, kept}

    parcel = undo_inferred_delivery(data, undone, _nov(10, 9))
    assert parcel.delivery_rejected
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert not parcel.state.inferred
    assert infer_deliveries(data, _nov(11, 8)) == set()
    assert (
        _error(undo_inferred_delivery, data, undone, _nov(11, 9))
        == "no_inferred_delivery"
    )

    parcel = update_parcel(data, kept, {"confirm_delivery": True}, _nov(10, 9))
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert not state.inferred
    assert state.delivered_at == _nov(9, 10, 40)
    assert [event.source for event in parcel.events if event.kind] == [
        Source.PARSER,
        Source.MANUAL,
    ]
    assert _error(undo_inferred_delivery, data, kept, _nov(10, 9)) == (
        "no_inferred_delivery"
    )


def test_repair_store() -> None:
    """The one-time repair fixes what 0.1.0 stored."""
    data = ParcelsData()
    untracked = _apply(
        data, _amazon("msg:a1#0", ORDER_1, _nov(6, 8), _eta(9), carrier="amazon")
    )
    by_ai = _apply(
        data,
        _amazon(
            "msg:a2#0",
            ORDER_2,
            _nov(6, 9),
            _eta(10),
            carrier="amazon",
            source=Source.AI,
        ),
    )
    logistics = _apply(
        data,
        _amazon(
            "msg:a3#0",
            ORDER_3,
            _nov(6, 10),
            _eta(11),
            carrier="amazon",
            number="TBA123456789012",
        ),
    )
    edited = _apply(
        data,
        _amazon(
            "msg:a4#0", "171-0000004-0000004", _nov(6, 11), _eta(12), carrier="amazon"
        ),
    )
    update_parcel(data, edited, {"carrier": "amazon"}, _nov(6, 12))
    order = _apply(data, _shop_order("msg:o1#0", _nov(20, 20, 30)))
    shipment = _apply(data, _shop_gls("msg:g1#0", GLS[0], _nov(21, 17, 40)))
    # What 0.1.0 stored for the shop's carrier notice.
    parcel = data.parcels[shipment]
    stored = parcel.origins["msg:g1#0"]
    stored.carrier = None
    stored.merchant = "GLS PT Informa"
    stored.tracking_url = tracking_url(None, GLS[0])
    parcel.touch(_nov(21, 17, 40))
    assert parcel.state.carrier is None
    data.orders.clear()

    changed = repair_store(data, _nov(22, 8))

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
    assert repair_store(data, _nov(22, 9)) == set()


def test_repair_forgets_a_carrier_learned_for_amazon() -> None:
    """Amazon's e-mails no longer suggest the carrier of an accepted one."""
    data = ParcelsData()
    data.sender("amazon.es").carrier = "amazon"
    data.sender(SHOP).carrier = "gls"

    repair_store(data, _nov(22, 8))

    assert data.senders["amazon.es"].carrier is None
    assert data.senders[SHOP].carrier == "gls"


def test_repair_forgets_an_unproven_amazon_carrier() -> None:
    """Amazon is a parcel's carrier only when one of its numbers proves it.

    The local AI and the Parcel app gave Amazon as the carrier of Amazon's
    orders that other carriers delivered, after 0.1.3's repair. What a
    parser read in Amazon's e-mail ("Amazon Logistics") and the user's own
    edits stay.
    """
    data = ParcelsData()
    by_ai = _apply(
        data,
        _amazon(
            "msg:a1#0",
            ORDER_1,
            _nov(16, 8),
            _eta(19),
            carrier="amazon",
            source=Source.AI,
        ),
    )
    parcel_app = _apply(
        data,
        contribution(
            f"pa:{ORDER_2}",
            time=_nov(16, 9),
            carrier="amazon",
            merchant="Amazon",
            orders=[ORDER_2],
            eta=_eta(20),
            source=Source.PARCELAPP,
            label="Parcel app",
        ),
    )
    proven = _apply(
        data,
        _amazon(
            "msg:a3#0",
            ORDER_3,
            _nov(16, 10),
            _eta(21),
            carrier="amazon",
            number=AMAZON_LOGISTICS,
            source=Source.AI,
        ),
    )
    named = _apply(
        data,
        _amazon(
            "msg:a4#0", "171-0000004-0000004", _nov(16, 11), _eta(22), carrier="amazon"
        ),
    )
    edited = _apply(
        data, _amazon("msg:a5#0", "171-0000005-0000005", _nov(16, 12), _eta(23))
    )
    update_parcel(data, edited, {"carrier": "amazon"}, _nov(16, 13))

    changed = repair_store(data, _nov(22, 8), since=3)

    assert changed == {by_ai, parcel_app}
    carriers = {
        parcel_id: data.parcels[parcel_id].state.carrier
        for parcel_id in (by_ai, parcel_app, proven, named, edited)
    }
    assert carriers == {
        by_ai: None,
        parcel_app: None,
        proven: "amazon",
        named: "amazon",
        edited: "amazon",
    }
    counts = {"origins": 2, "senders": 0, "answers": 0}
    assert data.engine[AMAZON_REPAIR_KEY] == counts
    assert repair_store(data, _nov(22, 9), since=REPAIR_VERSION) == set()
    assert data.engine[AMAZON_REPAIR_KEY] == counts


def _answer(
    item_id: str,
    suggestion: Suggestion,
    *,
    fill: bool = False,
    source: Source = Source.AI,
    reason: str = REASON_AI_SUGGESTION,
) -> ReviewItem:
    """An e-mail waiting under "Needs review"."""
    return ReviewItem(
        id=item_id,
        created=_nov(20, 8),
        message=f"m-{item_id}",
        received=_nov(20, 8),
        sender=f"Loja Exemplo <envios@{SELLER_SHOP}>",
        sender_domain=SELLER_SHOP,
        subject="A sua encomenda foi enviada",
        mailbox="entry",
        owner="person.one",
        reason=REASON_AI_FILL if fill else reason,
        authenticated=True,
        source=source,
        suggestion=suggestion,
        fill=fill,
    )


def test_repair_forgets_an_unproven_amazon_carrier_under_review() -> None:
    """Answers under review and learned carriers lose an unproven Amazon.

    The rest of an answer stands, as for a new answer. A fill that offered
    only the carrier is dropped.
    """
    data = ParcelsData()
    data.sender(SELLER_SHOP).carrier = "amazon"
    data.sender(SHOP).carrier = "gls"
    amazon = Suggestion(
        kind=MailKind.SHIPPED,
        merchant="Amazon",
        carrier="amazon",
        order_numbers=(ORDER_1,),
    )
    proven = replace(amazon, tracking_numbers=(AMAZON_LOGISTICS,))
    dated = Suggestion(
        kind=MailKind.SHIPPED,
        carrier="amazon",
        eta_start=date(2026, 11, 21),
        eta_end=date(2026, 11, 21),
    )
    data.review = {
        "r1": _answer("r1", amazon),
        "r2": _answer("r2", proven),
        "r3": _answer(
            "r3", Suggestion(kind=MailKind.SHIPPED, carrier="amazon"), fill=True
        ),
        "r4": _answer("r4", dated, fill=True),
        "r5": _answer("r5", amazon, source=Source.PARSER, reason="low_confidence"),
    }

    repair_store(data, _nov(22, 8), since=3)

    assert data.senders[SELLER_SHOP].carrier is None
    assert data.senders[SHOP].carrier == "gls"
    assert set(data.review) == {"r1", "r2", "r4", "r5"}
    answer = data.review["r1"]
    assert answer.suggestion == replace(amazon, carrier=None)
    assert (answer.reason, answer.errors) == (REASON_AI_SUGGESTION, ())
    assert data.review["r2"].suggestion == proven
    assert data.review["r2"].errors == ()
    assert data.review["r4"].suggestion == replace(dated, carrier=None)
    assert data.review["r4"].errors == ()
    assert data.review["r5"].suggestion == amazon
    assert data.engine[AMAZON_REPAIR_KEY] == {
        "origins": 0,
        "senders": 1,
        "answers": 3,
    }


def test_order_pairs_with_its_delivery_once_amazon_is_not_its_carrier() -> None:
    """An order that lost its unproven carrier pairs with the day's delivery."""
    data = _separate(
        _amazon(
            "msg:a1#0",
            ORDER_1,
            _nov(16, 9),
            _eta(18),
            items=[MUG],
            carrier="amazon",
            source=Source.AI,
        ),
        _ctt("msg:t1#0", CTT_1, MailKind.DELIVERED, _nov(18, 11, 12)),
    )

    repair_store(data, _nov(18, 14), since=3)

    (parcel,) = data.parcels.values()
    assert parcel.state.carrier == "ctt_expresso"
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert parcel.state.items == (MUG,)
    assert parcel.auto_merged is not None


@pytest.mark.parametrize(("delivered_day", "merged"), [(15, True), (12, False)])
def test_delivery_read_first_joins_its_order(delivered_day: int, merged: bool) -> None:
    """An order's "delivered" e-mail read before its "shipped" e-mail is one parcel.

    A delivery before the order shipped is another package.
    """
    data = ParcelsData()
    delivered = _apply(
        data,
        _amazon(
            "msg:d1#0", ORDER_1, _nov(delivered_day, 15), None, kind=MailKind.DELIVERED
        ),
        _nov(15, 16),
    )
    shipped = _apply(
        data,
        _amazon(
            "msg:s1#0",
            ORDER_1,
            _nov(13, 9),
            _eta(15),
            shipment_id="DkSHIP0001",
            items=[POT],
        ),
        _nov(15, 16),
    )
    assert shipped != delivered

    result = reconcile(data, _nov(15, 16))

    if not merged:
        assert not result.removed
        assert len(data.parcels) == 2
        return
    assert result.removed == {delivered}
    parcel = data.parcels[shipped]
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert parcel.state.items == (POT,)
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_ORDER
    split = undo_auto_merge(data, shipped, _nov(15, 17))
    assert split is not None
    assert set(split.origins) == {"msg:d1#0"}
    assert not reconcile(data, _nov(15, 18)).removed


@pytest.mark.parametrize("other_shipment", [False, True])
def test_return_read_first_joins_its_shipment(other_shipment: bool) -> None:
    """A "returned" e-mail with the order's item updates the shipped parcel.

    Not when it names another shipment of the order.
    """
    data = ParcelsData()
    returned = _apply(
        data,
        _amazon(
            "msg:r1#0",
            ORDER_2,
            _nov(15, 14),
            None,
            kind=MailKind.RETURN,
            items=[LAMP],
            shipment_id="DkSHIP0002" if other_shipment else None,
        ),
        _nov(15, 16),
    )
    shipped = _apply(
        data,
        _amazon(
            "msg:s1#0",
            ORDER_2,
            _nov(14, 8),
            _eta(15),
            shipment_id="DkSHIP0001",
            items=[LAMP],
        ),
        _nov(15, 16),
    )
    assert shipped != returned

    result = reconcile(data, _nov(15, 16))

    if other_shipment:
        assert not result.removed
        return
    assert result.removed == {returned}
    state = data.parcels[shipped].state
    assert state.status is ParcelStatus.RETURNED
    assert state.amazon_shipment_ids == ("DkSHIP0001",)


def test_order_mail_finds_its_package_by_items() -> None:
    """An order's e-mails about one package don't join its other package."""
    data = ParcelsData()
    lamp = _apply(
        data, _amazon("msg:c1#0", ORDER_3, _nov(20, 9), _eta(23), items=[LAMP])
    )
    # Read before the mug's "shipped" e-mail, which is older.
    mug = _apply(
        data,
        _amazon("msg:s2#0", ORDER_3, _nov(22, 10, 25), _eta(22), items=[MUG]),
        _nov(22, 12),
    )
    assert mug != lamp

    applied = apply_contribution(
        data,
        _amazon(
            "msg:s1#0",
            ORDER_3,
            _nov(22, 0, 40),
            _eta(26),
            shipment_id="DkSHIP0003",
            items=[MUG],
        ),
        _nov(22, 12),
    )

    assert applied.parcel_id == mug
    assert applied.auto_merged == REASON_SAME_ORDER
    state = data.parcels[mug].state
    assert state.eta == _eta(22)
    assert state.items == (MUG,)
    assert data.parcels[lamp].state.items == (LAMP,)


def test_order_merges_stack_on_a_carrier_pairing() -> None:
    """A package's other e-mail joins it after it paired with the carrier's.

    One undo takes every guessed e-mail back together.
    """
    data = ParcelsData()
    lamp = _apply(
        data, _amazon("msg:c1#0", ORDER_3, _nov(20, 9), _eta(30), items=[LAMP])
    )
    # The first sync reads the carrier's delivery before Amazon's e-mail.
    ctt = _apply(
        data,
        _ctt("msg:t1#0", CTT_1, MailKind.DELIVERED, _nov(22, 13, 20)),
        _nov(22, 14),
    )
    _apply(
        data,
        _amazon("msg:s2#0", ORDER_3, _nov(22, 10, 25), _eta(22), items=[MUG]),
        _nov(22, 14),
    )
    assert len(data.parcels) == 3
    reconcile(data, _nov(22, 14))
    assert set(data.parcels) == {lamp, ctt}
    shipped = _apply(
        data,
        _amazon(
            "msg:s1#0",
            ORDER_3,
            _nov(22, 0, 40),
            _eta(26),
            shipment_id="DkSHIP0003",
            items=[MUG],
        ),
        _nov(22, 14),
    )
    assert shipped not in (lamp, ctt)

    result = reconcile(data, _nov(22, 15))

    assert result.removed == {shipped}
    parcel = data.parcels[ctt]
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert parcel.state.items == (MUG,)
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_DAY
    assert parcel.auto_merged.all_origins == {"msg:s1#0", "msg:s2#0"}
    split = undo_auto_merge(data, ctt, _nov(22, 16))
    assert split is not None
    assert set(split.origins) == {"msg:s1#0", "msg:s2#0"}
    assert set(data.parcels[ctt].origins) == {"msg:t1#0"}
    assert not reconcile(data, _nov(22, 17)).removed


def _separate(*contributions: Contribution) -> ParcelsData:
    """Return data with a parcel per e-mail, as earlier versions could store."""
    data = ParcelsData()
    for contrib in contributions:
        alone = ParcelsData()
        _apply(alone, contrib, _nov(22, 14))
        data.parcels.update(alone.parcels)
        data.orders.update(alone.orders)
    return data


def test_repaired_order_pairs_with_the_carrier() -> None:
    """A package that the repair put back together pairs with the carrier's.

    The guesses stay one: a single undo takes them back together.
    """
    data = _separate(
        _amazon("msg:c1#0", ORDER_3, _nov(20, 9), _eta(30), items=[LAMP]),
        _amazon(
            "msg:s1#0",
            ORDER_3,
            _nov(22, 0, 40),
            _eta(26),
            shipment_id="DkSHIP0003",
            items=[MUG],
        ),
        _amazon("msg:s2#0", ORDER_3, _nov(22, 10, 25), _eta(22), items=[MUG]),
        _ctt("msg:t1#0", CTT_1, MailKind.DELIVERED, _nov(22, 13, 20)),
    )
    assert len(data.parcels) == 4
    repair_store(data, _nov(23, 2))

    result = reconcile(data, _nov(23, 2))

    assert not result.suggestions
    assert len(data.parcels) == 2
    ctt = next(p for p in data.parcels.values() if p.state.tracking_number == CTT_1)
    assert ctt.state.items == (MUG,)
    assert ctt.auto_merged is not None
    assert ctt.auto_merged.reason == REASON_SAME_MERCHANT_DAY
    assert ctt.auto_merged.all_origins == {"msg:s1#0", "msg:s2#0"}


def test_guesses_on_one_parcel_undo_together() -> None:
    """A guess on a parcel that another guess made grows its flag."""
    data = ParcelsData()
    _apply(data, _amazon("msg:c1#0", ORDER_3, _nov(20, 9), _eta(30), items=[LAMP]))
    mug = _apply(
        data, _amazon("msg:s2#0", ORDER_3, _nov(21, 20), _eta(22), items=[MUG])
    )
    shipped = apply_contribution(
        data,
        _amazon(
            "msg:s1#0",
            ORDER_3,
            _nov(22, 0, 40),
            _eta(22),
            shipment_id="DkSHIP0003",
            items=[MUG],
        ),
        _nov(22, 2),
    )
    assert shipped.parcel_id == mug
    assert shipped.auto_merged == REASON_SAME_ORDER

    delivered = apply_contribution(
        data,
        _ctt("msg:t1#0", CTT_1, MailKind.DELIVERED, _nov(22, 13, 20)),
        _nov(22, 14),
    )

    assert delivered.parcel_id == mug
    assert delivered.auto_merged == REASON_SAME_MERCHANT_ETA
    flag = data.parcels[mug].auto_merged
    assert flag is not None
    assert flag.all_origins == {"msg:s1#0", "msg:t1#0"}
    split = undo_auto_merge(data, mug, _nov(22, 15))
    assert split is not None
    assert set(split.origins) == {"msg:s1#0", "msg:t1#0"}


@pytest.mark.parametrize(("elsewhere", "merged"), [(False, True), (True, False)])
def test_items_of_unrelated_orders_link_nothing(elsewhere: bool, merged: bool) -> None:
    """A title that unrelated orders share, e.g. a recommendation, links nothing."""
    data = ParcelsData()
    if elsewhere:
        _apply(
            data,
            _amazon("msg:x1#0", ORDER_1, _nov(10, 9), _eta(12), items=[POT, SHARED]),
        )
    returned = _apply(
        data,
        _amazon(
            "msg:r1#0",
            ORDER_2,
            _nov(15, 14),
            None,
            kind=MailKind.RETURN,
            items=[SHARED],
        ),
        _nov(15, 16),
    )
    _apply(
        data,
        _amazon(
            "msg:s1#0",
            ORDER_2,
            _nov(14, 8),
            _eta(15),
            shipment_id="DkSHIP0001",
            items=[LAMP, SHARED],
        ),
        _nov(15, 16),
    )

    result = reconcile(data, _nov(15, 16))

    assert (result.removed == {returned}) is merged


def test_attach_only_never_makes_a_parcel() -> None:
    """An e-mail with only a delivery code joins its parcel or nothing."""
    data = ParcelsData()
    tracked = _apply(data, _ctt("msg:t1#0", CTT_1, MailKind.IN_TRANSIT, _nov(21, 9)))
    ordered = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(21, 8), _eta(23)))

    def code(origin_id: str, **kwargs: Any) -> Applied:
        contrib = contribution(
            origin_id, kind=MailKind.CODE, time=_nov(22, 7), **kwargs
        )
        contrib.attach_only = True
        return apply_contribution(data, contrib, _nov(22, 7))

    ctt = {"carrier": "ctt_expresso", "label": "cttexpresso.pt"}
    amazon = {"merchant": "Amazon.es", "label": "amazon.es"}
    assert code("msg:k1#0", number=CTT_1, **ctt).parcel_id == tracked
    assert code("msg:k2#0", orders=[ORDER_1], **amazon).parcel_id == ordered
    # The same merchant and day isn't enough, and nothing new is made.
    assert code("msg:k3#0", eta=_eta(23), **amazon) == Applied(parcel_id=None)
    assert code("msg:k4#0", number=CTT_2, **ctt) == Applied(parcel_id=None)
    assert set(data.parcels) == {tracked, ordered}


def test_carrier_mail_naming_the_order_joins_its_parcel() -> None:
    """A carrier's e-mail with the shop's order number is that order's parcel.

    Even when it comes earlier than the shop said.
    """
    data = ParcelsData()
    ordered = _apply(
        data,
        _amazon(
            "msg:a1#0",
            ORDER_1,
            _nov(21, 8),
            _eta(25),
            shipment_id="DkSHIP0001",
            items=[POT],
        ),
    )

    applied = apply_contribution(
        data,
        contribution(
            "msg:e1#0",
            kind=MailKind.OUT_FOR_DELIVERY,
            time=_nov(23, 8),
            carrier="correos_express",
            number=CEX,
            merchant="AMAZON EU SARL SUCURSAL EN",
            orders=[ORDER_1],
            label="correosexpress.com",
        ),
        _nov(23, 8),
    )

    assert applied.parcel_id == ordered
    assert applied.auto_merged == REASON_SAME_ORDER
    state = data.parcels[ordered].state
    assert state.carrier == "correos_express"
    assert state.tracking_number == CEX
    assert state.merchant == "Amazon"
    assert state.items == (POT,)


def test_repair_cleans_items_and_merges_orders() -> None:
    """The repair drops recommendations read as items and merges duplicates.

    Unlike reconciling, it looks at old parcels too.
    """
    data = ParcelsData()
    first = _apply(
        data,
        _amazon("msg:a1#0", ORDER_1, _nov(6, 8), _eta(9), items=[MUG, *RECOMMENDED]),
    )
    second = _apply(
        data,
        _amazon("msg:a2#0", ORDER_2, _nov(7, 8), _eta(10), items=[POT, *RECOMMENDED]),
    )
    # Two shared titles could be bought again: they stay.
    third = _apply(
        data,
        _amazon(
            "msg:a3#0", ORDER_3, _nov(8, 8), _eta(11), items=[LAMP, *RECOMMENDED[:2]]
        ),
    )
    old_order = "171-0000004-0000004"
    delivered = _apply(
        data,
        _amazon(
            "msg:d1#0",
            old_order,
            _nov(13, 15) - _DAYS_40,
            None,
            kind=MailKind.DELIVERED,
        ),
    )
    shipped = _apply(
        data,
        _amazon(
            "msg:s1#0",
            old_order,
            _nov(11, 9) - _DAYS_40,
            None,
            shipment_id="DkSHIP0004",
            items=[SHARED],
        ),
        _nov(13, 16) - _DAYS_40,
    )
    assert not reconcile(data, _nov(22, 8)).removed

    changed = repair_store(data, _nov(22, 8))

    assert changed == {first, second, shipped}
    assert data.parcels[first].state.items == (MUG,)
    assert data.parcels[second].state.items == (POT,)
    assert data.parcels[third].state.items == (LAMP, *RECOMMENDED[:2])
    assert delivered not in data.parcels
    parcel = data.parcels[shipped]
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_ORDER
    assert repair_store(data, _nov(22, 9)) == set()


@pytest.mark.parametrize("rival_eta", [_eta(7), _eta(11)], ids=["late", "early"])
def test_delivery_another_order_could_be_is_suggested(rival_eta: Eta) -> None:
    """A delivery joins the order due that day only when no other order could be it.

    The shop's late parcel, or one due in the next days, may be the package
    delivered, so the user picks.
    """
    data = ParcelsData()
    due = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(5, 8), _eta(9), items=[MUG]))
    rival = _apply(
        data, _amazon("msg:a2#0", ORDER_2, _nov(4, 8), rival_eta, items=[LAMP])
    )
    applied = apply_contribution(
        data,
        _ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _nov(9, 9, 15)),
        _nov(9, 9, 15),
    )
    assert applied.created
    assert applied.auto_merged is None

    result = reconcile(data, _nov(9, 9, 20))

    assert not result.removed
    [suggestion] = result.suggestions
    assert suggestion.parcel_id == applied.parcel_id
    assert set(suggestion.candidates) == {due, rival}


def test_late_order_alone_is_only_suggested() -> None:
    """A late order is a possible match for a delivery, never a sure one."""
    data = ParcelsData()
    late = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(4, 8), _eta(7)))
    ctt = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)))

    result = reconcile(data, _nov(9, 11))

    assert not result.removed
    assert [(s.parcel_id, s.candidates) for s in result.suggestions] == [(ctt, (late,))]


def test_delivery_by_another_carrier_isnt_the_order() -> None:
    """When the shop names the carrier, only that carrier's delivery pairs."""
    data = ParcelsData()
    _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(5, 8), _eta(9), carrier="gls"))
    applied = apply_contribution(
        data,
        _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)),
        _nov(9, 10, 40),
    )
    assert applied.created

    result = reconcile(data, _nov(9, 11))

    assert not result.removed
    assert result.suggestions == []
    assert infer_deliveries(data, _nov(10, 8)) == set()


def test_inference_skips_a_delivery_another_order_could_be() -> None:
    """A delivery that may be a late order's package infers nothing."""
    data = ParcelsData()
    # Read first, so nothing joins it when the orders are read.
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)))
    _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(5, 8), _eta(9)), SYNC)
    _apply(data, _amazon("msg:a2#0", ORDER_2, _nov(4, 8), _eta(7)), SYNC)
    assert len(data.parcels) == 3

    assert infer_deliveries(data, _nov(10, 8)) == set()


def test_inference_skips_another_orders_delivery() -> None:
    """A delivery already linked to another order doesn't close this one."""
    data = ParcelsData()
    _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(5, 8), _eta(9)))
    other = _apply(data, _amazon("msg:a2#0", ORDER_2, _nov(5, 9), _eta(9)))
    ctt = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)))
    assert len(data.parcels) == 3
    merge_parcels(data, ctt, (other,), _nov(9, 11))

    assert infer_deliveries(data, _nov(10, 8)) == set()


def test_probably_delivered_order_may_still_be_the_package() -> None:
    """An order only guessed delivered may be what a later delivery held.

    The guess came from another delivery of the shop, so it isn't proof: the
    later delivery is suggested with both orders, never merged with one.
    """
    data = ParcelsData()
    # Read first, so nothing joins them when the orders are read.
    first = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(8, 10, 40)))
    second = _apply(data, _ctt("msg:c2#0", CTT_2, MailKind.DELIVERED, _nov(9, 10, 40)))
    late = _apply(
        data, _amazon("msg:a2#0", ORDER_2, _nov(3, 8), _eta(7), items=[LAMP]), SYNC
    )
    due = _apply(
        data, _amazon("msg:a1#0", ORDER_1, _nov(8, 12), _eta(9), items=[MUG]), SYNC
    )
    assert infer_deliveries(data, _nov(9, 8)) == {late}
    assert data.parcels[late].state.inferred

    result = reconcile(data, _nov(9, 13))

    assert not result.removed
    suggested = {s.parcel_id: set(s.candidates) for s in result.suggestions}
    assert suggested == {first: {late}, second: {due, late}}


def test_repair_pairs_old_deliveries_with_their_orders() -> None:
    """Stored deliveries older than a sync looks at join their only order."""
    data = ParcelsData()
    day = date(2026, 9, 30)
    ctt = _apply(
        data,
        _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40) - _DAYS_40),
    )
    order = _apply(
        data,
        _amazon(
            "msg:a1#0",
            ORDER_1,
            _nov(5, 8) - _DAYS_40,
            Eta(start=day, end=day),
            items=[MUG],
        ),
        SYNC - _DAYS_40,
    )
    assert infer_deliveries(data, _nov(10, 8) - _DAYS_40) == {order}
    assert not reconcile(data, _nov(22, 8)).removed

    changed = repair_store(data, _nov(22, 8))

    assert order not in data.parcels
    assert ctt in changed
    parcel = data.parcels[ctt]
    assert parcel.state.items == (MUG,)
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert not parcel.state.inferred
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_DAY
    assert repair_store(data, _nov(22, 9)) == set()


# Made up: the part of Paack's order IDs before "_", shared by the packages.
PAACK_STEM = "Rb5Lq2Vm7"


def _paack(
    origin_id: str,
    when: datetime,
    *,
    number: str | None = None,
    reference: str | None = None,
    kind: MailKind = MailKind.IN_TRANSIT,
) -> Contribution:
    """Paack's e-mail about a parcel from Amazon."""
    return contribution(
        origin_id,
        kind=kind,
        time=when,
        carrier="paack",
        number=number,
        reference=reference,
        merchant="Amazon",
        label="paack.co",
    )


def test_paack_stem_is_suggested_for_each_package() -> None:
    """A stem two packages share is suggested for both; one left takes it."""
    data = ParcelsData()
    one = _apply(data, _paack("msg:p1#0", _nov(9, 8), number=f"{PAACK_STEM}_1"))
    two = _apply(data, _paack("msg:p2#0", _nov(9, 9), number=f"{PAACK_STEM}_2"))
    stem = _apply(
        data,
        _paack(
            "msg:p3#0",
            _nov(9, 10),
            reference=PAACK_STEM,
            kind=MailKind.OUT_FOR_DELIVERY,
        ),
    )
    assert len({one, two, stem}) == 3

    result = reconcile(data, _nov(9, 12))

    assert not result.removed
    assert sorted(
        (s.parcel_id, s.candidates, s.reason) for s in result.suggestions
    ) == sorted(
        [
            (one, (stem,), REASON_SAME_REFERENCE),
            (two, (stem,), REASON_SAME_REFERENCE),
        ]
    )

    remove_message(data, "p2", _nov(9, 13))
    result = reconcile(data, _nov(9, 13))

    assert result.removed == {stem}
    assert result.suggestions == []
    parcel = data.parcels[one]
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_REFERENCE
    assert parcel.state.status is ParcelStatus.OUT_FOR_DELIVERY


DAY_20 = date(2026, 11, 20)


def _day_parcel(
    pid: str,
    status: ParcelStatus = ParcelStatus.IN_TRANSIT,
    when: datetime | None = None,
    *,
    carrier: str | None = None,
    tracked: bool | None = None,
    merchant: str | None = "Amazon",
    orders: tuple[str, ...] = (),
    eta: Eta | None = None,
    private: bool = False,
    first: datetime | None = None,
    undated: bool = False,
) -> Parcel:
    """A parcel of one e-mail, due on the 20th; a carrier brings its number."""
    moment = when or _nov(20, 7)
    origin = Origin(
        id=f"origin-{pid}",
        source=Source.PARSER,
        time=first or _nov(20, 7),
        carrier=carrier,
        tracking_number=f"TEST{pid.upper()}"
        if (carrier if tracked is None else tracked)
        else None,
        merchant=merchant,
        order_numbers=orders,
    )
    event = ParcelEvent(
        time=moment,
        source=Source.PARSER,
        origin=origin.id,
        status=status,
        eta=eta or _eta(20),
        force=True,
        undated=undated,
        by=moment if undated else None,
    )
    return Parcel(
        id=pid,
        created=origin.time,
        updated=moment,
        origins={origin.id: origin},
        events=[event],
        private=private,
    )


def _boxes(
    *parcels: Parcel, apart: tuple[Parcel, Parcel] | None = None
) -> dict[str, tuple[str, ...]]:
    data = ParcelsData()
    for parcel in parcels:
        data.parcels[parcel.id] = parcel
    if apart is not None:
        keep_apart(data, *apart)
    return boxes_of_day(data, parcels, DAY_20)


def test_boxes_of_day() -> None:
    """Which of the day's packages may hold an order without a carrier number."""
    delivered = ParcelStatus.DELIVERED
    order = _day_parcel("order")
    box = _day_parcel("box", carrier="ctt_expresso")
    # The shop's package, or one whose shop isn't known; the shop's first.
    assert _boxes(order, box) == {"order": ("box",)}
    paack = _day_parcel("paack", carrier="paack", merchant=None)
    assert _boxes(order, paack) == {"order": ("paack",)}
    assert _boxes(paack, order, box) == {"order": ("box",)}
    # As likely: both.
    gls = _day_parcel("gls", carrier="gls")
    assert _boxes(order, box, gls) == {"order": ("box", "gls")}
    # The carrier the shop named, when known, first.
    ctt_order = _day_parcel("order", carrier="ctt", tracked=False)
    assert _boxes(ctt_order, gls, box) == {"order": ("box",)}
    assert _boxes(_day_parcel("order", carrier="dpd", tracked=False), box) == {}

    # Never another shop's package, a private package for a public order, a
    # package of another day, a pickup, or one that names an order.
    assert (
        _boxes(order, _day_parcel("zalando", carrier="gls", merchant="Zalando")) == {}
    )
    assert _boxes(order, _day_parcel("box", carrier="ctt", private=True)) == {}
    assert _boxes(_day_parcel("order", private=True), box) == {"order": ("box",)}
    assert _boxes(order, _day_parcel("box", carrier="ctt", eta=_eta(21))) == {}
    ready = ParcelStatus.READY_FOR_PICKUP
    assert _boxes(order, _day_parcel("box", ready, carrier="ctt")) == {}
    assert _boxes(order, _day_parcel("box", carrier="ctt", orders=(ORDER_1,))) == {}
    assert _boxes(order, box, apart=(order, box)) == {}
    # An order with a problem, one without a shop, or one due later stands alone.
    attempted = ParcelStatus.ATTEMPTED
    assert _boxes(_day_parcel("order", attempted), box) == {}
    assert _boxes(_day_parcel("order", merchant=None), box) == {}
    assert _boxes(_day_parcel("order", eta=_eta(22)), box) == {}
    assert _boxes(_day_parcel("order", eta=_eta(18)), box) == {"order": ("box",)}

    # Delivered: the package must be too, within three hours when both
    # times are known.
    came = _day_parcel("box", delivered, _nov(20, 10), carrier="ctt")
    assert _boxes(_day_parcel("order", delivered, _nov(20, 12, 30)), came) == {
        "order": ("box",)
    }
    assert _boxes(_day_parcel("order", delivered, _nov(20, 13, 30)), came) == {}
    undated = _day_parcel("order", delivered, _nov(20, 18), undated=True)
    assert _boxes(undated, came) == {"order": ("box",)}
    assert _boxes(undated, box) == {}
    assert _boxes(_day_parcel("order", delivered, _nov(19, 12)), came) == {}
    # Not when its news came after the delivery, or a dated status did.
    later = _nov(20, 11)
    assert (
        _boxes(_day_parcel("order", first=later, when=later, undated=True), came) == {}
    )
    out = ParcelStatus.OUT_FOR_DELIVERY
    assert _boxes(_day_parcel("order", out, _nov(20, 12)), came) == {}
    assert _boxes(_day_parcel("order", out, _nov(20, 9)), came) == {"order": ("box",)}
