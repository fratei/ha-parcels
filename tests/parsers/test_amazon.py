"""Tests for the Amazon e-mail parser."""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
from datetime import date, datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.const import CONFIDENCE_APPLY, MailKind, ParcelStatus
from custom_components.parcels.convert import result_contributions
from custom_components.parcels.dedup import apply_contribution, reconcile
from custom_components.parcels.models import ParcelsData, Source
from custom_components.parcels.parsers import tracking
from custom_components.parcels.parsers.amazon import parse_amazon
from custom_components.parcels.parsers.base import (
    Eta,
    Link,
    MailMessage,
    ParseResult,
    SenderVerdict,
    shipment_base,
)
from custom_components.parcels.parsers.items import same_item

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
        ("order_pedido_pt", MailKind.ORDER, "pt", "406-2958173-6604821"),
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
        (
            "shipped_recommendations_es",
            MailKind.SHIPPED,
            "es",
            "405-7263918-4410392",
        ),
        (
            "shipped_recommendations_pt",
            MailKind.SHIPPED,
            "pt",
            "406-3917452-8803164",
        ),
        ("shipped_duplicate_item_pt", MailKind.SHIPPED, "pt", "406-8264017-3359120"),
        ("delivery_code_es", MailKind.CODE, "es", "405-5190372-2286401"),
        (
            "out_for_delivery_code_pt",
            MailKind.OUT_FOR_DELIVERY,
            "pt",
            "406-2750193-9918274",
        ),
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
            [("Mx8RbQ2zL", _day(19)), ("Nz3TcW6yH#1", _day(21))],
        ),
        ("out_for_delivery_fr", "fr", [("Wm6KcY2pD", _day(19))]),
        ("delayed_en_us", "com", [("Ks5RtW2nY", _day(20))]),
        ("delayed_de", "de", [("Rj4MxB7qT", _day(21))]),
        ("delivered_nl", "nl", [("Pv2LnR8cJ", None)]),
    ],
)
def test_amazon_shipments(
    parse: Parse, name: str, tld: str, expected: list[tuple[str, Eta | None]]
) -> None:
    """Shipment IDs come from the "Track package" links, one per package.

    A package after a shipment's first adds its index to the ID. Amazon
    hands parcels to other carriers too, so the carrier stays unknown when
    the e-mail doesn't name one, and the Amazon link is kept.
    """
    result = parse(name)
    order = result.order_numbers[0]
    assert [
        (shipment.amazon_shipment_id, shipment.eta) for shipment in result.shipments
    ] == expected
    for index, shipment in enumerate(result.shipments):
        assert shipment.kind is None
        assert shipment.carrier is None
        assert shipment.tracking_number is None
        assert shipment.event_time is None
        assert shipment.amazon_shipment_id is not None
        assert shipment.tracking_url == (
            f"https://www.amazon.{tld}/progress-tracker/package?orderId={order}"
            f"&shipmentId={shipment_base(shipment.amazon_shipment_id)}"
            f"&packageIndex={index}"
        )


def _package(message: MailMessage, index: str) -> MailMessage:
    """Return the message with its links about another package of the shipment."""
    return _moved_links(message, "&packageIndex=0", f"&packageIndex={index}")


@pytest.mark.parametrize(
    ("name", "shipment", "number", "url"),
    [
        (
            "shipped_de",
            "DqWzN8xKb",
            None,
            "https://www.amazon.de/progress-tracker/package"
            "?orderId=303-5928471-2039485&shipmentId=DqWzN8xKb&packageIndex=1",
        ),
        (
            "shipped_ctt_pt",
            "Fk7tQ2LmZ",
            "RR473124829PT",
            tracking.tracking_url("ctt", "RR473124829PT"),
        ),
    ],
)
def test_boxes_of_a_shipment_are_apart(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    name: str,
    shipment: str,
    number: str | None,
    url: str,
) -> None:
    """A shipment's second box is told apart from its first by its index.

    The first box keeps the bare shipment ID, as before; the others add
    their index, and their links keep it.
    """
    message = load_eml(f"amazon/{name}.eml")
    verdict = verdict_for(message)
    first = parse_amazon(message, verdict, tz)
    second = parse_amazon(_package(message, "1"), verdict, tz)
    assert first is not None
    assert second is not None
    [one] = first.shipments
    [two] = second.shipments
    assert one.amazon_shipment_id == shipment
    assert two.amazon_shipment_id == f"{shipment}#1"
    assert one.tracking_number == two.tracking_number == number
    assert two.tracking_url == url


def test_boxes_of_a_shipment_in_one_email(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """An e-mail about two boxes of one shipment gives two packages."""
    message = load_eml("amazon/shipped_two_packages_en_us.eml")
    verdict = verdict_for(message)
    message = _moved_links(message, "shipmentId=Nz3TcW6yH", "shipmentId=Mx8RbQ2zL")
    result = parse_amazon(message, verdict, tz)
    assert result is not None
    assert [s.amazon_shipment_id for s in result.shipments] == [
        "Mx8RbQ2zL",
        "Mx8RbQ2zL#1",
    ]
    assert [s.tracking_url for s in result.shipments] == [
        "https://www.amazon.com/progress-tracker/package"
        f"?orderId=114-5938201-7362514&shipmentId=Mx8RbQ2zL&packageIndex={index}"
        for index in range(2)
    ]


def test_box_link_without_index_is_the_same_box(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """A link to the shipment without an index is about the box the e-mail is."""
    message = load_eml("amazon/shipped_de.eml")
    verdict = verdict_for(message)
    message = _package(message, "1")
    plain = Link(
        "https://www.amazon.de/progress-tracker/package"
        "?orderId=303-5928471-2039485&shipmentId=DqWzN8xKb",
        "Lieferung verfolgen",
    )
    message = dataclasses.replace(message, links=(*message.links, plain))
    result = parse_amazon(message, verdict, tz)
    assert result is not None
    assert [s.amazon_shipment_id for s in result.shipments] == ["DqWzN8xKb#1"]


@pytest.mark.parametrize("index", ["x", "1234", "-1", "1&packageIndex=2"])
def test_unreadable_box_index_is_ignored(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    index: str,
) -> None:
    """An index that isn't a small number, or two different indexes, leave the
    shipment ID as it is."""
    message = load_eml("amazon/shipped_de.eml")
    result = parse_amazon(_package(message, index), verdict_for(message), tz)
    assert result is not None
    assert [s.amazon_shipment_id for s in result.shipments] == ["DqWzN8xKb"]


@pytest.mark.parametrize(
    ("extra", "number"),
    [
        ("Entregado por Amazon Logistics.", None),
        ("ID de seguimiento: TBA312345678901", "TBA312345678901"),
    ],
)
def test_amazon_logistics_named(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    extra: str,
    number: str | None,
) -> None:
    """Amazon's own delivery service counts when named or by its number."""
    message = load_eml("amazon/delivered_photo_es.eml")
    message = dataclasses.replace(message, text=f"{message.text}\n{extra}\n")
    result = parse_amazon(message, verdict_for(message), tz)
    assert result is not None
    [shipment] = result.shipments
    assert shipment.carrier == "amazon"
    assert shipment.tracking_number == number
    assert shipment.amazon_shipment_id == "Tq8ZmX3vB"
    assert shipment.tracking_url is not None
    assert shipment.tracking_url.startswith("https://www.amazon.es/progress-tracker/")


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
        (
            "order_pedido_pt",
            Eta(date(2026, 12, 7), date(2026, 12, 7)),
            (
                "Candeeiro de mesa Exemplo, LED, regulável, branco",
                "Lâmpada LED E27 Exemplo, 9 W, pack de 2",
                "Extensão elétrica Exemplo com 3 tomadas",
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


@pytest.mark.parametrize(
    "subject",
    [
        "Pedido recebido: \u201cCandeeiro de mesa Exemplo\u2026\u201d",
        "Pedido confirmado: \u201cCandeeiro de mesa Exemplo\u2026\u201d",
        "Pedido realizado",
        "Pedido: \u201cCandeeiro de mesa Exemplo\u2026\u201d e mais 2 produtos",
        "Confirmação do seu pedido",
        "Confirmação do pedido 406-2958173-6604821",
        "O seu pedido da Amazon.es",
        "Obrigado pelo seu pedido",
    ],
)
def test_portuguese_order_says_pedido(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    subject: str,
) -> None:
    """Amazon's Portuguese e-mails call an order "pedido" as well as "encomenda".

    Words shared with Spanish keep the e-mail's own language.
    """
    message = load_eml("amazon/order_pedido_pt.eml")
    message = dataclasses.replace(message, subject=subject)
    result = parse_amazon(message, verdict_for(message), tz)
    assert result is not None
    assert result.kind is MailKind.ORDER
    assert result.language == "pt"
    assert result.confidence >= max(0.85, CONFIDENCE_APPLY)
    [shipment] = result.shipments
    assert shipment.eta == Eta(date(2026, 12, 7), date(2026, 12, 7))


def test_update_about_the_pedido_reads_its_body(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """Only a subject that starts with "O seu pedido da Amazon" is an order.

    An update about the order further on in the subject is read by its body.
    """
    message = load_eml("amazon/shipped_recommendations_pt.eml")
    message = dataclasses.replace(
        message, subject="Atualização sobre o seu pedido da Amazon.es"
    )
    result = parse_amazon(message, verdict_for(message), tz)
    assert result is not None
    assert result.kind is MailKind.SHIPPED
    assert result.language == "pt"


def test_portuguese_order_by_its_body(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """Under an unknown subject, "Obrigado pelo seu pedido!" is an order."""
    message = load_eml("amazon/order_pedido_pt.eml")
    message = dataclasses.replace(message, subject="Novidades para si")
    result = parse_amazon(message, verdict_for(message), tz)
    assert result is not None
    assert result.kind is MailKind.ORDER
    assert result.language == "pt"
    assert result.order_numbers == ("406-2958173-6604821",)


@pytest.mark.parametrize(
    ("name", "item"),
    [
        (
            "shipped_recommendations_es",
            "Sartén antiadherente de 28 cm con mango ergonómico, apta para inducción",
        ),
        (
            "shipped_recommendations_pt",
            "Frigideira antiaderente de 28 cm com pega ergonómica",
        ),
        (
            "shipped_duplicate_item_pt",
            "Exemplo Frigideira Origem, 24 cm, antiaderente, indução",
        ),
    ],
)
def test_items_are_the_order_lines_once(parse: Parse, name: str, item: str) -> None:
    """Products under "Buy again" or "Inspired by your shopping" aren't items.

    An item named twice, once cut short, is listed once with its full title.
    """
    result = parse(name)
    assert result.items == (item,)
    [shipment] = result.shipments
    assert shipment.items == (item,)


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


type Edit = Callable[[str], str]


@pytest.fixture
def parse_edited(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> Callable[[str, Edit], ParseResult]:
    """Return a helper that parses an Amazon fixture with its text edited."""

    def run(name: str, edit: Edit) -> ParseResult:
        message = load_eml(f"amazon/{name}.eml")
        verdict = verdict_for(message)
        message = dataclasses.replace(message, text=edit(message.text))
        result = parse_amazon(message, verdict, tz)
        assert result is not None
        return result

    return run


def _appended(extra: str) -> Edit:
    return lambda text: f"{text}\n{extra}\n"


def _replaced(edits: dict[str, str]) -> Edit:
    def edit(text: str) -> str:
        for old, new in edits.items():
            assert text.count(old) == 1
            text = text.replace(old, new)
        return text

    return edit


def _amazon_url(tld: str, result: ParseResult, index: int) -> str:
    """Return the cleaned Amazon tracking page of a package."""
    shipment = result.shipments[index].amazon_shipment_id
    assert shipment is not None
    return (
        f"https://www.amazon.{tld}/progress-tracker/package"
        f"?orderId={result.order_numbers[0]}"
        f"&shipmentId={shipment_base(shipment)}"
        f"&packageIndex={index}"
    )


@pytest.mark.parametrize("named", ["Paack", "a transportadora"])
def test_paack_barcode_is_paacks_number(
    parse_edited: Callable[[str, Edit], ParseResult], named: str
) -> None:
    """Amazon gives Paack's label barcode (made up here) as the number."""
    barcode = "534000088812345678"
    result = parse_edited(
        "shipped_ctt_pt",
        _replaced(
            {
                "pela CTT.": f"pela {named}.",
                "Transportadora: CTT": f"Transportadora: {named}",
                "RR473124829PT": barcode,
            }
        ),
    )

    [shipment] = result.shipments
    assert (shipment.carrier, shipment.tracking_number) == ("paack", barcode)
    assert shipment.amazon_shipment_id == "Fk7tQ2LmZ"


@pytest.mark.parametrize(
    ("name", "language", "tld", "carrier", "eta"),
    [
        ("shipped_carrier_pt", "pt", "es", "ctt_expresso", _day(21)),
        ("shipped_carrier_es", "es", "es", "seur", _day(20)),
        ("shipped_carrier_en", "en", "co.uk", "dpd", _day(20)),
        ("shipped_carrier_de", "de", "de", "dhl", _day(20)),
        ("shipped_carrier_fr", "fr", "fr", "colissimo", _day(20)),
        ("shipped_carrier_it", "it", "it", "brt", _day(20)),
        ("shipped_carrier_nl", "nl", "nl", "postnl", _day(20)),
    ],
)
def test_carrier_named_without_number(
    parse: Parse, name: str, language: str, tld: str, carrier: str, eta: Eta
) -> None:
    """The carrier an e-mail names is kept even without its tracking number.

    Until the carrier's number is known, Amazon's tracking page is the link.
    """
    result = parse(name)
    assert result.kind is MailKind.SHIPPED
    assert result.language == language
    [shipment] = result.shipments
    assert shipment.carrier == carrier
    assert shipment.tracking_number is None
    assert shipment.eta == eta
    assert shipment.tracking_url == _amazon_url(tld, result, 0)


def test_each_package_has_the_carrier_of_its_block(parse: Parse) -> None:
    """Packages handed to different carriers each get their own carrier.

    A tracking number in one package's block belongs to that package only.
    """
    result = parse("shipped_two_carriers_es")
    first, second = result.shipments
    assert (first.carrier, first.tracking_number, first.eta) == ("seur", None, _day(20))
    assert first.tracking_url == _amazon_url("es", result, 0)
    assert first.items == ("Zapatillas de running para hombre, talla 43, gris",)
    assert (second.carrier, second.tracking_number, second.eta) == (
        "ups",
        "1ZWMGWFD4777499550",
        _day(23),
    )
    assert second.tracking_url == tracking.tracking_url("ups", "1ZWMGWFD4777499550")
    assert second.items == ("Calcetines deportivos transpirables, pack de 3",)


def test_carriers_of_the_whole_order_are_not_guessed(parse: Parse) -> None:
    """Carriers named for the whole order aren't given to any one package."""
    result = parse("shipped_carrier_ambiguous_en")
    assert [(s.carrier, s.tracking_number) for s in result.shipments] == [
        (None, None),
        (None, None),
    ]
    assert [s.tracking_url for s in result.shipments] == [
        _amazon_url("co.uk", result, index) for index in range(2)
    ]


@pytest.mark.parametrize(
    ("name", "extra", "carrier"),
    [
        ("shipped_en_uk", "Carrier: DPD", "dpd"),
        ("shipped_en_uk", "Courier \u2013 Evri", "evri"),
        ("delayed_en_us", "Your package will be delivered by UPS.", "ups"),
        ("delayed_en_us", "Shipped with USPS", "usps"),
        ("shipped_recommendations_pt", "Transportadora: CTT", "ctt"),
        ("shipped_recommendations_pt", "Transportadora:\nCTT Expresso", "ctt_expresso"),
        (
            "shipped_duplicate_item_pt",
            "A sua encomenda será entregue pela CTT Expresso.",
            "ctt_expresso",
        ),
        (
            "shipped_recommendations_es",
            "Transportista: Correos Express",
            "correos_express",
        ),
        ("delivered_photo_es", "Entregado por Correos.", "correos"),
        ("shipped_de", "Versanddienstleister: Hermes", "hermes"),
        ("shipped_de", "Ihr Paket wird von DPD zugestellt.", "dpd"),
        ("delayed_de", "Zustellung durch GLS", "gls"),
        ("out_for_delivery_fr", "Transporteur : Chronopost", "chronopost"),
        ("attempted_fr", "Votre colis est acheminé par La Poste.", "la_poste"),
        ("arriving_today_it", "Corriere: SDA", "sda"),
        (
            "attempted_it",
            "Il pacco sarà consegnato dal corriere Poste Italiane.",
            "poste_italiane",
        ),
        ("delivered_nl", "Vervoerder: PostNL", "postnl"),
        ("delivered_nl", "Je pakket is door DPD bezorgd.", "dpd"),
    ],
)
def test_carrier_named_by_label_or_verb(
    parse_edited: Callable[[str, Edit], ParseResult],
    name: str,
    extra: str,
    carrier: str,
) -> None:
    """A carrier counts after a carrier label or a delivery verb."""
    result = parse_edited(name, _appended(extra))
    [shipment] = result.shipments
    assert shipment.carrier == carrier
    assert shipment.tracking_number is None
    assert shipment.tracking_url is not None
    assert "/progress-tracker/package?" in shipment.tracking_url


@pytest.mark.parametrize(
    ("name", "extra"),
    [
        ("shipped_en_uk", "Sold by Amazon EU S.à r.l."),
        ("shipped_en_uk", "Dispatched from and sold by Amazon."),
        ("shipped_en_uk", "Sold by: DPD Outlet Store"),
        ("shipped_en_uk", "Dispatched by: GLS Shop"),
        ("shipped_en_uk", "Your parcel will be delivered by DPD or Evri."),
        ("shipped_en_uk", "Carrier: DPD\nCourier: Evri"),
        ("shipped_en_uk", "Carrier: Amazon"),
        ("shipped_recommendations_pt", "Vendido e enviado por: CTT Loja"),
        ("shipped_recommendations_es", "Vendido y enviado por Amazon"),
        ("delivered_photo_es", "Entregado por Amazon Logistics.\nTransportista: SEUR"),
        ("shipped_de", "Verkauf und Versand durch Amazon"),
        ("shipped_de", "Versand durch: DHL Shop"),
        ("out_for_delivery_fr", "Expédié par : Chronopost Boutique"),
        ("arriving_today_it", "Venduto e spedito da: BRT Store"),
        ("arriving_today_it", "Corriere della Sera"),
        ("delivered_nl", "Verkocht en verzonden door: GLS Winkel"),
    ],
)
def test_no_carrier_from_sellers_or_conflicts(
    parse_edited: Callable[[str, Edit], ParseResult], name: str, extra: str
) -> None:
    """Sellers aren't carriers, and conflicting carriers leave it unknown."""
    result = parse_edited(name, _appended(extra))
    [shipment] = result.shipments
    assert shipment.carrier is None
    assert shipment.tracking_number is None


_NUMBER = "1ZWMGWFD4777499550"


@pytest.mark.parametrize(
    ("edits", "expected"),
    [
        (
            {
                "Package 1 of 2\n": "Package 1 of 2\nCarrier: UPS\n",
                "Package 2 of 2\n": "Package 2 of 2\nCarrier: DPD\n",
            },
            [("ups", None), ("dpd", None)],
        ),
        (
            {"Package 2 of 2\n": "Package 2 of 2\nShipped with USPS\n"},
            [(None, None), ("usps", None)],
        ),
        (
            {"Package 1 of 2\n": "Package 1 of 2\nCarrier: UPS\nCourier: DPD\n"},
            [(None, None), (None, None)],
        ),
        (
            {"Package 1 of 2\n": "Delivered by UPS.\nPackage 1 of 2\n"},
            [(None, None), (None, None)],
        ),
        (
            {"Package 1 of 2\n": f"Package 1 of 2\nUPS tracking number: {_NUMBER}\n"},
            [("ups", _NUMBER), (None, None)],
        ),
        (
            {
                "Package 1 of 2\n": f"Package 1 of 2\nTracking number: {_NUMBER}\n",
                "Package 2 of 2\n": f"Package 2 of 2\nTracking number: {_NUMBER}\n",
            },
            [(None, None), (None, None)],
        ),
        (
            {
                "Package 1 of 2\n": (
                    f"Package 1 of 2\nTracking number: {_NUMBER}\n"
                    "Tracking number: 1ZDKWG7R3659985008\n"
                )
            },
            [(None, None), (None, None)],
        ),
        (
            {"Package 1 of 2\n": "Delivered by Amazon Logistics.\nPackage 1 of 2\n"},
            [("amazon", None), ("amazon", None)],
        ),
    ],
)
def test_carrier_and_number_per_package(
    parse_edited: Callable[[str, Edit], ParseResult],
    edits: dict[str, str],
    expected: list[tuple[str | None, str | None]],
) -> None:
    """A package gets a carrier or number only from its own block."""
    result = parse_edited("shipped_two_packages_en_us", _replaced(edits))
    assert [(s.carrier, s.tracking_number) for s in result.shipments] == expected
    for index, (carrier, number) in enumerate(expected):
        url = (
            tracking.tracking_url(carrier, number)
            if carrier is not None and number is not None
            else _amazon_url("com", result, index)
        )
        assert result.shipments[index].tracking_url == url


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
    assert shipment.carrier is None
    assert shipment.pickup_point == point
    assert shipment.pickup_code == code
    assert shipment.eta is None
    expected = datetime(2026, 11, *event, tzinfo=tz) if event else None
    assert shipment.event_time == expected


def test_delivery_code_only(parse: Parse) -> None:
    """An e-mail with only a delivery code adds it to the order's package."""
    result = parse("delivery_code_es")
    assert result.confidence >= CONFIDENCE_APPLY
    assert result.items == ()
    [shipment] = result.shipments
    assert shipment.kind is MailKind.CODE
    assert shipment.pickup_code == "739215"
    assert shipment.amazon_shipment_id == "Ts9KdM2xQ"
    assert shipment.carrier is None
    assert shipment.tracking_number is None
    assert shipment.eta is None
    assert shipment.event_time is None


def test_delivery_code_needs_an_order_or_a_package(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """A code that names neither an order nor a package isn't read."""
    message = load_eml("amazon/delivery_code_es.eml")
    verdict = verdict_for(message)
    result = parse_amazon(message, verdict, tz)
    assert result is not None
    assert result.kind is MailKind.CODE
    bare = dataclasses.replace(
        message, text="Hola:\nTu código de entrega es 739215.\n", links=()
    )
    assert parse_amazon(bare, verdict, tz) is None


def test_status_with_delivery_code(parse: Parse) -> None:
    """A status e-mail keeps its kind and carries the delivery code."""
    result = parse("out_for_delivery_code_pt")
    [shipment] = result.shipments
    assert shipment.kind is None
    assert shipment.pickup_code == "4821"
    assert shipment.amazon_shipment_id == "Wm5RbQ7tL"
    assert shipment.eta == Eta(
        date(2026, 11, 20), date(2026, 11, 20), None, time(21, 0)
    )


@pytest.mark.parametrize(
    ("line", "number"),
    [
        ("Entregue pela CTT.\nCódigo de entrega: 7391520486", None),
        (
            "Entregue pela CTT, objeto RR482915732PT.\n"
            "Código de entrega do objeto RR482915732PT: 7391520486",
            "RR482915732PT",
        ),
    ],
)
def test_delivery_code_is_no_tracking_number(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    line: str,
    number: str | None,
) -> None:
    """A PIN shaped like a CTT number isn't one, and a number isn't the PIN."""
    message = load_eml("amazon/out_for_delivery_code_pt.eml")
    text = message.text.replace("Código de entrega: 4821", line)
    message = dataclasses.replace(message, text=text)
    result = parse_amazon(message, verdict_for(message), tz)
    assert result is not None
    assert result.order_numbers == ("406-2750193-9918274",)
    [shipment] = result.shipments
    assert shipment.pickup_code == "7391520486"
    assert shipment.tracking_number == number


@pytest.mark.parametrize("index", ["0", "1"])
def test_shipment_id_is_no_tracking_number(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    index: str,
) -> None:
    """A shipment ID written in the e-mail isn't a tracking number, even when
    it's shaped like one, whatever box of the shipment the e-mail is about."""
    message = load_eml("amazon/shipped_de.eml")
    message = _moved_links(message, "shipmentId=DqWzN8xKb", "shipmentId=RR482915732PT")
    message = _package(message, index)
    text = f"{message.text}\nSendung: RR482915732PT\n"
    message = dataclasses.replace(message, text=text)
    result = parse_amazon(message, verdict_for(message), tz)
    assert result is not None
    [shipment] = result.shipments
    assert shipment.amazon_shipment_id == (
        "RR482915732PT" if index == "0" else "RR482915732PT#1"
    )
    assert shipment.tracking_number is None


@pytest.mark.parametrize("index", ["0", "1"])
def test_shipment_id_is_no_delivery_code(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    index: str,
) -> None:
    """A shipment ID after a code label isn't the delivery code, whatever box
    of the shipment the e-mail is about."""
    message = load_eml("amazon/out_for_delivery_code_pt.eml")
    message = _package(message, index)
    text = message.text.replace(
        "Código de entrega: 4821", "Código de entrega: Wm5RbQ7tL"
    )
    message = dataclasses.replace(message, text=text)
    result = parse_amazon(message, verdict_for(message), tz)
    assert result is not None
    [shipment] = result.shipments
    assert shipment.amazon_shipment_id == (
        "Wm5RbQ7tL" if index == "0" else "Wm5RbQ7tL#1"
    )
    assert shipment.pickup_code is None


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


_US_ORDER = "112-4839201-5938472"


@pytest.mark.parametrize(
    ("subject", "text"),
    [
        (
            f"Your Amazon.com order {_US_ORDER} has been canceled",
            f"Hello Alex,\nYour order {_US_ORDER} has been canceled.\n"
            "Stainless Steel Insulated Water Bottle, 32 oz, Ma...\nQuantity: 1\n"
            "Silicone Straw Lid Replacement, 2...\nQuantity: 1\n",
        ),
        (
            'Canceled: "Stainless Steel Insulated Water Bottle..." and 1 more item',
            f"Hello Alex,\nYour order {_US_ORDER} has been canceled.\n",
        ),
    ],
    ids=["body", "subject"],
)
def test_a_cancellation_with_titles_cut_short_cancels_the_order(
    parse: Parse,
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    subject: str,
    text: str,
) -> None:
    """Amazon cuts titles short in other places than the order e-mail did;
    the cancellation is about the same items, so it cancels the order's
    parcel instead of becoming a parcel of its own."""
    ordered = load_eml("amazon/order_en_us.eml")
    message = dataclasses.replace(
        ordered,
        subject=subject,
        text=text,
        links=(),
        date=ordered.date + timedelta(hours=3),
    )
    cancelled = parse_amazon(message, verdict_for(message), tz)
    assert cancelled is not None
    assert cancelled.kind is MailKind.CANCELLED
    order = parse("order_en_us")
    assert cancelled.items
    for item in cancelled.items:
        assert any(same_item(item, full) for full in order.items), item

    data = ParcelsData()
    for name, result, sent in (
        ("order", order, ordered.date),
        ("cancel", cancelled, message.date),
    ):
        [contrib] = result_contributions(
            result, message_hash=name, time=sent, source=Source.PARSER
        )
        apply_contribution(data, contrib, sent)
    reconcile(data, message.date)
    [parcel] = data.parcels.values()
    assert parcel.state.status is ParcelStatus.CANCELLED


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
