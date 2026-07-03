"""Abstract base classes (protocols) for pybhav's extensibility points.

Each ABC defines a single, narrow contract. Implement any of them and
inject your implementation into ``NSEBhavcopy`` via its constructor to
swap behaviour without touching library code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Existing protocols
# ---------------------------------------------------------------------------

class BhavcopCache(ABC):
    """Interface for a bhavcopy data cache keyed by (segment, date)."""

    @abstractmethod
    def has(self, segment: str, dt: date) -> bool: ...

    @abstractmethod
    def get(self, segment: str, dt: date) -> bytes: ...

    @abstractmethod
    def put(self, segment: str, dt: date, data: bytes) -> None: ...


class BhavcopFetcher(ABC):
    """Interface for fetching raw bhavcopy CSV bytes."""

    @abstractmethod
    def fetch(self, segment: str, dt: date) -> bytes: ...


class AsyncBhavcopFetcher(ABC):
    """Interface for fetching raw bhavcopy CSV bytes asynchronously."""

    @abstractmethod
    async def fetch(self, segment: str, dt: date) -> bytes: ...


class BhavcopParser(ABC):
    """Interface for parsing raw bhavcopy bytes into a DataFrame."""

    @abstractmethod
    def parse(self, data: bytes) -> pd.DataFrame: ...


# ---------------------------------------------------------------------------
# New protocols
# ---------------------------------------------------------------------------

class BhavcopCalendar(ABC):
    """Interface for an NSE trading-day calendar.

    Implement this to plug in a custom holiday source — for example, a
    calendar that fetches the official list from NSE's API — without
    modifying any other pybhav code.

    The concrete default is :class:`pybhav.holidays.NSEHolidayCalendar`.
    """

    @abstractmethod
    def is_holiday(self, dt: date) -> bool:
        """Return ``True`` if *dt* is a listed public holiday (not a weekend)."""
        ...

    @abstractmethod
    def is_weekend(self, dt: date) -> bool:
        """Return ``True`` if *dt* falls on a Saturday or Sunday."""
        ...

    @abstractmethod
    def is_trading_day(self, dt: date) -> bool:
        """Return ``True`` if *dt* is a weekday that is not a public holiday."""
        ...

    @abstractmethod
    def holiday_name(self, dt: date) -> Optional[str]:
        """Return the occasion name for *dt*, or ``None`` if it is not a holiday."""
        ...

    @abstractmethod
    def next_trading_day(self, dt: date, *, inclusive: bool = False) -> date:
        """Return the next NSE trading day at or after *dt*."""
        ...

    @abstractmethod
    def previous_trading_day(self, dt: date, *, inclusive: bool = False) -> date:
        """Return the most recent NSE trading day at or before *dt*."""
        ...


class BhavcopSchedule(ABC):
    """Interface for the bhavcopy publish-time schedule.

    Encapsulates the rule that decides *which* trading date's bhavcopy
    is currently available, decoupling that logic from both the client
    and the calendar.

    The concrete default is :class:`pybhav.schedule.NSEBhavSchedule`.
    """

    @abstractmethod
    def latest_trading_date(self, calendar: BhavcopCalendar) -> date:
        """Return the date of the bhavcopy that is currently downloadable.

        Args:
            calendar: The calendar used to determine valid trading days.
        """
        ...
