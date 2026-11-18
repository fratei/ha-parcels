"""Parser for Amazon order and shipping e-mails.

Amazon's layouts differ per marketplace and change often, so the parser is
driven by keywords and labels rather than one fixed template. The subject
gives the e-mail's kind (with phrases near the top of the body as a weaker
fallback), labels such as "Arriving:", "Chegada:" or "Zustellung:" give
the delivery estimates, and the order number, the shipment ID (from the
"Track package" link) and any carrier tracking number are collected from
the whole e-mail. Links are only read as strings, never fetched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import tzinfo
import re
from urllib.parse import urlencode, urlsplit, urlunsplit

from ..const import MailKind
from . import tracking
from ._amazon_shopify_common import (
    MAX_POINT_CHARS,
    FoundNumber,
    KindPattern,
    add_item,
    carrier_mentions,
    clip,
    detect_kind,
    event_time,
    find_numbers,
    fold_text,
    kind_table,
    label_values,
    line_bounds,
    local_date,
    own_https_url,
    pickup_details,
    quantity_items,
    query_params,
    today_eta,
    unwrap_url,
    url_host,
    url_path,
    words_regex,
)
from .base import Eta, Link, MailMessage, ParsedShipment, ParseResult, SenderVerdict
from .eta import find_eta, parse_eta, parse_time_window
from .senders import lookup

PARSER = "amazon"
MERCHANT = "Amazon"

ORDER_NUMBER_RE = re.compile(r"(?<![\dA-Za-z-])\d{3}-\d{7}-\d{7}(?![\d-])")
# Digital orders (Kindle, apps, video) never ship a parcel.
_DIGITAL_ORDER_RE = re.compile(r"(?<![\dA-Za-z-])D\d{2}-\d{7}-\d{7}(?![\d-])")
_SHIPMENT_ID_RE = re.compile(r"[A-Za-z0-9]{6,20}")
_ASIN_PATH_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?=[/?#]|$)")
# A quoted product title in a folded subject; truncated titles lose the
# closing quote.
_QUOTED_RE = re.compile(r'"[^"]*(?:"|$)')
_KEPT_PARAMS = frozenset({"orderid", "shipmentid", "packageindex", "itemid"})
_MAX_ORDERS = 10

# Kinds whose key identifier is the order number.
_ORDER_KINDS = frozenset({MailKind.ORDER, MailKind.CANCELLED, MailKind.RETURN})
# Confidence by (kind found in the subject, key identifier present).
_CONFIDENCE: dict[tuple[bool, bool], float] = {
    (True, True): 0.9,
    (True, False): 0.7,
    (False, True): 0.6,
    (False, False): 0.5,
}
# Kinds that carry a delivery estimate.
_ETA_KINDS = frozenset(
    {
        MailKind.ORDER,
        MailKind.SHIPPED,
        MailKind.IN_TRANSIT,
        MailKind.OUT_FOR_DELIVERY,
        MailKind.DELAYED,
        MailKind.ATTEMPTED,
    }
)


# Subject patterns, on the folded subject without quoted product titles,
# in order of precedence.
_SUBJECT_PATTERNS: tuple[KindPattern, ...] = (
    *kind_table(
        MailKind.CANCELLED,
        en=r"cancel(?:l?ed|lation)",
        pt=r"cancelad[oa]s?|cancelamento",
        es=r"cancelad[oa]s?|cancelacion",
        de=r"storniert|stornierung|storno",
        fr=r"annulee?s?|annulation",
        it=r"annullat[oaie]|cancellat[oaie]|annullamento",
        nl=r"geannuleerd|annulering",
    ),
    *kind_table(
        MailKind.RETURN,
        en=r"refund(?:ed|s)?|your\s+return|return\s+(?:received|processed|started"
        r"|requested|request|label|confirmation|confirmed|dropped\s+off)",
        pt=r"reembols\w*|devolucao|devolvid[oa]",
        es=r"reembols\w*|devolucion|devuelt[oa]",
        de=r"erstattung|ruckerstattung|erstattet|rucksendung|retoure",
        fr=r"rembours\w*|votre\s+retour|retour\s+(?:recu|enregistre|accepte)",
        it=r"rimbors\w*|il\s+tuo\s+reso|reso\s+(?:ricevuto|accettato|registrato)",
        nl=r"terugbetal\w*|terugbetaald|restitutie|(?:je|uw)\s+retour"
        r"|retour\s+(?:ontvangen|aangemeld)",
    ),
    *kind_table(
        MailKind.ATTEMPTED,
        en=r"delivery\s+attempt(?:ed)?|attempted\s+delivery|missed\s+delivery"
        r"|we\s+(?:attempted|tried)\s+to\s+deliver"
        r"|(?:could\s+not|couldn't|unable\s+to)\s+(?:be\s+)?deliver(?:ed)?",
        pt=r"tentativa\s+de\s+entrega|tentamos\s+entregar"
        r"|nao\s+(?:foi\s+possivel|conseguimos)\s+entregar",
        es=r"intento\s+de\s+entrega|intentamos\s+entregar"
        r"|hemos\s+intentado\s+entregar|no\s+(?:hemos\s+podido|pudimos)\s+entregar",
        de=r"zustellversuch|zustellung\s+nicht\s+moglich"
        r"|(?:konnte|konnten)\s+nicht\s+zugestellt|nicht\s+zugestellt\s+werden",
        fr=r"tentative\s+de\s+livraison|nous\s+avons\s+tente\s+de\s+livrer"
        r"|livraison\s+(?:tentee|impossible|echouee)|n'avons\s+pas\s+pu\s+livrer",
        it=r"tentativo\s+di\s+consegna|abbiamo\s+tentato\s+di\s+consegnare"
        r"|consegna\s+(?:non\s+riuscita|tentata|fallita|mancata)|mancata\s+consegna",
        nl=r"bezorgpoging|bezorging\s+(?:mislukt|niet\s+gelukt)"
        r"|geprobeerd\s+(?:\w+\s+){0,3}te\s+bezorgen|niet\s+bezorgd\s+kunnen",
    ),
    *kind_table(
        MailKind.READY_FOR_PICKUP,
        en=r"ready\s+for\s+(?:pick\s?-?up|collection)"
        r"|ready\s+to\s+(?:be\s+)?(?:picked\s+up|collected|pick\s+up|collect)"
        r"|available\s+for\s+(?:pick\s?-?up|collection)"
        r"|(?:pick\s+up|collect)\s+your\s+(?:package|parcel|order)",
        pt=r"pront[oa]s?\s+para\s+(?:levantamento|levantar|recolha)"
        r"|disponivel\s+para\s+(?:levantamento|levantar|recolha)"
        r"|aguarda\s+(?:o\s+seu\s+)?levantamento",
        es=r"list[oa]s?\s+para\s+(?:recoger|recogida|retirar)"
        r"|disponible\s+para\s+(?:recoger|recogida)|recoge\s+tu\s+(?:paquete|pedido)",
        de=r"abholbereit|bereit\s+zur\s+abholung|zur\s+abholung\s+bereit"
        r"|kann\s+(?:jetzt\s+)?abgeholt\s+werden|liegt\s+zur\s+abholung",
        fr=r"pret\s+(?:a\s+etre\s+retire|pour\s+le\s+retrait|a\s+retirer)"
        r"|disponible\s+(?:au|en|pour\s+le)\s+retrait|retirez\s+votre\s+colis",
        it=r"pront[oa]\s+(?:per\s+il\s+ritiro|da\s+ritirare|per\s+essere\s+ritirat[oa])"
        r"|disponibile\s+per\s+il\s+ritiro|ritira\s+il\s+tuo\s+pacco",
        nl=r"klaar\s+(?:om\s+(?:op|af)\s+te\s+halen|voor\s+ophalen)"
        r"|ligt\s+(?:voor\s+je\s+)?klaar|kan\s+(?:worden\s+)?opgehaald",
    ),
    *kind_table(
        MailKind.DELAYED,
        en=r"delayed|running\s+late|now\s+arriving|new\s+delivery\s+date"
        r"|later\s+than\s+(?:expected|planned|originally\s+expected)|delivery\s+delay",
        pt=r"atrasad[oa]s?|atraso|mais\s+tarde\s+do\s+que\s+(?:o\s+)?previsto"
        r"|nova\s+data\s+de\s+entrega",
        es=r"retrasad[oa]s?|retraso|mas\s+tarde\s+de\s+lo\s+previsto"
        r"|nueva\s+fecha\s+de\s+entrega",
        de=r"verspatet|verspatung|verzogert|verzogerung"
        r"|spater\s+als\s+(?:erwartet|geplant)"
        r"|neue[rs]?\s+(?:liefertermin|zustelltermin|lieferdatum)",
        fr=r"en\s+retard|retardee?s?|plus\s+tard\s+que\s+prevu"
        r"|nouvelle\s+date\s+de\s+livraison",
        it=r"in\s+ritardo|ritardat[oaie]|ritardo|piu\s+tardi\s+del\s+previsto"
        r"|nuova\s+data\s+di\s+consegna",
        nl=r"vertraagd|vertraging|later\s+dan\s+verwacht|nieuwe\s+bezorgdatum",
    ),
    *kind_table(
        MailKind.OUT_FOR_DELIVERY,
        en=r"out\s+for\s+delivery|arriving\s+today|arrives\s+today"
        r"|will\s+be\s+delivered\s+today|delivering\s+today",
        pt=r"saiu\s+para\s+(?:a\s+)?entrega|em\s+(?:distribuicao|entrega)"
        r"|chega\s+hoje|entrega\s+hoje|sera\s+entregue\s+hoje",
        es=r"en\s+reparto|llega\s+hoy|(?:se\s+)?entrega\s+hoy"
        r"|sera\s+entregad[oa]\s+hoy",
        de=r"in\s+zustellung|wird\s+heute\s+(?:zugestellt|geliefert)"
        r"|kommt\s+heute(?:\s+an)?|zustellung\s+heute|lieferung\s+heute",
        fr=r"en\s+cours\s+de\s+livraison|livraison\s+aujourd'hui"
        r"|arrive\s+aujourd'hui|sera\s+livree?\s+aujourd'hui",
        it=r"in\s+consegna|arriva\s+oggi|consegna\s+oggi|in\s+arrivo\s+oggi"
        r"|sara\s+consegnat[oa]\s+oggi",
        nl=r"wordt\s+vandaag\s+(?:bezorgd|geleverd)|vandaag\s+verwacht"
        r"|bezorging\s+vandaag|komt\s+vandaag(?:\s+aan)?"
        r"|onderweg\s+voor\s+bezorging",
    ),
    *kind_table(
        MailKind.DELIVERED,
        en=r"delivered",
        pt=r"entregues?",
        es=r"entregad[oa]s?",
        de=r"zugestellt|geliefert",
        fr=r"livree?s?",
        it=r"consegnat[oaie]",
        nl=r"bezorgd|afgeleverd|geleverd",
    ),
    *kind_table(
        MailKind.SHIPPED,
        en=r"shipped|dispatched|on\s+(?:its|the)\s+way|in\s+transit|arriving"
        r"|will\s+arrive",
        pt=r"enviad[oa]s?|expedid[oa]s?|a\s+caminho|em\s+transito|chega(?:ra)?"
        r"|vai\s+chegar",
        es=r"enviad[oa]s?|en\s+camino|en\s+transito|llega(?:ra)?|va\s+a\s+llegar",
        de=r"versandt|verschickt|versendet|unterwegs|ist\s+auf\s+dem\s+weg"
        r"|kommt\s+(?:morgen|bald|am)",
        fr=r"expediee?s?|en\s+route|en\s+chemin|en\s+transit|arrivera",
        it=r"spedit[oaie]|in\s+arrivo|in\s+viaggio|in\s+transito|arrivera",
        nl=r"verzonden|verstuurd|onderweg|komt\s+(?:morgen|eraan)",
    ),
    *kind_table(
        MailKind.ORDER,
        en=r"ordered|order\s+(?:confirmation|confirmed|placed|received)"
        r"|your\s+(?:amazon(?:\.[a-z.]+)?\s+)?order\s+(?:of|from|for|with)"
        r"|thank(?:s|\s+you)\s+for\s+your\s+order",
        pt=r"encomenda\s+(?:efetuada|confirmada|realizada|recebida)|encomendado"
        r"|confirmacao\s+d[ae]\s+encomenda|a\s+sua\s+encomenda\s+d[ae]\s+amazon"
        r"|obrigad[oa]\s+pela\s+sua\s+encomenda|^\s*encomenda\s*:",
        es=r"pedido\s+(?:realizado|confirmado|recibido|efectuado)"
        r"|confirmacion\s+del?\s+pedido|tu\s+pedido\s+(?:de|en)\s+amazon"
        r"|gracias\s+por\s+tu\s+pedido|^\s*pedido\s*:",
        de=r"bestellt|bestellbestatigung|bestellung\s+(?:bestatigt|eingegangen)"
        r"|ihre\s+amazon(?:\.[a-z.]+)?(?:-|\s+)bestellung"
        r"|(?:vielen\s+)?dank\s+fur\s+ihre\s+bestellung",
        fr=r"commandee?s?\s*:|commande\s+(?:confirmee|passee|recue|enregistree)"
        r"|confirmation\s+de\s+(?:votre\s+)?commande|votre\s+commande\s+amazon"
        r"|merci\s+pour\s+votre\s+commande",
        it=r"ordinat[oaie]|ordine\s+(?:confermato|effettuato|ricevuto)"
        r"|conferma\s+(?:d'ordine|dell'ordine|ordine)|il\s+tuo\s+ordine\s+amazon"
        r"|grazie\s+per\s+il\s+tuo\s+ordine",
        nl=r"besteld|bestelbevestiging|bestelling\s+(?:bevestigd|geplaatst|ontvangen)"
        r"|(?:je|uw)\s+amazon(?:\.[a-z.]+)?(?:-|\s+)bestelling"
        r"|bedankt\s+voor\s+(?:je|uw)\s+bestelling",
    ),
)

# Body sentences, used only when the subject has no known pattern; the
# earliest one near the top of the e-mail wins.
_BODY_PATTERNS: tuple[KindPattern, ...] = (
    *kind_table(
        MailKind.CANCELLED,
        en=r"(?:has\s+been|was|have\s+been|were)\s+cancel+ed",
        pt=r"foi\s+cancelad[oa]|foram\s+cancelad[oa]s",
        es=r"ha\s+sido\s+cancelad[oa]|se\s+ha\s+cancelado",
        de=r"wurde\s+storniert|wurden\s+storniert",
        fr=r"a\s+ete\s+annulee?",
        it=r"e\s+stat[oa]\s+annullat[oa]",
        nl=r"is\s+geannuleerd",
    ),
    *kind_table(
        MailKind.RETURN,
        en=r"refund\s+(?:of|for|has|was|issued)"
        r"|(?:we've|we\s+have)\s+(?:issued|processed)\s+(?:a|your)\s+refund",
        pt=r"reembolso\s+(?:de|do|da|emitido|processado)",
        es=r"reembolso\s+(?:de|del|emitido|procesado)",
        de=r"erstattung\s+(?:fur|von|veranlasst)",
        fr=r"remboursement\s+(?:de|pour|effectue)",
        it=r"rimborso\s+(?:di|per|emesso)",
        nl=r"terugbetaling\s+(?:van|voor)",
    ),
    *kind_table(
        MailKind.ATTEMPTED,
        en=r"(?:attempted|tried)\s+to\s+deliver",
        pt=r"tentamos\s+entregar",
        es=r"(?:intentamos|hemos\s+intentado)\s+entregar",
        de=r"zustellversuch",
        fr=r"tente\s+de\s+livrer",
        it=r"tentato\s+di\s+consegnare",
        nl=r"geprobeerd\s+(?:\w+\s+){0,3}te\s+bezorgen|bezorgpoging",
    ),
    *kind_table(
        MailKind.READY_FOR_PICKUP,
        en=r"ready\s+for\s+(?:pick\s?-?up|collection)",
        pt=r"pront[oa]\s+para\s+levantamento",
        es=r"list[oa]\s+para\s+recoger",
        de=r"abholbereit|bereit\s+zur\s+abholung",
        fr=r"pret\s+a\s+etre\s+retire",
        it=r"pront[oa]\s+per\s+il\s+ritiro",
        nl=r"klaar\s+om\s+op\s+te\s+halen|ligt\s+(?:voor\s+je\s+)?klaar",
    ),
    *kind_table(
        MailKind.DELAYED,
        en=r"(?:is|has\s+been)\s+delayed|running\s+late|later\s+than\s+expected",
        pt=r"esta\s+atrasad[oa]|mais\s+tarde\s+do\s+que\s+(?:o\s+)?previsto",
        es=r"se\s+ha\s+retrasado|mas\s+tarde\s+de\s+lo\s+previsto",
        de=r"(?:verspatet|verzogert)\s+sich",
        fr=r"est\s+retardee?|en\s+retard",
        it=r"e\s+in\s+ritardo",
        nl=r"is\s+vertraagd",
    ),
    *kind_table(
        MailKind.OUT_FOR_DELIVERY,
        en=r"out\s+for\s+delivery|arriving\s+today",
        pt=r"saiu\s+para\s+(?:a\s+)?entrega|chega\s+hoje",
        es=r"esta\s+en\s+reparto|llega\s+hoy",
        de=r"in\s+zustellung|wird\s+heute\s+zugestellt",
        fr=r"en\s+cours\s+de\s+livraison|arrive\s+aujourd'hui",
        it=r"e\s+in\s+consegna|arriva\s+oggi",
        nl=r"wordt\s+vandaag\s+bezorgd|komt\s+vandaag",
    ),
    *kind_table(
        MailKind.DELIVERED,
        en=r"(?:was|has\s+been)\s+delivered",
        pt=r"foi\s+entregue",
        es=r"(?:se\s+ha|ha\s+sido)\s+entregad[oa]",
        de=r"wurde\s+zugestellt",
        fr=r"a\s+ete\s+livree?",
        it=r"e\s+stat[oa]\s+consegnat[oa]",
        nl=r"is\s+(?:bezorgd|afgeleverd)",
    ),
    # Footers say "this e-mail was sent from an address that ...", so a
    # "sent from" never counts.
    *kind_table(
        MailKind.SHIPPED,
        en=r"(?:has|have)\s+(?:been\s+)?shipped|is\s+on\s+(?:its|the)\s+way",
        pt=r"foi\s+enviad[oa](?!\s+(?:de|desde|a\s+partir)\s)|esta\s+a\s+caminho",
        es=r"(?:se\s+ha|ha\s+sido)\s+enviad[oa](?!\s+(?:de|desde)\s)"
        r"|esta\s+en\s+camino",
        de=r"wurde\s+versandt|ist\s+unterwegs",
        fr=r"a\s+ete\s+expediee?|est\s+en\s+route",
        it=r"e\s+stat[oa]\s+spedit[oa]|e\s+in\s+arrivo",
        nl=r"is\s+(?:verzonden|onderweg)(?!\s+vanaf\s)",
    ),
    *kind_table(
        MailKind.ORDER,
        en=r"thank(?:s|\s+you)\s+for\s+your\s+order",
        pt=r"obrigad[oa]\s+pela\s+sua\s+encomenda",
        es=r"gracias\s+por\s+tu\s+pedido",
        de=r"(?:vielen\s+)?dank\s+fur\s+ihre\s+bestellung",
        fr=r"merci\s+pour\s+votre\s+commande",
        it=r"grazie\s+per\s+il\s+tuo\s+ordine",
        nl=r"bedankt\s+voor\s+(?:je|uw)\s+bestelling",
    ),
)

# Requests for a rating or a review: never about a parcel.
_FEEDBACK_RE = re.compile(
    r"(?<![a-z0-9])(?:rate\s+your|how\s+was\s+your|how\s+did\s+we\s+do"
    r"|review\s+your\s+(?:recent\s+)?purchase|leave\s+(?:seller\s+)?feedback"
    r"|share\s+your\s+experience|avalie\s+(?:a\s+sua|o\s+seu)"
    r"|como\s+foi\s+(?:a\s+sua|o\s+seu)|valora\s+tu|que\s+te\s+ha\s+parecido"
    r"|bewerten?\s+(?:sie|deine?n?|ihre?n?)|wie\s+war|evaluez\s+votre"
    r"|donnez\s+votre\s+avis|valuta\s+(?:il|la|l')|lascia\s+una\s+recensione"
    r"|beoordeel\s+(?:je|uw)|hoe\s+was)(?![a-z0-9])"
)

# Delivery estimate labels. Distinctive phrases may stand without a colon;
# single words only count as a label when a colon follows.
_ETA_LOOSE = (
    "arriving",
    "now arriving",
    "estimated delivery",
    "expected delivery",
    "delivery estimate",
    "guaranteed delivery",
    "estimated arrival",
    "new delivery date",
    "new estimated delivery",
    "entrega prevista",
    "chegada prevista",
    "previsao de entrega",
    "data de entrega prevista",
    "data prevista de entrega",
    "nova data de entrega",
    "llegada prevista",
    "entrega estimada",
    "fecha de entrega",
    "fecha de entrega prevista",
    "fecha estimada de entrega",
    "nueva fecha de entrega",
    "voraussichtliche zustellung",
    "voraussichtliche lieferung",
    "neue voraussichtliche zustellung",
    "voraussichtliches lieferdatum",
    "zustellung voraussichtlich",
    "lieferung voraussichtlich",
    "lieferdatum",
    "neues lieferdatum",
    "livraison prevue",
    "livraison estimee",
    "date de livraison",
    "date de livraison prevue",
    "nouvelle date de livraison",
    "arrivee prevue",
    "consegna prevista",
    "consegna stimata",
    "arrivo previsto",
    "data di consegna",
    "data di consegna prevista",
    "nuova data di consegna",
    "verwachte bezorging",
    "verwachte levering",
    "verwachte bezorgdatum",
    "geschatte bezorging",
    "bezorgdatum",
    "nieuwe bezorgdatum",
)
_ETA_STRICT = (
    "arrives",
    "arrive",
    "expected",
    "delivery",
    "chegada",
    "chega",
    "entrega",
    "llegada",
    "llega",
    "zustellung",
    "lieferung",
    "ankunft",
    "livraison",
    "arrivee",
    "arrivo",
    "consegna",
    "bezorging",
    "levering",
)


def _alternation(words: tuple[str, ...]) -> str:
    """Join folded phrases into a regex alternation, longest first."""
    ordered = sorted(set(words), key=len, reverse=True)
    return "|".join(r"\s+".join(re.escape(w) for w in p.split()) for p in ordered)


_ETA_LABEL_RE = re.compile(
    rf"(?<![a-z0-9])(?:(?:{_alternation(_ETA_LOOSE)})(?![a-z0-9])(?:\s*:)?"
    rf"|(?:{_alternation(_ETA_STRICT)})\s*:)"
)
# A label for the old estimate in a delay notice ("Previously expected:").
_PREVIOUS_RE = re.compile(
    r"(?<![a-z])(?:previous(?:ly)?|originally|original|anteriormente|anterior"
    r"|inicialmente|ursprunglich\w*|bisherig\w*|zuvor|initialement|precedemment"
    r"|precedentemente|originariamente|inizialmente|eerder|oorspronkelijk\w*)"
    r"(?![a-z])"
)

# Link texts of buttons that point to a product page.
_BUTTON_RE = words_regex(
    (
        "buy it again",
        "buy again",
        "view item",
        "view your item",
        "write a review",
        "track package",
        "view order",
        "view or edit order",
        "return or replace items",
        "comprar de novo",
        "comprar novamente",
        "ver artigo",
        "acompanhar encomenda",
        "seguir encomenda",
        "comprar de nuevo",
        "volver a comprar",
        "ver articulo",
        "ver producto",
        "seguir paquete",
        "seguir envio",
        "ver pedido",
        "erneut kaufen",
        "nochmals kaufen",
        "artikel ansehen",
        "sendung verfolgen",
        "paket verfolgen",
        "bestellung ansehen",
        "acheter a nouveau",
        "acheter de nouveau",
        "voir l'article",
        "suivre votre colis",
        "suivre le colis",
        "voir la commande",
        "acquista di nuovo",
        "acquista ancora",
        "visualizza articolo",
        "traccia il pacco",
        "monitora il pacco",
        "visualizza ordine",
        "opnieuw kopen",
        "nogmaals kopen",
        "artikel bekijken",
        "pakket volgen",
        "volg je pakket",
        "bestelling bekijken",
    )
)

_LOCKER_RE = words_regex(
    ("amazon locker", "amazon hub", "amazon counter", "hub locker", "hub counter")
)

# Headings of product recommendations: the products below them weren't
# ordered.
_RECOMMENDATIONS_RE = words_regex(
    (
        "recommended for you",
        "recommended items",
        "top picks for you",
        "inspired by your",
        "customers who bought",
        "you might also like",
        "related to items you",
        "recomendado para si",
        "recomendados para si",
        "sugestoes para si",
        "recomendado para ti",
        "recomendados para ti",
        "productos recomendados",
        "los clientes que compraron",
        "empfehlungen fur sie",
        "empfohlen fur sie",
        "kunden, die",
        "recommande pour vous",
        "recommandations pour vous",
        "les clients ayant achete",
        "consigliati per te",
        "consigliato per te",
        "i clienti che hanno acquistato",
        "aanbevolen voor jou",
        "aanbevolen voor u",
        "aanbevelingen voor jou",
        "klanten die",
    )
)


@dataclass(slots=True)
class _Context:
    """What the helpers of one parse need to know about the e-mail."""

    message: MailMessage
    verdict: SenderVerdict
    tz: tzinfo
    text: str
    folded: str
    lang: str | None
    orders: tuple[str, ...]
    items: tuple[str, ...]
    urls: tuple[str, ...]


def _is_amazon_url(url: str) -> bool:
    """Return True for a link to an Amazon marketplace."""
    host = url_host(url)
    info = lookup(host) if host else None
    return info is not None and info.parser == PARSER


def _amazon_urls(links: tuple[Link, ...]) -> tuple[str, ...]:
    """Return every Amazon URL in the links, unwrapping click trackers."""
    urls: list[str] = []
    for link in links:
        urls.extend(
            url
            for url in unwrap_url(link.url)
            if url not in urls and _is_amazon_url(url)
        )
    return tuple(urls)


def _add_unique(values: list[str], value: str, limit: int = _MAX_ORDERS) -> None:
    if value not in values and len(values) < limit:
        values.append(value)


def _order_numbers(subject: str, text: str, urls: tuple[str, ...]) -> tuple[str, ...]:
    """Return the order numbers in the subject, the text and Amazon links."""
    orders: list[str] = []
    for source in (subject, text):
        for match in ORDER_NUMBER_RE.finditer(source):
            _add_unique(orders, match.group(0))
    for url in urls:
        for key, value in query_params(url):
            if key.lower() == "orderid" and ORDER_NUMBER_RE.fullmatch(value):
                _add_unique(orders, value)
    return tuple(orders)


def _shipment_ids(urls: tuple[str, ...]) -> list[str]:
    """Return the shipment IDs of the "Track package" links."""
    ids: list[str] = []
    for url in urls:
        for key, value in query_params(url):
            if key.lower() == "shipmentid" and _SHIPMENT_ID_RE.fullmatch(value):
                _add_unique(ids, value)
    return ids


def _subject_title(subject: str) -> str | None:
    """Return the quoted product title of a subject, if any."""
    folded = fold_text(subject)
    match = _QUOTED_RE.search(folded)
    if match is None:
        return None
    return subject[match.start() + 1 : match.end()].rstrip("\"'\u201d\u00bb")


def _items(
    message: MailMessage, text: str, folded: str
) -> tuple[tuple[str, ...], frozenset[str]]:
    """Return the product titles and the ASINs of the product links.

    Only product links whose text appears in the body before any
    recommendations heading count: image links (whose text is the image's
    alt text) and recommended products aren't ordered items.
    """
    items: list[str] = []
    asins: set[str] = set()
    flat = " ".join(folded.split())
    heading = _RECOMMENDATIONS_RE.search(flat)
    cutoff = heading.start() if heading else len(flat)
    for link in message.links:
        found = [
            match.group(1)
            for url in unwrap_url(link.url)
            if _is_amazon_url(url) and (match := _ASIN_PATH_RE.search(url_path(url)))
        ]
        if not found:
            continue
        asins.update(found)
        title = " ".join(fold_text(link.text).split())
        if title and not _BUTTON_RE.search(title) and 0 <= flat.find(title) < cutoff:
            add_item(items, link.text)
    if not items:
        quantity_items(text, folded, items)
    if not items and (title := _subject_title(message.subject)):
        add_item(items, title)
    return tuple(items), frozenset(asins)


def _label_etas(ctx: _Context, kind: MailKind) -> list[tuple[int, Eta]]:
    """Return the estimates that follow a delivery label, in text order."""
    found: list[tuple[int, Eta]] = []
    for value in label_values(ctx.text, ctx.folded, _ETA_LABEL_RE):
        line_start, _ = line_bounds(ctx.folded, value.label_start)
        if _PREVIOUS_RE.search(ctx.folded, line_start, value.start):
            continue
        eta = parse_eta(value.value, ctx.message.date, ctx.tz, ctx.lang)
        if (
            eta is None
            and kind is MailKind.OUT_FOR_DELIVERY
            and (window := parse_time_window(value.value)) is not None
        ):
            day = local_date(ctx.message.date, ctx.tz)
            eta = Eta(day, day, window[0], window[1])
        if eta is not None:
            found.append((value.label_start, eta))
    return found


def _etas(ctx: _Context, kind: MailKind) -> list[tuple[int, Eta]]:
    """Return the delivery estimates for kinds that have one."""
    if kind not in _ETA_KINDS:
        return []
    found = _label_etas(ctx, kind)
    if not found and (eta := find_eta(ctx.text, ctx.message.date, ctx.tz, ctx.lang)):
        found = [(-1, eta)]
    if not found and kind is MailKind.OUT_FOR_DELIVERY:
        found = [(-1, today_eta(ctx.message, ctx.tz))]
    return found


def _group_items(
    ctx: _Context, marks: list[tuple[int, int]], count: int
) -> list[tuple[str, ...]]:
    """Split the items between deliveries by the label each one follows.

    ``marks`` holds the text position of each delivery's estimate label and
    the delivery's index; an item goes to the last label before it.
    """
    groups: list[list[str]] = [[] for _ in range(count)]
    ordered = sorted(marks)
    first = ordered[0][0]
    for item in ctx.items:
        pos = ctx.text.find(item, first)
        if pos < 0:
            pos = ctx.text.find(item)
        index = ordered[0][1]
        for label_pos, group in ordered:
            if label_pos <= pos:
                index = group
        groups[index].append(item)
    return [tuple(group) for group in groups]


def _order_shipments(
    ctx: _Context, etas: list[tuple[int, Eta]]
) -> list[ParsedShipment]:
    """One ORDER shipment, or one per delivery when estimates differ."""
    distinct: list[Eta] = []
    marks: list[tuple[int, int]] = []
    for pos, eta in etas:
        if eta not in distinct:
            distinct.append(eta)
        if pos >= 0:
            marks.append((pos, distinct.index(eta)))
    if len(distinct) < 2 or not marks:
        return [
            ParsedShipment(
                kind=MailKind.ORDER,
                eta=distinct[0] if distinct else None,
                order_numbers=ctx.orders,
                items=ctx.items,
            )
        ]
    groups = _group_items(ctx, marks, len(distinct))
    return [
        ParsedShipment(
            kind=MailKind.ORDER,
            eta=eta,
            order_numbers=ctx.orders,
            items=group,
        )
        for eta, group in zip(distinct, groups, strict=True)
    ]


def _pickup(ctx: _Context) -> tuple[str | None, str | None]:
    """Return the pickup point and the pickup code of a pickup notice."""
    point, code = pickup_details(ctx.text, ctx.folded)
    if point is None and (match := _LOCKER_RE.search(ctx.folded)):
        _, end = line_bounds(ctx.text, match.start())
        point = clip(ctx.text[match.start() : end], MAX_POINT_CHARS).rstrip(".") or None
    return point, code


def _track_url(ctx: _Context, shipment_id: str | None) -> str | None:
    """Return the cleaned "Track package" link for a shipment, if it's safe."""
    if shipment_id is None:
        return None
    for url in ctx.urls:
        params = query_params(url)
        if not any(
            key.lower() == "shipmentid" and value == shipment_id
            for key, value in params
        ) or not own_https_url(url, ctx.message, ctx.verdict):
            continue
        try:
            path = urlsplit(url).path
        except ValueError:
            continue
        path = "/".join(part for part in path.split("/") if not part.startswith("ref="))
        kept = [(key, value) for key, value in params if key.lower() in _KEPT_PARAMS]
        return urlunsplit(("https", url_host(url), path or "/", urlencode(kept), ""))
    return None


def _status_shipments(
    ctx: _Context,
    kind: MailKind,
    shipment_ids: list[str],
    numbers: list[FoundNumber],
    etas: list[tuple[int, Eta]],
) -> tuple[list[ParsedShipment], str | None]:
    """Build one shipment per Amazon shipment; also return the pickup code."""
    if kind in (MailKind.CANCELLED, MailKind.RETURN):
        return [ParsedShipment(order_numbers=ctx.orders, items=ctx.items)], None
    point, code = _pickup(ctx) if kind is MailKind.READY_FOR_PICKUP else (None, None)
    when = event_time(ctx.folded, kind, ctx.message, ctx.tz, ctx.lang)
    slots: list[str | None] = [*shipment_ids] or [None]
    single = len(slots) == 1
    # Several packages share the items only when the labels split them.
    per_slot: list[tuple[str, ...]] = [ctx.items] if single else [()] * len(slots)
    if not single and len(etas) == len(slots):
        marks = [(pos, index) for index, (pos, _) in enumerate(etas) if pos >= 0]
        if len(marks) == len(slots):
            per_slot = _group_items(ctx, marks, len(slots))
    other = next((n for n in numbers if n.carrier != "amazon"), None)
    own = next((n for n in numbers if n.carrier == "amazon"), None)
    # Amazon hands many parcels to other carriers, so its own delivery
    # service counts only when the e-mail names it or has its number.
    logistics = any(m.carrier == "amazon" for m in carrier_mentions(ctx.folded))
    shipments: list[ParsedShipment] = []
    for index, shipment_id in enumerate(slots):
        if len(etas) == len(slots):
            eta: Eta | None = etas[index][1]
        else:
            eta = etas[0][1] if etas else None
        carrier: str | None = "amazon" if logistics else None
        number: str | None = None
        if single and other is not None:
            carrier, number = other.carrier, other.number
        elif single and own is not None:
            carrier, number = "amazon", own.number
        url = _track_url(ctx, shipment_id) if carrier in (None, "amazon") else None
        if url is None and number is not None:
            url = tracking.tracking_url(carrier, number)
        shipments.append(
            ParsedShipment(
                carrier=carrier,
                tracking_number=number,
                eta=eta,
                event_time=when,
                pickup_point=point,
                pickup_code=code,
                amazon_shipment_id=shipment_id,
                order_numbers=ctx.orders,
                items=per_slot[index],
                tracking_url=url,
            )
        )
    return shipments, code


def _not_parcel(message: MailMessage) -> ParseResult:
    return ParseResult(
        parser=PARSER,
        kind=MailKind.NOT_PARCEL,
        merchant=MERCHANT,
        confidence=0.9,
        language=message.language,
    )


def parse_amazon(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult | None:
    """Parse an Amazon order or shipping e-mail.

    Returns None when the e-mail isn't recognised (marketing, account
    e-mails, or a layout the parser can't read), and a NOT_PARCEL result
    for review requests and digital orders.
    """
    subject = _QUOTED_RE.sub(" ", fold_text(message.subject))
    if _FEEDBACK_RE.search(subject):
        return _not_parcel(message)
    text = message.text
    folded = fold_text(text)
    urls = _amazon_urls(message.links)
    orders = _order_numbers(message.subject, text, urls)
    if not orders and _DIGITAL_ORDER_RE.search(f"{message.subject}\n{text}"):
        return _not_parcel(message)
    pattern, from_subject = detect_kind(
        subject, folded, _SUBJECT_PATTERNS, _BODY_PATTERNS
    )
    if pattern is None:
        return None
    kind = pattern.kind
    if kind in _ORDER_KINDS and not orders:
        return None
    items, asins = _items(message, text, folded)
    ctx = _Context(
        message=message,
        verdict=verdict,
        tz=tz,
        text=text,
        folded=folded,
        lang=message.language or pattern.lang,
        orders=orders,
        items=items,
        urls=urls,
    )
    etas = _etas(ctx, kind)
    if kind in _ORDER_KINDS:
        shipments = (
            _order_shipments(ctx, etas)
            if kind is MailKind.ORDER
            else _status_shipments(ctx, kind, [], [], etas)[0]
        )
        key = True
    else:
        shipment_ids = _shipment_ids(urls)
        exclude = frozenset(
            {
                *asins,
                *(sid.upper() for sid in shipment_ids),
                *(order.replace("-", "") for order in orders),
            }
        )
        numbers = find_numbers(
            text, folded, message.links, exclude=exclude, window=120, allow_other=False
        )
        if not (orders or shipment_ids or numbers):
            return None
        shipments, code = _status_shipments(ctx, kind, shipment_ids, numbers, etas)
        key = bool(shipment_ids or numbers or code)
    return ParseResult(
        parser=PARSER,
        kind=kind,
        merchant=MERCHANT,
        order_numbers=orders,
        shipments=shipments,
        items=items,
        confidence=_CONFIDENCE[from_subject, key],
        language=ctx.lang,
    )
