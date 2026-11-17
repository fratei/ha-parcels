"""Tests for the check that only a local Ollama model reads e-mail."""

from __future__ import annotations

import socket
from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.parcels.ai.safety import (
    AICheck,
    async_check_ai_task,
    host_from_url,
    is_cloud_model,
)

from .common import LOCAL_MODEL, add_ai_task


def _addrinfo(*addresses: str) -> list[tuple[Any, ...]]:
    """Return what ``socket.getaddrinfo`` returns for ``addresses``."""
    return [
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, 0, 0, 0))
        if ":" in address
        else (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))
        for address in addresses
    ]


@pytest.mark.parametrize(
    ("url", "host"),
    [
        ("http://172.30.33.4:11434", "172.30.33.4"),
        ("http://172.30.32.1:11434", "172.30.32.1"),
        ("http://localhost:11434", "localhost"),
        ("http://LOCALHOST.:11434/", "localhost"),
        ("http://127.0.0.1:11434", "127.0.0.1"),
        ("http://[::1]:11434", "::1"),
        ("172.30.33.4:11434", "172.30.33.4"),
    ],
)
async def test_local_ollama_is_allowed(
    hass: HomeAssistant, url: str, host: str
) -> None:
    """An Ollama model on the HA host or the Supervisor network may read mail."""
    entity_id = add_ai_task(hass, url=url)
    with patch("socket.getaddrinfo") as getaddrinfo:
        check = await async_check_ai_task(hass, entity_id)
    assert check == AICheck(ok=True, reason="ok", model=LOCAL_MODEL, host=host)
    getaddrinfo.assert_not_called()


async def test_subentry_found_by_unique_id(hass: HomeAssistant) -> None:
    """Entities registered without a subentry id use their unique id."""
    entity_id = add_ai_task(hass, link_subentry=False)
    check = await async_check_ai_task(hass, entity_id)
    assert check.ok
    assert check.model == LOCAL_MODEL


@pytest.mark.parametrize(
    "addresses",
    [("172.30.33.7",), ("127.0.0.1", "::1"), ("::ffff:172.30.32.9",)],
)
async def test_host_name_resolving_to_local_addresses(
    hass: HomeAssistant, addresses: tuple[str, ...]
) -> None:
    """A host name is allowed when every address it resolves to is local."""
    entity_id = add_ai_task(hass, url="http://local-ollama:11434")
    with patch("socket.getaddrinfo", return_value=_addrinfo(*addresses)) as resolve:
        check = await async_check_ai_task(hass, entity_id)
    assert check == AICheck(
        ok=True, reason="ok", model=LOCAL_MODEL, host="local-ollama"
    )
    assert resolve.call_args.args[0] == "local-ollama"


@pytest.mark.parametrize(
    ("url", "addresses"),
    [
        ("http://192.168.1.20:11434", None),
        ("https://203.0.113.7", None),
        ("http://[2001:db8::7]:11434", None),
        ("http://ollama.example.com:11434", ("203.0.113.7",)),
        ("http://ollama.lan:11434", ("192.168.1.20",)),
        ("http://mixed.lan:11434", ("127.0.0.1", "192.168.1.20")),
    ],
)
async def test_remote_host_is_refused(
    hass: HomeAssistant, url: str, addresses: tuple[str, ...] | None
) -> None:
    """A LAN or internet host would send e-mail text off the HA host."""
    entity_id = add_ai_task(hass, url=url)
    with patch("socket.getaddrinfo", return_value=_addrinfo(*(addresses or ()))):
        check = await async_check_ai_task(hass, entity_id)
    assert not check.ok
    assert check.reason == "remote_host"
    assert check.model == LOCAL_MODEL
    assert check.host == host_from_url(url)


@pytest.mark.parametrize(
    "result",
    [socket.gaierror(socket.EAI_NONAME, "unknown"), OSError("down"), []],
)
async def test_unresolvable_host_is_refused(
    hass: HomeAssistant, result: Exception | list[Any]
) -> None:
    """A host name that doesn't resolve can't be shown to be local."""
    entity_id = add_ai_task(hass, url="http://ollama.invalid:11434")
    with patch("socket.getaddrinfo") as getaddrinfo:
        if isinstance(result, Exception):
            getaddrinfo.side_effect = result
        else:
            getaddrinfo.return_value = result
        check = await async_check_ai_task(hass, entity_id)
    assert check == AICheck(
        ok=False, reason="unresolvable", model=LOCAL_MODEL, host="ollama.invalid"
    )


async def test_missing_url_is_refused(hass: HomeAssistant) -> None:
    """Without a server URL the host can't be checked."""
    entity_id = add_ai_task(hass, url=None)
    check = await async_check_ai_task(hass, entity_id)
    assert check == AICheck(ok=False, reason="unresolvable", model=LOCAL_MODEL)


@pytest.mark.parametrize("model", ["gpt-oss:120b-cloud", "x:cloud", "mycloud:latest"])
async def test_cloud_model_is_refused(hass: HomeAssistant, model: str) -> None:
    """Ollama cloud models run on Ollama's servers, not on the HA host."""
    entity_id = add_ai_task(hass, model=model)
    with patch("socket.getaddrinfo") as getaddrinfo:
        check = await async_check_ai_task(hass, entity_id)
    assert check == AICheck(
        ok=False, reason="cloud_model", model=model, host="localhost"
    )
    getaddrinfo.assert_not_called()


async def test_not_ollama_is_refused(hass: HomeAssistant) -> None:
    """An AI task of another integration, such as OpenAI, is refused."""
    entity_id = add_ai_task(hass, platform="openai_conversation", object_id="openai")
    check = await async_check_ai_task(hass, entity_id)
    assert check == AICheck(ok=False, reason="not_ollama")


async def test_not_found_is_refused(hass: HomeAssistant) -> None:
    """An entity that isn't in the entity registry is refused."""
    check = await async_check_ai_task(hass, "ai_task.missing")
    assert check == AICheck(ok=False, reason="not_found")


async def test_not_ai_task_is_refused(hass: HomeAssistant) -> None:
    """An Ollama conversation agent isn't an AI task."""
    entity_id = add_ai_task(hass, domain="conversation")
    check = await async_check_ai_task(hass, entity_id)
    assert check == AICheck(ok=False, reason="not_ai_task")


async def test_entry_of_another_domain_is_refused(hass: HomeAssistant) -> None:
    """The entity's config entry must be an Ollama entry."""
    entity_id = add_ai_task(hass, entry_domain="custom_llm")
    check = await async_check_ai_task(hass, entity_id)
    assert check == AICheck(ok=False, reason="no_entry")


async def test_entity_without_entry_is_refused(hass: HomeAssistant) -> None:
    """An entity without a config entry has no server URL or model."""
    entity = er.async_get(hass).async_get_or_create("ai_task", "ollama", "orphan")
    check = await async_check_ai_task(hass, entity.entity_id)
    assert check == AICheck(ok=False, reason="no_entry")


async def test_subentry_without_model_is_refused(hass: HomeAssistant) -> None:
    """The model is needed to rule out cloud models."""
    entity_id = add_ai_task(hass, model=None)
    check = await async_check_ai_task(hass, entity_id)
    assert check == AICheck(ok=False, reason="no_model", host="localhost")


@pytest.mark.parametrize(
    ("model", "cloud"),
    [
        ("gpt-oss:120b-cloud", True),
        ("deepseek-v3.1:671b-cloud", True),
        ("x:cloud", True),
        ("mycloud", True),
        ("user/mycloud:latest", True),
        ("qwen3:4b-instruct", False),
        ("gemma4:e4b", False),
        ("llama3.2", False),
        ("cloudy:7b", False),
        ("registry.example.com:5000/qwen3:4b", False),
    ],
)
def test_is_cloud_model(model: str, cloud: bool) -> None:
    """A name or tag ending in "cloud" marks an Ollama cloud model."""
    assert is_cloud_model(model) is cloud
