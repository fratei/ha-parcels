"""Paack e-mails (Spain and Portugal), sent for shops such as Zara and Amazon.

"Tu pedido de <tienda> llegará hoy entre las 14:00 y las 16:00" or "Será
entregue em <date> entre as <start> e as <end>": the shop is named, in a
sentence or under an "Order from" label.

The number is Paack's order ID, nine letters and digits in mixed case, "_"
and the package number ("Ab3Cd4Ef5_1"), given at the end of the e-mail
("Order number", "Número de pedido") and in the tracking and preferences
links; it is kept as written. Those links also carry the postcode, the
e-mail address or the phone, which are never read. The label's barcode
("5340" and 14 digits) is Paack's too: Amazon shows it as the tracking ID.
"""

from __future__ import annotations

from typing import Final

from ...const import MailKind
from ._common import CarrierSpec

SPEC: Final = CarrierSpec(
    carrier="paack",
    brands=("paack",),
    link_hosts=("paack.co", "paack.app", "paack.com", "paack.es"),
    # Only the number: never "postal_code", "email", "phone" or the tokens.
    link_params=("tracking_number", "trackingnumber"),
    # The preferences links carry the number too.
    link_words_ok=("preference",),
    labels=("codigo paack", "codigo de envio paack"),
    # "Order from" is Paack's label; the other languages' are inferred.
    merchant_labels=(
        "order from",
        "encomenda de",
        "pedido de",
        "commande de",
        "ordine di",
    ),
    phrases=(
        (MailKind.OUT_FOR_DELIVERY, "llegara hoy"),
        (MailKind.OUT_FOR_DELIVERY, "chega hoje"),
        (MailKind.OUT_FOR_DELIVERY, "chegara hoje"),
        (MailKind.IN_TRANSIT, "llegara manana"),
        (MailKind.IN_TRANSIT, "chega amanha"),
        # "We missed you" in Paack's other languages.
        (MailKind.ATTEMPTED, "nao o encontramos"),
        (MailKind.ATTEMPTED, "no te hemos encontrado"),
        (MailKind.ATTEMPTED, "nous ne vous avons pas vu"),
        (MailKind.ATTEMPTED, "non ti abbiamo trovato"),
    ),
)
