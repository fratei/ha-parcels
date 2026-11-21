import { CARRIER_NAMES, carrierName } from "./carriers.ts";
import {
  KIND_LABELS,
  MERGE_REASON_LABELS,
  NOTE_MEANINGS,
  REASON_LABELS,
  SOURCE_LABELS,
  STATUS_LABELS,
  STRINGS,
} from "./strings.ts";
import type { Parcel } from "./types.ts";

function clean(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

/** "unknown_sender" → "Unknown sender"; other text is returned unchanged. */
export function humanize(code: string): string {
  const trimmed = code.trim();
  if (!/^[a-z0-9]+(?:[_-][a-z0-9]+)*$/.test(trimmed)) {
    return trimmed;
  }
  const words = trimmed.replace(/[_-]+/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function lookup(labels: Readonly<Record<string, string>>, code: unknown): string {
  const value = clean(code);
  if (!value) {
    return "";
  }
  return Object.hasOwn(labels, value) ? (labels[value] ?? value) : humanize(value);
}

/** The carrier's display name: carrier_name, else the name of the carrier ID, else null. */
export function carrierLabel(parcel: Pick<Parcel, "carrier" | "carrier_name">): string | null {
  const name = clean(parcel.carrier_name);
  if (name) {
    return name;
  }
  const id = clean(parcel.carrier);
  if (!id || id === "other") {
    return null;
  }
  return Object.hasOwn(CARRIER_NAMES, id) ? carrierName(id) : humanize(id);
}

type Titled = Pick<
  Parcel,
  "restricted" | "merchant" | "name" | "carrier" | "carrier_name" | "tracking_number"
>;

/**
 * The name shown for a parcel: "Private parcel" when restricted, else the
 * merchant, its name in the Parcel app, the carrier, the tracking number, or
 * "Parcel".
 */
export function parcelTitle(parcel: Titled): string {
  if (parcel.restricted) {
    return STRINGS.privateParcel;
  }
  return (
    clean(parcel.merchant) ??
    clean(parcel.name) ??
    carrierLabel(parcel) ??
    clean(parcel.tracking_number) ??
    STRINGS.unnamedParcel
  );
}

/** The carrier shown under the title, or null when the title already is the carrier. */
export function parcelSubtitle(parcel: Titled): string | null {
  const carrier = carrierLabel(parcel);
  return carrier && carrier !== parcelTitle(parcel) ? carrier : null;
}

/** The parcel's name in the Parcel app, or null when hidden or already the title. */
export function parcelAppName(parcel: Titled): string | null {
  const name = clean(parcel.name);
  return name && !parcel.restricted && name !== parcelTitle(parcel) ? name : null;
}

/** Where the expected date comes from, shown when it's the Parcel app; else null. */
export function etaSourceLabel(parcel: Pick<Parcel, "eta_source">): string | null {
  return parcel.eta_source === "parcelapp" ? sourceLabel(parcel.eta_source) : null;
}

export function statusLabel(status: unknown): string {
  return lookup(STATUS_LABELS, status);
}

export function kindLabel(kind: unknown): string {
  return lookup(KIND_LABELS, kind);
}

export function sourceLabel(source: unknown): string {
  return lookup(SOURCE_LABELS, source);
}

/** The notice on a parcel whose delivery is only inferred, saying why. */
export function inferredNotice(parcel: Pick<Parcel, "inferred_reason">): string {
  switch (parcel.inferred_reason) {
    case "quiet":
      return STRINGS.inferredQuietNotice;
    case "return":
      return STRINGS.inferredReturnNotice;
    default:
      return STRINGS.inferredNotice;
  }
}

/** A readable review reason: a known label, else the code made readable, else the text as sent. */
export function reasonLabel(reason: unknown): string {
  return lookup(REASON_LABELS, reason);
}

/** What a note on an AI answer means, in one line; null for a code without a meaning. */
export function noteMeaning(code: unknown): string | null {
  const value = clean(code);
  return value && Object.hasOwn(NOTE_MEANINGS, value) ? (NOTE_MEANINGS[value] ?? null) : null;
}

/** Why a parcel was merged automatically, for use inside a sentence; "" without a reason. */
export function mergeReasonLabel(reason: unknown): string {
  return lookup(MERGE_REASON_LABELS, reason);
}
