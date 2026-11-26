"""A parcel added by hand under the shop's order number joins the order."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from custom_components.parcels.const import MailKind, ParcelStatus
from custom_components.parcels.dedup import (
    Contribution,
    apply_contribution,
    join_keys,
    mark_delivered,
    update_parcel,
)
from custom_components.parcels.models import Origin, ParcelEvent, ParcelsData, Source
from custom_components.parcels.parsers.base import Eta

from .factories import T0, at, contribution

ORDER = "001234567890"
OTHER_ORDER = "009876543210"
SHOP = "Leroy Merlin"
CTT_NUMBER = "RR123456785PT"
OTHER_CTT_NUMBER = "RR102030405PT"
LOOSE_NUMBER = "KX20481632"
ETA = Eta(start=date(2026, 11, 6), end=date(2026, 11, 6))


def typed(
    name: str,
    number: str = ORDER,
    *,
    time: datetime = T0,
    carrier: str | None = None,
    merchant: str | None = SHOP,
) -> Contribution:
    """Build a parcel the user adds by hand, as the add action does."""
    origin = Origin(
        id=f"man:p_{name}",
        source=Source.MANUAL,
        time=time,
        carrier=carrier,
        tracking_number=number,
        merchant=merchant,
        owners=("person.one",),
        confirmed=True,
    )
    event = ParcelEvent(
        time=time,
        source=Source.MANUAL,
        origin=origin.id,
        status=ParcelStatus.SHIPPED,
        kind=MailKind.SHIPPED,
    )
    return Contribution(origin=origin, events=[event])


def shop_mail(
    name: str,
    *,
    time: datetime,
    orders: tuple[str, ...] = (ORDER,),
    eta: Eta | None = None,
    carrier: str | None = None,
    number: str | None = None,
    merchant: str = SHOP,
    attach_only: bool = False,
) -> Contribution:
    """Build the shop's e-mail that its order has shipped."""
    return contribution(
        f"msg:{name}#0",
        time=time,
        carrier=carrier,
        number=number,
        merchant=merchant,
        orders=orders,
        eta=eta,
        attach_only=attach_only,
    )


def add_typed(data: ParcelsData, *, eta: Eta | None = None, **kwargs: object) -> str:
    """Add a parcel by hand, then type its expected day, as he did."""
    parcel_id = apply_contribution(data, typed("a", **kwargs), T0).parcel_id  # type: ignore[arg-type]
    assert parcel_id is not None
    if eta is not None:
        update_parcel(data, parcel_id, {"eta_start": eta.start.isoformat()}, T0)
    return parcel_id


@pytest.mark.parametrize("attach_only", [False, True])
@pytest.mark.parametrize("eta", [None, ETA])
def test_shop_mail_joins_the_parcel_typed_under_its_order(
    attach_only: bool, eta: Eta | None
) -> None:
    """The order's e-mail joins it surely: not a guess the user must check.

    The typed number is the order's, so the parcel has no tracking number.
    """
    data = ParcelsData()
    parcel_id = add_typed(data, eta=eta)

    applied = apply_contribution(
        data,
        shop_mail("shop", time=at(days=1), eta=ETA, attach_only=attach_only),
        at(days=1),
    )

    assert applied.parcel_id == parcel_id
    assert not applied.created
    assert applied.auto_merged is None
    assert list(data.parcels) == [parcel_id]
    parcel = data.parcels[parcel_id]
    assert parcel.auto_merged is None
    state = parcel.state
    assert state.typed_number == ORDER
    assert state.typed_order
    assert state.tracking_number is None
    assert state.carrier is None
    assert state.tracking_url is None
    assert state.order_numbers == (ORDER,)
    assert state.eta == ETA
    assert state.status is ParcelStatus.SHIPPED


@pytest.mark.parametrize("eta", [None, ETA])
def test_parcel_typed_under_an_order_number_joins_the_order(eta: Eta | None) -> None:
    """Typed after the order's e-mail came, the number joins its parcel."""
    data = ParcelsData()
    order = apply_contribution(data, shop_mail("shop", time=T0, eta=eta), T0)

    applied = apply_contribution(data, typed("a", time=at(hours=1)), at(hours=1))

    assert applied.parcel_id == order.parcel_id
    assert not applied.created
    assert applied.auto_merged is None
    assert list(data.parcels) == [order.parcel_id]
    state = data.parcels[order.parcel_id].state
    assert state.typed_order
    assert state.tracking_number is None
    assert state.merchant == SHOP


def order_package(
    name: str,
    item: str,
    *,
    time: datetime = T0,
    number: str | None = None,
) -> Contribution:
    """Build the shop's e-mail about one package of the order."""
    return contribution(
        f"msg:{name}#0",
        time=time,
        carrier="ctt" if number else None,
        number=number,
        merchant=SHOP,
        orders=(ORDER,),
        items=(item,),
    )


def test_typed_number_joins_the_order_s_only_open_parcel() -> None:
    """A package of the order already delivered isn't the one typed."""
    data = ParcelsData()
    lamp = apply_contribution(data, order_package("lamp", "Candeeiro de mesa"), T0)
    chair = apply_contribution(
        data,
        order_package(
            "chair", "Cadeira de jardim", time=at(hours=1), number=CTT_NUMBER
        ),
        at(hours=1),
    )
    assert chair.parcel_id != lamp.parcel_id
    apply_contribution(
        data,
        contribution(
            "msg:chair-done#0",
            kind=MailKind.DELIVERED,
            time=at(hours=2),
            carrier="ctt",
            number=CTT_NUMBER,
        ),
        at(hours=2),
    )

    applied = apply_contribution(data, typed("a", time=at(hours=3)), at(hours=3))

    assert applied.parcel_id == lamp.parcel_id
    assert applied.auto_merged is None
    assert len(data.parcels) == 2


def test_typed_number_joins_no_parcel_when_the_order_has_several_open() -> None:
    """The number can't tell which of the order's open packages it is."""
    data = ParcelsData()
    lamp = apply_contribution(data, order_package("lamp", "Candeeiro de mesa"), T0)
    chair = apply_contribution(
        data, order_package("chair", "Cadeira de jardim", time=at(hours=1)), at(hours=1)
    )
    assert chair.parcel_id != lamp.parcel_id

    applied = apply_contribution(data, typed("a", time=at(hours=2)), at(hours=2))

    assert applied.created
    assert len(data.parcels) == 3
    assert data.parcels[applied.parcel_id].state.tracking_number == ORDER


@pytest.mark.parametrize("carrier", ["ctt", "dhl"])
def test_number_typed_with_a_carrier_stays_a_tracking_number(carrier: str) -> None:
    """The user said whose number it is, so it isn't taken for the order's."""
    data = ParcelsData()
    parcel_id = add_typed(data, carrier=carrier)

    applied = apply_contribution(data, shop_mail("shop", time=at(days=1)), at(days=1))

    assert applied.parcel_id != parcel_id
    state = data.parcels[parcel_id].state
    assert state.tracking_number == ORDER
    assert state.carrier == carrier
    assert state.typed_number is None
    assert not state.typed_order


def test_number_typed_with_other_carrier_is_the_order_s() -> None:
    """The carrier "Other" says nothing about whose number it is."""
    data = ParcelsData()
    parcel_id = add_typed(data, carrier="other")

    applied = apply_contribution(data, shop_mail("shop", time=at(days=1)), at(days=1))

    assert applied.parcel_id == parcel_id
    assert data.parcels[parcel_id].state.typed_order
    assert data.parcels[parcel_id].state.tracking_number is None
    assert data.parcels[parcel_id].state.carrier == "other"


@pytest.mark.parametrize("carrier", [None, "other"])
def test_carrier_number_replaces_the_typed_order_number(carrier: str | None) -> None:
    """The order's shipment with a tracking number is the parcel typed.

    Its carrier is the shipment's, though the user chose "Other".
    """
    data = ParcelsData()
    parcel_id = add_typed(data, carrier=carrier)

    applied = apply_contribution(
        data,
        shop_mail("shop", time=at(days=1), carrier="ctt", number=CTT_NUMBER),
        at(days=1),
    )

    assert applied.parcel_id == parcel_id
    assert applied.auto_merged is None
    state = data.parcels[parcel_id].state
    assert state.typed_order
    assert state.tracking_number == CTT_NUMBER
    assert state.carrier == "ctt"
    assert state.tracking_url is not None


def test_second_package_of_the_order_stays_apart() -> None:
    """Once the parcel has the carrier's number, another number is another one."""
    data = ParcelsData()
    parcel_id = add_typed(data)
    first = apply_contribution(
        data,
        shop_mail("first", time=at(days=1), carrier="ctt", number=CTT_NUMBER),
        at(days=1),
    )
    second = apply_contribution(
        data,
        shop_mail(
            "second",
            time=at(days=1, hours=1),
            carrier="ctt",
            number=OTHER_CTT_NUMBER,
        ),
        at(days=1, hours=1),
    )

    assert first.parcel_id == parcel_id
    assert second.parcel_id != parcel_id
    assert data.parcels[parcel_id].state.tracking_number == CTT_NUMBER
    assert data.parcels[second.parcel_id].state.tracking_number == OTHER_CTT_NUMBER


@pytest.mark.parametrize(
    ("orders", "merchant", "number"),
    [
        ((OTHER_ORDER,), SHOP, ORDER),
        (("10012",), "Loja Exemplo", "10012"),
    ],
    ids=["other-order", "other-shop-s-short-order"],
)
def test_typed_number_stays_a_tracking_number_for_other_orders(
    orders: tuple[str, ...], merchant: str, number: str
) -> None:
    """Another order's e-mail neither joins the parcel nor drops its number."""
    data = ParcelsData()
    parcel_id = add_typed(data, number=number)

    applied = apply_contribution(
        data,
        shop_mail("shop", time=at(days=1), orders=orders, merchant=merchant),
        at(days=1),
    )

    assert applied.parcel_id != parcel_id
    state = data.parcels[parcel_id].state
    assert state.tracking_number == number
    assert not state.typed_order


def test_number_a_carrier_names_stays_the_tracking_number() -> None:
    """A carrier's e-mail with the number makes it a tracking number for sure."""
    data = ParcelsData()
    parcel_id = add_typed(data)
    apply_contribution(
        data,
        contribution("msg:carrier#0", time=at(hours=1), number=ORDER),
        at(hours=1),
    )

    apply_contribution(data, shop_mail("shop", time=at(days=1)), at(days=1))

    state = data.parcels[parcel_id].state
    assert state.typed_number is None
    assert state.tracking_number == ORDER


def test_typed_order_number_is_a_join_key() -> None:
    """Keys of a typed number include its order, so others' orders are refused."""
    data = ParcelsData()
    parcel_id = add_typed(data)

    keys = join_keys(data.parcels[parcel_id])

    assert ("number", ORDER) in keys
    assert ("order", f"ord:{ORDER}") in keys


def test_number_typed_on_the_order_s_parcel_stays_its_tracking_number() -> None:
    """A number that isn't the order's is the parcel's own.

    Another shipment of the order, with another number, is another parcel.
    """
    data = ParcelsData()
    parcel_id = apply_contribution(data, shop_mail("shop", time=T0), T0).parcel_id
    assert parcel_id is not None
    update_parcel(data, parcel_id, {"tracking_number": LOOSE_NUMBER}, at(hours=1))
    state = data.parcels[parcel_id].state
    assert state.tracking_number == LOOSE_NUMBER
    assert not state.typed_order

    applied = apply_contribution(
        data,
        shop_mail("ctt", time=at(days=1), carrier="ctt", number=CTT_NUMBER),
        at(days=1),
    )

    assert applied.parcel_id != parcel_id
    assert data.parcels[parcel_id].state.tracking_number == LOOSE_NUMBER


def test_parcel_typed_and_delivered_takes_no_new_shipment() -> None:
    """As for one known only from its order, a new number is another package."""
    data = ParcelsData()
    parcel_id = add_typed(data)
    mark_delivered(data, parcel_id, at(hours=1))

    applied = apply_contribution(
        data,
        shop_mail("ctt", time=at(days=1), carrier="ctt", number=CTT_NUMBER),
        at(days=1),
    )

    assert applied.parcel_id != parcel_id
    state = data.parcels[parcel_id].state
    assert state.status is ParcelStatus.DELIVERED
    assert state.tracking_number == ORDER


def test_order_number_read_as_a_tracking_number_joins_nothing() -> None:
    """Only a number typed by hand is taken for the order's."""
    data = ParcelsData()
    order = apply_contribution(data, shop_mail("shop", time=T0), T0)

    applied = apply_contribution(
        data,
        contribution("msg:misread#0", time=at(hours=1), number=ORDER, merchant=SHOP),
        at(hours=1),
    )

    assert applied.created
    assert applied.parcel_id != order.parcel_id


@pytest.mark.parametrize(
    ("carrier", "joins"), [(None, True), ("other", True), ("ctt", False)]
)
def test_number_typed_with_a_carrier_joins_no_order(
    carrier: str | None, joins: bool
) -> None:
    """The user said whose number it is, unless they chose "Other"."""
    data = ParcelsData()
    order = apply_contribution(data, shop_mail("shop", time=T0), T0)

    applied = apply_contribution(
        data, typed("a", time=at(hours=1), carrier=carrier), at(hours=1)
    )

    assert (applied.parcel_id == order.parcel_id) is joins
    assert len(data.parcels) == (1 if joins else 2)


@pytest.mark.parametrize("typed_first", [True, False])
def test_number_in_a_carrier_s_format_stays_a_tracking_number(
    typed_first: bool,
) -> None:
    """Even with "Other", a number in a carrier's format is a tracking number."""
    data = ParcelsData()
    order_mail = shop_mail("shop", time=at(hours=1), orders=(CTT_NUMBER,))
    if typed_first:
        parcel_id = add_typed(data, number=CTT_NUMBER, carrier="other")
        applied = apply_contribution(data, order_mail, at(hours=1))
    else:
        apply_contribution(data, order_mail, at(hours=1))
        applied = apply_contribution(
            data,
            typed("a", number=CTT_NUMBER, time=at(hours=2), carrier="other"),
            at(hours=2),
        )
        parcel_id = applied.parcel_id
        assert parcel_id is not None

    assert applied.created
    assert len(data.parcels) == 2
    state = data.parcels[parcel_id].state
    assert state.typed_number is None
    assert state.tracking_number == CTT_NUMBER


def test_typed_number_a_carrier_named_joins_the_carrier_s_parcel() -> None:
    """A number a carrier's e-mail has is that parcel's, not the order's."""
    data = ParcelsData()
    carrier = apply_contribution(
        data, contribution("msg:carrier#0", time=T0, number=ORDER), T0
    )
    order = apply_contribution(data, shop_mail("shop", time=at(hours=1)), at(hours=1))
    assert order.parcel_id != carrier.parcel_id

    applied = apply_contribution(data, typed("a", time=at(hours=2)), at(hours=2))

    assert applied.parcel_id == carrier.parcel_id
    assert len(data.parcels) == 2
