"""Tests for refunds and customer returns, read through the mailboxes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant.common import CLIENT_ID
from pytest_homeassistant.typing import WebSocketGenerator

from custom_components.parcels.const import (
    DOMAIN,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.engine import RETURNS_CHECK_KEY, ParcelsEngine
from custom_components.parcels.mail.errors import MailServerError
from custom_components.parcels.models import (
    MessageRecord,
    MessageState,
    ParcelsData,
    PickupRule,
    dt_to_str,
)
from custom_components.parcels.parsers.auth import parse_authentication_results
from custom_components.parcels.parsers.base import (
    MailMessage,
    ParsedShipment,
    ParseResult,
)
from custom_components.parcels.parsers.normalize import message_from_bytes
from custom_components.parcels.parsers.returns import NOTE_REFUND
from custom_components.parcels.views import SYSTEM_VIEWER, details, parcel_json

from .common import (
    ADDRESS,
    EMAIL_FIXTURES,
    OTHER_ADDRESS,
    OTHER_OWNER,
    OWNER,
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    load_message,
    patch_mail_clients,
)

NOW = "2026-11-20 13:00:00+00:00"
# Tuesday 10 November: "Data de recolha: Dia útil seguinte".
RETURN_PT = "amazon/return_pickup_pt.eml"
RETURN_PT_ORDER = "404-5528193-7720416"
# Thursday 12 November, picked up on Friday 13 November.
RETURN_ES = "amazon/return_pickup_es.eml"
RETURN_ES_ORDER = "402-6619027-3348175"
# Wednesday 11 November, without an order number.
RETURN_NO_ORDER = "amazon/return_pickup_no_order_pt.eml"
RETURN_NO_ORDER_ITEM = "Suporte de portátil em alumínio"
# Shipped on 18 November, expected on 21 November.
SHIPPED = "amazon/shipped_carrier_pt.eml"
SHIPPED_ORDER = "406-7382916-2048573"
SHIPPED_ITEM = "Panela de pressão em aço inoxidável, 6 litros, com cesto"
# When the return of the shipped order started: Thursday 19 November.
RETURN_STARTED = datetime(2026, 11, 19, 9, 30, tzinfo=UTC)


def return_of_shipped_order() -> MailMessage:
    """Return the PT return e-mail, for the shipped order, sent on 19 November."""
    raw = (EMAIL_FIXTURES / RETURN_PT).read_bytes()
    for old, new in (
        (RETURN_PT_ORDER, SHIPPED_ORDER),
        ("Candeeiro de secretária LED, branco", SHIPPED_ITEM),
        ("Tue, 10 Nov 2026 15:20:00", "Thu, 19 Nov 2026 09:30:00"),
        ("return-pt-000001", "return-pt-000009"),
    ):
        assert old.encode() in raw
        raw = raw.replace(old.encode(), new.encode())
    return message_from_bytes(
        raw, mailbox=ADDRESS, provider_id="return-of-shipped", provider="google"
    )


def unverified(path: str) -> MailMessage:
    """Return a fixture with a header that a server Parcels doesn't trust wrote."""
    header = "mx.example.net; dkim=pass header.d=amazon.es"
    return replace(
        load_message(path),
        auth=parse_authentication_results(header),
        auth_headers=(header,),
    )


async def get_events(hass: HomeAssistant, start: str, end: str) -> list[dict[str, Any]]:
    """Return the events of the Parcels calendar between two times."""
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"start_date_time": start, "end_date_time": end},
        target={ATTR_ENTITY_ID: "calendar.parcels"},
        blocking=True,
        return_response=True,
    )
    assert response is not None
    return response["calendar.parcels"]["events"]


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on 20 November 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


async def test_refund_emails_are_dropped_silently(hass: HomeAssistant) -> None:
    """A refund never becomes a parcel, a review or a filtered e-mail.

    It's only counted, once, even when it's read again.
    """
    client = FakeMailClient()
    client.add("amazon/refund_es.eml")
    client.add("amazon/refund_de.eml")
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)

        assert not engine.data.parcels
        assert not engine.data.review
        assert not engine.data.filtered
        states = {record.state for record in engine.data.messages.values()}
        assert states == {MessageState.NOT_PARCEL}
        assert engine.diagnostics()["refunds_dropped"] == 2

        await engine.async_reprocess(next(iter(engine.data.messages)))

        assert not engine.data.parcels
        assert not engine.data.review
        assert engine.diagnostics()["refunds_dropped"] == 2


async def test_return_emails_become_returns(hass: HomeAssistant) -> None:
    """A shop's return e-mail becomes a return, with its pickup day.

    It never becomes a parcel, a review or a filtered e-mail, with or
    without an order number.
    """
    client = FakeMailClient()
    for path in (RETURN_PT, RETURN_ES, RETURN_NO_ORDER):
        client.add(path)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)

    data = engine.data
    assert not data.parcels
    assert not data.review
    assert not data.filtered
    assert {record.state for record in data.messages.values()} == {MessageState.APPLIED}
    returns = {
        (entry.order_numbers or entry.items)[0]: (
            entry.merchant,
            entry.pickup,
            entry.owners,
            len(entry.origins),
        )
        for entry in data.returns.values()
    }
    assert returns == {
        # The e-mail's "next working day", after Tuesday 10 November.
        RETURN_PT_ORDER: (
            "Amazon",
            (date(2026, 11, 11), PickupRule.NEXT_WORKING_DAY),
            (OWNER,),
            1,
        ),
        # The e-mail's own date.
        RETURN_ES_ORDER: (
            "Amazon",
            (date(2026, 11, 13), PickupRule.EMAIL),
            (OWNER,),
            1,
        ),
        RETURN_NO_ORDER_ITEM: (
            "Amazon",
            (date(2026, 11, 12), PickupRule.NEXT_WORKING_DAY),
            (OWNER,),
            1,
        ),
    }


async def test_return_in_two_mailboxes_is_one_return(hass: HomeAssistant) -> None:
    """The same e-mail in two people's mailboxes is one return, for both."""
    alex = FakeMailClient()
    sam = FakeMailClient(address=OTHER_ADDRESS)
    alex.add(RETURN_PT)
    sam.add(RETURN_PT)
    add_hub(hass)
    add_mailbox(hass)
    add_mailbox(hass, address=OTHER_ADDRESS, owner=OTHER_OWNER)

    with patch_mail_clients(alex, sam):
        engine = await async_setup_parcels(hass)

    (entry,) = engine.data.returns.values()
    assert entry.owners == (OWNER, OTHER_OWNER)
    assert len(entry.origins) == 1
    assert entry.pickup == (date(2026, 11, 11), PickupRule.NEXT_WORKING_DAY)
    assert not engine.data.parcels


async def test_return_infers_the_delivery(hass: HomeAssistant) -> None:
    """A return of a shipped order means its parcel arrived.

    The delivery is inferred on the day the return started, and the return
    keeps its own pickup day. Undoing the delivery keeps it from coming back.
    """
    client = FakeMailClient()
    client.add(SHIPPED)
    client.add(return_of_shipped_order())
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)

        (parcel,) = engine.data.parcels.values()
        state = parcel.state
        assert state.status is ParcelStatus.DELIVERED
        assert state.inferred
        assert state.inferred_reason == "return"
        assert state.delivered_at == RETURN_STARTED
        assert parcel_json(parcel, SYSTEM_VIEWER)["inferred_reason"] == "return"
        timeline = details(engine, parcel, SYSTEM_VIEWER)["timeline"]
        assert [(e["status"], e["source"], e["label"]) for e in timeline][-1] == (
            "delivered",
            "inferred_return",
            "",
        )
        (entry,) = engine.data.returns.values()
        assert entry.order_numbers == (SHIPPED_ORDER,)
        assert entry.items == (SHIPPED_ITEM,)
        # The working day after Thursday 19 November.
        assert entry.pickup == (date(2026, 11, 20), PickupRule.NEXT_WORKING_DAY)

        engine.undo_delivery(parcel.id)
        await hass.async_block_till_done()

        parcel = engine.data.parcels[parcel.id]
        assert parcel.delivery_rejected
        assert parcel.state.status is ParcelStatus.SHIPPED
        assert not parcel.state.inferred
        assert len(engine.data.returns) == 1


async def test_accepting_a_return_from_review(hass: HomeAssistant) -> None:
    """A return e-mail that failed the checks waits in review, with its pickup.

    Accepting it adds the return, not a parcel.
    """
    client = FakeMailClient()
    client.add(unverified(RETURN_NO_ORDER))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)

        (item,) = engine.data.review.values()
        assert item.reason == "untrusted_authserv"
        suggestion = item.suggestion
        assert suggestion is not None
        assert suggestion.kind is MailKind.CUSTOMER_RETURN
        # The working day after Wednesday 11 November.
        assert (suggestion.eta_start, suggestion.eta_end) == (date(2026, 11, 12),) * 2
        assert suggestion.items == (RETURN_NO_ORDER_ITEM,)
        assert not engine.data.returns

        assert engine.review_accept(item.id) == []
        await hass.async_block_till_done()

        assert not engine.data.review
        assert not engine.data.parcels
        (entry,) = engine.data.returns.values()
        assert entry.items == (RETURN_NO_ORDER_ITEM,)
        assert entry.pickup == (date(2026, 11, 12), PickupRule.EMAIL)
        assert entry.owners == (OWNER,)
        assert engine.data.messages[item.message].state is MessageState.APPLIED


async def send(
    ws: Any, msg_type: str, *, success: bool = True, **data: Any
) -> dict[str, Any]:
    """Send a WebSocket command; return its result, or its error."""
    await ws.send_json_auto_id({"type": msg_type, **data})
    reply = await ws.receive_json()
    assert reply["type"] == "result"
    assert reply["success"] is success, reply
    return reply["result"] if success else reply["error"]


async def test_remove_a_return(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """An administrator removes a return; its e-mails aren't read again.

    The delivery that only the return inferred goes with it, and isn't
    marked as undone. Others may not remove returns.
    """
    client = FakeMailClient()
    client.add(SHIPPED)
    client.add(return_of_shipped_order())
    add_hub(hass)
    add_mailbox(hass)
    sam = await hass.auth.async_create_user("Sam")
    refresh = await hass.auth.async_create_refresh_token(sam, CLIENT_ID)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        ws = await hass_ws_client(hass)
        sam_ws = await hass_ws_client(
            hass, access_token=hass.auth.async_create_access_token(refresh)
        )
        (parcel,) = engine.data.parcels.values()
        (entry,) = engine.data.returns.values()
        emails = list(entry.origins)
        (shown,) = (await send(ws, f"{DOMAIN}/list"))["returns"]
        assert {key: shown[key] for key in ("id", "day", "pickup", "pickup_rule")} == {
            "id": entry.id,
            "day": "2026-11-20",
            "pickup": "2026-11-20",
            "pickup_rule": PickupRule.NEXT_WORKING_DAY.value,
        }
        assert shown["merchant"] == "Amazon"
        assert shown["order_numbers"] == [SHIPPED_ORDER]
        assert shown["items"] == [SHIPPED_ITEM]
        assert shown["parcel_ids"] == [parcel.id]
        assert shown["owners"] == [OWNER]
        assert len(shown["emails"]) == 1
        assert not shown["received"]
        assert not shown["restricted"]

        denied = await send(
            sam_ws, f"{DOMAIN}/return/remove", success=False, return_id=entry.id
        )
        assert denied["code"] == "unauthorized"
        unknown = await send(
            ws, f"{DOMAIN}/return/remove", success=False, return_id="no-such-return"
        )
        assert unknown["translation_key"] == "unknown_return"
        assert entry.id in engine.data.returns

        assert await send(ws, f"{DOMAIN}/return/remove", return_id=entry.id) is None
        await hass.async_block_till_done()

        assert not engine.data.returns
        assert (await send(ws, f"{DOMAIN}/list"))["returns"] == []
        assert [engine.data.messages[key].state for key in emails] == [
            MessageState.DISMISSED
        ]
        parcel = engine.data.parcels[parcel.id]
        assert parcel.state.status is ParcelStatus.SHIPPED
        assert not parcel.state.inferred
        assert not parcel.delivery_rejected


async def test_calendar_shows_return_pickups(hass: HomeAssistant) -> None:
    """Each return is on its pickup day, ticked once the day is over.

    The returned order's delivery stays on its own day.
    """
    client = FakeMailClient()
    for message in (RETURN_PT, RETURN_ES, SHIPPED, return_of_shipped_order()):
        client.add(message)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        await async_setup_parcels(hass)
        events = await get_events(
            hass, "2026-11-09T00:00:00+00:00", "2026-11-23T00:00:00+00:00"
        )

    next_day = "Picked up the working day after the shop's e-mail"
    returns = sorted(
        (event["start"], event["summary"], event["description"])
        for event in events
        if event["summary"].startswith("Return")
    )
    assert returns == [
        ("2026-11-11", "Return pickup: Amazon ✓", f"Return to the shop\n{next_day}"),
        (
            "2026-11-13",
            "Return pickup: Amazon ✓",
            "Return to the shop\nPickup day from the shop's e-mail",
        ),
        # Today: not picked up yet.
        ("2026-11-20", "Return pickup: Amazon", f"Return to the shop\n{next_day}"),
    ]
    (delivery,) = [e for e in events if not e["summary"].startswith("Return")]
    assert delivery["start"] == "2026-11-19"
    assert delivery["summary"].endswith("✓")


# -- The one-time check after the update ---------------------------------

# Friday 20 November, 12:05 UTC; really about another order.
REFUND_ES = "amazon/refund_es.eml"
# Friday 20 November, 08:30 UTC.
REFUND_DE = "amazon/refund_de.eml"
REFUND_DE_ORDER = "303-8473625-1928374"
NO_COUNTS = dict.fromkeys(
    ("read", "refunds", "returns", "decided", "gone", "failed", "skipped"), 0
)


def old_result(kind: MailKind, *orders: str, confidence: float = 0.9) -> ParseResult:
    """Return how an earlier release could have read an e-mail."""
    shipments = (
        [] if kind is MailKind.NOT_PARCEL else [ParsedShipment(order_numbers=orders)]
    )
    return ParseResult(
        parser="amazon",
        kind=kind,
        merchant="Amazon",
        order_numbers=orders,
        shipments=shipments,
        confidence=confidence,
    )


@contextmanager
def parsed_as(
    earlier: dict[str, ParseResult],
    during: Callable[[MailMessage], None] | None = None,
) -> Iterator[None]:
    """Read e-mails, by their ID, as an earlier release did.

    ``during`` runs while each e-mail is read.
    """
    parse = ParcelsEngine.async_parse

    async def read(
        engine: ParcelsEngine, message: MailMessage, verdict: Any
    ) -> ParseResult:
        if during is not None:
            during(message)
        if (result := earlier.get(message.provider_id)) is not None:
            return deepcopy(result)
        return await parse(engine, message, verdict)

    with patch.object(ParcelsEngine, "async_parse", read):
        yield


async def async_sync(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """Read every mailbox now, and wait for what that starts.

    Only the tasks the sync starts: the AI queue's never ends.
    """
    tasks: list[asyncio.Task[Any]] = []
    create = engine.async_create_task

    def record(target: Coroutine[Any, Any, Any], name: str) -> asyncio.Task[Any]:
        task = create(target, name)
        tasks.append(task)
        return task

    with patch.object(engine, "async_create_task", record):
        for mailbox in list(engine.mailboxes.values()):
            assert mailbox.coordinator is not None
            await mailbox.coordinator.async_refresh()
        while pending := [task for task in tasks if not task.done()]:
            await asyncio.wait(pending)
    for task in tasks:
        task.result()
    await hass.async_block_till_done()


async def async_check(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> dict[str, Any]:
    """Run the check as after an update, on the next sync; return its record."""
    freezer.tick(timedelta(minutes=1))
    engine.data.engine[RETURNS_CHECK_KEY] = {"before": dt_to_str(dt_util.utcnow())}
    freezer.tick(timedelta(minutes=1))
    await async_sync(hass, engine)
    return engine.data.engine[RETURNS_CHECK_KEY]


def states(engine: ParcelsEngine) -> dict[str, MessageState]:
    """Return the state of each e-mail, by its ID in the mailbox."""
    return {
        min(record.refs.values()): record.state
        for record in engine.data.messages.values()
    }


def record_of(engine: ParcelsEngine, provider_id: str) -> MessageRecord:
    """Return the record of an e-mail, by its ID in the mailbox."""
    (record,) = [
        record
        for record in engine.data.messages.values()
        if provider_id in record.refs.values()
    ]
    return record


def sent_back() -> MailMessage:
    """Return a CTT e-mail about a parcel sent back to the shop, undelivered."""
    return replace(
        load_message("carriers/ctt_in_transit_pt.eml"),
        provider_id="ctt-sent-back",
        subject="Objeto devolvido ao remetente",
        text="Olá Alex Doe,\nO seu objeto RR482915732PT foi devolvido ao remetente.\n",
        links=(),
    )


def ai_lists(engine: ParcelsEngine) -> list[str]:
    """Return the e-mails in the AI's queue and among its shadow checks."""
    return [entry["hash"] for entry in engine.ai.queue] + list(
        engine.data.ai.get("shadow", [])
    )


async def test_check_drops_refunds_an_earlier_release_added(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Refunds an earlier release added as sent back are dropped, once.

    The parcel a refund joined goes back to what its other e-mails say, and
    a parcel only a refund made goes. Every mailbox lists its lookback
    period again on its next sync.
    """
    client = FakeMailClient()
    for path in (SHIPPED, REFUND_ES, REFUND_DE):
        client.add(path)
    add_hub(hass)
    add_mailbox(hass)
    earlier = {
        "refund_es.eml": old_result(MailKind.RETURN, SHIPPED_ORDER),
        "refund_de.eml": old_result(MailKind.RETURN, REFUND_DE_ORDER),
    }

    with patch_mail_clients(client):
        with parsed_as(earlier):
            engine = await async_setup_parcels(hass)
        assert sorted(
            (p.state.order_numbers, p.state.status)
            for p in engine.data.parcels.values()
        ) == [
            ((REFUND_DE_ORDER,), ParcelStatus.RETURNED),
            ((SHIPPED_ORDER,), ParcelStatus.RETURNED),
        ]
        client.fetches.clear()

        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 2, "refunds": 2}
    assert check.keys() == {"before", "started", "relisted", "done", "counts"}
    assert check["relisted"] == 1
    assert client.fetches == ["refund_es.eml", "refund_de.eml"]
    (parcel,) = engine.data.parcels.values()
    state = parcel.state
    assert state.status is ParcelStatus.SHIPPED
    assert state.order_numbers == (SHIPPED_ORDER,)
    assert state.items == (SHIPPED_ITEM,)
    assert ParcelStatus.RETURNED not in {event.status for event in parcel.events}
    assert states(engine) == {
        "shipped_carrier_pt.eml": MessageState.APPLIED,
        "refund_es.eml": MessageState.NOT_PARCEL,
        "refund_de.eml": MessageState.NOT_PARCEL,
    }
    assert not engine.data.returns
    assert not engine.data.review
    assert not engine.data.filtered
    diagnostics = engine.diagnostics()
    assert diagnostics["refunds_dropped"] == 2
    assert diagnostics["returns_check"] == check


async def test_check_finds_returns_an_earlier_release_added(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A customer return an earlier release added as sent back becomes a return.

    Its order's parcel then counts as delivered, as for a new e-mail.
    """
    client = FakeMailClient()
    client.add(SHIPPED)
    client.add(return_of_shipped_order())
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as(
            {"return-of-shipped": old_result(MailKind.RETURN, SHIPPED_ORDER)}
        ):
            engine = await async_setup_parcels(hass)
        (parcel,) = engine.data.parcels.values()
        assert parcel.state.status is ParcelStatus.RETURNED
        assert not engine.data.returns

        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "returns": 1}
    (parcel,) = engine.data.parcels.values()
    state = parcel.state
    assert state.status is ParcelStatus.DELIVERED
    assert state.inferred
    assert state.inferred_reason == "return"
    assert state.delivered_at == RETURN_STARTED
    assert state.items == (SHIPPED_ITEM,)
    (entry,) = engine.data.returns.values()
    assert entry.order_numbers == (SHIPPED_ORDER,)
    assert entry.items == (SHIPPED_ITEM,)
    assert entry.pickup == (date(2026, 11, 20), PickupRule.NEXT_WORKING_DAY)
    assert set(states(engine).values()) == {MessageState.APPLIED}


@pytest.mark.parametrize(
    ("state", "kind"),
    [
        (MessageState.NOT_PARCEL, MailKind.NOT_PARCEL),
        (MessageState.IGNORED, MailKind.NOT_PARCEL),
        (MessageState.REVIEW, MailKind.UNKNOWN),
        (MessageState.DISMISSED, MailKind.UNKNOWN),
        (MessageState.FILTERED, MailKind.UNKNOWN),
    ],
)
async def test_check_reads_set_aside_returns_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    state: MessageState,
    kind: MailKind,
) -> None:
    """A return e-mail an earlier release set aside becomes a return.

    Also when the user cleared it: it's read again, once.
    """
    client = FakeMailClient()
    client.add(RETURN_NO_ORDER)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"return_pickup_no_order_pt.eml": old_result(kind)}):
            engine = await async_setup_parcels(hass)
        record = record_of(engine, "return_pickup_no_order_pt.eml")
        if state is MessageState.IGNORED:
            record.state = MessageState.IGNORED
        elif state is MessageState.DISMISSED:
            (item,) = engine.data.review.values()
            engine.review_dismiss(item.id)
        elif state is MessageState.FILTERED:
            (item,) = engine.data.review.values()
            del engine.data.review[item.id]
            engine.add_filtered(item, record)
        assert record.state is state
        assert not engine.data.returns

        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "returns": 1}
    (entry,) = engine.data.returns.values()
    assert entry.items == (RETURN_NO_ORDER_ITEM,)
    assert entry.pickup == (date(2026, 11, 12), PickupRule.NEXT_WORKING_DAY)
    assert record_of(engine, "return_pickup_no_order_pt.eml").state is (
        MessageState.APPLIED
    )
    assert not engine.data.parcels
    assert not engine.data.review
    assert not engine.data.filtered


async def test_check_drops_refunds_from_review(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Refunds left in review, or accepted from it, are dropped too."""
    client = FakeMailClient()
    client.add(REFUND_ES)
    client.add(REFUND_DE)
    add_hub(hass)
    add_mailbox(hass)
    earlier = {
        "refund_es.eml": old_result(MailKind.RETURN, confidence=0.5),
        "refund_de.eml": old_result(MailKind.RETURN, REFUND_DE_ORDER, confidence=0.5),
    }

    with patch_mail_clients(client):
        with parsed_as(earlier):
            engine = await async_setup_parcels(hass)
        assert len(engine.data.review) == 2
        (accepted,) = [
            item
            for item in engine.data.review.values()
            if item.message == record_of(engine, "refund_de.eml").hash
        ]
        engine.review_accept(accepted.id)
        (parcel,) = engine.data.parcels.values()
        assert parcel.state.status is ParcelStatus.RETURNED
        client.fetches.clear()

        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 2, "refunds": 2}
    assert client.fetches == ["refund_de.eml", "refund_es.eml"]
    assert not engine.data.parcels
    assert not engine.data.review
    assert not engine.data.filtered
    assert set(states(engine).values()) == {MessageState.NOT_PARCEL}
    assert engine.diagnostics()["refunds_dropped"] == 2


async def test_check_drops_filtered_refunds_named_only_in_the_body(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A refund that only its body names, set aside earlier, is dropped too.

    Shop's parser can't read it, and its subject has no shipping words, so
    it's sure not to be about a parcel: as a refund, it's dropped.
    """
    client = FakeMailClient()
    client.add(
        replace(
            load_message("shop/out_for_delivery_pt.eml"),
            provider_id="body_refund.eml",
            subject="Informação sobre o seu artigo",
            text="Reembolso: 12,99 €.",
            links=(),
        )
    )
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"body_refund.eml": old_result(MailKind.UNKNOWN)}):
            engine = await async_setup_parcels(hass)
        record = record_of(engine, "body_refund.eml")
        # As after the local AI found it isn't about a parcel.
        (item,) = engine.data.review.values()
        del engine.data.review[item.id]
        engine.add_filtered(item, record)
        assert record.state is MessageState.FILTERED

        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "refunds": 1}
    assert not engine.data.filtered
    assert not engine.data.review
    assert not engine.data.parcels
    assert record_of(engine, "body_refund.eml").state is MessageState.NOT_PARCEL
    assert engine.diagnostics()["refunds_dropped"] == 1


async def test_check_takes_dropped_refunds_off_the_ai_lists(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, local_ai: str
) -> None:
    """A refund the check drops leaves the AI's queue and its shadow checks."""
    client = FakeMailClient()
    client.add(SHIPPED)
    client.add(REFUND_ES)
    add_hub(hass, ai_task_entity=local_ai, ai_mode="suggest")
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"refund_es.eml": old_result(MailKind.RETURN, SHIPPED_ORDER)}):
            engine = await async_setup_parcels(hass)
        key = record_of(engine, "refund_es.eml").hash
        assert key in ai_lists(engine)

        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "refunds": 1}
    assert key not in ai_lists(engine)
    assert record_of(engine, "shipped_carrier_pt.eml").hash in ai_lists(engine)


async def test_check_decides_emails_that_failed_to_download(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail that failed to download is decided as a new one, for everyone.

    From any sender: it was never read.
    """
    alex = FakeMailClient()
    sam = FakeMailClient(address=OTHER_ADDRESS)
    for client in (alex, sam):
        client.add("shopify/shipped_es.eml")
        client.fetch_errors["shipped_es.eml"] = MailServerError("down")
    add_hub(hass)
    add_mailbox(hass)
    add_mailbox(hass, address=OTHER_ADDRESS, owner=OTHER_OWNER)

    with patch_mail_clients(alex, sam):
        with patch("custom_components.parcels.engine.FETCH_ATTEMPTS", 1):
            engine = await async_setup_parcels(hass)
        record = record_of(engine, "shipped_es.eml")
        assert record.state is MessageState.FAILED
        assert record.owners == (OWNER, OTHER_OWNER)
        assert not engine.data.parcels
        for client in (alex, sam):
            client.fetch_errors.clear()

        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "decided": 1}
    assert record_of(engine, "shipped_es.eml").state is MessageState.APPLIED
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert set(parcel.state.owners) == {OWNER, OTHER_OWNER}
    assert not engine.data.returns


@pytest.mark.parametrize(
    ("age", "state"), [(20, MessageState.REVIEW), (2, MessageState.QUEUED)]
)
async def test_check_decides_failed_emails_as_on_a_first_sync(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    local_ai: str,
    age: int,
    state: MessageState,
) -> None:
    """The AI only gets e-mails that failed to download when they're recent."""
    client = FakeMailClient()
    received = dt_util.utcnow() - timedelta(days=age)
    client.add(replace(load_message(RETURN_NO_ORDER), received=received))
    client.fetch_errors["return_pickup_no_order_pt.eml"] = MailServerError("down")
    add_hub(hass, ai_task_entity=local_ai, ai_mode="suggest")
    add_mailbox(hass)

    with patch_mail_clients(client):
        with patch("custom_components.parcels.engine.FETCH_ATTEMPTS", 1):
            engine = await async_setup_parcels(hass)
        record = record_of(engine, "return_pickup_no_order_pt.eml")
        assert record.state is MessageState.FAILED
        client.fetch_errors.clear()
        with parsed_as({"return_pickup_no_order_pt.eml": old_result(MailKind.UNKNOWN)}):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "decided": 1}
    assert record.state is state
    queued = state is MessageState.QUEUED
    assert [entry["hash"] for entry in engine.ai.queue] == (
        [record.hash] if queued else []
    )
    assert len(engine.data.review) == (0 if queued else 1)


async def test_check_leaves_other_emails_alone(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The check reads only what an earlier release set aside, and changes
    only refunds and returns.

    Unknown senders, e-mails older than 30 days and those read after the
    update aren't read again; a refund already set aside or an unverified
    return stays as it was, and so does anything else from a trusted shop.
    """
    client = FakeMailClient()
    for path in (
        "common/unknown_phone_only.eml",
        "common/order_confirmation.eml",
        "amazon/marketing_es.eml",
        REFUND_ES,
    ):
        client.add(path)
    client.add(unverified(RETURN_NO_ORDER))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"refund_es.eml": old_result(MailKind.NOT_PARCEL)}):
            engine = await async_setup_parcels(hass)
        engine.data.sender("example-store.example").trusted = True
        record_of(engine, "marketing_es.eml").received = dt_util.utcnow() - timedelta(
            days=31
        )
        before = states(engine)
        assert before == {
            "unknown_phone_only.eml": MessageState.FILTERED,
            "order_confirmation.eml": MessageState.REVIEW,
            "marketing_es.eml": MessageState.NOT_PARCEL,
            "refund_es.eml": MessageState.NOT_PARCEL,
            "return_pickup_no_order_pt.eml": MessageState.REVIEW,
        }
        client.add(REFUND_DE)
        client.fetches.clear()

        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 3}
    assert client.fetches == [
        "refund_de.eml",
        "refund_es.eml",
        "order_confirmation.eml",
        "return_pickup_no_order_pt.eml",
    ]
    assert states(engine) == {**before, "refund_de.eml": MessageState.NOT_PARCEL}
    assert engine.diagnostics()["refunds_dropped"] == 1
    assert len(engine.data.review) == 2
    assert len(engine.data.filtered) == 1
    assert not engine.data.parcels
    assert not engine.data.returns


async def test_check_skips_ignored_senders(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """E-mails from a sender the user ignores are never read again."""
    client = FakeMailClient()
    client.add(REFUND_ES)
    client.add(RETURN_NO_ORDER)
    add_hub(hass)
    add_mailbox(hass)
    earlier = {
        "refund_es.eml": old_result(MailKind.RETURN, REFUND_DE_ORDER),
        "return_pickup_no_order_pt.eml": old_result(MailKind.UNKNOWN),
    }

    with patch_mail_clients(client):
        with parsed_as(earlier):
            engine = await async_setup_parcels(hass)
        engine.ignore_domain("amazon.es")
        before = states(engine)
        assert before == {
            "refund_es.eml": MessageState.APPLIED,
            "return_pickup_no_order_pt.eml": MessageState.IGNORED,
        }
        client.fetches.clear()

        check = await async_check(hass, engine, freezer)

    assert check["counts"] == NO_COUNTS
    assert not client.fetches
    assert states(engine) == before
    assert len(engine.data.parcels) == 1
    assert not engine.data.returns


async def test_check_lists_the_lookback_period_again(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """After the update, every mailbox lists its lookback period once more.

    A return e-mail an earlier release skipped without keeping a record is
    read then; e-mails read before aren't downloaded again.
    """
    client = FakeMailClient()
    client.relist = True
    client.add(SHIPPED)
    add_hub(hass)
    mailbox = add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        assert engine.is_synced(mailbox.entry_id)
        # Skipped by an earlier release's filter: in the mailbox, never read.
        client.add(RETURN_PT)
        client.pending.clear()
        client.fetches.clear()

        check = await async_check(hass, engine, freezer)
        assert check["relisted"] == 1
        assert check["counts"] == NO_COUNTS
        assert not engine.data.returns
        # Read like a first sync: the AI only gets the recent e-mails.
        assert not engine.is_synced(mailbox.entry_id)
        after_check = deepcopy(check)

        await async_sync(hass, engine)
        assert engine.is_synced(mailbox.entry_id)
        (entry,) = engine.data.returns.values()
        assert entry.order_numbers == (RETURN_PT_ORDER,)
        assert client.fetches == ["return_pickup_pt.eml"]

        await async_sync(hass, engine)

    assert client.syncs == [None, {"round": 1}, None, {"round": 3}]
    assert engine.data.engine[RETURNS_CHECK_KEY] == after_check
    assert client.fetches == ["return_pickup_pt.eml"]
    assert len(engine.data.parcels) == 1


async def test_check_reads_at_most_its_limit(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The newest e-mails are read first, up to the limit; the rest are counted."""
    client = FakeMailClient()
    client.add(REFUND_ES)
    client.add(REFUND_DE)
    add_hub(hass)
    add_mailbox(hass)
    earlier = {
        "refund_es.eml": old_result(MailKind.RETURN, SHIPPED_ORDER),
        "refund_de.eml": old_result(MailKind.RETURN, REFUND_DE_ORDER),
    }

    with patch_mail_clients(client):
        with parsed_as(earlier):
            engine = await async_setup_parcels(hass)
        client.fetches.clear()
        with patch("custom_components.parcels.engine.RETURNS_CHECK_MAX", 1):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "refunds": 1, "skipped": 1}
    assert client.fetches == ["refund_es.eml"]
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.order_numbers == (REFUND_DE_ORDER,)
    assert parcel.state.status is ParcelStatus.RETURNED


async def test_check_leaves_an_email_the_user_handled_meanwhile(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail the user dismisses while it's read again stays dismissed."""
    client = FakeMailClient()
    client.add(REFUND_ES)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"refund_es.eml": old_result(MailKind.RETURN, confidence=0.5)}):
            engine = await async_setup_parcels(hass)
        (item,) = engine.data.review.values()

        def dismiss(message: MailMessage) -> None:
            if item.id in engine.data.review:
                engine.review_dismiss(item.id)

        with parsed_as({}, during=dismiss):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1}
    assert record_of(engine, "refund_es.eml").state is MessageState.DISMISSED
    assert not engine.data.review
    assert engine.diagnostics()["refunds_dropped"] == 0


async def test_check_leaves_an_email_forgotten_meanwhile(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail forgotten while it's read again isn't decided.

    The daily cleanup forgets e-mails 120 days after they were seen.
    """
    client = FakeMailClient()
    client.add(REFUND_ES)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"refund_es.eml": old_result(MailKind.RETURN, confidence=0.5)}):
            engine = await async_setup_parcels(hass)
        (item,) = engine.data.review.values()
        key = record_of(engine, "refund_es.eml").hash

        def forget(message: MailMessage) -> None:
            engine.data.messages.pop(key, None)

        with parsed_as({}, during=forget):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1}
    assert key not in engine.data.messages
    assert list(engine.data.review) == [item.id]
    assert engine.diagnostics()["refunds_dropped"] == 0


async def test_check_counts_emails_it_cant_download(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail deleted since counts as gone, one that won't download as failed.

    Neither changes anything.
    """
    client = FakeMailClient()
    for path in (REFUND_ES, REFUND_DE):
        client.add(path)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as(
            {
                "refund_es.eml": old_result(MailKind.RETURN, SHIPPED_ORDER),
                "refund_de.eml": old_result(MailKind.RETURN, REFUND_DE_ORDER),
            }
        ):
            engine = await async_setup_parcels(hass)
        deleted = record_of(engine, "refund_es.eml")
        failing = record_of(engine, "refund_de.eml")
        parcels = deepcopy(engine.data.parcels)
        client.delete("refund_es.eml")
        client.fetch_errors["refund_de.eml"] = MailServerError("down")

        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "gone": 1, "failed": 1}
    assert not deleted.refs
    assert failing.refs
    assert deleted.state is failing.state is MessageState.APPLIED
    assert engine.data.parcels == parcels
    assert engine.diagnostics()["refunds_dropped"] == 0


async def test_check_leaves_emails_read_since_the_update_alone(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Only e-mails an earlier release read are read again, not newer ones."""
    client = FakeMailClient()
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        client.add(sent_back())
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == NO_COUNTS
    assert client.fetches == ["ctt-sent-back"]
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.status is ParcelStatus.RETURNED


@pytest.mark.parametrize("stored", ["messages", "nothing", "checked"])
async def test_check_is_due_once_after_an_update(
    hass: HomeAssistant, hass_storage: dict[str, Any], stored: str
) -> None:
    """The check is due when an earlier release read e-mails, and only once."""
    now = dt_util.utcnow()
    data = ParcelsData()
    if stored != "nothing":
        data.messages["hash"] = MessageRecord(
            hash="hash",
            seen=now - timedelta(days=2),
            state=MessageState.NOT_PARCEL,
            sender_domain="amazon.es",
        )
    checked = {"done": dt_to_str(now - timedelta(days=1)), "counts": NO_COUNTS}
    if stored == "checked":
        data.engine[RETURNS_CHECK_KEY] = deepcopy(checked)
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)

    engine = await async_setup_parcels(hass)

    assert (
        engine.data.engine[RETURNS_CHECK_KEY]
        == {
            "messages": {"before": dt_to_str(now)},
            "nothing": {"done": dt_to_str(now)},
            "checked": checked,
        }[stored]
    )


async def test_check_cut_short_by_a_restart_doesnt_run_again(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A check a restart cut short isn't started again: it runs only once."""
    client = FakeMailClient()
    client.add(REFUND_DE)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"refund_de.eml": old_result(MailKind.RETURN, REFUND_DE_ORDER)}):
            engine = await async_setup_parcels(hass)
        client.fetches.clear()
        freezer.tick(timedelta(minutes=1))
        now = dt_to_str(dt_util.utcnow())
        started = {"before": now, "started": now, "relisted": 1}
        engine.data.engine[RETURNS_CHECK_KEY] = deepcopy(started)
        freezer.tick(timedelta(minutes=1))
        await async_sync(hass, engine)

    assert engine.data.engine[RETURNS_CHECK_KEY] == started
    assert not client.fetches
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.status is ParcelStatus.RETURNED


async def test_diagnostics_count_recent_emails_by_day_sender_and_state(
    hass: HomeAssistant,
) -> None:
    """Recent e-mails are counted by day, sender organisation and state.

    Days follow Home Assistant's time zone; senders that are neither known
    nor trusted count as "other". Nothing else about the e-mails is shown.
    """
    await hass.config.async_set_time_zone("Pacific/Kiritimati")
    add_hub(hass)
    engine = await async_setup_parcels(hass)
    engine.data.sender("example-store.example").trusted = True
    records = [
        ("amazon.es", MessageState.NOT_PARCEL, "2026-11-20T12:05:37+00:00"),
        ("marketplace.amazon.es", MessageState.NOT_PARCEL, "2026-11-20T11:00:00+00:00"),
        ("amazon.de", MessageState.APPLIED, "2026-11-20T08:30:58+00:00"),
        ("tienda-ejemplo.es", MessageState.REVIEW, "2026-11-20T09:00:00+00:00"),
        ("", MessageState.FAILED, "2026-11-20T09:30:00+00:00"),
        ("mail.example-store.example", MessageState.FILTERED, None),
        ("amazon.es", MessageState.DISMISSED, "2026-11-05T12:00:00+00:00"),
    ]
    for number, (domain, state, received) in enumerate(records):
        engine.data.messages[f"hash{number}"] = MessageRecord(
            hash=f"hash{number}",
            seen=datetime(2026, 11, 19, 12, tzinfo=UTC),
            state=state,
            received=None if received is None else datetime.fromisoformat(received),
            sender_domain=domain,
        )

    recent = engine.diagnostics()["recent_emails"]

    assert recent == {
        "2026-11-21": {"amazon.es": {"not_parcel": 2}},
        "2026-11-20": {
            "amazon.de": {"applied": 1},
            "example-store.example": {"filtered": 1},
            "other": {"review": 1, "failed": 1},
        },
    }
    assert list(recent) == ["2026-11-21", "2026-11-20"]
    assert list(recent["2026-11-20"]) == ["amazon.de", "example-store.example", "other"]


@pytest.mark.parametrize(
    "reading",
    [
        ParseResult(
            parser="amazon",
            kind=MailKind.NOT_PARCEL,
            merchant="Amazon",
            notes=(NOTE_REFUND,),
            confidence=0.5,
        ),
        ParseResult(
            parser="amazon",
            kind=MailKind.CUSTOMER_RETURN,
            merchant="Amazon",
            shipments=[ParsedShipment(items=(RETURN_NO_ORDER_ITEM,))],
            confidence=0.5,
        ),
        old_result(MailKind.SHIPPED, SHIPPED_ORDER),
    ],
    ids=["weak-refund", "weak-return", "shipped"],
)
async def test_check_leaves_other_readings_alone(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, reading: ParseResult
) -> None:
    """Anything but a sure refund or return stays as it was, even a parcel e-mail.

    The check only looks for refunds and returns; the rest waits for the user.
    """
    client = FakeMailClient()
    client.add(RETURN_NO_ORDER)
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"return_pickup_no_order_pt.eml": old_result(MailKind.UNKNOWN)}):
            engine = await async_setup_parcels(hass)
        (item,) = engine.data.review.values()
        with parsed_as({"return_pickup_no_order_pt.eml": reading}):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1}
    assert list(engine.data.review) == [item.id]
    assert record_of(engine, "return_pickup_no_order_pt.eml").state is (
        MessageState.REVIEW
    )
    assert not engine.data.returns
    assert not engine.data.parcels
