"""Tests for the Parcels services: input, errors, permissions and responses."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import date, time, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.models import User
from homeassistant.core import Context, HomeAssistant, ServiceResponse
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
    UnknownUser,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import probatio as p
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockUser,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.parcels.const import (
    DOMAIN,
    EVENT_DELIVERED,
    EVENT_PARCEL_ADDED,
    EVENT_STATUS_CHANGED,
    MailKind,
    ParcelStatus,
)
from custom_components.parcels.dedup import (
    REASON_SAME_MERCHANT_ETA,
    apply_contribution,
    manual_origin_id,
    merge_parcels,
)
from custom_components.parcels.engine import ParcelsEngine
from custom_components.parcels.models import (
    AutoMerge,
    Eta,
    MessageState,
    Parcel,
    PickupRule,
    ReturnEntry,
    ReturnOrigin,
    Source,
)
from custom_components.parcels.services import ADD_SCHEMA, UPDATE_SCHEMA
from custom_components.parcels.views import SYSTEM_VIEWER, parcel_json, viewer_for

from .common import (
    OTHER_OWNER,
    OWNER,
    FakeMailClient,
    add_hub,
    add_mailbox,
    async_setup_parcels,
    patch_mail_clients,
)
from .factories import contribution

NOW = "2026-11-17 10:00:00+00:00"
CTT_NUMBER = "RR482915732PT"
DHL_NUMBER = "JJD0001234567"
# Long enough to match across carriers, which flags the merge for review.
LOOSE_NUMBER = "PARCEL1234567"
# A Paack order ID and a Paack label barcode, both made up.
PAACK_ID = "Qm7Rt2Kp9_2"
PAACK_BARCODE = "534000077712340056"
SHOP = "loja-exemplo.example"
FILTERED_SENDER = "servicos-exemplo.example"
CTT_MAIL = "carriers/ctt_in_transit_pt.eml"
SHOP_MAIL = "common/small_shop_ctt.eml"
FILTERED_MAIL = "common/unknown_phone_only.eml"

type Mail = tuple[ParcelsEngine, FakeMailClient]


@pytest.fixture(autouse=True)
async def lisbon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the tests on 17 November 2026, in Lisbon."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone("Europe/Lisbon")


@pytest.fixture
async def sam(hass: HomeAssistant) -> User:
    """Return Sam, who is not an administrator."""
    return await hass.auth.async_create_user("Sam")


@pytest.fixture
async def persons(hass: HomeAssistant, hass_admin_user: MockUser, sam: User) -> None:
    """Link person.alex to the administrator and person.sam to Sam."""
    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {"id": "alex", "name": "Alex", "user_id": hass_admin_user.id},
                {"id": "sam", "name": "Sam", "user_id": sam.id},
            ]
        },
    )
    assert hass.states.get(OWNER).attributes["user_id"] == hass_admin_user.id
    assert hass.states.get(OTHER_OWNER).attributes["user_id"] == sam.id


@pytest.fixture
async def engine(hass: HomeAssistant, persons: None) -> ParcelsEngine:
    """Load the hub, without mailboxes."""
    add_hub(hass)
    return await async_setup_parcels(hass)


@pytest.fixture
async def mail(hass: HomeAssistant, persons: None) -> AsyncIterator[Mail]:
    """Load the hub and Alex's mailbox: a parcel, a review and a filtered e-mail."""
    client = FakeMailClient()
    for path in (CTT_MAIL, SHOP_MAIL, FILTERED_MAIL):
        client.add(path)
    add_hub(hass)
    add_mailbox(hass)
    with patch_mail_clients(client):
        engine = await async_setup_parcels(hass)
        assert len(engine.data.parcels) == len(engine.data.review) == 1
        assert len(engine.data.filtered) == 1
        yield engine, client


async def call(
    hass: HomeAssistant,
    service: str,
    data: dict[str, Any] | None = None,
    *,
    user: User | None = None,
    response: bool = False,
) -> ServiceResponse:
    """Call a Parcels service as ``user``, or like an automation without one."""
    return await hass.services.async_call(
        DOMAIN,
        service,
        data or {},
        blocking=True,
        context=Context(user_id=user.id if user else None),
        return_response=response,
    )


async def add(
    hass: HomeAssistant, number: str, *, user: User | None = None, **data: Any
) -> str:
    """Add a parcel by tracking number; return its ID."""
    result = await call(
        hass, "add", {"tracking_number": number, **data}, user=user, response=True
    )
    assert result is not None
    return str(result["parcel_id"])


async def refused(
    hass: HomeAssistant,
    service: str,
    data: dict[str, Any],
    key: str,
    *,
    user: User | None = None,
) -> ServiceValidationError:
    """Call a service that must fail with the translated user error ``key``."""
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, service, data, user=user)
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == key
    return err.value


async def async_wait_reprocess(hass: HomeAssistant) -> None:
    """Wait for the e-mails of a trusted sender to be read again."""
    await asyncio.gather(
        *(
            task
            for task in asyncio.all_tasks()
            if task.get_name().startswith("parcels reprocess")
        )
    )
    await hass.async_block_till_done()


def origin_with(parcel: Parcel, number: str) -> str:
    """Return the ID of the parcel's origin with this tracking number."""
    (found,) = (
        origin_id
        for origin_id, origin in parcel.origins.items()
        if origin.tracking_number == number
    )
    return found


def add_phone(
    hass: HomeAssistant,
    name: str,
    user_id: str,
    *,
    os_name: str = "iOS",
    model: str = "iPhone17,1",
) -> str:
    """Add the Home Assistant app on a user's Apple device; return the device ID."""
    slug = name.lower().replace(" ", "_")
    entry = MockConfigEntry(
        domain="mobile_app",
        title=name,
        data={
            "app_data": {},
            "app_id": "io.robbie.HomeAssistant",
            "app_name": "Home Assistant",
            "app_version": "2026.11",
            "device_id": f"app-{slug}",
            "device_name": name,
            "os_name": os_name,
            "os_version": "26.1",
            "manufacturer": "Apple",
            "model": model,
            "supports_encryption": False,
            "user_id": user_id,
            "webhook_id": f"webhook-{slug}",
        },
    )
    entry.add_to_hass(hass)
    return (
        dr.async_get(hass)
        .async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("mobile_app", f"app-{slug}")},
            name=name,
        )
        .id
    )


# -- Adding parcels -----------------------------------------------------------


async def test_add(
    hass: HomeAssistant, engine: ParcelsEngine, hass_admin_user: MockUser
) -> None:
    """A parcel gets the normalised number, its carrier and the caller as owner."""
    parcel_id = await add(
        hass, "rr 482-915-732 pt", user=hass_admin_user, merchant="  Worten "
    )

    parcel = engine.data.parcels[parcel_id]
    state = parcel.state
    assert state.tracking_number == CTT_NUMBER
    assert state.carrier == "ctt"
    assert state.merchant == "Worten"
    assert state.status is ParcelStatus.SHIPPED
    assert state.source is Source.MANUAL
    assert state.owners == (OWNER,)
    assert not parcel.private
    # The same number again is the same parcel.
    assert await add(hass, CTT_NUMBER, user=hass_admin_user) == parcel_id
    assert list(engine.data.parcels) == [parcel_id]


async def test_add_carrier_and_private(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """The carrier ignores case; a private parcel from an automation has no owner."""
    parcel_id = await add(hass, DHL_NUMBER, carrier="DHL", private=True)
    detected = await add(hass, CTT_NUMBER, carrier="")

    parcel = engine.data.parcels[parcel_id]
    assert parcel.state.carrier == "dhl"
    assert parcel.private
    assert parcel.state.owners == ()
    # An empty carrier is found from the number.
    assert engine.data.parcels[detected].state.carrier == "ctt"


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"tracking_number": CTT_NUMBER, "carrier": "pigeon"},
        {"tracking_number": CTT_NUMBER, "private": "maybe"},
        {"tracking_number": CTT_NUMBER, "colour": "red"},
    ],
)
async def test_add_bad_input(
    hass: HomeAssistant, engine: ParcelsEngine, data: dict[str, Any]
) -> None:
    """Input the schema refuses adds nothing."""
    with pytest.raises(p.Invalid):
        await call(hass, "add", data)
    assert not engine.data.parcels


@pytest.mark.parametrize(
    ("action", "data"),
    [
        ("add", {"tracking_number": "RR123456785PT", "merchant": "A" * 501}),
        ("add", {"tracking_number": "A" * 501}),
        ("update", {"merchant": "A" * 501}),
        ("update", {"tracking_number": "A" * 501}),
        ("update", {"pickup_point": "A" * 501}),
        ("update", {"pickup_code": "A" * 501}),
    ],
)
async def test_action_texts_have_the_page_limits(
    hass: HomeAssistant, engine: ParcelsEngine, action: str, data: dict[str, Any]
) -> None:
    """The actions take texts of at most 500 characters, as the page does."""
    if action == "update":
        await call(hass, "add", {"tracking_number": "RR123456785PT"})
        (parcel,) = engine.data.parcels.values()
        data = {"parcel_id": parcel.id, **data}
    before = engine.data.as_dict()

    with pytest.raises(p.Invalid):
        await call(hass, action, data)
    assert engine.data.as_dict() == before

    schema = ADD_SCHEMA if action == "add" else UPDATE_SCHEMA
    schema({key: value[:500] for key, value in data.items()})


@pytest.mark.parametrize("number", ["1234", "A" * 41, "RR4829#5732PT"])
async def test_add_invalid_number(
    hass: HomeAssistant, engine: ParcelsEngine, number: str
) -> None:
    """A number that is too short, too long or has symbols is refused."""
    await refused(hass, "add", {"tracking_number": number}, "invalid_tracking_number")
    assert not engine.data.parcels


async def test_add_paack_order_id(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """A Paack order ID keeps its case; typed alone, its shape means Paack."""
    parcel_id = await add(hass, f" {PAACK_ID} ", carrier="paack")
    automatic = await add(hass, PAACK_ID)
    other_case = await add(hass, PAACK_ID.lower(), carrier="paack")

    state = engine.data.parcels[parcel_id].state
    assert (state.tracking_number, state.carrier) == (PAACK_ID, "paack")
    assert automatic == parcel_id
    # Paack's IDs are case-sensitive: in another case, it's another order.
    assert other_case != parcel_id
    assert engine.data.parcels[other_case].state.tracking_number == PAACK_ID.lower()


async def test_add_paack_order_id_for_another_carrier(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """Only Paack's order IDs may have an underscore."""
    data = {"tracking_number": PAACK_ID, "carrier": "ctt"}
    await refused(hass, "add", data, "invalid_tracking_number")
    assert not engine.data.parcels


async def test_update_to_paack_order_id(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> None:
    """A Paack order ID can replace the number of a parcel that Paack delivers."""
    paack = await add(hass, PAACK_BARCODE)
    ctt = await add(hass, CTT_NUMBER)
    unknown = await add(hass, LOOSE_NUMBER)
    other_id = "Wx4Hn8Tz3_1"

    freezer.tick()
    await call(hass, "update", {"parcel_id": paack, "tracking_number": PAACK_ID})
    data = {"parcel_id": ctt, "tracking_number": other_id}
    await refused(hass, "update", data, "invalid_tracking_number")
    await call(hass, "update", {**data, "carrier": "paack"})
    # Without a carrier, the ID's shape says Paack.
    await call(hass, "update", {"parcel_id": unknown, "tracking_number": "Hj6Np3Ws8_1"})

    state = engine.data.parcels[paack].state
    assert (state.tracking_number, state.carrier) == (PAACK_ID, "paack")
    state = engine.data.parcels[ctt].state
    assert (state.tracking_number, state.carrier) == (other_id, "paack")
    state = engine.data.parcels[unknown].state
    assert (state.tracking_number, state.carrier) == ("Hj6Np3Ws8_1", "paack")


async def test_hub_not_loaded(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """Without the hub, the services explain that it isn't loaded."""
    assert await hass.config_entries.async_unload(engine.entry.entry_id)

    await refused(hass, "add", {"tracking_number": CTT_NUMBER}, "hub_not_loaded")
    await refused(hass, "refresh", {}, "hub_not_loaded")
    await refused(hass, "trust_sender", {"domain": SHOP}, "hub_not_loaded")


# -- Editing parcels ----------------------------------------------------------


async def test_update(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> None:
    """A later edit overrides what was added, and an empty value clears it."""
    parcel_id = await add(hass, CTT_NUMBER, merchant="Worten")

    freezer.tick()
    await call(
        hass,
        "update",
        {
            "parcel_id": parcel_id,
            "merchant": "Fnac",
            "carrier": "CTT",
            "pickup_point": "Locker 12",
            "pickup_code": "4711",
            "eta_start": "2026-11-19",
            "eta_end": "2026-11-20",
            "window_start": "13:00",
            "window_end": "14:00",
        },
    )
    state = engine.data.parcels[parcel_id].state
    assert (state.merchant, state.carrier) == ("Fnac", "ctt")
    assert (state.pickup_point, state.pickup_code) == ("Locker 12", "4711")
    assert state.eta == Eta(
        start=date(2026, 11, 19),
        end=date(2026, 11, 20),
        window_start=time(13),
        window_end=time(14),
    )

    freezer.tick()
    await call(
        hass,
        "update",
        {"parcel_id": parcel_id, "merchant": " ", "pickup_code": None},
    )
    state = engine.data.parcels[parcel_id].state
    assert state.merchant is None
    assert (state.pickup_point, state.pickup_code) == ("Locker 12", None)


async def test_update_eta(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> None:
    """A later start date moves the end along; no start date clears the ETA."""
    parcel_id = await add(hass, CTT_NUMBER)
    await call(
        hass,
        "update",
        {"parcel_id": parcel_id, "eta_start": "2026-11-19", "eta_end": "2026-11-20"},
    )

    freezer.tick()
    await call(hass, "update", {"parcel_id": parcel_id, "eta_start": "2026-11-23"})
    eta = engine.data.parcels[parcel_id].state.eta
    assert eta is not None
    assert (eta.start, eta.end) == (date(2026, 11, 23), date(2026, 11, 23))

    freezer.tick()
    await call(hass, "update", {"parcel_id": parcel_id, "eta_start": None})
    assert engine.data.parcels[parcel_id].state.eta is None


async def test_update_number_merges(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> None:
    """Typing another parcel's number merges it into the edited, now private one."""
    other = await add(hass, CTT_NUMBER)
    parcel_id = await add(hass, DHL_NUMBER, carrier="dhl")

    freezer.tick()
    await call(
        hass,
        "update",
        {"parcel_id": parcel_id, "tracking_number": "rr482915732pt", "private": True},
    )

    assert other not in engine.data.parcels
    parcel = engine.data.parcels[parcel_id]
    assert parcel.private
    assert parcel.state.tracking_number == CTT_NUMBER
    assert len(parcel.origins) == 3


@pytest.mark.parametrize(
    ("data", "key"),
    [
        ({"parcel_id": "p_missing", "merchant": "Fnac"}, "unknown_parcel"),
        ({"tracking_number": "12"}, "invalid_tracking_number"),
    ],
)
async def test_update_refused(
    hass: HomeAssistant, engine: ParcelsEngine, data: dict[str, Any], key: str
) -> None:
    """An unknown parcel or an invalid number is a user error."""
    parcel_id = await add(hass, CTT_NUMBER)

    await refused(hass, "update", {"parcel_id": parcel_id, **data}, key)
    assert engine.data.parcels[parcel_id].state.tracking_number == CTT_NUMBER


@pytest.mark.parametrize(
    "data",
    [
        {"merchant": "Fnac"},
        {"parcel_id": "p_1", "carrier": "pigeon"},
        {"parcel_id": "p_1", "eta_start": "19/11/2026"},
        {"parcel_id": "p_1", "window_end": "25:00"},
        {"parcel_id": "p_1", "private": "maybe"},
    ],
)
async def test_update_bad_input(
    hass: HomeAssistant, engine: ParcelsEngine, data: dict[str, Any]
) -> None:
    """The schema refuses a missing parcel, an unknown carrier and bad dates."""
    with pytest.raises(p.Invalid):
        await call(hass, "update", data)


async def test_mark_delivered_and_archive(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """A parcel can be marked delivered now, then archived."""
    parcel_id = await add(hass, CTT_NUMBER)

    await call(hass, "mark_delivered", {"parcel_id": parcel_id})
    parcel = engine.data.parcels[parcel_id]
    assert parcel.state.status is ParcelStatus.DELIVERED
    assert parcel.state.delivered_at == dt_util.utcnow()

    await call(hass, "archive", {"parcel_id": parcel_id})
    assert parcel.archived == dt_util.utcnow()
    await refused(hass, "archive", {"parcel_id": "p_missing"}, "unknown_parcel")
    await refused(hass, "mark_delivered", {"parcel_id": "p_missing"}, "unknown_parcel")


async def test_undo_a_delivery_marked_by_hand(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> None:
    """Undo takes a mark back; automations told of the delivery hear it.

    However old the news it goes back to: here the parcel was added two days
    before it was marked delivered.
    """
    parcel_id = await add(hass, CTT_NUMBER)
    freezer.tick(timedelta(days=2))
    await call(hass, "mark_delivered", {"parcel_id": parcel_id})
    parcel = engine.data.parcels[parcel_id]
    assert parcel_json(parcel, SYSTEM_VIEWER)["delivered_by_hand"]
    added, changed, delivered = (
        async_capture_events(hass, event)
        for event in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED)
    )

    await call(hass, "undo_delivery", {"parcel_id": parcel_id})
    await hass.async_block_till_done()

    assert parcel.state.status is ParcelStatus.SHIPPED
    assert parcel.state.tracking_number == CTT_NUMBER
    assert not parcel_json(parcel, SYSTEM_VIEWER)["delivered_by_hand"]
    assert added == delivered == []
    assert [
        (event.data["parcel_id"], event.data["status"], event.data["previous_status"])
        for event in changed
    ] == [(parcel_id, "shipped", "delivered")]
    await refused(
        hass, "undo_delivery", {"parcel_id": parcel_id}, "no_delivery_to_undo"
    )


async def test_undoing_the_mark_of_a_parcel_without_emails_deletes_it(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """A mark that was all that was left of a parcel goes with the parcel."""
    parcel_id = apply_contribution(
        engine.data,
        contribution("msg:a#0", carrier="ctt", number=CTT_NUMBER, owner=None),
        dt_util.utcnow(),
    ).parcel_id
    engine.async_changed()
    await call(hass, "mark_delivered", {"parcel_id": parcel_id})
    # Read again, its only e-mail turned out not to be about a parcel.
    engine.clear_outputs("a", dt_util.utcnow())
    assert set(engine.data.parcels[parcel_id].origins) == {manual_origin_id(parcel_id)}

    await call(hass, "undo_delivery", {"parcel_id": parcel_id})
    await hass.async_block_till_done()

    assert parcel_id not in engine.data.parcels


async def test_a_reported_delivery_isnt_by_hand(
    hass: HomeAssistant, engine: ParcelsEngine, sam: User
) -> None:
    """Only a mark alone shows Undo, and only to who may see the parcel."""
    parcel_id = await add(hass, CTT_NUMBER, private=True)
    await call(hass, "mark_delivered", {"parcel_id": parcel_id})
    parcel = engine.data.parcels[parcel_id]
    assert parcel_json(parcel, SYSTEM_VIEWER)["delivered_by_hand"]
    assert not parcel_json(parcel, viewer_for(hass, sam))["delivered_by_hand"]

    apply_contribution(
        engine.data,
        contribution(
            "msg:carrier#0",
            kind=MailKind.DELIVERED,
            time=dt_util.utcnow(),
            carrier="ctt",
            number=CTT_NUMBER,
            owner=None,
        ),
        dt_util.utcnow(),
    )
    parcel.touch(dt_util.utcnow())

    view = parcel_json(parcel, SYSTEM_VIEWER)
    assert (view["status"], view["restricted"]) == ("delivered", False)
    assert not view["delivered_by_hand"]


async def test_after_an_undo_old_news_is_old_again(
    hass: HomeAssistant, engine: ParcelsEngine, freezer: FrozenDateTimeFactory
) -> None:
    """Only the undo itself makes old news worth telling.

    E-mails read days late after it, saying the parcel was delivered and then
    returned, tell nobody.
    """
    added = dt_util.utcnow()
    parcel_id = await add(hass, CTT_NUMBER)
    freezer.tick(timedelta(days=3))
    await call(hass, "mark_delivered", {"parcel_id": parcel_id})
    await call(hass, "undo_delivery", {"parcel_id": parcel_id})
    events = [
        async_capture_events(hass, event)
        for event in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED)
    ]

    for origin_id, kind, hours in (
        ("msg:delivered#0", MailKind.DELIVERED, 24),
        ("msg:returned#0", MailKind.RETURN, 30),
    ):
        apply_contribution(
            engine.data,
            contribution(
                origin_id,
                kind=kind,
                time=added + timedelta(hours=hours),
                carrier="ctt",
                number=CTT_NUMBER,
            ),
            dt_util.utcnow(),
        )
        engine.async_changed()
    await hass.async_block_till_done()

    assert engine.data.parcels[parcel_id].state.status is ParcelStatus.RETURNED
    assert events == [[], [], []]


# -- Customer returns ---------------------------------------------------------


def add_return(
    engine: ParcelsEngine, *, owners: tuple[str, ...] = (OWNER,), private: bool = False
) -> ReturnEntry:
    """Add a return to Loja Exemplo, picked up today."""
    now = dt_util.utcnow()
    entry = ReturnEntry(id="ret_1", created=now, updated=now, private=private)
    entry.origins["m1"] = ReturnOrigin(
        message="m1",
        time=now,
        label=SHOP,
        merchant="Loja Exemplo",
        pickup=dt_util.now().date(),
        pickup_rule=PickupRule.EMAIL,
        owners=owners,
    )
    engine.data.returns[entry.id] = entry
    return entry


async def test_return_picked_up(
    hass: HomeAssistant, engine: ParcelsEngine, sam: User
) -> None:
    """Anyone who sees a return may mark it picked up, and undo that."""
    entry = add_return(engine)
    data = {"return_id": entry.id}

    await call(hass, "mark_return_picked_up", data, user=sam)
    assert entry.picked_up == dt_util.utcnow()
    assert entry.done(dt_util.now().date())
    await call(hass, "undo_return_picked_up", data, user=sam)
    assert entry.picked_up is None
    assert not entry.done(dt_util.now().date())
    # An automation may too.
    await call(hass, "mark_return_picked_up", data)
    assert entry.picked_up == dt_util.utcnow()
    for service in ("mark_return_picked_up", "undo_return_picked_up"):
        await refused(hass, service, {"return_id": "ret_missing"}, "unknown_return")


async def test_private_return_refused(
    hass: HomeAssistant, engine: ParcelsEngine, hass_admin_user: MockUser, sam: User
) -> None:
    """Only its owners may mark a private return, administrators included."""
    entry = add_return(engine, owners=(OTHER_OWNER,), private=True)
    data = {"return_id": entry.id}

    for service in ("mark_return_picked_up", "undo_return_picked_up"):
        await refused(hass, service, data, "not_allowed", user=hass_admin_user)
    assert entry.picked_up is None
    await call(hass, "mark_return_picked_up", data, user=sam)
    assert entry.picked_up == dt_util.utcnow()


# -- Merging and splitting ----------------------------------------------------


async def test_merge(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """Merging keeps the first parcel, which gets the others' origins."""
    first = await add(hass, CTT_NUMBER)
    second = await add(hass, DHL_NUMBER, carrier="dhl")

    await refused(hass, "merge", {"parcel_ids": [first, first]}, "merge_needs_two")
    await refused(hass, "merge", {"parcel_ids": [first, "p_missing"]}, "unknown_parcel")
    with pytest.raises(p.Invalid):
        await call(hass, "merge", {"parcel_ids": [first]})
    assert len(engine.data.parcels) == 2

    result = await call(hass, "merge", {"parcel_ids": [second, first]}, response=True)
    assert result == {"parcel_id": second}
    assert list(engine.data.parcels) == [second]
    assert len(engine.data.parcels[second].origins) == 2


async def test_split(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """An origin can move to a new parcel when something stays behind."""
    parcel_id = await add(hass, CTT_NUMBER)
    other = await add(hass, DHL_NUMBER, carrier="dhl")
    await call(hass, "merge", {"parcel_ids": [parcel_id, other]})
    await call(hass, "update", {"parcel_id": parcel_id, "merchant": "Worten"})
    parcel = engine.data.parcels[parcel_id]
    edit = f"man:{parcel_id}"
    ctt_origin = origin_with(parcel, CTT_NUMBER)
    dhl_origin = origin_with(parcel, DHL_NUMBER)
    assert set(parcel.origins) == {edit, ctt_origin, dhl_origin}

    for origins, key in (
        ([edit], "unknown_origin"),
        (["man:p_missing"], "unknown_origin"),
        ([ctt_origin, dhl_origin], "nothing_left"),
    ):
        await refused(hass, "split", {"parcel_id": parcel_id, "origins": origins}, key)
    with pytest.raises(p.Invalid):
        await call(hass, "split", {"parcel_id": parcel_id, "origins": []})

    result = await call(
        hass,
        "split",
        {"parcel_id": parcel_id, "origins": [dhl_origin]},
        response=True,
    )
    assert result is not None
    new = engine.data.parcels[result["parcel_id"]]
    assert list(new.origins) == [dhl_origin]
    assert new.state.tracking_number == DHL_NUMBER
    assert set(parcel.origins) == {edit, ctt_origin}


async def test_split_shared_number(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """Origins with the same number stay together."""
    parcel_id = await add(hass, CTT_NUMBER)
    assert await add(hass, CTT_NUMBER) == parcel_id
    _, second = engine.data.parcels[parcel_id].origins

    await refused(
        hass,
        "split",
        {"parcel_id": parcel_id, "origins": [second]},
        "shared_number",
    )


async def test_split_shared_shipment(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """Amazon's e-mail without a number stays with its shipment's package."""
    now = dt_util.utcnow()
    shipment = {
        "label": "amazon.es",
        "merchant": "Amazon.es",
        "orders": ["406-7654321-7654321"],
        "shipment_id": "Hq4Wn7Pz2",
    }
    applied = [
        apply_contribution(
            engine.data,
            contribution(
                origin_id, time=now - timedelta(hours=hours), **shipment, **number
            ),
            now,
        )
        for origin_id, hours, number in (
            ("msg:box#0", 2, {}),
            ("msg:numbered#0", 1, {"carrier": "ctt", "number": "RR102030405PT"}),
        )
    ]
    parcel_id = applied[0].parcel_id
    assert parcel_id is not None
    assert applied[1].parcel_id == parcel_id
    engine.async_changed()

    await refused(
        hass,
        "split",
        {"parcel_id": parcel_id, "origins": ["msg:box#0"]},
        "shared_shipment",
    )


async def test_undo_merge(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """An automatic merge can be undone once."""
    parcel_id = await add(hass, LOOSE_NUMBER, carrier="dhl")
    assert await add(hass, LOOSE_NUMBER, carrier="gls") == parcel_id
    parcel = engine.data.parcels[parcel_id]
    assert parcel.auto_merged is not None
    merged = parcel.auto_merged.origin

    await call(hass, "undo_merge", {"parcel_id": parcel_id})

    assert parcel.auto_merged is None
    assert merged not in parcel.origins
    (restored,) = (p for pid, p in engine.data.parcels.items() if pid != parcel_id)
    assert list(restored.origins) == [merged]
    assert restored.state.carrier == "gls"
    await refused(hass, "undo_merge", {"parcel_id": parcel_id}, "nothing_to_undo")


async def test_confirm_merge(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """Confirming an automatic merge keeps the parcels together."""
    parcel_id = await add(hass, LOOSE_NUMBER, carrier="dhl")
    await add(hass, LOOSE_NUMBER, carrier="gls")

    await call(hass, "update", {"parcel_id": parcel_id, "confirm_merge": True})

    parcel = engine.data.parcels[parcel_id]
    assert parcel.auto_merged is None
    assert len(parcel.origins) == 2
    await refused(hass, "undo_merge", {"parcel_id": parcel_id}, "nothing_to_undo")


async def test_inferred_delivery(hass: HomeAssistant, engine: ParcelsEngine) -> None:
    """An inferred delivery can be kept, or undone once and not inferred again.

    Two Amazon orders were due on 12 November and the carrier delivered an
    Amazon parcel on the 13th, so both count as delivered, without merging.
    Undoing a kept delivery brings back the inferred one. Taking an inferred
    one back tells nobody: nobody was told of it.
    """
    data = engine.data
    now = dt_util.utcnow()
    delivered = dt_util.parse_datetime("2026-11-13 10:40:00+00:00")
    assert delivered is not None
    apply_contribution(
        data,
        contribution(
            "msg:carrier#0",
            kind=MailKind.DELIVERED,
            time=delivered,
            carrier="ctt_expresso",
            number="EX123456789012",
            merchant="Amazon",
            label="cttexpresso.pt",
        ),
        now,
    )
    kept, undone = (
        apply_contribution(
            data,
            contribution(
                f"msg:order{n}#0",
                time=delivered - timedelta(days=2, hours=n),
                merchant="Amazon.es",
                orders=[f"171-000000{n}-000000{n}"],
                eta=Eta(start=date(2026, 11, 12), end=date(2026, 11, 12)),
                label="amazon.es",
            ),
            now,
        ).parcel_id
        for n in (1, 2)
    )
    assert kept != undone

    engine.async_changed()

    assert len(data.parcels) == 3
    for parcel_id in (kept, undone):
        state = data.parcels[parcel_id].state
        assert state.status is ParcelStatus.DELIVERED
        assert state.inferred

    await call(hass, "update", {"parcel_id": kept, "confirm_delivery": True})
    state = data.parcels[kept].state
    assert state.status is ParcelStatus.DELIVERED
    assert not state.inferred
    await call(hass, "undo_delivery", {"parcel_id": kept})
    state = data.parcels[kept].state
    assert state.status is ParcelStatus.DELIVERED
    assert state.inferred

    events = [
        async_capture_events(hass, event)
        for event in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED)
    ]
    await call(hass, "undo_delivery", {"parcel_id": undone})
    await hass.async_block_till_done()
    parcel = data.parcels[undone]
    assert parcel.state.status is ParcelStatus.SHIPPED
    assert parcel.delivery_rejected
    assert events == [[], [], []]
    engine.async_changed()
    assert parcel.state.status is ParcelStatus.SHIPPED
    await refused(hass, "undo_delivery", {"parcel_id": undone}, "no_delivery_to_undo")


# -- E-mails ------------------------------------------------------------------


async def test_refresh(hass: HomeAssistant, mail: Mail) -> None:
    """Refresh reads new mail now."""
    engine, client = mail
    client.add("common/german_shop_dhl.eml")
    syncs = len(client.syncs)

    await call(hass, "refresh")
    await hass.async_block_till_done()

    assert len(client.syncs) == syncs + 1
    assert "german_shop_dhl.eml" in client.fetches
    assert len(engine.data.review) == 2


async def test_reprocess(hass: HomeAssistant, mail: Mail) -> None:
    """Reprocessing downloads the e-mails again and decides anew."""
    engine, client = mail
    (parcel,) = engine.data.parcels.values()
    (review,) = engine.data.review.values()
    (filtered,) = engine.data.filtered.values()
    client.fetches.clear()

    await call(hass, "reprocess", {"parcel_id": parcel.id})
    await call(hass, "reprocess", {"review_id": review.id})
    await call(hass, "reprocess", {"filtered_id": filtered.id, "use_ai": False})

    assert client.fetches == [
        "ctt_in_transit_pt.eml",
        "small_shop_ctt.eml",
        "unknown_phone_only.eml",
    ]
    data = engine.data
    assert [p.state.tracking_number for p in data.parcels.values()] == [CTT_NUMBER]
    assert [item.sender_domain for item in data.review.values()] == [SHOP]
    assert [item.sender_domain for item in data.filtered.values()] == [FILTERED_SENDER]


async def test_reprocess_refused(hass: HomeAssistant, mail: Mail) -> None:
    """Reprocessing needs a known item with an e-mail, and the AI to use it."""
    engine, client = mail
    (parcel,) = engine.data.parcels.values()
    manual = await add(hass, DHL_NUMBER, carrier="dhl")
    fetches = list(client.fetches)

    for data, key in (
        ({"parcel_id": manual}, "no_messages"),
        ({"parcel_id": parcel.id, "use_ai": True}, "ai_not_configured"),
        ({"parcel_id": "p_missing"}, "unknown_parcel"),
        ({"review_id": "r_missing"}, "unknown_review"),
        ({"filtered_id": "f_missing"}, "unknown_filtered"),
    ):
        await refused(hass, "reprocess", data, key)
    for data in ({}, {"parcel_id": parcel.id, "review_id": "r_1"}):
        with pytest.raises(p.Invalid):
            await call(hass, "reprocess", data)
    assert client.fetches == fetches


async def test_reprocess_deleted_mail(hass: HomeAssistant, mail: Mail) -> None:
    """When the e-mail is gone, the error says so and the parcel stays."""
    engine, client = mail
    (parcel,) = engine.data.parcels.values()
    client.delete("ctt_in_transit_pt.eml")

    with pytest.raises(HomeAssistantError) as err:
        await call(hass, "reprocess", {"parcel_id": parcel.id})

    assert not isinstance(err.value, ServiceValidationError)
    assert err.value.translation_key == "message_gone"
    assert list(engine.data.parcels) == [parcel.id]


async def test_reprocess_mail_the_parsers_fail_on(
    hass: HomeAssistant, mail: Mail, caplog: pytest.LogCaptureFixture
) -> None:
    """When the parsers fail on the e-mail, the error says so and the parcel stays."""
    engine, _ = mail
    (parcel,) = engine.data.parcels.values()
    origins = dict(parcel.origins)
    fail = AsyncMock(side_effect=ValueError("Rua Secreta 99"))

    with (
        patch.object(ParcelsEngine, "async_parse", fail),
        pytest.raises(HomeAssistantError) as err,
    ):
        await call(hass, "reprocess", {"parcel_id": parcel.id})

    assert not isinstance(err.value, ServiceValidationError)
    assert err.value.translation_key == "message_unreadable"
    assert list(engine.data.parcels) == [parcel.id]
    assert engine.data.parcels[parcel.id].origins == origins
    assert "Rua Secreta" not in caplog.text


async def test_reprocess_reads_the_email_into_its_parcel(
    hass: HomeAssistant, mail: Mail, hass_admin_user: MockUser, sam: User
) -> None:
    """Reading an e-mail again keeps its parcel: the ID, privacy and flags."""
    engine, _ = mail
    (parcel,) = engine.data.parcels.values()
    (origin_id,) = parcel.origins
    await call(
        hass, "update", {"parcel_id": parcel.id, "private": True}, user=hass_admin_user
    )
    await call(hass, "archive", {"parcel_id": parcel.id}, user=hass_admin_user)
    parcel.delivery_rejected = True
    flag = AutoMerge(origin_id, dt_util.utcnow(), REASON_SAME_MERCHANT_ETA)
    parcel.auto_merged = flag
    archived = parcel.archived
    assert archived is not None
    events = [
        async_capture_events(hass, event)
        for event in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED)
    ]

    await call(hass, "reprocess", {"parcel_id": parcel.id}, user=hass_admin_user)
    await hass.async_block_till_done()

    (again,) = engine.data.parcels.values()
    assert again.id == parcel.id
    assert list(again.origins) == [origin_id]
    assert (again.private, again.archived, again.delivery_rejected) == (
        True,
        archived,
        True,
    )
    assert again.auto_merged == flag
    assert not viewer_for(hass, sam).can_see(again)
    assert events == [[], [], []]
    assert not engine.data.messages[again.origins[origin_id].message].shells


async def test_reprocess_keeps_the_rest_of_the_parcel(
    hass: HomeAssistant, mail: Mail, hass_admin_user: MockUser, sam: User
) -> None:
    """An e-mail read again goes back to the parcel it shares with others."""
    engine, _ = mail
    (parcel,) = engine.data.parcels.values()
    (origin_id,) = parcel.origins
    now = dt_util.utcnow()
    linked = apply_contribution(
        engine.data,
        contribution(
            "msg:order#0",
            kind=MailKind.ORDER,
            time=now - timedelta(days=1),
            merchant="Loja Exemplo",
            orders=("#1001",),
            owner=OWNER,
        ),
        now,
    )
    assert linked.parcel_id is not None
    merge_parcels(engine.data, parcel.id, [linked.parcel_id], now)
    flag = AutoMerge("msg:order#0", now, REASON_SAME_MERCHANT_ETA)
    parcel.auto_merged = flag
    await call(
        hass, "update", {"parcel_id": parcel.id, "private": True}, user=hass_admin_user
    )

    await call(hass, "reprocess", {"parcel_id": parcel.id}, user=hass_admin_user)

    (again,) = engine.data.parcels.values()
    assert again.id == parcel.id
    assert set(again.origins) == {origin_id, "msg:order#0"}
    assert again.state.tracking_number == CTT_NUMBER
    assert again.private
    assert again.auto_merged == flag
    assert not viewer_for(hass, sam).can_see(again)


async def test_reprocess_keeps_the_edits(
    hass: HomeAssistant, mail: Mail, hass_admin_user: MockUser
) -> None:
    """A parcel the user edited is read again with the edits, not beside them."""
    engine, _ = mail
    (parcel,) = engine.data.parcels.values()
    await call(
        hass,
        "update",
        {"parcel_id": parcel.id, "pickup_point": "Locker 12"},
        user=hass_admin_user,
    )

    await call(hass, "reprocess", {"parcel_id": parcel.id}, user=hass_admin_user)

    (again,) = engine.data.parcels.values()
    assert again.id == parcel.id
    assert (again.state.tracking_number, again.state.pickup_point) == (
        CTT_NUMBER,
        "Locker 12",
    )


async def test_reprocess_of_a_delivered_parcel_tells_nobody_again(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mail: Mail
) -> None:
    """Automations hear of the delivery once, not again when it is read again."""
    engine, client = mail
    freezer.move_to("2026-11-17 12:00:00+00:00")
    client.add("carriers/ctt_delivered_pt.eml")
    delivered = async_capture_events(hass, EVENT_DELIVERED)
    await call(hass, "refresh")
    await hass.async_block_till_done()
    (parcel,) = (
        parcel
        for parcel in engine.data.parcels.values()
        if parcel.state.status is ParcelStatus.DELIVERED
    )
    assert len(delivered) == 1
    events = [
        async_capture_events(hass, event)
        for event in (EVENT_PARCEL_ADDED, EVENT_STATUS_CHANGED, EVENT_DELIVERED)
    ]

    await call(hass, "reprocess", {"parcel_id": parcel.id})
    await hass.async_block_till_done()

    assert engine.data.parcels[parcel.id].state.status is ParcelStatus.DELIVERED
    assert events == [[], [], []]


async def test_reprocess_of_an_unverified_email_keeps_its_parcel(
    hass: HomeAssistant, mail: Mail, hass_admin_user: MockUser, sam: User
) -> None:
    """An accepted e-mail from an unknown shop, read again, waits under review.

    Its parcel stays meanwhile; accepting the e-mail again updates that
    parcel, still private.
    """
    engine, _ = mail
    (review,) = engine.data.review.values()
    record = engine.data.messages[review.message]
    (parcel_id,) = (
        touched
        for touched in engine.review_accept(review.id)
        if engine.data.parcels[touched].state.tracking_number == "RR123456785PT"
    )
    await call(
        hass, "update", {"parcel_id": parcel_id, "private": True}, user=hass_admin_user
    )

    await call(hass, "reprocess", {"parcel_id": parcel_id}, user=hass_admin_user)

    assert record.state is MessageState.REVIEW
    (again,) = engine.data.review.values()
    assert parcel_id in engine.data.parcels
    assert not viewer_for(hass, sam).can_see(engine.data.parcels[parcel_id])

    assert engine.review_accept(again.id) == [parcel_id]

    parcel = engine.data.parcels[parcel_id]
    assert parcel.state.tracking_number == "RR123456785PT"
    assert parcel.private
    assert record.state is MessageState.APPLIED
    assert not record.shells


# -- Senders ------------------------------------------------------------------


async def test_trust_sender(hass: HomeAssistant, mail: Mail) -> None:
    """Trusting the sender of an e-mail under review adds what it says."""
    engine, _ = mail
    (review,) = engine.data.review.values()

    result = await call(hass, "trust_sender", {"review_id": review.id}, response=True)
    await async_wait_reprocess(hass)

    assert result == {"domain": SHOP, "added": 0, "rechecking": 1, "kept": 0}
    assert engine.data.senders[SHOP].trusted
    assert not engine.data.review
    numbers = {p.state.tracking_number for p in engine.data.parcels.values()}
    assert numbers == {CTT_NUMBER, "RR123456785PT"}


async def test_ignore_sender(hass: HomeAssistant, mail: Mail) -> None:
    """Ignoring a sender drops its e-mails from review and the filtered list."""
    engine, _ = mail
    (review,) = engine.data.review.values()
    (filtered,) = engine.data.filtered.values()

    by_review = await call(
        hass, "ignore_sender", {"review_id": review.id}, response=True
    )
    by_domain = await call(
        hass, "ignore_sender", {"domain": f" {FILTERED_SENDER.upper()} "}, response=True
    )

    assert by_review == {"domain": SHOP}
    assert by_domain == {"domain": FILTERED_SENDER}
    assert not engine.data.review
    assert not engine.data.filtered
    for item in (review, filtered):
        assert engine.data.messages[item.message].state is MessageState.IGNORED
    assert engine.data.senders[SHOP].ignored
    assert engine.data.senders[FILTERED_SENDER].ignored


async def test_trust_then_ignore_domain(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """A domain can be trusted and ignored without any e-mail from it."""
    trusted = await call(
        hass, "trust_sender", {"domain": "Example-Store.example"}, response=True
    )
    assert trusted == {"domain": "example-store.example"}
    assert engine.data.senders["example-store.example"].trusted

    await call(hass, "ignore_sender", {"domain": "example-store.example"})
    prefs = engine.data.senders["example-store.example"]
    assert prefs.ignored
    assert not prefs.trusted


@pytest.mark.parametrize(
    ("service", "key"),
    [
        ("trust_sender", "cannot_trust_free_mail"),
        ("ignore_sender", "cannot_ignore_free_mail"),
    ],
)
async def test_free_mail_sender(
    hass: HomeAssistant, engine: ParcelsEngine, service: str, key: str
) -> None:
    """Free mail providers can't be trusted or ignored as a whole."""
    err = await refused(hass, service, {"domain": "gmail.com"}, key)

    assert err.translation_placeholders == {"domain": "gmail.com"}
    assert "gmail.com" not in engine.data.senders
    await refused(hass, service, {"review_id": "r_missing"}, "unknown_review")


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"domain": "localhost"},
        {"domain": "shop .example"},
        {"domain": "-"},
        {"domain": SHOP, "review_id": "r_1"},
    ],
)
@pytest.mark.parametrize("service", ["trust_sender", "ignore_sender"])
async def test_sender_bad_input(
    hass: HomeAssistant, engine: ParcelsEngine, service: str, data: dict[str, Any]
) -> None:
    """A sender is one domain or one e-mail under review."""
    with pytest.raises(p.Invalid):
        await call(hass, service, data)
    assert not engine.data.senders


# -- Permissions --------------------------------------------------------------


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("update", {"merchant": "Fnac"}),
        ("update", {"private": False}),
        ("mark_delivered", {}),
        ("archive", {}),
        ("undo_merge", {}),
        ("undo_delivery", {}),
        ("split", {"origins": ["man:p_1"]}),
    ],
)
async def test_private_parcel_refused(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    hass_admin_user: MockUser,
    sam: User,
    service: str,
    data: dict[str, Any],
) -> None:
    """Only the owners may change a private parcel, administrators included."""
    alex_parcel = await add(hass, CTT_NUMBER, user=hass_admin_user, private=True)
    sam_parcel = await add(hass, DHL_NUMBER, user=sam, carrier="dhl", private=True)
    assert engine.data.parcels[alex_parcel].state.owners == (OWNER,)
    assert engine.data.parcels[sam_parcel].state.owners == (OTHER_OWNER,)

    await refused(
        hass, service, {"parcel_id": alex_parcel, **data}, "not_allowed", user=sam
    )
    await refused(
        hass,
        service,
        {"parcel_id": sam_parcel, **data},
        "not_allowed",
        user=hass_admin_user,
    )
    for parcel in engine.data.parcels.values():
        assert parcel.private
        assert parcel.archived is None
        assert parcel.state.status is ParcelStatus.SHIPPED
        assert parcel.state.merchant is None


async def test_private_number_refused(
    hass: HomeAssistant, engine: ParcelsEngine, hass_admin_user: MockUser, sam: User
) -> None:
    """Nobody reaches a private parcel through its number or a merge."""
    private = await add(hass, CTT_NUMBER, user=hass_admin_user, private=True)
    mine = await add(hass, DHL_NUMBER, user=sam, carrier="dhl")

    await refused(
        hass, "merge", {"parcel_ids": [mine, private]}, "not_allowed", user=sam
    )
    await refused(
        hass, "add", {"tracking_number": "rr482915732pt"}, "not_allowed", user=sam
    )
    await refused(
        hass,
        "update",
        {"parcel_id": mine, "tracking_number": CTT_NUMBER},
        "not_allowed",
        user=sam,
    )
    assert set(engine.data.parcels) == {private, mine}
    assert len(engine.data.parcels[private].origins) == 1
    # An automation may add to it.
    assert await add(hass, CTT_NUMBER) == private


async def test_private_reference_refused(
    hass: HomeAssistant, engine: ParcelsEngine, hass_admin_user: MockUser, sam: User
) -> None:
    """Nobody reaches a private parcel through the Paack shipment it names."""
    private = apply_contribution(
        engine.data,
        contribution(
            "msg:alexmail#0",
            kind=MailKind.OUT_FOR_DELIVERY,
            carrier="paack",
            reference=PAACK_ID.split("_")[0],
            merchant="Loja Exemplo",
            owner=OWNER,
            private=True,
        ),
        dt_util.utcnow(),
    ).parcel_id
    mine = await add(hass, DHL_NUMBER, user=sam, carrier="dhl")

    await refused(hass, "add", {"tracking_number": PAACK_ID}, "not_allowed", user=sam)
    data = {"parcel_id": mine, "tracking_number": PAACK_ID, "carrier": "paack"}
    await refused(hass, "update", data, "not_allowed", user=sam)

    assert set(engine.data.parcels) == {private, mine}
    assert list(engine.data.parcels[private].origins) == ["msg:alexmail#0"]
    assert engine.data.parcels[mine].state.tracking_number == DHL_NUMBER
    # Its owner may add the order ID: it goes to the parcel.
    assert await add(hass, PAACK_ID, user=hass_admin_user) == private


async def test_private_order_refused(
    hass: HomeAssistant, engine: ParcelsEngine, sam: User
) -> None:
    """An edit can't give a parcel the order of someone else's private parcel.

    Only what the edit adds counts: a parcel that already shares an order
    with it can still be edited.
    """
    now = dt_util.utcnow()
    shop = "Loja Exemplo"
    private = apply_contribution(
        engine.data,
        contribution(
            "msg:alexmail#0",
            carrier="dhl",
            number=DHL_NUMBER,
            merchant=shop,
            orders=("1001",),
            owner=OWNER,
            private=True,
        ),
        now,
    ).parcel_id
    mine = apply_contribution(
        engine.data,
        contribution(
            "msg:sammail#0",
            carrier="ctt",
            number=CTT_NUMBER,
            orders=("1001",),
            owner=OTHER_OWNER,
        ),
        now,
    ).parcel_id
    sharing = apply_contribution(
        engine.data,
        contribution(
            "msg:sammail#1",
            carrier="ups",
            number="1Z999AA10123456784",
            merchant=shop,
            orders=("1001",),
            owner=OTHER_OWNER,
        ),
        now,
    ).parcel_id
    assert len({private, mine, sharing}) == 3

    data = {"parcel_id": mine, "merchant": shop}
    await refused(hass, "update", data, "not_allowed", user=sam)
    assert engine.data.parcels[mine].state.merchant is None

    await call(
        hass, "update", {"parcel_id": sharing, "pickup_point": "Cacifo"}, user=sam
    )
    # Another shop's order 1001 is another order.
    await call(hass, "update", {**data, "merchant": "Example Shop"}, user=sam)
    assert engine.data.parcels[sharing].state.pickup_point == "Cacifo"
    assert engine.data.parcels[mine].state.merchant == "Example Shop"
    # An automation may.
    await call(hass, "update", data)
    assert engine.data.parcels[mine].state.merchant == shop


async def test_shared_and_own_parcels_allowed(
    hass: HomeAssistant, engine: ParcelsEngine, hass_admin_user: MockUser, sam: User
) -> None:
    """Anyone may change a shared parcel, and owners their private ones."""
    shared = await add(hass, CTT_NUMBER, user=hass_admin_user)
    private = await add(hass, DHL_NUMBER, user=sam, carrier="dhl", private=True)

    await call(hass, "update", {"parcel_id": shared, "merchant": "Worten"}, user=sam)
    await call(hass, "mark_delivered", {"parcel_id": private}, user=sam)
    result = await call(
        hass, "merge", {"parcel_ids": [private, shared]}, user=sam, response=True
    )

    assert result == {"parcel_id": private}
    parcel = engine.data.parcels[private]
    assert parcel.private
    assert parcel.state.merchant == "Worten"
    assert parcel.state.owners == (OWNER, OTHER_OWNER)
    # Alex owns part of it now.
    await call(hass, "archive", {"parcel_id": private}, user=hass_admin_user)
    assert parcel.archived is not None


async def test_private_parcel_without_owner(
    hass: HomeAssistant, engine: ParcelsEngine, hass_admin_user: MockUser, sam: User
) -> None:
    """A private parcel without owners is for administrators and automations."""
    parcel_id = await add(hass, CTT_NUMBER, private=True)

    await refused(
        hass,
        "update",
        {"parcel_id": parcel_id, "merchant": "Fnac"},
        "not_allowed",
        user=sam,
    )
    await call(
        hass,
        "update",
        {"parcel_id": parcel_id, "merchant": "Fnac"},
        user=hass_admin_user,
    )
    await call(hass, "update", {"parcel_id": parcel_id, "pickup_code": "4711"})

    state = engine.data.parcels[parcel_id].state
    assert (state.merchant, state.pickup_code) == ("Fnac", "4711")


async def test_unknown_user(
    hass: HomeAssistant, engine: ParcelsEngine, hass_admin_user: MockUser
) -> None:
    """A user that no longer exists has no rights and owns nothing."""
    private = await add(hass, CTT_NUMBER, user=hass_admin_user, private=True)
    context = Context(user_id="deleted-user")

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "archive", {"parcel_id": private}, blocking=True, context=context
        )
    assert err.value.translation_key == "not_allowed"
    result = await hass.services.async_call(
        DOMAIN,
        "add",
        {"tracking_number": DHL_NUMBER, "carrier": "dhl"},
        blocking=True,
        context=context,
        return_response=True,
    )
    assert result is not None
    assert engine.data.parcels[str(result["parcel_id"])].state.owners == ()


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("reprocess", {"parcel_id": "p_1"}),
        ("trust_sender", {"domain": SHOP}),
        ("ignore_sender", {"domain": SHOP}),
        ("test_live_activity", {}),
    ],
)
async def test_admin_services(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    sam: User,
    service: str,
    data: dict[str, Any],
) -> None:
    """Only administrators may reprocess, judge senders and test notifications."""
    with pytest.raises(Unauthorized):
        await call(hass, service, data, user=sam)
    with pytest.raises(UnknownUser):
        await hass.services.async_call(
            DOMAIN, service, data, blocking=True, context=Context(user_id="gone")
        )
    assert not engine.data.senders


# -- Live Activity test -------------------------------------------------------


async def test_test_live_activity(
    hass: HomeAssistant,
    engine: ParcelsEngine,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The demo Live Activity goes to the chosen iPhone and ends a minute later."""
    iphone = add_phone(hass, "Alex iPhone", hass_admin_user.id)
    ipad = add_phone(
        hass, "Alex iPad", hass_admin_user.id, os_name="iPadOS", model="iPad16,3"
    )
    sent = async_mock_service(hass, "notify", "mobile_app_alex_iphone")

    await call(hass, "test_live_activity", {"device_id": iphone}, user=hass_admin_user)
    assert [(c.data["title"], c.data["data"]["tag"]) for c in sent] == [
        ("Parcels", "parcels-test")
    ]

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert sent[-1].data == {
        "message": "clear_notification",
        "data": {"tag": "parcels-test"},
    }

    await refused(
        hass,
        "test_live_activity",
        {"device_id": ipad},
        "test_not_iphone",
        user=hass_admin_user,
    )
    assert len(sent) == 2


async def test_test_live_activity_without_notifier(
    hass: HomeAssistant, engine: ParcelsEngine
) -> None:
    """Without its notifier, the hub can't send the demo."""
    notifier, engine.notifier = engine.notifier, None
    try:
        await refused(hass, "test_live_activity", {}, "hub_not_loaded")
    finally:
        engine.notifier = notifier
