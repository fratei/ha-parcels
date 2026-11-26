"""Deduplication: every parcel appears once.

A parcel is assembled from *origins* (see models.py). A new origin joins every
parcel it shares a key with, and those parcels merge into one, which makes
this an incremental union-find where each parcel is one set. The keys are:

* the tracking number together with the carrier. Carriers that hand parcels
  over to each other under the same number count as one family;
* the tracking number alone for international postal (S10) numbers, because
  the carrier changes at the border;
* the Amazon shipment ID. Paack's order IDs for Amazon parcels are not
  Amazon's shipment IDs, so they don't join them;
* the origin ID. It holds the hash of the e-mail's Message-ID, so the same
  e-mail found in two mailboxes is applied once.

Weaker links are used only when no key matches, and they never merge two
existing parcels:

* the same tracking number when one side doesn't know the carrier;
* a shipment reference that isn't a tracking number: the part of Paack's
  order ID before "_", or a shop's own shipment number. An e-mail with only
  the reference joins the parcel that has it. When several do, it joins the
  one without a tracking number, or the only open one (flagged); otherwise
  it gets a parcel of its own. A shipment's e-mail with a tracking number
  absorbs the parcel of its reference unless another tracked parcel has it;
* an order: a shipment absorbs the parcel without a tracking number that an
  order e-mail of the same order created. When the order has several, the
  one with the shipment's items;
* heuristics, which flag the parcel "auto-merged" so the user can undo them:
  the same long tracking number from carriers of different families, the
  order's only open parcel with the same items (or, for a "delivered" e-mail
  without items, the order's only open parcel), the package that news of
  the same order (sub-order) sent out for delivery with the same carrier,
  for the local AI's "delivered" that lists other items, or the same
  merchant with overlapping delivery dates when only one parcel fits.

News without a number that closes a package (delivered or returned) but
lists other items than the order's only open package, which nothing else
takes, gets a parcel of its own and a merge suggestion with that package.

After a sync, :func:`reconcile` looks at whole parcels again, because e-mails
arrive in any order and a shop's e-mail rarely names the carrier's number:

* parcels of one order that are the same package join: the same items, or a
  "delivered" e-mail without items and the order's only other parcel;
* a shop's single parcel without a tracking number joins the tracked
  shipments that the same sender domain announces within a few days;
* a parcel known only by a shipment reference joins the only tracked parcel
  with that reference. With several, the user gets merge suggestions;
* an Amazon shipment that the Parcel app tracks joins the carrier's package
  whose own events have the same minutes as Amazon's tracking: delivered,
  and one more, such as arriving at the carrier. Only when exactly one
  package agrees, and flagged; several shipments may join one package. When
  more agree, the user gets merge suggestions;
* a parcel without a tracking number joins the tracked parcel of the same
  merchant delivered on its date, when they are the only two that fit. When
  more fit, the user gets merge suggestions instead. A package whose
  delivery time Amazon's tracking contradicts never fits.

Item titles never link different orders, and titles that unrelated orders
share (a shop's recommendations read as items) don't count at all, nor do
placeholders such as "item 1".

When the Parcel app switches an Amazon delivery to the carrier's number, its
sync joins the carrier's delivery to the order's parcel, flagged (see
:func:`join_switched` and :func:`flag_switch`).

A guess never puts a private parcel together with an e-mail or a parcel of
someone who isn't one of its owners, who would then see it. The flagged joins
above, the order's package picked by its items and the Parcel app's switch
hold such a pair back instead, and the people who may see both parcels get a
merge suggestion (see :func:`hold_guess`). Keys, and the links that leave no
choice, still join, and the other side's owners then share the parcel.

:func:`infer_deliveries` then closes parcels without a tracking number whose
date has passed when the same merchant delivered another parcel then. Shops
pack several orders in one carrier parcel, so these are marked as inferred,
not merged.

:func:`boxes_of_day` tells delivery day which of the day's orders without a
carrier's number a carrier's package of the day may hold, so it counts
packages rather than records. That is a guess, never a merge. Amazon's
tracking narrows it before the link: a shipment goes with the packages
repeating its times, and not with a delivered package that the Parcel app
showed while still showing the shipment on its way.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
import hashlib
from itertools import combinations
import re
from typing import Any

from homeassistant.util import dt as dt_util

from .ai.validate import NOTE_CARRIER_UNPROVEN, NOTE_ITEM_PLACEHOLDER
from .const import MailKind, ParcelStatus
from .models import (
    FILL_ORIGIN_SUFFIX,
    PARCELAPP_PREFIX,
    TYPED_ORDER_MARK,
    AutoMerge,
    Order,
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    ParcelShell,
    ParcelState,
    Source,
    carrier_like,
    check_codes,
    date_from_str,
    day_known,
    derive_state,
    dt_from_str,
    is_carrier_mail,
    is_carrier_name,
    local_date,
    merchant_key,
    new_id,
    order_key,
    time_from_str,
)
from .parsers.base import Eta, shipment_base
from .parsers.carriers import brand_carriers
from .parsers.carriers._common import fold_text, phrase_regex
from .parsers.carriers._phrases import KIND_PHRASES
from .parsers.items import is_placeholder_item, item_key, same_key
from .parsers.senders import (
    is_free_mail,
    lookup,
    organizational_domain,
    relays_carrier_mail,
    ships_with_many,
)
from .parsers.tracking import (
    PAACK_STEM_RE,
    amazon_logistics_number,
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
REASON_SAME_REFERENCE = "same_reference"
REASON_AMAZON_TRACKING = "amazon_tracking"
REASON_PARCEL_SWITCH = "parcel_switch"

# How far back reconcile() looks, and how soon after a shop's order e-mails
# its tracked shipments must follow to absorb the order's parcel.
RECONCILE_WINDOW = timedelta(days=30)
DOMAIN_ABSORB_WINDOW = timedelta(days=7)
# A delivery this many days around a parcel's dates counts for inference.
INFER_MARGIN = timedelta(days=1)
# How far back the diagnostics count Amazon's shipment IDs, and the kinds of
# Amazon e-mails that never link a shipment.
RECENT_AMAZON = timedelta(days=30)
_ORDER_STAGE = frozenset(
    {MailKind.ORDER, MailKind.CANCELLED, MailKind.RETURN, MailKind.CUSTOMER_RETURN}
)
# A shop's parcel up to this many days late, or due this many days later,
# could still be the package a carrier delivers: shops deliver early too.
LATE_DAYS = timedelta(days=14)
EARLY_DAYS = timedelta(days=7)
# Shorter parts of a seller's name ("SA", "PT") don't name a shop.
SELLER_KEY_MIN_LENGTH = 4
# An order delivered this long before or after a package wasn't in it.
BOX_DELIVERY_SLACK = timedelta(hours=3)
# Amazon's tracking of a shipment repeats the scans of the carrier's package
# that holds it, to the minute. One of the package's own events agrees with
# one of Amazon's this little before or after it: Amazon gives minutes, and
# a carrier's e-mail leaves some seconds after its scan.
AGREE_BEFORE = timedelta(minutes=1)
AGREE_AFTER = timedelta(minutes=2)
# A package delivered this long before or after Amazon's tracking says the
# shipment came, or marked delivered by hand this long before, didn't hold it.
CONTRADICTION_GAP = timedelta(hours=2)
# Amazon's tracking shows a carrier's scan within this long. A shipment still
# not delivered when the Parcel app had shown news this long after a package
# came wasn't in that package: see boxes_of_day().
AMAZON_CATCH_UP = timedelta(hours=1)
# What doesn't come to the door on a day, and the orders that need the user.
_NOT_COMING = frozenset(
    {ParcelStatus.READY_FOR_PICKUP, ParcelStatus.RETURNED, ParcelStatus.CANCELLED}
)
_PROBLEMS = frozenset({ParcelStatus.ATTEMPTED, ParcelStatus.EXCEPTION})

# Engine-state keys: pairs of origins the user keeps apart, the version of
# the one-time repair of stored parcels, what its fourth step changed, how
# Amazon shipments were linked to carriers' packages (counts only), how
# many parcels of orders' late e-mails were folded into their order's parcel
# once (see fold_known_orders()), and the guesses not made because a parcel
# was private (see hold_guess()).
KEPT_APART = "kept_apart"
HELD_GUESSES = "held_guesses"
REPAIR_KEY = "repair"
REPAIR_VERSION = 5
AMAZON_REPAIR_KEY = "amazon_carrier_repaired"
PLACEHOLDER_REPAIR_KEY = "placeholder_items_repaired"
AMAZON_LINKS_KEY = "amazon_links"
ORDER_FOLD_KEY = "order_fold"
# Where a carrier is read from the parcel's or someone else's say-so: the
# local AI, the Parcel app and 17TRACK. Amazon is their carrier only with
# one of its numbers.
_SAID_SOURCES = frozenset({Source.AI, Source.PARCELAPP, Source.SEVENTEENTRACK})
# Before any stored news: the one-time repair looks at every parcel.
_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
# The id of a carrier's package an e-mail would make on its own, weighed
# before it is applied: new_id() never makes it.
_INCOMING = "incoming"

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
    # A Parcel app delivery joins the parcel its sync chose, and no other.
    anchor: str | None = None
    # An e-mail read again goes back to its parcel: ``parcel`` joins that
    # parcel, as if it held the origin; ``home`` is where it goes when no
    # number, shipment, order or reference tells otherwise.
    parcel: str | None = None
    home: str | None = None


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
    data: ParcelsData, key: str, *, include_archived: bool = True, typed: bool = False
) -> list[Parcel]:
    """Return the parcels of an order.

    With ``typed``, also the ones whose number, typed by hand, may be the
    order's (see typed_order_key()).
    """
    return [
        parcel
        for parcel in data.parcels.values()
        if (include_archived or parcel.archived is None)
        and (
            key in parcel_order_keys(parcel)
            or (typed and typed_order_key(parcel) == key)
        )
    ]


def typed_order_key(parcel: Parcel) -> str | None:
    """Return the key of the order a number typed by hand may be, or None.

    See ParcelState.typed_number.
    """
    state = parcel.state
    if state.typed_number is None:
        return None
    return order_key(state.merchant, state.typed_number)


def shipment_parcels(data: ParcelsData, shipment: str) -> list[Parcel]:
    """Return the parcels of an Amazon shipment."""
    return [
        parcel
        for parcel in data.parcels.values()
        if shipment in parcel.state.amazon_shipment_ids
    ]


def box_parcels(data: ParcelsData, shipment: str) -> list[Parcel]:
    """Return the parcels of any box of an Amazon shipment (see shipment_key)."""
    return [
        parcel
        for parcel in data.parcels.values()
        if any(
            shipment_base(key) == shipment for key in parcel.state.amazon_shipment_ids
        )
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
    """Return the shipment a Paack e-mail names, as written.

    That's the part of its order ID before "_", or the reference it gives
    alone as the order number.
    """
    if carrier_family(origin.carrier) != "paack":
        return None
    if stem := paack_stem(origin.tracking_number):
        return stem
    reference = origin.reference
    return reference if reference and PAACK_STEM_RE.fullmatch(reference) else None


ReferenceKey = tuple[str, str]


def origin_reference_keys(
    origin: Origin, fallback_merchant: str | None = None
) -> set[ReferenceKey]:
    """Return the shipment references of an origin, each with its scope.

    Paack's references are Paack's; a shop's are the shop's, so an origin
    without a known merchant has none.
    """
    if stem := _paack_stem(origin):
        return {("paack", stem)}
    if not origin.reference:
        return set()
    scope = merchant_key(origin.merchant or fallback_merchant)
    return {(scope, origin.reference)} if scope else set()


def parcel_reference_keys(parcel: Parcel) -> set[ReferenceKey]:
    """Return the shipment references a parcel is known by."""
    state = parcel.state
    keys: set[ReferenceKey] = set()
    for origin in parcel.origins.values():
        keys |= origin_reference_keys(origin, state.merchant)
    if carrier_family(state.carrier) == "paack" and (
        stem := paack_stem(state.tracking_number)
    ):
        keys.add(("paack", stem))
    return keys


JoinKey = tuple[str, ...]


def join_keys(parcel: Parcel) -> set[JoinKey]:
    """Return the keys the deduplication can join a parcel to others by.

    Its tracking numbers, whatever the carrier, shipment references, orders
    and Amazon shipments, and the order a number typed by hand may be.
    """
    keys: set[JoinKey] = {("number", key.number) for key in parcel_numbers(parcel)}
    keys.update(("reference", *key) for key in parcel_reference_keys(parcel))
    keys.update(("order", key) for key in parcel_order_keys(parcel))
    if typed := typed_order_key(parcel):
        keys.add(("order", typed))
    keys.update(("shipment", value) for value in parcel.state.amazon_shipment_ids)
    return keys


def _references_differ(first: set[ReferenceKey], second: set[ReferenceKey]) -> bool:
    """Return True when both sides have references in a scope and none match."""
    for scope in {key[0] for key in first} & {key[0] for key in second}:
        mine = {ref for key_scope, ref in first if key_scope == scope}
        if mine.isdisjoint(ref for key_scope, ref in second if key_scope == scope):
            return True
    return False


def _same_shipment(first: Origin, second: Origin) -> bool:
    """Return True when two origins are about the same box of an Amazon shipment.

    They give the same shipment key (case counts: the IDs are case-sensitive;
    see shipment_key), and not two tracking numbers: when e-mails don't tell
    a shipment's boxes apart, their numbers do.
    """
    if not (
        first.amazon_shipment_id
        and first.amazon_shipment_id == second.amazon_shipment_id
    ):
        return False
    key_a, key_b = origin_number(first), origin_number(second)
    return key_a is None or key_b is None or key_a.number == key_b.number


def _numbers_linked(first: Origin, second: Origin) -> bool:
    """Return True when two origins give the same tracking number, for one carrier."""
    key_a, key_b = origin_number(first), origin_number(second)
    if not key_a or not key_b or key_a.number != key_b.number:
        return False
    return (
        is_s10(key_a.number)
        or key_a.family is None
        or key_b.family is None
        or key_a.family == key_b.family
    )


def _origins_linked(first: Origin, second: Origin) -> bool:
    """Return True when two origins certainly describe the same parcel."""
    return _numbers_linked(first, second) or _same_shipment(first, second)


def _origins_numbers(origins: Iterable[Origin]) -> set[str]:
    return {key.number for origin in origins if (key := origin_number(origin))}


def _shipment_shared(moving: list[Origin], staying: list[Origin]) -> bool:
    """Return True when an e-mail about an Amazon shipment would join two sides.

    They share a shipment key, and their tracking numbers don't tell them
    apart: one side has none, or both have the same.
    """
    keys = {origin.amazon_shipment_id for origin in moving}
    if not any(
        origin.amazon_shipment_id and origin.amazon_shipment_id in keys
        for origin in staying
    ):
        return False
    mine, theirs = _origins_numbers(moving), _origins_numbers(staying)
    return not mine or not theirs or bool(mine & theirs)


def _shipment_targets(data: ParcelsData, origin: Origin, strong: set[str]) -> set[str]:
    """Return the parcels an origin joins by its Amazon shipment.

    Those with an origin about the same box (see _same_shipment). When the
    origin, or a parcel it joins anyway, gives a number, only the parcels
    with that number or none; otherwise all of them while they have at most
    one number between them, else only those without one: news about a
    shipment never makes two boxes one.
    """
    found = {
        pid: {key.number for key in parcel_numbers(parcel)}
        for pid, parcel in data.parcels.items()
        if any(_same_shipment(origin, other) for other in parcel.origins.values())
    }
    known = {
        key.number
        for pid in strong
        if pid in data.parcels
        for key in parcel_numbers(data.parcels[pid])
    }
    if own := origin_number(origin):
        known.add(own.number)
    if known:
        return {pid for pid, numbers in found.items() if not numbers or numbers & known}
    if len(set().union(*found.values())) <= 1:
        return set(found)
    return {pid for pid, numbers in found.items() if not numbers}


def _id_shape(value: str) -> str:
    """Describe an ID by its length and character classes, e.g. "len9:Aa0"."""
    classes = (
        ("A", str.isupper),
        ("a", str.islower),
        ("0", str.isdigit),
        ("-", lambda char: not char.isalnum()),
    )
    marks = "".join(mark for mark, test in classes if any(test(char) for char in value))
    return f"len{len(value)}:{marks}"


def amazon_shipment_id_counts(
    data: ParcelsData, now: datetime
) -> dict[str, dict[str, Any]]:
    """Count Amazon's e-mails of the last 30 days by whether they gave a shipment ID.

    Per Amazon site, each shipment of an e-mail counts once: "orders" for
    orders, cancellations and returns, which never link a shipment, else
    "with_id" or "without_id". "shapes" counts the IDs by length and
    character classes. The counts hold no ID.
    """
    since = now - RECENT_AMAZON
    kinds: defaultdict[str, set[MailKind]] = defaultdict(set)
    for parcel in data.parcels.values():
        for event in parcel.events:
            if event.origin and event.kind:
                kinds[event.origin].add(event.kind)
    counts: dict[str, dict[str, Any]] = {}
    for origin in _all_origins(data):
        info = lookup(origin.label)
        if info is None or info.parser != "amazon" or origin.time < since:
            continue
        site = counts.setdefault(
            organizational_domain(origin.label),
            {"orders": 0, "with_id": 0, "without_id": 0, "shapes": {}},
        )
        if shipment := origin.amazon_shipment_id:
            site["with_id"] += 1
            shape = _id_shape(shipment_base(shipment))
            site["shapes"][shape] = site["shapes"].get(shape, 0) + 1
        elif kinds[origin.id] and kinds[origin.id] <= _ORDER_STAGE:
            site["orders"] += 1
        else:
            site["without_id"] += 1
    return dict(sorted(counts.items()))


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


def _typed_order_only(parcel: Parcel, key: str) -> bool:
    """Return True for an open parcel known only by a number typed as order ``key``.

    No e-mail has said yet whether the number is the order's.
    """
    state = parcel.state
    return (
        parcel.archived is None
        and not state.terminal
        and not state.typed_order
        and not state.amazon_shipment_ids
        and typed_order_key(parcel) == key
    )


def _finished(parcel: Parcel) -> bool:
    """Return True for a parcel that news or the user closed, not a guess."""
    state = parcel.state
    return state.terminal and not state.inferred


_SHIPPED_STATUSES = frozenset(
    {
        ParcelStatus.SHIPPED,
        ParcelStatus.IN_TRANSIT,
        ParcelStatus.EXCEPTION,
        ParcelStatus.ATTEMPTED,
        ParcelStatus.OUT_FOR_DELIVERY,
        ParcelStatus.READY_FOR_PICKUP,
        ParcelStatus.DELIVERED,
        ParcelStatus.RETURNED,
    }
)


def _first_message(parcel: Parcel) -> str | None:
    """Return the hash of the earliest e-mail about a parcel."""
    mails = [origin for origin in parcel.origins.values() if origin.message]
    if not mails:
        return None
    return min(mails, key=lambda origin: (origin.time, origin.id)).message


def _shipping_news(parcel: Parcel) -> bool:
    """Return True when news besides the order e-mail says the parcel shipped.

    That's a tracking number or an Amazon shipment, or a shipped-or-later
    status from an e-mail or a tracker. A delay notice isn't such news, nor
    is the local AI's reading of the parcel's first e-mail when it names no
    carrier: that's the order's e-mail, which the AI may take for a shipment.
    """
    if _tracked(parcel):
        return True
    first = _first_message(parcel)
    for event in parcel.events:
        if event.status not in _SHIPPED_STATUSES or event.kind is MailKind.DELAYED:
            continue
        origin = parcel.origins.get(event.origin or "")
        if (
            origin is None
            or origin.source is not Source.AI
            or origin.carrier
            or origin.message != first
        ):
            return True
    return False


def _takes_cancellation(parcel: Parcel) -> bool:
    """Return True for a parcel that its order's cancellation can cancel.

    That's one that hasn't shipped, as far as news besides the order e-mail
    tells.
    """
    state = parcel.state
    return state.status is ParcelStatus.ORDERED or (
        not state.terminal and not _shipping_news(parcel)
    )


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
) -> tuple[set[str], set[str]]:
    """Return, per order of a shipment, the parcel without a number it absorbs.

    That's the order's only such parcel, unless it lists other items. Of
    several, it's the only one with the shipment's items: a guess, returned
    apart from the sure ones, which the user can undo. A parcel whose only
    number was typed as the order's counts as one without a number.
    """
    sure: set[str] = set()
    guessed: set[str] = set()
    items = _item_keys(origin.items)
    noise: frozenset[str] = frozenset()
    if items:
        noise = _noise_items(data.parcels.values())
    for key in origin_order_keys(origin):
        candidates = [
            parcel
            for parcel in order_parcels(data, key, include_archived=False, typed=True)
            if _untracked(parcel) or _typed_order_only(parcel, key)
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
        (guessed if several else sure).add(candidates[0].id)
    return sure, guessed


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


def _typed_key(origin: Origin) -> str | None:
    """Return the key of the order a number typed by hand may be, or None.

    A number typed with a carrier ("Other" is none), or in a carrier's
    format, is a tracking number.
    """
    number = origin.tracking_number
    if (
        origin.source is not Source.MANUAL
        or not number
        or origin.carrier not in (None, "other")
        or detect_carrier(number)
    ):
        return None
    return order_key(origin.merchant, number)


def _typed_candidates(
    data: ParcelsData, key: str, typed: Parcel | None = None
) -> list[Parcel]:
    """Return the order's open parcels a number typed as its order may be.

    With or without a tracking number of their own; not one that ``typed``,
    the parcel with the number, can't be.
    """
    return [
        parcel
        for parcel in order_parcels(data, key, include_archived=False)
        if parcel is not typed
        and not parcel.state.terminal
        and (typed is None or not _parcels_conflict(typed, parcel, typed=True))
    ]


def _typed_for(parcel: Parcel, other: Parcel) -> bool:
    """Return True when a parcel is known only by a number typed as ``other``'s order.

    Its tracking number is then only that order's number, so it doesn't
    tell the two apart.
    """
    state = parcel.state
    if (
        state.typed_order
        or state.amazon_shipment_ids
        or (key := typed_order_key(parcel)) is None
        or key not in parcel_order_keys(other)
    ):
        return False
    typed = number_key_text(state.typed_number or "")
    return all(
        origin.source is Source.MANUAL
        or not origin.tracking_number
        or number_key_text(origin.tracking_number) == typed
        for origin in parcel.origins.values()
    )


def _order_only_target(
    data: ParcelsData,
    origin: Origin,
    events: list[ParcelEvent],
    *,
    include_archived: bool = False,
) -> str | None:
    """Pick the parcel that order-level news without a number belongs to.

    It's one of the order's parcels, archived ones only with
    ``include_archived``: see _order_pick(). A parcel whose number was typed
    as the order's is one of them.
    """
    parcels: dict[str, Parcel] = {}
    for key in origin_order_keys(origin):
        for parcel in order_parcels(
            data, key, include_archived=include_archived, typed=True
        ):
            if not _conflicts(parcel, origin):
                parcels[parcel.id] = parcel
    if not parcels:
        return None
    cancelled = any(event.status is ParcelStatus.CANCELLED for event in events)
    if cancelled:
        ordered = [
            p.id for p in parcels.values() if p.state.status is ParcelStatus.ORDERED
        ]
        unshipped = [p.id for p in parcels.values() if _takes_cancellation(p)]
        if ordered or unshipped:
            return _most_recent(data, ordered or unshipped)
        # A cancellation only applies to parcels that haven't shipped yet;
        # once shipped it's at most a partial cancellation.
        for event in events:
            if event.status is ParcelStatus.CANCELLED:
                event.status = None
    return _order_pick(data, parcels, _item_keys(origin.items))


def _order_pick(
    data: ParcelsData, parcels: Mapping[str, Parcel], items: set[str]
) -> str | None:
    """Pick, of an order's parcels, the one that news about ``items`` is about.

    That's the only parcel with the items, otherwise the latest open parcel
    without a number, or else the latest parcel. A parcel with other items
    is another package, so with only those, there's none.
    """
    if items:
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


def _order_package(
    data: ParcelsData, origin: Origin, events: list[ParcelEvent]
) -> tuple[str | None, str | None]:
    """Return the order's open package that news with other items may be about.

    It's for news without a number when no parcel of its order has its
    items (see :func:`_order_pick`). The local AI may misread items, so its
    "delivered" belongs to the package that the news of the same order
    (sub-order) said was out for delivery, with the same carrier: the first
    value, a guess to flag. Otherwise, news that closes a package
    (delivered or returned) may still be about the order's only open
    package: the second value, which the user decides on.
    """
    keys = origin_order_keys(origin)
    candidates: dict[str, Parcel] = {}
    for key in keys:
        for parcel in order_parcels(data, key, include_archived=False):
            if not _finished(parcel) and not _conflicts(parcel, origin):
                candidates[parcel.id] = parcel
    statuses = {event.status for event in events}
    if origin.source is Source.AI and ParcelStatus.DELIVERED in statuses:
        out = [
            pid
            for pid, parcel in candidates.items()
            if parcel.state.status is ParcelStatus.OUT_FOR_DELIVERY
            and _same_carrier(origin.carrier, parcel.state.carrier)
            and _out_for(parcel, keys)
        ]
        if len(out) == 1:
            return out[0], None
    closing = bool(statuses & {ParcelStatus.DELIVERED, ParcelStatus.RETURNED})
    if closing and len(candidates) == 1:
        return None, next(iter(candidates))
    return None, None


def _out_for(parcel: Parcel, keys: Collection[str]) -> bool:
    """Return whether news that named one of the orders ``keys`` sent it out."""
    for event in parcel.events:
        if event.status is not ParcelStatus.OUT_FOR_DELIVERY:
            continue
        origin = parcel.origins.get(event.origin) if event.origin else None
        if origin is not None and not origin_order_keys(
            origin, parcel.state.merchant
        ).isdisjoint(keys):
            return True
    return False


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
    if origin_orders and parcel_orders and not origin_orders & parcel_orders:
        return True
    references = origin_reference_keys(origin)
    return bool(references) and _references_differ(
        references, parcel_reference_keys(parcel)
    )


def _reference_holders(data: ParcelsData, origin: Origin) -> list[Parcel]:
    """Return the parcels known by a shipment reference of an origin."""
    if not (keys := origin_reference_keys(origin)):
        return []
    return [
        parcel
        for parcel in data.parcels.values()
        if not keys.isdisjoint(parcel_reference_keys(parcel))
    ]


def _tracked(parcel: Parcel) -> bool:
    state = parcel.state
    return bool(state.tracking_number or state.amazon_shipment_ids)


def _reference_absorbable(
    data: ParcelsData, origin: Origin, exclude: set[str]
) -> set[str]:
    """Return the parcel without a number that a shipment's reference names.

    An e-mail with only the reference created it. When another tracked
    parcel has the reference too, it's unclear which one that e-mail was
    about, and the user decides (see :func:`reconcile`).
    """
    found: list[Parcel] = []
    for parcel in _reference_holders(data, origin):
        if parcel.id in exclude:
            continue
        if _tracked(parcel):
            return set()
        if parcel.archived is None and not _conflicts(parcel, origin):
            found.append(parcel)
    return {found[0].id} if len(found) == 1 else set()


def _reference_target(
    data: ParcelsData, origin: Origin
) -> tuple[str | None, str | None, bool]:
    """Return the parcel that news with a shipment reference and no number is about.

    That's the only parcel with the reference. Of several, the only one
    without a tracking number (the e-mails with only the reference stay
    together), else the only open one, flagged so the user can undo it.
    Returns the parcel, the reason when it's a guess, and whether several
    parcels fit so that no other guess may pick one.
    """
    holders = [
        parcel
        for parcel in _reference_holders(data, origin)
        if not _conflicts(parcel, origin)
    ]
    if not holders:
        return None, None, False
    if len(holders) == 1:
        return holders[0].id, None, False
    if (
        len(untracked := [p for p in holders if p.archived is None and not _tracked(p)])
        == 1
    ):
        return untracked[0].id, None, False
    if (
        len(
            waiting := [
                p for p in holders if p.archived is None and not p.state.terminal
            ]
        )
        == 1
    ):
        return waiting[0].id, REASON_SAME_REFERENCE, False
    return None, None, True


def _heuristic_target(data: ParcelsData, contribution: Contribution) -> str | None:
    """Return the only open parcel of the same merchant the e-mail can be about.

    Its dates must overlap the e-mail's, and no other parcel of the merchant
    may be late, or due soon enough, to be the one instead. A parcel with
    other items, or another carrier, than the e-mail's isn't a candidate.
    Nor is an Amazon shipment the Parcel app follows for a carrier's e-mail
    about a package its tracking doesn't point to, when it points to some:
    see :func:`_points_away`.
    """
    origin = contribution.origin
    eta = _contribution_eta(contribution.events)
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
    if not (only.state.eta and _overlap(only.state.eta, eta)):
        return None
    return None if _points_away(data, only, contribution) else only.id


def _points_away(
    data: ParcelsData, shipment: Parcel, contribution: Contribution
) -> bool:
    """Return whether a shipment's tracking points away from an e-mail's package.

    The e-mail is weighed as the carrier's package it would make on its
    own. Amazon's tracking of the shipment, which the Parcel app follows,
    points to some packages, see :func:`_pointed`, and not to that one.
    """
    if not _is_shipment(shipment):
        return False
    origin = contribution.origin
    package = Parcel(
        id=_INCOMING,
        created=origin.time,
        updated=origin.time,
        origins={origin.id: origin},
        events=list(contribution.events),
        private=contribution.private,
    )
    if not _is_box(package):
        return False
    found = _pointed(shipment, [*_boxes(data), package], _apart_checker(data))
    return bool(found) and package.id not in found


def _normalise(origin: Origin) -> None:
    if origin.tracking_number:
        origin.tracking_number = normalize_tracking_number(origin.tracking_number)
    if origin.amazon_shipment_id:
        origin.amazon_shipment_id = origin.amazon_shipment_id.strip()
    if origin.reference:
        origin.reference = origin.reference.strip() or None
    if origin.source is not Source.MANUAL and origin.items:
        # "Item 1" names no item: it would make the parcel seem another one.
        origin.items = tuple(i for i in origin.items if not is_placeholder_item(i))


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
    data: ParcelsData,
    contribution: Contribution,
    now: datetime,
    *,
    keep_closed: bool = False,
) -> Applied:
    """Add an origin and its events to the parcel it belongs to.

    Applying the same contribution again replaces the earlier one, so
    reprocessing an e-mail or a repeated 17TRACK sync is harmless. An
    order's e-mail, or one read again with ``keep_closed``, isn't news about
    the parcel: an archived or finished parcel stays as it is, with the
    delivery Parcels inferred.
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
    if contribution.parcel in data.parcels:
        strong.add(contribution.parcel)
    if contribution.anchor is not None and not strong:
        strong = {
            pid
            for pid, parcel in data.parcels.items()
            if contribution.anchor in parcel.origins
        }
        if not strong:
            return Applied(parcel_id=None)
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
    if origin.amazon_shipment_id:
        strong |= _shipment_targets(data, origin, strong)

    targets = set(strong)
    reason: str | None = None
    ambiguous = False
    # The order's open package that news with other items may be about: the
    # user decides when nothing else takes it (see _order_package()).
    order_guess: str | None = None
    # Guesses not made because they would put a private parcel together with
    # someone else's: the user gets a suggestion instead (see hold_guess()).
    held: list[tuple[str, str]] = []
    refused: set[str] = set()

    def allowed(pid: str, why: str) -> bool:
        if _may_join(data, contribution, targets, pid):
            return True
        held.append((pid, why))
        refused.add(pid)
        return False

    if not targets and weak:
        targets = {_most_recent(data, weak)}
    if (
        not targets
        and loose
        and number is not None
        and len(number.number) >= LOOSE_MIN_LENGTH
    ):
        if allowed(pick := _most_recent(data, loose), REASON_SAME_NUMBER):
            targets = {pick}
            reason = REASON_SAME_NUMBER
        else:
            ambiguous = True
    placed = contribution.anchor is not None and origin.source is Source.PARCELAPP
    if (number or origin.amazon_shipment_id) and not placed:
        absorbed, guessed = _absorbable(data, origin, targets)
        targets |= absorbed
        absorb_reason: str | None = None
        for pid in sorted(guessed - absorbed):
            if allowed(pid, REASON_SAME_ORDER):
                targets.add(pid)
                absorb_reason = REASON_SAME_ORDER
            else:
                ambiguous = True
        if guessed & absorbed:
            absorb_reason = REASON_SAME_ORDER
        targets |= _reference_absorbable(data, origin, targets | refused)
        if (
            not targets
            and not ambiguous
            and (same := _same_order_target(data, origin, events))
        ):
            if allowed(same, REASON_SAME_ORDER):
                targets = {same}
                absorb_reason = REASON_SAME_ORDER
            else:
                ambiguous = True
        if not targets and not ambiguous and (key := _typed_key(origin)):
            # A number typed as the order's: the order's only open parcel.
            # With several, the user says which (see _join_typed()).
            candidates = _typed_candidates(data, key)
            if len(candidates) == 1 and allowed(candidates[0].id, REASON_SAME_ORDER):
                targets = {candidates[0].id}
            elif candidates:
                ambiguous = True
        reason = reason or absorb_reason
    elif not targets:
        target, reason, ambiguous = _reference_target(data, origin)
        if target is not None and reason is not None and not allowed(target, reason):
            target, reason, ambiguous = None, None, True
        if target is None and not ambiguous:
            target = _order_only_target(data, origin, events)
            if target is None and contribution.order_placed is not None:
                # An order's e-mail about a parcel already put away joins it:
                # the order is known, so it isn't a new parcel.
                target = _order_only_target(data, origin, events, include_archived=True)
            if target is None:
                target, order_guess = _order_package(data, origin, events)
                if target is not None:
                    if allowed(target, REASON_SAME_ORDER):
                        reason = REASON_SAME_ORDER
                    else:
                        target, ambiguous = None, True
        if target is not None:
            targets = {target}
    if not targets and contribution.home in data.parcels:
        targets = {contribution.home}
    if (
        not targets
        and not ambiguous
        and not contribution.attach_only
        and (heuristic := _heuristic_target(data, contribution))
        and allowed(heuristic, REASON_SAME_MERCHANT_ETA)
    ):
        targets = {heuristic}
        reason = REASON_SAME_MERCHANT_ETA
    if not targets and order_guess is not None:
        held.append((order_guess, REASON_SAME_ORDER))

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

    expected = parcel.state.eta
    keep = (keep_closed or contribution.order_placed is not None) and (
        parcel.archived is not None or parcel.state.terminal
    )
    if (existing := parcel.origins.get(origin.id)) is not None:
        origin.owners = tuple(sorted(set(existing.owners) | set(origin.owners)))
        origin.confirmed = origin.confirmed or existing.confirmed
    parcel.origins[origin.id] = origin
    # News about the parcel replaces a delivery Parcels only inferred.
    parcel.events = [
        e for e in parcel.events if e.origin != origin.id and (keep or not e.inferred)
    ]
    if origin.message is not None:
        _place_undated(parcel, events, expected)
    parcel.events.extend(events)
    parcel.private = parcel.private or contribution.private
    if reason:
        parcel.auto_merged = (
            AutoMerge(origin=origin.id, at=now, reason=reason)
            if parcel.auto_merged is None
            else _grown(parcel.auto_merged, parcel, {origin.id})
        )
    parcel.touch(now)
    if parcel.archived is not None and not keep and not parcel.state.terminal:
        # News about an archived parcel that isn't finished brings it back.
        parcel.archived = None
    _record_orders(data, parcel, now, origin.id, contribution.order_placed)
    for pid, why in held:
        if pid != parcel.id and (other := data.parcels.get(pid)) is not None:
            hold_guess(data, other.origins, (origin.id,), why)
    return Applied(
        parcel_id=parcel.id, created=created, merged=merged, auto_merged=reason
    )


def _may_share(
    private: bool,
    owners: Collection[str],
    other_private: bool,
    other_owners: Collection[str],
) -> bool:
    """Return True when a guess may put two sides in one parcel.

    A private side takes nothing of someone who isn't one of its owners:
    their e-mails and parcels would show it to them. What has no owner,
    such as a parcel added by hand, belongs to nobody else.
    """
    mine, theirs = set(owners), set(other_owners)
    if private and theirs - mine:
        return False
    return not (other_private and mine - theirs)


def _may_share_parcels(first: Parcel, second: Parcel) -> bool:
    """Return True when a guess may merge two parcels (see :func:`_may_share`)."""
    return _may_share(
        first.private, first.state.owners, second.private, second.state.owners
    )


def may_guess_into(parcel: Parcel, owners: Collection[str]) -> bool:
    """Return True when a guess may add a public delivery of owners to a parcel.

    See :func:`_may_share`: a private parcel takes nobody else's.
    """
    return _may_share(False, owners, parcel.private, parcel.state.owners)


def _may_join(
    data: ParcelsData, contribution: Contribution, targets: Collection[str], pid: str
) -> bool:
    """Return True when a guess may add an e-mail to a parcel.

    The e-mail brings the parcels it surely belongs to, ``targets``, along.
    """
    private = contribution.private
    owners = set(contribution.origin.owners)
    for other_id in targets:
        if other_id != pid and (other := data.parcels.get(other_id)) is not None:
            private = private or other.private
            owners.update(other.state.owners)
    parcel = data.parcels[pid]
    return _may_share(private, owners, parcel.private, parcel.state.owners)


def _place_undated(
    parcel: Parcel, events: Iterable[ParcelEvent], expected: Eta | None
) -> None:
    """Date an e-mail's news that doesn't say when it happened.

    A survey after a delivery says it was delivered, not when. The news goes
    just after the parcel's latest dated news, or the start of its expected
    days, from no later than the e-mail: never later than it happened. With
    neither, its day isn't known either.
    """
    pending = [
        event
        for event in events
        if event.undated
        and not event.dayless
        and event.by is not None
        and event.time == event.by
    ]
    if not pending:
        return
    known = [
        event.time
        for event in parcel.events
        if event.status is not None and not event.inferred and not event.undated
    ]
    if expected is not None:
        known.extend(
            dt_util.as_utc(dt_util.start_of_local_day(day))
            for day in (expected.start, expected.end)
        )
    for event in pending:
        if before := [value for value in known if value <= event.time]:
            event.time = max(before) + timedelta(microseconds=1)
        else:
            event.dayless = True


def merge_parcels(
    data: ParcelsData,
    target_id: str,
    other_ids: Iterable[str],
    now: datetime,
    *,
    keep_archived: bool = False,
    keep_inferred: bool = False,
) -> Parcel:
    """Merge parcels into ``target_id``; the others are deleted.

    The result is archived only when every parcel was, unless
    ``keep_archived`` keeps the target's own state. Inferred deliveries are
    dropped: they were guesses about one of the parcels. With
    ``keep_inferred``, only the others' are.
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
        target.events.extend(
            e
            for e in other.events
            if e.id not in known and not (keep_inferred and e.inferred)
        )
        target.private = target.private or other.private
        target.delivery_rejected = target.delivery_rejected or other.delivery_rejected
        target.created = min(target.created, other.created)
        if target.auto_merged is None:
            target.auto_merged = other.auto_merged
        del data.parcels[other.id]
    if others and not keep_inferred:
        target.events = [event for event in target.events if not event.inferred]
    target.touch(now)
    _record_orders(data, target, now)
    return target


def split_problem(parcel: Parcel, moving: Collection[str]) -> str | None:
    """Return why origins can't move out of a parcel, or None when they can.

    Nothing to move, an origin that isn't the parcel's (or is the user's
    edits), nothing left behind, or the two sides share a tracking number
    or an Amazon shipment their numbers don't tell apart (the next e-mail
    would merge them again).
    """
    edit_id = manual_origin_id(parcel.id)
    if not moving:
        return "no_origins"
    if not set(moving) <= parcel.origins.keys() or edit_id in moving:
        return "unknown_origin"
    staying = [o for oid, o in parcel.origins.items() if oid not in moving]
    if not [o for o in staying if o.id != edit_id]:
        return "nothing_left"
    leaving = [parcel.origins[oid] for oid in moving]
    if any(_numbers_linked(origin, other) for origin in leaving for other in staying):
        return "shared_number"
    if _shipment_shared(leaving, staying):
        return "shared_shipment"
    return None


def split_parcel(
    data: ParcelsData, parcel_id: str, origin_ids: Iterable[str], now: datetime
) -> Parcel:
    """Move origins and their events out of a parcel into a new one.

    The user's edits stay with the original parcel, and the two parcels are
    kept apart, so reconciling doesn't merge them again. Raises DedupError
    when the split is impossible (see :func:`split_problem`).
    """
    parcel = data.parcels[parcel_id]
    moving = set(origin_ids)
    if (problem := split_problem(parcel, moving)) is not None:
        raise DedupError(problem)
    new = _split(data, parcel, moving, now)
    keep_apart(data, parcel, new)
    return new


def _split(
    data: ParcelsData, parcel: Parcel, moving: Collection[str], now: datetime
) -> Parcel:
    """Move origins and their events out of a parcel into a new one."""
    new = Parcel(id=new_id("p"), created=now, updated=now, private=parcel.private)
    for oid in sorted(moving):
        new.origins[oid] = parcel.origins.pop(oid)
    new.events = [event for event in parcel.events if event.origin in moving]
    parcel.events = [event for event in parcel.events if event.origin not in moving]
    if parcel.auto_merged and parcel.auto_merged.all_origins & set(moving):
        parcel.auto_merged = None
    data.parcels[new.id] = new
    parcel.touch(now)
    new.touch(now)
    _record_orders(data, parcel, now)
    _record_orders(data, new, now)
    return new


def undo_auto_merge(data: ParcelsData, parcel_id: str, now: datetime) -> Parcel | None:
    """Undo a heuristic merge, returning the parcel that was split off.

    The origins that were linked by the heuristic leave together with every
    origin that shares their tracking number or shipment. When the flag has
    groups, such as Amazon shipments linked one by one to the package that
    carried them, each group leaves as its own parcel, and the first is
    returned. When nothing would be left behind, only the flag is cleared
    and None is returned. The parcels are then kept apart, so they aren't
    merged again.
    """
    parcel = data.parcels[parcel_id]
    flag = parcel.auto_merged
    parcel.auto_merged = None
    parcel.touch(now)
    if flag is None:
        return None
    first: Parcel | None = None
    for part in _undo_parts(flag, parcel):
        try:
            new = split_parcel(data, parcel_id, part, now)
        except DedupError:
            continue
        first = first or new
    return first


def _undo_parts(flag: AutoMerge, parcel: Parcel) -> list[set[str]]:
    """Return the origins that leave a parcel on undo, one set per parcel.

    Each group of the flag is one, and its other origins one more. Each
    takes the origins that share its tracking number or shipment, unless
    another took them first.
    """
    present = flag.all_origins & parcel.origins.keys()
    grouped = {oid for group in flag.groups for oid in group}
    parts = [set(group) & present for group in flag.groups]
    parts.append(present - grouped)
    parts = [part for part in parts if part]
    taken = set().union(*parts)
    for part in parts:
        pending = [parcel.origins[oid] for oid in part]
        while pending:
            current = pending.pop()
            for oid, other in parcel.origins.items():
                if oid not in taken and _origins_linked(current, other):
                    part.add(oid)
                    taken.add(oid)
                    pending.append(other)
    return parts


def _undo_guesses(data: ParcelsData, parcel: Parcel, now: datetime) -> list[Parcel]:
    """Take a parcel's guesses back, offering them as suggestions instead.

    Like :func:`undo_auto_merge`, but the parts aren't kept apart: each is
    held as a guess (see :func:`hold_guess`), so the user can still merge it.
    Returns the parcels split off.
    """
    flag = parcel.auto_merged
    parcel.auto_merged = None
    parcel.touch(now)
    if flag is None:
        return []
    split: list[Parcel] = []
    for part in _undo_parts(flag, parcel):
        if split_problem(parcel, part) is not None:
            continue
        new = _split(data, parcel, part, now)
        hold_guess(data, parcel.origins, new.origins, flag.reason)
        split.append(new)
    return split


def remove_message(data: ParcelsData, message_hash: str, now: datetime) -> set[str]:
    """Remove what an e-mail contributed, e.g. before reprocessing it.

    Returns the IDs of the parcels that changed; parcels and returns left
    without e-mails are deleted.
    """
    remove_return_origins(data, message_hash, now)
    return remove_parcel_origins(data, message_hash, now)


def _message_origins(parcel: Parcel, message_hash: str) -> set[str]:
    """Return the IDs of the origins that an e-mail added to a parcel."""
    prefix = f"msg:{message_hash}#"
    return {
        oid
        for oid, origin in parcel.origins.items()
        if origin.message == message_hash or oid.startswith(prefix)
    }


def message_outputs(data: ParcelsData, message_hash: str) -> bool:
    """Return True when an e-mail is part of a parcel or a return."""
    return any(
        _message_origins(parcel, message_hash) for parcel in data.parcels.values()
    ) or any(message_hash in entry.origins for entry in data.returns.values())


def message_shells(data: ParcelsData, message_hash: str) -> tuple[ParcelShell, ...]:
    """Return what the parcels of an e-mail are, before it's read again.

    One shell per parcel holding the e-mail's origins: see ParcelShell.
    """
    shells: list[ParcelShell] = []
    for parcel in data.parcels.values():
        if not (own := _message_origins(parcel, message_hash)):
            continue
        rest = [origin for oid, origin in parcel.origins.items() if oid not in own]
        lost = all(origin.source is Source.MANUAL for origin in rest)
        flag = parcel.auto_merged
        shells.append(
            ParcelShell(
                id=parcel.id,
                created=parcel.created,
                origins=tuple(sorted(own)),
                status=parcel.state.news_status,
                private=parcel.private,
                archived=parcel.archived,
                delivery_rejected=parcel.delivery_rejected,
                auto_merged=replace(flag) if flag is not None else None,
                lost=lost,
                kept_origins=tuple(
                    Origin.from_dict(origin.as_dict()) for origin in rest
                )
                if lost
                else (),
                kept_events=tuple(
                    ParcelEvent.from_dict(event.as_dict())
                    for event in parcel.events
                    if event.origin not in own
                )
                if lost
                else (),
            )
        )
    return tuple(shells)


def revive_shell(
    data: ParcelsData, shell: ParcelShell, now: datetime
) -> tuple[str, bool]:
    """Return the parcel a lost shell stands for, bringing it back when gone.

    It comes back with its ID, the user's edits and what Parcels inferred,
    but none of the e-mail's news: reading the e-mail again adds that.
    Returns its ID and whether it came back.
    """
    if shell.id in data.parcels:
        return shell.id, False
    manual = manual_origin_id(shell.id)
    for parcel in data.parcels.values():
        if manual in parcel.origins:
            # Merged meanwhile, with the user's edits.
            return parcel.id, False
    parcel = Parcel(
        id=shell.id,
        created=shell.created,
        updated=now,
        origins={
            origin.id: Origin.from_dict(origin.as_dict())
            for origin in shell.kept_origins
        },
        events=[ParcelEvent.from_dict(event.as_dict()) for event in shell.kept_events],
        private=shell.private,
        archived=shell.archived,
        delivery_rejected=shell.delivery_rejected,
    )
    data.parcels[parcel.id] = parcel
    return parcel.id, True


def restore_flag(parcel: Parcel, flag: AutoMerge | None) -> None:
    """Put back the merge to check that an e-mail read again took away.

    Only when the parcel holds the merged origin again, and only with the
    origins it still holds.
    """
    if flag is None or parcel.auto_merged is not None:
        return
    if flag.origin not in parcel.origins:
        return
    held = set(parcel.origins)
    parcel.auto_merged = replace(
        flag,
        origins=tuple(oid for oid in flag.origins if oid in held),
        groups=tuple(
            kept
            for group in flag.groups
            if (kept := tuple(oid for oid in group if oid in held))
        ),
    )


def remove_return_origins(data: ParcelsData, message_hash: str, now: datetime) -> bool:
    """Remove what an e-mail said about customer returns.

    Returns True when a return changed; returns left without e-mails are
    deleted.
    """
    changed = False
    for entry_id, entry in list(data.returns.items()):
        if entry.origins.pop(message_hash, None) is None:
            continue
        changed = True
        if entry.origins:
            entry.updated = now
        else:
            del data.returns[entry_id]
    return changed


def remove_parcel_origins(
    data: ParcelsData, message_hash: str, now: datetime
) -> set[str]:
    """Remove what an e-mail contributed to parcels.

    Returns the IDs of the parcels that changed; parcels left without origins
    are deleted.
    """
    affected: set[str] = set()
    for parcel in list(data.parcels.values()):
        if removed := _message_origins(parcel, message_hash):
            affected.add(parcel.id)
            remove_origins(data, parcel, removed, now)
    return affected


def remove_origins(
    data: ParcelsData, parcel: Parcel, removed: set[str], now: datetime
) -> None:
    """Remove some origins of a parcel and their events.

    A parcel left without origins is deleted.
    """
    for oid in removed:
        parcel.origins.pop(oid, None)
    parcel.events = [e for e in parcel.events if e.origin not in removed]
    if (flag := parcel.auto_merged) is not None:
        if flag.origin in removed:
            parcel.auto_merged = None
        elif set(flag.origins) & removed:
            parcel.auto_merged = replace(
                flag,
                origins=tuple(oid for oid in flag.origins if oid not in removed),
                groups=tuple(
                    kept
                    for group in flag.groups
                    if (kept := tuple(oid for oid in group if oid not in removed))
                ),
            )
    if parcel.origins:
        parcel.touch(now)
        _record_orders(data, parcel, now)
    else:
        data.parcels.pop(parcel.id, None)


def add_owner(
    data: ParcelsData, message_hash: str, owner: str, now: datetime
) -> set[str]:
    """Record that an e-mail was also found in another person's mailbox.

    The e-mail makes them an owner of its parcel. A private parcel's guesses
    are taken back first, so they don't see what only a guess put there: the
    owners get a suggestion instead. Returns the IDs of the parcels that
    changed.
    """
    return add_owner_to(data, {message_hash}, owner, now)


def add_owner_to(
    data: ParcelsData, messages: Collection[str], owner: str, now: datetime
) -> set[str]:
    """Make a person an owner of what some e-mails added, as :func:`add_owner`.

    E.g. the owner chosen for a mailbox after its e-mails were read. Returns
    the IDs of the parcels that changed.
    """
    keys = set(messages)
    affected: set[str] = set()
    for parcel in list(data.parcels.values()):
        if (
            parcel.private
            and parcel.auto_merged is not None
            and owner not in parcel.state.owners
            and any(o.message in keys for o in parcel.origins.values())
        ):
            affected.add(parcel.id)
            affected.update(new.id for new in _undo_guesses(data, parcel, now))
    for parcel in data.parcels.values():
        changed = False
        for origin in parcel.origins.values():
            if origin.message in keys and owner not in origin.owners:
                origin.owners = tuple(sorted({*origin.owners, owner}))
                changed = True
        if changed:
            parcel.touch(now)
            affected.add(parcel.id)
    for entry in data.returns.values():
        changed = False
        for key, found in entry.origins.items():
            if key in keys and owner not in found.owners:
                found.owners = tuple(sorted({*found.owners, owner}))
                changed = True
        if changed:
            entry.updated = now
    return affected


def remove_owner_from(
    data: ParcelsData, messages: Collection[str], owner: str, now: datetime
) -> set[str]:
    """Take a person off what some e-mails added, e.g. a mailbox's former owner.

    They stay an owner of a parcel through its other e-mails and additions.
    Returns the IDs of the parcels that changed.
    """
    keys = set(messages)
    affected: set[str] = set()
    for parcel in data.parcels.values():
        changed = False
        for origin in parcel.origins.values():
            if origin.message in keys and owner in origin.owners:
                origin.owners = tuple(o for o in origin.owners if o != owner)
                changed = True
        if changed:
            parcel.touch(now)
            affected.add(parcel.id)
    for entry in data.returns.values():
        changed = False
        for key, found in entry.origins.items():
            if key in keys and owner in found.owners:
                found.owners = tuple(o for o in found.owners if o != owner)
                changed = True
        if changed:
            entry.updated = now
    return affected


def fill_shop(
    data: ParcelsData, message_hash: str, merchant: str, now: datetime
) -> set[str]:
    """Name the shop where an e-mail's own readings name none, or the carrier.

    For e-mails an earlier release couldn't read the shop of. A filled-in
    gap of the local AI, or the user's edit, keeps what it says. Returns the
    IDs of the parcels that changed.
    """
    affected: set[str] = set()
    for parcel in data.parcels.values():
        changed = False
        for origin in parcel.origins.values():
            if (
                origin.message == message_hash
                and not origin.id.endswith(FILL_ORIGIN_SUFFIX)
                and (not origin.merchant or carrier_like(origin.merchant))
            ):
                origin.merchant = merchant
                changed = True
        if changed:
            parcel.touch(now)
            _record_orders(data, parcel, now)
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
    tracking number to one another parcel already has merges the two, and
    a number typed as an order's joins the order's only open parcel, as
    when adding it. Besides the fields, ``confirm`` confirms what the local
    AI found, ``confirm_merge`` keeps an automatic merge and
    ``confirm_delivery`` keeps an inferred delivery.
    """
    parcel = data.parcels[parcel_id]
    typed_order = parcel.state.typed_order
    edits = {key: changes[key] for key in UPDATABLE_FIELDS if key in changes}
    if edits or any(key in changes for key in ETA_FIELDS):
        origin = _edit_origin(parcel, now)
        for key, value in edits.items():
            text = str(value).strip() if value is not None else ""
            if key == "tracking_number":
                text = normalize_tracking_number(text)
            setattr(origin, key, text)
            # A pickup code typed at a point belongs to that point.
            origin.typed_at[key] = now
        if typed_order and "carrier" in edits and "tracking_number" not in edits:
            # The carrier is the order's, not its number's: see derive_state().
            origin.typed_at[TYPED_ORDER_MARK] = now
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
                # The reason's word isn't a label the details should show.
                event.label = None
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
    if (
        edits.keys() & {"tracking_number", "merchant", "carrier"}
        and (key := typed_order_key(parcel)) is not None
        and _typed_order_only(parcel, key)
    ):
        apart = _apart_checker(data)
        candidates = [
            other
            for other in _typed_candidates(data, key, parcel)
            if not apart(parcel, other) and _may_share_parcels(other, parcel)
        ]
        # With several, or one a guess may not join, see _join_typed().
        if len(candidates) == 1:
            merge_parcels(data, parcel_id, (candidates[0].id,), now)
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


def kept_apart_from(
    data: ParcelsData, origin_ids: Collection[str], parcel: Parcel
) -> bool:
    """Return True when the user keeps origins apart from a parcel."""
    one, two = set(origin_ids), parcel.origins.keys()
    return any(
        (not left.isdisjoint(one) and not right.isdisjoint(two))
        or (not left.isdisjoint(two) and not right.isdisjoint(one))
        for left, right in _kept_apart_pairs(data)
    )


# --- Guesses held back for privacy ----------------------------------------------

_HELD_REASONS = frozenset(
    {
        REASON_SAME_MERCHANT_ETA,
        REASON_SAME_NUMBER,
        REASON_SAME_MERCHANT_DAY,
        REASON_SAME_MERCHANT_DOMAIN,
        REASON_SAME_ORDER,
        REASON_SAME_REFERENCE,
        REASON_AMAZON_TRACKING,
        REASON_PARCEL_SWITCH,
    }
)


# A guess held back: the origins of its two sides and the reason.
type _Held = tuple[frozenset[str], frozenset[str], str]


def _held_guesses(data: ParcelsData) -> list[_Held]:
    """Return the guesses held back."""
    raw = data.engine.get(HELD_GUESSES)
    held: list[_Held] = []
    if not isinstance(raw, list):
        return held
    for entry in raw:
        if not isinstance(entry, list | tuple) or len(entry) != 3:
            continue
        first, second, reason = entry
        if reason not in _HELD_REASONS or not all(
            isinstance(side, list | tuple) for side in (first, second)
        ):
            continue
        left = frozenset(str(item) for item in first if item)
        right = frozenset(str(item) for item in second if item)
        if left and right and not left & right:
            held.append((left, right, reason))
    return held


def _store_held(data: ParcelsData, held: list[_Held]) -> None:
    if held:
        data.engine[HELD_GUESSES] = [
            [sorted(left), sorted(right), reason] for left, right, reason in held
        ]
    else:
        data.engine.pop(HELD_GUESSES, None)


def hold_guess(
    data: ParcelsData,
    first_ids: Collection[str],
    second_ids: Collection[str],
    reason: str,
) -> None:
    """Remember a guess not made, for the user to decide on.

    A guess never puts a private parcel together with someone else's e-mail
    or parcel: they would see it. Nor is news with other items joined to
    the package it only may be about (see :func:`_order_package`). The two
    sides, stored by origin IDs, are offered as a merge suggestion instead,
    which only people who may see both get (see :func:`reconcile`).
    """
    left, right = frozenset(first_ids), frozenset(second_ids)
    if not left or not right or left & right:
        return
    held: list[_Held] = []
    for one, two, why in _held_guesses(data):
        if {one, two} == {left, right}:
            return
        if (one & left and two & right) or (one & right and two & left):
            continue
        held.append((one, two, why))
    held.append((left, right, reason))
    _store_held(data, held)


def prune_held_guesses(data: ParcelsData) -> None:
    """Forget guesses that were merged, kept apart, or can no longer be.

    Each side must still be one parcel, both open and not the same one.
    """
    if HELD_GUESSES not in data.engine:
        return
    owner = {
        origin_id: parcel.id
        for parcel in data.parcels.values()
        for origin_id in parcel.origins
    }
    apart = _apart_checker(data)
    kept: list[_Held] = []
    pairs: set[frozenset[str]] = set()
    for left, right, reason in _held_guesses(data):
        ones = {owner[oid] for oid in left if oid in owner}
        twos = {owner[oid] for oid in right if oid in owner}
        if len(ones) != 1 or len(twos) != 1 or ones == twos:
            continue
        first, second = data.parcels[ones.pop()], data.parcels[twos.pop()]
        pair = frozenset((first.id, second.id))
        if (
            pair in pairs
            or first.archived is not None
            or second.archived is not None
            or apart(first, second)
            or _parcels_conflict(first, second, carried=True, numbers=True, typed=True)
        ):
            continue
        pairs.add(pair)
        kept.append(
            (
                frozenset(oid for oid in left if oid in owner),
                frozenset(oid for oid in right if oid in owner),
                reason,
            )
        )
    _store_held(data, kept)


def _suggest_held(data: ParcelsData, result: Reconciled) -> None:
    """Suggest the guesses held back, unless another suggestion has the pair.

    The parcel with a tracking number is the one the other joins, and the
    order's parcel the one a number typed as its order joins.
    """
    owner = {
        origin_id: parcel.id
        for parcel in data.parcels.values()
        for origin_id in parcel.origins
    }
    seen = {
        frozenset((suggestion.parcel_id, candidate))
        for suggestion in result.suggestions
        for candidate in suggestion.candidates
    }
    for left, right, reason in _held_guesses(data):
        first = data.parcels[owner[next(iter(left))]]
        second = data.parcels[owner[next(iter(right))]]
        if (pair := frozenset((first.id, second.id))) in seen:
            continue
        seen.add(pair)
        if _typed_for(first, second) or (
            not _typed_for(second, first) and _tracked(second) and not _tracked(first)
        ):
            first, second = second, first
        result.suggestions.append(_suggestion(first, [second], None, reason))


# --- Shops, carriers and their names -------------------------------------------


def _all_origins(data: ParcelsData) -> Iterator[Origin]:
    for parcel in data.parcels.values():
        yield from parcel.origins.values()


def is_shop(label: str) -> bool:
    """Return True for a sender domain of a shop Parcels doesn't know."""
    return bool(label) and lookup(label) is None and not is_free_mail(label)


def is_shop_sender(label: str) -> bool:
    """Return True for a sender domain whose e-mails speak for one shop.

    A shop Parcels doesn't know, or a known one that sends its carriers'
    notices from its own domain.
    """
    return is_shop(label) or relays_carrier_mail(label)


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
    """Return when a mailbox, 17TRACK or Parcel first told about a parcel."""
    return min(_news_times(parcel), default=None)


_SENT = frozenset({ParcelStatus.SHIPPED, ParcelStatus.IN_TRANSIT})
_ORDERED = frozenset({ParcelStatus.ORDERED})


def _first_dated(parcel: Parcel, statuses: frozenset[ParcelStatus]) -> datetime | None:
    """Return the time of the first dated news with one of these statuses.

    The user's edits and inferred events don't count.
    """
    return min(
        (
            event.time
            for event in parcel.events
            if event.status in statuses
            and not event.undated
            and not event.inferred
            and event.source is not Source.MANUAL
        ),
        default=None,
    )


def ordered_at(parcel: Parcel) -> datetime | None:
    """Return when the first news said a parcel's order was placed."""
    return _first_dated(parcel, _ORDERED)


def shipped_at(parcel: Parcel) -> datetime | None:
    """Return when the first news said a parcel left: shipped or in transit."""
    return _first_dated(parcel, _SENT)


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
    """Return when a parcel was delivered, unless that was only inferred.

    A delivery reported without a date gives none unless its day is known:
    it's placed on the day the parcel was expected, which can't prove that
    it came that day.
    """
    state = parcel.state
    if state.status is not ParcelStatus.DELIVERED or state.inferred:
        return None
    delivered = state.delivered_at
    if (
        delivered is not None
        and state.delivered_undated
        and not any(
            event.time == delivered
            and event.status is ParcelStatus.DELIVERED
            and day_known(event)
            for event in parcel.events
        )
    ):
        return None
    return delivered


def reported_delivery_event(parcel: Parcel) -> ParcelEvent | None:
    """Return the news that a parcel was delivered, from an e-mail, 17TRACK or Parcel.

    A delivery the user marked or confirmed doesn't say which carrier's
    package it was, so it never pairs parcels or infers other deliveries.
    """
    if (delivered := _real_delivery(parcel)) is None:
        return None
    events = [
        event
        for event in parcel.events
        if event.time == delivered
        and event.status is ParcelStatus.DELIVERED
        and event.source is not Source.MANUAL
        and not event.inferred
    ]
    # The one that tells the day, when another at that time doesn't.
    return next((event for event in events if day_known(event)), None) or next(
        iter(events), None
    )


def _reported_delivery(parcel: Parcel) -> datetime | None:
    """Return when an e-mail, 17TRACK or Parcel said a parcel was delivered."""
    event = reported_delivery_event(parcel)
    return None if event is None else event.time


def _parcels_conflict(
    first: Parcel,
    second: Parcel,
    *,
    carried: bool = False,
    numbers: bool = False,
    typed: bool = False,
) -> bool:
    """Return True when two parcels can't be the same parcel.

    With ``carried``, a carrier's package that carries Amazon shipments may
    take one more, of another order, or hold another order of the day. With
    ``numbers``, two parcels with the same tracking number, read as two
    carriers' numbers, may be one. With ``typed``, a parcel known only by a
    number typed as the other's order may be it (see :func:`_typed_for`).
    """
    one, two = first.state, second.state
    if (
        one.tracking_number
        and two.tracking_number
        and not (
            numbers
            and number_key_text(one.tracking_number)
            == number_key_text(two.tracking_number)
        )
        and not (typed and (_typed_for(first, second) or _typed_for(second, first)))
    ):
        return True
    holds = carried and (
        (_is_box(first) and _carries(first)) or (_is_box(second) and _carries(second))
    )
    if not holds:
        if (
            one.amazon_shipment_ids
            and two.amazon_shipment_ids
            and not set(one.amazon_shipment_ids) & set(two.amazon_shipment_ids)
        ):
            return True
        orders_one, orders_two = parcel_order_keys(first), parcel_order_keys(second)
        if orders_one and orders_two and not orders_one & orders_two:
            return True
    return _references_differ(
        parcel_reference_keys(first), parcel_reference_keys(second)
    )


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
        groups=flag.groups,
    )


def _may_auto_merge(target: Parcel, other: Parcel) -> bool:
    """Return True when a guessed merge of two parcels can still be undone.

    A parcel merged by an earlier guess gets suggestions instead, except a
    merge of the same order's e-mails, which leaves together on undo.
    """
    return target.auto_merged is None and (
        other.auto_merged is None or other.auto_merged.reason == REASON_SAME_ORDER
    )


def switch_target_open(parcel: Parcel) -> bool:
    """Return True when an order's parcel may take the carrier's number.

    An archived or finished parcel, or one with a number already, may not.
    """
    state = parcel.state
    return parcel.archived is None and not state.terminal and not state.tracking_number


def join_switched(
    data: ParcelsData, target_id: str, other_id: str, now: datetime
) -> bool:
    """Merge a carrier's parcel into the Amazon order's parcel it continues.

    The Parcel app may switch an Amazon delivery to the carrier's number,
    and the carrier's delivery became a parcel of its own. The merge is
    flagged, so the user can undo it. Not when the user keeps them apart,
    the order's parcel may not take the number (:func:`switch_target_open`),
    or they can't be one parcel: another order, shipment or shop. A private
    parcel and someone else's are only suggested (see :func:`hold_guess`).
    Returns True when merged.
    """
    target, other = data.parcels.get(target_id), data.parcels.get(other_id)
    if (
        target is None
        or other is None
        or target is other
        or other.archived is not None
        or not switch_target_open(target)
        or _parcels_conflict(target, other)
        or _apart_checker(data)(target, other)
    ):
        return False
    shops = {key for key in _shop_keys(other) if not is_carrier_name(key)}
    if shops and shops.isdisjoint(_shop_keys(target)):
        return False
    if not _may_share_parcels(target, other):
        hold_guess(data, target.origins, other.origins, REASON_PARCEL_SWITCH)
        return False
    _auto_merge(data, target, other, REASON_PARCEL_SWITCH, now, Reconciled())
    return True


def flag_switch(
    data: ParcelsData, parcel_id: str, origin_ids: Collection[str], now: datetime
) -> None:
    """Flag origins that joined a parcel because the Parcel app switched it.

    They leave on undo. A parcel already flagged by a guess has its flag
    grow, so one undo takes back both.
    """
    parcel = data.parcels[parcel_id]
    joined = sorted(
        set(origin_ids) & parcel.origins.keys(),
        key=lambda oid: (parcel.origins[oid].time, oid),
    )
    if not joined:
        return
    if parcel.auto_merged is not None:
        parcel.auto_merged = _grown(parcel.auto_merged, parcel, set(joined))
    else:
        parcel.auto_merged = AutoMerge(
            origin=joined[0],
            at=now,
            reason=REASON_PARCEL_SWITCH,
            origins=tuple(joined[1:]),
        )
    parcel.touch(now)


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
            if not _may_share_parcels(other, parcel):
                hold_guess(data, other.origins, parcel.origins, REASON_SAME_ORDER)
                continue
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
        if not _may_share_parcels(target, other):
            hold_guess(data, target.origins, other.origins, REASON_SAME_ORDER)
            continue
        _auto_merge(data, target, other, REASON_SAME_ORDER, now, result)
        return True
    return False


def _join_typed(
    data: ParcelsData,
    apart: Callable[[Parcel, Parcel], bool],
    now: datetime,
    result: Reconciled,
) -> None:
    """Join a parcel typed under an order's number to the order's parcel.

    One typed before the order's parcel came, or before Parcels joined such
    numbers, joins the order's only open parcel, undoably. With several, or
    when a guess may not put them together (see :func:`_may_share`), the
    user gets a suggestion for each.
    """
    while True:
        found: list[tuple[Parcel, list[Parcel]]] = []
        for parcel in sorted(data.parcels.values(), key=lambda p: p.id):
            if (key := typed_order_key(parcel)) is None or not _typed_order_only(
                parcel, key
            ):
                continue
            candidates = [
                other
                for other in _typed_candidates(data, key, parcel)
                if not apart(parcel, other)
            ]
            if (
                len(candidates) == 1
                and _may_share_parcels(candidates[0], parcel)
                and _may_auto_merge(candidates[0], parcel)
            ):
                _auto_merge(data, candidates[0], parcel, REASON_SAME_ORDER, now, result)
                break
            found.append((parcel, candidates))
        else:
            break
    seen = {
        frozenset((suggestion.parcel_id, candidate))
        for suggestion in result.suggestions
        for candidate in suggestion.candidates
    }
    for parcel, candidates in found:
        for other in candidates:
            if (pair := frozenset((other.id, parcel.id))) not in seen:
                seen.add(pair)
                result.suggestions.append(
                    _suggestion(other, [parcel], None, REASON_SAME_ORDER)
                )


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
            if origin.message is not None and is_shop_sender(origin.label):
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
        if (
            len(parcels) == 1
            and _may_auto_merge(target, parcels[0])
            and _may_share_parcels(target, parcels[0])
        ):
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
        if state.status_time is not None and not state.status_undated:
            return local_date(state.status_time)
    return None


def _shop_keys(parcel: Parcel) -> set[str]:
    """Return the names a parcel's shop goes by: its merchant, and its seller.

    A marketplace's carrier names the seller rather than the marketplace,
    and "Loja Exemplo (Exemplo Lda)" may go by its brand or its company.
    """
    state = parcel.state
    keys = {merchant_key(state.merchant)}
    if seller := state.seller:
        brand, _, company = seller.partition("(")
        keys.update(
            key
            for name in (seller, brand, company.partition(")")[0])
            if len(key := merchant_key(name)) >= SELLER_KEY_MIN_LENGTH
        )
    return keys - {""}


# --- Amazon shipments and the carrier's package -----------------------------------

# A place from the Parcel app is a name, not a sentence: "Vila Exemplo".
PLACE_MAX_WORDS = 8
PLACE_MAX_LENGTH = 60
_PLACE_TOKEN = re.compile(r"[a-z0-9]{3,}")
# Amazon's tracking says "Entrega em curso" when the van leaves, which no
# e-mail of the carriers says.
_VAN_OUT_PHRASES = (
    *KIND_PHRASES[MailKind.OUT_FOR_DELIVERY],
    "entrega em curso",
    "em entrega",
)


@dataclass(frozen=True, slots=True)
class AmazonEvidence:
    """When and where Amazon's tracking says a shipment was delivered.

    With ``timeless``, Amazon gave the day but not the time.
    """

    delivered: datetime
    timeless: bool
    place: str | None


@dataclass(frozen=True, slots=True)
class _Mark:
    """A time a shipment or package was seen at, and where.

    A scan's time (Amazon's tracking, 17TRACK, the Parcel app) is the
    carrier's; an e-mail leaves some time after what it tells.
    """

    time: datetime
    place: str | None = None
    scan: bool = False


def _van_out(event: ParcelEvent) -> bool:
    """Return whether an event says the parcel left for delivery."""
    return (
        event.status is ParcelStatus.OUT_FOR_DELIVERY
        or event.kind is MailKind.OUT_FOR_DELIVERY
        or (
            bool(event.label)
            and phrase_regex(_VAN_OUT_PHRASES).search(fold_text(event.label or ""))
            is not None
        )
    )


def _amazon_tracking(origin: Origin) -> bool:
    """Return whether an origin is the Parcel app's tracking of an Amazon order."""
    return (
        origin.source is Source.PARCELAPP
        and bool(origin.order_numbers)
        and not origin.tracking_number
    )


def _carries(parcel: Parcel) -> bool:
    """Return whether a parcel holds the Parcel app's tracking of Amazon's."""
    return any(_amazon_tracking(origin) for origin in parcel.origins.values())


def _amazon_mail(origin: Origin) -> bool:
    """Return whether an origin is one of Amazon's e-mails."""
    return (
        origin.message is not None
        and (info := lookup(origin.label or "")) is not None
        and info.parser == "amazon"
    )


def _exact(event: ParcelEvent) -> bool:
    """Return whether an event tells a time it was really seen at."""
    return (
        not event.inferred
        and not event.undated
        and event.source is not Source.MANUAL
        and (event.status is not None or bool(event.label))
    )


def _is_shipment(parcel: Parcel) -> bool:
    """Return whether a parcel is an Amazon shipment the Parcel app follows.

    It has no carrier's number: the package that carried it is another
    parcel.
    """
    state = parcel.state
    return (
        not state.tracking_number
        and state.status not in (ParcelStatus.CANCELLED, ParcelStatus.RETURNED)
        and _carries(parcel)
    )


def _is_box(parcel: Parcel) -> bool:
    """Return whether a parcel is a carrier's package of no shop's order.

    The orders of the Amazon shipments it carries don't count: one package
    may carry several.
    """
    state = parcel.state
    if not state.tracking_number:
        return False
    carried: set[str] = set()
    for origin in parcel.origins.values():
        keys = origin_order_keys(origin, state.merchant)
        if origin.tracking_number and keys:
            return False
        if _amazon_tracking(origin):
            carried |= keys
    return parcel_order_keys(parcel) <= carried


def _own_origin(origin: Origin) -> bool:
    """Return whether an origin tells about a package itself.

    Not the user's edits, nor Amazon's e-mails or tracking of the shipments
    it carries.
    """
    return (
        origin.source is not Source.MANUAL
        and origin.amazon_shipment_id is None
        and not (origin.order_numbers and not origin.tracking_number)
        and not _amazon_mail(origin)
    )


def _codes(part: str) -> bool:
    """Return whether a part of a label is only two-letter codes: "PT PT"."""
    words = part.split()
    return bool(words) and all(len(word) == 2 and word.isalpha() for word in words)


def _place(event: ParcelEvent) -> str | None:
    """Return the place a Parcel app event names, or None.

    The app writes an event as "<what>, <place>", maybe followed by the
    country's code, even twice: "Entregue, Vila Exemplo, PT PT".
    """
    if event.source is not Source.PARCELAPP or not event.label:
        return None
    parts = [part.strip() for part in event.label.split(",")]
    while len(parts) > 1 and _codes(parts[-1]):
        parts.pop()
    if len(parts) < 2:
        return None
    place = parts[-1]
    if (
        not place
        or len(place) > PLACE_MAX_LENGTH
        or len(place.split()) > PLACE_MAX_WORDS
        or not any(char.isalpha() for char in place)
        or place.endswith((".", "!", "?", "…"))
    ):
        return None
    return place


def _places_differ(first: str | None, second: str | None) -> bool:
    """Return True when two places share no word: they're other places."""
    if not first or not second:
        return False
    one = set(_PLACE_TOKEN.findall(fold_text(first)))
    two = set(_PLACE_TOKEN.findall(fold_text(second)))
    return bool(one) and bool(two) and one.isdisjoint(two)


def _agrees(amazon: _Mark, own: _Mark) -> bool:
    """Return whether a package's own news repeats one of Amazon's."""
    return (
        amazon.time - AGREE_BEFORE <= own.time <= amazon.time + AGREE_AFTER
        and not _places_differ(amazon.place, own.place)
    )


def _hand_marks(parcel: Parcel) -> list[datetime]:
    """Return when the user marked a parcel delivered."""
    return [
        event.time
        for event in parcel.events
        if event.source is Source.MANUAL
        and event.status is ParcelStatus.DELIVERED
        and not event.inferred
    ]


def _by_hand(parcel: Parcel) -> bool:
    """Return whether a parcel's delivery time is when the user marked it.

    It had come by then, maybe hours before.
    """
    return _real_delivery(parcel) is not None and _reported_delivery(parcel) is None


def _came_together(
    first: datetime, first_by_hand: bool, second: datetime, second_by_hand: bool
) -> bool:
    """Return whether two deliveries may have been one.

    A delivery marked by hand had come by then: only a later one rules it
    out.
    """
    if first_by_hand and second_by_hand:
        return True
    if first_by_hand:
        return second <= first + BOX_DELIVERY_SLACK
    if second_by_hand:
        return first <= second + BOX_DELIVERY_SLACK
    return abs(first - second) <= BOX_DELIVERY_SLACK


def _amazon_marks(parcel: Parcel) -> tuple[_Mark | None, list[_Mark]]:
    """Return Amazon's delivery of a shipment, and its other news but the van.

    Several packages in one van leave and come together; only their other
    news tells them apart.
    """
    return _tracking_marks(parcel, _tracking_of(parcel))


def _tracking_of(parcel: Parcel) -> set[str]:
    """Return the origins of a parcel that are Amazon's tracking."""
    return {oid for oid, origin in parcel.origins.items() if _amazon_tracking(origin)}


def _tracking_marks(
    parcel: Parcel, tracking: Collection[str]
) -> tuple[_Mark | None, list[_Mark]]:
    """Return the delivery some of Amazon's tracking tells, and its other news.

    Its other news leaves out the van leaving, see :func:`_amazon_marks`.
    """
    events = [
        event for event in parcel.events if event.origin in tracking and _exact(event)
    ]
    done = [event for event in events if event.status is ParcelStatus.DELIVERED]
    delivered = None
    if done:
        last = max(done, key=lambda event: event.time)
        delivered = _Mark(last.time, _place(last), scan=True)
    further = [
        _Mark(event.time, _place(event), scan=True)
        for event in events
        if event.status is not ParcelStatus.DELIVERED and not _van_out(event)
    ]
    return delivered, further


def _box_evidence(box: Parcel) -> tuple[list[_Mark], list[_Mark]]:
    """Return a package's own deliveries, and its other news but the van.

    The other news are the scans 17TRACK and the Parcel app give, and the
    carrier's first e-mail, sent when the package reached it.
    """
    own = {oid: origin for oid, origin in box.origins.items() if _own_origin(origin)}
    delivered: list[_Mark] = []
    further: list[_Mark] = []
    for event in box.events:
        origin = own.get(event.origin or "")
        if origin is None or not _exact(event):
            continue
        scan = origin.message is None
        if event.status is ParcelStatus.DELIVERED:
            delivered.append(_Mark(event.time, _place(event), scan))
        elif scan and not _van_out(event):
            further.append(_Mark(event.time, _place(event), scan=True))
    mails = sorted(
        (origin for origin in own.values() if origin.message is not None),
        key=lambda origin: (origin.time, origin.id),
    )
    if mails and not any(
        event.origin == mails[0].id
        and (event.status is ParcelStatus.DELIVERED or _van_out(event))
        for event in box.events
    ):
        further.append(_Mark(mails[0].time))
    return delivered, further


def _contradicted(
    at: datetime, marks: Iterable[_Mark], bounds: Iterable[datetime]
) -> bool:
    """Return whether a package's delivery rules out one at ``at``.

    A scan gives the time, which must be within two hours. An e-mail or the
    user's mark says only that it had come by then: it rules out a delivery
    more than two hours later.
    """
    marks = list(marks)
    if scans := [mark.time for mark in marks if mark.scan]:
        return not any(abs(time - at) <= CONTRADICTION_GAP for time in scans)
    upper = [mark.time for mark in marks if not mark.scan] + list(bounds)
    return bool(upper) and min(upper) < at - CONTRADICTION_GAP


def amazon_contradicts(shipment: Parcel, box: Parcel) -> bool:
    """Return whether Amazon's tracking rules out that a package held a parcel.

    The parcel has no carrier's number and Amazon's tracking says when it
    was delivered; the package was delivered at another time.
    """
    if shipment.state.tracking_number or not box.state.tracking_number:
        return False
    mark, _further = _amazon_marks(shipment)
    if mark is None:
        return False
    delivered, _further = _box_evidence(box)
    return _contradicted(mark.time, delivered, _hand_marks(box))


def amazon_disagree(first: Parcel, second: Parcel) -> bool:
    """Return whether Amazon's tracking rules out that two parcels are one."""
    return amazon_contradicts(first, second) or amazon_contradicts(second, first)


def amazon_evidence(parcel: Parcel) -> AmazonEvidence | None:
    """Return when and where Amazon's tracking says a shipment was delivered."""
    if not _is_shipment(parcel):
        return None
    tracking = _tracking_of(parcel)
    found = [
        event
        for event in parcel.events
        if event.origin in tracking
        and event.status is ParcelStatus.DELIVERED
        and not event.inferred
        and event.source is not Source.MANUAL
        and day_known(event)
    ]
    if not found:
        return None
    event = max(found, key=lambda event: event.time)
    return AmazonEvidence(event.time, event.undated, _place(event))


def _may_carry(
    shipment: Parcel, box: Parcel, apart: Callable[[Parcel, Parcel], bool]
) -> bool:
    """Return whether a package may have carried an Amazon shipment.

    Not another carrier's, another shop's, a private package with a public
    shipment, or one the user keeps apart.
    """
    if box.private and not shipment.private:
        return False
    if not _same_carrier(shipment.state.carrier, box.state.carrier):
        return False
    keys, box_keys = _shop_keys(shipment), _shop_keys(box)
    if keys and box_keys and keys.isdisjoint(box_keys):
        return False
    return not apart(shipment, box) and not _parcels_conflict(
        shipment, box, carried=True
    )


def _carry(
    data: ParcelsData, box: Parcel, shipment: Parcel, now: datetime, result: Reconciled
) -> bool:
    """Merge an Amazon shipment into the package that carried it, undoably.

    Shipments linked one by one leave as their own parcels on undo. A
    package or shipment merged by another guess isn't merged again.
    """
    earlier = box.auto_merged
    if earlier is not None and earlier.reason != REASON_AMAZON_TRACKING:
        return False
    if (
        shipment.auto_merged is not None
        and shipment.auto_merged.reason != REASON_SAME_ORDER
    ):
        return False
    if earlier is None:
        _auto_merge(data, box, shipment, REASON_AMAZON_TRACKING, now, result)
        return True
    present = tuple(
        sorted(
            earlier.all_origins & box.origins.keys(),
            key=lambda oid: (box.origins[oid].time, oid),
        )
    )
    groups = earlier.groups or ((present,) if present else ())
    moving = tuple(
        sorted(shipment.origins, key=lambda oid: (shipment.origins[oid].time, oid))
    )
    _auto_merge(data, box, shipment, REASON_AMAZON_TRACKING, now, result)
    if (flag := box.auto_merged) is not None:
        box.auto_merged = replace(flag, groups=(*groups, moving))
    return True


def _linkable_packages(data: ParcelsData) -> Iterator[Parcel]:
    """Yield the carriers' packages an Amazon shipment may be linked to.

    Packages put away count too; cancelled and returned ones don't.
    """
    for parcel in data.parcels.values():
        if parcel.state.status not in (
            ParcelStatus.CANCELLED,
            ParcelStatus.RETURNED,
        ) and _is_box(parcel):
            yield parcel


def _side(parcel: Parcel, origins: Collection[str]) -> Parcel:
    """Return what a parcel would be with only some of its origins.

    Nothing changes: it only weighs what each side of a merge tells.
    """
    kept = set(origins)
    return Parcel(
        id=parcel.id,
        created=parcel.created,
        updated=parcel.updated,
        origins={oid: parcel.origins[oid] for oid in kept},
        events=[event for event in parcel.events if event.origin in kept],
        private=parcel.private,
        delivery_rejected=parcel.delivery_rejected,
    )


def _undo_amazon_guesses(
    data: ParcelsData,
    pool: list[Parcel],
    apart: Callable[[Parcel, Parcel], bool],
    now: datetime,
    result: Reconciled,
) -> int:
    """Undo the shop's guesses that Amazon's tracking proves wrong.

    A guess put an Amazon shipment and a carrier's package together because
    the shop and the day matched. It is undone, as Undo would, when Amazon's
    tracking rules the package out, or when exactly one other package
    repeats the shipment's times as :func:`_link_amazon_shipments` asks and
    the merged one doesn't. It is undone too, before the shipment came or
    after, when the merged package repeats none of the shipment's times and
    its tracking points to other packages, see :func:`_pointed`: a package
    that held the shipment repeats at least one of them, the minute it
    reached the carrier or the one it came. The two are then kept apart,
    and the shipment is linked like any other. Each side is weighed as Undo
    would leave it: the user's edits stay with the parcel, so a guess the
    user gave a tracking number stays. The user's merges, other links and
    parcels put away stay, and so does a shipment merged with another one's
    tracking, or with an e-mail naming no package. Returns how many guesses
    were undone.
    """
    undone = 0
    for parcel in pool:
        flag = parcel.auto_merged
        if (
            flag is None
            or flag.reason not in (REASON_SAME_MERCHANT_ETA, REASON_SAME_MERCHANT_DAY)
            or parcel.id in result.removed
            or parcel.archived is not None
        ):
            continue
        parts = _undo_parts(flag, parcel)
        if len(parts) != 1 or split_problem(parcel, parts[0]) is not None:
            continue
        staying = parcel.origins.keys() - parts[0]
        sides = [_side(parcel, parts[0]), _side(parcel, staying)]
        shipments = [side for side in sides if _is_shipment(side)]
        if len(shipments) != 1:
            continue
        [shipment] = shipments
        [box] = [side for side in sides if side is not shipment]
        if not box.state.tracking_number or len(_tracking_of(shipment)) != 1:
            continue
        marks = _amazon_marks(shipment)
        wrong = False
        if marks[0] is not None:
            delivered, _further = _box_evidence(box)
            wrong = _contradicted(marks[0].time, delivered, _hand_marks(parcel))
            if not wrong and _agreement(marks, box) < 2:
                agreeing = [
                    other
                    for other in _linkable_packages(data)
                    if other.id != parcel.id
                    and _agreement(marks, other) == 2
                    and _may_carry(shipment, other, apart)
                ]
                wrong = len(agreeing) == 1
        if not wrong and _agreement(marks, box) == 0:
            others = [other for other in _boxes(data) if other.id != parcel.id]
            wrong = bool(_pointed(shipment, others, apart))
        if not wrong:
            continue
        new = undo_auto_merge(data, parcel.id, now)
        result.changed.add(parcel.id)
        if new is not None:
            result.changed.add(new.id)
            undone += 1
    return undone


def _link_amazon_shipments(
    data: ParcelsData,
    pool: list[Parcel],
    apart: Callable[[Parcel, Parcel], bool],
    now: datetime,
    result: Reconciled,
    *,
    undone: int = 0,
) -> set[str]:
    """Link Amazon shipments to the carriers' packages that carried them.

    Amazon's tracking of a shipment, which the Parcel app follows, repeats
    the scans of the carrier's package to the minute. A package carried it
    when it was delivered that minute and one more of its news agrees: a
    scan, or its first e-mail, sent when the package reached the carrier.
    The van leaving doesn't count, since a van takes many packages. When
    exactly one package agrees, the shipment merges into it, undoably; when
    several do, each is suggested. A package delivered at another time is
    ruled out. ``undone`` counts the guesses Amazon's tracking proved wrong
    this time. Returns the shipments that were linked or suggested.
    """
    shipments = [
        parcel
        for parcel in pool
        if parcel.id not in result.removed and _is_shipment(parcel)
    ]
    previous = data.engine.get(AMAZON_LINKS_KEY)
    if not shipments and not isinstance(previous, Mapping) and not undone:
        return set()
    boxes: list[tuple[Parcel, list[_Mark], list[_Mark], list[datetime], date | None]]
    boxes = []
    for box in _linkable_packages(data):
        delivered, further = _box_evidence(box)
        hands = _hand_marks(box)
        if delivered or hands:
            came = _real_delivery(box)
            boxes.append(
                (
                    box,
                    delivered,
                    further,
                    hands,
                    None if came is None else local_date(came),
                )
            )

    handled: set[str] = set()
    made = ambiguous = contradicted = 0
    for shipment in shipments:
        mark, extra = _amazon_marks(shipment)
        if mark is None:
            continue
        day = local_date(mark.time)
        found: list[Parcel] = []
        for box, delivered, further, hands, came in boxes:
            if box.id in result.removed:
                continue
            if (
                any(_agrees(mark, own) for own in delivered)
                and any(_agrees(theirs, own) for theirs in extra for own in further)
                and _may_carry(shipment, box, apart)
            ):
                found.append(box)
            elif (
                came == day
                and _contradicted(mark.time, delivered, hands)
                and _may_carry(shipment, box, apart)
            ):
                contradicted += 1
        if not found:
            continue
        handled.add(shipment.id)
        if len(found) == 1:
            [box] = found
            if _may_share_parcels(box, shipment) and _carry(
                data, box, shipment, now, result
            ):
                made += 1
            elif box.archived is None and shipment.archived is None:
                result.suggestions.append(
                    _suggestion(box, [shipment], day, REASON_AMAZON_TRACKING)
                )
            continue
        ambiguous += 1
        if shipment.archived is None:
            result.suggestions.extend(
                _suggestion(box, [shipment], day, REASON_AMAZON_TRACKING)
                for box in found
                if box.archived is None
            )

    earlier = previous.get("made") if isinstance(previous, Mapping) else None
    before = previous.get("undone") if isinstance(previous, Mapping) else None
    counts = {
        "made": (earlier if isinstance(earlier, int) else 0) + made,
        "ambiguous": ambiguous,
        "contradicted": contradicted,
        "undone": (before if isinstance(before, int) else 0) + undone,
    }
    if counts != previous:
        data.engine[AMAZON_LINKS_KEY] = counts
    return handled


def _pair_by_day(
    data: ParcelsData,
    pool: list[Parcel],
    apart: Callable[[Parcel, Parcel], bool],
    now: datetime,
    result: Reconciled,
    *,
    skip: Collection[str] = frozenset(),
) -> None:
    """Pair parcels without a tracking number with a carrier's delivery.

    A shop's e-mail rarely names the carrier's number, and the carrier's
    e-mail doesn't name the order, so the same package shows twice: once
    from the shop and once from the carrier, with the shop's name. When the
    carrier delivers (or is delivering) on the shop's date and they're the
    only two that could be the same package, they merge. An open parcel of
    the shop that is late, or due in the next days, could be it too, and two
    carriers known to differ never pair, nor does a delivery made before the
    day the shop's package left. Otherwise the user gets suggestions. The
    Amazon shipments in ``skip`` were already linked by Amazon's tracking,
    and a package it rules out is never paired.

    When a shipment's tracking repeats times of some packages, see
    :func:`_pointed`, it pairs only with those. Leaving the others out
    never makes a merge of what was a suggestion.
    """
    untracked: list[tuple[Parcel, set[str], date, date, datetime, date | None]] = []
    tracked: list[tuple[Parcel, set[str], date]] = []
    for parcel in pool:
        if parcel.id in skip:
            continue
        state = parcel.state
        if not (keys := _shop_keys(parcel)):
            continue
        if state.tracking_number:
            if (day := _delivery_day(parcel)) is not None:
                tracked.append((parcel, keys, day))
        elif (expected := _expected_days(parcel)) is not None and (
            first := first_news(parcel)
        ) is not None:
            shipped = shipped_at(parcel)
            untracked.append(
                (
                    parcel,
                    keys,
                    *expected,
                    first,
                    None if shipped is None else local_date(shipped),
                )
            )

    edges: dict[str, set[str]] = defaultdict(set)
    days: dict[str, date] = {}
    fits: set[frozenset[str]] = set()
    narrowed: set[str] = set()
    boxes = _boxes(data)
    for parcel, keys, start, end, first, sent in untracked:
        # A parcel may arrive late or early, unless news closed it (a
        # "probably delivered" guess doesn't); only a fit is sure.
        waiting = not _finished(parcel)
        points = _pointed(parcel, boxes, apart)
        for other, other_keys, day in tracked:
            delivered = _real_delivery(other)
            fit = start <= day <= end
            if (
                keys & other_keys
                and (
                    fit
                    or (waiting and _could_arrive(Eta(start=start, end=end), day, day))
                )
                and _same_carrier(parcel.state.carrier, other.state.carrier)
                and (delivered is None or first < delivered)
                and (sent is None or sent <= day)
                and not _parcels_conflict(parcel, other)
                and not apart(parcel, other)
                and not amazon_contradicts(parcel, other)
            ):
                if points and other.id not in points:
                    narrowed.update((parcel.id, other.id))
                    continue
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
            and not component & narrowed
        ):
            target = data.parcels[targets[0]]
            other = data.parcels[sources[0]]
            if _may_auto_merge(target, other) and _may_share_parcels(target, other):
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


# --- Packages of the day ---------------------------------------------------------


def _of_day(state: ParcelState, day: date) -> bool:
    """Return whether a parcel comes on a day: due then or late, or came then."""
    if state.status in _NOT_COMING:
        return False
    if state.status is ParcelStatus.DELIVERED:
        delivered = state.delivered_at or state.status_time
        return delivered is None or local_date(delivered) == day
    return state.eta is None or state.eta.end <= day


def _box_may_hold(
    order: Parcel, box: Parcel, apart: Callable[[Parcel, Parcel], bool]
) -> bool:
    """Return whether a carrier's package may hold an order of the same day.

    Its shop must be the order's or unknown, its carrier the one the shop
    named, if any, and it can't hold a public order when it's private. A
    delivered order was in a package delivered within a few hours; one the
    user marked delivered had come by then. An order that had news after the
    package came, or none before, wasn't in it, nor was an Amazon shipment
    whose tracking says it came at another time.
    """
    mine, theirs = order.state, box.state
    if box.private and not order.private:
        return False
    keys, box_keys = _shop_keys(order), _shop_keys(box)
    if box_keys and keys.isdisjoint(box_keys):
        return False
    if (
        not _same_carrier(mine.carrier, theirs.carrier)
        or _parcels_conflict(order, box, carried=True)
        or apart(order, box)
        or amazon_contradicts(order, box)
    ):
        return False
    delivered = _real_delivery(box)
    if (
        delivered is not None
        and (first := first_news(order)) is not None
        and first >= delivered
    ):
        return False
    if mine.status is ParcelStatus.DELIVERED:
        if theirs.status is not ParcelStatus.DELIVERED:
            return False
        came = None if mine.delivered_undated else mine.delivered_at
        if (
            came is not None
            and delivered is not None
            and not _came_together(came, _by_hand(order), delivered, _by_hand(box))
        ):
            return False
    elif (
        delivered is not None
        and mine.status_time is not None
        and not mine.status_undated
        and mine.status_time > delivered
    ):
        return False
    return True


def _box_rank(order: Parcel, box: Parcel) -> tuple[int, int]:
    """Rank the packages that may hold an order: its shop's, its carrier's."""
    family = carrier_family(order.state.carrier)
    return (
        0 if _shop_keys(order) & _shop_keys(box) else 1,
        0 if family is not None and family == carrier_family(box.state.carrier) else 1,
    )


def _agreement(marks: tuple[_Mark | None, list[_Mark]], box: Parcel) -> int:
    """Return how many of a shipment's kinds of time a package repeats.

    Its delivery, and its other news but the van leaving: a point each, as
    :func:`_link_amazon_shipments` asks both.
    """
    mark, extra = marks
    delivered, further = _box_evidence(box)
    return int(mark is not None and any(_agrees(mark, own) for own in delivered)) + int(
        any(_agrees(theirs, own) for theirs in extra for own in further)
    )


def _boxes(data: ParcelsData) -> list[Parcel]:
    """Return the carriers' packages still coming or come, see :func:`_is_box`.

    Not the archived ones, nor those cancelled or sent back.
    """
    return [
        parcel
        for parcel in data.parcels.values()
        if parcel.archived is None
        and parcel.state.status not in (ParcelStatus.CANCELLED, ParcelStatus.RETURNED)
        and _is_box(parcel)
    ]


def _pointed(
    shipment: Parcel, boxes: Iterable[Parcel], apart: Callable[[Parcel, Parcel], bool]
) -> frozenset[str]:
    """Return the packages an Amazon shipment's tracking points to, if any.

    Of the packages that may hold it, see :func:`_box_may_hold`, those
    repeating the most of its times but the van leaving, as in
    :func:`boxes_of_day`, whatever their day: a carrier's first e-mail and
    its scans come before its package does.
    """
    if not _is_shipment(shipment):
        return frozenset()
    marks = _amazon_marks(shipment)
    if marks[0] is None and not marks[1]:
        return frozenset()
    scores = {
        box.id: _agreement(marks, box)
        for box in boxes
        if _box_may_hold(shipment, box, apart)
    }
    top = max(scores.values(), default=0)
    return frozenset(pid for pid, score in scores.items() if top and score == top)


def amazon_elsewhere(
    data: ParcelsData,
    parcel: Parcel,
    visible: Callable[[Parcel], bool] = lambda _parcel: True,
) -> set[str]:
    """Return the ``visible`` parcels Amazon's tracking points away from.

    From a shipment whose tracking points to some packages, see
    :func:`_pointed`, the other packages; from a package, the shipments
    whose tracking points to others. A shipment counts only when one of the
    packages it points to is ``visible``: the marks never tell of a package
    the viewer may not see.
    """
    if parcel.archived is not None:
        return set()
    apart = _apart_checker(data)
    boxes = _boxes(data)

    def points(shipment: Parcel) -> frozenset[str]:
        found = _pointed(shipment, boxes, apart)
        if any(visible(data.parcels[pid]) for pid in found):
            return found
        return frozenset()

    if _is_shipment(parcel):
        if not (found := points(parcel)):
            return set()
        return {box.id for box in boxes if box.id not in found and visible(box)}
    if all(box.id != parcel.id for box in boxes):
        return set()
    return {
        shipment.id
        for shipment in data.parcels.values()
        if shipment.archived is None
        and visible(shipment)
        and (found := points(shipment))
        and parcel.id not in found
    }


@dataclass(frozen=True, slots=True)
class _Read:
    """What the Parcel app last showed of some of Amazon's tracking, and when."""

    at: datetime
    delivered: _Mark | None
    further: tuple[_Mark, ...]
    latest: datetime | None


def _read_at(data: ParcelsData, oid: str) -> datetime | None:
    """Return when Parcels last read a delivery in the Parcel app, if known."""
    records = data.parcelapp.get("records")
    if not oid.startswith(PARCELAPP_PREFIX) or not isinstance(records, Mapping):
        return None
    record = records.get(oid.removeprefix(PARCELAPP_PREFIX))
    return dt_from_str(record.get("seen")) if isinstance(record, Mapping) else None


def _shipment_read(data: ParcelsData, shipment: Parcel) -> datetime | None:
    """Return when Parcels last read Amazon's tracking of a shipment."""
    reads = [_read_at(data, oid) for oid in _tracking_of(shipment)]
    return max((at for at in reads if at is not None), default=None)


def _amazon_reads(data: ParcelsData) -> list[_Read]:
    """Return what the Parcel app last showed of each of Amazon's tracking."""
    reads: list[_Read] = []
    for parcel in data.parcels.values():
        for oid in _tracking_of(parcel):
            if (at := _read_at(data, oid)) is None:
                continue
            delivered, further = _tracking_marks(parcel, (oid,))
            latest = max(
                (
                    event.time
                    for event in parcel.events
                    if event.origin == oid and _exact(event) and event.time <= at
                ),
                default=None,
            )
            reads.append(_Read(at, delivered, tuple(further), latest))
    return reads


def _shown_elsewhere(box: Parcel, read: datetime, reads: list[_Read]) -> bool:
    """Return whether a read of the Parcel app would show a package's delivery.

    The Parcel app reads Amazon's tracking on the user's phone, when it can,
    so the time of a read proves nothing. Amazon's tracking read then or
    before does: a shipment delivered with the package, its times agreeing
    as :func:`_link_amazon_shipments` asks, or news at least
    ``AMAZON_CATCH_UP`` after the package came.
    """
    came = _real_delivery(box)
    if came is None:
        return False
    delivered, further = _box_evidence(box)
    for other in reads:
        if other.at > read:
            continue
        if other.latest is not None and other.latest >= came + AMAZON_CATCH_UP:
            return True
        if (
            other.delivered is not None
            and any(_agrees(other.delivered, own) for own in delivered)
            and any(_agrees(theirs, own) for theirs in other.further for own in further)
        ):
            return True
    return False


def boxes_of_day(
    data: ParcelsData, parcels: Iterable[Parcel], day: date
) -> dict[str, tuple[str, ...]]:
    """Return the packages that may hold each of a day's orders.

    An order here is a parcel of the day, delivered or not, of a known shop
    and without a carrier's number. A carrier's package that no shop's order
    names, apart from the Amazon shipments it carries, may hold it, see
    :func:`_box_may_hold`: shops pack orders together, so one package may
    hold several. Only the likeliest packages are kept, every one of them on
    a tie: the shop's, then the carrier's. An order that no package may
    hold, or with a problem, is left out.

    Amazon's tracking of a shipment, which the Parcel app follows, tells
    more before :func:`reconcile` links it. When packages repeat some of
    its times, but the van leaving, only those repeating the most may hold
    it, whatever their shop. Otherwise a delivered package may not while
    the shipment still isn't, once the Parcel app read with the shipment
    had shown that delivery: see :func:`_shown_elsewhere`.
    """
    apart = _apart_checker(data)
    today = [parcel for parcel in parcels if _of_day(parcel.state, day)]
    boxes = [parcel for parcel in today if _is_box(parcel)]
    covered: dict[str, tuple[str, ...]] = {}
    if not boxes:
        return covered
    reads: list[_Read] | None = None
    for order in today:
        state = order.state
        if state.tracking_number or state.status in _PROBLEMS or not _shop_keys(order):
            continue
        fits = [box for box in boxes if _box_may_hold(order, box, apart)]
        if fits and _is_shipment(order):
            marks = _amazon_marks(order)
            scores = {box.id: _agreement(marks, box) for box in fits}
            if top := max(scores.values()):
                covered[order.id] = tuple(
                    box.id for box in fits if scores[box.id] == top
                )
                continue
            read = _shipment_read(data, order)
            if (
                read is not None
                and marks[0] is None
                and state.status is not ParcelStatus.DELIVERED
            ):
                if reads is None:
                    reads = _amazon_reads(data)
                fits = [box for box in fits if not _shown_elsewhere(box, read, reads)]
        if fits:
            best = min(_box_rank(order, box) for box in fits)
            covered[order.id] = tuple(
                box.id for box in fits if _box_rank(order, box) == best
            )
    return covered


def _pair_by_reference(
    data: ParcelsData,
    pool: list[Parcel],
    apart: Callable[[Parcel, Parcel], bool],
    now: datetime,
    result: Reconciled,
) -> None:
    """Pair parcels known only by a shipment reference with tracked ones.

    Paack's e-mails may give only the part of its order ID before "_",
    which every package of the shipment shares. Such a parcel joins the
    only tracked parcel with that reference; with several, the user gets
    a suggestion for each.
    """
    holders: dict[ReferenceKey, list[Parcel]] = defaultdict(list)
    for parcel in data.parcels.values():
        if parcel.state.tracking_number and parcel.state.status not in (
            ParcelStatus.CANCELLED,
            ParcelStatus.RETURNED,
        ):
            for key in parcel_reference_keys(parcel):
                holders[key].append(parcel)
    for parcel in pool:
        if (
            parcel.id in result.removed
            or parcel.archived is not None
            or _tracked(parcel)
        ):
            continue
        found: dict[str, Parcel] = {}
        for key in parcel_reference_keys(parcel):
            for other in holders.get(key, ()):
                if (
                    other.id not in result.removed
                    and not _parcels_conflict(parcel, other)
                    and not apart(parcel, other)
                ):
                    found[other.id] = other
        if len(found) == 1:
            [target] = found.values()
            if _may_auto_merge(target, parcel) and _may_share_parcels(target, parcel):
                _auto_merge(data, target, parcel, REASON_SAME_REFERENCE, now, result)
                continue
        result.suggestions.extend(
            _suggestion(target, [parcel], None, REASON_SAME_REFERENCE)
            for target in sorted(found.values(), key=lambda p: (p.created, p.id))
            if target.archived is None
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
    _join_typed(data, apart, now, result)
    _absorb_by_domain(data, _reconcile_pool(data, start), apart, now, result)
    _pair_by_reference(data, _reconcile_pool(data, start), apart, now, result)
    undone = _undo_amazon_guesses(
        data, _reconcile_pool(data, start), apart, now, result
    )
    if undone:
        apart = _apart_checker(data)
    handled = _link_amazon_shipments(
        data, _reconcile_pool(data, start), apart, now, result, undone=undone
    )
    _pair_by_day(data, _reconcile_pool(data, start), apart, now, result, skip=handled)
    prune_held_guesses(data)
    _suggest_held(data, result)
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
    if _parcels_conflict(target, candidate, carried=True, numbers=True, typed=True):
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


def hand_delivery_events(parcel: Parcel) -> list[ParcelEvent]:
    """Return the user's events that alone make the parcel delivered.

    Marking a parcel delivered adds one, and so does keeping a delivery
    Parcels inferred; after a merge, the parcel merged in brings its own.
    When the carrier, the shop or another source reported the delivery too,
    before or after, the parcel was delivered without them: the list is
    empty, as it is for a parcel that isn't delivered.
    """
    state = parcel.state
    if state.status is not ParcelStatus.DELIVERED or state.inferred:
        return []
    own = [
        event
        for event in parcel.events
        if event.source is Source.MANUAL and event.status is ParcelStatus.DELIVERED
    ]
    if not own:
        return []
    ids = {event.id for event in own}
    without = derive_state(
        replace(
            parcel,
            events=[event for event in parcel.events if event.id not in ids],
            _state=None,
        )
    )
    if without.status is ParcelStatus.DELIVERED and not without.inferred:
        return []
    return own


def undo_delivery(data: ParcelsData, parcel_id: str, now: datetime) -> Parcel:
    """Take back a delivery the user marked or kept, or one Parcels inferred.

    Taking back the user's own brings back the news before it, which can be
    a delivery Parcels inferred: nothing stops a delivery from being marked,
    inferred or reported again. An inferred one taken back isn't inferred
    again. A delivery that was reported can't be taken back. When the
    user's mark was all that was left of the parcel, e.g. after its e-mails
    were removed, the parcel goes with it, as a parcel left without origins
    always does.
    """
    parcel = data.parcels[parcel_id]
    if own := hand_delivery_events(parcel):
        ids = {event.id for event in own}
        parcel.events = [event for event in parcel.events if event.id not in ids]
        # Marking it made the row of the user's edits when there was none.
        edits = manual_origin_id(parcel.id)
        origin = parcel.origins.get(edits)
        if (
            origin is not None
            and all(getattr(origin, key) is None for key in UPDATABLE_FIELDS)
            and not any(event.origin == edits for event in parcel.events)
        ):
            remove_origins(data, parcel, {edits}, now)
    elif any(event.inferred for event in parcel.events):
        parcel.events = [event for event in parcel.events if not event.inferred]
        parcel.delivery_rejected = True
    else:
        raise DedupError("no_delivery_to_undo")
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


def _drop_placeholder_items(data: ParcelsData, now: datetime) -> tuple[set[str], int]:
    """Drop the placeholders such as "item 1" that earlier versions kept as items.

    The local AI gave them for e-mails that list no items. What the user
    typed stays. Answers waiting in "Needs review" lose them too, with the
    note the checks now give; a fill that offered nothing else is dropped,
    as when the user dismisses it. Returns the changed parcel IDs and how
    many answers changed.
    """
    changed: set[str] = set()
    for parcel in data.parcels.values():
        for origin in parcel.origins.values():
            if origin.source is Source.MANUAL or not any(
                is_placeholder_item(item) for item in origin.items
            ):
                continue
            origin.items = tuple(i for i in origin.items if not is_placeholder_item(i))
            parcel.touch(now)
            changed.add(parcel.id)
    answers = 0
    for key, item in list(data.review.items()):
        suggestion = item.suggestion
        if suggestion is None or not any(
            is_placeholder_item(title) for title in suggestion.items
        ):
            continue
        answers += 1
        suggestion = replace(
            suggestion,
            items=tuple(i for i in suggestion.items if not is_placeholder_item(i)),
        )
        if item.fill and not (
            suggestion.eta_start
            or suggestion.items
            or suggestion.tracking_numbers
            or suggestion.carrier
        ):
            del data.review[key]
            continue
        item.suggestion = suggestion
        item.notes = check_codes((*item.notes, NOTE_ITEM_PLACEHOLDER))
    return changed, answers


def _forget_unproven_amazon_answers(data: ParcelsData) -> int:
    """Drop Amazon as the carrier of the local AI's answers under review.

    Amazon stays with one of its numbers. A kept answer gets the note the
    checks now give it, for administrators. A fill that offered nothing else
    is dropped, as when the user dismisses it. Returns how many answers
    changed.
    """
    changed = 0
    for key, item in list(data.review.items()):
        suggestion = item.suggestion
        if (
            item.source is not Source.AI
            or suggestion is None
            or suggestion.carrier != "amazon"
            or any(amazon_logistics_number(n) for n in suggestion.tracking_numbers)
        ):
            continue
        changed += 1
        suggestion = replace(suggestion, carrier=None)
        if item.fill and not (
            suggestion.eta_start or suggestion.items or suggestion.tracking_numbers
        ):
            del data.review[key]
            continue
        item.suggestion = suggestion
        item.notes = check_codes((*item.notes, NOTE_CARRIER_UNPROVEN))
    return changed


def repair_store(data: ParcelsData, now: datetime, since: int = 0) -> set[str]:
    """Fix what earlier versions stored; returns the changed parcel IDs.

    ``since`` is the repair version the store already had: the steps marked
    with a version run only for a store repaired before it.

    * Carrier brands in sender names become carriers, never merchants.
    * A shop's bare domain is replaced by its name from other e-mails.
    * (3) Amazon e-mails without a tracking number no longer claim that
      Amazon delivers: the carrier is unknown until a carrier's e-mail
      names it.
    * (4) Amazon is no longer the carrier that the local AI, the Parcel app
      or 17TRACK gave without one of its numbers, nor the carrier learned
      for a sender or offered by an answer waiting in "Needs review". What
      a parser read ("Amazon Logistics") and the user's edits stay.
    * (5) Placeholders such as "item 1" that the local AI gave as items are
      dropped, here and in answers waiting in "Needs review"; a fill that
      offered only them goes.
    * A shop's recommendations read as items are dropped.
    * Parcels of one order that are the same package are merged, undoably.
    * Orders are recorded again under the current order keys.
    * A carrier learned for a shop that ships with many carriers is forgotten.
    * A carrier's delivery and the shop's only parcel that could be it are
      merged, undoably, however old they are.

    The other steps can run again harmlessly. The fourth step's counts go to
    the engine state under ``AMAZON_REPAIR_KEY``, the fifth's under
    ``PLACEHOLDER_REPAIR_KEY``.
    """
    unproven = {"origins": 0, "senders": 0, "answers": 0}
    for domain, prefs in data.senders.items():
        if since < 4 and prefs.carrier == "amazon":
            prefs.carrier = None
            unproven["senders"] += 1
        elif prefs.carrier and ships_with_many(domain):
            prefs.carrier = None
    names = _merchant_names(_all_origins(data))
    changed: set[str] = set()
    for parcel in data.parcels.values():
        dirty = False
        for origin in parcel.origins.values():
            dirty |= _brand_carrier(origin)
            dirty |= _name_merchant(data, origin, names)
            if origin.carrier != "amazon":
                continue
            if (
                since < 3
                and origin.source in (Source.PARSER, Source.AI)
                and not origin.tracking_number
                and (info := lookup(origin.label)) is not None
                and info.parser == "amazon"
            ):
                origin.carrier = None
                dirty = True
            elif (
                since < 4
                and origin.source in _SAID_SOURCES
                and not amazon_logistics_number(origin.tracking_number)
            ):
                origin.carrier = None
                dirty = True
                unproven["origins"] += 1
        if dirty:
            parcel.touch(now)
            changed.add(parcel.id)
    if since < 4:
        unproven["answers"] = _forget_unproven_amazon_answers(data)
        data.engine[AMAZON_REPAIR_KEY] = unproven
    if since < 5:
        dropped, answers = _drop_placeholder_items(data, now)
        changed |= dropped
        data.engine[PLACEHOLDER_REPAIR_KEY] = {
            "parcels": len(dropped),
            "answers": answers,
        }
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


def fold_known_orders(data: ParcelsData, now: datetime) -> int:
    """Fold the parcels that late e-mails about known orders made.

    Releases before 0.1.16 made a parcel of an order's e-mail when the
    order's parcels were all archived. A parcel that only orders' e-mails
    made, and that the user left alone, joins the order's earlier parcel
    that such an e-mail joins now. That parcel stays as it was: archived,
    with the delivery Parcels inferred. Returns how many were folded.
    """
    apart = _apart_checker(data)
    folded = 0
    for parcel in sorted(data.parcels.values(), key=lambda p: (p.created, p.id)):
        if parcel.id not in data.parcels or not _order_mail_only(parcel):
            continue
        origins = list(parcel.origins.values())
        earlier = {
            other.id: other
            for key in parcel_order_keys(parcel)
            for other in order_parcels(data, key)
            if other.created < parcel.created
            and not apart(parcel, other)
            and (other.private or not parcel.private)
            and not any(_conflicts(other, origin) for origin in origins)
        }
        items = _item_keys(parcel.state.items)
        open_ = {pid: other for pid, other in earlier.items() if other.archived is None}
        target = _order_pick(data, open_, items) or _order_pick(data, earlier, items)
        if target is None:
            continue
        merge_parcels(
            data, target, [parcel.id], now, keep_archived=True, keep_inferred=True
        )
        folded += 1
    return folded


def restore_cancellations(
    data: ParcelsData, messages: Collection[str], now: datetime
) -> int:
    """Cancel the parcels whose cancellation was taken for a partial one.

    Releases before 0.1.18 judged whether an order had shipped by its
    parcel's status, which the local AI's reading of the order's own e-mail
    could give. A cancellation among the e-mails ``messages`` whose status
    was dropped cancels its parcel after all where it would now: see
    _takes_cancellation(). The e-mail stays on its parcel, and the order's
    other parcels stay as they are. Returns how many e-mails cancelled their
    parcel.
    """
    restored = 0
    for parcel in data.parcels.values():
        if parcel.archived is not None or not _takes_cancellation(parcel):
            continue
        dropped = [
            event
            for event in parcel.events
            if event.kind is MailKind.CANCELLED
            and event.status is None
            and (origin := parcel.origins.get(event.origin or "")) is not None
            and origin.message in messages
        ]
        if not dropped:
            continue
        for event in dropped:
            event.status = ParcelStatus.CANCELLED
        parcel.touch(now)
        restored += len({event.origin for event in dropped})
    return restored


def _order_mail_only(parcel: Parcel) -> bool:
    """Return True for a parcel that only orders' e-mails made.

    Not one that the user edited or confirmed, nor a guess Parcels flagged.
    """
    return (
        parcel.state.provisional
        and parcel.auto_merged is None
        and not parcel.delivery_rejected
        and bool(parcel.origins)
        and all(
            origin.message is not None
            and origin.source in (Source.PARSER, Source.AI)
            and not origin.confirmed
            for origin in parcel.origins.values()
        )
        and bool(parcel.events)
        and all(event.kind is MailKind.ORDER for event in parcel.events)
    )
