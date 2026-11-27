"""Shipments of several packages: one delivered, the others probably too.

A shop may send one order as several packages, each with its own tracking
number, and carriers often report only some of them: a carrier's e-mail, 17TRACK
or Parcel may follow one number while the others get no news of their own.
Once a package of a shipment is reported delivered, its other packages that
were due by that day, with no news since, most likely came with it. They are
shown as probably delivered, until the user keeps or undoes it, and news about
a package takes it back.

The packages of a shipment are those :func:`.views.shipment_groups` finds, the
ones the page and the persistent notification already show as one box: one
carrier, numbers in a short run, and first e-mails within two days of each
other about the same order, from the same shop or merchant. An order alone
isn't enough: its packages may leave on different days.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

from .const import MailKind, ParcelStatus
from .dedup import reported_delivery_event
from .models import (
    INFERRED_SHIPMENT,
    Parcel,
    ParcelEvent,
    ParcelsData,
    Source,
    local_date,
    one_day,
)
from .quiet import ON_THE_WAY, last_news
from .views import shipment_groups

# Who may see a parcel: everyone (None), or the owners of a private one, which
# are admins when it has none.
type _Audience = frozenset[str] | None


def _audience(parcel: Parcel) -> _Audience:
    return frozenset(parcel.state.owners) if parcel.private else None


def _visible_to_all(parcel: Parcel, audience: _Audience) -> bool:
    """Return True when everyone who may see a parcel of this audience sees this one."""
    if not parcel.private:
        return True
    if audience is None:
        return False
    owners = parcel.state.owners
    if not audience:
        return not owners
    return audience <= set(owners)


def _waiting(parcel: Parcel) -> bool:
    """Return True when a package on its way, due by now, could be closed."""
    state = parcel.state
    return (
        parcel.archived is None
        and not parcel.delivery_rejected
        and bool(state.tracking_number)
        and state.status in ON_THE_WAY
        and state.eta is not None
        and not any(event.inferred for event in parcel.events)
    )


def _closing(parcel: Parcel, deliveries: Iterable[ParcelEvent]) -> ParcelEvent | None:
    """Return the first delivery of another package that closes this one.

    One on or after its first expected day, and not before its own last news.
    """
    eta = parcel.state.eta
    if eta is None:
        return None
    news = last_news(parcel)
    return min(
        (
            event
            for event in deliveries
            if local_date(event.time) >= eta.start and event.time >= news
        ),
        key=lambda event: event.time,
        default=None,
    )


@one_day()
def infer_shipment_deliveries(data: ParcelsData, now: datetime) -> set[str]:
    """Close the packages of a shipment once another of its packages was delivered.

    Only a delivery that an e-mail, 17TRACK or Parcel reported counts: one the
    user marked or kept doesn't say which package came, and an inferred one
    proves nothing. A package that had news of its own after that delivery
    stays, and so does one that is expected later or without an expected day.
    Private packages count only for packages whose people may all see them, so
    that nobody learns about a parcel they may not see. Returns the IDs of the
    changed parcels.
    """
    parcels = data.parcels.values()
    waiting: dict[_Audience, list[Parcel]] = defaultdict(list)
    for parcel in parcels:
        if _waiting(parcel):
            waiting[_audience(parcel)].append(parcel)
    if not waiting:
        return set()
    delivered = {
        parcel.id: event
        for parcel in parcels
        if (event := reported_delivery_event(parcel)) is not None
    }
    if not delivered:
        return set()
    changed: set[str] = set()
    for audience, packages in waiting.items():
        groups = shipment_groups(
            parcel for parcel in parcels if _visible_to_all(parcel, audience)
        )
        deliveries: dict[str, list[ParcelEvent]] = defaultdict(list)
        for parcel_id, event in delivered.items():
            if (group := groups.get(parcel_id)) is not None:
                deliveries[group].append(event)
        for parcel in packages:
            group = groups.get(parcel.id)
            if group is None or group not in deliveries:
                continue
            if (event := _closing(parcel, deliveries[group])) is None:
                continue
            # A delivery known only by its day gives the others that day too.
            parcel.events.append(
                ParcelEvent(
                    time=event.time,
                    source=Source.PARSER,
                    status=ParcelStatus.DELIVERED,
                    kind=MailKind.DELIVERED,
                    label=INFERRED_SHIPMENT,
                    inferred=True,
                    undated=event.undated,
                    timeless=event.timeless,
                    by=event.by if event.undated else None,
                )
            )
            parcel.touch(now)
            changed.add(parcel.id)
    return changed
