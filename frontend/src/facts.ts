/**
 * The rows of the details dialog that join several fields, as text, so that
 * they can be tested without rendering the dialog.
 */
import {
  formatDate,
  formatDateTime,
  formatDayWithoutTime,
  MEDIUM_DATE,
  type LocaleOptions,
} from "./format.ts";
import { leftAtLabel, statusLabel } from "./labels.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { Parcel } from "./types.ts";

/** A day the dialog names in full, e.g. "Wed 15 Jul 2026". */
export const EXPECTED_FORMAT: Intl.DateTimeFormatOptions = {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
};

/**
 * The status and since when. A missed attempt whose e-mail didn't say when it
 * happened says when the e-mail reported it instead, so that the e-mail's time
 * isn't taken for the attempt's.
 */
export function statusFact(parcel: Parcel, locale: LocaleOptions): string {
  const label = statusLabel(parcel.status);
  const template =
    parcel.status === "attempted" && parcel.status_reported ? STRINGS.reportedDate : STRINGS.sinceDate;
  if (parcel.status_undated) {
    const day = parcel.status_timeless ? formatDayWithoutTime(parcel.status_time, locale, MEDIUM_DATE) : "";
    return `${label} · ${day ? fmt(template, { date: day }) : STRINGS.dateNotKnownInline}`;
  }
  if (parcel.status_time) {
    return `${label} · ${fmt(template, { date: formatDateTime(parcel.status_time, locale) })}`;
  }
  return label;
}

/** When it was delivered, then where it was left when known; null before its delivery. */
export function deliveredFact(parcel: Parcel, locale: LocaleOptions): string | null {
  let when: string;
  if (parcel.delivered_undated) {
    when =
      (parcel.delivered_timeless && formatDayWithoutTime(parcel.delivered_at, locale, MEDIUM_DATE)) ||
      STRINGS.dateNotKnown;
  } else if (parcel.delivered_at) {
    when = formatDateTime(parcel.delivered_at, locale);
  } else {
    return null;
  }
  const where = leftAtLabel(parcel.left_at);
  return where ? `${when} · ${where}` : when;
}

/** The day of the next attempt after a missed one, until that day has passed; else null. */
export function nextAttemptFact(parcel: Parcel, today: string, locale: LocaleOptions): string | null {
  const day = parcel.next_attempt;
  return day && day >= today ? formatDate(day, locale, EXPECTED_FORMAT) : null;
}

/** The last day to collect it from its pickup point; null when not known. */
export function collectByFact(parcel: Parcel, locale: LocaleOptions): string | null {
  return parcel.collect_by ? formatDate(parcel.collect_by, locale, EXPECTED_FORMAT) : null;
}
