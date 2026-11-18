"""Tests for reading delivery PINs, one-time passwords and pickup codes."""

from __future__ import annotations

import pytest

from custom_components.parcels.parsers.codes import (
    CODE_LABELS,
    code_spans,
    compact_code,
    find_code,
    has_code_label,
    mask_codes,
)

ORDER = "405-3829174-6627315"
SSCC = "00340434618273591202"
S10 = "RR123456785PT"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Portuguese.
        (f"O seu código de entrega para a encomenda {SSCC} é 4821.", "4821"),
        ("PIN de entrega: 4821", "4821"),
        ("Indique o código PIN 5937 ao estafeta.", "5937"),
        ("Código de levantamento:\n\n482913\n", "482913"),
        ("Código de recolha: 7KD3Q9", "7KD3Q9"),
        ("Palavra-passe única: 739 215", "739215"),
        ("O código de entrega da encomenda 4821 é 1234.", "1234"),
        # Spanish.
        ("Tu código de entrega es 5937.", "5937"),
        ("Código de recogida: 7KD3Q9", "7KD3Q9"),
        ("Contraseña de un solo uso (OTP): 482193", "482193"),
        ("Tu código de un solo uso es: 482193", "482193"),
        ("Facilita el código de entrega al repartidor: 482193", "482193"),
        # English.
        (f"Your delivery code for order {ORDER} is 4821", "4821"),
        ("Your one-time password (OTP) is 482193.", "482193"),
        (f"Delivery PIN for parcel {S10}: 4821", "4821"),
        ("Pick-up code: 7KD3Q9", "7KD3Q9"),
        ("Your collection code\n\n   7KD3Q9   \n", "7KD3Q9"),
        ("Share this delivery code with your driver: 482193", "482193"),
        # German.
        ("Ihr Zustellcode lautet: 4821", "4821"),
        ("Abholcode 519384", "519384"),
        ("Einmalpasswort: 73A9K2", "73A9K2"),
        ("Abholcode für Sendung Nr. 4711: 519384", "519384"),
        # French.
        ("Votre code de livraison est 4821.", "4821"),
        ("Code de retrait : 519384", "519384"),
        ("Code à usage unique : 482193", "482193"),
        ("Code de livraison pour la commande n° 30021 : 519384", "519384"),
        # Italian.
        ("Il codice di consegna è 4821.", "4821"),
        ("Codice di ritiro: 519384", "519384"),
        ("Codice monouso: 482193", "482193"),
        ("Codice di ritiro per la spedizione n. 30021: 519384", "519384"),
        # Dutch.
        ("Je bezorgcode is 4821.", "4821"),
        ("Ophaalcode: 519384", "519384"),
        ("Eenmalige code: 482193", "482193"),
        ("Bezorgcode voor bestelling 77012: 4821", "4821"),
    ],
)
def test_reads_labelled_code(text: str, expected: str) -> None:
    """A code right after its label is read in all seven languages."""
    assert find_code(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Código de seguimento: PK7311805018",
        "Usa el código APP15 para obtener un 15% de descuento.",
        f"Tracking code: {S10}",
        "Entrega em 24h, sem custos.",
        "Delivery code: show it to the courier.",
        f"Delivery code: {ORDER}",
        f"Delivery code: {S10}",
        "Código de entrega: 12/11/2026",
        "Delivery PIN: 10kg",
        "Código de entrega: 19,99 €",
        "Pickup code:\n7KD3Q9 is valid until Friday",
        "Código postal: 1000",
        "Code: 482913",
        "Unlock code: 482913",
        "Código de entrega a las 14:30 horas",
        "Partilhe o código de entrega com o estafeta quando ele chegar.",
        "Receberá o código de entrega por SMS no dia 20.",
        "Your delivery code will be sent on 20 November.",
        "Der Zustellcode wird per SMS gesendet.",
        "Votre code de livraison sera communiqué par SMS.",
    ],
)
def test_ignores_what_is_not_a_code(text: str) -> None:
    """Numbers, words, prices, dates and unlabelled values are no codes."""
    assert find_code(text) is None


@pytest.mark.parametrize(
    "text", ["Code: 482913", "Unlock code: 482913", "Código de abertura: 482913"]
)
def test_locker_labels_count_for_pickup(text: str) -> None:
    """Locker labels and a bare "Code:" count for a parcel to collect."""
    assert find_code(text, locker=True) == "482913"


@pytest.mark.parametrize(
    "text",
    [
        "Tracking Code: 4821",
        "Order code: 482193",
        "Parcel code: 482193",
        "Booking reference code: 482193",
    ],
)
def test_bare_code_label_naming_another_code(text: str) -> None:
    """A bare "Code:" after a tracking or order word names that number."""
    assert find_code(text, locker=True) is None
    assert find_code(f"Your parcel is ready.\n{text}\nCode: 519384", locker=True) == (
        "519384"
    )


def test_skips_values_equal_to_a_number() -> None:
    """A value equal to a tracking or an order number is never the code."""
    text = "Order 48213: your delivery code is 48213."

    assert find_code(text, exclude=["48213"]) is None
    assert find_code(text, exclude=["48-213"]) is None


def test_skips_to_the_next_label_after_an_excluded_value() -> None:
    """The next label's value is read when the first equals a number."""
    text = "Delivery code: 4821\nCódigo de entrega: 5937"

    assert find_code(text, exclude=["4821"]) == "5937"


def test_never_reads_a_url() -> None:
    """Codes in links are not read."""
    assert find_code("Delivery code: https://example.com/c/4821") is None


def test_has_code_label() -> None:
    """Delivery code labels are found; postal codes are not labels."""
    assert has_code_label("O seu Código de Entrega")
    assert has_code_label("Ihr ZUSTELLCODE")
    assert not has_code_label("Código postal 1000-001")


def test_labels_cover_all_languages() -> None:
    """Every supported language has its labels."""
    assert set(CODE_LABELS) == {"pt", "es", "en", "de", "fr", "it", "nl"}


def test_compact_code() -> None:
    """Spaces, dashes and "#" are not part of a code."""
    assert compact_code("739 215") == "739215"
    assert compact_code("#7kd-3q9") == "7KD3Q9"


def test_mask_codes_blanks_the_code_only() -> None:
    """Masking blanks the code and keeps the numbers and the offsets."""
    text = f"Objeto {S10}, encomenda {ORDER}.\nCódigo de entrega: 4821\n"
    masked = mask_codes(text)

    assert masked == text.replace(": 4821", ":     ")
    assert code_spans(text) == [(text.index("4821"), text.index("4821") + 4)]


def test_mask_codes_blanks_a_spaced_code() -> None:
    """Both halves of "739 215" are blanked."""
    assert mask_codes("OTP: 739 215.") == "OTP:        ."


def test_mask_codes_keeps_text_without_codes() -> None:
    """Text without a code comes back unchanged."""
    text = f"O seu objeto {S10} está em distribuição."

    assert mask_codes(text) == text
    assert code_spans(text) == []
