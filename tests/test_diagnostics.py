"""Tests for the diagnostics of the hub and mailbox entries.

Users attach the diagnostics file to public bug reports: it holds counts,
states and error types, never an address, a token, a person or e-mail text.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import replace
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
from custom_components.parcels.diagnostics import async_get_config_entry_diagnostics
from custom_components.parcels.engine import ParcelsEngine
from custom_components.parcels.mail.errors import MailServerError
from custom_components.parcels.parsers.auth import parse_authentication_results
from custom_components.parcels.parsers.normalize import message_from_bytes

from .common import (
    ADDRESS,
    EMAIL_FIXTURES,
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
# The shipment in amazon/shipped_recommendations_pt.eml.
AMAZON_SHIPMENT = "Pz6WnT4cR"


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


async def test_parcel_app_options_redacted(hass: HomeAssistant) -> None:
    """The Parcel app key, postcode and person never reach the file."""
    key = "synthetic-parcel-key-0001"
    hub = add_hub(
        hass,
        parcel_app_key=key,
        parcel_app_owner=OWNER,
        parcel_app_add=True,
        parcel_app_postcode="1000-001",
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, hub)

    options = diagnostics["entry"]["options"]
    assert options["parcel_app_key"] == REDACTED
    assert options["parcel_app_owner"] == REDACTED
    assert options["parcel_app_postcode"] == REDACTED
    assert options["parcel_app_add"] is True
    text = json.dumps(diagnostics)
    for secret in (key, OWNER, "1000-001"):
        assert secret not in text


async def test_sender_checks(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hub: MockConfigEntry,
    mailbox: MockConfigEntry,
    client: FakeMailClient,
    engine: ParcelsEngine,
) -> None:
    """An e-mail that failed the sender checks shows how they went.

    Only the shop's domain and the names of the servers that wrote the
    headers appear, so a user can tell why without sharing an address.
    """
    header = "mx.example.net; dkim=pass header.d=example-outfitters.co.uk"
    client.add(
        replace(
            load_message("shopify/shipped_en.eml"),
            provider_id="forged",
            message_id="<forged@example-outfitters.co.uk>",
            auth=parse_authentication_results(header),
            auth_headers=(header,),
        )
    )
    await mailbox.runtime_data.coordinator.async_refresh()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, hub)

    assert diagnostics["engine"]["sender_checks"] == [
        {
            "sender": "example-outfitters.co.uk",
            "reason": "untrusted_authserv",
            "checks": {
                "headers": 1,
                "servers": ["mx.example.net"],
                "used": None,
                "dkim": "",
                "dmarc": "",
                "spf": "",
                "originals": 0,
            },
        }
    ]


async def test_amazon_shipment_ids(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hub: MockConfigEntry,
    mailbox: MockConfigEntry,
) -> None:
    """Amazon's shipment IDs are counted by shape, without their values.

    Paack's ID isn't Amazon's shipment ID, even when they look alike, and
    without the Parcel app nothing links Amazon's shipments to packages.
    """
    freezer.move_to("2026-11-25 09:00:00+00:00")
    raw = (EMAIL_FIXTURES / "carriers/paack_out_for_delivery_pt.eml").read_bytes()
    paack = message_from_bytes(
        raw.replace(b"Rb5Lq2Vm7", AMAZON_SHIPMENT.encode()),
        mailbox=ADDRESS,
        provider_id="paack",
        provider="google",
    )
    client = FakeMailClient()
    client.add("amazon/shipped_recommendations_pt.eml")
    client.add(paack)
    with patch_mail_clients(client):
        await async_setup_parcels(hass)

        # Called directly: eight days on, the test client's token expired.
        diagnostics = await async_get_config_entry_diagnostics(hass, hub)

    engine_data = diagnostics["engine"]
    assert "paack_amazon" not in engine_data
    assert engine_data["amazon_links"] is None
    # Amazon's e-mail gave a shipment ID: only its shape shows.
    assert engine_data["amazon_shipment_ids"] == {
        "amazon.es": {
            "orders": 0,
            "with_id": 1,
            "without_id": 0,
            "shapes": {"len9:Aa0": 1},
        }
    }
    # Paack's e-mail stayed its own parcel.
    assert engine_data["parcels"] == {"shipped": 1, "out_for_delivery": 1}
    assert AMAZON_SHIPMENT not in json.dumps(diagnostics)


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
