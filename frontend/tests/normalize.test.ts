import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  normalizeDetails,
  normalizeParcel,
  normalizeReviewItem,
  normalizeSettings,
  normalizeSnapshot,
} from "../src/normalize.ts";
import { makeParcel } from "./helpers.ts";

const NOW = Date.UTC(2026, 6, 14, 23, 30);

describe("normalizeSnapshot", () => {
  test("survives an empty or broken payload", () => {
    assert.deepEqual(normalizeSnapshot(null, NOW), {
      parcels: [],
      review: [],
      filtered: [],
      settings: {
        user_is_admin: false,
        ai_enabled: false,
        ai_mode: "off",
        dashboard_url: "",
        seventeentrack: false,
        time_zone: "UTC",
        today: "2026-07-14",
      },
    });
    assert.deepEqual(normalizeSnapshot({ parcels: "nope", review: [null, 3], filtered: {} }, NOW).parcels, []);
  });

  test("keeps the server's today and works it out only when it's missing", () => {
    assert.equal(normalizeSettings({ time_zone: "Europe/Lisbon", today: "2026-07-10" }, NOW).today, "2026-07-10");
    assert.equal(normalizeSettings({ time_zone: "Europe/Lisbon" }, NOW).today, "2026-07-15");
    assert.equal(normalizeSettings({ time_zone: "Europe/Lisbon", today: "15/07/2026" }, NOW).today, "2026-07-15");
  });

  test("reads settings strictly", () => {
    assert.deepEqual(
      normalizeSettings(
        {
          user_is_admin: "true",
          ai_enabled: true,
          ai_mode: "auto",
          dashboard_url: "/parcels",
          seventeentrack: true,
          time_zone: "Europe/Lisbon",
          today: "2026-07-15",
        },
        NOW,
      ),
      {
        user_is_admin: false,
        ai_enabled: true,
        ai_mode: "auto",
        dashboard_url: "/parcels",
        seventeentrack: true,
        time_zone: "Europe/Lisbon",
        today: "2026-07-15",
      },
    );
    assert.equal(normalizeSettings({ ai_mode: "always" }, NOW).ai_mode, "off");
  });

  test("drops items without an id", () => {
    const snapshot = normalizeSnapshot(
      {
        parcels: [{ id: "p1", status: "shipped" }, { status: "shipped" }, { id: 7 }, { id: "" }],
        review: [{ id: "r1", subject: "Your order" }, { subject: "No id" }],
        filtered: [{ id: "f1", sender: "news@example.com" }, "f2"],
      },
      NOW,
    );
    assert.deepEqual(
      snapshot.parcels.map((parcel) => parcel.id),
      ["p1"],
    );
    assert.deepEqual(
      snapshot.review.map((item) => item.id),
      ["r1"],
    );
    assert.deepEqual(snapshot.filtered, [
      { id: "f1", created: "", received: null, sender: "news@example.com", sender_domain: "", subject: "" },
    ]);
  });
});

describe("normalizeParcel", () => {
  test("fills in missing fields", () => {
    assert.deepEqual(normalizeParcel({ id: "p1", status: "shipped" }), makeParcel({ status: "shipped" }));
  });

  test("keeps a full parcel as it is", () => {
    const parcel = makeParcel({
      merchant: "Example Shop",
      carrier: "dhl",
      carrier_name: "DHL",
      tracking_number: "TEST0001",
      tracking_url: "https://tracking.example.com/TEST0001",
      status: "out_for_delivery",
      status_time: "2026-07-14T08:00:00+00:00",
      eta_start: "2026-07-14",
      eta_end: "2026-07-15",
      window_start: "13:00",
      window_end: "15:00",
      pickup_point: "Example Locker 12",
      pickup_code: "123456",
      order_numbers: ["ORDER-1"],
      items: ["Blue mug"],
      private: true,
      owners: ["user-1"],
      source: "seventeentrack",
      ai: true,
      auto_merged: { origin: "o2", at: "2026-07-14T08:00:00+00:00", reason: "Same tracking number" },
      provisional: true,
      archived: true,
      origins: ["o1", "o2"],
      restricted: false,
    });
    assert.deepEqual(normalizeParcel(JSON.parse(JSON.stringify(parcel))), parcel);
  });

  test("never trusts the types it gets", () => {
    const parcel = normalizeParcel({
      id: "p1",
      status: "teleported",
      merchant: 42,
      items: ["Blue mug", 3, null],
      private: "yes",
      restricted: 1,
      source: "pigeon",
      auto_merged: { at: "2026-07-14T08:00:00Z" },
    });
    assert.ok(parcel);
    assert.equal(parcel.status, "teleported");
    assert.equal(parcel.merchant, null);
    assert.deepEqual(parcel.items, ["Blue mug"]);
    assert.equal(parcel.private, false);
    assert.equal(parcel.restricted, false);
    assert.equal(parcel.source, "parser");
    assert.equal(parcel.auto_merged, null);
    assert.equal(normalizeParcel([]), null);
    assert.equal(normalizeParcel("p1"), null);
  });
});

describe("normalizeReviewItem", () => {
  test("reads the item and its suggestion", () => {
    const item = normalizeReviewItem({
      id: "r1",
      created: "2026-07-14T08:00:00+00:00",
      received: null,
      sender: "orders@shop.example.com",
      sender_domain: "shop.example.com",
      subject: "Your order has shipped",
      mailbox_owner: "Test User",
      reason: "unknown_sender",
      authenticated: "yes",
      source: "ai",
      suggestion: { kind: "shipped", tracking_numbers: ["TEST0001", 2], carrier: "ups" },
    });
    assert.ok(item);
    assert.equal(item.authenticated, false);
    assert.equal(item.source, "ai");
    assert.deepEqual(item.suggestion, {
      kind: "shipped",
      merchant: null,
      carrier: "ups",
      tracking_numbers: ["TEST0001"],
      order_numbers: [],
      eta_start: null,
      eta_end: null,
      window_start: null,
      window_end: null,
      pickup_point: null,
      pickup_code: null,
      items: [],
    });
    const plain = normalizeReviewItem({ id: "r2", authenticated: true, source: "manual", suggestion: "x" });
    assert.ok(plain);
    assert.equal(plain.authenticated, true);
    assert.equal(plain.source, "parser");
    assert.equal(plain.suggestion, null);
  });
});

describe("normalizeDetails", () => {
  test("needs a parcel", () => {
    assert.equal(normalizeDetails({ timeline: [] }), null);
    assert.equal(normalizeDetails(null), null);
  });

  test("reads the timeline, orders and origins", () => {
    const details = normalizeDetails({
      parcel: { id: "p1", status: "delivered" },
      timeline: [{ time: "2026-07-14T08:00:00Z", status: "delivered", source: "ai", label: "Delivered" }, 5],
      orders: [{ id: "o1", number: "ORDER-1", parcel_ids: ["p1"] }],
      origins: [{ id: "m1", label: "E-mail from Example Shop", source: "parser", time: null }, { label: "No id" }],
    });
    assert.ok(details);
    assert.equal(details.parcel.status, "delivered");
    assert.deepEqual(details.timeline, [
      { time: "2026-07-14T08:00:00Z", status: "delivered", source: "ai", label: "Delivered" },
    ]);
    assert.deepEqual(details.orders, [
      { id: "o1", merchant: null, number: "ORDER-1", placed_at: null, parcel_ids: ["p1"] },
    ]);
    assert.deepEqual(details.origins, [
      { id: "m1", label: "E-mail from Example Shop", source: "parser", time: null },
    ]);
  });
});
