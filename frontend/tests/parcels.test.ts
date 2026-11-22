import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  alsoPossible,
  etaRange,
  isActiveParcel,
  possibleHint,
  possibleMatches,
  rankMergeCandidates,
  rankPossible,
  searchCandidates,
  suggestedCandidates,
  undatedParcels,
} from "../src/parcels.ts";
import type { PossibleMatch } from "../src/parcels.ts";
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

  test("keeps deliveries made before the parcel left behind Show older", () => {
    const sent = makeParcel({ ...self, shipped_at: "2026-07-13T08:00:00Z" });
    const delivered = (id: string, at: string): Parcel =>
      makeParcel({ id, merchant: "Example Shop", status: "delivered", delivered_at: at, status_time: at });
    const parcels = [
      sent,
      delivered("before", "2026-07-12T21:00:00Z"),
      delivered("same-day", "2026-07-13T07:00:00Z"),
      makeParcel({ ...delivered("undated", "2026-07-12T09:00:00Z"), delivered_undated: true }),
    ];
    const { likely, older } = rankMergeCandidates(parcels, sent, ctx);
    assert.deepEqual(ids(likely), ["same-day", "undated"]);
    assert.deepEqual(ids(older), ["before"]);
    const ordered = makeParcel({ ...self, ordered_at: "2026-07-13T08:00:00Z" });
    assert.deepEqual(ids(rankMergeCandidates([ordered, parcels[1]!], ordered, ctx).older), ["before"]);
  });

  test("a delivery known only by its day counts on that day", () => {
    const sent = makeParcel({ ...self, shipped_at: "2026-07-13T08:00:00Z" });
    const dayOnly = (id: string, at: string): Parcel =>
      makeParcel({
        id,
        merchant: "Example Shop",
        status: "delivered",
        delivered_at: at,
        delivered_undated: true,
        delivered_timeless: true,
        status_time: at,
        status_undated: true,
        status_timeless: true,
      });
    const parcels = [
      sent,
      dayOnly("day-before", "2026-07-11T23:00:00.000020Z"),
      dayOnly("same-day", "2026-07-12T23:00:00.000020Z"),
    ];
    const { likely, older } = rankMergeCandidates(parcels, sent, ctx);
    assert.deepEqual(ids(likely), ["same-day"]);
    assert.deepEqual(ids(older), ["day-before"]);
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
    assert.deepEqual(
      possibleMatches(suggestions, "lamp").map((match) => match.reason),
      ["same_merchant_day"],
    );
  });
});

describe("possible matches", () => {
  const ctx = { today: "2026-07-20", timeZone: "Europe/Lisbon" };
  const order = makeParcel({
    id: "order",
    merchant: "Example Shop",
    items: ["Blue kettle"],
    eta_start: "2026-07-18",
    shipped_at: "2026-07-14T08:00:00Z",
  });
  const box = (id: string, day: string, overrides: Partial<Parcel> = {}): Parcel =>
    makeParcel({
      id,
      merchant: "Example Shop",
      carrier: "dhl",
      tracking_number: `JD0000000000${id}`,
      status: "delivered",
      delivered_at: `${day}T10:00:00Z`,
      status_time: `${day}T10:00:00Z`,
      ...overrides,
    });
  const suggestion = (
    id: string,
    parcel: Parcel,
    candidates: Parcel[],
    reason = "same_merchant_day",
  ): MergeSuggestion => ({ id, reason, merchant: "Example Shop", day: null, parcel, candidates });
  const ids = (matches: readonly PossibleMatch[]): string[] => matches.map((match) => match.parcel.id);

  test("come nearest to the parcel's day first, without deliveries made before it left", () => {
    const boxes = [
      box("b1", "2026-07-15"),
      box("b2", "2026-07-18"),
      box("b3", "2026-07-21"),
      box("b4", "2026-07-13"),
      box("b5", "2026-07-14"),
      box("b6", "2026-07-18", { eta_start: "2026-07-25" }),
      box("b7", "2026-07-13", { delivered_undated: true, eta_start: "2026-07-19" }),
    ];
    const suggestions = boxes.map((parcel, index) => suggestion(`s${index}`, parcel, [order]));
    const matches = rankPossible(order, possibleMatches(suggestions, "order"), ctx);
    assert.deepEqual(ids(matches), ["b2", "b6", "b7", "b3", "b1", "b5"]);
  });

  test("leave out orders that left after the delivery", () => {
    const delivered = box("b1", "2026-07-13");
    const later = makeParcel({ ...order, id: "later" });
    const earlier = makeParcel({ ...order, id: "earlier", shipped_at: "2026-07-12T08:00:00Z" });
    const suggestions = [suggestion("s1", delivered, [later, earlier])];
    assert.deepEqual(ids(rankPossible(delivered, possibleMatches(suggestions, "b1"), ctx)), ["earlier"]);
  });

  test("name the other orders a delivery could be", () => {
    const lamp = makeParcel({ id: "lamp", merchant: "Example Shop", items: ["Lumen desk lamp"] });
    const shelved = makeParcel({ id: "shelved", archived: true, items: ["Old kettle"] });
    const gone = makeParcel({ id: "gone", status: "returned", items: ["Spare kettle"] });
    const came = makeParcel({
      id: "came",
      status: "delivered",
      delivered_at: "2026-07-18T09:00:00Z",
      items: ["Brava bin"],
    });
    const blank = makeParcel({ id: "blank", merchant: "Example Shop" });
    const suggestions = [
      suggestion("s1", box("b1", "2026-07-18"), [order, lamp, shelved, gone, came, blank]),
    ];
    assert.deepEqual(
      alsoPossible(suggestions, "b1", "order").map((parcel) => parcel.id),
      ["lamp", "came"],
    );
    assert.deepEqual(alsoPossible(suggestions, "lamp", "b1"), []);
    assert.deepEqual(alsoPossible(undefined, "b1", "order"), []);
  });

  test("explain what isn't confirmed, from either side", () => {
    const one = possibleMatches([suggestion("s1", box("b1", "2026-07-18"), [order])], "order");
    const two = possibleMatches(
      [suggestion("s1", box("b1", "2026-07-18"), [order]), suggestion("s2", box("b2", "2026-07-19"), [order])],
      "order",
    );
    assert.equal(
      possibleHint(two),
      "Not confirmed: the carrier's e-mails for these deliveries don't name an order. Merge the one this package came in, or rule out the others.",
    );
    assert.equal(
      possibleHint(one),
      "Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge it if this package came in it, or rule it out.",
    );
    const delivered = box("b1", "2026-07-18");
    const lamp = makeParcel({ id: "lamp", merchant: "Example Shop", items: ["Lumen desk lamp"] });
    const orders = possibleMatches([suggestion("s1", delivered, [order, lamp])], "b1");
    assert.equal(
      possibleHint(orders),
      "Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge the order that came in it, or rule out the others.",
    );
    assert.equal(
      possibleHint(orders.slice(0, 1)),
      "Not confirmed: the carrier's e-mails for this delivery don't name an order. Merge the order if it came in it, or rule it out.",
    );
    const stem = makeParcel({ id: "stem", merchant: "Example Shop" });
    const shared = possibleMatches(
      [
        suggestion("s1", box("b1", "2026-07-18"), [stem], "same_reference"),
        suggestion("s2", box("b2", "2026-07-18"), [stem], "same_reference"),
      ],
      "stem",
    );
    assert.equal(
      possibleHint(shared),
      "Not confirmed: this parcel's e-mails name only a shipment that several packages share. Merge the package they're about, or rule out the others.",
    );
    assert.equal(
      possibleHint(shared.slice(0, 1)),
      "Not confirmed: this parcel's e-mails name only a shipment reference. Merge the package if they're about it, or rule it out.",
    );
    assert.equal(
      possibleHint(possibleMatches([suggestion("s1", delivered, [stem], "same_reference")], "b1")),
      "Not confirmed: an e-mail names only the shipment this package is part of. Merge it if it's about this package, or rule it out.",
    );
  });
});
