"""Builders for Parcels test data."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from custom_components.parcels.const import KIND_TO_STATUS, MailKind, ParcelStatus
from custom_components.parcels.dedup import Contribution
from custom_components.parcels.models import Origin, ParcelEvent, Source
from custom_components.parcels.parsers.base import Eta

# Monday 2 November 2026, 09:00 UTC.
T0 = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def at(*, days: float = 0, hours: float = 0) -> datetime:
    """Return a time relative to T0."""
    return T0 + timedelta(days=days, hours=hours)


def contribution(
    origin_id: str,
    *,
    kind: MailKind = MailKind.SHIPPED,
    time: datetime = T0,
    carrier: str | None = None,
    number: str | None = None,
    merchant: str | None = None,
    orders: Iterable[str] = (),
    shipment_id: str | None = None,
    eta: Eta | None = None,
    owner: str | None = "person.one",
    source: Source = Source.PARSER,
    status: ParcelStatus | None = None,
    private: bool = False,
) -> Contribution:
    """Build what one e-mail says about one parcel."""
    message = origin_id.removeprefix("msg:").split("#")[0]
    origin = Origin(
        id=origin_id,
        source=source,
        time=time,
        carrier=carrier,
        tracking_number=number,
        amazon_shipment_id=shipment_id,
        merchant=merchant,
        order_numbers=tuple(orders),
        message=message,
        owners=(owner,) if owner else (),
    )
    event = ParcelEvent(
        time=time,
        source=source,
        status=status or KIND_TO_STATUS.get(kind),
        kind=kind,
        eta=eta,
    )
    return Contribution(origin=origin, events=[event], private=private)
