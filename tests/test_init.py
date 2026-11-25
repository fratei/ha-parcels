"""Tests for loading, unloading and removing the Parcels entries."""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_scheduled_timer_handles

from custom_components.parcels.const import (
    CONF_OWNER,
    DOMAIN,
    PERSISTENT_NOTIFICATION_ID,
    REASON_UNKNOWN_FORMAT,
    SIGNAL_DATA_UPDATED,
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
from custom_components.parcels.mail.errors import MailServerError
from custom_components.parcels.models import (
    MessageRecord,
    MessageState,
    ParcelsData,
    ReviewItem,
    Source,
)
from custom_components.parcels.notifier import Notifier
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.store import ParcelsStore

from .common import (
    OTHER_ADDRESS,
    OTHER_OWNER,
    OWNER,
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    async_wait_for_mail,
    patch_mail_clients,
)
from .factories import at, contribution

NOW = "2026-11-17 10:00:00+00:00"
CTT_MAIL = "carriers/ctt_in_transit_pt.eml"
SHOP_MAIL = "common/small_shop_ctt.eml"
THIRD_OWNER = "person.kim"


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


@pytest.mark.parametrize("fails", ["building", "starting"])
async def test_a_failed_hub_setup_stops_its_engine(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, fails: str
) -> None:
    """A hub setup that fails once its engine started stops that engine.

    The entities it set up go too, so the next setup runs the only engine and
    its entities read that engine.
    """
    engines: list[ParcelsEngine] = []

    def new_engine(*args: Any) -> ParcelsEngine:
        engines.append(ParcelsEngine(*args))
        return engines[-1]

    def new_notifier(*args: Any) -> Notifier:
        if fails == "building" and len(engines) == 1:
            raise RuntimeError("made-up failure")
        return Notifier(*args)

    real_start = Notifier.async_start

    async def start(notifier: Notifier) -> None:
        if fails == "starting" and len(engines) == 1:
            raise RuntimeError("made-up failure")
        await real_start(notifier)

    hub = add_hub(hass)
    with (
        patch("custom_components.parcels.ParcelsEngine", side_effect=new_engine),
        patch("custom_components.parcels.Notifier", side_effect=new_notifier),
        patch.object(Notifier, "async_start", autospec=True, side_effect=start),
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert hub.state is ConfigEntryState.SETUP_ERROR

        assert await hass.config_entries.async_reload(hub.entry_id)
        await hass.async_block_till_done()

    assert hub.state is ConfigEntryState.LOADED
    first, second = engines
    assert not first.started
    assert second.started
    assert get_engine(hass) is second
    midnight_jobs = [
        handle
        for handle in get_scheduled_timer_handles(hass.loop)
        if not handle.cancelled() and "ParcelsEngine._async_midnight" in repr(handle)
    ]
    assert len(midnight_jobs) == 1
    sensor = hass.data[DATA_INSTANCES]["sensor"].get_entity("sensor.parcels_in_transit")
    assert sensor.engine is second
    assert "has already been setup" not in caplog.text


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
        assert engine.data.engine["owners"] == {mailbox.entry_id: OWNER}

        assert await hass.config_entries.async_remove(mailbox.entry_id)
        await hass.async_block_till_done()

    assert mailbox.entry_id not in engine.data.cursors
    assert engine.data.engine["owners"] == {}
    assert not engine.is_synced(mailbox.entry_id)
    assert engine.mailboxes == {}
    assert all(not record.refs for record in engine.data.messages.values())
    # The parcel stays.
    assert len(engine.data.parcels) == 1


async def test_daily_job_forgets_unknown_mailboxes(hass: HomeAssistant) -> None:
    """The daily job drops what Parcels kept of mailboxes removed meanwhile."""
    client = FakeMailClient()
    add_hub(hass)
    mailbox = add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        engine.data.engine["owners"]["removed-mailbox"] = OTHER_OWNER
        engine._async_daily(datetime.now(UTC))

    assert engine.data.engine["owners"] == {mailbox.entry_id: OWNER}


async def _set_owner(
    hass: HomeAssistant, mailbox: MockConfigEntry, owner: str | None
) -> None:
    """Choose a mailbox's owner in its options, which reloads it."""
    result = await hass.config_entries.options.async_init(mailbox.entry_id)
    user_input = {k: v for k, v in mailbox.options.items() if k != CONF_OWNER}
    if owner:
        user_input[CONF_OWNER] = owner
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await async_wait_for_mail(hass)


def _review(
    item_id: str, message: str, mailbox: str | None, owner: str | None
) -> ReviewItem:
    return ReviewItem(
        id=item_id,
        created=datetime.now(UTC),
        message=message,
        received=None,
        sender="Loja Exemplo <envios@loja-exemplo.pt>",
        sender_domain="loja-exemplo.pt",
        subject="A sua encomenda foi enviada",
        mailbox=mailbox,
        owner=owner,
        reason=REASON_UNKNOWN_FORMAT,
        authenticated=True,
        source=Source.PARSER,
    )


async def test_mailbox_owner_chosen_later_gets_mail_read_before(
    hass: HomeAssistant,
) -> None:
    """An owner chosen after the first sync gets the e-mails read before.

    Their parcels are the owner's, and so are the e-mails under Needs review.
    """
    client = FakeMailClient()
    client.add(CTT_MAIL)
    client.add(SHOP_MAIL)
    add_hub(hass)
    mailbox = add_mailbox(hass, owner=None)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        (parcel,) = engine.data.parcels.values()
        (item,) = engine.data.review.values()
        assert parcel.state.owners == ()
        assert item.owner is None
        assert engine.data.engine["owners"] == {mailbox.entry_id: ""}

        updates: list[None] = []
        unsubscribe = async_dispatcher_connect(
            hass, SIGNAL_DATA_UPDATED, lambda: updates.append(None)
        )
        await _set_owner(hass, mailbox, OWNER)
        unsubscribe()

        # The page, the entities and the notifier hear of it.
        assert updates
        assert [record.owners for record in engine.data.messages.values()] == [
            (OWNER,),
            (OWNER,),
        ]
        assert parcel.state.owners == (OWNER,)
        assert item.owner == OWNER
        assert engine.data.engine["owners"] == {mailbox.entry_id: OWNER}


@pytest.mark.parametrize(
    ("owner", "shared", "owners"),
    [
        (OTHER_OWNER, False, (OTHER_OWNER,)),
        (None, False, ()),
        # Another mailbox with the e-mail is still the former owner's.
        (OTHER_OWNER, True, (OWNER, OTHER_OWNER)),
        (None, True, (OWNER,)),
    ],
)
async def test_mailbox_owner_change_replaces_the_former_owner(
    hass: HomeAssistant, owner: str | None, shared: bool, owners: tuple[str, ...]
) -> None:
    """A mailbox's former owner leaves the e-mails it read, and their parcels.

    They stay where another mailbox with the same e-mail is still theirs.
    """
    clients = [FakeMailClient()]
    add_hub(hass)
    mailbox = add_mailbox(hass)
    if shared:
        clients.append(FakeMailClient(address=OTHER_ADDRESS))
        add_mailbox(hass, address=OTHER_ADDRESS)
    for client in clients:
        client.add(CTT_MAIL)

    with patch_mail_clients(*clients):
        engine = await async_setup_parcels(hass)
        (record,) = engine.data.messages.values()
        (parcel,) = engine.data.parcels.values()
        assert record.owners == (OWNER,)
        assert parcel.state.owners == (OWNER,)

        await _set_owner(hass, mailbox, owner)

    assert record.owners == owners
    assert parcel.state.owners == tuple(sorted(owners))
    assert engine.data.engine["owners"][mailbox.entry_id] == (owner or "")


async def test_mailbox_owner_change_keeps_the_owners_order(
    hass: HomeAssistant,
) -> None:
    """A mailbox's new owner takes the former owner's place on its e-mails."""
    first, second = FakeMailClient(), FakeMailClient(address=OTHER_ADDRESS)
    for client in (first, second):
        client.add(CTT_MAIL)
    add_hub(hass)
    mailbox = add_mailbox(hass)

    with patch_mail_clients(first, second):
        engine = await async_setup_parcels(hass)
        other = add_mailbox(hass, address=OTHER_ADDRESS, owner=OTHER_OWNER)
        assert await hass.config_entries.async_setup(other.entry_id)
        await async_wait_for_mail(hass)
        (record,) = engine.data.messages.values()
        assert record.owners == (OWNER, OTHER_OWNER)

        await _set_owner(hass, mailbox, THIRD_OWNER)
        assert record.owners == (THIRD_OWNER, OTHER_OWNER)

        await _set_owner(hass, other, None)
        assert record.owners == (THIRD_OWNER,)

    (parcel,) = engine.data.parcels.values()
    assert parcel.state.owners == (THIRD_OWNER,)


async def test_mailbox_owners_changed_while_the_hub_was_off(
    hass: HomeAssistant,
) -> None:
    """Owners chosen while the hub was off apply once it's back.

    Two mailboxes had the e-mail and the same owner: the first to apply its
    new owner takes the former one off, and the second finds it gone.
    """
    first, second = FakeMailClient(), FakeMailClient(address=OTHER_ADDRESS)
    for client in (first, second):
        client.add(CTT_MAIL)
    hub = add_hub(hass)
    mailbox = add_mailbox(hass)
    other = add_mailbox(hass, address=OTHER_ADDRESS)

    with patch_mail_clients(first, second):
        engine = await async_setup_parcels(hass)
        (record,) = engine.data.messages.values()
        assert record.owners == (OWNER,)
        with patch("custom_components.parcels.HUB_WAIT", 0):
            assert await hass.config_entries.async_unload(hub.entry_id)
            await hass.async_block_till_done()
            await _set_owner(hass, mailbox, THIRD_OWNER)
            await _set_owner(hass, other, OTHER_OWNER)
        assert other.state is ConfigEntryState.SETUP_RETRY

        assert await hass.config_entries.async_setup(hub.entry_id)
        await async_wait_for_mail(hass)
        engine = get_engine(hass)

    assert engine is not None
    assert mailbox.state is ConfigEntryState.LOADED
    assert other.state is ConfigEntryState.LOADED
    (record,) = engine.data.messages.values()
    assert sorted(record.owners) == [THIRD_OWNER, OTHER_OWNER]
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.owners == (THIRD_OWNER, OTHER_OWNER)


async def test_mailbox_owner_change_reaches_its_reviews(
    hass: HomeAssistant,
) -> None:
    """Reviews of a mailbox and of its e-mails get their owner again.

    As when they were made: the e-mail's first owner, else the owner of the
    review's mailbox. Reviews of other e-mails stay as they are.
    """
    first, second = FakeMailClient(), FakeMailClient(address=OTHER_ADDRESS)
    add_hub(hass)
    mailbox = add_mailbox(hass)
    other = add_mailbox(hass, address=OTHER_ADDRESS, owner=OTHER_OWNER)
    mine, theirs, removed = mailbox.entry_id, other.entry_id, "removed-mailbox"

    with patch_mail_clients(first, second):
        engine = await async_setup_parcels(hass)
        data = engine.data
        for key, refs, owners in (
            # Also an owner through a mailbox removed since.
            ("m-first", (mine,), (OTHER_OWNER, OWNER)),
            ("m-both", (mine, theirs), (OWNER, OTHER_OWNER)),
            ("m-mine", (mine,), (OWNER,)),
            # Read by the other mailbox before it had an owner, and gone from
            # it since.
            ("m-gone", (mine,), (OWNER,)),
        ):
            data.messages[key] = MessageRecord(
                hash=key,
                seen=datetime.now(UTC),
                state=MessageState.REVIEW,
                refs=dict.fromkeys(refs, f"id-{key}"),
                owners=owners,
            )
        reviews = {
            "first": _review("first", "m-first", mine, OTHER_OWNER),
            "theirs": _review("theirs", "m-both", theirs, OWNER),
            "unknown": _review("unknown", "m-unknown", mine, OWNER),
            "removed": _review("removed", "m-mine", removed, OWNER),
            "gone": _review("gone", "m-gone", theirs, OWNER),
            "elsewhere": _review("elsewhere", "m-elsewhere", removed, OTHER_OWNER),
        }
        data.review.update(reviews)

        await _set_owner(hass, mailbox, THIRD_OWNER)
        assert {key: item.owner for key, item in reviews.items()} == {
            "first": OTHER_OWNER,
            "theirs": THIRD_OWNER,
            "unknown": THIRD_OWNER,
            "removed": THIRD_OWNER,
            "gone": THIRD_OWNER,
            "elsewhere": OTHER_OWNER,
        }

        await _set_owner(hass, mailbox, None)

    assert {key: item.owner for key, item in reviews.items()} == {
        "first": OTHER_OWNER,
        "theirs": OTHER_OWNER,
        "unknown": None,
        "removed": None,
        "gone": OTHER_OWNER,
        "elsewhere": OTHER_OWNER,
    }


async def test_mailbox_owner_gets_mail_that_failed_to_download(
    hass: HomeAssistant,
) -> None:
    """An e-mail that failed to download is the new owner's once it's read."""
    client = FakeMailClient()
    client.add(CTT_MAIL, provider_id="bad")
    client.add(SHOP_MAIL)
    client.fetch_errors["bad"] = MailServerError("HTTP 500")
    add_hub(hass)
    mailbox = add_mailbox(hass, owner=None)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        (record,) = (
            record
            for record in engine.data.messages.values()
            if record.state is MessageState.FAILED
        )
        assert not engine.data.parcels

        await _set_owner(hass, mailbox, OWNER)
        assert record.owners == (OWNER,)

        del client.fetch_errors["bad"]
        await engine.async_refresh()
        await hass.async_block_till_done()

    assert record.state is MessageState.APPLIED
    assert [p.state.owners for p in engine.data.parcels.values()] == [(OWNER,)]


async def test_upgrade_gives_mailbox_owner_the_mail_read_before(
    hass: HomeAssistant,
) -> None:
    """After an upgrade, a mailbox's owner gets the e-mails it read before.

    Earlier releases didn't keep which owner a mailbox gave its e-mails, so
    nobody is removed.
    """
    client = FakeMailClient()
    client.add(CTT_MAIL)
    add_hub(hass)
    mailbox = add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        (record,) = engine.data.messages.values()
        (parcel,) = engine.data.parcels.values()
        # As earlier releases left an owner changed after the first sync.
        del engine.data.engine["owners"]
        record.owners = (OTHER_OWNER,)
        for origin in parcel.origins.values():
            origin.owners = (OTHER_OWNER,)
        parcel.touch(datetime.now(UTC))

        assert await hass.config_entries.async_reload(mailbox.entry_id)
        await async_wait_for_mail(hass)

    assert record.owners == (OTHER_OWNER, OWNER)
    assert parcel.state.owners == (OWNER, OTHER_OWNER)
    assert engine.data.engine["owners"] == {mailbox.entry_id: OWNER}


async def test_reload_without_owner_change_changes_nothing(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Reloading a mailbox or the hub leaves the owners and parcels alone.

    An owner that isn't the mailbox's doing stays too.
    """
    client = FakeMailClient()
    client.add(CTT_MAIL)
    hub = add_hub(hass)
    mailbox = add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        (record,) = engine.data.messages.values()
        (parcel,) = engine.data.parcels.values()
        # E.g. from a mailbox removed since.
        record.owners = (OTHER_OWNER, OWNER)
        item = _review("kept", record.hash, mailbox.entry_id, OWNER)
        engine.data.review[item.id] = item
        updated = parcel.updated
        freezer.tick(timedelta(hours=1))

        assert await hass.config_entries.async_reload(mailbox.entry_id)
        await async_wait_for_mail(hass)
        assert record.owners == (OTHER_OWNER, OWNER)
        assert parcel.updated == updated
        assert item.owner == OWNER

        assert await hass.config_entries.async_reload(hub.entry_id)
        await async_wait_for_mail(hass)
        engine = get_engine(hass)

    assert engine is not None
    (record,) = engine.data.messages.values()
    (parcel,) = engine.data.parcels.values()
    assert record.owners == (OTHER_OWNER, OWNER)
    assert parcel.updated == updated
    assert engine.data.review["kept"].owner == OWNER


async def test_upgrade_without_mailbox_owner_changes_nothing(
    hass: HomeAssistant,
) -> None:
    """After an upgrade, a mailbox without owner leaves the owners alone."""
    client = FakeMailClient()
    client.add(CTT_MAIL)
    add_hub(hass)
    mailbox = add_mailbox(hass, owner=None)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        (record,) = engine.data.messages.values()
        (parcel,) = engine.data.parcels.values()
        item = _review("kept", "m-unknown", mailbox.entry_id, OTHER_OWNER)
        engine.data.review[item.id] = item
        # As earlier releases left an owner removed after the first sync.
        del engine.data.engine["owners"]
        record.owners = (OTHER_OWNER,)
        for origin in parcel.origins.values():
            origin.owners = (OTHER_OWNER,)
        parcel.touch(datetime.now(UTC))

        assert await hass.config_entries.async_reload(mailbox.entry_id)
        await async_wait_for_mail(hass)

    assert record.owners == (OTHER_OWNER,)
    assert parcel.state.owners == (OTHER_OWNER,)
    assert item.owner == OTHER_OWNER
    assert engine.data.engine["owners"] == {mailbox.entry_id: ""}


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


def _damaged_notifier_state(day: str) -> dict[str, Any]:
    """The notifier's stored state with a well-formed but impossible time."""
    return {
        "version": 1,
        "days": {
            day: {
                "board": [],
                "activities": {
                    "device-1": {
                        "p_1": {"tag": "parcel-1", "started": f"{day[:5]}13-02T08:00"}
                    }
                },
            }
        },
    }


@pytest.mark.parametrize("day", ["2026-11-02", "2026-11-17"])
async def test_hub_starts_with_damaged_stored_data(
    hass: HomeAssistant, hass_storage: dict[str, Any], day: str
) -> None:
    """A damaged entry or time is skipped and counted; the hub still starts."""
    data = ParcelsData()
    parcel_id = apply_contribution(
        data, contribution("msg:a#0", carrier="dpd", number="05212345678901"), at()
    ).parcel_id
    stored = data.as_dict()
    stored["parcels"].append(None)
    stored["engine"] = {"notifier": _damaged_notifier_state(day)}
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": stored,
    }
    hub = add_hub(hass)

    engine = await async_setup_parcels(hass)

    assert hub.state is ConfigEntryState.LOADED
    assert list(engine.data.parcels) == [parcel_id]
    assert engine.diagnostics()["damaged"] == {"engine": 1, "parcels": 1}


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
