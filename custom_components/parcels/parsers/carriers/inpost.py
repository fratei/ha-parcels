"""InPost and Vinted Go locker e-mails.

Both say a parcel is ready in a locker, give a code that opens it and a
deadline, and later that it was collected. Vinted e-mails can also be
about parcels carried by others (CTT, InPost, Mondial Relay...): the
carrier the e-mail names first is used. Seller-side e-mails ("deliver it
to the buyer") are not about the user's parcels.
"""

from __future__ import annotations

from typing import Final

from ...const import MailKind
from ..tracking import CARRIER_WORDS
from ._common import CarrierSpec, resolve_by_name

_PHRASES: Final[tuple[tuple[MailKind, str], ...]] = (
    (MailKind.READY_FOR_PICKUP, "esta a tua espera"),
    (MailKind.READY_FOR_PICKUP, "esta a sua espera"),
    (MailKind.READY_FOR_PICKUP, "te espera"),
    (MailKind.READY_FOR_PICKUP, "te esta esperando"),
    (MailKind.READY_FOR_PICKUP, "is waiting for you"),
    (MailKind.READY_FOR_PICKUP, "ready to collect"),
    (MailKind.READY_FOR_PICKUP, "ready for collection"),
    (MailKind.READY_FOR_PICKUP, "pronto a levantar"),
    (MailKind.READY_FOR_PICKUP, "pronta a levantar"),
    (MailKind.READY_FOR_PICKUP, "pronto para levantamento"),
    (MailKind.READY_FOR_PICKUP, "listo para recoger"),
    (MailKind.READY_FOR_PICKUP, "pronto per il ritiro"),
    (MailKind.READY_FOR_PICKUP, "pronto da ritirare"),
    (MailKind.READY_FOR_PICKUP, "pret a etre retire"),
    (MailKind.READY_FOR_PICKUP, "disponible au retrait"),
    (MailKind.READY_FOR_PICKUP, "klaar om op te halen"),
    (MailKind.READY_FOR_PICKUP, "kan worden opgehaald"),
)
_COLLECTED: Final = (
    "foi recolhida",
    "foi recolhido",
    "foi levantada",
    "foi levantado",
    "has been collected",
    "was collected",
    "ha sido recogido",
    "has recogido",
    "e stato ritirato",
    "hai ritirato",
    "a ete retire",
    "is opgehaald",
)
_SELLER_SIDE: Final = (
    "ao comprador",
    "al comprador",
    "to the buyer",
    "to your buyer",
    "an den kaufer",
    "a l'acheteur",
    "a votre acheteur",
    "all'acquirente",
    "aan de koper",
    "deposita o artigo",
    "deposita el articulo",
    "drop off your parcel",
    "drop your parcel off",
    "deposez votre colis",
)

INPOST_SPEC: Final = CarrierSpec(
    carrier="inpost",
    brands=("inpost", "inpost locker", "paczkomat"),
    link_hosts=("inpost.*", "inpost-spain.com", "inpost.co.uk", "inpost.eu"),
    link_params=("number", "parcel", "parcelnumber", "tracking", "numero"),
    labels=("numero do volume", "numero de envio inpost", "codigo de envio"),
    phrases=_PHRASES,
    collected=_COLLECTED,
)

VINTED_GO_SPEC: Final = CarrierSpec(
    carrier="vinted_go",
    brands=("vinted go", "vinted"),
    link_hosts=("vintedgo.com", "vinted.*", "vinted.co.uk"),
    link_params=("tracking_code", "code", "tracking", "number"),
    labels=("codigo de envio", "codigo de seguimiento", "code de suivi"),
    phrases=_PHRASES,
    collected=_COLLECTED,
    reject=_SELLER_SIDE,
    resolve=resolve_by_name({"vinted go": "vinted_go", **CARRIER_WORDS}, "vinted_go"),
    default_merchant="Vinted",
)
