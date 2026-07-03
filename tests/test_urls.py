from datetime import date
import pytest
from pybhav.urls import build_url


def test_cm_url():
    dt = date(2025, 6, 30)
    url = build_url("CM", dt)
    assert "EQUITIES" in url
    assert "30JUN2025" in url
    assert url.endswith(".csv.zip")


def test_fo_url():
    dt = date(2025, 6, 30)
    url = build_url("FO", dt)
    assert "DERIVATIVES" in url
    assert "fo30JUN2025" in url


def test_case_insensitive():
    dt = date(2025, 6, 30)
    assert build_url("cm", dt) == build_url("CM", dt)


def test_unknown_segment():
    with pytest.raises(ValueError, match="Unknown segment"):
        build_url("XX", date(2025, 6, 30))
