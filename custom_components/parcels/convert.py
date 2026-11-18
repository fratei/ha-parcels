"""Conversions between parser or AI results, review suggestions and parcels."""

from __future__ import annotations

from datetime import datetime

from .const import CONFIDENCE_APPLY, KIND_TO_STATUS, MailKind, ParcelStatus
from .dedup import Contribution
from .models import MAX_ITEMS, Origin, ParcelEvent, Source, Suggestion
from .parsers.base import Eta, ParsedShipment, ParseResult
from .parsers.tracking import normalize_tracking_number

_NOT_PARCEL = (MailKind.NOT_PARCEL, MailKind.UNKNOWN)


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


def suggestion_result(suggestion: Suggestion, source: Source) -> ParseResult:
    """Turn a suggestion, possibly edited by the user, into a result."""
    kind = suggestion_kind(suggestion)
    eta: Eta | None = None
    if suggestion.eta_start:
        end = suggestion.eta_end or suggestion.eta_start
        eta = Eta(
            start=suggestion.eta_start,
            end=max(end, suggestion.eta_start),
            window_start=suggestion.window_start,
            window_end=suggestion.window_end,
        )
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
