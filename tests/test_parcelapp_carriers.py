"""Tests for the mapping between Parcels' carriers and Parcel's codes."""

from __future__ import annotations

import pytest

from custom_components.parcels.const import CARRIER_NAMES
from custom_components.parcels.dedup import carrier_family
from custom_components.parcels.parcelapp.carriers import (
    UNUSABLE,
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
        ("amzles", "amazon"),
        ("amship", "amazon"),
        ("swiship", "amazon"),
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
