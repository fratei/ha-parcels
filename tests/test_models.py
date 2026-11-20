"""Tests for the Parcels data model and its status machine."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date, time
import json
import logging

from homeassistant.util import dt as dt_util
import pytest

from custom_components.parcels.const import MailKind, ParcelStatus
from custom_components.parcels.models import (
    AutoMerge,
    FilteredItem,
    MessageRecord,
    MessageState,
    Order,
    Origin,
    Parcel,
    ParcelEvent,
    ParcelsData,
    ReviewItem,
    SenderPrefs,
    Source,
    Suggestion,
    known_merchant_name,
    merchant_display,
    merchant_key,
    order_key,
)
from custom_components.parcels.parsers.base import Eta

from .factories import T0, at

S = ParcelStatus


@pytest.fixture
def lisbon() -> Generator[None]:
    """Use the Lisbon time zone for local dates."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Lisbon"))
    yield
    dt_util.set_default_time_zone(previous)


def _origin(origin_id: str = "o1", **kwargs) -> Origin:
    kwargs.setdefault("source", Source.PARSER)
    kwargs.setdefault("time", T0)
    return Origin(id=origin_id, **kwargs)


def _event(status: ParcelStatus | None, when, **kwargs) -> ParcelEvent:
    kwargs.setdefault("source", Source.PARSER)
    kwargs.setdefault("origin", "o1")
    return ParcelEvent(time=when, status=status, **kwargs)


def _parcel(*events: ParcelEvent, origins: tuple[Origin, ...] = ()) -> Parcel:
    parcel = Parcel(id="p_test", created=T0, updated=T0)
    for origin in origins or (_origin(),):
        parcel.origins[origin.id] = origin
    parcel.events = list(events)
    return parcel


def test_event_time_decides_not_arrival_order() -> None:
    """A late "shipped" e-mail doesn't move a delivered parcel back."""
    parcel = _parcel(
        _event(S.DELIVERED, at(days=2)),
        _event(S.SHIPPED, at()),
        _event(S.OUT_FOR_DELIVERY, at(days=2, hours=-4)),
    )
    state = parcel.state
    assert state.status is S.DELIVERED
    assert state.status_time == at(days=2)
    assert state.delivered_at == at(days=2)
    assert [entry.status for entry in state.timeline] == [
        S.SHIPPED,
        S.OUT_FOR_DELIVERY,
        S.DELIVERED,
    ]


def test_backward_status_is_ignored() -> None:
    """A reminder that the parcel shipped doesn't undo "in transit"."""
    parcel = _parcel(_event(S.IN_TRANSIT, at()), _event(S.SHIPPED, at(days=1)))
    state = parcel.state
    assert state.status is S.IN_TRANSIT
    assert [entry.accepted for entry in state.timeline] == [True, False]


def test_delay_takes_out_for_delivery_back_to_transit() -> None:
    """A delay notice with a new date can follow "out for delivery"."""
    new_eta = Eta(start=date(2026, 11, 4), end=date(2026, 11, 4))
    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at()),
        _event(S.IN_TRANSIT, at(hours=6), kind=MailKind.DELAYED, eta=new_eta),
    )
    assert parcel.state.status is S.IN_TRANSIT
    assert parcel.state.eta == new_eta

    # Without the delay kind, the same status is a step back.
    plain = _parcel(_event(S.OUT_FOR_DELIVERY, at()), _event(S.IN_TRANSIT, at(hours=6)))
    assert plain.state.status is S.OUT_FOR_DELIVERY


def test_forced_manual_event_wins() -> None:
    """Marking a parcel delivered works from any status."""
    parcel = _parcel(_event(S.ORDERED, at()))
    parcel.events.append(
        _event(S.DELIVERED, at(hours=1), source=Source.MANUAL, origin=None, force=True)
    )
    assert parcel.state.status is S.DELIVERED

    # A returned parcel can't become delivered without force.
    returned = _parcel(_event(S.RETURNED, at()), _event(S.DELIVERED, at(hours=1)))
    assert returned.state.status is S.RETURNED


@pytest.mark.usefixtures("lisbon")
def test_out_for_delivery_without_date_means_today() -> None:
    """The local date of the event is the delivery date."""
    parcel = _parcel(_event(S.OUT_FOR_DELIVERY, at(hours=15)))  # 00:00 in Lisbon
    assert parcel.state.eta == Eta(start=date(2026, 11, 3), end=date(2026, 11, 3))


def test_latest_estimate_wins_and_can_be_cleared() -> None:
    """A newer estimate replaces an older one, also when it arrives first."""
    early = Eta(start=date(2026, 11, 5), end=date(2026, 11, 6))
    late = Eta(start=date(2026, 11, 7), end=date(2026, 11, 7), window_start=time(9))
    parcel = _parcel(
        _event(S.IN_TRANSIT, at(days=1), eta=late), _event(None, at(), eta=early)
    )
    assert parcel.state.eta == late

    parcel.events.append(_event(None, at(days=2), clears_eta=True))
    parcel.touch(at(days=2))
    assert parcel.state.eta is None


def test_the_date_keeps_its_source() -> None:
    """The expected date says which source gave it: the newest that did."""
    early = Eta(start=date(2026, 11, 5), end=date(2026, 11, 5))
    late = Eta(start=date(2026, 11, 6), end=date(2026, 11, 6))
    parcel = _parcel(
        _event(None, at(days=1), eta=late, source=Source.PARCELAPP),
        _event(S.IN_TRANSIT, at(), eta=early),
    )
    assert (parcel.state.eta, parcel.state.eta_source) == (late, Source.PARCELAPP)

    parcel.events.append(_event(None, at(days=2), eta=early))
    parcel.touch(at(days=2))
    assert (parcel.state.eta, parcel.state.eta_source) == (early, Source.PARSER)

    # News without a date keeps the date and its source.
    parcel.events.append(_event(S.IN_TRANSIT, at(days=3), source=Source.PARCELAPP))
    parcel.touch(at(days=3))
    assert (parcel.state.eta, parcel.state.eta_source) == (early, Source.PARSER)

    # Out for delivery without a date means today, as that source says.
    parcel.events.append(
        _event(S.OUT_FOR_DELIVERY, at(days=4), source=Source.PARCELAPP)
    )
    parcel.touch(at(days=4))
    today = Eta(start=date(2026, 11, 6), end=date(2026, 11, 6))
    assert (parcel.state.eta, parcel.state.eta_source) == (today, Source.PARCELAPP)

    parcel.events.append(_event(None, at(days=5), clears_eta=True))
    parcel.touch(at(days=5))
    assert (parcel.state.eta, parcel.state.eta_source) == (None, None)


def test_manual_origin_overrides_and_clears() -> None:
    """The user's edits win; an empty string clears a field."""
    parcel = _parcel(
        _event(S.SHIPPED, at()),
        origins=(
            _origin(
                carrier="dpd",
                tracking_number="05212345678901",
                merchant="Example Shop",
                pickup_point="Locker 1",
            ),
            _origin(
                "man:p_test",
                source=Source.MANUAL,
                time=at(hours=1),
                carrier="gls",
                pickup_point="",
            ),
        ),
    )
    state = parcel.state
    assert state.carrier == "gls"
    assert state.carrier_name == "GLS"
    assert state.tracking_number == "05212345678901"
    assert state.merchant == "Example Shop"
    assert state.pickup_point is None
    assert state.source is Source.MANUAL
    assert state.tracking_url
    assert state.tracking_url.startswith("https://")


def test_best_source_supplies_the_number() -> None:
    """A parser number beats the AI's; the latest parser number wins."""
    parcel = _parcel(
        origins=(
            _origin("a", source=Source.AI, tracking_number="AI000000001"),
            _origin("b", tracking_number="OLD00000001", carrier="ctt"),
            _origin(
                "c", tracking_number="NEW00000001", carrier="ctt", time=at(hours=1)
            ),
        )
    )
    assert parcel.state.tracking_number == "NEW00000001"
    assert parcel.state.source is Source.PARSER


def test_ai_flag_until_confirmed() -> None:
    """Parcels found only by the AI are marked until the user confirms them."""
    origin = _origin(source=Source.AI, tracking_number="AI000000001")
    parcel = _parcel(_event(S.SHIPPED, at(), source=Source.AI), origins=(origin,))
    assert parcel.state.ai
    assert not parcel.state.ai_filled
    origin.confirmed = True
    parcel.touch(at())
    assert not parcel.state.ai


def test_ai_filled_until_confirmed() -> None:
    """What the AI filled in for a parser's parcel is marked until confirmed."""
    fill = _origin("msg:a#ai", source=Source.AI, items=("Lamp",))
    parcel = _parcel(
        _event(S.SHIPPED, at(), origin="msg:a#0"),
        origins=(_origin("msg:a#0", tracking_number="05212345678901"), fill),
    )
    assert not parcel.state.ai
    assert parcel.state.ai_filled
    assert parcel.state.items == ("Lamp",)
    # A parser's items replace the AI's.
    parcel.origins["b"] = _origin("b", time=at(hours=1), items=("Desk lamp",))
    parcel.touch(at())
    assert parcel.state.items == ("Desk lamp",)
    fill.confirmed = True
    parcel.touch(at())
    assert not parcel.state.ai_filled


def test_provisional_until_tracked() -> None:
    """An order without a tracking number is provisional."""
    parcel = _parcel(
        _event(S.ORDERED, at()), origins=(_origin(order_numbers=("#1001",)),)
    )
    assert parcel.state.provisional
    parcel.origins["o1"].tracking_number = "05212345678901"
    parcel.touch(at())
    assert not parcel.state.provisional


def test_items_are_unique_and_capped() -> None:
    """Items are merged from all origins without duplicates."""
    parcel = _parcel(
        origins=(
            _origin("a", items=("Lamp", "Cable")),
            _origin("b", items=("lamp", *(f"Item {n}" for n in range(30)))),
        )
    )
    assert parcel.state.items[:3] == ("Lamp", "Cable", "Item 0")
    assert len(parcel.state.items) == 20


def test_carrier_mail_names_the_carrier() -> None:
    """The carrier's own e-mail names the carrier; the shop's names the shop."""
    number = "61234567890123"
    parcel = _parcel(
        _event(S.OUT_FOR_DELIVERY, at()),
        origins=(
            _origin(
                "carrier",
                label="cttexpresso.pt",
                carrier="ctt_expresso",
                tracking_number=number,
                merchant="Example Seller SL",
            ),
            _origin(
                "shop",
                label="shop.example",
                time=at(hours=1),
                carrier="dhl",
                tracking_number=number,
                merchant="Example Shop",
            ),
        ),
    )
    assert parcel.state.carrier == "ctt_expresso"
    assert parcel.state.merchant == "Example Shop"


def test_seller_is_the_shop_not_a_domain_or_carrier() -> None:
    """The shop's own e-mails name the seller, even when they come later.

    A status service wrote first and only gave its domain; the carrier's
    e-mail named itself. Better evidence re-decides the seller.
    """
    number = "61234567890123"
    service = _origin(
        "service", label="statusmail.example", merchant="statusmail.example"
    )
    carrier = _origin(
        "carrier",
        label="cttexpresso.pt",
        time=at(hours=1),
        carrier="ctt_expresso",
        tracking_number=number,
        merchant="CTT Expresso",
    )
    parcel = _parcel(_event(S.SHIPPED, at()), origins=(service, carrier))
    assert parcel.state.merchant == "statusmail.example"

    parcel.origins["shop"] = _origin(
        "shop", label="lumenhaus.example", time=at(hours=2), merchant="Lumenhaus"
    )
    parcel.touch(at(hours=2))
    assert parcel.state.merchant == "Lumenhaus"

    # Another shop's name from a sender of its own beats a name from elsewhere.
    parcel.origins["relay"] = _origin(
        "relay", label="notify.example", time=at(hours=-1), merchant="Lumenhaus Store"
    )
    parcel.touch(at(hours=2))
    assert parcel.state.merchant == "Lumenhaus"

    # A carrier's name is never the seller.
    only_carrier = _parcel(_event(S.SHIPPED, at()), origins=(carrier,))
    assert only_carrier.state.merchant is None


def test_shop_mail_carrier_only_without_others() -> None:
    """Without a carrier's e-mail or a number, a shop's e-mail names it."""
    shop = _origin(
        "shop", label="shop.example", time=at(hours=1), carrier="gls", merchant="Shop"
    )
    parcel = _parcel(_event(S.SHIPPED, at()), origins=(shop,))
    assert parcel.state.carrier == "gls"

    # Even when the shop's e-mail is newer.
    parcel.origins["carrier"] = _origin(
        "carrier", label="cttexpresso.pt", carrier="ctt_expresso"
    )
    parcel.touch(at(hours=1))
    assert parcel.state.carrier == "ctt_expresso"


def test_shipment_items_win_over_the_order() -> None:
    """A package holds what its shipping e-mail lists, not the whole order."""
    order = _origin(
        "order",
        order_numbers=("1001",),
        items=("Lamp", "Cable", "Chávena de café EX200 para..."),
    )
    shipped = _origin(
        "shipped",
        time=at(hours=1),
        tracking_number="05212345678901",
        order_numbers=("1001",),
        items=("lamp",),
    )
    assert _parcel(origins=(order, shipped)).state.items == ("lamp",)

    # Without a shipment's list, the order's items show, each once.
    again = _origin(
        "again",
        time=at(hours=2),
        order_numbers=("1001",),
        items=("Chávena de café EX200 para expresso", "LAMP"),
    )
    assert _parcel(origins=(order, again)).state.items == (
        "Lamp",
        "Cable",
        "Chávena de café EX200 para expresso",
    )


def test_delivery_code_until_the_parcel_arrives() -> None:
    """A delivery code shows until the parcel is delivered, unless inferred."""
    coded = _origin(tracking_number="05212345678901", pickup_code="4821")
    parcel = _parcel(_event(S.OUT_FOR_DELIVERY, at()), origins=(coded,))
    assert parcel.state.pickup_code == "4821"

    parcel.events.append(_event(S.DELIVERED, at(hours=2), inferred=True))
    parcel.touch(at(hours=2))
    assert parcel.state.inferred
    assert parcel.state.pickup_code == "4821"

    parcel.events.append(_event(S.DELIVERED, at(hours=3)))
    parcel.touch(at(hours=3))
    assert parcel.state.pickup_code is None


def test_keys() -> None:
    """Merchant and order keys ignore case, accents and marketplaces."""
    assert merchant_key("Amazon.es") == merchant_key("amazon.co.uk") == "amazon"
    assert merchant_key("AMAZON EU SARL SUCURSAL EN") == "amazon"
    assert merchant_key("Amazon EU S.à r.l.") == "amazon"
    assert merchant_key("Amazonia Store") == "amazoniastore"
    assert merchant_key("Loja Ação") == "lojaacao"
    assert merchant_key(None) == ""
    assert order_key("Amazon.es", "405-1234567-1234567") == "ord:40512345671234567"
    assert order_key(None, "405-1234567-1234567") == "ord:40512345671234567"
    assert order_key("Example Shop", "#1001") == "ord:exampleshop:1001"
    assert order_key(None, "#1001") is None
    assert order_key("Example Shop", "#") is None


def test_merchant_display() -> None:
    """Marketplaces and legal names of a known merchant show as its name."""
    for name in ("Amazon.es", "amazon.co.uk", "AMAZON EU SARL SUCURSAL EN"):
        assert merchant_display(name) == "Amazon"
    assert merchant_display("Loja Ação") == "Loja Ação"
    assert merchant_display(None) is None


def test_known_merchant_name() -> None:
    """Free text names a merchant only when it starts with a known one."""
    assert known_merchant_name("Amazon.es order") == "Amazon"
    assert known_merchant_name("AMAZON EU SARL") == "Amazon"
    assert known_merchant_name("Headphones from Amazon") is None
    assert known_merchant_name("Example Shop") is None
    assert known_merchant_name("") is None
    assert known_merchant_name(None) is None


def _full_data() -> ParcelsData:
    parcel = _parcel(
        _event(S.SHIPPED, at(), kind=MailKind.SHIPPED),
        _event(
            None,
            at(hours=1),
            eta=Eta(date(2026, 11, 4), date(2026, 11, 5), time(9), time(13)),
        ),
        origins=(
            _origin(
                tracking_number="05212345678901",
                carrier="dpd",
                order_numbers=("#1001",),
                items=("Lamp",),
                owners=("person.one",),
                message="abc",
            ),
            _origin("man:p_test", source=Source.MANUAL, time=at(), merchant=""),
        ),
    )
    parcel.private = True
    parcel.auto_merged = AutoMerge(origin="o1", at=at(), reason="same_merchant_eta")
    suggestion = Suggestion(
        kind=MailKind.SHIPPED,
        carrier="ctt",
        tracking_numbers=("RR123456785PT",),
        eta_start=date(2026, 11, 4),
        window_start=time(9),
    )
    return ParcelsData(
        parcels={parcel.id: parcel},
        orders={
            "ord:exampleshop:1001": Order(
                "ord:exampleshop:1001", "#1001", "Example Shop", at(), at()
            )
        },
        messages={
            "abc": MessageRecord(
                "abc", at(), MessageState.APPLIED, {"entry": "id1"}, at(), "example.com"
            )
        },
        review={
            "r1": ReviewItem(
                "r1",
                at(),
                "def",
                at(),
                "Shop <shop@example.com>",
                "example.com",
                "Your order",
                "entry",
                "person.one",
                "low_confidence",
                True,
                Source.AI,
                suggestion,
                fill=True,
            )
        },
        filtered={
            "f1": FilteredItem(
                "f1", at(), "ghi", at(), "news@example.com", "example.com", "Hi", None
            )
        },
        senders={"example.com": SenderPrefs("example.com", trusted=True)},
        engine={"notifier": {"x": 1}},
        parcelapp={"poll": {"last": "2026-11-02T09:00:00+00:00"}},
        cursors={"entry": {"delta": "token"}},
    )


def test_round_trip() -> None:
    """Everything survives serialisation, as JSON."""
    data = _full_data()
    stored = json.loads(json.dumps(data.as_dict()))
    loaded = ParcelsData.from_dict(stored)
    assert loaded.as_dict() == data.as_dict()
    parcel = loaded.parcels["p_test"]
    assert parcel.state == data.parcels["p_test"].state
    assert parcel.origins["man:p_test"].merchant == ""
    assert loaded.review["r1"].suggestion == data.review["r1"].suggestion
    assert loaded.review["r1"].fill
    assert loaded.trusted_domains() == ("example.com",)


def test_unreadable_entries_are_skipped(caplog: pytest.LogCaptureFixture) -> None:
    """One damaged record doesn't lose the others."""
    stored = _full_data().as_dict()
    stored["parcels"].append({"origins": []})
    stored["orders"] = "garbage"
    with caplog.at_level(logging.WARNING):
        loaded = ParcelsData.from_dict(stored)
    assert list(loaded.parcels) == ["p_test"]
    assert loaded.orders == {}
    assert "unreadable stored parcel" in caplog.text
    assert ParcelsData.from_dict(None) == ParcelsData()


# The sources 0.1.5 can read: it skips a whole parcel with any other.
SOURCES_0_1_5 = {"parser", "ai", "manual", "seventeentrack"}


def test_parcel_app_news_is_stored_so_older_releases_read_it() -> None:
    """The Parcel app's records are stored as 17TRACK's and read back as its own.

    A parcel with the Parcel app's news must survive going back to 0.1.5.
    """
    parcel = _parcel(
        _event(S.SHIPPED, at()),
        _event(S.IN_TRANSIT, at(hours=2), source=Source.PARCELAPP, origin="pa:1"),
        _event(S.IN_TRANSIT, at(hours=3), source=Source.SEVENTEENTRACK, origin="17t:2"),
        origins=(
            _origin(),
            _origin("pa:1", source=Source.PARCELAPP, time=at(hours=2), name="Lamp"),
            _origin("17t:2", source=Source.SEVENTEENTRACK, time=at(hours=3)),
        ),
    )
    stored = json.loads(json.dumps(parcel.as_dict()))
    assert {origin["source"] for origin in stored["origins"]} <= SOURCES_0_1_5
    assert {event["source"] for event in stored["events"]} <= SOURCES_0_1_5
    loaded = Parcel.from_dict(stored)
    assert loaded.origins["pa:1"].source is Source.PARCELAPP
    assert loaded.origins["17t:2"].source is Source.SEVENTEENTRACK
    assert [event.source for event in loaded.events] == [
        Source.PARSER,
        Source.PARCELAPP,
        Source.SEVENTEENTRACK,
    ]
    assert loaded.as_dict() == parcel.as_dict()
    assert loaded.state == parcel.state


def test_a_source_from_a_newer_release_reads_as_a_parser() -> None:
    """A record isn't lost because a newer release stored an unknown source."""
    stored = _full_data().as_dict()
    stored["parcels"][0]["origins"][0]["source"] = "newer"
    stored["parcels"][0]["events"][0]["source"] = "newer"
    stored["review"][0]["source"] = "newer"
    loaded = ParcelsData.from_dict(stored)
    parcel = loaded.parcels["p_test"]
    assert parcel.origins["o1"].source is Source.PARSER
    assert parcel.events[0].source is Source.PARSER
    assert loaded.review["r1"].source is Source.PARSER


def test_name_from_the_latest_origin_that_has_one() -> None:
    """A delivery only in the Parcel app is named after its description."""
    parcel = _parcel(
        origins=(
            _origin("pa:1", source=Source.PARCELAPP, name="Old name"),
            _origin("pa:2", source=Source.PARCELAPP, time=at(hours=1), name="Lamp"),
            _origin("o1", time=at(hours=2)),
        )
    )
    assert parcel.state.name == "Lamp"
    assert parcel.state.source is Source.PARSER
    assert _parcel().state.name is None
    only = _parcel(origins=(_origin("pa:1", source=Source.PARCELAPP, name="Lamp"),))
    assert only.state.source is Source.PARCELAPP


def test_sender_preferences() -> None:
    """Sender domains are case-insensitive."""
    data = ParcelsData()
    data.sender("Example.COM").ignored = True
    assert data.is_ignored("example.com")
    assert not data.is_ignored("other.example")
