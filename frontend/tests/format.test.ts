import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  formatClock,
  formatDate,
  formatDateRange,
  formatDateTime,
  formatWindow,
  localeOptions,
} from "../src/format.ts";
import type { LocaleOptions } from "../src/format.ts";

const GB: LocaleOptions = { language: "en-GB", hour12: false, timeZone: "Europe/Lisbon" };
const US: LocaleOptions = { language: "en-US", hour12: true, timeZone: "America/New_York" };

describe("localeOptions", () => {
  test("follow the user's profile", () => {
    assert.deepEqual(
      localeOptions(
        { language: "fr", locale: { language: "pt-PT", time_format: "24", time_zone: "server" } },
        "Europe/Lisbon",
      ),
      { language: "pt-PT", hour12: false, timeZone: "Europe/Lisbon" },
    );
    assert.deepEqual(localeOptions({ language: "de", locale: { language: "", time_format: "12" } }), {
      language: "de",
      hour12: true,
      timeZone: undefined,
    });
  });

  test("use the browser's zone when the profile asks for it", () => {
    const options = localeOptions(
      { locale: { language: "en", time_format: "language", time_zone: "local" }, config: { time_zone: "Asia/Tokyo" } },
      "Europe/Lisbon",
    );
    assert.equal(options.timeZone, undefined);
    assert.equal(options.hour12, undefined);
  });

  test("fall back to the configured zone and English", () => {
    assert.deepEqual(localeOptions({ locale: { language: "not a language!" }, config: { time_zone: "Asia/Tokyo" } }), {
      language: "en",
      hour12: undefined,
      timeZone: "Asia/Tokyo",
    });
    assert.deepEqual(localeOptions(undefined), { language: "en", hour12: undefined, timeZone: undefined });
  });

  test("system time format is a boolean", () => {
    assert.equal(typeof localeOptions({ locale: { language: "en", time_format: "system" } }).hour12, "boolean");
  });
});

describe("calendar dates", () => {
  test("are formatted in the user's language", () => {
    const text = formatDate("2026-07-14", GB);
    assert.match(text, /Tue/);
    assert.match(text, /14/);
    assert.match(text, /Jul/);
    const portuguese = formatDate("2026-07-14", { ...GB, language: "pt-PT" });
    assert.match(portuguese, /14/);
    assert.notEqual(portuguese, text);
  });

  test("are never shifted by a time zone", () => {
    for (const timeZone of ["Pacific/Pago_Pago", "Pacific/Kiritimati", undefined]) {
      assert.match(formatDate("2026-07-14", { ...GB, timeZone }), /14/);
    }
  });

  test("ranges show both ends", () => {
    const text = formatDateRange("2026-07-13", "2026-07-19", GB);
    assert.match(text, /13/);
    assert.match(text, /19/);
    assert.equal(formatDateRange("2026-07-14", "2026-07-14", GB), formatDate("2026-07-14", GB));
    assert.match(formatDateRange("2026-12-28", "2027-01-03", GB, { day: "numeric", month: "short", year: "numeric" }), /2026.*2027/);
  });

  test("invalid dates are shown as sent", () => {
    assert.equal(formatDate("soon", GB), "soon");
    assert.equal(formatDateRange("soon", "", GB), "soon");
  });
});

describe("times", () => {
  test("follow the 12 or 24 hour setting", () => {
    assert.equal(formatClock("13:05", GB), "13:05");
    assert.match(formatClock("13:05", US), /^1:05\sPM$/u);
    assert.equal(formatClock("later", GB), "later");
  });

  test("windows can be open on either side", () => {
    assert.equal(formatWindow("13:00", "15:00", GB), "13:00–15:00");
    assert.equal(formatWindow("13:00", null, GB), "from 13:00");
    assert.equal(formatWindow(null, "15:00", GB), "until 15:00");
    assert.equal(formatWindow(null, null, GB), null);
  });

  test("date-times use the given zone", () => {
    const text = formatDateTime("2026-07-14T23:30:00Z", GB);
    assert.match(text, /15 Jul 2026/);
    assert.match(text, /00:30/);
    assert.match(formatDateTime("2026-07-14T23:30:00Z", US), /Jul 14, 2026/);
  });

  test("bad date-times don't throw", () => {
    assert.equal(formatDateTime(null, GB), "");
    assert.equal(formatDateTime("whenever", GB), "whenever");
    assert.ok(formatDateTime("2026-07-14T23:30:00Z", { ...GB, timeZone: "Not/A_Zone" }).length > 0);
  });
});
