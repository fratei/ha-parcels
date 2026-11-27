"""Tests for the carrier parsers' entry point and shared behaviour.

This module also holds the helpers the per-carrier test modules share. Each
carrier fixture is named ``<name>_<language>.eml`` and is read in the time
zone of a user who gets e-mails in that language.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time
import logging
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.const import CONFIDENCE_APPLY, MailKind
from custom_components.parcels.parsers import carriers, senders
from custom_components.parcels.parsers.base import (
    Eta,
    MailMessage,
    ParseResult,
    SenderVerdict,
)
from custom_components.parcels.parsers.carriers import CARRIER_PARSERS, parse_carrier
from custom_components.parcels.parsers.tracking import (
    normalize_tracking_number,
    tracking_url,
    validate_tracking_number,
)

type Loader = Callable[..., MailMessage]
type VerdictFor = Callable[..., SenderVerdict]

FIXTURES = Path(__file__).parent.parent / "fixtures" / "emails" / "carriers"
ZONES = {
    "pt": "Europe/Lisbon",
    "en": "Europe/London",
    "es": "Europe/Madrid",
    "de": "Europe/Berlin",
    "fr": "Europe/Paris",
    "it": "Europe/Rome",
    "nl": "Europe/Amsterdam",
}
# A clear layout and kind with a validated number.
CLEAR = 0.85
LISBON = ZoneInfo("Europe/Lisbon")
CTT = SenderVerdict(domain="ctt.pt", authenticated=True, known=True)


def zone(name: str) -> ZoneInfo:
    """Return the time zone of the user who gets fixture ``name``."""
    return ZoneInfo(ZONES[name.rsplit("_", 1)[1]])


def eta(
    day: str, start: str | None = None, end: str | None = None, *, until: str = ""
) -> Eta:
    """Build an Eta: one day with an optional window, or a range of days."""
    first = date.fromisoformat(day)
    return Eta(
        first,
        date.fromisoformat(until) if until else first,
        time.fromisoformat(start) if start else None,
        time.fromisoformat(end) if end else None,
    )


@dataclass(frozen=True, slots=True)
class Case:
    """What a carrier fixture must parse to.

    ``carrier`` defaults to ``parser``; ``event`` is a local ISO date and
    time in the fixture's time zone.
    """

    name: str
    parser: str
    kind: MailKind
    number: str
    carrier: str | None = None
    eta: Eta | None = None
    event: str | None = None
    pickup_point: str | None = None
    pickup_code: str | None = None
    merchant: str | None = None
    notes: tuple[str, ...] = ()


def _load(
    name: str, load_eml: Loader, verdict_for: VerdictFor
) -> tuple[MailMessage, SenderVerdict, str]:
    """Load a fixture and check that it comes from a verified carrier sender.

    Returns the message, its verdict and the parser its sender routes to.
    """
    message = load_eml(f"carriers/{name}.eml")
    verdict = verdict_for(message)
    assert verdict.verified
    info = senders.lookup(message.sender_domain)
    assert info is not None
    assert info.parser in CARRIER_PARSERS
    return message, verdict, info.parser


def check_case(case: Case, load_eml: Loader, verdict_for: VerdictFor) -> None:
    """Assert that the fixture of ``case`` parses to what the case expects."""
    message, verdict, parser = _load(case.name, load_eml, verdict_for)
    assert parser == case.parser
    check_result(case, message, verdict)


def check_result(case: Case, message: MailMessage, verdict: SenderVerdict) -> None:
    """Assert that the carrier parser of ``case`` reads ``message`` as expected."""
    tz = zone(case.name)
    result = parse_carrier(message, verdict, tz, case.parser)
    assert result is not None
    carrier = case.carrier or case.parser
    assert result.parser == case.parser
    assert result.kind is case.kind
    assert result.merchant == case.merchant
    assert result.language == case.name.rsplit("_", 1)[1]
    assert result.notes == case.notes
    assert CLEAR <= result.confidence <= 1
    [shipment] = result.shipments
    assert shipment.carrier == carrier
    assert shipment.tracking_number == case.number
    assert normalize_tracking_number(case.number) == case.number
    assert validate_tracking_number(case.number, carrier)
    assert shipment.kind is case.kind
    assert shipment.eta == case.eta
    event = None
    if case.event is not None:
        event = datetime.fromisoformat(case.event).replace(tzinfo=tz)
    assert shipment.event_time == event
    assert shipment.pickup_point == case.pickup_point
    assert shipment.pickup_code == case.pickup_code
    assert shipment.tracking_url == tracking_url(carrier, case.number)


def check_negative(name: str, load_eml: Loader, verdict_for: VerdictFor) -> None:
    """Assert that a carrier e-mail without parcel news parses to None."""
    message, verdict, parser = _load(name, load_eml, verdict_for)
    assert parse_carrier(message, verdict, zone(name), parser) is None


def _message(
    text: str,
    subject: str = "Atualização do seu envio",
    *,
    sender: str = "notificacoes@ctt.pt",
    sender_name: str = "CTT",
) -> MailMessage:
    """Return an e-mail with ``text`` as its body, from CTT by default."""
    return MailMessage(
        message_id="<20261117093000.ab12@mail.example.com>",
        provider_id="test",
        provider="google",
        mailbox="alex@example.com",
        sender=sender,
        sender_name=sender_name,
        subject=subject,
        date=datetime(2026, 11, 17, 9, 30, tzinfo=UTC),
        text=text,
    )


def _out_for_delivery(number: str) -> MailMessage:
    """Return a minimal CTT out-for-delivery e-mail about ``number``."""
    return _message(
        "Olá Alex Doe,\n"
        f"O seu objeto {number} está em distribuição e será entregue hoje"
        " entre as 14:00 e as 18:00.\n",
        subject=f"O seu objeto {number} está em distribuição",
    )


# One CTT notice written the ways real layouts vary.
LAYOUTS = {
    "sentence": (
        "O seu objeto RR123456785PT está em distribuição e será entregue hoje"
        " entre as 14:00 e as 18:00.\n"
    ),
    "rows": (
        "Número do objeto: RR123456785PT\n"
        "Estado: Em distribuição\n"
        "Janela horária: 14:00 - 18:00\n"
    ),
    "stacked": (
        "Número do objeto\nRR123456785PT\n\n"
        "Estado\nEm distribuição\n\n"
        "Janela horária\n14h00 - 18h00\n"
    ),
    "spaced": (
        "  NÚMERO DO OBJETO :   RR 1234 5678 5 PT\n\n"
        "  ESTADO :  EM DISTRIBUIÇÃO\n\n"
        "  JANELA HORÁRIA :  das 14h às 18h\n"
    ),
}

# Return-to-sender notices: parser, sender, subject and body.
RETURNS = {
    "pt": (
        "ctt",
        "notificacoes@ctt.pt",
        "Objeto devolvido ao remetente",
        "Olá Alex Doe,\nO seu objeto RR482915732PT foi devolvido ao remetente.\n",
    ),
    "en": (
        "ups",
        "pkginfo@ups.com",
        "UPS Update: Package Returned to Sender",
        "Hello Alex Doe,\n"
        "Your package 1ZX4V2690345127862 is being returned to the sender.\n",
    ),
    "es": (
        "seur",
        "notificaciones@seur.com",
        "Tu envío ha sido devuelto",
        "Hola Alex Doe,\nTu envío 0628174539 ha sido devuelto al remitente.\n",
    ),
    "de": (
        "dhl",
        "noreply@dhl.de",
        "Ihre Sendung wurde an den Absender zurückgesendet",
        "Hallo Alex Doe,\n"
        "Ihre DHL Sendung 00340434618273591202 wurde an den Absender"
        " zurückgesendet.\n",
    ),
}


def test_carrier_parsers() -> None:
    """Each carrier with a dedicated parser has its own id."""
    assert {
        "ctt",
        "ctt_expresso",
        "dpd",
        "gls",
        "seur",
        "ups",
        "dhl",
        "correos_express",
        "mrw",
        "nacex",
        "paack",
        "inpost",
        "vinted_go",
        "fedex",
    } == CARRIER_PARSERS


def test_carrier_parsers_match_the_sender_hints() -> None:
    """The handled ids are the carrier hints of the sender allow-list."""
    hints = {info.parser for info in senders.KNOWN_SENDERS.values()}
    assert hints >= CARRIER_PARSERS


def test_unknown_carrier_returns_none() -> None:
    """A parser id that isn't a carrier's gives no result."""
    message = _out_for_delivery("RR123456785PT")
    assert parse_carrier(message, CTT, LISBON, "postnl") is None


@pytest.mark.parametrize("layout", LAYOUTS)
def test_layouts_read_the_same(layout: str) -> None:
    """Sentences, label rows, stacked labels and odd spacing give one result."""
    message = _message(f"Olá Alex Doe,\n{LAYOUTS[layout]}")
    result = parse_carrier(message, CTT, LISBON, "ctt")
    assert result is not None
    assert result.kind is MailKind.OUT_FOR_DELIVERY
    assert result.confidence >= CLEAR
    [shipment] = result.shipments
    assert shipment.tracking_number == "RR123456785PT"
    assert shipment.eta == eta("2026-11-17", "14:00", "18:00")


@pytest.mark.parametrize("language", RETURNS)
def test_return_to_sender(language: str) -> None:
    """A parcel on its way back to the shop is a return, in each language."""
    parser, sender, subject, text = RETURNS[language]
    message = _message(text, subject, sender=sender, sender_name=parser.upper())
    domain = sender.partition("@")[2]
    verdict = SenderVerdict(domain=domain, authenticated=True, known=True)
    result = parse_carrier(message, verdict, LISBON, parser)
    assert result is not None
    assert result.kind is MailKind.RETURN
    assert result.language == language
    assert result.confidence >= CLEAR
    [shipment] = result.shipments
    assert shipment.carrier == parser
    assert shipment.tracking_number is not None
    assert shipment.tracking_number in text


def test_pickup_deadline_warning_is_not_a_return() -> None:
    """A pickup notice saying when the parcel goes back stays a pickup notice."""
    message = _message(
        "Hallo Alex Doe,\n"
        "Ihre DHL Sendung 00340434618273591202 liegt in der Packstation 123"
        " zur Abholung bereit.\n"
        "Bitte holen Sie die Sendung bis zum 24.11.2026 ab, andernfalls wird sie"
        " an den Absender zurückgesendet.\n",
        "Ihre Sendung liegt zur Abholung bereit",
        sender="noreply@dhl.de",
        sender_name="DHL",
    )
    verdict = SenderVerdict(domain="dhl.de", authenticated=True, known=True)
    result = parse_carrier(message, verdict, LISBON, "dhl")
    assert result is not None
    assert result.kind is MailKind.READY_FOR_PICKUP
    [shipment] = result.shipments
    assert shipment.pickup_point == "Packstation 123"
    assert shipment.eta == eta("2026-11-17", until="2026-11-24")


def _ctt_point(point: str) -> tuple[str, str, str, str, str]:
    """Return a CTT pickup sentence naming ``point``, then another sentence."""
    return (
        "ctt",
        "notificacoes@ctt.pt",
        "O seu objeto aguarda levantamento",
        f"Olá Alex Doe,\nO seu objeto RR123456785PT foi depositado no {point}."
        " Levante-o até 24-11-2026.\n",
        point,
    )


# Pickup sentences whose point is followed by another sentence: the parser,
# sender, subject, body and the point.
POINT_SENTENCES = {
    "inpost": (
        "inpost",
        "notificacoes@inpost.pt",
        "A sua encomenda está pronta para levantamento",
        "Olá Alex Doe,\nA sua encomenda 620417393912 está disponível no Locker"
        " PT-LIS-01. Levante-a no prazo de 3 dias.\n",
        "Locker PT-LIS-01",
    ),
    "ctt": (
        "ctt",
        "notificacoes@ctt.pt",
        "O seu objeto aguarda levantamento",
        "Olá Alex Doe,\nO seu objeto RR123456785PT aguarda levantamento no Cacifo"
        " CTT Av. Liberdade. Leve o código que lhe enviámos.\n",
        "Cacifo CTT Av. Liberdade",
    ),
    "dhl": (
        "dhl",
        "noreply@dhl.de",
        "Ihre Sendung liegt zur Abholung bereit",
        "Hallo Alex Doe,\nIhre DHL Sendung 00340434618273591202 liegt in der"
        " Packstation 123. Bitte holen Sie sie innerhalb von 7 Tagen ab.\n",
        "Packstation 123",
    ),
    "ctt-long-word": _ctt_point("Cacifo CTT Saldanha"),
    "ctt-short-word": _ctt_point("Cacifo CTT Sol"),
    "ctt-four-letters": _ctt_point("Loja CTT Lapa"),
    "ctt-company": _ctt_point("Ponto CTT Papelaria Exemplo, Lda"),
    "ctt-company-initials": _ctt_point("Ponto CTT Quiosque Exemplo, S.A"),
    "ctt-title": _ctt_point("Ponto CTT Farmácia Dr. Sá"),
    "ctt-initial": _ctt_point("Ponto CTT Papelaria J. Silva"),
    "ctt-initials": _ctt_point("Ponto CTT Quiosque C.C. Colombo"),
    "ctt-street": _ctt_point("Loja CTT R. Augusta"),
    "ctt-saint": _ctt_point("Ponto CTT Quiosque Sta. Apolónia"),
    "ctt-number": _ctt_point("Cacifo CTT 1234"),
    "ctt-block-letter": _ctt_point("Cacifo CTT Bloco B"),
    "ctt-building-letter": _ctt_point("Ponto CTT Edifício A"),
}


@pytest.mark.parametrize("case", POINT_SENTENCES)
def test_pickup_point_ends_with_its_sentence(case: str) -> None:
    """A point named in a sentence stops where the sentence ends.

    A full stop ends the name, except after an initial or an abbreviation that
    a name goes on after, as in "Av. Liberdade".
    """
    parser, sender, subject, text, point = POINT_SENTENCES[case]
    message = _message(text, subject, sender=sender, sender_name=parser.upper())
    domain = sender.partition("@")[2]
    verdict = SenderVerdict(domain=domain, authenticated=True, known=True)
    result = parse_carrier(message, verdict, LISBON, parser)
    assert result is not None
    assert result.kind is MailKind.READY_FOR_PICKUP
    [shipment] = result.shipments
    assert shipment.pickup_point == point


def test_number_with_a_bad_check_digit_is_not_used() -> None:
    """A number that fails its check digit isn't reported or trusted."""
    result = parse_carrier(_out_for_delivery("RR123456784PT"), CTT, LISBON, "ctt")
    assert result is not None
    assert [shipment.tracking_number for shipment in result.shipments] == [None]
    assert result.shipments[0].tracking_url is None
    assert result.notes == ("no_tracking_number",)
    assert result.confidence < CONFIDENCE_APPLY


def test_long_run_without_an_address_is_read_once() -> None:
    """A long run with no "@" doesn't slow a carrier e-mail down.

    Blanking e-mail addresses used to read such a run again from each of its
    characters: about 7 seconds for 60,000 characters.
    """
    message = _out_for_delivery("RR123456785PT")
    message = replace(message, text=message.text + "26-" * 20_000)
    start = perf_counter()
    result = parse_carrier(message, CTT, LISBON, "ctt")
    assert perf_counter() - start < 2
    assert result is not None
    assert result.kind is MailKind.OUT_FOR_DELIVERY
    assert [shipment.tracking_number for shipment in result.shipments] == [
        "RR123456785PT"
    ]


def test_code_only_email_gives_the_code_of_its_parcel() -> None:
    """A PIN for a parcel the e-mail names is a CODE result.

    The PIN isn't read as a second tracking number, and a PIN for no parcel
    gives no result.
    """
    sender = "notificaciones@seur.com"
    verdict = SenderVerdict(domain="seur.com", authenticated=True, known=True)
    message = _message(
        "Hola Alex Doe,\n"
        "El código de entrega de tu envío es 73915204.\n"
        "Número de envío: 0628174539\n",
        "Tu código de entrega",
        sender=sender,
        sender_name="SEUR",
    )
    result = parse_carrier(message, verdict, LISBON, "seur")
    assert result is not None
    assert result.kind is MailKind.CODE
    assert result.confidence >= CONFIDENCE_APPLY
    [shipment] = result.shipments
    assert shipment.kind is MailKind.CODE
    assert shipment.tracking_number == "0628174539"
    assert shipment.pickup_code == "73915204"
    assert shipment.eta is None
    no_parcel = _message(
        "Hola Alex Doe,\nTu código de entrega: 73915204\n",
        "Tu código de entrega",
        sender=sender,
        sender_name="SEUR",
    )
    assert parse_carrier(no_parcel, verdict, LISBON, "seur") is None


# Status e-mails with a code and an order number: the lines after the status
# line, the order numbers and the code they must give.
ORDER_AND_CODE = {
    "code_is_no_order": (
        "está em distribuição e será entregue hoje.\nCódigo de entrega do pedido: 4821\n",
        (),
        "4821",
    ),
    "order_is_no_code": (
        "está disponível para levantamento no Cacifo CTT Saldanha.\n"
        "Pedido n.º 48213\nCódigo de levantamento: 48213\n",
        ("48213",),
        None,
    ),
}


@pytest.mark.parametrize("case", ORDER_AND_CODE)
def test_code_and_order_number_stay_apart(case: str) -> None:
    """A code is never an order number, and an order number never a code."""
    lines, orders, code = ORDER_AND_CODE[case]
    message = _message(f"Olá Alex Doe,\nO seu objeto RR123456785PT {lines}")
    result = parse_carrier(message, CTT, LISBON, "ctt")
    assert result is not None
    assert result.order_numbers == orders
    [shipment] = result.shipments
    assert shipment.tracking_number == "RR123456785PT"
    assert shipment.order_numbers == orders
    assert shipment.pickup_code == code


def test_tracking_number_is_never_the_code() -> None:
    """A tracking number written after a code label isn't the code."""
    rows = "Olá Alex Doe,\nN.º do objeto: 7391520486\nEstado: Em distribuição\n"
    for line, code in (
        ("Código de entrega: 7391520486\n", None),
        ("Código de entrega do objeto 7391520486: 4821\n", "4821"),
    ):
        result = parse_carrier(_message(rows + line), CTT, LISBON, "ctt")
        assert result is not None
        assert result.kind is MailKind.OUT_FOR_DELIVERY
        [shipment] = result.shipments
        assert shipment.tracking_number == "7391520486"
        assert shipment.pickup_code == code


def test_failure_returns_none_and_logs_no_email_content(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A parser error gives None and logs no e-mail text."""
    message = _out_for_delivery("RR123456785PT")

    def fail(*args: object) -> ParseResult:
        raise ValueError(message.text)

    monkeypatch.setattr(carriers, "parse_with_spec", fail)
    with caplog.at_level(logging.DEBUG):
        assert parse_carrier(message, CTT, LISBON, "ctt") is None
    assert "ValueError" in caplog.text
    assert "Alex Doe" not in caplog.text
    assert "distribuição" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_every_fixture_has_expectations() -> None:
    """Each carrier fixture is checked by one of the carrier test modules."""
    # Imported here: those modules import this one.
    from . import (
        test_carriers_es,
        test_carriers_fedex,
        test_carriers_intl,
        test_carriers_lockers,
        test_carriers_pt,
    )

    modules = (
        test_carriers_pt,
        test_carriers_es,
        test_carriers_intl,
        test_carriers_lockers,
        test_carriers_fedex,
    )
    names = [case.name for module in modules for case in module.CASES]
    names += [name for module in modules for name in module.NEGATIVE]
    assert len(names) == len(set(names))
    assert set(names) == {path.stem for path in FIXTURES.glob("*.eml")}
