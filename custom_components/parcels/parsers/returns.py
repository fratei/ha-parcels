"""Customer returns and refunds, told apart from parcels sent back.

Shipping e-mail uses "return" for three different things: the buyer
sending an item back (a customer return, which a carrier picks up), a
parcel going back to its sender undelivered, and the refund that follows
a customer return. Parsers read all three as ``RETURN``; ``reclassify``
sorts them out after the parser has run:

- a refund isn't a parcel event: it becomes ``NOT_PARCEL`` with the
  ``refund`` note, and the engine drops it, keeping only a count;
- a customer return becomes ``CUSTOMER_RETURN``, with the pickup date
  when the e-mail gives one ("Pickup date: next working day" included);
- a parcel going back to its sender stays ``RETURN``.

Everything is read from the folded subject and body, in the seven
languages the parsers support. Return policies, "free returns" and
similar footer phrases are blanked out first, so they never count.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import tzinfo
from enum import StrEnum
import re

from ..const import CONFIDENCE_APPLY, MailKind
from ._amazon_shopify_common import fold_text, label_values
from .base import Eta, MailMessage, ParsedShipment, ParseResult
from .eta import parse_eta

NOTE_REFUND = "refund"
NOTE_PICKUP_NEXT_WORKING_DAY = "pickup_next_working_day"
NOTE_RETURN_RECEIVED = "return_received"

# Confidence of a customer return found by its pickup label, and by the
# customer-return wording of a shop's subject alone.
PICKUP_CONFIDENCE = 0.8
SUBJECT_CONFIDENCE = 0.7

MAX_TEXT_CHARS = 20_000
# What an e-mail is about is said at the top; later mentions are footers.
MAX_TOP_CHARS = 3_000
# How far from a pickup label a return word may be.
RETURN_WORD_DISTANCE = 500


class ReturnClass(StrEnum):
    """What a return e-mail is about."""

    REFUND = "refund"
    # A customer return with a pickup label ("Pickup date: ...").
    PICKUP = "pickup"
    TO_SENDER = "to_sender"
    # Customer-return wording ("your return", "return label"...).
    CUSTOMER = "customer"


@dataclass(frozen=True, slots=True)
class Classification:
    """The class of a return e-mail and where its wording was found."""

    kind: ReturnClass
    in_subject: bool = False
    # The shop says it has the item back ("return received").
    received: bool = False
    # The language of the pickup label.
    language: str | None = None
    # A pickup label with customer-return wording ("your return") too.
    customer: bool = False
    # A refund only named before any return word, not said to be made.
    weak: bool = False


@dataclass(frozen=True, slots=True)
class Pickup:
    """When a carrier picks up a customer return, as the e-mail states it."""

    eta: Eta | None
    next_working_day: bool = False


@dataclass(frozen=True, slots=True)
class _Label:
    lang: str
    value: str
    in_subject: bool


def _words(*patterns: str) -> re.Pattern[str]:
    """Compile folded patterns into one whole-word regex."""
    return re.compile(rf"(?<![a-z0-9])(?:{'|'.join(patterns)})(?![a-z0-9])")


# Return policies, footer links and feedback requests: blanked out, so a
# "free returns" banner is never a return.
_MASKED_RE = _words(
    r"(?:returns?|refunds?)\s+(?:(?:and|&)\s+refunds?\s+)?polic(?:y|ies)",
    r"(?:free|easy)\s+returns?",
    r"returns?\s+(?:window|cent(?:re|er))",
    # Plural only: "your return and refund" is about a return.
    r"returns\s+(?:&|and)\s+(?:orders|refunds?)",
    r"return\s+or\s+replace",
    r"politica\s+de\s+(?:devoluc(?:ao|oes)|devolucion(?:es)?)",
    r"devoluc(?:ao|oes)\s+(?:gratis|gratuitas?)",
    r"devolucion(?:es)?\s+(?:gratis|gratuitas?)",
    r"devoluc(?:oes\s+e|iones\s+y)\s+reembolsos?",
    r"devoluc(?:oes\s+e\s+encomendas|iones\s+y\s+pedidos)",
    r"centro\s+de\s+devoluc(?:oes|iones)",
    r"kostenlose\s+rucksendung(?:en)?",
    r"rucksendebedingungen|ruckgaberecht|ruckgabebedingungen|rucksendezentrum",
    r"rucksendungen\s+(?:&|und)\s+bestellungen",
    r"zurucksenden\s+oder\s+ersetzen",
    r"(?:politique|conditions|centre)\s+de\s+retours?",
    r"retours?\s+gratuits?",
    r"retours\s+et\s+commandes",
    r"retourner\s+ou\s+remplacer",
    r"(?:merci\s+(?:pour|de)|donnez|partagez)\s+votre\s+retour",
    r"votre\s+retour\s+(?:d'experience|nous)",
    r"politica\s+(?:di|dei|sui)\s+res[oi]",
    r"(?:condizioni|centro)\s+(?:di\s+)?res[oi]",
    r"res[oi]\s+gratuit[oi]",
    r"resi\s+e\s+ordini",
    r"restituisci\s+o\s+sostituisci",
    r"retourbeleid|retourvoorwaarden|retourcentrum",
    r"gratis\s+retour(?:neren)?",
    r"retourneren\s+(?:en\s+bestellingen|of\s+vervangen)",
)

# Any word about sending something back. "Devolver" (pt) is left out: it's
# also the "will be returned" of a locker's collection deadline.
_RETURN_WORD_RE = _words(
    r"return\w*",
    r"devolu\w*",
    r"devuel\w*",
    r"(?:zu)?rucksend\w*",
    r"ruckgabe\w*",
    r"retour\w*",
    r"restitu(?!tie)\w*",
    r"res[oi]",
)

_REFUND_WORD_RE = _words(
    r"refund(?:ed|s)?",
    r"reembols\w*",
    r"(?:zu)?(?:ruck)?erstatt\w*",
    r"rembours\w*",
    r"rimbors\w*",
    r"terugbeta\w*",
    r"restitutie",
)

# A refund that was issued or is being processed. "Will be refunded" is a
# promise in a return's first e-mail, so it doesn't count.
_REFUND_DONE_RE = _words(
    r"(?:we've|we\s+have|we)\s+(?:issued|processed|initiated|sent)\s+"
    r"(?:a|your|the)\s+(?:full\s+|partial\s+)?refund",
    r"refund\s+(?:has\s+been|was|is\s+being)\s+(?:issued|processed|initiated"
    r"|approved|sent|credited)",
    r"refund\s+(?:issued|processed|approved)",
    r"(?:has|have)\s+been\s+refunded",
    r"(?:was|were)\s+refunded",
    r"reembolso\s+(?:foi\s+|ja\s+foi\s+)?(?:emitido|processado|efetuado|efectuado"
    r"|realizado|aprovado|concluido)",
    r"reembolso\s+esta\s+a\s+ser\s+processado",
    r"(?:emitimos|processamos|efetuamos|efectuamos|realizamos)\s+"
    r"(?:o\s+seu\s+|o\s+teu\s+|o\s+|um\s+)?reembolso",
    r"(?:foi|foram)\s+reembolsad[oa]s?",
    r"reembolso\s+(?:ha\s+sido\s+|se\s+ha\s+)?(?:emitido|procesado|realizado"
    r"|aprobado|efectuado|completado)",
    r"reembolso\s+se\s+esta\s+procesando",
    r"(?:hemos|se\s+ha)\s+(?:emitido|procesado|realizado|efectuado)\s+"
    r"(?:el\s+|tu\s+|su\s+|un\s+)?reembolso",
    r"(?:te|le|les)\s+hemos\s+reembolsado",
    r"(?:ha|han)\s+sido\s+reembolsad[oa]s?",
    r"(?:ruck)?erstattung\s+(?:wurde\s+|ist\s+)?(?:veranlasst|bearbeitet|erfolgt"
    r"|ausgefuhrt|abgeschlossen)",
    r"(?:wurde|wurden|haben\s+wir|ist)\s+(?:\w+\s+){0,3}(?:zuruck)?erstattet",
    r"remboursement\s+(?:a\s+ete\s+|est\s+)?(?:effectue|traite|emis|valide"
    r"|confirme|initie)",
    r"(?:avons|a)\s+(?:effectue|emis|traite|initie)\s+(?:votre|le|un)\s+"
    r"remboursement",
    r"(?:a|ont|avez)\s+ete\s+remboursee?s?",
    r"rimborso\s+(?:e\s+stato\s+)?(?:effettuato|emesso|elaborato|approvato"
    r"|confermato)",
    r"abbiamo\s+(?:effettuato|emesso|elaborato)\s+(?:il\s+tuo\s+|il\s+|un\s+)?"
    r"rimborso",
    r"(?:e|sono)\s+stat[oaie]\s+rimborsat[oaie]",
    r"terugbetaling\s+(?:is\s+)?(?:verwerkt|uitgevoerd|gedaan|voltooid|verstuurd)",
    r"(?:hebben|heeft)\s+(?:je\s+|uw\s+)?terugbetaling\s+(?:verwerkt|uitgevoerd)",
    r"(?:is|zijn|werd|werden)\s+terugbetaald",
    r"(?:hebben|heeft)\s+(?:\w+\s+){0,3}terugbetaald",
)

# A parcel going back to its sender undelivered. A delivery that failed
# counts too: a customer return is never "undeliverable".
_TO_SENDER_RE = _words(
    r"(?:could\s+not|couldn't|unable\s+to)\s+(?:be\s+)?deliver(?:ed)?",
    r"undeliverable",
    r"nao\s+(?:foi\s+possivel|conseguimos)\s+entregar",
    r"nao\s+pode\s+ser\s+entregue",
    r"no\s+(?:se\s+)?(?:ha\s+)?(?:podido|pudo|pudimos)\s+(?:ser\s+)?entregar",
    r"(?:konnte|konnten)\s+nicht\s+zugestellt",
    r"unzustellbar",
    r"n'a\s+pas\s+pu\s+etre\s+livree?",
    r"impossible\s+de\s+(?:vous\s+)?livrer",
    r"non\s+(?:e\s+stato\s+possibile|siamo\s+riusciti\s+a)\s+consegnare",
    r"kon(?:den)?\s+niet\s+(?:worden\s+)?(?:bezorgd|afgeleverd)",
    r"onbestelbaar",
    r"return(?:ed|ing)?\s+to\s+(?:the\s+)?(?:sender|shipper)",
    r"(?:sent|going|on\s+its\s+way)\s+back\s+to\s+(?:the\s+)?(?:sender|shipper)",
    r"devolvid[oa]s?\s+ao\s+(?:remetente|expedidor)",
    r"devoluc(?:ao|oes)\s+ao\s+(?:remetente|expedidor)",
    r"devuelt[oa]s?\s+al\s+remitente",
    r"devolucion\s+al\s+remitente",
    r"(?:zuruck|retour)\s+an\s+(?:den\s+)?(?:absender|versender)",
    r"an\s+den\s+(?:absender|versender)\s+zuruck\w*",
    r"(?:retourne|renvoye)e?s?\s+a\s+l'expediteur",
    r"retour\s+(?:a\s+l')?expediteur",
    r"(?:restituit|rispedit|ritornat)[oaie]\s+al\s+mittente",
    r"(?:reso|restituzione|ritorno)\s+al\s+mittente",
    r"retour\s+afzender",
    r"(?:terug|retour)\s+naar\s+(?:de\s+)?afzender",
    r"(?:geretourneerd|teruggestuurd)\s+naar\s+(?:de\s+)?afzender",
)

# The buyer sending an item back.
_CUSTOMER_RE = _words(
    r"your\s+return",
    r"return\s+(?:request(?:ed)?|label|confirmation|confirmed|received|started"
    r"|initiated|processed|authori[sz]ation|code|instructions|dropped\s+off"
    r"|shipment|pick[\s-]?up)",
    r"(?:a\s+sua|a\s+tua|sua)\s+devolucao",
    r"(?:pedido|etiqueta|codigo|instrucoes|confirmacao|recolha)\s+(?:de|da)\s+"
    r"devolucao",
    r"devolucao\s+(?:foi\s+)?(?:recebida|registada|registrada|confirmada|aceite"
    r"|aceita|iniciada|solicitada|pedida|criada|agendada)",
    r"(?:tu|su)\s+devolucion",
    r"(?:solicitud|etiqueta|codigo|instrucciones|confirmacion|recogida)\s+de\s+"
    r"(?:la\s+|tu\s+)?devolucion",
    r"devolucion\s+(?:ha\s+sido\s+)?(?:recibida|registrada|confirmada|aceptada"
    r"|iniciada|solicitada|creada|programada)",
    r"(?:ihre|deine)\s+(?:rucksendung|retoure|ruckgabe)",
    r"(?:rucksende|retouren|ruckgabe)(?:etikett|schein|label|code|anfrage|auftrag"
    r"|nummer)",
    r"(?:rucksendung|retoure)\s+(?:ist\s+|wurde\s+)?(?:erhalten|eingegangen"
    r"|angemeldet|bestatigt|registriert)",
    r"votre\s+(?:demande\s+de\s+)?retour",
    r"(?:demande|etiquette|bon|code|confirmation)\s+de\s+retour",
    r"retour\s+(?:a\s+ete\s+)?(?:recu|enregistre|accepte|confirme|initie)",
    r"(?:il\s+tuo|il\s+suo|tuo)\s+reso",
    r"(?:richiesta|etichetta|codice|conferma)\s+di\s+reso",
    r"reso\s+(?:e\s+stato\s+)?(?:ricevuto|registrato|accettato|confermato|avviato)",
    r"(?:je|jouw|uw)\s+retour(?:zending)?",
    r"retour(?:label|verzoek|aanvraag|code|aanmelding|formulier)",
    r"retour(?:zending)?\s+(?:is\s+)?(?:ontvangen|aangemeld|bevestigd"
    r"|geregistreerd)",
)

# The shop has the item back: the return is over.
_RECEIVED_RE = _words(
    r"return\s+(?:has\s+been\s+|was\s+|is\s+)?received",
    r"received\s+your\s+return",
    r"devolucao\s+(?:foi\s+)?recebida",
    r"recebemos\s+(?:a\s+sua\s+|a\s+tua\s+|a\s+)?devolucao",
    r"devolucion\s+(?:ha\s+sido\s+)?recibida",
    r"recibido\s+(?:tu|su|la)\s+devolucion",
    r"(?:rucksendung|retoure)\s+(?:ist\s+|wurde\s+)?(?:erhalten|eingegangen"
    r"|angekommen)",
    r"(?:ihre|deine)\s+(?:rucksendung|retoure)\s+(?:\w+\s+){0,2}erhalten",
    r"retour\s+(?:a\s+ete\s+|est\s+)?(?:bien\s+)?recu",
    r"recu\s+votre\s+retour",
    r"reso\s+(?:e\s+stato\s+)?ricevuto",
    r"ricevuto\s+il\s+(?:tuo\s+)?reso",
    r"retour(?:zending)?\s+(?:is\s+)?ontvangen",
    r"(?:je|uw)\s+retour(?:zending)?\s+(?:is\s+)?ontvangen",
)

# Labels of a return's pickup date. A locker's collection deadline ("Fecha
# límite de recogida") is a different label and never matches.
_PICKUP_LABELS: dict[str, re.Pattern[str]] = {
    "pt": _words(
        r"data\s+(?:de|da|prevista\s+(?:de|da))\s+recolha",
        r"recolha\s+(?:agendada|prevista|marcada)\s+(?:para|em|no|na)",
        r"dia\s+(?:de|da)\s+recolha",
    ),
    "es": _words(
        r"fecha\s+(?:de|de\s+la|prevista\s+de(?:\s+la)?)\s+recogida",
        r"recogida\s+(?:programada|prevista)\s+(?:para|el)",
        r"dia\s+de\s+(?:la\s+)?recogida",
    ),
    "en": _words(
        r"(?:pick[\s-]?up|collection)\s+(?:date|day)",
        r"(?:pick[\s-]?up|collection)\s+(?:is\s+)?scheduled\s+(?:for|on)",
        r"scheduled\s+(?:pick[\s-]?up|collection)(?:\s+(?:date|day))?",
    ),
    "de": _words(
        r"abhol(?:datum|termin|tag)",
        r"abholung\s+(?:am|geplant\s+(?:am|fur))",
    ),
    "fr": _words(
        r"date\s+(?:d'|de\s+l'|de\s+)(?:enlevement|collecte|ramassage)",
        r"(?:enlevement|collecte|ramassage)\s+(?:prevue?|programmee?)\s+(?:le|pour)",
    ),
    "it": _words(
        r"(?:data|giorno)\s+(?:di|del)\s+ritiro",
        r"ritiro\s+(?:previsto|programmato)\s+(?:il|per)",
    ),
    "nl": _words(
        r"ophaal(?:datum|dag|moment)",
        r"(?:wordt|worden)\s+opgehaald\s+op",
    ),
}

# "Next working day" as a pickup date: the working day after the e-mail.
_NEXT_WORKING_DAY_RE = _words(
    r"dia\s+util\s+seguinte",
    r"proximo\s+dia\s+util",
    r"dia\s+util\s+a\s+seguir",
    r"(?:siguiente|proximo)\s+dia\s+(?:habil|laborable)",
    r"dia\s+(?:habil|laborable)\s+siguiente",
    r"(?:next|following)\s+(?:business|working)\s+day",
    r"(?:nachste[nmrs]?|folgende[nmrs]?)\s+(?:werktag|arbeitstag)",
    r"prochain\s+jour\s+(?:ouvre|ouvrable)",
    r"jour\s+(?:ouvre|ouvrable)\s+suivant",
    r"lendemain\s+ouvre",
    r"(?:prossimo|primo)\s+giorno\s+(?:lavorativo|utile)",
    r"giorno\s+(?:lavorativo|utile)\s+successivo",
    r"(?:eerst)?volgende\s+werkdag",
)

_TOUCHED_KINDS = frozenset({MailKind.RETURN, MailKind.UNKNOWN, MailKind.NOT_PARCEL})


def _blank(match: re.Match[str]) -> str:
    return " " * len(match.group())


def _prepare(text: str) -> str:
    """Fold, then blank out return policies; offsets stay aligned with ``text``."""
    return _MASKED_RE.sub(_blank, fold_text(text))


def _return_words(folded: str) -> list[int]:
    """Return the offsets of return words, without "return to sender"."""
    plain = _TO_SENDER_RE.sub(_blank, folded)
    return [match.start() for match in _RETURN_WORD_RE.finditer(plain)]


def _labels(subject: str, subj: str, text: str, body: str) -> list[_Label]:
    """Return the pickup labels that have a value and a return word nearby.

    A return word counts when it's in the subject or within
    ``RETURN_WORD_DISTANCE`` characters of the label. Body labels come
    first, each part in reading order.
    """
    subject_return = bool(_return_words(subj))
    found: list[_Label] = []
    for source, folded, in_subject in ((text, body, False), (subject, subj, True)):
        words = _return_words(folded)
        hits: list[tuple[int, str, str]] = []
        for lang, pattern in _PICKUP_LABELS.items():
            for value in label_values(source, folded, pattern):
                if subject_return or any(
                    abs(pos - value.label_start) <= RETURN_WORD_DISTANCE
                    for pos in words
                ):
                    hits.append((value.label_start, lang, value.value))
        found.extend(_Label(lang, value, in_subject) for _, lang, value in sorted(hits))
    return found


def _refund_first(folded: str) -> bool:
    """Return True when a refund word comes before any return word."""
    refund = _REFUND_WORD_RE.search(folded)
    if refund is None:
        return False
    words = _return_words(folded)
    return not words or refund.start() < words[0]


def classify(subject: str, text: str) -> Classification | None:
    """Return what a return e-mail is about, or None when it says nothing.

    In order: a refund named in the subject (before any return word), a
    return pickup label, a refund the body says was issued, a parcel sent
    back to its sender, customer-return wording (the subject is read
    before the body), then, as a weak refund, a body that names a refund
    before any return word under a subject without one.
    """
    text = text[:MAX_TEXT_CHARS]
    subj = _prepare(subject)
    body = _prepare(text)
    if _refund_first(subj):
        return Classification(ReturnClass.REFUND, in_subject=True)
    top = body[:MAX_TOP_CHARS]
    if labels := _labels(subject, subj, text, body):
        first = labels[0]
        return Classification(
            ReturnClass.PICKUP,
            in_subject=first.in_subject,
            language=first.lang,
            customer=bool(_CUSTOMER_RE.search(subj) or _CUSTOMER_RE.search(top)),
        )
    if _REFUND_DONE_RE.search(top):
        return Classification(ReturnClass.REFUND)
    received = bool(_RECEIVED_RE.search(subj) or _RECEIVED_RE.search(top))
    for folded, in_subject in ((subj, True), (top, False)):
        if _TO_SENDER_RE.search(folded):
            return Classification(ReturnClass.TO_SENDER, in_subject=in_subject)
        if _CUSTOMER_RE.search(folded):
            return Classification(
                ReturnClass.CUSTOMER, in_subject=in_subject, received=received
            )
    if not _return_words(subj) and _refund_first(top):
        return Classification(ReturnClass.REFUND, weak=True)
    return None


def find_pickup(message: MailMessage, tz: tzinfo) -> Pickup | None:
    """Return the pickup date a return e-mail gives, if it gives one.

    "Next working day" wording is returned as such: the working day after
    the e-mail depends on the local holidays, which the engine knows.
    """
    text = message.text[:MAX_TEXT_CHARS]
    subject = message.subject
    for label in _labels(subject, _prepare(subject), text, _prepare(text)):
        if _NEXT_WORKING_DAY_RE.search(fold_text(label.value)):
            return Pickup(None, next_working_day=True)
        eta = parse_eta(label.value, message.date, tz, label.lang)
        if eta is not None:
            return Pickup(eta)
    return None


def reclassify(
    result: ParseResult, message: MailMessage, tz: tzinfo, *, merchant: bool
) -> ParseResult:
    """Tell refunds, customer returns and parcels sent back apart.

    Only ``RETURN``, ``UNKNOWN`` and ``NOT_PARCEL`` results change; a
    ``NOT_PARCEL`` result only gains the refund note. ``merchant`` is True
    for the shops' own parsers (Amazon, Shop, Shopify): their return
    e-mails are about customer returns unless they say otherwise. A weak
    refund only counts for a ``RETURN`` result or a sure ``NOT_PARCEL`` one,
    and a pickup label in an ``UNKNOWN`` e-mail needs customer-return wording
    too.
    """
    if result.kind not in _TOUCHED_KINDS:
        return result
    found = classify(message.subject, message.text)
    if found is None:
        if result.kind is MailKind.RETURN and merchant:
            return _customer_return(result, message, tz, result.confidence)
        return result
    if found.kind is ReturnClass.REFUND:
        if found.weak and not _ends_with_a_refund(result):
            return result
        return ParseResult(
            parser=result.parser,
            kind=MailKind.NOT_PARCEL,
            merchant=result.merchant,
            confidence=1.0,
            language=result.language,
            source=result.source,
            notes=(NOTE_REFUND,),
        )
    if found.kind is ReturnClass.TO_SENDER or result.kind is MailKind.NOT_PARCEL:
        return result
    if found.kind is ReturnClass.PICKUP:
        if result.kind is MailKind.UNKNOWN and not found.customer:
            return result
        confidence = max(result.confidence, PICKUP_CONFIDENCE)
        return _customer_return(result, message, tz, confidence)
    if result.kind is MailKind.RETURN:
        return _customer_return(
            result, message, tz, result.confidence, received=found.received
        )
    if merchant and found.in_subject:
        return _customer_return(
            result, message, tz, SUBJECT_CONFIDENCE, received=found.received
        )
    return result


def _ends_with_a_refund(result: ParseResult) -> bool:
    """Return True when a refund only named in the body decides the e-mail.

    It ends a "return" reading, or a sure "not about a parcel" one: neither
    is a parcel event. A doubtful "not a parcel", such as the AI's for an
    e-mail with a tracking number, waits for review instead.
    """
    if result.kind is MailKind.RETURN:
        return True
    return result.kind is MailKind.NOT_PARCEL and result.confidence >= CONFIDENCE_APPLY


def _customer_return(
    result: ParseResult,
    message: MailMessage,
    tz: tzinfo,
    confidence: float,
    *,
    received: bool = False,
) -> ParseResult:
    """Turn a result into a customer return, with the pickup date if given."""
    pickup = find_pickup(message, tz)
    first = result.shipments[0] if result.shipments else ParsedShipment()
    orders = result.order_numbers or first.order_numbers
    items = result.items or first.items
    notes: list[str] = []
    if pickup is not None and pickup.next_working_day:
        notes.append(NOTE_PICKUP_NEXT_WORKING_DAY)
    if received:
        notes.append(NOTE_RETURN_RECEIVED)
    shipment = ParsedShipment(
        carrier=first.carrier,
        tracking_number=first.tracking_number,
        eta=pickup.eta if pickup is not None else None,
        order_numbers=orders,
        items=items,
        tracking_url=first.tracking_url,
    )
    return ParseResult(
        parser=result.parser,
        kind=MailKind.CUSTOMER_RETURN,
        merchant=result.merchant,
        order_numbers=orders,
        shipments=[shipment],
        items=items,
        confidence=confidence,
        language=result.language,
        source=result.source,
        notes=tuple(notes),
    )
