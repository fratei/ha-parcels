"""Services of Parcels."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
import probatio as p

from .const import CARRIER_NAMES, DOMAIN
from .customer_returns import linked_parcels, order_index
from .dedup import number_key_text, parcel_numbers
from .engine import ParcelsEngine, get_engine, validation_error
from .models import Parcel
from .views import Viewer, async_viewer

ATTR_CARRIER = "carrier"
ATTR_DEVICE_ID = "device_id"
ATTR_DOMAIN = "domain"
ATTR_FILTERED_ID = "filtered_id"
ATTR_MERCHANT = "merchant"
ATTR_ORIGINS = "origins"
ATTR_PARCEL_ID = "parcel_id"
ATTR_PARCEL_IDS = "parcel_ids"
ATTR_PRIVATE = "private"
ATTR_RETURN_ID = "return_id"
ATTR_REVIEW_ID = "review_id"
ATTR_TRACKING_NUMBER = "tracking_number"
ATTR_USE_AI = "use_ai"

SERVICE_ADD = "add"
SERVICE_ARCHIVE = "archive"
SERVICE_IGNORE_SENDER = "ignore_sender"
SERVICE_MARK_DELIVERED = "mark_delivered"
SERVICE_MARK_RETURN_PICKED_UP = "mark_return_picked_up"
SERVICE_MERGE = "merge"
SERVICE_REFRESH = "refresh"
SERVICE_REPROCESS = "reprocess"
SERVICE_SPLIT = "split"
SERVICE_TEST_LIVE_ACTIVITY = "test_live_activity"
SERVICE_TRUST_SENDER = "trust_sender"
SERVICE_UNDO_DELIVERY = "undo_delivery"
SERVICE_UNDO_MERGE = "undo_merge"
SERVICE_UNDO_RETURN_PICKED_UP = "undo_return_picked_up"
SERVICE_UPDATE = "update"


def clearable(validator: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Accept a value, or None or an empty text to clear the field."""

    def validate(value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return validator(value)

    return validate


DOMAIN_PATTERN = r"^(?=.{3,253}$)[a-z0-9-]+(\.[a-z0-9-]+)+$"
# The limits of every text and list a user may send, here and on the page.
MAX_TEXT = 500
MAX_LIST = 50
TEXT = p.All(cv.string, p.Length(max=MAX_TEXT))
TEXT_LIST = p.All(cv.ensure_list, [TEXT], p.Length(max=MAX_LIST))
_CARRIER = p.All(cv.string, p.Lower, p.In(list(CARRIER_NAMES)))
_IDS = p.All(cv.ensure_list, [cv.string])

ADD_SCHEMA = p.Schema(
    {
        p.Required(ATTR_TRACKING_NUMBER): TEXT,
        p.Optional(ATTR_CARRIER): clearable(_CARRIER),
        p.Optional(ATTR_MERCHANT): clearable(TEXT),
        p.Optional(ATTR_PRIVATE, default=False): cv.boolean,
    }
)
UPDATE_SCHEMA = p.Schema(
    {
        p.Required(ATTR_PARCEL_ID): cv.string,
        p.Optional(ATTR_MERCHANT): clearable(TEXT),
        p.Optional(ATTR_CARRIER): clearable(_CARRIER),
        p.Optional(ATTR_TRACKING_NUMBER): clearable(TEXT),
        p.Optional("pickup_point"): clearable(TEXT),
        p.Optional("pickup_code"): clearable(TEXT),
        p.Optional("eta_start"): clearable(cv.date),
        p.Optional("eta_end"): clearable(cv.date),
        p.Optional("window_start"): clearable(cv.time),
        p.Optional("window_end"): clearable(cv.time),
        p.Optional(ATTR_PRIVATE): cv.boolean,
        p.Optional("confirm"): cv.boolean,
        p.Optional("confirm_merge"): cv.boolean,
        p.Optional("confirm_delivery"): cv.boolean,
    }
)
PARCEL_SCHEMA = p.Schema({p.Required(ATTR_PARCEL_ID): cv.string})
RETURN_SCHEMA = p.Schema({p.Required(ATTR_RETURN_ID): cv.string})
MERGE_SCHEMA = p.Schema({p.Required(ATTR_PARCEL_IDS): p.All(_IDS, p.Length(min=2))})
SPLIT_SCHEMA = p.Schema(
    {
        p.Required(ATTR_PARCEL_ID): cv.string,
        p.Required(ATTR_ORIGINS): p.All(_IDS, p.Length(min=1)),
    }
)
REFRESH_SCHEMA = p.Schema({})
REPROCESS_SCHEMA = p.Schema(
    p.All(
        {
            p.Optional(ATTR_PARCEL_ID): cv.string,
            p.Optional(ATTR_REVIEW_ID): cv.string,
            p.Optional(ATTR_FILTERED_ID): cv.string,
            p.Optional(ATTR_USE_AI, default=False): cv.boolean,
        },
        p.ExactlyOne(ATTR_PARCEL_ID, ATTR_REVIEW_ID, ATTR_FILTERED_ID),
    )
)
SENDER_SCHEMA = p.Schema(
    p.All(
        {
            p.Optional(ATTR_DOMAIN): p.All(
                cv.string, p.Strip, p.Lower, p.Match(DOMAIN_PATTERN)
            ),
            p.Optional(ATTR_REVIEW_ID): cv.string,
        },
        p.ExactlyOne(ATTR_DOMAIN, ATTR_REVIEW_ID),
    )
)
TEST_LIVE_ACTIVITY_SCHEMA = p.Schema({p.Optional(ATTR_DEVICE_ID): cv.string})


def _engine(hass: HomeAssistant) -> ParcelsEngine:
    engine = get_engine(hass)
    if engine is None or not engine.started:
        raise validation_error("hub_not_loaded")
    return engine


async def _caller(call: ServiceCall) -> Viewer | None:
    """Return the viewer of the calling user; None for automations and scripts."""
    if call.context.user_id is None:
        return None
    return await async_viewer(call.hass, call.context.user_id)


def visible_parcel(
    engine: ParcelsEngine, viewer: Viewer | None, parcel_id: str
) -> Parcel:
    """Return a parcel the caller may change, or raise."""
    parcel = engine.parcel(parcel_id)
    if viewer is not None and not viewer.can_see(parcel):
        raise validation_error("not_allowed")
    return parcel


def _check_number(engine: ParcelsEngine, viewer: Viewer | None, number: str) -> None:
    """Refuse a number that would join a private parcel the caller can't see."""
    if viewer is None:
        return
    key = number_key_text(number)
    for parcel in engine.data.parcels.values():
        if (
            parcel.private
            and not viewer.can_see(parcel)
            and any(entry.number == key for entry in parcel_numbers(parcel))
        ):
            raise validation_error("not_allowed")


async def _async_add(call: ServiceCall) -> ServiceResponse:
    engine = _engine(call.hass)
    viewer = await _caller(call)
    number = call.data[ATTR_TRACKING_NUMBER]
    _check_number(engine, viewer, number)
    parcel_id = engine.add_parcel(
        number,
        carrier=call.data.get(ATTR_CARRIER),
        merchant=call.data.get(ATTR_MERCHANT),
        private=call.data[ATTR_PRIVATE],
        owners=sorted(viewer.persons) if viewer is not None else (),
    )
    return {ATTR_PARCEL_ID: parcel_id}


async def _async_update(call: ServiceCall) -> None:
    engine = _engine(call.hass)
    viewer = await _caller(call)
    parcel_id = call.data[ATTR_PARCEL_ID]
    visible_parcel(engine, viewer, parcel_id)
    changes = {key: value for key, value in call.data.items() if key != ATTR_PARCEL_ID}
    if number := changes.get(ATTR_TRACKING_NUMBER):
        _check_number(engine, viewer, number)
    engine.update(parcel_id, changes)


def _parcel_service(
    action: Callable[[ParcelsEngine, str], Any],
) -> Callable[[ServiceCall], Any]:
    async def handle(call: ServiceCall) -> None:
        engine = _engine(call.hass)
        viewer = await _caller(call)
        parcel_id = call.data[ATTR_PARCEL_ID]
        visible_parcel(engine, viewer, parcel_id)
        action(engine, parcel_id)

    return handle


def _return_picked_up(picked_up: bool) -> Callable[[ServiceCall], Any]:
    """Mark a return picked up, or undo that, for anyone who may see it."""

    async def handle(call: ServiceCall) -> None:
        engine = _engine(call.hass)
        viewer = await _caller(call)
        return_id = call.data[ATTR_RETURN_ID]
        entry = engine.data.returns.get(return_id)
        if entry is None:
            raise validation_error("unknown_return")
        linked = linked_parcels(entry, order_index(engine.data))
        if viewer is not None and not viewer.can_see_return(entry, linked):
            raise validation_error("not_allowed")
        engine.mark_return_picked_up(return_id, picked_up)

    return handle


async def _async_merge(call: ServiceCall) -> ServiceResponse:
    engine = _engine(call.hass)
    viewer = await _caller(call)
    parcel_ids = call.data[ATTR_PARCEL_IDS]
    for parcel_id in parcel_ids:
        visible_parcel(engine, viewer, parcel_id)
    return {ATTR_PARCEL_ID: engine.merge(parcel_ids)}


async def _async_split(call: ServiceCall) -> ServiceResponse:
    engine = _engine(call.hass)
    viewer = await _caller(call)
    parcel_id = call.data[ATTR_PARCEL_ID]
    visible_parcel(engine, viewer, parcel_id)
    return {ATTR_PARCEL_ID: engine.split(parcel_id, call.data[ATTR_ORIGINS])}


async def _async_refresh(call: ServiceCall) -> None:
    await _engine(call.hass).async_refresh()


async def _async_reprocess(call: ServiceCall) -> None:
    engine = _engine(call.hass)
    hashes = engine.message_hashes(
        review_id=call.data.get(ATTR_REVIEW_ID),
        filtered_id=call.data.get(ATTR_FILTERED_ID),
        parcel_id=call.data.get(ATTR_PARCEL_ID),
    )
    if not hashes:
        raise validation_error("no_messages")
    for key in hashes:
        await engine.async_reprocess(key, use_ai=call.data[ATTR_USE_AI])


def _sender_service(
    by_domain: Callable[[ParcelsEngine, str], ServiceResponse],
    by_review: Callable[[ParcelsEngine, str], ServiceResponse],
) -> Callable[[ServiceCall], Any]:
    async def handle(call: ServiceCall) -> ServiceResponse:
        engine = _engine(call.hass)
        if review_id := call.data.get(ATTR_REVIEW_ID):
            return by_review(engine, review_id)
        return by_domain(engine, call.data[ATTR_DOMAIN])

    return handle


async def _async_test_live_activity(call: ServiceCall) -> None:
    engine = _engine(call.hass)
    if engine.notifier is None:
        raise validation_error("hub_not_loaded")
    await engine.notifier.async_test_live_activity(call.data.get(ATTR_DEVICE_ID))


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services of Parcels."""
    register = hass.services.async_register
    register(DOMAIN, SERVICE_ADD, _async_add, ADD_SCHEMA, SupportsResponse.OPTIONAL)
    register(DOMAIN, SERVICE_UPDATE, _async_update, UPDATE_SCHEMA)
    register(
        DOMAIN,
        SERVICE_MARK_DELIVERED,
        _parcel_service(lambda engine, pid: engine.mark_delivered(pid)),
        PARCEL_SCHEMA,
    )
    register(
        DOMAIN,
        SERVICE_ARCHIVE,
        _parcel_service(lambda engine, pid: engine.archive(pid)),
        PARCEL_SCHEMA,
    )
    register(
        DOMAIN,
        SERVICE_UNDO_MERGE,
        _parcel_service(lambda engine, pid: engine.undo_merge(pid)),
        PARCEL_SCHEMA,
    )
    register(
        DOMAIN,
        SERVICE_UNDO_DELIVERY,
        _parcel_service(lambda engine, pid: engine.undo_delivery(pid)),
        PARCEL_SCHEMA,
    )
    register(
        DOMAIN, SERVICE_MARK_RETURN_PICKED_UP, _return_picked_up(True), RETURN_SCHEMA
    )
    register(
        DOMAIN, SERVICE_UNDO_RETURN_PICKED_UP, _return_picked_up(False), RETURN_SCHEMA
    )
    register(
        DOMAIN, SERVICE_MERGE, _async_merge, MERGE_SCHEMA, SupportsResponse.OPTIONAL
    )
    register(
        DOMAIN, SERVICE_SPLIT, _async_split, SPLIT_SCHEMA, SupportsResponse.OPTIONAL
    )
    register(DOMAIN, SERVICE_REFRESH, _async_refresh, REFRESH_SCHEMA)
    async_register_admin_service(
        hass, DOMAIN, SERVICE_REPROCESS, _async_reprocess, REPROCESS_SCHEMA
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_TRUST_SENDER,
        _sender_service(
            lambda engine, domain: {ATTR_DOMAIN: engine.trust_domain(domain)},
            lambda engine, review_id: engine.review_trust_sender(review_id),
        ),
        SENDER_SCHEMA,
        SupportsResponse.OPTIONAL,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_IGNORE_SENDER,
        _sender_service(
            lambda engine, domain: {ATTR_DOMAIN: engine.ignore_domain(domain)},
            lambda engine, review_id: {
                ATTR_DOMAIN: engine.review_ignore_sender(review_id)
            },
        ),
        SENDER_SCHEMA,
        SupportsResponse.OPTIONAL,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_TEST_LIVE_ACTIVITY,
        _async_test_live_activity,
        TEST_LIVE_ACTIVITY_SCHEMA,
    )
