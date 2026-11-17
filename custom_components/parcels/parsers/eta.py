"""Delivery dates, date ranges and time windows in seven languages.

Dates are always local dates in the given time zone. The reference date is
the e-mail's Date header converted to that zone: weekdays and relative days
count from it, and dates without a year get the year that puts them nearest
to it (from a week before it onwards).

Everything is matched on folded text (lowercase, no accents; see
``lang.fold_aligned``), which keeps positions aligned with the original.
"""

from __future__ import annotations

from collections.abc import Iterable
import contextlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
import re

from .base import Eta
from .lang import (
    DAY_AFTER_TOMORROW,
    MONTHS,
    MONTHS_BY_LANG,
    TODAY,
    TOMORROW,
    WEEKDAY_ABBREVIATIONS,
    WEEKDAYS,
    fold_aligned,
)

MAX_PARSE_CHARS = 2000
MAX_FIND_CHARS = 100_000
MAX_CALENDAR_DAYS = 21
MAX_BUSINESS_DAYS = 20

# Phrases that introduce a delivery date. Strong anchors may be followed by
# a few words before the date; weak anchors only by very few.
STRONG_ANCHORS: tuple[str, ...] = (
    # English
    "arriving",
    "arrives",
    "arrive",
    "will arrive",
    "should arrive",
    "expected to arrive",
    "estimated to arrive",
    "estimated delivery",
    "estimated delivery date",
    "estimated arrival",
    "expected delivery",
    "expected delivery date",
    "expected arrival",
    "arrival date",
    "delivery date",
    "delivery estimate",
    "delivery expected",
    "delivery is expected",
    "delivery window",
    "delivery day",
    "scheduled delivery",
    "scheduled for delivery",
    "scheduled to be delivered",
    "planned delivery",
    "new delivery date",
    "will be delivered",
    "should be delivered",
    "to be delivered",
    "delivered on",
    "get it",
    "be with you",
    "eta",
    # Portuguese
    "entrega prevista",
    "entrega estimada",
    "entrega agendada",
    "entrega programada",
    "data de entrega",
    "data prevista",
    "data prevista de entrega",
    "data estimada",
    "data estimada de entrega",
    "previsao de entrega",
    "estimativa de entrega",
    "prazo de entrega",
    "chegada prevista",
    "chegada estimada",
    "chega",
    "chegara",
    "vai chegar",
    "deve chegar",
    "devera chegar",
    "sera entregue",
    "vai ser entregue",
    "entregue em",
    "prevista para",
    "previsto para",
    # Spanish
    "llegada",
    "llegada prevista",
    "llegada estimada",
    "llega",
    "llegara",
    "entrega estimada",
    "fecha de entrega",
    "fecha estimada",
    "fecha prevista",
    "fecha estimada de entrega",
    "fecha prevista de entrega",
    "plazo de entrega",
    "sera entregado",
    "sera entregada",
    "se entregara",
    "entregado el",
    "recibiras",
    "lo recibiras",
    # German
    "voraussichtliche zustellung",
    "voraussichtliche lieferung",
    "voraussichtliche ankunft",
    "voraussichtlicher liefertermin",
    "voraussichtlicher zustelltermin",
    "voraussichtliches lieferdatum",
    "voraussichtliches zustelldatum",
    "voraussichtlich",
    "lieferdatum",
    "liefertermin",
    "zustelltermin",
    "zustelldatum",
    "zustellfenster",
    "zustellung am",
    "lieferung am",
    "zugestellt am",
    "geplante zustellung",
    "erwartete lieferung",
    "erwartete zustellung",
    "wird zugestellt",
    "wird geliefert",
    "kommt",
    "ankunft",
    # French
    "livraison prevue",
    "livraison estimee",
    "livraison le",
    "date de livraison",
    "date de livraison prevue",
    "date de livraison estimee",
    "date estimee",
    "date prevue",
    "creneau de livraison",
    "arrivera",
    "sera livre",
    "sera livree",
    "seront livres",
    "livre le",
    "livree le",
    "prevue le",
    "prevu le",
    "chez vous",
    # Italian
    "consegna prevista",
    "consegna stimata",
    "consegna entro",
    "consegna il",
    "data di consegna",
    "data di consegna prevista",
    "data prevista di consegna",
    "arriva",
    "arrivera",
    "sara consegnato",
    "sara consegnata",
    "verra consegnato",
    "verra consegnata",
    "consegnato il",
    "consegnata il",
    "fascia oraria",
    # Dutch
    "verwachte bezorging",
    "verwachte levering",
    "verwachte bezorgdatum",
    "verwachte leverdatum",
    "verwachte aankomst",
    "bezorgdatum",
    "leverdatum",
    "bezorgmoment",
    "bezorgd op",
    "geleverd op",
    "bezorging op",
    "levering op",
    "verwacht op",
    "wordt bezorgd",
    "wordt geleverd",
    "komt aan",
    "tijdvak",
)
WEAK_ANCHORS: tuple[str, ...] = (
    "delivery",
    "delivered",
    "arrival",
    "expected",
    "entrega",
    "chegada",
    "entregue",
    "entregado",
    "lieferung",
    "zustellung",
    "geliefert",
    "zugestellt",
    "livraison",
    "consegna",
    "consegnato",
    "levering",
    "bezorging",
    "bezorgd",
    "geleverd",
    "verwacht",
    "komt",
    "bezorgen",
    "liefern",
)
STRONG_MAX_GAP_WORDS = 8
WEAK_MAX_GAP_WORDS = 3
VERB_FINAL_AUXILIARIES: tuple[str, ...] = ("wird", "werden", "wordt", "worden")
VERB_FINAL_PARTICIPLES: tuple[str, ...] = (
    "zugestellt",
    "geliefert",
    "ausgeliefert",
    "bezorgd",
    "geleverd",
    "afgeleverd",
)

# Between an anchor and a date, these mean the date is about something else
# (when the order was placed or shipped, an offer, a return deadline).
OTHER_DATE_PHRASES: tuple[str, ...] = (
    "order date",
    "ordered on",
    "order placed",
    "placed on",
    "purchase date",
    "invoice date",
    "shipped on",
    "dispatched on",
    "sent on",
    "valid until",
    "return",
    "returns",
    "data da encomenda",
    "data do pedido",
    "encomenda efetuada",
    "encomenda feita",
    "pedido efetuado",
    "enviado em",
    "enviada em",
    "expedido em",
    "expedida em",
    "valido ate",
    "devolucao",
    "devolucoes",
    "fecha del pedido",
    "fecha de pedido",
    "pedido realizado",
    "realizado el",
    "enviado el",
    "enviada el",
    "valido hasta",
    "devolucion",
    "devoluciones",
    "bestellt am",
    "bestelldatum",
    "bestellung vom",
    "versandt am",
    "verschickt am",
    "rechnungsdatum",
    "gultig bis",
    "rucksendung",
    "retoure",
    "date de commande",
    "commande du",
    "commande passee",
    "passee le",
    "expedie le",
    "expediee le",
    "envoye le",
    "envoyee le",
    "valable jusqu",
    "retour",
    "retours",
    "data dell'ordine",
    "data ordine",
    "ordine del",
    "effettuato il",
    "spedito il",
    "spedita il",
    "valido fino",
    "reso",
    "resi",
    "besteldatum",
    "besteld op",
    "verzonden op",
    "verstuurd op",
    "geldig tot",
    "retourneren",
    # Deadlines: "the offer expires on 30/11".
    "expires",
    "expire",
    "expira",
    "caduca",
    "lauft ab",
    "ablauf",
    "scade",
    "vervalt",
    "vervallen",
    "verloopt",
    # Offers: "free delivery on orders until 30/11".
    "orders",
    "encomendas",
    "pedidos",
    "bestellungen",
    "commandes",
    "ordini",
    "bestellingen",
    "offer",
    "oferta",
    "angebot",
    "offre",
    "offerta",
    "aanbieding",
    "promo",
    "promocao",
    "promocion",
    "promozione",
    "aktion",
    "valid",
    "valida",
    "valido",
    "gultig",
    "valable",
    "geldig",
)
# Anchors next to these words advertise free delivery; they carry no ETA.
_FREE_WORDS = frozenset(
    {
        "free",
        "gratis",
        "gratuita",
        "gratuito",
        "gratuite",
        "gratuit",
        "kostenlos",
        "kostenlose",
        "kostenloser",
        "kostenlosen",
    }
)
# A negation right before an anchor means the date is not the delivery date
# ("will not arrive today", "nao chega hoje", "n'arrivera pas demain").
_NEGATIONS = frozenset(
    {
        "not",
        "won't",
        "wont",
        "never",
        "nao",
        "nunca",
        "nicht",
        "nie",
        "niet",
        "nooit",
        "non",
        "n'",
        "jamais",
    }
)
# Spanish "no" is also Portuguese "in the", so it only counts right before.
_NEGATION_RIGHT_BEFORE = frozenset({"no"})
_NEGATION_SCOPE_RE = re.compile(r"[.!?;:\n]")
_NOON_RE = re.compile(
    r"(?<![a-z0-9:])(?<!apres-)(?<!apres )(?:12\s*)?"
    r"(?:noon|midday|meio[-\s]dia|mediodia|mittag|midi|mezzogiorno)(?![a-z])"
)


def _alternation(words: Iterable[str]) -> str:
    """Build a regex alternation, longest first; spaces match any whitespace."""
    patterns = {
        re.escape(word).replace(r"\ ", r"\s+").replace(r"\-", r"[-\s]?")
        for word in words
    }
    return "|".join(sorted(patterns, key=len, reverse=True))


_MONTH = _alternation(MONTHS)
_MONTH_EN = _alternation(MONTHS_BY_LANG["en"])
_WEEKDAY = _alternation(WEEKDAYS)
_WEEKDAY_ABBR = _alternation(WEEKDAY_ABBREVIATIONS)
_ORDINAL = r"(?:st|nd|rd|th|er|o)?"
_YEAR = r"(?P<y>(?:19|20)\d{2})(?![\d:])"
_SEP_WORDS = (
    "to|till|until|through|thru|and|a|ao|as|al|e|y|et|au|bis|und|zum|"
    r"tot\s+en\s+met|tot|en|t/m|or|ou|oder|o|of|ate|hasta|fino\s+al"
)
_ARTICLES = r"(?:the|le|el|il|o|a|dem|den|la|het)"

_DM_RE = re.compile(
    rf"(?<![a-z0-9])(?<!\d[.,:/])(?P<d>[0-3]?\d){_ORDINAL}\.?\s*(?:(?:de|of|del)\s+)?"
    rf"(?P<m>{_MONTH})(?![a-z])(?!\s*of(?![a-z]))\.?"
    rf"(?:\s*,?\s*(?:(?:de|del)\s+)?{_YEAR})?"
)
_MD_RE = re.compile(
    rf"(?<![a-z0-9])(?P<m>{_MONTH_EN})(?![a-z])\.?\s*(?P<d>[0-3]?\d)"
    rf"(?:st|nd|rd|th)?(?!\d)(?![.:]\d)(?:\s*,?\s*{_YEAR})?"
)
_ISO_RE = re.compile(
    r"(?<![\d/.:-])(?P<y>(?:19|20)\d{2})-(?P<m>[01]?\d)-(?P<d>[0-3]?\d)(?!\d)"
)
_NUM_YEAR_RE = re.compile(
    r"(?<![\d/.,:-])(?P<d>[0-3]?\d)(?P<s>[/.-])(?P<m>[01]?\d)(?P=s)"
    r"(?P<y>(?:19|20)\d{2}|\d{2})(?!\d)(?![/.-]\d)"
)
_NUM_SLASH_RE = re.compile(r"(?<![\d/.,:-])(?P<d>[0-3]?\d)/(?P<m>[01]?\d)(?![\d/])")
_NUM_DOT_RE = re.compile(r"(?<![\d/.,:-])(?P<d>[0-3]?\d)\.(?P<m>[01]?\d)\.(?!\d)")
_WEEKDAY_RE = re.compile(rf"(?<![a-z])(?P<wd>{_WEEKDAY})(?![a-z])")
_WEEKDAY_PREFIX_RE = re.compile(
    rf"(?<![a-z])(?:(?P<wd>{_WEEKDAY})|(?P<wda>{_WEEKDAY_ABBR})\.?)\s*,?\s*"
    r"(?:(?:den|the|le|el|il|dia)\s+)?\Z"
)

_RELATIVE: dict[str, int] = {
    **dict.fromkeys(TODAY, 0),
    **dict.fromkeys(TOMORROW, 1),
    **dict.fromkeys(DAY_AFTER_TOMORROW, 2),
}
_RELATIVE_KEYS: dict[str, int] = {" ".join(k.split()): v for k, v in _RELATIVE.items()}
_RELATIVE_RE = re.compile(rf"(?<![a-z])(?P<rel>{_alternation(_RELATIVE)})(?![a-z])")

_WITHIN_WORDS = (
    "within",
    "em ate",
    "ate",
    "no maximo em",
    "dentro de",
    "en un plazo de",
    "en un maximo de",
    "en menos de",
    "innerhalb von",
    "innerhalb",
    "binnen",
    "sous",
    "d'ici",
    "entro",
    "nel giro di",
    "in meno di",
)
_IN_WORDS = ("in", "em", "en", "dans", "tra", "fra", "over", "nach")
_BUSINESS_UNITS = (
    r"business\s+days?|working\s+days?|dias?\s+uteis|dia\s+util|"
    r"dias?\s+laborables?|dias?\s+habiles|dia\s+habil|werktagen?|arbeitstagen?|"
    r"jours?\s+ouvr(?:es|ables?|e)|giorni\s+lavorativi|giorno\s+lavorativo|"
    r"giorni\s+feriali|werkdagen|werkdag"
)
_CALENDAR_UNITS = r"days?|dias?|tagen?|jours?|giorni|giorno|dagen|dag"
_SPAN_RE = re.compile(
    rf"(?<![a-z0-9])(?:(?P<within>{_alternation(_WITHIN_WORDS)})\s+"
    rf"|(?:{_alternation(_IN_WORDS)})\s+)?"
    r"(?P<a>\d{1,2})(?:(?:\s*[-~]\s*|\s+(?:a|to|or|ou|o|e|y|et|bis|und|oder|tot|en"
    r"|of|al)\s+)(?P<b>\d{1,2}))?\s*"
    rf"(?:(?P<bd>{_BUSINESS_UNITS})|(?P<cd>{_CALENDAR_UNITS}))(?![a-z])"
)

_RANGE_SEP_RE = re.compile(
    rf"\s*(?:[-~]|(?<![a-z])(?:{_SEP_WORDS})(?![a-z]))\s*(?:{_ARTICLES}\s+)?"
)
_DAY_BEFORE_RE = re.compile(
    rf"(?<![a-z0-9.,:/])(?P<d>[0-3]?\d){_ORDINAL}\.?\s*"
    rf"(?:[-~]|(?<![a-z])(?:{_SEP_WORDS}))\s*(?:{_ARTICLES}\s+)?\Z"
)
_DAY_AFTER_RE = re.compile(
    r"\s*(?:[-~]|(?:to|till|until|through|thru|and)(?![a-z]))\s*(?:the\s+)?"
    rf"(?P<d>[0-3]?\d)(?:st|nd|rd|th)?(?![\d:./a-z])(?:\s*,?\s*{_YEAR})?"
)
_WEEKDAY_DAY_RE = re.compile(
    rf"\s*,?\s*(?:(?:dia|den|the|le|el|il)\s+)?(?P<d>[0-3]?\d){_ORDINAL}\.?"
    r"(?![\d:./])(?!\s*(?:h|uhr|am|pm|a\.m|p\.m)(?![a-z]))"
)

# Portuguese weekdays without "-feira" are also ordinary words
# ("segunda tentativa" is a second attempt, "Quinta do Lago" a place).
_PT_SHORT_WEEKDAYS = frozenset({"segunda", "terca", "quarta", "quinta", "sexta"})
_PT_NOT_WEEKDAY_BEFORE = frozenset(
    {"a", "da", "uma", "pela", "sua", "nossa", "vossa", "tua", "rua"}
)
_PT_NOT_WEEKDAY_AFTER = frozenset(
    {
        "tentativa",
        "vez",
        "via",
        "parte",
        "edicao",
        "geracao",
        "classe",
        "mao",
        "opcao",
        "entrega",
        "encomenda",
        "fase",
        "etapa",
        "linha",
        "chamada",
        "notificacao",
        "volta",
        "do",
        "da",
        "dos",
        "das",
        "de",
    }
)
# "manana" is also "morning" (la manana) and "morgen" is "morning" in
# "am Morgen", "heute Morgen", "de morgen".
_MORNING_BEFORE = frozenset(
    {
        "la",
        "esta",
        "cada",
        "toda",
        "una",
        "media",
        "am",
        "heute",
        "gestern",
        "guten",
        "jeden",
        "den",
        "diesen",
        "vom",
        "zum",
        "der",
        "des",
        "dem",
        "ein",
        "einen",
        "de",
        "deze",
        "goede",
        "elke",
        "van",
    }
)
_SENTENCE_START = frozenset(".!?:;-(\n\"'*•")

_PUNCTUATION = str.maketrans(
    dict.fromkeys("\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d", "-")
    | dict.fromkeys("\u2018\u2019\u201b\u02bc\u2032", "'")
)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+")
_WORD_RE = re.compile(r"[a-z0-9']+")

_STRONG_RE = re.compile(rf"(?<![a-z])(?:{_alternation(STRONG_ANCHORS)})(?![a-z])")
_WEAK_RE = re.compile(rf"(?<![a-z])(?:{_alternation(WEAK_ANCHORS)})(?![a-z])")
_OTHER_DATE_RE = re.compile(
    rf"(?<![a-z])(?:{_alternation(OTHER_DATE_PHRASES)})(?![a-z])"
)
# German and Dutch put the participle last ("wird morgen zugestellt", "wordt
# donderdag bezorgd"), so the auxiliary is the anchor when one follows.
_VERB_FINAL_RE = re.compile(
    rf"(?<![a-z])(?:{_alternation(VERB_FINAL_AUXILIARIES)})(?![a-z])"
    r"(?=(?:(?!(?<![a-z])(?:nicht|kein|keine|niet|geen)(?![a-z]))[^\n!?]){0,120}?"
    rf"(?<![a-z])(?:{_alternation(VERB_FINAL_PARTICIPLES)})(?![a-z]))"
)


@dataclass(slots=True)
class _Atom:
    """One date expression found in folded text."""

    start: int
    end: int
    kind: str  # "date", "weekday", "relative" or "span"
    day: int = 0
    month: int = 0
    year: int | None = None
    weekday: int | None = None
    offset: int = 0
    low: int = 0
    high: int = 0
    business: bool = False
    within: bool = False
    month_first: bool = False
    named_month: bool = False


def _reference_date(reference: datetime, tz: tzinfo) -> date:
    """Return the local date of the e-mail (naive datetimes are UTC)."""
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    return reference.astimezone(tz).date()


def _prepare(text: str) -> str:
    """Fold text, unify dashes and apostrophes and blank out URLs."""
    folded = fold_aligned(text).translate(_PUNCTUATION)
    return _URL_RE.sub(lambda m: " " * len(m.group(0)), folded)


def _previous_word(s: str, pos: int) -> str:
    words = _WORD_RE.findall(s[max(0, pos - 30) : pos])
    return words[-1] if words else ""


def _negated(s: str, pos: int) -> bool:
    """Return True when a negation precedes the anchor at ``pos``."""
    clause = _NEGATION_SCOPE_RE.split(s[max(0, pos - 40) : pos])[-1]
    words = _WORD_RE.findall(clause)[-2:]
    if not words:
        return False
    return words[-1] in _NEGATION_RIGHT_BEFORE or any(w in _NEGATIONS for w in words)


def _next_word(s: str, pos: int) -> str:
    match = _WORD_RE.search(s, pos, min(len(s), pos + 30))
    return match.group(0) if match else ""


def _year(value: str | None) -> int | None:
    if not value:
        return None
    year = int(value)
    return year + 2000 if year < 100 else year


def _with_weekday_prefix(s: str, atom: _Atom) -> _Atom:
    """Extend a date atom over a weekday in front of it ("Tue, 18 Nov")."""
    match = _WEEKDAY_PREFIX_RE.search(s, max(0, atom.start - 40), atom.start)
    if match:
        name = " ".join((match.group("wd") or match.group("wda")).split())
        name = name.replace(" ", "-") if name not in WEEKDAYS else name
        atom.weekday = WEEKDAYS.get(name, WEEKDAY_ABBREVIATIONS.get(name))
        if atom.weekday is None:
            atom.weekday = _weekday_index(match.group("wd") or match.group("wda"))
        atom.start = match.start()
    return atom


def _weekday_index(name: str) -> int | None:
    """Return the weekday of a folded name or abbreviation."""
    key = " ".join(name.split())
    for candidate in (key, key.replace(" ", "-"), key.replace("-", " ")):
        if candidate in WEEKDAYS:
            return WEEKDAYS[candidate]
        if candidate in WEEKDAY_ABBREVIATIONS:
            return WEEKDAY_ABBREVIATIONS[candidate]
    return None


def _date_atom(
    match: re.Match[str], s: str, *, month_first: bool = False, named: bool = False
) -> _Atom | None:
    day = int(match.group("d"))
    month_text = match.group("m")
    month = MONTHS[month_text] if named else int(month_text)
    groups = match.groupdict()
    year = _year(groups.get("y"))
    if not named and month > 12 >= day and "s" in groups:
        # Month-first (US style) when day-first is impossible.
        day, month = month, day
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return None
    atom = _Atom(
        match.start(),
        match.end(),
        "date",
        day=day,
        month=month,
        year=year,
        month_first=month_first,
        named_month=named,
    )
    return _with_weekday_prefix(s, atom)


def _find_atoms(
    s: str, text: str, start: int, end: int, lang: str | None
) -> list[_Atom]:
    """Find non-overlapping date expressions in ``s[start:end]``."""
    found: list[_Atom] = []
    for match in _DM_RE.finditer(s, start, end):
        if atom := _date_atom(match, s, named=True):
            found.append(atom)
    for match in _MD_RE.finditer(s, start, end):
        if atom := _date_atom(match, s, month_first=True, named=True):
            found.append(atom)
    for regex in (_ISO_RE, _NUM_YEAR_RE, _NUM_SLASH_RE, _NUM_DOT_RE):
        for match in regex.finditer(s, start, end):
            if atom := _date_atom(match, s):
                found.append(atom)
    for match in _WEEKDAY_RE.finditer(s, start, end):
        name = " ".join(match.group("wd").split())
        if name in _PT_SHORT_WEEKDAYS and (
            _previous_word(s, match.start()) in _PT_NOT_WEEKDAY_BEFORE
            or _next_word(s, match.end()) in _PT_NOT_WEEKDAY_AFTER
        ):
            continue
        weekday = _weekday_index(name)
        if weekday is not None:
            found.append(_Atom(match.start(), match.end(), "weekday", weekday=weekday))
    for match in _RELATIVE_RE.finditer(s, start, end):
        key = " ".join(match.group("rel").split())
        if key in ("manana", "morgen") and not _is_tomorrow(s, text, match, lang):
            continue
        offset = _RELATIVE_KEYS.get(key)
        if offset is None:
            offset = _RELATIVE_KEYS.get(key.replace("-", " "), 0)
        found.append(_Atom(match.start(), match.end(), "relative", offset=offset))
    for match in _SPAN_RE.finditer(s, start, end):
        low = int(match.group("a"))
        high = int(match.group("b") or low)
        business = match.group("bd") is not None
        limit = MAX_BUSINESS_DAYS if business else MAX_CALENDAR_DAYS
        if low > high or high > limit:
            continue
        found.append(
            _Atom(
                match.start(),
                match.end(),
                "span",
                low=low,
                high=high,
                business=business,
                within=match.group("within") is not None,
            )
        )
    found.sort(key=lambda atom: (atom.start, atom.start - atom.end))
    atoms: list[_Atom] = []
    last_end = -1
    for atom in found:
        if atom.start >= last_end:
            atoms.append(atom)
            last_end = atom.end
    return atoms


def _is_tomorrow(s: str, text: str, match: re.Match[str], lang: str | None) -> bool:
    """Tell "tomorrow" from "morning" for Spanish manana and German morgen."""
    if _previous_word(s, match.start()) in _MORNING_BEFORE:
        return False
    if match.group("rel") == "morgen" and lang != "nl":
        original = text[match.start()] if match.start() < len(text) else ""
        if original == "M":
            before = text[: match.start()].rstrip(" \t")
            # A capitalised "Morgen" inside a sentence is the German noun.
            return not before or before[-1] in _SENTENCE_START
    return True


def _resolve_date(atom: _Atom, ref: date) -> date | None:
    """Return the date of a date atom, inferring the year when missing."""
    if atom.year is not None:
        try:
            return date(atom.year, atom.month, atom.day)
        except ValueError:
            return None
    candidates: list[date] = []
    for year in (ref.year - 1, ref.year, ref.year + 1):
        try:
            candidates.append(date(year, atom.month, atom.day))
        except ValueError:
            continue
    if not candidates:
        return None
    floor = ref - timedelta(days=7)
    pool = [c for c in candidates if c >= floor] or candidates
    if atom.weekday is not None:
        pool = [c for c in pool if c.weekday() == atom.weekday] or pool
    return min(pool, key=lambda c: abs((c - ref).days))


def _date_on_or_after(atom: _Atom, start: date) -> date | None:
    """Resolve a date atom without a year to the first such date >= start."""
    if atom.year is not None:
        return _resolve_date(atom, start)
    for year in (start.year, start.year + 1):
        try:
            candidate = date(year, atom.month, atom.day)
        except ValueError:
            continue
        if candidate >= start:
            return candidate
    return None


def _date_on_or_before(atom: _Atom, end: date) -> date | None:
    """Resolve a date atom without a year to the last such date <= end."""
    for year in (end.year, end.year - 1):
        try:
            candidate = date(year, atom.month, atom.day)
        except ValueError:
            continue
        if candidate <= end:
            return candidate
    return None


def _next_weekday(start: date, weekday: int) -> date:
    return start + timedelta(days=(weekday - start.weekday()) % 7)


def add_business_days(start: date, days: int) -> date:
    """Return the date ``days`` business days (Monday to Friday) after start."""
    current = start
    while days > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days -= 1
    return current


def _resolve_point(atom: _Atom, ref: date, after: date | None = None) -> date | None:
    """Resolve a date, weekday or relative atom, optionally on or after a date."""
    if atom.kind == "date":
        return (
            _resolve_date(atom, ref)
            if after is None
            else _date_on_or_after(atom, after)
        )
    if atom.kind == "weekday" and atom.weekday is not None:
        return _next_weekday(after or ref, atom.weekday)
    if atom.kind == "relative":
        return ref + timedelta(days=atom.offset)
    return None


def _weekday_with_day(atom: _Atom, day: int, ref: date) -> date | None:
    """Find the date with this day of month and weekday near the reference."""
    current = ref - timedelta(days=7)
    for _ in range(70):
        if current.day == day and current.weekday() == atom.weekday:
            return current
        current += timedelta(days=1)
    return None


def _expression(
    atoms: list[_Atom], index: int, s: str, ref: date
) -> tuple[date, date, int, int] | None:
    """Build (start, end, span start, span end) from the atom at ``index``."""
    atom = atoms[index]
    span_start, span_end = atom.start, atom.end
    if atom.kind == "span":
        if atom.business:
            first = add_business_days(ref, 1 if atom.within else atom.low)
            last = add_business_days(ref, atom.high)
        else:
            first = ref + timedelta(days=1 if atom.within else atom.low)
            last = ref + timedelta(days=atom.high)
        return first, max(first, last), span_start, span_end

    start = _resolve_point(atom, ref)
    if start is None:
        return None
    end = start
    following = atoms[index + 1] if index + 1 < len(atoms) else None

    if (
        following is not None
        and following.kind in ("date", "weekday", "relative")
        and _RANGE_SEP_RE.fullmatch(s, atom.end, following.start)
    ):
        if atom.kind == "date" and following.kind == "date":
            if atom.year is None and following.year is not None:
                last = _resolve_date(following, ref)
                first = _date_on_or_before(atom, last) if last else None
                if first and last:
                    start, end = first, last
            else:
                end = _date_on_or_after(following, start) or start
        else:
            end = _resolve_point(following, ref, after=start) or start
        span_end = following.end
    elif atom.kind == "date" and atom.named_month and not atom.month_first:
        before = _DAY_BEFORE_RE.search(s, max(0, atom.start - 40), atom.start)
        if before and atom.weekday is None:
            first_day = int(before.group("d"))
            if 1 <= first_day < start.day:
                start, end = start.replace(day=first_day), start
                span_start = before.start()
            elif first_day > start.day:
                # "30 - 2 December" starts in the previous month.
                previous = (start.replace(day=1) - timedelta(days=1)).replace(day=1)
                with contextlib.suppress(ValueError):
                    first = previous.replace(day=first_day)
                    if (start - first).days <= MAX_CALENDAR_DAYS:
                        start, end = first, start
                        span_start = before.start()
    elif atom.kind == "date" and atom.month_first:
        after = _DAY_AFTER_RE.match(s, atom.end)
        if after:
            last_day = int(after.group("d"))
            year = _year(after.group("y"))
            if year is not None and atom.year is None:
                try:
                    start = date(year, atom.month, atom.day)
                except ValueError:
                    return None
            try:
                if last_day >= start.day:
                    end = start.replace(day=last_day)
                else:
                    following_month = (
                        start.replace(day=28) + timedelta(days=4)
                    ).replace(day=1)
                    end = following_month.replace(day=last_day)
                span_end = after.end()
            except ValueError:
                end = start
    elif atom.kind == "weekday":
        after = _WEEKDAY_DAY_RE.match(s, atom.end)
        if after and (found := _weekday_with_day(atom, int(after.group("d")), ref)):
            start = end = found
            span_end = after.end()
    if end < start:
        start, end = end, start
    return start, end, span_start, span_end


def _mask(s: str, spans: Iterable[tuple[int, int]], start: int, end: int) -> str:
    """Return ``s[start:end]`` with the given spans blanked out."""
    chars = list(s[start:end])
    for lo, hi in spans:
        for i in range(max(lo, start), min(hi, end)):
            chars[i - start] = " "
    return "".join(chars)


def _eta_from(
    atoms: list[_Atom], s: str, ref: date, start: int, end: int, max_gap: int | None
) -> Eta | None:
    """Return the first ETA among the atoms; with ``max_gap``, it must be near."""
    for index, atom in enumerate(atoms):
        if max_gap is not None:
            gap = s[start : atom.start]
            if _OTHER_DATE_RE.search(gap) or len(_WORD_RE.findall(gap)) > max_gap:
                return None
        expression = _expression(atoms, index, s, ref)
        if expression is None:
            continue
        first, last, span_start, span_end = expression
        spans = [(a.start, a.end) for a in atoms] + [(span_start, span_end)]
        window = parse_time_window(_mask(s, spans, start, end))
        window_start, window_end = window or (None, None)
        return Eta(first, last, window_start, window_end)
    return None


def parse_eta(
    text: str, reference: datetime, tz: tzinfo, lang: str | None = None
) -> Eta | None:
    """Parse a snippet that describes a delivery date.

    Takes the first date, date range, weekday, relative day ("tomorrow") or
    business-day span, plus any time window in the snippet. ``reference``
    is the e-mail's date; ``lang`` is an optional hint.
    """
    text = text[:MAX_PARSE_CHARS]
    s = _prepare(text)
    ref = _reference_date(reference, tz)
    atoms = _find_atoms(s, text, 0, len(s), lang)
    return _eta_from(atoms, s, ref, 0, len(s), None)


def _line_end(s: str, pos: int) -> int:
    end = s.find("\n", pos)
    return len(s) if end < 0 else end


def _next_line(s: str, pos: int) -> tuple[int, int] | None:
    """Return the bounds of the first non-blank line after position ``pos``."""
    start = _line_end(s, pos)
    while start < len(s):
        end = _line_end(s, start + 1)
        if s[start + 1 : end].strip():
            return start + 1, end
        start = end
    return None


def _leading_window(s: str, pos: int) -> tuple[time | None, time | None] | None:
    """Return a time window that a line starting at ``pos`` begins with."""
    line = s[pos : _line_end(s, pos)].lstrip(" \t-*:")
    if any(regex.match(line) for regex in (_TIME_RANGE_RE, _UNTIL_RE, _FROM_RE)):
        return parse_time_window(line)
    return None


def find_eta(
    text: str, reference: datetime, tz: tzinfo, lang: str | None = None
) -> Eta | None:
    """Find a delivery date anchored on delivery keywords in a whole e-mail.

    Only dates that follow a delivery phrase ("Arriving", "Entrega
    prevista", "Voraussichtliche Zustellung", ...) on the same line or the
    next one are used, so order dates and footer dates are never taken.
    A time window may also stand alone on the line after the date.
    """
    text = text[:MAX_FIND_CHARS]
    s = _prepare(text)
    ref = _reference_date(reference, tz)
    for anchor_re, max_gap in (
        (_STRONG_RE, STRONG_MAX_GAP_WORDS),
        (_VERB_FINAL_RE, STRONG_MAX_GAP_WORDS),
        (_WEAK_RE, WEAK_MAX_GAP_WORDS),
    ):
        for anchor in anchor_re.finditer(s):
            if (
                _previous_word(s, anchor.start()) in _FREE_WORDS
                or _next_word(s, anchor.end()) in _FREE_WORDS
                or _negated(s, anchor.start())
            ):
                continue
            pos = anchor.end()
            end = _line_end(s, pos)
            if not _find_atoms(s, text, pos, end, lang) and (
                following := _next_line(s, pos)
            ):
                end = following[1]
            atoms = _find_atoms(s, text, pos, end, lang)
            if not atoms or not (eta := _eta_from(atoms, s, ref, pos, end, max_gap)):
                continue
            if eta.window_start is None and eta.window_end is None:
                following = _next_line(s, end)
                window = _leading_window(s, following[0]) if following else None
                if window is not None:
                    eta = Eta(eta.start, eta.end, window[0], window[1])
            return eta
    return None


_TIME = (
    r"(?P<{p}h>2[0-4]|[01]?\d)"
    r"(?:(?P<{p}sep>[:.h])(?P<{p}mi>[0-5]\d)|(?P<{p}hh>h)(?![a-z0-9]))?"
    r"(?:\s?(?P<{p}ap>[ap])\.?\s?m\.?(?![a-z]))?"
    r"(?:\s?(?P<{p}u>uhr|uur|hrs|hr|h|u)(?![a-z]))?"
)
_NOT_TIME_AFTER = (
    r"(?![\d:])(?![.,]\d)(?!\s*(?:€|eur|euro|usd|\$|£|gbp|chf|%|kg|cm|mm|km|min|minutes"
    r"|minutos|minuten|minuti|dias?|days?|tage|jours|giorni|dagen)(?![a-z]))"
)
_HOUR_ARTICLES = frozenset({"as", "las", "les", "le", "ore", "om"})
_TIME_RANGE_RE = re.compile(
    r"(?<![a-z0-9:.,/€$£])"
    r"(?:(?P<pre>between|entre|zwischen|tra|fra|tussen|from|dalle|das|de|von|van|du"
    r"|dal|desde)\s+)?"
    r"(?:(?P<art>the|as|las|les|le|ore|om|dem|den)\s+)?(?:ore\s+)?"
    + _TIME.format(p="a")
    + r"(?:\s*[-~]\s*|\s+(?:to|till|until|and|a|as|ao|e|y|et|und|bis|en|tot|al|alle"
    r"|hasta)\s+)(?:(?:as|las|les|le|ore|om|het)\s+)?(?:ore\s+)?"
    + _TIME.format(p="b")
    + _NOT_TIME_AFTER
)
_UNTIL_RE = re.compile(
    r"(?<![a-z])(?P<kw>no\s+later\s+than|by|before|until|till|ate|antes\s+de|antes"
    r"|hasta|bis\s+spatestens|spatestens\s+um|spatestens|bis|avant|jusqu'a"
    r"|jusqu\s+a|au\s+plus\s+tard\s+a|entro|prima\s+delle|voor|uiterlijk\s+om"
    r"|uiterlijk|tot)\s+(?:(?P<art>as|las|la|les|le|ore|om|het)\s+)?(?:ore\s+)?"
    + _TIME.format(p="b")
    + _NOT_TIME_AFTER
)
_FROM_RE = re.compile(
    r"(?<![a-z])(?P<kw>from|after|a\s+partir\s+das|a\s+partir\s+de\s+las"
    r"|a\s+partir\s+de|a\s+partir\s+del|desde|ab|nach|des|apres|vanaf|dalle|dopo"
    r"\s+le|dopo)\s+(?:(?P<art>as|las|les|le|ore|om|het)\s+)?(?:ore\s+)?"
    + _TIME.format(p="a")
    + _NOT_TIME_AFTER
)


def _explicit(match: re.Match[str], prefix: str) -> bool:
    """Return True when a time has minutes, "h", "Uhr" or am/pm."""
    return any(match.group(prefix + name) for name in ("mi", "hh", "ap", "u"))


def _to_time(hour: str, minute: str | None, ampm: str | None) -> time | None:
    h, m = int(hour), int(minute or 0)
    if ampm:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ampm == "p" else 0)
    if h == 24 and m == 0:
        return time(23, 59)
    if h > 23 or m > 59:
        return None
    return time(h, m)


def parse_time_window(text: str) -> tuple[time | None, time | None] | None:
    """Find a delivery time window such as ``13:00-14:00``.

    Returns (start, end); open-ended windows such as "by 9pm" or
    "bis 21 Uhr" return (None, end), and "from 9:00" returns (start, None).
    Returns None when there is no window.
    """
    s = fold_aligned(text[:MAX_PARSE_CHARS]).translate(_PUNCTUATION)
    s = _NOON_RE.sub("12:00", s)
    for match in _TIME_RANGE_RE.finditer(s):
        hour_words = (match.group("art") or "") in _HOUR_ARTICLES or (
            match.group("pre") in ("dalle", "das")
        )
        if not (_explicit(match, "a") or _explicit(match, "b") or hour_words):
            continue
        end = _to_time(match.group("bh"), match.group("bmi"), match.group("bap"))
        ampm = match.group("aap") or match.group("bap")
        start = _to_time(match.group("ah"), match.group("ami"), ampm)
        if match.group("aap") is None and start and end and start > end:
            start = _to_time(match.group("ah"), match.group("ami"), None)
        if start and end:
            return start, end
    for regex, prefix in ((_UNTIL_RE, "b"), (_FROM_RE, "a")):
        for match in regex.finditer(s):
            if not (
                _explicit(match, prefix) or (match.group("art") or "") in _HOUR_ARTICLES
            ):
                continue
            value = _to_time(
                match.group(prefix + "h"),
                match.group(prefix + "mi"),
                match.group(prefix + "ap"),
            )
            if value is not None:
                return (None, value) if prefix == "b" else (value, None)
    return None
