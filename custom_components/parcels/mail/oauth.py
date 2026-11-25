"""Create mail clients for config entries signed in with OAuth."""

from __future__ import annotations

import asyncio

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestBaseError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import CONF_ADDRESS, CONF_PROVIDER, PROVIDER_GOOGLE, PROVIDER_MICROSOFT
from . import REQUEST_TIMEOUT, MailClient, TokenGetter
from .errors import MailAuthError, MailServerError
from .gmail import GmailClient
from .graph import GraphClient


def create_client(
    provider: str,
    session: aiohttp.ClientSession,
    get_token: TokenGetter,
    *,
    address: str | None = None,
) -> MailClient:
    """Return the mail client of ``provider``.

    Raises ValueError for an unknown provider.
    """
    if provider == PROVIDER_MICROSOFT:
        return GraphClient(session, get_token, address=address)
    if provider == PROVIDER_GOOGLE:
        return GmailClient(session, get_token, address=address)
    raise ValueError(f"Unknown mail provider: {provider}")


def token_getter(oauth_session: config_entry_oauth2_flow.OAuth2Session) -> TokenGetter:
    """Return a token source that refreshes the entry's token when needed.

    The token is refreshed when it expires, or when the API rejected it and
    it hasn't been replaced since. A refused refresh raises MailAuthError
    (Home Assistant has then already started reauthentication); other
    failures, and a refresh that takes longer than a mail request may, raise
    MailServerError.
    """

    async def async_get_token(rejected: str | None = None) -> str:
        token = oauth_session.token
        if rejected is not None and token.get("access_token") == rejected:
            # Home Assistant refreshes only expired tokens: mark it expired.
            entry = oauth_session.config_entry
            oauth_session.hass.config_entries.async_update_entry(
                entry, data={**entry.data, "token": {**token, "expires_at": 0}}
            )
        try:
            # Home Assistant leaves the refresh's timeout to the caller.
            async with asyncio.timeout(REQUEST_TIMEOUT):
                await oauth_session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise MailAuthError("the sign-in was refused; sign in again") from err
        except (OAuth2TokenRequestBaseError, aiohttp.ClientError, TimeoutError) as err:
            raise MailServerError("could not refresh the sign-in") from err
        return str(oauth_session.token["access_token"])

    return async_get_token


async def async_create_entry_client(
    hass: HomeAssistant, entry: ConfigEntry
) -> MailClient:
    """Return the mail client of a mailbox config entry.

    Raises ImplementationUnavailableError (ConfigEntryNotReady) while the
    credentials can't be loaded, and UnknownImplementationError
    (ConfigEntryAuthFailed) when they were deleted.
    """
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    return create_client(
        entry.data[CONF_PROVIDER],
        async_get_clientsession(hass),
        token_getter(oauth_session),
        address=entry.data.get(CONF_ADDRESS),
    )
