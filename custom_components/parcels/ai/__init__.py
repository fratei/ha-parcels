"""Optional local AI extraction through an Ollama AI task.

Only an Ollama model on the Home Assistant host may read e-mail text
(``safety``). The model gets fixed instructions and one e-mail as labelled
untrusted input (``prompt``); its answer is treated as untrusted and only
checked values are kept, with a confidence computed in code (``validate``).
``client`` runs the AI task through the Python API and keeps e-mail text
and answers out of the log.
"""

from __future__ import annotations

from .client import (
    AIBadOutput,
    AIError,
    AIRefused,
    AITimeout,
    AIUnavailable,
    async_extract,
    install_log_filter,
)
from .safety import AICheck, async_check_ai_task
from .validate import Validation, validate_output

__all__ = [
    "AIBadOutput",
    "AICheck",
    "AIError",
    "AIRefused",
    "AITimeout",
    "AIUnavailable",
    "Validation",
    "async_check_ai_task",
    "async_extract",
    "install_log_filter",
    "validate_output",
]
