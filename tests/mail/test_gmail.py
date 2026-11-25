"""Tests for the Gmail API mail client."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
import threading
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

import custom_components.parcels.mail as mail_module
from custom_components.parcels.mail import MessageMeta, gmail as gmail_module
from custom_components.parcels.mail.errors import (
    MailApiDisabled,
    MailAuthError,
    MailError,
    MailNoMailbox,
    MailRateLimited,
    MailServerError,
)
from custom_components.parcels.mail.gmail import GmailClient
from custom_components.parcels.parsers import normalize
from custom_components.parcels.parsers.base import MailMessage

from .conftest import ADDRESS, LOOKBACK, LOOKBACK_START, NOW, async_get_token

GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
QUERY = f"after:{int(LOOKBACK_START.timestamp())} -in:trash"
RECEIVED = datetime(2026, 11, 16, 9, 12, tzinfo=UTC)
SENT = datetime(2026, 11, 16, 9, 11, 30, tzinfo=UTC)
INTERNAL_DATE = str(int(RECEIVED.timestamp() * 1000))
PROFILE = {"emailAddress": "Alex@Example.com", "historyId": "1000"}

RAW_EMAIL = (
    b"Return-Path: <bounce@shop.example>\r\n"
    b"Authentication-Results: mx.google.com;\r\n"
    b"       dkim=pass header.i=@shop.example header.s=sel1 header.b=AbCd1234;\r\n"
    b"       spf=pass (google.com: domain of bounce@shop.example designates"
    b" 192.0.2.10 as permitted sender) smtp.mailfrom=bounce@shop.example;\r\n"
    b"       dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=shop.example\r\n"
    b"From: =?UTF-8?Q?Loja_Exempl=C3=B3?= <Envios@Shop.Example>\r\n"
    b"To: Alex Doe <alex@example.com>\r\n"
    b"Subject: =?UTF-8?Q?Encomenda_enviada_=E2=9C=93?=\r\n"
    b"Date: Mon, 16 Nov 2026 09:11:30 +0000\r\n"
    b"Message-ID: <m1@shop.example>\r\n"
    b"MIME-Version: 1.0\r\n"
    b"Content-Type: text/html; charset=UTF-8\r\n"
    b"Content-Transfer-Encoding: 8bit\r\n"
    b"\r\n"
    b"<html><body><p>Hello Alex Doe,</p>"
    b"<p>Your order has shipped with Example Carrier.</p></body></html>\r\n"
)


def meta_item(message_id: str, *labels: str) -> dict[str, Any]:
    """Return a synthetic ``format=metadata`` message."""
    return {
        "id": message_id,
        "threadId": f"t{message_id}",
        "labelIds": list(labels or ("INBOX", "UNREAD")),
        "snippet": "Your order &#39;1&#39; has  shipped",
        "internalDate": INTERNAL_DATE,
        "payload": {
            "headers": [
                {
                    "name": "From",
                    "value": "=?UTF-8?Q?Loja_Exempl=C3=B3?= <Envios@Shop.Example>",
                },
                {"name": "Subject", "value": "=?UTF-8?Q?Encomenda_enviada_=E2=9C=93?="},
                {"name": "Message-ID", "value": f"<{message_id}@shop.example>"},
                {"name": "Date", "value": "Mon, 16 Nov 2026 09:11:30 +0000"},
            ]
        },
    }


def added(*messages: tuple[str, tuple[str, ...]], record_id: str) -> dict[str, Any]:
    """Return a history record that adds messages with labels."""
    return {
        "id": record_id,
        "messagesAdded": [
            {"message": {"id": message_id, "labelIds": list(labels)}}
            for message_id, labels in messages
        ],
    }


def ids(messages: list[MessageMeta]) -> list[str]:
    """Return the provider IDs of messages."""
    return [message.provider_id for message in messages]


def paths(aioclient_mock: AiohttpClientMocker) -> list[str]:
    """Return the request paths below ``users/me``."""
    return [
        call[1].path.removeprefix("/gmail/v1/users/me/")
        for call in aioclient_mock.mock_calls
    ]


async def test_get_address(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The address comes from the profile."""
    client = GmailClient(async_get_clientsession(hass), async_get_token)
    aioclient_mock.get(f"{GMAIL}/profile", json=PROFILE)

    assert await client.async_get_address() == ADDRESS
    assert client.address == ADDRESS


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({"json": {"historyId": "1"}}, MailNoMailbox),
        (
            {
                "status": 400,
                "json": {
                    "error": {
                        "code": 400,
                        "status": "FAILED_PRECONDITION",
                        "errors": [{"reason": "failedPrecondition"}],
                    }
                },
            },
            MailNoMailbox,
        ),
        (
            {
                "status": 403,
                "json": {
                    "error": {
                        "code": 403,
                        "status": "PERMISSION_DENIED",
                        "errors": [{"reason": "accessNotConfigured"}],
                        "details": [{"reason": "SERVICE_DISABLED"}],
                    }
                },
            },
            MailApiDisabled,
        ),
        (
            {
                "status": 403,
                "json": {"error": {"errors": [{"reason": "insufficientPermissions"}]}},
            },
            MailAuthError,
        ),
        (
            {
                "status": 403,
                "json": {"error": {"errors": [{"reason": "userRateLimitExceeded"}]}},
            },
            MailRateLimited,
        ),
        ({"status": 401}, MailAuthError),
        ({"status": 502}, MailServerError),
    ],
)
async def test_get_address_errors(
    gmail_client: GmailClient,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    error: type[MailError],
) -> None:
    """Gmail error reasons map to specific mail errors."""
    aioclient_mock.get(f"{GMAIL}/profile", **response)

    with pytest.raises(MailError) as exc_info:
        await gmail_client.async_get_address()

    assert type(exc_info.value) is error


async def test_rate_limited(
    gmail_client: GmailClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """HTTP 429 carries the Retry-After delay."""
    aioclient_mock.get(
        f"{GMAIL}/history",
        status=429,
        headers={"Retry-After": "30"},
        json={"error": {"status": "RESOURCE_EXHAUSTED"}},
    )

    with pytest.raises(MailRateLimited) as exc_info:
        await gmail_client.async_sync(
            {"history_id": "1000", "pending": []}, lookback=LOOKBACK
        )

    assert exc_info.value.retry_after == 30.0


async def test_first_sync(
    gmail_client: GmailClient,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The first sync stores the history ID and lists the lookback."""
    freezer.move_to(NOW)
    aioclient_mock.get(f"{GMAIL}/profile", json=PROFILE)
    aioclient_mock.get(
        f"{GMAIL}/messages",
        params={"pageToken": "p2"},
        json={"messages": [{"id": "m3"}, {"id": "m2"}]},
    )
    aioclient_mock.get(
        f"{GMAIL}/messages",
        json={"messages": [{"id": "m1"}, {"id": "m2"}], "nextPageToken": "p2"},
    )
    aioclient_mock.get(f"{GMAIL}/messages/m1", json=meta_item("m1"))
    aioclient_mock.get(f"{GMAIL}/messages/m2", json=meta_item("m2", "SPAM"))
    aioclient_mock.get(f"{GMAIL}/messages/m3", json=meta_item("m3", "SENT"))

    result = await gmail_client.async_sync(None, lookback=LOOKBACK)

    assert ids(result.messages) == ["m1", "m2"]
    assert [message.folder for message in result.messages] == ["inbox", "junkemail"]
    assert result.complete
    assert result.cursor == {"history_id": "1000", "pending": []}
    assert result.messages[0] == MessageMeta(
        provider_id="m1",
        message_id="<m1@shop.example>",
        sender="envios@shop.example",
        sender_name="Loja Exempló",
        subject="Encomenda enviada ✓",
        received=RECEIVED,
        sent=SENT,
        folder="inbox",
        preview="Your order '1' has shipped",
    )
    assert paths(aioclient_mock) == [
        "profile",
        "messages",
        "messages",
        "messages/m1",
        "messages/m2",
        "messages/m3",
    ]
    listing = aioclient_mock.mock_calls[1][1]
    assert listing.query["q"] == QUERY
    assert listing.query["includeSpamTrash"] == "true"
    assert listing.query["maxResults"] == "100"
    metadata = aioclient_mock.mock_calls[3][1]
    assert metadata.query["format"] == "metadata"
    assert metadata.query.getall("metadataHeaders") == [
        "From",
        "Subject",
        "Message-ID",
        "Date",
    ]


async def test_history_sync(
    gmail_client: GmailClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Later syncs read the history and skip drafts, sent mail and chats."""
    aioclient_mock.get(
        f"{GMAIL}/history",
        params={"pageToken": "h2"},
        json={
            "history": [added(("m6", ("INBOX",)), record_id="1010")],
            "historyId": "1012",
        },
    )
    aioclient_mock.get(
        f"{GMAIL}/history",
        json={
            "history": [
                added(
                    ("m4", ("INBOX", "UNREAD")),
                    ("m5", ("DRAFT",)),
                    ("m7", ("CHAT",)),
                    record_id="1005",
                )
            ],
            "nextPageToken": "h2",
            "historyId": "1012",
        },
    )
    aioclient_mock.get(f"{GMAIL}/messages/m4", json=meta_item("m4"))
    aioclient_mock.get(f"{GMAIL}/messages/m6", json=meta_item("m6"))

    result = await gmail_client.async_sync(
        {"history_id": "1000", "pending": []}, lookback=LOOKBACK
    )

    assert ids(result.messages) == ["m4", "m6"]
    assert result.complete
    assert result.cursor == {"history_id": "1012", "pending": []}
    assert paths(aioclient_mock) == ["history", "history", "messages/m4", "messages/m6"]
    history = aioclient_mock.mock_calls[0][1]
    assert history.query["startHistoryId"] == "1000"
    assert history.query["historyTypes"] == "messageAdded"


async def test_expired_history_restarts(
    gmail_client: GmailClient,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An expired history ID restarts with a lookback listing."""
    freezer.move_to(NOW)
    aioclient_mock.get(
        f"{GMAIL}/history",
        status=404,
        json={"error": {"code": 404, "status": "NOT_FOUND"}},
    )
    aioclient_mock.get(f"{GMAIL}/profile", json=PROFILE | {"historyId": "2000"})
    aioclient_mock.get(f"{GMAIL}/messages", json={"messages": [{"id": "m7"}]})
    aioclient_mock.get(f"{GMAIL}/messages/m7", json=meta_item("m7"))
    aioclient_mock.get(f"{GMAIL}/messages/m8", status=404)

    result = await gmail_client.async_sync(
        {"history_id": "1000", "pending": ["m8"]}, lookback=LOOKBACK
    )

    assert ids(result.messages) == ["m7"]
    assert result.complete
    assert result.cursor == {"history_id": "2000", "pending": []}
    assert aioclient_mock.mock_calls[2][1].query["q"] == QUERY


async def test_metadata_cap_keeps_the_rest_pending(
    gmail_client: GmailClient,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-mails above the per-sync cap are read on the next sync."""
    monkeypatch.setattr(gmail_module, "MAX_METADATA_FETCHES", 2)
    aioclient_mock.get(
        f"{GMAIL}/history",
        params={"startHistoryId": "1001"},
        json={"historyId": "1001"},
    )
    aioclient_mock.get(
        f"{GMAIL}/history",
        json={
            "history": [
                added(*((f"m{n}", ("INBOX",)) for n in (1, 2, 3)), record_id="1001")
            ],
            "historyId": "1001",
        },
    )
    for number in (1, 2, 3):
        aioclient_mock.get(f"{GMAIL}/messages/m{number}", json=meta_item(f"m{number}"))

    first = await gmail_client.async_sync(
        {"history_id": "1000", "pending": []}, lookback=LOOKBACK
    )

    assert ids(first.messages) == ["m1", "m2"]
    assert not first.complete
    assert first.cursor == {"history_id": "1001", "pending": ["m3"]}

    second = await gmail_client.async_sync(first.cursor, lookback=LOOKBACK)

    assert ids(second.messages) == ["m3"]
    assert second.complete
    assert second.cursor == {"history_id": "1001", "pending": []}


async def test_history_page_cap(
    gmail_client: GmailClient,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A capped history read continues from the last record next time."""
    monkeypatch.setattr(gmail_module, "MAX_PAGES", 1)
    aioclient_mock.get(
        f"{GMAIL}/history",
        json={
            "history": [added(("m1", ("INBOX",)), record_id="1004")],
            "nextPageToken": "h2",
            "historyId": "1009",
        },
    )
    aioclient_mock.get(f"{GMAIL}/messages/m1", json=meta_item("m1"))

    result = await gmail_client.async_sync(
        {"history_id": "1000", "pending": []}, lookback=LOOKBACK
    )

    assert ids(result.messages) == ["m1"]
    assert not result.complete
    assert result.cursor == {"history_id": "1004", "pending": []}


async def test_first_listing_resumes(
    gmail_client: GmailClient,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A capped first listing continues with its page token."""
    freezer.move_to(NOW)
    monkeypatch.setattr(gmail_module, "MAX_PAGES", 1)
    aioclient_mock.get(f"{GMAIL}/profile", json=PROFILE)
    aioclient_mock.get(
        f"{GMAIL}/messages",
        params={"pageToken": "p2"},
        json={"messages": [{"id": "m2"}]},
    )
    aioclient_mock.get(
        f"{GMAIL}/messages", json={"messages": [{"id": "m1"}], "nextPageToken": "p2"}
    )
    aioclient_mock.get(f"{GMAIL}/messages/m1", json=meta_item("m1"))
    aioclient_mock.get(f"{GMAIL}/messages/m2", json=meta_item("m2"))

    first = await gmail_client.async_sync(None, lookback=LOOKBACK)

    assert ids(first.messages) == ["m1"]
    assert not first.complete
    assert first.cursor == {
        "history_id": "1000",
        "pending": [],
        "query": QUERY,
        "page_token": "p2",
    }

    second = await gmail_client.async_sync(first.cursor, lookback=LOOKBACK)

    assert ids(second.messages) == ["m2"]
    assert second.complete
    assert second.cursor == {"history_id": "1000", "pending": []}
    assert paths(aioclient_mock) == [
        "profile",
        "messages",
        "messages/m1",
        "messages",
        "messages/m2",
    ]


async def test_fetch(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fetch decodes the raw e-mail and hands it to normalize."""
    raw = b"Subject: Test\r\n\r\n\xfb\xff\xfe"
    calls: list[tuple[bytes, str, str, str]] = []

    def message_from_bytes(
        raw: bytes, *, mailbox: str, provider_id: str, provider: str
    ) -> MailMessage:
        calls.append((raw, mailbox, provider_id, provider))
        return MailMessage(
            message_id="<m1@shop.example>",
            provider_id=provider_id,
            provider=provider,
            mailbox=mailbox,
            sender="envios@shop.example",
            sender_name="",
            subject="Test",
            date=SENT,
            text="",
        )

    monkeypatch.setattr(normalize, "message_from_bytes", message_from_bytes)
    client = GmailClient(async_get_clientsession(hass), async_get_token)
    aioclient_mock.get(f"{GMAIL}/profile", json=PROFILE)
    aioclient_mock.get(
        f"{GMAIL}/messages/m1",
        params={"format": "raw"},
        json={
            "id": "m1",
            "raw": base64.urlsafe_b64encode(raw).decode().rstrip("="),
            "internalDate": INTERNAL_DATE,
        },
    )

    message = await client.async_fetch("m1")

    assert calls == [(raw, ADDRESS, "m1", "google")]
    assert message.received == RECEIVED
    assert paths(aioclient_mock) == ["profile", "messages/m1"]


async def test_fetch_normalizes(
    gmail_client: GmailClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """A fetched e-mail is normalised by the real parser."""
    aioclient_mock.get(
        f"{GMAIL}/messages/m1",
        json={
            "id": "m1",
            "raw": base64.urlsafe_b64encode(RAW_EMAIL).decode(),
            "internalDate": INTERNAL_DATE,
        },
    )

    message = await gmail_client.async_fetch("m1")

    assert message.provider == "google"
    assert message.provider_id == "m1"
    assert message.mailbox == ADDRESS
    assert message.message_id == "<m1@shop.example>"
    assert message.sender == "envios@shop.example"
    assert message.subject == "Encomenda enviada ✓"
    assert "Your order has shipped with Example Carrier." in message.text
    assert message.received == RECEIVED
    assert message.date == SENT
    assert message.auth is not None


async def test_fetch_large_message_parses_off_loop(
    gmail_client: GmailClient,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Large e-mails are parsed in an executor thread."""
    monkeypatch.setattr(mail_module, "OFFLOAD_PARSE_BYTES", 10)
    threads: list[int] = []
    parse = normalize.message_from_bytes

    def message_from_bytes(raw: bytes, **kwargs: Any) -> MailMessage:
        threads.append(threading.get_ident())
        return parse(raw, **kwargs)

    monkeypatch.setattr(normalize, "message_from_bytes", message_from_bytes)
    aioclient_mock.get(
        f"{GMAIL}/messages/m1",
        json={"id": "m1", "raw": base64.urlsafe_b64encode(RAW_EMAIL).decode()},
    )

    message = await gmail_client.async_fetch("m1")

    assert message.sender == "envios@shop.example"
    assert threads
    assert threads[0] != threading.get_ident()


@pytest.mark.parametrize("payload", [{"id": "m1"}, {"id": "m1", "raw": 5}])
async def test_fetch_without_raw(
    gmail_client: GmailClient,
    aioclient_mock: AiohttpClientMocker,
    payload: dict[str, Any],
) -> None:
    """A response without raw content is a server error."""
    aioclient_mock.get(f"{GMAIL}/messages/m1", json=payload)

    with pytest.raises(MailServerError):
        await gmail_client.async_fetch("m1")


def nested_mime(depth: int) -> bytes:
    """Return a made-up e-mail whose body is ``depth`` nested multiparts."""
    inner = b"Content-Type: text/plain; charset=utf-8\r\n\r\nEncomenda enviada.\r\n"
    for level in reversed(range(depth)):
        boundary = b"b%d" % level
        inner = (
            b'Content-Type: multipart/mixed; boundary="%s"\r\n\r\n'
            b"--%s\r\n%s\r\n--%s--\r\n" % (boundary, boundary, inner, boundary)
        )
    return (
        b"From: Loja Exemplo <envios@shop.example>\r\n"
        b"To: alex@example.com\r\n"
        b"Subject: A sua encomenda foi enviada\r\n"
        b"Message-ID: <nested@shop.example>\r\n"
        b"Date: Mon, 16 Nov 2026 09:11:30 +0000\r\n"
        b"MIME-Version: 1.0\r\n" + inner
    )


async def test_fetch_unparseable(
    gmail_client: GmailClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """An e-mail the e-mail parser can't take is a server error."""
    raw = base64.urlsafe_b64encode(nested_mime(1200)).decode().rstrip("=")
    aioclient_mock.get(
        f"{GMAIL}/messages/m1",
        json={"id": "m1", "raw": raw, "internalDate": INTERNAL_DATE},
    )

    with pytest.raises(MailError) as exc_info:
        await gmail_client.async_fetch("m1")

    assert type(exc_info.value) is MailServerError


@pytest.mark.parametrize(
    ("response", "error"),
    [({"status": 500}, MailServerError)],
    ids=["500"],
)
async def test_metadata_failure_skips_the_email_after_three_tries(
    gmail_client: GmailClient,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    response: dict[str, Any],
    error: type[MailError],
) -> None:
    """An e-mail whose headers can't be read stops the sync three times.

    The cursor stays, so the next sync tries it again; the third failure
    skips it and the sync goes on.
    """
    aioclient_mock.get(
        f"{GMAIL}/history",
        json={
            "history": [
                added(
                    ("m4", ("INBOX",)),
                    ("m5", ("INBOX",)),
                    ("m6", ("INBOX",)),
                    record_id="1005",
                )
            ],
            "historyId": "1012",
        },
    )
    aioclient_mock.get(f"{GMAIL}/messages/m4", json=meta_item("m4"))
    aioclient_mock.get(f"{GMAIL}/messages/m5", **response)
    aioclient_mock.get(f"{GMAIL}/messages/m6", json=meta_item("m6"))
    cursor = {"history_id": "1000", "pending": []}

    for _ in range(2):
        with pytest.raises(MailError) as exc_info:
            await gmail_client.async_sync(cursor, lookback=LOOKBACK)
        assert type(exc_info.value) is error
    result = await gmail_client.async_sync(cursor, lookback=LOOKBACK)

    assert ids(result.messages) == ["m4", "m6"]
    assert result.complete
    assert result.cursor == {"history_id": "1012", "pending": []}
    assert paths(aioclient_mock).count("messages/m5") == 3
    assert "m5" not in caplog.text
