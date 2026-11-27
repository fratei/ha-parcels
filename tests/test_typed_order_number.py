"""A parcel added by hand under the shop's order number joins the order."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from custom_components.parcels.const import MailKind, ParcelStatus
from custom_components.parcels.dedup import (
    HELD_GUESSES,
    REASON_SAME_ORDER,
    Contribution,
    MergeSuggestion,
    accept_suggestion,
    apply_contribution,
    join_keys,
    keep_apart,
    mark_delivered,
    reconcile,
    split_parcel,
    undo_auto_merge,
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
    private: bool = False,
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
    return Contribution(origin=origin, events=[event], private=private)


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
    assert pairs(reconcile(data, at(hours=3)).suggestions) == {
        (lamp.parcel_id, applied.parcel_id),
        (chair.parcel_id, applied.parcel_id),
    }
    assert len(data.parcels) == 3


def pairs(suggestions: list[MergeSuggestion]) -> set[tuple[str, str]]:
    """Return the same-order suggestions as (order's parcel, typed parcel)."""
    assert all(item.reason == REASON_SAME_ORDER for item in suggestions)
    return {
        (item.parcel_id, candidate)
        for item in suggestions
        for candidate in item.candidates
    }


@pytest.mark.parametrize("merchant", [SHOP, None])
def test_typed_number_joins_the_order_s_parcel_with_the_carrier_s_number(
    merchant: str | None,
) -> None:
    """The order's only open parcel is the one typed, numbered or not (W17).

    A long order number names its order without the shop.
    """
    data = ParcelsData()
    order = apply_contribution(
        data, shop_mail("ctt", time=T0, carrier="ctt", number=CTT_NUMBER), T0
    )

    applied = apply_contribution(
        data, typed("a", time=at(hours=1), merchant=merchant), at(hours=1)
    )

    assert applied.parcel_id == order.parcel_id
    assert not applied.created
    assert applied.auto_merged is None
    assert list(data.parcels) == [order.parcel_id]
    parcel = data.parcels[order.parcel_id]
    assert parcel.auto_merged is None
    state = parcel.state
    assert state.typed_order
    assert state.tracking_number == CTT_NUMBER
    assert state.carrier == "ctt"
    assert state.merchant == SHOP
    assert not reconcile(data, at(hours=2)).suggestions


def test_typed_number_is_suggested_for_each_of_the_order_s_open_parcels() -> None:
    """With several open packages, the user says which one he typed."""
    data = ParcelsData()
    lamp = apply_contribution(data, order_package("lamp", "Candeeiro de mesa"), T0)
    chair = apply_contribution(
        data,
        order_package(
            "chair", "Cadeira de jardim", time=at(hours=1), number=CTT_NUMBER
        ),
        at(hours=1),
    )
    applied = apply_contribution(data, typed("a", time=at(hours=2)), at(hours=2))
    assert applied.created
    typed_id = applied.parcel_id
    assert typed_id is not None

    assert pairs(reconcile(data, at(hours=3)).suggestions) == {
        (lamp.parcel_id, typed_id),
        (chair.parcel_id, typed_id),
    }
    merged = accept_suggestion(data, chair.parcel_id, typed_id, at(hours=4))

    assert merged.id == chair.parcel_id
    assert set(data.parcels) == {lamp.parcel_id, chair.parcel_id}
    assert merged.state.typed_order
    assert merged.state.tracking_number == CTT_NUMBER
    assert not reconcile(data, at(hours=5)).suggestions


def chair_delivered(data: ParcelsData, time: datetime) -> None:
    """Have the carrier deliver the order's numbered package."""
    apply_contribution(
        data,
        contribution(
            "msg:chair-done#0",
            kind=MailKind.DELIVERED,
            time=time,
            carrier="ctt",
            number=CTT_NUMBER,
        ),
        time,
    )


def test_typed_parcel_kept_apart_from_one_package_isn_t_the_other_s() -> None:
    """Kept apart from one of two open packages, it stays apart (F32).

    The order still has two open parcels, so the user says which. Once the
    other is delivered, it's the order's only open parcel: a guess.
    """
    data = ParcelsData()
    lamp = apply_contribution(data, order_package("lamp", "Candeeiro de mesa"), T0)
    chair = apply_contribution(
        data,
        order_package(
            "chair", "Cadeira de jardim", time=at(hours=1), number=CTT_NUMBER
        ),
        at(hours=1),
    )
    applied = apply_contribution(data, typed("a", time=at(hours=2)), at(hours=2))
    typed_id = applied.parcel_id
    assert applied.created
    assert typed_id is not None
    assert lamp.parcel_id is not None
    assert chair.parcel_id is not None
    keep_apart(data, data.parcels[chair.parcel_id], data.parcels[typed_id])

    result = reconcile(data, at(hours=3))

    assert set(data.parcels) == {lamp.parcel_id, chair.parcel_id, typed_id}
    assert pairs(result.suggestions) == {(lamp.parcel_id, typed_id)}

    chair_delivered(data, at(hours=4))
    result = reconcile(data, at(hours=5))

    assert set(data.parcels) == {lamp.parcel_id, chair.parcel_id}
    assert typed_id in result.removed
    merged = data.parcels[lamp.parcel_id].auto_merged
    assert merged is not None
    assert merged.reason == REASON_SAME_ORDER


def test_number_edited_to_the_order_s_kept_apart_from_one_package_stays() -> None:
    """An edit doesn't make it the other open package's either (F32)."""
    data = ParcelsData()
    lamp = apply_contribution(data, order_package("lamp", "Candeeiro de mesa"), T0)
    chair = apply_contribution(
        data,
        order_package(
            "chair", "Cadeira de jardim", time=at(hours=1), number=CTT_NUMBER
        ),
        at(hours=1),
    )
    typed_id = add_typed(data, number=LOOSE_NUMBER)
    assert lamp.parcel_id is not None
    assert chair.parcel_id is not None
    assert len(data.parcels) == 3
    keep_apart(data, data.parcels[chair.parcel_id], data.parcels[typed_id])

    update_parcel(data, typed_id, {"tracking_number": ORDER}, at(hours=2))

    assert set(data.parcels) == {lamp.parcel_id, chair.parcel_id, typed_id}
    assert data.parcels[typed_id].state.tracking_number == ORDER
    assert pairs(reconcile(data, at(hours=3)).suggestions) == {
        (lamp.parcel_id, typed_id)
    }


def test_reconcile_joins_a_typed_parcel_left_apart_to_the_order_s() -> None:
    """A parcel typed before Parcels joined such numbers joins on upgrade.

    It's a guess the user can undo; undone, it's no longer suggested.
    """
    data = ParcelsData()
    order = apply_contribution(
        data, shop_mail("ctt", time=T0, carrier="ctt", number=CTT_NUMBER), T0
    )
    alone = ParcelsData()
    typed_id = apply_contribution(
        alone, typed("a", time=at(hours=1)), at(hours=1)
    ).parcel_id
    assert typed_id is not None
    data.parcels[typed_id] = alone.parcels[typed_id]

    result = reconcile(data, at(hours=2))

    assert list(data.parcels) == [order.parcel_id]
    assert typed_id in result.removed
    parcel = data.parcels[order.parcel_id]
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_ORDER
    assert parcel.state.typed_order
    assert parcel.state.tracking_number == CTT_NUMBER

    assert undo_auto_merge(data, order.parcel_id, at(hours=3)) is not None
    assert len(data.parcels) == 2
    assert not reconcile(data, at(hours=4)).suggestions
    assert len(data.parcels) == 2


def test_typed_parcel_kept_apart_from_the_order_s_is_left_alone() -> None:
    """Once the user kept them apart, neither a merge nor a suggestion."""
    data = ParcelsData()
    order = apply_contribution(
        data, shop_mail("ctt", time=T0, carrier="ctt", number=CTT_NUMBER), T0
    )
    alone = ParcelsData()
    typed_id = apply_contribution(
        alone, typed("a", time=at(hours=1)), at(hours=1)
    ).parcel_id
    assert typed_id is not None
    data.parcels[typed_id] = alone.parcels[typed_id]
    assert order.parcel_id is not None
    keep_apart(data, data.parcels[order.parcel_id], data.parcels[typed_id])

    assert not reconcile(data, at(hours=2)).suggestions
    assert len(data.parcels) == 2


@pytest.mark.parametrize("by", ["add", "edit"])
def test_typed_parcel_split_off_stays_apart_from_the_next_mail(by: str) -> None:
    """Split… moves a typed parcel and the order's apart for good.

    The shop's next e-mail with the carrier's number joins the order's
    parcel, not the typed one too.
    """
    data = ParcelsData()
    apply_contribution(
        data, shop_mail("ctt", time=T0, carrier="ctt", number=CTT_NUMBER), T0
    )
    if by == "add":
        joined = apply_contribution(data, typed("a", time=at(hours=1)), at(hours=1))
        parcel_id, moving = joined.parcel_id, ["man:p_a"]
    else:
        parcel_id, moving = add_typed(data, number=LOOSE_NUMBER), ["msg:ctt#0"]
        update_parcel(data, parcel_id, {"tracking_number": ORDER}, at(hours=1))
    assert parcel_id is not None
    assert list(data.parcels) == [parcel_id]
    new = split_parcel(data, parcel_id, moving, at(hours=2))
    tracked, typed_id = (parcel_id, new.id) if by == "add" else (new.id, parcel_id)

    later = apply_contribution(
        data,
        shop_mail("later", time=at(hours=3), carrier="ctt", number=CTT_NUMBER),
        at(hours=3),
    )

    assert later.parcel_id == tracked
    assert not later.merged
    assert "msg:later#0" not in data.parcels[typed_id].origins
    assert not reconcile(data, at(hours=4)).suggestions
    assert set(data.parcels) == {tracked, typed_id}


def test_private_typed_parcel_is_only_suggested_for_someone_else_s_order() -> None:
    """A private parcel takes nobody else's e-mails: the user decides."""
    data = ParcelsData()
    order = apply_contribution(
        data,
        contribution(
            "msg:ctt#0",
            time=T0,
            carrier="ctt",
            number=CTT_NUMBER,
            merchant=SHOP,
            orders=(ORDER,),
            owner="person.two",
        ),
        T0,
    )

    applied = apply_contribution(
        data, typed("a", time=at(hours=1), private=True), at(hours=1)
    )

    assert applied.created
    assert len(data.parcels) == 2
    assert data.engine.get(HELD_GUESSES)
    result = reconcile(data, at(hours=2))
    assert len(data.parcels) == 2
    assert [(s.parcel_id, s.candidates) for s in result.suggestions] == [
        (order.parcel_id, (applied.parcel_id,))
    ]
    assert result.suggestions[0].reason == REASON_SAME_ORDER


def test_shop_typed_later_joins_the_parcel_to_its_order() -> None:
    """A short order number names its order only with the shop (F26)."""
    data = ParcelsData()
    typed_id = add_typed(data, number="869685", merchant=None)
    order = apply_contribution(
        data, shop_mail("shop", time=at(hours=1), orders=("869685",)), at(hours=1)
    )
    assert order.parcel_id != typed_id

    update_parcel(data, typed_id, {"merchant": SHOP}, at(hours=2))

    assert list(data.parcels) == [typed_id]
    parcel = data.parcels[typed_id]
    assert parcel.auto_merged is None
    assert parcel.state.typed_order
    assert parcel.state.tracking_number is None

    applied = apply_contribution(
        data,
        shop_mail(
            "ctt",
            time=at(days=1),
            orders=("869685",),
            carrier="ctt",
            number=CTT_NUMBER,
        ),
        at(days=1),
    )

    assert applied.parcel_id == typed_id
    assert applied.auto_merged is None
    assert data.parcels[typed_id].state.tracking_number == CTT_NUMBER


@pytest.mark.parametrize("numbered", [False, True])
def test_number_edited_to_the_order_s_joins_the_order_s_parcel(
    numbered: bool,
) -> None:
    """An edit gets the same join as an add (F26)."""
    data = ParcelsData()
    order = apply_contribution(
        data,
        shop_mail(
            "shop",
            time=T0,
            carrier="ctt" if numbered else None,
            number=CTT_NUMBER if numbered else None,
        ),
        T0,
    )
    typed_id = add_typed(data, number=LOOSE_NUMBER)
    assert order.parcel_id != typed_id

    update_parcel(data, typed_id, {"tracking_number": ORDER}, at(hours=1))

    assert list(data.parcels) == [typed_id]
    parcel = data.parcels[typed_id]
    assert parcel.auto_merged is None
    state = parcel.state
    assert state.typed_order
    assert state.tracking_number == (CTT_NUMBER if numbered else None)


def test_order_number_typed_for_a_parcel_with_its_own_number_keeps_it() -> None:
    """A number the user typed for the order's parcel stays its tracking number."""
    data = ParcelsData()
    parcel_id = apply_contribution(data, shop_mail("shop", time=T0), T0).parcel_id
    assert parcel_id is not None
    update_parcel(data, parcel_id, {"tracking_number": LOOSE_NUMBER}, at(hours=1))

    applied = apply_contribution(data, typed("a", time=at(hours=2)), at(hours=2))

    assert applied.parcel_id == parcel_id
    state = data.parcels[parcel_id].state
    assert state.typed_order
    assert state.tracking_number == LOOSE_NUMBER


@pytest.mark.parametrize(
    ("number", "carrier"),
    [(CTT_NUMBER, "ctt"), (LOOSE_NUMBER, "dpd"), (None, "ctt")],
)
def test_order_number_added_keeps_what_was_typed_with_a_carrier(
    number: str | None, carrier: str
) -> None:
    """Adding the order's number keeps the number and carrier the user typed
    for the order's parcel (F29).

    The carrier is that number's, or the parcel's, not the order number's.
    """
    data = ParcelsData()
    parcel_id = apply_contribution(data, shop_mail("shop", time=T0), T0).parcel_id
    assert parcel_id is not None
    changes: dict[str, str] = {"carrier": carrier}
    if number is not None:
        changes["tracking_number"] = number
    update_parcel(data, parcel_id, changes, at(hours=1))

    applied = apply_contribution(data, typed("a", time=at(hours=2)), at(hours=2))

    assert applied.parcel_id == parcel_id
    state = data.parcels[parcel_id].state
    assert state.typed_order
    assert state.typed_number == ORDER
    assert state.tracking_number == number
    assert state.carrier == carrier


def test_order_number_typed_again_with_its_carrier_stays_a_tracking_number() -> None:
    """A number the user typed with a carrier stays a tracking number when he
    adds it again without one."""
    data = ParcelsData()
    parcel_id = add_typed(data, carrier="dpd")
    apply_contribution(data, shop_mail("shop", time=at(hours=1)), at(hours=1))

    applied = apply_contribution(data, typed("b", time=at(hours=2)), at(hours=2))

    assert applied.parcel_id == parcel_id
    state = data.parcels[parcel_id].state
    assert state.tracking_number == ORDER
    assert state.carrier == "dpd"
    assert state.typed_number is None


@pytest.mark.parametrize("edited", [False, True])
def test_carrier_typed_after_the_join_keeps_the_order_number_apart(
    edited: bool,
) -> None:
    """A carrier typed later doesn't make the order's number a tracking number (F27).

    The number may have been typed when adding the parcel or by editing it.
    """
    data = ParcelsData()
    if edited:
        apply_contribution(data, shop_mail("shop", time=T0), T0)
        parcel_id = add_typed(data, number=LOOSE_NUMBER)
        update_parcel(data, parcel_id, {"tracking_number": ORDER}, at(hours=1))
    else:
        parcel_id = add_typed(data)
        apply_contribution(data, shop_mail("shop", time=at(hours=1)), at(hours=1))
    assert list(data.parcels) == [parcel_id]
    assert data.parcels[parcel_id].state.typed_order

    update_parcel(data, parcel_id, {"carrier": "dpd"}, at(hours=2))

    state = data.parcels[parcel_id].state
    assert state.typed_order
    assert state.tracking_number is None
    assert state.carrier == "dpd"

    update_parcel(data, parcel_id, {"tracking_number": CTT_NUMBER}, at(hours=3))

    state = data.parcels[parcel_id].state
    assert state.tracking_number == CTT_NUMBER
    assert state.carrier == "dpd"
    assert not state.typed_order


def test_carrier_typed_for_a_parcel_alone_makes_its_number_a_tracking_number() -> None:
    """Not known as the order's, the number is the carrier's once one is typed."""
    data = ParcelsData()
    parcel_id = add_typed(data)

    update_parcel(data, parcel_id, {"carrier": "dpd"}, at(hours=1))

    state = data.parcels[parcel_id].state
    assert state.typed_number is None
    assert state.tracking_number == ORDER
    assert state.carrier == "dpd"


def test_carrier_changed_on_a_number_typed_with_one_keeps_it_a_tracking_number() -> (
    None
):
    """A number typed with a carrier was never the order's."""
    data = ParcelsData()
    parcel_id = add_typed(data, carrier="dpd")
    apply_contribution(data, shop_mail("shop", time=at(hours=1)), at(hours=1))
    assert len(data.parcels) == 2

    update_parcel(data, parcel_id, {"carrier": "gls"}, at(hours=2))

    state = data.parcels[parcel_id].state
    assert state.tracking_number == ORDER
    assert state.carrier == "gls"
    assert not state.typed_order
    assert len(data.parcels) == 2


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
