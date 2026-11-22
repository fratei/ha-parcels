"""Live carrier status from the built-in 17TRACK integration.

Parcels never talks to 17TRACK itself. It calls the services of the core
``seventeentrack`` integration, so the 17track.net login stays there. It sends
tracking numbers only, under a generic name such as ``parcels-1a2b3c``: never
item names or merchants, and never the numbers of private parcels, because any
Home Assistant user can list 17TRACK packages.

Each refresh:

- adds the numbers of active parcels that 17TRACK doesn't have yet, the ones
  due soonest first and at most 10 at a time. It leaves out the numbers
  17TRACK can't follow: Amazon Logistics', and those it can only follow with
  the recipient's postcode, which its services can't send (Paack's, and
  GLS's in Portugal). It also leaves out parcels without news for three
  weeks (see ``quiet``). A refused number is tried again later, and once
  a day after three refusals, because 17TRACK refuses new numbers while the
  account's quota is used up;
- reads the packages and turns new statuses into events of their parcel;
- archives the packages it added once their parcel is finished, archived,
  private, gone or without news for three weeks, when 17TRACK can't follow
  the number, or when 17TRACK still can't find it after two weeks.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
import logging
import re
from typing import TYPE_CHECKING, Any, Final

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CARRIER_NAMES,
    CONF_SEVENTEENTRACK,
    DEFAULT_SEVENTEENTRACK,
    MailKind,
    ParcelStatus,
)
from .dedup import Contribution, apply_contribution
from .models import (
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    Source,
    dt_from_str,
    dt_to_str,
)
from .parsers.carriers._common import fold_text, phrase_regex
from .parsers.carriers._phrases import KIND_PHRASES, PICKUP_PLACES
from .parsers.details import tracker_details
from .parsers.tracking import PAACK_ID_RE, detect_carrier, normalize_tracking_number
from .quiet import is_quiet

if TYPE_CHECKING:
    from .engine import ParcelsEngine

_LOGGER = logging.getLogger(__name__)

SEVENTEENTRACK_DOMAIN: Final = "seventeentrack"
ORIGIN_PREFIX: Final = "17t:"
NAME_PREFIX: Final = "parcels-"
ORIGIN_LABEL: Final = "17TRACK"
# The engine state key of the repair of 17TRACK's pickups, see
# :func:`repair_pickups`.
PICKUPS_REPAIR_KEY: Final = "seventeentrack_pickups"
# The engine state key of the pickups given back by
# :func:`restore_pickup_places`.
PICKUP_PLACES_KEY: Final = "seventeentrack_pickup_places"
# The engine state key of the second run of :func:`repair_pickups`, after
# 0.1.15 read more of the carrier's text (see :func:`pickup_status`).
PICKUPS_REREAD_KEY: Final = "seventeentrack_pickups_reread"

INTERVAL: Final = timedelta(minutes=30)
# While a parcel is out for delivery or due today.
BUSY_INTERVAL: Final = timedelta(minutes=10)
START_DELAY: Final = 60.0
RECONFIGURE_DELAY: Final = 5.0
SERVICE_TIMEOUT: Final = 60.0
MAX_ADDS: Final = 10
MAX_HISTORY: Final = 10
MAX_INFO_CHARS: Final = 160
MIN_NUMBER_CHARS: Final = 8
NOT_FOUND_ARCHIVE: Final = timedelta(days=14)
# A refused number is tried again after 6 and 12 hours, then once a day while
# its parcel is active: 17TRACK refuses new numbers while the account is full,
# and Parcels can't tell that apart from other refusals.
ADD_RETRIES: Final = 3
ADD_RETRY_DELAY: Final = timedelta(hours=6)
ADD_RETRY_LATER: Final = timedelta(days=1)
# pyseventeentrack's text for a refusal, which holds only 17TRACK's code.
_REFUSAL: Final = re.compile(r"Non-zero status code in response: (-?\d{1,6})")
# Carriers that 17TRACK follows only with the recipient's postcode, which the
# add_package service can't send, so their numbers would stay "Not Found":
# Paack (17TRACK key 100364) and SEUR (100438, which also needs the last
# digits of the recipient's phone) everywhere, and GLS in Portugal (100316,
# 100646), Spain (100189, 199992) and the Netherlands (100384). See
# https://res.17track.net/asset/carrier/info/additional_parameters.json
_NEEDS_POSTCODE: Final = frozenset({"paack", "seur"})
_NEEDS_POSTCODE_IN: Final[Mapping[str, frozenset[str]]] = {
    "ES": frozenset({"gls"}),
    "NL": frozenset({"gls"}),
    "PT": frozenset({"gls"}),
}

# Package statuses of the core integration, as slugs (see its package_state
# selector). Not found and expired carry no news. "Ready to be picked up" is
# 17TRACK's old "Pick Up" status, which also stands for out for delivery, so
# it counts as a pickup only when the carrier's text says so or names a
# pickup place (pickup_status).
_STATUSES: Final[dict[str, ParcelStatus]] = {
    "in_transit": ParcelStatus.IN_TRANSIT,
    "ready_to_be_picked_up": ParcelStatus.READY_FOR_PICKUP,
    "undelivered": ParcelStatus.ATTEMPTED,
    "delivered": ParcelStatus.DELIVERED,
    "alert": ParcelStatus.EXCEPTION,
    "returned": ParcelStatus.RETURNED,
}
_NO_NEWS: Final = frozenset({"not_found", "expired"})

# The carrier's text can be more precise than the 17TRACK status, in any of
# the languages the parsers know. The first match wins.
_INFO_RULES: Final[tuple[tuple[MailKind, ParcelStatus], ...]] = (
    (MailKind.RETURN, ParcelStatus.RETURNED),
    (MailKind.ATTEMPTED, ParcelStatus.ATTEMPTED),
    (MailKind.READY_FOR_PICKUP, ParcelStatus.READY_FOR_PICKUP),
    (MailKind.OUT_FOR_DELIVERY, ParcelStatus.OUT_FOR_DELIVERY),
)
_REFINED: Final = frozenset(
    {ParcelStatus.IN_TRANSIT, ParcelStatus.EXCEPTION, ParcelStatus.ATTEMPTED}
)


def _gap(stops: str) -> str:
    """Return a pattern for up to four words of one clause.

    None of them may be one of the stop words: a negation, another day or a
    word that joins two clauses.
    """
    return rf" (?:(?!(?:{stops})\b)[a-z0-9'-]+ ){{0,4}}"


_DE: Final = _gap(r"nicht|kein\w*|morgen|ubermorgen|und|oder|aber|sondern")
_NL: Final = _gap(r"niet|geen|morgen|overmorgen|en|of|maar")
_EN: Final = _gap(r"not|never|tomorrow|and|or|but")
_PT: Final = _gap(r"nao|amanha|e|ou|mas")
_ES: Final = _gap(r"no|manana|y|o|pero")
_FR: Final = _gap(r"pas|demain|et|ou|mais")
_IT: Final = _gap(r"non|domani|e|o|ma")
# A delivery today whose words a place splits, such as "wird heute an die
# Packstation geliefert" or "will be delivered to the locker today".
_DELIVERY_TODAY_APART: Final = re.compile(
    r"(?<![a-z0-9])(?:"
    rf"wird{_DE}heute{_DE}(?:zugestellt|geliefert)"
    rf"|wordt{_NL}vandaag{_NL}(?:bezorgd|geleverd)"
    rf"|will be delivered{_EN}today"
    rf"|(?<!nao )sera entregue{_PT}hoje"
    rf"|(?<!no )sera entregad[oa]{_ES}hoy"
    rf"|sera livree?{_FR}aujourd'hui"
    rf"|(?<!non )sara consegnat[oa]{_IT}oggi"
    r")(?![a-z0-9])"
)
# The carrier, not the user, took the parcel from a pickup place: one the
# sender dropped off there, now on its way.
_CARRIER_TOOK: Final = re.compile(
    r"(?<![a-z0-9])(?:"
    r"(?:picked up|collected|taken) by (?:the |our |a )?(?:carrier|courier|driver)"
    r"|recolhid[oa] pel[oa] (?:transportadora|estafeta|motorista)"
    r"|recogid[oa] por (?:el |la )?(?:transportista|repartidor|mensajero)"
    r"|(?:collecte|enleve|ramasse)e? par (?:le |la )?(?:transporteur|livreur|coursier)"
    r"|ritirat[oa] dal (?:corriere|vettore)"
    r"|vom (?:zusteller|kurier|fahrer|paketdienst)(?: [a-z0-9'-]+){0,4} abgeholt"
    r"|(?:opgehaald|afgehaald) door de (?:vervoerder|bezorger|koerier|chauffeur)"
    r")(?![a-z0-9])"
)


def origin_id(number: str) -> str:
    """Return the ID of the origin that holds 17TRACK's news about a number."""
    return f"{ORIGIN_PREFIX}{number}"


def friendly_name(parcel_id: str) -> str:
    """Return the generic name a parcel's number gets in 17TRACK."""
    return NAME_PREFIX + parcel_id.removeprefix("p_")[:6]


def map_status(status: Any, info: str | None) -> ParcelStatus | None:
    """Turn a 17TRACK package status and its carrier text into a status.

    17TRACK's "ready to be picked up" is its old "Pick Up" status, which also
    means out for delivery: see :func:`pickup_status`.
    """
    mapped = _STATUSES.get(slugify(str(status or "")))
    if mapped is None:
        return None
    if mapped is ParcelStatus.READY_FOR_PICKUP:
        return pickup_status(info)
    return refine_status(mapped, info)


def pickup_status(info: str | None) -> ParcelStatus:
    """Return what 17TRACK's "ready to be picked up" means, by the carrier's text.

    It's what the text says, such as a pickup, out for delivery or a missed
    attempt. A text that says none of these but names a place where parcels
    wait, such as a locker or a pickup point, is a pickup, unless it says
    the parcel is still on its way there or the carrier took it from there.
    Otherwise it's in transit.
    """
    if (status := _text_status(info)) is not None:
        return status
    text = fold_text(info or "")
    if phrase_regex(KIND_PHRASES[MailKind.IN_TRANSIT]).search(text):
        return ParcelStatus.IN_TRANSIT
    if _CARRIER_TOOK.search(text):
        return ParcelStatus.IN_TRANSIT
    if phrase_regex(PICKUP_PLACES).search(text):
        return ParcelStatus.READY_FOR_PICKUP
    return ParcelStatus.IN_TRANSIT


def refine_status(status: ParcelStatus, info: str | None) -> ParcelStatus:
    """Return the more precise status a tracker's carrier text tells, if any."""
    if status in _REFINED:
        return _text_status(info) or status
    return status


def _text_status(info: str | None) -> ParcelStatus | None:
    """Return the status a carrier's text tells, if it tells one.

    A delivery today counts even when a place splits its words.
    """
    if info:
        text = fold_text(info)
        for kind, status in _INFO_RULES:
            if phrase_regex(KIND_PHRASES[kind]).search(text):
                return status
        if _DELIVERY_TODAY_APART.search(text):
            return ParcelStatus.OUT_FOR_DELIVERY
    return None


def repair_pickups(data: ParcelsData, now: datetime, tz: tzinfo) -> int:
    """Take back the pickups that 17TRACK's pickup status alone gave.

    Before 0.1.13, 17TRACK's "ready to be picked up" was always a pickup, see
    :func:`pickup_status`. Its events whose text doesn't say so get the
    status the text tells, or in transit, in the stored packages and on
    their parcels, with the details read again as the sync reads them.
    0.1.15 runs it once more, as it reads more of the text. Returns how
    many parcels changed.
    """
    pickup = ParcelStatus.READY_FOR_PICKUP
    packages = data.seventeentrack.get("packages")
    # When each package event happened, by its origin, text and stored time.
    happened: dict[tuple[str, Any, Any], datetime | None] = {}
    for number, record in (packages if isinstance(packages, dict) else {}).items():
        if not isinstance(record, dict) or not isinstance(
            history := record.get("history"), list
        ):
            continue
        for entry in history:
            if not isinstance(entry, dict):
                continue
            if entry.get("status") == pickup.value:
                entry["status"] = pickup_status(entry.get("info")).value
            key = (origin_id(str(number)), entry.get("info"), entry.get("time"))
            happened[key] = dt_from_str(entry.get("at"))
    changed = 0
    for parcel in data.parcels.values():
        dirty = False
        for event in parcel.events:
            if event.source is not Source.SEVENTEENTRACK or event.status is not pickup:
                continue
            status = pickup_status(event.label)
            if status is pickup:
                continue
            key = (event.origin or "", event.label, dt_to_str(event.time))
            details = tracker_details(event.label, status, happened.get(key), tz)
            event.status = status
            event.collect_by = details.get("collect_by")
            event.next_attempt = details.get("next_attempt")
            dirty = True
        if dirty:
            parcel.touch(now)
            changed += 1
    return changed


def restore_pickup_places(data: ParcelsData, now: datetime, tz: tzinfo) -> int:
    """Give back the pickups whose text names the place the parcel waits at.

    0.1.13 read 17TRACK's "ready to be picked up" as in transit when the
    carrier's text had no collect wording, also when it named a locker or a
    pickup point (see :func:`pickup_status`). Only a package's latest news
    is known to come with that status, while 17TRACK still gives it: that
    news becomes a pickup again, in the stored package and on its parcel,
    with the details read again as the sync reads them. Returns how many
    parcels changed.
    """
    pickup = ParcelStatus.READY_FOR_PICKUP
    transit = ParcelStatus.IN_TRANSIT.value
    packages = data.seventeentrack.get("packages")
    # When each restored package event happened, by its origin, text and
    # stored time.
    restored: dict[tuple[str, Any, Any], datetime | None] = {}
    for number, record in (packages if isinstance(packages, dict) else {}).items():
        if (
            not isinstance(record, dict)
            or record.get("status") != "ready_to_be_picked_up"
            or not isinstance(history := record.get("history"), list)
            or not history
            or not isinstance(entry := history[-1], dict)
            or entry.get("status") != transit
            or pickup_status(entry.get("info")) is not pickup
        ):
            continue
        entry["status"] = pickup.value
        key = (origin_id(str(number)), entry.get("info"), entry.get("time"))
        restored[key] = dt_from_str(entry.get("at"))
    changed = 0
    for parcel in data.parcels.values() if restored else ():
        dirty = False
        for event in parcel.events:
            key = (event.origin or "", event.label, dt_to_str(event.time))
            if (
                event.source is not Source.SEVENTEENTRACK
                or event.status is not ParcelStatus.IN_TRANSIT
                or key not in restored
            ):
                continue
            details = tracker_details(event.label, pickup, restored[key], tz)
            event.status = pickup
            event.collect_by = details.get("collect_by")
            event.next_attempt = None
            dirty = True
        if dirty:
            parcel.touch(now)
            changed += 1
    return changed


def current_number(parcel: Parcel) -> str | None:
    """Return a parcel's tracking number, normalised, or None."""
    number = parcel.state.tracking_number
    return normalize_tracking_number(number) if number else None


def is_amazon(number: str, carrier: str | None) -> bool:
    """Return True for Amazon Logistics' numbers, which trackers can't follow."""
    return carrier == "amazon" or detect_carrier(number) == "amazon"


def add_order(parcel: Parcel) -> tuple[date, datetime]:
    """Sort key that adds late parcels first, then by date, undated ones last."""
    eta = parcel.state.eta
    return (eta.start if eta is not None else date.max), parcel.created


def clip_text(text: Any) -> str | None:
    """Return text on one line, cut to ``MAX_INFO_CHARS``, or None."""
    value = " ".join(str(text or "").split())
    if not value:
        return None
    return value if len(value) <= MAX_INFO_CHARS else value[: MAX_INFO_CHARS - 1] + "…"


def _package_time(package: Mapping[str, Any], now: datetime) -> datetime | None:
    raw = package.get("timestamp")
    if not raw:
        return None
    parsed = dt_util.parse_datetime(str(raw))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
    return min(dt_util.as_utc(parsed), now)


@dataclass(slots=True)
class _Stats:
    added: int = 0
    updated: int = 0
    archived: int = 0


class SeventeenTrackSync:
    """Keeps 17TRACK's packages in step with the active parcels."""

    def __init__(self, engine: ParcelsEngine) -> None:
        """Initialise the sync of the hub's engine."""
        self.engine = engine
        self.hass = engine.hass
        self._lock = asyncio.Lock()
        self._unsub: CALLBACK_TYPE | None = None
        self._running = False
        self.last_refresh: datetime | None = None
        self.last_error: str | None = None

    # -- State --------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Return True when 17TRACK is turned on in the options."""
        return bool(
            self.engine.options.get(CONF_SEVENTEENTRACK, DEFAULT_SEVENTEENTRACK)
        )

    @property
    def entry_id(self) -> str | None:
        """Return the loaded 17TRACK config entry, if any."""
        entries = self.hass.config_entries.async_loaded_entries(SEVENTEENTRACK_DOMAIN)
        return entries[0].entry_id if entries else None

    @property
    def available(self) -> bool:
        """Return True when 17TRACK is on and its integration is loaded."""
        return self.enabled and self.entry_id is not None

    @property
    def _packages(self) -> dict[str, dict[str, Any]]:
        return self.engine.data.seventeentrack.setdefault("packages", {})

    @property
    def _failed(self) -> dict[str, dict[str, Any]]:
        return self.engine.data.seventeentrack.setdefault("failed", {})

    def diagnostics(self) -> dict[str, Any]:
        """Return counts and errors, without any tracking number."""
        packages = self._packages
        return {
            "enabled": self.enabled,
            "available": self.available,
            "tracked": sum(1 for r in packages.values() if not r.get("archived")),
            "archived": sum(1 for r in packages.values() if r.get("archived")),
            "failed": len(self._failed),
            "last_refresh": dt_to_str(self.last_refresh),
            "last_error": self.last_error,
            "not_found_by_carrier": self._not_found_by_carrier(),
        }

    def _not_found_by_carrier(self) -> dict[str, int]:
        """Count tracked numbers 17TRACK can't find, by their parcel's carrier.

        "unknown" when the parcel or its carrier is gone, "other" for a
        carrier typed by hand.
        """
        counts: dict[str, int] = {}
        for record in self._packages.values():
            if record.get("archived") or record.get("status") != "not_found":
                continue
            parcel = self.engine.data.parcels.get(record.get("parcel") or "")
            carrier = parcel.state.carrier if parcel is not None else None
            if not carrier:
                key = "unknown"
            else:
                key = carrier if carrier in CARRIER_NAMES else "other"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    # -- Scheduling ---------------------------------------------------------

    @callback
    def async_start(self) -> None:
        """Start the periodic refresh."""
        self._running = True
        self._schedule(START_DELAY)

    async def async_stop(self) -> None:
        """Stop the periodic refresh."""
        self._running = False
        self._cancel()

    @callback
    def reconfigure(self) -> None:
        """Apply changed options: refresh soon when 17TRACK was turned on."""
        if not self._running:
            return
        if not self.enabled:
            self._cancel()
        elif self._unsub is None and not self._lock.locked():
            self._schedule(RECONFIGURE_DELAY)

    @callback
    def _cancel(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _schedule(self, delay: float) -> None:
        self._cancel()
        if self._running and self.enabled:
            self._unsub = async_call_later(self.hass, delay, self._async_timer)

    @callback
    def _async_timer(self, _now: datetime) -> None:
        self._unsub = None
        self.engine.async_create_task(self.async_refresh(), "parcels 17track refresh")

    def _busy(self) -> bool:
        today = dt_util.now().date()
        for record in self._packages.values():
            parcel = self.engine.data.parcels.get(record.get("parcel") or "")
            if parcel is None or record.get("archived"):
                continue
            state = parcel.state
            if state.status is ParcelStatus.OUT_FOR_DELIVERY or (
                state.eta is not None
                and not state.terminal
                and state.eta.start <= today <= state.eta.end
            ):
                return True
        return False

    # -- Refresh ------------------------------------------------------------

    async def async_refresh(self) -> None:
        """Add new numbers, read the packages and archive finished ones."""
        try:
            async with self._lock:
                entry_id = self.entry_id if self.enabled else None
                if entry_id is not None:
                    await self._async_sync(entry_id)
        finally:
            self._schedule(
                (BUSY_INTERVAL if self._busy() else INTERVAL).total_seconds()
            )

    async def _async_sync(self, entry_id: str) -> None:
        now = dt_util.utcnow()
        try:
            packages = await self._async_get_packages(entry_id)
        except Exception as err:
            self._failure("get_packages", err)
            return
        # Failed adds and archives below stay visible until the next refresh.
        self.last_error = None
        stats = _Stats()
        changed = await self._async_add_new(entry_id, packages, now, stats)
        changed |= self._update_statuses(packages, now, stats)
        changed |= await self._async_archive(entry_id, packages, now, stats)
        self.last_refresh = now
        if stats.added or stats.updated or stats.archived:
            _LOGGER.debug(
                "17TRACK: added %d, updated %d, archived %d packages",
                stats.added,
                stats.updated,
                stats.archived,
            )
        if changed:
            self.engine.async_changed()
        else:
            self.engine.async_schedule_save()

    @callback
    def _failure(self, action: str, err: BaseException) -> None:
        # Never the message itself: some hold the tracking number.
        error = type(err).__name__
        if (refusal := _REFUSAL.fullmatch(str(err))) is not None:
            error += f" (code {refusal[1]})"
        self.last_error = f"{action}: {error}"
        _LOGGER.warning("17TRACK %s failed (%s)", action, error)

    async def _async_call(
        self, service: str, data: dict[str, Any], *, response: bool = False
    ) -> Any:
        async with asyncio.timeout(SERVICE_TIMEOUT):
            return await self.hass.services.async_call(
                SEVENTEENTRACK_DOMAIN,
                service,
                data,
                blocking=True,
                return_response=response,
            )

    async def _async_get_packages(self, entry_id: str) -> dict[str, dict[str, Any]]:
        result = await self._async_call(
            "get_packages", {"config_entry_id": entry_id}, response=True
        )
        packages: dict[str, dict[str, Any]] = {}
        items = result.get("packages") if isinstance(result, Mapping) else None
        for package in items or ():
            if not isinstance(package, Mapping):
                continue
            number = normalize_tracking_number(
                str(package.get("tracking_number") or "")
            )
            if number:
                packages[number] = dict(package)
        return packages

    # -- Adding -------------------------------------------------------------

    def _wanted(self) -> dict[str, Parcel]:
        """Return the numbers that should be in 17TRACK, with their parcel."""
        wanted: dict[str, Parcel] = {}
        for parcel in self.engine.data.parcels.values():
            if parcel.archived is not None or parcel.private:
                continue
            state = parcel.state
            if state.terminal or (number := current_number(parcel)) is None:
                continue
            if len(number) < MIN_NUMBER_CHARS or is_amazon(number, state.carrier):
                continue
            wanted.setdefault(number, parcel)
        return wanted

    def _cannot_follow(self, number: str, carrier: str | None) -> bool:
        """Return True for numbers 17TRACK can only follow with a postcode."""
        country = self.hass.config.country or ""
        carriers = _NEEDS_POSTCODE | _NEEDS_POSTCODE_IN.get(country, frozenset())
        return (
            PAACK_ID_RE.fullmatch(number) is not None
            or carrier in carriers
            or detect_carrier(number) in carriers
        )

    def _left_out(self, number: str, parcel: Parcel, now: datetime) -> bool:
        """Return True for wanted numbers that still shouldn't be added.

        Ones the user added in 17TRACK, maybe with the postcode, are still
        followed.
        """
        return self._cannot_follow(number, parcel.state.carrier) or is_quiet(
            parcel, now
        )

    async def _async_add_new(
        self,
        entry_id: str,
        packages: dict[str, dict[str, Any]],
        now: datetime,
        stats: _Stats,
    ) -> bool:
        records = self._packages
        failed = self._failed
        adds = 0
        wanted = sorted(self._wanted().items(), key=lambda item: add_order(item[1]))
        for number, parcel in wanted:
            if number in records:
                continue
            if (package := packages.get(number)) is not None:
                # Already there: added by the user, or before the data was lost.
                name = str(package.get("friendly_name") or "")
                records[number] = {
                    "parcel": parcel.id,
                    "own": name.startswith(NAME_PREFIX),
                }
                continue
            if self._left_out(number, parcel, now):
                continue
            failure = failed.get(number)
            if failure is not None and (
                (retry := dt_from_str(failure.get("retry"))) is None or now < retry
            ):
                continue
            if adds >= MAX_ADDS:
                break
            adds += 1
            try:
                await self._async_call(
                    "add_package",
                    {
                        "config_entry_id": entry_id,
                        "package_tracking_number": number,
                        "package_friendly_name": friendly_name(parcel.id),
                    },
                )
            except Exception as err:
                self._failure("add_package", err)
                count = int((failure or {}).get("count", 0)) + 1
                delay = (
                    ADD_RETRY_LATER if count >= ADD_RETRIES else ADD_RETRY_DELAY * count
                )
                failed[number] = {"count": count, "retry": dt_to_str(now + delay)}
                continue
            failed.pop(number, None)
            records[number] = {
                "parcel": parcel.id,
                "own": True,
                "added": dt_to_str(now),
            }
            stats.added += 1
        # Forget failures of numbers that are no longer wanted or left out.
        wanted = self._wanted()
        for number in [
            n
            for n in failed
            if (parcel := wanted.get(n)) is None or self._left_out(n, parcel, now)
        ]:
            del failed[number]
        return False

    # -- Statuses -----------------------------------------------------------

    def _parcel_for(self, number: str, record: dict[str, Any]) -> Parcel | None:
        """Return the parcel a tracked number belongs to, following merges."""
        oid = origin_id(number)
        parcels = self.engine.data.parcels
        parcel = parcels.get(record.get("parcel") or "")
        if parcel is not None and (
            oid in parcel.origins or current_number(parcel) == number
        ):
            return parcel
        for parcel in parcels.values():
            if oid in parcel.origins or current_number(parcel) == number:
                record["parcel"] = parcel.id
                return parcel
        return None

    def _update_statuses(
        self, packages: dict[str, dict[str, Any]], now: datetime, stats: _Stats
    ) -> bool:
        changed = False
        for number, record in self._packages.items():
            package = packages.get(number)
            if package is None or record.get("archived"):
                continue
            parcel = self._parcel_for(number, record)
            if parcel is None or parcel.archived is not None:
                continue
            if current_number(parcel) != number:
                continue
            raw_status = slugify(str(package.get("status") or ""))
            record["status"] = raw_status
            info = clip_text(package.get("info_text")) or clip_text(
                package.get("location")
            )
            status = map_status(raw_status, info)
            if status is None:
                continue
            time = _package_time(package, now)
            history: list[dict[str, Any]] = record.setdefault("history", [])
            key = (status.value, info, dt_to_str(time))
            if (
                history
                and (
                    history[-1].get("status"),
                    history[-1].get("info"),
                    history[-1].get("at"),
                )
                == key
            ):
                continue
            history.append(
                {
                    "status": status.value,
                    "info": info,
                    "at": dt_to_str(time),
                    "time": dt_to_str(time or now),
                }
            )
            del history[:-MAX_HISTORY]
            self._apply(number, parcel, history, now)
            stats.updated += 1
            changed = True
        return changed

    def _apply(
        self,
        number: str,
        parcel: Parcel,
        history: list[dict[str, Any]],
        now: datetime,
    ) -> None:
        events: list[ParcelEvent] = []
        for entry in history:
            try:
                status = ParcelStatus(entry.get("status"))
            except ValueError:
                continue
            events.append(
                ParcelEvent(
                    time=dt_from_str(entry.get("time")) or now,
                    source=Source.SEVENTEENTRACK,
                    status=status,
                    label=entry.get("info"),
                    # Relative days count from the package's own time only.
                    **tracker_details(
                        entry.get("info"),
                        status,
                        dt_from_str(entry.get("at")),
                        self.engine.tz,
                    ),
                )
            )
        first = min((event.time for event in events), default=now)
        origin = Origin(
            id=origin_id(number),
            source=Source.SEVENTEENTRACK,
            time=first,
            label=ORIGIN_LABEL,
            carrier=parcel.state.carrier,
            tracking_number=number,
        )
        apply_contribution(
            self.engine.data, Contribution(origin=origin, events=events), now
        )

    # -- Archiving ----------------------------------------------------------

    async def _async_archive(
        self,
        entry_id: str,
        packages: dict[str, dict[str, Any]],
        now: datetime,
        stats: _Stats,
    ) -> bool:
        changed = False
        records = self._packages
        for number, record in list(records.items()):
            parcel = self._parcel_for(number, record)
            stale = parcel is None or current_number(parcel) != number
            if parcel is not None and stale and _drop_origin(parcel, number, now):
                changed = True
            if record.get("archived"):
                if parcel is None or stale:
                    del records[number]
                continue
            if not record.get("own") or number not in packages:
                if parcel is None or stale:
                    del records[number]
                continue
            if not (stale or self._finished(number, parcel, record, now)):
                continue
            try:
                await self._async_call(
                    "archive_package",
                    {"config_entry_id": entry_id, "package_tracking_number": number},
                )
            except Exception as err:
                self._failure("archive_package", err)
                continue
            stats.archived += 1
            if parcel is None or stale:
                del records[number]
            else:
                record["archived"] = dt_to_str(now)
        return changed

    def _finished(
        self,
        number: str,
        parcel: Parcel | None,
        record: Mapping[str, Any],
        now: datetime,
    ) -> bool:
        if parcel is None:
            return True
        if parcel.archived is not None or parcel.private or parcel.state.terminal:
            return True
        if self._left_out(number, parcel, now):
            return True
        added = dt_from_str(record.get("added"))
        return (
            record.get("status") in _NO_NEWS
            and added is not None
            and now - added >= NOT_FOUND_ARCHIVE
        )


def _drop_origin(parcel: Parcel, number: str, now: datetime) -> bool:
    """Remove 17TRACK's news about a number the parcel no longer has."""
    oid = origin_id(number)
    if oid not in parcel.origins:
        return False
    del parcel.origins[oid]
    parcel.events = [event for event in parcel.events if event.origin != oid]
    parcel.touch(now)
    return True
