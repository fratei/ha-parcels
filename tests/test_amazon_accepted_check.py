"""Tests for the one-time re-read of Amazon's e-mails the user accepted.

Releases before 0.1.16 couldn't read Amazon's Portuguese order
confirmations, so the local AI read them, and in its suggest mode the user
accepted its answers in review: on its way, for an order. Once after the
update, Amazon's e-mails of the last 30 days whose only reading is such an
accepted answer are read again by the parsers, never the AI. Where they read
an order with confidence, their reading replaces the AI's. Then Amazon's
cancellations that were taken for partial ones cancel their parcel, where
it now reads as not shipped.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import (
    REASON_AI_SUGGESTION,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.engine import (
    AMAZON_ACCEPTED_CHECK_KEY,
    ParcelsEngine,
)
from custom_components.parcels.mail.errors import MailServerError
from custom_components.parcels.models import (
    MessageRecord,
    MessageState,
    Parcel,
    ParcelsData,
    Source,
    Suggestion,
    dt_to_str,
)
from custom_components.parcels.parsers import NOTE_KNOWN_SENDER_UNPARSED
from custom_components.parcels.parsers.base import (
    Eta,
    MailMessage,
    ParsedShipment,
    ParseResult,
)

from .common import (
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    patch_mail_clients,
)
from .test_amazon_ai_check import (
    CTT,
    ITEMS,
    NO_COUNTS,
    NOW,
    ORDER,
    ORDER_NUMBER,
    SHIPPED,
    SHIPPED_NUMBER,
    UNREAD,
    ai_read,
    mail,
    sources,
    sources_of,
    unverified,
)
from .test_returns import ai_lists, async_sync, old_result, parsed_as, record_of

# Amazon's order e-mail, as releases before 0.1.16 read it: no parser could.
UNPARSED = replace(UNREAD, notes=(NOTE_KNOWN_SENDER_UNPARSED,))
# What the local AI answered for it: on its way, due on Tuesday 8 December.
# It named Amazon as the carrier, which isn't one, so no carrier.
AI_ANSWER = Suggestion(
    kind=MailKind.IN_TRANSIT,
    merchant="Amazon",
    order_numbers=(ORDER_NUMBER,),
    eta_start=date(2026, 12, 8),
)
# Amazon's e-mails about the same order: its cancellation, and its shipment.
CANCELLATION = old_result(MailKind.CANCELLED, ORDER_NUMBER)
SHIPMENT = ParseResult(
    parser="amazon",
    kind=MailKind.SHIPPED,
    merchant="Amazon",
    order_numbers=(ORDER_NUMBER,),
    shipments=[
        ParsedShipment(
            carrier="ctt",
            tracking_number=SHIPPED_NUMBER,
            order_numbers=(ORDER_NUMBER,),
        )
    ],
    confidence=0.9,
)
ON_ITS_WAY = old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)
# The order's e-mail as the parsers read it when its things come in two
# deliveries: the lamp on Monday 7 December, the rest on Tuesday.
TWO_DELIVERIES = ParseResult(
    parser="amazon",
    kind=MailKind.ORDER,
    merchant="Amazon",
    order_numbers=(ORDER_NUMBER,),
    shipments=[
        ParsedShipment(
            kind=MailKind.ORDER,
            eta=Eta(date(2026, 12, day), date(2026, 12, day)),
            order_numbers=(ORDER_NUMBER,),
            items=items,
        )
        for day, items in ((7, ITEMS[:1]), (8, ITEMS[1:]))
    ],
    items=ITEMS,
    confidence=0.9,
)
COUNTS = {**NO_COUNTS, "read": 1, "applied": 1}


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on Friday 4 December 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


def accept(engine: ParcelsEngine, provider_id: str, **corrections: Any) -> None:
    """Accept the local AI's answer for an e-mail waiting in review.

    With ``corrections``, as the user corrected the answer.
    """
    record = record_of(engine, provider_id)
    (item,) = [i for i in engine.data.review.values() if i.message == record.hash]
    review_id = f"ai-{provider_id}"
    engine.add_review(
        replace(
            item,
            id=review_id,
            reason=REASON_AI_SUGGESTION,
            source=Source.AI,
            suggestion=AI_ANSWER,
        ),
        record,
    )
    engine.review_accept(review_id, corrections or None)
    assert sources(engine, provider_id) == {Source.AI}


def drop_cancellation(engine: ParcelsEngine, provider_id: str) -> None:
    """Drop the status of an e-mail's cancellation, as releases before 0.1.18 did.

    They took it for a partial cancellation, as the parcel's status said the
    order had shipped.
    """
    key = record_of(engine, provider_id).hash
    found = False
    for parcel in engine.data.parcels.values():
        for event in parcel.events:
            origin = parcel.origins.get(event.origin or "")
            if (
                origin is not None
                and origin.message == key
                and event.status is ParcelStatus.CANCELLED
            ):
                event.status = None
                parcel.touch(dt_util.utcnow())
                found = True
    assert found


def cancellations(parcel: Parcel) -> list[ParcelStatus | None]:
    """Return the statuses of a parcel's cancellations: None where dropped."""
    return [event.status for event in parcel.events if event.kind is MailKind.CANCELLED]


async def async_check(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> dict[str, Any]:
    """Run the check as after an update, on the next sync; return its record."""
    freezer.tick(timedelta(minutes=1))
    engine.data.engine[AMAZON_ACCEPTED_CHECK_KEY] = {
        "before": dt_to_str(dt_util.utcnow())
    }
    freezer.tick(timedelta(minutes=1))
    await async_sync(hass, engine)
    return engine.data.engine[AMAZON_ACCEPTED_CHECK_KEY]


async def async_accepted(
    hass: HomeAssistant, client: FakeMailClient, **corrections: Any
) -> ParcelsEngine:
    """Set up Parcels with Amazon's order e-mail, its AI answer accepted."""
    client.add(mail(ORDER, "order-1", sent=dt_util.utcnow() - timedelta(days=3)))
    add_hub(hass)
    add_mailbox(hass)
    with parsed_as({"order-1": UNPARSED}):
        engine = await async_setup_parcels(hass)
    accept(engine, "order-1", **corrections)
    return engine


async def test_check_reads_an_order_the_user_accepted(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An order the user accepted as on its way shows as ordered.

    Accepting the AI's answer meant the e-mail is about the user's parcel,
    not that it shipped: the parsers' reading replaces the AI's, on the same
    parcel, and stays confirmed.
    """
    client = FakeMailClient()

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client)
        (parcel,) = engine.data.parcels.values()
        assert parcel.state.status is ParcelStatus.IN_TRANSIT
        assert "amazon.es" in engine.data.engine["unparsed"]
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == COUNTS
    assert check["cancellations"] == 0
    assert set(check) == {"before", "started", "done", "counts", "cancellations"}
    assert engine.diagnostics()["amazon_accepted_check"] == check
    assert client.fetches == ["order-1"]
    assert engine.data.parcels == {parcel.id: parcel}
    assert parcel.state.status is ParcelStatus.ORDERED
    assert parcel.state.items == ITEMS
    assert parcel.state.order_numbers == (ORDER_NUMBER,)
    assert parcel.state.eta is not None
    assert parcel.state.eta.start == date(2026, 12, 7)
    (origin,) = parcel.origins.values()
    assert origin.source is Source.PARSER
    assert origin.confirmed
    assert record_of(engine, "order-1").state is MessageState.APPLIED
    assert "amazon.es" not in engine.data.engine["unparsed"]


async def test_check_confirms_each_delivery_of_the_order(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Each delivery the parsers read in the accepted e-mail stays confirmed.

    Amazon's order e-mail lists one delivery per delivery date.
    """
    client = FakeMailClient()

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client)
        (parcel,) = engine.data.parcels.values()
        with parsed_as({"order-1": TWO_DELIVERIES}):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == COUNTS
    (other,) = (p for p in engine.data.parcels.values() if p is not parcel)
    assert [(p.state.status, p.state.items) for p in (parcel, other)] == [
        (ParcelStatus.ORDERED, ITEMS[:1]),
        (ParcelStatus.ORDERED, ITEMS[1:]),
    ]
    key = record_of(engine, "order-1").hash
    origins = [
        (origin.source, origin.confirmed)
        for p in (parcel, other)
        for origin in p.origins.values()
        if origin.message == key
    ]
    assert origins == [(Source.PARSER, True)] * 2


@pytest.mark.parametrize("read", [True, False])
async def test_check_cancels_an_order_whose_cancellation_was_dropped(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, read: bool
) -> None:
    """Amazon's cancellation of an order accepted as on its way cancels it.

    Releases before 0.1.18 took it for a partial cancellation. Also where
    the parsers can't read the order's e-mail: the AI's reading of it isn't
    news that the order shipped. Once only.
    """
    client = FakeMailClient()

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client)
        client.add(mail(ORDER, "cancel-1", sent=dt_util.utcnow() - timedelta(days=1)))
        with parsed_as({"cancel-1": CANCELLATION}):
            await async_sync(hass, engine)
        drop_cancellation(engine, "cancel-1")
        engine.async_changed()
        (parcel,) = engine.data.parcels.values()
        assert parcel.state.status is ParcelStatus.IN_TRANSIT
        assert hass.states.get("sensor.parcels_in_transit").state == "1"
        with parsed_as({} if read else {"order-1": UNREAD}):
            check = await async_check(hass, engine, freezer)
            assert parcel.state.status is ParcelStatus.CANCELLED
            assert hass.states.get("sensor.parcels_in_transit").state == "0"
            again = await async_check(hass, engine, freezer)

    kept = {**NO_COUNTS, "read": 1, "kept": 1}
    assert check["counts"] == (COUNTS if read else kept)
    assert check["cancellations"] == 1
    assert engine.data.parcels == {parcel.id: parcel}
    assert sources(engine, "order-1") == {Source.PARSER if read else Source.AI}
    assert again["counts"] == (NO_COUNTS if read else kept)
    assert again["cancellations"] == 0
    assert parcel.state.status is ParcelStatus.CANCELLED


async def test_check_leaves_a_cancellation_once_the_order_shipped(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A cancellation after Amazon said the order shipped stays partial."""
    client = FakeMailClient()

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client)
        now = dt_util.utcnow()
        client.add(mail(SHIPPED, "shipped-1", sent=now - timedelta(days=2)))
        with parsed_as({"shipped-1": SHIPMENT}):
            await async_sync(hass, engine)
        client.add(mail(ORDER, "cancel-1", sent=now - timedelta(days=1)))
        with parsed_as({"cancel-1": CANCELLATION}):
            await async_sync(hass, engine)
        (parcel,) = engine.data.parcels.values()
        assert parcel.state.status is ParcelStatus.IN_TRANSIT
        assert cancellations(parcel) == [None]
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == COUNTS
    assert check["cancellations"] == 0
    assert engine.data.parcels == {parcel.id: parcel}
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert cancellations(parcel) == [None]
    assert parcel.state.tracking_number == SHIPPED_NUMBER
    assert sources(engine, "order-1") == {Source.PARSER}


@pytest.mark.parametrize("done", ["edited", "merged", "split"])
async def test_check_keeps_what_the_user_did(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, done: str
) -> None:
    """What the user set, merged or split stays as it is."""
    client = FakeMailClient()

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client)
        (parcel,) = engine.data.parcels.values()
        key = record_of(engine, "order-1").hash
        if done == "edited":
            engine.update(
                parcel.id, {"merchant": "Loja Exemplo", "eta_start": "2026-12-05"}
            )
        elif done == "merged":
            client.add(mail(CTT, "ctt"))
            await async_sync(hass, engine)
            parcel = engine.data.parcels[engine.merge(sorted(engine.data.parcels))]
        else:
            client.add(mail(ORDER, "order-2"))
            await async_sync(hass, engine)
            assert engine.data.parcels == {parcel.id: parcel}
            (origin_id,) = [o.id for o in parcel.origins.values() if o.message == key]
            parcel = engine.data.parcels[engine.split(parcel.id, [origin_id])]
        assert {o.message for o in parcel.origins.values()} >= {key}
        before = {pid: set(p.origins) for pid, p in engine.data.parcels.items()}
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == COUNTS
    assert {pid: set(p.origins) for pid, p in engine.data.parcels.items()} == before
    assert sources(engine, "order-1") == {Source.PARSER}
    assert all(o.confirmed for o in parcel.origins.values() if o.message == key)
    assert parcel.state.items == ITEMS
    if done == "edited":
        assert parcel.state.status is ParcelStatus.ORDERED
        assert parcel.state.merchant == "Loja Exemplo"
        assert parcel.state.eta is not None
        assert parcel.state.eta.start == date(2026, 12, 5)
    elif done == "merged":
        assert parcel.state.status is ParcelStatus.IN_TRANSIT
    else:
        assert len(engine.data.parcels) == 2
        assert parcel.state.status is ParcelStatus.ORDERED


@pytest.mark.parametrize("reading", ["unread", "unsure", "shipped", "unverified"])
async def test_check_keeps_what_the_parsers_dont_read_as_an_order(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, reading: str
) -> None:
    """The accepted answer stays unless the parsers read an order, verified."""
    client = FakeMailClient()

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client)
        (parcel,) = engine.data.parcels.values()
        earlier = {}
        if reading == "unread":
            earlier["order-1"] = UNREAD
        elif reading == "unsure":
            earlier["order-1"] = old_result(
                MailKind.ORDER, ORDER_NUMBER, confidence=0.5
            )
        elif reading == "shipped":
            earlier["order-1"] = old_result(MailKind.SHIPPED, ORDER_NUMBER)
        else:
            client.messages["order-1"] = unverified(client.messages["order-1"])
        with parsed_as(earlier):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert engine.data.parcels == {parcel.id: parcel}
    assert parcel.state.status is ParcelStatus.IN_TRANSIT
    assert sources(engine, "order-1") == {Source.AI}


@pytest.mark.parametrize(
    "corrections",
    [
        {"carrier": "ctt", "tracking_numbers": [SHIPPED_NUMBER]},
        {"amazon_shipment_id": "Rq5TbY8wZ"},
    ],
    ids=["tracking_number", "amazon_shipment"],
)
async def test_check_keeps_an_answer_with_a_tracking_number(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, corrections: dict[str, Any]
) -> None:
    """An accepted answer with a tracking number or a shipment stays.

    The parsers read none in an order's e-mail, so their reading would lose
    what the user may have typed in.
    """
    client = FakeMailClient()

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client, **corrections)
        (parcel,) = engine.data.parcels.values()
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert engine.data.parcels == {parcel.id: parcel}
    assert sources(engine, "order-1") == {Source.AI}


@pytest.mark.parametrize("meanwhile", ["removed", "forgotten"])
async def test_check_leaves_an_email_that_changed_while_read(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, meanwhile: str
) -> None:
    """Nothing changes when the e-mail is removed or forgotten while it's read.

    The daily cleanup forgets e-mails 120 days after they were seen.
    """
    client = FakeMailClient()

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client)
        (parcel,) = engine.data.parcels.values()
        (origin_id,) = parcel.origins
        record = record_of(engine, "order-1")

        def change(message: MailMessage) -> None:
            if meanwhile == "forgotten":
                engine.data.messages.pop(record.hash, None)
            elif record.state is MessageState.APPLIED:
                engine.remove_email(parcel.id, origin_id)

        with parsed_as({}, during=change):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    if meanwhile == "removed":
        assert record.state is MessageState.FILTERED
        assert not engine.data.parcels
        return
    assert record.hash not in engine.data.messages
    assert engine.data.parcels == {parcel.id: parcel}
    assert sources_of(engine, record.hash) == {Source.AI}


async def test_check_reads_only_accepted_answers_about_amazons_emails(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Only Amazon's e-mails of the last 30 days, with an accepted answer.

    Not one whose AI answer nobody confirmed, nor one the parsers read, nor
    another sender's, nor older ones, nor one read since the update.
    """
    now = dt_util.utcnow()
    client = FakeMailClient()
    for days, name in enumerate(("accepted", "unconfirmed", "parser"), start=1):
        client.add(mail(ORDER, name, sent=now - timedelta(days=days)))
    client.add(mail(ORDER, "old", sent=now - timedelta(days=40)))
    client.add(mail(CTT, "ctt"))
    add_hub(hass)
    add_mailbox(hass)
    stored = dict.fromkeys(("accepted", "unconfirmed", "old", "late"), ON_ITS_WAY)

    with patch_mail_clients(client):
        with parsed_as(stored):
            engine = await async_setup_parcels(hass)
            freezer.tick(timedelta(minutes=1))
            before = dt_to_str(dt_util.utcnow())
            freezer.tick(timedelta(minutes=1))
            client.add(mail(ORDER, "late"))
            await async_sync(hass, engine)
        for name in ("accepted", "old", "ctt", "late"):
            ai_read(engine, name, confirmed=True)
        ai_read(engine, "unconfirmed")
        client.fetches.clear()
        engine.data.engine[AMAZON_ACCEPTED_CHECK_KEY] = {"before": before}
        await async_sync(hass, engine)

    check = engine.data.engine[AMAZON_ACCEPTED_CHECK_KEY]
    assert check["counts"] == COUNTS
    assert client.fetches == ["accepted"]
    assert {
        name: sources(engine, name)
        for name in ("accepted", "unconfirmed", "parser", "old", "ctt", "late")
    } == {
        "accepted": {Source.PARSER},
        "unconfirmed": {Source.AI},
        "parser": {Source.PARSER},
        "old": {Source.AI},
        "ctt": {Source.AI},
        "late": {Source.AI},
    }


async def test_check_leaves_a_sender_the_user_ignores(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Amazon's e-mails aren't read again once the user ignores Amazon.

    Nor do its cancellations cancel parcels.
    """
    client = FakeMailClient()

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client)
        client.add(mail(ORDER, "cancel-1"))
        with parsed_as({"cancel-1": CANCELLATION}):
            await async_sync(hass, engine)
        drop_cancellation(engine, "cancel-1")
        engine.ignore_domain("amazon.es")
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == NO_COUNTS
    assert check["cancellations"] == 0
    assert client.fetches == []
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.status is ParcelStatus.IN_TRANSIT
    assert sources(engine, "order-1") == {Source.AI}


@pytest.mark.parametrize("forced", [False, True])
async def test_check_leaves_an_email_the_user_asked_the_ai_to_read(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, local_ai: str, forced: bool
) -> None:
    """An e-mail the user asked the AI to fill in isn't read.

    Otherwise what the AI was to fill in goes once the parsers read it.
    """
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass, ai_task_entity=local_ai, ai_mode="suggest")
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": ON_ITS_WAY}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1", confirmed=True)
        record = record_of(engine, "order-1")
        (entry,) = engine.ai.queue
        assert entry["fill"]
        if forced:
            entry["forced"] = True
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    if forced:
        assert check["counts"] == NO_COUNTS
        assert client.fetches == []
        assert ai_lists(engine) == [record.hash]
        assert sources(engine, "order-1") == {Source.AI}
        return
    assert check["counts"] == COUNTS
    assert ai_lists(engine) == []
    assert sources(engine, "order-1") == {Source.PARSER}


async def test_check_leaves_an_archived_parcel_archived(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A parcel put away stays put away when its e-mail is read again."""
    client = FakeMailClient()

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client)
        (parcel,) = engine.data.parcels.values()
        engine.archive(parcel.id)
        archived = parcel.archived
        assert archived is not None
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == COUNTS
    assert engine.data.parcels == {parcel.id: parcel}
    assert parcel.archived == archived
    assert parcel.state.status is ParcelStatus.ORDERED
    assert sources(engine, "order-1") == {Source.PARSER}


async def test_check_reads_at_most_its_limit(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The newest e-mails are read first, up to the limit; the rest are counted."""
    now = dt_util.utcnow()
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1", sent=now - timedelta(days=2)))
    client.add(mail(ORDER, "order-2", sent=now - timedelta(days=1)))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": ON_ITS_WAY, "order-2": ON_ITS_WAY}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1", confirmed=True)
        ai_read(engine, "order-2", confirmed=True)
        client.fetches.clear()
        with patch("custom_components.parcels.engine.AMAZON_AI_CHECK_MAX", 1):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**COUNTS, "skipped": 1}
    assert client.fetches == ["order-2"]
    assert sources(engine, "order-1") == {Source.AI}
    assert sources(engine, "order-2") == {Source.PARSER}


async def test_check_counts_emails_it_cant_download(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail deleted since counts as gone, one that won't download as failed."""
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    client.add(mail(ORDER, "order-2"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": ON_ITS_WAY, "order-2": ON_ITS_WAY}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1", confirmed=True)
        ai_read(engine, "order-2", confirmed=True)
        keys = [record_of(engine, name).hash for name in ("order-1", "order-2")]
        client.delete("order-1")
        client.fetch_errors["order-2"] = MailServerError("down")
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "gone": 1, "failed": 1}
    assert [sources_of(engine, key) for key in keys] == [{Source.AI}, {Source.AI}]


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
            state=MessageState.APPLIED,
            sender_domain="amazon.es",
        )
    checked = {
        "done": dt_to_str(now - timedelta(days=1)),
        "counts": NO_COUNTS,
        "cancellations": 0,
    }
    if stored == "checked":
        data.engine[AMAZON_ACCEPTED_CHECK_KEY] = deepcopy(checked)
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)

    engine = await async_setup_parcels(hass)

    assert (
        engine.data.engine[AMAZON_ACCEPTED_CHECK_KEY]
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

    with patch_mail_clients(client):
        engine = await async_accepted(hass, client)
        client.fetches.clear()
        freezer.tick(timedelta(minutes=1))
        now = dt_to_str(dt_util.utcnow())
        started = {"before": now, "started": now}
        engine.data.engine[AMAZON_ACCEPTED_CHECK_KEY] = deepcopy(started)
        freezer.tick(timedelta(minutes=1))
        await async_sync(hass, engine)

    assert engine.data.engine[AMAZON_ACCEPTED_CHECK_KEY] == started
    assert client.fetches == []
    assert sources(engine, "order-1") == {Source.AI}
