"""Tests for the Amazon e-mail parser."""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
from datetime import date, datetime, time
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.const import CONFIDENCE_APPLY, MailKind
from custom_components.parcels.parsers import tracking
from custom_components.parcels.parsers.amazon import parse_amazon
from custom_components.parcels.parsers.base import (
    Eta,
    Link,
    MailMessage,
    ParseResult,
    SenderVerdict,
)

type Parse = Callable[..., ParseResult]


@pytest.fixture
def parse(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> Parse:
    """Return a helper that parses an Amazon fixture from a verified sender."""

    def run(name: str) -> ParseResult:
        message = load_eml(f"amazon/{name}.eml")
        verdict = verdict_for(message)
        assert verdict.verified
        result = parse_amazon(message, verdict, tz)
        assert result is not None
        return result

    return run


def _day(day: int) -> Eta:
    """Return a one-day estimate in November 2026."""
    return Eta(date(2026, 11, day), date(2026, 11, day))


@pytest.mark.parametrize(
    ("name", "kind", "language", "order"),
    [
        ("order_es", MailKind.ORDER, "es", "405-3829174-6627315"),
        ("order_multi_pt", MailKind.ORDER, "pt", "406-5839271-0042817"),
        ("order_en_us", MailKind.ORDER, "en", "112-4839201-5938472"),
        ("shipped_de", MailKind.SHIPPED, "de", "303-5928471-2039485"),
        ("shipped_ctt_pt", MailKind.SHIPPED, "pt", "406-1928374-5647382"),
        ("shipped_en_uk", MailKind.SHIPPED, "en", "205-8374619-2837465"),
        ("shipped_two_packages_en_us", MailKind.SHIPPED, "en", "114-5938201-7362514"),
        ("arriving_today_it", MailKind.OUT_FOR_DELIVERY, "it", "402-7364519-8273645"),
        ("out_for_delivery_fr", MailKind.OUT_FOR_DELIVERY, "fr", "171-4829375-6639201"),
        ("delivered_photo_es", MailKind.DELIVERED, "es", "407-2938475-1029384"),
        ("delivered_nl", MailKind.DELIVERED, "nl", "404-5839201-7748392"),
        ("delayed_en_us", MailKind.DELAYED, "en", "113-2938475-6610293"),
        ("delayed_de", MailKind.DELAYED, "de", "303-1029384-7564738"),
        ("attempted_fr", MailKind.ATTEMPTED, "fr", "171-5928374-1102938"),
        ("attempted_it", MailKind.ATTEMPTED, "it", "402-1928374-6655443"),
        ("pickup_locker_pt", MailKind.READY_FOR_PICKUP, "pt", "406-7362514-9081726"),
        (
            "pickup_counter_en_uk",
            MailKind.READY_FOR_PICKUP,
            "en",
            "205-1029384-5566778",
        ),
        ("cancelled_it", MailKind.CANCELLED, "it", "402-3847261-9938475"),
        ("cancelled_nl", MailKind.CANCELLED, "nl", "404-1122334-5566778"),
        ("refund_de", MailKind.RETURN, "de", "303-8473625-1928374"),
        ("refund_es", MailKind.RETURN, "es", "405-9384756-1203948"),
    ],
)
def test_kind_language_and_order(
    parse: Parse, name: str, kind: MailKind, language: str, order: str
) -> None:
    """Every layout and language is recognised with the order number."""
    result = parse(name)
    assert result.parser == "amazon"
    assert result.kind is kind
    assert result.language == language
    assert result.merchant == "Amazon"
    assert result.order_numbers == (order,)
    assert result.confidence >= max(0.85, CONFIDENCE_APPLY)
    assert result.shipments
    assert all(shipment.order_numbers == (order,) for shipment in result.shipments)


@pytest.mark.parametrize(
    ("name", "tld", "expected"),
    [
        ("shipped_de", "de", [("DqWzN8xKb", _day(19))]),
        ("shipped_en_uk", "co.uk", [("Bz4PqR7wX", _day(19))]),
        (
            "shipped_two_packages_en_us",
            "com",
            [("Mx8RbQ2zL", _day(19)), ("Nz3TcW6yH", _day(21))],
        ),
        ("out_for_delivery_fr", "fr", [("Wm6KcY2pD", _day(19))]),
        ("delayed_en_us", "com", [("Ks5RtW2nY", _day(20))]),
        ("delayed_de", "de", [("Rj4MxB7qT", _day(21))]),
        ("delivered_nl", "nl", [("Pv2LnR8cJ", None)]),
    ],
)
def test_amazon_logistics_shipments(
    parse: Parse, name: str, tld: str, expected: list[tuple[str, Eta | None]]
) -> None:
    """Shipment IDs come from the "Track package" links, one per package."""
    result = parse(name)
    order = result.order_numbers[0]
    assert [
        (shipment.amazon_shipment_id, shipment.eta) for shipment in result.shipments
    ] == expected
    for index, shipment in enumerate(result.shipments):
        assert shipment.kind is None
        assert shipment.carrier == "amazon"
        assert shipment.tracking_number is None
        assert shipment.event_time is None
        assert shipment.tracking_url == (
            f"https://www.amazon.{tld}/progress-tracker/package?orderId={order}"
            f"&shipmentId={shipment.amazon_shipment_id}&packageIndex={index}"
        )


def test_two_packages_split_items(parse: Parse) -> None:
    """Each package lists only its own items."""
    result = parse("shipped_two_packages_en_us")
    assert [shipment.items for shipment in result.shipments] == [
        ("Hiking Boots, Waterproof, Men's Size 10",),
        ("Merino Wool Hiking Socks, 3 Pairs",),
    ]


@pytest.mark.parametrize(
    ("name", "eta", "items"),
    [
        (
            "order_es",
            _day(19),
            (
                "Auriculares inalámbricos con cancelación de ruido, Bluetooth 5.3,"
                " negro",
                "Funda de silicona para auriculares, azul",
            ),
        ),
        (
            "order_en_us",
            _day(20),
            (
                "Stainless Steel Insulated Water Bottle, 32 oz, Matte Black",
                "Silicone Straw Lid Replacement, 2 Pack",
            ),
        ),
    ],
)
def test_order_confirmation(
    parse: Parse, name: str, eta: Eta, items: tuple[str, ...]
) -> None:
    """An order has one ORDER shipment with the estimate; no recommendations."""
    result = parse(name)
    assert result.items == items
    [shipment] = result.shipments
    assert shipment.kind is MailKind.ORDER
    assert shipment.eta == eta
    assert shipment.items == items
    assert shipment.carrier is None
    assert shipment.tracking_number is None
    assert shipment.amazon_shipment_id is None
    assert shipment.tracking_url is None


def test_order_in_several_deliveries(parse: Parse) -> None:
    """An order arriving in two deliveries has one ORDER shipment for each."""
    result = parse("order_multi_pt")
    assert len(result.items) == 3
    assert [
        (shipment.kind, shipment.eta, shipment.items) for shipment in result.shipments
    ] == [
        (
            MailKind.ORDER,
            _day(19),
            (
                "Cafeteira de cápsulas compacta, 1 litro, preta",
                "Cápsulas de café intenso, pack de 50",
            ),
        ),
        (MailKind.ORDER, _day(23), ("Moinho de café manual em aço inoxidável",)),
    ]


def test_arriving_today_with_time_window(parse: Parse) -> None:
    """ "Arriving today 10:00-14:00" sets today's date and the window."""
    [shipment] = parse("arriving_today_it").shipments
    assert shipment.amazon_shipment_id == "Hn3VbT9sK"
    assert shipment.eta == Eta(
        date(2026, 11, 18), date(2026, 11, 18), time(10, 0), time(14, 0)
    )
    assert shipment.items == ("Set di pentole antiaderenti, 10 pezzi, induzione",)


@pytest.mark.parametrize(
    ("name", "event", "eta"),
    [
        ("delivered_photo_es", (17, 10, 42), None),
        ("attempted_fr", (19, 14, 5), _day(20)),
        ("attempted_it", (17, 18, 20), _day(19)),
    ],
)
def test_event_time_from_text(
    parse: Parse, tz: ZoneInfo, name: str, event: tuple[int, int, int], eta: Eta | None
) -> None:
    """The stated event time is kept; a failed attempt has a new estimate."""
    [shipment] = parse(name).shipments
    day, hour, minute = event
    assert shipment.event_time == datetime(2026, 11, day, hour, minute, tzinfo=tz)
    assert shipment.eta == eta


def test_carrier_named_in_email(parse: Parse) -> None:
    """A parcel handed to CTT gets CTT's tracking number and tracking page."""
    [shipment] = parse("shipped_ctt_pt").shipments
    assert shipment.carrier == "ctt"
    assert shipment.tracking_number == "RR473124829PT"
    assert shipment.amazon_shipment_id == "Fk7tQ2LmZ"
    assert shipment.tracking_url == tracking.tracking_url("ctt", "RR473124829PT")
    assert shipment.eta == _day(20)


@pytest.mark.parametrize(
    ("name", "point", "code", "event"),
    [
        (
            "pickup_locker_pt",
            "Amazon Locker - Exemplo, Rua Exemplo 1, Lisboa",
            "482915",
            (17, 9, 15),
        ),
        (
            "pickup_counter_en_uk",
            "Amazon Counter \u2013 Example Store, 1 Example Road, London",
            "7KD3Q9",
            None,
        ),
    ],
)
def test_ready_for_pickup(
    parse: Parse,
    tz: ZoneInfo,
    name: str,
    point: str,
    code: str,
    event: tuple[int, int, int] | None,
) -> None:
    """Pickup e-mails carry the pickup point and code."""
    [shipment] = parse(name).shipments
    assert shipment.carrier == "amazon"
    assert shipment.pickup_point == point
    assert shipment.pickup_code == code
    assert shipment.eta is None
    expected = datetime(2026, 11, *event, tzinfo=tz) if event else None
    assert shipment.event_time == expected


@pytest.mark.parametrize(
    ("name", "item"),
    [
        ("cancelled_it", "Cuscino memory foam ergonomico"),
        ("cancelled_nl", "Bureaustoel met lendensteun, zwart"),
        ("refund_de", "Bluetooth-Kopfhörer, Over-Ear, kabellos, schwarz"),
        ("refund_es", "Taza térmica de acero inoxidable, 450 ml"),
    ],
)
def test_cancelled_and_refunded(parse: Parse, name: str, item: str) -> None:
    """Cancellations and refunds have one bare shipment for the order."""
    result = parse(name)
    assert result.items == (item,)
    [shipment] = result.shipments
    assert shipment.kind is None
    assert shipment.carrier is None
    assert shipment.tracking_number is None
    assert shipment.amazon_shipment_id is None
    assert shipment.eta is None


@pytest.mark.parametrize("name", ["marketing_es", "changed_layout_pt"])
def test_unreadable_returns_none(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    name: str,
) -> None:
    """Marketing and an unknown layout aren't parsed."""
    message = load_eml(f"amazon/{name}.eml")
    assert parse_amazon(message, verdict_for(message), tz) is None


def _moved_links(message: MailMessage, old: str, new: str) -> MailMessage:
    """Return the message with its links, and the targets they wrap, moved."""
    links = tuple(
        Link(
            link.url.replace(old, new).replace(
                quote(old, safe=""), quote(new, safe="")
            ),
            link.text,
        )
        for link in message.links
    )
    return dataclasses.replace(message, links=links)


@pytest.mark.parametrize(
    "new_prefix",
    ["https://www.amazon.de.example.net/", "http://www.amazon.de/"],
)
def test_tracking_url_only_from_own_https_links(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    new_prefix: str,
) -> None:
    """Links on other domains or without https are never copied."""
    message = load_eml("amazon/shipped_de.eml")
    verdict = verdict_for(message)
    message = _moved_links(message, "https://www.amazon.de/", new_prefix)
    result = parse_amazon(message, verdict, tz)
    assert result is not None
    assert [shipment.tracking_url for shipment in result.shipments] == [None]


def test_unverified_sender_gets_no_link(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """An unauthenticated look-alike is parsed, but none of its links is kept."""
    message = load_eml("amazon/shipped_de.eml")
    verdict = dataclasses.replace(verdict_for(message), authenticated=False)
    result = parse_amazon(message, verdict, tz)
    assert result is not None
    assert result.kind is MailKind.SHIPPED
    [shipment] = result.shipments
    assert shipment.amazon_shipment_id == "DqWzN8xKb"
    assert shipment.tracking_url is None
