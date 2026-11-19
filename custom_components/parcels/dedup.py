"""Deduplication: every parcel appears once.

A parcel is assembled from *origins* (see models.py). A new origin joins every
parcel it shares a key with, and those parcels merge into one, which makes
this an incremental union-find where each parcel is one set. The keys are:

* the tracking number together with the carrier. Carriers that hand parcels
  over to each other under the same number count as one family;
* the tracking number alone for international postal (S10) numbers, because
  the carrier changes at the border;
* the Amazon shipment ID. Paack's order ID for an Amazon parcel is that
  shipment ID, written the same way, then "_" and the package number;
* the origin ID. It holds the hash of the e-mail's Message-ID, so the same
  e-mail found in two mailboxes is applied once.

Weaker links are used only when no key matches, and they never merge two
existing parcels:

* the same tracking number when one side doesn't know the carrier;
* an order: a shipment absorbs the parcel without a tracking number that an
  order e-mail of the same order created. When the order has several, the
  one with the shipment's items;
* heuristics, which flag the parcel "auto-merged" so the user can undo them:
  the same long tracking number from carriers of different families, the
  order's only open parcel with the same items (or, for a "delivered" e-mail
  without items, the order's only open parcel), or the same merchant with
  overlapping delivery dates when only one parcel fits.

After a sync, :func:`reconcile` looks at whole parcels again, because e-mails
arrive in any order and a shop's e-mail rarely names the carrier's number:

* parcels of one order that are the same package join: the same items, or a
  "delivered" e-mail without items and the order's only other parcel;
* a shop's single parcel without a tracking number joins the tracked
  shipments that the same sender domain announces within a few days;
* a parcel without a tracking number joins the tracked parcel of the same
  merchant delivered on its date, when they are the only two that fit. When
  more fit, the user gets merge suggestions instead.

Item titles never link different orders, and titles that unrelated orders
share (a shop's recommendations read as items) don't count at all.

:func:`infer_deliveries` then closes parcels without a tracking number whose
date has passed when the same merchant delivered another parcel then. Shops
pack several orders in one carrier parcel, so these are marked as inferred,
not merged.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
import hashlib
from itertools import combinations
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
    is_carrier_mail,
    local_date,
    merchant_key,
    new_id,
    order_key,
    time_from_str,
)
from .parsers.base import Eta
from .parsers.carriers import brand_carriers
from .parsers.items import item_key, same_key
from .parsers.senders import (
    is_free_mail,
    lookup,
    organizational_domain,
    ships_with_many,
)
from .parsers.tracking import (
    detect_carrier,
    is_s10,
    normalize_tracking_number,
    paack_stem,
    tracking_url,
    validate_tracking_number,
)

REASON_SAME_MERCHANT_ETA = "same_merchant_eta"
REASON_SAME_NUMBER = "same_number"
REASON_SAME_MERCHANT_DAY = "same_merchant_day"
REASON_SAME_MERCHANT_DOMAIN = "same_merchant_domain"
REASON_SAME_ORDER = "same_order"

# How far back reconcile() looks, and how soon after a shop's order e-mails
# its tracked shipments must follow to absorb the order's parcel.
RECONCILE_WINDOW = timedelta(days=30)
DOMAIN_ABSORB_WINDOW = timedelta(days=7)
# A delivery this many days around a parcel's dates counts for inference.
INFER_MARGIN = timedelta(days=1)
# A shop's parcel up to this many days late, or due this many days later,
# could still be the package a carrier delivers: shops deliver early too.
LATE_DAYS = timedelta(days=14)
EARLY_DAYS = timedelta(days=7)

# Engine-state keys: pairs of origins the user keeps apart, and the version
# of the one-time repair of stored parcels.
KEPT_APART = "kept_apart"
REPAIR_KEY = "repair"
REPAIR_VERSION = 3
# Before any stored news: the one-time repair looks at every parcel.
_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)

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
    # Only joins a parcel that exists, e.g. an e-mail with just a delivery code.
    attach_only: bool = False
    # Joins the parcel holding this origin ID, or nothing when no parcel does:
    # what the AI filled in for an e-mail goes with the e-mail's parser origin.
    anchor: str | None = None


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


def _paack_stem(origin: Origin) -> str | None:
    """Return the shipment a Paack order ID names, as written."""
    if carrier_family(origin.carrier) != "paack":
        return None
    return paack_stem(origin.tracking_number)


def _names_shipment(paack: Origin, amazon: Origin) -> bool:
    stem = _paack_stem(paack)
    return stem is not None and stem == amazon.amazon_shipment_id


def _same_shipment(first: Origin, second: Origin) -> bool:
    """Return True when two origins are about the same Amazon shipment.

    Both give its shipment ID, or one is Paack's order ID whose part before
    "_" is the other's shipment ID. Case counts: the IDs are case-sensitive.
    """
    if (
        first.amazon_shipment_id
        and first.amazon_shipment_id == second.amazon_shipment_id
    ):
        return True
    return _names_shipment(first, second) or _names_shipment(second, first)


def _origins_linked(first: Origin, second: Origin) -> bool:
    """Return True when two origins certainly describe the same parcel."""
    if _same_shipment(first, second):
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


def paack_amazon_counts(data: ParcelsData) -> dict[str, dict[str, int]]:
    """Count Paack's e-mails by whether their order ID names an Amazon shipment.

    Each e-mail counts once: "matched" when the part of its order ID before
    "_" is the shipment ID of an Amazon e-mail, "unmatched" when no Amazon
    shipment fits, "without_id" when no order ID was read. The counts hold
    no ID or shop name.
    """
    shipments = {
        origin.amazon_shipment_id
        for origin in _all_origins(data)
        if origin.amazon_shipment_id
    }
    emails: defaultdict[str, list[Origin]] = defaultdict(list)
    for origin in _all_origins(data):
        if (info := lookup(origin.label)) is not None and info.carrier == "paack":
            emails[origin.message or origin.id].append(origin)
    counts = {
        group: {"matched": 0, "unmatched": 0, "without_id": 0}
        for group in ("naming_amazon", "not_naming_amazon")
    }
    for origins in emails.values():
        stems = {stem for origin in origins if (stem := _paack_stem(origin))}
        if stems & shipments:
            result = "matched"
        else:
            result = "unmatched" if stems else "without_id"
        amazon = any(merchant_key(origin.merchant) == "amazon" for origin in origins)
        counts["naming_amazon" if amazon else "not_naming_amazon"][result] += 1
    return counts


def _most_recent(data: ParcelsData, parcel_ids: Iterable[str]) -> str:
    return max(
        parcel_ids,
        key=lambda pid: (data.parcels[pid].updated, data.parcels[pid].created, pid),
    )


def _overlap(first: Eta, second: Eta) -> bool:
    return first.start <= second.end and second.start <= first.end


def _could_arrive(eta: Eta, start: date, end: date) -> bool:
    """Return True when a parcel due on ``eta`` could arrive in [start, end].

    It may be late, or early.
    """
    return start - LATE_DAYS <= eta.end and eta.start <= end + EARLY_DAYS


def _same_carrier(first: str | None, second: str | None) -> bool:
    """Return False only when both carriers are known and of other families."""
    one, two = carrier_family(first), carrier_family(second)
    return one is None or two is None or one == two


def _contribution_eta(events: Iterable[ParcelEvent]) -> Eta | None:
    events = list(events)
    dated = [event for event in events if event.eta is not None]
    if dated:
        return max(dated, key=lambda event: event.time).eta
    # A carrier's "out for delivery" or "delivered" e-mail dates the parcel.
    done = [
        event
        for event in events
        if event.status in (ParcelStatus.OUT_FOR_DELIVERY, ParcelStatus.DELIVERED)
    ]
    if not done:
        return None
    day = local_date(max(done, key=lambda event: event.time).time)
    return Eta(start=day, end=day)


def _untracked(parcel: Parcel) -> bool:
    """Return True for an open parcel known only from its order."""
    state = parcel.state
    return (
        parcel.archived is None
        and not state.terminal
        and not state.tracking_number
        and not state.amazon_shipment_ids
    )


def _finished(parcel: Parcel) -> bool:
    """Return True for a parcel that news or the user closed, not a guess."""
    state = parcel.state
    return state.terminal and not state.inferred


def _item_keys(items: Iterable[str]) -> set[str]:
    return {key for item in items if (key := item_key(item))}


def _noise_items(parcels: Iterable[Parcel]) -> frozenset[str]:
    """Return the item titles that unrelated orders share.

    A shop's recommendations ("buy it again") read as items make the same
    titles turn up in orders that have nothing in common, and so does an item
    bought again. Such titles don't tell which parcel an e-mail is about.
    """
    orders: dict[str, list[frozenset[str]]] = defaultdict(list)
    for parcel in parcels:
        if keys := frozenset(parcel_order_keys(parcel)):
            for item in _item_keys(parcel.state.items):
                orders[item].append(keys)
    # A title cut short counts as the full title it starts with.
    titles = sorted(orders)
    group = {title: title for title in titles}
    for index, short in enumerate(titles):
        for full in titles[index + 1 :]:
            if not full.startswith(short):
                break
            if same_key(short, full):
                group[full] = group[short]
    shared: dict[str, list[frozenset[str]]] = defaultdict(list)
    for title, keys in orders.items():
        shared[group[title]].extend(keys)
    noisy = {
        name
        for name, keys in shared.items()
        if any(first.isdisjoint(second) for first, second in combinations(keys, 2))
    }
    return frozenset(title for title in titles if group[title] in noisy)


def _is_noise(key: str, noise: Collection[str]) -> bool:
    return key in noise or any(same_key(key, other) for other in noise)


def _same_items(
    first: Iterable[str], second: Iterable[str], noise: Collection[str]
) -> bool:
    """Return True when the item titles of one side are all on the other.

    Titles in ``noise`` don't count; with none left on a side, it's False.
    """
    one = [key for key in first if not _is_noise(key, noise)]
    two = [key for key in second if not _is_noise(key, noise)]
    if not one or not two:
        return False
    fewer, more = sorted((one, two), key=len)
    return all(any(same_key(key, other) for other in more) for key in fewer)


def _different_items(
    first: Iterable[str], second: Iterable[str], noise: Collection[str]
) -> bool:
    """Return True when both sides list items and they aren't the same ones."""
    one = [key for key in first if not _is_noise(key, noise)]
    two = [key for key in second if not _is_noise(key, noise)]
    return bool(one and two) and not _same_items(one, two, ())


def _absorbable(
    data: ParcelsData, origin: Origin, exclude: set[str]
) -> tuple[set[str], str | None]:
    """Return, per order of a shipment, the parcel without a number it absorbs.

    That's the order's only such parcel, unless it lists other items. Of
    several, it's the only one with the shipment's items, and the merge is
    flagged so the user can undo it.
    """
    found: set[str] = set()
    reason: str | None = None
    items = _item_keys(origin.items)
    noise: frozenset[str] = frozenset()
    if items:
        noise = _noise_items(data.parcels.values())
    for key in origin_order_keys(origin):
        candidates = [
            parcel
            for parcel in order_parcels(data, key, include_archived=False)
            if _untracked(parcel)
        ]
        several = len(candidates) > 1
        if items:
            candidates = [
                parcel
                for parcel in candidates
                if not _different_items(items, _item_keys(parcel.state.items), noise)
            ]
            if len(candidates) > 1:
                candidates = [
                    parcel
                    for parcel in candidates
                    if _same_items(items, _item_keys(parcel.state.items), noise)
                ]
        elif several:
            continue
        if len(candidates) != 1 or candidates[0].id in exclude:
            continue
        found.add(candidates[0].id)
        if several:
            reason = REASON_SAME_ORDER
    return found, reason


def _same_order_target(
    data: ParcelsData, origin: Origin, events: list[ParcelEvent]
) -> str | None:
    """Return the open parcel of the order that a shipment's e-mail is about.

    The e-mail names a tracking number or shipment that no parcel has yet.
    It belongs to the order's only open parcel with its items. Without
    items, it belongs to the order's only open parcel when a carrier sent it
    or when it says the parcel was delivered or returned.
    """
    candidates: dict[str, Parcel] = {}
    for key in origin_order_keys(origin):
        for parcel in order_parcels(data, key, include_archived=False):
            if not _finished(parcel) and not _conflicts(parcel, origin):
                candidates[parcel.id] = parcel
    if not candidates:
        return None
    noise = _noise_items(data.parcels.values())
    items = [key for key in _item_keys(origin.items) if not _is_noise(key, noise)]
    if items:
        matches = [
            pid
            for pid, parcel in candidates.items()
            if _same_items(items, _item_keys(parcel.state.items), noise)
        ]
        return matches[0] if len(matches) == 1 else None
    closing = any(
        event.status in (ParcelStatus.DELIVERED, ParcelStatus.RETURNED)
        for event in events
    )
    if (closing or is_carrier_mail(origin)) and len(candidates) == 1:
        return next(iter(candidates))
    return None


def _order_only_target(
    data: ParcelsData, origin: Origin, events: list[ParcelEvent]
) -> str | None:
    """Pick the parcel that order-level news without a number belongs to.

    That's the order's only parcel with the e-mail's items, otherwise its
    latest parcel without a number. A parcel with other items is another
    package, so with only those, there's none.
    """
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
    if items := _item_keys(origin.items):
        noise = _noise_items(data.parcels.values())
        same = [
            pid
            for pid, parcel in parcels.items()
            if _same_items(items, _item_keys(parcel.state.items), noise)
        ]
        if len(same) == 1:
            return same[0]
        # A parcel with other items is another package of the order.
        parcels = {
            pid: parcel
            for pid, parcel in parcels.items()
            if not _different_items(items, _item_keys(parcel.state.items), noise)
        }
        if not parcels:
            return None
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
    """Return the only open parcel of the same merchant the e-mail can be about.

    Its dates must overlap the e-mail's, and no other parcel of the merchant
    may be late, or due soon enough, to be the one instead. A parcel with
    other items, or another carrier, than the e-mail's isn't a candidate.
    """
    wanted = merchant_key(origin.merchant)
    if not wanted or eta is None:
        return None
    candidates = [
        parcel
        for parcel in data.parcels.values()
        if parcel.archived is None
        and not parcel.state.terminal
        and parcel.state.eta is not None
        and merchant_key(parcel.state.merchant) == wanted
        and _could_arrive(parcel.state.eta, eta.start, eta.end)
        and _same_carrier(parcel.state.carrier, origin.carrier)
        and not _conflicts(parcel, origin)
    ]
    if candidates and (items := _item_keys(origin.items)):
        noise = _noise_items(data.parcels.values())
        candidates = [
            parcel
            for parcel in candidates
            if not _different_items(items, _item_keys(parcel.state.items), noise)
        ]
    if len(candidates) != 1:
        return None
    only = candidates[0]
    return only.id if only.state.eta and _overlap(only.state.eta, eta) else None


def _normalise(origin: Origin) -> None:
    if origin.tracking_number:
        origin.tracking_number = normalize_tracking_number(origin.tracking_number)
    if origin.amazon_shipment_id:
        origin.amazon_shipment_id = origin.amazon_shipment_id.strip()


def _record_orders(
    data: ParcelsData,
    parcel: Parcel,
    now: datetime,
    origin_id: str | None = None,
    placed: datetime | None = None,
) -> None:
    """Make sure every order of a parcel has a record.

    A short order number only has a key once the merchant is known, which can
    come from a later e-mail or from the user, so every change that can set
    the merchant records the parcel's orders again. ``placed`` is the order
    date given by the e-mail of ``origin_id``.
    """
    fallback = parcel.state.merchant
    for origin in parcel.origins.values():
        merchant = origin.merchant or fallback
        when = placed if origin.id == origin_id else None
        for number in origin.order_numbers:
            if not (key := order_key(merchant, number)):
                continue
            if (order := data.orders.get(key)) is None:
                data.orders[key] = Order(
                    key=key,
                    number=number,
                    merchant=merchant,
                    placed_at=when,
                    created=now,
                )
                continue
            if when and (order.placed_at is None or when < order.placed_at):
                order.placed_at = when
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
    _brand_carrier(origin)
    _name_merchant(data, origin)
    events = contribution.events
    for event in events:
        event.origin = origin.id

    strong = {
        pid for pid, parcel in data.parcels.items() if origin.id in parcel.origins
    }
    if contribution.anchor is not None and not strong:
        strong = {
            pid
            for pid, parcel in data.parcels.items()
            if contribution.anchor in parcel.origins
        }
        if not strong:
            return Applied(parcel_id=None)
    if origin.amazon_shipment_id or _paack_stem(origin):
        strong |= {
            pid
            for pid, parcel in data.parcels.items()
            if any(_same_shipment(origin, o) for o in parcel.origins.values())
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
        absorbed, absorb_reason = _absorbable(data, origin, targets)
        targets |= absorbed
        if not targets and (same := _same_order_target(data, origin, events)):
            targets = {same}
            absorb_reason = REASON_SAME_ORDER
        reason = reason or absorb_reason
    elif not targets and (order_target := _order_only_target(data, origin, events)):
        targets = {order_target}
    if (
        not targets
        and not contribution.attach_only
        and (heuristic := _heuristic_target(data, origin, _contribution_eta(events)))
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
        if contribution.attach_only:
            # Nothing it belongs to.
            return Applied(parcel_id=None)
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
    # News about the parcel replaces a delivery Parcels only inferred.
    parcel.events = [
        e for e in parcel.events if e.origin != origin.id and not e.inferred
    ]
    parcel.events.extend(events)
    parcel.private = parcel.private or contribution.private
    if reason:
        parcel.auto_merged = (
            AutoMerge(origin=origin.id, at=now, reason=reason)
            if parcel.auto_merged is None
            else _grown(parcel.auto_merged, parcel, {origin.id})
        )
    parcel.touch(now)
    if parcel.archived is not None and not parcel.state.terminal:
        # News about an archived parcel that isn't finished brings it back.
        parcel.archived = None
    _record_orders(data, parcel, now, origin.id, contribution.order_placed)
    return Applied(
        parcel_id=parcel.id, created=created, merged=merged, auto_merged=reason
    )


def merge_parcels(
    data: ParcelsData,
    target_id: str,
    other_ids: Iterable[str],
    now: datetime,
    *,
    keep_archived: bool = False,
) -> Parcel:
    """Merge parcels into ``target_id``; the others are deleted.

    The result is archived only when every parcel was, unless
    ``keep_archived`` keeps the target's own state. Inferred deliveries are
    dropped: they were guesses about one of the parcels.
    """
    target = data.parcels[target_id]
    others = [data.parcels[pid] for pid in dict.fromkeys(other_ids) if pid != target_id]
    if not keep_archived and any(
        parcel.archived is None for parcel in (target, *others)
    ):
        target.archived = None
    for other in others:
        for origin_id, origin in other.origins.items():
            target.origins.setdefault(origin_id, origin)
        known = {event.id for event in target.events}
        target.events.extend(e for e in other.events if e.id not in known)
        target.private = target.private or other.private
        target.delivery_rejected = target.delivery_rejected or other.delivery_rejected
        target.created = min(target.created, other.created)
        if target.auto_merged is None:
            target.auto_merged = other.auto_merged
        del data.parcels[other.id]
    if others:
        target.events = [event for event in target.events if not event.inferred]
    target.touch(now)
    _record_orders(data, target, now)
    return target


def split_parcel(
    data: ParcelsData, parcel_id: str, origin_ids: Iterable[str], now: datetime
) -> Parcel:
    """Move origins and their events out of a parcel into a new one.

    The user's edits stay with the original parcel, and the two parcels are
    kept apart, so reconciling doesn't merge them again. Raises DedupError
    when the split is impossible: nothing to move, nothing left behind, or
    the two sides share a tracking number or shipment (the next e-mail would
    merge them again).
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
    if parcel.auto_merged and parcel.auto_merged.all_origins & moving:
        parcel.auto_merged = None
    data.parcels[new.id] = new
    parcel.touch(now)
    new.touch(now)
    _record_orders(data, parcel, now)
    _record_orders(data, new, now)
    keep_apart(data, parcel, new)
    return new


def undo_auto_merge(data: ParcelsData, parcel_id: str, now: datetime) -> Parcel | None:
    """Undo a heuristic merge, returning the parcel that was split off.

    The origins that were linked by the heuristic leave together with every
    origin that shares their tracking number or shipment. When nothing would
    be left behind, only the flag is cleared and None is returned. The two
    parcels are then kept apart, so they aren't merged again.
    """
    parcel = data.parcels[parcel_id]
    flag = parcel.auto_merged
    parcel.auto_merged = None
    parcel.touch(now)
    if flag is None:
        return None
    component = flag.all_origins & parcel.origins.keys()
    if not component:
        return None
    pending = [parcel.origins[oid] for oid in component]
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
        if (flag := parcel.auto_merged) is not None:
            if flag.origin in removed:
                parcel.auto_merged = None
            elif set(flag.origins) & removed:
                parcel.auto_merged = replace(
                    flag,
                    origins=tuple(oid for oid in flag.origins if oid not in removed),
                )
        if parcel.origins:
            parcel.touch(now)
            _record_orders(data, parcel, now)
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
    Besides the fields, ``confirm`` confirms what the local AI found,
    ``confirm_merge`` keeps an automatic merge and ``confirm_delivery`` keeps
    an inferred delivery.
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
    if changes.get("confirm_delivery"):
        origin = _edit_origin(parcel, now)
        for event in parcel.events:
            if event.inferred:
                event.inferred = False
                event.source = Source.MANUAL
                event.origin = origin.id
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
    _record_orders(data, parcel, now)
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
    """Archive a parcel: it leaves the lists but stays in past weeks.

    Its delivery codes go: nobody needs them any more.
    """
    parcel = data.parcels[parcel_id]
    if parcel.archived is None:
        parcel.archived = now
        parcel.updated = now
    parcel.drop_codes()
    return parcel


# --- Parcels the user keeps apart ----------------------------------------------


def _kept_apart_pairs(
    data: ParcelsData,
) -> list[tuple[frozenset[str], frozenset[str]]]:
    """Return the pairs of origin sets that the user keeps apart."""
    raw = data.engine.get(KEPT_APART)
    pairs: list[tuple[frozenset[str], frozenset[str]]] = []
    if not isinstance(raw, list):
        return pairs
    for entry in raw:
        if not isinstance(entry, list | tuple) or len(entry) != 2:
            continue
        sides = [
            frozenset(str(item) for item in side if item)
            for side in entry
            if isinstance(side, list | tuple)
        ]
        if len(sides) == 2 and all(sides):
            pairs.append((sides[0], sides[1]))
    return pairs


def keep_apart(data: ParcelsData, first: Parcel, second: Parcel) -> None:
    """Remember that two parcels differ, so they aren't merged again.

    The pair is stored by origin IDs, which survive merges with other parcels.
    """
    left, right = frozenset(first.origins), frozenset(second.origins)
    if not left or not right or left & right:
        return
    pairs = _kept_apart_pairs(data)
    if (left, right) in pairs or (right, left) in pairs:
        return
    pairs.append((left, right))
    data.engine[KEPT_APART] = [[sorted(a), sorted(b)] for a, b in pairs]


def prune_kept_apart(data: ParcelsData) -> None:
    """Forget pairs whose parcels are gone or were merged after all."""
    pairs = _kept_apart_pairs(data)
    owner = {
        origin_id: parcel.id
        for parcel in data.parcels.values()
        for origin_id in parcel.origins
    }
    kept: list[list[list[str]]] = []
    for pair in pairs:
        left, right = ({oid for oid in side if oid in owner} for side in pair)
        if (
            left
            and right
            and not {owner[oid] for oid in left} & {owner[oid] for oid in right}
        ):
            kept.append([sorted(left), sorted(right)])
    if kept:
        data.engine[KEPT_APART] = kept
    else:
        data.engine.pop(KEPT_APART, None)


def _apart_checker(data: ParcelsData) -> Callable[[Parcel, Parcel], bool]:
    """Return a test for two parcels that the user keeps apart."""
    pairs = _kept_apart_pairs(data)

    def apart(first: Parcel, second: Parcel) -> bool:
        one, two = first.origins.keys(), second.origins.keys()
        return any(
            (not left.isdisjoint(one) and not right.isdisjoint(two))
            or (not left.isdisjoint(two) and not right.isdisjoint(one))
            for left, right in pairs
        )

    return apart


# --- Shops, carriers and their names -------------------------------------------


def _all_origins(data: ParcelsData) -> Iterator[Origin]:
    for parcel in data.parcels.values():
        yield from parcel.origins.values()


def is_shop(label: str) -> bool:
    """Return True for a sender domain of a shop Parcels doesn't know."""
    return bool(label) and lookup(label) is None and not is_free_mail(label)


def _domain_like(merchant: str, label: str) -> bool:
    """Return True when a merchant name is just the sender's domain."""
    text = merchant.strip().casefold()
    if text == label.casefold():
        return True
    return "." in text and " " not in text and organizational_domain(text) == label


def _merchant_names(
    origins: Iterable[Origin], wanted: str | None = None
) -> dict[str, str]:
    """Return, per sender domain, the merchant name its e-mails agree on.

    Names that only add words agree: ``Casa Verde`` and ``Casa Verde
    Portugal`` give ``Casa Verde``. A domain with unrelated names, carrier
    brands or bare domains only has none.
    """
    found: dict[str, dict[str, tuple[datetime, str]]] = defaultdict(dict)
    for origin in origins:
        label = origin.label
        if origin.message is None or not label or (wanted and label != wanted):
            continue
        name = (origin.merchant or "").strip()
        if not name or _domain_like(name, label) or brand_carriers(name):
            continue
        if not (key := merchant_key(name)):
            continue
        names = found[label]
        if (seen := names.get(key)) is None or (origin.time, name) < seen:
            names[key] = (origin.time, name)
    agreed: dict[str, str] = {}
    for label, names in found.items():
        shortest = min(names, key=lambda key: (len(key), key))
        if all(key.startswith(shortest) for key in names):
            agreed[label] = names[shortest][1]
    return agreed


def known_merchant(data: ParcelsData, label: str) -> str | None:
    """Return the merchant name that e-mails from a sender domain gave."""
    if not label:
        return None
    return _merchant_names(_all_origins(data), label).get(label)


def _brand_carrier(origin: Origin) -> bool:
    """Take an e-mail's carrier from a carrier brand in its sender name.

    Shops forward their carrier's notices under the carrier's name, e.g.
    "GLS PT Informa" from the shop's own domain. The brand counts when the
    tracking number fits exactly one of its carriers. Returns True on change.
    """
    number = origin.tracking_number
    if origin.message is None or origin.carrier or not number or not origin.merchant:
        return False
    fits = [
        carrier
        for carrier in brand_carriers(origin.merchant)
        if validate_tracking_number(number, carrier)
    ]
    if len(fits) != 1:
        return False
    origin.carrier = fits[0]
    if not origin.tracking_url or origin.tracking_url == tracking_url(None, number):
        origin.tracking_url = tracking_url(origin.carrier, number)
    return True


def _name_merchant(
    data: ParcelsData, origin: Origin, names: Mapping[str, str] | None = None
) -> bool:
    """Name the merchant of a shop's e-mail after the shop, never its carrier.

    A carrier brand ("GLS PT Informa") or a bare domain is replaced by the
    name the shop's other e-mails give. Without one, a brand is replaced by
    the shop's domain. ``names`` caches :func:`_merchant_names`. Returns True
    on change.
    """
    label = origin.label
    if origin.message is None or not is_shop(label):
        return False
    merchant = (origin.merchant or "").strip()
    brand = bool(merchant) and bool(brand_carriers(merchant))
    if merchant and not brand and not _domain_like(merchant, label):
        return False
    known = names.get(label) if names is not None else known_merchant(data, label)
    if brand:
        # A domain of the carrier itself has no shop to name.
        name = known or (None if brand_carriers(label) else label)
    else:
        name = known or origin.merchant
    if name == origin.merchant:
        return False
    origin.merchant = name
    return True


# --- Reconciling whole parcels ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class MergeSuggestion:
    """Parcels that are probably one, for the user to merge or keep apart.

    ``parcel_id`` is the parcel with the tracking number; ``candidates`` are
    the parcels without one that may belong to it.
    """

    id: str
    parcel_id: str
    candidates: tuple[str, ...]
    merchant: str | None
    day: date | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        """Serialise the suggestion."""
        return {
            "id": self.id,
            "parcel_id": self.parcel_id,
            "candidates": list(self.candidates),
            "merchant": self.merchant,
            "day": self.day.isoformat() if self.day else None,
            "reason": self.reason,
        }


@dataclass(slots=True)
class Reconciled:
    """What :func:`reconcile` did."""

    changed: set[str] = field(default_factory=set)
    removed: set[str] = field(default_factory=set)
    suggestions: list[MergeSuggestion] = field(default_factory=list)


def _news_times(parcel: Parcel) -> list[datetime]:
    return [
        origin.time
        for origin in parcel.origins.values()
        if origin.source is not Source.MANUAL
    ]


def first_news(parcel: Parcel) -> datetime | None:
    """Return when Parcels first heard of a parcel from a mailbox or 17TRACK."""
    return min(_news_times(parcel), default=None)


def _last_activity(parcel: Parcel) -> datetime | None:
    """Return the time of the latest news, not counting the user's edits."""
    times = _news_times(parcel)
    times.extend(
        event.time
        for event in parcel.events
        if not event.inferred and event.source is not Source.MANUAL
    )
    return max(times, default=None)


def _real_delivery(parcel: Parcel) -> datetime | None:
    """Return when a parcel was delivered, unless that was only inferred."""
    state = parcel.state
    if state.status is ParcelStatus.DELIVERED and not state.inferred:
        return state.delivered_at
    return None


def _reported_delivery(parcel: Parcel) -> datetime | None:
    """Return when an e-mail or 17TRACK said a parcel was delivered.

    A delivery the user marked or confirmed doesn't say which carrier's
    package it was, so it never pairs parcels or infers other deliveries.
    """
    if (delivered := _real_delivery(parcel)) is None:
        return None
    for event in parcel.events:
        if (
            event.time == delivered
            and event.status is ParcelStatus.DELIVERED
            and event.source is not Source.MANUAL
            and not event.inferred
        ):
            return delivered
    return None


def _parcels_conflict(first: Parcel, second: Parcel) -> bool:
    """Return True when two parcels can't be the same parcel."""
    one, two = first.state, second.state
    if one.tracking_number and two.tracking_number:
        return True
    if (
        one.amazon_shipment_ids
        and two.amazon_shipment_ids
        and not set(one.amazon_shipment_ids) & set(two.amazon_shipment_ids)
    ):
        return True
    orders_one, orders_two = parcel_order_keys(first), parcel_order_keys(second)
    return bool(orders_one and orders_two and not orders_one & orders_two)


def _keys_compatible(first: str, second: str) -> bool:
    return (
        not first or not second or first.startswith(second) or second.startswith(first)
    )


def _components(edges: Mapping[str, set[str]]) -> list[set[str]]:
    """Return the connected components of an undirected graph."""
    seen: set[str] = set()
    components: list[set[str]] = []
    for start in sorted(edges):
        if start in seen:
            continue
        component = {start}
        pending = [start]
        while pending:
            for other in edges[pending.pop()]:
                if other not in component:
                    component.add(other)
                    pending.append(other)
        seen |= component
        components.append(component)
    return components


def _suggestion(
    target: Parcel, candidates: Iterable[Parcel], day: date | None, reason: str
) -> MergeSuggestion:
    ordered = sorted(
        candidates,
        key=lambda parcel: (first_news(parcel) or parcel.created, parcel.id),
    )
    ids = tuple(parcel.id for parcel in ordered)
    digest = hashlib.sha1(
        "|".join((target.id, *sorted(ids))).encode(), usedforsecurity=False
    ).hexdigest()[:12]
    return MergeSuggestion(
        id=f"m{digest}",
        parcel_id=target.id,
        candidates=ids,
        merchant=target.state.merchant,
        day=day,
        reason=reason,
    )


def _auto_merge(
    data: ParcelsData,
    target: Parcel,
    other: Parcel,
    reason: str,
    now: datetime,
    result: Reconciled,
) -> None:
    """Merge ``other`` into ``target``, undoably.

    When ``target`` was already merged by a guess, that flag grows to cover
    the new origins too, so one undo takes back every guess. The merged
    parcel stays archived only when it was and nothing open joined it.
    """
    earlier = target.auto_merged
    joining_open = other.archived is None
    moving = sorted(other.origins.values(), key=lambda origin: (origin.time, origin.id))
    merge_parcels(data, target.id, (other.id,), now, keep_archived=True)
    if target.archived is not None and joining_open and not target.state.terminal:
        target.archived = None
    if earlier is not None:
        target.auto_merged = _grown(earlier, target, {origin.id for origin in moving})
    else:
        first = next(
            (origin for origin in moving if origin.source is not Source.MANUAL),
            moving[0],
        )
        target.auto_merged = AutoMerge(
            origin=first.id,
            at=now,
            reason=reason,
            origins=tuple(origin.id for origin in moving if origin.id != first.id),
        )
    result.changed.add(target.id)
    result.removed.add(other.id)


def _grown(flag: AutoMerge, parcel: Parcel, guessed: set[str]) -> AutoMerge:
    """Return a parcel's guess flag grown to cover more guessed origins.

    One undo then takes back every guess.
    """
    linked = (flag.all_origins | guessed) & parcel.origins.keys()
    linked.discard(flag.origin)
    return AutoMerge(
        origin=flag.origin,
        at=flag.at,
        reason=flag.reason,
        origins=tuple(sorted(linked, key=lambda oid: (parcel.origins[oid].time, oid))),
    )


def _may_auto_merge(target: Parcel, other: Parcel) -> bool:
    """Return True when a guessed merge of two parcels can still be undone.

    A parcel merged by an earlier guess gets suggestions instead, except a
    merge of the same order's e-mails, which leaves together on undo.
    """
    return target.auto_merged is None and (
        other.auto_merged is None or other.auto_merged.reason == REASON_SAME_ORDER
    )


def _merge_by_order(
    data: ParcelsData,
    since: datetime | None,
    apart: Callable[[Parcel, Parcel], bool],
    now: datetime,
    result: Reconciled,
) -> None:
    """Merge the parcels of an order that are the same package, undoably.

    Two parcels of an order with the same items are one, unless their
    tracking numbers or shipments differ or both were already finished. A
    "delivered" or "returned" e-mail without items belongs to the order's
    only other parcel when that was still open. Orders without news since
    ``since`` are left alone; None looks at every order.
    """
    noise = _noise_items(data.parcels.values())
    while _merge_one_by_order(data, since, noise, apart, now, result):
        pass


def _merge_one_by_order(
    data: ParcelsData,
    since: datetime | None,
    noise: frozenset[str],
    apart: Callable[[Parcel, Parcel], bool],
    now: datetime,
    result: Reconciled,
) -> bool:
    """Do one merge of :func:`_merge_by_order`; returns False when none is left."""
    by_order: dict[str, list[Parcel]] = defaultdict(list)
    for parcel in sorted(data.parcels.values(), key=lambda p: p.id):
        if parcel.state.status is not ParcelStatus.CANCELLED:
            for key in parcel_order_keys(parcel):
                by_order[key].append(parcel)

    def recent(*parcels: Parcel) -> bool:
        return since is None or any(
            time >= since for parcel in parcels for time in _news_times(parcel)
        )

    def mergeable(first: Parcel, second: Parcel) -> bool:
        return not _parcels_conflict(first, second) and not apart(first, second)

    for parcel in sorted(data.parcels.values(), key=lambda p: p.id):
        state = parcel.state
        if (
            not _finished(parcel)
            or state.status not in (ParcelStatus.DELIVERED, ParcelStatus.RETURNED)
            or state.items
            or state.tracking_number
            or not (keys := parcel_order_keys(parcel))
        ):
            continue
        others = {
            other.id: other
            for key in keys
            for other in by_order[key]
            if other.id != parcel.id
        }
        if len(others) != 1:
            continue
        other = next(iter(others.values()))
        when = state.delivered_at or state.status_time
        first = first_news(other)
        if (
            not _finished(other)
            and when is not None
            and first is not None
            and when >= first
            and recent(parcel, other)
            and mergeable(parcel, other)
        ):
            _auto_merge(data, other, parcel, REASON_SAME_ORDER, now, result)
            return True

    partners: dict[str, set[str]] = defaultdict(set)
    for parcels in by_order.values():
        for first, second in combinations(parcels, 2):
            if (
                not (_finished(first) and _finished(second))
                and recent(first, second)
                and _same_items(
                    _item_keys(first.state.items),
                    _item_keys(second.state.items),
                    noise,
                )
                and mergeable(first, second)
            ):
                partners[first.id].add(second.id)
                partners[second.id].add(first.id)
    for pid in sorted(partners):
        if len(partners[pid]) != 1:
            continue
        other_id = next(iter(partners[pid]))
        if partners[other_id] != {pid}:
            continue
        target, other = sorted(
            (data.parcels[pid], data.parcels[other_id]),
            key=lambda parcel: (
                not parcel.state.tracking_number,
                not parcel.state.amazon_shipment_ids,
                first_news(parcel) or parcel.created,
                parcel.id,
            ),
        )
        _auto_merge(data, target, other, REASON_SAME_ORDER, now, result)
        return True
    return False


def _reconcile_pool(data: ParcelsData, start: datetime) -> list[Parcel]:
    """Return the parcels with recent news that can still be reconciled."""
    return sorted(
        (
            parcel
            for parcel in data.parcels.values()
            if parcel.state.status
            not in (ParcelStatus.CANCELLED, ParcelStatus.RETURNED)
            and any(time >= start for time in _news_times(parcel))
        ),
        key=lambda parcel: (parcel.created, parcel.id),
    )


def _absorb_by_domain(
    data: ParcelsData,
    pool: list[Parcel],
    apart: Callable[[Parcel, Parcel], bool],
    now: datetime,
    result: Reconciled,
) -> None:
    """Let a shop's tracked shipments absorb its parcel without a number.

    A shop often sends an order's "shipped" e-mail without a tracking number
    and then forwards the carrier's notices from its own domain, without the
    order number. The parcel of the "shipped" e-mail joins the shipments that
    follow within a few days, when it's the only such parcel. With several,
    the user gets a suggestion.
    """
    untracked: dict[str, list[Parcel]] = defaultdict(list)
    tracked: dict[str, list[tuple[datetime, Parcel]]] = defaultdict(list)
    for parcel in pool:
        state = parcel.state
        shop_mail: dict[str, datetime] = {}
        for origin in parcel.origins.values():
            if origin.message is not None and is_shop(origin.label):
                when = shop_mail.get(origin.label)
                shop_mail[origin.label] = min(when or origin.time, origin.time)
        for label, when in shop_mail.items():
            if state.tracking_number:
                tracked[label].append((when, parcel))
            elif not state.amazon_shipment_ids and not state.terminal:
                untracked[label].append(parcel)

    edges: dict[str, set[str]] = defaultdict(set)
    first_mail: dict[str, datetime] = {}
    for label, parcels in untracked.items():
        for parcel in parcels:
            first = first_news(parcel)
            last = _last_activity(parcel)
            if first is None or last is None:
                continue
            key = merchant_key(parcel.state.merchant)
            for when, other in tracked.get(label, ()):
                if (
                    first < when <= last + DOMAIN_ABSORB_WINDOW
                    and _keys_compatible(key, merchant_key(other.state.merchant))
                    and not _parcels_conflict(parcel, other)
                    and not apart(parcel, other)
                ):
                    edges[parcel.id].add(other.id)
                    edges[other.id].add(parcel.id)
                    first_mail[other.id] = min(first_mail.get(other.id, when), when)

    for component in _components(edges):
        targets = sorted(
            (pid for pid in component if pid in first_mail),
            key=lambda pid: (first_mail[pid], pid),
        )
        sources = sorted(pid for pid in component if pid not in first_mail)
        target = data.parcels[targets[0]]
        parcels = [data.parcels[pid] for pid in sources]
        if len(parcels) == 1 and _may_auto_merge(target, parcels[0]):
            _auto_merge(
                data, target, parcels[0], REASON_SAME_MERCHANT_DOMAIN, now, result
            )
            continue
        if open_parcels := [parcel for parcel in parcels if parcel.archived is None]:
            result.suggestions.append(
                _suggestion(target, open_parcels, None, REASON_SAME_MERCHANT_DOMAIN)
            )


def _expected_days(parcel: Parcel) -> tuple[date, date] | None:
    """Return the days a parcel without a tracking number arrived or was due."""
    if (delivered := _reported_delivery(parcel)) is not None:
        day = local_date(delivered)
        return day, day
    if (eta := parcel.state.eta) is not None:
        return eta.start, eta.end
    return None


def _delivery_day(parcel: Parcel) -> date | None:
    """Return the day a tracked parcel was delivered or is out for delivery."""
    state = parcel.state
    if (delivered := _real_delivery(parcel)) is not None:
        return local_date(delivered)
    if state.status is ParcelStatus.OUT_FOR_DELIVERY:
        if state.eta is not None:
            return state.eta.end
        if state.status_time is not None:
            return local_date(state.status_time)
    return None


def _pair_by_day(
    data: ParcelsData,
    pool: list[Parcel],
    apart: Callable[[Parcel, Parcel], bool],
    now: datetime,
    result: Reconciled,
) -> None:
    """Pair parcels without a tracking number with a carrier's delivery.

    A shop's e-mail rarely names the carrier's number, and the carrier's
    e-mail doesn't name the order, so the same package shows twice: once
    from the shop and once from the carrier, with the shop's name. When the
    carrier delivers (or is delivering) on the shop's date and they're the
    only two that could be the same package, they merge. An open parcel of
    the shop that is late, or due in the next days, could be it too, and two
    carriers known to differ never pair. Otherwise the user gets suggestions.
    """
    untracked: list[tuple[Parcel, str, date, date, datetime]] = []
    tracked: list[tuple[Parcel, str, date]] = []
    for parcel in pool:
        state = parcel.state
        if not (key := merchant_key(state.merchant)):
            continue
        if state.tracking_number:
            if (day := _delivery_day(parcel)) is not None:
                tracked.append((parcel, key, day))
        elif (expected := _expected_days(parcel)) is not None and (
            first := first_news(parcel)
        ) is not None:
            untracked.append((parcel, key, *expected, first))

    edges: dict[str, set[str]] = defaultdict(set)
    days: dict[str, date] = {}
    fits: set[frozenset[str]] = set()
    for parcel, key, start, end, first in untracked:
        # A parcel may arrive late or early, unless news closed it (a
        # "probably delivered" guess doesn't); only a fit is sure.
        waiting = not _finished(parcel)
        for other, other_key, day in tracked:
            delivered = _real_delivery(other)
            fit = start <= day <= end
            if (
                key == other_key
                and (
                    fit
                    or (waiting and _could_arrive(Eta(start=start, end=end), day, day))
                )
                and _same_carrier(parcel.state.carrier, other.state.carrier)
                and (delivered is None or first < delivered)
                and not _parcels_conflict(parcel, other)
                and not apart(parcel, other)
            ):
                edges[parcel.id].add(other.id)
                edges[other.id].add(parcel.id)
                days[other.id] = day
                if fit:
                    fits.add(frozenset((parcel.id, other.id)))

    for component in _components(edges):
        targets = sorted(pid for pid in component if pid in days)
        sources = sorted(pid for pid in component if pid not in days)
        if (
            len(targets) == 1
            and len(sources) == 1
            and frozenset((targets[0], sources[0])) in fits
        ):
            target = data.parcels[targets[0]]
            other = data.parcels[sources[0]]
            if _may_auto_merge(target, other):
                _auto_merge(data, target, other, REASON_SAME_MERCHANT_DAY, now, result)
                continue
        for target_id in targets:
            target = data.parcels[target_id]
            if target.archived is not None:
                continue
            candidates = [
                data.parcels[pid]
                for pid in sorted(edges[target_id])
                if data.parcels[pid].archived is None
            ]
            if candidates:
                result.suggestions.append(
                    _suggestion(
                        target, candidates, days[target_id], REASON_SAME_MERCHANT_DAY
                    )
                )


def reconcile(
    data: ParcelsData, now: datetime, *, since: datetime | None = None
) -> Reconciled:
    """Look at whole parcels again after a sync and merge the same ones.

    Only parcels with news since ``since`` (default: the last 30 days) are
    looked at. Merges are flagged "auto-merged" so the user can undo them;
    pairs the user kept apart are left alone.
    """
    result = Reconciled()
    prune_kept_apart(data)
    apart = _apart_checker(data)
    start = since or now - RECONCILE_WINDOW

    names = _merchant_names(_all_origins(data))
    for parcel in _reconcile_pool(data, start):
        changed = False
        for origin in parcel.origins.values():
            changed |= _brand_carrier(origin)
            changed |= _name_merchant(data, origin, names)
        if changed:
            parcel.touch(now)
            _record_orders(data, parcel, now)
            result.changed.add(parcel.id)

    _merge_by_order(data, start, apart, now, result)
    _absorb_by_domain(data, _reconcile_pool(data, start), apart, now, result)
    _pair_by_day(data, _reconcile_pool(data, start), apart, now, result)
    result.changed -= result.removed
    return result


def accept_suggestion(
    data: ParcelsData, parcel_id: str, candidate_id: str, now: datetime
) -> Parcel:
    """Merge a suggested parcel into the parcel with the tracking number."""
    if parcel_id == candidate_id:
        raise DedupError("merge_needs_two")
    target, candidate = data.parcels.get(parcel_id), data.parcels.get(candidate_id)
    if target is None or candidate is None:
        raise DedupError("unknown_parcel")
    if _parcels_conflict(target, candidate):
        raise DedupError("cannot_merge")
    return merge_parcels(data, parcel_id, (candidate_id,), now, keep_archived=True)


def dismiss_suggestion(
    data: ParcelsData, parcel_id: str, candidate_ids: Iterable[str]
) -> None:
    """Keep the suggested parcels apart from the parcel with the number."""
    if (target := data.parcels.get(parcel_id)) is None:
        raise DedupError("unknown_parcel")
    for candidate_id in candidate_ids:
        if (candidate := data.parcels.get(candidate_id)) is not None:
            keep_apart(data, target, candidate)


# --- Inferred deliveries ---------------------------------------------------------


def _may_hold(
    parcel: Parcel,
    delivery: Parcel,
    when: datetime,
    waiting: Iterable[Parcel],
    apart: Callable[[Parcel, Parcel], bool],
) -> bool:
    """Return True when a delivery may have held a parcel it doesn't name.

    Not when the delivery belongs to other orders or came with another
    carrier, or when another open parcel of the shop that was late, or due
    days later, could have been the package instead.
    """
    orders = parcel_order_keys(parcel)
    if (theirs := parcel_order_keys(delivery)) and orders and theirs.isdisjoint(orders):
        return False
    if not _same_carrier(parcel.state.carrier, delivery.state.carrier):
        return False
    day = local_date(when)
    for other in waiting:
        eta = other.state.eta
        first = first_news(other)
        if (
            other.id not in (parcel.id, delivery.id)
            and eta is not None
            and first is not None
            and first < when
            and not eta.start - INFER_MARGIN <= day <= eta.end + INFER_MARGIN
            and _could_arrive(eta, day, day)
            and _same_carrier(other.state.carrier, delivery.state.carrier)
            and not _parcels_conflict(other, delivery)
            and not apart(other, delivery)
        ):
            return False
    return True


def infer_deliveries(data: ParcelsData, now: datetime) -> set[str]:
    """Close parcels without a tracking number that were probably delivered.

    Shops pack several orders into one carrier parcel and only the carrier
    reports the delivery. A parcel without a carrier tracking number whose
    dates have passed, with no news since, counts as delivered when an
    e-mail or 17TRACK reported another parcel of the same merchant delivered
    within a day of its dates, unless that delivery may have been another
    package (see :func:`_may_hold`). It only starts the day after its last
    expected day. The parcels aren't
    merged, and the delivery is shown as inferred until the user keeps or
    undoes it. Returns the IDs of the changed parcels.
    """
    apart = _apart_checker(data)
    today = local_date(now)
    delivered: dict[str, list[tuple[datetime, Parcel]]] = defaultdict(list)
    waiting: dict[str, list[Parcel]] = defaultdict(list)
    for parcel in data.parcels.values():
        state = parcel.state
        if not (key := merchant_key(state.merchant)):
            continue
        if (when := _reported_delivery(parcel)) is not None:
            delivered[key].append((when, parcel))
        if (
            parcel.archived is None
            and not state.terminal
            and not state.tracking_number
            and state.eta is not None
        ):
            waiting[key].append(parcel)

    changed: set[str] = set()
    for parcel in data.parcels.values():
        state = parcel.state
        eta = state.eta
        key = merchant_key(state.merchant)
        if (
            parcel.archived is not None
            or state.terminal
            or state.tracking_number
            or parcel.delivery_rejected
            or eta is None
            or today <= eta.end
            or not key
            or any(event.inferred for event in parcel.events)
        ):
            continue
        last = _last_activity(parcel)
        first_day, last_day = eta.start - INFER_MARGIN, eta.end + INFER_MARGIN
        matches = sorted(
            when
            for when, other in delivered.get(key, ())
            if other.id != parcel.id
            and first_day <= local_date(when) <= last_day
            and (last is None or last <= when)
            and not apart(parcel, other)
            and _may_hold(parcel, other, when, waiting[key], apart)
        )
        if not matches:
            continue
        parcel.events.append(
            ParcelEvent(
                time=matches[0],
                source=Source.PARSER,
                status=ParcelStatus.DELIVERED,
                kind=MailKind.DELIVERED,
                inferred=True,
            )
        )
        parcel.touch(now)
        changed.add(parcel.id)
    return changed


def undo_inferred_delivery(data: ParcelsData, parcel_id: str, now: datetime) -> Parcel:
    """Take back an inferred delivery; it won't be inferred again."""
    parcel = data.parcels[parcel_id]
    if not any(event.inferred for event in parcel.events):
        raise DedupError("no_inferred_delivery")
    parcel.events = [event for event in parcel.events if not event.inferred]
    parcel.delivery_rejected = True
    parcel.touch(now)
    if parcel.archived is not None and not parcel.state.terminal:
        parcel.archived = None
    return parcel


# --- Repairing parcels stored by earlier versions ---------------------------------


RECOMMENDATIONS_MIN = 3


def _drop_recommendations(data: ParcelsData, now: datetime) -> set[str]:
    """Drop the shop's recommendations that earlier versions read as items.

    They're the titles at the end of an item list that also follow the
    first item in the lists of unrelated orders. At least three must end the
    list, and the first item always stays. Returns the changed parcel IDs.
    """
    listed = [
        (parcel, origin, frozenset(keys), [item_key(item) for item in origin.items])
        for parcel in data.parcels.values()
        for origin in parcel.origins.values()
        if origin.source in (Source.PARSER, Source.AI)
        and len(origin.items) > 1
        and (keys := origin_order_keys(origin))
    ]

    def elsewhere(key: str, orders: frozenset[str]) -> bool:
        return bool(key) and any(
            orders.isdisjoint(other_orders)
            and any(same_key(key, other) for other in other_keys[1:])
            for _, _, other_orders, other_keys in listed
        )

    tails: dict[str, int] = {}
    for _, origin, orders, keys in listed:
        size = 0
        while size < len(keys) - 1 and elsewhere(keys[-1 - size], orders):
            size += 1
        if size >= RECOMMENDATIONS_MIN:
            tails[origin.id] = size
    changed: set[str] = set()
    for parcel, origin, _, _ in listed:
        if size := tails.get(origin.id):
            origin.items = origin.items[:-size]
            parcel.touch(now)
            changed.add(parcel.id)
    return changed


def repair_store(data: ParcelsData, now: datetime) -> set[str]:
    """Fix what earlier versions stored; returns the changed parcel IDs.

    * Carrier brands in sender names become carriers, never merchants.
    * A shop's bare domain is replaced by its name from other e-mails.
    * Amazon e-mails without a tracking number no longer claim that Amazon
      delivers: the carrier is unknown until a carrier's e-mail names it.
    * A shop's recommendations read as items are dropped.
    * Parcels of one order that are the same package are merged, undoably.
    * Orders are recorded again under the current order keys.
    * A carrier learned for a shop that ships with many carriers is forgotten.
    * A carrier's delivery and the shop's only parcel that could be it are
      merged, undoably, however old they are.

    Every step can run again harmlessly.
    """
    for domain, prefs in data.senders.items():
        if prefs.carrier and ships_with_many(domain):
            prefs.carrier = None
    names = _merchant_names(_all_origins(data))
    changed: set[str] = set()
    for parcel in data.parcels.values():
        dirty = False
        for origin in parcel.origins.values():
            dirty |= _brand_carrier(origin)
            dirty |= _name_merchant(data, origin, names)
            if (
                origin.carrier == "amazon"
                and origin.source in (Source.PARSER, Source.AI)
                and not origin.tracking_number
                and (info := lookup(origin.label)) is not None
                and info.parser == "amazon"
            ):
                origin.carrier = None
                dirty = True
        if dirty:
            parcel.touch(now)
            changed.add(parcel.id)
    changed |= _drop_recommendations(data, now)
    merged = Reconciled()
    apart = _apart_checker(data)
    _merge_by_order(data, None, apart, now, merged)
    _pair_by_day(data, _reconcile_pool(data, _EPOCH), apart, now, merged)
    changed |= merged.changed
    changed -= merged.removed
    for parcel in data.parcels.values():
        _record_orders(data, parcel, now)
    return changed
