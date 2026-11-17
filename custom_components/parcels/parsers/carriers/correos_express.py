"""Correos Express e-mails (Spain and Portugal).

"Tu envío está en reparto" with a "franja horaria", "ha sido entregado"
and, in Portuguese, "em distribuição" and "entregue". Shipment numbers are
long all-digit codes.
"""

from __future__ import annotations

from typing import Final

from ._common import CarrierSpec

SPEC: Final = CarrierSpec(
    carrier="correos_express",
    brands=("correos express", "correosexpress"),
    link_hosts=("correosexpress.com", "correosexpress.es", "correosexpress.pt"),
    link_params=("shippingnumber", "envio", "numenvio", "numero"),
    labels=("n.o de envio", "numero de envio", "n.o envio", "referencia del envio"),
)
