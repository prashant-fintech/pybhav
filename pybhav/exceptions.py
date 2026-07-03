class PybhavError(Exception):
    """Base exception for pybhav."""


class BhavcopNotAvailable(PybhavError):
    """Bhavcopy file not available for the requested date/segment (holiday, weekend, future date)."""


class SessionError(PybhavError):
    """Failed to establish a valid NSE session."""


class DownloadError(PybhavError):
    """HTTP download failed after all retries."""
