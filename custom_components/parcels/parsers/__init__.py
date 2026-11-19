"""E-mail parsers and the dispatcher that picks one for each e-mail.

``parse_message`` routes an e-mail by its sender: Amazon marketplaces go to
the Amazon parser, shop.app to the Shop app parser, e-mails sent through
Shopify to the Shopify parser, carriers with a dedicated parser to that
parser, and everything else to the generic parser. Shopify stores send
from their own domains, so Shopify is recognised by its DKIM signature and
its markers rather than by the sender. Parsers run for every sender,
authenticated or not; the engine applies the trust rules afterwards.

When a dedicated parser can't read an e-mail whose subject looks like
shipping mail, or a shop's e-mail whose body is about a return (a pickup
label, "your return"), the result is ``UNKNOWN`` with the ``known_sender_unparsed``
note, so the engine asks the AI and reports that the parser needs an
update; the sender's other e-mails (marketing, account e-mails) become
``NOT_PARCEL``. Parser errors never escape: only the parser's name and the
exception type are logged, at debug level, never anything from the e-mail.

Every result but a carrier's then goes through ``sort_returns``: a refund
becomes ``NOT_PARCEL`` with the ``refund`` note (the engine drops it), and
a customer return becomes ``CUSTOMER_RETURN``, apart from parcels going
back to their sender.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import tzinfo
import logging
import re

from ..const import MailKind
from . import amazon, auth, carriers, generic, prefilter, returns, senders, shopify
from .base import MailMessage, ParseResult, SenderVerdict

_LOGGER = logging.getLogger(__name__)

NOTE_KNOWN_SENDER_UNPARSED = "known_sender_unparsed"
NOT_PARCEL_CONFIDENCE = 0.9

PARSER_AMAZON = "amazon"
PARSER_SHOP = "shop"
PARSER_SHOPIFY = "shopify"
PARSER_GENERIC = "generic"
PARSER_NONE = "none"
# The shops' own parsers: their "return" e-mails are about customer returns.
_MERCHANT_PARSERS = frozenset({PARSER_AMAZON, PARSER_SHOP, PARSER_SHOPIFY})

_SHOPIFY_MAILER = "mailer@shopify.com"
_SHOPIFY_LINK_RE = re.compile(
    r"^https?://(?:[a-z0-9-]+\.)*(?:cdn\.shopify\.com|myshopify\.com)(?:[:/?#]|$)",
    re.IGNORECASE,
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
    return sort_returns(result, message, tz)


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


def _dispatch(message: MailMessage, verdict: SenderVerdict, tz: tzinfo) -> ParseResult:
    """Route the e-mail to its parser and apply the fallbacks."""
    hint = _parser_hint(message)
    if hint == PARSER_AMAZON:
        return _dedicated(PARSER_AMAZON, amazon.parse_amazon, message, verdict, tz)
    if hint == PARSER_SHOP:
        return _dedicated(PARSER_SHOP, shopify.parse_shop, message, verdict, tz)
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
    if _looks_like_shipping(message.subject) or (
        name in _MERCHANT_PARSERS and _about_a_return(message)
    ):
        return ParseResult(
            parser=name,
            kind=MailKind.UNKNOWN,
            confidence=0.0,
            notes=(NOTE_KNOWN_SENDER_UNPARSED,),
        )
    return ParseResult(
        parser=name, kind=MailKind.NOT_PARCEL, confidence=NOT_PARCEL_CONFIDENCE
    )


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
    """Return True when the subject has the prefilter's shipping keywords."""
    try:
        # No sender: known senders always pass the prefilter.
        return prefilter.is_candidate("", subject)
    except Exception as exc:
        _LOGGER.debug("Prefilter failed: %s", type(exc).__name__)
        return True
