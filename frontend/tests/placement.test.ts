import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { layoutWeek, placeParcel } from "../src/placement.ts";
import type { PlacementContext } from "../src/placement.ts";
import { PARCEL_STATUSES } from "../src/types.ts";
import { makeParcel } from "./helpers.ts";

// Wednesday 2026-07-15; its week runs from Monday 2026-07-13 to Sunday 2026-07-19.
const ctx: PlacementContext = { today: "2026-07-15", timeZone: "Europe/Lisbon" };
const MONDAY = "2026-07-13";
const SHOW_ALL = { showArchived: true };

describe("placeParcel", () => {
  test("puts delivered parcels on the local day of delivered_at", () => {
    const parcel = makeParcel({
      status: "delivered",
      delivered_at: "2026-07-14T23:30:00Z",
      status_time: "2026-07-13T10:00:00Z",
      eta_start: "2026-07-17",
    });
    assert.deepEqual(placeParcel(parcel, ctx), {
      kind: "delivered",
      from: "2026-07-15",
      to: "2026-07-15",
    });
  });

  test("falls back to status_time for delivered parcels", () => {
    const parcel = makeParcel({ status: "delivered", status_time: "2026-07-13T10:00:00Z" });
    assert.deepEqual(placeParcel(parcel, ctx), {
      kind: "delivered",
      from: "2026-07-13",
      to: "2026-07-13",
    });
    assert.equal(placeParcel(makeParcel({ status: "delivered" }), ctx), null);
  });

  test("puts returned parcels on their status day", () => {
    const parcel = makeParcel({
      status: "returned",
      status_time: "2026-07-16T08:00:00+01:00",
      eta_start: "2026-07-10",
    });
    assert.deepEqual(placeParcel(parcel, ctx), {
      kind: "returned",
      from: "2026-07-16",
      to: "2026-07-16",
    });
    assert.equal(placeParcel(makeParcel({ status: "returned" }), ctx), null);
  });

  test("hides cancelled parcels", () => {
    const parcel = makeParcel({
      status: "cancelled",
      status_time: "2026-07-14T08:00:00Z",
      eta_start: "2026-07-15",
    });
    assert.equal(placeParcel(parcel, ctx), null);
  });

  test("shows parcels ready for pickup from their status day to today", () => {
    const parcel = makeParcel({ status: "ready_for_pickup", status_time: "2026-07-13T09:00:00Z" });
    assert.deepEqual(placeParcel(parcel, ctx), { kind: "pickup", from: "2026-07-13", to: "2026-07-15" });
    assert.deepEqual(placeParcel(makeParcel({ status: "ready_for_pickup" }), ctx), {
      kind: "pickup",
      from: "2026-07-15",
      to: "2026-07-15",
    });
    const future = makeParcel({ status: "ready_for_pickup", status_time: "2026-07-16T09:00:00Z" });
    assert.deepEqual(placeParcel(future, ctx), { kind: "pickup", from: "2026-07-16", to: "2026-07-16" });
  });

  test("puts attempted and exception parcels without an ETA on their status day", () => {
    for (const status of ["attempted", "exception"] as const) {
      const parcel = makeParcel({ status, status_time: "2026-07-14T18:00:00Z" });
      assert.deepEqual(placeParcel(parcel, ctx), {
        kind: "status",
        from: "2026-07-14",
        to: "2026-07-14",
      });
      assert.equal(placeParcel(makeParcel({ status }), ctx), null);
      const withEta = makeParcel({
        status,
        status_time: "2026-07-14T18:00:00Z",
        eta_start: "2026-07-17",
      });
      assert.deepEqual(placeParcel(withEta, ctx), { kind: "eta", from: "2026-07-17", to: "2026-07-17" });
    }
  });

  test("spans the ETA for every other status", () => {
    for (const status of ["ordered", "shipped", "in_transit", "out_for_delivery"] as const) {
      const parcel = makeParcel({ status, eta_start: "2026-07-14", eta_end: "2026-07-16" });
      assert.deepEqual(placeParcel(parcel, ctx), { kind: "eta", from: "2026-07-14", to: "2026-07-16" });
      assert.equal(placeParcel(makeParcel({ status, status_time: "2026-07-14T08:00:00Z" }), ctx), null);
    }
  });

  test("uses a single day when the ETA has no usable end", () => {
    assert.deepEqual(placeParcel(makeParcel({ eta_start: "2026-07-14" }), ctx), {
      kind: "eta",
      from: "2026-07-14",
      to: "2026-07-14",
    });
    assert.deepEqual(placeParcel(makeParcel({ eta_start: "2026-07-14", eta_end: "2026-07-12" }), ctx), {
      kind: "eta",
      from: "2026-07-14",
      to: "2026-07-14",
    });
    assert.equal(placeParcel(makeParcel({ eta_start: "next week" }), ctx), null);
  });

  test("covers every status", () => {
    const placed = new Set<string>();
    for (const status of PARCEL_STATUSES) {
      const parcel = makeParcel({
        status,
        status_time: "2026-07-14T08:00:00Z",
        delivered_at: status === "delivered" ? "2026-07-14T08:00:00Z" : null,
        eta_start: "2026-07-16",
      });
      if (placeParcel(parcel, ctx)) {
        placed.add(status);
      }
    }
    assert.deepEqual(
      [...placed].sort(),
      PARCEL_STATUSES.filter((status) => status !== "cancelled").sort(),
    );
  });

  test("treats unknown statuses like active ones", () => {
    const parcel = makeParcel({ status: "held" as never, eta_start: "2026-07-16" });
    assert.deepEqual(placeParcel(parcel, ctx), { kind: "eta", from: "2026-07-16", to: "2026-07-16" });
  });
});

describe("layoutWeek", () => {
  test("covers Monday to Sunday", () => {
    const layout = layoutWeek([], MONDAY, ctx, SHOW_ALL);
    assert.equal(layout.start, "2026-07-13");
    assert.equal(layout.end, "2026-07-19");
    assert.equal(layout.days.length, 7);
    assert.equal(layout.lanes, 0);
    assert.deepEqual(layout.busy, [false, false, false, false, false, false, false]);
  });

  test("clips spans to the week and marks continuations", () => {
    const parcels = [
      makeParcel({ id: "before", eta_start: "2026-07-10", eta_end: "2026-07-14" }),
      makeParcel({ id: "after", eta_start: "2026-07-18", eta_end: "2026-07-21" }),
      makeParcel({ id: "both", eta_start: "2026-07-01", eta_end: "2026-07-31" }),
      makeParcel({ id: "inside", eta_start: "2026-07-15", eta_end: "2026-07-16" }),
      makeParcel({ id: "earlier", eta_start: "2026-07-06", eta_end: "2026-07-12" }),
      makeParcel({ id: "later", eta_start: "2026-07-20" }),
    ];
    const layout = layoutWeek(parcels, MONDAY, ctx, SHOW_ALL);
    const byId = new Map(layout.items.map((item) => [item.parcel.id, item]));
    assert.deepEqual([...byId.keys()].sort(), ["after", "before", "both", "inside"]);
    const pick = (id: string) => {
      const item = byId.get(id);
      assert.ok(item);
      return [item.startCol, item.endCol, item.continuesBefore, item.continuesAfter];
    };
    assert.deepEqual(pick("before"), [0, 1, true, false]);
    assert.deepEqual(pick("after"), [5, 6, false, true]);
    assert.deepEqual(pick("both"), [0, 6, true, true]);
    assert.deepEqual(pick("inside"), [2, 3, false, false]);
  });

  test("continues a pickup span to today when looking at a past week", () => {
    const parcel = makeParcel({ status: "ready_for_pickup", status_time: "2026-07-10T09:00:00Z" });
    const past = layoutWeek([parcel], "2026-07-06", ctx, SHOW_ALL).items[0];
    assert.ok(past);
    assert.deepEqual([past.startCol, past.endCol, past.continuesBefore, past.continuesAfter], [4, 6, false, true]);
    const current = layoutWeek([parcel], MONDAY, ctx, SHOW_ALL).items[0];
    assert.ok(current);
    assert.deepEqual(
      [current.startCol, current.endCol, current.continuesBefore, current.continuesAfter],
      [0, 2, true, false],
    );
  });

  test("shows archived parcels only when asked to", () => {
    const parcels = [
      makeParcel({ id: "active", eta_start: "2026-07-14" }),
      makeParcel({ id: "old", status: "delivered", delivered_at: "2026-07-13T12:00:00Z", archived: true }),
    ];
    assert.deepEqual(
      layoutWeek(parcels, MONDAY, ctx, { showArchived: true }).items.map((item) => item.parcel.id),
      ["old", "active"],
    );
    assert.deepEqual(
      layoutWeek(parcels, MONDAY, ctx, { showArchived: false }).items.map((item) => item.parcel.id),
      ["active"],
    );
  });

  test("leaves out cancelled parcels and parcels without a date", () => {
    const parcels = [
      makeParcel({ id: "cancelled", status: "cancelled", eta_start: "2026-07-14" }),
      makeParcel({ id: "undated", status: "shipped" }),
    ];
    assert.equal(layoutWeek(parcels, MONDAY, ctx, SHOW_ALL).items.length, 0);
  });

  test("packs overlapping parcels into separate lanes", () => {
    const parcels = [
      makeParcel({ id: "a", merchant: "Alpha", eta_start: "2026-07-13", eta_end: "2026-07-15" }),
      makeParcel({ id: "b", merchant: "Bravo", eta_start: "2026-07-14" }),
      makeParcel({ id: "c", merchant: "Charlie", eta_start: "2026-07-16", eta_end: "2026-07-17" }),
      makeParcel({ id: "d", merchant: "Delta", eta_start: "2026-07-14", window_start: "09:00" }),
    ];
    const layout = layoutWeek(parcels, MONDAY, ctx, SHOW_ALL);
    const lanes = Object.fromEntries(layout.items.map((item) => [item.parcel.id, item.lane]));
    assert.deepEqual(lanes, { a: 0, d: 1, b: 2, c: 0 });
    assert.equal(layout.lanes, 3);
    assert.deepEqual(
      layout.perDay.map((items) => items.map((item) => item.parcel.id)),
      [["a"], ["a", "d", "b"], ["a"], ["c"], ["c"], [], []],
    );
    assert.deepEqual(layout.busy, [true, true, true, true, true, false, false]);
  });

  test("puts longer spans first when they start on the same day", () => {
    const parcels = [
      makeParcel({ id: "short", merchant: "A", eta_start: "2026-07-14" }),
      makeParcel({ id: "long", merchant: "B", eta_start: "2026-07-14", eta_end: "2026-07-16" }),
    ];
    assert.deepEqual(
      layoutWeek(parcels, MONDAY, ctx, SHOW_ALL).items.map((item) => item.parcel.id),
      ["long", "short"],
    );
  });

  test("places restricted parcels like any other", () => {
    const parcel = makeParcel({ id: "secret", restricted: true, private: true, eta_start: "2026-07-17" });
    const item = layoutWeek([parcel], MONDAY, ctx, SHOW_ALL).items[0];
    assert.ok(item);
    assert.equal(item.startCol, 4);
  });

  test("uses the server's time zone for delivery days", () => {
    const parcel = makeParcel({ status: "delivered", delivered_at: "2026-07-19T23:30:00Z" });
    assert.equal(layoutWeek([parcel], MONDAY, ctx, SHOW_ALL).items.length, 0);
    const utc = layoutWeek([parcel], MONDAY, { ...ctx, timeZone: "UTC" }, SHOW_ALL).items[0];
    assert.ok(utc);
    assert.equal(utc.startCol, 6);
  });
});
