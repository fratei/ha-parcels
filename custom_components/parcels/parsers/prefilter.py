"""Cheap check on headers before an e-mail body is downloaded.

The mail coordinator calls ``is_candidate`` with the sender, the subject
and the provider's short preview (Graph ``bodyPreview``, Gmail
``snippet``). Known senders (``senders.KNOWN_SENDERS``) always pass. Other
e-mails pass when their subject or preview has shipping or order words in
one of the seven supported languages:

* ``STRONG_KEYWORDS`` (status phrases such as "out for delivery",
  "foi entregue", "zugestellt", tracking and order-number labels, and
  delivery or pickup code labels such as "código de entrega" or
  "Zustellcode") always pass; a one-time password without a delivery word
  is a login or bank code and doesn't count;
* ``WEAK_KEYWORDS`` (generic words such as "parcel", "your order",
  "envio", "Lieferung" or a carrier name) pass unless the text also has
  advertising markers (``MARKETING_WORDS``, or a "%" sign).

Advertising phrases such as "free shipping" or "order now"
(``MARKETING_PHRASES``) are removed first, so they never count, and when
the subject has one, weak keywords don't count either. Keywords
are folded (lowercase, no accents), matched as whole words, and may hold
small regular expressions; a space matches any whitespace and an
apostrophe matches ' or its typographic form.

``has_shipping_words`` applies the strong keywords to a downloaded body,
for the parser dispatcher's safety net. There an order-number label alone
("Order number", "Número de encomenda") doesn't count: invoices and
account e-mails name the order too. Nor does a link to follow the order in
the shop's account pages ("Acompanhe a sua encomenda na área de cliente").

``known_sender_subject`` checks the subject of a known sender's e-mail
that its parser couldn't read. There carrier names don't count, and
neither do subjects about something else (``not_shipping_topic``):
requests for feedback and surveys (``FEEDBACK_TOPICS``), invoices
(``INVOICE_TOPICS``), service notices such as opening hours, fraud
warnings and terms (``NOTICE_TOPICS``), and the sender's app or offers to
send parcels (``PROMOTION_TOPICS``), even when they name an order. A
status in the same subject wins: a strong keyword, or a kind the parsers'
own wording finds there (``generic.detect_kind``), as in "Entrega
concluída: avalie a entrega". That wording also counts like a weak
keyword. A product's name in quotes ('Ordered: "Customer Feedback
Board"') is neither a topic nor a status.

The parser dispatcher gates what a parser read with ``feedback_topic``,
``sent_receipt`` (a carrier's receipt for a parcel handed in,
``SENT_RECEIPT_TOPICS``), ``message_topic`` (a marketplace's notice of a
seller's message, or a prompt to complain, ``MESSAGE_TOPICS``; anyone
but a carrier) and ``invoice_topic``: those e-mails name a parcel and its
last status, but bring no news about it. ``survey_request`` finds a
survey by its body when the subject has neither a status nor a request
for feedback ("A sua entrega de 4 de novembro"): an invitation to answer
questions or a survey (``SURVEY_ACTIONS``), not a request for a rating,
which delivery e-mails may have in their footers. A survey's opening
question counts as its topic only at the subject's end ("Tem um minuto?",
not "Tem um minuto? Levante a sua encomenda"). A message from whoever
brings the parcel ("Nova mensagem do seu estafeta") isn't a seller's,
and a status in the same subject wins there too. An invoice can
still bring news ("Your package is out for delivery today"):
``has_news_words`` is ``has_shipping_words`` without the words any
invoice has, such as tracking-number labels, links to follow the parcel,
thanks for the order and refunds.
"""

from __future__ import annotations

from collections.abc import Iterable
import re

from .generic import detect_kind
from .lang import fold
from .senders import lookup, organizational_domain

# Only this much of subject + preview is looked at.
MAX_CHARS = 2000
# And this much of a body, by has_shipping_words.
BODY_CHARS = 20_000

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
        r"(?:parcel|package|order|delivery|shipment) (?:is here|has arrived)",
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
        r"(?:pick[- ]?up|collection) (?:code|pin)",
        r"delivery (?:code|pin|passcode|otp)",
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
        r"entregamos (?:o|a|os|as) (?:seu|sua|teu|tua|seus|suas) (?:objeto|objecto|encomenda|pedido|envio|volume)s?",
        r"(?:encomenda|objeto|objecto|pedido|envio) chegou",
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
        r"codigo de (?:levantamento|recolha|retirada)",
        r"(?:codigo|pin|senha) (?:de|da|para|para a) entrega",
        r"codigo de confirmacao (?:de|da) entrega",
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
        r"(?:paquete|pedido|envio) (?:ha llegado|llego)",
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
        r"codigo de (?:recogida|retirada|recoleccion)",
        r"(?:codigo|pin|clave) de entrega",
        r"codigo de confirmacion de entrega",
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
        r"(?:paket|sendung|bestellung) ist (?:da|angekommen)",
        r"zustellversuch",
        r"nicht (?:zugestellt|angetroffen)",
        "benachrichtigungskarte",
        "abholbereit",
        r"(?:zur|bereit zur) abholung",
        r"abholung bereit",
        r"(?:zustell|liefer|abhol)(?:-| ?)(?:code|pin)",
        "packstation",
        "sendungsverfolgung",
        r"(?:sendung|paket) verfolgen",
        r"verfolgen sie ihre sendung",
        r"verfolge (?:dein|deine) (?:paket|sendung|bestellung)",
        r"(?:verzogert|verspatet|verspatung)",
        r"zoll(?:abfertigung|gebuhr\w*)",
        "einfuhrabgaben",
        "einfuhrumsatzsteuer",
        r"(?:zoll|import)(?:abgaben|gebuhren)",
        r"(?:beim|im|vom|durch den) zoll",
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
        r"(?:colis|commande) est arrivee?",
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
        r"code (?:de )?(?:retrait|livraison)",
        r"code de confirmation de livraison",
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
        r"(?:pacco|ordine|spedizione) e arrivat[oa]",
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
        r"(?:codice|pin) (?:di )?consegna",
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
        r"(?:pakket|pakketje|bestelling|zending) is (?:er|aangekomen)(?! nog niet)",
        r"succesvol bezorgd",
        "niet thuis",
        r"kon niet (?:worden )?bezorgd",
        "niet bezorgd",
        "klaar om op te halen",
        "ligt klaar",
        r"kan (?:worden )?opgehaald",
        "af te halen",
        r"(?:ophaal|afhaal|bezorg) ?(?:pin)?code",
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
        r"(?:pick[- ]?up|collection) (?:point|date)",
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
        r"(?:data|dia) (?:de|da) recolha",
        r"recolha (?:agendada|prevista|marcada)",
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
        r"abhol(?:datum|termin)",
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
        r"date d'(?:enlevement|collecte)",
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
        "ophaaldatum",
        "opgehaald",
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

# A survey's opening question ends the subject, maybe after a name ("Tem
# um minuto, Alex?"): "Tem um minuto? Levante a sua encomenda" and "Got a
# minute? Your parcel is waiting" are pickup reminders.
_ENDS_QUESTION = r"(?=(?:, ?[^\W\d_]+)? ?\? ?$)"

# Subjects of a known sender's e-mails about something else than a parcel,
# though they name an order or a delivery: requests for feedback, surveys,
# invoices and service notices (opening hours, fraud warnings, terms).
FEEDBACK_TOPICS: dict[str, tuple[str, ...]] = {
    "pt": (
        r"avali(?:e|a|ar|aria|arias)",
        r"avaliac(?:ao|oes)",
        # Not "classificação": customs' "classificação pautal".
        r"classifi(?:que|car|caria|carias)",
        r"opinia(?:o|oes)",
        "inquerito",
        "questionario",
        "como correu",
        r"como foi (?:a (?:sua|tua) )?(?:experiencia|entrega|compra)",
        "gostou",
        r"o que (?:achou|achaste)",
        r"(?:conte|diga)-nos (?:o que (?:achou|achaste|acha|pensa)|como correu|a (?:sua|tua) experiencia)",
        r"ajud(?:e|a)-nos a melhorar",
        r"(?:sua|tua) experiencia com",
        "satisfacao",
        r"(?:tem|tens|dispoe de) (?:um )?(?:minuto|minutinho|momento|instante)"
        + _ENDS_QUESTION,
        r"(?:queremos|gostariamos de|adorariamos) (?:ouvi-lo|ouvi-la|ouvir-te|ouvir-vos)",
    ),
    "es": (
        r"valora(?:nos|r|rias|ria)?",
        "valoracion",
        r"opinion(?:es)?",
        "encuesta",
        r"que tal (?:fue|ha ido)",
        r"que te (?:ha parecido|parecio)",
        r"cuentanos (?:que|como|tu opinion|tu experiencia)",
        r"como (?:fue|ha sido) (?:tu|su) (?:experiencia|entrega|compra)",
        "ayudanos a mejorar",
        r"(?:tu|su) experiencia con",
        r"resenas?",
        r"califica(?:nos|r|rias|ria)?",
        "satisfaccion",
        r"(?:tienes|tiene|dispones de|dispone de) un (?:minuto|minutito|momento)"
        + _ENDS_QUESTION,
        r"(?:queremos|nos encantaria|nos gustaria) (?:escucharte|escucharle|saber de (?:ti|usted))",
    ),
    "en": (
        # "Review your delivery options" asks for a choice, not for feedback.
        r"(?<!under\s)reviews?(?! (?:and confirm )?(?:your |the )?(?:delivery|shipping|address))",
        r"rate (?:us|your|our|the|this|it|how|my)",
        "please rate",
        "would you rate",
        r"ratings?",
        "survey",
        "feedback",
        "how did we do",
        "how did it go",
        r"how was (?:your|the)",
        "your opinion",
        "tell us what you think",
        "tell us about",
        # Not "Tell us how you'd like your parcel delivered".
        r"tell us how (?:we did|it went|we're doing)",
        "help us improve",
        "your experience with",
        "questionnaire",
        "satisfaction",
        r"share your (?:thoughts|experience)",
        "meet your expectations",
        r"(?:got|have you got|do you have|have you) a (?:minute|moment|sec|second)"
        + _ENDS_QUESTION,
        r"(?:we'd|we would) (?:love|like) to hear (?:from you|your)",
        r"we want to hear (?:from you|your)",
    ),
    "de": (
        r"bewertung\w*",
        r"bewerten?",
        r"rezension\w*",
        "umfrage",
        "wie zufrieden",
        r"(?:ihre|deine) meinung",
        "wie gefallt",
        # Not "Helfen Sie uns bei der Zustellung".
        r"(?:helfen sie|hilf) uns,? (?:besser zu werden|(?:uns|unseren service) zu verbessern)",
        r"wie war (?:ihre|deine|die) (?:zustellung|lieferung|erfahrung)",
        "kundenzufriedenheit",
        r"(?:haben sie|hast du) (?:kurz )?(?:eine minute|einen moment|zeit)"
        + _ENDS_QUESTION,
        r"wir (?:mochten|wurden) (?:gerne? )?von (?:ihnen|dir) horen",
    ),
    "fr": (
        r"donnez(?:[- ]nous)? votre avis",
        # Not "avis de passage" nor "avis d'expédition", delivery notices.
        r"votre avis(?! d)",
        r"(?:laissez|deposez|partagez) (?:un|votre) avis",
        r"avis clients?",
        r"enquete (?:de satisfaction|client|qualite)",
        r"notez (?:votre|vos|nous|notre)",
        r"evalue(?:z|riez|r)",
        r"aidez-nous a (?:nous )?ameliorer",
        "votre opinion",
        "qu'en pensez-vous",
        "qu'avez-vous pense",
        r"comment s'est passee?",
        r"(?:avez-vous|as-tu|vous avez) (?:une minute|un instant|un moment|quelques minutes)"
        + _ENDS_QUESTION,
        # Not "Nous aimerions connaître votre disponibilité".
        r"nous (?:aimerions|voudrions) (?:connaitre|savoir|avoir) "
        r"(?:votre (?:experience|ressenti)|ce que vous (?:en )?pensez|de vos nouvelles)",
    ),
    "it": (
        r"recension\w*",
        "sondaggio",
        "questionario",
        r"valuta (?:il tuo|la tua)",
        # Not "valuta" alone: a currency.
        r"valuter(?:esti|ebbe|ai)",
        "valutaci",
        "aiutaci a migliorare",
        "opinione",
        "cosa ne pensi",
        "soddisfazione",
        "com'e andata",
        "come e andata",
        r"(?:hai|ha|avete) (?:un minuto|un momento|qualche minuto|due minuti)"
        + _ENDS_QUESTION,
        r"(?:tuo|suo|vostro) parere",
        r"(?:ci piacerebbe|vorremmo) (?:sentirti|sentirla|sentirvi)",
    ),
    "nl": (
        "beoordeel",
        r"beoordeling\w*",
        "vragenlijst",
        r"(?:vul|doe mee aan) (?:de |onze |deze )?enquete",
        r"(?:je|uw) mening",
        "hoe was",
        r"hoe vond (?:je|u)",
        "tevredenheid",
        r"wat (?:vond|vind) (?:je|u)",
        r"help ons (?:te )?verbeteren",
        r"(?:heb|hebt|heeft) (?:je|jij|u) (?:even )?(?:een minuut|een minuutje|een momentje|tijd)"
        + _ENDS_QUESTION,
        r"(?:we|wij) horen graag van (?:je|jou|u)",
    ),
}

# A body's invitation to answer a survey: questions to answer, or a survey
# or questionnaire to fill in. Not a request for a rating ("Avalie a
# entrega", "Rate your delivery", "How did we do?"): a carrier's delivery
# e-mail may have one in its footer.
SURVEY_ACTIONS: dict[str, tuple[str, ...]] = {
    "pt": (
        r"respond(?:a|e|er) (?:a|as|aos) (?:\d+|uma|duas|tres|quatro|cinco|algumas|umas"
        r"|poucas|estas|seguintes) (?:(?:breves|curtas|rapidas|pequenas|simples) )?perguntas?",
        r"(?:respond|particip|preench|complet)(?:a|e|er|ar)\b.{0,30}?"
        r"(?:inqueritos?|questionarios?|pesquisa de satisfacao|sondagem)",
    ),
    "es": (
        r"(?:responde|responda|contesta|conteste|responder|contestar) (?:a )?(?:\d+|unas"
        r"|algunas|pocas|dos|tres|cuatro|cinco|estas) "
        r"(?:(?:breves|cortas|rapidas|sencillas) )?preguntas",
        r"(?:participa|participe|participar|completa|complete|completar|rellena|rellene"
        r"|rellenar|responde|responda|contesta|conteste) (?:en |a )?(?:nuestra |la |esta "
        r"|una )?(?:breve |corta |rapida |pequena )?(?:encuesta|cuestionario)",
        r"(?:cuentanos|dinos) como lo (?:hemos hecho|hicimos)",
    ),
    "en": (
        r"(?:answer|take|complete|fill (?:in|out)|respond to|participate in|take part in) "
        r"(?:a |our |this |the |my )?(?:(?:short|quick|brief|\d+-minute|one-minute"
        r"|two-minute|customer|satisfaction) )*(?:survey|questionnaire)",
        r"answer (?:\d+|one|two|three|four|five|a few|some|these|a couple of) "
        r"(?:(?:short|quick|brief|simple) )?questions?",
        r"(?:tell|let) us (?:know )?how we did",
        r"(?:tell|let) us (?:know )?how we(?:'re| are) doing",
    ),
    "de": (
        r"an (?:unserer|der|einer|dieser) (?:kurzen |kleinen )?(?:kunden)?"
        r"(?:umfrage|befragung) teil(?:nehmen|zunehmen)?",
        r"(?:fur|zu) (?:unsere|unserer|die|eine|diese) (?:kurze |kleine )?(?:kunden)?"
        r"(?:umfrage|befragung)",
        r"zur (?:kurzen )?(?:kunden)?umfrage",
        r"beantworten sie (?:\d+|ein paar|einige|wenige|zwei|drei|vier|funf) "
        r"(?:(?:kurze|kurzen) )?fragen",
        r"(?:fullen sie|beantworten sie) (?:unseren|den|einen) (?:kurzen )?fragebogen",
    ),
    "fr": (
        r"repondez a (?:\d+|quelques|deux|trois|quatre|cinq|ces) "
        r"(?:(?:courtes|breves|petites) )?questions?",
        r"(?:participez|repondez|repondre|participer|remplissez|remplir|completez|completer) "
        r"(?:a |au )?(?:notre |cette |une |l')?(?:courte |breve |petite )?"
        r"(?:enquete|questionnaire|sondage)",
    ),
    "it": (
        r"rispond(?:i|a|ere) a (?:\d+|alcune|poche|due|tre|quattro|cinque|queste) "
        r"(?:(?:brevi|semplici|veloci) )?domande",
        r"(?:partecipa|partecipare|compila|compilare|rispondi|rispondere) (?:al nostro "
        r"|il nostro |al |a |il |questo |un )?(?:breve )?(?:sondaggio|questionario)",
    ),
    "nl": (
        r"beantwoord (?:\d+|een paar|enkele|twee|drie|vier|vijf|deze) "
        r"(?:(?:korte|snelle|eenvoudige) )?vragen",
        r"(?:vul|doe mee aan|neem deel aan) (?:de |onze |deze |een )?(?:korte )?"
        r"(?:enquete|vragenlijst)",
        r"laat (?:ons|het ons) weten hoe we het (?:deden|hebben gedaan)",
    ),
}

INVOICE_TOPICS: tuple[str, ...] = (
    r"faturas?",
    r"facturas?",
    r"notas? de credito",
    r"invoices?",
    r"credit notes?",
    r"(?<!auf\s)rechnung\w*",
    "gutschrift",
    r"factures?",
    r"fattur[ae]",
    "nota di credito",
    r"factu(?:ur|ren)",
    "creditnota",
)

# Subjects of a carrier's receipt for a parcel handed in at its counter:
# the parcel's number and its first status, but no news.
SENT_RECEIPT_TOPICS: tuple[str, ...] = (
    r"(?:comprovativo|recibo) d[eo] (?:seu |teu |su |tu )?envio",
    r"(?:seu|teu) envio (?:[a-z0-9]+ )?foi aceite",
    r"talao de (?:envio|aceitacao)",
    r"justificante de (?:envio|admision)",
    "proof of postage",
    "postage receipt",
    r"(?:shipment|shipping) receipt",
    r"einlieferungs(?:beleg|quittung|bestatigung)",
    "preuve de depot",
    r"recu (?:de depot|d'envoi)",
    r"ricevuta di (?:spedizione|accettazione)",
    "verzendbewijs",
)

NOTICE_TOPICS: tuple[str, ...] = (
    # Opening hours.
    "horario especial",
    r"horarios? de (?:natal|navidad|verao|verano|funcionamento|apertura|abertura|atendimento|atencion)",
    r"opening (?:hours|times)",
    "holiday hours",
    "offnungszeiten",
    "horaires d'ouverture",
    r"horaires (?:des fetes|de noel|d'ete|speciaux)",
    "orari di apertura",
    r"orari (?:festivi|natalizi|estivi)",
    "openingstijden",
    # Fraud warnings.
    r"fraud\w*",
    r"scams?",
    r"(?:ph|sm)ishing",
    r"burlas?",
    r"estafas?",
    r"betrug\w*",
    r"arnaques?",
    "hameconnage",
    r"truff[ae]",
    "oplichting",
    r"(?:mensagens|sms|e-?mails) (?:falsos|falsas|fraudulent[oa]s)",
    r"fake (?:sms|messages?|e-?mails?|texts?)",
    r"gefalschte?n? (?:sms|e-?mails?|nachrichten)",
    # Terms and privacy.
    "termos e condicoes",
    r"privacidad[e]?",
    "terminos y condiciones",
    "terms and conditions",
    r"terms of (?:service|use)",
    r"privacy (?:policy|notice)",
    r"datenschutz\w*",
    "agb",
    "conditions generales",
    "confidentialite",
    "termini e condizioni",
    r"informativa (?:sulla )?privacy",
    "algemene voorwaarden",
    r"privacy(?:beleid|verklaring)",
)

# Subjects of a marketplace's notice that a seller wrote, or of a prompt to
# complain about an order: they name an order, but what the seller says is
# not the carrier's news. A carrier's own message may be news: the parser
# dispatcher leaves carriers' e-mails to their parsers.
MESSAGE_TOPICS: dict[str, tuple[str, ...]] = {
    "pt": (
        r"recebe(?:u|ste) (?:uma |\d+ )?(?:nova |novas )?mensage(?:m|ns)(?: novas?)?",
        r"(?:tem|tens) (?:uma |\d+ )?(?:nova |novas )?mensage(?:m|ns)",
        r"nova mensagem d(?:e|o|a)",
        r"mensage(?:m|ns) d[oa] (?:vendedor|comprador)",
        r"(?:abrir|abra|abre|apresentar|apresente|fazer|faca) (?:uma )?(?:reclamacao|disputa)",
    ),
    "es": (
        r"(?:ha|has) recibido (?:un |\d+ )?(?:nuevo |nuevos )?mensajes?",
        r"(?:tiene|tienes) (?:un |\d+ )?(?:nuevo |nuevos )?mensajes?",
        "nuevo mensaje de",
        r"mensajes? del (?:vendedor|comprador)",
        r"(?:abrir|abre|abra|presentar|presenta|presente) (?:una )?(?:reclamacion|disputa)",
    ),
    "en": (
        r"you(?:'ve| have) (?:received |got )?(?:a |\d+ )?(?:new )?messages?",
        "new message from",
        r"messages? from (?:the |your )?(?:seller|buyer)",
        r"(?:open|file|submit|raise) (?:a )?(?:claim|complaint|dispute)",
    ),
    "de": (
        r"(?:sie haben|du hast) (?:eine |\d+ )?(?:neue )?nachricht(?:en)?",
        r"neue nachricht (?:von|vom)",
        r"nachricht (?:vom|des) (?:verkaufer|handler|kaufer)s?",
        r"(?:eine )?reklamation (?:eroffnen|einreichen)",
        r"(?:eine )?beschwerde einreichen",
        r"(?:einen )?(?:streitfall|konflikt) eroffnen",
    ),
    "fr": (
        r"vous avez (?:recu )?(?:un |\d+ )?(?:nouveaux? )?messages?",
        r"tu as (?:recu )?(?:un )?(?:nouveau )?message",
        "nouveau message de",
        r"message (?:du vendeur|de l'acheteur)",
        r"(?:ouvrir|ouvrez|deposer|deposez) (?:une reclamation|un litige)",
    ),
    "it": (
        r"(?:hai|ha) ricevuto (?:un |\d+ )?(?:nuovo |nuovi )?messaggi(?:o)?",
        r"(?:hai|ha) (?:un |\d+ )?(?:nuovo |nuovi )messaggi(?:o)?",
        "nuovo messaggio da",
        r"messaggio (?:dal|del) venditore",
        r"(?:aprire|apri|presentare|presenta) (?:un |una )?(?:reclamo|contestazione|controversia)",
    ),
    "nl": (
        r"(?:u heeft|u hebt|je hebt) (?:een |\d+ )?(?:nieuw |nieuwe )?bericht(?:en)?",
        "nieuw bericht van",
        r"bericht van (?:de |je |uw )?verkoper",
        r"(?:een )?klacht (?:indienen|openen)",
        r"(?:dien|open) (?:een )?klacht",
        r"(?:een )?geschil (?:openen|starten)",
    ),
}

# Whoever brings the parcel: a message from them may be news.
_COURIERS: tuple[str, ...] = (
    "estafeta",
    "motorista",
    "condutor",
    "carteiro",
    "entregador",
    "transportadora",
    "repartidor",
    "transportista",
    "conductor",
    "mensajero",
    "cartero",
    "driver",
    "courier",
    "carrier",
    "postman",
    r"(?:paket|post)?(?:zusteller|bote)",
    "fahrer",
    "kurier",
    "livreur",
    "chauffeur",
    "transporteur",
    "facteur",
    "coursier",
    "corriere",
    "autista",
    "fattorino",
    "postino",
    "bezorger",
    "koerier",
    "postbode",
)

# Subjects promoting the sender's app or its offers to send parcels: not
# about a parcel, though the body may still be (see has_shipping_words).
PROMOTION_TOPICS: tuple[str, ...] = (
    r"(?:nova|nueva|new|neue|nuova|nieuwe|nouvelle) (?:app|aplicacao|aplicacion|applicazione|application)",
    r"(?:con l'|avec l'|dans l')app",
    r"(?:com a|con la|met de|mit der|with the|with our|in der|nella) app",
    r"(?:descarga|descarregue|descarrega|download|scarica|telecharge[rz]?|lade) (?:\S+ )?(?:app|aplicacao|aplicacion|applicazione|application)",
    r"envi[ae] as (?:suas|tuas) encomendas",
    "envia tus paquetes",
    r"pakete? (?:\S+ )?versenden",
    r"send (?:your )?parcels",
    "ship more",
    "envoyez vos colis",
    "spedisci",
    r"pakket(?:ten)? versturen",
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
# Starts only where a run of address characters starts: linear on long runs.
_EMAIL_RE = re.compile(r"(?<![\w.+\-])[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_OPTIONAL_SPACE_RE = re.compile(r" \?")
# The strong keywords that only label an order's number: invoices and
# account e-mails name the order too, so in a body they aren't news.
_ORDER_LABELS = (
    r"order (?:number|no|nr)",
    r"numero (?:de|da|do|del) (?:encomenda|pedido)",
    r"n\.? ?[o\u00b0]\.? ?(?:de |da |do )?(?:encomenda|pedido)",
    r"(?:bestell|auftrags)nummer",
    "bestellnr",
    r"numero de commande",
    r"n\.? ?[o\u00b0]\.? ?(?:de )?commande",
    r"numero (?:d'|dell')?ordine",
    r"n\. ordine",
    r"(?:bestel|order)nummer",
)
# Links to follow an order in the shop's account pages ("Acompanhe a sua
# encomenda na área de cliente"): account e-mails have them too.
_ACCOUNT_TRACKING = (
    r"(?:acompanhe|acompanha|siga|segue|consulte) (?:o estado d[ao] )?"
    r"(?:a sua |a tua |o seu |o teu |sua |tua |seu |teu )?(?:encomenda|pedido|envio|objeto)s? "
    r"(?:na|no|em) (?:sua |tua )?(?:area (?:de |do )?cliente|area pessoal|conta|perfil|app|aplicacao)",
    r"(?:sigue|consulta|rastrea) (?:el estado de )?(?:tu |su )?(?:pedido|envio|paquete)s? "
    r"(?:en|desde) (?:tu |su |la )?(?:cuenta|area (?:de )?cliente|perfil|app|aplicacion)",
    r"track (?:your|my) (?:order|parcel|package|shipment|delivery)s? (?:in|on|from|via) "
    r"(?:your|my|the) (?:account|app|customer area|profile)",
    r"(?:verfolge|verfolgen sie) (?:deine|ihre|dein|ihr) (?:bestellung|sendung|paket)(?:en|e)? "
    r"(?:in|im|uber) (?:deinem |ihrem |dem |der )?(?:kundenkonto|konto|app|kundenbereich)",
    r"suivez (?:votre|vos) (?:commande|colis)s? (?:dans|depuis|sur) (?:votre |l')"
    r"(?:espace client|compte|application|app)",
    r"(?:segui|traccia|monitora) (?:il tuo ordine|la (?:tua )?spedizione|il tuo pacco) "
    r"(?:nel|dal|sul|nella|dalla|sulla) (?:tuo |tua )?(?:account|area (?:clienti|personale|riservata)|profilo|app)",
    r"volg (?:je|uw) (?:bestelling|pakket|zending)(?:en)? (?:in|via|op) (?:je|uw|de) "
    r"(?:account|klantenaccount|app|mijn omgeving)",
)

# The strong keywords that any invoice or receipt has: tracking-number
# labels and links, thanks for the order, and refunds. They aren't news.
_TRACKING_LABELS = (
    r"tracking (?:number|code|id|information|info|details|link)",
    r"track (?:your|my) (?:order|parcel|package|shipment|delivery)",
    r"track (?:order|parcel|package|shipment)",
    r"(?:numero|codigo) (?:de|do) (?:seguimento|rastreio|objeto|objecto)",
    r"(?:acompanhe|siga|seguir|rastrear|rastreie) (?:a sua |a tua |o seu |o teu )?"
    r"(?:encomenda|pedido|envio|objeto)",
    r"(?:numero|codigo) de seguimiento",
    r"(?:sigue|rastrea|seguimiento de) (?:tu |su |el |del )?(?:pedido|envio|paquete)",
    r"(?:sendungs|paket|tracking)nummer",
    "sendungsverfolgung",
    r"(?:sendung|paket) verfolgen",
    r"verfolgen sie ihre sendung",
    r"verfolge (?:dein|deine) (?:paket|sendung|bestellung)",
    r"numero de suivi",
    r"suivi de (?:colis|commande|livraison)",
    r"suivre (?:mon|votre|le) (?:colis|commande)",
    r"(?:codice|numero) di (?:tracciamento|spedizione|tracking)",
    r"(?:traccia|segui) (?:il tuo ordine|la (?:tua )?spedizione|il tuo pacco)",
    "zendingnummer",
    r"track\s*(?:&|en)\s*trace",
    r"volg (?:je|uw) (?:pakket|bestelling|zending)",
    r"tracking(?:nummer|code)",
)
_ORDER_THANKS = (
    r"order (?:confirmation|confirmed|received)",
    r"thanks? (?:you )?for your (?:order|purchase)",
    r"received your order",
    r"confirmacao (?:de|da|do) (?:encomenda|pedido)",
    r"(?:encomenda|pedido) (?:confirmad[oa]|recebid[oa])",
    r"recebemos (?:a sua|a tua|o seu|o teu) (?:encomenda|pedido)",
    r"obrigad[oa] (?:pela|pelo) (?:sua|tua|seu|teu) (?:encomenda|compra|pedido)",
    r"confirmacion (?:de|del|de tu|de su) pedido",
    r"pedido (?:confirmado|recibido)",
    r"hemos recibido (?:tu|su) pedido",
    r"gracias por (?:tu|su) (?:pedido|compra)",
    r"(?:bestell|auftrags)bestatigung",
    r"bestellung (?:bestatigt|eingegangen|erhalten)",
    r"(?:vielen )?dank fur (?:ihre|deine) bestellung",
    r"confirmation de (?:votre |la )?commande",
    r"commande (?:confirmee|recue)",
    r"merci (?:pour|de) votre (?:commande|achat)",
    r"nous avons bien recu votre commande",
    r"conferma (?:d'|dell')?ordine",
    r"ordine (?:confermato|ricevuto)",
    r"abbiamo ricevuto il tuo ordine",
    r"grazie per (?:il tuo |l')(?:ordine|acquisto)",
    r"(?:order|bestel)bevestiging",
    r"bestelling (?:bevestigd|ontvangen)",
    r"bedankt voor (?:je|uw) (?:bestelling|aankoop)",
)
_REFUND_LABELS = (
    r"refund (?:issued|processed|confirmation)",
    "your refund",
    r"reembolso (?:emitido|processado|efetuado|procesado|realizado)",
    r"o (?:seu|teu) reembolso",
    r"(?:tu|su) reembolso",
    r"(?:ruck)?erstattung",
    r"remboursement effectue",
    "votre remboursement",
    "rimborso emesso",
    r"il tuo rimborso",
    r"terugbetaling",
)
# Quotes around a product's name ('Ordered: "Customer Feedback Board"'),
# up to the subject's end when it was cut.
_QUOTES = str.maketrans(dict.fromkeys("\u201c\u201d\u201e\u201f\u00ab\u00bb", '"'))
_QUOTED_RE = re.compile(r'"[^"]*(?:"|$)')


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
_WEAK_NO_CARRIER_RE = _compile(WEAK_KEYWORDS.values())
_ORDER_LABEL_RE = _compile([_ORDER_LABELS])
_BODY_LABEL_RE = _compile([_ORDER_LABELS, _ACCOUNT_TRACKING])
_TOPIC_RE = _compile(
    [*FEEDBACK_TOPICS.values(), INVOICE_TOPICS, NOTICE_TOPICS, PROMOTION_TOPICS]
)
_FEEDBACK_RE = _compile(FEEDBACK_TOPICS.values())
_SURVEY_ACTION_RE = _compile(SURVEY_ACTIONS.values())
_MESSAGE_RE = _compile(MESSAGE_TOPICS.values())
_COURIER_RE = _compile([_COURIERS])
_SENT_RECEIPT_RE = _compile([SENT_RECEIPT_TOPICS])
_INVOICE_RE = _compile([INVOICE_TOPICS])
_NEWS_LABEL_RE = _compile(
    [_ORDER_LABELS, _ACCOUNT_TRACKING, _TRACKING_LABELS, _ORDER_THANKS, _REFUND_LABELS]
)


def _sender_domain(sender: str) -> str:
    """Domain of "a@b.example", "Name <a@b.example>" or a bare domain."""
    address = sender.strip()
    if "<" in address:
        address = address.rpartition("<")[2].partition(">")[0]
    return address.rpartition("@")[2].strip().strip(".").lower()


def _clean(text: str) -> str:
    """Fold text, without links, addresses and advertising phrases."""
    text = _EMAIL_RE.sub(" ", _URL_RE.sub(" ", text))
    return _MARKETING_PHRASE_RE.sub(" | ", fold(text))


def _prepare(subject: str, preview: str) -> str:
    """Fold subject and preview, without links and advertising phrases."""
    return _clean(f"{subject}\n{preview}"[:MAX_CHARS])


def has_shipping_words(text: str) -> bool:
    """Return True when an e-mail body has strong shipping keywords.

    The first ``BODY_CHARS`` are read. Order-number labels alone don't
    count, nor do links to follow the order in the shop's account pages,
    links and advertising phrases.
    """
    folded = _BODY_LABEL_RE.sub(" | ", _clean(text[:BODY_CHARS]))
    return _STRONG_RE.search(folded) is not None


def has_news_words(text: str) -> bool:
    """Return True when an e-mail body brings news about a parcel.

    Like ``has_shipping_words``, but the strong keywords that any invoice
    or receipt has don't count either: tracking-number labels and links
    to follow the parcel, thanks for the order, and refunds.
    """
    folded = _NEWS_LABEL_RE.sub(" | ", _clean(text[:BODY_CHARS]))
    return _STRONG_RE.search(folded) is not None


def _subject_text(subject: str) -> str:
    """Fold a subject without order-number labels."""
    return _ORDER_LABEL_RE.sub(" | ", _prepare(subject, ""))


def _unquoted(subject: str) -> str:
    """Return a subject without the names in quotes."""
    return _QUOTED_RE.sub(" | ", subject[:MAX_CHARS].translate(_QUOTES))


def _topic_text(subject: str) -> str:
    """Fold a subject without order-number labels and quoted names."""
    return _subject_text(_unquoted(subject))


def _kind_in_subject(subject: str) -> bool:
    """Return True when the parsers' own wording finds a kind in a subject.

    "Entrega concluída" or "Delivery complete" is a status for the parsers,
    so it is for the gate too; a product's name in quotes doesn't count.
    """
    return detect_kind(_unquoted(subject))[1] == "subject"


def _no_status(subject: str) -> bool:
    """Return True when a subject has no status or other strong keyword."""
    return _STRONG_RE.search(_topic_text(subject)) is None and not _kind_in_subject(
        subject
    )


def not_shipping_topic(subject: str) -> bool:
    """Return True when a subject is about feedback, an invoice or a notice.

    Those subjects can name an order ("Fatura da encomenda #1912"); a
    status in the same subject ("foi entregue: avalie a entrega") wins,
    and a product's name in quotes is no topic.
    """
    return _TOPIC_RE.search(_topic_text(subject)) is not None and _no_status(subject)


def feedback_topic(subject: str) -> bool:
    """Return True when a subject asks for feedback or a review, no status."""
    return _FEEDBACK_RE.search(_topic_text(subject)) is not None and _no_status(subject)


def survey_request(subject: str, text: str) -> bool:
    """Return True when a body invites to answer a survey, under no status.

    "Responda a 3 perguntas sobre a entrega" or "Take our short survey",
    under a subject such as "A sua entrega de 4 de novembro". A request for
    a rating ("Avalie a entrega", "How did we do?") isn't one: a carrier's
    delivery e-mail may have it in its footer. The first ``BODY_CHARS`` are
    read, without links, addresses and advertising phrases.
    """
    return _no_status(subject) and (
        _SURVEY_ACTION_RE.search(_clean(text[:BODY_CHARS])) is not None
    )


def message_topic(subject: str) -> bool:
    """Return True for a seller's message or a prompt to complain, no status.

    "Recebeu uma mensagem referente à encomenda nº ..." names an order, but
    a message from the one who brings the parcel ("Nova mensagem do seu
    estafeta") may be news, and so is a status in the same subject.
    """
    text = _topic_text(subject)
    return (
        _MESSAGE_RE.search(text) is not None
        and _COURIER_RE.search(text) is None
        and _no_status(subject)
    )


def sent_receipt(subject: str) -> bool:
    """Return True for a receipt for a parcel handed in, no status."""
    return _SENT_RECEIPT_RE.search(_topic_text(subject)) is not None and _no_status(
        subject
    )


def invoice_topic(subject: str) -> bool:
    """Return True when a subject is an invoice, no status nor feedback."""
    text = _topic_text(subject)
    return (
        _INVOICE_RE.search(text) is not None
        and _FEEDBACK_RE.search(text) is None
        and _no_status(subject)
    )


def known_sender_subject(subject: str) -> bool:
    """Return True when a known sender's subject is about a parcel or an order.

    Like ``is_candidate`` for other senders, but carrier names don't count
    (a carrier names itself in all its e-mails), and neither do subjects
    about something else (``not_shipping_topic``), even naming an order.
    The parsers' own wording for a status counts like a weak keyword.
    """
    if not_shipping_topic(subject):
        return False
    text = _prepare(subject, "")
    if _STRONG_RE.search(text) or _ORDER_NUMBER_RE.search(text):
        return True
    advertising = _MARKETING_PHRASE_RE.search(fold(subject[:MAX_CHARS]))
    if advertising or not (
        _WEAK_NO_CARRIER_RE.search(text) or _kind_in_subject(subject)
    ):
        return False
    return "%" not in text and not _MARKETING_RE.search(text)


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
