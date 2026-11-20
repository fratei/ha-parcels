"""Parcels without news for three weeks.

17TRACK stops following a number after 30 days without carrier events, and
a parcel that has been quiet for three weeks with no expected date still to
come has most likely arrived. Such numbers aren't added to 17TRACK, and the
ones Parcels added are archived there. Tracked parcels on their way that went
quiet are shown as probably delivered, until the user keeps or undoes it.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Final

from homeassistant.util import dt as dt_util

from .const import ParcelStatus
from .models import Parcel, ParcelEvent, ParcelsData, Source, local_date

QUIET_AFTER: Final = timedelta(days=21)
# Statuses a parcel can be delivered from without anyone saying so.
ON_THE_WAY: Final = frozenset(
    {ParcelStatus.SHIPPED, ParcelStatus.IN_TRANSIT, ParcelStatus.OUT_FOR_DELIVERY}
)
MIDDAY: Final = time(12)


def last_news(parcel: Parcel) -> datetime:
    """Return when an e-mail, 17TRACK or Parcel last told about a parcel.

    The user's edits and inferred events don't count. A parcel added by hand
    counts from when it was added.
    """
    times = [
        origin.time
        for origin in parcel.origins.values()
        if origin.source is not Source.MANUAL
    ]
    times.extend(
        event.time
        for event in parcel.events
        if not event.inferred and event.source is not Source.MANUAL
    )
    return max(times, default=parcel.created)


def is_quiet(parcel: Parcel, now: datetime) -> bool:
    """Return True when a parcel had no news for three weeks and isn't due.

    Counted in days from its last news, or from its last expected day when
    that is later.
    """
    since = local_date(last_news(parcel))
    if (eta := parcel.state.eta) is not None:
        since = max(since, eta.end)
    return local_date(now) - since >= QUIET_AFTER


def _probable_delivery(parcel: Parcel) -> datetime:
    """Return when a quiet parcel was probably delivered.

    Midday on its last expected day, so that the calendar shows it there, or
    its last news when that is later.
    """
    news = last_news(parcel)
    if (eta := parcel.state.eta) is None:
        return news
    midday = datetime.combine(eta.end, MIDDAY, tzinfo=dt_util.get_default_time_zone())
    return max(news, dt_util.as_utc(midday))


def infer_quiet_deliveries(data: ParcelsData, now: datetime) -> set[str]:
    """Close tracked parcels on their way that had no news for three weeks.

    Carriers' e-mails, 17TRACK and Parcel miss some deliveries, so such a
    parcel was most likely delivered. The delivery is shown as inferred until
    the user keeps or undoes it, and news about the parcel takes it back.
    Parcels without a carrier tracking number are left to
    :func:`.dedup.infer_deliveries`. Returns the IDs of the changed parcels.
    """
    changed: set[str] = set()
    for parcel in data.parcels.values():
        state = parcel.state
        if (
            parcel.archived is not None
            or parcel.delivery_rejected
            or not state.tracking_number
            or state.status not in ON_THE_WAY
            or not is_quiet(parcel, now)
        ):
            continue
        # No mail kind: that's how it's told from the shop rule's, see
        # :func:`.models.inference_reason`.
        parcel.events.append(
            ParcelEvent(
                time=_probable_delivery(parcel),
                source=Source.PARSER,
                status=ParcelStatus.DELIVERED,
                inferred=True,
            )
        )
        parcel.touch(now)
        changed.add(parcel.id)
    return changed
