"""MRW e-mails (Spain and Portugal).

MRW names a shipment by franchise and "albarán", written "02650/0123456"
or as one number; the slash is dropped so both forms match.
"""

from __future__ import annotations

from typing import Final

from ._common import CarrierSpec

SPEC: Final = CarrierSpec(
    carrier="mrw",
    brands=("mrw",),
    link_hosts=("mrw.es", "mrw.pt", "mrw.*"),
    link_params=("envio", "numeroenvio", "albaran", "num"),
    labels=("n.o de albaran", "numero de envio mrw", "n.o de envio", "guia mrw"),
    strip_slash=True,
)
