"""Tests for the dates in Parcel's answers."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.parcelapp.dates import (
    EventDate,
    date_shape,
    is_future_date,
    parse_event_date,
    parse_expected,
    read_event_date,
)
from custom_components.parcels.parsers.base import Eta

LISBON = ZoneInfo("Europe/Lisbon")
# Tuesday 17 November 2026, 10:00 in Lisbon (UTC+0 in winter, UTC+1 in summer).
NOW = datetime(2026, 11, 17, 10, 0, tzinfo=UTC)
DAY = date(2026, 11, 19)


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # ISO dates without an offset are local.
        ("2026-07-16 14:05:00", _utc(2026, 7, 16, 13, 5)),
        ("2026-07-16T14:05", _utc(2026, 7, 16, 13, 5)),
        ("2026-07-16", _utc(2026, 7, 15, 23, 0)),
        ("2026-11-16T14:05:00+01:00", _utc(2026, 11, 16, 13, 5)),
        ("2026-11-16T14:05:00Z", _utc(2026, 11, 16, 14, 5)),
        # As the app shows them.
        ("Saturday, 14 November 3:21 pm", _utc(2026, 11, 14, 15, 21)),
        ("Saturday, 14 November 12:30 am", _utc(2026, 11, 14, 0, 30)),
        ("Sat, 14 Nov 12:05 PM", _utc(2026, 11, 14, 12, 5)),
        ("November 14, 2026 at 3:21 p.m.", _utc(2026, 11, 14, 15, 21)),
        ("3:21 p.m., Sat 14 Nov", _utc(2026, 11, 14, 15, 21)),
        ("Saturday, 14 November", _utc(2026, 11, 14, 0, 0)),
        ("  July 16  ", _utc(2026, 7, 15, 23, 0)),
        ("sábado, 14 de novembro 15:21", _utc(2026, 11, 14, 15, 21)),
        ("sábado, 14 de novembro às 15h21", _utc(2026, 11, 14, 15, 21)),
        ("Samstag, 14. November 2026 um 15:21 Uhr", _utc(2026, 11, 14, 15, 21)),
        ("zaterdag 14 november om 15:21", _utc(2026, 11, 14, 15, 21)),
        # "mar" is Tuesday in Spanish and March in English.
        ("mar., 3 nov.", _utc(2026, 11, 3, 0, 0)),
        ("Mar 3", _utc(2026, 3, 3, 0, 0)),
    ],
)
def test_event_dates(value: str, expected: datetime) -> None:
    """Event dates are read in Home Assistant's time zone, in UTC."""
    assert parse_event_date(value, NOW, LISBON) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Portuguese, as the app shows it on a 12-hour clock.
        ("sábado, 7 de novembro 3:15 da tarde", _utc(2026, 11, 7, 15, 15)),
        ("sábado, 7 de novembro às 3:15 da tarde", _utc(2026, 11, 7, 15, 15)),
        ("sábado, 7 de novembro 9:05 da manhã", _utc(2026, 11, 7, 9, 5)),
        ("sábado, 7 de novembro 12:30 da tarde", _utc(2026, 11, 7, 12, 30)),
        ("sábado, 7 de novembro 12:30 da madrugada", _utc(2026, 11, 7, 0, 30)),
        ("sábado, 7 de novembro 12:30 da manhã", _utc(2026, 11, 7, 0, 30)),
        ("sábado, 7 de novembro 2:10 da madrugada", _utc(2026, 11, 7, 2, 10)),
        ("sábado, 7 de novembro 12:00 meio-dia", _utc(2026, 11, 7, 12, 0)),
        ("sábado, 7 de novembro 12:00 meia-noite", _utc(2026, 11, 7, 0, 0)),
        ("sábado, 7 de novembro 4:20 à tarde", _utc(2026, 11, 7, 16, 20)),
        ("sexta-feira, 13 de novembro 9:26 da noite", _utc(2026, 11, 13, 21, 26)),
        ("sábado, 7 de novembro 15:15 da tarde", _utc(2026, 11, 7, 15, 15)),
        # Spanish.
        ("sábado, 7 de noviembre 9:05 de la mañana", _utc(2026, 11, 7, 9, 5)),
        ("sábado, 7 de noviembre 4:20 de la tarde", _utc(2026, 11, 7, 16, 20)),
        ("sábado, 7 de noviembre 11:15 de la noche", _utc(2026, 11, 7, 23, 15)),
        ("sábado, 7 de noviembre 12:00 de la noche", _utc(2026, 11, 7, 0, 0)),
        ("sábado, 7 de noviembre 1:30 de la madrugada", _utc(2026, 11, 7, 1, 30)),
        ("sábado, 7 de noviembre 12:10 del mediodía", _utc(2026, 11, 7, 12, 10)),
        ("sábado, 7 de noviembre 1:15 del mediodía", _utc(2026, 11, 7, 13, 15)),
        # French.
        ("samedi 7 novembre 9:05 du matin", _utc(2026, 11, 7, 9, 5)),
        ("samedi 7 novembre 4:20 de l\u2019après-midi", _utc(2026, 11, 7, 16, 20)),
        ("samedi 7 novembre 4:20 de l'après-midi", _utc(2026, 11, 7, 16, 20)),
        ("samedi 7 novembre 8:45 du soir", _utc(2026, 11, 7, 20, 45)),
        ("samedi 7 novembre 12:30 de la nuit", _utc(2026, 11, 7, 0, 30)),
        ("samedi 7 novembre 12:00 midi", _utc(2026, 11, 7, 12, 0)),
        # Italian.
        ("sabato 7 novembre 9:05 di mattina", _utc(2026, 11, 7, 9, 5)),
        ("sabato 7 novembre 4:20 del pomeriggio", _utc(2026, 11, 7, 16, 20)),
        ("sabato 7 novembre 8:45 di sera", _utc(2026, 11, 7, 20, 45)),
        ("sabato 7 novembre 2:10 di notte", _utc(2026, 11, 7, 2, 10)),
        ("sabato 7 novembre 12:00 mezzanotte", _utc(2026, 11, 7, 0, 0)),
        # German.
        ("Samstag, 14. November 9:05 morgens", _utc(2026, 11, 14, 9, 5)),
        ("Samstag, 14. November 1:00 mittags", _utc(2026, 11, 14, 13, 0)),
        ("Samstag, 14. November 4:20 nachmittags", _utc(2026, 11, 14, 16, 20)),
        ("Samstag, 14. November 8:45 abends", _utc(2026, 11, 14, 20, 45)),
        ("Samstag, 14. November 2:10 nachts", _utc(2026, 11, 14, 2, 10)),
        # A German "am" before the day isn't a.m.
        ("15:25 am 14. November", _utc(2026, 11, 14, 15, 25)),
        # Dutch.
        ("zaterdag 14 november 9:05 \u2019s ochtends", _utc(2026, 11, 14, 9, 5)),
        ("zaterdag 14 november 4:20 's middags", _utc(2026, 11, 14, 16, 20)),
        ("zaterdag 14 november 8:45 \u2019s avonds", _utc(2026, 11, 14, 20, 45)),
        ("zaterdag 14 november 2:10 \u2019s nachts", _utc(2026, 11, 14, 2, 10)),
        # English.
        ("Saturday, 14 November 9:05 in the morning", _utc(2026, 11, 14, 9, 5)),
        ("Saturday, 14 November 4:20 in the afternoon", _utc(2026, 11, 14, 16, 20)),
        ("Saturday, 14 November 8:45 in the evening", _utc(2026, 11, 14, 20, 45)),
        ("Saturday, 14 November 11:30 at night", _utc(2026, 11, 14, 23, 30)),
        ("Saturday, 14 November 12:00 noon", _utc(2026, 11, 14, 12, 0)),
        ("Saturday, 14 November 12:00 midnight", _utc(2026, 11, 14, 0, 0)),
    ],
)
def test_parts_of_the_day(value: str, expected: datetime) -> None:
    """A 12-hour time takes its part of the day, in the seven languages."""
    assert parse_event_date(value, NOW, LISBON) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Saturday, 14 November 3:21 pm WET", _utc(2026, 11, 14, 15, 21)),
        ("Saturday, 14 November 3:21 pm GMT", _utc(2026, 11, 14, 15, 21)),
        ("Saturday, 14 November 15:21 CET", _utc(2026, 11, 14, 14, 21)),
        ("Samstag, 14. November 15:21 MEZ", _utc(2026, 11, 14, 14, 21)),
        ("Saturday, 14 November 15:21 GMT+1", _utc(2026, 11, 14, 14, 21)),
        ("Saturday, 14 November 15:21 UTC+01:00", _utc(2026, 11, 14, 14, 21)),
        ("Saturday, 14 November 15:21 +0100", _utc(2026, 11, 14, 14, 21)),
        ("Saturday, 14 November 15:21 (GMT-3)", _utc(2026, 11, 14, 18, 21)),
        ("Saturday, 14 November 15:21 GMT +2", _utc(2026, 11, 14, 13, 21)),
        # Lisbon's summer time.
        ("Thursday, 16 July 3:21 pm WEST", _utc(2026, 7, 16, 14, 21)),
        ("sábado, 7 de novembro 3:15 da tarde WET", _utc(2026, 11, 7, 15, 15)),
        ("16/11/2026 15:10 UTC", _utc(2026, 11, 16, 15, 10)),
    ],
)
def test_time_zones(value: str, expected: datetime) -> None:
    """A time zone after the time wins over Home Assistant's."""
    assert parse_event_date(value, NOW, LISBON) == expected


def test_read_event_date() -> None:
    """A reading keeps the local day, and the words that set the time."""
    assert read_event_date(
        "sábado, 7 de novembro 3:15 da tarde", NOW, LISBON
    ) == EventDate(_utc(2026, 11, 7, 15, 15), date(2026, 11, 7), ("da tarde",))
    assert read_event_date(
        "Saturday, 14 November 3:21 pm WET", NOW, LISBON
    ) == EventDate(_utc(2026, 11, 14, 15, 21), date(2026, 11, 14), ("pm", "wet"))
    assert read_event_date("2026-07-16", NOW, LISBON) == EventDate(
        _utc(2026, 7, 15, 23, 0), date(2026, 7, 16)
    )
    assert read_event_date("18/11/2026 09:00", NOW, LISBON) == EventDate(
        NOW, date(2026, 11, 17)
    )
    assert read_event_date("soon", NOW, LISBON) is None
    assert read_event_date("2026-11-19", NOW, LISBON) is None


@pytest.mark.parametrize(
    ("value", "day"),
    [
        # Words after the time that aren't understood: the time is unsure.
        ("sábado, 7 de novembro 3:15 qwerty", date(2026, 11, 7)),
        ("sábado, 7 de novembro 3:15 qwerty uiop", date(2026, 11, 7)),
        ("16/11/2026 15:10 extra", date(2026, 11, 16)),
        ("Saturday, 14 November 15:21 pst", date(2026, 11, 14)),
        ("Saturday, 14 November 3:21 pm (estimated)", date(2026, 11, 14)),
        ("Saturday, 14 November 3:21 pm at the depot", date(2026, 11, 14)),
        # A part of the day that contradicts the time.
        ("sábado, 7 de novembro 1:30 da noite", date(2026, 11, 7)),
        ("14 November 0:30 pm", date(2026, 11, 14)),
        # Tomorrow is today: a carrier's clock ahead of ours.
        ("18/11/2026 10:00 xyz", date(2026, 11, 17)),
    ],
)
def test_day_only_event_dates(value: str, day: date) -> None:
    """When only the time is unsure, the day is still read."""
    assert read_event_date(value, NOW, LISBON) == EventDate(None, day)
    assert parse_event_date(value, NOW, LISBON) is None
    assert not is_future_date(value, NOW, LISBON)


@pytest.mark.parametrize(
    "value",
    [
        "14 November near 3 pm",
        "15:21 xyz, Saturday 14 November",
        "Saturday, 14 November 15:21 by 16 November",
        "Wednesday, 14 November 3:15 xyz",
        "15:21 GMT+25, 14 November",
        "Saturday, 14 November 15:21 GMT+25",
        "Saturday, 14 November 3:15 da tarde 16:00",
    ],
)
def test_no_day_when_unsure(value: str) -> None:
    """Text not understood gives no day when it could hold the date."""
    assert read_event_date(value, NOW, LISBON) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Tomorrow is still this year (a carrier ahead of us), but not later.
        ("18 November", NOW),
        ("19 November", _utc(2025, 11, 19, 0, 0)),
        ("20 December 10:00", _utc(2025, 12, 20, 10, 0)),
        # The weekday tells the year.
        ("Friday, 14 November 1:00 am", _utc(2025, 11, 14, 1, 0)),
        ("29 February", _utc(2024, 2, 29, 0, 0)),
    ],
)
def test_event_years(value: str, expected: datetime) -> None:
    """A date without a year is the latest one up to tomorrow."""
    assert parse_event_date(value, NOW, LISBON) == expected


def test_event_dates_never_in_the_future() -> None:
    """A carrier's clock ahead of ours doesn't date an event after now."""
    assert parse_event_date("2026-11-17 18:00:00", NOW, LISBON) == NOW
    assert parse_event_date("18/11/2026 09:00", NOW, LISBON) == NOW


@pytest.mark.parametrize(
    "value",
    [
        "2026-11-19 10:00:00",
        "2026-11-19",
        "19/11/2026",
        "Thursday, 19 November 2026",
        "2027-01-05T08:00:00Z",
        "19/11/2026 10:00 xyz",
    ],
)
def test_future_event_dates_give_no_date(value: str) -> None:
    """A date after tomorrow is wrong: it isn't moved to now."""
    assert parse_event_date(value, NOW, LISBON) is None
    assert is_future_date(value, NOW, LISBON)


@pytest.mark.parametrize(
    "value",
    [None, 42, "", "soon", "2026-11-18 23:00:00", "16/11/2026", "19 November"],
)
def test_not_future_dates(value: Any) -> None:
    """Unreadable dates, and dates up to tomorrow, aren't in the future."""
    assert not is_future_date(value, NOW, LISBON)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("16/11/2026", _utc(2026, 11, 16, 0, 0)),
        ("16/11/2026 14:05", _utc(2026, 11, 16, 14, 5)),
        ("16-11-2026 14:05:30", _utc(2026, 11, 16, 14, 5, 30)),
        ("16.11.2026 14:05", _utc(2026, 11, 16, 14, 5)),
        ("16.11.2026, 14:05", _utc(2026, 11, 16, 14, 5)),
        ("16/11/2026 às 14h05", _utc(2026, 11, 16, 14, 5)),
        ("16/11/2026 2:05 pm", _utc(2026, 11, 16, 14, 5)),
        ("14:05 16/11/2026", _utc(2026, 11, 16, 14, 5)),
        ("Segunda-feira, 16/11/2026 14:05", _utc(2026, 11, 16, 14, 5)),
        ("16.11.2026 um 14:05 Uhr", _utc(2026, 11, 16, 14, 5)),
        # Lisbon is UTC+1 in July.
        ("6/7/2026 9:05", _utc(2026, 7, 6, 8, 5)),
        ("06.07.2026", _utc(2026, 7, 5, 23, 0)),
    ],
)
def test_numeric_day_first_dates(value: str, expected: datetime) -> None:
    """Carriers' numeric dates are day first, with a four-digit year."""
    assert parse_event_date(value, NOW, LISBON) == expected


@pytest.mark.parametrize(
    "value",
    [
        "16/11/26",
        "16/11-2026",
        "2026/11/16",
        "32/11/2026",
        "16/13/2026",
        "11/16/2026",
        "31/02/2026",
        "16/11/2026 25:00",
        "16/11/2026 14:05 extra",
        "16/11/2026 17/11/2026",
        "Tuesday, 16/11/2026",
        "116/11/2026",
        "16/11/20261",
    ],
)
def test_unreadable_numeric_dates(value: str) -> None:
    """Month-first, two-digit years and contradictions give no date."""
    assert parse_event_date(value, NOW, LISBON) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "null"),
        (True, "bool"),
        (1784448000, "number"),
        (1.5, "number"),
        ({"date": "x"}, "object"),
        (["x"], "object"),
        ("", "empty"),
        ("   ", "empty"),
        ("Entregue em 20/11/2026 às 14h05", "x 99/99/9999 as 99h99"),
        ("Today, 2:05 PM", "today, 9:99 pm"),
        ("ontem 14:05", "ontem 99:99"),
        ("Sexta-feira, 20 de Novembro", "sexta-feira, 99 de novembro"),
        ("20.11.2026 um 14:05 Uhr", "99.99.9999 um 99:99 uhr"),
        ("Delivered to Alex Example at the door", "x at the x"),
        ("2026-11-20T14:05:00Z", "9999-99-99t99:99:99z"),
        ("20 Nov → 14:05", "99 nov ? 99:99"),
        ("1" * 80, "9" * 60 + "..."),
        ("x" * 300, "x..."),
        # Parts of the day and time zones stay, and a short last word.
        ("sábado, 7 de novembro 3:15 da tarde", "sabado, 9 de novembro 9:99 da tarde"),
        ("Saturday, 14 November 3:21 pm WET", "saturday, 99 november 9:99 pm wet"),
        (
            "zaterdag 14 november 8:45 \u2019s avonds",
            "zaterdag 99 november 9:99 ?s avonds",
        ),
        (
            "samedi 7 novembre 4:20 de l'après-midi",
            "samedi 9 novembre 9:99 de l'apres-midi",
        ),
        ("sábado, 7 de novembro 3:15 qwerty", "sabado, 9 de novembro 9:99 qwerty"),
        ("sábado, 7 de novembro 3:15 abcdefg", "sabado, 9 de novembro 9:99 x"),
        ("sábado, 7 de novembro 3:15 qwerty uiop", "sabado, 9 de novembro 9:99 x uiop"),
        ("14/11/2026 3:15 (est.)", "99/99/9999 9:99 (est.)"),
        ("Order placed", "x"),
    ],
)
def test_date_shapes(value: Any, expected: str) -> None:
    """Shapes keep digits as 9 and date words, and no other text."""
    assert date_shape(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        42,
        "No date",
        "Order placed",
        "Saturday",
        # The weekday contradicts the date (this year and the year before).
        "Wednesday, 14 November",
        "Saturday, 14 November 2025",
        "14 November 15:21 pm 3",
        "0:30 pm, 14 November",
        "15:21",
        "6/12/2026",
        "31 February",
        "14 November near 3 pm",
        "14 November 15 November",
        "1999-12-31 10:00:00",
        "2026-13-01",
        "2026-11-16 25:00",
        "14 November 2126",
        "14 November " + "x" * 200,
    ],
)
def test_unreadable_event_dates(value: Any) -> None:
    """Anything else gives no date, never a guess."""
    assert parse_event_date(value, NOW, LISBON) is None


@pytest.mark.parametrize(
    ("delivery", "expected"),
    [
        ({"date_expected": "2026-11-19 00:00:00"}, Eta(DAY, DAY)),
        ({"date_expected": "2026-11-19"}, Eta(DAY, DAY)),
        # A lone time isn't a window.
        ({"date_expected": "2026-11-19 14:30:00"}, Eta(DAY, DAY)),
        (
            {
                "date_expected": "2026-11-19 00:00:00",
                "date_expected_end": "2026-11-21 00:00:00",
            },
            Eta(DAY, date(2026, 11, 21)),
        ),
        (
            {
                "date_expected": "2026-11-19 09:00:00",
                "date_expected_end": "2026-11-19 13:00",
            },
            Eta(DAY, DAY, time(9, 0), time(13, 0)),
        ),
        # From midnight: delivered by the end time.
        (
            {
                "date_expected": "2026-11-19 00:00:00",
                "date_expected_end": "2026-11-19 18:00:00",
            },
            Eta(DAY, DAY, None, time(18, 0)),
        ),
        (
            {"date_expected_end": "2026-11-19 18:00:00"},
            Eta(DAY, DAY, None, time(18, 0)),
        ),
        # An end before the start is ignored.
        (
            {
                "date_expected": "2026-11-19 13:00:00",
                "date_expected_end": "2026-11-19 09:00:00",
            },
            Eta(DAY, DAY),
        ),
        (
            {
                "date_expected": "2026-11-19 00:00:00",
                "date_expected_end": "2026-11-18 00:00:00",
            },
            Eta(DAY, DAY),
        ),
        # Timestamps are exact and win; Lisbon is UTC+1 in July.
        (
            {
                "date_expected": "2026-07-20 00:00:00",
                "timestamp_expected": 1784448000,
                "timestamp_expected_end": "1784462400",
            },
            Eta(date(2026, 7, 19), date(2026, 7, 19), time(9, 0), time(13, 0)),
        ),
        (
            {"date_expected": "2026-11-19 00:00:00", "timestamp_expected": 0},
            Eta(DAY, DAY),
        ),
    ],
)
def test_expected(delivery: dict[str, Any], expected: Eta) -> None:
    """The expected date, range or window, in local time."""
    assert parse_expected(delivery, LISBON) == expected


@pytest.mark.parametrize(
    "delivery",
    [
        {},
        {"date_expected": ""},
        {"date_expected": None, "timestamp_expected": None},
        {"date_expected": "0000-00-00 00:00:00"},
        {"date_expected": "1970-01-01 00:00:00"},
        {"date_expected": "soon"},
        {"timestamp_expected": True},
        {"timestamp_expected": 10**15},
        {"timestamp_expected": "x"},
    ],
)
def test_no_expected(delivery: dict[str, Any]) -> None:
    """Placeholders and unreadable values give no date."""
    assert parse_expected(delivery, LISBON) is None
