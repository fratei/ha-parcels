"""Fixtures for the local AI tests.

No model runs here. The AI task integration can't be imported in the test
environment, so ``fake_ai_task`` installs a stand-in module whose
``async_generate_data`` is a mock; Ollama config entries and AI task
entities are created directly in the registries (see ``common``).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import homeassistant.components
import pytest

from .common import TZ


@dataclass
class FakeResult:
    """Stand-in for ``ai_task.GenDataTaskResult``."""

    conversation_id: str
    data: Any


@pytest.fixture
def tz() -> ZoneInfo:
    """Return the local time zone of the tests."""
    return TZ


@pytest.fixture
def fake_ai_task(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.ModuleType]:
    """Install a stand-in ``homeassistant.components.ai_task`` module.

    Set ``fake_ai_task.async_generate_data.return_value`` (a ``FakeResult``)
    or its ``side_effect`` in a test.
    """
    module = types.ModuleType("homeassistant.components.ai_task")
    module.GenDataTaskResult = FakeResult  # type: ignore[attr-defined]
    module.async_generate_data = AsyncMock(  # type: ignore[attr-defined]
        return_value=FakeResult("conversation-1", {})
    )
    monkeypatch.setattr(homeassistant.components, "ai_task", module, raising=False)
    with patch.dict(sys.modules, {"homeassistant.components.ai_task": module}):
        yield module
