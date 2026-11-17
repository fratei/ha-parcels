"""GLS e-mails (FlexDeliveryService, ParcelShop), in many languages.

FlexDeliveryService e-mails announce today's or tomorrow's delivery with a
time window; ParcelShop e-mails say where to collect. Parcel numbers have
11 to 14 digits; the 8-character Track ID works too.
"""

from __future__ import annotations

from typing import Final

from ._common import CarrierSpec

SPEC: Final = CarrierSpec(
    carrier="gls",
    brands=("gls", "flexdeliveryservice", "gls parcelshop"),
    link_hosts=(
        "gls-group.eu",
        "gls-group.com",
        "gls-portugal.pt",
        "gls-spain.es",
        "gls-italy.com",
        "gls-info.nl",
        "gls-pakete.de",
        "gls-france.com",
        "gls.*",
    ),
    link_params=("match", "parcelno", "parcelnumber", "trackid", "numero", "match1"),
    labels=(
        "trackid",
        "track id",
        "track-id",
        "gls-paketnummer",
        "gls paketnummer",
        "numero de bulto",
        "numero de volume",
        "parcel id",
        "pakketnummer gls",
    ),
)
