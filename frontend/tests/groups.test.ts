import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { boxParcel, groupItems, shipmentBoxes, shipmentPackages } from "../src/groups.ts";
import type { Parcel } from "../src/types.ts";
import { makeParcel } from "./helpers.ts";

const MERGED = { origin: "o2", at: "2026-07-14T10:00:00Z", reason: "same_order" };

function pkg(id: string, number: string, overrides: Partial<Parcel> = {}): Parcel {
  return makeParcel({
    id,
    merchant: "Example Shop",
    carrier: "gls",
    tracking_number: number,
    shipment_group: "p1",
    ...overrides,
  });
}

describe("groupItems", () => {
  test("keeps the first-seen order and leaves items without a key alone", () => {
    const boxes = groupItems(["a1", "b1", "x", "a2", "x", "b2"], (item) =>
      item === "x" ? null : item.charAt(0),
    );
    assert.deepEqual(boxes, [["a1", "a2"], ["b1", "b2"], ["x"], ["x"]]);
  });
});

describe("shipmentBoxes", () => {
  test("puts packages of one shipment and status in one box", () => {
    const parcels = [
      pkg("p3", "61000012310053"),
      pkg("p9", "61000099910051", { shipment_group: null }),
      pkg("p1", "61000012310051"),
      pkg("p2", "61000012310052", { status: "exception" }),
      pkg("p4", "61000012310054", { restricted: true }),
      pkg("p5", "61000012310055", { restricted: true }),
    ];
    const boxes = shipmentBoxes(parcels).map((box) => [box.parcel.id, box.members.map((m) => m.id)]);
    assert.deepEqual(boxes, [
      ["p1", ["p1", "p3"]],
      ["p9", ["p9"]],
      ["p2", ["p2"]],
      ["p4", ["p4"]],
      ["p5", ["p5"]],
    ]);
  });
});

describe("boxParcel", () => {
  test("covers every package's window and flags", () => {
    const first = pkg("p1", "61000012310051", { window_start: "10:00", window_end: "12:00" });
    const members = [
      first,
      pkg("p2", "61000012310052", { window_start: "09:00", window_end: "11:00", ai: true }),
      pkg("p3", "61000012310053", { window_end: "13:00", has_code: true, auto_merged: MERGED }),
      pkg("p4", "61000012310054", { private: true, inferred: true }),
    ];
    const shown = boxParcel(first, members);
    assert.equal(shown.id, "p1");
    assert.equal(shown.tracking_number, "61000012310051");
    assert.equal(shown.window_start, "09:00");
    assert.equal(shown.window_end, "13:00");
    assert.equal(shown.ai, true);
    assert.equal(shown.has_code, true);
    assert.equal(shown.private, true);
    assert.equal(shown.inferred, true);
    assert.deepEqual(shown.auto_merged, MERGED);
    assert.equal(boxParcel(first, [first]), first);
  });

  test("has every package's items and PINs", () => {
    const first = pkg("p1", "61000012310051", { items: ["Brava bin"], pickup_code: "4711", has_code: true });
    const members = [
      first,
      pkg("p2", "61000012310052", { items: ["Zeta plug", "Brava bin"], pickup_code: "4711", has_code: true }),
      pkg("p3", "61000012310053", { items: ["Lumen lamp"], pickup_code: "0815", has_code: true }),
      pkg("p4", "61000012310054"),
    ];
    const shown = boxParcel(first, members);
    assert.deepEqual(shown.items, ["Brava bin", "Zeta plug", "Lumen lamp"]);
    assert.equal(shown.pickup_code, "4711, 0815");
    assert.equal(boxParcel(first, [first, pkg("p2", "61000012310052")]).pickup_code, "4711");
    assert.equal(boxParcel(pkg("p5", "61000012310055"), [pkg("p5", "61000012310055"), pkg("p6", "61000012310056")]).pickup_code, null);
  });
});

describe("shipmentPackages", () => {
  test("lists the shipment's packages by number", () => {
    const parcels = [
      pkg("p1", "61000012310510"),
      pkg("p2", "61000012310052"),
      pkg("p3", "61000012310100"),
      pkg("p4", "61000012310053", { shipment_group: "p4" }),
      pkg("p5", "61000012310054", { restricted: true }),
    ];
    const first = parcels[0] as Parcel;
    assert.deepEqual(
      shipmentPackages(parcels, first).map((parcel) => parcel.id),
      ["p2", "p3", "p1"],
    );
    assert.deepEqual(shipmentPackages(parcels, parcels[3] as Parcel), []);
    assert.deepEqual(shipmentPackages(parcels, parcels[4] as Parcel), []);
    assert.deepEqual(shipmentPackages(parcels, makeParcel()), []);
  });
});
