import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  etaRange,
  isActiveParcel,
  possibleMatches,
  rankMergeCandidates,
  searchCandidates,
  suggestedCandidates,
  undatedParcels,
} from "../src/parcels.ts";
import type { MergeSuggestion, Parcel } from "../src/types.ts";
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

describe("rankMergeCandidates", () => {
  const ctx = { today: "2026-07-14", timeZone: "Europe/Lisbon" };
  const self = makeParcel({
    id: "self",
    merchant: "Example Shop",
    order_numbers: ["111-0000001-0000001"],
    eta_start: "2026-07-15",
    status_time: "2026-07-13T08:00:00Z",
  });
  const ids = (parcels: readonly Parcel[]): string[] => parcels.map((parcel) => parcel.id);

  test("puts the same order first, then the same shop, then nearby dates", () => {
    const parcels = [
      makeParcel({ id: "other-far", merchant: "Other Shop", eta_start: "2026-07-30" }),
      makeParcel({ id: "other-near", merchant: "Other Shop", eta_start: "2026-07-15" }),
      self,
      makeParcel({ id: "shop-far", merchant: " example shop", eta_start: "2026-07-25" }),
      makeParcel({ id: "shop-near", merchant: "Example Shop", eta_start: "2026-07-16" }),
      makeParcel({
        id: "order",
        carrier: "dhl",
        order_numbers: ["111 0000001 0000001"],
        eta_start: "2026-07-28",
      }),
    ];
    const { likely, older } = rankMergeCandidates(parcels, self, ctx);
    assert.deepEqual(ids(likely), ["order", "shop-near", "shop-far", "other-near", "other-far"]);
    assert.deepEqual(older, []);
  });

  test("puts open parcels before ones delivered this week", () => {
    const parcels = [
      self,
      makeParcel({
        id: "delivered",
        merchant: "Example Shop",
        status: "delivered",
        delivered_at: "2026-07-14T09:00:00Z",
        status_time: "2026-07-14T09:00:00Z",
      }),
      makeParcel({ id: "open", merchant: "Example Shop", eta_start: "2026-07-21" }),
    ];
    assert.deepEqual(ids(rankMergeCandidates(parcels, self, ctx).likely), ["open", "delivered"]);
  });

  test("keeps archived, cancelled and long-delivered parcels behind Show older", () => {
    const parcels = [
      self,
      makeParcel({ id: "archived", archived: true, status_time: "2026-07-01T08:00:00Z" }),
      makeParcel({ id: "cancelled", status: "cancelled", status_time: "2026-07-12T08:00:00Z" }),
      makeParcel({
        id: "long-delivered",
        status: "delivered",
        delivered_at: "2026-07-06T08:00:00Z",
        status_time: "2026-07-06T08:00:00Z",
      }),
      makeParcel({
        id: "week-delivered",
        status: "returned",
        status_time: "2026-07-07T08:00:00Z",
      }),
      makeParcel({ id: "restricted", restricted: true }),
    ];
    const { likely, older } = rankMergeCandidates(parcels, self, ctx);
    assert.deepEqual(ids(likely), ["week-delivered"]);
    assert.deepEqual(ids(older), ["cancelled", "long-delivered", "archived"]);
  });

  test("activity follows the status", () => {
    assert.equal(isActiveParcel(makeParcel({ status: "exception" })), true);
    assert.equal(isActiveParcel(makeParcel({ status: "returned" })), false);
  });
});

describe("searchCandidates", () => {
  const kettle = makeParcel({
    id: "kettle",
    merchant: "Example Shop",
    carrier: "dhl",
    tracking_number: "TEST12345",
    order_numbers: ["111-0000001-0000001"],
    items: ["Blue kettle"],
  });
  const hose = makeParcel({ id: "hose", merchant: "Other Shop", items: ["Garden hose"] });

  test("finds parcels by shop, items, order, number or carrier", () => {
    const find = (query: string): string[] =>
      searchCandidates([kettle, hose], query).map((parcel) => parcel.id);
    assert.deepEqual(find("KETTLE"), ["kettle"]);
    assert.deepEqual(find("0000001"), ["kettle"]);
    assert.deepEqual(find("dhl test123"), ["kettle"]);
    assert.deepEqual(find("garden other"), ["hose"]);
    assert.deepEqual(find("shop"), ["kettle", "hose"]);
    assert.deepEqual(find("  "), ["kettle", "hose"]);
    assert.deepEqual(find("kettle hose"), []);
  });
});

describe("merge suggestions", () => {
  const tracked = makeParcel({ id: "tracked", tracking_number: "TEST0001" });
  const lamp = makeParcel({ id: "lamp", items: ["Lumen desk lamp"] });
  const bin = makeParcel({ id: "bin", items: ["Brava bin"] });
  const suggestion = (id: string, parcel: Parcel, candidates: Parcel[]): MergeSuggestion => ({
    id,
    reason: "same_merchant_day",
    merchant: "Example Shop",
    day: "2026-07-14",
    parcel,
    candidates,
  });
  const suggestions = [suggestion("s1", tracked, [lamp, bin]), suggestion("s2", tracked, [bin])];

  test("give each suggested parcel its candidates once", () => {
    const map = suggestedCandidates(suggestions);
    assert.deepEqual(
      map.get("tracked")?.map((parcel) => parcel.id),
      ["lamp", "bin"],
    );
    assert.equal(map.has("lamp"), false);
    assert.equal(suggestedCandidates(undefined).size, 0);
  });

  test("offer the parcels a package may be, from either side", () => {
    const fromTracked = possibleMatches(suggestions, "tracked").map((match) => [
      match.suggestionId,
      match.parcel.id,
      match.candidateId,
    ]);
    assert.deepEqual(fromTracked, [
      ["s1", "lamp", "lamp"],
      ["s1", "bin", "bin"],
    ]);
    const fromLamp = possibleMatches(suggestions, "lamp").map((match) => [
      match.suggestionId,
      match.parcel.id,
      match.candidateId,
    ]);
    assert.deepEqual(fromLamp, [["s1", "tracked", "lamp"]]);
    assert.deepEqual(possibleMatches(suggestions, "other"), []);
  });
});
