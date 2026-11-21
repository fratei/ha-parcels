"""Tests for the mapping between Parcels' carriers and Parcel's codes."""

from __future__ import annotations

import pytest

from custom_components.parcels.const import CARRIER_NAMES
from custom_components.parcels.dedup import carrier_family
from custom_components.parcels.parcelapp.carriers import (
    UNUSABLE,
    amazon_code,
    amazon_store,
    normalize_code,
    parcel_code,
    parcels_carrier,
)


@pytest.mark.parametrize(
    ("carrier", "country", "learned", "expected"),
    [
        ("ctt", "PT", {}, "ctt"),
        ("ctt_expresso", "PT", {}, "ctt"),
        ("ctt_expresso", "pt", {}, "ctt"),
        ("ctt_expresso", "ES", {}, "tourline"),
        ("ctt_expresso", None, {}, "tourline"),
        ("chronopost", "PT", {}, "chronop"),
        ("chronopost", "FR", {}, "chrono"),
        ("correos_express", "PT", {}, "chrexp"),
        ("ups", None, {}, "ups"),
        ("paack", "PT", {}, "paack"),
        # Several codes each: only what the user's own deliveries show.
        ("gls", "PT", {}, None),
        ("dpd", "PT", {}, None),
        ("dhl", "PT", {}, None),
        ("inpost", "PT", {}, None),
        ("gls", "PT", {"gls": "glsit"}, "glsit"),
        ("ctt", "PT", {"ctt": "tourline"}, "tourline"),
        ("ups", "PT", {"gls": "glsit"}, "ups"),
        ("amazon", "PT", {}, None),
        ("other", "PT", {}, None),
        (None, "PT", {"": "ups"}, None),
    ],
)
def test_parcel_code(
    carrier: str | None, country: str | None, learned: dict[str, str], expected: str
) -> None:
    """A learned code comes first, then the country's, then the usual one."""
    assert parcel_code(carrier, country, learned) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("ctt", "ctt"),
        (" CTT ", "ctt"),
        ("tourline", "ctt_expresso"),
        ("chronop", "chronopost"),
        ("chrono", "chronopost"),
        ("chrexp", "correos_express"),
        ("asmred", "gls"),
        ("glsit", "gls"),
        ("dpdpt", "dpd"),
        ("dpdgpcode", "dpd"),
        ("inpespcode", "inpost"),
        ("inpostit", "inpost"),
        # Amazon's own codes follow orders, not a carrier.
        ("amzles", None),
        ("amshipuk", None),
        ("swiship", None),
        ("tntp", "postnl"),
        ("tntpitp", "postnl"),
        ("tnt", "tnt"),
        ("dhlparcel", "dhl"),
        ("paack", "paack"),
        ("celeritas", None),
        ("", None),
        (None, None),
        ("dpd-pt", None),
        ("dpdé", None),
        ("dpd" + "x" * 30, None),
    ],
)
def test_parcels_carrier(code: object, expected: str | None) -> None:
    """Codes map back to Parcels' carriers, by name or by family prefix."""
    assert parcels_carrier(code) == expected


@pytest.mark.parametrize(
    ("code", "number", "expected"),
    [
        ("amshipuk", "TBA123456789012", "amazon"),
        ("swiship", "tba 123456789012", "amazon"),
        ("amzles", "TBA123456789012", "amazon"),
        ("amshipuk", "QA1234567890", None),
        ("swiship", "1Z999AA10123456784", None),
        ("amzles", "17112345671234567", None),
        ("ctt", "TBA123456789012", "ctt"),
    ],
)
def test_amazon_logistics_needs_its_number(
    code: str, number: str, expected: str | None
) -> None:
    """Amazon's codes stand for Amazon Logistics only with one of its numbers."""
    assert parcels_carrier(code, number) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("amzles", True),
        (" AMZLUS ", True),
        ("amshipfr", True),
        ("swiship", True),
        ("amz", False),
        ("ctt", False),
        ("", False),
        (None, False),
    ],
)
def test_amazon_code(code: object, expected: bool) -> None:
    """Amazon's own codes: its stores, Amazon Shipping and its sellers' site."""
    assert amazon_code(code) is expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("amzles", True),
        ("AMZLUS", True),
        ("amshipfr", False),
        ("swiship", False),
        ("ctt", False),
        (None, False),
    ],
)
def test_amazon_store(code: object, expected: bool) -> None:
    """Only the codes of Amazon's stores follow Amazon's own orders."""
    assert amazon_store(code) is expected


def test_normalize_code() -> None:
    """Codes are short lowercase ASCII words."""
    assert normalize_code(" UPS ") == "ups"
    assert normalize_code("a" * 32) == "a" * 32
    assert normalize_code("a" * 33) is None
    assert normalize_code("ups\n") == "ups"
    assert normalize_code("u ps") is None


@pytest.mark.parametrize("country", ["PT", "ES", None])
def test_codes_round_trip(country: str | None) -> None:
    """Every code Parcels adds under reads back as the same carrier family."""
    for carrier in CARRIER_NAMES:
        if (code := parcel_code(carrier, country, {})) is None:
            continue
        assert carrier_family(parcels_carrier(code)) == carrier_family(carrier)
        assert code not in UNUSABLE
