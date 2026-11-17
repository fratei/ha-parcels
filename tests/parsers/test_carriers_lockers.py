"""Tests for the InPost and Vinted Go locker e-mail parsers."""

from __future__ import annotations

import pytest

from custom_components.parcels.const import MailKind

from .test_carriers_common import (
    Case,
    Loader,
    VerdictFor,
    check_case,
    check_negative,
    eta,
)

CASES = (
    Case(
        "inpost_ready_pt",
        "inpost",
        MailKind.READY_FOR_PICKUP,
        "602937500284163957201848",
        eta=eta("2026-11-17", until="2026-11-20"),
        pickup_point="Cacifo InPost LIS01M, Rua Exemplo 1, 1000-001 Lisboa",
        pickup_code="539128",
        merchant="Shein",
    ),
    Case(
        "inpost_ready_it",
        "inpost",
        MailKind.READY_FOR_PICKUP,
        "602937500284163957201923",
        eta=eta("2026-11-17", until="2026-11-21"),
        pickup_point="Locker InPost MIL123M, Via Esempio 1, 20121 Milano",
        pickup_code="284716",
        merchant="Zalando",
    ),
    Case(
        "inpost_ready_es",
        "inpost",
        MailKind.READY_FOR_PICKUP,
        "602937500284163957202142",
        eta=eta("2026-11-17", until="2026-11-20"),
        pickup_point="Locker InPost MAD05M, Calle Ejemplo 1, 28001 Madrid",
        pickup_code="736152",
        merchant="Primor",
    ),
    Case(
        "inpost_collected_en",
        "inpost",
        MailKind.DELIVERED,
        "602937500284163957202067",
        event="2026-11-17 18:22",
        merchant="ASOS",
    ),
    Case(
        "vinted_go_ready_fr",
        "vinted_go",
        MailKind.READY_FOR_PICKUP,
        "1704829163057281",
        eta=eta("2026-11-17", until="2026-11-24"),
        pickup_point="Casier Vinted Go Paris Exemple, 1 Rue Exemple, 75011 Paris",
        pickup_code="718293",
        merchant="Vinted",
    ),
    Case(
        "vinted_go_ready_nl",
        "vinted_go",
        MailKind.READY_FOR_PICKUP,
        "1704829163057299",
        eta=eta("2026-11-17", until="2026-11-24"),
        pickup_point=(
            "Locker Vinted Go Amsterdam Voorbeeld, Voorbeeldstraat 1, 1011 AB Amsterdam"
        ),
        pickup_code="604127",
        merchant="Vinted",
    ),
    Case(
        "vinted_go_ready_es",
        "vinted_go",
        MailKind.READY_FOR_PICKUP,
        "1704829163057306",
        eta=eta("2026-11-17", until="2026-11-23"),
        pickup_point="Locker Vinted Go Madrid Ejemplo, Calle Ejemplo 1, 28001 Madrid",
        pickup_code="539016",
        merchant="Vinted",
    ),
    Case(
        "vinted_go_collected_en",
        "vinted_go",
        MailKind.DELIVERED,
        "1704829163057314",
        event="2026-11-17 16:58",
        merchant="Vinted",
    ),
)
# The seller drop-off e-mail is about a parcel the user sends, not receives.
NEGATIVE = (
    "inpost_marketing_pt",
    "vinted_go_marketing_it",
    "vinted_go_seller_dropoff_en",
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_parses_email(case: Case, load_eml: Loader, verdict_for: VerdictFor) -> None:
    """Each e-mail gives its kind, number, dates, pickup point, code and merchant."""
    check_case(case, load_eml, verdict_for)


@pytest.mark.parametrize("name", NEGATIVE)
def test_ignores_email_without_parcel_news(
    name: str, load_eml: Loader, verdict_for: VerdictFor
) -> None:
    """Promotions and e-mails about parcels the user sends give no result."""
    check_negative(name, load_eml, verdict_for)
