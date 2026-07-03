"""NSE HTTP async fetcher — downloads and extracts bhavcopy ZIP archives concurrently."""

from __future__ import annotations

import asyncio
from datetime import date

from curl_cffi.requests import AsyncSession, errors

from .exceptions import BhavcopNotAvailable, DownloadError, SessionError
from .fetcher import _BACKOFF, _DEFAULT_RETRIES, _ZipExtractor
from .protocols import AsyncBhavcopFetcher
from .session import _HEADERS
from .urls import NSE_HOME, build_url


async def async_make_session(timeout: int = 10) -> AsyncSession:
    """Create and warm up an AsyncSession against NSE."""
    client = AsyncSession(impersonate="chrome110", headers=_HEADERS, timeout=timeout)
    try:
        resp = await client.get(NSE_HOME)
        resp.raise_for_status()
    except errors.RequestsError as exc:
        # curl_cffi AsyncSession uses an async close() method
        await client.close()
        raise SessionError(
            f"Failed to warm up async NSE session: {exc}"
        ) from exc
    return client


class AsyncNSEHttpFetcher(AsyncBhavcopFetcher):
    """Fetch bhavcopy CSV bytes asynchronously over HTTP from NSE archives.

    Args:
        retries: Number of retry attempts on transient HTTP errors.
        timeout: HTTP timeout in seconds.
        client: Optional pre-built AsyncSession (useful for testing).
    """

    def __init__(
        self,
        retries: int = _DEFAULT_RETRIES,
        timeout: int = 30,
        client: AsyncSession | None = None,
    ):
        self._retries = retries
        self._timeout = timeout
        self._client = client
        self._extractor = _ZipExtractor()

    async def _get_client(self) -> AsyncSession:
        if self._client is None:
            self._client = await async_make_session(timeout=self._timeout)
        return self._client

    async def fetch(self, segment: str, dt: date) -> bytes:
        """Download and return raw CSV bytes for the given segment and date asynchronously."""
        url = build_url(segment, dt)
        client = await self._get_client()

        for attempt in range(1, self._retries + 1):
            try:
                resp = await client.get(url, timeout=self._timeout)
                if resp.status_code == 404:
                    raise BhavcopNotAvailable(
                        f"No bhavcopy for segment={segment} date={dt.isoformat()} "
                        f"(holiday, weekend, or future date)"
                    )
                resp.raise_for_status()

                # Zip extraction is technically CPU-bound but it's very fast
                # for these small files (~5MB zipped). We could wrap it in
                # asyncio.to_thread if profiling shows it blocking the event loop.
                return self._extractor.extract(resp.content, url)

            except BhavcopNotAvailable:
                raise
            except errors.RequestsError as exc:
                if attempt == self._retries:
                    raise DownloadError(
                        f"Download failed after {self._retries} attempts: {exc}"
                    ) from exc
                await asyncio.sleep(_BACKOFF * attempt)

        raise DownloadError("Download failed")  # satisfies type checkers
