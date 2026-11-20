"""Paack e-mails (Spain, Portugal, France and Italy), sent for shops such as
Zara and Amazon.

Each notice has a header ("Será entregue em <date> entre as <start> e as
<end>"), a status, a title and a sentence, then the shop ("Order from",
"Pedido de") and the order ID in a details table. The shop is also named in
the sentences, in Paack's own ways ("Your <shop> order", "O seu pedido a
<shop>").

Some notices name an earlier status: a return after a failed attempt, a
pickup point that received the parcel ("Pedido entregue em <point>"). Their
title or status decides: "Retorno em andamento", "Pronto para retirada",
"Pedido cancelado", whatever the other lines say.

The number is Paack's order ID, nine letters and digits in mixed case, "_"
and the package number ("Ab3Cd4Ef5_1"), given at the end of the e-mail
("Order number", "Número de pedido") and in the tracking and preferences
links; it is kept as written. Its first part, the stem, is Paack's order
reference: some e-mails give only the stem as their "Order number", and it
is never the shop's order number. Those links also carry the postcode, the
e-mail address or the phone, which are never read. The label's barcode
("5340" and 14 digits) is Paack's too: Amazon shows it as the tracking ID.
"""

from __future__ import annotations

from typing import Final

from ...const import MailKind
from ._common import CarrierSpec

# Failed attempts. The headers also say the delivery will be rescheduled or
# the parcel returned, which the other phrases decide.
_ATTEMPTED: Final = (
    # pt
    "nao foi possivel entregar",
    "nao pode ser entregue",
    "nao conseguimos entregar",
    "tentamos entregar",
    "falha na entrega",
    "cliente ausente",
    "morada incorreta",
    "falta dinheiro na entrega",
    # es
    "no ha podido ser entregado",
    "no se pudo entregar",
    "no hemos podido entregar",
    "no pudimos entregar",
    "hemos intentado entregar",
    "intentamos entregar",
    "direccion incorrecta",
    "falta pago contra reembolso",
    "entrega fallida",
    # fr
    "n'a pas pu etre livree",
    "n'a pas pu etre livre",
    "nous n'avons pas pu livrer",
    "nous n'avons pas ete en mesure de livrer",
    "impossible de livrer",
    "nous avons essaye de livrer",
    "nous avons tente de livrer",
    "adresse incorrecte",
    "paiement manquant a la livraison",
    "echec de la livraison",
    "client non trouve",
    # it
    "non e stato possibile consegnarlo",
    "non abbiamo potuto consegnare",
    "non siamo riusciti a consegnare",
    "impossibile consegnare",
    "abbiamo provato a consegnare",
    "abbiamo tentato di consegnare",
    "indirizzo errato",
    "manca il pagamento alla consegna",
    "consegna non riuscita",
    "cliente assente",
    # en
    "couldn't be delivered",
    "we couldn't deliver",
    "incorrect address",
    "missing cash on delivery",
    "failed delivery attempt",
    "customer absent",
)

# The titles and statuses that decide a notice's kind.
_DECISIVE: Final = {
    MailKind.SHIPPED: (
        "informacao recebida",
        "detalhes do pedido recebidos",
        "informacion recibida",
        "detalles del pedido recibidos",
        "informations recues",
        "details de la commande recue",
        "informazioni ricevute",
        "dettagli dell'ordine ricevuto",
        "information received",
        "order details received",
    ),
    MailKind.RETURN: (
        # In progress.
        "retorno em andamento",
        "devolucao em andamento",
        "devolucao em curso",
        "devolucion en proceso",
        "devolucion en curso",
        "retour en cours",
        "reso in corso",
        "return in progress",
        # Rejected.
        "rejeitado pelo cliente",
        "rechazado por el cliente",
        "refuse par le client",
        "rejete par le client",
        "rifiutato dal cliente",
        "rejected by customer",
        # Returned to the shop.
        "devolucao a",
        "foi devolvido para",
        "devuelto a",
        "ha sido devuelto a",
        "retourne a",
        "retournee a",
        "a ete retourne",
        "restituito a",
        "e stato restituito a",
        "returned to",
        "has been returned to",
        # Being returned.
        "estamos a gerir a devolucao",
        "vamos proceder com a devolucao",
        "estamos gestionando la devolucion",
        "procederemos a devolverlo",
        "nous nous occupons du retour",
        "nous procederons au retour",
        "stiamo gestendo il reso",
        "procederemo con il reso",
        "managing the return",
        "we will proceed with returning",
    ),
    MailKind.CANCELLED: (
        "pedido cancelado",
        "foi cancelado",
        "fue cancelado",
        "ha sido cancelado",
        "commande annulee",
        "a ete annulee",
        "a ete annule",
        "ordine annullato",
        "e stato annullato",
        "order cancelled",
        "order canceled",
        "was cancelled",
        "was canceled",
        "has been cancelled",
    ),
    MailKind.READY_FOR_PICKUP: (
        "pronto para retirada",
        "disponivel para retirada",
        "listo para recoger",
        "disponible para recoger",
        "prete a etre recuperee",
        "disponible pour etre recuperee",
        "pronto per essere ritirato",
        "disponibile per il ritiro",
        "ready for pickup",
        "available for pickup",
    ),
    MailKind.DELIVERED: (
        "voce recebeu seu pedido",
        "has recibido tu pedido",
        "vous avez recu votre commande",
        "hai ricevuto il tuo ordine",
        "you've received your order",
        "you have received your order",
    ),
}

SPEC: Final = CarrierSpec(
    carrier="paack",
    brands=("paack",),
    link_hosts=("paack.co", "paack.app", "paack.com", "paack.es"),
    # Only the number: never "postal_code", "email", "phone" or the tokens.
    link_params=("tracking_number", "trackingnumber"),
    # The preferences links carry the number too.
    link_words_ok=("preference",),
    labels=("codigo paack", "codigo de envio paack"),
    merchant_labels=(
        "order from",
        "encomenda de",
        "pedido de",
        "commande aupres de",
        "commande chez",
        "commande de",
        "ordine di",
    ),
    phrases=(
        (MailKind.OUT_FOR_DELIVERY, "llegara hoy"),
        (MailKind.OUT_FOR_DELIVERY, "chega hoje"),
        (MailKind.OUT_FOR_DELIVERY, "chegara hoje"),
        # The courier collected the parcel at the depot to deliver it.
        (MailKind.OUT_FOR_DELIVERY, "estafeta recolheu"),
        (MailKind.OUT_FOR_DELIVERY, "repartidor ha recogido"),
        (MailKind.OUT_FOR_DELIVERY, "livreur a recupere"),
        (MailKind.OUT_FOR_DELIVERY, "courier picked up"),
        (MailKind.IN_TRANSIT, "llegara manana"),
        (MailKind.IN_TRANSIT, "chega amanha"),
        (MailKind.DELAYED, "se ha reprogramado"),
        (MailKind.DELAYED, "a ete reprogramme"),
        (MailKind.DELAYED, "e stato riprogrammato"),
        # "We missed you" in Paack's other languages.
        (MailKind.ATTEMPTED, "nao o encontramos"),
        (MailKind.ATTEMPTED, "no te hemos encontrado"),
        (MailKind.ATTEMPTED, "nous ne vous avons pas vu"),
        (MailKind.ATTEMPTED, "non ti abbiamo trovato"),
        *((MailKind.ATTEMPTED, phrase) for phrase in _ATTEMPTED),
    ),
    # Collected from a PaackGo Point.
    collected=("coletado", "fue recogido", "recuperee"),
    decisive=tuple(
        (kind, phrase) for kind, phrases in _DECISIVE.items() for phrase in phrases
    ),
)
