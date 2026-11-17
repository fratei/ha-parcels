"""SEUR e-mails (Spain and Portugal), including Predict and Pickup points.

"Tu envío … llegará hoy entre las 10:00 y las 14:00", "ha sido
entregado", "está disponible en tu punto Pickup". Shipments are named by
an "expedición" or "localizador" code.
"""

from __future__ import annotations

from typing import Final

from ...const import MailKind
from ._common import CarrierSpec

SPEC: Final = CarrierSpec(
    carrier="seur",
    brands=("seur", "seur predict", "seur pickup"),
    link_hosts=("seur.com", "seur.*"),
    link_params=("segonlineidentificador", "localizador", "expedicion", "id"),
    labels=(
        "n.o de expedicion",
        "n.o de envio",
        "referencia seur",
        "codigo seur",
    ),
    phrases=(
        (MailKind.OUT_FOR_DELIVERY, "llegara hoy"),
        (MailKind.OUT_FOR_DELIVERY, "chegara hoje"),
        (MailKind.READY_FOR_PICKUP, "disponible en tu punto"),
        (MailKind.READY_FOR_PICKUP, "disponivel no teu ponto"),
        (MailKind.READY_FOR_PICKUP, "disponivel no seu ponto"),
    ),
)
