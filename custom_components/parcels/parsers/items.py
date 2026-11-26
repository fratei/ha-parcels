"""Item titles: compare the product names that e-mails list.

Shops cut long titles short ("Chávena de café EX200 para..."), and the same
item comes back with other capitals, accents or punctuation, so titles are
compared folded, and a cut title matches the full one.

Shops also list products they recommend under the order ("Buy again",
"Inspirado en tus compras"); the text from such a heading on doesn't hold
ordered items.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
import re
from typing import Final

from .lang import fold

# A title cut short must keep this many characters to match a longer one.
MIN_PREFIX_CHARS = 12

_QUANTITY_RE = re.compile(r"^\s*\d{1,3}\s*[x\u00d7]\s+", re.IGNORECASE)
_NOT_WORD_RE = re.compile(r"[\W_]+")


def item_key(title: str) -> str:
    """Return a title as compared: folded, words only, no leading quantity.

    ``"2 x Água Fresca…"`` -> ``"agua fresca"``.
    """
    text = _QUANTITY_RE.sub("", title)
    return _NOT_WORD_RE.sub(" ", fold(text)).strip()


def same_key(first_key: str, second_key: str) -> bool:
    """Return True when two keys from ``item_key`` name the same item.

    A key cut short matches the full one when it keeps at least
    ``MIN_PREFIX_CHARS`` characters.
    """
    if not first_key or not second_key:
        return False
    if first_key == second_key:
        return True
    short, full = sorted((first_key, second_key), key=len)
    return len(short) >= MIN_PREFIX_CHARS and full.startswith(short)


def same_item(first: str, second: str) -> bool:
    """Return True when two titles name the same item (see ``same_key``)."""
    return same_key(item_key(first), item_key(second))


def unique_items(items: Iterable[str]) -> list[str]:
    """Drop repeated titles; the longest spelling takes the place of the first."""
    kept: list[str] = []
    for item in items:
        if not item_key(item):
            continue
        for index, existing in enumerate(kept):
            if same_item(existing, item):
                if len(item_key(item)) > len(item_key(existing)):
                    kept[index] = item
                break
        else:
            kept.append(item)
    return kept


# --- Placeholders ------------------------------------------------------------

# What an AI writes for a product it can't name ("Item 1", "Artigo 2 de 3",
# "Unknown item", "Product name"): no product, so never an item. Folded
# words, as item_key() gives them.
_PLACEHOLDER_NOUNS = (
    "items?|itens|artigos?|articulos?|articles?|artikel(?:en)?|articol[oi]"
    "|produtos?|productos?|products?|produits?|prodott[oi]|produkte?"
    "|objetos?|objets?|oggett[oi]"
    "|packages?|parcels?|encomendas?|pacotes?|paquetes?|pakete?|pakket(?:ten)?"
    "|colis|pacc(?:o|hi)"
)
_PLACEHOLDER_UNKNOWN = (
    "unknown|unnamed|unspecified|not specified|not available|undefined"
    "|n a|na|none|null|nil"
    "|desconhecid[oa]s?|nao especificad[oa]|sem nome"
    "|desconocid[oa]s?|no especificad[oa]|sin nombre"
    "|unbekannte[rs]?|inconnue?s?|sconosciut[oi]|onbekende?"
)
_PLACEHOLDER_NUMBER = (
    r"(?:(?:no|n o|nr|n|num|number|numero|nummer|nro) )?(?:\d{1,3}|[a-z])"
)
_PLACEHOLDER_OF = r"(?:(?:of|out of|de|do|da|del|von|di|van|sur) )?\d{1,3}"
_PLACEHOLDER_RE = re.compile(
    rf"(?:\d{{1,3}} )?(?:(?:{_PLACEHOLDER_UNKNOWN}) )?(?:{_PLACEHOLDER_NOUNS})"
    rf"(?: (?:{_PLACEHOLDER_UNKNOWN}|name|title|description))?"
    rf"(?: {_PLACEHOLDER_NUMBER}(?: {_PLACEHOLDER_OF})?)?"
    rf"|{_PLACEHOLDER_UNKNOWN}"
    r"|(?:nome|descricao|titulo) d[oa] (?:produto|artigo|item)"
    r"|(?:nombre|descripcion|titulo) del (?:producto|articulo)"
    r"|(?:produkt|artikel)(?:name|bezeichnung)"
    r"|(?:nom|description) (?:du produit|de l article)"
    r"|(?:nome|descrizione) (?:del prodotto|dell articolo)"
    r"|(?:product|artikel)naam"
)


def is_placeholder_item(title: str) -> bool:
    """Return True for a title that stands for a product without naming it.

    ``"Item 1"``, ``"Artigo #2 de 3"``, ``"2 items"``, ``"Unknown item"``,
    ``"N/A"`` and ``"Product name"`` are; ``"Article de sport"`` and
    ``"Item 1: Black dress"`` aren't.
    """
    return _PLACEHOLDER_RE.fullmatch(item_key(title)) is not None


# --- Recommendations ---------------------------------------------------------

# Headings of the products a shop recommends under the order ("Inspired by
# your shopping trends", "Customers who bought this also bought"): the
# products below them weren't ordered. Folded words only; a heading starts
# its line, or is on a short line of its own.
RECOMMENDATION_HEADINGS: Final[tuple[str, ...]] = (
    # English.
    "recommended for you",
    "recommended based on",
    "recommended items",
    "recommendations for you",
    "top picks for you",
    "picked for you",
    "inspired by your",
    "customers who bought",
    "customers who viewed",
    "customers also bought",
    "frequently bought together",
    "you might also like",
    "you may also like",
    "related to items you",
    "related to your purchases",
    "deals related to your",
    "more items to consider",
    # Portuguese.
    "recomendado para si",
    "recomendados para si",
    "recomendado para voce",
    "recomendados para voce",
    "recomendacoes para si",
    "recomendacoes para voce",
    "sugestoes para si",
    "sugestoes para voce",
    "produtos recomendados",
    "artigos recomendados",
    "inspirado nas suas",
    "inspirados nas suas",
    "inspirado no seu",
    "inspirado nos seus",
    "inspirado pelas suas",
    "inspirado pelo seu",
    "inspirado em suas",
    "inspirado em seu",
    "os clientes que compraram",
    "clientes que compraram",
    "clientes que viram",
    "tambem pode gostar",
    "talvez tambem goste",
    "relacionado com artigos",
    "relacionados com artigos",
    "relacionado com os artigos",
    "relacionados com os artigos",
    "ofertas relacionadas com",
    # Spanish.
    "recomendado para ti",
    "recomendados para ti",
    "recomendado para usted",
    "recomendaciones para ti",
    "productos recomendados",
    "articulos recomendados",
    "inspirado en tus",
    "inspirados en tus",
    "inspirado en tu",
    "inspirado por tus",
    "los clientes que compraron",
    "los clientes que vieron",
    "tambien te puede interesar",
    "tambien te podria gustar",
    "relacionado con articulos",
    "relacionados con articulos",
    "relacionado con los articulos",
    "relacionados con los articulos",
    "ofertas relacionadas con",
    "basado en tu historial",
    "basado en tus compras",
    # German.
    "empfehlungen fur sie",
    "empfehlungen fur dich",
    "empfohlen fur sie",
    "empfohlen fur dich",
    "unsere empfehlungen",
    "inspiriert von ihren",
    "inspiriert von deinen",
    "inspiriert durch ihre",
    "inspiriert durch deine",
    "kunden die diesen",
    "kunden die auch",
    "kunden kauften auch",
    "das konnte ihnen auch gefallen",
    "das konnte dir auch gefallen",
    # French.
    "recommande pour vous",
    "recommandes pour vous",
    "recommandations pour vous",
    "nos recommandations",
    "inspire par vos",
    "inspires par vos",
    "inspire de vos",
    "inspires de vos",
    "les clients ayant achete",
    "les clients ayant consulte",
    "les clients qui ont achete",
    "vous aimerez aussi",
    "vous aimerez peut etre aussi",
    "vous pourriez aussi aimer",
    "vous pourriez egalement aimer",
    "lie aux articles que",
    "lies aux articles que",
    # Italian.
    "consigliati per te",
    "consigliato per te",
    "consigli per te",
    "ispirato ai tuoi",
    "ispirati ai tuoi",
    "ispirato dai tuoi",
    "ispirati dai tuoi",
    "i clienti che hanno acquistato",
    "i clienti che hanno visto",
    "potrebbe interessarti anche",
    "ti potrebbe interessare",
    "potrebbe piacerti anche",
    "correlati agli articoli",
    "correlato agli articoli",
    # Dutch.
    "aanbevolen voor jou",
    "aanbevolen voor je",
    "aanbevolen voor u",
    "aanbevelingen voor jou",
    "aanbevelingen voor je",
    "aanbevelingen voor u",
    "geinspireerd door je",
    "geinspireerd door jouw",
    "geinspireerd door uw",
    "geinspireerd op je",
    "geinspireerd op jouw",
    "geinspireerd op uw",
    "klanten die dit",
    "klanten die ook",
    "klanten kochten ook",
    "misschien ook interessant",
    "dit vind je misschien ook leuk",
    "gerelateerd aan artikelen",
)
# "Buy again" heads a list of products bought before, and is also the button
# under an ordered item. It only counts as a heading alone on its line (or
# with "See all"), once in the e-mail, and when it isn't a button's text.
BUY_AGAIN_HEADINGS: Final[tuple[str, ...]] = (
    "buy again",
    "buy it again",
    "comprar de novo",
    "comprar novamente",
    "comprar outra vez",
    "voltar a comprar",
    "compra de nuevo",
    "comprar de nuevo",
    "volver a comprar",
    "comprar otra vez",
    "erneut kaufen",
    "nochmals kaufen",
    "noch einmal kaufen",
    "wieder kaufen",
    "acheter a nouveau",
    "acheter de nouveau",
    "racheter",
    "acquista di nuovo",
    "acquista ancora",
    "riacquista",
    "opnieuw kopen",
    "nogmaals kopen",
    "opnieuw bestellen",
)
# Words of a "See all" link next to a heading.
_SEE_ALL_WORDS: Final = frozenset(
    {
        "see",
        "view",
        "show",
        "all",
        "more",
        "ver",
        "mostrar",
        "todo",
        "todos",
        "tudo",
        "mais",
        "mas",
        "alle",
        "alles",
        "mehr",
        "anzeigen",
        "ansehen",
        "voir",
        "tout",
        "tous",
        "plus",
        "vedi",
        "mostra",
        "tutto",
        "altro",
        "bekijk",
        "bekijken",
        "toon",
        "meer",
    }
)
_MAX_SEE_ALL_WORDS = 3
# A line this short holding a heading phrase is the heading.
_SHORT_LINE_CHARS = 60


def _phrase_alternation(phrases: Iterable[str]) -> str:
    return "|".join(re.escape(p) for p in sorted(set(phrases), key=len, reverse=True))


RECOMMENDATIONS_RE: Final = re.compile(
    rf"(?<![a-z0-9])(?:{_phrase_alternation(RECOMMENDATION_HEADINGS)})(?![a-z0-9])"
)
_BUY_AGAIN_RE: Final = re.compile(
    rf"(?:{_phrase_alternation(BUY_AGAIN_HEADINGS)})(?: (?P<rest>.+))?"
)


def text_key(text: str) -> str:
    """Return text as titles are compared: folded words, single spaces."""
    return _NOT_WORD_RE.sub(" ", fold(text)).strip()


def _is_heading(key: str) -> bool:
    """Return True when a line's key is a recommendations heading."""
    match = RECOMMENDATIONS_RE.search(key)
    return match is not None and (match.start() == 0 or len(key) <= _SHORT_LINE_CHARS)


def _is_buy_again(key: str) -> bool:
    """Return True when a line's key is a "Buy again" heading, maybe a button."""
    match = _BUY_AGAIN_RE.fullmatch(key)
    if match is None:
        return False
    rest = (match.group("rest") or "").split()
    return len(rest) <= _MAX_SEE_ALL_WORDS and all(w in _SEE_ALL_WORDS for w in rest)


def recommendations_start(text: str, *, buttons: Iterable[str] = ()) -> int | None:
    """Return where the first recommendations heading of ``text`` starts.

    ``text`` is the e-mail's text, one block per line; ``buttons`` are the
    texts of links next to ordered items, so a "Buy again" button isn't
    taken for the heading of the same name. Returns None without a heading.
    """
    button_keys = {text_key(button) for button in buttons}
    lines: list[tuple[int, str]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        if key := text_key(line):
            lines.append((pos, key))
        pos += len(line)
    buy_again = Counter(key for _, key in lines if _is_buy_again(key))
    for start, key in lines:
        if _is_heading(key):
            return start
        if buy_again[key] == 1 and key not in button_keys:
            return start
    return None


def before_recommendations(text: str, *, buttons: Iterable[str] = ()) -> str:
    """Return ``text`` up to its first recommendations heading."""
    cut = recommendations_start(text, buttons=buttons)
    return text if cut is None else text[:cut]


def drop_recommended(
    items: Iterable[str], text: str, *, buttons: Iterable[str] = ()
) -> list[str]:
    """Drop the items written in ``text`` only after a recommendations heading.

    Items are looked up by ``item_key``; an item that isn't found stays.
    """
    items = list(items)
    cut = recommendations_start(text, buttons=buttons)
    if cut is None:
        return items
    before = f" {text_key(text[:cut])} "
    after = f" {text_key(text[cut:])} "
    kept: list[str] = []
    for item in items:
        key = item_key(item)
        if key and f" {key}" not in before and f" {key}" in after:
            continue
        kept.append(item)
    return kept
