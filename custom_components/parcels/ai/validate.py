"""Check an AI answer against the e-mail it came from.

The answer is untrusted. ``validate_output`` keeps only the values it can
check and records an error code for every value it drops:

* ``kind`` must be one of ``MailKind``; otherwise the answer is unusable.
* Tracking and order numbers must be written in the e-mail (sender name,
  subject, body or the tracking numbers in its links), allowing the spaces,
  dashes and dots the e-mail printed. Tracking numbers must also pass the
  format and check-digit rules of their carrier. The code's own detector
  reads the subject and body as well, so a number the model missed is still
  found; the model's numbers are only extra candidates. Values marked as
  order, phone or tax numbers, or equal to the pickup code, are excluded.
* Dates and times are normalized in code from the forms models write
  (``9h``, ``09:00:00.000Z``, ``19/11``, ``19 de novembro``, ``amanhã``),
  and dates must fall between 2 days before and 60 days after the e-mail.
* The carrier comes from the sender's domain when it is a carrier's, else
  from the model's answer when the e-mail names that carrier, else from the
  sender name, else from each tracking number's format.
* Free text (merchant, items, pickup point) must be short plain text, and
  the pickup code must be written in the e-mail.

The confidence is computed here, never taken from the model: 0.8 when no
value was dropped and the result has a grounded identifier, else 0.5.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, time, timedelta, tzinfo
import re
from typing import Any
import unicodedata

from ..const import CARRIER_NAMES, MailKind
from ..parsers.base import Eta, MailMessage, ParsedShipment, ParseResult
from ..parsers.eta import parse_eta, parse_time_window
from ..parsers.lang import MONTHS, WEEKDAY_ABBREVIATIONS, WEEKDAYS, fold
from ..parsers.senders import lookup, organizational_domain
from ..parsers.tracking import (
    detect_carrier,
    find_tracking_numbers,
    normalize_tracking_number,
    tracking_url,
    validate_tracking_number,
)
from .prompt import email_body, is_strong_number, link_entries, received_at

CONFIDENCE_HIGH = 0.8
CONFIDENCE_LOW = 0.5

DAYS_BEFORE = 2
DAYS_AFTER = 60

MAX_TRACKING_NUMBERS = 20
MAX_ORDER_NUMBERS = 10
MAX_ITEMS = 10
MAX_ITEM_CHARS = 80
MAX_MERCHANT_CHARS = 60
MAX_PICKUP_POINT_CHARS = 120
MAX_PICKUP_CODE_CHARS = 20
LABEL_WINDOW_CHARS = 40

NOTE_ADDED_BY_DETECTOR = "tracking_added_by_detector"

# Carrier domains that aren't listed as carriers in parsers/senders.py.
EXTRA_CARRIER_DOMAINS: dict[str, str] = {"sda.it": "sda", "vintedgo.com": "vinted_go"}

_EXTRA_CARRIER_ALIASES: dict[str, str] = {
    "amazon logistics": "amazon",
    "aliexpress standard shipping": "cainiao",
    "bartolini": "brt",
    "correios": "ctt",
    "correios de portugal": "ctt",
    "correos de portugal": "ctt",
    "ctt correios": "ctt",
    "ctt correios de portugal": "ctt",
    "ctt express": "ctt_expresso",
    "ctt expresso": "ctt_expresso",
    "fed ex": "fedex",
    "federal express": "fedex",
    "post nl": "postnl",
    "united states postal service": "usps",
    "us postal service": "usps",
    "vintedgo": "vinted_go",
    "yun express": "yunexpress",
}

# Words removed from carrier names before matching ("DPD Portugal" -> dpd).
_CARRIER_NOISE_WORDS = frozenset(
    {
        "be",
        "belgie",
        "belgique",
        "belgium",
        "bv",
        "de",
        "deutschland",
        "es",
        "espana",
        "fr",
        "france",
        "gb",
        "germany",
        "gmbh",
        "group",
        "groupe",
        "gruppe",
        "iberia",
        "iberica",
        "internacional",
        "international",
        "it",
        "italia",
        "italy",
        "lda",
        "ltd",
        "nederland",
        "netherlands",
        "nl",
        "portugal",
        "pt",
        "sa",
        "spa",
        "spain",
        "uk",
    }
)

_NULL_WORDS = frozenset(
    {
        "",
        "-",
        "--",
        "aucun",
        "desconhecido",
        "desconocido",
        "geen",
        "inconnu",
        "keine",
        "n/a",
        "nenhum",
        "nessuno",
        "nil",
        "ninguno",
        "none",
        "null",
        "onbekend",
        "sconosciuto",
        "unbekannt",
        "unknown",
    }
)
_NULL_CARRIERS = _NULL_WORDS | {
    "altro",
    "andere",
    "anders",
    "autre",
    "other",
    "otra",
    "otro",
    "outra",
    "outro",
    "overig",
}

_ORDER_LABEL_RE = re.compile(
    r"(?:(?<![a-z])(?:order|orden|pedido|bestellung|bestellnummer|bestellnr|bestell-nr"
    r"|auftrag|auftragsnummer|auftragsnr|commande|ordine|bestelling|bestelnummer"
    r"|ordernummer|ordernr)"
    r"(?:\s*(?:n\.o|n°|n\.|no|nr|number|numero|nummer|num|id|ref|#))?"
    r"|(?<![a-z])(?:n\.o|n°|no|numero|nr)\s*(?:(?:de|da|do)\s+)?encomenda"
    r"|(?<![a-z])encomenda\s*(?:n\.o|n°|n\.|no|nr|numero|#))"
    r"(?:\s+(?:is|e|es|ist|est))?[\s:#.\-]*$"
)
# A label the model may copy in front of an order number ("Pedido nº 123").
_ORDER_PREFIX_RE = re.compile(
    r"^(?:order|orden|pedido|bestellung|bestellnummer|commande|ordine|bestelling"
    r"|ordernummer|encomenda)(?:\s*(?:n\.?º|n\.?o|n°|n\.|no|nr|number|numero"
    r"|número|nummer|id|#))?[\s:#.\-]*(?=\S)",
    re.IGNORECASE,
)
_OTHER_NUMBER_LABEL_RE = re.compile(
    r"(?<![a-z])(?:phone|telephone|tel|telefone|telemovel|telefono|telefon|telefoon"
    r"|movil|mobile|mobil|celular|contacto|contato|contact|kontakt|whatsapp|fax|nif"
    r"|nipc|cif|nie|vat|iva|iban|contribuinte|tva|btw|ust-?idnr|steuernummer)"
    r"(?:\s*(?:n\.o|n°|n\.|no|nr|number|numero|nummer|#))?"
    r"[\s:#.\-]*(?:\(?\+?\d{1,4}\)?[\s\-]*)?$"
)

# In a carrier's own e-mail a bare "encomenda" names the parcel ("A sua
# encomenda 09123456789012"); "n.º da encomenda" and "encomenda n.º" name
# the order and are left alone.
_ENCOMENDA_RE = re.compile(r"(?<![^\W\d_])(encomenda)(s?)(?![^\W\d_])", re.IGNORECASE)
_ORDER_BEFORE_RE = re.compile(
    r"(?<![^\W\d_])(?:n\.?\s*[o\u00ba\u00b0]\.?|n[u\u00fa]mero|nr\.?)\s*"
    r"(?:(?:da|de|do)\s+)?$"
)
# "encomenda no ponto" is "in the", so a bare "no" doesn't count after it.
_ORDER_AFTER_RE = re.compile(
    r"\s*(?:n\.?\s*[\u00ba\u00b0]|n\.\s*o\b|#|nr\b|n[u\u00fa]mero)"
)

_URL_TEXT_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
_URL_LIKE_RE = re.compile(r"://|(?<![a-z0-9])www\.", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}", re.IGNORECASE)
_HTML_RE = re.compile(
    r"<\s*/?\s*[a-z!][^>]*>|&(?:[a-z]+|#\d+|#x[0-9a-f]+);", re.IGNORECASE
)
_NUMBER_RE = re.compile(r"^[0-9A-Z]{4,40}$")
_ORDER_RE = re.compile(r"^(?=[^0-9]*[0-9])[0-9A-Za-z]{3,40}$")
_PICKUP_CODE_RE = re.compile(r"^[0-9A-Za-z]{3,20}$")
_LIST_SPLIT_RE = re.compile(r"[,;\n]+")

# Times
_NOON_WORDS = frozenset(
    {
        "meio-dia",
        "meio dia",
        "meiodia",
        "mediodia",
        "medio dia",
        "noon",
        "midday",
        "mittag",
        "midi",
        "mezzogiorno",
        "middag",
    }
)
_ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}(?:t|\s+)(?P<t>\S.*)$")
_TIME_OFFSET_RE = re.compile(
    r"^(?P<t>\d{1,2}:\d{2}(?::\d{2}(?:[.,]\d{1,9})?)?)\s*"
    r"(?:z|utc|gmt|[+-]\d{2}(?::?\d{2})?)$"
)
_TIME_PREFIX_RE = re.compile(
    r"^(?:(?:a partir d[aoe]s?|a partir de|entre|between|zwischen|tussen|tra|fra"
    r"|from|after|before|until|till|by|at|around|about|approx|ca|circa|as|a|das"
    r"|des|dos|do|da|de|las|los|alle|dalle|ore|um|ab|bis|om|tot|vanaf|vers|apres"
    r"|avant|jusqu'?\s?a|hasta|desde|ate|antes|depois)\s+)+"
)
_TIME_RE = re.compile(
    r"^(?P<h>\d{1,2})"
    r"(?::(?P<m1>\d{2})(?::\d{2}(?:[.,]\d{1,9})?)?"
    r"|\s*h\s*(?P<m2>\d{2})?"
    r"|\.(?P<m3>\d{2}))?"
    r"\s*(?P<ap>a\.?\s?m\.?|p\.?\s?m\.?)?"
    r"\s*(?:uhr|uur|u|horas|hora|hrs|hr|heures|heure|ore|min)?\.?$"
)
_TIME_RANGE_SPLIT_RE = re.compile(
    r"\s*[-\u2013\u2014]\s*|\s+(?:to|a|e|and|und|en|et|y|bis|tot|al|alle)\s+"
)
# Open windows: "até às 13h" ends a window, "a partir das 14h" starts one.
_TIME_UNTIL_RE = re.compile(
    r"^(?:ate|antes d[aoe]s?|until|till|by|before|no later than|bis"
    r"|spatestens|hasta|jusqu'?\s?a|avant|entro|fino a(?:lle)?|prima delle|tot"
    r"|uiterlijk|voor)\s+"
)
_TIME_FROM_RE = re.compile(
    r"^(?:a partir d[aoe]s?|depois d[aoe]s?|desde|from|after|ab"
    r"|des|apres|dalle|dopo le|vanaf|na)\s+"
)

# Dates
_ISO_DATE_RE = re.compile(r"^(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})(?:[t\s].*)?$")
_YMD_RE = re.compile(r"^(?P<y>\d{4})[/.](?P<m>\d{1,2})[/.](?P<d>\d{1,2})$")
_DMY_RE = re.compile(
    r"^(?P<d>\d{1,2})(?P<sep>[/.])(?P<m>\d{1,2})(?:(?P=sep)(?P<y>\d{4}|\d{2}))?\.?$"
)
_DMY_DASH_RE = re.compile(r"^(?P<d>\d{1,2})-(?P<m>\d{1,2})-(?P<y>\d{4}|\d{2})$")
_DAY_MONTH_RE = re.compile(
    r"^(?P<d>\d{1,2})(?:st|nd|rd|th|er|eme|e|o|a|\.o|\.a|\.)?\s*"
    r"(?:(?:de|of|di|du|del)\s+)?(?P<mon>[a-z]+)\.?"
    r"(?:\s*,?\s*(?:(?:de|del|of)\s+)?(?P<y>\d{4}))?$"
)
_MONTH_DAY_RE = re.compile(
    r"^(?P<mon>[a-z]+)\.?\s*(?P<d>\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(?P<y>\d{4}))?$"
)
_WEEKDAY_NAMES = sorted({*WEEKDAYS, *WEEKDAY_ABBREVIATIONS}, key=len, reverse=True)
_WEEKDAY_PREFIX_RE = re.compile(
    rf"^(?:{'|'.join(re.escape(name) for name in _WEEKDAY_NAMES)})\.?,?\s+"
)
_DATE_ARTICLE_RE = re.compile(
    r"^(?:(?:on|the|le|el|il|lo|o|a|am|op|dia|den|dem|der|de|jour)\s+)+(?=\d)"
)


@dataclass(frozen=True, slots=True)
class Validation:
    """A checked AI answer: a result, or the reasons it was rejected."""

    result: ParseResult | None
    errors: tuple[str, ...] = ()


def _name_key(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9&+]+", " ", fold(text)).split())


def _build_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for key, name in CARRIER_NAMES.items():
        if key == "other":
            continue
        aliases[_name_key(key)] = key
        aliases[_name_key(name)] = key
    for alias, key in _EXTRA_CARRIER_ALIASES.items():
        aliases[_name_key(alias)] = key
    for alias, key in list(aliases.items()):
        aliases.setdefault(alias.replace(" ", ""), key)
    return aliases


CARRIER_ALIASES: dict[str, str] = _build_aliases()
_ALIAS_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {}
for _alias, _carrier in CARRIER_ALIASES.items():
    _ALIAS_PATTERNS[_carrier] = (
        *_ALIAS_PATTERNS.get(_carrier, ()),
        re.compile(rf"(?<![a-z0-9]){re.escape(_alias)}(?![a-z0-9])"),
    )


def map_carrier(name: str, *, prefix: bool = True) -> str | None:
    """Map a carrier name such as "CTT Expresso" or "DPD Portugal" to its key.

    Case, accents, punctuation and country words don't matter. With
    ``prefix``, a known name followed by other words also matches
    ("UPS Standard" -> ups); the longest known name wins.
    """
    key = _name_key(name)
    if not key:
        return None
    if key in CARRIER_ALIASES:
        return CARRIER_ALIASES[key]
    stripped = " ".join(
        word for word in key.split() if word not in _CARRIER_NOISE_WORDS
    )
    for candidate in (stripped, stripped.replace(" ", "")):
        if candidate in CARRIER_ALIASES:
            return CARRIER_ALIASES[candidate]
    if not prefix or not stripped:
        return None
    best: tuple[str, str] | None = None
    for alias, carrier in CARRIER_ALIASES.items():
        if stripped.startswith(f"{alias} ") and (
            best is None or len(alias) > len(best[0])
        ):
            best = (alias, carrier)
    return best[1] if best else None


def sender_carrier(message: MailMessage) -> str | None:
    """Return the carrier whose own domain sent the e-mail, if any."""
    domain = message.sender_domain
    if not domain:
        return None
    info = lookup(domain)
    if info is not None and info.kind == "carrier" and info.carrier in CARRIER_NAMES:
        return info.carrier
    return EXTRA_CARRIER_DOMAINS.get(organizational_domain(domain))


def carrier_scan_text(text: str) -> str:
    """Let a bare "encomenda" label a tracking number in a carrier's e-mail.

    The shared detector doesn't treat "encomenda" (order or parcel in
    Portuguese) as a tracking word. When a carrier sent the e-mail it means
    the parcel, so it is replaced by "remessa" for the detector only.
    """

    def replace(match: re.Match[str]) -> str:
        before = text[max(0, match.start() - 20) : match.start()].lower()
        after = text[match.end() : match.end() + 12].lower()
        if _ORDER_BEFORE_RE.search(before) or _ORDER_AFTER_RE.match(after):
            return match.group(0)
        return "remessa" + match.group(2)

    return _ENCOMENDA_RE.sub(replace, text)


def _to_time(hour: str, minute: str | None, ampm: str | None) -> time | None:
    h = int(hour)
    m = int(minute or 0)
    if ampm:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ampm.startswith("p") else 0)
    if h == 24 and m == 0:
        return time(23, 59)
    if h > 23 or m > 59:
        return None
    return time(h, m)


def normalize_time(value: str) -> time | None:
    """Read one time of day as written by a model or an e-mail.

    Accepts forms such as ``9h``, ``9H``, ``9h30``, ``13h00``, ``9:00``,
    ``09:00:00``, ``9.30``, ``9 Uhr``, ``9am`` and ``09:00:00.000Z``. A time
    zone suffix is ignored: the value is taken as local wall time.
    """
    s = " ".join(fold(value).split()).strip(" ,;")
    if not s:
        return None
    if match := _ISO_DATETIME_RE.match(s):
        s = match.group("t")
    if match := _TIME_OFFSET_RE.match(s):
        s = match.group("t")
    if s in _NOON_WORDS:
        return time(12, 0)
    s = _TIME_PREFIX_RE.sub("", s)
    if s in _NOON_WORDS:
        return time(12, 0)
    match = _TIME_RE.match(s)
    if match is None:
        return None
    minute = match.group("m1") or match.group("m2") or match.group("m3")
    return _to_time(match.group("h"), minute, match.group("ap"))


def _make_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _nearest(month: int, day: int, reference: date) -> date | None:
    candidates = [
        found
        for year in (reference.year - 1, reference.year, reference.year + 1)
        if (found := _make_date(year, month, day)) is not None
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda d: (abs((d - reference).days), -d.toordinal()))


def _day_month(day: int, month: int, year: str | None, reference: date) -> date | None:
    if year is None:
        return _nearest(month, day, reference)
    full = int(year) + (2000 if len(year) == 2 else 0)
    return _make_date(full, month, day)


def _numeric_date(s: str, reference: date) -> date | None:
    if match := _ISO_DATE_RE.match(s):
        return _make_date(int(match["y"]), int(match["m"]), int(match["d"]))
    if match := _YMD_RE.match(s):
        return _make_date(int(match["y"]), int(match["m"]), int(match["d"]))
    match = _DMY_RE.match(s) or _DMY_DASH_RE.match(s)
    if match is None:
        return None
    day, month = int(match["d"]), int(match["m"])
    found = _day_month(day, month, match["y"], reference)
    if found is None and month <= 31 and day <= 12:
        found = _day_month(month, day, match["y"], reference)
    return found


def _text_date(s: str, reference: date) -> date | None:
    if match := _DAY_MONTH_RE.match(s):
        month = MONTHS.get(match["mon"])
        if month:
            return _day_month(int(match["d"]), month, match["y"], reference)
    if match := _MONTH_DAY_RE.match(s):
        month = MONTHS.get(match["mon"])
        if month:
            return _day_month(int(match["d"]), month, match["y"], reference)
    return None


def normalize_date(value: str, reference: date) -> date | None:
    """Read one calendar date as written by a model or an e-mail.

    Accepts ``YYYY-MM-DD`` (also with a time after it), ``dd/mm``,
    ``dd/mm/yyyy``, ``dd-mm-yyyy``, ``dd.mm.yyyy`` and a day with a month
    name in Portuguese, Spanish, English, German, French, Italian or Dutch
    ("19 de novembro", "Thursday, November 19th"). Without a year, the
    nearest such date to ``reference`` (the e-mail's date) is used.
    """
    s = " ".join(fold(value).split()).strip(" ,;")
    if not s:
        return None
    if (found := _numeric_date(s, reference)) is not None:
        return found
    variants = [s]
    without_weekday = _WEEKDAY_PREFIX_RE.sub("", s)
    if without_weekday != s:
        variants.append(without_weekday)
    for variant in list(variants):
        without_article = _DATE_ARTICLE_RE.sub("", variant)
        if without_article != variant:
            variants.append(without_article)
    for variant in variants:
        found = _numeric_date(variant, reference) if variant != s else None
        if found is None:
            found = _text_date(variant, reference)
        if found is not None:
            return found
    return None


class _Unreadable(Exception):
    """A value that is present but can't be read."""


def _text_value(value: Any) -> str | None:
    """Return a collapsed string, None when empty; raise when not text."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise _Unreadable
    text = " ".join(value.split())
    if fold(text) in _NULL_WORDS:
        return None
    return text


def _is_plain(text: str) -> bool:
    if _URL_LIKE_RE.search(text) or _EMAIL_RE.search(text) or _HTML_RE.search(text):
        return False
    return not any(unicodedata.category(char) in ("Cc", "Cf") for char in text)


def _as_list(value: Any) -> list[Any] | None:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return None


def _written_pattern(value: str, separators: str) -> re.Pattern[str]:
    gap = f"[{separators}]{{0,3}}"
    body = gap.join(re.escape(char) for char in value)
    return re.compile(rf"(?<![0-9A-Za-z]){body}(?![0-9A-Za-z])", re.IGNORECASE)


def _tracking_pattern(number: str) -> re.Pattern[str]:
    return _written_pattern(number, r"\s\-.")


def _previous_text(text: str, start: int) -> str:
    """Return up to 40 characters before ``start``, or the previous line."""
    line_start = text.rfind("\n", 0, start) + 1
    prefix = text[max(line_start, start - LABEL_WINDOW_CHARS) : start]
    if prefix.strip() or line_start == 0:
        return prefix
    for line in reversed(text[: line_start - 1].splitlines()):
        if line.strip():
            return line[-LABEL_WINDOW_CHARS:]
    return prefix


def _labelled(text: str, pattern: re.Pattern[str], label: re.Pattern[str]) -> bool:
    return any(
        label.search(fold(_previous_text(text, match.start())))
        for match in pattern.finditer(text)
    )


def _in_range(value: date, reference: date) -> bool:
    return (
        reference - timedelta(days=DAYS_BEFORE)
        <= value
        <= reference + timedelta(days=DAYS_AFTER)
    )


class _Checker:
    """Validate one AI answer for one e-mail."""

    def __init__(self, data: Mapping[str, Any], message: MailMessage, tz: tzinfo):
        self.data = data
        self.message = message
        self.tz = tz
        self.errors: list[str] = []
        self.notes: list[str] = []
        self.received = received_at(message, tz)
        self.reference = self.received.date()
        subject = message.subject or ""
        text = message.text or ""
        body = email_body(message)
        self.links = link_entries(link.url for link in message.links)
        link_numbers = [number for _, numbers in self.links for number in numbers]
        self.number_text = "\n".join(
            [message.sender_name or "", subject, text, body, *link_numbers]
        )
        self.detector_text = f"{subject}\n{_URL_TEXT_RE.sub(' ', text)}"
        self.sender_hint = sender_carrier(message)
        self.name_carrier = self.sender_name_carrier()
        self.scan_text = (
            carrier_scan_text(self.detector_text)
            if self.sender_hint or self.name_carrier
            else self.detector_text
        )
        self.code_text = "\n".join([subject, text, body])
        link_hosts = " ".join(domain for domain, _ in self.links)
        self.carrier_text = _name_key(
            " ".join(
                [
                    message.sender_name or "",
                    message.sender_domain or "",
                    subject,
                    text,
                    link_hosts,
                ]
            )
        )

    def error(self, code: str) -> None:
        if code not in self.errors:
            self.errors.append(code)

    def run(self) -> Validation:
        if not isinstance(self.data, Mapping):
            return Validation(None, ("not_a_mapping",))
        kind = self.kind()
        if kind is None:
            return Validation(None, ("kind_invalid",))
        merchant = self.merchant()
        items = self.items()
        pickup_point = self.pickup_point()
        pickup_code = self.pickup_code()
        orders = self.orders()
        carrier = self.carrier()
        numbers, detected = self.tracking_numbers(carrier, orders, pickup_code)
        strong = {number for number, _ in numbers if is_strong_number(number)}
        kept_orders = []
        for order in orders:
            if _compact(order).upper() in strong:
                self.error("order_is_tracking")
            else:
                kept_orders.append(order)
        eta = self.eta()
        if kind is MailKind.NOT_PARCEL:
            if any(n not in detected or n in strong for n, _ in numbers):
                self.error("not_parcel_has_tracking")
            numbers = []
        elif detected:
            self.notes.append(NOTE_ADDED_BY_DETECTOR)
        order_numbers = tuple(kept_orders)
        shipments = self.shipments(
            kind, carrier, numbers, eta, pickup_point, pickup_code, order_numbers, items
        )
        grounded = kind is MailKind.NOT_PARCEL or (
            kind is not MailKind.UNKNOWN
            and (bool(numbers) or (kind is MailKind.ORDER and bool(order_numbers)))
        )
        confidence = CONFIDENCE_HIGH if grounded and not self.errors else CONFIDENCE_LOW
        result = ParseResult(
            parser="ai",
            kind=kind,
            merchant=merchant,
            order_numbers=order_numbers,
            shipments=shipments,
            items=items,
            confidence=confidence,
            language=self.message.language,
            source="ai",
            notes=(*self.errors, *self.notes),
        )
        return Validation(result, tuple(self.errors))

    def kind(self) -> MailKind | None:
        value = self.data.get("kind")
        if not isinstance(value, str):
            return None
        try:
            return MailKind(re.sub(r"[\s\-]+", "_", value.strip().lower()))
        except ValueError:
            return None

    def merchant(self) -> str | None:
        try:
            text = _text_value(self.data.get("merchant"))
        except _Unreadable:
            self.error("merchant_invalid")
            return None
        if text is None:
            return None
        if len(text) > MAX_MERCHANT_CHARS or not _is_plain(text):
            self.error("merchant_invalid")
            return None
        return text

    def items(self) -> tuple[str, ...]:
        values = _as_list(self.data.get("items"))
        if values is None:
            self.error("items_invalid")
            return ()
        if len(values) > MAX_ITEMS:
            self.error("items_too_many")
            values = values[:MAX_ITEMS]
        items: list[str] = []
        for value in values:
            try:
                text = _text_value(value)
            except _Unreadable:
                self.error("item_invalid")
                continue
            if text is None:
                continue
            if not _is_plain(text):
                self.error("item_invalid")
                continue
            if len(text) > MAX_ITEM_CHARS:
                text = text[: MAX_ITEM_CHARS - 1].rstrip() + "\u2026"
            if text not in items:
                items.append(text)
        return tuple(items)

    def pickup_point(self) -> str | None:
        try:
            text = _text_value(self.data.get("pickup_point"))
        except _Unreadable:
            self.error("pickup_point_invalid")
            return None
        if text is None:
            return None
        if len(text) > MAX_PICKUP_POINT_CHARS or not _is_plain(text):
            self.error("pickup_point_invalid")
            return None
        return text

    def pickup_code(self) -> str | None:
        try:
            text = _text_value(self.data.get("pickup_code"))
        except _Unreadable:
            self.error("pickup_code_invalid")
            return None
        if text is None:
            return None
        text = text.rpartition(":")[2].strip()
        code = re.sub(r"[\s\-]", "", text)
        if len(text) > MAX_PICKUP_CODE_CHARS or not _PICKUP_CODE_RE.match(code):
            self.error("pickup_code_invalid")
            return None
        match = _written_pattern(code, r"\s\-").search(self.code_text)
        if match is None:
            self.error("pickup_code_not_in_email")
            return None
        return " ".join(match.group(0).split())

    def orders(self) -> list[str]:
        values = _as_list(self.data.get("order_numbers"))
        if values is None:
            self.error("order_numbers_invalid")
            return []
        if len(values) > MAX_ORDER_NUMBERS:
            self.error("order_numbers_too_many")
            values = values[:MAX_ORDER_NUMBERS]
        orders: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                self.error("order_invalid")
                continue
            for piece in _LIST_SPLIT_RE.split(value):
                piece = _ORDER_PREFIX_RE.sub("", piece.rpartition(":")[2].strip())
                piece = piece.lstrip("#").strip()
                if fold(piece) in _NULL_WORDS:
                    continue
                compact = _compact(piece)
                if not _ORDER_RE.match(compact) or len(piece) > 60:
                    self.error("order_invalid")
                    continue
                match = _written_pattern(compact, r"\s\-./").search(self.number_text)
                if match is None:
                    self.error("order_not_in_email")
                    continue
                printed = "".join(match.group(0).split())
                if compact.upper() not in seen:
                    seen.add(compact.upper())
                    orders.append(printed)
        return orders

    def sender_name_carrier(self) -> str | None:
        """Return the carrier named as the sender ("DPD Portugal").

        Shops and platforms known by their domain are skipped: their sender
        name is the shop's.
        """
        domain = self.message.sender_domain
        info = lookup(domain) if domain else None
        if info is not None and info.kind != "carrier":
            return None
        return map_carrier(self.message.sender_name or "", prefix=False)

    def carrier(self) -> str | None:
        """Return the e-mail's carrier: the sender's, the model's, or None."""
        named = self.ai_carrier(self.sender_hint)
        return self.sender_hint or named or self.name_carrier

    def ai_carrier(self, hint: str | None) -> str | None:
        try:
            text = _text_value(self.data.get("carrier"))
        except _Unreadable:
            self.error("carrier_unknown")
            return None
        if text is None or fold(text) in _NULL_CARRIERS:
            return None
        carrier = map_carrier(text)
        if carrier is None:
            self.error("carrier_unknown")
            return None
        if carrier == hint or self.carrier_named(carrier):
            return carrier
        self.error("carrier_not_in_email")
        return None

    def carrier_named(self, carrier: str) -> bool:
        """Return True when the e-mail names the carrier or one of its numbers."""
        if any(p.search(self.carrier_text) for p in _ALIAS_PATTERNS.get(carrier, ())):
            return True
        numbers = [match.number for match in find_tracking_numbers(self.detector_text)]
        numbers += [number for _, found in self.links for number in found]
        return any(detect_carrier(number) == carrier for number in numbers)

    def tracking_numbers(
        self, carrier: str | None, orders: list[str], pickup_code: str | None
    ) -> tuple[list[tuple[str, str | None]], set[str]]:
        """Return the final numbers and carriers, and those only code found.

        The model's numbers count when they are written in the e-mail and
        pass the carrier's rules; the code's detector adds what it finds.
        """
        orders_compact = {_compact(order).upper() for order in orders}
        found: dict[str, str | None] = {}
        for number in self.ai_numbers():
            if number in found:
                continue
            valid, number_carrier = _number_carrier(number, carrier)
            if not valid:
                self.error("tracking_invalid")
                continue
            reason = self.exclusion(number, orders_compact, pickup_code)
            if reason:
                self.error(reason)
                continue
            found[number] = number_carrier
        detected: set[str] = set()
        for match in find_tracking_numbers(self.scan_text, carrier=carrier):
            number = match.number
            if number in found:
                continue
            valid, number_carrier = _number_carrier(number, carrier)
            if not valid or self.exclusion(number, orders_compact, pickup_code):
                continue
            found[number] = number_carrier
            detected.add(number)
        return list(found.items()), detected

    def ai_numbers(self) -> list[str]:
        values = _as_list(self.data.get("tracking_numbers"))
        if values is None:
            self.error("tracking_numbers_invalid")
            return []
        if len(values) > MAX_TRACKING_NUMBERS:
            self.error("tracking_numbers_too_many")
            values = values[:MAX_TRACKING_NUMBERS]
        numbers: list[str] = []
        for value in values:
            if not isinstance(value, str):
                self.error("tracking_invalid")
                continue
            for piece in _LIST_SPLIT_RE.split(value):
                piece = piece.rpartition(":")[2].strip().lstrip("#").strip()
                if fold(piece) in _NULL_WORDS:
                    continue
                number = normalize_tracking_number(piece)
                if not _NUMBER_RE.match(number):
                    self.error("tracking_invalid")
                    continue
                if not _tracking_pattern(number).search(self.number_text):
                    self.error("tracking_not_in_email")
                    continue
                numbers.append(number)
        return numbers

    def exclusion(
        self, number: str, orders: set[str], pickup_code: str | None
    ) -> str | None:
        """Return why a tracking number must not be used, or None.

        UPU S10, UPS and Amazon numbers identify themselves and are kept.
        Others are left out when they equal an order number or the pickup
        code, or the e-mail labels them as an order, phone or tax number.
        """
        if is_strong_number(number):
            return None
        if pickup_code and number == _compact(pickup_code).upper():
            return "tracking_is_pickup_code"
        if number in orders:
            return "tracking_is_order"
        pattern = _tracking_pattern(number)
        if _labelled(self.detector_text, pattern, _ORDER_LABEL_RE):
            return "tracking_is_order"
        if _labelled(self.detector_text, pattern, _OTHER_NUMBER_LABEL_RE):
            return "tracking_is_other_number"
        return None

    def eta(self) -> Eta | None:
        start_span = self.date_span("eta_start")
        end_span = self.date_span("eta_end")
        start = start_span[0] if start_span else (end_span[0] if end_span else None)
        end = end_span[1] if end_span else (start_span[1] if start_span else None)
        if start and end and end < start:
            self.error("eta_end_before_start")
            end = start_span[1] if start_span else start
        window_start, window_end = self.window()
        if start is None or end is None:
            if window_start or window_end:
                self.error("window_without_date")
            return None
        return Eta(start, end, window_start, window_end)

    def date_span(self, field: str) -> tuple[date, date] | None:
        value = self.data.get(field)
        try:
            text = _text_value(value)
        except _Unreadable:
            self.error(f"{field}_unparsed")
            return None
        if text is None:
            return None
        span = self.read_date(text)
        if span is None:
            self.error(f"{field}_unparsed")
            return None
        if not (
            _in_range(span[0], self.reference) and _in_range(span[1], self.reference)
        ):
            self.error(f"{field}_out_of_range")
            return None
        return span

    def read_date(self, text: str) -> tuple[date, date] | None:
        found = normalize_date(text, self.reference)
        if found is not None:
            return (found, found)
        try:
            eta = parse_eta(text, self.received, self.tz, self.message.language)
        except ValueError, OverflowError:
            return None
        if eta is None or eta.end < eta.start:
            return None
        return (eta.start, eta.end)

    def window(self) -> tuple[time | None, time | None]:
        start_span = self.time_span("window_start")
        end_span = self.time_span("window_end")
        start = start_span[0] if start_span else None
        end = end_span[1] if end_span else None
        if start is None and end_span and end_span[0] != end_span[1]:
            start = end_span[0]
        if end is None and start_span and start_span[0] != start_span[1]:
            end = start_span[1]
        if start and end and not start < end:
            self.error("window_end_before_start")
            return None, None
        return start, end

    def time_span(self, field: str) -> tuple[time | None, time | None] | None:
        try:
            text = _text_value(self.data.get(field))
        except _Unreadable:
            self.error(f"{field}_unparsed")
            return None
        if text is None:
            return None
        span = read_time_span(text)
        if span is None:
            self.error(f"{field}_unparsed")
        return span

    def shipments(
        self,
        kind: MailKind,
        carrier: str | None,
        numbers: list[tuple[str, str | None]],
        eta: Eta | None,
        pickup_point: str | None,
        pickup_code: str | None,
        order_numbers: tuple[str, ...],
        items: tuple[str, ...],
    ) -> list[ParsedShipment]:
        if kind is MailKind.NOT_PARCEL:
            return []
        shipments = [
            ParsedShipment(
                carrier=number_carrier,
                tracking_number=number,
                kind=kind,
                eta=eta,
                pickup_point=pickup_point,
                pickup_code=pickup_code,
                order_numbers=order_numbers,
                items=items,
                tracking_url=tracking_url(number_carrier, number),
            )
            for number, number_carrier in numbers
        ]
        if not shipments and kind is not MailKind.UNKNOWN:
            shipments.append(
                ParsedShipment(
                    carrier=carrier,
                    kind=kind,
                    eta=eta,
                    pickup_point=pickup_point,
                    pickup_code=pickup_code,
                    order_numbers=order_numbers,
                    items=items,
                )
            )
        return shipments


def _compact(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", value)


def _number_carrier(number: str, carrier: str | None) -> tuple[bool, str | None]:
    """Return whether a tracking number is valid, and its carrier."""
    if carrier and validate_tracking_number(number, carrier):
        return True, carrier
    detected = detect_carrier(number)
    if detected and validate_tracking_number(number, detected):
        return True, detected
    if carrier is None and validate_tracking_number(number):
        return True, None
    return False, None


def read_time_span(text: str) -> tuple[time | None, time | None] | None:
    """Read a time ("9h") or a time range ("9h-13h", "entre as 9h e as 13h").

    Returns (first, last); both are the same for a single time, and one of
    them is None for open windows such as "até às 13h" or "a partir das 14h".
    """
    folded = " ".join(fold(text).split()).strip(" ,;")
    for pattern, until in ((_TIME_UNTIL_RE, True), (_TIME_FROM_RE, False)):
        if (match := pattern.match(folded)) and (
            found := normalize_time(folded[match.end() :])
        ):
            return (None, found) if until else (found, None)
    single = normalize_time(text)
    if single is not None:
        return single, single
    parts = _TIME_RANGE_SPLIT_RE.split(folded)
    if len(parts) == 2:
        first, last = normalize_time(parts[0]), normalize_time(parts[1])
        if first and last:
            return first, last
    window = parse_time_window(text)
    if window is None or window == (None, None):
        return None
    return window


def validate_output(
    data: Mapping[str, Any], message: MailMessage, tz: tzinfo
) -> Validation:
    """Check an AI answer against the e-mail it came from.

    Returns no result when the answer is unusable (not a mapping, or no
    valid kind); otherwise a result with only the checked values, and an
    error code for every value that was dropped.
    """
    return _Checker(data, message, tz).run()
