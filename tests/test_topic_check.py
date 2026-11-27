"""Tests for the one-time re-read of the e-mails waiting in "Needs review".

Releases before 0.1.27 took surveys, review requests, carriers' receipts and
invoices for shipping news. Once after the update, the e-mails waiting in
review are read again by the parsers, never the AI: those now known as no
parcel news leave the list, and what they added goes.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import MailKind
from custom_components.parcels.engine import TOPIC_CHECK_KEY, ParcelsEngine
from custom_components.parcels.mail.errors import MailServerError
from custom_components.parcels.models import (
    MessageRecord,
    MessageState,
    ParcelsData,
    dt_to_str,
)
from custom_components.parcels.parsers.base import (
    MailMessage,
    ParsedShipment,
    ParseResult,
)

from .common import (
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    load_message,
    patch_mail_clients,
)
from .test_returns import async_sync, parsed_as, record_of

NOW = "2026-11-17 15:00:00+00:00"
TRACKING = "RR123456785PT"
SURVEY = (
    f"Olá Alex,\n\nO objeto {TRACKING} foi entregue a 4 de novembro. "
    "Responda a 3 perguntas sobre a entrega e ajude-nos a melhorar.\n"
)
NEWS = f"Olá Alex,\n\nO seu objeto {TRACKING} já está em trânsito na rede CTT.\n"
NO_COUNTS = dict.fromkeys(("read", "settled", "kept", "gone", "failed", "skipped"), 0)


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on Tuesday 17 November 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


def ctt(provider_id: str, subject: str, text: str) -> MailMessage:
    """Return a CTT e-mail."""
    return replace(
        load_message("carriers/ctt_in_transit_pt.eml"),
        provider_id=provider_id,
        message_id=f"<{provider_id}@ctt.example>",
        subject=subject,
        text=text,
        links=(),
    )


def survey(provider_id: str = "survey-1") -> MailMessage:
    """Return CTT's survey about a delivery."""
    return ctt(provider_id, "Como correu a sua entrega?", SURVEY)


def old(confidence: float) -> ParseResult:
    """Return how an earlier release read the survey: as a delivery."""
    return ParseResult(
        parser="ctt",
        kind=MailKind.DELIVERED,
        shipments=[
            ParsedShipment(
                carrier="ctt", tracking_number=TRACKING, kind=MailKind.DELIVERED
            )
        ],
        confidence=confidence,
    )


async def async_check(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> dict[str, Any]:
    """Run the check as after an update, on the next sync; return its record."""
    freezer.tick(timedelta(minutes=1))
    engine.data.engine[TOPIC_CHECK_KEY] = {"before": dt_to_str(dt_util.utcnow())}
    freezer.tick(timedelta(minutes=1))
    await async_sync(hass, engine)
    return engine.data.engine[TOPIC_CHECK_KEY]


async def test_check_settles_a_survey_waiting_in_review(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A survey an earlier release sent to review leaves it, once."""
    client = FakeMailClient()
    client.add(survey())
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"survey-1": old(0.6)}):
            engine = await async_setup_parcels(hass)
        assert engine.data.review
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)
        await async_sync(hass, engine)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "settled": 1}
    assert client.fetches == ["survey-1"]
    assert not engine.data.review
    assert not engine.data.parcels
    assert record_of(engine, "survey-1").state is MessageState.NOT_PARCEL


async def test_check_keeps_what_is_still_news(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail the parsers still read as news waits in review as it was."""
    client = FakeMailClient()
    client.add(ctt("news-1", "O seu objeto está em trânsito", NEWS))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client), parsed_as({"news-1": old(0.6)}):
        engine = await async_setup_parcels(hass)
        review = deepcopy(engine.data.review)
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert engine.data.review == review
    assert record_of(engine, "news-1").state is MessageState.REVIEW


async def test_check_marks_the_shopify_stores_waiting_in_review(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A Shopify store's e-mail waiting in review is known as a store's.

    Releases before 0.1.27 didn't keep it, so the page offered to ignore the
    store for one e-mail Parcels couldn't read.
    """
    client = FakeMailClient()
    client.add(
        replace(
            load_message("shopify/shipped_pt.eml"),
            provider_id="store-1",
            message_id="<store-1@shopifyemail.com>",
            subject="Uma mensagem para si",
            text="Olá Alex,\n\nA sua encomenda #1002 foi expedida hoje.\n",
            links=(),
        )
    )
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        (item,) = engine.data.review.values()
        item.shopify_store = False
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert [item.known_sender for item in engine.data.review.values()] == [True]


async def test_check_leaves_what_an_earlier_release_applied(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A survey already applied as a delivery isn't read again.

    A survey follows a delivery, so what it applied is usually right.
    """
    client = FakeMailClient()
    client.add(survey())
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"survey-1": old(0.81)}):
            engine = await async_setup_parcels(hass)
        (parcel,) = engine.data.parcels.values()
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == NO_COUNTS
    assert not client.fetches
    assert list(engine.data.parcels) == [parcel.id]
    assert record_of(engine, "survey-1").state is MessageState.APPLIED


async def test_check_leaves_an_item_the_user_settled_meanwhile(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An item the user dismisses while its e-mail is read stays dismissed."""
    client = FakeMailClient()
    client.add(survey())
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"survey-1": old(0.6)}):
            engine = await async_setup_parcels(hass)
        (item,) = engine.data.review.values()
        with parsed_as({}, during=lambda _: engine.review_dismiss(item.id)):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert record_of(engine, "survey-1").state is MessageState.DISMISSED


async def test_check_reads_the_newest_emails_up_to_its_limit(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Past its limit, the check reads the newest e-mails and counts the rest."""
    client = FakeMailClient()
    client.add(survey("survey-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"survey-1": old(0.6), "survey-2": old(0.6)}):
            engine = await async_setup_parcels(hass)
            freezer.tick(timedelta(hours=1))
            client.add(survey("survey-2"))
            await async_sync(hass, engine)
        assert len(engine.data.review) == 2
        client.fetches.clear()
        with patch("custom_components.parcels.engine.TOPIC_CHECK_MAX", 1):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "settled": 1, "skipped": 1}
    assert client.fetches == ["survey-2"]
    assert record_of(engine, "survey-1").state is MessageState.REVIEW


async def test_check_counts_emails_it_cant_download(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail deleted since counts as gone, one that won't download as failed."""
    client = FakeMailClient()
    client.add(survey("gone-1"))
    client.add(survey("down-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"gone-1": old(0.6), "down-1": old(0.6)}):
            engine = await async_setup_parcels(hass)
        client.delete("gone-1")
        client.fetch_errors["down-1"] = MailServerError("down")
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "gone": 1, "failed": 1}
    assert record_of(engine, "down-1").state is MessageState.REVIEW


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
            state=MessageState.REVIEW,
            sender_domain="ctt.pt",
        )
    checked = {"done": dt_to_str(now - timedelta(days=1)), "counts": NO_COUNTS}
    if stored == "checked":
        data.engine[TOPIC_CHECK_KEY] = deepcopy(checked)
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)

    engine = await async_setup_parcels(hass)

    assert (
        engine.data.engine[TOPIC_CHECK_KEY]
        == {
            "messages": {"before": dt_to_str(now)},
            "nothing": {"done": dt_to_str(now)},
            "checked": checked,
        }[stored]
    )
