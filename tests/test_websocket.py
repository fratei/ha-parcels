"""Tests for the Parcels WebSocket API and the views it sends."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
import logging
import re
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.models import User
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant.common import (
    CLIENT_ID,
    MockUser,
    async_capture_events,
    async_fire_time_changed,
    async_fire_time_changed_exact,
)
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

from custom_components.parcels.const import (
    DOMAIN,
    EVENT_DELIVERED,
    EVENT_PARCEL_ADDED,
    EVENT_STATUS_CHANGED,
    REASON_AI_FILL,
    SIGNAL_AI_UPDATED,
    LeftAt,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.convert import fill_contribution
from custom_components.parcels.dedup import (
    REASON_SAME_MERCHANT_DAY,
    Contribution,
    apply_contribution,
)
from custom_components.parcels.engine import ParcelsEngine
from custom_components.parcels.mail.errors import MailError
from custom_components.parcels.models import (
    PARCELAPP_PREFIX,
    AutoMerge,
    MessageState,
    Origin,
    ParcelEvent,
    PickupRule,
    ReturnEntry,
    ReturnOrigin,
    Source,
    Suggestion,
    order_key,
)
from custom_components.parcels.parsers.auth import parse_authentication_results
from custom_components.parcels.parsers.base import Eta, MailMessage
from custom_components.parcels.services import MAX_LIST
from custom_components.parcels.views import (
    SYSTEM_VIEWER,
    Viewer,
    async_viewer,
    mailbox_owner,
    viewer_for,
)
from custom_components.parcels.websocket import OVERRIDES_SCHEMA, UPDATE_DELAY

from .common import (
    ADDRESS,
    OTHER_OWNER,
    OWNER,
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    load_message,
    patch_mail_clients,
)
from .factories import contribution

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
# DPD's e-mail with the code to give the driver for this parcel.
DPD_CODE_MAIL = "carriers/dpd_delivery_code_pt.eml"
DPD_NUMBER = "09381726450517"
DPD_CODE = "4821"
# Amazon's e-mail with a delivery code for an order Parcels doesn't know.
AMAZON_CODE_MAIL = "amazon/delivery_code_es.eml"
# What someone who may not see a private parcel gets instead of its details.
HIDDEN = {
    "merchant": None,
    "seller": None,
    "carrier": None,
    "carrier_name": None,
    "tracking_number": None,
    "tracking_url": None,
    "pickup_point": None,
    "pickup_code": None,
    "has_code": False,
    "collect_by": None,
    "left_at": None,
    "order_numbers": [],
    "references": [],
    "items": [],
    "source": "parser",
    "ai": False,
    "ai_filled": False,
    "auto_merged": None,
    "inferred": False,
    "inferred_reason": None,
    "origins": [],
    "shipment_group": None,
    "name": None,
    "eta_source": None,
    "senders": [],
    "ordered_at": None,
    "shipped_at": None,
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
        "removed",
    }
    assert not filtered["removed"]
    assert filtered["sender_domain"] == FILTERED_SENDER
    assert filtered["subject"] == "A sua encomenda está a caminho"
    assert snapshot["settings"] == {
        "user_is_admin": True,
        "ai_enabled": False,
        "ai_mode": "suggest",
        "ai_queue": 0,
        "ai_queue_seconds": None,
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
    # The code is in the list for whoever may see the parcel.
    assert alex[alex_parcel]["pickup_code"] == "4711"
    assert alex[alex_parcel]["has_code"]
    assert seen[alex_parcel] == {**alex[alex_parcel], **HIDDEN}
    assert seen[alex_parcel]["owners"] == [OWNER]
    assert seen[sam_parcel]["owners"] == [OTHER_OWNER]
    assert sam_view["review"] == sam_view["filtered"] == []
    assert not sam_view["settings"]["user_is_admin"]

    await refused(sam_ws, "parcels/get", "not_allowed", parcel_id=alex_parcel)
    await refused(sam_ws, "parcels/get", "not_allowed", parcel_id=system_parcel)
    await refused(ws, "parcels/get", "not_allowed", parcel_id=sam_parcel)
    await refused(ws, "parcels/get", "unknown_parcel", parcel_id="p_missing")
    shown = await result(ws, "parcels/get", parcel_id=alex_parcel)
    assert shown["parcel"]["pickup_code"] == "4711"
    mine = await result(sam_ws, "parcels/get", parcel_id=sam_parcel)
    assert mine["parcel"]["tracking_number"] == DHL_NUMBER
    unowned = await result(ws, "parcels/get", parcel_id=system_parcel)
    assert unowned["parcel"]["tracking_number"] == OTHER_DHL_NUMBER
    assert no_errors_logged(caplog)


async def test_delivery_code_mail(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    client: FakeMailClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A delivery code e-mail fills in its parcel's details and nothing else.

    It makes no parcel of its own. The page's list has the code until the
    parcel arrives, even a delivery that's only inferred; the entities and
    the logs never do.
    """
    caplog.set_level(logging.DEBUG, logger="custom_components.parcels")
    freezer.move_to("2026-11-20 09:00:00+00:00")
    parcel_id = await add(hass, DPD_NUMBER, carrier="dpd")
    parcels = set(engine.data.parcels)
    client.add(DPD_CODE_MAIL)
    client.add(AMAZON_CODE_MAIL)
    (mailbox,) = engine.mailboxes.values()
    assert mailbox.coordinator is not None

    await mailbox.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert set(engine.data.parcels) == parcels
    listed = {p["id"]: p for p in (await result(ws, "parcels/list"))["parcels"]}
    assert listed[parcel_id]["has_code"]
    assert listed[parcel_id]["pickup_code"] == DPD_CODE
    shown = await result(ws, "parcels/get", parcel_id=parcel_id)
    assert shown["parcel"]["pickup_code"] == DPD_CODE
    code = re.compile(rf"(?<![0-9A-Za-z]){DPD_CODE}(?![0-9A-Za-z])")
    for state in hass.states.async_all():
        assert not code.search(f"{state.state} {dict(state.attributes)}"), state
    assert not code.search(caplog.text)

    parcel = engine.data.parcels[parcel_id]
    parcel.events.append(
        ParcelEvent(
            time=dt_util.utcnow(),
            source=Source.PARSER,
            status=ParcelStatus.DELIVERED,
            inferred=True,
        )
    )
    parcel.touch(dt_util.utcnow())
    assert parcel.state.pickup_code == DPD_CODE
    listed = {p["id"]: p for p in (await result(ws, "parcels/list"))["parcels"]}
    assert listed[parcel_id]["pickup_code"] is None


async def test_ai_filled(
    hass: HomeAssistant, engine: ParcelsEngine, ws: MockHAClientWebSocket
) -> None:
    """A parcel shows what the AI filled in until someone confirms it."""
    data = engine.data
    now = dt_util.utcnow()
    applied = apply_contribution(
        data, contribution("msg:m1#0", carrier="ctt", number=CTT_NUMBER), now
    )
    fill = fill_contribution(
        Suggestion(kind=MailKind.SHIPPED, eta_start=date(2026, 11, 20)),
        message_hash="m1",
        time=now,
    )
    assert fill is not None
    assert apply_contribution(data, fill, now).parcel_id == applied.parcel_id

    listed = {p["id"]: p for p in (await result(ws, "parcels/list"))["parcels"]}
    shown = listed[applied.parcel_id]
    assert shown["ai_filled"]
    assert not shown["ai"]
    assert shown["eta_start"] == "2026-11-20"

    await hass.services.async_call(
        DOMAIN,
        "update",
        {"parcel_id": applied.parcel_id, "confirm": True},
        blocking=True,
    )

    listed = {p["id"]: p for p in (await result(ws, "parcels/list"))["parcels"]}
    assert not listed[applied.parcel_id]["ai_filled"]


async def test_parcel_app_name_and_date(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
) -> None:
    """A parcel shows its Parcel app name and where its date came from.

    Someone who may not see the parcel still sees when it comes, but neither.
    """
    (parcel_id,) = engine.data.parcels
    now = dt_util.utcnow()
    origin = Origin(
        id=PARCELAPP_PREFIX + CTT_NUMBER,
        source=Source.PARCELAPP,
        time=now,
        carrier="ctt",
        tracking_number=CTT_NUMBER,
        name="Desk lamp",
    )
    expected = Eta(start=date(2026, 11, 19), end=date(2026, 11, 19))
    delivery = Contribution(
        origin=origin,
        events=[ParcelEvent(time=now, source=Source.PARCELAPP, eta=expected)],
    )
    assert apply_contribution(engine.data, delivery, now).parcel_id == parcel_id

    listed = {p["id"]: p for p in (await result(ws, "parcels/list"))["parcels"]}
    shown = listed[parcel_id]
    assert (shown["name"], shown["eta_source"]) == ("Desk lamp", "parcelapp")
    assert shown["eta_start"] == "2026-11-19"

    await call(hass, "update", {"parcel_id": parcel_id, "private": True})
    seen = {p["id"]: p for p in (await result(sam_ws, "parcels/list"))["parcels"]}
    assert seen[parcel_id]["restricted"]
    assert (seen[parcel_id]["name"], seen[parcel_id]["eta_source"]) == (None, None)
    assert seen[parcel_id]["eta_start"] == "2026-11-19"


async def test_parcel_app_day_only_delivery(
    engine: ParcelsEngine, ws: MockHAClientWebSocket
) -> None:
    """A delivery the Parcel app gives the day of, but not the time, says so.

    The parcel, its timeline and the row of its source tell the time isn't
    known, so the card shows the day alone.
    """
    (parcel_id,) = engine.data.parcels
    now = dt_util.utcnow()
    origin = Origin(
        id=PARCELAPP_PREFIX + CTT_NUMBER,
        source=Source.PARCELAPP,
        time=now,
        carrier="ctt",
        tracking_number=CTT_NUMBER,
    )
    delivery = Contribution(
        origin=origin,
        events=[
            ParcelEvent(
                time=now - timedelta(hours=1),
                source=Source.PARCELAPP,
                status=ParcelStatus.DELIVERED,
                undated=True,
                timeless=True,
                by=now,
            )
        ],
    )
    assert apply_contribution(engine.data, delivery, now).parcel_id == parcel_id

    listed = {p["id"]: p for p in (await result(ws, "parcels/list"))["parcels"]}
    shown = listed[parcel_id]
    assert (shown["status_undated"], shown["status_timeless"]) == (True, True)
    assert (shown["delivered_undated"], shown["delivered_timeless"]) == (True, True)
    details = await result(ws, "parcels/get", parcel_id=parcel_id)
    assert [
        (entry["status"], entry["undated"], entry["timeless"])
        for entry in details["timeline"]
    ] == [("in_transit", False, False), ("delivered", True, True)]
    assert [
        (row["source"], row["undated"], row["timeless"]) for row in details["origins"]
    ] == [("parser", False, False), ("parcelapp", True, True)]


async def test_marketplace_seller(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
) -> None:
    """A parcel shows who sold it on a marketplace, unless it's hidden."""
    (parcel_id,) = engine.data.parcels
    now = dt_util.utcnow()
    shop = contribution(
        "msg:lm1#0",
        time=now,
        carrier="ctt",
        number=CTT_NUMBER,
        merchant="Leroy Merlin",
        seller="Loja Exemplo (Exemplo Lda)",
        label="leroymerlin.pt",
    )
    assert apply_contribution(engine.data, shop, now).parcel_id == parcel_id

    listed = {p["id"]: p for p in (await result(ws, "parcels/list"))["parcels"]}
    assert listed[parcel_id]["seller"] == "Loja Exemplo (Exemplo Lda)"

    await call(hass, "update", {"parcel_id": parcel_id, "private": True})
    seen = {p["id"]: p for p in (await result(sam_ws, "parcels/list"))["parcels"]}
    assert seen[parcel_id]["restricted"]
    assert seen[parcel_id]["seller"] is None


async def test_attempt_pickup_and_delivery_details(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
) -> None:
    """A parcel shows its next attempt, its collect-by day and where it was left.

    Someone who may not see the parcel sees only when it comes again.
    """
    (parcel_id,) = engine.data.parcels
    now = dt_util.utcnow()

    def news(index: int, status: ParcelStatus, minutes: int, **details: Any) -> None:
        mail = contribution(
            f"msg:ctt{index}#0",
            time=now - timedelta(minutes=minutes),
            carrier="ctt",
            number=CTT_NUMBER,
            status=status,
        )
        mail.events[0] = replace(mail.events[0], **details)
        assert apply_contribution(engine.data, mail, now).parcel_id == parcel_id

    async def shown(socket: MockHAClientWebSocket) -> tuple[Any, ...]:
        listed = (await result(socket, "parcels/list"))["parcels"]
        (parcel,) = (p for p in listed if p["id"] == parcel_id)
        return (
            parcel["status"],
            parcel["status_reported"],
            parcel["next_attempt"],
            parcel["collect_by"],
            parcel["left_at"],
        )

    # The e-mail gives no time for the attempt: its own time stands in.
    news(
        1,
        ParcelStatus.ATTEMPTED,
        60,
        next_attempt=date(2026, 11, 18),
        collect_by=date(2026, 11, 25),
    )
    missed = ("attempted", True, "2026-11-18", "2026-11-25", None)
    assert await shown(ws) == missed
    await call(hass, "update", {"parcel_id": parcel_id, "private": True})
    assert await shown(sam_ws) == ("attempted", True, "2026-11-18", None, None)

    news(2, ParcelStatus.DELIVERED, 30, left_at=LeftAt.NEIGHBOUR)
    assert await shown(ws) == ("delivered", True, None, None, "neighbour")
    assert await shown(sam_ws) == ("delivered", True, None, None, None)


async def test_check_again(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
    sam: User,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An administrator reads a parcel's e-mails again; the parcel stays."""
    (parcel_id,) = engine.data.parcels
    sam_parcel = await add(hass, DHL_NUMBER, user=sam, carrier="dhl", private=True)

    counts = await result(ws, "parcels/parcel/check_again", parcel_id=parcel_id)

    assert counts == {"read": 1, "queued": 0, "gone": 0, "failed": 0}
    assert parcel_id in engine.data.parcels
    await refused(ws, "parcels/parcel/check_again", "not_allowed", parcel_id=sam_parcel)
    await refused(
        ws, "parcels/parcel/check_again", "unknown_parcel", parcel_id="p_missing"
    )
    assert no_errors_logged(caplog)
    err = await error(sam_ws, "parcels/parcel/check_again", parcel_id=sam_parcel)
    assert err["code"] == "unauthorized"


async def test_shipments(
    engine: ParcelsEngine, ws: MockHAClientWebSocket, sam_ws: MockHAClientWebSocket
) -> None:
    """Packages sent together are one shipment, of the packages the user sees."""
    data = engine.data
    now = dt_util.utcnow()
    packages = [
        apply_contribution(
            data,
            contribution(
                f"msg:gls{n}#0",
                kind=MailKind.IN_TRANSIT,
                time=datetime(2026, 11, 16, 18, 50 + n, tzinfo=UTC),
                carrier="gls",
                number=f"6100001231005{n}",
                merchant="Loja Exemplo",
                label=SHOP,
                owner=OWNER,
                private=private,
            ),
            now,
        ).parcel_id
        for n, private in ((1, False), (2, True))
    ]
    engine.async_changed()

    alex = {p["id"]: p for p in (await result(ws, "parcels/list"))["parcels"]}
    sam = {p["id"]: p for p in (await result(sam_ws, "parcels/list"))["parcels"]}
    details = await result(ws, "parcels/get", parcel_id=packages[1])

    shipment = min(packages)
    assert [alex[parcel_id]["shipment_group"] for parcel_id in packages] == [
        shipment,
        shipment,
    ]
    assert details["parcel"]["shipment_group"] == shipment
    # Sam doesn't see Alex's private package, nor that it's in the shipment.
    assert [sam[parcel_id]["shipment_group"] for parcel_id in packages] == [
        None,
        None,
    ]


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
    """The details have the timeline, the tracking link, the pickup and e-mails.

    The delivery code shows until the parcel is delivered.
    """
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
    before = (await result(ws, "parcels/get", parcel_id=parcel_id))["parcel"]
    assert (before["pickup_point"], before["pickup_code"]) == ("Locker 12", "4711")
    freezer.tick(timedelta(minutes=5))
    await call(hass, "mark_delivered", {"parcel_id": parcel_id})

    details = await result(ws, "parcels/get", parcel_id=parcel_id)

    shown = details["parcel"]
    assert CTT_NUMBER in shown["tracking_url"]
    assert (shown["pickup_point"], shown["pickup_code"]) == ("Locker 12", None)
    assert shown["eta_start"] == "2026-11-19"
    # The edits stay with the parcel; only the e-mail can be split off.
    assert shown["origins"] == [mail_origin]
    # What each e-mail and source said and brought, oldest first.
    assert details["origins"] == [
        {
            "id": mail_origin,
            "source": "parser",
            "label": "ctt.pt",
            "sender_name": "CTT",
            "name": None,
            "time": "2026-11-17T08:05:00+00:00",
            "status": "in_transit",
            "kind": "in_transit",
            "event_time": "2026-11-17T08:05:00+00:00",
            "undated": False,
            "timeless": False,
            "dayless": False,
            "eta_start": "2026-11-19",
            "eta_end": "2026-11-19",
            "window_start": None,
            "window_end": None,
            "carrier": "ctt",
            "carrier_name": "CTT",
            "tracking_number": CTT_NUMBER,
            "reference": None,
            "merchant": "Worten",
            "seller": None,
            "order_numbers": [],
            "items": [],
            "pickup_point": None,
            "shipment": None,
            "email": True,
            "edits": False,
            "part_of": None,
            # It's the parcel's only e-mail.
            "split_blocked": "nothing_left",
        },
        {
            "id": f"man:{parcel_id}",
            "source": "manual",
            "label": "",
            "sender_name": None,
            "name": None,
            "time": "2026-11-17T10:10:00+00:00",
            "status": "delivered",
            "kind": "delivered",
            "event_time": "2026-11-17T10:10:00+00:00",
            "undated": False,
            "timeless": False,
            "dayless": False,
            "eta_start": "2026-11-19",
            "eta_end": "2026-11-19",
            "window_start": None,
            "window_end": None,
            "carrier": None,
            "carrier_name": None,
            "tracking_number": None,
            "reference": None,
            "merchant": None,
            "seller": None,
            "order_numbers": [],
            "items": [],
            "pickup_point": "Locker 12",
            "shipment": None,
            "email": False,
            "edits": True,
            "part_of": None,
            "split_blocked": None,
        },
    ]
    # The ETA change isn't a step on the way.
    assert details["timeline"] == [
        {
            "time": "2026-11-17T08:05:00+00:00",
            "status": "in_transit",
            "source": "parser",
            "label": "",
            "undated": False,
            "timeless": False,
        },
        {
            "time": "2026-11-17T10:10:00+00:00",
            "status": "delivered",
            "source": "manual",
            "label": "",
            "undated": False,
            "timeless": False,
        },
    ]
    assert (shown["status_undated"], shown["delivered_undated"]) == (False, False)
    assert (shown["status_timeless"], shown["delivered_timeless"]) == (False, False)
    assert details["orders"] == []


async def test_get_origin_rows(
    engine: ParcelsEngine, ws: MockHAClientWebSocket
) -> None:
    """Each e-mail and source shows what it said and what it brought.

    An order's Amazon shipments are numbered, 17TRACK, the Parcel app and
    the local AI show as such, and e-mails that share a tracking number
    can't be moved apart.
    """
    data = engine.data
    now = dt_util.utcnow()
    order = "405-1234567-7654321"
    amazon = {"merchant": "Amazon", "orders": [order], "label": "amazon.es"}
    gloves = apply_contribution(
        data,
        contribution(
            "msg:az1#0",
            time=now - timedelta(hours=3),
            carrier="dhl",
            number=DHL_NUMBER,
            shipment_id="SHIPMENT1",
            items=["Garden gloves", "Rain jacket"],
            **amazon,
        ),
        now,
    ).parcel_id
    lamp = apply_contribution(
        data,
        contribution(
            "msg:az2#0",
            time=now - timedelta(hours=2),
            carrier="dhl",
            number=OTHER_DHL_NUMBER,
            shipment_id="SHIPMENT2",
            items=["Desk lamp"],
            **amazon,
        ),
        now,
    ).parcel_id
    assert lamp != gloves
    carrier_mail = contribution(
        "msg:dhl1#0",
        kind=MailKind.IN_TRANSIT,
        time=now - timedelta(hours=1),
        carrier="dhl",
        number=DHL_NUMBER,
        label="dhl.com",
    )
    assert apply_contribution(data, carrier_mail, now).parcel_id == gloves
    for origin, status, minutes in (
        (
            Origin(
                id="17t:" + DHL_NUMBER,
                source=Source.SEVENTEENTRACK,
                time=now - timedelta(minutes=30),
                label="17TRACK",
                carrier="dhl",
                tracking_number=DHL_NUMBER,
            ),
            ParcelStatus.IN_TRANSIT,
            30,
        ),
        (
            Origin(
                id=PARCELAPP_PREFIX + DHL_NUMBER,
                source=Source.PARCELAPP,
                time=now - timedelta(minutes=10),
                label="Parcel app",
                carrier="dhl",
                tracking_number=DHL_NUMBER,
                name="Gloves",
            ),
            ParcelStatus.OUT_FOR_DELIVERY,
            10,
        ),
    ):
        event = ParcelEvent(
            time=now - timedelta(minutes=minutes), source=origin.source, status=status
        )
        tracked = Contribution(origin=origin, events=[event])
        assert apply_contribution(data, tracked, now).parcel_id == gloves
    fill = fill_contribution(
        Suggestion(kind=MailKind.SHIPPED, eta_start=date(2026, 11, 20)),
        message_hash="az1",
        time=now,
        label="amazon.es",
    )
    assert fill is not None
    assert apply_contribution(data, fill, now).parcel_id == gloves

    rows = (await result(ws, "parcels/get", parcel_id=gloves))["origins"]

    said = [
        (
            row["source"],
            row["label"],
            row["sender_name"],
            row["name"],
            row["status"],
            row["kind"],
            row["eta_start"],
            row["email"],
        )
        for row in rows
    ]
    assert said == [
        ("parser", "amazon.es", "Amazon", None, "shipped", "shipped", None, True),
        ("parser", "dhl.com", "DHL", None, "in_transit", "in_transit", None, True),
        ("seventeentrack", "17TRACK", None, None, "in_transit", None, None, False),
        (
            "parcelapp",
            "Parcel app",
            None,
            "Gloves",
            "out_for_delivery",
            None,
            None,
            False,
        ),
        ("ai", "amazon.es", "Amazon", None, None, None, "2026-11-20", True),
    ]
    first = rows[0]
    assert first["items"] == ["Garden gloves", "Rain jacket"]
    assert (first["merchant"], first["order_numbers"]) == ("Amazon", [order])
    assert (first["carrier_name"], first["tracking_number"]) == ("DHL", DHL_NUMBER)
    # The shipment is shown by its place in the order, never by its ID.
    assert first["shipment"] == [1, 2]
    assert "SHIPMENT1" not in str(rows)
    assert [row["shipment"] for row in rows[1:]] == [None] * 4
    # What the AI read is part of its e-mail: they move together, and the
    # tracking number holds the e-mails together.
    assert [row["part_of"] for row in rows] == [None] * 4 + ["msg:az1#0"]
    assert [row["split_blocked"] for row in rows] == ["shared_number"] * 5
    assert not any(row["edits"] for row in rows)

    other = (await result(ws, "parcels/get", parcel_id=lamp))["origins"]
    assert [(row["shipment"], row["split_blocked"]) for row in other] == [
        ([2, 2], "nothing_left")
    ]


async def test_list_senders_and_dates(
    hass: HomeAssistant, engine: ParcelsEngine, ws: MockHAClientWebSocket
) -> None:
    """A parcel lists who told about it, and when it was ordered and sent.

    Each e-mail counts once, with or without the local AI's reading, and the
    user's edits don't count. Only dated news gives the days.
    """
    data = engine.data
    now = dt_util.utcnow()
    amazon = {"merchant": "Amazon", "orders": ["405-1234567-7654321"]}
    ctt = {"carrier": "ctt", "number": SHOP_NUMBER}
    mails = [
        contribution(
            "msg:az1#0",
            kind=MailKind.ORDER,
            time=now - timedelta(days=3),
            items=["Garden gloves"],
            label="amazon.es",
            **amazon,
        ),
        # Its date isn't known: it doesn't say when the parcel left.
        contribution(
            "msg:ctt1#0",
            kind=MailKind.IN_TRANSIT,
            time=now - timedelta(days=2, hours=12),
            undated=True,
            label="ctt.pt",
            **ctt,
        ),
        contribution(
            "msg:az2#0",
            time=now - timedelta(days=2),
            label="amazon.es",
            **amazon,
            **ctt,
        ),
        contribution(
            "msg:ctt2#0",
            kind=MailKind.IN_TRANSIT,
            time=now - timedelta(days=1),
            label="ctt.pt",
            **ctt,
        ),
    ]
    tracked = Contribution(
        origin=Origin(
            id="17t:" + SHOP_NUMBER,
            source=Source.SEVENTEENTRACK,
            time=now - timedelta(hours=12),
            label="17TRACK",
            carrier="ctt",
            tracking_number=SHOP_NUMBER,
        ),
        events=[
            ParcelEvent(
                time=now - timedelta(hours=12),
                source=Source.SEVENTEENTRACK,
                status=ParcelStatus.IN_TRANSIT,
            )
        ],
    )
    fill = fill_contribution(
        Suggestion(kind=MailKind.SHIPPED, eta_start=date(2026, 11, 19)),
        message_hash="az2",
        time=now,
        label="amazon.es",
    )
    assert fill is not None
    for item in (*mails, tracked, fill):
        parcel_id = apply_contribution(data, item, now).parcel_id
    assert len(data.parcels[parcel_id].origins) == 6
    await call(hass, "update", {"parcel_id": parcel_id, "pickup_point": "Locker 12"})

    parcels = (await result(ws, "parcels/list"))["parcels"]

    (shown,) = [parcel for parcel in parcels if parcel["id"] == parcel_id]
    assert shown["senders"] == [
        {"name": "Amazon", "source": "email", "carrier": False, "count": 2},
        {"name": "CTT", "source": "email", "carrier": True, "count": 2},
        {"name": "17TRACK", "source": "seventeentrack", "carrier": False, "count": 1},
    ]
    assert shown["ordered_at"] == "2026-11-14T10:00:00+00:00"
    assert shown["shipped_at"] == "2026-11-15T10:00:00+00:00"


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


async def test_review_accept_reference(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
    review: dict[str, str],
) -> None:
    """An e-mail with only Paack's shipment reference can be added.

    The page shows the reference, except to someone who may not see it.
    """
    reference = "Wx4Hn8Tz3"
    accepted = await result(
        ws,
        "parcels/review/accept",
        review_id=review[UPS],
        overrides={"kind": "delivered", "carrier": "paack", "reference": reference},
    )

    (parcel_id,) = accepted["parcel_ids"]
    state = engine.data.parcels[parcel_id].state
    assert (state.tracking_number, state.references) == (None, (reference,))
    shown = (await result(ws, "parcels/get", parcel_id=parcel_id))["parcel"]
    assert (shown["status"], shown["references"]) == ("delivered", [reference])
    await call(hass, "update", {"parcel_id": parcel_id, "private": True})
    seen = {p["id"]: p for p in (await result(sam_ws, "parcels/list"))["parcels"]}
    assert seen[parcel_id]["references"] == []


async def test_review_accept_cancels_nothing(
    engine: ParcelsEngine, ws: MockHAClientWebSocket, review: dict[str, str]
) -> None:
    """Cancelling an order that has no parcel adds nothing."""
    parcels = set(engine.data.parcels)

    accepted = await result(
        ws,
        "parcels/review/accept",
        review_id=review[UPS],
        overrides={"kind": "cancelled", "order_numbers": ["#5150"]},
    )

    assert accepted == {"parcel_ids": []}
    assert set(engine.data.parcels) == parcels
    assert review[UPS] not in engine.data.review


async def test_review_teaches_a_shops_carrier(
    engine: ParcelsEngine, review: dict[str, str]
) -> None:
    """Accepting teaches the carrier of a shop, but not of Amazon.

    Amazon hands its parcels to many carriers.
    """
    shop = engine.data.review[review[SHOP]]
    engine.data.review["r_amazon"] = replace(
        shop, id="r_amazon", message="f" * 64, sender_domain="amazon.es"
    )
    engine.review_accept(
        "r_amazon",
        {
            "carrier": "ctt_expresso",
            "tracking_numbers": [],
            "order_numbers": ["171-0000001-0000001"],
        },
    )
    engine.review_accept(review[SHOP], {"carrier": "ctt"})

    assert engine.prefill(None, "amazon.es") is None
    assert engine.prefill(None, SHOP) == Suggestion(
        kind=MailKind.UNKNOWN, carrier="ctt"
    )
    assert engine.prefill(None, "cttexpresso.pt") == Suggestion(
        kind=MailKind.UNKNOWN, carrier="ctt_expresso"
    )
    assert engine.prefill(None, "vinted.pt") == Suggestion(
        kind=MailKind.UNKNOWN, carrier="vinted_go"
    )


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


async def test_filtered_clear(
    engine: ParcelsEngine, ws: MockHAClientWebSocket, client: FakeMailClient
) -> None:
    """A cleared e-mail leaves the filtered list and is never read again."""
    (filtered_id,) = engine.data.filtered
    message = engine.data.filtered[filtered_id].message

    assert await result(ws, "parcels/filtered/clear", filtered_id=filtered_id) is None

    assert (await result(ws, "parcels/list"))["filtered"] == []
    assert engine.data.messages[message].state is MessageState.DISMISSED
    await refused(
        ws, "parcels/filtered/clear", "unknown_filtered", filtered_id=filtered_id
    )
    # The mailbox reports the e-mail again: it isn't downloaded or listed.
    fetches = len(client.fetches)
    client.add("common/unknown_phone_only.eml")
    (mailbox,) = engine.mailboxes.values()
    assert mailbox.coordinator is not None
    await mailbox.coordinator.async_refresh()
    assert len(client.fetches) == fetches
    assert not engine.data.filtered
    assert engine.data.messages[message].state is MessageState.DISMISSED


async def test_filtered_clear_all(
    engine: ParcelsEngine, ws: MockHAClientWebSocket
) -> None:
    """Clear all empties the filtered list; the e-mails stay known."""
    data = engine.data
    (entry,) = data.filtered.values()
    data.messages["other"] = replace(data.messages[entry.message], hash="other")
    data.filtered["f_other"] = replace(entry, id="f_other", message="other")

    assert await result(ws, "parcels/filtered/clear_all") == {"cleared": 2}

    assert not data.filtered
    states = {data.messages[key].state for key in (entry.message, "other")}
    assert states == {MessageState.DISMISSED}
    assert (await result(ws, "parcels/list"))["filtered"] == []
    assert await result(ws, "parcels/filtered/clear_all") == {"cleared": 0}


@pytest.mark.parametrize("command", ["clear", "clear_all"])
async def test_filtered_admin_only(
    engine: ParcelsEngine, sam_ws: MockHAClientWebSocket, command: str
) -> None:
    """Only administrators clear filtered e-mails."""
    (filtered_id,) = engine.data.filtered
    data = {"filtered_id": filtered_id} if command == "clear" else {}

    err = await error(sam_ws, f"parcels/filtered/{command}", **data)

    assert err["code"] == "unauthorized"
    assert filtered_id in engine.data.filtered


# -- Removing e-mails ---------------------------------------------------------


async def test_origin_remove(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    client: FakeMailClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An e-mail removed from Parcels takes what it added and isn't read again.

    It waits under Filtered, marked as removed. A parcel left with only the
    user's edits goes too: the answer's parcel_id is None.
    """
    ((parcel_id, parcel),) = engine.data.parcels.items()
    (origin_id,) = parcel.origins
    key = parcel.origins[origin_id].message
    assert key is not None
    await call(hass, "update", {"parcel_id": parcel_id, "pickup_point": "Locker 12"})

    removed = await result(
        ws, "parcels/origin/remove", parcel_id=parcel_id, origin_id=origin_id
    )

    assert not engine.data.parcels
    assert removed["parcel_id"] is None
    assert engine.data.messages[key].state is MessageState.FILTERED
    snapshot = await result(ws, "parcels/list")
    assert snapshot["parcels"] == []
    (entry,) = [f for f in snapshot["filtered"] if f["id"] == removed["filtered_id"]]
    assert entry == {
        "id": removed["filtered_id"],
        "created": "2026-11-17T10:00:00+00:00",
        "received": "2026-11-17T08:05:00+00:00",
        "sender": "CTT",
        "sender_domain": "ctt.pt",
        "subject": "",
        "removed": True,
    }
    # The mailbox reports the e-mail again: it isn't downloaded or read.
    fetches = len(client.fetches)
    client.add("carriers/ctt_in_transit_pt.eml")
    (mailbox,) = engine.mailboxes.values()
    assert mailbox.coordinator is not None
    await mailbox.coordinator.async_refresh()
    assert len(client.fetches) == fetches
    assert not engine.data.parcels
    assert engine.data.messages[key].state is MessageState.FILTERED
    assert no_errors_logged(caplog)


async def test_origin_remove_everywhere(
    engine: ParcelsEngine, ws: MockHAClientWebSocket
) -> None:
    """A removed e-mail leaves every parcel it was part of; the others stay.

    Parcels doesn't need to have kept the e-mail's record.
    """
    data = engine.data
    now = dt_util.utcnow()
    first = apply_contribution(
        data,
        contribution("msg:both#0", carrier="dhl", number=DHL_NUMBER, label="dhl.com"),
        now,
    ).parcel_id
    second = apply_contribution(
        data,
        contribution(
            "msg:both#1", carrier="dhl", number=OTHER_DHL_NUMBER, label="dhl.com"
        ),
        now,
    ).parcel_id
    kept = apply_contribution(
        data,
        contribution(
            "msg:dhl#0",
            kind=MailKind.IN_TRANSIT,
            carrier="dhl",
            number=DHL_NUMBER,
            label="dhl.com",
        ),
        now,
    )
    assert kept.parcel_id == first
    assert "both" not in data.messages

    removed = await result(
        ws, "parcels/origin/remove", parcel_id=first, origin_id="msg:both#0"
    )

    assert removed["parcel_id"] == first
    assert second not in data.parcels
    assert list(data.parcels[first].origins) == ["msg:dhl#0"]
    assert data.messages["both"].state is MessageState.FILTERED
    (entry,) = [f for f in data.filtered.values() if f.removed]
    assert (entry.message, entry.sender, entry.sender_domain) == (
        "both",
        "DHL",
        "dhl.com",
    )


async def test_origin_remove_refused(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
    sam: User,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only administrators remove, only e-mails, from parcels they may see."""
    data = engine.data
    ((parcel_id, parcel),) = data.parcels.items()
    (origin_id,) = parcel.origins
    await call(hass, "update", {"parcel_id": parcel_id, "pickup_point": "Locker 12"})
    now = dt_util.utcnow()
    tracked = Origin(
        id=PARCELAPP_PREFIX + CTT_NUMBER,
        source=Source.PARCELAPP,
        time=now,
        label="Parcel app",
        carrier="ctt",
        tracking_number=CTT_NUMBER,
    )
    event = ParcelEvent(time=now, source=Source.PARCELAPP, status=ParcelStatus.SHIPPED)
    assert (
        apply_contribution(data, Contribution(origin=tracked, events=[event]), now)
    ).parcel_id == parcel_id
    sam_parcel = await add(hass, DHL_NUMBER, user=sam, carrier="dhl", private=True)
    (sam_origin,) = data.parcels[sam_parcel].origins
    remove = "parcels/origin/remove"

    err = await error(sam_ws, remove, parcel_id=parcel_id, origin_id=origin_id)
    assert err["code"] == "unauthorized"
    # Home Assistant logs that refusal itself; the others aren't errors.
    caplog.clear()
    await refused(ws, remove, "unknown_parcel", parcel_id="p_missing", origin_id="x")
    await refused(ws, remove, "not_allowed", parcel_id=sam_parcel, origin_id=sam_origin)
    await refused(ws, remove, "unknown_origin", parcel_id=parcel_id, origin_id="x")
    for not_mail in (f"man:{parcel_id}", tracked.id):
        await refused(
            ws, remove, "not_an_email", parcel_id=parcel_id, origin_id=not_mail
        )

    assert set(data.parcels[parcel_id].origins) == {
        origin_id,
        f"man:{parcel_id}",
        tracked.id,
    }
    assert not [entry for entry in data.filtered.values() if entry.removed]
    assert no_errors_logged(caplog)


@pytest.mark.parametrize("linked", [False, True], ids=["private", "linked"])
async def test_return_remove_refused(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
    linked: bool,
) -> None:
    """An administrator may not remove a private return they may not see.

    A return is private when it is, or when a parcel of its order is.
    """
    now = dt_util.utcnow()
    entry = ReturnEntry(id="ret_1", created=now, updated=now, private=not linked)
    entry.origins["m-sam"] = ReturnOrigin(
        message="m-sam",
        time=now,
        merchant="Loja Exemplo",
        order_numbers=("LE-1001",),
        pickup=dt_util.now().date(),
        pickup_rule=PickupRule.EMAIL,
        owners=(OTHER_OWNER,),
    )
    engine.data.returns[entry.id] = entry
    if linked:
        apply_contribution(
            engine.data,
            contribution(
                "msg:sam#0",
                time=now,
                merchant="Loja Exemplo",
                orders=["LE-1001"],
                number=DHL_NUMBER,
                carrier="dhl",
                owner=OTHER_OWNER,
                private=True,
            ),
            now,
        )

    await refused(ws, "parcels/return/remove", "not_allowed", return_id=entry.id)
    assert entry.id in engine.data.returns

    err = await error(sam_ws, "parcels/return/remove", return_id=entry.id)
    assert err["code"] == "unauthorized"


async def test_origin_restore(
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    client: FakeMailClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Restoring a removed e-mail reads it again into a parcel.

    The answer names the parcels it's in now. While its mailbox can't give
    it, it stays removed; once it's gone from the mailbox, it waits for
    review.
    """
    data = engine.data
    (parcel,) = data.parcels.values()
    (origin_id,) = parcel.origins
    key = parcel.origins[origin_id].message
    assert key is not None
    (provider_id,) = data.messages[key].refs.values()

    async def remove() -> str:
        (parcel_id,) = data.parcels
        removed = await result(
            ws, "parcels/origin/remove", parcel_id=parcel_id, origin_id=origin_id
        )
        assert not data.parcels
        return str(removed["filtered_id"])

    filtered_id = await remove()
    restored = await result(ws, "parcels/review/restore", filtered_id=filtered_id)

    (parcel,) = data.parcels.values()
    assert restored == {"review_id": None, "parcel_ids": [parcel.id]}
    assert (parcel.state.tracking_number, list(parcel.origins)) == (
        CTT_NUMBER,
        [origin_id],
    )
    assert data.messages[key].state is MessageState.APPLIED
    assert filtered_id not in data.filtered

    filtered_id = await remove()
    client.fetch_errors[provider_id] = MailError("Mailbox down")
    await refused(
        ws, "parcels/review/restore", "message_unavailable", filtered_id=filtered_id
    )
    assert data.filtered[filtered_id].removed
    assert data.messages[key].state is MessageState.FILTERED

    del client.fetch_errors[provider_id]
    client.delete(provider_id)
    restored = await result(ws, "parcels/review/restore", filtered_id=filtered_id)

    assert restored["parcel_ids"] == []
    review = data.review[restored["review_id"]]
    assert (review.message, review.reason, review.sender_domain) == (
        key,
        "restored",
        "ctt.pt",
    )
    assert filtered_id not in data.filtered
    assert not data.parcels
    assert no_errors_logged(caplog)


async def test_origin_restore_brings_the_parcel_back(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
) -> None:
    """A removed e-mail, restored, brings its parcel back as it was.

    The same parcel, still private, with the user's edits, the merge to check
    and the refused delivery; automations don't hear of it as a new parcel.
    """
    data = engine.data
    ((parcel_id, parcel),) = data.parcels.items()
    (origin_id,) = parcel.origins
    await call(
        hass,
        "update",
        {"parcel_id": parcel_id, "pickup_point": "Locker 12", "private": True},
    )
    parcel.delivery_rejected = True
    flag = AutoMerge(origin_id, dt_util.utcnow(), REASON_SAME_MERCHANT_DAY)
    parcel.auto_merged = flag
    removed = await result(
        ws, "parcels/origin/remove", parcel_id=parcel_id, origin_id=origin_id
    )
    assert not data.parcels
    events = [
        async_capture_events(hass, name)
        for name in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED)
    ]

    restored = await result(
        ws, "parcels/review/restore", filtered_id=removed["filtered_id"]
    )
    await hass.async_block_till_done()

    assert restored == {"review_id": None, "parcel_ids": [parcel_id]}
    parcel = data.parcels[parcel_id]
    assert set(parcel.origins) == {origin_id, f"man:{parcel_id}"}
    assert (parcel.state.tracking_number, parcel.state.pickup_point) == (
        CTT_NUMBER,
        "Locker 12",
    )
    assert (parcel.private, parcel.delivery_rejected) == (True, True)
    assert parcel.auto_merged == flag
    assert events == [[], [], []]
    seen = {p["id"]: p for p in (await result(sam_ws, "parcels/list"))["parcels"]}
    assert seen[parcel_id]["restricted"]
    key = parcel.origins[origin_id].message
    assert key is not None
    assert not data.messages[key].shells


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

    assert trusted == {"domain": SHOP, "added": 0, "rechecking": 1, "kept": 0}
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


def forged_shop_mail(number: int) -> MailMessage:
    """Return the shop's e-mail with a header the provider didn't write."""
    header = "mx.example.net; dkim=pass header.d=loja-exemplo.example"
    return replace(
        load_message(SHOP_MAIL, mailbox=ADDRESS),
        provider_id=f"forged-{number}",
        message_id=f"<forged-{number}@loja-exemplo.example>",
        auth=parse_authentication_results(header),
        auth_headers=(header,),
    )


async def test_trust_unverified_sender(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    client: FakeMailClient,
    ws: MockHAClientWebSocket,
) -> None:
    """Trusting a sender adds its e-mails that failed the checks, as seen.

    Later e-mails that fail the checks still need review, with a note.
    """
    data = engine.data
    (mailbox,) = engine.mailboxes.values()
    assert mailbox.coordinator is not None
    client.add(forged_shop_mail(1))
    await mailbox.coordinator.async_refresh()
    (forged,) = [r for r in data.review.values() if not r.authenticated]
    assert forged.reason == "untrusted_authserv"
    assert forged.checks == {
        "headers": 1,
        "servers": ["mx.example.net"],
        "used": None,
        "dkim": "",
        "dmarc": "",
        "spf": "",
        "originals": 0,
    }
    listed = {r["id"]: r for r in (await result(ws, "parcels/list"))["review"]}
    assert not listed[forged.id]["trusted_sender"]
    # Another of the shop's e-mails that failed, with nothing to add.
    data.messages["other"] = replace(data.messages[forged.message], hash="other")
    data.review["r_other"] = replace(
        forged, id="r_other", message="other", suggestion=None
    )

    trusted = await result(ws, "parcels/review/trust_sender", review_id=forged.id)
    await async_wait_reprocess(hass)

    assert trusted == {"domain": SHOP, "added": 1, "rechecking": 1, "kept": 1}
    assert data.senders[SHOP].trusted
    numbers = {p.state.tracking_number for p in data.parcels.values()}
    assert numbers == {CTT_NUMBER, SHOP_NUMBER}
    shop = [r for r in data.review.values() if r.sender_domain == SHOP]
    assert [r.id for r in shop] == ["r_other"]
    listed = {r["id"]: r for r in (await result(ws, "parcels/list"))["review"]}
    assert listed["r_other"]["trusted_sender"]

    client.add(forged_shop_mail(2))
    await mailbox.coordinator.async_refresh()

    (later,) = [
        r for r in data.review.values() if r.sender_domain == SHOP and r.suggestion
    ]
    assert later.reason == "untrusted_authserv"
    listed = {r["id"]: r for r in (await result(ws, "parcels/list"))["review"]}
    assert listed[later.id]["trusted_sender"]
    assert listed[later.id]["checks"] == later.checks


async def test_review_lists_fills(
    engine: ParcelsEngine, ws: MockHAClientWebSocket, review: dict[str, str]
) -> None:
    """A review item that fills in a parcel's missing details says so."""
    data = engine.data
    item = data.review[review[SHOP]]
    data.review["r_fill"] = replace(
        item, id="r_fill", reason=REASON_AI_FILL, source=Source.AI, fill=True
    )

    listed = {r["id"]: r for r in (await result(ws, "parcels/list"))["review"]}

    assert listed["r_fill"]["fill"]
    assert listed["r_fill"]["reason"] == REASON_AI_FILL
    assert not listed[item.id]["fill"]


async def test_review_lists_failed_checks(
    engine: ParcelsEngine, ws: MockHAClientWebSocket, review: dict[str, str]
) -> None:
    """A rejected AI answer lists the checks it failed and its notes, as codes."""
    data = engine.data
    item = data.review[review[SHOP]]
    data.review["r_rejected"] = replace(
        item,
        id="r_rejected",
        reason="ai_rejected",
        source=Source.AI,
        errors=("tracking_is_order", "eta_not_in_text"),
        notes=("carrier_unproven",),
    )

    listed = {r["id"]: r for r in (await result(ws, "parcels/list"))["review"]}

    assert listed["r_rejected"]["errors"] == ["tracking_is_order", "eta_not_in_text"]
    assert listed["r_rejected"]["notes"] == ["carrier_unproven"]
    assert listed[item.id]["notes"] == []
    assert listed[item.id]["errors"] == []


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


async def test_merge_suggestions(
    engine: ParcelsEngine,
    ws: MockHAClientWebSocket,
    sam_ws: MockHAClientWebSocket,
) -> None:
    """Administrators merge or keep apart parcels that may be one.

    Two Amazon orders are due today and the carrier delivered two Amazon
    parcels this morning: which order was in which can't be known.
    """
    data = engine.data
    now = dt_util.utcnow()
    carriers = [
        apply_contribution(
            data,
            contribution(
                f"msg:carrier{n}#0",
                kind=MailKind.DELIVERED,
                time=datetime(2026, 11, 17, 7 + n, tzinfo=UTC),
                carrier="ctt_expresso",
                number=f"EX00000000000{n}",
                merchant="Amazon",
                label="cttexpresso.pt",
            ),
            now,
        ).parcel_id
        for n in (1, 2)
    ]
    orders = [
        apply_contribution(
            data,
            contribution(
                f"msg:order{n}#0",
                time=datetime(2026, 11, 15, 20 + n, tzinfo=UTC),
                merchant="Amazon.es",
                orders=[f"171-000000{n}-000000{n}"],
                eta=Eta(start=date(2026, 11, 17), end=date(2026, 11, 17)),
                label="amazon.es",
            ),
            now,
        ).parcel_id
        for n in (1, 2)
    ]
    engine.async_changed()

    suggestions = {
        item["parcel"]["id"]: item
        for item in (await result(ws, "parcels/list"))["merge_suggestions"]
    }
    assert set(suggestions) == set(carriers)
    for item in suggestions.values():
        assert (item["reason"], item["merchant"], item["day"]) == (
            REASON_SAME_MERCHANT_DAY,
            "Amazon",
            "2026-11-17",
        )
        assert [parcel["id"] for parcel in item["candidates"]] == orders
    assert (await result(sam_ws, "parcels/list"))["merge_suggestions"] == []
    first, second = carriers
    for command, extra in (("accept", {"parcel_id": orders[0]}), ("dismiss", {})):
        err = await error(
            sam_ws,
            f"parcels/suggestion/{command}",
            suggestion_id=suggestions[first]["id"],
            **extra,
        )
        assert err["code"] == "unauthorized"

    assert (
        await result(
            ws, "parcels/suggestion/dismiss", suggestion_id=suggestions[first]["id"]
        )
        is None
    )
    (item,) = (await result(ws, "parcels/list"))["merge_suggestions"]
    assert item["parcel"]["id"] == second
    assert [parcel["id"] for parcel in item["candidates"]] == orders

    assert await result(
        ws, "parcels/suggestion/accept", suggestion_id=item["id"], parcel_id=orders[0]
    ) == {"parcel_id": second}
    assert set(data.parcels).issuperset({first, second, orders[1]})
    assert orders[0] not in data.parcels
    assert data.parcels[second].auto_merged is None
    assert data.parcels[second].state.order_numbers == ("171-0000001-0000001",)
    assert data.parcels[first].state.order_numbers == ()
    assert (await result(ws, "parcels/list"))["merge_suggestions"] == []
    for command, extra in (("accept", {"parcel_id": orders[1]}), ("dismiss", {})):
        await refused(
            ws,
            f"parcels/suggestion/{command}",
            "unknown_suggestion",
            suggestion_id=item["id"],
            **extra,
        )


async def test_mailbox_owner(
    hass: HomeAssistant, engine: ParcelsEngine, review: dict[str, str]
) -> None:
    """An e-mail's owner is the person's name, else the mailbox's title."""
    item = engine.data.review[review[SHOP]]

    assert mailbox_owner(hass, item) == "Alex"
    assert mailbox_owner(hass, replace(item, owner="person.nobody")) == ADDRESS
    assert mailbox_owner(hass, replace(item, owner=None, mailbox="gone")) is None
    assert mailbox_owner(hass, replace(item, owner=None, mailbox=None)) is None
