"""Tests for the one-time re-read that names the shop of Paack parcels.

Releases before 0.1.7 couldn't read the shop in Paack's e-mails, so their
parcels show only "Paack". Once after the update, the Paack e-mails of the
last 14 days that name no shop are read again by the parsers, never the
local AI, and the shop they name is filled in. Nothing else changes.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.dedup import (
    REASON_SAME_MERCHANT_DAY,
    apply_contribution,
)
from custom_components.parcels.engine import PAACK_SHOP_CHECK_KEY, ParcelsEngine
from custom_components.parcels.mail.errors import MailServerError
from custom_components.parcels.models import (
    MessageRecord,
    MessageState,
    ParcelsData,
    Source,
    dt_to_str,
)
from custom_components.parcels.parsers import parse_message
from custom_components.parcels.parsers.auth import verify_sender
from custom_components.parcels.parsers.base import Eta, MailMessage, ParseResult
from custom_components.parcels.parsers.normalize import message_from_bytes

from .common import (
    ADDRESS,
    EMAIL_FIXTURES,
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    patch_mail_clients,
)
from .factories import contribution
from .test_returns import async_sync, parsed_as, record_of

NOW = "2026-11-26 09:00:00+00:00"
LISBON = ZoneInfo("Europe/Lisbon")
# Monday 23 November: Casa Exemplo's parcel is on its way.
ON_THE_WAY = "carriers/paack_on_the_way_pt.eml"
ON_THE_WAY_NUMBER = "Wx4Hn8Tz3_1"
SHOP = "Casa Exemplo"
# Wednesday 25 November: Amazon's parcel is out for delivery.
OUT_FOR_DELIVERY = "carriers/paack_out_for_delivery_pt.eml"
OUT_FOR_DELIVERY_NUMBER = "Rb5Lq2Vm7_1"
# Tuesday 17 November: Zara's parcel was delivered.
DELIVERED = "carriers/paack_delivered_pt.eml"
DELIVERED_NUMBER = "PK7311805018"
# Zara's parcel arrives today.
TODAY_ES = "carriers/paack_today_es.eml"
TODAY_ES_NUMBER = "PK7311804926"
CTT = "carriers/ctt_in_transit_pt.eml"
CTT_NUMBER = "RR482915732PT"
OTHER_NUMBER = "Qm6Tp3Kd8_1"
NO_COUNTS = dict.fromkeys(("read", "filled", "kept", "gone", "failed", "skipped"), 0)


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on Thursday 26 November 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


def mail(
    path: str,
    provider_id: str,
    *,
    number: str | None = None,
    sent: datetime | None = None,
) -> MailMessage:
    """Return a fixture as an e-mail of its own.

    ``number`` replaces the parcel number of the "on its way" e-mail, and
    ``sent`` the time the e-mail was sent and received.
    """
    raw = (EMAIL_FIXTURES / path).read_bytes()
    if number is not None:
        assert ON_THE_WAY_NUMBER.encode() in raw
        raw = raw.replace(ON_THE_WAY_NUMBER.encode(), number.encode())
    message = message_from_bytes(
        raw, mailbox=ADDRESS, provider_id=provider_id, provider="google"
    )
    message = replace(message, message_id=f"<{provider_id}@mail.example.com>")
    if sent is not None:
        message = replace(message, date=sent, received=sent)
    return message


def as_stored(message: MailMessage, merchant: str | None = None) -> ParseResult:
    """Return what a release before 0.1.7 read: no shop, or ``merchant``."""
    result = parse_message(message, verify_sender(message), LISBON)
    assert result.merchant
    return replace(result, merchant=merchant)


async def async_check(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> dict[str, Any]:
    """Run the check as after an update, on the next sync; return its record."""
    freezer.tick(timedelta(minutes=1))
    engine.data.engine[PAACK_SHOP_CHECK_KEY] = {"before": dt_to_str(dt_util.utcnow())}
    freezer.tick(timedelta(minutes=1))
    await async_sync(hass, engine)
    return engine.data.engine[PAACK_SHOP_CHECK_KEY]


def shops(engine: ParcelsEngine) -> dict[str | None, str | None]:
    """Return the shop of each parcel, by its tracking number."""
    return {
        parcel.state.tracking_number: parcel.state.merchant
        for parcel in engine.data.parcels.values()
    }


@pytest.mark.parametrize("stored", ["nothing", "carrier", "confirmed_ai"])
async def test_check_names_the_shop_of_a_paack_parcel(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, stored: str
) -> None:
    """A Paack parcel stored without its shop gets the shop its e-mail names.

    Whether the earlier release read no shop, took Paack for it, or the
    user confirmed what the local AI read. Only the shop changes.
    """
    message = mail(ON_THE_WAY, "paack-1")
    client = FakeMailClient()
    client.add(message)
    add_hub(hass)
    add_mailbox(hass)
    merchant = None if stored == "nothing" else "Paack"

    with patch_mail_clients(client):
        with parsed_as({"paack-1": as_stored(message, merchant)}):
            engine = await async_setup_parcels(hass)
        (parcel,) = engine.data.parcels.values()
        (origin,) = parcel.origins.values()
        if stored == "confirmed_ai":
            origin.source = Source.AI
            origin.confirmed = True
            parcel.touch(dt_util.utcnow())
        assert parcel.state.merchant is None
        events = deepcopy(parcel.events)
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "filled": 1}
    assert set(check) == {"before", "started", "done", "counts"}
    assert engine.diagnostics()["paack_shop_check"] == check
    assert client.fetches == ["paack-1"]
    assert engine.data.parcels == {parcel.id: parcel}
    assert parcel.state.merchant == SHOP
    assert parcel.state.tracking_number == ON_THE_WAY_NUMBER
    assert parcel.events == events
    assert origin.source is (Source.AI if stored == "confirmed_ai" else Source.PARSER)
    assert origin.confirmed is (stored == "confirmed_ai")


async def test_check_pairs_the_parcel_with_its_shops_order(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Once Paack's parcel names the shop, it joins that shop's order."""
    message = mail(DELIVERED, "paack-1")
    client = FakeMailClient()
    client.add(message)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"paack-1": as_stored(message)}):
            engine = await async_setup_parcels(hass)
        (box,) = engine.data.parcels
        # Made up: Zara's e-mail that the order was sent, due 16 to 18 November.
        order = apply_contribution(
            engine.data,
            contribution(
                "msg:zara-1#0",
                time=datetime(2026, 11, 14, 10, tzinfo=UTC),
                merchant="Zara",
                orders=["ZX0042"],
                eta=Eta(start=date(2026, 11, 16), end=date(2026, 11, 18)),
                label="zara.com",
            ),
            dt_util.utcnow(),
        ).parcel_id
        engine.async_changed()
        assert set(engine.data.parcels) == {box, order}
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "filled": 1}
    assert set(engine.data.parcels) == {box}
    parcel = engine.data.parcels[box]
    assert parcel.state.merchant == "Zara"
    assert parcel.state.order_numbers == ("ZX0042",)
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_DAY


async def test_check_reads_only_recent_paack_emails_without_a_shop(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Only Paack's e-mails of the last 14 days that name no shop are read.

    Not older ones, nor those that name it, nor another carrier's, nor one
    the user removed from Parcels, nor one read since the update.
    """
    now = dt_util.utcnow()
    recent = mail(ON_THE_WAY, "paack-1")
    old = mail(TODAY_ES, "paack-old", sent=now - timedelta(days=20))
    removed = mail(OUT_FOR_DELIVERY, "paack-removed")
    named = mail(DELIVERED, "paack-named")
    newer = mail(ON_THE_WAY, "paack-new", number=OTHER_NUMBER)
    ctt = mail(CTT, "ctt")
    client = FakeMailClient()
    for message in (recent, old, removed, named, ctt):
        client.add(message)
    add_hub(hass)
    add_mailbox(hass)
    stored = {
        "paack-1": as_stored(recent),
        "paack-old": as_stored(old),
        "paack-removed": as_stored(removed),
        "ctt": as_stored(ctt),
    }

    with patch_mail_clients(client):
        with parsed_as(stored):
            engine = await async_setup_parcels(hass)
        (parcel,) = [
            parcel
            for parcel in engine.data.parcels.values()
            if parcel.state.tracking_number == OUT_FOR_DELIVERY_NUMBER
        ]
        engine.remove_email(parcel.id, next(iter(parcel.origins)))
        client.fetches.clear()
        client.add(newer)
        with parsed_as({"paack-new": as_stored(newer)}):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "filled": 1}
    assert client.fetches == ["paack-new", "paack-1"]
    assert record_of(engine, "paack-removed").state is MessageState.FILTERED
    found = shops(engine)
    assert found[ON_THE_WAY_NUMBER] == SHOP
    assert found[OTHER_NUMBER] is None
    assert found[TODAY_ES_NUMBER] is None
    assert found[DELIVERED_NUMBER] == "Zara"
    assert found[CTT_NUMBER] is None
    assert OUT_FOR_DELIVERY_NUMBER not in found


async def test_check_reads_at_most_its_limit(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The newest e-mails are read first, up to the limit; the rest are counted."""
    first = mail(ON_THE_WAY, "paack-1")
    second = mail(OUT_FOR_DELIVERY, "paack-2")
    client = FakeMailClient()
    client.add(first)
    client.add(second)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"paack-1": as_stored(first), "paack-2": as_stored(second)}):
            engine = await async_setup_parcels(hass)
        client.fetches.clear()
        with patch("custom_components.parcels.engine.PAACK_SHOP_CHECK_MAX", 1):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "filled": 1, "skipped": 1}
    assert client.fetches == ["paack-2"]
    assert shops(engine) == {ON_THE_WAY_NUMBER: None, OUT_FOR_DELIVERY_NUMBER: "Amazon"}


async def test_check_counts_emails_it_cant_download(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail deleted since counts as gone, one that won't download as failed."""
    first = mail(ON_THE_WAY, "paack-1")
    second = mail(OUT_FOR_DELIVERY, "paack-2")
    client = FakeMailClient()
    client.add(first)
    client.add(second)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"paack-1": as_stored(first), "paack-2": as_stored(second)}):
            engine = await async_setup_parcels(hass)
        client.delete("paack-1")
        client.fetch_errors["paack-2"] = MailServerError("down")
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "gone": 1, "failed": 1}
    assert shops(engine) == {ON_THE_WAY_NUMBER: None, OUT_FOR_DELIVERY_NUMBER: None}


async def test_check_leaves_an_email_removed_meanwhile(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail the user removes from Parcels while it's read stays removed."""
    message = mail(ON_THE_WAY, "paack-1")
    client = FakeMailClient()
    client.add(message)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"paack-1": as_stored(message)}):
            engine = await async_setup_parcels(hass)
        (parcel,) = engine.data.parcels.values()
        (origin_id,) = parcel.origins
        record = record_of(engine, "paack-1")

        def remove(message: MailMessage) -> None:
            if record.state is MessageState.APPLIED:
                engine.remove_email(parcel.id, origin_id)

        with parsed_as({}, during=remove):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert record.state is MessageState.FILTERED
    assert not engine.data.parcels


async def test_check_leaves_the_shop_the_user_set(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The shop the user gave a parcel still shows after the check."""
    message = mail(ON_THE_WAY, "paack-1")
    client = FakeMailClient()
    client.add(message)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"paack-1": as_stored(message)}):
            engine = await async_setup_parcels(hass)
        (parcel,) = engine.data.parcels.values()
        engine.update(parcel.id, {"merchant": "Mercearia Exemplo"})
        check = await async_check(hass, engine, freezer)

    assert check["counts"]["read"] == 1
    assert shops(engine) == {ON_THE_WAY_NUMBER: "Mercearia Exemplo"}


@pytest.mark.parametrize("stored", ["messages", "nothing", "checked"])
async def test_check_is_due_once_after_an_update(
    hass: HomeAssistant, hass_storage: dict[str, Any], stored: str
) -> None:
    """The check is due when an earlier release read e-mails, and only once."""
    now = dt_util.utcnow()
    data = ParcelsData()
    if stored != "nothing":
        data.messages["hash"] = MessageRecord(
            hash="hash",
            seen=now - timedelta(days=2),
            state=MessageState.APPLIED,
            sender_domain="paack.co",
        )
    checked = {"done": dt_to_str(now - timedelta(days=1)), "counts": NO_COUNTS}
    if stored == "checked":
        data.engine[PAACK_SHOP_CHECK_KEY] = deepcopy(checked)
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)

    engine = await async_setup_parcels(hass)

    assert (
        engine.data.engine[PAACK_SHOP_CHECK_KEY]
        == {
            "messages": {"before": dt_to_str(now)},
            "nothing": {"done": dt_to_str(now)},
            "checked": checked,
        }[stored]
    )


async def test_check_cut_short_by_a_restart_doesnt_run_again(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A check a restart cut short isn't started again: it runs only once."""
    message = mail(ON_THE_WAY, "paack-1")
    client = FakeMailClient()
    client.add(message)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"paack-1": as_stored(message)}):
            engine = await async_setup_parcels(hass)
        client.fetches.clear()
        freezer.tick(timedelta(minutes=1))
        now = dt_to_str(dt_util.utcnow())
        started = {"before": now, "started": now}
        engine.data.engine[PAACK_SHOP_CHECK_KEY] = deepcopy(started)
        freezer.tick(timedelta(minutes=1))
        await async_sync(hass, engine)

    assert engine.data.engine[PAACK_SHOP_CHECK_KEY] == started
    assert not client.fetches
    assert shops(engine) == {ON_THE_WAY_NUMBER: None}
