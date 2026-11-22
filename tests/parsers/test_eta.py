"""Tests for delivery dates, ranges and time windows."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.parsers.eta import (
    add_business_days,
    date_expressions,
    find_collect_by,
    find_delivery_eta,
    find_eta,
    find_next_attempt,
    parse_eta,
    parse_time_window,
)

# Tuesday 17 November 2026; Lisbon is on UTC in November.
REF = datetime(2026, 11, 17, 9, 12, tzinfo=UTC)
# Wednesday 30 December 2026.
REF_YEAR_END = datetime(2026, 12, 30, 10, 0, tzinfo=UTC)
# Friday 20 November 2026.
REF_FRIDAY = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
# Monday 15 June 2026; Lisbon is on UTC+1 in June.
REF_JUNE = datetime(2026, 6, 15, 8, 30, tzinfo=UTC)


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
        ("26-28/11", (_day(26), _day(28))),
        ("26 a 28/11", (_day(26), _day(28))),
        ("26.-28.11.", (_day(26), _day(28))),
        ("26 - 28/11/2026", (_day(26), _day(28))),
        ("entre el jueves 19 y el sábado 21 de noviembre", (_day(19), _day(21))),
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
        ("within 3-5 days", (_day(20), _day(22))),
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
        "antes das 21:00",
        "antes das 21h",
        "vor 21:00 Uhr",
        "vor 21 Uhr",
    ],
)
def test_open_ended_windows(text: str) -> None:
    """Open-ended windows return no start."""
    assert parse_time_window(text) == (None, time(21))


@pytest.mark.parametrize(
    ("text", "lang", "window_end"),
    [
        ("quinta-feira, 19 de novembro, antes das 20:00", "pt", time(20)),
        ("Donnerstag, 19.11.2026, vor 12:00 Uhr", "de", time(12)),
    ],
)
def test_date_with_open_ended_window(
    text: str, lang: str, window_end: time, tz: ZoneInfo
) -> None:
    """A scheduled delivery "before" a time keeps the time as the window end."""
    assert parse_eta(text, REF, tz, lang) == Eta(_day(19), _day(19), None, window_end)


@pytest.mark.parametrize(
    "text",
    [
        "Bitte warten Sie, bis das 2. Paket ankommt",
        "vor 2 Tagen",
        "vor 3 Wochen bestellt",
    ],
)
def test_not_open_ended_windows(text: str) -> None:
    """Articles and durations after "bis", "vor" or "antes" aren't windows."""
    assert parse_time_window(text) is None


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
        (
            "Die Zustellung erfolgt zwischen dem 19. und 21. November.",
            Eta(_day(19), _day(21)),
        ),
        ("Entrega prevista: 26-28/11", Eta(_day(26), _day(28))),
        ("Lieferung: 26.-28.11.", Eta(_day(26), _day(28))),
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


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Your delivery on 20 November has been rescheduled to 24 November.", "en"),
        ("Entrega de 20/11 adiada. Nova data: 24/11.", "pt"),
        ("Tu entrega del 20/11 se ha aplazado al 24/11.", "es"),
        ("Ursprünglich geplant war der 20.11., neuer Termin ist der 24.11.", "de"),
        (
            "Livraison prévue le 20/11 reportée. Nouvelle date de livraison : 24/11.",
            "fr",
        ),
        ("La consegna prevista per il 20/11 è stata posticipata al 24/11.", "it"),
        ("De bezorging stond gepland op 20/11 en is verplaatst naar 24/11.", "nl"),
    ],
)
def test_find_eta_takes_the_new_date(text: str, lang: str, tz: ZoneInfo) -> None:
    """A new or moved-to date wins over the date it replaces."""
    assert _dates(find_eta(text, REF, tz, lang)) == (_day(24), _day(24))
    assert _dates(find_delivery_eta(text, REF, tz, lang)) == (_day(24), _day(24))


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        (
            "Rescheduled to a later slot after the storm of 20 November. "
            "Arriving: 24 November.",
            "en",
        ),
        (
            "Nueva fecha: la tienda cierra por inventario el 20/11. Llegada: 24/11.",
            "es",
        ),
    ],
)
def test_new_date_phrase_needs_a_close_date(text: str, lang: str, tz: ZoneInfo) -> None:
    """A new-date phrase only takes a date at most three words after it."""
    assert _dates(find_eta(text, REF, tz, lang)) == (_day(24), _day(24))


@pytest.mark.parametrize(
    ("text", "lang", "day"),
    [
        ("Pode levantá-la até 25/11.", "pt", _day(25)),
        ("A encomenda fica disponível até 25/11 para levantar.", "pt", _day(25)),
        ("Pode devolvê-la até 18/12.", "pt", _day(18, 12)),
        ("Tienes hasta el 28/11 para recogerlo.", "es", _day(28)),
        ("Sie können es bis zum 25.11. abholen.", "de", _day(25)),
        ("Please pay the import VAT by 25/11.", "en", _day(25)),
        ("Votre colis est disponible jusqu'au 25/11 au point relais.", "fr", _day(25)),
        ("Il pacco resterà in giacenza fino al 25/11.", "it", _day(25)),
        ("Je kunt het pakket tot 25/11 ophalen.", "nl", _day(25)),
    ],
)
def test_deadlines(text: str, lang: str, day: date, tz: ZoneInfo) -> None:
    """Dates to collect, return or pay by, and hold periods, are deadlines."""
    (found,) = date_expressions(text, REF, tz, lang)
    assert (found.start, found.end) == (day, day)
    assert found.deadline
    assert not found.other


@pytest.mark.parametrize(
    ("text", "lang", "other"),
    [
        ("Bestelldatum: 16.11.2026", "de", [True]),
        ("Shipped on 16 November", "en", [True]),
        (
            "A entrega prevista para 20/11 foi adiada. Nova data de entrega: 24/11.",
            "pt",
            [True, False],
        ),
        ("Neuer Liefertermin: 24.11. (bisher 20.11.)", "de", [False, True]),
        (
            "Die Zustellung wurde vom 20.11. auf den 24.11. verschoben.",
            "de",
            [True, False],
        ),
        ("De bezorging is van 20/11 naar 24/11 verplaatst.", "nl", [True, False]),
        ("Entrega prevista: 20/11.", "pt", [False]),
    ],
)
def test_other_dates(text: str, lang: str, other: list[bool], tz: ZoneInfo) -> None:
    """Order, shipping and replaced dates are other dates; a delivery isn't."""
    found = date_expressions(text, REF, tz, lang)
    assert [expression.other for expression in found] == other
    assert not any(expression.deadline for expression in found)


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Expected delivery was 20 November, but your parcel is delayed.", "en"),
        ("A entrega prevista era 20/11, mas a encomenda está atrasada.", "pt"),
        ("La entrega prevista era el 20/11, pero tu paquete se ha retrasado.", "es"),
        ("Der geplante Liefertermin war der 20.11., Ihr Paket verspätet sich.", "de"),
        ("La livraison prévue était le 20/11, mais votre colis a du retard.", "fr"),
        ("La consegna prevista era il 20/11, ma il pacco è in ritardo.", "it"),
        ("De verwachte bezorgdatum was 20/11, maar je pakket is vertraagd.", "nl"),
    ],
)
def test_past_date_is_other(text: str, lang: str, tz: ZoneInfo) -> None:
    """A date right after a past "was" is no pending delivery date."""
    (found,) = date_expressions(text, REF, tz, lang)
    assert found.other
    assert find_delivery_eta(text, REF, tz, lang) is None


@pytest.mark.parametrize(
    ("text", "lang", "expected"),
    [
        ("A entrega prevista para 20/11 foi adiada.", "pt", None),
        ("La entrega prevista para el 20/11 se ha aplazado.", "es", None),
        ("Die Zustellung am 20.11. wurde verschoben.", "de", None),
        ("La livraison prévue le 20/11 a été reportée.", "fr", None),
        ("La consegna prevista per il 20/11 è stata rinviata.", "it", None),
        ("De bezorging van 20/11 is uitgesteld.", "nl", None),
        (
            "Entrega prevista: 20/11. Pode devolvê-la até 18/12.",
            "pt",
            (_day(20), _day(20)),
        ),
        (
            "Expected delivery was 20 November. It will now arrive on 24 November.",
            "en",
            (_day(24), _day(24)),
        ),
    ],
)
def test_find_delivery_eta(
    text: str, lang: str, expected: tuple[date, date] | None, tz: ZoneInfo
) -> None:
    """Replaced dates are skipped; the delivery date is still found."""
    assert _dates(find_delivery_eta(text, REF, tz, lang)) == expected


def _june(day: int, month: int = 6) -> date:
    return date(2026, month, day)


@pytest.mark.parametrize(
    ("text", "lang", "expected"),
    [
        ("A sua encomenda está no cacifo. Levante até 26/06.", "pt", _june(26)),
        ("Prazo de levantamento: 23/06/2026", "pt", _june(23)),
        ("O seu pacote está disponível na loja até 22/06.", "pt", _june(22)),
        (
            "Disponível para levantamento a partir de amanhã, 16-06-2026, "
            "durante 10 dias úteis.",
            "pt",
            _june(29),
        ),
        (
            "Tu paquete te espera en el punto de recogida. "
            "Recógelo antes del 25 de junio.",
            "es",
            _june(25),
        ),
        ("Plazo de recogida: 25/06/2026", "es", _june(25)),
        (
            "Your parcel is waiting at the locker. Collect it by Friday.",
            "en",
            _june(19),
        ),
        ("Please pick up your package before 26 June.", "en", _june(26)),
        ("Ihr Paket liegt bis zum 23.06. zur Abholung bereit.", "de", _june(23)),
        ("Abholfrist: 26.06.2026", "de", _june(26)),
        ("Lagerfrist bis 26.06.2026", "de", _june(26)),
        ("Votre colis est à retirer avant le 27 juin.", "fr", _june(27)),
        ("Délai de retrait : 25/06/2026", "fr", _june(25)),
        ("Il pacco resterà in giacenza fino al 29 giugno.", "it", _june(29)),
        ("Termine per il ritiro: 26/06/2026", "it", _june(26)),
        ("Je pakket ligt tot 25 juni klaar om op te halen.", "nl", _june(25)),
        ("Uiterste ophaaldatum: 25-06-2026", "nl", _june(25)),
        (
            "Votre colis est mis à disposition au point relais jusqu'au 25 juin.",
            "fr",
            _june(25),
        ),
        ("Ihr Paket liegt in der Filiale bis zum 26.06. bereit.", "de", _june(26)),
        (
            "Je pakket ligt voor je klaar bij het afhaalpunt tot en met 25 juni.",
            "nl",
            _june(25),
        ),
    ],
)
def test_find_collect_by(text: str, lang: str, expected: date, tz: ZoneInfo) -> None:
    """The last day to collect a parcel, in the 7 languages."""
    assert find_collect_by(text, REF_JUNE, tz, lang, pickup=True) == expected
    assert find_collect_by(text, REF_JUNE, tz, lang) == expected
    assert find_collect_by(text, REF_JUNE, tz, None, pickup=True) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Data limite: 23/06/2026", _june(23)),
        ("Disponível até 01/07/2026", _june(1, 7)),
    ],
)
def test_collect_by_needs_a_pickup_for_plain_deadlines(
    text: str, expected: date, tz: ZoneInfo
) -> None:
    """A deadline that doesn't say "collect" counts only on pickup notices."""
    assert find_collect_by(text, REF_JUNE, tz, "pt", pickup=True) == expected
    assert find_collect_by(text, REF_JUNE, tz, "pt") is None


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Desconto de 10% disponível até 30/06.", "pt"),
        ("Pague os direitos aduaneiros até 25/06 para receber a encomenda.", "pt"),
        ("Pode devolver o artigo até 30/06.", "pt"),
        ("Disponível para devolução até 30/06.", "pt"),
        ("Prazo de entrega: 19/06/2026", "pt"),
        ("Lieferfrist: 19.06.2026", "de"),
        ("Levante até 30/09/2026.", "pt"),
        ("Levante até 10/06/2026.", "pt"),
        ("Disponível desde hoje às 09:15.", "pt"),
        ("Free delivery on orders until 30 June.", "en"),
        (
            "Envía tus paquetes desde cualquier punto pickup con un 25% de "
            "descuento hasta el 30/06.",
            "es",
        ),
    ],
)
def test_collect_by_skips_other_deadlines(text: str, lang: str, tz: ZoneInfo) -> None:
    """Offers, duties, returns, delivery deadlines, past and far dates."""
    assert find_collect_by(text, REF_JUNE, tz, lang, pickup=True) is None


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        (
            "Your parcel will be available for collection at the locker by "
            "Tuesday 23 June.",
            "en",
        ),
        ("Your parcel will be available for pickup by 23/06.", "en"),
        (
            "A sua encomenda estará disponível para levantamento o mais tardar "
            "a 23/06.",
            "pt",
        ),
        ("Tu paquete estará disponible para recoger antes del 23/06.", "es"),
        (
            "Ihr Paket wird spätestens am 23.06. in der Filiale zur Abholung "
            "bereitliegen.",
            "de",
        ),
        ("Votre colis sera disponible en point relais au plus tard le 23/06.", "fr"),
        (
            "Votre colis sera mis à disposition dans votre point relais au plus "
            "tard le 23/06.",
            "fr",
        ),
        ("Il pacco sarà disponibile per il ritiro entro il 23/06.", "it"),
        ("Je pakket ligt uiterlijk 23 juni klaar bij het afhaalpunt.", "nl"),
    ],
)
def test_available_by_is_an_arrival(text: str, lang: str, tz: ZoneInfo) -> None:
    """Available "by" a date is when it arrives, not the last day to collect."""
    assert find_collect_by(text, REF_JUNE, tz, lang, pickup=True) is None
    assert find_collect_by(text, REF_JUNE, tz, None) is None


@pytest.mark.parametrize(
    ("text", "lang", "expected"),
    [
        (
            "Não foi possível entregar a sua encomenda. "
            "Nova tentativa: quarta-feira, 17 de junho.",
            "pt",
            _june(17),
        ),
        (
            "No hemos podido entregar tu paquete. Volveremos a intentarlo el 17/06.",
            "es",
            _june(17),
        ),
        ("We missed you today. We'll try again tomorrow.", "en", _june(16)),
        ("Next attempt:\nWednesday 17 June", "en", _june(17)),
        (
            "Wir haben Sie nicht angetroffen. "
            "Der nächste Zustellversuch erfolgt am 17.06.",
            "de",
            _june(17),
        ),
        (
            "Nous sommes passés en votre absence. "
            "Nouvelle tentative de livraison le 17 juin.",
            "fr",
            _june(17),
        ),
        (
            "Non eri in casa. "
            "Il prossimo tentativo di consegna è previsto per il 17 giugno.",
            "it",
            _june(17),
        ),
        (
            "We hebben je gemist. De volgende bezorgpoging is op woensdag 17 juni.",
            "nl",
            _june(17),
        ),
        ("Ausente. Nueva entrega mañana.", "es", _june(16)),
        ("Volveremos a pasar el miércoles.", "es", _june(17)),
        ("Destinatário ausente. Voltaremos a passar amanhã.", "pt", _june(16)),
        ("Le livreur repassera demain.", "fr", _june(16)),
        ("Il corriere ripasserà mercoledì.", "it", _june(17)),
        ("Wir versuchen es morgen erneut.", "de", _june(16)),
        ("We proberen het morgen opnieuw.", "nl", _june(16)),
    ],
)
def test_find_next_attempt(text: str, lang: str, expected: date, tz: ZoneInfo) -> None:
    """The day of the next delivery attempt, in the 7 languages."""
    assert find_next_attempt(text, REF_JUNE, tz, lang) == expected
    assert find_next_attempt(text, REF_JUNE, tz, None) == expected
    # The date in the text wins over the parser's estimate.
    assert find_next_attempt(text, REF_JUNE, tz, lang, eta_start=_june(18)) == expected


def test_next_attempt_without_a_date_takes_the_estimate(tz: ZoneInfo) -> None:
    """A planned attempt with no date of its own is on the estimated day."""
    text = "We'll try again soon."
    assert find_next_attempt(text, REF_JUNE, tz, "en", eta_start=_june(18)) == _june(18)
    assert find_next_attempt(text, REF_JUNE, tz, "en") is None
    # Not too far ahead.
    assert find_next_attempt(text, REF_JUNE, tz, "en", eta_start=_june(3, 7)) is None


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Não haverá nova tentativa de entrega. A encomenda foi devolvida.", "pt"),
        ("Pode solicitar uma nova tentativa até 19/06.", "pt"),
        ("Request a redelivery by Friday.", "en"),
        ("No further attempts will be made.", "en"),
        ("If you would like a new attempt, choose a date.", "en"),
        ("Ein weiterer Zustellversuch erfolgt nicht.", "de"),
        ("Pide una nueva entrega antes del 19/06.", "es"),
        ("Agende uma nova entrega no nosso site.", "pt"),
        ("Le livreur ne repassera pas.", "fr"),
        ("Bitte versuchen Sie es später erneut.", "de"),
    ],
)
def test_no_next_attempt(text: str, lang: str, tz: ZoneInfo) -> None:
    """Denied, offered or conditional attempts aren't planned ones."""
    assert find_next_attempt(text, REF_JUNE, tz, lang, eta_start=_june(18)) is None


def test_next_attempt_too_far_ahead(tz: ZoneInfo) -> None:
    """An attempt more than 14 days ahead isn't read."""
    assert find_next_attempt("Next attempt: 3 July.", REF_JUNE, tz, "en") is None
