"""Tests for the Shopify store and Shop app e-mail parsers."""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.const import CONFIDENCE_APPLY, MailKind
from custom_components.parcels.parsers import tracking
from custom_components.parcels.parsers.base import (
    Eta,
    Link,
    MailMessage,
    ParseResult,
    SenderVerdict,
)
from custom_components.parcels.parsers.shopify import parse_shop, parse_shopify

type Parse = Callable[[str], ParseResult]

STORES = {
    "pt": "Loja Exemplo",
    "es": "Tienda Ejemplo",
    "en": "Example Outfitters",
    "de": "Beispiel Laden",
    "fr": "Boutique Exemple",
    "it": "Negozio Esempio",
    "nl": "Winkel Voorbeeld",
}
ORDER_ITEMS = {
    "pt": ("Vela aromática de soja, lavanda", "Difusor de aromas em cerâmica"),
    "es": ("Taza de cerámica esmaltada", "Plato llano de gres"),
    "en": ("Merino Wool Beanie", "Waxed Cotton Jacket"),
    "de": ("Schneidebrett aus Eichenholz", "Leinen-Geschirrtuch, 2er-Set"),
    "fr": ("Carnet en papier recyclé A5", "Stylo plume en laiton"),
    "it": ("Caffè in grani, miscela classica 1 kg", "Moka in alluminio, 6 tazze"),
    "nl": ("Plantenpot van terracotta, 18 cm", "Gieter van gegalvaniseerd staal"),
}


def _day(day: int) -> Eta:
    """Return a one-day estimate in November 2026."""
    return Eta(date(2026, 11, day), date(2026, 11, day))


@pytest.fixture
def parse(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> Parse:
    """Return a helper that parses a fixture with the parser for its folder."""

    def run(path: str) -> ParseResult:
        message = load_eml(f"{path}.eml")
        verdict = verdict_for(message)
        assert verdict.verified
        parser = parse_shop if path.startswith("shop/") else parse_shopify
        result = parser(message, verdict, tz)
        assert result is not None
        return result

    return run


def _assert_tracked(result: ParseResult, carrier: str, number: str) -> None:
    """Assert one shipment with a validated number and its tracking page."""
    [shipment] = result.shipments
    assert shipment.carrier == carrier
    assert shipment.tracking_number == number
    assert tracking.validate_tracking_number(number, carrier)
    assert shipment.tracking_url == tracking.tracking_url(carrier, number)
    assert shipment.kind is None
    assert shipment.order_numbers == result.order_numbers


@pytest.mark.parametrize(
    ("lang", "order", "eta"),
    [
        ("pt", "#1001", None),
        ("es", "#2047", _day(19)),
        ("en", "#1052", None),
        ("de", "#1203", None),
        ("fr", "#3310", None),
        ("it", "#4521", None),
        ("nl", "#5610", None),
    ],
)
def test_order_confirmation(
    parse: Parse, lang: str, order: str, eta: Eta | None
) -> None:
    """Order confirmations in every language have one ORDER shipment."""
    result = parse(f"shopify/order_{lang}")
    assert result.parser == "shopify"
    assert result.kind is MailKind.ORDER
    assert result.language == lang
    assert result.merchant == STORES[lang]
    assert result.order_numbers == (order,)
    assert result.items == ORDER_ITEMS[lang]
    assert result.confidence >= max(0.85, CONFIDENCE_APPLY)
    [shipment] = result.shipments
    assert shipment.kind is MailKind.ORDER
    assert shipment.eta == eta
    assert shipment.carrier is None
    assert shipment.tracking_number is None
    assert shipment.tracking_url is None
    assert shipment.order_numbers == (order,)
    assert shipment.items == ORDER_ITEMS[lang]


@pytest.mark.parametrize(
    ("lang", "order", "carrier", "number", "eta"),
    [
        ("pt", "#1001", "ctt", "RR123456785PT", None),
        ("es", "#2047", "dpd", "01906004718236", None),
        ("en", "#1052", "ups", "1Z999AA10123456784", _day(19)),
        ("de", "#1203", "dpd", "01906004718250", None),
        ("fr", "#3310", "colissimo", "CP718304267FR", None),
        ("it", "#4521", "ups", "1Z5R89390357567127", None),
        ("nl", "#5610", "postnl", "3SWVBX0451239", None),
    ],
)
def test_shipping_confirmation(
    parse: Parse, lang: str, order: str, carrier: str, number: str, eta: Eta | None
) -> None:
    """Shipping confirmations carry the carrier and its validated number."""
    result = parse(f"shopify/shipped_{lang}")
    assert result.kind is MailKind.SHIPPED
    assert result.language == lang
    assert result.merchant == STORES[lang]
    assert result.order_numbers == (order,)
    assert result.confidence >= 0.85
    _assert_tracked(result, carrier, number)
    [shipment] = result.shipments
    assert shipment.eta == eta
    assert shipment.event_time is None
    assert shipment.items == ORDER_ITEMS[lang]


@pytest.mark.parametrize(
    ("name", "kind", "order", "carrier", "number", "eta", "items"),
    [
        (
            "out_for_delivery_pt",
            MailKind.OUT_FOR_DELIVERY,
            "#1008",
            "ctt",
            "LA908172638PT",
            _day(19),
            ("Vela aromática de soja, baunilha",),
        ),
        (
            "out_for_delivery_es",
            MailKind.OUT_FOR_DELIVERY,
            "#2051",
            "correos",
            "PQ4B7C0712345670128001L",
            _day(19),
            ("Jarra de cerámica, 1 litro",),
        ),
        (
            "delivered_en",
            MailKind.DELIVERED,
            "#1060",
            "royal_mail",
            "TT405182734GB",
            None,
            ("Leather Card Holder",),
        ),
        (
            "delivered_de",
            MailKind.DELIVERED,
            "#1203",
            "dpd",
            "01906004718250",
            None,
            ORDER_ITEMS["de"],
        ),
        (
            "shipping_update_en",
            MailKind.IN_TRANSIT,
            "#1052",
            "ups",
            "1Z999AA10123456784",
            _day(20),
            ORDER_ITEMS["en"],
        ),
    ],
)
def test_status_update(
    parse: Parse,
    name: str,
    kind: MailKind,
    order: str,
    carrier: str,
    number: str,
    eta: Eta | None,
    items: tuple[str, ...],
) -> None:
    """Out-for-delivery, delivered and updated shipments are recognised."""
    result = parse(f"shopify/{name}")
    lang = name.rsplit("_", 1)[1]
    assert result.kind is kind
    assert result.language == lang
    assert result.merchant == STORES[lang]
    assert result.order_numbers == (order,)
    assert result.confidence >= 0.85
    _assert_tracked(result, carrier, number)
    [shipment] = result.shipments
    assert shipment.eta == eta
    assert shipment.event_time is None
    assert shipment.items == items


def test_marketing_is_not_parsed(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """A store's newsletter isn't an order or shipping notification."""
    message = load_eml("shopify/marketing_pt.eml")
    assert parse_shopify(message, verdict_for(message), tz) is None


def _replace_everywhere(message: MailMessage, old: str, new: str) -> MailMessage:
    """Return the message with ``old`` replaced in its text and links."""
    return dataclasses.replace(
        message,
        text=message.text.replace(old, new),
        links=tuple(
            Link(link.url.replace(old, new), link.text.replace(old, new))
            for link in message.links
        ),
    )


def test_wrong_check_digit_is_dropped(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """A number that fails the carrier's check digit is never used."""
    message = load_eml("shopify/shipped_pt.eml")
    verdict = verdict_for(message)
    message = _replace_everywhere(message, "RR123456785PT", "RR123456786PT")
    result = parse_shopify(message, verdict, tz)
    assert result is not None
    assert result.kind is MailKind.SHIPPED
    assert result.confidence < 0.85
    [shipment] = result.shipments
    assert shipment.carrier is None
    assert shipment.tracking_number is None
    assert shipment.tracking_url is None
    assert shipment.order_numbers == ("#1001",)


def test_store_name_from_domain(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """Without a display name, the store's name comes from its domain."""
    message = load_eml("shopify/order_pt.eml")
    verdict = verdict_for(message)
    message = dataclasses.replace(message, sender_name="", links=())
    result = parse_shopify(message, verdict, tz)
    assert result is not None
    assert result.merchant == "Loja Exemplo"


def test_sizes_are_not_items(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """Titles may end in a digit; dimensions such as "30 x 40" aren't items."""
    message = load_eml("shopify/order_en.eml")
    verdict = verdict_for(message)
    text = (
        "Order summary\n"
        "Poster 30 x 40 cm \u00d7 1\n"
        "Frame size: 30 x 40\n"
        "Notebook A5 \u00d7 2\n"
        "Subtotal\n"
    )
    result = parse_shopify(dataclasses.replace(message, text=text), verdict, tz)
    assert result is not None
    assert result.items == ("Poster 30 x 40 cm", "Notebook A5")


@pytest.mark.parametrize(
    ("name", "kind", "order", "carrier", "number", "eta", "event", "item"),
    [
        (
            "on_the_way_en",
            MailKind.IN_TRANSIT,
            "#1057",
            "ups",
            "1Z0X118A0398765439",
            _day(19),
            None,
            "Waxed Canvas Weekender Bag",
        ),
        (
            "out_for_delivery_pt",
            MailKind.OUT_FOR_DELIVERY,
            "#1012",
            "ctt",
            "RL528147367PT",
            _day(19),
            None,
            "Vela aromática de soja, canela",
        ),
        (
            "delivered_es",
            MailKind.DELIVERED,
            "#2063",
            "dpd",
            "05212009845376",
            None,
            (19, 12, 31),
            "Cuenco de cerámica artesanal",
        ),
        (
            "arriving_today_de",
            MailKind.OUT_FOR_DELIVERY,
            "#1215",
            "dpd",
            "05212009845413",
            _day(20),
            None,
            "Teekanne aus Gusseisen, 1,2 l",
        ),
        (
            "on_the_way_fr",
            MailKind.IN_TRANSIT,
            "#3318",
            "colissimo",
            "6A19283746501",
            _day(23),
            None,
            "Agenda 2027 relié en lin",
        ),
        (
            "shipped_it",
            MailKind.SHIPPED,
            "#4530",
            "gls",
            "61234567890",
            None,
            None,
            "Macinacaffè manuale in acciaio",
        ),
        (
            "delivered_nl",
            MailKind.DELIVERED,
            "#5622",
            "dhl",
            "JVGL06241736251840",
            None,
            None,
            "Hangplant in macramé hanger",
        ),
    ],
)
def test_shop_app_update(
    parse: Parse,
    tz: ZoneInfo,
    name: str,
    kind: MailKind,
    order: str,
    carrier: str,
    number: str,
    eta: Eta | None,
    event: tuple[int, int, int] | None,
    item: str,
) -> None:
    """Shop app updates name the store the order came from as the merchant."""
    result = parse(f"shop/{name}")
    lang = name.rsplit("_", 1)[1]
    assert result.parser == "shop"
    assert result.kind is kind
    assert result.language == lang
    assert result.merchant == STORES[lang]
    assert result.order_numbers == (order,)
    assert result.confidence >= 0.85
    _assert_tracked(result, carrier, number)
    [shipment] = result.shipments
    assert shipment.eta == eta
    expected = datetime(2026, 11, *event, tzinfo=tz) if event else None
    assert shipment.event_time == expected
    assert shipment.items == (item,)


def test_shop_store_name_does_not_decide_kind(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """A store called "Delivered Goods Co" doesn't make a parcel delivered."""
    message = load_eml("shop/on_the_way_en.eml")
    verdict = verdict_for(message)
    message = dataclasses.replace(
        message, subject="Your order from Delivered Goods Co is on its way"
    )
    result = parse_shop(message, verdict, tz)
    assert result is not None
    assert result.merchant == "Delivered Goods Co"
    assert result.kind is MailKind.IN_TRANSIT


def test_shop_non_delivery_email(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """Shop app e-mails that aren't delivery updates aren't parsed."""
    message = load_eml("shop/on_the_way_en.eml")
    verdict = verdict_for(message)
    message = dataclasses.replace(
        message,
        subject="New arrivals from stores you follow",
        text="See what is new this week.\nOpen the Shop app\n",
        links=(),
    )
    assert parse_shop(message, verdict, tz) is None
