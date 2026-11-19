/**
 * Packages of one shipment shown as one box. The integration gives packages
 * sent together the same `shipment_group`; the cards put those with the same
 * status on the same days in one box, so packages delivered on different days
 * never share one.
 */
import type { Parcel } from "./types.ts";

/** Splits items into boxes: items with the same non-null key share one, in first-seen order. */
export function groupItems<T>(items: readonly T[], key: (item: T) => string | null): T[][] {
  const boxes: T[][] = [];
  const byKey = new Map<string, T[]>();
  for (const item of items) {
    const boxKey = key(item);
    const box = boxKey === null ? undefined : byKey.get(boxKey);
    if (box) {
      box.push(item);
      continue;
    }
    const created = [item];
    boxes.push(created);
    if (boxKey !== null) {
      byKey.set(boxKey, created);
    }
  }
  return boxes;
}

/** A parcel's box: its shipment, status and the extra parts; null when it's shown alone. */
export function shipmentKey(parcel: Parcel, ...parts: readonly string[]): string | null {
  if (parcel.restricted || parcel.shipment_group === null) {
    return null;
  }
  return JSON.stringify([parcel.shipment_group, parcel.status, ...parts]);
}

/** Orders parcels by ID; the first one of a box stands for the box. */
export function byId(a: Pick<Parcel, "id">, b: Pick<Parcel, "id">): number {
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

/** A box in a card: the parcel that stands for it and its packages, by ID. */
export interface ShipmentBox {
  parcel: Parcel;
  members: Parcel[];
}

/** Parcels without dates in boxes: one per shipment and status, in the parcels' order. */
export function shipmentBoxes(parcels: readonly Parcel[]): ShipmentBox[] {
  return groupItems(parcels, (parcel) => shipmentKey(parcel)).map((box) => {
    const members = [...box].sort(byId);
    return { parcel: box.reduce((min, parcel) => (byId(parcel, min) < 0 ? parcel : min)), members };
  });
}

function earliest(values: readonly (string | null)[]): string | null {
  return values.reduce<string | null>(
    (first, value) => (value !== null && (first === null || value < first) ? value : first),
    null,
  );
}

function latest(values: readonly (string | null)[]): string | null {
  return values.reduce<string | null>(
    (last, value) => (value !== null && (last === null || value > last) ? value : last),
    null,
  );
}

/**
 * What a box of packages shows: the parcel that stands for it, with the time
 * window covering every package's, and the AI badge, the lock, the PIN hint and
 * the auto-merge and inferred-delivery flags when any package has them.
 */
export function boxParcel(parcel: Parcel, members: readonly Parcel[]): Parcel {
  if (members.length < 2) {
    return parcel;
  }
  return {
    ...parcel,
    window_start: earliest(members.map((member) => member.window_start)),
    window_end: latest(members.map((member) => member.window_end)),
    ai: members.some((member) => member.ai),
    ai_filled: members.some((member) => member.ai_filled),
    private: members.some((member) => member.private),
    has_code: members.some((member) => member.has_code),
    pickup_code: boxCodes(members),
    items: boxItems(parcel, members),
    auto_merged: members.find((member) => member.auto_merged)?.auto_merged ?? null,
    inferred: members.some((member) => member.inferred),
  };
}

/** The packages' different PINs, e.g. "4711, 0815", or null when none has one. */
function boxCodes(members: readonly Parcel[]): string | null {
  const codes = new Set<string>();
  for (const member of members) {
    const code = member.pickup_code?.trim();
    if (code) {
      codes.add(code);
    }
  }
  return codes.size > 0 ? [...codes].join(", ") : null;
}

/** The shown package's items, then those only the other packages have. */
function boxItems(parcel: Parcel, members: readonly Parcel[]): string[] {
  const items = [...parcel.items];
  const seen = new Set(items);
  for (const member of members) {
    for (const item of member.items) {
      if (!seen.has(item)) {
        seen.add(item);
        items.push(item);
      }
    }
  }
  return items;
}

/** The visible packages of a parcel's shipment, by tracking number; empty when it's alone. */
export function shipmentPackages(parcels: readonly Parcel[], parcel: Parcel): Parcel[] {
  const group = parcel.shipment_group;
  if (group === null || parcel.restricted) {
    return [];
  }
  const packages = parcels
    .filter((other) => other.shipment_group === group && !other.restricted)
    .sort(
      (a, b) =>
        (a.tracking_number ?? "").localeCompare(b.tracking_number ?? "", "en", { numeric: true }) ||
        byId(a, b),
    );
  return packages.length > 1 ? packages : [];
}
