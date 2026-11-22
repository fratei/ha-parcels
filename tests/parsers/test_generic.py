"""Tests for the generic fallback parser."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.const import CONFIDENCE_APPLY, MailKind
from custom_components.parcels.parsers.base import (
    Eta,
    Link,
    MailMessage,
    ParseResult,
    SenderVerdict,
)
from custom_components.parcels.parsers.generic import (
    clean_sender_name,
    detect_kind,
    find_order_numbers,
    parse_generic,
    text_kinds,
)

REF = datetime(2026, 11, 17, 9, 12, tzinfo=UTC)
CTT_URL = (
    "https://www.ctt.pt/feapl_2/app/open/objectSearch/objectSearch.jspx"
    "?objects=RR123456785PT"
)


def _message(
    subject: str,
    text: str,
    *,
    sender: str = "orders@loja-exemplo.example",
    name: str = "Loja Exemplo",
    links: Sequence[Link] = (),
    sent: datetime = REF,
    language: str | None = None,
) -> MailMessage:
    return MailMessage(
        message_id="<synthetic-1@loja-exemplo.example>",
        provider_id="1",
        provider="google",
        mailbox="alex@example.com",
        sender=sender,
        sender_name=name,
        subject=subject,
        date=sent,
        text=text,
        links=tuple(links),
        language=language,
    )


def _parse(message: MailMessage, tz: ZoneInfo) -> ParseResult | None:
    verdict = SenderVerdict(
        domain=message.sender_domain,
        authenticated=True,
        known=False,
        method="dmarc",
        reason="unknown_sender",
    )
    return parse_generic(message, verdict, tz)


def test_small_shop_with_ctt_number(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """A small Portuguese shop sends a CTT S10 number."""
    message = load_eml("common/small_shop_ctt.eml")
    result = parse_generic(message, verdict_for(message), tz)
    assert result is not None
    assert result.parser == "generic"
    assert result.kind is MailKind.SHIPPED
    assert result.merchant == "Loja Exemplo"
    assert result.order_numbers == ("1042",)
    assert result.language == "pt"
    assert result.confidence == 0.8
    [shipment] = result.shipments
    assert shipment.carrier == "ctt"
    assert shipment.tracking_number == "RR123456785PT"
    assert shipment.kind is MailKind.SHIPPED
    assert shipment.eta == Eta(date(2026, 11, 19), date(2026, 11, 19))
    assert shipment.order_numbers == ("1042",)
    assert shipment.tracking_url == CTT_URL


def test_german_shop_with_dhl_link(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """The DHL number comes from the tracking link's query string."""
    message = load_eml("common/german_shop_dhl.eml")
    result = parse_generic(message, verdict_for(message), tz)
    assert result is not None
    assert result.kind is MailKind.SHIPPED
    assert result.merchant == "Beispiel Shop"
    assert result.order_numbers == ("100234",)
    assert result.language == "de"
    assert result.confidence == 0.8
    [shipment] = result.shipments
    assert shipment.carrier == "dhl"
    assert shipment.tracking_number == "00340434161094015902"
    assert shipment.eta == Eta(date(2026, 11, 19), date(2026, 11, 19))
    assert shipment.tracking_url is not None
    assert shipment.tracking_url.startswith("https://")


def test_order_confirmation(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """An order confirmation gives one shipment without a number."""
    message = load_eml("common/order_confirmation.eml")
    result = parse_generic(message, verdict_for(message), tz)
    assert result is not None
    assert result.kind is MailKind.ORDER
    assert result.merchant == "Example Store"
    assert result.order_numbers == ("#1001",)
    assert result.confidence == 0.6
    [shipment] = result.shipments
    assert shipment.tracking_number is None
    assert shipment.kind is MailKind.ORDER
    assert shipment.order_numbers == ("#1001",)


@pytest.mark.parametrize(
    "fixture", ["common/unknown_phone_only.eml", "common/newsletter.eml"]
)
def test_nothing_parcel_like(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    fixture: str,
) -> None:
    """A phone number alone or a newsletter gives nothing."""
    message = load_eml(fixture)
    assert parse_generic(message, verdict_for(message), tz) is None


def test_ready_for_pickup_with_point_and_code(tz: ZoneInfo) -> None:
    """Pickup point and code are read from their labels."""
    message = _message(
        "A sua encomenda está disponível para levantamento",
        "Olá Alex,\nA sua encomenda RR123456785PT está disponível para"
        " levantamento.\nPonto de recolha: Papelaria Exemplo, Rua Exemplo 1\n"
        "Código de levantamento: 482913\nObrigado.",
    )
    result = _parse(message, tz)
    assert result is not None
    assert result.kind is MailKind.READY_FOR_PICKUP
    [shipment] = result.shipments
    assert shipment.pickup_point == "Papelaria Exemplo, Rua Exemplo 1"
    assert shipment.pickup_code == "482913"
    assert shipment.eta is None


def test_pickup_point_on_next_line(tz: ZoneInfo) -> None:
    """A pickup point label alone on a line names the point below it."""
    message = _message(
        "Your parcel is ready for pickup",
        "Hi Alex,\nYour parcel RR123456785PT is ready for pickup.\nPickup point\n"
        "Papelaria Exemplo\nRua Exemplo 1\nPickup code: 482913",
    )
    result = _parse(message, tz)
    assert result is not None
    [shipment] = result.shipments
    assert shipment.pickup_point == "Papelaria Exemplo"
    assert shipment.pickup_code == "482913"


@pytest.mark.parametrize(
    ("subject", "text"),
    [
        (
            "We missed you",
            "We tried to deliver your parcel RR123456785PT but nobody was home."
            "\nCollection point: Papelaria Exemplo, Rua Exemplo 1",
        ),
        (
            "Tentativa de entrega",
            "Tentámos entregar a sua encomenda RR123456785PT.\n"
            "Local de levantamento\nPapelaria Exemplo\nRua Exemplo 1",
        ),
        (
            "Zustellversuch",
            "Ihr Paket RR123456785PT konnte leider nicht zugestellt werden.\n"
            "Abholstelle: Papelaria Exemplo",
        ),
    ],
)
def test_missed_attempt_names_where_it_was_taken(
    subject: str, text: str, tz: ZoneInfo
) -> None:
    """A missed attempt's pickup point label names where the parcel went."""
    result = _parse(_message(subject, text), tz)
    assert result is not None
    assert result.kind is MailKind.ATTEMPTED
    [shipment] = result.shipments
    assert shipment.pickup_point is not None
    assert shipment.pickup_point.startswith("Papelaria Exemplo")


@pytest.mark.parametrize(
    "line",
    [
        "Shop: Loja Exemplo",
        "Loja: Loja Exemplo",
        "Ponto de entrega: Rua Exemplo 1",
        "Punto de entrega: Calle Ejemplo 1",
    ],
)
def test_missed_attempt_shop_or_address_is_no_place(line: str, tz: ZoneInfo) -> None:
    """On a missed attempt a shop row or the delivery address isn't a place."""
    message = _message(
        "We missed you",
        f"We tried to deliver your parcel RR123456785PT.\n{line}",
    )
    result = _parse(message, tz)
    assert result is not None
    assert result.kind is MailKind.ATTEMPTED
    [shipment] = result.shipments
    assert shipment.pickup_point is None


def test_carrier_sender_has_no_merchant(tz: ZoneInfo) -> None:
    """A carrier is not a merchant; a number without check digit caps at 0.5."""
    message = _message(
        "Your parcel is on its way",
        "Your DPD parcel 01234567890123 will be delivered on Thursday,"
        " 19 November between 13:00 and 14:00.",
        sender="notifications@dpd.de",
        name="DPD",
    )
    result = _parse(message, tz)
    assert result is not None
    assert result.merchant is None
    assert result.confidence == 0.5
    [shipment] = result.shipments
    assert shipment.carrier == "dpd"
    assert shipment.tracking_number == "01234567890123"
    assert shipment.eta == Eta(
        date(2026, 11, 19), date(2026, 11, 19), time(13, 0), time(14, 0)
    )


@pytest.mark.parametrize(
    ("subject", "text", "kind", "confidence", "note"),
    [
        (
            "Your order has shipped",
            "Tracking number: RR123456785PT",
            MailKind.SHIPPED,
            0.8,
            "kind_from_subject",
        ),
        (
            "Update on your purchase",
            "Hi Alex,\nYour order has shipped.\nTracking number: RR123456785PT",
            MailKind.SHIPPED,
            0.7,
            "kind_from_body",
        ),
        (
            "Information",
            "Hi Alex,\nTracking number: RR123456785PT",
            MailKind.SHIPPED,
            0.7,
            "kind_default",
        ),
        (
            "Your order has shipped",
            "Tracking number: ABC123456789",
            MailKind.SHIPPED,
            0.5,
            "kind_from_subject",
        ),
    ],
)
def test_confidence(
    tz: ZoneInfo,
    subject: str,
    text: str,
    kind: MailKind,
    confidence: float,
    note: str,
) -> None:
    """0.5 base, +0.2 for a check digit, +0.1 for a subject kind; capped."""
    result = _parse(_message(subject, text), tz)
    assert result is not None
    assert result.kind is kind
    assert result.confidence == confidence
    assert note in result.notes
    assert ("check_digit" in result.notes) is (confidence > 0.6)


def test_one_shipment_per_number_validated_first(tz: ZoneInfo) -> None:
    """Each distinct number is a shipment; check-digit numbers come first."""
    message = _message(
        "Your order has shipped",
        "Your order was sent in two parcels: 01234567890123 (DPD) and"
        " RR123456785PT.\nTracking: DPD 01234567890123",
    )
    result = _parse(message, tz)
    assert result is not None
    assert [(s.carrier, s.tracking_number) for s in result.shipments] == [
        ("ctt", "RR123456785PT"),
        ("dpd", "01234567890123"),
    ]


def test_carrier_from_link_host(tz: ZoneInfo) -> None:
    """A number without its own carrier takes the carrier of the only link."""
    message = _message(
        "Your order has shipped",
        "Tracking number: 12345678901",
        links=[Link("https://gls-group.com/track", "Track your parcel")],
    )
    result = _parse(message, tz)
    assert result is not None
    [shipment] = result.shipments
    assert shipment.carrier == "gls"
    assert shipment.tracking_url == "https://gls-group.com/track/12345678901"


def test_order_kind_kept_with_numbers(tz: ZoneInfo) -> None:
    """An order confirmation that already has a number stays an order."""
    message = _message(
        "Order confirmation",
        "Thanks for your order #1001.\nTracking number: RR123456785PT",
    )
    result = _parse(message, tz)
    assert result is not None
    assert result.kind is MailKind.ORDER
    assert result.order_numbers == ("#1001",)
    assert result.shipments[0].tracking_number == "RR123456785PT"


def test_out_for_delivery_without_date_is_today(tz: ZoneInfo) -> None:
    """Out for delivery means today, in local time."""
    message = _message(
        "Your parcel is out for delivery",
        "Tracking number: RR123456785PT",
        sent=datetime(2026, 7, 14, 23, 30, tzinfo=UTC),
    )
    result = _parse(message, tz)
    assert result is not None
    assert result.shipments[0].eta == Eta(date(2026, 7, 15), date(2026, 7, 15))


def test_no_eta_for_delivered_or_unanchored_dates(tz: ZoneInfo) -> None:
    """Delivered e-mails have no ETA; order and footer dates are not ETAs."""
    delivered = _message(
        "Your parcel has been delivered",
        "Tracking number: RR123456785PT\nEstimated delivery: 19 November",
    )
    footer = _message(
        "Your order has shipped",
        "Order date: 17/11/2026\nTracking number: RR123456785PT\n"
        "© 2026 Loja Exemplo, 20 November",
    )
    for message in (delivered, footer):
        result = _parse(message, tz)
        assert result is not None
        assert result.shipments[0].eta is None


def test_merchant_falls_back_to_domain(tz: ZoneInfo) -> None:
    """A display name with only noise words gives the sender's domain."""
    message = _message(
        "Your order has shipped",
        "Tracking number: RR123456785PT",
        sender="no-reply@mail.loja-exemplo.example",
        name="No-Reply",
    )
    result = _parse(message, tz)
    assert result is not None
    assert result.merchant == "loja-exemplo.example"


def test_carrier_brand_in_shop_sender_name(tz: ZoneInfo) -> None:
    """A shop that sends its carrier's notices names the carrier, not itself.

    The brand in the display name gives the carrier when the number has its
    format; the shop is then named by its domain.
    """
    message = _message(
        "A sua encomenda está a caminho",
        "Olá,\nA sua encomenda 61234567890123 será entregue amanhã.\n"
        "Número de envio: 61234567890123",
        sender="avisos@bricolage-exemplo.example",
        name="GLS PT Informa",
    )
    result = _parse(message, tz)
    assert result is not None
    assert result.merchant == "bricolage-exemplo.example"
    [shipment] = result.shipments
    assert shipment.carrier == "gls"
    assert shipment.tracking_number == "61234567890123"
    assert shipment.tracking_url is not None
    assert "gls" in shipment.tracking_url


def test_carrier_brand_needs_the_carrier_format(tz: ZoneInfo) -> None:
    """A number the named carrier can't have keeps its carrier unknown."""
    message = _message(
        "A sua encomenda está a caminho",
        "Número de envio: ABC123456789",
        sender="avisos@bricolage-exemplo.example",
        name="GLS PT Informa",
    )
    result = _parse(message, tz)
    assert result is not None
    [shipment] = result.shipments
    assert shipment.tracking_number == "ABC123456789"
    assert shipment.carrier is None


# Out-for-delivery e-mails with a delivery PIN or one-time code: subject, body.
STATUS_WITH_CODE = {
    "pt": (
        "A sua encomenda está em distribuição",
        "Olá Alex,\nA sua encomenda RR123456785PT está em distribuição.\n"
        "Código de entrega: 4821\n",
    ),
    "es": (
        "Tu pedido está en reparto",
        "Hola Alex,\nTu pedido RR123456785PT está en reparto.\n"
        "Tu código de entrega es 4821.\n",
    ),
    "en": (
        "Your parcel is out for delivery",
        "Hi Alex,\nYour parcel RR123456785PT is out for delivery today.\n"
        "Your one-time password (OTP) is 4821.\n",
    ),
    "de": (
        "Ihr Paket ist in Zustellung",
        "Hallo Alex,\nIhr Paket RR123456785PT wird heute zugestellt.\n"
        "Ihr Zustellcode lautet: 4821\n",
    ),
    "fr": (
        "Votre colis est en cours de livraison",
        "Bonjour Alex,\nVotre colis RR123456785PT est en cours de livraison.\n"
        "Votre code de livraison est 4821.\n",
    ),
    "it": (
        "Il tuo pacco è in consegna",
        "Ciao Alex,\nIl tuo pacco RR123456785PT è in consegna oggi.\n"
        "Il codice di consegna è 4821.\n",
    ),
    "nl": (
        "Je pakket wordt vandaag bezorgd",
        "Hoi Alex,\nJe pakket RR123456785PT wordt vandaag bezorgd.\n"
        "Je bezorgcode is 4821.\n",
    ),
}


@pytest.mark.parametrize("lang", STATUS_WITH_CODE)
def test_status_email_with_a_code(tz: ZoneInfo, lang: str) -> None:
    """A delivery code next to a status is kept, and the status too."""
    subject, text = STATUS_WITH_CODE[lang]
    result = _parse(_message(subject, text), tz)
    assert result is not None
    assert result.kind is MailKind.OUT_FOR_DELIVERY
    assert result.language == lang
    [shipment] = result.shipments
    assert shipment.kind is MailKind.OUT_FOR_DELIVERY
    assert shipment.tracking_number == "RR123456785PT"
    assert shipment.pickup_code == "4821"


# E-mails whose only news is a code: subject, body, tracking and order numbers.
CODE_ONLY = {
    "pt": (
        "Código de entrega da sua encomenda",
        "Olá Alex,\nO código de entrega da sua encomenda RR123456785PT é 4821.\n",
        "RR123456785PT",
        (),
    ),
    "es": (
        "Tu código de entrega",
        "Hola Alex,\nEl código de entrega de tu pedido RR123456785PT es 4821.\n",
        "RR123456785PT",
        (),
    ),
    "en": (
        "Your delivery code",
        "Hi Alex,\nYour delivery code for parcel RR123456785PT is 4821.\n",
        "RR123456785PT",
        (),
    ),
    "de": (
        "Ihr Zustellcode",
        "Hallo Alex,\nDer Zustellcode für Ihre Sendung RR123456785PT lautet 4821.\n",
        "RR123456785PT",
        (),
    ),
    "fr": (
        "Votre code de livraison",
        "Bonjour Alex,\nLe code de livraison de votre colis RR123456785PT est 4821.\n",
        "RR123456785PT",
        (),
    ),
    "it": (
        "Il tuo codice di consegna",
        "Ciao Alex,\nIl codice di consegna del pacco RR123456785PT è 4821.\n",
        "RR123456785PT",
        (),
    ),
    "nl": (
        "Je bezorgcode",
        "Hoi Alex,\nDe bezorgcode voor bestelnummer 77012 is 4821.\n",
        None,
        ("77012",),
    ),
}


@pytest.mark.parametrize("lang", CODE_ONLY)
def test_code_only_email(tz: ZoneInfo, lang: str) -> None:
    """An e-mail whose only news is a code for a parcel has the kind CODE."""
    subject, text, number, orders = CODE_ONLY[lang]
    result = _parse(_message(subject, text), tz)
    assert result is not None
    assert result.kind is MailKind.CODE
    assert result.language == lang
    assert result.confidence >= CONFIDENCE_APPLY
    assert "kind_from_code" in result.notes
    assert result.order_numbers == orders
    [shipment] = result.shipments
    assert shipment.kind is MailKind.CODE
    assert shipment.tracking_number == number
    assert shipment.pickup_code == "4821"
    assert shipment.eta is None


def test_code_only_email_needs_a_parcel(tz: ZoneInfo) -> None:
    """A code for an order is a CODE result; a code for nothing is none."""
    order = _message(
        "Your delivery code", "Hi Alex,\nYour delivery code for order #1001 is 4821.\n"
    )
    result = _parse(order, tz)
    assert result is not None
    assert result.kind is MailKind.CODE
    assert result.order_numbers == ("#1001",)
    assert [shipment.pickup_code for shipment in result.shipments] == ["4821"]
    nothing = _message("Your delivery code", "Hi Alex,\nYour delivery code is 4821.\n")
    assert _parse(nothing, tz) is None


# A code next to tracking or order numbers: subject, body, then the tracking
# number, the order numbers and the code the e-mail must give.
APART = {
    "code_is_no_tracking_number_pt": (
        "O seu pedido está em distribuição",
        "Olá Alex,\nO seu pedido n.º 1001 está em distribuição pela CTT.\n"
        "Código de entrega: 7391520486\n",
        None,
        ("1001",),
        "7391520486",
    ),
    "code_is_no_tracking_number_es": (
        "Tu pedido ha sido enviado",
        "Hola Alex,\nTu pedido n.º 1001 ha sido enviado con SEUR.\n"
        "Código de entrega: 73915204\n",
        None,
        ("1001",),
        "73915204",
    ),
    "code_is_no_order_number": (
        "A sua encomenda está em distribuição",
        "Olá Alex,\nA sua encomenda RR123456785PT está em distribuição.\n"
        "Código de entrega do pedido: 4821\n",
        "RR123456785PT",
        (),
        "4821",
    ),
    "order_number_is_no_code": (
        "A sua encomenda está disponível para levantamento",
        "Olá Alex,\nA sua encomenda RR123456785PT está disponível para"
        " levantamento.\nPedido n.º 48213\nCódigo de levantamento: 48213\n",
        "RR123456785PT",
        ("48213",),
        None,
    ),
    "tracking_number_is_no_code": (
        "Tu pedido está en reparto",
        "Hola Alex,\nTu pedido está en reparto con SEUR.\n"
        "Número de envío SEUR: 0628174539\nCódigo de entrega: 0628174539\n"
        "Código de entrega del envío 0628174539: 73915204\n",
        "0628174539",
        (),
        "73915204",
    ),
}


@pytest.mark.parametrize("case", APART)
def test_codes_and_numbers_stay_apart(tz: ZoneInfo, case: str) -> None:
    """A code is never a tracking or order number, nor the other way round."""
    subject, text, number, orders, code = APART[case]
    result = _parse(_message(subject, text), tz)
    assert result is not None
    assert result.order_numbers == orders
    [shipment] = result.shipments
    assert shipment.tracking_number == number
    assert shipment.pickup_code == code


@pytest.mark.parametrize(
    ("subject", "text", "sender"),
    [
        (
            "Delivery Status Notification (Failure)",
            "Your order has shipped\nTracking number: RR123456785PT",
            "mailer-daemon@googlemail.com",
        ),
        (
            "Undeliverable: Your order has shipped",
            "Tracking number: RR123456785PT",
            "postmaster@outlook.example",
        ),
        (
            "Your parcel has been delivered",
            "Hi Alex,\nyour parcel has been delivered. Thanks!",
            "orders@loja-exemplo.example",
        ),
        ("Hello", "", "orders@loja-exemplo.example"),
    ],
)
def test_returns_none(tz: ZoneInfo, subject: str, text: str, sender: str) -> None:
    """Bounces, and kinds without any number or order number, give None."""
    assert _parse(_message(subject, text, sender=sender), tz) is None


@pytest.mark.parametrize(
    ("subject", "kind"),
    [
        ("Your order #1001 has been confirmed", MailKind.ORDER),
        ("Order confirmation", MailKind.ORDER),
        ("Your order has shipped", MailKind.SHIPPED),
        ("Your package is on its way", MailKind.SHIPPED),
        ("Your parcel is in transit", MailKind.IN_TRANSIT),
        ("Out for delivery today", MailKind.OUT_FOR_DELIVERY),
        ("Your parcel will be delivered today", MailKind.OUT_FOR_DELIVERY),
        ("Your parcel has been delivered", MailKind.DELIVERED),
        ("We missed you - delivery attempt", MailKind.ATTEMPTED),
        ("Your parcel is ready for pickup", MailKind.READY_FOR_PICKUP),
        ("Your shipment is delayed", MailKind.DELAYED),
        ("Customs clearance required for your parcel", MailKind.CUSTOMS),
        ("Your return has been received", MailKind.RETURN),
        ("Your refund has been processed", MailKind.RETURN),
        ("Your order has been cancelled", MailKind.CANCELLED),
        ("Confirmação da encomenda n.º 1042", MailKind.ORDER),
        ("A sua encomenda foi enviada", MailKind.SHIPPED),
        ("A sua encomenda está em distribuição", MailKind.OUT_FOR_DELIVERY),
        ("A sua encomenda foi entregue", MailKind.DELIVERED),
        ("Encomenda disponível para levantamento", MailKind.READY_FOR_PICKUP),
        ("Pedido confirmado", MailKind.ORDER),
        ("Tu pedido ha sido enviado", MailKind.SHIPPED),
        ("Tu pedido está en reparto", MailKind.OUT_FOR_DELIVERY),
        ("Tu pedido ha sido entregado", MailKind.DELIVERED),
        ("Tu paquete está listo para recoger", MailKind.READY_FOR_PICKUP),
        ("Bestellbestätigung", MailKind.ORDER),
        ("Ihre Bestellung wurde versandt", MailKind.SHIPPED),
        ("Ihr Paket wird heute zugestellt", MailKind.OUT_FOR_DELIVERY),
        ("Ihr Paket wurde zugestellt", MailKind.DELIVERED),
        ("Ihre Sendung liegt zur Abholung bereit", MailKind.READY_FOR_PICKUP),
        ("Confirmation de commande", MailKind.ORDER),
        ("Votre commande a été expédiée", MailKind.SHIPPED),
        ("Votre colis est en cours de livraison", MailKind.OUT_FOR_DELIVERY),
        ("Votre colis a été livré", MailKind.DELIVERED),
        ("Conferma d'ordine", MailKind.ORDER),
        ("Il tuo ordine è stato spedito", MailKind.SHIPPED),
        ("Il tuo pacco è in consegna", MailKind.OUT_FOR_DELIVERY),
        ("Il tuo pacco è stato consegnato", MailKind.DELIVERED),
        ("Bedankt voor je bestelling", MailKind.ORDER),
        ("Je bestelling is verzonden", MailKind.SHIPPED),
        ("Je pakket wordt vandaag bezorgd", MailKind.OUT_FOR_DELIVERY),
        ("Je pakket is bezorgd", MailKind.DELIVERED),
    ],
)
def test_detect_kind_from_subject(subject: str, kind: MailKind) -> None:
    """Localised subjects in all seven languages."""
    assert detect_kind(subject) == (kind, "subject")


@pytest.mark.parametrize(
    ("subject", "kind"),
    [
        (
            "Your parcel was delivered to the DPD Pickup point",
            MailKind.READY_FOR_PICKUP,
        ),
        ("Your parcel was delivered to the carrier", MailKind.SHIPPED),
        ("Your parcel was delivered to our depot", MailKind.IN_TRANSIT),
    ],
)
def test_delivered_to_a_handover_point(subject: str, kind: MailKind) -> None:
    """Delivered to a pickup point, carrier or depot is not delivered home."""
    assert detect_kind(subject) == (kind, "subject")


def test_detect_kind_from_body() -> None:
    """Without a kind in the subject, the start of the body is read."""
    assert detect_kind(
        "Hello", "Hi Alex,\nGood news: your order has shipped and is on its way."
    ) == (MailKind.SHIPPED, "body")
    assert detect_kind("Update", "Olá Alex,\nA sua encomenda foi entregue hoje.") == (
        MailKind.DELIVERED,
        "body",
    )


@pytest.mark.parametrize(
    ("text", "lang", "kind"),
    [
        ("A sua encomenda saiu do nosso armazém.", "pt", MailKind.SHIPPED),
        ("Tu pedido ha salido de nuestro almacén.", "es", MailKind.SHIPPED),
        ("Ihr Paket wurde an DHL übergeben.", "de", MailKind.SHIPPED),
        ("Il tuo pacco è partito.", "it", MailKind.SHIPPED),
        (
            "Il tuo pacco è partito dal centro di smistamento.",
            "it",
            MailKind.IN_TRANSIT,
        ),
        (
            "A sua encomenda está a caminho. Se não estiver em casa, fica "
            "disponível para levantamento num ponto de recolha.",
            "pt",
            MailKind.SHIPPED,
        ),
        ("Import VAT is due on your parcel.", "en", MailKind.CUSTOMS),
        (
            "É necessário pagar o IVA de importação da sua encomenda.",
            "pt",
            MailKind.CUSTOMS,
        ),
        ("Debes pagar los aranceles de tu paquete.", "es", MailKind.CUSTOMS),
        ("Für Ihr Paket sind noch Zollgebühren offen.", "de", MailKind.CUSTOMS),
        ("Des droits de douane sont à payer pour votre colis.", "fr", MailKind.CUSTOMS),
        ("Devi pagare i dazi doganali per il tuo pacco.", "it", MailKind.CUSTOMS),
        ("Je moet nog invoerrechten betalen voor je pakket.", "nl", MailKind.CUSTOMS),
        ("Departed from the sorting centre in Lyon.", "en", MailKind.IN_TRANSIT),
        ("Your parcel has left the hub in Porto.", "en", MailKind.IN_TRANSIT),
        ("Your parcel has left the DHL Leipzig hub.", "en", MailKind.IN_TRANSIT),
        ("Departed Facility in Leipzig - Germany", "en", MailKind.IN_TRANSIT),
        ("Departed FedEx location MEMPHIS, TN", "en", MailKind.IN_TRANSIT),
        ("Your parcel has left the country of origin.", "en", MailKind.IN_TRANSIT),
        (
            "O seu envio saiu do centro de distribuição de Lisboa.",
            "pt",
            MailKind.IN_TRANSIT,
        ),
        ("A encomenda saiu do país de origem.", "pt", MailKind.IN_TRANSIT),
        (
            "Tu envío ha salido del centro de clasificación de Madrid.",
            "es",
            MailKind.IN_TRANSIT,
        ),
        ("Salida de la delegación de Valencia.", "es", MailKind.IN_TRANSIT),
        (
            "Die Sendung hat das GLS-Paketzentrum in Leipzig verlassen.",
            "de",
            MailKind.IN_TRANSIT,
        ),
        ("Die Sendung hat das Ursprungsland verlassen.", "de", MailKind.IN_TRANSIT),
        ("Das Paket verließ das Verteilzentrum Hamburg.", "de", MailKind.IN_TRANSIT),
        ("Votre colis a quitté le centre de tri de Lyon.", "fr", MailKind.IN_TRANSIT),
        ("Votre colis est parti du dépôt.", "fr", MailKind.IN_TRANSIT),
        (
            "Il pacco ha lasciato il centro di smistamento di Bologna.",
            "it",
            MailKind.IN_TRANSIT,
        ),
        ("Il pacco ha lasciato il paese d'origine.", "it", MailKind.IN_TRANSIT),
        (
            "Je pakket is vertrokken uit het sorteercentrum in Utrecht.",
            "nl",
            MailKind.IN_TRANSIT,
        ),
        (
            "Je pakket heeft het land van herkomst verlaten.",
            "nl",
            MailKind.IN_TRANSIT,
        ),
        (
            "Je pakket heeft het PostNL sorteercentrum in Utrecht verlaten.",
            "nl",
            MailKind.IN_TRANSIT,
        ),
        ("Het pakket verliet het distributiecentrum.", "nl", MailKind.IN_TRANSIT),
        ("Your order has left our warehouse.", "en", MailKind.SHIPPED),
        ("Your parcel has left the Amazon fulfilment centre.", "en", MailKind.SHIPPED),
        ("Your order has left our logistics centre.", "en", MailKind.SHIPPED),
        ("Ihre Bestellung hat unser Lager verlassen.", "de", MailKind.SHIPPED),
        ("Votre commande a quitté notre entrepôt.", "fr", MailKind.SHIPPED),
        ("Il tuo ordine ha lasciato il nostro magazzino.", "it", MailKind.SHIPPED),
        ("Je bestelling heeft ons magazijn verlaten.", "nl", MailKind.SHIPPED),
    ],
)
def test_departure_and_customs_from_body(text: str, lang: str, kind: MailKind) -> None:
    """Departures, duties to pay and pickup only if absent, in the body.

    Leaving a carrier's facility, a hub or the country of origin is in
    transit; leaving the shop's own warehouse is shipped.
    """
    assert detect_kind("Update", text, lang=lang) == (kind, "body")


@pytest.mark.parametrize(
    "subject",
    [
        "Shipment update",
        "Shipping update for your parcel",
        "Dispatch update",
        "Atualização do envio",
        "Actualización del envío",
        "Sendungsupdate",
        "Update zu Ihrer Sendung",
        "Mise à jour de votre colis",
        "Aggiornamento sulla spedizione",
        "Update over je zending",
    ],
)
def test_update_subject_gives_no_kind(subject: str) -> None:
    """Carriers send a "shipment update" at every step: it says no kind."""
    assert detect_kind(subject) == (None, "")


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Your order has left our logistics hub.", "en"),
        ("Your order has left the fulfilment hub.", "en"),
        ("A encomenda saiu da plataforma logística.", "pt"),
        ("El pedido ha salido de la plataforma logística.", "es"),
        ("Das Paket hat unser Logistikzentrum verlassen.", "de"),
        ("Votre commande a quitté la plateforme logistique.", "fr"),
        ("L'ordine ha lasciato il centro logistico.", "it"),
        ("L'ordine ha lasciato il polo logistico.", "it"),
        ("Il pacco è uscito dalla piattaforma logistica.", "it"),
        ("Your order has departed from our facility.", "en"),
        ("Your parcel has departed the Amazon warehouse facility.", "en"),
    ],
)
def test_leaving_a_logistics_centre_is_not_in_transit(text: str, lang: str) -> None:
    """A shop's own logistics or fulfilment centre isn't a carrier's facility."""
    assert MailKind.IN_TRANSIT not in text_kinds("Update", text, lang=lang)


def test_order_with_a_dutch_condition() -> None:
    """Dutch "indien" (if) makes the shipping phrase a condition, not a kind."""
    assert detect_kind(
        "Bestelling 12345",
        "Bedankt voor je bestelling. Indien je pakket is verzonden, sturen we "
        "je een bericht.",
        lang="nl",
    ) == (MailKind.ORDER, "body")


@pytest.mark.parametrize(
    ("subject", "lang"),
    [
        ("Your parcel is on its way", "en"),
        ("A sua encomenda está a caminho", "pt"),
        ("Tu pedido está en camino", "es"),
        ("Ihr Paket ist unterwegs", "de"),
        ("Votre colis est en route", "fr"),
        ("Il tuo pacco è in viaggio", "it"),
        ("Je pakket is onderweg", "nl"),
    ],
)
def test_on_its_way_can_be_left_out(subject: str, lang: str) -> None:
    """On its way is SHIPPED, unless the caller treats it as unclear."""
    assert detect_kind(subject, lang=lang) == (MailKind.SHIPPED, "subject")
    assert detect_kind(subject, lang=lang, on_the_way=False) == (None, "")


def test_text_kinds_lists_every_kind() -> None:
    """The text backs both the picked kind and a less specific one."""
    text = "Il tuo pacco è partito dal centro di smistamento."
    assert detect_kind("Update", text, lang="it") == (MailKind.IN_TRANSIT, "body")
    assert text_kinds("Update", text, lang="it") == {
        MailKind.IN_TRANSIT,
        MailKind.SHIPPED,
    }


@pytest.mark.parametrize(
    ("subject", "text", "lang", "kind"),
    [
        (
            "Information zu deiner Sendung",
            "Dein Paket liegt zur Abholung bereit. Nach Ablauf der Lagerfrist "
            "geht das Paket an den Absender zurück.",
            "de",
            MailKind.READY_FOR_PICKUP,
        ),
        (
            "Information zu deiner Sendung",
            "Dein Paket liegt in der Packstation bereit. Holst du es nicht "
            "innerhalb von 7 Tagen ab, schicken wir es an den Absender zurück.",
            "de",
            MailKind.READY_FOR_PICKUP,
        ),
        (
            "Informatie over je pakket",
            "Je pakket ligt klaar bij het afhaalpunt. Je kunt het 7 dagen "
            "ophalen. Daarna gaat het pakket terug naar de afzender.",
            "nl",
            MailKind.READY_FOR_PICKUP,
        ),
        (
            "Informatie over je pakket",
            "Je pakket ligt klaar bij het afhaalpunt. Haal je het niet op vóór "
            "25 november, dan sturen we het terug naar de afzender.",
            "nl",
            MailKind.READY_FOR_PICKUP,
        ),
        (
            "Informatie over je pakket",
            "We hebben je gemist. We konden je pakket niet bezorgen. Je kunt "
            "het 7 dagen ophalen bij het afhaalpunt. Daarna gaat het pakket "
            "terug naar de afzender.",
            "nl",
            MailKind.ATTEMPTED,
        ),
    ],
    ids=["de-lagerfrist", "de-packstation", "nl-daarna", "nl-dan", "nl-gemist"],
)
def test_return_warning_in_a_pickup_notice(
    subject: str, text: str, lang: str, kind: MailKind
) -> None:
    """Sending the parcel back if nobody collects it is a warning, not a return."""
    assert detect_kind(subject, text, lang=lang) == (kind, "body")
    assert MailKind.RETURN not in text_kinds(subject, text, lang=lang)


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        (
            "Dein Paket lag 7 Tage zur Abholung bereit und wurde nicht abgeholt. "
            "Es geht jetzt an den Absender zurück.",
            "de",
        ),
        (
            "Dein Paket lag zur Abholung bereit. Nach Ablauf der Lagerfrist "
            "wurde es an den Absender zurückgeschickt.",
            "de",
        ),
        (
            "Je pakket lag klaar bij het afhaalpunt en is niet opgehaald. "
            "Daarom gaat het terug naar de afzender.",
            "nl",
        ),
        (
            "Je pakket lag klaar bij het afhaalpunt. Daarna hebben we het "
            "terug naar de afzender gestuurd.",
            "nl",
        ),
    ],
    ids=["de-jetzt", "de-past", "nl-daarom", "nl-past"],
)
def test_return_after_a_pickup_period_stays_a_return(text: str, lang: str) -> None:
    """A parcel that went back after its pickup period is a return."""
    subject = "Informatie over je pakket" if lang == "nl" else "Information"
    assert detect_kind(subject, text, lang=lang) == (MailKind.RETURN, "body")


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        pytest.param(
            "A sua encomenda vai chegar mais tarde do que o previsto.",
            "pt",
            id="pt-vai-chegar",
        ),
        pytest.param("Tu envío lleva retraso.", "es", id="es-lleva"),
        pytest.param(
            "Your parcel will arrive later than expected.", "en", id="en-will-arrive"
        ),
        pytest.param(
            "Die Zustellung deiner Sendung verzögert sich.", "de", id="de-sich"
        ),
        pytest.param("Je pakket loopt een dag vertraging op.", "nl", id="nl-dag"),
        pytest.param("Votre colis aura du retard.", "fr", id="fr-aura"),
        pytest.param(
            "Je pakket loopt een dag vertraging op wegens een storing in het "
            "distributiecentrum.",
            "nl",
            id="nl-facility",
        ),
        pytest.param("Je pakket loopt vertraging op door drukte.", "nl", id="nl-loopt"),
        pytest.param("La tua spedizione è in ritardo.", "it", id="it-ritardo"),
    ],
)
def test_delay_wordings(text: str, lang: str) -> None:
    """A delay notice reads as delayed under a neutral subject."""
    assert detect_kind("Update on your parcel", text, lang=lang) == (
        MailKind.DELAYED,
        "body",
    )


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        pytest.param(
            "A sua encomenda não vai chegar mais tarde do que o previsto.",
            "pt",
            id="pt-nao",
        ),
        pytest.param(
            "Your parcel won't arrive later than expected.", "en", id="en-wont"
        ),
        pytest.param(
            "If your parcel will arrive later than expected, we'll tell you.",
            "en",
            id="en-if",
        ),
        pytest.param("Je pakket heeft geen vertraging.", "nl", id="nl-geen"),
    ],
)
def test_delay_wordings_guarded(text: str, lang: str) -> None:
    """A negated or conditional delay wording is not a delay."""
    assert MailKind.DELAYED not in text_kinds("Update on your parcel", text, lang=lang)


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        pytest.param(
            "A sua encomenda já está no nosso centro de distribuição.",
            "pt",
            id="pt-centro",
        ),
        pytest.param(
            "Tu paquete ya está en nuestro centro de reparto.", "es", id="es-centro"
        ),
        pytest.param(
            "Deine Sendung ist in unserem Depot angekommen.", "de", id="de-depot"
        ),
        pytest.param("Votre colis est arrivé dans notre agence.", "fr", id="fr-agence"),
        pytest.param(
            "La tua spedizione è arrivata nella nostra filiale.",
            "it",
            id="it-filiale",
        ),
        pytest.param("Je pakket is aangekomen in ons depot.", "nl", id="nl-depot"),
        pytest.param(
            "Your parcel has arrived at our local depot.", "en", id="en-depot"
        ),
        pytest.param(
            "Tu envío ha llegado a la delegación de tu zona.",
            "es",
            id="es-delegacion",
        ),
    ],
)
def test_depot_arrivals(text: str, lang: str) -> None:
    """An arrival at a depot or hub is in transit."""
    assert detect_kind("Update on your parcel", text, lang=lang) == (
        MailKind.IN_TRANSIT,
        "body",
    )


def test_depot_arrival_guarded() -> None:
    """A depot arrival in a condition is not in transit."""
    text = "Sobald deine Sendung in unserem Depot angekommen ist, melden wir uns."
    assert not text_kinds("Update on your parcel", text, lang="de")


@pytest.mark.parametrize(
    ("subject", "text", "lang"),
    [
        ("Your parcel will be delivered tomorrow", "", "en"),
        ("Your parcel has not been delivered", "", "en"),
        ("Big sale this weekend", "Order now and get free shipping!", "en"),
        ("Update", "Once your parcel has been delivered, rate us.", "en"),
        ("Update", "Se a sua encomenda foi entregue, avalie-nos.", "pt"),
        (
            "Update",
            "Sobald die Sendung zugestellt wurde, erhalten Sie eine E-Mail.",
            "de",
        ),
        ("Update", "U hoeft geen invoerrechten te betalen.", "nl"),
        ("Update", "Mogelijk moet je invoerrechten betalen.", "nl"),
        (
            "Update",
            "Als er invoerrechten betaald moeten worden, ontvang je een e-mail.",
            "nl",
        ),
        ("Update", "Als je pakket is bezorgd, laat ons dan een review achter.", "nl"),
        (
            "Update",
            "Indien je pakket is verzonden, sturen we je een bericht.",
            "nl",
        ),
        ("Update", "Your parcel has not yet left the hub.", "en"),
        ("Update", "We will tell you once it has left the sorting centre.", "en"),
        ("Update", "Your parcel was left at the depot.", "en"),
        ("Update", "A encomenda ainda não saiu do centro de distribuição.", "pt"),
        (
            "Update",
            "Tu pedido todavía no ha salido del centro de clasificación.",
            "es",
        ),
        ("Update", "Die Sendung hat das Paketzentrum noch nicht verlassen.", "de"),
        ("Update", "Votre colis n'a pas encore quitté le centre de tri.", "fr"),
        (
            "Update",
            "Il pacco non ha ancora lasciato il centro di smistamento.",
            "it",
        ),
        ("Update", "Het pakket heeft het sorteercentrum nog niet verlaten.", "nl"),
    ],
)
def test_detect_kind_guards(subject: str, text: str, lang: str) -> None:
    """Negated, future and conditional phrases are not a kind."""
    assert detect_kind(subject, text, lang=lang) == (None, "")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Order #1001", ["#1001"]),
        ("Order number: 112-1234567-1234567", ["112-1234567-1234567"]),
        ("Order No. 4711", ["4711"]),
        ("Order ID: AB-12345", ["AB-12345"]),
        ("Pedido n.º 123456", ["123456"]),
        ("Encomenda nº 1042", ["1042"]),
        ("Número de pedido: 98765", ["98765"]),
        ("Número da encomenda: PT-20261117", ["PT-20261117"]),
        ("Bestellnummer: 4711-0815", ["4711-0815"]),
        ("Bestellung Nr. 12345", ["12345"]),
        ("N° de commande : 123456789", ["123456789"]),
        ("Commande n° 778899", ["778899"]),
        ("Numero d'ordine: 3001234", ["3001234"]),
        ("Ordine n. 445566", ["445566"]),
        ("Bestelnummer: 2026-555", ["2026-555"]),
        ("Bestelling #9001", ["#9001"]),
        ("order #1001 and order #1002, plus Order #1001", ["#1001", "#1002"]),
        ("Order date: 17/11/2026", []),
        ("Order now and save 20%", []),
        ("Order total: 49.99", []),
        ("Bestellnummer 2026-11-17", []),
    ],
)
def test_find_order_numbers(text: str, expected: list[str]) -> None:
    """Order numbers after localised labels; dates and prices are skipped."""
    assert find_order_numbers(text) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("No-Reply | Example Shop", "Example Shop"),
        ("Example Shop Notifications", "Example Shop"),
        ("Customer Service - Example Store", "Example Store"),
        ("Não responder - Loja Exemplo", "Loja Exemplo"),
        ("Equipa Loja Exemplo", "Loja Exemplo"),
        ("Beispiel Shop (Versand)", "Beispiel Shop"),
        ('"Loja Exemplo"', "Loja Exemplo"),
        ("Example Shop <orders@example.com>", "Example Shop"),
        ("orders@example.com", None),
        ("no-reply", None),
        ("1234", None),
        ("", None),
    ],
)
def test_clean_sender_name(name: str, expected: str | None) -> None:
    """Noise words and addresses are dropped from display names."""
    assert clean_sender_name(name) == expected
