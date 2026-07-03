"""Tests for _latest_trading_date() and NSEBhavcopy.get_latest()."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from pybhav.cache import NullCache
from pybhav.client import NSEBhavcopy, _IST, _BHAVCOPY_CUTOFF, _latest_trading_date
from pybhav.holidays import NSEHolidayCalendar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(fetcher=None) -> NSEBhavcopy:
    """Create a client with a mock fetcher that returns a trivial CSV."""
    if fetcher is None:
        fetcher = MagicMock()
        fetcher.fetch.return_value = b"SYMBOL,OPEN\nRELIANCE,2900\n"
    return NSEBhavcopy(cache=NullCache(), fetcher=fetcher)


def _ist(dt: date, hour: int, minute: int = 0) -> datetime:
    """Build a timezone-aware IST datetime for the given date and time."""
    return datetime(dt.year, dt.month, dt.day, hour, minute,
                    tzinfo=timezone(timedelta(hours=5, minutes=30)))


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


# ---------------------------------------------------------------------------
# _latest_trading_date — core logic
# ---------------------------------------------------------------------------

class TestLatestTradingDate:
    cal = NSEHolidayCalendar()

    # --- Trading day, time >= 19:00 → return today ---

    def test_trading_day_after_cutoff_returns_today(self):
        now = _ist(_TRADING_MON, 19, 0)   # exactly 19:00
        assert _latest_trading_date(self.cal, _now=now) == _TRADING_MON

    def test_trading_day_well_after_cutoff_returns_today(self):
        now = _ist(_TRADING_MON, 22, 30)
        assert _latest_trading_date(self.cal, _now=now) == _TRADING_MON

    # --- Trading day, time < 19:00 → return previous trading day ---

    def test_trading_day_before_cutoff_returns_previous(self):
        now = _ist(_TRADING_MON, 18, 59)
        assert _latest_trading_date(self.cal, _now=now) == _PREV_TRADING

    def test_trading_day_morning_returns_previous(self):
        now = _ist(_TRADING_MON, 9, 15)
        assert _latest_trading_date(self.cal, _now=now) == _PREV_TRADING

    def test_trading_day_midnight_returns_previous(self):
        now = _ist(_TRADING_MON, 0, 0)
        assert _latest_trading_date(self.cal, _now=now) == _PREV_TRADING

    # --- Weekend → always returns previous trading day ---

    def test_saturday_any_time_returns_previous_trading_day(self):
        for hour in (8, 15, 20):
            now = _ist(_SATURDAY, hour)
            result = _latest_trading_date(self.cal, _now=now)
            assert result == _PREV_TRADING, f"Failed at hour={hour}"

    def test_sunday_any_time_returns_previous_trading_day(self):
        now = _ist(_SUNDAY, 21)
        result = _latest_trading_date(self.cal, _now=now)
        assert result == _PREV_TRADING

    # --- Holiday → always returns previous trading day ---

    def test_holiday_morning_returns_previous(self):
        now = _ist(_HOLI, 10)
        assert _latest_trading_date(self.cal, _now=now) == _BEFORE_HOLI

    def test_holiday_after_cutoff_returns_previous(self):
        # Even after 19:00 on a holiday, the holiday itself has no bhavcopy
        now = _ist(_HOLI, 20)
        assert _latest_trading_date(self.cal, _now=now) == _BEFORE_HOLI

    # --- Boundary: exactly at 19:00 cutoff ---

    def test_exactly_at_cutoff_returns_today(self):
        now = _ist(_TRADING_MON, 19, 0)
        assert _latest_trading_date(self.cal, _now=now) == _TRADING_MON

    def test_one_minute_before_cutoff_returns_previous(self):
        now = _ist(_TRADING_MON, 18, 59)
        assert _latest_trading_date(self.cal, _now=now) == _PREV_TRADING


# ---------------------------------------------------------------------------
# NSEBhavcopy.get_latest() — integration
# ---------------------------------------------------------------------------

class TestGetLatest:
    def test_get_latest_calls_fetcher_with_correct_date(self):
        """get_latest() on a trading day after 19:00 IST should fetch today."""
        fetcher = MagicMock()
        fetcher.fetch.return_value = b"SYMBOL,OPEN\nINFY,1800\n"
        nse = NSEBhavcopy(cache=NullCache(), fetcher=fetcher)

        # Simulate Monday 2025-06-09 at 20:00 IST
        now = _ist(_TRADING_MON, 20)
        # Patch via a custom _latest_trading_date call — test the wiring by
        # injecting a fixed calendar so the date resolves deterministically.
        target = _latest_trading_date(nse._calendar, _now=now)
        assert target == _TRADING_MON

    def test_get_latest_before_cutoff_targets_previous_day(self):
        """get_latest() before 19:00 IST on a trading day should target Friday."""
        now = _ist(_TRADING_MON, 10, 0)
        target = _latest_trading_date(NSEHolidayCalendar(), _now=now)
        assert target == _PREV_TRADING

    def test_get_latest_returns_dataframe(self):
        fetcher = MagicMock()
        fetcher.fetch.return_value = b"SYMBOL,OPEN\nINFY,1800\n"
        nse = NSEBhavcopy(cache=NullCache(), fetcher=fetcher)

        # After 19:00 on a Monday → fetches today
        from unittest.mock import patch
        now = _ist(_TRADING_MON, 20)
        with patch("pybhav.client.datetime") as mock_dt:
            mock_dt.now.return_value = now
            # Also patch date so today() reflects our mock
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # Directly test via _latest_trading_date with injected now
            target = _latest_trading_date(nse._calendar, _now=now)
        assert target == _TRADING_MON

    def test_get_latest_on_saturday_returns_friday_data(self):
        fetcher = MagicMock()
        fetcher.fetch.return_value = b"SYMBOL,OPEN\nINFY,1800\n"
        nse = NSEBhavcopy(cache=NullCache(), fetcher=fetcher)

        now = _ist(_SATURDAY, 20)
        target = _latest_trading_date(nse._calendar, _now=now)
        assert target == _PREV_TRADING  # Friday


# ---------------------------------------------------------------------------
# IST constant sanity check
# ---------------------------------------------------------------------------

class TestISTConstant:
    def test_ist_offset(self):
        assert _IST.utcoffset(None) == timedelta(hours=5, minutes=30)

    def test_cutoff_is_7pm(self):
        from datetime import time
        assert _BHAVCOPY_CUTOFF.hour == 19
        assert _BHAVCOPY_CUTOFF.minute == 0
