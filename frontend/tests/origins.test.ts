import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { formatDate, formatDateRange, formatDayTime, type LocaleOptions } from "../src/format.ts";
import {
  originEntries,
  originRows,
  originsTitle,
  restoreOutcome,
  rowIds,
  splitBlockedReason,
  type OriginRow,
} from "../src/origins.ts";
import type { OriginInfo } from "../src/types.ts";
import { makeOrigin } from "./helpers.ts";

const GB: LocaleOptions = { language: "en-GB", hour12: false, timeZone: "Europe/Lisbon" };
const T1 = "2026-07-14T09:30:00Z";
const T2 = "2026-07-15T07:10:00Z";
const T3 = "2026-07-15T16:45:00Z";
const T4 = "2026-07-16T11:20:00Z";

function email(overrides: Partial<OriginInfo>): OriginInfo {
  return makeOrigin({ source: "parser", email: true, label: "carrier.example", ...overrides });
}

function one(origin: OriginInfo): OriginRow {
  const rows = originRows([origin], GB);
  assert.equal(rows.length, 1);
  return rows[0]!;
}

describe("the e-mails of a parcel", () => {
  test("a row says who sent it, when, what it said and what it added", () => {
    const row = one(
      email({
        id: "msg:a#0",
        sender_name: "Example Express",
        time: T1,
        status: "in_transit",
        kind: "shipped",
        event_time: T1,
        eta_start: "2026-07-16",
        eta_end: "2026-07-17",
        window_start: "13:00",
        window_end: "15:00",
        carrier: "dpd",
        carrier_name: "DPD",
        tracking_number: "09981234567890",
        merchant: "Example Shop",
        seller: "Example Seller",
        order_numbers: ["ORD-112233", "ORD-445566"],
        items: ["Blue mug with a very long name that wraps", "Green teapot"],
        pickup_point: "Example Locker 12",
        reference: "REF-998877",
        shipment: [1, 2],
      }),
    );
    assert.deepEqual(row.ids, ["msg:a#0"]);
    assert.equal(row.lead, "msg:a#0");
    assert.equal(row.header, "Example Express");
    assert.equal(row.when, "Tue 14 Jul at 10:30");
    assert.equal(
      row.said,
      `Shipped · expected ${formatDateRange("2026-07-16", "2026-07-17", GB)} · 13:00–15:00`,
    );
    assert.deepEqual(row.facts, [
      "Shop: Example Shop",
      "Sold by Example Seller",
      "Order …12233",
      "Order …45566",
      "Shipment 1/2",
      "DPD No. …67890",
      "Reference …98877",
      "Pickup: Example Locker 12",
    ]);
    assert.deepEqual(row.items, ["Blue mug with a very long name that wraps", "Green teapot"]);
    assert.equal(row.ai, null);
    assert.equal(row.email, true);
    assert.equal(row.edits, false);
    assert.equal(row.splitBlocked, null);
  });

  test("never show an Amazon shipment ID, only which shipment it is", () => {
    const row = one(email({ shipment: [2, 3] }));
    assert.deepEqual(row.facts, ["Shipment 2/3"]);
    assert.deepEqual(one(email({ shipment: null })).facts, []);
  });

  test("the carrier and the number show on their own when only one is known", () => {
    assert.deepEqual(one(email({ carrier: "dpd", carrier_name: "DPD" })).facts, ["DPD"]);
    assert.deepEqual(one(email({ tracking_number: "09981234567890" })).facts, ["No. …67890"]);
    assert.deepEqual(one(email({ tracking_number: "ABC_1" })).facts, ["No. ABC_1"]);
  });

  test("the header names the source", () => {
    assert.equal(one(email({ label: "shop.example", sender_name: null })).header, "shop.example");
    assert.equal(one(email({ label: "", sender_name: null })).header, "E-mail");
    assert.equal(
      one(makeOrigin({ id: "17t:X1", source: "seventeentrack", label: "17TRACK" })).header,
      "17TRACK",
    );
    const app = one(makeOrigin({ id: "pa:1", source: "parcelapp", label: "Parcel app", name: "Desk lamp" }));
    assert.equal(app.header, "Parcel app");
    assert.deepEqual(app.facts, ["Name: Desk lamp"]);
    assert.equal(one(makeOrigin({ id: "man:p9", source: "manual", label: "" })).header, "Added by hand");
    assert.equal(
      one(makeOrigin({ id: "man:p1", source: "manual", label: "", edits: true })).header,
      "Changed by hand",
    );
  });

  test("what it said: the kind of e-mail, else the status", () => {
    assert.equal(one(email({ kind: "order", status: "ordered" })).said, "Order confirmation");
    assert.equal(one(email({ kind: "unknown", status: "shipped" })).said, "Shipped");
    assert.equal(one(email({ kind: "not_parcel", status: null })).said, "");
    assert.equal(one(email({ kind: "delayed", status: null })).said, "Delayed");
    assert.equal(one(email({})).said, "");
  });

  test("the status's own time shows when it isn't the e-mail's", () => {
    const later = one(email({ time: T3, status: "delivered", event_time: T2 }));
    assert.equal(later.said, `Delivered · ${formatDayTime(T2, GB)}`);
    const same = one(email({ time: T3, status: "delivered", event_time: "2026-07-15T16:45:30Z" }));
    assert.equal(same.said, "Delivered");
    const undated = one(email({ time: T3, status: "delivered", event_time: T3, undated: true }));
    assert.equal(undated.said, "Delivered · date not known");
    const dayOnly = one(
      makeOrigin({
        id: "pa:2",
        source: "parcelapp",
        label: "Parcel app",
        time: T4,
        status: "delivered",
        event_time: "2026-07-14T23:00:00.000010Z",
        undated: true,
        timeless: true,
      }),
    );
    assert.equal(dayOnly.said, "Delivered · Wed 15 Jul, time not known");
    const window = one(email({ status: "out_for_delivery", window_start: "13:00", window_end: null }));
    assert.equal(window.said, "Out for delivery · from 13:00");
  });

  test("a row without a time has no when", () => {
    assert.equal(one(email({ time: null })).when, "");
  });

  test("what the local AI read in an e-mail joins that e-mail's row", () => {
    const rows = originRows(
      [
        email({
          id: "msg:b#0",
          label: "shop.example",
          time: T1,
          kind: "order",
          status: "ordered",
          event_time: T1,
          order_numbers: ["A-0000001"],
          items: ["Lamp"],
        }),
        email({ id: "msg:c#0", time: T2, status: "shipped" }),
        makeOrigin({
          id: "msg:b#ai",
          source: "ai",
          email: true,
          label: "shop.example",
          time: T1,
          part_of: "msg:b#0",
          status: "in_transit",
          carrier: "ups",
          carrier_name: "UPS",
          tracking_number: "1Z999AA10123456784",
          items: ["Lamp", "Bulb"],
          eta_start: "2026-07-16",
          eta_end: "2026-07-16",
        }),
      ],
      GB,
    );
    assert.deepEqual(
      rows.map((row) => row.ids),
      [["msg:b#0", "msg:b#ai"], ["msg:c#0"]],
    );
    const [order] = rows;
    assert.equal(order!.ai, "part");
    assert.deepEqual(order!.items, ["Lamp", "Bulb"]);
    assert.deepEqual(order!.facts, ["Order …00001", "UPS No. …56784"]);
    assert.equal(order!.said, `Order confirmation · expected ${formatDate("2026-07-16", GB)}`);
  });

  test("what the local AI said counts when the e-mail's own row said nothing", () => {
    const [row] = originRows(
      [
        email({ id: "msg:b#0", time: T1, items: ["Lamp"] }),
        makeOrigin({ id: "msg:b#ai", source: "ai", email: true, time: T1, part_of: "msg:b#0", kind: "delivered", status: "delivered", event_time: T1 }),
      ],
      GB,
    );
    assert.equal(row!.said, "Delivered");
  });

  test("an e-mail read only by the local AI is marked as such", () => {
    assert.equal(one(makeOrigin({ id: "msg:d#0", source: "ai", email: true })).ai, "all");
    const orphan = one(makeOrigin({ id: "msg:e#ai", source: "ai", email: true, part_of: "msg:gone#0" }));
    assert.deepEqual(orphan.ids, ["msg:e#ai"]);
    assert.equal(orphan.ai, "all");
  });

  test("a row says why it can't move to a new parcel", () => {
    assert.equal(one(email({ split_blocked: "shared_number" })).splitBlocked, "shared_number");
    assert.match(splitBlockedReason("shared_number") ?? "", /tracking number or shipment/);
    assert.match(splitBlockedReason("shared_shipment") ?? "", /tracking number or shipment/);
    assert.match(splitBlockedReason("nothing_left") ?? "", /nothing else/i);
    assert.ok(splitBlockedReason("something_new"));
    assert.equal(splitBlockedReason(null), null);
  });

  test("the IDs of the chosen rows include what the local AI read in them", () => {
    const rows = originRows(
      [
        email({ id: "msg:b#0", time: T1 }),
        makeOrigin({ id: "msg:b#ai", source: "ai", email: true, time: T1, part_of: "msg:b#0" }),
        email({ id: "msg:c#0", time: T2 }),
      ],
      GB,
    );
    assert.deepEqual(rowIds(rows, ["msg:b#0"]), ["msg:b#0", "msg:b#ai"]);
    assert.deepEqual(rowIds(rows, ["msg:c#0", "msg:gone#0"]), ["msg:c#0"]);
  });

  test("the title counts the rows, e-mails or not", () => {
    const mails = originRows([email({ id: "msg:b#0" }), email({ id: "msg:c#0" })], GB);
    assert.equal(originsTitle(mails), "E-mails (2)");
    const mixed = originRows(
      [email({ id: "msg:b#0" }), makeOrigin({ id: "17t:X1", source: "seventeentrack", label: "17TRACK" })],
      GB,
    );
    assert.equal(originsTitle(mixed), "E-mails and updates (2)");
  });
});

describe("repeated e-mails from one sender", () => {
  const carrier = {
    label: "express.example",
    sender_name: "Example Express",
    carrier: "dpd",
    carrier_name: "DPD",
    tracking_number: "09981234567890",
  };
  const shopMail = email({ id: "msg:s#0", label: "shop.example", time: T1, kind: "order", items: ["Kettle"] });
  const first = email({ ...carrier, id: "msg:1#0", time: T1, status: "shipped" });
  const second = email({ ...carrier, id: "msg:2#0", time: T2, status: "in_transit" });
  const third = email({ ...carrier, id: "msg:3#0", time: T3, status: "out_for_delivery" });
  const fourth = email({ ...carrier, id: "msg:4#0", time: T4, status: "delivered" });

  function shape(origins: OriginInfo[]): string[] {
    return originEntries(originRows(origins, GB)).map((entry) =>
      entry.type === "row" ? entry.row.lead : `${entry.rows.map((row) => row.lead).join("+")} (${entry.header})`,
    );
  }

  test("fold into one entry when they add nothing new", () => {
    assert.deepEqual(shape([first, shopMail, second, third, fourth]), [
      "msg:1#0",
      "msg:s#0",
      "msg:2#0+msg:3#0+msg:4#0 (Example Express)",
    ]);
    const entries = originEntries(originRows([first, second, third, fourth], GB));
    const fold = entries[1]!;
    assert.equal(fold.type, "repeats");
    assert.equal(fold.type === "repeats" ? fold.latest.lead : "", "msg:4#0");
    assert.equal(fold.type === "repeats" ? fold.key : "", "msg:4#0");
  });

  test("a single repeat shows as it is", () => {
    assert.deepEqual(shape([first, second]), ["msg:1#0", "msg:2#0"]);
  });

  test("an e-mail that adds something stays on show, and later ones are compared with it", () => {
    const withPickup = email({ ...carrier, id: "msg:p#0", time: T2, status: "ready_for_pickup", pickup_point: "Locker 7" });
    const after = email({ ...carrier, id: "msg:5#0", time: T3, status: "ready_for_pickup", pickup_point: "Locker 7" });
    const last = email({ ...carrier, id: "msg:6#0", time: T4, status: "delivered" });
    assert.deepEqual(shape([first, withPickup, after, last]), ["msg:1#0", "msg:p#0", "msg:5#0+msg:6#0 (Example Express)"]);
  });

  test("other sources and the user's edits never fold", () => {
    const edits = makeOrigin({ id: "man:p1", source: "manual", edits: true, time: T2 });
    const edits2 = makeOrigin({ id: "man:p1b", source: "manual", edits: true, time: T3 });
    assert.deepEqual(shape([first, edits, edits2, second]), ["msg:1#0", "man:p1", "man:p1b", "msg:2#0"]);
    const tracked = makeOrigin({ ...carrier, id: "17t:A", source: "seventeentrack", label: "Example Express", sender_name: null, time: T2 });
    assert.deepEqual(shape([first, tracked, second, third]), ["msg:1#0", "17t:A", "msg:2#0+msg:3#0 (Example Express)"]);
  });
});

describe("restoreOutcome", () => {
  test("an e-mail back in the parcel shown says so and stays there", () => {
    assert.deepEqual(restoreOutcome({ review: null, parcels: ["p1"] }, "p1", false), {
      notice: "restored",
      follow: null,
      show: null,
    });
  });

  test("the dialog follows the e-mail when the parcel shown went with it", () => {
    assert.deepEqual(restoreOutcome({ review: null, parcels: ["p9"] }, "p1", true), {
      notice: "restored",
      follow: "p9",
      show: null,
    });
  });

  test("an e-mail read into another parcel offers to show it", () => {
    assert.deepEqual(restoreOutcome({ review: null, parcels: ["p9"] }, "p1", false), {
      notice: "elsewhere",
      follow: null,
      show: "p9",
    });
  });

  test("an e-mail gone from the mailbox waits under Needs review", () => {
    assert.deepEqual(restoreOutcome({ review: "r1", parcels: [] }, "p1", true), {
      notice: "review",
      follow: null,
      show: null,
    });
  });

  test("an e-mail that isn't part of a visible parcel now points to Needs review", () => {
    assert.deepEqual(restoreOutcome({ review: null, parcels: [] }, "p1", true), {
      notice: "noParcel",
      follow: null,
      show: null,
    });
  });
});
