"""Tests for the repair about the e-mails of a known sender no parser reads.

Such an e-mail waits under "Needs review", or goes to the local AI. It counts
once it turns out to be about a parcel: when the user adds it from review, or
the AI's reading is added in automatic mode (see tests/ai/test_worker.py).
Two of a sender's e-mails that arrived within a week raise the repair. Those
the user dismisses don't count, nor those the AI finds aren't about a parcel.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import DOMAIN, ISSUE_PARSER_OUTDATED
from custom_components.parcels.engine import UNPARSED_RULE_KEY, ParcelsEngine
from custom_components.parcels.models import ParcelsData, ReviewItem, dt_to_str

from .common import (
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    patch_mail_clients,
)
from .test_amazon_accepted_check import UNPARSED
from .test_amazon_ai_check import NOW, ORDER, ORDER_NUMBER, mail
from .test_returns import parsed_as, record_of

ISSUE = ISSUE_PARSER_OUTDATED.format("amazon.es")
OTHER_ORDER_NUMBER = "406-5512093-7720418"


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on Friday 4 December 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


@pytest.fixture
def client() -> Iterator[FakeMailClient]:
    """Return the mailbox, patched in for the whole test."""
    client = FakeMailClient()
    with patch_mail_clients(client):
        yield client


def repair(hass: HomeAssistant) -> ir.IssueEntry | None:
    """Return the repair about Amazon's e-mails."""
    return ir.async_get(hass).async_get_issue(DOMAIN, ISSUE)


def order(number: str) -> dict[str, Any]:
    """Return what the user typed to add an e-mail from review."""
    return {"kind": "order", "order_numbers": [number]}


async def async_unread(
    hass: HomeAssistant, client: FakeMailClient, *days_ago: int
) -> tuple[ParcelsEngine, list[ReviewItem]]:
    """Set up Parcels with Amazon e-mails no parser reads, sent ``days_ago``.

    Each waits under "Needs review": returns them in the same order.
    """
    now = dt_util.utcnow()
    ids = [f"order-{n}" for n in range(1, len(days_ago) + 1)]
    for provider_id, days in zip(ids, days_ago, strict=True):
        client.add(mail(ORDER, provider_id, sent=now - timedelta(days=days)))
    add_hub(hass)
    add_mailbox(hass)
    with parsed_as(dict.fromkeys(ids, UNPARSED)):
        engine = await async_setup_parcels(hass)
    items = []
    for provider_id in ids:
        key = record_of(engine, provider_id).hash
        (item,) = [i for i in engine.data.review.values() if i.message == key]
        items.append(item)
    return engine, items


async def test_emails_waiting_for_review_dont_count(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """A known sender's e-mails no parser reads raise nothing on their own.

    They could be about something else: a survey, an invoice.
    """
    engine, items = await async_unread(hass, client, 2, 1)

    assert [item.unparsed for item in items] == [True, True]
    assert repair(hass) is None
    assert not engine.data.engine.get("unparsed")
    assert engine.diagnostics()["unparsed_senders"] == []


async def test_emails_added_from_review_raise_the_repair(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """Two e-mails of a week that the user added from review raise the repair."""
    engine, (first, second) = await async_unread(hass, client, 2, 1)

    engine.review_accept(first.id, order(ORDER_NUMBER))
    assert repair(hass) is None
    engine.review_accept(second.id, order(OTHER_ORDER_NUMBER))

    assert repair(hass) is not None
    assert engine.diagnostics()["unparsed_senders"] == ["amazon.es"]


async def test_dismissed_emails_dont_count(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """An e-mail the user dismissed wasn't about a parcel: it doesn't count."""
    engine, (first, second) = await async_unread(hass, client, 2, 1)

    engine.review_dismiss(first.id)
    engine.review_accept(second.id, order(ORDER_NUMBER))

    assert repair(hass) is None
    assert len(engine.data.engine["unparsed"]["amazon.es"]) == 1


async def test_emails_more_than_a_week_apart_raise_nothing(
    hass: HomeAssistant, client: FakeMailClient
) -> None:
    """The week is the e-mails' own, even when both are added on the same day."""
    engine, (first, second) = await async_unread(hass, client, 9, 1)

    engine.review_accept(first.id, order(ORDER_NUMBER))
    engine.review_accept(second.id, order(OTHER_ORDER_NUMBER))

    assert repair(hass) is None
    assert len(engine.data.engine["unparsed"]["amazon.es"]) == 2


@pytest.mark.parametrize("earlier", [True, False])
async def test_counts_of_earlier_releases_are_dropped_once(
    hass: HomeAssistant, hass_storage: dict[str, Any], earlier: bool
) -> None:
    """After the update, what earlier releases counted goes, with its repairs.

    They counted every e-mail no parser read, surveys and invoices too. Only
    once: what this release counted stays.
    """
    now = dt_util.utcnow()
    counted = {
        f"message-{days}": dt_to_str(now - timedelta(days=days)) for days in (2, 1)
    }
    data = ParcelsData()
    data.engine["unparsed"] = {"amazon.es": dict(counted)}
    rule = {"done": dt_to_str(now - timedelta(days=3))}
    if not earlier:
        data.engine[UNPARSED_RULE_KEY] = dict(rule)
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="parser_outdated",
        translation_placeholders={"sender": "amazon.es"},
    )
    add_hub(hass)

    engine = await async_setup_parcels(hass)

    if earlier:
        assert not engine.data.engine.get("unparsed")
        assert repair(hass) is None
        assert engine.data.engine[UNPARSED_RULE_KEY] == {"done": dt_to_str(now)}
    else:
        assert engine.data.engine["unparsed"] == {"amazon.es": counted}
        assert repair(hass) is not None
        assert engine.data.engine[UNPARSED_RULE_KEY] == rule
