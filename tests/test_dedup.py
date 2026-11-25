"""Tests for deduplication: every parcel appears once."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import dataclasses
from datetime import date, datetime, time
import json

import pytest

from custom_components.parcels.const import MailKind, ParcelStatus
from custom_components.parcels.convert import fill_contribution
from custom_components.parcels.dedup import (
    REASON_SAME_MERCHANT_ETA,
    REASON_SAME_NUMBER,
    REASON_SAME_REFERENCE,
    Contribution,
    DedupError,
    accept_suggestion,
    add_owner,
    add_owner_to,
    amazon_shipment_id_counts,
    apply_contribution,
    archive_parcel,
    dismiss_suggestion,
    find_parcels_by_number,
    fold_known_orders,
    keep_apart,
    mark_delivered,
    merge_parcels,
    order_parcels,
    parcel_order_keys,
    reconcile,
    remove_message,
    remove_owner_from,
    restore_cancellations,
    split_parcel,
    undo_auto_merge,
    update_parcel,
)
from custom_components.parcels.models import (
    Origin,
    ParcelEvent,
    ParcelsData,
    Source,
    Suggestion,
)
from custom_components.parcels.parsers.base import Eta

from .factories import T0, at, contribution

S = ParcelStatus
AMAZON_ORDER = "405-1234567-1234567"
DPD = "05212345678901"


def _eta(start: int, end: int | None = None) -> Eta:
    return Eta(start=date(2026, 11, start), end=date(2026, 11, end or start))


def test_split_order() -> None:
    """One order shipped as two parcels: the first absorbs the order e-mail."""
    data = ParcelsData()
    order = apply_contribution(
        data,
        contribution(
            "msg:o1#0", kind=MailKind.ORDER, merchant="Amazon.es", orders=[AMAZON_ORDER]
        ),
        T0,
    )
    assert order.created
    assert data.parcels[order.parcel_id].state.provisional

    first = apply_contribution(
        data,
        contribution(
            "msg:s1#0",
            time=at(days=1),
            carrier="amazon",
            number="TBA123456789012",
            merchant="Amazon.es",
            orders=[AMAZON_ORDER],
        ),
        at(days=1),
    )
    assert first.parcel_id == order.parcel_id
    assert not first.created

    second = apply_contribution(
        data,
        contribution(
            "msg:s2#0",
            time=at(days=2),
            carrier="ctt",
            number="RR123456785PT",
            merchant="Amazon.es",
            orders=[AMAZON_ORDER],
        ),
        at(days=2),
    )
    assert second.created
    assert len(data.parcels) == 2
    key = f"ord:{AMAZON_ORDER.replace('-', '')}"
    assert list(data.orders) == [key]
    assert {p.id for p in order_parcels(data, key)} == set(data.parcels)
    assert all(not p.state.provisional for p in data.parcels.values())


def test_consolidated_shipment() -> None:
    """Two orders in one box: their parcels become one."""
    data = ParcelsData()
    for number in ("#1001", "#1002"):
        apply_contribution(
            data,
            contribution(
                f"msg:{number}#0",
                kind=MailKind.ORDER,
                merchant="Example Shop",
                orders=[number],
            ),
            T0,
        )
    assert len(data.parcels) == 2

    shipped = apply_contribution(
        data,
        contribution(
            "msg:ship#0",
            time=at(days=1),
            carrier="gls",
            number="12345678901",
            merchant="Example Shop",
            orders=["#1001", "#1002"],
        ),
        at(days=1),
    )
    assert len(shipped.merged) == 1
    assert list(data.parcels) == [shipped.parcel_id]
    parcel = data.parcels[shipped.parcel_id]
    assert parcel_order_keys(parcel) == {"ord:exampleshop:1001", "ord:exampleshop:1002"}
    assert parcel.state.status is S.SHIPPED
    assert set(data.orders) == {"ord:exampleshop:1001", "ord:exampleshop:1002"}


def test_same_email_in_two_mailboxes() -> None:
    """The same e-mail found by two people is applied once."""
    data = ParcelsData()
    first = apply_contribution(
        data, contribution("msg:m#0", carrier="dpd", number=DPD, owner="person.one"), T0
    )
    second = apply_contribution(
        data, contribution("msg:m#0", carrier="dpd", number=DPD, owner="person.two"), T0
    )
    assert first.parcel_id == second.parcel_id
    parcel = data.parcels[first.parcel_id]
    assert len(parcel.events) == 1
    assert parcel.state.owners == ("person.one", "person.two")

    assert add_owner(data, "m", "person.three", T0) == {parcel.id}
    assert "person.three" in data.parcels[parcel.id].state.owners


def test_out_of_order_emails() -> None:
    """The delivery e-mail arrives before the shipping e-mail."""
    data = ParcelsData()
    delivered = apply_contribution(
        data,
        contribution(
            "msg:d#0",
            kind=MailKind.DELIVERED,
            time=at(days=2),
            carrier="dpd",
            number=DPD,
        ),
        at(days=2),
    )
    shipped = apply_contribution(
        data,
        contribution(
            "msg:s#0", time=at(), carrier="dpd", number="0521 2345 6789 01", eta=_eta(4)
        ),
        at(days=2, hours=1),
    )
    assert shipped.parcel_id == delivered.parcel_id
    state = data.parcels[delivered.parcel_id].state
    assert state.status is S.DELIVERED
    assert state.delivered_at == at(days=2)
    assert len(state.timeline) == 2


def test_carriers_of_one_family_share_numbers() -> None:
    """CTT Expresso and CTT use the same number for the same parcel."""
    data = ParcelsData()
    first = apply_contribution(
        data,
        contribution("msg:a#0", carrier="ctt_expresso", number="1234567890123"),
        T0,
    )
    second = apply_contribution(
        data,
        contribution(
            "msg:b#0", kind=MailKind.IN_TRANSIT, carrier="ctt", number="1234567890123"
        ),
        T0,
    )
    assert first.parcel_id == second.parcel_id
    assert second.auto_merged is None


def test_agency_slash_does_not_split_a_parcel() -> None:
    """Nacex writes "agency/number" in text and drops the slash in links."""
    data = ParcelsData()
    first = apply_contribution(
        data, contribution("msg:a#0", carrier="nacex", number="2834/71520946"), T0
    )
    second = apply_contribution(
        data,
        contribution(
            "msg:b#0", kind=MailKind.IN_TRANSIT, carrier="nacex", number="283471520946"
        ),
        T0,
    )
    assert first.parcel_id == second.parcel_id
    assert second.auto_merged is None
    assert [p.id for p in find_parcels_by_number(data, "2834 / 71520946")] == [
        first.parcel_id
    ]


def test_international_postal_numbers_cross_carriers() -> None:
    """An S10 number keeps its identity when the carrier changes at the border."""
    data = ParcelsData()
    first = apply_contribution(
        data, contribution("msg:a#0", carrier="cainiao", number="RR123456785CN"), T0
    )
    second = apply_contribution(
        data,
        contribution(
            "msg:b#0",
            kind=MailKind.OUT_FOR_DELIVERY,
            time=at(days=9),
            carrier="ctt",
            number="RR123456785CN",
        ),
        at(days=9),
    )
    assert second.parcel_id == first.parcel_id
    assert second.auto_merged is None
    state = data.parcels[first.parcel_id].state
    assert state.carrier == "ctt"
    assert state.status is S.OUT_FOR_DELIVERY


def test_unknown_carrier_attaches_without_flag() -> None:
    """A number without a carrier joins the parcel that has it."""
    data = ParcelsData()
    first = apply_contribution(
        data, contribution("msg:a#0", carrier="dpd", number=DPD), T0
    )
    second = apply_contribution(data, contribution("msg:b#0", number=DPD), T0)
    assert second.parcel_id == first.parcel_id
    assert second.auto_merged is None
    assert data.parcels[first.parcel_id].state.carrier == "dpd"


def test_same_long_number_other_carrier_is_flagged_and_undone() -> None:
    """The same long number from unrelated carriers is linked, but flagged."""
    data = ParcelsData()
    first = apply_contribution(
        data, contribution("msg:a#0", carrier="dpd", number=DPD), T0
    )
    second = apply_contribution(
        data, contribution("msg:b#0", carrier="gls", number=DPD), at(hours=1)
    )
    assert second.parcel_id == first.parcel_id
    assert second.auto_merged == REASON_SAME_NUMBER
    parcel = data.parcels[first.parcel_id]
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.origin == "msg:b#0"

    split_off = undo_auto_merge(data, parcel.id, at(hours=2))
    assert split_off is not None
    assert set(split_off.origins) == {"msg:b#0"}
    assert parcel.auto_merged is None
    assert set(parcel.origins) == {"msg:a#0"}
    assert len(data.parcels) == 2
    assert {p.id for p in find_parcels_by_number(data, DPD)} == set(data.parcels)


def test_short_numbers_of_other_carriers_stay_apart() -> None:
    """Short numbers are too common to link across carriers."""
    data = ParcelsData()
    apply_contribution(
        data, contribution("msg:a#0", carrier="mrw", number="12345678"), T0
    )
    apply_contribution(
        data, contribution("msg:b#0", carrier="nacex", number="12345678"), T0
    )
    assert len(data.parcels) == 2


def test_amazon_shipment_id_links() -> None:
    """Amazon e-mails about one shipment meet on the shipment ID."""
    data = ParcelsData()
    first = apply_contribution(
        data, contribution("msg:a#0", merchant="Amazon.es", shipment_id="DkXyz1234"), T0
    )
    second = apply_contribution(
        data,
        contribution(
            "msg:b#0",
            kind=MailKind.OUT_FOR_DELIVERY,
            merchant="Amazon.es",
            shipment_id=" DkXyz1234 ",
            carrier="amazon",
            number="TBA123456789012",
        ),
        at(days=1),
    )
    assert second.parcel_id == first.parcel_id
    assert data.parcels[first.parcel_id].state.amazon_shipment_ids == ("DkXyz1234",)


# Made up: an Amazon order sent in boxes of one shipment, with CTT numbers.
BOXES_ORDER = "406-7654321-7654321"
BOXES = "Hq4Wn7Pz2"
BOX_ONE, BOX_TWO, BOX_THREE = "RR102030405PT", "RR102030419PT", "RR102030422PT"


def _box(
    origin_id: str,
    shipment: str | None,
    number: str | None = None,
    *,
    hours: float = 0,
    kind: MailKind = MailKind.SHIPPED,
) -> Contribution:
    """Build Amazon's e-mail about a box of the order BOXES_ORDER."""
    return contribution(
        origin_id,
        kind=kind,
        time=at(hours=hours),
        label="amazon.es",
        merchant="Amazon.es",
        orders=[BOXES_ORDER],
        shipment_id=shipment,
        carrier="ctt" if number else None,
        number=number,
    )


def _ctt(
    origin_id: str, number: str, *, hours: float = 0, kind: MailKind
) -> Contribution:
    """Build CTT's e-mail about a package."""
    return contribution(
        origin_id, kind=kind, time=at(hours=hours), carrier="ctt", number=number
    )


def _apply(data: ParcelsData, *items: Contribution) -> list[str]:
    """Apply e-mails in order, then reconcile as a check does."""
    ids = []
    for item in items:
        applied = apply_contribution(data, item, item.origin.time)
        assert applied.parcel_id is not None
        ids.append(applied.parcel_id)
    reconcile(data, max(item.origin.time for item in items))
    return ids


def _holder(data: ParcelsData, number: str) -> str:
    """Return the only parcel with a number."""
    [parcel] = find_parcels_by_number(data, number)
    return parcel.id


@pytest.mark.parametrize("second", [BOXES, f"{BOXES}#1"])
@pytest.mark.parametrize("reverse", [False, True])
def test_boxes_of_a_shipment_stay_apart(second: str, reverse: bool) -> None:
    """Boxes of one Amazon shipment with their own numbers are two parcels.

    Whether or not the e-mails tell the boxes apart, and in any order:
    different tracking numbers are never one parcel, and delivering one box
    delivers only that one.
    """
    data = ParcelsData()
    boxes = [
        _box("msg:b1#0", BOXES, BOX_ONE, hours=1),
        _box("msg:b2#0", second, BOX_TWO, hours=2),
    ]
    _apply(
        data,
        _box("msg:o#0", None, kind=MailKind.ORDER),
        *(reversed(boxes) if reverse else boxes),
    )
    assert len(data.parcels) == 2
    one, two = _holder(data, BOX_ONE), _holder(data, BOX_TWO)
    assert one != two

    _apply(data, _ctt("msg:c#0", BOX_ONE, hours=24, kind=MailKind.DELIVERED))

    assert len(data.parcels) == 2
    assert data.parcels[one].state.status is S.DELIVERED
    assert data.parcels[two].state.status is S.SHIPPED


def test_boxes_without_numbers_stay_apart() -> None:
    """Boxes told apart by their index are two parcels before their numbers."""
    data = ParcelsData()
    first, second = _apply(
        data, _box("msg:b1#0", BOXES), _box("msg:b2#0", f"{BOXES}#1", hours=1)
    )
    assert first != second
    assert data.parcels[first].state.amazon_shipment_ids == (BOXES,)
    assert data.parcels[second].state.amazon_shipment_ids == (f"{BOXES}#1",)


def test_box_news_without_number_joins_its_box() -> None:
    """News about a box without its number joins the box with the number.

    The shipment ID links them while only one number is known for it.
    """
    data = ParcelsData()
    first, numbered, again = _apply(
        data,
        _box("msg:b1#0", BOXES),
        _box("msg:b2#0", BOXES, BOX_ONE, hours=1),
        _box("msg:b3#0", BOXES, hours=2, kind=MailKind.OUT_FOR_DELIVERY),
    )
    assert first == numbered == again
    assert len(data.parcels) == 1


def test_box_with_another_number_is_another_parcel() -> None:
    """A box with another number never joins a box with its number.

    Even when news without a number linked the shipment to the first box.
    """
    data = ParcelsData()
    first, _, other = _apply(
        data,
        _box("msg:b1#0", BOXES),
        _box("msg:b2#0", BOXES, BOX_ONE, hours=1),
        _box("msg:b3#0", BOXES, BOX_TWO, hours=2),
    )
    assert first != other
    assert _holder(data, BOX_ONE) == first
    assert _holder(data, BOX_TWO) == other


def test_box_number_joins_carrier_and_shipment() -> None:
    """Amazon's e-mail with the box's number joins the carrier's package and
    the shipment's news without a number."""
    data = ParcelsData()
    carrier, shipment, joined = _apply(
        data,
        _ctt("msg:c#0", BOX_ONE, kind=MailKind.IN_TRANSIT),
        _box("msg:b1#0", BOXES, hours=1),
        _box("msg:b2#0", BOXES, BOX_ONE, hours=2),
    )
    assert carrier != shipment
    assert len(data.parcels) == 1
    assert joined in (carrier, shipment)


def test_box_number_never_joins_another_box() -> None:
    """Amazon's e-mail with a box's number joins that box's package only,
    never a box of the shipment with another number."""
    data = ParcelsData()
    carrier, other, _ = _apply(
        data,
        _ctt("msg:c#0", BOX_ONE, kind=MailKind.IN_TRANSIT),
        _box("msg:b1#0", BOXES, hours=1),
        _box("msg:b2#0", BOXES, BOX_TWO, hours=2),
    )
    joined = apply_contribution(
        data, _box("msg:b3#0", BOXES, BOX_ONE, hours=3), at(hours=3)
    )
    assert joined.parcel_id == carrier
    assert _holder(data, BOX_TWO) == other
    assert len(data.parcels) == 2


def test_shipment_news_never_joins_two_boxes() -> None:
    """News about a shipment without a number joins none of two boxes with
    their own numbers, so it never makes them one."""
    data = ParcelsData()
    _apply(
        data,
        _box("msg:b1#0", BOXES, BOX_ONE),
        _box("msg:b2#0", BOXES, BOX_TWO, hours=1),
        _box("msg:b3#0", BOXES, hours=2, kind=MailKind.OUT_FOR_DELIVERY),
    )
    assert _holder(data, BOX_ONE) != _holder(data, BOX_TWO)


def test_boxes_merged_before_can_be_split() -> None:
    """Boxes of one shipment merged by an older version can be split, and
    stay apart; a shipment's news without a number can't leave its box."""
    data = ParcelsData()
    first = apply_contribution(data, _box("msg:b1#0", BOXES, BOX_ONE), T0)
    second = apply_contribution(
        data, _box("msg:b2#0", BOXES, BOX_TWO, hours=1), at(hours=1)
    )
    news = apply_contribution(data, _box("msg:b3#0", BOXES, hours=2), at(hours=2))
    assert first.parcel_id is not None
    assert second.parcel_id is not None
    if first.parcel_id != second.parcel_id:
        merge_parcels(data, first.parcel_id, [second.parcel_id], at(hours=3))
    if news.parcel_id not in (None, first.parcel_id):
        merge_parcels(data, first.parcel_id, [news.parcel_id], at(hours=3))
    assert list(data.parcels) == [first.parcel_id]

    with pytest.raises(DedupError, match="shared_shipment"):
        split_parcel(data, first.parcel_id, ["msg:b3#0"], at(hours=4))
    new = split_parcel(data, first.parcel_id, ["msg:b2#0"], at(hours=4))

    assert set(new.origins) == {"msg:b2#0"}
    _apply(data, _box("msg:b4#0", BOXES, BOX_TWO, hours=5, kind=MailKind.IN_TRANSIT))
    assert _holder(data, BOX_TWO) == new.id
    assert _holder(data, BOX_ONE) == first.parcel_id


def test_split_shared_shipment() -> None:
    """News about a shipment without a number stays with its box."""
    data = ParcelsData()
    [parcel_id, _] = _apply(
        data,
        _box("msg:b1#0", BOXES),
        _box("msg:b2#0", BOXES, BOX_ONE, hours=1),
    )
    with pytest.raises(DedupError, match="shared_shipment"):
        split_parcel(data, parcel_id, ["msg:b1#0"], at(hours=2))


def test_box_with_its_number_joins_whatever_carrier() -> None:
    """Amazon's e-mails about a box with the same number are one parcel,
    whatever carriers they name: not a guess, and not to be split apart."""
    data = ParcelsData()
    box = {
        "label": "amazon.es",
        "merchant": "Amazon.es",
        "orders": [BOXES_ORDER],
        "shipment_id": BOXES,
        "number": DPD,
    }
    first = apply_contribution(data, contribution("msg:b1#0", carrier="dpd", **box), T0)
    second = apply_contribution(
        data,
        contribution("msg:b2#0", time=at(hours=1), carrier="gls", **box),
        at(hours=1),
    )
    assert second.parcel_id == first.parcel_id
    assert second.auto_merged is None
    assert first.parcel_id is not None
    with pytest.raises(DedupError, match="shared_shipment"):
        split_parcel(data, first.parcel_id, ["msg:b2#0"], at(hours=2))


def test_undoing_a_guess_takes_its_box_news() -> None:
    """Undoing a guess on a box's number takes Amazon's news about that box
    along, though the news has no number."""
    data = ParcelsData()
    carrier = apply_contribution(
        data, contribution("msg:d#0", carrier="dpd", number=DPD), T0
    )
    guessed = apply_contribution(
        data,
        contribution(
            "msg:b1#0",
            time=at(hours=1),
            label="amazon.es",
            merchant="Amazon.es",
            orders=[BOXES_ORDER],
            shipment_id=BOXES,
            carrier="gls",
            number=DPD,
        ),
        at(hours=1),
    )
    news = apply_contribution(
        data, _box("msg:b2#0", BOXES, hours=2, kind=MailKind.IN_TRANSIT), at(hours=2)
    )
    assert carrier.parcel_id is not None
    assert guessed.parcel_id == news.parcel_id == carrier.parcel_id
    assert guessed.auto_merged == REASON_SAME_NUMBER

    split_off = undo_auto_merge(data, carrier.parcel_id, at(hours=3))

    assert split_off is not None
    assert set(split_off.origins) == {"msg:b1#0", "msg:b2#0"}
    assert set(data.parcels[carrier.parcel_id].origins) == {"msg:d#0"}


def test_box_news_read_again_joins_no_other_box() -> None:
    """News about a shipment without a number, read again, goes back to its
    parcel and joins no box with a number that parcel doesn't have."""
    data = ParcelsData()
    carrier, box = _apply(
        data,
        _ctt("msg:c#0", BOX_ONE, kind=MailKind.IN_TRANSIT),
        _box("msg:b2#0", BOXES, BOX_TWO, hours=1),
    )
    assert carrier != box
    news = dataclasses.replace(
        _box("msg:b3#0", BOXES, hours=2, kind=MailKind.OUT_FOR_DELIVERY),
        parcel=carrier,
    )

    applied = apply_contribution(data, news, at(hours=2))

    assert applied.parcel_id == carrier
    assert set(data.parcels) == {carrier, box}
    assert "msg:b3#0" in data.parcels[carrier].origins
    assert _holder(data, BOX_TWO) == box


# Made up: an Amazon shipment ID, and the Paack order ID of its first package.
SHIPMENT = "Rb5Lq2Vm7"
PAACK_ID = f"{SHIPMENT}_1"
PAACK_BARCODE = "534000088812345678"


@pytest.mark.parametrize("paack_eta", [None, _eta(5)])
@pytest.mark.parametrize("paack_first", [False, True])
def test_paack_order_id_is_not_an_amazon_shipment(
    paack_first: bool, paack_eta: Eta | None
) -> None:
    """Paack's order ID isn't Amazon's shipment ID, even when it looks so.

    Only the same expected day joins them, as a guess the user can undo.
    """
    data = ParcelsData()
    amazon = contribution(
        "msg:a#0",
        merchant="Amazon.es",
        orders=[AMAZON_ORDER],
        shipment_id=SHIPMENT,
        eta=_eta(5),
    )
    paack = contribution(
        "msg:p#0",
        kind=MailKind.IN_TRANSIT,
        carrier="paack",
        number=PAACK_ID,
        merchant="Amazon",
        eta=paack_eta,
    )
    first, second = (paack, amazon) if paack_first else (amazon, paack)
    apply_contribution(data, first, T0)
    joined = apply_contribution(data, second, at(hours=1))

    if paack_eta is None:
        assert joined.created
    else:
        assert joined.auto_merged == REASON_SAME_MERCHANT_ETA
        undo_auto_merge(data, joined.parcel_id, at(days=1))
    assert len(data.parcels) == 2


def test_paack_barcode_joins_amazon() -> None:
    """Amazon's number for a Paack parcel is the label barcode Paack scans."""
    data = ParcelsData()
    amazon = apply_contribution(
        data,
        contribution(
            "msg:a#0",
            merchant="Amazon.es",
            shipment_id=SHIPMENT,
            carrier="paack",
            number=PAACK_BARCODE,
        ),
        T0,
    )
    paack = apply_contribution(
        data,
        contribution(
            "msg:p#0",
            kind=MailKind.OUT_FOR_DELIVERY,
            carrier="paack",
            number=PAACK_BARCODE,
        ),
        at(hours=1),
    )
    assert paack.parcel_id == amazon.parcel_id
    assert paack.auto_merged is None


def test_amazon_shipment_id_counts() -> None:
    """Amazon's e-mails of the last 30 days are counted per site by whether
    they gave a shipment ID, with the IDs' shapes and never their values.

    Order e-mails never link a shipment, so they're counted apart.
    """
    data = ParcelsData()
    amazon = {"label": "amazon.es", "merchant": "Amazon.es"}
    sent = [
        contribution(
            "msg:a1#0", kind=MailKind.ORDER, orders=("402-1234567-1234567",), **amazon
        ),
        contribution("msg:a2#0", shipment_id=SHIPMENT, **amazon),
        contribution(
            "msg:a3#0", kind=MailKind.DELIVERED, shipment_id="Kp7Ws2Xd9", **amazon
        ),
        contribution("msg:a4#0", kind=MailKind.OUT_FOR_DELIVERY, **amazon),
        contribution(
            "msg:a5#0",
            label="marketplace.amazon.de",
            merchant="Amazon.de",
            shipment_id="DX4512345678",
        ),
        # Older than 30 days.
        contribution("msg:a6#0", time=at(days=-31), shipment_id="old0shape", **amazon),
        # A shipment's second box: the shape is the shipment ID's.
        contribution("msg:a7#0", shipment_id="Tg3Hs8Jq5#1", **amazon),
        # Paack's e-mail about an Amazon parcel isn't Amazon's.
        contribution(
            "msg:p1#0",
            label="paack.co",
            merchant="Amazon",
            carrier="paack",
            number=PAACK_ID,
        ),
        contribution(
            "msg:s1#0",
            label="casa-exemplo.pt",
            merchant="Casa Exemplo",
            number="1Z999AA10123456784",
        ),
    ]
    for index, item in enumerate(sent):
        apply_contribution(data, item, at(hours=index))

    counts = amazon_shipment_id_counts(data, at(days=1))

    assert counts == {
        "amazon.de": {
            "orders": 0,
            "with_id": 1,
            "without_id": 0,
            "shapes": {"len12:A0": 1},
        },
        "amazon.es": {
            "orders": 1,
            "with_id": 3,
            "without_id": 1,
            "shapes": {"len9:Aa0": 3},
        },
    }
    assert SHIPMENT not in json.dumps(counts)


def _paack(
    origin_id: str,
    *,
    hours: float = 0,
    kind: MailKind = MailKind.IN_TRANSIT,
    number: str | None = None,
    reference: str | None = None,
) -> Contribution:
    """Paack's e-mail about a parcel from Amazon."""
    return contribution(
        origin_id,
        kind=kind,
        time=at(hours=hours),
        carrier="paack",
        number=number,
        reference=reference,
        merchant="Amazon",
        label="paack.co",
    )


@pytest.mark.parametrize("stem_first", [False, True])
def test_paack_stem_joins_its_package(stem_first: bool) -> None:
    """An e-mail with only the part of Paack's ID before "_" joins its package."""
    data = ParcelsData()
    package = _paack("msg:p1#0", number=PAACK_ID)
    stem = _paack("msg:p2#0", hours=1, kind=MailKind.DELIVERED, reference=SHIPMENT)
    first, second = (stem, package) if stem_first else (package, stem)
    apply_contribution(data, first, at(hours=2))
    joined = apply_contribution(data, second, at(hours=3))

    [parcel] = data.parcels.values()
    assert joined.auto_merged is None
    assert parcel.auto_merged is None
    assert parcel.state.tracking_number == PAACK_ID
    assert parcel.state.status is S.DELIVERED
    assert parcel.state.references == (SHIPMENT,)


def test_paack_stem_of_two_packages_stays_apart() -> None:
    """With two open packages of the shipment, the stem doesn't tell which."""
    data = ParcelsData()
    one = apply_contribution(data, _paack("msg:p1#0", number=PAACK_ID), T0)
    two = apply_contribution(
        data, _paack("msg:p2#0", hours=1, number=f"{SHIPMENT}_2"), at(hours=1)
    )
    stem = apply_contribution(
        data,
        _paack("msg:p3#0", hours=2, kind=MailKind.OUT_FOR_DELIVERY, reference=SHIPMENT),
        at(hours=2),
    )
    assert stem.created
    again = apply_contribution(
        data,
        _paack("msg:p4#0", hours=3, kind=MailKind.DELIVERED, reference=SHIPMENT),
        at(hours=3),
    )
    assert again.parcel_id == stem.parcel_id
    assert again.auto_merged is None
    assert len(data.parcels) == 3
    for package in (one, two):
        assert data.parcels[package.parcel_id].state.status is S.IN_TRANSIT

    # A third package of the shipment doesn't take the stem's e-mails either.
    three = apply_contribution(
        data, _paack("msg:p5#0", hours=4, number=f"{SHIPMENT}_3"), at(hours=4)
    )
    assert three.created
    assert data.parcels[stem.parcel_id].state.tracking_number is None


def test_paack_stem_prefers_the_open_package() -> None:
    """Of two packages, one delivered, a stem's news is about the open one."""
    data = ParcelsData()
    done = apply_contribution(
        data, _paack("msg:p1#0", kind=MailKind.DELIVERED, number=PAACK_ID), T0
    )
    open_ = apply_contribution(
        data, _paack("msg:p2#0", hours=1, number=f"{SHIPMENT}_2"), at(hours=1)
    )
    stem = apply_contribution(
        data,
        _paack("msg:p3#0", hours=2, kind=MailKind.OUT_FOR_DELIVERY, reference=SHIPMENT),
        at(hours=2),
    )
    assert stem.parcel_id == open_.parcel_id
    assert stem.auto_merged == REASON_SAME_REFERENCE
    assert data.parcels[open_.parcel_id].state.status is S.OUT_FOR_DELIVERY
    assert data.parcels[done.parcel_id].state.status is S.DELIVERED
    undo_auto_merge(data, open_.parcel_id, at(hours=3))
    assert len(data.parcels) == 3


def test_paack_stem_is_not_an_amazon_shipment() -> None:
    """Paack's ID isn't Amazon's shipment ID, even when they look alike."""
    data = ParcelsData()
    amazon = apply_contribution(
        data,
        contribution(
            "msg:a#0",
            merchant="Amazon.es",
            orders=[AMAZON_ORDER],
            shipment_id=SHIPMENT,
            eta=_eta(5),
        ),
        T0,
    )
    stem = apply_contribution(
        data,
        _paack("msg:p#0", hours=1, kind=MailKind.DELIVERED, reference=SHIPMENT),
        at(hours=1),
    )
    assert stem.created
    assert stem.parcel_id != amazon.parcel_id
    assert len(data.parcels) == 2
    parcel = data.parcels[amazon.parcel_id]
    assert parcel.state.status is not S.DELIVERED
    assert parcel.state.order_numbers == (AMAZON_ORDER,)


@pytest.mark.parametrize("orders", [(), ("1001",)])
def test_shipment_references_of_a_shop(orders: tuple[str, ...]) -> None:
    """A shop's shipment reference joins its e-mails and keeps others apart."""
    data = ParcelsData()

    def shop(origin_id: str, reference: str, hours: float, kind: MailKind) -> str:
        applied = apply_contribution(
            data,
            contribution(
                origin_id,
                kind=kind,
                time=at(hours=hours),
                merchant="Casa Exemplo",
                orders=orders,
                reference=reference,
                eta=_eta(5),
            ),
            at(hours=hours),
        )
        assert applied.parcel_id
        assert applied.auto_merged is None
        return applied.parcel_id

    first = shop("msg:l1#0", "1111111111", 0, MailKind.SHIPPED)
    second = shop("msg:l2#0", "2222222222", 1, MailKind.OUT_FOR_DELIVERY)
    assert second != first
    assert shop("msg:l3#0", "1111111111", 2, MailKind.DELIVERED) == first
    assert data.parcels[first].state.references == ("1111111111",)
    assert data.parcels[first].state.status is S.DELIVERED
    assert data.parcels[second].state.status is S.OUT_FOR_DELIVERY


def test_same_merchant_and_dates_is_flagged() -> None:
    """A shop e-mail without a number joins the one parcel that fits."""
    data = ParcelsData()
    tracked = apply_contribution(
        data,
        contribution(
            "msg:a#0",
            carrier="dpd",
            number=DPD,
            merchant="Example Shop",
            eta=_eta(5, 6),
        ),
        T0,
    )
    shop = apply_contribution(
        data,
        contribution(
            "msg:b#0",
            kind=MailKind.IN_TRANSIT,
            merchant="example shop",
            eta=_eta(6),
            owner="person.two",
        ),
        at(hours=3),
    )
    assert shop.parcel_id == tracked.parcel_id
    assert shop.auto_merged == REASON_SAME_MERCHANT_ETA

    assert undo_auto_merge(data, tracked.parcel_id, at(hours=4)) is not None
    assert len(data.parcels) == 2


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        # Two parcels fit: no guess.
        ({"carrier": "gls", "number": "12345678901"}, 3),
        # Different order numbers: not the same parcel.
        ({"orders": ["#2002"]}, 2),
    ],
)
def test_heuristic_needs_one_compatible_candidate(
    other: dict[str, object], expected: int
) -> None:
    """The merchant heuristic only links when exactly one parcel fits."""
    data = ParcelsData()
    apply_contribution(
        data,
        contribution(
            "msg:a#0",
            carrier="dpd",
            number=DPD,
            merchant="Example Shop",
            orders=["#1001"],
            eta=_eta(5, 6),
        ),
        T0,
    )
    if "number" in other:
        apply_contribution(
            data,
            contribution(
                "msg:c#0",
                carrier=str(other["carrier"]),
                number=str(other["number"]),
                merchant="Example Shop",
                eta=_eta(6),
            ),
            T0,
        )
    apply_contribution(
        data,
        contribution(
            "msg:b#0",
            kind=MailKind.IN_TRANSIT,
            merchant="Example Shop",
            orders=other.get("orders", ()),  # type: ignore[arg-type]
            eta=_eta(6),
        ),
        T0,
    )
    assert len(data.parcels) == expected


def test_cancellations() -> None:
    """Cancelling applies to orders that haven't shipped."""
    data = ParcelsData()
    nothing = apply_contribution(
        data,
        contribution(
            "msg:c#0", kind=MailKind.CANCELLED, merchant="Example Shop", orders=["#1"]
        ),
        T0,
    )
    assert nothing.parcel_id is None
    assert not data.parcels

    ordered = apply_contribution(
        data,
        contribution(
            "msg:o#0", kind=MailKind.ORDER, merchant="Example Shop", orders=["#2"]
        ),
        T0,
    )
    cancelled = apply_contribution(
        data,
        contribution(
            "msg:x#0",
            kind=MailKind.CANCELLED,
            time=at(hours=1),
            merchant="Example Shop",
            orders=["#2"],
        ),
        at(hours=1),
    )
    assert cancelled.parcel_id == ordered.parcel_id
    assert data.parcels[ordered.parcel_id].state.status is S.CANCELLED

    shipped = apply_contribution(
        data,
        contribution(
            "msg:s#0", carrier="dpd", number=DPD, merchant="Example Shop", orders=["#3"]
        ),
        T0,
    )
    late = apply_contribution(
        data,
        contribution(
            "msg:y#0",
            kind=MailKind.CANCELLED,
            time=at(hours=2),
            merchant="Example Shop",
            orders=["#3"],
        ),
        at(hours=2),
    )
    assert late.parcel_id == shipped.parcel_id
    assert data.parcels[shipped.parcel_id].state.status is S.SHIPPED


AI_READ_ORDER = "402-0000000-1111111"


def _ai_reads_order(data: ParcelsData) -> str:
    """Apply the local AI's reading of an order e-mail as in transit."""
    applied = apply_contribution(
        data,
        contribution(
            "msg:o#0",
            kind=MailKind.IN_TRANSIT,
            merchant="Amazon",
            orders=[AI_READ_ORDER],
            items=["Desk lamp"],
            source=Source.AI,
        ),
        T0,
    )
    assert applied.parcel_id is not None
    return applied.parcel_id


def _order_news(
    data: ParcelsData, origin_id: str, kind: MailKind, **kwargs: object
) -> str | None:
    """Apply an Amazon e-mail about the order, a day after it was placed."""
    return apply_contribution(
        data,
        contribution(
            origin_id,
            kind=kind,
            time=at(hours=24),
            merchant="Amazon",
            orders=[AI_READ_ORDER],
            **kwargs,  # type: ignore[arg-type]
        ),
        at(hours=24),
    ).parcel_id


def _cancel(data: ParcelsData) -> str | None:
    return apply_contribution(
        data,
        contribution(
            "msg:x#0",
            kind=MailKind.CANCELLED,
            time=at(hours=30),
            merchant="Amazon",
            orders=[AI_READ_ORDER],
        ),
        at(hours=30),
    ).parcel_id


def test_cancelling_an_order_the_ai_read_as_shipped() -> None:
    """The AI's reading of the order e-mail isn't news that it shipped."""
    data = ParcelsData()
    pid = _ai_reads_order(data)
    assert data.parcels[pid].state.status is S.IN_TRANSIT
    assert _cancel(data) == pid
    assert data.parcels[pid].state.status is S.CANCELLED


def test_cancelling_after_a_delay_notice() -> None:
    """A delay notice about the order isn't news that it shipped either."""
    data = ParcelsData()
    order = apply_contribution(
        data,
        contribution(
            "msg:o#0", kind=MailKind.ORDER, merchant="Amazon", orders=[AI_READ_ORDER]
        ),
        T0,
    )
    assert _order_news(data, "msg:d#0", MailKind.DELAYED) == order.parcel_id
    assert data.parcels[order.parcel_id].state.status is S.IN_TRANSIT
    assert _cancel(data) == order.parcel_id
    assert data.parcels[order.parcel_id].state.status is S.CANCELLED


def _shipped_mail(data: ParcelsData, pid: str) -> None:
    assert _order_news(data, "msg:s#0", MailKind.SHIPPED) == pid


def _later_ai_reading(data: ParcelsData, pid: str) -> None:
    assert _order_news(data, "msg:a#0", MailKind.IN_TRANSIT, source=Source.AI) == pid


def _ai_names_a_carrier(data: ParcelsData, pid: str) -> None:
    data.parcels[pid].origins["msg:o#0"].carrier = "ctt"


def _parsers_read_it(data: ParcelsData, pid: str) -> None:
    data.parcels[pid].origins["msg:o#0"].source = Source.PARSER


def _delay_of_a_shipment(data: ParcelsData, pid: str) -> None:
    assert (
        _order_news(data, "msg:d#0", MailKind.DELAYED, shipment_id="Rq5TbY8wZ") == pid
    )


def _tracking_number(data: ParcelsData, pid: str) -> None:
    update_parcel(data, pid, {"tracking_number": DPD}, at(hours=24))


def _tracker(data: ParcelsData, pid: str) -> None:
    parcel = data.parcels[pid]
    origin = Origin(id="parcelapp:1", source=Source.PARCELAPP, time=at(hours=24))
    parcel.origins[origin.id] = origin
    parcel.events.append(
        ParcelEvent(
            time=at(hours=24),
            source=Source.PARCELAPP,
            origin=origin.id,
            status=S.IN_TRANSIT,
        )
    )


SHIPPING_NEWS = [
    _shipped_mail,
    _later_ai_reading,
    _ai_names_a_carrier,
    _parsers_read_it,
    _delay_of_a_shipment,
    _tracking_number,
    _tracker,
]


@pytest.mark.parametrize("news", SHIPPING_NEWS)
def test_shipping_news_makes_a_cancellation_partial(
    news: Callable[[ParcelsData, str], None],
) -> None:
    """Once other news says the parcel shipped, a cancellation is partial."""
    data = ParcelsData()
    pid = _ai_reads_order(data)
    news(data, pid)
    assert _cancel(data) == pid
    parcel = data.parcels[pid]
    assert parcel.state.status is not S.CANCELLED
    assert [e.status for e in parcel.events if e.kind is MailKind.CANCELLED] == [None]


def _dropped_cancellation(data: ParcelsData) -> str:
    """Cancel the AI-read order, then drop the status as 0.1.17 did."""
    pid = _ai_reads_order(data)
    assert _cancel(data) == pid
    parcel = data.parcels[pid]
    for event in parcel.events:
        if event.kind is MailKind.CANCELLED:
            event.status = None
    parcel.touch(at(hours=30))
    assert parcel.state.status is S.IN_TRANSIT
    return pid


def _now_ordered(data: ParcelsData, pid: str) -> None:
    """Read the order e-mail with the parsers instead of the AI."""
    assert (
        apply_contribution(
            data,
            contribution(
                "msg:o#0",
                kind=MailKind.ORDER,
                merchant="Amazon",
                orders=[AI_READ_ORDER],
                items=["Desk lamp"],
            ),
            at(hours=40),
        ).parcel_id
        == pid
    )
    assert data.parcels[pid].state.status is S.ORDERED


def _no_news(data: ParcelsData, pid: str) -> None:
    pass


@pytest.mark.parametrize("reading", [_now_ordered, _no_news])
def test_restoring_dropped_cancellations(
    reading: Callable[[ParcelsData, str], None],
) -> None:
    """A cancellation taken for a partial one cancels a parcel that takes it."""
    data = ParcelsData()
    pid = _dropped_cancellation(data)
    reading(data, pid)
    assert restore_cancellations(data, {"o"}, at(hours=41)) == 0
    assert restore_cancellations(data, {"o", "x"}, at(hours=41)) == 1
    parcel = data.parcels[pid]
    assert parcel.state.status is S.CANCELLED
    assert parcel.updated == at(hours=41)
    assert [e.status for e in parcel.events if e.kind is MailKind.CANCELLED] == [
        S.CANCELLED
    ]
    assert restore_cancellations(data, {"o", "x"}, at(hours=42)) == 0
    assert parcel.updated == at(hours=41)


def _delivered(data: ParcelsData, pid: str) -> None:
    mark_delivered(data, pid, at(hours=36))


def _archived(data: ParcelsData, pid: str) -> None:
    _now_ordered(data, pid)
    archive_parcel(data, pid, at(hours=40))


@pytest.mark.parametrize("news", [*SHIPPING_NEWS, _delivered, _archived])
def test_restoring_leaves_partial_cancellations(
    news: Callable[[ParcelsData, str], None],
) -> None:
    """A cancellation stays partial on a shipped, closed or archived parcel."""
    data = ParcelsData()
    pid = _dropped_cancellation(data)
    news(data, pid)
    status = data.parcels[pid].state.status
    assert restore_cancellations(data, {"o", "x"}, at(hours=41)) == 0
    parcel = data.parcels[pid]
    assert parcel.state.status is status
    assert [e.status for e in parcel.events if e.kind is MailKind.CANCELLED] == [None]


def test_restoring_leaves_a_date_the_ai_filled_in() -> None:
    """Only a cancellation gets its status back, not another event without one.

    Here the date the local AI filled in for the parsers' reading of an order.
    """
    data = ParcelsData()
    pid = apply_contribution(
        data,
        contribution(
            "msg:o#0", kind=MailKind.ORDER, merchant="Amazon", orders=[AI_READ_ORDER]
        ),
        T0,
    ).parcel_id
    assert pid is not None
    fill = fill_contribution(
        Suggestion(kind=MailKind.ORDER, eta_start=date(2026, 11, 6)),
        message_hash="o",
        time=T0,
    )
    assert fill is not None
    assert apply_contribution(data, fill, at(hours=1)).parcel_id == pid
    parcel = data.parcels[pid]
    filled = [e for e in parcel.events if e.origin == fill.origin.id]
    assert [e.status for e in filled] == [None]
    assert restore_cancellations(data, {"o"}, at(hours=41)) == 0
    assert parcel.state.status is S.ORDERED
    assert [e.status for e in filled] == [None]


def test_a_later_cancellation_skips_a_cancelled_parcel() -> None:
    """A partial cancellation joins the parcel with its items, not a closed one."""
    data = ParcelsData()
    shipped = apply_contribution(
        data,
        contribution(
            "msg:s#0",
            carrier="dpd",
            number=DPD,
            merchant="Amazon",
            orders=[AI_READ_ORDER],
            items=["Wool hat"],
        ),
        T0,
    ).parcel_id
    lamp = apply_contribution(
        data,
        contribution(
            "msg:o#0",
            kind=MailKind.ORDER,
            merchant="Amazon",
            orders=[AI_READ_ORDER],
            items=["Desk lamp"],
        ),
        T0,
    ).parcel_id
    assert lamp is not None
    assert lamp != shipped
    assert _cancel(data) == lamp
    assert data.parcels[lamp].state.status is S.CANCELLED

    hat = apply_contribution(
        data,
        contribution(
            "msg:y#0",
            kind=MailKind.CANCELLED,
            time=at(hours=36),
            merchant="Amazon",
            orders=[AI_READ_ORDER],
            items=["Wool hat"],
        ),
        at(hours=36),
    )
    assert hat.parcel_id == shipped
    parcel = data.parcels[shipped]
    assert parcel.state.status is S.SHIPPED
    assert [e.status for e in parcel.events if e.kind is MailKind.CANCELLED] == [None]


def test_reapplying_replaces_the_events() -> None:
    """Reprocessing an e-mail doesn't duplicate its events."""
    data = ParcelsData()
    apply_contribution(data, contribution("msg:a#0", carrier="dpd", number=DPD), T0)
    again = apply_contribution(
        data,
        contribution("msg:a#0", kind=MailKind.IN_TRANSIT, carrier="dpd", number=DPD),
        at(hours=1),
    )
    parcel = data.parcels[again.parcel_id]
    assert len(parcel.events) == 1
    assert parcel.state.status is S.IN_TRANSIT


def test_news_brings_back_an_archived_parcel() -> None:
    """Only news that reopens a parcel unarchives it."""
    data = ParcelsData()
    applied = apply_contribution(
        data, contribution("msg:a#0", carrier="dpd", number=DPD), T0
    )
    archive_parcel(data, applied.parcel_id, at(days=31))
    apply_contribution(
        data,
        contribution(
            "msg:b#0",
            kind=MailKind.OUT_FOR_DELIVERY,
            time=at(days=32),
            carrier="dpd",
            number=DPD,
        ),
        at(days=32),
    )
    assert data.parcels[applied.parcel_id].archived is None

    mark_delivered(data, applied.parcel_id, at(days=32, hours=2))
    archive_parcel(data, applied.parcel_id, at(days=50))
    apply_contribution(
        data,
        contribution(
            "msg:c#0",
            kind=MailKind.DELIVERED,
            time=at(days=32, hours=3),
            carrier="dpd",
            number=DPD,
        ),
        at(days=50),
    )
    assert data.parcels[applied.parcel_id].archived == at(days=50)


LAMP = "Candeeiro de mesa Exemplo"
RUG = "Tapete de banho Exemplo"


def _order_mail(
    origin_id: str,
    time: datetime,
    *,
    items: Iterable[str] = (),
    private: bool = False,
) -> Contribution:
    """What an Amazon order's e-mail says: no carrier, no tracking number."""
    return dataclasses.replace(
        contribution(
            origin_id,
            kind=MailKind.ORDER,
            time=time,
            merchant="Amazon.es",
            orders=[AMAZON_ORDER],
            items=items,
            private=private,
        ),
        order_placed=time,
    )


def _delivered_order(data: ParcelsData) -> str:
    """Store an order whose parcel CTT delivered, archived on day 17."""
    parcel_id = apply_contribution(
        data, _order_mail("msg:o#0", T0, items=[LAMP]), T0
    ).parcel_id
    assert parcel_id is not None
    apply_contribution(
        data,
        contribution(
            "msg:d#0",
            kind=MailKind.DELIVERED,
            time=at(days=3),
            carrier="ctt",
            number="RR123456785PT",
            merchant="Amazon.es",
            orders=[AMAZON_ORDER],
        ),
        at(days=3),
    )
    archive_parcel(data, parcel_id, at(days=17))
    return parcel_id


def test_order_mail_joins_the_parcel_put_away() -> None:
    """An order's late e-mail joins its archived parcel and leaves it closed."""
    data = ParcelsData()
    parcel_id = _delivered_order(data)

    for index, items in enumerate(((), (LAMP,))):
        late = at(days=30 + index)
        applied = apply_contribution(
            data, _order_mail(f"msg:late{index}#0", late, items=items), late
        )
        assert (applied.parcel_id, applied.created) == (parcel_id, False)
        assert applied.auto_merged is None

    assert list(data.parcels) == [parcel_id]
    parcel = data.parcels[parcel_id]
    assert parcel.archived == at(days=17)
    assert parcel.state.status is S.DELIVERED
    assert parcel.state.delivered_at == at(days=3)


def test_order_mail_with_other_items_is_another_package() -> None:
    """An order's e-mail with other items still makes a parcel of its own.

    So does each shipment of an order that ships in two.
    """
    data = ParcelsData()
    parcel_id = _delivered_order(data)
    late = at(days=30)

    applied = apply_contribution(
        data, _order_mail("msg:late#0", late, items=[RUG]), late
    )

    assert applied.created
    assert data.parcels[parcel_id].archived == at(days=17)

    data = ParcelsData()
    first, second = (
        apply_contribution(
            data, _order_mail(f"msg:two#{index}", T0, items=[item]), T0
        ).parcel_id
        for index, item in enumerate((LAMP, RUG))
    )
    assert first != second
    assert len(data.parcels) == 2


@pytest.mark.parametrize("archived", [False, True])
def test_order_mail_keeps_an_inferred_delivery(archived: bool) -> None:
    """An order's e-mail isn't news: the delivery Parcels inferred stays."""
    data = ParcelsData()
    parcel_id = apply_contribution(
        data, _order_mail("msg:o#0", T0, items=[LAMP]), T0
    ).parcel_id
    assert parcel_id is not None
    parcel = data.parcels[parcel_id]
    parcel.events.append(
        ParcelEvent(
            time=at(days=3),
            source=Source.PARSER,
            status=S.DELIVERED,
            kind=MailKind.DELIVERED,
            inferred=True,
        )
    )
    parcel.touch(at(days=4))
    if archived:
        archive_parcel(data, parcel_id, at(days=17))
    late = at(days=30)

    applied = apply_contribution(data, _order_mail("msg:late#0", late), late)

    assert applied.parcel_id == parcel_id
    parcel = data.parcels[parcel_id]
    assert parcel.state.status is S.DELIVERED
    assert parcel.state.inferred
    assert parcel.archived == (at(days=17) if archived else None)


def _stray(data: ParcelsData, contribution: Contribution, now: datetime) -> str:
    """Store the parcel that releases before 0.1.16 made of a late e-mail."""
    alone = ParcelsData()
    parcel_id = apply_contribution(alone, contribution, now).parcel_id
    assert parcel_id is not None
    data.parcels[parcel_id] = alone.parcels[parcel_id]
    return parcel_id


def test_fold_known_orders() -> None:
    """Once, the parcel an order's late e-mail made joins the order's parcel.

    That parcel stays archived and delivered; other orders' parcels stay.
    """
    data = ParcelsData()
    parcel_id = _delivered_order(data)
    late = at(days=30)
    stray = _stray(data, _order_mail("msg:late#0", late), late)
    other = apply_contribution(
        data,
        contribution(
            "msg:x#0",
            kind=MailKind.ORDER,
            time=late,
            merchant="Amazon.es",
            orders=["405-7654321-7654321"],
        ),
        late,
    ).parcel_id

    assert fold_known_orders(data, at(days=31)) == 1

    assert set(data.parcels) == {parcel_id, other}
    parcel = data.parcels[parcel_id]
    assert "msg:late#0" in parcel.origins
    assert parcel.archived == at(days=17)
    assert parcel.state.status is S.DELIVERED
    assert stray not in data.parcels
    assert fold_known_orders(data, at(days=31)) == 0


def _confirm(data: ParcelsData, parcel_id: str, earlier: str) -> None:
    for origin in data.parcels[parcel_id].origins.values():
        origin.confirmed = True


def _edit(data: ParcelsData, parcel_id: str, earlier: str) -> None:
    update_parcel(data, parcel_id, {"pickup_point": "Loja Exemplo"}, at(days=30))


def _delay(data: ParcelsData, parcel_id: str, earlier: str) -> None:
    data.parcels[parcel_id].events.append(
        ParcelEvent(time=at(days=30), source=Source.PARSER, kind=MailKind.DELAYED)
    )


def _part(data: ParcelsData, parcel_id: str, earlier: str) -> None:
    keep_apart(data, data.parcels[parcel_id], data.parcels[earlier])


def _older(data: ParcelsData, parcel_id: str, earlier: str) -> None:
    data.parcels[parcel_id].created = at(days=-1)


@pytest.mark.parametrize(
    ("items", "private", "spoil"),
    [
        ([RUG], False, None),
        ([], True, None),
        ([], False, _confirm),
        ([], False, _edit),
        ([], False, _delay),
        ([], False, _part),
        ([], False, _older),
    ],
    ids=[
        "other_items",
        "private",
        "confirmed",
        "edited",
        "news",
        "kept_apart",
        "older",
    ],
)
def test_fold_known_orders_leaves(
    items: list[str],
    private: bool,
    spoil: Callable[[ParcelsData, str, str], None] | None,
) -> None:
    """A parcel stays that the user touched, or that may be another package."""
    data = ParcelsData()
    parcel_id = _delivered_order(data)
    late = at(days=30)
    stray = _stray(
        data, _order_mail("msg:late#0", late, items=items, private=private), late
    )
    if spoil is not None:
        spoil(data, stray, parcel_id)

    assert fold_known_orders(data, at(days=31)) == 0
    assert set(data.parcels) == {parcel_id, stray}


def test_merge_and_split() -> None:
    """The user can merge parcels and split them again."""
    data = ParcelsData()
    a = apply_contribution(data, contribution("msg:a#0", carrier="dpd", number=DPD), T0)
    b = apply_contribution(
        data,
        contribution("msg:b#0", carrier="gls", number="12345678901", private=True),
        at(hours=1),
    )
    b2 = apply_contribution(
        data,
        contribution(
            "msg:b2#0", kind=MailKind.IN_TRANSIT, carrier="gls", number="12345678901"
        ),
        at(hours=2),
    )
    assert b2.parcel_id == b.parcel_id

    merged = merge_parcels(data, a.parcel_id, [b.parcel_id], at(hours=3))
    assert list(data.parcels) == [a.parcel_id]
    assert merged.private
    assert len(merged.events) == 3

    with pytest.raises(DedupError, match="shared_number"):
        split_parcel(data, a.parcel_id, ["msg:b#0"], at(hours=4))
    with pytest.raises(DedupError, match="nothing_left"):
        split_parcel(data, a.parcel_id, list(merged.origins), at(hours=4))
    with pytest.raises(DedupError, match="unknown_origin"):
        split_parcel(data, a.parcel_id, ["msg:zzz#0"], at(hours=4))
    with pytest.raises(DedupError, match="no_origins"):
        split_parcel(data, a.parcel_id, [], at(hours=4))

    new = split_parcel(data, a.parcel_id, ["msg:b#0", "msg:b2#0"], at(hours=4))
    assert set(new.origins) == {"msg:b#0", "msg:b2#0"}
    assert len(new.events) == 2
    assert new.state.status is S.IN_TRANSIT
    assert data.parcels[a.parcel_id].state.tracking_number == DPD


def test_update_parcel() -> None:
    """Edits are kept apart from the e-mails, so they survive reprocessing."""
    data = ParcelsData()
    a = apply_contribution(
        data,
        contribution(
            "msg:a#0",
            merchant="Example Shop",
            kind=MailKind.ORDER,
            orders=["#1"],
            source=Source.AI,
        ),
        T0,
    )
    b = apply_contribution(data, contribution("msg:b#0", carrier="dpd", number=DPD), T0)

    parcel = update_parcel(
        data,
        a.parcel_id,
        {"merchant": None, "eta_start": "2026-11-05", "window_start": "09:00"},
        at(hours=1),
    )
    state = parcel.state
    assert state.merchant is None
    assert state.eta == Eta(date(2026, 11, 5), date(2026, 11, 5), time(9))
    assert state.ai

    update_parcel(data, a.parcel_id, {"confirm": True}, at(hours=2))
    assert not data.parcels[a.parcel_id].state.ai

    update_parcel(data, a.parcel_id, {"eta_start": None}, at(hours=3))
    assert data.parcels[a.parcel_id].state.eta is None

    # Typing the number of another parcel merges the two.
    merged = update_parcel(
        data, a.parcel_id, {"tracking_number": "0521-2345-6789-01"}, at(hours=4)
    )
    assert b.parcel_id not in data.parcels
    assert merged.state.tracking_number == DPD
    assert merged.state.carrier == "dpd"


def test_short_order_recorded_once_merchant_known() -> None:
    """A short order number gets its record when the merchant turns up later."""
    data = ParcelsData()
    edited = apply_contribution(
        data,
        contribution(
            "msg:a#0", carrier="ups", number="1Z999AA10123456784", orders=["1042"]
        ),
        T0,
    )
    mailed = apply_contribution(
        data, contribution("msg:b#0", carrier="dpd", number=DPD, orders=["77"]), T0
    )
    assert not data.orders

    update_parcel(data, edited.parcel_id, {"merchant": "Loja Exemplo"}, at(hours=1))
    apply_contribution(
        data,
        contribution(
            "msg:c#0",
            kind=MailKind.IN_TRANSIT,
            time=at(hours=2),
            carrier="dpd",
            number=DPD,
            merchant="Example Shop",
        ),
        at(hours=2),
    )
    assert set(data.orders) == {"ord:lojaexemplo:1042", "ord:exampleshop:77"}
    assert order_parcels(data, "ord:lojaexemplo:1042") == [
        data.parcels[edited.parcel_id]
    ]
    assert order_parcels(data, "ord:exampleshop:77") == [data.parcels[mailed.parcel_id]]


def test_update_window_with_existing_estimate() -> None:
    """Changing only the time window keeps the date."""
    data = ParcelsData()
    applied = apply_contribution(
        data, contribution("msg:a#0", carrier="dpd", number=DPD, eta=_eta(5)), T0
    )
    parcel = update_parcel(
        data,
        applied.parcel_id,
        {"window_start": "09:00", "window_end": "13:00"},
        at(hours=1),
    )
    eta = parcel.state.eta
    assert eta is not None
    assert (eta.start, eta.window_start.hour, eta.window_end.hour) == (
        date(2026, 11, 5),
        9,
        13,
    )


def test_confirm_merge_clears_flag() -> None:
    """Keeping an automatic merge removes the flag."""
    data = ParcelsData()
    apply_contribution(data, contribution("msg:a#0", carrier="dpd", number=DPD), T0)
    flagged = apply_contribution(
        data, contribution("msg:b#0", carrier="gls", number=DPD), T0
    )
    assert flagged.parcel_id
    update_parcel(data, flagged.parcel_id, {"confirm_merge": True}, at())
    assert data.parcels[flagged.parcel_id].auto_merged is None
    assert len(data.parcels[flagged.parcel_id].origins) == 2


def test_remove_message() -> None:
    """Reprocessing first removes what the e-mail contributed."""
    data = ParcelsData()
    a = apply_contribution(data, contribution("msg:a#0", carrier="dpd", number=DPD), T0)
    apply_contribution(
        data,
        contribution("msg:b#0", kind=MailKind.IN_TRANSIT, carrier="dpd", number=DPD),
        at(hours=1),
    )
    only = apply_contribution(
        data, contribution("msg:c#0", carrier="gls", number="12345678901"), T0
    )

    assert remove_message(data, "b", at(hours=2)) == {a.parcel_id}
    assert data.parcels[a.parcel_id].state.status is S.SHIPPED
    assert remove_message(data, "c", at(hours=2)) == {only.parcel_id}
    assert only.parcel_id not in data.parcels


def test_mark_delivered_from_any_status() -> None:
    """The user can always mark a parcel delivered."""
    data = ParcelsData()
    applied = apply_contribution(
        data,
        contribution("msg:a#0", kind=MailKind.ORDER, merchant="Shop", orders=["#9"]),
        T0,
    )
    parcel = mark_delivered(data, applied.parcel_id, at(hours=5))
    assert parcel.state.status is S.DELIVERED
    assert parcel.state.delivered_at == at(hours=5)
    assert archive_parcel(data, parcel.id, at(days=1)).archived == at(days=1)


def test_anchored_contribution() -> None:
    """An anchored contribution joins the parcel holding its anchor, or nothing."""
    data = ParcelsData()
    shop = apply_contribution(
        data,
        contribution(
            "msg:shop#0", kind=MailKind.ORDER, orders=("1001",), merchant="Loja"
        ),
        T0,
    )
    other = apply_contribution(
        data,
        contribution("msg:other#0", orders=("2002",), merchant="Loja", eta=_eta(20)),
        T0,
    )
    fill = contribution("msg:shop#ai", source=Source.AI, eta=_eta(20), owner=None)
    fill.events[0].status = fill.events[0].kind = None
    fill.anchor = "msg:shop#0"

    applied = apply_contribution(data, fill, at(hours=1))

    assert applied.parcel_id == shop.parcel_id
    assert not applied.created
    assert applied.auto_merged is None
    parcel = data.parcels[shop.parcel_id]
    assert parcel.state.eta == _eta(20)
    assert parcel.state.status is S.ORDERED
    assert "msg:shop#ai" not in data.parcels[other.parcel_id].origins

    remove_message(data, "shop", at(hours=2))
    assert shop.parcel_id not in data.parcels
    assert apply_contribution(data, fill, at(hours=3)).parcel_id is None
    assert list(data.parcels) == [other.parcel_id]


# --- Guesses and private parcels ------------------------------------------------


def _tracked_shop(*, private: bool, owner: str = "person.one") -> Contribution:
    """The shop's parcel with DPD's number, due on the 5th or 6th."""
    return contribution(
        "msg:a#0",
        carrier="dpd",
        number=DPD,
        merchant="Example Shop",
        eta=_eta(5, 6),
        owner=owner,
        private=private,
    )


def _shop_news(
    origin_id: str = "msg:b#0", *, owner: str = "person.two", private: bool = False
) -> Contribution:
    """The shop's news without a number, which only a guess places."""
    return contribution(
        origin_id,
        kind=MailKind.IN_TRANSIT,
        time=at(hours=3),
        merchant="example shop",
        eta=_eta(6),
        owner=owner,
        private=private,
    )


@pytest.mark.parametrize("accept", [True, False])
def test_guess_never_shows_a_private_parcel_to_someone_else(accept: bool) -> None:
    """Someone else's e-mail isn't guessed into a private parcel: it's suggested.

    Accepting the suggestion shares the parcel, as merging by hand does.
    """
    data = ParcelsData()
    tracked = apply_contribution(data, _tracked_shop(private=True), T0)
    news = apply_contribution(data, _shop_news(), at(hours=3))

    assert news.created
    assert news.auto_merged is None
    assert len(data.parcels) == 2
    parcel = data.parcels[tracked.parcel_id]
    assert parcel.private
    assert parcel.state.owners == ("person.one",)
    assert parcel.auto_merged is None
    assert data.engine["held_guesses"] == [
        [["msg:a#0"], ["msg:b#0"], REASON_SAME_MERCHANT_ETA]
    ]

    [suggestion] = reconcile(data, at(hours=4)).suggestions
    assert suggestion.parcel_id == tracked.parcel_id
    assert suggestion.candidates == (news.parcel_id,)
    assert suggestion.reason == REASON_SAME_MERCHANT_ETA
    assert [s.id for s in reconcile(data, at(hours=5)).suggestions] == [suggestion.id]

    if accept:
        merged = accept_suggestion(
            data, tracked.parcel_id, str(news.parcel_id), at(hours=6)
        )
        assert merged.private
        assert merged.state.owners == ("person.one", "person.two")
        assert list(data.parcels) == [tracked.parcel_id]
    else:
        dismiss_suggestion(data, tracked.parcel_id, [str(news.parcel_id)])
        assert len(data.parcels) == 2
    assert reconcile(data, at(hours=7)).suggestions == []
    assert "held_guesses" not in data.engine


@pytest.mark.parametrize(
    ("owner", "joins"), [("person.one", True), ("person.two", False)]
)
def test_private_mail_is_guessed_only_into_its_owners_parcel(
    owner: str, joins: bool
) -> None:
    """A private e-mail joins a guessed parcel only when it's its owner's."""
    data = ParcelsData()
    tracked = apply_contribution(data, _tracked_shop(private=False), T0)
    news = apply_contribution(data, _shop_news(owner=owner, private=True), at(hours=3))

    assert (news.parcel_id == tracked.parcel_id) is joins
    assert data.parcels[tracked.parcel_id].private is joins
    assert ("held_guesses" in data.engine) is not joins


def test_guess_into_a_private_parcel_of_its_owner() -> None:
    """The private parcel's owner's own e-mails are still guessed into it."""
    data = ParcelsData()
    tracked = apply_contribution(data, _tracked_shop(private=True), T0)
    news = apply_contribution(data, _shop_news(owner="person.one"), at(hours=3))

    assert news.parcel_id == tracked.parcel_id
    assert news.auto_merged == REASON_SAME_MERCHANT_ETA
    assert "held_guesses" not in data.engine


def test_same_number_of_another_carrier_into_a_private_parcel_is_suggested() -> None:
    """The same number read as another carrier's doesn't join a private parcel."""
    data = ParcelsData()
    private = apply_contribution(
        data, contribution("msg:a#0", carrier="dpd", number=DPD, private=True), T0
    )
    other = apply_contribution(
        data,
        contribution(
            "msg:b#0", carrier="gls", number=DPD, owner="person.two", time=at(hours=1)
        ),
        at(hours=1),
    )

    assert other.created
    assert other.auto_merged is None
    assert data.engine["held_guesses"] == [
        [["msg:a#0"], ["msg:b#0"], REASON_SAME_NUMBER]
    ]
    [suggestion] = reconcile(data, at(hours=2)).suggestions
    assert {suggestion.parcel_id, *suggestion.candidates} == {
        private.parcel_id,
        other.parcel_id,
    }
    assert suggestion.reason == REASON_SAME_NUMBER
    merged = accept_suggestion(
        data, suggestion.parcel_id, suggestion.candidates[0], at(hours=3)
    )
    assert set(merged.origins) == {"msg:a#0", "msg:b#0"}
    assert merged.private


def test_refused_guess_makes_no_other_guess() -> None:
    """When the likely parcel is private, the e-mail isn't guessed elsewhere."""
    data = ParcelsData()
    private = apply_contribution(data, _tracked_shop(private=True), T0)
    shop = apply_contribution(data, _shop_news(), at(hours=3))
    assert shop.created
    gls = contribution(
        "msg:c#0",
        carrier="gls",
        number=DPD,
        merchant="Example Shop",
        eta=_eta(5, 6),
        owner="person.two",
        time=at(hours=4),
    )

    applied = apply_contribution(data, gls, at(hours=4))

    assert applied.created
    assert applied.parcel_id not in (private.parcel_id, shop.parcel_id)
    assert data.engine["held_guesses"] == [
        [["msg:a#0"], ["msg:b#0"], REASON_SAME_MERCHANT_ETA],
        [["msg:a#0"], ["msg:c#0"], REASON_SAME_NUMBER],
    ]

    # Without the private parcel, the shop's e-mail is the guess.
    data = ParcelsData()
    shop = apply_contribution(data, _shop_news(), at(hours=3))
    applied = apply_contribution(data, gls, at(hours=4))
    assert applied.parcel_id == shop.parcel_id
    assert applied.auto_merged == REASON_SAME_MERCHANT_ETA


def test_paack_stem_guesses_no_private_package_of_someone_else() -> None:
    """The stem's news isn't guessed into the open package when it's private."""
    data = ParcelsData()
    done = apply_contribution(
        data, _paack("msg:p1#0", kind=MailKind.DELIVERED, number=PAACK_ID), T0
    )
    package = _paack("msg:p2#0", hours=1, number=f"{SHIPMENT}_2")
    package.private = True
    open_ = apply_contribution(data, package, at(hours=1))
    news = _paack(
        "msg:p3#0", hours=2, kind=MailKind.OUT_FOR_DELIVERY, reference=SHIPMENT
    )
    news.origin.owners = ("person.two",)

    stem = apply_contribution(data, news, at(hours=2))

    assert stem.created
    assert stem.parcel_id not in (done.parcel_id, open_.parcel_id)
    assert data.parcels[open_.parcel_id].state.status is S.IN_TRANSIT
    assert data.engine["held_guesses"] == [
        [["msg:p2#0"], ["msg:p3#0"], REASON_SAME_REFERENCE]
    ]


def test_new_owner_of_a_private_parcel_doesnt_see_its_guesses() -> None:
    """An e-mail found in another mailbox takes its parcel's guesses back.

    Its new owner would otherwise see the private e-mails a guess put
    together with theirs. The guess becomes a suggestion.
    """
    data = ParcelsData()
    private = apply_contribution(data, _tracked_shop(private=True), T0)
    news = apply_contribution(data, _shop_news(owner="person.one"), at(hours=3))
    assert news.parcel_id == private.parcel_id

    changed = add_owner(data, "b", "person.two", at(hours=4))

    parcel = data.parcels[private.parcel_id]
    assert set(parcel.origins) == {"msg:a#0"}
    assert parcel.state.owners == ("person.one",)
    assert parcel.auto_merged is None
    [split] = [p for p in data.parcels.values() if p.id != parcel.id]
    assert set(split.origins) == {"msg:b#0"}
    assert split.private
    assert split.state.owners == ("person.one", "person.two")
    assert changed == {parcel.id, split.id}
    assert data.engine["held_guesses"] == [
        [["msg:a#0"], ["msg:b#0"], REASON_SAME_MERCHANT_ETA]
    ]
    [suggestion] = reconcile(data, at(hours=5)).suggestions
    assert (suggestion.parcel_id, suggestion.candidates) == (parcel.id, (split.id,))

    # A public parcel, or a known owner, keeps its guesses.
    data = ParcelsData()
    public = apply_contribution(data, _tracked_shop(private=False), T0)
    apply_contribution(data, _shop_news(owner="person.one"), at(hours=3))
    assert add_owner(data, "b", "person.two", at(hours=4)) == {public.parcel_id}
    assert len(data.parcels) == 1
    assert add_owner(data, "a", "person.one", at(hours=4)) == set()


def _guessed_and_unowned() -> ParcelsData:
    """A private parcel holding a guess, and a parcel of nobody's e-mail."""
    data = ParcelsData()
    apply_contribution(data, _tracked_shop(private=True), T0)
    apply_contribution(data, _shop_news(owner="person.one"), at(hours=3))
    apply_contribution(
        data,
        contribution("msg:c#0", carrier="ctt", number="RR123456785PT", owner=None),
        at(hours=3),
    )
    return data


def _owner_shape(data: ParcelsData) -> list[tuple[object, ...]]:
    """Return each parcel's e-mails, owners, privacy and guess, without IDs."""
    return sorted(
        (
            tuple(sorted(parcel.origins)),
            parcel.state.owners,
            parcel.private,
            parcel.auto_merged is not None,
        )
        for parcel in data.parcels.values()
    )


def test_owner_added_to_several_emails_at_once() -> None:
    """A mailbox's new owner reaches all its e-mails at once, as one by one.

    A private parcel's guesses are taken back first, so the new owner gets a
    suggestion instead.
    """
    data = _guessed_and_unowned()
    one_by_one = _guessed_and_unowned()
    assert len(data.parcels) == 2

    changed = add_owner_to(data, {"a", "b", "c"}, "person.two", at(hours=4))
    for message in ("a", "b", "c"):
        add_owner(one_by_one, message, "person.two", at(hours=4))

    assert (
        _owner_shape(data)
        == _owner_shape(one_by_one)
        == [
            (("msg:a#0",), ("person.one", "person.two"), True, False),
            (("msg:b#0",), ("person.one", "person.two"), True, False),
            (("msg:c#0",), ("person.two",), False, False),
        ]
    )
    assert changed == set(data.parcels)
    assert all(parcel.updated == at(hours=4) for parcel in data.parcels.values())
    assert (
        data.engine["held_guesses"]
        == one_by_one.engine["held_guesses"]
        == [[["msg:a#0"], ["msg:b#0"], REASON_SAME_MERCHANT_ETA]]
    )
    # The e-mails' owner already: nothing changes.
    assert add_owner_to(data, {"a", "b", "c"}, "person.two", at(hours=5)) == set()
    assert add_owner_to(data, set(), "person.three", at(hours=5)) == set()
    assert all(parcel.updated == at(hours=4) for parcel in data.parcels.values())


def test_owner_removed_from_emails() -> None:
    """A mailbox's former owner leaves its e-mails, and only those."""
    data = ParcelsData()
    first = apply_contribution(
        data, contribution("msg:m#0", carrier="ctt", number="RR123456785PT"), T0
    )
    apply_contribution(
        data,
        contribution(
            "msg:n#0",
            kind=MailKind.IN_TRANSIT,
            time=at(hours=1),
            carrier="ctt",
            number="RR123456785PT",
        ),
        at(hours=1),
    )
    add_owner(data, "m", "person.two", at(hours=1))
    parcel = data.parcels[first.parcel_id]
    assert len(data.parcels) == 1
    assert parcel.state.owners == ("person.one", "person.two")

    assert remove_owner_from(data, {"m"}, "person.one", at(hours=2)) == {parcel.id}

    assert parcel.origins["msg:m#0"].owners == ("person.two",)
    assert parcel.origins["msg:n#0"].owners == ("person.one",)
    assert parcel.state.owners == ("person.one", "person.two")
    assert parcel.updated == at(hours=2)

    assert remove_owner_from(data, {"m", "n"}, "person.one", at(hours=3)) == {parcel.id}
    assert parcel.origins["msg:n#0"].owners == ()
    assert parcel.state.owners == ("person.two",)
    # Not an owner of these e-mails.
    assert remove_owner_from(data, {"m", "n"}, "person.one", at(hours=4)) == set()
    assert parcel.updated == at(hours=3)
