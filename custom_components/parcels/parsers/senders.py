"""Known sender domains of merchants, carriers and platforms.

``KNOWN_SENDERS`` is a security boundary: an e-mail whose From domain is
listed here and passes DKIM or DMARC is applied automatically. Only list
domains that belong to the company, never shared or free mail domains.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SenderInfo:
    """A merchant, carrier or platform that sends shipping e-mails."""

    domain: str
    name: str
    kind: str
    carrier: str | None = None
    parser: str | None = None


# Multi-label public suffixes under which companies register domains.
PUBLIC_SUFFIXES: frozenset[str] = frozenset(
    {
        "ac.uk",
        "co.uk",
        "gov.uk",
        "ltd.uk",
        "me.uk",
        "net.uk",
        "org.uk",
        "plc.uk",
        "com.pt",
        "edu.pt",
        "gov.pt",
        "org.pt",
        "com.es",
        "edu.es",
        "gob.es",
        "nom.es",
        "org.es",
        "co.at",
        "or.at",
        "com.be",
        "com.br",
        "net.br",
        "org.br",
        "com.au",
        "net.au",
        "org.au",
        "co.jp",
        "ne.jp",
        "or.jp",
        "com.mx",
        "com.tr",
        "co.nz",
        "co.za",
        "com.cn",
        "net.cn",
        "org.cn",
        "com.hk",
        "com.sg",
        "co.in",
        "com.ar",
        "com.co",
        "com.pe",
        "com.pl",
        "net.pl",
        "co.il",
        "co.kr",
        "com.tw",
        "com.my",
        "co.id",
        "co.th",
        "com.ph",
        "com.vn",
        "com.gr",
        "com.cy",
        "com.mt",
        "com.ua",
        "com.ru",
        "com.sa",
        "com.eg",
        "com.uy",
        "com.ec",
        "com.ve",
    }
)


def _entries(
    domains: tuple[str, ...],
    name: str,
    kind: str,
    carrier: str | None = None,
    parser: str | None = None,
) -> dict[str, SenderInfo]:
    return {d: SenderInfo(d, name, kind, carrier, parser) for d in domains}


# Keyed by organizational domain. Domains marked "unverified" could not be
# confirmed as the company's own sending or web domain.
KNOWN_SENDERS: dict[str, SenderInfo] = {
    # Merchants
    **_entries(
        (
            "amazon.es",
            "amazon.com",
            "amazon.co.uk",
            "amazon.de",
            "amazon.fr",
            "amazon.it",
            "amazon.nl",
        ),
        "Amazon",
        "merchant",
        "amazon",
        "amazon",
    ),
    # Platforms
    **_entries(("shop.app",), "Shop", "platform", None, "shop"),
    **_entries(("shopify.com",), "Shopify", "platform", None, "shopify"),
    **_entries(
        (
            "vintedgo.com",  # unverified as a sender (its tracking site)
            "vinted.pt",  # unverified that it sends the locker e-mails
            "vinted.es",  # unverified that it sends the locker e-mails
            "vinted.fr",  # unverified that it sends the locker e-mails
            "vinted.de",  # unverified that it sends the locker e-mails
            "vinted.it",  # unverified that it sends the locker e-mails
            "vinted.nl",  # unverified that it sends the locker e-mails
            "vinted.be",  # unverified that it sends the locker e-mails
            "vinted.co.uk",  # unverified that it sends the locker e-mails
            "vinted.com",  # unverified that it sends the locker e-mails
        ),
        "Vinted Go",
        "platform",
        "vinted_go",
        "vinted_go",
    ),
    # Carriers with a dedicated parser
    **_entries(("ctt.pt",), "CTT", "carrier", "ctt", "ctt"),
    # CTT Expresso moved its notifications from no-reply@cttexpresso.pt to
    # no-reply@notifications.cttexpress.com.
    **_entries(
        ("cttexpresso.pt", "cttexpress.com"),
        "CTT Expresso",
        "carrier",
        "ctt_expresso",
        "ctt_expresso",
    ),
    **_entries(
        (
            "dpd.com",
            "dpd.pt",  # unverified (DPD Portugal uses dpd.com/pt)
            "dpd.de",
            "dpd.fr",
            "dpd.nl",
            "dpd.be",
            "dpd.at",
            "dpd.co.uk",
            "dpdgroup.com",
        ),
        "DPD",
        "carrier",
        "dpd",
        "dpd",
    ),
    **_entries(
        (
            "gls-group.eu",
            "gls-group.com",
            "gls-portugal.pt",  # unverified
            "gls-spain.es",  # unverified
            "gls-pakete.de",
            "gls-italy.com",
        ),
        "GLS",
        "carrier",
        "gls",
        "gls",
    ),
    **_entries(("seur.com",), "SEUR", "carrier", "seur", "seur"),
    **_entries(("ups.com",), "UPS", "carrier", "ups", "ups"),
    # DHL sends from dhl.com, its country domains and dpdhl.com.
    **_entries(
        (
            "dhl.com",
            "dhl.pt",
            "dhl.es",
            "dhl.de",
            "dhl.fr",
            "dhl.it",
            "dhl.nl",
            "dhl.be",
            "dhl.at",
            "dhl.co.uk",
            "dhlparcel.nl",
            "dpdhl.com",
        ),
        "DHL",
        "carrier",
        "dhl",
        "dhl",
    ),
    **_entries(
        ("correosexpress.com", "correosexpress.es"),
        "Correos Express",
        "carrier",
        "correos_express",
        "correos_express",
    ),
    **_entries(("mrw.es", "mrw.pt"), "MRW", "carrier", "mrw", "mrw"),
    **_entries(
        (
            "nacex.es",
            "nacex.com",  # unverified
            "nacex.pt",  # unverified
        ),
        "Nacex",
        "carrier",
        "nacex",
        "nacex",
    ),
    **_entries(("paack.co", "paack.app"), "Paack", "carrier", "paack", "paack"),
    **_entries(
        (
            "inpost.pt",
            "inpost.es",
            "inpost-spain.com",
            "inpost.pl",
            "inpost.co.uk",
            "inpost.eu",  # unverified
            "inpost.it",  # unverified
        ),
        "InPost",
        "carrier",
        "inpost",
        "inpost",
    ),
    # Carriers read by the generic parser
    **_entries(("correos.es",), "Correos", "carrier", "correos", None),
    **_entries(("fedex.com",), "FedEx", "carrier", "fedex", None),
    **_entries(("tnt.com",), "TNT", "carrier", "tnt", None),
    **_entries(("postnl.nl",), "PostNL", "carrier", "postnl", None),
    **_entries(("usps.com",), "USPS", "carrier", "usps", None),
    **_entries(("royalmail.com",), "Royal Mail", "carrier", "royal_mail", None),
    **_entries(("laposte.fr",), "La Poste", "carrier", "la_poste", None),
    **_entries(("colissimo.fr",), "Colissimo", "carrier", "colissimo", None),
    **_entries(("chronopost.fr",), "Chronopost", "carrier", "chronopost", None),
    **_entries(("deutschepost.de",), "Deutsche Post", "carrier", "deutsche_post", None),
    **_entries(
        ("poste.it", "posteitaliane.it"),
        "Poste Italiane",
        "carrier",
        "poste_italiane",
        None,
    ),
    **_entries(("bpost.be",), "bpost", "carrier", "bpost", None),
    **_entries(("brt.it",), "BRT", "carrier", "brt", None),
    **_entries(("evri.com",), "Evri", "carrier", "evri", None),
    **_entries(("myhermes.de", "hermesworld.com"), "Hermes", "carrier", "hermes", None),
    **_entries(
        ("mondialrelay.fr", "mondialrelay.es", "mondialrelay.com"),
        "Mondial Relay",
        "carrier",
        "mondial_relay",
        None,
    ),
    **_entries(("cainiao.com",), "Cainiao", "carrier", "cainiao", None),
    **_entries(("yunexpress.com",), "YunExpress", "carrier", "yunexpress", None),
    **_entries(("asendia.com",), "Asendia", "carrier", "asendia", None),
}


def organizational_domain(domain: str) -> str:
    """Return the registrable domain, e.g. ``amazon.co.uk``.

    The last two labels, or three when the last two form a known
    multi-label public suffix such as ``co.uk`` or ``com.pt``.
    """
    labels = [label for label in domain.strip().lower().rstrip(".").split(".") if label]
    if len(labels) <= 2:
        return ".".join(labels)
    if ".".join(labels[-2:]) in PUBLIC_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def lookup(domain: str) -> SenderInfo | None:
    """Return the known sender for a domain or any of its subdomains."""
    if not domain:
        return None
    return KNOWN_SENDERS.get(organizational_domain(domain.rpartition("@")[2]))


# Free mail providers: anyone can send from them, so they can't be trusted
# or ignored as a whole. Matched on the registrable domain or its first label.
FREE_MAIL_NAMES = frozenset(
    {
        "aol",
        "fastmail",
        "freenet",
        "gmail",
        "gmx",
        "googlemail",
        "hotmail",
        "icloud",
        "laposte",
        "libero",
        "live",
        "msn",
        "orange",
        "outlook",
        "proton",
        "protonmail",
        "sapo",
        "tuta",
        "tutanota",
        "wanadoo",
        "yahoo",
        "yandex",
        "ymail",
        "zoho",
    }
)
FREE_MAIL_DOMAINS = frozenset(
    {
        "free.fr",
        "mac.com",
        "mail.com",
        "mail.ru",
        "me.com",
        "pm.me",
        "t-online.de",
        "web.de",
    }
)


def is_free_mail(domain: str) -> bool:
    """Return True for a free mail provider, or for an empty domain."""
    org = organizational_domain(domain)
    if not org:
        return True
    return org in FREE_MAIL_DOMAINS or org.split(".", 1)[0] in FREE_MAIL_NAMES
