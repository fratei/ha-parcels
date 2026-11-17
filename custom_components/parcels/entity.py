"""Base entities of Parcels."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_PROVIDER,
    DOMAIN,
    NAME,
    PROVIDER_GOOGLE,
    PROVIDER_MICROSOFT,
    SIGNAL_DATA_UPDATED,
)
from .engine import ParcelsEngine

_PROVIDERS: dict[str, tuple[str, str]] = {
    PROVIDER_MICROSOFT: ("Microsoft", "Outlook.com"),
    PROVIDER_GOOGLE: ("Google", "Gmail"),
}


def hub_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the device of the hub entry."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        entry_type=DeviceEntryType.SERVICE,
        name=NAME,
    )


def mailbox_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the device of a mailbox entry, named after its address."""
    manufacturer, model = _PROVIDERS.get(
        str(entry.data.get(CONF_PROVIDER)), (None, None)
    )
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        entry_type=DeviceEntryType.SERVICE,
        name=entry.title,
        manufacturer=manufacturer,
        model=model,
    )


class ParcelsEntity(Entity):
    """An entity of the hub that follows the parcel data."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, engine: ParcelsEngine, key: str) -> None:
        """Initialise the entity of the hub."""
        self.engine = engine
        self._attr_translation_key = key
        self._attr_unique_id = f"{engine.entry.entry_id}_{key}"
        self._attr_device_info = hub_device_info(engine.entry)

    async def async_added_to_hass(self) -> None:
        """Follow the parcel data."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_DATA_UPDATED, self._async_data_updated
            )
        )

    @callback
    def _async_data_updated(self) -> None:
        """Write the new state."""
        self.async_write_ha_state()
