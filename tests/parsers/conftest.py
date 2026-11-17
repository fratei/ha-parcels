"""Shared fixtures for the parser tests.

Fixture e-mails live in ``tests/fixtures/emails/<group>/<name>.eml``; load
them with the ``load_eml`` fixture. All data in them must be synthetic:
people such as "Alex Doe" or "Sam Example", addresses such as
``alex@example.com``, streets such as "Rua Exemplo 1", made-up but
format-valid tracking numbers. Real merchant and carrier brands and their
domains are fine.

Conventions for ``.eml`` fixtures (LF line endings are fine):

- ``Return-Path`` with the bounce address, then the provider's
  Authentication-Results header *topmost* (above any other
  Authentication-Results header), in Gmail style, e.g.::

      Authentication-Results: mx.google.com;
             dkim=pass header.i=@amazon.es header.s=sel1 header.b=AbCd1234;
             spf=pass (google.com: domain of bounces@bounces.amazon.es
       designates 192.0.2.10 as permitted sender) smtp.mailfrom=bounces@bounces.amazon.es;
             dmarc=pass (p=QUARANTINE sp=QUARANTINE dis=NONE) header.from=amazon.es

- ``From``, ``To: Alex Doe <alex@example.com>``, ``Subject`` (RFC 2047
  encoded-words such as ``=?UTF-8?Q?...?=`` for non-ASCII text, or raw
  UTF-8), ``Date`` (RFC 5322, with a zone), a synthetic ``Message-ID``
  such as ``<20261117091200.ab12@mail.example.com>`` and
  ``MIME-Version: 1.0``.
- A ``multipart/alternative`` body with a ``text/plain`` and a
  ``text/html`` part, each ``charset=UTF-8`` with
  ``Content-Transfer-Encoding: quoted-printable`` or ``8bit``. The HTML
  part is the one that is parsed.

``load_eml`` uses ``normalize.message_from_bytes`` with the file name as
``provider_id``; ``verdict_for`` runs ``auth.verify_sender`` on a message.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from custom_components.parcels.parsers.auth import verify_sender
from custom_components.parcels.parsers.base import MailMessage, SenderVerdict
from custom_components.parcels.parsers.normalize import message_from_bytes

EMAIL_FIXTURES = Path(__file__).parent.parent / "fixtures" / "emails"
GRAPH_FIXTURES = Path(__file__).parent.parent / "fixtures" / "graph"


@pytest.fixture
def tz() -> ZoneInfo:
    """Return the local time zone used by the parser tests."""
    return ZoneInfo("Europe/Lisbon")


@pytest.fixture
def load_eml() -> Callable[..., MailMessage]:
    """Return a loader for ``.eml`` fixtures, relative to ``fixtures/emails``."""

    def load(
        relative_path: str,
        *,
        mailbox: str = "alex@example.com",
        provider: str = "google",
    ) -> MailMessage:
        path = EMAIL_FIXTURES / relative_path
        return message_from_bytes(
            path.read_bytes(),
            mailbox=mailbox,
            provider_id=path.name,
            provider=provider,
        )

    return load


@pytest.fixture
def verdict_for() -> Callable[..., SenderVerdict]:
    """Return a helper that verifies the sender of a message."""

    def verdict(message: MailMessage, trusted: Iterable[str] = ()) -> SenderVerdict:
        return verify_sender(message, trusted)

    return verdict
