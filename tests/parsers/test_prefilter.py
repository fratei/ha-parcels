"""Tests for the header-only prefilter."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from custom_components.parcels.parsers.base import MailMessage
from custom_components.parcels.parsers.prefilter import (
    MARKETING_PHRASES,
    STRONG_KEYWORDS,
    WEAK_KEYWORDS,
    feedback_topic,
    has_news_words,
    has_shipping_words,
    invoice_topic,
    is_candidate,
    known_sender_subject,
    not_shipping_topic,
    sent_receipt,
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


@pytest.mark.parametrize(
    "subject",
    [
        "Recolha agendada para amanhã",
        "Data de recolha confirmada",
        "Your pickup date is confirmed",
        "Ihr Abholtermin",
        "Date d'enlèvement confirmée",
        "Ophaaldatum bevestigd",
    ],
)
def test_return_pickup_subjects_pass(subject: str) -> None:
    """A return's pickup date in the subject marks a parcel e-mail."""
    assert is_candidate(UNKNOWN, subject)


@pytest.mark.parametrize(
    "subject", ["Recolha de dados pessoais", "Bin collection day reminder"]
)
def test_other_collections_fail(subject: str) -> None:
    """Collections that aren't pickups (data, waste) don't count."""
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


@pytest.mark.parametrize(
    "text",
    [
        "A sua encomenda 001234567890 foi expedida do nosso armazém.",
        "Número de encomenda: 001234567890. A sua encomenda foi expedida.",
        "Ihre Sendungsnummer: 00340434161094042557",
        # Bodies are read further than subjects.
        "Olá Alex,\n" + "Novidades da semana. " * 150 + "A encomenda foi expedida.",
    ],
)
def test_body_shipping_words(text: str) -> None:
    """A body's status phrases and parcel-number labels count."""
    assert has_shipping_words(text)


@pytest.mark.parametrize(
    "text",
    [
        "Número de encomenda: 001234567890. Segue em anexo a fatura.",
        "Order number: 10045. Your invoice is attached.",
        "Bestellnummer 100234: Ihre Rechnung",
        "Numéro de commande 123456 : votre facture",
        "Free shipping on your next order!",
        "See https://example.com/out-for-delivery",
        # An account e-mail: the order was added to the account.
        "A encomenda 001234567890 foi associada à sua conta. "
        "Acompanhe a sua encomenda na área de cliente.",
        "Order 10045 was added to your account. Track your order in your account.",
    ],
)
def test_body_without_shipping_words(text: str) -> None:
    """An order-number label alone, an offer or a link doesn't count.

    Nor does a link to follow the order in the shop's account pages.
    """
    assert not has_shipping_words(text)


def test_body_account_link_beside_news() -> None:
    """Next to a status, a link to the account pages doesn't hide it."""
    assert has_shipping_words(
        "A sua encomenda 001234567890 foi expedida. "
        "Acompanhe a sua encomenda na área de cliente."
    )


# Subjects of a known sender's e-mails about something else than a parcel,
# though some name one: feedback and surveys, invoices, service notices,
# the sender's app, and offers to send parcels.
NOT_SHIPPING_SUBJECTS: dict[str, list[str]] = {
    "pt": [
        "A sua opinião conta",
        "Avalie a sua compra",
        "Como correu a sua entrega?",
        "Como correu a sua encomenda #1912?",
        "Diga-nos o que achou",
        "Gostou das velas?",
        "Inquérito de satisfação",
        "Fatura da sua encomenda",
        "Fatura da encomenda #1912",
        "Horário especial de Natal",
        "Cuidado com SMS falsos sobre encomendas",
        "Atualização dos termos e condições",
        "Envia as tuas encomendas a partir de 2,99 € com InPost",
    ],
    "es": [
        "Tu opinión nos importa",
        "¿Qué tal fue tu experiencia con Paack?",
        "Alex, ¿qué te ha parecido tu compra?",
        "Valora tu experiencia con Tienda Ejemplo",
        "Encuesta sobre tu envío",
        "Tu factura del pedido 1912345",
        "Horario especial de Navidad en MRW",
        "Descubre la nueva app de Correos Express",
        "Intentos de estafa con tu envío",
    ],
    "en": [
        "How did we do?",
        "Rate your delivery experience",
        "Review your recent order",
        "Tell us what you think of your parcel",
        "Your UPS invoice is ready",
        "Invoice for order #1912",
        "Holiday opening hours",
        "Beware of fake SMS about your parcel",
        "Our privacy policy is changing",
        "Ship more this holiday season with UPS",
    ],
    "de": [
        "Wie zufrieden waren Sie mit uns?",
        "Wie gefällt Ihnen Ihr Kauf?",
        "Bewerten Sie Ihre Bestellung",
        "Ihre Rechnung zur Online-Frankierung",
        "Ihre Rechnung zur Bestellung #100234",
        "Neue Öffnungszeiten Ihrer Filiale",
        "Achtung Betrug: gefälschte Paket-SMS",
        "Jetzt Pakete günstiger versenden",
    ],
    "fr": [
        "Donnez votre avis sur votre commande",
        "Votre avis compte",
        "Enquête de satisfaction",
        "Qu'en pensez-vous ?",
        "Votre facture pour la commande 123456",
        "Horaires d'ouverture des fêtes",
        "Attention aux arnaques au colis",
    ],
    "it": [
        "Com'è andata la consegna?",
        "Lascia una recensione del tuo ordine",
        "Cosa ne pensi del tuo acquisto?",
        "La tua fattura per l'ordine 123456",
        "Orari di apertura festivi",
        "Con l'app GLS decidi tu dove ricevere i tuoi pacchi",
    ],
    "nl": [
        "Hoe was je bezorging?",
        "Beoordeel je bestelling",
        "Wat vond je van je pakket?",
        "Vragenlijst over je zending",
        "Je factuur voor bestelling 123456",
        "Openingstijden tijdens de feestdagen",
    ],
}


@pytest.mark.parametrize(
    "subject",
    [
        pytest.param(subject, id=f"{language}-{index}")
        for language, subjects in NOT_SHIPPING_SUBJECTS.items()
        for index, subject in enumerate(subjects)
    ],
)
def test_known_sender_subject_about_something_else(subject: str) -> None:
    """Feedback, invoices, notices and offers aren't shipping e-mails."""
    assert not known_sender_subject(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "Recoge tus compras en un punto NACEX.shop",
        "Neu: die Post & DHL App",
        "UPS My Choice",
        "Black Friday CTT: 20% nos envios",
    ],
)
def test_known_sender_subject_without_shipping_words(subject: str) -> None:
    """A carrier's own name is no shipping word in its own e-mails."""
    assert not known_sender_subject(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "Your parcel is on its way",
        "Ihr Zustellcode",
        "A encomenda 001234567890 foi expedida do nosso armazém",
        "Order #1001 confirmed",
        "CTT: a sua encomenda",
        "Sendung von DHL",
        "Your DHL shipment",
        "Su envío MRW está en reparto",
        "Tu pedido llega hoy",
        "Wir versenden Ihre Bestellung heute",
        "Horario de entrega de tu pedido",
        "Avis d'expédition de votre commande",
        "Diga-nos quando quer receber a sua encomenda",
        "Your return is under review",
        "Review your delivery options",
        # A status beats a request for feedback.
        "Your order has shipped \u2013 rate your experience",
        "A sua encomenda foi entregue: avalie a entrega",
    ],
)
def test_known_sender_subject_about_a_parcel(subject: str) -> None:
    """Statuses, numbers and parcel words still make a shipping e-mail."""
    assert known_sender_subject(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "Review your delivery options",
        "Review and confirm your shipping address",
        "Review the delivery address for your parcel",
        "Your return is under review",
    ],
)
def test_reviewing_a_delivery_choice_is_no_feedback(subject: str) -> None:
    """Reviewing an address or options, or a review of a return, isn't feedback."""
    assert not not_shipping_topic(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "Como correu a sua entrega?",
        "Diga-nos o que achou",
        "A sua opinião é importante",
        "Avalie a entrega do objeto RR123456785PT",
        "Tu opinión nos importa",
        "How did we do?",
        "Wie zufrieden waren Sie mit uns?",
        "Votre avis compte",
        "Com'è andata la consegna?",
        "Hoe was je bezorging?",
        # A product's name in quotes doesn't hide the request.
        'Avalie a sua compra "Candeeiro Lua"',
    ],
)
def test_feedback_topic(subject: str) -> None:
    """Requests for feedback, even naming the parcel, in each language."""
    assert feedback_topic(subject)


@pytest.mark.parametrize(
    "subject",
    [
        # A status beats a request for feedback.
        "A sua encomenda foi entregue: avalie a entrega",
        "Your order has shipped \u2013 rate your experience",
        # A product's name in quotes isn't the e-mail's topic.
        'Ordered: "Customer Feedback Board" and 1 more item',
        'Ordered: "Customer Feedback Board Deluxe Edition wit...',
        "Bestellt: \u201eBewertungsbogen A4\u201c",
        "Commande : \u00ab Livre d'or avis clients \u00bb",
        "Comprovativo de entrega",
        "Your parcel is on its way",
        "Fatura eletrónica FT 2026A/100001",
    ],
)
def test_no_feedback_topic(subject: str) -> None:
    """A status, a quoted product name or an invoice is no request for feedback."""
    assert not feedback_topic(subject)


@pytest.mark.parametrize(
    "subject",
    [
        'Ordered: "Customer Feedback Board" and 1 more item',
        "Bestellt: \u201eUmfrage\u201c",
    ],
)
def test_quoted_product_name_is_no_topic(subject: str) -> None:
    """An order of a product named like a topic is still about the order."""
    assert not not_shipping_topic(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "Comprovativo do seu envio",
        "Comprovativo de envio RR123456785PT",
        "Talão de aceitação",
        "Justificante de admisión de tu envío",
        "Proof of postage",
        "Ihr Einlieferungsbeleg",
        "Preuve de dépôt de votre colis",
        "Ricevuta di accettazione",
        "Je verzendbewijs",
    ],
)
def test_sent_receipt(subject: str) -> None:
    """A carrier's receipt for a parcel handed in, in each language."""
    assert sent_receipt(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "Comprovativo de entrega",
        "Comprovativo de pagamento",
        "Your proof of delivery",
        "Your parcel is on its way",
        # A status beats the receipt.
        "Comprovativo de envio: a sua encomenda foi entregue",
    ],
)
def test_no_sent_receipt(subject: str) -> None:
    """Proof of delivery or of payment isn't a receipt for a parcel handed in."""
    assert not sent_receipt(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "Fatura eletrónica FT 2026A/100001",
        "Fatura da encomenda #1912",
        "Your UPS invoice is ready",
        "Ihre Rechnung zur Bestellung #100234",
        "Votre facture pour la commande 123456",
        "La tua fattura per l'ordine 123456",
    ],
)
def test_invoice_topic(subject: str) -> None:
    """Invoices, in each language."""
    assert invoice_topic(subject)


@pytest.mark.parametrize(
    "subject",
    [
        # Customs news beats the invoice.
        "Fatura de desalfandegamento",
        "Invoice for customs clearance",
        "Avalie a sua experiência com a fatura eletrónica",
        "Your parcel is on its way",
    ],
)
def test_no_invoice_topic(subject: str) -> None:
    """Customs news and requests for feedback aren't invoices."""
    assert not invoice_topic(subject)


@pytest.mark.parametrize(
    "text",
    [
        "A sua encomenda foi enviada.",
        "Ihre Sendung wurde zugestellt.",
        "O objeto aguarda o pagamento dos direitos aduaneiros.",
        "Your package is out for delivery today.",
        "Your order has been cancelled.",
        "Hello Alex,\n" + "Invoice details. " * 150 + "Your parcel was delivered.",
    ],
)
def test_news_words(text: str) -> None:
    """Statuses, customs and cancellations are news about a parcel."""
    assert has_news_words(text)


@pytest.mark.parametrize(
    "text",
    [
        "Sendungsnummer: 00340434618273591202\nBetrag: 6,99 EUR",
        "Invoice for shipment 1Z999AA10123456784. Tracking number: 1Z999AA10123456784",
        "Número de seguimento: RR123456785PT. Acompanhe o seu envio em ctt.pt.",
        "Order number: 10045. Your invoice is attached.",
        "Thank you for your order. Your invoice is attached.",
        "Obrigado pela sua compra. Segue em anexo a fatura.",
        "Your refund has been issued.",
    ],
)
def test_no_news_words(text: str) -> None:
    """Numbers' labels, links to follow a parcel, thanks and refunds aren't news."""
    assert not has_news_words(text)


# Subjects of e-mails that only give a delivery or pickup code, and of
# one-time password e-mails without a delivery word.
CODE_SUBJECTS: dict[str, tuple[tuple[str, ...], str]] = {
    "pt": (
        ("O seu código de entrega", "PIN de entrega", "Código de recolha"),
        "A sua palavra-passe única",
    ),
    "es": (
        ("Tu código de entrega", "Tu PIN de entrega", "Código de recogida"),
        "Tu contraseña de un solo uso",
    ),
    "en": (
        ("Your delivery code", "Your delivery PIN", "Your collection code"),
        "Your one-time password",
    ),
    "de": (
        ("Ihr Zustellcode", "Ihre Liefer-PIN", "Ihr Abholcode"),
        "Ihr Einmalpasswort",
    ),
    "fr": (
        ("Votre code de livraison", "Votre code de retrait"),
        "Votre code à usage unique",
    ),
    "it": (
        ("Il tuo codice di consegna", "Il tuo PIN di consegna"),
        "Il tuo codice monouso",
    ),
    "nl": (("Je bezorgcode", "Je ophaalcode"), "Je eenmalige code"),
}


@pytest.mark.parametrize("lang", CODE_SUBJECTS)
def test_delivery_code_subjects_pass(lang: str) -> None:
    """Delivery and pickup code labels pass, even next to an offer.

    A one-time password without a delivery word is a login or a bank code.
    """
    subjects, one_time_password = CODE_SUBJECTS[lang]
    for subject in subjects:
        assert is_candidate(UNKNOWN, subject, "-10%"), subject
    assert not is_candidate(UNKNOWN, one_time_password)


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
