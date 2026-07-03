"""NSEBhavcopy — high-level client composed from injected dependencies."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from .cache import FileCache, NullCache
from .exceptions import BhavcopNotAvailable
from .fetcher import NSEHttpFetcher
from .holidays import NSEHolidayCalendar, nse_calendar
from .parser import NSECsvParser
from .protocols import BhavcopCache, BhavcopFetcher, BhavcopParser


class NSEBhavcopy:
    """High-level client for downloading NSE bhavcopy data.

    All three dependencies (cache, fetcher, parser) are injected via the
    constructor so they can be replaced for testing or extended behaviour.
    The positional arguments (cache_dir, retries, timeout) configure the
    default concrete implementations when no explicit deps are provided.

    Args:
        cache_dir: Directory for the default FileCache. Pass ``None`` to
                   disable caching (a NullCache is used instead).
        retries: Retry attempts for the default NSEHttpFetcher.
        timeout: HTTP timeout in seconds for the default NSEHttpFetcher.
        cache: Override the cache entirely with any BhavcopCache.
        fetcher: Override the fetcher entirely with any BhavcopFetcher.
        parser: Override the parser entirely with any BhavcopParser.
        calendar: Override the holiday calendar with any NSEHolidayCalendar.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = "~/.pybhav_cache",
        retries: int = 3,
        timeout: int = 30,
        *,
        cache: BhavcopCache | None = None,
        fetcher: BhavcopFetcher | None = None,
        parser: BhavcopParser | None = None,
        calendar: NSEHolidayCalendar | None = None,
    ):
        self._cache: BhavcopCache = cache or (
            FileCache(cache_dir) if cache_dir else NullCache()
        )
        self._fetcher: BhavcopFetcher = fetcher or NSEHttpFetcher(
            retries=retries, timeout=timeout
        )
        self._parser: BhavcopParser = parser or NSECsvParser()
        self._calendar: NSEHolidayCalendar = calendar or nse_calendar

    def _load(self, segment: str, dt: date) -> bytes:
        if self._cache.has(segment, dt):
            return self._cache.get(segment, dt)
        data = self._fetcher.fetch(segment, dt)
        self._cache.put(segment, dt, data)
        return data

    def get(self, dt: date | str, segment: str = "CM") -> pd.DataFrame:
        """Download bhavcopy and return as a DataFrame.

        Args:
            dt: Trading date as a ``date`` object or ``"YYYY-MM-DD"`` string.
            segment: One of ``CM``, ``FO``, ``CD``, ``SME``.

        Raises:
            BhavcopNotAvailable: If *dt* is a weekend or a known NSE holiday.
        """
        dt = _parse_date(dt)
        _check_trading_day(dt, self._calendar)
        return self._parser.parse(self._load(segment, dt))

    def get_range(
        self,
        start: date | str,
        end: date | str,
        segment: str = "CM",
        skip_errors: bool = True,
    ) -> pd.DataFrame:
        """Download bhavcopy for a date range and return a combined DataFrame.

        Args:
            start: Start date (inclusive).
            end: End date (inclusive).
            segment: Bhavcopy segment.
            skip_errors: Silently skip dates where data is unavailable
                         (weekends, holidays). Set to ``False`` to raise instead.
        """
        start, end = _parse_date(start), _parse_date(end)
        frames = []
        for dt in _date_range(start, end):
            try:
                df = self.get(dt, segment=segment)
                df["_date"] = dt
                frames.append(df)
            except BhavcopNotAvailable:
                if not skip_errors:
                    raise
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def get_latest(self, segment: str = "CM") -> pd.DataFrame:
        """Download the latest *available* bhavcopy and return it as a DataFrame.

        NSE publishes the bhavcopy after **19:00 IST** on each trading day.
        This method works out the correct date automatically:

        - If **today is a trading day** and the current IST time is **≥ 19:00**
          → downloads **today's** bhavcopy.
        - Otherwise (before 19:00, or today is a weekend/holiday)
          → downloads the **most recent previous trading day's** bhavcopy.

        Args:
            segment: One of ``CM``, ``FO``, ``CD``, ``SME``. Defaults to ``CM``.

        Returns:
            A DataFrame for the latest available bhavcopy date.

        Example::

            nse = NSEBhavcopy()
            df = nse.get_latest()           # always returns most recent data
            df = nse.get_latest(segment="FO")
        """
        target = _latest_trading_date(self._calendar)
        return self._parser.parse(self._load(segment, target))

    def download(
        self,
        dt: date | str,
        segment: str = "CM",
        dest: str | Path = ".",
    ) -> Path:
        """Download bhavcopy CSV to a directory and return the file path.

        Bytes are served from the cache when available, so a second call for
        the same date does not re-hit the network.

        Raises:
            BhavcopNotAvailable: If *dt* is a weekend or a known NSE holiday.
        """
        dt = _parse_date(dt)
        _check_trading_day(dt, self._calendar)
        data = self._load(segment, dt)
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / f"{segment.lower()}_{dt.isoformat()}_bhav.csv"
        path.write_bytes(data)
        return path


def _parse_date(dt: date | str) -> date:
    if isinstance(dt, str):
        return date.fromisoformat(dt)
    return dt


# IST = UTC +05:30
_IST = timezone(timedelta(hours=5, minutes=30))

# Bhavcopy is published on NSE servers after this time each trading day (IST)
_BHAVCOPY_CUTOFF = time(19, 0)  # 19:00 IST


def _latest_trading_date(
    calendar: NSEHolidayCalendar,
    _now: Optional[datetime] = None,
) -> date:
    """Return the date of the latest available NSE bhavcopy.

    Rules (all times in IST):
    - If today is a trading day **and** current time >= 19:00 → use today.
    - Otherwise → use the most recent previous trading day.

    Args:
        calendar: The holiday calendar used to determine trading days.
        _now:     Override the current datetime (IST). Useful for testing.
                  Defaults to ``datetime.now(_IST)``.
    """
    now_ist = _now if _now is not None else datetime.now(_IST)
    today = now_ist.date()
    current_time = now_ist.time().replace(tzinfo=None)  # naive for comparison

    if calendar.is_trading_day(today) and current_time >= _BHAVCOPY_CUTOFF:
        return today

    # Before cut-off, weekend, or holiday → fall back to previous trading day
    return calendar.previous_trading_day(today, inclusive=False)


_DAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]


def _check_trading_day(dt: date, calendar: NSEHolidayCalendar) -> None:
    """Raise :exc:`BhavcopNotAvailable` with a clear reason for weekends and holidays.

    The exception message always includes:
    - The date and day-of-week
    - The specific reason (e.g. "Saturday", "Holi", "Republic Day")
    - The next available NSE trading day
    """
    day_name = _DAY_NAMES[dt.weekday()]
    next_td = calendar.next_trading_day(dt, inclusive=False)

    if dt.weekday() == 5:  # Saturday
        raise BhavcopNotAvailable(
            f"NSE bhavcopy is not available for {dt.strftime('%d %b %Y')} ({day_name}). "
            f"The exchange is closed on Saturdays. "
            f"Next trading day: {next_td.strftime('%d %b %Y')} ({_DAY_NAMES[next_td.weekday()]})."
        )

    if dt.weekday() == 6:  # Sunday
        raise BhavcopNotAvailable(
            f"NSE bhavcopy is not available for {dt.strftime('%d %b %Y')} ({day_name}). "
            f"The exchange is closed on Sundays. "
            f"Next trading day: {next_td.strftime('%d %b %Y')} ({_DAY_NAMES[next_td.weekday()]})."
        )

    occasion = calendar.holiday_name(dt)
    if occasion:
        raise BhavcopNotAvailable(
            f"NSE bhavcopy is not available for {dt.strftime('%d %b %Y')} ({day_name}). "
            f"The exchange is closed for {occasion}. "
            f"Next trading day: {next_td.strftime('%d %b %Y')} ({_DAY_NAMES[next_td.weekday()]})."
        )


def _date_range(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)
