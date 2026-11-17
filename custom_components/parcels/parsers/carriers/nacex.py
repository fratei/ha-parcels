"""Nacex e-mails (Spain and Portugal), including NACEX.shop pickups.

Nacex names a shipment by agency and number ("2834/12345678"); the slash
is kept, as on the tracking page.
"""

from __future__ import annotations

from typing import Final

from ...const import MailKind
from ._common import CarrierSpec

SPEC: Final = CarrierSpec(
    carrier="nacex",
    brands=("nacex", "nacex.shop"),
    link_hosts=("nacex.es", "nacex.pt", "nacex.com", "nacex.*"),
    link_params=("expedicion", "codigo", "numero"),
    labels=("n.o de expedicion", "n.o de envio", "codigo de expedicion"),
    phrases=(
        (MailKind.READY_FOR_PICKUP, "ya puedes recoger"),
        (MailKind.READY_FOR_PICKUP, "ja pode recolher"),
        (MailKind.READY_FOR_PICKUP, "disponible en el nacex.shop"),
        (MailKind.READY_FOR_PICKUP, "disponivel na nacex.shop"),
    ),
)
