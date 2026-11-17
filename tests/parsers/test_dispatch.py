"""Tests for the parser dispatcher."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import logging
from types import ModuleType
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels import parsers
from custom_components.parcels.const import MailKind
from custom_components.parcels.parsers import (
    NOTE_KNOWN_SENDER_UNPARSED,
    parse_message,
    senders,
)
from custom_components.parcels.parsers.base import (
    AuthResult,
    Link,
    MailMessage,
    ParseResult,
    SenderVerdict,
)

SECRET = "Body-Secret-4K7Q"
BODY = f"Hello Alex Doe, {SECRET}. Your parcel is on its way to Rua Exemplo 1."
SHIPPING_SUBJECT = "Your parcel is on its way"
OTHER_SUBJECT = "Update your account password"
UNPARSED_NOTES = (NOTE_KNOWN_SENDER_UNPARSED,)

type Calls = list[str]


def _message(
    sender: str = "orders@store.example",
    subject: str = SHIPPING_SUBJECT,
    *,
    headers: dict[str, str] | None = None,
    links: tuple[Link, ...] = (),
    auth: AuthResult | None = None,
) -> MailMessage:
    """Return a synthetic e-mail."""
    return MailMessage(
        message_id="<dispatch-test@example.com>",
        provider_id="dispatch-test",
        provider="google",
        mailbox="alex@example.com",
        sender=sender,
        sender_name="Example Store",
        subject=subject,
        date=datetime(2026, 11, 17, 9, 30, tzinfo=UTC),
        text=BODY,
        links=links,
        auth=auth,
        headers=headers or {},
    )


def _verdict(message: MailMessage, *, shopify: bool = False) -> SenderVerdict:
    """Return a verified verdict for the e-mail's sender."""
    return SenderVerdict(
        domain=message.sender_domain,
        authenticated=True,
        known=True,
        shopify=shopify,
        method="dmarc",
    )


def _stub(
    name: str, calls: Calls, result: ParseResult | None = None
) -> Callable[..., ParseResult | None]:
    """Return a parser stand-in that records its calls."""

    def parse(*args: object) -> ParseResult | None:
        calls.append(name)
        return result

    return parse


def _explode(message: MailMessage, *args: object) -> ParseResult:
    """Fail with the e-mail's content in the exception, as a buggy parser might."""
    raise ValueError(f"{message.subject} {message.text}")


def _assert_no_content_logged(caplog: pytest.LogCaptureFixture, expected: str) -> None:
    """Assert the failure was logged at debug level without e-mail content."""
    assert expected in [record.getMessage() for record in caplog.records]
    for record in caplog.records:
        logged = f"{record.getMessage()} {record.args!r} {record.exc_text or ''}"
        assert SECRET not in logged
        assert SHIPPING_SUBJECT not in logged
        assert record.exc_info is None
        if record.name.startswith(parsers.__name__):
            assert record.levelno == logging.DEBUG


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    """Replace every parser with a recording stand-in that returns None."""
    seen: Calls = []
    monkeypatch.setattr(parsers.amazon, "parse_amazon", _stub("amazon", seen))
    monkeypatch.setattr(parsers.shopify, "parse_shopify", _stub("shopify", seen))
    monkeypatch.setattr(parsers.shopify, "parse_shop", _stub("shop", seen))
    monkeypatch.setattr(parsers.carriers, "parse_carrier", _stub("carrier", seen))
    monkeypatch.setattr(parsers.carriers, "CARRIER_PARSERS", frozenset({"ctt"}))
    monkeypatch.setattr(parsers.generic, "parse_generic", _stub("generic", seen))
    return seen


@pytest.mark.parametrize(
    ("sender", "expected"),
    [
        ("ship-confirm@amazon.es", ["amazon"]),
        ("auto-confirm@amazon.co.uk", ["amazon"]),
        ("shipment-tracking@amazon.com", ["amazon"]),
        ("noreply@shop.app", ["shop"]),
        ("mailer@shopify.com", ["shopify"]),
        ("info@ctt.pt", ["carrier"]),
        ("orders@store.example", ["generic"]),
    ],
)
def test_routes_by_sender(
    calls: Calls, tz: ZoneInfo, sender: str, expected: list[str]
) -> None:
    """Known senders go to their own parser, everyone else to the generic one."""
    message = _message(sender)
    parse_message(message, _verdict(message), tz)
    assert calls == expected


def test_carrier_parser_gets_the_carrier(
    monkeypatch: pytest.MonkeyPatch, calls: Calls, tz: ZoneInfo
) -> None:
    """A carrier's parser is called with its id and its result is returned."""
    expected = ParseResult(parser="ctt", kind=MailKind.SHIPPED, confidence=0.9)
    received: list[tuple[object, ...]] = []

    def parse_carrier(*args: object) -> ParseResult:
        received.append(args)
        return expected

    monkeypatch.setattr(parsers.carriers, "parse_carrier", parse_carrier)
    message = _message("info@ctt.pt")
    verdict = _verdict(message)
    assert parse_message(message, verdict, tz) is expected
    assert received == [(message, verdict, tz, "ctt")]


def test_shopify_signed_mail_uses_the_shopify_parser(
    calls: Calls, tz: ZoneInfo
) -> None:
    """A store's own domain signed by Shopify gets the Shopify parser."""
    auth = AuthResult(dkim_pass_domains=("store.example", "shopifyemail.com"))
    message = _message(auth=auth)
    result = parse_message(message, _verdict(message, shopify=True), tz)
    assert calls == ["shopify"]
    assert result == ParseResult(
        parser="shopify", kind=MailKind.UNKNOWN, confidence=0.0, notes=UNPARSED_NOTES
    )


@pytest.mark.parametrize(
    ("headers", "links", "shopify"),
    [
        ({"x-shopify-shop-id": "61234567890"}, (), False),
        ({}, (Link("https://cdn.shopify.com/s/files/1/0001/logo.png"),), False),
        ({}, (Link("https://example-store.myshopify.com/account"),), False),
        ({}, (), True),
    ],
)
def test_shopify_markers_fall_back_to_generic(
    calls: Calls,
    tz: ZoneInfo,
    headers: dict[str, str],
    links: tuple[Link, ...],
    shopify: bool,
) -> None:
    """Weak Shopify markers try the Shopify parser, then the generic one."""
    message = _message(headers=headers, links=links)
    result = parse_message(message, _verdict(message, shopify=shopify), tz)
    assert calls == ["shopify", "generic"]
    assert result == ParseResult(parser="none", kind=MailKind.UNKNOWN, confidence=0.0)


def test_shopify_marker_result_is_used(
    monkeypatch: pytest.MonkeyPatch, calls: Calls, tz: ZoneInfo
) -> None:
    """When the Shopify parser reads a marked e-mail, its result is returned."""
    expected = ParseResult(parser="shopify", kind=MailKind.ORDER, confidence=0.9)
    monkeypatch.setattr(
        parsers.shopify, "parse_shopify", _stub("shopify", calls, expected)
    )
    message = _message(headers={"X-Shopify-Shop-Id": "61234567890"})
    assert parse_message(message, _verdict(message), tz) is expected
    assert calls == ["shopify"]


def test_generic_result_is_used(
    monkeypatch: pytest.MonkeyPatch, calls: Calls, tz: ZoneInfo
) -> None:
    """Unknown senders get the generic parser's result."""
    expected = ParseResult(parser="generic", kind=MailKind.SHIPPED, confidence=0.6)
    monkeypatch.setattr(
        parsers.generic, "parse_generic", _stub("generic", calls, expected)
    )
    message = _message()
    assert parse_message(message, _verdict(message), tz) is expected


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        (
            SHIPPING_SUBJECT,
            ParseResult(
                parser="ctt",
                kind=MailKind.UNKNOWN,
                confidence=0.0,
                notes=UNPARSED_NOTES,
            ),
        ),
        (
            OTHER_SUBJECT,
            ParseResult(parser="ctt", kind=MailKind.NOT_PARCEL, confidence=0.9),
        ),
    ],
)
def test_known_sender_unparsed(
    calls: Calls, tz: ZoneInfo, subject: str, expected: ParseResult
) -> None:
    """Unreadable shipping mail asks for an update; other mail is skipped."""
    message = _message("info@ctt.pt", subject)
    assert parse_message(message, _verdict(message), tz) == expected
    assert calls == ["carrier"]


@pytest.mark.parametrize(
    ("sender", "module", "function", "parser"),
    [
        ("ship-confirm@amazon.es", parsers.amazon, "parse_amazon", "amazon"),
        ("noreply@shop.app", parsers.shopify, "parse_shop", "shop"),
        ("mailer@shopify.com", parsers.shopify, "parse_shopify", "shopify"),
        ("info@ctt.pt", parsers.carriers, "parse_carrier", "ctt"),
    ],
)
def test_failing_parser_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    calls: Calls,
    tz: ZoneInfo,
    sender: str,
    module: ModuleType,
    function: str,
    parser: str,
) -> None:
    """A parser error gives the unparsed result and logs no e-mail content."""
    monkeypatch.setattr(module, function, _explode)
    caplog.set_level(logging.DEBUG)
    message = _message(sender)
    result = parse_message(message, _verdict(message), tz)
    assert result == ParseResult(
        parser=parser, kind=MailKind.UNKNOWN, confidence=0.0, notes=UNPARSED_NOTES
    )
    _assert_no_content_logged(caplog, f"Parser {parser} failed: ValueError")


def test_failing_generic_parser(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    calls: Calls,
    tz: ZoneInfo,
) -> None:
    """A generic parser error gives the empty result."""
    monkeypatch.setattr(parsers.generic, "parse_generic", _explode)
    caplog.set_level(logging.DEBUG)
    message = _message()
    result = parse_message(message, _verdict(message), tz)
    assert result == ParseResult(parser="none", kind=MailKind.UNKNOWN, confidence=0.0)
    _assert_no_content_logged(caplog, "Parser generic failed: ValueError")


def test_invalid_parser_return_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    calls: Calls,
    tz: ZoneInfo,
) -> None:
    """A parser returning something other than a ParseResult counts as unread."""
    monkeypatch.setattr(
        parsers.amazon, "parse_amazon", lambda *args: {"kind": "shipped"}
    )
    caplog.set_level(logging.DEBUG)
    message = _message("ship-confirm@amazon.es")
    result = parse_message(message, _verdict(message), tz)
    assert result.kind is MailKind.UNKNOWN
    assert result.notes == UNPARSED_NOTES
    _assert_no_content_logged(caplog, "Parser amazon returned dict")


def test_helper_errors_never_escape(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    calls: Calls,
    tz: ZoneInfo,
) -> None:
    """Even a failing helper module gives a result instead of an exception."""

    def explode(*args: object) -> str:
        raise RuntimeError(SECRET)

    monkeypatch.setattr(parsers.senders, "organizational_domain", explode)
    caplog.set_level(logging.DEBUG)
    message = _message(auth=AuthResult(dkim_pass_domains=("shopifyemail.com",)))
    result = parse_message(message, _verdict(message, shopify=True), tz)
    assert result == ParseResult(parser="none", kind=MailKind.UNKNOWN, confidence=0.0)
    _assert_no_content_logged(caplog, "Parser dispatch failed: RuntimeError")


def test_prefilter_error_is_not_a_silent_skip(
    monkeypatch: pytest.MonkeyPatch, calls: Calls, tz: ZoneInfo
) -> None:
    """If the subject can't be checked, an unread e-mail goes to review."""

    def explode(*args: object, **kwargs: object) -> bool:
        raise RuntimeError(SECRET)

    monkeypatch.setattr(parsers.prefilter, "is_candidate", explode)
    message = _message("ship-confirm@amazon.es", OTHER_SUBJECT)
    result = parse_message(message, _verdict(message), tz)
    assert result.kind is MailKind.UNKNOWN
    assert result.notes == UNPARSED_NOTES


@pytest.mark.parametrize(
    ("path", "parser", "kind"),
    [
        ("amazon/shipped_de", "amazon", MailKind.SHIPPED),
        ("amazon/order_es", "amazon", MailKind.ORDER),
        ("shopify/shipped_pt", "shopify", MailKind.SHIPPED),
        ("shop/on_the_way_en", "shop", MailKind.IN_TRANSIT),
    ],
)
def test_fixture_routing(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    path: str,
    parser: str,
    kind: MailKind,
) -> None:
    """Real-looking e-mails reach their parser and are read."""
    message = load_eml(f"{path}.eml")
    result = parse_message(message, verdict_for(message), tz)
    assert result.parser == parser
    assert result.kind is kind
    assert result.confidence >= 0.85
    assert not result.notes


def test_shopify_store_found_by_dkim(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """Shopify stores send from their own domains; Shopify's DKIM marks them."""
    message = load_eml("shopify/order_de.eml")
    verdict = verdict_for(message)
    assert senders.lookup(message.sender_domain) is None
    assert verdict.shopify
    result = parse_message(message, verdict, tz)
    assert result.parser == "shopify"
    assert result.kind is MailKind.ORDER


@pytest.mark.parametrize(
    ("path", "kind", "confidence", "notes"),
    [
        ("amazon/marketing_es", MailKind.NOT_PARCEL, 0.9, ()),
        ("shopify/marketing_pt", MailKind.NOT_PARCEL, 0.9, ()),
        ("amazon/changed_layout_pt", MailKind.UNKNOWN, 0.0, UNPARSED_NOTES),
    ],
)
def test_fixture_not_parsed(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    path: str,
    kind: MailKind,
    confidence: float,
    notes: tuple[str, ...],
) -> None:
    """Marketing is skipped; a changed layout asks for a parser update."""
    message = load_eml(f"{path}.eml")
    result = parse_message(message, verdict_for(message), tz)
    assert result.parser == path.split("/", 1)[0]
    assert result.kind is kind
    assert result.confidence == confidence
    assert result.notes == notes
    assert not result.shipments
