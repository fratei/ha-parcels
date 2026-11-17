"""Tests for Authentication-Results parsing and sender verification."""

from __future__ import annotations

import pytest

from custom_components.parcels.parsers.auth import (
    parse_authentication_results,
    verify_sender,
)
from custom_components.parcels.parsers.base import MailMessage
from custom_components.parcels.parsers.normalize import message_from_bytes

GMAIL_AMAZON = (
    "mx.google.com;\n"
    "       dkim=pass header.i=@amazon.es header.s=abc header.b=Xy12;\n"
    "       spf=pass (google.com: domain of 20261117@bounces.amazon.es designates"
    " 54.240.1.1 as permitted sender) smtp.mailfrom=20261117@bounces.amazon.es;\n"
    "       dmarc=pass (p=QUARANTINE sp=QUARANTINE dis=NONE) header.from=amazon.es"
)
OUTLOOK_AMAZON = (
    "spf=pass (sender IP is 54.240.1.1) smtp.mailfrom=bounces.amazon.es; dkim=pass"
    " (signature was verified) header.d=amazon.es;dmarc=pass action=none"
    " header.from=amazon.es;compauth=pass reason=100"
)


def _message(
    sender: str,
    *auth_headers: str,
    provider: str = "google",
    extra_headers: str = "",
    html: str = "<p>Hello</p>",
) -> MailMessage:
    """Build a message with the given Authentication-Results, topmost first."""
    lines = [f"Authentication-Results: {value}" for value in auth_headers]
    raw = (
        "\n".join(
            [
                "Return-Path: <bounce@example.net>",
                *lines,
                f"From: {sender}",
                "To: Alex Doe <alex@example.com>",
                "Subject: Your order has shipped",
                "Date: Tue, 17 Nov 2026 09:12:00 +0000",
                "Message-ID: <20261117091200.a1@mail.example.net>",
                "MIME-Version: 1.0",
            ]
        )
        + "\n"
        + extra_headers
        + "Content-Type: text/html; charset=UTF-8\n\n"
        + html
        + "\n"
    )
    return message_from_bytes(
        raw.encode(), mailbox="alex@example.com", provider_id="t", provider=provider
    )


def test_parse_gmail_style() -> None:
    """Gmail headers carry the authserv-id and comments with ``;``."""
    auth = parse_authentication_results(GMAIL_AMAZON)
    assert auth.authserv_id == "mx.google.com"
    assert auth.dkim_pass_domains == ("amazon.es",)
    assert auth.dmarc_pass
    assert auth.dmarc_domain == "amazon.es"
    assert auth.spf_pass
    assert auth.spf_domain == "bounces.amazon.es"


def test_parse_outlook_style() -> None:
    """Outlook.com headers have no authserv-id."""
    auth = parse_authentication_results(OUTLOOK_AMAZON)
    assert auth.authserv_id is None
    assert auth.dkim_pass_domains == ("amazon.es",)
    assert auth.dmarc_pass
    assert auth.dmarc_domain == "amazon.es"
    assert auth.spf_pass
    assert auth.spf_domain == "bounces.amazon.es"


def test_parse_multiple_dkim_signatures() -> None:
    """Every passing DKIM signature counts; failing ones do not."""
    auth = parse_authentication_results(
        "mx.google.com; dkim=pass header.i=@shop.example header.s=s1;"
        " dkim=pass header.d=shopifyemail.com (a; comment=with ; semicolons);"
        " dkim=fail header.d=other.example; dkim=pass header.i=user@mail.shop.example;"
        " dmarc=fail (p=REJECT) header.from=shop.example"
    )
    assert auth.dkim_pass_domains == (
        "shop.example",
        "shopifyemail.com",
        "mail.shop.example",
    )
    assert not auth.dmarc_pass
    assert auth.dmarc_domain == "shop.example"
    assert not auth.spf_pass


@pytest.mark.parametrize("value", ["", "none", ";;;", "mx.google.com; none", "x=("])
def test_parse_garbage(value: str) -> None:
    """Empty or malformed values parse to an empty result."""
    auth = parse_authentication_results(value)
    assert auth.dkim_pass_domains == ()
    assert not auth.dmarc_pass
    assert not auth.spf_pass


def test_verify_gmail_known_sender() -> None:
    """An aligned DMARC pass on an allow-listed domain is trusted."""
    verdict = verify_sender(_message("Amazon.es <envio@amazon.es>", GMAIL_AMAZON))
    assert verdict.domain == "amazon.es"
    assert verdict.authenticated
    assert verdict.known
    assert verdict.method == "dmarc"
    assert verdict.reason == "ok"
    assert not verdict.shopify


def test_verify_outlook_known_sender() -> None:
    """Outlook.com's header without authserv-id is trusted for Microsoft."""
    message = _message(
        "Amazon.es <envio@amazon.es>", OUTLOOK_AMAZON, provider="microsoft"
    )
    verdict = verify_sender(message)
    assert verdict.authenticated
    assert verdict.known
    assert verdict.reason == "ok"


def test_verify_subdomain_alignment() -> None:
    """A DKIM pass for a subdomain aligns with the organizational domain."""
    message = _message(
        "Amazon <ship-confirm@marketplace.amazon.es>",
        "mx.google.com; dkim=pass header.d=bounces.amazon.es; spf=softfail",
    )
    verdict = verify_sender(message)
    assert verdict.domain == "marketplace.amazon.es"
    assert verdict.authenticated
    assert verdict.method == "dkim"
    assert verdict.reason == "ok"


def test_verify_misaligned_dkim() -> None:
    """A DKIM pass for an e-mail service provider does not authenticate."""
    message = _message(
        "Amazon <envio@amazon.es>",
        "mx.google.com; dkim=pass header.d=sendgrid.net;"
        " spf=pass smtp.mailfrom=bounce@sendgrid.net; dmarc=fail header.from=amazon.es",
    )
    verdict = verify_sender(message)
    assert not verdict.authenticated
    assert verdict.known
    assert verdict.reason == "not_aligned"


def test_verify_dmarc_fail_with_aligned_dkim() -> None:
    """An aligned DKIM pass still authenticates when DMARC is reported failed."""
    message = _message(
        "DHL <noreply@dhl.de>",
        "mx.google.com; dkim=pass header.i=@dhl.de; dmarc=fail header.from=dhl.de",
    )
    verdict = verify_sender(message)
    assert verdict.authenticated
    assert verdict.method == "dkim"


def test_verify_dmarc_fail() -> None:
    """A DMARC fail without an aligned DKIM pass is not authenticated."""
    message = _message(
        "DHL <noreply@dhl.de>",
        "mx.google.com; dkim=fail header.d=dhl.de; spf=pass smtp.mailfrom=dhl.de;"
        " dmarc=fail (p=REJECT) header.from=dhl.de",
    )
    verdict = verify_sender(message)
    assert not verdict.authenticated
    assert verdict.reason == "not_aligned"


def test_verify_spf_alone_is_not_enough() -> None:
    """SPF is not aligned with the From header and never authenticates."""
    message = _message(
        "CTT <noreply@ctt.pt>", "mx.google.com; spf=pass smtp.mailfrom=noreply@ctt.pt"
    )
    assert not verify_sender(message).authenticated


def test_verify_spoofed_brand() -> None:
    """A look-alike domain passing DMARC for itself is authenticated, not known."""
    message = _message(
        "DHL <dhl@dhl-tracking.example>",
        "mx.google.com; dkim=pass header.d=dhl-tracking.example;"
        " dmarc=pass header.from=dhl-tracking.example",
    )
    verdict = verify_sender(message)
    assert verdict.domain == "dhl-tracking.example"
    assert verdict.authenticated
    assert not verdict.known
    assert verdict.reason == "unknown_sender"


def test_verify_ignores_forged_lower_header() -> None:
    """Only the topmost Authentication-Results header counts."""
    message = _message(
        "CTT <noreply@ctt.pt>",
        "mx.google.com; dkim=none; spf=neutral; dmarc=none header.from=ctt.pt",
        "mx.google.com; dkim=pass header.d=ctt.pt; dmarc=pass header.from=ctt.pt",
    )
    verdict = verify_sender(message)
    assert not verdict.authenticated
    assert verdict.reason == "not_aligned"


@pytest.mark.parametrize(
    ("provider", "header"),
    [
        ("google", "mx.attacker.example; dkim=pass header.d=ctt.pt"),
        ("google", "dkim=pass header.d=ctt.pt; dmarc=pass header.from=ctt.pt"),
        ("microsoft", GMAIL_AMAZON.replace("amazon.es", "ctt.pt")),
        ("imap", "mx.google.com; dkim=pass header.d=ctt.pt"),
    ],
)
def test_verify_untrusted_authserv(provider: str, header: str) -> None:
    """Headers not written by the mailbox provider are ignored."""
    verdict = verify_sender(_message("CTT <noreply@ctt.pt>", header, provider=provider))
    assert not verdict.authenticated
    assert verdict.known
    assert verdict.reason == "untrusted_authserv"


def test_verify_without_header() -> None:
    """A message without Authentication-Results is not authenticated."""
    verdict = verify_sender(_message("CTT <noreply@ctt.pt>"))
    assert not verdict.authenticated
    assert verdict.method == "none"
    assert verdict.reason == "no_auth_header"


def test_verify_trusted_domains() -> None:
    """Domains trusted by the user count as known, including subdomains."""
    message = _message(
        "Loja Exemplo <encomendas@mail.loja-exemplo.example>",
        "mx.google.com; dkim=pass header.d=loja-exemplo.example;"
        " dmarc=pass header.from=mail.loja-exemplo.example",
    )
    assert verify_sender(message).reason == "unknown_sender"
    verdict = verify_sender(message, ["Loja-Exemplo.example"])
    assert verdict.authenticated
    assert verdict.known
    assert verdict.reason == "ok"


def test_verify_shopify_store_by_dkim() -> None:
    """A store e-mail signed by Shopify's DKIM key is known."""
    message = _message(
        "Loja Exemplo <loja@loja-exemplo.example>",
        "mx.google.com; dkim=pass header.i=@loja-exemplo.example header.s=shopify;"
        " dkim=pass header.i=@shopifyemail.com header.s=s1;"
        " dmarc=pass header.from=loja-exemplo.example",
    )
    verdict = verify_sender(message)
    assert verdict.authenticated
    assert verdict.known
    assert verdict.shopify
    assert verdict.reason == "ok"


def test_verify_shopify_links_alone_are_not_known() -> None:
    """Shopify links and headers mark a store but never make it known."""
    message = _message(
        "Loja Exemplo <loja@loja-exemplo.example>",
        "mx.google.com; dkim=pass header.d=loja-exemplo.example;"
        " dmarc=pass header.from=loja-exemplo.example",
        extra_headers="X-Shopify-Shop-Id: 12345\n",
        html=(
            '<a href="https://loja-exemplo.myshopify.com/orders/1">Order</a>'
            '<img src="https://cdn.shopify.com/s/files/logo.png">'
        ),
    )
    verdict = verify_sender(message)
    assert verdict.authenticated
    assert verdict.shopify
    assert not verdict.known
    assert verdict.reason == "unknown_sender"


def test_verify_shopify_link_only() -> None:
    """A single myshopify.com link sets the Shopify marker."""
    message = _message(
        "Loja Exemplo <loja@loja-exemplo.example>",
        "mx.google.com; dmarc=pass header.from=loja-exemplo.example",
        html='<a href="https://loja-exemplo.myshopify.com/x">Order</a>',
    )
    verdict = verify_sender(message)
    assert verdict.shopify
    assert not verdict.known


def test_verify_fixture(load_eml, verdict_for) -> None:
    """The shared fixtures produce Gmail-authenticated verdicts."""
    message = load_eml("common/small_shop_ctt.eml")
    verdict = verdict_for(message)
    assert verdict.authenticated
    assert verdict.reason == "unknown_sender"
    assert verdict_for(message, ["loja-exemplo.example"]).reason == "ok"
