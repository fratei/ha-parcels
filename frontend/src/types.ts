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

export type ParcelSource = "parser" | "ai" | "manual" | "seventeentrack";

/** A timeline entry's source; "inferred" marks a delivery worked out from another parcel's. */
export type TimelineSource = ParcelSource | "inferred";

export type AiMode = "off" | "suggest" | "auto";

export interface AutoMerged {
  origin: string;
  at: string;
  reason: string;
}

export interface Parcel {
  id: string;
  merchant: string | null;
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
  delivered_at: string | null;
  /** Delivered only by inference: another parcel from the shop was delivered then. */
  inferred: boolean;
  pickup_point: string | null;
  pickup_code: string | null;
  order_numbers: string[];
  items: string[];
  private: boolean;
  owners: string[];
  source: ParcelSource;
  ai: boolean;
  auto_merged: AutoMerged | null;
  provisional: boolean;
  archived: boolean;
  origins: string[];
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
  source: "parser" | "ai";
  suggestion: Suggestion | null;
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
  review: ReviewItem[];
  merge_suggestions: MergeSuggestion[];
  filtered: FilteredItem[];
  settings: Settings;
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
