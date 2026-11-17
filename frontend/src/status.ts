import type { ParcelStatus } from "./types.ts";

const GREY = "var(--secondary-text-color, #727272)";
const BLUE = "var(--info-color, #039be5)";
const ORANGE = "var(--warning-color, #ffa600)";
const GREEN = "var(--success-color, #43a047)";
const RED = "var(--error-color, #db4437)";
const PURPLE = "var(--purple-color, #926bc7)";

export const STATUS_COLORS: Readonly<Record<ParcelStatus, string>> = {
  ordered: GREY,
  shipped: BLUE,
  in_transit: BLUE,
  out_for_delivery: ORANGE,
  delivered: GREEN,
  attempted: RED,
  exception: RED,
  ready_for_pickup: PURPLE,
  returned: GREY,
  cancelled: GREY,
};

/** CSS colour (an HA theme variable with a fallback) for a status; unknown statuses are grey. */
export function statusColor(status: string): string {
  return Object.hasOwn(STATUS_COLORS, status) ? STATUS_COLORS[status as ParcelStatus] : GREY;
}

/** Progress of a status, as STATUS_RANK in const.py; unknown statuses rank first. */
const STATUS_RANK: Readonly<Record<ParcelStatus, number>> = {
  ordered: 0,
  shipped: 1,
  in_transit: 2,
  exception: 2,
  attempted: 3,
  out_for_delivery: 3,
  ready_for_pickup: 3,
  delivered: 4,
  returned: 4,
  cancelled: 4,
};

export function statusRank(status: string): number {
  return Object.hasOwn(STATUS_RANK, status) ? STATUS_RANK[status as ParcelStatus] : 0;
}

const TERMINAL: ReadonlySet<string> = new Set(["delivered", "returned", "cancelled"]);

/** True for statuses where the parcel is still on its way (not delivered, returned or cancelled). */
export function isActiveStatus(status: string): boolean {
  return !TERMINAL.has(status);
}
