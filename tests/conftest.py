"""Shared fixtures for Parcels tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request: pytest.FixtureRequest) -> None:
    """Let Home Assistant load the integration in tests that use hass."""
    if "hass" in request.fixturenames:
        request.getfixturevalue("enable_custom_integrations")
