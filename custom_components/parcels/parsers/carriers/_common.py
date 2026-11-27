"""Shared engine for the carrier e-mail parsers.

Carrier e-mails differ in layout but say the same things: a status ("out
for delivery", "entregue", "zugestellt"...), a tracking number next to a
label, a delivery day or a time window, and for pickups a point, a code and
a deadline. Each carrier module describes itself with a ``CarrierSpec`` and
``parse_with_spec`` reads an e-mail with it, driven by keywords and labels
so that small layout changes don't break it.

Everything works on the e-mail held in memory. Nothing here logs, stores or
raises e-mail text, and links are only read, never fetched.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, tzinfo
from functools import lru_cache
import re
from urllib.parse import parse_qsl, urlsplit

from ...const import MailKind
from ..base import Eta, MailMessage, ParsedShipment, ParseResult, SenderVerdict
from ..codes import find_code, has_code_label, mask_codes
from ..eta import find_eta, parse_eta, parse_time_window
from ..lang import (
    MONTHS,
    TODAY,
    TOMORROW,
    WEEKDAYS,
    detect_language,
    fold_aligned,
)
from ..tracking import (
    CARRIER_WORDS,
    PAACK_ID_RE,
    detect_carrier,
    find_tracking_numbers,
    id_shaped,
    normalize_tracking_number,
    numbers_from_url,
    tracking_url,
    validate_tracking_number,
)
from ._phrases import (
    ADDRESS_LABELS,
    AUX_CHECKED_KINDS,
    COLLECTED_PHRASES,
    COMPANY_INITIALS,
    CONDITIONAL_PHRASES,
    DEADLINE_WORDS,
    ETA_LABELS,
    EVENT_LABELS,
    FUTURE_WORDS,
    KIND_EXCLUSIONS,
    KIND_PHRASES,
    MARKETING_WORDS,
    MERCHANT_LABELS,
    MESSAGE_WORDS,
    NEGATION_WORDS,
    NOT_ETA_WORDS,
    NOT_EVENT_WORDS,
    NOT_MERCHANT_WORDS,
    NUMBER_GAP_WORDS,
    NUMBER_LABELS,
    OPENING_HOURS_WORDS,
    OPTION_WORDS,
    ORDER_LABELS,
    PAST_WORDS,
    PICKUP_CODE_LABELS,
    PICKUP_HINTS,
    PICKUP_NAME_LABELS,
    PICKUP_POINT_LABELS,
    POINT_ABBREVIATIONS,
    POINT_UNIT_WORDS,
    SENDER_SIDE_WORDS,
    STATUS_LABELS,
    SURVEY_WORDS,
    TIME_LABELS,
    WINDOW_LABELS,
)

# Only this much of an e-mail body is read.
MAX_TEXT_CHARS = 100_000
# Links looked at for a tracking number when the text has none.
MAX_LINKS = 200
# An ETA further away than this is not about this parcel.
MAX_ETA_DAYS = 60
# A pickup deadline further away than this is not a deadline.
MAX_DEADLINE_DAYS = 30
# Event times are accepted from this long before the e-mail ...
MAX_EVENT_AGE = timedelta(days=30)
# ... until this long after it (carriers write their own local time).
EVENT_TOLERANCE = timedelta(minutes=90)
MAX_POINT_CHARS = 120
# Lines that report the kind and are searched for the event time.
MAX_KIND_LINES = 4
# Confidence levels; the engine applies results from verified senders from
# const.CONFIDENCE_APPLY (0.7) up.
CONFIDENCE_SUBJECT = 0.9
CONFIDENCE_BODY = 0.86
CONFIDENCE_LINK = 0.85
CONFIDENCE_LINK_WEAK = 0.8
CONFIDENCE_NO_NUMBER = 0.7
CONFIDENCE_PARTIAL = 0.6
CONFIDENCE_PARTIAL_BODY = 0.55
CONFIDENCE_UNCLEAR = 0.6
# A number was found, but no wording for its status: in transit, by default.
NOTE_KIND_UNCLEAR = "kind_unclear"
NO_BRAND_PENALTY = 0.05
MAX_CONFIDENCE = 0.95

# Kinds by priority, for matches that start at the same place or share a
# line: the more specific (and rarer) news wins.
KIND_PRIORITY: tuple[MailKind, ...] = (
    MailKind.ATTEMPTED,
    MailKind.RETURN,
    MailKind.CANCELLED,
    MailKind.CUSTOMS,
    MailKind.READY_FOR_PICKUP,
    MailKind.DELIVERED,
    MailKind.OUT_FOR_DELIVERY,
    MailKind.DELAYED,
    MailKind.IN_TRANSIT,
    MailKind.SHIPPED,
)
_RANK = {kind: index for index, kind in enumerate(KIND_PRIORITY)}
WEAK_KINDS = frozenset({MailKind.SHIPPED, MailKind.IN_TRANSIT})
# Kinds whose e-mails say when something happened.
_EVENT_KINDS = frozenset(
    {
        MailKind.DELIVERED,
        MailKind.ATTEMPTED,
        MailKind.READY_FOR_PICKUP,
        MailKind.RETURN,
        MailKind.CUSTOMS,
    }
)

# One character per input character, so folded positions map back.
_PUNCT = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u02bc": "'",
        "`": "'",
        "\u00a0": " ",
        "\u2007": " ",
        "\u202f": " ",
        "\t": " ",
        "\u00b0": "o",
    }
)
_WORD_GAP = r"[^\S\n]+"
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
# An address starts where a run of address characters starts, so a long run
# without an "@" is read once, not once per character.
_EMAIL_RE = re.compile(r"(?<![\w.+\-])[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_BOUNDARY_RE = re.compile(r"[!?;\n]|\.(?!\d)")
_TOKEN_RE = re.compile(r"[a-z0-9']+")
_ALNUM3_RE = re.compile(r"[0-9A-Za-z]{3,}")
_WORDS_RE = re.compile(r"[a-z0-9']+")


def fold_text(text: str) -> str:
    """Fold text for matching: lowercase, no accents, plain punctuation.

    The result has exactly one character per input character.
    """
    return fold_aligned(text).translate(_PUNCT)


def _alternation(phrases: Iterable[str]) -> str:
    parts: list[str] = []
    for phrase in sorted(set(phrases), key=lambda p: (-len(p), p)):
        prefix = phrase.endswith("*")
        words = phrase.rstrip("*").split()
        if words:
            body = _WORD_GAP.join(re.escape(word) for word in words)
            parts.append(body + ("[a-z0-9]*" if prefix else ""))
    return "|".join(parts) or "(?!)"


@lru_cache(maxsize=256)
def phrase_regex(phrases: tuple[str, ...]) -> re.Pattern[str]:
    """Compile folded phrases into one whole-word regex, longest first.

    Words of a phrase are separated by spaces (never a line break); a
    trailing ``*`` matches any word that starts with the phrase.
    """
    return re.compile(rf"(?<![a-z0-9])(?:{_alternation(phrases)})(?![a-z0-9])")


@lru_cache(maxsize=64)
def _line_label_regex(labels: tuple[str, ...]) -> re.Pattern[str]:
    """Match a label at the start of a line, with an optional colon."""
    return re.compile(
        rf"[ \-*>\u2022\u00b7]*(?:{_alternation(labels)})(?![a-z0-9])"
        r"[ ]*(?:[:\-][ ]*)?"
    )


@lru_cache(maxsize=8)
def _conditional_regex() -> re.Pattern[str]:
    return re.compile(
        rf"(?<![a-z0-9\-'])(?:{_alternation(CONDITIONAL_PHRASES)})(?![a-z0-9])"
    )


def _blank(match: re.Match[str]) -> str:
    return " " * len(match.group(0))


@dataclass(frozen=True, slots=True)
class CarrierSpec:
    """How to read the e-mails of one carrier.

    ``brands`` are folded names that show the e-mail is about the carrier.
    ``strong`` regexes find numbers that need no label; ``validator`` adds a
    carrier-specific check to ``tracking.validate_tracking_number``.
    ``link_hosts`` and ``link_params`` let tracking links supply the number
    when the text has none; links with an unsubscribe word are skipped,
    except the words in ``link_words_ok``. ``labels``, ``phrases`` and
    ``collected`` extend the shared tables; ``reject`` phrases mark e-mails
    that aren't about a parcel the user receives. ``strip_slash`` drops "/"
    from numbers. ``resolve`` picks the carrier id from the folded subject
    and first lines. ``merchant_labels`` name the shop like the shared
    labels, but also start sentences, so they need a colon, a line of their
    own or nothing but the shop after them; ``default_merchant`` is used
    when the e-mail names no shop. ``decisive`` phrases are the carrier's
    status headlines: they decide the kind wherever they stand, over the
    other wording of the e-mail, unless they're negated or hypothetical.
    ``reference`` matches the carrier's own shipment reference when an
    order label gives it: it's the shipment's reference, never the shop's
    order number.
    """

    carrier: str
    brands: tuple[str, ...]
    strong: tuple[re.Pattern[str], ...] = ()
    validator: Callable[[str], bool] | None = None
    link_hosts: tuple[str, ...] = ()
    link_params: tuple[str, ...] = ()
    link_words_ok: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    phrases: tuple[tuple[MailKind, str], ...] = ()
    collected: tuple[str, ...] = ()
    reject: tuple[str, ...] = ()
    strip_slash: bool = False
    resolve: Callable[[str], str] | None = None
    merchant_labels: tuple[str, ...] = ()
    default_merchant: str | None = None
    decisive: tuple[tuple[MailKind, str], ...] = ()
    reference: re.Pattern[str] | None = None


@dataclass(slots=True)
class _Doc:
    """An e-mail prepared for matching: original and folded text."""

    text: str
    folded: str
    subject: str
    fsubject: str
    starts: list[int]
    date: datetime
    tz: tzinfo
    today: date
    language: str | None

    def line_index(self, pos: int) -> int:
        return bisect_right(self.starts, pos) - 1

    def line(self, index: int) -> tuple[int, int]:
        start = self.starts[index]
        end = (
            self.starts[index + 1] - 1
            if index + 1 < len(self.starts)
            else len(self.text)
        )
        return start, end

    def next_line(self, index: int) -> int | None:
        """Return the index of the next non-blank line."""
        for following in range(index + 1, min(index + 6, len(self.starts))):
            start, end = self.line(following)
            if self.text[start:end].strip():
                return following
        return None

    def lines(self) -> Iterable[tuple[int, int, int]]:
        for index in range(len(self.starts)):
            start, end = self.line(index)
            yield index, start, end


def _document(message: MailMessage, tz: tzinfo) -> _Doc:
    text = message.text[:MAX_TEXT_CHARS]
    text = _EMAIL_RE.sub(_blank, _URL_RE.sub(_blank, text))
    subject = message.subject[:1000]
    local = message.date.astimezone(tz)
    starts = [0, *(match.end() for match in re.finditer("\n", text))]
    language = message.language or detect_language(f"{subject}\n{text[:5000]}")
    return _Doc(
        text=text,
        folded=fold_text(text),
        subject=subject,
        fsubject=fold_text(subject),
        starts=starts,
        date=message.date,
        tz=tz,
        today=local.date(),
        language=language,
    )


# --- Kinds -----------------------------------------------------------------


@dataclass(slots=True)
class _KindMatch:
    kind: MailKind
    start: int
    end: int
    collected: bool = False
    decisive: bool = False


@lru_cache(maxsize=64)
def _kind_regexes(
    spec: CarrierSpec,
) -> tuple[tuple[MailKind, re.Pattern[str], bool], ...]:
    """Return (kind, regex, decisive): the shared phrases with the carrier's,
    then the carrier's decisive phrases.
    """
    extra: dict[MailKind, list[str]] = {}
    for kind, phrase in spec.phrases:
        extra.setdefault(kind, []).append(phrase)
    decisive: dict[MailKind, list[str]] = {}
    for kind, phrase in spec.decisive:
        decisive.setdefault(kind, []).append(phrase)
    kinds = (*KIND_PHRASES, *(kind for kind in extra if kind not in KIND_PHRASES))
    return (
        *(
            (
                kind,
                phrase_regex((*KIND_PHRASES.get(kind, ()), *extra.get(kind, ()))),
                False,
            )
            for kind in kinds
        ),
        *((kind, phrase_regex(tuple(found)), True) for kind, found in decisive.items()),
    )


def _clause(s: str, start: int, end: int) -> tuple[int, int]:
    """Return the bounds of the clause around a match."""
    low = max(0, start - 100)
    clause_start = low
    for match in _BOUNDARY_RE.finditer(s, low, start):
        clause_start = match.end()
    stop = _BOUNDARY_RE.search(s, end, min(len(s), end + 200))
    return clause_start, stop.start() if stop else min(len(s), end + 200)


def _tokens_before(s: str, clause_start: int, start: int) -> list[str]:
    return _TOKEN_RE.findall(s, clause_start, start)


def _negated(tokens: list[str]) -> bool:
    last = tokens[-3:]
    for index, token in enumerate(last):
        # French elides "ne" before a vowel: "n'est plus", "n'a pas".
        if token.startswith("n'") and len(token) > 2:
            return True
        if token not in NEGATION_WORDS:
            continue
        following = last[index + 1] if index + 1 < len(last) else ""
        # "nº 123" folds to "no 123": a number sign, not a negation.
        if token == "no" and following[:1].isdigit():
            continue
        return True
    return False


def _future(tokens: list[str]) -> bool:
    for token in reversed(tokens[-12:]):
        if token in FUTURE_WORDS:
            return True
        if token in PAST_WORDS:
            return False
    return False


def _match_ok(s: str, match: _KindMatch, exclusions: list[tuple[int, int]]) -> bool:
    if any(a <= match.start and match.end <= b for a, b in exclusions):
        return False
    clause_start, clause_end = _clause(s, match.start, match.end)
    if clause_end < len(s) and s[clause_end] == "?":
        return False
    if _conditional_regex().search(s, clause_start, match.start):
        return False
    tokens = _tokens_before(s, clause_start, match.start)
    if match.kind is MailKind.SHIPPED and phrase_regex(MESSAGE_WORDS).search(
        s, clause_start, match.start
    ):
        return False
    if match.decisive:
        # A headline states the status itself: only a negation undoes it.
        if _negated(tokens):
            return False
    elif (match.kind in AUX_CHECKED_KINDS or match.collected) and (
        _negated(tokens) or _future(tokens)
    ):
        return False
    return not (
        match.kind is MailKind.READY_FOR_PICKUP
        and not match.collected
        and any(token in OPTION_WORDS for token in tokens)
    )


def _kind_matches(s: str, spec: CarrierSpec) -> list[_KindMatch]:
    """Find the status phrases in folded text, minus hypothetical ones."""
    found = [
        _KindMatch(kind, match.start(), match.end(), decisive=decisive)
        for kind, regex, decisive in _kind_regexes(spec)
        for match in regex.finditer(s)
    ]
    collected = phrase_regex((*COLLECTED_PHRASES, *spec.collected))
    found += [
        _KindMatch(MailKind.DELIVERED, match.start(), match.end(), collected=True)
        for match in collected.finditer(s)
    ]
    found.sort(key=lambda m: (m.start, m.start - m.end, not m.decisive))
    kept: list[_KindMatch] = []
    far_end, far_start = -1, -1
    for match in found[:500]:
        inside = far_end > match.end or (
            far_end == match.end and far_start < match.start
        )
        # A longer phrase hides the phrases inside it, but not a headline.
        if inside and not match.decisive:
            continue
        kept.append(match)
        if match.end > far_end:
            far_end, far_start = match.end, match.start
    exclusions = {
        kind: [m.span() for m in phrase_regex(phrases).finditer(s)]
        for kind, phrases in KIND_EXCLUSIONS.items()
    }
    result: list[_KindMatch] = []
    for match in kept:
        if not _match_ok(s, match, exclusions.get(match.kind, [])):
            continue
        if match.decisive:
            result.append(match)
            continue
        clause_start, clause_end = _clause(s, match.start, match.end)
        if match.collected and phrase_regex(SENDER_SIDE_WORDS).search(
            s, clause_start, clause_end
        ):
            # "Picked up from the shipper" starts the journey.
            match = _KindMatch(MailKind.SHIPPED, match.start, match.end)
        elif (
            match.kind is MailKind.DELIVERED
            and not match.collected
            and phrase_regex(PICKUP_HINTS).search(
                s, max(clause_start, match.start - 40), min(clause_end, match.end + 60)
            )
        ):
            # Delivered to a locker or a shop: it waits there for the user.
            match = _KindMatch(MailKind.READY_FOR_PICKUP, match.start, match.end)
            if not _match_ok(s, match, exclusions.get(match.kind, [])):
                continue
        result.append(match)
    return result


def _best(matches: list[_KindMatch]) -> _KindMatch:
    return min(matches, key=lambda m: (_RANK[m.kind], m.start))


@dataclass(slots=True)
class _Decision:
    kind: MailKind | None = None
    source: str = ""
    line: int | None = None


def _progress_lines(doc: _Doc, matches: list[_KindMatch]) -> set[int]:
    """Lines that list several statuses, such as a progress bar."""
    kinds: dict[int, set[MailKind]] = {}
    for match in matches:
        kinds.setdefault(doc.line_index(match.start), set()).add(match.kind)
    return {line for line, found in kinds.items() if len(found) >= 3}


def _sentence_line(doc: _Doc, index: int) -> bool:
    start, end = doc.line(index)
    return len(_WORDS_RE.findall(doc.folded, start, end)) >= 4


def _first_line_best(
    doc: _Doc, matches: list[_KindMatch], strong_only: bool
) -> _KindMatch | None:
    by_line: dict[int, list[_KindMatch]] = {}
    for match in matches:
        if strong_only and match.kind in WEAK_KINDS:
            continue
        by_line.setdefault(doc.line_index(match.start), []).append(match)
    if not by_line:
        return None
    return _best(by_line[min(by_line)])


def _status_match(doc: _Doc, matches: list[_KindMatch]) -> _KindMatch | None:
    """Return the status given after a label such as "Estado:" or "Status"."""
    regex = _line_label_regex(STATUS_LABELS)
    for index, start, end in doc.lines():
        label = regex.match(doc.folded, start, end)
        if not label:
            continue
        value_start, value_end = label.end(), end
        if not doc.folded[value_start:value_end].strip(" :-"):
            following = doc.next_line(index)
            if following is None:
                continue
            value_start, value_end = doc.line(following)
        found = [m for m in matches if value_start <= m.start and m.end <= value_end]
        if found:
            return _best(found)
    return None


def _decide_kind(doc: _Doc, spec: CarrierSpec) -> tuple[_Decision, list[_KindMatch]]:
    """Pick the e-mail's kind from the subject, a status label or the body."""
    subject_matches = _kind_matches(doc.fsubject, spec)
    body = _kind_matches(doc.folded, spec)
    progress = _progress_lines(doc, body)
    body = [m for m in body if doc.line_index(m.start) not in progress]
    sentences = [m for m in body if _sentence_line(doc, doc.line_index(m.start))]

    def decided(match: _KindMatch, source: str) -> _Decision:
        line = doc.line_index(match.start) if source != "subject" else None
        return _Decision(match.kind, source, line)

    if headlines := [m for m in subject_matches if m.decisive]:
        first = min(headlines, key=lambda m: (m.start, _RANK[m.kind]))
        return _with_line(doc, _Decision(first.kind, "subject"), body), body
    if headlines := [m for m in body if m.decisive]:
        return decided(_best(headlines), "status"), body
    subject_kind: MailKind | None = None
    if subject_matches:
        first = min(subject_matches, key=lambda m: (m.start, _RANK[m.kind]))
        subject_kind = first.kind
        if subject_kind not in WEAK_KINDS:
            return _with_line(doc, _Decision(subject_kind, "subject"), body), body
    if status := _status_match(doc, body):
        return decided(status, "status"), body
    if subject_kind is not None:
        if found := _first_line_best(doc, sentences, strong_only=True):
            return decided(found, "body"), body
        return _with_line(doc, _Decision(subject_kind, "subject"), body), body
    for pool, strong_only in (
        (sentences, True),
        (sentences, False),
        (body, True),
        (body, False),
    ):
        if found := _first_line_best(doc, pool, strong_only):
            return decided(found, "body"), body
    return _Decision(), body


def _with_line(doc: _Doc, decision: _Decision, body: list[_KindMatch]) -> _Decision:
    """Point a subject decision at the first body line with the same kind."""
    for match in body:
        if match.kind is decision.kind:
            decision.line = doc.line_index(match.start)
            break
    return decision


# --- Tracking numbers --------------------------------------------------------


@dataclass(slots=True)
class _Number:
    number: str
    carrier: str
    source: str


_NUMBER_TOKEN_RE = re.compile(r"[0-9A-Za-z]+(?:[/\-.][0-9A-Za-z]+)*")
_GROUP_RE = re.compile(r"[ \u00a0]([0-9A-Z]{1,6})(?![0-9A-Za-z])")
_FIRST_GROUP_RE = re.compile(r"[0-9A-Z]{1,8}")
# The "_1" that ends Paack's order IDs, where a token stops.
_ID_SUFFIX_RE = re.compile(r"_\d{1,2}(?![0-9A-Za-z_])")
_DATE_LIKE_RE = re.compile(r"\d{1,4}[./-]\d{1,2}(?:[./-]\d{1,4})?")
_UNSUBSCRIBE_WORDS = (
    "unsubscribe",
    "optout",
    "opt-out",
    "newsletter",
    "preference",
    "privacy",
    "baja",
    "abmelden",
    "desinscri",
    "desabonn",
    "disiscri",
    "afmeld",
    "cancelar-subscricao",
)


def _clean_number(raw: str, spec: CarrierSpec) -> str:
    number = normalize_tracking_number(raw)
    return number.replace("/", "") if spec.strip_slash else number


def _carrier_for(number: str, spec: CarrierSpec, carrier: str) -> str | None:
    """Return the carrier a number is valid for, preferring ``carrier``."""
    if not number:
        return None
    if validate_tracking_number(number, carrier) and (
        carrier != spec.carrier or spec.validator is None or spec.validator(number)
    ):
        return carrier
    detected = detect_carrier(number)
    if detected and validate_tracking_number(number, detected):
        return detected
    return None


def _number_in_window(
    doc: _Doc, spec: CarrierSpec, carrier: str, start: int, end: int
) -> _Number | None:
    gap_words = phrase_regex(NUMBER_GAP_WORDS)
    text = doc.text
    skip_until = -1
    for token in _NUMBER_TOKEN_RE.finditer(text, start, end):
        if gap_words.search(doc.folded, start, token.start()):
            return None
        value = token.group(0)
        if token.start() < skip_until:
            continue
        if token.start() and text[token.start() - 1] == "+":
            # A phone number such as "+351 210 000 000": skip all its groups.
            skip_until = token.end()
            while group := _GROUP_RE.match(text, skip_until):
                skip_until = group.end()
            continue
        if _DATE_LIKE_RE.fullmatch(value):
            continue
        variants = [value]
        suffix = _ID_SUFFIX_RE.match(text, token.end())
        if suffix and PAACK_ID_RE.fullmatch(value + suffix.group(0)):
            variants.append(value + suffix.group(0))
        elif _FIRST_GROUP_RE.fullmatch(value):
            pos = token.end()
            for _ in range(6):
                group = _GROUP_RE.match(text, pos)
                if not group or group.end() > end + 24:
                    break
                variants.append(variants[-1] + group.group(1))
                pos = group.end()
        for variant in reversed(variants):
            number = _clean_number(variant, spec)
            if found := _carrier_for(number, spec, carrier):
                return _Number(number, found, "label")
    return None


def _label_numbers(doc: _Doc, spec: CarrierSpec, carrier: str) -> list[_Number]:
    regex = phrase_regex((*NUMBER_LABELS, *spec.labels))
    found: list[_Number] = []
    for label in regex.finditer(doc.folded):
        end = label.end()
        if re.match(r"-[a-z]", doc.folded[end : end + 2]):
            continue
        index = doc.line_index(end)
        line_end = doc.line(index)[1]
        window_end = min(line_end, end + 60)
        start = end
        if not _ALNUM3_RE.search(doc.text, start, window_end):
            following = doc.next_line(index)
            if following is None:
                continue
            start, line_end = doc.line(following)
            window_end = min(line_end, start + 60)
        if number := _number_in_window(doc, spec, carrier, start, window_end):
            found.append(number)
    return found


def _strong_numbers(doc: _Doc, spec: CarrierSpec, carrier: str) -> list[_Number]:
    found: list[_Number] = []
    for regex in spec.strong:
        for match in regex.finditer(doc.text):
            number = _clean_number(match.group(0), spec)
            if result := _carrier_for(number, spec, carrier):
                found.append(_Number(number, result, "strong"))
    for match in find_tracking_numbers(doc.text, carrier):
        number = _clean_number(match.number, spec)
        if result := _carrier_for(number, spec, carrier):
            found.append(
                _Number(number, result, "strong" if match.validated else "text")
            )
    return found


_PUBLIC_SUFFIX_RE = re.compile(r"[a-z]{2,3}|(?:co|com|org)\.[a-z]{2}")


def _host_ok(host: str, hosts: tuple[str, ...]) -> bool:
    """Tell whether a host is one of ``hosts`` or a subdomain of one.

    ``"name.*"`` stands for the name under any country or generic TLD.
    """
    labels = host.split(".")
    for wanted in hosts:
        if wanted.endswith(".*"):
            name = wanted[:-2]
            if any(
                label == name and _PUBLIC_SUFFIX_RE.fullmatch(".".join(labels[i + 1 :]))
                for i, label in enumerate(labels[:-1])
            ):
                return True
        elif host == wanted or host.endswith("." + wanted):
            return True
    return False


def _link_numbers(
    message: MailMessage, spec: CarrierSpec, carrier: str
) -> list[_Number]:
    found: list[_Number] = []
    params = frozenset(spec.link_params)
    skip_words = [w for w in _UNSUBSCRIBE_WORDS if w not in spec.link_words_ok]
    for link in message.links[:MAX_LINKS]:
        url = link.url
        if len(url) > 4096:
            continue
        try:
            parts = urlsplit(url)
            host = (parts.hostname or "").lower()
        except ValueError:
            continue
        lowered = url.lower()
        if not _host_ok(host, spec.link_hosts) or any(
            word in lowered for word in skip_words
        ):
            continue
        candidates = [match.number for match in numbers_from_url(url)]
        fragment_query = parts.fragment.partition("?")[2] or parts.fragment
        for query in (parts.query, fragment_query):
            for key, value in parse_qsl(query):
                if key.strip().lower() in params:
                    candidates.extend(re.split(r"[,;|+\s]+", value))
        for candidate in candidates:
            number = _clean_number(candidate, spec)
            if len(number) <= 40 and (result := _carrier_for(number, spec, carrier)):
                found.append(_Number(number, result, "link"))
    return found


def _numbers(
    doc: _Doc, message: MailMessage, spec: CarrierSpec, carrier: str
) -> list[_Number]:
    """Return the e-mail's tracking numbers, each once, best sources first."""
    found = _label_numbers(doc, spec, carrier)
    strong = _strong_numbers(doc, spec, carrier)
    found += [n for n in strong if n.source == "strong"]
    if not found:
        found = [n for n in strong if n.source == "text"]
    if not found:
        found = _link_numbers(message, spec, carrier)
    unique: dict[str, _Number] = {}
    for number in found:
        unique.setdefault(number.number, number)
    return list(unique.values())


# --- Delivery dates ------------------------------------------------------------


def _skip_eta_line(folded_line: str) -> bool:
    return bool(
        phrase_regex(NOT_ETA_WORDS).search(folded_line)
        or phrase_regex(OPENING_HOURS_WORDS).search(folded_line)
    )


def _label_only(doc: _Doc, start: int, end: int) -> bool:
    return not doc.folded[start:end].strip(" :-.")


def _anchor_eta(doc: _Doc, matches: list[_KindMatch]) -> Eta | None:
    """Find a date after a delivery phrase or an ETA label."""
    anchors = [
        (m.start, m.end)
        for m in matches
        if m.kind in (MailKind.OUT_FOR_DELIVERY, MailKind.IN_TRANSIT, MailKind.DELAYED)
    ]
    anchors += [m.span() for m in phrase_regex(ETA_LABELS).finditer(doc.folded)]
    for start, end in sorted(anchors):
        index = doc.line_index(start)
        line_start, line_end = doc.line(index)
        if _skip_eta_line(doc.folded[line_start:line_end]):
            continue
        eta = parse_eta(doc.text[start:line_end], doc.date, doc.tz, doc.language)
        if eta is None and _label_only(doc, end, line_end):
            following = doc.next_line(index)
            if following is not None:
                next_start, next_end = doc.line(following)
                if not _skip_eta_line(doc.folded[next_start:next_end]):
                    eta = parse_eta(
                        doc.text[next_start:next_end], doc.date, doc.tz, doc.language
                    )
        if eta is not None:
            return eta
    for match in _kind_matches(doc.fsubject, CarrierSpec("", ())):
        if match.kind in (MailKind.OUT_FOR_DELIVERY, MailKind.IN_TRANSIT):
            eta = parse_eta(doc.subject[match.start :], doc.date, doc.tz, doc.language)
            if eta is not None:
                return eta
    return None


def _window(doc: _Doc) -> tuple[time | None, time | None] | None:
    """Find a delivery time window after a window label."""
    for label in phrase_regex(WINDOW_LABELS).finditer(doc.folded):
        index = doc.line_index(label.start())
        line_start, line_end = doc.line(index)
        if _skip_eta_line(doc.folded[line_start:line_end]):
            continue
        window = parse_time_window(doc.text[label.start() : line_end])
        if window is None and _label_only(doc, label.end(), line_end):
            following = doc.next_line(index)
            if following is not None:
                next_start, next_end = doc.line(following)
                if not _skip_eta_line(doc.folded[next_start:next_end]):
                    window = parse_time_window(doc.text[next_start:next_end])
        if window is not None and (window[0] or window[1]):
            return window
    return None


def _deadline(doc: _Doc) -> date | None:
    """Find the last day to collect a parcel ("até 24/11", "bis 24.11.")."""
    latest = doc.today + timedelta(days=MAX_DEADLINE_DAYS)
    for word in phrase_regex(DEADLINE_WORDS).finditer(doc.folded):
        index = doc.line_index(word.start())
        line_end = doc.line(index)[1]
        eta = parse_eta(doc.text[word.end() : line_end], doc.date, doc.tz, doc.language)
        if eta is None and _label_only(doc, word.end(), line_end):
            following = doc.next_line(index)
            if following is not None:
                next_start, next_end = doc.line(following)
                eta = parse_eta(
                    doc.text[next_start:next_end], doc.date, doc.tz, doc.language
                )
        if eta is not None and doc.today <= eta.end <= latest:
            return eta.end
    return None


def _eta(doc: _Doc, kind: MailKind, matches: list[_KindMatch]) -> Eta | None:
    """Return the expected delivery (or, for pickups, the collection) days."""
    if kind in (MailKind.DELIVERED, MailKind.RETURN, MailKind.CANCELLED):
        return None
    if kind is MailKind.READY_FOR_PICKUP:
        return Eta(doc.today, _deadline(doc) or doc.today)
    eta = (
        find_eta(doc.text, doc.date, doc.tz, doc.language)
        or find_eta(doc.subject, doc.date, doc.tz, doc.language)
        or _anchor_eta(doc, matches)
    )
    if (
        eta is not None
        and eta.start == eta.end
        and eta.window_start is None
        and eta.window_end is None
        and (window := _window(doc))
    ):
        eta = Eta(eta.start, eta.end, window[0], window[1])
    if eta is None and kind is MailKind.OUT_FOR_DELIVERY and (window := _window(doc)):
        eta = Eta(doc.today, doc.today, window[0], window[1])
    if eta is not None and (
        eta.end < doc.today or eta.start > doc.today + timedelta(days=MAX_ETA_DAYS)
    ):
        return None
    return eta


# --- Event time -----------------------------------------------------------------


def _month_alternation() -> str:
    names = sorted((m for m in MONTHS if len(m) >= 3), key=len, reverse=True)
    return "|".join(re.escape(name) for name in names)


_MONTH_ALT = _month_alternation()
_TODAY_ALT = _alternation(TODAY)
_G = _WORD_GAP
_EVENT_DATE_RE = re.compile(
    r"(?<![0-9a-z/.:])(?:"
    r"(?P<iy>20\d{2})-(?P<im>[01]?\d)-(?P<id>[0-3]?\d)"
    r"|(?P<d>[0-3]?\d)[./-](?P<m>[01]?\d)(?:[./-](?P<y>(?:20)?\d{2}))?\.?"
    rf"|(?P<nd>[0-3]?\d)(?:\.|o)?{_G}(?:de{_G})?(?P<nm>{_MONTH_ALT})\.?"
    rf"(?:,?{_G}(?:de{_G})?(?P<ny>20\d{{2}}))?"
    rf"|(?P<em>{_MONTH_ALT})\.?{_G}(?P<ed>[0-3]?\d)(?:st|nd|rd|th)?,?"
    rf"(?:{_G}(?P<ey>20\d{{2}}))?"
    rf"|(?P<today>{_TODAY_ALT})"
    r")(?![0-9a-z])"
)
_EVENT_TIME_RE = re.compile(
    r"(?<![0-9:.,/])(?:"
    r"(?P<h>[01]?\d|2[0-3])(?::(?P<mi>[0-5]\d)(?::[0-5]\d)?"
    r"|h(?:(?P<hm>[0-5]\d)|(?![a-z]))"
    r"|\.(?P<dm>[0-5]\d)(?=[^\S\n]*(?:uhr|h|uur)(?![a-z])))"
    r"(?:[^\S\n]*(?P<ap>[ap])\.?[^\S\n]?m\.?(?![a-z]))?"
    r"|(?P<h2>1[0-2]|0?[1-9])[^\S\n]*(?P<ap2>[ap])\.?[^\S\n]?m\.?(?![a-z])"
    r")(?![0-9])"
)
_RANGE_AFTER_RE = re.compile(
    r"[^\S\n]*(?:-|~|to|till|until|a|as|ate|bis|and|e|y|et|und|tot|en|al|alle)"
    r"[^\S\n]*\d"
)
_TIME_PREFIX_RE = re.compile(
    rf"(?<![a-z])(?:at|as|a|um|a{_G}las|a{_G}la|alle|alle{_G}ore|om|pelas|pela"
    rf"|vers|gegen|kl\.?|ore){_G}$"
)


def _event_date(doc: _Doc, match: re.Match[str]) -> date | None:
    groups = match.groupdict()
    if groups["today"]:
        return doc.today
    if groups["iy"]:
        day, month, year = int(groups["id"]), int(groups["im"]), int(groups["iy"])
    elif groups["d"]:
        day, month = int(groups["d"]), int(groups["m"])
        year = int(groups["y"]) if groups["y"] else 0
    elif groups["nd"]:
        day, month = int(groups["nd"]), MONTHS[groups["nm"]]
        year = int(groups["ny"]) if groups["ny"] else 0
    else:
        day, month = int(groups["ed"]), MONTHS[groups["em"]]
        year = int(groups["ey"]) if groups["ey"] else 0
    if month > 12 >= day:
        day, month = month, day
    if 0 < year < 100:
        year += 2000
    try:
        if year:
            return date(year, month, day)
        found = date(doc.today.year, month, day)
        if found > doc.today + timedelta(days=1):
            found = date(doc.today.year - 1, month, day)
    except ValueError:
        return None
    return found


def _event_clock(match: re.Match[str]) -> time | None:
    groups = match.groupdict()
    if groups["h2"]:
        hour, minute, ampm = int(groups["h2"]), 0, groups["ap2"]
    else:
        hour = int(groups["h"])
        minute = int(groups["mi"] or groups["hm"] or groups["dm"] or 0)
        ampm = groups["ap"]
    if ampm:
        if hour > 12:
            return None
        hour = hour % 12 + (12 if ampm == "p" else 0)
    return time(hour, minute) if hour < 24 else None


def _not_event(doc: _Doc, start: int, end: int) -> bool:
    return bool(phrase_regex(NOT_EVENT_WORDS).search(doc.folded, max(0, start), end))


def _in_range(doc: _Doc, value: datetime) -> bool:
    return doc.date - MAX_EVENT_AGE <= value <= doc.date + EVENT_TOLERANCE


def _time_after(doc: _Doc, pos: int, line_end: int) -> time | None:
    """Return a time that follows ``pos`` closely on the same line."""
    found = _EVENT_TIME_RE.search(doc.folded, pos, min(line_end, pos + 25))
    if found is None or any(c.isdigit() for c in doc.folded[pos : found.start()]):
        return None
    if _not_event(doc, pos, found.start()) or _RANGE_AFTER_RE.match(
        doc.folded, found.end()
    ):
        return None
    return _event_clock(found)


def _datetime_in_line(doc: _Doc, start: int, end: int) -> datetime | None:
    for found in _EVENT_DATE_RE.finditer(doc.folded, start, end):
        if _not_event(doc, max(start, found.start() - 30), found.start()):
            continue
        day = _event_date(doc, found)
        clock = _time_after(doc, found.end(), end)
        if day is None or clock is None:
            continue
        value = datetime.combine(day, clock, tzinfo=doc.tz)
        if _in_range(doc, value):
            return value
    return None


def _date_only_in_line(doc: _Doc, start: int, end: int) -> date | None:
    for found in _EVENT_DATE_RE.finditer(doc.folded, start, end):
        if not _not_event(doc, max(start, found.start() - 30), found.start()):
            return _event_date(doc, found)
    return None


def _time_only_in_line(doc: _Doc, start: int, end: int) -> datetime | None:
    window = parse_time_window(doc.text[start:end])
    if window is not None and window[0] and window[1]:
        return None
    for found in _EVENT_TIME_RE.finditer(doc.folded, start, end):
        if not _TIME_PREFIX_RE.search(
            doc.folded, max(start, found.start() - 12), found.start()
        ):
            continue
        if _not_event(doc, max(start, found.start() - 30), found.start()):
            continue
        if _RANGE_AFTER_RE.match(doc.folded, found.end()):
            continue
        clock = _event_clock(found)
        if clock is not None:
            value = datetime.combine(doc.today, clock, tzinfo=doc.tz)
            if _in_range(doc, value):
                return value
    return None


def _kind_lines(doc: _Doc, decision: _Decision, matches: list[_KindMatch]) -> list[int]:
    """Return the decision's line, then the other lines with the same kind."""
    lines = [] if decision.line is None else [decision.line]
    for match in matches:
        index = doc.line_index(match.start)
        if match.kind is decision.kind and index not in lines:
            lines.append(index)
    return lines[:MAX_KIND_LINES]


def _event_time(doc: _Doc, kind: MailKind, lines: list[int]) -> datetime | None:
    """Return when the reported event happened, when the e-mail says so.

    ``lines`` are the lines that report the e-mail's kind, best first.
    """
    nearby: list[int] = []
    for index in lines:
        for found in (index, doc.next_line(index)):
            if found is not None and found not in nearby:
                nearby.append(found)
    labels = _line_label_regex(EVENT_LABELS)
    time_labels = _line_label_regex(TIME_LABELS)
    labelled = [
        index
        for index, start, end in doc.lines()
        if labels.match(doc.folded, start, end)
    ]
    for index in [*nearby, *labelled]:
        start, end = doc.line(index)
        if value := _datetime_in_line(doc, start, end):
            return value
    for index in labelled:
        start, end = doc.line(index)
        day = _date_only_in_line(doc, start, end)
        if day is None:
            continue
        following = index
        for _ in range(2):
            following = doc.next_line(following)
            if following is None:
                break
            next_start, next_end = doc.line(following)
            label = time_labels.match(doc.folded, next_start, next_end)
            if not label:
                continue
            found = _EVENT_TIME_RE.search(doc.folded, label.end(), next_end)
            clock = _event_clock(found) if found else None
            if clock is not None:
                value = datetime.combine(day, clock, tzinfo=doc.tz)
                if _in_range(doc, value):
                    return value
    if kind in _EVENT_KINDS:
        for index in lines:
            start, end = doc.line(index)
            if value := _time_only_in_line(doc, start, end):
                return value
    return None


# --- Pickup point and code --------------------------------------------------------

_POINT_WORD_RE = re.compile(
    r"[ ]*(?:[A-Z0-9\u00c0-\u00de][\w'&.\-/\u00ae\u2122]*"
    r"|(?:de|do|da|dos|das|del|la|las|los|el|y|e|und|am|an|der|die|di|du|des"
    r"|van|het|of|the)(?![\w])|[,\-\u00b7|][ ]*(?=[A-Z0-9\u00c0-\u00de]))"
)
_CONNECTOR_END_RE = re.compile(
    r"(?:[ ,\-\u00b7|]+|[ ]+(?:de|do|da|dos|das|del|la|las|los|el|y|e|und|am|an"
    r"|der|die|di|du|des|van|het|of|the))+$"
)
_POINT_PREP_RE = re.compile(
    rf"(?<![a-z])(?:na|no|em|at|en|el|in{_G}der|in{_G}die|im|in|au|al|bij|presso"
    rf"|nella|nel|alla|op|para|to|a)"
    rf"{_G}(?:(?:the|la|le|el|de|het|der|die|o|a|uma|um|une|un|your|sua|seu|tu|su)"
    rf"{_G})?$"
)

_ROW_GAP_RE = re.compile(r"[ ]*(?:[:\-][ ]*)?")
_NAME_ABBREVIATIONS = frozenset(POINT_ABBREVIATIONS)
_COMPANY_SUFFIXES = frozenset(COMPANY_INITIALS)
_UNIT_WORDS = frozenset(POINT_UNIT_WORDS)
_INITIALS_RE = re.compile(r"(?:[^\W\d_]\.)*[^\W\d_]")


def _ends_sentence(word: str, previous: str = "") -> bool:
    """Tell whether a point's word ends its sentence with a full stop.

    A number or a word before a full stop ends it, as in "Cacifo CTT Sol." A
    name goes on after an initial, as in "J. Silva" or "C.C. Colombo", and
    after an abbreviation such as "Av." or "Sta.", but a company's "S.A."
    ends it, and so does a letter after the ``previous`` word naming a part
    of a building, as in "Bloco B."
    """
    word = word.strip()
    if not word.endswith("."):
        return False
    stem = fold_text(word[:-1])
    if stem[-1:].isdigit():
        return True
    if _INITIALS_RE.fullmatch(stem):
        return stem in _COMPANY_SUFFIXES or (
            len(stem) == 1 and fold_text(previous.strip(" ,")) in _UNIT_WORDS
        )
    return stem not in _NAME_ABBREVIATIONS


def _clean_point(value: str) -> str | None:
    value = re.sub(r"\s+", " ", value).strip(" :-,.;")
    value = _CONNECTOR_END_RE.sub("", value).strip(" :-,.;")
    if len(re.findall(r"[^\W\d_]", value)) < 3:
        return None
    return value[:MAX_POINT_CHARS]


def _address_line(doc: _Doc, index: int) -> str | None:
    following = doc.next_line(index)
    if following is None:
        return None
    start, end = doc.line(following)
    # A table row reads "Address Rua Exemplo 1, ..." once flattened to text.
    if label := _line_label_regex(ADDRESS_LABELS).match(doc.folded, start, end):
        start = label.end()
    line = doc.text[start:end].strip()
    folded = doc.folded[start:end]
    if (
        len(line) > 80
        or not re.search(r"\d|,", line)
        or len(line.split()) > 10
        or re.match(r"[^:]{1,25}:", line)
        or phrase_regex(
            (*DEADLINE_WORDS, *OPENING_HOURS_WORDS, *PICKUP_CODE_LABELS)
        ).search(folded)
        or _ALNUM3_RE.search(line) is None
    ):
        return None
    return line


def _with_address(doc: _Doc, index: int, value: str | None) -> str | None:
    if value is None:
        return None
    if address := _address_line(doc, index):
        value = f"{value}, {address}"
    return value[:MAX_POINT_CHARS]


def _point_words(doc: _Doc, start: int, end: int) -> str:
    pos = start
    previous = ""
    while pos < end:
        word = _POINT_WORD_RE.match(doc.text, pos, end)
        if not word or word.end() == pos:
            break
        pos = word.end()
        if _ends_sentence(word.group(), previous):
            break
        previous = word.group()
    return doc.text[start:pos]


def _short_value(doc: _Doc, start: int, end: int) -> bool:
    """Tell whether a line part reads like a name or address, not a sentence."""
    value = doc.text[start:end].strip()
    return len(value) <= 80 and len(value.split()) <= 12 and not value.endswith(".")


def _pickup_point(doc: _Doc, kind: MailKind) -> str | None:
    """Return the pickup point named after a label or in a pickup sentence."""
    if kind is MailKind.DELIVERED:
        return None
    labels = _line_label_regex(PICKUP_POINT_LABELS)
    for index, start, end in doc.lines():
        label = labels.match(doc.folded, start, end)
        if not label:
            continue
        if _label_only(doc, label.end(), end):
            following = doc.next_line(index)
            if following is None:
                continue
            next_start, next_end = doc.line(following)
            if _short_value(doc, next_start, next_end):
                value = _clean_point(doc.text[next_start:next_end])
                return _with_address(doc, following, value)
        elif _short_value(doc, label.end(), end):
            return _with_address(doc, index, _clean_point(doc.text[label.end() : end]))
    if kind not in (MailKind.READY_FOR_PICKUP, MailKind.ATTEMPTED):
        return None
    names = phrase_regex(PICKUP_NAME_LABELS)
    for index, start, end in doc.lines():
        offset = len(doc.folded[start:end]) - len(doc.folded[start:end].lstrip(" -*>"))
        name = names.match(doc.folded, start + offset, end)
        if not name or not _short_value(doc, start, end):
            continue
        if _label_only(doc, name.end(), end):
            following = doc.next_line(index)
            if following is not None:
                next_start, next_end = doc.line(following)
                if _short_value(doc, next_start, next_end):
                    value = _clean_point(
                        f"{doc.text[name.start() : name.end()]} "
                        f"{doc.text[next_start:next_end]}"
                    )
                    return _with_address(doc, following, value)
            continue
        # A row label repeated by its value: "Packstation Packstation 123".
        rest = _ROW_GAP_RE.match(doc.folded, name.end(), end)
        if rest and names.match(doc.folded, rest.end(), end):
            start = rest.end()
        return _with_address(doc, index, _clean_point(doc.text[start:end]))
    for name in names.finditer(doc.folded):
        before = doc.folded[max(0, name.start() - 30) : name.start()]
        if not _POINT_PREP_RE.search(before):
            continue
        line_end = doc.line(doc.line_index(name.start()))[1]
        words = _point_words(doc, name.end(), line_end)
        if value := _clean_point(doc.text[name.start() : name.end()] + words):
            return value
    return None


# Kinds whose e-mails may give a locker or counter code with a bare label.
_LOCKER_KINDS = frozenset({MailKind.READY_FOR_PICKUP, MailKind.ATTEMPTED})


def _without_codes(doc: _Doc, locker: bool) -> _Doc:
    """Return ``doc`` with the values written as a code blanked out.

    Tracking and order numbers are read from it, so a PIN is never one.
    """
    text = mask_codes(doc.text, locker=locker)
    if text == doc.text:
        return doc
    return replace(doc, text=text, folded=fold_text(text))


def _code(doc: _Doc, exclude: list[str], locker: bool) -> str | None:
    """Return the delivery PIN or pickup code; never one of ``exclude``."""
    return find_code(doc.text, exclude=exclude, locker=locker) or find_code(
        doc.subject, exclude=exclude, locker=locker
    )


# --- Merchant and order numbers -------------------------------------------------------

# "Tu envío 0628174547 de Druni": a tracking number may sit before "de".
_NUMBER_SLOT = rf"(?:{_G}(?:n\.?o\.?{_G})?[0-9][0-9a-z/\-]{{5,30}})?"
# "O seu envio da loja Decathlon".
_SHOP_SLOT = rf"(?:{_G}(?:a{_G}loja|loja|la{_G}tienda|tienda))?"
_MERCHANT_PHRASE_RE = re.compile(
    rf"(?<![a-z])(?:"
    rf"(?:(?:a{_G})?(?:sua|tua){_G})?encomenda{_NUMBER_SLOT}{_G}(?:de|da|do)"
    rf"|(?:o{_G})?(?:seu|teu){_G}(?:envio|pedido){_NUMBER_SLOT}{_G}(?:de|da|do)"
    rf"|(?:o{_G})?(?:seu|teu){_G}pedido{_G}a"
    rf"|(?:tu|su){_G}(?:pedido|paquete|envio|compra){_NUMBER_SLOT}{_G}(?:de|en)"
    rf"|your{_G}(?:parcel|package|order|shipment|delivery){_G}from"
    rf"|(?:ihr|ihre|dein|deine){_G}(?:paket|sendung|bestellung|lieferung){_G}(?:von|bei)"
    rf"|(?:votre|ton){_G}(?:colis|commande){_G}"
    rf"(?:de{_G}|d'|(?:passee{_G})?chez{_G}|aupres{_G}de{_G})"
    rf"|(?:il{_G}tuo|il{_G}suo){_G}(?:pacco|ordine){_G}(?:di|da)"
    rf"|(?:je|uw){_G}(?:pakket|bestelling|zending){_G}(?:van|bij)"
    rf"){_SHOP_SLOT}(?:{_G})?"
)
_SHOP_WORD = (
    r"(?:[A-Z0-9\u00c0-\u00de][\w'&.+\-]*|&|(?:de|del|la|y|e|und|and|of)"
    r"(?=[^\S\n]+[A-Z0-9\u00c0-\u00de]))"
)
_MERCHANT_WORD_RE = re.compile(rf"(?:[^\S\n]+|(?<=[^\S\n])|(?<=')|^){_SHOP_WORD}")
# "Your Casa Exemplo order was delivered".
_YOUR_SHOP_ORDER_RE = re.compile(
    rf"(?<![A-Za-z])(?:[Yy]our|YOUR)[^\S\n]+"
    rf"(?P<shop>{_SHOP_WORD}(?:[^\S\n]+{_SHOP_WORD}){{0,4}}?)"
    r"[^\S\n]+(?:order|Order|ORDER)(?![A-Za-z])"
)
_MERCHANT_STOP = frozenset(
    {*NOT_MERCHANT_WORDS, *WEEKDAYS, *MONTHS, *TODAY, *TOMORROW, *CARRIER_WORDS}
)


def _valid_merchant(value: str, spec: CarrierSpec) -> str | None:
    value = re.sub(r"\s+", " ", value).strip(" :-,.;!?\"'()")
    folded = fold_text(value)
    if (
        not 2 <= len(value) <= 60
        or not (value[0].isupper() or value[0].isdigit())
        or len(value.split()) > 6
        or not re.search(r"[^\W\d_]", value)
        or "@" in value
        or "http" in folded
        or "www" in folded
        or folded in _MERCHANT_STOP
        or phrase_regex(spec.brands).search(folded)
        or phrase_regex(tuple(CARRIER_WORDS)).fullmatch(folded)
    ):
        return None
    return value


def _merchant_after(text: str, start: int, end: int) -> str:
    pos, words = start, 0
    while pos < end and words < 5:
        word = _MERCHANT_WORD_RE.match(text, pos, end)
        if not word or word.end() == pos:
            break
        pos, words = word.end(), words + 1
        # "… de Casa Exemplo. Entre em contacto": the sentence ends there.
        if text[pos - 1] == "." and text[pos : pos + 1].isspace():
            break
    return text[start:pos]


def _merchant_phrase(
    doc: _Doc, spec: CarrierSpec, text: str, folded: str
) -> str | None:
    found: list[tuple[int, str]] = []
    for phrase in _MERCHANT_PHRASE_RE.finditer(folded):
        end = folded.find("\n", phrase.end())
        end = len(folded) if end < 0 else end
        value = _merchant_after(text, phrase.end(), min(end, phrase.end() + 80))
        found.append((phrase.start(), value))
    found += [(m.start(), m.group("shop")) for m in _YOUR_SHOP_ORDER_RE.finditer(text)]
    for _, value in sorted(found):
        if value := _valid_merchant(value, spec):
            return value
    return None


def _labelled_merchant(
    doc: _Doc, spec: CarrierSpec, labels: tuple[str, ...], strict: bool
) -> str | None:
    """Return the shop named after a label at the start of a line.

    A ``strict`` label needs a colon, a line of its own or nothing but the
    shop after it: "Pedido de" is also how a sentence starts.
    """
    regex = _line_label_regex(labels)
    for index, start, end in doc.lines():
        label = regex.match(doc.folded, start, end)
        if not label:
            continue
        value_start, value_end = label.end(), end
        if _label_only(doc, value_start, value_end):
            following = doc.next_line(index)
            if following is None:
                continue
            value_start, value_end = doc.line(following)
        elif strict and ":" not in label.group(0):
            # "Pedido de Casa Exemplo", not "Pedido de devolução em curso".
            rest = doc.text[value_start:value_end].strip(" .!;,")
            shop = _merchant_after(doc.text, value_start, value_end)
            if shop.strip(" .!;,") != rest:
                continue
        if value := _valid_merchant(doc.text[value_start:value_end][:60], spec):
            return value
    return None


def _merchant(doc: _Doc, spec: CarrierSpec) -> str | None:
    """Return the shop that sent the parcel, when the e-mail names it."""
    if value := _merchant_phrase(doc, spec, doc.subject, doc.fsubject):
        return value
    if value := _labelled_merchant(doc, spec, MERCHANT_LABELS, strict=False):
        return value
    if spec.merchant_labels and (
        value := _labelled_merchant(doc, spec, spec.merchant_labels, strict=True)
    ):
        return value
    return _merchant_phrase(doc, spec, doc.text, doc.folded) or spec.default_merchant


_ORDER_VALUE_RE = re.compile(
    r"[ ]*(?:[:#][ ]*)?"
    r"(?:(?:number|numero|nummer|num|nr|n\.o|no|n|id)(?![a-z])\.?[ ]*[:#.]?[ ]*)?"
    # Paack's order ID whole, so that its first part isn't taken for one.
    r"#?(?P<v>[0-9A-Za-z]{9}_\d{1,2}(?![0-9A-Za-z])"
    r"|[0-9A-Za-z][0-9A-Za-z\-/]{2,29})(?![0-9A-Za-z])"
)


def _order_numbers(doc: _Doc, numbers: set[str]) -> tuple[str, ...]:
    """Return order numbers given after an order label."""
    found: list[str] = []
    for label in phrase_regex(ORDER_LABELS).finditer(doc.folded):
        match = _ORDER_VALUE_RE.match(doc.folded, label.end())
        if not match:
            continue
        value = doc.text[match.start("v") : match.end("v")]
        if (
            sum(c.isdigit() for c in value) >= 3
            and not _DATE_LIKE_RE.fullmatch(value)
            and normalize_tracking_number(value) not in numbers
            and value not in found
        ):
            found.append(value)
        if len(found) >= 3:
            break
    return tuple(found)


def _references(doc: _Doc, spec: CarrierSpec) -> tuple[str, ...]:
    """Return the carrier's shipment references given after an order label.

    The label must name a number ("order number", not "order"), or a colon,
    "#" or a number word must come first, and the value must look like an
    ID, not a word: a digit, or a capital past its first letter.
    """
    if spec.reference is None:
        return ()
    found: list[str] = []
    for label in phrase_regex(ORDER_LABELS).finditer(doc.folded):
        match = _ORDER_VALUE_RE.match(doc.folded, label.end())
        if not match:
            continue
        value = doc.text[match.start("v") : match.end("v")]
        named = (
            len(label.group().split()) > 1
            or label.group().endswith("nummer")
            or bool(doc.folded[label.end() : match.start("v")].strip())
        )
        if (
            named
            and spec.reference.fullmatch(value)
            and id_shaped(value)
            and doc.text[match.end("v") : match.end("v") + 1] != "_"
            and value not in found
        ):
            found.append(value)
    return tuple(found)


# --- Result ---------------------------------------------------------------------------


def _confidence(
    decision: _Decision,
    kind: MailKind,
    numbers: list[_Number],
    has_details: bool,
    has_date: bool,
    has_reference: bool = False,
) -> float | None:
    clear = decision.source in ("subject", "status")
    if has_reference or any(n.source != "link" for n in numbers):
        return CONFIDENCE_SUBJECT if clear else CONFIDENCE_BODY
    if numbers:
        return CONFIDENCE_LINK if kind not in WEAK_KINDS else CONFIDENCE_LINK_WEAK
    if clear and has_details and has_date:
        return CONFIDENCE_NO_NUMBER
    if has_date or has_details:
        return CONFIDENCE_PARTIAL if clear else CONFIDENCE_PARTIAL_BODY
    return None


def _code_confidence(doc: _Doc, numbers: list[_Number]) -> float:
    """Return the confidence of an e-mail that only gives a code."""
    if any(n.source != "link" for n in numbers):
        return CONFIDENCE_SUBJECT if has_code_label(doc.subject) else CONFIDENCE_BODY
    return CONFIDENCE_LINK if numbers else CONFIDENCE_NO_NUMBER


def parse_with_spec(
    message: MailMessage,
    verdict: SenderVerdict,
    tz: tzinfo,
    spec: CarrierSpec,
    parser: str,
) -> ParseResult | None:
    """Read a carrier e-mail with ``spec``; None when it isn't about a parcel.

    ``parser`` is the parser id reported in the result. ``verdict`` is not
    needed to read the e-mail: the parcel engine decides from it whether the
    result may be applied. An e-mail whose only news is a delivery PIN or a
    pickup code for a parcel it identifies gets the kind ``CODE``.
    """
    doc = _document(message, tz)
    whole = f"{doc.fsubject}\n{doc.folded}"
    if spec.reject and phrase_regex(spec.reject).search(whole):
        return None
    head = f"{doc.fsubject}\n{doc.folded[:1500]}"
    carrier = spec.resolve(head) if spec.resolve else spec.carrier
    decision, matches = _decide_kind(doc, spec)
    locker = decision.kind in _LOCKER_KINDS
    plain = _without_codes(doc, locker)
    numbers = _numbers(plain, message, spec, carrier)
    number_set = {n.number for n in numbers}
    references = _references(plain, spec)
    orders = tuple(o for o in _order_numbers(plain, number_set) if o not in references)
    reference = references[0] if references else None
    pickup_code = _code(doc, [*number_set, *orders, *references], locker)
    only_code = decision.kind is None and bool(
        pickup_code and (numbers or orders or reference)
    )
    # Survey wording, often a footer's, only counts when no status was read.
    blocked = phrase_regex(MARKETING_WORDS).search(whole) is not None or (
        decision.kind is None and phrase_regex(SURVEY_WORDS).search(whole) is not None
    )
    if (
        blocked
        and not only_code
        and (not (numbers or reference) or decision.kind is None)
    ):
        return None
    notes: list[str] = []
    kind = decision.kind
    if only_code:
        kind = MailKind.CODE
    elif kind is None:
        if not numbers:
            return None
        kind = MailKind.IN_TRANSIT
        notes.append(NOTE_KIND_UNCLEAR)
    eta: Eta | None = None
    event_time: datetime | None = None
    pickup_point: str | None = None
    if kind is not MailKind.CODE:
        eta = _eta(doc, kind, matches)
        if kind in WEAK_KINDS and eta is not None and eta.start == eta.end == doc.today:
            kind = MailKind.OUT_FOR_DELIVERY
        event_time = _event_time(doc, kind, _kind_lines(doc, decision, matches))
        pickup_point = _pickup_point(doc, kind)
    merchant = _merchant(doc, spec)
    if kind is MailKind.CODE:
        confidence: float | None = _code_confidence(doc, numbers)
    else:
        confidence = _confidence(
            decision,
            kind,
            numbers,
            has_details=bool(merchant or pickup_code),
            has_date=bool(eta or event_time),
            has_reference=reference is not None,
        )
    if confidence is None:
        return None
    if NOTE_KIND_UNCLEAR in notes:
        confidence = min(confidence, CONFIDENCE_UNCLEAR)
    brands = phrase_regex(spec.brands)
    if not (brands.search(whole) or brands.search(fold_text(message.sender_name))):
        confidence -= NO_BRAND_PENALTY
    if not numbers:
        notes.append("no_tracking_number")
    elif all(n.source == "link" for n in numbers):
        notes.append("number_from_link")
    shipments = [
        ParsedShipment(
            carrier=number.carrier,
            tracking_number=number.number,
            kind=kind,
            eta=eta,
            event_time=event_time,
            pickup_point=pickup_point,
            pickup_code=pickup_code,
            order_numbers=orders,
            tracking_url=tracking_url(number.carrier, number.number),
            reference=reference,
        )
        for number in numbers
    ] or [
        ParsedShipment(
            carrier=carrier,
            kind=kind,
            eta=eta,
            event_time=event_time,
            pickup_point=pickup_point,
            pickup_code=pickup_code,
            order_numbers=orders,
            reference=reference,
        )
    ]
    return ParseResult(
        parser=parser,
        kind=kind,
        merchant=merchant,
        order_numbers=orders,
        shipments=shipments,
        confidence=round(min(confidence, MAX_CONFIDENCE), 2),
        language=doc.language,
        notes=tuple(notes),
    )


def resolve_by_name(names: dict[str, str], default: str) -> Callable[[str], str]:
    """Return a resolver that maps the first carrier name found to its id.

    ``names`` maps folded names to carrier ids; the earliest name in the
    folded head of the e-mail wins, longer names first at the same place.
    """
    regex = phrase_regex(tuple(names))

    def resolve(head: str) -> str:
        found = regex.search(head)
        if found is None:
            return default
        return names.get(re.sub(r"\s+", " ", found.group(0)), default)

    return resolve
