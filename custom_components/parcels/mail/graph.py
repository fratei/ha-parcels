"""Microsoft Graph mail client for personal Microsoft accounts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
import logging
from typing import Any
from urllib.parse import quote

from yarl import URL

from ..const import MICROSOFT_FOLDERS, PROVIDER_MICROSOFT
from ..parsers import normalize
from ..parsers.base import MailMessage
from . import ApiClient, MessageMeta, SyncResult, async_parse, build_url, text
from .errors import MailCursorExpired, MailNoMailbox, MailNotFound, MailServerError

_LOGGER = logging.getLogger(__name__)

GRAPH_URL = "https://graph.microsoft.com/v1.0"
PAGE_SIZE = 50
MAX_PAGES_PER_FOLDER = 20
META_SELECT = (
    "id,internetMessageId,subject,from,receivedDateTime,sentDateTime,bodyPreview"
)
FETCH_SELECT = (
    "id,internetMessageId,subject,from,replyTo,sentDateTime,receivedDateTime,"
    "body,internetMessageHeaders"
)

_GRAPH_ORIGIN = "https://graph.microsoft.com/"
_PAGE_HEADERS = {"Prefer": f"odata.maxpagesize={PAGE_SIZE}"}
_FETCH_HEADERS = {"Prefer": 'outlook.body-content-type="html"'}


def _graph_time(value: Any) -> datetime | None:
    """Parse a Graph timestamp as an aware UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _graph_link(value: Any) -> URL | None:
    """Return a paging link if it points to Graph, so the token stays there."""
    if isinstance(value, str) and value.startswith(_GRAPH_ORIGIN):
        return URL(value, encoded=True)
    return None


class GraphClient(ApiClient):
    """Read Inbox and Junk Email of a personal Microsoft account.

    The cursor is ``{"folders": {folder: {"delta_link": url}}}``; a folder
    whose sync hit the page cap stores ``{"next_link": url}`` instead.
    """

    provider = PROVIDER_MICROSOFT
    no_mailbox_codes = frozenset(
        {"mailboxnotenabledforrestapi", "mailboxnotsupportedforrestapi"}
    )
    expired_codes = frozenset(
        {"syncstatenotfound", "syncstateinvalid", "resyncrequired"}
    )

    async def async_get_address(self) -> str:
        """Return the account's address, checking that it has a mailbox."""
        profile = await self.async_get_json(
            f"{GRAPH_URL}/me", params={"$select": "mail,userPrincipalName"}
        )
        address = text(profile.get("mail")) or text(profile.get("userPrincipalName"))
        if "@" not in address:
            raise MailNoMailbox("the account has no e-mail address")
        try:
            await self.async_get_json(
                f"{GRAPH_URL}/me/mailFolders/inbox", params={"$select": "id"}
            )
        except MailNotFound:
            raise MailNoMailbox("the account has no mailbox") from None
        self._address = address.lower()
        return self._address

    async def async_sync(
        self,
        cursor: dict[str, Any] | None,
        *,
        lookback: timedelta,
        folders: Sequence[str] = (),
    ) -> SyncResult:
        """Return e-mails added to ``folders`` since ``cursor``.

        Without a cursor, or when a stored link expired, the folder is read
        from ``lookback`` ago. Graph may return e-mails seen before, so the
        caller deduplicates.
        """
        states = cursor.get("folders") if isinstance(cursor, Mapping) else None
        states = states if isinstance(states, Mapping) else {}
        result = SyncResult(cursor={"folders": {}})
        for folder in dict.fromkeys(folders or MICROSOFT_FOLDERS):
            state = states.get(folder)
            messages, new_state, complete = await self._async_sync_folder(
                folder, state if isinstance(state, Mapping) else {}, lookback
            )
            result.messages.extend(messages)
            result.cursor["folders"][folder] = new_state
            result.complete = result.complete and complete
        return result

    async def _async_sync_folder(
        self, folder: str, state: Mapping[str, Any], lookback: timedelta
    ) -> tuple[list[MessageMeta], dict[str, str], bool]:
        """Continue a folder's delta sync, or restart it from ``lookback``."""
        link = _graph_link(state.get("next_link")) or _graph_link(
            state.get("delta_link")
        )
        if link is not None:
            try:
                return await self._async_read_delta(folder, link)
            except MailCursorExpired:
                _LOGGER.debug("Delta link of folder %s expired; resyncing", folder)
        since = datetime.now(UTC) - lookback
        start = build_url(
            f"{GRAPH_URL}/me/mailFolders/{quote(folder, safe='')}/messages/delta",
            {
                "$select": META_SELECT,
                "$filter": f"receivedDateTime ge {since:%Y-%m-%dT%H:%M:%SZ}",
            },
        )
        try:
            return await self._async_read_delta(folder, start)
        except MailCursorExpired as err:
            raise MailServerError(str(err)) from None

    async def _async_read_delta(
        self, folder: str, url: URL
    ) -> tuple[list[MessageMeta], dict[str, str], bool]:
        """Follow delta pages until the delta link or the page cap."""
        messages: list[MessageMeta] = []
        for _ in range(MAX_PAGES_PER_FOLDER):
            page = await self.async_get_json(url, headers=_PAGE_HEADERS)
            items = page.get("value")
            for item in items if isinstance(items, list) else ():
                if (
                    isinstance(item, Mapping)
                    and "@removed" not in item
                    and text(item.get("id"))
                ):
                    messages.append(self._meta(item, folder))
            if "@odata.nextLink" in page:
                if (next_link := _graph_link(page["@odata.nextLink"])) is None:
                    raise MailServerError("unexpected paging link")
                url = next_link
                continue
            if (delta_link := _graph_link(page.get("@odata.deltaLink"))) is None:
                raise MailServerError("delta response without a delta link")
            return messages, {"delta_link": str(delta_link)}, True
        return messages, {"next_link": str(url)}, False

    @staticmethod
    def _meta(item: Mapping[str, Any], folder: str) -> MessageMeta:
        """Return the headers of a Graph message."""
        sender = item.get("from")
        email = sender.get("emailAddress") if isinstance(sender, Mapping) else None
        email = email if isinstance(email, Mapping) else {}
        received = _graph_time(item.get("receivedDateTime"))
        sent = _graph_time(item.get("sentDateTime"))
        return MessageMeta(
            provider_id=text(item.get("id")),
            message_id=text(item.get("internetMessageId")) or None,
            sender=text(email.get("address")).lower(),
            sender_name=text(email.get("name")),
            subject=text(item.get("subject")),
            received=received or sent or datetime.now(UTC),
            sent=sent,
            folder=folder,
            preview=text(item.get("bodyPreview")),
        )

    async def async_fetch(self, provider_id: str) -> MailMessage:
        """Download one e-mail with its HTML body and Internet headers."""
        mailbox = await self._async_mailbox()
        item = await self.async_get_json(
            f"{GRAPH_URL}/me/messages/{quote(provider_id, safe='')}",
            params={"$select": FETCH_SELECT},
            headers=_FETCH_HEADERS,
        )
        body = item.get("body")
        content = body.get("content") if isinstance(body, Mapping) else None
        size = len(content) if isinstance(content, str) else 0
        message = await async_parse(
            size, normalize.message_from_graph, item, mailbox=mailbox
        )
        if message.received is None:
            message.received = _graph_time(item.get("receivedDateTime"))
        return message
