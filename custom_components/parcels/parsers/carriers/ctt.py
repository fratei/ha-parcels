"""CTT (Correios de Portugal) and CTT Expresso e-mails.

CTT writes in Portuguese: "O seu objeto RR123456785PT está em
distribuição", "foi entregue", "não foi possível entregar", "aguarda
levantamento" at a Loja CTT, a Ponto CTT or a Cacifo (locker, with a code
and a deadline) and "desalfandegamento" for customs. Objects carry UPU S10
numbers; CTT Expresso also uses its own alphanumeric codes.
"""

from __future__ import annotations

from typing import Final

from ...const import MailKind
from ._common import CarrierSpec, resolve_by_name

_HOSTS: Final = ("ctt.pt", "cttexpresso.pt", "cttexpress.com", "cttexpress.es")
_PARAMS: Final = ("objects", "objectcodeinput", "searchinput", "codigo", "shipment")
_LABELS: Final = (
    "n.o do objeto",
    "n.o de objeto",
    "codigo de objeto",
    "n.o de envio",
    "n.o da encomenda",
    "referencia ctt",
)
_PHRASES: Final[tuple[tuple[MailKind, str], ...]] = (
    (MailKind.OUT_FOR_DELIVERY, "saiu para distribuicao"),
    (MailKind.OUT_FOR_DELIVERY, "em distribuicao hoje"),
    (MailKind.ATTEMPTED, "foi deixado aviso"),
    (MailKind.ATTEMPTED, "deixamos aviso"),
    (MailKind.ATTEMPTED, "deixado um aviso"),
    (MailKind.READY_FOR_PICKUP, "disponivel para levantamento"),
    (MailKind.READY_FOR_PICKUP, "ja pode levantar"),
    (MailKind.CUSTOMS, "aguarda desalfandegamento"),
    (MailKind.CUSTOMS, "processo de desalfandegamento"),
    (MailKind.CUSTOMS, "retido na alfandega"),
)

CTT_SPEC: Final = CarrierSpec(
    carrier="ctt",
    brands=("ctt", "correios de portugal", "ctt correios"),
    link_hosts=_HOSTS,
    link_params=_PARAMS,
    labels=_LABELS,
    phrases=_PHRASES,
    # CTT also delivers CTT Expresso parcels; the e-mail says which.
    resolve=resolve_by_name(
        {"ctt expresso": "ctt_expresso", "ctt express": "ctt_expresso"}, "ctt"
    ),
)

EXPRESSO_SPEC: Final = CarrierSpec(
    carrier="ctt_expresso",
    brands=("ctt expresso", "ctt express", "ctt"),
    link_hosts=_HOSTS,
    link_params=_PARAMS,
    labels=_LABELS,
    phrases=_PHRASES,
)
