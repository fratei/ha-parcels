"""Turn raw e-mails into ``MailMessage`` objects.

E-mails come from Gmail (raw RFC 5322 bytes) or Microsoft Graph (JSON).
Bodies are converted to plain text in memory; links are collected but
never fetched, and images are never loaded.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
import contextlib
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
import re
from typing import Any

from .auth import parse_authentication_results
from .base import Link, MailMessage
from .css import GONE, INVISIBLE, element_masks, masks
from .lang import LANGUAGES, detect_language

MAX_HTML_CHARS = 2_000_000
MAX_TEXT_CHARS = 100_000
MAX_URL_CHARS = 2048
MAX_LINKS = 300
MAX_LINK_TEXT_CHARS = 200
MAX_HEADER_CHARS = 4000
MAX_SHOPIFY_HEADERS = 20
LANGUAGE_SAMPLE_CHARS = 3000

# Headers kept on the message (lowercased); X-Shopify-* headers are kept too.
KEPT_HEADERS: tuple[str, ...] = (
    "authentication-results",
    "content-language",
    "list-id",
    "x-mailer",
    "return-path",
)

# Elements whose content is never shown; the head is tracked on its own.
_SKIP_TAGS = frozenset(
    {
        "script",
        "style",
        "title",
        "noscript",
        "template",
        "svg",
        "math",
        "iframe",
        "object",
        "noembed",
        "noframes",
        "xmp",
    }
)
# Elements that may appear in <head>; anything else ends an unclosed head.
_HEAD_TAGS = frozenset(
    {
        "base",
        "basefont",
        "bgsound",
        "link",
        "meta",
        "noframes",
        "noscript",
        "script",
        "style",
        "template",
        "title",
    }
)
_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "center",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "tfoot",
        "thead",
        "tr",
        "ul",
    }
)
_CELL_TAGS = frozenset({"td", "th"})
_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "basefont",
        "bgsound",
        "br",
        "col",
        "embed",
        "frame",
        "hr",
        "image",
        "img",
        "input",
        "keygen",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
# HTML's special elements that can be open; they bound where end tags reach.
_SPECIAL = frozenset(
    {
        "address",
        "applet",
        "article",
        "aside",
        "blockquote",
        "button",
        "caption",
        "center",
        "colgroup",
        "dd",
        "details",
        "dir",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "frameset",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hgroup",
        "li",
        "listing",
        "main",
        "marquee",
        "menu",
        "nav",
        "ol",
        "p",
        "plaintext",
        "pre",
        "search",
        "section",
        "select",
        "summary",
        "table",
        "tbody",
        "td",
        "textarea",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
)
# A new li, dd or dt closes an open one unless one of these comes first.
_LIST_ITEM_STOPS = _SPECIAL - {"address", "div", "p"}
# End tags don't reach past these, except the tables' own parts.
_SCOPE_BARRIERS = frozenset({"applet", "caption", "marquee", "table", "td", "th"})
_TABLE_SCOPED = frozenset(
    {"caption", "colgroup", "table", "tbody", "td", "tfoot", "th", "thead", "tr"}
)
_CLOSES_P = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "center",
        "dd",
        "details",
        "dialog",
        "dir",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hgroup",
        "hr",
        "li",
        "listing",
        "main",
        "menu",
        "nav",
        "ol",
        "p",
        "plaintext",
        "pre",
        "search",
        "section",
        "summary",
        "table",
        "ul",
    }
)
_ROW_GROUP_PARTS = ("tbody", "thead", "tfoot", "tr", "td", "th")
# The open parts of the current table that a new table part closes.
_TABLE_SIBLINGS: dict[str, tuple[str, ...]] = {
    "td": ("td", "th"),
    "th": ("td", "th"),
    "tr": ("tr", "td", "th"),
    "tbody": _ROW_GROUP_PARTS,
    "thead": _ROW_GROUP_PARTS,
    "tfoot": _ROW_GROUP_PARTS,
}
# Deeper elements, and everything after them, are dropped.
MAX_DEPTH = 1024

# Zero-width and invisible characters, often used as preview padding.
_INVISIBLE_RE = re.compile(
    "[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180e\u200b-\u200f"
    "\u202a-\u202e\u2060-\u2064\u206a-\u206f\u3164\ufeff\uffa0]"
)
_SPACES_RE = re.compile(r"[^\S\n]+")
_WHITESPACE_RE = re.compile(r"\s+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_URL_IN_TEXT_RE = re.compile(r"https?://[^\s<>\"'`{}|\\^\[\]]+", re.IGNORECASE)
_URL_TRAILING = ".,;:!?)]}'\"*>"
_COMMENT_RE = re.compile(r"\([^()]*\)")


def _clean_text(text: str) -> str:
    """Collapse spaces, strip lines and keep at most one blank line."""
    text = _INVISIBLE_RE.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = [_SPACES_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = _BLANK_LINES_RE.sub("\n\n", "\n".join(lines))
    return text.strip()[:MAX_TEXT_CHARS]


def _clean_url(url: str) -> str | None:
    """Return an http(s) URL without whitespace, capped, or None."""
    url = "".join(url.split())
    lowered = url.lower()
    if not lowered.startswith(("http://", "https://")):
        return None
    if len(url.partition("://")[2].strip("/")) == 0:
        return None
    return url[:MAX_URL_CHARS]


class _TextExtractor(HTMLParser):
    """Collect the text and links a reader sees in HTML.

    Open elements are kept on one stack with their state, which combines the
    parent's state with the element's inline style and ``hidden`` attribute
    (see ``css``). Text, links and image alt texts are kept only while the
    state shows them. Unclosed elements are closed as browsers do for lists,
    paragraphs, table parts and options; other repairs aren't emulated.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.size = 0
        self.links: list[Link] = []
        self._skip: list[str] = []
        self._skipping: Counter[str] = Counter()
        self._in_head = False
        self._too_deep = False
        # Open elements as (tag, state), innermost last, with the positions of
        # each tag, of the special elements and of the scope barriers.
        self._stack: list[tuple[str, int]] = []
        self._open: dict[str, list[int]] = {}
        self._special: list[int] = []
        self._stops: list[int] = []
        self._barriers: list[int] = []
        self._root_attrs: dict[str, dict[str, str]] = {"html": {}, "body": {}}
        self._root = 0
        self._pre = 0
        self._href: str | None = None
        self._link_seen = False
        self._link_text: list[str] = []
        self._link_alt: str = ""
        self._line_start = True

    def _emit(self, text: str) -> None:
        if self.size >= MAX_TEXT_CHARS * 2 or not text:
            return
        if self._line_start and not self._pre and not text.strip():
            return
        self.parts.append(text)
        self.size += len(text)
        self._line_start = text.endswith("\n")
        if self._href is not None:
            self._link_text.append(text)

    def _break(self, *, hard: bool = False) -> None:
        """End the current line; block boundaries never stack, ``<br>`` does."""
        if hard or not self._line_start:
            self.parts.append("\n")
            self.size += 1
            self._line_start = True
            if self._href is not None:
                self._link_text.append(" ")

    def finish_link(self) -> None:
        """Store the link that is open, if a reader could see it."""
        if self._href is not None and self._link_seen and len(self.links) < MAX_LINKS:
            text = " ".join(_INVISIBLE_RE.sub("", "".join(self._link_text)).split())
            text = text or " ".join(self._link_alt.split())
            self.links.append(Link(self._href, text[:MAX_LINK_TEXT_CHARS]))
        self._href = None
        self._link_seen = False
        self._link_text = []
        self._link_alt = ""

    def _state(self) -> int:
        return self._stack[-1][1] if self._stack else self._root

    def _last(self, tag: str) -> int:
        """Return the position of the innermost open ``tag``, or -1."""
        positions = self._open.get(tag)
        return positions[-1] if positions else -1

    def _push(self, tag: str, state: int) -> None:
        if len(self._stack) >= MAX_DEPTH:
            self._too_deep = True
            return
        position = len(self._stack)
        self._stack.append((tag, state))
        self._open.setdefault(tag, []).append(position)
        if tag in _SPECIAL:
            self._special.append(position)
            if tag in _LIST_ITEM_STOPS:
                self._stops.append(position)
            if tag in _SCOPE_BARRIERS:
                self._barriers.append(position)
        if tag == "pre":
            self._pre += 1

    def _pop_to(self, position: int) -> None:
        """Close the element at ``position`` and everything inside it."""
        while len(self._stack) > position:
            tag, _ = self._stack.pop()
            self._open[tag].pop()
            if tag in _SPECIAL:
                self._special.pop()
                if tag in _LIST_ITEM_STOPS:
                    self._stops.pop()
                if tag in _SCOPE_BARRIERS:
                    self._barriers.pop()
            if tag == "pre":
                self._pre -= 1

    def _close_implied(self, tag: str) -> None:
        """Close the elements that a start tag ends without an end tag."""
        if tag in ("li", "dd", "dt") and self._stops:
            open_tag = self._stack[self._stops[-1]][0]
            if open_tag == tag or (tag != "li" and open_tag in ("dd", "dt")):
                self._pop_to(self._stops[-1])
        if tag in _CLOSES_P:
            barrier = self._barriers[-1] if self._barriers else -1
            p = self._last("p")
            if p > max(barrier, self._last("button")):
                self._pop_to(p)
        if (siblings := _TABLE_SIBLINGS.get(tag)) is not None:
            table = self._last("table")
            open_parts = [p for p in map(self._last, siblings) if p > table]
            if open_parts:
                self._pop_to(min(open_parts))
        if tag == "option" and self._stack and self._stack[-1][0] == "option":
            self._pop_to(len(self._stack) - 1)

    def _end_target(self, tag: str) -> int:
        """Return the position of the element an end tag closes, or -1."""
        target = self._last(tag)
        if target < 0:
            return -1
        if tag in _TABLE_SCOPED:
            return target if target >= self._last("table") else -1
        if tag in _SPECIAL:
            barrier = self._barriers[-1] if self._barriers else -1
            if tag == "p":
                barrier = max(barrier, self._last("button"))
            elif tag == "li":
                barrier = max(barrier, self._last("ol"), self._last("ul"))
            return target if barrier <= target else -1
        # Other end tags don't reach past an open special element.
        return target if not self._special or self._special[-1] < target else -1

    def _set_root(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Merge repeated html and body tags' attributes; the first one wins."""
        merged = self._root_attrs[tag]
        changed = False
        for name, value in attrs:
            if name in ("style", "hidden") and name not in merged:
                merged[name] = value or ""
                changed = True
        if changed:
            state = 0
            for root in ("html", "body"):
                found = self._root_attrs[root]
                keep, add = masks(root, found.get("style"), found.get("hidden"))
                state = (state & keep) | add
            self._root = state

    def _leave_head(self) -> None:
        if self._in_head and not self._skip:
            self._in_head = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._too_deep:
            return
        if tag in ("body", "html"):
            self._in_head = False
            self._set_root(tag, attrs)
            return
        if tag == "head":
            self._in_head = self._in_head or not self._skip
            return
        if tag not in _HEAD_TAGS:
            self._leave_head()
        if tag in _SKIP_TAGS:
            if len(self._skip) >= MAX_DEPTH:
                self._too_deep = True
                return
            self._skip.append(tag)
            self._skipping[tag] += 1
            return
        if self._skip or self._in_head:
            return
        self._close_implied(tag)
        keep, add = element_masks(tag, attrs)
        state = (self._state() & keep) | add
        if tag not in _VOID_TAGS:
            self._push(tag, state)
            if self._too_deep:
                return
        if tag == "a":
            self.finish_link()
            href = next((v for k, v in attrs if k == "href" and v), None)
            if not state & GONE and href and (url := _clean_url(href)):
                self._href = url
                # A link in hidden text counts once something in it shows.
                self._link_seen = not state
        elif tag == "img":
            if self._href is not None and not state & (GONE | INVISIBLE):
                self._link_seen = True
                if not self._link_alt:
                    self._link_alt = next((v for k, v in attrs if k == "alt" and v), "")
        elif state & GONE:
            return
        elif tag in _BLOCK_TAGS:
            self._break(hard=tag == "br")
        elif tag in _CELL_TAGS:
            self._emit(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("svg", "math"):
            # Only foreign elements really close themselves.
            if not self._too_deep:
                self._leave_head()
            return
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._too_deep:
            return
        if tag == "head":
            if self._in_head:
                self._in_head = False
                self._skip.clear()
                self._skipping.clear()
            return
        if tag in _SKIP_TAGS:
            if self._skipping[tag]:
                while (open_tag := self._skip.pop()) != tag:
                    self._skipping[open_tag] -= 1
                self._skipping[tag] -= 1
            return
        if self._skip or self._in_head or tag in ("body", "html"):
            return
        target = self._end_target(tag)
        state = self._stack[target][1] if target >= 0 else self._state()
        if tag == "a":
            self.finish_link()
        elif state & GONE:
            pass
        elif tag in _BLOCK_TAGS:
            self._break(hard=tag == "br")
        elif tag in _CELL_TAGS:
            self._emit(" ")
        if target >= 0:
            self._pop_to(target)

    def handle_data(self, data: str) -> None:
        if self._too_deep:
            return
        if self._in_head and not self._skip and data.strip():
            self._in_head = False
        if self._skip or self._in_head:
            return
        if state := self._state():
            if state == INVISIBLE:
                # Invisible text still takes its place: keep words apart.
                self._emit(" ")
            return
        if self._pre:
            self._emit(data)
        else:
            self._emit(_WHITESPACE_RE.sub(" ", data))
        if (
            self._href is not None
            and not self._link_seen
            and _INVISIBLE_RE.sub("", data).strip()
        ):
            self._link_seen = True


def html_to_text(html: str) -> tuple[str, tuple[Link, ...]]:
    """Convert HTML to plain text and the links it contains. Never fetches.

    Only what a reader sees is kept. Scripts, styles, the head and similar
    elements are dropped, and so is text that inline styles or the ``hidden``
    attribute hide: ``display:none``, ``visibility:hidden``, ``font-size:0``
    and a zero (maximum) height with hidden overflow. Block elements become
    line breaks and table cells are separated by spaces. Only http(s) links
    a reader could see are kept, with their visible text or image alt text.
    Images are otherwise ignored.
    """
    parser = _TextExtractor()
    # Malformed HTML keeps whatever was read before the error.
    with contextlib.suppress(Exception):
        parser.feed(html[:MAX_HTML_CHARS])
        parser.close()
    parser.finish_link()
    return _clean_text("".join(parser.parts)), tuple(parser.links)


def links_from_text(text: str) -> tuple[Link, ...]:
    """Find http(s) URLs in plain text, in order and without duplicates."""
    links: list[Link] = []
    seen: set[str] = set()
    for match in _URL_IN_TEXT_RE.finditer(text):
        url = _clean_url(match.group(0).rstrip(_URL_TRAILING))
        if url and url not in seen:
            seen.add(url)
            links.append(Link(url))
            if len(links) >= MAX_LINKS:
                break
    return tuple(links)


def _primary_language(value: str | None) -> str | None:
    """Return a supported language from a Content-Language value."""
    if not value:
        return None
    primary = re.split(r"[-_\s]", value.split(",")[0].strip().lower())[0]
    return primary if primary in LANGUAGES else None


def _guess_language(headers: Mapping[str, str], subject: str, text: str) -> str | None:
    return _primary_language(headers.get("content-language")) or detect_language(
        f"{subject}\n{text[:LANGUAGE_SAMPLE_CHARS]}"
    )


def _fix_surrogates(value: str) -> str:
    """Decode raw 8-bit header bytes kept as surrogate escapes as UTF-8."""
    if not any("\udc80" <= char <= "\udcff" for char in value):
        return value
    return value.encode("utf-8", "surrogateescape").decode("utf-8", "replace")


def _decode_payload(part: Message) -> str:
    """Decode a text part leniently, whatever charset it claims."""
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        return ""
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, bytes):
        return ""
    charset = (part.get_content_charset() or "utf-8").strip().strip("\"'").lower()
    with contextlib.suppress(LookupError, UnicodeDecodeError):
        return payload.decode(charset)
    with contextlib.suppress(UnicodeDecodeError):
        return payload.decode("utf-8")
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("latin-1", errors="replace")


def _body(message: Message) -> tuple[str, tuple[Link, ...]]:
    """Return the text and links of the best body part."""
    part: Message | None = None
    if isinstance(message, EmailMessage):
        with contextlib.suppress(Exception):
            part = message.get_body(preferencelist=("html", "plain"))
    if (
        part is None
        and not message.is_multipart()
        and message.get_content_maintype() == "text"
    ):
        part = message
    if part is None:
        return "", ()
    content = _decode_payload(part)
    if part.get_content_subtype() == "html":
        return html_to_text(content)
    text = _clean_text(content[:MAX_HTML_CHARS])
    return text, links_from_text(text)


def _raw_headers(message: Message) -> list[tuple[str, str]]:
    """Return headers as (lowercased name, unfolded raw value), top-down."""
    try:
        items = list(message.raw_items())
    except Exception:
        return []
    return [
        (name.strip().lower(), " ".join(_fix_surrogates(str(value)).split()))
        for name, value in items
    ]


def _decoded_header(message: Message, name: str, raw: str) -> str:
    """Return a header decoded from RFC 2047, else its raw value."""
    try:
        value = message.get(name)
    except Exception:
        value = None
    text = raw if value is None else _fix_surrogates(str(value))
    return " ".join(text.split())


def _kept_headers(raw: list[tuple[str, str]]) -> dict[str, str]:
    """Pick the headers kept on the message; only the first of each name."""
    headers: dict[str, str] = {}
    shopify = 0
    for name, value in raw:
        if name in headers:
            continue
        if name in KEPT_HEADERS:
            headers[name] = value[:MAX_HEADER_CHARS]
        elif name.startswith("x-shopify-") and shopify < MAX_SHOPIFY_HEADERS:
            headers[name] = value[:MAX_HEADER_CHARS]
            shopify += 1
    return headers


def _address(message: Message, name: str, raw: str) -> tuple[str, str]:
    """Return (display name, lowercased address) of an address header."""
    addresses: tuple[Any, ...] = ()
    with contextlib.suppress(Exception):
        addresses = tuple(getattr(message.get(name), "addresses", ()))
    for address in addresses:
        addr_spec = str(getattr(address, "addr_spec", ""))
        if "@" in addr_spec and " " not in addr_spec.strip():
            display = _fix_surrogates(str(getattr(address, "display_name", "")))
            return " ".join(display.split()), addr_spec.strip().lower()
    with contextlib.suppress(Exception):
        for display, addr in getaddresses([raw]):
            if "@" in addr:
                return " ".join(display.split()), addr.strip().lower()
    return "", ""


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _parse_rfc2822_date(value: str) -> datetime | None:
    try:
        return _aware(parsedate_to_datetime(value))
    except TypeError, ValueError, IndexError, OverflowError:
        return None


def _date(message: Message, raw: list[tuple[str, str]]) -> datetime:
    """Return the Date header, else the topmost Received date, else now."""
    value: Any = None
    with contextlib.suppress(Exception):
        value = getattr(message.get("Date"), "datetime", None)
    if isinstance(value, datetime):
        return _aware(value)
    raw_date = next((v for k, v in raw if k == "date"), "")
    if raw_date and (parsed := _parse_rfc2822_date(raw_date)):
        return parsed
    received = next((v for k, v in raw if k == "received"), "")
    if ";" in received:
        stamp = _COMMENT_RE.sub(" ", received.rpartition(";")[2]).strip()
        if parsed := _parse_rfc2822_date(stamp):
            return parsed
    return datetime.now(UTC)


def message_from_bytes(
    raw: bytes, *, mailbox: str, provider_id: str, provider: str
) -> MailMessage:
    """Parse an RFC 5322 message (Gmail ``format=raw``).

    The HTML part is preferred over the plain text part. Only the topmost
    Authentication-Results header is kept and parsed.
    """
    message = BytesParser(policy=policy.default).parsebytes(raw)
    raw_headers = _raw_headers(message)

    def first(name: str) -> str:
        return next((v for k, v in raw_headers if k == name), "")

    headers = _kept_headers(raw_headers)
    sender_name, sender = _address(message, "From", first("from"))
    _, reply_to = _address(message, "Reply-To", first("reply-to"))
    subject = _decoded_header(message, "Subject", first("subject"))
    text, links = _body(message)
    auth_header = headers.get("authentication-results")
    return MailMessage(
        message_id=first("message-id").strip(),
        provider_id=provider_id,
        provider=provider,
        mailbox=mailbox,
        sender=sender,
        sender_name=sender_name,
        subject=subject,
        date=_date(message, raw_headers),
        text=text,
        links=links,
        reply_to=reply_to or None,
        auth=parse_authentication_results(auth_header) if auth_header else None,
        received=None,
        headers=headers,
        language=_guess_language(headers, subject, text),
    )


def _graph_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _aware(datetime.fromisoformat(value.strip()))
    except ValueError:
        return None


def _graph_address(value: Any) -> tuple[str, str]:
    """Return (name, lowercased address) of a Graph recipient object."""
    email = value.get("emailAddress") if isinstance(value, Mapping) else None
    if not isinstance(email, Mapping):
        return "", ""
    name = email.get("name")
    address = email.get("address")
    return (
        " ".join(name.split()) if isinstance(name, str) else "",
        address.strip().lower() if isinstance(address, str) else "",
    )


def message_from_graph(item: Mapping[str, Any], *, mailbox: str) -> MailMessage:
    """Build a message from a Microsoft Graph message resource.

    Expects the body as HTML (``Prefer: outlook.body-content-type="html"``)
    and ``internetMessageHeaders``, which Graph lists top-down.
    """
    raw_headers: list[tuple[str, str]] = []
    for header in item.get("internetMessageHeaders") or ():
        if isinstance(header, Mapping):
            name, value = header.get("name"), header.get("value")
            if isinstance(name, str) and isinstance(value, str):
                raw_headers.append((name.strip().lower(), " ".join(value.split())))
    headers = _kept_headers(raw_headers)
    sender_name, sender = _graph_address(item.get("from"))
    reply_to = ""
    for recipient in item.get("replyTo") or ():
        if reply_to := _graph_address(recipient)[1]:
            break
    subject = " ".join(str(item.get("subject") or "").split())
    body = item.get("body")
    body = body if isinstance(body, Mapping) else {}
    content = body.get("content")
    content = content if isinstance(content, str) else ""
    if str(body.get("contentType") or "html").lower() == "html":
        text, links = html_to_text(content)
    else:
        text = _clean_text(content[:MAX_HTML_CHARS])
        links = links_from_text(text)
    received = _graph_datetime(item.get("receivedDateTime"))
    sent = _graph_datetime(item.get("sentDateTime")) or received
    auth_header = headers.get("authentication-results")
    return MailMessage(
        message_id=str(item.get("internetMessageId") or "").strip(),
        provider_id=str(item.get("id") or ""),
        provider="microsoft",
        mailbox=mailbox,
        sender=sender,
        sender_name=sender_name,
        subject=subject,
        date=sent or datetime.now(UTC),
        text=text,
        links=links,
        reply_to=reply_to or None,
        auth=parse_authentication_results(auth_header) if auth_header else None,
        received=received,
        headers=headers,
        language=_guess_language(headers, subject, text),
    )
