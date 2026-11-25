"""The WebSocket commands the Parcels page uses."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later
import probatio as p

from .const import DOMAIN, SIGNAL_AI_UPDATED, SIGNAL_DATA_UPDATED
from .engine import ParcelsEngine, get_engine, validation_error
from .services import TEXT, TEXT_LIST, check_return, clearable
from .views import details, snapshot, viewer_for

# Changes that come in bursts are sent to the page once.
UPDATE_DELAY = 0.5

OVERRIDES_SCHEMA = p.Schema(
    {
        p.Optional("kind"): TEXT,
        p.Optional("merchant"): clearable(TEXT),
        p.Optional("carrier"): clearable(TEXT),
        p.Optional("tracking_numbers"): TEXT_LIST,
        p.Optional("order_numbers"): TEXT_LIST,
        p.Optional("eta_start"): clearable(cv.date),
        p.Optional("eta_end"): clearable(cv.date),
        p.Optional("window_start"): clearable(cv.time),
        p.Optional("window_end"): clearable(cv.time),
        p.Optional("pickup_point"): clearable(TEXT),
        p.Optional("pickup_code"): clearable(TEXT),
        p.Optional("items"): TEXT_LIST,
        p.Optional("amazon_shipment_id"): clearable(TEXT),
        p.Optional("reference"): clearable(TEXT),
    }
)


type Handler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]], None
]


def _send_validation_error(
    connection: websocket_api.ActiveConnection,
    msg_id: int,
    err: HomeAssistantError,
) -> None:
    connection.send_error(
        msg_id,
        websocket_api.ERR_HOME_ASSISTANT_ERROR,
        str(err),
        translation_key=err.translation_key,
        translation_domain=err.translation_domain,
        translation_placeholders=err.translation_placeholders,
    )


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
            _send_validation_error(connection, msg["id"], err)

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
        ws_origin_remove,
        ws_filtered_clear,
        ws_filtered_clear_all,
        ws_return_remove,
        ws_suggestion_accept,
        ws_suggestion_dismiss,
        ws_parcel_check_again,
        ws_mail_retry_failed,
        ws_mail_dismiss_failed,
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
    connection.send_result(
        msg["id"], _engine(hass).review_trust_sender(msg["review_id"])
    )


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
@websocket_api.async_response
async def ws_review_restore(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Restore a filtered e-mail.

    One that was filtered out moves to the review list; one the user removed
    from Parcels is read again, and its review ID is None. "parcel_ids" are
    the parcels the user may see that hold the e-mail now.
    """
    engine = _engine(hass)
    entry = engine.data.filtered.get(msg["filtered_id"])
    message = entry.message if entry else None
    try:
        review_id = await engine.async_filtered_restore(msg["filtered_id"])
    except HomeAssistantError as err:
        _send_validation_error(connection, msg["id"], err)
        return
    viewer = viewer_for(hass, connection.user)
    parcel_ids = sorted(
        parcel.id
        for parcel in engine.data.parcels.values()
        if message is not None
        and viewer.can_see(parcel)
        and any(origin.message == message for origin in parcel.origins.values())
    )
    connection.send_result(
        msg["id"], {"review_id": review_id, "parcel_ids": parcel_ids}
    )


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/origin/remove",
        p.Required("parcel_id"): cv.string,
        p.Required("origin_id"): cv.string,
    }
)
@websocket_api.require_admin
@_expected_errors
@callback
def ws_origin_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove an e-mail from Parcels, with everything it added.

    The answer's parcel_id is None when the parcel went with the e-mail.
    """
    engine = _engine(hass)
    parcel = engine.parcel(msg["parcel_id"])
    if not viewer_for(hass, connection.user).can_see(parcel):
        raise validation_error("not_allowed")
    filtered_id = engine.remove_email(parcel.id, msg["origin_id"])
    kept = parcel.id if parcel.id in engine.data.parcels else None
    connection.send_result(msg["id"], {"filtered_id": filtered_id, "parcel_id": kept})


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/filtered/clear",
        p.Required("filtered_id"): cv.string,
    }
)
@websocket_api.require_admin
@_expected_errors
@callback
def ws_filtered_clear(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Drop an e-mail that was filtered out; it isn't read again."""
    _engine(hass).filtered_clear(msg["filtered_id"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({p.Required("type"): f"{DOMAIN}/filtered/clear_all"})
@websocket_api.require_admin
@_expected_errors
@callback
def ws_filtered_clear_all(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Drop every e-mail that was filtered out; none of them is read again."""
    cleared = _engine(hass).filtered_clear_all()
    connection.send_result(msg["id"], {"cleared": cleared})


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/return/remove",
        p.Required("return_id"): cv.string,
    }
)
@websocket_api.require_admin
@_expected_errors
@callback
def ws_return_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove a customer return; its e-mails aren't read again."""
    engine = _engine(hass)
    check_return(engine, viewer_for(hass, connection.user), msg["return_id"])
    engine.remove_return(msg["return_id"])
    connection.send_result(msg["id"])


def _check_suggestion(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    engine: ParcelsEngine,
    suggestion_id: str,
    parcel_id: str | None,
) -> None:
    """Refuse a suggestion with parcels the user may not see."""
    viewer = viewer_for(hass, connection.user)
    for item in engine.suggestions:
        if item.id != suggestion_id:
            continue
        for found in (item.parcel_id, parcel_id or item.parcel_id):
            if not viewer.can_see(engine.parcel(found)):
                raise validation_error("not_allowed")
        if parcel_id is None and not all(
            viewer.can_see(engine.parcel(candidate))
            for candidate in item.candidates
            if candidate in engine.data.parcels
        ):
            raise validation_error("not_allowed")
        return
    raise validation_error("unknown_suggestion")


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/suggestion/accept",
        p.Required("suggestion_id"): cv.string,
        p.Required("parcel_id"): cv.string,
    }
)
@websocket_api.require_admin
@_expected_errors
@callback
def ws_suggestion_accept(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Merge a suggested parcel into the parcel it was suggested for."""
    engine = _engine(hass)
    _check_suggestion(hass, connection, engine, msg["suggestion_id"], msg["parcel_id"])
    parcel_id = engine.accept_suggestion(msg["suggestion_id"], msg["parcel_id"])
    connection.send_result(msg["id"], {"parcel_id": parcel_id})


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/suggestion/dismiss",
        p.Required("suggestion_id"): cv.string,
        p.Optional("parcel_id"): cv.string,
    }
)
@websocket_api.require_admin
@_expected_errors
@callback
def ws_suggestion_dismiss(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Keep a suggested parcel, or all of a suggestion's parcels, apart."""
    engine = _engine(hass)
    parcel_id = msg.get("parcel_id")
    _check_suggestion(hass, connection, engine, msg["suggestion_id"], parcel_id)
    engine.dismiss_suggestion(msg["suggestion_id"], parcel_id)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        p.Required("type"): f"{DOMAIN}/parcel/check_again",
        p.Required("parcel_id"): cv.string,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_parcel_check_again(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Read a parcel's e-mails again, and ask the local AI what's missing."""
    try:
        engine = _engine(hass)
        parcel = engine.parcel(msg["parcel_id"])
        if not viewer_for(hass, connection.user).can_see(parcel):
            raise validation_error("not_allowed")
        result = await engine.async_check_again(parcel.id)
    except ServiceValidationError as err:
        _send_validation_error(connection, msg["id"], err)
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({p.Required("type"): f"{DOMAIN}/mail/retry_failed"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_mail_retry_failed(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Try once more to read the e-mails Parcels gave up on.

    The answer counts those read, those that failed again and those deleted
    from the mailbox meanwhile.
    """
    try:
        engine = _engine(hass)
    except ServiceValidationError as err:
        _send_validation_error(connection, msg["id"], err)
        return
    connection.send_result(msg["id"], await engine.async_retry_gave_up())


@websocket_api.websocket_command({p.Required("type"): f"{DOMAIN}/mail/dismiss_failed"})
@websocket_api.require_admin
@_expected_errors
@callback
def ws_mail_dismiss_failed(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Leave the e-mails Parcels gave up on unread, and stop listing them."""
    dismissed = _engine(hass).dismiss_gave_up()
    connection.send_result(msg["id"], {"dismissed": dismissed})
