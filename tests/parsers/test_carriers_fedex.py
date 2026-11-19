"""Tests for the FedEx e-mail parser.

FedEx and FedEx Delivery Manager send "scheduled delivery" notices with a
date and often a window, "on FedEx vehicle for delivery", "delivered" and
"new delivery date" notices. Numbers are 12-digit Express or Ground codes.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from custom_components.parcels.const import MailKind
from custom_components.parcels.parsers import parse_message, senders
from custom_components.parcels.parsers.base import MailMessage, SenderVerdict
from custom_components.parcels.parsers.carriers import parse_carrier
from custom_components.parcels.parsers.tracking import tracking_url

from .test_carriers_common import (
    LISBON,
    Case,
    Loader,
    VerdictFor,
    check_result,
    eta,
    zone,
)

FEDEX = SenderVerdict(domain="fedex.com", authenticated=True, known=True)
NUMBER = "874449900283"

CASES = (
    Case(
        "fedex_scheduled_en",
        "fedex",
        MailKind.IN_TRANSIT,
        "874449900283",
        eta=eta("2026-11-19", "10:30", "14:30"),
        merchant="Garmin",
    ),
    Case(
        "fedex_scheduled_pt",
        "fedex",
        MailKind.IN_TRANSIT,
        "521680287562",
        eta=eta("2026-11-19", None, "20:00"),
        merchant="Zara",
    ),
    Case(
        "fedex_scheduled_es",
        "fedex",
        MailKind.IN_TRANSIT,
        "231171978263",
        eta=eta("2026-11-19", "10:00", "14:00"),
        merchant="Mango",
    ),
    Case(
        "fedex_scheduled_de",
        "fedex",
        MailKind.IN_TRANSIT,
        "589513701214",
        eta=eta("2026-11-19", None, "12:00"),
        merchant="Tchibo",
    ),
    Case(
        "fedex_scheduled_fr",
        "fedex",
        MailKind.IN_TRANSIT,
        "306307040908",
        eta=eta("2026-11-19", "10:00", "14:00"),
        merchant="Decathlon",
    ),
    Case(
        "fedex_scheduled_it",
        "fedex",
        MailKind.IN_TRANSIT,
        "775405566729",
        eta=eta("2026-11-19", "10:00", "14:00"),
        merchant="Feltrinelli",
    ),
    Case(
        "fedex_scheduled_nl",
        "fedex",
        MailKind.IN_TRANSIT,
        "833879637036",
        eta=eta("2026-11-19", "10:00", "14:00"),
        merchant="Coolblue",
    ),
    Case(
        "fedex_delivered_en",
        "fedex",
        MailKind.DELIVERED,
        "428499337370",
        event="2026-11-17 11:58",
        merchant="Apple",
    ),
    Case(
        "fedex_new_date_en",
        "fedex",
        MailKind.DELAYED,
        "635462817030",
        eta=eta("2026-11-20"),
        merchant="Lego",
    ),
    Case(
        "fedex_out_for_delivery_en",
        "fedex",
        MailKind.OUT_FOR_DELIVERY,
        "572295331440",
        eta=eta("2026-11-19", "13:00", "17:00"),
        merchant="Dyson",
    ),
)
NEGATIVE: tuple[str, ...] = ()


def _load(
    name: str, load_eml: Loader, verdict_for: VerdictFor
) -> tuple[MailMessage, SenderVerdict]:
    """Load a fixture and check that it comes from a verified FedEx sender."""
    message = load_eml(f"carriers/{name}.eml")
    verdict = verdict_for(message)
    assert verdict.verified
    info = senders.lookup(message.sender_domain)
    assert info is not None
    assert info.carrier == "fedex"
    return message, verdict


def _fedex(text: str, subject: str) -> MailMessage:
    """Return a FedEx e-mail with ``text`` as its body."""
    return MailMessage(
        message_id="<20261117093000.cd34@fedex.com>",
        provider_id="test",
        provider="google",
        mailbox="alex@example.com",
        sender="TrackingUpdates@fedex.com",
        sender_name="FedEx",
        subject=subject,
        date=datetime(2026, 11, 17, 9, 30, tzinfo=UTC),
        text=text,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_parses_email(case: Case, load_eml: Loader, verdict_for: VerdictFor) -> None:
    """Each e-mail gives its kind, number, delivery date, window and merchant."""
    message, verdict = _load(case.name, load_eml, verdict_for)
    check_result(case, message, verdict)


def test_dispatcher_uses_the_fedex_parser(
    load_eml: Loader, verdict_for: VerdictFor
) -> None:
    """FedEx e-mails reach the FedEx parser, not the generic one."""
    message, verdict = _load("fedex_scheduled_de", load_eml, verdict_for)
    result = parse_message(message, verdict, zone("fedex_scheduled_de"))
    assert result.parser == "fedex"
    [shipment] = result.shipments
    assert shipment.tracking_number == "589513701214"
    assert shipment.eta == eta("2026-11-19", None, "12:00")


@pytest.mark.parametrize(
    "line",
    [
        "Your package is on a FedEx vehicle for delivery.",
        "A sua encomenda está no veículo da FedEx para entrega.",
        "Tu paquete está en el vehículo de FedEx para su entrega.",
        "Ihre Sendung ist im FedEx Fahrzeug zur Zustellung.",
        "Votre colis est dans le véhicule FedEx pour livraison.",
        "Il tuo pacco è sul veicolo FedEx per la consegna.",
        "Je pakket zit in het FedEx-voertuig voor bezorging.",
    ],
)
def test_on_fedex_vehicle_is_out_for_delivery(line: str) -> None:
    """ "On FedEx vehicle for delivery", in each language, is out for delivery."""
    message = _fedex(f"Hi Alex.\n{line}\nTracking number {NUMBER}\n", "FedEx")
    result = parse_carrier(message, FEDEX, LISBON, "fedex")
    assert result is not None
    assert result.kind is MailKind.OUT_FOR_DELIVERY
    [shipment] = result.shipments
    assert shipment.tracking_number == NUMBER
    assert shipment.tracking_url == tracking_url("fedex", NUMBER)


@pytest.mark.parametrize(
    "subject",
    [
        "Your scheduled delivery date has changed",
        "The delivery date has changed",
        "Your delivery date has been updated",
        "New scheduled delivery date: Fri, Nov 20",
        "A data de entrega foi alterada",
        "La fecha de entrega ha cambiado",
        "Das Zustelldatum wurde geändert",
        "La date de livraison a changé",
        "La data di consegna è cambiata",
        "De bezorgdatum is gewijzigd",
    ],
)
def test_changed_delivery_date_is_delayed(subject: str) -> None:
    """A changed delivery date, in each language, is a delay with the new date."""
    message = _fedex(
        f"Hi Alex.\nScheduled delivery:\nFri, Nov 20\nTracking number {NUMBER}\n",
        f"FedEx Shipment {NUMBER}: {subject}",
    )
    result = parse_carrier(message, FEDEX, LISBON, "fedex")
    assert result is not None
    assert result.kind is MailKind.DELAYED
    [shipment] = result.shipments
    assert shipment.eta is not None
    assert shipment.eta.start == date(2026, 11, 20)
