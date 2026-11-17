"""Tests for the Microsoft Graph mail client."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.parcels.mail import MessageMeta, graph as graph_module
from custom_components.parcels.mail.errors import (
    MailAuthError,
    MailError,
    MailNoMailbox,
    MailNotFound,
    MailRateLimited,
    MailServerError,
)
from custom_components.parcels.mail.graph import FETCH_SELECT, META_SELECT, GraphClient
from custom_components.parcels.parsers import normalize
from custom_components.parcels.parsers.base import MailMessage

from .conftest import ACCESS_TOKEN, ADDRESS, LOOKBACK, NOW, async_get_token

GRAPH = "https://graph.microsoft.com/v1.0"
DELTA = GRAPH + "/me/mailFolders/{}/messages/delta"
INBOX_DELTA = DELTA.format("inbox")
JUNK_DELTA = DELTA.format("junkemail")
MESSAGE_URL = f"{GRAPH}/me/messages/AAMkAD1"
RECEIVED = datetime(2026, 11, 16, 9, 12, tzinfo=UTC)
SENT = datetime(2026, 11, 16, 9, 11, 30, tzinfo=UTC)
SECRET = "Synthetic e-mail text"


def item(number: int, **changes: Any) -> dict[str, Any]:
    """Return the headers of a synthetic Graph message."""
    return {
        "id": f"AAMkAD{number}",
        "internetMessageId": f"<{number}.order@shop.example>",
        "subject": f"Order {number}  has shipped",
        "from": {
            "emailAddress": {"name": "Example Shop", "address": "Orders@Shop.Example"}
        },
        "receivedDateTime": "2026-11-16T09:12:00Z",
        "sentDateTime": "2026-11-16T09:11:30Z",
        "bodyPreview": "Your order\r\nis on its way",
    } | changes


def page(
    items: list[dict[str, Any]],
    *,
    folder: str = "inbox",
    next_token: str | None = None,
    delta_token: str | None = None,
) -> dict[str, Any]:
    """Return a delta page linking to the next page or the next sync."""
    data: dict[str, Any] = {"value": items}
    if next_token:
        data["@odata.nextLink"] = f"{DELTA.format(folder)}?$skiptoken={next_token}"
    if delta_token:
        data["@odata.deltaLink"] = f"{DELTA.format(folder)}?$deltatoken={delta_token}"
    return data


def ids(messages: list[MessageMeta]) -> list[str]:
    """Return the provider IDs of messages."""
    return [message.provider_id for message in messages]


async def test_get_address(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The address is read from the profile and the mailbox is checked."""
    client = GraphClient(async_get_clientsession(hass), async_get_token)
    aioclient_mock.get(
        f"{GRAPH}/me", json={"mail": None, "userPrincipalName": "Alex@Example.com"}
    )
    aioclient_mock.get(f"{GRAPH}/me/mailFolders/inbox", json={"id": "inbox-id"})

    assert await client.async_get_address() == ADDRESS
    assert client.address == ADDRESS
    _, profile_url, _, headers = aioclient_mock.mock_calls[0]
    assert profile_url.query["$select"] == "mail,userPrincipalName"
    assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"


@pytest.mark.parametrize(
    ("profile", "inbox"),
    [
        ({"json": {"mail": None, "userPrincipalName": "alex"}}, {"json": {}}),
        ({"json": {"mail": ADDRESS}}, {"status": 404}),
        (
            {"json": {"mail": ADDRESS}},
            {"status": 404, "json": {"error": {"code": "MailboxNotEnabledForRESTAPI"}}},
        ),
        (
            {
                "status": 400,
                "json": {"error": {"code": "MailboxNotSupportedForRESTAPI"}},
            },
            {"json": {}},
        ),
    ],
)
async def test_get_address_without_mailbox(
    graph_client: GraphClient,
    aioclient_mock: AiohttpClientMocker,
    profile: dict[str, Any],
    inbox: dict[str, Any],
) -> None:
    """Accounts without an Outlook.com mailbox are reported as such."""
    aioclient_mock.get(f"{GRAPH}/me", **profile)
    aioclient_mock.get(f"{GRAPH}/me/mailFolders/inbox", **inbox)

    with pytest.raises(MailNoMailbox):
        await graph_client.async_get_address()


async def test_first_sync(
    graph_client: GraphClient,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The first sync reads both folders from the lookback, page by page."""
    freezer.move_to(NOW)
    aioclient_mock.get(
        f"{INBOX_DELTA}?$skiptoken=p2",
        json=page(
            [item(2), {"id": "AAMkAD9", "@removed": {"reason": "deleted"}}],
            delta_token="d-inbox",
        ),
    )
    aioclient_mock.get(
        INBOX_DELTA, json=page([item(1), {"subject": "No ID"}], next_token="p2")
    )
    aioclient_mock.get(
        JUNK_DELTA, json=page([item(3)], folder="junkemail", delta_token="d-junk")
    )

    result = await graph_client.async_sync(None, lookback=LOOKBACK)

    assert ids(result.messages) == ["AAMkAD1", "AAMkAD2", "AAMkAD3"]
    assert [message.folder for message in result.messages] == [
        "inbox",
        "inbox",
        "junkemail",
    ]
    assert result.complete
    assert result.cursor == {
        "folders": {
            "inbox": {"delta_link": f"{INBOX_DELTA}?$deltatoken=d-inbox"},
            "junkemail": {"delta_link": f"{JUNK_DELTA}?$deltatoken=d-junk"},
        }
    }
    assert result.messages[0] == MessageMeta(
        provider_id="AAMkAD1",
        message_id="<1.order@shop.example>",
        sender="orders@shop.example",
        sender_name="Example Shop",
        subject="Order 1 has shipped",
        received=RECEIVED,
        sent=SENT,
        folder="inbox",
        preview="Your order is on its way",
    )
    _, url, _, headers = aioclient_mock.mock_calls[0]
    assert url.query["$select"] == META_SELECT
    assert url.query["$filter"] == "receivedDateTime ge 2026-10-18T12:00:00Z"
    assert headers["Prefer"] == "odata.maxpagesize=50"
    assert [call[1].path for call in aioclient_mock.mock_calls] == [
        "/v1.0/me/mailFolders/inbox/messages/delta",
        "/v1.0/me/mailFolders/inbox/messages/delta",
        "/v1.0/me/mailFolders/junkemail/messages/delta",
    ]


async def test_incremental_sync(
    graph_client: GraphClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Later syncs follow the stored delta links."""
    cursor = {
        "folders": {
            "inbox": {"delta_link": f"{INBOX_DELTA}?$deltatoken=d1"},
            "junkemail": {"delta_link": f"{JUNK_DELTA}?$deltatoken=j1"},
        }
    }
    aioclient_mock.get(
        f"{INBOX_DELTA}?$deltatoken=d1", json=page([item(4)], delta_token="d2")
    )
    aioclient_mock.get(
        f"{JUNK_DELTA}?$deltatoken=j1",
        json=page([], folder="junkemail", delta_token="j2"),
    )

    result = await graph_client.async_sync(cursor, lookback=LOOKBACK)

    assert ids(result.messages) == ["AAMkAD4"]
    assert result.complete
    assert result.cursor == {
        "folders": {
            "inbox": {"delta_link": f"{INBOX_DELTA}?$deltatoken=d2"},
            "junkemail": {"delta_link": f"{JUNK_DELTA}?$deltatoken=j2"},
        }
    }
    assert all("$filter" not in call[1].query for call in aioclient_mock.mock_calls)


async def test_sync_selected_folders(
    graph_client: GraphClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Only the chosen folders are read, each once."""
    aioclient_mock.get(
        JUNK_DELTA, json=page([item(5)], folder="junkemail", delta_token="j1")
    )

    result = await graph_client.async_sync(
        None, lookback=LOOKBACK, folders=["junkemail", "junkemail"]
    )

    assert ids(result.messages) == ["AAMkAD5"]
    assert list(result.cursor["folders"]) == ["junkemail"]
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    ("status", "code"), [(410, "SyncStateNotFound"), (400, "resyncRequired")]
)
async def test_expired_delta_link_restarts(
    graph_client: GraphClient,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    code: str,
) -> None:
    """An expired delta link restarts the folder from the lookback."""
    cursor = {"folders": {"inbox": {"delta_link": f"{INBOX_DELTA}?$deltatoken=old"}}}
    aioclient_mock.get(
        f"{INBOX_DELTA}?$deltatoken=old",
        status=status,
        json={"error": {"code": code, "message": SECRET}},
    )
    aioclient_mock.get(INBOX_DELTA, json=page([item(6)], delta_token="new"))

    result = await graph_client.async_sync(cursor, lookback=LOOKBACK, folders=["inbox"])

    assert ids(result.messages) == ["AAMkAD6"]
    assert result.complete
    assert result.cursor == {
        "folders": {"inbox": {"delta_link": f"{INBOX_DELTA}?$deltatoken=new"}}
    }
    assert "$filter" in aioclient_mock.mock_calls[1][1].query


async def test_page_cap_resumes(
    graph_client: GraphClient,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A capped sync stores the next page and continues there next time."""
    monkeypatch.setattr(graph_module, "MAX_PAGES_PER_FOLDER", 2)
    aioclient_mock.get(
        f"{INBOX_DELTA}?$skiptoken=p2", json=page([item(2)], next_token="p3")
    )
    aioclient_mock.get(
        f"{INBOX_DELTA}?$skiptoken=p3", json=page([item(3)], delta_token="d1")
    )
    aioclient_mock.get(INBOX_DELTA, json=page([item(1)], next_token="p2"))

    first = await graph_client.async_sync(None, lookback=LOOKBACK, folders=["inbox"])

    assert ids(first.messages) == ["AAMkAD1", "AAMkAD2"]
    assert not first.complete
    assert first.cursor == {
        "folders": {"inbox": {"next_link": f"{INBOX_DELTA}?$skiptoken=p3"}}
    }

    second = await graph_client.async_sync(
        first.cursor, lookback=LOOKBACK, folders=["inbox"]
    )

    assert ids(second.messages) == ["AAMkAD3"]
    assert second.complete
    assert second.cursor == {
        "folders": {"inbox": {"delta_link": f"{INBOX_DELTA}?$deltatoken=d1"}}
    }


async def test_links_outside_graph_are_not_followed(
    graph_client: GraphClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """The token is only ever sent to Graph."""
    cursor = {"folders": {"inbox": {"delta_link": "https://other.example/delta"}}}
    aioclient_mock.get(
        INBOX_DELTA,
        json={"value": [], "@odata.nextLink": "https://other.example/next"},
    )

    with pytest.raises(MailServerError):
        await graph_client.async_sync(cursor, lookback=LOOKBACK, folders=["inbox"])

    assert aioclient_mock.call_count == 1
    assert "$filter" in aioclient_mock.mock_calls[0][1].query


async def test_delta_without_delta_link(
    graph_client: GraphClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """A last page without a delta link is a server error."""
    aioclient_mock.get(INBOX_DELTA, json={"value": [item(1)]})

    with pytest.raises(MailServerError):
        await graph_client.async_sync(None, lookback=LOOKBACK, folders=["inbox"])


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({"status": 401}, MailAuthError),
        (
            {"status": 403, "json": {"error": {"code": "ErrorAccessDenied"}}},
            MailAuthError,
        ),
        ({"status": 404}, MailNotFound),
        ({"status": 500, "json": {"error": {"message": SECRET}}}, MailServerError),
        ({"status": 503, "text": f"<p>{SECRET}</p>"}, MailServerError),
        ({"status": 418}, MailError),
        ({"exc": TimeoutError()}, MailServerError),
        ({"exc": aiohttp.ClientError()}, MailServerError),
        ({"text": SECRET}, MailServerError),
        ({"json": [SECRET]}, MailServerError),
    ],
)
async def test_request_errors(
    graph_client: GraphClient,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    error: type[MailError],
) -> None:
    """Failures map to mail errors that never quote the response."""
    aioclient_mock.get(MESSAGE_URL, **response)

    with pytest.raises(MailError) as exc_info:
        await graph_client.async_fetch("AAMkAD1")

    assert type(exc_info.value) is error
    assert SECRET not in str(exc_info.value)


@pytest.mark.parametrize(("retry_after", "expected"), [("7", 7.0), (None, None)])
async def test_rate_limited(
    graph_client: GraphClient,
    aioclient_mock: AiohttpClientMocker,
    retry_after: str | None,
    expected: float | None,
) -> None:
    """HTTP 429 carries the Retry-After delay."""
    aioclient_mock.get(
        INBOX_DELTA,
        status=429,
        headers={"Retry-After": retry_after} if retry_after else None,
        json={"error": {"code": "ApplicationThrottled"}},
    )

    with pytest.raises(MailRateLimited) as exc_info:
        await graph_client.async_sync(None, lookback=LOOKBACK, folders=["inbox"])

    assert exc_info.value.retry_after == expected


async def test_token_errors_propagate(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A refused token refresh surfaces before any request is made."""

    async def async_refused_token() -> str:
        raise MailAuthError("refused")

    client = GraphClient(
        async_get_clientsession(hass), async_refused_token, address=ADDRESS
    )

    with pytest.raises(MailAuthError):
        await client.async_fetch("AAMkAD1")
    assert aioclient_mock.call_count == 0


FULL_ITEM = item(1) | {
    "replyTo": [
        {"emailAddress": {"name": "Shop Help", "address": "Help@Shop.Example"}}
    ],
    "body": {
        "contentType": "html",
        "content": (
            "<html><body><p>Hello Alex Doe,</p>"
            "<p>Your order has shipped with Example Carrier.</p></body></html>"
        ),
    },
    "internetMessageHeaders": [
        {"name": "Message-ID", "value": "<1.order@shop.example>"},
        {"name": "Content-Language", "value": "en-US"},
    ],
}


async def test_fetch(
    graph_client: GraphClient,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fetch asks for HTML and headers and hands the item to normalize."""
    calls: list[tuple[dict[str, Any], str]] = []

    def message_from_graph(item: dict[str, Any], *, mailbox: str) -> MailMessage:
        calls.append((item, mailbox))
        return MailMessage(
            message_id="<1.order@shop.example>",
            provider_id="AAMkAD1",
            provider="microsoft",
            mailbox=mailbox,
            sender="orders@shop.example",
            sender_name="Example Shop",
            subject="Order 1 has shipped",
            date=SENT,
            text="",
        )

    monkeypatch.setattr(normalize, "message_from_graph", message_from_graph)
    aioclient_mock.get(MESSAGE_URL, json=FULL_ITEM)

    message = await graph_client.async_fetch("AAMkAD1")

    assert calls == [(FULL_ITEM, ADDRESS)]
    assert message.received == RECEIVED
    _, url, _, headers = aioclient_mock.mock_calls[0]
    assert url.query["$select"] == FETCH_SELECT
    assert headers["Prefer"] == 'outlook.body-content-type="html"'


async def test_fetch_normalizes(
    graph_client: GraphClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """A fetched e-mail is normalised by the real parser."""
    aioclient_mock.get(MESSAGE_URL, json=FULL_ITEM)

    message = await graph_client.async_fetch("AAMkAD1")

    assert message.provider == "microsoft"
    assert message.provider_id == "AAMkAD1"
    assert message.mailbox == ADDRESS
    assert message.message_id == "<1.order@shop.example>"
    assert message.sender == "orders@shop.example"
    assert message.reply_to == "help@shop.example"
    assert message.subject == "Order 1 has shipped"
    assert "Your order has shipped with Example Carrier." in message.text
    assert message.received == RECEIVED
    assert message.date == SENT
