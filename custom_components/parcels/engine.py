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
from collections.abc import (
    AsyncIterator,
    Callable,
    Coroutine,
    Iterable,
    Mapping,
    Sequence,
)
from contextlib import asynccontextmanager
import copy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta, tzinfo
import hashlib
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .ai_worker import AIWorker, error_location
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
    REASON_AI_FILL,
    REASON_AI_REJECTED,
    REASON_LOW_CONFIDENCE,
    REASON_RESTORED,
    REASON_UNKNOWN_FORMAT,
    REASON_UNKNOWN_SENDER,
    SIGNAL_AI_UPDATED,
    SIGNAL_DATA_UPDATED,
    AIMode,
    MailKind,
    ParcelStatus,
)
from .convert import (
    fill_contribution,
    fill_fields,
    fill_gaps,
    is_confident,
    message_origin_id,
    result_contributions,
    suggestion_from_result,
    suggestion_result,
)
from .customer_returns import (
    apply_return,
    infer_return_deliveries,
    mark_return_picked_up,
    pickup_suggestion,
    remove_return,
    return_origin,
)
from .dedup import (
    AMAZON_LINKS_KEY,
    AMAZON_REPAIR_KEY,
    HELD_GUESSES,
    ORDER_FOLD_KEY,
    PLACEHOLDER_REPAIR_KEY,
    REPAIR_KEY,
    REPAIR_VERSION,
    Contribution,
    DedupError,
    JoinKey,
    MergeSuggestion,
    accept_suggestion,
    add_owner,
    add_owner_to,
    amazon_shipment_id_counts,
    apply_contribution,
    archive_parcel,
    dismiss_suggestion,
    fill_shop,
    fold_known_orders,
    infer_deliveries,
    join_keys,
    manual_origin_id,
    mark_delivered,
    merge_parcels,
    message_outputs,
    message_shells,
    number_key_text,
    reconcile,
    remove_message,
    remove_origins,
    remove_owner_from,
    remove_parcel_origins,
    remove_return_origins,
    repair_store,
    restore_cancellations,
    restore_flag,
    revive_shell,
    split_parcel,
    undo_auto_merge,
    undo_delivery,
    update_parcel,
)
from .mail.errors import MAILBOX_ERRORS, MailNotFound
from .models import (
    FILL_ORIGIN_SUFFIX,
    FINAL_ATTEMPTS,
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
    carrier_like,
    dt_from_str,
    dt_to_str,
    is_carrier_mail,
    new_id,
)
from .parcelapp.sync import DATES_REPAIR_KEY, repair_parcel_dates
from .parsers import NOTE_KNOWN_SENDER_UNPARSED, is_refund, parse_message
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
    PAACK_ID_RE,
    detect_carrier,
    normalize_tracking_number,
)
from .quiet import infer_quiet_deliveries
from .seventeentrack import (
    PICKUP_PLACES_KEY,
    PICKUPS_READ_KEY,
    PICKUPS_READ_VERSION,
    PICKUPS_REPAIR_KEY,
    PICKUPS_REREAD_KEY,
    TIMELESS_REPAIR_KEY,
    mark_timeless_news,
    repair_pickups,
    restore_pickup_places,
)
from .siblings import infer_shipment_deliveries
from .store import FORGOTTEN_KEY, ParcelsStore, apply_retention, forgotten_before
from .workdays import WorkingDays

if TYPE_CHECKING:
    from .coordinator import MailboxCoordinator
    from .mail import MailClient, MessageMeta
    from .notifier import Notifier
    from .parcelapp.sync import ParcelAppSync
    from .seventeentrack import SeventeenTrackSync

_LOGGER = logging.getLogger(__name__)

# Called with the keys a parcel the user adds or edits can join others by;
# raises to refuse them.
type KeyCheck = Callable[[set[JoinKey]], None]

# Events are only fired for changes that happened recently, so the first
# sync of a mailbox doesn't replay a month of deliveries.
EVENT_MAX_AGE = timedelta(days=1)
# An e-mail that fails to download or parse is tried again after these
# delays, one per failed try. After FINAL_ATTEMPTS tries, almost four days,
# Parcels gives up on it: Needs review shows it until the user retries or
# dismisses it.
RETRY_DELAYS = (
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=4),
    timedelta(hours=12),
    timedelta(days=1),
    timedelta(days=2),
)
# A try due this soon is made by the check at hand: checks run a little early.
RETRY_SLACK = timedelta(minutes=1)
# Each check tries at most this many failed e-mails, oldest first, and stops
# after this many failures when no download of the check worked.
RETRY_MAX = 20
RETRY_STOP = 3
# When most downloads of a check fail, Parcels downloads again up to
# PROBE_FETCHES e-mails it read before, newest first. When PROBE_FAILURES of
# them fail too, or all that were tried, the mail server has a problem: the
# check fails, and no e-mail's tries count.
PROBE_FETCHES = 6
PROBE_FAILURES = 3
# A known sender whose e-mails the parser can't read this often within the
# window raises a repair issue; failures are remembered for UNPARSED_KEEP.
UNPARSED_THRESHOLD = 2
UNPARSED_WINDOW = timedelta(days=7)
UNPARSED_KEEP = timedelta(days=30)
MIN_NUMBER_CHARS = 5
# The diagnostics show the sender checks of this many e-mails under review.
MAX_SENDER_CHECKS = 20
# "Check again" reads at most this many of a parcel's e-mails, newest first.
CHECK_AGAIN_MAX_EMAILS = 5
# Set once the first mailbox sync after the update checked what an earlier
# release stored: open parcels without a date or items, and e-mails refused
# for their mail server (0.1.3 didn't know Outlook.com's).
FILL_CHECK_KEY = "fill_check"
# How many refund e-mails were dropped: they're not parcel events.
REFUNDS_KEY = "refunds_dropped"
# Set when the store of an earlier release is loaded. Once the mailboxes were
# read, what that release read is checked again: it couldn't tell refunds and
# customer returns apart, and its filter skipped some return e-mails. Then it
# holds what the check found.
RETURNS_CHECK_KEY = "returns_check"
# The returns check downloads at most this many e-mails, newest first...
RETURNS_CHECK_MAX = 100
# ... and looks at e-mails set aside only if they arrived this recently.
RETURNS_CHECK_WINDOW = timedelta(days=30)
# What an earlier release set aside, and could have misread.
SET_ASIDE = frozenset(
    {
        MessageState.NOT_PARCEL,
        MessageState.IGNORED,
        MessageState.DISMISSED,
        MessageState.FAILED,
        MessageState.FILTERED,
        MessageState.REVIEW,
    }
)
# The diagnostics count the e-mails of this many recent days.
RECENT_DAYS = 14
REASON_UNTRUSTED_SERVER = "untrusted_authserv"
# Set once the first mailbox sync after the update read again the Paack
# e-mails under review whose AI reading was rejected: earlier releases
# couldn't read Paack's order IDs.
PAACK_CHECK_KEY = "paack_check"
# The same for Leroy Merlin's e-mails, which earlier releases had no parser for.
LEROYMERLIN_CHECK_KEY = "leroymerlin_check"
# Set when the store of an earlier release is loaded. Once the mailboxes were
# read, Paack's recent e-mails whose parcels name no shop are read again by
# the parsers: releases before 0.1.7 couldn't read the shop. Then it holds
# what the check found.
PAACK_SHOP_CHECK_KEY = "paack_shop_check"
# The check reads Paack's e-mails of this many recent days...
PAACK_SHOP_CHECK_WINDOW = timedelta(days=14)
# ... at most this many, newest first.
PAACK_SHOP_CHECK_MAX = 50
# Set when the store of an earlier release is loaded. Once the mailboxes were
# read, Amazon's recent e-mails that the local AI read, or that wait in
# review, are read again by the parsers: releases before 0.1.16 couldn't read
# Amazon's Portuguese order confirmations. Then it holds what the check found.
AMAZON_AI_CHECK_KEY = "amazon_ai_check"
# The check reads Amazon's e-mails of this many recent days...
AMAZON_AI_CHECK_WINDOW = timedelta(days=30)
# ... at most this many, newest first.
AMAZON_AI_CHECK_MAX = 100
# Set when the store of an earlier release is loaded. Once the mailboxes were
# read, Amazon's recent e-mails whose only reading is a local AI answer that
# the user accepted are read again by the parsers, within the same days and
# limit as above; then Amazon's cancellations taken for partial ones cancel
# their parcel where it hasn't shipped. Then it holds what the check found.
AMAZON_ACCEPTED_CHECK_KEY = "amazon_accepted_check"
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def validation_error(key: str, **placeholders: str) -> ServiceValidationError:
    """Return a translated error for a bad request."""
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def manual_carrier(value: str, carrier: str | None) -> str | None:
    """Return the carrier of a number the user typed: theirs, or Paack's.

    Only Paack's order IDs have their shape, so a typed one is Paack's.
    """
    if carrier:
        return carrier
    return "paack" if PAACK_ID_RE.fullmatch(normalize_tracking_number(value)) else None


def manual_number(value: str, carrier: str | None = None) -> str:
    """Return a tracking number the user typed, normalised, or raise.

    A Paack order ID keeps its case and its "_1" suffix, for Paack only.
    """
    number = normalize_tracking_number(value)
    if carrier == "paack" and PAACK_ID_RE.fullmatch(number):
        return number
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


def _paack_rejected(item: ReviewItem) -> bool:
    """Return True for an e-mail from or about Paack whose AI reading was rejected."""
    if item.reason != REASON_AI_REJECTED:
        return False
    info = lookup(item.sender_domain)
    return (info is not None and info.carrier == "paack") or (
        item.suggestion is not None and item.suggestion.carrier == "paack"
    )


def _leroymerlin_rejected(item: ReviewItem) -> bool:
    """Return True for Leroy Merlin's e-mail whose AI reading was rejected."""
    if item.reason != REASON_AI_REJECTED:
        return False
    info = lookup(item.sender_domain)
    return info is not None and info.parser == "leroymerlin"


def _aware(value: datetime) -> datetime:
    """Return ``value`` with a time zone; naive values are UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _domain(address: str) -> str:
    """Return the lowercased domain of an address or a bare domain."""
    return address.rpartition("@")[2].strip().lower().rstrip(">")


# An e-mail whose headers failed to download is stored under this prefix and
# a hash of its mailbox and provider ID, until its headers are read.
UNREAD_PREFIX = "u:"


def unread_key(entry_id: str, provider_id: str) -> str:
    """Return the key of an e-mail of a mailbox whose headers aren't read."""
    digest = hashlib.sha256(f"{entry_id}|{provider_id}".encode()).hexdigest()
    return UNREAD_PREFIX + digest[:32]


def is_unread_key(key: str) -> bool:
    """Return True for the key of an e-mail whose headers aren't read."""
    return key.startswith(UNREAD_PREFIX)


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
class MailCheck:
    """What one check of a mailbox downloaded, to tell outages apart.

    With ``retry_all``, as for a refresh the user asked for, failed e-mails
    are tried before their time; those tries (``early``) don't count.
    """

    retry_all: bool = False
    # The e-mails whose download failed in this check, with the error.
    failed: dict[str, Exception] = field(default_factory=dict)
    early: set[str] = field(default_factory=set)
    # The e-mails this check downloaded or tried.
    tried: set[str] = field(default_factory=set)
    # How many downloads worked.
    ok: int = 0


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
        self.parcelapp: ParcelAppSync | None = None
        self.ai = AIWorker(self)
        self.workdays = WorkingDays(hass)
        self.mailboxes: dict[str, MailboxRuntime] = {}
        self._statuses: dict[str, ParcelStatus] = {}
        self._inflight: dict[str, asyncio.Event] = {}
        # Old e-mails listed again after Parcels forgot them, since the start.
        self._old_skipped = 0
        self._unsubs: list[CALLBACK_TYPE] = []
        self._started = False
        # Mailboxes being read, and mailboxes with more e-mails to read soon.
        # Parcels are reconciled once all of them are done.
        self._syncing: set[str] = set()
        self._more: set[str] = set()
        self._reconciling = False
        self._suggestions: dict[str, MergeSuggestion] = {}
        # Parcels whose delivery the user is taking back.
        self._taken_back: set[str] = set()

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
        await self.workdays.async_load(dt_util.now(self.tz).date())
        data = self.data
        data.engine.setdefault("synced", {})
        now = dt_util.utcnow()
        if int(data.engine.get(REPAIR_KEY) or 0) < REPAIR_VERSION:
            self._repair(now)
        if DATES_REPAIR_KEY not in data.engine:
            # Before the Parcel app source starts: without a key, it forgets
            # its deliveries.
            fixed = repair_parcel_dates(data, now, self.tz)
            data.engine[DATES_REPAIR_KEY] = fixed
            if fixed:
                _LOGGER.info("Parcels placed Parcel app events on %d parcels", fixed)
            self.store.async_schedule_save()
        if PICKUPS_REPAIR_KEY not in data.engine:
            data.engine[PICKUPS_REPAIR_KEY] = repair_pickups(data, now, self.tz)
            self.store.async_schedule_save()
        if PICKUP_PLACES_KEY not in data.engine:
            data.engine[PICKUP_PLACES_KEY] = restore_pickup_places(data, now, self.tz)
            self.store.async_schedule_save()
        if int(data.engine.get(PICKUPS_READ_KEY) or 0) < PICKUPS_READ_VERSION:
            data.engine[PICKUPS_REREAD_KEY] = repair_pickups(data, now, self.tz)
            data.engine[PICKUPS_READ_KEY] = PICKUPS_READ_VERSION
            self.store.async_schedule_save()
        if TIMELESS_REPAIR_KEY not in data.engine:
            data.engine[TIMELESS_REPAIR_KEY] = mark_timeless_news(data, now)
            self.store.async_schedule_save()
        if ORDER_FOLD_KEY not in data.engine:
            data.engine[ORDER_FOLD_KEY] = fold_known_orders(data, now)
            self.store.async_schedule_save()
        if not (data.parcels or data.review):
            # Nothing stored by an earlier release to check after the update.
            data.engine.setdefault(FILL_CHECK_KEY, True)
        for key in (
            RETURNS_CHECK_KEY,
            PAACK_SHOP_CHECK_KEY,
            AMAZON_AI_CHECK_KEY,
            AMAZON_ACCEPTED_CHECK_KEY,
        ):
            data.engine.setdefault(
                key,
                {"before": dt_to_str(now)}
                if data.messages
                else {"done": dt_to_str(now)},
            )
        self._statuses = {pid: p.state.news_status for pid, p in data.parcels.items()}
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
        self.async_create_task(
            self.workdays.async_load(dt_util.now(self.tz).date()), "parcels_workdays"
        )
        self.async_changed()
        self.ai.wake()

    @callback
    def _repair(self, now: datetime) -> None:
        """Fix what earlier releases stored, once per repair version.

        The steps of the versions the store already had are skipped. Parcels
        are reconciled right after, as on every start.
        """
        data = self.data
        since = int(data.engine.get(REPAIR_KEY) or 0)
        changed = repair_store(data, now, since=since)
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
    def end_sync(self, entry_id: str, *, more: bool, ok: bool = True) -> None:
        """Note that a mailbox was read; ``more`` when it continues soon.

        Once no mailbox is being read, parcels are reconciled. After the first
        sync that worked, what an earlier release stored is checked once.
        """
        self._syncing.discard(entry_id)
        if more:
            self._more.add(entry_id)
        else:
            self._more.discard(entry_id)
        if self._reconcile(dt_util.utcnow()):
            self.async_changed(reconcile=False)
        if ok and self._started and not (self._syncing or self._more):
            self._start_checks()

    @callback
    def _start_checks(self) -> None:
        """Start the one-time checks of what an earlier release stored.

        Every mailbox lists its lookback period again on its next sync, as on
        its first: what the filter of an earlier release skipped is read then.
        """
        engine = self.data.engine
        check = engine.get(RETURNS_CHECK_KEY)
        before = None
        if isinstance(check, dict) and not {"started", "done"} & check.keys():
            before = dt_from_str(check.get("before"))
        shop_check = engine.get(PAACK_SHOP_CHECK_KEY)
        shops = None
        if isinstance(shop_check, dict) and not {"started", "done"} & shop_check.keys():
            shops = dt_from_str(shop_check.get("before"))
        amazon_check = engine.get(AMAZON_AI_CHECK_KEY)
        amazon_ai = None
        if (
            isinstance(amazon_check, dict)
            and not {"started", "done"} & amazon_check.keys()
        ):
            amazon_ai = dt_from_str(amazon_check.get("before"))
        accepted_check = engine.get(AMAZON_ACCEPTED_CHECK_KEY)
        accepted = None
        if (
            isinstance(accepted_check, dict)
            and not {"started", "done"} & accepted_check.keys()
        ):
            accepted = dt_from_str(accepted_check.get("before"))
        fill = not engine.get(FILL_CHECK_KEY)
        paack = not engine.get(PAACK_CHECK_KEY)
        leroymerlin = not engine.get(LEROYMERLIN_CHECK_KEY)
        if (
            before is None
            and shops is None
            and amazon_ai is None
            and accepted is None
            and not (fill or paack or leroymerlin)
        ):
            return
        if before is not None:
            check["started"] = dt_to_str(dt_util.utcnow())
            check["relisted"] = self._relist()
        if shops is not None:
            shop_check["started"] = dt_to_str(dt_util.utcnow())
        if amazon_ai is not None:
            amazon_check["started"] = dt_to_str(dt_util.utcnow())
        if accepted is not None:
            accepted_check["started"] = dt_to_str(dt_util.utcnow())
        engine[FILL_CHECK_KEY] = True
        engine[PAACK_CHECK_KEY] = True
        engine[LEROYMERLIN_CHECK_KEY] = True
        self.async_schedule_save()
        self.async_create_task(
            self._async_checks(
                before,
                shops=shops,
                amazon_ai=amazon_ai,
                accepted=accepted,
                fill=fill,
                paack=paack,
                leroymerlin=leroymerlin,
            ),
            "parcels checks",
        )

    @callback
    def _relist(self) -> int:
        """Have every mailbox read its lookback period again; return how many.

        E-mails read before are skipped as always.
        """
        data = self.data
        synced = data.engine.setdefault("synced", {})
        entry_ids = {*data.cursors, *synced}
        for entry_id in entry_ids:
            data.cursors.pop(entry_id, None)
            synced.pop(entry_id, None)
        return len(entry_ids)

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
            # A return is stronger evidence than another package of the
            # shipment, which is stronger than another parcel of the shop, and
            # all are stronger than three weeks without news.
            inferred = infer_return_deliveries(data, now)
            inferred |= infer_shipment_deliveries(data, now)
            inferred |= infer_deliveries(data, now)
            inferred |= infer_quiet_deliveries(data, now)
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
                "Retention archived %d and purged %d parcels, archived %d and "
                "purged %d returns",
                len(result.archived),
                len(result.purged),
                len(result.returns_archived),
                len(result.returns_purged),
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
            previous = self._statuses.get(parcel.id)
            # An inferred delivery isn't news: nothing reported it. Neither
            # is taking it back, and a delivery reported later is. News read
            # with it waits for one of them, told from the last status told.
            if state.inferred:
                if previous is not None:
                    statuses[parcel.id] = previous
                continue
            statuses[parcel.id] = state.status
            if previous == state.status or parcel.archived is not None:
                continue
            # A delivery taken back was news: so is what it goes back to.
            taken_back = (
                parcel.id in self._taken_back and previous is ParcelStatus.DELIVERED
            )
            happened = state.status_time
            if happened is not None and state.status_timeless:
                # Only its day is known: it can have happened until that day ended.
                happened = dt_util.start_of_local_day(
                    dt_util.as_local(happened).date() + timedelta(days=1)
                )
            old = not taken_back and (
                happened is None or now - happened > EVENT_MAX_AGE
            )
            if state.status_undated and old:
                # When it happened isn't known: a dated report may tell later,
                # and then it's news.
                if previous is None:
                    del statuses[parcel.id]
                else:
                    statuses[parcel.id] = previous
                continue
            if state.status_time is not None and old:
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
        self._apply_owner(mailbox)
        self.ai.wake()

        @callback
        def remove() -> None:
            if self.mailboxes.get(mailbox.entry_id) is mailbox:
                del self.mailboxes[mailbox.entry_id]
                self._syncing.discard(mailbox.entry_id)
                self._more.discard(mailbox.entry_id)

        return remove

    @callback
    def _apply_owner(self, mailbox: MailboxRuntime) -> None:
        """Make a mailbox's owner the owner of the e-mails it read before.

        The owner can be chosen, or changed, after the mailbox was read. The
        former owner is taken off its e-mails, unless another mailbox that has
        them is theirs too. Reviews of the mailbox and of those e-mails get
        their owner again, as when they were made. A mailbox of an earlier
        release, which didn't keep the owner it applied, only gets its owner
        added.
        """
        data = self.data
        entry_id = mailbox.entry_id
        new = mailbox.owner
        applied: dict[str, str] = data.engine.setdefault("owners", {})
        known = entry_id in applied
        old = applied.get(entry_id) or None
        if known and old == new:
            return
        applied[entry_id] = new or ""
        if new is None and not known:
            self.async_schedule_save()
            return
        now = dt_util.utcnow()
        entries = self.hass.config_entries

        def configured(ref: str | None) -> str | None:
            other = entries.async_get_entry(ref) if ref else None
            return (other.options.get(CONF_OWNER) or None) if other else None

        dropped: set[str] = set()
        added: set[str] = set()
        for key, record in data.messages.items():
            if entry_id not in record.refs:
                continue
            owners = list(record.owners)
            at = len(owners)
            if (
                old is not None
                and old in owners
                and not any(configured(ref) == old for ref in record.refs)
            ):
                at = owners.index(old)
                owners.remove(old)
                dropped.add(key)
            if new is not None and new not in owners:
                owners.insert(at, new)
                added.add(key)
            record.owners = tuple(owners)
        if old is not None and dropped:
            remove_owner_from(data, dropped, old, now)
        if new is not None and added:
            add_owner_to(data, added, new, now)
        changed = dropped | added

        def owner_of(
            message: str | None, ref: str | None, current: str | None
        ) -> str | None:
            # As when the review was made: its e-mail's first owner, else the
            # owner of its mailbox. A removed mailbox has none.
            if ref != entry_id and message not in changed:
                return current
            record = data.messages.get(message) if message else None
            if record is not None and record.owners:
                return record.owners[0]
            return configured(ref)

        touched = False
        for item in data.review.values():
            owner = owner_of(item.message, item.mailbox, item.owner)
            if owner != item.owner:
                item.owner = owner
                touched = True
        queued = False
        for entry in self.ai.queue:
            review = entry["review"]
            owner = owner_of(
                entry.get("hash"), review.get("mailbox"), review.get("owner")
            )
            if owner != review.get("owner"):
                review["owner"] = owner
                queued = True
        if queued:
            async_dispatcher_send(self.hass, SIGNAL_AI_UPDATED)
        if changed or touched:
            self.async_changed()
        else:
            self.async_schedule_save()

    @callback
    def async_forget_mailbox(self, entry_id: str) -> None:
        """Drop the sync state and e-mail references of a removed mailbox."""
        data = self.data
        data.cursors.pop(entry_id, None)
        data.engine.get("synced", {}).pop(entry_id, None)
        data.engine.get("owners", {}).pop(entry_id, None)
        for key, record in list(data.messages.items()):
            record.refs.pop(entry_id, None)
            if record.state is MessageState.FAILED and not record.refs:
                # Never read, and no mailbox left to read it from.
                del data.messages[key]
        self.async_schedule_save()

    @callback
    def _drop_unknown_mailboxes(self) -> None:
        known = {e.entry_id for e in self.hass.config_entries.async_entries(DOMAIN)}
        data = self.data
        stale = {
            *(key for key in data.cursors if key not in known),
            *(key for key in data.engine.get("synced", {}) if key not in known),
            *(key for key in data.engine.get("owners", {}) if key not in known),
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
        """Check every mailbox, 17TRACK and the Parcel app now.

        The mailboxes try the e-mails that failed at once, without counting
        the tries. The Parcel app is read only when its last read is ten
        minutes old.
        """
        for mailbox in list(self.mailboxes.values()):
            if (coordinator := mailbox.coordinator) is not None:
                coordinator.retry_now = True
                await coordinator.async_request_refresh()
        if self.tracker is not None:
            await self.tracker.async_refresh()
        if self.parcelapp is not None:
            await self.parcelapp.async_refresh()

    # -- E-mail intake ----------------------------------------------------

    async def async_process_mail(
        self,
        mailbox: MailboxRuntime,
        metas: Sequence[MessageMeta],
        *,
        first_sync: bool,
        check: MailCheck | None = None,
        unread: Mapping[str, Exception] | None = None,
    ) -> None:
        """Process new e-mails of a mailbox.

        Raises the mailbox's own errors (auth, rate limit, cursor, no
        mailbox). An e-mail that fails to download or parse is stored as
        failed and tried again later; ``check`` collects the downloads for
        async_finish_check. ``unread`` holds the e-mails listed whose headers
        failed to download, by provider ID: each is stored as failed, with
        no sender yet, and its headers are read again later.
        """
        check = MailCheck() if check is None else check
        changed = False
        # Oldest first: an e-mail never undoes what a newer one said, and
        # mail APIs list changes in any order.
        ordered = sorted(
            metas, key=lambda meta: (_aware(meta.received), meta.provider_id)
        )
        try:
            for meta in ordered:
                key = unread_key(mailbox.entry_id, meta.provider_id)
                if key in self.data.messages:
                    async with self._hold(key):
                        if (record := self.data.messages.get(key)) is not None:
                            if not self._retrying(record):
                                # Given up on, or dismissed: it stays unread.
                                continue
                            # Its headers downloaded at last.
                            self._drop_ref(record, mailbox.entry_id)
                            changed = True
                key = message_hash(
                    meta.message_id, meta.sender, meta.subject, meta.sent
                )
                # The same e-mail can arrive from two mailboxes at once.
                async with self._hold(key):
                    if await self._async_intake(
                        mailbox, meta, key, check, first_sync=first_sync
                    ):
                        changed = True
            if unread and await self._async_note_unread(mailbox, unread, check):
                changed = True
        finally:
            if changed:
                self.async_changed()

    async def _async_note_unread(
        self,
        mailbox: MailboxRuntime,
        unread: Mapping[str, Exception],
        check: MailCheck,
    ) -> bool:
        """Store the e-mails whose headers failed to download; True on changes.

        A new one counts as this check's failed try. One listed again before
        its next try counts only as an early try, as a refresh makes, and
        not at all in a check of its own. An e-mail the mailbox read before
        is left alone.
        """
        data = self.data
        entry_id = mailbox.entry_id
        known = {
            provider_id
            for record in data.messages.values()
            if not is_unread_key(record.hash)
            and (provider_id := record.refs.get(entry_id)) is not None
        }
        changed = False
        for provider_id, err in unread.items():
            if provider_id in known:
                continue
            key = unread_key(entry_id, provider_id)
            async with self._hold(key):
                now = dt_util.utcnow()
                if (record := data.messages.get(key)) is None:
                    check.tried.add(key)
                    check.failed[key] = err
                    data.messages[key] = MessageRecord(
                        hash=key,
                        seen=now,
                        state=MessageState.FAILED,
                        refs={entry_id: provider_id},
                        owners=_owners(mailbox.owner),
                        retry_at=now + RETRY_DELAYS[0],
                    )
                    changed = True
                    continue
                if not self._retrying(record) or key in check.tried:
                    continue
                check.tried.add(key)
                if record.retry_at <= now + RETRY_SLACK:  # type: ignore[operator]
                    check.failed[key] = err
                    # Not again before the check counts it.
                    record.retry_at = now + RETRY_DELAYS[0]
                elif check.retry_all:
                    check.failed[key] = err
                    check.early.add(key)
        return changed

    @asynccontextmanager
    async def _hold(self, key: str) -> AsyncIterator[None]:
        """Read an e-mail only once at a time."""
        while (pending := self._inflight.get(key)) is not None:
            await pending.wait()
        done = self._inflight[key] = asyncio.Event()
        try:
            yield
        finally:
            del self._inflight[key]
            done.set()

    async def _async_intake(
        self,
        mailbox: MailboxRuntime,
        meta: MessageMeta,
        key: str,
        check: MailCheck,
        *,
        first_sync: bool,
    ) -> bool:
        data = self.data
        now = dt_util.utcnow()
        if (record := data.messages.get(key)) is not None:
            return self._add_ref(record, mailbox, meta.provider_id, now)
        forgotten = forgotten_before(data)
        if forgotten is not None and _aware(meta.received) <= forgotten:
            # Read and forgotten: reading it again would bring back what
            # retention removed.
            self._old_skipped += 1
            return False
        domain = _domain(meta.sender)
        trusted = data.trusted_domains()
        if self.is_ignored(domain) or not is_candidate(
            meta.sender, meta.subject, meta.preview, trusted=trusted
        ):
            return False
        check.tried.add(key)
        try:
            message = await mailbox.client.async_fetch(meta.provider_id)
        except MailNotFound:
            return False
        except MAILBOX_ERRORS:
            raise
        except Exception as err:
            # Counted once the check knows whether the mail server failed.
            check.failed[key] = err
            data.messages[key] = MessageRecord(
                hash=key,
                seen=now,
                state=MessageState.FAILED,
                refs={mailbox.entry_id: meta.provider_id},
                received=_aware(meta.received),
                sender_domain=domain,
                owners=_owners(mailbox.owner),
                retry_at=now + RETRY_DELAYS[0],
            )
            return True
        check.ok += 1
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
        data.messages[key] = record
        try:
            verdict = self.verify(message)
            result = await self.async_parse(message, verdict)
        except Exception as err:
            record.state = MessageState.FAILED
            self._count_failure(record, err, now)
            return True
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

    # -- E-mails that failed ----------------------------------------------

    def _retrying(self, record: MessageRecord) -> bool:
        """Return True for a failed e-mail Parcels still tries."""
        return (
            record.state is MessageState.FAILED
            and record.retry_at is not None
            and not self.is_ignored(record.sender_domain)
        )

    def gave_up(self, record: MessageRecord) -> bool:
        """Return True for a failed e-mail Parcels no longer tries."""
        return (
            record.state is MessageState.FAILED
            and record.retry_at is None
            and not self.is_ignored(record.sender_domain)
        )

    def gave_up_emails(self) -> list[MessageRecord]:
        """Return the e-mails Parcels gave up on, newest first."""
        return sorted(
            (record for record in self.data.messages.values() if self.gave_up(record)),
            key=lambda record: (record.received or record.seen, record.hash),
            reverse=True,
        )

    def _count_failure(
        self, record: MessageRecord, err: Exception, now: datetime
    ) -> bool:
        """Count a failed try of an e-mail; True when Parcels gives up on it."""
        record.attempts += 1
        # Only where it failed: an error's message could quote the e-mail.
        location = error_location(err)
        if record.attempts >= FINAL_ATTEMPTS:
            record.retry_at = None
            if record.sender_domain:
                _LOGGER.warning(
                    "Couldn't read an e-mail from %s after %d tries (%s)",
                    record.sender_domain,
                    record.attempts,
                    location,
                )
            else:
                # Its headers never downloaded: the sender isn't known.
                _LOGGER.warning(
                    "Couldn't read an e-mail after %d tries (%s)",
                    record.attempts,
                    location,
                )
            return True
        record.retry_at = now + RETRY_DELAYS[record.attempts - 1]
        if record.sender_domain:
            _LOGGER.debug(
                "Couldn't read an e-mail from %s, try %d (%s)",
                record.sender_domain,
                record.attempts,
                location,
            )
        else:
            _LOGGER.debug(
                "Couldn't read an e-mail, try %d (%s)", record.attempts, location
            )
        return False

    async def async_finish_check(
        self, mailbox: MailboxRuntime, check: MailCheck
    ) -> Exception | None:
        """Try the mailbox's failed e-mails that are due, then count failures.

        When most downloads of the check failed, e-mails read before are
        downloaded again. When those fail too, the mail server has a
        problem: its error is returned, and no failure counts against an
        e-mail. Each is tried again with the next check.
        """
        changed = await self._async_retry_failed(mailbox, check)
        outage = None
        if len(check.failed) > check.ok:
            outage = await self._async_probe(mailbox, check)
        now = dt_util.utcnow()
        counted = False
        for key, err in check.failed.items():
            record = self.data.messages.get(key)
            if record is None or not self._retrying(record) or key in check.early:
                continue
            counted = True
            if outage is not None:
                record.retry_at = now + RETRY_DELAYS[0]
            elif self._count_failure(record, err, now):
                changed = True
        if changed:
            self.async_changed()
        elif counted:
            self.async_schedule_save()
        return outage

    async def _async_retry_failed(
        self, mailbox: MailboxRuntime, check: MailCheck
    ) -> bool:
        """Try the failed e-mails of a mailbox that are due; True on changes.

        Oldest first, at most RETRY_MAX. The tries stop after RETRY_STOP
        failures while no download of the check worked.
        """
        data = self.data
        entry_id = mailbox.entry_id
        now = dt_util.utcnow()
        due = now + RETRY_SLACK

        def wanted(record: MessageRecord) -> bool:
            return (
                self._retrying(record)
                and record.hash not in check.tried
                and entry_id in record.refs
                and (check.retry_all or record.retry_at <= due)  # type: ignore[operator]
            )

        candidates = sorted(
            (record for record in data.messages.values() if wanted(record)),
            key=lambda record: (record.received or record.seen, record.hash),
        )
        changed = False
        failures = 0
        for record in candidates[:RETRY_MAX]:
            if failures >= RETRY_STOP and not check.ok:
                break
            key = record.hash
            async with self._hold(key):
                if data.messages.get(key) is not record or not wanted(record):
                    continue
                check.tried.add(key)
                early = record.retry_at > due  # type: ignore[operator]
                if early:
                    check.early.add(key)
                if is_unread_key(key):
                    try:
                        await self._async_read_unread(record, mailbox, check)
                    except MAILBOX_ERRORS:
                        raise
                    except Exception as err:
                        check.failed[key] = err
                        failures += 1
                        if not early:
                            record.retry_at = now + RETRY_DELAYS[0]
                    else:
                        changed = True
                    continue
                try:
                    message = await mailbox.client.async_fetch(record.refs[entry_id])
                except MailNotFound:
                    self._drop_ref(record, entry_id)
                    changed = True
                    continue
                except MAILBOX_ERRORS:
                    raise
                except Exception as err:
                    check.failed[key] = err
                    failures += 1
                    if not early:
                        # Not again before the check counts it.
                        record.retry_at = now + RETRY_DELAYS[0]
                    continue
                check.ok += 1
                await self._async_read_failed(
                    record, message, mailbox, now, early=early
                )
                changed = True
        return changed

    def _drop_ref(self, record: MessageRecord, entry_id: str) -> None:
        """Forget a deleted copy of a failed e-mail, and the e-mail with the last."""
        record.refs.pop(entry_id, None)
        if not record.refs and self.data.messages.get(record.hash) is record:
            del self.data.messages[record.hash]

    async def _async_read_unread(
        self, record: MessageRecord, mailbox: MailboxRuntime, check: MailCheck
    ) -> str | None:
        """Read the headers of an e-mail that failed to, then the e-mail.

        Raises when the headers fail again, or the mailbox does. Otherwise
        the e-mail is read as a new one, and its key returned; the record
        of its headers is forgotten, as is a deleted e-mail's, for which
        None is returned. Only an e-mail about a parcel is downloaded.
        """
        entry_id = mailbox.entry_id
        try:
            meta = await mailbox.client.async_fetch_meta(record.refs[entry_id])
        except MailNotFound:
            meta = None
        if meta is None:
            self._drop_ref(record, entry_id)
            return None
        check.ok += 1
        key = message_hash(meta.message_id, meta.sender, meta.subject, meta.sent)
        async with self._hold(key):
            await self._async_intake(mailbox, meta, key, check, first_sync=True)
        self._drop_ref(record, entry_id)
        return key

    async def _async_read_failed(
        self,
        record: MessageRecord,
        message: MailMessage,
        mailbox: MailboxRuntime,
        now: datetime,
        *,
        early: bool,
    ) -> bool:
        """Read a failed e-mail that downloaded at last; True when it was.

        It's decided as on a first sync. Failing to parse it counts as a try,
        unless the try was early.
        """
        data = self.data
        key = record.hash
        alias = message.hash
        if alias != key and (existing := data.messages.get(alias)) is not None:
            # Read before under its other key.
            del data.messages[key]
            for entry_id, provider_id in record.refs.items():
                existing.refs.setdefault(entry_id, provider_id)
            for owner in record.owners:
                if owner not in existing.owners:
                    existing.owners = (*existing.owners, owner)
                    add_owner(data, alias, owner, now)
            return True
        record.received = _aware(message.received or record.received or now)
        record.sender_domain = message.sender_domain or record.sender_domain
        try:
            verdict = self.verify(message)
            result = await self.async_parse(message, verdict)
        except Exception as err:
            if not early and self._retrying(record):
                self._count_failure(record, err, now)
            return False
        if data.messages.get(key) is not record or record.state is not (
            MessageState.FAILED
        ):
            return False
        record.state = MessageState.IGNORED
        record.attempts = 0
        record.retry_at = None
        self._decide(
            message,
            verdict,
            result,
            record,
            mailbox=mailbox.entry_id,
            owner=record.owners[0] if record.owners else mailbox.owner,
            first_sync=True,
            now=now,
        )
        return True

    async def _async_probe(
        self, mailbox: MailboxRuntime, check: MailCheck
    ) -> Exception | None:
        """Download e-mails read before; return the error when they fail too.

        Newest first, until one downloads or PROBE_FAILURES fail. Without
        such e-mails, the failures count against the e-mails.
        """
        entry_id = mailbox.entry_id
        candidates = sorted(
            (
                record
                for record in self.data.messages.values()
                if record.state is not MessageState.FAILED
                and record.attempts == 0
                and entry_id in record.refs
                and record.hash not in check.tried
            ),
            key=lambda record: (record.received or record.seen, record.hash),
            reverse=True,
        )
        failure: Exception | None = None
        failures = 0
        for record in candidates[:PROBE_FETCHES]:
            if (provider_id := record.refs.get(entry_id)) is None:
                continue
            try:
                await mailbox.client.async_fetch(provider_id)
            except MailNotFound:
                continue
            except MAILBOX_ERRORS:
                raise
            except Exception as err:
                failure = err
                failures += 1
                if failures >= PROBE_FAILURES:
                    break
            else:
                return None
        return failure

    async def async_retry_gave_up(self) -> dict[str, int]:
        """Try once more the e-mails Parcels gave up on, oldest first.

        From any mailbox that has them; one that fails stays given up.
        """
        data = self.data
        counts = dict.fromkeys(("read", "failed", "gone"), 0)
        changed = False
        for record in reversed(self.gave_up_emails()):
            key = record.hash
            async with self._hold(key):
                if data.messages.get(key) is not record or not self.gave_up(record):
                    continue
                if is_unread_key(key):
                    outcome = await self._async_retry_unread(record)
                    counts[outcome] += 1
                    changed = changed or data.messages.get(key) is not record
                    continue
                fetched = await self.async_refetch(record)
                if data.messages.get(key) is not record or not self.gave_up(record):
                    continue
                if fetched.message is None or fetched.mailbox is None:
                    if fetched.gone:
                        del data.messages[key]
                        counts["gone"] += 1
                        changed = True
                    else:
                        counts["failed"] += 1
                    continue
                if await self._async_read_failed(
                    record,
                    fetched.message,
                    fetched.mailbox,
                    dt_util.utcnow(),
                    early=True,
                ):
                    counts["read"] += 1
                    changed = True
                else:
                    counts["failed"] += 1
        if changed:
            self.async_changed()
        return counts

    async def _async_retry_unread(self, record: MessageRecord) -> str:
        """Try again an e-mail given up on whose headers never downloaded.

        Returns "read", "gone", or "failed" when it stays given up: also
        when its headers download but the e-mail doesn't, or can't be read.
        Its sender is then known.
        """
        data = self.data
        mailbox = next(
            (
                mailbox
                for entry_id in record.refs
                if (mailbox := self.mailboxes.get(entry_id)) is not None
            ),
            None,
        )
        if mailbox is None:
            return "failed"
        check = MailCheck()
        try:
            key = await self._async_read_unread(record, mailbox, check)
        except Exception as err:
            # Only where it failed: an error's message could quote the e-mail.
            _LOGGER.debug("Download failed (%s)", error_location(err))
            return "failed"
        if key is None:
            return "gone"
        if key not in check.tried:
            # Read before, not about a parcel, or from an ignored sender.
            return "read"
        if (read := data.messages.get(key)) is None:
            # Read before under another key, or deleted meanwhile: only its
            # headers downloaded.
            return "read" if check.ok > 1 else "gone"
        if read.state is MessageState.FAILED:
            # It stays given up, now with its sender.
            read.attempts = max(read.attempts, record.attempts)
            read.retry_at = None
            return "failed"
        return "read"

    @callback
    def dismiss_gave_up(self) -> int:
        """Leave the e-mails Parcels gave up on unread; return how many."""
        records = self.gave_up_emails()
        for record in records:
            record.state = MessageState.DISMISSED
        if records:
            self.async_changed()
        return len(records)

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

    async def async_read(
        self, message: MailMessage
    ) -> tuple[SenderVerdict, ParseResult] | None:
        """Check and parse an e-mail read again; None when that fails.

        Where e-mails are read again, one that the parsers fail on counts as
        not read, and the others are still read.
        """
        try:
            verdict = self.verify(message)
            return verdict, await self.async_parse(message, verdict)
        except Exception as err:
            # Only where it failed: an error's message could quote the e-mail.
            _LOGGER.warning(
                "Couldn't read an e-mail from %s again (%s)",
                message.sender_domain,
                error_location(err),
            )
            return None

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
        reread: bool = False,
    ) -> None:
        """Apply, queue, review, filter or ignore a parsed e-mail.

        An e-mail read again (``reread``) keeps its parcels until a new
        reading replaces them: under review, or while the local AI reads it,
        they stay as they were.
        """
        org = organizational_domain(message.sender_domain)
        if reread:
            self._clear_lists(record.hash)
        if result.kind is MailKind.NOT_PARCEL and result.confidence >= CONFIDENCE_APPLY:
            if reread:
                self.clear_outputs(record.hash, now)
            if is_refund(result):
                self.drop_refund(record)
            else:
                record.state = MessageState.NOT_PARCEL
            return
        if result.kind is MailKind.CUSTOMER_RETURN:
            self.decide_return(
                message,
                verdict,
                result,
                record,
                mailbox=mailbox,
                owner=owner,
                now=now,
                reread=reread,
            )
            return
        raw = suggestion_from_result(result)
        if is_confident(result):
            if verdict.verified:
                if reread:
                    self.clear_outputs(record.hash, now)
                self.apply_result(
                    result,
                    record,
                    source=Source.PARSER,
                    time=self.message_time(message, now),
                    label=org,
                    now=now,
                )
                received = record.received or now
                if not (
                    (
                        not first_sync
                        or now - received <= timedelta(days=AI_FIRST_SYNC_DAYS)
                    )
                    and self.queue_fill(
                        message,
                        verdict,
                        result,
                        record,
                        mailbox=mailbox,
                        owner=owner,
                        now=now,
                    )
                ):
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
        if (
            raw is None
            and not result.is_parcel
            and not (reread and message_outputs(self.data, record.hash))
        ):
            # Junk guard: e-mails that matched a keyword but hold nothing
            # parcel-like stay out of the review list. One that is part of a
            # parcel goes there: the parcel stays until the user decides.
            if not verdict.authenticated:
                record.state = MessageState.IGNORED
                return
            if not verdict.known:
                self.add_filtered(item, record)
                return
        self.add_review(item, record)

    def decide_return(
        self,
        message: MailMessage,
        verdict: SenderVerdict,
        result: ParseResult,
        record: MessageRecord,
        *,
        mailbox: str | None,
        owner: str | None,
        now: datetime,
        reread: bool = False,
    ) -> None:
        """Add a customer return, or send it to "Needs review".

        The local AI doesn't read returns, and a return has nothing for it
        to fill in. Under review, the pickup day stays in the suggestion, and
        an e-mail read again (``reread``) stays part of its parcels.
        """
        org = organizational_domain(message.sender_domain)
        if verdict.verified and is_confident(result):
            if reread:
                self.clear_outputs(record.hash, now)
            self.apply_result(
                result,
                record,
                source=Source.PARSER,
                time=self.message_time(message, now),
                label=org,
                now=now,
            )
            self._clear_unparsed(org)
            return
        self.add_review(
            self.review_item(
                message,
                record,
                verdict,
                reason=review_reason(verdict, result),
                source=Source.PARSER,
                suggestion=self.suggestion_for(result, message, now),
                mailbox=mailbox,
                owner=owner,
                now=now,
            ),
            record,
        )

    def suggestion_for(
        self, result: ParseResult, message: MailMessage, now: datetime
    ) -> Suggestion | None:
        """Return the "Needs review" suggestion for a reading of an e-mail.

        A return's "next working day" pickup becomes a date: a suggestion
        only holds dates, and accepting it would otherwise lose the day.
        """
        return pickup_suggestion(
            self.prefill(suggestion_from_result(result), message.sender_domain),
            result,
            time=self.message_time(message, now),
            next_working_day=self.workdays.next_working_day,
        )

    def drop_refund(self, record: MessageRecord) -> None:
        """Drop a refund e-mail, counting it once: it isn't a parcel event.

        It never reaches a parcel, review or the filtered list.
        """
        if record.state is not MessageState.NOT_PARCEL:
            engine = self.data.engine
            engine[REFUNDS_KEY] = int(engine.get(REFUNDS_KEY) or 0) + 1
        record.state = MessageState.NOT_PARCEL

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
        keep_closed: bool = False,
    ) -> set[str]:
        """Add a parse result to the parcels; returns the touched parcel IDs.

        A customer return goes to the returns instead. Whatever the e-mail
        said before (as a parcel or as a return) gives way to the result.
        With ``keep_closed``, a parcel put away or closed stays so: the
        e-mail was read before, so it isn't news. An e-mail read again goes
        back to the parcels it was part of (its record's shells), which keep
        their IDs, privacy and flags and stay closed.
        """
        owners = record.owners
        shells, record.shells = record.shells, ()
        if result.kind is MailKind.CUSTOMER_RETURN:
            moved = remove_parcel_origins(self.data, record.hash, now)
            apply_return(
                self.data,
                return_origin(
                    result,
                    message_hash=record.hash,
                    time=time,
                    source=source,
                    label=label,
                    owners=owners,
                    next_working_day=self.workdays.next_working_day,
                ),
                now,
            )
            record.state = MessageState.APPLIED
            return moved
        remove_return_origins(self.data, record.hash, now)
        by_origin = {oid: shell for shell in shells for oid in shell.origins}
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
            # Every mailbox's owner at once: a guess must not show a private
            # parcel to any of them (see dedup.hold_guess()).
            contribution.origin.owners = tuple(
                sorted({*contribution.origin.owners, *owners})
            )
            if (shell := by_origin.get(contribution.origin.id)) is not None:
                if shell.lost:
                    pid, back = revive_shell(self.data, shell, now)
                    if back and shell.status is not None:
                        # The same parcel, back: not a new one.
                        self._statuses.setdefault(pid, shell.status)
                    contribution.parcel = pid
                else:
                    contribution.home = shell.id
                contribution.private = contribution.private or shell.private
            applied = apply_contribution(
                self.data,
                contribution,
                now,
                keep_closed=keep_closed or shell is not None,
            )
            if applied.parcel_id is not None:
                touched.add(applied.parcel_id)
        for owner in owners[1:]:
            touched |= add_owner(self.data, record.hash, owner, now)
        for shell in shells:
            if (flag := shell.auto_merged) is not None:
                holder = next(
                    (
                        parcel
                        for parcel in self.data.parcels.values()
                        if flag.origin in parcel.origins
                    ),
                    None,
                )
                if holder is not None:
                    restore_flag(holder, flag)
        record.state = MessageState.APPLIED
        return touched

    def fill_item(self, message_hash: str) -> ReviewItem | None:
        """Return the pending fill of the local AI for an e-mail."""
        return next(
            (
                item
                for item in self.data.review.values()
                if item.fill and item.message == message_hash
            ),
            None,
        )

    def fill_gaps_for(self, message_hash: str, result: ParseResult) -> set[str]:
        """Return what the local AI may still fill in for a parsed e-mail.

        Fields that a pending fill already offers aren't asked again.
        """
        anchor = message_origin_id(message_hash, 0)
        parcel = next(
            (p for p in self.data.parcels.values() if anchor in p.origins), None
        )
        if parcel is None:
            return set()
        gaps = fill_gaps(
            result, parcel.state, carrier_mail=is_carrier_mail(parcel.origins[anchor])
        )
        if (item := self.fill_item(message_hash)) is not None and item.suggestion:
            gaps -= fill_fields(item.suggestion)
        return gaps

    def queue_fill(
        self,
        message: MailMessage,
        verdict: SenderVerdict,
        result: ParseResult,
        record: MessageRecord,
        *,
        mailbox: str | None,
        owner: str | None,
        now: datetime,
        forced: bool = False,
    ) -> bool:
        """Queue a parsed e-mail for the local AI to fill in what's missing."""
        if not self.ai_active or not self.fill_gaps_for(record.hash, result):
            return False
        self.ai.enqueue(
            record.hash,
            received=record.received or now,
            review=self.review_item(
                message,
                record,
                verdict,
                reason=REASON_AI_FILL,
                source=Source.AI,
                suggestion=None,
                mailbox=mailbox,
                owner=owner,
                now=now,
            ),
            known=verdict.known,
            forced=forced,
            fill=True,
        )
        return True

    def apply_fill(
        self,
        suggestion: Suggestion,
        record: MessageRecord,
        *,
        time: datetime,
        label: str,
        now: datetime,
        confirmed: bool = False,
    ) -> str | None:
        """Add what the local AI filled in to the parcel of the parsed e-mail.

        Returns the parcel's ID, or None when that parcel is gone.
        """
        owners = record.owners
        contribution = fill_contribution(
            suggestion,
            message_hash=record.hash,
            time=time,
            label=label,
            owner=owners[0] if owners else None,
            confirmed=confirmed,
        )
        if contribution is None:
            return None
        contribution.origin.owners = tuple(
            sorted({*contribution.origin.owners, *owners})
        )
        return apply_contribution(self.data, contribution, now).parcel_id

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
            checks=verdict.check.as_dict() if verdict.check is not None else None,
        )

    def add_review(self, item: ReviewItem, record: MessageRecord | None) -> None:
        """Put an e-mail in the review list, replacing an older item.

        A fill of the local AI replaces only an older fill: the e-mail stays
        added.
        """
        review = self.data.review
        for key in [
            k
            for k, r in review.items()
            if r.message == item.message and (r.fill or not item.fill)
        ]:
            del review[key]
        review[item.id] = item
        if record is not None and not item.fill:
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
        """Download a stored e-mail again from any mailbox that has it.

        Not one whose headers never downloaded: what it is isn't known.
        """
        if is_unread_key(record.hash):
            return Refetch()
        unavailable = False
        for entry_id, provider_id in list(record.refs.items()):
            if (mailbox := self.mailboxes.get(entry_id)) is None:
                unavailable = True
                continue
            try:
                message = await mailbox.client.async_fetch(provider_id)
            except MailNotFound:
                del record.refs[entry_id]
            except Exception as err:
                # Only where it failed: an error's message could quote the
                # e-mail.
                _LOGGER.debug("Download failed (%s)", error_location(err))
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
        if item.fill:
            return self._accept_fill(review_id, item, suggestion)
        if suggestion is None or not (
            suggestion.kind is MailKind.CUSTOMER_RETURN
            or suggestion.tracking_numbers
            or suggestion.order_numbers
            or suggestion.amazon_shipment_id
            or suggestion.reference
        ):
            raise validation_error("nothing_to_add")
        if suggestion.carrier and suggestion.carrier not in CARRIER_NAMES:
            raise validation_error("unknown_carrier")
        now = dt_util.utcnow()
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
        self._keep_shells(item.message)
        remove_message(data, item.message, now)
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

    def _accept_fill(
        self, review_id: str, item: ReviewItem, suggestion: Suggestion | None
    ) -> list[str]:
        """Add what the local AI filled in, as the user confirmed it."""
        data = self.data
        if suggestion is not None and (
            suggestion.carrier and suggestion.carrier not in CARRIER_NAMES
        ):
            raise validation_error("unknown_carrier")
        record = data.messages.get(item.message)
        now = dt_util.utcnow()
        parcel_id = (
            self.apply_fill(
                suggestion,
                record,
                time=min(item.received or now, now),
                label=organizational_domain(item.sender_domain),
                now=now,
                confirmed=True,
            )
            if suggestion is not None and record is not None
            else None
        )
        if parcel_id is None:
            del data.review[review_id]
            self.async_changed()
            raise validation_error("unknown_parcel")
        data.review.pop(review_id, None)
        self.async_changed()
        return [parcel_id]

    def review_dismiss(self, review_id: str) -> None:
        """Drop an e-mail from the review list.

        An e-mail read again that is still part of a parcel stays so.
        """
        item = self._review(review_id)
        del self.data.review[review_id]
        if (
            not item.fill
            and (record := self.data.messages.get(item.message)) is not None
        ):
            record.state = (
                MessageState.APPLIED
                if message_outputs(self.data, item.message)
                else MessageState.DISMISSED
            )
            record.shells = ()
        self.async_changed()

    def review_trust_sender(self, review_id: str) -> dict[str, Any]:
        """Trust the sender of a reviewed e-mail and settle its e-mails under review.

        The user has seen them and confirmed the risk, so the e-mails that
        failed the sender checks are added as they are, when they hold
        something to add. The others are read again, now that the sender is
        trusted. Returns the trusted domain and how many e-mails were added,
        are being read again and still need review.
        """
        org = self._trust(self._review(review_id).sender_domain)
        data = self.data
        added = kept = 0
        hashes: list[str] = []
        for key, item in list(data.review.items()):
            if item.fill or organizational_domain(item.sender_domain) != org:
                continue
            if item.authenticated:
                hashes.append(item.message)
                continue
            try:
                self.review_accept(key)
            except ServiceValidationError:
                kept += 1
            else:
                added += 1
        self._async_reprocess_later(hashes)
        return {"domain": org, "added": added, "rechecking": len(hashes), "kept": kept}

    def review_ignore_sender(self, review_id: str) -> str:
        """Ignore the sender of a reviewed e-mail; returns its domain."""
        return self.ignore_domain(self._review(review_id).sender_domain)

    def trust_domain(self, domain: str) -> str:
        """Trust a sender organisation and re-read its e-mails under review.

        Returns the organisational domain that is now trusted.
        """
        org = self._trust(domain)
        self._async_reprocess_later(
            [
                item.message
                for item in self.data.review.values()
                if not item.fill and organizational_domain(item.sender_domain) == org
            ]
        )
        return org

    def _trust(self, domain: str) -> str:
        org = organizational_domain(domain)
        if is_free_mail(org):
            raise validation_error("cannot_trust_free_mail", domain=org)
        prefs = self.data.sender(org)
        prefs.trusted = True
        prefs.ignored = False
        prefs.updated = dt_util.utcnow()
        self.async_changed()
        return org

    def _async_reprocess_later(self, hashes: list[str]) -> None:
        if hashes:
            self.async_create_task(
                self._async_reprocess_many(hashes), "parcels reprocess trusted sender"
            )

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
                if not item.fill:
                    # A fill's e-mail stays added, as the parser read it.
                    hashes.add(item.message)
        for key, entry in list(data.filtered.items()):
            if organizational_domain(entry.sender_domain) == org:
                del data.filtered[key]
                hashes.add(entry.message)
        hashes.update(self.ai.drop_domain(org))
        for key in hashes:
            if (record := data.messages.get(key)) is not None:
                # One read again that is still part of a parcel stays so, like
                # the sender's other e-mails already added.
                record.state = (
                    MessageState.APPLIED
                    if message_outputs(data, key)
                    else MessageState.IGNORED
                )
                record.shells = ()
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

    async def async_filtered_restore(self, filtered_id: str) -> str | None:
        """Restore a filtered e-mail; returns the review ID, if it waits there.

        An e-mail the user removed from Parcels is read again, as if it were
        new. When it's gone from the mailboxes, it waits for review instead;
        while no mailbox can give it, it stays removed.
        """
        data = self.data
        if (entry := data.filtered.get(filtered_id)) is None:
            raise validation_error("unknown_filtered")
        if not entry.removed or entry.message not in data.messages:
            return self.filtered_restore(filtered_id)
        try:
            await self.async_reprocess(entry.message)
        except HomeAssistantError as err:
            if err.translation_key != "message_gone":
                raise
            return self.filtered_restore(filtered_id)
        return None

    def remove_email(self, parcel_id: str, origin_id: str) -> str:
        """Remove an e-mail from Parcels, with everything it added.

        The e-mail leaves every parcel and return it was part of, and isn't
        read again; it waits under Filtered, from where it can be restored.
        A parcel left with only the user's edits is deleted. Returns the ID
        of the filtered entry.
        """
        data = self.data
        parcel = self.parcel(parcel_id)
        if (origin := parcel.origins.get(origin_id)) is None:
            raise validation_error("unknown_origin")
        if (key := origin.message) is None:
            raise validation_error("not_an_email")
        now = dt_util.utcnow()
        if (record := data.messages.get(key)) is None:
            record = data.messages[key] = MessageRecord(
                hash=key, seen=now, state=MessageState.FILTERED
            )
        for affected in self.clear_outputs(key, now):
            if (left := data.parcels.get(affected)) is not None and set(
                left.origins
            ) <= {manual_origin_id(left.id)}:
                remove_origins(data, left, set(left.origins), now)
        domain = record.sender_domain or origin.label
        known = lookup(domain) if domain else None
        entry = FilteredItem(
            id=new_id("f"),
            created=now,
            message=key,
            received=record.received,
            sender=known.name if known is not None else "",
            sender_domain=domain,
            subject="",
            mailbox=next(iter(record.refs), None),
            removed=True,
        )
        data.filtered[entry.id] = entry
        record.state = MessageState.FILTERED
        self.async_changed()
        return entry.id

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
            record.shells = ()

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
        """Download an e-mail again and decide anew, or send it to the AI.

        Its parcels stay until a new reading replaces them, and then keep
        their IDs: see ``apply_result``.
        """
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
        if (read := await self.async_read(message)) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="message_unreadable"
            )
        verdict, result = read
        now = dt_util.utcnow()
        owner = record.owners[0] if record.owners else mailbox.owner
        # A refund is dropped as it is, and a return decided as it is: the AI
        # isn't asked about either.
        if (
            use_ai
            and not is_refund(result)
            and result.kind is not MailKind.CUSTOMER_RETURN
        ):
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
            self._clear_lists(key)
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
                reread=True,
            )
        self.async_changed()

    async def _async_reprocess_many(self, hashes: Iterable[str]) -> None:
        for key in hashes:
            try:
                await self.async_reprocess(key)
            except HomeAssistantError as err:
                _LOGGER.debug("Reprocessing skipped an e-mail: %s", err)

    async def async_check_again(
        self, parcel_id: str, *, forced: bool = True
    ) -> dict[str, int]:
        """Read a parcel's e-mails again and ask the local AI what's missing.

        Unlike reprocessing, the parcel stays on the page: an e-mail a parser
        reads is added again in place, unless the user confirmed it under
        review. Returns how many e-mails were read, queued for the AI, gone
        from the mailboxes, or not downloaded or read.
        """
        parcel = self.parcel(parcel_id)
        messages = self.data.messages
        records = [
            record
            for key in {o.message for o in parcel.origins.values() if o.message}
            if (record := messages.get(key)) is not None
            and record.state is MessageState.APPLIED
        ]
        records.sort(key=lambda r: r.received or _EPOCH, reverse=True)
        counts = {"read": 0, "queued": 0, "gone": 0, "failed": 0}
        for record in records[:CHECK_AGAIN_MAX_EMAILS]:
            fetched = await self.async_refetch(record)
            if fetched.message is None or fetched.mailbox is None:
                counts["gone" if fetched.gone else "failed"] += 1
                continue
            message, mailbox = fetched.message, fetched.mailbox
            if (read := await self.async_read(message)) is None:
                counts["failed"] += 1
                continue
            verdict, result = read
            counts["read"] += 1
            if not (verdict.verified and is_confident(result)):
                continue
            now = dt_util.utcnow()
            if self._parser_only(record.hash):
                self.apply_result(
                    result,
                    record,
                    source=Source.PARSER,
                    time=self.message_time(message, now),
                    label=organizational_domain(message.sender_domain),
                    now=now,
                )
            if self.queue_fill(
                message,
                verdict,
                result,
                record,
                mailbox=mailbox.entry_id,
                owner=record.owners[0] if record.owners else mailbox.owner,
                now=now,
                forced=forced,
            ):
                counts["queued"] += 1
        self.async_changed()
        return counts

    def _parser_only(self, message_hash: str) -> bool:
        """Return True when only a parser added an e-mail, and nobody confirmed it.

        What the local AI filled in has its own origin and doesn't count.
        """
        found = False
        for parcel in self.data.parcels.values():
            for origin in parcel.origins.values():
                if origin.message != message_hash or origin.id.endswith(
                    FILL_ORIGIN_SUFFIX
                ):
                    continue
                if origin.source is not Source.PARSER or origin.confirmed:
                    return False
                found = True
        return found

    def _ai_only(self, message_hash: str) -> bool:
        """Return True when only the local AI added an e-mail, and nobody confirmed it."""
        found = False
        for parcel in self.data.parcels.values():
            for origin in parcel.origins.values():
                if origin.message != message_hash or origin.id.endswith(
                    FILL_ORIGIN_SUFFIX
                ):
                    continue
                if origin.source is not Source.AI or origin.confirmed:
                    return False
                found = True
        return found

    def _ai_accepted(self, message_hash: str) -> bool:
        """Return True when only the local AI added an e-mail, and the user confirmed it.

        What the AI filled in for the parsers doesn't count.
        """
        found = confirmed = False
        for parcel in self.data.parcels.values():
            for origin in parcel.origins.values():
                if origin.message != message_hash or origin.id.endswith(
                    FILL_ORIGIN_SUFFIX
                ):
                    continue
                if origin.source is not Source.AI:
                    return False
                found = True
                confirmed = confirmed or origin.confirmed
        return found and confirmed

    async def _async_fill_check(self) -> None:
        """Check once, after the update, what an earlier release stored.

        E-mails refused for their mail server are read again first, then the
        open parcels without a date or items are checked again, within the
        daily limit of the local AI.
        """
        data = self.data
        refused = [
            item.message
            for item in data.review.values()
            if item.reason == REASON_UNTRUSTED_SERVER and not item.fill
        ]
        await self._async_reprocess_many(refused)
        lacking = [
            parcel.id
            for parcel in data.parcels.values()
            if parcel.archived is None
            and not parcel.state.terminal
            and (parcel.state.eta is None or not parcel.state.items)
        ]
        checked = 0
        for parcel_id in lacking:
            if parcel_id not in data.parcels:
                continue
            try:
                await self.async_check_again(parcel_id, forced=False)
            except HomeAssistantError as err:
                _LOGGER.debug("Checking a parcel again failed: %s", err)
                continue
            checked += 1
        _LOGGER.debug(
            "Read %d refused e-mails and checked %d parcels again",
            len(refused),
            checked,
        )

    async def _async_checks(
        self,
        before: datetime | None,
        *,
        shops: datetime | None,
        amazon_ai: datetime | None,
        accepted: datetime | None,
        fill: bool,
        paack: bool,
        leroymerlin: bool,
    ) -> None:
        """Run the one-time checks in turn.

        Returns first, as they can remove parcels. Paack's, Leroy Merlin's
        and then Amazon's e-mails last, so that what the parsers read then
        isn't filled in by the local AI: first those only the AI read, then
        those whose AI answer the user accepted, so that Amazon's
        cancellations are judged on the parsers' reading. The shops of
        Paack's parcels at the very end, once the e-mails under review were
        read.
        """
        if before is not None:
            await self._async_returns_check(before)
        if fill:
            await self._async_fill_check()
        if paack:
            await self._async_rejected_check(_paack_rejected, "Paack")
        if leroymerlin:
            await self._async_rejected_check(_leroymerlin_rejected, "Leroy Merlin")
        if amazon_ai is not None:
            await self._async_amazon_ai_check(amazon_ai)
        if accepted is not None:
            await self._async_amazon_accepted_check(accepted)
        if shops is not None:
            await self._async_paack_shop_check(shops)

    def _paack_shop_check_keys(self, before: datetime, now: datetime) -> list[str]:
        """Return Paack's e-mails whose parcels name no shop, newest first.

        Those of the last 14 days that an earlier release, before ``before``,
        added to parcels, where none of the e-mail's own readings names the
        shop: no name, or the carrier's. Senders the user ignores never count.
        """
        data = self.data
        named: dict[str, bool] = {}
        for parcel in data.parcels.values():
            for origin in parcel.origins.values():
                if not origin.message or origin.id.endswith(FILL_ORIGIN_SUFFIX):
                    continue
                shop = bool(origin.merchant) and not carrier_like(origin.merchant)
                named[origin.message] = named.get(origin.message, False) or shop
        since = now - PAACK_SHOP_CHECK_WINDOW

        def received(key: str) -> datetime:
            record = data.messages[key]
            return record.received or record.seen

        keys = [
            key
            for key, record in data.messages.items()
            if record.state is MessageState.APPLIED
            and named.get(key) is False
            and record.seen < before
            and received(key) >= since
            and (info := lookup(record.sender_domain)) is not None
            and info.carrier == "paack"
            and not self.is_ignored(record.sender_domain)
        ]
        return sorted(keys, key=received, reverse=True)

    async def _async_paack_shop_check(self, before: datetime) -> None:
        """Name the shop of Paack's parcels, once after the update.

        Releases before 0.1.7 couldn't read the shop Paack's e-mails name.
        Each e-mail is downloaded and read again by the parsers, never the
        AI, and only the shop is filled in, where the e-mail's own reading
        named none: what the user set, merged or split stays as it is.
        Nothing changes when the e-mail changed state while it was read.
        """
        data = self.data
        keys = self._paack_shop_check_keys(before, dt_util.utcnow())
        counts = dict.fromkeys(("read", "filled", "kept", "gone", "failed"), 0)
        counts["skipped"] = max(0, len(keys) - PAACK_SHOP_CHECK_MAX)
        for key in keys[:PAACK_SHOP_CHECK_MAX]:
            if (record := data.messages.get(key)) is None:
                continue
            fetched = await self.async_refetch(record)
            if fetched.message is None or fetched.mailbox is None:
                counts["gone" if fetched.gone else "failed"] += 1
                continue
            if (read := await self.async_read(fetched.message)) is None:
                counts["failed"] += 1
                continue
            counts["read"] += 1
            verdict, result = read
            shop = result.merchant
            if (
                data.messages.get(key) is record
                and record.state is MessageState.APPLIED
                and verdict.verified
                and is_confident(result)
                and shop
                and not carrier_like(shop)
                and fill_shop(data, key, shop, dt_util.utcnow())
            ):
                counts["filled"] += 1
            else:
                counts["kept"] += 1
        check = data.engine.setdefault(PAACK_SHOP_CHECK_KEY, {})
        check["done"] = dt_to_str(dt_util.utcnow())
        check["counts"] = counts
        if counts["filled"]:
            self.async_changed()
        else:
            self.async_schedule_save()

    def _amazon_check_messages(self, before: datetime, now: datetime) -> list[str]:
        """Return Amazon's e-mails of the last 30 days read before ``before``.

        Newest first. Senders the user ignores never count.
        """
        data = self.data
        since = now - AMAZON_AI_CHECK_WINDOW

        def received(key: str) -> datetime:
            record = data.messages[key]
            return record.received or record.seen

        keys = [
            key
            for key, record in data.messages.items()
            if record.seen < before
            and received(key) >= since
            and (info := lookup(record.sender_domain)) is not None
            and info.parser == "amazon"
            and not self.is_ignored(record.sender_domain)
        ]
        return sorted(keys, key=received, reverse=True)

    def _amazon_ai_reading(self, record: MessageRecord) -> str | None:
        """Return how the local AI left an e-mail, or None if it didn't.

        "applied" when only the AI added it to parcels, unconfirmed; "review"
        when it waits in review; "filtered" when the AI took it for no
        parcel; "queued" when it waits for the AI. None as well when the user
        asked the AI to read it, or removed it from Parcels.
        """
        data = self.data
        key = record.hash
        queued = [entry for entry in self.ai.queue if entry.get("hash") == key]
        if any(entry.get("forced") for entry in queued):
            return None
        if record.state is MessageState.APPLIED:
            return "applied" if self._ai_only(key) else None
        if record.state is MessageState.REVIEW:
            waiting = any(item.message == key for item in data.review.values())
            return "review" if waiting else None
        if record.state is MessageState.FILTERED:
            rejected = any(
                entry.message == key and not entry.removed
                for entry in data.filtered.values()
            )
            return "filtered" if rejected else None
        if record.state is MessageState.QUEUED:
            return "queued" if queued else None
        return None

    def _amazon_ai_check_keys(self, before: datetime, now: datetime) -> list[str]:
        """Return Amazon's e-mails that the local AI read, newest first.

        Those of the last 30 days that an earlier release, before ``before``,
        left to the AI or to review. Senders the user ignores never count.
        """
        messages = self.data.messages
        return [
            key
            for key in self._amazon_check_messages(before, now)
            if self._amazon_ai_reading(messages[key]) is not None
        ]

    async def _async_amazon_ai_check(self, before: datetime) -> None:
        """Read Amazon's e-mails that the local AI read again, once after the update.

        Releases before 0.1.16 couldn't read Amazon's Portuguese order
        confirmations, so the local AI read them, or they waited in review.
        Each e-mail is downloaded and read again by the parsers, never the
        AI. Where they read it with confidence, their reading replaces the
        AI's, without reopening a parcel that was put away; what the user
        set, merged or split stays, and so does a parcel only the AI saw
        once the user edited it. Nothing changes when the e-mail changed
        state while it was read.
        """
        data = self.data
        keys = self._amazon_ai_check_keys(before, dt_util.utcnow())
        counts = dict.fromkeys(("read", "applied", "kept", "gone", "failed"), 0)
        counts["skipped"] = max(0, len(keys) - AMAZON_AI_CHECK_MAX)
        for key in keys[:AMAZON_AI_CHECK_MAX]:
            if (record := data.messages.get(key)) is None:
                continue
            fetched = await self.async_refetch(record)
            if (message := fetched.message) is None or fetched.mailbox is None:
                counts["gone" if fetched.gone else "failed"] += 1
                continue
            if (read := await self.async_read(message)) is None:
                counts["failed"] += 1
                continue
            counts["read"] += 1
            verdict, result = read
            reading = (
                self._amazon_ai_reading(record)
                if data.messages.get(key) is record
                else None
            )
            if reading is None or not verdict.verified or not is_confident(result):
                counts["kept"] += 1
                continue
            now = dt_util.utcnow()
            org = organizational_domain(message.sender_domain)
            if reading != "applied":
                self.clear_outputs(key, now)
            self.apply_result(
                result,
                record,
                source=Source.PARSER,
                time=self.message_time(message, now),
                label=org,
                now=now,
                keep_closed=True,
            )
            # What only the AI read in the e-mail goes, but not a parcel that
            # the user edited.
            for parcel in list(data.parcels.values()):
                stale = {
                    origin.id
                    for origin in parcel.origins.values()
                    if origin.message == key
                    and origin.source is Source.AI
                    and not origin.id.endswith(FILL_ORIGIN_SUFFIX)
                }
                if stale and set(parcel.origins) - stale != {
                    manual_origin_id(parcel.id)
                }:
                    remove_origins(data, parcel, stale, now)
            self.ai.drop(key)
            self._clear_unparsed(org)
            counts["applied"] += 1
        check = data.engine.setdefault(AMAZON_AI_CHECK_KEY, {})
        check["done"] = dt_to_str(dt_util.utcnow())
        check["counts"] = counts
        if counts["applied"]:
            self.async_changed()
        else:
            self.async_schedule_save()

    def _amazon_accepted(self, record: MessageRecord) -> bool:
        """Return True when only a local AI answer the user accepted added an e-mail.

        Not when the user asked the AI to read the e-mail again.
        """
        key = record.hash
        return (
            record.state is MessageState.APPLIED
            and not any(
                entry.get("forced")
                for entry in self.ai.queue
                if entry.get("hash") == key
            )
            and self._ai_accepted(key)
        )

    async def _async_amazon_accepted_check(self, before: datetime) -> None:
        """Read again Amazon's e-mails whose AI answer the user accepted, once.

        Releases before 0.1.16 couldn't read Amazon's Portuguese order
        confirmations, so the local AI read them, and where it only suggested,
        the user accepted its answers in review: on its way, for an order.
        Accepting meant that the e-mail was about the user's parcel, not that
        it shipped. Each such e-mail is downloaded and read again by the
        parsers, never the AI. Where they read an order with confidence, their
        reading replaces the AI's and stays confirmed, without reopening a
        parcel that was put away; what the user set, merged or split stays.
        Not where what the e-mail added names a tracking number or a
        shipment, which the parsers don't read in an order's e-mail. Nothing
        changes when the e-mail changed state while it was read.

        Then Amazon's cancellations that were taken for partial ones cancel
        their parcel, where nothing but the order's e-mail says it shipped:
        see restore_cancellations().
        """
        data = self.data
        messages = self._amazon_check_messages(before, dt_util.utcnow())
        keys = [key for key in messages if self._amazon_accepted(data.messages[key])]
        counts = dict.fromkeys(("read", "applied", "kept", "gone", "failed"), 0)
        counts["skipped"] = max(0, len(keys) - AMAZON_AI_CHECK_MAX)
        for key in keys[:AMAZON_AI_CHECK_MAX]:
            if (record := data.messages.get(key)) is None:
                continue
            fetched = await self.async_refetch(record)
            if (message := fetched.message) is None or fetched.mailbox is None:
                counts["gone" if fetched.gone else "failed"] += 1
                continue
            if (read := await self.async_read(message)) is None:
                counts["failed"] += 1
                continue
            counts["read"] += 1
            verdict, result = read
            if (
                data.messages.get(key) is not record
                or not self._amazon_accepted(record)
                or not verdict.verified
                or not is_confident(result)
                or result.kind is not MailKind.ORDER
                or any(
                    origin.tracking_number or origin.amazon_shipment_id
                    for parcel in data.parcels.values()
                    for origin in parcel.origins.values()
                    if origin.message == key
                )
            ):
                counts["kept"] += 1
                continue
            now = dt_util.utcnow()
            org = organizational_domain(message.sender_domain)
            # Without a tracking number the answer added a single origin, and
            # the parsers' reading replaces it where it is: merges and splits
            # stay.
            self.apply_result(
                result,
                record,
                source=Source.PARSER,
                time=self.message_time(message, now),
                label=org,
                now=now,
                confirmed=True,
                keep_closed=True,
            )
            self.ai.drop(key)
            self._clear_unparsed(org)
            counts["applied"] += 1
        now = dt_util.utcnow()
        cancellations = restore_cancellations(
            data, set(self._amazon_check_messages(before, now)), now
        )
        check = data.engine.setdefault(AMAZON_ACCEPTED_CHECK_KEY, {})
        check["done"] = dt_to_str(now)
        check["counts"] = counts
        check["cancellations"] = cancellations
        if counts["applied"] or cancellations:
            self.async_changed()
        else:
            self.async_schedule_save()

    def _returns_check_keys(self, before: datetime, now: datetime) -> list[str]:
        """Return the e-mails for the returns check, in the order to read them.

        First those an earlier release added to parcels as sent back; then,
        from known or trusted senders and of the last 30 days, those it set
        aside. E-mails that failed to download count from any sender; senders
        the user ignores never count. Newest first; only e-mails read before
        ``before``.
        """
        data = self.data
        messages = data.messages
        returned: set[str] = set()
        for parcel in data.parcels.values():
            returned.update(
                origin.message
                for event in parcel.events
                if (
                    event.kind is MailKind.RETURN
                    or event.status is ParcelStatus.RETURNED
                )
                and event.origin is not None
                and (origin := parcel.origins.get(event.origin)) is not None
                and origin.message
            )
        trusted = {organizational_domain(d) for d in data.trusted_domains()}
        since = now - RETURNS_CHECK_WINDOW

        def received(key: str) -> datetime:
            record = messages[key]
            return record.received or record.seen

        first = [
            key
            for key in returned
            if (record := messages.get(key)) is not None
            and record.seen < before
            and not self.is_ignored(record.sender_domain)
        ]
        second = [
            key
            for key, record in messages.items()
            if key not in returned
            and record.state in SET_ASIDE
            and record.seen < before
            and (record.received or record.seen) >= since
            and not self.is_ignored(record.sender_domain)
            and (
                record.state is MessageState.FAILED
                or lookup(record.sender_domain) is not None
                or organizational_domain(record.sender_domain) in trusted
            )
        ]
        return [
            *sorted(first, key=received, reverse=True),
            *sorted(second, key=received, reverse=True),
        ]

    async def _async_returns_check(self, before: datetime) -> None:
        """Check once, after the update, what an earlier release read.

        An earlier release couldn't tell refunds and customer returns apart
        from parcels sent back, and set some return e-mails aside. Each
        e-mail is downloaded and read again by the parsers, never the AI: a
        refund is dropped wherever it went, and a customer return from a
        verified sender becomes a return. Anything else stays as it was, even
        if the user cleared it: those are only read again here, once. E-mails
        that failed to download are decided as new ones.
        """
        data = self.data
        keys = self._returns_check_keys(before, dt_util.utcnow())
        counts = dict.fromkeys(
            ("read", "refunds", "returns", "decided", "gone", "failed"), 0
        )
        counts["skipped"] = max(0, len(keys) - RETURNS_CHECK_MAX)
        for key in keys[:RETURNS_CHECK_MAX]:
            if (record := data.messages.get(key)) is None:
                continue
            state = record.state
            fetched = await self.async_refetch(record)
            if fetched.message is None or fetched.mailbox is None:
                counts["gone" if fetched.gone else "failed"] += 1
                continue
            if (read := await self.async_read(fetched.message)) is None:
                counts["failed"] += 1
                continue
            counts["read"] += 1
            outcome = self._recheck(
                record, state, fetched.message, fetched.mailbox, *read
            )
            if outcome is not None:
                counts[outcome] += 1
        check = data.engine.setdefault(RETURNS_CHECK_KEY, {})
        check["done"] = dt_to_str(dt_util.utcnow())
        check["counts"] = counts
        self.async_changed()
        _LOGGER.info(
            "Parcels read %d e-mails again: %d refunds dropped, %d returns found",
            counts["read"],
            counts["refunds"],
            counts["returns"],
        )

    def _recheck(
        self,
        record: MessageRecord,
        state: MessageState,
        message: MailMessage,
        mailbox: MailboxRuntime,
        verdict: SenderVerdict,
        result: ParseResult,
    ) -> str | None:
        """Decide anew on an e-mail for the returns check; return what changed.

        Nothing changes when the e-mail changed state while it was read.
        """
        key = record.hash
        if self.data.messages.get(key) is not record or record.state is not state:
            return None
        now = dt_util.utcnow()
        if state is MessageState.FAILED:
            # Never read: decided as a new e-mail, for everyone who has it,
            # with the AI only for recent ones, as on a first sync.
            record.state = MessageState.IGNORED
            record.attempts = 0
            record.retry_at = None
            self._decide(
                message,
                verdict,
                result,
                record,
                mailbox=mailbox.entry_id,
                owner=mailbox.owner,
                first_sync=True,
                now=now,
            )
            return "decided"
        if is_refund(result) and result.confidence >= CONFIDENCE_APPLY:
            if state is MessageState.NOT_PARCEL:
                return None
            self.clear_outputs(key, now)
            self.drop_refund(record)
            return "refunds"
        if (
            result.kind is MailKind.CUSTOMER_RETURN
            and verdict.verified
            and is_confident(result)
        ):
            self.clear_outputs(key, now)
            self.apply_result(
                result,
                record,
                source=Source.PARSER,
                time=self.message_time(message, now),
                label=organizational_domain(message.sender_domain),
                now=now,
            )
            return "returns"
        return None

    async def _async_rejected_check(
        self, rejected: Callable[[ReviewItem], bool], sender: str
    ) -> None:
        """Read e-mails rejected under review again, once after the update.

        ``rejected`` picks the e-mails a new parser reads. An e-mail the
        parsers now read is decided anew, without the local AI; the others
        stay under review as they were.
        """
        data = self.data
        items = [item for item in data.review.values() if rejected(item)]
        counts = {"read": 0, "kept": 0, "gone": 0, "failed": 0}
        for item in items:
            if (record := data.messages.get(item.message)) is None:
                continue
            fetched = await self.async_refetch(record)
            if fetched.message is None or fetched.mailbox is None:
                counts["gone" if fetched.gone else "failed"] += 1
                continue
            message, mailbox = fetched.message, fetched.mailbox
            if (read := await self.async_read(message)) is None:
                counts["failed"] += 1
                continue
            verdict, result = read
            if not is_confident(result):
                counts["kept"] += 1
                continue
            if data.review.get(item.id) is not item:
                # The user settled it meanwhile.
                continue
            now = dt_util.utcnow()
            self._decide(
                message,
                verdict,
                result,
                record,
                mailbox=mailbox.entry_id,
                owner=record.owners[0] if record.owners else mailbox.owner,
                first_sync=False,
                now=now,
                reread=True,
            )
            # What the parsers read isn't filled in or shadow-checked by the AI.
            self.ai.drop(record.hash)
            counts["read"] += 1
        if counts["read"]:
            self.async_changed()
        else:
            self.async_schedule_save()
        _LOGGER.debug("%s's rejected e-mails read again: %s", sender, counts)

    def clear_outputs(self, key: str, now: datetime) -> set[str]:
        """Undo everything an e-mail added: parcels, review and queue.

        What its parcels were stays on its record (see ParcelShell), so that
        a new reading goes back to them. Returns the IDs of the parcels that
        changed.
        """
        self._keep_shells(key)
        affected = remove_message(self.data, key, now)
        self._clear_lists(key)
        return affected

    def _keep_shells(self, key: str) -> None:
        """Note what an e-mail's parcels are, before its news leaves them.

        When it's part of none, the shells noted before stay: they still say
        where it was, e.g. for a removed e-mail that is restored.
        """
        record = self.data.messages.get(key)
        if record is not None and (shells := message_shells(self.data, key)):
            record.shells = shells

    def _clear_lists(self, key: str) -> None:
        """Take an e-mail out of "Needs review", Filtered and the AI queue."""
        data = self.data
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
        check: KeyCheck | None = None,
    ) -> str:
        """Add a parcel by tracking number; returns its ID.

        ``check`` gets the keys the parcel can join others by, and raises to
        refuse them.
        """
        carrier = manual_carrier(tracking_number, carrier)
        number = manual_number(tracking_number, carrier)
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
        if check is not None:
            added = Parcel(
                id=origin.id,
                created=now,
                updated=now,
                origins={origin.id: origin},
                events=[event],
            )
            check(join_keys(added))
        applied = self._run(
            apply_contribution,
            Contribution(origin=origin, events=[event], private=private),
            now,
        )
        return applied.parcel_id

    def update(
        self,
        parcel_id: str,
        changes: Mapping[str, Any],
        *,
        check: KeyCheck | None = None,
    ) -> None:
        """Edit a parcel.

        ``check`` gets the keys the edit gives the parcel, and raises to refuse
        them. A tracking number the edit sets counts even if the parcel had it:
        any parcel with it joins.
        """
        parcel = self.parcel(parcel_id)
        carrier = changes.get("carrier")
        if carrier and carrier not in CARRIER_NAMES:
            raise validation_error("unknown_carrier")
        if changes.get("tracking_number"):
            value = str(changes["tracking_number"])
            given = carrier if "carrier" in changes else parcel.state.carrier
            carrier = manual_carrier(value, given)
            changes = {**changes, "tracking_number": manual_number(value, carrier)}
            if carrier and not given:
                changes["carrier"] = carrier
        now = dt_util.utcnow()
        if check is not None:
            check(self._edited_keys(parcel, changes, now))
        self._run(update_parcel, parcel_id, dict(changes), now)

    @staticmethod
    def _edited_keys(
        parcel: Parcel, changes: Mapping[str, Any], now: datetime
    ) -> set[JoinKey]:
        """Return the keys an edit gives a parcel, trying it on a copy."""
        edited = copy.deepcopy(parcel)
        try:
            update_parcel(
                ParcelsData(parcels={edited.id: edited}), edited.id, dict(changes), now
            )
        except DedupError as err:
            raise validation_error(err.reason) from err
        keys = join_keys(edited) - join_keys(parcel)
        if number := changes.get("tracking_number"):
            keys.add(("number", number_key_text(str(number))))
        return keys

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
        """Take back a delivery marked by hand, kept, or inferred.

        An inferred one isn't inferred again. Automations told of the
        delivery hear of the status it goes back to, however old its news.
        """
        self.parcel(parcel_id)
        self._taken_back.add(parcel_id)
        try:
            self._run(undo_delivery, parcel_id, dt_util.utcnow())
        finally:
            self._taken_back.discard(parcel_id)

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

    def remove_return(self, return_id: str) -> None:
        """Remove a customer return; its e-mails aren't read again.

        A delivery that only the return inferred goes with it.
        """
        if return_id not in self.data.returns:
            raise validation_error("unknown_return")
        entry = remove_return(self.data, return_id, dt_util.utcnow())
        for key in entry.origins:
            self._dismiss_message(key)
        self.async_changed()

    def mark_return_picked_up(self, return_id: str, picked_up: bool) -> None:
        """Mark a customer return picked up now, or take that back.

        Its Live Activity ends; taken back, it shows again on its day.
        """
        if return_id not in self.data.returns:
            raise validation_error("unknown_return")
        mark_return_picked_up(self.data, return_id, picked_up, dt_util.utcnow())
        self.async_changed()

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
            # What the last load skipped, or couldn't read, by section.
            "damaged": dict(sorted(data.damaged.items())),
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
            "held_guesses": len(data.engine.get(HELD_GUESSES) or ()),
            "forgotten_before": data.engine.get(FORGOTTEN_KEY),
            "old_emails_skipped": self._old_skipped,
            "failed_emails": self._failed_emails(),
            "refunds_dropped": int(data.engine.get(REFUNDS_KEY) or 0),
            "returns_check": data.engine.get(RETURNS_CHECK_KEY),
            "paack_shop_check": data.engine.get(PAACK_SHOP_CHECK_KEY),
            "amazon_ai_check": data.engine.get(AMAZON_AI_CHECK_KEY),
            "amazon_accepted_check": data.engine.get(AMAZON_ACCEPTED_CHECK_KEY),
            "recent_emails": self._recent_emails(dt_util.utcnow()),
            "working_days": self.workdays.source,
            "amazon_shipment_ids": amazon_shipment_id_counts(data, dt_util.utcnow()),
            "amazon_links": data.engine.get(AMAZON_LINKS_KEY),
            "order_fold": data.engine.get(ORDER_FOLD_KEY),
            "repair": data.engine.get(REPAIR_KEY),
            "amazon_carrier_repaired": data.engine.get(AMAZON_REPAIR_KEY),
            "placeholder_items_repaired": data.engine.get(PLACEHOLDER_REPAIR_KEY),
            "parcel_app_dates_repaired": data.engine.get(DATES_REPAIR_KEY),
            "seventeentrack_pickups_repaired": data.engine.get(PICKUPS_REPAIR_KEY),
            "seventeentrack_pickups_restored": data.engine.get(PICKUP_PLACES_KEY),
            "seventeentrack_pickups_reread": data.engine.get(PICKUPS_REREAD_KEY),
            "seventeentrack_timeless_repaired": data.engine.get(TIMELESS_REPAIR_KEY),
            "reconcile_waiting": len(self._syncing | self._more),
            # How the sender checks went for the newest e-mails under review:
            # the shop's domain and the servers that wrote the headers only.
            "sender_checks": [
                {
                    "sender": organizational_domain(item.sender_domain),
                    "reason": item.reason,
                    "checks": item.checks,
                }
                for item in sorted(
                    data.review.values(), key=lambda item: item.created, reverse=True
                )
                if item.checks is not None
            ][:MAX_SENDER_CHECKS],
            "ai": self.ai.diagnostics(),
        }

    def _failed_emails(self) -> dict[str, Any]:
        """Count the e-mails that failed: still tried, and given up on."""
        retrying = [
            record.retry_at
            for record in self.data.messages.values()
            if self._retrying(record) and record.retry_at is not None
        ]
        return {
            "retrying": len(retrying),
            "gave_up": len(self.gave_up_emails()),
            "next_retry": min(retrying).isoformat() if retrying else None,
        }

    def _recent_emails(self, now: datetime) -> dict[str, dict[str, dict[str, int]]]:
        """Count the e-mails of the last days by day, sender and state.

        Known senders and the domains the user trusts are named by their
        organisation; every other sender counts as "other". Newest day first.
        """
        data = self.data
        trusted = {organizational_domain(d) for d in data.trusted_domains()}
        since = now - timedelta(days=RECENT_DAYS)
        days: dict[str, dict[str, dict[str, int]]] = {}
        for record in data.messages.values():
            received = record.received or record.seen
            if received < since:
                continue
            org = organizational_domain(record.sender_domain)
            sender = (
                org if org and (lookup(org) is not None or org in trusted) else "other"
            )
            day = received.astimezone(self.tz).date().isoformat()
            states = days.setdefault(day, {}).setdefault(sender, {})
            states[record.state.value] = states.get(record.state.value, 0) + 1
        return {
            day: {sender: days[day][sender] for sender in sorted(days[day])}
            for day in sorted(days, reverse=True)
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
