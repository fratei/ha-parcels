"""Deduplication: every parcel appears once.

A parcel is assembled from *origins* (see models.py). A new origin joins every
parcel it shares a key with, and those parcels merge into one, which makes
this an incremental union-find where each parcel is one set. The keys are:

* the tracking number together with the carrier. Carriers that hand parcels
  over to each other under the same number count as one family;
* the tracking number alone for international postal (S10) numbers, because
  the carrier changes at the border;
* the Amazon shipment ID;
* the origin ID. It holds the hash of the e-mail's Message-ID, so the same
  e-mail found in two mailboxes is applied once.

Weaker links are used only when no key matches, and they never merge two
existing parcels:

* the same tracking number when one side doesn't know the carrier;
* an order: a shipment absorbs the parcel without a tracking number that an
  order e-mail of the same order created;
* heuristics, which flag the parcel "auto-merged" so the user can undo them:
  the same long tracking number from carriers of different families, or the
  same merchant with overlapping delivery dates when only one parcel fits.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .const import MailKind, ParcelStatus
from .models import (
    AutoMerge,
    Order,
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    Source,
    date_from_str,
    merchant_key,
    new_id,
    order_key,
    time_from_str,
)
from .parsers.base import Eta
from .parsers.tracking import detect_carrier, is_s10, normalize_tracking_number

REASON_SAME_MERCHANT_ETA = "same_merchant_eta"
REASON_SAME_NUMBER = "same_number"

# Shorter numbers from carriers of different families are not linked.
LOOSE_MIN_LENGTH = 10

# Carriers that hand parcels over to each other under the same number.
_FAMILY: dict[str, str] = {
    "ctt_expresso": "ctt",
    "correos_express": "correos",
    "deutsche_post": "dhl",
    "seur": "dpd",
    "evri": "hermes",
    "colissimo": "la_poste",
    "tnt": "fedex",
    "vinted_go": "inpost",
}

UPDATABLE_FIELDS = (
    "merchant",
    "carrier",
    "tracking_number",
    "pickup_point",
    "pickup_code",
)
ETA_FIELDS = ("eta_start", "eta_end", "window_start", "window_end")


class DedupError(Exception):
    """A merge or split that can't be done; ``reason`` is a translation key."""

    def __init__(self, reason: str) -> None:
        """Store the reason."""
        super().__init__(reason)
        self.reason = reason


@dataclass(slots=True)
class Contribution:
    """What one source says about one parcel: an origin and its events."""

    origin: Origin
    events: list[ParcelEvent] = field(default_factory=list)
    private: bool = False
    order_placed: datetime | None = None


@dataclass(frozen=True, slots=True)
class Applied:
    """Where a contribution ended up.

    ``parcel_id`` is None when nothing was recorded, e.g. a cancellation of an
    order Parcels never saw.
    """

    parcel_id: str | None
    created: bool = False
    merged: tuple[str, ...] = ()
    auto_merged: str | None = None


@dataclass(frozen=True, slots=True)
class NumberKey:
    """A normalised tracking number with its carrier family (None if unknown)."""

    number: str
    family: str | None


def carrier_family(carrier: str | None) -> str | None:
    """Return the family of a carrier, or None when the carrier is unknown."""
    if not carrier or carrier == "other":
        return None
    return _FAMILY.get(carrier, carrier)


def manual_origin_id(parcel_id: str) -> str:
    """Return the ID of the origin that holds the user's edits of a parcel."""
    return f"man:{parcel_id}"


def number_key_text(value: str) -> str:
    """Return a tracking number as compared for deduplication.

    Some carriers write "agency/number" (Nacex, MRW) and drop the slash in
    links, so the slash doesn't count.
    """
    return normalize_tracking_number(value).replace("/", "")


def origin_number(origin: Origin) -> NumberKey | None:
    """Return the tracking number of an origin with its carrier family."""
    if not origin.tracking_number:
        return None
    number = number_key_text(origin.tracking_number)
    if not number:
        return None
    return NumberKey(number, carrier_family(origin.carrier or detect_carrier(number)))


def parcel_numbers(parcel: Parcel) -> set[NumberKey]:
    """Return every tracking number a parcel is known by.

    Besides the numbers of its origins this includes the current number with
    the current carrier, so a carrier the user corrected counts.
    """
    keys = {key for origin in parcel.origins.values() if (key := origin_number(origin))}
    state = parcel.state
    if state.tracking_number and (number := number_key_text(state.tracking_number)):
        keys.add(
            NumberKey(number, carrier_family(state.carrier or detect_carrier(number)))
        )
    return keys


def origin_order_keys(origin: Origin, fallback_merchant: str | None = None) -> set[str]:
    """Return the order keys of an origin."""
    merchant = origin.merchant or fallback_merchant
    return {
        key for number in origin.order_numbers if (key := order_key(merchant, number))
    }


def parcel_order_keys(parcel: Parcel) -> set[str]:
    """Return the keys of the orders a parcel belongs to."""
    merchant = parcel.state.merchant
    keys: set[str] = set()
    for origin in parcel.origins.values():
        keys |= origin_order_keys(origin, merchant)
    return keys


def order_parcels(
    data: ParcelsData, key: str, *, include_archived: bool = True
) -> list[Parcel]:
    """Return the parcels of an order."""
    return [
        parcel
        for parcel in data.parcels.values()
        if (include_archived or parcel.archived is None)
        and key in parcel_order_keys(parcel)
    ]


def find_parcels_by_number(data: ParcelsData, number: str) -> list[Parcel]:
    """Return the parcels known by a tracking number, whatever the carrier."""
    wanted = number_key_text(number)
    return [
        parcel
        for parcel in data.parcels.values()
        if any(key.number == wanted for key in parcel_numbers(parcel))
    ]


def _origins_linked(first: Origin, second: Origin) -> bool:
    """Return True when two origins certainly describe the same parcel."""
    if (
        first.amazon_shipment_id
        and first.amazon_shipment_id == second.amazon_shipment_id
    ):
        return True
    key_a, key_b = origin_number(first), origin_number(second)
    if not key_a or not key_b or key_a.number != key_b.number:
        return False
    return (
        is_s10(key_a.number)
        or key_a.family is None
        or key_b.family is None
        or key_a.family == key_b.family
    )


def _most_recent(data: ParcelsData, parcel_ids: Iterable[str]) -> str:
    return max(
        parcel_ids,
        key=lambda pid: (data.parcels[pid].updated, data.parcels[pid].created, pid),
    )


def _overlap(first: Eta, second: Eta) -> bool:
    return first.start <= second.end and second.start <= first.end


def _contribution_eta(events: Iterable[ParcelEvent]) -> Eta | None:
    dated = [event for event in events if event.eta is not None]
    if not dated:
        return None
    return max(dated, key=lambda event: event.time).eta


def _untracked(parcel: Parcel) -> bool:
    """Return True for an open parcel known only from its order."""
    state = parcel.state
    return (
        parcel.archived is None
        and not state.terminal
        and not state.tracking_number
        and not state.amazon_shipment_ids
    )


def _absorbable(data: ParcelsData, origin: Origin, exclude: set[str]) -> set[str]:
    """Return, per order of a shipment, its single parcel without a number."""
    found: set[str] = set()
    for key in origin_order_keys(origin):
        candidates = [
            parcel.id
            for parcel in order_parcels(data, key, include_archived=False)
            if _untracked(parcel)
        ]
        if len(candidates) == 1 and candidates[0] not in exclude:
            found.add(candidates[0])
    return found


def _order_only_target(
    data: ParcelsData, origin: Origin, events: list[ParcelEvent]
) -> str | None:
    """Pick the parcel that order-level news without a number belongs to."""
    parcels: dict[str, Parcel] = {}
    for key in origin_order_keys(origin):
        for parcel in order_parcels(data, key, include_archived=False):
            parcels[parcel.id] = parcel
    if not parcels:
        return None
    cancelled = any(event.status is ParcelStatus.CANCELLED for event in events)
    if cancelled:
        ordered = [
            p.id for p in parcels.values() if p.state.status is ParcelStatus.ORDERED
        ]
        if ordered:
            return _most_recent(data, ordered)
        # A cancellation only applies to parcels that haven't shipped yet;
        # once shipped it's at most a partial cancellation.
        for event in events:
            if event.status is ParcelStatus.CANCELLED:
                event.status = None
    untracked = [pid for pid, parcel in parcels.items() if _untracked(parcel)]
    return _most_recent(data, untracked or parcels)


def _conflicts(parcel: Parcel, origin: Origin) -> bool:
    """Return True when a parcel and an origin can't be the same parcel."""
    state = parcel.state
    if origin.tracking_number and state.tracking_number:
        return True
    if (
        origin.amazon_shipment_id
        and state.amazon_shipment_ids
        and origin.amazon_shipment_id not in state.amazon_shipment_ids
    ):
        return True
    origin_orders = origin_order_keys(origin)
    parcel_orders = parcel_order_keys(parcel)
    return bool(origin_orders and parcel_orders and not origin_orders & parcel_orders)


def _heuristic_target(data: ParcelsData, origin: Origin, eta: Eta | None) -> str | None:
    """Return the single open parcel of the same merchant with overlapping dates."""
    wanted = merchant_key(origin.merchant)
    if not wanted or eta is None:
        return None
    candidates = [
        parcel.id
        for parcel in data.parcels.values()
        if parcel.archived is None
        and not parcel.state.terminal
        and parcel.state.eta is not None
        and merchant_key(parcel.state.merchant) == wanted
        and _overlap(parcel.state.eta, eta)
        and not _conflicts(parcel, origin)
    ]
    return candidates[0] if len(candidates) == 1 else None


def _normalise(origin: Origin) -> None:
    if origin.tracking_number:
        origin.tracking_number = normalize_tracking_number(origin.tracking_number)
    if origin.amazon_shipment_id:
        origin.amazon_shipment_id = origin.amazon_shipment_id.strip()


def _record_orders(
    data: ParcelsData,
    origin: Origin,
    merchant: str | None,
    placed: datetime | None,
    now: datetime,
) -> None:
    merchant = origin.merchant or merchant
    for number in origin.order_numbers:
        if not (key := order_key(merchant, number)):
            continue
        if (order := data.orders.get(key)) is None:
            data.orders[key] = Order(
                key=key, number=number, merchant=merchant, placed_at=placed, created=now
            )
            continue
        if placed and (order.placed_at is None or placed < order.placed_at):
            order.placed_at = placed
        if merchant and not order.merchant:
            order.merchant = merchant


def apply_contribution(
    data: ParcelsData, contribution: Contribution, now: datetime
) -> Applied:
    """Add an origin and its events to the parcel it belongs to.

    Applying the same contribution again replaces the earlier one, so
    reprocessing an e-mail or a repeated 17TRACK sync is harmless.
    """
    origin = contribution.origin
    _normalise(origin)
    events = contribution.events
    for event in events:
        event.origin = origin.id

    strong = {
        pid for pid, parcel in data.parcels.items() if origin.id in parcel.origins
    }
    if origin.amazon_shipment_id:
        strong |= {
            pid
            for pid, parcel in data.parcels.items()
            if any(
                o.amazon_shipment_id == origin.amazon_shipment_id
                for o in parcel.origins.values()
            )
        }
    weak: set[str] = set()
    loose: set[str] = set()
    if number := origin_number(origin):
        for pid, parcel in data.parcels.items():
            for entry in parcel_numbers(parcel):
                if entry.number != number.number:
                    continue
                if is_s10(number.number) or (
                    number.family is not None and entry.family == number.family
                ):
                    strong.add(pid)
                elif number.family is None or entry.family is None:
                    weak.add(pid)
                else:
                    loose.add(pid)

    targets = set(strong)
    reason: str | None = None
    if not targets and weak:
        targets = {_most_recent(data, weak)}
    if (
        not targets
        and loose
        and number is not None
        and len(number.number) >= LOOSE_MIN_LENGTH
    ):
        targets = {_most_recent(data, loose)}
        reason = REASON_SAME_NUMBER
    if number or origin.amazon_shipment_id:
        targets |= _absorbable(data, origin, targets)
    elif not targets and (order_target := _order_only_target(data, origin, events)):
        targets = {order_target}
    if not targets and (
        heuristic := _heuristic_target(data, origin, _contribution_eta(events))
    ):
        targets = {heuristic}
        reason = REASON_SAME_MERCHANT_ETA

    created = False
    merged: tuple[str, ...] = ()
    if targets:
        target_id = min(targets, key=lambda pid: (data.parcels[pid].created, pid))
        merged = tuple(sorted(targets - {target_id}))
        parcel = merge_parcels(data, target_id, merged, now) if merged else None
        parcel = parcel or data.parcels[target_id]
    else:
        has_number = bool(number or origin.amazon_shipment_id)
        statuses = {event.status for event in events if event.status}
        if not has_number and statuses <= {ParcelStatus.CANCELLED} and statuses:
            # Nothing to cancel.
            return Applied(parcel_id=None)
        parcel = Parcel(id=new_id("p"), created=now, updated=now)
        data.parcels[parcel.id] = parcel
        created = True

    if (existing := parcel.origins.get(origin.id)) is not None:
        origin.owners = tuple(sorted(set(existing.owners) | set(origin.owners)))
        origin.confirmed = origin.confirmed or existing.confirmed
    parcel.origins[origin.id] = origin
    parcel.events = [e for e in parcel.events if e.origin != origin.id]
    parcel.events.extend(events)
    parcel.private = parcel.private or contribution.private
    if reason and parcel.auto_merged is None:
        parcel.auto_merged = AutoMerge(origin=origin.id, at=now, reason=reason)
    parcel.touch(now)
    if parcel.archived is not None and not parcel.state.terminal:
        # News about an archived parcel that isn't finished brings it back.
        parcel.archived = None
    _record_orders(data, origin, parcel.state.merchant, contribution.order_placed, now)
    return Applied(
        parcel_id=parcel.id, created=created, merged=merged, auto_merged=reason
    )


def merge_parcels(
    data: ParcelsData, target_id: str, other_ids: Iterable[str], now: datetime
) -> Parcel:
    """Merge parcels into ``target_id``; the others are deleted."""
    target = data.parcels[target_id]
    others = [data.parcels[pid] for pid in dict.fromkeys(other_ids) if pid != target_id]
    if any(parcel.archived is None for parcel in (target, *others)):
        target.archived = None
    for other in others:
        for origin_id, origin in other.origins.items():
            target.origins.setdefault(origin_id, origin)
        known = {event.id for event in target.events}
        target.events.extend(e for e in other.events if e.id not in known)
        target.private = target.private or other.private
        target.created = min(target.created, other.created)
        if target.auto_merged is None:
            target.auto_merged = other.auto_merged
        del data.parcels[other.id]
    target.touch(now)
    return target


def split_parcel(
    data: ParcelsData, parcel_id: str, origin_ids: Iterable[str], now: datetime
) -> Parcel:
    """Move origins and their events out of a parcel into a new one.

    The user's edits stay with the original parcel. Raises DedupError when
    the split is impossible: nothing to move, nothing left behind, or the two
    sides share a tracking number or shipment (the next e-mail would merge
    them again).
    """
    parcel = data.parcels[parcel_id]
    moving = set(origin_ids)
    edit_id = manual_origin_id(parcel_id)
    if not moving:
        raise DedupError("no_origins")
    if not moving <= parcel.origins.keys() or edit_id in moving:
        raise DedupError("unknown_origin")
    staying = [o for oid, o in parcel.origins.items() if oid not in moving]
    if not [o for o in staying if o.id != edit_id]:
        raise DedupError("nothing_left")
    if any(
        _origins_linked(parcel.origins[oid], other)
        for oid in moving
        for other in staying
    ):
        raise DedupError("shared_number")

    new = Parcel(id=new_id("p"), created=now, updated=now, private=parcel.private)
    for oid in sorted(moving):
        new.origins[oid] = parcel.origins.pop(oid)
    new.events = [event for event in parcel.events if event.origin in moving]
    parcel.events = [event for event in parcel.events if event.origin not in moving]
    if parcel.auto_merged and parcel.auto_merged.origin in moving:
        parcel.auto_merged = None
    data.parcels[new.id] = new
    parcel.touch(now)
    new.touch(now)
    return new


def undo_auto_merge(data: ParcelsData, parcel_id: str, now: datetime) -> Parcel | None:
    """Undo a heuristic merge, returning the parcel that was split off.

    The origin that was linked by the heuristic leaves together with every
    origin that shares its tracking number or shipment. When nothing would be
    left behind, only the flag is cleared and None is returned.
    """
    parcel = data.parcels[parcel_id]
    flag = parcel.auto_merged
    parcel.auto_merged = None
    parcel.touch(now)
    if flag is None or flag.origin not in parcel.origins:
        return None
    component = {flag.origin}
    pending = [parcel.origins[flag.origin]]
    while pending:
        current = pending.pop()
        for oid, other in parcel.origins.items():
            if oid not in component and _origins_linked(current, other):
                component.add(oid)
                pending.append(other)
    try:
        return split_parcel(data, parcel_id, component, now)
    except DedupError:
        return None


def remove_message(data: ParcelsData, message_hash: str, now: datetime) -> set[str]:
    """Remove what an e-mail contributed, e.g. before reprocessing it.

    Returns the IDs of the parcels that changed; parcels left without origins
    are deleted.
    """
    prefix = f"msg:{message_hash}#"
    affected: set[str] = set()
    for parcel in list(data.parcels.values()):
        removed = {
            oid
            for oid, origin in parcel.origins.items()
            if origin.message == message_hash or oid.startswith(prefix)
        }
        if not removed:
            continue
        affected.add(parcel.id)
        for oid in removed:
            del parcel.origins[oid]
        parcel.events = [e for e in parcel.events if e.origin not in removed]
        if parcel.auto_merged and parcel.auto_merged.origin in removed:
            parcel.auto_merged = None
        if parcel.origins:
            parcel.touch(now)
        else:
            del data.parcels[parcel.id]
    return affected


def add_owner(
    data: ParcelsData, message_hash: str, owner: str, now: datetime
) -> set[str]:
    """Record that an e-mail was also found in another person's mailbox."""
    affected: set[str] = set()
    for parcel in data.parcels.values():
        changed = False
        for origin in parcel.origins.values():
            if origin.message == message_hash and owner not in origin.owners:
                origin.owners = tuple(sorted({*origin.owners, owner}))
                changed = True
        if changed:
            parcel.touch(now)
            affected.add(parcel.id)
    return affected


def _edit_origin(parcel: Parcel, now: datetime) -> Origin:
    origin_id = manual_origin_id(parcel.id)
    if (origin := parcel.origins.get(origin_id)) is None:
        origin = parcel.origins[origin_id] = Origin(
            id=origin_id, source=Source.MANUAL, time=now
        )
    origin.time = now
    return origin


def update_parcel(
    data: ParcelsData, parcel_id: str, changes: Mapping[str, Any], now: datetime
) -> Parcel:
    """Apply the user's edits to a parcel.

    A key that is present with the value None clears that field. Changing the
    tracking number to one another parcel already has merges the two.
    Besides the fields, ``confirm`` confirms what the local AI found and
    ``confirm_merge`` keeps an automatic merge.
    """
    parcel = data.parcels[parcel_id]
    edits = {key: changes[key] for key in UPDATABLE_FIELDS if key in changes}
    if edits or any(key in changes for key in ETA_FIELDS):
        origin = _edit_origin(parcel, now)
        for key, value in edits.items():
            text = str(value).strip() if value is not None else ""
            if key == "tracking_number":
                text = normalize_tracking_number(text)
            setattr(origin, key, text)
        if any(key in changes for key in ETA_FIELDS):
            parcel.events.append(_eta_event(parcel, changes, origin.id, now))
    if "private" in changes:
        parcel.private = bool(changes["private"])
    if changes.get("confirm"):
        for origin in parcel.origins.values():
            if origin.source is Source.AI:
                origin.confirmed = True
    if changes.get("confirm_merge"):
        parcel.auto_merged = None
    parcel.touch(now)

    if edits.get("tracking_number") and (
        number := origin_number(_edit_origin(parcel, now))
    ):
        same = {
            other.id
            for other in data.parcels.values()
            if other.id != parcel_id
            and any(
                entry.number == number.number
                and (
                    is_s10(number.number)
                    or entry.family is None
                    or number.family is None
                    or entry.family == number.family
                )
                for entry in parcel_numbers(other)
            )
        }
        if same:
            merge_parcels(data, parcel_id, same, now)
    return parcel


def _eta_event(
    parcel: Parcel, changes: Mapping[str, Any], origin_id: str, now: datetime
) -> ParcelEvent:
    current = parcel.state.eta

    def pick(key: str, fallback: Any) -> Any:
        return changes.get(key, fallback)

    start = date_from_str(pick("eta_start", current.start if current else None))
    if start is None:
        return ParcelEvent(
            time=now, source=Source.MANUAL, origin=origin_id, clears_eta=True
        )
    end = date_from_str(pick("eta_end", current.end if current else None)) or start
    window_start = time_from_str(
        pick("window_start", current.window_start if current else None)
    )
    window_end = time_from_str(
        pick("window_end", current.window_end if current else None)
    )
    if "eta_start" in changes and "eta_end" not in changes and end < start:
        end = start
    return ParcelEvent(
        time=now,
        source=Source.MANUAL,
        origin=origin_id,
        eta=Eta(
            start=start,
            end=max(start, end),
            window_start=window_start,
            window_end=window_end,
        ),
    )


def mark_delivered(data: ParcelsData, parcel_id: str, now: datetime) -> Parcel:
    """Mark a parcel delivered now, whatever its status."""
    parcel = data.parcels[parcel_id]
    origin = _edit_origin(parcel, now)
    parcel.events.append(
        ParcelEvent(
            time=now,
            source=Source.MANUAL,
            origin=origin.id,
            status=ParcelStatus.DELIVERED,
            kind=MailKind.DELIVERED,
            force=True,
        )
    )
    parcel.touch(now)
    return parcel


def archive_parcel(data: ParcelsData, parcel_id: str, now: datetime) -> Parcel:
    """Archive a parcel: it leaves the lists but stays in past weeks."""
    parcel = data.parcels[parcel_id]
    if parcel.archived is None:
        parcel.archived = now
        parcel.updated = now
    return parcel
