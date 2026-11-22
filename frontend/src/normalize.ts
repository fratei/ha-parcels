/**
 * Defensive conversion of WebSocket payloads into the typed data contract, so a
 * missing or malformed field can never break rendering.
 */
import { isYmd, localDateOf } from "./dates.ts";
import { LEFT_AT } from "./types.ts";
import type {
  AiMode,
  AutoMerged,
  CustomerReturn,
  FilteredItem,
  InferredReason,
  LeftAt,
  MergeSuggestion,
  OrderInfo,
  OriginInfo,
  Parcel,
  ParcelDetails,
  ParcelSender,
  ParcelSource,
  ParcelStatus,
  PickupRule,
  ReturnEmail,
  ReviewItem,
  SenderChecks,
  Settings,
  Snapshot,
  Suggestion,
  TimelineEntry,
  TimelineSource,
} from "./types.ts";

type Obj = Record<string, unknown>;

function isObj(value: unknown): value is Obj {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function str(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function strs(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function id(value: unknown): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}

function count(value: unknown): number {
  return Number.isSafeInteger(value) && (value as number) > 0 ? (value as number) : 0;
}

function seconds(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function list<T>(value: unknown, convert: (item: unknown) => T | null): T[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const result: T[] = [];
  for (const item of value) {
    const converted = convert(item);
    if (converted !== null) {
      result.push(converted);
    }
  }
  return result;
}

function inferredReason(value: unknown): InferredReason | null {
  return value === "shop" || value === "return" || value === "quiet" ? value : null;
}

function leftAt(value: unknown): LeftAt | null {
  return (LEFT_AT as readonly unknown[]).includes(value) ? (value as LeftAt) : null;
}

function day(value: unknown): string | null {
  return isYmd(value) ? value : null;
}

function source(value: unknown): ParcelSource {
  return value === "ai" || value === "manual" || value === "seventeentrack" || value === "parcelapp"
    ? value
    : "parser";
}

function etaSource(value: unknown): ParcelSource | null {
  return typeof value === "string" && value ? source(value) : null;
}

function autoMerged(value: unknown): AutoMerged | null {
  if (!isObj(value) || !id(value.origin)) {
    return null;
  }
  return { origin: text(value.origin), at: text(value.at), reason: text(value.reason) };
}

function sender(raw: unknown): ParcelSender | null {
  if (!isObj(raw)) {
    return null;
  }
  const name = id(raw.name);
  if (!name) {
    return null;
  }
  return {
    name,
    source: raw.source === "seventeentrack" || raw.source === "parcelapp" ? raw.source : "email",
    carrier: raw.carrier === true,
    count: Math.max(1, count(raw.count)),
  };
}

export function normalizeParcel(raw: unknown): Parcel | null {
  if (!isObj(raw)) {
    return null;
  }
  const parcelId = id(raw.id);
  if (!parcelId) {
    return null;
  }
  return {
    id: parcelId,
    merchant: str(raw.merchant),
    seller: str(raw.seller),
    name: str(raw.name),
    carrier: str(raw.carrier),
    carrier_name: str(raw.carrier_name),
    tracking_number: str(raw.tracking_number),
    tracking_url: str(raw.tracking_url),
    // Unknown statuses are kept as sent; the cards treat them like an active status.
    status: text(raw.status) as ParcelStatus,
    status_time: str(raw.status_time),
    status_undated: raw.status_undated === true,
    status_timeless: raw.status_timeless === true,
    eta_start: str(raw.eta_start),
    eta_end: str(raw.eta_end),
    window_start: str(raw.window_start),
    window_end: str(raw.window_end),
    eta_source: etaSource(raw.eta_source),
    delivered_at: str(raw.delivered_at),
    delivered_undated: raw.delivered_undated === true,
    delivered_timeless: raw.delivered_timeless === true,
    status_reported: raw.status_reported === true,
    next_attempt: day(raw.next_attempt),
    collect_by: day(raw.collect_by),
    left_at: leftAt(raw.left_at),
    inferred: raw.inferred === true,
    inferred_reason: inferredReason(raw.inferred_reason),
    pickup_point: str(raw.pickup_point),
    pickup_code: str(raw.pickup_code),
    has_code: raw.has_code === true,
    order_numbers: strs(raw.order_numbers),
    references: strs(raw.references),
    items: strs(raw.items),
    private: raw.private === true,
    owners: strs(raw.owners),
    source: source(raw.source),
    ai: raw.ai === true,
    ai_filled: raw.ai_filled === true,
    auto_merged: autoMerged(raw.auto_merged),
    provisional: raw.provisional === true,
    archived: raw.archived === true,
    origins: strs(raw.origins),
    shipment_group: id(raw.shipment_group),
    restricted: raw.restricted === true,
    senders: list(raw.senders, sender),
    ordered_at: id(raw.ordered_at),
    shipped_at: id(raw.shipped_at),
  };
}

export function normalizeSuggestion(raw: unknown): Suggestion | null {
  if (!isObj(raw)) {
    return null;
  }
  return {
    kind: text(raw.kind),
    merchant: str(raw.merchant),
    carrier: str(raw.carrier),
    tracking_numbers: strs(raw.tracking_numbers),
    order_numbers: strs(raw.order_numbers),
    eta_start: str(raw.eta_start),
    eta_end: str(raw.eta_end),
    window_start: str(raw.window_start),
    window_end: str(raw.window_end),
    pickup_point: str(raw.pickup_point),
    pickup_code: str(raw.pickup_code),
    items: strs(raw.items),
    reference: str(raw.reference),
  };
}

export function normalizeReviewItem(raw: unknown): ReviewItem | null {
  if (!isObj(raw)) {
    return null;
  }
  const itemId = id(raw.id);
  if (!itemId) {
    return null;
  }
  return {
    id: itemId,
    created: text(raw.created),
    received: str(raw.received),
    sender: text(raw.sender),
    sender_domain: text(raw.sender_domain),
    subject: text(raw.subject),
    mailbox_owner: str(raw.mailbox_owner),
    reason: text(raw.reason),
    authenticated: raw.authenticated === true,
    trusted_sender: raw.trusted_sender === true,
    checks: senderChecks(raw.checks),
    fill: raw.fill === true,
    errors: checkCodes(raw.errors),
    notes: checkCodes(raw.notes),
    source: raw.source === "ai" ? "ai" : "parser",
    suggestion: normalizeSuggestion(raw.suggestion),
  };
}

const CHECK_CODE = /^[a-z0-9_]{1,40}$/;

/** The codes of the checks an AI answer failed, or of its notes; anything else is dropped. */
function checkCodes(raw: unknown): string[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const codes = raw.filter((code): code is string => typeof code === "string" && CHECK_CODE.test(code));
  return [...new Set(codes)];
}

/** How the sender checks went; null when the item has none. */
function senderChecks(raw: unknown): SenderChecks | null {
  if (!isObj(raw)) {
    return null;
  }
  const headers = count(raw.headers);
  const used = raw.used;
  return {
    headers,
    // Kept in order and position: an empty name is a header that named no server.
    servers: Array.isArray(raw.servers)
      ? raw.servers.map((server) => (typeof server === "string" ? server : ""))
      : [],
    used: Number.isSafeInteger(used) && (used as number) >= 0 && (used as number) < headers ? (used as number) : null,
    dkim: text(raw.dkim),
    dmarc: text(raw.dmarc),
    spf: text(raw.spf),
    originals: count(raw.originals),
  };
}

export function normalizeFilteredItem(raw: unknown): FilteredItem | null {
  if (!isObj(raw)) {
    return null;
  }
  const itemId = id(raw.id);
  if (!itemId) {
    return null;
  }
  return {
    id: itemId,
    created: text(raw.created),
    received: str(raw.received),
    sender: text(raw.sender),
    sender_domain: text(raw.sender_domain),
    subject: text(raw.subject),
    removed: raw.removed === true,
  };
}

/** A merge suggestion; null without an id, its parcel or any candidate. */
export function normalizeMergeSuggestion(raw: unknown): MergeSuggestion | null {
  if (!isObj(raw)) {
    return null;
  }
  const suggestionId = id(raw.id);
  const parcel = normalizeParcel(raw.parcel);
  const candidates = list(raw.candidates, normalizeParcel);
  if (!suggestionId || !parcel || !candidates.length) {
    return null;
  }
  return {
    id: suggestionId,
    reason: text(raw.reason),
    merchant: str(raw.merchant),
    day: isYmd(raw.day) ? raw.day : null,
    parcel,
    candidates,
  };
}

function aiMode(value: unknown): AiMode {
  return value === "suggest" || value === "auto" ? value : "off";
}

/**
 * `now` is only used when the server didn't send `today` (it always should):
 * then today is the current date in the server's time zone.
 */
export function normalizeSettings(raw: unknown, now: number = Date.now()): Settings {
  const settings = isObj(raw) ? raw : {};
  const timeZone = id(settings.time_zone) ?? "UTC";
  const today = isYmd(settings.today)
    ? settings.today
    : (localDateOf(new Date(now).toISOString(), timeZone) ?? "1970-01-01");
  return {
    user_is_admin: settings.user_is_admin === true,
    ai_enabled: settings.ai_enabled === true,
    ai_mode: aiMode(settings.ai_mode),
    ai_queue: count(settings.ai_queue),
    ai_queue_seconds: seconds(settings.ai_queue_seconds),
    dashboard_url: text(settings.dashboard_url),
    seventeentrack: settings.seventeentrack === true,
    time_zone: timeZone,
    today,
  };
}

export function normalizeSnapshot(raw: unknown, now: number = Date.now()): Snapshot {
  const snapshot = isObj(raw) ? raw : {};
  return {
    parcels: list(snapshot.parcels, normalizeParcel),
    returns: list(snapshot.returns, normalizeReturn),
    review: list(snapshot.review, normalizeReviewItem),
    merge_suggestions: list(snapshot.merge_suggestions, normalizeMergeSuggestion),
    filtered: list(snapshot.filtered, normalizeFilteredItem),
    settings: normalizeSettings(snapshot.settings, now),
  };
}

function pickupRule(value: unknown): PickupRule | null {
  return value === "email" || value === "next_working_day" || value === "assumed" ? value : null;
}

function returnEmail(raw: unknown): ReturnEmail | null {
  if (!isObj(raw)) {
    return null;
  }
  return { time: str(raw.time), label: text(raw.label), source: source(raw.source) };
}

/** A customer return; null without an id or a day to show it on. */
export function normalizeReturn(raw: unknown): CustomerReturn | null {
  if (!isObj(raw)) {
    return null;
  }
  const returnId = id(raw.id);
  if (!returnId || !isYmd(raw.day)) {
    return null;
  }
  return {
    id: returnId,
    merchant: str(raw.merchant),
    carrier: str(raw.carrier),
    carrier_name: str(raw.carrier_name),
    tracking_number: str(raw.tracking_number),
    tracking_url: str(raw.tracking_url),
    day: raw.day,
    pickup: isYmd(raw.pickup) ? raw.pickup : null,
    pickup_rule: pickupRule(raw.pickup_rule),
    started: str(raw.started),
    received: raw.received === true,
    order_numbers: strs(raw.order_numbers),
    items: strs(raw.items),
    parcel_ids: strs(raw.parcel_ids),
    emails: list(raw.emails, returnEmail),
    private: raw.private === true,
    owners: strs(raw.owners),
    archived: raw.archived === true,
    restricted: raw.restricted === true,
  };
}

function timelineSource(value: unknown): TimelineSource {
  return value === "inferred" || value === "inferred_return" || value === "quiet" ? value : source(value);
}

function timelineEntry(raw: unknown): TimelineEntry | null {
  if (!isObj(raw)) {
    return null;
  }
  return {
    time: text(raw.time),
    status: text(raw.status) as ParcelStatus,
    source: timelineSource(raw.source),
    label: text(raw.label),
    undated: raw.undated === true,
    timeless: raw.timeless === true,
  };
}

function orderInfo(raw: unknown): OrderInfo | null {
  if (!isObj(raw)) {
    return null;
  }
  return {
    id: text(raw.id),
    merchant: str(raw.merchant),
    number: text(raw.number),
    placed_at: str(raw.placed_at),
    parcel_ids: strs(raw.parcel_ids),
  };
}

/** [n, total] with 1 <= n <= total, else null. */
function shipment(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length !== 2) {
    return null;
  }
  const [n, total] = value.map(count);
  return n && total && n <= total ? [n, total] : null;
}

function originInfo(raw: unknown): OriginInfo | null {
  if (!isObj(raw)) {
    return null;
  }
  const originId = id(raw.id);
  if (!originId) {
    return null;
  }
  return {
    id: originId,
    label: text(raw.label),
    source: source(raw.source),
    sender_name: id(raw.sender_name),
    name: id(raw.name),
    time: str(raw.time),
    status: id(raw.status) as ParcelStatus | null,
    kind: id(raw.kind),
    event_time: id(raw.event_time),
    undated: raw.undated === true,
    timeless: raw.timeless === true,
    dayless: raw.dayless === true,
    eta_start: isYmd(raw.eta_start) ? raw.eta_start : null,
    eta_end: isYmd(raw.eta_end) ? raw.eta_end : null,
    window_start: id(raw.window_start),
    window_end: id(raw.window_end),
    carrier: id(raw.carrier),
    carrier_name: id(raw.carrier_name),
    tracking_number: id(raw.tracking_number),
    reference: id(raw.reference),
    merchant: id(raw.merchant),
    seller: id(raw.seller),
    order_numbers: strs(raw.order_numbers),
    items: strs(raw.items),
    pickup_point: id(raw.pickup_point),
    shipment: shipment(raw.shipment),
    email: raw.email === true,
    edits: raw.edits === true,
    part_of: id(raw.part_of),
    split_blocked: id(raw.split_blocked),
  };
}

/** Converts a `parcels/get` result; null when it has no usable parcel. */
export function normalizeDetails(raw: unknown): ParcelDetails | null {
  if (!isObj(raw)) {
    return null;
  }
  const parcel = normalizeParcel(raw.parcel);
  if (!parcel) {
    return null;
  }
  return {
    parcel,
    timeline: list(raw.timeline, timelineEntry),
    orders: list(raw.orders, orderInfo),
    origins: list(raw.origins, originInfo),
  };
}
