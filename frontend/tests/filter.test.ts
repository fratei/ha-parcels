import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  FILTER_EVENT,
  matchesFilter,
  readFilter,
  saveFilter,
  type FilterContext,
  type ParcelFilter,
} from "../src/filter.ts";
import type { Parcel } from "../src/types.ts";
import { makeParcel } from "./helpers.ts";

// A Wednesday; its week runs from Monday 13 to Sunday 19 July.
const CONTEXT: FilterContext = { today: "2026-07-15", timeZone: "Europe/Lisbon" };

function shown(filter: ParcelFilter, parcels: Record<string, Partial<Parcel>>): string[] {
  return Object.entries(parcels)
    .filter(([, overrides]) => matchesFilter(makeParcel(overrides), filter, CONTEXT))
    .map(([name]) => name);
}

const PARCELS: Record<string, Partial<Parcel>> = {
  ordered: { status: "ordered" },
  transit: { status: "in_transit", eta_start: "2026-07-21" },
  pickup: { status: "ready_for_pickup", status_time: "2026-07-01T10:00:00Z" },
  delivered: { status: "delivered", delivered_at: "2026-07-02T10:00:00Z" },
  inferred: { status: "delivered", inferred: true, status_time: "2026-07-03T10:00:00Z" },
  returned: { status: "returned" },
  cancelled: { status: "cancelled" },
};

describe("matchesFilter", () => {
  test("shows everything with All", () => {
    assert.deepEqual(shown("all", PARCELS), Object.keys(PARCELS));
  });

  test("splits active and completed parcels", () => {
    assert.deepEqual(shown("active", PARCELS), ["ordered", "transit", "pickup"]);
    assert.deepEqual(shown("completed", PARCELS), ["delivered", "inferred", "returned", "cancelled"]);
  });

  test("keeps what changed or is expected this week", () => {
    assert.deepEqual(
      shown("recent", {
        old: { status_time: "2026-07-10T10:00:00Z", eta_start: "2026-07-21" },
        changed: { status_time: "2026-07-13T08:00:00Z" },
        // Sunday 23:30 in Lisbon, the week before.
        sundayNight: { status_time: "2026-07-12T22:30:00Z" },
        // Monday 00:30 in Lisbon.
        mondayMorning: { status_time: "2026-07-12T23:30:00Z" },
        overlapping: { eta_start: "2026-07-10", eta_end: "2026-07-13" },
        nextWeek: { eta_start: "2026-07-20", eta_end: "2026-07-22" },
        lastDay: { eta_end: "2026-07-19" },
        deliveredNow: {
          status: "delivered",
          status_time: "2026-07-01T10:00:00Z",
          delivered_at: "2026-07-14T10:00:00Z",
        },
        deliveredBefore: { status: "delivered", delivered_at: "2026-07-11T10:00:00Z" },
      }),
      ["changed", "mondayMorning", "overlapping", "lastDay", "deliveredNow"],
    );
  });

  test("keeps late parcels, which the week shows today", () => {
    assert.deepEqual(
      shown("recent", {
        late: { eta_start: "2026-06-29", eta_end: "2026-07-01" },
        lateProblem: { status: "exception", status_time: "2026-07-01T10:00:00Z" },
        lateArchived: { eta_start: "2026-07-01", archived: true },
        delivered: { status: "delivered", eta_start: "2026-07-01", delivered_at: "2026-07-02T10:00:00Z" },
      }),
      ["late", "lateProblem"],
    );
  });
});

class MemoryStorage {
  values = new Map<string, string>();
  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

class BrokenStorage {
  getItem(): string | null {
    throw new Error("blocked");
  }
  setItem(): void {
    throw new Error("blocked");
  }
}

describe("the chosen filter", () => {
  test("is remembered on the device and announced to the other cards", () => {
    const storage = new MemoryStorage();
    const target = new EventTarget();
    const heard: unknown[] = [];
    target.addEventListener(FILTER_EVENT, (event) => heard.push((event as CustomEvent).detail));

    assert.equal(readFilter(storage), "all");
    saveFilter("recent", storage, target);

    assert.equal(readFilter(storage), "recent");
    assert.deepEqual(heard, ["recent"]);
  });

  test("falls back to All when nothing valid is stored or storage is blocked", () => {
    const storage = new MemoryStorage();
    storage.setItem("parcels-filter", "everything");
    assert.equal(readFilter(storage), "all");
    assert.equal(readFilter(new BrokenStorage()), "all");
    assert.equal(readFilter(null), "all");

    const target = new EventTarget();
    const heard: unknown[] = [];
    target.addEventListener(FILTER_EVENT, (event) => heard.push((event as CustomEvent).detail));
    saveFilter("completed", new BrokenStorage(), target);
    assert.deepEqual(heard, ["completed"]);
  });
});
