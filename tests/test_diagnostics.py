"""Tests for the diagnostics of the hub and mailbox entries.

Users attach the diagnostics file to public bug reports: it holds counts,
states and error types, never an address, a token, a person or e-mail text.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from http import HTTPStatus
import json
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from custom_components.parcels.config_flow import HUB_DEFAULTS, mailbox_defaults
from custom_components.parcels.const import (
    CONF_EXCLUDED_DEVICES,
    CONF_NOTIFY_PERSONS,
    CONF_OWNER,
    CONF_TEST_DEVICE,
    DEFAULT_INTERVAL_MINUTES,
)
from custom_components.parcels.engine import ParcelsEngine
from custom_components.parcels.mail.errors import MailServerError

from .common import (
    ADDRESS,
    OTHER_OWNER,
    OWNER,
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    load_message,
    patch_mail_clients,
)

REDACTED = "**REDACTED**"
FIXTURES = (
    "carriers/ctt_in_transit_pt.eml",
    "carriers/ctt_locker_ready_pt.eml",
    "shopify/shipped_en.eml",
    "common/unknown_phone_only.eml",
)
PHONE = "synthetic-iphone-device-id"
TABLET = "synthetic-ipad-device-id"
TOKENS = ("synthetic-access-token", "synthetic-refresh-token")
# Details of the e-mails, besides their subjects and senders.
E_MAIL_DETAILS = (
    "RR482915732PT",
    "RH358201962PT",
    "1Z999AA10123456784",
    "Merino Wool Beanie",
    "Waxed Cotton Jacket",
    "Avenida Exemplo 1",
    "Worten",
    "Example Outfitters",
)


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Freeze the clock on the day of the e-mails, in Lisbon."""
    freezer.move_to("2026-11-17 15:00:00+00:00")
    await hass.config.async_set_time_zone("Europe/Lisbon")


@pytest.fixture
def client() -> FakeMailClient:
    """Return Alex's mailbox with shipping e-mails and one from a stranger."""
    client = FakeMailClient()
    for fixture in FIXTURES:
        client.add(fixture)
    return client


@pytest.fixture
def hub(hass: HomeAssistant) -> MockConfigEntry:
    """Add the hub: it notifies Alex and Sam, on all devices but the iPad."""
    return add_hub(
        hass,
        **{
            CONF_NOTIFY_PERSONS: [OWNER, OTHER_OWNER],
            CONF_EXCLUDED_DEVICES: [TABLET],
            CONF_TEST_DEVICE: PHONE,
        },
    )


@pytest.fixture
def mailbox(hass: HomeAssistant, hub: MockConfigEntry) -> MockConfigEntry:
    """Add Alex's mailbox."""
    return add_mailbox(hass)


@pytest.fixture
async def engine(
    hass: HomeAssistant, client: FakeMailClient, mailbox: MockConfigEntry
) -> AsyncGenerator[ParcelsEngine]:
    """Load the entries and read Alex's e-mails."""
    with patch_mail_clients(client):
        yield await async_setup_parcels(hass)


async def async_download(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, entry: MockConfigEntry
) -> dict[str, Any]:
    """Download the diagnostics file of an entry, as a user does."""
    assert await async_setup_component(hass, "diagnostics", {})
    client = await hass_client()
    response = await client.get(f"/api/diagnostics/config_entry/{entry.entry_id}")
    assert response.status == HTTPStatus.OK
    return await response.json()


async def test_hub(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hub: MockConfigEntry,
    mailbox: MockConfigEntry,
    engine: ParcelsEngine,
) -> None:
    """The hub's diagnostics count parcels, e-mails, people and devices."""
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, hub)

    assert diagnostics["entry"] == {
        "title": "Parcels",
        "data": {"entry_type": "hub"},
        "options": {
            **HUB_DEFAULTS,
            CONF_NOTIFY_PERSONS: REDACTED,
            CONF_EXCLUDED_DEVICES: REDACTED,
            CONF_TEST_DEVICE: REDACTED,
        },
        "state": "loaded",
    }
    engine_data = diagnostics["engine"]
    assert engine_data["parcels"] == {
        "in_transit": 1,
        "ready_for_pickup": 1,
        "shipped": 1,
    }
    # The e-mail from a stranger was filtered out.
    assert engine_data["messages"] == {"applied": 3, "filtered": 1}
    assert engine_data["mailboxes"] == {
        mailbox.entry_id: {"provider": "google", "synced": True, "has_cursor": True}
    }
    notifications = diagnostics["notifications"]
    assert notifications["notify_persons"] == 2
    assert notifications["excluded_devices"] == 1
    assert notifications["test_device_set"] is True
    assert diagnostics["seventeentrack"]["tracked"] == 0


async def test_mailbox(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mailbox: MockConfigEntry,
    engine: ParcelsEngine,
) -> None:
    """A mailbox's diagnostics show its provider and how its checks went."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, mailbox) == {
        "entry": {
            "title": REDACTED,
            "data": {
                "auth_implementation": "google",
                "token": REDACTED,
                "entry_type": "mailbox",
                "provider": "google",
                "address": REDACTED,
            },
            "options": {**mailbox_defaults("google"), CONF_OWNER: REDACTED},
            "state": "loaded",
        },
        "mailbox": {
            "provider": "google",
            "sync": {
                "last_update_success": True,
                "last_sync": "2026-11-17T15:00:00+00:00",
                "synced": True,
                "failures": 0,
                "last_error": None,
                "interval_minutes": DEFAULT_INTERVAL_MINUTES,
            },
        },
    }


async def test_nothing_private(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hub: MockConfigEntry,
    mailbox: MockConfigEntry,
    client: FakeMailClient,
    engine: ParcelsEngine,
) -> None:
    """The files hold no address, token, person, device or e-mail text."""
    client.sync_error = MailServerError(f"The mailbox {ADDRESS} is full")
    await mailbox.runtime_data.coordinator.async_refresh()
    messages = [load_message(fixture) for fixture in FIXTURES]
    private = (
        ADDRESS,
        *TOKENS,
        OWNER,
        OTHER_OWNER,
        PHONE,
        TABLET,
        *E_MAIL_DETAILS,
        *(message.subject for message in messages),
        *(message.sender for message in messages),
    )

    files = [await async_download(hass, hass_client, entry) for entry in (hub, mailbox)]

    # The error is in the file, without its message.
    assert files[1]["data"]["mailbox"]["sync"]["last_error"] == "MailServerError"
    for file in files:
        text = json.dumps(file, ensure_ascii=False)
        assert REDACTED in text
        assert [secret for secret in private if secret in text] == []


async def test_unloaded_mailbox(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mailbox: MockConfigEntry,
    engine: ParcelsEngine,
) -> None:
    """A mailbox that isn't loaded shows only its redacted entry."""
    assert await hass.config_entries.async_unload(mailbox.entry_id)
    assert mailbox.state is ConfigEntryState.NOT_LOADED

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, mailbox)

    assert diagnostics == {
        "entry": {
            "title": REDACTED,
            "data": {
                "auth_implementation": "google",
                "token": REDACTED,
                "entry_type": "mailbox",
                "provider": "google",
                "address": REDACTED,
            },
            "options": {**mailbox_defaults("google"), CONF_OWNER: REDACTED},
            "state": "not_loaded",
        }
    }
