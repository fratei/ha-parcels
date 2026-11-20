"""Check an AI answer against the e-mail it came from.

The answer is untrusted. ``validate_output`` keeps only the values it can
check and records an error code for every value it drops:

* ``kind`` must be one of ``MailKind``; otherwise the answer is unusable.
  When the parsers' keyword detector finds a kind in the e-mail, the
  model's kind stays only if the e-mail's wording also gives it and it
  takes precedence over the detected one; else the detected kind is used.
* Tracking and order numbers must be written in the e-mail (sender name,
  subject, body or the tracking numbers in its links), allowing the spaces,
  dashes and dots the e-mail printed. Tracking numbers must also pass the
  format and check-digit rules of their carrier. The code's own detector
  reads the subject and body as well, so a number the model missed is still
  found; the model's numbers are only extra candidates. Values marked as
  order, phone or tax numbers, or written only as a delivery or pickup
  code, are excluded. A number the model miscopied by a character becomes
  the e-mail's number when exactly one number is that close (for tracking
  numbers, one that passes the carrier's rules, in the text or a link). An
  order number written only as a part of a longer number joined by hyphens
  or slashes ("4567890" in "PO-211-4567890") becomes that number when
  exactly one such number can be an order number, and is dropped
  otherwise. In a carrier's e-mail, an "order" that is the carrier's
  tracking number and isn't labelled as an order moves to the tracking
  numbers.
* Dates and times are normalized in code from the forms models write
  (``9h``, ``09:00:00.000Z``, ``19/11``, ``19 de novembro``, ``amanhã``),
  and dates must fall between 2 days before and 60 days after the e-mail.
  Kinds with no pending delivery have no delivery date. A date the e-mail
  gives only as a deadline (to collect, pay, return or be refunded by), an
  order or shipping date or a replaced date is dropped, and the date next
  to a delivery phrase, as the parsers read it, replaces a model date that
  differs from it (business days are counted here, not by the model).
* The carrier comes from the sender's domain when it is a carrier's, else
  from the model's answer when the e-mail names that carrier, else from the
  sender name, else from each tracking number's format.
* Free text (merchant, items, pickup point) must be short plain text, and
  the pickup code (a pickup code, delivery PIN or one-time code) must be
  written in the e-mail and can't be one of the tracking or order numbers.
  Items the e-mail lists only under a recommendations heading ("Buy again",
  "Recommended for you") are dropped, and repeated items are merged. The
  e-mail's carrier is never the merchant (unless it is also a shop, like
  Amazon), and a merchant given as a domain becomes the name the e-mail
  spells for it. Unless the parcel waits for pickup or missed its
  delivery, a pickup point must be written as one (a pickup, locker or
  collection word on its line or the line before) and name a place, not a
  kind of place ("a post office").
* Ollama stops each value at its cap in ``prompt.ANSWER_CAPS``, well above
  real values, so a value as long as its cap was cut. It is dropped, except
  an item, which keeps its start and ends with "…".

The confidence is computed here, never taken from the model: 0.8 when no
value was dropped and the result has a grounded identifier, else 0.5.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, time, timedelta, tzinfo
from functools import cached_property
import re
from typing import Any
import unicodedata

from ..const import CARRIER_NAMES, MailKind
from ..parsers.amazon import product_buttons
from ..parsers.base import Eta, MailMessage, ParsedShipment, ParseResult
from ..parsers.carriers import brand_carriers, phrase_regex
from ..parsers.carriers._phrases import PICKUP_NAME_LABELS, PICKUP_POINT_LABELS
from ..parsers.codes import code_spans, compact_code, find_code, mask_codes
from ..parsers.eta import (
    date_expressions,
    find_delivery_eta,
    parse_eta,
    parse_time_window,
)
from ..parsers.generic import (
    KIND_BODY_CHARS,
    KIND_PRECEDENCE,
    clean_sender_name,
    detect_kind,
    text_kinds,
)
from ..parsers.items import drop_recommended, unique_items
from ..parsers.lang import (
    MONTHS,
    WEEKDAY_ABBREVIATIONS,
    WEEKDAYS,
    detect_language,
    fold,
)
from ..parsers.senders import KNOWN_SENDERS, lookup, organizational_domain
from ..parsers.tracking import (
    PAACK_ID_RE,
    PAACK_STEM_RE,
    detect_carrier,
    find_tracking_numbers,
    id_shaped,
    named_carriers,
    normalize_tracking_number,
    tracking_url,
    validate_tracking_number,
)
from .prompt import (
    ANSWER_CAPS,
    email_body,
    is_strong_number,
    link_entries,
    received_at,
    text_link_numbers,
)

CONFIDENCE_HIGH = 0.8
CONFIDENCE_LOW = 0.5

DAYS_BEFORE = 2
DAYS_AFTER = 60

MAX_TRACKING_NUMBERS = 20
MAX_ORDER_NUMBERS = 10
MAX_ITEMS = 10
MAX_ITEM_CHARS = 80
MAX_MERCHANT_CHARS = 60
# A shop's name is read from a line only for domains this long ("ab.pt" no).
MIN_DOMAIN_NAME_CHARS = 4
MAX_PICKUP_POINT_CHARS = 120
MAX_PICKUP_CODE_CHARS = 20
LABEL_WINDOW_CHARS = 40

NOTE_ADDED_BY_DETECTOR = "tracking_added_by_detector"
NOTE_CODE_FROM_TEXT = "pickup_code_from_text"
NOTE_ITEM_RECOMMENDED = "item_recommended"
NOTE_ITEM_IS_NUMBER = "item_is_number"
NOTE_KIND_FROM_TEXT = "kind_from_text"
NOTE_NOT_OUT_TODAY = "out_for_delivery_not_today"
NOTE_ETA_DROPPED_FOR_KIND = "eta_dropped_for_kind"
NOTE_ETA_FROM_TEXT = "eta_from_text"
NOTE_ORDER_MOVED_TO_TRACKING = "order_moved_to_tracking"
NOTE_ORDER_FROM_TEXT = "order_from_text"
NOTE_TRACKING_FROM_TEXT = "tracking_from_text"
NOTE_MERCHANT_IS_CARRIER = "merchant_is_carrier"
NOTE_MERCHANT_FROM_SENDER = "merchant_from_sender_name"
NOTE_MERCHANT_FROM_TEXT = "merchant_from_text"
NOTE_PICKUP_POINT_DROPPED = "pickup_point_not_pickup"
NOTE_PICKUP_POINT_GENERIC = "pickup_point_generic"

# A miscopied order number is repaired only when it is this long, and only
# by this many changed characters (more from REPAIR_LONG_CHARS on).
REPAIR_MIN_CHARS = 6
REPAIR_LONG_CHARS = 12

# In these e-mails a bare "Code:" names the code to collect the parcel.
_LOCKER_KINDS = frozenset({MailKind.READY_FOR_PICKUP, MailKind.ATTEMPTED})
# No code is read from the e-mail for these kinds.
_NO_CODE_KINDS = frozenset({MailKind.DELIVERED, MailKind.NOT_PARCEL})
# No delivery is pending in these e-mails, so their dates are deadlines
# (to collect, pay or return by) or past dates, never delivery dates.
_NO_ETA_KINDS = frozenset(
    {
        MailKind.READY_FOR_PICKUP,
        MailKind.CUSTOMS,
        MailKind.DELIVERED,
        MailKind.RETURN,
        MailKind.CANCELLED,
        MailKind.NOT_PARCEL,
    }
)
_ETA_FIELDS = ("eta_start", "eta_end", "window_start", "window_end")

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
# Numbers written in the e-mail, to repair a miscopied order number. A value
# followed by an underscore is the start of a longer one (a Paack order ID);
# the atomic group keeps it from backing off to a shorter value.
_TOKEN_RE = re.compile(r"(?<![0-9A-Za-z])(?>[0-9A-Za-z]+(?:[\-./][0-9A-Za-z]+)*)(?!_)")
_DATE_TOKEN_RE = re.compile(r"^\d{1,4}[\-./]\d{1,2}(?:[\-./]\d{1,4})?$")
# Numbers joined by hyphens or slashes ("PO-211-4567890", "2026/4501").
_JOINED_RE = re.compile(r"(?<![0-9A-Za-z])[0-9A-Za-z]+(?:[\-/][0-9A-Za-z]+)+")
_JOINED_SPLIT_RE = re.compile(r"[\-/]")
# Label abbreviations that aren't part of a number ("Ref-4501").
_LABEL_PARTS = frozenset({"ID", "NO", "NR", "NUM", "REF"})
# A shop written as its domain ("loja-exemplo.example").
_DOMAIN_RE = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}", re.IGNORECASE
)
# Words that make a place a pickup point: labels, lockers and the verbs to
# collect a parcel, folded.
_PICKUP_WORDS_RE = phrase_regex(
    (
        *PICKUP_POINT_LABELS,
        *PICKUP_NAME_LABELS,
        "levant*",
        "recolh*",
        "recog*",
        "retir*",
        "punto pack",
        "pickup",
        "pick-up",
        "pick up",
        "collect",
        "for collection",
        "abhol*",
        "retrait",
        "relais",
        "ritir*",
        "ophal*",
        "ophaal*",
        "afhaal*",
        "afhal*",
    )
)
# Articles, possessives and "nearest" around a kind of place, folded.
_PICKUP_FILLER_WORDS = frozenset(
    {
        *("a", "an", "the", "your", "our", "nearest", "closest", "local"),
        *("o", "os", "as", "um", "uma", "no", "na", "num", "numa", "ao", "seu"),
        *("sua", "mais", "proximo", "proxima", "perto"),
        *("el", "la", "los", "las", "un", "una", "al", "su", "cercano"),
        *("cercana", "de", "del"),
        *("ein", "eine", "einer", "einem", "einen", "der", "die", "das"),
        *("den", "dem", "ihre", "ihrer", "ihrem", "nachste", "nachsten"),
        *("nachstgelegene", "nachstgelegenen", "in"),
        *("le", "les", "l", "une", "votre", "plus", "proche", "au", "du"),
        *("il", "lo", "gli", "uno", "vostro", "vicino", "vicina", "piu"),
        *("alla", "nel", "nella"),
        *("het", "een", "uw", "dichtstbijzijnde", "bij"),
    }
)
_PLACE_SPLIT_RE = re.compile(r"[\s'\u2019]+")


def _place_words(text: str) -> tuple[str, ...]:
    """Return the folded words of a place, without articles and the like."""
    words = (word.strip('.,;:!?()[]"') for word in _PLACE_SPLIT_RE.split(fold(text)))
    return tuple(word for word in words if word and word not in _PICKUP_FILLER_WORDS)


# A kind of place, not a place: "eine Filiale", "the nearest pickup point".
_GENERIC_PICKUP_PLACES = frozenset(
    _place_words(label)
    for label in (
        *PICKUP_POINT_LABELS,
        *PICKUP_NAME_LABELS,
        "post office",
        "postamt",
        "bureau de poste",
        "ufficio postale",
        "oficina de correos",
        "estacao de correios",
        "postkantoor",
    )
)

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
# Signs that an e-mail talks about a date at all, beyond what the ETA parser
# reads: a day and month, an ordinal day, a month or weekday name, or a
# number of days, weeks or months.
_DATE_EVIDENCE_RE = re.compile(
    r"(?<![\d.,])(?:[0-2]?\d|3[01])\s*[./-]\s*(?:0?[1-9]|1[0-2])(?![\d,])"
    r"|(?<![\d.,])(?:[0-2]?\d|3[01])(?:st|nd|rd|th|er|eme|o|a)(?![a-z])"
    rf"|(?<![a-z])(?:{'|'.join(sorted({*MONTHS, *WEEKDAYS}, key=len, reverse=True))})"
    r"(?![a-z])"
    r"|(?<![a-z])(?:weeks?|semanas?|wochen?|semaines?|settiman[ae]|weken|months?"
    r"|mes|meses|monate?n?|mois|mesi|mese|maanden|maand|business|working|uteis|util"
    r"|laborables?|habiles?|werktag\w*|arbeitstag\w*|ouvr\w*|lavorativ\w*|feriali"
    r"|werkdag\w*|lendemain|next day|dia seguinte|dia siguiente|giorno successivo"
    r"|nachsten tag|volgende dag)(?![a-z])"
    # A promise in hours: "24/48h", "48 horas", "24 Stunden".
    r"|(?<![\d.,:])(?:24|36|48|72|96)\s*(?:(?:[-/]|\s(?:a|to|or|e|y|o|ou|et|bis"
    r"|oder|tot|of)\s)\s*(?:24|36|48|72|96)\s*)?"
    r"(?:h|hrs?|horas?|hours?|heures?|ore|stunden|std|uur)(?![a-z])"
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


# Carriers that are also shops: "Amazon" stays the merchant of an Amazon
# Logistics parcel.
_SHOP_CARRIERS = frozenset(
    carrier
    for info in KNOWN_SENDERS.values()
    if info.kind == "merchant"
    and (carrier := map_carrier(info.name, prefix=False)) is not None
)


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


def _is_number(joined: str) -> bool:
    """Return whether parts joined by hyphens or slashes form one number.

    A part with letters only must be a short code ("PO", "INV"), not a word
    or a label joined to a number ("Pedido-4501", "Ref-4501").
    """
    return all(
        not part.isalpha() or (len(part) <= 4 and part.upper() not in _LABEL_PARTS)
        for part in _JOINED_SPLIT_RE.split(joined)
    )


def _written_pattern(value: str, separators: str) -> re.Pattern[str]:
    # A value followed by an underscore is the start of a longer one: the
    # first nine characters of a Paack order ID aren't a number of their own.
    gap = f"[{separators}]{{0,3}}"
    body = gap.join(re.escape(char) for char in value)
    return re.compile(rf"(?<![0-9A-Za-z]){body}(?![0-9A-Za-z_])", re.IGNORECASE)


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
        self.language = message.language or detect_language(
            f"{subject}\n{text[:KIND_BODY_CHARS]}"
        )
        body = email_body(message)
        self.links = link_entries(link.url for link in message.links)
        link_numbers = [number for _, numbers in self.links for number in numbers]
        # Tracking numbers in links and in URLs written in the text.
        self.url_numbers = {*link_numbers, *text_link_numbers(text)}
        self.number_text = "\n".join(
            [message.sender_name or "", subject, text, body, *link_numbers]
        )
        self.detector_text = f"{subject}\n{_URL_TEXT_RE.sub(' ', text)}"
        self.sender_hint = sender_carrier(message)
        self.name_carrier = self.sender_name_carrier()
        self.paack_mail = "paack" in (self.sender_hint, self.name_carrier)
        # Paack's references for the shipment (see ``paack_reference``).
        self.references: list[str] = []
        self.scan_text = (
            carrier_scan_text(self.detector_text)
            if self.sender_hint or self.name_carrier
            else self.detector_text
        )
        self.code_text = "\n".join([subject, text, body])
        # Values written as a delivery code, and the text without them; set
        # once the kind is known.
        self.code_values: set[str] = set()
        self.uncoded_text = self.number_text
        # Items are looked up in what the model read.
        self.item_text = f"{subject}\n{body}"
        self.buttons = product_buttons(message.links)
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

    def note(self, code: str) -> None:
        if code not in self.notes:
            self.notes.append(code)

    def without_cut_values(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Drop the values Ollama may have cut at their caps.

        Ollama stops each value at its cap in ``ANSWER_CAPS``, which is well
        above real values, so a value as long as its cap was cut, and a cut
        number, date or name is wrong. A cut item ends with "…", like the
        long items that ``items`` shortens.
        """
        kept = dict(data)
        for name, cap in ANSWER_CAPS.items():
            limit = cap.get("max_length")
            value = kept.get(name)
            if limit is None or value is None:
                continue
            values = []
            for entry in value if isinstance(value, list) else [value]:
                if not isinstance(entry, str) or len(entry) < limit:
                    values.append(entry)
                elif name == "items":
                    values.append(entry.rstrip() + "\u2026")
                else:
                    self.error(f"{name}_cut")
            if isinstance(value, list):
                kept[name] = values
            else:
                kept[name] = values[0] if values else None
        return kept

    def run(self) -> Validation:
        if not isinstance(self.data, Mapping):
            return Validation(None, ("not_a_mapping",))
        self.data = self.without_cut_values(self.data)
        kind = self.kind()
        if kind is None:
            return Validation(None, ("kind_invalid",))
        self.read_codes(kind)
        merchant = self.merchant()
        items = self.items()
        pickup_point = self.pickup_point(kind)
        pickup_code = self.pickup_code()
        orders = self.orders()
        carrier = self.carrier()
        merchant = self.checked_merchant(merchant, carrier)
        orders, moved = self.carrier_orders(orders, carrier)
        numbers, detected = self.tracking_numbers(carrier, orders, moved)
        strong = {number for number, _ in numbers if is_strong_number(number)}
        kept_orders = []
        for order in orders:
            if _compact(order).upper() in strong:
                self.error("order_is_tracking")
            elif self.code_only(order):
                self.error("order_is_pickup_code")
            else:
                kept_orders.append(order)
        if pickup_code and compact_code(pickup_code) in {
            *(number for number, _ in numbers),
            *(compact_code(order) for order in kept_orders),
        }:
            # A tracking or order number is never the code.
            self.error("pickup_code_is_number")
            pickup_code = None
        if pickup_code is None and kind not in _NO_CODE_KINDS:
            pickup_code = self.code_from_text(
                kind, [*(number for number, _ in numbers), *kept_orders]
            )
        reference = self.references[0] if self.references else None
        items = self.items_without_numbers(
            items,
            {
                *(number for number, _ in numbers),
                *kept_orders,
                *([pickup_code] if pickup_code else []),
                *([reference] if reference else []),
            },
        )
        eta = self.checked_eta(kind)
        kind = self.out_today(kind, eta)
        if kind is MailKind.NOT_PARCEL:
            if any(n not in detected or n in strong for n, _ in numbers):
                self.error("not_parcel_has_tracking")
            numbers = []
        elif detected:
            self.notes.append(NOTE_ADDED_BY_DETECTOR)
        order_numbers = tuple(kept_orders)
        shipments = self.shipments(
            kind,
            carrier,
            numbers,
            eta,
            pickup_point,
            pickup_code,
            order_numbers,
            items,
            reference,
        )
        grounded = kind is MailKind.NOT_PARCEL or (
            kind is not MailKind.UNKNOWN
            and (
                bool(numbers)
                or reference is not None
                or (kind is MailKind.ORDER and bool(order_numbers))
            )
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
            kind = MailKind(re.sub(r"[\s\-]+", "_", value.strip().lower()))
        except ValueError:
            return None
        if kind is MailKind.CUSTOMER_RETURN:
            # Not one of the AI's kinds: the return classifier decides it.
            kind = MailKind.RETURN
        return self.checked_kind(kind)

    def checked_kind(self, kind: MailKind) -> MailKind:
        """Return the kind the e-mail's own wording gives, if it disagrees.

        Models tend to read a later step into an e-mail: an order
        confirmation becomes "shipped", "out for delivery" becomes
        "delivered". When the parsers' keyword detector finds a kind, the
        model's kind stays only if the e-mail's wording also gives it and it
        takes precedence over the detected one; "not a parcel" and "unknown"
        always stay. A replaced kind is a note, not an error.
        """
        if kind not in KIND_PRECEDENCE:
            return kind
        subject = self.message.subject or ""
        text = self.message.text or ""
        lang = self.language
        # "On its way" fits a parcel just shipped as well as one in transit:
        # it alone doesn't decide between them.
        found = {
            detect_kind(subject, text, lang=lang)[0],
            detect_kind(subject, text, lang=lang, on_the_way=False)[0],
        }
        detected = next((k for k in KIND_PRECEDENCE if k in found), None)
        if detected is None or detected is kind:
            return kind
        supported = text_kinds(subject, text, lang=lang, on_the_way=False)
        if MailKind.SHIPPED not in supported and MailKind.SHIPPED in text_kinds(
            subject, text, lang=lang
        ):
            supported |= {MailKind.SHIPPED, MailKind.IN_TRANSIT}
        if kind in supported and (
            KIND_PRECEDENCE.index(kind) <= KIND_PRECEDENCE.index(detected)
        ):
            return kind
        self.notes.append(NOTE_KIND_FROM_TEXT)
        return detected

    def out_today(self, kind: MailKind, eta: Eta | None) -> MailKind:
        """Return in transit for "out for delivery" with a later delivery date.

        Out for delivery means today. Models also answer it for a parcel
        that reached a depot and is delivered tomorrow; with no such wording
        in the e-mail and a delivery date after the day it arrived, the
        parcel is in transit.
        """
        if (
            kind is not MailKind.OUT_FOR_DELIVERY
            or eta is None
            or eta.start <= self.reference
        ):
            return kind
        subject = self.message.subject or ""
        text = self.message.text or ""
        if MailKind.OUT_FOR_DELIVERY in text_kinds(subject, text, lang=self.language):
            return kind
        self.notes.append(NOTE_NOT_OUT_TODAY)
        return MailKind.IN_TRANSIT

    def read_codes(self, kind: MailKind) -> None:
        """Find the values the e-mail writes as a delivery or pickup code."""
        locker = kind in _LOCKER_KINDS
        self.code_values = {
            compact_code(self.number_text[start:end])
            for start, end in code_spans(self.number_text, locker=locker)
        }
        if self.code_values:
            self.uncoded_text = mask_codes(self.number_text, locker=locker)

    def code_only(self, value: str) -> bool:
        """Return True when the e-mail writes ``value`` only as a code.

        Such a value is a PIN, never a tracking or order number.
        """
        compact = compact_code(value)
        return compact in self.code_values and not _written_pattern(
            compact, r"\s\-./"
        ).search(self.uncoded_text)

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
        if brand_carriers(text):
            # A carrier isn't the merchant; the shop is named by its domain.
            return None
        return text

    def checked_merchant(self, merchant: str | None, carrier: str | None) -> str | None:
        """Drop the carrier given as the merchant; name a shop given as a domain.

        The merchant is the shop. A merchant that is this e-mail's carrier
        ("YunExpress" in YunExpress's own e-mail) is dropped, unless that
        carrier is also a shop (Amazon). A merchant written as a domain
        ("loja-exemplo.example") becomes the shop's name when the sender's
        display name or a line of the e-mail spells the domain ("Loja
        Exemplo").
        """
        if merchant is None:
            return None
        named = map_carrier(merchant)
        if (
            named is not None
            and named not in _SHOP_CARRIERS
            and named in {carrier, self.sender_hint, self.name_carrier}
        ):
            self.notes.append(NOTE_MERCHANT_IS_CARRIER)
            return None
        if _DOMAIN_RE.fullmatch(merchant) and (found := self.domain_name(merchant)):
            name, note = found
            if name != merchant:
                self.notes.append(note)
            return name
        return merchant

    def domain_name(self, domain: str) -> tuple[str, str] | None:
        """Return the shop's name as the e-mail spells ``domain``'s name.

        The sender's display name comes first ("Loja Exemplo" for
        loja-exemplo.example); otherwise a line that is only that name, such
        as the shop's signature. Returns the name and the note to add.
        """
        label = organizational_domain(domain.lower()).partition(".")[0]
        key = _alnum(label)
        name = clean_sender_name(self.message.sender_name or "")
        if name is not None and map_carrier(name) is None and _alnum(name) == key:
            return name, NOTE_MERCHANT_FROM_SENDER
        if len(key) < MIN_DOMAIN_NAME_CHARS:
            return None
        for line in (self.message.text or "").splitlines():
            line = " ".join(line.split())
            if (
                0 < len(line) <= MAX_MERCHANT_CHARS
                and _alnum(line) == key
                and map_carrier(line) is None
            ):
                return line, NOTE_MERCHANT_FROM_TEXT
        return None

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
            items.append(text)
        # Products the e-mail only lists under "Buy again" or "Recommended
        # for you" weren't ordered.
        kept = drop_recommended(items, self.item_text, buttons=self.buttons)
        if len(kept) < len(items):
            self.notes.append(NOTE_ITEM_RECOMMENDED)
        return tuple(unique_items(kept))

    def items_without_numbers(
        self, items: tuple[str, ...], numbers: set[str]
    ) -> tuple[str, ...]:
        """Drop items that are a kept tracking or order number or code."""
        compact = {compact_code(number) for number in numbers}
        kept = tuple(item for item in items if compact_code(item) not in compact)
        if len(kept) < len(items):
            self.notes.append(NOTE_ITEM_IS_NUMBER)
        return kept

    def pickup_point(self, kind: MailKind) -> str | None:
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
        if kind not in _LOCKER_KINDS and not self.written_as_pickup(text):
            # A shop's or the customer's address isn't a pickup point.
            self.notes.append(NOTE_PICKUP_POINT_DROPPED)
            return None
        if kind not in _LOCKER_KINDS and _generic_place(text):
            # "eine Filiale" where the parcel may go if nobody is home.
            self.notes.append(NOTE_PICKUP_POINT_GENERIC)
            return None
        return text

    def written_as_pickup(self, value: str) -> bool:
        """Return True when the e-mail writes ``value`` as a pickup point.

        A pickup, locker or collection word must be on the value's line or
        the line before; when the value isn't found in the e-mail, anywhere.
        """
        lines = [
            " ".join(line.split())
            for line in fold(
                f"{self.message.subject or ''}\n{self.message.text or ''}"
            ).splitlines()
        ]
        lines = [line for line in lines if line]
        head = " ".join(fold(value).split(",")[0].split())
        rows = [index for index, line in enumerate(lines) if head and head in line]
        if not rows:
            return any(_PICKUP_WORDS_RE.search(line) for line in lines)
        return any(
            _PICKUP_WORDS_RE.search(line)
            for index in rows
            for line in lines[max(0, index - 1) : index + 1]
        )

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

    def code_from_text(self, kind: MailKind, numbers: list[str]) -> str | None:
        """Return the e-mail's one delivery or pickup code, or None.

        Used when the checks leave no code: the model gave none, or one the
        e-mail doesn't write (often cut short). Values that are a kept
        tracking or order number don't count. With two or more codes,
        none is guessed.
        """
        locker = kind in _LOCKER_KINDS
        excluded = {compact_code(number) for number in numbers}
        codes = {
            compact_code(self.code_text[start:end])
            for start, end in code_spans(self.code_text, locker=locker)
        }
        if len(codes - excluded) != 1:
            return None
        code = find_code(self.code_text, exclude=numbers, locker=locker)
        match = code and _written_pattern(code, r"\s\-").search(self.code_text)
        if not match:
            return None
        self.notes.append(NOTE_CODE_FROM_TEXT)
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
                if fold(piece) in _NULL_WORDS or self.paack_reference(piece):
                    continue
                compact = _compact(piece)
                if PAACK_ID_RE.fullmatch(piece):
                    printed = self.printed_paack_id(piece)
                elif not _ORDER_RE.match(compact) or len(piece) > 60:
                    self.error("order_invalid")
                    continue
                else:
                    printed = self.printed_order(compact)
                if printed is None:
                    continue
                compact = _compact(printed)
                if compact.upper() not in seen:
                    seen.add(compact.upper())
                    orders.append(printed)
        return orders

    def printed_order(self, compact: str) -> str | None:
        """Return a model's order number as the e-mail prints it, or None.

        A number written on its own is kept. One written only as a part of
        longer numbers joined by hyphens or slashes ("4567890" in
        "PO-211-4567890") becomes the longer number when exactly one of
        them can be an order number, and is dropped otherwise. A number
        that isn't written at all may be a miscopy (see ``repaired_order``).
        """
        starts, joined = self.joined_numbers
        wholes: dict[str, str] = {}
        for match in _written_pattern(compact, r"\s\-./").finditer(self.number_text):
            index = bisect_right(starts, match.start()) - 1
            whole = joined[index] if index >= 0 else None
            if (
                whole is None
                or whole.end() < match.end()
                or whole.span() == match.span()
            ):
                return "".join(match.group(0).split())
            wholes[_compact(whole.group(0)).upper()] = whole.group(0)
        if wholes:
            tracking = self.tracking_candidates()
            numbers = [
                token
                for token in wholes.values()
                if self.order_candidate(token, tracking)
            ]
            if len(numbers) == 1:
                self.note(NOTE_ORDER_FROM_TEXT)
                return numbers[0]
            self.error("order_is_part")
            return None
        if (printed := self.repaired_order(compact)) is not None:
            self.note(NOTE_ORDER_FROM_TEXT)
            return printed
        self.error("order_not_in_email")
        return None

    def paack_reference(self, value: str) -> bool:
        """Keep a model's value that is Paack's reference for the shipment.

        Paack's e-mails call the first part of its order ID ("Wx4Hn8Tz3" in
        "Wx4Hn8Tz3_1") the order number. In Paack's own e-mail, a value of
        that shape that the e-mail writes on its own, and that looks like an
        ID, is that reference, in the e-mail's spelling: never the shop's
        order number, nor a tracking number. Returns whether it was one.
        """
        if not self.paack_mail or not PAACK_STEM_RE.fullmatch(value):
            return False
        written = _tracking_pattern(value).search(self.number_text)
        reference = _compact(written.group(0)) if written else ""
        if not PAACK_STEM_RE.fullmatch(reference) or not id_shaped(reference):
            return False
        if reference not in self.references:
            self.references.append(reference)
        return True

    def printed_paack_id(self, value: str) -> str | None:
        """Return a Paack order ID as the e-mail writes it, or None.

        The ID stays whole, in the e-mail's case: Paack's e-mail is the one
        that gives it as an order number, and there it is moved to the
        tracking numbers (see ``carrier_orders``).
        """
        written = _tracking_pattern(value).search(self.number_text)
        if written is None:
            self.error("order_not_in_email")
            return None
        return normalize_tracking_number(written.group(0))

    @cached_property
    def joined_numbers(self) -> tuple[list[int], list[re.Match[str]]]:
        """Return the numbers joined by hyphens or slashes outside links, and
        their offsets in ``number_text``."""
        text = _URL_TEXT_RE.sub(lambda url: " " * len(url.group(0)), self.number_text)
        joined = [
            match for match in _JOINED_RE.finditer(text) if _is_number(match.group(0))
        ]
        return [match.start() for match in joined], joined

    def order_candidate(self, token: str, tracking: set[str]) -> bool:
        """Return whether a number written in the e-mail can be an order number.

        Tracking numbers, dates, codes and phone or tax numbers can't.
        """
        candidate = _compact(token).upper()
        return not (
            not _ORDER_RE.match(candidate)
            or _DATE_TOKEN_RE.match(token)
            or candidate in tracking
            or is_strong_number(candidate)
            or compact_code(candidate) in self.code_values
            or _labelled(
                self.detector_text,
                _written_pattern(candidate, r"\s\-./"),
                _OTHER_NUMBER_LABEL_RE,
            )
        )

    def repaired_order(self, compact: str) -> str | None:
        """Return the e-mail's number that the model miscopied as ``compact``.

        Small models drop or change a digit when they copy a long number.
        When exactly one number in the e-mail is one character away (two
        from 12 characters on), and the e-mail doesn't give it as a tracking
        number, a code, a date or a phone or tax number, that number is used.
        """
        if len(compact) < REPAIR_MIN_CHARS:
            return None
        limit = 1 if len(compact) < REPAIR_LONG_CHARS else 2
        tracking = self.tracking_candidates()
        best: dict[str, str] = {}
        best_distance = limit + 1
        for match in _TOKEN_RE.finditer(self.detector_text):
            token = match.group(0)
            candidate = _compact(token).upper()
            if len(candidate) < REPAIR_MIN_CHARS or not self.order_candidate(
                token, tracking
            ):
                continue
            distance = _edit_distance(compact.upper(), candidate, limit)
            if distance > limit:
                continue
            if distance < best_distance:
                best_distance = distance
                best = {candidate: token}
            elif distance == best_distance:
                best[candidate] = token
        if len(best) != 1:
            return None
        return next(iter(best.values()))

    def tracking_candidates(self) -> set[str]:
        """Return the numbers the e-mail or the model give as tracking numbers."""
        numbers = {match.number for match in find_tracking_numbers(self.scan_text)}
        numbers.update(number for _, found in self.links for number in found)
        values = _as_list(self.data.get("tracking_numbers")) or []
        numbers.update(
            normalize_tracking_number(piece.rpartition(":")[2].strip().lstrip("#"))
            for value in values
            if isinstance(value, str)
            for piece in _LIST_SPLIT_RE.split(value)
        )
        return {_compact(number).upper() for number in numbers}

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

    def carrier_orders(
        self, orders: list[str], carrier: str | None
    ) -> tuple[list[str], list[str]]:
        """Move the parcel's own number out of the orders of a carrier's e-mail.

        Models read "Your parcel 123…" in a carrier's e-mail as an order
        number. A model order that the detector reads as this carrier's
        tracking number, or that a tracking link carries, is the parcel's
        number unless the e-mail labels it as an order: it is moved to the
        tracking numbers. Paack's own order ID is always moved: its e-mails
        label it as an order number. Returns the orders left and the numbers
        moved.
        """
        if carrier is None or not (self.sender_hint or self.name_carrier):
            return orders, []
        found = {
            match.number
            for match in find_tracking_numbers(self.scan_text, carrier=carrier)
        }
        found.update(number for _, numbers in self.links for number in numbers)
        kept: list[str] = []
        moved: list[str] = []
        for order in orders:
            number = normalize_tracking_number(order)
            if (
                number in found
                and _number_carrier(number, carrier)[0]
                and not self.code_only(number)
                and (
                    PAACK_ID_RE.fullmatch(number) is not None
                    or not _labelled(
                        self.detector_text, _tracking_pattern(number), _ORDER_LABEL_RE
                    )
                )
            ):
                moved.append(number)
            else:
                kept.append(order)
        if moved:
            self.notes.append(NOTE_ORDER_MOVED_TO_TRACKING)
        return kept, moved

    def tracking_numbers(
        self, carrier: str | None, orders: list[str], moved: list[str]
    ) -> tuple[list[tuple[str, str | None]], set[str]]:
        """Return the final numbers and carriers, and those only code found.

        The model's numbers count when they are written in the e-mail and
        pass the carrier's rules; the code's detector adds what it finds.
        ``moved`` holds the model's orders that are tracking numbers.
        """
        orders_compact = {_compact(order).upper() for order in orders}
        found: dict[str, str | None] = {}
        for number in [*self.ai_numbers(carrier, orders_compact), *moved]:
            if number in found:
                continue
            valid, number_carrier = _number_carrier(number, carrier)
            if not valid:
                self.error("tracking_invalid")
                continue
            reason = self.exclusion(number, orders_compact)
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
            if not valid or self.exclusion(number, orders_compact):
                continue
            found[number] = number_carrier
            detected.add(number)
        if carrier is None and None in found.values():
            self.context_carriers(found)
        return list(found.items()), detected

    def context_carriers(self, found: dict[str, str | None]) -> None:
        """Give numbers without a carrier the one carrier the e-mail names.

        A shop's e-mail often names the carrier next to a number whose format
        fits many carriers ("affidato a BRT. Numero di spedizione: …"). The
        detector reads the carrier from the number's context; that carrier is
        used only when the e-mail names no other ("GLS or SEUR" stays unknown).
        """
        named = named_carriers(self.detector_text)
        if len(named) != 1:
            return
        context = {
            match.number: match.carrier
            for match in find_tracking_numbers(self.detector_text)
            if match.carrier in named
        }
        for number, number_carrier in found.items():
            if number_carrier is None and number in context:
                found[number] = context[number]

    def ai_numbers(self, carrier: str | None, orders: set[str]) -> list[str]:
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
                if fold(piece) in _NULL_WORDS or self.paack_reference(piece):
                    continue
                number = normalize_tracking_number(piece)
                if not (_NUMBER_RE.match(number) or PAACK_ID_RE.fullmatch(number)):
                    self.error("tracking_invalid")
                    continue
                written = _tracking_pattern(number).search(self.number_text)
                if written is None:
                    repaired = self.repaired_tracking(number, carrier, orders)
                    if repaired is None:
                        self.error("tracking_not_in_email")
                        continue
                    self.note(NOTE_TRACKING_FROM_TEXT)
                    number = repaired
                elif PAACK_ID_RE.fullmatch(number):
                    # Paack's order IDs are case-sensitive: the e-mail's spelling.
                    number = normalize_tracking_number(written.group(0))
                numbers.append(number)
        return numbers

    def repaired_tracking(
        self, number: str, carrier: str | None, orders: set[str]
    ) -> str | None:
        """Return the e-mail's tracking number that the model miscopied.

        As with order numbers, a character gets changed, dropped or added,
        often when the number is only in a tracking link. When exactly one
        number in the text or in a link's tracking parameters is one
        character away, passes the carrier's format and check-digit rules,
        and isn't an order number, a code, a date or a phone or tax number,
        that number is used.
        """
        candidates = {
            _compact(match.group(0)).upper()
            for match in _TOKEN_RE.finditer(self.detector_text)
            if not _DATE_TOKEN_RE.match(match.group(0))
        }
        candidates.update(
            match.number
            for match in find_tracking_numbers(self.scan_text, carrier=carrier)
        )
        candidates.update(self.url_numbers)
        close = {
            candidate
            for candidate in candidates
            if _edit_distance(number, candidate, 1) == 1
            and _number_carrier(candidate, carrier)[0]
            and self.exclusion(candidate, orders) is None
        }
        return close.pop() if len(close) == 1 else None

    def exclusion(self, number: str, orders: set[str]) -> str | None:
        """Return why a tracking number must not be used, or None.

        UPU S10, UPS and Amazon numbers identify themselves and are kept, as
        are Paack's order IDs (valid only as Paack's numbers), which its
        e-mails label as order numbers. Others are left out when the e-mail
        writes them only as a delivery or pickup code, when they equal an
        order number, or when the e-mail labels them as an order, phone or
        tax number.
        """
        if is_strong_number(number) or PAACK_ID_RE.fullmatch(number):
            return None
        if self.code_only(number):
            return "tracking_is_pickup_code"
        if number in orders:
            return "tracking_is_order"
        pattern = _tracking_pattern(number)
        if _labelled(self.detector_text, pattern, _ORDER_LABEL_RE):
            return "tracking_is_order"
        if _labelled(self.detector_text, pattern, _OTHER_NUMBER_LABEL_RE):
            return "tracking_is_other_number"
        return None

    def checked_eta(self, kind: MailKind) -> Eta | None:
        """Return the delivery date, checked against the dates in the e-mail.

        Models take deadlines (to collect, pay, return or be refunded by),
        hold periods and replaced dates for delivery dates, and count
        business days wrongly. So:

        * kinds with no pending delivery have no delivery date;
        * the model's date stays when the e-mail writes exactly that date
          or range, and it isn't a deadline, an order or shipping date or a
          replaced date;
        * otherwise the date next to a delivery phrase, as the parsers read
          it, is used;
        * otherwise the model's date is dropped when it has passed, when the
          e-mail gives it only as one of those other dates, or when the
          e-mail mentions no date at all.
        """
        if kind in _NO_ETA_KINDS:
            if any(self.data.get(field) for field in _ETA_FIELDS):
                self.notes.append(NOTE_ETA_DROPPED_FOR_KIND)
            return None
        eta = self.eta()
        subject = self.message.subject or ""
        text = self.message.text or ""
        expressions = date_expressions(
            f"{subject}\n{text}", self.received, self.tz, self.language
        )
        candidates = {
            (found.start, found.end)
            for found in expressions
            if not (found.deadline or found.other) and found.end >= self.reference
        }
        flagged = {
            (found.start, found.end)
            for found in expressions
            if found.deadline or found.other
        } - candidates
        if eta is not None and (eta.start, eta.end) in candidates:
            return eta
        found = find_delivery_eta(
            text, self.received, self.tz, self.language
        ) or find_delivery_eta(subject, self.received, self.tz, self.language)
        if (
            found is not None
            and found.end >= self.reference
            and (found.start, found.end) not in flagged
        ):
            if eta is None or (found.start, found.end) != (eta.start, eta.end):
                self.notes.append(NOTE_ETA_FROM_TEXT)
            if eta is None or found.window_start or found.window_end:
                return found
            return Eta(found.start, found.end, eta.window_start, eta.window_end)
        if eta is None:
            return None
        if not any(
            start <= eta.end and eta.start <= end for start, end in candidates
        ) and (
            eta.end < self.reference
            or (eta.start, eta.end) in flagged
            or eta.end in {end for _, end in flagged}
        ):
            self.error("eta_not_delivery_date")
            return None
        if (
            not expressions
            and not _DATE_EVIDENCE_RE.search(fold(f"{subject}\n{text}"))
            and not (
                kind is MailKind.OUT_FOR_DELIVERY
                and eta.start == eta.end == self.reference
            )
        ):
            self.error("eta_not_in_text")
            return None
        return eta

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
        reference: str | None,
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
                reference=reference,
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
                    reference=reference,
                )
            )
        return shipments


def _compact(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", value)


def _alnum(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", fold(text))


def _generic_place(text: str) -> bool:
    """Return True when ``text`` names a kind of place, not a place.

    "eine Filiale" or "the nearest DHL Packstation" says nothing about where
    the parcel is; "Packstation 123" or "Kiosk Beispiel" does.
    """
    words = _place_words(text)
    if words in _GENERIC_PICKUP_PLACES:
        return True
    named = tuple(word for word in words if map_carrier(word, prefix=False) is None)
    return bool(named) and named in _GENERIC_PICKUP_PLACES


def _edit_distance(first: str, second: str, limit: int) -> int:
    """Return the edit distance, or ``limit + 1`` when it is larger.

    A changed, dropped or added character is one edit, and so is a swap of
    two neighbouring characters (optimal string alignment).
    """
    if abs(len(first) - len(second)) > limit:
        return limit + 1
    before: list[int] = []
    previous = list(range(len(second) + 1))
    for row, char in enumerate(first, 1):
        current = [row]
        for column, other in enumerate(second, 1):
            cost = min(
                previous[column] + 1,
                current[column - 1] + 1,
                previous[column - 1] + (char != other),
            )
            if (
                row > 1
                and column > 1
                and char == second[column - 2]
                and first[row - 2] == other
            ):
                cost = min(cost, before[column - 2] + 1)
            current.append(cost)
        if min(current) > limit:
            return limit + 1
        before, previous = previous, current
    return min(previous[-1], limit + 1)


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
