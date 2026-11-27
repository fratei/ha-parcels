"""Tests for what a survey about a delivery says besides naming it."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.const import MailKind
from custom_components.parcels.parsers.base import (
    MailMessage,
    ParsedShipment,
    ParseResult,
)
from custom_components.parcels.parsers.generic import NOTE_KIND_DEFAULT
from custom_components.parcels.parsers.survey import (
    NEWS_DATE,
    NEWS_LIVE,
    news,
    old_delivery,
)

# Tuesday 17 November 2026; Lisbon is on UTC in November.
SENT = datetime(2026, 11, 17, 9, 30, tzinfo=UTC)


def _message(text: str, subject: str = "A sua opinião conta") -> MailMessage:
    return MailMessage(
        message_id="<survey-test@example.com>",
        provider_id="survey-test",
        provider="google",
        mailbox="alex@example.com",
        sender="inqueritos@ctt.pt",
        sender_name="CTT",
        subject=subject,
        date=SENT,
        text=text,
    )


def _result(
    kind: MailKind = MailKind.DELIVERED,
    *,
    lang: str = "pt",
    notes: tuple[str, ...] = (),
    **shipment: object,
) -> ParseResult:
    return ParseResult(
        parser="ctt",
        kind=kind,
        shipments=[
            ParsedShipment(
                carrier="ctt", tracking_number="RR123456785PT", kind=kind, **shipment
            )
        ],
        confidence=0.81,
        language=lang,
        notes=notes,
    )


@pytest.mark.parametrize(
    ("result", "text", "expected"),
    [
        # Naming the delivery being rated.
        (_result(), "O objeto RR123456785PT foi entregue a 10/11.", None),
        (_result(), "O objeto foi entregue. Ajude-nos a melhorar.", None),
        (
            _result(lang="en"),
            "Your parcel was delivered on Friday. Tell us how we did.",
            None,
        ),
        # A status still to come, a pickup code or a day to collect by.
        (_result(MailKind.OUT_FOR_DELIVERY), "Está em distribuição.", NEWS_LIVE),
        (
            _result(MailKind.READY_FOR_PICKUP, pickup_code="482913"),
            "Código: 482913.",
            NEWS_LIVE,
        ),
        (
            _result(MailKind.READY_FOR_PICKUP),
            "Pode levantá-la até 25/11.",
            NEWS_LIVE,
        ),
        # A status a parser fell back to is no news.
        (
            _result(MailKind.IN_TRANSIT, notes=(NOTE_KIND_DEFAULT,)),
            "Obrigado por escolher os CTT.",
            None,
        ),
        # A day to come, outside the survey's own sentences.
        (_result(), "A próxima entrega está prevista para 20/11.", NEWS_DATE),
        (
            _result(lang="en"),
            "Your parcel will be delivered on Friday.",
            NEWS_DATE,
        ),
        (
            _result(lang="en"),
            "Your parcel was delivered on 20 November.",
            NEWS_DATE,
        ),
        # The survey's own dates, and days too far ahead.
        (_result(), "Responda ao inquérito até 25/11.", None),
        (_result(), "A entrega está prevista para 15/01/2027.", None),
    ],
)
def test_news(
    tz: ZoneInfo, result: ParseResult, text: str, expected: str | None
) -> None:
    """Only what the survey says besides naming its delivery is news."""
    assert news(result, _message(text), tz) == expected


@pytest.mark.parametrize(
    ("result", "subject", "text", "expected"),
    [
        # The parser read the event's day.
        (
            _result(event_time=datetime(2026, 11, 10, 8, 12, tzinfo=UTC)),
            "",
            "",
            True,
        ),
        (
            _result(event_time=datetime(2026, 11, 17, 8, 12, tzinfo=UTC)),
            "",
            "Foi entregue a 10/11.",
            False,
        ),
        # A parcel waiting with its code.
        (
            _result(MailKind.READY_FOR_PICKUP, pickup_code="482913"),
            "A sua entrega de 4 de novembro",
            "",
            False,
        ),
        # The subject names another day.
        (_result(), "A sua entrega de 4 de novembro", "", True),
        (_result(), "A sua entrega de hoje", "", False),
        # The body's done sentence names the day.
        (_result(), "", "O objeto foi entregue a 10/11.", True),
        (_result(), "", "O objeto foi entregue ontem.", True),
        (_result(), "", "O objeto foi entregue hoje.", False),
        (_result(lang="en"), "", "Your parcel was delivered on Friday.", True),
        # The e-mail's own weekday is a week ago.
        (_result(lang="en"), "", "Your parcel was delivered on Tuesday.", True),
        (_result(lang="en"), "", "Your parcel will be delivered on Friday.", False),
        # A parcel waiting until a day to come.
        (_result(), "", "Foi entregue a 10/11. Pode levantá-la até 25/11.", False),
        # Nothing said either way.
        (_result(), "", "Obrigado por escolher os CTT.", False),
    ],
)
def test_old_delivery(
    tz: ZoneInfo, result: ParseResult, subject: str, text: str, expected: bool
) -> None:
    """A delivery named with an earlier day is old; any fresh sign wins."""
    assert old_delivery(result, _message(text, subject), tz) is expected
