import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  candidateLabel,
  candidateLines,
  numberTail,
  chipMeta,
  chipPin,
  couldAlsoBe,
  describeParcel,
  itemsSummary,
  possiblyLine,
  sellerLine,
} from "../src/describe.ts";
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

  test("says when the local AI filled in details", () => {
    const parcel = makeParcel({ ...shop, ai_filled: true });
    assert.equal(
      describeParcel(parcel, { locale: GB }),
      "Example Shop, carrier DHL, In transit, details filled in by the local AI",
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
      ai_filled: true,
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
    assert.equal(chipMeta(shop, { locale: GB, count: 4, showStatus: true }), "DHL · In transit · 4 packages");
    assert.equal(chipMeta(shop, { locale: GB, count: 1 }), "DHL");
  });
});

describe("PIN codes", () => {
  test("show on the carrier line while the list has them", () => {
    const parcel = makeParcel({ ...shop, has_code: true, pickup_code: "4711" });
    assert.equal(describeParcel(parcel, { locale: GB }), "Example Shop, carrier DHL, In transit, PIN 4711");
    assert.equal(chipPin(parcel), "PIN 4711");
    assert.equal(chipMeta(parcel, { locale: GB, showStatus: true }), "DHL · In transit");
  });

  test("are hinted at when only the details have them", () => {
    const parcel = makeParcel({ ...shop, status: "delivered", inferred: true, has_code: true });
    assert.equal(chipPin(parcel), null);
    assert.match(describeParcel(parcel, { locale: GB }), /, PIN in the details$/);
  });

  test("never show for a restricted parcel", () => {
    const parcel = makeParcel({ ...shop, has_code: true, pickup_code: "4711", restricted: true });
    assert.equal(chipPin(parcel), null);
    assert.equal(
      describeParcel(parcel, { locale: GB }),
      "Private parcel, carrier DHL, In transit, private",
    );
  });
});

describe("sellerLine", () => {
  test("is the shop, else says the seller isn't known", () => {
    assert.equal(sellerLine(shop), "Example Shop");
    assert.equal(sellerLine(makeParcel({ carrier: "dhl", tracking_number: "TEST0001" })), "Unknown seller");
    assert.equal(sellerLine(makeParcel({ ...shop, restricted: true })), "Private parcel");
    assert.equal(
      describeParcel(makeParcel({ carrier: "dhl" }), { locale: GB }),
      "Unknown seller, carrier DHL, In transit",
    );
  });
});

describe("itemsSummary", () => {
  test("names one item in full", () => {
    assert.equal(itemsSummary(makeParcel({ items: ["  Lumen desk lamp  with dimmer "] })), "Lumen desk lamp with dimmer");
  });

  test("counts several items and keeps their names short", () => {
    assert.equal(
      itemsSummary(makeParcel({ items: ["Lumen desk lamp with dimmer", "Brava bin 30 L"] })),
      "2 items · Lumen desk lamp, Brava bin 30",
    );
    assert.equal(
      itemsSummary(
        makeParcel({
          items: ["Zeta Z2 plug, white", "Brava bin 30 L", "2 x AA batteries", "Brava liners (pack of 20)"],
        }),
      ),
      "4 items · Zeta, Brava, AA batteries, Brava",
    );
  });

  test("stops after eight names", () => {
    const items = Array.from({ length: 10 }, (_, index) => `Item${index + 1} thing`);
    assert.equal(
      itemsSummary(makeParcel({ items })),
      "10 items · Item1, Item2, Item3, Item4, Item5, Item6, Item7, Item8, …",
    );
  });

  test("is null without items or for a restricted parcel", () => {
    assert.equal(itemsSummary(makeParcel({ items: [" ", ""] })), null);
    assert.equal(itemsSummary(makeParcel({ items: ["Brava bin"], restricted: true })), null);
  });

  test("is in the description", () => {
    assert.equal(
      describeParcel(makeParcel({ ...shop, items: ["Brava bin 30 L", "Zeta Z2 plug"] }), { locale: GB }),
      "Example Shop, carrier DHL, In transit, 2 items · Brava bin 30, Zeta Z2 plug",
    );
  });
});

describe("possiblyLine", () => {
  const lamp = makeParcel({ id: "a", items: ["Lumen desk lamp with dimmer", "Brava bin 30 L"] });
  const plug = makeParcel({ id: "b", items: ["2 x Zeta Z2 plug, white"] });

  test("names the items of the one parcel the box may be", () => {
    assert.equal(possiblyLine([lamp]), "Possibly: 2 items · Lumen desk lamp, Brava bin 30");
  });

  test("offers each candidate's first item when there are several", () => {
    assert.equal(possiblyLine([lamp, plug]), "Possibly: Lumen desk lamp +1 or Zeta Z2 plug");
  });

  test("is null when no candidate's items are known or may be shown", () => {
    assert.equal(possiblyLine([]), null);
    assert.equal(possiblyLine([makeParcel({ id: "c", items: [] })]), null);
    assert.equal(possiblyLine([{ ...plug, restricted: true }]), null);
  });

  test("is announced only when the box's own items aren't known", () => {
    const tracked = makeParcel({ ...shop, items: [] });
    assert.equal(
      describeParcel(tracked, { locale: GB, possibly: "Possibly: Brava bin" }),
      "Example Shop, carrier DHL, In transit, Possibly: Brava bin",
    );
    assert.equal(
      describeParcel({ ...tracked, items: ["Zeta Z2 plug"] }, { locale: GB, possibly: "Possibly: Brava bin" }),
      "Example Shop, carrier DHL, In transit, Zeta Z2 plug",
    );
  });
});

describe("chipMeta", () => {
  test("shows the carrier and window, plus the status or dates when asked", () => {
    assert.equal(chipMeta(windowed, { locale: GB, placement: span }), "DHL · 13:00–15:00");
    assert.equal(chipMeta(windowed, { locale: GB, placement: on("delivered") }), "DHL");
    assert.equal(chipMeta(shop, { locale: GB, showStatus: true }), "DHL · In transit");
    assert.equal(
      chipMeta(windowed, { locale: GB, placement: span, showRange: true }),
      `DHL · ${formatDateRange(span.from, span.to, GB)} · 13:00–15:00`,
    );
    assert.equal(chipMeta(shop, { locale: GB, placement: on("eta"), showRange: true }), "DHL");
    assert.equal(chipMeta(makeParcel({ carrier: "dhl" }), { locale: GB }), "DHL");
  });
});

describe("merge candidates", () => {
  const kettle = makeParcel({
    merchant: "Example Shop",
    carrier: "dhl",
    tracking_number: "JD0000000012345",
    order_numbers: ["111-0000001-0004321"],
    items: ["Blue kettle", "Tea towel"],
    eta_start: span.from,
    eta_end: span.to,
  });
  const range = formatDateRange(span.from, span.to, GB);

  test("numbers are cut to their last five letters or digits", () => {
    assert.equal(numberTail("JD0000000012345"), "…12345");
    assert.equal(numberTail("111-0000001-0004321"), "…04321");
    assert.equal(numberTail("AB-123"), "AB-123");
    assert.equal(numberTail("  "), null);
  });

  test("a package number keeps its underscore", () => {
    assert.equal(numberTail("Qx7Tm4Rb_2"), "…m4Rb_2");
    assert.equal(numberTail("Qx7Tm4Rb_12"), "…4Rb_12");
  });

  test("tell parcels of one shop apart by items, carrier, number, order and date", () => {
    assert.deepEqual(candidateLines(kettle, GB), {
      title: "Example Shop",
      when: `In transit · ${range}`,
      carrier: "DHL · No. …12345 · Order …04321",
      items: "2 items · Blue kettle, Tea towel",
      emails: null,
      noItems: "Items not known yet",
    });
    assert.equal(
      candidateLabel(kettle, GB),
      `Example Shop · 2 items · Blue kettle, Tea towel · DHL · No. …12345 · Order …04321 · In transit · ${range}`,
    );
  });

  test("an expected parcel shows its time window", () => {
    const windowedKettle = makeParcel({ ...kettle, window_start: "13:00", window_end: "15:00" });
    assert.equal(candidateLines(windowedKettle, GB).when, `In transit · ${range} · 13:00–15:00`);
  });

  test("a delivered parcel shows the day and time it arrived", () => {
    const delivered = makeParcel({
      ...kettle,
      status: "delivered",
      delivered_at: "2026-07-13T09:30:00Z",
      window_start: "09:00",
      window_end: "11:00",
    });
    assert.equal(candidateLines(delivered, GB).when, "Delivered · Mon 13 Jul at 10:30");
    const inferred = makeParcel({ ...delivered, inferred: true });
    assert.equal(candidateLines(inferred, GB).when, "Delivered · Mon 13 Jul");
  });

  test("a delivery known only by its day shows no time", () => {
    const daily = makeParcel({ ...kettle, status: "delivered", delivered_at: "2026-07-12T23:00:00Z" });
    assert.equal(candidateLines(daily, GB).when, "Delivered · Mon 13 Jul");
  });

  test("say who wrote about a candidate, first sender first", () => {
    const told = makeParcel({
      ...kettle,
      senders: [
        { name: "Example Carrier", source: "email", carrier: true, count: 2 },
        { name: "example.com", source: "email", carrier: false, count: 1 },
        { name: "17TRACK", source: "seventeentrack", carrier: false, count: 3 },
      ],
    });
    assert.equal(
      candidateLines(told, GB).emails,
      "2 e-mails from Example Carrier, 1 e-mail from example.com, 3 updates from 17TRACK",
    );
    const many = makeParcel({
      senders: ["a.example", "b.example", "c.example", "d.example", "e.example"].map((name) => ({
        name,
        source: "email" as const,
        carrier: false,
        count: 1,
      })),
    });
    assert.equal(
      candidateLines(many, GB).emails,
      "1 e-mail from a.example, 1 e-mail from b.example, 1 e-mail from c.example, +2 more",
    );
    const update = makeParcel({ senders: [{ name: "Parcel app", source: "parcelapp", carrier: false, count: 1 }] });
    assert.equal(candidateLines(update, GB).emails, "1 update from Parcel app");
  });

  test("a delivery known only from its carrier says why its items aren't known", () => {
    const carrierMail = { name: "Example Carrier", source: "email" as const, carrier: true, count: 2 };
    const tracking = { name: "17TRACK", source: "seventeentrack" as const, carrier: false, count: 1 };
    const shopMail = { name: "example.com", source: "email" as const, carrier: false, count: 1 };
    const box = makeParcel({ carrier: "dhl", tracking_number: "JD0000000067890" });
    const noItems = (senders: Parcel["senders"]): string =>
      candidateLines(makeParcel({ ...box, senders }), GB).noItems;
    assert.equal(noItems([carrierMail]), "Carrier e-mails don't list items");
    assert.equal(noItems([carrierMail, tracking]), "Carrier e-mails don't list items");
    assert.equal(noItems([tracking]), "Tracking updates don't list items");
    assert.equal(noItems([carrierMail, shopMail]), "Items not known yet");
    assert.equal(noItems([]), "Items not known yet");
  });

  test("an item-less delivery names the other orders it could be", () => {
    const lamp = makeParcel({
      id: "lamp",
      merchant: "Example Shop",
      order_numbers: ["111-0000001-0000002"],
      items: ["Lumen desk lamp", "Bulb"],
    });
    const hose = makeParcel({ id: "hose", merchant: "Example Shop", items: ["Garden hose"] });
    const bare = makeParcel({ id: "bare", merchant: "Other Shop", order_numbers: ["A-0000777"] });
    assert.equal(
      couldAlsoBe([lamp, hose, bare]),
      "Could also be: Lumen desk lamp +1 (order …00002); Garden hose; Other Shop (order …00777)",
    );
    const extra = makeParcel({ id: "extra", items: ["Brava bin"] });
    assert.equal(
      couldAlsoBe([lamp, hose, bare, extra]),
      "Could also be: Lumen desk lamp +1 (order …00002); Garden hose; Other Shop (order …00777); +1 more",
    );
    assert.equal(couldAlsoBe([]), null);
  });

  test("a delivery whose source gave no date says so, not the day it's kept on", () => {
    const kept = makeParcel({
      ...kettle,
      status: "delivered",
      status_time: "2026-07-12T23:00:00.000010Z",
      status_undated: true,
      delivered_at: "2026-07-12T23:00:00.000010Z",
      delivered_undated: true,
    });
    assert.equal(candidateLines(kept, GB).when, "Delivered · date not known");
    const dayless = makeParcel({ ...kettle, status: "delivered", status_undated: true, delivered_undated: true });
    assert.equal(candidateLines(dayless, GB).when, "Delivered · date not known");
  });

  test("say what isn't known yet", () => {
    const bare = makeParcel({ tracking_number: "TEST0002", status: "ordered" });
    assert.deepEqual(candidateLines(bare, GB), {
      title: "Unknown seller",
      when: "Ordered",
      carrier: "Carrier not known yet · No. …T0002",
      items: null,
      emails: null,
      noItems: "Items not known yet",
    });
    assert.equal(
      candidateLabel(bare, GB),
      "Unknown seller · Carrier not known yet · No. …T0002 · Ordered",
    );
  });
});
