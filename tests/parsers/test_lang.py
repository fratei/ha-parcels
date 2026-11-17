"""Tests for the language helpers."""

from __future__ import annotations

import pytest

from custom_components.parcels.parsers.lang import (
    DAY_AFTER_TOMORROW,
    LANGUAGES,
    MONTHS,
    MONTHS_BY_LANG,
    TODAY,
    TOMORROW,
    WEEKDAYS,
    WEEKDAYS_BY_LANG,
    detect_language,
    fold,
    fold_aligned,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Março", "marco"),
        ("ÜBERMORGEN", "ubermorgen"),
        ("terça-feira", "terca-feira"),
        ("Lieferung für Straße", "lieferung fur strasse"),
        ("Entrega estimada: miércoles", "entrega estimada: miercoles"),
        ("livraison prévue à 14h", "livraison prevue a 14h"),
        ("martedì", "martedi"),
    ],
)
def test_fold(text: str, expected: str) -> None:
    """Folding lowercases and strips accents."""
    assert fold(text) == expected


def test_fold_aligned_keeps_positions() -> None:
    """Every input character maps to exactly one output character."""
    text = "Straße · ﬁnal Março ÉTÉ\u00a0x"
    folded = fold_aligned(text)
    assert len(folded) == len(text)
    assert folded.startswith("stra")
    assert folded[text.index("Março") :].startswith("marco")
    assert folded[text.index("ÉTÉ") :].startswith("ete")


def test_tables_cover_every_language() -> None:
    """Months and weekdays exist for all seven languages."""
    assert set(MONTHS_BY_LANG) == set(LANGUAGES)
    assert set(WEEKDAYS_BY_LANG) == set(LANGUAGES)
    for months in MONTHS_BY_LANG.values():
        assert set(months.values()) == set(range(1, 13))
    for weekdays in WEEKDAYS_BY_LANG.values():
        assert set(weekdays.values()) == set(range(7))


@pytest.mark.parametrize(
    ("word", "month"),
    [
        ("novembro", 11),
        ("noviembre", 11),
        ("november", 11),
        ("marz", 3),
        ("fevrier", 2),
        ("dicembre", 12),
        ("mei", 5),
        ("nov", 11),
        ("dez", 12),
    ],
)
def test_months(word: str, month: int) -> None:
    """Folded month names and abbreviations of all languages are merged."""
    assert MONTHS[word] == month


@pytest.mark.parametrize(
    ("word", "weekday"),
    [
        ("terca-feira", 1),
        ("sexta", 4),
        ("sabado", 5),
        ("miercoles", 2),
        ("thursday", 3),
        ("donnerstag", 3),
        ("vendredi", 4),
        ("martedi", 1),
        ("zaterdag", 5),
    ],
)
def test_weekdays(word: str, weekday: int) -> None:
    """Folded weekday names of all languages are merged."""
    assert WEEKDAYS[word] == weekday


def test_relative_days() -> None:
    """Relative-day words are folded and the longest phrases come first."""
    assert {"hoje", "hoy", "today", "heute", "oggi", "vandaag"} <= set(TODAY)
    assert {"amanha", "manana", "tomorrow", "morgen", "demain", "domani"} <= set(
        TOMORROW
    )
    assert {"depois de amanha", "pasado manana", "ubermorgen", "overmorgen"} <= set(
        DAY_AFTER_TOMORROW
    )
    lengths = [len(word) for word in DAY_AFTER_TOMORROW]
    assert lengths == sorted(lengths, reverse=True)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "A sua encomenda foi enviada e está a caminho. Obrigado pela sua compra!",
            "pt",
        ),
        ("Tu pedido ha sido enviado y llegará pronto. Gracias por tu compra.", "es"),
        (
            "Your order has been shipped and is on its way. Thank you for your order!",
            "en",
        ),
        (
            "Ihre Bestellung wurde versandt und ist auf dem Weg zu Ihnen. Vielen Dank!",
            "de",
        ),
        (
            "Votre commande a été expédiée et elle est en route. Merci pour votre achat.",
            "fr",
        ),
        (
            "Il tuo ordine è stato spedito ed è in arrivo. Grazie per il tuo acquisto.",
            "it",
        ),
        (
            "Je bestelling is verzonden en is onderweg naar je. Bedankt voor je bestelling.",
            "nl",
        ),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    """Typical shipping sentences are recognised in every language."""
    assert detect_language(text) == expected


@pytest.mark.parametrize("text", ["", "RR123456785PT", "12/11/2026 10:00", "OK"])
def test_detect_language_unclear(text: str) -> None:
    """Too little text gives no language."""
    assert detect_language(text) is None
