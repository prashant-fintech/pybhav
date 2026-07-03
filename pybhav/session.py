"""NSE session management.

NSE's servers check for a valid browser-like session (cookies + Referer).
Warming up by hitting the homepage seeds the required cookies.
"""

import requests
from .exceptions import SessionError
from .urls import NSE_HOME

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": NSE_HOME,
}


def make_session(timeout: int = 10) -> requests.Session:
    """Create and warm up a requests.Session against NSE."""
    session = requests.Session()
    session.headers.update(_HEADERS)
    try:
        resp = session.get(NSE_HOME, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise SessionError(f"Failed to warm up NSE session: {exc}") from exc
    return session
