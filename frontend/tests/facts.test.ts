import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { collectByFact, deliveredFact, EXPECTED_FORMAT, nextAttemptFact, statusFact } from "../src/facts.ts";
import { formatDate, formatDateTime, type LocaleOptions } from "../src/format.ts";
import { makeParcel } from "./helpers.ts";

const GB: LocaleOptions = { language: "en-GB", hour12: false, timeZone: "Europe/Lisbon" };
const TODAY = "2026-07-14";

describe("facts of the details dialog", () => {
  test("a missed attempt whose e-mail didn't say when it happened says when it was reported", () => {
    const missed = makeParcel({ status: "attempted", status_time: "2026-07-14T08:15:00Z" });
    const at = formatDateTime("2026-07-14T08:15:00Z", GB);
    assert.equal(at, "14 Jul 2026, 09:15");
    assert.equal(statusFact(missed, GB), `Delivery attempted · since ${at}`);
    assert.equal(statusFact({ ...missed, status_reported: true }, GB), `Delivery attempted · reported ${at}`);
    assert.equal(
      statusFact({ ...missed, status: "out_for_delivery", status_reported: true }, GB),
      `Out for delivery · since ${at}`,
    );
    assert.equal(
      statusFact({ ...missed, status_undated: true, status_timeless: true }, GB),
      "Delivery attempted · since 14 Jul 2026, time not known",
    );
    assert.equal(statusFact({ ...missed, status_undated: true }, GB), "Delivery attempted · date not known");
    assert.equal(statusFact({ ...missed, status_time: null }, GB), "Delivery attempted");
  });

  test("a delivery says where it was left when that's known", () => {
    const delivered = makeParcel({ status: "delivered", delivered_at: "2026-07-14T12:20:00Z" });
    const at = formatDateTime("2026-07-14T12:20:00Z", GB);
    assert.equal(deliveredFact(delivered, GB), at);
    assert.equal(deliveredFact({ ...delivered, left_at: "neighbour" }, GB), `${at} · with a neighbour`);
    assert.equal(deliveredFact({ ...delivered, left_at: "reception" }, GB), `${at} · at reception`);
    assert.equal(
      deliveredFact({ ...delivered, left_at: "mailbox", delivered_undated: true, delivered_timeless: true }, GB),
      "14 Jul 2026, time not known · in the mailbox",
    );
    assert.equal(
      deliveredFact({ ...delivered, left_at: "door", delivered_undated: true }, GB),
      "Date not known · at the door",
    );
    assert.equal(deliveredFact(makeParcel({ status: "in_transit", left_at: "garage" }), GB), null);
  });

  test("the next attempt shows until its day has passed", () => {
    const missed = makeParcel({ status: "attempted", next_attempt: "2026-07-15" });
    const day = formatDate("2026-07-15", GB, EXPECTED_FORMAT);
    assert.match(day, /^Wed,? 15 Jul 2026$/u);
    assert.equal(nextAttemptFact(missed, TODAY, GB), day);
    assert.equal(nextAttemptFact(missed, "2026-07-15", GB), day);
    assert.equal(nextAttemptFact(missed, "2026-07-16", GB), null);
    assert.equal(nextAttemptFact({ ...missed, next_attempt: null }, TODAY, GB), null);
  });

  test("a parcel waiting at a pickup point says until when it can be collected", () => {
    const waiting = makeParcel({
      status: "ready_for_pickup",
      pickup_point: "Example Locker 12",
      collect_by: "2026-07-21",
    });
    assert.equal(collectByFact(waiting, GB), formatDate("2026-07-21", GB, EXPECTED_FORMAT));
    assert.equal(collectByFact({ ...waiting, collect_by: null }, GB), null);
  });
});
