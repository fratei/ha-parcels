"""Tests for the parser dispatcher."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
import logging
from types import ModuleType
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels import parsers
from custom_components.parcels.const import CONFIDENCE_APPLY, MailKind
from custom_components.parcels.parsers import (
    NOTE_KNOWN_SENDER_UNPARSED,
    parse_message,
    senders,
)
from custom_components.parcels.parsers.base import (
    AuthResult,
    Eta,
    Link,
    MailMessage,
    ParsedShipment,
    ParseResult,
    SenderVerdict,
)
from custom_components.parcels.parsers.returns import (
    NOTE_PICKUP_NEXT_WORKING_DAY,
    NOTE_REFUND,
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
    text: str = BODY,
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
        text=text,
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
    monkeypatch.setattr(
        parsers.leroymerlin, "parse_leroymerlin", _stub("leroymerlin", seen)
    )
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
        ("encomendas@leroymerlin.pt", ["leroymerlin"]),
        ("novidades@mailing.leroymerlin.pt", ["leroymerlin"]),
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
            "Ihr Zustellcode",
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
    ("sender", "parser"),
    [("info@ctt.pt", "ctt"), ("ship-confirm@amazon.es", "amazon")],
)
@pytest.mark.parametrize(
    "subject",
    [
        "Como correu a sua encomenda #1912?",
        "Rate your delivery experience",
        "Fatura da encomenda #1912",
        "Wie zufrieden waren Sie mit uns?",
        "Horario especial de Navidad",
        "Neu: die Post & DHL App",
        "Your UPS invoice is ready",
    ],
)
def test_known_sender_mail_about_something_else(
    calls: Calls, tz: ZoneInfo, sender: str, parser: str, subject: str
) -> None:
    """Feedback, invoices and notices are skipped, though they name a parcel."""
    message = _message(sender, subject)
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser=parser, kind=MailKind.NOT_PARCEL, confidence=0.9
    )


@pytest.mark.parametrize(
    ("sender", "parser", "subject", "text"),
    [
        pytest.param(
            "info@ctt.pt",
            "ctt",
            "Tu opinión nos importa",
            "Hola Alex,\nTu pedido 1912345 fue entregado ayer. ¿Nos dejas tu opinión?\n",
            id="carrier",
        ),
        pytest.param(
            "mailer@shopify.com",
            "shopify",
            "Gostou das velas?",
            "Olá Alex,\nA sua encomenda #1912 foi entregue. Deixe a sua avaliação.\n",
            id="shopify",
        ),
        pytest.param(
            "opiniao@mailing.leroymerlin.pt",
            "leroymerlin",
            "Diga-nos o que achou",
            "Olá Alex,\nA sua encomenda 001234567890 foi entregue. Conte-nos tudo.\n",
            id="leroymerlin",
        ),
        pytest.param(
            "ship-confirm@amazon.es",
            "amazon",
            "Alex, comparte tu opinión",
            "Hola Alex,\nTu pedido 406-2958173-6604821 fue entregado.\n",
            id="amazon",
        ),
    ],
)
def test_feedback_about_a_delivered_order(
    calls: Calls, tz: ZoneInfo, sender: str, parser: str, subject: str, text: str
) -> None:
    """A request for feedback is skipped, though its body names the delivery."""
    message = _message(sender, subject, text=text)
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser=parser, kind=MailKind.NOT_PARCEL, confidence=0.9
    )


SELLER_MESSAGE_TEXT = (
    "Olá Alex,\nRecebeu uma mensagem do vendedor Loja Exemplo referente à "
    "encomenda nº ABC123-A.\nMensagem: a sua encomenda foi enviada hoje, com o "
    "número de seguimento RR123456785PT.\n"
)


@pytest.mark.parametrize(
    ("sender", "parser"),
    [
        ("ship-confirm@amazon.es", "amazon"),
        ("marketplace@mailing.leroymerlin.pt", "leroymerlin"),
        ("mailer@shopify.com", "shopify"),
    ],
)
@pytest.mark.parametrize(
    "subject",
    [
        "Recebeu uma mensagem referente à encomenda nº ABC123-A",
        "Abrir reclamação sobre o pedido 1234567890123-A",
        "You have a new message from the seller about order #1001",
    ],
)
def test_unreadable_seller_message(
    calls: Calls, tz: ZoneInfo, sender: str, parser: str, subject: str
) -> None:
    """A seller's message or a prompt to complain asks for no parser update."""
    message = _message(sender, subject, text=SELLER_MESSAGE_TEXT)
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser=parser, kind=MailKind.NOT_PARCEL, confidence=0.9
    )


@pytest.mark.parametrize(
    ("subject", "kind"),
    [
        ("Tens uma nova mensagem de alex123", MailKind.NOT_PARCEL),
        ("Nuevo mensaje de Tienda Ejemplo", MailKind.NOT_PARCEL),
        ("Tens uma nova mensagem do teu estafeta", MailKind.SHIPPED),
        ("Recebeu uma mensagem: a sua encomenda foi enviada", MailKind.SHIPPED),
    ],
)
def test_seller_message_from_an_unknown_sender(
    monkeypatch: pytest.MonkeyPatch,
    calls: Calls,
    tz: ZoneInfo,
    subject: str,
    kind: MailKind,
) -> None:
    """A marketplace's message is no news; a courier's or a status still is."""
    read = ParseResult(
        parser="generic",
        kind=MailKind.SHIPPED,
        shipments=[ParsedShipment(carrier="ctt", tracking_number="RR123456785PT")],
        confidence=0.6,
    )
    monkeypatch.setattr(parsers.generic, "parse_generic", _stub("generic", calls, read))
    message = _message("noreply@marketplace.example", subject, text=SELLER_MESSAGE_TEXT)
    verdict = replace(_verdict(message), known=False)
    assert parse_message(message, verdict, tz).kind is kind


def test_carrier_message_may_be_news(calls: Calls, tz: ZoneInfo) -> None:
    """A carrier's own message about a parcel still asks for a parser update."""
    message = _message(
        "info@ctt.pt",
        "Tem uma nova mensagem",
        text=(
            "Olá Alex,\nO objeto RR123456785PT está em distribuição. Indique "
            "onde o podemos deixar.\n"
        ),
    )
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser="ctt", kind=MailKind.UNKNOWN, confidence=0.0, notes=UNPARSED_NOTES
    )
    assert calls == ["carrier"]


@pytest.mark.parametrize(
    ("sender", "subject", "known", "kind"),
    [
        pytest.param(
            "loja@store.example",
            "Como correu a sua entrega?",
            False,
            MailKind.NOT_PARCEL,
            id="survey",
        ),
        pytest.param(
            "noreply@marketplace.example",
            "Tem uma nova mensagem do vendedor",
            False,
            MailKind.NOT_PARCEL,
            id="seller-message",
        ),
        pytest.param(
            "info@correos.es",
            "Tienes un nuevo mensaje",
            True,
            MailKind.UNKNOWN,
            id="carrier-message",
        ),
        pytest.param(
            "loja@store.example",
            "Atualização da sua encomenda",
            False,
            MailKind.UNKNOWN,
            id="other",
        ),
    ],
)
def test_nothing_read_from_a_survey_or_a_seller_message(
    calls: Calls, tz: ZoneInfo, sender: str, subject: str, known: bool, kind: MailKind
) -> None:
    """The local AI isn't asked about a survey or a seller's message either."""
    message = _message(
        sender, subject, text="Olá Alex,\n\nA sua encomenda foi entregue.\n"
    )
    verdict = replace(_verdict(message), known=known)
    result = parse_message(message, verdict, tz)
    assert (result.parser, result.kind) == ("none", kind)
    assert calls == ["generic"]


def test_account_mail_naming_an_order(calls: Calls, tz: ZoneInfo) -> None:
    """An order added to the shop's account, to follow there, isn't news."""
    message = _message(
        "conta@leroymerlin.pt",
        "A sua conta Leroy Merlin",
        text=(
            "Olá Alex,\nA encomenda 001234567890 foi associada à sua conta. "
            "Acompanhe a sua encomenda na área de cliente.\n"
        ),
    )
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser="leroymerlin", kind=MailKind.NOT_PARCEL, confidence=0.9
    )


PLAIN_SUBJECT = "Uma mensagem para si"


@pytest.mark.parametrize(
    ("sender", "parser"),
    [
        ("info@ctt.pt", "ctt"),
        ("ship-confirm@amazon.es", "amazon"),
        ("encomendas@leroymerlin.pt", "leroymerlin"),
        ("delivery@mailing.leroymerlin.pt", "leroymerlin"),
    ],
)
@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "Olá Alex,\nA sua encomenda 001234567890 foi expedida do nosso armazém.\n",
            id="pt-order",
        ),
        pytest.param(
            "Hello Alex,\nYour order #10045 has been shipped.\n", id="en-order"
        ),
        pytest.param(
            "Hello Alex,\nYour parcel 1Z999AA10123456784 is out for delivery.\n",
            id="tracking-number",
        ),
        pytest.param(
            "Olá Alex,\nA sua encomenda 001234567890 foi expedida. "
            "Acompanhe a sua encomenda na área de cliente.\n",
            id="pt-order-account-link",
        ),
    ],
)
def test_body_names_a_shipped_order(
    calls: Calls, tz: ZoneInfo, sender: str, parser: str, text: str
) -> None:
    """A number and shipping words in the body ask for an update too."""
    message = _message(sender, PLAIN_SUBJECT, text=text)
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser=parser, kind=MailKind.UNKNOWN, confidence=0.0, notes=UNPARSED_NOTES
    )


def test_review_of_a_delivery_address_asks_for_an_update(
    calls: Calls, tz: ZoneInfo
) -> None:
    """A request to review the shipping address is no request for feedback."""
    message = _message(
        "info@ctt.pt",
        "Review and confirm your shipping address",
        text="Hello Alex,\nYour parcel is on its way. Tracking: 1Z999AA10123456784\n",
    )
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser="ctt", kind=MailKind.UNKNOWN, confidence=0.0, notes=UNPARSED_NOTES
    )


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(BODY, id="no-number"),
        pytest.param(
            "Olá Alex,\nSegue em anexo a fatura da encomenda n.º 001234567890.\n",
            id="no-shipping-words",
        ),
        # A number's label alone isn't news about the order.
        pytest.param(
            "Olá Alex,\nNúmero de encomenda: 001234567890\nSegue em anexo a fatura.\n",
            id="pt-label",
        ),
        pytest.param(
            "Hello Alex,\nOrder number: 10045. Your invoice is attached.\n",
            id="en-label",
        ),
    ],
)
def test_body_without_shipping_news(calls: Calls, tz: ZoneInfo, text: str) -> None:
    """Without both a number and shipping words, other mail is skipped."""
    message = _message("info@ctt.pt", PLAIN_SUBJECT, text=text)
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser="ctt", kind=MailKind.NOT_PARCEL, confidence=0.9
    )


def test_body_check_error_is_not_a_silent_skip(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    calls: Calls,
    tz: ZoneInfo,
) -> None:
    """If the body can't be checked, an unread e-mail goes to review."""

    def explode(*args: object, **kwargs: object) -> bool:
        raise RuntimeError(SECRET)

    monkeypatch.setattr(parsers.prefilter, "has_shipping_words", explode)
    caplog.set_level(logging.DEBUG)
    message = _message(
        "ship-confirm@amazon.es",
        OTHER_SUBJECT,
        text=f"Hello Alex, {SECRET}. Your order #10045.",
    )
    result = parse_message(message, _verdict(message), tz)
    assert result.kind is MailKind.UNKNOWN
    assert result.notes == UNPARSED_NOTES
    _assert_no_content_logged(caplog, "Body check failed: RuntimeError")


# E-mails the parsers read as news, though they're about something else:
# surveys, review requests, a carrier's posting receipt, invoices, and a
# seller's messages and prompts to complain.
GATED = [
    pytest.param(
        "inqueritos@ctt.pt",
        "ctt",
        "Como correu a sua entrega?",
        "Olá Alex,\n\nO objeto RR123456785PT foi entregue a 4 de novembro. "
        "Responda a 3 perguntas sobre a entrega e ajude-nos a melhorar.\n",
        id="ctt-survey",
    ),
    pytest.param(
        "kundenservice@dhl.de",
        "dhl",
        "Wie zufrieden waren Sie mit uns?",
        "Hallo Alex,\n\nIhre Sendung 00340434618273591202 wurde am 4. November "
        "zugestellt.\nBitte nehmen Sie sich eine Minute Zeit für unsere Umfrage.\n",
        id="dhl-survey",
    ),
    pytest.param(
        "survey@ups.com",
        "ups",
        "How did we do?",
        "Hello Alex,\n\nYour package 1Z999AA10123456784 was delivered on Friday. "
        "Tell us how we did in 2 minutes.\n",
        id="ups-survey",
    ),
    pytest.param(
        "inquerito@inpost.pt",
        "inpost",
        "A sua opinião é importante",
        "Olá Alex,\n\nA sua encomenda 620417393912 foi entregue no Locker "
        "PT-LIS-01. Avalie a sua experiência em 1 minuto.\n",
        id="inpost-survey",
    ),
    pytest.param(
        "opiniao@leroymerlin.pt",
        "leroymerlin",
        "A sua opinião conta",
        "Olá Alex,\n\nA sua encomenda 009919100001 foi entregue. Avalie o "
        "Berbequim sem fios e ganhe pontos no cartão.\n",
        id="lm-review",
    ),
    pytest.param(
        "opiniao@mailing.leroymerlin.pt",
        "leroymerlin",
        "Diga-nos o que achou",
        "Olá Alex,\n\nA sua encomenda 009919100001 foi entregue. Avalie o "
        "Berbequim sem fios.\n",
        id="lm-review-mailing",
    ),
    pytest.param(
        "naoresponder@ctt.pt",
        "ctt",
        "Comprovativo do seu envio",
        "Olá Alex Doe,\n\nO seu envio RR123456785PT foi aceite na Loja CTT "
        "Exemplo a 12/11/2026.\nAcompanhe o seu envio em ctt.pt.\n\n"
        "Obrigado por escolher os CTT.\n",
        id="ctt-receipt",
    ),
    pytest.param(
        "naoresponder@ctt.pt",
        "ctt",
        "Recibo do seu envio",
        "Olá Alex,\n\nO seu envio RR123456785PT foi aceite na Loja CTT Exemplo "
        "a 25/11/2026. Obrigado.\n",
        id="ctt-receipt-recibo",
    ),
    pytest.param(
        "naoresponder@ctt.pt",
        "ctt",
        "O seu envio foi aceite",
        "Olá Alex,\n\nO seu envio RR123456785PT foi aceite na Loja CTT Exemplo "
        "a 25/11/2026. Obrigado.\n",
        id="ctt-receipt-aceite",
    ),
    pytest.param(
        "noreply@dhl.de",
        "dhl",
        "Ihre Einlieferungsbestätigung",
        "Hallo Alex,\n\nIhre Sendung 00340434618273591202 wurde am 25.11.2026 "
        "in der Filiale eingeliefert.\n",
        id="dhl-receipt",
    ),
    pytest.param(
        "billing@ups.com",
        "ups",
        "Your UPS shipment receipt",
        "Hello Alex,\n\nYour shipment 1Z999AA10123456784 was dropped off at a "
        "UPS Access Point on 25 November.\n",
        id="ups-receipt",
    ),
    pytest.param(
        "faturacao@ctt.pt",
        "ctt",
        "Fatura eletrónica FT 2026A/100001",
        "Exmo(a). Sr(a). Alex Doe,\n\nEnviamos a fatura n.º FT 2026A/100001 "
        "referente ao serviço de envio do objeto RR123456785PT, no valor de "
        "4,50 €.\n",
        id="ctt-invoice",
    ),
    pytest.param(
        "rechnung@dhl.de",
        "dhl",
        "Ihre Rechnung zur Online-Frankierung",
        "Hallo Alex,\n\nvielen Dank für Ihren Kauf. Rechnungsnummer "
        "7012345678.\nSendungsnummer: 00340434618273591202\nBetrag: 6,99 EUR\n",
        id="dhl-invoice",
    ),
    pytest.param(
        "billing@ups.com",
        "ups",
        "Your UPS invoice is ready",
        "Hello Alex,\n\nInvoice 0000A12B34 for shipment 1Z999AA10123456784. "
        "Amount due: 12.40 EUR by 10 January.\n",
        id="ups-invoice",
    ),
    *(
        pytest.param(
            "inqueritos@ctt.pt",
            "ctt",
            subject,
            "Olá Alex,\n\nO objeto RR123456785PT foi entregue a 4 de novembro. "
            "Responda a 3 perguntas sobre a entrega.\n",
            id=f"ctt-survey-{index}",
        )
        for index, subject in enumerate(
            (
                "Ajude-nos a melhorar",
                "Classifique a entrega do seu objeto",
                "A sua experiência com os CTT",
                "Já recebeu o seu objeto? Avalie a entrega",
            )
        )
    ),
    # Surveys whose subject has neither a status nor a request for feedback:
    # the body asks to answer questions about the delivery it names.
    *(
        pytest.param(sender, parser, subject, text, id=f"survey-body-{name}")
        for name, sender, parser, subject, text in (
            (
                "ctt-date",
                "inqueritos@ctt.pt",
                "ctt",
                "A sua entrega de 4 de novembro",
                "Olá Alex,\n\nO objeto RR123456785PT foi entregue a 4 de novembro. "
                "Responda a 3 perguntas sobre a entrega.\n",
            ),
            (
                "ctt-minute",
                "inqueritos@ctt.pt",
                "ctt",
                "Tem um minuto?",
                "Olá Alex,\n\nO objeto RR123456785PT foi entregue a 4 de novembro. "
                "Responda a 3 perguntas sobre a entrega.\n",
            ),
            (
                "ups-hear",
                "survey@ups.com",
                "ups",
                "We'd love to hear from you",
                "Hello Alex,\n\nYour package 1Z999AA10123456784 was delivered on "
                "Friday. Tell us how we did in 2 minutes.\n",
            ),
            (
                "ups-question",
                "survey@ups.com",
                "ups",
                "A quick question about your delivery",
                "Hello Alex,\n\nYour package 1Z999AA10123456784 was delivered on "
                "Friday. Tell us how we did in 2 minutes.\n",
            ),
            (
                "dhl",
                "kundenservice@dhl.de",
                "dhl",
                "Ihre Sendung vom 4. November",
                "Hallo Alex,\n\nIhre Sendung 00340434618273591202 wurde am 4. "
                "November zugestellt. Bitte nehmen Sie an unserer Umfrage teil.\n",
            ),
            (
                "es",
                "survey@ups.com",
                "ups",
                "Tu entrega del 4 de noviembre",
                "Hola Alex,\n\nTu paquete 1Z999AA10123456784 fue entregado el "
                "viernes. Responde a 3 preguntas sobre la entrega.\n",
            ),
            (
                "fr",
                "survey@ups.com",
                "ups",
                "Votre livraison du 4 novembre",
                "Bonjour Alex,\n\nVotre colis 1Z999AA10123456784 a été livré "
                "vendredi. Répondez à notre enquête en 2 minutes.\n",
            ),
            (
                "it",
                "survey@ups.com",
                "ups",
                "La tua consegna del 4 novembre",
                "Ciao Alex,\n\nIl tuo pacco 1Z999AA10123456784 è stato consegnato "
                "venerdì. Rispondi a 3 domande sulla consegna.\n",
            ),
            (
                "nl",
                "survey@ups.com",
                "ups",
                "Je bezorging van 4 november",
                "Hallo Alex,\n\nJe pakket 1Z999AA10123456784 is vrijdag bezorgd. "
                "Vul onze korte enquête in.\n",
            ),
            (
                "locker",
                "inquerito@inpost.pt",
                "inpost",
                "A sua recolha de 4 de novembro",
                "Olá Alex,\n\nA sua encomenda 620417393912 foi entregue no Locker "
                "PT-LIS-02. Responda a 3 perguntas.\n",
            ),
        )
    ),
    # A survey's subject alone, over a body that only asks for a rating.
    pytest.param(
        "inqueritos@ctt.pt",
        "ctt",
        "Tem um minuto?",
        "Olá Alex,\n\nO objeto RR123456785PT foi entregue a 4 de novembro. "
        "Avalie a entrega.\n",
        id="survey-subject-minute",
    ),
    pytest.param(
        "survey@ups.com",
        "ups",
        "We'd love to hear from you",
        "Hello Alex,\n\nYour package 1Z999AA10123456784 was delivered on Friday. "
        "Rate your delivery.\n",
        id="survey-subject-hear",
    ),
    *(
        pytest.param(sender, "amazon", subject, text, id=f"amazon-review-{lang}")
        for lang, sender, subject, text in (
            (
                "pt",
                "avaliacoes@amazon.es",
                "Alex, como classificaria o Tapete Exemplo?",
                "Olá Alex,\n\nA sua encomenda 406-1234567-1234567 foi entregue. "
                "Como classificaria o Tapete Exemplo?\n",
            ),
            (
                "pt-2",
                "avaliacoes@amazon.es",
                "Alex, como avaliaria o Tapete Exemplo?",
                "Olá Alex,\n\nA sua encomenda 406-1234567-1234567 foi entregue. "
                "Escreva uma avaliação.\n",
            ),
            (
                "es",
                "opiniones@amazon.es",
                "Alex, ¿cómo valorarías Alfombra Ejemplo?",
                "Hola Alex,\n\nTu pedido 406-1234567-1234567 ha sido entregado. "
                "¿Cómo valorarías Alfombra Ejemplo?\n",
            ),
            (
                "en",
                "reviews@amazon.com",
                "Alex, how would you rate Ceramic Mug Example?",
                "Hello Alex,\n\nYour package for order 112-1234567-1234567 was "
                "delivered. How would you rate Ceramic Mug Example?\n",
            ),
            (
                "fr",
                "avis@amazon.fr",
                "Alex, comment évalueriez-vous Tasse Exemple ?",
                "Bonjour Alex,\n\nVotre colis pour la commande 405-1234567-1234567 "
                "a été livré. Donnez votre avis.\n",
            ),
            (
                "it",
                "recensioni@amazon.it",
                "Alex, come valuteresti Tazza Esempio?",
                "Ciao Alex,\n\nIl tuo ordine 405-1234567-1234567 è stato "
                "consegnato. Scrivi una recensione.\n",
            ),
            (
                "nl",
                "review@amazon.nl",
                "Alex, wat vind je van Mok Voorbeeld?",
                "Hallo Alex,\n\nJe bestelling 405-1234567-1234567 is bezorgd. "
                "Schrijf een review.\n",
            ),
        )
    ),
    *(
        pytest.param(sender, parser, subject, text, id=f"seller-message-{name}")
        for name, sender, parser, subject, text in (
            (
                "lm-shipped",
                "marketplace@mailing.leroymerlin.pt",
                "leroymerlin",
                "Recebeu uma mensagem referente à encomenda nº 1234567890123-A",
                "Olá Alex,\nRecebeu uma mensagem do vendedor Loja Exemplo "
                "referente à encomenda nº 1234567890123-A.\nMensagem: Olá, a sua "
                "encomenda foi enviada hoje pela transportadora.\nPara responder, "
                "aceda à sua área de cliente.\n",
            ),
            (
                "lm-delivered",
                "marketplace@mailing.leroymerlin.pt",
                "leroymerlin",
                "Recebeu uma mensagem referente à encomenda nº 1234567890123-A",
                "Olá Alex,\nRecebeu uma mensagem do vendedor Loja Exemplo "
                "referente à encomenda nº 1234567890123-A.\nMensagem: A encomenda "
                "foi entregue no dia 3. Obrigado.\nPara responder, aceda à sua "
                "área de cliente.\n",
            ),
            (
                "lm-complaint",
                "marketplace@mailing.leroymerlin.pt",
                "leroymerlin",
                "Leroy Merlin Marketplace - Abrir reclamação sobre o pedido "
                "1234567890123-A",
                "Olá Alex,\nPode abrir uma reclamação sobre o pedido "
                "1234567890123-A se a sua encomenda não foi entregue ou chegou "
                "danificada.\n",
            ),
            (
                "amazon",
                "vendedor@marketplace.amazon.es",
                "amazon",
                "Tem uma nova mensagem do vendedor",
                "Olá Alex,\nO vendedor Loja Exemplo enviou-lhe uma mensagem sobre "
                "a encomenda 406-1234567-1234567.\nMensagem: A sua encomenda foi "
                "enviada hoje.\n",
            ),
            (
                "vinted",
                "no-reply@vinted.pt",
                "vinted_go",
                "Tens uma nova mensagem de alex123",
                "Olá Alex,\nalex123 enviou-te uma mensagem: Já enviei a "
                "encomenda, o número de seguimento é RR123456785PT.\n",
            ),
        )
    ),
]


@pytest.mark.parametrize(("sender", "parser", "subject", "text"), GATED)
def test_parsed_mail_about_something_else(
    tz: ZoneInfo, sender: str, parser: str, subject: str, text: str
) -> None:
    """What the parsers read from it sets no status, nor adds a parcel."""
    message = _message(sender, subject, text=text)
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser=parser, kind=MailKind.NOT_PARCEL, confidence=0.9
    )


def test_shop_survey_from_an_unknown_sender(tz: ZoneInfo) -> None:
    """A shop's survey naming its delivery is no news either."""
    message = _message(
        "loja@store.example",
        "Como correu a sua entrega?",
        text=(
            "Olá Alex,\n\nA sua encomenda #1001 foi entregue pelos CTT. Número "
            "de seguimento: RR123456785PT. Avalie a entrega.\n"
        ),
    )
    verdict = replace(_verdict(message), known=False)
    assert parse_message(message, verdict, tz) == ParseResult(
        parser="generic", kind=MailKind.NOT_PARCEL, confidence=0.9
    )


@pytest.mark.parametrize(
    ("sender", "subject", "text", "kind"),
    [
        pytest.param(
            "info@ctt.pt",
            "Fatura de desalfandegamento",
            "Olá Alex,\n\nO objeto RR123456785PT aguarda o pagamento dos "
            "direitos aduaneiros.\n",
            MailKind.CUSTOMS,
            id="customs-invoice",
        ),
        pytest.param(
            "info@ctt.pt",
            "A sua encomenda foi entregue: avalie a entrega",
            "Olá Alex,\n\nO objeto RR123456785PT foi entregue.\n",
            MailKind.DELIVERED,
            id="status-and-feedback",
        ),
        pytest.param(
            "info@ctt.pt",
            "Entregue: tem um minuto para avaliar?",
            "Olá Alex,\n\nO objeto RR123456785PT foi entregue. Responda a 3 "
            "perguntas sobre a entrega.\n",
            MailKind.DELIVERED,
            id="status-and-survey",
        ),
        # Only a request for a rating under the news: no survey.
        pytest.param(
            "info@ctt.pt",
            "Informação sobre o seu objeto",
            "Olá Alex,\n\nO objeto RR123456785PT foi entregue. Avalie a entrega.\n",
            MailKind.DELIVERED,
            id="rating-footer",
        ),
        pytest.param(
            "mcinfo@ups.com",
            "UPS Update",
            "Hello Alex,\n\nYour package 1Z999AA10123456784 was delivered. How "
            "did we do? Rate your delivery.\n",
            MailKind.DELIVERED,
            id="rating-footer-en",
        ),
        # A survey under news that doesn't close a delivery.
        pytest.param(
            "info@ctt.pt",
            "Informação sobre o seu envio",
            "Olá Alex,\n\nO objeto RR123456785PT está a caminho. Responda a 3 "
            "perguntas sobre o nosso serviço.\n",
            MailKind.IN_TRANSIT,
            id="news-and-survey",
        ),
        *(
            pytest.param(
                sender, subject, text, MailKind.DELIVERED, id=f"arrived-{lang}"
            )
            for lang, sender, subject, text in (
                (
                    "pt",
                    "info@ctt.pt",
                    "Entrega concluída: avalie o nosso serviço",
                    "Olá Alex,\n\nO objeto RR123456785PT foi entregue.\n",
                ),
                (
                    "pt-2",
                    "info@ctt.pt",
                    "Entregámos o seu objeto. Como correu?",
                    "Olá Alex,\n\nO objeto RR123456785PT foi entregue.\n",
                ),
                (
                    "en",
                    "mcinfo@ups.com",
                    "Delivery complete \u2013 how did we do?",
                    "Hello Alex,\n\nYour package 1Z999AA10123456784 was delivered.\n",
                ),
                (
                    "en-2",
                    "mcinfo@ups.com",
                    "Your parcel is here! Rate your delivery",
                    "Hello Alex,\n\nYour package 1Z999AA10123456784 was delivered.\n",
                ),
                (
                    "es",
                    "mcinfo@ups.com",
                    "Tu paquete ha llegado: valora la entrega",
                    "Hola Alex,\n\nTu paquete 1Z999AA10123456784 ha sido entregado.\n",
                ),
                (
                    "de",
                    "noreply@dhl.de",
                    "Ihr Paket ist da: wie zufrieden waren Sie?",
                    "Hallo Alex,\n\nIhre Sendung 00340434618273591202 wurde "
                    "zugestellt.\n",
                ),
                (
                    "fr",
                    "mcinfo@ups.com",
                    "Votre colis est arrivé : donnez votre avis",
                    "Bonjour Alex,\n\nVotre colis 1Z999AA10123456784 a été livré.\n",
                ),
                (
                    "it",
                    "mcinfo@ups.com",
                    "Il tuo pacco è arrivato: com'è andata?",
                    "Ciao Alex,\n\nIl tuo pacco 1Z999AA10123456784 è stato "
                    "consegnato.\n",
                ),
                (
                    "nl",
                    "mcinfo@ups.com",
                    "Je pakket is er: hoe was je bezorging?",
                    "Hallo Alex,\n\nJe pakket 1Z999AA10123456784 is bezorgd.\n",
                ),
            )
        ),
        pytest.param(
            "auto-confirm@amazon.com",
            'Ordered: "Customer Feedback Board" and 1 more item',
            "Hello Alex,\nThank you for your order. We'll send a confirmation "
            "when your items ship.\nOrder #112-1234567-1234567\n"
            "Arriving Friday, November 20\n",
            MailKind.ORDER,
            id="product-named-feedback",
        ),
        pytest.param(
            "auto-confirm@amazon.com",
            'Ordered: "Customer Feedback Board Deluxe Edition wit...',
            "Hello Alex,\nThank you for your order. We'll send a confirmation "
            "when your items ship.\nOrder #112-1234567-1234567\n"
            "Arriving Friday, November 20\n",
            MailKind.ORDER,
            id="product-name-cut",
        ),
        pytest.param(
            "auto-confirm@amazon.de",
            "Bestellt: „Bewertungsbogen A4“",
            "Hallo Alex,\nVielen Dank für Ihre Bestellung.\n"
            "Bestellnr. 302-1234567-1234567\nZustellung: Freitag, 20. November\n",
            MailKind.ORDER,
            id="product-named-review",
        ),
    ],
)
def test_parsed_news_stays(
    tz: ZoneInfo, sender: str, subject: str, text: str, kind: MailKind
) -> None:
    """Customs invoices, a status in the subject and product names stay news."""
    message = _message(sender, subject, text=text)
    result = parse_message(message, _verdict(message), tz)
    assert result.kind is kind
    assert result.confidence >= CONFIDENCE_APPLY


@pytest.mark.parametrize(
    ("sender", "subject", "text"),
    [
        pytest.param(
            "encomendas@leroymerlin.pt",
            "Comprovativo de envio da encomenda 001234567890",
            "Olá Alex,\n\nA sua encomenda 001234567890 foi expedida do nosso "
            "armazém.\n",
            id="shop",
        ),
        pytest.param(
            "loja@store.example",
            "Comprovativo de envio da encomenda #1001",
            "Olá Alex,\n\nA sua encomenda #1001 foi enviada pelos CTT. Número "
            "de seguimento: RR123456785PT.\n",
            id="unknown-shop",
        ),
    ],
)
def test_shop_proof_of_shipping_is_news(
    tz: ZoneInfo, sender: str, subject: str, text: str
) -> None:
    """Only a carrier's posting receipt is about a parcel the user sends."""
    message = _message(sender, subject, text=text)
    result = parse_message(message, _verdict(message), tz)
    assert result.kind is MailKind.SHIPPED


def test_invoice_with_news_is_checked(tz: ZoneInfo) -> None:
    """An invoice that also brings news is read, but not applied unchecked."""
    message = _message(
        "billing@ups.com",
        "Your UPS invoice is ready",
        text=(
            "Hello Alex,\n\nInvoice 0000A12B34 for shipment 1Z999AA10123456784. "
            "Your package is out for delivery today.\n"
        ),
    )
    result = parse_message(message, _verdict(message), tz)
    assert result.kind is MailKind.OUT_FOR_DELIVERY
    assert [shipment.tracking_number for shipment in result.shipments] == [
        "1Z999AA10123456784"
    ]
    assert result.confidence < CONFIDENCE_APPLY


@pytest.mark.parametrize(
    ("sender", "subject", "text", "parser"),
    [
        pytest.param(
            "noreply@dpd.pt",
            "Fatura e envio da encomenda n.º 123456",
            "Olá Alex,\n\nA sua encomenda n.º 123456 foi enviada. Segue em anexo "
            "a fatura.\n",
            "dpd",
            id="shipped",
        ),
        pytest.param(
            "noreply@dpd.pt",
            "Fatura e envio da encomenda n.º 44550123",
            "A sua encomenda n.º 44550123 foi enviada hoje. Segue a fatura em anexo.",
            "dpd",
            id="shipped-today",
        ),
        pytest.param(
            "noreply@dhl.de",
            "Ihre Rechnung 4711",
            "Hallo Alex,\nIhre Bestellung Nr. 44550123 wird beim Zoll festgehalten. "
            "Anbei die Rechnung.\n",
            "dhl",
            id="held-at-customs-de",
        ),
        pytest.param(
            "noreply@dhl.de",
            "Ihre Rechnung 4711",
            "Hallo Alex,\nFür Ihre Bestellung Nr. 44550123 ist die "
            "Einfuhrumsatzsteuer offen. Anbei die Rechnung.\n",
            "dhl",
            id="import-vat-de",
        ),
        pytest.param(
            "noreply@dpd.fr",
            "Votre facture 4711",
            "Bonjour Alex,\nVotre commande n° 44550123 est retenue en douane. "
            "Votre facture est jointe.\n",
            "dpd",
            id="held-at-customs-fr",
        ),
    ],
)
def test_unread_invoice_with_news_asks_for_an_update(
    sender: str, subject: str, text: str, parser: str, tz: ZoneInfo
) -> None:
    """An invoice and shipping e-mail in one, unread, goes to the AI or review."""
    message = _message(sender, subject, text=text)
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser=parser, kind=MailKind.UNKNOWN, confidence=0.0, notes=UNPARSED_NOTES
    )


def test_unread_posting_receipt_is_skipped(calls: Calls, tz: ZoneInfo) -> None:
    """A carrier's posting receipt its parser can't read isn't asked about."""
    message = _message(
        "info@ctt.pt",
        "Comprovativo de envio RR123456785PT",
        text="Olá Alex,\nO seu envio RR123456785PT foi aceite. Acompanhe o seu envio.\n",
    )
    assert parse_message(message, _verdict(message), tz) == ParseResult(
        parser="ctt", kind=MailKind.NOT_PARCEL, confidence=0.9
    )


def test_customs_receipt_is_news(tz: ZoneInfo) -> None:
    """A receipt for customs charges paid isn't one for a parcel handed in."""
    message = _message(
        "notificacoes@ctt.pt",
        "Recibo do pagamento de encargos",
        text=(
            "Olá Alex,\n\nRecebemos o pagamento dos encargos do objeto "
            "LZ731940285CN. O objeto segue para entrega.\n"
        ),
    )
    result = parse_message(message, _verdict(message), tz)
    assert result.kind is MailKind.IN_TRANSIT
    assert [shipment.tracking_number for shipment in result.shipments] == [
        "LZ731940285CN"
    ]


def test_gate_error_keeps_the_reading(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tz: ZoneInfo
) -> None:
    """If the topic can't be checked, the parsers' reading stands."""

    def explode(*args: object, **kwargs: object) -> bool:
        raise RuntimeError(SECRET)

    monkeypatch.setattr(parsers.prefilter, "feedback_topic", explode)
    caplog.set_level(logging.DEBUG)
    subject = "Como correu a sua entrega?"
    message = _message(
        "inqueritos@ctt.pt",
        subject,
        text=f"Olá Alex, {SECRET}.\nO objeto RR123456785PT foi entregue.\n",
    )
    result = parse_message(message, _verdict(message), tz)
    assert result.kind is MailKind.DELIVERED
    assert "Topic gate failed: RuntimeError" in [
        record.getMessage() for record in caplog.records
    ]
    for record in caplog.records:
        logged = f"{record.getMessage()} {record.args!r} {record.exc_text or ''}"
        assert SECRET not in logged
        assert subject not in logged
        assert "RR123456785PT" not in logged


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


@pytest.mark.parametrize(
    "names",
    [
        ("known_sender_subject",),
        ("not_shipping_topic",),
        ("known_sender_subject", "not_shipping_topic"),
    ],
)
def test_prefilter_error_is_not_a_silent_skip(
    monkeypatch: pytest.MonkeyPatch,
    calls: Calls,
    tz: ZoneInfo,
    caplog: pytest.LogCaptureFixture,
    names: tuple[str, ...],
) -> None:
    """If the subject can't be checked, an unread e-mail goes to review."""

    def explode(*args: object, **kwargs: object) -> bool:
        raise RuntimeError(SECRET)

    for name in names:
        monkeypatch.setattr(parsers.prefilter, name, explode)
    message = _message("ship-confirm@amazon.es", OTHER_SUBJECT)
    with caplog.at_level(logging.DEBUG, logger=parsers.__name__):
        result = parse_message(message, _verdict(message), tz)
    assert result.kind is MailKind.UNKNOWN
    assert result.notes == UNPARSED_NOTES
    assert SECRET not in caplog.text


@pytest.mark.parametrize(
    ("path", "parser", "kind"),
    [
        ("amazon/shipped_de", "amazon", MailKind.SHIPPED),
        ("amazon/order_es", "amazon", MailKind.ORDER),
        ("shopify/shipped_pt", "shopify", MailKind.SHIPPED),
        ("shop/on_the_way_en", "shop", MailKind.IN_TRANSIT),
        ("amazon/delivery_code_es", "amazon", MailKind.CODE),
        ("carriers/dpd_delivery_code_pt", "dpd", MailKind.CODE),
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
    assert result.is_parcel
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


def test_carrier_changed_layout_asks_for_an_update(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
) -> None:
    """A carrier's shipping e-mail it can't read asks for a parser update."""
    message = load_eml("carriers/ups_changed_layout_en.eml")
    result = parse_message(message, verdict_for(message), tz)
    assert result.parser == "ups"
    assert result.kind is MailKind.UNKNOWN
    assert result.confidence == 0.0
    assert result.notes == UNPARSED_NOTES
    assert not result.shipments


@pytest.mark.parametrize(
    "path",
    [
        "carriers/correos_express_marketing_es",
        "carriers/dhl_marketing_de",
        "carriers/gls_marketing_it",
        "carriers/inpost_marketing_pt",
        "carriers/mrw_service_notice_es",
        "carriers/nacex_marketing_es",
        "carriers/paack_survey_es",
        "carriers/ups_marketing_en",
    ],
)
def test_carrier_fixtures_about_something_else(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    path: str,
) -> None:
    """A carrier's newsletters, surveys and notices are skipped, not reviewed."""
    message = load_eml(f"{path}.eml")
    result = parse_message(message, verdict_for(message), tz)
    assert result.kind is MailKind.NOT_PARCEL
    assert result.confidence == 0.9
    assert not result.notes
    assert not result.shipments


@pytest.mark.parametrize("path", ["amazon/refund_de", "amazon/refund_es"])
def test_refund_fixtures_are_marked(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    path: str,
) -> None:
    """A refund is no parcel event: it's marked for the engine to drop."""
    message = load_eml(f"{path}.eml")
    result = parse_message(message, verdict_for(message), tz)
    assert result.parser == "amazon"
    assert result.kind is MailKind.NOT_PARCEL
    assert result.confidence == 1.0
    assert result.notes == (NOTE_REFUND,)
    assert not result.shipments
    assert not result.order_numbers


@pytest.mark.parametrize(
    ("path", "confidence", "orders", "eta", "notes"),
    [
        (
            "amazon/return_pickup_pt",
            0.9,
            ("404-5528193-7720416",),
            None,
            (NOTE_PICKUP_NEXT_WORKING_DAY,),
        ),
        (
            "amazon/return_pickup_no_order_pt",
            0.8,
            (),
            None,
            (NOTE_PICKUP_NEXT_WORKING_DAY,),
        ),
        (
            "amazon/return_pickup_es",
            0.9,
            ("402-6619027-3348175",),
            Eta(date(2026, 11, 13), date(2026, 11, 13)),
            (),
        ),
    ],
)
def test_customer_return_fixtures(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    path: str,
    confidence: float,
    orders: tuple[str, ...],
    eta: Eta | None,
    notes: tuple[str, ...],
) -> None:
    """An Amazon return is a customer return with its pickup day.

    "Next working day" stays a note: the working days are the engine's.
    An e-mail without an order number or a return subject still counts.
    """
    message = load_eml(f"{path}.eml")
    result = parse_message(message, verdict_for(message), tz)
    assert result.parser == "amazon"
    assert result.kind is MailKind.CUSTOMER_RETURN
    assert result.confidence == confidence
    assert result.notes == notes
    assert result.order_numbers == orders
    assert len(result.items) == 1
    [shipment] = result.shipments
    assert shipment.eta == eta
    assert shipment.order_numbers == orders
    assert shipment.items == result.items


RETURN_SUBJECT = "Informação sobre o seu artigo"


@pytest.mark.parametrize(
    ("sender", "body", "kind", "notes"),
    [
        (
            "devolucoes@amazon.es",
            "Olá Alex Doe, a sua devolução foi registada.",
            MailKind.UNKNOWN,
            UNPARSED_NOTES,
        ),
        (
            "noreply@shop.app",
            "Hi Alex Doe, we've received your return.",
            MailKind.UNKNOWN,
            UNPARSED_NOTES,
        ),
        (
            "devolucoes@amazon.es",
            "A sua devolução foi registada.\nData de recolha: Dia útil seguinte",
            MailKind.CUSTOMER_RETURN,
            (NOTE_PICKUP_NEXT_WORKING_DAY,),
        ),
        (
            "devolucoes@amazon.es",
            "Olá Alex Doe, emitimos o seu reembolso de 12,99 €.",
            MailKind.NOT_PARCEL,
            (NOTE_REFUND,),
        ),
        # A body that only opens with an amount refunded is a refund: dropped.
        (
            "devolucoes@amazon.es",
            "Reembolso: 12,99 €.",
            MailKind.NOT_PARCEL,
            (NOTE_REFUND,),
        ),
        (
            "info@ctt.pt",
            "Olá Alex Doe, a sua devolução foi registada.",
            MailKind.NOT_PARCEL,
            (),
        ),
    ],
)
def test_unread_shop_return_is_not_skipped(
    calls: Calls,
    tz: ZoneInfo,
    sender: str,
    body: str,
    kind: MailKind,
    notes: tuple[str, ...],
) -> None:
    """A shop's return e-mail its parser can't read isn't silently skipped.

    The subject has no shipping words, but the body's return wording or
    pickup label says it's about a parcel; a refund is still dropped.
    Carriers' unread e-mails are judged by their subject, as before.
    """
    message = replace(_message(sender, RETURN_SUBJECT), text=body)
    result = parse_message(message, _verdict(message), tz)
    assert result.kind is kind
    assert result.notes == notes


@pytest.mark.parametrize(
    ("subject", "body", "kind", "notes"),
    [
        # Only a refund line says it's about a return.
        (
            "Devoluções",
            "Olá Alex Doe.\nReembolso de 12,99 € para o artigo Desk lamp, white.",
            MailKind.NOT_PARCEL,
            (),
        ),
        # A parcel going back to its sender is no customer return.
        (
            "A sua encomenda foi devolvida",
            "Olá Alex Doe.\nNão foi possível entregar a sua encomenda e foi "
            "devolvida ao remetente.",
            MailKind.UNKNOWN,
            UNPARSED_NOTES,
        ),
    ],
)
def test_orderless_amazon_mail_is_no_customer_return(
    tz: ZoneInfo, subject: str, body: str, kind: MailKind, notes: tuple[str, ...]
) -> None:
    """An Amazon e-mail without its order number needs customer-return words."""
    message = replace(_message("devolucoes@amazon.es", subject), text=body)
    result = parse_message(message, _verdict(message), tz)
    assert result.parser == "amazon"
    assert result.kind is kind
    assert result.notes == notes


@pytest.mark.parametrize(
    "extra", ["A sua devolução foi registada.", "Emitimos o seu reembolso."]
)
def test_shipping_mail_naming_a_return_keeps_its_shipment(
    load_eml: Callable[..., MailMessage],
    verdict_for: Callable[..., SenderVerdict],
    tz: ZoneInfo,
    extra: str,
) -> None:
    """A shipping e-mail that also confirms a return or a refund still ships.

    An exchange does both; the body's own status comes first.
    """
    message = load_eml("amazon/shipped_ctt_pt.eml")
    message = replace(
        message,
        subject="Informação sobre a sua encomenda",
        text=f"{message.text}\n{extra}",
    )
    result = parse_message(message, verdict_for(message), tz)
    assert result.kind is MailKind.SHIPPED
    assert result.order_numbers == ("406-1928374-5647382",)


def test_carrier_return_is_left_alone(
    monkeypatch: pytest.MonkeyPatch, calls: Calls, tz: ZoneInfo
) -> None:
    """A carrier's return is a parcel going back: shops' wording doesn't apply."""
    expected = ParseResult(parser="ctt", kind=MailKind.RETURN, confidence=0.9)
    monkeypatch.setattr(parsers.carriers, "parse_carrier", lambda *args: expected)
    message = replace(
        _message("info@ctt.pt", RETURN_SUBJECT), text="A sua devolução foi registada."
    )
    assert parse_message(message, _verdict(message), tz) is expected
