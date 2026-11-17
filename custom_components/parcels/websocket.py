"""The WebSocket commands the Parcels page uses."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later
import probatio as p

from .const import DOMAIN, SIGNAL_AI_UPDATED, SIGNAL_DATA_UPDATED
from .engine import ParcelsEngine, get_engine, validation_error
from .services import clearable
from .views import details, snapshot, viewer_for

# Changes that come in bursts are sent to the page once.
UPDATE_DELAY = 0.5
MAX_LIST = 50
_TEXT = p.All(cv.string, p.Length(max=500))
_LIST = p.All(cv.ensure_list, [_TEXT], p.Length(max=MAX_LIST))

OVERRIDES_SCHEMA = p.Schema(
    {
        p.Optional("kind"): _TEXT,
        p.Optional("merchant"): clearable(_TEXT),
        p.Optional("carrier"): clearable(_TEXT),
        p.Optional("tracking_numbers"): _LIST,
        p.Optional("order_numbers"): _LIST,
        p.Optional("eta_start"): clearable(cv.date),
        p.Optional("eta_end"): clearable(cv.date),
        p.Optional("window_start"): clearable(cv.time),
        p.Optional("window_end"): clearable(cv.time),
        p.Optional("pickup_point"): clearable(_TEXT),
        p.Optional("pickup_code"): clearable(_TEXT),
        p.Optional("items"): _LIST,
        p.Optional("amazon_shipment_id"): clearable(_TEXT),
    }
)


type Handler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]], None
]


def _expected_errors(func: Handler) -> Handler:
    """Answer a bad request with its error, without logging it as a failure."""

    @wraps(func)
    def handle(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        try:
            func(hass, connection, msg)
        except ServiceValidationError as err:
            connection.send_error(
                msg["id"],
                websocket_api.ERR_HOME_ASSISTANT_ERROR,
                str(err),
                translation_key=err.translation_key,
                translation_domain=err.translation_domain,
                translation_placeholders=err.translation_placeholders,
            )

    return handle


def _engine(hass: HomeAssistant) -> ParcelsEngine:
    engine = get_engine(hass)
    if engine is None or not engine.started:
        raise validation_error("hub_not_loaded")
    return engine


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    """Register the WebSocket commands."""
    for command in (
        ws_list,
        ws_subscribe,
        ws_get,
        ws_review_accept,
        ws_review_dismiss,
        ws_review_trust_sender,
        ws_review_ignore_sender,
        ws_review_restore,
    ):
        websocket_api.async_register_command(hass, command)


@websocket_api.websocket_command({p.Required("type"): f"{DOMAIN}/list"})
@_expected_errors
@callback
def ws_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the parcels, the review list and the settings."""
    engine = _engine(hass)
    connection.send_result(
        msg["id"], snapshot(engine, viewer_for(hass, connection.user))
    )


class _Subscription:
    """Sends the page a new snapshot whenever the parcels change."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg_id: int,
    ) -> None:
        self.hass = hass
        self.connection = connection
        self.msg_id = msg_id
        self._timer: CALLBACK_TYPE | None = None
        self._unsubs = [
            async_dispatcher_connect(hass, SIGNAL_DATA_UPDATED, self._schedule),
            async_dispatcher_connect(hass, SIGNAL_AI_UPDATED, self._schedule),
        ]

    @callback
    def _schedule(self, *_: Any) -> None:
        if self._timer is None:
            self._timer = async_call_later(self.hass, UPDATE_DELAY, self._send_later)

    @callback
    def _send_later(self, _now: Any) -> None:
        self._timer = None
        self.send()

    @callback
    def send(self) -> None:
        """Send the snapshot, computed for the user as they are now."""
        engine = get_engine(self.hass)
        if engine is None or not engine.started:
            return
        viewer = viewer_for(self.hass, self.connection.user)
        self.connection.send_event(self.msg_id, snapshot(engine, viewer))

    @callback
    def close(self) -> None:
        """Stop sending."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._timer is not None:
            self._timer()
            self._timer = None


@websocket_api.websocket_command({p.Required("type"): f"{DOMAIN}/subscribe"})
@_expected_errors
@callback
def ws_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send a snapshot now and after every change."""
    _engine(hass)
    subscription = _Subscription(hass, connection, msg["id"])
    connection.subscriptions[msg["id"]] = subscription.close
    connection.send_result(msg["id"])
    subscription.send()


@websocket_api.websocket_command(
    {p.Required("type"): f"{DOMAIN}/get", p.Required("parcel_id"): cv.string}
)
@_expected_errors
@callback
def ws_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return a parcel with its timeline, orders and origins."""
    engine = _engine(hass)
    viewer = viewer_for(hass, connection.user)
    parcel = engine.parcel(msg["parcel_id"])
    if not viewer.can_see(parcel):
        raise validation_error("not_allowed")
    connection.send_result(msg["id"], details(engine, parcel, viewer))


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/review/accept",
        p.Required("review_id"): cv.string,
        p.Optional("overrides"): p.Maybe(OVERRIDES_SCHEMA),
    }
)
@websocket_api.require_admin
@_expected_errors
@callback
def ws_review_accept(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Add what an e-mail under review says, with the user's corrections."""
    parcel_ids = _engine(hass).review_accept(msg["review_id"], msg.get("overrides"))
    connection.send_result(msg["id"], {"parcel_ids": parcel_ids})


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/review/dismiss",
        p.Required("review_id"): cv.string,
    }
)
@websocket_api.require_admin
@_expected_errors
@callback
def ws_review_dismiss(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Drop an e-mail from the review list."""
    _engine(hass).review_dismiss(msg["review_id"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/review/trust_sender",
        p.Required("review_id"): cv.string,
    }
)
@websocket_api.require_admin
@_expected_errors
@callback
def ws_review_trust_sender(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Trust the sender of an e-mail under review."""
    domain = _engine(hass).review_trust_sender(msg["review_id"])
    connection.send_result(msg["id"], {"domain": domain})


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/review/ignore_sender",
        p.Required("review_id"): cv.string,
    }
)
@websocket_api.require_admin
@_expected_errors
@callback
def ws_review_ignore_sender(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Ignore the sender of an e-mail under review."""
    domain = _engine(hass).review_ignore_sender(msg["review_id"])
    connection.send_result(msg["id"], {"domain": domain})


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/review/restore",
        p.Required("filtered_id"): cv.string,
    }
)
@websocket_api.require_admin
@_expected_errors
@callback
def ws_review_restore(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Move an e-mail that was filtered out to the review list."""
    review_id = _engine(hass).filtered_restore(msg["filtered_id"])
    connection.send_result(msg["id"], {"review_id": review_id})
