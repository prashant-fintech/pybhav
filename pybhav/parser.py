"""Concrete BhavcopParser implementation for NSE CSV data."""

from __future__ import annotations

import io

import pandas as pd

from .protocols import BhavcopParser


class NSECsvParser(BhavcopParser):
    """Parse raw bhavcopy CSV bytes into a cleaned pandas DataFrame."""

    def parse(self, data: bytes) -> pd.DataFrame:
        df = pd.read_csv(io.BytesIO(data))
        df.columns = df.columns.str.strip()
        return df
