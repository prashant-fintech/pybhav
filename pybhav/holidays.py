"""NSE market holiday calendar.

Provides the :class:`NSEHolidayCalendar` which knows which dates the NSE is
closed so that callers can avoid making fruitless download requests.

Usage::

    from pybhav.holidays import NSEHolidayCalendar

    cal = NSEHolidayCalendar()
    cal.is_holiday(date(2025, 3, 14))   # True  — Holi
    cal.is_trading_day(date(2025, 3, 14))  # False
    cal.next_trading_day(date(2025, 3, 14))  # date(2025, 3, 17)  (skips weekend too)
    cal.trading_days_in_range(date(2025, 3, 10), date(2025, 3, 20))
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import FrozenSet, Iterator, Optional, Sequence


# ---------------------------------------------------------------------------
# Built-in holiday data (NSE CM segment — equities)
# Source: official NSE holiday circulars
# Each entry maps a date to its occasion name.
# ---------------------------------------------------------------------------

_HOLIDAYS_2024: dict[date, str] = {
    date(2024, 1, 26): "Republic Day",
    date(2024, 3, 8):  "Mahashivratri",
    date(2024, 3, 25): "Holi",
    date(2024, 3, 29): "Good Friday",
    date(2024, 4, 11): "Id-Ul-Fitr (Ramadan Eid)",
    date(2024, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2024, 4, 17): "Shri Ram Navami",
    date(2024, 5, 1):  "Maharashtra Day",
    date(2024, 6, 17): "Bakri Id",
    date(2024, 7, 17): "Moharram",
    date(2024, 8, 15): "Independence Day / Parsi New Year",
    date(2024, 10, 2): "Mahatma Gandhi Jayanti",
    date(2024, 11, 1): "Diwali Laxmi Pujan",
    date(2024, 11, 15): "Gurunanak Jayanti",
    date(2024, 12, 25): "Christmas",
}

_HOLIDAYS_2025: dict[date, str] = {
    date(2025, 2, 26): "Mahashivratri",
    date(2025, 3, 14): "Holi",
    date(2025, 3, 31): "Id-Ul-Fitr (Ramadan Eid)",
    date(2025, 4, 10): "Shri Mahavir Jayanti",
    date(2025, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2025, 4, 18): "Good Friday",
    date(2025, 5, 1):  "Maharashtra Day",
    date(2025, 8, 15): "Independence Day",
    date(2025, 8, 27): "Ganesh Chaturthi",
    date(2025, 10, 2): "Mahatma Gandhi Jayanti / Dussehra",
    date(2025, 10, 21): "Diwali Laxmi Pujan",
    date(2025, 10, 22): "Diwali-Balipratipada",
    date(2025, 11, 5): "Prakash Gurpurb Sri Guru Nanak Dev",
    date(2025, 12, 25): "Christmas",
}

_HOLIDAYS_2026: dict[date, str] = {
    date(2026, 1, 15): "Municipal Corporation Election (Maharashtra)",
    date(2026, 1, 26): "Republic Day",
    date(2026, 3, 3):  "Holi",
    date(2026, 3, 26): "Shri Ram Navami",
    date(2026, 3, 31): "Shri Mahavir Jayanti",
    date(2026, 4, 3):  "Good Friday",
    date(2026, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2026, 5, 1):  "Maharashtra Day",
    date(2026, 5, 28): "Bakri Id",
    date(2026, 6, 26): "Muharram",
    date(2026, 9, 14): "Ganesh Chaturthi",
    date(2026, 10, 2): "Mahatma Gandhi Jayanti",
    date(2026, 10, 20): "Dussehra",
    date(2026, 11, 10): "Diwali-Balipratipada",
    date(2026, 11, 24): "Prakash Gurpurb Sri Guru Nanak Dev",
    date(2026, 12, 25): "Christmas",
}

# Master lookup: date -> occasion name (all years merged)
_ALL_HOLIDAYS: dict[date, str] = {**_HOLIDAYS_2024, **_HOLIDAYS_2025, **_HOLIDAYS_2026}


class NSEHolidayCalendar:
    """NSE market holiday calendar for the CM (equities) segment.

    The calendar ships with built-in holiday data for 2024-2026 (sourced from
    official NSE circulars). You can extend or override holidays for any year
    via the ``extra_holidays`` constructor argument.

    A *trading day* is any weekday (Monday-Friday) that is **not** a listed
    public holiday.

    Args:
        extra_holidays: Additional holiday dates to merge with the built-in
                        data (e.g. ad-hoc exchange closures, election days).
                        The built-in holidays are never removed.

    Examples::

        from datetime import date
        from pybhav.holidays import NSEHolidayCalendar

        cal = NSEHolidayCalendar()

        # Check a known holiday
        assert cal.is_holiday(date(2025, 3, 14))          # Holi

        # Check a weekend
        assert not cal.is_trading_day(date(2025, 3, 15))  # Saturday

        # Navigate to the next open session
        nxt = cal.next_trading_day(date(2025, 3, 14))     # 2025-03-17

        # List all trading days in a range
        days = cal.trading_days_in_range("2025-06-01", "2025-06-30")
    """

    def __init__(
        self,
        extra_holidays: Sequence[date] | None = None,
    ) -> None:
        # Start with a mutable copy of the built-in name mapping
        self._holiday_names: dict[date, str] = dict(_ALL_HOLIDAYS)

        # Merge extra holidays; they get a generic name if not supplied as a dict
        if extra_holidays:
            for d in extra_holidays:
                if d not in self._holiday_names:
                    self._holiday_names[d] = "Exchange Holiday"

        # Keep a frozenset of dates for fast membership tests
        self._holidays: FrozenSet[date] = frozenset(self._holiday_names)

    # ------------------------------------------------------------------
    # Core query API
    # ------------------------------------------------------------------

    def is_holiday(self, dt: date | str) -> bool:
        """Return ``True`` if *dt* is a listed public holiday (weekends excluded).

        Note that this only covers holidays recorded in the built-in data or
        supplied via ``extra_holidays``. It does **not** account for weekends
        (use :meth:`is_trading_day` for a combined check).
        """
        return _coerce(dt) in self._holidays

    def holiday_name(self, dt: date | str) -> Optional[str]:
        """Return the occasion name for a holiday date, or ``None`` if not a holiday.

        Examples::

            cal.holiday_name(date(2025, 3, 14))   # 'Holi'
            cal.holiday_name(date(2025, 6, 9))    # None  (trading day)
        """
        return self._holiday_names.get(_coerce(dt))

    def is_weekend(self, dt: date | str) -> bool:
        """Return ``True`` if *dt* falls on a Saturday or Sunday."""
        return _coerce(dt).weekday() >= 5  # 5=Saturday, 6=Sunday

    def is_trading_day(self, dt: date | str) -> bool:
        """Return ``True`` if *dt* is an NSE trading day.

        A trading day is a weekday that is not a listed public holiday.
        """
        d = _coerce(dt)
        return not self.is_weekend(d) and not self.is_holiday(d)

    def holidays_in_year(self, year: int) -> list[date]:
        """Return all recorded holidays for *year*, sorted ascending.

        Includes both built-in and any extra holidays supplied at construction.
        """
        return sorted(d for d in self._holidays if d.year == year)

    def trading_days_in_range(
        self,
        start: date | str,
        end: date | str,
    ) -> list[date]:
        """Return a sorted list of all trading days between *start* and *end* (inclusive).

        Args:
            start: First date of the range.
            end:   Last date of the range (inclusive).
        """
        start_d, end_d = _coerce(start), _coerce(end)
        if start_d > end_d:
            return []
        return [d for d in _iter_dates(start_d, end_d) if self.is_trading_day(d)]

    def next_trading_day(self, dt: date | str, *, inclusive: bool = False) -> date:
        """Return the next NSE trading day after *dt*.

        Args:
            dt:        Reference date.
            inclusive: If ``True`` and *dt* itself is a trading day, return
                       *dt* unchanged. Defaults to ``False`` (always moves
                       forward at least one day).
        """
        d = _coerce(dt)
        if not inclusive:
            d += timedelta(days=1)
        while not self.is_trading_day(d):
            d += timedelta(days=1)
        return d

    def previous_trading_day(self, dt: date | str, *, inclusive: bool = False) -> date:
        """Return the most recent NSE trading day before *dt*.

        Args:
            dt:        Reference date.
            inclusive: If ``True`` and *dt* itself is a trading day, return
                       *dt* unchanged. Defaults to ``False`` (always moves
                       backward at least one day).
        """
        d = _coerce(dt)
        if not inclusive:
            d -= timedelta(days=1)
        while not self.is_trading_day(d):
            d -= timedelta(days=1)
        return d

    def add_holiday(self, dt: date | str, name: str = "Exchange Holiday") -> None:
        """Add a single holiday to this calendar instance (mutates in place).

        Useful for adding ad-hoc exchange closures discovered after
        construction (e.g. election holidays announced at short notice).

        Args:
            dt:   The date to mark as a holiday.
            name: Human-readable occasion name shown in error messages.
        """
        d = _coerce(dt)
        self._holiday_names[d] = name
        self._holidays = frozenset(self._holidays | {d})

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __contains__(self, dt: object) -> bool:
        """Support ``date(...) in calendar`` syntax (checks :meth:`is_holiday`)."""
        if isinstance(dt, (date, str)):
            return self.is_holiday(dt)
        return NotImplemented

    def __repr__(self) -> str:
        return (
            f"NSEHolidayCalendar("
            f"holidays={len(self._holidays)}, "
            f"years={sorted({d.year for d in self._holidays})})"
        )


# ---------------------------------------------------------------------------
# Module-level convenience singleton
# ---------------------------------------------------------------------------

#: A ready-to-use default calendar instance (built-in holidays only).
#: Import and use directly when no customisation is needed::
#:
#:     from pybhav.holidays import nse_calendar
#:     nse_calendar.is_trading_day(date.today())
nse_calendar = NSEHolidayCalendar()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _coerce(dt: date | str) -> date:
    """Convert an ISO-format string to a :class:`datetime.date`."""
    if isinstance(dt, str):
        return date.fromisoformat(dt)
    return dt


def _iter_dates(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)
