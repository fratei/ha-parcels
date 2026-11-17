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
    ParcelsData,
    ReviewItem,
    Source,
)
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.store import ParcelsStore, apply_retention

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
