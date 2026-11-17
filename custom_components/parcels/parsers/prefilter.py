"""Cheap check on headers before an e-mail body is downloaded.

The mail coordinator calls ``is_candidate`` with the sender, the subject
and the provider's short preview (Graph ``bodyPreview``, Gmail
``snippet``). Known senders (``senders.KNOWN_SENDERS``) always pass. Other
e-mails pass when their subject or preview has shipping or order words in
one of the seven supported languages:

* ``STRONG_KEYWORDS`` (status phrases such as "out for delivery",
  "foi entregue", "zugestellt", tracking and order-number labels) always
  pass;
* ``WEAK_KEYWORDS`` (generic words such as "parcel", "your order",
  "envio", "Lieferung" or a carrier name) pass unless the text also has
  advertising markers (``MARKETING_WORDS``, or a "%" sign).

Advertising phrases such as "free shipping" or "order now"
(``MARKETING_PHRASES``) are removed first, so they never count, and when
the subject has one, weak keywords don't count either. Keywords
are folded (lowercase, no accents), matched as whole words, and may hold
small regular expressions; a space matches any whitespace and an
apostrophe matches ' or its typographic form.
"""

from __future__ import annotations

from collections.abc import Iterable
import re

from .lang import fold
from .senders import lookup, organizational_domain

# Only this much of subject + preview is looked at.
MAX_CHARS = 2000

MARKETING_PHRASES: dict[str, tuple[str, ...]] = {
    "en": (
        r"free (?:standard |express |next[- ]day |uk |eu )?(?:shipping|delivery|returns?)",
        r"ships free",
        r"shipping (?:is )?(?:free|included)",
        r"(?:fast|express|next[- ]day|same[- ]day) (?:shipping|delivery)",
        r"order now",
        r"pre[- ]?orders?",
        r"order by",
        r"(?:shop|buy) now",
        r"delivered (?:to|straight to) your (?:door|inbox)",
        r"get it delivered",
    ),
    "pt": (
        r"(?:portes|envios?|entregas?|devolucoes) (?:gratis|gratuit[oa]s?|gratuit[oa])",
        r"encomende (?:ja|agora|hoje)",
        r"compre (?:ja|agora)",
        r"pre[- ]?venda",
        r"pre[- ]?reserva",
    ),
    "es": (
        r"(?:envios?|entregas?|devoluci(?:on|ones)) (?:gratis|gratuit[oa]s?)",
        r"pide(?:lo)? (?:ya|ahora)",
        r"compra (?:ya|ahora)",
        r"reserva ya",
        r"pre[- ]?venta",
    ),
    "de": (
        r"(?:kostenlose[rn]?|gratis) (?:versand|lieferung|ruecksendung|rucksendung|retoure)",
        r"(?:versand|lieferung) (?:gratis|kostenlos)",
        r"versandkostenfrei",
        r"jetzt (?:bestellen|kaufen|vorbestellen|shoppen)",
        r"vorbestell\w*",
    ),
    "fr": (
        r"livraison (?:gratuite|offerte)",
        r"frais de port (?:offerts|gratuits)",
        r"retours? (?:gratuits?|offerts?)",
        r"commandez (?:maintenant|des maintenant|vite|aujourd'hui)",
        r"achetez (?:maintenant|vite)",
        r"pre[- ]?commande\w*",
    ),
    "it": (
        r"(?:spedizion[ei]|consegna|resi) (?:gratuit[aei]|gratis)",
        r"(?:ordina|acquista) (?:ora|subito|adesso)",
        r"preordin\w*",
    ),
    "nl": (
        r"gratis (?:verzending|verzonden|bezorging|levering|retour\w*)",
        r"(?:bestel|koop) (?:nu|vandaag|snel)",
        r"voorbestel\w*",
        r"pre[- ]?order",
    ),
}

MARKETING_WORDS: dict[str, tuple[str, ...]] = {
    "en": (
        r"sales?",
        r"deals?",
        r"discounts?",
        r"promo\w*",
        r"offers?",
        r"coupons?",
        r"vouchers?",
        "black friday",
        "cyber monday",
        "newsletter",
        "new arrivals",
        "new in",
        "save",
        "last chance",
        "limited time",
        "exclusive",
        r"(?:un)?subscribe",
        "webinar",
        r"best ?sellers",
        "clearance",
    ),
    "pt": (
        r"promoc(?:ao|oes)",
        r"descontos?",
        r"ofertas?",
        "saldos",
        "campanha",
        "novidades",
        "cupao",
        "cupom",
        "poupe",
        "aproveite",
        "imperdivel",
        r"exclusiv[oa]s?",
    ),
    "es": (
        r"ofertas?",
        r"descuentos?",
        "rebajas",
        r"promoci(?:on|ones)",
        "novedades",
        "cupon",
        "ahorra",
        "aprovecha",
        r"chollos?",
        "liquidacion",
        r"suscribete",
    ),
    "de": (
        r"angebote?",
        r"rabatte?",
        "gutschein",
        r"aktion(?:en)?",
        "sparen",
        "spare",
        "neuheiten",
        r"schnappchen",
        r"exklusiv\w*",
        "abmelden",
        "reduziert",
    ),
    "fr": (
        "soldes",
        r"remises?",
        r"offres?",
        r"reductions?",
        r"bons? plans?",
        "nouveautes",
        "economisez",
        "code promo",
        r"ventes? privees?",
        r"exclusi(?:f|ve|fs|ves)",
        "desabonner",
    ),
    "it": (
        r"scont[oi]",
        "saldi",
        r"offert[ae]",
        r"promozion[ei]",
        "novita",
        "risparmia",
        "codice sconto",
        r"esclusiv[oaei]",
        "imperdibile",
    ),
    "nl": (
        r"kortingen?",
        r"aanbieding(?:en)?",
        "uitverkoop",
        r"acties?",
        "nieuw binnen",
        "bespaar",
        r"exclusie[fv]e?",
        "uitschrijven",
        "nieuwsbrief",
    ),
}

STRONG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "en": (
        r"order (?:confirmation|confirmed|received|number|no|nr)",
        r"thanks? (?:you )?for your (?:order|purchase)",
        r"received your order",
        r"(?:has|have|has been|have been|was|were) (?:shipped|dispatched)",
        r"(?:shipped|dispatched|delivered):",
        r"(?:shipping|shipment|dispatch) (?:confirmation|notification|update)",
        r"delivery (?:notification|update)",
        r"(?:order|parcel|package|shipment|delivery|purchase|items?) (?:is|are) on (?:its|the|their) way",
        "in transit",
        "out for delivery",
        r"(?:has|have) been delivered",
        r"(?:was|were) delivered",
        r"(?:package|parcel|order|shipment) delivered",
        r"(?:attempted|missed|failed) delivery",
        r"delivery (?:attempt|was attempted)",
        r"we missed you",
        r"(?:unable to|could not|couldn't) deliver",
        r"could not be delivered",
        r"ready (?:for|to) (?:pick[- ]?up|collection|collect|be collected)",
        r"(?:available|awaiting) (?:for )?(?:pick[- ]?up|collection)",
        r"tracking (?:number|code|id|information|info|details|update|link)",
        r"track (?:your|my) (?:order|parcel|package|shipment|delivery)",
        r"track (?:order|parcel|package|shipment)",
        r"(?:delivery|shipment|order|package|parcel) (?:is )?delayed",
        "delayed delivery",
        "customs clearance",
        "held at customs",
        r"customs (?:charges|fees?|duty|duties)",
        r"import (?:duties|taxes)",
        r"returns? (?:label|request|confirmation|(?:has been |was )?(?:received|processed|accepted|approved))",
        r"refund (?:issued|processed|confirmation)",
        "your refund",
        r"order (?:has been )?(?:cancell?ed)",
        r"estimated (?:delivery|arrival)",
        "expected delivery",
        r"(?:arriving|arrives) (?:today|tomorrow)",
        "will be delivered",
        r"(?:scheduled|delivery) (?:delivery|window|scheduled)",
        r"(?:pick[- ]?up|collection) code",
        "proof of delivery",
    ),
    "pt": (
        r"confirmacao (?:de|da|do) (?:encomenda|pedido)",
        r"(?:encomenda|pedido) (?:confirmad[oa]|recebid[oa])",
        r"recebemos (?:a sua|a tua|o seu|o teu) (?:encomenda|pedido)",
        r"obrigad[oa] (?:pela|pelo) (?:sua|tua|seu|teu) (?:encomenda|compra|pedido)",
        r"numero (?:de|da|do) (?:encomenda|pedido)",
        r"n\.? ?[o\u00b0]\.? ?(?:de |da |do )?(?:encomenda|pedido)",
        r"(?:foi|foram) (?:enviad[oa]s?|expedid[oa]s?|entregues?)",
        r"(?:encomenda|pedido|objeto|objecto) (?:enviad[oa]|expedid[oa]|entregue)",
        r"(?:encomenda|pedido|objeto|envio|remessa) (?:esta|segue|vai) a caminho",
        r"em (?:transito|distribuicao|entrega)",
        r"saiu para (?:entrega|distribuicao)",
        r"sera entregue",
        r"entrega prevista",
        r"entregue com sucesso",
        r"tentativa de entrega",
        r"nao (?:foi possivel|conseguimos) entregar",
        r"entrega (?:falhada|sem sucesso)",
        r"(?:pront[oa]|disponivel) (?:para|a) (?:levantamento|levantar|recolha)",
        r"aguarda (?:levantamento|recolha)",
        r"(?:numero|codigo) (?:de|do) (?:seguimento|rastreio|objeto|objecto)",
        r"(?:acompanhe|siga|seguir|rastrear|rastreie) (?:a sua |a tua |o seu |o teu )?(?:encomenda|pedido|envio|objeto)",
        r"(?:entrega|encomenda) atrasada",
        r"atraso na entrega",
        "desalfandegamento",
        r"alfandega",
        "direitos aduaneiros",
        r"(?:etiqueta|pedido) de devolucao",
        r"devolucao recebida",
        r"reembolso (?:emitido|processado|efetuado)",
        r"o (?:seu|teu) reembolso",
        r"(?:encomenda|pedido) cancelad[oa]",
        r"cacifos?",
        r"ponto (?:de recolha|pickup|payshop)",
        r"codigo de (?:levantamento|recolha)",
    ),
    "es": (
        r"confirmacion (?:de|del|de tu|de su) pedido",
        r"pedido (?:confirmado|recibido)",
        r"hemos recibido (?:tu|su) pedido",
        r"gracias por (?:tu|su) (?:pedido|compra)",
        r"numero (?:de|del) pedido",
        r"n\.? ?[o\u00b0]\.? ?(?:de )?pedido",
        r"(?:ha|han) sido (?:enviad[oa]s?|entregad[oa]s?)",
        r"fue (?:enviad[oa]|entregad[oa])",
        r"(?:pedido|paquete|envio) (?:enviado|entregado)",
        r"(?:pedido|paquete|envio) (?:ya )?(?:esta|va) en camino",
        r"en (?:transito|reparto)",
        r"(?:sale|saldra|ha salido) (?:a|para) reparto",
        r"entregado con exito",
        r"intento de entrega",
        r"entrega fallida",
        r"no (?:hemos podido|se ha podido|pudimos) entregar",
        r"(?:list[oa]|disponible) para (?:recoger|su recogida|recogida)",
        r"(?:pendiente|esperando) de? recogida",
        r"(?:numero|codigo) de seguimiento",
        r"(?:sigue|rastrea|seguimiento de) (?:tu |su |el |del )?(?:pedido|envio|paquete)",
        r"(?:entrega|pedido|envio) retrasad[oa]",
        r"retraso en (?:la entrega|tu pedido|el envio)",
        r"aduanas?",
        r"(?:etiqueta|solicitud) de devolucion",
        r"devolucion recibida",
        r"reembolso (?:emitido|procesado|realizado)",
        r"(?:tu|su) reembolso",
        r"pedido (?:cancelado|anulado)",
        r"punto (?:de recogida|pack)",
        r"taquillas?",
        r"codigo de recogida",
        r"entrega (?:prevista|estimada)",
    ),
    "de": (
        r"(?:bestell|auftrags|versand)bestatigung",
        "versandbenachrichtigung",
        r"bestellung (?:bestatigt|eingegangen|erhalten|versandt|verschickt|storniert)",
        r"(?:vielen )?dank fur (?:ihre|deine) bestellung",
        r"(?:bestell|auftrags|sendungs|paket|tracking)nummer",
        "bestellnr",
        r"(?:wurde|wurden) (?:versandt|versendet|verschickt|zugestellt|geliefert|storniert)",
        r"(?:sendung|paket|bestellung|lieferung) (?:ist|sind) (?:jetzt )?(?:unterwegs|auf dem weg)",
        r"in zustellung",
        r"(?:wird|werden) (?:heute )?zugestellt",
        r"zustellung (?:heute|verzogert)",
        "zugestellt",
        r"zustellversuch",
        r"nicht (?:zugestellt|angetroffen)",
        "benachrichtigungskarte",
        "abholbereit",
        r"(?:zur|bereit zur) abholung",
        r"abholung bereit",
        "abholcode",
        "packstation",
        "sendungsverfolgung",
        r"(?:sendung|paket) verfolgen",
        r"verfolgen sie ihre sendung",
        r"verfolge (?:dein|deine) (?:paket|sendung|bestellung)",
        r"(?:verzogert|verspatet|verspatung)",
        r"zoll(?:abfertigung|gebuhr\w*)",
        "einfuhrabgaben",
        r"(?:rucksende|retouren)(?:etikett|schein)",
        r"(?:rucksendung|retoure) (?:eingegangen|erhalten)",
        r"(?:ruck)?erstattung",
        r"stornierung\w*",
        r"voraussichtliche (?:zustellung|lieferung)",
    ),
    "fr": (
        r"confirmation de (?:votre |la )?commande",
        r"commande (?:confirmee|recue|expediee|livree|annulee)",
        r"merci (?:pour|de) votre (?:commande|achat)",
        r"nous avons bien recu votre commande",
        r"numero de commande",
        r"n\.? ?[o\u00b0]\.? ?(?:de )?commande",
        r"(?:a|ont) ete (?:expedie|livre)e?s?",
        r"colis (?:expedie|livre|retarde)",
        r"(?:est|sont) en route",
        r"en cours (?:d'acheminement|de livraison)",
        "en livraison",
        r"sera livree?",
        r"livraison (?:prevue|estimee|echouee|retardee)",
        r"livrees?",
        r"tentative de livraison",
        "avis de passage",
        r"n'a pas pu etre livree?",
        r"nous n'avons pas pu (?:vous )?livrer",
        r"disponible (?:en (?:point )?relais|au retrait|en consigne)",
        r"pret a etre retire",
        r"en attente de retrait",
        r"code de retrait",
        r"numero de suivi",
        r"suivi de (?:colis|commande|livraison)",
        r"suivre (?:mon|votre|le) (?:colis|commande)",
        r"retard de livraison",
        "dedouanement",
        r"(?:frais|droits) de douane",
        r"(?:etiquette|demande) de retour",
        r"retour recu",
        r"remboursement effectue",
        "votre remboursement",
        r"annulation de (?:votre )?commande",
    ),
    "it": (
        r"conferma (?:d'|dell')?ordine",
        r"ordine (?:confermato|ricevuto|spedito|consegnato|annullato)",
        r"abbiamo ricevuto il tuo ordine",
        r"grazie per (?:il tuo |l')(?:ordine|acquisto)",
        r"numero (?:d'|dell')?ordine",
        r"n\. ordine",
        r"(?:e|sono) (?:stat[oaie] )?(?:spedit[oaie]|consegnat[oaie])",
        r"pacco (?:spedito|consegnato)",
        r"(?:conferma di )?spedizione confermata",
        "conferma di spedizione",
        "in viaggio",
        "in transito",
        r"in consegna",
        r"sara consegnat[oa]",
        r"consegna (?:prevista|stimata|ritardata|non riuscita)",
        r"consegnat[oa]",
        "tentativo di consegna",
        "mancata consegna",
        r"non e stato possibile consegnare",
        r"(?:pronto|disponibile) per (?:il ritiro|essere ritirato)",
        r"in attesa di ritiro",
        r"(?:codice|punto) di ritiro",
        "fermopoint",
        r"(?:codice|numero) di (?:tracciamento|spedizione|tracking)",
        r"(?:traccia|segui) (?:il tuo ordine|la (?:tua )?spedizione|il tuo pacco)",
        "in ritardo",
        r"ritardo nella consegna",
        "sdoganamento",
        "dogana",
        r"dazi doganali",
        r"(?:etichetta|richiesta) di reso",
        "reso ricevuto",
        "rimborso emesso",
        r"il tuo rimborso",
        r"annullamento (?:dell')?ordine",
    ),
    "nl": (
        r"(?:order|bestel)bevestiging",
        r"bestelling (?:bevestigd|ontvangen|verzonden|bezorgd|geannuleerd)",
        r"bedankt voor (?:je|uw) (?:bestelling|aankoop)",
        r"(?:bestel|order|zending)nummer",
        r"(?:is|zijn|wordt|worden) (?:verzonden|bezorgd|afgeleverd)",
        r"(?:pakket|pakketje|bestelling|zending) (?:is|zijn) (?:nu )?onderweg",
        r"(?:wordt )?vandaag bezorgd",
        r"bezorger is onderweg",
        r"verwachte (?:bezorging|levering)",
        r"bezorg(?:moment|venster|poging)",
        r"pakket (?:verzonden|bezorgd)",
        r"succesvol bezorgd",
        "niet thuis",
        r"kon niet (?:worden )?bezorgd",
        "niet bezorgd",
        "klaar om op te halen",
        "ligt klaar",
        r"kan (?:worden )?opgehaald",
        "af te halen",
        r"(?:ophaal|afhaal)code",
        r"track\s*(?:&|en)\s*trace",
        r"volg (?:je|uw) (?:pakket|bestelling|zending)",
        r"tracking(?:nummer|code)",
        r"vertraa?g\w*",
        "douane",
        "inklaring",
        "invoerrechten",
        "retourlabel",
        r"(?:retourzending|retour) ontvangen",
        r"terugbetaling",
        r"annulering",
        r"(?:pakket|afhaal|ophaal)punt",
        r"pakket(?:automaat|kluis)",
    ),
}

WEAK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "en": (
        r"(?:your|my) (?:order|purchase|parcel|package|shipment|delivery|items?|returns?)",
        r"parcels?",
        r"shipments?",
        "shipped",
        "dispatched",
        "delivered",
        r"tracking",
        "courier",
        "customs",
        r"refund(?:ed)?",
        r"(?:pick[- ]?up|collection) point",
        r"(?:parcel )?lockers?",
        r"arriv(?:ing|es)",
        "delayed",
    ),
    "pt": (
        r"(?:a sua|a tua) encomenda",
        r"(?:o seu|o teu) pedido",
        r"encomendas?",
        r"obje(?:c)?to",
        r"remessas?",
        "envio",
        r"enviad[oa]s?",
        r"expedid[oa]s?",
        "entrega",
        r"entregues?",
        "levantamento",
        "seguimento",
        "rastreio",
        "devolucao",
        "reembolso",
        r"atrasad[oa]s?",
        "transportadora",
        "estafeta",
    ),
    "es": (
        r"(?:tu|su) pedido",
        r"pedidos?",
        r"envios?",
        r"enviad[oa]s?",
        r"paquetes?",
        "entrega",
        r"entregad[oa]s?",
        "reparto",
        "recogida",
        "seguimiento",
        "devolucion",
        "reembolso",
        r"retras(?:o|ad[oa]s?)",
        r"llega(?:ra)?",
        "transportista",
        "mensajero",
    ),
    "de": (
        r"(?:ihre|deine) bestellung",
        "bestellung",
        r"(?:ihr|dein) paket",
        r"pakete?",
        r"sendung(?:en)?",
        "lieferung",
        "zustellung",
        "versand",
        "versandt",
        "verschickt",
        "abholung",
        "zoll",
        "retoure",
        "rucksendung",
        "lieferdatum",
        "paketshop",
        "filiale",
        "paketbote",
        "zusteller",
    ),
    "fr": (
        r"(?:votre|ta) commande",
        "commande",
        r"(?:votre|ton) colis",
        "colis",
        "livraison",
        r"expediee?s?",
        "expedition",
        "envoi",
        "suivi",
        "retrait",
        r"(?:point )?relais",
        "douane",
        "retour",
        "remboursement",
        r"retardee?s?",
        "consigne",
        "transporteur",
        "livreur",
    ),
    "it": (
        r"(?:il tuo|il suo) ordine",
        "ordine",
        r"(?:il tuo|il suo) pacco",
        "pacco",
        "pacchi",
        "spedizione",
        r"spedit[oa]",
        "consegna",
        "ritiro",
        "reso",
        "rimborso",
        "tracciamento",
        "corriere",
    ),
    "nl": (
        r"(?:je|uw) bestelling",
        "bestelling",
        r"(?:je|uw) pakket",
        r"pakket(?:je)?",
        "zending",
        "bezorging",
        "bezorgd",
        "levering",
        "verzending",
        "verzonden",
        "retour",
        "afhalen",
        "ophalen",
        "bezorger",
    ),
}

# Carrier names count as weak keywords in every language.
CARRIER_KEYWORDS: tuple[str, ...] = (
    "amazon logistics",
    "bpost",
    "brt",
    "chronopost",
    "colissimo",
    "correos",
    r"correos ?express",
    r"ctt(?: expresso?)?",
    "deutsche post",
    "dhl",
    "dpd",
    "evri",
    "fedex",
    "gls",
    "inpost",
    "la poste",
    "mondial relay",
    "mrw",
    "nacex",
    "paack",
    "postnl",
    "poste italiane",
    "royal mail",
    "seur",
    "tnt",
    "ups",
    "usps",
    "vinted go",
)

# "Order #1001", "Pedido n.º 1001", "Bestellung Nr. 1001", "Commande : 123456"...
_ORDER_NUMBER_RE = re.compile(
    r"(?<![a-z0-9])(?:order|pedido|encomenda|bestellung|auftrag|commande|ordine"
    r"|bestelling)\s*(?:#\s*[a-z0-9-]*\d"
    r"|(?:n\.?\s*[o\u00b0]\.?|nr\.?|no\.?|num\.?|number|numero|nummer)\s*:?\s*#?\s*"
    r"[a-z0-9-]*\d"
    r"|:\s*#?\s*\d{3,})"
)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_OPTIONAL_SPACE_RE = re.compile(r" \?")


def _fragment(pattern: str) -> str:
    """Turn a keyword into a regex fragment (flexible spaces and apostrophes)."""
    pattern = _OPTIONAL_SPACE_RE.sub(r"\\s*", pattern)
    return pattern.replace(" ", r"\s+").replace("'", "['\u2019]")


def _compile(groups: Iterable[Iterable[str]]) -> re.Pattern[str]:
    """Compile keyword lists into one whole-word regex, longest first."""
    patterns = sorted({p for group in groups for p in group}, key=len, reverse=True)
    body = "|".join(_fragment(pattern) for pattern in patterns)
    return re.compile(rf"(?<![a-z0-9])(?:{body})(?![a-z0-9])")


_MARKETING_PHRASE_RE = _compile(MARKETING_PHRASES.values())
_MARKETING_RE = _compile(MARKETING_WORDS.values())
_STRONG_RE = _compile(STRONG_KEYWORDS.values())
_WEAK_RE = _compile([*WEAK_KEYWORDS.values(), CARRIER_KEYWORDS])


def _sender_domain(sender: str) -> str:
    """Domain of "a@b.example", "Name <a@b.example>" or a bare domain."""
    address = sender.strip()
    if "<" in address:
        address = address.rpartition("<")[2].partition(">")[0]
    return address.rpartition("@")[2].strip().strip(".").lower()


def _prepare(subject: str, preview: str) -> str:
    """Fold subject and preview, without links and advertising phrases."""
    text = f"{subject}\n{preview}"[:MAX_CHARS]
    text = _EMAIL_RE.sub(" ", _URL_RE.sub(" ", text))
    return _MARKETING_PHRASE_RE.sub(" | ", fold(text))


def is_candidate(
    sender: str,
    subject: str,
    preview: str = "",
    *,
    trusted: Iterable[str] = (),
) -> bool:
    """Return True when an e-mail is likely about a parcel or an order.

    ``sender`` is the From address (a bare domain works too); ``trusted``
    holds extra domains the user chose to trust, which always pass like
    the known senders. Only headers and the provider's preview are used.
    """
    domain = _sender_domain(sender)
    if domain and (
        lookup(domain) is not None
        or organizational_domain(domain)
        in {organizational_domain(d) for d in trusted if d}
    ):
        return True
    text = _prepare(subject, preview)
    if _STRONG_RE.search(text) or _ORDER_NUMBER_RE.search(text):
        return True
    advertising = _MARKETING_PHRASE_RE.search(fold(subject[:MAX_CHARS]))
    if advertising or not _WEAK_RE.search(text):
        return False
    return "%" not in text and not _MARKETING_RE.search(text)
