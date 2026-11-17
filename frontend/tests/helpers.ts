import type { Parcel } from "../src/types.ts";

/** A synthetic parcel; every field can be overridden. */
export function makeParcel(overrides: Partial<Parcel> = {}): Parcel {
  return {
    id: "p1",
    merchant: null,
    carrier: null,
    carrier_name: null,
    tracking_number: null,
    tracking_url: null,
    status: "in_transit",
    status_time: null,
    eta_start: null,
    eta_end: null,
    window_start: null,
    window_end: null,
    delivered_at: null,
    pickup_point: null,
    pickup_code: null,
    order_numbers: [],
    items: [],
    private: false,
    owners: [],
    source: "parser",
    ai: false,
    auto_merged: null,
    provisional: false,
    archived: false,
    origins: [],
    restricted: false,
    ...overrides,
  };
}

/** Lets pending promise callbacks run. */
export function flush(): Promise<void> {
  return new Promise((resolve) => setImmediate(resolve));
}
