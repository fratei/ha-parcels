"""Tests for the dashboard cards: loaded once, from a URL that changes per build."""

from __future__ import annotations

import hashlib
from http import HTTPStatus
from pathlib import Path
import re
from unittest.mock import patch

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, add_extra_js_url
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant.typing import ClientSessionGenerator

from custom_components.parcels import const
from custom_components.parcels.ai import validate
from custom_components.parcels.ai.prompt import ANSWER_CAPS
from custom_components.parcels.cards import (
    CARDS_FILE,
    FRONTEND_DIR,
    async_register_frontend,
)
from custom_components.parcels.const import DOMAIN, FRONTEND_URL_PATH

from .common import add_hub

CARDS = FRONTEND_DIR / CARDS_FILE
STRINGS = Path(__file__).parents[1] / "frontend" / "src" / "strings.ts"
BENCHMARK = Path(__file__).parents[1] / "docs" / "ai-benchmark.md"


async def test_cards(hass: HomeAssistant, hass_client: ClientSessionGenerator) -> None:
    """Every dashboard loads the cards, which browsers cache until a new build."""
    add_hub(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    version = hashlib.sha256(CARDS.read_bytes()).hexdigest()[:12]
    url = f"{FRONTEND_URL_PATH}/{CARDS_FILE}?v={version}"

    modules = hass.data[DATA_EXTRA_MODULE_URL].urls
    assert [module for module in modules if FRONTEND_URL_PATH in module] == [url]
    client = await hass_client()
    response = await client.get(url)
    assert response.status == HTTPStatus.OK
    assert await response.read() == CARDS.read_bytes()
    assert response.headers["Cache-Control"].startswith("public, max-age=")


async def test_cards_added_once(hass: HomeAssistant) -> None:
    """Reloading Parcels doesn't add the cards to the dashboards again."""
    hub = add_hub(hass)
    with patch(
        "custom_components.parcels.cards.add_extra_js_url", wraps=add_extra_js_url
    ) as add:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert await hass.config_entries.async_reload(hub.entry_id)
        await hass.async_block_till_done()
        await async_register_frontend(hass)

    add.assert_called_once()


def test_review_card_labels_every_review_reason() -> None:
    """The review card has its own label for each reason Parcels stores.

    A reason without one would show as its code made readable.
    """
    source = STRINGS.read_text(encoding="utf-8")
    block = source.split("export const REASON_LABELS", 1)[1].split("};", 1)[0]
    labels = dict(re.findall(r'^\s*(\w+): "([^"]+)",$', block, re.MULTILINE))
    reasons = [
        value for name, value in vars(const).items() if name.startswith("REASON_")
    ]
    assert len(set(reasons)) == len(reasons)
    assert set(reasons) <= set(labels)
    assert len({labels[reason] for reason in reasons}) == len(reasons)


def test_review_card_explains_every_ai_note() -> None:
    """The card explains each note on an AI answer in one line, as the docs do.

    A note without one would show as its bare code.
    """
    notes = {
        value for name, value in vars(validate).items() if name.startswith("NOTE_")
    }
    source = STRINGS.read_text(encoding="utf-8")
    block = source.split("export const NOTE_MEANINGS", 1)[1].split("};", 1)[0]
    meanings = {
        code: text.replace('\\"', '"')
        for code, text in re.findall(
            r'^\s*(\w+): "((?:[^"\\]|\\.)+)",$', block, re.MULTILINE
        )
    }
    docs = BENCHMARK.read_text(encoding="utf-8")
    section = docs.split("\n### Notes\n", 1)[1].split("\n## ", 1)[0]
    documented = dict(re.findall(r"^\| `(\w+)` \| (.+) \|$", section, re.MULTILINE))
    assert set(meanings) == notes
    assert meanings == documented


def _failed_check_codes() -> set[str]:
    """Return the code of every check the validator can fail.

    Most codes are written out; the rest are a field's name plus a suffix.
    """
    source = Path(validate.__file__).read_text(encoding="utf-8")
    codes = set(re.findall(r'self\.error\("(\w+)"\)', source))
    codes |= set(re.findall(r'Validation\(None, \("(\w+)",\)\)', source))
    built = set(re.findall(r'self\.error\(f"\{(\w+)\}(\w+)"\)', source))
    passed = set(re.findall(r"self\.error\((\w+)\)", source))
    assert built == {
        ("name", "_cut"),
        ("field", "_unparsed"),
        ("field", "_out_of_range"),
    }
    assert passed == {"reason"}
    codes |= {
        f"{name}_cut"
        for name, cap in ANSWER_CAPS.items()
        if "max_length" in cap and name != "items"
    }
    dates = ("eta_start", "eta_end")
    codes |= {f"{field}_unparsed" for field in (*dates, "window_start", "window_end")}
    codes |= {f"{field}_out_of_range" for field in dates}
    codes |= set(re.findall(r'return "(tracking_is_\w+)"', source))
    return codes


def test_review_card_explains_every_failed_check() -> None:
    """The card explains each failed check in one line, as the docs do.

    A check without one would show as its bare code.
    """
    source = STRINGS.read_text(encoding="utf-8")
    block = source.split("export const CHECK_MEANINGS", 1)[1].split("};", 1)[0]
    meanings = {
        code: text.replace('\\"', '"')
        for code, text in re.findall(
            r'^\s*(\w+): "((?:[^"\\]|\\.)+)",$', block, re.MULTILINE
        )
    }
    docs = BENCHMARK.read_text(encoding="utf-8")
    section = docs.split("\n## Check codes\n", 1)[1].split("\n### ", 1)[0]
    documented = {
        code: text
        for codes, text in re.findall(
            r"^\| (`\w+`(?:, `\w+`)*) \| (.+) \|$", section, re.MULTILINE
        )
        for code in re.findall(r"`(\w+)`", codes)
    }
    assert set(meanings) == _failed_check_codes()
    assert meanings == documented
