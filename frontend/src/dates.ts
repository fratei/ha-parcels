/**
 * Calendar arithmetic on "YYYY-MM-DD" strings. Everything is integer maths on
 * year, month and day values, so the browser's time zone and DST never matter.
 */

const YMD_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const INSTANT_RE =
  /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:[.,](\d+))?(Z|[+-]\d{2}(?::?\d{2})?)?$/i;
const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

export interface Ymd {
  year: number;
  month: number;
  day: number;
}

export function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

export function daysInMonth(year: number, month: number): number {
  return month === 2 && isLeapYear(year) ? 29 : (DAYS_IN_MONTH[month - 1] ?? 0);
}

/** Parses a "YYYY-MM-DD" calendar date; anything else (or an impossible date) gives null. */
export function parseYmd(value: unknown): Ymd | null {
  if (typeof value !== "string") {
    return null;
  }
  const match = YMD_RE.exec(value);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)) {
    return null;
  }
  return { year, month, day };
}

export function isYmd(value: unknown): value is string {
  return parseYmd(value) !== null;
}

function requireYmd(value: string): Ymd {
  const ymd = parseYmd(value);
  if (!ymd) {
    throw new RangeError(`Not a YYYY-MM-DD date: ${value}`);
  }
  return ymd;
}

/** Days since 1970-01-01 in the proleptic Gregorian calendar (H. Hinnant's days_from_civil). */
export function toDayNumber({ year, month, day }: Ymd): number {
  const y = month <= 2 ? year - 1 : year;
  const era = Math.floor(y / 400);
  const yearOfEra = y - era * 400;
  const shiftedMonth = (month + 9) % 12;
  const dayOfYear = Math.floor((153 * shiftedMonth + 2) / 5) + day - 1;
  const dayOfEra =
    yearOfEra * 365 + Math.floor(yearOfEra / 4) - Math.floor(yearOfEra / 100) + dayOfYear;
  return era * 146097 + dayOfEra - 719468;
}

/** Inverse of `toDayNumber` (H. Hinnant's civil_from_days). */
export function fromDayNumber(days: number): Ymd {
  const z = days + 719468;
  const era = Math.floor(z / 146097);
  const dayOfEra = z - era * 146097;
  const yearOfEra = Math.floor(
    (dayOfEra -
      Math.floor(dayOfEra / 1460) +
      Math.floor(dayOfEra / 36524) -
      Math.floor(dayOfEra / 146096)) /
      365,
  );
  const dayOfYear =
    dayOfEra - (365 * yearOfEra + Math.floor(yearOfEra / 4) - Math.floor(yearOfEra / 100));
  const shiftedMonth = Math.floor((5 * dayOfYear + 2) / 153);
  const day = dayOfYear - Math.floor((153 * shiftedMonth + 2) / 5) + 1;
  const month = shiftedMonth < 10 ? shiftedMonth + 3 : shiftedMonth - 9;
  return { year: yearOfEra + era * 400 + (month <= 2 ? 1 : 0), month, day };
}

export function formatYmd({ year, month, day }: Ymd): string {
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function addDays(date: string, days: number): string {
  return formatYmd(fromDayNumber(toDayNumber(requireYmd(date)) + days));
}

/** Number of days from `from` to `to` (negative when `to` is earlier). */
export function diffDays(from: string, to: string): number {
  return toDayNumber(requireYmd(to)) - toDayNumber(requireYmd(from));
}

/** Day of the week, 0 = Monday … 6 = Sunday. */
export function weekday(date: string): number {
  // 1970-01-01 was a Thursday (3).
  return (((toDayNumber(requireYmd(date)) + 3) % 7) + 7) % 7;
}

/** The Monday of the week that contains `date`. */
export function startOfWeek(date: string): string {
  return addDays(date, -weekday(date));
}

/** The seven dates, Monday to Sunday, of the week that starts on `monday`. */
export function weekDates(monday: string): string[] {
  return Array.from({ length: 7 }, (_, index) => addDays(monday, index));
}

/** Compares two valid "YYYY-MM-DD" strings (their text order is their date order). */
export function compareYmd(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

export function minYmd(a: string, b: string): string {
  return compareYmd(a, b) <= 0 ? a : b;
}

export function maxYmd(a: string, b: string): string {
  return compareYmd(a, b) >= 0 ? a : b;
}

/**
 * Milliseconds since the epoch for an ISO 8601 date-time such as the ones
 * Python's `datetime.isoformat()` produces. A missing offset means UTC, so the
 * result never depends on the browser's zone. Invalid input gives null.
 */
export function parseInstant(value: unknown): number | null {
  if (typeof value !== "string") {
    return null;
  }
  const match = INSTANT_RE.exec(value.trim());
  if (!match) {
    return null;
  }
  const [, date, time, fraction, zone] = match;
  if (!date || !time || !isYmd(date)) {
    return null;
  }
  const millis = fraction ? `.${fraction.slice(0, 3).padEnd(3, "0")}` : "";
  let offset = "Z";
  if (zone && zone.toUpperCase() !== "Z") {
    const digits = zone.slice(1).replace(":", "").padEnd(4, "0");
    offset = `${zone[0]}${digits.slice(0, 2)}:${digits.slice(2, 4)}`;
  }
  const ms = Date.parse(`${date}T${time}${millis}${offset}`);
  return Number.isNaN(ms) ? null : ms;
}

const dateFormatters = new Map<string, Intl.DateTimeFormat>();

function dateFormatter(timeZone: string): Intl.DateTimeFormat {
  let formatter = dateFormatters.get(timeZone);
  if (!formatter) {
    const options: Intl.DateTimeFormatOptions = {
      calendar: "gregory",
      numberingSystem: "latn",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    };
    try {
      formatter = new Intl.DateTimeFormat("en-US", { ...options, timeZone });
    } catch {
      formatter = new Intl.DateTimeFormat("en-US", { ...options, timeZone: "UTC" });
    }
    dateFormatters.set(timeZone, formatter);
  }
  return formatter;
}

/**
 * The calendar date of an ISO date-time in an IANA time zone, e.g. 23:30Z on a
 * summer day is the next day in Europe/Lisbon. A plain "YYYY-MM-DD" is returned
 * as is. An unknown zone falls back to UTC; invalid input gives null.
 */
export function localDateOf(value: unknown, timeZone: string): string | null {
  if (isYmd(value)) {
    return value;
  }
  const ms = parseInstant(value);
  if (ms === null) {
    return null;
  }
  let year = "";
  let month = "";
  let day = "";
  for (const part of dateFormatter(timeZone).formatToParts(ms)) {
    if (part.type === "year") {
      year = part.value;
    } else if (part.type === "month") {
      month = part.value;
    } else if (part.type === "day") {
      day = part.value;
    }
  }
  const result = `${year.padStart(4, "0")}-${month}-${day}`;
  return isYmd(result) ? result : null;
}
