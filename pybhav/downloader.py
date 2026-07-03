"""HTTP fetch with retry and ZIP extraction."""

import io
import time
import zipfile
from datetime import date
from pathlib import Path

import requests

from .exceptions import BhavcopNotAvailable, DownloadError
from .session import make_session
from .urls import build_url

_DEFAULT_RETRIES = 3
_BACKOFF = 1.5  # seconds between retries


def fetch_csv(
    segment: str,
    dt: date,
    session: requests.Session | None = None,
    retries: int = _DEFAULT_RETRIES,
    timeout: int = 30,
) -> bytes:
    """Download bhavcopy and return raw CSV bytes."""
    url = build_url(segment, dt)
    sess = session or make_session(timeout=timeout)

    for attempt in range(1, retries + 1):
        try:
            resp = sess.get(url, timeout=timeout)
            if resp.status_code == 404:
                raise BhavcopNotAvailable(
                    f"No bhavcopy for segment={segment} date={dt.isoformat()} "
                    f"(holiday, weekend, or future date)"
                )
            resp.raise_for_status()
            return _extract_csv(resp.content, url)
        except BhavcopNotAvailable:
            raise
        except requests.RequestException as exc:
            if attempt == retries:
                raise DownloadError(
                    f"Download failed after {retries} attempts: {exc}"
                ) from exc
            time.sleep(_BACKOFF * attempt)

    raise DownloadError("Download failed")  # unreachable but satisfies type checkers


def download_to_file(
    segment: str,
    dt: date,
    dest: str | Path,
    session: requests.Session | None = None,
    retries: int = _DEFAULT_RETRIES,
    timeout: int = 30,
) -> Path:
    """Download bhavcopy CSV to *dest* directory. Returns the written file path."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    csv_bytes = fetch_csv(segment, dt, session=session, retries=retries, timeout=timeout)
    filename = f"{segment.lower()}_{dt.isoformat()}_bhav.csv"
    path = dest / filename
    path.write_bytes(csv_bytes)
    return path


def _extract_csv(zip_bytes: bytes, source_url: str) -> bytes:
    """Extract the single CSV from a ZIP archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
            if not csv_names:
                raise DownloadError(f"No CSV found in ZIP from {source_url}")
            return zf.read(csv_names[0])
    except zipfile.BadZipFile as exc:
        raise DownloadError(f"Invalid ZIP received from {source_url}: {exc}") from exc
