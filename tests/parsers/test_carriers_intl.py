"""Tests for the DPD, GLS, UPS and DHL e-mail parsers."""

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
        "dpd_predict_pt",
        "dpd",
        MailKind.OUT_FOR_DELIVERY,
        "05346718290412",
        eta=eta("2026-11-17", "13:00", "14:00"),
        merchant="Zalando",
    ),
    # Its only news is the delivery PIN of a parcel it names.
    Case(
        "dpd_delivery_code_pt",
        "dpd",
        MailKind.CODE,
        "09381726450517",
        pickup_code="4821",
    ),
    Case(
        "dpd_predict_en",
        "dpd",
        MailKind.IN_TRANSIT,
        "15502468013579",
        eta=eta("2026-11-18", "10:24", "11:24"),
        merchant="ASOS",
    ),
    Case(
        "dpd_delivered_de",
        "dpd",
        MailKind.DELIVERED,
        "01906123456789",
        event="2026-11-17 13:24",
        merchant="Otto",
    ),
    Case(
        "dpd_pickup_ready_fr",
        "dpd",
        MailKind.READY_FOR_PICKUP,
        "25018364729105",
        eta=eta("2026-11-17", until="2026-11-27"),
        pickup_point="Relais Pickup Tabac Presse Exemple, 1 Rue Exemple, 75011 Paris",
        pickup_code="735915",
        merchant="Fnac",
    ),
    Case(
        "dpd_predict_nl",
        "dpd",
        MailKind.OUT_FOR_DELIVERY,
        "05743829165047",
        eta=eta("2026-11-17", "15:15", "16:15"),
        merchant="Coolblue",
    ),
    Case(
        "gls_flex_de",
        "gls",
        MailKind.OUT_FOR_DELIVERY,
        "620417392859",
        eta=eta("2026-11-17", "11:10", "13:10"),
        merchant="Tchibo",
    ),
    Case(
        "gls_tomorrow_it",
        "gls",
        MailKind.IN_TRANSIT,
        "620417393016",
        eta=eta("2026-11-18", "09:00", "12:00"),
        merchant="Yoox",
    ),
    Case(
        "gls_parcelshop_nl",
        "gls",
        MailKind.READY_FOR_PICKUP,
        "620417393191",
        eta=eta("2026-11-17", until="2026-11-26"),
        pickup_point=(
            "ParcelShop Tabakszaak Voorbeeld, Voorbeeldstraat 1, 1011 AB Amsterdam"
        ),
        merchant="Wehkamp",
    ),
    Case(
        "gls_delivered_en",
        "gls",
        MailKind.DELIVERED,
        "620417393276",
        event="2026-11-17 12:31",
        merchant="Boots",
    ),
    Case(
        "gls_out_for_delivery_es",
        "gls",
        MailKind.OUT_FOR_DELIVERY,
        "620417393351",
        eta=eta("2026-11-17", "16:00", "18:00"),
        merchant="Pull&Bear",
    ),
    Case(
        "gls_flex_pt",
        "gls",
        MailKind.OUT_FOR_DELIVERY,
        "620417393436",
        eta=eta("2026-11-17", "10:00", "12:00"),
        merchant="Wook",
    ),
    Case(
        "ups_scheduled_today_en",
        "ups",
        MailKind.OUT_FOR_DELIVERY,
        "1ZX4V2690345127862",
        eta=eta("2026-11-17", "14:00", "18:00"),
        merchant="Apple",
    ),
    Case(
        "ups_delivered_pt",
        "ups",
        MailKind.DELIVERED,
        "1ZE7F1426803941570",
        event="2026-11-17 11:58",
        merchant="Nike",
    ),
    Case(
        "ups_access_point_fr",
        "ups",
        MailKind.READY_FOR_PICKUP,
        "1Z9W8R371125836041",
        eta=eta("2026-11-17", until="2026-11-24"),
        pickup_point="UPS Access Point Librairie Exemple, 1 Rue Exemple, 69001 Lyon",
        merchant="Sephora",
    ),
    Case(
        "ups_delayed_de",
        "ups",
        MailKind.DELAYED,
        "1ZA5Y0610477203153",
        eta=eta("2026-11-19"),
        merchant="Zalando",
    ),
    Case(
        "ups_out_for_delivery_es",
        "ups",
        MailKind.OUT_FOR_DELIVERY,
        "1Z6R3E520483719262",
        eta=eta("2026-11-17", "12:00", "15:30"),
        merchant="LEGO",
    ),
    Case(
        "dhl_today_de",
        "dhl",
        MailKind.OUT_FOR_DELIVERY,
        "00340434618273591202",
        eta=eta("2026-11-17", "10:30", "13:30"),
        merchant="Zalando",
    ),
    Case(
        "dhl_packstation_de",
        "dhl",
        MailKind.READY_FOR_PICKUP,
        "JJD000390007283946521",
        eta=eta("2026-11-17", until="2026-11-24"),
        pickup_point="Packstation 123, Musterstraße 1, 10115 Berlin",
        pickup_code="519384",
        merchant="Thalia",
    ),
    # Offering delivery to a Service Point doesn't make the parcel wait there.
    Case(
        "dhl_express_en",
        "dhl",
        MailKind.IN_TRANSIT,
        "4716382591",
        eta=eta("2026-11-18", "09:00", "12:00"),
        merchant="Apple",
    ),
    Case(
        "dhl_window_nl",
        "dhl",
        MailKind.OUT_FOR_DELIVERY,
        "JVGL0626380815294716",
        eta=eta("2026-11-17", "17:30", "20:30"),
        merchant="HEMA",
    ),
    Case(
        "dhl_express_delivered_it",
        "dhl",
        MailKind.DELIVERED,
        "5829173641",
        event="2026-11-17 10:42",
        merchant="Yoox",
    ),
    Case(
        "dhl_express_pt",
        "dhl",
        MailKind.OUT_FOR_DELIVERY,
        "5830164723",
        eta=eta("2026-11-17", "09:00", "13:00"),
        merchant="Farfetch",
    ),
    Case(
        "dhl_servicepoint_es",
        "dhl",
        MailKind.READY_FOR_PICKUP,
        "6402951833",
        eta=eta("2026-11-17", until="2026-11-24"),
        pickup_point="DHL ServicePoint Estanco Ejemplo, Calle Ejemplo 1, 28001 Madrid",
        merchant="Massimo Dutti",
    ),
)
NEGATIVE = (
    "dpd_marketing_en",
    "gls_marketing_it",
    "ups_marketing_en",
    "dhl_marketing_de",
)


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
