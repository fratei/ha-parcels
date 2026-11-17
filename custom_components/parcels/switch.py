"""Switches of Parcels: Live Activities and the daily notification."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .engine import ParcelsEngine
from .entity import ParcelsEntity
from .notifier import Notifier

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NotifierSwitchDescription(SwitchEntityDescription):
    """A switch that turns a part of the notifier on or off."""

    is_on: Callable[[Notifier], bool]
    set_on: Callable[[Notifier, bool], Coroutine[Any, Any, None]]


SWITCHES: tuple[NotifierSwitchDescription, ...] = (
    NotifierSwitchDescription(
        key="live_activities",
        translation_key="live_activities",
        entity_category=EntityCategory.CONFIG,
        is_on=lambda notifier: notifier.live_activities_enabled,
        set_on=lambda notifier, on: notifier.async_set_live_activities(on),
    ),
    NotifierSwitchDescription(
        key="daily_notification",
        translation_key="daily_notification",
        entity_category=EntityCategory.CONFIG,
        is_on=lambda notifier: notifier.daily_notification_enabled,
        set_on=lambda notifier, on: notifier.async_set_daily_notification(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the switches of the hub."""
    engine: ParcelsEngine = entry.runtime_data
    if engine.notifier is None:
        return
    async_add_entities(
        NotifierSwitch(engine, engine.notifier, description) for description in SWITCHES
    )


class NotifierSwitch(ParcelsEntity, SwitchEntity):
    """Turns Live Activities or the persistent notification on or off."""

    entity_description: NotifierSwitchDescription

    def __init__(
        self,
        engine: ParcelsEngine,
        notifier: Notifier,
        description: NotifierSwitchDescription,
    ) -> None:
        """Initialise the switch."""
        super().__init__(engine, description.key)
        self.entity_description = description
        self._notifier = notifier

    @property
    def is_on(self) -> bool:
        """Return True when this part of the notifier is on."""
        return self.entity_description.is_on(self._notifier)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn it on."""
        await self.entity_description.set_on(self._notifier, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn it off."""
        await self.entity_description.set_on(self._notifier, False)
        self.async_write_ha_state()
