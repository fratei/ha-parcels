/**
 * Data contract of the Parcels integration (WebSocket API and services) and the
 * small part of Home Assistant's frontend `hass` object that the cards use.
 */

export const PARCEL_STATUSES = [
  "ordered",
  "shipped",
  "in_transit",
  "out_for_delivery",
  "delivered",
  "attempted",
  "exception",
  "ready_for_pickup",
  "returned",
  "cancelled",
] as const;

export type ParcelStatus = (typeof PARCEL_STATUSES)[number];

export type ParcelSource = "parser" | "ai" | "manual" | "seventeentrack" | "parcelapp";

/**
 * A timeline entry's source. Inferred deliveries: "inferred" when worked out
 * from another parcel's, "inferred_return" from a return of its order,
 * "inferred_shipment" from another package of its shipment, "quiet" after
 * three weeks without news.
 */
export type TimelineSource = ParcelSource | "inferred" | "inferred_return" | "inferred_shipment" | "quiet";

/** Why a delivery was inferred; see `TimelineSource`. */
export type InferredReason = "shop" | "return" | "shipment" | "quiet";

/** Where a delivered parcel was left: fixed categories, never names or numbers. */
export const LEFT_AT = ["neighbour", "mailbox", "door", "reception", "garage", "locker"] as const;

export type LeftAt = (typeof LEFT_AT)[number];

export type AiMode = "off" | "suggest" | "auto";

/** Who told about a parcel: a sender of e-mails, 17TRACK or the Parcel app. */
export interface ParcelSender {
  /** The known sender's name, else the e-mail's sender domain or the source's name. */
  name: string;
  source: "email" | "seventeentrack" | "parcelapp";
  /** The carrier's own e-mails. */
  carrier: boolean;
  /** How many e-mails or updates; at least 1. */
  count: number;
}

export interface AutoMerged {
  origin: string;
  at: string;
  reason: string;
}

/** When and where Amazon's tracking, via the Parcel app, says a shipment was delivered. */
export interface AmazonTracking {
  delivered: string;
  /** Amazon gave the day but not the time. */
  timeless: boolean;
  place: string | null;
}

export interface Parcel {
  id: string;
  merchant: string | null;
  /** Who sold it, when the merchant is a marketplace; null when restricted. */
  seller: string | null;
  /** What the user calls the parcel in the Parcel app; null when restricted. */
  name: string | null;
  carrier: string | null;
  carrier_name: string | null;
  tracking_number: string | null;
  tracking_url: string | null;
  status: ParcelStatus;
  status_time: string | null;
  /**
   * The status came from a source that gave no date that could be read:
   * `status_time` only keeps the parcel on the last day known, and is null
   * when no day is.
   */
  status_undated: boolean;
  /**
   * Of an undated status, the source gave the day but not the time:
   * `status_time` is on that day.
   */
  status_timeless: boolean;
  eta_start: string | null;
  eta_end: string | null;
  window_start: string | null;
  window_end: string | null;
  /** Where the expected date comes from; null without one or when restricted. */
  eta_source: ParcelSource | null;
  delivered_at: string | null;
  /** Like `status_undated`, for `delivered_at`. */
  delivered_undated: boolean;
  /** Like `status_timeless`, for `delivered_at`. */
  delivered_timeless: boolean;
  /**
   * `status_time` is when an e-mail reported the status, not when it
   * happened: the e-mail didn't say.
   */
  status_reported: boolean;
  /** The day of the next attempt ("YYYY-MM-DD"), after a missed one. */
  next_attempt: string | null;
  /**
   * The last day to collect it at its pickup point ("YYYY-MM-DD"), while it
   * waits there or after a missed attempt; null when not known or restricted.
   */
  collect_by: string | null;
  /** Where it was left once delivered; null when not known or restricted. */
  left_at: LeftAt | null;
  /** Delivered only by inference, until the user keeps or undoes it. */
  inferred: boolean;
  /**
   * Why: "shop" when another parcel from the shop was delivered around its
   * dates, "return" when its items are being sent back, "shipment" when
   * another package of its shipment was delivered on or after its day,
   * "quiet" when it had no news for three weeks; null when not inferred.
   */
  inferred_reason: InferredReason | null;
  /**
   * Delivered only because someone marked it delivered, or kept an inferred
   * delivery, in Parcels: Undo takes that back. False once a carrier, the
   * shop, 17TRACK or the Parcel app reports the delivery.
   */
  delivered_by_hand: boolean;
  pickup_point: string | null;
  /**
   * The PIN or pickup code. The list has it while the parcel is on its way;
   * the details (`parcels/get`) always do.
   */
  pickup_code: string | null;
  /** The parcel has a PIN or pickup code. */
  has_code: boolean;
  order_numbers: string[];
  /** The carrier's or shop's references for the shipment, such as Paack's order number. */
  references: string[];
  items: string[];
  private: boolean;
  owners: string[];
  source: ParcelSource;
  ai: boolean;
  /** The local AI filled in details a parser missed; false once confirmed. */
  ai_filled: boolean;
  auto_merged: AutoMerged | null;
  provisional: boolean;
  archived: boolean;
  origins: string[];
  /** Packages sent together share this ID (the shipment's first parcel ID); null when alone. */
  shipment_group: string | null;
  restricted: boolean;
  /** Who told about it, in the order they first did; empty when restricted. */
  senders: ParcelSender[];
  /** When it was ordered, per a dated e-mail; null when not known or restricted. */
  ordered_at: string | null;
  /** When it left, per a dated e-mail; null when not known or restricted. */
  shipped_at: string | null;
  /** What Amazon's tracking says of an Amazon shipment; null otherwise or when restricted. */
  amazon_tracking: AmazonTracking | null;
}

/** What the parser or the AI read from an e-mail; also the shape of accept overrides. */
export interface Suggestion {
  kind: string;
  merchant: string | null;
  carrier: string | null;
  tracking_numbers: string[];
  order_numbers: string[];
  eta_start: string | null;
  eta_end: string | null;
  window_start: string | null;
  window_end: string | null;
  pickup_point: string | null;
  pickup_code: string | null;
  items: string[];
  amazon_shipment_id: string | null;
  /** The carrier's or shop's reference for the shipment, such as Paack's order number. */
  reference: string | null;
}

export interface SenderChecks {
  /** How many Authentication-Results headers the e-mail had. */
  headers: number;
  /** The server named in each header, in order. */
  servers: string[];
  /** The header that was used, by position, or null when none was. */
  used: number | null;
  dkim: string;
  dmarc: string;
  spf: string;
  /** Headers the provider renamed, because they came with the e-mail. */
  originals: number;
}

export interface ReviewItem {
  id: string;
  created: string;
  received: string | null;
  sender: string;
  sender_domain: string;
  /** The organisation's domain, which trusting or ignoring the sender applies to. */
  sender_org: string;
  subject: string;
  mailbox_owner: string | null;
  reason: string;
  authenticated: boolean;
  /** The sender is trusted, but this e-mail failed the sender checks. */
  trusted_sender: boolean;
  /** Parcels has a parser for the sender or lists it, so it can't be trusted or ignored from here. */
  known_sender: boolean;
  /** A free mail domain, such as gmail.com: anyone can send from it, so it's neither trusted nor ignored. */
  free_mail: boolean;
  checks: SenderChecks | null;
  /** The local AI fills in details the parser missed, for a parcel the e-mail already updated. */
  fill: boolean;
  /** The checks a rejected AI answer failed, as codes without values. */
  errors: string[];
  /** What the checks changed in an AI answer, as codes: not failures. */
  notes: string[];
  source: "parser" | "ai";
  suggestion: Suggestion | null;
}

/** What trusting a sender from "Needs review" did. */
export interface TrustResult {
  domain: string;
  added: number;
  rechecking: number;
  kept: number;
}

/** A sender domain whose e-mails Parcels skips (administrators only). */
export interface IgnoredSender {
  domain: string;
  /** When it was last changed. */
  updated: string | null;
}

/** What "Stop ignoring" did. */
export interface UnignoreResult {
  domain: string;
  /** Its recent e-mails being read again. */
  rechecking: number;
}

/** E-mails Parcels gave up reading after trying for days (administrators only). */
export interface UnreadEmails {
  count: number;
  /** Their senders' domains, newest first; at most five. */
  senders: string[];
  /** How many have no known sender: their headers never downloaded. */
  unnamed: number;
  /** When the newest arrived. */
  newest: string | null;
}

/** What "Try again" on the e-mails Parcels couldn't read did. */
export interface RetryResult {
  read: number;
  failed: number;
  /** No longer in any mailbox. */
  gone: number;
}

export interface FilteredItem {
  id: string;
  created: string;
  received: string | null;
  sender: string;
  sender_domain: string;
  subject: string;
  /** Removed from a parcel in its details, rather than filtered when it was read. */
  removed: boolean;
}

export interface Settings {
  user_is_admin: boolean;
  ai_enabled: boolean;
  ai_mode: AiMode;
  /** E-mails waiting for the local AI; 0 for everyone but administrators. */
  ai_queue: number;
  /** About how long the AI needs for them; null when nobody can tell. */
  ai_queue_seconds: number | null;
  dashboard_url: string;
  seventeentrack: boolean;
  time_zone: string;
  /** Home Assistant's local date, "YYYY-MM-DD". */
  today: string;
}

/**
 * Parcels that are probably one: `candidates` may belong to `parcel`. Each
 * user gets those theirs to decide: administrators, and the owners of a
 * private parcel in them.
 */
export interface MergeSuggestion {
  id: string;
  reason: string;
  merchant: string | null;
  /** The delivery day, "YYYY-MM-DD". */
  day: string | null;
  parcel: Parcel;
  candidates: Parcel[];
}

/** Payload of `parcels/list` and of every `parcels/subscribe` event. */
export interface Snapshot {
  parcels: Parcel[];
  /** Customer returns, archived ones included. */
  returns: CustomerReturn[];
  review: ReviewItem[];
  merge_suggestions: MergeSuggestion[];
  filtered: FilteredItem[];
  ignored_senders: IgnoredSender[];
  unread_emails: UnreadEmails;
  settings: Settings;
}

/**
 * Where a return's pickup day comes from: a date in an e-mail, an e-mail that
 * says "next working day", or the shop's usual practice.
 */
export type PickupRule = "email" | "next_working_day" | "assumed";

export interface ReturnEmail {
  time: string | null;
  label: string;
  source: ParcelSource;
}

/**
 * Something sent back to a shop: collected on its pickup day. The parcel it
 * came in keeps its own delivery.
 */
export interface CustomerReturn {
  id: string;
  merchant: string | null;
  carrier: string | null;
  carrier_name: string | null;
  tracking_number: string | null;
  tracking_url: string | null;
  /** The day in the calendar: the pickup, else the day of the first e-mail. */
  day: string;
  pickup: string | null;
  pickup_rule: PickupRule | null;
  /** The time of the first e-mail. */
  started: string | null;
  /** The shop said it has the return. */
  received: boolean;
  /** When someone marked it picked up; null until then. */
  picked_up: string | null;
  order_numbers: string[];
  items: string[];
  /** The parcels the items came in. */
  parcel_ids: string[];
  /** Oldest first. */
  emails: ReturnEmail[];
  private: boolean;
  owners: string[];
  archived: boolean;
  restricted: boolean;
}

export interface TimelineEntry {
  time: string;
  status: ParcelStatus;
  source: TimelineSource;
  label: string;
  /** The source gave no date that could be read: `time` only orders the entry. */
  undated: boolean;
  /** Of an undated entry, the source gave the day but not the time: `time` is on that day. */
  timeless: boolean;
}

export interface OrderInfo {
  id: string;
  merchant: string | null;
  number: string;
  placed_at: string | null;
  parcel_ids: string[];
}

/** What one e-mail or source of a parcel said and added (`parcels/get`), oldest first. */
export interface OriginInfo {
  id: string;
  /** An e-mail's sender domain, or the source's name; may be empty for the user's edits. */
  label: string;
  source: ParcelSource;
  /** The known sender's name, for an e-mail from one. */
  sender_name: string | null;
  /** The delivery's name in the Parcel app. */
  name: string | null;
  /** When it arrived. */
  time: string | null;
  /** The latest status it gave. */
  status: ParcelStatus | null;
  /** What kind of e-mail it was (a MailKind value). */
  kind: string | null;
  /** When that status happened, per the source. */
  event_time: string | null;
  /** The source gave no date for it that could be read. */
  undated: boolean;
  /** Of an undated status, the source gave the day but not the time: `event_time` is on that day. */
  timeless: boolean;
  /** Not even the day is known. */
  dayless: boolean;
  eta_start: string | null;
  eta_end: string | null;
  window_start: string | null;
  window_end: string | null;
  carrier: string | null;
  carrier_name: string | null;
  tracking_number: string | null;
  reference: string | null;
  merchant: string | null;
  seller: string | null;
  order_numbers: string[];
  items: string[];
  pickup_point: string | null;
  /** Which of the order's shipments it's about, [n, total]; null with only one. */
  shipment: [number, number] | null;
  /** It's an e-mail, rather than 17TRACK, the Parcel app or the user's edits. */
  email: boolean;
  /** The user's edits of the parcel. */
  edits: boolean;
  /** What the local AI read in an e-mail: the ID of that e-mail's row, which it belongs to. */
  part_of: string | null;
  /** Why it can't be moved to a new parcel (a code); null when it can. */
  split_blocked: string | null;
}

/** Result of `parcels/get`. */
export interface ParcelDetails {
  parcel: Parcel;
  timeline: TimelineEntry[];
  orders: OrderInfo[];
  origins: OriginInfo[];
  /** The parcels Amazon's tracking rules out as the same package: delivered at another time. */
  contradicted: string[];
  /**
   * The parcels Amazon's tracking points away from: it repeats the times of
   * other packages, not theirs. None of them is in `contradicted`.
   */
  elsewhere: string[];
  /** The e-mails an automatic merge joined list other items than the rest of the parcel's. */
  merged_items_differ: boolean;
}

export interface HassMessage {
  type: string;
  [key: string]: unknown;
}

export type HassUnsubscribe = () => Promise<void>;

export type ConnectionEvent = "ready" | "disconnected" | "reconnect-error";

/** The part of home-assistant-js-websocket's Connection that the cards use. */
export interface HassConnection {
  subscribeMessage<T>(
    callback: (message: T) => void,
    message: HassMessage,
    options?: { resubscribe?: boolean },
  ): Promise<HassUnsubscribe>;
  addEventListener(event: ConnectionEvent, listener: () => void): void;
  removeEventListener(event: ConnectionEvent, listener: () => void): void;
}

export interface HassLocale {
  language: string;
  /** "language", "system", "12" or "24". */
  time_format?: string;
  /** "local" (browser) or "server". */
  time_zone?: string;
}

/** The part of Home Assistant's frontend `hass` object that the cards use. */
export interface HomeAssistant {
  connection: HassConnection;
  language?: string;
  locale?: HassLocale;
  user?: { is_admin?: boolean };
  config?: { time_zone?: string };
  themes?: { darkMode?: boolean };
  callWS<T>(message: HassMessage): Promise<T>;
  callService(
    domain: string,
    service: string,
    serviceData?: Record<string, unknown>,
    target?: Record<string, unknown>,
    notifyOnError?: boolean,
    returnResponse?: boolean,
  ): Promise<unknown>;
}
