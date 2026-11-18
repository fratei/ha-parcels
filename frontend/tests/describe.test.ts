import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { candidateLabel, chipMeta, describeParcel } from "../src/describe.ts";
import { formatDate, formatDateRange, type LocaleOptions } from "../src/format.ts";
import type { Placement } from "../src/placement.ts";
import type { Parcel } from "../src/types.ts";
import { makeParcel } from "./helpers.ts";

const GB: LocaleOptions = { language: "en-GB", hour12: false, timeZone: "Europe/Lisbon" };
const DAY = "2026-07-14";
const shop = makeParcel({ merchant: "Example Shop", carrier: "dhl", tracking_number: "TEST0001" });
const windowed = makeParcel({ ...shop, window_start: "13:00", window_end: "15:00" });
const span: Placement = { kind: "eta", from: "2026-07-14", to: "2026-07-16" };
const MERGED = { origin: "o2", at: "2026-07-14T10:00:00Z", reason: "same_tracking" };

function on(kind: Placement["kind"]): Placement {
  return { kind, from: DAY, to: DAY };
}

describe("describeParcel", () => {
  test("says what happened on the chip's day", () => {
    const day = formatDate(DAY, GB);
    const text = (status: Parcel["status"], kind: Placement["kind"]): string =>
      describeParcel({ ...windowed, status }, { locale: GB, placement: on(kind) });
    assert.equal(text("delivered", "delivered"), `Example Shop, carrier DHL, delivered ${day}`);
    assert.equal(text("returned", "returned"), `Example Shop, carrier DHL, returned ${day}`);
    assert.equal(
      text("ready_for_pickup", "pickup"),
      `Example Shop, carrier DHL, ready for pickup since ${day}, 13:00–15:00`,
    );
    assert.equal(
      text("attempted", "status"),
      `Example Shop, carrier DHL, Delivery attempted on ${day}, 13:00–15:00`,
    );
    assert.equal(
      describeParcel(windowed, { locale: GB, placement: span }),
      `Example Shop, carrier DHL, In transit, expected ${formatDateRange(span.from, span.to, GB)}, 13:00–15:00`,
    );
    assert.equal(describeParcel(shop, { locale: GB }), "Example Shop, carrier DHL, In transit");
  });

  test("adds the badges, privacy and continuation marks", () => {
    const parcel = makeParcel({ ...shop, ai: true, auto_merged: MERGED, private: true });
    assert.equal(
      describeParcel(parcel, { locale: GB, continuesBefore: true, continuesAfter: true }),
      "Example Shop, carrier DHL, In transit, found by the local AI, merged automatically, please check, " +
        "private, started before this week, continues after this week",
    );
  });

  test("says when a delivery was only inferred", () => {
    const parcel = makeParcel({ ...shop, status: "delivered", inferred: true });
    assert.equal(
      describeParcel(parcel, { locale: GB }),
      "Example Shop, carrier DHL, Delivered, delivery inferred, please check",
    );
  });

  test("reveals nothing but the carrier and status of a restricted parcel", () => {
    const parcel = makeParcel({
      carrier: "dhl",
      restricted: true,
      private: true,
      ai: true,
      auto_merged: MERGED,
      inferred: true,
    });
    assert.equal(describeParcel(parcel, { locale: GB }), "Private parcel, carrier DHL, In transit, private");
    assert.equal(chipMeta(parcel, { locale: GB }), "DHL");
  });
});

describe("carrier and shop", () => {
  const untracked = makeParcel({ merchant: "Example Shop", window_start: "13:00", window_end: "15:00" });

  test("say when the carrier isn't known yet instead of naming the shop", () => {
    assert.equal(
      describeParcel(untracked, { locale: GB }),
      "Example Shop, carrier not known yet, In transit, 13:00–15:00",
    );
    assert.equal(
      chipMeta(untracked, { locale: GB, placement: span }),
      "13:00–15:00 · Carrier not known yet",
    );
    assert.equal(
      chipMeta(untracked, { locale: GB, showStatus: true }),
      "In transit · 13:00–15:00 · Carrier not known yet",
    );
  });

  test("keep quiet about the carrier of another user's private parcel", () => {
    const parcel = makeParcel({ restricted: true, private: true });
    assert.equal(describeParcel(parcel, { locale: GB }), "Private parcel, In transit, private");
    assert.equal(chipMeta(parcel, { locale: GB }), "");
  });
});

describe("shipment boxes", () => {
  test("count the packages", () => {
    assert.equal(
      describeParcel(shop, { locale: GB, count: 4 }),
      "Example Shop, 4 packages, carrier DHL, In transit",
    );
    assert.equal(chipMeta(shop, { locale: GB, count: 4, showStatus: true }), "In transit · 4 packages · DHL");
    assert.equal(chipMeta(shop, { locale: GB, count: 1 }), "DHL");
  });
});

describe("PIN codes", () => {
  test("are hinted at, never shown", () => {
    const parcel = makeParcel({ ...shop, has_code: true, pickup_code: "4711" });
    const text = describeParcel(parcel, { locale: GB });
    assert.equal(text, "Example Shop, carrier DHL, In transit, PIN in the details");
    assert.equal(chipMeta(parcel, { locale: GB, showStatus: true }), "In transit · DHL");
    assert.equal(
      describeParcel({ ...parcel, restricted: true }, { locale: GB }),
      "Private parcel, carrier DHL, In transit, private",
    );
  });
});

describe("chipMeta", () => {
  test("shows the carrier and window, plus the status or dates when asked", () => {
    assert.equal(chipMeta(windowed, { locale: GB, placement: span }), "DHL · 13:00–15:00");
    assert.equal(chipMeta(windowed, { locale: GB, placement: on("delivered") }), "DHL");
    assert.equal(chipMeta(shop, { locale: GB, showStatus: true }), "In transit · DHL");
    assert.equal(
      chipMeta(windowed, { locale: GB, placement: span, showRange: true }),
      `DHL · ${formatDateRange(span.from, span.to, GB)} · 13:00–15:00`,
    );
    assert.equal(chipMeta(shop, { locale: GB, placement: on("eta"), showRange: true }), "DHL");
    assert.equal(chipMeta(makeParcel({ carrier: "dhl" }), { locale: GB }), "");
  });
});

describe("candidateLabel", () => {
  test("tells parcels apart by name, carrier, number and date", () => {
    const eta = makeParcel({ ...shop, eta_start: span.from, eta_end: span.to });
    assert.equal(
      candidateLabel(eta, GB),
      `Example Shop · DHL · TEST0001 · ${formatDateRange(span.from, span.to, GB)}`,
    );
    assert.equal(
      candidateLabel(makeParcel({ tracking_number: "TEST0002", status: "ordered" }), GB),
      "TEST0002 · Ordered",
    );
    assert.equal(
      candidateLabel(makeParcel({ carrier: "dhl", tracking_number: "TEST0003", status: "shipped" }), GB),
      "DHL · TEST0003 · Shipped",
    );
  });
});
