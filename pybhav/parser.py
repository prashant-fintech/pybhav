"""Parse raw bhavcopy CSV bytes into a pandas DataFrame."""

import io
import pandas as pd


def parse(csv_bytes: bytes) -> pd.DataFrame:
    """Return a cleaned DataFrame from raw bhavcopy CSV bytes."""
    df = pd.read_csv(io.BytesIO(csv_bytes))
    df.columns = df.columns.str.strip()
    return df
