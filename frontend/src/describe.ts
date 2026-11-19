/**
 * Text shown on and announced for a parcel chip: its three lines (seller,
 * carrier line, items) and the full description used as the chip's accessible
 * name and tooltip.
 */
import { formatDate, formatDateRange, formatWindow, type LocaleOptions } from "./format.ts";
import { carrierLabel, statusLabel } from "./labels.ts";
import { localDateOf } from "./dates.ts";
import { etaRange, isActiveParcel } from "./parcels.ts";
import type { Placement } from "./placement.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { Parcel } from "./types.ts";

export interface ChipContext {
  locale: LocaleOptions;
  /** The number of packages in the box; 1 when the parcel is alone. */
  count?: number;
  /** Where the chip is in the calendar; absent in the list card. */
  placement?: Placement | null;
  continuesBefore?: boolean;
  continuesAfter?: boolean;
  /** "Possibly: …", when the items aren't known but may be a shop's parcel's. */
  possibly?: string | null;
}

export interface MetaOptions {
  locale: LocaleOptions;
  /** The number of packages in the box; 1 when the parcel is alone. */
  count?: number;
  placement?: Placement | null;
  /** Start with the status (the list card, which has no dates to show it). */
  showStatus?: boolean;
  /** Add the dates of a span over several days (the stacked layout). */
  showRange?: boolean;
}

/** A delivery window only matters while the parcel is still on its way. */
function windowText(parcel: Parcel, placement: Placement | null, locale: LocaleOptions): string | null {
  if (placement?.kind === "delivered" || placement?.kind === "returned") {
    return null;
  }
  return formatWindow(parcel.window_start, parcel.window_end, locale);
}

/** Whether to say the carrier isn't known yet: never for another user's private parcel. */
function carrierUnknown(parcel: Parcel): boolean {
  return !parcel.restricted && carrierLabel(parcel) === null;
}

function packagesText(count: number | undefined): string | null {
  return count !== undefined && count > 1 ? fmt(STRINGS.packages, { count: String(count) }) : null;
}

/** The first line of a chip: the shop, never the carrier or a tracking number. */
export function sellerLine(parcel: Parcel): string {
  if (parcel.restricted) {
    return STRINGS.privateParcel;
  }
  return clean(parcel.merchant) ?? STRINGS.unknownSeller;
}

/** "PIN 4711" while the list has the parcel's delivery PIN or pickup code. */
export function chipPin(parcel: Parcel): string | null {
  if (parcel.restricted) {
    return null;
  }
  const code = clean(parcel.pickup_code);
  return code ? fmt(STRINGS.pin, { code }) : null;
}

/**
 * The second line of a chip, e.g. "DPD · 4 packages · 13:00–14:00". The
 * carrier is the one delivering, never the shop; until an e-mail names it,
 * "Carrier not known yet" comes last, after the window. The PIN is shown
 * apart, at the end of the line (see chipPin).
 */
export function chipMeta(parcel: Parcel, options: MetaOptions): string {
  const placement = options.placement ?? null;
  const parts: string[] = [];
  const carrier = carrierLabel(parcel);
  if (carrier) {
    parts.push(carrier);
  }
  if (options.showStatus) {
    const status = statusLabel(parcel.status);
    if (status) {
      parts.push(status);
    }
  }
  const packages = packagesText(options.count);
  if (packages) {
    parts.push(packages);
  }
  if (options.showRange && placement && placement.from !== placement.to) {
    parts.push(formatDateRange(placement.from, placement.to, options.locale));
  }
  const window = windowText(parcel, placement, options.locale);
  if (window) {
    parts.push(window);
  }
  if (carrierUnknown(parcel)) {
    parts.push(STRINGS.carrierNotKnown);
  }
  return parts.join(" · ");
}

const QUANTITY = /^\d{1,3}\s*[x×]\s+/i;
const NAME_END = /\s*(?:[,;(|[]|\s[-–—]\s)/;
const MAX_NAMES = 8;

function clean(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const text = value.replace(/\s+/g, " ").trim();
  return text ? text : null;
}

/** An item's name without a leading "2 x" or anything after a comma or bracket. */
function itemName(item: string): string {
  const name = item.replace(QUANTITY, "");
  const end = name.search(NAME_END);
  return (end > 0 ? name.slice(0, end) : name).trim() || item;
}

/** Up to three words and about 24 characters, e.g. "Lumen desk lamp". */
function shortName(item: string): string {
  const words = itemName(item).split(" ").slice(0, 3);
  while (words.length > 1 && words.join(" ").length > 24) {
    words.pop();
  }
  return words.join(" ");
}

/** The first word, or two when the first is very short, e.g. "Zeta" or "AA batteries". */
function firstWords(item: string): string {
  const words = itemName(item).split(" ");
  const first = words[0] ?? item;
  return first.length < 4 && words.length > 1 ? `${first} ${words[1]}` : first;
}

/**
 * The third line of a chip: one item in full, else the count and short names,
 * e.g. "4 items · Zeta, Brava, AA batteries, Brava". Null when no item is
 * known or the parcel is someone else's private one.
 */
export function itemsSummary(parcel: Pick<Parcel, "restricted" | "items">): string | null {
  if (parcel.restricted) {
    return null;
  }
  const items = (parcel.items ?? []).map(clean).filter((item): item is string => item !== null);
  if (items.length === 0) {
    return null;
  }
  if (items.length === 1) {
    return items[0] ?? null;
  }
  const names = items.map(items.length === 2 ? shortName : firstWords);
  const shown = names.slice(0, MAX_NAMES);
  if (names.length > MAX_NAMES) {
    shown.push("…");
  }
  return `${fmt(STRINGS.itemsCount, { count: String(items.length) })} · ${shown.join(", ")}`;
}

/** A candidate's first item, short, with the count of the others, e.g. "Lumen lamp +2". */
function firstItem(parcel: Parcel): string | null {
  const items = (parcel.items ?? []).map(clean).filter((item): item is string => item !== null);
  const first = items[0];
  if (parcel.restricted || first === undefined) {
    return null;
  }
  const name = shortName(first);
  return items.length > 1 ? fmt(STRINGS.itemsMore, { name, count: String(items.length - 1) }) : name;
}

/**
 * The third line of a box that may be a shop's parcel its carrier's e-mails
 * don't name: "Possibly: 2 items · Lumen lamp, Brava bin", or with several
 * candidates "Possibly: Lumen lamp or Brava bin +1". Null when no
 * candidate's items are known.
 */
export function possiblyLine(candidates: readonly Parcel[]): string | null {
  const only = candidates.length === 1 ? candidates[0] : undefined;
  if (only !== undefined) {
    const items = itemsSummary(only);
    return items ? fmt(STRINGS.possibly, { items }) : null;
  }
  const names = [
    ...new Set(candidates.map(firstItem).filter((name): name is string => name !== null)),
  ];
  return names.length ? fmt(STRINGS.possibly, { items: names.join(STRINGS.possiblyOr) }) : null;
}

/**
 * Everything a chip shows, as one sentence for screen readers and the tooltip,
 * e.g. "Example Shop, carrier DPD, In transit, expected Tue 14 Jul,
 * 13:00–14:00, 2 items · Lumen lamp, Brava bin, PIN 4711, private".
 */
export function describeParcel(parcel: Parcel, context: ChipContext): string {
  const { locale } = context;
  const placement = context.placement ?? null;
  const parts: string[] = [sellerLine(parcel)];
  const packages = packagesText(context.count);
  if (packages) {
    parts.push(packages);
  }
  const carrier = carrierLabel(parcel);
  if (carrier) {
    parts.push(fmt(STRINGS.carrierIs, { carrier }));
  } else if (carrierUnknown(parcel)) {
    parts.push(STRINGS.carrierNotKnownLabel);
  }
  const status = statusLabel(parcel.status);
  const day = placement ? formatDate(placement.from, locale) : "";
  switch (placement?.kind) {
    case "delivered":
      parts.push(fmt(STRINGS.deliveredOn, { date: day }));
      break;
    case "returned":
      parts.push(fmt(STRINGS.returnedOn, { date: day }));
      break;
    case "pickup":
      parts.push(fmt(STRINGS.readyForPickupSince, { date: day }));
      break;
    case "status":
      parts.push(fmt(STRINGS.statusOn, { status, date: day }));
      break;
    case "eta":
      if (status) {
        parts.push(status);
      }
      parts.push(
        fmt(STRINGS.expectedOn, { date: formatDateRange(placement.from, placement.to, locale) }),
      );
      break;
    default:
      if (status) {
        parts.push(status);
      }
      break;
  }
  const window = windowText(parcel, placement, locale);
  if (window) {
    parts.push(window);
  }
  const items = itemsSummary(parcel);
  if (items) {
    parts.push(items);
  } else if (context.possibly && !parcel.restricted) {
    parts.push(context.possibly);
  }
  if (!parcel.restricted) {
    if (parcel.ai) {
      parts.push(STRINGS.aiBadgeLabel);
    } else if (parcel.ai_filled) {
      parts.push(STRINGS.aiFilledLabel);
    }
    if (parcel.auto_merged) {
      parts.push(STRINGS.autoMergedLabel);
    }
    if (parcel.inferred) {
      parts.push(STRINGS.inferredLabel);
    }
    const pin = chipPin(parcel);
    if (pin) {
      parts.push(pin);
    } else if (parcel.has_code) {
      parts.push(STRINGS.hasCode);
    }
  }
  if (parcel.private || parcel.restricted) {
    parts.push(STRINGS.privateLabel);
  }
  if (context.continuesBefore) {
    parts.push(STRINGS.continuesBefore);
  }
  if (context.continuesAfter) {
    parts.push(STRINGS.continuesAfter);
  }
  return parts.join(", ");
}

/** "…12345": the last five letters or digits of a long tracking or order number. */
export function numberTail(value: string | null | undefined): string | null {
  const text = value?.trim();
  if (!text) {
    return null;
  }
  return text.length <= 6 ? text : `…${text.replace(/[^0-9a-z]/gi, "").slice(-5)}`;
}

export interface CandidateLines {
  /** The shop. */
  title: string;
  /** The status, with the day it arrived or the expected days. */
  when: string;
  /** The carrier with the tails of the tracking and order numbers. */
  carrier: string;
  /** The items summary; null when the items aren't known. */
  items: string | null;
}

/** What tells one parcel from another in the merge picker and merge suggestions. */
export function candidateLines(parcel: Parcel, locale: LocaleOptions): CandidateLines {
  let days: string | null = null;
  if (isActiveParcel(parcel)) {
    const eta = etaRange(parcel);
    days = eta ? formatDateRange(eta.start, eta.end, locale) : null;
  } else {
    const timeZone = locale.timeZone ?? Intl.DateTimeFormat().resolvedOptions().timeZone;
    const day = localDateOf(parcel.delivered_at ?? parcel.status_time, timeZone);
    days = day ? formatDateRange(day, day, locale) : null;
  }
  const carrier = [carrierLabel(parcel) ?? STRINGS.carrierNotKnown];
  const number = numberTail(parcel.tracking_number);
  if (number) {
    carrier.push(fmt(STRINGS.numberTail, { tail: number }));
  }
  const order = numberTail(parcel.order_numbers[0]);
  if (order) {
    carrier.push(fmt(STRINGS.orderTail, { tail: order }));
  }
  return {
    title: sellerLine(parcel),
    when: [statusLabel(parcel.status), days].filter(Boolean).join(" · "),
    carrier: carrier.join(" · "),
    items: itemsSummary(parcel),
  };
}

/** The candidate on one line, for its accessible name and the merge suggestion's button. */
export function candidateLabel(parcel: Parcel, locale: LocaleOptions): string {
  const lines = candidateLines(parcel, locale);
  return [lines.title, lines.items, lines.carrier, lines.when].filter(Boolean).join(" · ");
}
