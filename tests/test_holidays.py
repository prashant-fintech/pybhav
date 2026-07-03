"""Tests for pybhav.holidays — NSEHolidayCalendar."""

from datetime import date

import pytest

from pybhav.holidays import NSEHolidayCalendar, nse_calendar


# ---------------------------------------------------------------------------
# is_holiday
# ---------------------------------------------------------------------------

class TestIsHoliday:
    def test_known_holiday_2024(self):
        # Republic Day 2024
        assert nse_calendar.is_holiday(date(2024, 1, 26)) is True

    def test_known_holiday_2025_string(self):
        # Holi 2025 — also accepts ISO string
        assert nse_calendar.is_holiday("2025-03-14") is True

    def test_known_holiday_2026(self):
        # Good Friday 2026
        assert nse_calendar.is_holiday(date(2026, 4, 3)) is True

    def test_regular_weekday_not_holiday(self):
        # A normal Tuesday
        assert nse_calendar.is_holiday(date(2025, 6, 10)) is False

    def test_weekend_not_listed_as_holiday(self):
        # Weekends are NOT in the holiday list — is_holiday is holiday-only
        assert nse_calendar.is_holiday(date(2025, 6, 7)) is False  # Saturday


# ---------------------------------------------------------------------------
# is_weekend
# ---------------------------------------------------------------------------

class TestIsWeekend:
    @pytest.mark.parametrize("dt", [
        date(2025, 6, 7),   # Saturday
        date(2025, 6, 8),   # Sunday
    ])
    def test_weekend_days(self, dt):
        assert nse_calendar.is_weekend(dt) is True

    @pytest.mark.parametrize("dt", [
        date(2025, 6, 9),   # Monday
        date(2025, 6, 13),  # Friday
    ])
    def test_weekdays_not_weekend(self, dt):
        assert nse_calendar.is_weekend(dt) is False


# ---------------------------------------------------------------------------
# is_trading_day
# ---------------------------------------------------------------------------

class TestIsTradingDay:
    def test_holiday_is_not_trading_day(self):
        assert nse_calendar.is_trading_day(date(2025, 3, 14)) is False  # Holi

    def test_saturday_is_not_trading_day(self):
        assert nse_calendar.is_trading_day(date(2025, 6, 7)) is False

    def test_sunday_is_not_trading_day(self):
        assert nse_calendar.is_trading_day(date(2025, 6, 8)) is False

    def test_regular_weekday_is_trading_day(self):
        assert nse_calendar.is_trading_day(date(2025, 6, 9)) is True  # Monday

    def test_string_input_accepted(self):
        assert nse_calendar.is_trading_day("2025-06-09") is True


# ---------------------------------------------------------------------------
# holidays_in_year
# ---------------------------------------------------------------------------

class TestHolidaysInYear:
    def test_2025_count(self):
        h = nse_calendar.holidays_in_year(2025)
        assert len(h) == 14  # 14 listed holidays

    def test_2025_sorted(self):
        h = nse_calendar.holidays_in_year(2025)
        assert h == sorted(h)

    def test_2024_includes_republic_day(self):
        h = nse_calendar.holidays_in_year(2024)
        assert date(2024, 1, 26) in h

    def test_unknown_year_returns_empty(self):
        h = nse_calendar.holidays_in_year(2099)
        assert h == []


# ---------------------------------------------------------------------------
# trading_days_in_range
# ---------------------------------------------------------------------------

class TestTradingDaysInRange:
    def test_excludes_weekends_and_holidays(self):
        # June 2025: no holidays in June per NSE list
        days = nse_calendar.trading_days_in_range("2025-06-02", "2025-06-06")
        # Mon–Fri, no holidays → 5 trading days
        assert len(days) == 5

    def test_excludes_holi_2025(self):
        # Week containing Holi (Fri 2025-03-14)
        days = nse_calendar.trading_days_in_range("2025-03-10", "2025-03-14")
        # Mon–Thu = 4 days; Friday is Holi → 4 trading days
        assert len(days) == 4
        assert date(2025, 3, 14) not in days

    def test_inverted_range_returns_empty(self):
        days = nse_calendar.trading_days_in_range("2025-06-10", "2025-06-01")
        assert days == []

    def test_single_holiday_returns_empty(self):
        days = nse_calendar.trading_days_in_range("2025-03-14", "2025-03-14")
        assert days == []

    def test_single_trading_day(self):
        days = nse_calendar.trading_days_in_range("2025-06-09", "2025-06-09")
        assert days == [date(2025, 6, 9)]


# ---------------------------------------------------------------------------
# next_trading_day / previous_trading_day
# ---------------------------------------------------------------------------

class TestNavigationMethods:
    def test_next_trading_day_skips_holiday(self):
        # Holi = Friday 2025-03-14; next trading day is Monday 2025-03-17
        nxt = nse_calendar.next_trading_day(date(2025, 3, 14))
        assert nxt == date(2025, 3, 17)

    def test_next_trading_day_skips_weekend(self):
        # Friday → next is Monday
        nxt = nse_calendar.next_trading_day(date(2025, 6, 6))
        assert nxt == date(2025, 6, 9)

    def test_next_trading_day_inclusive_on_trading_day(self):
        d = date(2025, 6, 9)  # Monday, not a holiday
        assert nse_calendar.next_trading_day(d, inclusive=True) == d

    def test_next_trading_day_inclusive_on_holiday_still_advances(self):
        # inclusive=True but date is a holiday → should advance
        nxt = nse_calendar.next_trading_day(date(2025, 3, 14), inclusive=True)
        assert nxt == date(2025, 3, 17)

    def test_previous_trading_day_skips_weekend(self):
        # Monday → previous is Friday
        prev = nse_calendar.previous_trading_day(date(2025, 6, 9))
        assert prev == date(2025, 6, 6)

    def test_previous_trading_day_inclusive_on_trading_day(self):
        d = date(2025, 6, 9)
        assert nse_calendar.previous_trading_day(d, inclusive=True) == d


# ---------------------------------------------------------------------------
# add_holiday
# ---------------------------------------------------------------------------

class TestAddHoliday:
    def test_add_holiday_marks_day_as_holiday(self):
        cal = NSEHolidayCalendar()
        target = date(2025, 6, 9)  # normally a trading day
        assert cal.is_trading_day(target) is True
        cal.add_holiday(target)
        assert cal.is_holiday(target) is True
        assert cal.is_trading_day(target) is False

    def test_add_holiday_custom_name_stored(self):
        cal = NSEHolidayCalendar()
        cal.add_holiday(date(2025, 6, 9), name="State Election")
        assert cal.holiday_name(date(2025, 6, 9)) == "State Election"

    def test_add_holiday_default_name(self):
        cal = NSEHolidayCalendar()
        cal.add_holiday(date(2025, 6, 10))
        assert cal.holiday_name(date(2025, 6, 10)) == "Exchange Holiday"

    def test_add_holiday_does_not_affect_singleton(self):
        # Mutating a custom instance should not pollute nse_calendar
        cal = NSEHolidayCalendar()
        cal.add_holiday(date(2025, 6, 9))
        assert nse_calendar.is_trading_day(date(2025, 6, 9)) is True


# ---------------------------------------------------------------------------
# extra_holidays constructor argument
# ---------------------------------------------------------------------------

class TestExtraHolidays:
    def test_extra_holidays_respected(self):
        extra = [date(2025, 6, 9), date(2025, 6, 10)]
        cal = NSEHolidayCalendar(extra_holidays=extra)
        assert cal.is_holiday(date(2025, 6, 9)) is True
        assert cal.is_holiday(date(2025, 6, 10)) is True

    def test_builtin_holidays_still_present(self):
        cal = NSEHolidayCalendar(extra_holidays=[date(2025, 6, 9)])
        assert cal.is_holiday(date(2025, 3, 14)) is True  # Holi still there


# ---------------------------------------------------------------------------
# holiday_name
# ---------------------------------------------------------------------------

class TestHolidayName:
    def test_returns_occasion_name_for_holiday(self):
        assert nse_calendar.holiday_name(date(2025, 3, 14)) == "Holi"

    def test_returns_occasion_name_for_2026(self):
        assert nse_calendar.holiday_name(date(2026, 1, 26)) == "Republic Day"

    def test_returns_none_for_trading_day(self):
        assert nse_calendar.holiday_name(date(2025, 6, 9)) is None

    def test_returns_none_for_weekend(self):
        # Weekends are not in the holiday name map
        assert nse_calendar.holiday_name(date(2025, 6, 7)) is None

    def test_string_input_accepted(self):
        assert nse_calendar.holiday_name("2025-03-14") == "Holi"


# ---------------------------------------------------------------------------
# __contains__
# ---------------------------------------------------------------------------

class TestContains:
    def test_in_operator_for_holiday(self):
        cal = NSEHolidayCalendar()
        assert date(2025, 3, 14) in cal

    def test_in_operator_for_non_holiday(self):
        cal = NSEHolidayCalendar()
        assert date(2025, 6, 9) not in cal


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------

class TestRepr:
    def test_repr_contains_years(self):
        r = repr(nse_calendar)
        assert "2024" in r
        assert "2025" in r
        assert "2026" in r
