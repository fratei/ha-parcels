"""Diagnostics: counts, states and errors, never e-mail content or names."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ADDRESS,
    CONF_ENTRY_TYPE,
    CONF_EXCLUDED_DEVICES,
    CONF_NOTIFY_PERSONS,
    CONF_OWNER,
    CONF_PARCEL_APP_KEY,
    CONF_PARCEL_APP_OWNER,
    CONF_PARCEL_APP_POSTCODE,
    CONF_TEST_DEVICE,
    ENTRY_TYPE_MAILBOX,
)
from .engine import MailboxRuntime, ParcelsEngine

TO_REDACT = {
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    CONF_ADDRESS,
    CONF_OWNER,
    CONF_NOTIFY_PERSONS,
    CONF_EXCLUDED_DEVICES,
    CONF_TEST_DEVICE,
    CONF_PARCEL_APP_KEY,
    CONF_PARCEL_APP_OWNER,
    CONF_PARCEL_APP_POSTCODE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the hub or a mailbox."""
    result: dict[str, Any] = {
        "entry": {
            "title": "**REDACTED**"
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_MAILBOX
            else entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
            "state": entry.state.value,
        }
    }
    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, ParcelsEngine):
        result["engine"] = runtime.diagnostics() if runtime.started else None
        notifier = getattr(runtime, "notifier", None)
        result["notifications"] = notifier.diagnostics() if notifier else None
        tracker = getattr(runtime, "tracker", None)
        result["seventeentrack"] = tracker.diagnostics() if tracker else None
        sync = getattr(runtime, "parcelapp", None)
        result["parcelapp"] = sync.diagnostics() if sync else None
    elif isinstance(runtime, MailboxRuntime):
        coordinator = runtime.coordinator
        result["mailbox"] = {
            "provider": runtime.client.provider,
            "sync": coordinator.diagnostics() if coordinator else None,
        }
    return result
