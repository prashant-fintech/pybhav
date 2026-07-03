"""NSEBhavcopy — high-level client composed from injected dependencies.

All behaviour is provided by four strategies injected via the constructor:

- :class:`~pybhav.protocols.BhavcopCache`    — caching layer
- :class:`~pybhav.protocols.BhavcopFetcher`  — HTTP download layer
- :class:`~pybhav.protocols.BhavcopParser`   — CSV parsing layer
- :class:`~pybhav.protocols.BhavcopCalendar` — holiday/trading-day logic
- :class:`~pybhav.protocols.BhavcopSchedule` — publish-time schedule

The client itself contains *no* business logic about holidays, timezones, or
publish times — it only orchestrates the pipeline.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

import pandas as pd

from .cache import FileCache, NullCache
from .exceptions import BhavcopNotAvailable
from .fetcher import NSEHttpFetcher
from .holidays import NSEHolidayCalendar, nse_calendar
from .parser import NSECsvParser
from .protocols import (
    BhavcopCache,
    BhavcopCalendar,
    BhavcopFetcher,
    BhavcopParser,
    BhavcopSchedule,
)
from .schedule import NSEBhavSchedule, nse_schedule


_DAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]


class NSEBhavcopy:
    """High-level client for downloading NSE bhavcopy data.

    All five dependencies are injected via the constructor — swap any of them
    to extend behaviour without modifying this class.
    The client depends exclusively on abstractions, never on concretions.

    Args:
        cache_dir: Directory for the default :class:`~pybhav.cache.FileCache`.
                   Pass ``None`` to disable caching.
        retries:   Retry attempts for the default
                   :class:`~pybhav.fetcher.NSEHttpFetcher`.
        timeout:   HTTP timeout in seconds for the default fetcher.
        cache:     Override the cache with any :class:`~pybhav.protocols.BhavcopCache`.
        fetcher:   Override the HTTP layer with any :class:`~pybhav.protocols.BhavcopFetcher`.
        parser:    Override the parser with any :class:`~pybhav.protocols.BhavcopParser`.
        calendar:  Override the holiday calendar with any
                   :class:`~pybhav.protocols.BhavcopCalendar`.
        schedule:  Override the publish-time schedule with any
                   :class:`~pybhav.protocols.BhavcopSchedule`.
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
        calendar: BhavcopCalendar | None = None,
        schedule: BhavcopSchedule | None = None,
    ):
        self._cache: BhavcopCache = cache or (
            FileCache(cache_dir) if cache_dir else NullCache()
        )
        self._fetcher: BhavcopFetcher = fetcher or NSEHttpFetcher(
            retries=retries, timeout=timeout
        )
        self._parser: BhavcopParser = parser or NSECsvParser()
        self._calendar: BhavcopCalendar = calendar or nse_calendar
        self._schedule: BhavcopSchedule = schedule or nse_schedule

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self, segment: str, dt: date) -> bytes:
        if self._cache.has(segment, dt):
            return self._cache.get(segment, dt)
        data = self._fetcher.fetch(segment, dt)
        self._cache.put(segment, dt, data)
        return data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, dt: date | str, segment: str = "CM") -> pd.DataFrame:
        """Download bhavcopy and return as a DataFrame.

        Args:
            dt:      Trading date as a ``date`` object or ``"YYYY-MM-DD"`` string.
            segment: One of ``CM``, ``FO``, ``CD``, ``SME``.

        Raises:
            BhavcopNotAvailable: If *dt* is a weekend or a known NSE holiday.
        """
        dt = _parse_date(dt)
        _check_trading_day(dt, self._calendar)
        return self._parser.parse(self._load(segment, dt))

    def get_latest(self, segment: str = "CM") -> pd.DataFrame:
        """Download the latest *available* bhavcopy and return it as a DataFrame.

        The target date is resolved by the injected
        :class:`~pybhav.protocols.BhavcopSchedule` (default: 19:00 IST cutoff).

        - Current time **≥ 19:00 IST** on a trading day → **today's** bhavcopy.
        - Otherwise → **most recent previous trading day's** bhavcopy.

        Args:
            segment: One of ``CM``, ``FO``, ``CD``, ``SME``. Defaults to ``CM``.

        Returns:
            A DataFrame for the latest available bhavcopy date.

        Example::

            nse = NSEBhavcopy()
            df = nse.get_latest()            # auto-selects the right date
            df = nse.get_latest(segment="FO")
        """
        target = self._schedule.latest_trading_date(self._calendar)
        return self._parser.parse(self._load(segment, target))

    def get_range(
        self,
        start: date | str,
        end: date | str,
        segment: str = "CM",
        skip_errors: bool = True,
    ) -> pd.DataFrame:
        """Download bhavcopy for a date range and return a combined DataFrame.

        Args:
            start:       Start date (inclusive).
            end:         End date (inclusive).
            segment:     Bhavcopy segment.
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


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_date(dt: date | str) -> date:
    if isinstance(dt, str):
        return date.fromisoformat(dt)
    return dt


def _check_trading_day(dt: date, calendar: BhavcopCalendar) -> None:
    """Raise :exc:`BhavcopNotAvailable` with a clear reason for weekends / holidays.

    Depends on the :class:`~pybhav.protocols.BhavcopCalendar` abstraction —
    no concrete class is referenced here.

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
