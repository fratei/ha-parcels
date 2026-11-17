"""Helpers for the tests that load the Parcels entries.

``FakeMailClient`` stands in for the Graph and Gmail clients: tests put
e-mails in it and the mailbox coordinator reads them like new mail. All data
is synthetic, as in ``tests/parsers/conftest.py``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
import dataclasses
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import MockConfigEntry

from custom_components.parcels.config_flow import HUB_DEFAULTS, mailbox_defaults
from custom_components.parcels.const import (
    CONF_ADDRESS,
    CONF_ENTRY_TYPE,
    CONF_OWNER,
    CONF_PROVIDER,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_MAILBOX,
)
from custom_components.parcels.engine import MailboxRuntime, ParcelsEngine, get_engine
from custom_components.parcels.mail import MessageMeta, SyncResult
from custom_components.parcels.mail.errors import MailNotFound
from custom_components.parcels.parsers.base import MailMessage
from custom_components.parcels.parsers.normalize import message_from_bytes

EMAIL_FIXTURES = Path(__file__).parent / "fixtures" / "emails"
ADDRESS = "alex@example.com"
OTHER_ADDRESS = "sam@example.net"
OWNER = "person.alex"
OTHER_OWNER = "person.sam"


def load_message(
    relative_path: str, *, mailbox: str = ADDRESS, provider: str = "google"
) -> MailMessage:
    """Load an ``.eml`` fixture, relative to ``fixtures/emails``."""
    path = EMAIL_FIXTURES / relative_path
    return message_from_bytes(
        path.read_bytes(), mailbox=mailbox, provider_id=path.name, provider=provider
    )


def meta_for(message: MailMessage) -> MessageMeta:
    """Return the headers the mail API reports before the download."""
    return MessageMeta(
        provider_id=message.provider_id,
        message_id=message.message_id,
        sender=message.sender,
        sender_name=message.sender_name,
        subject=message.subject,
        received=message.received or message.date,
        sent=message.date,
        preview=message.text[:255],
    )


class FakeMailClient:
    """A mailbox API held in memory.

    ``add`` delivers an e-mail: the next sync reports it and a fetch returns
    it. Set ``sync_error`` or ``fetch_errors`` to make calls fail.
    """

    def __init__(self, provider: str = "google", address: str = ADDRESS) -> None:
        """Initialise an empty mailbox."""
        self.provider = provider
        self.address = address
        self.messages: dict[str, MailMessage] = {}
        self.pending: list[MessageMeta] = []
        self.sync_error: Exception | None = None
        self.fetch_errors: dict[str, Exception] = {}
        self.syncs: list[Mapping[str, Any] | None] = []
        self.fetches: list[str] = []

    def add(
        self, message: MailMessage | str, *, provider_id: str | None = None
    ) -> MessageMeta:
        """Deliver an e-mail, or the ``.eml`` fixture at a relative path."""
        if isinstance(message, str):
            message = load_message(message, mailbox=self.address)
        message = dataclasses.replace(
            message,
            provider_id=provider_id or message.provider_id,
            mailbox=self.address,
            provider=self.provider,
        )
        self.messages[message.provider_id] = message
        meta = meta_for(message)
        self.pending.append(meta)
        return meta

    def delete(self, provider_id: str) -> None:
        """Delete an e-mail: a fetch now raises MailNotFound."""
        self.messages.pop(provider_id, None)

    async def async_get_address(self) -> str:
        """Return the mailbox address."""
        return self.address

    async def async_sync(
        self,
        cursor: dict[str, Any] | None,
        *,
        lookback: timedelta,
        folders: Sequence[str] = (),
    ) -> SyncResult:
        """Return the e-mails delivered since the last sync."""
        self.syncs.append(cursor)
        if self.sync_error is not None:
            raise self.sync_error
        messages, self.pending = self.pending, []
        return SyncResult(
            messages=messages, cursor={"round": len(self.syncs)}, complete=True
        )

    async def async_fetch(self, provider_id: str) -> MailMessage:
        """Return one e-mail."""
        self.fetches.append(provider_id)
        if (error := self.fetch_errors.get(provider_id)) is not None:
            raise error
        try:
            return self.messages[provider_id]
        except KeyError:
            raise MailNotFound("the e-mail was deleted") from None


def add_hub(hass: HomeAssistant, **options: Any) -> MockConfigEntry:
    """Add the hub entry, with the default options plus ``options``."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Parcels",
        unique_id="hub",
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB},
        options={**HUB_DEFAULTS, **options},
    )
    entry.add_to_hass(hass)
    return entry


def add_mailbox(
    hass: HomeAssistant,
    *,
    address: str = ADDRESS,
    provider: str = "google",
    owner: str | None = OWNER,
    **options: Any,
) -> MockConfigEntry:
    """Add a signed-in mailbox entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=address,
        unique_id=address,
        data={
            "auth_implementation": provider,
            "token": {
                "access_token": "synthetic-access-token",
                "refresh_token": "synthetic-refresh-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "expires_at": 4102444800,
            },
            CONF_ENTRY_TYPE: ENTRY_TYPE_MAILBOX,
            CONF_PROVIDER: provider,
            CONF_ADDRESS: address,
        },
        options={
            **mailbox_defaults(provider),
            **({CONF_OWNER: owner} if owner else {}),
            **options,
        },
    )
    entry.add_to_hass(hass)
    return entry


@contextmanager
def patch_mail_clients(*clients: FakeMailClient) -> Iterator[None]:
    """Give each mailbox entry the fake client with the same address."""
    by_address = {client.address: client for client in clients}

    async def create(hass: HomeAssistant, entry: Any) -> FakeMailClient:
        return by_address[entry.data[CONF_ADDRESS]]

    with patch("custom_components.parcels.async_create_entry_client", create):
        yield


async def async_wait_for_mail(hass: HomeAssistant) -> None:
    """Wait until the loaded mailboxes finished their first sync."""
    await hass.async_block_till_done()
    tasks = [
        runtime.first_sync
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if isinstance(runtime := getattr(entry, "runtime_data", None), MailboxRuntime)
        and runtime.first_sync is not None
    ]
    if tasks:
        await asyncio.wait(tasks)
    await hass.async_block_till_done()


async def async_setup_parcels(hass: HomeAssistant) -> ParcelsEngine:
    """Load every Parcels entry and read the mail; return the hub's engine.

    Call it inside ``patch_mail_clients`` when there are mailbox entries,
    and keep the patch active while the mailboxes may reload.
    """
    assert await async_setup_component(hass, DOMAIN, {})
    await async_wait_for_mail(hass)
    engine = get_engine(hass)
    assert engine is not None
    return engine
