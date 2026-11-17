"""UPS e-mails: "UPS Update", UPS My Choice windows and Access Point pickups.

"UPS Update: Package Scheduled for Delivery Today" with an estimated
window, "Your package was delivered", "Your package is at a UPS Access
Point" and delay notices. Numbers are 1Z codes with a check digit.
"""

from __future__ import annotations

from typing import Final

from ...const import MailKind
from ._common import CarrierSpec

SPEC: Final = CarrierSpec(
    carrier="ups",
    brands=("ups", "united parcel service", "ups my choice"),
    link_hosts=("ups.com",),
    link_params=("tracknum", "tracknums", "inquirynumber1", "trackingnumber"),
    labels=(
        "numero de rastreamento",
        "rastreamento",
        "numero di tracking",
        "numero de tracking",
        "n.o de seguimento",
        "trackingnummer",
    ),
    phrases=(
        (MailKind.OUT_FOR_DELIVERY, "scheduled for delivery today"),
        (MailKind.OUT_FOR_DELIVERY, "arriving today"),
        (MailKind.OUT_FOR_DELIVERY, "entrega prevista para hoje"),
        (MailKind.OUT_FOR_DELIVERY, "entrega programada para hoy"),
        (MailKind.OUT_FOR_DELIVERY, "zustellung heute geplant"),
        (MailKind.OUT_FOR_DELIVERY, "livraison prevue aujourd'hui"),
        (MailKind.IN_TRANSIT, "scheduled for delivery"),
        (MailKind.DELAYED, "new delivery date"),
        (MailKind.DELAYED, "neues zustelldatum"),
        (MailKind.DELAYED, "nova data de entrega"),
        (MailKind.DELAYED, "nueva fecha de entrega"),
        (MailKind.DELAYED, "nouvelle date de livraison"),
        (MailKind.DELAYED, "nuova data di consegna"),
        (MailKind.DELAYED, "nieuwe bezorgdatum"),
    ),
)
