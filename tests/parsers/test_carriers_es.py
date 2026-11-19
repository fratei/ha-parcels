"""Tests for the SEUR, Correos Express, MRW, NACEX and Paack e-mail parsers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.parcels.ai.prompt import link_entries
from custom_components.parcels.const import MailKind
from custom_components.parcels.parsers.base import (
    Link,
    MailMessage,
    ParseResult,
    SenderVerdict,
)
from custom_components.parcels.parsers.carriers import parse_carrier

from .test_carriers_common import (
    LISBON,
    Case,
    Loader,
    VerdictFor,
    check_case,
    check_negative,
    eta,
)

CASES = (
    Case(
        "seur_predict_es",
        "seur",
        MailKind.OUT_FOR_DELIVERY,
        "0628174539",
        eta=eta("2026-11-17", "10:00", "14:00"),
        merchant="PcComponentes",
    ),
    Case(
        "seur_pickup_ready_es",
        "seur",
        MailKind.READY_FOR_PICKUP,
        "0628174547",
        eta=eta("2026-11-17", until="2026-11-27"),
        pickup_point="Punto Pickup Papelería Ejemplo, Calle Ejemplo 1, 28001 Madrid",
        pickup_code="482177",
        merchant="Druni",
    ),
    Case(
        "seur_delivered_pt",
        "seur",
        MailKind.DELIVERED,
        "0628174555",
        event="2026-11-17 12:47",
    ),
    Case(
        "correos_express_in_delivery_es",
        "correos_express",
        MailKind.OUT_FOR_DELIVERY,
        "3230004517823964",
        eta=eta("2026-11-17", "09:00", "14:00"),
        merchant="El Corte Inglés",
    ),
    Case(
        "correos_express_delivered_pt",
        "correos_express",
        MailKind.DELIVERED,
        "3230004517823972",
        event="2026-11-17 15:20",
    ),
    Case(
        "mrw_in_delivery_es",
        "mrw",
        MailKind.OUT_FOR_DELIVERY,
        "026500438217",
        eta=eta("2026-11-17", "09:00", "14:00"),
        merchant="MediaMarkt",
    ),
    Case(
        "mrw_delivered_pt",
        "mrw",
        MailKind.DELIVERED,
        "072100517364",
        event="2026-11-17 09:41",
    ),
    Case(
        "nacex_in_delivery_es",
        "nacex",
        MailKind.OUT_FOR_DELIVERY,
        "2834/71520946",
        eta=eta("2026-11-17", "15:00", "19:00"),
        merchant="Mango",
    ),
    Case(
        "nacex_shop_pt",
        "nacex",
        MailKind.READY_FOR_PICKUP,
        "2834/71520953",
        eta=eta("2026-11-17", until="2026-12-01"),
        pickup_point="NACEX.shop Papelaria Exemplo, Rua Exemplo 1, 4000-001 Porto",
        pickup_code="739214",
        merchant="Primark",
    ),
    # The text has no number: it comes from the tracking link.
    Case(
        "paack_today_es",
        "paack",
        MailKind.OUT_FOR_DELIVERY,
        "PK7311804926",
        eta=eta("2026-11-17", "14:00", "16:00"),
        merchant="Zara",
        notes=("number_from_link",),
    ),
    Case(
        "paack_delivered_pt",
        "paack",
        MailKind.DELIVERED,
        "PK7311805018",
        event="2026-11-17 15:12",
        merchant="Zara",
    ),
    # Paack's order ID, in the footer and the links, kept as written.
    Case(
        "paack_on_the_way_pt",
        "paack",
        MailKind.IN_TRANSIT,
        "Wx4Hn8Tz3_1",
        eta=eta("2026-11-25", "09:00", "13:00"),
        merchant="Casa Exemplo",
    ),
    # Sent on the delivery day; the shop is under an "Encomenda de" label.
    Case(
        "paack_out_for_delivery_pt",
        "paack",
        MailKind.OUT_FOR_DELIVERY,
        "Rb5Lq2Vm7_1",
        eta=eta("2026-11-25", "10:00", "12:00"),
        merchant="Amazon",
    ),
)
NEGATIVE = (
    "seur_marketing_es",
    "correos_express_marketing_es",
    "mrw_service_notice_es",
    "mrw_marketing_pt",
    "nacex_marketing_es",
    "paack_survey_es",
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_parses_email(case: Case, load_eml: Loader, verdict_for: VerdictFor) -> None:
    """Each e-mail gives its kind, number, dates, pickup data and merchant."""
    check_case(case, load_eml, verdict_for)


@pytest.mark.parametrize("name", NEGATIVE)
def test_ignores_email_without_parcel_news(
    name: str, load_eml: Loader, verdict_for: VerdictFor
) -> None:
    """Promotions, surveys and service notices give no result."""
    check_negative(name, load_eml, verdict_for)


# --- Paack's order IDs ----------------------------------------------------------

PAACK = SenderVerdict(domain="paack.co", authenticated=True, known=True)
# A made-up order ID: nine letters and digits in mixed case, "_" and the
# package number.
PAACK_ID = "Wx4Hn8Tz3_1"
PREFERENCES_LINK = (
    "https://paack.co/shipments/preferences?email=alex%40example.com"
    f"&phone=%2B351910000000&postal_code=4099-321&tracking_number={PAACK_ID}"
)
SLOT_LINK = "https://paack.co/shipments/timeslot/direct/k7Qm2ZpX9vRt4LwN8sYb3HcF"
# Paack's window sentence and footer label in each of its languages.
PAACK_FOOTERS = {
    "en": "Will be delivered on 25 November between 09:00 and 13:00.\n\n"
    "Order number: {id}\n",
    "pt": "Será entregue em 25 de novembro entre as 09:00 e as 13:00.\n\n"
    "Número de pedido: {id}\n",
    "es": "Será entregado el 25 de noviembre entre las 09:00 y las 13:00.\n\n"
    "Número de pedido: {id}\n",
    "fr": "Sera livré le 25 novembre entre 09:00 et 13:00.\n\n"
    "Numéro de commande : {id}\n",
    "it": "Sarà consegnato il 25 novembre tra le 09:00 e le 13:00.\n\n"
    "Numero d'ordine: {id}\n",
}


def _paack(text: str, *links: str, subject: str = "Paack") -> ParseResult | None:
    """Parse a Paack e-mail with ``text`` as its body and ``links``."""
    message = MailMessage(
        message_id="<20261117093000.ef56@mail.example.com>",
        provider_id="test",
        provider="google",
        mailbox="alex@example.com",
        sender="no-reply@paack.co",
        sender_name="Paack",
        subject=subject,
        date=datetime(2026, 11, 17, 9, 30, tzinfo=UTC),
        text=text,
        links=tuple(Link(url) for url in links),
    )
    return parse_carrier(message, PAACK, LISBON, "paack")


@pytest.mark.parametrize("language", PAACK_FOOTERS)
def test_paack_reads_order_id_in_footer(language: str) -> None:
    """The ID after the footer's label is the number, as written.

    Its first part isn't an order number of the shop: orders are keyed
    without case, and the ID's case matters.
    """
    result = _paack(PAACK_FOOTERS[language].format(id=PAACK_ID))
    assert result is not None
    [shipment] = result.shipments
    assert (shipment.carrier, shipment.tracking_number) == ("paack", PAACK_ID)
    assert shipment.eta == eta("2026-11-25", "09:00", "13:00")
    assert result.order_numbers == shipment.order_numbers == ()


@pytest.mark.parametrize(
    "label",
    ["Código Paack: ", "Número de seguimento: ", "Tracking number: "],
)
def test_paack_label_reads_whole_order_id(label: str) -> None:
    """A tracking label gives the whole ID, not its first part uppercased."""
    result = _paack(f"Será entregue em breve.\n\n{label}{PAACK_ID}\n")
    assert result is not None
    assert [s.tracking_number for s in result.shipments] == [PAACK_ID]


@pytest.mark.parametrize(
    "text",
    [
        "We missed you.\n\nOrder number: {id}\n",
        "Não o encontrámos.\n\nNúmero de pedido: {id}\n",
        "No te hemos encontrado.\n\nNúmero de pedido: {id}\n",
        "Nous ne vous avons pas vu.\n\nNuméro de commande : {id}\n",
        "Non ti abbiamo trovato.\n\nNumero d'ordine: {id}\n",
    ],
)
def test_paack_missed_delivery(text: str) -> None:
    """Paack's "we missed you" notices are failed delivery attempts."""
    result = _paack(text.format(id=PAACK_ID))
    assert result is not None
    assert result.kind is MailKind.ATTEMPTED
    assert result.notes == ()


def test_paack_reads_order_id_from_preferences_link() -> None:
    """The preferences link gives the ID when the text has none."""
    result = _paack("Será entregue em breve.\n", PREFERENCES_LINK)
    assert result is not None
    assert [s.tracking_number for s in result.shipments] == [PAACK_ID]
    assert result.notes == ("number_from_link",)


def test_paack_slot_link_gives_no_number() -> None:
    """The opaque token of a slot link isn't a number."""
    result = _paack("Será entregue em breve.\n", SLOT_LINK)
    assert result is None or not any(s.tracking_number for s in result.shipments)


def test_paack_keeps_no_postcode_email_or_phone(load_eml: Loader) -> None:
    """Paack's links also carry the postcode, the e-mail address, the phone
    and opaque tokens: only the order ID is read, for the parcel and for the
    model.
    """
    message = load_eml("carriers/paack_on_the_way_pt.eml")
    result = parse_carrier(message, PAACK, LISBON, "paack")
    assert result is not None
    assert link_entries(link.url for link in message.links) == [
        ("paack.co", ("Wx4Hn8Tz3_1",))
    ]
    text = repr(result)
    for private in ("4099", "postal", "alex%40", "351910000000", "k7Qm2Z", "0f6b2c1e"):
        assert private not in text


@pytest.mark.parametrize(
    ("text", "merchant"),
    [
        ("Encomenda de\nAmazon\n", "Amazon"),
        ("Encomenda de: Amazon\n", "Amazon"),
        ("Order from\nCasa Exemplo\n", "Casa Exemplo"),
        ("Pedido de:\nCasa Exemplo\n", "Casa Exemplo"),
        # A sentence that starts like the label isn't a label.
        ("Order from Monday to Friday.\n", None),
    ],
)
def test_paack_reads_shop_label(text: str, merchant: str | None) -> None:
    """Paack names the shop under an "Order from" label."""
    result = _paack(
        f"Será entregue em breve.\n\n{text}\nNúmero de pedido: {PAACK_ID}\n"
    )
    assert result is not None
    assert result.merchant == merchant
