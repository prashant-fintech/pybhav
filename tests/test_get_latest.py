"""Tests for NSEBhavSchedule.latest_trading_date() and NSEBhavcopy.get_latest()."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from pybhav.cache import NullCache
from pybhav.client import NSEBhavcopy
from pybhav.holidays import NSEHolidayCalendar
from pybhav.schedule import NSEBhavSchedule, _IST, _BHAVCOPY_CUTOFF


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(fetcher=None, schedule=None) -> NSEBhavcopy:
    """Create a client with a mock fetcher that returns a trivial CSV."""
    if fetcher is None:
        fetcher = MagicMock()
        fetcher.fetch.return_value = b"SYMBOL,OPEN\nRELIANCE,2900\n"
    return NSEBhavcopy(cache=NullCache(), fetcher=fetcher, schedule=schedule)


def _ist(dt: date, hour: int, minute: int = 0) -> datetime:
    """Build a timezone-aware IST datetime for the given date and time."""
    return datetime(dt.year, dt.month, dt.day, hour, minute, tzinfo=_IST)


def _schedule_at(dt: date, hour: int, minute: int = 0) -> NSEBhavSchedule:
    """Return an NSEBhavSchedule pinned to the given IST date+time."""
    fixed_dt = _ist(dt, hour, minute)
    return NSEBhavSchedule(clock=lambda: fixed_dt)


# A known normal trading day (Monday, no holiday)
_TRADING_MON = date(2025, 6, 9)

# The previous trading day relative to _TRADING_MON
_PREV_TRADING = date(2025, 6, 6)  # Friday

# A Saturday
_SATURDAY = date(2025, 6, 7)

# A Sunday
_SUNDAY = date(2025, 6, 8)

# A known NSE holiday (Holi 2025 — Friday)
_HOLI = date(2025, 3, 14)

# Previous trading day before Holi (Thursday 13 Mar)
_BEFORE_HOLI = date(2025, 3, 13)

_CAL = NSEHolidayCalendar()


# ---------------------------------------------------------------------------
# NSEBhavSchedule.latest_trading_date — core logic
# ---------------------------------------------------------------------------

class TestLatestTradingDate:

    # --- Trading day, time >= 19:00 → return today ---

    def test_trading_day_after_cutoff_returns_today(self):
        s = _schedule_at(_TRADING_MON, 19, 0)
        assert s.latest_trading_date(_CAL) == _TRADING_MON

    def test_trading_day_well_after_cutoff_returns_today(self):
        s = _schedule_at(_TRADING_MON, 22, 30)
        assert s.latest_trading_date(_CAL) == _TRADING_MON

    # --- Trading day, time < 19:00 → return previous trading day ---

    def test_trading_day_before_cutoff_returns_previous(self):
        s = _schedule_at(_TRADING_MON, 18, 59)
        assert s.latest_trading_date(_CAL) == _PREV_TRADING

    def test_trading_day_morning_returns_previous(self):
        s = _schedule_at(_TRADING_MON, 9, 15)
        assert s.latest_trading_date(_CAL) == _PREV_TRADING

    def test_trading_day_midnight_returns_previous(self):
        s = _schedule_at(_TRADING_MON, 0, 0)
        assert s.latest_trading_date(_CAL) == _PREV_TRADING

    # --- Weekend → always returns previous trading day ---

    def test_saturday_any_time_returns_previous_trading_day(self):
        for hour in (8, 15, 20):
            s = _schedule_at(_SATURDAY, hour)
            result = s.latest_trading_date(_CAL)
            assert result == _PREV_TRADING, f"Failed at hour={hour}"

    def test_sunday_any_time_returns_previous_trading_day(self):
        s = _schedule_at(_SUNDAY, 21)
        assert s.latest_trading_date(_CAL) == _PREV_TRADING

    # --- Holiday → always returns previous trading day ---

    def test_holiday_morning_returns_previous(self):
        s = _schedule_at(_HOLI, 10)
        assert s.latest_trading_date(_CAL) == _BEFORE_HOLI

    def test_holiday_after_cutoff_returns_previous(self):
        # Even after 19:00 on a holiday, the holiday itself has no bhavcopy
        s = _schedule_at(_HOLI, 20)
        assert s.latest_trading_date(_CAL) == _BEFORE_HOLI

    # --- Boundary: exactly at 19:00 cutoff ---

    def test_exactly_at_cutoff_returns_today(self):
        s = _schedule_at(_TRADING_MON, 19, 0)
        assert s.latest_trading_date(_CAL) == _TRADING_MON

    def test_one_minute_before_cutoff_returns_previous(self):
        s = _schedule_at(_TRADING_MON, 18, 59)
        assert s.latest_trading_date(_CAL) == _PREV_TRADING


# ---------------------------------------------------------------------------
# NSEBhavcopy.get_latest() — wiring test
# ---------------------------------------------------------------------------

class TestGetLatest:
    def test_get_latest_after_cutoff_fetches_today(self):
        fetcher = MagicMock()
        fetcher.fetch.return_value = b"SYMBOL,OPEN\nINFY,1800\n"
        schedule = _schedule_at(_TRADING_MON, 20)
        nse = _make_client(fetcher=fetcher, schedule=schedule)
        df = nse.get_latest()
        # Must have fetched Monday's data
        fetcher.fetch.assert_called_once_with("CM", _TRADING_MON)
        assert not df.empty

    def test_get_latest_before_cutoff_fetches_previous_day(self):
        fetcher = MagicMock()
        fetcher.fetch.return_value = b"SYMBOL,OPEN\nINFY,1800\n"
        schedule = _schedule_at(_TRADING_MON, 10)  # morning → previous
        nse = _make_client(fetcher=fetcher, schedule=schedule)
        df = nse.get_latest()
        fetcher.fetch.assert_called_once_with("CM", _PREV_TRADING)

    def test_get_latest_on_saturday_fetches_friday(self):
        fetcher = MagicMock()
        fetcher.fetch.return_value = b"SYMBOL,OPEN\nINFY,1800\n"
        schedule = _schedule_at(_SATURDAY, 20)
        nse = _make_client(fetcher=fetcher, schedule=schedule)
        nse.get_latest()
        fetcher.fetch.assert_called_once_with("CM", _PREV_TRADING)

    def test_get_latest_on_holiday_fetches_previous(self):
        fetcher = MagicMock()
        fetcher.fetch.return_value = b"SYMBOL,OPEN\nINFY,1800\n"
        schedule = _schedule_at(_HOLI, 20)
        nse = _make_client(fetcher=fetcher, schedule=schedule)
        nse.get_latest()
        fetcher.fetch.assert_called_once_with("CM", _BEFORE_HOLI)

    def test_custom_schedule_is_respected(self):
        """Any BhavcopSchedule implementation can be injected (DIP test)."""
        from pybhav.protocols import BhavcopCalendar, BhavcopSchedule

        class AlwaysFridaySchedule(BhavcopSchedule):
            def latest_trading_date(self, calendar: BhavcopCalendar) -> date:
                return _PREV_TRADING  # always return Friday

        fetcher = MagicMock()
        fetcher.fetch.return_value = b"SYMBOL,OPEN\nINFY,1800\n"
        nse = NSEBhavcopy(
            cache=NullCache(),
            fetcher=fetcher,
            schedule=AlwaysFridaySchedule(),
        )
        nse.get_latest()
        fetcher.fetch.assert_called_once_with("CM", _PREV_TRADING)


# ---------------------------------------------------------------------------
# IST constant and cutoff sanity checks
# ---------------------------------------------------------------------------

class TestISTConstant:
    def test_ist_offset(self):
        assert _IST.utcoffset(None) == timedelta(hours=5, minutes=30)

    def test_cutoff_is_7pm(self):
        from datetime import time
        assert _BHAVCOPY_CUTOFF.hour == 19
        assert _BHAVCOPY_CUTOFF.minute == 0
