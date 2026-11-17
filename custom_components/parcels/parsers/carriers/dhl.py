"""DHL e-mails: Parcel Germany, DHL eCommerce/Parcel and DHL Express.

DHL Paket writes "Ihre DHL Sendung kommt heute" with a "Zeitfenster",
"liegt in der Packstation zur Abholung bereit" with an Abholcode, and
"wurde zugestellt". DHL Express uses 10-digit waybills (mod 7 check);
Paket uses JJD, JVGL and 00340434 (SSCC) numbers.
"""

from __future__ import annotations

from typing import Final

from ...const import MailKind
from ._common import CarrierSpec

SPEC: Final = CarrierSpec(
    carrier="dhl",
    brands=("dhl", "dhl express", "dhl paket", "dhl parcel", "deutsche post"),
    link_hosts=("dhl.*", "dhl.com", "dhlparcel.nl", "dhlparcel.*", "dpdhl.com"),
    link_params=(
        "piececode",
        "idc",
        "tracking-id",
        "awb",
        "barcode",
        "tc",
        "awbnumber",
        "trackingnumber",
    ),
    labels=(
        "numero de guia",
        "guia aerea",
        "numero de guia aerea",
        "waybill no",
        "dhl-sendungsnummer",
        "dhl sendungsnummer",
        "zendingcode",
        "numero de lettre de transport",
        "lettre de transport",
    ),
    phrases=(
        (MailKind.OUT_FOR_DELIVERY, "kommt heute"),
        (MailKind.OUT_FOR_DELIVERY, "wird heute zugestellt"),
        (MailKind.OUT_FOR_DELIVERY, "komt vandaag"),
        (MailKind.OUT_FOR_DELIVERY, "wordt vandaag bezorgd"),
        (MailKind.IN_TRANSIT, "kommt morgen"),
        (MailKind.IN_TRANSIT, "komt morgen"),
        (MailKind.READY_FOR_PICKUP, "zur abholung bereit"),
        (MailKind.READY_FOR_PICKUP, "liegt zur abholung"),
    ),
)
