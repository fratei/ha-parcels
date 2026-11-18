"""Helpers shared by the Amazon, Shopify and Shop app parsers.

Everything here is a pure function over in-memory text. Links are only
inspected as strings: they are never fetched.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
import re
from urllib.parse import SplitResult, parse_qsl, urlsplit

from ..const import CARRIER_NAMES, MailKind
from . import tracking
from .base import Eta, Link, MailMessage, SenderVerdict
from .items import same_item
from .lang import fold_aligned
from .senders import organizational_domain

MAX_ITEMS = 10
MAX_ITEM_CHARS = 80
MAX_MERCHANT_CHARS = 60
MAX_POINT_CHARS = 80
MAX_LABEL_VALUE_CHARS = 200
MAX_UNWRAP_DEPTH = 3
MAX_QUERY_FIELDS = 100
# Status words are looked for near the top of an e-mail only.
MAX_STATUS_CHARS = 1500
MAX_EVENT_CHARS = 4000

# Typographic characters mapped one-to-one to ASCII before folding, so
# folded text stays aligned with the original.
_PUNCTUATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u2032": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u00ab": '"',
        "\u00bb": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
        "\u2007": " ",
        "\u2009": " ",
        "\u202f": " ",
    }
)
_VALUE_STRIP = " \t:-|*\u2013\u2014\u2022"


def fold_text(text: str) -> str:
    """Lowercase and strip accents, keeping one character per input character.

    Typographic quotes, dashes and spaces become their ASCII forms, so a
    match in the folded text maps back to the same offsets in ``text``.
    """
    return fold_aligned(text.translate(_PUNCTUATION))


def local_date(moment: datetime, tz: tzinfo) -> date:
    """Return the local date of a moment (naive moments are taken as UTC)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(tz).date()


def today_eta(message: MailMessage, tz: tzinfo) -> Eta:
    """Return an ETA for the day the e-mail was sent, in local time."""
    day = local_date(message.date, tz)
    return Eta(day, day)


# --- Lines and labels -------------------------------------------------------


def line_bounds(text: str, pos: int) -> tuple[int, int]:
    """Return the start and end offsets of the line that contains ``pos``."""
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return start, len(text) if end < 0 else end


def iter_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield the start offset and content of every line."""
    pos = 0
    for line in text.split("\n"):
        yield pos, line
        pos += len(line) + 1


def next_line(text: str, pos: int) -> tuple[int, int] | None:
    """Return the bounds of the first non-blank line after the one at ``pos``."""
    newline = text.find("\n", pos)
    while newline >= 0:
        start = newline + 1
        end = text.find("\n", start)
        end = len(text) if end < 0 else end
        if text[start:end].strip():
            return start, end
        newline = end if end < len(text) else -1
    return None


def previous_line(text: str, pos: int) -> tuple[int, int] | None:
    """Return the bounds of the last non-blank line before the one at ``pos``."""
    end = text.rfind("\n", 0, pos)
    while end >= 0:
        start = text.rfind("\n", 0, end) + 1
        if text[start:end].strip():
            return start, end
        end = start - 1
    return None


def _strip_value(text: str, start: int, end: int) -> tuple[int, str]:
    raw = text[start:end]
    lead = len(raw) - len(raw.lstrip(_VALUE_STRIP))
    return start + lead, raw.strip(_VALUE_STRIP)


@dataclass(frozen=True, slots=True)
class LabelValue:
    """The text that follows a label such as "Arriving:" in an e-mail."""

    label_start: int
    start: int
    value: str


def label_values(text: str, folded: str, pattern: re.Pattern[str]) -> list[LabelValue]:
    """Return the value after every match of ``pattern`` in ``folded``.

    The value is the rest of the label's line or, when the label ends its
    line, the next non-blank line. ``folded`` must be aligned with
    ``text`` (see ``fold_text``); values are read from ``text``.
    """
    found: list[LabelValue] = []
    for match in pattern.finditer(folded):
        _, end = line_bounds(folded, match.end())
        start, value = _strip_value(text, match.end(), end)
        if not value:
            following = next_line(text, end)
            if following is None:
                continue
            start, value = _strip_value(text, *following)
        if value:
            found.append(
                LabelValue(match.start(), start, value[:MAX_LABEL_VALUE_CHARS])
            )
    return found


def words_regex(words: Sequence[str], *, prefix: bool = False) -> re.Pattern[str]:
    """Compile folded words or phrases into one regex, longest first.

    Spaces in a phrase match any run of whitespace. With ``prefix`` the
    words may be followed by more letters ("entregad" matches "entregado").
    """
    parts = sorted({" ".join(word.split()) for word in words}, key=len, reverse=True)
    body = "|".join(r"\s+".join(re.escape(p) for p in part.split()) for part in parts)
    tail = "" if prefix else r"(?![a-z0-9])"
    return re.compile(rf"(?<![a-z0-9])(?:{body}){tail}")


# --- Links ------------------------------------------------------------------


def _split(url: str) -> SplitResult | None:
    try:
        return urlsplit(url)
    except ValueError:
        return None


def url_host(url: str) -> str:
    """Return the lowercased host of a URL, or "" when there is none."""
    parts = _split(url)
    if parts is None:
        return ""
    try:
        return (parts.hostname or "").rstrip(".")
    except ValueError:
        return ""


def url_org(url: str) -> str:
    """Return the organizational domain of a URL's host, or ""."""
    host = url_host(url)
    return organizational_domain(host) if host else ""


def url_path(url: str) -> str:
    """Return the path of a URL, or "" when it can't be parsed."""
    parts = _split(url)
    return parts.path if parts is not None else ""


def query_params(url: str) -> list[tuple[str, str]]:
    """Return the decoded query parameters of a URL."""
    parts = _split(url)
    if parts is None or not parts.query:
        return []
    try:
        return parse_qsl(parts.query, max_num_fields=MAX_QUERY_FIELDS)
    except ValueError:
        return []


def unwrap_url(url: str) -> list[str]:
    """Return a URL followed by the http(s) URLs nested in its query string.

    Click-tracking services wrap links as ``...?U=<encoded target>``; the
    targets are decoded from the query string, never by following a link.
    """
    urls = [url]
    pending = [url]
    for _ in range(MAX_UNWRAP_DEPTH):
        nested: list[str] = []
        for current in pending:
            for _key, value in query_params(current):
                if (
                    value.lower().startswith(("http://", "https://"))
                    and value not in urls
                ):
                    urls.append(value)
                    nested.append(value)
        if not nested:
            break
        pending = nested
    return urls


def own_https_url(url: str, message: MailMessage, verdict: SenderVerdict) -> bool:
    """Return True for an https link on the verified sender's own domain."""
    if not verdict.verified or not message.sender_domain:
        return False
    parts = _split(url)
    if (
        parts is None
        or parts.scheme.lower() != "https"
        or parts.username
        or parts.password
    ):
        return False
    host = url_host(url)
    return bool(host) and organizational_domain(host) == organizational_domain(
        message.sender_domain
    )


# --- Carriers ---------------------------------------------------------------

_CARRIER_ALIASES: dict[str, str] = {
    alias: carrier
    for alias, carrier in {
        "ctt expresso": "ctt_expresso",
        "ctt express": "ctt_expresso",
        "correos express": "correos_express",
        "deutsche post": "deutsche_post",
        "dhl paket": "dhl",
        "dhl parcel": "dhl",
        "dhl express": "dhl",
        "poste italiane": "poste_italiane",
        "royal mail": "royal_mail",
        "la poste": "la_poste",
        "mondial relay": "mondial_relay",
        "vinted go": "vinted_go",
        "amazon logistics": "amazon",
        "chronopost": "chronopost",
        "colissimo": "colissimo",
        "postnl": "postnl",
        "post nl": "postnl",
        "bpost": "bpost",
        "cainiao": "cainiao",
        "yunexpress": "yunexpress",
        "asendia": "asendia",
        "correos": "correos",
        "seur": "seur",
        "nacex": "nacex",
        "paack": "paack",
        "inpost": "inpost",
        "hermes": "hermes",
        "evri": "evri",
        "fedex": "fedex",
        "dhl": "dhl",
        "dpd": "dpd",
        "gls": "gls",
        "ups": "ups",
        "usps": "usps",
        "tnt": "tnt",
        "brt": "brt",
        "bartolini": "brt",
        "sda": "sda",
        "mrw": "mrw",
        "ctt": "ctt",
    }.items()
    if carrier in CARRIER_NAMES
}
_CARRIER_RE = words_regex(tuple(_CARRIER_ALIASES))

# Organizational domains of carrier websites.
CARRIER_HOSTS: dict[str, str] = {
    "ctt.pt": "ctt",
    "cttexpresso.pt": "ctt_expresso",
    "cttexpress.com": "ctt_expresso",
    "dpd.com": "dpd",
    "dpd.de": "dpd",
    "dpd.pt": "dpd",
    "dpd.fr": "dpd",
    "dpd.nl": "dpd",
    "dpd.be": "dpd",
    "dpd.at": "dpd",
    "dpd.co.uk": "dpd",
    "dpdgroup.com": "dpd",
    "ups.com": "ups",
    "dhl.com": "dhl",
    "dhl.de": "dhl",
    "dhlparcel.nl": "dhl",
    "dhlparcel.es": "dhl",
    "gls-group.com": "gls",
    "gls-group.eu": "gls",
    "gls-spain.es": "gls",
    "gls-italy.com": "gls",
    "gls-info.nl": "gls",
    "gls-pakete.de": "gls",
    "seur.com": "seur",
    "correos.es": "correos",
    "correosexpress.com": "correos_express",
    "mrw.es": "mrw",
    "nacex.es": "nacex",
    "nacex.com": "nacex",
    "inpost.pl": "inpost",
    "inpost.es": "inpost",
    "inpost.it": "inpost",
    "inpost.pt": "inpost",
    "inpost.eu": "inpost",
    "inpost.co.uk": "inpost",
    "fedex.com": "fedex",
    "tnt.com": "tnt",
    "postnl.nl": "postnl",
    "postnl.post": "postnl",
    "usps.com": "usps",
    "royalmail.com": "royal_mail",
    "laposte.fr": "la_poste",
    "colissimo.fr": "colissimo",
    "chronopost.fr": "chronopost",
    "deutschepost.de": "deutsche_post",
    "poste.it": "poste_italiane",
    "bpost.be": "bpost",
    "brt.it": "brt",
    "sda.it": "sda",
    "evri.com": "evri",
    "myhermes.de": "hermes",
    "hermesworld.com": "hermes",
    "mondialrelay.fr": "mondial_relay",
    "mondialrelay.es": "mondial_relay",
    "mondialrelay.com": "mondial_relay",
    "mondialrelay.pt": "mondial_relay",
    "cainiao.com": "cainiao",
    "yunexpress.com": "yunexpress",
    "asendia.com": "asendia",
}


@dataclass(frozen=True, slots=True)
class CarrierMention:
    """A carrier name found in folded text."""

    start: int
    end: int
    carrier: str


def carrier_mentions(folded: str) -> list[CarrierMention]:
    """Return every carrier name in folded text, in order."""
    return [
        CarrierMention(
            m.start(), m.end(), _CARRIER_ALIASES[" ".join(m.group(0).split())]
        )
        for m in _CARRIER_RE.finditer(folded)
    ]


def carrier_from_url(url: str) -> str | None:
    """Return the carrier whose website a URL points to."""
    return CARRIER_HOSTS.get(url_org(url))


def carrier_near(
    folded: str, mentions: Sequence[CarrierMention], pos: int, window: int
) -> str | None:
    """Return the carrier named closest before ``pos``, or later on its line.

    Names before ``pos`` count when they are on the same line or at most
    ``window`` characters away.
    """
    line_start, line_end = line_bounds(folded, pos)
    before = [m for m in mentions if m.start < pos and pos - m.start <= window]
    before += [m for m in mentions if line_start <= m.start < pos]
    if before:
        return max(before, key=lambda m: m.start).carrier
    after = [m for m in mentions if pos <= m.start < line_end]
    return after[0].carrier if after else None


@dataclass(frozen=True, slots=True)
class FoundNumber:
    """A tracking number with the carrier it validates for."""

    carrier: str
    number: str
    named: bool


_TOKEN_RE = re.compile(r"[0-9A-Za-z]{8,35}")
_STRONG_TRACKING_RE = words_regex(
    (
        "tracking",
        "track",
        "seguimento",
        "rastreio",
        "seguimiento",
        "localizador",
        "sendungsnummer",
        "trackingnummer",
        "suivi",
        "tracciamento",
        "tracking number",
        "volgnummer",
        "track & trace",
        "track and trace",
        "waybill",
    ),
    prefix=True,
)


def _position(text: str, number: str) -> int:
    match = re.search(
        rf"(?<![0-9A-Za-z]){re.escape(number)}(?![0-9A-Za-z])", text, re.IGNORECASE
    )
    return match.start() if match else -1


def _link_numbers(links: Sequence[Link]) -> list[tuple[str, str]]:
    """Return (carrier, candidate number) pairs from links to carrier websites."""
    found: list[tuple[str, str]] = []
    for link in links:
        for url in unwrap_url(link.url):
            carrier = carrier_from_url(url)
            if carrier is None:
                continue
            values = [link.text, url_path(url).replace("/", " ")]
            values += [value for _key, value in query_params(url)]
            for value in values:
                for token in _TOKEN_RE.findall(value):
                    found.append((carrier, tracking.normalize_tracking_number(token)))
    return found


def find_numbers(
    text: str,
    folded: str,
    links: Sequence[Link],
    *,
    exclude: frozenset[str] = frozenset(),
    window: int = 100,
    allow_other: bool = True,
) -> list[FoundNumber]:
    """Find tracking numbers and the carrier each one validates for.

    The carrier is the one named next to the number, else the carrier of
    a link that contains it, else the one its format identifies. Numbers
    that validate for none of them are dropped. With ``allow_other``, a
    number on a line with a tracking label and no known carrier is kept
    with the carrier "other".
    """
    mentions = carrier_mentions(folded)
    hosted: dict[str, str] = {}
    for carrier, number in _link_numbers(links):
        if tracking.validate_tracking_number(number, carrier):
            hosted.setdefault(number, carrier)
    candidates = [m.number for m in tracking.find_tracking_numbers(text)]
    candidates += [n for n in hosted if n not in candidates]
    found: list[FoundNumber] = []
    for number in candidates:
        if number in exclude or any(f.number == number for f in found):
            continue
        pos = _position(text, number)
        named = carrier_near(folded, mentions, pos, window) if pos >= 0 else None
        choice: FoundNumber | None = None
        if named and tracking.validate_tracking_number(number, named):
            choice = FoundNumber(named, number, True)
        elif (host := hosted.get(number)) is not None:
            choice = FoundNumber(host, number, True)
        elif (detected := tracking.detect_carrier(number)) is not None:
            choice = FoundNumber(detected, number, False)
        elif (
            allow_other
            and named is None
            and pos >= 0
            and tracking.validate_tracking_number(number, "other")
        ):
            line_start, _ = line_bounds(folded, pos)
            if _STRONG_TRACKING_RE.search(folded, line_start, pos):
                choice = FoundNumber("other", number, False)
        if choice is not None:
            found.append(choice)
    return found


# --- Items and names --------------------------------------------------------

_PRICE_RE = re.compile(
    r"^(?:[\u20ac$\u00a3]|eur|usd|gbp)?\s*\d[\d.,\s]*(?:[\u20ac$\u00a3]|eur|usd|gbp)?$",
    re.IGNORECASE,
)
_ELLIPSIS_RE = re.compile(r"(?:\.{3}|\u2026)$")


def clean_item(text: str) -> str | None:
    """Return a short product title, or None when ``text`` isn't one."""
    title = " ".join(text.split()).strip(" -|*:,;\u2013\u2014\u2022\u00b7\"'")
    title = _ELLIPSIS_RE.sub("", title).rstrip(" ,;:-")
    if len(title) < 3 or not any(c.isalpha() for c in title) or _PRICE_RE.match(title):
        return None
    if len(title) > MAX_ITEM_CHARS:
        cut = title[:MAX_ITEM_CHARS]
        space = cut.rfind(" ")
        title = (cut[:space] if space >= MAX_ITEM_CHARS // 2 else cut).rstrip(" ,;:-(")
    return title


def add_item(items: list[str], text: str) -> None:
    """Append a cleaned title unless the list has it already or is full.

    A title that is the same item as one in the list (``same_item``: equal
    words, or one cut short of the other) replaces it when it's longer.
    """
    if (title := clean_item(text)) is None:
        return
    for index, item in enumerate(items):
        if same_item(item, title):
            if len(title) > len(item):
                items[index] = title
            return
    if len(items) < MAX_ITEMS:
        items.append(title)


_QUANTITY_RE = re.compile(
    r"(?<![a-z])(?:quantity|qty|quantidade|qtd|cantidad|cant|menge|anzahl"
    r"|quantite|qte|quantita|qta|aantal)\.?\s*:\s*\d"
)


def quantity_items(text: str, folded: str, items: list[str]) -> None:
    """Add the titles written next to "Quantity: 1" labels to ``items``.

    The title is the text before the label on its line or, when there is
    none, the previous non-blank line.
    """
    for match in _QUANTITY_RE.finditer(folded):
        start, _ = line_bounds(text, match.start())
        title = clean_item(text[start : match.start()])
        if title is None and (previous := previous_line(text, match.start())):
            title = clean_item(text[previous[0] : previous[1]])
        if title is not None:
            add_item(items, title)


# --- Pickup -----------------------------------------------------------------

_PICKUP_POINT_RE = re.compile(
    r"(?<![a-z0-9])(?:pick\s?-?up\s+(?:location|point|address)|collection\s+point"
    r"|local\s+de\s+(?:levantamento|recolha)|ponto\s+de\s+(?:levantamento|recolha)"
    r"|punto\s+de\s+recogida|lugar\s+de\s+recogida|abholort|abholstation"
    r"|abholadresse|point\s+de\s+retrait|lieu\s+de\s+retrait|punto\s+di\s+ritiro"
    r"|luogo\s+di\s+ritiro|ophaalpunt|ophaallocatie|afhaalpunt)(?![a-z0-9])\s*:?"
)


def pickup_point(text: str, folded: str) -> str | None:
    """Return the pickup point written after its label.

    Pickup and delivery codes are read by ``codes.find_code``.
    """
    for value in label_values(text, folded, _PICKUP_POINT_RE):
        if candidate := clip(value.value, MAX_POINT_CHARS).rstrip("."):
            return candidate
    return None


# --- Kinds ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KindPattern:
    """A regex over folded text that identifies an e-mail kind in a language."""

    kind: MailKind
    lang: str
    regex: re.Pattern[str]


def kind_table(kind: MailKind, **by_lang: str) -> tuple[KindPattern, ...]:
    """Compile one whole-word pattern per language for a kind."""
    return tuple(
        KindPattern(kind, lang, re.compile(rf"(?<![a-z0-9])(?:{body})(?![a-z0-9])"))
        for lang, body in by_lang.items()
    )


def detect_kind(
    subject: str,
    folded: str,
    subject_patterns: Sequence[KindPattern],
    body_patterns: Sequence[KindPattern],
) -> tuple[KindPattern | None, bool]:
    """Return the kind pattern that matched and whether it was in the subject.

    Subject patterns are tried in order of precedence; when none matches,
    the body pattern that matches earliest near the top of the e-mail wins.
    """
    for pattern in subject_patterns:
        if pattern.regex.search(subject):
            return pattern, True
    head = folded[:MAX_STATUS_CHARS]
    best: tuple[int, KindPattern] | None = None
    for pattern in body_patterns:
        match = pattern.regex.search(head)
        if match is not None and (best is None or match.start() < best[0]):
            best = (match.start(), pattern)
    return (best[1], False) if best is not None else (None, False)


_GENERIC_NAMES = frozenset(
    {
        "customer service",
        "info",
        "mailer",
        "no reply",
        "no-reply",
        "noreply",
        "notification",
        "notifications",
        "order",
        "orders",
        "shop",
        "shopify",
        "store",
        "support",
    }
)


def clean_name(name: str) -> str | None:
    """Return a short merchant name, or None for empty or generic names."""
    value = " ".join(name.split()).strip(" \"'<>")
    if not value or "@" in value or fold_text(value) in _GENERIC_NAMES:
        return None
    return value[:MAX_MERCHANT_CHARS].rstrip()


def clip(text: str, limit: int) -> str:
    """Collapse whitespace and cut text to at most ``limit`` characters."""
    return " ".join(text.split())[:limit].rstrip(" ,;:-")


# --- Event times ------------------------------------------------------------

_TIME_RE = re.compile(
    r"(?<![\d:.,])(?P<h>2[0-3]|[01]?\d)"
    r"(?:[:h](?P<m>[0-5]\d)|(?P<hh>h)(?![a-z0-9]))?"
    r"(?:\s?(?P<ampm>[ap])\.?\s?m\b\.?)?"
    r"(?![\d:])"
)
# A deadline right before a time ("until 20:00", "hasta las 20:00").
_UNTIL_RE = re.compile(
    r"(?<![a-z])(?:until|till|by|before|ate|antes|hasta|bis|vor|jusqu'?a?|avant|"
    r"fino|entro|prima|tot|voor|uiterlijk)"
    r"\s+(?:(?:as|das|las|les|le|la|alle|ore|om|at|the|um|a|de|del)\s+)?$"
)
_YESTERDAY_RE = re.compile(
    r"(?<![a-z])(?:yesterday|ontem|ayer|gestern|hier|ieri|gisteren)(?![a-z])"
)
_EVENT_RES: dict[MailKind, re.Pattern[str]] = {
    MailKind.DELIVERED: words_regex(
        (
            "delivered",
            "entregue",
            "entregad",
            "zugestellt",
            "geliefert",
            "livre",
            "consegnat",
            "bezorgd",
            "afgeleverd",
            "geleverd",
        ),
        prefix=True,
    ),
    MailKind.ATTEMPTED: words_regex(
        (
            "attempt",
            "tried",
            "missed",
            "tentativa",
            "tentamos",
            "intent",
            "versucht",
            "zustellversuch",
            "tente",
            "tentative",
            "tentat",
            "tentativo",
            "geprobeerd",
            "bezorgpoging",
        ),
        prefix=True,
    ),
    MailKind.READY_FOR_PICKUP: words_regex(
        (
            "ready",
            "available",
            "pront",
            "disponivel",
            "listo",
            "lista",
            "disponible",
            "abholbereit",
            "bereit",
            "pret",
            "disponibile",
            "klaar",
            "beschikbaar",
        ),
        prefix=True,
    ),
}
_EVENT_DISTANCE = 80
_FUTURE_SLACK = timedelta(minutes=5)
_MAX_EVENT_AGE = timedelta(days=3)


def _clock(match: re.Match[str]) -> time | None:
    hour = int(match.group("h"))
    minute = int(match.group("m") or 0)
    if (ampm := match.group("ampm")) is not None:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if ampm == "p" else 0)
    return time(hour, minute)


def event_time(
    folded: str,
    kind: MailKind,
    message: MailMessage,
    tz: tzinfo,
    lang: str | None,
) -> datetime | None:
    """Return when a delivery event happened, if the e-mail says so.

    Looks for a clock time on the same line as an event word ("Delivered
    today at 10:42", "ieri alle 18:20"). Times that would be after the
    e-mail was sent, or more than three days before it, are ignored.
    """
    words = _EVENT_RES.get(kind)
    if words is None:
        return None
    sent = message.date if message.date.tzinfo else message.date.replace(tzinfo=UTC)
    day = local_date(sent, tz)
    for _, line in iter_lines(folded[:MAX_EVENT_CHARS]):
        word = words.search(line)
        if word is None:
            continue
        for match in _TIME_RE.finditer(line):
            if not (match.group("m") or match.group("hh") or match.group("ampm")):
                continue
            if abs(match.start() - word.start()) > _EVENT_DISTANCE:
                continue
            if _UNTIL_RE.search(line[: match.start()]):
                continue
            clock = _clock(match)
            if clock is None:
                continue
            yesterday = any(
                m.group(0) != "hier" or lang != "nl"
                for m in _YESTERDAY_RE.finditer(line)
            )
            when = datetime.combine(
                day - timedelta(days=1) if yesterday else day, clock, tzinfo=tz
            )
            if sent - _MAX_EVENT_AGE <= when <= sent + _FUTURE_SLACK:
                return when
    return None
