"""E-mail parsers and the dispatcher that picks one for each e-mail.

``parse_message`` routes an e-mail by its sender: Amazon marketplaces go to
the Amazon parser, shop.app to the Shop app parser, Leroy Merlin to its
parser, e-mails sent through Shopify to the Shopify parser, carriers with a
dedicated parser to that parser, and everything else to the generic parser. Shopify stores send
from their own domains, so Shopify is recognised by its DKIM signature and
its markers rather than by the sender. Parsers run for every sender,
authenticated or not; the engine applies the trust rules afterwards.

When a dedicated parser can't read an e-mail whose subject looks like
shipping mail, whose body names an order or a parcel number in shipping
words ("A sua encomenda 001234567890 foi expedida"), or a shop's e-mail
whose body is about a return (a pickup label, "your return"), the result
is ``UNKNOWN`` with the ``known_sender_unparsed`` note, so the engine asks
the AI and reports that the parser needs an update; the sender's other
e-mails (marketing, account e-mails) become ``NOT_PARCEL``, and so do
e-mails whose subject asks for feedback, or is an invoice or a service
notice (``prefilter.not_shipping_topic``), even when they name an order,
a carrier's receipt for a parcel handed in, and a notice of a seller's
message or a prompt to complain (``prefilter.message_topic``) from anyone
but a carrier. An invoice whose body
brings news ("A sua encomenda n.º 123456 foi enviada") still asks for an
update. Parser errors never escape: only the parser's name and the
exception type are logged, at debug level, never anything from the e-mail.

Every result but a carrier's then goes through ``sort_returns``: a refund
becomes ``NOT_PARCEL`` with the ``refund`` note (the engine drops it), and
a customer return becomes ``CUSTOMER_RETURN``, apart from parcels going
back to their sender.

Then ``_gate`` checks the topic of what a parser read: surveys and review
requests, a carrier's receipt for a parcel handed in, invoices, and a
marketplace's notices of a seller's message or prompts to complain name a
parcel and its last status, but bring no news, so they become
``NOT_PARCEL``. A survey whose subject has no status and doesn't ask for
feedback ("A sua entrega de 4 de novembro") is found by its body, when
what it names is done or waiting at its point and the body asks to
answer questions or a survey (``prefilter.survey_request``). Carriers'
own messages are left to their parsers. An
invoice whose body brings news keeps its reading, at a confidence too low
to apply unchecked. A survey or a seller's message that no parser could
read becomes ``NOT_PARCEL`` too, so the local AI isn't asked about it.

Last, ``add_details`` (``parsers.details``) adds what the e-mail says
besides the status: the last day to collect a parcel at its pickup point,
the day of the next attempt after a missed one, and where a delivered
parcel was left.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import tzinfo
import logging
import re

from ..const import MailKind
from . import (
    amazon,
    auth,
    carriers,
    generic,
    leroymerlin,
    prefilter,
    returns,
    senders,
    shopify,
    tracking,
)
from .base import MailMessage, ParseResult, SenderVerdict
from .details import add_details
from .lang import fold

_LOGGER = logging.getLogger(__name__)

NOTE_KNOWN_SENDER_UNPARSED = "known_sender_unparsed"
NOT_PARCEL_CONFIDENCE = 0.9
# Below CONFIDENCE_APPLY: an invoice's news goes to the AI or Needs review.
INVOICE_CONFIDENCE = 0.6
# What a survey's body names: a delivery done, or a parcel at its point.
_CLOSING_KINDS = frozenset({MailKind.DELIVERED, MailKind.READY_FOR_PICKUP})

PARSER_AMAZON = "amazon"
PARSER_SHOP = "shop"
PARSER_SHOPIFY = "shopify"
PARSER_LEROYMERLIN = leroymerlin.PARSER
PARSER_GENERIC = "generic"
PARSER_NONE = "none"
# The shops' own parsers: their "return" e-mails are about customer returns.
_MERCHANT_PARSERS = frozenset(
    {PARSER_AMAZON, PARSER_SHOP, PARSER_SHOPIFY, PARSER_LEROYMERLIN}
)

_SHOPIFY_MAILER = "mailer@shopify.com"
_SHOPIFY_LINK_RE = re.compile(
    r"^https?://(?:[a-z0-9-]+\.)*(?:cdn\.shopify\.com|myshopify\.com)(?:[:/?#]|$)",
    re.IGNORECASE,
)
# "A sua encomenda 001234567890 foi expedida": a number without a label.
_BARE_NUMBER_RE = re.compile(
    r"(?<![a-z0-9])(?:order|pedido|encomenda|bestellung|auftrag|commande|ordine"
    r"|bestelling|envio|shipment|sendung|colis|spedizione|zending)\s+\d{6,}"
    r"(?![0-9a-z])"
)


def parse_message(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult:
    """Parse an e-mail with the best matching parser. Never raises.

    Returns the dedicated parser's result for known senders (or
    ``NOT_PARCEL`` / ``UNKNOWN`` with the ``known_sender_unparsed`` note
    when it can't read the e-mail), the generic parser's result for other
    senders, and an empty ``UNKNOWN`` result when no parser applies.
    """
    try:
        result = _dispatch(message, verdict, tz)
    except Exception as exc:
        _LOGGER.debug("Parser dispatch failed: %s", type(exc).__name__)
        return ParseResult(parser=PARSER_NONE, kind=MailKind.UNKNOWN, confidence=0.0)
    return add_details(_gate(sort_returns(result, message, tz), message), message, tz)


def sort_returns(
    result: ParseResult,
    message: MailMessage,
    tz: tzinfo,
    *,
    parser: str | None = None,
) -> ParseResult:
    """Tell refunds and customer returns apart from parcels sent back.

    ``parser`` names the parser that recognised the sender, for a result
    read elsewhere (the local AI's). Carriers' e-mails are left alone: when
    a carrier says "returned", the parcel is going back to its sender.
    Never raises.
    """
    name = parser or result.parser
    if name in carriers.CARRIER_PARSERS:
        return result
    try:
        return returns.reclassify(
            result, message, tz, merchant=name in _MERCHANT_PARSERS
        )
    except Exception as exc:
        _LOGGER.debug("Return check failed: %s", type(exc).__name__)
        return result


def is_refund(result: ParseResult) -> bool:
    """Return True for a refund e-mail: never a parcel event."""
    return result.kind is MailKind.NOT_PARCEL and returns.NOTE_REFUND in result.notes


def _gate(result: ParseResult, message: MailMessage) -> ParseResult:
    """Keep surveys, a carrier's posting receipts and invoices from counting.

    They name a parcel and its last status ("O objeto ... foi entregue.
    Avalie a entrega"), but bring no news about it. So do a marketplace's
    notices of a seller's message and prompts to complain ("Recebeu uma
    mensagem referente à encomenda nº ..."), except a carrier's: what a
    seller writes isn't the carrier's news. A subject with a status of its
    own ("Entrega concluída: avalie a entrega") is news, and counts. A
    survey whose subject says neither ("A sua entrega de 4 de novembro") is
    found by its body (``_survey``). An
    invoice whose body brings news keeps its reading, capped below
    ``CONFIDENCE_APPLY``. A parser's undated, attach-only confirmation, such
    as Leroy Merlin's survey after a delivery, stands. When nothing was
    read, a survey or a seller's message becomes ``NOT_PARCEL`` too, so the
    local AI isn't asked about it. Never raises: when the check fails, the
    reading stands.
    """
    if result.kind is MailKind.NOT_PARCEL:
        return result
    try:
        if not (result.is_parcel or result.shipments or result.order_numbers):
            if prefilter.feedback_topic(message.subject) or _seller_message(message):
                return _not_parcel(result.parser)
            return result
        if result.shipments and all(
            shipment.attach_only and shipment.undated for shipment in result.shipments
        ):
            return result
        subject = message.subject
        if (
            prefilter.feedback_topic(subject)
            or (
                result.parser in carriers.CARRIER_PARSERS
                and prefilter.sent_receipt(subject)
            )
            or _seller_message(message)
            or _survey(result, message)
        ):
            return _not_parcel(result.parser)
        if prefilter.invoice_topic(subject):
            if not prefilter.has_news_words(message.text[: generic.SCAN_CHARS]):
                return _not_parcel(result.parser)
            return replace(
                result, confidence=min(result.confidence, INVOICE_CONFIDENCE)
            )
    except Exception as exc:
        _LOGGER.debug("Topic gate failed: %s", type(exc).__name__)
    return result


def _survey(result: ParseResult, message: MailMessage) -> bool:
    """Return True for a survey about a delivery, found by its body.

    The subject has no status ("A sua entrega de 4 de novembro", "We'd
    love to hear from you"), every shipment read is delivered or waiting
    at its point ("foi entregue no Locker ..."), and the body asks to
    answer questions or a survey about it ("Responda a 3 perguntas sobre a
    entrega"). Other news, and a delivery whose footer only asks for a
    rating ("Avalie a entrega"), keep their reading.
    """
    kinds = {s.kind or result.kind for s in result.shipments} or {result.kind}
    return kinds <= _CLOSING_KINDS and prefilter.survey_request(
        message.subject, message.text[: generic.SCAN_CHARS]
    )


def _not_parcel(name: str) -> ParseResult:
    """Result for an e-mail that isn't about a parcel."""
    return ParseResult(
        parser=name, kind=MailKind.NOT_PARCEL, confidence=NOT_PARCEL_CONFIDENCE
    )


def _dispatch(message: MailMessage, verdict: SenderVerdict, tz: tzinfo) -> ParseResult:
    """Route the e-mail to its parser and apply the fallbacks."""
    hint = _parser_hint(message)
    if hint == PARSER_AMAZON:
        return _dedicated(PARSER_AMAZON, amazon.parse_amazon, message, verdict, tz)
    if hint == PARSER_SHOP:
        return _dedicated(PARSER_SHOP, shopify.parse_shop, message, verdict, tz)
    if hint == PARSER_LEROYMERLIN:
        return _dedicated(
            PARSER_LEROYMERLIN, leroymerlin.parse_leroymerlin, message, verdict, tz
        )
    if hint is not None and hint in carriers.CARRIER_PARSERS:
        result = _run(hint, carriers.parse_carrier, message, verdict, tz, hint)
        return result if result is not None else _unparsed(hint, message)
    if hint == PARSER_SHOPIFY or _shopify_signed(message, verdict):
        return _dedicated(PARSER_SHOPIFY, shopify.parse_shopify, message, verdict, tz)
    if _shopify_marked(message, verdict):
        # Weak markers (a Shopify image or link) don't identify the sender:
        # an e-mail the Shopify parser can't read goes to the generic parser.
        result = _run(PARSER_SHOPIFY, shopify.parse_shopify, message, verdict, tz)
        if result is not None:
            return result
    result = _run(PARSER_GENERIC, generic.parse_generic, message, verdict, tz)
    if result is not None:
        return result
    return ParseResult(parser=PARSER_NONE, kind=MailKind.UNKNOWN, confidence=0.0)


def _parser_hint(message: MailMessage) -> str | None:
    """Return the dedicated parser of the sender's domain, if any."""
    try:
        info = senders.lookup(message.sender_domain)
    except Exception as exc:
        _LOGGER.debug("Sender lookup failed: %s", type(exc).__name__)
        return None
    return info.parser if info is not None else None


def _shopify_signed(message: MailMessage, verdict: SenderVerdict) -> bool:
    """Return True when Shopify's DKIM signature passed for the e-mail."""
    if not verdict.shopify:
        return False
    result = message.auth
    if result is None and (raw := message.headers.get("authentication-results")):
        try:
            result = auth.parse_authentication_results(raw)
        except Exception as exc:
            _LOGGER.debug("Authentication-Results failed: %s", type(exc).__name__)
            return False
    return result is not None and any(
        senders.organizational_domain(domain) in auth.SHOPIFY_DKIM_DOMAINS
        for domain in result.dkim_pass_domains
    )


def _shopify_marked(message: MailMessage, verdict: SenderVerdict) -> bool:
    """Return True for weak signs that the e-mail came through Shopify."""
    return (
        verdict.shopify
        or message.sender.lower() == _SHOPIFY_MAILER
        or any(name.lower().startswith("x-shopify-") for name in message.headers)
        or any(_SHOPIFY_LINK_RE.match(link.url) for link in message.links)
    )


def _run(
    name: str, parser: Callable[..., ParseResult | None], *args: object
) -> ParseResult | None:
    """Call a parser; return None when it fails, logging no e-mail content."""
    try:
        result = parser(*args)
    except Exception as exc:
        _LOGGER.debug("Parser %s failed: %s", name, type(exc).__name__)
        return None
    if result is not None and not isinstance(result, ParseResult):
        _LOGGER.debug("Parser %s returned %s", name, type(result).__name__)
        return None
    return result


def _dedicated(
    name: str,
    parser: Callable[[MailMessage, SenderVerdict, tzinfo], ParseResult | None],
    message: MailMessage,
    verdict: SenderVerdict,
    tz: tzinfo,
) -> ParseResult:
    """Run a known sender's parser, falling back to an unparsed result."""
    result = _run(name, parser, message, verdict, tz)
    return result if result is not None else _unparsed(name, message)


def _unparsed(name: str, message: MailMessage) -> ParseResult:
    """Result for a known sender's e-mail that its parser couldn't read."""
    subject = message.subject
    if _other_topic(subject):
        if _invoice(subject) and _numbered_shipping(message, news_only=True):
            return _asks_for_update(name)
        return _not_parcel(name)
    if _seller_message(message):
        return _not_parcel(name)
    if name in carriers.CARRIER_PARSERS and _sent_receipt(subject):
        return _not_parcel(name)
    if (
        _looks_like_shipping(subject)
        or _numbered_shipping(message)
        or (name in _MERCHANT_PARSERS and _about_a_return(message))
    ):
        return _asks_for_update(name)
    return _not_parcel(name)


def _asks_for_update(name: str) -> ParseResult:
    """Result for a shipping e-mail that a known sender's parser can't read."""
    return ParseResult(
        parser=name,
        kind=MailKind.UNKNOWN,
        confidence=0.0,
        notes=(NOTE_KNOWN_SENDER_UNPARSED,),
    )


def _numbered_shipping(message: MailMessage, *, news_only: bool = False) -> bool:
    """Return True when the body names an order or a parcel in shipping words.

    The subject can be plain ("Uma mensagem para si") while the body says
    "A sua encomenda 001234567890 foi expedida". With ``news_only``, the
    words any invoice has (tracking-number labels, thanks for the order)
    don't count.
    """
    try:
        text = message.text[: generic.SCAN_CHARS]
        words = prefilter.has_news_words if news_only else prefilter.has_shipping_words
        if not words(text):
            return False
        return bool(
            _BARE_NUMBER_RE.search(fold(text))
            or generic.find_order_numbers(text)
            or tracking.find_tracking_numbers(text)
        )
    except Exception as exc:
        _LOGGER.debug("Body check failed: %s", type(exc).__name__)
        return True


def _about_a_return(message: MailMessage) -> bool:
    """Return True when the body is about a return, refunds aside.

    A return's subject can lack shipping words ("About your item's
    pickup"), while its pickup label or return wording says it's a parcel.
    """
    try:
        found = returns.classify(message.subject, message.text)
    except Exception as exc:
        _LOGGER.debug("Return check failed: %s", type(exc).__name__)
        return True
    return found is not None and found.kind is not returns.ReturnClass.REFUND


def _looks_like_shipping(subject: str) -> bool:
    """Return True when the subject has shipping words, carrier names aside."""
    try:
        return prefilter.known_sender_subject(subject)
    except Exception as exc:
        _LOGGER.debug("Prefilter failed: %s", type(exc).__name__)
        return True


def _other_topic(subject: str) -> bool:
    """Return True when the subject asks for feedback, or is an invoice or a notice."""
    try:
        return prefilter.not_shipping_topic(subject)
    except Exception as exc:
        _LOGGER.debug("Topic check failed: %s", type(exc).__name__)
        return False


def _invoice(subject: str) -> bool:
    """Return True when the subject is an invoice."""
    try:
        return prefilter.invoice_topic(subject)
    except Exception as exc:
        _LOGGER.debug("Topic check failed: %s", type(exc).__name__)
        return False


def _seller_message(message: MailMessage) -> bool:
    """Return True for a seller's message or a prompt to complain, not a carrier's.

    A carrier's own message may be news, so carriers' e-mails are left to
    their parsers; so are messages from whoever brings the parcel
    (``prefilter.message_topic``).
    """
    try:
        if not prefilter.message_topic(message.subject):
            return False
        info = senders.lookup(message.sender_domain)
    except Exception as exc:
        _LOGGER.debug("Topic check failed: %s", type(exc).__name__)
        return False
    return info is None or info.kind != "carrier"


def _sent_receipt(subject: str) -> bool:
    """Return True when the subject is a receipt for a parcel handed in."""
    try:
        return prefilter.sent_receipt(subject)
    except Exception as exc:
        _LOGGER.debug("Topic check failed: %s", type(exc).__name__)
        return False
