"""Tests for telling refunds, customer returns and parcels sent back apart."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.const import CONFIDENCE_APPLY, MailKind
from custom_components.parcels.parsers.base import (
    Eta,
    MailMessage,
    ParsedShipment,
    ParseResult,
)
from custom_components.parcels.parsers.returns import (
    NOTE_PICKUP_NEXT_WORKING_DAY,
    NOTE_REFUND,
    NOTE_RETURN_RECEIVED,
    Classification,
    Pickup,
    ReturnClass,
    classify,
    find_pickup,
    reclassify,
)

TZ = ZoneInfo("Europe/Lisbon")
# Tuesday 10 November 2026.
SENT = datetime(2026, 11, 10, 15, 20, tzinfo=UTC)
ORDER = "123-4567890-1234567"
ITEM = "Desk lamp, white"
FILLER = "Lorem ipsum dolor sit amet. " * 25


def _message(subject: str, text: str) -> MailMessage:
    """Return a synthetic e-mail sent on ``SENT``."""
    return MailMessage(
        message_id="<returns-test@example.com>",
        provider_id="returns-test",
        provider="google",
        mailbox="alex@example.com",
        sender="returns@store.example",
        sender_name="Example Store",
        subject=subject,
        date=SENT,
        text=text,
    )


def _result(kind: MailKind, confidence: float = 0.9) -> ParseResult:
    """Return a parser result with an order and an item."""
    return ParseResult(
        parser="amazon",
        kind=kind,
        merchant="Example Store",
        order_numbers=(ORDER,),
        shipments=[ParsedShipment(order_numbers=(ORDER,), items=(ITEM,))],
        items=(ITEM,),
        confidence=confidence,
        language="en",
    )


def _day(day: int) -> Eta:
    """Return a November 2026 date as an ETA."""
    return Eta(date(2026, 11, day), date(2026, 11, day))


@pytest.mark.parametrize(
    ("lang", "text", "pickup"),
    [
        (
            "pt",
            "A sua devolução foi registada.\nData de recolha: Dia útil seguinte",
            Pickup(None, next_working_day=True),
        ),
        (
            "es",
            "Tu devolución ha sido registrada.\nFecha de recogida: viernes, 13 de "
            "noviembre",
            Pickup(_day(13)),
        ),
        (
            "es",
            "Tu devolución ha sido registrada.\nFecha de recogida: siguiente día hábil",
            Pickup(None, next_working_day=True),
        ),
        (
            "en",
            "Your return is confirmed.\nPickup date: Thursday, 12 November",
            Pickup(_day(12)),
        ),
        (
            "en",
            "Your return is confirmed.\nCollection date: next business day",
            Pickup(None, next_working_day=True),
        ),
        (
            "de",
            "Ihre Rücksendung wurde angemeldet.\nAbholtermin: Donnerstag, 12. November",
            Pickup(_day(12)),
        ),
        (
            "de",
            "Ihre Rücksendung wurde angemeldet.\nAbholtermin: nächster Werktag",
            Pickup(None, next_working_day=True),
        ),
        (
            "fr",
            "Votre retour a été enregistré.\nDate d'enlèvement : jeudi 12 novembre",
            Pickup(_day(12)),
        ),
        (
            "fr",
            "Votre retour a été enregistré.\nDate d'enlèvement : prochain jour ouvré",
            Pickup(None, next_working_day=True),
        ),
        (
            "it",
            "Il tuo reso è stato registrato.\nData di ritiro: giovedì 12 novembre",
            Pickup(_day(12)),
        ),
        (
            "it",
            "Il tuo reso è stato registrato.\nData di ritiro: prossimo giorno lavorativo",
            Pickup(None, next_working_day=True),
        ),
        (
            "nl",
            "Je retour is aangemeld.\nOphaaldatum: donderdag 12 november",
            Pickup(_day(12)),
        ),
        (
            "nl",
            "Je retour is aangemeld.\nOphaaldatum: volgende werkdag",
            Pickup(None, next_working_day=True),
        ),
    ],
)
def test_pickup_labels(lang: str, text: str, pickup: Pickup) -> None:
    """A return's pickup label is read in every language, as a date or a rule."""
    message = _message("Information about your item", text)
    assert classify(message.subject, message.text) == Classification(
        ReturnClass.PICKUP, language=lang, customer=True
    )
    assert find_pickup(message, TZ) == pickup


@pytest.mark.parametrize(
    ("subject", "text", "expected"),
    [
        # A refund named first in the subject.
        (
            "Refund for your return",
            "Your return was received.",
            Classification(ReturnClass.REFUND, in_subject=True),
        ),
        (
            "Reembolso da sua devolução",
            "Olá Alex Doe.",
            Classification(ReturnClass.REFUND, in_subject=True),
        ),
        # A refund the body says was made outranks the return in the subject.
        (
            "Update on your return",
            "We've issued your refund of €12.99.",
            Classification(ReturnClass.REFUND),
        ),
        (
            "A sua devolução",
            "O seu reembolso foi processado.",
            Classification(ReturnClass.REFUND),
        ),
        (
            "Ihre Rücksendung",
            "Der Betrag wurde Ihnen erstattet.",
            Classification(ReturnClass.REFUND),
        ),
        # A refund promised in a return's first e-mail is no refund yet.
        (
            "Your return and refund",
            "We'll refund you once we receive the item.",
            Classification(ReturnClass.CUSTOMER, in_subject=True),
        ),
        (
            "Your return label",
            "Your refund will be processed when we receive the item.",
            Classification(ReturnClass.CUSTOMER, in_subject=True),
        ),
        # The subject says what the e-mail is about; the body comes second.
        (
            "Your return label",
            "Attach the label to the box. A parcel that could not be delivered "
            "to our warehouse comes back to you.",
            Classification(ReturnClass.CUSTOMER, in_subject=True),
        ),
        # A refund only named in the body, under a subject without a return.
        (
            "Update on order 123",
            "Refund: €12.99 for the returned item.",
            Classification(ReturnClass.REFUND, weak=True),
        ),
        # The shop has the item back.
        (
            "Your return has been received",
            "Olá Alex Doe.",
            Classification(ReturnClass.CUSTOMER, in_subject=True, received=True),
        ),
        (
            "Information about your item",
            "Hemos recibido tu devolución.",
            Classification(ReturnClass.CUSTOMER, received=True),
        ),
        # A parcel going back to its sender, or a failed delivery.
        (
            "Your parcel",
            "Your parcel couldn't be delivered and is being returned to the sender.",
            Classification(ReturnClass.TO_SENDER),
        ),
        (
            "A sua encomenda foi devolvida ao remetente",
            "Olá Alex Doe.",
            Classification(ReturnClass.TO_SENDER, in_subject=True),
        ),
        (
            "Ihr Paket",
            "Ihr Paket ist unzustellbar und geht zurück an den Absender.",
            Classification(ReturnClass.TO_SENDER),
        ),
        (
            "Il tuo pacco",
            "Il pacco è stato restituito al mittente.",
            Classification(ReturnClass.TO_SENDER),
        ),
        (
            "Je pakket",
            "Je pakket wordt retour afzender gestuurd.",
            Classification(ReturnClass.TO_SENDER),
        ),
        (
            "Votre colis",
            "Votre colis a été retourné à l'expéditeur.",
            Classification(ReturnClass.TO_SENDER),
        ),
        (
            "Tu paquete",
            "Tu paquete ha sido devuelto al remitente.",
            Classification(ReturnClass.TO_SENDER),
        ),
    ],
)
def test_classify(subject: str, text: str, expected: Classification) -> None:
    """Refunds, customer returns and parcels sent back are told apart."""
    assert classify(subject, text) == expected


@pytest.mark.parametrize(
    ("subject", "text"),
    [
        # Policies, footer links and free-returns banners.
        (
            "Your order has shipped",
            "Free returns within 30 days. Returns & Orders. Return policy.",
        ),
        (
            "Your order has shipped",
            "Return & refund policy. Returns and refunds. Refund policy.",
        ),
        (
            "A sua encomenda foi enviada",
            "Política de devoluções. Devoluções e encomendas. Devoluções gratuitas.",
        ),
        (
            "Ihre Bestellung wurde versandt",
            "Kostenlose Rücksendung. Rücksendungen & Bestellungen.",
        ),
        # A feedback request ("votre retour") is no return either.
        (
            "Votre commande a été expédiée",
            "Donnez votre retour d'expérience sur votre commande.",
        ),
        # A click-and-collect date, with a policy link as its only return word.
        (
            "Your order is ready for collection",
            "Collection date: Thursday, 12 November.\nReturn & refund policy.",
        ),
        # A locker's collection deadline isn't a return's pickup date.
        (
            "Tu paquete te espera",
            "Fecha límite de recogida: viernes, 20 de noviembre. Después se "
            "iniciará la devolución.",
        ),
        # A pickup label without a return word nearby: not a return.
        ("Recolha de resíduos", "Data de recolha: 12 de novembro"),
        # "Devolver" is also a locker's "will be returned".
        (
            "Recolha da sua encomenda",
            "Data de recolha: 12 de novembro. Se não estiver em casa, vamos "
            "devolver a encomenda ao vendedor.",
        ),
    ],
)
def test_not_about_a_return(subject: str, text: str) -> None:
    """Footers, lockers and other pickups say nothing about a return."""
    assert classify(subject, text) is None


def test_pickup_label_needs_a_return_word_nearby() -> None:
    """A pickup label far from any return word doesn't count."""
    near = "A sua devolução foi registada.\nData de recolha: 12 de novembro"
    far = f"A sua devolução foi registada.\n{FILLER}\nData de recolha: 12 de novembro"
    assert classify("Informação", near) == Classification(
        ReturnClass.PICKUP, language="pt", customer=True
    )
    assert classify("Informação", far) == Classification(ReturnClass.CUSTOMER)
    assert find_pickup(_message("Informação", far), TZ) is None


def test_refund_explained_in_a_footer_is_no_refund() -> None:
    """Only the top of the body says a refund was made; footers explain."""
    text = (
        f"Your return is confirmed.\n{FILLER * 5}\n"
        "When your refund has been issued, we'll e-mail you."
    )
    assert classify("Your return is confirmed", text) == Classification(
        ReturnClass.CUSTOMER, in_subject=True
    )


def test_refund_estimate_of_a_return_is_no_refund() -> None:
    """A return e-mail may name its refund first; it's still about the return."""
    message = _message("Devolução do artigo", "Reembolso estimado: 12,99 €.")
    assert classify(message.subject, message.text) is None
    result = reclassify(_result(MailKind.RETURN), message, TZ, merchant=True)
    assert result.kind is MailKind.CUSTOMER_RETURN


def test_return_word_in_the_subject_counts_for_any_label() -> None:
    """With a return in the subject, a label anywhere in the body counts."""
    text = f"{FILLER}\nData de recolha: 12 de novembro"
    assert classify("Devoluções", text) == Classification(
        ReturnClass.PICKUP, language="pt"
    )


@pytest.mark.parametrize(
    ("merchant", "kind"),
    [(True, MailKind.CUSTOMER_RETURN), (False, MailKind.RETURN)],
)
def test_unclassified_return(merchant: bool, kind: MailKind) -> None:
    """A shop's own "return" e-mail is a customer return; others stay as read."""
    message = _message("Devolução", "Olá Alex Doe.")
    result = reclassify(_result(MailKind.RETURN), message, TZ, merchant=merchant)
    assert result.kind is kind
    assert result.order_numbers == (ORDER,)
    assert result.items == (ITEM,)
    assert result.confidence == 0.9


def test_customer_return_keeps_its_order_and_pickup() -> None:
    """A customer return keeps the order, the items and the pickup day."""
    message = _message(
        "Your return is confirmed",
        "Your return is confirmed.\nPickup date: Thursday, 12 November",
    )
    result = reclassify(_result(MailKind.RETURN, 0.6), message, TZ, merchant=True)
    assert result.kind is MailKind.CUSTOMER_RETURN
    assert result.confidence == 0.8
    assert result.order_numbers == (ORDER,)
    assert result.items == (ITEM,)
    assert result.notes == ()
    [shipment] = result.shipments
    assert shipment.eta == _day(12)
    assert shipment.order_numbers == (ORDER,)
    assert shipment.items == (ITEM,)


def test_next_working_day_is_a_note() -> None:
    """Leave "next working day" to the engine, which knows the holidays."""
    message = _message(
        "Confirmação da sua devolução",
        "A sua devolução foi registada.\nData de recolha: Dia útil seguinte",
    )
    result = reclassify(_result(MailKind.RETURN), message, TZ, merchant=True)
    assert result.kind is MailKind.CUSTOMER_RETURN
    assert result.notes == (NOTE_PICKUP_NEXT_WORKING_DAY,)
    assert result.shipments[0].eta is None


def test_received_return_is_noted() -> None:
    """A return the shop has back is marked as received."""
    message = _message("Your return has been received", "Thanks, Alex Doe.")
    result = reclassify(_result(MailKind.RETURN), message, TZ, merchant=True)
    assert result.kind is MailKind.CUSTOMER_RETURN
    assert result.notes == (NOTE_RETURN_RECEIVED,)


@pytest.mark.parametrize("merchant", [True, False])
@pytest.mark.parametrize(
    "kind", [MailKind.RETURN, MailKind.UNKNOWN, MailKind.NOT_PARCEL]
)
def test_refund_is_dropped(kind: MailKind, merchant: bool) -> None:
    """A refund becomes NOT_PARCEL with the refund note, with nothing kept."""
    message = _message("Your refund", "We've issued your refund of €12.99.")
    result = reclassify(_result(kind), message, TZ, merchant=merchant)
    assert result == ParseResult(
        parser="amazon",
        kind=MailKind.NOT_PARCEL,
        merchant="Example Store",
        confidence=1.0,
        language="en",
        notes=(NOTE_REFUND,),
    )


@pytest.mark.parametrize(
    ("kind", "confidence", "dropped"),
    [
        (MailKind.RETURN, 0.9, True),
        (MailKind.UNKNOWN, 0.9, False),
        (MailKind.NOT_PARCEL, CONFIDENCE_APPLY, True),
        (MailKind.NOT_PARCEL, CONFIDENCE_APPLY - 0.01, False),
    ],
    ids=["return", "unknown", "sure-not-parcel", "doubtful-not-parcel"],
)
def test_weak_refund_ends_a_return_or_a_sure_not_parcel(
    kind: MailKind, confidence: float, dropped: bool
) -> None:
    """A refund only named in the body drops a "return" or "not a parcel" e-mail.

    A doubtful "not a parcel", such as the AI's for an e-mail with a tracking
    number, stays for review; an unread e-mail is read as usual.
    """
    message = _message("Update on order 123", "Refund: €12.99 for the returned item.")
    result = reclassify(_result(kind, confidence), message, TZ, merchant=True)
    assert (result.notes == (NOTE_REFUND,)) is dropped
    assert result.kind is (MailKind.NOT_PARCEL if dropped else kind)


def test_parcel_sent_back_stays_a_return() -> None:
    """A parcel going back to its sender is no customer return."""
    message = _message(
        "Your parcel",
        "Your parcel couldn't be delivered and is being returned to the sender.",
    )
    original = _result(MailKind.RETURN)
    assert reclassify(original, message, TZ, merchant=True) is original


def test_not_parcel_is_not_rescued() -> None:
    """A feedback request about a return stays NOT_PARCEL."""
    message = _message(
        "How was your return?",
        "Your return is confirmed.\nPickup date: Thursday, 12 November",
    )
    original = _result(MailKind.NOT_PARCEL)
    assert reclassify(original, message, TZ, merchant=True) is original


def test_unknown_pickup_needs_customer_wording() -> None:
    """A pickup label in an unread e-mail counts with customer wording only."""
    bare = _message("Devoluções", "Data de recolha: 12 de novembro")
    original = _result(MailKind.UNKNOWN, 0.0)
    assert reclassify(original, bare, TZ, merchant=True) is original
    worded = _message(
        "Devoluções", "A sua devolução foi registada.\nData de recolha: 12 de novembro"
    )
    result = reclassify(original, worded, TZ, merchant=True)
    assert result.kind is MailKind.CUSTOMER_RETURN
    assert result.confidence == 0.8
    assert result.shipments[0].eta == _day(12)


@pytest.mark.parametrize(
    ("merchant", "kind"),
    [(True, MailKind.CUSTOMER_RETURN), (False, MailKind.UNKNOWN)],
)
def test_customer_subject_of_an_unread_shop_email(
    merchant: bool, kind: MailKind
) -> None:
    """A shop's unread e-mail with a return subject is a customer return."""
    message = _message("Your return label", "Print the attached label.")
    result = reclassify(_result(MailKind.UNKNOWN, 0.0), message, TZ, merchant=merchant)
    assert result.kind is kind
    if merchant:
        assert result.confidence == 0.7


@pytest.mark.parametrize(
    ("subject", "text"),
    [
        ("Your order has shipped", "Your return label is in the Returns Centre."),
        (
            "Your replacement has shipped",
            "We've issued your refund for the missing item.",
        ),
    ],
)
def test_other_kinds_are_left_alone(subject: str, text: str) -> None:
    """Shipping e-mails keep their kind, whatever else they say."""
    message = _message(subject, text)
    original = _result(MailKind.SHIPPED)
    assert reclassify(original, message, TZ, merchant=True) is original
