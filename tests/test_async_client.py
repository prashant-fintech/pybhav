"""Tests for the asynchronous client methods in NSEBhavcopy."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from pybhav.cache import NullCache
from pybhav.client import NSEBhavcopy
from pybhav.exceptions import BhavcopNotAvailable
from pybhav.protocols import AsyncBhavcopFetcher


class MockAsyncFetcher(AsyncBhavcopFetcher):
    """A mock async fetcher that always returns a simple CSV byte string."""
    def __init__(self):
        self.mock_fetch = AsyncMock(return_value=b"SYMBOL,OPEN\nINFY,1800\n")
        
    async def fetch(self, segment: str, dt: date) -> bytes:
        return await self.mock_fetch(segment, dt)


@pytest.mark.asyncio
class TestAsyncClient:
    async def test_async_get_fetches_and_parses(self):
        """async_get() should await the fetcher and return a DataFrame."""
        fetcher = MockAsyncFetcher()
        nse = NSEBhavcopy(cache=NullCache(), async_fetcher=fetcher)
        
        # 09 Jun 2025 is a normal Monday
        df = await nse.async_get(date(2025, 6, 9))
        
        assert not df.empty
        assert len(df) == 1
        assert df.iloc[0]["SYMBOL"] == "INFY"
        fetcher.mock_fetch.assert_awaited_once_with("CM", date(2025, 6, 9))

    async def test_async_get_raises_for_holiday(self):
        """async_get() should immediately raise BhavcopNotAvailable for a holiday."""
        fetcher = MockAsyncFetcher()
        nse = NSEBhavcopy(cache=NullCache(), async_fetcher=fetcher)
        
        # 14 Mar 2025 is Holi
        with pytest.raises(BhavcopNotAvailable, match="Holi"):
            await nse.async_get(date(2025, 3, 14))
            
        # The fetcher should not be hit
        fetcher.mock_fetch.assert_not_awaited()

    async def test_async_get_range_fetches_concurrently(self):
        """async_get_range() should gather multiple days concurrently."""
        fetcher = MockAsyncFetcher()
        nse = NSEBhavcopy(cache=NullCache(), async_fetcher=fetcher)
        
        # Mon, Tue, Wed
        start = date(2025, 6, 9)
        end = date(2025, 6, 11)
        
        df = await nse.async_get_range(start, end, concurrency=2)
        
        assert len(df) == 3
        # Should have fetched exactly 3 times
        assert fetcher.mock_fetch.await_count == 3
        
        # The _date column should have been injected
        dates = df["_date"].tolist()
        assert date(2025, 6, 9) in dates
        assert date(2025, 6, 11) in dates

    async def test_async_get_range_skips_weekends_by_default(self):
        """async_get_range() should skip weekends when skip_errors=True."""
        fetcher = MockAsyncFetcher()
        nse = NSEBhavcopy(cache=NullCache(), async_fetcher=fetcher)
        
        # Fri, Sat, Sun, Mon
        start = date(2025, 6, 6)
        end = date(2025, 6, 9)
        
        df = await nse.async_get_range(start, end)
        
        # Should only return Fri and Mon
        assert len(df) == 2
        assert fetcher.mock_fetch.await_count == 2
        
        dates = df["_date"].tolist()
        assert date(2025, 6, 6) in dates
        assert date(2025, 6, 9) in dates
        assert date(2025, 6, 7) not in dates

    async def test_lazy_instantiation_of_default_fetcher(self):
        """If no async_fetcher is provided, it should lazily create AsyncNSEHttpFetcher."""
        nse = NSEBhavcopy(cache=NullCache())
        
        # We need to mock the actual AsyncNSEHttpFetcher to avoid hitting the network
        with patch("pybhav.async_fetcher.AsyncNSEHttpFetcher") as mock_fetcher_cls:
            mock_instance = mock_fetcher_cls.return_value
            mock_instance.fetch = AsyncMock(return_value=b"SYMBOL\nTEST\n")
            
            await nse.async_get(date(2025, 6, 9))
            
            mock_fetcher_cls.assert_called_once()
            mock_instance.fetch.assert_awaited_once()
