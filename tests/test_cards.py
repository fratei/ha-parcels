"""Tests for the dashboard cards: loaded once, from a URL that changes per build."""

from __future__ import annotations

import hashlib
from http import HTTPStatus
from unittest.mock import patch

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, add_extra_js_url
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant.typing import ClientSessionGenerator

from custom_components.parcels.cards import (
    CARDS_FILE,
    FRONTEND_DIR,
    async_register_frontend,
)
from custom_components.parcels.const import DOMAIN, FRONTEND_URL_PATH

from .common import add_hub

CARDS = FRONTEND_DIR / CARDS_FILE


async def test_cards(hass: HomeAssistant, hass_client: ClientSessionGenerator) -> None:
    """Every dashboard loads the cards, which browsers cache until a new build."""
    add_hub(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    version = hashlib.sha256(CARDS.read_bytes()).hexdigest()[:12]
    url = f"{FRONTEND_URL_PATH}/{CARDS_FILE}?v={version}"

    modules = hass.data[DATA_EXTRA_MODULE_URL].urls
    assert [module for module in modules if FRONTEND_URL_PATH in module] == [url]
    client = await hass_client()
    response = await client.get(url)
    assert response.status == HTTPStatus.OK
    assert await response.read() == CARDS.read_bytes()
    assert response.headers["Cache-Control"].startswith("public, max-age=")


async def test_cards_added_once(hass: HomeAssistant) -> None:
    """Reloading Parcels doesn't add the cards to the dashboards again."""
    hub = add_hub(hass)
    with patch(
        "custom_components.parcels.cards.add_extra_js_url", wraps=add_extra_js_url
    ) as add:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert await hass.config_entries.async_reload(hub.entry_id)
        await hass.async_block_till_done()
        await async_register_frontend(hass)

    add.assert_called_once()
