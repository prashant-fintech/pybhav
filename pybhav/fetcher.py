"""NSE HTTP fetcher — downloads and extracts bhavcopy ZIP archives."""

from __future__ import annotations

import io
import time
import zipfile
from datetime import date

from curl_cffi import requests
from curl_cffi.requests import errors

from .exceptions import BhavcopNotAvailable, DownloadError
from .protocols import BhavcopFetcher
from .session import make_session
from .urls import build_url

_DEFAULT_RETRIES = 3
_BACKOFF = 1.5


class _ZipExtractor:
    """Extracts the first CSV file from a ZIP archive payload."""

    def extract(self, zip_bytes: bytes, source_url: str) -> bytes:
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                if not csv_names:
                    raise DownloadError(f"No CSV found in ZIP from {source_url}")
                return zf.read(csv_names[0])
        except zipfile.BadZipFile as exc:
            raise DownloadError(
                f"Invalid ZIP received from {source_url}: {exc}"
            ) from exc


class NSEHttpFetcher(BhavcopFetcher):
    """Fetch bhavcopy CSV bytes over HTTP from NSE archives.

    Args:
        retries: Number of retry attempts on transient HTTP errors.
        timeout: HTTP timeout in seconds.
        session: Optional pre-built requests.Session (useful for testing).
    """

    def __init__(
        self,
        retries: int = _DEFAULT_RETRIES,
        timeout: int = 30,
        session: requests.Session | None = None,
    ):
        self._retries = retries
        self._timeout = timeout
        self._session = session
        self._extractor = _ZipExtractor()

    def _get_session(self) -> requests.Session:
        if self._session is None:
            self._session = make_session(timeout=self._timeout)
        return self._session

    def fetch(self, segment: str, dt: date) -> bytes:
        """Download and return raw CSV bytes for the given segment and date."""
        url = build_url(segment, dt)
        sess = self._get_session()

        for attempt in range(1, self._retries + 1):
            try:
                resp = sess.get(url, timeout=self._timeout)
                if resp.status_code == 404:
                    raise BhavcopNotAvailable(
                        f"No bhavcopy for segment={segment} date={dt.isoformat()} "
                        f"(holiday, weekend, or future date)"
                    )
                resp.raise_for_status()
                return self._extractor.extract(resp.content, url)
            except BhavcopNotAvailable:
                raise
            except errors.RequestsError as exc:
                if attempt == self._retries:
                    raise DownloadError(
                        f"Download failed after {self._retries} attempts: {exc}"
                    ) from exc
                time.sleep(_BACKOFF * attempt)

        raise DownloadError("Download failed")  # satisfies type checkers
