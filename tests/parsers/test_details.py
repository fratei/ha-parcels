"""Tests for the details read from parcel e-mails.

The collect-by date of a pickup, the next attempt after a missed one and
where a delivered parcel was left (``parsers.details``).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
import logging
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.const import LeftAt, MailKind, ParcelStatus
from custom_components.parcels.parsers import details, parse_message
from custom_components.parcels.parsers.base import (
    Eta,
    MailMessage,
    ParsedShipment,
    ParseResult,
    SenderVerdict,
)
from custom_components.parcels.parsers.details import (
    add_details,
    find_left_at,
    tracker_details,
)

from .conftest import EMAIL_FIXTURES

# Monday 15 June 2026.
SENT = datetime(2026, 6, 15, 15, 20, tzinfo=UTC)

NEIGHBOUR = LeftAt.NEIGHBOUR
MAILBOX = LeftAt.MAILBOX
DOOR = LeftAt.DOOR
RECEPTION = LeftAt.RECEPTION
GARAGE = LeftAt.GARAGE
LOCKER = LeftAt.LOCKER


def _message(text: str, subject: str = "Your parcel") -> MailMessage:
    """Return a synthetic carrier e-mail sent on ``SENT``."""
    return MailMessage(
        message_id="<details-test@example.com>",
        provider_id="details-test",
        provider="google",
        mailbox="alex@example.com",
        sender="noreply@carrier.example",
        sender_name="Example Carrier",
        subject=subject,
        date=SENT,
        text=text,
    )


def _result(kind: MailKind, *, eta: Eta | None = None) -> ParseResult:
    """Return a carrier's result with one shipment of ``kind``."""
    return ParseResult(
        parser="generic",
        kind=kind,
        shipments=[
            ParsedShipment(carrier="gls", tracking_number="58200417310", eta=eta)
        ],
        confidence=0.9,
        language="en",
    )


@pytest.mark.parametrize(
    ("lang", "text", "expected"),
    [
        ("en", "Your parcel was left with your neighbour at No. 12.", NEIGHBOUR),
        ("en", "Delivered on Monday 15 June to your neighbour.", NEIGHBOUR),
        ("en", "Left next door.", NEIGHBOUR),
        ("en", "Your parcel was delivered to your letterbox.", MAILBOX),
        ("en", "Left at\nFront door", DOOR),
        ("en", "Delivered, Front door", DOOR),
        ("en", "Non-contact delivery: left at the front door.", DOOR),
        ("en", "Your parcel was handed to the concierge.", RECEPTION),
        ("en", "Signed for by: Reception", RECEPTION),
        ("en", "Your parcel was left in the garage.", GARAGE),
        ("en", "Your parcel was delivered to a parcel locker.", LOCKER),
        ("pt", "A sua encomenda foi entregue ao vizinho.", NEIGHBOUR),
        ("pt", "Entregue na caixa de correio.", MAILBOX),
        ("pt", "Entregue a Porta da frente", DOOR),
        (None, "Entregue a Porta da frente", DOOR),
        ("pt", "Recebido por: Porteiro", RECEPTION),
        ("pt", "A sua encomenda encontra-se entregue na receção.", RECEPTION),
        ("pt", "A encomenda foi deixada na garagem.", GARAGE),
        ("pt", "Deixado no cacifo", LOCKER),
        ("es", "Entregado a tu vecino.", NEIGHBOUR),
        ("es", "Tu paquete ha sido depositado en el buzón.", MAILBOX),
        ("es", "Tu paquete se ha dejado en la puerta principal.", DOOR),
        ("es", "Entregado en conserjería.", RECEPTION),
        ("de", "Ihr Paket wurde beim Nachbarn abgegeben.", NEIGHBOUR),
        ("de", "Ihre Sendung wurde in Ihren Briefkasten eingeworfen.", MAILBOX),
        ("de", "Ihr Paket wurde vor der Tür abgestellt.", DOOR),
        ("de", "Zustellort Haustür", DOOR),
        ("de", "Ihr Paket wurde am Empfang abgegeben.", RECEPTION),
        ("de", "Zustellort\nGarage", GARAGE),
        ("de", "Ihr Paket wurde im Paketkasten abgelegt.", LOCKER),
        ("fr", "Votre colis a été remis à votre voisin.", NEIGHBOUR),
        ("fr", "Votre colis a été déposé dans votre boîte aux lettres.", MAILBOX),
        ("fr", "Votre colis a été déposé devant votre porte.", DOOR),
        ("fr", "Livré à l'accueil.", RECEPTION),
        ("it", "Il pacco è stato lasciato al vicino.", NEIGHBOUR),
        ("it", "Il pacco è stato messo nella cassetta delle lettere.", MAILBOX),
        ("it", "Il pacco è stato consegnato al portiere.", RECEPTION),
        ("it", "Luogo di consegna Portineria", RECEPTION),
        ("it", "Consegnato nell'armadietto.", LOCKER),
        ("nl", "Je pakket is bij de buren bezorgd.", NEIGHBOUR),
        ("nl", "Je pakket is bezorgd bij de buren.", NEIGHBOUR),
        ("nl", "Je pakket is in de brievenbus geleverd.", MAILBOX),
        ("nl", "Je pakket is afgeleverd bij de voordeur.", DOOR),
        ("nl", "Je pakket is afgegeven bij de receptie.", RECEPTION),
    ],
)
def test_left_at(lang: str | None, text: str, expected: LeftAt) -> None:
    """Where a parcel was left, in the 7 languages."""
    assert find_left_at(text, lang) is expected


@pytest.mark.parametrize(
    ("lang", "text"),
    [
        # Names of people and items aren't places.
        ("pt", "Recebido por Alex Doe"),
        ("en", "Delivered: A garage rack"),
        ("en", "Delivered\nGarage rack"),
        # A delivery to the address isn't a place it was left.
        ("en", "Delivered to your door."),
        ("pt", "Entregue à porta."),
        ("en", "We offer door to door delivery."),
        # Not done, not yet done, or only possible.
        ("en", "Your parcel was not left with a neighbour."),
        ("en", "We weren't able to leave it, so it wasn't left in the mailbox."),
        ("pt", "A encomenda não foi deixada na garagem."),
        ("es", "No hemos dejado el paquete en el buzón."),
        ("de", "Ihr Paket wurde nicht beim Nachbarn abgegeben."),
        ("it", "Il pacco non è stato lasciato al vicino."),
        ("nl", "Je pakket is niet bij de buren bezorgd."),
        ("en", "If you're out, it can be left with a neighbour."),
        ("en", "Your parcel can be left with a neighbour."),
        ("en", "Next time it can be left in the garage."),
        ("pt", "Se não estiver em casa, a encomenda será entregue a um vizinho."),
        ("pt", "Pode escolher ser entregue na portaria."),
        ("es", "Si no estás, se entregará a un vecino."),
        ("es", "Los paquetes van a ser entregados en la portería."),
        ("de", "Ihr Paket wird beim Nachbarn abgegeben."),
        ("de", "Falls Sie nicht da sind, wird es beim Nachbarn abgegeben."),
        ("fr", "Si vous êtes absent, votre colis sera remis à un voisin."),
        ("nl", "Je pakket wordt bij de buren bezorgd."),
        ("nl", "Indien je niet thuis bent, bezorgen we bij de buren."),
        ("en", "Was it left with a neighbour?"),
        # A card left for a missed delivery, and footers.
        ("en", "We left a card in your letterbox."),
        (
            "de",
            "Wir haben eine Benachrichtigungskarte in Ihren Briefkasten eingeworfen.",
        ),
        ("fr", "Nous avons laissé un avis de passage dans votre boîte aux lettres."),
        ("en", "This email was sent from an unattended mailbox."),
        ("fr", "Retour à la page d'accueil"),
        # "vicino" is also "near".
        ("it", "Il pacco è stato lasciato vicino alla porta."),
    ],
)
def test_no_left_at(lang: str, text: str) -> None:
    """Names, offers, denials, notice cards and footers give no place."""
    assert find_left_at(text, lang) is None


DELIVERED_PLACES = {
    "amazon/delivered_nl.eml": DOOR,
    "amazon/delivered_photo_es.eml": DOOR,
    "carriers/dhl_express_delivered_it.eml": RECEPTION,
    "carriers/dpd_delivered_de.eml": DOOR,
    "carriers/fedex_delivered_en.eml": DOOR,
    "carriers/gls_delivered_en.eml": DOOR,
    "carriers/ups_delivered_pt.eml": DOOR,
}


def _parse_fixtures(
    tz: ZoneInfo,
    verdict_for: Callable[..., SenderVerdict],
    load_eml: Callable[..., MailMessage],
) -> list[tuple[str, MailMessage, ParseResult]]:
    parsed = []
    for path in sorted(EMAIL_FIXTURES.rglob("*.eml")):
        name = path.relative_to(EMAIL_FIXTURES).as_posix()
        message = load_eml(name)
        parsed.append((name, message, parse_message(message, verdict_for(message), tz)))
    return parsed


def test_fixture_places(
    tz: ZoneInfo,
    verdict_for: Callable[..., SenderVerdict],
    load_eml: Callable[..., MailMessage],
) -> None:
    """Delivered e-mails get the place they name, the others none.

    Receivers' names ("Recebido por ...") aren't places, and a carrier's
    "unattended mailbox" footer isn't the mailbox.
    """
    places = {}
    for name, _message, result in _parse_fixtures(tz, verdict_for, load_eml):
        for shipment in result.shipments:
            if (shipment.kind or result.kind) is MailKind.DELIVERED:
                places[name] = shipment.left_at
            else:
                assert shipment.left_at is None, name
    assert {name: place for name, place in places.items() if place} == (
        DELIVERED_PLACES
    )
    assert len(places) > len(DELIVERED_PLACES)


def test_fixture_pickups_and_attempts(
    tz: ZoneInfo,
    verdict_for: Callable[..., SenderVerdict],
    load_eml: Callable[..., MailMessage],
) -> None:
    """Pickup notices get their collect-by date, missed attempts the next one."""
    pickups = attempts = 0
    for name, message, result in _parse_fixtures(tz, verdict_for, load_eml):
        for shipment in result.shipments:
            kind = shipment.kind or result.kind
            if kind is MailKind.READY_FOR_PICKUP:
                pickups += 1
                if shipment.eta is not None:
                    # Carriers' pickup windows end on the last day.
                    assert shipment.collect_by == shipment.eta.end, name
                else:
                    # Amazon: "Collect by: <the same weekday a week later>".
                    assert shipment.collect_by == message.date.date() + timedelta(
                        days=7
                    ), name
                assert shipment.next_attempt is None, name
            elif kind is MailKind.ATTEMPTED:
                attempts += 1
                if name == "carriers/ctt_attempted_pt.eml":
                    # Collectable for 10 working days from the next day.
                    assert shipment.collect_by == date(2026, 12, 1)
                    assert shipment.next_attempt is None
                else:
                    assert shipment.next_attempt == shipment.eta.start, name
                    assert shipment.collect_by is None, name
            else:
                assert shipment.collect_by is None, name
                assert shipment.next_attempt is None, name
    assert pickups >= 10
    assert attempts >= 3


def test_add_details_by_kind(tz: ZoneInfo) -> None:
    """Each kind gets only its own details."""
    message = _message(
        "We missed you today. We'll try again tomorrow. "
        "Your parcel was left with your neighbour. "
        "Collect it by Friday."
    )
    delivered = add_details(_result(MailKind.DELIVERED), message, tz)
    assert delivered.shipments[0].left_at is NEIGHBOUR
    assert delivered.shipments[0].collect_by is None
    assert delivered.shipments[0].next_attempt is None

    attempted = add_details(_result(MailKind.ATTEMPTED), message, tz)
    assert attempted.shipments[0].next_attempt == date(2026, 6, 16)
    assert attempted.shipments[0].collect_by == date(2026, 6, 19)
    assert attempted.shipments[0].left_at is None

    pickup = add_details(_result(MailKind.READY_FOR_PICKUP), message, tz)
    assert pickup.shipments[0].collect_by == date(2026, 6, 19)
    assert pickup.shipments[0].next_attempt is None
    assert pickup.shipments[0].left_at is None

    for kind in (MailKind.IN_TRANSIT, MailKind.OUT_FOR_DELIVERY, MailKind.SHIPPED):
        result = _result(kind)
        assert add_details(result, message, tz) is result


def test_add_details_keeps_the_original(tz: ZoneInfo) -> None:
    """A new result is returned; the parser's own is left as it was."""
    result = _result(MailKind.DELIVERED)
    updated = add_details(result, _message("Left with your neighbour."), tz)
    assert updated.shipments[0].left_at is NEIGHBOUR
    assert result.shipments[0].left_at is None


def test_add_details_reads_the_subject(tz: ZoneInfo) -> None:
    """When the body doesn't say where, the subject may."""
    message = _message(
        "Track your parcel in the app.", subject="Delivered: left in your mailbox"
    )
    result = add_details(_result(MailKind.DELIVERED), message, tz)
    assert result.shipments[0].left_at is MAILBOX


def test_add_details_uses_each_shipments_kind(tz: ZoneInfo) -> None:
    """A shipment's own kind wins over the e-mail's."""
    result = _result(MailKind.IN_TRANSIT)
    result.shipments.append(
        ParsedShipment(
            carrier="gls", tracking_number="58200417328", kind=MailKind.DELIVERED
        )
    )
    updated = add_details(result, _message("Left with your neighbour."), tz)
    assert [s.left_at for s in updated.shipments] == [None, NEIGHBOUR]


@pytest.mark.parametrize("kind", [MailKind.NOT_PARCEL, MailKind.UNKNOWN])
def test_add_details_skips_other_mail(kind: MailKind, tz: ZoneInfo) -> None:
    """E-mails that aren't about a parcel are left alone."""
    result = ParseResult(
        parser="generic",
        kind=kind,
        shipments=[ParsedShipment(kind=MailKind.DELIVERED)],
    )
    assert add_details(result, _message("Left with your neighbour."), tz) is result


def test_add_details_never_raises(
    tz: ZoneInfo, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An error leaves the result as it was and logs only the error's type."""

    def broken(text: str, lang: str | None) -> LeftAt | None:
        raise ValueError(text)

    monkeypatch.setattr(details, "find_left_at", broken)
    result = _result(MailKind.DELIVERED)
    with caplog.at_level(logging.DEBUG, logger=details.__name__):
        assert add_details(result, _message("Left with your neighbour."), tz) is result
    assert "ValueError" in caplog.text
    assert "neighbour" not in caplog.text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Delivered - Front door", DOOR),
        ("Delivered: Garage", GARAGE),
        ("Zugestellt - Briefkasten", MAILBOX),
        ("Entregue \u2013 Vizinho", NEIGHBOUR),
        ("Livré : Boîte aux lettres", MAILBOX),
        ("Consegnato \u2014 Portineria", RECEPTION),
        ("Bezorgd - Brievenbus", MAILBOX),
        ("Delivered - Parcel locker", LOCKER),
    ],
)
def test_left_at_in_a_tracker_line(text: str, expected: LeftAt) -> None:
    """In a tracker's status line, a dash or a colon after the verb names it.

    In an e-mail, the words after such a colon may be an item.
    """
    assert find_left_at(text, tracker=True) is expected
    assert find_left_at(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "Delivered",
        "Delivered - Signed by A. Example",
        "Entregue - Assinado por A. Exemplo",
    ],
)
def test_no_left_at_in_a_tracker_line(text: str) -> None:
    """A tracker line with no place, or a name, gives none."""
    assert find_left_at(text, tracker=True) is None


def test_tracker_details_by_status(tz: ZoneInfo) -> None:
    """Each status reads only its own details from a tracker's event."""
    delivered = "Delivered - Front door"
    assert tracker_details(delivered, ParcelStatus.DELIVERED, SENT, tz) == {
        "left_at": DOOR
    }
    for status in (
        ParcelStatus.SHIPPED,
        ParcelStatus.IN_TRANSIT,
        ParcelStatus.OUT_FOR_DELIVERY,
        None,
    ):
        assert tracker_details(delivered, status, SENT, tz) == {}

    pickup = "Disponível para levantamento até 22/06"
    assert tracker_details(pickup, ParcelStatus.READY_FOR_PICKUP, SENT, tz) == {
        "collect_by": date(2026, 6, 22)
    }
    assert tracker_details(pickup, ParcelStatus.ATTEMPTED, SENT, tz) == {
        "collect_by": date(2026, 6, 22)
    }
    # A plain deadline is the last day to collect on a pickup notice only.
    plain = "Disponível até 22/06"
    assert tracker_details(plain, ParcelStatus.READY_FOR_PICKUP, SENT, tz) == {
        "collect_by": date(2026, 6, 22)
    }
    assert tracker_details(plain, ParcelStatus.ATTEMPTED, SENT, tz) == {}

    attempt = "Empfänger nicht angetroffen. Neuer Zustellversuch am Mittwoch"
    assert tracker_details(attempt, ParcelStatus.ATTEMPTED, SENT, tz) == {
        "next_attempt": date(2026, 6, 17)
    }
    # A next attempt follows a missed one only.
    assert tracker_details(attempt, ParcelStatus.READY_FOR_PICKUP, SENT, tz) == {}


def test_tracker_details_without_a_day(tz: ZoneInfo) -> None:
    """An event whose day isn't known gives no dates, only where it was left."""
    assert (
        tracker_details(
            "Disponível para levantamento até 22/06",
            ParcelStatus.READY_FOR_PICKUP,
            None,
            tz,
        )
        == {}
    )
    assert (
        tracker_details(
            "Not home. Next attempt Wednesday", ParcelStatus.ATTEMPTED, None, tz
        )
        == {}
    )
    assert tracker_details(
        "Delivered - Front door", ParcelStatus.DELIVERED, None, tz
    ) == {"left_at": DOOR}


@pytest.mark.parametrize("text", [None, ""])
def test_tracker_details_without_text(text: str | None, tz: ZoneInfo) -> None:
    """An event without text gives nothing."""
    assert tracker_details(text, ParcelStatus.DELIVERED, SENT, tz) == {}


def test_tracker_details_never_raises(
    tz: ZoneInfo, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An error gives nothing and logs only the error's type."""

    def broken(text: str, *args: object, **kwargs: object) -> date | None:
        raise ValueError(text)

    monkeypatch.setattr(details, "find_collect_by", broken)
    with caplog.at_level(logging.DEBUG, logger=details.__name__):
        assert (
            tracker_details(
                "Disponível para levantamento até 22/06",
                ParcelStatus.READY_FOR_PICKUP,
                SENT,
                tz,
            )
            == {}
        )
    assert "ValueError" in caplog.text
    assert "levantamento" not in caplog.text
