"""The polling coordinator of a mailbox.

Each refresh asks the mail API for e-mails added since the stored cursor and
hands them to the engine. Large first syncs are read in rounds; the cursor is
saved after every round, so a restart continues where the sync stopped.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .ai_worker import error_location
from .const import (
    CONF_FOLDERS,
    CONF_INTERVAL_MINUTES,
    CONF_LOOKBACK_DAYS,
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_LOOKBACK_DAYS,
    DOMAIN,
)
from .mail.errors import (
    MailApiDisabled,
    MailAuthError,
    MailCursorExpired,
    MailError,
    MailNoMailbox,
    MailRateLimited,
)

if TYPE_CHECKING:
    from .engine import MailboxRuntime, ParcelsEngine

_LOGGER = logging.getLogger(__name__)

# Sync rounds per refresh; a mailbox with more new e-mails continues soon.
MAX_ROUNDS = 10
FOLLOW_UP = timedelta(seconds=30)
BACKOFF_MAX = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class MailboxStatus:
    """The result of the last successful check of a mailbox."""

    last_sync: datetime
    # E-mails the API returned; most are filtered out before download.
    messages: int
    # True once the first sync read the whole lookback period.
    synced: bool


class MailboxCoordinator(DataUpdateCoordinator[MailboxStatus]):
    """Checks one mailbox for new e-mails."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, engine: ParcelsEngine, mailbox: MailboxRuntime
    ) -> None:
        """Initialise the coordinator of a loaded mailbox."""
        options = mailbox.entry.options
        minutes = int(options.get(CONF_INTERVAL_MINUTES) or DEFAULT_INTERVAL_MINUTES)
        self._interval = timedelta(minutes=max(1, minutes))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=mailbox.entry,
            name=f"{DOMAIN} mailbox",
            update_interval=self._interval,
            always_update=False,
        )
        self.engine = engine
        self.mailbox = mailbox
        self.failures = 0
        self.last_error: str | None = None
        # A refresh asked for during a long sync waits for it to finish.
        self._sync_lock = asyncio.Lock()

    async def _async_update_data(self) -> MailboxStatus:
        """Read new e-mails and process them."""
        if not self.engine.started:
            # The hub is reloading; this mailbox is reloaded right after.
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="hub_not_loaded"
            )
        try:
            async with self._sync_lock:
                status = await self._async_sync()
        except ConfigEntryAuthFailed:
            self._failed("auth")
            raise
        except MailRateLimited as err:
            self._failed(type(err).__name__)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="mailbox_rate_limited",
                retry_after=self._backoff(err.retry_after),
            ) from err
        except MailCursorExpired as err:
            # Start over from the lookback period; the engine skips e-mails
            # it has seen.
            self.engine.data.cursors.pop(self.mailbox.entry_id, None)
            self._failed(type(err).__name__)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="mailbox_sync_failed",
                translation_placeholders={"error": str(err) or type(err).__name__},
                retry_after=FOLLOW_UP.total_seconds(),
            ) from err
        except (MailNoMailbox, MailApiDisabled) as err:
            self._failed(type(err).__name__)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key=(
                    "mailbox_no_mailbox"
                    if isinstance(err, MailNoMailbox)
                    else "mailbox_api_disabled"
                ),
                retry_after=self._backoff(None),
            ) from err
        except MailError as err:
            self._failed(type(err).__name__)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="mailbox_sync_failed",
                translation_placeholders={"error": str(err) or type(err).__name__},
                retry_after=self._backoff(None),
            ) from err
        except Exception as err:
            # Never let an exception message carry e-mail text into the log.
            location = error_location(err)
            self._failed(location)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="mailbox_sync_failed",
                translation_placeholders={"error": location},
                retry_after=self._backoff(None),
            ) from None
        self.failures = 0
        self.last_error = None
        return status

    async def _async_sync(self) -> MailboxStatus:
        engine = self.engine
        mailbox = self.mailbox
        entry_id = mailbox.entry_id
        options = mailbox.entry.options
        lookback = timedelta(
            days=int(options.get(CONF_LOOKBACK_DAYS) or DEFAULT_LOOKBACK_DAYS)
        )
        folders = tuple(options.get(CONF_FOLDERS) or ())
        first_sync = not engine.is_synced(entry_id)
        count = 0
        complete = False
        more = False
        engine.begin_sync(entry_id)
        try:
            for _ in range(MAX_ROUNDS):
                if not engine.started:
                    break
                result = await mailbox.client.async_sync(
                    engine.data.cursors.get(entry_id),
                    lookback=lookback,
                    folders=folders,
                )
                count += len(result.messages)
                await engine.async_process_mail(
                    mailbox, result.messages, first_sync=first_sync
                )
                # Only advance after every e-mail of the round was handled.
                engine.data.cursors[entry_id] = result.cursor
                engine.async_schedule_save()
                if result.complete:
                    complete = True
                    break
            more = not complete
        except MailAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="mailbox_auth_failed",
                translation_placeholders={"address": mailbox.address},
            ) from err
        finally:
            # A failed sync doesn't hold up reconciling; it retries later.
            engine.end_sync(entry_id, more=more)
        if complete and first_sync:
            engine.mark_synced(entry_id)
        self.update_interval = self._interval if complete else FOLLOW_UP
        return MailboxStatus(
            last_sync=dt_util.utcnow(),
            messages=count,
            synced=engine.is_synced(entry_id),
        )

    def _failed(self, error: str) -> None:
        self.failures += 1
        self.last_error = error
        self.update_interval = self._interval

    def _backoff(self, minimum: float | None) -> float:
        """Return seconds until the next try: doubling, up to an hour."""
        base = self._interval.total_seconds()
        delay = min(base * 2 ** max(0, self.failures - 1), BACKOFF_MAX.total_seconds())
        return max(delay, minimum or 0.0)

    def diagnostics(self) -> dict[str, object]:
        """Return the sync state for diagnostics, without addresses."""
        data = self.data
        return {
            "last_update_success": self.last_update_success,
            "last_sync": data.last_sync.isoformat() if data else None,
            "synced": self.engine.is_synced(self.mailbox.entry_id),
            "failures": self.failures,
            "last_error": self.last_error,
            "interval_minutes": self._interval.total_seconds() / 60,
        }
