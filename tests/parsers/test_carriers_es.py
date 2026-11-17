"""Tests for the SEUR, Correos Express, MRW, NACEX and Paack e-mail parsers."""

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
