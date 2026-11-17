"""Serve the Parcels cards and load them on every dashboard."""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_URL_PATH

FRONTEND_DIR = Path(__file__).parent / "frontend"
CARDS_FILE = "parcels-cards.js"
DATA_FRONTEND = f"{DOMAIN}_frontend"


def _version(path: Path) -> str:
    """Return a short hash of the file, so browsers fetch a new build."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the cards and add them to every dashboard, once per run."""
    if DATA_FRONTEND in hass.data:
        return
    hass.data[DATA_FRONTEND] = True
    version = await hass.async_add_executor_job(_version, FRONTEND_DIR / CARDS_FILE)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL_PATH, str(FRONTEND_DIR), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{FRONTEND_URL_PATH}/{CARDS_FILE}?v={version}")
