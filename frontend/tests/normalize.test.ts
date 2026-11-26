import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  normalizeDetails,
  normalizeMergeSuggestion,
  normalizeParcel,
  normalizeRetryResult,
  normalizeReviewItem,
  normalizeSettings,
  normalizeSnapshot,
  normalizeUnignoreResult,
} from "../src/normalize.ts";
import { makeOrigin, makeParcel } from "./helpers.ts";

const NOW = Date.UTC(2026, 6, 14, 23, 30);

describe("normalizeSnapshot", () => {
  test("survives an empty or broken payload", () => {
    assert.deepEqual(normalizeSnapshot(null, NOW), {
      parcels: [],
      returns: [],
      review: [],
      merge_suggestions: [],
      filtered: [],
      ignored_senders: [],
      unread_emails: { count: 0, senders: [], unnamed: 0, newest: null },
      settings: {
        user_is_admin: false,
        ai_enabled: false,
        ai_mode: "off",
        ai_queue: 0,
        ai_queue_seconds: null,
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
          ai_queue: 3,
          ai_queue_seconds: 159,
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
        ai_queue: 3,
        ai_queue_seconds: 159,
        dashboard_url: "/parcels",
        seventeentrack: true,
        time_zone: "Europe/Lisbon",
        today: "2026-07-15",
      },
    );
    assert.equal(normalizeSettings({ ai_mode: "always" }, NOW).ai_mode, "off");
    for (const queue of ["3", -1, 2.5, Number.NaN, Infinity, null]) {
      assert.equal(normalizeSettings({ ai_queue: queue }, NOW).ai_queue, 0, String(queue));
    }
    for (const wait of ["60", -1, Number.NaN, Infinity]) {
      assert.equal(normalizeSettings({ ai_queue_seconds: wait }, NOW).ai_queue_seconds, null, String(wait));
    }
    assert.equal(normalizeSettings({ ai_queue_seconds: 0 }, NOW).ai_queue_seconds, 0);
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
      {
        id: "f1",
        created: "",
        received: null,
        sender: "news@example.com",
        sender_domain: "",
        subject: "",
        removed: false,
      },
    ]);
  });

  test("tells e-mails removed from a parcel apart from filtered ones", () => {
    const filtered = normalizeSnapshot(
      { filtered: [{ id: "f1", removed: true }, { id: "f2", removed: "yes" }] },
      NOW,
    ).filtered;
    assert.deepEqual(
      filtered.map((item) => item.removed),
      [true, false],
    );
  });

  test("reads the e-mails Parcels couldn't read strictly", () => {
    assert.deepEqual(
      normalizeSnapshot(
        {
          unread_emails: {
            count: 6,
            senders: ["ups.com", "", 3, null, "a.example"],
            unnamed: 2,
            newest: "2026-11-17T05:00:00+00:00",
          },
        },
        NOW,
      ).unread_emails,
      { count: 6, senders: ["ups.com", "a.example"], unnamed: 2, newest: "2026-11-17T05:00:00+00:00" },
    );
    for (const raw of [
      null,
      "6",
      [],
      { count: "6", senders: "ups.com", unnamed: "1", newest: 5 },
      { count: -1, unnamed: -1 },
      { count: 2.5, unnamed: 1.5 },
    ]) {
      assert.deepEqual(
        normalizeSnapshot({ unread_emails: raw }, NOW).unread_emails,
        { count: 0, senders: [], unnamed: 0, newest: null },
        JSON.stringify(raw),
      );
    }
  });
});

describe("ignored senders", () => {
  test("lists them with their domain, and reads what stopping did", () => {
    const snapshot = normalizeSnapshot(
      { ignored_senders: [{ domain: "example.net", updated: "2026-07-14T08:00:00+00:00" }, { updated: 1 }, "x"] },
      NOW,
    );
    assert.deepEqual(snapshot.ignored_senders, [{ domain: "example.net", updated: "2026-07-14T08:00:00+00:00" }]);
    assert.deepEqual(normalizeUnignoreResult({ domain: "example.net", rechecking: 2 }), {
      domain: "example.net",
      rechecking: 2,
    });
    assert.deepEqual(normalizeUnignoreResult(null), { domain: "", rechecking: 0 });
  });
});

describe("normalizeRetryResult", () => {
  test("counts what trying again did, and nothing from a broken answer", () => {
    assert.deepEqual(normalizeRetryResult({ read: 2, failed: 1, gone: 3 }), { read: 2, failed: 1, gone: 3 });
    assert.deepEqual(normalizeRetryResult({ read: "2", failed: -1, gone: 1.5 }), { read: 0, failed: 0, gone: 0 });
    assert.deepEqual(normalizeRetryResult(null), { read: 0, failed: 0, gone: 0 });
  });
});

describe("normalizeParcel", () => {
  test("fills in missing fields", () => {
    assert.deepEqual(normalizeParcel({ id: "p1", status: "shipped" }), makeParcel({ status: "shipped" }));
  });

  test("keeps a full parcel as it is", () => {
    const parcel = makeParcel({
      merchant: "Example Shop",
      seller: "Example Seller (Example Lda)",
      name: "Blue mug",
      carrier: "dhl",
      carrier_name: "DHL",
      tracking_number: "TEST0001",
      tracking_url: "https://tracking.example.com/TEST0001",
      status: "out_for_delivery",
      status_time: "2026-07-14T08:00:00+00:00",
      status_undated: true,
      status_timeless: true,
      eta_start: "2026-07-14",
      eta_end: "2026-07-15",
      window_start: "13:00",
      window_end: "15:00",
      eta_source: "parcelapp",
      delivered_undated: true,
      delivered_timeless: true,
      status_reported: true,
      next_attempt: "2026-07-15",
      collect_by: "2026-07-21",
      left_at: "locker",
      inferred: true,
      inferred_reason: "return",
      delivered_by_hand: true,
      pickup_point: "Example Locker 12",
      pickup_code: "123456",
      has_code: true,
      order_numbers: ["ORDER-1"],
      references: ["Ab3Cd5Ef7"],
      items: ["Blue mug"],
      private: true,
      owners: ["user-1"],
      source: "seventeentrack",
      ai: true,
      ai_filled: true,
      auto_merged: { origin: "o2", at: "2026-07-14T08:00:00+00:00", reason: "Same tracking number" },
      provisional: true,
      archived: true,
      origins: ["o1", "o2"],
      shipment_group: "p0",
      restricted: false,
      senders: [
        { name: "Example Shop", source: "email", carrier: false, count: 1 },
        { name: "DHL", source: "email", carrier: true, count: 2 },
        { name: "17TRACK", source: "seventeentrack", carrier: false, count: 1 },
      ],
      ordered_at: "2026-07-10T09:00:00+00:00",
      shipped_at: "2026-07-12T09:00:00+00:00",
      amazon_tracking: { delivered: "2026-07-14T09:27:00+00:00", timeless: true, place: "Vila Exemplo" },
    });
    assert.deepEqual(normalizeParcel(JSON.parse(JSON.stringify(parcel))), parcel);
  });

  test("reads who told about a parcel defensively", () => {
    const parcel = normalizeParcel({
      id: "p1",
      senders: [
        { name: "DHL", source: "email", carrier: true, count: 3 },
        { name: "Example Shop", source: "pigeon", carrier: "yes", count: -2 },
        { source: "email", count: 1 },
        { name: "", source: "email", count: 1 },
        "DHL",
      ],
      ordered_at: 3,
      shipped_at: "",
    });
    assert.ok(parcel);
    assert.deepEqual(parcel.senders, [
      { name: "DHL", source: "email", carrier: true, count: 3 },
      { name: "Example Shop", source: "email", carrier: false, count: 1 },
    ]);
    assert.equal(parcel.ordered_at, null);
    assert.equal(parcel.shipped_at, null);
    assert.deepEqual(normalizeParcel({ id: "p1", senders: "DHL" })?.senders, []);
  });

  test("reads why a delivery was inferred", () => {
    for (const reason of ["shop", "return", "quiet", "shipment"]) {
      assert.equal(normalizeParcel({ id: "p1", inferred: true, inferred_reason: reason })?.inferred_reason, reason);
    }
  });

  test("never trusts the types it gets", () => {
    const parcel = normalizeParcel({
      id: "p1",
      status: "teleported",
      merchant: 42,
      seller: 42,
      items: ["Blue mug", 3, null],
      private: "yes",
      restricted: 1,
      source: "pigeon",
      auto_merged: { at: "2026-07-14T08:00:00Z" },
      has_code: "yes",
      shipment_group: 7,
      inferred_reason: "pigeon",
      delivered_by_hand: "yes",
      name: 7,
      eta_source: "pigeon",
      status_undated: "yes",
      delivered_undated: 1,
      status_timeless: "yes",
      delivered_timeless: 1,
      status_reported: "yes",
      next_attempt: "tomorrow",
      collect_by: 20260721,
      left_at: "with the cat",
      amazon_tracking: { delivered: 5, timeless: true, place: "Vila Exemplo" },
    });
    assert.ok(parcel);
    assert.equal(parcel.status, "teleported");
    assert.equal(parcel.merchant, null);
    assert.equal(parcel.seller, null);
    assert.deepEqual(parcel.items, ["Blue mug"]);
    assert.equal(parcel.private, false);
    assert.equal(parcel.restricted, false);
    assert.equal(parcel.source, "parser");
    assert.equal(parcel.auto_merged, null);
    assert.equal(parcel.has_code, false);
    assert.equal(parcel.shipment_group, null);
    assert.equal(parcel.inferred_reason, null);
    assert.equal(parcel.delivered_by_hand, false);
    assert.equal(parcel.name, null);
    assert.equal(parcel.eta_source, "parser");
    assert.equal(parcel.status_undated, false);
    assert.equal(parcel.delivered_undated, false);
    assert.equal(parcel.status_timeless, false);
    assert.equal(parcel.delivered_timeless, false);
    assert.equal(parcel.status_reported, false);
    assert.equal(parcel.next_attempt, null);
    assert.equal(parcel.collect_by, null);
    assert.equal(parcel.left_at, null);
    assert.equal(normalizeParcel({ id: "p1", left_at: "Neighbour" })?.left_at, null);
    assert.equal(parcel.amazon_tracking, null);
    assert.deepEqual(
      normalizeParcel({ id: "p1", amazon_tracking: { delivered: "2026-07-14T09:27:00Z", timeless: "yes", place: 7 } })
        ?.amazon_tracking,
      { delivered: "2026-07-14T09:27:00Z", timeless: false, place: null },
    );
    assert.equal(normalizeParcel({ id: "p1", amazon_tracking: "2026-07-14" })?.amazon_tracking, null);
    assert.equal(normalizeParcel({ id: "p1", amazon_tracking: { delivered: "" } })?.amazon_tracking, null);
    assert.equal(normalizeParcel({ id: "p1", collect_by: "2026-02-30" })?.collect_by, null);
    assert.equal(normalizeParcel({ id: "p1", eta_source: 3 })?.eta_source, null);
    assert.equal(normalizeParcel({ id: "p1", eta_source: "" })?.eta_source, null);
    assert.equal(normalizeParcel([]), null);
    assert.equal(normalizeParcel("p1"), null);
  });
});

describe("normalizeMergeSuggestion", () => {
  const tracked = { id: "p1", merchant: "Example Shop", tracking_number: "TEST0001", status: "delivered" };
  const untracked = { id: "p2", merchant: "Example Shop", status: "shipped", inferred: true };

  test("reads a suggestion with its parcels", () => {
    const suggestion = normalizeMergeSuggestion({
      id: "m1",
      reason: "same_merchant_day",
      merchant: "Example Shop",
      day: "2026-07-14",
      parcel: tracked,
      candidates: [untracked, { status: "shipped" }],
    });
    assert.ok(suggestion);
    assert.equal(suggestion.parcel.tracking_number, "TEST0001");
    assert.deepEqual(
      suggestion.candidates.map((parcel) => [parcel.id, parcel.inferred]),
      [["p2", true]],
    );
    assert.equal(suggestion.day, "2026-07-14");
    assert.equal(suggestion.reason, "same_merchant_day");
  });

  test("drops a suggestion without its parcel or any candidate", () => {
    assert.equal(normalizeMergeSuggestion({ id: "m1", parcel: tracked, candidates: [] }), null);
    assert.equal(normalizeMergeSuggestion({ id: "m1", parcel: {}, candidates: [untracked] }), null);
    assert.equal(normalizeMergeSuggestion({ parcel: tracked, candidates: [untracked] }), null);
    const snapshot = normalizeSnapshot(
      {
        merge_suggestions: [
          { id: "m1", parcel: tracked, candidates: [untracked], day: "14/07/2026" },
          { id: "m2", parcel: tracked, candidates: "p2" },
        ],
      },
      NOW,
    );
    assert.deepEqual(
      snapshot.merge_suggestions.map((item) => [item.id, item.day]),
      [["m1", null]],
    );
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
      sender_org: "example.com",
      known_sender: true,
      subject: "Your order has shipped",
      mailbox_owner: "Test User",
      reason: "unknown_sender",
      authenticated: "yes",
      source: "ai",
      suggestion: {
        kind: "shipped",
        tracking_numbers: ["TEST0001", 2],
        carrier: "ups",
        amazon_shipment_id: "TESTSHIPMENT1",
      },
    });
    assert.ok(item);
    assert.equal(item.authenticated, false);
    assert.equal(item.source, "ai");
    assert.equal(item.sender_org, "example.com");
    assert.equal(item.known_sender, true);
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
      amazon_shipment_id: "TESTSHIPMENT1",
      reference: null,
    });
    const paack = normalizeReviewItem({ id: "r8", suggestion: { kind: "delivered", reference: "Ab3Cd5Ef7" } });
    assert.equal(paack?.suggestion?.reference, "Ab3Cd5Ef7");
    const plain = normalizeReviewItem({ id: "r2", authenticated: true, source: "manual", suggestion: "x" });
    assert.ok(plain);
    assert.equal(plain.authenticated, true);
    assert.equal(plain.source, "parser");
    assert.equal(plain.suggestion, null);
    assert.equal(plain.known_sender, false);
    assert.equal(plain.sender_org, "");
  });

  test("keeps the sender checks, the trusted-sender note and fills", () => {
    const item = normalizeReviewItem({
      id: "r3",
      trusted_sender: true,
      fill: true,
      checks: {
        headers: 2,
        servers: ["mx.example.net", "", 3],
        used: 1,
        dkim: "pass",
        dmarc: "fail",
        spf: 7,
        originals: 1,
      },
    });
    assert.ok(item);
    assert.equal(item.trusted_sender, true);
    assert.equal(item.fill, true);
    assert.deepEqual(item.checks, {
      headers: 2,
      servers: ["mx.example.net", "", ""],
      used: 1,
      dkim: "pass",
      dmarc: "fail",
      spf: "",
      originals: 1,
    });
    const odd = normalizeReviewItem({ id: "r4", checks: { headers: 1, servers: "x", used: 1 } });
    assert.ok(odd?.checks);
    assert.deepEqual(odd.checks.servers, []);
    assert.equal(odd.checks.used, null);
    const plain = normalizeReviewItem({ id: "r5", trusted_sender: "yes", fill: 1, checks: "x" });
    assert.ok(plain);
    assert.equal(plain.trusted_sender, false);
    assert.equal(plain.fill, false);
    assert.equal(plain.checks, null);
  });

  test("keeps only the codes of the checks an AI answer failed", () => {
    const item = normalizeReviewItem({
      id: "r6",
      errors: ["tracking_is_order", "Tracking IS order", 3, "x".repeat(41), "tracking_is_order", "eta_not_in_text"],
    });
    assert.ok(item);
    assert.deepEqual(item.errors, ["tracking_is_order", "eta_not_in_text"]);
    assert.deepEqual(normalizeReviewItem({ id: "r7", errors: "tracking_is_order" })?.errors, []);
  });

  test("keeps only the codes of the notes on an AI answer, apart from failed checks", () => {
    const item = normalizeReviewItem({
      id: "r8",
      errors: ["tracking_not_in_email"],
      notes: ["carrier_unproven", "Amazon", null, "carrier_unproven", "eta_from_text"],
    });
    assert.ok(item);
    assert.deepEqual(item.notes, ["carrier_unproven", "eta_from_text"]);
    assert.deepEqual(item.errors, ["tracking_not_in_email"]);
    assert.deepEqual(normalizeReviewItem({ id: "r9" })?.notes, []);
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
      timeline: [
        { time: "2026-07-14T08:00:00Z", status: "delivered", source: "ai", label: "Delivered", undated: "yes", timeless: "yes" },
        5,
        { time: "2026-07-15T08:00:00Z", status: "delivered", source: "inferred", label: "" },
        { time: "2026-07-15T09:00:00Z", status: "delivered", source: "inferred_return", label: "" },
        { time: "2026-07-15T10:00:00Z", status: "delivered", source: "inferred_shipment", label: "" },
        { time: "2026-07-16T08:00:00Z", status: "delivered", source: "pigeon", label: "" },
        { time: "2026-07-17T08:00:00Z", status: "delivered", source: "quiet", label: "" },
        { time: "2026-07-18T08:00:00Z", status: "in_transit", source: "parcelapp", label: "Sorted", undated: true },
        { time: "2026-07-19T00:00:00.00001Z", status: "delivered", source: "parcelapp", label: "Left", undated: true, timeless: true },
      ],
      orders: [{ id: "o1", number: "ORDER-1", parcel_ids: ["p1"] }],
      origins: [{ id: "m1", label: "E-mail from Example Shop", source: "parser", time: null }, { label: "No id" }],
      contradicted: ["p2", 3, "", null, "p3"],
      elsewhere: ["p4", {}, "", "p5"],
    });
    assert.ok(details);
    assert.equal(details.parcel.status, "delivered");
    assert.deepEqual(details.contradicted, ["p2", "p3"]);
    assert.deepEqual(details.elsewhere, ["p4", "p5"]);
    const flat = normalizeDetails({ parcel: { id: "p1" }, contradicted: "p2", elsewhere: "p4" });
    assert.deepEqual(flat?.contradicted, []);
    assert.deepEqual(flat?.elsewhere, []);
    assert.deepEqual(details.timeline, [
      { time: "2026-07-14T08:00:00Z", status: "delivered", source: "ai", label: "Delivered", undated: false, timeless: false },
      { time: "2026-07-15T08:00:00Z", status: "delivered", source: "inferred", label: "", undated: false, timeless: false },
      { time: "2026-07-15T09:00:00Z", status: "delivered", source: "inferred_return", label: "", undated: false, timeless: false },
      { time: "2026-07-15T10:00:00Z", status: "delivered", source: "inferred_shipment", label: "", undated: false, timeless: false },
      { time: "2026-07-16T08:00:00Z", status: "delivered", source: "parser", label: "", undated: false, timeless: false },
      { time: "2026-07-17T08:00:00Z", status: "delivered", source: "quiet", label: "", undated: false, timeless: false },
      { time: "2026-07-18T08:00:00Z", status: "in_transit", source: "parcelapp", label: "Sorted", undated: true, timeless: false },
      { time: "2026-07-19T00:00:00.00001Z", status: "delivered", source: "parcelapp", label: "Left", undated: true, timeless: true },
    ]);
    assert.deepEqual(details.orders, [
      { id: "o1", merchant: null, number: "ORDER-1", placed_at: null, parcel_ids: ["p1"] },
    ]);
    assert.deepEqual(details.origins, [makeOrigin({ id: "m1", label: "E-mail from Example Shop", time: null })]);
  });

  test("keeps what each e-mail said and added", () => {
    const origin = makeOrigin({
      id: "m2",
      label: "example.com",
      source: "ai",
      sender_name: "Example Shop",
      name: "Blue mug",
      time: "2026-07-14T08:00:00+00:00",
      status: "out_for_delivery",
      kind: "delayed",
      event_time: "2026-07-14T07:00:00+00:00",
      undated: true,
      timeless: true,
      dayless: true,
      eta_start: "2026-07-14",
      eta_end: "2026-07-15",
      window_start: "13:00",
      window_end: "15:00",
      carrier: "dhl",
      carrier_name: "DHL",
      tracking_number: "TEST0001",
      reference: "Ab3Cd5Ef7",
      merchant: "Example Shop",
      seller: "Example Seller",
      order_numbers: ["ORDER-1"],
      items: ["Blue mug", "Tea towel"],
      pickup_point: "Example Locker 12",
      shipment: [1, 2],
      email: true,
      edits: false,
      part_of: "m1",
      split_blocked: "shared_number",
    });
    const details = normalizeDetails({ parcel: { id: "p1" }, origins: [JSON.parse(JSON.stringify(origin))] });
    assert.deepEqual(details?.origins, [origin]);
  });

  test("never trusts an origin's types", () => {
    const details = normalizeDetails({
      parcel: { id: "p1" },
      origins: [
        { id: "m1", status: 3, kind: "", items: ["Blue mug", 7], shipment: [2, 1], split_blocked: 4, email: "yes", part_of: 2 },
        { id: "m2", shipment: [0, 2] },
        { id: "m3", shipment: [1.5, 2] },
        { id: "m4", shipment: "1/2" },
        { id: "m5", shipment: [1, 2, 3] },
        { id: "m6", shipment: [2, 2], edits: true, dayless: 1, timeless: "yes" },
      ],
    });
    assert.ok(details);
    const [first, ...rest] = details.origins;
    assert.ok(first);
    assert.equal(first.status, null);
    assert.equal(first.kind, null);
    assert.deepEqual(first.items, ["Blue mug"]);
    assert.equal(first.shipment, null);
    assert.equal(first.split_blocked, null);
    assert.equal(first.email, false);
    assert.equal(first.part_of, null);
    assert.deepEqual(
      rest.map((origin) => origin.shipment),
      [null, null, null, null, [2, 2]],
    );
    assert.equal(rest.at(-1)?.edits, true);
    assert.equal(rest.at(-1)?.dayless, false);
    assert.equal(rest.at(-1)?.timeless, false);
  });
});
