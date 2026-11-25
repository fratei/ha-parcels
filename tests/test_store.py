"""Tests for storing the Parcels data and the retention rules."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import UnsupportedStorageVersionError
import pytest

from custom_components.parcels.const import MailKind, ParcelStatus
from custom_components.parcels.dedup import apply_contribution, archive_parcel
from custom_components.parcels.models import (
    FilteredItem,
    MessageRecord,
    MessageState,
    ParcelEvent,
    ParcelsData,
    ReviewItem,
    Source,
)
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.store import (
    FORGOTTEN_KEY,
    ParcelsStore,
    apply_retention,
    forgotten_before,
)

from .factories import T0, at, contribution

DPD = "05212345678901"


def _stored(version: int, minor: int, data: dict[str, Any]) -> dict[str, Any]:
    return {"version": version, "minor_version": minor, "key": "parcels", "data": data}


async def test_save_and_load(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """The data is stored versioned and comes back the same."""
    store = ParcelsStore(hass)
    data = await store.async_load()
    assert data == ParcelsData()

    apply_contribution(data, contribution("msg:a#0", carrier="dpd", number=DPD), T0)
    await store.async_save()
    assert hass_storage["parcels"]["version"] == 1
    assert hass_storage["parcels"]["minor_version"] == 1

    loaded = await ParcelsStore(hass).async_load()
    assert loaded.as_dict() == data.as_dict()


async def test_newer_minor_version_is_read(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Data from a newer release with extra fields can still be read."""
    data = ParcelsData()
    apply_contribution(data, contribution("msg:a#0", carrier="dpd", number=DPD), T0)
    stored = data.as_dict()
    stored["new_section"] = {"x": 1}
    hass_storage["parcels"] = _stored(1, 5, stored)

    loaded = await ParcelsStore(hass).async_load()
    assert loaded.as_dict() == data.as_dict()


async def test_newer_major_version_is_refused(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Data in an incompatible format isn't overwritten."""
    hass_storage["parcels"] = _stored(2, 1, {"parcels": []})
    with pytest.raises(UnsupportedStorageVersionError):
        await ParcelsStore(hass).async_load()
    assert hass_storage["parcels"]["version"] == 2


def _parcel(data: ParcelsData, name: str, kind: MailKind, days: float, **kwargs) -> str:
    applied = apply_contribution(
        data,
        contribution(
            f"msg:{name}#0",
            kind=kind,
            time=at(days=days),
            carrier="dpd",
            number=f"0521234567{len(data.parcels):04d}",
            **kwargs,
        ),
        at(days=days),
    )
    assert applied.parcel_id
    return applied.parcel_id


def test_parcel_retention() -> None:
    """Finished parcels are archived after 14 days and removed after 90."""
    data = ParcelsData()
    delivered_old = _parcel(data, "d1", MailKind.DELIVERED, -14)
    delivered_new = _parcel(data, "d2", MailKind.DELIVERED, -13)
    stale = _parcel(data, "s1", MailKind.SHIPPED, -30)
    expected = _parcel(
        data, "s2", MailKind.SHIPPED, -40, eta=Eta(date(2026, 11, 2), date(2026, 11, 2))
    )
    recent = _parcel(data, "s3", MailKind.SHIPPED, -29)
    gone = _parcel(data, "x1", MailKind.DELIVERED, -90)
    kept_archived = _parcel(data, "x2", MailKind.DELIVERED, -89)
    for parcel_id in (gone, kept_archived):
        archive_parcel(data, parcel_id, at(days=-60))

    result = apply_retention(data, T0)

    assert set(result.archived) == {delivered_old, stale}
    assert result.purged == [gone]
    assert data.parcels[delivered_old].archived == T0
    assert data.parcels[stale].archived == T0
    for parcel_id in (delivered_new, expected, recent):
        assert data.parcels[parcel_id].archived is None
    assert data.parcels[kept_archived].archived == at(days=-60)
    assert gone not in data.parcels

    assert not apply_retention(data, T0).changed


def _untracked(
    data: ParcelsData,
    name: str,
    eta_day: int,
    *,
    days: float = -20,
    mail: str | None = None,
    **kwargs,
) -> str:
    """Add a shop's parcel without a tracking number, due on ``eta_day`` Oct."""
    due = date(2026, 10, eta_day)
    applied = apply_contribution(
        data,
        contribution(
            f"msg:{mail or name}#0",
            time=at(days=days),
            merchant=f"Shop {name}",
            orders=[f"#{name}"],
            eta=Eta(due, due),
            **kwargs,
        ),
        at(days=days),
    )
    assert applied.parcel_id
    return applied.parcel_id


def test_untracked_parcels_archived_a_week_after_their_dates() -> None:
    """Nothing reports the delivery of a parcel without a tracking number."""
    data = ParcelsData()
    overdue = _untracked(data, "u1", 26)
    six_days = _untracked(data, "u2", 27)
    rejected = _untracked(data, "u3", 26)
    data.parcels[rejected].delivery_rejected = True
    late_news = _untracked(data, "u4", 20)
    news = _untracked(data, "u4", 20, days=-6, mail="u5", kind=MailKind.IN_TRANSIT)
    assert news == late_news
    assert len(data.parcels) == 4
    due = date(2026, 10, 26)
    tracked = _parcel(data, "t1", MailKind.SHIPPED, -20, eta=Eta(due, due))

    assert apply_retention(data, T0).archived == [overdue]
    assert apply_retention(data, at(days=1)).archived == [six_days, late_news]
    for parcel_id in (rejected, tracked):
        assert data.parcels[parcel_id].archived is None


def test_retention_options() -> None:
    """The archive and purge periods are options."""
    data = ParcelsData()
    parcel_id = _parcel(data, "d1", MailKind.DELIVERED, -3)
    assert apply_retention(data, T0, archive_days=3, purge_days=5).archived == [
        parcel_id
    ]
    assert apply_retention(data, at(days=2), archive_days=3, purge_days=5).purged == [
        parcel_id
    ]


def test_record_retention() -> None:
    """Orders, e-mail hashes and list items expire."""
    data = ParcelsData()
    parcel_id = _parcel(
        data, "o1", MailKind.SHIPPED, -100, merchant="Example Shop", orders=["#1"]
    )
    _parcel(data, "o2", MailKind.SHIPPED, 0, merchant="Example Shop", orders=["#2"])
    data.parcels[parcel_id].archived = at(days=-50)
    for name, seen, reviewed, filtered in (
        ("old", -120, -30, -14),
        ("new", -119, -29, -13),
    ):
        data.messages[name] = MessageRecord(
            name, at(days=seen), MessageState.APPLIED, {}, at(days=seen), "example.com"
        )
        data.review[name] = ReviewItem(
            name,
            at(days=reviewed),
            name,
            at(days=reviewed),
            "shop@example.com",
            "example.com",
            "Your order",
            "entry",
            None,
            "low_confidence",
            False,
            Source.PARSER,
        )
        data.filtered[name] = FilteredItem(
            name,
            at(days=filtered),
            name,
            at(days=filtered),
            "news@example.com",
            "example.com",
            "Hi",
            None,
        )

    result = apply_retention(data, T0)

    assert result.purged == [parcel_id]
    assert result.orders == 1
    assert list(data.orders) == ["ord:exampleshop:2"]
    assert (result.messages, result.review, result.filtered) == (1, 1, 1)
    assert list(data.messages) == list(data.review) == list(data.filtered) == ["new"]
    assert data.parcels[next(iter(data.parcels))].state.status is ParcelStatus.SHIPPED


def _record(data: ParcelsData, name: str, seen: float, received: float | None) -> None:
    data.messages[name] = MessageRecord(
        name,
        at(days=seen),
        MessageState.APPLIED,
        {"entry": name},
        None if received is None else at(days=received),
        "example.com",
    )


def test_forgotten_emails_leave_a_mark() -> None:
    """The newest forgotten e-mail's time marks what's been read before.

    A mailbox can list an e-mail again after Parcels forgot it; the engine
    skips e-mails received at or before the mark.
    """
    data = ParcelsData()
    assert forgotten_before(data) is None
    _record(data, "old", -130, -135)
    _record(data, "older", -121, -125)
    _record(data, "kept", -119, -119)

    apply_retention(data, T0)

    assert list(data.messages) == ["kept"]
    assert forgotten_before(data) == at(days=-125)

    # The mark never moves back.
    _record(data, "late", -200, -210)
    apply_retention(data, T0)
    assert forgotten_before(data) == at(days=-125)

    # Without a received time, or with one later than when it was read, the
    # e-mail counts from when it was read.
    _record(data, "unknown", -120.5, None)
    apply_retention(data, T0)
    assert forgotten_before(data) == at(days=-120.5)
    _record(data, "future", -120.25, 5)
    apply_retention(data, T0)
    assert forgotten_before(data) == at(days=-120.25)
    assert list(data.messages) == ["kept"]


def test_a_damaged_mark_is_counted_and_replaced() -> None:
    """A mark that can't be read skips nothing; the next one replaces it."""
    data = ParcelsData.from_dict({"engine": {FORGOTTEN_KEY: "2026-13-45T00:00:00"}})
    assert data.damaged == {"engine": 1}
    assert forgotten_before(data) is None

    _record(data, "old", -130, -135)
    apply_retention(data, T0)

    assert forgotten_before(data) == at(days=-135)


def test_delivery_codes_go_once_the_parcel_is_done() -> None:
    """Delivery codes of delivered or archived parcels are deleted."""
    data = ParcelsData()
    delivered = _parcel(data, "d1", MailKind.DELIVERED, -1)
    inferred = _parcel(data, "i1", MailKind.SHIPPED, -2)
    data.parcels[inferred].events.append(
        ParcelEvent(
            time=at(days=-1),
            source=Source.PARSER,
            status=ParcelStatus.DELIVERED,
            inferred=True,
        )
    )
    out = _parcel(data, "o1", MailKind.OUT_FOR_DELIVERY, 0)
    archived = _parcel(data, "a1", MailKind.SHIPPED, -2)
    for parcel in data.parcels.values():
        for origin in parcel.origins.values():
            origin.pickup_code = "4821"
        parcel.touch(parcel.updated)
    archive_parcel(data, archived, at(days=-1))
    assert data.parcels[archived].state.pickup_code is None

    result = apply_retention(data, T0)

    assert result.codes == 1
    assert result.changed
    assert data.parcels[delivered].state.pickup_code is None
    assert all(
        origin.pickup_code is None
        for parcel_id in (delivered, archived)
        for origin in data.parcels[parcel_id].origins.values()
    )
    for parcel_id in (inferred, out):
        assert data.parcels[parcel_id].state.pickup_code == "4821"
    assert data.parcels[inferred].state.inferred
    assert not apply_retention(data, T0).changed
