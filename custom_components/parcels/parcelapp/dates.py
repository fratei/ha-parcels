"""Dates in Parcel's answers.

Parcel gives an event's date as text without a time zone: ISO ("2026-11-14
15:21:00"), as the app shows it ("Saturday, 14 November 3:21 pm"), often
without the year, or as carriers write it, day first ("14/11/2026 15:21").
All are read in Home Assistant's time zone. The expected delivery comes as
local dates ("2026-11-19 00:00:00"), or as epoch timestamps when the carrier
gives its time zone.

A 12-hour time takes its part of the day in the seven languages ("3:15 da
tarde", "9:05 du matin", "8:45 's avonds"; 12:30 "da madrugada" is 00:30),
and a time zone after it wins ("3:21 pm WET", "15:21 GMT+1"). When words
after the time aren't understood, only the day is read: read_event_date
gives it without a time. Anything else that doesn't read cleanly gives None,
never a guess, and so does a date after tomorrow: an event can't have
happened yet. date_shape describes an unreadable date for diagnostics
without its text.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
import math
import re
import string
from typing import Any

from ..parsers.base import Eta
from ..parsers.lang import MONTHS, WEEKDAY_ABBREVIATIONS, WEEKDAYS, fold

MAX_LENGTH = 100
MIN_YEAR = 2000
MAX_YEAR = 2100
SHAPE_LENGTH = 60

_SHAPE_INPUT = 200
_MIDNIGHT = time(0, 0)
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Day first, with a four-digit year: "16/11/2026", "16-11-2026", "16.11.2026".
_NUMERIC_RE = re.compile(r"(?<!\d)(\d{1,2})([/.-])(\d{1,2})\2(\d{4})(?!\d)")
_MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_SHAPE_RE = re.compile(r"([0-9]+)|([^\W\d_]+)|(\s+)|(.)")
# The last word of a date, when it follows a space, a digit or a bracket.
_LAST_WORD_RE = re.compile(r"(?<=[\s\d(])((?:[^\W\d_]|\.){1,6})[\s)]*$")
_LAST_WORD_LETTERS = 6
_APOSTROPHE_RE = re.compile("['`\u2018\u2019\u02bc]")
_MERIDIEM_RE = re.compile(r"(\d)\s*([ap])\.?\s?m\.?(?=[\s,;)]|$)")
_SEPARATOR_RE = re.compile(r"[,.;()]")
_TIME_RE = re.compile(r"(\d{1,2})(?:[:h](\d{2})(?::(\d{2}))?|h)")
_YEAR_RE = re.compile(r"\d{4}")
_DAY_RE = re.compile(r"(\d{1,2})(?:st|nd|rd|th|er|e|o|a)?")
_TIMESTAMP_RE = re.compile(r"\d{1,12}(?:\.\d+)?")

# Words between the parts of a date, in the seven languages ("14 de
# novembro às 15h21", "am 14. November um 15:21 Uhr", "op 14 november om").
# They win over the two-letter weekday abbreviations ("di", "do").
_FILLER = frozenset(
    (
        "a",
        "alle",
        "am",
        "as",
        "at",
        "de",
        "del",
        "den",
        "der",
        "di",
        "el",
        "feira",
        "h",
        "heures",
        "horas",
        "hrs",
        "il",
        "la",
        "las",
        "le",
        "of",
        "om",
        "on",
        "op",
        "ore",
        "the",
        "uhr",
        "um",
        "uur",
    )
)

# Words right after a time that only say it's a time ("15:21 Uhr").
_CLOCK_WORDS = frozenset(("h", "heures", "horas", "hrs", "uhr", "uur"))

_MORNING = frozenset(range(12))
_AFTERNOON = frozenset(range(12, 24))
_EVENING = frozenset((*range(17, 24), 0))
_NIGHT = frozenset((*range(18, 24), *range(6)))
_DAWN = frozenset(range(7))
_NOON = frozenset((12,))
_MIDDAY = frozenset(range(12, 16))
_MIDNIGHT_HOURS = frozenset((0,))

# The parts of the day after a 12-hour time, folded, with the hours they
# can be (after CLDR's day periods). No bare "manana": in Spanish it's also
# tomorrow. Apostrophes are spaces: "'s avonds" is "s avonds".
_PERIODS: dict[tuple[str, ...], frozenset[int]] = {
    tuple(phrase.split()): hours
    for hours, phrases in (
        (
            _MORNING,
            (
                "am",
                "in the morning",
                "da manha",
                "de manha",
                "de la manana",
                "du matin",
                "matin",
                "di mattina",
                "della mattina",
                "del mattino",
                "di mattino",
                "mattina",
                "mattino",
                "morgens",
                "vormittags",
                "vorm",
                "s ochtends",
                "ochtends",
                "s morgens",
            ),
        ),
        (
            _AFTERNOON,
            (
                "pm",
                "in the afternoon",
                "da tarde",
                "de tarde",
                "a tarde",
                "tarde",
                "de la tarde",
                "de l apres-midi",
                "de l apres midi",
                "l apres-midi",
                "l apres midi",
                "apres-midi",
                "apres midi",
                "del pomeriggio",
                "di pomeriggio",
                "pomeriggio",
                "nachmittags",
                "nachm",
                "mittags",
                "s middags",
                "middags",
            ),
        ),
        (
            _EVENING,
            (
                "in the evening",
                "da noite",
                "de noite",
                "a noite",
                "noite",
                "de la noche",
                "noche",
                "du soir",
                "soir",
                "di sera",
                "della sera",
                "sera",
                "abends",
                "s avonds",
                "avonds",
            ),
        ),
        (
            _NIGHT,
            (
                "at night",
                "de nuit",
                "de la nuit",
                "nuit",
                "di notte",
                "della notte",
                "notte",
                "nachts",
                "s nachts",
            ),
        ),
        (_DAWN, ("da madrugada", "de madrugada", "madrugada", "de la madrugada")),
        (
            _NOON,
            (
                "meio-dia",
                "meio dia",
                "midi",
                "mezzogiorno",
                "mittag",
                "noon",
                "at noon",
            ),
        ),
        (_MIDDAY, ("del mediodia", "mediodia")),
        (
            _MIDNIGHT_HOURS,
            (
                "meia-noite",
                "meia noite",
                "medianoche",
                "minuit",
                "mezzanotte",
                "mitternacht",
                "middernacht",
                "midnight",
                "at midnight",
            ),
        ),
    )
    for phrase in phrases
}
_PERIOD_LENGTH = max(len(phrase) for phrase in _PERIODS)

# Time zones after a time, in minutes from UTC; no American ones.
_ZONES = {
    "utc": 0,
    "gmt": 0,
    "z": 0,
    "wet": 0,
    "wez": 0,
    "west": 60,
    "wesz": 60,
    "bst": 60,
    "cet": 60,
    "mez": 60,
    "cest": 120,
    "mesz": 120,
    "eet": 120,
    "oez": 120,
    "eest": 180,
    "oesz": 180,
}
_OFFSET_RE = re.compile(r"(?:utc|gmt)?([+-])(\d{1,2})(?::?(\d{2}))?")
_MAX_OFFSET_HOURS = 14

# Kept in the shapes of unreadable dates, with the month, weekday, filler,
# part-of-day and time zone words: relative days, am/pm, ordinal suffixes
# and ISO's "t" and "z".
_SHAPE_WORDS = (
    "today",
    "yesterday",
    "hoje",
    "ontem",
    "hoy",
    "ayer",
    "heute",
    "gestern",
    "aujourd",
    "hui",
    "hier",
    "oggi",
    "ieri",
    "vandaag",
    "gisteren",
    "am",
    "pm",
    "p",
    "m",
    "t",
    "z",
    "st",
    "nd",
    "rd",
    "th",
    "er",
    "e",
    "o",
)
_DATE_WORDS = frozenset(
    word
    for key in (
        *MONTHS,
        *WEEKDAYS,
        *WEEKDAY_ABBREVIATIONS,
        *_FILLER,
        *_SHAPE_WORDS,
        *_ZONES,
        *(" ".join(phrase) for phrase in _PERIODS),
    )
    for word in re.findall(r"[a-z]+", key)
)


@dataclass(frozen=True, slots=True)
class EventDate:
    """An event's date: its time in UTC, or only its local day.

    ``marks`` are the folded words that set the time: a part of the day or a
    time zone ("da tarde", "wet").
    """

    at: datetime | None
    day: date
    marks: tuple[str, ...] = ()


def read_event_date(value: object, now: datetime, tz: tzinfo) -> EventDate | None:
    """Return an event's date, never later than now; None when unreadable.

    Up to tomorrow a date is a carrier's clock ahead of ours and becomes now;
    a later one is wrong and gives None. When words after the time aren't
    understood, only the day is known: ``at`` is None.
    """
    found = _read(value, now, tz)
    if found is None or found.day > _tomorrow(now, tz):
        return None
    if found.at is None:
        return EventDate(None, min(found.day, now.astimezone(tz).date()))
    at = min(found.at, now.astimezone(UTC))
    return EventDate(at, at.astimezone(tz).date(), found.marks)


def parse_event_date(value: object, now: datetime, tz: tzinfo) -> datetime | None:
    """Return an event's date in UTC, never later than now.

    None when it's unreadable, after tomorrow or only a day.
    """
    found = read_event_date(value, now, tz)
    return None if found is None else found.at


def is_future_date(value: object, now: datetime, tz: tzinfo) -> bool:
    """Return whether an event's date reads as a day after tomorrow."""
    found = _read(value, now, tz)
    return found is not None and found.day > _tomorrow(now, tz)


def date_shape(value: object) -> str:
    """Describe an unreadable date without its text, for diagnostics.

    Digits become 9, date words stay, any other run of words becomes one x,
    and other characters stay when they're ASCII punctuation, else "?". The
    last word stays too when it has at most six letters and dots and follows
    the digits ("9:99 wet", "(est.)"): such markers say how the time is told.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "number"
    if not isinstance(value, str):
        return "object"
    folded = fold(value[:_SHAPE_INPUT])
    pieces: list[str] = []
    last = _LAST_WORD_RE.search(folded) if len(value) <= _SHAPE_INPUT else None
    if (
        last is not None
        and any(char.isdigit() for char in folded[: last.start(1)])
        and any(char.isalpha() for char in last.group(1))
    ):
        _shape_pieces(folded[: last.start(1)], pieces)
        pieces.append(last.group(1))
        _shape_pieces(folded[last.end(1) :], pieces)
    else:
        _shape_pieces(folded, pieces)
    shape = "".join(pieces).strip()
    if not shape:
        return "empty"
    if len(shape) > SHAPE_LENGTH or len(value) > _SHAPE_INPUT:
        return shape[:SHAPE_LENGTH] + "..."
    return shape


def _shape_pieces(text: str, pieces: list[str]) -> None:
    """Add the shape of ``text`` to ``pieces``."""
    for match in _SHAPE_RE.finditer(text):
        digits, word, space, other = match.groups()
        if digits:
            piece = "9" * len(digits)
        elif word:
            piece = word if word in _DATE_WORDS else "x"
        elif space:
            piece = " "
        else:
            piece = other if other in string.punctuation else "?"
        if piece == "x" and pieces[-2:] == ["x", " "]:
            pieces.pop()
            continue
        pieces.append(piece)


def _read(value: object, now: datetime, tz: tzinfo) -> EventDate | None:
    """Return an event's date as written, not checked against now."""
    if not isinstance(value, str) or len(value) > MAX_LENGTH:
        return None
    text = value.strip()
    if _ISO_RE.match(text):
        if (parsed := _iso(text)) is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return EventDate(parsed.astimezone(UTC), parsed.astimezone(tz).date())
    if (spelled := _spell_numeric(text)) is None:
        return None
    return _text_date(spelled, _tomorrow(now, tz), tz)


def _tomorrow(now: datetime, tz: tzinfo) -> date:
    return now.astimezone(tz).date() + timedelta(days=1)


def _spell_numeric(text: str) -> str | None:
    """Spell out a day-first numeric date ("16/11/2026" -> "16 november 2026").

    The rest of the text is read as usual; two numeric dates give None.
    """
    matches = list(_NUMERIC_RE.finditer(text))
    if not matches:
        return text
    if len(matches) > 1:
        return None
    match = matches[0]
    day, _, month, year = match.groups()
    if not 1 <= int(month) <= 12:
        return None
    words = f" {int(day)} {_MONTH_NAMES[int(month) - 1]} {year} "
    return text[: match.start()] + words + text[match.end() :]


def parse_expected(delivery: Mapping[str, Any], tz: tzinfo) -> Eta | None:
    """Return the expected delivery date, range or time window."""
    start = _expected(delivery, "timestamp_expected", "date_expected", tz)
    end = _expected(delivery, "timestamp_expected_end", "date_expected_end", tz)
    if start is None:
        if end is None:
            return None
        window_end = end.time() if end.time() != _MIDNIGHT else None
        return Eta(end.date(), end.date(), None, window_end)
    day = start.date()
    if end is None or end < start:
        return Eta(day, day)
    if end.date() != day:
        return Eta(day, end.date())
    if start.time() == _MIDNIGHT:
        if end.time() == _MIDNIGHT:
            return Eta(day, day)
        return Eta(day, day, None, end.time())
    if end > start:
        return Eta(day, day, start.time(), end.time())
    return Eta(day, day)


def _iso(text: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if MIN_YEAR <= parsed.year <= MAX_YEAR else None


def _expected(
    delivery: Mapping[str, Any], timestamp_key: str, date_key: str, tz: tzinfo
) -> datetime | None:
    """Return one side of the expected delivery as a naive local time."""
    stamp = _timestamp(delivery.get(timestamp_key), tz)
    if stamp is not None:
        return stamp
    value = delivery.get(date_key)
    if not isinstance(value, str) or len(value) > MAX_LENGTH:
        return None
    text = value.strip()
    if not _ISO_RE.match(text) or (parsed := _iso(text)) is None:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(tz).replace(tzinfo=None)
    return parsed


def _timestamp(value: object, tz: tzinfo) -> datetime | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and _TIMESTAMP_RE.fullmatch(value.strip()):
        value = float(value)
    if not isinstance(value, int | float) or not math.isfinite(value) or value <= 0:
        return None
    try:
        parsed = datetime.fromtimestamp(value, tz)
    except ValueError, OverflowError, OSError:
        return None
    if not MIN_YEAR <= parsed.year <= MAX_YEAR:
        return None
    return parsed.replace(tzinfo=None)


def _text_date(text: str, limit: date, tz: tzinfo) -> EventDate | None:
    """Read a date as the app shows it; a missing year is the latest one.

    Words after the time that aren't understood, or a part of the day that
    contradicts it, leave only the day, unless digits follow: they could be
    the date's.
    """
    tokens = _tokens(text)
    day: int | None = None
    year: int | None = None
    weekday: int | None = None
    clock: tuple[int, int, int] | None = None
    zone: tzinfo | None = None
    marks: list[str] = []
    months: list[tuple[int, int | None]] = []
    stop: int | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if match := _TIME_RE.fullmatch(token):
            if clock is not None:
                return None
            hour, minute, second = (int(part or 0) for part in match.groups())
            if hour > 23 or minute > 59 or second > 59:
                return None
            index += 1
            while index < len(tokens) and tokens[index] in _CLOCK_WORDS:
                index += 1
            if (period := _period(tokens, index, hour)) is not None:
                phrase, hours = period
                if len(chosen := _hours(hour) & hours) != 1:
                    stop = index
                    break
                (hour,) = chosen
                marks.append(" ".join(phrase))
                index += len(phrase)
            if (found_zone := _zone(tokens, index)) is not None:
                length, zone = found_zone
                marks.append(" ".join(tokens[index : index + length]))
                index += length
            clock = (hour, minute, second)
            continue
        if _YEAR_RE.fullmatch(token):
            if year is not None:
                return None
            year = int(token)
        elif match := _DAY_RE.fullmatch(token):
            if day is not None:
                return None
            day = int(match.group(1))
        elif token in _FILLER:
            pass
        elif token in WEEKDAYS:
            if weekday is not None:
                return None
            weekday = WEEKDAYS[token]
        elif token in MONTHS:
            # "mar" is both March and, in es/fr/it, Tuesday.
            months.append((MONTHS[token], WEEKDAY_ABBREVIATIONS.get(token)))
        elif token in WEEKDAY_ABBREVIATIONS:
            if weekday is not None:
                return None
            weekday = WEEKDAY_ABBREVIATIONS[token]
        elif clock is None:
            return None
        else:
            stop = index
            break
        index += 1
    if stop is not None and any(
        char.isdigit() for token in tokens[stop:] for char in token
    ):
        return None
    month, weekday = _month(months, weekday)
    if day is None or month is None or not 1 <= day <= 31:
        return None
    found = _day(day, month, year, weekday, limit)
    if found is None or not MIN_YEAR <= found.year <= MAX_YEAR:
        return None
    if stop is not None:
        return EventDate(None, found)
    hour, minute, second = clock or (0, 0, 0)
    moment = datetime.combine(found, time(hour, minute, second), tzinfo=zone or tz)
    return EventDate(moment.astimezone(UTC), moment.astimezone(tz).date(), tuple(marks))


def _tokens(text: str) -> list[str]:
    """Split a date into folded words; apostrophes are spaces ("'s avonds")."""
    text = _MERIDIEM_RE.sub(r"\1 \2m", _APOSTROPHE_RE.sub(" ", fold(text)))
    return _SEPARATOR_RE.sub(" ", text).split()


def _period(
    tokens: list[str], index: int, hour: int
) -> tuple[tuple[str, ...], frozenset[int]] | None:
    """Return the longest part of the day at ``index``, and its hours."""
    for length in range(min(_PERIOD_LENGTH, len(tokens) - index), 0, -1):
        phrase = tuple(tokens[index : index + length])
        if (hours := _PERIODS.get(phrase)) is None:
            continue
        if phrase == ("am",) and hour > 12:
            # "15:21 am 14. November" is German.
            return None
        return phrase, hours
    return None


def _hours(hour: int) -> frozenset[int]:
    """Return the hours a written hour can be on a 12- or 24-hour clock."""
    if hour == 0 or hour > 12:
        return frozenset((hour,))
    return frozenset((hour % 12, hour % 12 + 12))


def _zone(tokens: list[str], index: int) -> tuple[int, tzinfo] | None:
    """Return the length and zone of a time zone at ``index``, if there's one."""
    if index >= len(tokens):
        return None
    token = tokens[index]
    if (
        token in ("gmt", "utc")
        and index + 1 < len(tokens)
        and (offset := _offset(tokens[index + 1])) is not None
    ):
        return 2, offset
    if token in _ZONES:
        return 1, timezone(timedelta(minutes=_ZONES[token]))
    if (offset := _offset(token)) is not None:
        return 1, offset
    return None


def _offset(token: str) -> tzinfo | None:
    """Return the zone of an offset ("+0100", "gmt-3", "utc+01:00")."""
    if (match := _OFFSET_RE.fullmatch(token)) is None:
        return None
    sign, hours, minutes = match.groups()
    if int(hours) > _MAX_OFFSET_HOURS or int(minutes or 0) > 59:
        return None
    offset = timedelta(hours=int(hours), minutes=int(minutes or 0))
    return timezone(-offset if sign == "-" else offset)


def _month(
    months: list[tuple[int, int | None]], weekday: int | None
) -> tuple[int | None, int | None]:
    """Return the month and weekday; of two month words the first is the day."""
    if len(months) == 1:
        return months[0][0], weekday
    if len(months) != 2:
        return None, weekday
    (first, first_day), (second, second_day) = months
    if first_day is not None and weekday is None:
        return second, first_day
    if second_day is not None and weekday is None:
        return first, second_day
    return None, weekday


def _day(
    day: int, month: int, year: int | None, weekday: int | None, limit: date
) -> date | None:
    if year is not None:
        try:
            found = date(year, month, day)
        except ValueError:
            return None
        return found if weekday is None or found.weekday() == weekday else None
    # The two latest dates up to tomorrow: the weekday tells between them.
    candidates: list[date] = []
    for candidate_year in range(limit.year, limit.year - 9, -1):
        try:
            found = date(candidate_year, month, day)
        except ValueError:
            continue
        if found <= limit:
            candidates.append(found)
            if len(candidates) == 2:
                break
    if weekday is None:
        return candidates[0] if candidates else None
    return next((found for found in candidates if found.weekday() == weekday), None)
