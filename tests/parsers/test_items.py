"""Tests for comparing item titles."""

from __future__ import annotations

import pytest

from custom_components.parcels.parsers.items import (
    before_recommendations,
    drop_recommended,
    recommendations_start,
    same_item,
    unique_items,
)

ORDERED = "Livro de receitas da cozinha portuguesa, capa dura"
RECOMMENDED = [
    "Chávena de café EX200 para expresso",
    "Pilhas alcalinas AA, pack de 8",
    "Sacos do lixo 30 L, 50 unidades",
]


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (
            "Chávena de café EX200 para...",
            "Chavena de cafe ex200 para expresso",
            True,
        ),
        ("Papel higiénico Suave…", "PAPEL HIGIENICO SUAVE 12 rolos", True),
        ("2 x Tampa de vidro 24 cm", "Tampa de vidro 24 cm", True),
        ("Tampa...", "Tampa de vidro 24 cm", False),
        ("Tampa de vidro 24 cm", "Tampa de vidro 28 cm", False),
        ("...", "...", False),
    ],
)
def test_same_item(first: str, second: str, expected: bool) -> None:
    """Cut titles match the full one; short cuts and other sizes don't."""
    assert same_item(first, second) is expected
    assert same_item(second, first) is expected


def test_unique_items_keeps_longest_spelling_in_place() -> None:
    """A repeated title is listed once, at its first place, in full."""
    items = [
        "Tampa de vidro 24 cm...",
        "Toalhas de algodão",
        "tampa de vidro 24 cm, transparente",
        "Toalhas de algodao",
        "",
    ]

    assert unique_items(items) == [
        "tampa de vidro 24 cm, transparente",
        "Toalhas de algodão",
    ]


def _order_text(heading: str) -> str:
    """Return an order's text with a block of products under ``heading``."""
    return "\n".join(
        [
            "Encomenda n.º 406-1928374-5647382",
            ORDERED,
            "Quantidade: 1",
            heading,
            *RECOMMENDED,
        ]
    )


@pytest.mark.parametrize(
    "heading",
    [
        "Comprar de novo",
        "Comprar novamente",
        "Compra de nuevo",
        "Volver a comprar",
        "Buy again",
        "Erneut kaufen",
        "Acheter à nouveau",
        "Acquista di nuovo",
        "Opnieuw kopen",
        "Comprar de novo  Ver tudo \u203a",
        "Inspirado nas suas tendências de compra",
        "Inspirado en tus compras",
        "Recomendado para ti",
        "Recomendados para si",
        "Inspired by your shopping trends",
        "Recommended for you",
        "Customers who bought this item also bought",
        "Inspiriert von Ihren Einkäufen",
        "Kunden, die diesen Artikel gekauft haben, kauften auch",
        "Inspiré par vos achats",
        "Ispirato ai tuoi acquisti",
        "Geïnspireerd door je aankopen",
        "Ver más  Recomendados para ti",
    ],
)
def test_cuts_at_recommendations_heading(heading: str) -> None:
    """The text ends before the recommendations, in every language."""
    text = _order_text(heading)

    assert before_recommendations(text).rstrip("\n").endswith("Quantidade: 1")
    assert recommendations_start(text) == text.index(heading)


def test_no_heading_keeps_the_text() -> None:
    """Without a heading the text is whole."""
    text = "\n".join([ORDERED, "Quantidade: 1", "Recomendamos que guarde a fatura."])

    assert recommendations_start(text) is None
    assert before_recommendations(text) == text


def test_heading_inside_a_long_line_is_text() -> None:
    """A heading phrase in the middle of a long sentence isn't a heading."""
    line = "Obrigado pela sua compra; inspirado nas suas sugestões, melhorámos a loja."

    assert recommendations_start(f"{ORDERED}\n{line}") is None


def test_buy_again_buttons_are_no_heading() -> None:
    """A "Buy again" button under each item isn't a heading."""
    text = "\n".join([ORDERED, "Comprar de novo", RECOMMENDED[0], "Comprar de novo"])

    assert recommendations_start(text) is None


def test_buy_again_link_is_a_button() -> None:
    """A "Buy again" that is the text of an item's link isn't a heading."""
    text = "\n".join([ORDERED, "Buy it again"])

    assert recommendations_start(text, buttons=["Buy it again"]) is None
    assert recommendations_start(text) == len(ORDERED) + 1


def test_buy_again_in_a_sentence_is_no_heading() -> None:
    """ "Buy again" with more words on its line isn't a heading."""
    text = "\n".join([ORDERED, "Comprar de novo este artigo com 10% de desconto"])

    assert recommendations_start(text) is None


def test_drop_recommended_items() -> None:
    """Items written only under the heading are dropped; others stay."""
    text = _order_text("Inspirado nas suas compras")
    items = [ORDERED, "Chávena de café EX200 para...", "Not in the e-mail", ORDERED]

    assert drop_recommended(items, text) == [ORDERED, "Not in the e-mail", ORDERED]


def test_drop_recommended_keeps_items_also_ordered() -> None:
    """An ordered item that is recommended again stays."""
    text = _order_text("Comprar de novo") + f"\n{ORDERED}"

    assert drop_recommended([ORDERED, *RECOMMENDED], text) == [ORDERED]
