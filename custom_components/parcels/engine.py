"""The Parcels engine.

The engine owns the stored data and makes every change to it: e-mails from
the mailbox coordinators, results of the AI worker, review actions and the
services. After each change it fires the parcel events, saves the store,
tells entities and WebSocket subscribers, and lets the notifier re-evaluate.

E-mail bodies only exist in memory while an e-mail is processed. The store
keeps a hash of each e-mail and the provider IDs needed to download it again.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, tzinfo
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .ai_worker import AIWorker
from .config_flow import HUB_DEFAULTS
from .const import (
    AI_FIRST_SYNC_DAYS,
    CARRIER_NAMES,
    CONF_ADDRESS,
    CONF_AI_MODE,
    CONF_AI_TASK,
    CONF_ARCHIVE_DAYS,
    CONF_ENTRY_TYPE,
    CONF_OWNER,
    CONF_PURGE_DAYS,
    CONFIDENCE_APPLY,
    DEFAULT_AI_MODE,
    DEFAULT_ARCHIVE_DAYS,
    DEFAULT_PURGE_DAYS,
    DOMAIN,
    ENTRY_TYPE_HUB,
    EVENT_DELIVERED,
    EVENT_PARCEL_ADDED,
    EVENT_STATUS_CHANGED,
    ISSUE_PARSER_OUTDATED,
    REASON_LOW_CONFIDENCE,
    REASON_RESTORED,
    REASON_UNKNOWN_FORMAT,
    REASON_UNKNOWN_SENDER,
    SIGNAL_DATA_UPDATED,
    AIMode,
    MailKind,
    ParcelStatus,
)
from .convert import (
    is_confident,
    result_contributions,
    suggestion_from_result,
    suggestion_result,
)
from .dedup import (
    REPAIR_KEY,
    REPAIR_VERSION,
    Contribution,
    DedupError,
    MergeSuggestion,
    accept_suggestion,
    add_owner,
    apply_contribution,
    archive_parcel,
    dismiss_suggestion,
    infer_deliveries,
    mark_delivered,
    merge_parcels,
    reconcile,
    remove_message,
    repair_store,
    split_parcel,
    undo_auto_merge,
    undo_inferred_delivery,
    update_parcel,
)
from .mail.errors import (
    MailAuthError,
    MailCursorExpired,
    MailError,
    MailNotFound,
    MailRateLimited,
)
from .models import (
    FilteredItem,
    MessageRecord,
    MessageState,
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    ReviewItem,
    Source,
    Suggestion,
    dt_from_str,
    dt_to_str,
    new_id,
)
from .parsers import NOTE_KNOWN_SENDER_UNPARSED, parse_message
from .parsers.auth import verify_sender
from .parsers.base import MailMessage, ParseResult, SenderVerdict, message_hash
from .parsers.prefilter import is_candidate
from .parsers.senders import (
    is_free_mail,
    lookup,
    organizational_domain,
    ships_with_many,
)
from .parsers.tracking import (
    MAX_NUMBER_CHARS,
    detect_carrier,
    normalize_tracking_number,
)
from .store import ParcelsStore, apply_retention

if TYPE_CHECKING:
    from .coordinator import MailboxCoordinator
    from .mail import MailClient, MessageMeta
    from .notifier import Notifier
    from .seventeentrack import SeventeenTrackSync

_LOGGER = logging.getLogger(__name__)

# Events are only fired for changes that happened recently, so the first
# sync of a mailbox doesn't replay a month of deliveries.
EVENT_MAX_AGE = timedelta(days=1)
# A download that fails this often is recorded as failed and skipped.
FETCH_ATTEMPTS = 3
# A known sender whose e-mails the parser can't read this often within the
# window raises a repair issue; failures are remembered for UNPARSED_KEEP.
UNPARSED_THRESHOLD = 2
UNPARSED_WINDOW = timedelta(days=7)
UNPARSED_KEEP = timedelta(days=30)
MIN_NUMBER_CHARS = 5


def validation_error(key: str, **placeholders: str) -> ServiceValidationError:
    """Return a translated error for a bad request."""
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def manual_number(value: str) -> str:
    """Return a tracking number the user typed, normalised, or raise."""
    number = normalize_tracking_number(value)
    if (
        not MIN_NUMBER_CHARS <= len(number) <= MAX_NUMBER_CHARS
        or not number.replace("/", "").isalnum()
    ):
        raise validation_error("invalid_tracking_number")
    return number


def review_reason(verdict: SenderVerdict, result: ParseResult) -> str:
    """Return why an e-mail needs review."""
    if not verdict.authenticated:
        return verdict.reason or "no_auth_header"
    if not verdict.known:
        return REASON_UNKNOWN_SENDER
    if result.is_parcel:
        return REASON_LOW_CONFIDENCE
    return REASON_UNKNOWN_FORMAT


def _aware(value: datetime) -> datetime:
    """Return ``value`` with a time zone; naive values are UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _domain(address: str) -> str:
    """Return the lowercased domain of an address or a bare domain."""
    return address.rpartition("@")[2].strip().lower().rstrip(">")


@dataclass(slots=True)
class MailboxRuntime:
    """A loaded mailbox entry: its API client and polling coordinator."""

    entry: ConfigEntry
    client: MailClient
    coordinator: MailboxCoordinator | None = None
    # The first sync, which runs in the background.
    first_sync: asyncio.Task[None] | None = None

    @property
    def entry_id(self) -> str:
        """Return the config entry ID."""
        return self.entry.entry_id

    @property
    def address(self) -> str:
        """Return the mailbox address."""
        return str(self.entry.data.get(CONF_ADDRESS) or self.entry.title)

    @property
    def owner(self) -> str | None:
        """Return the person entity that owns the mailbox, if set."""
        return self.entry.options.get(CONF_OWNER) or None


@dataclass(slots=True)
class Refetch:
    """The result of downloading a stored e-mail again."""

    message: MailMessage | None = None
    mailbox: MailboxRuntime | None = None
    # True when every mailbox reported the e-mail deleted.
    gone: bool = False


@callback
def get_engine(hass: HomeAssistant) -> ParcelsEngine | None:
    """Return the engine of the loaded hub entry."""
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB:
            engine = getattr(entry, "runtime_data", None)
            if isinstance(engine, ParcelsEngine):
                return engine
    return None


class ParcelsEngine:
    """Owns the Parcels data and every change to it."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the engine of the hub entry."""
        self.hass = hass
        self.entry = entry
        self.store = ParcelsStore(hass)
        self.notifier: Notifier | None = None
        self.tracker: SeventeenTrackSync | None = None
        self.ai = AIWorker(self)
        self.mailboxes: dict[str, MailboxRuntime] = {}
        self._statuses: dict[str, ParcelStatus] = {}
        self._inflight: dict[str, asyncio.Event] = {}
        self._fetch_failures: dict[str, int] = {}
        self._unsubs: list[CALLBACK_TYPE] = []
        self._started = False
        # Mailboxes being read, and mailboxes with more e-mails to read soon.
        # Parcels are reconciled once all of them are done.
        self._syncing: set[str] = set()
        self._more: set[str] = set()
        self._reconciling = False
        self._suggestions: dict[str, MergeSuggestion] = {}

    # -- Properties -------------------------------------------------------

    @property
    def started(self) -> bool:
        """Return True between async_start and async_stop."""
        return self._started

    @property
    def data(self) -> ParcelsData:
        """Return the stored data."""
        return self.store.data

    @property
    def options(self) -> dict[str, Any]:
        """Return the hub options, with defaults for missing ones."""
        return {**HUB_DEFAULTS, **self.entry.options}

    @property
    def tz(self) -> tzinfo:
        """Return Home Assistant's time zone."""
        return dt_util.get_default_time_zone()

    @property
    def ai_entity(self) -> str | None:
        """Return the AI task entity, if one is configured."""
        return self.entry.options.get(CONF_AI_TASK) or None

    @property
    def ai_mode(self) -> AIMode:
        """Return the configured AI mode."""
        try:
            return AIMode(self.entry.options.get(CONF_AI_MODE, DEFAULT_AI_MODE))
        except ValueError:
            return DEFAULT_AI_MODE

    @property
    def ai_active(self) -> bool:
        """Return True when e-mails may be sent to the AI."""
        return bool(self.ai_entity) and self.ai_mode is not AIMode.OFF

    # -- NotifierHost -----------------------------------------------------

    def visible_parcels(self) -> list[Parcel]:
        """Return the parcels that aren't archived."""
        return [p for p in self.data.parcels.values() if p.archived is None]

    @callback
    def async_schedule_save(self) -> None:
        """Save the store soon; a stopped engine never saves again.

        After a reload of the hub, a new engine owns the stored data.
        """
        if self._started:
            self.store.async_schedule_save()

    # -- Lifecycle --------------------------------------------------------

    async def async_start(self) -> None:
        """Load the store and start the scheduled jobs and the AI worker."""
        await self.store.async_load()
        data = self.data
        data.engine.setdefault("synced", {})
        now = dt_util.utcnow()
        if int(data.engine.get(REPAIR_KEY) or 0) < REPAIR_VERSION:
            self._repair(now)
        self._statuses = {pid: p.state.status for pid, p in data.parcels.items()}
        self._started = True
        self._run_retention(now)
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._async_daily, hour=3, minute=15, second=0
            )
        )
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._async_midnight, hour=0, minute=0, second=5
            )
        )
        self.ai.async_start()

    async def async_stop(self) -> None:
        """Stop the jobs and the AI worker, and save."""
        while self._unsubs:
            self._unsubs.pop()()
        await self.ai.async_stop()
        self._started = False
        await self.store.async_save()

    @callback
    def async_create_task(
        self, coro: Coroutine[Any, Any, Any], name: str
    ) -> asyncio.Task[Any]:
        """Run ``coro`` in the background until the hub entry unloads."""
        return self.entry.async_create_background_task(self.hass, coro, name)

    @callback
    def _async_daily(self, _now: datetime) -> None:
        """Apply retention and drop data of removed mailboxes."""
        self._drop_unknown_mailboxes()
        self._run_retention(dt_util.utcnow())

    @callback
    def _async_midnight(self, _now: datetime) -> None:
        """Refresh what depends on the date, e.g. inferred deliveries."""
        self.async_changed()
        self.ai.wake()

    @callback
    def _repair(self, now: datetime) -> None:
        """Fix what earlier releases stored, once per repair version.

        Parcels are reconciled right after, as on every start.
        """
        data = self.data
        changed = repair_store(data, now)
        data.engine[REPAIR_KEY] = REPAIR_VERSION
        if changed:
            _LOGGER.info("Parcels updated %d stored parcels", len(changed))
        self.async_schedule_save()

    # -- Reconciling ------------------------------------------------------

    @callback
    def begin_sync(self, entry_id: str) -> None:
        """Note that a mailbox is being read."""
        self._syncing.add(entry_id)

    @callback
    def end_sync(self, entry_id: str, *, more: bool) -> None:
        """Note that a mailbox was read; ``more`` when it continues soon.

        Once no mailbox is being read, parcels are reconciled.
        """
        self._syncing.discard(entry_id)
        if more:
            self._more.add(entry_id)
        else:
            self._more.discard(entry_id)
        if self._reconcile(dt_util.utcnow()):
            self.async_changed(reconcile=False)

    @callback
    def _reconcile(self, now: datetime) -> bool:
        """Merge parcels that turned out to be one, and infer deliveries.

        Waits while mailboxes are read, so that a first sync, which can arrive
        in any order, is looked at as a whole. Returns True when parcels
        changed.
        """
        if not self._started or self._reconciling or self._syncing or self._more:
            return False
        self._reconciling = True
        try:
            data = self.data
            result = reconcile(data, now)
            inferred = infer_deliveries(data, now)
        finally:
            self._reconciling = False
        self._suggestions = {item.id: item for item in result.suggestions}
        if result.removed or result.changed or inferred:
            _LOGGER.debug(
                "Reconciling merged %d parcels and inferred %d deliveries",
                len(result.removed),
                len(inferred),
            )
            return True
        return False

    @callback
    def _run_retention(self, now: datetime) -> None:
        # Infer deliveries first, so overdue parcels close rather than archive.
        if self._reconcile(now):
            self.async_changed(reconcile=False)
        options = self.options
        result = apply_retention(
            self.data,
            now,
            archive_days=int(options.get(CONF_ARCHIVE_DAYS) or DEFAULT_ARCHIVE_DAYS),
            purge_days=int(options.get(CONF_PURGE_DAYS) or DEFAULT_PURGE_DAYS),
        )
        pruned = self._prune_unparsed(now)
        if result.changed or pruned:
            _LOGGER.debug(
                "Retention archived %d and purged %d parcels",
                len(result.archived),
                len(result.purged),
            )
            self.async_changed()

    # -- Change tracking --------------------------------------------------

    @callback
    def async_changed(self, *, reconcile: bool = True) -> None:
        """Fire events, save, and tell entities, subscribers and the notifier.

        Parcels are reconciled first, unless the caller just did.
        """
        if self._started:
            now = dt_util.utcnow()
            if reconcile:
                self._reconcile(now)
            self._fire_events(now)
        self.async_schedule_save()
        async_dispatcher_send(self.hass, SIGNAL_DATA_UPDATED)
        if self.notifier is not None:
            self.notifier.async_parcels_changed()

    @callback
    def _fire_events(self, now: datetime) -> None:
        statuses: dict[str, ParcelStatus] = {}
        for parcel in self.data.parcels.values():
            state = parcel.state
            statuses[parcel.id] = state.status
            previous = self._statuses.get(parcel.id)
            # An inferred delivery isn't news: nothing reported it.
            if (
                previous == state.status
                or parcel.archived is not None
                or state.inferred
            ):
                continue
            if (
                state.status_time is not None
                and now - state.status_time > EVENT_MAX_AGE
            ):
                continue
            payload = _event_payload(parcel)
            if previous is None:
                self.hass.bus.async_fire(EVENT_PARCEL_ADDED, payload)
            else:
                self.hass.bus.async_fire(
                    EVENT_STATUS_CHANGED,
                    {**payload, "previous_status": previous.value},
                )
            if state.status is ParcelStatus.DELIVERED:
                self.hass.bus.async_fire(EVENT_DELIVERED, payload)
        self._statuses = statuses

    # -- Mailboxes --------------------------------------------------------

    @callback
    def async_add_mailbox(self, mailbox: MailboxRuntime) -> CALLBACK_TYPE:
        """Register a loaded mailbox; returns a callback that removes it."""
        self.mailboxes[mailbox.entry_id] = mailbox
        self.ai.wake()

        @callback
        def remove() -> None:
            if self.mailboxes.get(mailbox.entry_id) is mailbox:
                del self.mailboxes[mailbox.entry_id]
                self._syncing.discard(mailbox.entry_id)
                self._more.discard(mailbox.entry_id)

        return remove

    @callback
    def async_forget_mailbox(self, entry_id: str) -> None:
        """Drop the sync state and e-mail references of a removed mailbox."""
        data = self.data
        data.cursors.pop(entry_id, None)
        data.engine.get("synced", {}).pop(entry_id, None)
        for record in data.messages.values():
            record.refs.pop(entry_id, None)
        self.async_schedule_save()

    @callback
    def _drop_unknown_mailboxes(self) -> None:
        known = {e.entry_id for e in self.hass.config_entries.async_entries(DOMAIN)}
        data = self.data
        stale = {
            *(key for key in data.cursors if key not in known),
            *(key for key in data.engine.get("synced", {}) if key not in known),
        }
        for record in data.messages.values():
            stale.update(key for key in record.refs if key not in known)
        for entry_id in stale:
            self.async_forget_mailbox(entry_id)

    def is_synced(self, entry_id: str) -> bool:
        """Return True once a mailbox finished its first full sync."""
        return bool(self.data.engine.get("synced", {}).get(entry_id))

    @callback
    def mark_synced(self, entry_id: str) -> None:
        """Remember that a mailbox finished its first full sync."""
        synced = self.data.engine.setdefault("synced", {})
        if not synced.get(entry_id):
            synced[entry_id] = dt_to_str(dt_util.utcnow())
            self.async_schedule_save()

    async def async_refresh(self) -> None:
        """Check every mailbox, and 17TRACK, now."""
        for mailbox in list(self.mailboxes.values()):
            if mailbox.coordinator is not None:
                await mailbox.coordinator.async_request_refresh()
        if self.tracker is not None:
            await self.tracker.async_refresh()

    # -- E-mail intake ----------------------------------------------------

    async def async_process_mail(
        self,
        mailbox: MailboxRuntime,
        metas: Sequence[MessageMeta],
        *,
        first_sync: bool,
    ) -> None:
        """Process new e-mails of a mailbox.

        Raises the mailbox's auth, rate-limit and cursor errors, and other
        download errors until an e-mail failed FETCH_ATTEMPTS times.
        """
        changed = False
        # Oldest first: an e-mail never undoes what a newer one said, and
        # mail APIs list changes in any order.
        ordered = sorted(
            metas, key=lambda meta: (_aware(meta.received), meta.provider_id)
        )
        try:
            for meta in ordered:
                if await self._async_process_meta(mailbox, meta, first_sync=first_sync):
                    changed = True
        finally:
            if changed:
                self.async_changed()

    async def _async_process_meta(
        self, mailbox: MailboxRuntime, meta: MessageMeta, *, first_sync: bool
    ) -> bool:
        key = message_hash(meta.message_id, meta.sender, meta.subject, meta.sent)
        # The same e-mail can arrive from two mailboxes at once.
        while (pending := self._inflight.get(key)) is not None:
            await pending.wait()
        done = self._inflight[key] = asyncio.Event()
        try:
            return await self._async_intake(mailbox, meta, key, first_sync=first_sync)
        finally:
            del self._inflight[key]
            done.set()

    async def _async_intake(
        self,
        mailbox: MailboxRuntime,
        meta: MessageMeta,
        key: str,
        *,
        first_sync: bool,
    ) -> bool:
        data = self.data
        now = dt_util.utcnow()
        if (record := data.messages.get(key)) is not None:
            return self._add_ref(record, mailbox, meta.provider_id, now)
        domain = _domain(meta.sender)
        trusted = data.trusted_domains()
        if self.is_ignored(domain) or not is_candidate(
            meta.sender, meta.subject, meta.preview, trusted=trusted
        ):
            return False
        try:
            message = await mailbox.client.async_fetch(meta.provider_id)
        except MailNotFound:
            return False
        except MailAuthError, MailRateLimited, MailCursorExpired:
            raise
        except MailError:
            failures = self._fetch_failures.get(key, 0) + 1
            if failures < FETCH_ATTEMPTS:
                self._fetch_failures[key] = failures
                raise
            self._fetch_failures.pop(key, None)
            _LOGGER.warning(
                "Skipping an e-mail from %s that failed to download %d times",
                domain,
                failures,
            )
            data.messages[key] = MessageRecord(
                hash=key,
                seen=now,
                state=MessageState.FAILED,
                refs={mailbox.entry_id: meta.provider_id},
                received=_aware(meta.received),
                sender_domain=domain,
                owners=_owners(mailbox.owner),
            )
            return True
        self._fetch_failures.pop(key, None)
        alias = message.hash
        if alias != key and (existing := data.messages.get(alias)) is not None:
            return self._add_ref(existing, mailbox, meta.provider_id, now)
        record = MessageRecord(
            hash=key,
            seen=now,
            state=MessageState.IGNORED,
            refs={mailbox.entry_id: meta.provider_id},
            received=_aware(message.received or meta.received),
            sender_domain=message.sender_domain,
            owners=_owners(mailbox.owner),
        )
        verdict = self.verify(message)
        result = await self.async_parse(message, verdict)
        data.messages[key] = record
        self._decide(
            message,
            verdict,
            result,
            record,
            mailbox=mailbox.entry_id,
            owner=mailbox.owner,
            first_sync=first_sync,
            now=now,
        )
        return True

    def _add_ref(
        self,
        record: MessageRecord,
        mailbox: MailboxRuntime,
        provider_id: str,
        now: datetime,
    ) -> bool:
        changed = False
        if record.refs.get(mailbox.entry_id) != provider_id:
            record.refs[mailbox.entry_id] = provider_id
            changed = True
        owner = mailbox.owner
        if owner and owner not in record.owners:
            record.owners = (*record.owners, owner)
            add_owner(self.data, record.hash, owner, now)
            changed = True
        return changed

    def is_ignored(self, domain: str) -> bool:
        """Return True when the user ignores a domain or its organisation."""
        if not domain:
            return False
        data = self.data
        return data.is_ignored(domain) or data.is_ignored(organizational_domain(domain))

    def verify(self, message: MailMessage) -> SenderVerdict:
        """Check the sender of an e-mail, counting the trusted domains."""
        return verify_sender(message, self.data.trusted_domains())

    async def async_parse(
        self, message: MailMessage, verdict: SenderVerdict
    ) -> ParseResult:
        """Parse an e-mail in an executor thread."""
        return await self.hass.async_add_executor_job(
            parse_message, message, verdict, self.tz
        )

    @staticmethod
    def message_time(message: MailMessage, now: datetime) -> datetime:
        """Return when an e-mail was sent, never in the future."""
        return min(_aware(message.date), now)

    def _decide(
        self,
        message: MailMessage,
        verdict: SenderVerdict,
        result: ParseResult,
        record: MessageRecord,
        *,
        mailbox: str | None,
        owner: str | None,
        first_sync: bool,
        now: datetime,
    ) -> None:
        """Apply, queue, review, filter or ignore a parsed e-mail."""
        org = organizational_domain(message.sender_domain)
        if result.kind is MailKind.NOT_PARCEL and result.confidence >= CONFIDENCE_APPLY:
            record.state = MessageState.NOT_PARCEL
            return
        raw = suggestion_from_result(result)
        if is_confident(result):
            if verdict.verified:
                self.apply_result(
                    result,
                    record,
                    source=Source.PARSER,
                    time=self.message_time(message, now),
                    label=org,
                    now=now,
                )
                self.ai.add_shadow_candidate(record.hash)
                self._clear_unparsed(org)
                return
            self.add_review(
                self.review_item(
                    message,
                    record,
                    verdict,
                    reason=verdict.reason or REASON_UNKNOWN_SENDER,
                    source=Source.PARSER,
                    suggestion=self.prefill(raw, message.sender_domain),
                    mailbox=mailbox,
                    owner=owner,
                    now=now,
                ),
                record,
            )
            return
        if verdict.verified and NOTE_KNOWN_SENDER_UNPARSED in result.notes:
            self._track_unparsed(org, now)
        item = self.review_item(
            message,
            record,
            verdict,
            reason=review_reason(verdict, result),
            source=Source.PARSER,
            suggestion=self.prefill(raw, message.sender_domain),
            mailbox=mailbox,
            owner=owner,
            now=now,
        )
        received = record.received or now
        if (
            self.ai_active
            and verdict.authenticated
            and (not first_sync or now - received <= timedelta(days=AI_FIRST_SYNC_DAYS))
        ):
            self.ai.enqueue(
                record.hash, received=received, review=item, known=verdict.known
            )
            record.state = MessageState.QUEUED
            return
        if raw is None and not result.is_parcel:
            # Junk guard: e-mails that matched a keyword but hold nothing
            # parcel-like stay out of the review list.
            if not verdict.authenticated:
                record.state = MessageState.IGNORED
                return
            if not verdict.known:
                self.add_filtered(item, record)
                return
        self.add_review(item, record)

    def apply_result(
        self,
        result: ParseResult,
        record: MessageRecord,
        *,
        source: Source,
        time: datetime,
        label: str,
        now: datetime,
        confirmed: bool = False,
    ) -> set[str]:
        """Add a parse result to the parcels; returns the touched parcel IDs."""
        owners = record.owners
        touched: set[str] = set()
        for contribution in result_contributions(
            result,
            message_hash=record.hash,
            time=time,
            source=source,
            label=label,
            owner=owners[0] if owners else None,
            confirmed=confirmed,
        ):
            applied = apply_contribution(self.data, contribution, now)
            if applied.parcel_id is not None:
                touched.add(applied.parcel_id)
        for owner in owners[1:]:
            touched |= add_owner(self.data, record.hash, owner, now)
        record.state = MessageState.APPLIED
        return touched

    def prefill(self, suggestion: Suggestion | None, domain: str) -> Suggestion | None:
        """Fill in the carrier the user chose before, or the sender's carrier."""
        prefs = self.data.senders.get(organizational_domain(domain))
        info = lookup(domain)
        carrier = (prefs.carrier if prefs else None) or (
            info.carrier if info is not None and not ships_with_many(domain) else None
        )
        if not carrier:
            return suggestion
        if suggestion is None:
            return Suggestion(kind=MailKind.UNKNOWN, carrier=carrier)
        if suggestion.carrier:
            return suggestion
        return replace(suggestion, carrier=carrier)

    def review_item(
        self,
        message: MailMessage,
        record: MessageRecord,
        verdict: SenderVerdict,
        *,
        reason: str,
        source: Source,
        suggestion: Suggestion | None,
        mailbox: str | None,
        owner: str | None,
        now: datetime,
    ) -> ReviewItem:
        """Return a review item for an e-mail."""
        return ReviewItem(
            id=new_id("r"),
            created=now,
            message=record.hash,
            received=record.received,
            sender=message.sender,
            sender_domain=message.sender_domain,
            subject=message.subject,
            mailbox=mailbox,
            owner=owner,
            reason=reason,
            authenticated=verdict.authenticated,
            source=source,
            suggestion=suggestion,
        )

    def add_review(self, item: ReviewItem, record: MessageRecord | None) -> None:
        """Put an e-mail in the review list, replacing an older item."""
        review = self.data.review
        for key in [k for k, r in review.items() if r.message == item.message]:
            del review[key]
        review[item.id] = item
        if record is not None:
            record.state = MessageState.REVIEW

    def add_filtered(self, item: ReviewItem, record: MessageRecord | None) -> None:
        """Put an e-mail in the filtered list."""
        filtered = self.data.filtered
        for key in [k for k, f in filtered.items() if f.message == item.message]:
            del filtered[key]
        entry = FilteredItem(
            id=new_id("f"),
            created=item.created,
            message=item.message,
            received=item.received,
            sender=item.sender,
            sender_domain=item.sender_domain,
            subject=item.subject,
            mailbox=item.mailbox,
        )
        filtered[entry.id] = entry
        if record is not None:
            record.state = MessageState.FILTERED

    async def async_refetch(self, record: MessageRecord) -> Refetch:
        """Download a stored e-mail again from any mailbox that has it."""
        unavailable = False
        for entry_id, provider_id in list(record.refs.items()):
            if (mailbox := self.mailboxes.get(entry_id)) is None:
                unavailable = True
                continue
            try:
                message = await mailbox.client.async_fetch(provider_id)
            except MailNotFound:
                del record.refs[entry_id]
            except MailError as err:
                _LOGGER.debug("Download failed: %s", type(err).__name__)
                unavailable = True
            else:
                return Refetch(message, mailbox)
        return Refetch(gone=not unavailable)

    # -- Parser health ----------------------------------------------------

    def _track_unparsed(self, org: str, now: datetime) -> None:
        unparsed = self.data.engine.setdefault("unparsed", {})
        times = [
            t
            for value in unparsed.get(org, [])
            if (t := dt_from_str(value)) is not None and now - t <= UNPARSED_KEEP
        ]
        times.append(now)
        unparsed[org] = [dt_to_str(t) for t in times[-10:]]
        recent = [t for t in times if now - t <= UNPARSED_WINDOW]
        if len(recent) >= UNPARSED_THRESHOLD:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_PARSER_OUTDATED.format(org),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="parser_outdated",
                translation_placeholders={"sender": org},
            )

    def _clear_unparsed(self, org: str) -> None:
        if self.data.engine.get("unparsed", {}).pop(org, None) is not None:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_PARSER_OUTDATED.format(org))

    def _prune_unparsed(self, now: datetime) -> bool:
        unparsed = self.data.engine.get("unparsed", {})
        changed = False
        for org, values in list(unparsed.items()):
            kept = [
                value
                for value in values
                if (t := dt_from_str(value)) is not None and now - t <= UNPARSED_KEEP
            ]
            if kept == values:
                continue
            changed = True
            if kept:
                unparsed[org] = kept
            else:
                del unparsed[org]
                ir.async_delete_issue(
                    self.hass, DOMAIN, ISSUE_PARSER_OUTDATED.format(org)
                )
        return changed

    # -- Review -----------------------------------------------------------

    def _review(self, review_id: str) -> ReviewItem:
        if (item := self.data.review.get(review_id)) is None:
            raise validation_error("unknown_review")
        return item

    def review_accept(
        self, review_id: str, overrides: Mapping[str, Any] | None = None
    ) -> list[str]:
        """Add a reviewed e-mail, with the user's corrections."""
        data = self.data
        item = self._review(review_id)
        suggestion = item.suggestion
        if overrides:
            base = (
                suggestion.as_dict()
                if suggestion is not None
                else {"kind": MailKind.UNKNOWN.value}
            )
            suggestion = Suggestion.from_dict({**base, **overrides})
        if suggestion is None or not (
            suggestion.tracking_numbers
            or suggestion.order_numbers
            or suggestion.amazon_shipment_id
        ):
            raise validation_error("nothing_to_add")
        if suggestion.carrier and suggestion.carrier not in CARRIER_NAMES:
            raise validation_error("unknown_carrier")
        now = dt_util.utcnow()
        remove_message(data, item.message, now)
        record = data.messages.get(item.message)
        if record is None:
            record = data.messages[item.message] = MessageRecord(
                hash=item.message,
                seen=now,
                state=MessageState.APPLIED,
                received=item.received,
                sender_domain=item.sender_domain,
                owners=_owners(item.owner),
            )
        org = organizational_domain(item.sender_domain)
        touched = self.apply_result(
            suggestion_result(suggestion, item.source),
            record,
            source=item.source,
            time=min(item.received or now, now),
            label=org,
            now=now,
            confirmed=True,
        )
        data.review.pop(review_id, None)
        self.ai.drop(item.message)
        if org and not is_free_mail(org):
            prefs = data.sender(org)
            prefs.accepted += 1
            if item.suggestion is not None and suggestion != item.suggestion:
                prefs.corrections += 1
            if suggestion.carrier and not ships_with_many(org):
                prefs.carrier = suggestion.carrier
            prefs.updated = now
        self.async_changed()
        return sorted(touched)

    def review_dismiss(self, review_id: str) -> None:
        """Drop an e-mail from the review list."""
        item = self._review(review_id)
        del self.data.review[review_id]
        if (record := self.data.messages.get(item.message)) is not None:
            record.state = MessageState.DISMISSED
        self.async_changed()

    def review_trust_sender(self, review_id: str) -> str:
        """Trust the sender of a reviewed e-mail; returns its domain."""
        return self.trust_domain(self._review(review_id).sender_domain)

    def review_ignore_sender(self, review_id: str) -> str:
        """Ignore the sender of a reviewed e-mail; returns its domain."""
        return self.ignore_domain(self._review(review_id).sender_domain)

    def trust_domain(self, domain: str) -> str:
        """Trust a sender organisation and re-read its e-mails under review.

        Returns the organisational domain that is now trusted.
        """
        org = organizational_domain(domain)
        if is_free_mail(org):
            raise validation_error("cannot_trust_free_mail", domain=org)
        data = self.data
        prefs = data.sender(org)
        prefs.trusted = True
        prefs.ignored = False
        prefs.updated = dt_util.utcnow()
        hashes = [
            item.message
            for item in data.review.values()
            if organizational_domain(item.sender_domain) == org
        ]
        self.async_changed()
        if hashes:
            self.async_create_task(
                self._async_reprocess_many(hashes), "parcels reprocess trusted sender"
            )
        return org

    def ignore_domain(self, domain: str) -> str:
        """Ignore a sender organisation and drop its pending e-mails.

        Returns the organisational domain that is now ignored.
        """
        org = organizational_domain(domain)
        if is_free_mail(org):
            raise validation_error("cannot_ignore_free_mail", domain=org)
        data = self.data
        now = dt_util.utcnow()
        prefs = data.sender(org)
        prefs.ignored = True
        prefs.trusted = False
        prefs.updated = now
        hashes: set[str] = set()
        for key, item in list(data.review.items()):
            if organizational_domain(item.sender_domain) == org:
                del data.review[key]
                hashes.add(item.message)
        for key, entry in list(data.filtered.items()):
            if organizational_domain(entry.sender_domain) == org:
                del data.filtered[key]
                hashes.add(entry.message)
        hashes.update(self.ai.drop_domain(org))
        for key in hashes:
            if (record := data.messages.get(key)) is not None:
                record.state = MessageState.IGNORED
        self.async_changed()
        return org

    def filtered_restore(self, filtered_id: str) -> str:
        """Move a filtered e-mail to the review list; returns the review ID."""
        data = self.data
        if (entry := data.filtered.pop(filtered_id, None)) is None:
            raise validation_error("unknown_filtered")
        record = data.messages.get(entry.message)
        item = ReviewItem(
            id=new_id("r"),
            created=dt_util.utcnow(),
            message=entry.message,
            received=entry.received,
            sender=entry.sender,
            sender_domain=entry.sender_domain,
            subject=entry.subject,
            mailbox=entry.mailbox,
            owner=record.owners[0] if record and record.owners else None,
            reason=REASON_RESTORED,
            authenticated=True,
            source=Source.PARSER,
            suggestion=self.prefill(None, entry.sender_domain),
        )
        self.add_review(item, record)
        self.async_changed()
        return item.id

    def filtered_clear(self, filtered_id: str) -> None:
        """Drop a filtered e-mail; its hash stays, so it's never read again."""
        data = self.data
        if (entry := data.filtered.pop(filtered_id, None)) is None:
            raise validation_error("unknown_filtered")
        self._dismiss_message(entry.message)
        self.async_changed()

    def filtered_clear_all(self) -> int:
        """Drop every filtered e-mail; returns how many there were."""
        data = self.data
        entries = list(data.filtered.values())
        data.filtered.clear()
        for entry in entries:
            self._dismiss_message(entry.message)
        if entries:
            self.async_changed()
        return len(entries)

    def _dismiss_message(self, key: str) -> None:
        if (record := self.data.messages.get(key)) is not None:
            record.state = MessageState.DISMISSED

    def message_hashes(
        self,
        *,
        review_id: str | None = None,
        filtered_id: str | None = None,
        parcel_id: str | None = None,
    ) -> list[str]:
        """Return the e-mails behind a review item, filtered item or parcel."""
        data = self.data
        if review_id is not None:
            return [self._review(review_id).message]
        if filtered_id is not None:
            if (entry := data.filtered.get(filtered_id)) is None:
                raise validation_error("unknown_filtered")
            return [entry.message]
        if parcel_id is not None:
            parcel = self.parcel(parcel_id)
            hashes = {o.message for o in parcel.origins.values() if o.message}
            return sorted(h for h in hashes if h in data.messages)
        return []

    async def async_reprocess(self, key: str, *, use_ai: bool = False) -> None:
        """Download an e-mail again and decide anew, or send it to the AI."""
        if use_ai and not self.ai_entity:
            raise validation_error("ai_not_configured")
        data = self.data
        if (record := data.messages.get(key)) is None:
            raise validation_error("unknown_message")
        fetched = await self.async_refetch(record)
        if fetched.message is None or fetched.mailbox is None:
            self.async_schedule_save()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="message_gone"
                if fetched.gone
                else "message_unavailable",
            )
        message, mailbox = fetched.message, fetched.mailbox
        now = dt_util.utcnow()
        self._clear_outputs(key, now)
        verdict = self.verify(message)
        result = await self.async_parse(message, verdict)
        owner = record.owners[0] if record.owners else mailbox.owner
        if use_ai:
            item = self.review_item(
                message,
                record,
                verdict,
                reason=review_reason(verdict, result),
                source=Source.PARSER,
                suggestion=self.prefill(
                    suggestion_from_result(result), message.sender_domain
                ),
                mailbox=mailbox.entry_id,
                owner=owner,
                now=now,
            )
            self.ai.enqueue(
                key,
                received=record.received or now,
                review=item,
                known=verdict.known,
                forced=True,
            )
            record.state = MessageState.QUEUED
        else:
            self._decide(
                message,
                verdict,
                result,
                record,
                mailbox=mailbox.entry_id,
                owner=owner,
                first_sync=False,
                now=now,
            )
        self.async_changed()

    async def _async_reprocess_many(self, hashes: Iterable[str]) -> None:
        for key in hashes:
            try:
                await self.async_reprocess(key)
            except HomeAssistantError as err:
                _LOGGER.debug("Reprocessing skipped an e-mail: %s", err)

    def _clear_outputs(self, key: str, now: datetime) -> None:
        """Undo everything an e-mail added: parcels, review and queue."""
        data = self.data
        remove_message(data, key, now)
        for review_id in [k for k, r in data.review.items() if r.message == key]:
            del data.review[review_id]
        for filtered_id in [k for k, f in data.filtered.items() if f.message == key]:
            del data.filtered[filtered_id]
        self.ai.drop(key)

    # -- Parcel services --------------------------------------------------

    def parcel(self, parcel_id: str) -> Parcel:
        """Return a parcel, or raise a translated error."""
        if (parcel := self.data.parcels.get(parcel_id)) is None:
            raise validation_error("unknown_parcel")
        return parcel

    def _run[T](self, func: Callable[..., T], *args: Any) -> T:
        try:
            result = func(self.data, *args)
        except DedupError as err:
            raise validation_error(err.reason) from err
        except KeyError as err:
            raise validation_error("unknown_parcel") from err
        self.async_changed()
        return result

    def add_parcel(
        self,
        tracking_number: str,
        *,
        carrier: str | None = None,
        merchant: str | None = None,
        private: bool = False,
        owners: Sequence[str] = (),
    ) -> str:
        """Add a parcel by tracking number; returns its ID."""
        number = manual_number(tracking_number)
        carrier = carrier or detect_carrier(number)
        if carrier is not None and carrier not in CARRIER_NAMES:
            raise validation_error("unknown_carrier")
        now = dt_util.utcnow()
        origin = Origin(
            id=f"man:{new_id('p')}",
            source=Source.MANUAL,
            time=now,
            carrier=carrier,
            tracking_number=number,
            merchant=(merchant or "").strip() or None,
            owners=tuple(owners),
            confirmed=True,
        )
        event = ParcelEvent(
            time=now,
            source=Source.MANUAL,
            origin=origin.id,
            status=ParcelStatus.SHIPPED,
            kind=MailKind.SHIPPED,
        )
        applied = self._run(
            apply_contribution,
            Contribution(origin=origin, events=[event], private=private),
            now,
        )
        return applied.parcel_id

    def update(self, parcel_id: str, changes: Mapping[str, Any]) -> None:
        """Edit a parcel."""
        self.parcel(parcel_id)
        carrier = changes.get("carrier")
        if carrier and carrier not in CARRIER_NAMES:
            raise validation_error("unknown_carrier")
        if changes.get("tracking_number"):
            changes = {
                **changes,
                "tracking_number": manual_number(str(changes["tracking_number"])),
            }
        self._run(update_parcel, parcel_id, dict(changes), dt_util.utcnow())

    def merge(self, parcel_ids: Sequence[str]) -> str:
        """Merge parcels into the first one; returns its ID."""
        ids = list(dict.fromkeys(parcel_ids))
        if len(ids) < 2:
            raise validation_error("merge_needs_two")
        for parcel_id in ids:
            self.parcel(parcel_id)
        return self._run(merge_parcels, ids[0], ids[1:], dt_util.utcnow()).id

    def split(self, parcel_id: str, origin_ids: Sequence[str]) -> str:
        """Move origins of a parcel to a new parcel; returns its ID."""
        self.parcel(parcel_id)
        return self._run(split_parcel, parcel_id, list(origin_ids), dt_util.utcnow()).id

    def undo_merge(self, parcel_id: str) -> str | None:
        """Undo an automatic merge; returns the restored parcel's ID."""
        parcel = self.parcel(parcel_id)
        if parcel.auto_merged is None:
            raise validation_error("nothing_to_undo")
        restored = self._run(undo_auto_merge, parcel_id, dt_util.utcnow())
        return restored.id if restored is not None else None

    def mark_delivered(self, parcel_id: str) -> None:
        """Mark a parcel delivered now."""
        self.parcel(parcel_id)
        self._run(mark_delivered, parcel_id, dt_util.utcnow())

    def undo_delivery(self, parcel_id: str) -> None:
        """Take back an inferred delivery; it isn't inferred again."""
        self.parcel(parcel_id)
        self._run(undo_inferred_delivery, parcel_id, dt_util.utcnow())

    # -- Merge suggestions ------------------------------------------------

    @property
    def suggestions(self) -> list[MergeSuggestion]:
        """Return the merge suggestions whose parcels are still there."""
        parcels = self.data.parcels
        return [
            item
            for item in self._suggestions.values()
            if item.parcel_id in parcels
            and any(candidate in parcels for candidate in item.candidates)
        ]

    def _suggestion(
        self, suggestion_id: str, candidate_id: str | None
    ) -> MergeSuggestion:
        item = self._suggestions.get(suggestion_id)
        if (
            item is None
            or item.parcel_id not in self.data.parcels
            or (candidate_id is not None and candidate_id not in item.candidates)
        ):
            raise validation_error("unknown_suggestion")
        return item

    def _drop_candidates(self, item: MergeSuggestion, candidates: set[str]) -> None:
        """Update a suggestion the user acted on, until the next reconcile."""
        left = tuple(c for c in item.candidates if c not in candidates)
        if left:
            self._suggestions[item.id] = replace(item, candidates=left)
        else:
            self._suggestions.pop(item.id, None)

    def accept_suggestion(self, suggestion_id: str, candidate_id: str) -> str:
        """Merge a suggested parcel; returns the merged parcel's ID."""
        item = self._suggestion(suggestion_id, candidate_id)
        merged = self._run(
            accept_suggestion, item.parcel_id, candidate_id, dt_util.utcnow()
        )
        if suggestion_id in self._suggestions:
            self._suggestions.pop(suggestion_id)
        return merged.id

    def dismiss_suggestion(
        self, suggestion_id: str, candidate_id: str | None = None
    ) -> None:
        """Keep one suggested parcel, or all of them, apart."""
        item = self._suggestion(suggestion_id, candidate_id)
        candidates = (candidate_id,) if candidate_id else item.candidates
        self._drop_candidates(item, set(candidates))
        self._run(dismiss_suggestion, item.parcel_id, candidates)

    def archive(self, parcel_id: str) -> None:
        """Archive a parcel."""
        self.parcel(parcel_id)
        self._run(archive_parcel, parcel_id, dt_util.utcnow())

    # -- Diagnostics ------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        """Return counts and states, without personal data."""
        data = self.data
        statuses: dict[str, int] = {}
        for parcel in data.parcels.values():
            key = "archived" if parcel.archived else parcel.state.status.value
            statuses[key] = statuses.get(key, 0) + 1
        messages: dict[str, int] = {}
        for record in data.messages.values():
            messages[record.state.value] = messages.get(record.state.value, 0) + 1
        return {
            "parcels": statuses,
            "orders": len(data.orders),
            "messages": messages,
            "review": len(data.review),
            "filtered": len(data.filtered),
            "senders": {
                "trusted": sum(1 for p in data.senders.values() if p.trusted),
                "ignored": sum(1 for p in data.senders.values() if p.ignored),
            },
            "mailboxes": {
                entry_id: {
                    "provider": mailbox.client.provider,
                    "synced": self.is_synced(entry_id),
                    "has_cursor": entry_id in data.cursors,
                }
                for entry_id, mailbox in self.mailboxes.items()
            },
            "unparsed_senders": sorted(data.engine.get("unparsed", {})),
            "merge_suggestions": len(self.suggestions),
            "inferred_deliveries": sum(
                1 for parcel in data.parcels.values() if parcel.state.inferred
            ),
            "auto_merged": sum(
                1 for parcel in data.parcels.values() if parcel.auto_merged
            ),
            "kept_apart": len(data.engine.get("kept_apart") or ()),
            "repair": data.engine.get(REPAIR_KEY),
            "reconcile_waiting": len(self._syncing | self._more),
            "ai": self.ai.diagnostics(),
        }


def _owners(owner: str | None) -> tuple[str, ...]:
    return (owner,) if owner else ()


def _event_payload(parcel: Parcel) -> dict[str, Any]:
    """Return event data for a parcel, without item names."""
    state = parcel.state
    eta = state.eta
    payload: dict[str, Any] = {
        "parcel_id": parcel.id,
        "status": state.status.value,
        "carrier": state.carrier,
        "eta_start": eta.start.isoformat() if eta and eta.start else None,
        "eta_end": eta.end.isoformat() if eta and eta.end else None,
        "private": parcel.private,
        "owners": list(state.owners),
    }
    if not parcel.private:
        payload["merchant"] = state.merchant
        payload["tracking_number"] = state.tracking_number
    return payload
