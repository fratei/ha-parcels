/**
 * The parcel filter of the week and list cards: All, Active, Recent (changed or
 * expected this week) or Completed. The choice is kept on the device and
 * shared by the cards on the page.
 */
import { addDays, compareYmd, localDateOf, startOfWeek } from "./dates.ts";
import { etaRange } from "./parcels.ts";
import { isActiveStatus } from "./status.ts";
import { STRINGS } from "./strings.ts";
import type { Parcel } from "./types.ts";

export const PARCEL_FILTERS = ["all", "active", "recent", "completed"] as const;
export type ParcelFilter = (typeof PARCEL_FILTERS)[number];

export const FILTER_LABELS: Readonly<Record<ParcelFilter, string>> = {
  all: STRINGS.filterAll,
  active: STRINGS.filterActive,
  recent: STRINGS.filterRecent,
  completed: STRINGS.filterCompleted,
};

export const FILTER_KEY = "parcels-filter";
/** Sent on the window when the choice changes, so every card on the page follows it. */
export const FILTER_EVENT = "parcels-filter-changed";

export interface FilterContext {
  /** Today where the user is, "YYYY-MM-DD"; Recent is about this day's week. */
  today: string;
  timeZone: string;
}

export interface FilterStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function isParcelFilter(value: unknown): value is ParcelFilter {
  return typeof value === "string" && (PARCEL_FILTERS as readonly string[]).includes(value);
}

function deviceStorage(): FilterStorage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

/** The filter chosen on this device; All when none was chosen or storage is blocked. */
export function readFilter(storage: FilterStorage | null = deviceStorage()): ParcelFilter {
  try {
    const value = storage?.getItem(FILTER_KEY);
    return isParcelFilter(value) ? value : "all";
  } catch {
    return "all";
  }
}

/** Keeps the choice on this device and tells the other cards on the page. */
export function saveFilter(
  filter: ParcelFilter,
  storage: FilterStorage | null = deviceStorage(),
  target: EventTarget | null = globalThis.window ?? null,
): void {
  try {
    storage?.setItem(FILTER_KEY, filter);
  } catch {
    // Blocked or full storage: the choice lasts until the page reloads.
  }
  target?.dispatchEvent(new CustomEvent(FILTER_EVENT, { detail: filter }));
}

/** Changed (status or delivery) or expected during the current Monday-to-Sunday week. */
function isRecent(parcel: Parcel, { today, timeZone }: FilterContext): boolean {
  const monday = startOfWeek(today);
  const sunday = addDays(monday, 6);
  const inWeek = (day: string | null): boolean =>
    day !== null && compareYmd(day, monday) >= 0 && compareYmd(day, sunday) <= 0;
  if (inWeek(localDateOf(parcel.status_time, timeZone)) || inWeek(localDateOf(parcel.delivered_at, timeZone))) {
    return true;
  }
  const eta = etaRange(parcel);
  return eta !== null && compareYmd(eta.start, sunday) <= 0 && compareYmd(eta.end, monday) >= 0;
}

/**
 * Whether a parcel shows under a filter. Active parcels are on their way;
 * Completed ones were delivered (inferred deliveries too), returned or
 * cancelled.
 */
export function matchesFilter(parcel: Parcel, filter: ParcelFilter, context: FilterContext): boolean {
  switch (filter) {
    case "active":
      return isActiveStatus(parcel.status);
    case "completed":
      return !isActiveStatus(parcel.status);
    case "recent":
      return isRecent(parcel, context);
    default:
      return true;
  }
}
