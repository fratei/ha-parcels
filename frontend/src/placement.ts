import {
  addDays,
  compareYmd,
  diffDays,
  localDateOf,
  maxYmd,
  weekDates,
} from "./dates.ts";
import { byId, groupItems, shipmentKey } from "./groups.ts";
import { parcelTitle } from "./labels.ts";
import { etaRange } from "./parcels.ts";
import type { Parcel } from "./types.ts";

/** Why a parcel is on the days it's on. */
export type PlacementKind = "delivered" | "returned" | "pickup" | "status" | "eta";

/** Inclusive range of "YYYY-MM-DD" days on which a parcel shows. */
export interface Placement {
  kind: PlacementKind;
  from: string;
  to: string;
}

export interface PlacementContext {
  /** Home Assistant's local date (settings.today). */
  today: string;
  /** Home Assistant's time zone (settings.time_zone). */
  timeZone: string;
}

/**
 * Where a parcel goes in the calendar, or null when it doesn't go in it:
 * - delivered: the local day of delivered_at (else status_time);
 * - returned: its status day;
 * - cancelled: hidden;
 * - ready_for_pickup: from its status day to today;
 * - anything else with an ETA: eta_start..eta_end;
 * - attempted or exception without an ETA: its status day;
 * - no ETA: not in the calendar (the list card shows those).
 */
export function placeParcel(parcel: Parcel, context: PlacementContext): Placement | null {
  const statusDay = localDateOf(parcel.status_time, context.timeZone);
  switch (parcel.status) {
    case "cancelled":
      return null;
    case "delivered": {
      const day = localDateOf(parcel.delivered_at, context.timeZone) ?? statusDay;
      return day ? { kind: "delivered", from: day, to: day } : null;
    }
    case "returned":
      return statusDay ? { kind: "returned", from: statusDay, to: statusDay } : null;
    case "ready_for_pickup": {
      const from = statusDay ?? context.today;
      return { kind: "pickup", from, to: maxYmd(from, context.today) };
    }
    default:
      break;
  }
  const eta = etaRange(parcel);
  if (eta) {
    return { kind: "eta", from: eta.start, to: eta.end };
  }
  if ((parcel.status === "attempted" || parcel.status === "exception") && statusDay) {
    return { kind: "status", from: statusDay, to: statusDay };
  }
  return null;
}

export interface WeekItem {
  /** The parcel, or the first package of a shipment shown as one box. */
  parcel: Parcel;
  /** The packages in the box, by ID; just the parcel when it's alone. */
  members: Parcel[];
  placement: Placement;
  /** First and last day column (0 = Monday … 6 = Sunday) after clipping to the week. */
  startCol: number;
  endCol: number;
  /** The placement starts before Monday / ends after Sunday. */
  continuesBefore: boolean;
  continuesAfter: boolean;
  /** Row in the grid; items in the same lane never overlap. */
  lane: number;
}

export interface WeekLayout {
  /** Monday and Sunday of the week. */
  start: string;
  end: string;
  days: string[];
  /** Placed items, sorted by start day. */
  items: WeekItem[];
  /** Number of lanes needed. */
  lanes: number;
  /** The items covering each day, in lane order. */
  perDay: WeekItem[][];
  /** Whether each day has anything on it. */
  busy: boolean[];
}

export interface LayoutOptions {
  showArchived: boolean;
}

function windowKey(parcel: Parcel): string {
  return parcel.window_start ?? parcel.window_end ?? "~";
}

function compareText(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function compareItems(a: WeekItem, b: WeekItem): number {
  return (
    a.startCol - b.startCol ||
    b.endCol - b.startCol - (a.endCol - a.startCol) ||
    compareText(windowKey(a.parcel), windowKey(b.parcel)) ||
    compareText(parcelTitle(a.parcel).toLowerCase(), parcelTitle(b.parcel).toLowerCase()) ||
    compareText(a.parcel.id, b.parcel.id)
  );
}

/**
 * Places parcels on the week that starts on the Monday `weekStart` and packs
 * them into lanes. Packages of one shipment with the same status on the same
 * days share one box.
 */
export function layoutWeek(
  parcels: readonly Parcel[],
  weekStart: string,
  context: PlacementContext,
  options: LayoutOptions,
): WeekLayout {
  const days = weekDates(weekStart);
  const weekEnd = addDays(weekStart, 6);
  const placed: WeekItem[] = [];
  for (const parcel of parcels) {
    if (parcel.archived && !options.showArchived) {
      continue;
    }
    const placement = placeParcel(parcel, context);
    if (
      !placement ||
      compareYmd(placement.to, weekStart) < 0 ||
      compareYmd(placement.from, weekEnd) > 0
    ) {
      continue;
    }
    placed.push({
      parcel,
      members: [parcel],
      placement,
      startCol: Math.max(0, diffDays(weekStart, placement.from)),
      endCol: Math.min(6, diffDays(weekStart, placement.to)),
      continuesBefore: compareYmd(placement.from, weekStart) < 0,
      continuesAfter: compareYmd(placement.to, weekEnd) > 0,
      lane: 0,
    });
  }
  const items = groupItems(placed, (item) =>
    shipmentKey(item.parcel, item.placement.kind, item.placement.from, item.placement.to),
  ).map((box): WeekItem => {
    const first = box.reduce((min, item) => (byId(item.parcel, min.parcel) < 0 ? item : min));
    return { ...first, members: box.map((item) => item.parcel).sort(byId) };
  });
  items.sort(compareItems);
  const laneEnds: number[] = [];
  for (const item of items) {
    let lane = laneEnds.findIndex((end) => end < item.startCol);
    if (lane === -1) {
      lane = laneEnds.length;
    }
    laneEnds[lane] = item.endCol;
    item.lane = lane;
  }
  const perDay = days.map((_, column) =>
    items
      .filter((item) => item.startCol <= column && column <= item.endCol)
      .sort((a, b) => a.lane - b.lane),
  );
  return {
    start: weekStart,
    end: weekEnd,
    days,
    items,
    lanes: laneEnds.length,
    perDay,
    busy: perDay.map((dayItems) => dayItems.length > 0),
  };
}
