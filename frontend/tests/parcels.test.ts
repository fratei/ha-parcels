import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { etaRange, isActiveParcel, mergeCandidates, undatedParcels } from "../src/parcels.ts";
import { makeParcel } from "./helpers.ts";

describe("etaRange", () => {
  test("spans eta_start to eta_end", () => {
    assert.deepEqual(etaRange({ eta_start: "2026-07-14", eta_end: "2026-07-16" }), {
      start: "2026-07-14",
      end: "2026-07-16",
    });
  });

  test("is a single day when only one end is usable", () => {
    const day = { start: "2026-07-14", end: "2026-07-14" };
    assert.deepEqual(etaRange({ eta_start: "2026-07-14", eta_end: null }), day);
    assert.deepEqual(etaRange({ eta_start: null, eta_end: "2026-07-14" }), day);
    assert.deepEqual(etaRange({ eta_start: "2026-07-14", eta_end: "2026-07-13" }), day);
    assert.deepEqual(etaRange({ eta_start: "2026-07-14", eta_end: "Friday" }), day);
  });

  test("is null without an ETA", () => {
    assert.equal(etaRange({ eta_start: null, eta_end: null }), null);
    assert.equal(etaRange({ eta_start: "", eta_end: "soon" }), null);
  });
});

describe("undatedParcels", () => {
  test("lists active parcels without an ETA, newest first", () => {
    const parcels = [
      makeParcel({ id: "older", status: "shipped", status_time: "2026-07-10T08:00:00Z" }),
      makeParcel({ id: "no-time", status: "ordered" }),
      makeParcel({ id: "newer", status: "in_transit", status_time: "2026-07-12T08:00:00+02:00" }),
      makeParcel({ id: "pickup", status: "ready_for_pickup", status_time: "2026-07-11T08:00:00Z" }),
      makeParcel({ id: "a-no-time", status: "attempted" }),
      makeParcel({ id: "dated", status: "shipped", eta_start: "2026-07-14" }),
      makeParcel({ id: "end-only", status: "shipped", eta_end: "2026-07-14" }),
      makeParcel({ id: "delivered", status: "delivered" }),
      makeParcel({ id: "returned", status: "returned" }),
      makeParcel({ id: "cancelled", status: "cancelled" }),
      makeParcel({ id: "archived", status: "shipped", archived: true }),
    ];
    assert.deepEqual(
      undatedParcels(parcels).map((parcel) => parcel.id),
      ["newer", "pickup", "older", "a-no-time", "no-time"],
    );
  });

  test("keeps restricted parcels", () => {
    const parcels = [makeParcel({ id: "secret", restricted: true, private: true })];
    assert.deepEqual(
      undatedParcels(parcels).map((parcel) => parcel.id),
      ["secret"],
    );
  });

  test("doesn't change the input", () => {
    const parcels = [
      makeParcel({ id: "b", status_time: "2026-07-10T08:00:00Z" }),
      makeParcel({ id: "a", status_time: "2026-07-12T08:00:00Z" }),
    ];
    undatedParcels(parcels);
    assert.deepEqual(
      parcels.map((parcel) => parcel.id),
      ["b", "a"],
    );
  });
});

describe("mergeCandidates", () => {
  test("are the other active, visible, not archived parcels", () => {
    const parcels = [
      makeParcel({ id: "self", status_time: "2026-07-13T08:00:00Z" }),
      makeParcel({ id: "older", status_time: "2026-07-10T08:00:00Z", eta_start: "2026-07-15" }),
      makeParcel({ id: "newer", status: "ordered", status_time: "2026-07-12T08:00:00Z" }),
      makeParcel({ id: "delivered", status: "delivered" }),
      makeParcel({ id: "archived", archived: true }),
      makeParcel({ id: "restricted", restricted: true }),
    ];
    assert.deepEqual(
      mergeCandidates(parcels, "self").map((parcel) => parcel.id),
      ["newer", "older"],
    );
  });

  test("activity follows the status", () => {
    assert.equal(isActiveParcel(makeParcel({ status: "exception" })), true);
    assert.equal(isActiveParcel(makeParcel({ status: "returned" })), false);
  });
});
