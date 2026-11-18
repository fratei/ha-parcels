"""Persistence of the Parcels data in ``.storage/parcels``, and its retention."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import (
    DEFAULT_ARCHIVE_DAYS,
    DEFAULT_PURGE_DAYS,
    FILTERED_RETENTION,
    MESSAGE_HASH_RETENTION,
    REVIEW_RETENTION,
    STALE_ARCHIVE,
    STORAGE_KEY,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
    UNTRACKED_GRACE,
)
from .dedup import parcel_order_keys
from .models import Parcel, ParcelsData, local_date

# Changes come in bursts (a mailbox poll applies several e-mails), so saves
# are batched.
SAVE_DELAY = 5


def migrate(major: int, minor: int, data: dict[str, Any]) -> dict[str, Any]:
    """Bring data stored by an older release up to the current version.

    Data from a newer minor version is kept as it is: minor versions only add
    fields, which this release ignores.
    """
    if (major, minor) > (STORAGE_VERSION, STORAGE_MINOR_VERSION):
        raise NotImplementedError
    # 1.1 is the first version. A later version adds its step here, e.g.
    # ``if (major, minor) < (1, 2): ...``
    return dict(data)


class _VersionedStore(Store[dict[str, Any]]):
    """An HA Store that runs the Parcels migrations."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        return migrate(old_major_version, old_minor_version, old_data)


class ParcelsStore:
    """Loads and saves the Parcels data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create the store; the file is readable by Home Assistant only."""
        self._store = _VersionedStore(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            private=True,
            atomic_writes=True,
            minor_version=STORAGE_MINOR_VERSION,
        )
        self.data = ParcelsData()

    async def async_load(self) -> ParcelsData:
        """Load the stored data; an empty data set when there is none."""
        self.data = ParcelsData.from_dict(await self._store.async_load())
        return self.data

    @callback
    def async_schedule_save(self) -> None:
        """Save soon; pending saves are also written when HA stops."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    async def async_save(self) -> None:
        """Save now."""
        await self._store.async_save(self._data_to_save())

    async def async_remove(self) -> None:
        """Delete the stored data."""
        await self._store.async_remove()

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        return self.data.as_dict()


@dataclass(slots=True)
class RetentionResult:
    """What a retention run changed."""

    archived: list[str] = field(default_factory=list)
    purged: list[str] = field(default_factory=list)
    orders: int = 0
    messages: int = 0
    review: int = 0
    filtered: int = 0
    codes: int = 0

    @property
    def changed(self) -> bool:
        """Return True when anything was archived or removed."""
        return bool(
            self.archived
            or self.purged
            or self.orders
            or self.messages
            or self.review
            or self.filtered
            or self.codes
        )


def last_activity(parcel: Parcel) -> datetime:
    """Return the time of the latest news about a parcel."""
    return max(
        (
            parcel.created,
            *(origin.time for origin in parcel.origins.values()),
            *(event.time for event in parcel.events),
        )
    )


def _overdue_untracked(parcel: Parcel, activity: datetime, today: date) -> bool:
    """Return True for a parcel without tracking that's long past its dates."""
    state = parcel.state
    if state.tracking_number or state.eta is None or parcel.delivery_rejected:
        return False
    quiet_since = max(state.eta.end, local_date(activity))
    return today >= quiet_since + UNTRACKED_GRACE


def apply_retention(
    data: ParcelsData,
    now: datetime,
    *,
    archive_days: int = DEFAULT_ARCHIVE_DAYS,
    purge_days: int = DEFAULT_PURGE_DAYS,
) -> RetentionResult:
    """Archive and remove old records.

    * Finished parcels (delivered, returned, cancelled) are archived
      ``archive_days`` after their last status change. Archived parcels leave
      the lists but stay in past weeks of the calendar.
    * Open parcels without news for 30 days are archived too, unless they're
      still expected. Open parcels without a carrier tracking number are
      archived 7 days after their last expected day when there's been no news
      since: nothing will report their delivery. Parcels whose inferred
      delivery the user undid wait for the 30 days.
    * Archived parcels are deleted ``purge_days`` after their last news.
    * Delivery codes of archived parcels, and of parcels that were delivered,
      returned or cancelled (not just inferred delivered), are deleted.
    * Orders without parcels, e-mail hashes after 120 days, "Needs review"
      items after 30 days and "Filtered" items after 14 days are deleted.
    """
    result = RetentionResult()
    archive_after = timedelta(days=archive_days)
    purge_after = timedelta(days=purge_days)
    today = local_date(now)

    for parcel in list(data.parcels.values()):
        state = parcel.state
        activity = last_activity(parcel)
        if parcel.archived is None:
            if state.terminal:
                archive = now - (state.status_time or activity) >= archive_after
            else:
                expected = state.eta is not None and state.eta.end >= today
                archive = (
                    now - activity >= STALE_ARCHIVE and not expected
                ) or _overdue_untracked(parcel, activity, today)
            if archive:
                parcel.archived = now
                result.archived.append(parcel.id)
        if parcel.archived is not None and now - activity >= purge_after:
            del data.parcels[parcel.id]
            result.purged.append(parcel.id)
            continue
        if parcel.archived is not None or (state.terminal and not state.inferred):
            result.codes += parcel.drop_codes()

    used: set[str] = set()
    for parcel in data.parcels.values():
        used |= parcel_order_keys(parcel)
    for key in [key for key in data.orders if key not in used]:
        del data.orders[key]
        result.orders += 1

    for message_hash, record in list(data.messages.items()):
        if now - record.seen >= MESSAGE_HASH_RETENTION:
            del data.messages[message_hash]
            result.messages += 1
    for item_id, item in list(data.review.items()):
        if now - item.created >= REVIEW_RETENTION:
            del data.review[item_id]
            result.review += 1
    for item_id, filtered in list(data.filtered.items()):
        if now - filtered.created >= FILTERED_RETENTION:
            del data.filtered[item_id]
            result.filtered += 1
    return result
