"""Tests for the conversions between parser results, suggestions and parcels."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest

from custom_components.parcels.const import CONFIDENCE_APPLY, MailKind, ParcelStatus
from custom_components.parcels.convert import (
    fill_contribution,
    fill_gaps,
    fill_origin_id,
    fill_suggestion,
    has_identifier,
    is_confident,
    result_contributions,
    results_agree,
    suggestion_from_result,
    suggestion_result,
)
from custom_components.parcels.dedup import Contribution, apply_contribution
from custom_components.parcels.models import (
    MAX_ITEMS,
    ParcelsData,
    ParcelState,
    Source,
    Suggestion,
)
from custom_components.parcels.parsers.base import Eta, ParsedShipment, ParseResult

from .factories import T0, contribution

SENT = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)
NUMBER = "RR123456785PT"
OTHER_NUMBER = "1Z999AA10123456784"
ETA = Eta(start=date(2026, 11, 18), end=date(2026, 11, 19))


def _result(
    kind: MailKind = MailKind.SHIPPED,
    *shipments: ParsedShipment,
    confidence: float = 0.9,
    **kwargs: Any,
) -> ParseResult:
    return ParseResult(
        parser="test",
        kind=kind,
        shipments=list(shipments),
        confidence=confidence,
        **kwargs,
    )


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (_result(MailKind.ORDER, order_numbers=("1001",)), True),
        (_result(MailKind.SHIPPED, ParsedShipment(tracking_number=NUMBER)), True),
        (_result(MailKind.SHIPPED, ParsedShipment(amazon_shipment_id="Mx8Rb")), True),
        (_result(MailKind.ORDER, ParsedShipment(order_numbers=("1001",))), True),
        (_result(MailKind.DELIVERED, ParsedShipment(reference="Wx4Hn8Tz3")), True),
        (_result(MailKind.SHIPPED, ParsedShipment(carrier="ctt", eta=ETA)), False),
        (_result(MailKind.SHIPPED), False),
    ],
    ids=[
        "order",
        "number",
        "amazon_shipment",
        "shipment_order",
        "reference",
        "carrier",
        "none",
    ],
)
def test_has_identifier(result: ParseResult, expected: bool) -> None:
    """Order numbers, shipment IDs, tracking numbers and references identify."""
    assert has_identifier(result) is expected


@pytest.mark.parametrize(
    ("kind", "confidence", "shipment", "expected"),
    [
        (
            MailKind.SHIPPED,
            CONFIDENCE_APPLY,
            ParsedShipment(tracking_number=NUMBER),
            True,
        ),
        (MailKind.SHIPPED, 0.69, ParsedShipment(tracking_number=NUMBER), False),
        (MailKind.SHIPPED, 1.0, ParsedShipment(carrier="ctt"), False),
        (MailKind.UNKNOWN, 1.0, ParsedShipment(tracking_number=NUMBER), False),
        (MailKind.NOT_PARCEL, 1.0, ParsedShipment(tracking_number=NUMBER), False),
    ],
    ids=["threshold", "low_confidence", "no_identifier", "unknown", "not_parcel"],
)
def test_is_confident(
    kind: MailKind, confidence: float, shipment: ParsedShipment, expected: bool
) -> None:
    """A result applies on its own when it's a parcel, sure, and identified."""
    assert is_confident(_result(kind, shipment, confidence=confidence)) is expected


@pytest.mark.parametrize("kind", [MailKind.NOT_PARCEL, MailKind.UNKNOWN])
def test_contributions_need_a_parcel(kind: MailKind) -> None:
    """Results that aren't about a parcel add nothing."""
    result = _result(kind, ParsedShipment(tracking_number=NUMBER))
    assert (
        result_contributions(result, message_hash="h", time=SENT, source=Source.AI)
        == []
    )


def test_order_only_contribution() -> None:
    """An order e-mail without shipments gives one provisional order parcel."""
    result = _result(
        MailKind.ORDER, merchant="Loja Exemplo", order_numbers=("1001",), items=("Mug",)
    )

    [contribution] = result_contributions(
        result,
        message_hash="abc",
        time=SENT,
        source=Source.PARSER,
        label="example.com",
        owner="person.alex",
    )

    origin = contribution.origin
    assert origin.id == "msg:abc#0"
    assert origin.message == "abc"
    assert origin.tracking_number is None
    assert origin.order_numbers == ("1001",)
    assert origin.items == ("Mug",)
    assert origin.owners == ("person.alex",)
    assert origin.label == "example.com"
    assert contribution.order_placed == SENT
    [event] = contribution.events
    assert event.status is ParcelStatus.ORDERED
    assert event.time == SENT


@pytest.mark.parametrize(("confirmed", "attach_only"), [(False, True), (True, False)])
def test_code_mail_only_joins_its_parcel(confirmed: bool, attach_only: bool) -> None:
    """An e-mail with just a delivery code adds to a parcel, never makes one.

    Unless the user confirmed it in "Needs review".
    """
    result = _result(
        MailKind.CODE,
        ParsedShipment(tracking_number=NUMBER, kind=MailKind.CODE, pickup_code="4821"),
    )

    [contribution] = result_contributions(
        result, message_hash="h", time=SENT, source=Source.PARSER, confirmed=confirmed
    )

    assert contribution.attach_only is attach_only
    assert contribution.origin.pickup_code == "4821"
    assert contribution.events == []


@pytest.mark.parametrize(("confirmed", "attach_only"), [(False, True), (True, False)])
def test_survey_only_joins_its_parcel(confirmed: bool, attach_only: bool) -> None:
    """A shipment that can only confirm a known parcel never makes one.

    Unless the user confirmed it in "Needs review". Its seller is kept, and
    its delivery, which the e-mail doesn't date, had happened by then.
    """
    result = _result(
        MailKind.DELIVERED,
        ParsedShipment(
            reference="1234567890",
            seller="Loja Exemplo",
            attach_only=True,
            undated=True,
        ),
        merchant="Leroy Merlin",
    )

    [contribution] = result_contributions(
        result, message_hash="h", time=SENT, source=Source.PARSER, confirmed=confirmed
    )

    assert contribution.attach_only is attach_only
    assert contribution.origin.reference == "1234567890"
    assert contribution.origin.seller == "Loja Exemplo"
    [event] = contribution.events
    assert event.status is ParcelStatus.DELIVERED
    assert (event.undated, event.by, event.time) == (True, SENT, SENT)


def test_status_mail_with_a_code_makes_a_parcel() -> None:
    """A status e-mail that also gives a code is applied as usual."""
    result = _result(
        MailKind.OUT_FOR_DELIVERY,
        ParsedShipment(
            tracking_number=NUMBER,
            kind=MailKind.OUT_FOR_DELIVERY,
            pickup_code="4821",
        ),
    )

    [contribution] = result_contributions(
        result, message_hash="h", time=SENT, source=Source.PARSER
    )

    assert not contribution.attach_only
    assert contribution.origin.pickup_code == "4821"


def test_contribution_per_shipment() -> None:
    """Each shipment is a parcel; its own kind wins and items stay with it."""
    result = _result(
        MailKind.SHIPPED,
        ParsedShipment(
            tracking_number=NUMBER, kind=MailKind.DELIVERED, items=("Lamp",)
        ),
        ParsedShipment(tracking_number=OTHER_NUMBER, kind=MailKind.UNKNOWN),
        order_numbers=("1001",),
        items=("Lamp", "Mug"),
    )

    first, second = result_contributions(
        result, message_hash="abc", time=SENT, source=Source.PARSER
    )

    assert [first.origin.id, second.origin.id] == ["msg:abc#0", "msg:abc#1"]
    assert first.events[0].status is ParcelStatus.DELIVERED
    # An unreadable shipment kind falls back to the e-mail's kind.
    assert second.events[0].status is ParcelStatus.SHIPPED
    # With several parcels, the e-mail's item list can't be assigned.
    assert first.origin.items == ("Lamp",)
    assert second.origin.items == ()
    assert second.origin.order_numbers == ("1001",)
    assert first.order_placed is None
    assert first.origin.owners == ()


@pytest.mark.parametrize(
    ("event_time", "expected"),
    [
        (SENT + timedelta(hours=2), SENT),
        (SENT - timedelta(hours=2), SENT - timedelta(hours=2)),
        (datetime(2026, 11, 16, 9, 0), SENT),
    ],
    ids=["after_sending", "before_sending", "naive"],
)
def test_event_time_clamped(event_time: datetime, expected: datetime) -> None:
    """A parcel can't have moved after the e-mail about it was sent."""
    result = _result(
        MailKind.IN_TRANSIT,
        ParsedShipment(tracking_number=NUMBER, event_time=event_time),
    )

    [contribution] = result_contributions(
        result, message_hash="abc", time=SENT, source=Source.PARSER
    )

    assert contribution.events[0].time == expected
    assert contribution.origin.time == SENT


@pytest.mark.parametrize(
    ("source", "expected"),
    [(Source.PARSER, "https://track.example.com/a"), (Source.AI, None)],
)
def test_ai_links_are_dropped(source: Source, expected: str | None) -> None:
    """Tracking links read by the AI are never used."""
    result = _result(
        MailKind.SHIPPED,
        ParsedShipment(
            tracking_number=NUMBER, tracking_url="https://track.example.com/a"
        ),
    )

    [contribution] = result_contributions(
        result, message_hash="abc", time=SENT, source=source
    )

    assert contribution.origin.tracking_url == expected


@pytest.mark.parametrize(
    "result",
    [
        None,
        _result(MailKind.NOT_PARCEL, ParsedShipment(tracking_number=NUMBER)),
        _result(MailKind.UNKNOWN, ParsedShipment(carrier="ctt", eta=ETA)),
    ],
    ids=["none", "not_parcel", "unknown_without_identifier"],
)
def test_nothing_to_suggest(result: ParseResult | None) -> None:
    """Nothing parcel-like gives no suggestion."""
    assert suggestion_from_result(result) is None


def test_suggestion_collects_the_shipments() -> None:
    """A suggestion merges the shipments, normalised and without repeats."""
    result = _result(
        MailKind.UNKNOWN,
        ParsedShipment(carrier=None, order_numbers=("1001", "1002")),
        ParsedShipment(
            carrier="ctt",
            tracking_number="rr 123-456.785 pt",
            kind=MailKind.IN_TRANSIT,
            eta=ETA,
            pickup_point="Loja Centro",
            pickup_code="4321",
            amazon_shipment_id="Mx8Rb",
            items=("Lamp",),
        ),
        ParsedShipment(tracking_number=NUMBER, items=("Mug",)),
        merchant="Loja Exemplo",
        order_numbers=("1001",),
        items=tuple(f"Item {n}" for n in range(MAX_ITEMS)),
    )

    suggestion = suggestion_from_result(result)

    assert suggestion == Suggestion(
        # The kind of an unreadable e-mail comes from its shipments.
        kind=MailKind.IN_TRANSIT,
        merchant="Loja Exemplo",
        carrier="ctt",
        tracking_numbers=(NUMBER,),
        order_numbers=("1001", "1002"),
        eta_start=ETA.start,
        eta_end=ETA.end,
        pickup_point="Loja Centro",
        pickup_code="4321",
        items=tuple(f"Item {n}" for n in range(MAX_ITEMS)),
        amazon_shipment_id="Mx8Rb",
    )


def test_suggestion_round_trip() -> None:
    """An accepted suggestion reads back as the same suggestion."""
    suggestion = Suggestion(
        kind=MailKind.OUT_FOR_DELIVERY,
        merchant="Loja Exemplo",
        carrier="ctt",
        tracking_numbers=(NUMBER,),
        order_numbers=("1001",),
        eta_start=date(2026, 11, 18),
        eta_end=date(2026, 11, 18),
        window_start=time(9, 0),
        window_end=time(13, 0),
        pickup_point="Loja Centro",
        pickup_code="4321",
        items=("Lamp",),
        amazon_shipment_id="Mx8Rb",
    )

    result = suggestion_result(suggestion, Source.AI)

    assert result.confidence == 1.0
    assert result.source == "ai"
    assert is_confident(result)
    assert suggestion_from_result(result) == suggestion


def test_reference_suggestion_round_trip() -> None:
    """A suggestion with only a shipment reference applies, and reads back."""
    suggestion = Suggestion(
        kind=MailKind.DELIVERED,
        merchant="Amazon",
        carrier="paack",
        reference="Wx4Hn8Tz3",
    )

    result = suggestion_result(suggestion, Source.AI)

    assert is_confident(result)
    assert suggestion_from_result(result) == suggestion
    [contribution] = result_contributions(
        result, message_hash="h", time=SENT, source=Source.AI
    )
    assert contribution.origin.reference == "Wx4Hn8Tz3"
    assert contribution.origin.tracking_number is None
    unknown = Suggestion(kind=MailKind.UNKNOWN, reference="Wx4Hn8Tz3")
    assert suggestion_result(unknown, Source.MANUAL).kind is MailKind.SHIPPED
    assert suggestion_from_result(
        _result(MailKind.UNKNOWN, ParsedShipment(reference="Wx4Hn8Tz3"))
    ) == Suggestion(kind=MailKind.UNKNOWN, reference="Wx4Hn8Tz3")


def test_suggestion_with_two_numbers() -> None:
    """Pickup details and the shipment ID can't be split over two parcels."""
    suggestion = Suggestion(
        kind=MailKind.SHIPPED,
        carrier="ups",
        tracking_numbers=(NUMBER, OTHER_NUMBER),
        pickup_point="Loja Centro",
        pickup_code="4321",
        amazon_shipment_id="Mx8Rb",
        eta_start=date(2026, 11, 19),
        eta_end=date(2026, 11, 18),
    )

    result = suggestion_result(suggestion, Source.PARSER)

    assert [s.tracking_number for s in result.shipments] == [NUMBER, OTHER_NUMBER]
    for shipment in result.shipments:
        assert shipment.carrier == "ups"
        assert shipment.pickup_point is None
        assert shipment.pickup_code is None
        assert shipment.amazon_shipment_id is None
        # An end before the start is read as a single day.
        assert shipment.eta == Eta(start=date(2026, 11, 19), end=date(2026, 11, 19))


@pytest.mark.parametrize(
    ("suggestion", "kind"),
    [
        (
            Suggestion(kind=MailKind.UNKNOWN, tracking_numbers=(NUMBER,)),
            MailKind.SHIPPED,
        ),
        (
            Suggestion(kind=MailKind.UNKNOWN, amazon_shipment_id="Mx8Rb"),
            MailKind.SHIPPED,
        ),
        (Suggestion(kind=MailKind.NOT_PARCEL, order_numbers=("1001",)), MailKind.ORDER),
        (Suggestion(kind=MailKind.DELAYED, order_numbers=("1001",)), MailKind.DELAYED),
    ],
    ids=["number", "amazon_shipment", "order", "kept"],
)
def test_suggestion_kind(suggestion: Suggestion, kind: MailKind) -> None:
    """Without a kind, a tracking number means shipped and an order ordered."""
    result = suggestion_result(suggestion, Source.MANUAL)

    assert result.kind is kind
    assert [s.kind for s in result.shipments] == [kind]
    assert result.is_parcel


def _shadow(kind: MailKind, number: str | None, eta: Eta | None) -> ParseResult:
    return _result(kind, ParsedShipment(tracking_number=number, kind=kind, eta=eta))


@pytest.mark.parametrize(
    ("ai", "expected"),
    [
        (_shadow(MailKind.SHIPPED, "rr123456785pt", ETA), True),
        (_shadow(MailKind.IN_TRANSIT, NUMBER, ETA), False),
        (_shadow(MailKind.SHIPPED, OTHER_NUMBER, ETA), False),
        (_shadow(MailKind.SHIPPED, NUMBER, Eta(ETA.start, date(2026, 11, 20))), False),
        (_shadow(MailKind.SHIPPED, NUMBER, None), False),
    ],
    ids=["same", "status", "number", "eta", "no_eta"],
)
def test_results_agree(ai: ParseResult, expected: bool) -> None:
    """The shadow check compares the status, the numbers and the first ETA."""
    parser = _shadow(MailKind.SHIPPED, NUMBER, ETA)
    assert results_agree(parser, ai) is expected


def test_results_agree_without_parser_eta() -> None:
    """An ETA the parser didn't find isn't held against the AI."""
    parser = _result(MailKind.DELAYED, ParsedShipment(tracking_number=NUMBER))
    ai = _shadow(MailKind.DELAYED, NUMBER, ETA)

    assert results_agree(parser, ai)
    # A delay keeps a parcel in transit, so both read the same status.
    assert results_agree(parser, _shadow(MailKind.IN_TRANSIT, NUMBER, None))


def _state(*contributions: Contribution) -> ParcelState:
    data = ParcelsData()
    parcel_id = None
    for item in contributions:
        parcel_id = apply_contribution(data, item, T0).parcel_id
    assert parcel_id is not None
    return data.parcels[parcel_id].state


def _parsed(kind: MailKind, **shipment: Any) -> ParseResult:
    return _result(kind, ParsedShipment(kind=kind, **shipment))


SHIPPED_GAPS = {"eta", "items", "tracking_number", "carrier"}


@pytest.mark.parametrize(
    ("result", "carrier_mail", "expected"),
    [
        (
            _parsed(MailKind.SHIPPED, tracking_number=NUMBER, carrier="ctt"),
            False,
            {"eta", "items"},
        ),
        (
            _parsed(MailKind.IN_TRANSIT, tracking_number=NUMBER, carrier="ctt"),
            True,
            {"eta"},
        ),
        (_result(MailKind.ORDER, order_numbers=("1001",)), False, {"eta", "items"}),
        (_result(MailKind.SHIPPED, order_numbers=("1001",)), False, SHIPPED_GAPS),
        (
            _parsed(MailKind.SHIPPED, tracking_number=NUMBER, eta=ETA, items=("Lamp",)),
            False,
            {"carrier"},
        ),
        (_parsed(MailKind.DELIVERED, tracking_number=NUMBER), False, set()),
        (_parsed(MailKind.CODE, tracking_number=NUMBER), False, set()),
        (
            _result(
                MailKind.SHIPPED,
                ParsedShipment(tracking_number=NUMBER),
                ParsedShipment(tracking_number=OTHER_NUMBER),
            ),
            False,
            set(),
        ),
    ],
    ids=[
        "shop",
        "carrier",
        "order",
        "no_number",
        "carrier_gap",
        "delivered",
        "code",
        "two",
    ],
)
def test_fill_gaps(result: ParseResult, carrier_mail: bool, expected: set[str]) -> None:
    """The AI may fill in only what neither the e-mail nor the parcel has."""
    state = _state(contribution("msg:other#0", orders=("1001",), merchant="Loja"))

    assert fill_gaps(result, state, carrier_mail=carrier_mail) == expected


def test_fill_gaps_from_the_parcel() -> None:
    """What the parcel already knows from other e-mails isn't a gap."""
    result = _result(MailKind.SHIPPED, order_numbers=("1001",))
    known = contribution(
        "msg:other#0", number=NUMBER, carrier="ctt", eta=ETA, items=("Lamp",)
    )

    assert fill_gaps(result, _state(known), carrier_mail=False) == set()
    delivered = contribution("msg:late#0", number=NUMBER, kind=MailKind.DELIVERED)
    shop = _parsed(MailKind.SHIPPED, tracking_number=NUMBER)
    assert fill_gaps(shop, _state(delivered), carrier_mail=False) == set()


def _ai(
    *shipments: ParsedShipment, kind: MailKind = MailKind.SHIPPED, **kwargs: Any
) -> ParseResult:
    return ParseResult(
        parser="ai", kind=kind, shipments=list(shipments), source="ai", **kwargs
    )


def test_fill_suggestion() -> None:
    """Only the gaps are taken, with the parser's kind."""
    parser = _parsed(MailKind.IN_TRANSIT, tracking_number=NUMBER, carrier="ctt")
    ai = _ai(
        ParsedShipment(tracking_number=NUMBER, carrier="dpd", eta=ETA),
        kind=MailKind.OUT_FOR_DELIVERY,
        merchant="Other",
        items=("Lamp", "Rug"),
    )

    assert fill_suggestion(ai, {"eta", "items"}, parser) == Suggestion(
        kind=MailKind.IN_TRANSIT,
        eta_start=ETA.start,
        eta_end=ETA.end,
        items=("Lamp", "Rug"),
    )
    assert fill_suggestion(ai, {"items"}, parser) == Suggestion(
        kind=MailKind.IN_TRANSIT, items=("Lamp", "Rug")
    )


def test_fill_suggestion_number() -> None:
    """A missing number and carrier are filled when the AI found one of each."""
    parser = _result(MailKind.SHIPPED, order_numbers=("1001",))
    ai = _ai(ParsedShipment(tracking_number=NUMBER.lower(), carrier="ctt"))

    assert fill_suggestion(ai, SHIPPED_GAPS, parser) == Suggestion(
        kind=MailKind.SHIPPED, carrier="ctt", tracking_numbers=(NUMBER,)
    )


@pytest.mark.parametrize(
    "ai",
    [
        None,
        _ai(kind=MailKind.NOT_PARCEL),
        _ai(ParsedShipment(tracking_number=OTHER_NUMBER, eta=ETA)),
        _ai(
            ParsedShipment(tracking_number=NUMBER, eta=ETA),
            ParsedShipment(tracking_number=OTHER_NUMBER, eta=ETA),
        ),
        _ai(ParsedShipment(tracking_number=NUMBER)),
        _ai(
            ParsedShipment(eta=ETA),
            ParsedShipment(eta=Eta(start=date(2026, 11, 20), end=date(2026, 11, 20))),
        ),
    ],
    ids=["failed", "not_parcel", "other_number", "two_numbers", "nothing", "two_dates"],
)
def test_no_fill_suggestion(ai: ParseResult | None) -> None:
    """Nothing is filled from an answer about another parcel or an unclear one."""
    parser = _parsed(MailKind.SHIPPED, tracking_number=NUMBER)

    assert fill_suggestion(ai, {"eta", "items"}, parser) is None


def test_fill_contribution() -> None:
    """A fill adds only its values, to the parcel of the e-mail's parser result."""
    suggestion = Suggestion(
        kind=MailKind.SHIPPED,
        eta_start=ETA.start,
        eta_end=ETA.end,
        items=("Lamp",),
        carrier="ctt",
        tracking_numbers=(NUMBER,),
    )

    fill = fill_contribution(
        suggestion, message_hash="abc", time=SENT, owner="person.one", label="Loja"
    )

    assert fill is not None
    assert fill.anchor == "msg:abc#0"
    origin = fill.origin
    assert origin.id == fill_origin_id("abc") == "msg:abc#ai"
    assert (origin.source, origin.message, origin.owners) == (
        Source.AI,
        "abc",
        ("person.one",),
    )
    assert (origin.carrier, origin.tracking_number, origin.items) == (
        "ctt",
        NUMBER,
        ("Lamp",),
    )
    assert origin.merchant is None
    assert not origin.confirmed
    [event] = fill.events
    assert (event.status, event.kind, event.eta, event.time) == (None, None, ETA, SENT)
    assert (
        fill_contribution(
            Suggestion(kind=MailKind.SHIPPED), message_hash="abc", time=SENT
        )
        is None
    )
