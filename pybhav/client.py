"""NSEBhavcopy — high-level client composed from injected dependencies."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

import pandas as pd

from .cache import FileCache, NullCache
from .exceptions import BhavcopNotAvailable
from .fetcher import NSEHttpFetcher
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
    ):
        self._cache: BhavcopCache = cache or (
            FileCache(cache_dir) if cache_dir else NullCache()
        )
        self._fetcher: BhavcopFetcher = fetcher or NSEHttpFetcher(
            retries=retries, timeout=timeout
        )
        self._parser: BhavcopParser = parser or NSECsvParser()

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
        """
        dt = _parse_date(dt)
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

    def download(
        self,
        dt: date | str,
        segment: str = "CM",
        dest: str | Path = ".",
    ) -> Path:
        """Download bhavcopy CSV to a directory and return the file path.

        Bytes are served from the cache when available, so a second call for
        the same date does not re-hit the network.
        """
        dt = _parse_date(dt)
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


def _date_range(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)
