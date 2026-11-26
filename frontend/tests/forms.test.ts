import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  DEFAULT_KIND,
  addFormToServiceData,
  dateFormToUpdate,
  dateProblem,
  formToSuggestion,
  isValidSplit,
  normalizeClock,
  parcelToDateForm,
  splitLines,
  splitList,
  suggestionToForm,
  validateDateRange,
  validateWindow,
} from "../src/forms.ts";
import { STRINGS } from "../src/strings.ts";
import type { Suggestion } from "../src/types.ts";
import { makeParcel } from "./helpers.ts";

describe("parsing form fields", () => {
  test("splits lists on commas, semicolons and new lines", () => {
    assert.deepEqual(splitList(" TEST0001, TEST0002;TEST0003\n\nTEST0001 "), [
      "TEST0001",
      "TEST0002",
      "TEST0003",
    ]);
    assert.deepEqual(splitList("  "), []);
  });

  test("splits items on new lines only", () => {
    assert.deepEqual(splitLines("Blue mug, large\r\n\n  Tea towel  "), ["Blue mug, large", "Tea towel"]);
  });

  test("normalizes wall-clock times", () => {
    assert.equal(normalizeClock("9:05"), "09:05");
    assert.equal(normalizeClock(" 13:30 "), "13:30");
    assert.equal(normalizeClock("13:30:00"), "13:30");
    assert.equal(normalizeClock("00:00"), "00:00");
    for (const value of ["24:00", "12:60", "noon", "1330", "", null, undefined]) {
      assert.equal(normalizeClock(value), null, String(value));
    }
  });
});

describe("validation", () => {
  test("date ranges need a start and must not end before it", () => {
    assert.equal(validateDateRange("", ""), null);
    assert.equal(validateDateRange("2026-07-14", ""), null);
    assert.equal(validateDateRange("2026-07-14", "2026-07-14"), null);
    assert.equal(validateDateRange("", "2026-07-14"), STRINGS.dateEndWithoutStart);
    assert.equal(validateDateRange("2026-07-15", "2026-07-14"), STRINGS.dateEndBeforeStart);
  });

  test("time windows must end after they start", () => {
    assert.equal(validateWindow("9:00", "13:00"), null);
    assert.equal(validateWindow("13:00", ""), null);
    assert.equal(validateWindow("", "13:00"), null);
    assert.equal(validateWindow("13:00", "13:00"), STRINGS.windowEndBeforeStart);
    assert.equal(validateWindow("13:00", "9:30"), STRINGS.windowEndBeforeStart);
  });
});

describe("date form", () => {
  test("round-trips a parcel into update data", () => {
    const parcel = makeParcel({
      id: "p7",
      eta_start: "2026-07-14",
      eta_end: null,
      window_start: "09:00:00",
      window_end: null,
    });
    const form = parcelToDateForm(parcel);
    assert.deepEqual(form, { eta_start: "2026-07-14", eta_end: "", window_start: "09:00", window_end: "" });
    assert.equal(dateProblem(form), null);
    assert.deepEqual(dateFormToUpdate("p7", { ...form, eta_end: "2026-07-15", window_end: "12:00" }), {
      parcel_id: "p7",
      eta_start: "2026-07-14",
      eta_end: "2026-07-15",
      window_start: "09:00",
      window_end: "12:00",
    });
  });

  test("clears empty fields with null", () => {
    assert.deepEqual(
      dateFormToUpdate("p7", { eta_start: " ", eta_end: "", window_start: "", window_end: "" }),
      { parcel_id: "p7", eta_start: null, eta_end: null, window_start: null, window_end: null },
    );
  });

  test("reports the first problem and the field to point at", () => {
    assert.deepEqual(
      dateProblem({ eta_start: "", eta_end: "2026-07-15", window_start: "13:00", window_end: "12:00" }),
      { message: STRINGS.dateEndWithoutStart, field: "eta_start" },
    );
    assert.deepEqual(
      dateProblem({ eta_start: "2026-07-16", eta_end: "2026-07-15", window_start: "", window_end: "" }),
      { message: STRINGS.dateEndBeforeStart, field: "eta_end" },
    );
    assert.deepEqual(
      dateProblem({ eta_start: "", eta_end: "", window_start: "13:00", window_end: "12:00" }),
      { message: STRINGS.windowEndBeforeStart, field: "window_end" },
    );
  });
});

describe("suggestion form", () => {
  const suggestion: Suggestion = {
    kind: "out_for_delivery",
    merchant: "Example Shop",
    carrier: "dhl",
    tracking_numbers: ["TEST0001", "TEST0002"],
    order_numbers: ["ORDER-1"],
    eta_start: "2026-07-14",
    eta_end: null,
    window_start: "13:00",
    window_end: "15:00:00",
    pickup_point: null,
    pickup_code: null,
    items: ["Blue mug, large", "Tea towel"],
    amazon_shipment_id: "TESTSHIPMENT1",
    reference: "Ab3Cd5Ef7",
  };

  test("is prefilled from the suggestion", () => {
    assert.deepEqual(suggestionToForm(suggestion), {
      kind: "out_for_delivery",
      merchant: "Example Shop",
      carrier: "dhl",
      tracking_numbers: "TEST0001, TEST0002",
      order_numbers: "ORDER-1",
      eta_start: "2026-07-14",
      eta_end: "",
      window_start: "13:00",
      window_end: "15:00",
      pickup_point: "",
      pickup_code: "",
      items: "Blue mug, large\nTea towel",
      reference: "Ab3Cd5Ef7",
    });
  });

  test("round-trips into accept overrides", () => {
    const { amazon_shipment_id: _kept, ...edited } = suggestion;
    assert.deepEqual(formToSuggestion(suggestionToForm(suggestion)), { ...edited, window_end: "15:00" });
  });

  test("starts empty without a suggestion", () => {
    const form = suggestionToForm(null);
    assert.equal(form.kind, DEFAULT_KIND);
    assert.equal(form.tracking_numbers, "");
    assert.equal(dateProblem(form), null);
    assert.deepEqual(formToSuggestion({ ...form, kind: " ", merchant: "  Example Shop " }), {
      kind: DEFAULT_KIND,
      merchant: "Example Shop",
      carrier: null,
      tracking_numbers: [],
      order_numbers: [],
      eta_start: null,
      eta_end: null,
      window_start: null,
      window_end: null,
      pickup_point: null,
      pickup_code: null,
      items: [],
      reference: null,
    });
  });

  test("is validated like the date form", () => {
    const form = suggestionToForm(suggestion);
    assert.deepEqual(dateProblem({ ...form, eta_end: "2026-07-01" }), {
      message: STRINGS.dateEndBeforeStart,
      field: "eta_end",
    });
  });
});

describe("add form", () => {
  test("needs a tracking number", () => {
    assert.equal(addFormToServiceData({ tracking_number: " ", carrier: "dhl", merchant: "", private: false }), null);
  });

  test("sends only what was filled in", () => {
    assert.deepEqual(
      addFormToServiceData({ tracking_number: " TEST0001 ", carrier: "", merchant: " ", private: false }),
      { tracking_number: "TEST0001" },
    );
    assert.deepEqual(
      addFormToServiceData({ tracking_number: "TEST0001", carrier: "ups", merchant: "Example Shop", private: true }),
      { tracking_number: "TEST0001", carrier: "ups", merchant: "Example Shop", private: true },
    );
  });
});

describe("split", () => {
  test("moves some but not all origins", () => {
    assert.equal(isValidSplit([], 2), false);
    assert.equal(isValidSplit(["o1"], 2), true);
    assert.equal(isValidSplit(["o1", "o2"], 2), false);
    assert.equal(isValidSplit(["o1"], 1), false);
  });
});
