"""Tests for the working days of return pickups."""

from __future__ import annotations

from datetime import date
import sys
from types import SimpleNamespace

from homeassistant.core import HomeAssistant
import pytest

from custom_components.parcels.workdays import WorkingDays

TODAY = date(2026, 11, 20)
# Tuesday 1 and Tuesday 8 December 2026 are public holidays in Portugal.
PT_HOLIDAYS = {
    date(2026, 12, 1): "Restauração da Independência",
    date(2026, 12, 8): "Imaculada Conceição",
}


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[int]]]:
    """Install a holidays package that knows Portugal only."""
    found: list[tuple[str, list[int]]] = []

    def country_holidays(country: str, years: list[int]) -> dict[date, str]:
        found.append((country, years))
        if country != "PT":
            raise NotImplementedError(f"Country {country} not available")
        return dict(PT_HOLIDAYS)

    monkeypatch.setitem(
        sys.modules, "holidays", SimpleNamespace(country_holidays=country_holidays)
    )
    return found


async def test_public_holidays_are_not_working_days(
    hass: HomeAssistant, calls: list[tuple[str, list[int]]]
) -> None:
    """The holidays of Home Assistant's country are skipped, then weekends."""
    hass.config.country = "PT"
    days = WorkingDays(hass)

    await days.async_load(TODAY)

    assert calls == [("PT", [2025, 2026, 2027])]
    assert days.source == "holidays:PT"
    assert days.next_working_day(date(2026, 11, 30)) == date(2026, 12, 2)
    assert days.next_working_day(date(2026, 12, 7)) == date(2026, 12, 9)
    assert days.next_working_day(date(2026, 11, 20)) == date(2026, 11, 23)

    await days.async_load(date(2026, 12, 31))
    assert len(calls) == 1
    await days.async_load(date(2027, 1, 1))
    assert calls[-1] == ("PT", [2026, 2027, 2028])


@pytest.mark.parametrize(("country", "asked"), [(None, 0), ("XX", 1)])
async def test_monday_to_friday_for_an_unknown_country(
    hass: HomeAssistant,
    calls: list[tuple[str, list[int]]],
    country: str | None,
    asked: int,
) -> None:
    """Without a country the holidays package knows, it's Monday to Friday."""
    hass.config.country = country
    days = WorkingDays(hass)

    await days.async_load(TODAY)

    assert len(calls) == asked
    assert days.source == "weekdays"
    assert days.next_working_day(date(2026, 11, 30)) == date(2026, 12, 1)
    assert days.next_working_day(date(2026, 11, 20)) == date(2026, 11, 23)


async def test_monday_to_friday_without_the_holidays_package(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parcels doesn't require the holidays package."""
    monkeypatch.setitem(sys.modules, "holidays", None)
    hass.config.country = "PT"
    days = WorkingDays(hass)

    await days.async_load(TODAY)

    assert days.source == "weekdays"
    assert days.next_working_day(date(2026, 11, 30)) == date(2026, 12, 1)
