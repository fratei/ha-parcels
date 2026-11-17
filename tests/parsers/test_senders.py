"""Tests for the known-sender table."""

from __future__ import annotations

import pytest

from custom_components.parcels.const import CARRIER_NAMES
from custom_components.parcels.parsers.senders import (
    KNOWN_SENDERS,
    lookup,
    organizational_domain,
)

PARSER_HINTS = {
    "amazon",
    "shop",
    "shopify",
    "ctt",
    "ctt_expresso",
    "dpd",
    "gls",
    "seur",
    "ups",
    "dhl",
    "correos_express",
    "mrw",
    "nacex",
    "paack",
    "inpost",
    "vinted_go",
}


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("amazon.es", "amazon.es"),
        ("bounces.amazon.es", "amazon.es"),
        ("marketplace.amazon.co.uk", "amazon.co.uk"),
        ("AMAZON.CO.UK.", "amazon.co.uk"),
        ("mail.loja.com.pt", "loja.com.pt"),
        ("notifications.cttexpress.com", "cttexpress.com"),
        ("a.b.c.example.com.br", "example.com.br"),
        ("example", "example"),
        ("", ""),
    ],
)
def test_organizational_domain(domain: str, expected: str) -> None:
    """The registrable domain respects multi-label public suffixes."""
    assert organizational_domain(domain) == expected


@pytest.mark.parametrize(
    ("domain", "name", "parser"),
    [
        ("amazon.es", "Amazon", "amazon"),
        ("shipment-tracking.amazon.de", "Amazon", "amazon"),
        ("amazon.co.uk", "Amazon", "amazon"),
        ("shop.app", "Shop", "shop"),
        ("email.shopify.com", "Shopify", "shopify"),
        ("ctt.pt", "CTT", "ctt"),
        ("notifications.cttexpress.com", "CTT Expresso", "ctt_expresso"),
        ("dpd.de", "DPD", "dpd"),
        ("gls-group.eu", "GLS", "gls"),
        ("seur.com", "SEUR", "seur"),
        ("ups.com", "UPS", "ups"),
        ("dhl.de", "DHL", "dhl"),
        ("correosexpress.com", "Correos Express", "correos_express"),
        ("mrw.es", "MRW", "mrw"),
        ("nacex.es", "Nacex", "nacex"),
        ("paack.co", "Paack", "paack"),
        ("inpost.pt", "InPost", "inpost"),
        ("correos.es", "Correos", None),
    ],
)
def test_lookup(domain: str, name: str, parser: str | None) -> None:
    """Domains and their subdomains resolve to the sender and parser hint."""
    info = lookup(domain)
    assert info is not None
    assert info.name == name
    assert info.parser == parser


def test_lookup_accepts_addresses() -> None:
    """An e-mail address is looked up by its domain."""
    info = lookup("ship-confirm@amazon.es")
    assert info is not None
    assert info.carrier == "amazon"


@pytest.mark.parametrize(
    "domain",
    [
        "",
        "example.com",
        "gmail.com",
        "dhl-tracking.example",
        "amazon.es.example",
        "notamazon.es",
        "myshopify.com",
    ],
)
def test_lookup_unknown(domain: str) -> None:
    """Look-alike and unrelated domains are not known."""
    assert lookup(domain) is None


def test_table_is_consistent() -> None:
    """Keys are organizational domains and hints and carriers are known ids."""
    for key, info in KNOWN_SENDERS.items():
        assert key == info.domain == organizational_domain(key)
        assert info.kind in {"merchant", "carrier", "platform"}
        assert info.parser is None or info.parser in PARSER_HINTS
        assert info.carrier is None or info.carrier in CARRIER_NAMES
    assert {info.parser for info in KNOWN_SENDERS.values()} - {None} == PARSER_HINTS
