import {
  addDays,
  compareYmd,
  diffDays,
  localDateOf,
  maxYmd,
  startOfWeek,
  weekDates,
} from "./dates.ts";
import { byId, groupItems, shipmentKey } from "./groups.ts";
import { parcelTitle } from "./labels.ts";
import { etaRange } from "./parcels.ts";
import { returnTitle } from "./returns.ts";
import type { CustomerReturn, Parcel } from "./types.ts";

/** Why a parcel is on the days it's on. */
export type PlacementKind = "delivered" | "returned" | "pickup" | "status" | "eta" | "late";

/** Inclusive range of "YYYY-MM-DD" days on which a parcel shows. */
export interface Placement {
  kind: PlacementKind;
  from: string;
  to: string;
  /** A late parcel's last expected day, or the day of its problem when `since`. */
  expected?: string;
  /** Late since its missed delivery or problem, as it had no expected day. */
  since?: true;
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
 * A parcel still on its way whose ETA ended before today, or whose missed
 * delivery or problem without an ETA was before today, is late: it moves to
 * today, with the day it was expected. Archived parcels stay on their days.
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
  const { today } = context;
  const eta = etaRange(parcel);
  if (eta) {
    if (!parcel.archived && compareYmd(eta.end, today) < 0) {
      return { kind: "late", from: today, to: today, expected: eta.end };
    }
    return { kind: "eta", from: eta.start, to: eta.end };
  }
  if ((parcel.status === "attempted" || parcel.status === "exception") && statusDay) {
    if (!parcel.archived && compareYmd(statusDay, today) < 0) {
      return { kind: "late", from: today, to: today, expected: statusDay, since: true };
    }
    return { kind: "status", from: statusDay, to: statusDay };
  }
  return null;
}

export interface WeekItem {
  type: "parcel";
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

/** A customer return, on its pickup day (or the day it started, without one). */
export interface ReturnItem {
  type: "return";
  ret: CustomerReturn;
  day: string;
  startCol: number;
  endCol: number;
  continuesBefore: false;
  continuesAfter: false;
  lane: number;
}

export type LayoutItem = WeekItem | ReturnItem;

/** A key unique among a week's items. */
export function itemKey(item: LayoutItem): string {
  return item.type === "parcel" ? item.parcel.id : `return:${item.ret.id}`;
}

/** A late parcel (or box), carried into today. */
export function isLateItem(item: LayoutItem): item is WeekItem {
  return item.type === "parcel" && item.placement.kind === "late";
}

export interface WeekLayout {
  /** Monday and Sunday of the week. */
  start: string;
  end: string;
  days: string[];
  /** Placed items, sorted by start day; a day's returns after its parcels. */
  items: LayoutItem[];
  /** Number of lanes needed. */
  lanes: number;
  /** The items covering each day, in lane order. */
  perDay: LayoutItem[][];
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

function compareParcels(a: WeekItem, b: WeekItem): number {
  return (
    compareText(windowKey(a.parcel), windowKey(b.parcel)) ||
    compareText(parcelTitle(a.parcel).toLowerCase(), parcelTitle(b.parcel).toLowerCase()) ||
    compareText(a.parcel.id, b.parcel.id)
  );
}

function compareReturns(a: ReturnItem, b: ReturnItem): number {
  return (
    compareText(returnTitle(a.ret).toLowerCase(), returnTitle(b.ret).toLowerCase()) ||
    compareText(a.ret.id, b.ret.id)
  );
}

function compareItems(a: LayoutItem, b: LayoutItem): number {
  const order =
    a.startCol - b.startCol ||
    Number(isLateItem(b)) - Number(isLateItem(a)) ||
    b.endCol - b.startCol - (a.endCol - a.startCol) ||
    (a.type === b.type ? 0 : a.type === "parcel" ? -1 : 1);
  if (order) {
    return order;
  }
  if (a.type === "parcel" && b.type === "parcel") {
    return compareParcels(a, b);
  }
  return a.type === "return" && b.type === "return" ? compareReturns(a, b) : 0;
}

/**
 * Places parcels on the week that starts on the Monday `weekStart` and packs
 * them into lanes. Packages of one shipment with the same status on the same
 * days (and, when late, expected on the same day) share one box. Late
 * parcels take the top lanes of today. Customer returns go on their day,
 * after its parcels.
 */
export function layoutWeek(
  parcels: readonly Parcel[],
  weekStart: string,
  context: PlacementContext,
  options: LayoutOptions,
  returns: readonly CustomerReturn[] = [],
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
      type: "parcel",
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
  const items: LayoutItem[] = groupItems(placed, (item) =>
    shipmentKey(
      item.parcel,
      item.placement.kind,
      item.placement.from,
      item.placement.to,
      item.placement.expected ?? "",
      item.placement.since ? "since" : "",
    ),
  ).map((box): WeekItem => {
    const first = box.reduce((min, item) => (byId(item.parcel, min.parcel) < 0 ? item : min));
    return { ...first, members: box.map((item) => item.parcel).sort(byId) };
  });
  for (const ret of returns) {
    if (
      (ret.archived && !options.showArchived) ||
      compareYmd(ret.day, weekStart) < 0 ||
      compareYmd(ret.day, weekEnd) > 0
    ) {
      continue;
    }
    const column = diffDays(weekStart, ret.day);
    items.push({
      type: "return",
      ret,
      day: ret.day,
      startCol: column,
      endCol: column,
      continuesBefore: false,
      continuesAfter: false,
      lane: 0,
    });
  }
  items.sort(compareItems);
  // The days each lane has taken; late parcels go first, to top today's column.
  const taken: boolean[][] = [];
  for (const item of [...items.filter(isLateItem), ...items.filter((item) => !isLateItem(item))]) {
    const columns = days.map((_, column) => column).slice(item.startCol, item.endCol + 1);
    let lane = taken.find((busy) => columns.every((column) => !busy[column]));
    if (!lane) {
      lane = days.map(() => false);
      taken.push(lane);
    }
    for (const column of columns) {
      lane[column] = true;
    }
    item.lane = taken.indexOf(lane);
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
    lanes: taken.length,
    perDay,
    busy: perDay.map((dayItems) => dayItems.length > 0),
  };
}

/** The late parcels (a box counting once) of the current week, carried into today. */
export function lateItems(parcels: readonly Parcel[], context: PlacementContext): WeekItem[] {
  return layoutWeek(parcels, startOfWeek(context.today), context, { showArchived: false }).items.filter(
    isLateItem,
  );
}
