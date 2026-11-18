"""Tests for the polling coordinator of a mailbox.

Every test loads the hub and a mailbox entry whose API is a FakeMailClient,
then makes the client's sync fail or page to drive the coordinator.
"""

from __future__ import annotations

from collections.abc import Sequence
import dataclasses
from datetime import UTC, datetime, timedelta
import logging
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.parcels.const import DOMAIN, ParcelStatus
from custom_components.parcels.coordinator import (
    FOLLOW_UP,
    MAX_ROUNDS,
    MailboxCoordinator,
)
from custom_components.parcels.dedup import (
    REASON_SAME_MERCHANT_DAY,
    REASON_SAME_MERCHANT_ETA,
)
from custom_components.parcels.engine import ParcelsEngine
from custom_components.parcels.mail import SyncResult
from custom_components.parcels.mail.errors import (
    MailApiDisabled,
    MailAuthError,
    MailCursorExpired,
    MailError,
    MailNoMailbox,
    MailRateLimited,
    MailServerError,
)
from custom_components.parcels.parsers.base import MailMessage
from custom_components.parcels.store import ParcelsStore

from .common import (
    ADDRESS,
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    load_message,
    patch_mail_clients,
)

NOW = "2026-11-17 10:00:00+00:00"
INTERVAL = timedelta(minutes=5)
CTT = "carriers/ctt_in_transit_pt.eml"
# Amazon's e-mail of 17 November: no carrier number, delivery on 19 November.
AMAZON = "amazon/shipped_de.eml"
AMAZON_ORDER = "303-5928471-2039485"
CTT_EXPRESSO = "carriers/ctt_expresso_delivered_pt.eml"
CTT_EXPRESSO_NUMBER = "EA529184065PT"


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on 17 November 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


class PagedClient(FakeMailClient):
    """A mailbox API whose first ``pages`` syncs return partial results."""

    def __init__(self, pages: int) -> None:
        """Initialise an empty mailbox that answers in pages."""
        super().__init__()
        self.pages = pages

    async def async_sync(
        self,
        cursor: dict[str, Any] | None,
        *,
        lookback: timedelta,
        folders: Sequence[str] = (),
    ) -> SyncResult:
        """Return the next page; only the last one is complete."""
        result = await super().async_sync(cursor, lookback=lookback, folders=folders)
        result.complete = len(self.syncs) > self.pages
        return result


class OneByOneClient(PagedClient):
    """A paged mailbox API that lists one e-mail per page, in delivery order."""

    async def async_sync(
        self,
        cursor: dict[str, Any] | None,
        *,
        lookback: timedelta,
        folders: Sequence[str] = (),
    ) -> SyncResult:
        """Return the next page, with at most one e-mail."""
        result = await super().async_sync(cursor, lookback=lookback, folders=folders)
        self.pending[:0] = result.messages[1:]
        del result.messages[1:]
        result.complete = result.complete and not self.pending
        return result


def _amazon_delivered_by_ctt() -> tuple[MailMessage, MailMessage]:
    """Return Amazon's e-mail for an order and CTT Expresso's delivery of it.

    CTT Expresso's e-mail names the shop but not the order, and comes two
    days after Amazon's, on the day Amazon expects the parcel.
    """
    shipped = load_message(AMAZON)
    delivered = load_message(CTT_EXPRESSO)
    text = delivered.text.replace(
        f"O seu envio {CTT_EXPRESSO_NUMBER} foi entregue ontem, 16-11-2026, às 16:05.",
        "O seu envio da loja Amazon foi entregue hoje, 19-11-2026, às 10:40.",
    ).replace("Data de entrega 16-11-2026 16:05", "Data de entrega 19-11-2026 10:40")
    assert "loja Amazon" in text
    assert "19-11-2026 10:40" in text
    delivered = dataclasses.replace(
        delivered,
        message_id="<amazon-delivered@notifications.cttexpress.com>",
        date=datetime(2026, 11, 19, 11, 40, tzinfo=UTC),
        text=text,
    )
    return shipped, delivered


async def _setup(
    hass: HomeAssistant, client: FakeMailClient
) -> tuple[MockConfigEntry, MailboxCoordinator, ParcelsEngine]:
    """Load the hub and a mailbox that reads from ``client``."""
    add_hub(hass)
    mailbox = add_mailbox(hass)
    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
    coordinator = mailbox.runtime_data.coordinator
    assert coordinator is not None
    return mailbox, coordinator, engine


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    """Move the clock and run the timers that are due."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _problem(hass: HomeAssistant, mailbox: MockConfigEntry) -> str:
    """Return the state of the mailbox's problem sensor."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{mailbox.entry_id}_problem"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def _failure(coordinator: MailboxCoordinator) -> UpdateFailed:
    """Return the error of the last refresh."""
    assert not coordinator.last_update_success
    err = coordinator.last_exception
    assert isinstance(err, UpdateFailed)
    return err


async def test_auth_failure_starts_reauth(hass: HomeAssistant) -> None:
    """A rejected token turns the problem sensor on and asks to sign in again."""
    client = FakeMailClient()
    client.sync_error = MailAuthError("401")

    mailbox, coordinator, _ = await _setup(hass, client)

    err = coordinator.last_exception
    assert isinstance(err, ConfigEntryAuthFailed)
    assert err.translation_key == "mailbox_auth_failed"
    assert err.translation_placeholders == {"address": ADDRESS}
    flows = hass.config_entries.flow.async_progress()
    assert [(f["context"]["source"], f["context"]["entry_id"]) for f in flows] == [
        (SOURCE_REAUTH, mailbox.entry_id)
    ]
    assert _problem(hass, mailbox) == "on"
    assert coordinator.diagnostics() == {
        "last_update_success": False,
        "last_sync": None,
        "synced": False,
        "failures": 1,
        "last_error": "auth",
        "interval_minutes": 5.0,
    }


async def test_rate_limit_backs_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A 429 waits twice as long after each failure, up to an hour."""
    client = FakeMailClient()
    mailbox, coordinator, _ = await _setup(hass, client)
    client.sync_error = MailRateLimited()

    delays = []
    for _ in range(6):
        await coordinator.async_refresh()
        err = _failure(coordinator)
        assert err.translation_key == "mailbox_rate_limited"
        delays.append(err.retry_after)
    assert delays == [300, 600, 1200, 2400, 3600, 3600]
    assert coordinator.failures == 6
    assert coordinator.last_error == "MailRateLimited"
    assert _problem(hass, mailbox) == "on"

    # A longer Retry-After from the server wins.
    client.sync_error = MailRateLimited(retry_after=7200)
    await coordinator.async_refresh()
    assert _failure(coordinator).retry_after == 7200

    # The next check waits for the delay.
    syncs = len(client.syncs)
    await _advance(hass, freezer, timedelta(seconds=7199))
    assert len(client.syncs) == syncs
    client.sync_error = None
    await _advance(hass, freezer, timedelta(seconds=1))
    assert len(client.syncs) == syncs + 1
    assert coordinator.last_update_success
    assert (coordinator.failures, coordinator.last_error) == (0, None)
    assert _problem(hass, mailbox) == "off"

    # After a success, the backoff starts over.
    client.sync_error = MailRateLimited()
    await coordinator.async_refresh()
    assert _failure(coordinator).retry_after == 300


@pytest.mark.parametrize(
    ("error", "key", "placeholders"),
    [
        (MailServerError("HTTP 503"), "mailbox_sync_failed", {"error": "HTTP 503"}),
        (MailError(), "mailbox_sync_failed", {"error": "MailError"}),
        (MailNoMailbox(), "mailbox_no_mailbox", None),
        (MailApiDisabled(), "mailbox_api_disabled", None),
    ],
)
async def test_sync_failures(
    hass: HomeAssistant,
    error: MailError,
    key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Other mail errors keep the mailbox loaded and retry with a backoff."""
    client = FakeMailClient()
    client.sync_error = error

    mailbox, coordinator, _ = await _setup(hass, client)

    err = _failure(coordinator)
    assert err.translation_key == key
    assert err.translation_placeholders == placeholders
    assert err.retry_after == INTERVAL.total_seconds()
    assert coordinator.last_error == type(error).__name__
    assert _problem(hass, mailbox) == "on"
    assert hass.config_entries.flow.async_progress() == []


async def test_unexpected_error_hides_its_message(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A bug reports where it happened; its message may quote an e-mail."""
    caplog.set_level(logging.DEBUG)
    client = FakeMailClient()
    client.sync_error = ValueError("Parcel RR123456785PT for Alex Example")

    _, coordinator, _ = await _setup(hass, client)

    err = _failure(coordinator)
    assert err.translation_key == "mailbox_sync_failed"
    assert err.translation_placeholders is not None
    assert err.translation_placeholders["error"].startswith("ValueError in async_sync:")
    assert err.__cause__ is None
    assert err.__suppress_context__
    assert coordinator.last_error == err.translation_placeholders["error"]
    assert "RR123456785PT" not in caplog.text


async def test_expired_cursor_resyncs(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An expired cursor is dropped; the sync 30 s later starts over."""
    client = FakeMailClient()
    meta = client.add(CTT)
    mailbox, coordinator, engine = await _setup(hass, client)
    assert engine.data.cursors[mailbox.entry_id] == {"round": 1}

    client.sync_error = MailCursorExpired("history expired")
    await coordinator.async_refresh()

    err = _failure(coordinator)
    assert err.translation_key == "mailbox_sync_failed"
    assert err.translation_placeholders == {"error": "history expired"}
    assert err.retry_after == FOLLOW_UP.total_seconds()
    assert mailbox.entry_id not in engine.data.cursors

    # The full resync reports the e-mail again; it isn't downloaded twice.
    client.sync_error = None
    client.pending.append(meta)
    await _advance(hass, freezer, FOLLOW_UP)

    assert client.syncs[-1] is None
    assert coordinator.last_update_success
    assert engine.data.cursors[mailbox.entry_id] == {"round": len(client.syncs)}
    assert client.fetches == [meta.provider_id]
    assert len(engine.data.parcels) == 1


async def test_large_sync_continues(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A sync stops after MAX_ROUNDS rounds and continues 30 s later."""
    client = PagedClient(pages=MAX_ROUNDS + 1)
    client.add(CTT)

    mailbox, coordinator, engine = await _setup(hass, client)

    # Each round continues from the cursor of the round before.
    assert client.syncs == [None, *({"round": n} for n in range(1, MAX_ROUNDS))]
    assert engine.data.cursors[mailbox.entry_id] == {"round": MAX_ROUNDS}
    assert len(engine.data.parcels) == 1
    assert coordinator.data.messages == 1
    assert not coordinator.data.synced
    assert not engine.is_synced(mailbox.entry_id)
    assert coordinator.update_interval == FOLLOW_UP

    await _advance(hass, freezer, FOLLOW_UP - timedelta(seconds=1))
    assert len(client.syncs) == MAX_ROUNDS

    await _advance(hass, freezer, timedelta(seconds=1))
    assert len(client.syncs) == MAX_ROUNDS + 2
    assert coordinator.data.synced
    assert engine.is_synced(mailbox.entry_id)
    assert coordinator.update_interval == INTERVAL

    # Back to the normal interval.
    await _advance(hass, freezer, INTERVAL)
    assert len(client.syncs) == MAX_ROUNDS + 3
    assert (
        coordinator.diagnostics()["last_sync"] == coordinator.data.last_sync.isoformat()
    )


async def test_hub_unload_stops_a_sync(hass: HomeAssistant) -> None:
    """A sync ends with its round when the hub unloads; that round isn't saved."""
    client = PagedClient(pages=100)
    mailbox, coordinator, engine = await _setup(hass, client)
    hub = engine.entry
    assert len(client.syncs) == MAX_ROUNDS
    sync = client.async_sync

    async def unload_during_sync(*args: Any, **kwargs: Any) -> SyncResult:
        assert await hass.config_entries.async_unload(hub.entry_id)
        return await sync(*args, **kwargs)

    client.async_sync = unload_during_sync  # type: ignore[method-assign]
    client.add(CTT)
    with patch("custom_components.parcels.HUB_WAIT", 0):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert len(client.syncs) == MAX_ROUNDS + 1
    assert not engine.started
    # The next engine reads that round again, from the saved cursor.
    stored = await ParcelsStore(hass).async_load()
    assert stored.cursors[mailbox.entry_id] == {"round": MAX_ROUNDS}
    assert stored.parcels == {}
    assert mailbox.state is ConfigEntryState.SETUP_RETRY


async def test_refresh_while_the_hub_stops(hass: HomeAssistant) -> None:
    """A refresh between the hub's stop and the mailbox reload doesn't sync."""
    client = FakeMailClient()
    mailbox, coordinator, engine = await _setup(hass, client)

    # The hub's unload stops the engine before it reloads the mailboxes.
    await engine.async_stop()
    await coordinator.async_refresh()

    assert _failure(coordinator).translation_key == "hub_not_loaded"
    assert client.syncs == [None]
    with patch("custom_components.parcels.HUB_WAIT", 0):
        assert await hass.config_entries.async_unload(engine.entry.entry_id)
        await hass.async_block_till_done()
    assert mailbox.state is ConfigEntryState.SETUP_RETRY


async def test_page_is_read_oldest_first(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A page's e-mails are read oldest first, whatever order the API lists.

    The carrier's delivery then finds the shop's parcel open and joins it on
    arrival, before parcels are reconciled.
    """
    freezer.move_to("2026-11-19 12:00:00+00:00")
    shipped, delivered = _amazon_delivered_by_ctt()
    # The sync doesn't finish, so parcels aren't reconciled.
    client = PagedClient(pages=MAX_ROUNDS)
    client.add(delivered, provider_id="delivered")
    client.add(shipped, provider_id="shipped")

    _, coordinator, engine = await _setup(hass, client)

    assert not coordinator.data.synced
    [parcel] = engine.data.parcels.values()
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert state.carrier == "ctt_expresso"
    assert state.tracking_number == CTT_EXPRESSO_NUMBER
    assert state.order_numbers == (AMAZON_ORDER,)
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_ETA


async def test_reconcile_waits_for_the_sync(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Parcels are reconciled once a sync has listed every page.

    Here the API lists the delivery a page before the order it's for, so the
    delivery can't join the order on arrival.
    """
    freezer.move_to("2026-11-19 12:00:00+00:00")
    shipped, delivered = _amazon_delivered_by_ctt()
    client = OneByOneClient(pages=MAX_ROUNDS + 1)
    client.add(delivered, provider_id="delivered")
    client.add(shipped, provider_id="shipped")

    _, coordinator, engine = await _setup(hass, client)

    assert client.fetches == ["delivered", "shipped"]
    assert not coordinator.data.synced
    assert len(engine.data.parcels) == 2
    # Other changes meanwhile don't reconcile either.
    engine.async_changed()
    assert len(engine.data.parcels) == 2

    await _advance(hass, freezer, FOLLOW_UP)

    assert coordinator.data.synced
    [parcel] = engine.data.parcels.values()
    state = parcel.state
    assert state.tracking_number == CTT_EXPRESSO_NUMBER
    assert state.order_numbers == (AMAZON_ORDER,)
    assert parcel.auto_merged is not None
    assert parcel.auto_merged.reason == REASON_SAME_MERCHANT_DAY
