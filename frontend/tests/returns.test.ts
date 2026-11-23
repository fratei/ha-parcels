import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { matchesReturnFilter } from "../src/filter.ts";
import { formatDate, type LocaleOptions } from "../src/format.ts";
import { normalizeReturn, normalizeSnapshot } from "../src/normalize.ts";
import {
  canMarkPickedUp,
  canUndoPickedUp,
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
// Marked picked up on the morning of TODAY, 10:12 in Lisbon.
const MARKED = "2026-07-15T09:12:00+00:00";

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
      picked_up: "2026-07-16T09:12:00+00:00",
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
      picked_up: 5,
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
    assert.equal(ret.picked_up, null);
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

  test("is done once someone marks it picked up, even before its day", () => {
    assert.equal(isReturnDone(makeReturn({ day: TODAY, picked_up: MARKED }), TODAY), true);
    assert.equal(isReturnDone(makeReturn({ day: "2026-07-16", picked_up: MARKED }), TODAY), true);
  });
});

describe("marking a return picked up", () => {
  const upcoming = makeReturn({ day: "2026-07-16", pickup: "2026-07-16" });
  const today = makeReturn({ day: TODAY, pickup: TODAY });
  const marked = { ...today, picked_up: MARKED };

  test("is offered until the return is done, when it has a pickup day", () => {
    assert.equal(canMarkPickedUp(today, TODAY), true);
    // The carrier may come early.
    assert.equal(canMarkPickedUp(upcoming, TODAY), true);
    assert.equal(canMarkPickedUp(makeReturn({ day: "2026-07-14", pickup: "2026-07-14" }), TODAY), false);
    assert.equal(canMarkPickedUp(marked, TODAY), false);
    assert.equal(canMarkPickedUp({ ...today, received: true }, TODAY), false);
    // Without a pickup day nobody comes for it.
    assert.equal(canMarkPickedUp({ ...today, pickup: null, pickup_rule: null }, TODAY), false);
  });

  test("can be undone until the pickup day is over", () => {
    assert.equal(canUndoPickedUp(marked, TODAY), true);
    assert.equal(canUndoPickedUp({ ...upcoming, picked_up: MARKED }, TODAY), true);
    // Done anyway once its day is over: undoing would change nothing.
    assert.equal(canUndoPickedUp(marked, "2026-07-16"), false);
    assert.equal(canUndoPickedUp(today, TODAY), false);
    assert.equal(canUndoPickedUp({ ...marked, received: true }, TODAY), false);
  });

  test("is only for someone who may see the return", () => {
    assert.equal(canMarkPickedUp({ ...today, restricted: true }, TODAY), false);
    assert.equal(canUndoPickedUp({ ...marked, restricted: true }, TODAY), false);
  });
});

describe("matchesReturnFilter", () => {
  const upcoming = makeReturn({ day: "2026-07-16" });
  const today = makeReturn({ day: TODAY });
  const past = makeReturn({ day: "2026-07-14" });
  const received = makeReturn({ day: "2026-07-17", received: true });
  const marked = makeReturn({ day: TODAY, picked_up: MARKED });
  const context = { today: TODAY };

  test("All shows every return", () => {
    for (const ret of [upcoming, today, past, received, marked]) {
      assert.equal(matchesReturnFilter(ret, "all", context), true);
    }
  });

  test("Active shows the ones still to be picked up, Completed the others", () => {
    const returns = [upcoming, today, past, received, marked];
    const active = returns.map((ret) => matchesReturnFilter(ret, "active", context));
    const completed = returns.map((ret) => matchesReturnFilter(ret, "completed", context));
    assert.deepEqual(active, [true, true, false, false, false]);
    assert.deepEqual(completed, [false, false, true, true, true]);
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

  test("says a return was picked up as soon as someone marks it", () => {
    assert.equal(returnStateLine({ ...upcoming, picked_up: MARKED }, TODAY), "Return picked up · UPS");
    // Marked although no pickup day was known.
    assert.equal(
      returnStateLine({ ...upcoming, pickup: null, pickup_rule: null, picked_up: MARKED }, TODAY),
      "Return picked up · UPS",
    );
    assert.equal(
      returnStateLine({ ...upcoming, received: true, picked_up: MARKED }, TODAY),
      "Received by the shop · UPS",
    );
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

  test("describes when someone marked a return picked up", () => {
    const early = { ...upcoming, carrier: null, carrier_name: null, items: [], picked_up: MARKED };
    assert.equal(describeReturn(early, GB, TODAY), "Return to Example Shop, picked up Wed 15 Jul at 10:12");
    assert.equal(
      describeReturn(early, GB, "2026-07-17"),
      "Return to Example Shop, picked up Wed 15 Jul at 10:12",
    );
    assert.equal(
      describeReturn({ ...early, received: true }, GB, "2026-07-17"),
      "Return to Example Shop, picked up Wed 15 Jul at 10:12, received by the shop",
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
