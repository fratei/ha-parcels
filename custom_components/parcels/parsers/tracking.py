"""Tracking numbers: normalisation, check digits, detection and links.

Public API (stable, used by the engine and the AI checks):
``normalize_tracking_number``, ``is_s10``, ``validate_tracking_number``,
``detect_carrier``, ``find_tracking_numbers`` and ``tracking_url``.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import quote

FALLBACK_URL = "https://t.17track.net/en#nums={n}"

_S10_RE = re.compile(r"^[A-Z]{2}\d{9}[A-Z]{2}$")
_UPS_RE = re.compile(r"^1Z[0-9A-Z]{16}$")
_AMAZON_RE = re.compile(r"^TBA\d{12}$")
_S10_WEIGHTS = (8, 6, 4, 2, 3, 5, 9, 7)

# Postal operators that use UPU S10 numbers for tracked items.
S10_CARRIERS = frozenset(
    {
        "bpost",
        "cainiao",
        "colissimo",
        "correos",
        "ctt",
        "ctt_expresso",
        "deutsche_post",
        "la_poste",
        "poste_italiane",
        "postnl",
        "royal_mail",
        "usps",
    }
)

# Formats per carrier, after normalisation. S10 is accepted separately for
# the carriers in S10_CARRIERS.
CARRIER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "amazon": (_AMAZON_RE, re.compile(r"^[A-Z]{2}\d{10,12}$")),
    "ups": (_UPS_RE,),
    "dhl": (
        re.compile(r"^\d{10}$"),
        re.compile(r"^\d{12}$"),
        re.compile(r"^\d{20}$"),
        re.compile(r"^JJD\d{18,20}$"),
        re.compile(r"^JVGL\d{10,20}$"),
        re.compile(r"^GM\d{16,22}$"),
        re.compile(r"^[0-9A-Z]{10,39}$"),
    ),
    "dpd": (re.compile(r"^\d{14}$"), re.compile(r"^\d{14}[0-9A-Z]$")),
    "gls": (re.compile(r"^\d{11,14}$"), re.compile(r"^[0-9A-Z]{8}$")),
    "seur": (re.compile(r"^[0-9A-Z]{8,22}$"),),
    "ctt": (re.compile(r"^[0-9A-Z]{10,20}$"),),
    "ctt_expresso": (re.compile(r"^[0-9A-Z]{10,20}$"),),
    "correos": (re.compile(r"^P[QKX][0-9A-Z]{14,21}$"),),
    "correos_express": (re.compile(r"^\d{10,23}$"),),
    "mrw": (re.compile(r"^\d{8,14}$"),),
    "nacex": (re.compile(r"^\d{4}/?\d{6,10}$"), re.compile(r"^\d{8,12}$")),
    "paack": (re.compile(r"^[0-9A-Z]{8,24}$"),),
    "inpost": (re.compile(r"^\d{24}$"), re.compile(r"^[0-9A-Z]{10,24}$")),
    "vinted_go": (re.compile(r"^[0-9A-Z]{8,24}$"),),
    "fedex": (
        re.compile(r"^\d{12}$"),
        re.compile(r"^\d{15}$"),
        re.compile(r"^\d{20,22}$"),
    ),
    "tnt": (re.compile(r"^\d{9}$"), re.compile(r"^[A-Z]{2}\d{9}[A-Z]{2}$")),
    "mondial_relay": (re.compile(r"^\d{8,12}$"),),
}

_GENERIC_RE = re.compile(r"^[0-9A-Z]{8,35}$")

URL_TEMPLATES: dict[str, str] = {
    "ups": "https://www.ups.com/track?tracknum={n}",
    "dhl": "https://www.dhl.com/global-en/home/tracking/tracking-parcel.html?submit=1&tracking-id={n}",
    "dpd": "https://tracking.dpd.de/status/en_US/parcel/{n}",
    "ctt": "https://appserver.ctt.pt/CustomerArea/PublicArea_Detail?ObjectCodeInput={n}&SearchInput={n}",
    "ctt_expresso": "https://appserver.ctt.pt/CustomerArea/PublicArea_Detail?ObjectCodeInput={n}&SearchInput={n}",
    "seur": "https://www.seur.com/livetracking/?segOnlineIdentificador={n}",
    "gls": "https://gls-group.com/track/{n}",
}

# Words that introduce a tracking number, in pt, es, en, de, fr, it and nl.
_KEYWORDS = (
    "tracking",
    "track",
    "seguimento",
    "rastreio",
    "objeto",
    "encomenda",
    "seguimiento",
    "envío",
    "envio",
    "localizador",
    "sendung",
    "paket",
    "suivi",
    "colis",
    "spedizione",
    "tracciamento",
    "zending",
    "pakket",
    "volgnummer",
    "parcel",
    "shipment",
    "waybill",
)
_WORD_RE = re.compile(r"(?<![0-9A-Za-z])[0-9A-Za-z]{8,35}(?![0-9A-Za-z])")


@dataclass(frozen=True, slots=True)
class TrackingMatch:
    """A tracking number found in text."""

    number: str
    carrier: str | None
    validated: bool


def normalize_tracking_number(value: str) -> str:
    """Uppercase a tracking number and drop spaces, dashes and dots."""
    return re.sub(r"[\s\-.]", "", value).upper()


def s10_check_digit(serial: str) -> int:
    """Return the UPU S10 check digit for an 8-digit serial number."""
    total = sum(int(d) * w for d, w in zip(serial, _S10_WEIGHTS, strict=True))
    check = 11 - total % 11
    if check == 10:
        return 0
    if check == 11:
        return 5
    return check


def is_s10(number: str) -> bool:
    """Return True for a valid UPU S10 number such as RR123456785PT."""
    number = normalize_tracking_number(number)
    if not _S10_RE.match(number):
        return False
    return s10_check_digit(number[2:10]) == int(number[10])


def ups_check_digit_ok(number: str) -> bool:
    """Return True when a UPS 1Z number has a valid check digit."""
    number = normalize_tracking_number(number)
    if not _UPS_RE.match(number):
        return False
    total = 0
    for pos, char in enumerate(number[2:17], start=1):
        value = int(char) if char.isdigit() else (ord(char) - ord("A") + 2) % 10
        total += value * (2 if pos % 2 == 0 else 1)
    return (10 - total % 10) % 10 == int(number[17])


def _generic_ok(number: str) -> bool:
    if not _GENERIC_RE.match(number):
        return False
    digits = sum(c.isdigit() for c in number)
    return digits >= 6 and len(set(number)) > 2


def validate_tracking_number(number: str, carrier: str | None = None) -> bool:
    """Return True when a number fits the carrier's format and check digit."""
    number = normalize_tracking_number(number)
    if not number:
        return False
    if _S10_RE.match(number):
        return is_s10(number) and (
            carrier in (None, "other", "tnt") or carrier in S10_CARRIERS
        )
    if number.startswith("1Z"):
        return ups_check_digit_ok(number) and carrier in (None, "other", "ups")
    if carrier in (None, "other") or carrier not in CARRIER_PATTERNS:
        if carrier in S10_CARRIERS:
            return False
        return _generic_ok(number)
    return any(p.match(number) for p in CARRIER_PATTERNS[carrier]) and _generic_ok(
        number.replace("/", "")
    )


def detect_carrier(number: str) -> str | None:
    """Return the carrier for numbers whose format identifies it."""
    number = normalize_tracking_number(number)
    if ups_check_digit_ok(number):
        return "ups"
    if _AMAZON_RE.match(number):
        return "amazon"
    if is_s10(number):
        country = number[-2:]
        return {
            "PT": "ctt",
            "ES": "correos",
            "FR": "la_poste",
            "DE": "deutsche_post",
            "GB": "royal_mail",
            "IT": "poste_italiane",
            "NL": "postnl",
            "BE": "bpost",
            "US": "usps",
            "CN": "cainiao",
        }.get(country)
    if re.match(r"^JJD\d{18,20}$", number) or re.match(r"^JVGL\d{10,20}$", number):
        return "dhl"
    return None


def _has_keyword(text: str, start: int) -> bool:
    window = text[max(0, start - 60) : start].lower()
    return any(word in window for word in _KEYWORDS)


def find_tracking_numbers(text: str, carrier: str | None = None) -> list[TrackingMatch]:
    """Find tracking numbers in text.

    S10, UPS 1Z and Amazon Logistics numbers are found anywhere. Other numbers
    are only accepted next to a tracking keyword and, when a carrier is given,
    when they match its format.
    """
    found: dict[str, TrackingMatch] = {}
    for match in _WORD_RE.finditer(text):
        raw = match.group(0)
        number = normalize_tracking_number(raw)
        if number in found:
            continue
        if is_s10(number) or ups_check_digit_ok(number) or _AMAZON_RE.match(number):
            detected = detect_carrier(number)
            use = (
                carrier
                if carrier and validate_tracking_number(number, carrier)
                else detected
            )
            found[number] = TrackingMatch(number, use, True)
            continue
        if not _has_keyword(text, match.start()):
            continue
        if carrier and carrier != "other":
            if validate_tracking_number(number, carrier):
                found[number] = TrackingMatch(number, carrier, False)
        elif _generic_ok(number) and not number.isalpha():
            found[number] = TrackingMatch(number, detect_carrier(number), False)
    return list(found.values())


def tracking_url(carrier: str | None, number: str) -> str:
    """Return an official tracking link, or 17TRACK's when there is none."""
    number = normalize_tracking_number(number)
    template = URL_TEMPLATES.get(carrier or "", FALLBACK_URL)
    return template.format(n=quote(number, safe=""))
