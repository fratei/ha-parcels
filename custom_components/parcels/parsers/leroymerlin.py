"""Parser for Leroy Merlin's e-mails (Portugal).

Leroy Merlin sends its own e-mails about orders and marketplace shipments
("Encomenda em distribuição!", "Envio entregue. Até breve!"), a survey
after each shipment, and some of its carriers' notices from its own domain
under the carrier's name ("GLS PT Informa"). Its newsletters come from a
subdomain (mailing.leroymerlin.pt) and are never about a parcel.

The e-mails name the order ("Encomenda n.º"), Leroy Merlin's shipment
number ("Envio n.º"), the marketplace seller ("Vendido e expedido por")
and the items. The shipment number is the shop's reference, which links
the shipment's e-mails and its survey; it's the tracking number too when
it validates for the carrier the e-mail names. The survey
says that the shipment came, not when: it can add a delivery to a parcel
already known, never make one.

The status comes from the subject. Read from the body alone, it's
uncertain, and the e-mail goes to the AI or to review.
"""

from __future__ import annotations

from datetime import tzinfo
import re

from ..const import MailKind
from . import tracking
from ._amazon_shopify_common import (
    MAX_MERCHANT_CHARS,
    carrier_from_url,
    carrier_mentions,
    clip,
    find_numbers,
    fold_text,
    label_values,
    line_bounds,
    named_carriers,
    pickup_point,
    quantity_items,
)
from .base import MailMessage, ParsedShipment, ParseResult, SenderVerdict
from .carriers import brand_carriers
from .generic import (
    KIND_BODY_CHARS,
    MAX_SUBJECT_CHARS,
    NOTE_KIND_DEFAULT,
    NOTE_KIND_FROM_BODY,
    NOTE_KIND_FROM_SUBJECT,
    SCAN_CHARS,
    detect_kind,
    find_order_numbers,
    is_bounce,
    message_eta,
)
from .lang import detect_language

PARSER = "leroymerlin"
MERCHANT = "Leroy Merlin"

CONFIDENCE = 0.8
# A status read from the body alone: below CONFIDENCE_APPLY.
BODY_KIND_CONFIDENCE = 0.6
NOT_PARCEL_CONFIDENCE = 0.9

# Shipment numbers are written with at least this many digits.
MIN_NUMBER_DIGITS = 4
# How far before a carrier's name "pela" ("by") may start.
BY_CARRIER_CHARS = 40

_NEWSLETTER_PREFIX = "mailing."

# Matched on folded text: "n.º" folds to "n.o".
_NO = r"n\.?\s*o\.?"
_ORDER_RE = re.compile(
    rf"(?<![a-z])encomenda\s+(?:{_NO}\s*)?[:#]?\s*(\d{{6,14}})(?![0-9a-z])"
)
_SHIPMENT_RE = re.compile(
    rf"(?<![a-z])(?:envio(?:\s+{_NO})?|(?:numero|{_NO})\s+d[eo]\s+envio|o\s+volume)"
    r"\s*[:#]?\s*([0-9a-z]{8,14})(?![0-9a-z])"
)
_SURVEY_RE = re.compile(
    rf"opiniao\s+sobre\s+o\s+(?:seu\s+)?envio\s+(?:{_NO}\s*)?([0-9a-z]{{6,14}})"
    r"\s+de\s+(\S.*)$"
)
# Only at the start of a line, so prose ("o artigo vendido por") never counts.
_SELLER_RE = re.compile(
    r"^[ \t]*(?:vendido\s+e\s+(?:expedido|enviado)\s+por|vendido\s+por|vendedor)"
    r"(?![a-z])\s*:?",
    re.MULTILINE,
)
# The words right before a carrier's name that make it the one delivering:
# "entregue hoje pela GLS", "via DPD", "Transportadora: GLS".
_BY_CARRIER_RE = re.compile(
    r"(?:^|[^a-z0-9])(?:pel[ao]s?|via|com\s+a|atraves\s+d[aeo]s?|transportadora:?)"
    r"\s+$"
)
_NAME_WORDS_RE = re.compile(r"[a-z0-9]+")


def parse_leroymerlin(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult | None:
    """Read an e-mail from Leroy Merlin.

    Returns ``NOT_PARCEL`` for newsletters and bounces, and None when the
    e-mail has no status or nothing that identifies the order or the
    shipment; the dispatcher then decides between review and ``NOT_PARCEL``.
    """
    if message.sender_domain.lower().startswith(_NEWSLETTER_PREFIX) or is_bounce(
        message
    ):
        return ParseResult(
            parser=PARSER, kind=MailKind.NOT_PARCEL, confidence=NOT_PARCEL_CONFIDENCE
        )
    subject = message.subject[:MAX_SUBJECT_CHARS]
    text = message.text[:SCAN_CHARS]
    language = message.language or detect_language(
        f"{subject}\n{text[:KIND_BODY_CHARS]}"
    )
    if (survey := _survey(subject, language)) is not None:
        return survey

    relayed = brand_carriers(message.sender_name)
    relay = relayed[0] if len(relayed) == 1 else None
    kind, source = detect_kind(subject, text, lang=language)
    if kind is None and relay is None:
        return None

    folded = fold_text(text)
    carrier = relay or _body_carrier(folded) or _link_carrier(message)
    number = _shipment_number(text, folded)
    tracking_number: str | None = None
    if number is not None:
        if carrier is None and (detected := tracking.detect_carrier(number)):
            carrier = detected
        if carrier is not None and tracking.validate_tracking_number(number, carrier):
            tracking_number = number
    # The shop's shipment number, which its survey names, stays its reference
    # when it's the carrier's tracking number too. A carrier's notice has the
    # carrier's number.
    reference = number if relay is None or tracking_number is None else None
    orders = _orders(f"{subject}\n{text}", exclude={number} if number else set())
    if tracking_number is None:
        exclude = frozenset(orders) | ({number} if number else set())
        found = {
            (match.carrier, match.number)
            for match in find_numbers(
                text, folded, message.links, exclude=exclude, allow_other=False
            )
            if carrier is None or match.carrier == carrier
        }
        if len(found) == 1:
            carrier, tracking_number = found.pop()
    if not (orders or reference or tracking_number):
        return None

    notes: list[str] = []
    if kind is None:
        kind = MailKind.SHIPPED
        notes.append(NOTE_KIND_DEFAULT)
    else:
        notes.append(
            NOTE_KIND_FROM_SUBJECT if source == "subject" else NOTE_KIND_FROM_BODY
        )
    certain = source == "subject" or (relay is not None and tracking_number)

    items: list[str] = []
    quantity_items(text, folded, items)
    order_numbers = tuple(orders)
    shipment = ParsedShipment(
        carrier=carrier,
        tracking_number=tracking_number,
        kind=kind,
        eta=message_eta(message, kind, tz, language),
        pickup_point=(
            pickup_point(text, folded) if kind is MailKind.READY_FOR_PICKUP else None
        ),
        reference=reference,
        order_numbers=order_numbers,
        tracking_url=(
            tracking.tracking_url(carrier, tracking_number) if tracking_number else None
        ),
        seller=None if relay else _label_seller(text, folded),
    )
    return ParseResult(
        parser=PARSER,
        kind=kind,
        merchant=MERCHANT,
        order_numbers=order_numbers,
        shipments=[shipment],
        items=tuple(items),
        confidence=CONFIDENCE if certain else BODY_KIND_CONFIDENCE,
        language=language,
        notes=tuple(notes),
    )


def _survey(subject: str, language: str | None) -> ParseResult | None:
    """Read the survey after a shipment: it came, by the time of the e-mail."""
    match = _SURVEY_RE.search(fold_text(subject))
    if match is None:
        return None
    number = subject[match.start(1) : match.end(1)]
    if not _number_like(number):
        return None
    shipment = ParsedShipment(
        kind=MailKind.DELIVERED,
        reference=number,
        seller=_seller(subject[match.start(2) :]),
        attach_only=True,
        undated=True,
    )
    return ParseResult(
        parser=PARSER,
        kind=MailKind.DELIVERED,
        merchant=MERCHANT,
        shipments=[shipment],
        confidence=CONFIDENCE,
        language=language,
    )


def _shipment_number(text: str, folded: str) -> str | None:
    """Return the shipment number written after its label, as written."""
    for match in _SHIPMENT_RE.finditer(folded):
        number = text[match.start(1) : match.end(1)]
        if _number_like(number):
            return number
    return None


def _orders(text: str, exclude: set[str]) -> list[str]:
    """Return the order numbers, including "a sua encomenda 51800012"."""
    found: list[str] = []
    labelled = [match[1] for match in _ORDER_RE.finditer(fold_text(text))]
    for number in [*find_order_numbers(text), *labelled]:
        if number not in found and number not in exclude:
            found.append(number)
    return found


def _body_carrier(folded: str) -> str | None:
    """Return the only carrier the body names as delivering the parcel."""
    found = {mention.carrier for mention in named_carriers(folded)}
    for mention in carrier_mentions(folded):
        start, _ = line_bounds(folded, mention.start)
        before = folded[max(start, mention.start - BY_CARRIER_CHARS) : mention.start]
        if _BY_CARRIER_RE.search(before):
            found.add(mention.carrier)
    return found.pop() if len(found) == 1 else None


def _link_carrier(message: MailMessage) -> str | None:
    """Return the only carrier whose website the e-mail links to."""
    found = {
        carrier for link in message.links if (carrier := carrier_from_url(link.url))
    }
    return found.pop() if len(found) == 1 else None


def _label_seller(text: str, folded: str) -> str | None:
    """Return the marketplace seller written after "Vendido por"."""
    for value in label_values(text, folded, _SELLER_RE):
        if seller := _seller(value.value):
            return seller
    return None


def _seller(name: str) -> str | None:
    """Return a seller's name, or None for Leroy Merlin itself."""
    seller = clip(name, MAX_MERCHANT_CHARS).rstrip(" .!?")
    words = _NAME_WORDS_RE.findall(fold_text(seller))
    if not words or words[:2] == ["leroy", "merlin"]:
        return None
    return seller


def _number_like(value: str) -> bool:
    return sum(char.isdigit() for char in value) >= MIN_NUMBER_DIGITS
