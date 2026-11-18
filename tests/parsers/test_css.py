"""Tests for reading the inline styles that hide text."""

from __future__ import annotations

import pytest

from custom_components.parcels.parsers.css import declarations


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (" Display : NONE ! Important ; display: block", {"display": "none"}),
        ("display:none !important;display:block !important", {"display": "show"}),
        ("display:inline flow-root", {"display": "show"}),
        ("display:block block", {}),
        ("display:revert-layer", {"display": "revert"}),
        ("visibility:inherit", {"visibility": "keep"}),
        ("font-size:0.0em", {"font-size": "zero"}),
        ("font-size:-0px", {"font-size": "zero"}),
        ("font-size:-2px", {}),
        ("font-size:12", {}),
        ("font-size:12furlongs", {}),
        ("font-size:150%", {"font-size": "keep"}),
        ("font-size:smaller", {"font-size": "keep"}),
        ("font-size:2vmin", {"font-size": "show"}),
        ("font-size:1.2REM", {"font-size": "show"}),
        ("font-size:xx-small", {"font-size": "show"}),
        ("max-height:0%", {"max-height": "zero"}),
        ("height:calc(10px - 10px)", {"height": "other"}),
        ("height:fit-content", {"height": "other"}),
        ("height:5", {}),
        ("overflow:hidden auto", {"overflow": "clip"}),
        ("overflow-y:visible", {"overflow-y": "other"}),
        ("overflow:hidden hidden hidden", {}),
        ("font-size:0e3px", {"font-size": "zero"}),
        ("font-size:" + "0" * 100 + "px", {"font-size": "zero"}),
        ("font-size:0;font-size:1.px", {"font-size": "zero"}),
        ("color:red;opacity:0;mso-hide:all;display", {}),
    ],
)
def test_declarations(style: str, expected: dict[str, str]) -> None:
    """Only valid values of the properties that hide text are read."""
    assert declarations(style) == expected
