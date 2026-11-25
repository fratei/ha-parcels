/**
 * The rows of a parcel's "E-mails" section: what each e-mail and source said
 * and added, from what Parcels stored. Never a subject, a body or an Amazon
 * shipment ID.
 */
import { parseInstant } from "./dates.ts";
import { numberTail } from "./describe.ts";
import { formatDateRange, formatDayTime, formatDayWithoutTime, formatWindow, type LocaleOptions } from "./format.ts";
import { carrierLabel, kindLabel, sourceLabel, statusLabel } from "./labels.ts";
import { STRINGS, fmt } from "./strings.ts";
import type { OriginInfo } from "./types.ts";

export interface OriginRow {
  /** The origins it shows: the row's own, then what the local AI read in that e-mail. */
  ids: string[];
  /** The row's own origin. */
  lead: string;
  /** Who or what it came from. */
  header: string;
  /** When it arrived; "" when not known. */
  when: string;
  /** What it said: the kind of e-mail or the status, its time, the expected days and window. */
  said: string;
  /** What it added besides items: shop, orders, shipment, carrier and number, pickup point… */
  facts: string[];
  items: string[];
  /** "all" when the local AI read the e-mail, "part" when it filled some of it in. */
  ai: "all" | "part" | null;
  email: boolean;
  /** The user's edits of the parcel. */
  edits: boolean;
  /** Why it can't be moved to a new parcel (a code); null when it can. */
  splitBlocked: string | null;
  /** The sender, to find repeated e-mails. */
  sender: string;
}

export type OriginEntry =
  | { type: "row"; row: OriginRow }
  | {
      type: "repeats";
      /** The latest repeat's row, which stands for the fold. */
      key: string;
      header: string;
      /** Oldest first. */
      rows: OriginRow[];
      latest: OriginRow;
    };

const SAME_TIME_MS = 60_000;

function text(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

/** An e-mail's row with what the local AI read in it: the row's values win. */
function combine(lead: OriginInfo, fills: OriginInfo[]): OriginInfo {
  const all = [lead, ...fills];
  const said = all.find((origin) => origin.status || origin.kind) ?? lead;
  const estimate = all.find((origin) => origin.eta_start || origin.window_start || origin.window_end) ?? lead;
  const carrier = all.find((origin) => origin.carrier || origin.carrier_name) ?? lead;
  const first = <K extends keyof OriginInfo>(key: K): OriginInfo[K] =>
    all.find((origin) => origin[key] !== null && origin[key] !== "")?.[key] ?? lead[key];
  const union = (key: "order_numbers" | "items"): string[] => [...new Set(all.flatMap((origin) => origin[key]))];
  return {
    ...lead,
    status: said.status,
    kind: said.kind,
    event_time: said.event_time,
    undated: said.undated,
    timeless: said.timeless,
    dayless: said.dayless,
    eta_start: estimate.eta_start,
    eta_end: estimate.eta_end,
    window_start: estimate.window_start,
    window_end: estimate.window_end,
    carrier: carrier.carrier,
    carrier_name: carrier.carrier_name,
    tracking_number: first("tracking_number"),
    reference: first("reference"),
    merchant: first("merchant"),
    seller: first("seller"),
    pickup_point: first("pickup_point"),
    shipment: first("shipment"),
    name: first("name"),
    order_numbers: union("order_numbers"),
    items: union("items"),
  };
}

function header(origin: OriginInfo): string {
  if (origin.edits) {
    return STRINGS.originEdits;
  }
  if (origin.email) {
    return text(origin.sender_name) ?? text(origin.label) ?? STRINGS.originEmail;
  }
  return text(origin.label) ?? sourceLabel(origin.source);
}

function saidText(origin: OriginInfo, locale: LocaleOptions): string {
  const parts: string[] = [];
  const kind = origin.kind && origin.kind !== "unknown" && origin.kind !== "not_parcel" ? kindLabel(origin.kind) : "";
  const label = kind || (origin.status ? statusLabel(origin.status) : "");
  if (label) {
    parts.push(label);
    const at = origin.event_time ? parseInstant(origin.event_time) : null;
    const arrived = origin.time ? parseInstant(origin.time) : null;
    if (origin.undated) {
      parts.push((origin.timeless && formatDayWithoutTime(origin.event_time, locale)) || STRINGS.dateNotKnownInline);
    } else if (at !== null && (arrived === null || Math.abs(at - arrived) >= SAME_TIME_MS)) {
      parts.push(formatDayTime(origin.event_time, locale));
    }
  }
  if (origin.eta_start) {
    const days = formatDateRange(origin.eta_start, origin.eta_end ?? origin.eta_start, locale);
    parts.push(fmt(STRINGS.expectedOn, { date: days }));
  }
  const window = formatWindow(origin.window_start, origin.window_end, locale);
  if (window) {
    parts.push(window);
  }
  return parts.join(" · ");
}

function facts(origin: OriginInfo): string[] {
  const result: string[] = [];
  const merchant = text(origin.merchant);
  if (merchant) {
    result.push(fmt(STRINGS.factShop, { name: merchant }));
  }
  const seller = text(origin.seller);
  if (seller) {
    result.push(fmt(STRINGS.factSeller, { name: seller }));
  }
  for (const order of origin.order_numbers) {
    const tail = numberTail(order);
    if (tail) {
      result.push(fmt(STRINGS.orderTail, { tail }));
    }
  }
  if (origin.shipment) {
    const [n, total] = origin.shipment;
    result.push(fmt(STRINGS.factShipment, { n: String(n), total: String(total) }));
  }
  const carrier = carrierLabel(origin);
  const number = numberTail(origin.tracking_number);
  if (carrier && number) {
    result.push(fmt(STRINGS.factCarrierNumber, { carrier, tail: number }));
  } else if (carrier) {
    result.push(carrier);
  } else if (number) {
    result.push(fmt(STRINGS.numberTail, { tail: number }));
  }
  const reference = numberTail(origin.reference);
  if (reference) {
    result.push(fmt(STRINGS.factReference, { tail: reference }));
  }
  const pickup = text(origin.pickup_point);
  if (pickup) {
    result.push(fmt(STRINGS.factPickup, { place: pickup }));
  }
  const name = text(origin.name);
  if (name) {
    result.push(fmt(STRINGS.factName, { name }));
  }
  return result;
}

/** One row per e-mail or source, in the given order (oldest first); the local AI's reads join their e-mail. */
export function originRows(origins: readonly OriginInfo[], locale: LocaleOptions): OriginRow[] {
  const ids = new Set(origins.map((origin) => origin.id));
  const fills = new Map<string, OriginInfo[]>();
  for (const origin of origins) {
    if (origin.part_of && origin.part_of !== origin.id && ids.has(origin.part_of)) {
      fills.set(origin.part_of, [...(fills.get(origin.part_of) ?? []), origin]);
    }
  }
  const rows: OriginRow[] = [];
  for (const lead of origins) {
    if (lead.part_of && lead.part_of !== lead.id && ids.has(lead.part_of)) {
      continue;
    }
    const parts = fills.get(lead.id) ?? [];
    const origin = combine(lead, parts);
    const name = header(origin);
    let ai: OriginRow["ai"] = null;
    if (lead.source === "ai") {
      ai = "all";
    } else if (parts.length) {
      ai = "part";
    }
    rows.push({
      ids: [lead.id, ...parts.map((part) => part.id)],
      lead: lead.id,
      header: name,
      when: formatDayTime(lead.time, locale),
      said: saidText(origin, locale),
      facts: facts(origin),
      items: origin.items.filter((item) => item.trim()),
      ai,
      email: lead.email,
      edits: lead.edits,
      splitBlocked: lead.split_blocked,
      sender: `${lead.email ? "email" : lead.source}:${name}`,
    });
  }
  return rows;
}

/**
 * The rows to show: an e-mail that adds nothing new to the earlier ones of
 * its sender is a repeat; two or more repeats of a sender fold into one entry
 * where the latest of them was.
 */
export function originEntries(rows: readonly OriginRow[]): OriginEntry[] {
  const seen = new Map<string, Set<string>>();
  const repeats = new Map<string, OriginRow[]>();
  for (const row of rows) {
    if (!row.email || row.edits) {
      continue;
    }
    const known = seen.get(row.sender);
    const added = [...row.facts, ...row.items.map((item) => `\u0000${item}`)];
    if (known && added.every((value) => known.has(value))) {
      repeats.set(row.sender, [...(repeats.get(row.sender) ?? []), row]);
    }
    seen.set(row.sender, new Set([...(known ?? []), ...added]));
  }
  const folded = new Map<string, OriginRow[]>();
  for (const list of repeats.values()) {
    if (list.length >= 2) {
      for (const row of list) {
        folded.set(row.lead, list);
      }
    }
  }
  const entries: OriginEntry[] = [];
  for (const row of rows) {
    const list = folded.get(row.lead);
    if (!list) {
      entries.push({ type: "row", row });
      continue;
    }
    const latest = list[list.length - 1]!;
    if (latest.lead === row.lead) {
      entries.push({ type: "repeats", key: latest.lead, header: row.header, rows: list, latest });
    }
  }
  return entries;
}

/** "E-mails (3)", or "E-mails and updates (4)" with other sources. */
export function originsTitle(rows: readonly OriginRow[]): string {
  const template = rows.every((row) => row.email) ? STRINGS.originsTitle : STRINGS.originsAndUpdatesTitle;
  return fmt(template, { count: String(rows.length) });
}

/** The origin IDs of the chosen rows (by their own origin), in row order. */
export function rowIds(rows: readonly OriginRow[], leads: readonly string[]): string[] {
  const chosen = new Set(leads);
  return rows.filter((row) => chosen.has(row.lead)).flatMap((row) => row.ids);
}

/** Why a row can't move to a new parcel, for the user; null when it can. */
export function splitBlockedReason(code: string | null): string | null {
  switch (code) {
    case null:
      return null;
    case "nothing_left":
      return STRINGS.splitBlockedNothingLeft;
    case "shared_number":
    case "shared_shipment":
      return STRINGS.splitBlockedShared;
    default:
      return STRINGS.splitBlockedOther;
  }
}

/** What the details dialog does once an e-mail removed from Parcels is restored. */
export interface RestoreOutcome {
  notice: "restored" | "elsewhere" | "review" | "noParcel";
  /** The parcel to show instead, when the one shown went with the e-mail. */
  follow: string | null;
  /** Another parcel the notice offers to show. */
  show: string | null;
}

/**
 * Reads the answer to a restore: the e-mail went back to Needs review (gone
 * from the mailbox) or was read again into the visible parcels listed.
 * `shownGone` is true when the parcel shown is no longer there.
 */
export function restoreOutcome(
  result: { review: string | null; parcels: readonly string[] },
  parcelId: string,
  shownGone: boolean,
): RestoreOutcome {
  const other = result.parcels[0];
  if (result.review !== null) {
    return { notice: "review", follow: null, show: null };
  }
  if (result.parcels.includes(parcelId)) {
    return { notice: "restored", follow: null, show: null };
  }
  if (other === undefined) {
    return { notice: "noParcel", follow: null, show: null };
  }
  if (shownGone) {
    return { notice: "restored", follow: other, show: null };
  }
  return { notice: "elsewhere", follow: null, show: other };
}
