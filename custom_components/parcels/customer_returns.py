"""Customer returns: parcels the user sends back to a shop.

A shop's return e-mails make a return entry, which the page shows on its
pickup day: the date the e-mail gives, the working day after an e-mail that
says "next working day", or, for shops whose carrier collects returns on the
next working day (Amazon), the working day after the e-mail. E-mails about the
same return join one entry: they share an order and an item, or, without
order numbers, the shop and an item.

A return never changes its order's parcels, with one exception: a parcel can
only be sent back once it arrived. When a return names an order whose parcel
is still on its way, that parcel gets an inferred delivery the user can undo
(see :func:`infer_return_deliveries`).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import date, datetime, timedelta

from homeassistant.util import dt as dt_util

from .const import MailKind, ParcelStatus
from .dedup import parcel_order_keys
from .models import (
    MAX_ITEMS,
    Parcel,
    ParcelEvent,
    ParcelsData,
    PickupRule,
    ReturnEntry,
    ReturnOrigin,
    Source,
    Suggestion,
    local_date,
    merchant_key,
    new_id,
    order_key,
)
from .parsers.base import ParseResult
from .parsers.items import item_key, same_key, unique_items
from .parsers.returns import NOTE_PICKUP_NEXT_WORKING_DAY, NOTE_RETURN_RECEIVED

# E-mails about one return come within days of each other; the shop's
# "return received" e-mail can come weeks after the first.
JOIN_DAYS = timedelta(days=7)
RECEIVED_DAYS = timedelta(days=45)
# Shops whose carrier collects a return on the working day after its e-mail.
NEXT_DAY_PICKUP_SHOPS = frozenset({"amazon"})
# The label of a delivery inferred from a return of the parcel's order.
INFERRED_RETURN = "return"
# An inferred delivery goes at noon of the parcel's last expected day.
_NOON = 12


def return_origin(
    result: ParseResult,
    *,
    message_hash: str,
    time: datetime,
    source: Source,
    label: str,
    owners: Iterable[str],
    next_working_day: Callable[[date], date],
) -> ReturnOrigin:
    """Return what a customer-return e-mail says about the return."""
    shipment = result.shipments[0] if result.shipments else None
    received = NOTE_RETURN_RECEIVED in result.notes
    pickup: date | None = None
    rule: PickupRule | None = None
    if shipment is not None and shipment.eta is not None:
        pickup, rule = shipment.eta.start, PickupRule.EMAIL
    elif NOTE_PICKUP_NEXT_WORKING_DAY in result.notes:
        pickup = next_working_day(local_date(time))
        rule = PickupRule.NEXT_WORKING_DAY
    elif not received and merchant_key(result.merchant or label) in (
        NEXT_DAY_PICKUP_SHOPS
    ):
        pickup, rule = next_working_day(local_date(time)), PickupRule.ASSUMED
    orders = list(result.order_numbers)
    items = list(result.items)
    if shipment is not None:
        orders.extend(shipment.order_numbers)
        items.extend(shipment.items)
    return ReturnOrigin(
        message=message_hash,
        time=time,
        source=source,
        label=label,
        merchant=result.merchant or None,
        order_numbers=tuple(dict.fromkeys(orders)),
        items=tuple(unique_items(items)[:MAX_ITEMS]),
        carrier=shipment.carrier if shipment is not None else None,
        tracking_number=shipment.tracking_number if shipment is not None else None,
        pickup=pickup,
        pickup_rule=rule,
        received=received,
        owners=tuple(sorted({owner for owner in owners if owner})),
    )


def pickup_suggestion(
    suggestion: Suggestion | None,
    result: ParseResult,
    *,
    time: datetime,
    next_working_day: Callable[[date], date],
) -> Suggestion | None:
    """Give a return's "Needs review" suggestion its "next working day" pickup.

    A suggestion only holds dates: without it, accepting would lose the day.
    """
    if (
        suggestion is None
        or suggestion.eta_start is not None
        or NOTE_PICKUP_NEXT_WORKING_DAY not in result.notes
    ):
        return suggestion
    day = next_working_day(local_date(time))
    return replace(suggestion, eta_start=day, eta_end=day)


def _origin_order_keys(origin: ReturnOrigin) -> set[str]:
    merchant = origin.merchant or origin.label
    return {
        key for number in origin.order_numbers if (key := order_key(merchant, number))
    }


def return_order_keys(entry: ReturnEntry) -> set[str]:
    """Return the keys of the orders a return belongs to."""
    keys: set[str] = set()
    for origin in entry.origins.values():
        keys |= _origin_order_keys(origin)
    return keys


def _shop(origin: ReturnOrigin) -> str:
    return merchant_key(origin.merchant or origin.label)


def _share_item(first: Iterable[str], second: Iterable[str]) -> bool:
    one = {key for item in first if (key := item_key(item))}
    two = {key for item in second if (key := item_key(item))}
    return any(same_key(key, other) for key in one for other in two)


def _same_return(entry: ReturnEntry, origin: ReturnOrigin) -> bool:
    """Return True when an e-mail is about the return of ``entry``.

    With order numbers on both sides, they must share an order and, when
    both list items, an item: one order can be sent back in parts. Otherwise
    it takes the same shop and an item in common.
    """
    keys, entry_keys = _origin_order_keys(origin), return_order_keys(entry)
    items = entry.items
    if keys and entry_keys:
        if keys.isdisjoint(entry_keys):
            return False
        return not (origin.items and items) or _share_item(origin.items, items)
    shop = _shop(origin)
    return (
        bool(shop)
        and any(_shop(other) == shop for other in entry.origins.values())
        and _share_item(origin.items, items)
    )


def _in_time(entry: ReturnEntry, origin: ReturnOrigin) -> bool:
    """Return True when an e-mail's time fits the return of ``entry``.

    The shop's "received" e-mail follows the first e-mails; any other
    e-mail comes within days of them, and never after the shop had the
    parcel back.
    """
    if origin.received:
        return entry.started <= origin.time <= entry.started + RECEIVED_DAYS
    if any(o.received and o.time <= origin.time for o in entry.origins.values()):
        return False
    return abs(origin.time - entry.started) <= JOIN_DAYS


def apply_return(data: ParcelsData, origin: ReturnOrigin, now: datetime) -> ReturnEntry:
    """Add what an e-mail says to its return, or start one; return the entry.

    The same e-mail again (from another mailbox) only adds its owners. Of
    several returns the e-mail fits, it joins one not yet received, then
    the one that started closest to it.
    """
    for entry in data.returns.values():
        if (known := entry.origins.get(origin.message)) is not None:
            origin.owners = tuple(sorted({*known.owners, *origin.owners}))
            entry.origins[origin.message] = origin
            entry.updated = now
            return entry
    entry = min(
        (
            entry
            for entry in data.returns.values()
            if _in_time(entry, origin) and _same_return(entry, origin)
        ),
        key=lambda e: (e.received, abs(e.started - origin.time), e.id),
        default=None,
    )
    if entry is None:
        entry = ReturnEntry(id=new_id("ret"), created=now, updated=now)
        data.returns[entry.id] = entry
    entry.origins[origin.message] = origin
    entry.updated = now
    if (
        entry.archived is not None
        and not origin.received
        and not entry.done(local_date(now))
    ):
        entry.archived = None
    return entry


def order_index(data: ParcelsData) -> dict[str, list[Parcel]]:
    """Return the parcels of each order, by order key."""
    index: dict[str, list[Parcel]] = defaultdict(list)
    for parcel in data.parcels.values():
        for key in parcel_order_keys(parcel):
            index[key].append(parcel)
    return index


def linked_parcels(
    entry: ReturnEntry, index: Mapping[str, list[Parcel]]
) -> list[Parcel]:
    """Return the parcels of the orders a return belongs to."""
    found: dict[str, Parcel] = {}
    for key in sorted(return_order_keys(entry)):
        for parcel in index.get(key, ()):
            found.setdefault(parcel.id, parcel)
    return list(found.values())


def _returned_parcel(parcels: list[Parcel], entry: ReturnEntry) -> Parcel | None:
    """Return the order's parcel that was sent back: the only one, or the only
    one with an item of the return."""
    if len(parcels) == 1:
        return parcels[0]
    items = entry.items
    holding = [parcel for parcel in parcels if _share_item(parcel.state.items, items)]
    return holding[0] if len(holding) == 1 else None


def _delivery_time(parcel: Parcel, started: datetime) -> datetime:
    """Return when a parcel that was sent back arrived, at the latest.

    That's noon of its last expected day, or the parcel's last news if
    later, but never after the return started.
    """
    when = started
    if (eta := parcel.state.eta) is not None:
        when = min(when, dt_util.start_of_local_day(eta.end).replace(hour=_NOON))
    last = max((event.time for event in parcel.events), default=None)
    if last is not None and last > when:
        when = min(last, started)
    return when


def infer_return_deliveries(data: ParcelsData, now: datetime) -> set[str]:
    """Mark the parcels that were sent back as delivered.

    The return's order must have one parcel, or one with an item of the
    return. When it's still on its way, it gets an inferred delivery,
    unless the user undid one before. Returns the IDs of the changed parcels.
    """
    if not data.returns:
        return set()
    index = order_index(data)
    changed: set[str] = set()
    for entry in sorted(data.returns.values(), key=lambda e: (e.started, e.id)):
        parcel = _returned_parcel(linked_parcels(entry, index), entry)
        if (
            parcel is None
            or parcel.state.terminal
            or parcel.delivery_rejected
            or any(event.inferred for event in parcel.events)
        ):
            continue
        parcel.events.append(
            ParcelEvent(
                time=_delivery_time(parcel, entry.started),
                source=Source.PARSER,
                status=ParcelStatus.DELIVERED,
                kind=MailKind.DELIVERED,
                label=INFERRED_RETURN,
                inferred=True,
            )
        )
        parcel.touch(now)
        changed.add(parcel.id)
    return changed


def _inferred_by_return(event: ParcelEvent) -> bool:
    return event.inferred and event.label == INFERRED_RETURN


def remove_return(data: ParcelsData, entry_id: str, now: datetime) -> ReturnEntry:
    """Remove a return, and the deliveries only it inferred; return it.

    Raises KeyError for an unknown return.
    """
    entry = data.returns.pop(entry_id)
    index = order_index(data)
    still_returned = {
        parcel.id
        for other in data.returns.values()
        if (parcel := _returned_parcel(linked_parcels(other, index), other)) is not None
    }
    for parcel in linked_parcels(entry, index):
        if parcel.id in still_returned or not any(
            _inferred_by_return(event) for event in parcel.events
        ):
            continue
        parcel.events = [
            event for event in parcel.events if not _inferred_by_return(event)
        ]
        parcel.touch(now)
        if parcel.archived is not None and not parcel.state.terminal:
            parcel.archived = None
    return entry
