"""Application credentials for Outlook.com (Microsoft Graph) and Gmail.

One integration signs in to two providers. The provider of a credential is
told apart by its client ID: Google client IDs end in
``.apps.googleusercontent.com``, Microsoft ones are GUIDs.
"""

from __future__ import annotations

from typing import Any, ClassVar, override

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    MY_AUTH_CALLBACK_PATH,
    LocalOAuth2ImplementationWithPkce,
)

from .const import PROVIDER_GOOGLE, PROVIDER_MICROSOFT

MICROSOFT_AUTHORIZE_URL = (
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
)
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
MICROSOFT_SCOPES = (
    "offline_access",
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/User.Read",
)
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = ("https://www.googleapis.com/auth/gmail.readonly",)
GOOGLE_CLIENT_ID_SUFFIX = ".apps.googleusercontent.com"

MICROSOFT_CONSOLE_URL = (
    "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"
)
GOOGLE_CONSOLE_URL = "https://console.cloud.google.com/apis/credentials"
GMAIL_API_URL = "https://console.cloud.google.com/apis/library/gmail.googleapis.com"
# Branding values of the user's Google app, which Google needs before it can be
# published. Keep the www host: the bare domain redirects, and Google reports it
# as unresponsive.
GOOGLE_BRANDING_HOME_PAGE_URL = "https://www.home-assistant.io"
GOOGLE_BRANDING_PRIVACY_POLICY_URL = "https://www.home-assistant.io/privacy"


def provider_from_client_id(client_id: str) -> str:
    """Return the provider that issued ``client_id``."""
    if client_id.strip().lower().endswith(GOOGLE_CLIENT_ID_SUFFIX):
        return PROVIDER_GOOGLE
    return PROVIDER_MICROSOFT


class ParcelsAuthImplementation(AuthImplementation):
    """Sign-in with PKCE and the scopes of one provider."""

    provider: ClassVar[str]
    label: ClassVar[str]
    scopes: ClassVar[tuple[str, ...]]
    server: ClassVar[AuthorizationServer]

    def __init__(
        self, hass: HomeAssistant, auth_domain: str, credential: ClientCredential
    ) -> None:
        """Initialize the implementation with a new PKCE code verifier."""
        super().__init__(hass, auth_domain, credential, self.server)
        self.code_verifier = LocalOAuth2ImplementationWithPkce.generate_code_verifier()

    @property
    @override
    def name(self) -> str:
        """Return the credential name and the provider."""
        return f"{super().name} ({self.label})"

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Return the scopes and the PKCE challenge."""
        return {
            "scope": " ".join(self.scopes),
            "code_challenge": LocalOAuth2ImplementationWithPkce.compute_code_challenge(
                self.code_verifier
            ),
            "code_challenge_method": "S256",
        }

    @property
    @override
    def extra_token_resolve_data(self) -> dict[str, Any]:
        """Return the PKCE code verifier."""
        return {"code_verifier": self.code_verifier}


class MicrosoftAuthImplementation(ParcelsAuthImplementation):
    """Sign-in to a personal Microsoft account (Outlook.com, Hotmail)."""

    provider = PROVIDER_MICROSOFT
    label = "Microsoft"
    scopes = MICROSOFT_SCOPES
    server = AuthorizationServer(
        authorize_url=MICROSOFT_AUTHORIZE_URL, token_url=MICROSOFT_TOKEN_URL
    )


class GoogleAuthImplementation(ParcelsAuthImplementation):
    """Sign-in to a Google account with offline access to Gmail."""

    provider = PROVIDER_GOOGLE
    label = "Google"
    scopes = GOOGLE_SCOPES
    server = AuthorizationServer(
        authorize_url=GOOGLE_AUTHORIZE_URL, token_url=GOOGLE_TOKEN_URL
    )

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Also ask for a refresh token on every consent."""
        return super().extra_authorize_data | {
            "access_type": "offline",
            "prompt": "consent",
        }


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> ParcelsAuthImplementation:
    """Return the sign-in implementation of a credential's provider."""
    if provider_from_client_id(credential.client_id) == PROVIDER_GOOGLE:
        return GoogleAuthImplementation(hass, auth_domain, credential)
    return MicrosoftAuthImplementation(hass, auth_domain, credential)


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return the links shown in the credentials dialog."""
    return {
        "redirect_url": MY_AUTH_CALLBACK_PATH,
        "microsoft_console_url": MICROSOFT_CONSOLE_URL,
        "google_console_url": GOOGLE_CONSOLE_URL,
        "gmail_api_url": GMAIL_API_URL,
        "branding_home_page_url": GOOGLE_BRANDING_HOME_PAGE_URL,
        "branding_privacy_policy_url": GOOGLE_BRANDING_PRIVACY_POLICY_URL,
    }
