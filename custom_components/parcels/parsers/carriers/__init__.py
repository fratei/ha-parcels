"""Parsers for carrier e-mails.

Each carrier module declares a :class:`~._common.CarrierSpec`: its names,
tracking-link hosts, labels and extra phrases. The shared engine in
``_common`` reads the e-mail with it: the kind of event, the tracking
numbers, the delivery date and window, when the event happened, the
pickup point and code, and the shop that sent the parcel.
"""

from __future__ import annotations

from datetime import tzinfo
import logging
from typing import Final

from ..base import MailMessage, ParseResult, SenderVerdict
from . import (
    correos_express,
    ctt,
    dhl,
    dpd,
    gls,
    inpost,
    mrw,
    nacex,
    paack,
    seur,
    ups,
)
from ._common import CarrierSpec, parse_with_spec

_LOGGER = logging.getLogger(__name__)

_SPECS: Final[dict[str, CarrierSpec]] = {
    "ctt": ctt.CTT_SPEC,
    "ctt_expresso": ctt.EXPRESSO_SPEC,
    "dpd": dpd.SPEC,
    "gls": gls.SPEC,
    "seur": seur.SPEC,
    "ups": ups.SPEC,
    "dhl": dhl.SPEC,
    "correos_express": correos_express.SPEC,
    "mrw": mrw.SPEC,
    "nacex": nacex.SPEC,
    "paack": paack.SPEC,
    "inpost": inpost.INPOST_SPEC,
    "vinted_go": inpost.VINTED_GO_SPEC,
}

CARRIER_PARSERS: frozenset[str] = frozenset(_SPECS)


def parse_carrier(
    message: MailMessage, verdict: SenderVerdict, tz: tzinfo, carrier: str
) -> ParseResult | None:
    """Parse an e-mail from a carrier, or return None when it isn't readable.

    ``carrier`` is the parser id from the sender allow-list (one of
    :data:`CARRIER_PARSERS`). The result's shipments may name another
    carrier when the e-mail says so (a CTT e-mail about a CTT Expresso
    parcel, a Vinted e-mail about a parcel carried by CTT).
    """
    spec = _SPECS.get(carrier)
    if spec is None:
        return None
    try:
        return parse_with_spec(message, verdict, tz, spec, carrier)
    except Exception as err:  # one bad e-mail must not stop a sync
        # Only the exception type: its message could quote the e-mail.
        _LOGGER.warning("Carrier parser %s failed: %s", carrier, type(err).__name__)
        return None
