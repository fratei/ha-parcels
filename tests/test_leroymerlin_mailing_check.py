"""Tests for the one-time re-read of Leroy Merlin's e-mails taken for newsletters.

Releases before 0.1.25 took every e-mail from mailing.leroymerlin.pt for a
newsletter, order e-mails included. Once after the update, Leroy Merlin's
e-mails of the last 30 days recorded as no parcel are read again by the
parsers, never the AI. Old news only joins the parcels it's about: it adds
no parcel that would show as late.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import MailKind, ParcelStatus
from custom_components.parcels.engine import (
    LEROYMERLIN_MAILING_CHECK_KEY,
    ParcelsEngine,
)
from custom_components.parcels.mail.errors import MailServerError
from custom_components.parcels.models import (
    MessageRecord,
    MessageState,
    ParcelEvent,
    ParcelsData,
    Source,
    dt_to_str,
)
from custom_components.parcels.parsers.auth import parse_authentication_results
from custom_components.parcels.parsers.base import MailMessage, ParseResult
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
from .test_returns import ai_lists, async_sync, parsed_as, record_of

NOW = "2026-12-04 09:00:00+00:00"
HEADER = (
    "mx.google.com; dkim=pass header.i=@mailing.leroymerlin.pt header.s=sel1"
    " header.b=abc; dmarc=pass (p=REJECT) header.from=mailing.leroymerlin.pt"
)
ORDER = "001234567890"
OTHER_ORDER = "001234567892"
NEWSLETTER = "Novidades para a sua casa"
NEWS = (
    "Olá Cliente Exemplo,\n"
    "Descubra as novidades da semana para a sua casa e o seu jardim.\n"
    "A Equipa LEROY MERLIN\n"
)
# What releases before 0.1.25 read in every e-mail from mailing.leroymerlin.pt.
OLD = ParseResult(parser="leroymerlin", kind=MailKind.NOT_PARCEL, confidence=0.9)
NO_COUNTS = dict.fromkeys(
    ("read", "applied", "review", "old", "kept", "gone", "failed", "skipped"), 0
)


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on Friday 4 December 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


def mailing(
    provider_id: str, subject: str, text: str, *, days: float = 1
) -> MailMessage:
    """Return an e-mail from Leroy Merlin's mailing address, ``days`` old."""
    raw = (EMAIL_FIXTURES / "leroymerlin/out_for_delivery_pt.eml").read_bytes()
    message = message_from_bytes(
        raw, mailbox=ADDRESS, provider_id=provider_id, provider="google"
    )
    sent = dt_util.utcnow() - timedelta(days=days)
    return replace(
        message,
        message_id=f"<{provider_id}@mail.example.com>",
        sender="delivery@mailing.leroymerlin.pt",
        subject=subject,
        text=text,
        links=(),
        auth=parse_authentication_results(HEADER),
        auth_headers=(HEADER,),
        date=sent,
        received=sent,
    )


def shipped(
    provider_id: str,
    *,
    order: str = ORDER,
    eta: str | None = "07-12-2026",
    days: float = 1,
) -> MailMessage:
    """Return Leroy Merlin's e-mail about an order sent out of its warehouse."""
    due = f"A entrega está prevista para dia {eta}.\n" if eta else ""
    return mailing(
        provider_id,
        f"A encomenda {order} foi expedida do nosso armazém",
        f"Olá Cliente Exemplo,\nA sua encomenda {order} foi expedida do nosso"
        f" armazém.\n{due}Será contactado pelo transportador, no dia anterior,"
        " com a informação do horário de entrega.\nA Equipa LEROY MERLIN\n",
        days=days,
    )


async def async_check(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> dict[str, Any]:
    """Run the check as after an update, on the next sync; return its record."""
    freezer.tick(timedelta(minutes=1))
    engine.data.engine[LEROYMERLIN_MAILING_CHECK_KEY] = {
        "before": dt_to_str(dt_util.utcnow())
    }
    freezer.tick(timedelta(minutes=1))
    await async_sync(hass, engine)
    return engine.data.engine[LEROYMERLIN_MAILING_CHECK_KEY]


async def test_check_reads_an_order_taken_for_a_newsletter(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, local_ai: str
) -> None:
    """An order sent out shows as shipped, with its order and the day it's due.

    The parsers read it: the local AI doesn't read it or check their reading.
    """
    client = FakeMailClient()
    client.add(shipped("shipped-1"))
    add_hub(hass, ai_task_entity=local_ai, ai_mode="suggest")
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"shipped-1": OLD}):
            engine = await async_setup_parcels(hass)
        assert record_of(engine, "shipped-1").state is MessageState.NOT_PARCEL
        assert not engine.data.parcels
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    assert set(check) == {"before", "started", "done", "counts"}
    assert engine.diagnostics()["leroymerlin_mailing_check"] == check
    assert client.fetches == ["shipped-1"]
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert parcel.state.merchant == "Leroy Merlin"
    assert parcel.state.order_numbers == (ORDER,)
    assert parcel.state.eta is not None
    assert parcel.state.eta.start == date(2026, 12, 7)
    assert record_of(engine, "shipped-1").state is MessageState.APPLIED
    assert ai_lists(engine) == []


async def test_check_keeps_a_newsletter(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A newsletter stays one."""
    client = FakeMailClient()
    client.add(mailing("news-1", NEWSLETTER, NEWS))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"news-1": OLD}):
            engine = await async_setup_parcels(hass)
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert record_of(engine, "news-1").state is MessageState.NOT_PARCEL
    assert not engine.data.parcels
    assert not engine.data.review


async def test_check_sends_what_the_parsers_cant_read_to_review(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, local_ai: str
) -> None:
    """An e-mail the parsers can't read with confidence waits in "Needs review".

    The local AI doesn't read it.
    """
    client = FakeMailClient()
    client.add(
        mailing(
            "update-1",
            "Uma mensagem para si",
            f"Olá Cliente Exemplo,\nA sua encomenda {OTHER_ORDER} foi expedida.\n",
        )
    )
    add_hub(hass, ai_task_entity=local_ai, ai_mode="suggest")
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"update-1": OLD}):
            engine = await async_setup_parcels(hass)
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "review": 1}
    record = record_of(engine, "update-1")
    assert record.state is MessageState.REVIEW
    assert [item.message for item in engine.data.review.values()] == [record.hash]
    assert ai_lists(engine) == []
    assert not engine.data.parcels


async def test_check_reads_only_recent_emails_taken_for_no_parcel(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Only Leroy Merlin's e-mails of the last 30 days taken for no parcel.

    Not older ones, another sender's, those read as parcels or those first
    read after the update.
    """
    client = FakeMailClient()
    client.add(shipped("shipped-1"))
    client.add(shipped("old-1", order=OTHER_ORDER, eta="02-11-2026", days=40))
    client.add("carriers/ctt_in_transit_pt.eml", provider_id="ctt-1")
    client.add(shipped("applied-1", order="001234567893"))
    add_hub(hass)
    add_mailbox(hass)
    ctt = ParseResult(parser="ctt", kind=MailKind.NOT_PARCEL, confidence=0.9)

    with patch_mail_clients(client):
        with parsed_as({"shipped-1": OLD, "old-1": OLD, "ctt-1": ctt}):
            engine = await async_setup_parcels(hass)
        assert record_of(engine, "applied-1").state is MessageState.APPLIED
        client.add(mailing("news-1", NEWSLETTER, NEWS))
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    # The newsletter is read once, when it arrives.
    assert sorted(client.fetches) == ["news-1", "shipped-1"]
    for name in ("old-1", "ctt-1", "news-1"):
        assert record_of(engine, name).state is MessageState.NOT_PARCEL


async def test_check_skips_a_shop_the_user_ignores(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The e-mails of a shop the user ignores aren't read."""
    client = FakeMailClient()
    client.add(shipped("shipped-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"shipped-1": OLD}):
            engine = await async_setup_parcels(hass)
        engine.ignore_domain("leroymerlin.pt")
        client.fetches.clear()
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == NO_COUNTS
    assert client.fetches == []
    assert not engine.data.parcels


async def test_check_reads_the_newest_emails_up_to_its_limit(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Past its limit, the check reads the newest e-mails and counts the rest."""
    client = FakeMailClient()
    client.add(shipped("shipped-1", days=2))
    client.add(shipped("shipped-2", order=OTHER_ORDER))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"shipped-1": OLD, "shipped-2": OLD}):
            engine = await async_setup_parcels(hass)
        client.fetches.clear()
        with patch("custom_components.parcels.engine.LEROYMERLIN_MAILING_CHECK_MAX", 1):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1, "skipped": 1}
    assert client.fetches == ["shipped-2"]
    assert record_of(engine, "shipped-1").state is MessageState.NOT_PARCEL


async def test_check_counts_emails_it_cant_download(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An e-mail deleted since counts as gone, one that won't download as failed."""
    client = FakeMailClient()
    client.add(shipped("gone-1"))
    client.add(shipped("down-1", order=OTHER_ORDER))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"gone-1": OLD, "down-1": OLD}):
            engine = await async_setup_parcels(hass)
        client.delete("gone-1")
        client.fetch_errors["down-1"] = MailServerError("down")
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "gone": 1, "failed": 1}
    assert record_of(engine, "down-1").state is MessageState.NOT_PARCEL
    assert not engine.data.parcels


@pytest.mark.parametrize("change", ["forgotten", "dismissed"])
async def test_check_leaves_an_email_that_changed_meanwhile(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, change: str
) -> None:
    """An e-mail forgotten or changed while it's read is left as it is."""
    client = FakeMailClient()
    client.add(shipped("shipped-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"shipped-1": OLD}):
            engine = await async_setup_parcels(hass)
        record = record_of(engine, "shipped-1")

        def meanwhile(message: MailMessage) -> None:
            if change == "forgotten":
                engine.data.messages.pop(record.hash, None)
            else:
                record.state = MessageState.DISMISSED

        with parsed_as({}, during=meanwhile):
            check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "kept": 1}
    assert not engine.data.parcels


@pytest.mark.parametrize(
    ("eta", "days", "added"),
    [
        ("07-12-2026", 10, True),
        ("01-12-2026", 10, False),
        (None, 3, True),
        (None, 10, False),
    ],
    ids=["due", "overdue", "recent", "old"],
)
async def test_check_adds_a_parcel_only_for_current_news(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    eta: str | None,
    days: int,
    added: bool,
) -> None:
    """Old news adds no parcel: it would show as late.

    News is current while its parcel is due today or later, or, without a
    date, for a week after the e-mail. Older news only joins its parcel.
    """
    client = FakeMailClient()
    client.add(shipped("shipped-1", eta=eta, days=days))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"shipped-1": OLD}):
            engine = await async_setup_parcels(hass)
        check = await async_check(hass, engine, freezer)

    counted = "applied" if added else "old"
    assert check["counts"] == {**NO_COUNTS, "read": 1, counted: 1}
    assert len(engine.data.parcels) == (1 if added else 0)
    assert record_of(engine, "shipped-1").state is MessageState.APPLIED


@pytest.mark.parametrize(
    ("eta", "days"), [("07-12-2026", 1), ("30-11-2026", 10)], ids=["due", "overdue"]
)
async def test_check_joins_the_parcel_added_under_the_order_s_number(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, eta: str, days: int
) -> None:
    """The e-mail joins the parcel the user added by hand under its order's number.

    That number isn't a tracking number.
    """
    client = FakeMailClient()
    client.add(shipped("shipped-1", eta=eta, days=days))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"shipped-1": OLD}):
            engine = await async_setup_parcels(hass)
        parcel_id = engine.add_parcel(ORDER, merchant="Leroy Merlin")
        engine.update(parcel_id, {"eta_start": "2026-12-07"})
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    assert list(engine.data.parcels) == [parcel_id]
    parcel = engine.data.parcels[parcel_id]
    assert parcel.auto_merged is None
    assert parcel.state.order_numbers == (ORDER,)
    assert parcel.state.tracking_number is None
    key = record_of(engine, "shipped-1").hash
    assert any(origin.message == key for origin in parcel.origins.values())


async def test_check_leaves_a_delivered_parcel_delivered(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Old news joins its order's parcel and leaves it delivered.

    Here Parcels inferred the delivery, which news would otherwise replace.
    """
    client = FakeMailClient()
    client.add(shipped("shipped-1", eta="30-11-2026", days=10))
    client.add(shipped("shipped-2", eta="30-11-2026", days=9))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"shipped-2": OLD}):
            engine = await async_setup_parcels(hass)
        (parcel,) = engine.data.parcels.values()
        parcel.events.append(
            ParcelEvent(
                time=datetime(2026, 11, 30, 15, tzinfo=UTC),
                source=Source.PARSER,
                status=ParcelStatus.DELIVERED,
                kind=MailKind.DELIVERED,
                inferred=True,
            )
        )
        parcel.touch(dt_util.utcnow())
        assert parcel.state.status is ParcelStatus.DELIVERED
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "applied": 1}
    assert list(engine.data.parcels) == [parcel.id]
    assert parcel.state.status is ParcelStatus.DELIVERED
    key = record_of(engine, "shipped-2").hash
    assert any(origin.message == key for origin in parcel.origins.values())


async def test_check_reads_current_news_first(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An old order e-mail joins the parcel that newer news of the order adds."""
    client = FakeMailClient()
    client.add(
        mailing(
            "order-1",
            f"Recebemos a sua encomenda {ORDER}",
            f"Olá Cliente Exemplo,\nRecebemos a sua encomenda {ORDER}.\n",
            days=20,
        )
    )
    client.add(shipped("shipped-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"order-1": OLD, "shipped-1": OLD}):
            engine = await async_setup_parcels(hass)
        check = await async_check(hass, engine, freezer)

    assert check["counts"] == {**NO_COUNTS, "read": 2, "applied": 2}
    (parcel,) = engine.data.parcels.values()
    assert parcel.state.status is ParcelStatus.SHIPPED
    keys = {record_of(engine, name).hash for name in ("order-1", "shipped-1")}
    assert {origin.message for origin in parcel.origins.values()} == keys


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
            sender_domain="mailing.leroymerlin.pt",
        )
    checked = {"done": dt_to_str(now - timedelta(days=1)), "counts": NO_COUNTS}
    if stored == "checked":
        data.engine[LEROYMERLIN_MAILING_CHECK_KEY] = deepcopy(checked)
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)

    engine = await async_setup_parcels(hass)

    assert (
        engine.data.engine[LEROYMERLIN_MAILING_CHECK_KEY]
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
    client.add(shipped("shipped-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"shipped-1": OLD}):
            engine = await async_setup_parcels(hass)
        client.fetches.clear()
        freezer.tick(timedelta(minutes=1))
        now = dt_to_str(dt_util.utcnow())
        started = {"before": now, "started": now}
        engine.data.engine[LEROYMERLIN_MAILING_CHECK_KEY] = deepcopy(started)
        freezer.tick(timedelta(minutes=1))
        await async_sync(hass, engine)

    assert engine.data.engine[LEROYMERLIN_MAILING_CHECK_KEY] == started
    assert client.fetches == []
    assert not engine.data.parcels
