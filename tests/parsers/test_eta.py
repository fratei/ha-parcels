"""Tests for delivery dates, ranges and time windows."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.parsers.eta import (
    add_business_days,
    find_eta,
    parse_eta,
    parse_time_window,
)

# Tuesday 17 November 2026; Lisbon is on UTC in November.
REF = datetime(2026, 11, 17, 9, 12, tzinfo=UTC)
# Wednesday 30 December 2026.
REF_YEAR_END = datetime(2026, 12, 30, 10, 0, tzinfo=UTC)
# Friday 20 November 2026.
REF_FRIDAY = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)


def _day(day: int, month: int = 11, year: int = 2026) -> date:
    return date(year, month, day)


def _dates(eta: Eta | None) -> tuple[date, date] | None:
    return None if eta is None else (eta.start, eta.end)


@pytest.mark.parametrize(
    "text",
    [
        "Tuesday, 18 November 2026",
        "terça-feira, 18 de novembro",
        "martes, 18 de noviembre",
        "Dienstag, 18. November",
        "mardi 18 novembre",
        "martedì 18 novembre",
        "dinsdag 18 november",
        "November 18",
        "Nov 18",
        "18 Nov",
        "Wed 18 Nov",
        "18 de nov.",
        "18 de novembro de 2026",
        "18/11/2026",
        "18/11",
        "18-11-2026",
        "18.11.2026",
        "18.11.",
        "2026-11-18",
    ],
)
def test_absolute_dates(text: str, tz: ZoneInfo) -> None:
    """Absolute dates parse with and without year and weekday."""
    assert _dates(parse_eta(text, REF, tz)) == (_day(18), _day(18))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("18\u201320 November", (_day(18), _day(20))),
        ("between 18 and 20 November", (_day(18), _day(20))),
        ("entre 18 e 20 de novembro", (_day(18), _day(20))),
        ("del 18 al 20 de noviembre", (_day(18), _day(20))),
        ("18. \u2013 20. November", (_day(18), _day(20))),
        ("du 18 au 20 novembre", (_day(18), _day(20))),
        ("dal 18 al 20 novembre", (_day(18), _day(20))),
        ("tussen 18 en 20 november", (_day(18), _day(20))),
        ("18 Nov - 20 Nov", (_day(18), _day(20))),
        ("Nov 30 - Dec 2", (_day(30), _day(2, 12))),
        ("30 - 2 December", (_day(30), _day(2, 12))),
        ("entre 30 e 2 de dezembro", (_day(30), _day(2, 12))),
        ("Thursday - Saturday", (_day(19), _day(21))),
        ("entre quinta e sábado", (_day(19), _day(21))),
        ("zwischen Donnerstag und Samstag", (_day(19), _day(21))),
    ],
)
def test_ranges(text: str, expected: tuple[date, date], tz: ZoneInfo) -> None:
    """Date and weekday ranges in all languages, also across a month."""
    assert _dates(parse_eta(text, REF, tz)) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2 January", (_day(2, 1, 2027), _day(2, 1, 2027))),
        ("2/1", (_day(2, 1, 2027), _day(2, 1, 2027))),
        ("23 December", (_day(23, 12), _day(23, 12))),
        ("Friday", (_day(1, 1, 2027), _day(1, 1, 2027))),
        ("Dec 30 - Jan 2", (_day(30, 12), _day(2, 1, 2027))),
        ("30 Dec \u2013 2 Jan", (_day(30, 12), _day(2, 1, 2027))),
        ("31/12 - 02/01", (_day(31, 12), _day(2, 1, 2027))),
        ("30 - 2 January", (_day(30, 12), _day(2, 1, 2027))),
        ("entre 30 de dezembro e 2 de janeiro", (_day(30, 12), _day(2, 1, 2027))),
        ("du 30 décembre au 2 janvier", (_day(30, 12), _day(2, 1, 2027))),
        ("3-5 business days", (_day(4, 1, 2027), _day(6, 1, 2027))),
    ],
)
def test_year_boundary(text: str, expected: tuple[date, date], tz: ZoneInfo) -> None:
    """Dates without a year around New Year get the nearest sensible year."""
    assert _dates(parse_eta(text, REF_YEAR_END, tz)) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10 November", _day(10)),
        ("15 November", _day(15)),
        ("9 November", _day(9, 11, 2027)),
        ("18/11/2025", _day(18, 11, 2025)),
    ],
)
def test_year_inference(text: str, expected: date, tz: ZoneInfo) -> None:
    """Up to a week in the past stays this year; an explicit year is kept."""
    assert _dates(parse_eta(text, REF, tz)) == (expected, expected)


@pytest.mark.parametrize(
    "text", ["31/11", "31 November", "30 February 2026", "", "no date here"]
)
def test_impossible_or_missing_dates(text: str, tz: ZoneInfo) -> None:
    """Impossible dates and text without a date give None."""
    assert parse_eta(text, REF, tz) is None


def test_reversed_range_keeps_order(tz: ZoneInfo) -> None:
    """A range whose start can't precede its end never yields start > end."""
    eta = parse_eta("20-18 November", REF, tz)
    assert eta is not None
    assert eta.start <= eta.end == _day(18)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Arriving Friday", _day(20)),
        ("Chega sexta-feira", _day(20)),
        ("by Friday", _day(20)),
        ("Tuesday", _day(17)),
        ("terça", _day(17)),
    ],
)
def test_weekdays(text: str, expected: date, tz: ZoneInfo) -> None:
    """A weekday alone is the next such day on or after the reference."""
    assert _dates(parse_eta(text, REF, tz)) == (expected, expected)


@pytest.mark.parametrize(
    ("text", "offset"),
    [
        ("today", 0),
        ("hoje", 0),
        ("hoy", 0),
        ("heute", 0),
        ("aujourd'hui", 0),
        ("oggi", 0),
        ("vandaag", 0),
        ("tomorrow", 1),
        ("amanhã", 1),
        ("mañana", 1),
        ("morgen", 1),
        ("demain", 1),
        ("domani", 1),
        ("day after tomorrow", 2),
        ("depois de amanhã", 2),
        ("pasado mañana", 2),
        ("übermorgen", 2),
        ("après-demain", 2),
        ("dopodomani", 2),
        ("overmorgen", 2),
        ("heute am Morgen", 0),
    ],
)
def test_relative_days(text: str, offset: int, tz: ZoneInfo) -> None:
    """Relative days in all languages count from the reference date."""
    expected = _day(17) + timedelta(days=offset)
    assert _dates(parse_eta(text, REF, tz)) == (expected, expected)


def test_german_morning_is_not_tomorrow(tz: ZoneInfo) -> None:
    """German "am Morgen" means in the morning, "Morgen ..." tomorrow."""
    assert parse_eta("am Morgen", REF, tz) is None
    eta = parse_eta("Morgen zwischen 9 und 12 Uhr", REF, tz)
    assert eta == Eta(_day(18), _day(18), time(9), time(12))


@pytest.mark.parametrize(
    "text",
    [
        "3-5 business days",
        "3 a 5 dias úteis",
        "3-5 días laborables",
        "3-5 días hábiles",
        "3\u20135 Werktage",
        "3 \u2013 5 Werktage",
        "3 à 5 jours ouvrés",
        "3 à 5 jours ouvrables",
        "3-5 giorni lavorativi",
        "3-5 werkdagen",
    ],
)
def test_business_days(text: str, tz: ZoneInfo) -> None:
    """Business-day spans skip weekends, from a Tuesday and from a Friday."""
    assert _dates(parse_eta(text, REF, tz)) == (_day(20), _day(24))
    assert _dates(parse_eta(text, REF_FRIDAY, tz)) == (_day(25), _day(27))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 business day", (_day(18), _day(18))),
        ("in 2 business days", (_day(19), _day(19))),
        ("within 2 business days", (_day(18), _day(19))),
        ("2-4 business days", (_day(19), _day(23))),
        ("3-5 days", (_day(20), _day(22))),
    ],
)
def test_day_spans(text: str, expected: tuple[date, date], tz: ZoneInfo) -> None:
    """Single business days, "within" spans and calendar-day spans."""
    assert _dates(parse_eta(text, REF, tz)) == expected


def test_add_business_days() -> None:
    """Saturdays and Sundays are skipped."""
    assert add_business_days(_day(20), 1) == _day(23)
    assert add_business_days(_day(17), 0) == _day(17)
    assert add_business_days(_day(21), 5) == _day(27)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Wednesday 18 November between 9am and 1pm",
            Eta(_day(18), _day(18), time(9), time(13)),
        ),
        ("18 Nov, 1:00 PM \u2013 2:00 PM", Eta(_day(18), _day(18), time(13), time(14))),
        ("tomorrow, 13:00 - 14:00", Eta(_day(18), _day(18), time(13), time(14))),
        (
            "amanhã, entre as 13:00 e as 14:00",
            Eta(_day(18), _day(18), time(13), time(14)),
        ),
        ("Thursday by 9pm", Eta(_day(19), _day(19), None, time(21))),
    ],
)
def test_dates_with_windows(text: str, expected: Eta, tz: ZoneInfo) -> None:
    """A time window next to the date is returned with it."""
    assert parse_eta(text, REF, tz) == expected


def test_reference_is_converted_to_local_time(tz: ZoneInfo) -> None:
    """The reference date is the e-mail date in the local time zone."""
    pacific = datetime(2026, 11, 17, 23, 30, tzinfo=timezone(timedelta(hours=-8)))
    assert _dates(parse_eta("tomorrow", pacific, tz)) == (_day(19), _day(19))
    naive = datetime(2026, 11, 17, 9, 12)
    assert _dates(parse_eta("tomorrow", naive, tz)) == (_day(18), _day(18))


@pytest.mark.parametrize(
    ("reference", "text", "expected"),
    [
        # 00:30 on Sunday 25 October in Lisbon, before the clocks go back.
        (datetime(2026, 10, 24, 23, 30, tzinfo=UTC), "today", _day(25, 10)),
        (datetime(2026, 10, 24, 23, 30, tzinfo=UTC), "tomorrow", _day(26, 10)),
        (datetime(2026, 10, 24, 23, 30, tzinfo=UTC), "Monday", _day(26, 10)),
        # Still Saturday 28 March in Lisbon; the clocks go forward that night.
        (datetime(2026, 3, 28, 23, 30, tzinfo=UTC), "amanhã", _day(29, 3)),
        # 00:30 on Monday 30 March in Lisbon, in summer time.
        (datetime(2026, 3, 29, 23, 30, tzinfo=UTC), "hoje", _day(30, 3)),
    ],
)
def test_dst_weeks(
    reference: datetime, text: str, expected: date, tz: ZoneInfo
) -> None:
    """Dates around the DST changes use the local date of the e-mail."""
    assert _dates(parse_eta(text, reference, tz)) == (expected, expected)


def test_business_days_over_dst_week(tz: ZoneInfo) -> None:
    """Business days across the March DST change and a weekend."""
    reference = datetime(2026, 3, 27, 12, 0, tzinfo=UTC)
    assert _dates(parse_eta("3-5 business days", reference, tz)) == (
        _day(1, 4),
        _day(3, 4),
    )


@pytest.mark.parametrize(
    "text",
    [
        "13:00 - 14:00",
        "13:00\u201314:00",
        "13h00-14h00",
        "13h-14h",
        "13.00 - 14.00 Uhr",
        "between 13:00 and 14:00",
        "entre as 13:00 e as 14:00",
        "entre las 13:00 y las 14:00",
        "zwischen 13:00 und 14:00 Uhr",
        "entre 13h00 et 14h00",
        "tra le 13:00 e le 14:00",
        "tussen 13:00 en 14:00",
        "1pm - 2pm",
        "1:00 PM \u2013 2:00 PM",
    ],
)
def test_time_windows(text: str) -> None:
    """Time windows in all languages and notations."""
    assert parse_time_window(text) == (time(13), time(14))


@pytest.mark.parametrize(
    "text",
    [
        "by 9pm",
        "até às 21:00",
        "antes de las 21:00",
        "bis 21 Uhr",
        "avant 21h",
        "entro le 21:00",
        "voor 21:00",
    ],
)
def test_open_ended_windows(text: str) -> None:
    """Open-ended windows return no start."""
    assert parse_time_window(text) == (None, time(21))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("from 9:00", (time(9), None)),
        ("ab 9 Uhr", (time(9), None)),
        ("dalle 9 alle 13", (time(9), time(13))),
        ("das 9h às 13h", (time(9), time(13))),
        ("de 9h a 13h", (time(9), time(13))),
        ("before noon", (None, time(12))),
        ("9am to noon", (time(9), time(12))),
        ("12:00 - 24:00", (time(12), time(23, 59))),
    ],
)
def test_other_windows(text: str, expected: tuple[time | None, time | None]) -> None:
    """Windows that start at a time, with hour words, noon and midnight."""
    assert parse_time_window(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Total 13.00 - 14.00 €",
        "Order total 24,90 €",
        "2-3 days",
        "valid 2026-11-18",
        "Call 21 000 0000",
    ],
)
def test_not_time_windows(text: str) -> None:
    """Prices, durations, dates and phone numbers are not windows."""
    assert parse_time_window(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Order placed: 16/11/2026\nArriving: Thursday", Eta(_day(19), _day(19))),
        ("Your parcel will be delivered on 19/11/2026.", Eta(_day(19), _day(19))),
        (
            "Hi Alex, your order (placed on 16 November) is arriving on Thursday.",
            Eta(_day(19), _day(19)),
        ),
        ("Arrives: Nov 19 - Nov 21", Eta(_day(19), _day(21))),
        ("Estimated delivery: 3-5 business days", Eta(_day(20), _day(24))),
        ("Expected delivery\n\nFriday, 20 November", Eta(_day(20), _day(20))),
        (
            "Arriving tomorrow\n13:00 - 14:00",
            Eta(_day(18), _day(18), time(13), time(14)),
        ),
        ("A sua encomenda chega amanhã.", Eta(_day(18), _day(18))),
        (
            "Entrega prevista:\nquinta-feira, 19 de novembro",
            Eta(_day(19), _day(19)),
        ),
        ("Tu pedido llegará el jueves.", Eta(_day(19), _day(19))),
        ("Entrega estimada: jueves, 19 de noviembre", Eta(_day(19), _day(19))),
        ("Llegada: entre el jueves y el sábado", Eta(_day(19), _day(21))),
        (
            "Voraussichtliche Zustellung: Donnerstag, 19.11.2026",
            Eta(_day(19), _day(19)),
        ),
        ("Ihr Paket wird morgen zugestellt.", Eta(_day(18), _day(18))),
        (
            "Ihr Paket wird voraussichtlich am Donnerstag, 19.11. zwischen 13 und"
            " 15 Uhr zugestellt.",
            Eta(_day(19), _day(19), time(13), time(15)),
        ),
        (
            "Livraison prévue le jeudi 19 novembre entre 13h00 et 14h00",
            Eta(_day(19), _day(19), time(13), time(14)),
        ),
        ("Votre colis arrivera demain.", Eta(_day(18), _day(18))),
        ("Consegna prevista: giovedì 19 novembre", Eta(_day(19), _day(19))),
        ("Il pacco arriverà domani.", Eta(_day(18), _day(18))),
        (
            "Verwachte bezorging: donderdag 19 november tussen 13:00 en 14:00",
            Eta(_day(19), _day(19), time(13), time(14)),
        ),
        ("Je pakket wordt morgen bezorgd.", Eta(_day(18), _day(18))),
        ("Bezorgd op donderdag 19 november", Eta(_day(19), _day(19))),
        (
            "Je pakket komt morgen tussen 13:00 en 15:00",
            Eta(_day(18), _day(18), time(13), time(15)),
        ),
        (
            "Delivery date: 19 November. Order date: 16 November",
            Eta(_day(19), _day(19)),
        ),
        (
            "Order date: 16 November. Delivery date: 19 November",
            Eta(_day(19), _day(19)),
        ),
        (
            "Your parcel will not be delivered today. New delivery date: Thursday",
            Eta(_day(19), _day(19)),
        ),
        (
            "Offer valid until 30/11. Delivery in 3-5 business days.",
            Eta(_day(20), _day(24)),
        ),
    ],
)
def test_find_eta_anchored(text: str, expected: Eta, tz: ZoneInfo) -> None:
    """Dates after delivery phrases in all languages are found."""
    assert find_eta(text, REF, tz) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Encomendado em 16/11/2026. Total 24,90 €",
        "Thanks for shopping with us.\n© 2026 Example Store · 01/01/2026",
        "Date of order: 18/11/2026\nDelivery address: Rua Exemplo 1",
        "Sendung verfolgen\nBestelldatum: 16.11.2026",
        "Estimated delivery date\nShipped on 16 November",
        "Free delivery tomorrow on orders over €30",
        "Entrega gratuita amanhã em encomendas acima de 30 €",
        "Your return label expires on 30/11",
        "Dit aanbod komt te vervallen op 30/11",
        "Your parcel won't arrive today.",
        "A encomenda não chega hoje.",
        "Tu pedido no llegará hoy.",
        "Das Paket wird heute nicht zugestellt",
        "Votre colis n'arrivera pas aujourd'hui.",
        "Il pacco non arriverà oggi.",
        "Je pakket wordt vandaag niet bezorgd.",
        "",
    ],
)
def test_find_eta_ignores_unanchored_dates(text: str, tz: ZoneInfo) -> None:
    """Order dates, footers, offers, deadlines and negations are no ETA."""
    assert find_eta(text, REF, tz) is None
