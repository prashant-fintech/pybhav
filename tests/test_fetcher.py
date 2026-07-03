import io
import zipfile
from datetime import date
from unittest.mock import MagicMock

import pytest

from pybhav.fetcher import NSEHttpFetcher, _ZipExtractor
from pybhav.exceptions import BhavcopNotAvailable, DownloadError


def _make_zip(csv_content: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("bhav.csv", csv_content)
    return buf.getvalue()


def test_zip_extractor_returns_csv_bytes():
    csv = "SYMBOL,OPEN\nRELIANCE,2900"
    result = _ZipExtractor().extract(_make_zip(csv), "http://example.com")
    assert b"RELIANCE" in result


def test_zip_extractor_bad_zip_raises_download_error():
    with pytest.raises(DownloadError, match="Invalid ZIP"):
        _ZipExtractor().extract(b"notazip", "http://example.com")


def test_fetch_404_raises_not_available():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    fetcher = NSEHttpFetcher(session=mock_session)
    with pytest.raises(BhavcopNotAvailable):
        fetcher.fetch("CM", date(2025, 6, 28))


def test_fetch_success_returns_csv_bytes():
    csv = "SYMBOL,OPEN\nINFY,1800"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = _make_zip(csv)
    mock_resp.raise_for_status = MagicMock()
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    fetcher = NSEHttpFetcher(session=mock_session)
    result = fetcher.fetch("CM", date(2025, 6, 30))
    assert b"INFY" in result
