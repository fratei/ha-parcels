"""The Parcels integration: deliveries read from shipping e-mails.

One hub entry owns the parcels, the notifications and the AI queue. Each
mailbox is its own entry that feeds the hub. The hub's options apply live:
reloading it would leave the mailboxes holding the old engine, so a reload
or unload of the hub reloads the mailboxes too.
"""

from __future__ import annotations

import asyncio

from homeassistant.components import persistent_notification
from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
    ConfigEntryState,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import ConfigType

from .cards import async_register_frontend
from .const import (
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_MAILBOX,
    PERSISTENT_NOTIFICATION_ID,
    SIGNAL_DATA_UPDATED,
)
from .coordinator import MailboxCoordinator
from .engine import MailboxRuntime, ParcelsEngine, get_engine
from .mail.oauth import async_create_entry_client
from .notifier import Notifier
from .services import async_setup_services
from .seventeentrack import SeventeenTrackSync
from .store import ParcelsStore
from .websocket import async_setup_websocket

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

HUB_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.SENSOR,
    Platform.SWITCH,
]
MAILBOX_PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

# A mailbox waits this long for the hub, which loads at the same time.
HUB_WAIT = 30.0
# The hub states a mailbox waits through.
_HUB_CHANGING = {
    ConfigEntryState.NOT_LOADED,
    ConfigEntryState.SETUP_IN_PROGRESS,
    ConfigEntryState.UNLOAD_IN_PROGRESS,
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services, WebSocket commands and dashboard cards."""
    async_setup_services(hass)
    async_setup_websocket(hass)
    await async_register_frontend(hass)
    return True


def _is_mailbox(entry: ConfigEntry) -> bool:
    return entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_MAILBOX


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the hub or a mailbox."""
    if _is_mailbox(entry):
        return await _async_setup_mailbox(hass, entry)
    return await _async_setup_hub(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the hub or a mailbox."""
    if _is_mailbox(entry):
        return await hass.config_entries.async_unload_platforms(
            entry, MAILBOX_PLATFORMS
        )
    return await _async_unload_hub(hass, entry)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete what the hub or a mailbox stored."""
    if _is_mailbox(entry):
        if (engine := get_engine(hass)) is not None:
            engine.async_forget_mailbox(entry.entry_id)
        return
    persistent_notification.async_dismiss(hass, PERSISTENT_NOTIFICATION_ID)
    registry = ir.async_get(hass)
    for domain, issue_id in list(registry.issues):
        if domain == DOMAIN:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
    await ParcelsStore(hass).async_remove()


# -- Hub -------------------------------------------------------------------


async def _async_setup_hub(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    engine = ParcelsEngine(hass, entry)
    await engine.async_start()
    notifier = Notifier(hass, entry, engine)
    tracker = SeventeenTrackSync(engine)
    engine.notifier = notifier
    engine.tracker = tracker
    entry.runtime_data = engine
    try:
        await hass.config_entries.async_forward_entry_setups(entry, HUB_PLATFORMS)
        await notifier.async_start()
    except BaseException:
        await notifier.async_stop()
        await engine.async_stop()
        raise
    tracker.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_hub_updated))
    # Mailboxes that gave up waiting for the hub don't wait for their retry.
    for other in hass.config_entries.async_entries(DOMAIN):
        if _is_mailbox(other) and other.state is ConfigEntryState.SETUP_RETRY:
            hass.config_entries.async_schedule_reload(other.entry_id)
    return True


async def _async_hub_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply changed hub options without a reload."""
    engine: ParcelsEngine = entry.runtime_data
    engine.ai.wake()
    if engine.tracker is not None:
        engine.tracker.reconfigure()
    if engine.notifier is not None:
        engine.notifier.async_parcels_changed()
    async_dispatcher_send(hass, SIGNAL_DATA_UPDATED)


async def _async_unload_hub(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    engine: ParcelsEngine = entry.runtime_data
    if not await hass.config_entries.async_unload_platforms(entry, HUB_PLATFORMS):
        return False
    if engine.tracker is not None:
        await engine.tracker.async_stop()
    if engine.notifier is not None:
        await engine.notifier.async_stop()
    await engine.async_stop()
    # The mailboxes hold this engine: reload them so they find the next one.
    for other in hass.config_entries.async_loaded_entries(DOMAIN):
        if _is_mailbox(other):
            hass.config_entries.async_schedule_reload(other.entry_id)
    return True


# -- Mailboxes -------------------------------------------------------------


def _hub_entry(hass: HomeAssistant) -> ConfigEntry | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB:
            return entry
    return None


async def _async_wait_for_hub(hass: HomeAssistant) -> ParcelsEngine:
    """Return the hub's engine; it may still be loading."""
    try:
        async with asyncio.timeout(HUB_WAIT):
            while True:
                engine = get_engine(hass)
                if engine is not None and engine.started:
                    return engine
                hub = _hub_entry(hass)
                if (
                    hub is None
                    or hub.disabled_by is not None
                    or hub.state not in _HUB_CHANGING
                ):
                    break
                await _async_entry_changed(hass, hub)
    except TimeoutError:
        pass
    raise ConfigEntryNotReady(
        translation_domain=DOMAIN, translation_key="hub_not_loaded"
    )


async def _async_entry_changed(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Wait until an entry changes state or is removed."""
    changed: asyncio.Future[None] = hass.loop.create_future()

    @callback
    def _changed(_change: ConfigEntryChange, other: ConfigEntry) -> None:
        if other.entry_id == entry.entry_id and not changed.done():
            changed.set_result(None)

    remove = async_dispatcher_connect(hass, SIGNAL_CONFIG_ENTRY_CHANGED, _changed)
    try:
        await changed
    finally:
        remove()


async def _async_setup_mailbox(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    engine = await _async_wait_for_hub(hass)
    client = await async_create_entry_client(hass, entry)
    mailbox = MailboxRuntime(entry, client)
    coordinator = MailboxCoordinator(hass, engine, mailbox)
    mailbox.coordinator = coordinator
    entry.runtime_data = mailbox
    # Poll even when no entity of the mailbox is enabled.
    entry.async_on_unload(coordinator.async_add_listener(lambda: None))
    entry.async_on_unload(engine.async_add_mailbox(mailbox))
    await hass.config_entries.async_forward_entry_setups(entry, MAILBOX_PLATFORMS)
    # The first sync reads up to 30 days of mail: don't hold up the startup.
    # A 401 still starts the reauthentication.
    mailbox.first_sync = entry.async_create_background_task(
        hass, coordinator.async_refresh(), f"{DOMAIN} first sync"
    )
    return True
