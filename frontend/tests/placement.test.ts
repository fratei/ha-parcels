import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { isLateItem, itemKey, lateItems, layoutWeek, placeParcel } from "../src/placement.ts";
import type { PlacementContext } from "../src/placement.ts";
import { PARCEL_STATUSES, type Parcel } from "../src/types.ts";
import { makeParcel, makeReturn } from "./helpers.ts";

// Wednesday 2026-07-15; its week runs from Monday 2026-07-13 to Sunday 2026-07-19.
const ctx: PlacementContext = { today: "2026-07-15", timeZone: "Europe/Lisbon" };
const MONDAY = "2026-07-13";
const SHOW_ALL = { showArchived: true };
// Today in the week before, so that nothing in the week shown is late.
const EARLIER: PlacementContext = { today: "2026-07-06", timeZone: "Europe/Lisbon" };

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
      const parcel = makeParcel({ status, status_time: "2026-07-15T09:00:00Z" });
      assert.deepEqual(placeParcel(parcel, ctx), {
        kind: "status",
        from: "2026-07-15",
        to: "2026-07-15",
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
    assert.deepEqual(placeParcel(makeParcel({ eta_start: "2026-07-16" }), ctx), {
      kind: "eta",
      from: "2026-07-16",
      to: "2026-07-16",
    });
    assert.deepEqual(placeParcel(makeParcel({ eta_start: "2026-07-16", eta_end: "2026-07-12" }), ctx), {
      kind: "eta",
      from: "2026-07-16",
      to: "2026-07-16",
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
    const layout = layoutWeek(parcels, MONDAY, EARLIER, SHOW_ALL);
    const byId = new Map(layout.items.map((item) => [itemKey(item), item]));
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
      makeParcel({ id: "active", eta_start: "2026-07-16" }),
      makeParcel({ id: "old", status: "delivered", delivered_at: "2026-07-13T12:00:00Z", archived: true }),
    ];
    assert.deepEqual(
      layoutWeek(parcels, MONDAY, ctx, { showArchived: true }).items.map(itemKey),
      ["old", "active"],
    );
    assert.deepEqual(
      layoutWeek(parcels, MONDAY, ctx, { showArchived: false }).items.map(itemKey),
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
    const layout = layoutWeek(parcels, MONDAY, EARLIER, SHOW_ALL);
    const lanes = Object.fromEntries(layout.items.map((item) => [itemKey(item), item.lane]));
    assert.deepEqual(lanes, { a: 0, d: 1, b: 2, c: 0 });
    assert.equal(layout.lanes, 3);
    assert.deepEqual(
      layout.perDay.map((items) => items.map(itemKey)),
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
      layoutWeek(parcels, MONDAY, EARLIER, SHOW_ALL).items.map(itemKey),
      ["long", "short"],
    );
  });

  test("places restricted parcels like any other", () => {
    const parcel = makeParcel({ id: "secret", restricted: true, private: true, eta_start: "2026-07-17" });
    const item = layoutWeek([parcel], MONDAY, ctx, SHOW_ALL).items[0];
    assert.ok(item);
    assert.equal(item.startCol, 4);
  });

  test("shows packages of one shipment with the same status and days as one box", () => {
    const pkg = (id: string, overrides: Partial<Parcel> = {}): Parcel =>
      makeParcel({
        id,
        merchant: "Example Shop",
        carrier: "gls",
        tracking_number: `6100001231005${id.slice(-1)}`,
        eta_start: "2026-07-14",
        shipment_group: "g1",
        ...overrides,
      });
    const parcels = [
      pkg("p3"),
      pkg("p1"),
      pkg("p2", { window_start: "09:00" }),
      pkg("p4", { eta_start: "2026-07-15" }),
      pkg("p5", { status: "out_for_delivery" }),
      pkg("p6", { shipment_group: "g2" }),
      pkg("p7", { shipment_group: null }),
      pkg("p8", { status: "delivered", delivered_at: "2026-07-14T10:00:00Z" }),
      pkg("p9", { status: "delivered", delivered_at: "2026-07-15T10:00:00Z" }),
    ];
    const layout = layoutWeek(parcels, MONDAY, EARLIER, SHOW_ALL);
    const boxes = Object.fromEntries(
      layout.items.map((item) => [itemKey(item), item.type === "parcel" ? item.members.map((member) => member.id) : []]),
    );
    assert.deepEqual(boxes, {
      p1: ["p1", "p2", "p3"],
      p4: ["p4"],
      p5: ["p5"],
      p6: ["p6"],
      p7: ["p7"],
      p8: ["p8"],
      p9: ["p9"],
    });
    assert.equal(layout.perDay[1]?.length, 5);
  });

  test("never puts other users' private parcels in a box", () => {
    const parcels = ["p1", "p2"].map((id) =>
      makeParcel({ id, restricted: true, eta_start: "2026-07-14", shipment_group: "g1" }),
    );
    assert.equal(layoutWeek(parcels, MONDAY, ctx, SHOW_ALL).items.length, 2);
  });

  test("uses the server's time zone for delivery days", () => {
    const parcel = makeParcel({ status: "delivered", delivered_at: "2026-07-19T23:30:00Z" });
    assert.equal(layoutWeek([parcel], MONDAY, ctx, SHOW_ALL).items.length, 0);
    const utc = layoutWeek([parcel], MONDAY, { ...ctx, timeZone: "UTC" }, SHOW_ALL).items[0];
    assert.ok(utc);
    assert.equal(utc.startCol, 6);
  });
});

describe("layoutWeek with returns", () => {
  test("puts a return on its day, after that day's parcels", () => {
    const parcels = [
      makeParcel({ id: "zulu", merchant: "Zulu", eta_start: "2026-07-14" }),
      makeParcel({ id: "long", merchant: "Bravo", eta_start: "2026-07-13", eta_end: "2026-07-14" }),
    ];
    const returns = [
      makeReturn({ id: "r2", merchant: "Alpha", day: "2026-07-16", pickup: "2026-07-16" }),
      makeReturn({ id: "r1", merchant: "Alpha", day: "2026-07-14", pickup: "2026-07-14" }),
    ];
    const layout = layoutWeek(parcels, MONDAY, EARLIER, SHOW_ALL, returns);
    assert.deepEqual(layout.items.map(itemKey), ["long", "zulu", "return:r1", "return:r2"]);
    assert.deepEqual(
      layout.perDay.map((items) => items.map(itemKey)),
      [["long"], ["long", "zulu", "return:r1"], [], ["return:r2"], [], [], []],
    );
    assert.equal(layout.lanes, 3);
    assert.deepEqual(layout.busy, [true, true, false, true, false, false, false]);
    const item = layout.items[2];
    assert.ok(item?.type === "return");
    assert.equal(item.ret.id, "r1");
    assert.deepEqual(
      [item.day, item.startCol, item.endCol, item.continuesBefore, item.continuesAfter, item.lane],
      ["2026-07-14", 1, 1, false, false, 2],
    );
  });

  test("orders returns of one day by shop, then by id", () => {
    const returns = [
      makeReturn({ id: "r3", merchant: "bravo", day: "2026-07-15" }),
      makeReturn({ id: "r2", merchant: "Alpha", day: "2026-07-15" }),
      makeReturn({ id: "r1", merchant: "Alpha", day: "2026-07-15" }),
    ];
    assert.deepEqual(
      layoutWeek([], MONDAY, ctx, SHOW_ALL, returns).items.map(itemKey),
      ["return:r1", "return:r2", "return:r3"],
    );
  });

  test("leaves out returns of other weeks, and archived ones unless asked", () => {
    const returns = [
      makeReturn({ id: "sunday", day: "2026-07-12" }),
      makeReturn({ id: "monday", day: "2026-07-13" }),
      makeReturn({ id: "last", day: "2026-07-19" }),
      makeReturn({ id: "next", day: "2026-07-20" }),
      makeReturn({ id: "old", day: "2026-07-14", archived: true }),
    ];
    assert.deepEqual(
      layoutWeek([], MONDAY, ctx, SHOW_ALL, returns).items.map(itemKey),
      ["return:monday", "return:old", "return:last"],
    );
    assert.deepEqual(
      layoutWeek([], MONDAY, ctx, { showArchived: false }, returns).items.map(itemKey),
      ["return:monday", "return:last"],
    );
  });

  test("places other users' private returns like any other", () => {
    const ret = makeReturn({ id: "secret", merchant: null, restricted: true, day: "2026-07-17" });
    const item = layoutWeek([], MONDAY, ctx, SHOW_ALL, [ret]).items[0];
    assert.ok(item);
    assert.equal(item.startCol, 4);
  });
});

describe("late parcels", () => {
  const late = (expected: string) => ({ kind: "late", from: "2026-07-15", to: "2026-07-15", expected });

  test("carry an active parcel whose expected day has passed into today", () => {
    for (const status of ["ordered", "shipped", "in_transit", "out_for_delivery", "attempted", "exception", "held"]) {
      const parcel = makeParcel({ status: status as never, eta_start: "2026-07-14" });
      assert.deepEqual(placeParcel(parcel, ctx), late("2026-07-14"), status);
    }
    const range = makeParcel({ eta_start: "2026-07-10", eta_end: "2026-07-14" });
    assert.deepEqual(placeParcel(range, ctx), late("2026-07-14"));
    const old = makeParcel({ eta_start: "2026-06-22" });
    assert.deepEqual(placeParcel(old, ctx), late("2026-06-22"));
  });

  test("aren't late while their expected days include today", () => {
    assert.deepEqual(placeParcel(makeParcel({ eta_start: "2026-07-15" }), ctx), {
      kind: "eta",
      from: "2026-07-15",
      to: "2026-07-15",
    });
    assert.deepEqual(placeParcel(makeParcel({ eta_start: "2026-07-13", eta_end: "2026-07-15" }), ctx), {
      kind: "eta",
      from: "2026-07-13",
      to: "2026-07-15",
    });
  });

  test("carry a missed delivery or a problem without an ETA from its day into today", () => {
    for (const status of ["attempted", "exception"] as const) {
      const parcel = makeParcel({ status, status_time: "2026-07-14T18:00:00Z" });
      assert.deepEqual(placeParcel(parcel, ctx), { ...late("2026-07-14"), since: true }, status);
    }
    const shipped = makeParcel({ status: "shipped", status_time: "2026-07-14T18:00:00Z" });
    assert.equal(placeParcel(shipped, ctx), null);
  });

  test("are never delivered, returned, cancelled, waiting for pickup or archived parcels", () => {
    const parcels = [
      makeParcel({ status: "delivered", eta_start: "2026-07-10", delivered_at: "2026-07-14T10:00:00Z" }),
      makeParcel({ status: "returned", eta_start: "2026-07-10", status_time: "2026-07-14T10:00:00Z" }),
      makeParcel({ status: "ready_for_pickup", eta_start: "2026-07-10", status_time: "2026-07-10T10:00:00Z" }),
    ];
    assert.deepEqual(
      parcels.map((parcel) => placeParcel(parcel, ctx)?.kind),
      ["delivered", "returned", "pickup"],
    );
    assert.equal(placeParcel(makeParcel({ status: "cancelled", eta_start: "2026-07-10" }), ctx), null);
    const archived = makeParcel({ eta_start: "2026-07-10", archived: true });
    assert.deepEqual(placeParcel(archived, ctx), { kind: "eta", from: "2026-07-10", to: "2026-07-10" });
    const archivedProblem = makeParcel({ status: "exception", status_time: "2026-07-10T10:00:00Z", archived: true });
    assert.deepEqual(placeParcel(archivedProblem, ctx), { kind: "status", from: "2026-07-10", to: "2026-07-10" });
  });

  test("go first in today's column, above the parcels expected today", () => {
    const parcels = [
      makeParcel({ id: "late2", merchant: "Alpha", status: "out_for_delivery", eta_start: "2026-07-10", eta_end: "2026-07-12" }),
      makeParcel({ id: "late1", merchant: "Bravo", eta_start: "2026-07-14" }),
      makeParcel({ id: "span", merchant: "Charlie", eta_start: "2026-07-13", eta_end: "2026-07-17" }),
      makeParcel({ id: "got", merchant: "Delta", status: "delivered", delivered_at: "2026-07-14T10:00:00Z" }),
      makeParcel({ id: "today", merchant: "Foxtrot", eta_start: "2026-07-15", eta_end: "2026-07-16" }),
      makeParcel({ id: "fri", merchant: "Echo", eta_start: "2026-07-17" }),
    ];
    const layout = layoutWeek(parcels, MONDAY, ctx, SHOW_ALL);
    assert.deepEqual(layout.items.map(itemKey), ["span", "got", "late2", "late1", "today", "fri"]);
    const lanes = Object.fromEntries(layout.items.map((item) => [itemKey(item), item.lane]));
    assert.deepEqual(lanes, { late2: 0, late1: 1, span: 2, got: 0, today: 3, fri: 0 });
    assert.equal(layout.lanes, 4);
    assert.deepEqual(
      layout.perDay.map((items) => items.map(itemKey)),
      [["span"], ["got", "span"], ["late2", "late1", "span", "today"], ["span", "today"], ["fri", "span"], [], []],
    );
    const first = layout.items[2];
    assert.ok(first?.type === "parcel");
    assert.deepEqual(
      [first.startCol, first.endCol, first.continuesBefore, first.continuesAfter],
      [2, 2, false, false],
    );
    assert.deepEqual(layout.items.filter(isLateItem).map(itemKey), ["late2", "late1"]);
  });

  test("leave their old days, and show in no other week", () => {
    const parcel = makeParcel({ id: "late", eta_start: "2026-07-08" });
    assert.equal(layoutWeek([parcel], "2026-07-06", ctx, SHOW_ALL).items.length, 0);
    assert.equal(layoutWeek([parcel], "2026-07-20", ctx, SHOW_ALL).items.length, 0);
    assert.deepEqual(layoutWeek([parcel], MONDAY, ctx, SHOW_ALL).items.map(itemKey), ["late"]);
  });

  test("of one shipment share a box only when expected on the same day", () => {
    const pkg = (id: string, eta: string): Parcel =>
      makeParcel({ id, merchant: "Example Shop", eta_start: eta, shipment_group: "g1" });
    const parcels = [pkg("p1", "2026-07-14"), pkg("p2", "2026-07-14"), pkg("p3", "2026-07-13"), pkg("p4", "2026-07-15")];
    const layout = layoutWeek(parcels, MONDAY, ctx, SHOW_ALL);
    const boxes = Object.fromEntries(
      layout.items.map((item) => [itemKey(item), item.type === "parcel" ? item.members.map((member) => member.id) : []]),
    );
    assert.deepEqual(boxes, { p1: ["p1", "p2"], p3: ["p3"], p4: ["p4"] });
  });

  test("of one shipment share a box only when late for the same reason", () => {
    const missed = (id: string, overrides: Partial<Parcel>): Parcel =>
      makeParcel({ id, merchant: "Example Shop", status: "attempted", shipment_group: "g1", ...overrides });
    const parcels = [
      missed("p1", { eta_start: "2026-07-14" }),
      missed("p2", { status_time: "2026-07-14T18:00:00Z" }),
      missed("p3", { status_time: "2026-07-14T09:00:00Z" }),
    ];
    const layout = layoutWeek(parcels, MONDAY, ctx, SHOW_ALL);
    const boxes = Object.fromEntries(
      layout.items.map((item) => [itemKey(item), item.type === "parcel" ? item.members.map((member) => member.id) : []]),
    );
    assert.deepEqual(boxes, { p1: ["p1"], p2: ["p2", "p3"] });
  });

  test("are counted by box, without archived or completed parcels", () => {
    const parcels = [
      makeParcel({ id: "p1", eta_start: "2026-07-14", shipment_group: "g1" }),
      makeParcel({ id: "p2", eta_start: "2026-07-14", shipment_group: "g1" }),
      makeParcel({ id: "secret", eta_start: "2026-07-13", restricted: true, private: true }),
      makeParcel({ id: "old", eta_start: "2026-07-01", archived: true }),
      makeParcel({ id: "got", status: "delivered", eta_start: "2026-07-14", delivered_at: "2026-07-15T08:00:00Z" }),
      makeParcel({ id: "today", eta_start: "2026-07-15" }),
    ];
    assert.deepEqual(lateItems(parcels, ctx).map(itemKey), ["p1", "secret"]);
    assert.deepEqual(lateItems([], ctx), []);
  });
});
