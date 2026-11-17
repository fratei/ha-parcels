"""Tests for the header-only prefilter."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from custom_components.parcels.parsers.base import MailMessage
from custom_components.parcels.parsers.prefilter import (
    MARKETING_PHRASES,
    STRONG_KEYWORDS,
    WEAK_KEYWORDS,
    is_candidate,
)

UNKNOWN = "news@store.example"

POSITIVES: dict[str, list[str]] = {
    "en": [
        "Your order #1001 is confirmed",
        "Order confirmation",
        "Thanks for your order!",
        "Your order has shipped",
        "Your package has been dispatched",
        "Shipping confirmation",
        "Your parcel is on its way",
        "Your order is out for delivery",
        "Your package was delivered",
        "Delivery attempt failed",
        "We missed you",
        "Your parcel is ready for pickup",
        "Your parcel is waiting in the locker",
        "Track your package",
        "Tracking number for your order",
        "Your shipment is delayed",
        "Your return has been received",
        "Refund for order 123-1234567-1234567",
    ],
    "pt": [
        "Confirmação de encomenda n.º 1042",
        "Pedido confirmado",
        "A sua encomenda foi enviada",
        "Seu pedido foi enviado",
        "A sua encomenda está a caminho",
        "Em distribuição",
        "A sua encomenda foi entregue",
        "Tentativa de entrega sem sucesso",
        "A sua encomenda está disponível para levantamento",
        "O seu objeto está disponível no cacifo",
        "Acompanhe a sua encomenda",
        "Código de rastreio",
        "A sua encomenda está atrasada",
        "Reembolso da sua encomenda",
    ],
    "es": [
        "Confirmación de pedido",
        "Gracias por tu pedido",
        "Tu pedido ha sido enviado",
        "Tu paquete está en camino",
        "En reparto",
        "Tu pedido ha sido entregado",
        "Intento de entrega fallido",
        "Tu paquete está listo para recoger",
        "Número de seguimiento",
        "Tu envío está retrasado",
        "Reembolso de tu pedido",
    ],
    "de": [
        "Bestellbestätigung",
        "Ihre Bestellung wurde versandt",
        "Versandbestätigung",
        "Ihr Paket ist unterwegs",
        "Ihr Paket wird heute zugestellt",
        "Ihr Paket wurde zugestellt",
        "Zustellversuch",
        "Ihr Paket liegt zur Abholung bereit",
        "Sendungsverfolgung",
        "Ihre Sendung verzögert sich",
        "Rückerstattung für Ihre Bestellung",
    ],
    "fr": [
        "Confirmation de commande",
        "Merci pour votre commande",
        "Votre commande a été expédiée",
        "Votre colis est en route",
        "En cours de livraison",
        "Votre colis a été livré",
        "Tentative de livraison",
        "Votre colis est disponible en point relais",
        "Suivi de votre colis",
        "Votre colis est retardé",
        "Remboursement de votre commande",
    ],
    "it": [
        "Conferma d'ordine",
        "Grazie per il tuo ordine",
        "Il tuo ordine è stato spedito",
        "Il tuo pacco è in viaggio",
        "In consegna",
        "Il tuo pacco è stato consegnato",
        "Tentativo di consegna",
        "Il tuo pacco è pronto per il ritiro",
        "Traccia il tuo pacco",
        "La tua spedizione è in ritardo",
        "Rimborso del tuo ordine",
    ],
    "nl": [
        "Orderbevestiging",
        "Bedankt voor je bestelling",
        "Je bestelling is verzonden",
        "Je pakket is onderweg",
        "Je pakket wordt vandaag bezorgd",
        "Je pakket is bezorgd",
        "Bezorgpoging mislukt",
        "Je pakket ligt klaar om op te halen",
        "Volg je pakket",
        "Je zending is vertraagd",
        "Terugbetaling van je bestelling",
    ],
}

NEGATIVES: dict[str, list[str]] = {
    "en": [
        "Free shipping on all orders this weekend",
        "Order now and save 20%",
        "Black Friday deals: free delivery",
        "Last chance: 50% off",
        "Your weekly newsletter",
        "New arrivals just landed",
        "Meeting notes",
        "Your invoice is ready",
        "Password reset",
    ],
    "pt": [
        "Portes grátis em todas as encomendas",
        "Encomende já e poupe",
        "Promoções de Natal com entrega gratuita",
        "Novidades da semana",
        "Fatura disponível",
    ],
    "es": [
        "Envío gratis en todos los pedidos",
        "Pídelo ya",
        "Ofertas exclusivas",
        "Rebajas de invierno",
        "Tu factura está disponible",
    ],
    "de": [
        "Kostenloser Versand für alle Bestellungen",
        "Jetzt bestellen und sparen",
        "Angebote der Woche",
        "Newsletter November",
        "Ihre Rechnung",
    ],
    "fr": [
        "Livraison gratuite sur toute la boutique",
        "Commandez maintenant",
        "Soldes d'hiver",
        "Nouveautés de la semaine",
        "Votre facture",
    ],
    "it": [
        "Spedizione gratuita su tutti gli ordini",
        "Ordina ora",
        "Saldi invernali",
        "Offerte della settimana",
        "La tua fattura",
    ],
    "nl": [
        "Gratis verzending op alle bestellingen",
        "Bestel nu",
        "Uitverkoop",
        "Aanbiedingen van de week",
        "Je factuur",
    ],
}


@pytest.mark.parametrize(
    "subject",
    [
        pytest.param(s, id=f"{lang}-{s}")
        for lang, items in POSITIVES.items()
        for s in items
    ],
)
def test_shipping_subjects_pass(subject: str) -> None:
    """Order and shipping subjects pass in every language."""
    assert is_candidate(UNKNOWN, subject)


@pytest.mark.parametrize(
    "subject",
    [
        pytest.param(s, id=f"{lang}-{s}")
        for lang, items in NEGATIVES.items()
        for s in items
    ],
)
def test_advertising_and_other_subjects_fail(subject: str) -> None:
    """Offers, newsletters and unrelated subjects are filtered out."""
    assert not is_candidate(UNKNOWN, subject)


def test_case_and_accents_are_ignored() -> None:
    """Keywords match regardless of case and accents."""
    assert is_candidate(UNKNOWN, "SUA ENCOMENDA FOI ENTREGUE")
    assert is_candidate(UNKNOWN, "Votre colis a ete livre")
    assert is_candidate(UNKNOWN, "ihr paket wurde zugestellt")


def test_keywords_match_whole_words_only() -> None:
    """A keyword inside another word does not count."""
    assert not is_candidate(UNKNOWN, "Upstream release notes")
    assert not is_candidate(UNKNOWN, "Gratitude journal")


@pytest.mark.parametrize(
    "sender",
    [
        "store@shop.app",
        "mailer@shopify.com",
        "Amazon <auto-confirm@amazon.es>",
        "shipment-tracking@amazon.co.uk",
        "info@ctt.pt",
        "noreply@news.dpd.pt",
        "amazon.de",
    ],
)
def test_known_senders_always_pass(sender: str) -> None:
    """Known merchants, platforms and carriers pass whatever the subject."""
    assert is_candidate(sender, "Hello")


def test_trusted_domains_pass() -> None:
    """Domains the user trusts pass, also from a subdomain."""
    assert not is_candidate("hello@store.example", "Hi")
    assert is_candidate("hello@store.example", "Hi", trusted=["store.example"])
    assert is_candidate("Shop <hi@mail.store.example>", "Hi", trusted=["STORE.example"])
    assert not is_candidate("hello@other.example", "Hi", trusted=["store.example"])


def test_preview_counts() -> None:
    """The provider's preview is searched as well as the subject."""
    assert is_candidate(UNKNOWN, "Update", "Your parcel is out for delivery")
    assert is_candidate(UNKNOWN, "Info", "Pedido n.º 1042 - obrigado!")
    assert not is_candidate(UNKNOWN, "Update", "See you at the meeting")


def test_links_and_addresses_do_not_count() -> None:
    """Keywords inside URLs and e-mail addresses are ignored."""
    assert not is_candidate(UNKNOWN, "Hello", "https://example.com/tracking/123")
    assert not is_candidate(UNKNOWN, "Hello", "Write to delivery@example.com")


def test_order_number_patterns_pass() -> None:
    """Order-number labels pass even without other keywords."""
    assert is_candidate(UNKNOWN, "Bestellung Nr. 100234")
    assert is_candidate(UNKNOWN, "Commande : 123456")
    assert is_candidate(UNKNOWN, "Ordine #A1001")


def test_strong_keyword_beats_advertising() -> None:
    """A real status phrase passes even next to an offer."""
    assert is_candidate(UNKNOWN, "Your order has shipped - free returns for 30 days")


def test_weak_keyword_with_marketing_fails() -> None:
    """Weak keywords next to sale words or a percentage don't pass."""
    assert is_candidate(UNKNOWN, "Your parcel")
    assert not is_candidate(UNKNOWN, "Your parcel: 20% off your next order")
    assert not is_candidate(UNKNOWN, "Parcel deals this week")


def test_newsletter_fixture(load_eml: Callable[..., MailMessage]) -> None:
    """The newsletter fixture is filtered out by its headers."""
    message = load_eml("common/newsletter.eml")
    assert not is_candidate(message.sender, message.subject)


def test_shipping_fixtures(load_eml: Callable[..., MailMessage]) -> None:
    """The shipping fixtures pass on their headers alone."""
    for name in ("small_shop_ctt", "german_shop_dhl", "order_confirmation"):
        message = load_eml(f"common/{name}.eml")
        assert is_candidate(message.sender, message.subject), name


def test_keyword_tables_cover_all_languages() -> None:
    """Every supported language has keyword lists."""
    for table in (STRONG_KEYWORDS, WEAK_KEYWORDS, MARKETING_PHRASES):
        assert set(table) == {"pt", "es", "en", "de", "fr", "it", "nl"}
