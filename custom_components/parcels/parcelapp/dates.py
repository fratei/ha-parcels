"""Dates in Parcel's answers.

Parcel gives an event's date as text without a time zone: ISO ("2026-11-14
15:21:00"), as the app shows it ("Saturday, 14 November 3:21 pm"), often
without the year, or as carriers write it, day first ("14/11/2026 15:21").
All are read in Home Assistant's time zone. The expected delivery comes as
local dates ("2026-11-19 00:00:00"), or as epoch timestamps when the carrier
gives its time zone.

Anything that doesn't read cleanly gives None, never a guess, and so does a
date after tomorrow: an event can't have happened yet. date_shape describes
an unreadable date for diagnostics without its text.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, time, timedelta, tzinfo
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
_MERIDIEM_RE = re.compile(r"(\d)\s*([ap])\.?\s?m\.?(?=[\s,;]|$)")
_SEPARATOR_RE = re.compile(r"[,.;]")
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

# Kept in the shapes of unreadable dates, with the month, weekday and filler
# words: relative days, am/pm, ordinal suffixes and ISO's "t" and "z".
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
    for key in (*MONTHS, *WEEKDAYS, *WEEKDAY_ABBREVIATIONS, *_FILLER, *_SHAPE_WORDS)
    for word in re.findall(r"[a-z]+", key)
)


def parse_event_date(value: object, now: datetime, tz: tzinfo) -> datetime | None:
    """Return an event's date in UTC, never later than now.

    Up to tomorrow a date is a carrier's clock ahead of ours and becomes now;
    a later one is wrong and gives None.
    """
    parsed = _event_date(value, now, tz)
    if parsed is None or _future(parsed, now, tz):
        return None
    return min(parsed, now.astimezone(UTC))


def is_future_date(value: object, now: datetime, tz: tzinfo) -> bool:
    """Return whether an event's date reads as a day after tomorrow."""
    parsed = _event_date(value, now, tz)
    return parsed is not None and _future(parsed, now, tz)


def date_shape(value: object) -> str:
    """Describe an unreadable date without its text, for diagnostics.

    Digits become 9, date words stay, any other run of words becomes one x,
    and other characters stay when they're ASCII punctuation, else "?".
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "number"
    if not isinstance(value, str):
        return "object"
    pieces: list[str] = []
    for match in _SHAPE_RE.finditer(fold(value[:_SHAPE_INPUT])):
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
    shape = "".join(pieces).strip()
    if not shape:
        return "empty"
    if len(shape) > SHAPE_LENGTH or len(value) > _SHAPE_INPUT:
        return shape[:SHAPE_LENGTH] + "..."
    return shape


def _event_date(value: object, now: datetime, tz: tzinfo) -> datetime | None:
    """Return an event's date in UTC, as written."""
    if not isinstance(value, str) or len(value) > MAX_LENGTH:
        return None
    text = value.strip()
    if _ISO_RE.match(text):
        parsed = _iso(text)
    elif (spelled := _spell_numeric(text)) is not None:
        parsed = _text_date(spelled, _tomorrow(now, tz), tz)
    else:
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(UTC)


def _tomorrow(now: datetime, tz: tzinfo) -> date:
    return now.astimezone(tz).date() + timedelta(days=1)


def _future(parsed: datetime, now: datetime, tz: tzinfo) -> bool:
    return parsed.astimezone(tz).date() > _tomorrow(now, tz)


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


def _text_date(text: str, limit: date, tz: tzinfo) -> datetime | None:
    """Read a date as the app shows it; a missing year is the latest one."""
    text = _SEPARATOR_RE.sub(" ", _MERIDIEM_RE.sub(r"\1 \2m", fold(text)))
    day: int | None = None
    year: int | None = None
    weekday: int | None = None
    clock: list[int] | None = None
    months: list[tuple[int, int | None]] = []
    after_time = False
    for token in text.split():
        if after_time and clock is not None and token in ("am", "pm"):
            after_time = False
            if not _meridiem(clock, token):
                return None
            continue
        after_time = False
        if match := _TIME_RE.fullmatch(token):
            if clock is not None:
                return None
            clock = [int(part or 0) for part in match.groups()]
            after_time = True
        elif _YEAR_RE.fullmatch(token):
            if year is not None:
                return None
            year = int(token)
        elif match := _DAY_RE.fullmatch(token):
            if day is not None:
                return None
            day = int(match.group(1))
        elif token in _FILLER:
            continue
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
        else:
            return None
    month, weekday = _month(months, weekday)
    if day is None or month is None or not 1 <= day <= 31:
        return None
    found = _day(day, month, year, weekday, limit)
    if found is None or not MIN_YEAR <= found.year <= MAX_YEAR:
        return None
    hour, minute, second = clock or (0, 0, 0)
    if hour > 23 or minute > 59 or second > 59:
        return None
    return datetime.combine(found, time(hour, minute, second), tzinfo=tz)


def _meridiem(clock: list[int], token: str) -> bool:
    """Apply am or pm to the time just read; False when it makes no sense."""
    hour = clock[0]
    if hour > 12:
        # "15:21 am 14. November" is German; "15:21 pm" can only be 15:21.
        return True
    if hour == 0:
        return token == "am"
    clock[0] = hour % 12 + (12 if token == "pm" else 0)
    return True


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
