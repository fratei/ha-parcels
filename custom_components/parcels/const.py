"""Constants for the Parcels integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import Final

DOMAIN: Final = "parcels"
NAME: Final = "Parcels"
VERSION: Final = "0.1.0"

STORAGE_KEY: Final = "parcels"
STORAGE_VERSION: Final = 1
STORAGE_MINOR_VERSION: Final = 1

# Config entry data
CONF_ENTRY_TYPE: Final = "entry_type"
ENTRY_TYPE_HUB: Final = "hub"
ENTRY_TYPE_MAILBOX: Final = "mailbox"
HUB_UNIQUE_ID: Final = "hub"

CONF_PROVIDER: Final = "provider"
PROVIDER_MICROSOFT: Final = "microsoft"
PROVIDER_GOOGLE: Final = "google"
CONF_ADDRESS: Final = "address"

# Mailbox options
CONF_OWNER: Final = "owner"
CONF_FOLDERS: Final = "folders"
CONF_LOOKBACK_DAYS: Final = "lookback_days"
CONF_INTERVAL_MINUTES: Final = "interval_minutes"
DEFAULT_LOOKBACK_DAYS: Final = 30
DEFAULT_INTERVAL_MINUTES: Final = 5
MICROSOFT_FOLDERS: Final = ("inbox", "junkemail")
DEFAULT_MICROSOFT_FOLDERS: Final = ["inbox", "junkemail"]

# Hub options. Notified devices are the companion apps of the chosen people,
# found through each person's HA user, minus any excluded device.
CONF_NOTIFY_PERSONS: Final = "notify_persons"
CONF_EXCLUDED_DEVICES: Final = "excluded_devices"
CONF_START_TIME: Final = "start_time"
CONF_CUTOFF_TIME: Final = "cutoff_time"
CONF_COLLAPSE_THRESHOLD: Final = "collapse_threshold"
CONF_ITEM_NAMES: Final = "item_names_on_lock_screen"
CONF_SEVENTEENTRACK: Final = "seventeentrack"
CONF_TEST_MODE: Final = "test_mode"
CONF_TEST_DEVICE: Final = "test_device"
CONF_ARCHIVE_DAYS: Final = "archive_days"
CONF_PURGE_DAYS: Final = "purge_days"
CONF_AI_TASK: Final = "ai_task_entity"
CONF_AI_MODE: Final = "ai_mode"
CONF_DASHBOARD_PATH: Final = "dashboard_path"

DEFAULT_START_TIME: Final = "08:00:00"
DEFAULT_CUTOFF_TIME: Final = "22:00:00"
DEFAULT_COLLAPSE_THRESHOLD: Final = 3
DEFAULT_ARCHIVE_DAYS: Final = 14
DEFAULT_PURGE_DAYS: Final = 90
DEFAULT_DASHBOARD_PATH: Final = "/dashboard-parcels/week"
DEFAULT_SEVENTEENTRACK: Final = True
DEFAULT_ITEM_NAMES: Final = False
MESSAGE_HASH_RETENTION: Final = timedelta(days=120)
FILTERED_RETENTION: Final = timedelta(days=14)
REVIEW_RETENTION: Final = timedelta(days=30)
# Parcels still open with no news for this long are archived as stale.
STALE_ARCHIVE: Final = timedelta(days=30)


class AIMode(StrEnum):
    """How results of the local AI are used."""

    OFF = "off"
    SUGGEST = "suggest"
    AUTO = "auto"


DEFAULT_AI_MODE: Final = AIMode.SUGGEST

# AI limits
AI_TIMEOUT: Final = timedelta(minutes=5)
AI_RETRY_DELAY: Final = timedelta(minutes=30)
AI_DAILY_LIMIT: Final = 50
AI_FIRST_SYNC_DAYS: Final = 14
AI_SHADOW_DAILY_LIMIT: Final = 5
AI_MAX_INPUT_CHARS: Final = 6000

# Confidence at or above which parser results are applied directly.
CONFIDENCE_APPLY: Final = 0.7


class ParcelStatus(StrEnum):
    """Canonical parcel statuses."""

    ORDERED = "ordered"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    ATTEMPTED = "attempted"
    EXCEPTION = "exception"
    READY_FOR_PICKUP = "ready_for_pickup"
    RETURNED = "returned"
    CANCELLED = "cancelled"


S = ParcelStatus

# Main progression; used for progress bars and for ordering.
STATUS_RANK: Final[dict[ParcelStatus, int]] = {
    S.ORDERED: 0,
    S.SHIPPED: 1,
    S.IN_TRANSIT: 2,
    S.EXCEPTION: 2,
    S.ATTEMPTED: 3,
    S.OUT_FOR_DELIVERY: 3,
    S.READY_FOR_PICKUP: 3,
    S.DELIVERED: 4,
    S.RETURNED: 4,
    S.CANCELLED: 4,
}

ALLOWED_TRANSITIONS: Final[dict[ParcelStatus, frozenset[ParcelStatus]]] = {
    S.ORDERED: frozenset(set(S) - {S.ORDERED}),
    S.SHIPPED: frozenset(
        {
            S.IN_TRANSIT,
            S.OUT_FOR_DELIVERY,
            S.DELIVERED,
            S.ATTEMPTED,
            S.EXCEPTION,
            S.READY_FOR_PICKUP,
            S.RETURNED,
            S.CANCELLED,
        }
    ),
    S.IN_TRANSIT: frozenset(
        {
            S.OUT_FOR_DELIVERY,
            S.DELIVERED,
            S.ATTEMPTED,
            S.EXCEPTION,
            S.READY_FOR_PICKUP,
            S.RETURNED,
            S.CANCELLED,
        }
    ),
    S.OUT_FOR_DELIVERY: frozenset(
        {S.DELIVERED, S.ATTEMPTED, S.EXCEPTION, S.READY_FOR_PICKUP, S.RETURNED}
    ),
    S.ATTEMPTED: frozenset(
        {
            S.OUT_FOR_DELIVERY,
            S.IN_TRANSIT,
            S.DELIVERED,
            S.EXCEPTION,
            S.READY_FOR_PICKUP,
            S.RETURNED,
        }
    ),
    S.EXCEPTION: frozenset(
        {
            S.IN_TRANSIT,
            S.OUT_FOR_DELIVERY,
            S.DELIVERED,
            S.ATTEMPTED,
            S.READY_FOR_PICKUP,
            S.RETURNED,
            S.CANCELLED,
        }
    ),
    S.READY_FOR_PICKUP: frozenset({S.DELIVERED, S.RETURNED, S.EXCEPTION}),
    S.DELIVERED: frozenset({S.RETURNED}),
    S.RETURNED: frozenset(),
    S.CANCELLED: frozenset(),
}

TERMINAL_STATUSES: Final = frozenset({S.DELIVERED, S.RETURNED, S.CANCELLED})
ACTIVE_STATUSES: Final = frozenset(set(S) - TERMINAL_STATUSES)


class MailKind(StrEnum):
    """What an e-mail is about, as classified by a parser or the AI."""

    ORDER = "order"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    ATTEMPTED = "attempted"
    READY_FOR_PICKUP = "ready_for_pickup"
    DELAYED = "delayed"
    CUSTOMS = "customs"
    RETURN = "return"
    CANCELLED = "cancelled"
    NOT_PARCEL = "not_parcel"
    UNKNOWN = "unknown"


# Status that a mail kind moves a parcel to. Delayed keeps the parcel in
# transit with a new ETA; customs holds are exceptions.
KIND_TO_STATUS: Final[dict[MailKind, ParcelStatus]] = {
    MailKind.ORDER: S.ORDERED,
    MailKind.SHIPPED: S.SHIPPED,
    MailKind.IN_TRANSIT: S.IN_TRANSIT,
    MailKind.OUT_FOR_DELIVERY: S.OUT_FOR_DELIVERY,
    MailKind.DELIVERED: S.DELIVERED,
    MailKind.ATTEMPTED: S.ATTEMPTED,
    MailKind.READY_FOR_PICKUP: S.READY_FOR_PICKUP,
    MailKind.DELAYED: S.IN_TRANSIT,
    MailKind.CUSTOMS: S.EXCEPTION,
    MailKind.RETURN: S.RETURNED,
    MailKind.CANCELLED: S.CANCELLED,
}

# Canonical carrier IDs and display names. The AI must answer with one of
# these IDs; anything else is rejected.
CARRIER_NAMES: Final[dict[str, str]] = {
    "amazon": "Amazon Logistics",
    "asendia": "Asendia",
    "bpost": "bpost",
    "brt": "BRT",
    "cainiao": "Cainiao",
    "chronopost": "Chronopost",
    "colissimo": "Colissimo",
    "correos": "Correos",
    "correos_express": "Correos Express",
    "ctt": "CTT",
    "ctt_expresso": "CTT Expresso",
    "deutsche_post": "Deutsche Post",
    "dhl": "DHL",
    "dpd": "DPD",
    "evri": "Evri",
    "fedex": "FedEx",
    "gls": "GLS",
    "hermes": "Hermes",
    "inpost": "InPost",
    "la_poste": "La Poste",
    "mondial_relay": "Mondial Relay",
    "mrw": "MRW",
    "nacex": "Nacex",
    "paack": "Paack",
    "postnl": "PostNL",
    "poste_italiane": "Poste Italiane",
    "royal_mail": "Royal Mail",
    "sda": "SDA",
    "seur": "SEUR",
    "tnt": "TNT",
    "ups": "UPS",
    "usps": "USPS",
    "vinted_go": "Vinted Go",
    "yunexpress": "YunExpress",
    "other": "Other",
}

# Events
EVENT_PARCEL_ADDED: Final = "parcels_parcel_added"
EVENT_STATUS_CHANGED: Final = "parcels_status_changed"
EVENT_DELIVERED: Final = "parcels_delivered"

# Dispatcher signals
SIGNAL_DATA_UPDATED: Final = "parcels_data_updated"
SIGNAL_MAILBOX_UPDATED: Final = "parcels_mailbox_updated_{}"
SIGNAL_AI_UPDATED: Final = "parcels_ai_updated"

# Persistent notification
PERSISTENT_NOTIFICATION_ID: Final = "parcels_today"

# Frontend
FRONTEND_URL_PATH: Final = "/parcels_static"
FRONTEND_SCRIPT: Final = "parcels-cards.js"

# Repairs issue IDs
ISSUE_AI_UNAVAILABLE: Final = "ai_unavailable"
ISSUE_AI_REFUSED: Final = "ai_task_refused"
ISSUE_PARSER_OUTDATED: Final = "parser_outdated_{}"

# Why an e-mail is under "Needs review". Sender checks add their own reasons
# (not_aligned, no_auth_header, untrusted_authserv).
REASON_UNKNOWN_SENDER: Final = "unknown_sender"
REASON_LOW_CONFIDENCE: Final = "low_confidence"
REASON_UNKNOWN_FORMAT: Final = "unknown_format"
REASON_RESTORED: Final = "restored"
REASON_AI_SUGGESTION: Final = "ai_suggestion"
REASON_AI_UNAVAILABLE: Final = "ai_unavailable"
REASON_AI_REJECTED: Final = "ai_rejected"
