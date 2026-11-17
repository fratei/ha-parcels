"""Tests for the call to the local AI task and the log filter."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import timedelta
import logging
import sys
import types
from typing import Any

from homeassistant.const import EVENT_CALL_SERVICE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant.common import async_capture_events

from custom_components.parcels.ai import client
from custom_components.parcels.ai.client import (
    DATA_LOG_FILTER,
    LOGGER_NAMES,
    REDACTED,
    AIBadOutput,
    AIRefused,
    AITimeout,
    AIUnavailable,
    async_extract,
    install_log_filter,
    redact_record,
)
from custom_components.parcels.ai.prompt import AI_STRUCTURE, build_prompt
from custom_components.parcels.ai.validate import validate_output
from custom_components.parcels.const import MailKind

from .common import TZ, add_ai_task, answer, make_message
from .conftest import FakeResult

SECRET = "Rua Secreta 99"
S10 = "RR123456785PT"
OLLAMA_LOGGER = "homeassistant.components.ollama.ai_task"


@pytest.fixture(autouse=True)
def remove_log_filter(hass: HomeAssistant) -> Iterator[None]:
    """Take the filter off the global loggers after each test."""
    yield
    install = hass.data.pop(DATA_LOG_FILTER, None)
    if install is not None:
        for name in LOGGER_NAMES:
            logging.getLogger(name).removeFilter(install.log_filter)


def loaded_ai_task(hass: HomeAssistant, *, loaded: bool = True, **kwargs: Any) -> str:
    """Add a local Ollama AI task entity with a state and return its id."""
    entity_id = add_ai_task(hass, **kwargs)
    if loaded:
        hass.config.components.add("ai_task")
    hass.states.async_set(entity_id, "2026-11-18T09:00:00+00:00")
    return entity_id


def secret_message() -> Any:
    """Return an e-mail whose text must never leave the call."""
    return make_message(
        f"Objeto {S10} enviado para {SECRET}.", subject=f"Envio para {SECRET}"
    )


async def test_calls_python_api(
    hass: HomeAssistant, fake_ai_task: types.ModuleType
) -> None:
    """The AI task's Python API gets the prompt and structure, not the action."""
    entity_id = loaded_ai_task(hass)
    data = answer(kind="shipped", tracking_numbers=[S10])
    fake_ai_task.async_generate_data.return_value = FakeResult("c1", data)
    events = async_capture_events(hass, EVENT_CALL_SERVICE)
    message = secret_message()

    validation = await async_extract(hass, entity_id, message, TZ)

    fake_ai_task.async_generate_data.assert_awaited_once_with(
        hass,
        task_name="parcels",
        entity_id=entity_id,
        instructions=build_prompt(message, TZ),
        structure=AI_STRUCTURE,
    )
    assert validation == validate_output(data, message, TZ)
    assert validation.result is not None
    assert validation.result.kind is MailKind.SHIPPED
    assert events == []


async def test_refused_check(
    hass: HomeAssistant, fake_ai_task: types.ModuleType
) -> None:
    """A model that may not read e-mail is never called."""
    entity_id = loaded_ai_task(hass, model="gpt-oss:120b-cloud")

    with pytest.raises(AIRefused) as err:
        await async_extract(hass, entity_id, secret_message(), TZ)

    assert err.value.reason == "cloud_model"
    with pytest.raises(AIRefused, match="not_found"):
        await async_extract(hass, "ai_task.missing", secret_message(), TZ)
    fake_ai_task.async_generate_data.assert_not_awaited()


@pytest.mark.parametrize("problem", ["unavailable", "no_state", "not_loaded"])
async def test_ai_task_unavailable(
    hass: HomeAssistant, fake_ai_task: types.ModuleType, problem: str
) -> None:
    """An unavailable entity or AI task integration isn't called."""
    entity_id = loaded_ai_task(hass, loaded=problem != "not_loaded")
    if problem == "unavailable":
        hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    elif problem == "no_state":
        hass.states.async_remove(entity_id)

    with pytest.raises(AIUnavailable):
        await async_extract(hass, entity_id, secret_message(), TZ)

    fake_ai_task.async_generate_data.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        HomeAssistantError(f"Ollama answered: {SECRET}"),
        ConnectionError(f"Connection refused: {SECRET}"),
        KeyError(SECRET),
    ],
)
async def test_task_errors(
    hass: HomeAssistant,
    fake_ai_task: types.ModuleType,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """Errors of the task or Ollama mean the AI is unavailable."""
    caplog.set_level(logging.DEBUG)
    entity_id = loaded_ai_task(hass)
    fake_ai_task.async_generate_data.side_effect = error

    with pytest.raises(AIUnavailable) as err:
        await async_extract(hass, entity_id, secret_message(), TZ)

    assert SECRET not in str(err.value)
    assert err.value.__cause__ is None
    assert err.value.__suppress_context__
    assert SECRET not in caplog.text


async def test_timeout(
    hass: HomeAssistant,
    fake_ai_task: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A task that takes too long times out."""
    monkeypatch.setattr(client, "AI_TIMEOUT", timedelta(milliseconds=20))
    entity_id = loaded_ai_task(hass)

    async def slow(*args: Any, **kwargs: Any) -> FakeResult:
        await asyncio.sleep(10)
        raise AssertionError("not reached")

    fake_ai_task.async_generate_data.side_effect = slow

    with pytest.raises(AITimeout) as err:
        await async_extract(hass, entity_id, secret_message(), TZ)

    assert SECRET not in str(err.value)


async def test_calls_run_one_at_a_time(
    hass: HomeAssistant, fake_ai_task: types.ModuleType
) -> None:
    """A call waits until the previous one has finished."""
    entity_id = loaded_ai_task(hass)
    calls: list[str] = []
    started = asyncio.Event()
    release = asyncio.Event()

    async def generate(hass: HomeAssistant, **kwargs: Any) -> FakeResult:
        calls.append(kwargs["instructions"])
        started.set()
        await release.wait()
        return FakeResult("c", answer(kind="not_parcel"))

    fake_ai_task.async_generate_data.side_effect = generate
    tasks = [
        asyncio.create_task(async_extract(hass, entity_id, make_message(text), TZ))
        for text in ("Primeiro", "Segundo")
    ]
    async with asyncio.timeout(5):
        await started.wait()
    for _ in range(20):
        await asyncio.sleep(0)
    assert len(calls) == 1

    release.set()
    results = await asyncio.gather(*tasks)

    assert all(result.result is not None for result in results)
    assert "Primeiro" in calls[0]
    assert "Segundo" in calls[1]


async def test_time_limit_starts_at_turn(
    hass: HomeAssistant,
    fake_ai_task: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Waiting for an earlier call doesn't count against the time limit."""
    monkeypatch.setattr(client, "AI_TIMEOUT", timedelta(milliseconds=100))
    entity_id = loaded_ai_task(hass)
    calls = 0

    async def generate(hass: HomeAssistant, **kwargs: Any) -> FakeResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.sleep(10)
        return FakeResult("c", answer(kind="not_parcel"))

    fake_ai_task.async_generate_data.side_effect = generate
    first = asyncio.create_task(
        async_extract(hass, entity_id, make_message("Primeiro"), TZ)
    )
    second = asyncio.create_task(
        async_extract(hass, entity_id, make_message("Segundo"), TZ)
    )

    with pytest.raises(AITimeout):
        await first
    validation = await second

    assert validation.result is not None
    assert validation.result.kind is MailKind.NOT_PARCEL


@pytest.mark.parametrize(
    ("data", "errors"),
    [
        (f"Sem JSON: {SECRET}", ("not_a_mapping",)),
        ([SECRET], ("not_a_mapping",)),
        (answer(kind=SECRET), ("kind_invalid",)),
    ],
)
async def test_unusable_answer(
    hass: HomeAssistant,
    fake_ai_task: types.ModuleType,
    data: Any,
    errors: tuple[str, ...],
) -> None:
    """An unusable answer raises AIBadOutput without quoting it."""
    entity_id = loaded_ai_task(hass)
    fake_ai_task.async_generate_data.return_value = FakeResult("c", data)

    with pytest.raises(AIBadOutput) as err:
        await async_extract(hass, entity_id, secret_message(), TZ)

    assert err.value.errors == errors
    assert SECRET not in str(err.value)


async def test_log_filter_redacts_during_call(
    hass: HomeAssistant,
    fake_ai_task: types.ModuleType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """What Ollama logs during a call never reaches the log."""
    caplog.set_level(logging.DEBUG)
    entity_id = loaded_ai_task(hass)
    ollama = logging.getLogger(OLLAMA_LOGGER)
    entity = logging.getLogger("homeassistant.components.ollama.entity")

    async def log_debug(text: str) -> None:
        entity.debug(f"Response {text}")

    async def generate(hass: HomeAssistant, **kwargs: Any) -> FakeResult:
        response = f'{{"kind": "shipped", "merchant": "{SECRET}"'
        await asyncio.create_task(log_debug(response))
        ollama.error(
            "Failed to parse JSON response: %s. Response: %s",
            ValueError(response),
            response,
        )
        raise HomeAssistantError("Error with Ollama structured response")

    fake_ai_task.async_generate_data.side_effect = generate

    with pytest.raises(AIUnavailable):
        await async_extract(hass, entity_id, secret_message(), TZ)

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("homeassistant.components.ollama")
    ]
    assert messages == [
        REDACTED,
        f"Failed to parse JSON response: {REDACTED}. Response: {REDACTED}",
    ]
    assert SECRET not in caplog.text
    assert DATA_LOG_FILTER in hass.data


async def test_log_filter_outside_calls(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Outside calls, only records that contain a prompt are redacted."""
    caplog.set_level(logging.DEBUG)
    remove = install_log_filter(hass)
    chat_log = logging.getLogger("homeassistant.components.conversation.chat_log")
    ollama = logging.getLogger("homeassistant.components.ollama")

    chat_log.debug("Adding content: %s", build_prompt(secret_message(), TZ))
    ollama.info("Model %s is ready", "qwen3:4b-instruct")
    remove()
    chat_log.debug("Adding content: %s", build_prompt(secret_message(), TZ))

    messages = [record.getMessage() for record in caplog.records]
    assert messages[:2] == [
        f"Adding content: {REDACTED}",
        "Model qwen3:4b-instruct is ready",
    ]
    assert SECRET in messages[2]


async def test_install_log_filter_is_shared(hass: HomeAssistant) -> None:
    """Installing twice shares one filter, removed with the last remover."""
    remove_first = install_log_filter(hass)
    remove_second = install_log_filter(hass)
    log_filter = hass.data[DATA_LOG_FILTER].log_filter
    for name in LOGGER_NAMES:
        assert logging.getLogger(name).filters.count(log_filter) == 1

    remove_first()
    remove_first()
    assert logging.getLogger(OLLAMA_LOGGER).filters.count(log_filter) == 1

    remove_second()
    for name in LOGGER_NAMES:
        assert log_filter not in logging.getLogger(name).filters
    assert DATA_LOG_FILTER not in hass.data


@pytest.mark.parametrize(
    ("msg", "args", "expected"),
    [
        (
            "Response: %s (%d tokens)",
            (SECRET, 12),
            f"Response: {REDACTED} ({REDACTED} tokens)",
        ),
        ("Response: %(text)s", ({"text": SECRET},), f"Response: {REDACTED}"),
        ("100%% of %s", (SECRET,), f"100% of {REDACTED}"),
        (f"Response: {SECRET}", (), REDACTED),
        (ValueError(SECRET), (), REDACTED),
    ],
)
def test_redact_record(msg: Any, args: tuple[Any, ...], expected: str) -> None:
    """Every value of a record is removed; its fixed text is kept."""
    record = logging.LogRecord(OLLAMA_LOGGER, logging.ERROR, "x.py", 1, msg, args, None)
    redact_record(record)
    assert record.getMessage() == expected


def test_redact_record_drops_exception() -> None:
    """Exception details are dropped; their type is kept."""
    try:
        raise ValueError(SECRET)
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        OLLAMA_LOGGER, logging.ERROR, "x.py", 1, "Failed: %s", (SECRET,), exc_info
    )
    redact_record(record)
    assert record.getMessage() == f"Failed: {REDACTED} (ValueError)"
    assert record.exc_info is None
    assert record.exc_text is None
    assert SECRET not in logging.Formatter().format(record)
