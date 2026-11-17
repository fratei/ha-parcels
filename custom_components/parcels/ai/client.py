"""Ask the local AI task to read one e-mail, then check its answer.

``async_extract`` re-runs the safety check, then calls the Python API
``ai_task.async_generate_data`` with the fixed instructions, the e-mail as
labelled untrusted input and the output structure. It never uses the
``ai_task.generate_data`` action: the recorder would store the e-mail text
in the ``call_service`` event. Calls run one at a time, and the time limit
starts when a call's turn comes, because the Ollama server answers one
request at a time.

Where the e-mail text lives during a call (Home Assistant 2026.11):

* In memory only. The AI task opens a new chat session and keeps a chat log
  (``hass.data["conversation_chat_logs"]``) with the system prompt, the
  instructions with the e-mail text, and the model's answer. The session
  expires five minutes after its last use and is cleaned up by a timer that
  runs about every five minutes, so the log stays for up to ten minutes.
  Administrators can watch chat logs through the websocket commands
  ``conversation/chat_log/subscribe`` and ``subscribe_index`` meanwhile.
* The Ollama server on the Home Assistant host receives it over HTTP.
* Nothing is written to the database: the AI task entity's state is only
  the time of its last task, and no service call event is fired.
  Conversation debug traces aren't recorded for AI tasks.
* Logs: the Ollama, AI task and conversation integrations log prompts and
  answers at debug level, and Ollama logs the whole answer as an error when
  it isn't valid JSON. ``install_log_filter`` redacts those records.

Exception messages never contain e-mail text or model output.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import tzinfo
import logging
import re
from typing import Final

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.hass_dict import HassKey

from ..const import AI_TIMEOUT, DOMAIN
from ..parsers.base import MailMessage
from .prompt import AI_STRUCTURE, BEGIN_MARKER, END_MARKER, build_prompt
from .safety import AI_TASK_DOMAIN, async_check_ai_task
from .validate import Validation, validate_output

_LOGGER = logging.getLogger(__name__)

TASK_NAME: Final = "parcels"
REDACTED: Final = "[redacted]"

# Loggers that may log prompts or answers: the AI task, Ollama, and the
# conversation chat log that the AI task uses.
LOGGER_NAMES: Final[tuple[str, ...]] = (
    "homeassistant.components.ai_task",
    "homeassistant.components.conversation",
    "homeassistant.components.conversation.agent_manager",
    "homeassistant.components.conversation.chat_log",
    "homeassistant.components.conversation.default_agent",
    "homeassistant.components.conversation.services",
    "homeassistant.components.conversation.util",
    "homeassistant.components.ollama",
    "homeassistant.components.ollama.ai_task",
    "homeassistant.components.ollama.entity",
)

DATA_AI_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_ai_lock")
DATA_LOG_FILTER: HassKey[_FilterInstall] = HassKey(f"{DOMAIN}_ai_log_filter")

# True while this task (and the tasks it starts) runs an AI call.
_IN_CALL: ContextVar[bool] = ContextVar(f"{DOMAIN}_ai_call", default=False)

_FORMAT_SPEC_RE = re.compile(
    r"%(?:%|(?:\([^)]*\))?[#0 +\-]*(?:\*|\d+)?(?:\.(?:\*|\d+))?[hlL]?[a-zA-Z])"
)


class AIError(HomeAssistantError):
    """The AI couldn't read an e-mail."""


class AIUnavailable(AIError):
    """The AI task or the Ollama app isn't available."""


class AITimeout(AIError):
    """The AI took too long."""


class AIRefused(AIError):
    """The AI task may not read e-mail; ``reason`` is a safety reason code."""

    def __init__(self, reason: str) -> None:
        """Store the reason code."""
        super().__init__(f"The AI task may not read e-mail: {reason}")
        self.reason = reason


class AIBadOutput(AIError):
    """The AI task's answer can't be used; ``errors`` are validation codes."""

    def __init__(self, errors: tuple[str, ...] = ()) -> None:
        """Store the validation error codes."""
        detail = f" ({', '.join(errors)})" if errors else ""
        super().__init__(f"The AI task returned no usable answer{detail}")
        self.errors = errors


async def async_extract(
    hass: HomeAssistant, entity_id: str, message: MailMessage, tz: tzinfo
) -> Validation:
    """Ask the AI task to read one e-mail and check its answer.

    Returns a validation with a result. Raises ``AIRefused`` when the safety
    check fails, ``AIUnavailable`` when the AI task or Ollama can't be used,
    ``AITimeout`` after ``AI_TIMEOUT`` and ``AIBadOutput`` when the answer
    is unusable. Installs the log filter for the rest of the run if it
    isn't installed yet.
    """
    if DATA_LOG_FILTER not in hass.data:
        install_log_filter(hass)
    lock = hass.data.setdefault(DATA_AI_LOCK, asyncio.Lock())
    async with lock:
        check = await async_check_ai_task(hass, entity_id)
        if not check.ok:
            raise AIRefused(check.reason)
        state = hass.states.get(entity_id)
        if (
            AI_TASK_DOMAIN not in hass.config.components
            or state is None
            or state.state == STATE_UNAVAILABLE
        ):
            raise AIUnavailable("The AI task isn't available")
        data = await _async_generate(hass, entity_id, build_prompt(message, tz))
    if not isinstance(data, Mapping):
        raise AIBadOutput(("not_a_mapping",))
    validation = validate_output(data, message, tz)
    if validation.result is None:
        raise AIBadOutput(validation.errors)
    return validation


async def _async_generate(hass: HomeAssistant, entity_id: str, prompt: str) -> object:
    """Run the AI task and return its raw answer."""
    from homeassistant.components import ai_task

    token = _IN_CALL.set(True)
    try:
        async with asyncio.timeout(AI_TIMEOUT.total_seconds()):
            result = await ai_task.async_generate_data(
                hass,
                task_name=TASK_NAME,
                entity_id=entity_id,
                instructions=prompt,
                structure=AI_STRUCTURE,
            )
    except TimeoutError:
        raise AITimeout("The AI task took too long") from None
    except Exception as err:
        # HomeAssistantError from the task, KeyError when the AI task isn't
        # set up, and ConnectionError or HTTP errors from the Ollama client
        # that its integration doesn't wrap. Their messages may quote the
        # server or the answer, so only the type is logged.
        _LOGGER.debug("AI task failed: %s", type(err).__name__)
        raise AIUnavailable("The AI task failed") from None
    finally:
        _IN_CALL.reset(token)
    return result.data


def _redact_template(template: str) -> str:
    """Replace every %-placeholder of a log message by REDACTED."""
    return _FORMAT_SPEC_RE.sub(
        lambda match: "%" if match.group(0) == "%%" else REDACTED, template
    )


def _mentions_email(record: logging.LogRecord) -> bool:
    """Return True when a log record contains a prompt of this integration."""
    values: list[object] = [record.msg]
    if isinstance(record.args, Mapping):
        values.extend(record.args.values())
    elif record.args:
        values.extend(record.args)
    for value in values:
        text = str(value)
        if BEGIN_MARKER in text or END_MARKER in text:
            return True
    return False


def redact_record(record: logging.LogRecord) -> None:
    """Remove every value of a log record, keeping its fixed message text.

    A message without arguments may itself be built from content, so it is
    replaced as a whole. Exception details are dropped; their type is kept.
    """
    template = record.msg if isinstance(record.msg, str) else ""
    message = _redact_template(template) if record.args and template else REDACTED
    if record.exc_info and record.exc_info[0] is not None:
        message = f"{message} ({record.exc_info[0].__name__})"
    record.msg = message
    record.args = ()
    record.exc_info = None
    record.exc_text = None
    record.stack_info = None


class _RedactFilter(logging.Filter):
    """Redact log records written during an AI call or containing a prompt."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the record when needed; drop it if that fails."""
        try:
            if _IN_CALL.get() or _mentions_email(record):
                redact_record(record)
        except Exception:
            return False
        return True


@dataclass(slots=True)
class _FilterInstall:
    """The installed filter and the tokens of those who installed it."""

    log_filter: _RedactFilter = field(default_factory=_RedactFilter)
    tokens: set[object] = field(default_factory=set)


def install_log_filter(hass: HomeAssistant) -> Callable[[], None]:
    """Redact e-mail text and AI answers from the AI integrations' logs.

    Installing again shares the same filter; it is removed when every
    returned remover has been called.
    """
    install = hass.data.get(DATA_LOG_FILTER)
    if install is None:
        install = _FilterInstall()
        for name in LOGGER_NAMES:
            logging.getLogger(name).addFilter(install.log_filter)
        hass.data[DATA_LOG_FILTER] = install
    token = object()
    install.tokens.add(token)

    def remove() -> None:
        if token not in install.tokens:
            return
        install.tokens.discard(token)
        if install.tokens:
            return
        for name in LOGGER_NAMES:
            logging.getLogger(name).removeFilter(install.log_filter)
        if hass.data.get(DATA_LOG_FILTER) is install:
            hass.data.pop(DATA_LOG_FILTER)

    return remove
