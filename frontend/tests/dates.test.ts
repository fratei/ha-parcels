import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  addDays,
  compareYmd,
  diffDays,
  formatYmd,
  fromDayNumber,
  isLeapYear,
  isYmd,
  localDateOf,
  parseInstant,
  parseYmd,
  startOfWeek,
  toDayNumber,
  weekDates,
  weekday,
} from "../src/dates.ts";

describe("calendar dates", () => {
  test("parses only real YYYY-MM-DD dates", () => {
    assert.deepEqual(parseYmd("2026-07-14"), { year: 2026, month: 7, day: 14 });
    assert.equal(parseYmd("2026-02-29"), null);
    assert.equal(parseYmd("2026-13-01"), null);
    assert.equal(parseYmd("2026-00-10"), null);
    assert.equal(parseYmd("2026-7-14"), null);
    assert.equal(parseYmd("2026-07-14T10:00:00Z"), null);
    assert.equal(parseYmd(null), null);
    assert.equal(isYmd("2028-02-29"), true);
    assert.equal(isYmd(20260714), false);
  });

  test("knows leap years", () => {
    assert.equal(isLeapYear(2028), true);
    assert.equal(isLeapYear(2100), false);
    assert.equal(isLeapYear(2000), true);
    assert.equal(parseYmd("2100-02-29"), null);
    assert.equal(addDays("2028-02-28", 1), "2028-02-29");
    assert.equal(addDays("2028-02-29", 1), "2028-03-01");
    assert.equal(addDays("2100-02-28", 1), "2100-03-01");
  });

  test("day numbers round-trip and agree with UTC dates", () => {
    assert.equal(toDayNumber({ year: 1970, month: 1, day: 1 }), 0);
    let date = "2023-12-25";
    for (let step = 0; step < 3000; step += 1) {
      const ymd = parseYmd(date);
      assert.ok(ymd);
      const utc = new Date(Date.UTC(ymd.year, ymd.month - 1, ymd.day));
      assert.equal(toDayNumber(ymd), utc.getTime() / 86_400_000);
      assert.equal(formatYmd(fromDayNumber(toDayNumber(ymd))), date);
      assert.equal(weekday(date), (utc.getUTCDay() + 6) % 7);
      date = addDays(date, 1);
    }
  });

  test("adds and subtracts days across months and years", () => {
    assert.equal(addDays("2026-01-31", 1), "2026-02-01");
    assert.equal(addDays("2026-12-31", 1), "2027-01-01");
    assert.equal(addDays("2027-01-01", -1), "2026-12-31");
    assert.equal(addDays("2026-03-01", -1), "2026-02-28");
    assert.equal(diffDays("2026-12-28", "2027-01-03"), 6);
    assert.equal(diffDays("2027-01-03", "2026-12-28"), -6);
    assert.throws(() => addDays("not a date", 1), RangeError);
  });

  test("compares dates", () => {
    assert.equal(compareYmd("2026-07-14", "2026-07-15"), -1);
    assert.equal(compareYmd("2026-07-15", "2026-07-15"), 0);
    assert.equal(compareYmd("2027-01-01", "2026-12-31"), 1);
  });
});

describe("weeks", () => {
  test("start on Monday", () => {
    assert.equal(weekday("2026-07-13"), 0);
    assert.equal(weekday("2026-07-19"), 6);
    assert.equal(startOfWeek("2026-07-13"), "2026-07-13");
    assert.equal(startOfWeek("2026-07-15"), "2026-07-13");
    assert.equal(startOfWeek("2026-07-19"), "2026-07-13");
    assert.equal(startOfWeek("2026-07-20"), "2026-07-20");
  });

  test("cross months", () => {
    assert.equal(startOfWeek("2026-07-01"), "2026-06-29");
    assert.deepEqual(weekDates("2026-06-29"), [
      "2026-06-29",
      "2026-06-30",
      "2026-07-01",
      "2026-07-02",
      "2026-07-03",
      "2026-07-04",
      "2026-07-05",
    ]);
  });

  test("cross years", () => {
    assert.equal(startOfWeek("2026-12-31"), "2026-12-28");
    assert.equal(startOfWeek("2027-01-01"), "2026-12-28");
    assert.equal(startOfWeek("2027-01-03"), "2026-12-28");
    assert.equal(startOfWeek("2027-01-04"), "2027-01-04");
    assert.deepEqual(weekDates("2026-12-28"), [
      "2026-12-28",
      "2026-12-29",
      "2026-12-30",
      "2026-12-31",
      "2027-01-01",
      "2027-01-02",
      "2027-01-03",
    ]);
  });

  test("include leap days", () => {
    assert.equal(startOfWeek("2028-03-01"), "2028-02-28");
    assert.deepEqual(weekDates("2028-02-28").slice(0, 3), ["2028-02-28", "2028-02-29", "2028-03-01"]);
  });

  test("have seven distinct days in DST weeks", () => {
    // Europe switches on 2026-03-29 and 2026-10-25, the US on 2026-03-08 and 2026-11-01.
    const cases: Array<[string, string, string]> = [
      ["2026-03-29", "2026-03-23", "2026-03-29"],
      ["2026-10-25", "2026-10-19", "2026-10-25"],
      ["2026-03-08", "2026-03-02", "2026-03-08"],
      ["2026-11-01", "2026-10-26", "2026-11-01"],
    ];
    for (const [day, monday, sunday] of cases) {
      const week = weekDates(startOfWeek(day));
      assert.equal(week[0], monday);
      assert.equal(week[6], sunday);
      assert.equal(new Set(week).size, 7);
      for (let index = 1; index < 7; index += 1) {
        assert.equal(diffDays(week[index - 1] ?? "", week[index] ?? ""), 1);
      }
    }
  });

  test("don't depend on the process time zone", () => {
    const original = process.env.TZ;
    try {
      for (const zone of ["Europe/Lisbon", "America/Santiago", "Pacific/Chatham", "UTC"]) {
        process.env.TZ = zone;
        assert.equal(startOfWeek("2026-10-25"), "2026-10-19");
        assert.equal(addDays("2026-03-28", 2), "2026-03-30");
        assert.equal(localDateOf("2026-07-14T23:30:00Z", "Europe/Lisbon"), "2026-07-15");
      }
    } finally {
      if (original === undefined) {
        delete process.env.TZ;
      } else {
        process.env.TZ = original;
      }
    }
  });
});

describe("instants", () => {
  test("parse ISO date-times with and without offsets", () => {
    const base = Date.UTC(2026, 6, 14, 23, 30);
    assert.equal(parseInstant("2026-07-14T23:30:00Z"), base);
    assert.equal(parseInstant("2026-07-14T23:30:00+00:00"), base);
    assert.equal(parseInstant("2026-07-15T00:30:00+01:00"), base);
    assert.equal(parseInstant("2026-07-14T19:30:00-0400"), base);
    assert.equal(parseInstant("2026-07-14T23:30"), base);
    assert.equal(parseInstant("2026-07-14 23:30:00"), base);
    assert.equal(parseInstant("2026-07-14T23:30:00.123456+00:00"), base + 123);
  });

  test("reject anything else", () => {
    assert.equal(parseInstant(""), null);
    assert.equal(parseInstant("yesterday"), null);
    assert.equal(parseInstant("2026-02-30T10:00:00Z"), null);
    assert.equal(parseInstant("2026-07-14"), null);
    assert.equal(parseInstant(null), null);
    assert.equal(parseInstant(1_784_072_000_000), null);
  });
});

describe("local date of an instant", () => {
  test("is the next day in Lisbon at 23:30 UTC in summer", () => {
    assert.equal(localDateOf("2026-07-14T23:30:00Z", "Europe/Lisbon"), "2026-07-15");
    assert.equal(localDateOf("2026-07-14T23:30:00+00:00", "UTC"), "2026-07-14");
  });

  test("is the same day in Lisbon at 23:30 UTC in winter", () => {
    assert.equal(localDateOf("2026-01-14T23:30:00Z", "Europe/Lisbon"), "2026-01-14");
  });

  test("follows DST changes and other zones", () => {
    assert.equal(localDateOf("2026-03-29T00:30:00Z", "Europe/Lisbon"), "2026-03-29");
    assert.equal(localDateOf("2026-10-24T23:30:00Z", "Europe/Lisbon"), "2026-10-25");
    assert.equal(localDateOf("2026-10-25T23:30:00Z", "Europe/Lisbon"), "2026-10-25");
    assert.equal(localDateOf("2026-07-15T02:30:00Z", "America/New_York"), "2026-07-14");
    assert.equal(localDateOf("2026-12-31T15:00:00Z", "Asia/Tokyo"), "2027-01-01");
  });

  test("keeps plain dates and falls back to UTC for unknown zones", () => {
    assert.equal(localDateOf("2026-07-14", "Asia/Tokyo"), "2026-07-14");
    assert.equal(localDateOf("2026-07-14T23:30:00Z", "Not/A_Zone"), "2026-07-14");
    assert.equal(localDateOf("2026-07-14T23:30:00Z", ""), "2026-07-14");
  });

  test("is null for invalid input", () => {
    assert.equal(localDateOf(null, "UTC"), null);
    assert.equal(localDateOf("soon", "UTC"), null);
  });
});
