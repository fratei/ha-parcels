import type { CustomerReturn, OriginInfo, Parcel } from "../src/types.ts";

/** A synthetic parcel; every field can be overridden. */
export function makeParcel(overrides: Partial<Parcel> = {}): Parcel {
  return {
    id: "p1",
    merchant: null,
    seller: null,
    name: null,
    carrier: null,
    carrier_name: null,
    tracking_number: null,
    tracking_url: null,
    status: "in_transit",
    status_time: null,
    status_undated: false,
    status_timeless: false,
    eta_start: null,
    eta_end: null,
    window_start: null,
    window_end: null,
    eta_source: null,
    delivered_at: null,
    delivered_undated: false,
    delivered_timeless: false,
    status_reported: false,
    next_attempt: null,
    collect_by: null,
    left_at: null,
    inferred: false,
    inferred_reason: null,
    pickup_point: null,
    pickup_code: null,
    has_code: false,
    order_numbers: [],
    references: [],
    items: [],
    private: false,
    owners: [],
    source: "parser",
    ai: false,
    ai_filled: false,
    auto_merged: null,
    provisional: false,
    archived: false,
    origins: [],
    shipment_group: null,
    restricted: false,
    senders: [],
    ordered_at: null,
    shipped_at: null,
    ...overrides,
  };
}

/** A synthetic e-mail of a parcel's details, as read by the parser; every field can be overridden. */
export function makeOrigin(overrides: Partial<OriginInfo> = {}): OriginInfo {
  return {
    id: "m1",
    label: "",
    source: "parser",
    sender_name: null,
    name: null,
    time: null,
    status: null,
    kind: null,
    event_time: null,
    undated: false,
    timeless: false,
    dayless: false,
    eta_start: null,
    eta_end: null,
    window_start: null,
    window_end: null,
    carrier: null,
    carrier_name: null,
    tracking_number: null,
    reference: null,
    merchant: null,
    seller: null,
    order_numbers: [],
    items: [],
    pickup_point: null,
    shipment: null,
    email: false,
    edits: false,
    part_of: null,
    split_blocked: null,
    ...overrides,
  };
}

/** A synthetic customer return, picked up on 15 Jul 2026; every field can be overridden. */
export function makeReturn(overrides: Partial<CustomerReturn> = {}): CustomerReturn {
  return {
    id: "r1",
    merchant: "Example Shop",
    carrier: null,
    carrier_name: null,
    tracking_number: null,
    tracking_url: null,
    day: "2026-07-15",
    pickup: "2026-07-15",
    pickup_rule: "assumed",
    started: "2026-07-14T10:00:00+00:00",
    received: false,
    order_numbers: [],
    items: [],
    parcel_ids: [],
    emails: [],
    private: false,
    owners: [],
    archived: false,
    restricted: false,
    ...overrides,
  };
}

/** Lets pending promise callbacks run. */
export function flush(): Promise<void> {
  return new Promise((resolve) => setImmediate(resolve));
}
