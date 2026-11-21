"""Tests for tracking-number validation, detection and URLs."""

from __future__ import annotations

from time import perf_counter

import pytest

from custom_components.parcels.parsers.tracking import (
    FALLBACK_URL,
    URL_TEMPLATES,
    TrackingMatch,
    amazon_logistics_number,
    check_digit_ok,
    detect_carrier,
    find_tracking_numbers,
    is_s10,
    normalize_tracking_number,
    numbers_from_url,
    s10_check_digit,
    tracking_url,
    ups_check_digit_ok,
    validate_tracking_number,
)

UPS = "1Z999AA10123456784"
DHL_SSCC = "00340434161094015902"


def _found(text: str, carrier: str | None = None) -> list[tuple[str, str | None, bool]]:
    return [
        (m.number, m.carrier, m.validated) for m in find_tracking_numbers(text, carrier)
    ]


def _from_url(url: str) -> list[tuple[str, str | None, bool]]:
    return [(m.number, m.carrier, m.validated) for m in numbers_from_url(url)]


def test_normalize_tracking_number() -> None:
    """Spaces, dashes, dots and invisible characters go; letters are upper."""
    assert normalize_tracking_number(" rr 123-456.785 pt ") == "RR123456785PT"
    assert normalize_tracking_number("1z\u00a0999\u00adaa1") == "1Z999AA1"


def test_s10_check_digit() -> None:
    """UPU S10 check digits."""
    assert s10_check_digit("12345678") == 5
    assert s10_check_digit("06948388") == 6


@pytest.mark.parametrize(
    "number",
    [
        "RR123456785PT",
        "RB123456785GB",
        "DA069483886PT",
        "CD123456785BE",
        "rr123456785pt",
    ],
)
def test_is_s10_valid(number: str) -> None:
    """Valid S10 numbers, also in lowercase."""
    assert is_s10(number)


@pytest.mark.parametrize(
    "number", ["RB123456786US", "RR12345678PT", "RR123456785P1", "R1123456785PT", ""]
)
def test_is_s10_invalid(number: str) -> None:
    """A wrong check digit or shape is not S10."""
    assert not is_s10(number)


def test_ups_check_digit() -> None:
    """UPS 1Z numbers, also spaced out."""
    assert ups_check_digit_ok(UPS)
    assert ups_check_digit_ok("1Z 999 AA1 01 2345 6784")
    assert not ups_check_digit_ok("1Z999AA10123456785")
    assert not ups_check_digit_ok("1Z999AA1012345678")


@pytest.mark.parametrize("number", ["3318810025", "73891051146", "8487135506"])
def test_dhl_express_check_digit(number: str) -> None:
    """DHL Express mod-7 check digits count only for DHL."""
    assert check_digit_ok(number, "dhl")
    assert validate_tracking_number(number, "dhl")
    assert not check_digit_ok(number)
    assert detect_carrier(number) is None


@pytest.mark.parametrize("number", ["3318810010", "3318810034"])
def test_dhl_express_bad_check_digit(number: str) -> None:
    """A DHL Express waybill with a wrong check digit is rejected."""
    assert not check_digit_ok(number, "dhl")
    assert not validate_tracking_number(number, "dhl")


def test_other_check_digits() -> None:
    """FedEx needs the carrier; SSCC and S10 check themselves."""
    assert check_digit_ok("986578788855", "fedex")
    assert not check_digit_ok("986578788855")
    assert check_digit_ok("041441760228964", "fedex")
    assert check_digit_ok(DHL_SSCC)
    assert check_digit_ok("RR123456785PT")
    assert check_digit_ok(UPS)
    assert not check_digit_ok("ABCDEF12345")


@pytest.mark.parametrize(
    ("number", "carrier", "expected"),
    [
        ("RR123456785PT", None, True),
        ("RR123456785PT", "ctt", True),
        ("RR123456785PT", "dpd", False),
        ("RB123456786US", None, False),
        (UPS, "ups", True),
        (UPS, "dhl", False),
        ("1Z999AA10123456785", None, False),
        ("01234567890123", "dpd", True),
        ("0123456789012", "dpd", False),
        ("12345678901", "gls", True),
        ("3SABCD1234567", "postnl", True),
        ("3SAB1234567", "postnl", False),
        ("JJD000390007882452811", "dhl", True),
        ("ABC12345678", "other", True),
        ("ABCDEFGHIJ", None, False),
        ("", None, False),
        ("1" * 41, None, False),
    ],
)
def test_validate_tracking_number(
    number: str, carrier: str | None, expected: bool
) -> None:
    """Formats and check digits per carrier; length and charset otherwise."""
    assert validate_tracking_number(number, carrier) is expected


@pytest.mark.parametrize(
    ("number", "carrier"),
    [
        ("RR123456785PT", "ctt"),
        ("DA069483886PT", "ctt_expresso"),
        ("RR123456785ES", "correos"),
        ("RR123456785FR", "la_poste"),
        ("CC123456785FR", "colissimo"),
        ("RR123456785DE", "deutsche_post"),
        ("RB123456785GB", "royal_mail"),
        ("RR123456785IT", "poste_italiane"),
        ("RR123456785NL", "postnl"),
        ("CD123456785BE", "bpost"),
        ("RR123456785US", "usps"),
        ("RR123456785CN", None),
        (UPS, "ups"),
        ("JJD000390007882452811", "dhl"),
        ("JVGL0123456789", "dhl"),
        (DHL_SSCC, "dhl"),
        ("TBA123456789012", "amazon"),
        ("3SABCD1234567", "postnl"),
        ("LP00123456789012", "cainiao"),
        ("YT1234567890123456", "yunexpress"),
        ("VGS1234ABCD", "vinted_go"),
        ("01234567890123", None),
    ],
)
def test_detect_carrier(number: str, carrier: str | None) -> None:
    """Formats that name their carrier on their own."""
    assert detect_carrier(number) == carrier


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        ("TBA123456789012", True),
        ("tba-1234 5678 9012", True),
        ("TBA12345678901", False),
        ("AB1234567890", False),
        ("17112345671234567", False),
        (UPS, False),
        ("", False),
        (None, False),
    ],
)
def test_amazon_logistics_number(number: str | None, expected: bool) -> None:
    """Only Amazon Logistics' own format proves Amazon delivers a parcel."""
    assert amazon_logistics_number(number) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tracking number: 1Z 999 AA1 01 2345 6784", [(UPS, "ups", True)]),
        ("Your UPS number is 1Z-999-AA1-01-2345-6784.", [(UPS, "ups", True)]),
        ("Objeto RR 123 456 785 PT enviado", [("RR123456785PT", "ctt", True)]),
        ("N.º de objeto: DA069483886PT", [("DA069483886PT", "ctt_expresso", True)]),
        ("Sendungsnummer: 00340434161094015902", [(DHL_SSCC, "dhl", True)]),
        ("Your Amazon order TBA123456789012", [("TBA123456789012", "amazon", True)]),
        ("Vinted Go: VGS1234ABCD", [("VGS1234ABCD", "vinted_go", True)]),
        ("DHL Express waybill 3318810025", [("3318810025", "dhl", True)]),
        ("DPD parcel number: 01234567890123", [("01234567890123", "dpd", False)]),
        (
            "Your DPD Predict parcel 0123 4567 8901 23 arrives tomorrow",
            [("01234567890123", "dpd", False)],
        ),
        ("GLS tracking 12345678901", [("12345678901", "gls", False)]),
        ("Nacex expedición 0402/1234567", [("0402/1234567", "nacex", False)]),
        ("Seguimiento SEUR: 12345678", [("12345678", "seur", False)]),
        ("Tracking number: ABCDEF12345", [("ABCDEF12345", None, False)]),
    ],
)
def test_find_tracking_numbers(
    text: str, expected: list[tuple[str, str | None, bool]]
) -> None:
    """Numbers are found with spaces and dashes, and with their carrier."""
    assert _found(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Order 123-1234567-1234567 has shipped",
        "Order number: 12345678901",
        "Pedido n.º 123456789012 enviado com CTT",
        "Bestellnummer 4012345678",
        "Invoice 2026-0001234",
        "Ref. 2026111712345678",
        "Call us on +351 912 345 678 or 213 456 789",
        "Telefone: 912345678",
        "Customer service 800 20 30 40",
        "Total: 1234567890 €",
        "IBAN PT50 0002 0123 1234 5678 9015 4",
        "Delivered on 18/11/2026 at 13:45",
        "Rua Exemplo 1, 1000-001 Lisboa",
        "Waybill 3318810025",
        "Order #1001 tracking ABC123",
        "Tracking number RB123456786US",
        "Tracking number 1Z999AA10123456785",
        "Track it: https://shop.example/account?session=ABCDEF1234567890ABCDEF",
        "Write to tracking12345678@example.com",
        "",
    ],
)
def test_find_tracking_numbers_false_positives(text: str) -> None:
    """Order numbers, phones, prices, IBANs, dates, postcodes and links."""
    assert _found(text) == []


@pytest.mark.parametrize(
    "run",
    ["26-" * 20_000, "." * 60_000, "ab" * 30_000],
    ids=["dates", "dots", "word"],
)
def test_long_run_without_an_address_is_read_once(run: str) -> None:
    """A long run of letters, digits, dots or hyphens with no "@" stays fast.

    Blanking e-mail addresses used to read such a run again from each of its
    characters: about 7 seconds for 60,000 characters.
    """
    start = perf_counter()
    found = _found(f"{run}\nTracking number RR123456785PT")
    assert perf_counter() - start < 2
    assert found == [("RR123456785PT", "ctt", True)]


def test_find_with_carrier_hint() -> None:
    """The carrier passed by the caller is used for its formats."""
    assert _found("Parcel number: 01234567890123", "dpd") == [
        ("01234567890123", "dpd", False)
    ]
    assert _found("Sendungsnummer 3318810025", "dhl") == [("3318810025", "dhl", True)]


def test_find_orders_validated_first_and_deduplicates() -> None:
    """Validated numbers come first; repeated numbers appear once."""
    text = (
        "Tracking number ABCDEF12345. Also RR123456785PT and RR 123 456 785 PT,"
        f" plus {UPS}"
    )
    assert _found(text) == [
        ("RR123456785PT", "ctt", True),
        (UPS, "ups", True),
        ("ABCDEF12345", None, False),
    ]
    assert all(isinstance(m, TrackingMatch) for m in find_tracking_numbers(text))


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://www.ups.com/track?loc=en_US&tracknum=1Z999AA10123456784",
            [(UPS, "ups", True)],
        ),
        (
            "https://www.ctt.pt/feapl_2/app/open/objectSearch/objectSearch.jspx"
            "?objects=RR123456785PT",
            [("RR123456785PT", "ctt", True)],
        ),
        (
            "https://t.17track.net/en#nums=RR123456785PT",
            [("RR123456785PT", "ctt", True)],
        ),
        (
            "https://click.store.example/ls/click?upn=https%3A%2F%2Fwww.ups.com"
            "%2Ftrack%3Ftracknum%3D1Z999AA10123456784",
            [(UPS, "ups", True)],
        ),
        (
            "https://www.dhl.de/de/privatkunden/pakete-empfangen/verfolgen.html"
            "?piececode=00340434161094015902",
            [(DHL_SSCC, "dhl", True)],
        ),
        (
            "https://tracking.dpd.de/status/en_US/parcel/01234567890123",
            [("01234567890123", "dpd", False)],
        ),
        (
            "https://www.seur.com/livetracking/?segOnlineIdentificador=12345678",
            [("12345678", "seur", False)],
        ),
        ("https://gls-group.com/track/12345678901", [("12345678901", "gls", False)]),
        (
            "https://shop.example/x?trackingNumber=ABC123456789",
            [("ABC123456789", None, False)],
        ),
    ],
)
def test_numbers_from_url(
    url: str, expected: list[tuple[str, str | None, bool]]
) -> None:
    """Tracking parameters anywhere; paths and generic parameters on carriers."""
    assert _from_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://shop.example/orders/12345678901234?key=abcdef",
        "https://shop.example/account?session=ABCDEF1234567890ABCDEF",
        "https://www.amazon.es/progress-tracker/package/ref=pe_1?_encoding=UTF8"
        "&orderId=123-1234567-1234567&shipmentId=AbCdEf123",
        "https://shop.example/x?trackingNumber=RB123456786US",
        "mailto:alex@example.com",
        "javascript:alert(1)",
        "",
        "https://[broken",
    ],
)
def test_numbers_from_url_ignores_other_links(url: str) -> None:
    """Shop pages, order links, session IDs and odd links give nothing."""
    assert _from_url(url) == []


@pytest.mark.parametrize(
    ("carrier", "number", "expected"),
    [
        ("ups", UPS, f"https://www.ups.com/track?tracknum={UPS}"),
        (
            "ctt",
            "RR 123 456 785 PT",
            "https://www.ctt.pt/feapl_2/app/open/objectSearch/objectSearch.jspx"
            "?objects=RR123456785PT",
        ),
        ("gls", "123 45678901", "https://gls-group.com/track/12345678901"),
        ("postnl", "3SABCD1234567", "https://t.17track.net/en#nums=3SABCD1234567"),
        (None, "RR123456785PT", "https://t.17track.net/en#nums=RR123456785PT"),
        ("nacex", "0402/1234567", "https://t.17track.net/en#nums=0402%2F1234567"),
        ("unknown", "A/B C&D", "https://t.17track.net/en#nums=A%2FBC%26D"),
    ],
)
def test_tracking_url(carrier: str | None, number: str, expected: str) -> None:
    """Official templates with URL-encoded numbers, else 17TRACK."""
    assert tracking_url(carrier, number) == expected


def test_url_templates_are_https() -> None:
    """Every template is an https URL with one number placeholder."""
    assert FALLBACK_URL.startswith("https://")
    for template in URL_TEMPLATES.values():
        assert template.startswith("https://")
        assert template.count("{n}") == 1


# --- Paack ---------------------------------------------------------------------

# Made-up Paack order IDs (nine letters and digits in mixed case, "_" and the
# package number) and a made-up label barcode.
PAACK_ID = "Qm7Rt2Kp9_2"
PAACK_LETTERS = "AbCdEfGhJ_12"
PAACK_BARCODE = "534000077712340056"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (PAACK_ID, PAACK_ID),
        (" Qm7Rt2Kp9 _2\u200b", PAACK_ID),
        ("qm7rt2kp9_12", "qm7rt2kp9_12"),
        ("Qm7Rt2Kp9", "QM7RT2KP9"),
        ("Qm7Rt2Kp9_123", "QM7RT2KP9_123"),
        ("ab-12.cd 34", "AB12CD34"),
    ],
)
def test_normalize_keeps_paack_ids(value: str, expected: str) -> None:
    """Paack's order IDs keep their case and package number; others go upper."""
    assert normalize_tracking_number(value) == expected


@pytest.mark.parametrize(
    ("number", "carrier", "valid"),
    [
        (PAACK_ID, "paack", True),
        (PAACK_LETTERS, "paack", True),
        ("qm7rt2kp9_2", "paack", True),
        (PAACK_BARCODE, "paack", True),
        ("PK7311804926", "paack", True),
        (PAACK_ID, None, False),
        (PAACK_ID, "other", False),
        (PAACK_ID, "gls", False),
        (PAACK_ID, "seur", False),
        ("Qm7Rt2Kp_2", "paack", False),
        ("Qm7Rt2Kp9_123", "paack", False),
        ("Qm7Rt2Kp9_x", "paack", False),
    ],
)
def test_validate_paack_numbers(number: str, carrier: str | None, valid: bool) -> None:
    """Paack's order IDs are only valid for Paack; its barcode is valid too."""
    assert validate_tracking_number(number, carrier) is valid


def test_detect_paack_barcode() -> None:
    """The 5340 barcode names Paack; the order ID's shape alone doesn't."""
    assert detect_carrier(PAACK_BARCODE) == "paack"
    assert detect_carrier("5340000777123400") is None
    assert detect_carrier(PAACK_ID) is None


@pytest.mark.parametrize(
    "text",
    [
        f"Código Paack: {PAACK_ID}",
        f"Paack {PAACK_ID}",
        f"Your Paack tracking number is {PAACK_ID}.",
    ],
)
def test_find_paack_ids_next_to_paack(text: str) -> None:
    """Next to Paack's name, its order ID is found as written."""
    assert _found(text) == [(PAACK_ID, "paack", False)]
    assert _found(text, "paack") == [(PAACK_ID, "paack", False)]


def test_find_paack_ids_in_paack_mail() -> None:
    """In a Paack e-mail a tracking word is enough, unless another carrier is named."""
    assert _found(f"Tracking number: {PAACK_ID}", "paack") == [
        (PAACK_ID, "paack", False)
    ]
    assert _found(f"GLS tracking number: {PAACK_ID}", "paack") == []


@pytest.mark.parametrize(
    ("text", "carrier"),
    [
        (f"Tracking number: {PAACK_ID}", None),
        (f"Tracking number: {PAACK_ID}", "gls"),
        (f"Paack file report_{PAACK_ID}", None),
        (f"Paack code {PAACK_ID}_7", None),
        (f"Paack code {PAACK_ID}.pdf", None),
        (f"{PAACK_ID} is on its way", "paack"),
        (f"Order number: {PAACK_ID}", None),
    ],
)
def test_paack_ids_need_paack(text: str, carrier: str | None) -> None:
    """The bare shape, or a tracking word without Paack's name, isn't enough."""
    assert _found(text, carrier) == []


def test_find_paack_barcode() -> None:
    """The barcode is found after a tracking word, and named Paack."""
    assert _found(f"Tracking ID: {PAACK_BARCODE}") == [(PAACK_BARCODE, "paack", False)]


@pytest.mark.parametrize(
    "url",
    [
        f"https://paack.co/shipments/tracking/order?tracking_number={PAACK_ID}"
        "&postal_code=1000-001",
        f"https://mydeliveries.paack.app/tracking?tracking_number={PAACK_ID}"
        "&postal_code=28001",
        "https://paack.co/shipments/preferences/timeslot?email=alex%40example.com"
        f"&phone=%2B351900000000&order_id=a1b2&postal_code=1000-001"
        f"&tracking_number={PAACK_ID}",
    ],
)
def test_numbers_from_paack_links(url: str) -> None:
    """Paack's links give the order ID as written, from tracking_number only."""
    assert _from_url(url) == [(PAACK_ID, "paack", False)]


@pytest.mark.parametrize(
    "url",
    [
        f"https://shop.example/track?tracking_number={PAACK_ID}",
        f"https://t.17track.net/en#nums={PAACK_ID}",
        f"https://paack.co/shipments/tracking/{PAACK_ID}",
        f"https://paack.co/shipments/tracking/order?id={PAACK_ID}",
        "https://paack.co/shipments/timeslot/direct/QWERTY12345ASDFG67890ZX",
        "https://paack.co/shipments/address/reverse/AB12CD34EF56GH78",
        "https://paack.co/shipments/tracking/order?tracking_number=x&postal_code=28001",
    ],
)
def test_paack_links_without_order_id(url: str) -> None:
    """Other sites, other parameters and Paack's opaque tokens give nothing."""
    assert _from_url(url) == []


def test_paack_tracking_url() -> None:
    """Paack's page needs a postcode: the link is its search page."""
    url = tracking_url("paack", PAACK_ID)
    assert url == "https://paack.co/shipments/tracking"
    assert tracking_url("paack", PAACK_BARCODE) == url


@pytest.mark.parametrize(
    "text",
    [
        f"Order number: {PAACK_ID}",
        f"Order No. {PAACK_ID}",
        f"Número de pedido: {PAACK_ID}",
        f"N.º de pedido: {PAACK_ID}",
        f"Núm. de pedido: {PAACK_ID}",
        f"Número da encomenda: {PAACK_ID}",
        f"Numéro de commande : {PAACK_ID}",
        f"N° de commande : {PAACK_ID}",
        f"Numero d'ordine: {PAACK_ID}",
        f"N. ordine: {PAACK_ID}",
        f"Número de pedido\n{PAACK_ID}",
        f"NÚMERO DE PEDIDO:\n\n{PAACK_ID}",
    ],
)
def test_find_paack_ids_after_footer_label(text: str) -> None:
    """In a Paack e-mail, the order number in its footer is Paack's ID."""
    assert _found(text, "paack") == [(PAACK_ID, "paack", False)]
    assert _found(text) == []
    assert _found(text, "gls") == []


@pytest.mark.parametrize(
    "text",
    [
        f"GLS order number: {PAACK_ID}",
        f"Order number: 12345\n{PAACK_ID}",
        f"Número de pedido: ver abaixo\nReferência interna: {PAACK_ID}",
        f"Order number in your account. Reference {PAACK_ID}",
    ],
)
def test_footer_label_must_be_next_to_paack_id(text: str) -> None:
    """The label must be the one right before the ID, and not name another carrier."""
    assert _found(text, "paack") == []
