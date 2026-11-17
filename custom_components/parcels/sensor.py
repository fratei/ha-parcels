"""Sensors of Parcels: parcel counts, the AI queue and mailbox syncs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import summary
from .const import CONF_ENTRY_TYPE, ENTRY_TYPE_MAILBOX, SIGNAL_AI_UPDATED
from .coordinator import MailboxCoordinator
from .engine import MailboxRuntime, ParcelsEngine
from .entity import ParcelsEntity, mailbox_device_info
from .models import Parcel

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ParcelCountDescription(SensorEntityDescription):
    """A sensor that counts the parcels matching a rule."""

    parcels: Callable[[ParcelsEngine], list[Parcel]]


def _today_rule(rule: Callable[..., bool]) -> Callable[[ParcelsEngine], list[Parcel]]:
    def parcels(engine: ParcelsEngine) -> list[Parcel]:
        return summary.count(engine.visible_parcels(), rule, summary.today())

    return parcels


def _rule(rule: Callable[..., bool]) -> Callable[[ParcelsEngine], list[Parcel]]:
    def parcels(engine: ParcelsEngine) -> list[Parcel]:
        return summary.count(engine.visible_parcels(), rule)

    return parcels


COUNT_SENSORS: tuple[ParcelCountDescription, ...] = (
    ParcelCountDescription(
        key="arriving_today",
        translation_key="arriving_today",
        state_class=SensorStateClass.MEASUREMENT,
        parcels=_today_rule(summary.arriving_today),
    ),
    ParcelCountDescription(
        key="in_transit",
        translation_key="in_transit",
        state_class=SensorStateClass.MEASUREMENT,
        parcels=_rule(summary.in_transit),
    ),
    ParcelCountDescription(
        key="ready_for_pickup",
        translation_key="ready_for_pickup",
        state_class=SensorStateClass.MEASUREMENT,
        parcels=_rule(summary.ready_for_pickup),
    ),
    ParcelCountDescription(
        key="delivered_today",
        translation_key="delivered_today",
        state_class=SensorStateClass.MEASUREMENT,
        parcels=_today_rule(summary.delivered_today),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors of the hub or of a mailbox."""
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_MAILBOX:
        mailbox: MailboxRuntime = entry.runtime_data
        if mailbox.coordinator is not None:
            async_add_entities([MailboxLastSyncSensor(mailbox, mailbox.coordinator)])
        return
    engine: ParcelsEngine = entry.runtime_data
    async_add_entities(
        [
            *(ParcelCountSensor(engine, description) for description in COUNT_SENSORS),
            AIQueueSensor(engine),
        ]
    )


class ParcelCountSensor(ParcelsEntity, SensorEntity):
    """How many parcels match a rule; the parcels are in an attribute."""

    entity_description: ParcelCountDescription
    _unrecorded_attributes = frozenset({"parcels"})

    def __init__(
        self, engine: ParcelsEngine, description: ParcelCountDescription
    ) -> None:
        """Initialise the sensor."""
        super().__init__(engine, description.key)
        self.entity_description = description
        self._parcels: list[Parcel] = []

    @callback
    def _async_compute(self) -> None:
        self._parcels = self.entity_description.parcels(self.engine)

    async def async_added_to_hass(self) -> None:
        """Count the parcels before the first state is written."""
        self._async_compute()
        await super().async_added_to_hass()

    @callback
    def _async_data_updated(self) -> None:
        self._async_compute()
        super()._async_data_updated()

    @property
    def native_value(self) -> int:
        """Return the number of parcels."""
        return len(self._parcels)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the parcels, without item names."""
        return {"parcels": [summary.parcel_attributes(p) for p in self._parcels]}


class AIQueueSensor(ParcelsEntity, SensorEntity):
    """E-mails waiting for the local AI, with its status and today's counts."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, engine: ParcelsEngine) -> None:
        """Initialise the sensor."""
        super().__init__(engine, "ai_queue")

    async def async_added_to_hass(self) -> None:
        """Also follow the AI worker."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_AI_UPDATED, self._async_data_updated
            )
        )

    @property
    def native_value(self) -> int:
        """Return the number of queued e-mails."""
        return self.engine.ai.queue_size

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the AI mode, the worker status and today's counters."""
        return {
            "mode": self.engine.ai_mode.value,
            "status": self.engine.ai.status,
            **dict(self.engine.ai.today()),
        }


class MailboxLastSyncSensor(CoordinatorEntity[MailboxCoordinator], SensorEntity):
    """When a mailbox was last checked successfully."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_sync"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, mailbox: MailboxRuntime, coordinator: MailboxCoordinator
    ) -> None:
        """Initialise the sensor of a mailbox."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{mailbox.entry_id}_last_sync"
        self._attr_device_info = mailbox_device_info(mailbox.entry)

    @property
    def available(self) -> bool:
        """Keep showing the last successful check while checks fail."""
        return self.coordinator.data is not None

    @property
    def native_value(self) -> datetime | None:
        """Return the time of the last successful check."""
        data = self.coordinator.data
        return data.last_sync if data is not None else None
