"""Details of a parcel event, read from the e-mail that reports it.

``add_details`` adds to each shipment of a result what Live Activities,
the details and the persistent notification show besides the status:

- the last day to collect a parcel waiting at a pickup point, from pickup
  notices and missed-attempt e-mails (``eta.find_collect_by``);
- the day of the next delivery attempt after a missed one
  (``eta.find_next_attempt``);
- where a delivered parcel was left (``find_left_at``): with a neighbour,
  in the mailbox, at the door, at reception, in the garage or in a locker.
  Only these fixed categories are kept, never names, house numbers or
  photos.

``tracker_details`` reads the same from a tracker's event text (17TRACK's
and the Parcel app's), for the event's status.

The readers are deterministic and read the 7 languages of the parsers.
Neither function raises: on an error nothing is added and only the
exception type is logged, at debug level.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, tzinfo
import logging
import re
from typing import Any

from ..const import LeftAt, MailKind, ParcelStatus
from .base import MailMessage, ParsedShipment, ParseResult
from .eta import MAX_FIND_CHARS, find_collect_by, find_next_attempt
from .lang import MONTHS, WEEKDAYS, detect_language, fold

_LOGGER = logging.getLogger(__name__)


def _phrases(*patterns: str) -> str:
    """Join regex phrases, longest first; a space matches any whitespace."""
    ordered = sorted(patterns, key=len, reverse=True)
    return "|".join(pattern.replace(" ", r"\s+") for pattern in ordered)


# Places a delivered parcel was left at. Groups ending in "p" start with
# their own preposition ("beim Empfang", "devant la porte"). Italian
# "vicino" is also "near", so it only counts with its preposition.
_PLACE_RE = re.compile(
    r"(?<![a-z0-9])(?:"
    r"(?P<neighbourp>"
    + _phrases(
        "(?:al|dal|ai|dai|alla|dalla|a un|a una|presso (?:il|un|una|la|i))"
        " (?:(?:tuo|tua|tuoi|suo|sua|vostro|vostra) )?vicin[oaie]",
        "next door",
    )
    + r")|(?P<receptionp>"
    + _phrases("am empfang", "beim empfang", "an den empfang")
    + r")|(?P<doorp>"
    + _phrases(
        "vor (?:der|die) tur",
        "devant (?:la|votre|ta) porte",
        "davanti alla porta",
        "voor de deur",
        "delante de la puerta",
        "em frente (?:a|da) porta",
    )
    + r")|(?P<door>"
    + _phrases(
        "front door",
        "back door",
        "doorstep",
        "porch",
        "porta da frente",
        "porta de entrada",
        "porta principal",
        "porta de casa",
        "puerta principal",
        "puerta de entrada",
        "puerta de casa",
        "haustur",
        "wohnungstur",
        "hintertur",
        "terrassentur",
        "eingangstur",
        "porte d'entree",
        "porta d'ingresso",
        "porta di casa",
        "voordeur",
        "achterdeur",
    )
    + r")|(?P<doorx>"
    + _phrases("doors?", "porta", "puerta", "tur", "porte", "deur")
    + r")|(?P<neighbour>"
    + _phrases(
        "neighbours?",
        "neighbors?",
        "vizinh[oa]s?",
        "vecin[oa]s?",
        "nachbar(?:n|in)?",
        "wunschnachbarn?",
        "voisine?s?",
        "buren",
        "buurman",
        "buurvrouw",
    )
    + r")|(?P<mailbox>"
    + _phrases(
        "mailbox(?:es)?",
        "mail box(?:es)?",
        "letterbox(?:es)?",
        "letter box(?:es)?",
        "postbox(?:es)?",
        "post box(?:es)?",
        "caixa de correios?",
        "caixa do correio",
        "caixa postal",
        "buzon(?:es)?",
        "briefkasten",
        "hausbriefkasten",
        "boite aux lettres",
        "boite a lettres",
        "cassetta delle lettere",
        "cassetta postale",
        "buca delle lettere",
        "brievenbus",
    )
    + r")|(?P<reception>"
    + _phrases(
        "reception",
        "front desk",
        "concierge",
        "porter",
        "mailroom",
        "mail room",
        "post room",
        "doorman",
        "rececao",
        "recepcao",
        "rececionista",
        "recepcionista",
        "portaria",
        "porteir[oa]",
        "recepcion",
        "conserje",
        "conserjeria",
        "porteria",
        "porter[oa]",
        "rezeption",
        "pfortner",
        "poststelle",
        "hausmeister",
        "empfangsbereich",
        "accueil",
        "gardien(?:ne)?s?",
        "loge",
        "conciergerie",
        "portineria",
        "portiere",
        "portinaio",
        "receptie",
        "balie",
        "portier",
        "postkamer",
    )
    + r")|(?P<garage>"
    + _phrases(
        "garage", "garagem", "garaje", "cochera", "box auto", "carport", "garagentor"
    )
    + r")|(?P<locker>"
    + _phrases(
        "parcel lockers?",
        "parcel box(?:es)?",
        "lockers?",
        "cacifos?",
        "taquillas?",
        "casilleros?",
        "paketkasten",
        "paketbox",
        "paketfach",
        "paketschrank",
        "schliessfach",
        "packstation",
        "paketstation",
        "casiers?",
        "boite a colis",
        "armadiett[oi]",
        "pakketkluis",
        "pakketautomaat",
        "pakketbus",
        "pakketbox",
    )
    + r"))(?![a-z0-9])"
)
_PLACES = {
    "neighbourp": LeftAt.NEIGHBOUR,
    "neighbour": LeftAt.NEIGHBOUR,
    "mailbox": LeftAt.MAILBOX,
    "doorp": LeftAt.DOOR,
    "door": LeftAt.DOOR,
    "doorx": LeftAt.DOOR,
    "receptionp": LeftAt.RECEPTION,
    "reception": LeftAt.RECEPTION,
    "garage": LeftAt.GARAGE,
    "locker": LeftAt.LOCKER,
}
_OWN_PREPOSITION = frozenset({"neighbourp", "receptionp", "doorp"})
# A bare door ("delivered to your door", "entregue à porta") is home
# delivery: it only counts as a place with a verb of leaving.
_BARE_DOOR = "doorx"

# Verbs that say where a parcel went. "by" forms name who took it ("Recebido
# por", "Ha ritirato:"), which counts only when a place follows, never a
# name; labels name the place ("Zustellort: Haustür"); "left" forms are
# verbs of leaving.
_PARTICIPLE_RE = re.compile(
    r"(?<![a-z0-9])(?:"
    r"(?P<by>"
    + _phrases(
        "signed for by",
        "signed by",
        "received by",
        "accepted by",
        "taken in by",
        "recebid[oa]s? por",
        "assinad[oa]s? por",
        "recibid[oa]s? por",
        "recogid[oa]s? por",
        "firmad[oa]s? por",
        "entgegengenommen von",
        "angenommen von",
        "unterschrieben von",
        "recue?s? par",
        "receptionnee?s? par",
        "signee?s? par",
        "ricevut[oaie] da",
        "ritirat[oaie] da",
        "ha ritirato",
        "hanno ritirato",
        "firmat[oaie] da",
        "ontvangen door",
        "in ontvangst genomen door",
        "aangenomen door",
        "getekend door",
        "ondertekend door",
    )
    + r")|(?P<label>"
    + _phrases(
        "zustellort",
        "ablageort",
        "abstellort",
        "delivery location",
        "lieu de livraison",
        "lieu de depot",
        "local de entrega",
        "lugar de entrega",
        "luogo di consegna",
        "afleverlocatie",
        "bezorglocatie",
    )
    + r")|(?P<left>"
    + _phrases(
        "left",
        "placed",
        "put",
        "deixad[oa]s?",
        "colocad[oa]s?",
        "pousad[oa]s?",
        "dejad[oa]s?",
        "depositad[oa]s?",
        "abgelegt",
        "abgestellt",
        "deposee?s?",
        "laissee?s?",
        "lasciat[oaie]",
        "depositat[oaie]",
        "mess[oaie]",
        "achtergelaten",
        "neergezet",
        "gezet",
        "hinterlegt",
    )
    + r")|(?P<plain>"
    + _phrases(
        "delivered",
        "posted",
        "dropped off",
        "dropped",
        "handed over",
        "handed",
        "entregues?",
        "entregad[oa]s?",
        "zugestellt",
        "geliefert",
        "abgegeben",
        "eingeworfen",
        "eingelegt",
        "entgegengenommen",
        "ubergeben",
        "ausgehandigt",
        "angenommen",
        "livree?s?",
        "remise?s?",
        "consegnat[oaie]",
        "afgeleverd",
        "geleverd",
        "bezorgd",
        "afgegeven",
        "geplaatst",
    )
    + r"))(?![a-z0-9])"
)
_NAMES_PLACE = frozenset({"by", "label"})
_LEAVES = frozenset({"left", "label"})

# Words that may stand between a verb and its place: articles, possessives,
# prepositions and adverbs such as "today" or "successfully".
_PREPOSITIONS = frozenset(
    {
        # en
        "at",
        "to",
        "in",
        "into",
        "on",
        "with",
        "by",
        "through",
        "inside",
        "outside",
        "behind",
        "near",
        # pt
        "ao",
        "aos",
        "na",
        "no",
        "nas",
        "nos",
        "num",
        "numa",
        "em",
        "com",
        "junto",
        "pelo",
        "pela",
        "para",
        # es
        "al",
        "en",
        "con",
        # de
        "im",
        "an",
        "am",
        "beim",
        "bei",
        "vor",
        "zum",
        "zur",
        "auf",
        "von",
        "unter",
        "hinter",
        # fr
        "au",
        "aux",
        "dans",
        "chez",
        "devant",
        # it
        "allo",
        "alla",
        "ai",
        "agli",
        "alle",
        "all",
        "nel",
        "nello",
        "nella",
        "nei",
        "negli",
        "nelle",
        "nell",
        "dal",
        "dalla",
        "dai",
        "dall",
        "presso",
        "davanti",
        # nl
        "bij",
        "aan",
        "op",
        "voor",
        "naar",
        "met",
    }
)
_GLUE = _PREPOSITIONS | frozenset(
    {
        # en
        "the",
        "a",
        "an",
        "your",
        "you",
        "our",
        "next",
        "safely",
        "securely",
        "successfully",
        "today",
        "it",
        "them",
        # pt
        "o",
        "os",
        "as",
        "um",
        "uma",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "seu",
        "sua",
        "seus",
        "suas",
        "vosso",
        "vossa",
        "teu",
        "tua",
        "hoje",
        "sucesso",
        # es
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "del",
        "tu",
        "su",
        "sus",
        "tus",
        "vuestro",
        "vuestra",
        "hoy",
        "exito",
        # de
        "der",
        "die",
        "den",
        "dem",
        "des",
        "ein",
        "eine",
        "einen",
        "einem",
        "einer",
        "ihr",
        "ihre",
        "ihren",
        "ihrem",
        "ihrer",
        "dein",
        "deine",
        "deinen",
        "deinem",
        "heute",
        "erfolgreich",
        # fr
        "le",
        "les",
        "l",
        "une",
        "du",
        "d",
        "votre",
        "vos",
        "ton",
        "ta",
        "tes",
        "son",
        "sa",
        "ses",
        "aujourd",
        "hui",
        "avec",
        "succes",
        # it
        "il",
        "lo",
        "i",
        "gli",
        "uno",
        "di",
        "della",
        "tuo",
        "tuoi",
        "suo",
        "vostro",
        "vostra",
        "oggi",
        # nl
        "het",
        "een",
        "je",
        "jouw",
        "uw",
        "vandaag",
        "succesvol",
    }
)
# Month and weekday names may stand between a verb and its place, like
# numbers: "Delivered on Monday 15 June to your neighbour".
_DATE_WORDS = frozenset(
    word for name in (*MONTHS, *WEEKDAYS) for word in re.findall(r"[a-z]+", name)
)
# "a" is "to" or "at" in Portuguese, Spanish, French and Italian, but the
# article in English ("Delivered: A garage rack").
_A_IS_PREPOSITION = frozenset({"pt", "es", "fr", "it"})
MAX_GAP_WORDS = 6
MAX_LABEL_WORDS = 8
MAX_VERB_AFTER = 5

_NEGATIONS = frozenset(
    {
        "not",
        "never",
        "cannot",
        "unable",
        "nao",
        "nunca",
        "nem",
        "ni",
        "jamas",
        "nicht",
        "nie",
        "niemals",
        "kein",
        "keine",
        "keinen",
        "keinem",
        "keiner",
        "keines",
        "pas",
        "jamais",
        "aucun",
        "aucune",
        "non",
        "nessun",
        "nessuno",
        "nessuna",
        "niet",
        "geen",
        "nooit",
    }
)
# Plans, offers and settings rather than what happened.
_MODALS = frozenset(
    {
        # en
        "will",
        "would",
        "may",
        "might",
        "can",
        "could",
        "should",
        "shall",
        "must",
        "be",
        "get",
        "getting",
        "choose",
        "select",
        "prefer",
        "preferred",
        "preference",
        "preferences",
        "want",
        "wish",
        "option",
        "options",
        "instruction",
        "instructions",
        "future",
        # pt
        "sera",
        "serao",
        "podera",
        "pode",
        "podem",
        "vai",
        "ira",
        "quiser",
        "escolha",
        "preferencia",
        # es
        "podra",
        "puede",
        "pueden",
        "va",
        # de
        "wird",
        "werden",
        "kann",
        "konnen",
        "konnte",
        "soll",
        "mochten",
        "wahlen",
        "wunsch",
        # fr
        "seront",
        "peut",
        "pourra",
        "vont",
        "choisir",
        "souhaitez",
        "voulez",
        # it
        "sara",
        "verra",
        "verranno",
        "puo",
        "potra",
        "scegli",
        "vuoi",
        "preferenza",
        # nl
        "wordt",
        "worden",
        "kan",
        "kunnen",
        "zal",
        "zullen",
        "kies",
        "wil",
        "wilt",
        "voorkeur",
    }
)
_CONDITIONALS = frozenset(
    {"if", "unless", "wenn", "sofern", "indien", "mocht", "qualora"}
)
_CONDITIONAL_PAIRS = frozenset(
    {("in", "case"), ("en", "caso"), ("no", "caso"), ("au", "cas"), ("nel", "caso")}
)
_CONDITIONALS_BY_LANG = {
    "pt": frozenset({"se", "caso", "falls"}),
    "es": frozenset({"si", "falls"}),
    "de": frozenset({"falls"}),
    "fr": frozenset({"si", "falls"}),
    "it": frozenset({"se", "falls"}),
    "nl": frozenset({"falls"}),
    None: frozenset({"falls"}),
}
# "encontra-se", "que se": the Portuguese reflexive, not "if".
_REFLEXIVE_BEFORE = frozenset({"-", "que"})
# A card left in the mailbox is a notice, not the parcel.
_NOTICES = frozenset(
    {
        "card",
        "cards",
        "notice",
        "slip",
        "aviso",
        "avis",
        "avviso",
        "benachrichtigung",
        "benachrichtigungskarte",
        "karte",
        "kaart",
        "kaartje",
    }
)
# "Unattended mailbox", "caixa de correio eletrónico": e-mail, not post.
_NOT_POST_RE = re.compile(
    r"(?<![a-z])(?:e-?mails?|electronic\w*|eletronic\w*|electronique|elettronic\w*"
    r"|elektronisch\w*|unattended|unmonitored|inbox|no-?reply|reply|respond\w*"
    r"|antwort\w*|repondre|rispondere|beantwoord\w*|voz|voicemail)(?![a-z])"
)
_DOOR_TO_DOOR_RE = re.compile(
    r"(?<![a-z])(?:door[\s-]+to[\s-]+door|porta[\s-]+a[\s-]+porta"
    r"|puerta[\s-]+a[\s-]+puerta|porte[\s-]+a[\s-]+porte|deur[\s-]+tot[\s-]+deur)"
    r"(?![a-z])"
)
# What a tracker's status line puts between its verb and the place
# ("Zugestellt - Briefkasten", "Delivered: Front door").
_TRACKER_SEPARATORS = frozenset({":", "-", "\u2013", "\u2014"})
_SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+")
_TOKEN_RE = re.compile(r"[a-z]+|\d+|[^\sa-z0-9]")


def find_left_at(
    text: str, lang: str | None = None, *, tracker: bool = False
) -> LeftAt | None:
    """Return where a delivered parcel was left, from a delivery e-mail.

    Reads phrases such as "Left at Front door", "Entregue ao vizinho",
    "beim Nachbarn abgegeben", "déposé dans votre boîte aux lettres" or
    "Zustellort: Garage" in any of the 7 languages. A verb of delivering,
    or a label, must name the place. Plans and offers ("can be left with a
    neighbour"), conditions, negations, questions, notice cards and a bare
    "delivered to your door" don't count. Returns a fixed category only.

    With ``tracker``, the text is a tracker's status line, which never
    names items: a dash or a colon after the verb then names the place too
    ("Zugestellt - Briefkasten"). In an e-mail, "Delivered: Garage door
    opener" names an item.
    """
    previous = ""
    for raw in text[:MAX_FIND_CHARS].splitlines():
        line = fold(raw).replace("\u2019", "'")
        if not line.strip():
            continue
        label = _label_line(previous)
        for index, sentence in enumerate(_SENTENCE_RE.split(line)):
            if sentence.rstrip().endswith("?"):
                continue
            found = _place_in(
                sentence, label if index == 0 else None, lang, tracker=tracker
            )
            if found is not None:
                return found
        previous = line
    return None


def _label_line(line: str) -> str | None:
    """Return a short line that may label the next one ("Left at")."""
    stripped = line.rstrip()
    if not stripped or stripped[-1] in ".!?":
        return None
    words = [token for token in _TOKEN_RE.findall(stripped) if token.isalnum()]
    return stripped if len(words) <= MAX_LABEL_WORDS else None


def _place_in(
    sentence: str, label: str | None, lang: str | None, *, tracker: bool = False
) -> LeftAt | None:
    """Return the first place in a sentence that a verb or label names."""
    for match in _PLACE_RE.finditer(sentence):
        group = match.lastgroup or ""
        place = _PLACES[group]
        if place is LeftAt.DOOR and _door_to_door(sentence, match):
            continue
        if place is LeftAt.MAILBOX and _NOT_POST_RE.search(sentence):
            continue
        before = sentence[: match.start()]
        if label is not None and not _words(before):
            before = f"{label} {before}"
            if place is LeftAt.MAILBOX and _NOT_POST_RE.search(label):
                continue
        after = sentence[match.end() :].partition(",")[0]
        before_tokens = _TOKEN_RE.findall(before)
        if _conditional(before_tokens, lang) or _NOTICES.intersection(before_tokens):
            continue
        if _named_before(before, after, group, lang, tracker=tracker) or _named_after(
            before, after, group, lang
        ):
            return place
    return None


def _door_to_door(sentence: str, match: re.Match[str]) -> bool:
    """Return True when a door is part of "door to door" (home delivery)."""
    return any(
        found.start() < match.end() and match.start() < found.end()
        for found in _DOOR_TO_DOOR_RE.finditer(sentence)
    )


def _named_before(
    before: str, after: str, group: str, lang: str | None, *, tracker: bool = False
) -> bool:
    """Verb first: "Left at the front door", "Entregue ao vizinho"."""
    verbs = list(_PARTICIPLE_RE.finditer(before))
    if not verbs:
        return False
    verb = verbs[-1]
    kind = verb.lastgroup or ""
    if group == _BARE_DOOR and kind not in _LEAVES:
        return False
    preposition = _gap(_TOKEN_RE.findall(before[verb.end() :]), lang, tracker=tracker)
    if preposition is None:
        return False
    if not (preposition or group in _OWN_PREPOSITION or kind in _NAMES_PLACE):
        return False
    clause = _TOKEN_RE.findall(before[: verb.start()].rpartition(",")[2])
    after_tokens = _TOKEN_RE.findall(after)
    return not (
        _negated(clause, lang) or _modal(clause, lang) or _negated(after_tokens, lang)
    )


def _named_after(before: str, after: str, group: str, lang: str | None) -> bool:
    """Verb last: "beim Nachbarn abgegeben", "bij de buren bezorgd"."""
    glue: list[str] = []
    for token in reversed(_TOKEN_RE.findall(before)):
        if token == "'":
            continue
        if token not in _GLUE:
            break
        glue.append(token)
        if len(glue) == 2:
            break
    if group not in _OWN_PREPOSITION and not any(
        _is_preposition(token, lang) for token in glue
    ):
        return False
    after_tokens = _TOKEN_RE.findall(after)
    words = [token for token in after_tokens if token.isalnum()][:MAX_VERB_AFTER]
    verb = _PARTICIPLE_RE.search(" ".join(words))
    if verb is None:
        return False
    if group == _BARE_DOOR and verb.lastgroup not in _LEAVES:
        return False
    clause = _TOKEN_RE.findall(before.rpartition(",")[2])
    return not (
        _negated(clause, lang)
        or _modal(clause, lang)
        or _negated(after_tokens, lang)
        or _modal(after_tokens, lang)
    )


def _gap(tokens: list[str], lang: str | None, *, tracker: bool = False) -> bool | None:
    """Check the words between a verb and its place.

    Returns None when they aren't all glue words, dates or punctuation (or
    are too many), else whether they hold a preposition. A comma counts as
    one ("Delivered, Front door"); a colon doesn't ("Delivered: A garage
    rack" names an item), except in a tracker's status line, where a dash
    or a colon does.
    """
    words = 0
    dates = 0
    preposition = False
    colon = False
    for token in tokens:
        if tracker and token in _TRACKER_SEPARATORS:
            colon = colon or token == ":"
            preposition = True
        elif token == ":":
            colon = True
        elif token == ",":
            preposition = True
        elif token.isdigit() or token in _DATE_WORDS:
            dates += 1
            if dates > MAX_GAP_WORDS:
                return None
        elif token.isalnum():
            words += 1
            if words > MAX_GAP_WORDS or token not in _GLUE:
                return None
            if token == "a":
                if lang in _A_IS_PREPOSITION or (lang is None and not colon):
                    preposition = True
            elif token in _PREPOSITIONS:
                preposition = True
    return preposition


def _is_preposition(token: str, lang: str | None) -> bool:
    """Return True for a preposition before a verb-last place."""
    if token == "a":
        return lang in _A_IS_PREPOSITION
    return token in _PREPOSITIONS


def _words(text: str) -> bool:
    """Return True when text holds a word or a number."""
    return any(token.isalnum() for token in _TOKEN_RE.findall(text))


def _negated(tokens: list[str], lang: str | None) -> bool:
    """Return True when words deny the delivery ("not", "nicht", "não")."""
    for index, token in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if token in _NEGATIONS:
            # "non-contact delivery" isn't a negation.
            if token == "non" and following == "-":
                continue
            return True
        # "isn't", "wasn't", "couldn't".
        if (
            token == "t"
            and index >= 2
            and tokens[index - 1] == "'"
            and tokens[index - 2].endswith("n")
        ):
            return True
        # "no" is "in the" in Portuguese; "No. 5" is a number and
        # "no-contact delivery" a kind of delivery.
        if (
            token == "no"
            and lang != "pt"
            and following not in {".", "-"}
            and not following.isdigit()
        ):
            return True
        if token == "mai" and lang == "it":
            return True
    return False


def _modal(tokens: list[str], lang: str | None) -> bool:
    """Return True for a plan, an offer or a setting ("can be left")."""
    for index, token in enumerate(tokens):
        if token == "next" and tokens[index + 1 : index + 2] == ["time"]:
            return True
        # "van" is "from" in Dutch.
        if token == "van" and lang == "es":
            return True
        if token not in _MODALS:
            continue
        # "15 May" is a date.
        nearby = tokens[index - 1 : index] + tokens[index + 1 : index + 2]
        if token == "may" and any(word.isdigit() for word in nearby):
            continue
        return True
    return False


def _conditional(tokens: list[str], lang: str | None) -> bool:
    """Return True when the sentence so far states a condition ("If ...")."""
    words = _CONDITIONALS | _CONDITIONALS_BY_LANG.get(lang, frozenset())
    for index, token in enumerate(tokens):
        if token in words:
            if token == "se" and index and tokens[index - 1] in _REFLEXIVE_BEFORE:
                continue
            return True
        if tuple(tokens[index : index + 2]) in _CONDITIONAL_PAIRS:
            return True
    return False


def add_details(result: ParseResult, message: MailMessage, tz: tzinfo) -> ParseResult:
    """Add the collect-by date, next attempt and delivery place. Never raises.

    Only parcel results with shipments change; each shipment gets the
    details of its own kind (pickup notices a collect-by date, missed
    attempts a next attempt and a collect-by date, deliveries the place).
    """
    if not result.is_parcel or not result.shipments:
        return result
    try:
        return _with_details(result, message, tz)
    except Exception as exc:
        _LOGGER.debug("Detail check failed: %s", type(exc).__name__)
        return result


def _with_details(result: ParseResult, message: MailMessage, tz: tzinfo) -> ParseResult:
    lang = result.language or message.language
    text = message.text
    # Shipments of the same kind share the e-mail's details: read them once.
    collect_by: dict[bool, date | None] = {}
    next_attempt: dict[date | None, date | None] = {}
    left_at: list[LeftAt | None] = []
    shipments: list[ParsedShipment] = []
    changed = False
    for shipment in result.shipments:
        # As ``convert.result_contributions`` reads it.
        kind = shipment.kind
        if kind in (None, MailKind.NOT_PARCEL, MailKind.UNKNOWN):
            kind = result.kind
        found: dict[str, Any] = {}
        if kind in (MailKind.READY_FOR_PICKUP, MailKind.ATTEMPTED):
            pickup = kind is MailKind.READY_FOR_PICKUP
            if pickup not in collect_by:
                collect_by[pickup] = find_collect_by(
                    text, message.date, tz, lang, pickup=pickup
                )
            found["collect_by"] = collect_by[pickup]
        if kind is MailKind.ATTEMPTED:
            start = shipment.eta.start if shipment.eta else None
            if start not in next_attempt:
                next_attempt[start] = find_next_attempt(
                    text, message.date, tz, lang, eta_start=start
                )
            found["next_attempt"] = next_attempt[start]
        if kind is MailKind.DELIVERED:
            if not left_at:
                left_at.append(
                    find_left_at(text, lang) or find_left_at(message.subject, lang)
                )
            found["left_at"] = left_at[0]
        found = {key: value for key, value in found.items() if value is not None}
        if found:
            shipment = replace(shipment, **found)
            changed = True
        shipments.append(shipment)
    return replace(result, shipments=shipments) if changed else result


def tracker_details(
    text: str | None,
    status: ParcelStatus | None,
    reference: datetime | None,
    tz: tzinfo,
) -> dict[str, Any]:
    """Return what a tracker's event text says besides its status.

    For 17TRACK's and the Parcel app's events: keyword arguments for a
    ``ParcelEvent``, without the ones the text doesn't give. ``reference``
    is when the event happened; without it, when its day isn't known, only
    where a delivered parcel was left is read. Never raises.
    """
    if not text or status not in _TRACKER_STATUSES:
        return {}
    try:
        lang = detect_language(text)
        found: dict[str, Any] = {}
        if status is ParcelStatus.DELIVERED:
            found["left_at"] = find_left_at(text, lang, tracker=True)
        elif reference is not None:
            found["collect_by"] = find_collect_by(
                text,
                reference,
                tz,
                lang,
                pickup=status is ParcelStatus.READY_FOR_PICKUP,
            )
            if status is ParcelStatus.ATTEMPTED:
                found["next_attempt"] = find_next_attempt(text, reference, tz, lang)
    except Exception as exc:
        _LOGGER.debug("Detail check failed: %s", type(exc).__name__)
        return {}
    return {key: value for key, value in found.items() if value is not None}


_TRACKER_STATUSES = frozenset(
    {ParcelStatus.READY_FOR_PICKUP, ParcelStatus.ATTEMPTED, ParcelStatus.DELIVERED}
)
