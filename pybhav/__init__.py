"""pybhav — Download NSE bhavcopy (end-of-day market data)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

import pandas as pd

from .cache import Cache
from .downloader import download_to_file, fetch_csv
from .exceptions import BhavcopNotAvailable, DownloadError, PybhavError, SessionError
from .parser import parse
from .session import make_session

__version__ = "0.1.0"
__all__ = [
    "NSEBhavcopy",
    "PybhavError",
    "BhavcopNotAvailable",
    "DownloadError",
    "SessionError",
]


class NSEBhavcopy:
    """High-level client for downloading NSE bhavcopy data.

    Args:
        cache_dir: Directory to cache downloaded CSVs. Pass None to disable caching.
        retries: Number of download retry attempts on transient failures.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = "~/.pybhav_cache",
        retries: int = 3,
        timeout: int = 30,
    ):
        self._cache = Cache(cache_dir) if cache_dir else None
        self._retries = retries
        self._timeout = timeout
        self._session = None

    def _get_session(self):
        if self._session is None:
            self._session = make_session(timeout=self._timeout)
        return self._session

    def _fetch(self, segment: str, dt: date) -> bytes:
        if self._cache and self._cache.has(segment, dt):
            return self._cache.get(segment, dt)
        csv_bytes = fetch_csv(
            segment, dt,
            session=self._get_session(),
            retries=self._retries,
            timeout=self._timeout,
        )
        if self._cache:
            self._cache.put(segment, dt, csv_bytes)
        return csv_bytes

    def get(self, dt: date | str, segment: str = "CM") -> pd.DataFrame:
        """Download bhavcopy and return as a DataFrame.

        Args:
            dt: Trading date as ``date`` object or ``"YYYY-MM-DD"`` string.
            segment: One of ``CM``, ``FO``, ``CD``, ``SME``.
        """
        dt = _parse_date(dt)
        return parse(self._fetch(segment, dt))

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
            skip_errors: If True, silently skip dates where data is unavailable
                         (weekends, holidays). If False, raise on first error.
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
        """Download bhavcopy CSV to a directory and return the file path."""
        dt = _parse_date(dt)
        return download_to_file(
            segment, dt, dest,
            session=self._get_session(),
            retries=self._retries,
            timeout=self._timeout,
        )


def _parse_date(dt: date | str) -> date:
    if isinstance(dt, str):
        return date.fromisoformat(dt)
    return dt


def _date_range(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)
