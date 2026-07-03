"""URL construction for NSE archive files."""

from datetime import date

SEGMENTS = {
    "CM":  "https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{mon}/cm{date}bhav.csv.zip",
    "FO":  "https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{year}/{mon}/fo{date}bhav.csv.zip",
    "CD":  "https://nsearchives.nseindia.com/content/historical/CURRENCY/{year}/{mon}/cd{date}bhav.csv.zip",
    "SME": "https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{mon}/MS{date}bhav.csv.zip",
}

NSE_HOME = "https://www.nseindia.com"


def build_url(segment: str, dt: date) -> str:
    """Return the archive download URL for a given segment and date."""
    segment = segment.upper()
    if segment not in SEGMENTS:
        raise ValueError(f"Unknown segment '{segment}'. Choose from: {list(SEGMENTS)}")
    return SEGMENTS[segment].format(
        year=dt.strftime("%Y"),
        mon=dt.strftime("%b").upper(),
        date=dt.strftime("%d%b%Y").upper(),
    )
