"""pybhav — Download NSE bhavcopy (end-of-day market data)."""

from .cache import FileCache, NullCache
from .client import NSEBhavcopy
from .exceptions import BhavcopNotAvailable, DownloadError, PybhavError, SessionError
from .fetcher import NSEHttpFetcher
from .holidays import NSEHolidayCalendar, nse_calendar
from .parser import NSECsvParser
from .protocols import BhavcopCache, BhavcopFetcher, BhavcopParser

__version__ = "0.1.0"
__all__ = [
    # Main client
    "NSEBhavcopy",
    # Exceptions
    "PybhavError",
    "BhavcopNotAvailable",
    "DownloadError",
    "SessionError",
    # Protocols — implement these to extend pybhav
    "BhavcopCache",
    "BhavcopFetcher",
    "BhavcopParser",
    # Concrete implementations
    "FileCache",
    "NullCache",
    "NSEHttpFetcher",
    "NSECsvParser",
    # Holiday calendar
    "NSEHolidayCalendar",
    "nse_calendar",
]
