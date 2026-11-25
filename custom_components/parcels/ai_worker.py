"""The local AI queue.

E-mails that the parsers couldn't read with confidence wait here and go to
the AI task one at a time, newest first. The queue keeps only e-mail hashes
and the prepared review item; each e-mail is downloaded again for its call,
and its text only exists in memory during that call.

Limits: one retry after a failed call, at most ``AI_DAILY_LIMIT`` calls a
day, and e-mails still waiting after a day go to "Needs review". While the
AI mode is "suggest", the worker also reads up to ``AI_SHADOW_DAILY_LIMIT``
e-mails a day that a parser already handled, and counts how often the AI
agrees; those results are never applied.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .ai import (
    AIBadOutput,
    AIError,
    AIRefused,
    AITimeout,
    AIUnavailable,
    async_extract,
    install_log_filter,
)
from .const import (
    AI_DAILY_LIMIT,
    AI_FILL_DAILY_LIMIT,
    AI_RETRY_DELAY,
    AI_SHADOW_DAILY_LIMIT,
    CONFIDENCE_APPLY,
    DOMAIN,
    ISSUE_AI_REFUSED,
    ISSUE_AI_UNAVAILABLE,
    REASON_AI_FILL,
    REASON_AI_REJECTED,
    REASON_AI_SUGGESTION,
    REASON_AI_TIMEOUT,
    REASON_AI_UNAVAILABLE,
    REASON_UNKNOWN_FORMAT,
    SIGNAL_AI_UPDATED,
    AIMode,
    MailKind,
)
from .convert import (
    fill_suggestion,
    is_confident,
    merge_fills,
    results_agree,
)
from .models import (
    MessageRecord,
    MessageState,
    ReviewItem,
    Source,
    check_codes,
    dt_from_str,
    dt_to_str,
    new_id,
)
from .parsers import add_details, is_refund, sort_returns
from .parsers.senders import organizational_domain

if TYPE_CHECKING:
    from .ai import Validation
    from .engine import ParcelsEngine
    from .parsers.base import MailMessage, ParseResult

_LOGGER = logging.getLogger(__name__)

# Failed calls before an e-mail goes to review: one retry.
MAX_ATTEMPTS = 2
# E-mails still waiting after this long go to review.
QUEUE_MAX_AGE = timedelta(days=1)
# Longest sleep; changes, new mailboxes and midnight wake the worker sooner.
IDLE_WAIT = timedelta(hours=1)
SHADOW_CANDIDATES = 20
_NEVER = datetime.min.replace(tzinfo=UTC)
STATS_DAYS = 14
STAT_KEYS = (
    "calls",
    "applied",
    "suggested",
    "filtered",
    "rejected",
    "failed",
    "shadow",
    "agree",
    "disagree",
    "fills",
    "filled",
)

STATUS_OFF = "off"
STATUS_IDLE = "idle"
STATUS_BUSY = "busy"
STATUS_PAUSED = "paused"
STATUS_LIMIT = "limit"


def error_location(err: BaseException) -> str:
    """Return where an exception was raised, without its message."""
    tb = err.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if tb is None:
        return type(err).__name__
    code = tb.tb_frame.f_code
    return f"{type(err).__name__} in {code.co_name}:{tb.tb_lineno}"


def _stats_cutoff() -> str:
    """Return the oldest day the counters keep, in Home Assistant's time zone."""
    return (dt_util.now().date() - timedelta(days=STATS_DAYS)).isoformat()


class AIWorker:
    """Sends queued e-mails to the AI task, one at a time."""

    def __init__(self, engine: ParcelsEngine) -> None:
        """Initialise the worker of an engine."""
        self.engine = engine
        self.hass = engine.hass
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._remove_log_filter: Callable[[], None] | None = None
        self._busy: str | None = None
        self._last_error: str | None = None

    # -- State ------------------------------------------------------------

    @property
    def queue(self) -> list[dict[str, Any]]:
        """Return the stored queue entries."""
        queue = self.engine.data.ai.get("queue")
        if not isinstance(queue, list):
            queue = self.engine.data.ai["queue"] = []
        return queue

    @property
    def queue_size(self) -> int:
        """Return the number of e-mails waiting for the AI."""
        return len(self.queue)

    @property
    def status(self) -> str:
        """Return off, idle, busy, paused or limit."""
        engine = self.engine
        if not engine.ai_active:
            return STATUS_OFF
        if self._busy is not None:
            return STATUS_BUSY
        paused = dt_from_str(engine.data.ai.get("paused_until"))
        if paused is not None and paused > dt_util.utcnow():
            return STATUS_PAUSED
        if self.today().get("calls", 0) >= AI_DAILY_LIMIT:
            return STATUS_LIMIT
        return STATUS_IDLE

    def today(self) -> dict[str, int]:
        """Return today's counters, in Home Assistant's time zone."""
        day = self._day("stats")
        for name in STAT_KEYS:
            day.setdefault(name, 0)
        return day

    def _day(self, store: str) -> dict[str, Any]:
        """Return today's entry in a per-day store; a new day drops old ones."""
        days = self.engine.data.ai.get(store)
        if not isinstance(days, dict):
            days = self.engine.data.ai[store] = {}
        key = dt_util.now().date().isoformat()
        day = days.get(key)
        if not isinstance(day, dict):
            day = days[key] = {}
            cutoff = _stats_cutoff()
            for old in [k for k in days if k < cutoff]:
                del days[old]
        return day

    def _recent(self, store: str) -> list[dict[str, Any]]:
        """Return the days of a per-day store within the last STATS_DAYS."""
        days = self.engine.data.ai.get(store)
        if not isinstance(days, dict):
            return []
        cutoff = _stats_cutoff()
        return [
            day for key, day in days.items() if key >= cutoff and isinstance(day, dict)
        ]

    def average_seconds(self) -> float | None:
        """Return how long a call took on average in the last STATS_DAYS days."""
        timing = self._recent("timing")
        calls = sum(int(day.get("calls", 0)) for day in timing)
        seconds = sum(float(day.get("seconds", 0.0)) for day in timing)
        return seconds / calls if calls else None

    def wait_seconds(self) -> int | None:
        """Return about how long the queue will take; None when it can't be told.

        Only while the AI is working through it: not paused, nor at the limit.
        """
        average = self.average_seconds()
        if not self.queue or average is None:
            return None
        if self.status not in (STATUS_IDLE, STATUS_BUSY):
            return None
        return round(len(self.queue) * average)

    def shadow_totals(self) -> tuple[int, int]:
        """Return how often the AI agreed and disagreed with the parsers."""
        agree = disagree = 0
        for day in self._recent("stats"):
            agree += int(day.get("agree", 0))
            disagree += int(day.get("disagree", 0))
        return agree, disagree

    def _count(self, name: str) -> None:
        self.today()[name] += 1
        self.engine.async_schedule_save()

    def _count_call(self, started: float, *, shadow: bool, fill: bool = False) -> None:
        """Count a call that reached the AI task, and how long it took."""
        self._count("calls")
        if shadow:
            self._count("shadow")
        if fill:
            self._count("fills")
        timing = self._day("timing")
        timing["calls"] = int(timing.get("calls", 0)) + 1
        timing["seconds"] = float(timing.get("seconds", 0.0)) + max(
            self.hass.loop.time() - started, 0.0
        )

    # -- Lifecycle --------------------------------------------------------

    @callback
    def async_start(self) -> None:
        """Start the worker in the background."""
        if self._task is not None and not self._task.done():
            return
        queue = self.queue
        queue[:] = [
            entry
            for entry in queue
            if isinstance(entry, dict)
            and isinstance(entry.get("hash"), str)
            and isinstance(entry.get("review"), dict)
        ]
        if self._remove_log_filter is None:
            self._remove_log_filter = install_log_filter(self.hass)
        self._task = self.engine.async_create_task(
            self._async_run(), "parcels ai queue"
        )

    async def async_stop(self) -> None:
        """Stop the worker; a running call is cancelled."""
        if (task := self._task) is not None:
            self._task = None
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._busy = None
        if self._remove_log_filter is not None:
            self._remove_log_filter()
            self._remove_log_filter = None

    @callback
    def wake(self) -> None:
        """Look at the queue again now."""
        self._wake.set()

    async def _async_run(self) -> None:
        while True:
            self._wake.clear()
            try:
                delay = await self._async_step()
            except Exception as err:
                # Only the location: messages could quote an e-mail.
                _LOGGER.error("The AI queue failed (%s)", error_location(err))
                self._set_busy(None)
                delay = AI_RETRY_DELAY.total_seconds()
            if delay <= 0:
                await asyncio.sleep(0)
                continue
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(min(delay, IDLE_WAIT.total_seconds())):
                    await self._wake.wait()

    # -- Queue ------------------------------------------------------------

    @callback
    def enqueue(
        self,
        key: str,
        *,
        received: datetime,
        review: ReviewItem,
        known: bool,
        forced: bool = False,
        fill: bool = False,
    ) -> None:
        """Queue an e-mail; ``review`` is used if the AI can't help.

        A ``fill`` entry is an e-mail a parser read: the AI only fills in what
        the parser missed, and nothing goes to review when it can't.
        """
        self._discard(key)
        self.queue.append(
            {
                "id": new_id("q"),
                "hash": key,
                "attempts": 0,
                "not_before": None,
                "queued": dt_to_str(dt_util.utcnow()),
                "received": dt_to_str(received),
                "forced": forced,
                "known": known,
                "fill": fill,
                "review": review.as_dict(),
            }
        )
        self.wake()
        async_dispatcher_send(self.hass, SIGNAL_AI_UPDATED)

    @callback
    def drop(self, key: str) -> None:
        """Forget an e-mail, in the queue and as a shadow candidate."""
        if self._discard(key):
            async_dispatcher_send(self.hass, SIGNAL_AI_UPDATED)

    @callback
    def drop_domain(self, org: str) -> list[str]:
        """Forget the e-mails of a sender organisation; returns their hashes.

        Fills are dropped too, but their e-mails were already read, so their
        hashes aren't returned.
        """
        messages = self.engine.data.messages
        dropped: list[str] = []
        queue = self.queue
        changed = False
        for entry in list(queue):
            domain = str(entry["review"].get("sender_domain", ""))
            if organizational_domain(domain) == org:
                queue.remove(entry)
                changed = True
                if not entry.get("fill"):
                    dropped.append(entry["hash"])
        shadow = self._shadow()
        shadow[:] = [
            key
            for key in shadow
            if (record := messages.get(key)) is None
            or organizational_domain(record.sender_domain) != org
        ]
        if changed:
            async_dispatcher_send(self.hass, SIGNAL_AI_UPDATED)
        return dropped

    @callback
    def add_shadow_candidate(self, key: str) -> None:
        """Offer an e-mail that a parser handled for the shadow check."""
        if not self.engine.ai_entity or self.engine.ai_mode is not AIMode.SUGGEST:
            return
        shadow = self._shadow()
        if key in shadow:
            shadow.remove(key)
        shadow.append(key)
        del shadow[:-SHADOW_CANDIDATES]

    def _shadow(self) -> list[str]:
        shadow = self.engine.data.ai.get("shadow")
        if not isinstance(shadow, list):
            shadow = self.engine.data.ai["shadow"] = []
        return shadow

    def _discard(self, key: str) -> bool:
        queue = self.queue
        before = len(queue)
        queue[:] = [entry for entry in queue if entry["hash"] != key]
        shadow = self._shadow()
        if key in shadow:
            shadow.remove(key)
        return len(queue) != before

    def _current(self, entry: dict[str, Any]) -> bool:
        """Return True while an entry is still queued."""
        return any(item is entry for item in self.queue)

    def _remove(self, entry: dict[str, Any]) -> None:
        self.queue[:] = [item for item in self.queue if item is not entry]

    def _drop(self, entry: dict[str, Any]) -> None:
        """Drop a fill: its e-mail stays added as the parser read it."""
        self._remove(entry)
        self.engine.async_schedule_save()
        async_dispatcher_send(self.hass, SIGNAL_AI_UPDATED)

    def _drop_refund(self, entry: dict[str, Any], record: MessageRecord) -> None:
        """Drop a refund e-mail silently: not in review, nor filtered."""
        self._remove(entry)
        self.engine.drop_refund(record)
        self.engine.async_changed()

    def _set_busy(self, key: str | None) -> None:
        if self._busy != key:
            self._busy = key
            async_dispatcher_send(self.hass, SIGNAL_AI_UPDATED)

    # -- Steps ------------------------------------------------------------

    async def _async_step(self) -> float:
        """Handle one e-mail; returns how long to wait before the next step."""
        engine = self.engine
        data = engine.data
        now = dt_util.utcnow()
        if not engine.ai_active:
            self._release_all(now)
            self._clear_issues()
            return IDLE_WAIT.total_seconds()
        if self._expire(now):
            engine.async_changed()
        paused = dt_from_str(data.ai.get("paused_until"))
        if paused is not None:
            if paused > now:
                return (paused - now).total_seconds()
            data.ai.pop("paused_until", None)
            async_dispatcher_send(self.hass, SIGNAL_AI_UPDATED)
        if self.today()["calls"] >= AI_DAILY_LIMIT:
            # Midnight wakes the worker.
            return IDLE_WAIT.total_seconds()
        if (entry := self._next_entry(now)) is not None:
            self._set_busy(entry["hash"])
            try:
                await self._async_process(entry)
            finally:
                self._set_busy(None)
            return 0
        if (
            engine.ai_mode is AIMode.SUGGEST
            and self.today()["shadow"] < AI_SHADOW_DAILY_LIMIT
            and self._shadow()
        ):
            key = self._shadow().pop()
            self._set_busy(key)
            try:
                await self._async_shadow(key)
            finally:
                self._set_busy(None)
            return 0
        return self._idle_delay(now)

    def _idle_delay(self, now: datetime) -> float:
        """Return the time until a waiting entry is due or expires."""
        delay = IDLE_WAIT.total_seconds()
        for entry in self.queue:
            for moment in (
                dt_from_str(entry.get("not_before")),
                (queued + QUEUE_MAX_AGE)
                if (queued := dt_from_str(entry.get("queued")))
                else None,
            ):
                if moment is not None and moment > now:
                    delay = min(delay, (moment - now).total_seconds())
        return max(delay, 1.0)

    def _record(self, entry: dict[str, Any]) -> MessageRecord | None:
        record = self.engine.data.messages.get(entry["hash"])
        wanted = MessageState.APPLIED if entry.get("fill") else MessageState.QUEUED
        if record is None or record.state is not wanted:
            return None
        return record

    def _next_entry(self, now: datetime) -> dict[str, Any] | None:
        """Return the next due entry that a loaded mailbox can download.

        E-mails no parser read go first, newest first; fills come after them
        and wait while today's fill limit is reached, unless forced.
        """
        engine = self.engine
        fills_full = self.today()["fills"] >= AI_FILL_DAILY_LIMIT
        best: dict[str, Any] | None = None
        best_rank: tuple[bool, bool, datetime] | None = None
        changed = False
        for entry in list(self.queue):
            fill = bool(entry.get("fill"))
            record = self._record(entry)
            if record is None:
                self._remove(entry)
                changed = True
                continue
            if not record.refs:
                # Every mailbox that had it was removed.
                self._remove(entry)
                if not fill:
                    record.state = MessageState.IGNORED
                changed = True
                continue
            if fill and fills_full and not entry.get("forced"):
                continue
            not_before = dt_from_str(entry.get("not_before"))
            if not_before is not None and not_before > now:
                continue
            if not any(entry_id in engine.mailboxes for entry_id in record.refs):
                continue
            received = dt_from_str(entry.get("received")) or dt_from_str(
                entry.get("queued")
            )
            rank = (not fill, received is not None, received or _NEVER)
            if best_rank is None or rank > best_rank:
                best, best_rank = entry, rank
        if changed:
            engine.async_changed()
        return best

    def _expire(self, now: datetime) -> bool:
        """Send e-mails that waited too long to review."""
        changed = False
        for entry in list(self.queue):
            queued = dt_from_str(entry.get("queued"))
            if queued is not None and now - queued <= QUEUE_MAX_AGE:
                continue
            self._to_review(entry, now, reason=REASON_AI_UNAVAILABLE, notify=False)
            changed = True
        return changed

    def _release_all(self, now: datetime) -> None:
        """Send every queued e-mail to review, as the parser left it."""
        if not self.queue:
            return
        for entry in list(self.queue):
            self._to_review(entry, now, notify=False)
        self.engine.async_changed()

    def _to_review(
        self,
        entry: dict[str, Any],
        now: datetime,
        *,
        reason: str | None = None,
        notify: bool = True,
        **changes: Any,
    ) -> None:
        """Move an entry to "Needs review"; a fill is only dropped."""
        if entry.get("fill"):
            self._drop(entry)
            return
        self._remove(entry)
        record = self._record(entry)
        if record is None:
            return
        item = ReviewItem.from_dict(entry["review"])
        item = replace(
            item, id=new_id("r"), created=now, reason=reason or item.reason, **changes
        )
        self.engine.add_review(item, record)
        if notify:
            self.engine.async_changed()

    def _retry_or_review(
        self, entry: dict[str, Any], now: datetime, *, timed_out: bool = False
    ) -> None:
        """Count a failed call; retry later, or give up after the last try.

        The review reason tells a last try that took too long from one that
        failed.
        """
        entry["attempts"] = int(entry.get("attempts", 0)) + 1
        self._count("failed")
        if entry["attempts"] >= MAX_ATTEMPTS:
            reason = REASON_AI_TIMEOUT if timed_out else REASON_AI_UNAVAILABLE
            self._to_review(entry, now, reason=reason)
            return
        entry["not_before"] = dt_to_str(now + AI_RETRY_DELAY)
        self.engine.async_schedule_save()

    def _pause(self, now: datetime) -> None:
        self.engine.data.ai["paused_until"] = dt_to_str(now + AI_RETRY_DELAY)
        self.engine.async_schedule_save()

    def _entity_available(self) -> bool:
        entity_id = self.engine.ai_entity
        state = self.hass.states.get(entity_id) if entity_id else None
        return state is not None and state.state != STATE_UNAVAILABLE

    async def _async_download(
        self, record: MessageRecord
    ) -> tuple[MailMessage | None, bool]:
        """Download an e-mail again; returns it, or whether it's gone."""
        fetched = await self.engine.async_refetch(record)
        return fetched.message, fetched.gone

    async def _async_process(self, entry: dict[str, Any]) -> None:
        """Read one queued e-mail with the AI."""
        engine = self.engine
        record = self._record(entry)
        if record is None:
            self._remove(entry)
            return
        message, gone = await self._async_download(record)
        now = dt_util.utcnow()
        if not self._current(entry):
            return
        if message is None:
            if gone and entry.get("fill"):
                self._drop(entry)
            elif gone:
                self._remove(entry)
                record.state = MessageState.IGNORED
                engine.async_changed()
            else:
                entry["not_before"] = dt_to_str(now + AI_RETRY_DELAY)
                engine.async_schedule_save()
            return
        read = await engine.async_read(message)
        now = dt_util.utcnow()
        if not self._current(entry):
            return
        if read is None:
            entry["not_before"] = dt_to_str(now + AI_RETRY_DELAY)
            engine.async_schedule_save()
            return
        verdict, parsed = read
        org = organizational_domain(message.sender_domain)
        fill = bool(entry.get("fill"))
        gaps: set[str] = set()
        if fill:
            # Only for an e-mail a parser read and added; and only what's
            # still missing.
            if verdict.verified and is_confident(parsed):
                gaps = engine.fill_gaps_for(record.hash, parsed)
            if not gaps:
                self._drop(entry)
                return
        elif is_refund(parsed):
            # Refunds aren't parcel events, even when asked to read again.
            self._drop_refund(entry, record)
            return
        elif parsed.kind is MailKind.CUSTOMER_RETURN:
            # Nor does the AI read returns: the parser's reading decides.
            self._remove(entry)
            item = ReviewItem.from_dict(entry["review"])
            engine.decide_return(
                message,
                verdict,
                parsed,
                record,
                mailbox=item.mailbox,
                owner=item.owner,
                now=now,
            )
            engine.async_changed()
            return
        elif not entry.get("forced") and verdict.verified and is_confident(parsed):
            # A trusted sender or a newer parser can read it now.
            self._remove(entry)
            engine.apply_result(
                parsed,
                record,
                source=Source.PARSER,
                time=engine.message_time(message, now),
                label=org,
                now=now,
            )
            engine.async_changed()
            return
        entity_id = engine.ai_entity
        if entity_id is None:
            return
        try:
            validation = await self._async_extract(entity_id, message, fill=fill)
        except AIRefused as err:
            self._last_error = f"refused:{err.reason}"
            self._raise_issue(ISSUE_AI_REFUSED, reason=err.reason)
            self._pause(dt_util.utcnow())
            return
        except AIUnavailable:
            self._last_error = "unavailable"
            self._raise_issue(ISSUE_AI_UNAVAILABLE)
            now = dt_util.utcnow()
            self._pause(now)
            if self._current(entry) and self._entity_available():
                # The AI task looked available but the call failed.
                self._retry_or_review(entry, now)
            return
        except AIBadOutput as err:
            self._last_error = "bad_output"
            _LOGGER.debug("The AI answer was rejected: %s", ", ".join(err.errors))
            self._clear_issues()
            self._count("rejected")
            if self._current(entry):
                self._to_review(
                    entry,
                    dt_util.utcnow(),
                    reason=REASON_AI_REJECTED,
                    errors=check_codes(err.errors),
                )
            return
        except AIError as err:
            self._last_error = type(err).__name__
            if self._current(entry):
                self._retry_or_review(
                    entry, dt_util.utcnow(), timed_out=isinstance(err, AITimeout)
                )
            return
        self._last_error = None
        self._clear_issues()
        now = dt_util.utcnow()
        if not self._current(entry) or (record := self._record(entry)) is None:
            return
        if fill:
            self._fill(
                entry,
                record,
                message,
                parsed,
                validation.result,
                # The parcel may have changed meanwhile.
                engine.fill_gaps_for(record.hash, parsed),
                now,
                notes=validation.notes,
            )
            return
        self._decide(
            entry,
            record,
            message,
            validation.result,
            now,
            trusted=verdict.verified,
            errors=validation.errors,
            notes=validation.notes,
            parser=parsed.parser,
        )

    async def _async_extract(
        self,
        entity_id: str,
        message: MailMessage,
        *,
        shadow: bool = False,
        fill: bool = False,
    ) -> Validation:
        """Ask the AI task to read an e-mail; count the calls that reached it."""
        started = self.hass.loop.time()
        try:
            validation = await async_extract(
                self.hass, entity_id, message, self.engine.tz
            )
        except AIRefused:
            raise
        except AIUnavailable:
            # An AI task that is down was never called.
            if self._entity_available():
                self._count_call(started, shadow=shadow, fill=fill)
            raise
        except AIError:
            self._count_call(started, shadow=shadow, fill=fill)
            raise
        self._count_call(started, shadow=shadow, fill=fill)
        return validation

    def _decide(
        self,
        entry: dict[str, Any],
        record: MessageRecord,
        message: MailMessage,
        result: ParseResult | None,
        now: datetime,
        *,
        trusted: bool,
        errors: tuple[str, ...] = (),
        notes: tuple[str, ...] = (),
        parser: str | None = None,
    ) -> None:
        """Apply, suggest, filter or review the AI's reading of an e-mail.

        ``errors`` are the checks the answer failed; its other values are
        still offered for review. ``notes`` say what the checks changed, for
        administrators. ``parser`` names the parser that recognised the
        sender: the answer is sorted the same way as the parser's, so a
        refund is dropped and a customer return told apart. The details a
        parser's result gets (collect-by date, next attempt, where it was
        left) are read from the e-mail for the answer too.
        """
        engine = self.engine
        if result is not None:
            result = sort_returns(result, message, engine.tz, parser=parser)
            result = add_details(result, message, engine.tz)
        if result is None or result.kind is MailKind.UNKNOWN:
            self._to_review(entry, now, reason=REASON_UNKNOWN_FORMAT)
            return
        if is_refund(result):
            self._drop_refund(entry, record)
            return
        if result.kind is MailKind.NOT_PARCEL:
            if result.confidence >= CONFIDENCE_APPLY:
                self._remove(entry)
                item = ReviewItem.from_dict(entry["review"])
                engine.add_filtered(replace(item, created=now), record)
                self._count("filtered")
                engine.async_changed()
            else:
                # The AI said "not a parcel" but the e-mail has tracking numbers.
                self._count("rejected")
                self._to_review(
                    entry,
                    now,
                    reason=REASON_AI_REJECTED,
                    errors=check_codes(errors),
                    notes=check_codes(notes),
                )
            return
        if engine.ai_mode is AIMode.AUTO and trusted and is_confident(result):
            self._remove(entry)
            engine.apply_result(
                result,
                record,
                source=Source.AI,
                time=engine.message_time(message, now),
                label=organizational_domain(message.sender_domain),
                now=now,
            )
            self._count("applied")
            engine.async_changed()
            return
        if errors:
            _LOGGER.debug("The AI answer failed checks: %s", ", ".join(errors))
        self._count("rejected" if errors else "suggested")
        self._to_review(
            entry,
            now,
            reason=REASON_AI_REJECTED if errors else REASON_AI_SUGGESTION,
            source=Source.AI,
            suggestion=engine.suggestion_for(result, message, now),
            errors=check_codes(errors),
            notes=check_codes(notes),
        )

    def _fill(
        self,
        entry: dict[str, Any],
        record: MessageRecord,
        message: MailMessage,
        parsed: ParseResult,
        result: ParseResult | None,
        gaps: set[str],
        now: datetime,
        *,
        notes: tuple[str, ...] = (),
    ) -> None:
        """Add, or suggest, the gaps the AI filled in an e-mail a parser read.

        Only checked values that fill a gap count: the parser's values always
        win. In Auto mode they're added, marked as the AI's until confirmed;
        otherwise they wait in "Needs review", with the answer's ``notes``
        and those of the older fill they replace.
        """
        engine = self.engine
        suggestion = fill_suggestion(result, gaps, parsed)
        if suggestion is None:
            self._drop(entry)
            return
        self._remove(entry)
        self._count("filled")
        if engine.ai_mode is AIMode.AUTO:
            engine.apply_fill(
                suggestion,
                record,
                time=engine.message_time(message, now),
                label=organizational_domain(message.sender_domain),
                now=now,
            )
        else:
            if (old := engine.fill_item(record.hash)) is not None and old.suggestion:
                suggestion = merge_fills(old.suggestion, suggestion)
                notes = (*old.notes, *notes)
            item = ReviewItem.from_dict(entry["review"])
            engine.add_review(
                replace(
                    item,
                    id=new_id("r"),
                    created=now,
                    reason=REASON_AI_FILL,
                    source=Source.AI,
                    suggestion=suggestion,
                    fill=True,
                    notes=check_codes(notes),
                ),
                record,
            )
        engine.async_changed()

    async def _async_shadow(self, key: str) -> None:
        """Read an e-mail that a parser handled, and compare the answers."""
        engine = self.engine
        record = engine.data.messages.get(key)
        if (
            record is None
            or record.state is not MessageState.APPLIED
            or not any(entry_id in engine.mailboxes for entry_id in record.refs)
        ):
            return
        message, _gone = await self._async_download(record)
        if message is None or (read := await engine.async_read(message)) is None:
            return
        verdict, parsed = read
        entity_id = engine.ai_entity
        if entity_id is None or not (verdict.verified and is_confident(parsed)):
            return
        try:
            validation = await self._async_extract(entity_id, message, shadow=True)
        except AIRefused as err:
            self._last_error = f"refused:{err.reason}"
            self._raise_issue(ISSUE_AI_REFUSED, reason=err.reason)
            self._pause(dt_util.utcnow())
            return
        except AIUnavailable:
            self._last_error = "unavailable"
            self._raise_issue(ISSUE_AI_UNAVAILABLE)
            self._pause(dt_util.utcnow())
            return
        except AIBadOutput:
            self._clear_issues()
            self._count("disagree")
            return
        except AIError as err:
            self._last_error = type(err).__name__
            return
        self._last_error = None
        self._clear_issues()
        result = validation.result
        if result is not None:
            result = sort_returns(result, message, engine.tz, parser=parsed.parser)
        agree = result is not None and results_agree(parsed, result)
        self._count("agree" if agree else "disagree")

    # -- Repairs ----------------------------------------------------------

    def _raise_issue(self, issue_id: str, **placeholders: str) -> None:
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=issue_id,
            translation_placeholders=placeholders or None,
        )

    def _clear_issues(self) -> None:
        for issue_id in (ISSUE_AI_UNAVAILABLE, ISSUE_AI_REFUSED):
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    # -- Diagnostics ------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        """Return the queue state and counters, without e-mail details.

        ``totals``, ``average_seconds`` and ``agreement_rate`` cover the last
        ``STATS_DAYS`` days.
        """
        ai = self.engine.data.ai
        agree, disagree = self.shadow_totals()
        days = self._recent("stats")
        average = self.average_seconds()
        return {
            "configured": bool(self.engine.ai_entity),
            "mode": self.engine.ai_mode.value,
            "status": self.status,
            "running": self._task is not None and not self._task.done(),
            "queue": len(self.queue),
            "queue_forced": sum(1 for entry in self.queue if entry.get("forced")),
            "queue_retrying": sum(1 for entry in self.queue if entry.get("attempts")),
            "paused_until": ai.get("paused_until"),
            "shadow_candidates": len(self._shadow()),
            "shadow_agree": agree,
            "shadow_disagree": disagree,
            "agreement_rate": (
                round(agree / (agree + disagree), 2) if agree + disagree else None
            ),
            "totals": {
                name: sum(int(day.get(name, 0)) for day in days) for name in STAT_KEYS
            },
            "average_seconds": round(average, 1) if average is not None else None,
            "stats": dict(ai.get("stats") or {}),
            "last_error": self._last_error,
        }
