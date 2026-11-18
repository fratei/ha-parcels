"""Fallback parser for e-mails from senders without a dedicated parser.

``parse_generic`` reads what most shipping e-mails contain: tracking
numbers in the text and in carrier tracking links (links are only read,
never fetched), the kind of e-mail from localised keywords (the subject
first, then the start of the body), the delivery date from anchored
phrases, order numbers from localised labels, pickup details, and the
merchant from the sender. Confidence is capped at 0.8, and at 0.5 when no
tracking number carries a check digit, so most generic results go to
"Needs review". An e-mail whose only news is a delivery PIN or a pickup
code for a parcel it identifies by tracking or order number gets the kind
``CODE`` and 0.7 (0.8 with a code label in the subject): it can only add
the code to a parcel that exists.

Keyword tables hold folded (lowercase, accent-free) regex fragments: a
space stands for any whitespace, " ?" for optional whitespace, and "'" for
either apostrophe. ``KIND_PHRASES`` are used in the subject and the body;
``SUBJECT_KEYWORDS`` are shorter and only trusted in the subject.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, tzinfo
import re
from urllib.parse import urlsplit

from ..const import MailKind
from .base import Eta, MailMessage, ParsedShipment, ParseResult, SenderVerdict
from .carriers import brand_carriers
from .codes import find_code, has_code_label, mask_codes
from .eta import find_eta
from .lang import detect_language, fold, fold_aligned
from .senders import SenderInfo, lookup, organizational_domain
from .tracking import (
    TrackingMatch,
    check_digit_ok,
    find_tracking_numbers,
    normalize_tracking_number,
    numbers_from_url,
    tracking_url,
    validate_tracking_number,
)

PARSER = "generic"
BASE_CONFIDENCE = 0.5
CHECK_DIGIT_BONUS = 0.2
SUBJECT_KIND_BONUS = 0.1
MAX_CONFIDENCE = 0.8
# Cap when tracking numbers were found but none has a check digit.
FORMAT_ONLY_CONFIDENCE = 0.5
# An e-mail that only gives a code for a parcel it identifies.
CODE_CONFIDENCE = 0.7
MAX_SUBJECT_CHARS = 500
# The kind is read from the subject, then from this much of the body.
KIND_BODY_CHARS = 2000
SCAN_CHARS = 20_000
MAX_LINKS = 100
MAX_SHIPMENTS = 10
MAX_ORDER_NUMBERS = 5
MAX_MERCHANT_CHARS = 60
MAX_POINT_CHARS = 80

# When several kinds match, the first one wins: a parcel that could not be
# delivered and waits at a pickup point is READY_FOR_PICKUP, a delivered
# e-mail that thanks for the order is DELIVERED, and so on.
KIND_PRECEDENCE: tuple[MailKind, ...] = (
    MailKind.CANCELLED,
    MailKind.RETURN,
    MailKind.CUSTOMS,
    MailKind.READY_FOR_PICKUP,
    MailKind.ATTEMPTED,
    MailKind.DELIVERED,
    MailKind.OUT_FOR_DELIVERY,
    MailKind.DELAYED,
    MailKind.IN_TRANSIT,
    MailKind.SHIPPED,
    MailKind.ORDER,
)

# Kinds for which a delivery date makes no sense.
NO_ETA_KINDS = frozenset({MailKind.DELIVERED, MailKind.RETURN, MailKind.CANCELLED})
# Kinds whose e-mails may give a locker code under a bare "Code:" label.
_LOCKER_KINDS = frozenset({MailKind.READY_FOR_PICKUP, MailKind.ATTEMPTED})

# "On its way" is SHIPPED for the parsers, but it fits a parcel in transit
# as well; ``detect_kind(..., on_the_way=False)`` leaves these out.
ON_THE_WAY_PHRASES: tuple[str, ...] = (
    r"(?:order|package|parcel|shipment|item|items)s? (?:is|are) (?:now )?on"
    r" (?:its|their|the) way",
    r"on (?:its|their) way to you",
    r"(?:esta|estao|vai|segue|seguiu) a caminho",
    r"(?:esta|estan|va|van) en camino",
    r"(?:sendung|paket|bestellung|lieferung)(?:en)? (?:ist|sind) (?:jetzt |nun )?"
    r"(?:unterwegs|auf dem weg)",
    r"auf dem weg zu (?:ihnen|dir)",
    r"(?:est|sont) (?:en route|en chemin)",
    r"(?:e|sono) in (?:viaggio|arrivo)",
    r"(?:pakket|pakketje|bestelling|zending)(?:en)? (?:is|zijn) (?:nu )?onderweg",
    r"(?:is|zijn) onderweg naar (?:je|jou|u)(?: toe)?",
)
ON_THE_WAY_KEYWORDS: tuple[str, ...] = (
    r"on (?:its|the|their) way",
    r"a caminho",
    r"(?:en|de) camino",
    r"unterwegs",
    r"auf dem weg",
    r"en (?:route|chemin)",
    r"in (?:arrivo|viaggio)",
    r"onderweg",
)

# Leaving a carrier's facility, a hub or the country of origin is
# IN_TRANSIT; leaving the shop's own warehouse ("has left our warehouse")
# stays SHIPPED. In English up to two words may name the place ("the DHL
# hub", "FedEx origin facility"), but not the shop's own premises.
_EN_PLACE_WORDS = (
    r"(?:(?!(?:our|the|a|an|in|at|on|to|for|by|with|and|or|of|from|warehouse"
    r"|fulfil+ment|seller|store|shop|logistics) )[a-z]+ ){0,2}?"
)
_EN_LEFT = r"(?:(?:has |have |had )?(?:left|departed)(?: from)?|departure from)"
_EN_PLACES = (
    r"(?:(?:sorting|sort|distribution|processing|parcel|delivery|transit|transfer"
    r"|exchange|regional|local|national|international|export|import|origin"
    r"|destination|network|carrier|courier|postal|mail) (?:centre|center|facility"
    r"|hub|depot|terminal|station|office|unit|location)|hubs?|depots?|terminals?"
    r"|gateway|airport)"
)
_PT_PLACES = (
    r"(?:centro (?:operacional|de distribuicao|de triagem|de tratamento|de operacoes"
    r"|de processamento|de transito)|hub|terminal|aeroporto|plataforma"
    r"(?! logistica)|delegacao|pais (?:de origem|de expedicao|de envio|de partida))"
)
_ES_PLACES = (
    r"(?:centro (?:de clasificacion|de distribucion|de tratamiento|operativo"
    r"|de operaciones|de procesamiento|de transito)|delegacion|plataforma"
    r"(?! logistica)|hub|terminal|aeropuerto|agencia|franquicia|pais (?:de origen"
    r"|de envio|de expedicion|de procedencia))"
)
_DE_PLACES = (
    r"(?:[a-z]+(?:-| ))?(?:(?:start|ziel|abgangs|eingangs|ausgangs)-?)?"
    r"(?:paketzentrum|paketverteilzentrum|verteilzentrum|sortierzentrum|briefzentrum"
    r"|frachtzentrum|umschlagzentrum|zustellbasis|zustellstutzpunkt|umschlagbasis"
    r"|depot|hub|terminal|flughafen|ursprungsland|herkunftsland|abgangsland"
    r"|ausgangsland|exportland|versandland|absendeland)"
)
_FR_PLACES = (
    r"(?:centre (?:de tri|de distribution|de traitement|colis|d'exploitation"
    r"|de transit|operationnel)|plate-?forme(?! logistique)(?: de tri"
    r"| de distribution| colis)?|site (?:de tri|de distribution|colis)|agence|hub"
    r"|depot|terminal|aeroport|pays (?:d'origine|d'expedition|de depart"
    r"|de provenance))"
)
_IT_PLACES = (
    r"(?:centro(?! logistico)|hub|deposito|filiale|terminale?|aeroporto"
    r"|polo(?! logistico)|piattaforma(?! logistica)|paese (?:d'origine|di origine"
    r"|di partenza|di provenienza))"
)
_NL_PLACES = (
    r"(?:[a-z]+(?:-| ))?(?:(?:sorteer|distributie|verdeel|post|pakket)centrum"
    r"|(?:sorteer|distributie)locatie|depot|hub|terminal|luchthaven|vliegveld"
    r"|land van (?:herkomst|oorsprong|verzending|vertrek))"
)

KIND_PHRASES: dict[MailKind, tuple[str, ...]] = {
    MailKind.CANCELLED: (
        r"(?:has|have) been cancell?ed",
        r"(?:was|were|is|are) (?:now )?cancell?ed",
        r"cancellation (?:of your order|confirmation|confirmed|complete)",
        r"(?:foi|foram) cancelad[ao]s?",
        r"cancelamento (?:da|de|do) (?:sua |seu |tua |teu )?(?:encomenda|pedido|compra)",
        r"(?:ha|han) sido (?:cancelad|anulad)[oa]s?",
        r"(?:fue|fueron) (?:cancelad|anulad)[oa]s?",
        r"cancelacion (?:de|del) (?:tu |su )?pedido",
        r"(?:wurde|wurden|ist|sind) (?:erfolgreich )?storniert",
        r"stornierung (?:der|ihrer|deiner) bestellung",
        r"stornierungsbestatigung",
        r"(?:a|ont) ete annulee?s?",
        r"annulation de (?:votre |ta )?commande",
        r"(?:e|sono) stat[oaie] (?:annullat|cancellat)[oaie]",
        r"annullamento (?:del |dell')?ordine",
        r"(?:is|zijn|werd|werden) geannuleerd",
        r"annulering van (?:je|jouw|uw) bestelling",
    ),
    MailKind.RETURN: (
        r"return (?:has been |was )?(?:received|confirmed|processed|approved"
        r"|authori[sz]ed|registered|accepted|completed)",
        r"(?:has|have) been returned",
        r"(?:was|were) returned",
        r"returned to (?:the )?sender",
        r"refund (?:has been |was )?(?:issued|processed|approved|initiated"
        r"|confirmed|completed)",
        r"(?:has|have) been refunded",
        r"(?:was|were) refunded",
        r"we(?:'ve| have) (?:received|processed) your return",
        r"devolucao (?:foi )?(?:registada|registrada|confirmada|recebida|aceite"
        r"|aprovada|concluida)",
        r"reembolso (?:foi )?(?:processado|efetuado|efectuado|emitido|aprovado"
        r"|realizado|concluido)",
        r"devolvid[oa]s? ao remetente",
        r"(?:foi|foram) devolvid[oa]s?",
        r"(?:foi|foram) reembolsad[oa]s?",
        r"devolucion (?:ha sido )?(?:registrada|confirmada|recibida|aceptada"
        r"|aprobada|completada)",
        r"reembolso (?:ha sido )?(?:procesado|emitido|aprobado|realizado"
        r"|efectuado|completado)",
        r"devuelt[oa]s? al remitente",
        r"(?:ha|han) sido devuelt[oa]s?",
        r"(?:ha|han) sido reembolsad[oa]s?",
        r"(?:rucksendung|retoure) (?:ist |wurde )?(?:eingegangen|erhalten|bestatigt"
        r"|registriert|bearbeitet)",
        r"(?:ruck)?erstattung (?:wurde |ist )?(?:veranlasst|bearbeitet|erfolgt"
        r"|ausgelost|angewiesen)",
        r"(?:wurde|wurden) (?:ihnen |dir )?(?:zuruck)?erstattet",
        r"(?:zuruck|retour) an (?:den )?absender",
        r"an den absender zuruck(?:geschickt|gesendet|gesandt)?",
        r"retour (?:a ete )?(?:enregistre|confirme|recu|accepte|valide)",
        r"remboursement (?:a ete )?(?:effectue|traite|emis|valide|confirme)",
        r"(?:a|ont) ete remboursee?s?",
        r"(?:retourne|renvoye)e?s? a l'expediteur",
        r"retour a l'expediteur",
        r"(?:reso|restituzione) (?:e stat[oa] )?(?:registrat|confermat|ricevut"
        r"|accettat)[oa]",
        r"rimborso (?:e stato )?(?:effettuato|emesso|elaborato|approvato|confermato)",
        r"(?:e|sono) stat[oaie] rimborsat[oaie]",
        r"(?:restituit|rispedit)[oaie] al mittente",
        r"retour(?:zending)? (?:is )?(?:ontvangen|bevestigd|geregistreerd|verwerkt)",
        r"terugbetaling (?:is )?(?:verwerkt|uitgevoerd|gedaan|voltooid)",
        r"(?:is|zijn|wordt|werd) terugbetaald",
        r"retour afzender",
        r"terug naar (?:de )?afzender",
        r"(?:is|zijn) geretourneerd",
    ),
    MailKind.CUSTOMS: (
        r"(?:held|waiting|awaiting|stopped|detained|retained|being held)"
        r" (?:at|in|by) customs",
        r"(?:is|are) (?:currently )?(?:in|at|with) customs",
        r"customs clearance (?:is )?(?:required|pending|in progress)",
        r"(?:awaiting|pending) customs (?:clearance|payment|charges)",
        r"retid[oa]s? na alfandega",
        r"(?:esta|encontra-se|encontra se) na alfandega",
        r"(?:aguarda|pendente de) desalfandegamento",
        r"desalfandegamento (?:pendente|em curso)",
        r"retenid[oa]s? en (?:la )?aduana",
        r"(?:esta|se encuentra) en (?:la )?aduana",
        r"despacho de aduanas? (?:pendiente|en curso)",
        r"en tramite aduanero",
        r"(?:liegt|ist|befindet sich|wird) (?:derzeit |aktuell |noch )?(?:beim|im) zoll",
        r"(?:vom|durch den|beim) zoll (?:aufgehalten|zuruckgehalten|gepruft|einbehalten)",
        r"zollabfertigung (?:erforderlich|ausstehend|lauft)",
        r"(?:bloquee?|retenue?|en attente) (?:en|a la|par la) douane",
        r"(?:est|se trouve) (?:actuellement )?en douane",
        r"dedouanement (?:en cours|requis|en attente)",
        r"(?:fermo|ferma|bloccat[oa]|trattenut[oa]) in dogana",
        r"(?:e|si trova) (?:attualmente )?in dogana",
        r"sdoganamento (?:in corso|richiesto|in attesa)",
        r"(?:vastgehouden|tegengehouden) (?:door|bij) de douane",
        r"(?:is|ligt) bij de douane",
        r"inklaring (?:vereist|in behandeling)",
        # Import charges to pay before delivery. Each phrase starts at its
        # verb or noun, so "may need to pay" and "wenn ... fällig" stay guarded.
        r"(?:a |the )?(?:fee|charges?|payment) (?:is |are )?(?:now )?(?:due|outstanding"
        r"|required) (?:on|for) (?:your|this|the) (?:item|parcel|package|shipment)",
        r"(?:import|customs) (?:vat|duty|duties|charges?|fees?|taxes|tax)"
        r" (?:is |are )?(?:now )?(?:due|payable|outstanding|unpaid)",
        r"(?:need|needs|have|has|must|required) to pay (?:the |a |an |your |any )?"
        r"(?:import|customs) (?:vat|duty|duties|charges?|fees?|taxes|tax)",
        r"(?:e necessario|tem de|tem que|precisa de|deve) pagar (?:o )?iva",
        r"(?:e necessario|tem de|tem que|precisa de|deve) pagar (?:os |as |o |a )?"
        r"(?:impostos?|taxas?|direitos|despesas) (?:de importacao|aduaneir[oa]s"
        r"|alfandegari[oa]s|de desalfandegamento)",
        r"(?:iva de importacao|(?:impostos?|taxas?|direitos|despesas) (?:de importacao"
        r"|aduaneir[oa]s|alfandegari[oa]s|de desalfandegamento))"
        r" (?:a pagar|por pagar|em divida|pendentes?)",
        r"(?:aguarda|a aguardar|pendente de) (?:o )?pagamento (?:de |do |dos |da |das )?"
        r"(?:iva|impostos?|taxas?|direitos|despesas)",
        r"(?:debe|debes|tiene que|tienes que|es necesario|necesitas|necesita)"
        r" (?:pagar|abonar) (?:el |los |la |las )?(?:iva|aranceles|(?:impuestos?"
        r"|derechos|tasas|gastos) (?:de importacion|aduaner[oa]s|de aduanas?))",
        r"(?:iva de importacion|aranceles|(?:impuestos?|derechos|tasas|gastos)"
        r" (?:de importacion|aduaner[oa]s|de aduanas?))"
        r" (?:pendientes? de pago|a pagar|por pagar)",
        r"pendiente del? pago de (?:los |las |el |la )?(?:iva|impuestos?|aranceles"
        r"|derechos|tasas|gastos)",
        r"(?:zollgebuhren|einfuhrabgaben|einfuhrumsatzsteuer|zollabgaben|importgebuhren)"
        r" (?:sind |ist )?(?:noch )?(?:offen|fallig|zu (?:be)?zahlen|ausstehend)",
        r"(?:bezahlen|zahlen|begleichen|entrichten) sie (?:bitte )?(?:die |den )?"
        r"(?:zollgebuhren|einfuhrabgaben|einfuhrumsatzsteuer|zollabgaben|importgebuhren)",
        r"(?:droits|frais|taxes|tva) (?:de douane|d'importation|douaniers"
        r"|a l'importation) (?:sont |est )?(?:a payer|a regler|dus|impayes"
        r"|en attente de paiement)",
        r"(?:devez|merci de|veuillez) (?:payer|regler|acquitter) (?:les |la |des )?"
        r"(?:droits|frais|taxes|tva) (?:de douane|d'importation|douaniers"
        r"|a l'importation)",
        r"en attente (?:de |du )?paiement (?:des |de la |du )?(?:droits|frais|taxes|tva)",
        r"(?:devi|deve|e necessario|occorre) pagare (?:i |gli |le |l'|la )?"
        r"(?:dazi(?: doganali)?|(?:oneri|tasse|diritti) (?:doganali|di importazione)"
        r"|iva (?:all'importazione|di importazione))",
        r"(?:dazi(?: doganali)?|(?:oneri|tasse|diritti) (?:doganali|di importazione))"
        r" (?:da pagare|in sospeso|non pagati)",
        r"in attesa (?:del )?pagamento (?:dei |degli |delle |del |della )?"
        r"(?:dazi|oneri|tasse|diritti|iva)",
        r"(?:betaal|betalen|voldoe|voldoen) (?:de |je |uw )?(?:invoerkosten"
        r"|invoerrechten|inklaringskosten|douanekosten|importkosten)",
        r"(?:invoerkosten|invoerrechten|inklaringskosten|douanekosten|importkosten)"
        r" (?:moeten |moet )?(?:nog )?(?:worden )?(?:betaald|te betalen|betalen"
        r"|openstaand|verschuldigd)",
    ),
    MailKind.READY_FOR_PICKUP: (
        r"ready (?:for|to be) (?:pick ?-?up|picked up|collect(?:ed|ion))",
        r"ready to (?:pick ?-?up|collect)",
        r"available (?:for|to) (?:pick ?-?up|collect(?:ion)?)",
        r"awaiting (?:your )?collection",
        r"(?:can|may) (?:now )?be (?:collected|picked up)",
        r"(?:is|has arrived|arrived|is waiting|waiting for you) (?:at|in)"
        r" (?:the |your |a )?(?:selected )?(?:pick ?-?up (?:point|location)"
        r"|parcel ?shop|parcel locker|locker|collection point|access point|post office)",
        r"disponivel para (?:levantamento|recolha)",
        r"pront[ao] (?:para|a) (?:levantamento|levantar|recolha|ser levantad[ao])",
        r"aguarda (?:o seu |o teu )?levantamento",
        r"(?:ja )?(?:pode|podes) (?:levantar|recolher) (?:a sua |o seu |a tua |o teu )?"
        r"(?:encomenda|objeto|objecto|pedido|envio)",
        r"(?:pode|podera) ser levantad[ao]",
        r"(?:esta|encontra-se|chegou) (?:disponivel )?(?:no|ao|na|a) (?:cacifo"
        r"|ponto de recolha|ponto pickup|ponto de levantamento|loja ctt|estacao)",
        r"disponivel (?:no|na|em) (?:cacifo|loja|ponto)",
        r"list[oa] para (?:recoger|su recogida|la recogida)",
        r"disponible para (?:recoger|su recogida|la recogida|recogida)",
        r"(?:ya )?(?:puedes|puede) recoger (?:tu|su) (?:pedido|paquete|envio)",
        r"(?:esta|se encuentra|ha llegado) (?:disponible )?(?:en|a) (?:el |la )?"
        r"(?:punto de recogida|punto pack|locker|oficina|tienda|parcel ?shop"
        r"|punto de conveniencia)",
        r"te espera en",
        r"abholbereit",
        r"bereit zur abholung",
        r"zur abholung bereit(?:gestellt)?",
        r"liegt (?:zur abholung|fur (?:sie|dich)) (?:bereit|in|an)",
        r"kann (?:[a-z]+ ){0,3}?abgeholt werden",
        r"(?:ist|liegt) (?:in|an) (?:der|ihrer|deiner|einer) (?:packstation|filiale"
        r"|paketshop|postfiliale|paketstation)",
        r"(?:in|an) (?:die|der|ihre|deine|eine|einer) (?:packstation|paketstation"
        r"|filiale|postfiliale|paketshop|paketbox) (?:eingelegt|gebracht|geliefert)",
        r"disponible (?:en|au|dans (?:votre|le|la|un|une)) (?:point relais|relais"
        r"|point de retrait|bureau de poste|consigne|casier|locker|point pickup)",
        r"pret a etre retire",
        r"pret pour (?:le )?retrait",
        r"disponible (?:au|pour le) retrait",
        r"vous attend (?:en|au|dans|chez)",
        r"pront[oa] per (?:il )?ritiro",
        r"pront[oa] (?:al|da) ritir(?:o|are)",
        r"disponibile per (?:il )?ritiro",
        r"disponibile (?:presso|nel|nella|al) (?:punto di ritiro|locker|punto poste"
        r"|ufficio postale|fermopoint)",
        r"(?:puoi|puo) ritirare (?:il tuo|il suo|la tua|la sua) (?:pacco|ordine|spedizione)",
        r"in giacenza",
        r"ligt (?:voor (?:je|u) )?klaar (?:bij|in|op|om)",
        r"klaar (?:om op te halen|voor ophalen|om te worden opgehaald)",
        r"kan (?:worden )?opgehaald(?: worden)?",
        r"(?:kun je|kunt u) (?:je|jouw|uw) (?:pakket|zending|bestelling) ophalen",
        r"(?:ligt|is) (?:bij|in) (?:het|de) (?:afhaalpunt|ophaalpunt|pakketpunt"
        r"|pakketautomaat|servicepunt)",
    ),
    MailKind.ATTEMPTED: (
        r"delivery attempt",
        r"attempted (?:delivery|to deliver)",
        r"(?:we )?tried to deliver",
        r"(?:were|was) unable to deliver",
        r"could ?(?:not|n't) (?:be )?deliver(?:ed)?",
        r"missed delivery",
        r"delivery (?:was )?(?:unsuccessful|failed)",
        r"failed delivery",
        r"we missed you",
        r"tentativa de entrega",
        r"tentamos entregar",
        r"nao (?:foi possivel|conseguimos|pudemos) (?:fazer a |efetuar a |efectuar a )?"
        r"entrega(?:r)?",
        r"entrega (?:falhada|sem sucesso|nao (?:efetuada|efectuada|conseguida|realizada))",
        r"destinatario ausente",
        r"intento de entrega",
        r"intentamos entregar",
        r"no (?:hemos podido|se ha podido|pudimos|fue posible) (?:realizar la )?"
        r"entrega(?:r)?",
        r"entrega (?:fallida|no realizada|sin exito)",
        r"zustellversuch",
        r"zustellung (?:war )?(?:nicht moglich|fehlgeschlagen|gescheitert)",
        r"(?:konnte|konnten|wurde|wurden) (?:leider )?nicht zugestellt",
        r"(?:konnte|konnten) (?:ihr|dein|ihre|deine) (?:paket|sendung|bestellung)"
        r" (?:leider )?nicht (?:zustellen|liefern)",
        r"nicht angetroffen",
        r"benachrichtigungskarte",
        r"tentative de livraison",
        r"n'(?:a|ont) pas pu etre livree?s?",
        r"n'avons pas pu (?:vous )?livrer",
        r"avis de passage",
        r"echec (?:de (?:la )?)?livraison",
        r"livraison (?:echouee|manquee|impossible)",
        r"tentativo di consegna",
        r"mancata consegna",
        r"(?:non e stato possibile|non siamo riusciti a) consegnare",
        r"consegna (?:non riuscita|fallita|non effettuata)",
        r"destinatario assente",
        r"bezorgpoging",
        r"(?:kon|konden) niet (?:worden )?(?:bezorgd|afgeleverd)",
        r"(?:kon|konden) (?:je|jouw|uw) (?:pakket|zending|bestelling) niet"
        r" (?:bezorgen|afleveren)",
        r"we hebben (?:je|u) gemist",
        r"mislukte bezorging",
        r"bezorging (?:is )?mislukt",
    ),
    MailKind.DELIVERED: (
        r"(?:has|have) (?:now )?been (?:successfully )?delivered",
        r"(?:was|were) (?:successfully )?delivered",
        r"(?:successfully|safely) delivered",
        r"delivered (?:successfully|safely)",
        r"delivery (?:completed|complete|successful)",
        r"we(?:'ve| have) delivered",
        r"(?:foi|foram) entregues?",
        r"entregues? com sucesso",
        r"entrega (?:efetuada|efectuada|realizada|concluida)",
        r"(?:ha|han) sido entregad[oa]s?",
        r"(?:fue|fueron) entregad[oa]s?",
        r"entregad[oa]s? con exito",
        r"se (?:ha|han) entregado",
        r"entrega (?:completada|efectuada|realizada)",
        r"(?:wurde|wurden|ist|sind) (?:heute |gestern |erfolgreich |soeben |bereits )*"
        r"(?:zugestellt|ausgeliefert|geliefert)",
        r"erfolgreich zugestellt",
        r"zustellung erfolgreich",
        r"(?:a|ont) ete livree?s?",
        r"livree?s? avec succes",
        r"livraison (?:effectuee|reussie|realisee)",
        r"(?:e|sono) stat[oaie] consegnat[oaie]",
        r"consegnat[oaie] con successo",
        r"consegna (?:effettuata|avvenuta|completata|riuscita)",
        r"(?:is|zijn|werd|werden) (?:vandaag |zojuist |succesvol |net )*"
        r"(?:bezorgd|afgeleverd)",
        r"succesvol (?:bezorgd|afgeleverd)",
        r"bezorging (?:geslaagd|gelukt|voltooid)",
    ),
    MailKind.OUT_FOR_DELIVERY: (
        r"(?:is|are|was|now|currently) out for delivery",
        r"(?:has|have) gone out for delivery",
        r"(?:is|are) (?:with|on) (?:the|our|your) (?:courier|driver|delivery van|van)",
        r"(?:will be|being) delivered today",
        r"(?:arriving|arrives|will arrive|coming) today",
        r"driver is on (?:the|their|his|her) way",
        r"(?:esta|encontra-se|seguiu|saiu|segue) (?:hoje )?(?:em|para)"
        r" (?:distribuicao|entrega)",
        r"saiu para (?:entrega|distribuicao)",
        r"(?:esta|estao) a ser entregues?",
        r"(?:sera|vai ser) entregue hoje",
        r"(?:chega|chegara|vai chegar) hoje",
        r"(?:esta|segue|encontra-se) com o (?:estafeta|motorista|carteiro)",
        r"(?:esta|se encuentra|ya esta) en reparto",
        r"(?:ha )?salido (?:a|para) (?:reparto|entrega)",
        r"(?:esta|se encuentra) en (?:ruta|proceso) de entrega",
        r"(?:sera|va a ser) entregad[oa] hoy",
        r"(?:llega|llegara|va a llegar) hoy",
        r"(?:esta|se encuentra) en distribucion",
        r"(?:ist|befindet sich) (?:jetzt |heute )?in (?:der )?zustellung",
        r"(?:wird|werden) (?:heute |voraussichtlich heute )+(?:zugestellt|geliefert)",
        r"(?:kommt|kommen) heute",
        r"(?:ist|befindet sich) (?:im|auf dem) zustellfahrzeug",
        r"(?:zusteller|zustellerin|fahrer|fahrerin) ist (?:auf dem weg|unterwegs)",
        r"(?:est|sont) (?:actuellement )?en cours de livraison",
        r"(?:est|sont) en livraison",
        r"(?:sera|seront) livree?s? aujourd'hui",
        r"(?:arrive|arrivera) aujourd'hui",
        r"(?:est|sont) en cours de distribution",
        r"(?:e|sono) in (?:consegna|distribuzione)",
        r"(?:sara|verra) consegnat[oa] oggi",
        r"(?:arriva|arrivera) oggi",
        r"consegna prevista (?:per )?oggi",
        r"(?:wordt|worden) vandaag (?:bezorgd|geleverd|afgeleverd)",
        r"(?:de )?bezorger is onderweg",
        r"(?:komt|komen) vandaag",
        r"(?:is|zijn) in bezorging",
        r"wordt nu bezorgd",
    ),
    MailKind.DELAYED: (
        r"(?:has|have) been delayed",
        r"(?:is|are|was|were) (?:now |currently |unfortunately )?delayed",
        r"(?:is|are) running late",
        r"(?:delivery|shipping|shipment) delay",
        r"delayed (?:delivery|shipment)",
        r"later than (?:expected|planned|originally (?:expected|planned))",
        r"new (?:estimated )?delivery date",
        r"delivery (?:has been )?(?:rescheduled|postponed)",
        r"(?:esta|encontra-se|foi) atrasad[ao]",
        r"sofreu (?:um )?atraso",
        r"atraso n[ao] (?:entrega|envio|sua encomenda|seu pedido)",
        r"nova data (?:prevista )?de entrega",
        r"entrega (?:foi )?reagendada",
        r"mais tarde do que (?:o )?previsto",
        r"(?:esta|ha sido|se ha) retrasad[oa]",
        r"(?:sufre|tiene) (?:un )?retraso",
        r"retraso en (?:la entrega|el envio|tu pedido|su pedido)",
        r"nueva fecha (?:estimada )?de entrega",
        r"entrega (?:ha sido )?reprogramada",
        r"mas tarde de lo previsto",
        r"(?:ist|wurde|hat sich) (?:leider )?verzogert",
        r"verzogerung (?:bei|der|ihrer|deiner) (?:zustellung|lieferung|sendung|bestellung)",
        r"(?:liefer|zustell)verzogerung",
        r"(?:ist|wird) (?:leider )?verspatet",
        r"neuer (?:liefertermin|zustelltermin)",
        r"spater als (?:erwartet|geplant|angekundigt)",
        r"(?:est|a ete) (?:legerement )?retardee?",
        r"retard (?:de|dans la) livraison",
        r"(?:a|prend|accuse) du retard",
        r"nouvelle date de livraison",
        r"livraison (?:reportee|reprogrammee)",
        r"plus tard que prevu",
        r"(?:e|risulta) in ritardo",
        r"ritardo (?:nella|della) (?:consegna|spedizione)",
        r"(?:ha subito|subisce) (?:un )?ritardo",
        r"nuova data (?:prevista )?di consegna",
        r"consegna (?:posticipata|rinviata|riprogrammata)",
        r"piu tardi del previsto",
        r"(?:is|zijn|wordt) vertraagd",
        r"vertraging (?:bij|in|van) (?:de |je |uw )?(?:bezorging|levering|zending"
        r"|bestelling)",
        r"(?:heeft|loopt) vertraging",
        r"nieuwe (?:bezorgdatum|leverdatum)",
        r"later dan (?:verwacht|gepland)",
        r"bezorging (?:is )?uitgesteld",
    ),
    MailKind.IN_TRANSIT: (
        r"(?:is|are) (?:now |currently |still )?in transit",
        r"(?:has |have )?arrived at (?:the |our |a )?(?:sorting|distribution|delivery"
        r"|local|regional) (?:centre|center|facility|hub|depot|office)",
        _EN_LEFT + r" (?:the |our |a |an |its |their )?" + _EN_PLACE_WORDS + _EN_PLACES,
        r"departed(?: from)? (?:the |a |an )?"
        + _EN_PLACE_WORDS
        + r"(?:facility|location)",
        _EN_LEFT + r" (?:the |its |their )?(?:country of (?:origin|departure|export"
        r"|dispatch)|(?:origin|export|departure|sending) country)",
        r"(?:has )?cleared customs",
        r"customs (?:clearance )?(?:cleared|completed|complete|done)",
        r"(?:esta|encontra-se|segue) em transito",
        r"(?:chegou|deu entrada) (?:ao|no|na) (?:centro|armazem)",
        r"(?:(?:saiu|partiu|saida|partida) (?:do|da|dos|das)|deixou (?:o|a|os|as))"
        r" (?:nosso |nossa |seu |sua )?" + _PT_PLACES,
        r"desalfandegad[ao]",
        r"desalfandegamento (?:concluido|efetuado|efectuado|realizado)",
        r"(?:esta|se encuentra|sigue) en transito",
        r"(?:ha )?llegado (?:al|a la) (?:centro|delegacion|almacen|plataforma)",
        r"(?:(?:ha |han )?(?:salido|partido)|salio|salieron|partio|partieron|salida)"
        r" (?:del|de (?:la|los|las|nuestro|nuestra|su)) " + _ES_PLACES,
        r"(?:despachad[oa]|liberad[oa]) (?:de|por|en) (?:la )?aduana",
        r"(?:im|ins) (?:start-?|ziel-?)?paketzentrum",
        r"(?:im|ins) (?:verteil|sortier)zentrum",
        r"(?:hat|haben) (?:(?:heute|soeben|gerade|bereits|jetzt|nun) )?(?:das|den|die"
        r"|unser|unseren|unsere) " + _DE_PLACES + r"(?: in [a-z\-]+)? verlassen",
        r"verliess(?:en)? (?:das|den|die|unser|unseren|unsere) " + _DE_PLACES,
        r"zollabfertigung abgeschlossen",
        r"verzollt",
        r"(?:est|sont) (?:actuellement )?en transit",
        r"(?:est|sont) en cours d'acheminement",
        r"(?:a|ont) quitte (?:le |la |l'|les |son |sa |notre |nos |leur )?"
        + _FR_PLACES,
        r"(?:(?:est|sont) (?:parti|sorti)e?s?|depart|sortie) (?:du |de la |de l'|des "
        r"|de (?:notre|nos|son|sa|leur) )" + _FR_PLACES,
        r"dedouanee?s?",
        r"dedouanement (?:termine|effectue)",
        r"(?:e|sono) in transito",
        r"(?:(?:e|sono) (?:partit|uscit)[oaie]|partenza|uscita) (?:dal|dall'|dallo"
        r"|dalla|dai|dagli|dalle) ?" + _IT_PLACES,
        r"(?:ha|hanno) lasciato (?:il|lo|la|l'|i|gli|le) ?(?:nostro |nostra )?"
        + _IT_PLACES,
        r"sdoganat[oaie]",
        r"(?:is |wordt |werd )?gesorteerd",
        r"(?:in|bij) (?:het|ons) (?:sorteercentrum|distributiecentrum)",
        r"(?:heeft|hebben) (?:(?:vandaag|zojuist|net|nu) )?(?:het|de|ons|onze) "
        + _NL_PLACES
        + r"(?: in [a-z\-]+)? verlaten",
        r"(?:(?:is |zijn )?vertrokken|vertrek) (?:uit|van|vanuit|vanaf) (?:het|de|ons"
        r"|onze) " + _NL_PLACES,
        r"verliet(?:en)? (?:het|de|ons|onze) " + _NL_PLACES,
        r"ingeklaard",
    ),
    MailKind.SHIPPED: (
        r"(?:has|have) (?:now )?(?:been )?shipped",
        r"(?:was|were|is|are) (?:now )?shipped",
        r"(?:has|have) (?:now )?(?:been )?dispatched",
        r"(?:was|were|is|are) (?:now )?dispatched",
        r"(?:order|package|parcel|item|items|shipment)s? (?:has|have) been"
        r" (?:sent|posted)",
        r"(?:shipping|shipment|dispatch) (?:confirmation|notification|notice)",
        *ON_THE_WAY_PHRASES,
        r"(?:order|package|parcel|shipment)s? (?:has|have) left",
        r"handed (?:over )?to (?:the )?(?:carrier|courier)",
        r"we(?:'ve| have) (?:just )?(?:shipped|sent|dispatched|posted) your",
        r"(?:foi|foram) (?:enviad|expedid|despachad)[ao]s?",
        r"(?:enviamos|expedimos|despachamos) (?:a sua|o seu|a tua|o teu)",
        r"confirmacao de (?:envio|expedicao)",
        r"entregue (?:a|ao) (?:transportadora|transportador|estafeta)",
        r"saiu (?:do|dos) (?:nosso|nossos) armaz(?:em|ens)",
        r"(?:ha|han) sido (?:enviad|expedid|despachad)[oa]s?",
        r"(?:fue|fueron) (?:enviad|expedid)[oa]s?",
        r"(?:hemos enviado|enviamos) (?:tu|su)",
        r"confirmacion de envio",
        r"entregad[oa] al transportista",
        r"(?:ha|han) salido de (?:nuestro|nuestros) (?:almacen|almacenes)",
        r"(?:ha|han) salido de nuestras instalaciones",
        r"(?:wurde|wurden|ist|sind) (?:heute |soeben |bereits |jetzt )*(?:versendet"
        r"|verschickt|versandt|abgeschickt)",
        r"versandbestatigung",
        r"versandbenachrichtigung",
        r"(?:hat|haben) (?:unser|das) lager verlassen",
        r"an (?:den |unseren )?(?:versanddienstleister|versandpartner|paketdienst"
        r"|logistikpartner|dhl|hermes|dpd|gls|ups|fedex|tnt|deutsche post"
        r"|go express) ubergeben",
        r"(?:a|ont) ete (?:expediee?s?|envoyee?s?)",
        r"(?:confirmation|avis) d'expedition",
        r"(?:a|ont) quitte (?:notre|nos) entrepots?",
        r"remise? (?:au|a votre) (?:transporteur|livreur)",
        r"(?:e|sono) stat[oaie] (?:spedit|inviat)[oaie]",
        r"(?:spedizion[ei]|pacc(?:o|hi)|ordin[ei]|coll[oi])(?: n\.? ?[a-z0-9-]+)?"
        r" (?:e|sono) partit[oaie]",
        r"abbiamo spedito",
        r"conferma di spedizione",
        r"(?:affidat|consegnat)[oaie] al corriere",
        r"(?:ha|hanno) lasciato il (?:nostro )?magazzino",
        r"(?:is|zijn|werd|werden) (?:vandaag |zojuist )*(?:verzonden|verstuurd)",
        r"verzendbevestiging",
        r"(?:we|wij) hebben (?:je|jouw|uw) (?:bestelling|pakket) (?:verzonden|verstuurd)",
        r"(?:overgedragen|meegegeven) aan (?:de )?(?:vervoerder|bezorger|postnl|dhl"
        r"|dpd|gls|ups)",
        r"(?:heeft|hebben) (?:ons|het) magazijn verlaten",
    ),
    MailKind.ORDER: (
        r"order confirmation",
        r"order (?:is |has been )?confirmed",
        r"(?:thank you|thanks) for (?:your|the) (?:order|purchase)",
        r"we(?:'ve| have)? received your order",
        r"(?:your )?order (?:has been |was )?(?:placed|received)",
        r"purchase confirmation",
        r"confirmacao (?:da|de|do) (?:sua |seu |tua |teu )?(?:encomenda|pedido|compra)",
        r"(?:encomenda|pedido|compra) (?:foi )?(?:confirmad|recebid|registad"
        r"|registrad)[ao]",
        r"obrigad[oa] pel[ao] (?:sua |seu |tua |teu )?(?:encomenda|pedido|compra)",
        r"recebemos (?:a sua|o seu|a tua|o teu) (?:encomenda|pedido)",
        r"confirmacion (?:de|del) (?:tu |su )?(?:pedido|compra)",
        r"pedido (?:ha sido )?(?:confirmado|recibido|realizado|registrado)",
        r"compra confirmada",
        r"gracias por (?:tu|su) (?:pedido|compra)",
        r"(?:hemos recibido|recibimos) (?:tu|su) pedido",
        r"(?:bestell|auftrags)bestatigung",
        r"bestelleingang",
        r"bestellung (?:ist |wurde )?(?:eingegangen|bestatigt|aufgenommen|erhalten)",
        r"(?:vielen )?dank fur (?:ihre|deine) bestellung",
        r"confirmation de (?:votre |ta )?commande",
        r"commande (?:a ete )?(?:confirmee|recue|enregistree|validee)",
        r"merci (?:pour|de) (?:votre|ta) (?:commande|achat)",
        r"(?:nous )?avons (?:bien )?recu (?:votre|ta) commande",
        r"recapitulatif de (?:votre |ta )?commande",
        r"conferma (?:dell'|del |di |d')?(?:ordine|acquisto)",
        r"ordine (?:e stato )?(?:confermato|ricevuto|registrato)",
        r"grazie per (?:il tuo |il suo |l')?(?:ordine|acquisto)",
        r"abbiamo ricevuto il tuo ordine",
        r"riepilogo (?:dell'|del )?ordine",
        r"(?:order|bestel)bevestiging",
        r"bevestiging van (?:je|jouw|uw) (?:bestelling|order|aankoop)",
        r"bedankt voor (?:je|jouw|uw) (?:bestelling|order|aankoop)",
        r"(?:we|wij) hebben (?:je|jouw|uw) (?:bestelling|order) ontvangen",
        r"bestelling (?:is )?(?:ontvangen|bevestigd|geplaatst)",
    ),
}

# Shorter keywords, trusted only in the subject: in a body they also appear
# in footers, progress bars and adverts.
SUBJECT_KEYWORDS: dict[MailKind, tuple[str, ...]] = {
    MailKind.CANCELLED: (
        r"cancell?ed",
        r"cancell?ation",
        r"cancelad[oa]s?",
        r"cancelamento",
        r"anulad[oa]s?",
        r"cancelacion",
        r"anulacion",
        r"storniert",
        r"stornierung",
        r"storno",
        r"annulee?s?",
        r"annulation",
        r"(?:annullat|cancellat)[oaie]",
        r"annullamento",
        r"geannuleerd",
        r"annulering",
    ),
    MailKind.RETURN: (
        r"(?:your|the|a) return",
        r"return (?:label|request|confirmation|confirmed|received|started|initiated"
        r"|approved|authori[sz]ation|update|processed|registered)",
        r"(?:your|the|a) refund",
        r"refund (?:issued|processed|confirmation|confirmed|approved|initiated"
        r"|completed|request)",
        r"refunded",
        r"returned",
        r"devolucao",
        r"devolvid[oa]s?",
        r"reembolso",
        r"reembolsad[oa]s?",
        r"devolucion",
        r"devuelt[oa]s?",
        r"rucksendung",
        r"retoure",
        r"(?:ruck)?erstattung",
        r"(?:zuruck)?erstattet",
        r"(?:votre|ton) retour",
        r"retour (?:enregistre|confirme|recu|accepte|valide)",
        r"remboursement",
        r"remboursee?s?",
        r"(?:il tuo|il suo|tuo|suo) reso",
        r"reso (?:confermato|ricevuto|registrato|autorizzato|approvato|accettato)",
        r"rimborso",
        r"rimborsat[oaie]",
        r"restituzione",
        r"(?:je|jouw|uw) retour",
        r"retour(?:zending|bevestiging|aanmelding)",
        r"retour (?:ontvangen|bevestigd|aangemeld|verwerkt)",
        r"terugbetaling",
        r"terugbetaald",
        r"geretourneerd",
    ),
    MailKind.CUSTOMS: (
        r"customs",
        r"alfandega",
        r"desalfandegamento",
        r"aduanas?",
        r"aduaner[oa]s?",
        # Not "27 Zoll" (inches).
        r"(?<![0-9])(?<![0-9]\s)zoll(?:abfertigung|gebuhren|anmeldung|kontrolle|amt)?",
        r"einfuhrabgaben",
        r"douane",
        r"dedouanement",
        r"dogana",
        r"doganal[ei]",
        r"sdoganamento",
        r"dazi",
        r"inklaring",
        r"invoerrechten",
        r"aduaneir[oa]s?",
        r"alfandegari[oa]s?",
        r"import (?:vat|duty|duties|charges?|fees?|taxes)",
        r"iva de importa(?:cao|cion)",
        r"iva all'importazione",
        r"aranceles",
        r"einfuhrumsatzsteuer",
        r"tva a l'importation",
        r"(?:frais|droits|taxes) d'importation",
        r"invoerkosten",
        r"inklaringskosten",
        r"douanekosten",
    ),
    MailKind.READY_FOR_PICKUP: (
        r"pick ?-?up (?:code|reminder|notice|notification|available)",
        r"collection (?:code|reminder|notice)",
        r"awaiting collection",
        r"para (?:levantamento|levantar|recolha)",
        r"pront[ao] a levantar",
        r"para recoger",
        r"codigo de recogida",
        r"abholbereit",
        r"abholcode",
        r"zur abholung",
        r"a retirer",
        r"code de retrait",
        r"da ritirare",
        r"codice di ritiro",
        r"afhalen",
        r"ophalen",
        r"(?:afhaal|ophaal)code",
    ),
    MailKind.ATTEMPTED: (
        r"missed (?:delivery|you|your delivery)",
        r"not delivered",
        r"delivery (?:attempt|failed|unsuccessful)",
        r"nao entregue",
        r"(?:entrega )?falhada",
        r"no entregad[oa]",
        r"ausente",
        r"nicht zugestellt",
        r"zustellung (?:nicht moglich|fehlgeschlagen)",
        r"pas (?:pu etre )?livree?s?",
        r"non consegnat[oaie]",
        r"niet (?:bezorgd|afgeleverd)",
        r"gemist",
    ),
    MailKind.DELIVERED: (
        r"delivered(?! (?:tomorrow|within|in \d|next|free|fast(?:er)?))",
        r"entregues?(?! (?:em \d|amanha|gratis|gratuitamente|no prazo|ate))",
        r"entregad[oa]s?(?! (?:en \d|manana|gratis|gratuitamente|hasta))",
        r"zugestellt",
        r"ausgeliefert",
        r"livree?s?(?= ?[:!])",
        r"(?:est|sont) livree?s?",
        r"(?:colis|commande|envoi|paquet)s? (?:a ete |est )?livree?s?",
        r"consegnat[oaie](?= ?[:!])",
        r"(?:e|sono) consegnat[oaie]",
        r"(?:pacco|pacchi|ordine|ordini|spedizione|spedizioni)"
        r" (?:e stat[oa] |sono stat[ie] )?consegnat[oaie]",
        r"(?:bezorgd|afgeleverd)(?= ?[:!])",
        r"(?:pakket|pakketje|bestelling|zending)(?:en)? (?:bezorgd|afgeleverd)",
    ),
    MailKind.OUT_FOR_DELIVERY: (
        r"out for delivery",
        r"(?:arriving|arrives|delivery|coming) today",
        r"em (?:distribuicao|entrega)",
        r"saiu para (?:entrega|distribuicao)",
        r"(?:chega|entrega) hoje",
        r"en reparto",
        r"(?:llega|entrega) hoy",
        r"in zustellung",
        r"(?:kommt|lieferung|zustellung) heute",
        r"en (?:cours de )?livraison",
        r"(?:arrive|livraison) aujourd'hui",
        # Not "presa in consegna" (taken over by the carrier).
        r"(?<!presa\s)(?<!preso\s)in (?:consegna|distribuzione)",
        r"(?:arriva|consegna) oggi",
        r"in bezorging",
        r"(?:komt|bezorging) vandaag",
    ),
    MailKind.DELAYED: (
        r"delay(?:ed)?",
        r"running late",
        r"atrasad[ao]s?",
        r"atraso",
        r"retrasad[oa]s?",
        r"retraso",
        r"verzogerung",
        r"verzogert",
        r"verspatet",
        r"verspatung",
        r"retard",
        r"retardee?s?",
        r"ritardo",
        r"vertraging",
        r"vertraagd",
    ),
    MailKind.IN_TRANSIT: (
        r"(?:in|em|en) transito?",
        r"em transporte",
        r"(?:im|ins) paketzentrum",
        r"en cours d'acheminement",
    ),
    MailKind.SHIPPED: (
        r"shipped",
        r"dispatched",
        *ON_THE_WAY_KEYWORDS,
        # Not "shipment update": carriers send it at every step.
        r"(?:shipping|shipment|dispatch) (?:confirmation|notification)",
        r"enviad[oa]s?",
        r"expedid[oa]s?",
        r"despachad[oa]s?",
        r"versendet",
        r"verschickt",
        r"versandt",
        r"versand(?:bestatigung|benachrichtigung|info)",
        r"expediee?s?",
        r"envoyee?s?",
        r"spedit[oaie]",
        r"inviat[oaie]",
        r"verzonden",
        r"verstuurd",
    ),
    MailKind.ORDER: (
        r"(?:order|pedido|encomenda|bestellung|commande|ordine|bestelling)"
        r" (?:(?:n\.? ?o|nr|no|num)\.? ?)?#? ?[a-z0-9-]*\d[a-z0-9-]*"
        r" (?:(?:is|has been|was|foi|ha sido|wurde|a ete|e stat[oa]) )?"
        r"(?:confirmed|received|placed|confirmad[ao]|recebid[ao]|registad[ao]"
        r"|recibid[oa]|bestatigt|eingegangen|confirmee|recue|enregistree"
        r"|confermat[oa]|ricevut[oa]|bevestigd|ontvangen|geplaatst)",
    ),
}

# A keyword right after one of these words describes something that may
# happen ("will be delivered", "não foi entregue", "kann abgeholt werden").
GUARD_WORDS: frozenset[str] = frozenset(
    {
        # English
        *("will", "would", "shall", "be", "not", "never", "yet", "may", "might"),
        *("could", "should", "ll", "won", "cannot", "couldn", "wasn", "hasn"),
        *("haven", "isn", "aren", "didn", "don", "doesn", "weren", "wouldn"),
        # Portuguese
        *("sera", "serao", "ser", "vai", "vao", "nao", "nunca", "ainda", "pode"),
        *("podem", "podera", "poderao", "possa"),
        # Spanish
        *("seran", "todavia", "aun", "puede", "pueden", "podra", "podria", "pueda"),
        *("va",),
        # German
        *("wird", "werden", "nicht", "kein", "keine", "keinen", "nie", "niemals"),
        *("kann", "konnen", "durfte", "sollte", "soll"),
        # French
        *("seront", "pas", "jamais", "encore", "peut", "peuvent", "pourra"),
        *("pourrait", "etre"),
        # Italian
        *("sara", "saranno", "verra", "verranno", "non", "mai", "ancora", "puo"),
        *("possono", "potrebbe", "potra", "essere", "deve"),
        # Dutch
        *("wordt", "worden", "niet", "geen", "nooit", "kan", "kunnen", "zou"),
        *("zal", "zullen"),
    }
)
# A keyword shortly after one of these words is a condition ("once your
# parcel has been delivered", "sobald die Sendung zugestellt wurde").
CONDITIONAL_WORDS: frozenset[str] = frozenset(
    {
        *("once", "when", "whenever", "after", "if", "unless", "until", "soon"),
        *("case", "whether"),
        *("quando", "assim", "depois", "apos", "caso"),
        *("cuando", "vez", "despues", "hasta"),
        *("wenn", "sobald", "nachdem", "falls", "bis", "fall"),
        *("quand", "lorsque", "lorsqu", "apres", "cas"),
        *("appena", "dopo", "finche"),
        *("zodra", "wanneer", "nadat", "totdat", "geval"),
    }
)
# "If" is "si" in Spanish and French, "se" in Portuguese and Italian and
# "als" in Dutch; the same words are pronouns or "as" in the other
# languages. Dutch puts "mogelijk" (possibly) a few words before the verb.
CONDITIONAL_BY_LANGUAGE: dict[str, frozenset[str]] = {
    "es": frozenset({"si"}),
    "fr": frozenset({"si"}),
    "pt": frozenset({"se"}),
    "it": frozenset({"se"}),
    "nl": frozenset(
        {"als", "indien", "mocht", "mochten", "mogelijk", "misschien", "eventueel"}
    ),
}
GUARD_WINDOW = 48

# "Not at home?" and "if you're away" open a what-if: a pickup point in what
# follows ("then we take it to a branch, where it waits 7 days") is an
# option, not where the parcel is. Folded text.
ABSENCE_PHRASES: tuple[str, ...] = (
    r"not (?:at )?home",
    r"not (?:going to |gonna )?be (?:at )?(?:home|in|there|around)",
    r"(?:won't|wont|will not) be (?:at )?(?:home|in|there|around)",
    r"(?:be|are|re|you) away",
    r"(?:nobody|no one|no-one) (?:is |will be )?(?:at )?home",
    r"nao (?:vai |vais |vao )?(?:estar|esta|estas|estara|estiver|estiveres|esteja"
    r"|estejas) em casa",
    r"no (?:vas a |va a |vais a |van a )?(?:estar|estas|esta|estaras|estara|estes"
    r"|este) en casa",
    r"ausentes?",
    r"nicht (?:zu ?hause|daheim|da|anwesend)",
    r"abwesend",
    r"pas (?:chez (?:vous|toi)|a (?:la maison|domicile))",
    r"(?:etes|serez|seras|es) pas la",
    r"absente?s?",
    r"non (?:sei|sarai|e|sara|siete|sarete) (?:a casa|in casa|presente)",
    r"assent[ei]",
    r"niet thuis",
    r"afwezig",
)
# Past forms and words for a delivery attempt ("were you not at home?",
# "absent lors de notre passage ?") describe what happened instead.
ABSENCE_PAST_WORDS: frozenset[str] = frozenset(
    {
        *("was", "were", "wasn", "weren", "visit", "visited", "called", "came"),
        *("tried", "attempt", "attempted"),
        *("estava", "estavas", "estavam", "esteve", "estiveste", "tentativa"),
        *("passamos", "tentamos"),
        *("estaba", "estabas", "estaban", "estuvo", "estuviste", "intento"),
        *("pasamos", "intentamos"),
        *("war", "waren", "warst", "wart", "gewesen", "versucht"),
        *("etais", "etait", "etiez", "etaient", "ete", "passage"),
        *("eri", "era", "eravate", "erano", "stato", "stata", "stati"),
        *("passaggio", "tentativo"),
        *("geweest", "poging", "langs"),
    }
)
# Dutch "if" words, only counted as a condition before an absence.
_ABSENCE_CONDITIONS = frozenset({"als", "indien", "mocht", "mochten"})
# A question covers the next sentences, a condition its own sentence.
ABSENCE_QUESTION_SENTENCES = 2
ABSENCE_REACH = 240

# "Delivered to the carrier / pickup point / depot" is not a delivery to the
# customer. Checked right after a DELIVERED match, pickup places first so
# that "the DPD Pickup point" isn't read as "DPD".
_HANDOVER_PREPOSITIONS = (
    "to|at|in|into|a|ao|aos|as|al|ai|allo|alla|alle|an|am|aan|bij|au|aux|chez"
    "|no|na|nos|nas|en|em|im|ins|beim|presso|nel|nella|nei|op|naar|zum|zur"
)
HANDOVER_TARGETS: dict[MailKind, tuple[str, ...]] = {
    MailKind.READY_FOR_PICKUP: (
        r"pick ?-?up",
        r"parcel ?shops?",
        r"parcel ?lockers?",
        r"lockers?",
        r"collection points?",
        r"access points?",
        r"service ?points?",
        r"post office",
        r"stores?",
        r"shops?",
        r"cacifos?",
        r"ponto",
        r"loja",
        r"estacao",
        r"punto",
        r"oficina",
        r"tienda",
        r"consigna",
        r"packstation",
        r"paket ?shop",
        r"paketstation",
        r"(?:post)?filiale",
        r"relais",
        r"point (?:relais|retrait|de retrait|pick ?-?up)",
        r"bureau de poste",
        r"consigne",
        r"casier",
        r"ufficio postale",
        r"fermopoint",
        r"afhaalpunt",
        r"ophaalpunt",
        r"pakketpunt",
        r"pakketautomaat",
        r"servicepunt",
        r"punt",
        r"postkantoor",
    ),
    MailKind.IN_TRANSIT: (
        r"depots?",
        r"warehouse",
        r"hub",
        r"(?:sorting|distribution|delivery) (?:centre|center|facility|office)",
        r"facility",
        r"armazem",
        r"centro",
        r"almacen",
        r"delegacion",
        r"plataforma",
        r"lager",
        r"(?:start|ziel)?-?paketzentrum",
        r"(?:verteil|sortier)zentrum",
        r"zustellbasis",
        r"entrepot",
        r"centre de tri",
        r"plateforme",
        r"magazzino",
        r"deposito",
        r"magazijn",
        r"(?:sorteer|distributie)centrum",
    ),
    MailKind.SHIPPED: (
        r"carriers?",
        r"couriers?",
        r"(?:shipping|delivery|logistics) (?:partner|company|provider|service)",
        r"transportadora",
        r"transportador",
        r"estafeta",
        r"transportista",
        r"mensajero",
        r"versanddienstleister",
        r"paketdienst",
        r"zusteller",
        r"spediteur",
        r"(?:logistik|versand)partner",
        r"transporteur",
        r"livreur",
        r"corriere",
        r"vettore",
        r"vervoerder",
        r"(?:bezorg|pakket)dienst",
        r"(?:ctt|dpd|gls|ups|dhl|seur|mrw|nacex|paack|inpost|fedex|tnt|postnl"
        r"|correos|hermes|evri|chronopost|colissimo|bpost|brt|sda)",
        r"(?:royal mail|la poste|poste italiane|deutsche post)",
    ),
}

# Senders and subjects of bounce messages, which quote the original e-mail.
_BOUNCE_LOCALS = frozenset({"mailer-daemon", "postmaster"})
_BOUNCE_SUBJECT_RE = re.compile(
    r"^\W*(?:(?:undeliverable|unzustellbar|non remis|no se puede entregar"
    r"|nao e possivel entregar|non recapitabile|onbestelbaar)\s*:"
    r"|undelivered mail|delivery status notification|mail delivery (?:failed|failure"
    r"|subsystem)|returned mail)"
)

NOTE_KIND_FROM_SUBJECT = "kind_from_subject"
NOTE_KIND_FROM_BODY = "kind_from_body"
NOTE_KIND_DEFAULT = "kind_default"
NOTE_CHECK_DIGIT = "check_digit"
NOTE_KIND_FROM_CODE = "kind_from_code"

# Words that are not a shop's name in a From display name ("Example Shop
# Orders", "No-Reply | Example", "Customer Service - Example").
NAME_NOISE_WORDS: frozenset[str] = frozenset(
    {
        *("no", "reply", "noreply", "donotreply", "do", "not", "dont", "info"),
        *("news", "newsletter", "newsletters", "notification", "notifications"),
        *("alert", "alerts", "update", "updates", "tracking", "team", "support"),
        *("service", "services", "customer", "care", "orders", "order"),
        *("shipping", "shipment", "shipments", "mailer", "mail", "email"),
        *("hello", "contact"),
        *("nao", "responder", "responda", "naoresponder", "noresponder"),
        *("notificacao", "notificacoes", "notificacion", "notificaciones"),
        *("equipa", "equipo", "suporte", "soporte", "servico", "servicos"),
        *("servicio", "cliente", "clientes", "encomendas", "pedidos", "envios"),
        *("contacto",),
        *("nicht", "antworten", "benachrichtigung", "benachrichtigungen"),
        *("kundenservice", "kundendienst", "bestellungen", "versand", "kontakt"),
        *("ne", "pas", "repondre", "nepasrepondre", "equipe", "commandes"),
        *("non", "rispondere", "notifica", "notifiche", "assistenza", "ordini"),
        *("spedizioni",),
        *("niet", "beantwoorden", "antwoorden", "melding", "meldingen"),
        *("klantenservice", "bestellingen", "verzending"),
    }
)

_OPTIONAL_SPACE_RE = re.compile(r" \?")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_GUARD_CUT_RE = re.compile(r"[.!?\n:;|,()\[\]]")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_LEADING_TOKEN_RE = re.compile(r"^[a-z0-9]+")
_LETTER_RE = re.compile(r"[^\W\d_]")
_DIGIT_RE = re.compile(r"\d")


def _fragment(pattern: str) -> str:
    """Turn a table entry into a regex fragment (flexible spaces, apostrophes)."""
    pattern = _OPTIONAL_SPACE_RE.sub(r"\\s*", pattern)
    return pattern.replace(" ", r"\s+").replace("'", "['\u2019]")


def _compile(patterns: Iterable[str]) -> re.Pattern[str]:
    """Compile table entries into one whole-word regex, longest first."""
    ordered = sorted(set(patterns), key=len, reverse=True)
    body = "|".join(_fragment(pattern) for pattern in ordered)
    return re.compile(rf"(?<![a-z0-9])(?:{body})(?![a-z0-9])")


_PHRASE_RES: dict[MailKind, re.Pattern[str]] = {
    kind: _compile(KIND_PHRASES[kind]) for kind in KIND_PRECEDENCE
}
_SUBJECT_RES: dict[MailKind, re.Pattern[str]] = {
    kind: _compile(SUBJECT_KEYWORDS[kind])
    for kind in KIND_PRECEDENCE
    if kind in SUBJECT_KEYWORDS
}
_ON_THE_WAY = frozenset((*ON_THE_WAY_PHRASES, *ON_THE_WAY_KEYWORDS))
_NEUTRAL_PHRASE_RES: dict[MailKind, re.Pattern[str]] = {
    **_PHRASE_RES,
    MailKind.SHIPPED: _compile(set(KIND_PHRASES[MailKind.SHIPPED]) - _ON_THE_WAY),
}
_NEUTRAL_SUBJECT_RES: dict[MailKind, re.Pattern[str]] = {
    **_SUBJECT_RES,
    MailKind.SHIPPED: _compile(set(SUBJECT_KEYWORDS[MailKind.SHIPPED]) - _ON_THE_WAY),
}
_ABSENCE_RE = _compile(ABSENCE_PHRASES)
_QUESTION_TAIL_RE = re.compile(r"[^.!?\n]{0,40}\?")
_CLAUSE_TAIL_RE = re.compile(r"[^.!?\n,;:]{0,40}")
_SENTENCE_END_RE = re.compile(r"[.!?\n][\s.!?]*")
_SENTENCE_START_RE = re.compile(r"[.!?\n](?=[^.!?\n]*$)")
_HANDOVER_RES: tuple[tuple[MailKind, re.Pattern[str]], ...] = tuple(
    (
        kind,
        re.compile(
            rf"\s+(?:(?:{_HANDOVER_PREPOSITIONS})\s+|all['\u2019]\s*)"
            r"(?:[a-z]+(?:['\u2019\-]\s*|\s+)){0,3}?"
            rf"(?:{'|'.join(_fragment(target) for target in targets)})(?![a-z0-9])"
        ),
    )
    for kind, targets in HANDOVER_TARGETS.items()
)


def _blank_links(text: str) -> str:
    """Replace URLs and e-mail addresses with spaces."""
    return _EMAIL_RE.sub(" ", _URL_RE.sub(" ", text))


def _guarded(folded: str, start: int, conditional: frozenset[str]) -> bool:
    """Return True when the words before a match negate it or make it future."""
    low = max(0, start - GUARD_WINDOW)
    window = folded[low:start]
    cut: re.Match[str] | None = None
    for cut in _GUARD_CUT_RE.finditer(window):  # noqa: B007
        pass
    if cut is not None:
        window = window[cut.end() :]
    elif low > 0 and folded[low - 1].isalnum():
        window = _LEADING_TOKEN_RE.sub("", window)
    tokens = _TOKEN_RE.findall(window)
    if not tokens:
        return False
    if tokens[-1] == "no":
        return True
    if any(token in GUARD_WORDS for token in tokens[-2:]):
        return True
    return any(token in conditional for token in tokens[-4:])


def _delivered_to(folded: str, end: int) -> MailKind | None:
    """Return the real kind of "delivered to the carrier/pickup point/depot"."""
    tail = folded[end : end + 160]
    for kind, regex in _HANDOVER_RES:
        if regex.match(tail):
            return kind
    return None


def _sentences_end(folded: str, start: int, count: int) -> int:
    """Return where the ``count``-th sentence from ``start`` ends."""
    limit = min(len(folded), start + ABSENCE_REACH)
    position = start + len(folded[start:limit]) - len(folded[start:limit].lstrip())
    for _ in range(count):
        found = _SENTENCE_END_RE.search(folded, position, limit)
        if found is None:
            return limit
        position = found.end()
    return position


def _absence_scopes(folded: str, conditional: frozenset[str]) -> list[tuple[int, int]]:
    """Return the spans that "not at home?" or "if you're away" make a what-if.

    A question covers the sentences after it, a condition its own sentence.
    Past forms ("were you not at home?") describe what happened, so they
    open no span.
    """
    scopes: list[tuple[int, int]] = []
    for match in _ABSENCE_RE.finditer(folded):
        head = folded[max(0, match.start() - GUARD_WINDOW) : match.start()]
        cut = _SENTENCE_START_RE.search(head)
        if cut is not None:
            head = head[cut.end() :]
        before = _TOKEN_RE.findall(head)[-4:]
        question = _QUESTION_TAIL_RE.match(folded, match.end())
        tail = question or _CLAUSE_TAIL_RE.match(folded, match.end())
        words = [*before[-3:], *_TOKEN_RE.findall(tail.group() if tail else "")]
        if any(word in ABSENCE_PAST_WORDS for word in words):
            continue
        if question is not None:
            start = question.end()
            end = _sentences_end(folded, start, ABSENCE_QUESTION_SENTENCES)
            scopes.append((start, end))
        elif any(word in conditional or word in _ABSENCE_CONDITIONS for word in before):
            start = match.start() - len(head)
            scopes.append((start, _sentences_end(folded, match.end(), 1)))
    return scopes


def _kinds(
    folded: str,
    regexes: Mapping[MailKind, re.Pattern[str]],
    conditional: frozenset[str],
) -> set[MailKind]:
    """Return every kind with an unguarded match in folded text."""
    found: set[MailKind] = set()
    scopes: list[tuple[int, int]] | None = None
    for kind, regex in regexes.items():
        for match in regex.finditer(folded):
            if _guarded(folded, match.start(), conditional):
                continue
            real = kind
            if kind is MailKind.DELIVERED:
                real = _delivered_to(folded, match.end()) or kind
            if real is MailKind.READY_FOR_PICKUP:
                if scopes is None:
                    scopes = _absence_scopes(folded, conditional)
                if any(start <= match.start() < end for start, end in scopes):
                    continue
            found.add(real)
            if real is kind:
                break
    return found


def _pick(kinds: set[MailKind]) -> MailKind | None:
    """Return the kind that takes precedence."""
    return next((kind for kind in KIND_PRECEDENCE if kind in kinds), None)


def _conditional(lang: str | None) -> frozenset[str]:
    """Return the words that make a following keyword a condition."""
    return CONDITIONAL_WORDS | CONDITIONAL_BY_LANGUAGE.get(lang or "", frozenset())


def _tables(
    on_the_way: bool,
) -> tuple[Mapping[MailKind, re.Pattern[str]], Mapping[MailKind, re.Pattern[str]]]:
    """Return the phrase and subject regexes, with or without "on its way"."""
    if on_the_way:
        return _PHRASE_RES, _SUBJECT_RES
    return _NEUTRAL_PHRASE_RES, _NEUTRAL_SUBJECT_RES


def detect_kind(
    subject: str,
    text: str = "",
    *,
    lang: str | None = None,
    on_the_way: bool = True,
) -> tuple[MailKind | None, str]:
    """Return the kind of a shipping e-mail and where it was found.

    The subject's phrases and keywords are checked first, then the phrases
    in the start of the body. Returns ``(kind, "subject")``,
    ``(kind, "body")`` or ``(None, "")``. ``lang`` decides whether "si" or
    "se" means "if". With ``on_the_way=False``, "on its way" alone is no
    evidence of SHIPPED.
    """
    conditional = _conditional(lang)
    phrases, keywords = _tables(on_the_way)
    folded_subject = fold(subject[:MAX_SUBJECT_CHARS])
    for regexes in (phrases, keywords):
        kind = _pick(_kinds(folded_subject, regexes, conditional))
        if kind is not None:
            return kind, "subject"
    body = fold(_blank_links(text[:KIND_BODY_CHARS]))
    kind = _pick(_kinds(body, phrases, conditional))
    if kind is not None:
        return kind, "body"
    return None, ""


def text_kinds(
    subject: str,
    text: str = "",
    *,
    lang: str | None = None,
    on_the_way: bool = True,
) -> set[MailKind]:
    """Return every kind whose wording appears unguarded in an e-mail.

    Unlike ``detect_kind``, which picks one kind, this returns all of them
    from the subject's phrases and keywords and the start of the body, so a
    caller can tell whether another reading is backed by the text too.
    """
    conditional = _conditional(lang)
    phrases, keywords = _tables(on_the_way)
    folded_subject = fold(subject[:MAX_SUBJECT_CHARS])
    body = fold(_blank_links(text[:KIND_BODY_CHARS]))
    return (
        _kinds(folded_subject, phrases, conditional)
        | _kinds(folded_subject, keywords, conditional)
        | _kinds(body, phrases, conditional)
    )


# Order numbers: full labels ("Order number", "Número de pedido",
# "Bestellnummer"...), or a short word with a marker ("Order #1001",
# "Encomenda n.º 123", "Commande n° 123"). Matched on fold_aligned text.
_ORDER_VALUE = r"(?P<value>[a-z0-9][a-z0-9\-]{2,29})(?![a-z0-9\-])(?![/.,:]\d)(?!\.\d)"
_ORDER_LABEL_RE = re.compile(
    r"(?<![a-z0-9])(?:"
    r"order\s*(?:number|no|nr|num|id|ref(?:erence)?|code)"
    r"|(?:numero|n\.?\s*o|num)\.?\s*(?:(?:de|da|do|del)\s+)?(?:encomenda|pedido|compra)"
    r"|(?:referencia|id|codigo)\s+(?:de|del)\s+pedido"
    r"|bestell(?:ungs)?(?:nummer|-?\s*nr)|auftrags(?:nummer|-?\s*nr)"
    r"|(?:numero|n[o\u00b0])\s*de\s+commande|reference\s+de\s+(?:la\s+)?commande"
    r"|(?:numero|n\.|n[o\u00b0]|codice|id|riferimento)\s*"
    r"(?:dell['\u2019]\s*|d['\u2019]\s*|del\s+)?ordine"
    r"|bestel(?:ling)?nummer|ordernummer|ordernr"
    r")(?![a-z0-9])\.?\s*(?:[:#.]\s*)*" + _ORDER_VALUE
)
_ORDER_SHORT_RE = re.compile(
    r"(?<![a-z0-9])(?:order|pedido|encomenda|bestellung|commande|ordine|bestelling)"
    r"\s*(?:n\.?\s*[o\u00b0]\.?|n\.|nr\.?|no\.?|num\.?|#|:)\s*[:#]?\s*" + _ORDER_VALUE
)
_DATE_LIKE_RE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}-\d{2,4}")
_NON_ALNUM_RE = re.compile(r"[^0-9A-Z]")


def find_order_numbers(text: str) -> list[str]:
    """Return order numbers written after localised labels, in text order.

    "Order #1001" gives "#1001"; other labels give the value as written
    ("Bestellnummer: 4711-0815" -> "4711-0815"). Values need a digit; dates
    and prices are skipped. At most five numbers.
    """
    text = text[:SCAN_CHARS]
    folded = fold_aligned(text)
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for regex in (_ORDER_LABEL_RE, _ORDER_SHORT_RE):
        for match in regex.finditer(folded):
            start, end = match.span("value")
            value = text[start:end].rstrip("-")
            if not _DIGIT_RE.search(value) or _DATE_LIKE_RE.fullmatch(value):
                continue
            key = _NON_ALNUM_RE.sub("", value.upper())
            if key in seen:
                continue
            seen.add(key)
            if folded[match.start() : start].rstrip().endswith("#"):
                value = f"#{value}"
            found.append((start, value))
    found.sort()
    return [value for _, value in found[:MAX_ORDER_NUMBERS]]


# Pickup point labels. Strong labels may stand alone on a line (the point
# is on the next line); weak ones need a colon.
_POINT_STRONG = (
    r"pick\s*-?\s*up\s+(?:point|location|store|shop)|collection\s+point"
    r"|parcel\s*shop|parcel\s+locker|access\s+point|service\s*point"
    r"|ponto\s+(?:de\s+)?(?:recolha|levantamento|entrega|pickup)"
    r"|local\s+de\s+(?:levantamento|recolha)"
    r"|punto\s+(?:de\s+)?(?:recogida|entrega)|punto\s+pack"
    r"|abhol(?:ort|stelle|filiale)|paketshop|packstation"
    r"|point\s+relais|point\s+(?:de\s+)?retrait|lieu\s+de\s+retrait"
    r"|punto\s+(?:di\s+)?ritiro|fermopoint"
    r"|afhaalpunt|ophaalpunt|pakketpunt|servicepunt|pakketautomaat"
)
_POINT_WEAK = (
    r"lockers?|cacifo|loja|oficina|filiale|paketstation|relais|ufficio\s+postale"
    r"|store|shop|tienda"
)
_POINT_LINE_RE = re.compile(
    r"^[^a-z0-9]*(?:(?:your|selected|o\s+seu|a\s+sua|o\s+teu|a\s+tua|tu|su|ihr"
    r"|ihre|dein|deine|votre|ton|il\s+tuo|il\s+suo|la\s+tua|la\s+sua|je|jouw|uw)\s+)?"
    rf"(?:(?P<strong>{_POINT_STRONG})|(?:{_POINT_WEAK}))"
    r"(?:\s*\([^)]*\))?\s*(?:(?P<colon>:)\s*(?P<rest>.*?))?\s*$"
)
_POINT_STRIP = " \t-\u2013\u2014\u2022*|>:"
_POINT_LOOKAHEAD_LINES = 3


def _clean_point(value: str) -> str | None:
    """Return a pickup point name fit for display, or None."""
    value = " ".join(value.split()).strip(_POINT_STRIP)
    if (
        not value
        or "http" in value.lower()
        or "@" in value
        or not _LETTER_RE.search(value)
    ):
        return None
    return value[:MAX_POINT_CHARS].rstrip()


def _pickup_point(text: str) -> str | None:
    """Return the pickup point after a label ("Pickup point: ...")."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = _POINT_LINE_RE.match(fold_aligned(line))
        if match is None or (match["strong"] is None and match["colon"] is None):
            continue
        if match["rest"]:
            point = _clean_point(line[match.start("rest") : match.end("rest")])
        else:
            following = (
                candidate
                for candidate in lines[index + 1 : index + 1 + _POINT_LOOKAHEAD_LINES]
                if candidate.strip()
            )
            point = _clean_point(next(following, ""))
        if point is not None:
            return point
    return None


_NAME_SPLIT_RE = re.compile(
    r"\s*[|\u2022\u00b7:]\s*|\s+[\u2013\u2014-]\s+|\s+via\s+", re.IGNORECASE
)
_NAME_ADDRESS_RE = re.compile(r"<[^<>]*>")
_NAME_DELETE = str.maketrans("", "", "\"'()[]<>{}*")
MAX_NAME_INPUT = 200


def _noise_word(word: str) -> bool:
    """Return True for a word that is not part of a shop's name."""
    tokens = _TOKEN_RE.findall(fold(word))
    return not tokens or all(token in NAME_NOISE_WORDS for token in tokens)


def clean_sender_name(name: str) -> str | None:
    """Return a shop name from a From display name, or None.

    Drops "no-reply", "notifications", "customer service" and similar
    parts: "Example Shop | Notifications" and "No-Reply - Example Shop" give
    "Example Shop". Addresses in angle brackets are dropped, and parts with
    an e-mail address are ignored.
    """
    name = _NAME_ADDRESS_RE.sub(" ", (name or "")[:MAX_NAME_INPUT])
    for segment in _NAME_SPLIT_RE.split(name):
        if "@" in segment:
            continue
        words = segment.translate(_NAME_DELETE).split()
        while words and _noise_word(words[0]):
            words.pop(0)
        while words and _noise_word(words[-1]):
            words.pop()
        cleaned = " ".join(words)
        if cleaned and _LETTER_RE.search(cleaned):
            return cleaned[:MAX_MERCHANT_CHARS].rstrip()
    return None


def _merchant(message: MailMessage, info: SenderInfo | None, domain: str) -> str | None:
    """Return the merchant: a known merchant, the sender's name or domain.

    Carriers are not merchants, so e-mails from a carrier have none, and a
    shop that sends its carrier's notices ("GLS PT Informa") is named by its
    domain.
    """
    if info is not None and info.kind == "merchant":
        return info.name
    if info is not None and info.kind == "carrier":
        return None
    name = clean_sender_name(message.sender_name)
    if name and not brand_carriers(name):
        return name
    if info is not None:
        return info.name
    return organizational_domain(domain) if domain else None


def _host(url: str) -> str:
    """Return a link's host name, or "" when the URL is malformed."""
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _carrier_for(
    match: TrackingMatch,
    link_carriers: set[str],
    info: SenderInfo | None,
    brands: tuple[str, ...] = (),
) -> str | None:
    """Return the carrier of a number: its format, a carrier link or the sender.

    ``brands`` are the carriers the sender's name names; one of them counts
    when the number has its format.
    """
    if match.carrier:
        return match.carrier
    if len(link_carriers) == 1:
        carrier = next(iter(link_carriers))
        if validate_tracking_number(match.number, carrier):
            return carrier
    valid = [c for c in brands if validate_tracking_number(match.number, c)]
    if len(valid) == 1:
        return valid[0]
    if (
        info is not None
        and info.carrier
        and (
            info.kind == "carrier"
            or validate_tracking_number(match.number, info.carrier)
        )
    ):
        return info.carrier
    return None


def _numbers(
    message: MailMessage, info: SenderInfo | None, orders: Iterable[str], text: str
) -> list[TrackingMatch]:
    """Return the tracking numbers in ``text`` and the links, validated first.

    ``text`` is the subject and the body, with codes masked.
    """
    hint = info.carrier if info is not None else None
    found: dict[str, TrackingMatch] = {}

    def add(match: TrackingMatch) -> None:
        old = found.get(match.number)
        if old is None:
            found[match.number] = match
        else:
            found[match.number] = TrackingMatch(
                match.number,
                old.carrier or match.carrier,
                old.validated or match.validated,
            )

    for match in find_tracking_numbers(text, carrier=hint):
        add(match)
    link_carriers: set[str] = set()
    for link in message.links[:MAX_LINKS]:
        host = _host(link.url)
        host_info = lookup(host) if host else None
        if host_info is not None and host_info.kind == "carrier" and host_info.carrier:
            link_carriers.add(host_info.carrier)
        for match in numbers_from_url(link.url):
            add(match)

    order_keys = {normalize_tracking_number(order) for order in orders}
    brands = brand_carriers(message.sender_name) if info is None else ()
    numbers = [
        TrackingMatch(
            match.number,
            _carrier_for(match, link_carriers, info, brands),
            match.validated,
        )
        for match in found.values()
        if match.number not in order_keys
    ]
    numbers.sort(key=lambda match: not match.validated)
    return numbers[:MAX_SHIPMENTS]


def _eta(
    message: MailMessage, kind: MailKind, tz: tzinfo, lang: str | None
) -> Eta | None:
    """Return the delivery date; "today" for out-for-delivery e-mails."""
    if kind in NO_ETA_KINDS:
        return None
    reference = message.date
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    eta = find_eta(message.text[:SCAN_CHARS], reference, tz, lang) or find_eta(
        message.subject[:MAX_SUBJECT_CHARS], reference, tz, lang
    )
    if eta is None and kind is MailKind.OUT_FOR_DELIVERY:
        today = reference.astimezone(tz).date()
        eta = Eta(today, today)
    return eta


def _is_bounce(message: MailMessage) -> bool:
    """Return True for bounce messages, which quote someone else's e-mail."""
    local = message.sender.partition("@")[0].lower()
    return local in _BOUNCE_LOCALS or bool(
        _BOUNCE_SUBJECT_RE.match(fold(message.subject[:MAX_SUBJECT_CHARS]))
    )


def parse_generic(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo
) -> ParseResult | None:
    """Read a shipping e-mail from a sender without a dedicated parser.

    Returns one shipment per tracking number found in the text or in
    carrier tracking links, or one shipment without a number for an e-mail
    with a recognised kind and an order number. A delivery PIN or pickup
    code is read whatever the kind when the e-mail is about one parcel; an
    e-mail with no other news gets the kind ``CODE``. Returns None when
    nothing parcel-like is found.
    """
    if _is_bounce(message):
        return None
    domain = (verdict.domain or message.sender_domain).lower()
    info = lookup(domain) if domain else None
    subject = message.subject[:MAX_SUBJECT_CHARS]
    text = message.text[:SCAN_CHARS]
    language = message.language or detect_language(
        f"{subject}\n{text[:KIND_BODY_CHARS]}"
    )
    kind, source = detect_kind(subject, text, lang=language)
    locker = kind in _LOCKER_KINDS
    # Numbers are read without the codes, so a PIN is never one of them.
    plain = f"{mask_codes(subject, locker=locker)}\n{mask_codes(text, locker=locker)}"
    orders = find_order_numbers(plain)
    numbers = _numbers(message, info, orders, plain)
    code: str | None = None
    if len(numbers) <= 1:
        exclude = [*(match.number for match in numbers), *orders]
        code = find_code(text, exclude=exclude, locker=locker) or find_code(
            subject, exclude=exclude, locker=locker
        )
    only_code = kind is None and code is not None and bool(numbers or orders)
    if not numbers and (kind is None or not orders) and not only_code:
        return None

    notes: list[str] = []
    if only_code:
        kind = MailKind.CODE
        notes.append(NOTE_KIND_FROM_CODE)
    elif kind is None:
        kind = MailKind.SHIPPED
        notes.append(NOTE_KIND_DEFAULT)
    else:
        notes.append(
            NOTE_KIND_FROM_SUBJECT if source == "subject" else NOTE_KIND_FROM_BODY
        )
    eta = _eta(message, kind, tz, language) if kind is not MailKind.CODE else None
    point: str | None = None
    if kind is MailKind.READY_FOR_PICKUP and len(numbers) <= 1:
        point = _pickup_point(text)

    order_numbers = tuple(orders)
    if numbers:
        shipments = [
            ParsedShipment(
                carrier=match.carrier,
                tracking_number=match.number,
                kind=kind,
                eta=eta,
                pickup_point=point,
                pickup_code=code,
                order_numbers=order_numbers,
                tracking_url=tracking_url(match.carrier, match.number),
            )
            for match in numbers
        ]
    else:
        carrier = info.carrier if info is not None and info.kind == "carrier" else None
        shipments = [
            ParsedShipment(
                carrier=carrier,
                kind=kind,
                eta=eta,
                pickup_point=point,
                pickup_code=code,
                order_numbers=order_numbers,
            )
        ]

    confidence = BASE_CONFIDENCE
    check_digit = any(check_digit_ok(match.number, match.carrier) for match in numbers)
    if check_digit:
        confidence += CHECK_DIGIT_BONUS
        notes.append(NOTE_CHECK_DIGIT)
    if source == "subject":
        confidence += SUBJECT_KIND_BONUS
    confidence = min(confidence, MAX_CONFIDENCE)
    if numbers and not check_digit:
        confidence = min(confidence, FORMAT_ONLY_CONFIDENCE)
    if kind is MailKind.CODE:
        confidence = CODE_CONFIDENCE
        if has_code_label(subject):
            confidence += SUBJECT_KIND_BONUS

    return ParseResult(
        parser=PARSER,
        kind=kind,
        merchant=_merchant(message, info, domain),
        order_numbers=order_numbers,
        shipments=shipments,
        confidence=round(confidence, 2),
        language=language,
        notes=tuple(notes),
    )
