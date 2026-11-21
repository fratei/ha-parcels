"""Tests for the Leroy Merlin parser.

Leroy Merlin (Portugal) sends its own e-mails about orders and marketplace
shipments, a survey after each shipment, and its carriers' notices from
its own domain under the carrier's name.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.parcels.const import CONFIDENCE_APPLY, MailKind, ParcelStatus
from custom_components.parcels.convert import is_confident, result_contributions
from custom_components.parcels.dedup import apply_contribution
from custom_components.parcels.models import ParcelsData, Source
from custom_components.parcels.parsers import NOTE_KNOWN_SENDER_UNPARSED, parse_message
from custom_components.parcels.parsers.base import (
    Link,
    MailMessage,
    ParseResult,
    SenderVerdict,
)
from custom_components.parcels.parsers.tracking import tracking_url

from .test_carriers_common import LISBON, eta

ORDER = "51800012"
ENVIO = "1234567890"
GLS = "61234567890123"
SELLER = "Loja Exemplo (Exemplo Lda)"
ITEMS = ("Berbequim sem fios 18V", "Conjunto de brocas para madeira")
DETAILS = (
    f"Encomenda n.º {ORDER}\n"
    f"Envio n.º {ENVIO}\n\n"
    f"Vendido e expedido por: {SELLER}\n\n"
    "Berbequim sem fios 18V\n"
    "Quantidade: 1\n"
    "Conjunto de brocas para madeira\n"
    "Quantidade: 2\n\n"
    "Obrigado por escolher a Leroy Merlin.\n"
)
TODAY_BY_GLS = "Olá Alex,\n\nA sua encomenda será entregue hoje pela GLS.\n\n"
SENT = datetime(2026, 11, 17, 9, 30, tzinfo=UTC)
SURVEYED = datetime(2026, 11, 19, 10, tzinfo=UTC)


def _lm(
    subject: str,
    text: str,
    *links: str,
    sender: str = "encomendas@leroymerlin.pt",
    sender_name: str = "Leroy Merlin",
    date: datetime = SENT,
) -> ParseResult:
    """Parse an authenticated e-mail from Leroy Merlin."""
    message = MailMessage(
        message_id=f"<{date:%Y%m%d%H%M%S}.lm01@mail.example.com>",
        provider_id="test",
        provider="google",
        mailbox="alex@example.com",
        sender=sender,
        sender_name=sender_name,
        subject=subject,
        date=date,
        text=text,
        links=tuple(Link(url) for url in links),
    )
    verdict = SenderVerdict(
        domain="leroymerlin.pt", authenticated=True, known=True, method="dmarc"
    )
    return parse_message(message, verdict, LISBON)


def test_out_for_delivery() -> None:
    """A marketplace shipment out for delivery, with everything it names."""
    result = _lm("Encomenda em distribuição!", TODAY_BY_GLS + DETAILS)

    assert result.parser == "leroymerlin"
    assert result.kind is MailKind.OUT_FOR_DELIVERY
    assert result.merchant == "Leroy Merlin"
    assert result.order_numbers == (ORDER,)
    assert result.items == ITEMS
    assert result.confidence >= CONFIDENCE_APPLY
    assert is_confident(result)
    [shipment] = result.shipments
    assert shipment.carrier == "gls"
    assert shipment.tracking_number is None
    # The shop's shipment number isn't one of GLS's tracking numbers.
    assert shipment.reference == ENVIO
    assert shipment.seller == SELLER
    assert shipment.eta == eta("2026-11-17")
    assert not shipment.attach_only


@pytest.mark.parametrize(
    ("subject", "kind"),
    [
        ("Encomenda confirmada!", MailKind.ORDER),
        ("A sua encomenda foi enviada", MailKind.SHIPPED),
        ("Encomenda pronta para levantamento", MailKind.READY_FOR_PICKUP),
        ("Envio entregue. Até breve!", MailKind.DELIVERED),
    ],
)
def test_statuses(subject: str, kind: MailKind) -> None:
    """The subject gives the status; the order makes it certain."""
    result = _lm(subject, DETAILS)

    assert result.kind is kind
    assert result.order_numbers == (ORDER,)
    assert is_confident(result)
    [shipment] = result.shipments
    assert shipment.reference == ENVIO
    assert shipment.seller == SELLER


def test_delivered_has_no_date_to_expect() -> None:
    """A delivered shipment isn't expected any more."""
    result = _lm("Envio entregue. Até breve!", DETAILS)

    [shipment] = result.shipments
    assert shipment.eta is None


def test_shipped_with_only_the_order() -> None:
    """Leroy Merlin's own "shipped" e-mail names just the order."""
    result = _lm(
        "A sua encomenda foi enviada",
        f"Olá Alex,\n\nA sua encomenda {ORDER} foi enviada.\n",
    )

    assert result.kind is MailKind.SHIPPED
    assert result.merchant == "Leroy Merlin"
    assert result.order_numbers == (ORDER,)
    assert is_confident(result)
    assert not any(
        shipment.tracking_number or shipment.reference or shipment.seller
        for shipment in result.shipments
    )


def test_status_from_the_body_alone_is_uncertain() -> None:
    """Without a status in the subject, a person or the AI checks the e-mail."""
    result = _lm("Encomenda " + ORDER, TODAY_BY_GLS + DETAILS)

    assert result.kind is MailKind.OUT_FOR_DELIVERY
    assert result.confidence < CONFIDENCE_APPLY


def test_shipment_number_of_the_carrier_is_the_tracking_number() -> None:
    """A shipment number that is the named carrier's is its tracking number.

    It stays the shop's shipment number too, which its survey names.
    """
    result = _lm(
        "Encomenda em distribuição!",
        TODAY_BY_GLS + DETAILS.replace(ENVIO, GLS),
    )

    [shipment] = result.shipments
    assert (shipment.carrier, shipment.tracking_number) == ("gls", GLS)
    assert shipment.tracking_url == tracking_url("gls", GLS)
    assert shipment.reference == GLS


@pytest.mark.parametrize(
    "line",
    [
        f"Envio: {ENVIO}",
        f"Envio {ENVIO}",
        f"O seu envio {ENVIO} está em distribuição.",
        f"N.º de envio: {ENVIO}",
    ],
)
def test_shipment_number_labels(line: str) -> None:
    """The shipment number is read however the e-mail labels it."""
    result = _lm(
        "Encomenda em distribuição!",
        f"{TODAY_BY_GLS}{line}\nEncomenda n.º {ORDER}\n",
    )

    [shipment] = result.shipments
    assert shipment.reference == ENVIO
    assert result.order_numbers == (ORDER,)


@pytest.mark.parametrize(
    "text",
    [
        "Data de envio: 17/11/2026\n",
        "Envio gratuito em encomendas acima de 50 €.\n",
        "Prazo de envio: 3 a 5 dias úteis.\n",
    ],
)
def test_other_envio_lines_are_no_shipment_number(text: str) -> None:
    """Dates, prices and delays next to "envio" aren't shipment numbers."""
    result = _lm(
        "Encomenda em distribuição!",
        f"{TODAY_BY_GLS}{text}Encomenda n.º {ORDER}\n",
    )

    [shipment] = result.shipments
    assert shipment.reference is None
    assert shipment.tracking_number is None


def test_sold_by_leroy_merlin_has_no_seller() -> None:
    """Leroy Merlin's own products have no marketplace seller."""
    result = _lm(
        "A sua encomenda foi enviada",
        DETAILS.replace(SELLER, "LEROY MERLIN"),
    )

    [shipment] = result.shipments
    assert shipment.seller is None


@pytest.mark.parametrize(
    "text",
    [
        f"O volume {GLS} foi expedido e está a caminho.\n\nGLS Portugal\n",
        f"Número de envio: {GLS}\n",
    ],
)
def test_carrier_notice_sent_by_the_shop(text: str) -> None:
    """The shop forwards GLS's notices under GLS's name, without the order."""
    result = _lm("Informação sobre o seu envio", text, sender_name="GLS PT Informa")

    assert result.parser == "leroymerlin"
    assert result.kind is MailKind.SHIPPED
    assert result.merchant == "Leroy Merlin"
    assert is_confident(result)
    [shipment] = result.shipments
    assert (shipment.carrier, shipment.tracking_number) == ("gls", GLS)
    assert shipment.tracking_url == tracking_url("gls", GLS)
    # GLS's number, not the shop's shipment number.
    assert shipment.reference is None
    assert result.order_numbers == ()


def test_survey_only_confirms_the_delivery() -> None:
    """The survey after a shipment adds a delivery to its parcel, if known."""
    result = _lm(
        f"Queremos saber a sua opinião sobre o envio {ENVIO} de {SELLER}",
        "Olá Alex,\n\nComo correu a entrega? A sua opinião ajuda-nos a melhorar.\n\n"
        "Responder ao inquérito\n",
        "https://inqueritos.example.com/s/abc123",
    )

    assert result.kind is MailKind.DELIVERED
    assert result.merchant == "Leroy Merlin"
    assert result.order_numbers == ()
    assert is_confident(result)
    [shipment] = result.shipments
    assert shipment.reference == ENVIO
    assert shipment.seller == SELLER
    assert shipment.tracking_number is None
    assert shipment.attach_only
    # It doesn't say when the shipment came, only that it had by then.
    assert shipment.undated
    assert shipment.eta is None


def _applied(data: ParcelsData, result: ParseResult, when: datetime) -> str | None:
    [contribution] = result_contributions(
        result,
        message_hash=f"lm{when:%d%H%M}",
        time=when,
        source=Source.PARSER,
        label="leroymerlin.pt",
    )
    return apply_contribution(data, contribution, when).parcel_id


def test_survey_closes_the_shipment_tracked_by_its_number() -> None:
    """The survey finds its shipment when its number is the carrier's too."""
    data = ParcelsData()
    parcel_id = _applied(
        data,
        _lm("Encomenda em distribuição!", TODAY_BY_GLS + DETAILS.replace(ENVIO, GLS)),
        SENT,
    )
    assert parcel_id is not None

    survey = _lm(
        f"Queremos saber a sua opinião sobre o envio {GLS} de {SELLER}",
        "Olá Alex,\n\nComo correu a entrega?\n",
        date=SURVEYED,
    )

    assert _applied(data, survey, SURVEYED) == parcel_id
    state = data.parcels[parcel_id].state
    assert state.status is ParcelStatus.DELIVERED
    assert state.tracking_number == GLS
    # The tracking number isn't shown twice.
    assert state.references == ()


@pytest.mark.parametrize(
    "subject",
    [
        "Ofertas de inverno: até 30% de desconto",
        "Entrega grátis em todas as encomendas",
    ],
)
def test_newsletters_are_not_parcels(subject: str) -> None:
    """The newsletters come from a subdomain and are never about a parcel."""
    result = _lm(
        subject,
        "Descubra as novidades da semana para a sua casa.\n",
        sender="novidades@mailing.leroymerlin.pt",
    )

    assert result.parser == "leroymerlin"
    assert result.kind is MailKind.NOT_PARCEL


def test_unreadable_shipping_mail_goes_to_review() -> None:
    """A shipping e-mail the parser can't read goes to the AI or a person."""
    result = _lm("A sua encomenda está a caminho", "Olá Alex,\n\nAté breve!\n")

    assert result.parser == "leroymerlin"
    assert result.kind is MailKind.UNKNOWN
    assert NOTE_KNOWN_SENDER_UNPARSED in result.notes


def test_other_mail_is_not_a_parcel() -> None:
    """Account and marketing e-mails from the main domain aren't parcels."""
    result = _lm("Novidades para a sua casa", "Olá Alex,\n\nAté breve!\n")

    assert result.parser == "leroymerlin"
    assert result.kind is MailKind.NOT_PARCEL
