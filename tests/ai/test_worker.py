"""Tests for the local AI queue worker.

The worker's loop is replaced by an idle stand-in, so each test runs the
steps itself with ``engine.ai._async_step()``; the loop has its own tests at
the end. The e-mails are the synthetic CTT fixture with its body replaced by
text that no parser reads, so the engine queues them for the AI.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
import dataclasses
from datetime import UTC, date, datetime, timedelta
import logging
import types
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.ai.client import DATA_LOG_FILTER, LOGGER_NAMES
from custom_components.parcels.ai_worker import (
    STATUS_BUSY,
    STATUS_IDLE,
    STATUS_LIMIT,
    STATUS_OFF,
    STATUS_PAUSED,
    AIWorker,
    error_location,
)
from custom_components.parcels.const import (
    AI_DAILY_LIMIT,
    AI_FILL_DAILY_LIMIT,
    AI_SHADOW_DAILY_LIMIT,
    CONF_AI_MODE,
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_MAILBOX,
    ISSUE_AI_REFUSED,
    ISSUE_AI_UNAVAILABLE,
    REASON_AI_FILL,
    REASON_AI_REJECTED,
    REASON_AI_SUGGESTION,
    REASON_AI_TIMEOUT,
    REASON_AI_UNAVAILABLE,
    REASON_UNKNOWN_FORMAT,
    REASON_UNKNOWN_SENDER,
    MailKind,
)
from custom_components.parcels.convert import fill_origin_id, message_origin_id
from custom_components.parcels.engine import (
    FILL_CHECK_KEY,
    PAACK_CHECK_KEY,
    ParcelsEngine,
)
from custom_components.parcels.mail.errors import MailError
from custom_components.parcels.models import (
    MessageState,
    ParcelStatus,
    ReviewItem,
    Source,
    Suggestion,
)
from custom_components.parcels.parsers.base import (
    MailMessage,
    ParseResult,
    SenderVerdict,
)
from custom_components.parcels.views import SYSTEM_VIEWER, Viewer, settings_json

from ..common import (
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    load_message,
    patch_mail_clients,
)
from .common import LOCAL_MODEL, add_ai_task, answer
from .conftest import FakeResult

NOW = "2026-11-17 10:00:00+00:00"
RECEIVED = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
IN_30_MINUTES = "2026-11-17T10:30:00+00:00"
CTT = "carriers/ctt_in_transit_pt.eml"
# The CTT fixture's subject holds this number, so the AI's checks find it.
TRACKING = "RR482915732PT"
UNREADABLE = "Olá, temos novidades. Consulte em breve."
# An unknown shop's return: picked up the working day after, Wednesday 18 Nov.
SHOP_RETURN = (
    "Devolução da encomenda #1001",
    "Recebemos o seu pedido de devolução da encomenda #1001.\n"
    "Data de recolha: Dia útil seguinte",
)
PICKUP_DAY = date(2026, 11, 18)
CLOUD_MODEL = "gpt-oss:120b-cloud"
SECRET = "Rua Secreta 99"
REAL_RUN = AIWorker._async_run


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on 17 November 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


@pytest.fixture(autouse=True)
def remove_log_filter(hass: HomeAssistant) -> Iterator[None]:
    """Take the AI log filter off the global loggers after each test."""
    yield
    install = hass.data.pop(DATA_LOG_FILTER, None)
    if install is not None:
        for name in LOGGER_NAMES:
            logging.getLogger(name).removeFilter(install.log_filter)


@pytest.fixture(autouse=True)
def no_loop() -> Iterator[None]:
    """Replace the worker's loop by one that returns at once."""

    async def idle(self: AIWorker) -> None:
        return None

    with patch.object(AIWorker, "_async_run", idle):
        yield


@pytest.fixture(autouse=True)
def generate(fake_ai_task: types.ModuleType) -> AsyncMock:
    """Return the AI task's ``async_generate_data`` stand-in."""
    return fake_ai_task.async_generate_data


@pytest.fixture
async def client(hass: HomeAssistant) -> AsyncIterator[FakeMailClient]:
    """Return the mailbox, patched in for the whole test.

    The mailbox unloads before the hub at the end: a hub that unloads first
    reloads it, and the reloaded mailbox would wait for the hub on a frozen
    clock.
    """
    client = FakeMailClient()
    with patch_mail_clients(client):
        yield client
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_MAILBOX:
                await hass.config_entries.async_unload(entry.entry_id)


def ctt_message(
    text: str | None = UNREADABLE,
    *,
    number: int = 1,
    received: datetime = RECEIVED,
    subject: str | None = None,
) -> MailMessage:
    """Return the CTT e-mail with its own Message-ID and ``text`` as its body.

    ``text=None`` keeps the fixture's body, which the CTT parser reads.
    """
    changes: dict[str, Any] = {}
    if text is not None:
        changes.update(text=text, links=())
    if subject is not None:
        changes["subject"] = subject
    return dataclasses.replace(
        load_message(CTT),
        message_id=f"<ai-worker-{number}@mail.example.com>",
        provider_id=f"ctt-{number}",
        date=received,
        received=received,
        **changes,
    )


def shop_message(subject: str, text: str) -> MailMessage:
    """Return the example shop's e-mail with its subject and body replaced."""
    return dataclasses.replace(
        load_message("common/order_confirmation.eml"),
        subject=subject,
        text=text,
        links=(),
        date=RECEIVED,
        received=RECEIVED,
    )


def result(*, data: Any = None, **values: Any) -> FakeResult:
    """Return an AI task result: ``data``, or an answer with ``values``."""
    return FakeResult("conversation-1", answer(**values) if data is None else data)


async def async_setup(
    hass: HomeAssistant,
    client: FakeMailClient,
    *messages: MailMessage,
    mode: str = "suggest",
    model: str = LOCAL_MODEL,
) -> ParcelsEngine:
    """Load the hub with a local AI task and a mailbox holding ``messages``."""
    for message in messages:
        client.add(message)
    entity_id = add_ai_task(hass, model=model)
    hass.config.components.add("ai_task")
    hass.states.async_set(entity_id, "2026-11-17T09:00:00+00:00")
    add_hub(hass, ai_task_entity=entity_id, ai_mode=mode)
    add_mailbox(hass)
    return await async_setup_parcels(hass)


def issue(hass: HomeAssistant, issue_id: str) -> ir.IssueEntry | None:
    """Return a repair issue of Parcels."""
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_id)


# -- Answers ------------------------------------------------------------------


async def test_suggest_mode_offers_the_answer(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """In suggest mode the AI's reading waits under "Needs review"."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    record = engine.data.messages[message.hash]
    assert record.state is MessageState.QUEUED
    assert engine.ai.queue_size == 1
    generate.return_value = result(kind="in_transit")

    assert await engine.ai._async_step() == 0

    generate.assert_awaited_once()
    assert generate.await_args.kwargs["entity_id"] == engine.ai_entity
    assert record.state is MessageState.REVIEW
    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_SUGGESTION
    assert item.source is Source.AI
    assert item.suggestion is not None
    assert item.suggestion.kind is MailKind.IN_TRANSIT
    assert item.suggestion.tracking_numbers == (TRACKING,)
    assert engine.ai.queue_size == 0
    assert not engine.data.parcels
    assert engine.ai.today()["calls"] == 1
    assert engine.ai.today()["suggested"] == 1
    assert engine.ai.status == STATUS_IDLE


async def test_auto_mode_applies_a_trusted_answer(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """In auto mode a confident reading of a verified sender's e-mail is applied."""
    message = ctt_message()
    engine = await async_setup(hass, client, message, mode="auto")
    generate.return_value = result(kind="shipped")

    await engine.ai._async_step()

    assert engine.data.messages[message.hash].state is MessageState.APPLIED
    assert not engine.data.review
    (parcel,) = engine.data.parcels.values()
    origins = list(parcel.origins.values())
    assert [origin.source for origin in origins] == [Source.AI]
    assert [origin.tracking_number for origin in origins] == [TRACKING]
    assert engine.ai.today()["applied"] == 1


async def test_auto_mode_only_suggests_for_unverified_senders(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """A shop that isn't on the allow-list only gets a suggestion, even in auto mode."""
    message = dataclasses.replace(
        load_message("common/order_confirmation.eml"), date=RECEIVED, received=RECEIVED
    )
    engine = await async_setup(hass, client, message, mode="auto")
    assert engine.ai.queue_size == 1
    generate.return_value = result(kind="order", order_numbers=["1001"])

    await engine.ai._async_step()

    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_SUGGESTION
    assert item.suggestion is not None
    assert item.suggestion.order_numbers == ("1001",)
    assert not engine.data.parcels
    assert engine.ai.today()["applied"] == 0


async def test_not_parcel_answer_is_filtered(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """A confident "not about a parcel" moves the e-mail to the filtered list."""
    message = ctt_message(
        "Temos novidades sobre a sua entrega. Consulte em breve.",
        subject="Informação sobre a entrega",
    )
    engine = await async_setup(hass, client, message)
    assert engine.ai.queue_size == 1
    generate.return_value = result(kind="not_parcel")

    await engine.ai._async_step()

    assert engine.data.messages[message.hash].state is MessageState.FILTERED
    assert len(engine.data.filtered) == 1
    assert not engine.data.review
    assert engine.ai.today()["filtered"] == 1


async def test_not_parcel_answer_with_a_tracking_number_is_rejected(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """ "Not about a parcel" for an e-mail with a tracking number goes to review."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    generate.return_value = result(kind="not_parcel")

    await engine.ai._async_step()

    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_REJECTED
    assert item.source is Source.PARSER
    assert not engine.data.filtered
    assert engine.ai.today()["rejected"] == 1


async def test_refund_answer_is_dropped_silently(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """An e-mail the AI reads as a return, but that is about a refund, is dropped.

    It goes neither to review nor to the filtered list; it's only counted.
    """
    message = shop_message(
        "An update on order #1001",
        "Your refund will follow once the item arrives at our warehouse.",
    )
    engine = await async_setup(hass, client, message)
    assert engine.ai.queue_size == 1
    generate.return_value = result(kind="return", order_numbers=["1001"])

    await engine.ai._async_step()

    generate.assert_awaited_once()
    assert engine.data.messages[message.hash].state is MessageState.NOT_PARCEL
    assert not engine.data.parcels
    assert not engine.data.review
    assert not engine.data.filtered
    assert engine.ai.queue_size == 0
    assert engine.diagnostics()["refunds_dropped"] == 1


async def test_queued_refund_is_dropped_without_the_ai(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """A refund an earlier release queued is dropped when its turn comes."""
    message = shop_message(
        "Your refund for order #1001",
        "We have issued a refund of 19.99 EUR for order #1001.",
    )
    unread = ParseResult(parser="none", kind=MailKind.UNKNOWN, confidence=0.0)
    with patch("custom_components.parcels.engine.parse_message", return_value=unread):
        engine = await async_setup(hass, client, message)
    assert engine.ai.queue_size == 1

    await engine.ai._async_step()

    generate.assert_not_awaited()
    assert engine.data.messages[message.hash].state is MessageState.NOT_PARCEL
    assert not engine.data.review
    assert not engine.data.filtered
    assert engine.ai.queue_size == 0
    assert engine.diagnostics()["refunds_dropped"] == 1


async def test_reading_a_refund_with_the_ai_drops_it_once(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """Asking the AI to read a refund again drops it, without counting it twice."""
    message = shop_message(
        "Your refund for order #1001",
        "We have issued a refund of 19.99 EUR for order #1001.",
    )
    engine = await async_setup(hass, client, message)
    record = engine.data.messages[message.hash]
    assert record.state is MessageState.NOT_PARCEL
    assert engine.diagnostics()["refunds_dropped"] == 1

    await engine.async_reprocess(message.hash, use_ai=True)

    assert engine.ai.queue_size == 0
    assert record.state is MessageState.NOT_PARCEL
    assert engine.diagnostics()["refunds_dropped"] == 1
    generate.assert_not_awaited()


async def test_shop_return_waits_under_review_without_the_ai(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """The AI doesn't read returns, not even when asked to read one again.

    An unknown shop's return waits under review with its pickup day.
    """
    message = shop_message(*SHOP_RETURN)
    engine = await async_setup(hass, client, message)
    assert engine.ai.queue_size == 0
    (first,) = engine.data.review.values()

    await engine.async_reprocess(message.hash, use_ai=True)

    generate.assert_not_awaited()
    assert engine.ai.queue_size == 0
    assert engine.data.messages[message.hash].state is MessageState.REVIEW
    (item,) = engine.data.review.values()
    assert item.id != first.id
    assert item.reason == REASON_UNKNOWN_SENDER
    assert item.suggestion is not None
    assert item.suggestion.kind is MailKind.CUSTOMER_RETURN
    assert (item.suggestion.eta_start, item.suggestion.eta_end) == (PICKUP_DAY,) * 2
    assert not engine.data.parcels
    assert not engine.data.returns


async def test_queued_return_is_decided_without_the_ai(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """A return an earlier release queued is decided by its parser's reading."""
    message = shop_message(*SHOP_RETURN)
    unread = ParseResult(parser="none", kind=MailKind.UNKNOWN, confidence=0.0)
    with patch("custom_components.parcels.engine.parse_message", return_value=unread):
        engine = await async_setup(hass, client, message)
    (entry,) = engine.ai.queue
    queued = ReviewItem.from_dict(entry["review"])

    await engine.ai._async_step()

    generate.assert_not_awaited()
    assert engine.ai.queue_size == 0
    assert engine.data.messages[message.hash].state is MessageState.REVIEW
    (item,) = engine.data.review.values()
    assert item.reason == REASON_UNKNOWN_SENDER
    assert item.source is Source.PARSER
    assert (item.mailbox, item.owner) == (queued.mailbox, queued.owner)
    assert item.suggestion is not None
    assert item.suggestion.kind is MailKind.CUSTOMER_RETURN
    assert (item.suggestion.eta_start, item.suggestion.eta_end) == (PICKUP_DAY,) * 2
    assert not engine.data.returns


async def test_return_answer_keeps_the_pickup_day(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """A return the AI reads waits under review with the e-mail's pickup day."""
    message = shop_message(
        "Atualização da encomenda #1001",
        "Devolução.\nData de recolha: Dia útil seguinte",
    )
    engine = await async_setup(hass, client, message)
    assert engine.ai.queue_size == 1
    generate.return_value = result(kind="return", order_numbers=["1001"])

    await engine.ai._async_step()

    generate.assert_awaited_once()
    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_SUGGESTION
    assert item.suggestion is not None
    assert item.suggestion.kind is MailKind.CUSTOMER_RETURN
    assert (item.suggestion.eta_start, item.suggestion.eta_end) == (PICKUP_DAY,) * 2
    assert not engine.data.returns


async def test_unknown_answer_goes_to_review(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """When the AI can't tell either, the e-mail goes to review as unknown."""
    engine = await async_setup(hass, client, ctt_message())
    generate.return_value = result(kind="unknown")

    await engine.ai._async_step()

    (item,) = engine.data.review.values()
    assert item.reason == REASON_UNKNOWN_FORMAT
    assert engine.ai.today()["calls"] == 1


@pytest.mark.parametrize("mode", ["suggest", "auto"])
async def test_answer_failing_checks_is_offered_as_rejected(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock, mode: str
) -> None:
    """An answer that fails a check goes to review, with the values that passed."""
    engine = await async_setup(hass, client, ctt_message(), mode=mode)
    # A valid S10 number that isn't in the e-mail.
    generate.return_value = result(
        kind="in_transit", tracking_numbers=["RR123456785PT"]
    )

    await engine.ai._async_step()

    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_REJECTED
    assert item.source is Source.AI
    assert item.suggestion is not None
    assert item.suggestion.kind is MailKind.IN_TRANSIT
    assert "RR123456785PT" not in item.suggestion.tracking_numbers
    assert not engine.data.parcels
    assert engine.ai.today()["rejected"] == 1
    assert engine.ai.today()["suggested"] == 0


async def test_unusable_answer_is_rejected(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """An answer that isn't a mapping counts as a call and goes to review."""
    engine = await async_setup(hass, client, ctt_message())
    generate.return_value = result(data="not JSON")

    await engine.ai._async_step()

    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_REJECTED
    assert item.source is Source.PARSER
    assert engine.ai.today()["calls"] == 1
    assert engine.ai.today()["rejected"] == 1
    assert engine.ai.diagnostics()["last_error"] == "bad_output"


async def test_email_dropped_during_the_call_is_left_alone(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """An e-mail dismissed while the AI reads it isn't put back."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    statuses: list[str] = []

    async def dismiss(*args: Any, **kwargs: Any) -> FakeResult:
        statuses.append(engine.ai.status)
        engine.ai.drop(message.hash)
        return result(kind="shipped")

    generate.side_effect = dismiss

    await engine.ai._async_step()

    assert statuses == [STATUS_BUSY]
    assert not engine.data.review
    assert engine.ai.queue_size == 0
    assert engine.ai.today()["calls"] == 1
    assert engine.ai.today()["suggested"] == 0


# -- Failures and limits ------------------------------------------------------


async def test_refused_ai_task_pauses_the_queue(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """An AI task that may not read e-mail raises a repair and pauses the queue."""
    engine = await async_setup(hass, client, ctt_message(), model=CLOUD_MODEL)

    await engine.ai._async_step()

    generate.assert_not_awaited()
    refused = issue(hass, ISSUE_AI_REFUSED)
    assert refused is not None
    assert refused.translation_placeholders == {"reason": "cloud_model"}
    assert engine.data.ai["paused_until"] == IN_30_MINUTES
    assert engine.ai.status == STATUS_PAUSED
    assert engine.ai.queue_size == 1
    assert engine.ai.today()["calls"] == 0
    assert engine.ai.diagnostics()["last_error"] == "refused:cloud_model"
    assert await engine.ai._async_step() == 1800


async def test_unavailable_ai_task_pauses_without_a_call(
    hass: HomeAssistant,
    client: FakeMailClient,
    generate: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """While the AI task is unavailable the queue pauses; nothing is counted."""
    engine = await async_setup(hass, client, ctt_message())
    entity_id = engine.ai_entity
    assert entity_id is not None
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)

    await engine.ai._async_step()

    generate.assert_not_awaited()
    assert issue(hass, ISSUE_AI_UNAVAILABLE) is not None
    assert engine.ai.status == STATUS_PAUSED
    (entry,) = engine.ai.queue
    assert entry["attempts"] == 0
    assert engine.ai.today()["calls"] == 0

    hass.states.async_set(entity_id, "2026-11-17T10:20:00+00:00")
    generate.return_value = result(kind="shipped")
    freezer.tick(timedelta(minutes=30))

    await engine.ai._async_step()

    assert issue(hass, ISSUE_AI_UNAVAILABLE) is None
    assert "paused_until" not in engine.data.ai
    assert engine.ai.queue_size == 0
    assert engine.ai.today()["suggested"] == 1


async def test_failed_call_is_retried_once(
    hass: HomeAssistant,
    client: FakeMailClient,
    generate: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A call that fails is tried again after 30 minutes, then goes to review."""
    engine = await async_setup(hass, client, ctt_message())
    generate.side_effect = RuntimeError(SECRET)

    await engine.ai._async_step()

    (entry,) = engine.ai.queue
    assert entry["attempts"] == 1
    assert entry["not_before"] == IN_30_MINUTES
    assert engine.ai.status == STATUS_PAUSED
    assert engine.ai.diagnostics()["queue_retrying"] == 1
    assert engine.ai.today()["calls"] == 1
    assert engine.ai.today()["failed"] == 1
    assert await engine.ai._async_step() == 1800

    freezer.tick(timedelta(minutes=30))
    await engine.ai._async_step()

    assert engine.ai.queue_size == 0
    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_UNAVAILABLE
    assert engine.ai.today()["calls"] == 2
    assert engine.ai.today()["failed"] == 2


async def test_timed_out_call_is_retried_without_a_pause(
    hass: HomeAssistant,
    client: FakeMailClient,
    generate: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A call that takes too long is tried again later; the queue keeps going.

    When the last try takes too long as well, the review item says so: the
    AI was there, but too slow for this e-mail.
    """
    engine = await async_setup(hass, client, ctt_message())
    generate.side_effect = TimeoutError

    await engine.ai._async_step()

    (entry,) = engine.ai.queue
    assert entry["attempts"] == 1
    assert entry["not_before"] == IN_30_MINUTES
    assert engine.ai.status == STATUS_IDLE
    assert issue(hass, ISSUE_AI_UNAVAILABLE) is None
    assert engine.ai.diagnostics()["last_error"] == "AITimeout"
    # Nothing is due before the retry.
    assert await engine.ai._async_step() == 1800

    freezer.tick(timedelta(minutes=30))
    await engine.ai._async_step()

    assert engine.ai.queue_size == 0
    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_TIMEOUT
    assert engine.ai.today()["failed"] == 2


async def test_daily_limit_stops_the_calls_until_midnight(
    hass: HomeAssistant,
    client: FakeMailClient,
    generate: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After the daily limit nothing is sent until the next day."""
    engine = await async_setup(hass, client, ctt_message())
    engine.ai.today()["calls"] = AI_DAILY_LIMIT
    assert engine.ai.status == STATUS_LIMIT

    assert await engine.ai._async_step() == 3600

    generate.assert_not_awaited()
    assert engine.ai.queue_size == 1

    freezer.move_to("2026-11-18 00:01:00+00:00")
    generate.return_value = result(kind="shipped")
    await engine.ai._async_step()

    generate.assert_awaited_once()
    assert engine.ai.today()["calls"] == 1
    assert set(engine.data.ai["stats"]) == {"2026-11-17", "2026-11-18"}


async def test_waiting_too_long_sends_the_email_to_review(
    hass: HomeAssistant,
    client: FakeMailClient,
    generate: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An e-mail still queued after a day goes to review."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    freezer.tick(timedelta(days=1, minutes=1))

    assert await engine.ai._async_step() == 3600

    generate.assert_not_awaited()
    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_UNAVAILABLE
    assert engine.data.messages[message.hash].state is MessageState.REVIEW


async def test_turning_the_ai_off_releases_the_queue(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """With the AI off, queued e-mails go to review as the parser left them."""
    engine = await async_setup(hass, client, ctt_message())
    entity_id = engine.ai_entity
    assert entity_id is not None
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await engine.ai._async_step()
    assert issue(hass, ISSUE_AI_UNAVAILABLE) is not None
    (entry,) = engine.ai.queue
    reason = entry["review"]["reason"]

    hass.config_entries.async_update_entry(
        engine.entry, options={**engine.entry.options, CONF_AI_MODE: "off"}
    )
    await hass.async_block_till_done()
    assert engine.ai.status == STATUS_OFF

    assert await engine.ai._async_step() == 3600

    generate.assert_not_awaited()
    (item,) = engine.data.review.values()
    assert item.reason == reason
    assert item.source is Source.PARSER
    assert engine.ai.queue_size == 0
    assert issue(hass, ISSUE_AI_UNAVAILABLE) is None


# -- Queue order and downloads ------------------------------------------------


async def test_newest_email_goes_first(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """The queue sends the most recently received e-mail first."""
    older = ctt_message(number=1, received=RECEIVED - timedelta(hours=2))
    newer = ctt_message(number=2)
    engine = await async_setup(hass, client, older, newer)
    assert engine.ai.queue_size == 2
    generate.return_value = result(kind="shipped")

    await engine.ai._async_step()

    assert engine.data.messages[newer.hash].state is MessageState.REVIEW
    assert engine.data.messages[older.hash].state is MessageState.QUEUED


async def test_email_without_mailboxes_is_ignored(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """An e-mail whose mailboxes were all removed leaves the queue."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    record = engine.data.messages[message.hash]
    record.refs.clear()

    assert await engine.ai._async_step() == 3600

    generate.assert_not_awaited()
    assert engine.ai.queue_size == 0
    assert record.state is MessageState.IGNORED


async def test_email_handled_elsewhere_leaves_the_queue(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """An e-mail that is no longer queued is dropped from the queue."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    record = engine.data.messages[message.hash]
    record.state = MessageState.DISMISSED

    assert await engine.ai._async_step() == 3600

    generate.assert_not_awaited()
    assert engine.ai.queue_size == 0
    assert record.state is MessageState.DISMISSED


async def test_email_of_an_unloaded_mailbox_waits(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """An e-mail waits while none of its mailboxes is loaded."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    record = engine.data.messages[message.hash]
    record.refs = {"unloaded_entry": message.provider_id}

    assert await engine.ai._async_step() == 3600

    generate.assert_not_awaited()
    assert engine.ai.queue_size == 1
    assert record.state is MessageState.QUEUED


async def test_deleted_email_leaves_the_queue(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """An e-mail deleted from the mailbox is dropped and ignored."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    client.delete(message.provider_id)

    assert await engine.ai._async_step() == 0

    generate.assert_not_awaited()
    assert engine.ai.queue_size == 0
    assert engine.data.messages[message.hash].state is MessageState.IGNORED


async def test_download_error_retries_later(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """A failed download is tried again after 30 minutes, without a call."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    client.fetch_errors[message.provider_id] = MailError("server busy")

    await engine.ai._async_step()

    generate.assert_not_awaited()
    (entry,) = engine.ai.queue
    assert entry["not_before"] == IN_30_MINUTES
    assert entry["attempts"] == 0
    assert await engine.ai._async_step() == 1800


async def test_email_a_parser_now_reads_skips_the_ai(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """A queued e-mail that a parser now reads with confidence is applied."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    # The download now returns a body the CTT parser reads.
    client.add(dataclasses.replace(ctt_message(text=None), subject=message.subject))

    await engine.ai._async_step()

    generate.assert_not_awaited()
    assert engine.ai.queue_size == 0
    assert engine.data.messages[message.hash].state is MessageState.APPLIED
    (parcel,) = engine.data.parcels.values()
    assert [o.source for o in parcel.origins.values()] == [Source.PARSER]


async def test_reprocess_with_the_ai_reads_a_parsed_email(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """Reprocessing with the AI sends an e-mail even when a parser reads it."""
    message = ctt_message(text=None)
    engine = await async_setup(hass, client, message)
    assert engine.data.messages[message.hash].state is MessageState.APPLIED

    await engine.async_reprocess(message.hash, use_ai=True)

    (entry,) = engine.ai.queue
    assert entry["forced"] is True
    assert engine.ai.diagnostics()["queue_forced"] == 1
    generate.return_value = result(kind="in_transit", tracking_numbers=[TRACKING])

    await engine.ai._async_step()

    generate.assert_awaited_once()
    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_SUGGESTION
    assert item.suggestion is not None
    assert item.suggestion.kind is MailKind.IN_TRANSIT


async def test_ignoring_a_sender_drops_its_emails(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """Ignoring a sender empties its queued e-mails and shadow candidates."""
    queued = ctt_message(number=1)
    parsed = ctt_message(text=None, number=2)
    engine = await async_setup(hass, client, queued, parsed)
    assert engine.ai.queue_size == 1
    assert engine.data.ai["shadow"] == [parsed.hash]

    assert engine.ignore_domain("notificacoes.ctt.pt") == "ctt.pt"

    assert engine.ai.queue_size == 0
    assert engine.data.ai["shadow"] == []
    assert engine.data.messages[queued.hash].state is MessageState.IGNORED
    assert await engine.ai._async_step() == 3600
    generate.assert_not_awaited()


# -- Shadow check -------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "counter"),
    [
        (
            answer(
                kind="in_transit",
                tracking_numbers=[TRACKING],
                eta_start="19/11/2026",
                eta_end="19/11/2026",
            ),
            "agree",
        ),
        (answer(kind="not_parcel"), "disagree"),
        ("not JSON", "disagree"),
    ],
)
async def test_shadow_check_compares_with_the_parser(
    hass: HomeAssistant,
    client: FakeMailClient,
    generate: AsyncMock,
    data: Any,
    counter: str,
) -> None:
    """In suggest mode the AI also reads parsed e-mails; only agreement is kept."""
    message = ctt_message(text=None)
    engine = await async_setup(hass, client, message)
    assert engine.data.ai["shadow"] == [message.hash]
    generate.return_value = result(data=data)

    assert await engine.ai._async_step() == 0

    generate.assert_awaited_once()
    today = engine.ai.today()
    assert today[counter] == 1
    assert today["agree"] + today["disagree"] == 1
    assert today["shadow"] == 1
    assert today["calls"] == 1
    assert engine.data.ai["shadow"] == []
    assert engine.data.messages[message.hash].state is MessageState.APPLIED
    assert not engine.data.review
    (parcel,) = engine.data.parcels.values()
    assert [o.source for o in parcel.origins.values()] == [Source.PARSER]
    assert engine.ai.diagnostics()["agreement_rate"] == (
        1.0 if counter == "agree" else 0.0
    )


@pytest.mark.parametrize(
    ("model", "state", "repair"),
    [
        (CLOUD_MODEL, "2026-11-17T09:00:00+00:00", ISSUE_AI_REFUSED),
        (LOCAL_MODEL, STATE_UNAVAILABLE, ISSUE_AI_UNAVAILABLE),
    ],
)
async def test_shadow_check_pauses_when_the_ai_task_cant_be_used(
    hass: HomeAssistant,
    client: FakeMailClient,
    generate: AsyncMock,
    model: str,
    state: str,
    repair: str,
) -> None:
    """A refused or unavailable AI task pauses the shadow check too."""
    engine = await async_setup(hass, client, ctt_message(text=None), model=model)
    entity_id = engine.ai_entity
    assert entity_id is not None
    hass.states.async_set(entity_id, state)

    await engine.ai._async_step()

    generate.assert_not_awaited()
    assert issue(hass, repair) is not None
    assert engine.ai.status == STATUS_PAUSED
    assert engine.ai.today()["shadow"] == 0


async def test_shadow_check_timeout_counts_no_result(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """A shadow call that times out counts as a call, not as a disagreement."""
    engine = await async_setup(hass, client, ctt_message(text=None))
    generate.side_effect = TimeoutError

    await engine.ai._async_step()

    today = engine.ai.today()
    assert today["shadow"] == 1
    assert today["agree"] == today["disagree"] == 0
    assert engine.ai.diagnostics()["last_error"] == "AITimeout"
    assert engine.ai.status == STATUS_IDLE


async def test_shadow_check_skips_emails_it_cant_compare(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """Deleted e-mails and e-mails that are no longer applied aren't compared."""
    deleted = ctt_message(text=None, number=1)
    dismissed = ctt_message(text=None, number=2)
    engine = await async_setup(hass, client, deleted, dismissed)
    assert engine.data.ai["shadow"] == [deleted.hash, dismissed.hash]
    client.delete(deleted.provider_id)
    engine.data.messages[dismissed.hash].state = MessageState.DISMISSED

    assert await engine.ai._async_step() == 0
    assert await engine.ai._async_step() == 0
    assert await engine.ai._async_step() == 3600

    generate.assert_not_awaited()
    assert engine.data.ai["shadow"] == []
    assert engine.ai.today()["shadow"] == 0


async def test_shadow_check_daily_limit(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """After the daily shadow limit the candidates wait for the next day."""
    message = ctt_message(text=None)
    engine = await async_setup(hass, client, message)
    engine.ai.today()["shadow"] = AI_SHADOW_DAILY_LIMIT

    assert await engine.ai._async_step() == 3600

    generate.assert_not_awaited()
    assert engine.data.ai["shadow"] == [message.hash]


async def test_shadow_candidates_only_in_suggest_mode(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """In auto mode parsed e-mails aren't offered for the shadow check."""
    engine = await async_setup(hass, client, ctt_message(text=None), mode="auto")

    assert not engine.data.ai.get("shadow")
    assert await engine.ai._async_step() == 3600
    generate.assert_not_awaited()


async def test_shadow_candidates_keep_the_latest_twenty(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """The shadow check keeps the 20 most recent candidates, without repeats."""
    engine = await async_setup(hass, client)

    for number in range(25):
        engine.ai.add_shadow_candidate(f"hash{number}")
    engine.ai.add_shadow_candidate("hash10")

    shadow = engine.data.ai["shadow"]
    assert len(shadow) == 20
    assert shadow[0] == "hash5"
    assert shadow[-1] == "hash10"
    assert shadow.count("hash10") == 1


# -- Filling in gaps ----------------------------------------------------------

# The CTT parser reads this e-mail, but not its date, which the AI may find.
NO_DATE = (
    "O seu objeto RR482915732PT, enviado por Exemplo Loja, já está em trânsito "
    "na rede CTT.\nN.º do objeto RR482915732PT\nEstado Em trânsito\n"
    "Será entregue, previsivelmente, a 20 do corrente mês."
)
FILLED = date(2026, 11, 20)


def dated(**values: Any) -> FakeResult:
    """Return the AI's answer for the e-mail without a date, with its date."""
    return result(
        kind="in_transit",
        tracking_numbers=[TRACKING],
        eta_start="2026-11-20",
        **values,
    )


async def test_fill_suggests_what_the_parser_missed(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """In suggest mode the date the AI found waits under review; Accept adds it."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.eta is None
    assert engine.data.messages[message.hash].state is MessageState.APPLIED
    assert engine.ai.queue_size == 1
    assert not engine.data.ai.get("shadow")
    generate.return_value = dated()

    await engine.ai._async_step()

    (item,) = engine.data.review.values()
    assert item.reason == REASON_AI_FILL
    assert item.fill
    assert item.source is Source.AI
    assert item.suggestion is not None
    assert item.suggestion.eta_start == FILLED
    assert item.suggestion.tracking_numbers == ()
    assert engine.data.messages[message.hash].state is MessageState.APPLIED
    assert engine.data.parcels[parcel.id].state.eta is None
    assert engine.ai.queue_size == 0
    today = engine.ai.today()
    assert today["fills"] == today["filled"] == today["calls"] == 1

    engine.review_accept(item.id)

    parcel = engine.data.parcels[parcel.id]
    eta = parcel.state.eta
    assert eta is not None
    assert eta.start == FILLED
    assert not parcel.state.ai_filled
    assert parcel.origins[fill_origin_id(message.hash)].confirmed
    assert not engine.data.review
    assert engine.data.messages[message.hash].state is MessageState.APPLIED


async def test_fill_is_added_in_auto_mode(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """In auto mode the date is added at once, marked as the AI's."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message, mode="auto")
    generate.return_value = dated()

    await engine.ai._async_step()

    assert not engine.data.review
    (parcel,) = engine.data.parcels.values()
    state = parcel.state
    assert state.eta is not None
    assert state.eta.start == FILLED
    assert state.status is ParcelStatus.IN_TRANSIT
    assert state.ai_filled
    assert not state.ai
    assert parcel.origins[message_origin_id(message.hash, 0)].source is Source.PARSER
    assert engine.ai.today()["filled"] == 1
    assert engine.data.messages[message.hash].state is MessageState.APPLIED


async def test_dismissing_a_fill_keeps_the_email(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """Dismissing what the AI found leaves the parsed e-mail as it was."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    generate.return_value = dated()
    await engine.ai._async_step()
    (item,) = engine.data.review.values()

    engine.review_dismiss(item.id)

    assert not engine.data.review
    assert engine.data.messages[message.hash].state is MessageState.APPLIED
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.eta is None


async def test_trusting_the_sender_keeps_a_fill(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """Trusting a sender doesn't read again an e-mail it already added."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    generate.return_value = dated()
    await engine.ai._async_step()
    (item,) = engine.data.review.values()

    engine.trust_domain(message.sender_domain)
    result = engine.review_trust_sender(item.id)
    await hass.async_block_till_done()

    assert list(engine.data.review.values()) == [item]
    assert result["rechecking"] == result["added"] == result["kept"] == 0
    assert engine.ai.queue_size == 0
    assert engine.data.messages[message.hash].state is MessageState.APPLIED


async def test_ignoring_the_sender_drops_a_fill(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """Ignoring a sender drops what the AI found, not the parcel it added."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    generate.return_value = dated()
    await engine.ai._async_step()

    engine.ignore_domain(message.sender_domain)

    assert not engine.data.review
    assert engine.data.messages[message.hash].state is MessageState.APPLIED
    assert len(engine.data.parcels) == 1


@pytest.mark.parametrize(
    "data",
    [
        "not JSON",
        answer(kind="not_parcel"),
        answer(kind="in_transit", tracking_numbers=[TRACKING]),
    ],
)
async def test_fill_without_an_answer_is_dropped(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock, data: Any
) -> None:
    """An answer that fills nothing leaves the parsed e-mail as it was."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    generate.return_value = result(data=data)

    await engine.ai._async_step()

    assert not engine.data.review
    assert engine.ai.queue_size == 0
    assert engine.ai.today()["filled"] == 0
    assert engine.data.messages[message.hash].state is MessageState.APPLIED


async def test_failed_fill_is_dropped_after_the_retry(
    hass: HomeAssistant,
    client: FakeMailClient,
    generate: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A fill that fails twice is dropped without a review item."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    generate.side_effect = RuntimeError(SECRET)

    await engine.ai._async_step()
    (entry,) = engine.ai.queue
    assert entry["attempts"] == 1
    freezer.tick(timedelta(minutes=30))
    await engine.ai._async_step()

    assert engine.ai.today()["fills"] == 2
    assert engine.ai.queue_size == 0
    assert not engine.data.review
    assert engine.data.messages[message.hash].state is MessageState.APPLIED


async def test_fill_waits_for_unread_emails(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """E-mails no parser read go first, even when older."""
    unread = ctt_message(number=1, received=RECEIVED - timedelta(hours=1))
    engine = await async_setup(hass, client, unread, ctt_message(NO_DATE, number=2))
    assert engine.ai.queue_size == 2
    generate.return_value = result(kind="not_parcel")

    await engine.ai._async_step()

    (entry,) = engine.ai.queue
    assert entry["fill"]
    assert engine.ai.today()["fills"] == 0


async def test_fill_daily_limit(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """After the daily fill limit, fills wait for the next day."""
    engine = await async_setup(hass, client, ctt_message(NO_DATE))
    engine.ai.today()["fills"] = AI_FILL_DAILY_LIMIT

    assert await engine.ai._async_step() == 3600

    generate.assert_not_awaited()
    assert engine.ai.queue_size == 1


async def test_turning_the_ai_off_drops_fills(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """With the AI off, queued fills go away without a review item."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    assert engine.ai.queue_size == 1

    hass.config_entries.async_update_entry(
        engine.entry, options={**engine.entry.options, CONF_AI_MODE: "off"}
    )
    await hass.async_block_till_done()
    await engine.ai._async_step()

    generate.assert_not_awaited()
    assert engine.ai.queue_size == 0
    assert not engine.data.review
    assert engine.data.messages[message.hash].state is MessageState.APPLIED


# -- Check again --------------------------------------------------------------

PARSED_DATE = (
    "O seu objeto RR482915732PT está em trânsito.\nEntrega prevista: 20-11-2026"
)


async def test_check_again_asks_the_ai_and_keeps_the_parcel(
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """Check again reads the e-mails again and asks the AI, past the daily
    fill limit; the parcel stays on the page meanwhile."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    (parcel,) = engine.data.parcels.values()
    engine.ai.drop(message.hash)
    engine.ai.today()["fills"] = AI_FILL_DAILY_LIMIT

    result = await engine.async_check_again(parcel.id)

    assert result == {"read": 1, "queued": 1, "gone": 0, "failed": 0}
    assert list(engine.data.parcels) == [parcel.id]
    (entry,) = engine.ai.queue
    assert entry["fill"]
    assert entry["forced"]
    generate.return_value = dated()

    await engine.ai._async_step()

    (item,) = engine.data.review.values()
    assert item.fill
    assert item.suggestion is not None
    assert item.suggestion.eta_start == FILLED
    assert engine.data.parcels[parcel.id].state.eta is None


async def test_check_again_takes_what_the_parser_now_reads(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """A date the parser now reads updates the same parcel."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    (parcel,) = engine.data.parcels.values()
    client.add(ctt_message(PARSED_DATE))

    result = await engine.async_check_again(parcel.id)

    assert result == {"read": 1, "queued": 0, "gone": 0, "failed": 0}
    assert list(engine.data.parcels) == [parcel.id]
    eta = engine.data.parcels[parcel.id].state.eta
    assert eta is not None
    assert eta.start == FILLED


async def test_check_again_keeps_what_the_user_confirmed(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """An e-mail accepted under review isn't read again over the user's choices."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    (parcel,) = engine.data.parcels.values()
    anchor = message_origin_id(message.hash, 0)
    parcel.origins[anchor] = dataclasses.replace(parcel.origins[anchor], confirmed=True)
    client.add(ctt_message(PARSED_DATE))

    result = await engine.async_check_again(parcel.id)

    assert result["read"] == 1
    assert engine.data.parcels[parcel.id].origins[anchor].confirmed
    assert engine.data.parcels[parcel.id].state.eta is None


@pytest.mark.parametrize("deleted", [True, False])
async def test_check_again_counts_emails_it_cant_download(
    hass: HomeAssistant, client: FakeMailClient, deleted: bool
) -> None:
    """E-mails deleted from the mailbox, or not downloaded, are counted."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    (parcel,) = engine.data.parcels.values()
    if deleted:
        client.delete(message.provider_id)
    else:
        client.fetch_errors[message.provider_id] = MailError("offline")

    result = await engine.async_check_again(parcel.id)

    assert result == {
        "read": 0,
        "queued": 0,
        "gone": int(deleted),
        "failed": int(not deleted),
    }
    assert list(engine.data.parcels) == [parcel.id]


async def test_check_again_unknown_parcel(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """A parcel that doesn't exist is a translated error."""
    engine = await async_setup(hass, client)

    with pytest.raises(ServiceValidationError):
        await engine.async_check_again("p_missing")


async def async_sync_again(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """Read the mailbox again and wait for what runs after it."""
    (mailbox,) = engine.mailboxes.values()
    assert mailbox.coordinator is not None
    await mailbox.coordinator.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_update_checks_open_parcels_once(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """After the update, the first mailbox sync checks open parcels without a
    date once, within the daily fill limit."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    # As an earlier release left it: nothing asked of the AI, nothing checked.
    engine.ai.drop(message.hash)
    del engine.data.engine[FILL_CHECK_KEY]

    await async_sync_again(hass, engine)

    (entry,) = engine.ai.queue
    assert entry["fill"]
    assert not entry["forced"]
    assert engine.data.engine[FILL_CHECK_KEY]
    engine.ai.drop(message.hash)

    await async_sync_again(hass, engine)

    assert not engine.ai.queue


async def test_update_check_waits_for_a_sync_that_works(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """While the mailbox can't be read, the check waits for the next sync."""
    message = ctt_message(NO_DATE)
    engine = await async_setup(hass, client, message)
    engine.ai.drop(message.hash)
    del engine.data.engine[FILL_CHECK_KEY]
    client.sync_error = MailError("offline")

    await async_sync_again(hass, engine)

    assert FILL_CHECK_KEY not in engine.data.engine
    assert not engine.ai.queue
    client.sync_error = None

    await async_sync_again(hass, engine)

    assert engine.data.engine[FILL_CHECK_KEY]
    (entry,) = engine.ai.queue
    assert entry["fill"]


async def test_update_reads_refused_emails_again(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """E-mails an earlier release refused for their mail server are read once
    more after the update."""
    refused = SenderVerdict(
        domain="ctt.pt", authenticated=False, known=True, reason="untrusted_authserv"
    )
    with patch("custom_components.parcels.engine.verify_sender", return_value=refused):
        engine = await async_setup(hass, client, ctt_message(None))
    (item,) = engine.data.review.values()
    assert item.reason == "untrusted_authserv"
    del engine.data.engine[FILL_CHECK_KEY]

    await async_sync_again(hass, engine)

    assert not engine.data.review
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.tracking_number == TRACKING


async def test_new_install_has_nothing_to_check(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """A new install reads its e-mails once, without checking them again."""
    with patch.object(ParcelsEngine, "async_check_again") as check:
        engine = await async_setup(hass, client, ctt_message(NO_DATE))
        await hass.async_block_till_done(wait_background_tasks=True)

    check.assert_not_called()
    assert engine.data.engine[FILL_CHECK_KEY]


PAACK = "carriers/paack_on_the_way_pt.eml"
# The order ID in the Paack fixture.
PAACK_ID = "Wx4Hn8Tz3_1"


def paack_message(n: int = 1) -> MailMessage:
    """Return a Paack e-mail with its own Message-ID, received before NOW."""
    return dataclasses.replace(
        load_message(PAACK),
        message_id=f"<paack-{n}@mail.example.com>",
        provider_id=f"paack-{n}",
        date=RECEIVED,
        received=RECEIVED,
    )


async def async_rejected(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    message: MailMessage,
    *,
    reason: str = REASON_AI_REJECTED,
    carrier: str | None = "paack",
    checked: bool = False,
) -> ReviewItem:
    """Put an e-mail under review as an earlier release left it.

    Earlier releases couldn't read Paack's order IDs, so they failed the
    checks of the AI's reading, and the e-mail waited under review. Unless
    ``checked``, the check after the update hasn't run yet.
    """
    await hass.async_block_till_done(wait_background_tasks=True)
    now = dt_util.utcnow()
    engine._clear_outputs(message.hash, now)
    record = engine.data.messages[message.hash]
    (mailbox,) = engine.mailboxes.values()
    item = engine.review_item(
        message,
        record,
        engine.verify(message),
        reason=reason,
        source=Source.AI,
        suggestion=Suggestion(kind=MailKind.IN_TRANSIT, carrier=carrier),
        mailbox=mailbox.entry_id,
        owner=None,
        now=now,
    )
    engine.add_review(item, record)
    if not checked:
        engine.data.engine.pop(PAACK_CHECK_KEY, None)
    return item


@pytest.mark.parametrize("carrier", ["paack", None])
async def test_update_reads_rejected_paack_emails_again(
    hass: HomeAssistant, client: FakeMailClient, carrier: str | None
) -> None:
    """After the update, Paack's e-mails whose AI reading was rejected are read
    once more, and what the parsers read now stays away from the AI."""
    message = paack_message()
    engine = await async_setup(hass, client, message)
    await async_rejected(hass, engine, message, carrier=carrier)

    await async_sync_again(hass, engine)

    assert not engine.data.review
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.tracking_number == PAACK_ID
    assert parcel.state.carrier == "paack"
    assert engine.data.messages[message.hash].state is MessageState.APPLIED
    assert not engine.ai.queue
    assert not engine.data.ai.get("shadow")
    assert engine.data.engine[PAACK_CHECK_KEY]

    # Once only: an e-mail rejected again later stays under review.
    item = await async_rejected(hass, engine, message, carrier=carrier, checked=True)

    await async_sync_again(hass, engine)

    assert list(engine.data.review.values()) == [item]
    assert not engine.data.parcels


async def test_paack_check_waits_for_a_sync_that_works(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """While the mailbox can't be read, the check waits for the next sync."""
    message = paack_message()
    engine = await async_setup(hass, client, message)
    item = await async_rejected(hass, engine, message)
    client.sync_error = MailError("offline")

    await async_sync_again(hass, engine)

    assert PAACK_CHECK_KEY not in engine.data.engine
    assert list(engine.data.review.values()) == [item]
    client.sync_error = None

    await async_sync_again(hass, engine)

    assert engine.data.engine[PAACK_CHECK_KEY]
    assert not engine.data.review
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.tracking_number == PAACK_ID


@pytest.mark.parametrize(("carrier", "read"), [("paack", True), ("ctt", False)])
async def test_paack_check_reads_only_paack_emails(
    hass: HomeAssistant, client: FakeMailClient, carrier: str, read: bool
) -> None:
    """Other carriers' e-mails aren't read again, and one offered as Paack's
    that the parsers still can't read stays under review as it was."""
    message = ctt_message()
    engine = await async_setup(hass, client, message)
    item = await async_rejected(hass, engine, message, carrier=carrier)
    client.fetches.clear()

    await async_sync_again(hass, engine)

    assert (message.provider_id in client.fetches) is read
    assert list(engine.data.review.values()) == [item]
    assert engine.data.messages[message.hash].state is MessageState.REVIEW
    assert not engine.ai.queue
    assert engine.data.engine[PAACK_CHECK_KEY]


async def test_paack_check_leaves_other_reviews(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """A Paack e-mail under review for another reason stays as it is."""
    message = paack_message()
    engine = await async_setup(hass, client, message)
    item = await async_rejected(hass, engine, message, reason=REASON_AI_SUGGESTION)
    client.fetches.clear()

    await async_sync_again(hass, engine)

    assert message.provider_id not in client.fetches
    assert list(engine.data.review.values()) == [item]
    assert engine.data.engine[PAACK_CHECK_KEY]


@pytest.mark.parametrize("deleted", [True, False])
async def test_paack_check_keeps_emails_it_cant_download(
    hass: HomeAssistant, client: FakeMailClient, deleted: bool
) -> None:
    """A Paack e-mail that's gone or can't be downloaded stays under review,
    and the check goes on with the next one."""
    missing, other = paack_message(1), paack_message(2)
    engine = await async_setup(hass, client, missing, other)
    item = await async_rejected(hass, engine, missing)
    await async_rejected(hass, engine, other)
    if deleted:
        client.delete(missing.provider_id)
    else:
        client.fetch_errors[missing.provider_id] = MailError("offline")

    await async_sync_again(hass, engine)

    assert list(engine.data.review.values()) == [item]
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.tracking_number == PAACK_ID
    assert engine.data.engine[PAACK_CHECK_KEY]


async def test_paack_check_leaves_what_the_user_settled(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """An e-mail the user dismisses while the check reads it stays dismissed."""
    message = paack_message()
    engine = await async_setup(hass, client, message)
    item = await async_rejected(hass, engine, message)
    parse = engine.async_parse

    async def dismiss_meanwhile(*args: Any) -> Any:
        engine.review_dismiss(item.id)
        return await parse(*args)

    with patch.object(engine, "async_parse", dismiss_meanwhile):
        await async_sync_again(hass, engine)

    assert not engine.data.review
    assert not engine.data.parcels
    assert engine.data.messages[message.hash].state is MessageState.DISMISSED


async def test_paack_check_runs_after_the_fill_check(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """Updating from before both checks: the parcel the Paack check reads
    isn't sent to the local AI by the fill check."""
    message = paack_message()
    window = "Será entregue em 25 de novembro entre as 09:00 e as 13:00."
    assert window in message.text
    message = dataclasses.replace(message, text=message.text.replace(window, ""))
    engine = await async_setup(hass, client, message)
    await async_rejected(hass, engine, message)
    del engine.data.engine[FILL_CHECK_KEY]

    await async_sync_again(hass, engine)

    (parcel,) = engine.data.parcels.values()
    assert parcel.state.tracking_number == PAACK_ID
    assert parcel.state.eta is None
    assert not engine.ai.queue
    assert engine.data.engine[FILL_CHECK_KEY]
    assert engine.data.engine[PAACK_CHECK_KEY]


# -- Diagnostics and counters -------------------------------------------------


async def test_diagnostics_report_timing_and_totals(
    hass: HomeAssistant,
    client: FakeMailClient,
    generate: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Diagnostics give the average call time and the totals, without e-mails."""
    engine = await async_setup(hass, client, ctt_message())

    async def slow(*args: Any, **kwargs: Any) -> FakeResult:
        freezer.tick(7)
        return result(kind="shipped")

    generate.side_effect = slow

    await engine.ai._async_step()

    diagnostics = engine.ai.diagnostics()
    assert diagnostics["average_seconds"] == 7.0
    assert diagnostics["totals"]["calls"] == 1
    assert diagnostics["totals"]["suggested"] == 1
    assert diagnostics["configured"] is True
    assert diagnostics["mode"] == "suggest"
    assert diagnostics["status"] == STATUS_IDLE
    assert diagnostics["queue"] == 0
    assert diagnostics["agreement_rate"] is None
    assert diagnostics["last_error"] is None
    assert SECRET not in str(diagnostics)
    assert "Consulte" not in str(diagnostics)


async def test_counters_keep_two_weeks(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """Counters older than 14 days are dropped and left out of the totals."""
    engine = await async_setup(hass, client)
    engine.data.ai["stats"] = {
        "2026-11-02": {"calls": 3, "agree": 3},
        "2026-11-03": {"calls": 4, "agree": 1, "disagree": 1},
    }
    engine.data.ai["timing"] = {
        "2026-11-02": {"calls": 3, "seconds": 90.0},
        "2026-11-03": {"calls": 4, "seconds": 20.0},
    }

    diagnostics = engine.ai.diagnostics()

    assert diagnostics["totals"]["calls"] == 4
    assert diagnostics["shadow_agree"] == 1
    assert diagnostics["shadow_disagree"] == 1
    assert diagnostics["agreement_rate"] == 0.5
    assert diagnostics["average_seconds"] == 5.0
    engine.ai.today()
    assert set(engine.data.ai["stats"]) == {"2026-11-03", "2026-11-17"}


async def test_page_shows_the_wait_for_the_ai(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """Administrators see how many e-mails wait for the AI, and about how long."""
    engine = await async_setup(
        hass, client, *(ctt_message(number=number) for number in (1, 2, 3))
    )
    assert engine.ai.queue_size == 3
    # No call has been timed yet.
    settings = settings_json(engine, SYSTEM_VIEWER)
    assert (settings["ai_queue"], settings["ai_queue_seconds"]) == (3, None)

    engine.data.ai["timing"] = {"2026-11-17": {"calls": 2, "seconds": 106.0}}
    settings = settings_json(engine, SYSTEM_VIEWER)
    assert (settings["ai_queue"], settings["ai_queue_seconds"]) == (3, 159)
    # The others don't see the review lists, so they don't see the queue either.
    settings = settings_json(engine, Viewer(is_admin=False))
    assert (settings["ai_queue"], settings["ai_queue_seconds"]) == (0, None)

    # While the AI is paused, nobody can tell how long it takes.
    engine.data.ai["paused_until"] = IN_30_MINUTES
    assert engine.ai.status == STATUS_PAUSED
    settings = settings_json(engine, SYSTEM_VIEWER)
    assert (settings["ai_queue"], settings["ai_queue_seconds"]) == (3, None)


async def test_damaged_stored_data_is_reset(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """Stored AI data of the wrong type is replaced by empty data."""
    engine = await async_setup(hass, client)
    engine.data.ai.update(queue="queue", shadow={}, stats=[], timing=None)

    diagnostics = engine.ai.diagnostics()

    assert diagnostics["queue"] == 0
    assert diagnostics["shadow_candidates"] == 0
    assert diagnostics["totals"]["calls"] == 0
    assert diagnostics["average_seconds"] is None
    assert engine.ai.today()["calls"] == 0
    assert isinstance(engine.data.ai["stats"], dict)


# -- Loop ---------------------------------------------------------------------


def test_error_location() -> None:
    """Errors are described by type and place only, never by their message."""

    def fail() -> None:
        raise RuntimeError(SECRET)

    with pytest.raises(RuntimeError) as raised:
        fail()

    assert error_location(raised.value).startswith("RuntimeError in fail:")
    assert SECRET not in error_location(raised.value)
    assert error_location(RuntimeError(SECRET)) == "RuntimeError"


async def test_start_drops_damaged_queue_entries(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """Queue entries without a hash or review item are dropped at start."""
    engine = await async_setup(hass, client)
    valid = {"hash": "abc", "review": {}}
    engine.data.ai["queue"] = [valid, {"hash": 1, "review": {}}, {"hash": "x"}, "x"]

    engine.ai.async_start()
    await hass.async_block_till_done()

    assert engine.ai.queue == [valid]


async def test_loop_logs_failures_and_waits_for_a_wake(
    hass: HomeAssistant, client: FakeMailClient, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing step is logged without details; the loop goes on when woken."""
    delays = [0.0, 3600.0]
    steps: list[float] = []

    async def step(self: AIWorker) -> float:
        if not steps:
            steps.append(-1.0)
            raise RuntimeError(SECRET)
        delay = delays.pop(0) if delays else 3600.0
        steps.append(delay)
        return delay

    async def settle() -> None:
        for _ in range(10):
            await asyncio.sleep(0)

    with (
        patch.object(AIWorker, "_async_run", REAL_RUN),
        patch.object(AIWorker, "_async_step", step),
    ):
        engine = await async_setup(hass, client)
        await settle()
        task = engine.ai._task
        assert task is not None
        assert not task.done()
        assert "The AI queue failed (RuntimeError in step:" in caplog.text
        assert SECRET not in caplog.text
        assert engine.ai.diagnostics()["running"] is True
        engine.ai.async_start()
        assert engine.ai._task is task

        engine.ai.wake()
        await settle()

        # A step that returns 0 runs the next one at once.
        assert steps[:3] == [-1.0, 0.0, 3600.0]
        count = len(steps)

        engine.ai.wake()
        await settle()

        # A step that returns an hour waits for the next wake.
        assert steps[count:] == [3600.0]
        assert DATA_LOG_FILTER in hass.data

        await engine.ai.async_stop()

    assert task.cancelled()
    assert engine.ai.diagnostics()["running"] is False
    # Stopping also takes the log filter off.
    assert DATA_LOG_FILTER not in hass.data
