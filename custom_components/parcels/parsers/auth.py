"""Sender authentication from the provider's Authentication-Results header.

Gmail: only the topmost header is used; it is the one Gmail added. Headers
further down can be written by anyone, including the sender.

Outlook.com (Graph): Microsoft renames the headers it received to
Authentication-Results-Original and adds its own, so exactly one is
expected. Graph doesn't list headers in arrival order, so when there are
two or more, none is trusted.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
import re

from .base import AuthCheck, AuthResult, MailMessage, SenderVerdict
from .senders import lookup, organizational_domain

GOOGLE_AUTHSERV_ID = "mx.google.com"
MICROSOFT_AUTHSERV_IDS: frozenset[str] = frozenset({"mx.microsoft.com"})

# DKIM signatures from these domains mean the e-mail was sent by Shopify on
# behalf of a store.
SHOPIFY_DKIM_DOMAINS: frozenset[str] = frozenset({"shopify.com", "shopifyemail.com"})

_SHOPIFY_LINK_RE = re.compile(
    r"^https?://(?:[a-z0-9-]+\.)*(?:cdn\.shopify\.com|myshopify\.com)(?:[:/?#]|$)",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[^\s;]+|;")
_WORD_RE = re.compile(r"[a-z]{1,16}")
_SERVER_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}\.)*[a-z0-9-]{1,63}")
MAX_SERVER_CHARS = 100
_METHODS = frozenset(
    {
        "arc",
        "auth",
        "bimi",
        "compauth",
        "dkim",
        "dkim-adsp",
        "dkim-atps",
        "dmarc",
        "domainkeys",
        "iprev",
        "rrvs",
        "sender-id",
        "smime",
        "spf",
        "vbr",
        "x-google-dkim",
    }
)


def _strip_comments(value: str) -> str:
    """Remove RFC 5322 comments, which may be nested and contain ``;``."""
    out: list[str] = []
    depth = 0
    quoted = False
    escaped = False
    for char in value:
        if escaped:
            escaped = False
            if depth == 0:
                out.append(char)
            continue
        if char == "\\":
            escaped = True
            if depth == 0:
                out.append(char)
            continue
        if quoted:
            if char == '"':
                quoted = False
            out.append(char)
            continue
        if char == '"' and depth == 0:
            quoted = True
            out.append(char)
        elif char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
            if not depth:
                out.append(" ")
        elif not depth:
            out.append(char)
    return "".join(out)


def _domain_of(value: str) -> str | None:
    """Return the domain of ``@domain``, ``user@domain`` or ``domain``."""
    value = value.strip().strip('"').strip("<>").rstrip(".").lower()
    domain = value.rpartition("@")[2]
    if not domain or not re.fullmatch(r"[a-z0-9._-]+", domain) or "." not in domain:
        return None
    return domain


def parse_authentication_results(value: str) -> AuthResult:
    """Parse one Authentication-Results header value (RFC 8601), tolerantly.

    Handles the Gmail style (``mx.google.com; dkim=pass header.i=@x.com``)
    and the Outlook.com style, which has no authserv-id.
    """
    text = " ".join(_strip_comments(value).split())
    first, _, rest = text.partition(";")
    authserv_id: str | None = None
    if first.strip() and "=" not in first:
        authserv_id = first.split()[0].lower()
        text = rest
    dkim: list[str] = []
    dmarc_pass = False
    dmarc_domain: str | None = None
    dmarc_seen = False
    spf_pass = False
    spf_domain: str | None = None
    spf_seen = False

    results: list[tuple[str, str, dict[str, str]]] = []
    current: tuple[str, str, dict[str, str]] | None = None
    for token in _TOKEN_RE.findall(text):
        if token == ";":
            current = None
            continue
        name, sep, val = token.partition("=")
        if not sep:
            continue
        name = name.lower()
        if name in _METHODS or (current is None and "." not in name):
            current = (name, val.strip('"').lower(), {})
            results.append(current)
        elif current is not None:
            current[2].setdefault(name, val)

    words: dict[str, str] = {}
    for method, result, props in results:
        if method in ("dkim", "dmarc", "spf"):
            word = result if _WORD_RE.fullmatch(result) else "other"
            if method not in words or (method == "dkim" and word == "pass"):
                words[method] = word
        if method == "dkim" and result == "pass":
            domain = _domain_of(props.get("header.d", "")) or _domain_of(
                props.get("header.i", "")
            )
            if domain and domain not in dkim:
                dkim.append(domain)
        elif method == "dmarc" and not dmarc_seen:
            dmarc_seen = True
            dmarc_pass = result == "pass"
            dmarc_domain = _domain_of(props.get("header.from", ""))
        elif method == "spf" and not spf_seen:
            spf_seen = True
            spf_pass = result == "pass"
            spf_domain = _domain_of(
                props.get("smtp.mailfrom", "") or props.get("smtp.helo", "")
            )
    return AuthResult(
        authserv_id=authserv_id,
        dkim_pass_domains=tuple(dkim),
        dmarc_pass=dmarc_pass,
        dmarc_domain=dmarc_domain,
        spf_pass=spf_pass,
        spf_domain=spf_domain,
        dkim=words.get("dkim", ""),
        dmarc=words.get("dmarc", ""),
        spf=words.get("spf", ""),
    )


def _trusted_authserv(message: MailMessage, auth: AuthResult) -> bool:
    if message.provider == "google":
        return auth.authserv_id == GOOGLE_AUTHSERV_ID
    if message.provider == "microsoft":
        # Outlook.com wrote no authserv-id until about September 2026, and
        # "mx.microsoft.com 1" since; the version number isn't kept.
        return auth.authserv_id is None or auth.authserv_id in MICROSOFT_AUTHSERV_IDS
    return False


def _server(authserv_id: str | None) -> str:
    """Return an authserv-id fit to show: a host name, "" or "(other)"."""
    if authserv_id is None:
        return ""
    if len(authserv_id) <= MAX_SERVER_CHARS and _SERVER_RE.fullmatch(authserv_id):
        return authserv_id
    return "(other)"


def _weak_shopify(message: MailMessage) -> bool:
    if message.sender.lower() == "mailer@shopify.com":
        return True
    if any(name.startswith("x-shopify-") for name in message.headers):
        return True
    return any(_SHOPIFY_LINK_RE.match(link.url) for link in message.links)


def verify_sender(message: MailMessage, trusted: Iterable[str] = ()) -> SenderVerdict:
    """Decide whether the sender is authenticated and known.

    Authenticated: the provider's DMARC pass, or a DKIM pass, aligned with
    the From domain (same organizational domain). Known: on the allow-list,
    trusted by the user, or sent through Shopify (DKIM from Shopify).
    Weak Shopify markers only set ``shopify``; they never make a sender
    known, because anyone can paste a Shopify link.
    """
    domain = message.sender_domain
    org = organizational_domain(domain) if domain else ""
    trusted_orgs = {organizational_domain(d) for d in trusted if d}
    known = bool(org) and (lookup(org) is not None or org in trusted_orgs)
    shopify = _weak_shopify(message)

    auth = message.auth
    if auth is None and (raw := message.headers.get("authentication-results")):
        auth = parse_authentication_results(raw)
    parsed = [parse_authentication_results(value) for value in message.auth_headers]
    if not parsed and auth is not None:
        parsed = [auth]
    check = AuthCheck(
        headers=len(parsed),
        servers=tuple(_server(result.authserv_id) for result in parsed),
        originals=message.auth_originals,
    )
    reason = ""
    if auth is None:
        reason = "no_auth_header"
    elif message.provider == "microsoft" and len(parsed) > 1:
        # Graph doesn't list headers in arrival order, so a second header
        # may be the sender's, and there's no telling which is which.
        reason = "multiple_auth_results"
    elif not _trusted_authserv(message, auth):
        reason = "untrusted_authserv"
    if reason or auth is None:
        return SenderVerdict(
            domain, False, known, shopify, method="none", reason=reason, check=check
        )
    check = replace(check, used=0, dkim=auth.dkim, dmarc=auth.dmarc, spf=auth.spf)

    dkim_orgs = {organizational_domain(d) for d in auth.dkim_pass_domains}
    if dkim_orgs & SHOPIFY_DKIM_DOMAINS:
        shopify = True
        known = known or bool(org)
    method = "none"
    if org:
        if (
            auth.dmarc_pass
            and auth.dmarc_domain
            and organizational_domain(auth.dmarc_domain) == org
        ):
            method = "dmarc"
        elif org in dkim_orgs:
            method = "dkim"
    if method == "none":
        return SenderVerdict(
            domain,
            False,
            known,
            shopify,
            method="none",
            reason="not_aligned",
            check=check,
        )
    return SenderVerdict(
        domain,
        True,
        known,
        shopify,
        method=method,
        reason="ok" if known else "unknown_sender",
        check=check,
    )
