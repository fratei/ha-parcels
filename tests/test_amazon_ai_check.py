"""Tests for the one-time re-read of Amazon's e-mails that the local AI read.

Releases before 0.1.16 couldn't read Amazon's Portuguese order
confirmations, so the local AI read them, or they waited in review. Once
after the update, Amazon's e-mails of the last 30 days that the AI read, or
that wait in review, are read again by the parsers, never the AI. Where the
parsers read one with confidence, their reading replaces the AI's.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import (
    DOMAIN,
    ISSUE_PARSER_OUTDATED,
    REASON_AI_SUGGESTION,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.convert import fill_origin_id
from custom_components.parcels.engine import AMAZON_AI_CHECK_KEY, ParcelsEngine
from custom_components.parcels.mail.errors import MailServerError
from custom_components.parcels.models import (
    MessageRecord,
    MessageState,
    ParcelsData,
    Source,
    Suggestion,
    dt_to_str,
)
from custom_components.parcels.parsers import NOTE_KNOWN_SENDER_UNPARSED
from custom_components.parcels.parsers.auth import parse_authentication_results
from custom_components.parcels.parsers.base import (
    MailMessage,
    ParsedShipment,
    ParseResult,
)
from custom_components.parcels.parsers.normalize import message_from_bytes

from .common import (
    ADDRESS,
    EMAIL_FIXTURES,
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    patch_mail_clients,
)
from .test_returns import ai_lists, async_sync, old_result, parsed_as, record_of

NOW = "2026-12-04 09:00:00+00:00"
# Thursday 3 December: Amazon's order of a lamp and two more things, due on
# Monday 7 December.
ORDER = "amazon/order_pedido_pt.eml"
ORDER_NUMBER = "406-2958173-6604821"
ITEMS = (
    "Candeeiro de mesa Exemplo, LED, regulável, branco",
    "Lâmpada LED E27 Exemplo, 9 W, pack de 2",
    "Extensão elétrica Exemplo com 3 tomadas",
)
# Wednesday 18 November: Amazon sent a cookery book with CTT.
SHIPPED = "amazon/shipped_ctt_pt.eml"
SHIPPED_ORDER = "406-1928374-5647382"
SHIPPED_NUMBER = "RR473124829PT"
CTT = "carriers/ctt_in_transit_pt.eml"
# What a release before 0.1.16 read in Amazon's Portuguese order e-mails.
UNREAD = old_result(MailKind.UNKNOWN, confidence=0.0)
NO_COUNTS = dict.fromkeys(("read", "applied", "kept", "gone", "failed", "skipped"), 0)


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on Friday 4 December 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


def mail(path: str, provider_id: str, *, sent: datetime | None = None) -> MailMessage:
    """Return a fixture as an e-mail of its own, sent at ``sent``."""
    raw = (EMAIL_FIXTURES / path).read_bytes()
    message = message_from_bytes(
        raw, mailbox=ADDRESS, provider_id=provider_id, provider="google"
    )
    message = replace(message, message_id=f"<{provider_id}@mail.example.com>")
    if sent is not None:
        message = replace(message, date=sent, received=sent)
    return message


def unverified(message: MailMessage) -> MailMessage:
    """Return an e-mail with a header that a server Parcels doesn't trust wrote."""
    header = "mx.example.net; dkim=pass header.d=amazon.es"
    return replace(
        message, auth=parse_authentication_results(header), auth_headers=(header,)
    )


def ai_read(
    engine: ParcelsEngine, provider_id: str, *, confirmed: bool = False
) -> None:
    """Make what an e-mail added look as the local AI added it."""
    key = record_of(engine, provider_id).hash
    found = False
    for parcel in engine.data.parcels.values():
        origins = [o for o in parcel.origins.values() if o.message == key]
        for origin in origins:
            origin.source = Source.AI
            origin.confirmed = confirmed
            for event in parcel.events:
                if event.origin == origin.id:
                    event.source = Source.AI
        if origins:
            parcel.touch(dt_util.utcnow())
            found = True
    assert found


def sources(engine: ParcelsEngine, provider_id: str) -> set[Source]:
    """Return the sources of what an e-mail added to parcels."""
    return sources_of(engine, record_of(engine, provider_id).hash)


def sources_of(engine: ParcelsEngine, key: str) -> set[Source]:
    """Return the sources of what the e-mail with this hash added to parcels."""
    return {
        origin.source
        for parcel in engine.data.parcels.values()
        for origin in parcel.origins.values()
        if origin.message == key
    }


def review_of(engine: ParcelsEngine, provider_id: str) -> list[str]:
    """Return the IDs of an e-mail's review items."""
    key = record_of(engine, provider_id).hash
    return [item.id for item in engine.data.review.values() if item.message == key]


async def async_check(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> dict[str, Any]:
    """Run the check as after an update, on the next sync; return its record."""
    freezer.tick(timedelta(minutes=1))
    engine.data.engine[AMAZON_AI_CHECK_KEY] = {"before": dt_to_str(dt_util.utcnow())}
    freezer.tick(timedelta(minutes=1))
    await async_sync(hass, engine)
    return engine.data.engine[AMAZON_AI_CHECK_KEY]


async def test_check_reads_an_order_the_ai_read(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An order the local AI took for a parcel on its way shows as ordered.

    The parcel stays the same, with what the parsers read: the items and
    the day it's due.
    """
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
        (parcel,) = engine.data.parcels.values()
        assert parcel.state.status is ParcelStatus.IN_TRANSIT
        assert parcel.state.ai
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    assert set(check) == {"before", "started", "done", "counts"}
    assert engine.diagnostics()["amazon_ai_check"] == check
    assert client.fetches == ["order-1"]
    assert engine.data.parcels == {parcel.id: parcel}
    assert parcel.state.status is ParcelStatus.ORDERED
    assert parcel.state.items == ITEMS
    assert parcel.state.order_numbers == (ORDER_NUMBER,)
    assert parcel.state.eta is not None
    assert parcel.state.eta.start == date(2026, 12, 7)
    assert not parcel.state.ai
    assert sources(engine, "order-1") == {Source.PARSER}
    assert record_of(engine, "order-1").state is MessageState.APPLIED


async def test_check_keeps_what_the_ai_filled_in(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """What the AI filled in, as when the user checks a parcel again, stays."""
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
        record = record_of(engine, "order-1")
        now = dt_util.utcnow()
        parcel_id = engine.apply_fill(
            Suggestion(kind=MailKind.UNKNOWN, carrier="CTT"),
            record,
            time=now,
            label="amazon.es",
            now=now,
        )
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    (parcel,) = engine.data.parcels.values()
    assert parcel.id == parcel_id
    assert parcel.origins[fill_origin_id(record.hash)].source is Source.AI
    assert parcel.state.status is ParcelStatus.ORDERED


async def test_check_leaves_a_sender_the_user_ignores(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Amazon's e-mails aren't read again once the user ignores Amazon."""
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
        engine.ignore_domain("amazon.es")
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == NO_COUNTS
    assert client.fetches == []
    assert sources(engine, "order-1") == {Source.AI}


TWO_SHIPMENTS = ParseResult(
    parser="amazon",
    kind=MailKind.IN_TRANSIT,
    merchant="Amazon",
    order_numbers=(ORDER_NUMBER,),
    shipments=[
        ParsedShipment(order_numbers=(ORDER_NUMBER,), items=("Artigo A Exemplo",)),
        ParsedShipment(order_numbers=(ORDER_NUMBER,), items=("Artigo B Exemplo",)),
    ],
    confidence=0.9,
)


@pytest.mark.parametrize("edited", [False, True])
async def test_check_drops_parcels_only_the_ai_saw(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, edited: bool
) -> None:
    """A parcel the AI read in the e-mail and the parsers don't goes.

    Unless the user edited it: then it stays, with what the user set.
    """
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": TWO_SHIPMENTS}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
        first, second = sorted(
            engine.data.parcels.values(), key=lambda parcel: parcel.state.items
        )
        assert (first.state.items, second.state.items) == (
            ("Artigo A Exemplo",),
            ("Artigo B Exemplo",),
        )
        if edited:
            engine.update(second.id, {"merchant": "Loja Exemplo"})
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    assert first.state.status is ParcelStatus.ORDERED
    assert first.state.items == ITEMS
    if edited:
        assert engine.data.parcels == {first.id: first, second.id: second}
        assert second.state.merchant == "Loja Exemplo"
        assert second.state.items == ("Artigo B Exemplo",)
        assert sources(engine, "order-1") == {Source.PARSER, Source.AI}
        return
    assert engine.data.parcels == {first.id: first}
    assert sources(engine, "order-1") == {Source.PARSER}


async def test_check_leaves_an_archived_parcel_archived(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A parcel put away stays put away when its e-mail is read again."""
    client = FakeMailClient()
    client.add(mail(SHIPPED, "shipped-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"shipped-1": old_result(MailKind.IN_TRANSIT, SHIPPED_ORDER)}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "shipped-1")
        (parcel,) = engine.data.parcels.values()
        engine.archive(parcel.id)
        archived = parcel.archived
        assert archived is not None
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    assert engine.data.parcels == {parcel.id: parcel}
    assert parcel.archived == archived
    assert parcel.state.tracking_number == SHIPPED_NUMBER
    assert sources(engine, "shipped-1") == {Source.PARSER}


@pytest.mark.parametrize("read_by", ["parser", "ai"])
async def test_check_reads_an_order_waiting_in_review(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, read_by: str
) -> None:
    """An order waiting in review is added, and leaves the review list.

    Whether no parser could read it, or the AI suggested a reading.
    """
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass)
    add_mailbox(hass)
    unread = replace(UNREAD, notes=(NOTE_KNOWN_SENDER_UNPARSED,))

    with patch_mail_clients(client):
        with parsed_as({"order-1": unread}):
            engine = await async_setup_parcels(hass)
        record = record_of(engine, "order-1")
        assert record.state is MessageState.REVIEW
        (item,) = engine.data.review.values()
        if read_by == "ai":
            suggestion = Suggestion(
                kind=MailKind.IN_TRANSIT, order_numbers=(ORDER_NUMBER,)
            )
            engine.add_review(
                replace(
                    item,
                    id="r-ai",
                    reason=REASON_AI_SUGGESTION,
                    source=Source.AI,
                    suggestion=suggestion,
                ),
                record,
            )
            assert list(engine.data.review) == ["r-ai"]
        assert not engine.data.parcels
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    assert not engine.data.review
    assert record.state is MessageState.APPLIED
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.status is ParcelStatus.ORDERED
    assert parcel.state.items == ITEMS


async def test_check_reads_only_what_the_ai_read_or_waits_in_review(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Only Amazon's e-mails of the last 30 days that the AI read are read.

    Or those that wait in review, or that the AI took for something else
    than a parcel. Not those the parsers read, nor another sender's, nor
    one the user confirmed, removed from Parcels or dismissed, nor older
    ones, nor one read since the update.
    """
    now = dt_util.utcnow()
    names = ("ai-applied", "filtered", "removed", "confirmed", "parser", "dismissed")
    client = FakeMailClient()
    for days, name in enumerate(names, start=1):
        client.add(mail(ORDER, name, sent=now - timedelta(days=days)))
    client.add(mail(ORDER, "old", sent=now - timedelta(days=40)))
    client.add(mail(CTT, "ctt"))
    add_hub(hass)
    add_mailbox(hass)
    on_its_way = old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)
    stored = {
        "ai-applied": on_its_way,
        "confirmed": on_its_way,
        "old": on_its_way,
        "filtered": UNREAD,
        "dismissed": UNREAD,
    }

    with patch_mail_clients(client):
        with parsed_as(stored):
            engine = await async_setup_parcels(hass)
        for name in ("ai-applied", "old", "ctt"):
            ai_read(engine, name)
        ai_read(engine, "confirmed", confirmed=True)
        removed = record_of(engine, "removed").hash
        (parcel,) = [
            parcel
            for parcel in engine.data.parcels.values()
            if any(origin.message == removed for origin in parcel.origins.values())
        ]
        engine.remove_email(parcel.id, f"msg:{removed}#0")
        # The AI took it for something else than a parcel.
        (review_id,) = review_of(engine, "filtered")
        item = engine.data.review.pop(review_id)
        engine.add_filtered(item, record_of(engine, "filtered"))
        (review_id,) = review_of(engine, "dismissed")
        engine.review_dismiss(review_id)
        client.fetches.clear()
        client.add(mail(ORDER, "new"))
        with parsed_as({"new": UNREAD}):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 2, "applied": 2}
    assert client.fetches == ["new", "ai-applied", "filtered"]
    assert {
        name: record_of(engine, name).state
        for name in ("ai-applied", "filtered", "removed", "dismissed", "new")
    } == {
        "ai-applied": MessageState.APPLIED,
        "filtered": MessageState.APPLIED,
        "removed": MessageState.FILTERED,
        "dismissed": MessageState.DISMISSED,
        "new": MessageState.REVIEW,
    }
    assert {
        name: sources(engine, name)
        for name in ("ai-applied", "filtered", "confirmed", "parser", "old", "ctt")
    } == {
        "ai-applied": {Source.PARSER},
        "filtered": {Source.PARSER},
        "confirmed": {Source.AI},
        "parser": {Source.PARSER},
        "old": {Source.AI},
        "ctt": {Source.AI},
    }
    assert [entry.removed for entry in engine.data.filtered.values()] == [True]


@pytest.mark.parametrize("forced", [False, True])
async def test_check_reads_an_email_waiting_for_the_ai(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, local_ai: str, forced: bool
) -> None:
    """An e-mail waiting for the AI is read by the parsers instead.

    Unless the user asked the AI to read it. The parsers' reading isn't
    given to the AI afterwards.
    """
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass, ai_task_entity=local_ai, ai_mode="suggest")
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": UNREAD}):
            engine = await async_setup_parcels(hass)
        record = record_of(engine, "order-1")
        assert record.state is MessageState.QUEUED
        (entry,) = engine.ai.queue
        if forced:
            entry["forced"] = True
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    if forced:
        assert check["counts"] == NO_COUNTS
        assert client.fetches == []
        assert record.state is MessageState.QUEUED
        assert ai_lists(engine) == [record.hash]
        assert not engine.data.parcels
        return
    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    assert record.state is MessageState.APPLIED
    assert ai_lists(engine) == []
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.status is ParcelStatus.ORDERED


@pytest.mark.parametrize("forced", [False, True])
async def test_check_drops_a_fill_waiting_for_the_ai(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, local_ai: str, forced: bool
) -> None:
    """What the AI was to fill in goes once the parsers read the e-mail.

    Unless the user asked the AI to fill it in: then the e-mail isn't read.
    """
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass, ai_task_entity=local_ai, ai_mode="suggest")
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
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
    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    assert ai_lists(engine) == []
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
    on_its_way = old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)

    with patch_mail_clients(client):
        with parsed_as({"order-1": on_its_way, "order-2": on_its_way}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
        ai_read(engine, "order-2")
        client.fetches.clear()
        with patch("custom_components.parcels.engine.AMAZON_AI_CHECK_MAX", 1):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1, "skipped": 1}
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
    on_its_way = old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)

    with patch_mail_clients(client):
        with parsed_as({"order-1": on_its_way, "order-2": on_its_way}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
        ai_read(engine, "order-2")
        keys = [record_of(engine, name).hash for name in ("order-1", "order-2")]
        client.delete("order-1")
        client.fetch_errors["order-2"] = MailServerError("down")
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "gone": 1, "failed": 1}
    assert [sources_of(engine, key) for key in keys] == [{Source.AI}, {Source.AI}]


async def test_check_keeps_what_the_parsers_cant_read(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """What the AI read stays when the parsers can't read the e-mail either."""
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
        (parcel,) = engine.data.parcels.values()
        with parsed_as({"order-1": UNREAD}):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert engine.data.parcels == {parcel.id: parcel}
    assert parcel.state.status is ParcelStatus.IN_TRANSIT
    assert sources(engine, "order-1") == {Source.AI}


async def test_check_keeps_an_unverified_email_in_review(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail whose sender isn't verified stays in review."""
    client = FakeMailClient()
    client.add(unverified(mail(ORDER, "order-1")))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        record = record_of(engine, "order-1")
        assert record.state is MessageState.REVIEW
        review = review_of(engine, "order-1")
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert record.state is MessageState.REVIEW
    assert review_of(engine, "order-1") == review
    assert not engine.data.parcels


async def test_check_leaves_an_email_removed_meanwhile(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail the user removes from Parcels while it's read stays removed."""
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
        (parcel,) = engine.data.parcels.values()
        (origin_id,) = parcel.origins
        record = record_of(engine, "order-1")

        def remove(message: MailMessage) -> None:
            if record.state is MessageState.APPLIED:
                engine.remove_email(parcel.id, origin_id)

        with parsed_as({}, during=remove):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert record.state is MessageState.FILTERED
    assert not engine.data.parcels


async def test_check_leaves_an_email_forgotten_meanwhile(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail forgotten while it's read isn't added.

    The daily cleanup forgets e-mails 120 days after they were seen.
    """
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass)
    add_mailbox(hass)
    unread = replace(UNREAD, notes=(NOTE_KNOWN_SENDER_UNPARSED,))

    with patch_mail_clients(client):
        with parsed_as({"order-1": unread}):
            engine = await async_setup_parcels(hass)
        (item,) = engine.data.review.values()
        key = record_of(engine, "order-1").hash

        def forget(message: MailMessage) -> None:
            engine.data.messages.pop(key, None)

        with parsed_as({}, during=forget):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert key not in engine.data.messages
    assert list(engine.data.review) == [item.id]
    assert not engine.data.parcels


async def test_check_leaves_what_the_user_set(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The shop and the day the user gave a parcel still show after the check."""
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
        (parcel,) = engine.data.parcels.values()
        engine.update(
            parcel.id, {"merchant": "Loja Exemplo", "eta_start": "2026-12-09"}
        )
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    assert engine.data.parcels == {parcel.id: parcel}
    assert parcel.state.status is ParcelStatus.ORDERED
    assert parcel.state.items == ITEMS
    assert parcel.state.merchant == "Loja Exemplo"
    assert parcel.state.eta is not None
    assert parcel.state.eta.start == date(2026, 12, 9)


async def test_check_clears_the_outdated_parser_repair(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Once the parsers read Amazon's e-mails, the repair about them goes."""
    now = dt_util.utcnow()
    client = FakeMailClient()
    client.add(mail(ORDER, "order-1", sent=now - timedelta(days=2)))
    client.add(mail(ORDER, "order-2", sent=now - timedelta(days=1)))
    add_hub(hass)
    add_mailbox(hass)
    unread = replace(UNREAD, notes=(NOTE_KNOWN_SENDER_UNPARSED,))
    issue = ISSUE_PARSER_OUTDATED.format("amazon.es")

    with patch_mail_clients(client):
        with parsed_as({"order-1": unread, "order-2": unread}):
            engine = await async_setup_parcels(hass)
        for item in engine.data.review.values():
            engine.note_unparsed_read(item, now)
        assert ir.async_get(hass).async_get_issue(DOMAIN, issue) is not None
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 2, "applied": 2}
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue) is None
    assert "amazon.es" not in engine.data.engine.get("unparsed", {})


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
    checked = {"done": dt_to_str(now - timedelta(days=1)), "counts": NO_COUNTS}
    if stored == "checked":
        data.engine[AMAZON_AI_CHECK_KEY] = deepcopy(checked)
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)

    engine = await async_setup_parcels(hass)

    assert (
        engine.data.engine[AMAZON_AI_CHECK_KEY]
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
    client.add(mail(ORDER, "order-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": old_result(MailKind.IN_TRANSIT, ORDER_NUMBER)}):
            engine = await async_setup_parcels(hass)
        ai_read(engine, "order-1")
        client.fetches.clear()
        freezer.tick(timedelta(minutes=1))
        now = dt_to_str(dt_util.utcnow())
        started = {"before": now, "started": now}
        engine.data.engine[AMAZON_AI_CHECK_KEY] = deepcopy(started)
        freezer.tick(timedelta(minutes=1))
        await async_sync(hass, engine)

    assert engine.data.engine[AMAZON_AI_CHECK_KEY] == started
    assert client.fetches == []
    assert sources(engine, "order-1") == {Source.AI}
