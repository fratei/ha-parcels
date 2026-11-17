"""Paack e-mails (Spain and Portugal), sent for shops such as Zara.

"Tu pedido de <tienda> llegará hoy entre las 14:00 y las 16:00": the shop
is named, and the tracking code often appears only in the tracking link.
"""

from __future__ import annotations

from typing import Final

from ...const import MailKind
from ._common import CarrierSpec

SPEC: Final = CarrierSpec(
    carrier="paack",
    brands=("paack",),
    link_hosts=("paack.co", "paack.app", "paack.com", "paack.es"),
    link_params=("tracking_number", "trackingnumber", "tracking", "code"),
    labels=("codigo paack", "codigo de envio paack"),
    phrases=(
        (MailKind.OUT_FOR_DELIVERY, "llegara hoy"),
        (MailKind.OUT_FOR_DELIVERY, "chega hoje"),
        (MailKind.OUT_FOR_DELIVERY, "chegara hoje"),
        (MailKind.IN_TRANSIT, "llegara manana"),
        (MailKind.IN_TRANSIT, "chega amanha"),
    ),
)
