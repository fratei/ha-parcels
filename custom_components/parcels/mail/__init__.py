"""Mailbox API clients: shared types and HTTP handling."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from http import HTTPStatus
import json
from typing import Any, ClassVar, Protocol
from urllib.parse import quote, urlencode

import aiohttp
from yarl import URL

from ..parsers.base import MailMessage
from .errors import (
    MailApiDisabled,
    MailAuthError,
    MailCursorExpired,
    MailError,
    MailNoMailbox,
    MailNotFound,
    MailRateLimited,
    MailServerError,
    parse_retry_after,
)

REQUEST_TIMEOUT = 30.0
# Bodies above this size are parsed in an executor thread.
OFFLOAD_PARSE_BYTES = 256 * 1024

# Returns the access token. Called with a token the API rejected, it returns
# a refreshed one.
type TokenGetter = Callable[[str | None], Awaitable[str]]
type QueryParams = Mapping[str, str] | Sequence[tuple[str, str]]


@dataclass(frozen=True, slots=True)
class MessageMeta:
    """Headers of one e-mail, read before deciding to download its body."""

    provider_id: str
    message_id: str | None
    sender: str
    sender_name: str
    subject: str
    received: datetime
    sent: datetime | None = None
    folder: str | None = None
    # The API's short body preview (Graph bodyPreview, Gmail snippet). Kept in
    # memory only, for the prefilter.
    preview: str = ""


@dataclass(slots=True)
class SyncResult:
    """New e-mails since the last sync and the cursor for the next one."""

    messages: list[MessageMeta] = field(default_factory=list)
    cursor: dict[str, Any] = field(default_factory=dict)
    complete: bool = True
    # E-mails listed whose headers failed to download, by provider ID. The
    # cursor moves past them: Parcels reads their headers again later.
    failed: dict[str, Exception] = field(default_factory=dict)


class MailClient(Protocol):
    """What the polling coordinator needs from a mailbox API."""

    provider: str

    async def async_get_address(self) -> str:
        """Return the mailbox address."""

    async def async_sync(
        self,
        cursor: dict[str, Any] | None,
        *,
        lookback: timedelta,
        folders: Sequence[str] = (),
    ) -> SyncResult:
        """Return e-mails added since ``cursor``, or within ``lookback``."""

    async def async_fetch_meta(self, provider_id: str) -> MessageMeta | None:
        """Return the headers of one e-mail; None once it's deleted."""

    async def async_fetch(self, provider_id: str) -> MailMessage:
        """Download one full e-mail and normalise it."""


def build_url(url: str, params: QueryParams | None = None) -> URL:
    """Return ``url`` with ``params`` percent-encoded (spaces as ``%20``)."""
    if params:
        url = f"{url}?{urlencode(params, quote_via=quote, safe='$,:')}"
    return URL(url, encoded=True)


def text(value: Any) -> str:
    """Return ``value`` with collapsed whitespace, or "" if it isn't a string."""
    return " ".join(value.split()) if isinstance(value, str) else ""


async def async_parse(
    size: int, func: Callable[..., MailMessage], /, *args: Any, **kwargs: Any
) -> MailMessage:
    """Run a parser, in an executor thread when the input is large."""
    if size <= OFFLOAD_PARSE_BYTES:
        return func(*args, **kwargs)
    return await asyncio.get_running_loop().run_in_executor(
        None, partial(func, *args, **kwargs)
    )


class ApiClient:
    """Shared HTTP handling of the mailbox API clients.

    Error responses are reduced to their status and error codes, so no
    response text (which could quote e-mail content) reaches exceptions or
    logs.
    """

    provider: str = ""
    no_mailbox_codes: ClassVar[frozenset[str]] = frozenset()
    api_disabled_codes: ClassVar[frozenset[str]] = frozenset()
    rate_limit_codes: ClassVar[frozenset[str]] = frozenset()
    expired_codes: ClassVar[frozenset[str]] = frozenset()

    def __init__(
        self,
        session: aiohttp.ClientSession,
        get_token: TokenGetter,
        *,
        address: str | None = None,
    ) -> None:
        """Store the HTTP session, the token source and the mailbox address."""
        self._session = session
        self._get_token = get_token
        self._address = address.strip().lower() if address else None

    @property
    def address(self) -> str | None:
        """Return the mailbox address, if known."""
        return self._address

    async def _async_mailbox(self) -> str:
        """Return the mailbox address, reading it from the API if unknown."""
        return self._address or await self.async_get_address()

    async def async_get_address(self) -> str:
        """Return the mailbox address."""
        raise NotImplementedError

    async def async_get_json(
        self,
        url: str | URL,
        *,
        params: QueryParams | None = None,
        headers: Mapping[str, str] | None = None,
        per_message: bool = False,
    ) -> dict[str, Any]:
        """GET a JSON object and map failures to mail errors.

        A token the API rejects before it expires (revoked, or a clock out of
        step) is refreshed once and the request made again. ``per_message``
        marks a request for one e-mail, whose refusal concerns that e-mail.
        """
        request_url = url if isinstance(url, URL) else build_url(url, params)
        token = await self._get_token(None)
        try:
            return await self._async_request(
                request_url, token, headers, per_message=per_message
            )
        except _TokenRejected:
            pass
        token = await self._get_token(token)
        try:
            return await self._async_request(
                request_url, token, headers, per_message=per_message
            )
        except _TokenRejected as err:
            raise MailAuthError(str(err)) from None

    async def _async_request(
        self,
        request_url: URL,
        token: str,
        headers: Mapping[str, str] | None,
        *,
        per_message: bool,
    ) -> dict[str, Any]:
        """GET a JSON object with ``token``."""
        request_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            **(headers or {}),
        }
        try:
            async with (
                asyncio.timeout(REQUEST_TIMEOUT),
                self._session.get(request_url, headers=request_headers) as response,
            ):
                if response.status >= HTTPStatus.BAD_REQUEST:
                    error = self._status_error(
                        response.status,
                        await _async_error_codes(response),
                        response.headers,
                        per_message=per_message,
                    )
                    if (
                        response.status == HTTPStatus.UNAUTHORIZED
                        and type(error) is MailAuthError
                    ):
                        raise _TokenRejected(str(error))
                    raise error
                body = await response.read()
        except MailError:
            raise
        except TimeoutError as err:
            raise MailServerError("request timed out") from err
        except aiohttp.ClientError as err:
            raise MailServerError(f"request failed ({type(err).__name__})") from err
        try:
            data = json.loads(body)
        except ValueError:
            raise MailServerError("response is not JSON") from None
        if not isinstance(data, dict):
            raise MailServerError("response is not a JSON object")
        return data

    def _status_error(
        self,
        status: int,
        codes: frozenset[str],
        headers: Mapping[str, str],
        *,
        per_message: bool = False,
    ) -> MailError:
        """Return the mail error for an HTTP error status."""
        lowered = {code.lower() for code in codes}
        detail = f"HTTP {status}" + (f" ({', '.join(sorted(codes))})" if codes else "")
        if lowered & self.no_mailbox_codes:
            return MailNoMailbox(detail)
        if lowered & self.api_disabled_codes:
            return MailApiDisabled(detail)
        if status == HTTPStatus.TOO_MANY_REQUESTS or (
            status == HTTPStatus.FORBIDDEN and lowered & self.rate_limit_codes
        ):
            return MailRateLimited(parse_retry_after(headers.get("Retry-After")))
        if status == HTTPStatus.FORBIDDEN and per_message:
            return MailError(detail)
        if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            return MailAuthError(detail)
        if status == HTTPStatus.NOT_FOUND:
            return MailNotFound(detail)
        if status == HTTPStatus.GONE or lowered & self.expired_codes:
            return MailCursorExpired(detail)
        if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
            return MailServerError(detail)
        return MailError(detail)


class _TokenRejected(MailAuthError):
    """The API rejected the access token (HTTP 401)."""


_CODE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)


def _is_code(value: Any) -> bool:
    """Return whether ``value`` looks like an error code, not free text."""
    return isinstance(value, str) and 0 < len(value) <= 64 and set(value) <= _CODE_CHARS


async def _async_error_codes(response: aiohttp.ClientResponse) -> frozenset[str]:
    """Return the error codes of an error response, never its message."""
    try:
        data = json.loads(await response.read())
    except aiohttp.ClientError, ValueError:
        return frozenset()
    error = data.get("error") if isinstance(data, dict) else None
    found: list[Any] = []
    if isinstance(error, str):
        found.append(error)
    elif isinstance(error, dict):
        found += [error.get("code"), error.get("status")]
        for key in ("errors", "details"):
            items = error.get(key)
            if isinstance(items, list):
                found += [
                    item.get("reason") for item in items if isinstance(item, dict)
                ]
    return frozenset(code for code in found if _is_code(code))
