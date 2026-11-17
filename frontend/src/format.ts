/**
 * Locale-aware formatting with Intl, following the user's Home Assistant
 * language, time format and time zone settings.
 */
import { parseInstant, parseYmd } from "./dates.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { HassLocale } from "./types.ts";

export interface LocaleOptions {
  language: string;
  /** undefined lets the language decide. */
  hour12: boolean | undefined;
  /** IANA zone for date-times; undefined is the browser's zone. */
  timeZone: string | undefined;
}

interface LocaleSource {
  language?: string;
  locale?: HassLocale;
  config?: { time_zone?: string };
}

function validLanguage(language: string): string {
  try {
    Intl.DateTimeFormat.supportedLocalesOf([language]);
    return language;
  } catch {
    return "en";
  }
}

function systemUsesAmPm(): boolean {
  const cycle = new Intl.DateTimeFormat(undefined, { hour: "numeric" }).resolvedOptions().hourCycle;
  return cycle === "h11" || cycle === "h12";
}

/**
 * Like Home Assistant's own formatting: the profile's language and time format;
 * date-times in the browser's zone when the profile says "local", else in the
 * server's zone.
 */
export function localeOptions(hass: LocaleSource | undefined, serverTimeZone?: string): LocaleOptions {
  const language = validLanguage(hass?.locale?.language || hass?.language || "en");
  const timeFormat = hass?.locale?.time_format;
  let hour12: boolean | undefined;
  if (timeFormat === "12") {
    hour12 = true;
  } else if (timeFormat === "24") {
    hour12 = false;
  } else if (timeFormat === "system") {
    hour12 = systemUsesAmPm();
  }
  const timeZone =
    hass?.locale?.time_zone === "local"
      ? undefined
      : serverTimeZone || hass?.config?.time_zone || undefined;
  return { language, hour12, timeZone };
}

const formatters = new Map<string, Intl.DateTimeFormat>();

function formatter(
  locale: LocaleOptions,
  options: Intl.DateTimeFormatOptions,
  calendarDate: boolean,
): Intl.DateTimeFormat {
  const hasTime = options.hour !== undefined || options.timeStyle !== undefined;
  const full: Intl.DateTimeFormatOptions = {
    ...options,
    timeZone: calendarDate ? "UTC" : locale.timeZone,
  };
  if (hasTime && locale.hour12 !== undefined) {
    full.hour12 = locale.hour12;
  }
  const key = JSON.stringify([locale.language, full]);
  let result = formatters.get(key);
  if (!result) {
    try {
      result = new Intl.DateTimeFormat(locale.language, full);
    } catch {
      // An unknown time zone: fall back to the browser's.
      result = new Intl.DateTimeFormat(locale.language, { ...full, timeZone: undefined });
    }
    formatters.set(key, result);
  }
  return result;
}

function calendarDate(value: string): Date | null {
  const ymd = parseYmd(value);
  return ymd ? new Date(Date.UTC(ymd.year, ymd.month - 1, ymd.day)) : null;
}

export const DAY_FORMAT: Intl.DateTimeFormatOptions = {
  weekday: "short",
  day: "numeric",
  month: "short",
};

export const RANGE_FORMAT: Intl.DateTimeFormatOptions = {
  day: "numeric",
  month: "short",
  year: "numeric",
};

/** Formats a "YYYY-MM-DD" calendar date (never shifted by a time zone). */
export function formatDate(
  value: string,
  locale: LocaleOptions,
  options: Intl.DateTimeFormatOptions = DAY_FORMAT,
): string {
  const date = calendarDate(value);
  return date ? formatter(locale, options, true).format(date) : value;
}

/** Formats an inclusive range of calendar dates, e.g. "14 – 16 Jul". */
export function formatDateRange(
  from: string,
  to: string,
  locale: LocaleOptions,
  options: Intl.DateTimeFormatOptions = DAY_FORMAT,
): string {
  const start = calendarDate(from);
  const end = calendarDate(to);
  if (!start || !end) {
    return [from, to].filter(Boolean).join(" – ");
  }
  if (from === to) {
    return formatter(locale, options, true).format(start);
  }
  return formatter(locale, options, true).formatRange(start, end);
}

/** Formats a "HH:MM" wall-clock time. */
export function formatClock(value: string, locale: LocaleOptions): string {
  const match = /^(\d{1,2}):(\d{2})/.exec(value);
  if (!match) {
    return value;
  }
  const date = new Date(Date.UTC(1970, 0, 1, Number(match[1]), Number(match[2])));
  return formatter(locale, { hour: "numeric", minute: "2-digit" }, true).format(date);
}

/** "13:00–14:00", "from 13:00", "until 14:00", or null without a window. */
export function formatWindow(
  start: string | null,
  end: string | null,
  locale: LocaleOptions,
): string | null {
  if (start && end) {
    return `${formatClock(start, locale)}–${formatClock(end, locale)}`;
  }
  if (start) {
    return fmt(STRINGS.windowFrom, { time: formatClock(start, locale) });
  }
  if (end) {
    return fmt(STRINGS.windowUntil, { time: formatClock(end, locale) });
  }
  return null;
}

/** Formats an ISO date-time in the user's zone; invalid input is returned as is. */
export function formatDateTime(value: string | null, locale: LocaleOptions): string {
  if (!value) {
    return "";
  }
  const ms = parseInstant(value);
  if (ms === null) {
    return value;
  }
  return formatter(locale, { dateStyle: "medium", timeStyle: "short" }, false).format(ms);
}
