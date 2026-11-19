"""FedEx e-mails: shipment updates and FedEx Delivery Manager notices.

"Your package is scheduled for delivery" with a day and often a window,
"On FedEx vehicle for delivery", "Delivered" and "New delivery date"
notices. Numbers are 12-digit Express or Ground codes (and the 15-, 20-
and 22-digit Ground forms), checked by ``tracking.validate_tracking_number``.
"""

from __future__ import annotations

from typing import Final

from ...const import MailKind
from ._common import CarrierSpec
from ._phrases import NEW_DATE_PHRASES, SCHEDULED_PHRASES

SPEC: Final = CarrierSpec(
    carrier="fedex",
    brands=("fedex", "federal express", "fedex delivery manager"),
    link_hosts=("fedex.com",),
    link_params=("trknbr", "tracknumbers", "tracknumber", "trackingnumber"),
    labels=(
        "numero de rastreamento",
        "numero di tracking",
        "numero de tracking",
        "fedex tracking number",
        "master tracking number",
    ),
    phrases=(
        (MailKind.OUT_FOR_DELIVERY, "scheduled for delivery today"),
        (MailKind.OUT_FOR_DELIVERY, "on fedex vehicle for delivery"),
        (MailKind.OUT_FOR_DELIVERY, "on a fedex vehicle for delivery"),
        (MailKind.OUT_FOR_DELIVERY, "no veiculo da fedex para entrega"),
        (MailKind.OUT_FOR_DELIVERY, "no veiculo fedex para entrega"),
        (MailKind.OUT_FOR_DELIVERY, "en el vehiculo de fedex"),
        (MailKind.OUT_FOR_DELIVERY, "im fedex fahrzeug"),
        (MailKind.OUT_FOR_DELIVERY, "im fedex-fahrzeug"),
        (MailKind.OUT_FOR_DELIVERY, "dans le vehicule fedex"),
        (MailKind.OUT_FOR_DELIVERY, "sul veicolo fedex"),
        (MailKind.OUT_FOR_DELIVERY, "in het fedex-voertuig"),
        (MailKind.OUT_FOR_DELIVERY, "in het fedex voertuig"),
        *((MailKind.IN_TRANSIT, phrase) for phrase in SCHEDULED_PHRASES),
        *((MailKind.DELAYED, phrase) for phrase in NEW_DATE_PHRASES),
    ),
)
