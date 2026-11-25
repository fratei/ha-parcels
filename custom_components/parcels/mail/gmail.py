"""Gmail API mail client."""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime
import html
import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from ..const import PROVIDER_GOOGLE
from ..parsers import normalize
from ..parsers.base import MailMessage
from . import ApiClient, MessageMeta, SyncResult, TokenGetter, async_parse, text
from .errors import (
    MAILBOX_ERRORS,
    MailError,
    MailNoMailbox,
    MailNotFound,
    MailServerError,
)

_LOGGER = logging.getLogger(__name__)

GMAIL_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
LIST_PAGE_SIZE = 100
HISTORY_PAGE_SIZE = 500
MAX_PAGES = 20
MAX_METADATA_FETCHES = 200
# Failed header reads of one e-mail before the sync skips it.
META_ATTEMPTS = 3
SKIP_LABELS = frozenset({"TRASH", "SENT", "DRAFT", "CHAT"})
METADATA_HEADERS = ("From", "Subject", "Message-ID", "Date")


def _history_id(value: Any) -> str | None:
    """Return a history ID as a string of digits, or None."""
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return str(value)
    if isinstance(value, str) and value.isdigit() and value.isascii():
        return value
    return None


def _from_millis(value: Any) -> datetime | None:
    """Return an aware UTC datetime from milliseconds since the epoch."""
    try:
        return datetime.fromtimestamp(int(value) / 1000, UTC)
    except TypeError, ValueError, OverflowError, OSError:
        return None


def _parse_date(value: str | None) -> datetime | None:
    """Return a Date header as an aware UTC datetime, or None."""
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except TypeError, ValueError, IndexError, OverflowError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _decoded(name: str, value: str) -> Any:
    """Return a header parsed and decoded from RFC 2047, or None."""
    try:
        return default_policy.header_factory(name, value)
    except Exception:
        return None


def _sender(value: str) -> tuple[str, str]:
    """Return (display name, lowercased address) of a From header."""
    header = _decoded("from", value)
    for address in getattr(header, "addresses", ()):
        addr_spec = str(getattr(address, "addr_spec", "")).strip()
        if "@" in addr_spec and " " not in addr_spec:
            return text(str(getattr(address, "display_name", ""))), addr_spec.lower()
    name, addr = parseaddr(value)
    return (text(name), addr.strip().lower()) if "@" in addr else ("", "")


def _subject(value: str) -> str:
    """Return a decoded Subject header."""
    header = _decoded("subject", value)
    return text(str(header) if header is not None else value)


def _folder(labels: set[str]) -> str:
    """Return the folder name used for an e-mail's labels."""
    if "SPAM" in labels:
        return "junkemail"
    if "INBOX" in labels:
        return "inbox"
    return "archive"


def _labels(item: Mapping[str, Any]) -> set[str]:
    """Return the label IDs of a message resource."""
    labels = item.get("labelIds")
    return (
        {label for label in labels if isinstance(label, str)}
        if isinstance(labels, list)
        else set()
    )


def _decode_raw(raw: str) -> bytes:
    """Decode Gmail's base64url ``raw`` field."""
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def _parse_raw(raw: str, *, mailbox: str, provider_id: str) -> MailMessage:
    """Decode and parse a ``format=raw`` message."""
    return normalize.message_from_bytes(
        _decode_raw(raw),
        mailbox=mailbox,
        provider_id=provider_id,
        provider=PROVIDER_GOOGLE,
    )


class GmailClient(ApiClient):
    """Read a Gmail mailbox: every e-mail except Trash, Sent, Drafts and Chats.

    The cursor is ``{"history_id": str, "pending": [message IDs]}``. While
    the first listing is still in progress it also has ``query`` and
    ``page_token``. ``folder`` is "inbox", "junkemail" (Spam) or "archive".
    """

    provider = PROVIDER_GOOGLE
    no_mailbox_codes = frozenset({"failedprecondition", "failed_precondition"})
    api_disabled_codes = frozenset({"accessnotconfigured", "service_disabled"})
    rate_limit_codes = frozenset(
        {
            "ratelimitexceeded",
            "userratelimitexceeded",
            "dailylimitexceeded",
            "quotaexceeded",
            "resource_exhausted",
            "rate_limit_exceeded",
        }
    )

    def __init__(
        self,
        session: aiohttp.ClientSession,
        get_token: TokenGetter,
        *,
        address: str | None = None,
    ) -> None:
        """Initialise the client with no failed header reads."""
        super().__init__(session, get_token, address=address)
        self._meta_failures: dict[str, int] = {}

    async def _async_profile(self) -> dict[str, Any]:
        """Return the mailbox profile."""
        return await self.async_get_json(f"{GMAIL_URL}/profile")

    async def async_get_address(self) -> str:
        """Return the mailbox address."""
        profile = await self._async_profile()
        address = text(profile.get("emailAddress"))
        if "@" not in address:
            raise MailNoMailbox("the account has no Gmail address")
        self._address = address.lower()
        return self._address

    async def async_sync(
        self,
        cursor: dict[str, Any] | None,
        *,
        lookback: timedelta,
        folders: Sequence[str] = (),
    ) -> SyncResult:
        """Return e-mails added since ``cursor``, or within ``lookback``.

        ``folders`` is ignored: Gmail has labels, not folders. Gmail may
        return e-mails seen before, so the caller deduplicates.
        """
        state: Mapping[str, Any] = cursor if isinstance(cursor, Mapping) else {}
        history_id = _history_id(state.get("history_id"))
        pending = state.get("pending")
        pending_ids = (
            [item for item in pending if isinstance(item, str) and item]
            if isinstance(pending, list)
            else []
        )
        query = state.get("query") if isinstance(state.get("query"), str) else None
        page_token = text(state.get("page_token")) or None
        complete = True

        if history_id is not None and not query:
            try:
                added, history_id, complete = await self._async_history(history_id)
            except MailNotFound:
                _LOGGER.debug("Gmail history ID expired; resyncing")
                history_id = None
            else:
                pending_ids += added
        if history_id is None:
            profile = await self._async_profile()
            if (history_id := _history_id(profile.get("historyId"))) is None:
                raise MailServerError("profile without a history ID")
            since = int((datetime.now(UTC) - lookback).timestamp())
            query = f"after:{since} -in:trash"
            page_token = None
        if query:
            want = MAX_METADATA_FETCHES - len(pending_ids)
            listed, page_token = await self._async_list(query, page_token, want)
            pending_ids += listed
            if page_token is None:
                query = None
            else:
                complete = False

        pending_ids = list(dict.fromkeys(pending_ids))
        batch = pending_ids[:MAX_METADATA_FETCHES]
        rest = pending_ids[MAX_METADATA_FETCHES:]
        messages: list[MessageMeta] = []
        for message_id in batch:
            try:
                meta = await self._async_meta(message_id)
            except MAILBOX_ERRORS:
                raise
            except MailError:
                # The sync fails and is tried again until one e-mail failed
                # META_ATTEMPTS times; that e-mail is then skipped.
                failures = self._meta_failures.pop(message_id, 0) + 1
                if failures < META_ATTEMPTS:
                    self._meta_failures[message_id] = failures
                    raise
                _LOGGER.warning(
                    "Skipping an e-mail whose headers failed to download %d times",
                    failures,
                )
                continue
            self._meta_failures.pop(message_id, None)
            if meta is not None:
                messages.append(meta)

        new_cursor: dict[str, Any] = {"history_id": history_id, "pending": rest}
        if query:
            new_cursor |= {"query": query, "page_token": page_token}
        return SyncResult(
            messages=messages, cursor=new_cursor, complete=complete and not rest
        )

    async def _async_list(
        self, query: str, page_token: str | None, want: int
    ) -> tuple[list[str], str | None]:
        """List message IDs matching ``query`` until ``want`` are found.

        Returns the IDs and the token of the next page, None when done.
        """
        ids: list[str] = []
        for _ in range(MAX_PAGES):
            params = {
                "q": query,
                "includeSpamTrash": "true",
                "maxResults": str(LIST_PAGE_SIZE),
            }
            if page_token:
                params["pageToken"] = page_token
            page = await self.async_get_json(f"{GMAIL_URL}/messages", params=params)
            items = page.get("messages")
            for item in items if isinstance(items, list) else ():
                if isinstance(item, Mapping) and (message_id := text(item.get("id"))):
                    ids.append(message_id)
            page_token = text(page.get("nextPageToken")) or None
            if page_token is None or len(ids) >= want:
                break
        return ids, page_token

    async def _async_history(self, start: str) -> tuple[list[str], str, bool]:
        """Return IDs of e-mails added after history ID ``start``.

        Returns the IDs, the history ID to continue from and whether the
        history was read to the end.
        """
        ids: list[str] = []
        last = start
        page_token: str | None = None
        for _ in range(MAX_PAGES):
            params = {
                "startHistoryId": start,
                "historyTypes": "messageAdded",
                "maxResults": str(HISTORY_PAGE_SIZE),
            }
            if page_token:
                params["pageToken"] = page_token
            page = await self.async_get_json(f"{GMAIL_URL}/history", params=params)
            records = page.get("history")
            for record in records if isinstance(records, list) else ():
                if not isinstance(record, Mapping):
                    continue
                added = record.get("messagesAdded")
                for entry in added if isinstance(added, list) else ():
                    message = (
                        entry.get("message") if isinstance(entry, Mapping) else None
                    )
                    if (
                        not isinstance(message, Mapping)
                        or _labels(message) & SKIP_LABELS
                    ):
                        continue
                    if message_id := text(message.get("id")):
                        ids.append(message_id)
                last = _history_id(record.get("id")) or last
            page_token = text(page.get("nextPageToken")) or None
            if page_token is None:
                return ids, _history_id(page.get("historyId")) or last, True
        return ids, last, False

    async def _async_meta(self, message_id: str) -> MessageMeta | None:
        """Return the headers of one e-mail, or None to skip it."""
        try:
            item = await self.async_get_json(
                f"{GMAIL_URL}/messages/{quote(message_id, safe='')}",
                params=[
                    ("format", "metadata"),
                    *(("metadataHeaders", name) for name in METADATA_HEADERS),
                ],
            )
        except MailNotFound:
            return None
        labels = _labels(item)
        if labels & SKIP_LABELS:
            return None
        headers: dict[str, str] = {}
        payload = item.get("payload")
        raw_headers = payload.get("headers") if isinstance(payload, Mapping) else None
        for header in raw_headers if isinstance(raw_headers, list) else ():
            if not isinstance(header, Mapping):
                continue
            name = text(header.get("name")).lower()
            value = header.get("value")
            if name and isinstance(value, str):
                headers.setdefault(name, value)
        sender_name, sender = _sender(headers.get("from", ""))
        sent = _parse_date(headers.get("date"))
        snippet = item.get("snippet")
        return MessageMeta(
            provider_id=text(item.get("id")) or message_id,
            message_id=text(headers.get("message-id")) or None,
            sender=sender,
            sender_name=sender_name,
            subject=_subject(headers.get("subject", "")),
            received=_from_millis(item.get("internalDate"))
            or sent
            or datetime.now(UTC),
            sent=sent,
            folder=_folder(labels),
            preview=text(html.unescape(snippet)) if isinstance(snippet, str) else "",
        )

    async def async_fetch(self, provider_id: str) -> MailMessage:
        """Download one complete e-mail and normalise it."""
        mailbox = await self._async_mailbox()
        item = await self.async_get_json(
            f"{GMAIL_URL}/messages/{quote(provider_id, safe='')}",
            params={"format": "raw"},
        )
        raw = item.get("raw")
        if not isinstance(raw, str) or not raw:
            raise MailServerError("message without raw content")
        try:
            message = await async_parse(
                len(raw), _parse_raw, raw, mailbox=mailbox, provider_id=provider_id
            )
        except Exception:
            # Malformed e-mails can raise anything, e.g. RecursionError.
            raise MailServerError("message with invalid raw content") from None
        message.received = _from_millis(item.get("internalDate")) or message.received
        return message
