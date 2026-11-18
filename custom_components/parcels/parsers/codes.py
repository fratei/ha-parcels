"""Delivery PINs, one-time passwords and pickup codes, read next to a label.

Couriers ask for a code at the door ("Código de entrega: 4821", "Your
one-time password (OTP) is 482193"); lockers and shops ask for one at
pickup ("Abholcode 519384"). A code is only read right after one of its
labels, in one of three shapes:

* the label, an optional "(OTP)", an optional ":" or verb ("is", "é", "es",
  "ist", "est", "è"...), then the code: "PIN de entrega: 4821";
* the label, what the code is for, then ":" or a verb and the code: "Your
  delivery code for order 405-3829174-6627315 is 4821";
* the label alone on its line and the code alone on the next one.

A code has 3 to 10 letters and digits, at least one of them a digit, so a
word never passes; a value equal to a tracking or an order number never
does either. Labels are folded (lowercase, no accents) and cover
Portuguese, Spanish, English, German, French, Italian and Dutch.

Parsers read tracking and order numbers from text passed through
``mask_codes``, so a PIN is never taken for one of them either.
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Final

from .lang import fold_aligned

MIN_CODE_CHARS: Final = 3
MAX_CODE_CHARS: Final = 10

# Labels of a code given to the courier or used at pickup. They name a
# code whatever the news of the e-mail is.
CODE_LABELS: Final[dict[str, tuple[str, ...]]] = {
    "pt": (
        "codigo de entrega",
        "codigo da entrega",
        "codigo para entrega",
        "codigo para a entrega",
        "codigo de confirmacao de entrega",
        "codigo de confirmacao da entrega",
        "pin de entrega",
        "pin da entrega",
        "codigo pin",
        "codigo de recolha",
        "codigo de levantamento",
        "codigo de retirada",
        "codigo otp",
        "palavra passe unica",
        "palavra passe de uso unico",
        "palavra passe de utilizacao unica",
        "codigo de uso unico",
        "codigo de utilizacao unica",
        "senha de uso unico",
        "senha de entrega",
    ),
    "es": (
        "codigo de entrega",
        "codigo de confirmacion de entrega",
        "pin de entrega",
        "clave de entrega",
        "codigo pin",
        "codigo de recogida",
        "codigo de retirada",
        "codigo de recoleccion",
        "codigo de un solo uso",
        "codigo de un uso",
        "contrasena de un solo uso",
        "clave de un solo uso",
        "codigo otp",
    ),
    "en": (
        "delivery code",
        "delivery pin",
        "delivery passcode",
        "delivery otp",
        "one time password",
        "one time passcode",
        "one time code",
        "one time pin",
        "otp",
        "pickup code",
        "pick up code",
        "pickup pin",
        "pick up pin",
        "collection code",
        "collection pin",
        "pin code",
        "pincode",
        "pin",
    ),
    "de": (
        "zustellcode",
        "zustell code",
        "zustellpin",
        "zustell pin",
        "liefercode",
        "lieferpin",
        "liefer pin",
        "abholcode",
        "abhol code",
        "abholpin",
        "abhol pin",
        "einmalpasswort",
        "einmal passwort",
        "einmalkennwort",
        "einmalcode",
        "einmal code",
        "einmaliger code",
        "einmaligen code",
        "einmaliges passwort",
        "einmaliges kennwort",
        "pin code",
    ),
    "fr": (
        "code de livraison",
        "code livraison",
        "code de confirmation de livraison",
        "code pin",
        "code de retrait",
        "code retrait",
        "code de recuperation",
        "code a usage unique",
        "mot de passe a usage unique",
        "code otp",
    ),
    "it": (
        "codice di consegna",
        "codice consegna",
        "pin di consegna",
        "codice pin",
        "codice di ritiro",
        "codice ritiro",
        "codice monouso",
        "password monouso",
        "codice usa e getta",
        "codice otp",
    ),
    "nl": (
        "bezorgcode",
        "bezorg code",
        "bezorgpincode",
        "ophaalcode",
        "afhaalcode",
        "eenmalige code",
        "eenmalige pincode",
        "eenmalig wachtwoord",
        "pincode",
    ),
}
# Labels that only name a code the customer needs: in "ready for pickup"
# and "delivery attempted" e-mails (lockers, shops).
LOCKER_CODE_LABELS: Final[tuple[str, ...]] = (
    "codigo de abertura",
    "codigo de apertura",
    "codigo de desbloqueio",
    "codigo de desbloqueo",
    "codigo de acesso",
    "codigo de acceso",
    "codigo de seguranca",
    "codigo de seguridad",
    "unlock code",
    "opening code",
    "locker code",
    "retrieval code",
    "access code",
    "security code",
    "abholnummer",
    "offnungscode",
    "code de deverrouillage",
    "codice di sblocco",
    "codice di apertura",
    "openingscode",
    "ontgrendelcode",
)
# Bare "code" labels, only when a colon follows them, in the same e-mails
# as LOCKER_CODE_LABELS.
GENERIC_CODE_LABELS: Final[tuple[str, ...]] = ("codigo", "code", "codice")
# A bare label on a line with one of these words names another code.
NOT_CODE_WORDS: Final[tuple[str, ...]] = (
    "postal",
    "codigo postal",
    "rastreio",
    "seguimento",
    "seguimiento",
    "promo*",
    "desconto",
    "descuento",
    "discount",
    "zip",
    "postcode",
    "tracking",
    "track",
    "plz",
    "postleitzahl",
    "rabatt*",
    "gutschein*",
    "code postal",
    "suivi",
    "reduction",
    "cap",
    "tracciamento",
    "sconto",
    "kortingscode",
    "voucher",
    "coupon",
    "qr",
    "cliente",
    "customer",
    "kunde*",
    "client",
    "klant*",
)
# Words that, right before a bare "Code:", name another code: "Order code:".
OTHER_CODE_NOUNS: Final[tuple[str, ...]] = (
    "order",
    "shipment",
    "shipping",
    "parcel",
    "package",
    "consignment",
    "reference",
    "booking",
    "product",
    "item",
    "article",
    "account",
    "gift",
    "bar",
    "post",
    "area",
    "country",
    "sort",
)


# One character per input character, so folded offsets map back to the text.
_PUNCT = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u02bc": "'",
        "`": "'",
        "\u00a0": " ",
        "\u2007": " ",
        "\u2009": " ",
        "\u202f": " ",
        "\t": " ",
        "\u00b0": "o",
    }
)
_S = r"[^\S\n]"
# Words of a label are apart by spaces or a hyphen: "pick-up code".
_GAP = rf"(?:{_S}*-{_S}*|{_S}+)"


def _alternation(phrases: Iterable[str]) -> str:
    """Join folded phrases into a regex alternation, longest first."""
    parts: list[str] = []
    for phrase in sorted(set(phrases), key=lambda p: (-len(p), p)):
        prefix = phrase.endswith("*")
        words = phrase.rstrip("*").split()
        if words:
            body = _GAP.join(re.escape(word) for word in words)
            parts.append(body + ("[a-z0-9]*" if prefix else ""))
    return "|".join(parts) or "(?!)"


def _phrases_regex(phrases: Iterable[str]) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9])(?:{_alternation(phrases)})(?![a-z0-9])")


ALL_CODE_LABELS: Final[tuple[str, ...]] = tuple(
    sorted({label for labels in CODE_LABELS.values() for label in labels})
)
_LABEL_RE = _phrases_regex(ALL_CODE_LABELS)
_LOCKER_LABEL_RE = _phrases_regex(LOCKER_CODE_LABELS)
_GENERIC_LABEL_RE = re.compile(
    rf"(?<![a-z0-9])(?:{_alternation(GENERIC_CODE_LABELS)}){_S}*(?=:)"
)
_NOT_CODE_RE = _phrases_regex(NOT_CODE_WORDS)
_OTHER_CODE_NOUN_RE = re.compile(
    rf"(?<![a-z0-9])(?:{_alternation(OTHER_CODE_NOUNS)}){_GAP}$"
)

# "Código de entrega (OTP): 4821".
_ABBREVIATION = rf"(?:{_S}*\((?:otp|pin|code|codigo|codice)\))?"
# "is" (en, nl), "é"/"è" (pt, it), "es" (es), "ist"/"lautet" (de), "est" (fr).
_VERB = r"(?:is|e|es|ist|lautet|est|sera)"
_CONNECTOR = rf"(?:{_S}*[:#=]{_S}*|{_S}*-{_S}+|{_S}+{_VERB}{_S}*:?{_S}+|{_S}+)"
_VALUE = r"(?P<value>[0-9a-z]{3,10})(?![0-9a-z])"
_DIRECT_RE = re.compile(rf"{_ABBREVIATION}{_CONNECTOR}?{_VALUE}")
# What the code is for, or who gets it: "for order 405-3829174-6627315",
# "para a encomenda", "with your driver", "al repartidor".
_PURPOSE = (
    r"(?:para|pra|for|of|de|da|do|das|dos|del|von|vom|fur|zur|zum|pour|du|des"
    r"|per|di|della|dello|dell|voor|van|to|with|a|ao|aos|al|au|aux|con|com|mit"
    r"|an|dem|avec|aan|met)"
)
# The words in between stay in the sentence: no ":" and no full stop, but
# "Nr. 4711" and "n. 30021" are fine.
_PURPOSE_WORDS = r"(?:[^\n:;!?.]|\.(?=\S)|(?<![a-z])(?:n|nr|no|num|nro)\.){1,80}?"
_QUALIFIED_RE = re.compile(
    rf"{_ABBREVIATION}{_S}+{_PURPOSE}(?![a-z0-9]){_PURPOSE_WORDS}"
    rf"(?:{_S}*[:=]{_S}*|{_S}+{_VERB}{_S}*:?{_S}+){_VALUE}"
)
# A label that ends its line: "Código de levantamento:".
_LABEL_TAIL_RE = re.compile(rf"{_ABBREVIATION}{_S}*[:#.\-]?{_S}*")
# A code alone on its line: "  482913".
_LINE_VALUE_RE = re.compile(rf"{_S}*(?:[:#*>\-]{_S}*)?{_VALUE}")
_LINE_REST_RE = re.compile(rf"{_S}*\.?{_S}*")
# "739 215" is one code.
_SECOND_HALF_RE = re.compile(rf"{_S}(?P<half>\d{{3}})(?![0-9a-z])")
# The value goes on: a date, a time, a number in groups, a price.
_CONTINUES_RE = re.compile(rf"[.,:/\-][0-9a-z]|{_S}+\d{{3}}|{_S}*[%\u20ac$\u00a3]")
# "24h", "2x", "10kg", "3rd": a quantity or a rank, not a code.
_QUANTITY_RE = re.compile(
    r"\d{1,3}(?:h|hr|hrs|min|x|g|kg|l|ml|m|cm|mm|km|am|pm|st|nd|rd|th|o|a|er|e)"
)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+")
_LOOKAHEAD_LINES = 3


def fold_code_text(text: str) -> str:
    """Fold text for the code labels, one character per input character."""
    return fold_aligned(text.translate(_PUNCT))


def has_code_label(text: str) -> bool:
    """Return True when ``text`` has a delivery or pickup code label."""
    return _LABEL_RE.search(fold_code_text(text)) is not None


def compact_code(value: str) -> str:
    """Return a code or a number as compared: ASCII letters and digits only.

    "739 215", "#4821" and "405-3829174-6627315" compare as "739215",
    "4821" and "40538291746627315".
    """
    return "".join(char for char in value if char.isascii() and char.isalnum()).upper()


def find_code(
    text: str, *, exclude: Iterable[str] = (), locker: bool = False
) -> str | None:
    """Return the first delivery or pickup code written after its label.

    Values equal to one in ``exclude`` (the tracking and order numbers of
    the e-mail) are skipped. With ``locker``, for e-mails about a parcel
    that waits for pickup, locker labels ("unlock code") and a bare
    "Code:" count too. The code is returned as written, without the space
    of "739 215".
    """
    excluded = {compact_code(value) for value in exclude if value}
    for value, _start, _end in _codes(text, locker=locker):
        if compact_code(value) not in excluded:
            return value
    return None


def code_spans(text: str, *, locker: bool = False) -> list[tuple[int, int]]:
    """Return where values written as a code are in ``text``, in text order.

    Each span is the (start, end) of a value ``find_code`` could return,
    whatever the exclusions.
    """
    return [(start, end) for _value, start, end in _codes(text, locker=locker)]


def mask_codes(text: str, *, locker: bool = False) -> str:
    """Return ``text`` with every value written as a code blanked out.

    Offsets don't change. Tracking and order numbers read from the masked
    text are never a PIN that sits next to a code label.
    """
    spans = code_spans(text, locker=locker)
    if not spans:
        return text
    parts: list[str] = []
    pos = 0
    for start, end in spans:
        if start < pos:
            continue
        parts.extend((text[pos:start], " " * (end - start)))
        pos = end
    parts.append(text[pos:])
    return "".join(parts)


def _codes(text: str, *, locker: bool) -> list[tuple[str, int, int]]:
    """Return every value written after a code label, with its span."""
    folded = _URL_RE.sub(lambda m: " " * len(m.group(0)), fold_code_text(text))
    found: list[tuple[str, int, int]] = []
    for start, end in _label_spans(folded, locker=locker):
        if (value := _value_after(text, folded, start, end)) is not None:
            found.append(value)
    return found


def _label_spans(folded: str, *, locker: bool) -> list[tuple[int, int]]:
    """Return the spans of the code labels in ``folded``, in text order."""
    spans = [match.span() for match in _LABEL_RE.finditer(folded)]
    if locker:
        spans += [match.span() for match in _LOCKER_LABEL_RE.finditer(folded)]
        for match in _GENERIC_LABEL_RE.finditer(folded):
            line_start = folded.rfind("\n", 0, match.start()) + 1
            before = folded[line_start : match.start()]
            if not _NOT_CODE_RE.search(before) and not _OTHER_CODE_NOUN_RE.search(
                before
            ):
                spans.append(match.span())
    return sorted(spans)


def _value_after(
    text: str, folded: str, start: int, end: int
) -> tuple[str, int, int] | None:
    """Return the code that follows the label at ``start``-``end``, if any."""
    for regex in (_DIRECT_RE, _QUALIFIED_RE):
        match = regex.match(folded, end)
        if match is not None and (found := _checked(text, folded, match)):
            return found
    return _value_below(text, folded, end)


def _value_below(text: str, folded: str, end: int) -> tuple[str, int, int] | None:
    """Return the code alone on a line under a label that ends its line."""
    line_end = _line_end(folded, end)
    tail = _LABEL_TAIL_RE.match(folded, end, line_end)
    if tail is None or tail.end() != line_end:
        return None
    pos = line_end
    for _ in range(_LOOKAHEAD_LINES):
        if pos >= len(folded):
            return None
        next_start = pos + 1
        next_end = _line_end(folded, next_start)
        if folded[next_start:next_end].strip():
            match = _LINE_VALUE_RE.match(folded, next_start, next_end)
            found = _checked(text, folded, match) if match is not None else None
            if found is None:
                return None
            rest = _LINE_REST_RE.match(folded, found[2], next_end)
            return found if rest is not None and rest.end() == next_end else None
        pos = next_end
    return None


def _line_end(folded: str, pos: int) -> int:
    end = folded.find("\n", pos)
    return len(folded) if end < 0 else end


def _checked(
    text: str, folded: str, match: re.Match[str]
) -> tuple[str, int, int] | None:
    """Return the matched value and its span, when it can be a code."""
    start, end = match.span("value")
    value = text[start:end]
    if (
        len(value) == 3
        and value.isdigit()
        and (half := _SECOND_HALF_RE.match(folded, end))
    ):
        value += half.group("half")
        end = half.end()
    if _CONTINUES_RE.match(folded, end):
        return None
    if not (
        MIN_CODE_CHARS <= len(value) <= MAX_CODE_CHARS
        and value.isascii()
        and value.isalnum()
        and any(char.isdigit() for char in value)
    ):
        return None
    if _QUANTITY_RE.fullmatch(value.lower()):
        return None
    return value, start, end
