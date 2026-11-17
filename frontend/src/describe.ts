/**
 * Text shown on and announced for a parcel chip: the visible meta line and the
 * full description used as the chip's accessible name and tooltip.
 */
import { formatDate, formatDateRange, formatWindow, type LocaleOptions } from "./format.ts";
import { parcelSubtitle, parcelTitle, statusLabel } from "./labels.ts";
import { etaRange } from "./parcels.ts";
import type { Placement } from "./placement.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { Parcel } from "./types.ts";

export interface ChipContext {
  locale: LocaleOptions;
  /** Where the chip is in the calendar; absent in the list card. */
  placement?: Placement | null;
  continuesBefore?: boolean;
  continuesAfter?: boolean;
}

export interface MetaOptions {
  locale: LocaleOptions;
  placement?: Placement | null;
  /** Start with the status (the list card, which has no dates to show it). */
  showStatus?: boolean;
  /** Add the dates of a span over several days (the stacked layout). */
  showRange?: boolean;
}

/** A delivery window only matters while the parcel is still on its way. */
function windowText(parcel: Parcel, placement: Placement | null, locale: LocaleOptions): string | null {
  if (placement?.kind === "delivered" || placement?.kind === "returned") {
    return null;
  }
  return formatWindow(parcel.window_start, parcel.window_end, locale);
}

/** The second line of a chip, e.g. "DPD · 13:00–14:00". */
export function chipMeta(parcel: Parcel, options: MetaOptions): string {
  const placement = options.placement ?? null;
  const parts: string[] = [];
  if (options.showStatus) {
    const status = statusLabel(parcel.status);
    if (status) {
      parts.push(status);
    }
  }
  const subtitle = parcelSubtitle(parcel);
  if (subtitle) {
    parts.push(subtitle);
  }
  if (options.showRange && placement && placement.from !== placement.to) {
    parts.push(formatDateRange(placement.from, placement.to, options.locale));
  }
  const window = windowText(parcel, placement, options.locale);
  if (window) {
    parts.push(window);
  }
  return parts.join(" · ");
}

/**
 * Everything a chip shows, as one sentence for screen readers and the tooltip,
 * e.g. "Example Shop, DPD, In transit, expected Tue 14 Jul, 13:00–14:00, private".
 */
export function describeParcel(parcel: Parcel, context: ChipContext): string {
  const { locale } = context;
  const placement = context.placement ?? null;
  const parts: string[] = [parcelTitle(parcel)];
  const subtitle = parcelSubtitle(parcel);
  if (subtitle) {
    parts.push(subtitle);
  }
  const status = statusLabel(parcel.status);
  const day = placement ? formatDate(placement.from, locale) : "";
  switch (placement?.kind) {
    case "delivered":
      parts.push(fmt(STRINGS.deliveredOn, { date: day }));
      break;
    case "returned":
      parts.push(fmt(STRINGS.returnedOn, { date: day }));
      break;
    case "pickup":
      parts.push(fmt(STRINGS.readyForPickupSince, { date: day }));
      break;
    case "status":
      parts.push(fmt(STRINGS.statusOn, { status, date: day }));
      break;
    case "eta":
      if (status) {
        parts.push(status);
      }
      parts.push(
        fmt(STRINGS.expectedOn, { date: formatDateRange(placement.from, placement.to, locale) }),
      );
      break;
    default:
      if (status) {
        parts.push(status);
      }
      break;
  }
  const window = windowText(parcel, placement, locale);
  if (window) {
    parts.push(window);
  }
  if (!parcel.restricted) {
    if (parcel.ai) {
      parts.push(STRINGS.aiBadgeLabel);
    }
    if (parcel.auto_merged) {
      parts.push(STRINGS.autoMergedLabel);
    }
  }
  if (parcel.private || parcel.restricted) {
    parts.push(STRINGS.privateLabel);
  }
  if (context.continuesBefore) {
    parts.push(STRINGS.continuesBefore);
  }
  if (context.continuesAfter) {
    parts.push(STRINGS.continuesAfter);
  }
  return parts.join(", ");
}

/** One option in the "Merge with…" picker, e.g. "Example Shop · DPD · 05123456789 · Tue 14 Jul". */
export function candidateLabel(parcel: Parcel, locale: LocaleOptions): string {
  const parts: string[] = [parcelTitle(parcel)];
  const subtitle = parcelSubtitle(parcel);
  if (subtitle) {
    parts.push(subtitle);
  }
  const number = parcel.tracking_number?.trim();
  if (number && number !== parts[0]) {
    parts.push(number);
  }
  const eta = etaRange(parcel);
  parts.push(eta ? formatDateRange(eta.start, eta.end, locale) : statusLabel(parcel.status));
  return parts.filter(Boolean).join(" · ");
}
