"""Tests for the pre-flight holiday/weekend checks wired into NSEBhavcopy."""

from datetime import date

import pytest

from pybhav.client import NSEBhavcopy
from pybhav.exceptions import BhavcopNotAvailable


def _make_client() -> NSEBhavcopy:
    """Client with no-op fetcher/cache — network never hit."""
    from unittest.mock import MagicMock
    from pybhav.cache import NullCache

    mock_fetcher = MagicMock()
    return NSEBhavcopy(cache=NullCache(), fetcher=mock_fetcher)


# ---------------------------------------------------------------------------
# Saturday
# ---------------------------------------------------------------------------

class TestSaturdayMessage:
    def test_get_saturday_raises(self):
        nse = _make_client()
        with pytest.raises(BhavcopNotAvailable) as exc_info:
            nse.get(date(2025, 6, 7))  # Saturday
        msg = str(exc_info.value)
        assert "07 Jun 2025" in msg
        assert "Saturday" in msg
        assert "Next trading day" in msg
        # Next trading day after a Saturday is Monday
        assert "Monday" in msg

    def test_download_saturday_raises(self, tmp_path):
        nse = _make_client()
        with pytest.raises(BhavcopNotAvailable) as exc_info:
            nse.download(date(2025, 6, 7), dest=str(tmp_path))
        assert "Saturday" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Sunday
# ---------------------------------------------------------------------------

class TestSundayMessage:
    def test_get_sunday_raises(self):
        nse = _make_client()
        with pytest.raises(BhavcopNotAvailable) as exc_info:
            nse.get(date(2025, 6, 8))  # Sunday
        msg = str(exc_info.value)
        assert "08 Jun 2025" in msg
        assert "Sunday" in msg
        assert "Next trading day" in msg


# ---------------------------------------------------------------------------
# Public holiday (named occasion)
# ---------------------------------------------------------------------------

class TestHolidayMessage:
    def test_get_holi_raises_with_occasion(self):
        nse = _make_client()
        with pytest.raises(BhavcopNotAvailable) as exc_info:
            nse.get(date(2025, 3, 14))  # Holi
        msg = str(exc_info.value)
        assert "14 Mar 2025" in msg
        assert "Holi" in msg
        assert "Next trading day" in msg
        # Next trading day after Holi (Friday) is Monday 17 Mar
        assert "17 Mar 2025" in msg

    def test_get_republic_day_raises_with_occasion(self):
        nse = _make_client()
        with pytest.raises(BhavcopNotAvailable) as exc_info:
            nse.get(date(2026, 1, 26))  # Republic Day (Monday)
        msg = str(exc_info.value)
        assert "Republic Day" in msg
        assert "Next trading day" in msg

    def test_get_christmas_raises_with_occasion(self):
        nse = _make_client()
        with pytest.raises(BhavcopNotAvailable) as exc_info:
            nse.get(date(2025, 12, 25))  # Christmas
        assert "Christmas" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Normal trading day — no exception
# ---------------------------------------------------------------------------

class TestTradingDayPassesThrough:
    def test_trading_day_calls_fetcher(self):
        """Pre-flight check must NOT raise for a regular trading day."""
        from unittest.mock import MagicMock
        import io, zipfile
        from pybhav.cache import NullCache

        # Build a dummy zip/csv so the fetcher+parser don't error
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("bhav.csv", "SYMBOL,OPEN\nRELIANCE,2900\n")
        zip_bytes = buf.getvalue()

        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = b"SYMBOL,OPEN\nRELIANCE,2900\n"

        nse = NSEBhavcopy(cache=NullCache(), fetcher=mock_fetcher)
        # Monday 09 Jun 2025 — no holiday
        df = nse.get(date(2025, 6, 9))
        mock_fetcher.fetch.assert_called_once()
        assert not df.empty


# ---------------------------------------------------------------------------
# get_range — skip_errors should swallow the new detailed messages too
# ---------------------------------------------------------------------------

class TestGetRangeSkipsClosedDays:
    def test_range_spanning_weekend_returns_only_weekdays(self):
        from unittest.mock import MagicMock
        from pybhav.cache import NullCache

        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = b"SYMBOL,OPEN\nINFY,1800\n"

        nse = NSEBhavcopy(cache=NullCache(), fetcher=mock_fetcher)
        # Mon–Sun: should only fetch Mon, Tue, Wed, Thu, Fri (5 calls)
        df = nse.get_range(date(2025, 6, 9), date(2025, 6, 15))
        assert mock_fetcher.fetch.call_count == 5
