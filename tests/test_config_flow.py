"""Tests for the Parcels config and options flows."""

from __future__ import annotations

from collections.abc import Generator
from http import HTTPStatus
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from yarl import URL

from custom_components.parcels import config_flow
from custom_components.parcels.ai import safety
from custom_components.parcels.ai.safety import AICheck
from custom_components.parcels.config_flow import HUB_DEFAULTS, mailbox_defaults
from custom_components.parcels.const import DOMAIN

MICROSOFT_CLIENT_ID = "00000000-0000-0000-0000-000000000000"
GOOGLE_CLIENT_ID = "1234-abc.apps.googleusercontent.com"
CLIENT_SECRET = "synthetic-client-secret"
REDIRECT_URI = "https://example.com/auth/external/callback"
ADDRESS = "alex@example.com"
ACCESS_TOKEN = "synthetic-access-token"
TOKEN = {
    "access_token": ACCESS_TOKEN,
    "refresh_token": "synthetic-refresh-token",
    "token_type": "Bearer",
    "expires_in": 3600,
}

MICROSOFT_AUTHORIZE_URL = (
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
)
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
TOKEN_URLS = {"microsoft": MICROSOFT_TOKEN_URL, "google": GOOGLE_TOKEN_URL}
GRAPH_ME = "https://graph.microsoft.com/v1.0/me"
GRAPH_INBOX = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox"
GMAIL_PROFILE = "https://gmail.googleapis.com/gmail/v1/users/me/profile"

STRINGS = json.loads(
    (Path(config_flow.__file__).parent / "translations" / "en.json").read_text(
        encoding="utf-8"
    )
)

HUB_INPUT: dict[str, Any] = {
    "notify_persons": ["person.alex"],
    "excluded_devices": ["shared-tablet-device-id"],
    "start_time": "07:30:00",
    "cutoff_time": "21:00:00",
    "collapse_threshold": 4,
    "item_names_on_lock_screen": True,
    "pin_on_lock_screen": True,
    "seventeentrack": False,
    "test_mode": False,
    "archive_days": 7,
    "purge_days": 30,
    "ai_mode": "off",
}


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Keep entry setup out of the flow tests."""
    with patch(
        "custom_components.parcels.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def hub_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add the hub entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Parcels",
        unique_id="hub",
        data={"entry_type": "hub"},
        options=dict(HUB_DEFAULTS),
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def credentials(hass: HomeAssistant) -> None:
    """Add a Microsoft and a Google application credential."""
    assert await async_setup_component(hass, "application_credentials", {})
    for client_id, auth_domain in (
        (MICROSOFT_CLIENT_ID, "microsoft"),
        (GOOGLE_CLIENT_ID, "google"),
    ):
        await async_import_client_credential(
            hass, DOMAIN, ClientCredential(client_id, CLIENT_SECRET), auth_domain
        )


def add_mailbox(
    hass: HomeAssistant, provider: str, *, auth_implementation: str | None = None
) -> MockConfigEntry:
    """Add a signed-in mailbox entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=ADDRESS,
        unique_id=ADDRESS,
        data={
            "auth_implementation": auth_implementation or provider,
            "token": {
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "expires_at": 0,
            },
            "entry_type": "mailbox",
            "provider": provider,
            "address": ADDRESS,
        },
        options=mailbox_defaults(provider),
    )
    entry.add_to_hass(hass)
    return entry


async def async_sign_in(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    result: ConfigFlowResult,
    authorize_url: str,
) -> dict[str, str]:
    """Come back from the provider's sign-in page; return the authorize query."""
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    url = URL(result["url"])
    assert str(url.with_query(None)) == authorize_url
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    assert url.query["redirect_uri"] == REDIRECT_URI
    assert url.query["state"] == state
    client = await hass_client_no_auth()
    response = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert response.status == HTTPStatus.OK
    return dict(url.query)


async def async_start_mailbox_flow(
    hass: HomeAssistant, implementation: str
) -> ConfigFlowResult:
    """Start adding a mailbox and pick the credentials of ``implementation``."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": implementation}
    )


@pytest.mark.usefixtures("credentials")
async def test_create_hub(hass: HomeAssistant) -> None:
    """The first entry is the hub, even when credentials exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hub"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Parcels"
    assert result["data"] == {"entry_type": "hub"}
    assert result["options"] == HUB_DEFAULTS
    assert result["description"] == "hub"
    assert result["result"].unique_id == "hub"


@pytest.mark.usefixtures("hub_entry", "current_request_with_host")
async def test_add_mailbox_without_credentials(hass: HomeAssistant) -> None:
    """Adding a mailbox asks for application credentials first."""
    assert await async_setup_component(hass, "application_credentials", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("hub_entry", "credentials", "current_request_with_host")
async def test_add_microsoft_mailbox(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Signing in to a Microsoft account adds its mailbox."""
    aioclient_mock.post(MICROSOFT_TOKEN_URL, json=TOKEN)
    aioclient_mock.get(
        GRAPH_ME,
        json={"mail": "Alex@Example.com", "userPrincipalName": "alex.doe@example.net"},
    )
    aioclient_mock.get(GRAPH_INBOX, json={"id": "inbox-id"})

    result = await async_start_mailbox_flow(hass, "microsoft")
    query = await async_sign_in(
        hass, hass_client_no_auth, result, MICROSOFT_AUTHORIZE_URL
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert query["client_id"] == MICROSOFT_CLIENT_ID
    assert query["scope"] == (
        "offline_access https://graph.microsoft.com/Mail.Read"
        " https://graph.microsoft.com/User.Read"
    )
    assert query["code_challenge_method"] == "S256"
    _, _, token_request, _ = aioclient_mock.mock_calls[0]
    assert token_request["code"] == "abcd"
    assert (
        LocalOAuth2ImplementationWithPkce.compute_code_challenge(
            token_request["code_verifier"]
        )
        == query["code_challenge"]
    )
    assert all(
        headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        for _, _, _, headers in aioclient_mock.mock_calls[1:]
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ADDRESS
    entry = result["result"]
    assert entry.unique_id == ADDRESS
    data = dict(entry.data)
    token = data.pop("token")
    assert token["access_token"] == ACCESS_TOKEN
    assert token["refresh_token"] == TOKEN["refresh_token"]
    assert data == {
        "auth_implementation": "microsoft",
        "entry_type": "mailbox",
        "provider": "microsoft",
        "address": ADDRESS,
    }
    assert entry.options == {
        "lookback_days": 30,
        "interval_minutes": 5,
        "folders": ["inbox", "junkemail"],
    }


@pytest.mark.usefixtures("hub_entry", "credentials", "current_request_with_host")
async def test_add_gmail_mailbox(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Signing in to a Google account adds its Gmail mailbox."""
    aioclient_mock.post(GOOGLE_TOKEN_URL, json=TOKEN)
    aioclient_mock.get(
        GMAIL_PROFILE, json={"emailAddress": "Alex@Example.com", "historyId": "4321"}
    )

    result = await async_start_mailbox_flow(hass, "google")
    query = await async_sign_in(hass, hass_client_no_auth, result, GOOGLE_AUTHORIZE_URL)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert query["client_id"] == GOOGLE_CLIENT_ID
    assert query["scope"] == "https://www.googleapis.com/auth/gmail.readonly"
    assert query["access_type"] == "offline"
    assert query["prompt"] == "consent"
    assert query["code_challenge_method"] == "S256"

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ADDRESS
    entry = result["result"]
    assert entry.unique_id == ADDRESS
    assert entry.data["auth_implementation"] == "google"
    assert entry.data["entry_type"] == "mailbox"
    assert entry.data["provider"] == "google"
    assert entry.data["address"] == ADDRESS
    assert entry.data["token"]["access_token"] == ACCESS_TOKEN
    assert entry.options == {"lookback_days": 30, "interval_minutes": 5}


@pytest.mark.usefixtures("hub_entry", "credentials", "current_request_with_host")
async def test_mailbox_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A mailbox can be added only once."""
    entry = add_mailbox(hass, "microsoft")
    aioclient_mock.post(MICROSOFT_TOKEN_URL, json=TOKEN)
    aioclient_mock.get(GRAPH_ME, json={"mail": ADDRESS})
    aioclient_mock.get(GRAPH_INBOX, json={"id": "inbox-id"})

    result = await async_start_mailbox_flow(hass, "microsoft")
    await async_sign_in(hass, hass_client_no_auth, result, MICROSOFT_AUTHORIZE_URL)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["token"]["access_token"] == "old-access-token"


@pytest.mark.parametrize(
    ("implementation", "responses", "reason"),
    [
        ("microsoft", [(GRAPH_ME, {"status": 500})], "cannot_connect"),
        ("microsoft", [(GRAPH_ME, {"exc": TimeoutError()})], "cannot_connect"),
        ("microsoft", [(GRAPH_ME, {"status": 403})], "missing_permission"),
        (
            "microsoft",
            [(GRAPH_ME, {"json": {"mail": ADDRESS}}), (GRAPH_INBOX, {"status": 404})],
            "no_mailbox",
        ),
        ("microsoft", [(GRAPH_ME, {"exc": RuntimeError()})], "unknown"),
        (
            "google",
            [
                (
                    GMAIL_PROFILE,
                    {
                        "status": 403,
                        "json": {
                            "error": {"errors": [{"reason": "accessNotConfigured"}]}
                        },
                    },
                )
            ],
            "api_disabled",
        ),
        (
            "google",
            [
                (
                    GMAIL_PROFILE,
                    {
                        "status": 400,
                        "json": {"error": {"status": "FAILED_PRECONDITION"}},
                    },
                )
            ],
            "no_mailbox",
        ),
    ],
)
@pytest.mark.usefixtures("hub_entry", "credentials", "current_request_with_host")
async def test_add_mailbox_errors(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    implementation: str,
    responses: list[tuple[str, dict[str, Any]]],
    reason: str,
) -> None:
    """Failures to read the mailbox address abort with a clear reason."""
    aioclient_mock.post(TOKEN_URLS[implementation], json=TOKEN)
    for url, response in responses:
        aioclient_mock.get(url, **response)
    authorize_url = (
        MICROSOFT_AUTHORIZE_URL
        if implementation == "microsoft"
        else GOOGLE_AUTHORIZE_URL
    )

    result = await async_start_mailbox_flow(hass, implementation)
    await async_sign_in(hass, hass_client_no_auth, result, authorize_url)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert reason in STRINGS["config"]["abort"]
    assert not hass.config_entries.async_entries(DOMAIN)[1:]


@pytest.mark.usefixtures("hub_entry", "credentials", "current_request_with_host")
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Signing in again to the same account stores the new token."""
    entry = add_mailbox(hass, "microsoft")
    aioclient_mock.post(MICROSOFT_TOKEN_URL, json=TOKEN)
    aioclient_mock.get(GRAPH_ME, json={"mail": "Alex@Example.com"})
    aioclient_mock.get(GRAPH_INBOX, json={"id": "inbox-id"})

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["address"] == ADDRESS

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await async_sign_in(hass, hass_client_no_auth, result, MICROSOFT_AUTHORIZE_URL)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"]["access_token"] == ACCESS_TOKEN
    assert entry.data["auth_implementation"] == "microsoft"
    assert entry.data["address"] == ADDRESS
    assert entry.data["provider"] == "microsoft"


@pytest.mark.usefixtures("hub_entry", "credentials", "current_request_with_host")
async def test_reauth_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Signing in again with another account changes nothing."""
    entry = add_mailbox(hass, "microsoft")
    aioclient_mock.post(MICROSOFT_TOKEN_URL, json=TOKEN)
    aioclient_mock.get(GRAPH_ME, json={"mail": "sam@example.com"})
    aioclient_mock.get(GRAPH_INBOX, json={"id": "inbox-id"})

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await async_sign_in(hass, hass_client_no_auth, result, MICROSOFT_AUTHORIZE_URL)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert result["description_placeholders"] == {"address": ADDRESS}
    assert entry.data["token"]["access_token"] == "old-access-token"


@pytest.mark.usefixtures("hub_entry", "credentials", "current_request_with_host")
async def test_reauth_with_other_provider(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The same address at another provider is a different account."""
    entry = add_mailbox(hass, "microsoft", auth_implementation="removed")
    aioclient_mock.post(GOOGLE_TOKEN_URL, json=TOKEN)
    aioclient_mock.get(GMAIL_PROFILE, json={"emailAddress": ADDRESS, "historyId": "1"})

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_implementation"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "google"}
    )
    await async_sign_in(hass, hass_client_no_auth, result, GOOGLE_AUTHORIZE_URL)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data["auth_implementation"] == "removed"
    assert entry.data["token"]["access_token"] == "old-access-token"


async def test_hub_options(
    hass: HomeAssistant, hub_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hub options are stored after the AI task passed the local-only check."""
    checked: list[str] = []

    async def async_check_ai_task(hass: HomeAssistant, entity_id: str) -> AICheck:
        checked.append(entity_id)
        return AICheck(ok=True, reason="ok", model="llama3.2:3b", host="127.0.0.1")

    monkeypatch.setattr(safety, "async_check_ai_task", async_check_ai_task)
    user_input = HUB_INPUT | {
        "test_mode": True,
        "test_device": "phone-device-id",
        "ai_task_entity": "ai_task.local_ollama",
        "ai_mode": "auto",
    }

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hub"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hub_entry.options == user_input
    assert checked == ["ai_task.local_ollama"]

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], HUB_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hub_entry.options == HUB_INPUT | {"test_device": "phone-device-id"}
    assert checked == ["ai_task.local_ollama"]


@pytest.mark.parametrize(
    ("changes", "errors"),
    [
        ({"test_mode": True}, {"test_device": "test_device_required"}),
        ({"cutoff_time": "07:30:00"}, {"cutoff_time": "cutoff_before_start"}),
        ({"archive_days": 30}, {"purge_days": "purge_before_archive"}),
    ],
)
async def test_hub_options_errors(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    changes: dict[str, Any],
    errors: dict[str, str],
) -> None:
    """Inconsistent hub options are refused."""
    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], HUB_INPUT | changes
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors
    assert set(errors.values()) <= set(STRINGS["options"]["error"])
    assert hub_entry.options == HUB_DEFAULTS


@pytest.mark.parametrize(
    ("reason", "error"),
    [
        ("not_found", "ai_not_found"),
        ("not_ai_task", "ai_not_ai_task"),
        ("not_ollama", "ai_not_ollama"),
        ("no_entry", "ai_no_entry"),
        ("no_model", "ai_no_model"),
        ("cloud_model", "ai_cloud_model"),
        ("remote_host", "ai_remote_host"),
        ("unresolvable", "ai_unresolvable"),
        ("not_implemented", "ai_unknown"),
    ],
)
async def test_hub_options_refuse_ai_task(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
    error: str,
) -> None:
    """AI tasks that fail the local-only check are refused with the reason."""

    async def async_check_ai_task(hass: HomeAssistant, entity_id: str) -> AICheck:
        return AICheck(ok=False, reason=reason)

    monkeypatch.setattr(safety, "async_check_ai_task", async_check_ai_task)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], HUB_INPUT | {"ai_task_entity": "ai_task.cloud_assistant"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"ai_task_entity": error}
    assert error in STRINGS["options"]["error"]


PARCEL_KEY = "synthetic-parcel-key-0001"
PARCEL_DELIVERIES = "https://api.parcel.app/external/deliveries/"
PARCEL_INPUT: dict[str, Any] = {
    "parcel_app_key": PARCEL_KEY,
    "parcel_app_owner": "person.alex",
    "parcel_app_import": True,
    "parcel_app_add": True,
    "parcel_app_everyone": False,
    "parcel_app_daily": 5,
    "parcel_app_postcode": "1000-001",
}


async def test_hub_options_parcel_app(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A Parcel app key is checked once and kept with its settings."""
    hass.config.country = "PT"
    aioclient_mock.get(PARCEL_DELIVERIES, json={"success": True, "deliveries": []})

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        HUB_INPUT
        | PARCEL_INPUT
        | {"parcel_app_key": f" {PARCEL_KEY} ", "parcel_app_postcode": "1000001"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hub_entry.options == HUB_INPUT | PARCEL_INPUT
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][3]["api-key"] == PARCEL_KEY

    # The same key isn't checked again. With adding off, the form hides the
    # settings for adding, and they're kept for when it's turned back on.
    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        HUB_INPUT
        | {
            "parcel_app_key": PARCEL_KEY,
            "parcel_app_import": False,
            "parcel_app_add": False,
            "parcel_app_everyone": True,
            "parcel_app_daily": 20,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hub_entry.options == {
        **HUB_INPUT,
        **{k: v for k, v in PARCEL_INPUT.items() if k != "parcel_app_owner"},
        "parcel_app_import": False,
        "parcel_app_add": False,
    }
    assert aioclient_mock.call_count == 1

    # Clearing the key drops every Parcel app setting.
    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], HUB_INPUT | {"parcel_app_key": "  "}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hub_entry.options == HUB_INPUT
    assert aioclient_mock.call_count == 1


async def test_hub_options_parcel_app_form(
    hass: HomeAssistant, hub_entry: MockConfigEntry
) -> None:
    """The form shows the Parcel app settings once a key is typed."""
    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    schema = result["data_schema"].schema
    visible = {
        key.schema: getattr(key, "visible", None)
        for key in schema
        if key.schema.startswith("parcel_app_")
    }

    key_typed = {"field": "parcel_app_key", "operator": "exists"}
    adding = [key_typed, {"field": "parcel_app_add", "value": True}]
    assert visible == {
        "parcel_app_key": None,
        "parcel_app_owner": key_typed,
        "parcel_app_import": key_typed,
        "parcel_app_add": key_typed,
        "parcel_app_everyone": adding,
        "parcel_app_daily": adding,
        "parcel_app_postcode": adding,
    }
    for field in visible:
        assert field in STRINGS["options"]["step"]["hub"]["data"]
        assert field in STRINGS["options"]["step"]["hub"]["data_description"]


@pytest.mark.parametrize(
    ("changes", "answer", "errors"),
    [
        (
            {"parcel_app_key": "short"},
            None,
            {"parcel_app_key": "parcel_app_key_invalid"},
        ),
        (
            {"parcel_app_postcode": "1000-01"},
            None,
            {"parcel_app_postcode": "parcel_app_postcode_invalid"},
        ),
        (
            {},
            {"json": {"success": False, "error_message": "Invalid API key"}},
            {"parcel_app_key": "parcel_app_key_refused"},
        ),
        (
            {},
            {"status": HTTPStatus.UNAUTHORIZED},
            {"parcel_app_key": "parcel_app_key_refused"},
        ),
    ],
)
async def test_hub_options_parcel_app_errors(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    changes: dict[str, Any],
    answer: dict[str, Any] | None,
    errors: dict[str, str],
) -> None:
    """A malformed or refused key and a malformed postcode are refused."""
    hass.config.country = "PT"
    aioclient_mock.get(
        PARCEL_DELIVERIES,
        **(answer or {"json": {"success": True, "deliveries": []}}),
    )

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], HUB_INPUT | PARCEL_INPUT | changes
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors
    assert set(errors.values()) <= set(STRINGS["options"]["error"])
    assert hub_entry.options == HUB_DEFAULTS
    # Only a well-formed key is sent, and only to check it.
    assert aioclient_mock.call_count == (1 if answer else 0)


@pytest.mark.parametrize(
    "answer",
    [
        {"status": HTTPStatus.TOO_MANY_REQUESTS},
        {"status": HTTPStatus.INTERNAL_SERVER_ERROR},
        {"exc": TimeoutError()},
    ],
)
async def test_hub_options_parcel_app_unreachable(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    answer: dict[str, Any],
) -> None:
    """A key is kept when Parcel can't be asked: the sync checks it later."""
    aioclient_mock.get(PARCEL_DELIVERIES, **answer)

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], HUB_INPUT | PARCEL_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hub_entry.options == HUB_INPUT | PARCEL_INPUT


async def test_hub_options_parcel_app_owner(
    hass: HomeAssistant,
    hub_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The key's user is asked for once mailboxes have owners."""
    aioclient_mock.get(PARCEL_DELIVERIES, json={"success": True, "deliveries": []})
    without_owner = {k: v for k, v in PARCEL_INPUT.items() if k != "parcel_app_owner"}

    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], HUB_INPUT | without_owner
    )
    await hass.async_block_till_done()

    # Without owners, every mailbox is the key user's.
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hub_entry.options == HUB_INPUT | without_owner

    mailbox = add_mailbox(hass, "google")
    hass.config_entries.async_update_entry(
        mailbox, options={**mailbox.options, "owner": "person.sam"}
    )
    result = await hass.config_entries.options.async_init(hub_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], HUB_INPUT | without_owner
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"parcel_app_owner": "parcel_app_owner_required"}
    assert "parcel_app_owner_required" in STRINGS["options"]["error"]


async def test_microsoft_mailbox_options(hass: HomeAssistant) -> None:
    """Microsoft mailboxes choose their folders."""
    entry = add_mailbox(hass, "microsoft")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mailbox"
    assert result["description_placeholders"] == {"address": ADDRESS}
    assert "folders" in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"folders": [], "lookback_days": 30, "interval_minutes": 5}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"folders": "no_folders"}
    assert "no_folders" in STRINGS["options"]["error"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "owner": "person.alex",
            "folders": ["junkemail", "inbox"],
            "lookback_days": 14,
            "interval_minutes": 10,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        "owner": "person.alex",
        "folders": ["inbox", "junkemail"],
        "lookback_days": 14,
        "interval_minutes": 10,
    }


async def test_gmail_mailbox_options(hass: HomeAssistant) -> None:
    """Gmail mailboxes have no folder choice."""
    entry = add_mailbox(hass, "google")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "folders" not in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"lookback_days": 60, "interval_minutes": 15}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"lookback_days": 60, "interval_minutes": 15}
