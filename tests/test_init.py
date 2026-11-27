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
from homeassistant.core import Event, HomeAssistant, callback
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
    EVENT_DELIVERED,
    EVENT_PARCEL_ADDED,
    EVENT_STATUS_CHANGED,
    PERSISTENT_NOTIFICATION_ID,
    REASON_UNKNOWN_FORMAT,
    SIGNAL_DATA_UPDATED,
    VERSION,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.dedup import (
    ORDER_FOLD_KEY,
    REASON_RELAY,
    REASON_SAME_ORDER,
    REPAIR_KEY,
    REPAIR_VERSION,
    TYPED_JOIN_KEY,
    Contribution,
    apply_contribution,
    archive_parcel,
)
from custom_components.parcels.engine import (
    RELEASE_KEY,
    RELIST_KEY,
    UNIGNORE_REREAD_KEY,
    ParcelsEngine,
    get_engine,
)
from custom_components.parcels.mail.errors import MailServerError
from custom_components.parcels.models import (
    MessageRecord,
    MessageState,
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    ReviewItem,
    Source,
)
from custom_components.parcels.notifier import Notifier
from custom_components.parcels.parsers.base import Eta, MailMessage
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
    async_wait_reprocess,
    patch_mail_clients,
)
from .factories import at, contribution

NOW = "2026-11-17 10:00:00+00:00"
CTT_MAIL = "carriers/ctt_in_transit_pt.eml"
SHOP_MAIL = "common/small_shop_ctt.eml"
SHOP = "loja-exemplo.example"
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
    assert engine.diagnostics()["placeholder_items_repaired"] == {
        "parcels": 0,
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


async def test_start_joins_a_typed_parcel_left_apart_quietly(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A parcel an earlier release left apart joins the order's as it starts.

    It's a change made once after the update: it fires no events, though the
    status it gives the order's parcel is less than a day old.
    """
    now = datetime.fromisoformat(NOW)
    order, shop = "001234567890", "Loja Exemplo"
    data = ParcelsData()
    data.engine[REPAIR_KEY] = REPAIR_VERSION
    ordered = now - timedelta(hours=3)
    parcel_id = apply_contribution(
        data,
        dataclasses.replace(
            contribution(
                "msg:shop#0",
                kind=MailKind.ORDER,
                time=ordered,
                merchant=shop,
                orders=[order],
            ),
            order_placed=ordered,
        ),
        ordered,
    ).parcel_id
    assert parcel_id is not None
    # What releases before 0.1.26 made of the number typed an hour ago.
    typed_at = now - timedelta(hours=1)
    origin = Origin(
        id="man:p_typed",
        source=Source.MANUAL,
        time=typed_at,
        tracking_number=order,
        merchant=shop,
        owners=(OWNER,),
        confirmed=True,
    )
    alone = ParcelsData()
    typed_id = apply_contribution(
        alone,
        Contribution(
            origin=origin,
            events=[
                ParcelEvent(
                    time=typed_at,
                    source=Source.MANUAL,
                    origin=origin.id,
                    status=ParcelStatus.SHIPPED,
                    kind=MailKind.SHIPPED,
                )
            ],
        ),
        typed_at,
    ).parcel_id
    assert typed_id is not None
    data.parcels[typed_id] = alone.parcels[typed_id]
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    hub = add_hub(hass)
    fired: list[str] = []
    for event_type in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED):
        hass.bus.async_listen(event_type, lambda event: fired.append(event.event_type))

    engine = await async_setup_parcels(hass)
    await hass.async_block_till_done()

    assert list(engine.data.parcels) == [parcel_id]
    parcel = engine.data.parcels[parcel_id]
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert parcel.auto_merged is not None
    assert fired == []
    assert engine.data.engine[TYPED_JOIN_KEY] == 1
    assert engine.diagnostics()["typed_join"] == 1

    with patch("custom_components.parcels.engine.join_typed_parcels") as join:
        assert await hass.config_entries.async_reload(hub.entry_id)
        await hass.async_block_till_done()

    join.assert_not_called()


@pytest.mark.parametrize(
    ("repaired", "joined"),
    [(4, True), (REPAIR_VERSION, False)],
    ids=["0.1.23", "0.1.24"],
)
async def test_start_joins_an_old_delivery_to_the_package_open_then(
    hass: HomeAssistant, hass_storage: dict[str, Any], repaired: int, joined: bool
) -> None:
    """The repair of a 0.1.23 store joins a delivery it left apart, quietly.

    The order's first package was already delivered when the shop's
    "delivered" e-mail, which names only the order, came: it's the second
    package's. Reconciling looks at the last 30 days only; the repair looks
    at every order, once, so a store 0.1.24 repaired keeps it apart.
    """
    now = datetime.fromisoformat(NOW)
    order, shop = "001234567890", "Loja Exemplo"
    data = ParcelsData()
    data.engine[REPAIR_KEY] = repaired
    mails = [
        contribution(
            "msg:one#0",
            time=now - timedelta(days=45),
            carrier="ctt",
            number="RR482915732PT",
            merchant=shop,
            orders=[order],
        ),
        contribution(
            "msg:one-done#0",
            kind=MailKind.DELIVERED,
            time=now - timedelta(days=43),
            carrier="ctt",
            number="RR482915732PT",
            merchant=shop,
            orders=[order],
        ),
        contribution(
            "msg:two#0",
            time=now - timedelta(days=42),
            carrier="ctt",
            number="RR123456785PT",
            merchant=shop,
            orders=[order],
        ),
    ]
    ids = [apply_contribution(data, mail, mail.origin.time).parcel_id for mail in mails]
    first, second = ids[0], ids[2]
    assert ids[1] == first
    assert second not in (None, first)
    # What 0.1.23 made of the shop's "delivered" e-mail.
    delivered = now - timedelta(days=40)
    alone = ParcelsData()
    apart = apply_contribution(
        alone,
        contribution(
            "msg:done#0",
            kind=MailKind.DELIVERED,
            time=delivered,
            merchant=shop,
            orders=[order],
        ),
        delivered,
    ).parcel_id
    assert apart is not None
    data.parcels[apart] = alone.parcels[apart]
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)
    fired: list[str] = []
    for event_type in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED):
        hass.bus.async_listen(event_type, lambda event: fired.append(event.event_type))

    engine = await async_setup_parcels(hass)
    await hass.async_block_till_done()

    parcels = engine.data.parcels
    assert parcels[first].state.status is ParcelStatus.DELIVERED
    assert "msg:done#0" not in parcels[first].origins
    if joined:
        assert apart not in parcels
        parcel = parcels[second]
        assert "msg:done#0" in parcel.origins
        assert parcel.state.status is ParcelStatus.DELIVERED
        assert not parcel.state.inferred
        assert parcel.auto_merged is not None
        assert parcel.auto_merged.reason == REASON_SAME_ORDER
    else:
        assert set(parcels) == {first, second, apart}
        # Only three weeks without news say it was delivered.
        assert parcels[second].state.inferred_reason == "quiet"
    assert fired == []
    assert engine.data.engine[REPAIR_KEY] == REPAIR_VERSION


@pytest.mark.parametrize(
    ("release", "events"),
    [
        (None, set()),
        # The delivery was told of before the restart: its parcel is new, and
        # the package goes back, but the delivery isn't news again.
        ({"version": VERSION}, {EVENT_STATUS_CHANGED, EVENT_PARCEL_ADDED}),
    ],
    ids=["after-an-update", "same-release"],
)
async def test_start_reconciles_quietly_once_after_an_update(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    release: dict[str, Any] | None,
    events: set[str],
) -> None:
    """A new release reconciles once as it starts, before it tells statuses
    apart: what its rules change then fires no events.

    0.1.27 put the shop's "delivered" e-mail, which names only the order, in
    one of two packages on their way an hour ago. Now it gets a parcel of
    its own, suggested for each package.
    """
    now = datetime.fromisoformat(NOW)
    order, shop = "001234567890", "Loja Exemplo"
    data = ParcelsData()
    data.engine[REPAIR_KEY] = REPAIR_VERSION
    if release is not None:
        data.engine[RELEASE_KEY] = release
    mails = [
        contribution(
            "msg:one#0",
            time=now - timedelta(hours=5),
            carrier="ctt",
            number="RR482915732PT",
            merchant=shop,
            orders=[order],
        ),
        contribution(
            "msg:done#0",
            kind=MailKind.DELIVERED,
            time=now - timedelta(hours=1),
            merchant=shop,
            orders=[order],
        ),
        contribution(
            "msg:two#0",
            time=now - timedelta(hours=4),
            carrier="ctt",
            number="RR123456785PT",
            merchant=shop,
            orders=[order],
        ),
    ]
    ids = [apply_contribution(data, mail, mail.origin.time).parcel_id for mail in mails]
    first, second = ids[0], ids[2]
    assert ids[1] == first
    assert data.parcels[first].state.status is ParcelStatus.DELIVERED
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)
    fired: list[str] = []
    for event_type in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED):
        hass.bus.async_listen(event_type, lambda event: fired.append(event.event_type))

    engine = await async_setup_parcels(hass)
    await hass.async_block_till_done()

    parcels = engine.data.parcels
    delivery = next(p for p in parcels.values() if "msg:done#0" in p.origins)
    assert delivery.id not in (first, second)
    assert delivery.state.status is ParcelStatus.DELIVERED
    assert parcels[first].state.status is ParcelStatus.SHIPPED
    assert parcels[second].state.status is ParcelStatus.SHIPPED
    assert {(s.parcel_id, s.candidates) for s in engine.suggestions} == {
        (first, (delivery.id,)),
        (second, (delivery.id,)),
    }
    assert set(fired) == events
    assert engine.data.engine[RELEASE_KEY]["version"] == VERSION
    assert engine.diagnostics()["release"]["version"] == VERSION


# What automations hear: an event's type, parcel and status.
Fired = list[tuple[str, str, str]]


def _listen(hass: HomeAssistant) -> Fired:
    """Record the events Parcels fires, in order."""
    fired: Fired = []

    @callback
    def record(event: Event) -> None:
        fired.append((event.event_type, event.data["parcel_id"], event.data["status"]))

    for event_type in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED):
        hass.bus.async_listen(event_type, record)
    return fired


def _read(
    engine: ParcelsEngine,
    origin_id: str,
    hours: float,
    kind: MailKind = MailKind.SHIPPED,
    **details: Any,
) -> None:
    """Read an e-mail about Loja Exemplo's order, sent ``hours`` ago."""
    now = datetime.fromisoformat(NOW)
    details.setdefault("merchant", "Loja Exemplo")
    details.setdefault("orders", ["001234567890"])
    apply_contribution(
        engine.data,
        contribution(
            origin_id, kind=kind, time=now - timedelta(hours=hours), **details
        ),
        now,
    )
    engine.async_changed()


def _holder(engine: ParcelsEngine, origin_id: str) -> Parcel:
    """Return the parcel an e-mail is in."""
    return next(p for p in engine.data.parcels.values() if origin_id in p.origins)


async def test_a_delivery_placed_again_is_told_once(hass: HomeAssistant) -> None:
    """parcels_delivered fires once per delivery, however often Parcels
    places its e-mail again.

    The shop's "delivered" e-mail, which names only the order, delivers its
    only package on its way. The order's other package, read later, was on
    its way too: the delivery gets a parcel of its own, and the first package
    goes back. Automations hear of both, but not of the delivery again. The
    other package's own delivery is news.
    """
    add_hub(hass)
    engine = await async_setup_parcels(hass)
    fired = _listen(hass)

    _read(engine, "msg:one#0", 5, carrier="ctt", number="RR482915732PT")
    _read(engine, "msg:done#0", 1, MailKind.DELIVERED)
    first = _holder(engine, "msg:one#0").id
    assert _holder(engine, "msg:done#0").id == first
    _read(engine, "msg:two#0", 4, carrier="ctt", number="RR123456785PT")
    second = _holder(engine, "msg:two#0").id
    delivery = _holder(engine, "msg:done#0").id
    assert delivery not in (first, second)
    _read(
        engine,
        "msg:arrived#0",
        0.5,
        MailKind.DELIVERED,
        carrier="ctt",
        number="RR123456785PT",
        merchant=None,
        orders=[],
    )
    await hass.async_block_till_done()

    assert _holder(engine, "msg:arrived#0").id == second
    assert sorted(fired) == sorted(
        [
            (EVENT_PARCEL_ADDED, first, "shipped"),
            (EVENT_STATUS_CHANGED, first, "delivered"),
            (EVENT_DELIVERED, first, "delivered"),
            (EVENT_STATUS_CHANGED, first, "shipped"),
            (EVENT_PARCEL_ADDED, second, "shipped"),
            (EVENT_PARCEL_ADDED, delivery, "delivered"),
            (EVENT_STATUS_CHANGED, second, "delivered"),
            (EVENT_DELIVERED, second, "delivered"),
        ]
    )


async def test_a_delivery_joined_and_taken_apart_is_told_once(
    hass: HomeAssistant,
) -> None:
    """The shop's delivery, read before the e-mail of the package on its way
    when it was sent, gets a parcel of its own, then joins the package as a
    guess. Undoing the guess takes it apart again. Each time the parcels'
    statuses are news, but the delivery was only once.
    """
    add_hub(hass)
    engine = await async_setup_parcels(hass)
    fired = _listen(hass)

    # Sent after the delivery: not the package it's about.
    _read(engine, "msg:two#0", 2, carrier="ctt", number="RR123456785PT")
    later = _holder(engine, "msg:two#0").id
    _read(engine, "msg:done#0", 3, MailKind.DELIVERED)
    alone = _holder(engine, "msg:done#0").id
    _read(engine, "msg:one#0", 5, carrier="ctt", number="RR482915732PT")
    package = _holder(engine, "msg:one#0")
    assert "msg:done#0" in package.origins
    assert package.auto_merged is not None
    engine.undo_merge(package.id)
    await hass.async_block_till_done()

    delivery = _holder(engine, "msg:done#0")
    assert package.state.status is ParcelStatus.SHIPPED
    assert fired == [
        (EVENT_PARCEL_ADDED, later, "shipped"),
        (EVENT_PARCEL_ADDED, alone, "delivered"),
        (EVENT_DELIVERED, alone, "delivered"),
        (EVENT_PARCEL_ADDED, package.id, "delivered"),
        (EVENT_STATUS_CHANGED, package.id, "shipped"),
        (EVENT_PARCEL_ADDED, delivery.id, "delivered"),
    ]


async def test_a_delivery_beside_two_packages_is_told_once(
    hass: HomeAssistant,
) -> None:
    """The shop's delivery stays apart from the order's two packages on
    their way when one of them goes out for delivery, and its news is told
    once."""
    add_hub(hass)
    engine = await async_setup_parcels(hass)
    fired = _listen(hass)

    _read(engine, "msg:order#0", 5, MailKind.ORDER)
    _read(engine, "msg:one#0", 4.6, carrier="ctt", number="RR482915732PT")
    _read(engine, "msg:two#0", 4.5, carrier="ctt", number="RR123456785PT")
    _read(engine, "msg:done#0", 1, MailKind.DELIVERED)
    _read(
        engine,
        "msg:out#0",
        0.1,
        MailKind.OUT_FOR_DELIVERY,
        carrier="ctt",
        number="RR482915732PT",
        orders=[],
    )
    _read(engine, "msg:other#0", 0, carrier="ctt", number="RR000000017PT", orders=[])
    await hass.async_block_till_done()

    package = _holder(engine, "msg:one#0")
    delivery = _holder(engine, "msg:done#0")
    assert package.state.status is ParcelStatus.OUT_FOR_DELIVERY
    assert delivery.id != package.id
    assert _holder(engine, "msg:two#0").id not in (package.id, delivery.id)
    assert [event for event in fired if event[0] == EVENT_DELIVERED] == [
        (EVENT_DELIVERED, delivery.id, "delivered")
    ]


async def test_a_suggested_delivery_accepted_is_told_once(
    hass: HomeAssistant,
) -> None:
    """Putting the shop's delivery with one of two packages tells that the
    package was delivered, but not of the delivery again."""
    add_hub(hass)
    engine = await async_setup_parcels(hass)
    _read(engine, "msg:one#0", 5, carrier="ctt", number="RR482915732PT")
    _read(engine, "msg:two#0", 4, carrier="ctt", number="RR123456785PT")
    _read(engine, "msg:done#0", 1, MailKind.DELIVERED)
    second = _holder(engine, "msg:two#0").id
    delivery = _holder(engine, "msg:done#0").id
    assert delivery != second
    suggestion = next(s for s in engine.suggestions if s.parcel_id == second)
    fired = _listen(hass)

    engine.accept_suggestion(suggestion.id, delivery)
    await hass.async_block_till_done()

    assert _holder(engine, "msg:done#0").id == second
    assert fired == [(EVENT_STATUS_CHANGED, second, "delivered")]


async def test_marking_again_after_an_undo_is_news(hass: HomeAssistant) -> None:
    """Each mark by hand is a delivery of its own."""
    add_hub(hass)
    engine = await async_setup_parcels(hass)
    _read(engine, "msg:one#0", 5, carrier="ctt", number="RR482915732PT")
    parcel = _holder(engine, "msg:one#0").id
    fired = _listen(hass)

    engine.mark_delivered(parcel)
    engine.undo_delivery(parcel)
    engine.mark_delivered(parcel)
    await hass.async_block_till_done()

    told = [
        (EVENT_STATUS_CHANGED, parcel, "delivered"),
        (EVENT_DELIVERED, parcel, "delivered"),
    ]
    assert fired == [*told, (EVENT_STATUS_CHANGED, parcel, "shipped"), *told]


# The shop's own e-mails tell its carrier's news two hours after the carrier,
# without its number; the carrier's name only the shop's agent. By the hours
# ago each was sent.
RELAY_MAILS = {
    "msg:s1#0": (20, MailKind.SHIPPED),
    "msg:c1#0": (6, MailKind.OUT_FOR_DELIVERY),
    "msg:s2#0": (4, MailKind.OUT_FOR_DELIVERY),
    "msg:c2#0": (3, MailKind.DELIVERED),
    "msg:s3#0": (1, MailKind.DELIVERED),
}


def _relay_details(origin_id: str) -> dict[str, Any]:
    """Return what the shop's or the carrier's e-mail says besides its news."""
    if origin_id.startswith("msg:s"):
        return {"label": "lojaexemplo.example", "source": Source.AI, "carrier": "ctt"}
    return {
        "carrier": "ctt_expresso",
        "number": "DS314159268PT",
        "merchant": "Envios Exemplo",
        "label": "cttexpress.com",
        "orders": (),
    }


@pytest.mark.parametrize(
    ("order", "expected"),
    [
        pytest.param(
            ["msg:s1#0", "msg:c1#0", "msg:s2#0", "msg:c2#0", "msg:s3#0"],
            [
                (EVENT_PARCEL_ADDED, "shop", "shipped"),
                (EVENT_PARCEL_ADDED, "package", "out_for_delivery"),
                (EVENT_STATUS_CHANGED, "shop", "out_for_delivery"),
                (EVENT_STATUS_CHANGED, "package", "delivered"),
                (EVENT_DELIVERED, "package", "delivered"),
            ],
            id="as-sent",
        ),
        pytest.param(
            ["msg:s1#0", "msg:s2#0", "msg:s3#0", "msg:c1#0", "msg:c2#0"],
            [
                (EVENT_PARCEL_ADDED, "shop", "shipped"),
                (EVENT_STATUS_CHANGED, "shop", "out_for_delivery"),
                (EVENT_STATUS_CHANGED, "shop", "delivered"),
                (EVENT_DELIVERED, "shop", "delivered"),
                (EVENT_PARCEL_ADDED, "package", "out_for_delivery"),
                (EVENT_STATUS_CHANGED, "package", "delivered"),
            ],
            id="shop-first",
        ),
    ],
)
async def test_a_relayed_delivery_is_told_once(
    hass: HomeAssistant, order: list[str], expected: Fired
) -> None:
    """The shop's parcel joins the carrier's package whose news it told
    again, and automations hear of the delivery once, whichever mailbox is
    read first. The package keeps the carrier's number and delivery time,
    with the shop's name."""
    now = datetime.fromisoformat(NOW)
    add_hub(hass)
    engine = await async_setup_parcels(hass)
    fired = _listen(hass)
    ids: dict[str, str] = {}

    for origin_id in order:
        hours, kind = RELAY_MAILS[origin_id]
        _read(engine, origin_id, hours, kind, **_relay_details(origin_id))
        side = "shop" if origin_id.startswith("msg:s") else "package"
        ids.setdefault(side, _holder(engine, origin_id).id)
    await hass.async_block_till_done()

    [parcel] = engine.data.parcels.values()
    assert parcel.id == ids["package"]
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_RELAY
    state = parcel.state
    assert (state.merchant, state.carrier, state.tracking_number) == (
        "Loja Exemplo",
        "ctt_expresso",
        "DS314159268PT",
    )
    assert state.status is ParcelStatus.DELIVERED
    assert state.status_time == now - timedelta(hours=3)
    names = {pid: side for side, pid in ids.items()}
    assert [(event, names[pid], status) for event, pid, status in fired] == expected


async def test_start_joins_a_relayed_parcel_quietly(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """The first start after the update joins a shop's parcel to the
    carrier's package whose news it told again, which no earlier release
    did. It fires no events, and diagnostics count it."""
    now = datetime.fromisoformat(NOW)
    data = ParcelsData()
    data.engine[REPAIR_KEY] = REPAIR_VERSION
    data.engine[RELEASE_KEY] = {"version": "0.1.28", "changed": 0}
    for origin_id, (hours, kind) in RELAY_MAILS.items():
        details = {"merchant": "Loja Exemplo", "orders": ["001234567890"]}
        details |= _relay_details(origin_id)
        when = now - timedelta(hours=hours)
        apply_contribution(
            data, contribution(origin_id, kind=kind, time=when, **details), when
        )
    assert len(data.parcels) == 2
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)
    fired = _listen(hass)

    engine = await async_setup_parcels(hass)
    await hass.async_block_till_done()

    [parcel] = engine.data.parcels.values()
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_RELAY
    assert fired == []
    assert engine.diagnostics()["relay_links"] == {"made": 1, "suggested": 0}


async def test_stop_ignoring_survives_a_restart(hass: HomeAssistant) -> None:
    """E-mails still to read again when Home Assistant stops are read after.

    Stop ignoring reads the sender's ignored e-mails again one by one. Those
    it hadn't finished are read once the mailboxes were checked again.
    """
    client = FakeMailClient()
    client.add(CTT_MAIL)
    shop = client.add(SHOP_MAIL)
    hub = add_hub(hass)
    add_mailbox(hass)
    fetch = client.async_fetch
    stalled = asyncio.Event()

    async def stall(provider_id: str) -> MailMessage:
        if provider_id == shop.provider_id and not stalled.is_set():
            stalled.set()
            await asyncio.Event().wait()
        return await fetch(provider_id)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        (item,) = engine.data.review.values()
        engine.ignore_domain(SHOP)
        client.relist = True
        with patch.object(client, "async_fetch", stall):
            assert engine.unignore_domain(SHOP) == {"domain": SHOP, "rechecking": 1}
            await stalled.wait()
            assert engine.data.engine[UNIGNORE_REREAD_KEY] == [item.message]

            assert await hass.config_entries.async_reload(hub.entry_id)
            await async_wait_for_mail(hass)
            await async_wait_reprocess(hass)
        engine = get_engine(hass)

    assert engine is not None
    assert engine.data.messages[item.message].state is MessageState.REVIEW
    assert [r.message for r in engine.data.review.values()] == [item.message]
    assert UNIGNORE_REREAD_KEY not in engine.data.engine
    assert client.syncs[-1] is None


async def test_relist_survives_a_restart(hass: HomeAssistant) -> None:
    """A mailbox being read when a sender stopped being ignored lists again.

    It would have looked over its lookback period again once read, for the
    e-mails skipped meanwhile: Home Assistant stopping first changes nothing.
    """
    client = FakeMailClient()
    client.add(CTT_MAIL)
    hub = add_hub(hass)
    mailbox = add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        engine.ignore_domain(SHOP)
        engine.begin_sync(mailbox.entry_id)
        engine.unignore_domain(SHOP)
        client.relist = True

        assert await hass.config_entries.async_reload(hub.entry_id)
        await async_wait_for_mail(hass)
        engine = get_engine(hass)

    assert engine is not None
    assert client.syncs == [None, None]
    assert RELIST_KEY not in engine.data.engine
    assert len(engine.data.parcels) == 1
