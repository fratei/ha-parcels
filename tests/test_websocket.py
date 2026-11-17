"""Tests for the Parcels WebSocket API and the views it sends."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import date, time, timedelta
import logging
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.models import User
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant.common import (
    CLIENT_ID,
    MockUser,
    async_fire_time_changed,
    async_fire_time_changed_exact,
)
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

from custom_components.parcels.const import DOMAIN, SIGNAL_AI_UPDATED
from custom_components.parcels.engine import ParcelsEngine
from custom_components.parcels.models import MessageState, order_key
from custom_components.parcels.parsers.base import Eta
from custom_components.parcels.views import (
    SYSTEM_VIEWER,
    Viewer,
    async_viewer,
    mailbox_owner,
    viewer_for,
)
from custom_components.parcels.websocket import MAX_LIST, OVERRIDES_SCHEMA, UPDATE_DELAY

from .common import (
    ADDRESS,
    OTHER_OWNER,
    OWNER,
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    patch_mail_clients,
)

NOW = "2026-11-17 10:00:00+00:00"
CTT_NUMBER = "RR482915732PT"
SHOP_NUMBER = "RR123456785PT"
UPS_NUMBER = "1Z999AA10123456784"
DHL_NUMBER = "JJD0001234567"
OTHER_DHL_NUMBER = "JJD0007654321"
SHOP = "loja-exemplo.example"
UPS = "email.ups.com"
FILTERED_SENDER = "servicos-exemplo.example"
SHOP_MAIL = "common/small_shop_ctt.eml"
DASHBOARD = "/dashboard-parcels/week"
# What someone who may not see a private parcel gets instead of its details.
HIDDEN = {
    "merchant": None,
    "carrier": None,
    "carrier_name": None,
    "tracking_number": None,
    "tracking_url": None,
    "pickup_point": None,
    "pickup_code": None,
    "order_numbers": [],
    "items": [],
    "source": "parser",
    "ai": False,
    "auto_merged": None,
    "origins": [],
    "restricted": True,
}


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on 17 November 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


@pytest.fixture
async def sam(hass: HomeAssistant) -> User:
    """Return Sam, who is not an administrator."""
    return await hass.auth.async_create_user("Sam")


@pytest.fixture
async def persons(hass: HomeAssistant, hass_admin_user: MockUser, sam: User) -> None:
    """Link person.alex to the administrator and person.sam to Sam."""
    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {"id": "alex", "name": "Alex", "user_id": hass_admin_user.id},
                {"id": "sam", "name": "Sam", "user_id": sam.id},
            ]
        },
    )


@pytest.fixture
def client() -> FakeMailClient:
    """Return Alex's mailbox: a parcel, two e-mails to review and a filtered one."""
    client = FakeMailClient()
    for path in (
        "carriers/ctt_in_transit_pt.eml",
        SHOP_MAIL,
        "carriers/ups_marketing_en.eml",
        "common/unknown_phone_only.eml",
    ):
        client.add(path)
    return client


@pytest.fixture
async def engine(
    hass: HomeAssistant, persons: None, client: FakeMailClient
) -> AsyncIterator[ParcelsEngine]:
    """Load the hub, with a dashboard, and Alex's mailbox."""
    add_hub(hass, dashboard_path=DASHBOARD)
    add_mailbox(hass)
    with patch_mail_clients(client):
        yield await async_setup_parcels(hass)


@pytest.fixture
async def ws(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, engine: ParcelsEngine
) -> MockHAClientWebSocket:
    """Connect Alex, an administrator."""
    return await hass_ws_client(hass)


@pytest.fixture
async def sam_ws(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    engine: ParcelsEngine,
    sam: User,
) -> MockHAClientWebSocket:
    """Connect Sam, who is not an administrator."""
    refresh = await hass.auth.async_create_refresh_token(sam, CLIENT_ID)
    return await hass_ws_client(
        hass, access_token=hass.auth.async_create_access_token(refresh)
    )


@pytest.fixture
def review(engine: ParcelsEngine) -> dict[str, str]:
    """Return the IDs of the e-mails under review, by sender domain."""
    return {item.sender_domain: item.id for item in engine.data.review.values()}


async def result(ws: MockHAClientWebSocket, msg_type: str, **data: Any) -> Any:
    """Send a command and return its result."""
    await ws.send_json_auto_id({"type": msg_type, **data})
    reply = await ws.receive_json()
    assert reply["type"] == "result"
    assert reply["success"], reply
    return reply["result"]


async def error(
    ws: MockHAClientWebSocket, msg_type: str, **data: Any
) -> dict[str, Any]:
    """Send a command that must fail; return the error."""
    await ws.send_json_auto_id({"type": msg_type, **data})
    reply = await ws.receive_json()
    assert reply["type"] == "result"
    assert not reply["success"]
    return reply["error"]


async def refused(
    ws: MockHAClientWebSocket, msg_type: str, key: str, **data: Any
) -> dict[str, Any]:
    """Send a command that must fail with the translated user error ``key``."""
    err = await error(ws, msg_type, **data)
    assert err["code"] == "home_assistant_error"
    assert err["translation_domain"] == DOMAIN
    assert err["translation_key"] == key
    return err


def no_errors_logged(caplog: pytest.LogCaptureFixture) -> bool:
    """Return True when nothing was logged as an error."""
    return not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def subscribe(ws: MockHAClientWebSocket) -> tuple[int, dict[str, Any]]:
    """Subscribe to the parcels; return the subscription and the first snapshot."""
    await ws.send_json_auto_id({"type": "parcels/subscribe"})
    reply = await ws.receive_json()
    assert reply["success"]
    assert reply["result"] is None
    event = await ws.receive_json()
    assert (event["id"], event["type"]) == (reply["id"], "event")
    return reply["id"], event["event"]


async def assert_nothing_sent(ws: MockHAClientWebSocket) -> None:
    """Check that no event is waiting: a command's result comes first."""
    await ws.send_json_auto_id({"type": "parcels/list"})
    reply = await ws.receive_json()
    assert reply["type"] == "result", reply


async def async_wait_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Let the time for a burst of changes to reach the page pass."""
    freezer.tick(timedelta(seconds=UPDATE_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def async_wait_reprocess(hass: HomeAssistant) -> None:
    """Wait for the e-mails of a trusted sender to be read again."""
    await asyncio.gather(
        *(
            task
            for task in asyncio.all_tasks()
            if task.get_name().startswith("parcels reprocess")
        )
    )
    await hass.async_block_till_done()


async def call(
    hass: HomeAssistant, service: str, data: dict[str, Any], *, user: User | None = None
) -> None:
    """Call a Parcels service as ``user``, or like an automation without one."""
    await hass.services.async_call(
        DOMAIN,
        service,
        data,
        blocking=True,
        context=Context(user_id=user.id if user else None),
    )


async def add(
    hass: HomeAssistant, number: str, *, user: User | None = None, **data: Any
) -> str:
    """Add a parcel by tracking number; return its ID."""
    response = await hass.services.async_call(
        DOMAIN,
        "add",
        {"tracking_number": number, **data},
        blocking=True,
        context=Context(user_id=user.id if user else None),
        return_response=True,
    )
    assert response is not None
    return str(response["parcel_id"])


# -- Listing ------------------------------------------------------------------


async def test_list(engine: ParcelsEngine, ws: MockHAClientWebSocket) -> None:
    """An administrator gets the parcels, the e-mails to review and the settings."""
    snapshot = await result(ws, "parcels/list")

    (parcel,) = snapshot["parcels"]
    assert (parcel["tracking_number"], parcel["carrier"]) == (CTT_NUMBER, "ctt")
    assert parcel["owners"] == [OWNER]
    assert not parcel["restricted"]
    # Newest first, with whose mailbox they came to.
    assert [
        (item["sender_domain"], item["reason"], item["mailbox_owner"])
        for item in snapshot["review"]
    ] == [(SHOP, "unknown_sender", "Alex"), (UPS, "unknown_format", "Alex")]
    assert snapshot["review"][0]["suggestion"]["tracking_numbers"] == [SHOP_NUMBER]
    # Filtered e-mails show only who sent them and what about.
    (filtered,) = snapshot["filtered"]
    assert set(filtered) == {
        "id",
        "created",
        "received",
        "sender",
        "sender_domain",
        "subject",
    }
    assert filtered["sender_domain"] == FILTERED_SENDER
    assert filtered["subject"] == "A sua encomenda está a caminho"
    assert snapshot["settings"] == {
        "user_is_admin": True,
        "ai_enabled": False,
        "ai_mode": "suggest",
        "dashboard_url": DASHBOARD,
        "seventeentrack": False,
        "time_zone": "Europe/Lisbon",
        "today": "2026-11-17",
    }


async def test_private_parcels(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
    sam: User,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the owners see a private parcel; the others see when it comes."""
    (alex_parcel,) = engine.data.parcels
    await call(
        hass,
        "update",
        {
            "parcel_id": alex_parcel,
            "private": True,
            "merchant": "Worten",
            "pickup_point": "Locker 12",
            "pickup_code": "4711",
        },
    )
    sam_parcel = await add(hass, DHL_NUMBER, user=sam, carrier="dhl", private=True)
    # Without owners, only administrators may see it.
    system_parcel = await add(hass, OTHER_DHL_NUMBER, carrier="dhl", private=True)

    alex = {p["id"]: p for p in (await result(ws, "parcels/list"))["parcels"]}
    sam_view = await result(sam_ws, "parcels/list")
    seen = {p["id"]: p for p in sam_view["parcels"]}

    assert [pid for pid, p in alex.items() if p["restricted"]] == [sam_parcel]
    assert [pid for pid, p in seen.items() if p["restricted"]] == [
        alex_parcel,
        system_parcel,
    ]
    assert alex[alex_parcel]["pickup_code"] == "4711"
    assert seen[alex_parcel] == {**alex[alex_parcel], **HIDDEN}
    assert seen[alex_parcel]["owners"] == [OWNER]
    assert seen[sam_parcel]["owners"] == [OTHER_OWNER]
    assert sam_view["review"] == sam_view["filtered"] == []
    assert not sam_view["settings"]["user_is_admin"]

    await refused(sam_ws, "parcels/get", "not_allowed", parcel_id=alex_parcel)
    await refused(sam_ws, "parcels/get", "not_allowed", parcel_id=system_parcel)
    await refused(ws, "parcels/get", "not_allowed", parcel_id=sam_parcel)
    await refused(ws, "parcels/get", "unknown_parcel", parcel_id="p_missing")
    mine = await result(sam_ws, "parcels/get", parcel_id=sam_parcel)
    assert mine["parcel"]["tracking_number"] == DHL_NUMBER
    unowned = await result(ws, "parcels/get", parcel_id=system_parcel)
    assert unowned["parcel"]["tracking_number"] == OTHER_DHL_NUMBER
    assert no_errors_logged(caplog)


async def test_viewer_for(
    hass: HomeAssistant, engine: ParcelsEngine, hass_admin_user: MockUser, sam: User
) -> None:
    """Users see as their persons; without a user, the system sees everything."""
    assert viewer_for(hass, None) is SYSTEM_VIEWER
    assert viewer_for(hass, hass_admin_user) == Viewer(
        is_admin=True, persons=frozenset({OWNER})
    )
    assert viewer_for(hass, sam) == Viewer(
        is_admin=False, persons=frozenset({OTHER_OWNER})
    )
    # The same for service calls, by user ID; a deleted user has no rights.
    assert await async_viewer(hass, None) is SYSTEM_VIEWER
    assert await async_viewer(hass, sam.id) == viewer_for(hass, sam)
    assert await async_viewer(hass, "deleted-user") == Viewer(is_admin=False)


# -- Subscribing --------------------------------------------------------------


async def test_subscribe(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The page gets a snapshot now, then one update per burst of changes."""
    sub_id, snapshot = await subscribe(ws)
    assert len(snapshot["parcels"]) == 1
    assert snapshot["settings"]["user_is_admin"]

    await add(hass, DHL_NUMBER, carrier="dhl")
    await add(hass, OTHER_DHL_NUMBER, carrier="dhl")
    freezer.tick(timedelta(seconds=UPDATE_DELAY - 0.1))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()
    await assert_nothing_sent(ws)

    freezer.tick(timedelta(seconds=0.1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    event = await ws.receive_json()
    assert event["id"] == sub_id
    assert len(event["event"]["parcels"]) == 3
    await assert_nothing_sent(ws)

    # The AI's progress reaches the page too.
    async_dispatcher_send(hass, SIGNAL_AI_UPDATED)
    await async_wait_update(hass, freezer)
    assert (await ws.receive_json())["id"] == sub_id

    # Unsubscribing drops the update that was due.
    await call(hass, "archive", {"parcel_id": next(iter(engine.data.parcels))})
    assert await result(ws, "unsubscribe_events", subscription=sub_id) is None
    await async_wait_update(hass, freezer)
    await assert_nothing_sent(ws)


async def test_hub_not_loaded(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    freezer: FrozenDateTimeFactory,
    review: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without the hub, the page gets no more updates, and commands say why."""
    await subscribe(ws)
    await add(hass, DHL_NUMBER, carrier="dhl")
    # The mailbox reloads and gives up waiting for the hub at once.
    with patch("custom_components.parcels.HUB_WAIT", 0):
        assert await hass.config_entries.async_unload(engine.entry.entry_id)
        await async_wait_update(hass, freezer)

    await refused(ws, "parcels/list", "hub_not_loaded")
    await refused(ws, "parcels/subscribe", "hub_not_loaded")
    await refused(ws, "parcels/get", "hub_not_loaded", parcel_id="p_1")
    await refused(
        ws, "parcels/review/dismiss", "hub_not_loaded", review_id=review[SHOP]
    )
    assert no_errors_logged(caplog)


# -- Details ------------------------------------------------------------------


async def test_get(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The details have the timeline, the tracking link, the pickup and e-mails."""
    ((parcel_id, parcel),) = engine.data.parcels.items()
    (mail_origin,) = parcel.origins
    freezer.tick(timedelta(minutes=5))
    await call(
        hass,
        "update",
        {
            "parcel_id": parcel_id,
            "pickup_point": "Locker 12",
            "pickup_code": "4711",
            "eta_start": "2026-11-19",
        },
    )
    freezer.tick(timedelta(minutes=5))
    await call(hass, "mark_delivered", {"parcel_id": parcel_id})

    details = await result(ws, "parcels/get", parcel_id=parcel_id)

    shown = details["parcel"]
    assert CTT_NUMBER in shown["tracking_url"]
    assert (shown["pickup_point"], shown["pickup_code"]) == ("Locker 12", "4711")
    assert shown["eta_start"] == "2026-11-19"
    # The edits stay with the parcel; only the e-mail can be split off.
    assert shown["origins"] == [mail_origin]
    assert details["origins"] == [
        {
            "id": mail_origin,
            "label": "ctt.pt",
            "source": "parser",
            "time": "2026-11-17T08:05:00+00:00",
        }
    ]
    # The ETA change isn't a step on the way.
    assert details["timeline"] == [
        {
            "time": "2026-11-17T08:05:00+00:00",
            "status": "in_transit",
            "source": "parser",
            "label": "",
        },
        {
            "time": "2026-11-17T10:10:00+00:00",
            "status": "delivered",
            "source": "manual",
            "label": "",
        },
    ]
    assert details["orders"] == []


async def test_get_orders(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
    review: dict[str, str],
) -> None:
    """An order lists its parcels, except the private ones the user can't see."""
    (first,) = (await result(ws, "parcels/review/accept", review_id=review[SHOP]))[
        "parcel_ids"
    ]
    accepted = await result(
        ws,
        "parcels/review/accept",
        review_id=review[UPS],
        overrides={
            "merchant": "Loja Exemplo",
            "order_numbers": ["1042"],
            "tracking_numbers": [UPS_NUMBER],
        },
    )
    (second,) = accepted["parcel_ids"]
    assert second != first
    await call(hass, "update", {"parcel_id": second, "private": True})

    (order,) = (await result(ws, "parcels/get", parcel_id=first))["orders"]
    assert order == {
        "id": order_key("Loja Exemplo", "1042"),
        "merchant": "Loja Exemplo",
        "number": "1042",
        "placed_at": None,
        "parcel_ids": [first, second],
    }
    (seen,) = (await result(sam_ws, "parcels/get", parcel_id=first))["orders"]
    assert seen == {**order, "parcel_ids": [first]}


# -- Review -------------------------------------------------------------------


async def test_review_accept(
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    review: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Accepting adds what the e-mail says, with the user's corrections."""
    # The UPS e-mail names no parcel.
    await refused(
        ws,
        "parcels/review/accept",
        "nothing_to_add",
        review_id=review[UPS],
        overrides=None,
    )
    await refused(
        ws,
        "parcels/review/accept",
        "unknown_carrier",
        review_id=review[UPS],
        overrides={"carrier": "pigeon", "tracking_numbers": [UPS_NUMBER]},
    )
    await refused(ws, "parcels/review/accept", "unknown_review", review_id="r_1")
    assert no_errors_logged(caplog)

    accepted = await result(
        ws,
        "parcels/review/accept",
        review_id=review[UPS],
        overrides={
            "tracking_numbers": UPS_NUMBER,
            "merchant": None,
            "eta_start": "2026-11-19",
            "window_start": "13:00",
            "window_end": "14:00",
            "pickup_point": "Locker 12",
        },
    )

    (parcel_id,) = accepted["parcel_ids"]
    state = engine.data.parcels[parcel_id].state
    assert (state.tracking_number, state.carrier) == (UPS_NUMBER, "ups")
    assert state.eta == Eta(
        start=date(2026, 11, 19),
        end=date(2026, 11, 19),
        window_start=time(13),
        window_end=time(14),
    )
    assert state.pickup_point == "Locker 12"
    assert review[UPS] not in engine.data.review


@pytest.mark.parametrize(
    "overrides",
    [
        {"merchant": "x" * 501},
        {"tracking_numbers": [f"JJD000{n:07}" for n in range(MAX_LIST + 1)]},
        {"eta_start": "19/11/2026"},
        {"colour": "red"},
    ],
)
async def test_review_accept_bad_overrides(
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    review: dict[str, str],
    overrides: dict[str, Any],
) -> None:
    """Corrections that are too long, too many or unknown are refused."""
    err = await error(
        ws, "parcels/review/accept", review_id=review[SHOP], overrides=overrides
    )

    assert err["code"] == "invalid_format"
    assert review[SHOP] in engine.data.review


def test_review_accept_override_limits() -> None:
    """Corrections up to the limits are accepted as they are."""
    overrides = {"merchant": "x" * 500, "tracking_numbers": ["x"] * MAX_LIST}

    assert OVERRIDES_SCHEMA(overrides) == overrides


async def test_review_dismiss_and_restore(
    engine: ParcelsEngine, ws: MockHAClientWebSocket, review: dict[str, str]
) -> None:
    """Dismissed e-mails leave; a filtered one can come back for review."""
    message = engine.data.review[review[SHOP]].message
    (filtered_id,) = engine.data.filtered

    assert await result(ws, "parcels/review/dismiss", review_id=review[SHOP]) is None
    restored = await result(ws, "parcels/review/restore", filtered_id=filtered_id)

    assert engine.data.messages[message].state is MessageState.DISMISSED
    snapshot = await result(ws, "parcels/list")
    assert snapshot["filtered"] == []
    assert [
        (item["id"], item["sender_domain"], item["reason"], item["mailbox_owner"])
        for item in snapshot["review"]
    ] == [
        (restored["review_id"], FILTERED_SENDER, "restored", "Alex"),
        (review[UPS], UPS, "unknown_format", "Alex"),
    ]
    await refused(
        ws, "parcels/review/dismiss", "unknown_review", review_id=review[SHOP]
    )
    await refused(
        ws, "parcels/review/restore", "unknown_filtered", filtered_id=filtered_id
    )


async def test_review_senders(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    review: dict[str, str],
) -> None:
    """Trusting a sender adds what it sent; ignoring one drops its e-mails."""
    trusted = await result(ws, "parcels/review/trust_sender", review_id=review[SHOP])
    await async_wait_reprocess(hass)
    ignored = await result(ws, "parcels/review/ignore_sender", review_id=review[UPS])

    assert trusted == {"domain": SHOP}
    assert ignored == {"domain": "ups.com"}
    assert not engine.data.review
    assert engine.data.senders[SHOP].trusted
    assert engine.data.senders["ups.com"].ignored
    numbers = {p.state.tracking_number for p in engine.data.parcels.values()}
    assert numbers == {CTT_NUMBER, SHOP_NUMBER}
    for command in ("trust_sender", "ignore_sender"):
        await refused(
            ws, f"parcels/review/{command}", "unknown_review", review_id=review[SHOP]
        )


async def test_review_free_mail_sender(
    engine: ParcelsEngine, ws: MockHAClientWebSocket, review: dict[str, str]
) -> None:
    """A free mail provider can't be trusted or ignored, and the error names it."""
    # As if the shop wrote from a free mail account.
    engine.data.review[review[SHOP]].sender_domain = "gmail.com"

    for command in ("trust_sender", "ignore_sender"):
        err = await refused(
            ws,
            f"parcels/review/{command}",
            f"cannot_{command.removesuffix('_sender')}_free_mail",
            review_id=review[SHOP],
        )
        assert err["translation_placeholders"] == {"domain": "gmail.com"}
    assert review[SHOP] in engine.data.review
    assert not engine.data.senders


@pytest.mark.parametrize(
    "command", ["accept", "dismiss", "trust_sender", "ignore_sender", "restore"]
)
async def test_review_admin_only(
    engine: ParcelsEngine,
    sam_ws: MockHAClientWebSocket,
    review: dict[str, str],
    command: str,
) -> None:
    """Only administrators decide about e-mails."""
    (filtered_id,) = engine.data.filtered
    data = (
        {"filtered_id": filtered_id}
        if command == "restore"
        else {"review_id": review[SHOP]}
    )

    err = await error(sam_ws, f"parcels/review/{command}", **data)

    assert err["code"] == "unauthorized"
    assert review[SHOP] in engine.data.review
    assert filtered_id in engine.data.filtered
    assert not engine.data.senders


async def test_mailbox_owner(
    hass: HomeAssistant, engine: ParcelsEngine, review: dict[str, str]
) -> None:
    """An e-mail's owner is the person's name, else the mailbox's title."""
    item = engine.data.review[review[SHOP]]

    assert mailbox_owner(hass, item) == "Alex"
    assert mailbox_owner(hass, replace(item, owner="person.nobody")) == ADDRESS
    assert mailbox_owner(hass, replace(item, owner=None, mailbox="gone")) is None
    assert mailbox_owner(hass, replace(item, owner=None, mailbox=None)) is None
