"""Builders for the local AI tests."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.parcels.ai.prompt import FIELDS, LIST_FIELDS
from custom_components.parcels.parsers.base import Link, MailMessage

TZ = ZoneInfo("Europe/Lisbon")
# Wednesday 18 November 2026, 10:00 in Lisbon.
RECEIVED = datetime(2026, 11, 18, 10, 0, tzinfo=TZ)

SUBENTRY_ID = "sub1"
LOCAL_URL = "http://localhost:11434"
LOCAL_MODEL = "qwen3:4b-instruct"


def make_message(
    text: str = "",
    *,
    subject: str = "",
    sender: str = "noreply@loja-exemplo.pt",
    sender_name: str = "",
    links: Iterable[str] = (),
    date: datetime = RECEIVED,
    language: str | None = "pt",
) -> MailMessage:
    """Return an e-mail with synthetic content."""
    return MailMessage(
        message_id="<20261118100000.ab12@mail.example.com>",
        provider_id="test",
        provider="google",
        mailbox="alex@example.com",
        sender=sender,
        sender_name=sender_name,
        subject=subject,
        date=date,
        text=text,
        links=tuple(Link(url) for url in links),
        language=language,
    )


def answer(**values: Any) -> dict[str, Any]:
    """Return a model answer: every field empty except ``values``."""
    data: dict[str, Any] = {
        field: [] if field in LIST_FIELDS else "" for field in FIELDS
    }
    data.update(values)
    return data


def add_ai_task(
    hass: HomeAssistant,
    *,
    url: str | None = LOCAL_URL,
    model: str | None = LOCAL_MODEL,
    domain: str = "ai_task",
    platform: str = "ollama",
    entry_domain: str | None = None,
    link_subentry: bool = True,
    object_id: str = "local_ollama",
) -> str:
    """Add an AI task entity with its config entry and subentry; return its id.

    The entry and subentry look like the Ollama integration's: the server
    URL in the entry data, the model in an ``ai_task_data`` subentry.
    """
    subentry_data = {"model": model} if model is not None else {}
    entry = MockConfigEntry(
        domain=entry_domain or platform,
        data={"url": url} if url is not None else {},
        subentries_data=[
            {
                "data": subentry_data,
                "subentry_id": SUBENTRY_ID,
                "subentry_type": "ai_task_data",
                "title": "AI task",
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)
    entity = er.async_get(hass).async_get_or_create(
        domain,
        platform,
        SUBENTRY_ID,
        config_entry=entry,
        config_subentry_id=SUBENTRY_ID if link_subentry else None,
        suggested_object_id=object_id,
    )
    return entity.entity_id
