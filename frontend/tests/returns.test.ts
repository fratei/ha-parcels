import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { matchesReturnFilter } from "../src/filter.ts";
import { formatDate, type LocaleOptions } from "../src/format.ts";
import { normalizeReturn, normalizeSnapshot } from "../src/normalize.ts";
import {
  describeReturn,
  isReturnDone,
  pickupRuleText,
  returnStateLine,
  returnTitle,
  returnsOfParcel,
} from "../src/returns.ts";
import { makeReturn } from "./helpers.ts";

const GB: LocaleOptions = { language: "en-GB", hour12: false, timeZone: "Europe/Lisbon" };
// Wednesday; its week runs from Monday 13 to Sunday 19 July 2026.
const TODAY = "2026-07-15";
const NOW = Date.UTC(2026, 6, 15, 10);

describe("normalizeReturn", () => {
  test("keeps a full return as it is", () => {
    const ret = makeReturn({
      merchant: "Example Shop",
      carrier: "ups",
      carrier_name: "UPS",
      tracking_number: "1Z0000000000000000",
      tracking_url: "https://tracking.example.com/1Z0000000000000000",
      day: "2026-07-16",
      pickup: "2026-07-16",
      pickup_rule: "next_working_day",
      started: "2026-07-15T11:44:00+00:00",
      received: true,
      order_numbers: ["ORDER-1"],
      items: ["Blue mug"],
      parcel_ids: ["p1"],
      emails: [
        { time: "2026-07-15T11:44:00+00:00", label: "example.com", source: "parser" },
        { time: null, label: "", source: "manual" },
      ],
      private: true,
      owners: ["person.one"],
      archived: true,
    });
    assert.deepEqual(normalizeReturn(JSON.parse(JSON.stringify(ret))), ret);
  });

  test("fills in missing fields", () => {
    assert.deepEqual(
      normalizeReturn({ id: "r1", day: "2026-07-15" }),
      makeReturn({ merchant: null, pickup: null, pickup_rule: null, started: null }),
    );
  });

  test("needs an id and a day", () => {
    assert.equal(normalizeReturn({ day: "2026-07-15" }), null);
    assert.equal(normalizeReturn({ id: "", day: "2026-07-15" }), null);
    assert.equal(normalizeReturn({ id: "r1" }), null);
    assert.equal(normalizeReturn({ id: "r1", day: "15/07/2026" }), null);
    assert.equal(normalizeReturn(null), null);
    assert.equal(normalizeReturn([]), null);
  });

  test("never trusts the types it gets", () => {
    const ret = normalizeReturn({
      id: "r1",
      day: "2026-07-15",
      merchant: 3,
      pickup: "tomorrow",
      pickup_rule: "whenever",
      received: "yes",
      items: ["Blue mug", 3, null],
      parcel_ids: "p1",
      emails: [{ time: 5, label: 3, source: "pigeon" }, null, "e-mail"],
      private: "yes",
      archived: 1,
      restricted: "true",
    });
    assert.ok(ret);
    assert.equal(ret.merchant, null);
    assert.equal(ret.pickup, null);
    assert.equal(ret.pickup_rule, null);
    assert.equal(ret.received, false);
    assert.deepEqual(ret.items, ["Blue mug"]);
    assert.deepEqual(ret.parcel_ids, []);
    assert.deepEqual(ret.emails, [{ time: null, label: "", source: "parser" }]);
    assert.equal(ret.private, false);
    assert.equal(ret.archived, false);
    assert.equal(ret.restricted, false);
  });

  test("keeps every pickup rule the integration sends", () => {
    for (const rule of ["email", "next_working_day", "assumed"] as const) {
      assert.equal(normalizeReturn({ id: "r1", day: TODAY, pickup_rule: rule })?.pickup_rule, rule);
    }
  });

  test("comes with the snapshot", () => {
    const snapshot = normalizeSnapshot(
      { returns: [{ id: "r1", day: TODAY }, { id: "r2" }, 3, { id: "r3", day: "2026-07-16" }] },
      NOW,
    );
    assert.deepEqual(
      snapshot.returns.map((ret) => ret.id),
      ["r1", "r3"],
    );
    assert.deepEqual(normalizeSnapshot({ returns: {} }, NOW).returns, []);
  });
});

describe("isReturnDone", () => {
  test("is done once its day is over, or when the shop has it", () => {
    assert.equal(isReturnDone(makeReturn({ day: "2026-07-14" }), TODAY), true);
    assert.equal(isReturnDone(makeReturn({ day: TODAY }), TODAY), false);
    assert.equal(isReturnDone(makeReturn({ day: "2026-07-16" }), TODAY), false);
    assert.equal(isReturnDone(makeReturn({ day: "2026-07-16", received: true }), TODAY), true);
  });
});

describe("matchesReturnFilter", () => {
  const upcoming = makeReturn({ day: "2026-07-16" });
  const today = makeReturn({ day: TODAY });
  const past = makeReturn({ day: "2026-07-14" });
  const received = makeReturn({ day: "2026-07-17", received: true });
  const context = { today: TODAY };

  test("All shows every return", () => {
    for (const ret of [upcoming, today, past, received]) {
      assert.equal(matchesReturnFilter(ret, "all", context), true);
    }
  });

  test("Active shows the ones still to be picked up, Completed the others", () => {
    const active = [upcoming, today, past, received].map((ret) => matchesReturnFilter(ret, "active", context));
    const completed = [upcoming, today, past, received].map((ret) =>
      matchesReturnFilter(ret, "completed", context),
    );
    assert.deepEqual(active, [true, true, false, false]);
    assert.deepEqual(completed, [false, false, true, true]);
  });

  test("Recent shows the returns of this week", () => {
    const days = ["2026-07-12", "2026-07-13", "2026-07-19", "2026-07-20"];
    assert.deepEqual(
      days.map((day) => matchesReturnFilter(makeReturn({ day }), "recent", context)),
      [false, true, true, false],
    );
  });
});

describe("return text", () => {
  const day = formatDate("2026-07-16", GB);
  const upcoming = makeReturn({
    merchant: "Example Shop",
    carrier: "ups",
    carrier_name: "UPS",
    day: "2026-07-16",
    pickup: "2026-07-16",
    items: ["Blue mug", "Lumen desk lamp"],
  });

  test("explains where the pickup day comes from", () => {
    assert.equal(pickupRuleText("email"), "date from the e-mail");
    assert.equal(pickupRuleText("next_working_day"), "the e-mail says the next working day");
    assert.equal(pickupRuleText("assumed"), "usually the working day after the e-mail");
    assert.equal(pickupRuleText(null), null);
  });

  test("names the shop, or hides it when the return is someone else's private one", () => {
    assert.equal(returnTitle(upcoming), "Example Shop");
    assert.equal(returnTitle(makeReturn({ merchant: "  " })), "Unknown seller");
    assert.equal(returnTitle(makeReturn({ restricted: true, merchant: null })), "Private return");
  });

  test("says how far the return is on the chip", () => {
    assert.equal(returnStateLine(upcoming, TODAY), "Return pickup · UPS");
    assert.equal(returnStateLine({ ...upcoming, day: "2026-07-14" }, TODAY), "Return picked up · UPS");
    assert.equal(returnStateLine({ ...upcoming, received: true }, TODAY), "Received by the shop · UPS");
    assert.equal(
      returnStateLine({ ...upcoming, pickup: null, pickup_rule: null, carrier: null, carrier_name: null }, TODAY),
      "Return started",
    );
    assert.equal(returnStateLine({ ...upcoming, restricted: true }, TODAY), "Return pickup");
  });

  test("describes a pickup to come, with where its day comes from", () => {
    assert.equal(
      describeReturn(upcoming, GB, TODAY),
      `Return to Example Shop, pickup ${day}, usually the working day after the e-mail, carrier UPS, 2 items · Blue mug, Lumen desk lamp`,
    );
    assert.equal(
      describeReturn({ ...upcoming, pickup_rule: "email", items: [], private: true }, GB, TODAY),
      `Return to Example Shop, pickup ${day}, date from the e-mail, carrier UPS, private`,
    );
  });

  test("describes a return that was picked up or that the shop has", () => {
    const past = { ...upcoming, carrier: null, carrier_name: null, items: [] };
    assert.equal(describeReturn(past, GB, "2026-07-17"), `Return to Example Shop, picked up ${day}`);
    assert.equal(
      describeReturn({ ...past, received: true }, GB, "2026-07-17"),
      `Return to Example Shop, picked up ${day}, received by the shop`,
    );
    // The shop has it before the day the pickup was expected: that day was wrong.
    assert.equal(
      describeReturn({ ...past, received: true }, GB, TODAY),
      "Return to Example Shop, received by the shop",
    );
  });

  test("describes a return without a pickup day by the day it started", () => {
    const started = makeReturn({ merchant: null, day: "2026-07-16", pickup: null, pickup_rule: null });
    assert.equal(describeReturn(started, GB, TODAY), `Return, started ${day}`);
  });

  test("tells nothing but the day about someone else's private return", () => {
    const secret = makeReturn({ restricted: true, merchant: null, day: "2026-07-16", pickup: "2026-07-16" });
    assert.equal(
      describeReturn(secret, GB, TODAY),
      `Private return, pickup ${day}, usually the working day after the e-mail, private`,
    );
  });

  test("finds the returns of a parcel", () => {
    const returns = [
      makeReturn({ id: "r1", parcel_ids: ["p1", "p2"] }),
      makeReturn({ id: "r2", parcel_ids: ["p3"] }),
      makeReturn({ id: "r3", parcel_ids: ["p2"] }),
    ];
    assert.deepEqual(
      returnsOfParcel(returns, "p2").map((ret) => ret.id),
      ["r1", "r3"],
    );
    assert.deepEqual(returnsOfParcel(returns, "p9"), []);
  });
});
