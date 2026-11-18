"""Parsers for Shopify store notifications and Shop app delivery updates.

Most Shopify stores send Shopify's standard customer notifications, often
lightly customised, from their own domain: order and shipping
confirmations, shipping updates, out-for-delivery and delivered notices.
The subject identifies the notification (sentences at the top of the body
are a weaker fallback), the "#1001" order name ties the e-mails of one
order together, and a tracking number is only kept when it validates for
the carrier named next to it, the carrier website it links to, or the
carrier its format identifies. The Shop app (shop.app) sends delivery
updates for orders from many stores; the store's name is read from the
subject. Links are only read as strings, never fetched.

A delivery PIN or one-time password is read for any kind; an e-mail whose
only news is such a code for an order or a tracking number gets the kind
``CODE``. Codes are hidden before order names and tracking numbers are
read, so a PIN is never taken for either.
"""

from __future__ import annotations

from datetime import tzinfo
import re

from ..const import MailKind
from . import tracking
from ._amazon_shopify_common import (
    MAX_ITEMS,
    MAX_MERCHANT_CHARS,
    MAX_STATUS_CHARS,
    FoundNumber,
    KindPattern,
    add_item,
    clean_name,
    clip,
    detect_kind,
    event_time,
    find_numbers,
    fold_text,
    iter_lines,
    kind_table,
    pickup_point,
    quantity_items,
    today_eta,
    url_org,
    url_path,
)
from .base import Eta, MailMessage, ParsedShipment, ParseResult, SenderVerdict
from .codes import find_code, has_code_label, mask_codes
from .eta import find_eta
from .items import before_recommendations, unique_items
from .senders import organizational_domain

SHOPIFY_PARSER = "shopify"
SHOP_PARSER = "shop"

# Shopify order names: "#1001", possibly with a store prefix or suffix.
_ORDER_NAME_RE = re.compile(
    r"(?<![\w&#])#\s?(?P<name>(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9][A-Za-z0-9_-]{0,23})"
    r"(?![\w-])"
)
# A line item in Shopify's templates: "Product title \u00d7 2". A title may end
# in a digit ("Notebook A5") only before a real multiplication sign that isn't
# followed by a unit, so sizes such as "30 x 40 cm" are not taken for items.
_ITEM_LINE_RE = re.compile(
    r"^[ \t]*(?P<title>\S[^\n]*?(?:[^\d\s]|\d(?=[ \t]+\u00d7[ \t]*\d{1,3}"
    r"(?![\d.,])(?![ \t]*[^\W\d_]))))"
    r"[ \t]+[\u00d7xX][ \t]*\d{1,3}(?![\d.,])",
    re.MULTILINE,
)
# Platform domains: never a store's own name.
_PLATFORM_ORGS = frozenset(
    {"shopify.com", "shopifyemail.com", "myshopify.com", "shop.app"}
)
_MAX_SHIPMENTS = 10

_ORDER_KINDS = frozenset({MailKind.ORDER, MailKind.CANCELLED, MailKind.RETURN})
_NO_ETA_KINDS = frozenset(
    {
        MailKind.DELIVERED,
        MailKind.READY_FOR_PICKUP,
        MailKind.CANCELLED,
        MailKind.RETURN,
        MailKind.CODE,
    }
)
# Kinds whose e-mails may give a locker code under a bare "Code:" label.
_LOCKER_KINDS = frozenset({MailKind.READY_FOR_PICKUP, MailKind.ATTEMPTED})
# Kinds without a delivery code: the parcel won't be delivered.
_NO_CODE_KINDS = frozenset({MailKind.CANCELLED, MailKind.RETURN})
# Confidence of a code-only e-mail, with and without a code label in the
# subject.
_CODE_CONFIDENCE = {True: 0.9, False: 0.8}

# Subjects of Shopify's standard notifications, on the folded subject
# without the order name, in order of precedence.
_SHOPIFY_SUBJECT: tuple[KindPattern, ...] = (
    *kind_table(
        MailKind.CANCELLED,
        en=r"cancel+ed|cancel+ation",
        pt=r"cancelad[oa]|cancelamento",
        es=r"cancelad[oa]|cancelacion",
        de=r"storniert|stornierung",
        fr=r"annulee?|annulation",
        it=r"annullat[oa]|cancellat[oa]|annullamento",
        nl=r"geannuleerd|annulering",
    ),
    *kind_table(
        MailKind.RETURN,
        en=r"refund\w*|return\s+(?:received|processed|confirmed|label)",
        pt=r"reembols\w*|devolucao",
        es=r"reembols\w*|devolucion",
        de=r"(?:ruck)?erstattung\w*|rucksendung|retoure",
        fr=r"rembours\w*|votre\s+retour|retour\s+(?:recu|accepte|enregistre)",
        it=r"rimbors\w*|il\s+tuo\s+reso|reso\s+(?:ricevuto|accettato|registrato)",
        nl=r"terugbetal\w*|restitutie|(?:je|uw)\s+retour|retour\s+ontvangen",
    ),
    *kind_table(
        MailKind.ATTEMPTED,
        en=r"delivery\s+attempt(?:ed)?|attempted\s+delivery|missed\s+delivery"
        r"|(?:could\s+not|couldn't)\s+be\s+delivered",
        pt=r"tentativa\s+de\s+entrega|nao\s+foi\s+possivel\s+entregar",
        es=r"intento\s+de\s+entrega|no\s+se\s+(?:ha\s+)?pudo\s+entregar",
        de=r"zustellversuch|nicht\s+zugestellt\s+werden",
        fr=r"tentative\s+de\s+livraison|livraison\s+impossible",
        it=r"tentativo\s+di\s+consegna|mancata\s+consegna",
        nl=r"bezorgpoging|niet\s+bezorgd\s+kunnen",
    ),
    *kind_table(
        MailKind.READY_FOR_PICKUP,
        en=r"ready\s+for\s+(?:local\s+)?(?:pick\s?-?up|collection)"
        r"|ready\s+to\s+(?:be\s+)?(?:picked\s+up|collected)",
        pt=r"pront[oa]\s+para\s+(?:levantamento|recolha|levantar)",
        es=r"list[oa]\s+para\s+(?:recoger|retirar|recogida)",
        de=r"abholbereit|bereit\s+zur\s+abholung|zur\s+abholung\s+bereit",
        fr=r"prete?\s+(?:a\s+etre\s+retiree?|pour\s+le\s+retrait|a\s+retirer)",
        it=r"pront[oa]\s+(?:per\s+il\s+ritiro|da\s+ritirare)",
        nl=r"klaar\s+(?:om\s+(?:op|af)\s+te\s+halen|voor\s+(?:afhalen|ophalen))",
    ),
    *kind_table(
        MailKind.OUT_FOR_DELIVERY,
        en=r"out\s+for\s+delivery|arriving\s+today",
        pt=r"saiu\s+para\s+(?:a\s+)?entrega|em\s+distribuicao|chega\s+hoje",
        es=r"en\s+reparto|(?:salio|ha\s+salido)\s+(?:a|para)\s+(?:su\s+|la\s+)?"
        r"(?:reparto|entrega)|llega\s+hoy",
        de=r"in\s+zustellung|wird\s+(?:heute\s+)?zugestellt|kommt\s+heute",
        fr=r"en\s+cours\s+de\s+livraison|arrive\s+aujourd'hui",
        it=r"in\s+consegna|arriva\s+oggi",
        nl=r"wordt\s+(?:vandaag\s+)?bezorgd|komt\s+vandaag",
    ),
    *kind_table(
        MailKind.DELIVERED,
        en=r"delivered",
        pt=r"entregues?",
        es=r"entregad[oa]s?",
        de=r"zugestellt|geliefert",
        fr=r"livree?s?",
        it=r"consegnat[oa]",
        nl=r"bezorgd|afgeleverd",
    ),
    # "A shipment from order #1001 has been updated"; "Order #1001 has been
    # updated" alone is an edited order, not a shipping update.
    *kind_table(
        MailKind.IN_TRANSIT,
        en=r"shipping\s+update|shipment\s+update|tracking\s+update"
        r"|shipment\s+(?:from\s+(?:your\s+)?order\s+)?(?:has\s+been\s+)?updated",
        pt=r"atualizacao\s+d[oe]\s+envio"
        r"|envio\s+(?:da\s+(?:sua\s+)?encomenda\s+)?foi\s+atualizado",
        es=r"actualizacion\s+del?\s+envio"
        r"|envio\s+(?:del\s+pedido\s+)?(?:ha\s+sido|fue)\s+actualizado"
        r"|se\s+(?:ha\s+)?actualizado\s+un\s+envio|se\s+actualizo\s+un\s+envio",
        de=r"versandaktualisierung|versand-?update|sendungsaktualisierung"
        r"|sendung\s+(?:aus\s+(?:der\s+)?bestellung\s+)?wurde\s+aktualisiert",
        fr=r"mise\s+a\s+jour\s+(?:de\s+l'expedition|d'expedition|de\s+la\s+livraison)"
        r"|expedition\s+(?:de\s+la\s+commande\s+)?a\s+ete\s+mise\s+a\s+jour",
        it=r"aggiornamento\s+(?:sulla|della)\s+spedizione"
        r"|spedizione\s+(?:dell'ordine\s+)?e\s+stata\s+aggiornata",
        nl=r"verzendupdate|verzending\s+bijgewerkt"
        r"|zending\s+(?:van\s+(?:je\s+|uw\s+)?bestelling\s+)?is\s+bijgewerkt",
    ),
    *kind_table(
        MailKind.SHIPPED,
        en=r"on\s+(?:the|its)\s+way|shipped",
        pt=r"a\s+caminho|enviad[oa]|expedid[oa]",
        es=r"en\s+camino|enviad[oa]",
        de=r"unterwegs|versandt|verschickt",
        fr=r"en\s+route|expediee?",
        it=r"in\s+arrivo|spedit[oa]",
        nl=r"onderweg|verzonden",
    ),
    *kind_table(
        MailKind.ORDER,
        en=r"confirmed|order\s+confirmation|thank\s+you\s+for\s+your\s+(?:purchase|order)",
        pt=r"confirmad[oa]|confirmacao\s+d[ae]\s+encomenda",
        es=r"confirmad[oa]|confirmacion\s+del?\s+pedido",
        de=r"bestatigt|bestellbestatigung",
        fr=r"confirmee?|confirmation\s+de\s+(?:votre\s+)?commande",
        it=r"confermat[oa]|conferma\s+(?:d'ordine|dell'ordine|ordine)",
        nl=r"bevestigd|bestelbevestiging",
    ),
)

# Sentences of the standard templates, for subjects a store has rewritten.
_ORDER_WORDS = {
    "en": r"your\s+order",
    "pt": r"a\s+sua\s+encomenda",
    "es": r"tu\s+pedido",
    "de": r"(?:ihre|deine)\s+bestellung",
    "fr": r"votre\s+commande",
    "it": r"il\s+tuo\s+ordine",
    "nl": r"(?:je|uw)\s+bestelling",
}


def _sentences(kind: MailKind, **by_lang: str) -> tuple[KindPattern, ...]:
    """Patterns for "<your order> <verb phrase>" in each language."""
    return kind_table(
        kind,
        **{
            lang: rf"{_ORDER_WORDS[lang]}\s+(?:{verb})"
            for lang, verb in by_lang.items()
        },
    )


_SHOPIFY_BODY: tuple[KindPattern, ...] = (
    *_sentences(
        MailKind.CANCELLED,
        en=r"(?:has\s+been|was)\s+cancel+ed",
        pt=r"foi\s+cancelada",
        es=r"(?:ha\s+sido|fue)\s+cancelado",
        de=r"wurde\s+storniert",
        fr=r"a\s+ete\s+annulee",
        it=r"e\s+stato\s+annullato",
        nl=r"is\s+geannuleerd",
    ),
    *_sentences(
        MailKind.OUT_FOR_DELIVERY,
        en=r"is\s+out\s+for\s+delivery",
        pt=r"saiu\s+para\s+(?:a\s+)?entrega",
        es=r"esta\s+en\s+reparto",
        de=r"ist\s+in\s+zustellung|wird\s+heute\s+zugestellt",
        fr=r"est\s+en\s+cours\s+de\s+livraison",
        it=r"e\s+in\s+consegna",
        nl=r"wordt\s+vandaag\s+bezorgd",
    ),
    *_sentences(
        MailKind.DELIVERED,
        en=r"(?:has\s+been|was)\s+delivered",
        pt=r"foi\s+entregue",
        es=r"(?:ha\s+sido|fue)\s+entregado",
        de=r"wurde\s+zugestellt",
        fr=r"a\s+ete\s+livree",
        it=r"e\s+stato\s+consegnato",
        nl=r"is\s+bezorgd",
    ),
    *_sentences(
        MailKind.SHIPPED,
        en=r"is\s+on\s+(?:the|its)\s+way|has\s+(?:been\s+)?shipped",
        pt=r"esta\s+a\s+caminho|foi\s+enviada",
        es=r"esta\s+en\s+camino|(?:ha\s+sido|fue)\s+enviado",
        de=r"ist\s+unterwegs|wurde\s+versandt",
        fr=r"est\s+en\s+route|a\s+ete\s+expediee",
        it=r"e\s+in\s+arrivo|e\s+stato\s+spedito",
        nl=r"is\s+onderweg|is\s+verzonden",
    ),
    *kind_table(
        MailKind.ORDER,
        en=r"thank\s+you\s+for\s+your\s+purchase",
        pt=r"obrigad[oa]\s+pela\s+(?:sua\s+)?compra",
        es=r"gracias\s+por\s+(?:tu|su)\s+compra",
        de=r"(?:vielen\s+)?dank\s+fur\s+(?:ihren|deinen)\s+einkauf",
        fr=r"merci\s+pour\s+votre\s+(?:achat|commande)",
        it=r"grazie\s+per\s+(?:il\s+tuo\s+|l')acquisto",
        nl=r"bedankt\s+voor\s+(?:je|uw)\s+aankoop",
    ),
)

# Shop app updates, in order of precedence (subject first, then body).
_SHOP_PATTERNS: tuple[KindPattern, ...] = (
    *kind_table(
        MailKind.ATTEMPTED,
        en=r"delivery\s+attempt(?:ed)?|attempted\s+delivery|missed\s+delivery"
        r"|(?:could\s+not|couldn't)\s+be\s+delivered",
        pt=r"tentativa\s+de\s+entrega",
        es=r"intento\s+de\s+entrega",
        de=r"zustellversuch",
        fr=r"tentative\s+de\s+livraison",
        it=r"tentativo\s+di\s+consegna",
        nl=r"bezorgpoging",
    ),
    *kind_table(
        MailKind.READY_FOR_PICKUP,
        en=r"ready\s+for\s+(?:pick\s?-?up|collection)"
        r"|ready\s+to\s+(?:be\s+)?(?:picked\s+up|collected)",
        pt=r"pront[oa]\s+para\s+(?:levantamento|recolha)",
        es=r"list[oa]\s+para\s+recoger",
        de=r"abholbereit|bereit\s+zur\s+abholung",
        fr=r"prete?\s+a\s+etre\s+retiree?",
        it=r"pront[oa]\s+per\s+il\s+ritiro",
        nl=r"klaar\s+om\s+op\s+te\s+halen|ligt\s+klaar",
    ),
    *kind_table(
        MailKind.DELAYED,
        en=r"delayed|running\s+late",
        pt=r"atrasad[oa]",
        es=r"retrasad[oa]",
        de=r"verspatet|verzogert",
        fr=r"en\s+retard|retardee?",
        it=r"in\s+ritardo",
        nl=r"vertraagd",
    ),
    *kind_table(
        MailKind.OUT_FOR_DELIVERY,
        en=r"out\s+for\s+delivery|arriving\s+today|arrives\s+today",
        pt=r"saiu\s+para\s+(?:a\s+)?entrega|chega\s+hoje",
        es=r"en\s+reparto|llega\s+hoy",
        de=r"in\s+zustellung|wird\s+heute\s+zugestellt|kommt\s+heute",
        fr=r"en\s+cours\s+de\s+livraison|arrive\s+aujourd'hui",
        it=r"in\s+consegna|arriva\s+oggi",
        nl=r"wordt\s+vandaag\s+bezorgd|komt\s+vandaag",
    ),
    *kind_table(
        MailKind.DELIVERED,
        en=r"delivered",
        pt=r"entregue",
        es=r"entregad[oa]",
        de=r"zugestellt",
        fr=r"livree?",
        it=r"consegnat[oa]",
        nl=r"bezorgd|afgeleverd",
    ),
    *kind_table(
        MailKind.SHIPPED,
        en=r"shipped",
        pt=r"enviad[oa]|expedid[oa]",
        es=r"enviad[oa]",
        de=r"versandt|verschickt",
        fr=r"expediee?",
        it=r"spedit[oa]",
        nl=r"verzonden|verstuurd",
    ),
    *kind_table(
        MailKind.IN_TRANSIT,
        en=r"on\s+(?:its|the)\s+way|in\s+transit",
        pt=r"a\s+caminho|em\s+transito",
        es=r"en\s+camino|en\s+transito",
        de=r"unterwegs|auf\s+dem\s+weg",
        fr=r"en\s+route|en\s+chemin|en\s+transit",
        it=r"in\s+arrivo|in\s+viaggio|in\s+transito",
        nl=r"onderweg",
    ),
)

# "Your order from <store> is on its way", "Your <store> order ...".
_STORE_END = (
    r"is|has|was|will|arrives|esta|foi|vai|chega|saiu|ha\s+sido|se\s+ha|fue|llega"
    r"|ist|wird|wurde|kommt|est|a\s+ete|arrive|sera|e\s+(?:in|stat[oa]|pront[oa])"
    r"|arriva|sara|wordt|werd|komt|ligt"
)
_STORE_RES = (
    re.compile(
        r"(?<![a-z0-9])(?:order|package|parcel|shipment|encomenda|pedido|paquete"
        r"|envio|bestellung|paket|sendung|commande|colis|ordine|pacco|spedizione"
        r"|bestelling|pakket|zending)\s+(?:from|da|de|do|del|von|bei|chez|di|dal"
        r"|della|van|bij)\s+(?P<store>[^\s#].*?)"
        rf"(?=\s+(?:{_STORE_END})(?![a-z0-9])|\s*(?:[:!?,|]|\.(?:\s|$))|\s+-\s|\s*$)",
        re.MULTILINE,
    ),
    re.compile(r"(?<![a-z0-9])your\s+(?P<store>[^\s#][^\n]*?)\s+order(?![a-z0-9])"),
)
# Names that refer to the app itself, not to a store.
_NOT_STORES = frozenset({"shop", "shop app", "the shop app", "the shop", "app"})


def _order_name(text: str) -> str | None:
    """Return the first "#1001" style order name in a text."""
    match = _ORDER_NAME_RE.search(text)
    return f"#{match.group('name')}" if match else None


def _items(message: MailMessage, folded: str) -> tuple[str, ...]:
    """Return the product titles of the line items.

    Products below a recommendations heading ("You may also like") weren't
    ordered; a link's text (a "Buy again" button) is never that heading.
    """
    text = before_recommendations(
        message.text, buttons=[link.text for link in message.links]
    )
    folded = folded[: len(text)]
    items: list[str] = []
    for match in _ITEM_LINE_RE.finditer(text):
        add_item(items, match.group("title"))
        if len(items) >= MAX_ITEMS:
            break
    if not items:
        quantity_items(text, folded, items)
    return tuple(unique_items(items))


def _store_name(message: MailMessage) -> str | None:
    """Return the store's name: the sender's name, its home link or domain."""
    if name := clean_name(message.sender_name):
        return name
    org = organizational_domain(message.sender_domain) if message.sender_domain else ""
    if not org or org in _PLATFORM_ORGS:
        return None
    for link in message.links:
        if (
            url_org(link.url) == org
            and url_path(link.url) in ("", "/")
            and (name := clean_name(link.text))
        ):
            return name
    label = org.split(".", 1)[0].replace("_", "-")
    words = [part.capitalize() for part in label.split("-") if part]
    return clip(" ".join(words), MAX_MERCHANT_CHARS) or None


def _eta(
    kind: MailKind, message: MailMessage, tz: tzinfo, lang: str | None
) -> Eta | None:
    """Return the stated delivery estimate; today for out-for-delivery."""
    if kind in _NO_ETA_KINDS:
        return None
    eta = find_eta(message.text, message.date, tz, lang)
    if eta is None and kind is MailKind.OUT_FOR_DELIVERY:
        eta = today_eta(message, tz)
    return eta


def _numbers(message: MailMessage, plain: str, order: str | None) -> list[FoundNumber]:
    """Return the validated tracking numbers of a shipping notification.

    ``plain`` is the body with its delivery codes hidden.
    """
    exclude = frozenset({order.lstrip("#").upper()}) if order else frozenset()
    return find_numbers(
        plain,
        fold_text(plain),
        message.links,
        exclude=exclude,
        window=100,
        allow_other=True,
    )[:_MAX_SHIPMENTS]


def _order_and_numbers(
    message: MailMessage, kind: MailKind
) -> tuple[tuple[str, ...], list[FoundNumber], str | None]:
    """Return the order names, the tracking numbers and the delivery code.

    Codes are hidden before the order name and the numbers are read, and a
    code equal to either is never taken.
    """
    locker = kind in _LOCKER_KINDS
    plain = mask_codes(message.text, locker=locker)
    order = _order_name(mask_codes(message.subject, locker=locker)) or _order_name(
        plain
    )
    orders = (order,) if order else ()
    numbers = [] if kind in _ORDER_KINDS else _numbers(message, plain, order)
    code: str | None = None
    if kind not in _NO_CODE_KINDS:
        exclude = [*orders, *(found.number for found in numbers)]
        code = find_code(message.text, exclude=exclude, locker=locker) or find_code(
            message.subject, exclude=exclude, locker=locker
        )
    return orders, numbers, code


def _shipments(
    kind: MailKind,
    message: MailMessage,
    tz: tzinfo,
    lang: str | None,
    folded: str,
    numbers: list[FoundNumber],
    orders: tuple[str, ...],
    items: tuple[str, ...],
    code: str | None = None,
) -> list[ParsedShipment]:
    """Build one shipment per tracking number (or one without a number)."""
    if kind in _ORDER_KINDS:
        return [
            ParsedShipment(
                kind=MailKind.ORDER if kind is MailKind.ORDER else None,
                eta=_eta(kind, message, tz, lang),
                pickup_code=code,
                order_numbers=orders,
                items=items,
            )
        ]
    eta = _eta(kind, message, tz, lang)
    when = event_time(folded, kind, message, tz, lang)
    point = (
        pickup_point(message.text, folded)
        if kind is MailKind.READY_FOR_PICKUP
        else None
    )
    shipment_kind = MailKind.CODE if kind is MailKind.CODE else None
    if not numbers:
        return [
            ParsedShipment(
                kind=shipment_kind,
                eta=eta,
                event_time=when,
                pickup_point=point,
                pickup_code=code,
                order_numbers=orders,
                items=items,
            )
        ]
    single = len(numbers) == 1
    return [
        ParsedShipment(
            carrier=found.carrier,
            tracking_number=found.number,
            kind=shipment_kind,
            eta=eta,
            event_time=when,
            pickup_point=point,
            pickup_code=code,
            order_numbers=orders,
            items=items if single else (),
            tracking_url=tracking.tracking_url(found.carrier, found.number),
        )
        for found in numbers
    ]


def parse_shopify(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult | None:
    """Parse a notification sent by a Shopify store.

    Returns None when the e-mail isn't one of Shopify's order or shipping
    notifications (marketing, account e-mails, unknown layouts). An e-mail
    that only gives a delivery code for an order or a tracking number is a
    CODE result.
    """
    subject = _ORDER_NAME_RE.sub(" ", fold_text(message.subject))
    folded = fold_text(message.text)
    pattern, from_subject = detect_kind(
        subject, folded, _SHOPIFY_SUBJECT, _SHOPIFY_BODY
    )
    # Without a status, the e-mail can only be about a delivery code.
    kind = pattern.kind if pattern is not None else MailKind.CODE
    orders, numbers, code = _order_and_numbers(message, kind)
    if not orders and not numbers:
        return None
    if kind is MailKind.CODE and code is None:
        return None
    lang = message.language or (pattern.lang if pattern is not None else None)
    items = _items(message, folded)
    validated = any(found.carrier != "other" for found in numbers)
    if kind is MailKind.CODE:
        confidence = _CODE_CONFIDENCE[has_code_label(message.subject)]
    elif kind in _ORDER_KINDS:
        confidence = 0.9 if from_subject else 0.6
    elif from_subject:
        confidence = 0.9 if validated else 0.7
    else:
        confidence = 0.6 if numbers else 0.5
    return ParseResult(
        parser=SHOPIFY_PARSER,
        kind=kind,
        merchant=_store_name(message),
        order_numbers=orders,
        shipments=_shipments(
            kind, message, tz, lang, folded, numbers, orders, items, code
        ),
        items=items,
        confidence=confidence,
        language=lang,
    )


def _shop_store(text: str, folded: str) -> tuple[str | None, tuple[int, int]]:
    """Return the store named in a Shop app sentence and its offsets."""
    for regex in _STORE_RES:
        for match in regex.finditer(folded):
            start, end = match.span("store")
            name = clean_name(text[start:end])
            if name and fold_text(name) not in _NOT_STORES:
                return clip(name, MAX_MERCHANT_CHARS), (start, end)
    return None, (0, 0)


def _body_store(text: str, folded: str) -> str | None:
    """Return the store named in a sentence near the top of the body."""
    for offset, line in iter_lines(folded[:MAX_STATUS_CHARS]):
        if line.strip():
            store, _ = _shop_store(text[offset : offset + len(line)], line)
            if store is not None:
                return store
    return None


def parse_shop(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult | None:
    """Parse a delivery update sent by the Shop app.

    The store the order came from is the merchant. Returns None for e-mails
    that aren't delivery updates; an e-mail that only gives a delivery code
    for an order or a tracking number is a CODE result.
    """
    folded_subject = fold_text(message.subject)
    store, (start, end) = _shop_store(message.subject, folded_subject)
    folded = fold_text(message.text)
    if store is None:
        store = _body_store(message.text, folded)
    # The store's name must not decide the kind ("Delivered Goods Co").
    subject = folded_subject[:start] + " " * (end - start) + folded_subject[end:]
    subject = _ORDER_NAME_RE.sub(" ", subject)
    pattern, from_subject = detect_kind(subject, folded, _SHOP_PATTERNS, _SHOP_PATTERNS)
    # Without a status, the e-mail can only be about a delivery code.
    kind = pattern.kind if pattern is not None else MailKind.CODE
    orders, numbers, code = _order_and_numbers(message, kind)
    if kind is MailKind.CODE and (code is None or not (numbers or orders)):
        return None
    if not (numbers or orders or store):
        return None
    lang = message.language or (pattern.lang if pattern is not None else None)
    items = _items(message, folded)
    if kind is MailKind.CODE:
        confidence = _CODE_CONFIDENCE[has_code_label(message.subject)]
    elif not from_subject:
        confidence = 0.5
    elif any(found.carrier != "other" for found in numbers):
        confidence = 0.9
    elif numbers or orders:
        confidence = 0.7
    else:
        confidence = 0.6 if store else 0.5
    return ParseResult(
        parser=SHOP_PARSER,
        kind=kind,
        merchant=store,
        order_numbers=orders,
        shipments=_shipments(
            kind, message, tz, lang, folded, numbers, orders, items, code
        ),
        items=items,
        confidence=confidence,
        language=lang,
    )
