"""Fixtures for the mailbox API client tests.

All data is synthetic: the mailbox is ``alex@example.com`` and senders use
``example`` domains.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.parcels.mail.gmail import GmailClient
from custom_components.parcels.mail.graph import GraphClient

ADDRESS = "alex@example.com"
ACCESS_TOKEN = "synthetic-access-token"
LOOKBACK = timedelta(days=30)
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
LOOKBACK_START = NOW - LOOKBACK


async def async_get_token() -> str:
    """Return a fixed access token."""
    return ACCESS_TOKEN


@pytest.fixture
async def graph_client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> GraphClient:
    """Return a Graph client whose HTTP requests are mocked."""
    return GraphClient(async_get_clientsession(hass), async_get_token, address=ADDRESS)


@pytest.fixture
async def gmail_client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> GmailClient:
    """Return a Gmail client whose HTTP requests are mocked."""
    return GmailClient(async_get_clientsession(hass), async_get_token, address=ADDRESS)
