"""Tests for the Parcel app API client.

The answers follow the shapes in Parcel's documentation
(parcelapp.net/help/api-view-deliveries.html and api-add-delivery.html),
with made-up values.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.parcels.parcelapp.api import (
    ADD_URL,
    DELIVERIES_URL,
    ErrorKind,
    ParcelAppError,
    async_add_delivery,
    async_get_deliveries,
    normalize_postcode,
    valid_key,
)

KEY = "synthetic-parcel-key-0001"
SECRET_WORDS = "synthetic-secret-detail"
DELIVERY: dict[str, Any] = {
    "carrier_code": "ctt",
    "description": "Example Shop",
    "status_code": 2,
    "tracking_number": "EA123456785PT",
    "events": [
        {
            "event": "In transit",
            "date": "2026-11-03 10:15:00",
            "location": "Example City",
            "additional": "",
        }
    ],
    "date_expected": "2026-11-05 00:00:00",
}


async def test_get_deliveries(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Deliveries are read with the key header; stray entries are skipped."""
    aioclient_mock.get(
        DELIVERIES_URL,
        json={"success": True, "deliveries": [DELIVERY, "not a delivery", None]},
    )

    assert await async_get_deliveries(hass, KEY) == [DELIVERY]
    assert await async_get_deliveries(hass, KEY, active_only=True) == [DELIVERY]

    (method, url, data, headers), (_, active_url, _, _) = aioclient_mock.mock_calls
    assert method == "get"
    assert url.query == {"filter_mode": "recent"}
    assert active_url.query == {"filter_mode": "active"}
    assert data is None
    assert headers["api-key"] == KEY


@pytest.mark.parametrize(
    ("answer", "kind", "status"),
    [
        ({"status": HTTPStatus.TOO_MANY_REQUESTS}, ErrorKind.RATE, 429),
        ({"status": HTTPStatus.UNAUTHORIZED}, ErrorKind.KEY, 401),
        ({"status": HTTPStatus.FORBIDDEN}, ErrorKind.KEY, 403),
        ({"status": HTTPStatus.INTERNAL_SERVER_ERROR}, ErrorKind.SERVER, 500),
        ({"status": HTTPStatus.SERVICE_UNAVAILABLE}, ErrorKind.SERVER, 503),
        ({"status": HTTPStatus.NOT_FOUND, "text": "<html>"}, ErrorKind.HTTP, 404),
        ({"text": "<html>"}, ErrorKind.INVALID, None),
        ({"json": ["not", "an", "object"]}, ErrorKind.INVALID, None),
        ({"json": {"success": True}}, ErrorKind.INVALID, None),
        ({"json": {"deliveries": []}}, ErrorKind.INVALID, None),
        (
            {"json": {"success": False, "error_message": "Invalid API key"}},
            ErrorKind.KEY,
            None,
        ),
        (
            {"json": {"success": False, "error_message": "Premium required"}},
            ErrorKind.KEY,
            None,
        ),
        (
            {"json": {"success": False, "error_message": "Too many requests"}},
            ErrorKind.RATE,
            None,
        ),
        (
            {
                "status": HTTPStatus.BAD_REQUEST,
                "json": {"success": False, "error_message": "Rate limit exceeded"},
            },
            ErrorKind.RATE,
            400,
        ),
        # Reading takes nothing but the key, so any other refusal is the key's.
        (
            {"json": {"success": False, "error_message": SECRET_WORDS}},
            ErrorKind.KEY,
            None,
        ),
        ({"exc": aiohttp.ClientError()}, ErrorKind.NETWORK, None),
        ({"exc": TimeoutError()}, ErrorKind.NETWORK, None),
    ],
)
async def test_get_deliveries_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    answer: dict[str, Any],
    kind: ErrorKind,
    status: int | None,
) -> None:
    """Failures are sorted by kind, without Parcel's own message."""
    aioclient_mock.get(DELIVERIES_URL, **answer)

    with pytest.raises(ParcelAppError) as caught:
        await async_get_deliveries(hass, KEY)

    assert caught.value.kind is kind
    assert caught.value.status == status
    assert SECRET_WORDS not in str(caught.value)
    assert caught.value.code == (kind.value if status is None else f"{kind}_{status}")


async def test_rate_limit_retry_after(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rate limit keeps the delay Parcel asks for."""
    aioclient_mock.get(
        DELIVERIES_URL,
        status=HTTPStatus.TOO_MANY_REQUESTS,
        headers={"Retry-After": "1800"},
    )

    with pytest.raises(ParcelAppError) as caught:
        await async_get_deliveries(hass, KEY)

    assert caught.value.kind is ErrorKind.RATE
    assert caught.value.retry_after == 1800


async def test_add_delivery(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A delivery is added quietly, with the postcode only when given."""
    aioclient_mock.post(ADD_URL, json={"success": True})

    await async_add_delivery(
        hass,
        KEY,
        number="EA123456785PT",
        carrier="ctt",
        description="Example Shop",
        language="pt",
    )
    await async_add_delivery(
        hass,
        KEY,
        number="Ab3Cd4Ef5_1",
        carrier="paack",
        description="Parcels",
        language=None,
        postcode="1000-001",
    )

    (method, _, first, headers), (_, _, second, _) = aioclient_mock.mock_calls
    assert method == "post"
    assert headers["api-key"] == KEY
    assert first == {
        "tracking_number": "EA123456785PT",
        "carrier_code": "ctt",
        "description": "Example Shop",
        "send_push_confirmation": False,
        "language": "pt",
    }
    assert second == {
        "tracking_number": "Ab3Cd4Ef5_1",
        "carrier_code": "paack",
        "description": "Parcels",
        "send_push_confirmation": False,
        "postcode": "1000-001",
    }


@pytest.mark.parametrize(
    ("answer", "kind"),
    [
        (
            {"json": {"success": False, "error_message": "Invalid tracking number"}},
            ErrorKind.REFUSED,
        ),
        ({"json": {"success": False}}, ErrorKind.REFUSED),
        (
            {"json": {"success": False, "error_message": SECRET_WORDS}},
            ErrorKind.REFUSED,
        ),
        (
            {"json": {"success": False, "error_message": "Invalid API key"}},
            ErrorKind.KEY,
        ),
        (
            {"json": {"success": False, "error_message": "Daily limit reached"}},
            ErrorKind.RATE,
        ),
        ({"status": HTTPStatus.TOO_MANY_REQUESTS}, ErrorKind.RATE),
        ({"status": HTTPStatus.BAD_GATEWAY}, ErrorKind.SERVER),
    ],
)
async def test_add_delivery_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    answer: dict[str, Any],
    kind: ErrorKind,
) -> None:
    """A refused delivery is told apart from a refused key or a rate limit."""
    aioclient_mock.post(ADD_URL, **answer)

    with pytest.raises(ParcelAppError) as caught:
        await async_add_delivery(
            hass,
            KEY,
            number="EA123456785PT",
            carrier="ctt",
            description="Example Shop",
            language="en",
        )

    assert caught.value.kind is kind
    assert SECRET_WORDS not in str(caught.value)


@pytest.mark.parametrize(
    ("value", "country", "expected"),
    [
        ("1000-001", "PT", "1000-001"),
        ("1000001", "PT", "1000-001"),
        (" 1000 001 ", "PT", "1000-001"),
        ("1000-01", "PT", None),
        ("10000-001", "PT", None),
        ("ABCD-EFG", "PT", None),
        ("", "PT", None),
        ("sw1a  1aa", "GB", "SW1A 1AA"),
        ("28001", "ES", "28001"),
        ("1000-001", None, "1000-001"),
        ("ABCDE", None, None),
        ("1", None, None),
        ("12345678901234", None, None),
    ],
)
def test_normalize_postcode(
    value: str, country: str | None, expected: str | None
) -> None:
    """Postcodes are checked, strictly in Portugal (NNNN-NNN)."""
    assert normalize_postcode(value, country) == expected


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (KEY, True),
        ("short", False),
        ("with a space", False),
        ("x" * 512, True),
        ("x" * 513, False),
        ("chave-com-acentuação", False),
    ],
)
def test_valid_key(key: str, expected: bool) -> None:
    """A key is printable ASCII without spaces."""
    assert valid_key(key) is expected
