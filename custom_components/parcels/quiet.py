"""Parcels without news for three weeks.

17TRACK stops following a number after 30 days without carrier events, and
a parcel that has been quiet for three weeks with no expected date still to
come has most likely arrived. Such numbers aren't added to 17TRACK, and the
ones Parcels added are archived there.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

from .models import Parcel, Source, local_date

QUIET_AFTER: Final = timedelta(days=21)


def last_news(parcel: Parcel) -> datetime:
    """Return when an e-mail or 17TRACK last told something about a parcel.

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
