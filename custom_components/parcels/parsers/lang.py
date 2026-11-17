"""Language helpers for pt, es, en, de, fr, it and nl.

Everything here works on *folded* text: lowercase without accents (see
``fold``). The tables are shared by the date parser and the e-mail parsers.
"""

from __future__ import annotations

from collections import Counter
import re
import unicodedata

LANGUAGES: tuple[str, ...] = ("pt", "es", "en", "de", "fr", "it", "nl")

# Month names and abbreviations per language, folded.
MONTHS_BY_LANG: dict[str, dict[str, int]] = {
    "pt": {
        "janeiro": 1,
        "fevereiro": 2,
        "marco": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
        "jan": 1,
        "fev": 2,
        "mar": 3,
        "abr": 4,
        "mai": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "set": 9,
        "out": 10,
        "nov": 11,
        "dez": 12,
    },
    "es": {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
        "ene": 1,
        "feb": 2,
        "mar": 3,
        "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "sep": 9,
        "sept": 9,
        "set": 9,
        "oct": 10,
        "nov": 11,
        "dic": 12,
    },
    "en": {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "sept": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    },
    "de": {
        "januar": 1,
        "janner": 1,
        "februar": 2,
        "feber": 2,
        "marz": 3,
        "april": 4,
        "mai": 5,
        "juni": 6,
        "juli": 7,
        "august": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "dezember": 12,
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "mrz": 3,
        "apr": 4,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "sept": 9,
        "okt": 10,
        "nov": 11,
        "dez": 12,
    },
    "fr": {
        "janvier": 1,
        "fevrier": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "aout": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "decembre": 12,
        "janv": 1,
        "fevr": 2,
        "fev": 2,
        "avr": 4,
        "juil": 7,
        "sept": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    },
    "it": {
        "gennaio": 1,
        "febbraio": 2,
        "marzo": 3,
        "aprile": 4,
        "maggio": 5,
        "giugno": 6,
        "luglio": 7,
        "agosto": 8,
        "settembre": 9,
        "ottobre": 10,
        "novembre": 11,
        "dicembre": 12,
        "gen": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "mag": 5,
        "giu": 6,
        "lug": 7,
        "ago": 8,
        "set": 9,
        "ott": 10,
        "nov": 11,
        "dic": 12,
    },
    "nl": {
        "januari": 1,
        "februari": 2,
        "maart": 3,
        "april": 4,
        "mei": 5,
        "juni": 6,
        "juli": 7,
        "augustus": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "december": 12,
        "jan": 1,
        "feb": 2,
        "mrt": 3,
        "apr": 4,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "sept": 9,
        "okt": 10,
        "nov": 11,
        "dec": 12,
    },
}

# Full weekday names per language (0 = Monday), folded.
WEEKDAYS_BY_LANG: dict[str, dict[str, int]] = {
    "pt": {
        "segunda-feira": 0,
        "segunda feira": 0,
        "segunda": 0,
        "terca-feira": 1,
        "terca feira": 1,
        "terca": 1,
        "quarta-feira": 2,
        "quarta feira": 2,
        "quarta": 2,
        "quinta-feira": 3,
        "quinta feira": 3,
        "quinta": 3,
        "sexta-feira": 4,
        "sexta feira": 4,
        "sexta": 4,
        "sabado": 5,
        "domingo": 6,
    },
    "es": {
        "lunes": 0,
        "martes": 1,
        "miercoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sabado": 5,
        "domingo": 6,
    },
    "en": {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    },
    "de": {
        "montag": 0,
        "dienstag": 1,
        "mittwoch": 2,
        "donnerstag": 3,
        "freitag": 4,
        "samstag": 5,
        "sonnabend": 5,
        "sonntag": 6,
    },
    "fr": {
        "lundi": 0,
        "mardi": 1,
        "mercredi": 2,
        "jeudi": 3,
        "vendredi": 4,
        "samedi": 5,
        "dimanche": 6,
    },
    "it": {
        "lunedi": 0,
        "martedi": 1,
        "mercoledi": 2,
        "giovedi": 3,
        "venerdi": 4,
        "sabato": 5,
        "domenica": 6,
    },
    "nl": {
        "maandag": 0,
        "dinsdag": 1,
        "woensdag": 2,
        "donderdag": 3,
        "vrijdag": 4,
        "zaterdag": 5,
        "zondag": 6,
    },
}

# Weekday abbreviations, folded. Short and ambiguous, so they are only used
# in front of a date ("Tue, 18 Nov", "qui., 20/11").
WEEKDAY_ABBREVIATIONS_BY_LANG: dict[str, dict[str, int]] = {
    "pt": {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6},
    "es": {"lun": 0, "mar": 1, "mie": 2, "jue": 3, "vie": 4, "sab": 5, "dom": 6},
    "en": {
        "mon": 0,
        "tue": 1,
        "tues": 1,
        "wed": 2,
        "thu": 3,
        "thur": 3,
        "thurs": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    },
    "de": {"mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6},
    "fr": {"lun": 0, "mar": 1, "mer": 2, "jeu": 3, "ven": 4, "sam": 5, "dim": 6},
    "it": {"lun": 0, "mar": 1, "mer": 2, "gio": 3, "ven": 4, "sab": 5, "dom": 6},
    "nl": {"ma": 0, "di": 1, "wo": 2, "do": 3, "vr": 4, "za": 5, "zo": 6},
}

# Relative days per language, folded. Longer phrases win over shorter ones
# when matching ("pasado manana" before "manana").
TODAY_BY_LANG: dict[str, tuple[str, ...]] = {
    "pt": ("hoje", "esta noite"),
    "es": ("hoy", "esta noche"),
    "en": ("today", "tonight", "this evening"),
    "de": ("heute", "heute abend"),
    "fr": ("aujourd'hui", "aujourd hui", "ce soir"),
    "it": ("oggi", "stasera"),
    "nl": ("vandaag", "vanavond"),
}
TOMORROW_BY_LANG: dict[str, tuple[str, ...]] = {
    "pt": ("amanha",),
    "es": ("manana",),
    "en": ("tomorrow",),
    "de": ("morgen",),
    "fr": ("demain",),
    "it": ("domani",),
    "nl": ("morgen",),
}
DAY_AFTER_TOMORROW_BY_LANG: dict[str, tuple[str, ...]] = {
    "pt": ("depois de amanha",),
    "es": ("pasado manana",),
    "en": ("day after tomorrow", "the day after tomorrow"),
    "de": ("ubermorgen",),
    "fr": ("apres-demain", "apres demain"),
    "it": ("dopodomani", "dopo domani"),
    "nl": ("overmorgen",),
}


def _merge(tables: dict[str, dict[str, int]]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for table in tables.values():
        merged.update(table)
    return merged


def _union(tables: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    words = {word for table in tables.values() for word in table}
    return tuple(sorted(words, key=lambda w: (-len(w), w)))


# Every language merged. Names that exist in several languages always mean
# the same month or weekday ("mar" is March wherever it is a month).
MONTHS: dict[str, int] = _merge(MONTHS_BY_LANG)
WEEKDAYS: dict[str, int] = _merge(WEEKDAYS_BY_LANG)
WEEKDAY_ABBREVIATIONS: dict[str, int] = _merge(WEEKDAY_ABBREVIATIONS_BY_LANG)
TODAY: tuple[str, ...] = _union(TODAY_BY_LANG)
TOMORROW: tuple[str, ...] = _union(TOMORROW_BY_LANG)
DAY_AFTER_TOMORROW: tuple[str, ...] = _union(DAY_AFTER_TOMORROW_BY_LANG)

# Frequent words per language, folded, used to guess the language.
STOPWORDS: dict[str, frozenset[str]] = {
    "pt": frozenset(
        [
            "o",
            "os",
            "as",
            "do",
            "da",
            "dos",
            "das",
            "no",
            "na",
            "nos",
            "nas",
            "um",
            "uma",
            "uns",
            "umas",
            "para",
            "com",
            "nao",
            "sua",
            "seu",
            "suas",
            "seus",
            "voce",
            "encomenda",
            "obrigado",
            "obrigada",
            "ola",
            "pelo",
            "pela",
            "foi",
            "sera",
            "esta",
            "estao",
            "ja",
            "tambem",
            "ate",
            "hoje",
            "amanha",
            "entrega",
            "enviada",
            "enviado",
            "aqui",
            "mais",
            "muito",
            "quando",
            "onde",
            "ao",
            "aos",
            "numa",
            "num",
            "pode",
            "podes",
            "levantamento",
            "morada",
            "envio",
        ]
    ),
    "es": frozenset(
        [
            "el",
            "la",
            "los",
            "las",
            "del",
            "y",
            "en",
            "un",
            "una",
            "unos",
            "unas",
            "por",
            "para",
            "con",
            "su",
            "sus",
            "tu",
            "tus",
            "pedido",
            "gracias",
            "hola",
            "usted",
            "ha",
            "sido",
            "esta",
            "sera",
            "hoy",
            "manana",
            "envio",
            "entrega",
            "nuestro",
            "nuestra",
            "puedes",
            "aqui",
            "mas",
            "muy",
            "cuando",
            "donde",
            "al",
            "enviado",
            "recibido",
            "llegara",
            "paquete",
            "tienda",
        ]
    ),
    "en": frozenset(
        [
            "the",
            "and",
            "your",
            "you",
            "is",
            "of",
            "to",
            "for",
            "has",
            "been",
            "order",
            "with",
            "on",
            "we",
            "will",
            "be",
            "this",
            "it",
            "are",
            "our",
            "thanks",
            "thank",
            "hi",
            "hello",
            "shipped",
            "delivery",
            "package",
            "has",
            "have",
            "from",
            "by",
            "your",
            "at",
            "track",
            "arriving",
            "today",
            "tomorrow",
        ]
    ),
    "de": frozenset(
        [
            "der",
            "die",
            "das",
            "und",
            "ist",
            "ihre",
            "ihr",
            "sie",
            "wir",
            "nicht",
            "mit",
            "von",
            "zu",
            "den",
            "dem",
            "ein",
            "eine",
            "einen",
            "fur",
            "auf",
            "bestellung",
            "sendung",
            "paket",
            "wird",
            "heute",
            "vielen",
            "dank",
            "hallo",
            "ihrer",
            "ihren",
            "unser",
            "unsere",
            "wurde",
            "werden",
            "morgen",
            "zustellung",
            "lieferung",
            "versandt",
        ]
    ),
    "fr": frozenset(
        [
            "le",
            "la",
            "les",
            "des",
            "du",
            "et",
            "est",
            "votre",
            "vos",
            "vous",
            "nous",
            "pour",
            "avec",
            "une",
            "un",
            "sur",
            "commande",
            "colis",
            "merci",
            "bonjour",
            "sera",
            "ete",
            "livraison",
            "aujourd",
            "hui",
            "notre",
            "nos",
            "dans",
            "par",
            "au",
            "aux",
            "ce",
            "cette",
            "expedie",
            "livre",
            "demain",
        ]
    ),
    "it": frozenset(
        [
            "il",
            "lo",
            "la",
            "gli",
            "le",
            "di",
            "del",
            "della",
            "dei",
            "delle",
            "e",
            "che",
            "per",
            "con",
            "un",
            "una",
            "il",
            "tuo",
            "tua",
            "tuoi",
            "suo",
            "ordine",
            "grazie",
            "ciao",
            "sara",
            "stato",
            "stata",
            "spedizione",
            "consegna",
            "non",
            "sono",
            "ha",
            "nel",
            "nella",
            "al",
            "alla",
            "oggi",
            "domani",
            "spedito",
            "pacco",
        ]
    ),
    "nl": frozenset(
        [
            "de",
            "het",
            "een",
            "en",
            "van",
            "is",
            "je",
            "jouw",
            "uw",
            "wij",
            "we",
            "niet",
            "met",
            "voor",
            "op",
            "bestelling",
            "pakket",
            "zending",
            "bedankt",
            "hallo",
            "wordt",
            "vandaag",
            "morgen",
            "bezorgd",
            "bezorging",
            "ons",
            "onze",
            "naar",
            "bij",
            "heeft",
            "zijn",
            "verzonden",
        ]
    ),
}

_WORD_WEIGHTS: dict[str, dict[str, float]] = {}
for _lang, _words in STOPWORDS.items():
    for _word in _words:
        _WORD_WEIGHTS.setdefault(_word, {})[_lang] = 0.0
for _word, _langs in _WORD_WEIGHTS.items():
    for _lang in _langs:
        _langs[_lang] = 1.0 / len(_langs)

_TOKEN_RE = re.compile(r"[a-z]+")
_FOLD_TABLE: dict[int, str] = {c: chr(c + 32) for c in range(ord("A"), ord("Z") + 1)}


def fold(text: str) -> str:
    """Lowercase and strip accents ("Março" -> "marco", "ÜBER" -> "uber")."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _fold_char(char: str) -> str:
    decomposed = unicodedata.normalize("NFKD", char)
    base = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return base[:1] if base else " "


def fold_aligned(text: str) -> str:
    """Fold text keeping exactly one character per input character.

    Positions in the result line up with the original text, so a match in
    folded text can be mapped back. Characters that would expand (such as
    ligatures) are cut to their first folded character.
    """
    table = dict(_FOLD_TABLE)
    for char in set(text):
        if ord(char) > 127:
            table[ord(char)] = _fold_char(char)
    return text.translate(table)


def detect_language(text: str) -> str | None:
    """Guess the language of a text from frequent words.

    Returns one of ``LANGUAGES``, or None when the text is too short or
    the scores are too close to call.
    """
    counts = Counter(_TOKEN_RE.findall(fold(text[:5000])))
    scores = dict.fromkeys(LANGUAGES, 0.0)
    for word, count in counts.items():
        for lang, weight in _WORD_WEIGHTS.get(word, {}).items():
            scores[lang] += weight * min(count, 5)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    (best, top), (_, second) = ranked[0], ranked[1]
    if top < 1.5 or top < second * 1.25:
        return None
    return best
