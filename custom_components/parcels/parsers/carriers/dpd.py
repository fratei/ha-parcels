"""DPD e-mails (Predict, Pickup parcelshops), in many languages.

DPD Predict announces the delivery day and a one-hour window ("Your parcel
01234567890123 will be delivered today between 13:00 and 14:00"); Pickup
e-mails say a parcel waits at a parcelshop. Parcel numbers have 14 digits,
sometimes followed by a check character, often written in groups of four.
"""

from __future__ import annotations

from typing import Final

from ._common import CarrierSpec

SPEC: Final = CarrierSpec(
    carrier="dpd",
    brands=("dpd", "dpd predict", "dpd pickup", "dpdgroup"),
    link_hosts=("dpd.*", "dpdgroup.com", "mydpd.*", "dpd.co.uk", "dpd.com.pl"),
    link_params=("parcelnumber", "parcelno", "parcelnr", "pknr", "query", "parcel"),
    labels=(
        "dpd parcel number",
        "dpd-paketnummer",
        "paketscheinnummer",
        "n.o de encomenda dpd",
        "numero de parcel",
        "pakketnr",
    ),
)
