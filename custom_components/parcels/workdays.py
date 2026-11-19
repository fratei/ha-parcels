"""Working days, for the day a carrier picks up a customer return.

Monday to Friday, minus the public holidays of Home Assistant's country when
the holidays package is installed. Home Assistant's Workday and Holiday
integrations use that package; Parcels doesn't require it and falls back to
Monday to Friday without it.
"""

from __future__ import annotations

from datetime import date, timedelta
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

SOURCE_WEEKDAYS = "weekdays"
SOURCE_HOLIDAYS = "holidays"

_WEEKEND = frozenset({5, 6})
# A run of days off longer than this is a bad holiday list; stop looking.
_MAX_DAYS_OFF = 14


def _country_holidays(country: str, years: list[int]) -> frozenset[date]:
    """Return the public holidays of ``country`` in ``years``.

    Runs in the executor: importing the package and building a country's
    holidays read files.
    """
    import holidays

    return frozenset(holidays.country_holidays(country, years=years))


class WorkingDays:
    """Monday to Friday, minus the public holidays of Home Assistant's country."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Start with Monday to Friday until the holidays are loaded."""
        self.hass = hass
        self._holidays: frozenset[date] = frozenset()
        self._years: tuple[int, ...] = ()
        self.source = SOURCE_WEEKDAYS

    async def async_load(self, today: date) -> None:
        """Load the holidays of last year, this year and next year.

        Nothing is loaded again until the year changes. Without the holidays
        package, or for a country it doesn't know, it's Monday to Friday.
        """
        years = (today.year - 1, today.year, today.year + 1)
        if years == self._years:
            return
        self._years = years
        country = self.hass.config.country
        found: frozenset[date] = frozenset()
        source = SOURCE_WEEKDAYS
        if country:
            try:
                found = await self.hass.async_add_executor_job(
                    _country_holidays, country, list(years)
                )
            except ImportError:
                _LOGGER.debug("The holidays package isn't installed")
            except Exception as err:  # Never fail the hub's start over holidays.
                _LOGGER.debug("No public holidays: %s", type(err).__name__)
            else:
                source = f"{SOURCE_HOLIDAYS}:{country}"
        self._holidays = found
        self.source = source

    def is_working_day(self, day: date) -> bool:
        """Return True on a weekday that isn't a public holiday."""
        return day.weekday() not in _WEEKEND and day not in self._holidays

    def next_working_day(self, day: date) -> date:
        """Return the first working day after ``day``."""
        following = day + timedelta(days=1)
        for _ in range(_MAX_DAYS_OFF):
            if self.is_working_day(following):
                return following
            following += timedelta(days=1)
        return following
