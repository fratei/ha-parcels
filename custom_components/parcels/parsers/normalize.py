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
# Table parts, which browsers ignore outside a table.
_TABLE_PARTS = (_TABLE_SCOPED - {"table"}) | {"col"}
# Elements that end tags such as </form> close implicitly.
_IMPLIED_END = frozenset(
    {"dd", "dt", "li", "optgroup", "option", "p", "rb", "rp", "rt", "rtc"}
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
_HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
# Formatting elements. Closed early, browsers open them again before the next
# text or start tag, unless the tag is one of _NO_RECONSTRUCT.
_FORMATTING = frozenset(
    {
        "a",
        "b",
        "big",
        "code",
        "em",
        "font",
        "i",
        "nobr",
        "s",
        "small",
        "strike",
        "strong",
        "tt",
        "u",
    }
)
_NO_RECONSTRUCT = _HEADINGS | frozenset(
    {
        "address",
        "article",
        "aside",
        "base",
        "basefont",
        "bgsound",
        "blockquote",
        "body",
        "caption",
        "center",
        "col",
        "colgroup",
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
        "frame",
        "frameset",
        "head",
        "header",
        "hgroup",
        "hr",
        "html",
        "iframe",
        "li",
        "link",
        "listing",
        "main",
        "menu",
        "meta",
        "nav",
        "noembed",
        "noframes",
        "ol",
        "p",
        "param",
        "plaintext",
        "pre",
        "rb",
        "rp",
        "rt",
        "rtc",
        "script",
        "search",
        "section",
        "source",
        "style",
        "summary",
        "table",
        "tbody",
        "td",
        "template",
        "textarea",
        "tfoot",
        "th",
        "thead",
        "title",
        "tr",
        "track",
        "ul",
    }
)
# Skipped elements that browsers open formatting elements again for.
_RECONSTRUCT_SKIPPED = frozenset({"math", "noscript", "object", "svg", "xmp"})
# Whitespace in these doesn't open formatting elements again.
_TABLE_TEXT_PARTS = frozenset({"table", "tbody", "tfoot", "thead", "tr"})
_HTML_SPACE = " \t\n\f\r"
# Doctypes that keep browsers out of quirks mode, where a table doesn't close an
# open paragraph: public identifiers by their lowercased start, alone or with a
# system identifier. Any other doctype counts as quirks, which hides more.
_STANDARD_DOCTYPES = (
    "-//w3c//dtd html 4.01//",
    "-//w3c//dtd xhtml 1.0 frameset//",
    "-//w3c//dtd xhtml 1.0 strict//",
    "-//w3c//dtd xhtml 1.0 transitional//",
    "-//w3c//dtd xhtml 1.1//",
)
_STANDARD_WITH_SYSTEM = (
    "-//w3c//dtd html 4.01 frameset//",
    "-//w3c//dtd html 4.01 transitional//",
)
_QUIRKS_SYSTEM = "http://www.ibm.com/data/dtd/v11/ibmxhtml1-transitional.dtd"
_DOCTYPE_RE = re.compile(
    r"""doctype\s+html(?:\s+(public|system)\s*("[^"]*"|'[^']*')"""
    r"""(?:\s*("[^"]*"|'[^']*'))?)?\s*""",
    re.IGNORECASE,
)


def _quirks(decl: str) -> bool:
    """Tell whether browsers may read a page with this doctype in quirks mode."""
    if not (match := _DOCTYPE_RE.fullmatch(decl)):
        return True
    keyword, public, system = match.groups()
    if keyword is None:
        return False
    first = public[1:-1].lower()
    second = system[1:-1].lower() if system else None
    if keyword.lower() == "system":
        return second is not None or first == _QUIRKS_SYSTEM
    if second == _QUIRKS_SYSTEM:
        return True
    return not (
        first.startswith(_STANDARD_DOCTYPES)
        or (second is not None and first.startswith(_STANDARD_WITH_SYSTEM))
    )


# Kinds of the elements open in svg or math content. HTML integration points
# (_POINT) and MathML text integration points (_TEXT) hold HTML; _ANNOT is an
# annotation-xml element that doesn't.
_FOREIGN, _POINT, _TEXT, _ANNOT, _HTML = range(5)
# HTML start tags that close svg and math elements until HTML holds again.
_BREAKOUT = frozenset(
    {
        "b",
        "big",
        "blockquote",
        "body",
        "br",
        "center",
        "code",
        "dd",
        "div",
        "dl",
        "dt",
        "em",
        "embed",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "head",
        "hr",
        "i",
        "img",
        "li",
        "listing",
        "menu",
        "meta",
        "nobr",
        "ol",
        "p",
        "pre",
        "ruby",
        "s",
        "small",
        "span",
        "strike",
        "strong",
        "sub",
        "sup",
        "table",
        "tt",
        "u",
        "ul",
        "var",
    }
)
_SVG_POINTS = frozenset({"desc", "foreignobject", "title"})
_MATH_TEXT = frozenset({"mi", "mn", "mo", "ms", "mtext"})
_HTML_ENCODINGS = frozenset({"application/xhtml+xml", "text/html"})
# HTML elements whose parsing isn't modelled in svg or math content (formatting
# elements, tables, forms, select and ruby). The rest of the content is then
# skipped by tag name alone, as before namespaces were tracked.
_UNSURE = frozenset(
    {
        "a",
        "b",
        "big",
        "caption",
        "code",
        "col",
        "colgroup",
        "em",
        "font",
        "form",
        "frameset",
        "i",
        "nobr",
        "optgroup",
        "option",
        "plaintext",
        "rb",
        "rp",
        "rt",
        "rtc",
        "s",
        "select",
        "small",
        "strike",
        "strong",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "tt",
        "u",
    }
)
# The special elements and scope barriers among HTML elements in svg or math.
_REGION_SPECIAL = _SPECIAL | (_SKIP_TAGS - {"svg", "math"})
_REGION_BARRIERS = frozenset(
    {"applet", "caption", "marquee", "object", "table", "td", "template", "th"}
)
# The table parts a table part's end tag may close with it.
_TABLE_INNER: dict[str, tuple[str, ...]] = {
    "tr": ("td", "th"),
    "tbody": ("tr", "td", "th"),
    "thead": ("tr", "td", "th"),
    "tfoot": ("tr", "td", "th"),
}

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


class _Formatting:
    """A formatting element browsers may open again, and where it's open."""

    __slots__ = ("add", "attrs", "keep", "order", "position", "tag")

    def __init__(
        self,
        tag: str,
        keep: int,
        add: int,
        attrs: frozenset[tuple[str, str]],
        position: int,
        order: int,
    ) -> None:
        self.tag = tag
        self.keep = keep
        self.add = add
        self.attrs = attrs
        # Its position on the stack, or None once it's closed.
        self.position: int | None = position
        # How many formatting elements were listed up to this one.
        self.order = order


def _remove(items: list[Any], item: object) -> None:
    """Remove ``item`` itself from ``items``, looking from the end."""
    for index in range(len(items) - 1, -1, -1):
        if items[index] is item:
            del items[index]
            return


class _TextExtractor(HTMLParser):
    """Collect the text and links a reader sees in HTML.

    Open elements are kept on one stack with their state, which combines the
    parent's state with the element's inline style and ``hidden`` attribute
    (see ``css``). Text, links and image alt texts are kept only while the
    state shows them. Unclosed elements are closed as browsers do for lists,
    paragraphs, table parts and options, and formatting elements closed early
    are opened again before the next text or inline element. Table parts
    outside a table are ignored, and without a standard doctype a table stays
    in an open paragraph, as in quirks mode. Other repairs aren't emulated.
    Browsers add a later html or body tag's attributes to the page's root
    elements, so ``html_to_text`` reads the HTML again when one changes the
    state of what came before it.

    svg and math content is never shown, but browsers parse it differently:
    its elements close themselves, and its style, script and title elements
    hold markup. Only integration points such as foreignObject hold HTML, and
    some HTML start tags break out of it. Its elements are tracked with their
    namespace, except inside noscript. HTML whose repairs aren't modelled there
    (formatting elements, tables, forms, implied closes) makes the rest of it
    fall back to skipping by tag name; it then ends only once the elements
    opened in it are closed by their end tags, in order.

    noscript content is skipped too. Browsers with scripting on read it as raw
    text, so inside it only </noscript> ends anything; nested elements still
    count, as with scripting off. Either way, it ends no earlier than in both.
    """

    def __init__(
        self, root_attrs: Mapping[str, Mapping[str, str]] | None = None
    ) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.size = 0
        self.links: list[Link] = []
        self._skip: list[str] = []
        self._skipping: Counter[str] = Counter()
        self._in_head = False
        # Once the body has started, browsers ignore <head>.
        self._head_done = False
        self._too_deep = False
        # Open elements as (tag, state), innermost last, with the positions of
        # each tag, of the special elements and of the scope barriers.
        self._stack: list[tuple[str, int]] = []
        self._open: dict[str, list[int]] = {}
        self._special: list[int] = []
        self._stops: list[int] = []
        self._barriers: list[int] = []
        # Formatting elements browsers open again (see _reconstruct), with None
        # for the markers that cells, captions, applets and marquees add; the
        # open ones by stack position; the listed ones by tag, and by tag and
        # attributes; and the markers as their element's position and the
        # number of formatting elements listed before them.
        self._formatting: list[_Formatting | None] = []
        self._listed: dict[int, _Formatting] = {}
        self._by_tag: dict[str, list[_Formatting]] = {}
        self._alike: dict[
            tuple[str, frozenset[tuple[str, str]]], list[_Formatting]
        ] = {}
        self._markers: list[tuple[int, int]] = []
        self._listings = 0
        # The attributes of the html and body elements, which may be known from
        # a first reading, and whether one read later changed what came before.
        self.root_attrs: dict[str, dict[str, str]] = {
            root: dict(root_attrs.get(root, {})) if root_attrs else {}
            for root in ("html", "body")
        }
        self.root_late = False
        self._root = self._root_state()
        self._pre = 0
        self._href: str | None = None
        self._link_seen = False
        self._link_text: list[str] = []
        self._link_alt: str = ""
        self._line_start = True
        # An svg or math region: its root's position in _skip, and its open
        # elements as (tag, namespace, kind), with the positions of each tag,
        # of the special elements and of the scope barriers.
        self._region_at = -1
        self._unsure = False
        self._fstack: list[tuple[str, str, int]] = []
        self._f_named: dict[str, list[int]] = {}
        self._h_named: dict[str, list[int]] = {}
        self._h_all: list[int] = []
        self._f_special: list[int] = []
        self._f_barriers: list[int] = []
        self._as_foreign = False
        # Elements opened while the region is skipped by tag name, with the
        # depth of _skip they opened at.
        self._u_open: list[tuple[str, int]] = []
        # Quirks mode, unless a standard doctype comes before the content.
        self._quirks = True
        self._begun = False

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
            index = len(self._stack)
            if (entry := self._listed.pop(index, None)) is not None:
                entry.position = None
            elif self._markers and self._markers[-1][0] == index:
                # The formatting elements opened in a cell, caption, applet or
                # marquee end with it.
                self._markers.pop()
                while self._formatting and (last := self._formatting[-1]) is not None:
                    self._unlist(last)
                if self._formatting:
                    self._formatting.pop()

    def _reconstruct(self) -> None:
        """Open the formatting elements closed early again, as browsers do."""
        closed: list[_Formatting] = []
        for entry in reversed(self._formatting):
            if entry is None or entry.position is not None:
                break
            closed.append(entry)
        for entry in reversed(closed):
            position = len(self._stack)
            self._push(entry.tag, (self._state() & entry.keep) | entry.add)
            if self._too_deep:
                return
            entry.position = position
            self._listed[position] = entry

    def _marker_order(self) -> int:
        """Return how many formatting elements were listed before the last marker."""
        return self._markers[-1][1] if self._markers else 0

    def _last_entry(self, tag: str) -> _Formatting | None:
        """Return the last formatting ``tag`` listed after the last marker."""
        entries = self._by_tag.get(tag)
        if entries and entries[-1].order > self._marker_order():
            return entries[-1]
        return None

    def _unlist(self, entry: _Formatting) -> None:
        if entry.position is not None:
            self._listed.pop(entry.position, None)
        _remove(self._formatting, entry)
        same_tag = self._by_tag[entry.tag]
        _remove(same_tag, entry)
        if not same_tag:
            del self._by_tag[entry.tag]
        key = (entry.tag, entry.attrs)
        alike = self._alike[key]
        _remove(alike, entry)
        if not alike:
            del self._alike[key]

    def _list(
        self, tag: str, keep: int, add: int, attrs: list[tuple[str, str | None]]
    ) -> None:
        """List the formatting element just opened, as browsers do."""
        # The attributes as parsed: the first of a name counts.
        parsed = frozenset({k: v or "" for k, v in reversed(attrs)}.items())
        alike = self._alike.get((tag, parsed))
        if alike and len(alike) >= 3 and alike[-3].order > self._marker_order():
            # Browsers keep three alike after the last marker.
            self._unlist(alike[-3])
        self._listings += 1
        position = len(self._stack) - 1
        listed = _Formatting(tag, keep, add, parsed, position, self._listings)
        self._formatting.append(listed)
        self._listed[position] = listed
        self._by_tag.setdefault(tag, []).append(listed)
        self._alike.setdefault((tag, parsed), []).append(listed)

    def _close_formatting(self, tag: str) -> int:
        """Return the position a formatting end tag closes, or -1, as browsers do."""
        top = len(self._stack) - 1
        if top >= 0 and self._stack[top][0] == tag and top not in self._listed:
            return top
        entry = self._last_entry(tag)
        if entry is None:
            return self._end_target(tag)
        position = entry.position
        if position is None:
            self._unlist(entry)
            return -1
        if self._special and self._special[-1] > position:
            # Out of scope, or browsers move what's inside it: it stays open,
            # which hides more.
            return -1
        self._unlist(entry)
        return position

    def _close_implied(self, tag: str) -> None:
        """Close the elements that a start tag ends without an end tag."""
        if tag in ("li", "dd", "dt") and self._stops:
            open_tag = self._stack[self._stops[-1]][0]
            if open_tag == tag or (tag != "li" and open_tag in ("dd", "dt")):
                self._pop_to(self._stops[-1])
        # In quirks mode a table stays in the paragraph.
        if tag in _CLOSES_P and not (tag == "table" and self._quirks):
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
        target = (
            max(map(self._last, _HEADINGS)) if tag in _HEADINGS else self._last(tag)
        )
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

    def _root_state(self) -> int:
        state = 0
        for root in ("html", "body"):
            found = self.root_attrs[root]
            keep, add = masks(root, found.get("style"), found.get("hidden"))
            state = (state & keep) | add
        return state

    def _set_root(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Merge repeated html and body tags' attributes; the first one wins."""
        merged = self.root_attrs[tag]
        changed = False
        for name, value in attrs:
            if name in ("style", "hidden") and name not in merged:
                merged[name] = value or ""
                changed = True
        if changed:
            state = self._root_state()
            # Browsers apply it to the whole page, so also to what came before.
            if state != self._root and (
                self.parts or self.links or self._stack or self._href is not None
            ):
                self.root_late = True
            self._root = state

    def _start_body(self) -> None:
        if not self._skip:
            self._in_head = False
            self._head_done = True

    def _h_last(self, tag: str) -> int:
        """Return the position of the region's innermost open HTML ``tag``, or -1."""
        positions = self._h_named.get(tag)
        return positions[-1] if positions else -1

    def _f_push(self, tag: str, namespace: str, kind: int) -> None:
        position = len(self._fstack)
        if self._region_at + position >= MAX_DEPTH:
            self._too_deep = True
            return
        self._fstack.append((tag, namespace, kind))
        if kind == _HTML:
            self._h_named.setdefault(tag, []).append(position)
            self._h_all.append(position)
            special = tag in _REGION_SPECIAL
            barrier = tag in _REGION_BARRIERS
        else:
            self._f_named.setdefault(tag, []).append(position)
            # Integration points and annotation-xml are special scope barriers.
            special = barrier = kind != _FOREIGN
        if special:
            self._f_special.append(position)
        if barrier:
            self._f_barriers.append(position)

    def _f_pop_to(self, position: int) -> None:
        """Close the region's element at ``position`` and everything inside it."""
        while len(self._fstack) > position:
            index = len(self._fstack) - 1
            tag, _, kind = self._fstack.pop()
            if kind == _HTML:
                self._h_named[tag].pop()
                self._h_all.pop()
            else:
                self._f_named[tag].pop()
            if self._f_special and self._f_special[-1] == index:
                self._f_special.pop()
            if self._f_barriers and self._f_barriers[-1] == index:
                self._f_barriers.pop()
        if not self._fstack:
            self._end_region()

    def _pop_foreign(self) -> None:
        """Close svg and math elements until HTML holds, as HTML start tags do."""
        position = len(self._fstack)
        while position and self._fstack[position - 1][2] in (_FOREIGN, _ANNOT):
            position -= 1
        self._f_pop_to(position)

    def _clear_region(self) -> None:
        self._fstack.clear()
        self._f_named.clear()
        self._h_named.clear()
        self._h_all.clear()
        self._f_special.clear()
        self._f_barriers.clear()

    def _end_region(self) -> None:
        """Close the region's root and whatever is open in it."""
        while len(self._skip) > self._region_at:
            self._skipping[self._skip.pop()] -= 1
        self._clear_region()
        self._region_at = -1

    def _go_unsure(self) -> None:
        """Skip the rest of the region by tag name alone."""
        for tag, _, kind in self._fstack[1:]:
            if tag in _SKIP_TAGS:
                self._skip.append(tag)
                self._skipping[tag] += 1
            elif kind == _HTML:
                self._u_open.append((tag, len(self._skip)))
        self._clear_region()
        self._unsure = True

    @staticmethod
    def _kind(namespace: str, tag: str, attrs: list[tuple[str, str | None]]) -> int:
        if namespace == "svg":
            return _POINT if tag in _SVG_POINTS else _FOREIGN
        if tag in _MATH_TEXT:
            return _TEXT
        if tag == "annotation-xml":
            encoding = next((v for k, v in attrs if k == "encoding"), None) or ""
            return _POINT if encoding.lower() in _HTML_ENCODINGS else _ANNOT
        return _FOREIGN

    def _raw_text(self, tag: str) -> None:
        # Browsers ignore the slash here: raw text still runs to the end tag.
        if tag in self.CDATA_CONTENT_ELEMENTS or tag == "plaintext":
            self.set_cdata_mode(tag)
        elif tag in self.RCDATA_CONTENT_ELEMENTS:
            self.set_cdata_mode(tag, escapable=True)

    def set_cdata_mode(self, elem: str, *, escapable: bool = False) -> None:
        # svg and math elements hold markup, whatever their name.
        if not self._as_foreign:
            super().set_cdata_mode(elem, escapable=escapable)

    def _closes_open(self, tag: str) -> bool:
        """Tell whether a start tag may close an HTML element open in the region."""
        named = self._h_named
        return bool(
            ((tag in _CLOSES_P or tag == "xmp") and named.get("p"))
            or (tag == "li" and named.get("li"))
            or (tag in ("dd", "dt") and (named.get("dd") or named.get("dt")))
            or (tag in _HEADINGS and any(named.get(h) for h in _HEADINGS))
            or (tag == "button" and named.get("button"))
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._as_foreign = False
        self._start(tag, attrs, closed=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._as_foreign = False
        self._start(tag, attrs, closed=True)

    def _start(
        self, tag: str, attrs: list[tuple[str, str | None]], *, closed: bool
    ) -> None:
        self._begun = True
        if self._too_deep:
            return
        if (
            self._region_at >= 0
            and not self._unsure
            and self._region_start(tag, attrs, closed=closed)
        ):
            return
        if closed:
            self._outer_closed(tag, attrs)
        else:
            self._outer_start(tag, attrs)

    def _outer_start(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("body", "html"):
            if not self._skip:
                self._in_head = False
                self._head_done = self._head_done or tag == "body"
            # Browsers ignore them in a template. svg or math content is open
            # here only when it's skipped by tag name; a body tag may break out
            # of it.
            foreign = self._skipping["svg"] or self._skipping["math"]
            if foreign or not self._skipping["template"]:
                self._set_root(tag, attrs)
            return
        if tag == "head":
            self._in_head = self._in_head or not (self._skip or self._head_done)
            return
        if tag not in _HEAD_TAGS:
            self._start_body()
        if tag in _SKIP_TAGS:
            if tag in _RECONSTRUCT_SKIPPED and not (self._skip or self._in_head):
                self._reconstruct()
            if self._too_deep or len(self._skip) >= MAX_DEPTH:
                self._too_deep = True
                return
            # Not in noscript: browsers with scripting on read it as raw text.
            region = (
                tag in ("svg", "math")
                and self._region_at < 0
                and not self._skipping["noscript"]
            )
            if region:
                self._region_at = len(self._skip)
            self._skip.append(tag)
            self._skipping[tag] += 1
            if region:
                self._f_push(tag, tag, _FOREIGN)
            return
        if self._skip or self._in_head:
            if (
                self._unsure
                and tag not in _VOID_TAGS
                and not self._skipping["noscript"]
            ):
                # What opens here keeps the region open until it's closed.
                if len(self._u_open) >= MAX_DEPTH:
                    self._too_deep = True
                    return
                self._u_open.append((tag, len(self._skip)))
            return
        if tag in _TABLE_PARTS and self._last("table") < 0:
            # Browsers ignore table parts outside a table. Words stay apart.
            if not self._state() & GONE:
                if tag in _BLOCK_TAGS:
                    self._break()
                elif tag in _CELL_TAGS:
                    self._emit(" ")
            return
        self._close_implied(tag)
        if tag == "a" and (entry := self._last_entry("a")) is not None:
            # Browsers close the open link first. Here one around a block stays
            # open, which hides more.
            position = entry.position
            self._unlist(entry)
            if position is not None and not (
                self._special and self._special[-1] > position
            ):
                self._pop_to(position)
        if tag not in _NO_RECONSTRUCT:
            self._reconstruct()
            if tag == "nobr" and self._last("nobr") > (
                self._barriers[-1] if self._barriers else -1
            ):
                if (target := self._close_formatting(tag)) >= 0:
                    self._pop_to(target)
                self._reconstruct()
            if self._too_deep:
                return
        keep, add = element_masks(tag, attrs)
        state = (self._state() & keep) | add
        if tag not in _VOID_TAGS:
            self._push(tag, state)
            if self._too_deep:
                return
            if tag in _FORMATTING:
                self._list(tag, keep, add, attrs)
            elif tag in ("applet", "marquee") or (
                tag in ("caption", "td", "th") and self._last("table") >= 0
            ):
                self._markers.append((len(self._stack) - 1, self._listings))
                self._formatting.append(None)
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

    def _outer_closed(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("svg", "math"):
            # Only foreign elements really close themselves.
            self._start_body()
            if not (self._skip or self._in_head):
                self._reconstruct()
            return
        self._outer_start(tag, attrs)
        if not (self._skipping["svg"] or self._skipping["math"]):
            self._raw_text(tag)

    def _region_start(
        self, tag: str, attrs: list[tuple[str, str | None]], *, closed: bool
    ) -> bool:
        """Apply a start tag in svg or math content; False leaves it to the rest."""
        _, namespace, kind = self._fstack[-1]
        if not (
            kind in (_HTML, _POINT)
            or (kind == _TEXT and tag not in ("mglyph", "malignmark"))
            or (kind == _ANNOT and tag == "svg")
        ):
            if tag not in _BREAKOUT and not (
                tag == "font" and any(k in ("color", "face", "size") for k, _ in attrs)
            ):
                if not closed:
                    self._f_push(tag, namespace, self._kind(namespace, tag, attrs))
                self._as_foreign = True
                return True
            self._pop_foreign()
            if self._region_at < 0:
                return False
        if tag in ("svg", "math"):
            if not closed:
                self._f_push(tag, tag, _FOREIGN)
            return True
        if tag in ("body", "html"):
            if not (self._skipping["template"] or self._h_named.get("template")):
                self._set_root(tag, attrs)
            return True
        if tag == "head":
            return True
        if tag in _UNSURE or self._closes_open(tag):
            self._go_unsure()
            if closed:
                self._raw_text(tag)
            return False
        if tag not in _VOID_TAGS:
            self._f_push(tag, "html", _HTML)
            if closed:
                self._raw_text(tag)
        return True

    def handle_endtag(self, tag: str) -> None:
        self._begun = True
        if self._too_deep:
            return
        if tag == "head":
            # It closes nothing: an open noscript or template stays hidden.
            self._in_head = False
            return
        if self._region_at >= 0 and not self._unsure and self._region_end(tag):
            return
        if tag in _SKIP_TAGS:
            if self._skipping[tag]:
                if self._skipping["noscript"] and tag != "noscript":
                    # Browsers with scripting on read noscript as raw text;
                    # nested elements still count, as with scripting off.
                    return
                if self._u_open and tag != "template":
                    # Browsers ignore it while what opened in it is open.
                    at = len(self._skip) - 1 - self._skip[::-1].index(tag)
                    if self._u_open[-1][1] > at:
                        return
                while (open_tag := self._skip.pop()) != tag:
                    self._skipping[open_tag] -= 1
                self._skipping[tag] -= 1
                while self._u_open and self._u_open[-1][1] > len(self._skip):
                    self._u_open.pop()
                if self._unsure and len(self._skip) <= self._region_at:
                    self._unsure = False
                    self._region_at = -1
            return
        if self._u_open and self._u_open[-1] == (tag, len(self._skip)):
            self._u_open.pop()
        if self._skip or self._in_head or tag in ("body", "html"):
            return
        if tag == "br":
            # Read as <br>, which opens formatting elements again.
            self._reconstruct()
            if self._too_deep:
                return
        if tag in _FORMATTING:
            target = self._close_formatting(tag)
        elif tag == "form":
            target = self._end_target(tag)
            # Browsers take only the form off the stack, once paragraphs and
            # list items in it are closed; if more is open in it, the form
            # stays open here, which hides more.
            if target >= 0 and any(
                open_tag not in _IMPLIED_END
                for open_tag, _ in self._stack[target + 1 :]
            ):
                target = -1
        else:
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

    def _region_end(self, tag: str) -> bool:
        """Apply an end tag in svg or math content; False leaves it to the rest."""
        if self._fstack[-1][2] != _HTML:
            if tag in ("p", "br"):
                self._pop_foreign()
                if self._region_at < 0:
                    return False
                if tag == "p":
                    self._region_close_p()
                return True
            named = self._f_named.get(tag)
            f = named[-1] if named else -1
            h = self._h_all[-1] if self._h_all else -1
            if f > h:
                self._f_pop_to(f)
                return True
            if h < 0:
                return self._region_end_outside(tag)
        return self._region_end_html(tag)

    def _region_close_p(self) -> None:
        p = self._h_last("p")
        if p >= 0 and p > max(self._f_barriers[-1], self._h_last("button")):
            self._f_pop_to(p)

    def _end_table_part(self, tag: str) -> bool:
        if self._table_consistent(tag):
            self._end_region()
        else:
            self._go_unsure()
        return False

    def _region_end_html(self, tag: str) -> bool:
        """Apply an end tag that HTML's rules handle in the region."""
        if tag == "template":
            if (template := self._h_last("template")) >= 0:
                self._f_pop_to(template)
            elif self._skipping["template"]:
                self._end_region()
                return False
            return True
        if tag in ("body", "html", "br", "form", "colgroup"):
            return True
        if tag == "p":
            self._region_close_p()
            return True
        if tag in _TABLE_SCOPED:
            return True if self._h_named.get("template") else self._end_table_part(tag)
        if tag in _HEADINGS:
            target = max(map(self._h_last, _HEADINGS))
            if target >= 0 and target >= self._f_barriers[-1]:
                self._f_pop_to(target)
            return True
        target = self._h_last(tag)
        if target < 0:
            return True
        if tag in _REGION_SPECIAL and tag != "noscript":
            scope = self._f_barriers[-1]
            if tag == "li":
                scope = max(scope, self._h_last("ol"), self._h_last("ul"))
        else:
            # Other end tags stop at the innermost special element. noscript is
            # read as markup here; browsers with scripting on read raw text.
            scope = self._f_special[-1]
        if target >= scope:
            self._f_pop_to(target)
        return True

    def _region_end_outside(self, tag: str) -> bool:
        """Apply an end tag that HTML's rules handle outside the region."""
        if self._region_at == 0:
            if tag in ("body", "html", "form", "colgroup") or tag in _SKIP_TAGS:
                return True
            if tag in _TABLE_SCOPED:
                return self._end_table_part(tag)
            entry = self._last_entry(tag) if tag in _FORMATTING else None
            if entry is not None:
                # Browsers close a formatting element in scope around the
                # region, and the region with it, even past a special element.
                position = entry.position
                if position is None:
                    self._unlist(entry)
                    return True
                if self._f_special or (
                    self._barriers and self._barriers[-1] > position
                ):
                    return True
            elif self._f_special or self._end_target(tag) < 0:
                return True
        elif tag == "template":
            if not self._skipping["template"]:
                return True
        elif tag in ("object", "noscript"):
            if self._f_special or not self._skipping[tag]:
                return True
        else:
            self._go_unsure()
            return False
        self._end_region()
        return False

    def _table_consistent(self, tag: str) -> bool:
        """Tell whether ending the region before a table end tag matches browsers."""
        target = self._end_target(tag)
        if tag == "table":
            return target >= 0
        table = self._last("table")
        # _end_target accepts any open part when no table is open.
        if table < 0 or target <= table:
            return False
        inner = _TABLE_INNER.get(tag, ())
        return all(
            self._last(part) <= target or part in inner for part in _TABLE_SCOPED
        )

    def handle_decl(self, decl: str) -> None:
        # Only a doctype before the content sets the mode.
        if not self._begun:
            self._quirks = _quirks(decl)
        self._begun = True

    def handle_data(self, data: str) -> None:
        if self._too_deep:
            return
        if not self._begun and data.strip(_HTML_SPACE):
            self._begun = True
        if not self._head_done and not self._skip and data.strip():
            self._in_head = False
            self._head_done = True
        if self._skip or self._in_head:
            return
        if (
            data
            and self._formatting
            and (
                data.strip(_HTML_SPACE)
                or not self._stack
                or self._stack[-1][0] not in _TABLE_TEXT_PARTS
                or self._last("table") < 0
            )
        ):
            self._reconstruct()
            if self._too_deep:
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
    parser = _extract(html)
    if parser.root_late:
        # A later html or body tag's style also applies to the text before it,
        # so read the HTML again with the page's final root attributes.
        parser = _extract(html, parser.root_attrs)
    return _clean_text("".join(parser.parts)), tuple(parser.links)


def _extract(
    html: str, root_attrs: Mapping[str, Mapping[str, str]] | None = None
) -> _TextExtractor:
    parser = _TextExtractor(root_attrs)
    # Malformed HTML keeps whatever was read before the error.
    with contextlib.suppress(Exception):
        parser.feed(html[:MAX_HTML_CHARS])
        parser.close()
    parser.finish_link()
    return parser


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
