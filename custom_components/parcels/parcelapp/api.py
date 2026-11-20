"""Parcel's API: read the user's deliveries and add new ones.

Documented at https://parcelapp.net/help/api-view-deliveries.html and
https://parcelapp.net/help/api-add-delivery.html. Reading allows 20 requests
an hour and answers from Parcel's cache; adding allows 20 requests a day,
failures included.

Parcel's error messages are never logged or kept, since they may repeat a
tracking number: an error carries only its kind and HTTP status.
"""

from __future__ import annotations

import asyncio
from enum import StrEnum
from http import HTTPStatus
import json
import re
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..mail.errors import parse_retry_after

API_ROOT = "https://api.parcel.app/external/"
DELIVERIES_URL = f"{API_ROOT}deliveries/"
ADD_URL = f"{API_ROOT}add-delivery/"
KEY_HEADER = "api-key"
REQUEST_TIMEOUT = 30.0

_KEY_RE = re.compile(r"[\x21-\x7e]{8,512}")
_PT_POSTCODE_RE = re.compile(r"(\d{4})[- ]?(\d{3})")
_POSTCODE_RE = re.compile(r"(?=.*\d)[A-Z0-9][A-Z0-9 -]{1,8}[A-Z0-9]")
_RATE_WORDS_RE = re.compile(
    r"\b(?:rate|too many|quota|limits? (?:reached|exceeded|hit)"
    r"|(?:daily|hourly|request|api) limits?|per (?:minute|hour|day)"
    r"|try again later)\b",
    re.IGNORECASE,
)
_KEY_WORDS_RE = re.compile(
    r"\b(?:api[ -]?key|auth\w*|unauthori[sz]ed|forbidden|premium|subscri\w*"
    r"|token|credential\w*)\b",
    re.IGNORECASE,
)


class ErrorKind(StrEnum):
    """What went wrong with a request to Parcel."""

    KEY = "key"
    """The key was refused, or the account has no Premium."""
    RATE = "rate"
    """Over the hourly or the daily limit."""
    REFUSED = "refused"
    """Parcel refused the delivery being added."""
    SERVER = "server"
    NETWORK = "network"
    INVALID = "invalid"
    """An answer Parcels can't read."""
    HTTP = "http"
    """Another HTTP error."""


class ParcelAppError(Exception):
    """A failed request to Parcel, described by kind and HTTP status only."""

    def __init__(
        self,
        kind: ErrorKind,
        status: int | None = None,
        *,
        retry_after: float | None = None,
    ) -> None:
        """Initialize the error."""
        super().__init__(kind.value if status is None else f"{kind} (HTTP {status})")
        self.kind = kind
        self.status = status
        self.retry_after = retry_after

    @property
    def code(self) -> str:
        """Return a short code for diagnostics."""
        return self.kind.value if self.status is None else f"{self.kind}_{self.status}"


def valid_key(key: str) -> bool:
    """Return whether ``key`` looks like an API key."""
    return _KEY_RE.fullmatch(key) is not None


def normalize_postcode(value: str, country: str | None) -> str | None:
    """Return the postcode in its usual form, or None when it isn't one.

    Portuguese postcodes must be NNNN-NNN; elsewhere a loose check applies.
    """
    text = " ".join(str(value).upper().split())
    if (country or "").upper() == "PT":
        if match := _PT_POSTCODE_RE.fullmatch(text):
            return f"{match[1]}-{match[2]}"
        return None
    return text if _POSTCODE_RE.fullmatch(text) else None


async def async_get_deliveries(
    hass: HomeAssistant, key: str, *, active_only: bool = False
) -> list[dict[str, Any]]:
    """Return the deliveries in the user's list.

    By default the recent ones: those on their way and those that arrived
    lately. Parcel answers from its cache, so asking doesn't update them.
    """
    data = await _async_request(
        hass,
        "get",
        DELIVERIES_URL,
        key,
        params={"filter_mode": "active" if active_only else "recent"},
    )
    deliveries = data.get("deliveries")
    if not isinstance(deliveries, list):
        raise ParcelAppError(ErrorKind.INVALID)
    return [delivery for delivery in deliveries if isinstance(delivery, dict)]


async def async_add_delivery(
    hass: HomeAssistant,
    key: str,
    *,
    number: str,
    carrier: str,
    description: str,
    language: str | None,
    postcode: str | None = None,
) -> None:
    """Add a delivery to the user's list, without a push to his devices."""
    payload: dict[str, Any] = {
        "tracking_number": number,
        "carrier_code": carrier,
        "description": description,
        "send_push_confirmation": False,
    }
    if language:
        payload["language"] = language
    if postcode:
        payload["postcode"] = postcode
    await _async_request(hass, "post", ADD_URL, key, payload=payload)


async def _async_request(
    hass: HomeAssistant,
    method: str,
    url: str,
    key: str,
    *,
    params: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a request and return its JSON object, or raise ParcelAppError."""
    session = async_get_clientsession(hass)
    headers = {KEY_HEADER: key, "Accept": "application/json"}
    try:
        async with (
            asyncio.timeout(REQUEST_TIMEOUT),
            session.request(
                method, url, params=params, json=payload, headers=headers
            ) as response,
        ):
            status = response.status
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            body = await response.read()
    except TimeoutError, aiohttp.ClientError:
        raise ParcelAppError(ErrorKind.NETWORK) from None
    if status == HTTPStatus.TOO_MANY_REQUESTS:
        raise ParcelAppError(ErrorKind.RATE, status, retry_after=retry_after)
    if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        raise ParcelAppError(ErrorKind.KEY, status)
    if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        raise ParcelAppError(ErrorKind.SERVER, status)
    try:
        data = json.loads(body)
    except ValueError:
        data = None
    failed = status >= HTTPStatus.BAD_REQUEST
    if isinstance(data, dict) and data.get("success") is False:
        raise ParcelAppError(
            _refusal(data, adding=payload is not None),
            status if failed else None,
            retry_after=retry_after,
        )
    if failed:
        raise ParcelAppError(ErrorKind.HTTP, status)
    if not isinstance(data, dict) or data.get("success") is not True:
        raise ParcelAppError(ErrorKind.INVALID)
    return data


def _refusal(data: dict[str, Any], *, adding: bool) -> ErrorKind:
    """Return the kind of a refusal from Parcel's message, without keeping it."""
    message = data.get("error_message")
    text = message if isinstance(message, str) else ""
    if _RATE_WORDS_RE.search(text):
        return ErrorKind.RATE
    if _KEY_WORDS_RE.search(text):
        return ErrorKind.KEY
    # Reading sends nothing but the key; adding also sends the delivery.
    return ErrorKind.REFUSED if adding else ErrorKind.KEY
