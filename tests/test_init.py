"""Tests for loading, unloading and removing the Parcels entries."""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
import pytest

from custom_components.parcels.const import (
    DOMAIN,
    PERSISTENT_NOTIFICATION_ID,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.dedup import (
    ORDER_FOLD_KEY,
    REPAIR_KEY,
    REPAIR_VERSION,
    apply_contribution,
    archive_parcel,
)
from custom_components.parcels.engine import ParcelsEngine, get_engine
from custom_components.parcels.models import ParcelsData, Source
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.store import ParcelsStore

from .common import (
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    async_wait_for_mail,
    patch_mail_clients,
)
from .factories import at, contribution

NOW = "2026-11-17 10:00:00+00:00"


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on 17 November 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


async def test_setup_reads_mail(hass: HomeAssistant) -> None:
    """A mailbox reads its mail once the hub is loaded."""
    client = FakeMailClient()
    client.add("carriers/ctt_in_transit_pt.eml")
    client.add("common/newsletter.eml")
    # The mailbox loads first and waits for the hub.
    mailbox = add_mailbox(hass)
    hub = add_hub(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)

    assert hub.state is ConfigEntryState.LOADED
    assert mailbox.state is ConfigEntryState.LOADED
    assert mailbox.runtime_data.client is client
    assert engine.mailboxes == {mailbox.entry_id: mailbox.runtime_data}
    numbers = [p.state.tracking_number for p in engine.data.parcels.values()]
    assert numbers == ["RR482915732PT"]
    # The newsletter isn't downloaded.
    assert client.fetches == ["ctt_in_transit_pt.eml"]
    assert engine.is_synced(mailbox.entry_id)
    assert engine.data.cursors[mailbox.entry_id] == {"round": 1}
    assert hass.states.get("sensor.parcels_in_transit").state == "1"


async def test_mailbox_waits_for_hub(hass: HomeAssistant) -> None:
    """Without a hub, a mailbox retries; adding the hub loads it."""
    client = FakeMailClient()
    mailbox = add_mailbox(hass)

    with patch_mail_clients(client):
        assert await hass.config_entries.async_setup(mailbox.entry_id) is False
        assert mailbox.state is ConfigEntryState.SETUP_RETRY
        assert mailbox.error_reason_translation_key == "hub_not_loaded"

        hub = add_hub(hass)
        assert await hass.config_entries.async_setup(hub.entry_id)
        await async_wait_for_mail(hass)

    assert hub.state is ConfigEntryState.LOADED
    assert mailbox.state is ConfigEntryState.LOADED


async def test_mailbox_gives_up_waiting(hass: HomeAssistant) -> None:
    """A mailbox stops waiting for a slow hub, and loads once the hub does."""
    assert await async_setup_component(hass, DOMAIN, {})
    hub = add_hub(hass)
    mailbox = add_mailbox(hass)
    entered = asyncio.Event()
    release = asyncio.Event()
    start = ParcelsEngine.async_start

    async def slow_start(engine: ParcelsEngine) -> None:
        entered.set()
        await release.wait()
        await start(engine)

    with (
        patch_mail_clients(FakeMailClient()),
        patch.object(ParcelsEngine, "async_start", slow_start),
    ):
        hub_setup = hass.async_create_task(
            hass.config_entries.async_setup(hub.entry_id)
        )
        await entered.wait()
        with patch("custom_components.parcels.HUB_WAIT", 0):
            assert not await hass.config_entries.async_setup(mailbox.entry_id)
        assert mailbox.state is ConfigEntryState.SETUP_RETRY
        assert hub.state is ConfigEntryState.SETUP_IN_PROGRESS

        release.set()
        assert await hub_setup
        # The hub retries the waiting mailbox at once.
        await async_wait_for_mail(hass)

    assert hub.state is ConfigEntryState.LOADED
    assert mailbox.state is ConfigEntryState.LOADED


async def test_hub_reload_reloads_mailboxes(hass: HomeAssistant) -> None:
    """After a hub reload, the mailbox feeds the new engine."""
    client = FakeMailClient()
    hub = add_hub(hass)
    mailbox = add_mailbox(hass)

    with patch_mail_clients(client):
        old = await async_setup_parcels(hass)
        assert await hass.config_entries.async_reload(hub.entry_id)
        await async_wait_for_mail(hass)
        new = get_engine(hass)

        assert new is not None
        assert new is not old
        assert not old.started
        assert mailbox.state is ConfigEntryState.LOADED
        assert mailbox.runtime_data.coordinator.engine is new
        assert new.mailboxes == {mailbox.entry_id: mailbox.runtime_data}

        client.add("carriers/ctt_in_transit_pt.eml")
        await new.async_refresh()
        await hass.async_block_till_done()

    assert len(new.data.parcels) == 1


async def test_hub_options_apply_without_reload(hass: HomeAssistant) -> None:
    """Changing the hub options keeps the same engine."""
    hub = add_hub(hass)
    engine = await async_setup_parcels(hass)

    hass.config_entries.async_update_entry(
        hub, options={**hub.options, "collapse_threshold": 5}
    )
    await hass.async_block_till_done()

    assert get_engine(hass) is engine
    assert engine.started
    assert engine.options["collapse_threshold"] == 5


async def test_unload_stops_and_saves(hass: HomeAssistant) -> None:
    """Unloading the hub stops the engine and saves the data."""
    client = FakeMailClient()
    client.add("carriers/ctt_in_transit_pt.eml")
    hub = add_hub(hass)
    mailbox = add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        # The mailbox reloads and gives up waiting at once.
        with patch("custom_components.parcels.HUB_WAIT", 0):
            assert await hass.config_entries.async_unload(hub.entry_id)
            await hass.async_block_till_done()

    assert hub.state is ConfigEntryState.NOT_LOADED
    assert not engine.started
    assert get_engine(hass) is None
    # The mailbox reloaded and now waits for the hub.
    assert mailbox.state is ConfigEntryState.SETUP_RETRY
    stored = await ParcelsStore(hass).async_load()
    assert [p.state.tracking_number for p in stored.parcels.values()] == [
        "RR482915732PT"
    ]


async def test_remove_mailbox_forgets_its_state(hass: HomeAssistant) -> None:
    """Removing a mailbox drops its cursor and e-mail references."""
    client = FakeMailClient()
    client.add("carriers/ctt_in_transit_pt.eml")
    add_hub(hass)
    mailbox = add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        assert mailbox.entry_id in engine.data.cursors

        assert await hass.config_entries.async_remove(mailbox.entry_id)
        await hass.async_block_till_done()

    assert mailbox.entry_id not in engine.data.cursors
    assert not engine.is_synced(mailbox.entry_id)
    assert engine.mailboxes == {}
    assert all(not record.refs for record in engine.data.messages.values())
    # The parcel stays.
    assert len(engine.data.parcels) == 1


async def test_remove_hub_deletes_data(hass: HomeAssistant) -> None:
    """Removing the hub deletes the stored data, issues and notification."""
    client = FakeMailClient()
    client.add("carriers/ctt_in_transit_pt.eml")
    hub = add_hub(hass)
    mailbox = add_mailbox(hass)

    with patch_mail_clients(client):
        await async_setup_parcels(hass)
        ir.async_create_issue(
            hass,
            DOMAIN,
            "ai_unavailable",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="ai_unavailable",
        )
        persistent_notification.async_create(
            hass, "Deliveries today", notification_id=PERSISTENT_NOTIFICATION_ID
        )

        assert await hass.config_entries.async_remove(hub.entry_id)
        await hass.async_block_till_done()

    # The mailbox stops waiting as soon as the hub is gone.
    assert mailbox.state is ConfigEntryState.SETUP_RETRY
    assert ir.async_get(hass).async_get_issue(DOMAIN, "ai_unavailable") is None
    assert (
        PERSISTENT_NOTIFICATION_ID
        not in persistent_notification._async_get_or_create_notifications(hass)
    )
    stored = await ParcelsStore(hass).async_load()
    assert stored.parcels == {}


async def test_start_repairs_stored_parcels_once(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Parcels an earlier release stored are fixed once, without reading mail."""
    data = ParcelsData()
    when = datetime(2026, 11, 16, 9, tzinfo=UTC)
    # What 0.1.0 stored for Amazon's e-mail without a carrier number.
    parcel_id = apply_contribution(
        data,
        contribution(
            "msg:amazon#0",
            time=when,
            carrier="amazon",
            merchant="Amazon.es",
            orders=["171-0000001-0000001"],
            eta=Eta(start=date(2026, 11, 19), end=date(2026, 11, 19)),
            label="amazon.es",
        ),
        when,
    ).parcel_id
    assert parcel_id is not None
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    hub = add_hub(hass)

    engine = await async_setup_parcels(hass)

    parcel = engine.data.parcels[parcel_id]
    assert parcel.state.carrier is None
    assert parcel.state.merchant == "Amazon"
    assert engine.data.engine[REPAIR_KEY] == REPAIR_VERSION

    with patch("custom_components.parcels.engine.repair_store") as repair:
        assert await hass.config_entries.async_reload(hub.entry_id)
        await hass.async_block_till_done()

    repair.assert_not_called()
    engine = get_engine(hass)
    assert engine is not None
    assert engine.data.parcels[parcel_id].state.carrier is None


async def test_start_repairs_again_for_newer_rules(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A store an earlier repair fixed is repaired again when rules were added."""
    data = ParcelsData()
    # What 0.1.1's repair left.
    data.engine[REPAIR_KEY] = 1
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)

    with patch(
        "custom_components.parcels.engine.repair_store", return_value=set()
    ) as repair:
        engine = await async_setup_parcels(hass)

    repair.assert_called_once()
    # Only the rules added since run again.
    assert repair.call_args.kwargs["since"] == 1
    assert engine.data.engine[REPAIR_KEY] == REPAIR_VERSION


async def test_start_forgets_an_unproven_amazon_carrier(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A store 0.1.7 repaired loses the carriers Amazon never proved.

    The local AI and the Parcel app named Amazon without one of its numbers;
    what a parser read stays.
    """
    data = ParcelsData()
    data.engine[REPAIR_KEY] = 3
    when = datetime(2026, 11, 16, 9, tzinfo=UTC)
    parcels: dict[Source, str] = {}
    for day, source, origin_id, label in (
        (19, Source.AI, "msg:ai#0", "amazon.es"),
        (20, Source.PARCELAPP, "pa:171-0000020-0000001", "Parcel app"),
        (21, Source.PARSER, "msg:parser#0", "amazon.es"),
    ):
        parcel_id = apply_contribution(
            data,
            contribution(
                origin_id,
                time=when,
                carrier="amazon",
                merchant="Amazon.es",
                orders=[f"171-00000{day}-0000001"],
                eta=Eta(start=date(2026, 11, day), end=date(2026, 11, day)),
                source=source,
                label=label,
            ),
            when,
        ).parcel_id
        assert parcel_id is not None
        parcels[source] = parcel_id
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)

    engine = await async_setup_parcels(hass)

    carriers = {
        source: engine.data.parcels[parcel_id].state.carrier
        for source, parcel_id in parcels.items()
    }
    assert carriers == {
        Source.AI: None,
        Source.PARCELAPP: None,
        Source.PARSER: "amazon",
    }
    assert engine.data.engine[REPAIR_KEY] == REPAIR_VERSION
    assert engine.diagnostics()["amazon_carrier_repaired"] == {
        "origins": 2,
        "senders": 0,
        "answers": 0,
    }


async def test_start_folds_late_order_mail_once(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """The parcel an order's late e-mail made joins the order's parcel, once."""
    data = ParcelsData()
    order = "405-7777777-0000001"
    parcels = []
    for origin, kind, when in (
        ("msg:o#0", MailKind.ORDER, at()),
        ("msg:d#0", MailKind.DELIVERED, at(days=3)),
    ):
        parcels.append(
            apply_contribution(
                data,
                dataclasses.replace(
                    contribution(
                        origin,
                        kind=kind,
                        time=when,
                        merchant="Amazon.es",
                        orders=[order],
                        carrier="ctt" if kind is MailKind.DELIVERED else None,
                        number="RR123456785PT" if kind is MailKind.DELIVERED else None,
                    ),
                    order_placed=when if kind is MailKind.ORDER else None,
                ),
                when,
            ).parcel_id
        )
    parcel_id = parcels[0]
    assert parcel_id is not None
    assert parcels == [parcel_id, parcel_id]
    archive_parcel(data, parcel_id, at(days=10))
    # What 0.1.15 made of the order's e-mail a few days later.
    late = at(days=13)
    alone = ParcelsData()
    stray = apply_contribution(
        alone,
        dataclasses.replace(
            contribution(
                "msg:late#0",
                kind=MailKind.ORDER,
                time=late,
                merchant="Amazon.es",
                orders=[order],
            ),
            order_placed=late,
        ),
        late,
    ).parcel_id
    assert stray is not None
    data.parcels[stray] = alone.parcels[stray]
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    hub = add_hub(hass)

    engine = await async_setup_parcels(hass)

    assert set(engine.data.parcels) == {parcel_id}
    parcel = engine.data.parcels[parcel_id]
    assert "msg:late#0" in parcel.origins
    assert parcel.archived == at(days=10)
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert engine.data.engine[ORDER_FOLD_KEY] == 1
    assert engine.diagnostics()["order_fold"] == 1

    with patch("custom_components.parcels.engine.fold_known_orders") as fold:
        assert await hass.config_entries.async_reload(hub.entry_id)
        await hass.async_block_till_done()

    fold.assert_not_called()
