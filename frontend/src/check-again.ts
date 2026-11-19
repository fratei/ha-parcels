/** "Check again" in the details: who gets it, and what it did. */

import { etaRange, isActiveParcel } from "./parcels.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { AiMode, Parcel } from "./types.ts";

/** What `parcels/parcel/check_again` did with the parcel's e-mails. */
export interface CheckAgainResult {
  /** Downloaded and read again. */
  read: number;
  /** Sent to the local AI for what the parsers left out. */
  queued: number;
  /** No longer in the mailbox. */
  gone: number;
  /** Couldn't be downloaded this time. */
  failed: number;
}

export interface AiState {
  enabled: boolean;
  mode: AiMode;
}

/** Administrators can check an open parcel without a date again. */
export function canCheckAgain(parcel: Parcel, isAdmin: boolean): boolean {
  return (
    isAdmin &&
    !parcel.restricted &&
    !parcel.archived &&
    isActiveParcel(parcel) &&
    etaRange(parcel) === null
  );
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : 0;
}

export function normalizeCheckAgain(raw: unknown): CheckAgainResult {
  const value = (raw !== null && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  return {
    read: count(value.read),
    queued: count(value.queued),
    gone: count(value.gone),
    failed: count(value.failed),
  };
}

function counted(value: number, one: string, many: string): string | null {
  if (value <= 0) {
    return null;
  }
  return value === 1 ? one : fmt(many, { count: value });
}

/** "Read 2 e-mails again. The local AI is checking 2 e-mails. What it finds waits under Needs review." */
export function checkAgainText(result: CheckAgainResult, ai: AiState): string {
  if (result.read + result.gone + result.failed === 0) {
    return STRINGS.checkAgainNoEmails;
  }
  const parts = [
    counted(result.read, STRINGS.checkAgainReadOne, STRINGS.checkAgainReadMany),
    counted(result.gone, STRINGS.checkAgainGoneOne, STRINGS.checkAgainGoneMany),
    counted(result.failed, STRINGS.checkAgainFailedOne, STRINGS.checkAgainFailedMany),
  ];
  if (result.queued > 0) {
    parts.push(
      counted(result.queued, STRINGS.checkAgainQueuedOne, STRINGS.checkAgainQueuedMany),
      ai.mode === "suggest" ? STRINGS.checkAgainSuggest : STRINGS.checkAgainAuto,
    );
  } else if (result.read > 0) {
    parts.push(ai.enabled ? STRINGS.checkAgainNothingForAi : STRINGS.checkAgainAiOff);
  }
  return parts.filter((part): part is string => part !== null).join(" ");
}
