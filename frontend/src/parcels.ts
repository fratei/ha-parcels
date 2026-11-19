import { compareYmd, diffDays, isYmd, localDateOf, parseInstant } from "./dates.ts";
import { carrierLabel } from "./labels.ts";
import { isActiveStatus } from "./status.ts";
import type { MergeSuggestion, Parcel } from "./types.ts";

export interface DateRange {
  start: string;
  end: string;
}

/**
 * The expected delivery days of a parcel: eta_start..eta_end, a single day when
 * only one of them is set (or the end is before the start), null without an ETA.
 */
export function etaRange(parcel: Pick<Parcel, "eta_start" | "eta_end">): DateRange | null {
  const start = isYmd(parcel.eta_start) ? parcel.eta_start : null;
  const end = isYmd(parcel.eta_end) ? parcel.eta_end : null;
  const first = start ?? end;
  if (!first) {
    return null;
  }
  return { start: first, end: end && compareYmd(end, first) >= 0 ? end : first };
}

/** Not delivered, returned or cancelled. */
export function isActiveParcel(parcel: Pick<Parcel, "status">): boolean {
  return isActiveStatus(parcel.status);
}

function newestFirst(a: Parcel, b: Parcel): number {
  const timeA = parseInstant(a.status_time);
  const timeB = parseInstant(b.status_time);
  if (timeA !== timeB) {
    if (timeA === null) {
      return 1;
    }
    if (timeB === null) {
      return -1;
    }
    return timeB - timeA;
  }
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

/** Active, not archived parcels without an ETA, newest status first: the "No date yet" list. */
export function undatedParcels(parcels: readonly Parcel[]): Parcel[] {
  return parcels
    .filter((parcel) => isActiveParcel(parcel) && !parcel.archived && etaRange(parcel) === null)
    .sort(newestFirst);
}

/** Today and the server's time zone, to tell recent parcels from old ones. */
export interface DayContext {
  today: string;
  timeZone: string;
}

/** Parcels delivered or returned longer ago than this go behind "Show older". */
const RECENT_DAYS = 7;
/** The day distance of a parcel without any day. */
const NO_DAY = 9999;

export interface MergeCandidates {
  /** Open parcels and ones closed this week, likely matches first. */
  likely: Parcel[];
  /** Archived, cancelled and long-closed parcels, newest first. */
  older: Parcel[];
}

function orderKey(value: string): string {
  return value.replace(/[^0-9a-z]/gi, "").toUpperCase();
}

function sellerKey(parcel: Parcel): string {
  return parcel.merchant?.trim().toLowerCase() ?? "";
}

/** The days a parcel is about: its ETA, else the day its status last changed. */
function daysOf(parcel: Parcel, timeZone: string): { start: string; end: string } | null {
  const eta = etaRange(parcel);
  if (eta) {
    return eta;
  }
  const day = localDateOf(parcel.delivered_at ?? parcel.status_time, timeZone);
  return day ? { start: day, end: day } : null;
}

function dayDistance(a: Parcel, b: Parcel, timeZone: string): number {
  const first = daysOf(a, timeZone);
  const second = daysOf(b, timeZone);
  if (!first || !second) {
    return NO_DAY;
  }
  if (compareYmd(first.end, second.start) < 0) {
    return diffDays(first.end, second.start);
  }
  if (compareYmd(second.end, first.start) < 0) {
    return diffDays(second.end, first.start);
  }
  return 0;
}

/**
 * Orders candidates for merging with the given parcel: the same order first,
 * then the same shop, then the rest; open before closed; nearby days first.
 */
export function compareLikelihood(
  parcel: Parcel,
  { timeZone }: DayContext,
): (a: Parcel, b: Parcel) => number {
  const orders = new Set(parcel.order_numbers.map(orderKey).filter(Boolean));
  const seller = sellerKey(parcel);
  const tier = (candidate: Parcel): number => {
    if (candidate.order_numbers.some((number) => orders.has(orderKey(number)))) {
      return 0;
    }
    return seller && sellerKey(candidate) === seller ? 1 : 2;
  };
  return (a, b) =>
    tier(a) - tier(b) ||
    Number(!isActiveParcel(a)) - Number(!isActiveParcel(b)) ||
    dayDistance(parcel, a, timeZone) - dayDistance(parcel, b, timeZone) ||
    newestFirst(a, b);
}

/** Closed long enough ago, or put away, to be left out until asked for. */
function isOlder(parcel: Parcel, { today, timeZone }: DayContext): boolean {
  if (parcel.archived || parcel.status === "cancelled") {
    return true;
  }
  if (isActiveParcel(parcel)) {
    return false;
  }
  const day = localDateOf(parcel.delivered_at ?? parcel.status_time, timeZone);
  return day !== null && diffDays(day, today) > RECENT_DAYS;
}

/** The parcels the given one can be merged with: every other parcel the viewer may see. */
export function rankMergeCandidates(
  parcels: readonly Parcel[],
  parcel: Parcel,
  context: DayContext,
): MergeCandidates {
  const likely: Parcel[] = [];
  const older: Parcel[] = [];
  for (const candidate of parcels) {
    if (candidate.id === parcel.id || candidate.restricted) {
      continue;
    }
    (isOlder(candidate, context) ? older : likely).push(candidate);
  }
  likely.sort(compareLikelihood(parcel, context));
  older.sort(newestFirst);
  return { likely, older };
}

/** The parcels whose shop, items, order or tracking number, or carrier contain every word. */
export function searchCandidates(parcels: readonly Parcel[], query: string): Parcel[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) {
    return [...parcels];
  }
  return parcels.filter((parcel) => {
    const text = [
      parcel.merchant,
      carrierLabel(parcel),
      parcel.tracking_number,
      ...parcel.order_numbers,
      ...parcel.items,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return words.every((word) => text.includes(word));
  });
}

/** For each parcel a merge suggestion is about, the parcels it may be, each once. */
export function suggestedCandidates(
  suggestions: readonly MergeSuggestion[] | undefined,
): Map<string, Parcel[]> {
  const map = new Map<string, Parcel[]>();
  for (const suggestion of suggestions ?? []) {
    const list = map.get(suggestion.parcel.id) ?? [];
    for (const candidate of suggestion.candidates) {
      if (!list.some((parcel) => parcel.id === candidate.id)) {
        list.push(candidate);
      }
    }
    map.set(suggestion.parcel.id, list);
  }
  return map;
}

export interface PossibleMatch {
  suggestionId: string;
  /** The parcel the given one may be. */
  parcel: Parcel;
  /** The suggestion's candidate, as `suggestion/accept` and `suggestion/dismiss` take it. */
  candidateId: string;
}

/**
 * The parcels merge suggestions say the given one may be: a suggestion's
 * candidates when it's about this parcel, else the parcel a suggestion is
 * about when this one is among its candidates.
 */
export function possibleMatches(
  suggestions: readonly MergeSuggestion[] | undefined,
  parcelId: string,
): PossibleMatch[] {
  const matches: PossibleMatch[] = [];
  const seen = new Set<string>();
  const add = (suggestionId: string, parcel: Parcel, candidateId: string): void => {
    if (!seen.has(parcel.id)) {
      seen.add(parcel.id);
      matches.push({ suggestionId, parcel, candidateId });
    }
  };
  for (const suggestion of suggestions ?? []) {
    if (suggestion.parcel.id === parcelId) {
      for (const candidate of suggestion.candidates) {
        add(suggestion.id, candidate, candidate.id);
      }
    } else if (suggestion.candidates.some((candidate) => candidate.id === parcelId)) {
      add(suggestion.id, suggestion.parcel, parcelId);
    }
  }
  return matches;
}
