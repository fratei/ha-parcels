"""Parcel's carrier codes, and Parcels' carriers they stand for.

Parcel lists its codes at
https://api.parcel.app/external/supported_carriers.json. A code marked
``"extra_required": 1`` only works with the recipient's postcode or e-mail;
the few marked otherwise need something Parcels can't give.

Parcels only adds a number under a code it is sure of. GLS, DPD, InPost and
DHL have several codes each, by country and service, so their codes are
learned from the deliveries the user added himself instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

# Parcels' carrier -> Parcel's code.
_CODES: Final[Mapping[str, str]] = {
    "bpost": "bpost",
    "brt": "bartol",
    "cainiao": "aliex",
    "chronopost": "chrono",
    "correos": "cor",
    "correos_express": "chrexp",
    "ctt": "ctt",
    "ctt_expresso": "tourline",
    "deutsche_post": "dp",
    "evri": "myher",
    "fedex": "fedex",
    "hermes": "hermes",
    "la_poste": "lp",
    "mondial_relay": "relay",
    "mrw": "mrw",
    "nacex": "nacex",
    "paack": "paack",
    "postnl": "tntp",
    "poste_italiane": "it",
    "royal_mail": "rm",
    "seur": "seur",
    "tnt": "tnt",
    "ups": "ups",
    "usps": "usps",
    "vinted_go": "vinted",
    "yunexpress": "yun",
}
# By Home Assistant's country. In Portugal CTT Expresso's numbers are CTT's
# (ctt.pt tracks them); "tourline" is CTT Express in Spain.
_CODES_IN: Final[Mapping[str, Mapping[str, str]]] = {
    "PT": {"chronopost": "chronop", "ctt_expresso": "ctt"},
}

# Codes that need the recipient's postcode ("extra_required": 1).
NEEDS_POSTCODE: Final = frozenset(
    {
        "allied",
        "arrowxl",
        "asmred",
        "bonshaw",
        "bpost",
        "colispcode",
        "cyclpcode",
        "dpdfrpcode",
        "dpdgpcode",
        "dpditpcode",
        "dpdpcode",
        "dx",
        "dynalogic",
        "fleetpcode",
        "gelpcode",
        "geodis",
        "glsnl",
        "hivedpcode",
        "inpespcode",
        "mrelpcode",
        "paack",
        "planzer",
        "relaypcode",
        "tntp",
        "transm",
        "trnkrpcode",
        "xdp",
        "yodel",
    }
)
# Codes that need more than a postcode ("extra_required" 2, 3 or 5).
UNUSABLE: Final = frozenset({"apple", "eshopw", "jde", "tntpitp"})

# A code shared by two carriers stands for the one it is named after.
_REVERSE: Final[Mapping[str, str]] = {
    **{
        code: carrier for codes in _CODES_IN.values() for carrier, code in codes.items()
    },
    **{code: carrier for carrier, code in _CODES.items()},
    "asmred": "gls",
    "dicom": "gls",
    "gso": "gls",
    "inpespcode": "inpost",
    "swiship": "amazon",
}
# Families of codes, by prefix; the longest prefix first.
_PREFIXES: Final[tuple[tuple[str, str], ...]] = (
    ("amship", "amazon"),
    ("inpost", "inpost"),
    ("amzl", "amazon"),
    ("tntp", "postnl"),
    ("dhl", "dhl"),
    ("dpd", "dpd"),
    ("gls", "gls"),
    ("tnt", "tnt"),
)


def normalize_code(code: object) -> str | None:
    """Return a carrier code as Parcel writes it, or None."""
    text = str(code or "").strip().lower()
    return text if text.isascii() and text.isalnum() and len(text) <= 32 else None


def parcels_carrier(code: object) -> str | None:
    """Return the Parcels carrier a Parcel code stands for, or None."""
    if (text := normalize_code(code)) is None:
        return None
    if (carrier := _REVERSE.get(text)) is not None:
        return carrier
    return next(
        (carrier for prefix, carrier in _PREFIXES if text.startswith(prefix)), None
    )


def parcel_code(
    carrier: str | None, country: str | None, learned: Mapping[str, str]
) -> str | None:
    """Return the Parcel code to add a carrier's number under, or None.

    A code learned from the user's own deliveries comes first.
    """
    if not carrier:
        return None
    if code := learned.get(carrier):
        return code
    return _CODES_IN.get((country or "").upper(), {}).get(carrier) or _CODES.get(
        carrier
    )


def parcel_codes(country: str | None, learned: Mapping[str, str]) -> dict[str, str]:
    """Return the code each carrier's numbers are added under, by carrier."""
    carriers = {*_CODES, *_CODES_IN.get((country or "").upper(), {}), *learned}
    return {
        carrier: code
        for carrier in sorted(carriers)
        if (code := parcel_code(carrier, country, learned)) is not None
    }
