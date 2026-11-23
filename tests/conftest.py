"""Shared fixtures for Parcels tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.parcels.ai_worker import AIWorker
from custom_components.parcels.const import CONF_ENTRY_TYPE, DOMAIN, ENTRY_TYPE_MAILBOX

from .ai.common import LOCAL_MODEL, add_ai_task


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request: pytest.FixtureRequest) -> None:
    """Let Home Assistant load the integration in tests that use hass."""
    if "hass" in request.fixturenames:
        request.getfixturevalue("enable_custom_integrations")


@pytest.fixture
async def local_ai(hass: HomeAssistant) -> AsyncIterator[str]:
    """Add a local AI task and return its entity; its queue only fills up.

    The mailbox unloads before the hub at the end, as in the AI's own tests:
    a hub that unloads first reloads it, and it would wait for the hub.
    """

    async def idle(self: AIWorker) -> None:
        return None

    entity_id = add_ai_task(hass, model=LOCAL_MODEL)
    hass.config.components.add("ai_task")
    hass.states.async_set(entity_id, "2026-11-20T09:00:00+00:00")
    with patch.object(AIWorker, "_async_run", idle):
        yield entity_id
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_MAILBOX:
            await hass.config_entries.async_unload(entry.entry_id)
