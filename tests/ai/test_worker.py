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
from datetime import UTC, datetime, timedelta
import logging
import types
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
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
    AI_SHADOW_DAILY_LIMIT,
    CONF_AI_MODE,
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_MAILBOX,
    ISSUE_AI_REFUSED,
    ISSUE_AI_UNAVAILABLE,
    REASON_AI_REJECTED,
    REASON_AI_SUGGESTION,
    REASON_AI_UNAVAILABLE,
    REASON_UNKNOWN_FORMAT,
    MailKind,
)
from custom_components.parcels.engine import ParcelsEngine
from custom_components.parcels.mail.errors import MailError
from custom_components.parcels.models import MessageState, Source
from custom_components.parcels.parsers.base import MailMessage
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
    hass: HomeAssistant, client: FakeMailClient, generate: AsyncMock
) -> None:
    """A call that takes too long is tried again later; the queue keeps going."""
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
