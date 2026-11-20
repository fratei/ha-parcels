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
 * from another parcel's, "inferred_return" from a return of its order, "quiet"
 * after three weeks without news.
 */
export type TimelineSource = ParcelSource | "inferred" | "inferred_return" | "quiet";

/** Why a delivery was inferred; see `TimelineSource`. */
export type InferredReason = "shop" | "return" | "quiet";

export type AiMode = "off" | "suggest" | "auto";

export interface AutoMerged {
  origin: string;
  at: string;
  reason: string;
}

export interface Parcel {
  id: string;
  merchant: string | null;
  /** What the user calls the parcel in the Parcel app; null when restricted. */
  name: string | null;
  carrier: string | null;
  carrier_name: string | null;
  tracking_number: string | null;
  tracking_url: string | null;
  status: ParcelStatus;
  status_time: string | null;
  eta_start: string | null;
  eta_end: string | null;
  window_start: string | null;
  window_end: string | null;
  /** Where the expected date comes from; null without one or when restricted. */
  eta_source: ParcelSource | null;
  delivered_at: string | null;
  /** Delivered only by inference, until the user keeps or undoes it. */
  inferred: boolean;
  /**
   * Why: "shop" when another parcel from the shop was delivered around its
   * dates, "return" when its items are being sent back, "quiet" when it had no
   * news for three weeks; null when not inferred.
   */
  inferred_reason: InferredReason | null;
  pickup_point: string | null;
  /**
   * The PIN or pickup code. The list has it while the parcel is on its way;
   * the details (`parcels/get`) always do.
   */
  pickup_code: string | null;
  /** The parcel has a PIN or pickup code. */
  has_code: boolean;
  order_numbers: string[];
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
  subject: string;
  mailbox_owner: string | null;
  reason: string;
  authenticated: boolean;
  /** The sender is trusted, but this e-mail failed the sender checks. */
  trusted_sender: boolean;
  checks: SenderChecks | null;
  /** The local AI fills in details the parser missed, for a parcel the e-mail already updated. */
  fill: boolean;
  /** The checks a rejected AI answer failed, as codes without values. */
  errors: string[];
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

export interface FilteredItem {
  id: string;
  created: string;
  received: string | null;
  sender: string;
  sender_domain: string;
  subject: string;
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

/** Parcels that are probably one: `candidates` may belong to `parcel` (administrators only). */
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
}

export interface OrderInfo {
  id: string;
  merchant: string | null;
  number: string;
  placed_at: string | null;
  parcel_ids: string[];
}

export interface OriginInfo {
  id: string;
  label: string;
  source: ParcelSource;
  time: string | null;
}

/** Result of `parcels/get`. */
export interface ParcelDetails {
  parcel: Parcel;
  timeline: TimelineEntry[];
  orders: OrderInfo[];
  origins: OriginInfo[];
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
  ): Promise<unknown>;
}
