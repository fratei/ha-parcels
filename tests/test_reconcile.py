"""Tests for reconciling whole parcels, inferred deliveries and the repair.

Also how e-mails about one of an order's packages find that package.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
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
    AMAZON_CATCH_UP,
    AMAZON_LINKS_KEY,
    AMAZON_REPAIR_KEY,
    REASON_AMAZON_TRACKING,
    REASON_SAME_MERCHANT_DAY,
    REASON_SAME_MERCHANT_DOMAIN,
    REASON_SAME_MERCHANT_ETA,
    REASON_SAME_NUMBER,
    REASON_SAME_ORDER,
    REASON_SAME_REFERENCE,
    REPAIR_VERSION,
    AmazonEvidence,
    Applied,
    Contribution,
    DedupError,
    accept_suggestion,
    amazon_contradicts,
    amazon_disagree,
    amazon_evidence,
    apply_contribution,
    boxes_of_day,
    dismiss_suggestion,
    fill_shop,
    hand_delivery_events,
    infer_deliveries,
    keep_apart,
    manual_origin_id,
    mark_delivered,
    merge_parcels,
    order_parcels,
    reconcile,
    remove_message,
    repair_store,
    undo_auto_merge,
    undo_delivery,
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
    dt_to_str,
    order_key,
)
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.parsers.tracking import tracking_url
from custom_components.parcels.views import (
    SYSTEM_VIEWER,
    Viewer,
    details,
    parcel_json,
    shipment_groups,
)

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
    ("delivered", "paired"), [(_nov(14, 11), False), (_nov(15, 16), True)]
)
def test_delivery_before_the_shipping_mail_stays_apart(
    delivered: datetime, paired: bool
) -> None:
    """A delivery made before the order shipped is another package.

    The order e-mail came days earlier, but the shipping e-mail tells when
    the package left: a delivery of an earlier day isn't even a suggestion.
    The day counts, not the hour, since e-mails come late.
    """
    data = ParcelsData()
    ctt = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, delivered))
    order = _amazon(
        "msg:a0#0", ORDER_1, _nov(12, 20), _eta(13, 17), kind=MailKind.ORDER
    )
    amazon = _apply(data, order)
    shipped = _amazon("msg:a1#0", ORDER_1, _nov(15, 8), _eta(15, 17))
    assert _apply(data, shipped) == amazon

    result = reconcile(data, _nov(15, 18))

    assert result.suggestions == []
    if paired:
        assert result.removed == {amazon}
        assert data.parcels[ctt].state.order_numbers == (ORDER_1,)
    else:
        assert not result.removed
        assert set(data.parcels) == {ctt, amazon}


def _paack_delivered(
    origin_id: str, number: str, merchant: str | None = None, **kwargs: Any
) -> Contribution:
    """Paack's e-mail about a parcel it delivered: the shop, if read, no order."""
    return contribution(
        origin_id,
        kind=MailKind.DELIVERED,
        time=_nov(25, 11),
        carrier="paack",
        number=number,
        merchant=merchant,
        label="paack.co",
        **kwargs,
    )


def test_fill_shop_names_the_shop_where_the_email_named_none() -> None:
    """Only the e-mail's own readings that name no shop, or the carrier, change."""
    data = ParcelsData()
    now = _nov(26, 9)
    unnamed = _apply(data, _paack_delivered("msg:p1#0", "Hx7Kp2Wd9_1"))
    assert _apply(
        data, _paack_delivered("msg:p1#ai", "Hx7Kp2Wd9_1", source=Source.AI)
    ) == (unnamed)
    carrier = _apply(data, _paack_delivered("msg:p1#1", "Hx7Kp2Wd9_2", "PAACK"))
    named = _apply(data, _paack_delivered("msg:p1#2", "Hx7Kp2Wd9_3", "Zara"))
    other = _apply(data, _paack_delivered("msg:p2#0", "Hx7Kp2Wd9_4"))

    assert fill_shop(data, "p1", SHOP_NAME, now) == {unnamed, carrier}

    merchants = {
        origin.id: origin.merchant
        for parcel in data.parcels.values()
        for origin in parcel.origins.values()
    }
    assert merchants == {
        "msg:p1#0": SHOP_NAME,
        "msg:p1#ai": None,
        "msg:p1#1": SHOP_NAME,
        "msg:p1#2": "Zara",
        "msg:p2#0": None,
    }
    assert [data.parcels[pid].state.merchant for pid in (unnamed, carrier)] == [
        SHOP_NAME,
        SHOP_NAME,
    ]
    assert data.parcels[unnamed].updated == now
    assert data.parcels[named].updated != now
    assert data.parcels[other].state.merchant is None
    assert fill_shop(data, "p1", SHOP_NAME, now) == set()


@pytest.mark.parametrize("apart", [False, True])
def test_shop_filled_in_pairs_the_box_unless_kept_apart(apart: bool) -> None:
    """Once Paack's box names the shop, it joins the shop's order of its day.

    Unless the user split them before: they stay apart.
    """
    data = ParcelsData()
    order = _apply(data, _shop_order("msg:o1#0", _nov(23, 20, 30)))
    box = _apply(data, _paack_delivered("msg:p1#0", "Hx7Kp2Wd9_1"))
    now = _nov(26, 9)
    assert not reconcile(data, now).removed
    if apart:
        keep_apart(data, data.parcels[order], data.parcels[box])

    assert fill_shop(data, "p1", SHOP_NAME, now) == {box}
    result = reconcile(data, now)

    assert data.parcels[box].state.merchant == SHOP_NAME
    if apart:
        assert not result.removed
        assert set(data.parcels) == {order, box}
    else:
        assert result.removed == {order}
        parcel = data.parcels[box]
        assert parcel.state.order_numbers == (SHOP_ORDER,)
        assert parcel.auto_merged is not None
        assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_DAY


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


def test_packages_read_in_any_order_are_one_shipment() -> None:
    """A shop's packages read between others' are still found together."""
    data = ParcelsData()
    first = _apply(data, _shop_gls("msg:g1#0", "61000012310052", _nov(21, 17, 40)))
    far = _apply(data, _shop_gls("msg:g2#0", "61000012319052", _nov(21, 17, 41)))
    second = _apply(data, _shop_gls("msg:g3#0", "61000012310157", _nov(21, 17, 42)))
    assert len({first, far, second}) == 3

    groups = shipment_groups(data.parcels.values())

    assert groups == dict.fromkeys((first, second), min(first, second))


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
    """The user can take an inferred delivery back, or keep it.

    Undoing a kept delivery brings the inference back, until it's undone.
    """
    data = ParcelsData()
    undone = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(6, 8), _eta(8)))
    kept = _apply(data, _amazon("msg:a2#0", ORDER_2, _nov(6, 9), _eta(8)))
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)))
    assert infer_deliveries(data, _nov(10, 8)) == {undone, kept}

    parcel = undo_delivery(data, undone, _nov(10, 9))
    assert parcel.delivery_rejected
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert not parcel.state.inferred
    assert infer_deliveries(data, _nov(11, 8)) == set()
    assert _error(undo_delivery, data, undone, _nov(11, 9)) == "no_delivery_to_undo"

    parcel = update_parcel(data, kept, {"confirm_delivery": True}, _nov(10, 9))
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert not state.inferred
    assert state.delivered_at == _nov(9, 10, 40)
    assert [event.source for event in parcel.events if event.kind] == [
        Source.PARSER,
        Source.MANUAL,
    ]

    parcel = undo_delivery(data, kept, _nov(10, 10))
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert not parcel.delivery_rejected
    assert infer_deliveries(data, _nov(10, 10)) == {kept}
    assert parcel.state.inferred
    parcel = undo_delivery(data, kept, _nov(10, 11))
    assert parcel.delivery_rejected
    assert parcel.state.status is ParcelStatus.SHIPPED


def test_undo_a_mark_on_an_inferred_delivery() -> None:
    """Marking it delivered keeps it; Undo goes back to the inferred one."""
    data = ParcelsData()
    order = _apply(data, _amazon("msg:a1#0", ORDER_1, _nov(6, 8), _eta(8)))
    _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.DELIVERED, _nov(9, 10, 40)))
    assert infer_deliveries(data, _nov(10, 8)) == {order}

    parcel = mark_delivered(data, order, _nov(10, 9))
    assert not parcel.state.inferred
    assert hand_delivery_events(parcel)

    parcel = undo_delivery(data, order, _nov(10, 10))
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert parcel.state.inferred
    assert not hand_delivery_events(parcel)
    assert not parcel.delivery_rejected
    parcel = undo_delivery(data, order, _nov(10, 11))
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert parcel.delivery_rejected


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

    The rest of an answer stands, as for a new answer, with the same note for
    admins. A fill that offered only the carrier is dropped.
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
        "r4": replace(_answer("r4", dated, fill=True), notes=("eta_from_text",)),
        "r5": _answer("r5", amazon, source=Source.PARSER, reason="low_confidence"),
    }

    repair_store(data, _nov(22, 8), since=3)

    assert data.senders[SELLER_SHOP].carrier is None
    assert data.senders[SHOP].carrier == "gls"
    assert set(data.review) == {"r1", "r2", "r4", "r5"}
    answer = data.review["r1"]
    assert answer.suggestion == replace(amazon, carrier=None)
    assert (answer.reason, answer.errors) == (REASON_AI_SUGGESTION, ())
    assert answer.notes == ("carrier_unproven",)
    assert data.review["r2"].suggestion == proven
    assert (data.review["r2"].errors, data.review["r2"].notes) == ((), ())
    assert data.review["r4"].suggestion == replace(dated, carrier=None)
    assert data.review["r4"].errors == ()
    assert data.review["r4"].notes == ("eta_from_text", "carrier_unproven")
    assert data.review["r5"].suggestion == amazon
    assert data.review["r5"].notes == ()
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


# Amazon's tracking of its shipments, which the Parcel app follows, against the
# carriers' packages. All made up, in June, when Lisbon is on UTC+1.
SHIPMENT_1 = "Kd3Fw9Qa2"
SHIPMENT_2 = "Mv8Hc4Tn6"
SHIPMENT_3 = "Wp5Gx2Rk8"
SHIPMENT_4 = "Zc7Jt3Hn4"
SHIPMENT_5 = "Yb2Ms6Lq9"
SHIPMENT_6 = "Fq9Lr3Td7"
PAACK_1 = "Gt5Rm8Vb3_1"
PAACK_2 = "Jy6Ns1Qe9_1"
ARRIVED = "o pedido chegou a uma instalação da transportadora, Cidade Exemplo, ES"
VAN_OUT = "Entrega em curso, Vila Exemplo, PT"
HANDED = "Entregue, Vila Exemplo, PT"
CENTER = "(CO) C.O. Centro Exemplo"
CTT_ARRIVED = f"Chegou ao centro operacional, 4321 - {CENTER}"
AMAZON_AT_CENTER = f"o pedido chegou a uma instalação da transportadora, {CENTER}, PT"
JUNE_10 = date(2026, 6, 10)
NO_LINKS = {"made": 0, "ambiguous": 0, "contradicted": 0, "undone": 0}


def _jun(day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 6, day, hour, minute, second, tzinfo=UTC)


def _scan(
    time: datetime,
    status: ParcelStatus | None = None,
    label: str | None = None,
    *,
    eta: Eta | None = None,
    undated: bool = False,
    timeless: bool = False,
    dayless: bool = False,
) -> ParcelEvent:
    """An event of a delivery in the Parcel app."""
    return ParcelEvent(
        time=time,
        source=Source.PARCELAPP,
        status=status,
        label=label,
        eta=eta,
        undated=undated,
        timeless=timeless,
        dayless=dayless,
        by=time if undated else None,
    )


def _parcel_app(
    key: str, anchor: str, events: tuple[ParcelEvent, ...], **fields: Any
) -> Contribution:
    """A delivery in the Parcel app, joining the parcel its sync chose."""
    return Contribution(
        origin=Origin(
            id=f"pa:{key}",
            source=Source.PARCELAPP,
            time=min(event.time for event in events),
            label="Parcel app",
            **fields,
        ),
        events=list(events),
        anchor=anchor,
    )


def _shipment(
    data: ParcelsData,
    key: int,
    order: str,
    shipment: str,
    sent: datetime,
    *events: ParcelEvent,
    carrier: str | None = None,
    eta: Eta | None = None,
) -> str:
    """Amazon's e-mail about a shipment due on 10 June, and its tracking."""
    mail = f"msg:a{key}#0"
    eta = eta or Eta(start=JUNE_10, end=JUNE_10)
    parcel = _apply(
        data, _amazon(mail, order, sent, eta, shipment_id=shipment, carrier=carrier)
    )
    if events:
        tracking = _parcel_app(
            f"t{key}", mail, events, order_numbers=(order,), amazon_shipment_id=shipment
        )
        assert _apply(data, tracking) == parcel
    return parcel


def _came(
    arrived: datetime | None = None, delivered: str = "Entregue"
) -> tuple[ParcelEvent, ...]:
    """Amazon's tracking: at the carrier on 9 June, delivered on the 10th."""
    return (
        _scan(arrived or _jun(9, 15, 2), ParcelStatus.IN_TRANSIT, ARRIVED),
        _scan(_jun(10, 9, 27), ParcelStatus.DELIVERED, delivered),
    )


def _fifth(data: ParcelsData, *events: ParcelEvent) -> str:
    return _shipment(data, 5, ORDER_1, SHIPMENT_5, _jun(8, 9), *(events or _came()))


def _at_center(arrived: datetime | None = None) -> tuple[ParcelEvent, ...]:
    """Amazon's tracking of a shipment in CTT's package of 10 June."""
    return (
        _scan(arrived or _jun(10, 1, 41), ParcelStatus.IN_TRANSIT, AMAZON_AT_CENTER),
        _scan(_jun(10, 7, 12), ParcelStatus.OUT_FOR_DELIVERY, "Entrega em curso"),
        _scan(_jun(10, 9, 27), ParcelStatus.DELIVERED, "Entregue"),
    )


def _own_scans(data: ParcelsData, box: str, *events: ParcelEvent) -> None:
    """CTT's own tracking of its package in the Parcel app."""
    tracking = _parcel_app(
        "c1", "msg:c1#0", events, carrier="ctt_expresso", tracking_number=CTT_1
    )
    assert _apply(data, tracking) == box


def _ctt_box(data: ParcelsData, *, delivered: bool = True) -> str:
    """CTT's package of 10 June: its e-mail, and its own tracking."""
    box = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.SHIPPED, _jun(9, 15)))
    scans = (
        _scan(_jun(10, 1, 41), ParcelStatus.IN_TRANSIT, CTT_ARRIVED),
        _scan(_jun(10, 7, 12), ParcelStatus.OUT_FOR_DELIVERY, "Em entrega"),
        _scan(_jun(10, 9, 27), ParcelStatus.DELIVERED, "Entregue"),
    )
    _own_scans(data, box, *(scans if delivered else scans[:2]))
    return box


def _ctt_with_two(data: ParcelsData, *, delivered: bool = True) -> tuple[str, str, str]:
    """Shipments of two orders, then CTT's package that carried both."""
    end = None if delivered else 2
    third = _shipment(data, 3, ORDER_1, SHIPMENT_3, _jun(8, 9), *_at_center()[:end])
    fourth = _shipment(data, 4, ORDER_2, SHIPMENT_4, _jun(8, 10), *_at_center()[:end])
    return _ctt_box(data, delivered=delivered), third, fourth


def _mail_box(
    data: ParcelsData, number: str, *mails: tuple[str, MailKind, datetime]
) -> str:
    """CTT's e-mails about one package."""
    [box] = {
        _apply(data, _ctt(origin_id, number, kind, when))
        for origin_id, kind, when in mails
    }
    return box


def _paack_box(
    origin_id: str, number: str, kind: MailKind, when: datetime
) -> Contribution:
    """Paack's e-mail about a package, naming no shop."""
    return contribution(
        origin_id,
        kind=kind,
        time=when,
        carrier="paack",
        number=number,
        label="paack.co",
    )


def _two_paack_boxes(
    data: ParcelsData, *, delivered: bool = True
) -> tuple[str, str, str, str]:
    """Two shipments, each in its own Paack package, delivered the same minute."""
    shipments = []
    for key, order, shipment, sent, arrived in (
        (1, ORDER_1, SHIPMENT_1, _jun(8, 9), _jun(9, 12, 36)),
        (2, ORDER_2, SHIPMENT_2, _jun(8, 10), _jun(9, 17, 18)),
    ):
        news = (
            _scan(arrived, ParcelStatus.IN_TRANSIT, ARRIVED),
            _scan(_jun(10, 6, 41), ParcelStatus.OUT_FOR_DELIVERY, VAN_OUT),
            _scan(_jun(10, 10, 14), ParcelStatus.DELIVERED, HANDED),
        )
        shipments.append(
            _shipment(
                data, key, order, shipment, sent, *(news if delivered else news[:2])
            )
        )
    first, second = shipments
    one = _apply(
        data,
        _paack_box("msg:p1#0", PAACK_1, MailKind.IN_TRANSIT, _jun(9, 12, 36, 16)),
    )
    two = _apply(
        data,
        _paack_box("msg:p2#0", PAACK_2, MailKind.IN_TRANSIT, _jun(9, 17, 18, 47)),
    )
    mails = (
        ("msg:p3#0", PAACK_1, MailKind.OUT_FOR_DELIVERY, _jun(10, 6, 52), one),
        ("msg:p4#0", PAACK_2, MailKind.OUT_FOR_DELIVERY, _jun(10, 6, 59), two),
        ("msg:p5#0", PAACK_1, MailKind.DELIVERED, _jun(10, 10, 14, 22), one),
        ("msg:p6#0", PAACK_2, MailKind.DELIVERED, _jun(10, 10, 14, 48), two),
    )
    for origin_id, number, kind, when, box in mails if delivered else mails[:2]:
        assert _apply(data, _paack_box(origin_id, number, kind, when)) == box
    assert len({one, two, first, second}) == 4
    return one, two, first, second


def _linked(parcel: Parcel) -> bool:
    flag = parcel.auto_merged
    return flag is not None and flag.reason == REASON_AMAZON_TRACKING


def test_amazon_tracking_links_each_shipment_to_its_package() -> None:
    """A shipment joins the package whose times agree with Amazon's tracking.

    It was delivered that minute and reached the carrier when the shipment
    did; the van leaving with both doesn't tell them apart.
    """
    data = ParcelsData()
    one, two, first, second = _two_paack_boxes(data)

    result = reconcile(data, _jun(10, 22))

    assert result.removed == {first, second}
    assert result.suggestions == []
    for box, mail, tracking, shipment in (
        (one, "msg:a1#0", "pa:t1", SHIPMENT_1),
        (two, "msg:a2#0", "pa:t2", SHIPMENT_2),
    ):
        parcel = data.parcels[box]
        flag = parcel.auto_merged
        assert flag is not None
        assert flag.reason == REASON_AMAZON_TRACKING
        assert flag.origin == mail
        assert flag.all_origins == {mail, tracking}
        assert flag.groups == ()
        assert parcel.state.amazon_shipment_ids == (shipment,)
    links = {"made": 2, "ambiguous": 0, "contradicted": 0, "undone": 0}
    assert data.engine[AMAZON_LINKS_KEY] == links

    again = reconcile(data, _jun(10, 22, 30))

    assert not again.removed
    assert again.suggestions == []
    assert data.engine[AMAZON_LINKS_KEY] == links


def test_amazon_tracking_links_shipments_sharing_a_package() -> None:
    """Shipments of two orders in one package both join it.

    On undo, each leaves as it came, and the next sync doesn't link it again.
    """
    data = ParcelsData()
    box, third, fourth = _ctt_with_two(data)

    result = reconcile(data, _jun(10, 22))

    assert result.removed == {third, fourth}
    parcel = data.parcels[box]
    flag = parcel.auto_merged
    assert flag is not None
    assert flag.reason == REASON_AMAZON_TRACKING
    assert flag.origin == "msg:a3#0"
    assert flag.groups == (("msg:a3#0", "pa:t3"), ("msg:a4#0", "pa:t4"))
    assert set(parcel.state.amazon_shipment_ids) == {SHIPMENT_3, SHIPMENT_4}
    links = {"made": 2, "ambiguous": 0, "contradicted": 0, "undone": 0}
    assert data.engine[AMAZON_LINKS_KEY] == links

    undo_auto_merge(data, box, _jun(10, 22, 30))

    assert {frozenset(parcel.origins) for parcel in data.parcels.values()} == {
        frozenset({"msg:c1#0", "pa:c1"}),
        frozenset({"msg:a3#0", "pa:t3"}),
        frozenset({"msg:a4#0", "pa:t4"}),
    }
    again = reconcile(data, _jun(10, 22, 45))
    assert not again.removed
    assert again.suggestions == []
    assert len(data.parcels) == 3
    assert not any(_linked(parcel) for parcel in data.parcels.values())
    assert data.engine[AMAZON_LINKS_KEY] == links


def test_removed_mail_leaves_its_shipment_group() -> None:
    """A removed e-mail leaves the group of the shipment it was about."""
    data = ParcelsData()
    box, _third, _fourth = _ctt_with_two(data)
    reconcile(data, _jun(10, 22))

    remove_message(data, "a4", _jun(10, 22, 30))

    flag = data.parcels[box].auto_merged
    assert flag is not None
    assert flag.groups == (("msg:a3#0", "pa:t3"), ("pa:t4",))


def test_amazon_tracking_suggests_packages_agreeing_equally() -> None:
    """When two packages agree as well, none is chosen.

    Each is suggested and the shipment may ride along in either, until one
    is turned down.
    """
    data = ParcelsData()
    fifth = _fifth(data)
    first = _mail_box(
        data,
        CTT_1,
        ("msg:c1#0", MailKind.SHIPPED, _jun(9, 15, 2)),
        ("msg:c2#0", MailKind.DELIVERED, _jun(10, 9, 27, 30)),
    )
    second = _mail_box(
        data,
        CTT_2,
        ("msg:c3#0", MailKind.SHIPPED, _jun(9, 15, 3)),
        ("msg:c4#0", MailKind.DELIVERED, _jun(10, 9, 28)),
    )

    result = reconcile(data, _jun(10, 22))

    assert not result.removed
    assert len(result.suggestions) == 2
    assert {
        (suggestion.parcel_id, suggestion.candidates, suggestion.reason)
        for suggestion in result.suggestions
    } == {
        (first, (fifth,), REASON_AMAZON_TRACKING),
        (second, (fifth,), REASON_AMAZON_TRACKING),
    }
    assert {suggestion.day for suggestion in result.suggestions} == {JUNE_10}
    assert data.engine[AMAZON_LINKS_KEY] == {
        "made": 0,
        "ambiguous": 1,
        "contradicted": 0,
        "undone": 0,
    }
    riding = boxes_of_day(data, data.parcels.values(), JUNE_10)
    assert set(riding[fifth]) == {first, second}

    dismiss_suggestion(data, second, [fifth])
    result = reconcile(data, _jun(10, 22, 30))

    assert result.removed == {fifth}
    assert _linked(data.parcels[first])
    assert data.engine[AMAZON_LINKS_KEY] == {
        "made": 1,
        "ambiguous": 0,
        "contradicted": 0,
        "undone": 0,
    }


@pytest.mark.parametrize(
    ("arrived", "mails"),
    [
        # Its first e-mail came hours before the shipment reached the carrier.
        (
            _jun(9, 15, 2),
            (
                ("msg:c1#0", MailKind.SHIPPED, _jun(9, 12)),
                ("msg:c2#0", MailKind.DELIVERED, _jun(10, 9, 27, 30)),
            ),
        ),
        # Only the van leaving agrees: a van takes many packages.
        (
            _jun(10, 7, 12),
            (
                ("msg:c1#0", MailKind.OUT_FOR_DELIVERY, _jun(10, 7, 12, 30)),
                ("msg:c2#0", MailKind.DELIVERED, _jun(10, 9, 27, 30)),
            ),
        ),
        # Delivered three minutes later.
        (
            _jun(9, 15, 2),
            (
                ("msg:c1#0", MailKind.SHIPPED, _jun(9, 15, 2)),
                ("msg:c2#0", MailKind.DELIVERED, _jun(10, 9, 30, 30)),
            ),
        ),
    ],
)
def test_amazon_tracking_needs_two_agreeing_times(
    arrived: datetime, mails: tuple[tuple[str, MailKind, datetime], ...]
) -> None:
    """A package takes a shipment only when two of its times agree.

    It was delivered that minute, and one more of its news agrees too.
    """
    data = ParcelsData()
    _fifth(data, *_came(arrived))
    box = _mail_box(data, CTT_1, *mails)

    result = reconcile(data, _jun(10, 22))

    assert data.engine[AMAZON_LINKS_KEY] == NO_LINKS
    assert all(s.reason != REASON_AMAZON_TRACKING for s in result.suggestions)
    assert not _linked(data.parcels[box])


def test_amazon_tracking_rules_out_a_package_delivered_hours_apart() -> None:
    """A package delivered hours from Amazon's time didn't carry the shipment.

    The shipment neither rides along in it nor is suggested for it.
    """
    data = ParcelsData()
    fifth = _fifth(data)
    box = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.SHIPPED, _jun(9, 15)))
    _own_scans(data, box, _scan(_jun(10, 11, 58), ParcelStatus.DELIVERED, "Entregue"))

    result = reconcile(data, _jun(10, 22))

    assert not result.removed
    assert result.suggestions == []
    assert data.engine[AMAZON_LINKS_KEY] == {
        "made": 0,
        "ambiguous": 0,
        "contradicted": 1,
        "undone": 0,
    }
    shipment, package = data.parcels[fifth], data.parcels[box]
    assert amazon_contradicts(shipment, package)
    assert amazon_disagree(shipment, package)
    assert amazon_disagree(package, shipment)
    assert boxes_of_day(data, data.parcels.values(), JUNE_10) == {}


@pytest.mark.parametrize(
    ("source", "when", "contradicts"),
    [
        # A delivered e-mail or a mark by hand says it came by then.
        ("mail", _jun(10, 13, 27), False),
        ("mail", _jun(10, 6, 57), True),
        ("hand", _jun(10, 14, 27), False),
        ("hand", _jun(10, 6, 57), True),
        # A scan says when: more than two hours apart rules it out.
        ("scan", _jun(10, 11, 26), False),
        ("scan", _jun(10, 11, 28), True),
    ],
)
def test_amazon_tracking_contradiction_bounds(
    source: str, when: datetime, contradicts: bool
) -> None:
    """Amazon delivered at 09:27 UTC: which deliveries of a package rule it out."""
    data = ParcelsData()
    fifth = _fifth(data)
    box = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.SHIPPED, _jun(9, 15)))
    if source == "mail":
        assert _apply(data, _ctt("msg:c2#0", CTT_1, MailKind.DELIVERED, when)) == box
    elif source == "hand":
        mark_delivered(data, box, when)
    else:
        _own_scans(data, box, _scan(when, ParcelStatus.DELIVERED, "Entregue"))

    assert amazon_contradicts(data.parcels[fifth], data.parcels[box]) is contradicts


def test_amazon_tracking_never_links_a_pair_kept_apart() -> None:
    """A pair kept apart ("Not this one") never links, though the times agree."""
    data = ParcelsData()
    one, _two, first, second = _two_paack_boxes(data)
    keep_apart(data, data.parcels[one], data.parcels[first])

    result = reconcile(data, _jun(10, 22))

    assert result.removed == {second}
    assert first in data.parcels
    assert data.parcels[one].auto_merged is None
    assert data.engine[AMAZON_LINKS_KEY] == {
        "made": 1,
        "ambiguous": 0,
        "contradicted": 0,
        "undone": 0,
    }


@pytest.mark.parametrize(("place", "made"), [("Vila Exemplo", 1), ("Aldeia Modelo", 0)])
def test_amazon_tracking_places_must_match(place: str, made: int) -> None:
    """Delivered the same minute in another town isn't the same package."""
    data = ParcelsData()
    _fifth(data, *_came(delivered=f"Entregue, {place}, PT"))
    box = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.SHIPPED, _jun(9, 15, 2)))
    _own_scans(data, box, _scan(_jun(10, 9, 27), ParcelStatus.DELIVERED, HANDED))

    reconcile(data, _jun(10, 22))

    assert data.engine[AMAZON_LINKS_KEY] == {
        "made": made,
        "ambiguous": 0,
        "contradicted": 0,
        "undone": 0,
    }
    assert _linked(data.parcels[box]) is bool(made)


def test_a_shipment_merges_by_hand_into_a_package_carrying_another() -> None:
    """A package carrying one shipment may take another order's by hand.

    Two shipments still can't merge.
    """
    data = ParcelsData()
    third = _shipment(data, 3, ORDER_1, SHIPMENT_3, _jun(8, 9), *_at_center())
    fourth = _shipment(
        data, 4, ORDER_2, SHIPMENT_4, _jun(8, 10), *_at_center(_jun(9, 20))
    )
    box = _ctt_box(data)

    result = reconcile(data, _jun(10, 22))

    assert result.removed == {third}
    assert result.suggestions == []
    assert data.engine[AMAZON_LINKS_KEY] == {
        "made": 1,
        "ambiguous": 0,
        "contradicted": 0,
        "undone": 0,
    }

    accept_suggestion(data, box, fourth, _jun(10, 22, 30))

    assert fourth not in data.parcels
    shipments = set(data.parcels[box].state.amazon_shipment_ids)
    assert shipments == {SHIPMENT_3, SHIPMENT_4}

    eta = Eta(start=JUNE_10, end=JUNE_10)
    fifth = _apply(
        data, _amazon("msg:a5#0", ORDER_1, _jun(8, 9), eta, shipment_id=SHIPMENT_5)
    )
    sixth = _apply(
        data, _amazon("msg:a6#0", ORDER_3, _jun(8, 10), eta, shipment_id=SHIPMENT_6)
    )
    assert fifth != sixth
    assert _error(accept_suggestion, data, fifth, sixth, _jun(10, 22, 45)) == (
        "cannot_merge"
    )


def test_an_order_rides_along_in_a_package_carrying_shipments() -> None:
    """An order may ride along in a package carrying another order's shipments."""
    data = ParcelsData()
    box, _third, _fourth = _ctt_with_two(data)
    reconcile(data, _jun(10, 22))
    eta = Eta(start=JUNE_10, end=JUNE_10)

    seventh = _apply(data, _amazon("msg:a7#0", ORDER_3, _jun(8, 11), eta))

    assert boxes_of_day(data, data.parcels.values(), JUNE_10) == {seventh: (box,)}


@pytest.mark.parametrize(
    ("marked", "rides"), [(_jun(10, 21, 40), True), (_jun(10, 5), False)]
)
def test_marked_delivered_means_delivered_by_then(
    marked: datetime, rides: bool
) -> None:
    """Marking an order delivered by hand says it came by then, not then.

    It rides along in a package delivered earlier that day, not in a later one.
    """
    data = ParcelsData()
    eta = Eta(start=JUNE_10, end=JUNE_10)
    eighth = _apply(data, _amazon("msg:a8#0", ORDER_2, _jun(8, 9), eta))
    box = _mail_box(
        data,
        CTT_1,
        ("msg:c1#0", MailKind.SHIPPED, _jun(9, 15)),
        ("msg:c2#0", MailKind.DELIVERED, _jun(10, 9, 27)),
    )
    assert box != eighth

    mark_delivered(data, eighth, marked)

    expected = {eighth: (box,)} if rides else {}
    assert boxes_of_day(data, data.parcels.values(), JUNE_10) == expected


@pytest.mark.parametrize(
    ("ctt", "paack"), [(False, False), (True, False), (True, True)]
)
def test_amazon_tracking_narrows_the_packages_a_shipment_rides_in(
    ctt: bool, paack: bool
) -> None:
    """A shipment rides along only in the packages repeating most of its times.

    CTT's package names Amazon and Paack's name no shop, so the shop alone
    would put all four shipments in CTT's: before anything came, once CTT's
    came, and once both of Paack's came the same minute. Each shipment
    reached the carrier when its own package did; the van tells nothing.
    """
    data = ParcelsData()
    one, two, first, second = _two_paack_boxes(data, delivered=paack)
    box, third, fourth = _ctt_with_two(data, delivered=ctt)
    assert len({one, two, first, second, box, third, fourth}) == 7

    assert boxes_of_day(data, data.parcels.values(), JUNE_10) == {
        first: (one,),
        second: (two,),
        third: (box,),
        fourth: (box,),
    }


def _sixth(data: ParcelsData) -> str:
    """A shipment on its way whose tracking repeats no package's times."""
    return _shipment(
        data,
        6,
        ORDER_3,
        SHIPMENT_6,
        _jun(8, 11),
        _scan(_jun(9, 11, 11), ParcelStatus.IN_TRANSIT, ARRIVED),
        _scan(_jun(10, 6, 41), ParcelStatus.OUT_FOR_DELIVERY, VAN_OUT),
    )


def _one_paack_box(data: ParcelsData, *, van: bool = True) -> tuple[str, str]:
    """A shipment in its own Paack package, out for delivery on 10 June or not."""
    news = (
        _scan(_jun(9, 12, 36), ParcelStatus.IN_TRANSIT, ARRIVED),
        _scan(_jun(10, 6, 41), ParcelStatus.OUT_FOR_DELIVERY, VAN_OUT),
    )
    first = _shipment(
        data, 1, ORDER_1, SHIPMENT_1, _jun(8, 9), *(news if van else news[:1])
    )
    one = _apply(
        data,
        _paack_box("msg:p1#0", PAACK_1, MailKind.IN_TRANSIT, _jun(9, 12, 36, 16)),
    )
    if van:
        out = _paack_box(
            "msg:p3#0", PAACK_1, MailKind.OUT_FOR_DELIVERY, _jun(10, 6, 52)
        )
        assert _apply(data, out) == one
    return one, first


def test_amazon_tracking_narrows_the_packages_suggested_for_a_shipment() -> None:
    """A shipment is suggested only for the packages repeating its times.

    The morning the vans left, CTT's package names Amazon and Paack's name
    no shop, so the shop alone suggested all five shipments for CTT's. Two
    reached the carrier when a Paack package did: they're left out. One
    repeats no package's times, so the shop still decides for it.
    """
    data = ParcelsData()
    _one, _two, _first, _second = _two_paack_boxes(data, delivered=False)
    sixth = _sixth(data)
    box, third, fourth = _ctt_with_two(data, delivered=False)

    result = reconcile(data, _jun(10, 8))

    assert not result.removed
    assert [
        (suggestion.parcel_id, set(suggestion.candidates), suggestion.reason)
        for suggestion in result.suggestions
    ] == [(box, {third, fourth, sixth}, REASON_SAME_MERCHANT_DAY)]
    assert all(parcel.auto_merged is None for parcel in data.parcels.values())


@pytest.mark.parametrize(
    ("shipments", "van"),
    [(1, True), (1, False), (2, True)],
    ids=["one", "one-before-the-van", "two"],
)
def test_amazon_tracking_keeps_shipments_out_of_another_package(
    shipments: int, van: bool
) -> None:
    """Shipments that reached the carrier with Paack's packages aren't CTT's.

    CTT's package names Amazon and comes on the shop's day, so the shop
    alone merged a lone shipment into it, or suggested it for two.
    """
    data = ParcelsData()
    if shipments == 1:
        _one, first = _one_paack_box(data, van=van)
        mine = {first}
    else:
        _one, _two, first, second = _two_paack_boxes(data, delivered=False)
        mine = {first, second}
    box = _ctt_box(data, delivered=False)

    result = reconcile(data, _jun(10, 8))

    assert not result.removed
    assert result.suggestions == []
    assert mine <= data.parcels.keys()
    assert data.parcels[box].auto_merged is None


def test_a_narrowed_suggestion_never_merges() -> None:
    """Leaving a shipment out of a suggestion never makes it a merge.

    A shipment whose tracking repeats no package's times fits CTT's package
    too. With the other left out it's the only one, but it wasn't before.
    """
    data = ParcelsData()
    _one, _first = _one_paack_box(data)
    sixth = _sixth(data)
    box = _ctt_box(data, delivered=False)

    result = reconcile(data, _jun(10, 8))

    assert not result.removed
    assert [(s.parcel_id, s.candidates) for s in result.suggestions] == [
        (box, (sixth,))
    ]
    assert data.parcels[box].auto_merged is None


def _ctt_came() -> tuple[ParcelEvent, ...]:
    """CTT's own tracking of its package of 10 June, delivered."""
    return (
        _scan(_jun(10, 1, 41), ParcelStatus.IN_TRANSIT, CTT_ARRIVED),
        _scan(_jun(10, 7, 12), ParcelStatus.OUT_FOR_DELIVERY, "Em entrega"),
        _scan(_jun(10, 9, 27), ParcelStatus.DELIVERED, "Entregue"),
    )


def _guessed_into_ctt(data: ParcelsData) -> str:
    """A shipment the shop alone merged into CTT's package as the vans left.

    Its tracking repeats none of CTT's times, and no other package was
    known yet.
    """
    sixth = _sixth(data)
    box = _ctt_box(data, delivered=False)
    reconcile(data, _jun(10, 8))
    assert sixth not in data.parcels
    flag = data.parcels[box].auto_merged
    assert flag is not None
    assert flag.reason == REASON_SAME_MERCHANT_DAY
    assert flag.origin == "msg:a6#0"
    assert flag.all_origins == {"msg:a6#0", "pa:t6"}
    return box


def _late_paack(
    data: ParcelsData, key: int, number: str, first: datetime, came: datetime
) -> str:
    """Paack's e-mails about a package, read only after it came."""
    read = _jun(10, 10, 20)
    box = _apply(
        data, _paack_box(f"msg:p{key}#0", number, MailKind.IN_TRANSIT, first), read
    )
    delivered = _paack_box(f"msg:p{key + 4}#0", number, MailKind.DELIVERED, came)
    assert _apply(data, delivered, read) == box
    return box


def _sixth_came(data: ParcelsData, parcel_id: str) -> None:
    """Amazon's tracking of the sixth shipment, now delivered."""
    tracking = _parcel_app(
        "t6",
        "msg:a6#0",
        (
            _scan(_jun(9, 11, 11), ParcelStatus.IN_TRANSIT, ARRIVED),
            _scan(_jun(10, 6, 41), ParcelStatus.OUT_FOR_DELIVERY, VAN_OUT),
            _scan(_jun(10, 10, 14), ParcelStatus.DELIVERED, HANDED),
        ),
        order_numbers=(ORDER_3,),
        amazon_shipment_id=SHIPMENT_6,
    )
    assert _apply(data, tracking, _jun(10, 10, 20)) == parcel_id


def test_a_guess_is_undone_when_amazons_tracking_points_to_another_package() -> None:
    """A shop's guess is undone when Amazon's tracking points to another package.

    As the vans left, the shop alone merged a shipment into CTT's package.
    Paack's e-mails, read later, came the minutes the shipment reached the
    carrier and was delivered; CTT's package came at another time. The
    guess is undone as Undo would, and the shipment joins Paack's package.
    """
    data = ParcelsData()
    box = _guessed_into_ctt(data)
    paack = _late_paack(data, 1, PAACK_1, _jun(9, 11, 11, 20), _jun(10, 10, 14, 22))
    _sixth_came(data, box)
    _own_scans(data, box, *_ctt_came())

    result = reconcile(data, _jun(10, 22))

    assert set(data.parcels) == {box, paack}
    assert {box, paack} <= result.changed
    ctt = data.parcels[box]
    assert set(ctt.origins) == {"msg:c1#0", "pa:c1"}
    assert ctt.auto_merged is None
    parcel = data.parcels[paack]
    assert set(parcel.origins) == {"msg:p1#0", "msg:p5#0", "msg:a6#0", "pa:t6"}
    flag = parcel.auto_merged
    assert flag is not None
    assert flag.reason == REASON_AMAZON_TRACKING
    assert flag.origin == "msg:a6#0"
    assert flag.all_origins == {"msg:a6#0", "pa:t6"}
    links = {"made": 1, "ambiguous": 0, "contradicted": 0, "undone": 1}
    assert data.engine[AMAZON_LINKS_KEY] == links

    again = reconcile(data, _jun(10, 23))

    assert not again.removed
    assert again.suggestions == []
    assert set(data.parcels[box].origins) == {"msg:c1#0", "pa:c1"}
    assert len(data.parcels[paack].origins) == 4
    assert data.engine[AMAZON_LINKS_KEY] == links


def _guessed_by_eta(data: ParcelsData) -> str:
    """CTT's e-mail naming Amazon, put in the shipment due that day."""
    first = _shipment(
        data,
        1,
        ORDER_1,
        SHIPMENT_1,
        _jun(8, 9),
        _scan(_jun(9, 12, 36), ParcelStatus.IN_TRANSIT, ARRIVED),
        _scan(_jun(10, 6, 41), ParcelStatus.OUT_FOR_DELIVERY, VAN_OUT),
    )
    mail = _ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _jun(10, 7, 30))
    assert _apply(data, mail) == first
    flag = data.parcels[first].auto_merged
    assert flag is not None
    assert (flag.reason, flag.origin, flag.origins) == (
        REASON_SAME_MERCHANT_ETA,
        "msg:c1#0",
        (),
    )
    return first


def _first_came(data: ParcelsData, parcel_id: str) -> None:
    """Amazon's tracking of the first shipment, delivered hours after CTT's."""
    tracking = _parcel_app(
        "t1",
        "msg:a1#0",
        (
            _scan(_jun(9, 12, 36), ParcelStatus.IN_TRANSIT, ARRIVED),
            _scan(_jun(10, 6, 41), ParcelStatus.OUT_FOR_DELIVERY, VAN_OUT),
            _scan(_jun(10, 12, 30), ParcelStatus.DELIVERED, HANDED),
        ),
        order_numbers=(ORDER_1,),
        amazon_shipment_id=SHIPMENT_1,
    )
    assert _apply(data, tracking, _jun(10, 13)) == parcel_id


@pytest.mark.parametrize("by_hand", [False, True], ids=["scanned", "by-hand"])
def test_a_guess_is_undone_when_amazons_tracking_rules_its_package_out(
    by_hand: bool,
) -> None:
    """A shop's guess is undone when its package came hours before the shipment.

    CTT's e-mail named Amazon and came the day a shipment was due, so it
    joined the shipment. CTT's package came three hours before Amazon's
    tracking says the shipment did, by its own tracking or by the user's
    mark, which says it came by then. The user's edits stay, as with Undo.
    """
    data = ParcelsData()
    first = _guessed_by_eta(data)
    if by_hand:
        mark_delivered(data, first, _jun(10, 9, 27))
    else:
        _own_scans(data, first, *_ctt_came())
    _first_came(data, first)

    result = reconcile(data, _jun(10, 14))

    [ctt] = set(data.parcels) - {first}
    assert {first, ctt} <= result.changed
    shipment = data.parcels[first]
    mine = {"msg:a1#0", "pa:t1"}
    assert set(shipment.origins) == mine | (
        {manual_origin_id(first)} if by_hand else set()
    )
    assert shipment.auto_merged is None
    package = data.parcels[ctt]
    assert set(package.origins) == {"msg:c1#0"} | (set() if by_hand else {"pa:c1"})
    assert package.auto_merged is None
    links = {"made": 0, "ambiguous": 0, "contradicted": 0, "undone": 1}
    assert data.engine[AMAZON_LINKS_KEY] == links

    again = reconcile(data, _jun(10, 15))

    assert not again.removed
    assert again.suggestions == []
    assert set(data.parcels) == {first, ctt}
    assert data.engine[AMAZON_LINKS_KEY] == links


@pytest.mark.parametrize(
    "reason",
    [
        None,
        REASON_SAME_ORDER,
        REASON_SAME_NUMBER,
        REASON_SAME_REFERENCE,
        REASON_SAME_MERCHANT_DOMAIN,
        REASON_AMAZON_TRACKING,
    ],
)
def test_only_the_shops_guesses_are_undone(reason: str | None) -> None:
    """Only the shop's guesses are undone, never the user's merges.

    A merge the user made or kept carries no flag. An order, a number, a
    reference, a shop's own domain or Amazon's tracking are no guess.
    """
    data = ParcelsData()
    first = _guessed_by_eta(data)
    _own_scans(data, first, *_ctt_came())
    _first_came(data, first)
    guess = data.parcels[first].auto_merged
    assert guess is not None
    flag = None if reason is None else replace(guess, reason=reason)
    data.parcels[first].auto_merged = flag

    reconcile(data, _jun(10, 14))

    assert set(data.parcels) == {first}
    parcel = data.parcels[first]
    assert set(parcel.origins) == {"msg:a1#0", "pa:t1", "msg:c1#0", "pa:c1"}
    assert parcel.auto_merged == flag
    assert AMAZON_LINKS_KEY not in data.engine


def test_a_guess_put_away_stays() -> None:
    """A guess about a parcel put away stays: undoing it would bring it back."""
    data = ParcelsData()
    first = _guessed_by_eta(data)
    _own_scans(data, first, *_ctt_came())
    _first_came(data, first)
    data.parcels[first].archived = _jun(10, 13, 30)

    reconcile(data, _jun(10, 14))

    assert set(data.parcels) == {first}
    parcel = data.parcels[first]
    assert len(parcel.origins) == 4
    assert parcel.auto_merged is not None
    assert parcel.archived == _jun(10, 13, 30)
    assert AMAZON_LINKS_KEY not in data.engine


def test_a_guess_stays_when_the_user_merged_another_shipment_in() -> None:
    """A guess stays when the user merged another shipment into the parcel.

    Amazon's tracking of the two shipments then tells two stories, and the
    user put them together.
    """
    data = ParcelsData()
    first = _guessed_by_eta(data)
    _own_scans(data, first, *_ctt_came())
    _first_came(data, first)
    second = _shipment(data, 2, ORDER_2, SHIPMENT_2, _jun(8, 10), *_at_center())
    merge_parcels(data, first, [second], _jun(10, 13, 30))

    reconcile(data, _jun(10, 14))

    assert set(data.parcels) == {first}
    parcel = data.parcels[first]
    assert len(parcel.origins) == 6
    flag = parcel.auto_merged
    assert flag is not None
    assert flag.reason == REASON_SAME_MERCHANT_ETA
    assert AMAZON_LINKS_KEY not in data.engine


def _guess_and_others(data: ParcelsData, case: str) -> str:
    """A shop's guess into CTT's package, then Paack's packages, as in ``case``."""
    box = _guessed_into_ctt(data)
    first, came = _jun(9, 11, 11, 20), _jun(10, 10, 14, 22)
    if case == "came-only":
        first = _jun(9, 13, 30)
    if case == "reached-only":
        came = _jun(10, 11, 30)
    paack = _late_paack(data, 1, PAACK_1, first, came)
    if case == "two-packages":
        _late_paack(data, 2, PAACK_2, _jun(9, 11, 11, 30), _jun(10, 10, 14, 40))
    if case == "private":
        data.parcels[paack].private = True
    if case != "not-delivered":
        _sixth_came(data, box)
    scans = _ctt_came()
    if case == "merged-one-agrees":
        scans = (
            _scan(_jun(9, 11, 11), ParcelStatus.IN_TRANSIT, CTT_ARRIVED),
            scans[1],
            _scan(_jun(10, 10, 15), ParcelStatus.DELIVERED, "Entregue"),
        )
    _own_scans(data, box, *scans)
    return box


@pytest.mark.parametrize("case", ["merged-one-agrees", "private"])
def test_a_guess_stays_when_the_merged_package_agrees_or_no_other_may(
    case: str,
) -> None:
    """A guess stays when the merged package repeats the shipment's times.

    Or when the only other package repeating them can't have held the
    shipment: a private package doesn't hold a public one.
    """
    data = ParcelsData()
    box = _guess_and_others(data, case)

    reconcile(data, _jun(10, 22))

    parcel = data.parcels[box]
    assert set(parcel.origins) == {"msg:c1#0", "pa:c1", "msg:a6#0", "pa:t6"}
    flag = parcel.auto_merged
    assert flag is not None
    assert flag.reason == REASON_SAME_MERCHANT_DAY
    assert data.engine[AMAZON_LINKS_KEY] == NO_LINKS


@pytest.mark.parametrize(
    ("case", "ambiguous"),
    [
        ("two-packages", 1),
        ("came-only", 0),
        ("reached-only", 0),
        ("not-delivered", 0),
    ],
)
def test_a_guess_is_undone_when_the_merged_package_repeats_none_of_its_times(
    case: str, ambiguous: int
) -> None:
    """A guess is undone when the tracking points only to other packages.

    CTT's package repeats none of the shipment's times but the van leaving,
    and Paack's repeat some: two packages repeat both, one repeats only the
    minute the shipment came, or only the one it reached the carrier, or
    the shipment hasn't come yet. The guess is undone as Undo would, and the
    two stay apart. Two packages repeating both times are each suggested.
    """
    data = ParcelsData()
    box = _guess_and_others(data, case)

    result = reconcile(data, _jun(10, 22))

    ctt = data.parcels[box]
    assert set(ctt.origins) == {"msg:c1#0", "pa:c1"}
    assert ctt.auto_merged is None
    [shipment] = [
        parcel for parcel in data.parcels.values() if "msg:a6#0" in parcel.origins
    ]
    assert set(shipment.origins) == {"msg:a6#0", "pa:t6"}
    assert {box, shipment.id} <= result.changed
    assert all(box not in suggestion.candidates for suggestion in result.suggestions)
    assert len(result.suggestions) == 2 * ambiguous
    links = {"made": 0, "ambiguous": ambiguous, "contradicted": 0, "undone": 1}
    assert data.engine[AMAZON_LINKS_KEY] == links

    again = reconcile(data, _jun(10, 23))

    assert not again.removed
    assert set(data.parcels[box].origins) == {"msg:c1#0", "pa:c1"}
    assert set(data.parcels[shipment.id].origins) == {"msg:a6#0", "pa:t6"}
    assert data.engine[AMAZON_LINKS_KEY] == links


def _paack_first(data: ParcelsData, first: datetime) -> str:
    """Paack's package of 10 June: its first e-mail, and the van leaving."""
    paack = _apply(data, _paack_box("msg:p1#0", PAACK_1, MailKind.IN_TRANSIT, first))
    out = _paack_box("msg:p3#0", PAACK_1, MailKind.OUT_FOR_DELIVERY, _jun(10, 6, 52))
    assert _apply(data, out) == paack
    return paack


def _first_on_its_way() -> Contribution:
    """Amazon's tracking of the first shipment: at the carrier, then the van."""
    return _parcel_app(
        "t1",
        "msg:a1#0",
        (
            _scan(_jun(9, 12, 36), ParcelStatus.IN_TRANSIT, ARRIVED),
            _scan(_jun(10, 6, 41), ParcelStatus.OUT_FOR_DELIVERY, VAN_OUT),
        ),
        order_numbers=(ORDER_1,),
        amazon_shipment_id=SHIPMENT_1,
    )


def test_the_shops_guess_skips_a_shipment_whose_tracking_points_elsewhere() -> None:
    """The shop and day don't put a package with a shipment pointing elsewhere.

    Amazon's tracking of the shipment due that day, read the evening
    before, says it reached the carrier the minute Paack's first e-mail
    came. CTT's e-mail naming Amazon, as the vans leave, makes a parcel of
    its own, and the day's look neither merges nor suggests the two.
    """
    data = ParcelsData()
    first = _shipment(data, 1, ORDER_1, SHIPMENT_1, _jun(8, 9))
    assert _apply(data, _first_on_its_way(), _jun(9, 19)) == first
    paack = _paack_first(data, _jun(9, 12, 36, 16))

    ctt = _apply(
        data, _ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _jun(10, 7, 30))
    )

    assert ctt not in {first, paack}
    assert set(data.parcels[first].origins) == {"msg:a1#0", "pa:t1"}
    assert set(data.parcels[ctt].origins) == {"msg:c1#0"}

    result = reconcile(data, _jun(10, 8))

    assert not result.removed
    assert result.suggestions == []
    assert set(data.parcels) == {first, paack, ctt}
    assert all(parcel.auto_merged is None for parcel in data.parcels.values())
    assert data.engine[AMAZON_LINKS_KEY] == NO_LINKS


def test_the_shops_guess_stands_when_amazons_tracking_points_nowhere() -> None:
    """The shop's guess stands when the tracking repeats no package's times.

    Paack's first e-mail came at another time than the shipment reached the
    carrier: nothing tells CTT's package isn't the one.
    """
    data = ParcelsData()
    first = _shipment(data, 1, ORDER_1, SHIPMENT_1, _jun(8, 9))
    assert _apply(data, _first_on_its_way(), _jun(9, 19)) == first
    _paack_first(data, _jun(9, 13, 30))
    mail = _ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _jun(10, 7, 30))
    assert _apply(data, mail) == first

    reconcile(data, _jun(10, 8))

    parcel = data.parcels[first]
    assert set(parcel.origins) == {"msg:a1#0", "pa:t1", "msg:c1#0"}
    flag = parcel.auto_merged
    assert flag is not None
    assert (flag.reason, flag.origin) == (REASON_SAME_MERCHANT_ETA, "msg:c1#0")
    assert AMAZON_LINKS_KEY not in data.engine


def test_a_guess_is_undone_once_amazons_tracking_points_elsewhere() -> None:
    """A guess made before the tracking was read is undone at the next look.

    CTT's e-mail naming Amazon joined the shipment due that day, whose
    tracking the Parcel app hadn't read yet. The tracking then says the
    shipment reached the carrier the minute Paack's first e-mail came, and
    repeats none of CTT's times: before anything came, the guess is undone
    as Undo would, and stays undone.
    """
    data = ParcelsData()
    first = _shipment(data, 1, ORDER_1, SHIPMENT_1, _jun(8, 9))
    paack = _paack_first(data, _jun(9, 12, 36, 16))
    mail = _ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _jun(10, 7, 30))
    assert _apply(data, mail) == first
    guess = data.parcels[first].auto_merged
    assert guess is not None
    assert guess.reason == REASON_SAME_MERCHANT_ETA
    assert _apply(data, _first_on_its_way(), _jun(10, 7, 45)) == first

    result = reconcile(data, _jun(10, 8))

    [ctt] = set(data.parcels) - {first, paack}
    assert {first, ctt} <= result.changed
    assert set(data.parcels[first].origins) == {"msg:a1#0", "pa:t1"}
    assert data.parcels[first].auto_merged is None
    assert set(data.parcels[ctt].origins) == {"msg:c1#0"}
    assert result.suggestions == []
    links = {"made": 0, "ambiguous": 0, "contradicted": 0, "undone": 1}
    assert data.engine[AMAZON_LINKS_KEY] == links

    again = reconcile(data, _jun(10, 8, 5))

    assert not again.removed
    assert again.suggestions == []
    assert set(data.parcels) == {first, paack, ctt}
    assert set(data.parcels[ctt].origins) == {"msg:c1#0"}
    assert data.engine[AMAZON_LINKS_KEY] == links


def test_a_guess_stays_when_the_package_it_points_to_went_back() -> None:
    """A guess stays when the package Amazon's tracking points to went back.

    Paack's package came the minutes the shipment did, then went back to
    its sender. A package sent back is never linked, so nothing would take
    the shipment from CTT's package.
    """
    data = ParcelsData()
    box = _guessed_into_ctt(data)
    paack = _late_paack(data, 1, PAACK_1, _jun(9, 11, 11, 20), _jun(10, 10, 14, 22))
    _sixth_came(data, box)
    _own_scans(data, box, *_ctt_came())
    back = _paack_box("msg:p9#0", PAACK_1, MailKind.RETURN, _jun(10, 18))
    assert _apply(data, back) == paack
    assert data.parcels[paack].state.status is ParcelStatus.RETURNED

    reconcile(data, _jun(10, 22))

    assert set(data.parcels) == {box, paack}
    parcel = data.parcels[box]
    assert set(parcel.origins) == {"msg:c1#0", "pa:c1", "msg:a6#0", "pa:t6"}
    flag = parcel.auto_merged
    assert flag is not None
    assert flag.reason == REASON_SAME_MERCHANT_DAY
    assert data.engine[AMAZON_LINKS_KEY] == NO_LINKS


def test_a_guess_the_user_gave_a_tracking_number_stays() -> None:
    """A guess stays once the user gave the parcel a tracking number.

    Undo would leave the user's edits with the shipment, which would then
    have a carrier's number of its own: the user may have named its package.
    """
    data = ParcelsData()
    first = _guessed_by_eta(data)
    _own_scans(data, first, *_ctt_came())
    _first_came(data, first)
    update_parcel(data, first, {"tracking_number": "EX123456789099"}, _jun(10, 13))

    reconcile(data, _jun(10, 14))

    assert set(data.parcels) == {first}
    parcel = data.parcels[first]
    mine = {"msg:a1#0", "pa:t1", manual_origin_id(first)}
    assert set(parcel.origins) == mine | {"msg:c1#0", "pa:c1"}
    flag = parcel.auto_merged
    assert flag is not None
    assert flag.reason == REASON_SAME_MERCHANT_ETA
    assert AMAZON_LINKS_KEY not in data.engine


def test_a_guess_of_an_email_naming_no_package_stays() -> None:
    """A guess stays when the e-mail it put in names no package.

    Amazon's e-mail without an order or a number joined the shipment due
    that day. Paack's package repeats the shipment's times, but undoing the
    guess would leave the e-mail on its own: the shipment is only suggested
    for the package.
    """
    data = ParcelsData()
    arrived = _scan(_jun(9, 11, 11), ParcelStatus.IN_TRANSIT, ARRIVED)
    van = _scan(_jun(10, 6, 41), ParcelStatus.OUT_FOR_DELIVERY, VAN_OUT)
    first = _shipment(data, 1, ORDER_1, SHIPMENT_1, _jun(8, 9), arrived, van)
    mail = contribution(
        "msg:a7#0",
        kind=MailKind.OUT_FOR_DELIVERY,
        time=_jun(10, 7, 30),
        merchant="Amazon.es",
        eta=Eta(start=JUNE_10, end=JUNE_10),
        label="amazon.es",
    )
    assert _apply(data, mail) == first
    guess = data.parcels[first].auto_merged
    assert guess is not None
    assert (guess.reason, guess.origin) == (REASON_SAME_MERCHANT_ETA, "msg:a7#0")
    came = _scan(_jun(10, 10, 14), ParcelStatus.DELIVERED, HANDED)
    tracking = _parcel_app(
        "t1",
        "msg:a1#0",
        (arrived, van, came),
        order_numbers=(ORDER_1,),
        amazon_shipment_id=SHIPMENT_1,
    )
    assert _apply(data, tracking, _jun(10, 10, 20)) == first
    paack = _late_paack(data, 1, PAACK_1, _jun(9, 11, 11, 20), _jun(10, 10, 14, 22))

    result = reconcile(data, _jun(10, 22))

    assert set(data.parcels) == {first, paack}
    parcel = data.parcels[first]
    assert set(parcel.origins) == {"msg:a1#0", "pa:t1", "msg:a7#0"}
    flag = parcel.auto_merged
    assert flag is not None
    assert (flag.reason, flag.origin) == (REASON_SAME_MERCHANT_ETA, "msg:a7#0")
    assert [(s.parcel_id, s.candidates) for s in result.suggestions] == [
        (paack, (first,))
    ]
    assert data.engine[AMAZON_LINKS_KEY] == NO_LINKS


def test_a_guess_undone_counts_when_the_shipment_left_a_month_before() -> None:
    """A guess undone counts when the shipment left over a month before.

    Only parcels with news in the last 30 days are looked at, so once apart
    the shipment, whose e-mail and tracking began in May, has nothing to
    link. The undo still counts.
    """
    data = ParcelsData()
    may = datetime(2026, 5, 4, 12, 36, tzinfo=UTC)
    arrived = _scan(may, ParcelStatus.IN_TRANSIT, ARRIVED)
    van = _scan(_jun(10, 6, 41), ParcelStatus.OUT_FOR_DELIVERY, VAN_OUT)
    sent = datetime(2026, 5, 2, 9, tzinfo=UTC)
    first = _shipment(data, 1, ORDER_1, SHIPMENT_1, sent, arrived, van)
    mail = _ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _jun(10, 7, 30))
    assert _apply(data, mail) == first
    guess = data.parcels[first].auto_merged
    assert guess is not None
    assert guess.reason == REASON_SAME_MERCHANT_ETA
    _own_scans(data, first, *_ctt_came())
    came = _scan(_jun(10, 12, 30), ParcelStatus.DELIVERED, HANDED)
    tracking = _parcel_app(
        "t1",
        "msg:a1#0",
        (arrived, van, came),
        order_numbers=(ORDER_1,),
        amazon_shipment_id=SHIPMENT_1,
    )
    assert _apply(data, tracking, _jun(10, 13)) == first

    result = reconcile(data, _jun(10, 14))

    [ctt] = set(data.parcels) - {first}
    assert {first, ctt} <= result.changed
    assert set(data.parcels[first].origins) == {"msg:a1#0", "pa:t1"}
    assert set(data.parcels[ctt].origins) == {"msg:c1#0", "pa:c1"}
    links = {"made": 0, "ambiguous": 0, "contradicted": 0, "undone": 1}
    assert data.engine[AMAZON_LINKS_KEY] == links


def test_details_list_the_packages_amazons_tracking_points_away_from() -> None:
    """The details list the packages a shipment's tracking points away from.

    Both ways: from a shipment, the packages that don't repeat its times,
    when some do; from a package, the shipments pointing to others. Not the
    parcels the viewer may not see, nor a mark pointing only to those.
    """
    data = ParcelsData()
    one, two, first, second = _two_paack_boxes(data, delivered=False)
    sixth = _sixth(data)
    box, third, fourth = _ctt_with_two(data, delivered=False)
    engine: Any = SimpleNamespace(data=data)

    def elsewhere(parcel_id: str, viewer: Viewer = SYSTEM_VIEWER) -> list[str]:
        return details(engine, data.parcels[parcel_id], viewer)["elsewhere"]

    assert elsewhere(first) == sorted((two, box))
    assert elsewhere(third) == sorted((one, two))
    assert elsewhere(box) == sorted((first, second))
    assert elsewhere(one) == sorted((second, third, fourth))
    assert elsewhere(sixth) == []
    data.parcels[two].private = True
    stranger = Viewer(is_admin=False, persons=frozenset({"person.two"}))
    assert elsewhere(first, stranger) == [box]
    assert elsewhere(box, stranger) == [first]
    shipment = data.parcels[second]
    shipment.private = True
    for origin in shipment.origins.values():
        origin.owners = ("person.two",)
    shipment.touch(_jun(10, 8))
    both = Viewer(is_admin=False, persons=frozenset({"person.one", "person.two"}))
    assert elsewhere(second, both) == sorted((one, box))
    assert elsewhere(second, stranger) == []
    assert elsewhere(box, both) == sorted((first, second))
    assert elsewhere(box, stranger) == [first]


def _seen(data: ParcelsData, **reads: datetime) -> None:
    """When Parcels last read each delivery in the Parcel app."""
    records = data.parcelapp.setdefault("records", {})
    for key, when in reads.items():
        records[key] = {"seen": dt_to_str(when)}


@pytest.mark.parametrize("linked", [False, True])
@pytest.mark.parametrize(
    ("reads", "in_ctt"),
    [
        # Read with the shipments in CTT's package, which it showed delivered.
        ({"t3": _jun(10, 9, 40), "t4": _jun(10, 9, 40), "t6": _jun(10, 9, 40)}, False),
        # Read before that read: it may not have shown CTT's delivery yet.
        ({"t3": _jun(10, 9, 40), "t4": _jun(10, 9, 40), "t6": _jun(10, 9, 35)}, True),
        # Not read since.
        ({"t3": _jun(10, 9, 40), "t4": _jun(10, 9, 40)}, True),
        ({}, True),
    ],
)
def test_a_shipment_on_its_way_wasnt_in_a_package_shown_delivered(
    reads: dict[str, datetime], in_ctt: bool, linked: bool
) -> None:
    """A shipment still on its way wasn't in a package delivered before.

    The Parcel app read Amazon's tracking on the user's phone, so its reads
    tell only what Amazon's tracking showed then. That read showed CTT's
    package delivered with the shipments it carried, their times agreeing,
    and this one still on its way: it may only be in one of Paack's.
    Otherwise CTT's, which names its shop, still comes first.
    """
    data = ParcelsData()
    one, two, _first, _second = _two_paack_boxes(data, delivered=False)
    box, third, fourth = _ctt_with_two(data)
    sixth = _sixth(data)
    _seen(data, **reads)
    if linked:
        result = reconcile(data, _jun(10, 9, 45))
        assert result.removed == {third, fourth}
        assert _linked(data.parcels[box])

    riding = boxes_of_day(data, data.parcels.values(), JUNE_10)

    assert set(riding[sixth]) == ({box} if in_ctt else {one, two})


@pytest.mark.parametrize(
    ("after", "in_ctt"),
    [(AMAZON_CATCH_UP, False), (AMAZON_CATCH_UP - timedelta(minutes=1), True)],
)
def test_amazon_tracking_an_hour_after_a_package_came_shows_it(
    after: timedelta, in_ctt: bool
) -> None:
    """Amazon's tracking read with news an hour after a package came shows it.

    Another order's shipment, due later, had news then: the shipment still
    on its way, read with it, wasn't in CTT's package. A minute less proves
    nothing.
    """
    data = ParcelsData()
    one, two, _first, _second = _two_paack_boxes(data, delivered=False)
    box = _ctt_box(data)
    sixth = _sixth(data)
    _shipment(
        data,
        5,
        ORDER_1,
        SHIPMENT_5,
        _jun(8, 9),
        _scan(_jun(10, 9, 27) + after, ParcelStatus.IN_TRANSIT, ARRIVED),
        eta=Eta(start=date(2026, 6, 12), end=date(2026, 6, 12)),
    )
    _seen(data, t5=_jun(10, 10, 40), t6=_jun(10, 10, 40))

    riding = boxes_of_day(data, data.parcels.values(), JUNE_10)

    assert set(riding[sixth]) == ({box} if in_ctt else {one, two})


def test_amazon_tracking_needs_the_parcel_app() -> None:
    """Without the Parcel app, Amazon's e-mails give no tracking to match."""
    data = ParcelsData()
    eta = Eta(start=JUNE_10, end=JUNE_10)
    fifth = _apply(
        data, _amazon("msg:a5#0", ORDER_1, _jun(8, 9), eta, shipment_id=SHIPMENT_5)
    )
    box = _mail_box(
        data,
        CTT_1,
        ("msg:c1#0", MailKind.SHIPPED, _jun(9, 15)),
        ("msg:c2#0", MailKind.DELIVERED, _jun(10, 11, 58)),
    )
    assert amazon_evidence(data.parcels[fifth]) is None
    assert not amazon_contradicts(data.parcels[fifth], data.parcels[box])

    reconcile(data, _jun(10, 22))

    assert AMAZON_LINKS_KEY not in data.engine


def test_amazon_tracking_skips_amazons_own_deliveries() -> None:
    """A delivery of Amazon's own, with its number, isn't another's package."""
    data = ParcelsData()
    _fifth(data)
    eta = Eta(start=JUNE_10, end=JUNE_10)
    own = _apply(
        data,
        _amazon(
            "msg:a6#0",
            ORDER_2,
            _jun(8, 10),
            eta,
            number=AMAZON_LOGISTICS,
            carrier="amazon",
            shipment_id=SHIPMENT_6,
        ),
    )
    tracking = _parcel_app(
        "tba", "msg:a6#0", _came(), carrier="amazon", tracking_number=AMAZON_LOGISTICS
    )
    assert _apply(data, tracking) == own

    reconcile(data, _jun(10, 22))

    assert data.engine[AMAZON_LINKS_KEY] == NO_LINKS
    assert not _linked(data.parcels[own])


@pytest.mark.parametrize(
    ("status", "label", "made"),
    [(ParcelStatus.IN_TRANSIT, ARRIVED, 1), (None, None, 0)],
)
def test_amazon_tracking_counts_only_news_of_the_shipment(
    status: ParcelStatus | None, label: str | None, made: int
) -> None:
    """A new estimate isn't news of where the shipment is."""
    data = ParcelsData()
    _fifth(
        data,
        _scan(_jun(9, 15, 2), status, label, eta=Eta(start=JUNE_10, end=JUNE_10)),
        _scan(_jun(10, 9, 27), ParcelStatus.DELIVERED, "Entregue"),
    )
    _mail_box(
        data,
        CTT_1,
        ("msg:c1#0", MailKind.SHIPPED, _jun(9, 15, 2)),
        ("msg:c2#0", MailKind.DELIVERED, _jun(10, 9, 27, 30)),
    )

    reconcile(data, _jun(10, 22))

    assert data.engine[AMAZON_LINKS_KEY]["made"] == made


def _evidence(*events: ParcelEvent) -> AmazonEvidence | None:
    data = ParcelsData()
    return amazon_evidence(data.parcels[_fifth(data, *events)])


def test_amazon_evidence() -> None:
    """When and where Amazon's tracking says a shipment was delivered."""
    delivered = ParcelStatus.DELIVERED
    at_center = _scan(_jun(9, 15, 2), ParcelStatus.IN_TRANSIT, ARRIVED)
    assert _evidence(*_came()) == AmazonEvidence(_jun(10, 9, 27), False, None)
    assert _evidence(*_came(delivered=HANDED)) == AmazonEvidence(
        _jun(10, 9, 27), False, "Vila Exemplo"
    )
    # The country's code may come twice; a label of codes alone names no place.
    assert _evidence(*_came(delivered="Entregue, Vila Exemplo, PT PT")) == (
        AmazonEvidence(_jun(10, 9, 27), False, "Vila Exemplo")
    )
    assert _evidence(*_came(delivered="Entregue, PT PT")) == AmazonEvidence(
        _jun(10, 9, 27), False, None
    )
    # The day without the time, then no day at all.
    timeless = _scan(_jun(10, 12), delivered, "Entregue", undated=True, timeless=True)
    assert _evidence(at_center, timeless) == AmazonEvidence(_jun(10, 12), True, None)
    dayless = _scan(_jun(10, 12), delivered, "Entregue", undated=True, dayless=True)
    assert _evidence(at_center, dayless) is None
    assert _evidence(at_center) is None
    # A carrier's package isn't a shipment.
    data = ParcelsData()
    assert amazon_evidence(data.parcels[_ctt_box(data)]) is None


def test_page_shows_amazons_tracking() -> None:
    """The page shows when and where Amazon's tracking says a shipment came.

    Only for Amazon's shipments, and only to those who may see them.
    """
    data = ParcelsData()
    shipment = data.parcels[_fifth(data, *_came(delivered=HANDED))]
    box = data.parcels[_ctt_box(data)]

    assert parcel_json(shipment, SYSTEM_VIEWER)["amazon_tracking"] == {
        "delivered": "2026-06-10T09:27:00+00:00",
        "timeless": False,
        "place": "Vila Exemplo",
    }
    assert parcel_json(box, SYSTEM_VIEWER)["amazon_tracking"] is None
    shipment.private = True
    stranger = Viewer(is_admin=False, persons=frozenset({"person.two"}))
    assert parcel_json(shipment, stranger)["amazon_tracking"] is None


def test_details_list_the_parcels_amazons_tracking_rules_out() -> None:
    """The details list the parcels Amazon's tracking rules out, both ways.

    Not a package whose time agrees, nor one the viewer may not see.
    """
    data = ParcelsData()
    fifth = _fifth(data)
    apart = _apply(data, _ctt("msg:c1#0", CTT_1, MailKind.SHIPPED, _jun(9, 15)))
    _own_scans(data, apart, _scan(_jun(10, 11, 58), ParcelStatus.DELIVERED, "Entregue"))
    agrees = _mail_box(
        data, CTT_2, ("msg:c3#0", MailKind.DELIVERED, _jun(10, 9, 27, 30))
    )
    engine: Any = SimpleNamespace(data=data)

    def contradicted(parcel_id: str, viewer: Viewer = SYSTEM_VIEWER) -> list[str]:
        return details(engine, data.parcels[parcel_id], viewer)["contradicted"]

    assert contradicted(fifth) == [apart]
    assert contradicted(apart) == [fifth]
    assert contradicted(agrees) == []
    data.parcels[apart].private = True
    stranger = Viewer(is_admin=False, persons=frozenset({"person.two"}))
    assert contradicted(fifth, stranger) == []


@pytest.mark.parametrize(("carrier", "made"), [(None, 1), ("ctt", 1), ("dpd", 0)])
def test_amazon_tracking_keeps_the_named_carrier(
    carrier: str | None, made: int
) -> None:
    """A shipment Amazon says another carrier took isn't in CTT's package."""
    data = ParcelsData()
    _shipment(data, 3, ORDER_1, SHIPMENT_3, _jun(8, 9), *_at_center(), carrier=carrier)
    _ctt_box(data)

    reconcile(data, _jun(10, 22))

    assert data.engine[AMAZON_LINKS_KEY] == {
        "made": made,
        "ambiguous": 0,
        "contradicted": 0,
        "undone": 0,
    }


# --- Guesses and private parcels ------------------------------------------------
# A guess never puts a private parcel together with someone else's parcel or
# e-mail: people who can see both get a merge suggestion instead.

SHARING = pytest.mark.parametrize(
    ("owner", "merged"), [("person.one", True), ("person.two", False)]
)


def _private(contrib: Contribution) -> Contribution:
    contrib.private = True
    return contrib


def _of(owner: str, contrib: Contribution) -> Contribution:
    contrib.origin.owners = (owner,)
    return contrib


def _make_private(data: ParcelsData, parcel_id: str, owner: str) -> None:
    """Make a parcel the private parcel of ``owner``."""
    parcel = data.parcels[parcel_id]
    for origin in parcel.origins.values():
        origin.owners = (owner,)
    parcel.private = True
    parcel.touch(parcel.updated)


def _offered(
    data: ParcelsData, now: datetime
) -> list[tuple[str, tuple[str, ...], str]]:
    return [
        (s.parcel_id, s.candidates, s.reason) for s in reconcile(data, now).suggestions
    ]


@SHARING
def test_order_package_guess_keeps_a_private_package_apart(
    owner: str, merged: bool
) -> None:
    """The package picked by its items isn't someone else's private package."""
    data = ParcelsData()
    _apply(data, _amazon("msg:c1#0", ORDER_3, _nov(2, 9), _eta(5), items=[LAMP]))
    mug = _apply(
        data,
        _amazon(
            "msg:s2#0", ORDER_3, _nov(4, 10, 25), _eta(4), items=[MUG], private=True
        ),
        _nov(4, 12),
    )

    applied = apply_contribution(
        data,
        _amazon(
            "msg:s1#0",
            ORDER_3,
            _nov(4, 0, 40),
            _eta(6),
            shipment_id="DkSHIP0003",
            items=[MUG],
            owner=owner,
        ),
        _nov(4, 12),
    )

    assert (applied.parcel_id == mug) is merged
    if merged:
        assert applied.auto_merged == REASON_SAME_ORDER
        return
    assert applied.created
    assert data.engine["held_guesses"] == [
        [["msg:s2#0"], ["msg:s1#0"], REASON_SAME_ORDER]
    ]
    assert _offered(data, _nov(4, 13)) == [
        (str(applied.parcel_id), (mug,), REASON_SAME_ORDER)
    ]
    assert data.parcels[mug].state.amazon_shipment_ids == ()


@SHARING
def test_carrier_mail_of_the_order_keeps_a_private_parcel_apart(
    owner: str, merged: bool
) -> None:
    """A carrier's e-mail naming the order isn't put in someone's private parcel."""
    data = ParcelsData()
    shipped = _apply(
        data,
        _amazon(
            "msg:a1#0",
            ORDER_1,
            _nov(3, 9),
            _eta(5),
            shipment_id="DkSHIP0001",
            private=True,
        ),
    )
    carrier = contribution(
        "msg:c1#0",
        kind=MailKind.IN_TRANSIT,
        time=_nov(4, 9),
        carrier="ctt_expresso",
        number=CTT_1,
        merchant="Amazon",
        orders=[ORDER_1],
        label="cttexpresso.pt",
        owner=owner,
    )

    applied = apply_contribution(data, carrier, _nov(4, 9))

    assert (applied.parcel_id == shipped) is merged
    if merged:
        assert applied.auto_merged == REASON_SAME_ORDER
        return
    assert data.engine["held_guesses"] == [
        [["msg:a1#0"], ["msg:c1#0"], REASON_SAME_ORDER]
    ]
    reconcile(data, _nov(4, 10))
    assert len(data.parcels) == 2
    assert data.parcels[shipped].state.tracking_number is None


@SHARING
def test_order_merge_keeps_a_private_parcel_apart(owner: str, merged: bool) -> None:
    """Two parcels of an order are merged only when the owners may share."""
    data = ParcelsData()
    delivered = _apply(
        data,
        _amazon(
            "msg:d1#0",
            ORDER_1,
            _nov(5, 15),
            None,
            kind=MailKind.DELIVERED,
            private=True,
        ),
        _nov(5, 16),
    )
    shipped = _apply(
        data,
        _amazon(
            "msg:s1#0",
            ORDER_1,
            _nov(3, 9),
            _eta(5),
            shipment_id="DkSHIP0001",
            items=[POT],
            owner=owner,
        ),
        _nov(5, 16),
    )
    assert shipped != delivered

    result = reconcile(data, _nov(5, 16))

    if merged:
        assert result.removed == {delivered}
        assert data.parcels[shipped].private
        return
    assert not result.removed
    assert [(s.parcel_id, s.candidates, s.reason) for s in result.suggestions] == [
        (shipped, (delivered,), REASON_SAME_ORDER)
    ]
    assert data.parcels[shipped].state.status is not ParcelStatus.DELIVERED


@SHARING
def test_carrier_delivery_of_the_day_keeps_a_private_parcel_apart(
    owner: str, merged: bool
) -> None:
    """Someone else's order isn't joined to a private delivery of its day."""
    data = ParcelsData()
    sync = _nov(4, 13)
    ctt = _apply(
        data,
        _private(_ctt("msg:c1#0", CTT_1, MailKind.OUT_FOR_DELIVERY, _nov(4, 9, 15))),
        sync,
    )
    assert (
        _apply(
            data,
            _private(_ctt("msg:c2#0", CTT_1, MailKind.DELIVERED, _nov(4, 10, 40))),
            sync,
        )
        == ctt
    )
    amazon = _apply(
        data, _amazon("msg:a1#0", ORDER_1, _nov(4, 2, 5), _eta(4), owner=owner), sync
    )
    assert amazon != ctt

    result = reconcile(data, sync)

    if merged:
        assert result.removed == {amazon}
        return
    assert not result.removed
    assert [
        (s.parcel_id, s.candidates, s.day, s.reason) for s in result.suggestions
    ] == [(ctt, (amazon,), date(2026, 11, 4), REASON_SAME_MERCHANT_DAY)]


@SHARING
def test_shop_shipment_absorbs_no_private_order_of_someone_else(
    owner: str, merged: bool
) -> None:
    """A shop's tracked shipment doesn't absorb someone else's private order."""
    data = ParcelsData()
    order = _apply(data, _private(_shop_order("msg:o1#0", _nov(3, 20, 30))))
    shipment = _apply(data, _of(owner, _shop_gls("msg:g1#0", GLS[0], _nov(4, 17, 40))))
    assert shipment != order

    result = reconcile(data, _nov(4, 19))

    if merged:
        assert result.removed == {order}
        assert data.parcels[shipment].private
        return
    assert not result.removed
    assert [
        (s.parcel_id, s.candidates, s.day, s.reason) for s in result.suggestions
    ] == [(shipment, (order,), None, REASON_SAME_MERCHANT_DOMAIN)]


@SHARING
def test_paack_stem_left_to_a_private_package_is_suggested(
    owner: str, merged: bool
) -> None:
    """The stem joins the one package left only when the owners may share."""
    data = ParcelsData()
    one = _apply(
        data, _private(_paack("msg:p1#0", _nov(3, 8), number=f"{PAACK_STEM}_1"))
    )
    _apply(data, _paack("msg:p2#0", _nov(3, 9), number=f"{PAACK_STEM}_2"))
    stem = _apply(
        data,
        _of(
            owner,
            _paack(
                "msg:p3#0",
                _nov(3, 10),
                reference=PAACK_STEM,
                kind=MailKind.OUT_FOR_DELIVERY,
            ),
        ),
    )
    remove_message(data, "p2", _nov(3, 13))

    result = reconcile(data, _nov(3, 13))

    if merged:
        assert result.removed == {stem}
        return
    assert not result.removed
    assert [(s.parcel_id, s.candidates, s.reason) for s in result.suggestions] == [
        (one, (stem,), REASON_SAME_REFERENCE)
    ]


@SHARING
def test_amazon_tracking_carries_no_private_shipment_of_someone_else(
    owner: str, merged: bool
) -> None:
    """A carrier's package doesn't take someone else's private shipment."""
    data = ParcelsData()
    one, two, first, second = _two_paack_boxes(data)
    _make_private(data, first, owner)

    result = reconcile(data, _jun(10, 22))

    if merged:
        assert result.removed == {first, second}
        assert data.parcels[one].private
        return
    assert result.removed == {second}
    assert [(s.parcel_id, s.candidates, s.reason) for s in result.suggestions] == [
        (one, (first,), REASON_AMAZON_TRACKING)
    ]
    assert data.parcels[one].state.amazon_shipment_ids == ()
    assert data.parcels[two].state.amazon_shipment_ids == (SHIPMENT_2,)
