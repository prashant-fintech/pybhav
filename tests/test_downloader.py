import io
import zipfile
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from pybhav.downloader import fetch_csv, _extract_csv
from pybhav.exceptions import BhavcopNotAvailable, DownloadError


def _make_zip(csv_content: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("bhav.csv", csv_content)
    return buf.getvalue()


def test_extract_csv():
    csv = "SYMBOL,OPEN\nRELIANCE,2900"
    result = _extract_csv(_make_zip(csv), "http://example.com")
    assert b"RELIANCE" in result


def test_extract_csv_bad_zip():
    with pytest.raises(DownloadError, match="Invalid ZIP"):
        _extract_csv(b"notazip", "http://example.com")


def test_fetch_csv_404_raises_not_available():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    with pytest.raises(BhavcopNotAvailable):
        fetch_csv("CM", date(2025, 6, 28), session=mock_session)


def test_fetch_csv_success():
    csv = "SYMBOL,OPEN\nINFY,1800"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = _make_zip(csv)
    mock_resp.raise_for_status = MagicMock()
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp

    result = fetch_csv("CM", date(2025, 6, 30), session=mock_session)
    assert b"INFY" in result
