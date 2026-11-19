"""Conversions between parser or AI results, review suggestions and parcels."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import replace
from datetime import datetime

from .const import CONFIDENCE_APPLY, KIND_TO_STATUS, MailKind, ParcelStatus
from .dedup import Contribution
from .models import (
    FILL_ORIGIN_SUFFIX,
    MAX_ITEMS,
    Origin,
    ParcelEvent,
    ParcelState,
    Source,
    Suggestion,
)
from .parsers.base import Eta, ParsedShipment, ParseResult
from .parsers.tracking import normalize_tracking_number

_NOT_PARCEL = (MailKind.NOT_PARCEL, MailKind.UNKNOWN)
# The parser results whose gaps the local AI may fill in.
_FILL_KINDS = frozenset(
    {
        MailKind.ORDER,
        MailKind.SHIPPED,
        MailKind.IN_TRANSIT,
        MailKind.OUT_FOR_DELIVERY,
        MailKind.DELAYED,
        MailKind.ATTEMPTED,
        MailKind.READY_FOR_PICKUP,
    }
)


def has_identifier(result: ParseResult) -> bool:
    """Return True when a result names an order, shipment or tracking number."""
    return bool(result.order_numbers) or any(
        shipment.tracking_number
        or shipment.amazon_shipment_id
        or shipment.order_numbers
        for shipment in result.shipments
    )


def is_confident(result: ParseResult) -> bool:
    """Return True when a result is good enough to apply without review."""
    return (
        result.is_parcel
        and result.confidence >= CONFIDENCE_APPLY
        and has_identifier(result)
    )


def message_origin_id(message_hash: str, index: int) -> str:
    """Return the ID of the origin of the ``index``-th parcel in an e-mail."""
    return f"msg:{message_hash}#{index}"


def _unique(values: list[str | None]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def result_contributions(
    result: ParseResult,
    *,
    message_hash: str,
    time: datetime,
    source: Source,
    label: str = "",
    owner: str | None = None,
    confirmed: bool = False,
) -> list[Contribution]:
    """Return one contribution per parcel in a parser or AI result.

    ``time`` is the e-mail's date. An e-mail about an order without shipment
    details becomes an order-only contribution, which creates a provisional
    parcel until a shipping e-mail absorbs it.
    """
    if not result.is_parcel:
        return []
    shipments = list(result.shipments) or [ParsedShipment()]
    single = len(shipments) == 1
    contributions: list[Contribution] = []
    for index, shipment in enumerate(shipments):
        kind = shipment.kind if shipment.kind not in (None, *_NOT_PARCEL) else None
        kind = kind or result.kind
        status = KIND_TO_STATUS.get(kind)
        event_time = time
        if shipment.event_time and shipment.event_time.tzinfo is not None:
            # A parcel can't have moved after the e-mail about it was sent.
            event_time = min(shipment.event_time, time)
        items = shipment.items or (result.items if single else ())
        origin = Origin(
            id=message_origin_id(message_hash, index),
            source=source,
            time=time,
            label=label,
            carrier=shipment.carrier,
            tracking_number=shipment.tracking_number,
            amazon_shipment_id=shipment.amazon_shipment_id,
            merchant=result.merchant,
            order_numbers=shipment.order_numbers or result.order_numbers,
            items=tuple(items[:MAX_ITEMS]),
            pickup_point=shipment.pickup_point,
            pickup_code=shipment.pickup_code,
            # Links found by the AI are never used.
            tracking_url=shipment.tracking_url if source is not Source.AI else None,
            message=message_hash,
            owners=(owner,) if owner else (),
            confirmed=confirmed,
        )
        events: list[ParcelEvent] = []
        if status is not None or shipment.eta is not None:
            events.append(
                ParcelEvent(
                    time=event_time,
                    source=source,
                    status=status,
                    kind=kind,
                    eta=shipment.eta,
                )
            )
        contributions.append(
            Contribution(
                origin=origin,
                events=events,
                order_placed=time if kind is MailKind.ORDER else None,
                # An e-mail with just a delivery code adds it to its parcel.
                attach_only=kind is MailKind.CODE and not confirmed,
            )
        )
    return contributions


def suggestion_from_result(result: ParseResult | None) -> Suggestion | None:
    """Return what a result found, for the "Needs review" list.

    Returns None when the result holds nothing worth showing.
    """
    if result is None or result.kind is MailKind.NOT_PARCEL:
        return None
    shipments = result.shipments
    kind = result.kind
    if kind is MailKind.UNKNOWN:
        kind = next(
            (s.kind for s in shipments if s.kind and s.kind not in _NOT_PARCEL),
            MailKind.UNKNOWN,
        )
    eta = next((s.eta for s in shipments if s.eta), None)
    suggestion = Suggestion(
        kind=kind,
        merchant=result.merchant,
        carrier=next((s.carrier for s in shipments if s.carrier), None),
        tracking_numbers=_unique(
            [normalize_tracking_number(s.tracking_number or "") for s in shipments]
        ),
        order_numbers=_unique(
            [*result.order_numbers, *(n for s in shipments for n in s.order_numbers)]
        ),
        eta_start=eta.start if eta else None,
        eta_end=eta.end if eta else None,
        window_start=eta.window_start if eta else None,
        window_end=eta.window_end if eta else None,
        pickup_point=next((s.pickup_point for s in shipments if s.pickup_point), None),
        pickup_code=next((s.pickup_code for s in shipments if s.pickup_code), None),
        items=_unique([*result.items, *(i for s in shipments for i in s.items)])[
            :MAX_ITEMS
        ],
        amazon_shipment_id=next(
            (s.amazon_shipment_id for s in shipments if s.amazon_shipment_id), None
        ),
    )
    if (
        kind is MailKind.UNKNOWN
        and not suggestion.tracking_numbers
        and not suggestion.order_numbers
        and not suggestion.amazon_shipment_id
    ):
        return None
    return suggestion


def suggestion_kind(suggestion: Suggestion) -> MailKind:
    """Return the kind to record for an accepted suggestion.

    When the kind is unknown, a tracking number means the parcel was shipped
    and an order number alone means it was ordered.
    """
    if suggestion.kind not in _NOT_PARCEL:
        return suggestion.kind
    if suggestion.tracking_numbers or suggestion.amazon_shipment_id:
        return MailKind.SHIPPED
    return MailKind.ORDER


def _suggestion_eta(suggestion: Suggestion) -> Eta | None:
    if not suggestion.eta_start:
        return None
    end = suggestion.eta_end or suggestion.eta_start
    return Eta(
        start=suggestion.eta_start,
        end=max(end, suggestion.eta_start),
        window_start=suggestion.window_start,
        window_end=suggestion.window_end,
    )


def suggestion_result(suggestion: Suggestion, source: Source) -> ParseResult:
    """Turn a suggestion, possibly edited by the user, into a result."""
    kind = suggestion_kind(suggestion)
    eta = _suggestion_eta(suggestion)
    numbers: list[str | None] = list(suggestion.tracking_numbers) or [None]
    single = len(numbers) == 1
    shipments = [
        ParsedShipment(
            carrier=suggestion.carrier,
            tracking_number=number,
            kind=kind,
            eta=eta,
            pickup_point=suggestion.pickup_point if single else None,
            pickup_code=suggestion.pickup_code if single else None,
            amazon_shipment_id=suggestion.amazon_shipment_id if single else None,
        )
        for number in numbers
    ]
    return ParseResult(
        parser="review",
        kind=kind,
        merchant=suggestion.merchant,
        order_numbers=suggestion.order_numbers,
        shipments=shipments,
        items=suggestion.items,
        confidence=1.0,
        source=source.value,
    )


def _shipment_kind(shipment: ParsedShipment, result: ParseResult) -> MailKind:
    kind = shipment.kind if shipment.kind not in (None, *_NOT_PARCEL) else None
    return kind or result.kind


def fill_origin_id(message_hash: str) -> str:
    """Return the ID of the origin holding what the AI filled in for an e-mail."""
    return f"msg:{message_hash}{FILL_ORIGIN_SUFFIX}"


def fill_gaps(
    result: ParseResult, state: ParcelState, *, carrier_mail: bool
) -> set[str]:
    """Return what the local AI may fill in after a parser read an e-mail.

    Only for an open parcel with one shipment in the e-mail, and only what
    neither the parser's result nor the parcel has: the delivery date, the
    items (not from a carrier's own e-mail, which rarely lists them) and,
    once the parcel is shipped, the tracking number and the carrier.
    """
    if state.terminal or len(result.shipments) > 1:
        return set()
    shipment = result.shipments[0] if result.shipments else ParsedShipment()
    kind = _shipment_kind(shipment, result)
    if kind not in _FILL_KINDS:
        return set()
    gaps: set[str] = set()
    if shipment.eta is None and state.eta is None:
        gaps.add("eta")
    if not carrier_mail and not (shipment.items or result.items or state.items):
        gaps.add("items")
    if kind is not MailKind.ORDER:
        if not shipment.tracking_number and not state.tracking_number:
            gaps.add("tracking_number")
        if not shipment.carrier and not state.carrier:
            gaps.add("carrier")
    return gaps


def fill_suggestion(
    ai: ParseResult | None, gaps: Collection[str], parser: ParseResult
) -> Suggestion | None:
    """Return the gaps the local AI's checked answer fills, with the parser's kind.

    Each value must be the only one the AI found. Returns None when it found
    none of them, or when its answer may be about another parcel: a tracking
    number the parser didn't read, or more than one.
    """
    if ai is None or not ai.is_parcel or not gaps:
        return None
    shipments = ai.shipments
    numbers = _unique(
        [normalize_tracking_number(s.tracking_number or "") for s in shipments]
    )
    known = {
        normalize_tracking_number(s.tracking_number)
        for s in parser.shipments
        if s.tracking_number
    }
    if len(numbers) > 1 or (known and numbers and numbers[0] not in known):
        return None
    eta: Eta | None = None
    etas = [s.eta for s in shipments if s.eta]
    if "eta" in gaps and etas and all(other == etas[0] for other in etas):
        eta = etas[0]
    items: tuple[str, ...] = ()
    if "items" in gaps:
        items = _unique([*ai.items, *(i for s in shipments for i in s.items)])
    carriers = _unique([s.carrier for s in shipments])
    carrier = carriers[0] if "carrier" in gaps and len(carriers) == 1 else None
    number = numbers[0] if "tracking_number" in gaps and numbers else None
    if eta is None and not items and carrier is None and number is None:
        return None
    first = parser.shipments[0] if parser.shipments else ParsedShipment()
    return Suggestion(
        kind=_shipment_kind(first, parser),
        carrier=carrier,
        tracking_numbers=(number,) if number else (),
        eta_start=eta.start if eta else None,
        eta_end=eta.end if eta else None,
        window_start=eta.window_start if eta else None,
        window_end=eta.window_end if eta else None,
        items=items[:MAX_ITEMS],
    )


def fill_fields(suggestion: Suggestion) -> set[str]:
    """Return the gaps that a fill of the local AI fills."""
    fields: set[str] = set()
    if suggestion.eta_start is not None:
        fields.add("eta")
    if suggestion.items:
        fields.add("items")
    if suggestion.tracking_numbers:
        fields.add("tracking_number")
    if suggestion.carrier:
        fields.add("carrier")
    return fields


def merge_fills(old: Suggestion, new: Suggestion) -> Suggestion:
    """Return a new fill, keeping what an earlier one found and it didn't."""
    if new.eta_start is None:
        new = replace(
            new,
            eta_start=old.eta_start,
            eta_end=old.eta_end,
            window_start=old.window_start,
            window_end=old.window_end,
        )
    return replace(
        new,
        carrier=new.carrier or old.carrier,
        tracking_numbers=new.tracking_numbers or old.tracking_numbers,
        items=new.items or old.items,
    )


def fill_contribution(
    suggestion: Suggestion,
    *,
    message_hash: str,
    time: datetime,
    label: str = "",
    owner: str | None = None,
    confirmed: bool = False,
) -> Contribution | None:
    """Return what the AI filled in for an e-mail, for its parser's parcel.

    Only the date, items, tracking number and carrier count. The contribution
    joins the parcel that holds the parser's origin for the same e-mail, and
    nothing else; None when there's nothing to add.
    """
    eta = _suggestion_eta(suggestion)
    number = suggestion.tracking_numbers[0] if suggestion.tracking_numbers else None
    items = suggestion.items[:MAX_ITEMS]
    if eta is None and not items and not number and not suggestion.carrier:
        return None
    origin = Origin(
        id=fill_origin_id(message_hash),
        source=Source.AI,
        time=time,
        label=label,
        carrier=suggestion.carrier,
        tracking_number=number,
        items=items,
        message=message_hash,
        owners=(owner,) if owner else (),
        confirmed=confirmed,
    )
    events = (
        [ParcelEvent(time=time, source=Source.AI, status=None, kind=None, eta=eta)]
        if eta
        else []
    )
    return Contribution(
        origin=origin, events=events, anchor=message_origin_id(message_hash, 0)
    )


def result_status(result: ParseResult) -> set[ParcelStatus]:
    """Return the statuses a result reports."""
    kinds = {s.kind for s in result.shipments if s.kind} or {result.kind}
    return {status for kind in kinds if (status := KIND_TO_STATUS.get(kind))}


def results_agree(parser: ParseResult, ai: ParseResult) -> bool:
    """Return True when the AI read an e-mail the way the parser did.

    Used by the shadow check: the status, the tracking numbers and the first
    delivery estimate must match.
    """

    def numbers(result: ParseResult) -> set[str]:
        return {
            normalize_tracking_number(s.tracking_number)
            for s in result.shipments
            if s.tracking_number
        }

    def first_eta(result: ParseResult) -> tuple[object, object] | None:
        eta = next((s.eta for s in result.shipments if s.eta), None)
        return (eta.start, eta.end) if eta else None

    if result_status(parser) != result_status(ai) or numbers(parser) != numbers(ai):
        return False
    parser_eta = first_eta(parser)
    return parser_eta is None or parser_eta == first_eta(ai)
