"""Tests for deduplication: every parcel appears once."""

from __future__ import annotations

from datetime import date, time
import json

import pytest

from custom_components.parcels.const import MailKind, ParcelStatus
from custom_components.parcels.dedup import (
    REASON_SAME_MERCHANT_ETA,
    REASON_SAME_NUMBER,
    REASON_SAME_REFERENCE,
    Contribution,
    DedupError,
    add_owner,
    amazon_shipment_id_counts,
    apply_contribution,
    archive_parcel,
    find_parcels_by_number,
    mark_delivered,
    merge_parcels,
    order_parcels,
    paack_amazon_counts,
    parcel_order_keys,
    remove_message,
    split_parcel,
    undo_auto_merge,
    update_parcel,
)
from custom_components.parcels.models import ParcelsData, Source
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


# Made up: an Amazon shipment ID, and the Paack order ID of its first package.
SHIPMENT = "Rb5Lq2Vm7"
PAACK_ID = f"{SHIPMENT}_1"
PAACK_BARCODE = "534000088812345678"


@pytest.mark.parametrize("paack_eta", [None, _eta(5)])
@pytest.mark.parametrize("paack_first", [False, True])
def test_paack_order_id_joins_its_amazon_shipment(
    paack_first: bool, paack_eta: Eta | None
) -> None:
    """Paack's order ID is Amazon's shipment ID and a package number."""
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

    [parcel] = data.parcels.values()
    assert joined.auto_merged is None
    assert parcel.auto_merged is None
    assert parcel.state.tracking_number == PAACK_ID
    assert parcel.state.amazon_shipment_ids == (SHIPMENT,)
    with pytest.raises(DedupError, match="shared_number"):
        split_parcel(data, parcel.id, {"msg:p#0"}, at(days=1))


@pytest.mark.parametrize(
    ("carrier", "number"),
    [
        ("paack", PAACK_ID.upper()),
        ("paack", PAACK_ID.lower()),
        ("paack", "Rb5Lq2Vm8_1"),
        ("gls", PAACK_ID),
        (None, PAACK_ID),
    ],
)
def test_paack_order_id_needs_the_exact_shipment_id(
    carrier: str | None, number: str
) -> None:
    """Only Paack's ID with the shipment ID as written joins the shipment."""
    data = ParcelsData()
    apply_contribution(
        data, contribution("msg:a#0", merchant="Amazon.es", shipment_id=SHIPMENT), T0
    )
    apply_contribution(
        data,
        contribution(
            "msg:p#0", kind=MailKind.IN_TRANSIT, carrier=carrier, number=number
        ),
        at(hours=1),
    )
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


def test_paack_amazon_counts() -> None:
    """Paack's e-mails are counted by whether their ID names a shipment.

    Each e-mail counts once, with no ID or shop name, so users can share the
    counts. Two more counts per group: e-mails whose ID names a shipment
    when case is ignored, and e-mails that came at most 7 days after an
    Amazon e-mail that gave a shipment ID.
    """
    data = ParcelsData()
    sent = [
        contribution(
            "msg:a#0",
            label="amazon.es",
            merchant="Amazon.es",
            shipment_id=SHIPMENT,
            carrier="paack",
            number=PAACK_BARCODE,
        ),
        *(
            contribution(
                origin_id,
                label="paack.co",
                source=source,
                kind=MailKind.IN_TRANSIT,
                carrier="paack",
                number=number,
                merchant=merchant,
            )
            for origin_id, source, number, merchant in (
                ("msg:p1#0", Source.PARSER, PAACK_ID, "Amazon"),
                ("msg:p1#ai", Source.AI, PAACK_ID, None),
                ("msg:p2#0", Source.PARSER, f"{SHIPMENT.lower()}_2", "Amazon"),
                ("msg:p3#0", Source.PARSER, PAACK_BARCODE, "Amazon"),
                ("msg:p4#0", Source.PARSER, f"{SHIPMENT}_2", None),
                ("msg:p5#0", Source.PARSER, f"{SHIPMENT[:-1]}X_1", "Casa Exemplo"),
            )
        ),
        # Only the shipment, as Paack's "order number".
        contribution(
            "msg:p6#0",
            label="paack.co",
            kind=MailKind.DELIVERED,
            carrier="paack",
            reference=SHIPMENT,
            merchant="Amazon",
        ),
        # A day before Amazon's e-mail with the shipment ID.
        contribution(
            "msg:p7#0",
            label="paack.co",
            kind=MailKind.IN_TRANSIT,
            carrier="paack",
            number=f"{SHIPMENT}_3",
            merchant="Amazon",
            time=at(days=-1),
        ),
        # Amazon's e-mail without a shipment ID, half a day before Paack's.
        contribution(
            "msg:a2#0", label="amazon.es", merchant="Amazon.es", time=at(days=7.5)
        ),
        # Eight days after Amazon's e-mail with the shipment ID.
        contribution(
            "msg:p8#0",
            label="paack.co",
            kind=MailKind.IN_TRANSIT,
            carrier="paack",
            number="Tq3Zr8Lm2_1",
            time=at(days=8),
        ),
    ]
    for index, item in enumerate(sent):
        apply_contribution(data, item, at(days=9, hours=index))

    assert paack_amazon_counts(data) == {
        "naming_amazon": {
            "matched": 3,
            "unmatched": 1,
            "without_id": 1,
            "matched_ignoring_case": 4,
            "amazon_id_7_days_before": 4,
        },
        "not_naming_amazon": {
            "matched": 1,
            "unmatched": 2,
            "without_id": 0,
            "matched_ignoring_case": 1,
            "amazon_id_7_days_before": 2,
        },
    }


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
            "with_id": 2,
            "without_id": 1,
            "shapes": {"len9:Aa0": 2},
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


def test_paack_stem_joins_its_amazon_shipment() -> None:
    """The stem is Amazon's shipment ID, so it joins Amazon's parcel."""
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
    assert stem.parcel_id == amazon.parcel_id
    assert stem.auto_merged is None
    [parcel] = data.parcels.values()
    assert parcel.state.status is S.DELIVERED
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
