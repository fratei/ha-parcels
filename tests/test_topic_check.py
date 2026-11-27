"""Tests for the one-time re-read of the e-mails waiting in "Needs review".

Releases before 0.1.27 took surveys, review requests, carriers' receipts and
invoices for shipping news. Once after the update, the e-mails waiting in
review are read again by the parsers, never the AI: those now known as no
parcel news leave the list, and what they added goes.

0.1.27 knew surveys by a fixed list of subject phrases, which failed both
ways. Once after an update from it, the e-mails waiting in review are read
again, and so are those it took for no parcel. 0.1.28 took deliveries whose
text also asked for a rating for surveys: once after an update from it, what
it took for no parcel is read again.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant.common import async_capture_events

from custom_components.parcels.const import EVENT_DELIVERED, MailKind, ParcelStatus
from custom_components.parcels.engine import (
    RELEASE_KEY,
    SURVEY_CHECK_KEY,
    SURVEY_RECHECK_KEY,
    TOPIC_CHECK_KEY,
    TOPIC_RECHECK_KEY,
    ParcelsEngine,
)
from custom_components.parcels.mail.errors import MailServerError
from custom_components.parcels.models import (
    MessageRecord,
    MessageState,
    ParcelsData,
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
DELIVERY = f"Olá Alex,\n\nO objeto {TRACKING} foi entregue hoje.\n"
# A delivery whose closing line asks how it went: 0.1.28 took it for a survey.
RATED_DELIVERY = f"{DELIVERY}\nDiga-nos como correu.\n"
NO_COUNTS = dict.fromkeys(("read", "settled", "kept", "gone", "failed", "skipped"), 0)
NO_READS = dict.fromkeys(
    ("read", "applied", "review", "old", "kept", "gone", "failed", "skipped"), 0
)
# How 0.1.27 read a delivery whose subject also asks for a review.
DROPPED = ParseResult(parser="ctt", kind=MailKind.NOT_PARCEL, confidence=0.9)
ORDER = "406-1234567-1234567"
# How 0.1.27 read Amazon's request to review an item: a delivery it doubted.
REVIEW_READ = ParseResult(
    parser="amazon", kind=MailKind.DELIVERED, order_numbers=[ORDER], confidence=0.5
)
# When 0.1.27 started, and when its check read the e-mails waiting in review.
STARTED = "2026-11-10T09:00:00+00:00"
CHECKED = "2026-11-10T09:05:00+00:00"
# When 0.1.28 started, and when its check read what 0.1.27 took for no parcel.
UPDATED = "2026-11-12T09:00:00+00:00"
REREAD = "2026-11-12T09:05:00+00:00"
MARKETPLACE_HEADER = (
    "mx.google.com; dkim=pass header.i=@mailing.leroymerlin.pt header.s=sel1"
    " header.b=abc; dmarc=pass (p=REJECT) header.from=mailing.leroymerlin.pt"
)
MARKETPLACE_ORDER = "1234567890123-A"


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


def later(message: MailMessage, hours: float) -> MailMessage:
    """Return ``message`` as sent ``hours`` after its fixture's time."""
    assert message.date is not None
    sent = message.date + timedelta(hours=hours)
    return replace(message, date=sent, received=sent)


def delivery(provider_id: str = "done-1") -> MailMessage:
    """Return CTT's delivery, whose subject also asks for a review."""
    return later(
        ctt(provider_id, "Entrega concluída: avalie a sua experiência", DELIVERY), 2
    )


def amazon_review(provider_id: str = "review-1") -> MailMessage:
    """Return Amazon's request to review an item it delivered."""
    sent = datetime.fromisoformat("2026-11-15T18:00:00+00:00")
    return replace(
        load_message("amazon/order_pedido_pt.eml"),
        provider_id=provider_id,
        message_id=f"<{provider_id}@amazon.example>",
        sender="avaliacoes@amazon.es",
        subject="Alex, como classificaria o Tapete Exemplo?",
        text=(
            f"Olá Alex,\n\nA sua encomenda {ORDER} foi entregue. "
            "Como classificaria o Tapete Exemplo?\n"
        ),
        links=(),
        date=sent,
        received=sent,
    )


def marketplace(provider_id: str, subject: str, text: str) -> MailMessage:
    """Return a notice from Leroy Merlin's marketplace, a day old."""
    raw = (EMAIL_FIXTURES / "leroymerlin/out_for_delivery_pt.eml").read_bytes()
    message = message_from_bytes(
        raw, mailbox=ADDRESS, provider_id=provider_id, provider="google"
    )
    sent = dt_util.utcnow() - timedelta(days=1)
    return replace(
        message,
        message_id=f"<{provider_id}@mail.example.com>",
        sender="marketplace@mailing.leroymerlin.pt",
        subject=subject,
        text=text,
        links=(),
        auth=parse_authentication_results(MARKETPLACE_HEADER),
        auth_headers=(MARKETPLACE_HEADER,),
        date=sent,
        received=sent,
    )


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
    hass: HomeAssistant,
    engine: ParcelsEngine,
    freezer: FrozenDateTimeFactory,
    key: str = TOPIC_CHECK_KEY,
    since: datetime | None = None,
) -> dict[str, Any]:
    """Run a check as after an update, on the next sync; return its record."""
    freezer.tick(timedelta(minutes=1))
    check = {"before": dt_to_str(dt_util.utcnow())}
    if since is not None:
        check["since"] = dt_to_str(since)
    engine.data.engine[key] = check
    freezer.tick(timedelta(minutes=1))
    await async_sync(hass, engine)
    return engine.data.engine[key]


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


async def test_recheck_settles_a_review_request_0127_kept_in_review(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Amazon's review request that 0.1.27 kept in review leaves it, once.

    0.1.27 knew surveys by a fixed list of subject phrases, without "como
    classificaria".
    """
    client = FakeMailClient()
    client.add(amazon_review())
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"review-1": REVIEW_READ}):
            engine = await async_setup_parcels(hass)
        assert engine.data.review
        client.fetches.clear()
        check = await async_check(hass, engine, freezer, TOPIC_RECHECK_KEY)
        await async_sync(hass, engine)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "settled": 1}
    assert client.fetches == ["review-1"]
    assert not engine.data.review
    assert not engine.data.parcels
    assert record_of(engine, "review-1").state is MessageState.NOT_PARCEL


@pytest.mark.parametrize(
    ("subject", "text", "read"),
    [
        pytest.param(
            f"Recebeu uma mensagem referente à encomenda nº {MARKETPLACE_ORDER}",
            "Olá Alex,\nRecebeu uma mensagem do vendedor Loja Exemplo referente "
            f"à encomenda nº {MARKETPLACE_ORDER}.\nMensagem: Olá, a sua encomenda "
            "foi enviada hoje pela transportadora.\n",
            ParseResult(
                parser="leroymerlin",
                kind=MailKind.SHIPPED,
                order_numbers=[MARKETPLACE_ORDER],
                confidence=0.6,
            ),
            id="seller-message",
        ),
        pytest.param(
            "Leroy Merlin Marketplace - Abrir reclamação sobre o pedido "
            f"{MARKETPLACE_ORDER}",
            f"Olá Alex,\nPode abrir uma reclamação sobre o pedido {MARKETPLACE_ORDER} "
            "se a sua encomenda não foi entregue.\n",
            ParseResult(
                parser="leroymerlin",
                kind=MailKind.UNKNOWN,
                confidence=0.0,
                notes=(NOTE_KNOWN_SENDER_UNPARSED,),
            ),
            id="complaint",
        ),
    ],
)
async def test_recheck_settles_a_marketplace_notice_waiting_in_review(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    subject: str,
    text: str,
    read: ParseResult,
) -> None:
    """A seller's message or a prompt to complain that 0.1.27 kept in review leaves it.

    0.1.27 read a seller's message as news it doubted, and a prompt to
    complain as an e-mail its parser couldn't read.
    """
    client = FakeMailClient()
    client.add(marketplace("notice-1", subject, text))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"notice-1": read}):
            engine = await async_setup_parcels(hass)
        assert engine.data.review
        client.fetches.clear()
        check = await async_check(hass, engine, freezer, TOPIC_RECHECK_KEY)
        await async_sync(hass, engine)

    assert check["counts"] == {**NO_COUNTS, "read": 1, "settled": 1}
    assert client.fetches == ["notice-1"]
    assert not engine.data.review
    assert not engine.data.parcels
    assert record_of(engine, "notice-1").state is MessageState.NOT_PARCEL


async def test_survey_check_reads_a_delivery_0127_took_for_a_survey(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A delivery 0.1.27 dropped for asking for a review is read again, once.

    It's today's news, so it's told as usual.
    """
    client = FakeMailClient()
    client.add(ctt("news-1", "O seu objeto está em trânsito", NEWS))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        (parcel,) = engine.data.parcels.values()
        assert parcel.state.status is ParcelStatus.IN_TRANSIT
        started = dt_util.utcnow()
        freezer.tick(timedelta(hours=1))
        client.add(delivery())
        with parsed_as({"done-1": DROPPED}):
            await async_sync(hass, engine)
        assert record_of(engine, "done-1").state is MessageState.NOT_PARCEL
        assert parcel.state.status is ParcelStatus.IN_TRANSIT
        client.fetches.clear()
        delivered = async_capture_events(hass, EVENT_DELIVERED)
        check = await async_check(
            hass, engine, freezer, SURVEY_CHECK_KEY, since=started
        )
        await async_sync(hass, engine)

    assert check["counts"] == {**NO_READS, "read": 1, "applied": 1}
    assert client.fetches == ["done-1"]
    assert list(engine.data.parcels) == [parcel.id]
    assert engine.data.parcels[parcel.id].state.status is ParcelStatus.DELIVERED
    assert record_of(engine, "done-1").state is MessageState.APPLIED
    assert [event.data["parcel_id"] for event in delivered] == [parcel.id]


async def test_survey_check_reads_only_what_0127_took_for_no_parcel(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Only the e-mails first read since 0.1.27 started are read again.

    A survey stays no parcel news.
    """
    client = FakeMailClient()
    client.add(delivery("early-1"))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        with parsed_as({"early-1": DROPPED}):
            engine = await async_setup_parcels(hass)
        freezer.tick(timedelta(hours=1))
        started = dt_util.utcnow()
        client.add(survey())
        await async_sync(hass, engine)
        client.fetches.clear()
        check = await async_check(
            hass, engine, freezer, SURVEY_CHECK_KEY, since=started
        )

    assert check["counts"] == {**NO_READS, "read": 1, "kept": 1}
    assert client.fetches == ["survey-1"]
    assert not engine.data.parcels
    assert not engine.data.review
    assert record_of(engine, "early-1").state is MessageState.NOT_PARCEL
    assert record_of(engine, "survey-1").state is MessageState.NOT_PARCEL


async def test_survey_check_skips_a_sender_the_user_ignores(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The e-mails of a sender the user ignores aren't read."""
    client = FakeMailClient()
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        started = dt_util.utcnow()
        client.add(delivery())
        with parsed_as({"done-1": DROPPED}):
            await async_sync(hass, engine)
        engine.ignore_domain("ctt.pt")
        client.fetches.clear()
        check = await async_check(
            hass, engine, freezer, SURVEY_CHECK_KEY, since=started
        )

    assert check["counts"] == NO_READS
    assert client.fetches == []
    assert not engine.data.parcels


async def test_survey_check_reads_the_newest_emails_up_to_its_limit(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Past its limit, the check reads the newest e-mails and counts the rest."""
    client = FakeMailClient()
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        started = dt_util.utcnow()
        client.add(survey("survey-1"))
        client.add(later(survey("survey-2"), 1))
        await async_sync(hass, engine)
        client.fetches.clear()
        with patch("custom_components.parcels.engine.SURVEY_CHECK_MAX", 1):
            check = await async_check(
                hass, engine, freezer, SURVEY_CHECK_KEY, since=started
            )

    assert check["counts"] == {**NO_READS, "read": 1, "kept": 1, "skipped": 1}
    assert client.fetches == ["survey-2"]


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


# What 0.1.27 stored of its own check.
EARLIER_CHECKS: dict[str, dict[str, Any] | None] = {
    # A release before 0.1.27: its check reads every e-mail in review.
    "before-0.1.27": None,
    # 0.1.27 read the e-mails waiting in review.
    "checked": {
        "before": STARTED,
        "started": STARTED,
        "done": CHECKED,
        "counts": NO_COUNTS,
    },
    # 0.1.27 was installed afresh.
    "fresh": {"done": STARTED},
    # 0.1.27 never read the mailboxes: its check now reads every e-mail.
    "unchecked": {"before": STARTED},
    # Nothing was read.
    "nothing": {"done": STARTED},
    # The checks are already due, or done.
    "planned": {"done": STARTED},
}


@pytest.mark.parametrize("stored", list(EARLIER_CHECKS))
async def test_checks_are_due_once_after_an_update_from_0127(
    hass: HomeAssistant, hass_storage: dict[str, Any], stored: str
) -> None:
    """After an update from 0.1.27, what it read is read again, once.

    The e-mails waiting in review are, once its check read them, and so are
    those it took for no parcel since it started.
    """
    now = dt_to_str(dt_util.utcnow())
    data = ParcelsData()
    if stored != "nothing":
        data.messages["hash"] = MessageRecord(
            hash="hash",
            seen=dt_util.utcnow() - timedelta(days=2),
            state=MessageState.REVIEW,
            sender_domain="ctt.pt",
        )
    if (earlier := EARLIER_CHECKS[stored]) is not None:
        data.engine[TOPIC_CHECK_KEY] = deepcopy(earlier)
    planned = {"done": CHECKED}
    if stored == "planned":
        data.engine[TOPIC_RECHECK_KEY] = deepcopy(planned)
        data.engine[SURVEY_CHECK_KEY] = deepcopy(planned)
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)

    engine = await async_setup_parcels(hass)

    due = {"before": now}
    survey_due = {"before": now, "since": STARTED}
    done = {"done": now}
    assert [
        engine.data.engine.get(key)
        for key in (TOPIC_CHECK_KEY, TOPIC_RECHECK_KEY, SURVEY_CHECK_KEY)
    ] == {
        "before-0.1.27": [due, done, done],
        "checked": [earlier, due, survey_due],
        "fresh": [earlier, due, survey_due],
        "unchecked": [due, done, survey_due],
        "nothing": [earlier, done, done],
        "planned": [earlier, planned, planned],
    }[stored]


async def test_survey_recheck_reads_a_delivery_0128_took_for_a_survey(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A delivery 0.1.28 dropped for asking how it went is read again, once.

    Its subject names no status, and only its closing line asks for a rating.
    It's today's news, so it's told as usual.
    """
    client = FakeMailClient()
    client.add(ctt("news-1", "O seu objeto está em trânsito", NEWS))
    add_hub(hass)
    add_mailbox(hass)

    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        (parcel,) = engine.data.parcels.values()
        started = dt_util.utcnow()
        freezer.tick(timedelta(hours=1))
        client.add(later(ctt("done-1", f"Objeto {TRACKING}", RATED_DELIVERY), 2))
        with parsed_as({"done-1": DROPPED}):
            await async_sync(hass, engine)
        assert parcel.state.status is ParcelStatus.IN_TRANSIT
        client.fetches.clear()
        delivered = async_capture_events(hass, EVENT_DELIVERED)
        check = await async_check(
            hass, engine, freezer, SURVEY_RECHECK_KEY, since=started
        )
        await async_sync(hass, engine)

    assert check["counts"] == {**NO_READS, "read": 1, "applied": 1}
    assert client.fetches == ["done-1"]
    assert list(engine.data.parcels) == [parcel.id]
    assert engine.data.parcels[parcel.id].state.status is ParcelStatus.DELIVERED
    assert record_of(engine, "done-1").state is MessageState.APPLIED
    assert [event.data["parcel_id"] for event in delivered] == [parcel.id]


# What 0.1.28 stored of its check of what 0.1.27 took for no parcel.
SURVEY_CHECKS: dict[str, dict[str, Any] | None] = {
    # 0.1.28 read again what 0.1.27 took for no parcel, from when it started.
    "checked": {
        "before": UPDATED,
        "since": STARTED,
        "started": UPDATED,
        "done": REREAD,
        "counts": NO_READS,
    },
    # 0.1.28 was installed afresh, or over a release before 0.1.27.
    "fresh": {"done": UPDATED},
    # 0.1.28 never read the mailboxes: its check now reads, then this one.
    "unchecked": {"before": UPDATED, "since": STARTED},
    # A store without that check: it's planned from 0.1.27's own check, and
    # it reads what 0.1.28 took for no parcel too.
    "unplanned": None,
    # 0.1.28 read nothing.
    "nothing": {"done": UPDATED},
    # 0.1.27 or an earlier release.
    "0.1.27": None,
    # The check is already due, or done.
    "planned": {"done": UPDATED},
}


@pytest.mark.parametrize("stored", list(SURVEY_CHECKS))
async def test_survey_recheck_is_due_once_after_an_update_from_0128(
    hass: HomeAssistant, hass_storage: dict[str, Any], stored: str
) -> None:
    """After an update from 0.1.28, what it took for no parcel is read again, once.

    From when it started, or from when 0.1.27 started once its own check read
    what 0.1.27 took for no parcel.
    """
    now = dt_to_str(dt_util.utcnow())
    data = ParcelsData()
    if stored != "nothing":
        data.messages["hash"] = MessageRecord(
            hash="hash",
            seen=dt_util.utcnow() - timedelta(days=2),
            state=MessageState.NOT_PARCEL,
            sender_domain="ctt.pt",
        )
    if stored != "0.1.27":
        data.engine[RELEASE_KEY] = {"version": "0.1.28", "changed": 0}
    data.engine[TOPIC_CHECK_KEY] = {"done": STARTED}
    data.engine[TOPIC_RECHECK_KEY] = {"done": UPDATED}
    if (earlier := SURVEY_CHECKS[stored]) is not None:
        data.engine[SURVEY_CHECK_KEY] = deepcopy(earlier)
    elif stored == "0.1.27":
        del data.engine[TOPIC_RECHECK_KEY]
    planned = {"done": REREAD}
    if stored == "planned":
        data.engine[SURVEY_RECHECK_KEY] = deepcopy(planned)
    hass_storage["parcels"] = {
        "version": 1,
        "minor_version": 1,
        "key": "parcels",
        "data": data.as_dict(),
    }
    add_hub(hass)

    engine = await async_setup_parcels(hass)

    assert (
        engine.data.engine[SURVEY_RECHECK_KEY]
        == {
            "checked": {"before": now, "since": STARTED},
            "fresh": {"before": now, "since": UPDATED},
            "unchecked": {"before": now, "since": UPDATED},
            "unplanned": {"before": now, "since": now},
            "nothing": {"done": now},
            "0.1.27": {"done": now},
            "planned": planned,
        }[stored]
    )
    if stored == "unchecked":
        assert engine.data.engine[SURVEY_CHECK_KEY] == earlier
    if stored == "unplanned":
        assert engine.data.engine[SURVEY_CHECK_KEY] == {"before": now, "since": STARTED}
