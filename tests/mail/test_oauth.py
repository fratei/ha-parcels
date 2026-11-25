"""Tests for the mail clients of the mailbox entries signed in with OAuth.

The application credentials, tokens and mailbox are synthetic; the token
endpoints and the mail APIs are mocked.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

from custom_components.parcels.const import DOMAIN
from custom_components.parcels.mail import MailClient
from custom_components.parcels.mail.errors import (
    MailAuthError,
    MailError,
    MailServerError,
)
from custom_components.parcels.mail.gmail import GmailClient
from custom_components.parcels.mail.graph import GraphClient
from custom_components.parcels.mail.oauth import (
    async_create_entry_client,
    create_client,
    token_getter,
)

from ..common import add_mailbox
from .conftest import ACCESS_TOKEN, ADDRESS, async_get_token

MICROSOFT_CLIENT_ID = "00000000-0000-0000-0000-000000000000"
GOOGLE_CLIENT_ID = "1234-abc.apps.googleusercontent.com"
CLIENT_SECRET = "synthetic-client-secret"
REFRESH_TOKEN = "synthetic-refresh-token"
NEW_ACCESS_TOKEN = "synthetic-new-access-token"
NEW_TOKEN = {
    "access_token": NEW_ACCESS_TOKEN,
    "token_type": "Bearer",
    "expires_in": 3600,
}
TOKEN_URLS = {
    "microsoft": "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
    "google": "https://oauth2.googleapis.com/token",
}
GRAPH_ME = "https://graph.microsoft.com/v1.0/me"
GRAPH_INBOX = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox"
GMAIL_PROFILE = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
API_URLS = {"microsoft": [GRAPH_ME, GRAPH_INBOX], "google": [GMAIL_PROFILE]}
API_ANSWERS = {
    GRAPH_ME: {"mail": ADDRESS},
    GRAPH_INBOX: {"id": "synthetic-inbox-id"},
    GMAIL_PROFILE: {"emailAddress": ADDRESS},
}


@pytest.fixture
async def credentials(hass: HomeAssistant) -> None:
    """Import a Microsoft and a Google application credential."""
    assert await async_setup_component(hass, "application_credentials", {})
    for client_id, auth_domain in (
        (MICROSOFT_CLIENT_ID, "microsoft"),
        (GOOGLE_CLIENT_ID, "google"),
    ):
        await async_import_client_credential(
            hass, DOMAIN, ClientCredential(client_id, CLIENT_SECRET), auth_domain
        )


def add_expired_mailbox(hass: HomeAssistant, provider: str) -> MockConfigEntry:
    """Add a mailbox entry whose access token has expired."""
    entry = add_mailbox(hass, provider=provider)
    token = {**entry.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(entry, data={**entry.data, "token": token})
    return entry


def mock_mail_api(aioclient_mock: AiohttpClientMocker, provider: str) -> None:
    """Answer the requests that read the mailbox address."""
    for url in API_URLS[provider]:
        aioclient_mock.get(url, json=API_ANSWERS[url])


def refused_once(
    answer: dict[str, Any],
) -> Callable[[str, URL, Any], Awaitable[AiohttpClientMockResponse]]:
    """Return a mock answer that rejects the token of the first request."""
    calls = 0

    async def respond(method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return AiohttpClientMockResponse(method, url, status=401)
        return AiohttpClientMockResponse(method, url, json=answer)

    return respond


def requests(aioclient_mock: AiohttpClientMocker) -> list[tuple[str, str]]:
    """Return the method and URL, without query, of each request made."""
    return [
        (method, str(url.with_query(None)))
        for method, url, _, _ in aioclient_mock.mock_calls
    ]


def bearer_tokens(aioclient_mock: AiohttpClientMocker) -> list[str]:
    """Return the token each mail API request was signed with."""
    return [
        headers["Authorization"].removeprefix("Bearer ")
        for method, _, _, headers in aioclient_mock.mock_calls
        if method == "GET"
    ]


@pytest.mark.parametrize(
    ("provider", "client_class"),
    [("microsoft", GraphClient), ("google", GmailClient)],
)
async def test_create_client(
    hass: HomeAssistant, provider: str, client_class: type[MailClient]
) -> None:
    """Each provider gets its API client, for the normalized address."""
    client = create_client(
        provider,
        async_get_clientsession(hass),
        async_get_token,
        address=" Alex@Example.com ",
    )

    assert type(client) is client_class
    assert client.provider == provider
    assert client.address == ADDRESS


async def test_create_client_unknown_provider(hass: HomeAssistant) -> None:
    """A provider without an API client is refused."""
    with pytest.raises(ValueError, match="imap"):
        create_client("imap", async_get_clientsession(hass), async_get_token)


@pytest.mark.usefixtures("credentials")
@pytest.mark.parametrize(
    ("provider", "client_class"),
    [("microsoft", GraphClient), ("google", GmailClient)],
)
async def test_entry_client(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    provider: str,
    client_class: type[MailClient],
) -> None:
    """The entry's client signs its requests with the entry's valid token."""
    entry = add_mailbox(hass, provider=provider)
    mock_mail_api(aioclient_mock, provider)

    client = await async_create_entry_client(hass, entry)

    assert type(client) is client_class
    assert client.address == ADDRESS
    assert await client.async_get_address() == ADDRESS
    assert requests(aioclient_mock) == [("GET", url) for url in API_URLS[provider]]
    assert set(bearer_tokens(aioclient_mock)) == {ACCESS_TOKEN}


@pytest.mark.usefixtures("credentials")
@pytest.mark.parametrize("provider", ["microsoft", "google"])
async def test_token_refresh(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, provider: str
) -> None:
    """An expired token is refreshed once, saved, and signs the requests."""
    entry = add_expired_mailbox(hass, provider)
    aioclient_mock.post(TOKEN_URLS[provider], json=NEW_TOKEN)
    mock_mail_api(aioclient_mock, provider)
    client = await async_create_entry_client(hass, entry)

    assert await client.async_get_address() == ADDRESS
    assert await client.async_get_address() == ADDRESS

    api_requests = [("GET", url) for url in API_URLS[provider]]
    assert requests(aioclient_mock) == [
        ("POST", TOKEN_URLS[provider]),
        *api_requests,
        *api_requests,
    ]
    refresh = aioclient_mock.mock_calls[0][2]
    assert refresh["grant_type"] == "refresh_token"
    assert refresh["refresh_token"] == REFRESH_TOKEN
    assert set(bearer_tokens(aioclient_mock)) == {NEW_ACCESS_TOKEN}
    assert entry.data["token"]["access_token"] == NEW_ACCESS_TOKEN


@pytest.mark.usefixtures("credentials")
@pytest.mark.parametrize(
    ("provider", "response"),
    [
        ("microsoft", {"status": 400, "json": {"error": "invalid_grant"}}),
        ("google", {"status": 401, "json": {"error": "invalid_client"}}),
    ],
    ids=["400", "401"],
)
async def test_token_refused(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    provider: str,
    response: dict[str, Any],
) -> None:
    """A refused refresh raises MailAuthError and asks to sign in again."""
    entry = add_expired_mailbox(hass, provider)
    aioclient_mock.post(TOKEN_URLS[provider], **response)
    mock_mail_api(aioclient_mock, provider)
    client = await async_create_entry_client(hass, entry)

    with pytest.raises(MailAuthError):
        await client.async_get_address()
    await hass.async_block_till_done()

    assert requests(aioclient_mock) == [("POST", TOKEN_URLS[provider])]
    assert entry.data["token"]["access_token"] == ACCESS_TOKEN
    assert [
        (flow["context"]["source"], flow["context"]["entry_id"])
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    ] == [(SOURCE_REAUTH, entry.entry_id)]


@pytest.mark.usefixtures("credentials")
@pytest.mark.parametrize(
    "response",
    [
        {"status": 500},
        {"status": 429},
        {"exc": aiohttp.ClientConnectionError()},
        {"exc": TimeoutError()},
        {"json": {"token_type": "Bearer", "expires_in": 3600}},
    ],
    ids=["server_error", "rate_limited", "network", "timeout", "no_token"],
)
async def test_token_refresh_failed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, response: dict[str, Any]
) -> None:
    """A refresh that may work later raises MailServerError, without reauth."""
    entry = add_expired_mailbox(hass, "google")
    aioclient_mock.post(TOKEN_URLS["google"], **response)
    mock_mail_api(aioclient_mock, "google")
    client = await async_create_entry_client(hass, entry)

    with pytest.raises(MailServerError):
        await client.async_get_address()
    await hass.async_block_till_done()

    assert requests(aioclient_mock) == [("POST", TOKEN_URLS["google"])]
    assert entry.data["token"]["access_token"] == ACCESS_TOKEN
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.usefixtures("credentials")
async def test_token_refresh_stalled(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A token endpoint that never answers fails the request after 30 seconds."""
    entry = add_expired_mailbox(hass, "microsoft")
    stalled = asyncio.Event()

    async def stall(method: str, url: URL, data: Any) -> None:
        """Never answer the token request."""
        stalled.set()
        await hass.loop.create_future()

    aioclient_mock.post(TOKEN_URLS["microsoft"], side_effect=stall)
    client = await async_create_entry_client(hass, entry)
    request = asyncio.create_task(client.async_get_address())
    await stalled.wait()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert request.done()
    with pytest.raises(MailServerError):
        request.result()
    assert entry.data["token"]["access_token"] == ACCESS_TOKEN


async def test_entry_client_without_credential(hass: HomeAssistant) -> None:
    """A mailbox whose application credential was deleted must sign in again."""
    assert await async_setup_component(hass, "application_credentials", {})
    entry = add_mailbox(hass, provider="google")

    with pytest.raises(ConfigEntryAuthFailed):
        await async_create_entry_client(hass, entry)


@pytest.mark.usefixtures("credentials")
@pytest.mark.parametrize("provider", ["microsoft", "google"])
async def test_token_rejected(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, provider: str
) -> None:
    """A token the mail API rejects before it expires is refreshed once.

    The request is made again with the new token, and nobody is asked to
    sign in again.
    """
    entry = add_mailbox(hass, provider=provider)
    aioclient_mock.post(TOKEN_URLS[provider], json=NEW_TOKEN)
    first, *others = API_URLS[provider]
    aioclient_mock.get(first, side_effect=refused_once(API_ANSWERS[first]))
    for url in others:
        aioclient_mock.get(url, json=API_ANSWERS[url])
    client = await async_create_entry_client(hass, entry)

    assert await client.async_get_address() == ADDRESS
    await hass.async_block_till_done()

    assert requests(aioclient_mock) == [
        ("GET", first),
        ("POST", TOKEN_URLS[provider]),
        ("GET", first),
        *(("GET", url) for url in others),
    ]
    assert bearer_tokens(aioclient_mock) == [ACCESS_TOKEN] + [NEW_ACCESS_TOKEN] * len(
        API_URLS[provider]
    )
    assert entry.data["token"]["access_token"] == NEW_ACCESS_TOKEN
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.usefixtures("credentials")
async def test_new_token_rejected(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A refreshed token the mail API rejects too is an auth error."""
    entry = add_mailbox(hass, provider="google")
    aioclient_mock.post(TOKEN_URLS["google"], json=NEW_TOKEN)
    aioclient_mock.get(GMAIL_PROFILE, status=401)
    client = await async_create_entry_client(hass, entry)

    with pytest.raises(MailError) as exc_info:
        await client.async_get_address()

    assert type(exc_info.value) is MailAuthError
    assert requests(aioclient_mock) == [
        ("GET", GMAIL_PROFILE),
        ("POST", TOKEN_URLS["google"]),
        ("GET", GMAIL_PROFILE),
    ]


@pytest.mark.usefixtures("credentials")
async def test_rejected_token_already_replaced(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Only a rejection of the current token refreshes it.

    Requests that were rejected together refresh the token once.
    """
    entry = add_mailbox(hass, provider="google")
    aioclient_mock.post(TOKEN_URLS["google"], json=NEW_TOKEN)
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    get_token = token_getter(
        config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    )

    assert await get_token(None) == ACCESS_TOKEN
    assert await get_token("synthetic-older-access-token") == ACCESS_TOKEN
    assert aioclient_mock.call_count == 0
    assert await get_token(ACCESS_TOKEN) == NEW_ACCESS_TOKEN
    assert await get_token(ACCESS_TOKEN) == NEW_ACCESS_TOKEN
    assert requests(aioclient_mock) == [("POST", TOKEN_URLS["google"])]
