"""Tests for the application credentials platform."""

from __future__ import annotations

import json
from pathlib import Path
import re

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)
import pytest

from custom_components.parcels import application_credentials
from custom_components.parcels.application_credentials import (
    GoogleAuthImplementation,
    MicrosoftAuthImplementation,
    async_get_auth_implementation,
    async_get_description_placeholders,
    provider_from_client_id,
)

MICROSOFT_CLIENT_ID = "00000000-0000-0000-0000-000000000000"
GOOGLE_CLIENT_ID = "1234-abc.apps.googleusercontent.com"
CLIENT_SECRET = "synthetic-client-secret"


@pytest.mark.parametrize(
    ("client_id", "provider"),
    [
        (MICROSOFT_CLIENT_ID, "microsoft"),
        (GOOGLE_CLIENT_ID, "google"),
        (" 1234-ABC.Apps.GoogleUserContent.com ", "google"),
    ],
)
def test_provider_from_client_id(client_id: str, provider: str) -> None:
    """Google client IDs end in their domain; anything else is Microsoft."""
    assert provider_from_client_id(client_id) == provider


async def test_microsoft_implementation(hass: HomeAssistant) -> None:
    """A GUID client ID signs in to personal Microsoft accounts."""
    implementation = await async_get_auth_implementation(
        hass, "microsoft", ClientCredential(MICROSOFT_CLIENT_ID, CLIENT_SECRET, "Home")
    )

    assert isinstance(implementation, MicrosoftAuthImplementation)
    assert implementation.provider == "microsoft"
    assert implementation.domain == "microsoft"
    assert implementation.name == "Home (Microsoft)"
    assert implementation.client_id == MICROSOFT_CLIENT_ID
    assert implementation.authorize_url == (
        "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
    )
    assert implementation.token_url == (
        "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    )
    assert implementation.extra_authorize_data == {
        "scope": (
            "offline_access https://graph.microsoft.com/Mail.Read"
            " https://graph.microsoft.com/User.Read"
        ),
        "code_challenge": LocalOAuth2ImplementationWithPkce.compute_code_challenge(
            implementation.code_verifier
        ),
        "code_challenge_method": "S256",
    }
    assert implementation.extra_token_resolve_data == {
        "code_verifier": implementation.code_verifier
    }


async def test_google_implementation(hass: HomeAssistant) -> None:
    """A Google client ID signs in to Gmail with offline access."""
    implementation = await async_get_auth_implementation(
        hass, "google", ClientCredential(GOOGLE_CLIENT_ID, CLIENT_SECRET)
    )

    assert isinstance(implementation, GoogleAuthImplementation)
    assert implementation.provider == "google"
    assert implementation.name == f"{GOOGLE_CLIENT_ID} (Google)"
    assert (
        implementation.authorize_url == "https://accounts.google.com/o/oauth2/v2/auth"
    )
    assert implementation.token_url == "https://oauth2.googleapis.com/token"
    assert implementation.extra_authorize_data == {
        "scope": "https://www.googleapis.com/auth/gmail.readonly",
        "code_challenge": LocalOAuth2ImplementationWithPkce.compute_code_challenge(
            implementation.code_verifier
        ),
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    assert implementation.extra_token_resolve_data == {
        "code_verifier": implementation.code_verifier
    }


async def test_each_sign_in_has_its_own_verifier(hass: HomeAssistant) -> None:
    """Every implementation instance gets a new PKCE code verifier."""
    credential = ClientCredential(MICROSOFT_CLIENT_ID, CLIENT_SECRET)
    first = await async_get_auth_implementation(hass, "microsoft", credential)
    second = await async_get_auth_implementation(hass, "microsoft", credential)

    assert first.code_verifier != second.code_verifier


async def test_description_placeholders(hass: HomeAssistant) -> None:
    """The credentials dialog gets its links and Google's branding values."""
    placeholders = await async_get_description_placeholders(hass)

    assert (
        placeholders["redirect_url"] == config_entry_oauth2_flow.MY_AUTH_CALLBACK_PATH
    )
    assert placeholders["redirect_url"] == "https://my.home-assistant.io/redirect/oauth"
    assert all(url.startswith("https://") for url in placeholders.values())

    strings = json.loads(
        (
            Path(application_credentials.__file__).parent / "translations" / "en.json"
        ).read_text(encoding="utf-8")
    )
    description = strings["application_credentials"]["description"]
    assert set(re.findall(r"\{(\w+)\}", description)) == set(placeholders)
    # Hassfest rejects URLs in translations, including ones without a scheme.
    assert not re.search(r"https?://|www\.", description)
