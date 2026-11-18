"""Tests for the CTT and CTT Expresso e-mail parsers."""

from __future__ import annotations

import pytest

from custom_components.parcels.const import MailKind
from custom_components.parcels.parsers.carriers import parse_carrier

from .test_carriers_common import (
    Case,
    Loader,
    VerdictFor,
    check_case,
    check_negative,
    eta,
    zone,
)

CASES = (
    Case(
        "ctt_in_transit_pt",
        "ctt",
        MailKind.IN_TRANSIT,
        "RR482915732PT",
        eta=eta("2026-11-19"),
        merchant="Worten",
    ),
    Case(
        "ctt_out_for_delivery_pt",
        "ctt",
        MailKind.OUT_FOR_DELIVERY,
        "RR617304824PT",
        eta=eta("2026-11-17", "13:00", "17:00"),
        merchant="Fnac Portugal",
    ),
    # A delivery PIN in a status e-mail: the status stays, the PIN is kept.
    Case(
        "ctt_out_for_delivery_code_pt",
        "ctt",
        MailKind.OUT_FOR_DELIVERY,
        "RR739204180PT",
        eta=eta("2026-11-19", "09:00", "13:00"),
        pickup_code="5937",
    ),
    Case(
        "ctt_delivered_pt",
        "ctt",
        MailKind.DELIVERED,
        "RL273849102PT",
        event="2026-11-17 11:42",
    ),
    Case(
        "ctt_attempted_pt",
        "ctt",
        MailKind.ATTEMPTED,
        "RR905172642PT",
        event="2026-11-17 10:05",
        pickup_point="Loja CTT Avenidas Novas, Rua Exemplo 1, 1050-001 Lisboa",
    ),
    Case("ctt_customs_pt", "ctt", MailKind.CUSTOMS, "LZ731940285CN"),
    Case(
        "ctt_locker_ready_pt",
        "ctt",
        MailKind.READY_FOR_PICKUP,
        "RH358201962PT",
        eta=eta("2026-11-17", until="2026-11-24"),
        pickup_point="Cacifo CTT Saldanha, Avenida Exemplo 1, 1050-001 Lisboa",
        pickup_code="482913",
    ),
    Case(
        "ctt_expresso_out_for_delivery_pt",
        "ctt_expresso",
        MailKind.OUT_FOR_DELIVERY,
        "EA529183745PT",
        eta=eta("2026-11-17", "10:00", "13:00"),
        merchant="Decathlon",
    ),
    Case(
        "ctt_expresso_delivered_pt",
        "ctt_expresso",
        MailKind.DELIVERED,
        "EA529184065PT",
        event="2026-11-16 16:05",
    ),
    # Vinted names the carrier of a parcel it doesn't carry itself.
    Case(
        "vinted_ctt_shipped_pt",
        "vinted_go",
        MailKind.SHIPPED,
        "RR146820353PT",
        carrier="ctt",
        merchant="Vinted",
    ),
)
NEGATIVE = ("ctt_marketing_pt", "ctt_expresso_marketing_pt")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_parses_email(case: Case, load_eml: Loader, verdict_for: VerdictFor) -> None:
    """Each e-mail gives its kind, number, dates, pickup data and merchant."""
    check_case(case, load_eml, verdict_for)


@pytest.mark.parametrize("name", NEGATIVE)
def test_ignores_email_without_parcel_news(
    name: str, load_eml: Loader, verdict_for: VerdictFor
) -> None:
    """Newsletters and promotions give no result."""
    check_negative(name, load_eml, verdict_for)


def test_ctt_email_about_an_expresso_parcel(
    load_eml: Loader, verdict_for: VerdictFor
) -> None:
    """The CTT parser reports CTT Expresso when the e-mail names it."""
    name = "ctt_expresso_out_for_delivery_pt"
    message = load_eml(f"carriers/{name}.eml")
    result = parse_carrier(message, verdict_for(message), zone(name), "ctt")
    assert result is not None
    assert result.parser == "ctt"
    assert [shipment.carrier for shipment in result.shipments] == ["ctt_expresso"]
