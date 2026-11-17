import { compareYmd, isYmd, parseInstant } from "./dates.ts";
import { isActiveStatus } from "./status.ts";
import type { Parcel } from "./types.ts";

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

/** Parcels the given one can be merged with: other active, visible, not archived parcels. */
export function mergeCandidates(parcels: readonly Parcel[], parcelId: string): Parcel[] {
  return parcels
    .filter(
      (parcel) =>
        parcel.id !== parcelId && isActiveParcel(parcel) && !parcel.archived && !parcel.restricted,
    )
    .sort(newestFirst);
}
