"""Tell from an element's inline style whether a reader sees its text.

Only the element's own ``style`` and ``hidden`` attributes are read; rules
in ``<style>`` blocks, CSS escapes, comments and the ``font`` shorthand are
not. As in browsers, the last declaration of a property wins, ``!important``
beats a later normal one and a declaration whose value isn't understood is
ignored. A zero length counts as zero whatever its unit.
"""

from __future__ import annotations

from collections.abc import Iterable
import re

# The state of an element is 0 when its text shows, otherwise these flags.
GONE = 1  # display:none and the like: nothing inside shows again
INVISIBLE = 2  # visibility:hidden: a descendant can set visibility:visible
ZERO = 4  # font-size:0: a descendant can set a non-zero absolute size
ALL = GONE | INVISIBLE | ZERO

# A zero height or maximum height doesn't hide table parts: they grow to fit.
TABLE_PARTS = frozenset({"table", "tbody", "td", "tfoot", "th", "thead", "tr"})


_CSS_WIDE = frozenset({"inherit", "initial", "unset", "revert", "revert-layer"})
_DISPLAY_WORDS = frozenset(
    {
        "-moz-box",
        "-moz-inline-box",
        "-ms-flexbox",
        "-ms-grid",
        "-ms-inline-flexbox",
        "-ms-inline-grid",
        "-webkit-box",
        "-webkit-flex",
        "-webkit-inline-box",
        "-webkit-inline-flex",
        "block",
        "contents",
        "flex",
        "flow",
        "flow-root",
        "grid",
        "inline",
        "inline-block",
        "inline-flex",
        "inline-grid",
        "inline-list-item",
        "inline-table",
        "list-item",
        "math",
        "ruby",
        "ruby-base",
        "ruby-base-container",
        "ruby-text",
        "ruby-text-container",
        "run-in",
        "table",
        "table-caption",
        "table-cell",
        "table-column",
        "table-column-group",
        "table-footer-group",
        "table-header-group",
        "table-row",
        "table-row-group",
    }
)
_FONT_SIZE_SHOW = frozenset(
    {
        "initial",
        "large",
        "medium",
        "small",
        "x-large",
        "x-small",
        "xx-large",
        "xx-small",
        "xxx-large",
    }
)
_FONT_SIZE_KEEP = frozenset(
    {"inherit", "larger", "math", "revert", "revert-layer", "smaller", "unset"}
)
_HEIGHT_WORDS = _CSS_WIDE | {
    "-moz-available",
    "-webkit-fill-available",
    "auto",
    "fit-content",
    "max-content",
    "min-content",
    "none",
    "stretch",
}
_OVERFLOW_WORDS = _CSS_WIDE | {"auto", "clip", "hidden", "overlay", "scroll", "visible"}
_RELATIVE_UNITS = frozenset({"%", "cap", "ch", "em", "ex", "ic", "lh"})
_ABSOLUTE_UNIT_RE = re.compile(
    r"px|pt|pc|cm|mm|in|q|r(?:em|ex|ch|cap|ic|lh)"
    r"|[sld]?v(?:w|h|i|b|min|max)|cq(?:w|h|i|b|min|max)"
)
_LENGTH_RE = re.compile(r"([+-]?)((?:\d+(?:\.\d+)?|\.\d+)(?:e[+-]?\d+)?)([a-z]*|%)")
_FUNCTION_RE = re.compile(r"[a-z-]+\(.*\)")


def _length(value: str) -> tuple[float, str] | None:
    """Return a length's size and unit, or None if it isn't a valid length."""
    match = _LENGTH_RE.fullmatch(value)
    if match is None:
        return None
    sign, number, unit = match.groups()
    size = float(number)
    if sign == "-" and size:
        return None
    return size, unit


def _display(value: str) -> str | None:
    if value == "none":
        return "none"
    if value in ("revert", "revert-layer"):
        # Falls back to the browser's own style: hidden elements stay hidden.
        return "revert"
    if value in _CSS_WIDE:
        return "show"
    words = value.split(" ")
    if (
        len(words) <= 3
        and len(set(words)) == len(words)
        and all(word in _DISPLAY_WORDS for word in words)
    ):
        return "show"
    return None


def _visibility(value: str) -> str | None:
    if value in ("hidden", "collapse"):
        return "hide"
    if value in ("visible", "initial"):
        return "show"
    if value in _CSS_WIDE:
        return "keep"
    return None


def _font_size(value: str) -> str | None:
    if value in _FONT_SIZE_SHOW:
        return "show"
    if value in _FONT_SIZE_KEEP:
        return "keep"
    if (length := _length(value)) is None:
        return None
    size, unit = length
    if not size:
        return "zero"
    if unit in _RELATIVE_UNITS:
        # A share of the parent's size: zero stays zero.
        return "keep"
    if _ABSOLUTE_UNIT_RE.fullmatch(unit):
        return "show"
    return None


def _height(value: str) -> str | None:
    if value in _HEIGHT_WORDS or _FUNCTION_RE.fullmatch(value):
        return "other"
    if (length := _length(value)) is None:
        return None
    size, unit = length
    if not size:
        return "zero"
    return "other" if unit else None


def _overflow(value: str) -> str | None:
    words = value.split(" ")
    if len(words) > 2 or not all(word in _OVERFLOW_WORDS for word in words):
        return None
    return "clip" if "hidden" in words or "clip" in words else "other"


_READERS = {
    "display": _display,
    "font-size": _font_size,
    "height": _height,
    "max-height": _height,
    "overflow": _overflow,
    "overflow-y": _overflow,
    "visibility": _visibility,
}


def declarations(style: str) -> dict[str, str]:
    """Read the properties that can hide text from an inline style.

    Returns each property's winning value as a kind: ``none``, ``show``,
    ``revert``, ``hide``, ``keep``, ``zero``, ``other`` or ``clip``.
    """
    found: dict[str, tuple[str, bool]] = {}
    for declaration in style.split(";"):
        name, colon, value = declaration.partition(":")
        name = name.strip().lower()
        reader = _READERS.get(name)
        if not colon or reader is None:
            continue
        value = " ".join(value.split()).lower()
        important = False
        if value.endswith("important"):
            head = value[: -len("important")].rstrip()
            if head.endswith("!"):
                value, important = head[:-1].rstrip(), True
        if (kind := reader(value)) is None:
            continue
        if name in found and found[name][1] and not important:
            continue
        found[name] = (kind, important)
    return {name: kind for name, (kind, _) in found.items()}


def masks(tag: str, style: str | None, hidden: str | None) -> tuple[int, int]:
    """Return ``(keep, add)``: the element's state is ``parent & keep | add``.

    ``style`` and ``hidden`` are the element's attributes, None when absent
    and an empty string when present without a value.
    """
    if style is None and hidden is None:
        return ALL, 0
    found = declarations(style) if style else {}
    keep, add = ALL, 0
    display = found.get("display")
    if display == "none" or (
        hidden is not None and (display != "show" or hidden.lower() == "until-found")
    ):
        add |= GONE
    if (
        tag not in TABLE_PARTS
        and "zero" in (found.get("height"), found.get("max-height"))
        and "clip" in (found.get("overflow"), found.get("overflow-y"))
    ):
        add |= GONE
    visibility = found.get("visibility")
    if visibility == "hide":
        add |= INVISIBLE
    elif visibility == "show":
        keep &= ~INVISIBLE
    font_size = found.get("font-size")
    if font_size == "zero":
        add |= ZERO
    elif font_size == "show":
        keep &= ~ZERO
    return keep, add


def element_masks(tag: str, attrs: Iterable[tuple[str, str | None]]) -> tuple[int, int]:
    """Return ``(keep, add)`` for an element from its attributes.

    As in browsers, the first of repeated attributes counts.
    """
    style: str | None = None
    hidden: str | None = None
    for name, value in attrs:
        if name == "style":
            if style is None:
                style = value or ""
        elif name == "hidden" and hidden is None:
            hidden = value or ""
    return masks(tag, style, hidden)
