"""Binary sensors of Parcels: a delivery today, and mailbox problems."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import summary
from .const import CONF_ENTRY_TYPE, ENTRY_TYPE_MAILBOX
from .coordinator import MailboxCoordinator
from .engine import MailboxRuntime, ParcelsEngine
from .entity import ParcelsEntity, mailbox_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the binary sensors of the hub or of a mailbox."""
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_MAILBOX:
        mailbox: MailboxRuntime = entry.runtime_data
        if mailbox.coordinator is not None:
            async_add_entities([MailboxProblemSensor(mailbox, mailbox.coordinator)])
        return
    engine: ParcelsEngine = entry.runtime_data
    async_add_entities([DeliveryTodaySensor(engine)])


class DeliveryTodaySensor(ParcelsEntity, BinarySensorEntity):
    """On while a parcel that hasn't arrived yet is expected today."""

    def __init__(self, engine: ParcelsEngine) -> None:
        """Initialise the sensor."""
        super().__init__(engine, "delivery_today")

    @property
    def is_on(self) -> bool:
        """Return True when a parcel is expected today."""
        today = summary.today()
        return any(
            summary.arriving_today(parcel.state, today)
            for parcel in self.engine.visible_parcels()
        )


class MailboxProblemSensor(CoordinatorEntity[MailboxCoordinator], BinarySensorEntity):
    """On while a mailbox can't be checked."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, mailbox: MailboxRuntime, coordinator: MailboxCoordinator
    ) -> None:
        """Initialise the sensor of a mailbox."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{mailbox.entry_id}_problem"
        self._attr_device_info = mailbox_device_info(mailbox.entry)

    @property
    def available(self) -> bool:
        """Always report, also while checks fail."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True when the last check failed."""
        return not self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the kind of the last error, without e-mail details."""
        return {"last_error": self.coordinator.last_error}
