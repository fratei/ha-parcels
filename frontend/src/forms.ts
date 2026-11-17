import { compareYmd } from "./dates.ts";
import { STRINGS } from "./strings.ts";
import type { Parcel, Suggestion } from "./types.ts";

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

/** Splits "A, B; C" or one value per line into trimmed, non-empty, unique values. */
export function splitList(value: string): string[] {
  return unique(
    value
      .split(/[\n,;]+/)
      .map((part) => part.trim())
      .filter(Boolean),
  );
}

/** Splits text into trimmed, non-empty lines (for items, which may contain commas). */
export function splitLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

/** "9:05", "09:05" or "09:05:00" → "09:05"; anything else → null. */
export function normalizeClock(value: string | null | undefined): string | null {
  const match = /^(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/.exec((value ?? "").trim());
  if (!match) {
    return null;
  }
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 23 || minutes > 59) {
    return null;
  }
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function textOrNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

/** An error message when the date range is invalid, else null. Empty strings mean "not set". */
export function validateDateRange(start: string, end: string): string | null {
  if (end && !start) {
    return STRINGS.dateEndWithoutStart;
  }
  if (start && end && compareYmd(end, start) < 0) {
    return STRINGS.dateEndBeforeStart;
  }
  return null;
}

/** An error message when the time window is invalid, else null. Either end may be open. */
export function validateWindow(start: string, end: string): string | null {
  const from = normalizeClock(start);
  const until = normalizeClock(end);
  if (from && until && until <= from) {
    return STRINGS.windowEndBeforeStart;
  }
  return null;
}

export interface DateForm {
  eta_start: string;
  eta_end: string;
  window_start: string;
  window_end: string;
}

export function parcelToDateForm(parcel: Parcel): DateForm {
  return {
    eta_start: parcel.eta_start ?? "",
    eta_end: parcel.eta_end ?? "",
    window_start: normalizeClock(parcel.window_start) ?? "",
    window_end: normalizeClock(parcel.window_end) ?? "",
  };
}

/** The date and time-window fields of the date form and of the suggestion form. */
export type DateField = "eta_start" | "eta_end" | "window_start" | "window_end";

export interface FormProblem {
  message: string;
  /** The field to mark invalid and focus. */
  field: DateField;
}

/** The first problem with a form's dates or time window, or null when they're fine. */
export function dateProblem(form: Readonly<Record<DateField, string>>): FormProblem | null {
  const dates = validateDateRange(form.eta_start, form.eta_end);
  if (dates) {
    return {
      message: dates,
      field: dates === STRINGS.dateEndWithoutStart ? "eta_start" : "eta_end",
    };
  }
  const window = validateWindow(form.window_start, form.window_end);
  return window ? { message: window, field: "window_end" } : null;
}

/** Data for the `update` service; empty fields become null, which clears them. */
export function dateFormToUpdate(parcelId: string, form: DateForm): Record<string, unknown> {
  return {
    parcel_id: parcelId,
    eta_start: textOrNull(form.eta_start),
    eta_end: textOrNull(form.eta_end),
    window_start: normalizeClock(form.window_start),
    window_end: normalizeClock(form.window_end),
  };
}

export interface SuggestionForm {
  kind: string;
  merchant: string;
  carrier: string;
  tracking_numbers: string;
  order_numbers: string;
  eta_start: string;
  eta_end: string;
  window_start: string;
  window_end: string;
  pickup_point: string;
  pickup_code: string;
  items: string;
}

export const DEFAULT_KIND = "shipped";

export function suggestionToForm(suggestion: Suggestion | null): SuggestionForm {
  return {
    kind: suggestion?.kind || DEFAULT_KIND,
    merchant: suggestion?.merchant ?? "",
    carrier: suggestion?.carrier ?? "",
    tracking_numbers: (suggestion?.tracking_numbers ?? []).join(", "),
    order_numbers: (suggestion?.order_numbers ?? []).join(", "),
    eta_start: suggestion?.eta_start ?? "",
    eta_end: suggestion?.eta_end ?? "",
    window_start: normalizeClock(suggestion?.window_start) ?? "",
    window_end: normalizeClock(suggestion?.window_end) ?? "",
    pickup_point: suggestion?.pickup_point ?? "",
    pickup_code: suggestion?.pickup_code ?? "",
    items: (suggestion?.items ?? []).join("\n"),
  };
}

/** The `overrides` of `parcels/review/accept`, in the same shape as a suggestion. */
export function formToSuggestion(form: SuggestionForm): Suggestion {
  return {
    kind: form.kind.trim() || DEFAULT_KIND,
    merchant: textOrNull(form.merchant),
    carrier: textOrNull(form.carrier),
    tracking_numbers: splitList(form.tracking_numbers),
    order_numbers: splitList(form.order_numbers),
    eta_start: textOrNull(form.eta_start),
    eta_end: textOrNull(form.eta_end),
    window_start: normalizeClock(form.window_start),
    window_end: normalizeClock(form.window_end),
    pickup_point: textOrNull(form.pickup_point),
    pickup_code: textOrNull(form.pickup_code),
    items: splitLines(form.items),
  };
}

export interface AddForm {
  tracking_number: string;
  carrier: string;
  merchant: string;
  private: boolean;
}

/** Data for the `add` service, or null when the tracking number is missing. */
export function addFormToServiceData(form: AddForm): Record<string, unknown> | null {
  const trackingNumber = form.tracking_number.trim();
  if (!trackingNumber) {
    return null;
  }
  const data: Record<string, unknown> = { tracking_number: trackingNumber };
  const carrier = textOrNull(form.carrier);
  if (carrier) {
    data.carrier = carrier;
  }
  const merchant = textOrNull(form.merchant);
  if (merchant) {
    data.merchant = merchant;
  }
  if (form.private) {
    data.private = true;
  }
  return data;
}

/** Split needs at least one origin moved out and at least one left behind. */
export function isValidSplit(selected: readonly string[], total: number): boolean {
  return selected.length > 0 && selected.length < total;
}
