"""Tracking numbers: normalisation, check digits, detection and links.

Public API (stable; used by the parsers, the engine and the AI checks):
``normalize_tracking_number``, ``s10_check_digit``, ``is_s10``,
``ups_check_digit_ok``, ``check_digit_ok``, ``validate_tracking_number``,
``detect_carrier``, ``find_tracking_numbers``, ``numbers_from_url`` and
``tracking_url``, plus the tables ``S10_CARRIERS``, ``CARRIER_PATTERNS``
and ``URL_TEMPLATES``.

Everything here is pure: links are taken apart, never fetched.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import re
from urllib.parse import parse_qsl, quote, unquote, urlsplit

from .codes import ALL_CODE_LABELS, LOCKER_CODE_LABELS
from .lang import fold_aligned
from .senders import lookup, organizational_domain

FALLBACK_URL = "https://t.17track.net/en#nums={n}"

# Longest normalised number accepted anywhere.
MAX_NUMBER_CHARS = 40
# Only this much of a text is scanned for numbers.
MAX_SCAN_CHARS = 100_000
# Longest link taken apart by numbers_from_url.
MAX_URL_CHARS = 4096
# How far before a number its context words are looked for.
CONTEXT_CHARS = 120

_STRIP_RE = re.compile(r"[\s\-.\u00ad\u200b-\u200d\u2010-\u2015\u2060\u2212\ufeff]")
_S10_RE = re.compile(r"[A-Z]{2}\d{9}[A-Z]{2}")
_UPS_RE = re.compile(r"1Z[0-9A-Z]{15}\d")
_SSCC_RE = re.compile(r"00\d{18}")
_USPS_RE = re.compile(r"9[2-5]\d{20}")
_FEDEX96_RE = re.compile(r"96\d{20}")
_GENERIC_RE = re.compile(r"[0-9A-Z]{8,35}")
_S10_WEIGHTS = (8, 6, 4, 2, 3, 5, 9, 7)
_FEDEX_WEIGHTS = (3, 1, 7)

# Postal operators (and TNT) that use UPU S10 numbers for tracked items.
S10_CARRIERS: frozenset[str] = frozenset(
    {
        "asendia",
        "bpost",
        "cainiao",
        "chronopost",
        "colissimo",
        "correos",
        "ctt",
        "ctt_expresso",
        "deutsche_post",
        "dhl",
        "la_poste",
        "poste_italiane",
        "postnl",
        "royal_mail",
        "tnt",
        "usps",
        "yunexpress",
    }
)


@dataclass(frozen=True, slots=True)
class TrackingMatch:
    """A tracking number found in text or in a link.

    ``validated`` is True when the number identifies itself: a check digit
    passed (UPU S10, UPS 1Z, SSCC, USPS, FedEx, or DHL Express with DHL
    context) or the format carries a carrier prefix (Amazon TBA, DHL JJD,
    PostNL 3S...). It is False for numbers accepted only because a tracking
    word or a carrier name stood next to them.
    """

    number: str
    carrier: str | None
    validated: bool


def normalize_tracking_number(value: str) -> str:
    """Uppercase a tracking number and drop spaces, dashes and dots."""
    return _STRIP_RE.sub("", value).upper()


def s10_check_digit(serial: str) -> int:
    """Return the UPU S10 check digit for an 8-digit serial number.

    Raises ValueError when ``serial`` is not exactly eight digits.
    """
    total = sum(int(d) * w for d, w in zip(serial, _S10_WEIGHTS, strict=True))
    check = 11 - total % 11
    if check == 10:
        return 0
    if check == 11:
        return 5
    return check


def is_s10(number: str) -> bool:
    """Return True for a valid UPU S10 number such as RR123456785PT."""
    number = normalize_tracking_number(number)
    if not _S10_RE.fullmatch(number):
        return False
    return s10_check_digit(number[2:10]) == int(number[10])


def ups_check_digit_ok(number: str) -> bool:
    """Return True when a UPS 1Z number has a valid check digit."""
    number = normalize_tracking_number(number)
    if not _UPS_RE.fullmatch(number):
        return False
    total = 0
    for pos, char in enumerate(number[2:17], start=1):
        value = int(char) if char.isdigit() else (ord(char) - 63) % 10
        total += value * (2 if pos % 2 == 0 else 1)
    return (10 - total % 10) % 10 == int(number[17])


def _gs1_ok(number: str) -> bool:
    """GS1 mod 10 (weights 3, 1 from the right), as in SSCC and USPS IMpb."""
    if len(number) < 2 or not number.isdigit():
        return False
    body = number[-2::-1]
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(body))
    return (10 - total % 10) % 10 == int(number[-1])


def _mod7_ok(number: str) -> bool:
    """DHL Express waybill: the last digit is the others modulo 7."""
    return (
        len(number) > 1 and number.isdigit() and int(number[:-1]) % 7 == int(number[-1])
    )


def _fedex12_ok(number: str) -> bool:
    """FedEx Express 12-digit numbers: weights 3, 1, 7, modulo 11."""
    if len(number) != 12 or not number.isdigit():
        return False
    total = sum(int(d) * _FEDEX_WEIGHTS[i % 3] for i, d in enumerate(number[:11]))
    return total % 11 % 10 == int(number[11])


def _fedex96_ok(number: str) -> bool:
    """FedEx Ground 96 numbers: GS1 mod 10 over the last 15 digits."""
    return len(number) == 22 and _gs1_ok(number[7:])


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(f"^(?:{pattern})$")


# Formats per carrier, matched against normalised numbers, each with its
# check-digit test when the format has one. UPU S10 numbers are handled
# separately for the carriers in S10_CARRIERS.
_RULES: dict[str, tuple[tuple[str, Callable[[str], bool] | None], ...]] = {
    "amazon": (
        (r"TBA\d{12}", None),
        (r"[A-Z]{2}\d{10,12}", None),  # unverified: Amazon Logistics in Europe
    ),
    "ups": ((r"1Z[0-9A-Z]{15}\d", ups_check_digit_ok),),
    "dhl": (
        (r"\d{10,11}", _mod7_ok),  # DHL Express waybill
        (r"\d{12}", None),  # DHL Paket
        (r"\d{20}", None),  # DHL Paket (SSCC)
        (r"(?:JJD|JVGL)\d{9,20}", None),
        (r"JD\d{18}", None),
        (r"GM\d{16,22}", None),  # DHL eCommerce
        (r"[A-Z]{2,4}\d{10,20}", None),  # unverified: DHL eCommerce
    ),
    "dpd": ((r"\d{14}", None), (r"\d{14}[0-9A-Z]", None)),
    "gls": ((r"\d{11,14}", None), (r"[0-9A-Z]{8}", None)),
    "seur": ((r"[0-9A-Z]{8,22}", None),),
    "ctt": ((r"[0-9A-Z]{10,20}", None),),
    "ctt_expresso": ((r"[0-9A-Z]{10,20}", None),),
    "correos": ((r"P[A-Z][0-9A-Z]{14,21}", None),),
    "correos_express": ((r"\d{10,23}", None),),
    "mrw": ((r"\d{8,14}", None),),
    "nacex": ((r"\d{4}/?\d{6,10}", None), (r"\d{8,12}", None)),
    "paack": ((r"[0-9A-Z]{8,24}", None),),
    "inpost": ((r"\d{24}", None), (r"[0-9A-Z]{10,24}", None)),
    "vinted_go": (
        (r"(?:17|18)\d{14}", None),  # unverified
        (r"VGS[0-9A-Z]{6,30}", None),  # unverified
        (r"[0-9A-Z]{8,24}", None),
    ),
    "fedex": (
        (r"\d{12}", _fedex12_ok),
        (r"\d{15}", _gs1_ok),  # FedEx Ground
        (r"96\d{20}", _fedex96_ok),  # FedEx Ground 96
        (r"9[2-5]\d{20}", _gs1_ok),  # FedEx Ground Economy (USPS barcode)
        (r"\d{20}", None),
        (r"DT\d{12}", None),  # door tag
    ),
    "tnt": ((r"\d{9}", None),),
    "mondial_relay": ((r"\d{8,12}", None),),
    "postnl": ((r"3S[A-Z]{4}\d{6,11}", None),),
    "la_poste": ((r"\d[A-Z]\d{11}", None),),
    "colissimo": ((r"\d[A-Z]\d{11}", None),),
    "usps": ((r"9[2-5]\d{20}", _gs1_ok), (r"\d{20}", None)),
    "evri": ((r"[A-Z][0-9A-Z]{15}", None),),  # unverified
    "hermes": ((r"\d{14}", None), (r"H\d{19}", None)),  # unverified
    "cainiao": ((r"LP\d{14}", None),),
    "yunexpress": ((r"YT\d{16}", None),),
}

_CARRIER_RULES: dict[
    str, tuple[tuple[re.Pattern[str], Callable[[str], bool] | None], ...]
] = {
    carrier: tuple((_compile(pattern), check) for pattern, check in rules)
    for carrier, rules in _RULES.items()
}

CARRIER_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    carrier: tuple(pattern for pattern, _ in rules)
    for carrier, rules in _CARRIER_RULES.items()
}

# Formats that name their carrier on their own, tried in order.
_DETECT_RULES: tuple[tuple[re.Pattern[str], str, Callable[[str], bool] | None], ...] = (
    (_compile(r"(?:JJD|JVGL)\d{9,20}|JD\d{18}|GM\d{16,22}"), "dhl", None),
    (_compile(r"00340434\d{12}"), "dhl", _gs1_ok),  # DHL Paket SSCC
    (_compile(r"TBA\d{12}"), "amazon", None),
    (_compile(r"3S[A-Z]{4}\d{6,11}"), "postnl", None),
    (_compile(r"LP\d{14}"), "cainiao", None),
    (_compile(r"YT\d{16}"), "yunexpress", None),
    (_compile(r"VGS[0-9A-Z]{6,30}"), "vinted_go", None),  # unverified
    (_FEDEX96_RE, "fedex", _fedex96_ok),
    (_USPS_RE, "usps", _gs1_ok),
)

# Carrier of an S10 number by its country code (the last two letters).
_S10_COUNTRIES: dict[str, str] = {
    "PT": "ctt",
    "ES": "correos",
    "FR": "la_poste",
    "DE": "deutsche_post",
    "GB": "royal_mail",
    "IT": "poste_italiane",
    "NL": "postnl",
    "BE": "bpost",
    "US": "usps",
    "WW": "tnt",
}

# Official tracking pages; {n} is the URL-encoded number. Carriers missing
# here (PostNL and Nacex need a postcode or an agency code, InPost and Paack
# have no stable public link) get the 17TRACK page.
URL_TEMPLATES: dict[str, str] = {
    "ctt": "https://www.ctt.pt/feapl_2/app/open/objectSearch/objectSearch.jspx?objects={n}",
    "ctt_expresso": "https://www.ctt.pt/feapl_2/app/open/objectSearch/objectSearch.jspx?objects={n}",
    "seur": "https://www.seur.com/livetracking/?segOnlineIdentificador={n}",
    "gls": "https://gls-group.com/track/{n}",
    "ups": "https://www.ups.com/track?tracknum={n}",
    "mrw": "https://www.mrw.es/seguimiento_envios/MRW_resultados_consultas.asp?modo=nacional&envio={n}",
    "correos_express": "https://s.correosexpress.com/SeguimientoSinCP?request_locale=es_ES&shippingNumber={n}",
    # unverified: the templates below follow the carriers' public tracking
    # pages but could not be confirmed with a live number.
    "dhl": "https://www.dhl.com/global-en/home/tracking/tracking-parcel.html?submit=1&tracking-id={n}",
    "deutsche_post": "https://www.dhl.com/global-en/home/tracking/tracking-parcel.html?submit=1&tracking-id={n}",
    "dpd": "https://tracking.dpd.de/status/en_US/parcel/{n}",
    "fedex": "https://www.fedex.com/fedextrack/?trknbr={n}",
    "correos": "https://www.correos.es/es/es/herramientas/localizador/envios/detalle?tracking-number={n}",
    "usps": "https://tools.usps.com/go/TrackConfirmAction?tLabels={n}",
    "royal_mail": "https://www.royalmail.com/track-your-item#/tracking-results/{n}",
    "la_poste": "https://www.laposte.fr/outils/suivre-vos-envois?code={n}",
    "colissimo": "https://www.laposte.fr/outils/suivre-vos-envois?code={n}",
    "chronopost": "https://www.chronopost.fr/tracking-no-cms/suivi-page?listeNumerosLT={n}",
    "poste_italiane": "https://www.poste.it/cerca/index.html#/risultati-spedizioni/{n}",
    "bpost": "https://track.bpost.cloud/btr/web/#/search?itemCode={n}&lang=en",
    "vinted_go": "https://vintedgo.com/en/tracking/{n}",
    "tnt": "https://www.tnt.com/express/en_gc/site/shipping-tools/tracking.html?searchType=con&cons={n}",
}

# Link hosts that are tracking pages although they don't send e-mail:
# organizational domain -> carrier (None for multi-carrier trackers).
TRACKING_HOSTS: dict[str, str | None] = {
    "17track.net": None,
    "aftership.com": None,
    "parcelsapp.com": None,
    "trackingmore.com": None,
    "bpost.cloud": "bpost",
    "dhlparcel.nl": "dhl",
    "gls-pakete.de": "gls",
    "vintedgo.com": "vinted_go",
    "yuntrack.com": "yunexpress",
}

# Query parameters that hold a tracking number on any site.
_STRONG_PARAMS = frozenset(
    {
        "awb",
        "consignmentnumber",
        "itemcode",
        "listenumeroslt",
        "nums",
        "parcel_number",
        "parcelnumber",
        "piececode",
        "segonlineidentificador",
        "sendungsnummer",
        "shippingnumber",
        "tlabels",
        "trackid",
        "tracking-id",
        "tracking-number",
        "tracking_code",
        "tracking_id",
        "tracking_number",
        "trackingcode",
        "trackingid",
        "trackingnumber",
        "trackingnumbers",
        "tracknum",
        "tracknumber",
        "tracknumbers",
        "tracknums",
        "trknbr",
    }
)
# Query parameters that hold a tracking number on carrier tracking sites.
_WEAK_PARAMS = frozenset(
    {
        "b",
        "barcode",
        "code",
        "codigo",
        "cons",
        "consignment",
        "envio",
        "id",
        "idc",
        "match",
        "n",
        "number",
        "numero",
        "object",
        "objects",
        "objeto",
        "parcel",
        "q",
        "query",
        "ref",
        "search",
        "sendung",
        "shipment",
        "t",
        "tracking",
    }
)


def _words(patterns: Iterable[str]) -> re.Pattern[str]:
    """Compile folded words or phrases into one whole-word regex."""
    ordered = sorted(patterns, key=len, reverse=True)
    body = "|".join(pattern.replace(" ", r"\s+") for pattern in ordered)
    return re.compile(rf"(?<![a-z0-9])(?:{body})(?![a-z0-9])")


# Words that introduce a tracking number (folded).
TRACKING_WORDS: tuple[str, ...] = (
    # en
    r"track\w*",
    "trace",
    "tracing",
    "waybill",
    "awb",
    r"consignment\w*",
    r"parcel\w*",
    r"package\w*",
    r"shipment\w*",
    "shipping",
    "barcode",
    # pt, es
    r"rastre\w*",
    r"seguiment\w*",
    r"seguimient\w*",
    "objeto",
    "objecto",
    r"remessa\w*",
    "envio",
    "envios",
    r"expedi\w*",
    "localizador",
    "albaran",
    r"bulto\w*",
    r"paquete\w*",
    r"pacote\w*",
    "volume",
    # de
    r"sendung\w*",
    r"paket\w*",
    "identcode",
    # fr
    r"suivie?",
    "colis",
    r"envoi\w*",
    "lettre de voiture",
    # it
    r"tracciament\w*",
    r"spedizion\w*",
    "collo",
    "colli",
    "pacco",
    "pacchi",
    "lettera di vettura",
    # nl
    r"zending\w*",
    r"pakket\w*",
    "volgnummer",
    r"verzend\w*",
)

# Words that introduce other numbers: orders, phones, accounts, money...
BLOCKING_WORDS: tuple[str, ...] = (
    # en
    r"order\w*",
    r"invoice\w*",
    "receipt",
    "phone",
    "telephone",
    "tel",
    "mobile",
    "fax",
    "hotline",
    "call",
    "customer",
    "account",
    "reference",
    "ref",
    "sku",
    "item",
    "article",
    "model",
    "ean",
    "isbn",
    "asin",
    "iban",
    "swift",
    "bic",
    "vat",
    "tax",
    "postcode",
    "zip",
    "postal",
    "total",
    "price",
    "amount",
    "card",
    r"contact\w*",
    "whatsapp",
    "sms",
    "voucher",
    "coupon",
    "pin",
    # pt, es
    r"pedido\w*",
    "fatura",
    "factura",
    "recibo",
    "telefone",
    "telemovel",
    "tlm",
    "telefono",
    "movil",
    "contribuinte",
    "nif",
    "nipc",
    "cif",
    "dni",
    "referencia",
    "entidade",
    "cliente",
    "montante",
    "valor",
    "importe",
    "nib",
    "cartao",
    "tarjeta",
    "cuenta",
    "conta",
    "artigo",
    "articulo",
    "codigo postal",
    "llame",
    "ligue",
    "contacto",
    "codigo de recogida",
    "codigo de recolha",
    "codigo de levantamento",
    r"n\.?\s*[o°]\.?\s*(?:da\s+|de\s+)?encomenda",
    r"numero\s+(?:da|de)\s+encomenda",
    r"encomenda\s+(?:n\.?\s*[o°]|#)",
    # de
    r"bestell\w*",
    r"auftrag\w*",
    r"rechnung\w*",
    "beleg",
    r"telefon\w*",
    "handy",
    r"mobil\w*",
    r"kunde\w*",
    "referenz",
    r"artikel\w*",
    "plz",
    "postleitzahl",
    "postnummer",
    "ust",
    r"steuer\w*",
    "betrag",
    "konto",
    "summe",
    "preis",
    r"anruf\w*",
    r"kontakt\w*",
    "gutschein",
    "abholcode",
    "abholnummer",
    # fr
    r"commande\w*",
    "facture",
    "recu",
    "portable",
    "client",
    "montant",
    "tva",
    "siret",
    "prix",
    "code postal",
    "appelez",
    "contactez",
    "code de retrait",
    # it
    "ordine",
    "ordini",
    "fattura",
    "ricevuta",
    "cellulare",
    "riferimento",
    "importo",
    "partita",
    "iva",
    "cap",
    "codice fiscale",
    "prezzo",
    "articolo",
    "chiami",
    r"contatt\w*",
    "codice di ritiro",
    # nl
    r"bestelling\w*",
    "bestelnummer",
    "factuur",
    r"telefoon\w*",
    "mobiel",
    r"klant\w*",
    "referentie",
    "bedrag",
    "btw",
    "kvk",
    "prijs",
    "bel",
    "ophaalcode",
)

# Carrier names (folded) -> carrier id; a name next to a number lets its
# carrier-specific format count.
CARRIER_WORDS: dict[str, str] = {
    "amazon logistics": "amazon",
    "asendia": "asendia",
    "bartolini": "brt",
    "bpost": "bpost",
    "brt": "brt",
    "cainiao": "cainiao",
    "chronopost": "chronopost",
    "colissimo": "colissimo",
    "correos": "correos",
    "correos express": "correos_express",
    "correosexpress": "correos_express",
    "ctt": "ctt",
    "ctt express": "ctt_expresso",
    "ctt expresso": "ctt_expresso",
    "deutsche post": "deutsche_post",
    "dhl": "dhl",
    "dpd": "dpd",
    "evri": "evri",
    "fedex": "fedex",
    "gls": "gls",
    "hermes": "hermes",
    "inpost": "inpost",
    "la poste": "la_poste",
    "mondial relay": "mondial_relay",
    "mrw": "mrw",
    "nacex": "nacex",
    "paack": "paack",
    "postnl": "postnl",
    "poste italiane": "poste_italiane",
    "royal mail": "royal_mail",
    "sda": "sda",
    "seur": "seur",
    "tnt": "tnt",
    "ups": "ups",
    "usps": "usps",
    "vinted go": "vinted_go",
    "yunexpress": "yunexpress",
}

_KEYWORD_RE = _words(TRACKING_WORDS)
# A PIN after its label ("delivery code", "Abholcode") is not a tracking number.
_BLOCKER_RE = _words((*BLOCKING_WORDS, *ALL_CODE_LABELS, *LOCKER_CODE_LABELS))
_CARRIER_WORD_RE = _words(re.escape(name).replace(r"\ ", " ") for name in CARRIER_WORDS)
# A possessive right before an order word: "tracking number of your order".
_POSSESSIVE_RE = re.compile(
    r"(?<![a-z])(?:(?:of|for|from|with)\s+your"
    r"|de\s+(?:tu|tus|su|sus|vuestro|vuestra|votre|vos)"
    r"|(?:da|de|na|para\s+a)\s+(?:sua|tua|vossa)"
    r"|(?:do|de|no|para\s+o)\s+(?:seu|teu|vosso)"
    r"|(?:del|dal|per\s+il|nel)\s+(?:tuo|suo|vostro)"
    r"|(?:della|dalla|per\s+la|nella)\s+(?:tua|sua|vostra)"
    r"|dell['\u2019]"
    r"|ihrer|ihres|deiner|deines"
    r"|(?:zu|aus|von|mit|fur)\s+(?:ihrer|ihrem|deiner|deinem)"
    r"|(?:van|voor|bij|uit)\s+(?:je|jouw|uw))\s*$"
)
# What may stand between two numbers of one list.
_LIST_GAP_RE = re.compile(r"\s*(?:[,;/|&+]|and|e|y|und|et|en|ed|o|or|ou|oder|of)?\s*")
_SPACES_RE = re.compile(r"\s+")


def _basic_ok(number: str) -> bool:
    """At least one digit and three different characters."""
    return any(c.isdigit() for c in number) and len(set(number) - {"/"}) >= 3


def _generic_ok(number: str) -> bool:
    """Shape of a tracking number of an unknown carrier."""
    if not _GENERIC_RE.fullmatch(number):
        return False
    return sum(c.isdigit() for c in number) >= 6 and len(set(number)) >= 3


def _rules_ok(
    number: str,
    rules: tuple[tuple[re.Pattern[str], Callable[[str], bool] | None], ...],
) -> bool:
    return any(
        pattern.fullmatch(number) and (check is None or check(number))
        for pattern, check in rules
    )


def check_digit_ok(number: str, carrier: str | None = None) -> bool:
    """Return True when the number carries a check digit and it is right.

    UPU S10, UPS 1Z, SSCC, USPS and FedEx Ground 96 numbers are checked on
    their own. DHL Express (mod 7) and FedEx 12/15-digit check digits only
    count when ``carrier`` names that carrier: random numbers pass them too
    often.
    """
    number = normalize_tracking_number(number)
    if is_s10(number) or ups_check_digit_ok(number):
        return True
    if (_SSCC_RE.fullmatch(number) or _USPS_RE.fullmatch(number)) and _gs1_ok(number):
        return True
    if _FEDEX96_RE.fullmatch(number) and _fedex96_ok(number):
        return True
    return any(
        check is not None and pattern.fullmatch(number) and check(number)
        for pattern, check in _CARRIER_RULES.get(carrier or "", ())
    )


def validate_tracking_number(number: str, carrier: str | None = None) -> bool:
    """Return True when a number fits the carrier's format and check digit.

    Without a carrier (or with "other") any known format, or the generic
    shape of 8-35 letters and digits with at least six digits, is accepted.
    Formats without a check digit are only checked for length and charset.
    """
    number = normalize_tracking_number(number)
    if not number or len(number) > MAX_NUMBER_CHARS:
        return False
    if carrier in ("", "other"):
        carrier = None
    if _S10_RE.fullmatch(number):
        return is_s10(number) and (carrier is None or carrier in S10_CARRIERS)
    if number.startswith("1Z"):
        return ups_check_digit_ok(number) and carrier in (None, "ups")
    if not _basic_ok(number):
        return False
    if carrier is None:
        return _generic_ok(number) or any(
            _rules_ok(number, rules) for rules in _CARRIER_RULES.values()
        )
    rules = _CARRIER_RULES.get(carrier)
    if not rules:
        return _generic_ok(number)
    return _rules_ok(number, rules)


def _s10_carrier(number: str) -> str | None:
    country = number[-2:]
    if country == "PT" and number[0] == "D":
        return "ctt_expresso"  # unverified: CTT Expresso's "D" service codes
    if country == "FR" and number[0] == "C":
        return "colissimo"
    if country == "FR" and number[0] == "E":
        return "chronopost"
    return _S10_COUNTRIES.get(country)


def detect_carrier(number: str) -> str | None:
    """Return the carrier for numbers whose format identifies it.

    S10 numbers map to the postal operator of their country (None for
    countries without a carrier id, such as CN).
    """
    number = normalize_tracking_number(number)
    if not number or len(number) > MAX_NUMBER_CHARS:
        return None
    if ups_check_digit_ok(number):
        return "ups"
    if is_s10(number):
        return _s10_carrier(number)
    if not _basic_ok(number):
        return None
    for pattern, carrier, check in _DETECT_RULES:
        if pattern.fullmatch(number) and (check is None or check(number)):
            return carrier
    return None


def _self_identifying(number: str) -> bool:
    """True for numbers that need no context: S10, 1Z and prefixed formats."""
    return is_s10(number) or detect_carrier(number) is not None


def _pick_carrier(number: str, preferred: str | None) -> str | None:
    if preferred and validate_tracking_number(number, preferred):
        return preferred
    return detect_carrier(number)


_B = r"(?<![0-9A-Za-z])"
_E = r"(?![0-9A-Za-z])"
# Self-identifying numbers, found anywhere; S10 and 1Z may be spaced out.
_SELF_TEXT_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        _B + r"[A-Z]{2}[ \u00a0-]?(?:\d[ \u00a0.-]?){8}\d[ \u00a0-]?[A-Z]{2}" + _E
    ),
    re.compile(_B + r"1Z(?:[ \u00a0-]?[0-9A-Z]){16}" + _E),
    re.compile(
        _B + r"(?:(?:JJD|JVGL)\d{9,20}|JD\d{18}|GM\d{16,22}|00340434\d{12}|TBA\d{12}"
        r"|3S[A-Z]{4}\d{6,11}|LP\d{14}|YT\d{16}|VGS[0-9A-Z]{6,30}|9[2-6]\d{20})" + _E
    ),
)
# Other candidates: digit groups ("0150 1234 5678 90"), Nacex "0402/1234567"
# and uppercase runs of letters and digits.
_TOKEN_RE = re.compile(
    _B + r"(?:(?P<grouped>\d{4}(?:[ \u00a0]\d{4}){2,6}(?:[ \u00a0]\d{1,3})?)"
    r"|(?P<slash>\d{4}/\d{6,10})"
    r"|(?P<plain>[0-9A-Z]{8,35}))" + _E
)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
# An address starts where a run of address characters starts, so a long run
# without an "@" is read once, not once per character.
_EMAIL_RE = re.compile(r"(?<![\w.+\-])[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_PHONE_BEFORE_RE = re.compile(r"(?:\+\s?\d{1,4}|\(0\)|\(\d{2,5}\))[\s.\-]*$")
_INTL_PHONE_RE = re.compile(r"00[1-9]\d{9,12}")
_PRICE_AFTER_RE = re.compile(
    r"\s?(?:[.,]\d{1,2}(?!\d)|€|\$|£|(?:eur|usd|gbp|chf)(?![a-z]))", re.IGNORECASE
)
_PRICE_BEFORE_RE = re.compile(r"(?:€|\$|£|(?<![a-z])(?:eur|usd|gbp|chf))\s?$", re.I)
_IBAN_RE = re.compile(r"[A-Z]{2}\d{2}[0-9A-Z]{10,30}")
_IBAN_START_RE = re.compile(r"(?<![0-9A-Za-z])[A-Z]{2}\d{2}[ \u00a0]$")
_NEVER_NEXT_TO = frozenset("@/\\=&?%_")


def _blank(match: re.Match[str]) -> str:
    return " " * len(match.group(0))


def _is_iban(number: str) -> bool:
    if not _IBAN_RE.fullmatch(number):
        return False
    digits = "".join(str(int(c, 36)) for c in number[4:] + number[:4])
    return int(digits) % 97 == 1


def _plausible(text: str, start: int, end: int, number: str) -> bool:
    """Reject numbers that are part of something else (price, phone, IBAN...)."""
    before = text[start - 1] if start else ""
    after = text[end] if end < len(text) else ""
    if before in _NEVER_NEXT_TO or after in _NEVER_NEXT_TO:
        return False
    if before == "." and start > 1 and text[start - 2].isdigit():
        return False
    if before == "-" and start > 1 and text[start - 2].isalnum():
        return False
    if after == "." and text[end + 1 : end + 2].isdigit():
        return False
    if after == "-" and text[end + 1 : end + 2].isalnum():
        return False
    head = text[max(0, start - 12) : start]
    if (
        _PHONE_BEFORE_RE.search(head)
        or _PRICE_BEFORE_RE.search(head)
        or _IBAN_START_RE.search(head)
        or _PRICE_AFTER_RE.match(text, end)
    ):
        return False
    return not (_INTL_PHONE_RE.fullmatch(number) or _is_iban(number))


def _context_start(text: str, start: int) -> int:
    """Start of the window: this line and the previous non-empty one."""
    low = max(0, start - CONTEXT_CHARS)
    cut = text.rfind("\n", low, start)
    if cut < 0:
        return low
    end = cut
    while True:
        prev = text.rfind("\n", low, end)
        line_start = prev + 1 if prev >= 0 else low
        if text[line_start:end].strip() or prev < 0:
            return line_start
        end = prev


def _read_context(folded: str, low: int, high: int) -> tuple[bool, str | None]:
    """Return whether a tracking word is the nearest label, and the carrier named.

    An order word ("order", "Bestellung"...) closer to the number than any
    tracking word rejects it, unless it follows a possessive after a
    tracking word ("tracking number of your order").
    """
    first_keyword: int | None = None
    keyword_end = -1
    brand: str | None = None
    for match in _KEYWORD_RE.finditer(folded, low, high):
        if first_keyword is None:
            first_keyword = match.start()
        keyword_end = match.end()
    for match in _CARRIER_WORD_RE.finditer(folded, low, high):
        if first_keyword is None or match.start() < first_keyword:
            first_keyword = match.start()
        keyword_end = max(keyword_end, match.end())
        brand = CARRIER_WORDS.get(_SPACES_RE.sub(" ", match.group(0)))
    blocker_end = -1
    for match in _BLOCKER_RE.finditer(folded, low, high):
        if (
            first_keyword is not None
            and first_keyword < match.start()
            and _POSSESSIVE_RE.search(
                folded, max(low, match.start() - 24), match.start()
            )
        ):
            continue
        blocker_end = match.end()
    return keyword_end > blocker_end, brand


def _generic_candidate(number: str) -> bool:
    """Numbers accepted without a carrier: long digit runs or mixed codes."""
    if not _GENERIC_RE.fullmatch(number):
        return False
    digits = sum(c.isdigit() for c in number)
    if digits == len(number):
        return digits >= 11
    return digits >= 4 and len(set(number)) >= 3


def _classify(
    number: str, carrier: str | None, brand: str | None, slash: bool
) -> TrackingMatch | None:
    if carrier:
        if validate_tracking_number(number, carrier):
            return TrackingMatch(number, carrier, check_digit_ok(number, carrier))
        return None
    if brand and validate_tracking_number(number, brand):
        return TrackingMatch(number, brand, check_digit_ok(number, brand))
    if slash or not _generic_candidate(number) or not validate_tracking_number(number):
        return None
    detected = detect_carrier(number)
    return TrackingMatch(number, detected, check_digit_ok(number, detected))


def _merge(
    found: dict[str, tuple[int, TrackingMatch]], start: int, match: TrackingMatch
) -> None:
    current = found.get(match.number)
    if current is None:
        found[match.number] = (start, match)
        return
    first, kept = current
    if (match.validated and not kept.validated) or (
        kept.carrier is None and match.carrier
    ):
        found[match.number] = (
            min(first, start),
            TrackingMatch(
                match.number,
                match.carrier or kept.carrier,
                match.validated or kept.validated,
            ),
        )


def find_tracking_numbers(text: str, carrier: str | None = None) -> list[TrackingMatch]:
    """Find tracking numbers in text.

    Self-identifying numbers (UPU S10 and UPS 1Z with valid check digits,
    even spaced out; DHL JJD/SSCC, Amazon TBA, PostNL 3S, USPS, FedEx 96...)
    are found anywhere. Other numbers need a tracking word or a carrier name
    as their nearest label, no order/phone/price word closer to them, and a
    known format: the given carrier's, the named carrier's, or a long
    generic code. Text inside links and e-mail addresses is ignored.

    Returns validated matches first, then the others, each in text order,
    deduplicated by normalised number.
    """
    if not text:
        return []
    if carrier in ("", "other"):
        carrier = None
    text = _EMAIL_RE.sub(_blank, _URL_RE.sub(_blank, text[:MAX_SCAN_CHARS]))
    found: dict[str, tuple[int, TrackingMatch]] = {}
    taken: list[tuple[int, int]] = []
    for regex in _SELF_TEXT_RES:
        for match in regex.finditer(text):
            number = normalize_tracking_number(match.group(0))
            if _self_identifying(number):
                taken.append(match.span())
                found_match = TrackingMatch(
                    number, _pick_carrier(number, carrier), True
                )
                _merge(found, match.start(), found_match)

    folded = fold_aligned(text)
    prev_end, prev_ok, prev_brand = -1, False, None
    for match in _TOKEN_RE.finditer(text):
        start, end = match.span()
        if any(s < end and start < e for s, e in taken):
            prev_end, prev_ok = end, True
            continue
        number = normalize_tracking_number(match.group(0))
        if not _basic_ok(number):
            continue
        result: TrackingMatch | None = None
        brand: str | None = None
        if _plausible(text, start, end, number):
            if prev_ok and _LIST_GAP_RE.fullmatch(folded, prev_end, start):
                context, brand = True, prev_brand
            else:
                low = max(_context_start(text, start), prev_end, 0)
                context, brand = _read_context(folded, low, start)
            if context:
                result = _classify(number, carrier, brand, match.lastgroup == "slash")
        prev_end, prev_ok, prev_brand = end, result is not None, brand
        if result is not None:
            _merge(found, start, result)

    ordered = sorted(found.values(), key=lambda item: (not item[1].validated, item[0]))
    return [item for _, item in ordered]


def named_carriers(text: str) -> set[str]:
    """Return the carriers the text names, read as ``find_tracking_numbers`` does.

    Names inside links and e-mail addresses don't count.
    """
    if not text:
        return set()
    text = _EMAIL_RE.sub(_blank, _URL_RE.sub(_blank, text[:MAX_SCAN_CHARS]))
    return {
        CARRIER_WORDS[_SPACES_RE.sub(" ", match.group(0))]
        for match in _CARRIER_WORD_RE.finditer(fold_aligned(text))
    }


_URL_VALUE_SPLIT_RE = re.compile(r"[,;|+\s]+")
_URL_NUMBER_RE = re.compile(r"[0-9A-Z/]+")
_LOWER_RE = re.compile(r"[a-z]")
# At most this many values of one link are looked at.
_MAX_URL_VALUES = 50


def _link_host(host: str) -> tuple[bool, str | None]:
    """Return whether a host serves tracking pages, and its carrier."""
    org = organizational_domain(host)
    if org in TRACKING_HOSTS:
        return True, TRACKING_HOSTS[org]
    info = lookup(host)
    if info is not None and info.kind == "carrier":
        return True, info.carrier
    return False, None


def _url_values(
    query: str, path: str, tracking_host: bool, nested: list[str]
) -> list[tuple[str, bool]]:
    """Return (value, strong) pairs from a query string and a path.

    Values that are links themselves are added to ``nested``.
    """
    values: list[tuple[str, bool]] = []
    for key, value in parse_qsl(query):
        name = key.strip().lower()
        if value.strip().lower().startswith(("http://", "https://")):
            nested.append(value.strip())
            continue
        if name in _STRONG_PARAMS:
            strong = True
        elif tracking_host and name in _WEAK_PARAMS:
            strong = False
        else:
            continue
        values.extend(
            (part, strong) for part in _URL_VALUE_SPLIT_RE.split(value) if part
        )
    if tracking_host:
        values.extend((part, False) for part in unquote(path).split("/") if part)
    return values


def _url_match(
    value: str, strong: bool, host_carrier: str | None, aggregator: bool
) -> TrackingMatch | None:
    if not strong and _LOWER_RE.search(value):
        return None
    number = normalize_tracking_number(value)
    if (
        len(number) > MAX_NUMBER_CHARS
        or not _URL_NUMBER_RE.fullmatch(number)
        or not _basic_ok(number)
    ):
        return None
    if _self_identifying(number):
        return TrackingMatch(number, _pick_carrier(number, host_carrier), True)
    if host_carrier and validate_tracking_number(number, host_carrier):
        return TrackingMatch(number, host_carrier, check_digit_ok(number, host_carrier))
    if (
        (strong or aggregator)
        and _generic_ok(number)
        and validate_tracking_number(number)
    ):
        return TrackingMatch(number, host_carrier, False)
    return None


def _numbers_from_url(url: str, depth: int) -> list[TrackingMatch]:
    if not url or len(url) > MAX_URL_CHARS:
        return []
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
    except ValueError:
        return []
    if parts.scheme.lower() not in ("http", "https") or not host:
        return []
    tracking_host, host_carrier = _link_host(host)
    aggregator = tracking_host and host_carrier is None
    nested: list[str] = []
    values = _url_values(parts.query, parts.path, tracking_host, nested)
    fragment = parts.fragment
    if fragment:
        frag_path, sep, frag_query = fragment.partition("?")
        if not sep and "=" in frag_path:
            frag_path, frag_query = "", frag_path
        values += _url_values(frag_query, frag_path, tracking_host, nested)
    found: list[TrackingMatch] = []
    for value, strong in values[:_MAX_URL_VALUES]:
        match = _url_match(value, strong, host_carrier, aggregator)
        if match is not None:
            found.append(match)
    if depth == 0:
        for link in nested[:3]:
            found.extend(_numbers_from_url(link, depth + 1))
    return found


def numbers_from_url(url: str) -> list[TrackingMatch]:
    """Read tracking numbers from a link without fetching it.

    Values of well-known parameters (``tracknum``, ``trackingNumber``,
    ``nums``...) count on any site. On carrier tracking sites (a known
    carrier domain or a tracking host such as 17track.net) generic
    parameters (``id``, ``objects``, ``query``...) and path segments count
    too, and the host's carrier is used. A link wrapped in another link's
    parameter (click trackers) is read once. Validated matches come first.
    """
    found: dict[str, tuple[int, TrackingMatch]] = {}
    for index, match in enumerate(_numbers_from_url(url, 0)):
        _merge(found, index, match)
    ordered = sorted(found.values(), key=lambda item: (not item[1].validated, item[0]))
    return [item for _, item in ordered]


def tracking_url(carrier: str | None, number: str) -> str:
    """Return the carrier's official tracking page, else the 17TRACK page."""
    number = normalize_tracking_number(number)
    template = URL_TEMPLATES.get(carrier or "", "")
    if not template.startswith("https://"):
        template = FALLBACK_URL
    return template.format(n=quote(number, safe=""))
