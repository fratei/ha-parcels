import { compareYmd, diffDays, isYmd, localDateOf, parseInstant } from "./dates.ts";
import { carrierLabel } from "./labels.ts";
import { isActiveStatus } from "./status.ts";
import { STRINGS } from "./strings.ts";
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

/** Delivered on a known day, not just inferred from another parcel. */
function deliveredDay(parcel: Parcel, timeZone: string): string | null {
  const unknown = parcel.delivered_undated && !parcel.delivered_timeless;
  if (parcel.status !== "delivered" || parcel.inferred || unknown) {
    return null;
  }
  return localDateOf(parcel.delivered_at, timeZone);
}

/** The days a parcel is about: the day it was delivered, else its ETA, else the day its status last changed. */
function daysOf(parcel: Parcel, timeZone: string): { start: string; end: string } | null {
  const delivered = deliveredDay(parcel, timeZone);
  if (delivered) {
    return { start: delivered, end: delivered };
  }
  const eta = etaRange(parcel);
  if (eta) {
    return eta;
  }
  const day = localDateOf(parcel.delivered_at ?? parcel.status_time, timeZone);
  return day ? { start: day, end: day } : null;
}

/**
 * Whether one of the two was delivered on a day before the other was
 * shipped (or ordered), so it can't have held it.
 */
function deliveredBeforeSent(a: Parcel, b: Parcel, timeZone: string): boolean {
  const before = (box: Parcel, other: Parcel): boolean => {
    const delivered = deliveredDay(box, timeZone);
    const sent = localDateOf(other.shipped_at ?? other.ordered_at, timeZone);
    return delivered !== null && sent !== null && compareYmd(delivered, sent) < 0;
  };
  return before(a, b) || before(b, a);
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

/**
 * The parcels the given one can be merged with: every other parcel the viewer
 * may see. Ones delivered before the other was shipped go behind "Show older".
 */
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
    const old =
      isOlder(candidate, context) || deliveredBeforeSent(parcel, candidate, context.timeZone);
    (old ? older : likely).push(candidate);
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
  /** Why the suggestion was made, e.g. "same_merchant_day". */
  reason: string;
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
  const add = (suggestion: MergeSuggestion, parcel: Parcel, candidateId: string): void => {
    if (!seen.has(parcel.id)) {
      seen.add(parcel.id);
      matches.push({ suggestionId: suggestion.id, parcel, candidateId, reason: suggestion.reason });
    }
  };
  for (const suggestion of suggestions ?? []) {
    if (suggestion.parcel.id === parcelId) {
      for (const candidate of suggestion.candidates) {
        add(suggestion, candidate, candidate.id);
      }
    } else if (suggestion.candidates.some((candidate) => candidate.id === parcelId)) {
      add(suggestion, suggestion.parcel, parcelId);
    }
  }
  return matches;
}

/**
 * The possible matches nearest to the parcel's day first, without the ones
 * delivered before the other was shipped.
 */
export function rankPossible(
  parcel: Parcel,
  matches: readonly PossibleMatch[],
  { timeZone }: DayContext,
): PossibleMatch[] {
  const distance = (match: PossibleMatch): number => dayDistance(parcel, match.parcel, timeZone);
  return matches
    .filter((match) => !deliveredBeforeSent(parcel, match.parcel, timeZone))
    .sort((a, b) => distance(a) - distance(b) || newestFirst(a.parcel, b.parcel));
}

/**
 * The other parcels with known items or orders that a possible match of the
 * given parcel may also be, to rule them out: still open or delivered, not
 * put away.
 */
export function alsoPossible(
  suggestions: readonly MergeSuggestion[] | undefined,
  matchId: string,
  parcelId: string,
): Parcel[] {
  return possibleMatches(suggestions, matchId)
    .map((match) => match.parcel)
    .filter(
      (other) =>
        other.id !== parcelId &&
        !other.archived &&
        !other.restricted &&
        other.status !== "cancelled" &&
        other.status !== "returned" &&
        (other.items.length > 0 || other.order_numbers.length > 0),
    );
}

/** Why the possible matches of a parcel aren't merged yet, from its side of the suggestions. */
export function possibleHint(matches: readonly PossibleMatch[]): string {
  const many = matches.length > 1;
  // Suggestions are about a tracked delivery; their candidates are what it may have brought.
  const delivery = matches.some((match) => match.candidateId === match.parcel.id);
  if (matches.length && matches.every((match) => match.reason === "same_reference")) {
    if (delivery) {
      return STRINGS.possibleHintShipment;
    }
    return many ? STRINGS.possibleHintStemMany : STRINGS.possibleHintStemOne;
  }
  if (delivery) {
    return many ? STRINGS.possibleHintDeliveryMany : STRINGS.possibleHintDeliveryOne;
  }
  return many ? STRINGS.possibleHintOrderMany : STRINGS.possibleHintOrderOne;
}
